"""Independent clocks/pixels, real FFmpeg transport and transaction boundaries.

The tiny worker used here is synthetic, not neural quality evidence. Actual
installed RIFE CUDA execution and held-out media are separately recorded.
"""
import copy,hashlib,io,json,struct,subprocess,sys,tempfile,threading,time,unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch
import numpy as np
from ai_ad_editor import interpolation_plan as planning,local_interpolation as local
from ai_ad_editor.interpolation_clock import selected_clock,subdivision,duration_seconds,packet_filter,validate_clock
from ai_ad_editor.interpolation_frames import process_frames
from ai_ad_editor.interpolation_pipeline import execute,validate_response
from ai_ad_editor.errors import AppError
from ai_ad_editor.job_workspaces import managed_workspace
from ai_ad_editor.media import ffmpeg_path,probe_media
from ai_ad_editor.project import create_project
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import sha256_file
from ai_ad_editor.reverse_video_clock import probe_frames
import test_local_matting as fixture

def clock():return dict(time_base='1/1000',pts=[100,300,700,1100],durations=[200,400,400,300])

class ClockTests(unittest.TestCase):
    def test_native_VFR_all_anchor_times_and_durations(self):
        c=clock();o=subdivision(c,4)
        self.assertEqual(o['time_base'],'1/4000');self.assertEqual(o['pts'],[0,200,400,600,800,1200,1600,2000,2400,2800,3200,3600,4000,4300,4600,4900])
        self.assertEqual(o['durations'],[200]*4+[400]*8+[300]*4);self.assertEqual(duration_seconds(o),Fraction(13,10))
    def test_half_open_selection_uses_actual_next_point(self):
        c=clock();c['durations'][1]=1;s=selected_clock(c,1,3)
        self.assertEqual(s['pts'],[300,700]);self.assertEqual(s['durations'],[400,400]);self.assertEqual(duration_seconds(s),Fraction(4,5))
    def test_arbitrary_factors_preserve_every_source_anchor(self):
        c=clock()
        for factor in range(2,9):
            o=subdivision(c,factor);self.assertEqual(duration_seconds(o),duration_seconds(c))
            self.assertEqual([Fraction(o['pts'][i*factor])*Fraction(o['time_base']) for i in range(4)],[Fraction(p-100,1000) for p in c['pts']])
    def test_non_unit_timebase_numerator(self):
        c=dict(time_base='1001/30000',pts=[20,21,23],durations=[1,2,1]);o=subdivision(c,3)
        self.assertEqual(o['pts'],[0,1001,2002,3003,5005,7007,9009,10010,11011]);self.assertEqual(duration_seconds(o),Fraction(1001,7500))
    def test_missing_final_duration_rejected(self):
        c=clock();c['durations'][-1]=0
        with self.assertRaises(ValueError):subdivision(c,2)
    def test_nonmonotonic_pts_rejected(self):
        c=clock();c['pts'][2]=300
        with self.assertRaises(ValueError):validate_clock(c)
    def test_fractional_or_boolean_indices_rejected(self):
        for first in (True,.5,-1,4):
            with self.assertRaises(ValueError):selected_clock(clock(),first,None)
    def test_output_AVRational_overflow_rejected(self):
        c=clock();c['time_base']='1/2147483647'
        with self.assertRaises(ValueError):subdivision(c,2)
    def test_packet_expression_sets_PTS_DTS_and_every_duration(self):
        value=packet_filter(subdivision(clock(),3));self.assertIn('setts=ts=',value);self.assertIn(':duration=',value);self.assertTrue(value.endswith(':time_base=1/3000'))

class Model:
    def __init__(self):self.calls=[]
    def interpolate(self,a,b,queries):
        self.calls.append(list(queries))
        for k,f in queries:yield np.rint(a.astype(float)*(1-k/f)+b.astype(float)*k/f).astype(np.uint8)

