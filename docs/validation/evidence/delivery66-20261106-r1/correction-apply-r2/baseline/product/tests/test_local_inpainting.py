from __future__ import annotations

import copy
import io
import json
import math
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

import test_local_matting as matting_fixture
from ai_ad_editor.errors import AppError
from ai_ad_editor.inpainting_frames import process_frames, repair_frame
from ai_ad_editor.local_inpainting import INPAINT_ENGINE, check_model, mask_unchanged, normalize_options, settings, verify_adapter
from ai_ad_editor.local_matting import manifest_hash, validate_response
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json

invoke = matting_fixture.invoke


class InpaintingFrameTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.full((48, 64, 4), 150, np.uint8)
        self.frame[:, :, 3] = np.arange(64, dtype=np.uint8)[None] * 4
        self.mask = np.zeros_like(self.frame); self.mask[16:32, 24:40, 3] = 255
        self.options = normalize_options(grow=0, context=0)

    def repair(self, **kw):
        return repair_frame(self.frame, self.mask, options=self.options, channel='alpha', infer=lambda image, mask: np.full_like(image, .2), budget=512 * 1024**2, **kw)

    def test_masked_pixels_repaired_and_outside_rgb_and_all_alpha_exact(self):
        result, stats = self.repair()
        np.testing.assert_array_equal(result[16:32, 24:40, :3], 51)
        selected = self.mask[:, :, 3] != 0
        np.testing.assert_array_equal(result[~selected], self.frame[~selected])
        np.testing.assert_array_equal(result[:, :, 3], self.frame[:, :, 3])
        self.assertEqual(stats['outside_mask_changed_pixels'], 0)
        self.assertEqual(stats['roi'], [24, 16, 40, 32])

    def test_empty_mask_passes_exactly_without_model_call(self):
        self.mask[:] = 0
        with patch('builtins.print'):
            result, stats = repair_frame(self.frame, self.mask, options=self.options, channel='alpha', infer=lambda *_: self.fail('model must not run'), budget=1_000_000)
        np.testing.assert_array_equal(result, self.frame)
        self.assertEqual(stats['model_calls'], 0)

    def test_luma_mask_ignores_opaque_background_alpha(self):
        self.mask[:, :, 3] = 255; self.mask[16:32, 24:40, :3] = 255
        result, stats = repair_frame(self.frame, self.mask, options=self.options, channel='luma', infer=lambda image, mask: np.zeros_like(image), budget=1_000_000)
        self.assertEqual(stats['mask_pixels'], 256)
        self.assertEqual(result[20, 30, 0], 0)
        self.assertEqual(result[0, 0, 0], 150)

    def test_grow_and_feather_remain_inside_expanded_region(self):
        self.options = normalize_options(grow=2, feather=2., context=0)
        result, stats = self.repair()
        self.assertEqual(stats['mask_pixels'], 400)
        self.assertGreater(int(result[14, 22, 0]), 51)
        self.assertLess(int(result[14, 22, 0]), 150)
        np.testing.assert_array_equal(result[:14], self.frame[:14])

    def test_roi_context_resize_and_multiple_of_eight_padding(self):
        self.frame = np.full((120, 180, 4), 255, np.uint8); self.mask = self.frame.copy()
        self.options = normalize_options(grow=0, context=16, model_max_edge=65)
        seen = []
        def model(image, mask):
            seen.append((image.shape, mask.shape)); return image
        result, stats = repair_frame(self.frame, self.mask, options=self.options, channel='alpha', infer=model, budget=4_000_000)
        self.assertEqual(seen, [((1, 3, 64, 72), (1, 1, 64, 72))])
        self.assertTrue(stats['resized']); self.assertEqual(stats['model_pixels'], 4608)
        np.testing.assert_array_equal(result, self.frame)

    def test_nonfinite_wrong_shape_and_buffer_budget_rejected(self):
        for output in (np.zeros((1, 1, 64, 64), np.float32), np.full((1, 3, 64, 64), np.nan, np.float32), np.zeros((1, 3, 64, 64), np.float64)):
            with self.subTest(shape=output.shape, dtype=output.dtype), self.assertRaises(ValueError):
                repair_frame(self.frame, self.mask, options=self.options, channel='alpha', infer=lambda *_: output, budget=1_000_000)
        with self.assertRaisesRegex(ValueError, 'BUDGET'):
            repair_frame(self.frame, self.mask, options=self.options, channel='alpha', infer=lambda *_: self.fail(), budget=8)

    def test_thin_mask_disappearing_during_downscale_is_rejected(self):
        source = np.full((120, 180, 4), 255, np.uint8); mask = np.zeros_like(source); mask[-1, -1, 3] = 255
        with self.assertRaisesRegex(ValueError, 'MASK_LOST_DURING_RESIZE'):
            repair_frame(source, mask, options=normalize_options(grow=0, context=1024, model_max_edge=64), channel='alpha', infer=lambda *_: self.fail('empty downsampled mask must not run'), budget=4_000_000)

    def test_paired_stream_partial_reads_empty_frames_and_alpha_hashes(self):
        class Partial(io.BytesIO):
            def read(self, size=-1): return super().read(min(size, 13))
        pair = np.concatenate([self.frame, self.mask], axis=1)
        empty = np.concatenate([self.frame, np.zeros_like(self.mask)], axis=1)
        output = io.BytesIO()
        metrics = process_frames(Partial(pair.tobytes() + empty.tobytes()), output, width=64, height=48, frames=2,
                                 options=self.options, channel='alpha', infer=lambda image, mask: image)
        self.assertEqual(metrics['model_calls'], 1); self.assertEqual(metrics['empty_mask_frames'], 1)
        self.assertEqual(metrics['input_alpha_sha256'], metrics['output_alpha_sha256'])
        self.assertEqual(metrics['rgba_bytes'], 2 * self.frame.nbytes)
        self.assertEqual(metrics['state_reset'], 'per-frame')
        self.assertEqual(len(output.getvalue()), 2 * self.frame.nbytes)

    def test_truncated_extra_streams_and_invalid_options_rejected(self):
        pair = np.concatenate([self.frame, self.mask], axis=1).tobytes()
        for data in (pair[:-1], pair + b'x'):
            with self.assertRaises(ValueError):
                process_frames(io.BytesIO(data), io.BytesIO(), width=64, height=48, frames=1, options=self.options, channel='alpha', infer=lambda image, mask: image)
        for options in ({'threshold': math.nan}, {'feather': -1}, {'grow': True}, {'context': 1025}, {'model_max_edge': 63}):
            with self.subTest(options=options), self.assertRaises(AppError): normalize_options(**options)


    def test_harmonic_plane_texture_and_single_quantization(self):
        y,x=np.indices((48,64))
        truth=np.stack([30+x+y,60+x,100+y],axis=2).astype(np.float32)
        self.frame[:,:,:3]=truth.astype(np.uint8)
        self.frame[16:32,24:40,:3]=[255,0,255]
        wanted=truth.copy();wanted[21:25,29:33,:]+=.75
        self.options=normalize_options(grow=0,context=64,blend_mode='harmonic')
        def infer(image,mask):
            prediction=(wanted+20)/255
            prediction=np.pad(prediction,((0,16),(0,0),(0,0)),mode='edge')
            return np.ascontiguousarray(prediction.transpose(2,0,1)[None],dtype=np.float32)
        result,stats=repair_frame(self.frame,self.mask,options=self.options,channel='alpha',infer=infer,budget=4_000_000)
        selected=self.mask[:,:,3]!=0
        np.testing.assert_array_equal(result[selected,:3],np.rint(wanted[selected]).astype(np.uint8))
        np.testing.assert_array_equal(result[~selected],self.frame[~selected])
        np.testing.assert_array_equal(result[:,:,3],self.frame[:,:,3])
        self.assertEqual(stats['blend_detail']['selected_pixels'],256)
        self.assertGreater(stats['state_bytes'],stats['base_state_bytes'])

    def test_harmonic_rejects_full_mask_and_budget_before_model_and_bypasses_empty(self):
        self.options=normalize_options(grow=0,context=0,blend_mode='harmonic')
        def never(*args):self.fail('Invalid selection must not load or invoke a model')
        with self.assertRaisesRegex(ValueError,'BUDGET'):
            repair_frame(self.frame,self.mask,options=self.options,channel='alpha',infer=never,budget=250_000)
        self.mask[:,:,3]=255
        with self.assertRaisesRegex(ValueError,'NO_BOUNDARY'):
            repair_frame(self.frame,self.mask,options=self.options,channel='alpha',infer=never,budget=4_000_000)
        self.mask[:]=0
        result,stats=repair_frame(self.frame,self.mask,options=self.options,channel='alpha',infer=never,budget=4_000_000)
        np.testing.assert_array_equal(result,self.frame);self.assertIsNone(stats['blend_detail'])

    def test_harmonic_nonconvergence_writes_no_partial_frame(self):
        options=normalize_options(grow=0,context=0,blend_mode='harmonic',blend_max_iterations=1)
        rng=np.random.default_rng(13);self.frame[:,:,:3]=rng.integers(0,256,(48,64,3),dtype=np.uint8)
        destination=io.BytesIO();pair=np.concatenate([self.frame,self.mask],axis=1)
        with self.assertRaisesRegex(ValueError,'NOT_CONVERGED'):
            process_frames(io.BytesIO(pair.tobytes()),destination,width=64,height=48,frames=1,options=options,channel='alpha',infer=lambda image,mask:np.full_like(image,.2))
        self.assertEqual(destination.getvalue(),b'')

    def test_blend_option_validation(self):
        for kw in ({'blend_mode':[]},{'blend_mode':'unknown'},{'blend_max_iterations':True},{'blend_max_iterations':0},{'blend_max_iterations':10001},{'blend_tolerance':float('nan')},{'blend_tolerance':float('inf')},{'blend_tolerance':0},{'blend_tolerance':.02},{'blend_tolerance':True}):
            with self.subTest(kw=kw),self.assertRaises(AppError):normalize_options(**kw)


