"""Independent spline systems, native RGB16 and real author-clock CLI checks."""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_curves import (compile_curves,apply_curves,state_at,coefficients,evaluate,parse_points,validate_curves)
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
import test_float_timeline as fixture
import test_float_preview as preview_fixture
from test_float_lut import write_cube

LINEAR = {'primaries':'bt709','transfer':'linear'}
SRGB = {'primaries':'bt709','transfer':'srgb'}
WORKING = ColorSignal(**LINEAR)
NATIVE_CALLS = []


def effect(**parameters):
    return {'type':'rgb_curves','parameters':{'input_signal':dict(LINEAR),'output_signal':dict(LINEAR),**parameters}}


def track(prop='all.1.y', left=.3, right=.7, mode='linear', stop=100, controls=None):
    k = {'at_tick':0,'value':left,'interpolation':mode}
    if controls is not None: k['control_points'] = controls
    return {'property':prop,'keyframes':[k,{'at_tick':stop,'value':right}]}


def independent_spline(points, values):
    """Dense global second-derivative system, independent of product Thomas solve."""
    p = np.asarray(points,np.float64); x,y = p.T; n = len(x)
    if n==1: return np.full(np.shape(values),y[0])
    matrix = np.zeros((n,n)); rhs = np.zeros(n); matrix[0,0] = matrix[-1,-1] = 1
    for i in range(1,n-1):
        a,b = x[i]-x[i-1],x[i+1]-x[i]
        matrix[i,i-1:i+2] = [a,2*(a+b),b]
        rhs[i] = 6*((y[i+1]-y[i])/b-(y[i]-y[i-1])/a)
    second = np.linalg.solve(matrix,rhs)
    q = np.clip(values,x[0],x[-1]); j = np.clip(np.searchsorted(x,q,side='right')-1,0,n-2)
    h = x[j+1]-x[j]; a,b = (x[j+1]-q)/h,(q-x[j])/h
    out = a*y[j]+b*y[j+1]+((a*a*a-a)*second[j]+(b*b*b-b)*second[j+1])*h*h/6
    return np.clip(out,0,1)


def independent_pchip(points, values, *, native_two_point_extension=False):
    x,y = np.asarray(points,np.float64).T; n = len(x)
    if n==1: return np.full(np.shape(values),y[0])
    h = np.diff(x); d = np.diff(y)/h
    if n==2:
        q = values if native_two_point_extension else np.clip(values,x[0],x[-1])
        return np.clip(y[0]+d[0]*(q-x[0]),0,1)
    slopes = np.zeros(n)
    for i in range(1,n-1):
        if d[i-1]*d[i]>0:
            slopes[i] = 3*(h[i-1]+h[i])/((2*h[i]+h[i-1])/d[i-1]+(h[i]+2*h[i-1])/d[i])
    for j,ha,hb,da,db in ((0,h[0],h[1],d[0],d[1]),(-1,h[-1],h[-2],d[-1],d[-2])):
        m = ((2*ha+hb)*da-ha*db)/(ha+hb)
        slopes[j] = 0 if m*da<=0 else np.sign(m)*min(abs(m),3*abs(da)) if da*db<0 else m
    q = np.clip(values,x[0],x[-1]); j = np.clip(np.searchsorted(x,q,side='right')-1,0,n-2)
    u = (q-x[j])/h[j]
    return np.clip((2*u**3-3*u*u+1)*y[j]+(u**3-2*u*u+u)*h[j]*slopes[j]+(-2*u**3+3*u*u)*y[j+1]+(u**3-u*u)*h[j]*slopes[j+1],0,1)


def independent_native_curve(points, codes, method):
    """Model FFmpeg's integer grid origin and quantization, outside product code."""
    q = codes.astype(np.float64)/65535; p = np.asarray(points,np.float64)
    if method=='natural' and len(points)>1:
        grid = np.floor(p[:,0]*65535).astype(int)
        j = np.clip(np.searchsorted(grid,codes,side='right')-1,0,len(p)-2)
        shifted = p[j,0]+(codes-grid[j])/65535
        result = independent_spline(points,shifted)
        result = np.where(codes<grid[0],p[0,1],np.where(codes>=grid[-1],p[-1,1],result))
    elif method=='natural': result = np.full(q.shape,p[0,1])
    else: result = independent_pchip(points,q,native_two_point_extension=True)
    return np.floor(np.clip(result,0,1)*65535).astype(np.uint16)


