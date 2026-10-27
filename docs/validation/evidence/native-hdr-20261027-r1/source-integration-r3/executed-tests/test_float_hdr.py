"""Independent standard/scalar oracles and actual native HDR deliveries."""
import copy
from decimal import Decimal, localcontext
import hashlib
import math
from pathlib import Path
import unittest

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal, convert_rgba
from ai_ad_editor.float_hdr import LuminanceSignal as Signal, parse_signal, map_display, mapping_configuration
from ai_ad_editor.float_standard_render import configuration
from ai_ad_editor.project import save_project
from ai_ad_editor.media import probe_media
from ai_ad_editor.schema_contract import make_validator
from ai_ad_editor.render import output_settings
from ai_ad_editor.rights import add_record, load_ledger, save_ledger
from ai_ad_editor.validator import validate_project
from ai_ad_editor.media import ffmpeg_path

RECEIPTS=[]
PQ=Signal('bt2020','pq-st2084',203)
HLG=Signal('bt2020','hlg-bt2100',203,1000,1.2)
WORK=Signal('bt2020','linear',203)
MAPPING=dict(operator='reinhard-luminance',source_peak_nits=1000,target_peak_nits=100,
             exposure_stops=0,gamut_policy='clip')


def surface(rgb):
    a=np.ones((1,len(rgb),4),np.float32);a[0,:,:3]=rgb;return a


def pq_decimal(value, inverse=False):
    """50-digit scalar oracle independent of product NumPy/formula constants."""
    with localcontext() as c:
        c.prec=50
        x=Decimal(str(float(value)))
        m=Decimal(1305)/8192;n=Decimal(2523)/32
        a=Decimal(107)/128;b=Decimal(2413)/128;d=Decimal(2392)/128
        if inverse:
            p=(x/10000)**m
            return float(((a+b*p)/(1+d*p))**n)
        p=x**(1/n)
        return float(10000*(max(p-a,Decimal(0))/(b-d*p))**(1/m))


def hlg_scalar(rgb, peak=1000, gamma=1.2, inverse=False):
    rgb=list(map(float,rgb))
    a=.17883277;b=1-4*a;c=.5-a*math.log(4*a)
    if not inverse:
        scene=[v*v/3 if v<=.5 else (math.exp((v-c)/a)+b)/12 for v in rgb]
        y=sum(v*w for v,w in zip(scene,(.2627,.678,.0593)))
        return [peak*v*y**(gamma-1) if y else 0 for v in scene]
    display=[v/peak for v in rgb];y=sum(v*w for v,w in zip(display,(.2627,.678,.0593)))
    scene=[v*y**((1-gamma)/gamma) if y else 0 for v in display]
    return [math.sqrt(3*v) if v<=1/12 else a*math.log(12*v-b)+c for v in scene]