class PixelTests(unittest.TestCase):
    def run_frames(self,images=None,model=None,options=None,source=None,sink=None,budget=512*1024**2):
        if images is None:
            images=np.zeros((3,48,64,4),np.uint8);images[:,:,:,:]=[10,20,30,0];images[1,:]=[80,90,100,127];images[2,:]=[140,150,160,255]
        output=sink or io.BytesIO();m=model or Model()
        result=process_frames(source or io.BytesIO(images.tobytes()),output,width=64,height=48,frames=len(images),factor=3,predictor=m,
            options=options or dict(scene_cut_threshold=None,cut_after_frame=[]),budget=budget)
        return np.frombuffer(output.getvalue(),np.uint8).reshape(-1,48,64,4),result,m
    def test_all_decoded_RGBA_anchors_and_hidden_RGB_unchanged(self):
        out,m,_=self.run_frames();self.assertEqual(out[0,0,0].tolist(),[10,20,30,0]);self.assertEqual(m['source_rgba_sha256'],m['anchor_rgba_sha256']);self.assertEqual(out[3,0,0].tolist(),[80,90,100,127]);self.assertEqual(m['generated_frames'],4)
    def test_arbitrary_times_and_final_interval_are_explicit(self):
        out,m,model=self.run_frames();self.assertEqual(model.calls,[[(1,3),(2,3)]]*2);self.assertTrue(np.array_equal(out[-3],out[-1]));self.assertEqual(m['held_inserted_frames'],2)
    def test_explicit_cut_never_calls_model_across_pair(self):
        out,m,model=self.run_frames(options=dict(scene_cut_threshold=None,cut_after_frame=[0]));self.assertEqual(len(model.calls),1);self.assertEqual(m['cut_after_frames'],[0]);self.assertTrue(np.array_equal(out[0],out[2]))
    def test_difference_cut_disabled_or_thresholded(self):
        _,m,model=self.run_frames(options=dict(scene_cut_threshold=.01,cut_after_frame=[]));self.assertEqual(m['cut_after_frames'],[0,1]);self.assertEqual(model.calls,[]);self.assertEqual(m['flow_forwards'],0)
    def test_identical_RGBA_pair_is_held_without_fake_forward(self):
        images=np.full((3,48,64,4),77,np.uint8);_,m,model=self.run_frames(images);self.assertEqual(model.calls,[]);self.assertEqual(m['static_pairs'],[0,1]);self.assertEqual(m['held_inserted_frames'],6)
    def test_partial_input_reads_and_output_writes(self):
        raw=np.full((3,48,64,4),77,np.uint8).tobytes()
        class Reader(io.BytesIO):
            def read(self,n=-1):return super().read(min(n,7))
        class Writer(io.BytesIO):
            def write(self,data):return super().write(data[:13])
        out,m,_=self.run_frames(source=Reader(raw),sink=Writer());self.assertEqual(out.shape[0],9)
    def test_truncated_input_rejected(self):
        with self.assertRaisesRegex(ValueError,'TRUNCATED'):self.run_frames(source=io.BytesIO(bytes(64*48*4*3-1)))
    def test_extra_source_frame_rejected(self):
        with self.assertRaisesRegex(ValueError,'EXTRA_FRAMES'):self.run_frames(source=io.BytesIO(bytes(64*48*4*4)))
    def test_missing_neural_frame_rejected(self):
        class Missing(Model):
            def interpolate(self,a,b,queries):return iter(())
        with self.assertRaisesRegex(ValueError,'MISSING_NEURAL'):self.run_frames(model=Missing())
    def test_invalid_neural_raster_rejected(self):
        class Wrong(Model):
            def interpolate(self,a,b,queries):yield np.zeros((1,1,4),np.uint8)
        with self.assertRaisesRegex(ValueError,'NEURAL_FRAME_CONTRACT'):self.run_frames(model=Wrong())
    def test_array_budget_rejects_before_output(self):
        sink=io.BytesIO()
        with self.assertRaisesRegex(ValueError,'ARRAY_BUDGET'):self.run_frames(sink=sink,budget=1)
        self.assertEqual(sink.getvalue(),b'')

