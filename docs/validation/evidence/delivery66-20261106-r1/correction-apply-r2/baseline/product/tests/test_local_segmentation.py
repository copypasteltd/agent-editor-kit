from __future__ import annotations

import copy
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import test_local_matting as fixtures

from ai_ad_editor.errors import AppError
from ai_ad_editor.local_segmentation import SEGMENTATION_ENGINE, model_files, normalize_prompts, verify_adapter
from ai_ad_editor.matting_frames import read_frame
from ai_ad_editor.sam2_worker import prune_session
from ai_ad_editor.segmentation_frames import mask_union, process_frames
from ai_ad_editor.utils import atomic_write_json

invoke = fixtures.invoke


def prompt_fixture():
    objects = [{'object_id': 1, 'points': [{'x': .3, 'y': .4, 'label': 1}, {'x': .1, 'y': .1, 'label': 0}]}, {'object_id': 2, 'box': [.6, .2, .9, .8]}]
    return {'version': '1.0.0', 'coordinate_space': 'normalized-output', 'frames': [{'frame': 0, 'objects': objects}, {'frame': 2, 'objects': [objects[1]]}, {'frame': 3, 'reset': True, 'objects': objects}]}


class SegmentationPromptTests(unittest.TestCase):
    def test_valid_multiple_objects_selection_correction_and_reset(self):
        result = normalize_prompts(prompt_fixture(), frames=4, object_ids=[2])
        self.assertEqual(result['object_ids'], [2])
        self.assertEqual(result['frames'][2]['reset'], True)
        self.assertEqual(len(result['sha256']), 71)
        canonical = normalize_prompts({k: result[k] for k in ('version', 'coordinate_space', 'frames')}, frames=4, object_ids=[2])
        self.assertEqual(canonical, result)

    def test_rejects_ambiguous_frames_ids_coordinates_and_unknown_fields(self):
        changes = [lambda x: x.update(extra=True), lambda x: x.update(coordinate_space='source-pixels'), lambda x: x['frames'][0].update(frame=1),
                   lambda x: x['frames'][1].update(frame=0), lambda x: x['frames'][2].update(frame=4), lambda x: x['frames'][0]['objects'][0].update(object_id=True),
                   lambda x: x['frames'][0]['objects'][1].update(object_id=1), lambda x: x['frames'][0]['objects'][0]['points'][0].update(x=float('nan')),
                   lambda x: x['frames'][0]['objects'][0]['points'][0].update(label=2), lambda x: x['frames'][0]['objects'][0]['points'][0].update(y=1.1),
                   lambda x: x['frames'][0]['objects'][1].update(box=[.7, .2, .6, .9]), lambda x: x['frames'][0]['objects'][0].update(points=[]),
                   lambda x: x['frames'][2].update(objects=x['frames'][2]['objects'][:1]), lambda x: x['frames'][0].update(reset='yes')]
        for change in changes:
            value = prompt_fixture(); change(value)
            with self.subTest(change=change), self.assertRaises(AppError):
                normalize_prompts(value, frames=4)

    def test_limits_selection_and_threshold_are_not_silently_ignored(self):
        for kwargs in ({'object_ids': [3]}, {'object_ids': [1, 1]}, {'object_ids': []}, {'mask_mode': 'matte'}, {'threshold': float('inf')}, {'threshold': 21}):
            with self.subTest(kwargs=kwargs), self.assertRaises(AppError):
                normalize_prompts(prompt_fixture(), frames=4, **kwargs)
        for modify in (lambda x: x['frames'][0]['objects'][0].update(points=[{'x': .5, 'y': .5, 'label': 1}] * 33), lambda x: x.update(frames=x['frames'] * 100)):
            x = prompt_fixture(); modify(x)
            with self.assertRaises(AppError): normalize_prompts(x, frames=4)

    def test_new_object_can_enter_later_but_selected_output_starts_at_zero(self):
        x = prompt_fixture(); x['frames'][0]['objects'] = x['frames'][0]['objects'][:1]
        value = normalize_prompts(x, frames=4)
        self.assertEqual(value['object_ids'], [1, 2])
        with self.assertRaises(AppError): normalize_prompts(x, frames=4, object_ids=[2])