MOCK_WORKER = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, PRODUCT_SOURCE)
sys.path.insert(0, NUMPY_SOURCE)
import numpy as np
from ai_ad_editor.inpainting_frames import process_frames
from ai_ad_editor.utils import atomic_write_json
request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
mode=sys.argv[2]
if mode in {'wait','cancel'}:
    if mode=='cancel': Path(sys.argv[3]).write_text('cancel',encoding='utf-8')
    time.sleep(20)
if mode=='fail': raise RuntimeError('controlled model failure')
info=request['video']
metrics=process_frames(sys.stdin.buffer,sys.stdout.buffer,width=info['width'],height=info['height'],frames=info['frames'],
                      options=request['inpainting'],channel=request['mask']['channel'],infer=lambda image,mask: np.full_like(image,.2))
response={'protocol':request['protocol'],'engine':request['engine'],'status':'succeeded','network':'disabled','blocked_network_events':[],
          'request_sha256':request['request_sha256'],'source_sha256':request['source']['sha256'],'adapter_sha256':request['adapter']['sha256'],
          'mask_sha256':request['mask']['sha256'],'mask_plan_sha256':request['mask']['plan_sha256'],'inpainting':request['inpainting'],
          'providers':['torch-'+request['adapter']['settings']['device']],'metrics':metrics}
