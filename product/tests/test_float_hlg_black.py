"""Independent BT.2100 black-lift oracles and actual native HDR deliveries."""
import copy,json,math,unittest
from pathlib import Path
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import convert_rgba
from ai_ad_editor.float_hdr import LuminanceSignal,parse_signal,to_linear,from_linear
from ai_ad_editor.float_hlg_black import HLGBlackSignal,beta
from ai_ad_editor.float_chromatic import equivalent
from ai_ad_editor.project import save_project,load_project,project_write_lock
from ai_ad_editor.render import render_project
from ai_ad_editor.media import ffmpeg_path,probe_media
from ai_ad_editor.schema_contract import make_validator
import test_float_hdr as hdr_reference
surface,pq_decimal=hdr_reference.surface,hdr_reference.pq_decimal

RECEIPTS=[]
BASE=dict(primaries='bt2020',transfer='hlg-bt2100',reference_white_nits=203,display_peak_nits=1000,system_gamma=1.2)
BLACK=parse_signal(BASE|dict(display_black_nits=.005))
WORK=LuminanceSignal('bt2020','linear',203)
PQ=LuminanceSignal('bt2020','pq-st2084',203)

def scalar(rgb,black=.005,peak=1000,gamma=1.2,inverse=False):
    """Independent scalar/log implementation of Table5, no product constants."""
    lift=math.sqrt(3)*math.exp(math.log(black/peak)/(2*gamma)) if black else 0
    aa=.17883277;bb=1-4*aa;cc=.5-aa*math.log(4*aa)
    if not inverse:
        lifted=[lift+(1-lift)*float(v) for v in rgb]
        scene=[v*v/3 if v<=.5 else (math.exp((v-cc)/aa)+bb)/12 for v in lifted]
        yy=sum(x*y for x,y in zip(scene,(.2627,.678,.0593)))
        return [peak*x*yy**(gamma-1) if yy else 0 for x in scene]
    display=[float(x)/peak for x in rgb];yy=sum(x*y for x,y in zip(display,(.2627,.678,.0593)))
    scene=[x*yy**((1-gamma)/gamma) if yy else 0 for x in display]
    lifted=[math.sqrt(3*x) if x<=1/12 else aa*math.log(12*x-bb)+cc for x in scene]
    return [(x-lift)/(1-lift) for x in lifted]

