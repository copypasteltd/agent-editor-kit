"""Actual native YCbCr filters, independent matrix oracle and public paths."""
import copy
from dataclasses import replace
from fractions import Fraction
import hashlib
import math
from pathlib import Path
import subprocess
import unittest

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_tone import compile_tone,apply_tone,state_at,validate_tone,ALIASES
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
from test_float_levels import track
import test_float_timeline as fixture
import test_float_preview as preview_fixture

LINEAR={'primaries':'bt709','transfer':'linear'}
WORKING=ColorSignal(**LINEAR)
NATIVE_CALLS=[]


def effect(kind='color',**parameters):
    return {'type':kind,'parameters':{'input_signal':dict(LINEAR),'output_signal':dict(LINEAR),
        'matrix':'bt709','range':'full',**parameters}}


def transform(matrix='bt709',range_value='full',bits=8):
    kr,kb={'bt709':(.2126,.0722),'smpte170m':(.299,.114),'bt470bg':(.299,.114),'bt2020nc':(.2627,.0593)}[matrix]
    luma=np.array([kr,1-kr-kb,kb],np.float64)
    a=np.array([luma,(np.array([0,0,1])-luma)/(2-2*kb),(np.array([1,0,0])-luma)/(2-2*kr)])
    m=(1<<bits)-1;s=1<<(bits-8)
    scales=np.array([219*s,224*s,224*s] if range_value=='limited' else [m,m,m])
    offsets=np.array([16*s if range_value=='limited' else 0,128*s,128*s])
    return a,scales,offsets


def from_codes(codes,matrix='bt709',range_value='full',bits=8):
    a,scales,offsets=transform(matrix,range_value,bits)
    return ((codes.astype(np.float64)-offsets)/scales)@np.linalg.inv(a).T


def to_codes(rgb,matrix='bt709',range_value='full',bits=8):
    a,scales,offsets=transform(matrix,range_value,bits)
    return rgb.astype(np.float64)@a.T*scales+offsets


def scalar(rgb,p,kind='color'):
    """Independent matrix solve plus scalar, unclipped fractional code math."""
    matrix=p.get('matrix','bt709');ranges=p.get('range','full');bits=p.get('reference_bits',8)
    q=to_codes(np.array([rgb],np.float64),matrix,ranges,bits)[0].tolist();m=(1<<bits)-1;center=1<<(bits-1)
    if kind in ('hue','hsl','grayscale'):
        angle=p.get('hue',p.get('degrees',0))*math.pi/180;s=0 if kind=='grayscale' else p.get('saturation',1)
        if angle or s!=1:
            u,v=q[1]-center,q[2]-center
            q[1]=min(m,max(0,math.cos(angle)*s*u-math.sin(angle)*s*v+center))
            q[2]=min(m,max(0,math.sin(angle)*s*u+math.cos(angle)*s*v+center))
        b=p.get('lightness',0)
        if b:q[0]=min(m,max(0,q[0]+b*(25.5 if bits==8 else 102.4)))
    else:
        b=p.get('brightness',0);c=p.get('contrast',1);s=min(3,p.get('saturation',1));g=p.get('gamma',1)
        for i,contrast,brightness,gamma in ((0,c,b,g),(1,s,0,1),(2,s,0,1)):
            if contrast==1 and brightness==0 and gamma==1:continue
            q[i]=min(1,max(0,contrast*(q[i]/m-.5)+.5+brightness))**(1/gamma)*m
    out=from_codes(np.array([q]),matrix,ranges,bits)[0]
    return np.clip(out,0,1) if p.get('output_gamut')=='clip' else out


def native(codes,kernel,bits=8,cpu_reference=False):
    h,w=codes.shape[:2];fmt='yuva444p' if bits==8 else 'yuva444p10le';dtype=np.uint8 if bits==8 else '<u2'
    payload=np.moveaxis(codes.astype(dtype),2,0).tobytes()
    args=[ffmpeg_path(),'-nostdin','-v','error']
    if cpu_reference:args+=['-cpuflags','0']
    args+=['-filter_threads','1','-f','rawvideo','-pixel_format',fmt,'-video_size',f'{w}x{h}',
        '-i','pipe:0','-vf',kernel,'-frames:v','1','-threads','1','-pix_fmt',fmt,'-f','rawvideo','pipe:1']
    r=subprocess.run(args,input=payload,capture_output=True,check=True)
    NATIVE_CALLS.append({'kernel':kernel,'bits':bits,'cpu_reference':cpu_reference,'pixels':h*w,
        'exit_code':r.returncode,'input_sha256':hashlib.sha256(payload).hexdigest(),
        'output_sha256':hashlib.sha256(r.stdout).hexdigest()})
    return np.moveaxis(np.frombuffer(r.stdout,dtype).reshape(4,h,w),0,2).copy()


