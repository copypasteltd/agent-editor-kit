"""Published independent matrices, native encoded edits and owned GPU whites."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal,convert_rgba,_rgb_to_xyz
from ai_ad_editor.float_chromatic import (D50,D60,D65,WhitePointSignal,WhitePointLuminanceSignal,
    bradford_matrix,white_of,conversion,xyz_white)
from ai_ad_editor.float_hdr import LuminanceSignal,parse_signal
from ai_ad_editor.float_glow import compile_glow,apply_glow,luma_coefficients
from ai_ad_editor.float_gpu import FloatGPUSession
from ai_ad_editor.float_standard_render import configuration
from ai_ad_editor.render import output_settings,render_project
from ai_ad_editor.project import save_project,load_project,project_write_lock
from ai_ad_editor.schema_contract import make_validator
from ai_ad_editor.media import ffmpeg_path
from test_float_color_signal import XYZ,surface

RECEIPTS=[]
# Published CSS Color 4 matrices, not derived using product constants/solver.
CAT=np.array([[.955473421488075,-.02309845494876471,.06325924320057072],
    [-.0283697093338637,1.0099953980813041,.021041441191917323],
    [.012314014864481998,-.020507649298898964,1.330365926242124]],np.float64)
PROPHOTO=np.array([[.7977666449006423,.13518129740053308,.03134773412839220],
    [.2880748288194013,.711835234241873,.00008993693872564],[0,0,.8251046025104602]])
# Academy AP1 normalized primary matrix, independently tabulated to10 decimals.
AP1=np.array([[.6624541811,.1340042065,.1561876870],[.2722287168,.6740817658,.0536895174],
    [-.0055746495,.0040607335,1.0103391003]])


class ChromaticNumericTests(unittest.TestCase):
    def test_D50_to_D65_Bradford_matches_published_matrix(self):
        np.testing.assert_allclose(bradford_matrix(D50,D65),CAT,rtol=0,atol=9e-16)
        np.testing.assert_allclose(bradford_matrix(D65,D50)@CAT,np.eye(3),rtol=0,atol=9e-16)

    def test_ProPhoto_D50_and_ACES_AP1_D60_primary_matrices(self):
        np.testing.assert_allclose(_rgb_to_xyz('prophoto-rgb'),PROPHOTO,rtol=0,atol=8e-16)
        np.testing.assert_allclose(_rgb_to_xyz('aces-ap1'),AP1,rtol=0,atol=6e-11)
        self.assertEqual(white_of(ColorSignal('aces-ap1','linear')),D60)

    def test_ProPhoto_to_sRGB_matches_independent_matrix_and_scalar_transfer(self):
        source=surface([[.02,.3,.6],[-.03,.5,1.2],[.65,.2,.1]])
        result,receipt=convert_rgba(source,ColorSignal('prophoto-rgb','prophoto-rgb'),ColorSignal('bt709','linear'))
        linear=np.array([float(v)/16 if abs(float(v))<=1/32 else np.copysign(abs(float(v))**1.8,v)
            for v in source[...,:3].flat]).reshape(1,3,3)
        expected=np.einsum('ij,hwj->hwi',np.linalg.inv(XYZ['bt709'])@CAT@PROPHOTO,linear).astype(np.float32)
        np.testing.assert_array_equal(result[...,:3],expected)
        self.assertTrue(receipt['chromatic_adaptation']);self.assertEqual(receipt['chromatic_transform']['source_white_xy'],list(D50))

    def test_ProPhoto_piecewise_toe_signed_extension_and_inverse(self):
        a=surface([[-.04,-1/32,-.001],[0,1/32,.04],[.5,1,1.4]])
        b,_=convert_rgba(a,ColorSignal('prophoto-rgb','prophoto-rgb'),ColorSignal('prophoto-rgb','linear'))
        expected=np.where(np.abs(a[...,:3])<=1/32,a[...,:3].astype(float)/16,np.sign(a[...,:3])*np.abs(a[...,:3].astype(float))**1.8)
        np.testing.assert_array_equal(b[...,:3],expected.astype(np.float32))
        c,_=convert_rgba(b,ColorSignal('prophoto-rgb','linear'),ColorSignal('prophoto-rgb','prophoto-rgb'))
        np.testing.assert_allclose(c,a,rtol=0,atol=6e-8)

    def test_custom_D50_BT709_transforms_using_Bradford_in_XYZ(self):
        src=WhitePointSignal('bt709','linear',D50);target=ColorSignal('bt709','linear')
        a=surface([[.1,.4,.7],[1,0,0],[-.2,1.3,.4]])
        actual,m=convert_rgba(a,src,target)
        # Independent white-normalized matrix derives scales with an explicit inverse.
        columns=np.array([[.64/.33,.3/.6,.15/.06],[1,1,1],[(1-.64-.33)/.33,(1-.3-.6)/.6,(1-.15-.06)/.06]])
        white=np.array([.3457/.3585,1,(1-.3457-.3585)/.3585]);matrix=columns*(np.linalg.inv(columns)@white)
        expected=np.einsum('ij,hwj->hwi',np.linalg.inv(XYZ['bt709'])@CAT@matrix,a[...,:3].astype(float))
        np.testing.assert_allclose(actual[...,:3],expected,rtol=0,atol=8e-8)
        self.assertEqual(m['chromatic_transform']['method'],'Bradford')

    def test_adaptation_maps_equal_RGB_to_equal_RGB_across_all_reference_whites(self):
        neutral=surface([[0,0,0],[.18,.18,.18],[1,1,1],[3,3,3]])
        signals=[ColorSignal('bt709','linear'),ColorSignal('prophoto-rgb','linear'),ColorSignal('aces-ap1','linear'),WhitePointSignal('bt2020','linear',D50)]
        for src in signals:
            for dst in signals:
                value,_=convert_rgba(neutral,src,dst);np.testing.assert_allclose(value,neutral,rtol=0,atol=2e-7)

    def test_absolute_nit_scaling_and_chromatic_adaptation_are_both_applied(self):
        src=WhitePointLuminanceSignal('bt709','linear',100,white_xy=D50)
        dst=LuminanceSignal('bt2020','linear',200);a=surface([[1,1,1],[.2,.3,.4]])
        actual,m=convert_rgba(a,src,dst)
        relative,_=convert_rgba(a,WhitePointSignal('bt709','linear',D50),ColorSignal('bt2020','linear'))
        np.testing.assert_array_equal(actual[...,:3],relative[...,:3]/2)
        self.assertEqual(m['linear_unit_scale'],.5);self.assertTrue(m['absolute_nits_managed'])

    def test_explicit_equivalent_D65_is_bit_exact_and_keeps_signed_zero_alpha(self):
        a=surface([[.1,.4,.7],[1,0,0]]);a[0,0,3]=np.float32(-0.)
        a[0,1,3]=np.array([1],np.uint32).view(np.float32)[0]
        b,m=convert_rgba(a,WhitePointSignal('bt709','srgb',D65),ColorSignal('bt709','srgb'))
        self.assertEqual(a.tobytes(),b.tobytes());self.assertTrue(m['same_signal_byte_exact'])
        self.assertFalse(m['chromatic_adaptation'])

    def test_negative_and_superwhite_values_and_hidden_RGB_are_not_clipped(self):
        a=surface([[1,0,0],[-.2,2,.3]]);a[...,3]=0
        b,m=convert_rgba(a,ColorSignal('prophoto-rgb','linear'),ColorSignal('bt709','linear'))
        self.assertLess(float(np.min(b[...,:3])),0);self.assertGreater(float(np.max(b[...,:3])),1)
        self.assertEqual(a[...,3].tobytes(),b[...,3].tobytes());self.assertEqual(m['RGB_clipping'],'none')

    def test_custom_white_is_owned_immutable_and_JSON_roundtrips(self):
        white=[.3457,.3585];s=parse_signal(dict(primaries='bt709',transfer='linear',white_xy=white));white[0]=0
        self.assertEqual(s.white_xy,D50);self.assertEqual(parse_signal(json.loads(json.dumps(vars(s)))),s)
        n=parse_signal(dict(primaries='aces-ap1',transfer='linear',reference_white_nits=203,white_xy=list(D60)))
        self.assertIsInstance(n,WhitePointLuminanceSignal);self.assertEqual(parse_signal(json.loads(json.dumps(vars(n)))),n)

    def test_invalid_white_types_geometry_and_HDR_non_D65_are_rejected(self):
        for v in (None,[],[.3],[True,.3],[float('nan'),.3],[10**400,.3],[.9,.2],[.01,.01],[.3,0]):
            with self.subTest(v=v),self.assertRaises(AppError):WhitePointSignal('bt709','linear',v)
        for t in ('pq-st2084','hlg-bt2100'):
            kwargs=dict(primaries='bt2020',transfer=t,reference_white_nits=203,white_xy=list(D50))
            if t=='hlg-bt2100':kwargs.update(display_peak_nits=1000,system_gamma=1.2)
            with self.assertRaises(AppError):parse_signal(kwargs)

    def test_chunk_sizes_do_not_change_rounding_and_cancel_does_not_change_source(self):
        a=np.random.default_rng(211).uniform(-.3,1.3,(9,13,4)).astype(np.float32);a[...,3]=.5
        src=ColorSignal('prophoto-rgb','prophoto-rgb');dst=ColorSignal('bt709','srgb');before=a.tobytes()
        outputs=[convert_rgba(a,src,dst,tile_pixels=n)[0].tobytes() for n in (1,7,64,65536)]
        self.assertTrue(all(v==outputs[0] for v in outputs))
        count=[]
        def cancel():
            count.append(1)
            if len(count)>2:raise AppError('CANCELLED','test')
        with self.assertRaises(AppError):convert_rgba(a,src,dst,tile_pixels=7,cancel=cancel)
        self.assertEqual(a.tobytes(),before)

    def test_glow_threshold_luma_uses_declared_white(self):
        a=luma_coefficients('bt709');b=luma_coefficients('bt709',D50)
        self.assertGreater(max(abs(x-y) for x,y in zip(a,b)),.01)
        self.assertAlmostEqual(sum(b),1,places=14)
        np.testing.assert_allclose(luma_coefficients('aces-ap1'),AP1[1],rtol=0,atol=6e-11)


class ChromaticGPUTests(unittest.TestCase):
    def test_real_GPU_Bloom_Halation_match_CPU_for_D50_D60_and_custom_white(self):
        a=np.random.default_rng(413).uniform(-.1,2,(11,17,4)).astype(np.float32);a[...,3]=.7
        a[0,0,3]=-0.;a[0,1,3]=np.array([1],np.uint32).view(np.float32)[0];maximum=0.
        with tempfile.TemporaryDirectory() as folder:
            with FloatGPUSession(folder,{'projection_acceleration':{'mode':'require','device':'0.0'}},max_pixels=187) as gpu:
                signals=[ColorSignal('prophoto-rgb','linear'),ColorSignal('aces-ap1','linear'),WhitePointSignal('bt709','linear',D50)]
                for signal in signals:
                    for kind in ('bloom','halation'):
                        plan=compile_glow(dict(type=kind,parameters=dict(radius=1.25,threshold=.4,knee=.1)))
                        expected,_=apply_glow(a,plan,0,working_signal=signal)
                        actual,m=apply_glow(a,plan,0,working_signal=signal,gpu=gpu)
                        np.testing.assert_allclose(actual,expected,rtol=0,atol=3e-6)
                        self.assertEqual(actual[...,3].tobytes(),a[...,3].tobytes());self.assertTrue(m['GPU'])
                        maximum=max(maximum,float(np.max(np.abs(actual-expected))))
                self.assertEqual(gpu.evidence['operations']['glow'],6)
            self.assertTrue(gpu.evidence['worker_closed']);self.assertTrue(gpu.evidence['shared_handles_closed'])
            self.assertTrue(gpu.evidence['control']['threads_closed']);self.assertTrue(gpu.evidence['control']['streams_closed'])
            RECEIPTS.append(dict(test=self.id(),maximum_error=maximum,GPU=gpu.evidence))


class ChromaticIntegrationTests(unittest.TestCase):
    def setUp(self):
        from test_float_standard_render import FloatStandardRenderTests
        self.f=FloatStandardRenderTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f;f.s['duration_tick']=72000
        a=np.ones((8,16,32,4),np.float32);a[...,:3]=np.array([.35,.4,.45],np.float32)
        f.visual(a);f.p['settings']['pixel_pipeline']['sources']['picture']['source_signal']=dict(primaries='prophoto-rgb',transfer='prophoto-rgb')
        f.p['settings']['pixel_pipeline']['working_signal']=dict(primaries='aces-ap1',transfer='linear',white_xy=list(D60))

    def test_actual_encoded_ProPhoto_D50_to_D60_edit_to_D65_matches_independent_oracle(self):
        r=self.f.execute();y=self.f.decode_y(r['path'],32,16)
        v=np.rint(np.array([.35,.4,.45],np.float32).astype(float)*65535)/65535
        rgb=np.linalg.inv(XYZ['bt709'])@CAT@PROPHOTO@(v**1.8)
        expected=64+876*(rgb@np.array([.2126,.7152,.0722]))
        self.assertLess(abs(float(y[:,0].mean())-expected),1.6)
        source=r['delivery']['pixel_pipeline']['source_receipts']['picture']
        self.assertEqual(source['working_signal']['white_xy'],list(D60))
        RECEIPTS.append(dict(test=self.id(),expected_luma=expected,actual_luma=float(y[:,0].mean()),result=r));self.f.assert_clean()

    def test_custom_white_effect_signals_use_common_conversion(self):
        f=self.f;f.s['tracks'][0]['clips'][0]['effects']=[dict(type='curves',parameters=dict(
            input_signal=dict(primaries='bt709',transfer='linear',white_xy=list(D50)),
            output_signal=dict(primaries='bt709',transfer='linear',white_xy=list(D50)),
            all='0/0 1/1',intensity=1))]
        baseline=f.execute('baseline.mkv');self.assertEqual(baseline['status'],'succeeded')
        RECEIPTS.append(dict(test=self.id(),result=baseline));f.assert_clean()

    def test_schema_and_rejected_output_white_preserve_author_project(self):
        f=self.f;save_project(f.root,f.p);self.assertEqual(list(make_validator().iter_errors(f.p)),[])
        before=(f.root/'project.json').read_bytes();code,value=f.invoke('validate','--project',f.root);self.assertEqual(code,0,value)
        bad=copy.deepcopy(f.p['settings']);bad['pixel_pipeline']['output_signal']['white_xy']=list(D50)
        with self.assertRaises(AppError) as c:configuration(bad['pixel_pipeline'],bad,output_settings(bad))
        self.assertEqual(c.exception.code,'FLOAT_RENDER_OUTPUT_WHITE')
        bad=copy.deepcopy(f.p);bad['settings']['pixel_pipeline']['working_signal']['white_xy']=[True,.3]
        self.assertTrue(list(make_validator().iter_errors(bad)));self.assertEqual(before,(f.root/'project.json').read_bytes())

    def test_actual_SDR_previews_keep_author_signals_and_timebase(self):
        f=self.f;save_project(f.root,f.p);before=(f.root/'project.json').read_bytes()
        code,v=f.invoke('preview','range','--project',f.root,'--start-frame','0','--end-frame','3','--height','64')
        self.assertEqual(code,0,v);self.assertEqual(v['data']['verified_clock']['decoded_video_frames'],3)
        self.assertEqual(before,(f.root/'project.json').read_bytes());RECEIPTS.append(dict(test=self.id(),result=v['data']));f.assert_clean()

    def test_editable_package_preserves_white_signals_complete_decoded_picture_and_PCM(self):
        f=self.f;f.audio();first=f.execute('before.mkv');archive=f.root/'exports/color.zip'
        code,v=f.invoke('convert','export','--project',f.root,'--output',archive,'--target-format','package');self.assertEqual(code,0,v)
        restored=f.base/'restored';code,v=f.invoke('convert','import','--input',archive,'--output',restored);self.assertEqual(code,0,v)
        _,p=load_project(restored);self.assertEqual(p['settings']['pixel_pipeline'],f.p['settings']['pixel_pipeline'])
        with project_write_lock(restored):second=render_project(restored,p,p['sequences'][0],restored/'renders/after.mkv')
        self.assertEqual(f.decode_y(first['path'],32,16).tobytes(),f.decode_y(second['path'],32,16).tobytes())
        def pcm(path):return f.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        self.assertEqual(pcm(first['path']),pcm(second['path']));RECEIPTS.append(dict(test=self.id(),first=first,second=second));f.assert_clean()

if __name__=='__main__':unittest.main()