class HDRNumericTests(unittest.TestCase):
    def test_PQ_EOTF_matches_independent_50_digit_oracle_and_known_nits(self):
        codes=[0,.1,.25,.508078421517399,.5806888810416109,.751827096247041,1]
        source=surface([[v]*3 for v in codes]);result,meta=convert_rgba(source,PQ,WORK)
        expected=[pq_decimal(v)*1/203 for v in source[0,:,0]]
        np.testing.assert_allclose(result[0,:,0],expected,rtol=6e-8,atol=2e-8)
        np.testing.assert_allclose(result[0,3:6,0]*203,[100,203,1000],rtol=0,atol=.0005)
        self.assertTrue(meta['absolute_nits_managed']);self.assertFalse(meta['HDR_accepted'])
        RECEIPTS.append(dict(group='PQ-oracle',codes=codes,maximum_nit_error=float(np.max(np.abs(result[0,:,0]*203-np.array(expected)*203)))))

    def test_inverse_PQ_has_standard_nonzero_black_code_and_roundtrips(self):
        nits=[0,.001,.1,1,100,203,1000,10000]
        s=surface([[v/203]*3 for v in nits]);out,meta=convert_rgba(s,WORK,PQ,hdr_range_policy='clip')
        # 10000/203 rounded to the public Float32 working surface is slightly
        # above the exact endpoint. The explicit output policy records it.
        self.assertEqual(meta['hdr_output_components_clipped'],3)
        expected=[pq_decimal(min(float(v)*203,10000),inverse=True) for v in s[0,:,0]]
        np.testing.assert_allclose(out[0,:,0],expected,rtol=0,atol=3e-8)
        self.assertGreater(float(out[0,0,0]),0)
        back,_=convert_rgba(out,PQ,WORK)
        np.testing.assert_allclose(back,s,rtol=4e-6,atol=2e-8)

    def test_HLG_uses_coupled_RGB_OOTF_not_three_independent_power_curves(self):
        s=surface([[.75,.5,.25],[1,.3,.6],[0,0,0],[.75,.75,.75]])
        out,meta=convert_rgba(s,HLG,WORK)
        expected=np.array([hlg_scalar(v) for v in s[0,:,:3]],np.float64)/203
        np.testing.assert_allclose(out[0,:,:3],expected,rtol=6e-8,atol=3e-8)
        self.assertGreater(abs(float(out[0,0,0])*203-hlg_scalar([.75]*3)[0]),20)
        self.assertAlmostEqual(float(out[0,3,0])*203,203.152145,delta=.0002)
        self.assertTrue(meta['HLG_RGB_coupled_OOTF'])

    def test_HLG_inverse_peak_gamma_and_PQ_cross_conversion_match_scalar(self):
        for peak,gamma in [(1000,1.2),(2000,1.3264),(400,.95)]:
            signal=Signal('bt2020','hlg-bt2100',203,peak,gamma)
            source=surface([[.1,.3,.8],[.75,.5,.2],[1,1,1],[0,0,0]])
            linear,_=convert_rgba(source,signal,WORK)
            expected=np.array([hlg_scalar(v,peak,gamma) for v in source[0,:,:3]])/203
            np.testing.assert_allclose(linear[0,:,:3],expected,rtol=7e-8,atol=3e-8)
            back,_=convert_rgba(linear,WORK,signal,hdr_range_policy='clip')
            np.testing.assert_allclose(back,source,rtol=0,atol=6e-8)
            pq,_=convert_rgba(source,signal,PQ)
            oracle=np.array([[pq_decimal(v*203,inverse=True) for v in row] for row in expected])
            np.testing.assert_allclose(pq[0,:,:3],oracle,rtol=0,atol=3e-8)

    def test_explicit_reference_white_rescales_absolute_light_and_PQ_is_invariant(self):
        source=surface([[1,.5,.25]])
        a=Signal('bt709','linear',100);b=Signal('bt709','linear',200)
        result,meta=convert_rgba(source,a,b)
        np.testing.assert_array_equal(result[...,:3],source[...,:3]/2);self.assertEqual(meta['linear_unit_scale'],.5)
        for white in (100,203,1000):
            out,_=convert_rgba(surface([[100/white]*3]),Signal('bt2020','linear',white),PQ)
            self.assertAlmostEqual(float(out[0,0,0]),pq_decimal(100,inverse=True),delta=3e-8)

    def test_units_and_HLG_context_are_required_and_bad_types_are_rejected(self):
        for value in [dict(primaries='bt2020',transfer='pq-st2084'),
            dict(primaries='bt2020',transfer='hlg-bt2100',reference_white_nits=203),
            dict(primaries='bt709',transfer='pq-st2084',reference_white_nits=203),
            dict(primaries='bt2020',transfer='linear',reference_white_nits=True),
            dict(primaries='bt2020',transfer='linear',reference_white_nits=float('nan')),
            dict(primaries='bt2020',transfer='linear',reference_white_nits=203,system_gamma=1.2),
            dict(primaries='bt2020',transfer='hlg-bt2100',reference_white_nits=203,display_peak_nits=1000,system_gamma=[]),
            dict(primaries='bt2020',transfer='linear',reference_white_nits=203,unknown=1)]:
            with self.subTest(value=value),self.assertRaises(AppError):parse_signal(value)
        with self.assertRaises(AppError):convert_rgba(surface([[.5]*3]),PQ,ColorSignal('bt2020','linear'))
        self.assertEqual(vars(parse_signal(dict(primaries='bt709',transfer='linear'))),dict(primaries='bt709',transfer='linear'))

    def test_source_and_output_domain_policies_report_every_clamp(self):
        source=surface([[-.001,.5,1.001]]);before=source.tobytes()
        with self.assertRaises(AppError):convert_rgba(source,PQ,WORK)
        out,meta=convert_rgba(source,PQ,WORK,hdr_input_range_policy='clip')
        self.assertEqual(meta['hdr_input_components_clipped'],2);self.assertEqual(source.tobytes(),before)
        with self.assertRaises(AppError):convert_rgba(surface([[-1,.5,100]]),WORK,PQ)
        _,meta=convert_rgba(surface([[-1,.5,100]]),WORK,PQ,hdr_range_policy='clip')
        self.assertEqual(meta['hdr_output_components_clipped'],2)
        # Saturated HLG display red at nominal peak is outside HLG scene gamut.
        with self.assertRaises(AppError):convert_rgba(surface([[1000/203,0,0]]),WORK,HLG)
        _,meta=convert_rgba(surface([[1000/203,0,0]]),WORK,HLG,hdr_range_policy='clip')
        self.assertGreater(meta['hdr_output_components_clipped'],0)

    def test_identical_signals_preserve_bits_but_do_not_bypass_HDR_domain_checks(self):
        source=surface([[.2,.3,.4],[.5,.6,.7]]);source[0,:,3]=[np.float32(-0.),np.nextafter(np.float32(0),np.float32(1))]
        same,meta=convert_rgba(source,PQ,PQ);self.assertEqual(same.tobytes(),source.tobytes());self.assertTrue(meta['same_signal_byte_exact'])
        output,_=convert_rgba(source,PQ,WORK);self.assertEqual(output[...,3].tobytes(),source[...,3].tobytes())
        source[0,0,0]=-1
        with self.assertRaises(AppError):convert_rgba(source,PQ,PQ)
        _,meta=convert_rgba(source,PQ,PQ,hdr_input_range_policy='clip');self.assertFalse(meta['same_signal_byte_exact'])

    def test_tiles_cancel_and_budgets_preserve_caller_surface(self):
        source=np.random.default_rng(51).uniform(.01,.98,(7,13,4)).astype(np.float32);before=source.tobytes()
        outputs=[convert_rgba(source,HLG,WORK,tile_pixels=n)[0].tobytes() for n in (1,7,29,65536)]
        self.assertEqual(len(set(outputs)),1)
        for change in [dict(max_working_bytes=1),dict(hdr_range_policy=[]),dict(hdr_input_range_policy=True)]:
            with self.assertRaises(AppError):convert_rgba(source,HLG,WORK,**change)
        calls=[]
        def cancel():
            calls.append(1)
            if len(calls)==4:raise AppError('CANCELLED','test',exit_code=8)
        with self.assertRaises(AppError):convert_rgba(source,HLG,WORK,tile_pixels=3,cancel=cancel)
        self.assertEqual(source.tobytes(),before)

    def test_display_mapping_matches_scalar_neutral_shoulder_and_alpha(self):
        nits=[0,1,18,100,203,500,1000]
        s=surface([[v/203]*3 for v in nits]);s[...,3]=.4
        out,target,meta=map_display(s,WORK,MAPPING)
        expected=[]
        for v in s[0,:,0]:
            x=float(v)*203/100;expected.append(x*(1+x/100)/(1+x))
        np.testing.assert_allclose(out[0,:,0],expected,rtol=1e-7,atol=3e-8)
        self.assertEqual(out[...,3].tobytes(),s[...,3].tobytes());self.assertEqual(target.reference_white_nits,100)
        self.assertFalse(meta['BT2390_claimed']);self.assertFalse(meta['automatic_peak_inference'])

    def test_mapping_rejects_or_counts_gamut_excess_and_peak_overflow(self):
        s=surface([[1,0,0],[20000/203]*3])
        with self.assertRaises(AppError):map_display(s,WORK,{**MAPPING,'gamut_policy':'reject'})
        out,_,meta=map_display(s,WORK,MAPPING)
        self.assertGreater(meta['negative_components_clipped'],0);self.assertGreater(meta['over_one_components_clipped'],0)
        self.assertEqual(meta['above_declared_peak_pixels'],1);self.assertLessEqual(float(np.max(out)),1)

    def test_mapping_validates_full_context_budgets_exposure_and_cancellation(self):
        for value in [{},None,{**MAPPING,'gamut_policy':[]},{**MAPPING,'target_peak_nits':2000},
                      {**MAPPING,'source_peak_nits':50},{**MAPPING,'exposure_stops':True}]:
            with self.assertRaises(AppError):mapping_configuration(value)
        s=surface([[.5,.5,.5]])
        with self.assertRaises(AppError):map_display(s,ColorSignal('bt2020','linear'),MAPPING)
        for budget in (1,True,'large'):
            with self.assertRaises(AppError):map_display(s,WORK,MAPPING,max_working_bytes=budget)
        out,_,_=map_display(s,WORK,{**MAPPING,'exposure_stops':1})
        x=float(s[0,0,0])*203/100*2
        self.assertAlmostEqual(float(out[0,0,0]),x*(1+x/100)/(1+x),delta=8e-8)
        before=s.tobytes()
        def cancel():raise AppError('CANCELLED','test',exit_code=8)
        with self.assertRaises(AppError):map_display(s,WORK,MAPPING,cancel=cancel)
        self.assertEqual(s.tobytes(),before)