class HLGBlackNumericTests(unittest.TestCase):
    def test_declared_neutral_black_and_peak_match_physical_nits(self):
        for black in (.00001,.005,.1,.5,1,10):
            signal=parse_signal(BASE|dict(display_black_nits=black));a=surface([[0,0,0],[1,1,1]])
            out,m=convert_rgba(a,signal,WORK)
            np.testing.assert_allclose(out[0,0,:3]*203,black,rtol=1e-7,atol=1e-8)
            np.testing.assert_allclose(out[0,1,:3]*203,1000,rtol=2e-7,atol=1e-4)
            self.assertEqual(m['HLG_black_level']['source']['display_black_nits'],black)
            RECEIPTS.append(dict(test=self.id(),black_nits=black,actual_black_nits=float(out[0,0,0])*203,beta=beta(signal)))
    def test_colored_coupled_EOTF_matches_independent_scalar_reference(self):
        source=surface([[0,.2,.7],[.2,.7,.4],[.8,.1,.3],[.4,.4,.4],[.99,.7,.5]])
        for peak,gamma,black in ((500,.8,.005),(1000,1.2,.1),(2000,1.4,.5)):
            signal=parse_signal(BASE|dict(display_peak_nits=peak,system_gamma=gamma,display_black_nits=black))
            out,_=convert_rgba(source,signal,WORK)
            expected=np.array([scalar(rgb,black,peak,gamma) for rgb in source[0,:,:3]])/203
            error=float(np.max(np.abs(out[0,:,:3]-expected)));self.assertLess(error,2e-7)
            RECEIPTS.append(dict(test=self.id(),peak=peak,gamma=gamma,black=black,maximum_error=error))
    def test_inverse_coupled_transform_matches_scalar_and_double_precision_roundtrip(self):
        codes=np.array([[.02,.2,.7],[.8,.1,.3],[.4,.4,.4],[.99,.99,.99]],float)
        nits=np.array([scalar(v) for v in codes]);actual,clipped=from_linear(nits/203,BLACK)
        np.testing.assert_allclose(actual,codes,rtol=0,atol=3e-15);self.assertEqual(clipped,0)
        encoded=np.array([scalar(v,inverse=True) for v in nits]);np.testing.assert_allclose(actual,encoded,rtol=0,atol=3e-15)
    def test_rounded_standard_white_endpoint_requires_explicit_range_policy(self):
        nits=np.array([scalar([1,1,1])]);self.assertTrue(np.all(nits>1000))
        with self.assertRaises(AppError):from_linear(nits/203,BLACK)
        encoded,clipped=from_linear(nits/203,BLACK,policy='clip')
        np.testing.assert_allclose(encoded,1,rtol=0,atol=1e-8);self.assertEqual(clipped,3)
    def test_omitted_and_explicit_zero_preserve_legacy_math_metadata_and_source_bits(self):
        old=parse_signal(BASE);zero=parse_signal(BASE|dict(display_black_nits=0))
        self.assertNotIn('display_black_nits',vars(old));self.assertTrue(equivalent(old,zero))
        codes=np.random.default_rng(710).uniform(.001,.99,(31,3))
        self.assertEqual(to_linear(codes,old).tobytes(),to_linear(codes,zero).tobytes())
        values=np.random.default_rng(711).uniform(.01,.6,(31,3))
        self.assertEqual(from_linear(values,old)[0].tobytes(),from_linear(values,zero)[0].tobytes())
        a=surface([[0,.2,.7],[.8,.4,.1]]);a[0,:,3]=np.array([0x80000000,1],np.uint32).view(np.float32)
        b,m=convert_rgba(a,zero,old);self.assertEqual(a.tobytes(),b.tobytes());self.assertTrue(m['same_signal_byte_exact'])
        self.assertEqual(m['HLG_black_level']['source']['display_black_nits'],0)
    def test_different_black_declarations_never_take_identical_signal_shortcut(self):
        target=parse_signal(BASE|dict(display_black_nits=.5));a=surface([[.4,.4,.4],[.7,.5,.3]])
        self.assertFalse(equivalent(BLACK,target));b,m=convert_rgba(a,BLACK,target)
        expected=np.array([scalar(scalar(v),black=.5,inverse=True) for v in a[0,:,:3]])
        np.testing.assert_allclose(b[0,:,:3],expected,rtol=0,atol=3e-8);self.assertFalse(m['same_signal_byte_exact'])
    def test_alpha_signed_zero_and_subnormal_bits_are_independent(self):
        a=surface([[.2,.6,.4],[.7,.3,.9]]);a[0,:,3]=np.array([0x80000000,1],np.uint32).view(np.float32)
        b,_=convert_rgba(a,BLACK,PQ);self.assertEqual(a[...,3].tobytes(),b[...,3].tobytes())
    def test_HLG_black_to_PQ_matches_independent_fifty_digit_PQ_oracle(self):
        a=surface([[0,0,0],[.02,.1,.3],[.6,.6,.6],[.8,.2,.3]])
        b,m=convert_rgba(a,BLACK,PQ)
        expected=np.array([[pq_decimal(v,inverse=True) for v in scalar(rgb)] for rgb in a[0,:,:3]])
        np.testing.assert_allclose(b[0,:,:3],expected,rtol=0,atol=3e-8)
        self.assertIsNone(m['HLG_black_level']['target']);self.assertFalse(m['HLG_black_level']['black_luminance_inferred'])
    def test_below_black_output_requires_reject_or_explicit_counted_clip(self):
        a=surface([[0,0,0]])
        with self.assertRaises(AppError):convert_rgba(a,WORK,BLACK)
        b,m=convert_rgba(a,WORK,BLACK,hdr_range_policy='clip')
        self.assertTrue(np.all(b[...,:3]==0));self.assertEqual(m['hdr_output_components_clipped'],3)
        self.assertEqual(m['HLG_black_level']['below_black_output_policy'],'clip')
        self.assertEqual(a[...,3].tobytes(),b[...,3].tobytes())
    def test_nominal_input_domain_is_checked_even_for_identical_signals(self):
        a=surface([[-.1,.5,1.1]]);before=a.tobytes()
        with self.assertRaises(AppError):convert_rgba(a,BLACK,BLACK)
        b,m=convert_rgba(a,BLACK,BLACK,hdr_input_range_policy='clip')
        np.testing.assert_array_equal(b[0,0,:3],[0,.5,1]);self.assertEqual(m['hdr_input_components_clipped'],2)
        self.assertEqual(before,a.tobytes());self.assertFalse(m['same_signal_byte_exact'])
    def test_tiles_are_byte_identical_and_cancel_budget_preserve_caller(self):
        a=np.random.default_rng(712).uniform(.01,.97,(13,17,4)).astype(np.float32);before=a.tobytes()
        results=[convert_rgba(a,BLACK,PQ,tile_pixels=n)[0].tobytes() for n in (1,7,257,65536)]
        self.assertEqual(len(set(results)),1)
        with self.assertRaises(AppError):convert_rgba(a,BLACK,PQ,max_working_bytes=1)
        calls=[]
        def cancel():
            calls.append(1)
            if len(calls)==4:raise AppError('CANCELLED','actual HLG black tile cancellation')
        with self.assertRaises(AppError):convert_rgba(a,BLACK,PQ,tile_pixels=7,cancel=cancel)
        self.assertEqual(before,a.tobytes())
    def test_invalid_black_values_degenerate_beta_and_wrong_transfer_are_rejected(self):
        for black in (-1,10.1,True,None,'0.005',float('nan'),float('inf')):
            with self.assertRaises(AppError):parse_signal(BASE|dict(display_black_nits=black))
        with self.assertRaises(AppError):parse_signal(BASE|dict(display_peak_nits=100,system_gamma=3,display_black_nits=10))
        for transfer in ('linear','pq-st2084','srgb'):
            with self.assertRaises(AppError):parse_signal(dict(primaries='bt2020',transfer=transfer,reference_white_nits=203,display_black_nits=0))
        with self.assertRaises(AppError):parse_signal({k:v for k,v in BASE.items() if k!='reference_white_nits'}|dict(display_black_nits=.005))
    def test_explicit_D65_is_equivalent_but_nonD65_HLG_is_rejected(self):
        signal=parse_signal(BASE|dict(display_black_nits=.005,white_xy=[.3127,.329]));self.assertTrue(equivalent(signal,BLACK))
        a=surface([[.1,.4,.8]]);b,m=convert_rgba(a,signal,BLACK);self.assertEqual(a.tobytes(),b.tobytes())
        with self.assertRaises(AppError):parse_signal(BASE|dict(display_black_nits=.005,white_xy=[.3457,.3585]))
    def test_schema_requires_HLG_context_and_numeric_black(self):
        validator=make_validator();v=validator.evolve(schema=validator.schema['$defs']['nativeFloatSignal'])
        self.assertEqual(list(v.iter_errors(BASE|dict(display_black_nits=.005))),[])
        for value in (BASE|dict(display_black_nits=True),BASE|dict(display_black_nits=11),BASE|dict(transfer='pq-st2084',display_black_nits=0),{k:x for k,x in BASE.items() if k!='display_peak_nits'}|dict(display_black_nits=.005)):
            self.assertTrue(list(v.iter_errors(value)))

class HLGBlackIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.parent=hdr_reference.HDRIntegrationTests('runTest');self.parent.setUp();self.addCleanup(self.parent.doCleanups);self.f=self.parent.f
    def pcm(self,path):
        return self.f.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
    def test_actual_HLG_black_source_to_PQ_all_encoded_pixels_VUI_and_PCM(self):
        f=self.f;source=self.parent.source(BLACK);r=f.execute('black-to-pq.mkv');y=f.decode_y(r['path'],32,16)
        expected=np.array([pq_decimal(scalar([v]*3)[0],inverse=True) for v in source[...,0].flat]).reshape(8,16,32)
        maximum=float(np.max(np.abs(y[:,0]-(64+876*expected))));self.assertLess(maximum,1.6)
        video=next(v for v in probe_media(Path(r['path']))['streams'] if v.get('codec_type')=='video')
        self.assertEqual(video['color_transfer'],'smpte2084');self.assertEqual(video['color_primaries'],'bt2020')
        self.assertEqual(self.pcm(r['path']),self.parent.samples[:38400].tobytes())
        boundary=r['delivery']['pixel_pipeline']['source_receipts']['picture']['color_boundary']['HLG_black_level']
        self.assertEqual(boundary['source']['display_black_nits'],.005);f.assert_clean()
        RECEIPTS.append(dict(test=self.id(),maximum_luma_code_error=maximum,all_encoded_pixels=8*16*32,result=r))
    def test_actual_PQ_to_HLG_black_output_counts_unrepresentable_black_and_VUI(self):
        f=self.f;self.parent.configure(BLACK);source=self.parent.source(PQ)
        f.p['settings']['pixel_pipeline']['range_policy']='clip';r=f.execute('pq-to-black.mkv');y=f.decode_y(r['path'],32,16)
        expected=np.array([np.clip(scalar([pq_decimal(v)]*3,inverse=True)[0],0,1) for v in source[...,0].flat]).reshape(8,16,32)
        maximum=float(np.max(np.abs(y[:,0]-(64+876*expected))));self.assertLess(maximum,1.6)
        video=next(v for v in probe_media(Path(r['path']))['streams'] if v.get('codec_type')=='video');self.assertEqual(video['color_transfer'],'arib-std-b67')
        self.assertEqual(r['delivery']['pixel_pipeline']['output_signal']['display_black_nits'],.005)
        self.assertEqual(self.pcm(r['path']),self.parent.samples[:38400].tobytes());f.assert_clean()
        RECEIPTS.append(dict(test=self.id(),maximum_luma_code_error=maximum,result=r))
    def test_raw_native_clock_bundle_keeps_black_interpretation_and_pixels(self):
        from ai_ad_editor import float_bundle
        f=self.f;source=self.parent.source(BLACK);output=f.root/'renders/black-surface'
        plan=float_bundle.prepare(f.root,f.p,'picture',output,source_signal=BLACK,target_signal=WORK,stop_frame=2)
        result=float_bundle.export_bundle(f.root,plan);manifest=json.loads((output/'bundle.json').read_bytes())
        actual=np.fromfile(output/'frames.rgba-f32le','<f4').reshape(2,16,32,4)
        expected=np.array([scalar(v) for v in source[:2,...,:3].reshape(-1,3)]).reshape(2,16,32,3)/203
        maximum=float(np.max(np.abs(actual[...,:3]-expected)));self.assertLess(maximum,2e-7)
        np.testing.assert_array_equal(actual[...,3],source[:2,...,3]);self.assertEqual(manifest['colour_boundary']['HLG_black_level']['source']['display_black_nits'],.005)
        clock=np.fromfile(output/'clock.i64le','<i8').reshape(2,3);np.testing.assert_array_equal(clock[:,0],[0,1]);self.assertTrue(np.all(clock[:,2]>0))
        self.assertEqual(result['frames'],2);f.assert_clean();RECEIPTS.append(dict(test=self.id(),maximum_error=maximum,manifest=manifest))
    def test_CLI_complete_signal_JSON_exports_actual_HDR_pixels(self):
        f=self.f;source=self.parent.source(BLACK)
        source_json=f.root/'source-signal.json';working_json=f.root/'working-signal.json'
        source_json.write_text(json.dumps(vars(BLACK)),encoding='utf8')
        working_json.write_text(json.dumps(vars(WORK)),encoding='utf8')
        before=(f.root/'project.json').read_bytes();output=f.root/'renders/cli-black'
        code,v=f.invoke('surface','export','--project',f.root,'--asset-id','picture','--output',output,
            '--source-signal-json',source_json,'--working-signal-json',working_json,'--stop-frame','2')
        self.assertEqual(code,0,v)
        actual=np.fromfile(output/'frames.rgba-f32le','<f4').reshape(2,16,32,4)
        expected=np.array([scalar(v) for v in source[:2,...,:3].reshape(-1,3)]).reshape(2,16,32,3)/203
        maximum=float(np.max(np.abs(actual[...,:3]-expected)));self.assertLess(maximum,2e-7)
        np.testing.assert_array_equal(actual[...,3],source[:2,...,3])
        self.assertEqual(before,(f.root/'project.json').read_bytes());f.assert_clean()
        RECEIPTS.append(dict(test=self.id(),maximum_error=maximum,all_pixels=1024,result=v))
    def test_CLI_signal_JSON_rejects_mixed_and_incomplete_context_before_publication(self):
        f=self.f;self.parent.source(BLACK)
        source_json=f.root/'source-signal.json';working_json=f.root/'working-signal.json'
        source_json.write_text(json.dumps(vars(BLACK)),encoding='utf8')
        working_json.write_text(json.dumps(vars(WORK)),encoding='utf8')
        output=f.root/'renders/invalid-cli-black'
        args=('surface','export','--project',f.root,'--asset-id','picture','--output',output,
            '--source-signal-json',source_json,'--working-signal-json',working_json)
        for extra in (('--source-transfer','linear'),('--working-transfer','linear')):
            code,v=f.invoke(*args,*extra);self.assertNotEqual(code,0,v);self.assertFalse(output.exists())
        working_json.write_text(json.dumps(dict(primaries='bt2020',transfer='linear')),encoding='utf8')
        code,v=f.invoke(*args);self.assertNotEqual(code,0,v);self.assertFalse(output.exists());f.assert_clean()
    def test_previews_and_portable_package_keep_black_signals_all_video_and_PCM(self):
        f=self.f;self.parent.source(BLACK);first=f.execute('before.mkv');before=(f.root/'project.json').read_bytes()
        for command in (('preview','frame','--project',f.root,'--frame','2','--height','64'),('preview','range','--project',f.root,'--start-frame','0','--end-frame','3','--height','64')):
            code,v=f.invoke(*command);self.assertEqual(code,0,v)
        self.assertEqual(before,(f.root/'project.json').read_bytes());archive=f.root/'exports/black.zip'
        code,v=f.invoke('convert','export','--project',f.root,'--output',archive,'--target-format','package');self.assertEqual(code,0,v)
        restored=f.base/'restored-black';code,v=f.invoke('convert','import','--input',archive,'--output',restored);self.assertEqual(code,0,v)
        _,p=load_project(restored);self.assertEqual(p['settings']['pixel_pipeline'],f.p['settings']['pixel_pipeline'])
        with project_write_lock(restored):second=render_project(restored,p,p['sequences'][0],restored/'renders/after.mkv')
        self.assertEqual(f.decode_y(first['path'],32,16).tobytes(),f.decode_y(second['path'],32,16).tobytes())
        self.assertEqual(self.pcm(first['path']),self.pcm(second['path']));f.assert_clean()
        RECEIPTS.append(dict(test=self.id(),first=first,second=second))
    def test_invalid_black_context_is_rejected_before_movie_publication(self):
        f=self.f;self.parent.source(BLACK);spec=f.p['settings']['pixel_pipeline']['sources']['picture']
        spec['source_signal']=spec['source_signal']|dict(display_black_nits=11)
        output=f.root/'renders/keep.mkv';output.write_bytes(b'prior-good-movie')
        with self.assertRaises(AppError):f.execute('keep.mkv')
        self.assertEqual(output.read_bytes(),b'prior-good-movie');f.assert_clean()

if __name__=='__main__':unittest.main()