if mode=='bad_mask_hash': response['mask_sha256']='sha256:'+'0'*64
if mode=='bad_device': response['providers']=['torch-cuda']
if mode=='bad_outside': metrics['outside_mask_changed_pixels']=1
if mode=='bad_alpha': metrics['output_alpha_sha256']='sha256:'+'0'*64
if mode=='bad_calls': metrics['model_calls']+=1
if mode=='bad_rgba': metrics['rgba_sha256']='sha256:'+'0'*64
if mode=='bad_network': response['blocked_network_events']=['socket.connect']
if mode=='bad_blend': metrics['blend']['mode']='invented'
if mode=='bad_blend_type': metrics['blend']['max_selected_pixels']=False
if mode=='bad_blend_budget': metrics['blend']['owned_array_peak_bytes']+=1
if mode=='bad_blend_residual': metrics['blend']['residual_ratio_max']=2
if mode=='bad_blend_samples': metrics['blend']['samples']=[]
if mode=='tamper_mask':
    with Path(request['mask']['path']).open('ab') as changed: changed.write(b'changed')
if mode=='race': Path(sys.argv[3]).write_bytes(b'external editor output')
atomic_write_json(Path(request['response']),response)
'''


class NativeInpaintingTests(unittest.TestCase):
    metadata = matting_fixture.NativeMattingTests.metadata
    decode = matting_fixture.NativeMattingTests.decode
    fake_command = matting_fixture.NativeMattingTests.fake_command

    @classmethod
    def setUpClass(cls): configure_local_runtime()

    def setUp(self):
        matting_fixture.NativeMattingTests.setUp(self)
        self.model = self.base / 'model.pt'
        with zipfile.ZipFile(self.model, 'w') as z:
            z.writestr('archive/code/__torch__.py', '# protocol fixture only; not an inference model')
            z.writestr('archive/constants.pkl', b'protocol fixture')
        self.worker.write_text(MOCK_WORKER.replace('PRODUCT_SOURCE', repr(str(Path(__file__).resolve().parents[1] / 'src'))).replace('NUMPY_SOURCE', repr(str(Path(np.__file__).resolve().parent.parent))), encoding='utf-8')
        self.mask = self.base / 'mask.png'
        mask = np.zeros((48, 64, 4), np.uint8); mask[16:32, 24:40, 3] = 255
        Image.fromarray(mask).save(self.mask)
        self.mask_id = self.ingest(self.mask)
        self.options = ['--project', str(self.root), '--adapter-id', 'lama', '--engine', INPAINT_ENGINE, '--model-path', str(self.model), '--executable', sys.executable, '--evidence', str(self.evidence)]
        self.output = self.root / 'assets/derived/repaired.mov'

    def ingest(self, path):
        code, data = invoke('media', 'ingest', '--project', str(self.root), '--input', str(path), '--license-spdx', 'CC0-1.0', '--verification-status', 'verified', '--permitted-use', 'commercial_ad', '--evidence', str(self.evidence))
        self.assertEqual(code, 0, data); return data['data']['asset']['id']

    def register(self):
        code, data = invoke('media', 'adapter', 'register', *self.options)
        self.assertEqual(code, 0, data); return data['data']['adapter']

    def command(self):
        return ['media', 'inpaint', '--project', str(self.root), '--asset-id', self.asset_id, '--mask-asset-id', self.mask_id, '--adapter-id', 'lama', '--derived-asset-id', 'repaired', '--mask-grow', '0', '--apply', '--track-id', 'track_video_1', '--audio-track-id', 'track_audio_1']

    def assert_clean_failure(self, before):
        self.assertEqual(self.metadata(), before)
        self.assertFalse(self.output.exists())
        self.assertFalse(list((self.root / 'cache/inpainting').glob('*')))
        self.assertFalse((self.root / 'operations/project-transaction.json').exists())

    def test_registration_dry_run_inspection_and_plan_have_no_inference(self):
        before = self.metadata()
        self.assertEqual(invoke('media', 'adapter', 'register', *self.options, '--dry-run')[0], 0)
        self.assertEqual(self.metadata(), before)
        adapter = self.register(); self.assertEqual(len(adapter['artifacts']), 14)
        self.assertTrue(verify_adapter(adapter)['ok'])
        before = self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as worker:
            code, data = invoke(*self.command(), '--dry-run')
            self.assertEqual(code, 0, data); worker.assert_not_called()
            self.assertEqual(data['command'], 'media.inpaint')
            self.assertTrue(mask_unchanged(data['data']['plan']))
            self.assertEqual(set(data['data']['rights_dependencies']), {self.asset_id, self.mask_id, adapter['rights_ref']})
            self.assertEqual(invoke('media', 'adapter', 'inspect', '--project', str(self.root), '--adapter-id', 'lama')[0], 0)
        self.assertEqual(self.metadata(), before)

    def test_harmonic_cli_dry_run_and_real_protocol_rollback(self):
        self.register();before=self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as worker:
            for flags in (['--blend-max-iterations','200'],['--blend-tolerance','.001'],['--repair-blend','harmonic','--blend-max-iterations','0'],['--repair-blend','harmonic','--blend-tolerance','nan']):
                code,data=invoke(*self.command(),*flags,'--dry-run');self.assertEqual(code,2,data)
            code,data=invoke(*self.command(),'--repair-blend','harmonic','--dry-run');self.assertEqual(code,0,data)
            self.assertEqual(data['data']['plan']['inpainting']['blend_mode'],'harmonic')
            self.assertFalse(data['data']['plan']['blend_budget']['mask_pixel_count_known'])
            worker.assert_not_called()
        self.assertEqual(self.metadata(),before)
        with self.fake_command():code,data=invoke(*self.command(),'--repair-blend','harmonic','--blend-max-iterations','1')
        self.assertEqual(code,6,data);self.assert_clean_failure(before)
        for mode in ('bad_blend_budget','bad_blend_residual','bad_blend_samples'):
            with self.subTest(mode=mode),self.fake_command(mode):
                code,data=invoke(*self.command(),'--repair-blend','harmonic');self.assertEqual(code,6,data)
            self.assert_clean_failure(before)
        with self.fake_command():code,data=invoke(*self.command(),'--repair-blend','harmonic','--idempotency-key','blend-once')
        self.assertEqual(code,0,data)
        metrics=data['data']['inpainting']['worker']['metrics']
        self.assertEqual(metrics['blend']['frames'],4);self.assertLessEqual(metrics['blend']['residual_ratio_max'],1)
        output=self.decode(self.output);selected=np.zeros((48,64),bool);selected[16:32,24:40]=True
        np.testing.assert_array_equal(output[:,~selected],self.frames[:,~selected]);np.testing.assert_array_equal(output[:,:,:,3],self.frames[:,:,:,3])
        with patch('ai_ad_editor.cli.matte_native') as worker:
            for flags in ([],['--repair-blend','harmonic','--blend-max-iterations','1999'],['--repair-blend','harmonic','--blend-tolerance','.00001']):
                code,result=invoke(*self.command(),*flags,'--idempotency-key','blend-once');self.assertEqual(code,2,result)
                self.assertEqual(result['errors'][0]['code'],'IDEMPOTENCY_CONFLICT')
            worker.assert_not_called()

    def test_registration_rejects_raw_checkpoint_remote_or_missing_evidence(self):
        bad = self.base / 'raw.pt'; bad.write_bytes(b'not a TorchScript archive')
        for flag, value in (('--model-path', str(bad)), ('--model-path', 'https://invalid.example/model.pt'), ('--evidence', str(self.base / 'absent.json')), ('--executable', str(self.worker)), ('--threads', '0')):
            options = self.options.copy()
            if flag in options: options[options.index(flag) + 1] = value
            else: options.extend([flag, value])
            self.assertNotEqual(invoke('media', 'adapter', 'register', *options)[0], 0)
        with self.assertRaises(AppError): settings(device='auto')
        with zipfile.ZipFile(bad, 'w') as z: z.writestr('../code/evil', b'x'); z.writestr('a/constants.pkl', b'x')
        with self.assertRaises(AppError): check_model(bad)

    def test_full_pipeline_preserves_alpha_outside_audio_and_rights(self):
        adapter = self.register()
        with self.fake_command(): code, data = invoke(*self.command())
        self.assertEqual(code, 0, data)
        rgba = self.decode(self.output)
        expected = self.frames.copy(); expected[:, 16:32, 24:40, :3] = 51
        np.testing.assert_array_equal(rgba, expected)
        np.testing.assert_allclose(self.decode(self.output, audio=True), self.decode(self.source, audio=True), atol=1e-6)
        metrics = data['data']['inpainting']['worker']['metrics']
        self.assertEqual(metrics['model_calls'], 4); self.assertEqual(metrics['mask_pixels'], 4 * 256)
        self.assertEqual(metrics['input_alpha_sha256'], metrics['output_alpha_sha256'])
        self.assertEqual(set(data['data']['rights']['derived_from']), {self.asset_id, self.mask_id, adapter['rights_ref']})
        self.assertEqual(invoke('validate', '--project', str(self.root))[0], 0)
        self.assertEqual(invoke('policy', 'audit', '--project', str(self.root))[0], 0)
        self.assertEqual(invoke('rights', 'check', '--project', str(self.root))[0], 7)

    def test_dynamic_alpha_mask_clock_and_empty_frames(self):
        frames = np.zeros_like(self.frames); frames[1:3, 16:32, 24:40, 3] = 255
        path = self.base / 'mask.mov'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', '64x48', '-framerate', '8', '-i', 'pipe:0', '-c:v', 'qtrle', '-pix_fmt', 'argb', str(path)], input=frames.tobytes(), capture_output=True, check=True)
        self.mask_id = self.ingest(path); self.register()
        with self.fake_command(): code, data = invoke(*self.command())
        self.assertEqual(code, 0, data)
        expected = self.frames.copy(); expected[1:3, 16:32, 24:40, :3] = 51
        np.testing.assert_array_equal(self.decode(self.output), expected)
        self.assertEqual(data['data']['inpainting']['worker']['metrics']['empty_mask_frames'], 2)

    def test_luma_png_and_explicit_same_aspect_mask_resize(self):
        mask = np.zeros((24, 32, 3), np.uint8); mask[8:16, 12:20] = 255
        path = self.base / 'luma.png'; Image.fromarray(mask).save(path); self.mask_id = self.ingest(path); self.register()
        self.assertNotEqual(invoke(*self.command(), '--dry-run')[0], 0)
        self.assertNotEqual(invoke(*self.command(), '--mask-channel', 'luma', '--dry-run')[0], 0)
        with self.fake_command(): code, data = invoke(*self.command(), '--mask-channel', 'luma', '--mask-resize', 'nearest')
        self.assertEqual(code, 0, data)
        self.assertEqual(data['data']['inpainting']['worker']['metrics']['mask_pixels'], 4 * 256)

    def test_short_mask_bad_geometry_range_and_output_rejected(self):
        self.register(); before = self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as worker:
            for flags in (['--mask-start-seconds', '1'], ['--mask-grow', '-1'], ['--mask-feather', 'nan'], ['--context-pixels', '2048'], ['--model-max-edge', '32'], ['--fps', 'nan'], ['--end-seconds', '2'], ['--output', '../outside.mov'], ['--audio-track-id', 'track_video_1']):
                self.assertNotEqual(invoke(*self.command(), *flags, '--dry-run')[0], 0)
            worker.assert_not_called()
        self.assertEqual(self.metadata(), before)
        frames = np.zeros((1, 48, 64, 4), np.uint8)
        path = self.base / 'short.mov'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', '64x48', '-framerate', '8', '-i', 'pipe:0', '-c:v', 'qtrle', '-pix_fmt', 'argb', str(path)], input=frames.tobytes(), capture_output=True, check=True)
        self.mask_id = self.ingest(path)
        self.assertNotEqual(invoke(*self.command(), '--dry-run')[0], 0)

    def test_model_mask_and_evidence_tamper_rejected_before_worker(self):
        adapter = self.register()
        project = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))
        mask_path = self.root / next(a['uri'] for a in project['assets'] if a['id'] == self.mask_id)
        for path in (self.model, self.evidence, mask_path):
            original = path.read_bytes(); path.write_bytes(original + b'changed')
            with patch('ai_ad_editor.cli.matte_native') as worker:
                self.assertEqual(invoke(*self.command())[0], 10); worker.assert_not_called()
            path.write_bytes(original)
        changed = copy.deepcopy(adapter); changed['settings']['precision'] = 'float16'; changed['sha256'] = manifest_hash(changed)
        self.assertFalse(verify_adapter(changed)['ok'])

    def test_adapter_role_rejects_matting_and_tracking(self):
        self.register()
        for command in (['media', 'matting', '--derived-asset-id', 'wrong'], ['media', 'track', '--roi', '0,0,1,1']):
            code, data = invoke(*command, '--project', str(self.root), '--asset-id', self.asset_id, '--adapter-id', 'lama', '--dry-run')
            self.assertEqual(code, 10, data)

    def test_worker_integrity_pixel_contract_and_decode_mismatch_roll_back(self):
        self.register(); before = self.metadata()
        for mode in ('bad_mask_hash', 'bad_device', 'bad_outside', 'bad_alpha', 'bad_calls', 'bad_rgba', 'bad_network', 'bad_blend', 'bad_blend_type', 'fail'):
            with self.subTest(mode=mode), self.fake_command(mode):
                code, data = invoke(*self.command())
                self.assertEqual(code, 6, data)
            self.assert_clean_failure(before)

    def test_cancel_timeout_kill_pipeline_and_restore_metadata(self):
        self.register(); before = self.metadata(); real = subprocess.Popen
        for mode in ('wait', 'cancel'):
            children = []; cancel = self.root / 'cache' / ('cancel-' + mode)
            def capture(*a, **kw):
                p = real(*a, **kw); children.append(p); return p
            with self.fake_command(mode, str(cancel)), patch('ai_ad_editor.local_matting.subprocess.Popen', side_effect=capture):
                code, data = invoke(*self.command(), '--timeout-seconds', '2', '--cancel-file', str(cancel))
            self.assertEqual(code, 8, data)
            self.assertGreaterEqual(len(children), 3); self.assertTrue(all(p.poll() is not None for p in children))
            self.assert_clean_failure(before)

    def test_mask_changed_during_inference_and_save_failure_clean_outputs(self):
        self.register(); before = self.metadata()
        project = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))
        mask_path = self.root / next(a['uri'] for a in project['assets'] if a['id'] == self.mask_id)
        original = mask_path.read_bytes()
        with self.fake_command('tamper_mask'): code, data = invoke(*self.command())
        self.assertEqual(code, 10, data); self.assert_clean_failure(before); mask_path.write_bytes(original)
        with self.fake_command(), patch('ai_ad_editor.cli.save_project', side_effect=OSError('controlled disk failure')):
            code, data = invoke(*self.command())
        self.assertEqual(code, 6, data); self.assert_clean_failure(before)

    def test_idempotency_package_and_snapshot_restore_include_registry(self):
        self.register()
        with self.fake_command() as worker:
            first = invoke(*self.command(), '--idempotency-key', 'repair-1'); second = invoke(*self.command(), '--idempotency-key', 'repair-1')
        self.assertEqual(first[0], 0, first[1]); self.assertEqual(second[0], 0, second[1]); self.assertEqual(worker.call_count, 1)
        package = self.base / 'repaired.aevpkg.zip'
        self.assertEqual(invoke('convert', 'export', '--project', str(self.root), '--output', str(package), '--target-format', 'package')[0], 0)
        with zipfile.ZipFile(package) as z: self.assertTrue(any(n.endswith('models/visual-adapters.json') for n in z.namelist()))
        snapshot = first[1]['data']['snapshot_id']
        code, data = invoke('project', 'restore', '--project', str(self.root), '--snapshot', snapshot)
        self.assertEqual(code, 0, data)
        project = json.loads((self.root / 'project.json').read_text(encoding='utf-8'))
        self.assertNotIn('repaired', {a['id'] for a in project['assets']})
        self.assertEqual(invoke('media', 'adapter', 'inspect', '--project', str(self.root), '--adapter-id', 'lama')[0], 0)

    def test_explicit_video_mask_offset_and_selected_source_range_keep_clocks(self):
        frames = np.zeros((8, 48, 64, 4), np.uint8); frames[2, 16:32, 24:40, 3] = 255
        path = self.base / 'offset-mask.mov'
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n', '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', '64x48', '-framerate', '8', '-i', 'pipe:0', '-c:v', 'qtrle', '-pix_fmt', 'argb', str(path)], input=frames.tobytes(), capture_output=True, check=True)
        self.mask_id = self.ingest(path); self.register()
        with self.fake_command():
            code, data = invoke(*self.command(), '--start-seconds', '.125', '--end-seconds', '.375', '--mask-start-seconds', '.25')
        self.assertEqual(code, 0, data)
        expected = self.frames[1:3].copy(); expected[0, 16:32, 24:40, :3] = 51
        np.testing.assert_array_equal(self.decode(self.output), expected)
        self.assertEqual(len(self.decode(self.output, audio=True)), 12000)
        self.assertEqual(data['data']['inpainting']['worker']['metrics']['empty_mask_frames'], 1)

    def test_missing_mask_rights_and_incompatible_aspect_are_rejected(self):
        from ai_ad_editor.rights import load_ledger, save_ledger
        self.register(); ledger = load_ledger(self.root)
        for record in ledger['records']:
            if record['asset_id'] == self.mask_id: record['sha256'] = 'sha256:' + '0' * 64
        save_ledger(self.root, ledger)
        code, data = invoke(*self.command(), '--dry-run')
        self.assertEqual(code, 7, data)
        wrong = self.base / 'wrong-aspect.png'; Image.new('RGBA', (32, 32), 'white').save(wrong)
        self.mask_id = self.ingest(wrong)
        self.assertNotEqual(invoke(*self.command(), '--mask-resize', 'nearest', '--dry-run')[0], 0)

    def test_existing_output_publish_race_and_overlap_preserve_existing_data(self):
        self.register(); self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_bytes(b'existing')
        with patch('ai_ad_editor.cli.matte_native') as worker:
            self.assertEqual(invoke(*self.command())[0], 2); worker.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b'existing'); self.output.unlink()
        with self.fake_command('race', str(self.output)): code, data = invoke(*self.command())
        self.assertEqual(code, 6, data); self.assertEqual(self.output.read_bytes(), b'external editor output')
        self.output.unlink()
        with self.fake_command(): self.assertEqual(invoke(*self.command())[0], 0)
        command = self.command(); command[command.index('--derived-asset-id') + 1] = 'second'
        with patch('ai_ad_editor.cli.matte_native') as worker:
            self.assertEqual(invoke(*command)[0], 2); worker.assert_not_called()

    def test_mask_plan_tamper_rejected_even_with_same_mask_file(self):
        self.register(); code, value = invoke(*self.command(), '--dry-run')
        self.assertEqual(code, 0, value)
        plan = value['data']['plan']; self.assertTrue(mask_unchanged(plan))
        plan['mask']['start_seconds'] += .1
        self.assertFalse(mask_unchanged(plan))
