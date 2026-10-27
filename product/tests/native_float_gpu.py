"""Explicit real-device suite; absence of a compatible GPU is a failure."""
import copy
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_composite import composite_rgba
from ai_ad_editor.float_geometry import resample_rgba
from ai_ad_editor.float_gpu import FloatGPUSession
from ai_ad_editor.float_gpu_native import NativeGPU

RECEIPTS = []


class NativeFloatGPUTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1]/'.runtime/temp'
        base.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='float-gpu-', dir=base)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.gpu = FloatGPUSession(self.root, {'projection_acceleration': {'mode': 'require'}})
        self.gpu.__enter__()
        self.addCleanup(self.close)

    def close(self):
        self.gpu.__exit__(None, None, None)
        self.assertTrue(self.gpu.evidence['worker_closed'])
        self.assertTrue(self.gpu.evidence['shared_handles_closed'])
        self.assertTrue(self.gpu.evidence['control']['threads_closed'])
        self.assertTrue(self.gpu.evidence['control']['streams_closed'])
        RECEIPTS.append({'test': self.id(), 'evidence': copy.deepcopy(self.gpu.evidence)})

    def random(self, h=27, w=39):
        a = np.random.default_rng(31).random((h, w, 4), dtype=np.float32)
        a[:, :, :3] = a[:, :, :3]*2-0.4
        a[::4, ::3, 3] = 0
        return a

    def test_independent_probe_and_subnormal_bits(self):
        self.assertTrue(self.gpu.active)
        self.assertEqual(self.gpu.evidence['probe']['actual_gpu_operations'], 9)
        self.assertEqual(self.gpu.evidence['probe']['optical_gpu_operations'],3)
        self.assertLessEqual(max(self.gpu.evidence['probe']['optical_max_errors'].values()),3e-6)
        self.assertTrue(self.gpu.evidence['probe']['subnormal_over_bit_exact'])
        self.assertTrue(self.gpu.evidence['probe']['subnormal_affine_bit_exact'])
        self.assertLessEqual(max(self.gpu.evidence['probe']['max_errors'].values()), 3e-7)

    def test_all_65536_levels_survive_identity_and_source_over(self):
        levels = np.arange(65536, dtype=np.float32).reshape(256, 256)/65535
        a = np.stack([levels, levels, levels, np.ones_like(levels)], axis=-1)
        actual, _ = self.gpu.resample(a, (256, 256), [[1, 0, 0], [0, 1, 0]])
        np.testing.assert_array_equal(actual, a)
        np.testing.assert_array_equal(self.gpu.over(np.zeros_like(a), a), a)

    def test_subpixel_affine_extended_RGB_and_hidden_alpha(self):
        a = self.random()
        before = a.copy()
        for inverse in ([[.89, .12, -.25], [-.08, 1.03, .4]], [[1, 0, 1e8], [0, 1, -1e8]],
                        [[0, -1, 29], [1, 0, -3]]):
            ref, _ = resample_rgba(a, (31, 29), inverse)
            actual, _ = self.gpu.resample(a, (31, 29), inverse)
            np.testing.assert_allclose(actual, ref, rtol=0, atol=3e-7)
        np.testing.assert_array_equal(a, before)

    def test_source_over_opacity_against_cpu_and_input_immutable(self):
        a = self.random(); b = a[::-1].copy(); before = [a.copy(), b.copy()]
        for opacity in (0., .123456789, 1.):
            ref, _ = composite_rgba(a, b, opacity=opacity)
            np.testing.assert_array_equal(self.gpu.over(a, b, opacity), ref)
        np.testing.assert_array_equal(a, before[0]); np.testing.assert_array_equal(b, before[1])

    def test_four_ordered_components_with_nontransparent_base(self):
        base = self.random(); masks = np.random.default_rng(9).integers(0, 256, (4, 27, 39), dtype=np.uint8)
        colors = [[.2, -.1, 1.2, .37], [.123456789, .9, .3, .8], [.01, .3, .7, 1.], [.4, .6, .9, .02]]
        ref = base.copy()
        for mask, color in zip(masks, colors):
            old = ref.astype(np.float64)
            alpha = mask.astype(np.float64)[:, :, None]*(color[3]/255)
            total = alpha+old[:, :, 3:4]*(1-alpha)
            top = np.asarray(color[:3])*alpha+old[:, :, :3]*old[:, :, 3:4]*(1-alpha)
            ref[:, :, :3] = np.divide(top, total, out=np.zeros_like(top), where=total > 0)
            ref[:, :, 3:4] = total
        actual = self.gpu.paint(masks, colors, base=base)
        np.testing.assert_array_equal(actual, ref)

    def test_binary_selection_preserves_whole_paragraph(self):
        a = self.random(); b = a[::-1].copy()
        mask = np.where(np.indices(a.shape[:2])[1] % 2, 255, 0).astype(np.uint8)
        np.testing.assert_array_equal(self.gpu.select(a, b, mask), np.where(mask[:, :, None] != 0, b, a))

    def test_real_text_styles_and_word_clock_match_cpu(self):
        import test_float_text as text_tests
        fixture = text_tests.FloatTextTests('runTest'); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        from ai_ad_editor.float_text import FloatTextHost
        host = FloatTextHost(fixture.root, fixture.assets, text_tests.LINEAR, 100, Fraction(10), gpu=self.gpu)
        cases = [(fixture.title(), 0), (fixture.title('Hello world', box=True, boxcolor='#20506060',
            borderw=2, bordercolor='#a03060c0', shadowx=2, shadowy=3, shadowcolor='#10203080'), 13)]
        words = fixture.title('Hello world', active_color='#ff9020a0')
        words['subtitle']['word_timing'] = [{'text': 'Hello', 'start_tick': 0, 'end_tick': 50},
                                             {'text': 'world', 'start_tick': 50, 'end_tick': 100}]
        words['subtitle']['ticks_per_second'] = 100
        cases += [(words, 0), (words, 49), (words, 50), (words, 99)]
        for clip, tick in cases:
            expected, _ = fixture.sample(clip, tick=tick)
            actual, _ = fixture.sample(clip, tick=tick, host=host)
            np.testing.assert_allclose(actual, expected, rtol=0, atol=3e-7)
        self.assertGreater(self.gpu.evidence['operations'].get('paint', 0), 0)

    def test_invalid_late_tile_fails_without_mutating_input(self):
        a = self.random(257, 256); a[-1, -1, 3] = np.nan; before = a.copy()
        with self.assertRaises(AppError): self.gpu.over(a, np.zeros_like(a))
        np.testing.assert_array_equal(a, before)

    def test_runtime_bad_mask_is_failure_and_worker_closed(self):
        a = self.random(); before = a.copy(); mask = np.full(a.shape[:2], 7, np.uint8)
        with self.assertRaises(AppError): self.gpu.select(a, a, mask)
        self.assertEqual(self.gpu.evidence['status'], 'failed')
        self.assertFalse(self.gpu.active); self.assertTrue(self.gpu.evidence['worker_closed'])
        np.testing.assert_array_equal(a, before)

    def test_worker_exit_is_failure_without_cpu_retry(self):
        self.gpu.process.terminate(); self.gpu.process.wait(timeout=5)
        with self.assertRaises(AppError): self.gpu.over(self.random(), self.random())
        self.assertEqual(self.gpu.evidence['status'], 'failed')
        self.assertFalse(self.gpu.evidence['runtime_failure_CPU_fallback'])

    def test_cancel_poll_during_request_stops_only_owned_worker(self):
        calls = [0]
        def cancel():
            calls[0] += 1
            if calls[0] >= 3: raise AppError('CANCELLED', 'test cancellation', exit_code=8)
        self.gpu.poll = cancel
        with self.assertRaisesRegex(AppError, 'test cancellation'): self.gpu.over(self.random(), self.random())
        self.assertEqual(self.gpu.evidence['status'], 'cancelled')
        self.assertTrue(self.gpu.evidence['worker_closed'])

    def test_timeout_closes_worker_without_cpu_retry(self):
        original = self.gpu._wait
        with patch.object(self.gpu, '_wait', side_effect=lambda number, timeout: original(number+1, .01)):
            with self.assertRaises(AppError) as result: self.gpu.over(self.random(), self.random())
        self.assertEqual(result.exception.code, 'FLOAT_GPU_TIMEOUT')
        self.assertTrue(self.gpu.evidence['worker_closed'])

    def test_many_owned_control_packets_and_shape_growth(self):
        a = self.random(2, 3)
        for index in range(120):
            if index in (30, 60, 90): a = self.random(3+index//10, 7+index//10)
            expected, _ = composite_rgba(a, a, opacity=.73)
            np.testing.assert_array_equal(self.gpu.over(a, a, .73), expected)
        self.assertEqual(self.gpu.evidence['operations']['over'], 120)
        self.assertEqual(len(self.gpu.segments), 3)
        self.assertLessEqual(self.gpu.evidence['maximum_host_shared_bytes'], self.gpu.config['max_working_bytes'])
        self.assertFalse((self.gpu.directory/'request.json').exists())
        self.assertFalse((self.gpu.directory/'response.json').exists())
        self.assertEqual(self.gpu.evidence['control']['received_packets'], 121)


class FloatGPUPolicyTests(unittest.TestCase):
    def test_dry_run_creates_no_context_process_or_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('ai_ad_editor.float_gpu.subprocess.Popen', side_effect=AssertionError('must not launch')):
                with FloatGPUSession(folder, {'projection_acceleration': {'mode': 'require'}}, dry_run=True) as gpu:
                    self.assertFalse(gpu.active); self.assertEqual(gpu.evidence['status'], 'planned')
            self.assertFalse((Path(folder)/'cache').exists())

    def test_off_creates_no_process(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('ai_ad_editor.float_gpu.subprocess.Popen', side_effect=AssertionError('must not launch')):
                with FloatGPUSession(folder, {}) as gpu: self.assertFalse(gpu.active)

    def test_planned_4K_budget_prefer_falls_back_before_process(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('ai_ad_editor.float_gpu.subprocess.Popen', side_effect=AssertionError('must not launch')):
                with FloatGPUSession(folder, {'projection_acceleration': {'mode': 'prefer', 'max_working_bytes': 8*1024**2}},
                                     max_pixels=3840*2160) as gpu:
                    self.assertEqual(gpu.evidence['status'], 'cpu_fallback'); self.assertFalse(gpu.active)

    def test_planned_4K_budget_require_fails_before_process(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('ai_ad_editor.float_gpu.subprocess.Popen', side_effect=AssertionError('must not launch')):
                with self.assertRaises(AppError):
                    with FloatGPUSession(folder, {'projection_acceleration': {'mode': 'require', 'max_working_bytes': 8*1024**2}},
                                         max_pixels=3840*2160): pass

    def test_native_output_rejects_wrong_dtype_and_readonly(self):
        for dtype in (np.float64, np.uint8):
            with self.assertRaises(AppError): NativeGPU.output(np.empty((2, 3, 4), dtype))
        a = np.empty((2, 3, 4), np.float32); a.flags.writeable = False
        with self.assertRaises(AppError): NativeGPU.output(a)

    def test_existing_operation_directory_is_never_cleaned_or_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); existing = root/'cache/float-gpu/already-there'; existing.mkdir(parents=True)
            names = ['init.json', 'request.json', 'response.json', 'receipt.json']
            for name in names: (existing/name).write_bytes(b'previous unrelated content')
            before = {name: (existing/name).read_bytes() for name in names}
            with FloatGPUSession(root, {'projection_acceleration': {'mode': 'prefer'}}, operation_id='already-there') as gpu:
                self.assertFalse(gpu.active); self.assertFalse(gpu.directory_owned)
            self.assertEqual(before, {name: (existing/name).read_bytes() for name in names})

    def test_actual_missing_device_prefer_records_preflight_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            with FloatGPUSession(folder, {'projection_acceleration': {'mode': 'prefer', 'device': '999.999'}}) as gpu:
                self.assertEqual(gpu.evidence['status'], 'cpu_fallback')
                self.assertFalse(gpu.active); self.assertTrue(gpu.evidence['worker_closed'])
                self.assertEqual(gpu.evidence['error']['code'], 'FLOAT_GPU_DEVICE')


class NativeFloatRenderGPUTests(unittest.TestCase):
    def setUp(self):
        import test_float_standard_render as tests
        self.fixture = tests.FloatStandardRenderTests('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_real_encoded_frame_and_PCM_match_CPU(self):
        f = self.fixture
        values = np.arange(65536, dtype=np.float32).reshape(256, 256)/65535
        rgba = np.ones((256, 256, 4), np.float32); rgba[:, :, :3] = values[:, :, None]
        f.visual(rgba)
        cpu = f.execute('cpu.mkv')
        f.p['settings']['projection_acceleration'] = {'mode': 'require'}
        gpu = f.execute('gpu.mkv')
        evidence = gpu['projection_acceleration']
        self.assertEqual(evidence['status'], 'verified')
        self.assertTrue(evidence['worker_closed']); self.assertTrue(evidence['shared_handles_closed'])
        self.assertGreater(evidence['operations']['affine'], 0); self.assertGreater(evidence['operations']['over'], 0)
        np.testing.assert_array_equal(f.decode_y(cpu['path'], 256, 256), f.decode_y(gpu['path'], 256, 256))
        from ai_ad_editor.media import ffmpeg_path
        def audio(path): return f.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', path,
                                         '-map', '0:a:0', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'])
        self.assertEqual(audio(cpu['path']), audio(gpu['path']))
        RECEIPTS.append({'test': self.id(), 'render': copy.deepcopy(gpu)})

    def test_real_encoder_cancel_resume_with_GPU(self):
        self.fixture.p['settings']['projection_acceleration'] = {'mode': 'require'}
        self.fixture.test_mid_producer_cancel_public_resume_and_changed_setting_rejection()
        rows = list((self.fixture.root/'cache/float-gpu').glob('*/receipt.json'))
        import json
        evidence = [json.loads(p.read_bytes()) for p in rows]
        self.assertTrue(any(r['status'] == 'cancelled' for r in evidence))
        self.assertTrue(all(r['worker_closed'] and r['shared_handles_closed'] for r in evidence))
        RECEIPTS.append({'test': self.id(), 'GPU_receipts': evidence})

    def test_public_dry_run_records_GPU_plan_without_worker(self):
        self.fixture.p['settings']['projection_acceleration'] = {'mode': 'require'}
        self.fixture.visual()
        value = self.fixture.execute('planned.mkv', dry_run=True)
        evidence = value['plan']['projection_acceleration']
        self.assertEqual(evidence['status'], 'planned')
        self.assertNotIn('owned_worker_pid', evidence)
        self.assertFalse((self.fixture.root/'cache/float-gpu').exists())


if __name__ == '__main__': unittest.main(verbosity=2)
