"""Pixel/clock, real FFmpeg transport and rollback tests; workers here are synthetic.

Actual MuseTalk CUDA inference has separate installed-case evidence. These tests
deliberately use a tiny deterministic worker to exercise failures and publication.
"""
import copy,hashlib,io,json,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from ai_ad_editor import lipsync_plan as planning,local_lipsync as local
from ai_ad_editor.lipsync_frames import process_frames
from ai_ad_editor.lipsync_pipeline import execute,validate_response
from ai_ad_editor.errors import AppError
from ai_ad_editor.job_workspaces import managed_workspace
from ai_ad_editor.local_matting import manifest_hash
from ai_ad_editor.media import ffmpeg_path,probe_media
from ai_ad_editor.project import create_project
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import sha256_file
import test_local_matting as fixture


def box(values=(16,8,48,40),frames=None):
    return dict(clock='output-frame-25fps',keys=[dict(frame=0,box=list(values))]+([dict(frame=frames[0],box=frames[1])] if frames else []))


class Model:
    def source(self,crop,parse):return None,np.full((512,512),255,np.uint8)
    def predict(self,latents,ids):return np.full((len(ids),256,256,3),222,np.uint8)


class PixelTests(unittest.TestCase):
    def run_frames(self,*,alpha=255,frames=5,options=None,model=None,raw=None,budget=512*1024**2,sink=None):
        image=np.full((frames,48,64,4),30,np.uint8);image[:,:,:,3]=alpha
        image[:,:,0,3]=0;image[:,:,-1,3]=129
        source=io.BytesIO(image.tobytes() if raw is None else raw);destination=io.BytesIO() if sink is None else sink
        metrics=process_frames(source,destination,width=64,height=48,frames=frames,boxes=box(),options=options or planning.options(mask_top=0,feather_pixels=0),predictor=model or Model(),batch_size=2,budget=budget)
        return image,np.frombuffer(destination.getvalue(),np.uint8).reshape(image.shape),metrics

    def test_fractional_and_hidden_alpha_and_outside_box_are_bit_exact(self):
        for alpha in (0,1,127,255):
            original,result,m=self.run_frames(alpha=alpha)
            np.testing.assert_array_equal(result[:,:,:,3],original[:,:,:,3])
            outside=np.ones((48,64),bool);outside[8:40,16:48]=False
            np.testing.assert_array_equal(result[:,outside],original[:,outside])
            if alpha==0:np.testing.assert_array_equal(result,original)
            else:np.testing.assert_array_equal(result[:,8:40,16:48,:3],222)
            self.assertEqual(m['input_alpha_sha256'],m['output_alpha_sha256']);self.assertEqual(m['batches'],3)

    def test_semantic_zero_mask_is_identity_even_when_prediction_changes(self):
        class Zero(Model):
            def source(self,*args):return None,np.zeros((512,512),np.uint8)
        a,b,m=self.run_frames(model=Zero());np.testing.assert_array_equal(a,b);self.assertEqual(m['changed_RGB_pixels'],0)

    def test_mask_top_protects_upper_face_with_no_feather(self):
        original,result,m=self.run_frames(options=planning.options(mask_top=.5,feather_pixels=0))
        np.testing.assert_array_equal(result[:,8:24,16:48],original[:,8:24,16:48]);np.testing.assert_array_equal(result[:,24:40,16:48,:3],222)

    def test_feather_stays_inside_explicit_box(self):
        original,result,_=self.run_frames(options=planning.options(mask_top=.5,feather_pixels=3))
        np.testing.assert_array_equal(result[:,:,:16],original[:,:,:16]);np.testing.assert_array_equal(result[:,:,48:],original[:,:,48:])
        self.assertGreater(len(np.unique(result[:,20:40,16:48,0])),2)

    def test_truncated_and_extra_frames_rejected(self):
        for raw in (bytes(64*48*4*5-1),bytes(64*48*4*5+1)):
            with self.subTest(size=len(raw)),self.assertRaisesRegex(ValueError,'SOURCE_(TRUNCATED|EXTRA)'):self.run_frames(raw=raw)

    def test_array_budget_rejects_before_neural_batch(self):
        class Never(Model):
            def predict(self,*args):raise AssertionError('Neural batch should not execute')
        with self.assertRaisesRegex(ValueError,'BUDGET'):self.run_frames(budget=1,model=Never())

    def test_invalid_neural_batch_and_semantic_mask_rejected(self):
        class Bad(Model):
            def predict(self,latents,ids):return np.zeros((len(ids),3,256,256),np.uint8)
        with self.assertRaisesRegex(ValueError,'FRAME_CONTRACT'):self.run_frames(model=Bad())
        class BadMask(Model):
            def source(self,*args):return None,np.zeros((511,512),np.float32)
        with self.assertRaisesRegex(ValueError,'SEMANTIC_MASK'):self.run_frames(model=BadMask())

    def test_short_write_rejected(self):
        class Short(io.BytesIO):
            def write(self,value):return len(value)-1
        with self.assertRaisesRegex(ValueError,'SHORT_OUTPUT_WRITE'):self.run_frames(sink=Short())

    def test_partial_pipe_reads_produce_the_same_complete_frames(self):
        class Partial(io.BytesIO):
            def read(self,size=-1):return super().read(min(size,97))
        original,expected,_=self.run_frames();sink=io.BytesIO()
        process_frames(Partial(original.tobytes()),sink,width=64,height=48,frames=5,boxes=box(),options=planning.options(mask_top=0,feather_pixels=0),predictor=Model(),batch_size=2,budget=512*1024**2)
        self.assertEqual(sink.getvalue(),expected.tobytes())


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.source=dict(asset_id='portrait',kind='image',sha256='sha256:'+'1'*64,probe=dict(video=dict(width=64,height=48)))
        self.audio=dict(asset_id='speech',kind='audio',sha256='sha256:'+'2'*64,probe=dict(audio=dict(sample_rate=44100,channels=2,duration_seconds=1.001),duration_seconds=1.001))
    def plan(self,**kwargs):return planning.configuration(self.source,self.audio,face_boxes=box(),settings=local.settings(),**kwargs)
    def asset(self,plan):
        a=plan['audio'];v=plan['video']
        return dict(id='result',kind='video',probe=dict(video=v,streams=[dict(codec_type='video',nb_frames=v['frames'],avg_frame_rate='25/1'),dict(codec_type='audio',sample_rate=a['sample_rate'],channels=a['channels'],duration_ts=a['output_samples'],time_base='1/'+str(a['sample_rate']))]),
            source=dict(derived_from=['portrait','speech']))
    def test_ceil_clock_preserves_all_selected_samples_with_less_than_40ms_padding(self):
        plan=self.plan();a=plan['audio'];self.assertEqual(plan['video']['frames'],26);self.assertEqual(a['samples'],44144)
        self.assertEqual(a['output_samples'],45864);self.assertLess(a['padding_seconds'],.04)
    def test_source_video_requires_explicit_shortage_strategy(self):
        self.source.update(kind='video');self.source['probe']['video']['duration_seconds']=.5
        with self.assertRaisesRegex(AppError,'视频源不足'):self.plan()
        for mode in ('hold','loop'):self.assertEqual(self.plan(source_mode=mode)['range']['source_mode'],mode)
        with self.assertRaises(AppError):self.plan(source_mode='loop',source_start_seconds=.1)
    def test_image_range_and_source_loop_are_rejected(self):
        for kwargs in (dict(source_mode='loop'),dict(source_start_seconds=.1),dict(source_end_seconds=.5)):
            with self.assertRaises(AppError):self.plan(**kwargs)
    def test_options_clocks_and_quotas_reject_before_execution(self):
        for kwargs in (dict(seed=True),dict(seed=-1),dict(mask_top=float('nan')),dict(feather_pixels=33),dict(audio_start_seconds=1.1),dict(audio_end_seconds=0),dict(storage_budget_mib=1)):
            with self.subTest(kwargs=kwargs),self.assertRaises(AppError):self.plan(**kwargs)
        self.source['probe']['video'].update(width=4096,height=4096)
        with self.assertRaises(AppError):self.plan()
    def test_box_interpolation_and_hold_are_exact_output_frame_clock(self):
        b=box(frames=(4,[24,12,56,44]));local.boxes(b,64,48,5)
        self.assertEqual(local.box_at(b,2),[20,10,52,42]);self.assertEqual(local.box_at(b,9),[24,12,56,44])
    def test_bad_boxes_rejected(self):
        cases=[dict(clock='seconds',keys=[]),box((0,0,31,32)),box((0,0,65,40)),box((True,0,40,40)),box(frames=(0,[16,8,48,40])),box(frames=(5,[16,8,48,40]))]
        for row in cases:
            with self.subTest(row=row),self.assertRaises(AppError):local.boxes(row,64,48,5)
    def test_portable_recipe_digests_clock_parents_and_rebinding(self):
        plan=self.plan();value=planning.recipe(plan,self.source,self.audio);asset=self.asset(plan)
        assets={row['asset_id']:dict(id=row['asset_id'],kind=row['kind'],sha256=row['sha256']) for row in (self.source,self.audio)}
        planning.validate_recipe(value,asset=asset,assets=assets)
        rebound=planning.rebind_recipe(value,mapping={'portrait':'other_portrait','speech':'other_speech'},asset=asset,assets=assets)
        self.assertEqual(rebound['audio_asset_id'],'other_speech');self.assertNotEqual(value['sha256'],rebound['sha256'])
        for change in ('digest','frame','parent','audio'):
            altered=copy.deepcopy(value);out=copy.deepcopy(asset)
            if change=='digest':altered['options']['seed']=2
            elif change=='frame':out['probe']['streams'][0]['nb_frames']=25
            elif change=='parent':out['source']['derived_from']=[]
            else:out['probe']['streams'][1]['duration_ts']-=1
            with self.subTest(change=change),self.assertRaises(AppError):planning.validate_recipe(altered,asset=out,assets=assets)
    def test_cuda_settings_reject_cpu_and_boolean_batch(self):
        for kwargs in (dict(device='cpu'),dict(batch_size=True),dict(batch_size=9),dict(threads=0)):
            with self.assertRaises(AppError):local.settings(**kwargs)