class FloatToneTests(unittest.TestCase):
    def apply(self,value,e=None,tick=0,**kwargs):
        return apply_tone(value,compile_tone(e or effect()),tick,working_signal=WORKING,**kwargs)

    def bad(self,fn,code=None):
        with self.assertRaises(AppError) as caught:fn()
        if code:self.assertEqual(caught.exception.code,code)

    def compare_native(self,e,kernel,bits=8,cpu_reference=False):
        rng=np.random.default_rng(106+bits);m=(1<<bits)-1
        codes=rng.integers(0,m+1,(19,43,4),dtype=np.uint16)
        rgb=from_codes(codes[...,:3],e['parameters']['matrix'],e['parameters']['range'],bits)
        a=np.concatenate((rgb,codes[...,3:4]/m),axis=2).astype(np.float32)
        actual,_=self.apply(a,e);q=to_codes(actual[...,:3],e['parameters']['matrix'],e['parameters']['range'],bits)
        expected=native(codes,kernel,bits,cpu_reference)
        maximum=float(np.max(np.abs(q-expected[...,:3])))
        NATIVE_CALLS[-1]['maximum_fractional_code_error']=maximum
        NATIVE_CALLS[-1]['predeclared_fractional_code_limit']=1.01
        self.assertLessEqual(maximum,1.01)
        self.assertEqual(actual[...,3].tobytes(),a[...,3].tobytes())
        self.assertEqual(expected[...,3].tobytes(),codes[...,3].astype(expected.dtype).tobytes())

    def test_every_identity_alias_preserves_signed_zero_headroom_and_alpha(self):
        a=fixture.rgba((-.3,.4,1.4,-0.));a[0,0,0]=-0.;a[0,1,3]=np.nextafter(np.float32(0),np.float32(1))
        for name in ALIASES:
            if ALIASES[name]=='grayscale':continue
            out,m=self.apply(a,effect(name));self.assertEqual(out.tobytes(),a.tobytes());self.assertFalse(m['integer_intermediate'])

    def test_brightness_native_scalar_coefficients_for_both_CPU_paths(self):
        for b in (-.19,.017,.23):
            for cpu in (False,True):self.compare_native(effect('brightness',amount=b,arithmetic='native_coefficients'),f'eq=brightness={b}',cpu_reference=cpu)

    def test_contrast_native_scalar_coefficients(self):
        for c in (0.,.73,1.31,4.):self.compare_native(effect('contrast',amount=c,arithmetic='native_coefficients'),f'eq=contrast={c}')

    def test_saturation_native_scalar_coefficients_and_native_three_limit(self):
        for s in (0.,.6,2.4,4.):self.compare_native(effect('saturation',amount=s,arithmetic='native_coefficients'),f'eq=saturation={s}')

    def test_combined_color_native_coefficients_on_limited_601(self):
        self.compare_native(effect('color',brightness=.037,contrast=1.17,saturation=.61,matrix='smpte170m',range='limited',arithmetic='native_coefficients'),
            'eq=brightness=.037:contrast=1.17:saturation=.61')

    def test_gamma_matches_native_LUT_to_one_fractional_code(self):
        for g in (.5,1.7,3.3):self.compare_native(effect('gamma',gamma=g,arithmetic='native_coefficients'),f'eq=gamma={g}')

    def test_hue_native_quantized_trigonometry_eight_bit(self):
        for degrees in (-137.,37.,180.):self.compare_native(effect('hue',degrees=degrees,arithmetic='native_coefficients'),f'hue=h={degrees}')

    def test_global_HSL_native_ten_bit_code_axes(self):
        self.compare_native(effect('hsl',hue=57.,saturation=.6,lightness=.3,reference_bits=10,range='limited',arithmetic='native_coefficients'),
            'hue=h=57:s=.6:b=.3',bits=10)

    def test_grayscale_native_neutral_chroma_at_eight_and_ten_bits(self):
        for bits in (8,10):self.compare_native(effect('grayscale',reference_bits=bits,arithmetic='native_coefficients'),'hue=s=0',bits=bits)

    def test_continuous_equations_against_independent_matrix_scalar(self):
        a=np.random.default_rng(4).uniform(-.2,1.3,(5,7,4)).astype(np.float32);a[...,3]=.37
        for kind,p in [('color',{'brightness':.06,'contrast':.82,'saturation':1.4}),('gamma',{'gamma':1.8}),
                       ('hsl',{'hue':-51.,'saturation':.72,'lightness':.23}),('grayscale',{})]:
            e=effect(kind,**p);out,_=self.apply(a,e)
            expected=np.array([scalar(rgb,e['parameters'],kind) for rgb in a[...,:3].reshape(-1,3)]).reshape(a.shape[:2]+(3,))
            np.testing.assert_allclose(out[...,:3],expected,atol=1.4e-7,rtol=0)

    def test_matrix_and_range_change_the_declared_operator(self):
        a=fixture.rgba((.21,.47,.83,.6));results=[]
        for matrix in ('bt709','smpte170m','bt470bg','bt2020nc'):
            for ranges in ('limited','full'):
                e=effect('hsl',hue=43,saturation=.7,lightness=.12,matrix=matrix,range=ranges)
                out,_=self.apply(a,e);np.testing.assert_allclose(out[0,0,:3],scalar(a[0,0,:3],e['parameters'],'hsl'),atol=1e-7,rtol=0);results.append(out)
        self.assertFalse(np.array_equal(results[0],results[1]));self.assertFalse(np.array_equal(results[0],results[-1]))

    def test_global_HSL_lightness_uses_tenth_scale_not_full_brightness(self):
        a=fixture.rgba((.2,.2,.2,.4))
        h,_=self.apply(a,effect('hsl',lightness=.5));b,_=self.apply(a,effect('brightness',brightness=.5))
        np.testing.assert_allclose(h[0,0,:3],.25,atol=3e-8,rtol=0);self.assertGreater(float(b[0,0,0]-h[0,0,0]),.4)

    def test_saturation_zero_uses_eq_half_code_center_not_neutral_gray(self):
        a=fixture.rgba((.2,.4,.8,.4));s,_=self.apply(a,effect('saturation',saturation=0));g,_=self.apply(a,effect('grayscale'))
        self.assertNotEqual(float(s[0,0,0]),float(s[0,0,2]));self.assertEqual(float(g[0,0,0]),float(g[0,0,2]))

    def test_gamma_is_luma_only_and_alpha_is_unmodified(self):
        a=fixture.rgba((.2,.4,.6,.39));out,_=self.apply(a,effect('gamma',gamma=1.5))
        before=to_codes(a[...,:3]);after=to_codes(out[...,:3])
        np.testing.assert_allclose(after[...,1:],before[...,1:],atol=8e-6,rtol=0);self.assertEqual(out[...,3].tobytes(),a[...,3].tobytes())

    def test_continuous_and_native_coefficients_are_distinct_declared_arithmetic(self):
        a=fixture.rgba((.2,.4,.6,.7));e=effect('brightness',brightness=.017)
        smooth,_=self.apply(a,e);e['parameters']['arithmetic']='native_coefficients';compat,m=self.apply(a,e)
        self.assertFalse(np.array_equal(smooth,compat));self.assertTrue(m['coefficient_quantization']);self.assertFalse(m['raster_quantization'])

    def test_continuous_ramp_keeps_more_than_integer_code_values(self):
        x=np.linspace(.1,.8,131072,dtype=np.float32);a=np.empty((1,len(x),4),np.float32)
        # Stay within the documented edge budget while testing a large raster.
        a=a.reshape(128,1024,4);a[...,:3]=x.reshape(128,1024,1);a[...,3]=.5
        out,_=self.apply(a,effect('brightness',brightness=.017))
        self.assertGreater(len(np.unique(out[...,0])),130000)

    def test_changed_planes_clip_but_unaffected_luma_headroom_survives(self):
        a=fixture.rgba((1.6,1.6,1.6,.3));out,m=self.apply(a,effect('saturation',saturation=1.4))
        self.assertGreater(float(out[0,0,0]),1.5);self.assertEqual(m['changed_plane_clipped_components'],0)
        low=fixture.rgba((-.3,-.3,-.3,.3));out,m=self.apply(low,effect('gamma',gamma=2))
        self.assertTrue(np.all(out[...,:3]==0));self.assertGreater(m['changed_plane_clipped_components'],0)

    def test_output_RGB_clip_is_explicit_and_separate(self):
        a=fixture.rgba((1.6,1.6,1.6,.3));out,m=self.apply(a,effect('color',output_gamut='clip'))
        self.assertTrue(np.all(out[...,:3]==1));self.assertEqual(m['output_clipped_components'],a.shape[0]*a.shape[1]*3)

    def test_eq10_is_explicit_continuous_extension(self):
        a=fixture.rgba((.2,.4,.8,.6));out,m=self.apply(a,effect('gamma',gamma=2,reference_bits=10))
        self.assertIn('no-native',m['ten_bit_eq']);self.assertTrue(np.isfinite(out).all())
        self.bad(lambda:compile_tone(effect('gamma',gamma=2,reference_bits=10,arithmetic='native_coefficients')))

    def test_zero_intensity_is_byte_identity_after_full_validation(self):
        a=fixture.rgba((-.2,.3,1.6,-0.));out,_=self.apply(a,effect('color',contrast=4,output_gamut='clip',intensity=0))
        self.assertEqual(a.tobytes(),out.tobytes());a[-1,-1,3]=np.nan;self.bad(lambda:self.apply(a,effect(intensity=0)))

    def test_srgb_signal_and_intensity_mix_use_linear_working_RGB(self):
        a=fixture.rgba((.2,.4,.7,.3));srgb={'primaries':'bt709','transfer':'srgb'}
        def encode(v):return 12.92*v if v<=.0031308 else 1.055*v**(1/2.4)-.055
        def decode(v):return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
        e=effect('color',brightness=.03,contrast=.8,input_signal=srgb,output_signal=srgb,intensity=.3)
        expected=scalar([encode(float(v)) for v in a[0,0,:3]],e['parameters']);expected=np.array([decode(v) for v in expected])
        out,_=self.apply(a,e);np.testing.assert_allclose(out[0,0,:3],a[0,0,:3]*.7+expected*.3,atol=7e-8,rtol=0)

    def test_distinct_input_output_signal_interpretation_is_honored(self):
        a=fixture.rgba((.2,.4,.7,.3));out,_=self.apply(a,effect(output_signal={'primaries':'bt709','transfer':'srgb'}))
        expected=np.where(a[...,:3]<=.04045,a[...,:3]/12.92,((a[...,:3]+.055)/1.055)**2.4)
        np.testing.assert_allclose(out[...,:3],expected,atol=6e-8,rtol=0)

    def test_all_six_easings_and_overshoot_are_bounded(self):
        values={'linear':.25,'hold':0,'ease_in':.0625,'ease_out':.4375,'ease_in_out':.125,'bezier':.25}
        for mode,want in values.items():
            e=effect('brightness');e['keyframes']=[track('amount',0,1,mode,controls=[1/3,2/3] if mode=='bezier' else None)];self.assertAlmostEqual(state_at(compile_tone(e),25)['brightness'],want)
        e=effect('brightness');e['keyframes']=[track('value',0,1,'bezier')];e['keyframes'][0]['keyframes'][0]['control_points']=[10,10]
        self.assertEqual(state_at(compile_tone(e),50)['brightness'],1)

    def test_large_rational_tick_and_hold_left_limit_remain_precise(self):
        n=10**20;e=effect('hue');e['keyframes']=[track('degrees',0,100,start=n,stop=n+100)]
        self.assertEqual(state_at(compile_tone(e),Fraction(n*2+1,2))['hue'],.5)
        e['keyframes'][0]['keyframes'][0]['interpolation']='hold'
        self.assertEqual(state_at(compile_tone(e),Fraction(n+100)-Fraction(1,1000))['hue'],0)
        self.assertEqual(state_at(compile_tone(e),n+100)['hue'],100)

    def test_four_control_Bezier_solves_author_time_root(self):
        e=effect('hue');e['keyframes']=[track('hue',0,100,'bezier')]
        e['keyframes'][0]['keyframes'][0]['control_points']=[.25,0,.75,1]
        self.assertAlmostEqual(state_at(compile_tone(e),50)['hue'],50,places=8)

    def test_each_family_channel_and_alias_can_animate(self):
        cases=[('brightness','amount',-.4,.4),('contrast','value',.3,2),('saturation','saturation',0,4),
            ('color','brightness',-.3,.3),('gamma_adjust','amount',.5,2),('hue_rotate','degrees',-90,90),
            ('hsl_adjust','brightness',-.5,.5),('grayscale','intensity',0,1)]
        for kind,prop,left,right in cases:
            e=effect(kind);e['keyframes']=[track(kind+'.'+prop,left,right)];p=compile_tone(e)
            self.assertIn((left+right)/2,state_at(p,50).values())

    def test_compiled_plan_does_not_retain_mutable_author_data(self):
        e=effect('brightness');e['keyframes']=[track('amount',0,1)];p=compile_tone(e)
        e['parameters']['brightness']=-1;e['parameters']['input_signal']['transfer']='bad';e['keyframes'][0]['keyframes'][0]['value']=-1
        self.assertEqual(state_at(p,25)['brightness'],.25)

    def test_invalid_signals_configuration_and_parameters_reject(self):
        cases=[{'matrix':'auto'},{'range':'auto'},{'matrix':None},{'range':None},{'reference_bits':True},
            {'reference_bits':12},{'arithmetic':'guess'},{'output_gamut':'auto'},{'contrast':float('nan')},
            {'contrast':True},{'saturation':4.1},{'intensity':-1},{'unknown':1},{'input_signal':LINEAR|{'tag':'guess'}}]
        for p in cases:self.bad(lambda p=p:compile_tone(effect(**p)))
        self.bad(lambda:compile_tone(effect('brightness',amount=.1,brightness=.1)))
        self.bad(lambda:compile_tone(effect('hsl',brightness=.1,lightness=.1)))

    def test_duplicate_aliases_bad_keyframes_and_double_location_reject(self):
        for rows in ([track('amount',0,1),track('brightness',0,1)],[track('bad',0,1)]):
            e=effect('brightness');e['keyframes']=rows;self.bad(lambda:compile_tone(e))
        e=effect('hue');e['keyframes']=[track('hue',0,100)];e['parameters']['keyframes']=[];self.bad(lambda:compile_tone(e))
        e=effect('hue');e['keyframes']=[track('hue',0,100)];e['keyframes'][0]['keyframes'][1]['at_tick']=0;self.bad(lambda:compile_tone(e))

    def test_keyframe_budget_and_authored_duration_reject(self):
        e=effect('hue');e['keyframes']=[{'property':'hue','keyframes':[{'at_tick':i,'value':0} for i in range(1025)]}]
        self.bad(lambda:compile_tone(e));e=effect('hue');e['keyframes']=[track('hue',0,100)]
        self.assertEqual(validate_tone(e,duration_tick=100),[]);self.assertTrue(validate_tone(e,duration_tick=99))

    def test_forged_plans_and_invalid_clocks_reject(self):
        p=compile_tone(effect())
        for forged in (replace(p,values=p.values[:-1]),replace(p,matrix='auto'),replace(p,tracks_json=' []')):
            self.bad(lambda:state_at(forged,0))
        for tick in (True,-1,float('nan'),'0'):self.bad(lambda:state_at(p,tick))

    def test_surface_layout_late_bad_alpha_and_nonfinite_values_reject_transactionally(self):
        a=fixture.rgba((.2,.4,.6,.5));a[-1,-1,3]=1.1;before=a.tobytes();self.bad(lambda:self.apply(a,tile_pixels=1));self.assertEqual(a.tobytes(),before)
        for value in (a.astype(np.float64),a[:,::2],np.zeros((2,3,3),np.float32)):
            self.bad(lambda value=value:self.apply(value))
        a[-1,-1,3]=.5;a[-1,-1,0]=np.inf;self.bad(lambda:self.apply(a))

    def test_readonly_input_and_all_tiles_produce_identical_pixels(self):
        a=np.random.default_rng(5).uniform(0,1,(31,29,4)).astype(np.float32);a.flags.writeable=False
        e=effect('hsl',hue=31,saturation=.8,lightness=.1);expected,_=self.apply(a,e,tile_pixels=1)
        for tile in (7,16384,262144):
            out,_=self.apply(a,e,tile_pixels=tile);self.assertEqual(expected.tobytes(),out.tobytes())

    def test_workspace_retained_tables_and_tile_budget_admit_before_output(self):
        a=fixture.rgba((.2,.4,.6,.5));before=a.tobytes()
        for options in ({'max_working_bytes':1},{'retained_table_bytes':768*1024*1024},{'tile_pixels':0},{'tile_pixels':True}):
            self.bad(lambda options=options:self.apply(a,**options));self.assertEqual(a.tobytes(),before)

    def test_cancel_and_callback_exception_preserve_caller_pixels(self):
        a=fixture.rgba((.2,.4,.6,.5));before=a.tobytes();count=[0]
        def cancel():count[0]+=1;return count[0]>6
        self.bad(lambda:self.apply(a,effect('gamma',gamma=2),tile_pixels=1,cancel=cancel),'RENDER_CANCELLED')
        self.assertEqual(a.tobytes(),before)
        def crash():raise RuntimeError('callback failed')
        with self.assertRaises(RuntimeError):self.apply(a,cancel=crash)
        self.assertEqual(a.tobytes(),before)

    def test_transfer_overflow_is_explicit_and_transactional(self):
        a=fixture.rgba((3e38,3e38,3e38,.5));before=a.tobytes()
        self.bad(lambda:self.apply(a,effect(output_signal={'primaries':'bt709','transfer':'srgb'})))
        self.assertEqual(a.tobytes(),before)

    def test_ordered_tone_exposure_and_eight_band_HSL_are_not_reordered(self):
        compiler=EffectCompiler(resource_root=None,working_signal=WORKING);a=fixture.rgba((.2,.4,.6,.5))
        rows=[effect('hue',degrees=20),{'type':'exposure','parameters':{'amount':.3}},effect('gamma',gamma=1.3),
            {'type':'selective_hsl','parameters':{'input_signal':LINEAR,'output_signal':LINEAR,'input_gamut':'clip','blue_hue':20}}]
        actual,m=compiler.apply(a,compiler.compile(rows),50);expected=a
        for row in rows:expected,_=compiler.apply(expected,compiler.compile([row]),50)
        self.assertEqual(actual.tobytes(),expected.tobytes());self.assertEqual(m['alpha'],'input-bits-preserved')
        reverse,_=compiler.apply(a,compiler.compile(list(reversed(rows))),50);self.assertFalse(np.array_equal(actual,reverse))

    def test_presentation_window_uses_original_tone_author_ticks(self):
        p,s=fixture.image_project(fixture.rgba((.1,.2,.3,.5)),duration=200);e=effect('hue');e['keyframes']=[track('degrees',-60,60,stop=200)]
        p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e]);host=FloatTimeline(p,'main',s,working_signal=WORKING)
        full=[host.render_frame(i)[0] for i in range(20)];selected=copy.deepcopy(p)
        selected['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=60,presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':200,'offset_tick':70})
        host=FloatTimeline(selected,'main',s,working_signal=WORKING)
        for i in range(6):self.assertEqual(host.render_frame(i)[0].tobytes(),full[i+7].tobytes())

    def test_nested_reverse_keeps_child_and_parent_author_clocks(self):
        p,s=fixture.image_project(fixture.rgba((.1,.2,.3,.5)),duration=200);child=copy.deepcopy(p['sequences'][0]);child['id']='child'
        e=effect('hue');e['keyframes']=[track('degrees',-60,60,'hold',stop=160)]
        child['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[e]);parent=p['sequences'][0]['tracks'][0]['clips'][0]
        parent.pop('asset_id');parent.update(sequence_id='child',duration_tick=200,source_out_tick=200,reverse=True,effects=[effect('hue',degrees=10)])
        p['sequences'].append(child);out,_=FloatTimeline(p,'main',s,working_signal=WORKING).render_frame(4)
        expected,_=self.apply(fixture.rgba((.1,.2,.3,.5)),e,tick=np.nextafter(160.,-np.inf));expected,_=self.apply(expected,parent['effects'][0],tick=40)
        np.testing.assert_allclose(out,expected,atol=2e-7,rtol=0)

    def test_validator_routes_native_tone_and_preserves_legacy_engine(self):
        from ai_ad_editor.validator import validate_project
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.visual(np.ones((2,16,32,4),np.float32)*.5);case.s['duration_tick']=18000
            e=effect('hsl');e['keyframes']=[track('hue',-60,60,stop=9000)];case.s['tracks'][0]['clips'][0]['effects']=[e]
            result=validate_project(case.root,case.p);self.assertTrue(result['ok'],result)
            e['parameters'].pop('matrix');self.assertFalse(validate_project(case.root,case.p)['ok'])
            case.p['settings'].pop('pixel_pipeline');case.s['tracks'][0]['clips'][0]['effects']=[{'type':'hsl','parameters':{'hue':30}}]
            self.assertTrue(validate_project(case.root,case.p)['ok'])
        finally:case.doCleanups()

    def test_real_preview_PCM_and_PNG16_share_continuous_tone(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000;pixels=case.visual(np.broadcast_to(np.array([.2,.3,.4,.5],np.float32),(2,16,32,4)).copy());audio=case.audio()
            e=effect('color',brightness=.03,contrast=.8,saturation=.6);e['keyframes']=[track('intensity',.25,.75,stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects']=[e];result=case.execute(end=2);actual=case.reference(result)
            source=np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/np.float32(65535);expected=source.copy()
            for i,strength in enumerate((.25,.75)):
                graded=scalar(source[i,0,0,:3],e['parameters'])
                expected[i,...,:3]=((source[i,...,:3].astype(np.float64)*(1-strength)+graded*strength)*source[i,...,3:4].astype(np.float64)).astype(np.float32)
            expected[...,3]=1;np.testing.assert_allclose(actual,expected,atol=1e-7,rtol=0);self.assertEqual(case.pcm(result),audio[:9600].tobytes())
            np.testing.assert_allclose(case.png(case.execute(mode='frame')),np.rint(actual[0].astype(np.float64)*65535),atol=1,rtol=0);case.assert_clean()
        finally:case.doCleanups()

    def test_real_formal_render_and_preview_share_transport_pixels(self):
        import json
        from ai_ad_editor.render import render_project
        from ai_ad_editor.project import project_write_lock
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000;case.visual(np.broadcast_to(np.array([.2,.3,.4,.5],np.float32),(2,16,32,4)).copy());case.audio()
            case.s['tracks'][0]['clips'][0]['effects']=[effect('hsl',hue=30,saturation=.7,lightness=.05)]
            actual=case.reference(case.execute(end=2))
            with project_write_lock(case.root):formal=render_project(case.root,case.p,case.s,case.root/'renders/tone.mkv')
            manifest=json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            payload=np.moveaxis(np.rint(actual[...,[1,2,0,3]].astype(np.float64)*65535).astype('<u2'),3,1).tobytes()
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],'sha256:'+hashlib.sha256(payload).hexdigest());case.assert_clean()
        finally:case.doCleanups()

    def test_real_cache_hit_and_matrix_change_invalidate_cache(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000;case.visual(np.broadcast_to(np.array([.2,.3,.4,.5],np.float32),(2,16,32,4)).copy());case.audio();e=effect('hue',degrees=20)
            case.s['tracks'][0]['clips'][0]['effects']=[e];one=case.execute(end=2);self.assertTrue(case.execute(end=2)['cache_hit'])
            e['parameters']['matrix']='smpte170m';two=case.execute(end=2);self.assertNotEqual(one['cache_key'],two['cache_key']);self.assertFalse(two['cache_hit']);case.assert_clean()
        finally:case.doCleanups()

    def test_capabilities_and_disabled_effects_report_limits(self):
        from ai_ad_editor.capabilities import build_capability_manifest
        row=build_capability_manifest()['capabilities']['timeline_native_float_basic_tone']
        self.assertIn('global_HSL_is_YCbCr_rotation_not_RGB_HSL',row['limits'])
        self.assertEqual(EffectCompiler(resource_root=None,working_signal=WORKING).compile([{'type':'hue','enabled':False,'parameters':{'bad':True}}]),())