class SegmentationFrameTests(unittest.TestCase):
    def test_union_selection_probability_and_alpha_multiplication(self):
        logits = np.array([[[4., -4., 0.]], [[-4., 4., 0.]]], dtype=np.float32)
        np.testing.assert_array_equal(mask_union(logits, [1, 2], [1, 2], mode='binary', threshold=0, height=1, width=3), [[[[1, 1, 0]]]])
        selected = mask_union(logits, [1, 2], [2], mode='probability', threshold=0, height=1, width=3)
        self.assertAlmostEqual(float(selected[0, 0, 0, 2]), .5)
        rgba = np.array([[[200, 100, 40, 0], [200, 100, 40, 128], [200, 100, 40, 255]]], np.uint8)
        prompts = normalize_prompts({'version': '1.0.0', 'coordinate_space': 'normalized-output', 'frames': prompt_fixture()['frames'][:1]}, frames=1, object_ids=[2], mask_mode='probability')
        out = io.BytesIO()
        report = process_frames(io.BytesIO(rgba.tobytes()), out, width=3, height=1, frames=1, prompts=prompts, infer=lambda rgb, i, e: (logits, [1, 2], 1024), state_budget=2048)
        actual = np.frombuffer(out.getvalue(), np.uint8).reshape(1, 3, 4)
        np.testing.assert_array_equal(actual[:, :, :3], rgba[:, :, :3])
        np.testing.assert_array_equal(actual[:, :, 3], [[0, 126, 128]])
        self.assertEqual(report['state_reset'], 'per-job-and-explicit-frames')

    def test_invalid_mask_values_frames_and_state_budget_reject(self):
        prompts = normalize_prompts({'version': '1.0.0', 'coordinate_space': 'normalized-output', 'frames': prompt_fixture()['frames'][:1]}, frames=1)
        raw = bytes([255] * 16)
        for data, mask, budget in [(raw[:-1], np.ones((2, 2, 2), np.float32), 1024), (raw + b'x', np.ones((2, 2, 2), np.float32), 1024),
                                   (raw, np.full((2, 2, 2), np.nan, np.float32), 1024), (raw, np.ones((1, 2, 2), np.float32), 1024), (raw, np.ones((2, 2, 2), np.float32), 1)]:
            with self.subTest(size=len(data), shape=mask.shape, budget=budget), self.assertRaises(ValueError):
                process_frames(io.BytesIO(data), io.BytesIO(), width=2, height=2, frames=1, prompts=prompts, infer=lambda rgb, i, e: (mask, [1, 2], 1024), state_budget=budget)

    def test_stream_dispatches_only_current_event_and_preserves_reset_evidence(self):
        prompts = normalize_prompts(prompt_fixture(), frames=4)
        calls = []
        def infer(rgb, i, event):
            calls.append((i, event['reset'] if event else None))
            return np.ones((2, 2, 2), np.float32), [1, 2], 1024
        report = process_frames(io.BytesIO(bytes([255] * 64)), io.BytesIO(), width=2, height=2, frames=4, prompts=prompts, infer=infer, state_budget=2048)
        self.assertEqual(calls, [(0, False), (1, None), (2, False), (3, True)])
        self.assertEqual((report['prompt_events'], report['explicit_resets']), (3, 1))

    def test_long_stream_prunes_rasters_and_nonconditioning_memory_without_losing_anchors(self):
        state = SimpleNamespace(processed_frames={}, output_dict_per_obj={0: {'cond_frame_outputs': {0: 'anchor'}, 'non_cond_frame_outputs': {}}}, frames_tracked_per_obj={0: {}})
        for i in range(100):
            state.processed_frames[i] = 'raster'
            state.output_dict_per_obj[0]['non_cond_frame_outputs'][i] = 'memory'
            state.frames_tracked_per_obj[0][i] = 'tracked'
            prune_session(state, i, 16)
            self.assertEqual(len(state.processed_frames), 1)
            self.assertLessEqual(len(state.output_dict_per_obj[0]['non_cond_frame_outputs']), 16)
            self.assertLessEqual(len(state.frames_tracked_per_obj[0]), 16)
        self.assertEqual(state.output_dict_per_obj[0]['cond_frame_outputs'], {0: 'anchor'})
        self.assertEqual(min(state.output_dict_per_obj[0]['non_cond_frame_outputs']), 84)