FAKE_WORKER=r'''
import sys,json,time
from pathlib import Path
sys.path.insert(0,PACKAGE)
import numpy as np
from ai_ad_editor.lipsync_frames import process_frames
from ai_ad_editor.utils import atomic_write_json
r=json.loads(Path(sys.argv[1]).read_bytes());n=r['video']['frames'];batch=r['adapter']['settings']['batch_size']
if MODE=='wait':time.sleep(30)
if MODE=='fail':raise RuntimeError('intentional synthetic protocol failure')
class Model:
 def source(self,*args):return None,np.full((512,512),255,np.uint8)
 def predict(self,latents,ids):return np.full((len(ids),256,256,3),177,np.uint8)
m=process_frames(sys.stdin.buffer,sys.stdout.buffer,width=r['video']['width'],height=r['video']['height'],frames=n,boxes=r['boxes'],options=r['options'],predictor=Model(),batch_size=batch,budget=r['adapter']['settings']['state_budget_bytes'])
execution=dict(engine=r['engine'],model_loads=1,cache_hits=0,CPU_fallback=False,network='disabled',weight_reader='safetensors-pread',precision=r['adapter']['settings']['precision'],cuda_peak_allocated_bytes=1,batch_frames=[min(batch,n-i) for i in range(0,n,batch)],calls=dict(audio_encoder=1,vae_encoder=n*2,unet=m['batches'],vae_decoder=m['batches'],face_parser=n))
out=dict(status='succeeded',engine=r['engine'],protocol=r['protocol'],network='disabled',blocked_network_events=[],request_sha256=r['request_sha256'],adapter_sha256=r['adapter']['sha256'],source_sha256=r['source']['sha256'],audio_sha256=r['audio_source']['sha256'],providers=['torch-cuda'],model_loaded=True,metrics=m,model_execution=execution)
if MODE=='bad':out['metrics']['output_alpha_sha256']='sha256:'+'0'*64
atomic_write_json(Path(r['response']),out)
'''


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):configure_local_runtime()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        self.root=self.base/'project';create_project(self.root)
        self.portrait=self.base/'image.png';Image.new('RGBA',(64,48),(60,80,100,129)).save(self.portrait)
        self.wav=self.base/'speech.wav'
        subprocess.run([ffmpeg_path(),'-v','error','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=0.201','-ac','2','-c:a','pcm_f32le',str(self.wav)],capture_output=True,check=True)
        self.source=dict(asset_id='portrait',kind='image',path=str(self.portrait),sha256='sha256:'+sha256_file(self.portrait),probe=probe_media(self.portrait),stream_index=0)
        self.audio=dict(asset_id='speech',kind='audio',path=str(self.wav),sha256='sha256:'+sha256_file(self.wav),probe=probe_media(self.wav),stream_index=0)
        self.adapter=dict(adapter_id='test',engine=local.ENGINE,protocol=local.PROTOCOL,settings=local.settings(),sha256='sha256:'+'0'*64,executable=sys.executable)
        self.plan=planning.configuration(self.source,self.audio,face_boxes=box(),settings=self.adapter['settings'],mask_top=0,feather_pixels=0)
        self.worker=self.base/'worker.py'
    def execute(self,mode='ok',timeout=60,marker=None):
        self.worker.write_text('PACKAGE='+repr(str(Path(local.__file__).resolve().parent.parent))+'\nMODE='+repr(mode)+'\n'+FAKE_WORKER,encoding='utf8')
        actual=subprocess.Popen
        def start(command,*args,**kwargs):
            if any(str(v).endswith('lipsync_worker.py') for v in command):command=[sys.executable,'-I','-B',str(self.worker),command[-1]]
            return actual(command,*args,**kwargs)
        with managed_workspace(self.root,'lip-sync') as job,patch('ai_ad_editor.lipsync_pipeline.verify_adapter',return_value={'ok':True}),patch('ai_ad_editor.lipsync_pipeline.subprocess.Popen',side_effect=start):
            return execute(self.root,job,self.plan,self.source,self.audio,self.adapter,timeout=timeout,cancel_file=marker)
    def test_complete_actual_qtrle_and_float_pcm_transport_and_cleanup(self):
        stage,result=self.execute();self.assertTrue(result['rgba_roundtrip_verified']);self.assertTrue(result['complete_PCM_roundtrip_verified'])
        self.assertEqual(result['recipe']['audio']['samples'],9648);self.assertEqual(result['recipe']['audio']['output_samples'],11520)
        self.assertTrue(all(p['exited'] and p['stdout_closed'] for p in result['cleanup']['processes']))
        self.assertFalse(stage.exists());self.assertFalse(list((self.root/'cache/managed-jobs').glob('job-*')))
    def test_worker_failure_is_diagnosed_and_workspace_recovered(self):
        with self.assertRaisesRegex(AppError,'管道失败') as caught:self.execute('fail')
        self.assertEqual(caught.exception.diagnostics['status'],'stored');self.assertFalse(list((self.root/'cache/managed-jobs').glob('job-*')))
    def test_forged_alpha_response_is_rejected(self):
        with self.assertRaisesRegex(AppError,'协议校验'):self.execute('bad')
    def test_timeout_kills_owned_children(self):
        started=time.monotonic()
        with self.assertRaises(AppError) as caught:self.execute('wait',timeout=2)
        self.assertEqual(caught.exception.code,'TIMEOUT');self.assertLess(time.monotonic()-started,15)
        self.assertFalse(list((self.root/'cache/managed-jobs').glob('job-*')))
    def test_cancel_marker_kills_owned_children(self):
        marker=self.base/'cancel';timer=threading.Timer(1,lambda:marker.write_text('cancel'));timer.start()
        try:
            with self.assertRaises(AppError) as caught:self.execute('wait',marker=marker)
            self.assertEqual(caught.exception.code,'CANCELLED')
        finally:timer.cancel();timer.join()
        self.assertFalse(list((self.root/'cache/managed-jobs').glob('job-*')))


