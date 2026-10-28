"""Real CLI float bundles, exact native clocks, public signal and failure gates."""
import contextlib,copy,hashlib,io,json
from pathlib import Path
import subprocess,tempfile,unittest
from unittest.mock import patch
import numpy as np
from ai_ad_editor import cli,float_bundle
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import load_project

NATIVE_CALLS=[]
def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def invoke(*args):
    stdout=io.StringIO()
    with contextlib.redirect_stdout(stdout):code=cli.main(list(map(str,args)))
    value=json.loads(stdout.getvalue());NATIVE_CALLS.append({'kind':'actual-in-process-CLI','args':list(map(str,args)),
        'exit_code':code,'status':value['status'],'stdout_sha256':digest(stdout.getvalue().encode('utf8'))})
    if code==0 and args[:2]==('surface','export') and value['status']=='succeeded':
        manifest=json.loads(Path(value['data']['manifest']).read_bytes())
        NATIVE_CALLS.append({'kind':'actual-native-source-reader-CLI','command':manifest['source_reader']['command'],
            'exit_code':manifest['source_reader_process']['exit_code'],'owned_threads_terminated':manifest['source_reader_process']['owned_threads_terminated'],
            'decoded_frames':manifest['source_reader']['decoded_frames'],'manifest_sha256':value['data']['manifest_sha256']})
    return code,value

class FloatBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='bundle-originals-',dir=base);cls.sources=Path(cls.temp.name)
        rng=np.random.default_rng(7122);cls.codes=rng.integers(1,65536,(4,16,32,4),dtype=np.uint16);cls.codes[:,0,:,3]=0
        raw=cls.sources/'original.gbrap16le';raw.write_bytes(np.moveaxis(cls.codes[...,[1,2,0,3]],-1,1).astype('<u2').tobytes())
        cls.source=cls.sources/'original.nut'
        y=np.tile(np.arange(512,dtype=np.uint16).reshape(16,32)*128,(4,1,1));c=np.full_like(y,32768)
        cls.yuv_codes=y;yr=cls.sources/'original.yuv444p16le';yr.write_bytes(np.stack((y,c,c),1).astype('<u2').tobytes());cls.yuv=cls.sources/'original-yuv.nut'
        tags=['-color_range','pc','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709']
        for source,fmt,dest,extra in [(raw,'gbrap16le',cls.source,[]),(yr,'yuv444p16le',cls.yuv,tags)]:
            command=[ffmpeg_path(),'-v','error','-f','rawvideo','-pixel_format',fmt,'-video_size','32x16','-framerate','8',*extra,'-i',str(source),
                '-vf',"setpts='(if(eq(N,0),0,if(eq(N,1),1,if(eq(N,2),3,7)))/8+5)/TB'",'-fps_mode','passthrough',
                '-c:v','ffv1','-level','3',*extra,str(dest)]
            p=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            NATIVE_CALLS.append({'kind':'native-original-encode','command':command,'exit_code':p.returncode,'stderr_sha256':digest(p.stderr)})
            if p.returncode:raise RuntimeError(p.stderr.decode('utf8','replace'))
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp'
        self.temp_project=tempfile.TemporaryDirectory(prefix='bundle-project-',dir=base);self.addCleanup(self.temp_project.cleanup)
        self.base=Path(self.temp_project.name);self.root=self.base/'project'
        self.call('project','init',self.root)
        self.call('media','ingest','--project',self.root,'--input',self.source,'--asset-id','source')
        self.out=self.root/'renders/float-bundle'
        self.request=['surface','export','--project',self.root,'--asset-id','source','--output',self.out,
            '--source-primaries','bt709','--source-transfer','srgb','--working-transfer','srgb']
        self.project_bytes=(self.root/'project.json').read_bytes();self.rights_bytes=(self.root/'rights-ledger.json').read_bytes()

    def call(self,*args):
        code,value=invoke(*args);self.assertEqual(code,0,value);return value
    def metadata(self,path=None):return json.loads(((path or self.out)/'bundle.json').read_bytes())
    def frames(self,path=None):
        path=path or self.out;m=self.metadata(path)
        return np.fromfile(path/'frames.rgba-f32le',dtype='<f4').reshape(m['frames'],m['height'],m['width'],4)
    def plan(self,**kwargs):
        root,project=load_project(self.root)
        return float_bundle.prepare(root,project,'source',self.out,source_signal=ColorSignal('bt709','srgb'),target_signal=ColorSignal('bt709','srgb'),**kwargs)
    def assert_authored_unchanged(self):
        self.assertEqual((self.root/'project.json').read_bytes(),self.project_bytes)
        self.assertEqual((self.root/'rights-ledger.json').read_bytes(),self.rights_bytes)

    def test_dry_run_does_not_probe_decode_create_bundle_or_modify_authored_data(self):
        with (patch('ai_ad_editor.float_bundle.probe_frames',side_effect=AssertionError('dry run probed')),
             patch('ai_ad_editor.float_video_source.NativeRGBSource.__enter__',side_effect=AssertionError('dry run decoded'))):
            value=self.call(*self.request,'--dry-run')
        self.assertEqual(value['status'],'planned');self.assertFalse(self.out.exists());self.assert_authored_unchanged()

    def test_actual_RGB_CLI_bundle_keeps_every_native_code_alpha_and_VFR_clock(self):
        result=self.call(*self.request);m=self.metadata();actual=self.frames()
        np.testing.assert_array_equal(np.rint(actual.astype(np.float64)*65535).astype(np.uint16),self.codes)
        clock=np.fromfile(self.out/'clock.i64le','<i8').reshape(4,3)
        from fractions import Fraction
        self.assertEqual([int(v)*Fraction(m['native_time_base']) for v in clock[:,1]],list(map(Fraction,('5','5.125','5.375','5.875'))))
        self.assertEqual(clock[:,0].tolist(),[0,1,2,3]);self.assertTrue(m['all_source_frames_exported']);self.assertFalse(m['encoded_movie'])
        self.assertEqual(result['data']['manifest_sha256'],digest((self.out/'bundle.json').read_bytes()));self.assert_authored_unchanged()
        verified=self.call('surface','inspect','--project',self.root,'--input',self.out)
        self.assertEqual(verified['data']['status'],'verified');self.assertFalse(verified['data']['original_inputs_revalidated'])

    def test_selected_window_static_affine_and_clock_remain_editable_native_data(self):
        transform=self.base/'transform.json';transform.write_text(json.dumps({'width':16,'height':32,'inverse':[[0,1,0],[-1,0,15]]}),encoding='utf8')
        self.call(*self.request,'--start-frame',1,'--stop-frame',3,'--transform-json',transform)
        actual=self.frames();truth=np.stack([np.rot90(v,-1) for v in self.codes[1:3]]).astype(np.float32)/65535
        truth[...,:3][truth[...,3]==0]=0
        np.testing.assert_allclose(actual,truth,rtol=0,atol=6e-8)
        m=self.metadata();self.assertFalse(m['all_source_frames_exported']);self.assertEqual(m['source_reader']['requested_prefix_frame_count'],3)
        self.assertEqual(np.fromfile(self.out/'clock.i64le','<i8').reshape(2,3)[:,0].tolist(),[1,2]);self.assert_authored_unchanged()

    def test_real_CLI_srgb_to_linear_checks_all_channels_and_leaves_alpha_untouched(self):
        request=self.request.copy();request[request.index('--working-transfer')+1]='linear'
        self.call(*request,'--stop-frame',1)
        actual=self.frames();rgb=self.codes[:1,...,:3].astype(np.float64)/65535
        truth=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
        # Native integer normalization itself has a public Float32 boundary.
        rgb32=(self.codes[:1,...,:3].astype(np.float32)/65535).astype(np.float64)
        quantized_truth=np.where(rgb32<=.04045,rgb32/12.92,((rgb32+.055)/1.055)**2.4).astype(np.float32)
        np.testing.assert_array_equal(actual[...,:3],quantized_truth)
        np.testing.assert_array_equal(np.rint(actual[...,3].astype(np.float64)*65535).astype(np.uint16),self.codes[:1,...,3])
        self.assertLess(float(np.max(np.abs(actual[...,:3]-truth))),9e-8)

    def test_actual_YUV_CLI_requires_explicit_spec_and_keeps_neutral_sixteen_bit_codes(self):
        self.call('media','ingest','--project',self.root,'--input',self.yuv,'--asset-id','yuv')
        self.call('surface','export','--project',self.root,'--asset-id','yuv','--output',self.out,
            '--source-primaries','bt709','--source-transfer','bt709-oetf','--working-transfer','bt709-oetf','--pixel-family','yuv',
            '--yuv-matrix','bt709','--yuv-range','full','--chroma-location','center','--scan','progressive')
        actual=self.frames()
        for c in range(3):np.testing.assert_array_equal(np.rint(actual[...,c].astype(np.float64)*65535).astype(np.uint16),self.yuv_codes)
        self.assertTrue(np.all(actual[...,3]==1));self.assertFalse(self.metadata()['source_reader']['scan_automatically_verified'])

    def test_pixel_corruption_is_rejected_by_readonly_inspection(self):
        self.call(*self.request,'--stop-frame',1);path=self.out/'frames.rgba-f32le'
        with path.open('r+b') as stream:stream.seek(17);b=stream.read(1);stream.seek(17);stream.write(bytes([b[0]^1]))
        code,value=invoke('surface','inspect','--project',self.root,'--input',self.out)
        self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'FLOAT_BUNDLE_CORRUPT');self.assert_authored_unchanged()

    def test_clock_corruption_and_resigned_invalid_source_indexes_are_rejected(self):
        self.call(*self.request,'--stop-frame',2);path=self.out/'clock.i64le'
        values=np.fromfile(path,'<i8').reshape(2,3);values[1,0]=7;path.write_bytes(values.tobytes())
        code,value=invoke('surface','inspect','--project',self.root,'--input',self.out)
        self.assertEqual(value['errors'][0]['code'],'FLOAT_BUNDLE_CORRUPT');self.assertNotEqual(code,0)
        m=self.metadata();m['files']['clock']['sha256']=digest(path.read_bytes());(self.out/'bundle.json').write_text(json.dumps(m),encoding='utf8')
        code,value=invoke('surface','inspect','--project',self.root,'--input',self.out)
        self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'FLOAT_BUNDLE_INVALID')

    def test_preexisting_cancellation_returns_structured_error_and_no_bundle(self):
        marker=self.base/'cancel';marker.write_text('cancel',encoding='utf8')
        code,value=invoke(*self.request,'--cancel-file',marker)
        self.assertEqual(code,8);self.assertEqual(value['errors'][0]['code'],'CANCELLED');self.assertFalse(self.out.exists());self.assert_authored_unchanged()

    def test_cancel_during_real_export_cleans_owned_process_and_partial_bundle(self):
        plan=self.plan();marker=self.base/'cancel-after-one'
        def progress(done,total):
            if done==1:marker.write_text('cancel',encoding='utf8')
        with self.assertRaises(AppError) as caught:float_bundle.export_bundle(self.root,plan,cancel_file=marker,progress=progress)
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertFalse(self.out.exists())
        self.assertFalse(list(self.out.parent.glob('.float-bundle-*')));self.assert_authored_unchanged()

    def test_actual_source_change_between_plan_and_export_rejects_before_native_open(self):
        plan=self.plan();source=Path(plan['recipe']['source'])
        with source.open('ab') as stream:stream.write(b'actual-registered-source-change')
        with patch('ai_ad_editor.float_video_source.NativeRGBSource.__enter__',side_effect=AssertionError('changed source decoded')):
            with self.assertRaises(AppError) as caught:float_bundle.export_bundle(self.root,plan)
        self.assertEqual(caught.exception.code,'FLOAT_BUNDLE_INPUT_CHANGED');self.assertFalse(self.out.exists())

    def test_output_budget_rejects_before_pixel_decode_and_writes_no_partial_artifact(self):
        plan=self.plan(max_output_bytes=1)
        with patch('ai_ad_editor.float_video_source.NativeRGBSource.__enter__',side_effect=AssertionError('budget gate decoded')):
            with self.assertRaises(AppError) as caught:float_bundle.export_bundle(self.root,plan)
        self.assertEqual(caught.exception.code,'FLOAT_BUNDLE_BUDGET');self.assertFalse(self.out.exists());self.assert_authored_unchanged()

    def test_existing_output_is_never_overwritten_and_outside_paths_are_refused(self):
        self.out.mkdir(parents=True);existing=self.out/'keep';existing.write_bytes(b'existing-owned-output')
        code,value=invoke(*self.request);self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'FLOAT_BUNDLE_OUTPUT_EXISTS')
        self.assertEqual(existing.read_bytes(),b'existing-owned-output')
        root,project=load_project(self.root)
        with self.assertRaises(AppError):float_bundle.prepare(root,project,'source',self.base/'outside',source_signal=ColorSignal('bt709','srgb'),target_signal=ColorSignal('bt709','linear'))
        self.assert_authored_unchanged()

    def test_missing_YUV_spec_and_invalid_geometry_return_structured_errors(self):
        code,value=invoke(*self.request,'--pixel-family','yuv')
        self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'FLOAT_BUNDLE_COLOR')
        transform=self.base/'invalid-transform.json';transform.write_text(json.dumps({'width':16,'height':16,'inverse':[[0,0,0],[0,0,0]]}),encoding='utf8')
        code,value=invoke(*self.request,'--transform-json',transform)
        self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'FLOAT_BUNDLE_GEOMETRY');self.assertFalse(self.out.exists())

    def test_readonly_inspection_creates_no_operation_or_project_metadata_changes(self):
        self.call(*self.request,'--stop-frame',1)
        files={p.relative_to(self.root).as_posix():digest(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        self.call('surface','inspect','--project',self.root,'--input',self.out)
        after={p.relative_to(self.root).as_posix():digest(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(after,files);self.assert_authored_unchanged()

    def test_out_of_native_frame_range_rejects_before_decoder(self):
        plan=self.plan(start_frame=3,stop_frame=5)
        with patch('ai_ad_editor.float_video_source.NativeRGBSource.__enter__',side_effect=AssertionError('invalid window decoded')):
            with self.assertRaises(AppError) as caught:float_bundle.export_bundle(self.root,plan)
        self.assertEqual(caught.exception.code,'FLOAT_BUNDLE_RANGE');self.assertFalse(self.out.exists());self.assert_authored_unchanged()
