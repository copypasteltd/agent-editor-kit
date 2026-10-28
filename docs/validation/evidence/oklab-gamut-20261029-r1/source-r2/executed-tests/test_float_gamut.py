"""Independent scalar OKLab oracle, contracts and actual native delivery."""
import copy
import math
import unittest

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_gamut import reduce_chroma
from ai_ad_editor.float_hdr import map_display, LuminanceSignal, mapping_configuration

RECEIPTS=[]
MAPPING=dict(operator='reinhard-luminance',source_peak_nits=1000,target_peak_nits=100,
             exposure_stops=0,gamut_policy='oklab-chroma')


def lab_scalar(c):
    r,g,b=map(float,c)
    cube=lambda x: math.copysign(abs(x)**(1/3),x)
    l=cube(.4122214708*r+.5363325363*g+.0514459929*b)
    m=cube(.2119034982*r+.6806995451*g+.1073969566*b)
    s=cube(.0883024619*r+.2817188376*g+.6299787005*b)
    return (.2104542553*l+.7936177850*m-.0040720468*s,
            1.9779984951*l-2.4285922050*m+.4505937099*s,
            .0259040371*l+.7827717662*m-.8086757660*s)


def rgb_scalar(c):
    L,a,b=c
    l=(L+.3963377774*a+.2158037573*b)**3
    m=(L-.1055613458*a-.0638541728*b)**3
    s=(L-.0894841775*a-1.291485548*b)**3
    return (4.0767416621*l-3.3077115913*m+.2309699292*s,
            -1.2684380046*l+2.6097574011*m-.3413193965*s,
            -.0041960863*l-.7034186147*m+1.707614701*s)


def oracle(c):
    if all(0<=v<=1 for v in c):return c
    L,a,b=lab_scalar(c)
    if L<=0:return (0.,)*3
    if L>=1:return (1.,)*3
    # More iterations and independent published inverse scalar equations.
    lo=0.;hi=1.
    for _ in range(48):
        mid=(lo+hi)/2;r=rgb_scalar((L,a*mid,b*mid))
        if all(0<=v<=1 for v in r):lo=mid
        else:hi=mid
    return rgb_scalar((L,a*lo,b*lo))


class GamutTests(unittest.TestCase):
    def test_scalar_reference_all_hues_and_lightness(self):
        colors=[]
        for L in (.15,.4,.65,.9):
            for h in np.linspace(-math.pi,math.pi,49):
                colors.append(rgb_scalar((L,.5*math.cos(h),.5*math.sin(h))))
        a=np.array(colors,np.float64);out,receipt=reduce_chroma(a)
        expected=np.array([oracle(c) for c in a]);error=float(np.max(np.abs(out-expected)))
        self.assertLess(error,9e-7);self.assertTrue(np.all((out>=0)&(out<=1)))
        RECEIPTS.append(dict(scope='196-scalar-colours',maximum_linear_RGB_error=error,counts=receipt))

    def test_preserves_lightness_hue_and_reduces_chroma(self):
        a=np.array([rgb_scalar((.6,.4*math.cos(h),.4*math.sin(h))) for h in np.linspace(-3,3,31)])
        out,r=reduce_chroma(a)
        for before,after in zip(a,out):
            L,x,y=lab_scalar(before);l,u,v=lab_scalar(after)
            self.assertAlmostEqual(L,l,places=11)
            self.assertLess(abs(x*v-y*u),1e-11)
            self.assertLessEqual(math.hypot(u,v),math.hypot(x,y)+1e-11)
        self.assertEqual(r['gamut_chroma_reduced_pixels'],31)

    def test_in_gamut_and_neutral_bits_unchanged(self):
        a=np.random.default_rng(38).random((101,3));a[:3]=[[0,0,0],[1,1,1],[.5,.5,.5]]
        out,r=reduce_chroma(a);self.assertEqual(a.tobytes(),out.tobytes());self.assertEqual(r['gamut_pixels_mapped'],0)

    def test_lightness_endpoints_counted_not_claimed_preserved(self):
        a=np.array([[-1,-1,-1],[2,2,2]],np.float64);out,r=reduce_chroma(a)
        np.testing.assert_array_equal(out,[[0,0,0],[1,1,1]])
        self.assertEqual(r['gamut_lightness_to_black_pixels'],1);self.assertEqual(r['gamut_lightness_to_white_pixels'],1)

    def test_invalid_and_unbounded_tiles_rejected(self):
        for a in [None,np.zeros((0,3)),np.zeros((65537,3)),np.zeros((3,4)),np.zeros((2,3),np.float32),np.array([[np.nan,0,0]])]:
            with self.assertRaises(AppError):reduce_chroma(a)

    def test_cancellation_inside_search_leaves_input_unchanged(self):
        a=np.array([[1.5,-.1,.3]],np.float64);before=a.tobytes();calls=[]
        def cancel():
            calls.append(1)
            if len(calls)==5:raise AppError('CANCELLED','test',exit_code=8)
        with self.assertRaisesRegex(AppError,'test'):reduce_chroma(a,cancel=cancel)
        self.assertEqual(a.tobytes(),before);self.assertEqual(len(calls),5)

    def test_target_rejected_before_mapping(self):
        a=np.ones((1,1,4),np.float32)
        with self.assertRaises(AppError):map_display(a,LuminanceSignal('bt2020','linear',203),MAPPING,target_primaries='bt2020')

    def test_negative_luminance_explicitly_rejected(self):
        a=np.ones((1,1,4),np.float32);a[...,:3]=-1
        with self.assertRaises(AppError):map_display(a,LuminanceSignal('bt709','linear',100),MAPPING)

    def test_mapping_keeps_alpha_input_and_exposes_no_component_clip(self):
        a=np.array([[[1,0,0,.25],[0,1,0,.5],[0,0,1,.75],[.5,.5,.5,1]]],np.float32);before=a.tobytes()
        out,signal,r=map_display(a,LuminanceSignal('bt2020','linear',203),MAPPING)
        self.assertEqual(a.tobytes(),before);self.assertEqual(out[...,3].tobytes(),a[...,3].tobytes())
        self.assertEqual(signal.primaries,'bt709');self.assertEqual(r['negative_components_clipped'],0)
        self.assertEqual(r['over_one_components_clipped'],0);self.assertGreater(r['perceptual_gamut']['gamut_pixels_mapped'],0)
        self.assertFalse(r['perceptual_gamut']['component_clipping'])

    def test_mapping_domain_configuration_and_budget(self):
        self.assertEqual(mapping_configuration(MAPPING)['gamut_policy'],'oklab-chroma')
        a=np.ones((1,1,4),np.float32)
        with self.assertRaises(AppError):map_display(a,LuminanceSignal('bt709','linear',100),MAPPING,max_working_bytes=1)