class CLITests(unittest.TestCase):
    setUpClass=TransportTests.__dict__['setUpClass']
    def setUp(self):
        TransportTests.setUp(self)
        import struct
        model=self.base/'model';model.mkdir()
        header=json.dumps({'weight':dict(dtype='F32',shape=[1],data_offsets=[0,4])}).encode();header+=b' '*((-len(header))%8)
        for name in local.MODEL_FILES:
            p=model/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(struct.pack('<Q',len(header))+header+bytes(4) if name.endswith('.safetensors') else b'{}\n')
        hashes={name:sha256_file(model/name) for name in local.CONFIG_HASHES}
        self.addCleanup(patch.stopall);patch('ai_ad_editor.local_lipsync.CONFIG_HASHES',hashes).start()
        self.proof=self.base/'proof.txt';self.proof.write_text('Synthetic protocol tests; not a usable neural model.',encoding='utf8')
        code,value=fixture.invoke('lipsync','adapter','register','--project',str(self.root),'--adapter-id','test','--model-path',str(model),
            '--executable',sys.executable,'--evidence',str(self.proof),'--license-spdx','MIT')
        self.assertEqual(code,0,value);self.registered=value['data']['adapter']
        ids=[]
        for path in (self.portrait,self.wav):
            code,value=fixture.invoke('media','ingest','--project',str(self.root),'--input',str(path),'--license-spdx','CC0-1.0','--evidence',str(self.proof))
            self.assertEqual(code,0,value);ids.append(value['data']['asset']['id'])
        self.ids=ids
    def command(self):return ['lipsync','generate','--project',str(self.root),'--adapter-id','test','--asset-id','generated','--source-asset-id',self.ids[0],'--audio-asset-id',self.ids[1],'--face-box','16','8','48','40','--apply','--video-track-id','track_video_1','--audio-track-id','track_audio_1']
    def metadata(self):return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*.json') if not p.is_relative_to(self.root/'cache') and not p.is_relative_to(self.root/'snapshots')}
    def worker_patch(self,mode='ok'):
        self.worker.write_text('PACKAGE='+repr(str(Path(local.__file__).resolve().parent.parent))+'\nMODE='+repr(mode)+'\n'+FAKE_WORKER,encoding='utf8')
        actual=subprocess.Popen
        def start(command,*args,**kwargs):
            if any(str(v).endswith('lipsync_worker.py') for v in command):command=[sys.executable,'-I','-B',str(self.worker),command[-1]]
            return actual(command,*args,**kwargs)
        return patch('ai_ad_editor.lipsync_pipeline.subprocess.Popen',side_effect=start)
    def test_dry_run_has_no_inference_or_project_mutation(self):
        before=self.metadata()
        with patch('ai_ad_editor.lipsync_pipeline.execute') as infer:
            code,value=fixture.invoke(*self.command(),'--dry-run')
        self.assertEqual(code,0,value);infer.assert_not_called();self.assertEqual(before,self.metadata())
    def test_actual_transport_registers_two_editable_linked_tracks_and_rerun_plan(self):
        with self.worker_patch():code,value=fixture.invoke(*self.command())
        self.assertEqual(code,0,value);clips=value['data']['clips'];self.assertEqual(len(clips),2)
        self.assertEqual(clips[0]['clip']['link_id'],clips[1]['clip']['link_id'])
        self.assertEqual(clips[0]['clip']['asset_id'],clips[1]['clip']['asset_id'])
        code,value=fixture.invoke('lipsync','generate','--project',str(self.root),'--adapter-id','test','--asset-id','rerun','--recipe-asset-id','generated','--seed','19','--dry-run')
        self.assertEqual(code,0,value);self.assertEqual(value['data']['configuration']['options']['seed'],19)
    def test_failed_generation_rolls_back_all_project_and_rights_metadata(self):
        before=self.metadata()
        with self.worker_patch('fail'):code,value=fixture.invoke(*self.command())
        self.assertEqual(code,6,value);self.assertEqual(before,self.metadata());self.assertFalse((self.root/'assets/derived/generated.mov').exists())
    def test_validation_failure_after_publication_rolls_back_asset_and_metadata(self):
        before=self.metadata()
        with self.worker_patch(),patch('ai_ad_editor.validator.validate_project',return_value={'ok':False,'errors':[{'code':'intentional'}]}):code,value=fixture.invoke(*self.command())
        self.assertEqual(code,2,value);self.assertEqual(before,self.metadata());self.assertFalse((self.root/'assets/derived/generated.mov').exists())
    def test_registered_tensor_tamper_is_detected_before_inference(self):
        model=Path(self.registered['model_path']);p=model/'unet/diffusion_pytorch_model.safetensors';data=p.read_bytes();p.write_bytes(data[:-4]+b'\1\0\0\0')
        self.assertFalse(local.verify_adapter(self.registered)['ok'])
        with patch('ai_ad_editor.lipsync_pipeline.execute') as infer:code,value=fixture.invoke(*self.command())
        self.assertNotEqual(code,0,value);infer.assert_not_called()
    def test_read_only_inspection_preserves_metadata(self):
        before=self.metadata()
        for action in ('list','inspect'):
            args=['lipsync','adapter',action,'--project',str(self.root)]
            if action=='inspect':args+=['--adapter-id','test']
            code,value=fixture.invoke(*args);self.assertEqual(code,0,value)
        self.assertEqual(before,self.metadata())


if __name__=='__main__':unittest.main()