MOCK_WORKER = r'''
import json,sys,time
from pathlib import Path
sys.path.insert(0,PRODUCT_SOURCE);sys.path.insert(0,NUMPY_SOURCE)
import numpy as np
from ai_ad_editor.segmentation_frames import process_frames
from ai_ad_editor.utils import atomic_write_json
r=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));mode=sys.argv[2];v=r['video'];p=r['prompt_plan']
if mode=='wait':time.sleep(20)
def infer(rgb,index,event):
    masks=np.full((2,v['height'],v['width']),-4,np.float32)
    masks[0,:,16:24]=4;masks[1,:,40:56]=4
    return masks,[1,2],1024
m=process_frames(sys.stdin.buffer,sys.stdout.buffer,width=v['width'],height=v['height'],frames=v['frames'],prompts=p,infer=infer,state_budget=2048)
response={'status':'succeeded','protocol':r['protocol'],'engine':r['engine'],'network':'disabled','blocked_network_events':[],
          'request_sha256':r['request_sha256'],'adapter_sha256':r['adapter']['sha256'],'source_sha256':r['source']['sha256'],
          'providers':['torch-'+r['adapter']['settings']['device']],'metrics':m,'prompt_sha256':p['sha256'],'object_ids':p['object_ids'],'mask_mode':p['mask_mode']}
if mode=='prompt_hash':response['prompt_sha256']='sha256:'+'0'*64
if mode=='objects':response['object_ids']=[999]
if mode=='provider':response['providers']=['torch-cuda']
if mode=='mask_mode':response['mask_mode']='probability'
if mode=='reset':m['explicit_resets']=0
if mode=='state_budget':m['state_peak_bytes']=1024**3
if mode=='prompt_tamper':
    with Path(r['prompt_source']['path']).open('ab') as f:f.write(b' ')
atomic_write_json(Path(r['response']),response)
'''


