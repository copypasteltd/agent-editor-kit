"""Real integer-native comparisons and independent continuous colour oracles."""
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
from ai_ad_editor.float_balance import (compile_balance,apply_balance,state_at,validate_balance,
    parameter_names,ALIASES,WHEEL)
from ai_ad_editor.float_color_signal import ColorSignal,convert_rgba
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
import test_float_timeline as fixture
import test_float_preview as preview_fixture
from test_float_levels import track
from test_float_lut import write_cube

LINEAR={'primaries':'bt709','transfer':'linear'}
WORKING=ColorSignal(**LINEAR)
NATIVE_CALLS=[]

def effect(kind='color_wheel',**parameters):
    return {'type':kind,'parameters':{'input_signal':dict(LINEAR),'output_signal':dict(LINEAR),**parameters}}

def native(value,options,packed=False):
    """uint16 input/output; no hidden float-to-integer conversion in oracle."""
    h,w=value.shape[:2];fmt='rgba64le' if packed else 'gbrap16le'
    payload=value.astype('<u2').tobytes() if packed else np.moveaxis(value[...,[1,2,0,3]],2,0).astype('<u2').tobytes()
    args=[ffmpeg_path(),'-nostdin','-v','error','-f','rawvideo','-pixel_format',fmt,'-video_size',f'{w}x{h}',
          '-i','pipe:0','-vf','colorbalance='+options,'-frames:v','1','-threads','1','-pix_fmt',fmt,'-f','rawvideo','pipe:1']
    result=subprocess.run(args,input=payload,capture_output=True,check=True)
    raw=np.frombuffer(result.stdout,'<u2')
    out=raw.reshape(h,w,4).copy() if packed else np.moveaxis(raw.reshape(4,h,w),0,2)[...,[2,0,1,3]].copy()
    NATIVE_CALLS.append({'options':options,'format':fmt,'input_sha256':hashlib.sha256(payload).hexdigest(),
        'output_sha256':hashlib.sha256(result.stdout).hexdigest(),'pixels':h*w,'exit_code':result.returncode})
    return out

def scalar(rgb,controls,*,clip=False,midrange=False):
    """Binary64 scalar oracle, independent of the product's Float32 vectors."""
    r,g,b=map(float,rgb);level=max(r,g,b)+min(r,g,b)
    unit=lambda x:max(0.,min(1.,x))
    weights=(unit((.333-level)*4+.5)*.7,
             unit((level-.333)*4+.5)*unit((1-level-.333)*4+.5)*.7,
             unit((level+.333-1)*4+.5)*.7)
    out=[v+sum(float(controls.get(t+'_'+c,0))*weights[j] for j,t in enumerate(('shadows','midtones','highlights')))
         for v,c in zip((r,g,b),('red','green','blue'))]
    if clip:out=[unit(x) for x in out]
    if midrange:
        shift=(max(r,g,b)+min(r,g,b)-max(out)-min(out))*.5
        out=[x+shift for x in out]
        if clip:out=[unit(x) for x in out]
    return out

