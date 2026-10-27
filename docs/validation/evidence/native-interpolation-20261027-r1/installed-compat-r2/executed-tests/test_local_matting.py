from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_matting import MATTING_ENGINE, manifest_hash, prepare_plan, settings, verify_adapter
from ai_ad_editor.matting_frames import pack_rgba, process_frames
from ai_ad_editor.media import probe_media
from ai_ad_editor.project import ledger_file
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json


def invoke(*argv):
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        code = main(list(argv))
    return code, json.loads(capture.getvalue())


class MattingFrameTests(unittest.TestCase):
    def test_soft_alpha_multiplies_existing_alpha_without_premultiplying_rgb(self):
        fgr = np.full((1, 3, 1, 3), .8, dtype=np.float32)
        alpha = np.full((1, 1, 1, 3), .5, dtype=np.float32)
        packed = pack_rgba(fgr, alpha, np.array([[0, 128, 255]], dtype=np.uint8))
        np.testing.assert_array_equal(packed[:, :, :3], 204)
        np.testing.assert_array_equal(packed[:, :, 3], [[0, 64, 128]])

    def test_partial_pipe_reads_and_recurrent_states_are_preserved(self):
        class Partial(io.BytesIO):
            def read(self, size=-1):
                return super().read(min(size, 7))
        frames = np.full((3, 16, 16, 4), 255, dtype=np.uint8)
        seen = []
        def infer(rgb, states):
            seen.append([float(s.flat[0]) for s in states])
            return [rgb, np.full((1, 1, 16, 16), .5, np.float32), *[s + 1 for s in states]]
        output = io.BytesIO()
        report = process_frames(Partial(frames.tobytes()), output, width=16, height=16, frames=3, infer=infer)
        self.assertEqual(seen, [[0] * 4, [1] * 4, [2] * 4])
        self.assertEqual(report['state_updates'], 3)
        self.assertEqual(report['soft_alpha_pixels'], 3 * 16 * 16)
        self.assertEqual(len(output.getvalue()), frames.nbytes)
        # A new job must begin with zero state again.
        process_frames(io.BytesIO(frames[:1].tobytes()), io.BytesIO(), width=16, height=16, frames=1, infer=infer)
        self.assertEqual(seen[-1], [0] * 4)

    def test_rejects_incomplete_extra_and_nonfinite_outputs(self):
        frame = np.full((16, 16, 4), 255, np.uint8).tobytes()
        def good(rgb, states):
            return [rgb, np.ones((1, 1, 16, 16), np.float32), *states]
        for data in (frame[:-1], frame + b'x'):
            with self.assertRaises(ValueError):
                process_frames(io.BytesIO(data), io.BytesIO(), width=16, height=16, frames=1, infer=good)
        for what in ('shape', 'nan', 'range', 'state', 'count'):
            def bad(rgb, states):
                out = good(rgb, states)
                if what == 'shape': out[0] = rgb[:, :1]
                if what == 'nan': out[1][0, 0, 0, 0] = np.nan
                if what == 'range': out[1][0, 0, 0, 0] = 2
                if what == 'state': out[2] = np.zeros((2, 1, 1, 1), np.float32)
                if what == 'count': out.pop()
                return out
            with self.subTest(what=what), self.assertRaises(ValueError):
                process_frames(io.BytesIO(frame), io.BytesIO(), width=16, height=16, frames=1, infer=bad)


