"""Independent sample-clock, DSP, recipe integrity and failure-boundary tests.

Identity stubs below test transport/OLA, not neural quality. Actual installed
CUDA inference and natural/synthetic speech cases are recorded separately.
"""
import copy,contextlib,io,json,math,os,struct,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from ai_ad_editor import enhancement_plan as planning,local_enhancement as local
from ai_ad_editor.enhancement_dsp import analysis,synthesis,features,process_pcm,window
from ai_ad_editor.enhancement_pipeline import execute,validate_response
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.job_workspaces import managed_workspace
from ai_ad_editor.project import create_project
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.media import ffmpeg_path,probe_media
from ai_ad_editor.utils import sha256_file
from ai_ad_editor import native_audio_clock as clock

def invoke(*argv):
    f=io.StringIO()
    with contextlib.redirect_stdout(f):code=main(list(map(str,argv)))
    return code,json.loads(f.getvalue())

class FrontendTests(unittest.TestCase):
    def test_unity_spectrum_roundtrip_native_tail_and_impulses(self):
        rng=np.random.default_rng(123)
        for count in (1,479,480,481,961,48013):
            for c in (1,2):
                x=rng.normal(0,.1,(c,count)).astype('float32');y=synthesis(analysis(x),count)
                self.assertEqual(y.shape,x.shape);self.assertLess(float(np.abs(y-x).max()),1e-7)
    def test_window_has_unit_overlap_power(self):
        w=window();self.assertLess(float(np.abs(w[:480]**2+w[480:]**2-1).max()),2e-7)
    def test_independent_stereo_channels_without_downmix(self):
        x=np.zeros((2,481),np.float32);x[0,100]=.5;x[1,333]=-.25
        y=synthesis(analysis(x),481);np.testing.assert_allclose(y,x,atol=1e-7)
        self.assertGreater(abs(y[0,100]),.49);self.assertEqual(y[1,100],0)
    def test_frontend_rejects_nonfinite_and_unsupported_input(self):
        for x in (np.zeros((1,0),np.float32),np.zeros((3,10),np.float32),np.ones((1,5),np.float64),np.full((1,20),np.nan,np.float32)):
            with self.assertRaises(ValueError):analysis(x)
    def test_erb_feature_initial_state_and_causal_update(self):
        bank=np.zeros((481,32),np.float32);bank[:32]=np.eye(32,dtype=np.float32)
        spec=np.full((1,2,481),1+.5j,np.complex64);erb,low=features(spec,bank)
        db=np.float32(10)*np.log10(np.float32(1.25)+np.float32(1e-10));a=np.float32(.99)
        initial=np.linspace(-60,-90,32,dtype=np.float32);mean=db*(np.float32(1)-a)+initial*a
        np.testing.assert_allclose(erb[0,0,0],(db-mean)/40,atol=2e-7)
        unit=np.linspace(.001,.0001,96,dtype=np.float32)*a+np.float32(abs(1+.5j))*(np.float32(1)-a)
        np.testing.assert_allclose(low[0,0,0,:,0],1/np.sqrt(unit),atol=2e-5)
    def test_feature_channels_have_no_shared_normalization_state(self):
        bank=np.ones((481,32),np.float32)/481
        x=np.stack((np.full((3,481),.01+.02j,np.complex64),np.full((3,481),.3+.4j,np.complex64)))
        a,b=features(x,bank);c,d=features(x[1:],bank)
        np.testing.assert_array_equal(a[1:],c);np.testing.assert_array_equal(b[1:],d)