class FloatBalanceTests(unittest.TestCase):
    def apply(self,value,e=None,tick=0,**kwargs):
        return apply_balance(value,compile_balance(e or effect()),tick,working_signal=WORKING,**kwargs)

    def bad(self,fn,code=None):
        with self.assertRaises(AppError) as caught:fn()
        if code:self.assertEqual(caught.exception.code,code)

    def test_identity_retains_negative_superwhite_signed_zero_and_alpha_bits(self):
        a=np.random.default_rng(104).uniform(-.5,2,(7,19,4)).astype(np.float32);a[...,3]=.5
        a[0,0,:]=[-0.,0.,1.,-0.];a[0,1,3]=np.nextafter(np.float32(0),np.float32(1))
        out,m=self.apply(a);self.assertEqual(out.tobytes(),a.tobytes());self.assertFalse(m['integer_intermediate'])

    def test_signals_are_required_and_cannot_be_inferred_from_tags(self):
        for p in ({},{'input_signal':LINEAR},{'input_signal':LINEAR,'output_signal':{'primaries':'bt709','transfer':'bt709'}}):
            self.bad(lambda:compile_balance({'type':'color_wheel','parameters':p}))

    def test_all_type_aliases_use_the_correct_canonical_operator(self):
        for name in ALIASES:
            plan=compile_balance(effect(name));kind='color_temperature' if name in ('temperature','warmth','color_temperature') else 'color_balance' if name in ('colorbalance','color_balance') else 'color_wheel'
            self.assertEqual(plan.effect_type,kind)

    def test_three_way_channels_match_real_planar_native_16bit(self):
        q=np.random.default_rng(28).integers(0,65536,(17,31,4),dtype=np.uint16)
        values=dict(zip(WHEEL,(.13,-.08,.09,-.07,.11,-.12,.05,-.1,.14)))
        out,_=self.apply(q.astype(np.float32)/np.float32(65535),effect(**values,output_gamut='clip'))
        expected=native(q,'rs=.13:gs=-.08:bs=.09:rm=-.07:gm=.11:bm=-.12:rh=.05:gh=-.1:bh=.14')
        actual=np.rint(out.astype(np.float64)*65535).astype(np.uint16)
        error=int(np.abs(actual.astype(np.int32)-expected.astype(np.int32)).max());NATIVE_CALLS[-1]['maximum_16bit_code_error']=error
        self.assertLessEqual(error,2);np.testing.assert_array_equal(actual[...,3],q[...,3])

    def test_packed_native_RGBA64_matches_independent_path(self):
        q=np.random.default_rng(29).integers(0,65536,(9,27,4),dtype=np.uint16)
        out,_=self.apply(q.astype(np.float32)/np.float32(65535),effect(rs=.21,gm=-.17,bh=.19,output_gamut='clip'))
        expected=native(q,'rs=.21:gm=-.17:bh=.19',packed=True)
        error=int(np.abs(np.rint(out.astype(np.float64)*65535).astype(np.int32)-expected.astype(np.int32)).max())
        NATIVE_CALLS[-1]['maximum_16bit_code_error']=error;self.assertLessEqual(error,2)

    def test_shadow_balance_is_not_a_uniform_RGB_offset(self):
        a=np.array([[[.05,.1,.15,.3],[.45,.5,.55,.8],[.85,.9,.95,1]]],np.float32)
        out,_=self.apply(a,effect('color_balance',red=.2,green=-.1,blue=.07))
        for x in range(3):np.testing.assert_allclose(out[0,x,:3],scalar(a[0,x,:3],{'shadows_red':.2,'shadows_green':-.1,'shadows_blue':.07}),atol=2e-7,rtol=0)
        np.testing.assert_array_equal(out[0,2],a[0,2])

    def test_Kelvin_mapping_matches_native_and_saturates_above_13000(self):
        q=np.random.default_rng(30).integers(0,65536,(7,19,4),dtype=np.uint16);a=q.astype(np.float32)/np.float32(65535)
        for kelvin in (1000,3500,6500,13000,40000):
            out,m=self.apply(a,effect('temperature',kelvin=kelvin,output_gamut='clip'))
            delta=max(-1.,min(1.,(kelvin-6500)/6500))
            expected=native(q,f'rs={-delta*.30:.17g}:gs={-delta*.05:.17g}:bs={delta*.30:.17g}')
            err=int(np.abs(np.rint(out.astype(np.float64)*65535).astype(np.int32)-expected.astype(np.int32)).max())
            NATIVE_CALLS[-1]['maximum_16bit_code_error']=err;self.assertLessEqual(err,2)
            self.assertIn('not-physical-white-balance',m['kelvin_model'])
        np.testing.assert_array_equal(self.apply(a,effect('temperature',kelvin=13000))[0],self.apply(a,effect('temperature',kelvin=40000))[0])

    def test_native_HSL_preservation_matches_real_native_on_bounded_RGB(self):
        q=np.random.default_rng(31).integers(4000,60000,(17,31,4),dtype=np.uint16);a=q.astype(np.float32)/np.float32(65535)
        for options,values in [('rs=.17:gm=-.12:bh=.14',{'rs':.17,'gm':-.12,'bh':.14}),('rs=1:bs=-1',{'rs':1,'bs':-1})]:
            out,_=self.apply(a,effect(**values,preserve_luma=True,output_gamut='clip'))
            expected=native(q,options+':pl=1');error=int(np.abs(np.rint(out.astype(np.float64)*65535).astype(np.int32)-expected.astype(np.int32)).max())
            NATIVE_CALLS[-1]['maximum_16bit_code_error']=error;self.assertLessEqual(error,2)

    def test_native_float_format_is_rejected_when_auto_conversion_is_disabled(self):
        a=fixture.rgba((.1,.2,.3,1));payload=np.moveaxis(a[...,[1,2,0,3]],2,0).astype('<f4').tobytes()
        command=[ffmpeg_path(),'-nostdin','-v','error','-noauto_conversion_filters','-f','rawvideo','-pixel_format','gbrapf32le',
                 '-video_size','8x4','-i','pipe:0','-vf','colorbalance=rs=.2','-frames:v','1','-f','null','-']
        result=subprocess.run(command,input=payload,capture_output=True)
        self.assertNotEqual(result.returncode,0);self.assertIn(b'common format',result.stderr)
        NATIVE_CALLS.append({'format':'gbrapf32le','auto_conversion':False,'exit_code':result.returncode,'expected_rejection':True})

    def test_weights_use_max_plus_min_instead_of_average_or_Rec709_luma(self):
        a=fixture.rgba((.04,.23,.61,1));controls={'shadows_red':.1,'midtones_green':.1,'highlights_blue':.1}
        out,_=self.apply(a,effect(**controls))
        np.testing.assert_allclose(out[0,0,:3],scalar(a[0,0,:3],controls),atol=8e-8,rtol=0)
        self.assertGreater(float(out[0,0,2]),float(a[0,0,2]))

    def test_131073_distinct_values_remain_continuous_without_integer_LUT(self):
        a=np.ones((1,131073,4),np.float32);a[0,:,:3]=np.linspace(.7,.9,131073,dtype=np.float32)[:,None]
        # Stay within the documented edge bound by using a two-dimensional raster.
        a=np.concatenate((a,np.ones((1,511,4),np.float32)),axis=1).reshape(257,512,4)
        out,_=self.apply(a,effect(highlights_red=.07))
        self.assertGreater(len(np.unique(out[...,0])),65536)

    def test_unclipped_headroom_and_explicit_clip_are_distinct(self):
        a=np.array([[[-.2,.1,.3,.4],[.8,1.2,1.7,.6]]],np.float32);e=effect(shadows_red=-.2,highlights_blue=.3)
        out,_=self.apply(a,e);clipped,_=self.apply(a,effect(shadows_red=-.2,highlights_blue=.3,output_gamut='clip'))
        for x in range(2):np.testing.assert_allclose(out[0,x,:3],scalar(a[0,x,:3],e['parameters']),atol=2e-7,rtol=0)
        self.assertLess(float(out[...,0].min()),0);self.assertGreater(float(out[...,2].max()),1)
        self.assertGreaterEqual(float(clipped[...,:3].min()),0);self.assertLessEqual(float(clipped[...,:3].max()),1)

    def test_midrange_preserves_lightness_with_negative_and_superwhite_RGB(self):
        a=np.array([[[-.3,.1,.8,.3],[.7,1.2,1.8,.7]]],np.float32);e=effect(shadows_red=.2,midtones_green=-.3,highlights_blue=.4,preserve_lightness='midrange')
        out,_=self.apply(a,e)
        for x in range(2):np.testing.assert_allclose(out[0,x,:3],scalar(a[0,x,:3],e['parameters'],midrange=True),atol=3e-7,rtol=0)
        np.testing.assert_allclose(out[...,:3].max(axis=2)+out[...,:3].min(axis=2),a[...,:3].max(axis=2)+a[...,:3].min(axis=2),atol=3e-7,rtol=0)

    def test_native_HSL_rejects_unbounded_input_without_mutation(self):
        for rgb in ((-.01,.2,.3),(.2,.3,1.01)):
            a=fixture.rgba((*rgb,.4));old=a.tobytes()
            self.bad(lambda:self.apply(a,effect(rs=.1,pl=True)),'FLOAT_BALANCE_PRESERVE_DOMAIN');self.assertEqual(a.tobytes(),old)

    def test_HSL_black_and_white_are_explicitly_finite_and_exact(self):
        a=np.array([[[0,0,0,.3],[1,1,1,.7]]],np.float32)
        out,m=self.apply(a,effect(rs=.4,gs=.2,bs=.1,rh=-.4,gh=-.2,bh=-.1,pl=True))
        np.testing.assert_array_equal(out,a);self.assertTrue(m['native_HSL_black_white_defined_explicitly'])
        q=np.rint(a.astype(np.float64)*65535).astype(np.uint16);reference=native(q,'rs=.4:gs=.2:bs=.1:rh=-.4:gh=-.2:bh=-.1:pl=1')
        NATIVE_CALLS[-1]['native_black_white_RGB']=reference[0,:,:3].tolist();NATIVE_CALLS[-1]['product_black_white_RGB']=q[0,:,:3].tolist()

    def test_all_six_easings_use_the_original_author_clock(self):
        expected={'linear':.25,'hold':0.,'ease_in':.0625,'ease_out':.4375,'ease_in_out':.125,'bezier':.15625}
        for mode,t in expected.items():
            e=effect();e['keyframes']=[track('midtones_green',-.2,.6,mode,controls=[0,1] if mode=='bezier' else None)]
            values,_=state_at(compile_balance(e),25);self.assertAlmostEqual(values['midtones_green'],-.2+.8*t,places=12)

    def test_large_rational_ticks_keep_fractional_positions_above_float_precision(self):
        n=2**60;e=effect();e['keyframes']=[track('parameters.rm',-.2,.6,start=n,stop=n+8)]
        values,_=state_at(compile_balance(e),Fraction(2*n+3,2));self.assertAlmostEqual(values['midtones_red'],-.05,places=13)

    def test_four_control_Bezier_uses_time_root_not_value_only_interpolation(self):
        e=effect();e['keyframes']=[track('shadows_blue',-.4,.4,'bezier',controls=[.1,.8,.7,.2])]
        lo,hi=0.,1.
        for _ in range(80):
            u=(lo+hi)*.5;x=3*(1-u)**2*u*.1+3*(1-u)*u*u*.7+u**3
            if x<.25:lo=u
            else:hi=u
        u=(lo+hi)*.5;y=3*(1-u)**2*u*.8+3*(1-u)*u*u*.2+u**3
        self.assertAlmostEqual(state_at(compile_balance(e),25)[0]['shadows_blue'],-.4+.8*y,places=12)

    def test_hold_left_limit_and_endpoints_are_half_open(self):
        e=effect();e['keyframes']=[track('rs',-.2,.4,'hold')];p=compile_balance(e)
        self.assertEqual(state_at(p,np.nextafter(100.,-np.inf))[0]['shadows_red'],-.2)
        self.assertEqual(state_at(p,100)[0]['shadows_red'],.4);self.assertEqual(state_at(p,1000)[0]['shadows_red'],.4)

    def test_overshooting_authored_values_are_clamped_to_parameter_bounds(self):
        e=effect();e['keyframes']=[track('intensity',0,1,'bezier',controls=[10,10])]
        self.assertEqual(state_at(compile_balance(e),50)[0]['intensity'],1.)

    def test_later_author_mutation_cannot_change_compiled_plan(self):
        e=effect(rs=.2);e['keyframes']=[track('gm',-.1,.1)];plan=compile_balance(e)
        e['parameters']['rs']=1;e['parameters']['input_signal']['transfer']='srgb';e['keyframes'][0]['keyframes'][0]['value']=.8
        values,_=state_at(plan,0);self.assertEqual(values['shadows_red'],.2);self.assertEqual(values['midtones_green'],-.1);self.assertEqual(plan.input_signal,WORKING)

    def test_invalid_parameters_and_unknown_fields_are_rejected(self):
        for values in ({'rs':True},{'rs':'.2'},{'rs':math.nan},{'rs':1.1},{'intensity':-.1},{'unknown':1},{'kelvin':5000}):
            self.bad(lambda:compile_balance(effect(**values)))
        self.bad(lambda:compile_balance(effect('temperature',kelvin=999)))
        self.bad(lambda:compile_balance({**effect(),'shadows_red':.2}))

    def test_duplicate_channel_and_lightness_aliases_must_agree(self):
        self.bad(lambda:compile_balance(effect(rs=.1,shadows_red=.2)))
        self.bad(lambda:compile_balance(effect(pl=True,preserve_lightness='midrange')))
        plan=compile_balance(effect(rs=.1,shadows_red=.1,pl=True,preserve_luma='lum'));self.assertEqual(plan.preserve_lightness,'native_hsl')

    def test_invalid_tracks_counts_ticks_controls_and_duplicate_aliases_reject(self):
        examples=[[track('rs',0,.2),track('shadows_red',0,.2)], [track('unknown',0,1)], [track('rs',0,.2,start=-1)], [track('rs',0,.2,start=1,stop=1)], [track('rs',0,.2,'bezier',controls=[-1,0,2,1])]]
        for tracks in examples:
            e=effect();e['keyframes']=tracks;self.bad(lambda:compile_balance(e))
        e=effect();e['keyframes']=[{'property':'rs','keyframes':[{'at_tick':i,'value':0} for i in range(1025)]}];self.bad(lambda:compile_balance(e))

    def test_keyframes_cannot_be_authored_in_two_locations(self):
        e=effect(keyframes=[track('rs',0,1)]);e['keyframes']=[track('gm',0,1)];self.bad(lambda:compile_balance(e))

    def test_forged_plans_and_invalid_sample_clocks_are_rejected(self):
        p=compile_balance(effect());a=fixture.rgba()
        for bad in (replace(p,effect_type='three_way_wheel'),replace(p,values=list(p.values)),replace(p,values=()),replace(p,output_gamut='auto'),replace(p,preserve_lightness='guess'),replace(p,input_signal={}),replace(p,tracks_json='[] ')):
            self.bad(lambda:apply_balance(a,bad,0,working_signal=WORKING))
        for t in (-1,True,math.inf,'25'):self.bad(lambda:self.apply(a,tick=t))

    def test_surface_dtype_shape_and_late_alpha_errors_never_mutate_input(self):
        for a in (np.ones((2,3,4),np.float64),np.ones((2,3,3),np.float32),np.ones((2,3,4),np.float32)[:,::-1]):self.bad(lambda:self.apply(a))
        for value in (math.nan,-.1,1.1):
            a=fixture.rgba((.2,.3,.4,.5),(5,7));a[-1,-1,3]=value;old=a.tobytes()
            self.bad(lambda:self.apply(a,effect(rs=.1),tile_pixels=1));self.assertEqual(a.tobytes(),old)

    def test_tile_size_invariance_readonly_input_and_alpha_are_exact(self):
        a=np.random.default_rng(32).uniform(-.2,1.4,(19,37,4)).astype(np.float32);a[...,3]=.5;a[0,0,3]=-0.;old=a.tobytes();a.setflags(write=False)
        e=effect(rs=.2,gm=-.2,bh=.1,preserve_lightness='midrange');outputs=[self.apply(a,e,tile_pixels=t)[0] for t in (1,7,16384,262144)]
        for out in outputs:self.assertEqual(out.tobytes(),outputs[0].tobytes());self.assertEqual(out[...,3].tobytes(),a[...,3].tobytes())
        self.assertEqual(a.tobytes(),old)

    def test_workspace_and_retained_LUT_admission_precede_output_allocation(self):
        a=fixture.rgba();e=effect(rs=.1)
        with patch('ai_ad_editor.float_balance.np.empty_like',side_effect=AssertionError('allocated')):
            self.bad(lambda:self.apply(a,e,max_working_bytes=1),'FLOAT_BALANCE_BUDGET')
            self.bad(lambda:self.apply(a,e,retained_table_bytes=768*1024*1024),'FLOAT_BALANCE_BUDGET')
        for n in (0,True,262145):self.bad(lambda:self.apply(a,tile_pixels=n))

    def test_boolean_cancellation_inside_colour_conversion_is_propagated(self):
        a=fixture.rgba((.2,.3,.4,.5),(20,30));old=a.tobytes();polls=[]
        def cancel():polls.append(1);return len(polls)>4
        self.bad(lambda:self.apply(a,effect(rs=.2),tile_pixels=100,cancel=cancel),'RENDER_CANCELLED');self.assertEqual(a.tobytes(),old)

    def test_callback_exception_preserves_caller_owned_pixels(self):
        a=fixture.rgba();old=a.tobytes()
        def cancel():raise RuntimeError('caller stop')
        with self.assertRaisesRegex(RuntimeError,'caller stop'):self.apply(a,effect(rs=.1),cancel=cancel)
        self.assertEqual(a.tobytes(),old)

    def test_explicit_transfer_conversion_and_linear_intensity_mix(self):
        a=fixture.rgba((.07,.17,.27,.4));srgb={'primaries':'bt709','transfer':'srgb'};e=effect(rs=.1,gm=-.07,intensity=.35,input_signal=srgb,output_signal=srgb)
        out,_=self.apply(a,e)
        encode=lambda v:12.92*v if v<=.0031308 else 1.055*v**(1/2.4)-.055
        decode=lambda v:v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
        encoded=[encode(float(v)) for v in a[0,0,:3]];mapped=scalar(encoded,{'shadows_red':.1,'midtones_green':-.07})
        expected=[float(v)*.65+decode(float(g))*.35 for v,g in zip(a[0,0,:3],mapped)]
        np.testing.assert_allclose(out[0,0,:3],expected,atol=8e-8,rtol=0);self.assertEqual(out[...,3].tobytes(),a[...,3].tobytes())

    def test_zero_intensity_keeps_bytes_even_for_HSL_headroom_input(self):
        a=fixture.rgba((-.1,.3,1.2,.7));out,_=self.apply(a,effect(rs=.5,pl=True,output_gamut='clip',intensity=0))
        self.assertEqual(out.tobytes(),a.tobytes())

    def test_float_overflow_in_transfer_is_explicit_and_preserves_source(self):
        a=fixture.rgba((3e38,3e38,3e38,.5));old=a.tobytes()
        self.bad(lambda:self.apply(a,effect(rs=.1,output_signal={'primaries':'bt709','transfer':'gamma24'})));self.assertEqual(a.tobytes(),old)

    def test_ordered_exposure_levels_curves_LUT_balance_and_alpha_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);write_cube(root/'look.cube',2,transform=lambda r,g,b:(r*.7,g*.8,b*.9))
            compiler=EffectCompiler(resource_root=root,working_signal=WORKING);a=fixture.rgba((.2,.4,.6,.5))
            rows=[{'type':'exposure','keyframes':[track('amount',0,.5)]},
                  {'type':'color_levels','parameters':{'input_signal':LINEAR,'output_signal':LINEAR,'alpha_output_white':.8}},
                  {'type':'rgb_curves','parameters':{'input_signal':LINEAR,'output_signal':LINEAR,'all':'0/.1 1/.9'}},
                  {'type':'lut3d','parameters':{'path':'look.cube','input_signal':LINEAR,'output_signal':LINEAR}},effect(rs=.2,gm=-.1)]
            out,m=compiler.apply(a,compiler.compile(rows),50);expected=a
            for row in rows:expected,_=compiler.apply(expected,compiler.compile([row]),50)
            self.assertEqual(out.tobytes(),expected.tobytes());self.assertEqual(m['alpha'],'explicit-per-effect-alpha-mapping')
            reverse,_=compiler.apply(a,compiler.compile(list(reversed(rows))),50);self.assertFalse(np.array_equal(out,reverse))

    def test_author_presentation_window_retains_original_effect_positions(self):
        p,s=fixture.image_project(fixture.rgba((.1,.2,.3,.5)),duration=200);e=effect();e['keyframes']=[track('rs',-.2,.3,stop=200)]
        p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e]);host=FloatTimeline(p,'main',s,working_signal=WORKING)
        full=[host.render_frame(i)[0] for i in range(20)];selected=copy.deepcopy(p)
        selected['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=60,presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':200,'offset_tick':70})
        host=FloatTimeline(selected,'main',s,working_signal=WORKING)
        for i in range(6):self.assertEqual(host.render_frame(i)[0].tobytes(),full[i+7].tobytes())

    def test_nested_reverse_child_hold_and_parent_animation_use_distinct_clocks(self):
        p,s=fixture.image_project(fixture.rgba((.1,.2,.3,.5)),duration=200);child=copy.deepcopy(p['sequences'][0]);child['id']='child'
        e=effect();e['keyframes']=[track('rs',-.2,.3,'hold',stop=160)]
        child['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e]);parent=p['sequences'][0]['tracks'][0]['clips'][0]
        parent.pop('asset_id');parent.update(sequence_id='child',duration_tick=200,source_out_tick=200,reverse=True,effects=[effect('temperature',kelvin=3500)])
        p['sequences'].append(child);out,_=FloatTimeline(p,'main',s,working_signal=WORKING).render_frame(4)
        expected,_=self.apply(fixture.rgba((.1,.2,.3,.5)),e,tick=np.nextafter(160.,-np.inf));expected,_=self.apply(expected,parent['effects'][0],tick=40)
        np.testing.assert_allclose(out,expected,atol=2e-7,rtol=0)

    def test_native_project_validator_accepts_wheel_aliases_and_duration(self):
        from ai_ad_editor.validator import validate_project
        self.assertIn('rm',parameter_names('color_wheel'));e=effect();e['keyframes']=[track('effect.rm',-.2,.2,stop=9000)]
        self.assertEqual(validate_balance(e,duration_tick=9000),[]);self.assertTrue(validate_balance(e,duration_tick=8999))
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.visual(np.ones((2,16,32,4),np.float32)*.5);case.s['duration_tick']=18000;case.s['tracks'][0]['clips'][0]['effects']=[e]
            result=validate_project(case.root,case.p);self.assertTrue(result['ok'],result)
        finally:case.doCleanups()

    def test_legacy_validator_keeps_existing_shadow_parameter_contract(self):
        from ai_ad_editor.validator import validate_project
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.visual(np.ones((2,16,32,4),np.float32)*.5);case.s['duration_tick']=18000
            case.s['tracks'][0]['clips'][0]['effects']=[{'type':'color_balance','parameters':{'red':.1}}]
            original=case.p['settings'].pop('pixel_pipeline');self.assertTrue(validate_project(case.root,case.p)['ok'])
            case.p['settings']['pixel_pipeline']=original;self.assertFalse(validate_project(case.root,case.p)['ok'])
        finally:case.doCleanups()

    def test_real_preview_formal_PCM_and_PNG16_share_the_same_balance(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000;pixels=case.visual(np.broadcast_to(np.array([.08,.16,.24,.5],np.float32),(2,16,32,4)).copy());audio=case.audio()
            e=effect(shadows_red=.2,midtones_green=-.1,highlights_blue=.1);e['keyframes']=[track('intensity',.25,.75,stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects']=[e];result=case.execute(end=2);actual=case.reference(result)
            source=np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/np.float32(65535);expected=source.copy()
            for i,strength in enumerate((.25,.75)):
                graded=np.array(scalar(source[i,0,0,:3],e['parameters']),np.float64)
                expected[i,...,:3]=((source[i,...,:3].astype(np.float64)*(1-strength)+graded*strength)*source[i,...,3:4].astype(np.float64)).astype(np.float32)
            expected[...,3]=1;np.testing.assert_allclose(actual,expected,atol=2e-7,rtol=0);self.assertEqual(case.pcm(result),audio[:9600].tobytes())
            np.testing.assert_allclose(case.png(case.execute(mode='frame')),np.rint(actual[0].astype(np.float64)*65535),atol=1,rtol=0)
            from ai_ad_editor.render import render_project
            from ai_ad_editor.project import project_write_lock
            with project_write_lock(case.root):formal=render_project(case.root,case.p,case.s,case.root/'renders/balance.mkv')
            manifest=json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            payload=np.moveaxis(np.rint(actual[...,[1,2,0,3]].astype(np.float64)*65535).astype('<u2'),3,1).tobytes()
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],'sha256:'+hashlib.sha256(payload).hexdigest());case.assert_clean()
        finally:case.doCleanups()

    def test_real_cache_hit_and_changed_colour_channel_invalidation(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000;case.visual(np.ones((2,16,32,4),np.float32)*.5);case.audio();e=effect(rh=.2)
            case.s['tracks'][0]['clips'][0]['effects']=[e];before=copy.deepcopy(case.p)
            one=case.execute(end=2);self.assertTrue(case.execute(end=2)['cache_hit']);e['parameters']['rh']=.3;two=case.execute(end=2)
            self.assertNotEqual(one['cache_key'],two['cache_key']);self.assertFalse(two['cache_hit']);before['sequences'][0]['tracks'][0]['clips'][0]['effects'][0]['parameters']['rh']=.3
            for key in ('settings','assets','sequences'):self.assertEqual(case.p[key],before[key])
            case.assert_clean()
        finally:case.doCleanups()

    def test_capabilities_declare_limits_and_disabled_effects_start_no_operator(self):
        from ai_ad_editor.capabilities import build_capability_manifest
        row=build_capability_manifest()['capabilities']['timeline_native_float_balance'];self.assertIn('native_HSL_requires_operator_input_RGB_zero_one',row['limits'])
        compiler=EffectCompiler(resource_root=None,working_signal=WORKING)
        self.assertEqual(compiler.compile([{'type':'color_wheel','enabled':False,'parameters':{'unknown':'bad'}}]),())