MOCK_WORKER = r'''
import json, sys, time
from pathlib import Path
mode=sys.argv[2]
if mode in {'wait','cancel'}:
    if mode=='cancel': Path(sys.argv[3]).write_text('cancel',encoding='utf-8')
    time.sleep(20)
sys.path.insert(0, PRODUCT_SOURCE)
sys.path.insert(0, NUMPY_SOURCE)
import numpy as np
from ai_ad_editor.matting_frames import process_frames
from ai_ad_editor.utils import atomic_write_json
request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
if mode=='fail': raise RuntimeError('controlled worker failure')
info=request['video']
def infer(rgb,states):
    return [rgb,np.full((1,1,info['height'],info['width']),.5,np.float32),*[s+1 for s in states]]
metrics=process_frames(sys.stdin.buffer,sys.stdout.buffer,width=info['width'],height=info['height'],frames=info['frames'],infer=infer)
response={'protocol':request['protocol'],'engine':request['engine'],'status':'succeeded','network':'disabled','blocked_network_events':[],
          'request_sha256':request['request_sha256'],'source_sha256':request['source']['sha256'],'adapter_sha256':request['adapter']['sha256'],
          'providers':['CPUExecutionProvider'],'metrics':metrics}
if mode=='bad_hash': response['source_sha256']='sha256:'+'0'*64
if mode=='bad_frames': metrics['frames']-=1
if mode=='bad_network': response['blocked_network_events']=['socket.connect']
if mode=='bad_alpha': metrics['alpha_mean']=float('nan')
if mode=='bad_state': metrics['state_updates']=0
if mode=='bad_digest': metrics['rgba_sha256']='sha256:'+'0'*64
if mode=='race': Path(sys.argv[3]).write_bytes(b'external editor output')
if mode in {'tamper_model','tamper_source'}:
    path=Path(request['adapter']['model_path'] if mode=='tamper_model' else request['source']['path'])
    with path.open('ab') as changed: changed.write(b'changed during inference')
if mode=='bad_json':
    Path(request['response']).write_text('invalid JSON',encoding='utf-8')
    raise SystemExit(0)
atomic_write_json(Path(request['response']),response)
'''


class NativeMattingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agent-matting-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / '中文项目'
        self.assertEqual(invoke('project', 'init', str(self.root))[0], 0)
        self.model = self.base / 'model.onnx'
        self.model.write_bytes(b'protocol-only fixture; real weights have separate smoke evidence')
        self.evidence = self.base / 'evidence.json'
        atomic_write_json(self.evidence, {'usage': 'internal synthetic test only'})
        self.worker = self.base / 'mock_worker.py'
        self.worker.write_text(MOCK_WORKER.replace('PRODUCT_SOURCE', repr(str(Path(__file__).resolve().parents[1] / 'src'))).replace('NUMPY_SOURCE', repr(str(Path(np.__file__).resolve().parent.parent))), encoding='utf-8')
        self.source = self.base / 'source.mov'
        frame = np.zeros((48, 64, 4), np.uint8)
        frame[:, :, :3] = [200, 40, 30]
        frame[:, 16:48, 3] = 128
        frame[:, 48:, 3] = 255
        self.frames = np.repeat(frame[None], 4, axis=0)
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', '64x48', '-framerate', '8', '-i', 'pipe:0',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '0.5', '-c:v', 'qtrle', '-pix_fmt', 'argb', '-c:a', 'pcm_s16le', str(self.source)], input=self.frames.tobytes(), capture_output=True, check=True)
        code, value = invoke('media', 'ingest', '--project', str(self.root), '--input', str(self.source), '--license-spdx', 'CC0-1.0', '--verification-status', 'verified', '--permitted-use', 'commercial_ad', '--evidence', str(self.evidence))
        self.assertEqual(code, 0, value)
        self.asset_id = value['data']['asset']['id']
        self.options = ['--project', str(self.root), '--adapter-id', 'rvm', '--engine', MATTING_ENGINE, '--model-path', str(self.model), '--executable', sys.executable, '--evidence', str(self.evidence)]
        self.output = self.root / 'assets/derived/cutout.mov'

    def metadata(self):
        return tuple(p.read_bytes() if p.is_file() else None for p in (self.root / 'project.json', self.root / 'project.lock.json', ledger_file(self.root), self.root / 'models/visual-adapters.json'))

    def register(self):
        code, value = invoke('media', 'adapter', 'register', *self.options)
        self.assertEqual(code, 0, value)
        return value['data']['adapter']

    def options_for_matting(self):
        return ['media', 'matting', '--project', str(self.root), '--asset-id', self.asset_id, '--adapter-id', 'rvm', '--derived-asset-id', 'cutout', '--apply', '--track-id', 'track_video_1', '--audio-track-id', 'track_audio_1']

    def fake_command(self, mode='ok', extra=''):
        return patch('ai_ad_editor.local_matting._worker_command', side_effect=lambda adapter, request: [sys.executable, '-I', '-B', str(self.worker), str(request), mode, extra])

    def decode(self, path, *, audio=False):
        options = ['-vn', '-f', 'f32le', '-acodec', 'pcm_f32le'] if audio else ['-an', '-f', 'rawvideo', '-pix_fmt', 'rgba']
        raw = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(path), *options, 'pipe:1'], capture_output=True, check=True).stdout
        return np.frombuffer(raw, dtype='<f4') if audio else np.frombuffer(raw, dtype=np.uint8).reshape(-1, 48, 64, 4)

    def assert_no_outputs(self):
        self.assertFalse(self.output.exists())
        self.assertFalse(list((self.root / 'cache/matting').glob('*')))
        self.assertFalse((self.root / 'operations/project-transaction.json').exists())

    def test_registration_dry_run_and_inspection_do_not_infer(self):
        before = self.metadata()
        code, value = invoke('media', 'adapter', 'register', *self.options, '--dry-run')
        self.assertEqual(code, 0, value)
        self.assertEqual(self.metadata(), before)
        adapter = self.register()
        self.assertEqual(len(adapter['artifacts']), 9)
        self.assertEqual({a['role'] for a in adapter['artifacts']}, {'model', 'python', 'evidence', 'worker', 'frames', 'controller', 'diagnostics', 'error_contract', 'local_policy'})
        self.assertEqual(adapter['kind'], 'video-matting')
        with patch('ai_ad_editor.cli.matte_native') as infer:
            before = self.metadata()
            for action in ('list', 'inspect'):
                extra = ['--adapter-id', 'rvm'] if action == 'inspect' else []
                self.assertEqual(invoke('media', 'adapter', action, '--project', str(self.root), *extra)[0], 0)
            self.assertEqual(invoke(*self.options_for_matting(), '--dry-run')[0], 0)
            infer.assert_not_called()
        self.assertEqual(self.metadata(), before)
        self.assertFalse((self.root / 'cache/matting').exists())

    def test_registration_requires_local_python_model_evidence(self):
        for flag, value in (('--model-path', 'https://invalid.example/model.onnx'), ('--evidence', str(self.base / 'missing.json')), ('--executable', str(self.base / 'runner.cmd'))):
            options = list(self.options); options[options.index(flag) + 1] = value
            self.assertNotEqual(invoke('media', 'adapter', 'register', *options)[0], 0)
        for config in ({'threads': 0}, {'threads': True}, {'downsample_ratio': math.nan}, {'downsample_ratio': 0}, {'downsample_ratio': 1.1}):
            with self.subTest(config=config), self.assertRaises(AppError): settings(**config)

    def test_model_evidence_and_settings_tamper_rejected_before_execution(self):
        adapter = self.register()
        for path in (self.model, self.evidence):
            original = path.read_bytes(); path.write_bytes(original + b'changed')
            with patch('ai_ad_editor.cli.matte_native') as worker:
                code, result = invoke(*self.options_for_matting())
                self.assertEqual(code, 10, result); worker.assert_not_called()
            path.write_bytes(original)
        changed = copy.deepcopy(adapter); changed['settings']['provider'] = 'AzureExecutionProvider'; changed['sha256'] = manifest_hash(changed)
        self.assertFalse(verify_adapter(changed)['ok'])

    def test_source_tamper_wrong_track_and_invalid_range_rejected_before_execution(self):
        self.register(); before = self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as worker:
            for options in (['--track-id', 'track_audio_1'], ['--audio-track-id', 'track_video_1'], ['--end-seconds', '2'], ['--fps', 'nan'], ['--max-frames', '1'], ['--max-edge', '-1'], ['--timeline-start-seconds', 'nan'], ['--timeout-seconds', '0']):
                code, value = invoke(*self.options_for_matting(), *options)
                self.assertNotEqual(code, 0, value)
            source = self.root / json.loads((self.root / 'project.json').read_text(encoding='utf-8'))['assets'][0]['uri']
            source.write_bytes(source.read_bytes() + b'tamper')
            self.assertEqual(invoke(*self.options_for_matting())[0], 10)
            worker.assert_not_called()
        self.assertEqual(self.metadata(), before)

    def test_matting_adapter_cannot_be_used_as_tracker(self):
        self.register()
        code, value = invoke('media', 'track', '--project', str(self.root), '--asset-id', self.asset_id, '--adapter-id', 'rvm', '--roi', '0,0,1,1', '--dry-run')
        self.assertEqual(code, 10, value)
        self.assertEqual(value['errors'][0]['code'], 'TRACKING_ADAPTER_UNAVAILABLE')

    def test_pipeline_preserves_soft_alpha_exact_frames_audio_and_rights(self):
        adapter = self.register()
        with self.fake_command():
            code, value = invoke(*self.options_for_matting())
        self.assertEqual(code, 0, value)
        data = value['data']; result = data['matting']
        rgba = self.decode(self.output)
        np.testing.assert_array_equal(rgba[:, :, :, :3], self.frames[:, :, :, :3])
        np.testing.assert_array_equal(rgba[:, :, :, 3], np.rint(self.frames[:, :, :, 3].astype(np.float32) * .5).astype(np.uint8))
        audio = self.decode(self.output, audio=True)
        reference = self.decode(self.source, audio=True)
        self.assertEqual(len(audio), 24000)
        np.testing.assert_allclose(audio, reference, atol=1e-6)
        self.assertTrue(result['rgba_roundtrip_verified'])
        self.assertEqual(result['worker']['metrics']['frames'], 4)
        self.assertEqual(set(data['rights']['derived_from']), {self.asset_id, adapter['rights_ref']})
        self.assertIsNotNone(data['generated_audio_clip'])
        self.assertEqual(invoke('validate', '--project', str(self.root))[0], 0)
        self.assertEqual(invoke('policy', 'audit', '--project', str(self.root))[0], 0)
        code, rights = invoke('rights', 'check', '--project', str(self.root))
        self.assertEqual(code, 7, rights)
        self.assertFalse(list((self.root / 'cache/matting').glob('*')))

    def test_selected_range_fractional_clock_resampling_and_no_audio(self):
        self.register()
        options = self.options_for_matting()
        options = options[:options.index('--audio-track-id')]
        with self.fake_command():
            code, value = invoke(*options, '--start-seconds', '.125', '--end-seconds', '.44', '--fps', '10', '--no-audio')
        self.assertEqual(code, 0, value)
        self.assertEqual(value['data']['matting']['video']['frames'], 4)
        self.assertAlmostEqual(probe_media(self.output)['duration_seconds'], .4, places=3)
        self.assertFalse(probe_media(self.output)['audio']['codec'])

    def test_protocol_and_rgba_mismatch_roll_back_all_metadata(self):
        self.register(); before = self.metadata()
        expected_codes = {'bad_hash': 'MATTING_WORKER_INTEGRITY_INVALID', 'bad_frames': 'MATTING_WORKER_OUTPUT_INVALID', 'bad_network': 'MATTING_WORKER_INTEGRITY_INVALID',
                          'bad_alpha': 'MATTING_WORKER_OUTPUT_INVALID', 'bad_state': 'MATTING_WORKER_OUTPUT_INVALID', 'bad_digest': 'MATTING_ALPHA_ROUNDTRIP_FAILED', 'bad_json': 'MATTING_WORKER_OUTPUT_INVALID', 'fail': 'MATTING_PIPELINE_FAILED'}
        for mode in ('bad_hash', 'bad_frames', 'bad_network', 'bad_alpha', 'bad_state', 'bad_digest', 'bad_json', 'fail'):
            with self.subTest(mode=mode), self.fake_command(mode):
                code, value = invoke(*self.options_for_matting())
                self.assertEqual(code, 6, value)
                self.assertEqual(value['errors'][0]['code'], expected_codes[mode], value)
            self.assert_no_outputs()
            self.assertEqual(self.metadata(), before)

    def test_cancellation_and_timeout_terminate_all_pipeline_processes(self):
        self.register(); before = self.metadata()
        real_popen = subprocess.Popen
        for mode in ('wait', 'cancel'):
            processes = []
            cancel = self.root / 'cache' / ('cancel-' + mode)
            def capture(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                processes.append(process)
                return process
            with self.fake_command(mode, str(cancel)), patch('ai_ad_editor.local_matting.subprocess.Popen', side_effect=capture):
                code, value = invoke(*self.options_for_matting(), '--timeout-seconds', '2', '--cancel-file', str(cancel))
            self.assertEqual(code, 8, value)
            self.assertGreaterEqual(len(processes), 3)
            self.assertTrue(all(p.poll() is not None for p in processes))
            self.assert_no_outputs()
            self.assertEqual(self.metadata(), before)

    def test_existing_output_and_external_publish_race_are_not_deleted(self):
        self.register()
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_bytes(b'original')
        with patch('ai_ad_editor.cli.matte_native') as worker:
            self.assertEqual(invoke(*self.options_for_matting())[0], 2)
            worker.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b'original')
        self.output.unlink()
        with self.fake_command('race', str(self.output)):
            code, value = invoke(*self.options_for_matting())
        self.assertEqual(code, 6, value)
        self.assertEqual(self.output.read_bytes(), b'external editor output')

    def test_save_failure_cleans_published_video_and_restores_metadata(self):
        self.register(); before = self.metadata()
        with self.fake_command(), patch('ai_ad_editor.cli.save_project', side_effect=OSError('controlled disk write failure')):
            code, value = invoke(*self.options_for_matting())
        self.assertEqual(code, 6, value)
        self.assert_no_outputs()
        self.assertEqual(self.metadata(), before)

    def test_idempotency_does_not_repeat_inference_and_package_keeps_model_registry(self):
        self.register()
        with self.fake_command() as worker:
            first = invoke(*self.options_for_matting(), '--idempotency-key', 'matting-1')
            second = invoke(*self.options_for_matting(), '--idempotency-key', 'matting-1')
            self.assertEqual(first[0], 0, first[1]); self.assertEqual(second[0], 0, second[1])
            self.assertEqual(worker.call_count, 1)
        package = self.base / 'project.aevpkg.zip'
        code, value = invoke('convert', 'export', '--project', str(self.root), '--target-format', 'package', '--output', str(package))
        self.assertEqual(code, 0, value)
        restored = self.base / 'imported'
        code, value = invoke('convert', 'import', '--input', str(package), '--output', str(restored))
        self.assertEqual(code, 0, value)
        self.assertTrue((restored / 'models/visual-adapters.json').is_file())
        self.assertEqual(invoke('media', 'adapter', 'inspect', '--project', str(restored), '--adapter-id', 'rvm')[0], 0)
        self.assertEqual(invoke('validate', '--project', str(restored))[0], 0)

    def test_source_rotation_sar_and_hdr_are_explicit_in_plan(self):
        adapter = self.register()
        probe = probe_media(self.source)
        stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        stream.update(sample_aspect_ratio='2:1', side_data_list=[{'rotation': 90}])
        with patch('ai_ad_editor.local_matting.probe_media', return_value=probe):
            plan = prepare_plan(self.source, adapter)
        self.assertEqual((plan['video']['width'], plan['video']['height']), (48, 128))
        stream['color_transfer'] = 'smpte2084'
        with patch('ai_ad_editor.local_matting.probe_media', return_value=probe), self.assertRaises(AppError) as error:
            prepare_plan(self.source, adapter)
        self.assertEqual(error.exception.code, 'MATTING_HDR_UNSUPPORTED')

    def test_audio_delayed_start_preserves_initial_silence_and_content(self):
        shifted = self.base / 'shifted.mov'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(self.source), '-itsoffset', '0.125', '-i', str(self.source),
                        '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', str(shifted)], capture_output=True, check=True)
        code, value = invoke('media', 'ingest', '--project', str(self.root), '--input', str(shifted))
        self.assertEqual(code, 0, value)
        self.asset_id = value['data']['asset']['id']
        self.register()
        with self.fake_command(): code, value = invoke(*self.options_for_matting())
        self.assertEqual(code, 0, value)
        audio = self.decode(self.output, audio=True)
        reference = self.decode(self.source, audio=True)
        self.assertEqual(len(audio), 24000)
        np.testing.assert_array_equal(audio[:6000], 0)
        np.testing.assert_allclose(audio[6000:], reference[:18000], atol=1e-6)

    def test_actual_rotated_sar_source_is_normalized_in_output(self):
        source = self.base / 'sar.mov'
        rotated = self.base / 'rotated.mov'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(self.source), '-vf', 'setsar=2/1', '-c:v', 'qtrle', '-pix_fmt', 'argb', '-c:a', 'copy', str(source)], capture_output=True, check=True)
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-display_rotation:v:0', '90', '-i', str(source), '-c', 'copy', str(rotated)], capture_output=True, check=True)
        code, value = invoke('media', 'ingest', '--project', str(self.root), '--input', str(rotated))
        self.assertEqual(code, 0, value)
        self.asset_id = value['data']['asset']['id']
        self.register()
        with self.fake_command(): code, value = invoke(*self.options_for_matting())
        self.assertEqual(code, 0, value)
        video = value['data']['matting']['video']
        self.assertEqual((video['width'], video['height']), (48, 128))
        self.assertTrue(value['data']['matting']['rgba_roundtrip_verified'])
        raw = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(self.output), '-frames:v', '1', '-an', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'], capture_output=True, check=True).stdout
        rgba = np.frombuffer(raw, dtype=np.uint8).reshape(128, 48, 4)
        self.assertEqual(rgba[8, 24, 3], 128)
        self.assertEqual(rgba[-8, 24, 3], 0)

    def test_missing_model_rights_blocks_before_inference(self):
        self.register()
        ledger = json.loads(ledger_file(self.root).read_text(encoding='utf-8'))
        # Preserve the ledger shape but remove the model record through its
        # existing collection; synthetic corruption must fail before a worker.
        for name, value in list(ledger.items()):
            if isinstance(value, list):
                ledger[name] = [r for r in value if not isinstance(r, dict) or r.get('asset_id') != 'visual_adapter_rvm']
        atomic_write_json(ledger_file(self.root), ledger)
        with patch('ai_ad_editor.cli.matte_native') as worker:
            code, value = invoke(*self.options_for_matting())
            self.assertEqual(code, 7, value); worker.assert_not_called()
        self.assert_no_outputs()

    def test_inputs_changed_during_processing_fail_after_pipeline(self):
        self.register(); before = self.metadata()
        asset = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))['assets'][0]
        for mode, path in (('tamper_model', self.model), ('tamper_source', self.root / asset['uri'])):
            original = path.read_bytes()
            with self.fake_command(mode): code, value = invoke(*self.options_for_matting())
            self.assertEqual(code, 10, value)
            self.assertEqual(value['errors'][0]['code'], 'MATTING_INTEGRITY_FAILED')
            self.assert_no_outputs(); self.assertEqual(self.metadata(), before)
            path.write_bytes(original)

    def test_overlap_is_preflighted_and_explicit_replace_keeps_audio_aligned(self):
        self.register()
        with self.fake_command(): code, value = invoke(*self.options_for_matting())
        self.assertEqual(code, 0, value)
        opts = self.options_for_matting(); opts[opts.index('--derived-asset-id') + 1] = 'replacement'
        with patch('ai_ad_editor.cli.matte_native') as worker:
            code, value = invoke(*opts, '--dry-run')
            self.assertEqual(code, 2, value); worker.assert_not_called()
        with self.fake_command(): code, value = invoke(*opts, '--replace-track')
        self.assertEqual(code, 0, value)
        project = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))
        for track in project['sequences'][0]['tracks']:
            if track['id'] in ('track_video_1', 'track_audio_1'):
                self.assertEqual(len(track['clips']), 1)
                self.assertEqual(track['clips'][0]['asset_id'], 'replacement')

    def test_snapshot_restore_keeps_registered_adapter_and_removes_derived_metadata(self):
        self.register()
        with self.fake_command(): code, value = invoke(*self.options_for_matting())
        self.assertEqual(code, 0, value)
        code, restored = invoke('project', 'restore', '--project', str(self.root), '--snapshot', value['data']['snapshot_id'])
        self.assertEqual(code, 0, restored)
        project = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))
        self.assertNotIn('cutout', {a['id'] for a in project['assets']})
        code, inspected = invoke('media', 'adapter', 'inspect', '--project', str(self.root), '--adapter-id', 'rvm')
        self.assertEqual(code, 0, inspected)
        self.assertTrue(inspected['data']['verification']['ok'])

    def test_worker_network_guard_blocks_lookup_in_isolated_process(self):
        code = "import sys;sys.path.insert(0," + repr(str(Path(__file__).resolve().parents[1] / 'src')) + ");from ai_ad_editor.rvm_worker import install_network_guard;events=[];install_network_guard(events);import socket\ntry: socket.getaddrinfo('localhost',80)\nexcept RuntimeError: print(events[0])\nelse: raise RuntimeError('network guard failed')"
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True, check=True)
        self.assertIn('socket.getaddrinfo', result.stdout)

    def test_rational_fps_scaled_canvas_and_partial_audio_tail(self):
        self.register()
        with self.fake_command():
            code, value = invoke(*self.options_for_matting(), '--fps', '30000/1001', '--max-edge', '32')
        self.assertEqual(code, 0, value)
        info = value['data']['matting']['video']
        self.assertEqual((info['width'], info['height'], info['frames'], info['fps']), (32, 24, 15, '30000/1001'))
        self.assertAlmostEqual(info['duration_seconds'], .5005)
        audio = self.decode(self.output, audio=True)
        self.assertEqual(len(audio), 24024)
        np.testing.assert_array_equal(audio[-24:], 0)


if __name__ == '__main__':
    unittest.main()