class OLATests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
    def run_pcm(self,x,infer=lambda x:x,**kw):
        src=self.base/'input.f32';out=self.base/'output.f32';src.write_bytes(x.astype('<f4').tobytes())
        opts=dict(channels=x.shape[1],segment_seconds=1.,overlap=.5,strength=1.,attenuation_limit_db=None,infer=infer);opts.update(kw)
        report=process_pcm(src,out,**opts);return np.fromfile(out,dtype='<f4').reshape(x.shape),report
    def test_all_OLA_samples_covered_and_last_partial_segment_preserved(self):
        x=np.random.default_rng(2).normal(0,.1,(100017,2)).astype(np.float32);y,r=self.run_pcm(x)
        np.testing.assert_allclose(y,x,atol=5e-8);self.assertGreater(r['model_calls'],1);self.assertEqual(r['samples'],len(x))
    def test_strength_zero_is_every_bit_exact_including_negative_zero(self):
        x=np.random.default_rng(3).normal(0,.1,(50013,2)).astype(np.float32);x[10]=-0.
        y,r=self.run_pcm(x,infer=lambda _:self.fail('bypass must not call model'),strength=0.)
        self.assertEqual(x.tobytes(),y.tobytes());self.assertEqual(r['model_calls'],0)
    def test_full_silence_does_not_fake_forward(self):
        x=np.zeros((1000,1),np.float32);y,r=self.run_pcm(x,infer=lambda _:self.fail('silence must not call model'))
        self.assertEqual(x.tobytes(),y.tobytes());self.assertEqual(r['model_calls'],0)
    def test_strength_and_attenuation_mix_have_independent_expected_values(self):
        x=np.full((500,1),.4,np.float32);y,_=self.run_pcm(x,infer=lambda x:np.zeros_like(x),strength=.5,attenuation_limit_db=20.)
        np.testing.assert_allclose(y,.22,atol=2e-8)
    def test_bad_model_shape_removes_only_owned_outputs(self):
        x=np.ones((1000,1),np.float32)
        with self.assertRaisesRegex(ValueError,'MODEL_OUTPUT'):self.run_pcm(x,infer=lambda x:x[:,:-1])
        self.assertFalse((self.base/'output.f32').exists());self.assertFalse((self.base/'output.weights.f32').exists());self.assertTrue((self.base/'input.f32').exists())
    def test_nonfinite_estimate_rejected(self):
        with self.assertRaises(ValueError):self.run_pcm(np.ones((500,1),np.float32),infer=lambda x:x*np.nan)
    def test_existing_output_preserved(self):
        p=self.base/'output.f32';p.write_bytes(b'preserve')
        with self.assertRaises(ValueError):self.run_pcm(np.ones((500,1),np.float32))
        self.assertEqual(p.read_bytes(),b'preserve')
    def test_cancellation_cleans_owned_PCM(self):
        def stop():raise RuntimeError('cancel fixture')
        with self.assertRaises(RuntimeError):self.run_pcm(np.ones((500,1),np.float32),check=stop)
        self.assertFalse((self.base/'output.f32').exists())
    def test_malformed_PCM_and_channels_rejected(self):
        src=self.base/'bad.f32';src.write_bytes(b'abc')
        with self.assertRaises(ValueError):process_pcm(src,self.base/'out',channels=1,segment_seconds=1,overlap=0,strength=1,attenuation_limit_db=None,infer=lambda x:x)
        with self.assertRaises(ValueError):process_pcm(src,self.base/'out',channels=3,segment_seconds=1,overlap=0,strength=1,attenuation_limit_db=None,infer=lambda x:x)

def fixture_recipe():
    source=dict(asset_id='source',sha256='sha256:'+'1'*64)
    adapter=dict(model_sha256='sha256:'+'2'*64,settings=local.settings())
    r=dict(start_sample=441,end_sample=88244,samples=87803,sample_rate=44100)
    recipe=planning.recipe(source,adapter,r,channels=2,selection_=planning.selection(start_seconds=.01,end_seconds=88244/44100),options_=local.options(strength=.75))
    asset=dict(id='enhanced',kind='audio',source=dict(derived_from=['source'],speech_enhancement=recipe),probe=dict(streams=[dict(codec_type='audio',codec_name='pcm_f32le',sample_rate=44100,channels=2,time_base='1/44100',duration_ts=87803)]))
    return recipe,asset,{'source':dict(id='source',kind='audio',sha256=source['sha256'])}

