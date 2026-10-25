"""Actual authored stereo PCM through the common-engine Float32 audio adapter."""
import copy,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_audio_graph import prepare,verify
from ai_ad_editor.media import ffmpeg_path,probe_media
from ai_ad_editor.project import initial_project
from ai_ad_editor.render import build_filter_graph

NATIVE_CALLS=[]
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()

class FloatAudioGraphTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='float-audio-',dir=base);self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        t=np.arange(48000,dtype=np.float64)/48000;self.samples=np.stack((.2*np.sin(2*np.pi*347*t),.17*np.cos(2*np.pi*619*t)),1).astype('<f4')
        raw=self.root/'source.f32';raw.write_bytes(self.samples.tobytes());self.audio=self.root/'source.wav'
        self.native([ffmpeg_path(),'-nostdin','-v','error','-f','f32le','-ar','48000','-ac','2','-i',raw,'-c:a','pcm_f32le',self.audio])
        self.p=initial_project('float audio graph fixture','float_audio');self.p['settings']['canvas'].update(width=8,height=4);self.p['settings']['timebase']['display_fps']={'num':10,'den':1}
        self.p['assets']=[{'id':'sound','kind':'audio','uri':'source.wav','sha256':sha(self.audio),'probe':probe_media(self.audio),'rights_ref':'rights_generated'},
            {'id':'visual','kind':'video','uri':'this-visual-file-is-deliberately-absent.mp4','sha256':'sha256:'+'a'*64,'probe':{'duration_tick':90000,'video':{'width':8,'height':4,'fps':'10/1'}},'rights_ref':'rights_generated'}]
        s=self.p['sequences'][0];s['duration_tick']=90000
        self.c={'id':'sound','asset_id':'sound','timeline_start_tick':0,'duration_tick':90000,'source_in_tick':0,'source_out_tick':90000}
        self.v={'id':'visual','asset_id':'visual','timeline_start_tick':0,'duration_tick':90000,'source_in_tick':0,'source_out_tick':90000}
        s['tracks'][0]['clips']=[self.v];s['tracks'][1]['clips']=[self.c]

    def native(self,command):
        command=list(map(str,command));p=subprocess.run(command,capture_output=True,cwd=self.root,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        NATIVE_CALLS.append({'test':self.id(),'command':command,'exit_code':p.returncode,'stdout_bytes':len(p.stdout),'stdout_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),'stderr':p.stderr.decode('utf8','replace')[-2000:]})
        self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace')[-2000:]);return p.stdout

    def render(self,project=None):
        p=self.p if project is None else project;before=copy.deepcopy(p);plan=prepare(self.root,p,'seq_main');self.assertEqual(p,before)
        result=self.native([ffmpeg_path(),'-nostdin','-v','error','-filter_complex_threads','1',*plan['inputs'],'-filter_complex',plan['filter_complex'],'-map','[aout]','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        self.assertEqual(len(result),plan['expected_samples_48000']*8);verify(self.root,plan);return result,plan

    def test_native_stereo_source_is_exact_and_missing_visual_is_never_opened(self):
        result,plan=self.render();self.assertEqual(result,self.samples.tobytes());self.assertEqual(plan['pruned_visual_leaves'],1)
        self.assertNotIn('this-visual-file',str(plan['inputs']));self.assertTrue(plan['synthetic_video_discarded'])

    def test_half_open_source_trim_and_timeline_silence_match_every_sample(self):
        self.c.update(timeline_start_tick=9000,duration_tick=45000,source_in_tick=9000,source_out_tick=54000)
        result,_=self.render();expected=np.zeros_like(self.samples);expected[4800:28800]=self.samples[4800:28800];self.assertEqual(result,expected.tobytes())

    def test_reverse_preserves_channel_pairs_and_every_original_sample(self):
        self.c['reverse']=True;result,_=self.render();self.assertEqual(result,self.samples[::-1].tobytes())

    def test_freeze_inserts_exact_authored_silence_and_preserves_source_clock(self):
        self.c.update(source_out_tick=72000,freeze={'at_tick':22500,'duration_tick':18000})
        result,_=self.render();expected=np.concatenate((self.samples[:12000],np.zeros((9600,2),'<f4'),self.samples[12000:38400]));self.assertEqual(result,expected.tobytes())

    def test_nested_video_container_retains_complete_child_audio_and_window(self):
        root=self.p['sequences'][0];child=copy.deepcopy(root);child['id']='child';child['tracks'][0]['id']='child_video';child['tracks'][1]['id']='child_audio';self.p['sequences'].append(child)
        parent={'id':'nested','sequence_id':'child','timeline_start_tick':0,'duration_tick':45000,'source_in_tick':0,'source_out_tick':90000,
            'presentation_window':{'version':1,'authored_start_tick':0,'authored_duration_tick':90000,'offset_tick':18000}}
        root['duration_tick']=45000;root['tracks'][0]['clips']=[parent];root['tracks'][1]['clips']=[]
        result,_=self.render();self.assertEqual(result,self.samples[9600:33600].tobytes())

    def test_audio_volume_automation_is_retained_after_visual_keyframes_are_pruned(self):
        gain=10**(-6/20)
        self.c['keyframes']=[{'property':'audio.volume','keyframes':[{'at_tick':0,'value':gain,'interpolation':'linear'},{'at_tick':90000,'value':gain,'interpolation':'linear'}]},
            {'property':'opacity','keyframes':[{'at_tick':0,'value':0,'interpolation':'linear'},{'at_tick':90000,'value':1,'interpolation':'linear'}]}]
        result,_=self.render();actual=np.frombuffer(result,'<f4').reshape(-1,2);np.testing.assert_allclose(actual,self.samples*gain,atol=3e-8,rtol=0)

    def test_unprefixed_volume_and_pan_aliases_preserve_independent_stereo_channels(self):
        self.c['keyframes']=[{'property':name,'keyframes':[{'at_tick':0,'value':value,'interpolation':'linear'},
            {'at_tick':90000,'value':value,'interpolation':'linear'}]} for name,value in (('volume',.5),('pan',.25))]
        result,_=self.render();actual=np.frombuffer(result,'<f4').reshape(-1,2)
        np.testing.assert_allclose(actual,self.samples*np.array([.375,.5],dtype='<f4'),atol=3e-8,rtol=0)

    def test_nested_video_freeze_and_parent_gain_keep_original_audio_clock(self):
        root=self.p['sequences'][0];child=copy.deepcopy(root);child['id']='child';child['tracks'][0]['id']='child_video';child['tracks'][1]['id']='child_audio';self.p['sequences'].append(child)
        root['tracks'][0]['clips']=[{'id':'nested','sequence_id':'child','timeline_start_tick':0,'duration_tick':90000,
            'source_in_tick':0,'source_out_tick':72000,'freeze':{'at_tick':22500,'duration_tick':18000},'audio':{'volume':.5}}]
        root['tracks'][1]['clips']=[]
        result,plan=self.render();expected=np.concatenate((self.samples[:12000],np.zeros((9600,2),'<f4'),self.samples[12000:38400]))*.5
        self.assertEqual(result,expected.tobytes());self.assertEqual(plan['nested_visual_containers_compiled_as_audio'],1)

    def test_empty_and_muted_audio_keep_exact_authored_sample_count(self):
        self.p['sequences'][0]['duration_tick']=112501;self.p['sequences'][0]['tracks'][1]['muted']=True
        result,plan=self.render();self.assertEqual(plan['expected_samples_48000'],60001);self.assertEqual(result,bytes(60001*8))

    def source_transition_fixture(self,reverse=False):
        seq=self.p['sequences'][0]
        for asset in self.p['assets']:asset['probe']['duration_seconds']=1.
        for track,original in zip(seq['tracks'][:2],(self.v,self.c)):
            first,second=copy.deepcopy(original),copy.deepcopy(original)
            first.update(id=original['id']+'_a',duration_tick=45000,source_in_tick=18000,source_out_tick=63000,reverse=reverse)
            second.update(id=original['id']+'_b',timeline_start_tick=45000,duration_tick=45000,source_in_tick=18000,source_out_tick=63000,reverse=reverse)
            track['clips']=[first,second]
        seq['source_transitions']=[dict(id='real_cut',type='dissolve',duration_tick=27000,
            from_clip_id='visual_a',to_clip_id='visual_b',audio_pairs=[dict(from_clip_id='sound_a',to_clip_id='sound_b')])]
        n=np.arange(48000);q=np.clip((n-19200)/14400,0.,1.)[:,None]
        a=np.zeros_like(self.samples);b=np.zeros_like(self.samples)
        ia=n[:33600]+9600 if not reverse else 33599-n[:33600]
        ib=n[19200:]-14400 if not reverse else 57599-n[19200:]
        a[:33600]=self.samples[ia];b[19200:]=self.samples[ib]
        return (a.astype(np.float64)*(1-q)+b.astype(np.float64)*q).astype('<f4')

    def test_real_source_transition_audio_matches_every_sample_without_visual_decode(self):
        for reverse in (False,True):
            expected=self.source_transition_fixture(reverse)
            result,plan=self.render();actual=np.frombuffer(result,'<f4').reshape(-1,2)
            np.testing.assert_allclose(actual,expected,rtol=0,atol=3e-7)
            self.assertEqual(len(plan['source_transition_plans']),1)
            self.assertNotIn('deliberately-absent',str(plan['inputs']))
            self.assertEqual(len(actual),48000)

    def test_nested_real_source_transition_audio_retains_original_cut_after_trim_and_reverse(self):
        self.source_transition_fixture()
        root=self.p['sequences'][0];child=copy.deepcopy(root);child['id']='child';root.pop('source_transitions')
        self.p['sequences'].append(child)
        root['duration_tick']=54000
        root['tracks'][0]['clips']=[dict(id='nested',sequence_id='child',timeline_start_tick=0,duration_tick=54000,
            source_in_tick=18000,source_out_tick=72000,reverse=True)]
        root['tracks'][1]['clips']=[]
        result,_=self.render();actual=np.frombuffer(result,'<f4').reshape(-1,2)
        # Existing engine contract: each original PCM interval is reversed;
        # gain is evaluated at the continuous authored child presentation
        # boundary (.8 - n/SR), not at the preceding PCM sample's timestamp.
        # Simply reversing a previously mixed buffer is a different oracle.
        n=np.arange(28800);q=np.clip((.8-n/48000-.4)/.3,0.,1.)[:,None]
        a=np.zeros((28800,2),np.float64);b=np.zeros_like(a)
        a[4800:]=self.samples[47999-n[4800:]]
        b[:19200]=self.samples[23999-n[:19200]]
        expected=(a*(1-q)+b*q).astype('<f4')
        np.testing.assert_allclose(actual,expected,rtol=0,atol=3e-7)

    def test_cancel_and_invalid_source_transitions_reject_without_real_video_decode(self):
        marker=self.root/'cancel';marker.touch()
        with self.assertRaises(AppError) as caught:prepare(self.root,self.p,'seq_main',cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED');self.p['sequences'][0]['source_transitions']=[{'id':'not-wired'}]
        with self.assertRaises(AppError) as caught:prepare(self.root,self.p,'seq_main')
        self.assertEqual(caught.exception.code,'SOURCE_TRANSITION_INVALID')

if __name__=='__main__':unittest.main()