class FloatCurvesTests(unittest.TestCase):
    def apply(self, value, e=None, tick=0, **kwargs):
        return apply_curves(value,compile_curves(e or effect()),tick,working_signal=WORKING,**kwargs)

    def assert_bad(self, call):
        with self.assertRaises(AppError): call()

    def test_natural_nonuniform_points_match_independent_dense_system(self):
        points = [(0,.04),(.07,.25),(.39,.21),(.83,.91),(1,.95)]
        q = np.linspace(-.2,1.2,8192)
        np.testing.assert_allclose(evaluate(q,coefficients(points,'natural')),independent_spline(points,q),rtol=0,atol=5e-15)

    def test_one_point_constant_and_two_point_linear_end_extensions(self):
        for points in ([(.4,.6)],[(.2,.1),(.8,.9)]):
            for mode in ('natural','pchip'):
                q = np.linspace(-1,2,101)
                np.testing.assert_allclose(evaluate(q,coefficients(points,mode)),np.interp(q,*np.array(points).T),rtol=0,atol=3e-16)

    def test_pchip_monotone_shape_preservation_and_exact_knots(self):
        points = [(0,0),(.1,.02),(.4,.9),(.8,.95),(1,1)]
        q = np.linspace(0,1,5001); result = evaluate(q,coefficients(points,'pchip'))
        self.assertTrue(np.all(np.diff(result)>=0));self.assertGreaterEqual(float(result.min()),0);self.assertLessEqual(float(result.max()),1)
        np.testing.assert_allclose(evaluate(np.array(points)[:,0],coefficients(points,'pchip')),np.array(points)[:,1],atol=2e-16,rtol=0)

    def test_pchip_extrema_plateaus_and_linear_reproduction(self):
        points = [(0,.1),(.2,.6),(.45,.6),(.7,.2),(1,.8)]
        result = evaluate(np.linspace(.2,.45,100),coefficients(points,'pchip'))
        np.testing.assert_allclose(result,.6,atol=1e-15,rtol=0)
        q = np.linspace(0,1,500);points = [(0,.1),(.13,.204),(.81,.748),(1,.9)]
        np.testing.assert_allclose(evaluate(q,coefficients(points,'pchip')),.1+.8*q,atol=4e-16,rtol=0)

    def test_native_RGB16_natural_and_pchip_all_channels_and_post_master(self):
        rng = np.random.default_rng(102); codes = rng.integers(0,65536,(32,64,4),dtype=np.uint16)
        for mode in ('natural','pchip'):
            for custom in ({'all':'0/.05 .2/.3 .7/.65 1/.95'},
                           {'all':'0/0 .5/.3 1/1','red':'0/.1 .1/.25 .8/.7 1/.9','blue':'.1/.2 .9/.85','post_master':'0/.03 .4/.55 1/.97'}):
                e = effect(interpolation=mode,**custom)
                command = [ffmpeg_path(),'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrap16le','-video_size','64x32','-i','pipe:0',
                    '-vf','curves=interp='+mode+':'+':'.join(('master' if c=='post_master' else c)+"='"+v+"'" for c,v in custom.items()),
                    '-frames:v','1','-pix_fmt','gbrap16le','-f','rawvideo','pipe:1']
                raw = np.moveaxis(codes[...,[1,2,0,3]],2,0).astype('<u2').tobytes()
                result = subprocess.run(command,input=raw,capture_output=True,check=True)
                native = np.moveaxis(np.frombuffer(result.stdout,'<u2').reshape(4,32,64)[[2,0,1,3]],0,-1)
                actual,_ = self.apply(codes.astype(np.float32)/65535,e)
                expected_native = codes.copy(); predicted_base = codes.copy()
                expected_float = np.ones(codes.shape,np.float32);expected_float[...,3] = codes[...,3].astype(np.float32)/65535
                for i,c in enumerate(('red','green','blue')):
                    points = [tuple(map(float,v.split('/'))) for v in custom.get(c,custom['all']).split()]
                    reference = independent_spline if mode=='natural' else independent_pchip
                    mapped = reference(points,(codes[...,i].astype(np.float32)/65535).astype(np.float64))
                    quantized = independent_native_curve(points,codes[...,i],mode)
                    predicted_base[...,i] = quantized
                    if 'post_master' in custom:
                        master = [tuple(map(float,v.split('/'))) for v in custom['post_master'].split()]
                        mapped = reference(master,mapped);quantized = independent_native_curve(master,quantized,mode)
                    expected_float[...,i] = mapped.astype(np.float32);expected_native[...,i] = quantized
                composed_diagnostic = int(np.max(np.abs(expected_native[...,:3].astype(np.int32)-native[...,:3].astype(np.int32))))
                if 'post_master' in custom:
                    base_command = list(command)
                    base_command[base_command.index('-vf')+1] = 'curves=interp='+mode+':'+':'.join(c+"='"+v+"'" for c,v in custom.items() if c!='post_master')
                    base_result = subprocess.run(base_command,input=raw,capture_output=True,check=True)
                    native_base = np.moveaxis(np.frombuffer(base_result.stdout,'<u2').reshape(4,32,64)[[2,0,1,3]],0,-1)
                    stage_one_error = int(np.max(np.abs(predicted_base[...,:3].astype(np.int32)-native_base[...,:3].astype(np.int32))))
                    self.assertLessEqual(stage_one_error,1)
                    master_command = list(command);master_command[master_command.index('-vf')+1] = 'curves=interp='+mode+":master='"+custom['post_master']+"'"
                    master_result = subprocess.run(master_command,input=base_result.stdout,capture_output=True,check=True)
                    self.assertEqual(master_result.stdout,result.stdout)
                    for i in range(3): expected_native[...,i] = independent_native_curve(master,native_base[...,i],mode)
                else: stage_one_error = composed_diagnostic
                delta = int(np.max(np.abs(expected_native[...,:3].astype(np.int32)-native[...,:3].astype(np.int32))))
                direct = float(np.max(np.abs(actual[...,:3].astype(np.float64)*65535-native[...,:3])))
                NATIVE_CALLS.append({'mode':mode,'parameters':custom,'maximum_native_model_error_codes':delta,'native_model_tolerance_codes':1,
                    'first_stage_model_error_codes':stage_one_error,'composed_prediction_diagnostic_codes':composed_diagnostic,
                    'native_combined_equals_explicit_two_stage':True if 'post_master' in custom else None,
                    'continuous_vs_integer_native_diagnostic_codes':direct,'diagnostic_is_not_acceptance':True,'alpha_equal':bool(np.array_equal(native[...,3],codes[...,3]))})
                self.assertLessEqual(delta,1);np.testing.assert_allclose(actual,expected_float,atol=6e-8,rtol=0);np.testing.assert_array_equal(native[...,3],codes[...,3])

    def test_all_is_fallback_and_independent_channel_does_not_receive_it_twice(self):
        value = fixture.rgba((.2,.3,.4,1));actual,meta = self.apply(value,effect(all='0/1 1/0',red='0/0 1/1'))
        np.testing.assert_allclose(actual,fixture.rgba((.2,.7,.6,1)),atol=6e-8,rtol=0)
        self.assertEqual(meta['all_semantics'],'fallback-not-post-master')

    def test_explicit_post_master_executes_after_independent_channels(self):
        actual,_ = self.apply(fixture.rgba((.2,.3,.4,1)),effect(all='0/0 1/.5',red='0/.2 1/1',post_master='0/1 1/0'))
        np.testing.assert_allclose(actual,fixture.rgba((.64,.85,.8,1)),rtol=0,atol=6e-8)

    def test_master_alias_and_curves_type_preserve_legacy_meaning(self):
        e = effect(master='0/1 1/0');e['type'] = 'curves'
        actual,_ = self.apply(fixture.rgba((.2,.3,.4,1)),e)
        np.testing.assert_allclose(actual,fixture.rgba((.8,.7,.6,1)),rtol=0,atol=6e-8)

    def test_identity_preserves_all_65536_gray_values_without_table_quantization(self):
        value = np.ones((256,256,4),np.float32);value[...,:3] = np.arange(65536,dtype=np.float32).reshape(256,256,1)/65535
        actual,_ = self.apply(value);np.testing.assert_array_equal(actual,value);self.assertEqual(len(np.unique(actual[...,0])),65536)

    def test_adjacent_float32_values_and_sub_code_variations_survive(self):
        q = np.array([.2,np.nextafter(np.float32(.2),np.float32(1)),.200001],np.float32)
        value = np.ones((1,3,4),np.float32);value[0,:,:3] = q[:,None]
        actual,_ = self.apply(value,effect(all='0/0 1/.8'))
        self.assertEqual(len(np.unique(actual[...,0])),3)

    def test_source_alpha_negative_zero_subnormal_hidden_rgb_are_preserved(self):
        value = np.ones((1,5,4),np.float32);value[...,0:3] = .2;value[0,:,3] = [0.,-0.,np.nextafter(np.float32(0),np.float32(1)),.5,1.]
        before = value.tobytes();actual,_ = self.apply(value,effect(all='0/1 1/0'))
        np.testing.assert_array_equal(actual[...,3].view('u4'),value[...,3].view('u4'));self.assertEqual(value.tobytes(),before)
        self.assertGreater(float(actual[0,0,0]),.7)

    def test_curve_boundary_explicitly_clamps_negative_and_above_one_values(self):
        actual,_ = self.apply(fixture.rgba((-2,.5,3,1)),effect(all='.2/.1 .8/.9'))
        np.testing.assert_allclose(actual,fixture.rgba((.1,.5,.9,1)),atol=6e-8,rtol=0)

    def test_signal_conversion_and_intensity_mix_are_in_linear_working_rgb(self):
        actual,meta = self.apply(fixture.rgba((.18,.18,.18,.3)),effect(input_signal=SRGB,output_signal=SRGB,all='0/0 1/.5',intensity=.4))
        encoded = 1.055*float(np.float32(.18))**(1/2.4)-.055
        mapped = float(np.float32(np.float32(encoded)*.5));graded = ((mapped+.055)/1.055)**2.4
        expected = np.float32(float(np.float32(.18))*.6+float(np.float32(graded))*.4)
        np.testing.assert_allclose(actual[...,:3],expected,rtol=0,atol=3e-8);self.assertEqual(meta['mix_domain'],'linear-working-straight-RGB')

    def test_intensity_zero_returns_exact_copy_including_out_of_domain_rgb(self):
        value = fixture.rgba((-2,3,.5,-0.));actual,_ = self.apply(value,effect(intensity=0))
        self.assertEqual(actual.tobytes(),value.tobytes());self.assertIsNot(actual,value)

    def test_all_six_author_easings_and_both_bezier_control_forms(self):
        expected = {'linear':.25,'hold':0.,'ease_in':.0625,'ease_out':.4375,'ease_in_out':.125}
        for mode,p in expected.items():
            e = effect(all='0/0 .5/.3 1/1');e['keyframes'] = [track(mode=mode)]
            state,_ = state_at(compile_curves(e),25);self.assertAlmostEqual(state['all'][1][1],.3+.4*p,places=14)
        for controls in ([.2,.8],[.25,.2,.75,.8]):
            e = effect();e['keyframes'] = [track('intensity',0,1,'bezier',controls=controls)]
            self.assertAlmostEqual(state_at(compile_curves(e),50)[1],.5,places=7)

    def test_keyframe_prefixes_parameter_layer_and_immutable_compiled_snapshot(self):
        e = effect(all='0/0 .5/.3 1/1');e['parameters']['keyframes'] = [track('parameters.all.1.y')]
        plan = compile_curves(e);e['parameters']['keyframes'][0]['keyframes'][0]['value'] = .9
        self.assertAlmostEqual(state_at(plan,0)[0]['all'][1][1],.3)

    def test_animated_channel_forks_static_all_and_then_moves_independently(self):
        e = effect(all='0/0 .5/.3 1/1');e['keyframes'] = [track('all.1.y',.3,.9),track('red.1.y',.2,.4)]
        state,_ = state_at(compile_curves(e),50);self.assertAlmostEqual(state['all'][1][1],.6);self.assertAlmostEqual(state['red'][1][1],.3)

    def test_animated_x_coordinates_have_no_eight_bit_grid_restriction(self):
        e = effect(all='0/0 .0001/.2 .5/.4 1/1');e['keyframes'] = [track('all.1.x',.0001,.0002)]
        plan = compile_curves(e);state,_ = state_at(plan,50);self.assertAlmostEqual(state['all'][1][0],.00015)
        self.assertEqual(validate_curves(e,duration_tick=100),[])

    def test_author_sampling_rejects_crossed_or_coincident_x_points(self):
        e = effect(all='0/0 .3/.2 .7/.8 1/1');e['keyframes'] = [track('all.1.x',.3,.8)]
        plan = compile_curves(e);self.assert_bad(lambda:state_at(plan,100));state_at(plan,0)

    def test_bezier_overshoot_clamps_coordinates_and_intensity(self):
        e = effect();e['keyframes'] = [track('intensity',0,1,'bezier',controls=[3,3])]
        self.assertEqual(state_at(compile_curves(e),50)[1],1)

    def test_huge_integer_author_clock_retains_fractional_offset(self):
        start = 2**54; e = effect();t = track('intensity',0,1,stop=2)
        t['keyframes'][0]['at_tick'] = start;t['keyframes'][1]['at_tick'] = start+2;e['keyframes'] = [t]
        self.assertEqual(state_at(compile_curves(e),Fraction(start*2+1,2))[1],.25)

    def test_parser_rejects_expressions_nonfinite_out_of_range_and_bad_order(self):
        for raw in ('','0/0 0/1','1/0 0/1','0/nan 1/1','-1/0 1/1','0/0 1/2','0/0;movie=x','0/0/0','1e999/0'):
            with self.subTest(raw=raw):self.assert_bad(lambda:parse_points(raw))

    def test_parser_maximum_256_points_and_no_silent_point_count_changes(self):
        points = ' '.join(f'{i/255}/{i/255}' for i in range(256));self.assertEqual(len(parse_points(points)),256)
        self.assert_bad(lambda:parse_points(points+' 1/1'))
        e = effect();e['keyframes'] = [track('all.2.y')];self.assert_bad(lambda:compile_curves(e))

    def test_unknown_options_alias_conflicts_and_independent_wrong_type_reject(self):
        for e in (effect(preset='vintage'),effect(all='0/0 1/1',master='0/1 1/0'),effect(interpolation='nearest'),{**effect(red='0/0 1/1'),'type':'curves'}):
            self.assert_bad(lambda:compile_curves(e))

    def test_missing_signals_wrong_working_signal_and_bad_surface_reject(self):
        e = effect();del e['parameters']['input_signal'];self.assert_bad(lambda:compile_curves(e))
        self.assert_bad(lambda:apply_curves(fixture.rgba(),compile_curves(effect()),0,working_signal=ColorSignal(**SRGB)))
        for value in (np.zeros((1,1,4),np.float64),np.zeros((0,1,4),np.float32),np.zeros((1,1,3),np.float32)):
            self.assert_bad(lambda:self.apply(value))

    def test_duplicate_properties_invalid_keys_and_time_controls_reject(self):
        for tracks in ([track(),track()], [track('all.99.y')], [track(mode='unknown')], [track(mode='bezier',controls=[2,0,2,1])]):
            e = effect(all='0/0 .5/.3 1/1');e['keyframes'] = tracks;self.assert_bad(lambda:compile_curves(e))
        for value in (True,float('nan'),2):
            e = effect();e['keyframes'] = [track('intensity',value,1)];self.assert_bad(lambda:compile_curves(e))

    def test_duration_bounds_track_and_key_budgets_reject(self):
        e = effect();e['keyframes'] = [track('intensity',0,1)];self.assertTrue(validate_curves(e,duration_tick=99))
        e['keyframes'] = [track('intensity',0,1)]*2562;self.assert_bad(lambda:compile_curves(e))
        e['keyframes'] = [{'property':'intensity','keyframes':[{'at_tick':i,'value':.5} for i in range(1025)]}];self.assert_bad(lambda:compile_curves(e))

    def test_tile_partition_bit_identity_and_read_only_source(self):
        rng = np.random.default_rng(101);value = rng.random((17,23,4),dtype=np.float32);value.flags.writeable = False
        e = effect(all='0/0 .3/.2 .8/.9 1/1',post_master='0/.03 1/.96')
        a,_ = self.apply(value,e,tile_pixels=1);b,_ = self.apply(value,e,tile_pixels=57);self.assertEqual(a.tobytes(),b.tobytes())

    def test_late_nonfinite_and_bad_alpha_preserve_every_source_byte(self):
        for bad in ((0,float('nan')),(1,float('inf')),(3,1.01)):
            value = np.ones((2,8,4),np.float32);value[-1,-1,bad[0]] = bad[1];before = value.tobytes()
            self.assert_bad(lambda:self.apply(value,tile_pixels=3));self.assertEqual(value.tobytes(),before)

    def test_memory_budget_includes_retained_luts_and_rejects_before_output(self):
        with patch('ai_ad_editor.float_curves.np.empty_like',side_effect=AssertionError('allocated')):
            self.assert_bad(lambda:self.apply(fixture.rgba(),max_working_bytes=1))
        self.assert_bad(lambda:self.apply(fixture.rgba(),retained_table_bytes=768*1024*1024))

    def test_cancellation_mid_tiles_preserves_input(self):
        value = np.ones((3,8,4),np.float32)*.5;before = value.tobytes();calls = []
        def cancel():calls.append(1);return len(calls)>6
        self.assert_bad(lambda:self.apply(value,tile_pixels=1,cancel=cancel));self.assertEqual(value.tobytes(),before)

    def test_ordered_exposure_curves_and_curve_exposure_are_distinct(self):
        compiler = EffectCompiler(resource_root=None,working_signal=WORKING);e = effect(all='0/.1 1/.7')
        exposure = {'type':'exposure','parameters':{'amount':1}}
        a,ma = compiler.apply(fixture.rgba((.2,.3,.4,1)),compiler.compile([exposure,e]),0)
        b,mb = compiler.apply(fixture.rgba((.2,.3,.4,1)),compiler.compile([e,exposure]),0)
        self.assertFalse(np.array_equal(a,b));self.assertEqual([r['type'] for r in ma['ordered_effects']],['exposure','rgb_curves'])
        self.assertEqual([r['type'] for r in mb['ordered_effects']],['rgb_curves','exposure'])

    def test_ordered_lut_curves_and_disabled_effects_use_same_compiler(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp);write_cube(root/'look.cube',2,transform=lambda r,g,b:(r*.5,g*.5,b*.5))
            compiler = EffectCompiler(resource_root=root,working_signal=WORKING)
            lut = {'type':'lut3d','parameters':{'path':'look.cube','input_signal':LINEAR,'output_signal':LINEAR}}
            plans = compiler.compile([lut,{**effect(),'enabled':False},effect(all='0/.1 1/.9')])
            result,meta = compiler.apply(fixture.rgba((.2,.4,.6,1)),plans,0)
            np.testing.assert_allclose(result,fixture.rgba((.18,.26,.34,1)),atol=6e-8,rtol=0)
            self.assertEqual([r['type'] for r in meta['ordered_effects']],['lut3d','rgb_curves']);compiler.verify([plans])

    def test_author_presentation_window_preserves_original_control_point_clock(self):
        e = effect(all='0/0 .5/.3 1/1');e['keyframes'] = [track()]
        p,s = fixture.image_project(fixture.rgba((.5,.5,.5,1)));c = p['sequences'][0]['tracks'][0]['clips'][0]
        c.update(duration_tick=30,presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':100,'offset_tick':40},effects=[e])
        actual,meta = FloatTimeline(p,'main',s,working_signal=WORKING).render_frame(0)
        np.testing.assert_allclose(actual,fixture.rgba((.46,.46,.46,1)),atol=3e-8,rtol=0)
        self.assertEqual(meta['layers'][0]['effects']['ordered_effects'][0]['author_tick'],'40')

    def test_nested_reverse_child_and_group_curves_use_separate_author_clocks(self):
        p,s = fixture.image_project(fixture.rgba((.5,.5,.5,1)));child = copy.deepcopy(p['sequences'][0]);child['id'] = 'child';child['duration_tick'] = 200
        e = effect(all='0/0 .5/.3 1/1');e['keyframes'] = [track(stop=200)]
        child['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e])
        c = p['sequences'][0]['tracks'][0]['clips'][0];c.pop('asset_id');parent = effect(all='0/0 1/1');parent['keyframes'] = [track('intensity',0,1)]
        c.update(sequence_id='child',source_out_tick=200,speed=2,reverse=True,effects=[parent]);p['sequences'].append(child)
        actual,meta = FloatTimeline(p,'main',s,working_signal=WORKING).render_frame(2)
        np.testing.assert_allclose(actual,fixture.rgba((.62,.62,.62,1)),atol=6e-8,rtol=0)
        tick = float(meta['layers'][0]['effects']['ordered_effects'][0]['author_tick'])
        self.assertLess(tick,160);self.assertEqual(tick,np.nextafter(160.,-np.inf))
        self.assertAlmostEqual(meta['layers'][1]['effects']['ordered_effects'][0]['intensity'],.2)

    def test_public_validator_uses_float_points_and_keeps_legacy_restriction(self):
        case = preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.visual(np.ones((2,16,32,4),np.float32)*.5);e = effect(all='0/0 .0001/.1 .5/.4 1/1')
            e['keyframes'] = [track('all.1.x',.0001,.0002,stop=9000),track('post_master.1.y',.9,.8,stop=9000),track('intensity',.5,1,stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects'] = [e]
            from ai_ad_editor.validator import validate_project
            result = validate_project(case.root,case.p);self.assertFalse([r for r in result['errors'] if 'CURVE' in r['code']])
            self.assertFalse([r for r in result['warnings'] if r['code']=='EFFECT_KEYFRAME_PROPERTY_UNSUPPORTED'])
            del case.p['settings']['pixel_pipeline'];result = validate_project(case.root,case.p)
            self.assertTrue([r for r in result['errors'] if 'CURVE' in r['code']])
        finally:case.doCleanups()

    def test_public_validator_reports_missing_signal_even_on_static_curve(self):
        e = effect();del e['parameters']['output_signal'];self.assertTrue(validate_curves(e))
        self.assertEqual(validate_curves({**e,'enabled':False}),[])

    def test_real_render_preview_png16_and_PCM_match_independent_curve(self):
        case = preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick'] = 18000;value = fixture.rgba((.2,.4,.6,.5),shape=(16,32));value[...,0] = np.arange(32,dtype=np.float32)[None,:]/31
            pixels = case.visual(np.stack([value]*2));audio = case.audio();e = effect(all='0/.1 1/.9')
            e['keyframes'] = [track('intensity',.25,.75,stop=9000)];case.s['tracks'][0]['clips'][0]['effects'] = [e]
            result = case.execute(end=2);actual = case.reference(result);source = np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/65535
            expected = source.copy()
            for i,strength in enumerate((.25,.75)):
                graded = (.1+.8*source[i,...,:3].astype(np.float64)).astype(np.float32)
                mixed = (source[i,...,:3].astype(np.float64)*(1-strength)+graded.astype(np.float64)*strength).astype(np.float32)
                expected[i,...,:3] = (mixed.astype(np.float64)*source[i,...,3:4].astype(np.float64)).astype(np.float32)
            expected[...,3] = 1;np.testing.assert_allclose(actual,expected,atol=6e-8,rtol=0)
            self.assertEqual(case.pcm(result),audio[:9600].tobytes())
            np.testing.assert_allclose(case.png(case.execute(mode='frame')),np.rint(expected[0].astype(np.float64)*65535),atol=1,rtol=0)
            from ai_ad_editor.render import render_project
            from ai_ad_editor.project import project_write_lock
            with project_write_lock(case.root):formal = render_project(case.root,case.p,case.s,case.root/'renders/curves.mkv')
            manifest = json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            payload = np.moveaxis(np.rint(expected[...,[1,2,0,3]].astype(np.float64)*65535).astype('<u2'),3,1).tobytes()
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],'sha256:'+hashlib.sha256(payload).hexdigest());case.assert_clean()
        finally:case.doCleanups()

    def test_real_preview_cache_invalidates_curve_controls_and_keeps_authored_IR(self):
        case = preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick'] = 18000;case.visual(np.ones((2,16,32,4),np.float32)*.5);case.audio()
            case.s['tracks'][0]['clips'][0]['effects'] = [effect(all='0/.1 1/.9')]
            first = case.execute(end=2);before = copy.deepcopy(case.p);cached = case.execute(end=2);self.assertTrue(cached['cache_hit'])
            for section in ('settings','assets','sequences'):self.assertEqual(case.p[section],before[section])
            case.s['tracks'][0]['clips'][0]['effects'][0]['parameters']['post_master'] = '0/0 1/.5'
            changed = case.execute(end=2);self.assertNotEqual(changed['cache_key'],first['cache_key']);self.assertFalse(changed['cache_hit']);case.assert_clean()
        finally:case.doCleanups()

    def test_invalid_temporal_crossing_fails_transaction_and_preserves_existing_output(self):
        e = effect(all='0/0 .3/.2 .7/.8 1/1');e['keyframes'] = [track('all.1.x',.3,.8)]
        value = fixture.rgba();before = value.tobytes();self.assert_bad(lambda:self.apply(value,e,tick=100));self.assertEqual(value.tobytes(),before)