FAKE_WORKER=r'''
import json,sys,time
from pathlib import Path
sys.path.insert(0,PACKAGE)
from ai_ad_editor.interpolation_frames import process_frames
from ai_ad_editor.utils import atomic_write_json
r=json.loads(Path(sys.argv[1]).read_bytes());v=r['video']
if MODE=='fail':raise RuntimeError('intentional protocol test failure')
if MODE=='wait':time.sleep(30)
import numpy as np
class Model:
 def interpolate(self,a,b,queries):
  for k,f in queries:yield np.rint(a.astype(float)*(1-k/f)+b.astype(float)*k/f).astype('uint8')
m=process_frames(sys.stdin.buffer,sys.stdout.buffer,width=v['width'],height=v['height'],frames=v['source_frames'],factor=v['factor'],predictor=Model(),options=r['options'],budget=r['adapter']['settings']['state_budget_bytes'])
execution=dict(engine=r['engine'],model_loads=1,CPU_fallback=False,network='disabled',weight_reader='safetensors-pread',precision='float32',cuda_peak_allocated_bytes=1,scale=r['adapter']['settings']['scale'],padding='replicate',alpha_transport='same-flow-mask-premultiplied-RGBA',flow_forwards=m['flow_forwards'],generated_frames=m['generated_frames'],time_queries=m['time_queries'])
out=dict(status='succeeded',engine=r['engine'],protocol=r['protocol'],network='disabled',blocked_network_events=[],request_sha256=r['request_sha256'],adapter_sha256=r['adapter']['sha256'],source_sha256=r['source']['sha256'],providers=['torch-cuda'],model_loaded=True,metrics=m,model_execution=execution)
if MODE=='bad':out['metrics']['anchor_rgba_sha256']='sha256:'+'0'*64
atomic_write_json(Path(r['response']),out)
'''

