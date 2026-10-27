"""Real FFV1/PCM proofs and native blocked-writer lifecycle checks."""
import copy,hashlib,json,subprocess,sys,tempfile,threading,time,unittest
from fractions import Fraction
from pathlib import Path
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_audio_graph import prepare
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_stream import CHUNK_BYTES,_EncoderPipe,render_ffv1
from ai_ad_editor.float_timeline import FloatTimeline,TimedSurfaceSource
from ai_ad_editor.media import ffmpeg_path,probe_media
from ai_ad_editor.project import initial_project

LINEAR=ColorSignal('bt709','linear');NATIVE_CALLS=[];ENCODE_RECEIPTS=[];ERROR_RECEIPTS=[]
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

class FloatStreamTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='float-stream-',dir=base);self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def native(self,command):
        command=list(map(str,command));p=subprocess.run(command,capture_output=True,cwd=self.root,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        NATIVE_CALLS.append({'test':self.id(),'command':command,'exit_code':p.returncode,'stdout_bytes':len(p.stdout),
            'stdout_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),'stderr':p.stderr.decode('utf8','replace')[-2000:]})
        self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace'));return p.stdout

    def fixture(self,rgba=None,*,duration=9000,with_audio=False):
        value=np.broadcast_to(np.array([.25,.5,.75,1],np.float32),(4,8,4)).copy() if rgba is None else rgba
        h,w=value.shape[:2];original=self.root/'original.f32';original.write_bytes(value.tobytes());expected=sha(original)
        def verify():
            if sha(original)!=expected:raise AppError('TEST_SOURCE_CHANGED','actual registered source changed')
        source=TimedSurfaceSource([0],[0],'1/90000',0,lambda i:value.copy(),signal=LINEAR,
            source_sha256=expected,still=True,verify=verify)
        p=initial_project('native float stream fixture','float_stream');p['settings']['canvas'].update(width=w,height=h,background='transparent')
        p['settings']['timebase']['display_fps']={'num':10,'den':1};s=p['sequences'][0];s['duration_tick']=duration
        p['assets']=[{'id':'picture','kind':'image','uri':'original.f32','sha256':expected,'rights_ref':'rights_generated',
            'probe':{'video':{'width':w,'height':h,'fps':'10/1'},'duration_tick':duration}}]
        s['tracks'][0]['clips']=[{'id':'picture','asset_id':'picture','timeline_start_tick':0,'duration_tick':duration,
            'source_in_tick':0,'source_out_tick':duration}];s['tracks'][1]['clips']=[]
        samples=None
        if with_audio:
            t=np.arange(48000,dtype=np.float64)/48000;samples=np.stack((.2*np.sin(2*np.pi*347*t),.17*np.cos(2*np.pi*619*t)),1).astype('<f4')
            raw=self.root/'audio.f32';raw.write_bytes(samples.tobytes());wav=self.root/'audio.wav'
            self.native([ffmpeg_path(),'-nostdin','-v','error','-f','f32le','-ar','48000','-ac','2','-i',raw,'-c:a','pcm_f32le',wav])
            p['assets'].append({'id':'sound','kind':'audio','uri':'audio.wav','sha256':sha(wav),'probe':probe_media(wav),'rights_ref':'rights_generated'})
            s['tracks'][1]['clips']=[{'id':'sound','asset_id':'sound','timeline_start_tick':0,'duration_tick':90000,'source_in_tick':0,'source_out_tick':90000}]
        return p,source,value,samples

    def encode(self,p,source,*,audio=False,name='actual.mkv',**options):
        timeline=FloatTimeline(p,'seq_main',{'picture':source},working_signal=LINEAR)
        plan=prepare(self.root,p,'seq_main') if audio else None
        try:result=render_ffv1(self.root,timeline,self.root/name,output_signal=LINEAR,audio_plan=plan,**options)
        except AppError as exc:
            ERROR_RECEIPTS.append({'test':self.id(),'error':exc.as_dict()});raise
        ENCODE_RECEIPTS.append({'test':self.id(),**result});self.assertTrue(result['owned_threads_closed'])
        self.assertEqual(result['owned_process_exit_code'],0);self.assertLessEqual(result['maximum_queued_chunks'],4)
        return self.root/name,result

    def picture(self,path):return self.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:v:0','-an','-pix_fmt','gbrap16le','-f','rawvideo','pipe:1'])

    def test_real_lossless_all_65536_codes_survive_without_eight_bit_boundary(self):
        codes=np.arange(65536,dtype='<u2').reshape(256,256);rgba=np.stack((codes,np.roll(codes,59,axis=1),65535-codes,np.full_like(codes,65535)),2).astype(np.float32)/65535
        p,source,_,_=self.fixture(rgba);path,receipt=self.encode(p,source);actual=np.frombuffer(self.picture(path),'<u2').reshape(4,256,256)
        np.testing.assert_array_equal(actual,np.stack((np.roll(codes,59,axis=1),65535-codes,codes,np.full_like(codes,65535))))
        self.assertEqual(len(np.unique(actual[2])),65536);self.assertEqual(receipt['video_input_bytes'],256*256*8)

    def test_straight_alpha_independent_sixteen_bit_output_and_hidden_zero_canonicalization(self):
        codes=np.array([0,1,255,256,1023,32768,65534,65535],'<u2');rgba=np.ones((4,8,4),np.float32);rgba[:,:,:3]=np.array([.125,.375,.875],np.float32);rgba[:,:,3]=codes.astype(np.float32)/65535
        p,source,_,_=self.fixture(rgba);path,_=self.encode(p,source);actual=np.frombuffer(self.picture(path),'<u2').reshape(4,4,8)
        expected=np.rint(rgba.astype(np.float64)*65535).astype('<u2');expected[:,0,:3]=0
        np.testing.assert_array_equal(actual,np.moveaxis(expected[:,:,[1,2,0,3]],2,0))

    def test_real_combined_video_reverse_freeze_audio_matches_every_stereo_sample(self):
        p,source,_,samples=self.fixture(duration=90000,with_audio=True)
        c=p['sequences'][0]['tracks'][1]['clips'][0];c.update(source_out_tick=72000,reverse=True,freeze={'at_tick':22500,'duration_tick':18000})
        path,r=self.encode(p,source,audio=True);actual=self.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        reverse=samples[:38400][::-1];expected=np.concatenate((reverse[:12000],np.zeros((9600,2),'<f4'),reverse[12000:]))
        self.assertEqual(actual,expected.tobytes());self.assertEqual(r['frames'],10);self.assertEqual(r['audio_samples_48000'],48000)
        self.assertEqual(len(self.picture(path)),10*8*4*8)

    def test_fractional_author_end_keeps_ceil_video_and_exact_independent_audio_end(self):
        p,source,_,samples=self.fixture(duration=112501,with_audio=True);path,r=self.encode(p,source,audio=True)
        actual=self.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        self.assertEqual(actual,np.concatenate((samples,np.zeros((12001,2),'<f4'))).tobytes())
        self.assertEqual(r['frames'],13);self.assertEqual(r['video_coverage_end'],'13/10');self.assertEqual(r['audio_samples_48000'],60001)
        self.assertEqual(len(self.picture(path)),13*8*4*8)

    def test_explicit_clip_policy_and_atomic_existing_output_protection(self):
        rgba=np.broadcast_to(np.array([1.25,-.25,.5,1],np.float32),(4,8,4)).copy();p,source,_,_=self.fixture(rgba)
        target=self.root/'actual.mkv';target.write_bytes(b'existing user file')
        with self.assertRaises(AppError) as caught:self.encode(p,source)
        self.assertEqual(caught.exception.code,'FLOAT_STREAM_OUTPUT_EXISTS')
        with self.assertRaises(AppError) as caught:self.encode(p,source,overwrite=True)
        self.assertEqual(caught.exception.code,'FLOAT_STREAM_RANGE');self.assertEqual(target.read_bytes(),b'existing user file');self.assertFalse(list(self.root.glob('.float-*.mkv')))
        path,r=self.encode(p,source,overwrite=True,range_policy='clip');self.assertEqual(r['clipped_RGB_components'],64)
        actual=np.frombuffer(self.picture(path),'<u2').reshape(4,4,8);self.assertTrue(np.all(actual[2]==65535));self.assertTrue(np.all(actual[0]==0))

    def test_changed_original_rejects_before_output_replace_and_reaps_threads(self):
        p,source,_,_=self.fixture();fetch=source.fetch
        def changed(index):
            (self.root/'original.f32').write_bytes(b'changed while actual frame was fetched');return fetch(index)
        source.fetch=changed;target=self.root/'actual.mkv';target.write_bytes(b'keep output')
        with self.assertRaises(AppError) as caught:self.encode(p,source,overwrite=True)
        self.assertEqual(caught.exception.code,'TEST_SOURCE_CHANGED');self.assertEqual(target.read_bytes(),b'keep output')
        self.assertFalse(list(self.root.glob('.float-*.mkv')));self.assertFalse([t for t in threading.enumerate() if t.name.startswith('float-encoder-')])

    def test_audio_plan_for_a_different_project_is_rejected(self):
        p,source,_,_=self.fixture();timeline=FloatTimeline(p,'seq_main',{'picture':source},working_signal=LINEAR)
        other=copy.deepcopy(p);other['title']='different author document';plan=prepare(self.root,other,'seq_main')
        with self.assertRaises(AppError) as caught:render_ffv1(self.root,timeline,self.root/'actual.mkv',output_signal=LINEAR,audio_plan=plan)
        self.assertEqual(caught.exception.code,'FLOAT_STREAM_AUDIO_BINDING');self.assertFalse((self.root/'actual.mkv').exists())

    def test_native_blocked_stdin_timeout_reaps_owned_child_and_threads(self):
        command=[sys.executable,'-I','-S','-B','-c','import time;time.sleep(30)'];pipe=_EncoderPipe(command,cwd=self.root,timeout=.3)
        try:
            with self.assertRaises(AppError) as caught:
                for _ in range(100):pipe.put(bytes(CHUNK_BYTES))
            self.assertEqual(caught.exception.code,'FLOAT_STREAM_TIMEOUT')
        finally:pipe.close()
        self.assertIsNotNone(pipe.process.poll());self.assertTrue(all(not t.is_alive() for t in pipe.threads));self.assertTrue(pipe.queue.empty())

    def test_native_blocked_stdin_cancel_reaps_owned_child_and_threads(self):
        marker=self.root/'cancel';command=[sys.executable,'-I','-S','-B','-c','import time;time.sleep(30)']
        pipe=_EncoderPipe(command,cwd=self.root,cancel_file=marker,timeout=10);timer=threading.Timer(.2,marker.touch);timer.start()
        try:
            with self.assertRaises(AppError) as caught:
                for _ in range(100):pipe.put(bytes(CHUNK_BYTES))
            self.assertEqual(caught.exception.code,'CANCELLED')
        finally:timer.join();pipe.close()
        self.assertIsNotNone(pipe.process.poll());self.assertTrue(all(not t.is_alive() for t in pipe.threads));self.assertTrue(pipe.queue.empty())

if __name__=='__main__':unittest.main()
