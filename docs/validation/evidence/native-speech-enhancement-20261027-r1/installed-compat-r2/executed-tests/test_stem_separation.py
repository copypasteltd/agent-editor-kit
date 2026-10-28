"""Signal and failure contracts; genuine model quality is measured separately."""
from __future__ import annotations

import contextlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import ledger_file
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor import stem_separation as native
from ai_ad_editor.stem_separation_dsp import ROLES, separate_pcm
from ai_ad_editor.utils import atomic_write_json, run_process, sha256_file

BASE_RUN = run_process


def invoke(*args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream): code = main(list(args))
    return code, json.loads(stream.getvalue())


class FourSourceDSPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'source.f32'
        self.outputs = {role:self.root/(role+'.f32') for role in ROLES}

    def separate(self, data, infer, *, overlap=.25):
        np.asarray(data,dtype='<f4').tofile(self.source)
        return separate_pcm(self.source,self.outputs,window=128,overlap=overlap,infer=infer)

    def clear(self):
        for path in self.outputs.values(): path.unlink(missing_ok=True)

    def test_all_model_sources_tail_dc_and_high_peaks_are_preserved(self):
        # Distinct nonlinear predictions expose a dropped, reordered or residual stem.
        for count in (1, 127, 128, 129, 1103):
            for overlap in (0,.25,.75):
                data = np.random.default_rng(count).normal(.3,.2,(count,2)).astype('<f4')
                data[0,0] = 4; data[-1,1] = -3
                def infer(x): return np.stack((x*.1,x*.2,x*.3,x*.7))
                metrics = self.separate(data,infer,overlap=overlap)
                mean = metrics['normalization_mean']
                for role,gain in zip(ROLES,(.1,.2,.3,.7)):
                    actual = np.fromfile(self.outputs[role],dtype='<f4').reshape(-1,2)
                    np.testing.assert_allclose(actual,(data-mean)*gain+mean/4,atol=2e-6)
                self.assertEqual(metrics['mixture_projection'],'none')
                self.assertGreater(metrics['raw_sum_max_abs_error'],.01)
                self.assertEqual(metrics['samples'],count)
                self.clear()

    def test_silence_skips_model_and_closes_windows_mappings(self):
        def forbidden(_): self.fail('Silent input must not run a model forward')
        metrics = self.separate(np.zeros((513,2)),forbidden)
        self.assertEqual(metrics['model_calls'],0)
        for path in self.outputs.values():
            self.assertEqual(np.count_nonzero(np.fromfile(path,dtype='<f4')),0)
            path.unlink()
        self.source.unlink()
        self.assertFalse(list(self.root.glob('*.weights.f32')))

    def test_antiphase_keeps_finite_shared_normalization(self):
        x = np.sin(np.arange(8193)*.1).astype('<f4'); data = np.stack((x,-x),axis=1)
        metrics = self.separate(data,lambda x:np.stack([x*.25]*4))
        self.assertGreater(metrics['normalization_std'],.5)
        for path in self.outputs.values():
            actual = np.fromfile(path,dtype='<f4').reshape(-1,2)
            np.testing.assert_allclose(actual,data*.25,atol=2e-6)

    def test_bad_shape_nan_and_exception_clean_all_partial_files(self):
        for callback in (lambda x:np.stack([x]*3),lambda x:np.full((4,2,128),np.nan),
                         lambda x:(_ for _ in ()).throw(RuntimeError('injected model failure'))):
            with self.assertRaises((ValueError,RuntimeError)):
                self.separate(np.ones((1003,2)),callback)
            self.assertFalse(any(path.exists() for path in self.outputs.values()))
            self.assertFalse(list(self.root.glob('*.weights.f32')))
            self.source.unlink()

    def test_malformed_nonfinite_and_existing_output_preserved(self):
        for data in (b'abc',np.array([np.inf,0],dtype='<f4').tobytes()):
            self.source.write_bytes(data)
            with self.assertRaises(ValueError):
                separate_pcm(self.source,self.outputs,window=128,overlap=.25,infer=lambda x:x)
            self.source.unlink()
        self.outputs['bass'].write_bytes(b'keep')
        self.source.write_bytes(np.zeros((2,2),dtype='<f4').tobytes())
        with self.assertRaises(ValueError):
            separate_pcm(self.source,self.outputs,window=128,overlap=.25,infer=lambda x:x)
        self.assertEqual(self.outputs['bass'].read_bytes(),b'keep')


class FourSourceCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): configure_local_runtime()

    def setUp(self):
        runtime = configure_local_runtime()
        self.temp = tempfile.TemporaryDirectory(prefix='four-stem-',dir=runtime['temp']); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base/'中文 工程'
        self.call('project','init',str(self.root))
        self.model = self.base/'model.pt'; self.model.write_bytes(b'protocol-only fixture, not real model inference')
        self.evidence = self.base/'evidence.json'; atomic_write_json(self.evidence,dict(scope='internal test'))
        source = self.base/'source.wav'
        with wave.open(str(source),'wb') as stream:
            stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(16000)
            x = np.sin(np.arange(5003)*2*np.pi*440/16000)*10000
            stream.writeframes(np.stack((x,x*.7),axis=1).astype('<i2').tobytes())
        self.asset = self.call('media','ingest','--project',str(self.root),'--input',str(source),
            '--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','commercial_ad',
            '--evidence',str(self.evidence))['data']['asset']['id']
        self.options = ['audio','adapter','register','--project',str(self.root),'--adapter-id','four',
            '--engine',native.ENGINE,'--model-path',str(self.model),'--executable',sys.executable,
            '--evidence',str(self.evidence),'--segment-seconds','1']
        self.command = ['audio','separate-stems','--project',str(self.root),'--asset-id',self.asset,
            '--adapter-id','four','--prefix','test','--device','cpu','--apply']
        self.calls = 0; self.mutate = None

    def call(self,*args,expected=0):
        code,value = invoke(*args); self.assertEqual(code,expected,value); return value

    def metadata(self):
        return tuple(path.read_bytes() if path.exists() else None for path in
            (self.root/'project.json',self.root/'project.lock.json',ledger_file(self.root),self.root/'models/audio-adapters.json'))

    def register(self): return self.call(*self.options)

    def runner(self,argv,**kwargs):
        if any(str(value).endswith('stem_separation_worker.py') for value in argv):
            self.calls += 1
            request = json.loads(Path(argv[-1]).read_text('utf-8'))
            self.assertIn('-I',argv); self.assertIn('-B',argv)
            outputs = {role:Path(path) for role,path in request['outputs'].items()}
            metrics = separate_pcm(Path(request['input']),outputs,window=44100,overlap=.25,
                infer=lambda x:np.stack([x*gain for gain in (.1,.2,.3,.4)]))
            payload = {key:request[key] for key in ('protocol','request_sha256','input_sha256','source_sha256','samples','device','device_index')}
            payload.update(status='succeeded',network='disabled',blocked_network_events=[],adapter_sha256=request['adapter']['sha256'],
                metrics=metrics,outputs={role:dict(sha256='sha256:'+sha256_file(path),bytes=path.stat().st_size) for role,path in outputs.items()})
            if self.mutate: self.mutate(request,payload)
            atomic_write_json(Path(request['response']),payload)
            return subprocess.CompletedProcess(argv,0,'','')
        return BASE_RUN(argv,**kwargs)

    def assert_clean(self,before):
        self.assertEqual(self.metadata(),before)
        self.assertFalse(list((self.root/'assets/derived').glob('test_*.wav')))
        self.assertFalse(list((self.root/'cache/four-stem-separation').glob('hdemucs-*')))
        self.assertFalse((self.root/'operations/project-transaction.json').exists())

    def test_default_gpu_preference_and_readonly_dry_run(self):
        before = self.metadata()
        planned = self.call(*self.options,'--dry-run')
        self.assertEqual(planned['data']['adapter']['settings']['device'],'auto')
        self.assertEqual(self.metadata(),before)
        self.register(); before = self.metadata()
        with patch('ai_ad_editor.stem_separation.run_process') as runner:
            self.call(*self.command,'--dry-run'); runner.assert_not_called()
        self.assertEqual(self.metadata(),before)

    def test_four_independent_assets_tracks_samples_rights_and_source_preserved(self):
        self.register()
        before_project = json.loads((self.root/'project.json').read_text('utf-8'))
        with patch('ai_ad_editor.stem_separation.run_process',side_effect=self.runner):
            value = self.call(*self.command,'--sample-rate','48000','--timeline-start-seconds','1.2')
        data = value['data']; self.assertEqual(set(data['assets']),set(ROLES))
        project = json.loads((self.root/'project.json').read_text('utf-8'))
        for role in ROLES:
            self.assertEqual(data['rights'][role]['derived_from'],[self.asset,'audio_adapter_four'])
            self.assertEqual(data['assets'][role]['probe']['audio']['sample_rate'],48000)
            self.assertEqual(data['separation']['stems'][role]['samples'],round(data['separation']['worker']['samples']*48000/44100))
            self.assertEqual(data['generated_tracks'][role]['clip']['timeline_start_tick'],108000)
        self.assertEqual(project['sequences'][0]['tracks'][:2],before_project['sequences'][0]['tracks'][:2])
        self.call('validate','--project',str(self.root)); self.call('policy','audit','--project',str(self.root))
        self.call('rights','check','--project',str(self.root),expected=7)

    def test_bad_protocol_shape_network_hash_device_and_metrics_roll_back(self):
        self.register(); before = self.metadata()
        mutations = [lambda r,p:p.update(protocol='bad'),lambda r,p:p.update(request_sha256='bad'),
            lambda r,p:p.update(device='cuda'),lambda r,p:p.update(blocked_network_events=['socket.connect']),
            lambda r,p:p['metrics'].update(raw_sum_rms_error=math.nan),lambda r,p:p['metrics'].update(mixture_projection='residual'),
            lambda r,p:p['outputs'].pop('bass'),lambda r,p:Path(r['outputs']['other']).write_bytes(b'tampered')]
        for mutation in mutations:
            self.mutate = mutation
            with patch('ai_ad_editor.stem_separation.run_process',side_effect=self.runner):
                self.call(*self.command,expected=6)
            self.assert_clean(before)

    def test_late_encode_and_metadata_failure_clean_four_outputs(self):
        self.register(); before = self.metadata()
        def late_fail(argv,**kwargs):
            if str(argv[-1]).endswith('vocals.wav'):
                return subprocess.CompletedProcess(argv,1,'','injected last encoder failure')
            return self.runner(argv,**kwargs)
        with patch('ai_ad_editor.stem_separation.run_process',side_effect=late_fail): self.call(*self.command,expected=6)
        self.assert_clean(before)
        with patch('ai_ad_editor.stem_separation.run_process',side_effect=self.runner), patch('ai_ad_editor.stem_separation_cli.save_project',side_effect=AppError('INJECTED','failure',exit_code=6)):
            self.call(*self.command,expected=6)
        self.assert_clean(before)

    def test_precancel_and_invalid_execution_never_start_worker(self):
        self.register(); before = self.metadata()
        marker = self.root/'cancel'; marker.touch()
        with patch('ai_ad_editor.stem_separation.run_process') as runner:
            self.call(*self.command,'--cancel-file',str(marker),expected=8)
            for extra in (['--timeout-seconds','nan'],['--device-index','32'],['--timeline-start-seconds','inf'],['--sample-rate','12345']):
                self.call(*self.command,*extra,expected=2)
            runner.assert_not_called()
        self.assert_clean(before)

    def test_output_id_source_or_model_tampering_stop_before_inference(self):
        self.register(); before = self.metadata()
        output = self.root/'assets/derived/test_bass.wav'; output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(b'keep')
        with patch('ai_ad_editor.stem_separation.run_process') as runner:
            self.call(*self.command,expected=2); self.assertEqual(output.read_bytes(),b'keep'); output.unlink()
            self.model.write_bytes(b'changed model'); self.call(*self.command,expected=10)
            runner.assert_not_called()
        self.assert_clean(before)

    def test_inflight_cancel_cleanup_and_gpu_selection_fail_without_fallback(self):
        self.register(); before = self.metadata()
        def cancel(argv,**kwargs):
            if any(str(v).endswith('stem_separation_worker.py') for v in argv):
                raise AppError('CANCELLED','injected running worker cancellation',exit_code=8)
            return self.runner(argv,**kwargs)
        with patch('ai_ad_editor.stem_separation.run_process',side_effect=cancel): self.call(*self.command,expected=8)
        self.assert_clean(before)
        with patch('ai_ad_editor.community_device.inspect',return_value=dict(gpus=[],available=False)):
            self.call(*self.command,'--device','cuda',expected=10)
        self.assert_clean(before)

    def test_gpu_auto_preflight_fallback_is_reported(self):
        self.register()
        with patch('ai_ad_editor.community_device.inspect',return_value=dict(gpus=[],available=False)), patch('ai_ad_editor.stem_separation.run_process',side_effect=self.runner):
            result = self.call(*self.command,'--device','auto')
        decision = result['data']['separation']['device_selection']
        self.assertEqual(decision['selected'],'cpu'); self.assertEqual(decision['fallback_reason'],'gpu_not_available')

    def test_idempotent_replay_does_not_repeat_model(self):
        self.register()
        with patch('ai_ad_editor.stem_separation.run_process',side_effect=self.runner):
            first = self.call(*self.command,'--idempotency-key','four-once')
            again = self.call(*self.command,'--idempotency-key','four-once')
        self.assertEqual(first['operation_id'],again['operation_id']); self.assertEqual(self.calls,1)

    def test_package_roundtrip_keeps_four_editable_tracks_without_weights(self):
        self.register()
        with patch('ai_ad_editor.stem_separation.run_process',side_effect=self.runner): self.call(*self.command)
        package = self.base/'four.aevpkg.zip'
        self.call('convert','export','--project',str(self.root),'--target-format','package','--output',str(package))
        restored = self.base/'restored'
        self.call('convert','import','--input',str(package),'--output',str(restored))
        self.call('validate','--project',str(restored))
        data = json.loads((restored/'project.json').read_text('utf-8'))
        self.assertEqual(sum(t['id'].startswith('track_test_') for t in data['sequences'][0]['tracks']),4)


if __name__ == '__main__': unittest.main()