class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):configure_local_runtime()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.root=self.base/'project';create_project(self.root)
        self.video=self.base/'input.mov';c=clock();c['pts']=[p-100 for p in c['pts']];self.expression=self.base/'clock.txt';self.expression.write_text(packet_filter(c),encoding='ascii')
        silent=self.base/'silent.mov'
        subprocess.run([ffmpeg_path(),'-v','error','-f','lavfi','-i','testsrc=size=64x48:rate=10','-frames:v','4','-c:v','qtrle','-pix_fmt','argb','-fps_mode','passthrough','-enc_time_base','1/1000','-/bsf:v',str(self.expression),'-video_track_timescale','1000',str(silent)],capture_output=True,check=True)
        subprocess.run([ffmpeg_path(),'-v','error','-i',str(silent),'-f','lavfi','-i','sine=frequency=443:sample_rate=44100:duration=1.3','-map','0:v','-map','1:a','-c:v','copy','-c:a','pcm_f32le','-video_track_timescale','1000',str(self.video)],capture_output=True,check=True)
        probe=probe_media(self.video);self.source=dict(asset_id='source',kind='video',path=str(self.video),sha256='sha256:'+sha256_file(self.video),probe=probe,stream_index=0)
        self.adapter=dict(adapter_id='test',engine=local.ENGINE,protocol=local.PROTOCOL,settings=local.settings(),sha256='sha256:'+'0'*64,executable=sys.executable)
        points,durations,stream,_=probe_frames(self.video);self.clock=dict(time_base=stream['time_base'],pts=list(points),durations=list(durations))
        self.plan=planning.configuration(self.source,self.clock,settings=self.adapter['settings'],factor=3,scene_cut_threshold=None);self.worker=self.base/'worker.py'
    def worker_patch(self,mode='ok'):
        self.worker.write_text('PACKAGE='+repr(str(Path(local.__file__).resolve().parent.parent))+'\nimport sys;sys.path.insert(0,'+repr(str(Path(np.__file__).resolve().parent.parent))+')\nMODE='+repr(mode)+'\n'+FAKE_WORKER,encoding='utf8');actual=subprocess.Popen
        def start(command,*args,**kwargs):
            if any(str(v).endswith('interpolation_worker.py') for v in command):command=[sys.executable,'-I','-B',str(self.worker),command[-1]]
            return actual(command,*args,**kwargs)
        return patch('ai_ad_editor.interpolation_pipeline.subprocess.Popen',side_effect=start)
    def execute(self,mode='ok',timeout=60,marker=None):
        with managed_workspace(self.root,'frame-interpolation') as job,patch('ai_ad_editor.interpolation_pipeline.verify_adapter',return_value={'ok':True}),self.worker_patch(mode):
            return execute(self.root,job,self.plan,self.source,self.adapter,timeout=timeout,cancel_file=marker)
    def test_real_VFR_qtrle_all_PTS_durations_original_anchors_and_PCM(self):
        stage,result=self.execute();self.assertTrue(result['all_native_PTS_and_durations_verified']);self.assertTrue(result['all_original_anchors_roundtrip_verified']);self.assertTrue(result['complete_PCM_roundtrip_verified']);self.assertFalse(stage.exists())
        self.assertTrue(all(p['exited'] and p['stdout_closed'] for p in result['cleanup']['processes']));self.assertFalse(list((self.root/'cache/managed-jobs').glob('job-*')))
    def test_original_44100_sample_clock_and_source_selection(self):
        p=planning.configuration(self.source,self.clock,settings=self.adapter['settings'],factor=2,start_frame=1,end_frame=3)
        self.assertEqual(p['audio']['start_sample'],8820);self.assertEqual(p['audio']['end_sample'],44100);self.assertEqual(p['audio']['samples'],35280)
    def test_delayed_audio_has_explicit_leading_and_trailing_zeros(self):
        s=copy.deepcopy(self.source);a=next(s for s in s['probe']['streams'] if s['codec_type']=='audio');a.update(start_pts=8820,duration_ts=22050,time_base='1/44100')
        p=planning.configuration(s,self.clock,settings=self.adapter['settings']);self.assertEqual(p['audio']['leading_zero_samples'],8820);self.assertEqual(p['audio']['samples'],22050);self.assertEqual(p['audio']['trailing_zero_samples'],26460)
    def test_unknown_original_audio_duration_rejected(self):
        s=copy.deepcopy(self.source);a=next(s for s in s['probe']['streams'] if s['codec_type']=='audio');a.pop('duration_ts',None)
        with self.assertRaises(AppError):planning.configuration(s,self.clock,settings=self.adapter['settings'])
    def test_forged_anchor_report_rejected(self):
        with self.assertRaises(AppError) as caught:self.execute('bad')
        self.assertEqual(caught.exception.code,'INTERPOLATION_WORKER_CONTRACT')
    def test_worker_failure_diagnoses_and_recovers(self):
        with self.assertRaises(AppError) as caught:self.execute('fail')
        self.assertEqual(caught.exception.diagnostics['status'],'stored');self.assertFalse(list((self.root/'cache/managed-jobs').glob('job-*')))
    def test_timeout_reclaims_owned_children(self):
        started=time.monotonic()
        with self.assertRaises(AppError) as caught:self.execute('wait',timeout=2)
        self.assertEqual(caught.exception.code,'TIMEOUT');self.assertLess(time.monotonic()-started,15)
    def test_cancel_reclaims_owned_children(self):
        marker=self.base/'cancel';timer=threading.Timer(1,lambda:marker.write_text('cancel'));timer.start()
        try:
            with self.assertRaises(AppError) as caught:self.execute('wait',marker=marker)
            self.assertEqual(caught.exception.code,'CANCELLED')
        finally:timer.cancel();timer.join()
        self.assertFalse(list((self.root/'cache/managed-jobs').glob('job-*')))