class NativeSegmentationTests(unittest.TestCase):
    setUpClass = classmethod(lambda cls: fixtures.configure_local_runtime())
    metadata = fixtures.NativeMattingTests.metadata
    register = fixtures.NativeMattingTests.register
    decode = fixtures.NativeMattingTests.decode

    def setUp(self):
        fixtures.NativeMattingTests.setUp(self)
        self.model = self.base / 'sam2'
        self.model.mkdir()
        configs = {'config.json': {'model_type': 'sam2_video', 'architectures': ['Sam2VideoModel'], 'image_size': 1024, 'num_maskmem': 7, 'max_object_pointers_in_encoder': 16},
                   'preprocessor_config.json': {}, 'processor_config.json': {}, 'video_preprocessor_config.json': {}}
        for name, value in configs.items(): atomic_write_json(self.model / name, value)
        (self.model / 'model.safetensors').write_bytes(b'protocol fixture, not an inference checkpoint')
        self.options = ['--project', str(self.root), '--adapter-id', 'sam2', '--engine', SEGMENTATION_ENGINE, '--model-path', str(self.model), '--executable', sys.executable, '--evidence', str(self.evidence), '--device', 'cpu']
        self.prompts = self.base / 'prompts.json'; atomic_write_json(self.prompts, prompt_fixture())
        self.worker.write_text(MOCK_WORKER.replace('PRODUCT_SOURCE', repr(str(Path(__file__).resolve().parents[1] / 'src'))).replace('NUMPY_SOURCE', repr(str(Path(np.__file__).resolve().parent.parent))), encoding='utf-8')

    def options_for_matting(self):
        return ['media', 'matting', '--project', str(self.root), '--asset-id', self.asset_id, '--adapter-id', 'sam2', '--derived-asset-id', 'cutout', '--prompts', str(self.prompts), '--apply', '--track-id', 'track_video_1', '--audio-track-id', 'track_audio_1']

    def fake_command(self, mode='ok'):
        return patch('ai_ad_editor.local_matting._worker_command', side_effect=lambda adapter, request: [sys.executable, '-I', '-B', str(self.worker), str(request), mode])

    def test_register_dry_run_and_inspect_do_not_infer_and_bind_complete_inventory(self):
        before = self.metadata()
        code, value = invoke('media', 'adapter', 'register', *self.options, '--dry-run')
        self.assertEqual(code, 0, value); self.assertEqual(before, self.metadata())
        record = self.register()
        self.assertTrue(verify_adapter(record)['ok'])
        self.assertEqual(record['model_file_count'], 5)
        self.assertEqual(record['kind'], 'video-segmentation')
        self.assertEqual(invoke('media', 'adapter', 'inspect', '--project', str(self.root), '--adapter-id', 'sam2')[1]['data']['verification']['ok'], True)
        (self.model / 'config.json').write_text('{}', encoding='utf-8')
        self.assertFalse(verify_adapter(record)['ok'])

    def test_model_custom_code_missing_files_and_pickle_weights_reject(self):
        config = self.model / 'config.json'; original = config.read_bytes()
        atomic_write_json(config, {'auto_map': {'AutoModel': 'external.Code'}})
        with self.assertRaises(AppError): model_files(self.model)
        config.write_bytes(original)
        bad = self.model / 'remote.py'; bad.write_text('raise RuntimeError()', encoding='utf-8')
        with self.assertRaises(AppError): model_files(self.model)
        bad.unlink(); weights = self.model / 'model.safetensors'; weights.rename(self.model / 'model.pt')
        with self.assertRaises(AppError): model_files(self.model)

    def test_manifest_device_evidence_and_inventory_tamper_reject(self):
        record = self.register()
        for mutate in (lambda r: r['settings'].update(device='cuda'), lambda r: r['artifacts'].pop(), lambda r: r.update(rights_ref='other')):
            changed = copy.deepcopy(record); mutate(changed); self.assertFalse(verify_adapter(changed)['ok'])
        self.evidence.write_text('changed', encoding='utf-8')
        self.assertFalse(verify_adapter(record)['ok'])

    def test_missing_prompts_selection_and_engine_specific_flags_reject_before_inference(self):
        self.register()
        args = self.options_for_matting()
        for options in (args[:args.index('--prompts')] + args[args.index('--prompts') + 2:], args + ['--object-id', '999'], args + ['--logit-threshold', 'nan']):
            with patch('ai_ad_editor.cli.matte_native') as inference:
                code, value = invoke(*options)
            self.assertNotEqual(code, 0, value); inference.assert_not_called()
        code, value = invoke('media', 'adapter', 'register', *self.options, '--adapter-id', 'other', '--downsample-ratio', '0.5')
        self.assertNotEqual(code, 0, value)

    def test_dry_run_reads_prompts_but_creates_no_asset_or_snapshot(self):
        self.register(); before = self.metadata()
        code, value = invoke(*self.options_for_matting(), '--dry-run')
        self.assertEqual(code, 0, value); self.assertEqual(before, self.metadata()); self.assertFalse(self.output.exists())
        self.assertEqual(value['data']['plan']['prompt_plan']['object_ids'], [1, 2])
        self.assertNotIn('downsample_ratio', value['data']['plan']['video'])

    def test_binary_union_pipeline_preserves_rgb_input_alpha_audio_and_rights(self):
        self.register()
        with self.fake_command(): code, value = invoke(*self.options_for_matting())
        self.assertEqual(code, 0, value)
        data = value['data']; result = data['matting']
        self.assertEqual(result['worker']['metrics']['explicit_resets'], 1)
        actual = self.decode(self.output)
        expected = self.frames.copy(); keep = np.zeros((48, 64), bool); keep[:, 16:24] = True; keep[:, 40:56] = True
        expected[:, :, :, 3] *= keep
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(data['rights']['source_version'], 'derived-video-sam2-segmentation')
        self.assertIn('visual_adapter_sam2', data['rights']['derived_from'])
        self.assertIsNotNone(data['generated_audio_clip'])
        self.assertEqual(invoke('validate', '--project', str(self.root))[0], 0)
        self.assertEqual(invoke('policy', 'audit', '--project', str(self.root))[0], 0)
        self.assertEqual(invoke('rights', 'check', '--project', str(self.root))[0], 7)

    def test_single_object_selection_and_probability_mode_are_executed(self):
        self.register()
        with self.fake_command(): code, value = invoke(*self.options_for_matting(), '--object-id', '2', '--mask-mode', 'probability')
        self.assertEqual(code, 0, value)
        actual = self.decode(self.output)
        self.assertGreater(int(actual[:, :, 40:56, 3].max()), 240)
        self.assertLess(int(actual[:, :, 16:24, 3].max()), 8)
        self.assertGreater(value['data']['matting']['worker']['metrics']['soft_alpha_pixels'], 0)

    def test_protocol_prompt_device_mode_reset_and_memory_mismatches_roll_back(self):
        self.register(); before = self.metadata()
        for mode in ['prompt_hash', 'objects', 'provider', 'mask_mode', 'reset', 'state_budget', 'prompt_tamper']:
            with self.subTest(mode=mode), self.fake_command(mode): code, value = invoke(*self.options_for_matting())
            self.assertNotEqual(code, 0, value); self.assertFalse(self.output.exists()); self.assertEqual(before, self.metadata())
            self.assertFalse(list((self.root / 'cache/matting').glob('rgba-*')))

    def test_metadata_write_failure_removes_media_and_restores_project(self):
        self.register(); before = self.metadata()
        with self.fake_command(), patch('ai_ad_editor.cli.save_project', side_effect=OSError('controlled failure')):
            code, value = invoke(*self.options_for_matting())
        self.assertNotEqual(code, 0, value); self.assertFalse(self.output.exists()); self.assertEqual(before, self.metadata())

    def test_tracking_rejects_segmentation_role_and_network_prompt_is_rejected(self):
        self.register()
        code, value = invoke('media', 'track', '--project', str(self.root), '--asset-id', self.asset_id, '--adapter-id', 'sam2', '--roi', '0,0,1,1')
        self.assertNotEqual(code, 0, value)
        args = self.options_for_matting(); args[args.index('--prompts') + 1] = 'https://example.invalid/prompts.json'
        with patch('ai_ad_editor.cli.matte_native') as infer:
            code, value = invoke(*args)
        self.assertNotEqual(code, 0, value); infer.assert_not_called()

    def test_idempotency_package_and_snapshot_preserve_registered_model_dependencies(self):
        self.register()
        with self.fake_command() as worker:
            first = invoke(*self.options_for_matting(), '--idempotency-key', 'sam2-1')
            second = invoke(*self.options_for_matting(), '--idempotency-key', 'sam2-1')
        self.assertEqual(first[0], 0, first[1]); self.assertEqual(second[0], 0, second[1]); self.assertEqual(worker.call_count, 1)
        package = self.base / 'sam2.aevpkg.zip'
        code, value = invoke('convert', 'export', '--project', str(self.root), '--target-format', 'package', '--output', str(package))
        self.assertEqual(code, 0, value)
        import zipfile
        with zipfile.ZipFile(package) as archive:
            self.assertFalse(any(n.endswith('.safetensors') for n in archive.namelist()))
        restored = self.base / 'imported'
        code, value = invoke('convert', 'import', '--input', str(package), '--output', str(restored))
        self.assertEqual(code, 0, value)
        code, value = invoke('media', 'adapter', 'inspect', '--project', str(restored), '--adapter-id', 'sam2')
        self.assertEqual(code, 0, value); self.assertTrue(value['data']['verification']['ok'])
        code, value = invoke('project', 'restore', '--project', str(self.root), '--snapshot', first[1]['data']['snapshot_id'])
        self.assertEqual(code, 0, value)
        payload = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))
        self.assertNotIn('cutout', {a['id'] for a in payload['assets']})
        self.assertEqual(invoke('media', 'adapter', 'inspect', '--project', str(self.root), '--adapter-id', 'sam2')[0], 0)

    def test_precancel_and_timeout_leave_no_media_and_no_live_children(self):
        self.register(); before = self.metadata()
        cancel = self.base / 'cancel'; cancel.write_text('cancel', encoding='utf-8')
        with patch('ai_ad_editor.local_matting._worker_command') as child:
            code, value = invoke(*self.options_for_matting(), '--cancel-file', str(cancel))
        self.assertEqual(code, 8, value); child.assert_not_called()
        children = []; real_popen = subprocess.Popen
        def capture(*args, **kwargs):
            p = real_popen(*args, **kwargs); children.append(p); return p
        with self.fake_command('wait'), patch('ai_ad_editor.local_matting.subprocess.Popen', side_effect=capture):
            code, value = invoke(*self.options_for_matting(), '--timeout-seconds', '2')
        self.assertEqual(code, 8, value); self.assertGreaterEqual(len(children), 3)
        self.assertTrue(all(p.poll() is not None for p in children)); self.assertFalse(self.output.exists()); self.assertEqual(before, self.metadata())

    def test_rvm_rejects_sam2_prompt_and_cuda_flags(self):
        rvm = self.base / 'rvm.onnx'; rvm.write_bytes(b'protocol fixture')
        opts = ['--project', str(self.root), '--adapter-id', 'rvm', '--engine', 'rvm-onnx-cpu-matting-v1', '--model-path', str(rvm), '--executable', sys.executable, '--evidence', str(self.evidence)]
        self.assertEqual(invoke('media', 'adapter', 'register', *opts)[0], 0)
        args = self.options_for_matting(); args[args.index('--adapter-id') + 1] = 'rvm'
        with patch('ai_ad_editor.cli.matte_native') as infer:
            code, value = invoke(*args)
        self.assertEqual(code, 2, value); infer.assert_not_called()
        self.assertEqual(invoke('media', 'adapter', 'register', *opts, '--adapter-id', 'rvm_cuda', '--device', 'cuda')[0], 2)


if __name__ == '__main__':
    unittest.main()