class HDRIntegrationTests(unittest.TestCase):
    def setUp(self):
        from test_float_standard_render import FloatStandardRenderTests
        self.f=FloatStandardRenderTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.s['duration_tick']=72000
        self.configure(PQ)

    def configure(self,signal):
        f=self.f;f.p['settings']['color']=dict(primaries='bt2020',transfer='smpte2084' if signal.transfer=='pq-st2084' else 'arib-std-b67',matrix='bt2020nc',range='limited')
        f.p['settings']['pixel_pipeline'].update(working_signal=vars(WORK),output_signal=vars(signal),range_policy='reject',preview_mapping=dict(MAPPING))

    def source(self,signal=PQ):
        f=self.f
        codes=np.linspace(.01,.75,32,dtype=np.float32)
        rgba=np.ones((8,16,32,4),np.float32);rgba[...,:3]=codes[None,None,:,None]
        for frame in range(8):rgba[frame,:,:,:3]*=1-frame*.015
        f.visual(rgba)
        f.p['settings']['pixel_pipeline']['sources']['picture']['source_signal']=vars(signal)
        self.samples=f.audio()
        audio=f.p['assets'][-1];audio['rights_ref']='rights_audio'
        ledger=load_ledger(f.root)
        add_record(ledger,dict(record_id='rights_audio',asset_id='sound',verification_status='verified',
            source_type='generated',source_url=str(f.root/'assets/audio.wav'),license_spdx='CC0-1.0',
            permitted_uses=['all'],commercial_use_allowed=True,modification_allowed=True,attribution_required=False,
            sha256=audio['sha256'],evidence='Original synthetic stereo tones generated by this test.'))
        save_ledger(f.root,ledger)
        c=f.s['tracks'][1]['clips'][0];c.update(id='audio_clip',duration_tick=72000,source_out_tick=72000)
        save_project(f.root,f.p)
        checked=validate_project(f.root,f.p);self.assertTrue(checked['ok'],checked)
        return (np.rint(rgba.astype(np.float64)*65535)/65535).astype(np.float32)

    def receipt(self,result,group):
        RECEIPTS.append(dict(group=group,result=copy.deepcopy(result)))

    def test_PQ_ten_bit_actual_pixels_VUI_and_complete_PCM(self):
        f=self.f;source=self.source();result=f.execute();actual=f.decode_y(result['path'],32,16)
        expected=64+source[...,0].astype(np.float64)*876
        self.assertEqual(actual.shape[0],8);self.assertLessEqual(float(np.max(np.abs(actual[:,0]-expected))),1.5)
        self.assertGreater(len(np.unique(actual[:,0])),100)
        video=next(v for v in probe_media(Path(result['path']))['streams'] if v.get('codec_type')=='video')
        for key,value in dict(color_primaries='bt2020',color_transfer='smpte2084',color_space='bt2020nc',pix_fmt='yuv444p10le').items():self.assertEqual(video[key],value)
        self.assertEqual(result['delivery']['pixel_pipeline']['transport']['frames'],8)
        pcm=f.native([ffmpeg_path(),'-nostdin','-v','error','-i',result['path'],'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        self.assertEqual(pcm,self.samples[:38400].tobytes())
        f.assert_clean();self.receipt(result,'actual-PQ-10bit')

    def test_HLG_ten_bit_roundtrip_and_PQ_to_HLG_absolute_light_conversion(self):
        f=self.f;self.configure(HLG);source=self.source(HLG);first=f.execute('hlg.mkv');actual=f.decode_y(first['path'],32,16)
        self.assertLessEqual(float(np.max(np.abs(actual[:,0]-(64+source[...,0]*876)))),1.5)
        video=next(v for v in probe_media(Path(first['path']))['streams'] if v.get('codec_type')=='video');self.assertEqual(video['color_transfer'],'arib-std-b67')
        f.p['settings']['pixel_pipeline']['sources']['picture']['source_signal']=vars(PQ)
        second=f.execute('pq-to-hlg.mkv');actual=f.decode_y(second['path'],32,16)
        expected=np.array([hlg_scalar([pq_decimal(v)]*3,inverse=True)[0] for v in source[...,0].flat]).reshape(8,16,32)
        self.assertLessEqual(float(np.max(np.abs(actual[:,0]-(64+expected*876)))),1.5)
        f.assert_clean();self.receipt(second,'actual-PQ-to-HLG')

    def test_actual_explicit_SDR_trim_matches_independent_scalar_luminance(self):
        f=self.f;source=self.source();p=f.p['settings']['pixel_pipeline'];p['display_mapping']=dict(MAPPING)
        p['output_signal']=vars(Signal('bt709','linear',100));f.p['settings']['color']=dict(primaries='bt709',transfer='linear',matrix='bt709',range='limited')
        result=f.execute('trim.mkv');actual=f.decode_y(result['path'],32,16)
        x=np.array([pq_decimal(v)/100 for v in source[...,0].flat]).reshape(8,16,32)
        expected=x*(1+x/100)/(1+x)
        self.assertLessEqual(float(np.max(np.abs(actual[:,0]-(64+expected*876)))),1.5)
        self.assertEqual(result['delivery']['pixel_pipeline']['display_mapping'],MAPPING)
        f.assert_clean();self.receipt(result,'actual-SDR-trim')

    def test_HDR_previews_are_explicit_SDR_views_and_preserve_author_bytes(self):
        f=self.f;self.source();before=(f.root/'project.json').read_bytes()
        for args in [('preview','frame','--frame','2'),('preview','range','--start-frame','0','--end-frame','3')]:
            code,result=f.invoke(*args,'--project',f.root,'--height','64')
            self.assertEqual(code,0,result);data=result['data'];self.assertEqual(data['request']['reference_signal']['primaries'],'bt709')
            self.assertEqual(data['request']['display_mapping'],MAPPING)
            self.assertFalse(data['request']['HDR_reference_preserved']);self.receipt(data,'actual-HDR-SDR-preview')
        self.assertEqual(before,(f.root/'project.json').read_bytes())

    def test_missing_preview_mapping_or_invalid_delivery_is_rejected_before_mutation(self):
        f=self.f;self.source();p=f.p['settings']['pixel_pipeline'];p.pop('preview_mapping');save_project(f.root,f.p)
        before=(f.root/'project.json').read_bytes();code,value=f.invoke('preview','frame','--project',f.root,'--frame','0','--height','64')
        self.assertNotEqual(code,0);self.assertEqual(before,(f.root/'project.json').read_bytes())
        self.assertTrue(any(e['code']=='FLOAT_RENDER_HDR_PREVIEW' for e in value['errors']),value)
        for change in ('precision','units','tags'):
            settings=copy.deepcopy(f.p['settings'])
            if change=='precision':settings['output']['video']['pixel_format']='yuv420p'
            elif change=='units':settings['pixel_pipeline']['working_signal']=dict(primaries='bt2020',transfer='linear')
            else:settings['color']['transfer']='bt709'
            with self.assertRaises(AppError):configuration(settings['pixel_pipeline'],settings,output_settings(settings))

    def test_schema_accepts_explicit_HDR_and_rejects_missing_HLG_context(self):
        self.source();validator=make_validator()
        self.assertEqual(list(validator.iter_errors(self.f.p)),[])
        invalid=copy.deepcopy(self.f.p);invalid['settings']['pixel_pipeline']['output_signal']=dict(primaries='bt2020',transfer='hlg-bt2100',reference_white_nits=203)
        self.assertTrue(list(validator.iter_errors(invalid)))

    def test_native_ten_bit_YCbCr_input_preserves_codes_without_eight_bit_stage(self):
        f=self.f;self.source();first=f.execute('source-pq.mkv')
        code,value=f.invoke('media','ingest','--project',f.root,'--input',first['path'],'--asset-id','ten-bit',
            '--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','all','--evidence','Original synthetic HDR test master')
        self.assertEqual(code,0,value)
        from ai_ad_editor.project import load_project
        _,f.p=load_project(f.root);f.s=f.p['sequences'][0]
        f.s['tracks'][0]['clips'][0]['asset_id']='ten-bit'
        f.p['settings']['pixel_pipeline']['sources']['ten-bit']=dict(source_signal=vars(PQ),display_geometry='square-unrotated',
            yuv_spec=dict(matrix='bt2020nc',range='limited',chroma_location='left'),scan='progressive',demux_origin=0)
        second=f.execute('from-yuv.mkv')
        a=f.decode_y(first['path'],32,16);b=f.decode_y(second['path'],32,16)
        self.assertLessEqual(int(np.max(np.abs(a.astype(int)-b))),1)
        source=second['delivery']['pixel_pipeline']['source_receipts']['ten-bit']
        self.assertEqual(source['pixel_format'],'yuv444p10le')
        f.assert_clean();self.receipt(second,'actual-native-10bit-YCbCr-source')

    def test_editable_package_retains_absolute_signals_and_complete_encoded_audio_video(self):
        f=self.f;self.source();first=f.execute('before-package.mkv')
        archive=f.root/'exports/hdr.zip';code,value=f.invoke('convert','export','--project',f.root,'--output',archive,'--target-format','package')
        self.assertEqual(code,0,value)
        restored=f.base/'restored-hdr';code,value=f.invoke('convert','import','--input',archive,'--output',restored);self.assertEqual(code,0,value)
        from ai_ad_editor.project import load_project, project_write_lock
        from ai_ad_editor.render import render_project
        _,p=load_project(restored);self.assertEqual(p['settings']['pixel_pipeline'],f.p['settings']['pixel_pipeline'])
        with project_write_lock(restored):second=render_project(restored,p,p['sequences'][0],restored/'renders/after.mkv')
        for fmt in ('yuv444p10le','pcm_f32le'):
            if fmt=='yuv444p10le':a=f.decode_y(first['path'],32,16).tobytes();b=f.decode_y(second['path'],32,16).tobytes()
            else:
                def pcm(path):return f.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a',fmt,'-f','f32le','pipe:1'])
                a=pcm(first['path']);b=pcm(second['path'])
            self.assertEqual(a,b)
        self.receipt(second,'actual-editable-HDR-package-roundtrip')