class CLITests(unittest.TestCase):
    setUpClass=TransportTests.__dict__['setUpClass']
    def setUp(self):
        TransportTests.setUp(self);self.worker_patch=lambda mode='ok':TransportTests.worker_patch(self,mode)
        model=self.base/'model';model.mkdir();header=json.dumps({'weight':dict(dtype='F32',shape=[1],data_offsets=[0,4])}).encode();header+=b' '*((-len(header))%8)
        for name in local.MODEL_FILES:(model/name).write_bytes(struct.pack('<Q',len(header))+header+bytes(4) if name.endswith('.safetensors') else b'{}\n')
        self.addCleanup(patch.stopall);patch('ai_ad_editor.local_interpolation.CONFIG_SHA256',sha256_file(model/'config.json')).start()
        self.proof=self.base/'proof.txt';self.proof.write_text('Synthetic protocol worker, not a usable neural model.',encoding='utf8')
        code,value=fixture.invoke('interpolate','adapter','register','--project',str(self.root),'--adapter-id','test','--model-path',str(model),'--executable',sys.executable,'--evidence',str(self.proof),'--license-spdx','MIT')
        self.assertEqual(code,0,value);self.registered=value['data']['adapter']
        code,value=fixture.invoke('media','ingest','--project',str(self.root),'--input',str(self.video),'--license-spdx','CC0-1.0','--evidence',str(self.proof));self.assertEqual(code,0,value);self.asset=value['data']['asset']
    def command(self):return ['interpolate','generate','--project',str(self.root),'--adapter-id','test','--asset-id','generated','--source-asset-id',self.asset['id'],'--factor','3','--scene-cut-threshold','0','--apply','--video-track-id','track_video_1','--audio-track-id','track_audio_1','--playback-speed',str(1/3)]
    def metadata(self):return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*.json') if not any(p.is_relative_to(self.root/d) for d in ('cache','snapshots','renders/diagnostics'))}
    def test_dry_run_no_inference_or_metadata_mutation(self):
        before=self.metadata()
        with patch('ai_ad_editor.interpolation_pipeline.execute') as infer:code,value=fixture.invoke(*self.command(),'--dry-run')
        self.assertEqual(code,0,value);infer.assert_not_called();self.assertEqual(before,self.metadata());self.assertFalse(value['data']['model_inference_executed'])
    def test_linked_slow_motion_and_rerunnable_native_recipe(self):
        with self.worker_patch():code,value=fixture.invoke(*self.command())
        self.assertEqual(code,0,value);clips=value['data']['clips'];self.assertEqual(len(clips),2);self.assertEqual(clips[0]['clip']['link_id'],clips[1]['clip']['link_id']);self.assertEqual(clips[0]['clip']['duration_tick'],351000)
        code,value=fixture.invoke('interpolate','generate','--project',str(self.root),'--adapter-id','test','--asset-id','rerun','--recipe-asset-id','generated','--factor','4','--dry-run')
        self.assertEqual(code,0,value);self.assertEqual(value['data']['configuration']['video']['factor'],4)
    def test_failed_worker_rolls_back_asset_and_metadata(self):
        before=self.metadata()
        with self.worker_patch('fail'):code,value=fixture.invoke(*self.command())
        self.assertEqual(code,6,value);self.assertEqual(before,self.metadata());self.assertFalse((self.root/'assets/derived/generated.mov').exists())
    def test_validation_failure_after_publication_rolls_back(self):
        before=self.metadata()
        with self.worker_patch(),patch('ai_ad_editor.validator.validate_project',return_value={'ok':False,'errors':[{'code':'intentional'}]}):code,value=fixture.invoke(*self.command())
        self.assertEqual(code,2,value);self.assertEqual(before,self.metadata());self.assertFalse((self.root/'assets/derived/generated.mov').exists())
    def test_weight_tamper_rejected_before_inference(self):
        p=Path(self.registered['model_path'])/'model.safetensors';p.write_bytes(p.read_bytes()[:-4]+b'\1\0\0\0');self.assertFalse(local.verify_adapter(self.registered)['ok'])
        with patch('ai_ad_editor.interpolation_pipeline.execute') as infer:code,value=fixture.invoke(*self.command())
        self.assertNotEqual(code,0,value);infer.assert_not_called()
    def test_read_only_adapter_commands_preserve_metadata(self):
        before=self.metadata()
        for action in ('list','inspect'):
            code,value=fixture.invoke('interpolate','adapter',action,'--project',str(self.root),*(['--adapter-id','test'] if action=='inspect' else []));self.assertEqual(code,0,value)
        self.assertEqual(before,self.metadata())

if __name__=='__main__':unittest.main()