class GamutIntegrationTests(unittest.TestCase):
    def setUp(self):
        from test_float_hdr import HDRIntegrationTests
        self.h=HDRIntegrationTests('runTest');self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.f=self.h.f;self.h.source()
        self.f.p['settings']['pixel_pipeline']['preview_mapping']=copy.deepcopy(MAPPING)

    def test_actual_HDR_preview_keeps_author_project_and_reports_mapping(self):
        from ai_ad_editor.project import save_project
        f=self.f;save_project(f.root,f.p);before=(f.root/'project.json').read_bytes()
        code,value=f.invoke('preview','frame','--project',f.root,'--frame','0','--height','64')
        self.assertEqual(code,0,value);self.assertEqual((f.root/'project.json').read_bytes(),before)
        self.assertEqual(value['data']['request']['display_mapping']['gamut_policy'],'oklab-chroma')
        f.assert_clean();RECEIPTS.append(dict(scope='actual-HDR-preview',result=value))

    def test_actual_SDR_render_and_editable_package_complete_pixels_PCM(self):
        from ai_ad_editor.project import load_project,project_write_lock
        from ai_ad_editor.render import render_project
        from ai_ad_editor.media import ffmpeg_path
        f=self.f;p=f.p['settings'];p['color'].update(primaries='bt709',transfer='bt709',matrix='bt709')
        p['pixel_pipeline'].update(output_signal=dict(primaries='bt709',transfer='srgb',reference_white_nits=100),display_mapping=copy.deepcopy(MAPPING))
        # Match actual encoder transfer tag to explicit sRGB output.
        p['color']['transfer']='iec61966-2-1'
        first=f.execute('oklab.mkv');meta=first['delivery']['pixel_pipeline']['last_display_mapping']
        self.assertIn('perceptual_gamut',meta)
        archive=f.root/'exports/oklab.zip';code,value=f.invoke('convert','export','--project',f.root,'--output',archive,'--target-format','package');self.assertEqual(code,0,value)
        restored=f.base/'restored';code,value=f.invoke('convert','import','--input',archive,'--output',restored);self.assertEqual(code,0,value)
        _,p=load_project(restored);self.assertEqual(p['settings']['pixel_pipeline'],f.p['settings']['pixel_pipeline'])
        with project_write_lock(restored):second=render_project(restored,p,p['sequences'][0],restored/'renders/again.mkv')
        self.assertEqual(f.decode_y(first['path'],32,16).tobytes(),f.decode_y(second['path'],32,16).tobytes())
        def pcm(path):return f.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        self.assertEqual(pcm(first['path']),pcm(second['path']));self.assertEqual(pcm(first['path']),self.h.samples[:38400].tobytes())
        f.assert_clean();RECEIPTS.append(dict(scope='actual-SDR-render-package-replay',first=first,second=second))