class RecipeTests(unittest.TestCase):
    def test_native_nearest_sample_rounding(self):
        r=planning.sample_range(planning.selection(start_seconds=.01,end_seconds=.123),44100,44100)
        self.assertEqual(r,dict(start_sample=441,end_sample=5424,samples=4983,sample_rate=44100))
    def test_out_of_source_selection_rejected(self):
        for s in (dict(start_seconds=2,end_seconds=None),dict(start_seconds=0,end_seconds=2)):
            with self.assertRaises(AppError):planning.sample_range(s,48000,48000)
    def test_nonfinite_and_boolean_settings_rejected(self):
        for kwargs in (dict(threads=True),dict(segment_seconds=float('inf')),dict(overlap=1.)):
            with self.assertRaises(AppError):local.settings(**kwargs)
        for kwargs in (dict(strength=float('nan')),dict(strength=True),dict(attenuation_limit_db=-1)):
            with self.assertRaises(AppError):local.options(**kwargs)
    def test_recipe_has_no_runtime_absolute_paths(self):
        r,a,assets=fixture_recipe();self.assertIs(planning.validate_recipe(r,asset=a,assets=assets),r);self.assertNotIn('path',json.dumps(r))
    def test_recipe_tamper_digest_and_source_hash_rejected(self):
        r,a,assets=fixture_recipe();r['options']['strength']=.2
        with self.assertRaises(AppError):planning.validate_recipe(r,asset=a,assets=assets)
        r['sha256']=planning.digest(r);assets['source']['sha256']='sha256:'+'3'*64
        with self.assertRaises(AppError):planning.validate_recipe(r,asset=a,assets=assets)
    def test_wrong_encoded_native_clock_rejected(self):
        r,a,assets=fixture_recipe();a['probe']['streams'][0]['duration_ts']-=1
        with self.assertRaises(AppError):planning.validate_recipe(r,asset=a,assets=assets)
    def test_rebinding_source_rehashes_recipe(self):
        r,a,assets=fixture_recipe();out=planning.rebind_recipe(r,mapping={'source':'imported_source'},asset=a,assets=assets)
        self.assertEqual(out['source_asset_id'],'imported_source');self.assertNotEqual(r['sha256'],out['sha256']);self.assertEqual(r['source_asset_id'],'source')

class NativeTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):configure_local_runtime()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.root=self.base/'project';create_project(self.root)
        self.src=self.base/'source.wav';self.native=os.environ.get('AI_AD_EDITOR_TEST_NATIVE_PYTHON',sys.executable)
        subprocess.run([ffmpeg_path(),'-nostdin','-v','error','-n','-f','lavfi','-i','sine=frequency=523:sample_rate=44100:duration=0.35','-ac','2','-c:a','pcm_f32le',str(self.src)],check=True,capture_output=True)
        self.source=dict(asset_id='source',path=str(self.src),sha256='sha256:'+sha256_file(self.src))
    def test_native_audio_gap_and_overlap_clock(self):
        rows=[0,4,0,8,4,0,10,4,0];stats=clock._positions(rows,dict(sample_rate=8000,channels=1,time_base='1/8000',origin='0',channel_layout='mono'))
        self.assertEqual(rows[2::3],[0,8,10]);self.assertEqual(stats['gap_samples'],4);self.assertEqual(stats['overlap_samples'],2);self.assertEqual(stats['logical_frames'],14)
    def test_cancel_before_worker_does_not_start_or_publish(self):
        marker=self.base/'cancel';marker.touch()
        with managed_workspace(self.root,'speech-enhancement') as job,patch('ai_ad_editor.enhancement_pipeline.subprocess.Popen') as launch:
            with self.assertRaises(AppError):execute(self.root,job,self.source,{'executable':self.native},selection=planning.selection(),options=local.options(strength=0),storage_budget_bytes=64*1024**2,timeout=5,cancel_file=marker,operation_id='cancel')
            launch.assert_not_called()
    def test_cli_missing_model_no_metadata_changes(self):
        code,data=invoke('media','ingest','--project',self.root,'--input',self.src,'--license-spdx','CC0-1.0');self.assertEqual(code,0)
        before=(self.root/'project.json').read_bytes();source=data['data']['asset']['id']
        code,data=invoke('audio','enhance','--project',self.root,'--adapter-id','missing','--source-asset-id',source,'--asset-id','out')
        self.assertNotEqual(code,0);self.assertEqual(before,(self.root/'project.json').read_bytes());self.assertFalse((self.root/'assets/derived/out.wav').exists())
    def test_cli_adapter_list_is_read_only(self):
        before=(self.root/'project.json').read_bytes();code,data=invoke('audio','enhancement-adapter','list','--project',self.root)
        self.assertEqual(code,0);self.assertEqual(before,(self.root/'project.json').read_bytes());self.assertEqual(data['data']['adapters'],[])
    def test_invalid_apply_and_storage_fail_before_mutation(self):
        before=(self.root/'project.json').read_bytes()
        for extra in (['--apply'],['--storage-budget-mib','1']):
            code,_=invoke('audio','enhance','--project',self.root,'--adapter-id','x','--asset-id','out',*extra);self.assertNotEqual(code,0)
        self.assertEqual(before,(self.root/'project.json').read_bytes())

if __name__=='__main__':unittest.main()
