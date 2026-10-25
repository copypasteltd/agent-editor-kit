"""Observable whole-speech timing, atomic editing and owned recovery contracts.

Model inference is explicitly simulated here; separate real-run receipts are required.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

import numpy as np

from ai_ad_editor.cli import main
from ai_ad_editor import dubbing, dubbing_cli, material_catalog
from ai_ad_editor.errors import AppError
from ai_ad_editor.job_workspaces import Workspace, recover_workspaces
from ai_ad_editor.project import create_project, load_project, save_project
from ai_ad_editor.rights import add_record, load_ledger, save_ledger
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, sha256_file


def invoke(*args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main([str(v) for v in args])
    return code,json.loads(stream.getvalue())


class FakeEngine:
    def __init__(self, seconds=1.):
        self.seconds,self.calls = seconds,[]

    def generate(self,text,sid,speed):
        self.calls.append((text,sid,speed))
        count = round(self.seconds*24000/speed)
        signal = (.15*np.sin(np.arange(count,dtype=np.float32)*.11)).astype(np.float32)
        return SimpleNamespace(samples=signal,sample_rate=24000)


class CueContractTests(unittest.TestCase):
    def test_source_ids_order_text_and_integer_clocks_are_preserved(self):
        cues = dubbing.parse_srt('8\n00:00:02,123 --> 00:00:03,456\nsecond\nline\n\n2\n00:00:00,001 --> 00:00:01,111\nfirst')
        self.assertEqual([c['source_id'] for c in cues],['8','2'])
        self.assertEqual(cues[0]['text'],'second\nline')
        self.assertEqual(cues[0]['slot_samples'],1333*24)

    def test_invalid_block_is_not_silently_skipped(self):
        with self.assertRaises(ValueError):
            dubbing.parse_srt('1\n00:00:00,000 --> 00:00:01,000\nhello\n\ngarbage')

    def test_duplicate_canonical_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            dubbing.parse_srt('01\n00:00:00,000 --> 00:00:01,000\nhello\n\n1\n00:00:01,000 --> 00:00:02,000\nworld')

    def test_invalid_minutes_and_reversed_windows_are_rejected(self):
        for timing in ('00:60:00,000 --> 00:61:01,000','00:00:01,000 --> 00:00:00,000'):
            with self.subTest(timing=timing),self.assertRaises(ValueError):
                dubbing.parse_srt('1\n'+timing+'\nhello')

    def test_markup_and_controls_require_explicit_prior_normalization(self):
        for text in ('<i>hello</i>','{\\pos(1,2)}hello','hello\x00world'):
            with self.subTest(text=text),self.assertRaises(ValueError):
                dubbing.parse_srt('1\n00:00:00,000 --> 00:00:01,000\n'+text)


class BatchAudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def payload(self,slots,fit='reject',maximum=1.5):
        return dict(speed=1.,max_speed=maximum,fit=fit,segments=[dict(cue_index=i+1,text='Complete sentence '+str(i),
            speaker_id=i,voice_id='test'+str(i),slot_samples=slot,output_directory=str(self.root/str(i))) for i,slot in enumerate(slots)])

    def test_one_engine_is_reused_and_complete_utterances_remain_separate(self):
        engine = FakeEngine()
        result = dubbing.synthesize_segments(engine,self.payload([48000,48000]))
        self.assertEqual(result['fit_status'],'fits')
        self.assertEqual(result['total_generations'],2)
        self.assertEqual(len(engine.calls),2)
        self.assertEqual([dubbing.inspect_wave(s['attempts'][0]['output'])['samples'] for s in result['segments']],[24000,24000])

    def test_speed_fit_regenerates_full_text_and_keeps_original_wav(self):
        engine = FakeEngine(seconds=2.)
        result = dubbing.synthesize_segments(engine,self.payload([36000],fit='speed'))
        attempts = result['segments'][0]['attempts']
        self.assertEqual(result['fit_status'],'fits')
        self.assertEqual(len(attempts),2)
        self.assertEqual(attempts[0]['samples'],48000)
        self.assertLessEqual(attempts[-1]['samples'],36000)
        self.assertEqual(engine.calls[0][:2],engine.calls[1][:2])
        self.assertTrue(all(Path(a['output']).is_file() for a in attempts))

    def test_reject_reports_overflow_without_truncation_or_later_generation(self):
        engine = FakeEngine()
        result = dubbing.synthesize_segments(engine,self.payload([100,48000]))
        self.assertEqual(result['fit_status'],'overflow')
        self.assertEqual(result['processed_cues'],1)
        self.assertEqual(result['segments'][0]['attempts'][0]['samples'],24000)
        self.assertFalse(result['truncation'])

    def test_speed_limit_cannot_be_bypassed(self):
        result = dubbing.synthesize_segments(FakeEngine(2.),self.payload([12000],fit='speed',maximum=1.2))
        self.assertEqual(result['fit_status'],'overflow')
        self.assertEqual(result['segments'][0]['attempts'][-1]['speed'],1.2)
        self.assertGreater(result['segments'][0]['attempts'][-1]['samples'],12000)

    def test_existing_output_is_not_overwritten(self):
        directory = self.root/'0'
        directory.mkdir()
        sentinel = directory/'attempt-1.wav'
        sentinel.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            dubbing.synthesize_segments(FakeEngine(),self.payload([48000]))
        self.assertEqual(sentinel.read_bytes(),b'preserve')

    def test_silence_and_wrong_channel_formats_are_refused(self):
        target = self.root/'bad.wav'
        for channels in (1,2):
            with wave.open(str(target),'wb') as wav:
                wav.setparams((channels,2,24000,0,'NONE','not compressed'))
                wav.writeframes(b'\0'*(480*channels))
            with self.assertRaises(ValueError):
                dubbing.inspect_wave(target)


class DubbingWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'中文 工程'
        create_project(self.root)
        self.source = self.base/'source.srt'
        self.source.write_text('7\n00:00:00,000 --> 00:00:02,000\n你好\n\n4\n00:00:03,000 --> 00:00:05,000\n继续前进\n',encoding='utf-8')
        self.pack = self.base/'fake-pack'
        self.pack.mkdir()
        (self.pack/'LICENSE.txt').write_text('Simulated model evidence; not a real inference.',encoding='utf-8')
        # The pinned pack protocol maps logical IDs to descriptive metadata;
        # the descriptive model ID need not equal its lookup key.
        self.manifest = dict(id='simulated-pack',models={mid:dict(id='descriptive-model-'+mid,
            sha256='1'*64,creator='test',license='MIT',license_path='LICENSE.txt') for mid in ('kokoro','zh-en','en-zh')})
        self.engine,self.calls = FakeEngine(),[]
        self.context_patch = patch('ai_ad_editor.dubbing_cli.model_context',side_effect=self.context)
        self.inference_patch = patch('ai_ad_editor.community_models.infer',side_effect=self.infer)
        self.context_patch.start();self.addCleanup(self.context_patch.stop)
        self.inference_patch.start();self.addCleanup(self.inference_patch.stop)

    def context(self,args,task):
        return dict(config=SimpleNamespace(device='cpu',device_index=0,pack=str(self.pack)),
            device=dict(requested='cpu',selected='cpu',fallback_reason=None),pack=self.pack,
            manifest=copy.deepcopy(self.manifest),library=None)

    def infer(self,root,*,task,payload,**kwargs):
        self.calls.append(dict(root=str(root),task=task,payload=copy.deepcopy(payload)))
        directory = root/'validation'
        directory.mkdir()
        result = dict(protocol='agent-community-cpu-v1',ok=True,task=task,provider=payload['device'],network='disabled',
            pack={'manifest_sha256':'test-only'})
        if task=='translate':
            result['output'] = ['Hello','Keep moving'][:len(payload['texts'])]
        else:
            result.update(dubbing.synthesize_segments(self.engine,payload))
        request,response,log = directory/'request.json',directory/'response.json',directory/'worker.txt'
        atomic_write_json(request,payload)
        atomic_write_json(response,result)
        log.write_text('Simulated model worker for unit tests only.',encoding='utf-8')
        return dict(result,request=str(request),response=str(response),worker_log=str(log))

    def run_command(self,*extra):
        return invoke('dub','subtitles','--project',self.root,'--input',self.source,'--from','zh-Hans','--to','en',*extra)

    def baseline(self):
        return [(self.root/name).read_bytes() for name in ('project.json','rights-ledger.json')]

    def apply_tracks(self,allow=False):
        font = next(p for p in (Path(material_catalog.__file__).parent/'material_data/fonts').iterdir() if p.suffix.lower() in ('.ttf','.otf'))
        code,result = invoke('media','ingest','--project',self.root,'--input',font,'--asset-id','font')
        self.assertEqual(code,0,result)
        _,project = load_project(self.root)
        tracks = project['sequences'][0]['tracks']
        tracks.append(dict(id='sub',kind='subtitle',order=0,clips=[]))
        if allow:
            for track in tracks:
                track['overlap_policy']='allow'
        save_project(self.root,project)
        return ('--apply','--audio-track-id','track_audio_1','--subtitle-track-id','sub','--font-asset-id','font')

    def test_dry_run_does_not_infer_or_change_metadata(self):
        before = self.baseline()
        code,result = self.run_command('--dry-run')
        self.assertEqual(code,0,result)
        self.assertEqual(result['status'],'planned')
        self.assertFalse(result['data']['actual_audio_duration_known'])
        self.assertEqual(self.calls,[])
        self.assertEqual(before,self.baseline())
        self.assertFalse((self.root/'cache/managed-jobs').exists())

    def test_same_language_batch_preserves_text_and_initializes_voice_only(self):
        flags = self.apply_tracks()
        code,result = self.run_command(*flags,'--to','zh-Hans')
        self.assertEqual(code,0,result)
        report = json.loads(Path(result['data']['report']).read_bytes())
        self.assertEqual(report['text_mode'],'preserve-original')
        self.assertEqual(report['translation_attempts'],[])
        self.assertEqual(set(report['model_rights_refs']),{'voice'})
        self.assertEqual([c['source_text'] for c in report['cues']],[c['translation'] for c in report['cues']])
        self.assertEqual([c['text'] for c in self.calls[0]['payload']['segments']],['你好','继续前进'])
        self.assertEqual([c['task'] for c in self.calls],['voice'])
        self.assertEqual(dubbing_cli.model_context.call_args_list[0].args[1],'voice')
        self.assertEqual(dubbing_cli.model_context.call_count,1)
        self.assertFalse((Path(result['data']['report']).parent/'translation-MODEL-SOURCE.txt').exists())
        shown=[c['subtitle']['text'] for c in result['data']['clips'] if 'subtitle' in c]
        self.assertEqual(shown,['你好','继续前进'])

    def test_same_language_dry_run_needs_no_translation_runtime(self):
        before=self.baseline()
        code,result=self.run_command('--to','zh-Hans','--dry-run')
        self.assertEqual(code,0,result)
        self.assertEqual(set(result['data']['devices']),{'voice'})
        self.assertEqual(result['data']['text_mode'],'preserve-original')
        self.assertEqual(self.calls,[])
        self.assertEqual(self.baseline(),before)

    def test_apply_retains_source_translation_audio_and_portable_model_evidence(self):
        flags = self.apply_tracks()
        source = self.source.read_bytes()
        code,result = self.run_command(*flags,'--timeline-start-tick','90000')
        self.assertEqual(code,0,result)
        data = result['data']
        report = json.loads(Path(data['report']).read_text('utf-8'))
        self.assertEqual([c['source_id'] for c in report['cues']],['7','4'])
        self.assertEqual(data['model_initializations'],1)
        self.assertEqual(data['total_generations'],2)
        self.assertEqual(len(data['clips']),4)
        self.assertEqual([c['timeline_start_tick'] for c in data['clips']],[90000,90000,360000,360000])
        self.assertEqual((Path(data['report']).parent/'source.srt').read_bytes(),source)
        self.assertTrue(all((self.root/a['uri']).is_file() for a in data['assets']))
        self.assertTrue(all((Path(data['report']).parent/(task+'-MODEL-SOURCE.txt')).is_file() for task in ('voice','translation')))
        self.assertEqual(recover_workspaces(self.root)['jobs'],[])
        self.assertTrue(all(r['verification_status']=='unverified' for r in load_ledger(self.root)['records'] if r.get('kind')=='audio'))

    def test_overflow_restores_metadata_preserves_original_speech_and_can_be_cleaned(self):
        self.source.write_text('1\n00:00:00,000 --> 00:00:00,100\n你好\n',encoding='utf-8')
        before = self.baseline()
        code,result = self.run_command()
        self.assertEqual(code,2,result)
        self.assertEqual(result['errors'][0]['code'],'DUBBING_CUE_OVERFLOW')
        failure = Path(result['errors'][0]['path'])
        self.assertTrue(failure.is_file())
        self.assertEqual(dubbing.inspect_wave(next(failure.parent.rglob('*.wav')))['samples'],24000)
        self.assertEqual(before,self.baseline())
        self.assertFalse(any((self.root/'assets/derived').rglob('*')) if (self.root/'assets/derived').exists() else False)
        self.assertEqual(recover_workspaces(self.root,dry_run=True)['jobs'][0]['status'],'cleanup_planned')
        recover_workspaces(self.root)
        self.assertFalse(failure.exists())

    def test_speed_success_keeps_both_natural_and_final_assets(self):
        self.source.write_text('1\n00:00:00,000 --> 00:00:01,500\n你好\n',encoding='utf-8')
        self.engine.seconds=2.
        code,result = self.run_command('--fit','speed')
        self.assertEqual(code,0,result)
        report = json.loads(Path(result['data']['report']).read_text('utf-8'))
        attempts = report['cues'][0]['attempts']
        self.assertEqual([a['samples'] for a in attempts],[48000,34951])
        self.assertEqual(len([a for a in result['data']['assets'] if a['kind']=='audio']),2)

    def test_invalid_srt_and_wrong_voice_language_fail_before_inference(self):
        code,result = self.run_command('--voice','zf_001')
        self.assertEqual(code,2,result)
        self.assertEqual(self.calls,[])
        self.source.write_text('not subtitles',encoding='utf-8')
        self.assertEqual(self.run_command()[0],2)
        self.assertEqual(self.calls,[])

    def test_overlapping_cues_require_explicit_mix_and_allow_tracks(self):
        self.source.write_text('1\n00:00:00,000 --> 00:00:02,000\n你好\n\n2\n00:00:01,000 --> 00:00:03,000\n再见',encoding='utf-8')
        self.assertEqual(self.run_command()[0],2)
        flags = self.apply_tracks(allow=True)
        code,result = self.run_command(*flags,'--overlap-policy','mix')
        self.assertEqual(code,0,result)
        self.assertEqual(len(result['data']['clips']),4)

    def test_wrong_actual_sample_report_is_rejected_and_stage_is_removed(self):
        real = self.infer
        def tamper(*args,**kwargs):
            result = real(*args,**kwargs)
            if kwargs['task']=='voice':
                result['segments'][0]['attempts'][0]['samples']+=1
            return result
        before = self.baseline()
        with patch('ai_ad_editor.community_models.infer',side_effect=tamper):
            code,result = self.run_command()
        self.assertEqual(result['errors'][0]['code'],'DUBBING_VOICE_INVALID')
        self.assertEqual(before,self.baseline())
        self.assertEqual(recover_workspaces(self.root)['jobs'],[])

    def test_publication_failure_rolls_back_all_published_files(self):
        before = self.baseline()
        publish = Workspace.publish
        count = []
        def fail(workspace,*args):
            publish(workspace,*args)
            count.append(1)
            if len(count)==2:
                raise AppError('TEST_PUBLICATION_FAILURE','Injected after second actual file publication',exit_code=6)
        with patch.object(Workspace,'publish',fail):
            code,result = self.run_command()
        self.assertEqual(code,6,result)
        self.assertEqual(before,self.baseline())
        self.assertFalse(any(p.is_file() for p in (self.root/'assets/derived').rglob('*')))
        self.assertEqual(recover_workspaces(self.root)['jobs'],[])

    def test_idempotent_replay_does_not_generate_duplicate_speech(self):
        code,first = self.run_command('--idempotency-key','same-batch')
        self.assertEqual(code,0,first)
        calls = len(self.calls)
        code,second = self.run_command('--idempotency-key','same-batch')
        self.assertEqual(code,0,second)
        self.assertEqual(len(self.calls),calls)
        self.assertEqual(first['data']['report'],second['data']['report'])

    def test_preexisting_cancel_marker_starts_no_model(self):
        marker = self.root/'cancel'
        marker.write_text('cancel')
        before = self.baseline()
        code,result = self.run_command('--cancel-file',marker)
        self.assertEqual(code,8,result)
        self.assertEqual(self.calls,[])
        self.assertEqual(before,self.baseline())

    def test_manual_per_cue_voice_selection_is_applied_without_diarization(self):
        mapping = self.base/'voices.json'
        mapping.write_text(json.dumps({'cues':{'4':'af_sol'}}),encoding='utf-8')
        code,result = self.run_command('--voice-map',mapping)
        self.assertEqual(code,0,result)
        self.assertEqual([c[1] for c in self.engine.calls],[0,1])

    def test_auto_cuda_worker_failure_uses_a_fresh_cpu_batch_directory(self):
        context = self.context
        inference = self.infer
        observed = []
        def select(args,task):
            value = context(args,task)
            if task=='voice':
                value['config'].device='auto'
                value['device'].update(requested='auto',selected='cuda')
            return value
        def partial(root,*,task,payload,**kwargs):
            observed.append((task,payload['device'],str(root)))
            if task=='voice' and payload['device']=='cuda':
                (root/'partially-generated.wav').write_bytes(b'partial GPU attempt')
                raise AppError('COMMUNITY_MODEL_FAILED','Simulated CUDA worker failure',exit_code=6)
            return inference(root,task=task,payload=payload,**kwargs)
        with patch('ai_ad_editor.dubbing_cli.model_context',side_effect=select),patch('ai_ad_editor.community_models.infer',side_effect=partial),patch('ai_ad_editor.community_models.verify_pack',return_value=(self.pack,self.manifest)):
            code,result = self.run_command()
        self.assertEqual(code,0,result)
        self.assertEqual([(task,provider) for task,provider,_ in observed],[('translate','cpu'),('voice','cuda'),('voice','cpu')])
        self.assertNotEqual(observed[-2][2],observed[-1][2])
        self.assertEqual(result['data']['devices']['voice']['fallback_reason'],'cuda_inference_failed')
        self.assertEqual(recover_workspaces(self.root)['jobs'],[])

    def test_cancelled_worker_is_not_retried_as_a_gpu_failure(self):
        before = self.baseline()
        with patch('ai_ad_editor.community_models.infer',side_effect=AppError('CANCELLED','Simulated active cancellation',exit_code=8)) as worker:
            code,result = self.run_command()
        self.assertEqual(code,8,result)
        self.assertEqual(worker.call_count,1)
        self.assertEqual(before,self.baseline())
        self.assertEqual(recover_workspaces(self.root)['jobs'],[])

    def test_total_deadline_includes_translation_and_prevents_later_voice(self):
        import time
        inference = self.infer
        before = self.baseline()
        def delayed(*args,**kwargs):
            result = inference(*args,**kwargs)
            time.sleep(.1)
            return result
        with patch('ai_ad_editor.community_models.infer',side_effect=delayed):
            code,result = self.run_command('--timeout-seconds','.05')
        self.assertEqual(code,6,result)
        self.assertEqual(result['errors'][0]['code'],'PROCESS_TIMEOUT')
        self.assertFalse(any(call['task']=='voice' for call in self.calls))
        self.assertEqual(before,self.baseline())

    def test_malformed_model_metadata_returns_structured_error_and_rolls_back(self):
        self.manifest['models'] = list(self.manifest['models'].values())
        before = self.baseline()
        code,result = self.run_command()
        self.assertEqual(code,9,result)
        self.assertEqual(result['errors'][0]['code'],'DUBBING_RESPONSE_INVALID')
        self.assertEqual(before,self.baseline())
        self.assertEqual(recover_workspaces(self.root)['jobs'],[])


class ExtendedWorkspaceTests(unittest.TestCase):
    def test_more_than_128_outputs_recover_and_committed_license_is_protected(self):
        with tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp']) as directory:
            root,_ = create_project(Path(directory)/'project')
            workspace = Workspace(root,'subtitle-dubbing')
            for i in range(140):
                stage = workspace.path/str(i)
                stage.write_bytes(str(i).encode())
                workspace.publish(stage,root/'assets/derived'/str(i))
            ledger = load_ledger(root)
            protected = root/'assets/derived/0'
            add_record(ledger,dict(asset_id='model',kind='model',sha256='sha256:'+'1'*64,evidence='assets/derived/0',
                license_spdx='MIT',verification_status='unverified',permitted_uses=['internal']))
            save_ledger(root,ledger)
            workspace.lease.close()
            result = recover_workspaces(root)
            self.assertEqual(result['cleaned'],1)
            self.assertTrue(protected.is_file())
            self.assertFalse((root/'assets/derived/1').exists())


if __name__=='__main__':
    unittest.main()
