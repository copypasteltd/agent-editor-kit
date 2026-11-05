from __future__ import annotations

import array
import contextlib
import copy
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_separation import DEMUCS_ENGINE, DEMUCS_PROTOCOL, manifest_hash, settings
from ai_ad_editor.model_registry import verify_audio_adapter
from ai_ad_editor.project import ledger_file
from ai_ad_editor.rights import check_project_rights, load_ledger
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.separation_dsp import segment_ranges, separate_pcm
from ai_ad_editor.utils import atomic_write_json, run_process, sha256_file

BASE_RUN = run_process


def invoke(*argv):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(list(argv))
    return code, json.loads(output.getvalue())


class OverlapAddTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='separation-dsp-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def separate(self, data, infer, *, overlap=.25, window=128):
        source, vocals, accompaniment = (self.root / name for name in ('input.f32', 'vocals.f32', 'accompaniment.f32'))
        np.asarray(data, dtype='<f4').tofile(source)
        result = separate_pcm(source, vocals, accompaniment, window=window, overlap=overlap, infer=infer)
        return result, np.fromfile(vocals, dtype='<f4').reshape(-1, 2), np.fromfile(accompaniment, dtype='<f4').reshape(-1, 2)

    def test_segment_coverage_and_tail_without_redundant_final_chunk(self):
        for samples in (1, 7, 128, 129, 1000):
            for overlap in (0, .25, .75):
                ranges = segment_ranges(samples, 128, overlap)
                self.assertEqual(ranges[0][0], 0)
                self.assertEqual(ranges[-1][1], samples)
                coverage = np.zeros(samples, dtype=int)
                for start, end in ranges:
                    coverage[start:end] += 1
                self.assertTrue((coverage > 0).all())
                self.assertEqual(sum(end == samples for _, end in ranges), 1)
        for values in ((0, 128, .25), (1, 0, .25), (10, 10, .76), (10, 10, math.nan)):
            with self.assertRaises(ValueError):
                segment_ranges(*values)

    def test_overlap_tail_and_dc_reconstruct_known_gain_without_clipping(self):
        for samples in (1, 7, 129, 8193):
            for overlap in (0, .25, .75):
                with self.subTest(samples=samples, overlap=overlap):
                    data = np.random.default_rng(samples).normal(.3, .2, (samples, 2)).astype('float32')
                    data[0, 0] = 4; data[-1, 1] = -3
                    report, vocals, accompaniment = self.separate(data, lambda x: x * .25, overlap=overlap)
                    np.testing.assert_allclose(vocals, data * .25, atol=2e-6)
                    np.testing.assert_allclose(vocals + accompaniment, data, atol=2e-6)
                    self.assertEqual(vocals.shape, data.shape)
                    self.assertLess(report['mixture_max_abs_error'], 2e-6)
                    self.assertFalse((self.root / 'vocals.weights.f32').exists())

    def test_silence_skips_model_and_preserves_all_samples(self):
        def forbidden(_):
            self.fail('silence should not invoke model')
        report, vocals, accompaniment = self.separate(np.zeros((513, 2)), forbidden)
        self.assertTrue(report['silence_fast_path'])
        self.assertEqual(report['model_calls'], 0)
        self.assertEqual(vocals.shape, (513, 2))
        self.assertEqual(np.count_nonzero(vocals) + np.count_nonzero(accompaniment), 0)

    def test_antiphase_stereo_has_finite_normalization(self):
        left = np.sin(np.arange(1001) * .1).astype('float32')
        data = np.stack((left, -left), axis=1)
        report, vocals, accompaniment = self.separate(data, lambda x: x * .25)
        self.assertGreater(report['normalization_std'], .1)
        np.testing.assert_allclose(vocals, data * .25, atol=2e-6)
        np.testing.assert_allclose(vocals + accompaniment, data, atol=2e-6)

    def test_nonfinite_and_malformed_input_release_windows_mapping(self):
        source = self.root / 'invalid.f32'
        for data in (b'abc', np.array([math.nan, 0], dtype='<f4').tobytes()):
            source.write_bytes(data)
            with self.assertRaises(ValueError):
                separate_pcm(source, self.root / 'v.f32', self.root / 'a.f32', window=8, overlap=.25, infer=lambda x: x)
            source.unlink()

    def test_wrong_shape_and_nonfinite_model_output_reject_without_weight_leak(self):
        for callback in (lambda x: x[:, :-1], lambda x: np.full_like(x, math.nan)):
            with self.assertRaisesRegex(ValueError, 'Invalid model vocal'):
                self.separate(np.ones((129, 2)), callback)
            self.assertFalse((self.root / 'vocals.weights.f32').exists())
            for name in ('input.f32', 'vocals.f32', 'accompaniment.f32'):
                (self.root / name).unlink(missing_ok=True)


class NativeSeparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agent-separation-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / '中文项目'
        self.assertEqual(invoke('project', 'init', str(self.root))[0], 0)
        self.model = self.base / 'model.pt'
        self.model.write_bytes(b'protocol fixture; actual inference is tested separately with real weights')
        self.evidence = self.base / 'evidence.json'
        atomic_write_json(self.evidence, {'use': 'internal synthetic test fixture only'})
        source = self.base / 'source.wav'
        values = array.array('h', (round(9000 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(5003)))
        if sys.byteorder != 'little': values.byteswap()
        with wave.open(str(source), 'wb') as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(16000)
            stream.writeframes(values.tobytes())
        code, value = invoke('media', 'ingest', '--project', str(self.root), '--input', str(source), '--license-spdx', 'CC0-1.0', '--verification-status', 'verified', '--permitted-use', 'commercial_ad', '--evidence', str(self.evidence))
        self.assertEqual(code, 0, value)
        self.asset_id = value['data']['asset']['id']
        self.options = ['--project', str(self.root), '--adapter-id', 'hdemucs', '--engine', DEMUCS_ENGINE, '--model-path', str(self.model), '--executable', sys.executable, '--evidence', str(self.evidence), '--segment-seconds', '1']
        self.worker_calls = 0
        self.payload_change = None
        self.output_change = None

    def project(self):
        return json.loads((self.root / 'project.json').read_text(encoding='utf-8'))

    def metadata(self):
        files = [self.root / 'project.json', self.root / 'project.lock.json', ledger_file(self.root), self.root / 'models/audio-adapters.json']
        return tuple(p.read_bytes() if p.exists() else None for p in files)

    def register(self):
        code, value = invoke('audio', 'adapter', 'register', *self.options)
        self.assertEqual(code, 0, value)
        return value

    def separate_options(self, *, stem='vocals'):
        return ['audio', 'separate', '--project', str(self.root), '--asset-id', self.asset_id, '--adapter-id', 'hdemucs', '--vocals-asset-id', 'vocals', '--accompaniment-asset-id', 'accompaniment', '--stem', stem, '--track-id', 'track_audio_1', '--apply']

    def fake_runner(self, argv, **kwargs):
        if any(str(item).endswith('demucs_worker.py') for item in argv):
            self.worker_calls += 1
            self.assertIn('-I', argv); self.assertIn('-B', argv)
            request = json.loads(Path(argv[-1]).read_text(encoding='utf-8'))
            self.assertEqual(request['network'], 'disabled')
            data = np.fromfile(request['input'], dtype='<f4').reshape(-1, 2)
            outputs = {}
            peaks = {}
            for role, gain in (('vocals', .25), ('accompaniment', .75)):
                path = Path(request['outputs'][role]); (data * gain).astype('<f4').tofile(path)
                outputs[role] = {'sha256': 'sha256:' + sha256_file(path), 'bytes': path.stat().st_size}
                peaks[role] = float(np.abs(data * gain).max())
            payload = {'protocol': DEMUCS_PROTOCOL, 'status': 'succeeded', 'network': 'disabled', 'blocked_network_events': [], 'input_sha256': request['input_sha256'], 'source_sha256': request['source_sha256'], 'samples': request['samples'], 'adapter_sha256': request['adapter']['sha256'], 'outputs': outputs, 'metrics': {'samples': request['samples'], 'channels': 2, 'normalization_mean': 0, 'normalization_std': 1, 'mixture_max_abs_error': 0, 'peaks': peaks}}
            if self.payload_change: self.payload_change(payload)
            if self.output_change: self.output_change(request)
            atomic_write_json(Path(request['response']), payload)
            return subprocess.CompletedProcess(argv, 0, '', '')
        return BASE_RUN(argv, **kwargs)

    def decode(self, path, rate=44100):
        result = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(path), '-ar', str(rate), '-ac', '2', '-f', 'f32le', 'pipe:1'], capture_output=True, check=True)
        return np.frombuffer(result.stdout, dtype='<f4').reshape(-1, 2)

    def assert_no_outputs(self):
        self.assertFalse((self.root / 'assets/derived/vocals.wav').exists())
        self.assertFalse((self.root / 'assets/derived/accompaniment.wav').exists())
        self.assertFalse(list((self.root / 'cache/audio-separation').glob('hdemucs-*')))
        self.assertFalse((self.root / 'operations/project-transaction.json').exists())

    def test_registration_dry_run_and_read_only_inspection(self):
        before = self.metadata()
        with patch('ai_ad_editor.local_separation.run_process') as runner:
            code, value = invoke('audio', 'adapter', 'register', *self.options, '--dry-run')
            self.assertEqual(code, 0, value)
            self.assertEqual(self.metadata(), before)
            registered = self.register()
            before = self.metadata()
            for action in ('list', 'inspect'):
                extra = ['--adapter-id', 'hdemucs'] if action == 'inspect' else []
                code, value = invoke('audio', 'adapter', action, '--project', str(self.root), *extra)
                self.assertEqual(code, 0, value)
                self.assertEqual(self.metadata(), before)
            runner.assert_not_called()
        adapter = registered['data']['adapter']
        self.assertEqual(len(adapter['artifacts']), 6)
        self.assertTrue(verify_audio_adapter(adapter)['ok'])

    def test_registration_requires_local_weights_python_and_evidence(self):
        for flag, value in (('--model-path', 'https://invalid.example/model.pt'), ('--evidence', 'https://invalid.example/evidence'), ('--executable', str(self.base / 'python.cmd')), ('--evidence', str(self.base / 'missing.json'))):
            options = list(self.options); options[options.index(flag) + 1] = value
            with self.subTest(flag=flag, value=value):
                code, result = invoke('audio', 'adapter', 'register', *options)
                self.assertNotEqual(code, 0, result)
                self.assertFalse((self.root / 'models/audio-adapters.json').exists())

    def test_invalid_device_segment_threads_and_overlap_are_rejected(self):
        for options in ({'device': 'auto'}, {'threads': 0}, {'threads': True}, {'segment_seconds': .5}, {'segment_seconds': math.inf}, {'overlap': -.1}, {'overlap': .8}, {'overlap': math.nan}):
            with self.subTest(options=options), self.assertRaises(AppError):
                settings(**options)

    def test_model_evidence_and_manifest_tampering_fail_before_worker(self):
        adapter = self.register()['data']['adapter']
        for path in (self.model, self.evidence):
            before = path.read_bytes(); path.write_bytes(before + b'tampered')
            with patch('ai_ad_editor.cli.separate_native') as runner:
                code, value = invoke(*self.separate_options())
                self.assertEqual(code, 10, value); runner.assert_not_called()
            path.write_bytes(before)
        changed = copy.deepcopy(adapter); changed['settings']['device'] = 'cuda'
        self.assertFalse(verify_audio_adapter(changed)['ok'])
        changed['settings']['sample_rate'] = 16000; changed['sha256'] = manifest_hash(changed)
        self.assertFalse(verify_audio_adapter(changed)['ok'])

    def test_native_dry_run_semantic_stems_and_preflight_do_not_infer(self):
        self.register(); before = self.metadata()
        with patch('ai_ad_editor.cli.separate_native') as runner:
            code, value = invoke(*self.separate_options(), '--dry-run')
            self.assertEqual(code, 0, value)
            self.assertEqual(value['data']['method'], 'hdemucs')
            self.assertIn('vocals', value['data']); self.assertIn('accompaniment', value['data'])
            for extra in (['--stem', 'center'], ['--track-id', 'track_video_1'], ['--sample-rate', '12345']):
                code, value = invoke(*self.separate_options(), *extra)
                self.assertNotEqual(code, 0, value)
            runner.assert_not_called()
        self.assertEqual(self.metadata(), before)

    def test_native_stems_exact_samples_roles_rights_and_local_policy(self):
        self.register()
        source = self.root / self.project()['assets'][0]['uri']
        with patch('ai_ad_editor.local_separation.run_process', side_effect=self.fake_runner):
            code, value = invoke(*self.separate_options())
        self.assertEqual(code, 0, value)
        stems = value['data']['assets']
        self.assertEqual(set(stems), {'vocals', 'accompaniment'})
        vocal = self.decode(self.root / stems['vocals']['uri'])
        accompaniment = self.decode(self.root / stems['accompaniment']['uri'])
        mixture = self.decode(source)
        self.assertEqual(vocal.shape, mixture.shape)
        np.testing.assert_allclose(vocal + accompaniment, mixture, atol=1e-6)
        self.assertEqual(value['data']['generated_clip']['asset_id'], 'vocals')
        for role in stems:
            rights = value['data']['rights'][role]
            self.assertEqual(set(rights['derived_from']), {self.asset_id, 'audio_adapter_hdemucs'})
            self.assertIn(role, rights['notes'])
        code, audit = invoke('policy', 'audit', '--project', str(self.root))
        self.assertEqual(code, 0, audit)
        rights = check_project_rights(self.project(), load_ledger(self.root))
        self.assertFalse(rights['ok'])
        self.assertIn('audio_adapter_hdemucs', str(rights))

    def test_accompaniment_selection_and_resampled_duration(self):
        self.register()
        with patch('ai_ad_editor.local_separation.run_process', side_effect=self.fake_runner):
            code, value = invoke(*self.separate_options(stem='accompaniment'), '--sample-rate', '48000')
        self.assertEqual(code, 0, value)
        self.assertEqual(value['data']['generated_clip']['asset_id'], 'accompaniment')
        worker_samples = value['data']['separation']['worker']['samples']
        for stem in value['data']['separation']['stems'].values():
            self.assertEqual(stem['samples'], round(worker_samples * 48000 / 44100))
            self.assertEqual(stem['probe']['audio']['sample_rate'], 48000)

    def test_invalid_worker_protocol_hash_samples_network_and_metrics_rollback(self):
        self.register(); before = self.metadata()
        mutations = [lambda p: p.update(protocol='wrong'), lambda p: p.update(input_sha256='sha256:' + '0' * 64), lambda p: p.update(samples=p['samples'] - 1), lambda p: p.update(blocked_network_events=['socket.connect']), lambda p: p['metrics'].update(normalization_std=math.nan)]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.payload_change = mutation
                with patch('ai_ad_editor.local_separation.run_process', side_effect=self.fake_runner):
                    code, value = invoke(*self.separate_options())
                self.assertEqual(code, 6, value)
                self.assertEqual(self.metadata(), before)
                self.assert_no_outputs()

    def test_tampered_worker_pcm_is_rejected_before_registration(self):
        self.register(); before = self.metadata()
        self.output_change = lambda request: Path(request['outputs']['accompaniment']).write_bytes(b'invalid')
        with patch('ai_ad_editor.local_separation.run_process', side_effect=self.fake_runner):
            code, value = invoke(*self.separate_options())
        self.assertEqual(code, 6, value)
        self.assertEqual(self.metadata(), before); self.assert_no_outputs()

    def test_second_wav_encoding_failure_removes_first_output(self):
        self.register(); before = self.metadata()
        def fail_second(argv, **kwargs):
            if str(argv[-1]).endswith('accompaniment.wav'):
                return subprocess.CompletedProcess(argv, 1, '', 'injected encode failure')
            return self.fake_runner(argv, **kwargs)
        with patch('ai_ad_editor.local_separation.run_process', side_effect=fail_second):
            code, value = invoke(*self.separate_options())
        self.assertEqual(code, 6, value)
        self.assertEqual(self.metadata(), before); self.assert_no_outputs()

    def test_metadata_commit_failure_restores_project_ledger_registry_and_outputs(self):
        self.register(); before = self.metadata()
        with patch('ai_ad_editor.local_separation.run_process', side_effect=self.fake_runner), patch('ai_ad_editor.cli.save_project', side_effect=AppError('TEST_COMMIT_FAILED', 'injected failure', exit_code=6)):
            code, value = invoke(*self.separate_options())
        self.assertEqual(code, 6, value)
        self.assertEqual(self.metadata(), before); self.assert_no_outputs()

    def test_idempotency_does_not_repeat_inference(self):
        self.register()
        with patch('ai_ad_editor.local_separation.run_process', side_effect=self.fake_runner):
            first_code, first = invoke(*self.separate_options(), '--idempotency-key', 'one-separation')
            repeat_code, repeat = invoke(*self.separate_options(), '--idempotency-key', 'one-separation')
        self.assertEqual(first_code, 0, first); self.assertEqual(repeat_code, 0, repeat)
        self.assertEqual(first['operation_id'], repeat['operation_id'])
        self.assertEqual(self.worker_calls, 1)

    def test_source_tamper_and_existing_output_stop_before_inference(self):
        self.register()
        output = self.root / 'assets/keep.wav'; output.write_bytes(b'preserve')
        with patch('ai_ad_editor.cli.separate_native') as runner:
            code, value = invoke(*self.separate_options(), '--vocals-output', str(output))
            self.assertEqual(code, 2, value)
            self.assertEqual(output.read_bytes(), b'preserve')
            source = self.root / self.project()['assets'][0]['uri']
            source.write_bytes(source.read_bytes() + b'tamper')
            code, value = invoke(*self.separate_options())
            self.assertEqual(code, 10, value); runner.assert_not_called()

    def test_registry_survives_project_package_and_restores_before_registration(self):
        registered = self.register()
        package = self.base / 'project.aevpkg.zip'
        code, value = invoke('convert', 'export', '--project', str(self.root), '--target-format', 'package', '--output', str(package))
        self.assertEqual(code, 0, value)
        restored_root = self.base / 'restored'
        code, value = invoke('convert', 'import', '--input', str(package), '--output', str(restored_root))
        self.assertEqual(code, 0, value)
        code, value = invoke('audio', 'adapter', 'inspect', '--project', str(restored_root), '--adapter-id', 'hdemucs')
        self.assertEqual(code, 0, value); self.assertTrue(value['data']['verification']['ok'])
        with zipfile.ZipFile(package) as archive:
            self.assertFalse(any(name.endswith('.pt') for name in archive.namelist()))
        code, value = invoke('project', 'restore', '--project', str(self.root), '--snapshot', registered['data']['snapshot']['snapshot_id'])
        self.assertEqual(code, 0, value)
        self.assertFalse((self.root / 'models/audio-adapters.json').exists())

    def test_worker_network_guard_rejects_dns_in_isolated_python(self):
        worker = Path(__file__).resolve().parents[1] / 'src/ai_ad_editor/demucs_worker.py'
        script = "import runpy,sys,socket; ns=runpy.run_path(sys.argv[1]); events=[]; ns['install_network_guard'](events)\ntry: socket.getaddrinfo('invalid.example',443)\nexcept RuntimeError: pass\nelse: raise AssertionError('network guard failed')\nassert events == ['socket.getaddrinfo']"
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(worker)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_worker_bad_protocol_returns_structured_failure_without_loading_model(self):
        worker = Path(__file__).resolve().parents[1] / 'src/ai_ad_editor/demucs_worker.py'
        response = self.base / 'failure.json'; request = self.base / 'request.json'
        atomic_write_json(request, {'protocol': 'invalid', 'network': 'disabled', 'response': str(response)})
        result = subprocess.run([sys.executable, '-I', '-B', str(worker), str(request)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(response.read_text(encoding='utf-8'))['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
