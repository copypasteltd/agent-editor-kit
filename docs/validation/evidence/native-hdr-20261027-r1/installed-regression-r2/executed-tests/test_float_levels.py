"""Real Float32 native comparisons, independent colour and author-clock checks."""
import copy
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_levels import (compile_levels,apply_levels,state_at,compile_animated_exposure,
    exposure_at,apply_animated_exposure,validate_native,PARAMETER_NAMES)
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
    return {'type':'color_levels','parameters':{'input_signal':dict(LINEAR),'output_signal':dict(LINEAR),**parameters}}


def track(prop,left,right,mode='linear',start=0,stop=100,controls=None):
    key = {'at_tick':start,'value':left,'interpolation':mode}
    if controls is not None:key['control_points'] = controls
    return {'property':prop,'keyframes':[key,{'at_tick':stop,'value':right,'interpolation':'linear'}]}


def native(value,options,kind='colorlevels'):
    h,w = value.shape[:2]
    args = [ffmpeg_path(),'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrapf32le',
        '-video_size',f'{w}x{h}','-i','pipe:0','-vf',kind+'='+options,
        '-frames:v','1','-threads','1','-pix_fmt','gbrapf32le','-f','rawvideo','pipe:1']
    payload = np.moveaxis(value[...,[1,2,0,3]],2,0).astype('<f4').tobytes()
    p = subprocess.run(args,input=payload,capture_output=True,check=True)
    out = np.moveaxis(np.frombuffer(p.stdout,'<f4').reshape(4,h,w),0,2)[...,[2,0,1,3]].copy()
    NATIVE_CALLS.append({'filter':kind,'options':options,'pixels':h*w,'input_sha256':hashlib.sha256(payload).hexdigest(),
        'output_sha256':hashlib.sha256(p.stdout).hexdigest(),'native_output_finite':bool(np.isfinite(out).all())})
    return out


def oracle_preserve(rgb,mode):
    # Scalar binary64 mathematics independent from the vectorized product and
    # from the real native comparison. "avg" intentionally includes +1.
    r,g,b = [float(v) for v in rgb]
    if mode=='lum':return max(r,g,b)+min(r,g,b)
    if mode=='max':return max(r,g,b)
    if mode=='avg':return (r+g+b+1)/3
    if mode=='sum':return r+g+b
    if mode=='nrm':return math.sqrt(r*r+g*g+b*b)
    return math.cbrt(r*r*r+g*g*g+b*b*b)


class FloatLevelsTests(unittest.TestCase):
    def apply(self,value,e=None,tick=0,**options):
        return apply_levels(value,compile_levels(e or effect()),tick,working_signal=WORKING,**options)

    def bad(self,call):
        with self.assertRaises(AppError):call()

    def test_identity_preserves_negative_superwhite_and_alpha_bits(self):
        a = np.random.default_rng(103).uniform(-.5,2,(8,16,4)).astype(np.float32);a[...,3] = .5
        a[0,:3,3] = [-0.,np.nextafter(np.float32(0),np.float32(1)),1]
        out,m = self.apply(a);self.assertEqual(out.tobytes(),a.tobytes());self.assertEqual(m['RGB_clipping'],'none')

    def test_shared_endpoints_match_closed_affine_values_without_clipping(self):
        a = fixture.rgba((-.2,.4,1.4,.3));out,_ = self.apply(a,effect(input_black=.1,input_white=.9,output_black=.2,output_white=.8))
        expected = (a[...,:3].astype(np.float64)-.1)*.75+.2
        np.testing.assert_allclose(out[...,:3],expected,atol=2e-7,rtol=0);self.assertGreater(float(out[...,2].min()),1)

    def test_independent_RGBA_endpoints_match_real_native_float32(self):
        a = np.random.default_rng(33).uniform(0,1,(8,16,4)).astype(np.float32)
        e = effect(red_input_black=.07,red_input_white=.91,green_output_black=.11,blue_output_white=.82,alpha_output_black=.1,alpha_output_white=.9)
        actual,_ = self.apply(a,e);expected = native(a,'rimin=.07:rimax=.91:gomin=.11:bomax=.82:aomin=.1:aomax=.9')
        np.testing.assert_allclose(actual,expected,atol=2e-7,rtol=2e-7)

    def test_all_seven_preserve_modes_match_native_and_scalar_oracle(self):
        a = np.random.default_rng(71).uniform(.05,.95,(9,15,4)).astype(np.float32)
        for mode in ('none','lum','max','avg','sum','nrm','pwr'):
            out,_ = self.apply(a,effect(output_black=.06,red_output_white=.8,green_output_white=.91,blue_output_white=.72,preserve=mode))
            expected = native(a,'romin=.06:gomin=.06:bomin=.06:romax=.8:gomax=.91:bomax=.72:preserve='+mode)
            error = float(np.max(np.abs(out.astype(np.float64)-expected.astype(np.float64))))
            NATIVE_CALLS[-1]['maximum_absolute_product_error'] = error
            np.testing.assert_allclose(out,expected,atol=2e-6,rtol=3e-6)
            for y,x in ((0,0),(4,7),(8,14)):
                before = a[y,x,:3].astype(np.float64);mapped = (before*np.array([.74,.85,.66])+.06)
                if mode!='none':mapped *= oracle_preserve(before,mode)/oracle_preserve(mapped,mode)
                np.testing.assert_allclose(out[y,x,:3],mapped,atol=4e-7,rtol=0)

    def test_preserve_lum_is_max_plus_min_and_avg_includes_one(self):
        a = fixture.rgba((.2,.4,.7,1));e = effect(red_output_white=.6,blue_output_white=.8)
        lum,_ = self.apply(a,{**e,'parameters':{**e['parameters'],'preserve':'lum'}})
        avg,_ = self.apply(a,{**e,'parameters':{**e['parameters'],'preserve':'avg'}})
        np.testing.assert_allclose(lum[0,0,:3],np.array([.12,.4,.56])*.9/.68,atol=2e-7,rtol=0)
        np.testing.assert_allclose(avg[0,0,:3],np.array([.12,.4,.56])*2.3/2.08,atol=2e-7,rtol=0)

    def test_preserve_signed_cube_root_and_nonpositive_output_metric(self):
        for mode in ('lum','max','avg','sum','nrm','pwr'):
            a = fixture.rgba((-.7,-.2,.1,.5));out,_ = self.apply(a,effect(output_white=.7,preserve=mode))
            expected = native(a,'romax=.7:gomax=.7:bomax=.7:preserve='+mode)
            np.testing.assert_allclose(out,expected,atol=2e-6,rtol=3e-6)

    def test_whole_surface_auto_endpoints_include_late_and_hidden_pixels(self):
        a = np.linspace(.2,.8,3*13*4,dtype=np.float32).reshape(3,13,4);a[...,3] = .5
        a[0,0] = [-.2,-.3,-.1,0];a[-1,-1,:3] = [1.2,1.4,1.1]
        out,m = self.apply(a,effect(input_black=-1,input_white=-1),tile_pixels=2)
        observed = native(a,'rimin=-1:gimin=-1:bimin=-1:rimax=-1:gimax=-1:bimax=-1')
        NATIVE_CALLS[-1].update(scope='diagnostic-native-planar-auto-cross-channel-difference-not-an-equivalence-assertion',
            maximum_absolute_product_difference=float(np.max(np.abs(out.astype(np.float64)-observed.astype(np.float64)))))
        expected = a.copy()
        for c in range(3):
            low,high = min(1.,float(a[...,c].min())),max(0.,float(a[...,c].max()))
            expected[...,c] = ((a[...,c].astype(np.float64)-low)/(high-low)).astype(np.float32)
        np.testing.assert_allclose(out,expected,atol=2e-7,rtol=2e-7)
        self.assertEqual(m['effective_endpoints']['red']['input_black'],float(np.float32(-.2)))
        self.assertEqual(m['effective_endpoints']['green']['input_white'],float(np.float32(1.4)))

    def test_auto_normalized_seed_policy_outside_unit_range(self):
        for colour in ((2,3,4,1),(-4,-3,-2,1)):
            a = fixture.rgba(colour);out,m = self.apply(a,effect(input_black=-1,input_white=-.01))
            observed = native(a,'rimin=-1:gimin=-1:bimin=-1:rimax=-.01:gimax=-.01:bimax=-.01')
            NATIVE_CALLS[-1].update(scope='diagnostic-native-planar-auto-cross-channel-difference-not-an-equivalence-assertion',
                maximum_absolute_product_difference=float(np.max(np.abs(out.astype(np.float64)-observed.astype(np.float64)))))
            expected = a.copy();expected[...,:3] = 1 if colour[0]>0 else 0
            np.testing.assert_allclose(out,expected,atol=2e-7,rtol=2e-7)
            self.assertEqual(m['effective_endpoints']['red']['input_black' if colour[0]>0 else 'input_white'],1 if colour[0]>0 else 0)

    def test_native_planar_auto_cross_channel_difference_is_explicit(self):
        outputs = [];native_outputs = []
        for low,high in ((.1,.9),(.2,.8)):
            a = np.ones((4,64,4),np.float32);a[...,0] = np.linspace(.3,.7,64,dtype=np.float32)
            a[...,1] = np.linspace(low,high,64,dtype=np.float32);a[...,2] = .5
            out,_ = self.apply(a,effect(red_input_black=-1,red_input_white=-1));outputs.append(out[...,0])
            observed = native(a,'rimin=-1:rimax=-1');native_outputs.append(observed[...,0])
            NATIVE_CALLS[-1]['scope'] = 'native-planar-cross-channel-observation-not-product-semantics'
        self.assertEqual(outputs[0].tobytes(),outputs[1].tobytes())
        self.assertFalse(np.array_equal(native_outputs[0],native_outputs[1]))
        np.testing.assert_allclose(outputs[0][0],np.linspace(0,1,64),atol=2e-7,rtol=0)

    def test_explicit_automatic_alpha_uses_its_own_complete_plane(self):
        a = np.random.default_rng(92).uniform(.2,.8,(5,9,4)).astype(np.float32)
        out,m = self.apply(a,effect(alpha_input_black=-1,alpha_input_white=-1))
        low,high = float(a[...,3].min()),float(a[...,3].max())
        np.testing.assert_allclose(out[...,3],(a[...,3].astype(np.float64)-low)/(high-low),atol=2e-7,rtol=0)
        self.assertEqual(out[...,:3].tobytes(),a[...,:3].tobytes());self.assertEqual(m['effective_endpoints']['alpha']['input_black'],low)

    def test_reversed_input_and_output_ranges_are_valid_native_operations(self):
        a = fixture.rgba((.2,.5,1.2,.5));out,_ = self.apply(a,effect(input_black=.8,input_white=.2,output_black=.9,output_white=.1))
        np.testing.assert_allclose(out,native(a,'rimin=.8:gimin=.8:bimin=.8:rimax=.2:gimax=.2:bimax=.2:romin=.9:gomin=.9:bomin=.9:romax=.1:gomax=.1:bomax=.1'),atol=2e-7,rtol=2e-7)

    def test_zero_span_reject_and_explicit_flat_frame_policy(self):
        a = fixture.rgba((.5,.5,.5,.4));before = a.tobytes()
        self.bad(lambda:self.apply(a,effect(input_black=-1,input_white=-1)))
        self.assertEqual(a.tobytes(),before)
        out,_ = self.apply(a,effect(input_black=-1,input_white=-1,output_black=.2,zero_span='output_black'))
        np.testing.assert_array_equal(out[...,:3],np.float32(.2));self.assertEqual(out[...,3].tobytes(),a[...,3].tobytes())

    def test_explicit_alpha_map_is_independent_of_shared_RGB_endpoints(self):
        a = fixture.rgba((.2,.4,.6,.5));out,_ = self.apply(a,effect(output_black=.1,output_white=.8,alpha_output_black=.2,alpha_output_white=.6))
        np.testing.assert_allclose(out[0,0],[.24,.38,.52,.4],atol=1e-7,rtol=0)
        plain,_ = self.apply(a,effect(output_black=.1,output_white=.8));self.assertEqual(plain[...,3].tobytes(),a[...,3].tobytes())

    def test_alpha_outside_coverage_rejects_and_partial_mix_is_explicit(self):
        a = fixture.rgba((.2,.4,.6,.5));before = a.tobytes()
        self.bad(lambda:self.apply(a,effect(alpha_input_black=.6,alpha_input_white=1)))
        self.assertEqual(a.tobytes(),before)
        out,_ = self.apply(a,effect(alpha_input_black=.6,alpha_input_white=1,intensity=.25))
        np.testing.assert_allclose(out[...,3],.3125,atol=1e-7,rtol=0)

    def test_zero_intensity_preserves_every_bit_and_does_not_fail_flat_auto(self):
        a = fixture.rgba((.5,.5,.5,-0.));out,m = self.apply(a,effect(input_black=-1,input_white=-1,intensity=0))
        self.assertEqual(out.tobytes(),a.tobytes());self.assertEqual(m['coefficients'],{})

    def test_explicit_srgb_endpoints_mix_in_linear_working_space(self):
        a = fixture.rgba((.02,.18,.8,.3));out,_ = self.apply(a,effect(input_signal=SRGB,output_signal=SRGB,output_black=.04,output_white=.84,intensity=.35))
        rgb = a[...,:3].astype(np.float64);encoded = np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055).astype(np.float32)
        mapped = ((encoded-np.float32(0))*np.float32(.8)+np.float32(.04)).astype(np.float64)
        linear = np.where(mapped<=.04045,mapped/12.92,((mapped+.055)/1.055)**2.4).astype(np.float32)
        np.testing.assert_allclose(out[...,:3],rgb*.65+linear.astype(np.float64)*.35,atol=9e-8,rtol=0)

    def test_legacy_shared_aliases_and_independent_channel_aliases(self):
        a = fixture.rgba((.2,.4,.6,1))
        first,_ = self.apply(a,effect(rimin=.1,rimax=.9,romin=.05,romax=.8,gomin=.2,bomax=.7))
        second,_ = self.apply(a,effect(input_black=.1,input_white=.9,output_black=.05,output_white=.8,green_output_black=.2,blue_output_white=.7))
        self.assertEqual(first.tobytes(),second.tobytes());self.bad(lambda:compile_levels(effect(rimin=.2,input_black=.1)))

    def test_live_shared_endpoint_tracks_and_independent_override(self):
        e = effect(red_output_white=.7);e['keyframes'] = [track('output_black',0,.2),track('green_output_white',.8,.9)]
        channels,intensity,alpha = state_at(compile_levels(e),50)
        self.assertEqual(channels['red']['output_black'],.1);self.assertEqual(channels['red']['output_white'],.7)
        self.assertAlmostEqual(channels['green']['output_white'],.85);self.assertFalse(alpha);self.assertEqual(intensity,1)

    def test_all_six_endpoint_time_easings(self):
        functions = {'linear':.25,'hold':0,'ease_in':.0625,'ease_out':.4375,'ease_in_out':.125,'bezier':.15625}
        for mode,p in functions.items():
            e = effect();e['keyframes'] = [track('output_black',0,.4,mode,controls=[0,1] if mode=='bezier' else None)]
            channels,_,_ = state_at(compile_levels(e),25);self.assertAlmostEqual(channels['blue']['output_black'],.4*p,places=14)

    def test_four_control_bezier_matches_independent_polynomial_root(self):
        e = effect();e['keyframes'] = [track('intensity',.2,.8,'bezier',controls=[.2,.05,.8,.95])]
        for at in (13,37,81):
            roots = np.roots([-.8,1.2,.6,-at/100]);t = next(float(z.real) for z in roots if abs(z.imag)<1e-12 and 0<=z.real<=1)
            y = 3*(1-t)**2*t*.05+3*(1-t)*t*t*.95+t**3
            self.assertAlmostEqual(state_at(compile_levels(e),at)[1],.2+.6*y,places=13)

    def test_fraction_author_ticks_beyond_binary64_integer_precision(self):
        start = 2**60;e = effect();e['keyframes'] = [track('intensity',.1,.9,start=start,stop=start+8)]
        self.assertAlmostEqual(state_at(compile_levels(e),Fraction(start*2+3,2))[1],.25,places=15)

    def test_bezier_overshoot_clamps_to_declared_parameter_range(self):
        e = effect();e['keyframes'] = [track('output_black',.1,.9,'bezier',controls=[10,10])]
        self.assertEqual(state_at(compile_levels(e),50)[0]['red']['output_black'],1)

    def test_dynamic_exposure_six_easings_match_actual_native_coefficients(self):
        a = fixture.rgba((-.1,.2,1.3,.5))
        for mode in ('linear','hold','ease_in','ease_out','ease_in_out','bezier'):
            e = {'type':'exposure','parameters':{'amount':0,'black':0},'keyframes':[
                track('exposure',-.5,1.5,mode,controls=[0,1] if mode=='bezier' else None),track('black',-.1,.1)]}
            plan = compile_animated_exposure(e);sample = exposure_at(plan,25)
            out,m = apply_animated_exposure(a,plan,25);expected = native(a,f'exposure={sample.amount:.17g}:black={sample.black:.17g}','exposure')
            np.testing.assert_array_equal(out,expected);self.assertEqual(m['author_tick'],'25')

    def test_dynamic_exposure_exact_singular_gain_1024(self):
        e = {'type':'exposure','keyframes':[track('amount',1,1),track('black',.5,.5)]}
        plan = compile_animated_exposure(e);sample = exposure_at(plan,50);self.assertTrue(sample.singular);self.assertEqual(sample.scale,1024)
        a = fixture.rgba((.2,.5,.8,1));out,_ = apply_animated_exposure(a,plan,50)
        np.testing.assert_array_equal(out,native(a,'exposure=1:black=.5','exposure'))

    def test_dynamic_exposure_large_fraction_clock_and_parameter_prefix(self):
        n = 2**60;e = {'type':'exposure','keyframes':[track('parameters.exposure',0,2,start=n,stop=n+8)]}
        self.assertEqual(exposure_at(compile_animated_exposure(e),Fraction(n*2+3,2)).amount,.375)

    def test_dynamic_exposure_accepts_legacy_top_level_parameters(self):
        e = {'type':'exposure','amount':.5,'black':.1,'keyframes':[track('amount',0,1)]}
        plan = compile_animated_exposure(e);self.assertEqual(exposure_at(plan,50).amount,.5)
        self.assertEqual(exposure_at(plan,50).black,float(np.float32(.1)))
        e['parameters'] = {'amount':.5};self.bad(lambda:compile_animated_exposure(e))

    def test_dynamic_exposure_boolean_cancellation_preserves_source(self):
        plan = compile_animated_exposure({'type':'exposure','keyframes':[track('amount',0,1)]})
        a = fixture.rgba();before = a.tobytes();calls = []
        def cancel():calls.append(1);return len(calls)>4
        self.bad(lambda:apply_animated_exposure(a,plan,50,tile_pixels=1,cancel=cancel));self.assertEqual(a.tobytes(),before)

    def test_compiled_tracks_detach_from_later_author_mutation(self):
        e = effect();e['keyframes'] = [track('intensity',.2,.8)];plan = compile_levels(e)
        e['keyframes'][0]['keyframes'][0]['value'] = 1;e['parameters']['output_white'] = .2
        self.assertAlmostEqual(state_at(plan,50)[1],.5);self.assertEqual(state_at(plan,50)[0]['red']['output_white'],1)

    def test_invalid_parameters_and_duplicate_alias_channels_reject(self):
        for p in ({'input_signal':None},{'output_signal':{'primaries':'bt709','transfer':'pq'}},{'input_black':True},
                  {'green_input_black':-1.01},{'output_white':1.01},{'preserve':'weighted-luma'},{'zero_span':'nan'},
                  {'provider':'https://example.test'},{'preserve':'sum','preserve_color':'max'}):self.bad(lambda p=p:compile_levels(effect(**p)))
        e = effect();e['keyframes'] = [track('rimin',0,.1),track('input_black',0,.2)];self.bad(lambda:compile_levels(e))

    def test_invalid_keyframes_clocks_values_controls_and_unknown_fields_reject(self):
        variants = [track('unknown',0,1),track('input_black',0,2),track('intensity',0,1,start=-1),
            track('intensity',0,1,mode='bezier',controls=[-1,0,2,1]),track('intensity',0,1,mode='cloud')]
        bad = track('intensity',0,1);bad['keyframes'][0]['script']='run';variants.append(bad)
        for t in variants:
            e = effect();e['keyframes'] = [t];self.bad(lambda:compile_levels(e))
        e = effect(keyframes=[]);e['keyframes'] = [];self.bad(lambda:compile_levels(e))

    def test_temporal_key_budget_and_forged_plan_reject(self):
        e = effect();e['keyframes'] = [{'property':'intensity','keyframes':[{'at_tick':i,'value':.5} for i in range(1025)]}]
        self.bad(lambda:compile_levels(e));plan = compile_levels(effect())
        self.bad(lambda:state_at(replace(plan,preserve='weighted'),0));self.bad(lambda:state_at(replace(plan,tracks_json='{}'),0))

    def test_nonfinite_late_source_and_invalid_alpha_are_transactional(self):
        for channel,bad in ((0,float('inf')),(1,float('nan')),(3,-.01),(3,1.01)):
            a = fixture.rgba();a[-1,-1,channel] = bad;before = a.tobytes()
            self.bad(lambda:self.apply(a,effect(input_black=-1,input_white=-1),tile_pixels=1));self.assertEqual(a.tobytes(),before)

    def test_budget_rejects_before_output_allocation_and_counts_retained_LUT(self):
        with patch('ai_ad_editor.float_levels.np.empty_like',side_effect=AssertionError('allocated')):
            self.bad(lambda:self.apply(fixture.rgba(),max_working_bytes=1))
        self.bad(lambda:self.apply(fixture.rgba(),retained_table_bytes=768*1024*1024))

    def test_cancel_during_auto_scan_preserves_input(self):
        a = fixture.rgba();before = a.tobytes();calls = []
        def cancel():calls.append(1);return len(calls)>7
        self.bad(lambda:self.apply(a,effect(input_black=-1,input_white=-1),tile_pixels=1,cancel=cancel));self.assertEqual(a.tobytes(),before)

    def test_tiles_and_readonly_input_produce_bit_identical_auto_preserve(self):
        a = np.random.default_rng(5).uniform(.1,.9,(3,17,4)).astype(np.float32);a.flags.writeable = False
        e = effect(input_black=-1,input_white=-1,preserve='nrm',alpha_output_white=.8)
        one,_ = self.apply(a,e,tile_pixels=1);many,_ = self.apply(a,e,tile_pixels=16384);self.assertEqual(one.tobytes(),many.tobytes())

    def test_signal_surface_tile_and_clock_contract_rejects(self):
        self.bad(lambda:apply_levels(fixture.rgba(),compile_levels(effect()),0,working_signal=ColorSignal(**SRGB)))
        self.bad(lambda:self.apply(fixture.rgba().astype(np.float64)))
        for v in (0,True,262145):self.bad(lambda:self.apply(fixture.rgba(),tile_pixels=v))
        self.bad(lambda:self.apply(fixture.rgba(),tick=-1));self.bad(lambda:self.apply(fixture.rgba(),cancel=1))

    def test_ordered_exposure_levels_curves_LUT_and_disabled_effects(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp);write_cube(root/'look.cube',2,transform=lambda r,g,b:(r*.7,g*.7,b*.7))
            compiler = EffectCompiler(resource_root=root,working_signal=WORKING)
            levels = effect(output_black=.1,output_white=.9)
            exposure = {'type':'exposure','keyframes':[track('amount',0,1)]}
            curves = {'type':'rgb_curves','parameters':{'input_signal':LINEAR,'output_signal':LINEAR,'all':'0/.1 1/.8'}}
            lut = {'type':'lut3d','parameters':{'path':'look.cube','input_signal':LINEAR,'output_signal':LINEAR}}
            a = fixture.rgba((.2,.4,.6,.5));plans = compiler.compile([exposure,levels,curves,lut,{'type':'cloud','enabled':False}])
            actual,m = compiler.apply(a,plans,50);expected = a
            for e in (exposure,levels,curves,lut):expected,_ = compiler.apply(expected,compiler.compile([e]),50)
            self.assertEqual(actual.tobytes(),expected.tobytes());self.assertEqual([r['type'] for r in m['ordered_effects']],['exposure','color_levels','rgb_curves','lut3d'])
            reverse,_ = compiler.apply(a,compiler.compile([levels,exposure,curves,lut]),50);self.assertFalse(np.array_equal(actual,reverse))

    def test_author_presentation_window_matches_complete_timeline_samples(self):
        p,s = fixture.image_project(fixture.rgba((.2,.4,.6,.5)),duration=200)
        e = effect();e['keyframes'] = [track('output_black',0,.3,stop=200)];p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e])
        host = FloatTimeline(p,'main',s,working_signal=WORKING);full = [host.render_frame(i)[0] for i in range(20)]
        selected_p = copy.deepcopy(p)
        selected_p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=60,
            presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':200,'offset_tick':70})
        selected = FloatTimeline(selected_p,'main',s,working_signal=WORKING)
        for i in range(6):self.assertEqual(selected.render_frame(i)[0].tobytes(),full[i+7].tobytes())

    def test_nested_reverse_evaluates_child_and_parent_author_channels(self):
        p,s = fixture.image_project(fixture.rgba((.2,.4,.6,.5)),duration=200)
        child = copy.deepcopy(p['sequences'][0]);child['id']='child'
        e = effect();e['keyframes'] = [track('output_black',0,.2,stop=200)]
        child['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e])
        parent = p['sequences'][0]['tracks'][0]['clips'][0];parent.pop('asset_id');parent.update(sequence_id='child',duration_tick=200,source_out_tick=200,reverse=True)
        parent['effects'] = [{'type':'exposure','keyframes':[track('amount',0,1,stop=200)]}];p['sequences'].append(child)
        host = FloatTimeline(p,'main',s,working_signal=WORKING);out,_ = host.render_frame(4)
        compiler = EffectCompiler(resource_root=None,working_signal=WORKING)
        expected,_ = compiler.apply(fixture.rgba((.2,.4,.6,.5)),compiler.compile([e]),np.nextafter(160.,-np.inf))
        expected,_ = compiler.apply(expected,compiler.compile(parent['effects']),40)
        np.testing.assert_allclose(out,expected,atol=2e-7,rtol=0)

    def test_public_native_validator_advertises_endpoint_channels_and_duration(self):
        self.assertIn('green_output_white',PARAMETER_NAMES)
        e = effect();e['keyframes'] = [track('green_output_white',.7,.9)]
        self.assertEqual(validate_native(e,duration_tick=100),[]);self.assertTrue(validate_native(e,duration_tick=99))
        from ai_ad_editor.validator import validate_project
        case = preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.visual(np.ones((2,16,32,4),np.float32)*.5);case.s['duration_tick'] = 18000
            e['keyframes'] = [track('green_output_white',.7,.9,stop=9000)];case.s['tracks'][0]['clips'][0]['effects'] = [e]
            result = validate_project(case.root,case.p)
            self.assertTrue(result['ok'],result)
        finally:case.doCleanups()

    def test_real_preview_formal_render_PCM_and_PNG16_use_same_levels(self):
        case = preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick'] = 18000;pixels = case.visual(np.broadcast_to(np.array([.2,.4,.6,.5],np.float32),(2,16,32,4)).copy());audio = case.audio()
            e = effect(output_black=.125,output_white=.875);e['keyframes'] = [track('intensity',.25,.75,stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects'] = [e,{'type':'exposure','keyframes':[track('amount',0,.5,stop=9000)]}]
            result = case.execute(end=2);actual = case.reference(result);source = np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/65535
            expected = source.copy()
            for i,strength in enumerate((.25,.75)):
                graded = source[i,...,:3]*np.float32(.75)+np.float32(.125)
                mixed = (source[i,...,:3].astype(np.float64)*(1-strength)+graded.astype(np.float64)*strength).astype(np.float32)
                scale = np.float32(math.exp2(i*.5));mixed = (mixed*scale).astype(np.float32)
                expected[i,...,:3] = (mixed.astype(np.float64)*source[i,...,3:4].astype(np.float64)).astype(np.float32)
            expected[...,3] = 1;np.testing.assert_allclose(actual,expected,atol=8e-8,rtol=0)
            self.assertEqual(case.pcm(result),audio[:9600].tobytes())
            np.testing.assert_allclose(case.png(case.execute(mode='frame')),np.rint(expected[0].astype(np.float64)*65535),atol=1,rtol=0)
            from ai_ad_editor.render import render_project
            from ai_ad_editor.project import project_write_lock
            with project_write_lock(case.root):formal = render_project(case.root,case.p,case.s,case.root/'renders/levels.mkv')
            manifest = json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            payload = np.moveaxis(np.rint(expected[...,[1,2,0,3]].astype(np.float64)*65535).astype('<u2'),3,1).tobytes()
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],'sha256:'+hashlib.sha256(payload).hexdigest());case.assert_clean()
        finally:case.doCleanups()

    def test_real_preview_cache_invalidates_levels_without_author_mutation(self):
        case = preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick'] = 18000;case.visual(np.ones((2,16,32,4),np.float32)*.5);case.audio()
            e = effect(output_white=.8);case.s['tracks'][0]['clips'][0]['effects'] = [e]
            before = copy.deepcopy(case.p);one = case.execute(end=2);self.assertTrue(case.execute(end=2)['cache_hit'])
            for section in ('settings','assets','sequences'):self.assertEqual(case.p[section],before[section])
            e['parameters']['green_output_white'] = .6;two = case.execute(end=2)
            self.assertNotEqual(one['cache_key'],two['cache_key']);self.assertFalse(two['cache_hit']);case.assert_clean()
        finally:case.doCleanups()
