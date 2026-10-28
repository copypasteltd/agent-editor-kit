"""Real author previews against independent source, alpha, clock and PCM oracles."""
from bisect import bisect_left
import copy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor import float_preview, preview
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_standard_render import FloatRenderContext
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import project_file, project_write_lock, save_project
import test_float_standard_render as standard_helpers

PREVIEW_RECEIPTS = []


class FloatPreviewTests(unittest.TestCase):
    native = standard_helpers.FloatStandardRenderTests.native
    visual = standard_helpers.FloatStandardRenderTests.visual
    audio = standard_helpers.FloatStandardRenderTests.audio
    invoke = standard_helpers.FloatStandardRenderTests.invoke

    def setUp(self):
        standard_helpers.FloatStandardRenderTests.setUp(self)
        self.runtime = self.base/'preview-runtime.fixture'
        self.runtime.write_bytes(b'preview runtime A')
        self.numpy_runtime = self.base/'numpy-runtime.fixture'
        self.numpy_runtime.write_bytes(b'numpy runtime A')
        for target, name, paths in [(preview, '_runtime_paths', {self.runtime}),
                                    (float_preview, 'runtime_paths', {self.numpy_runtime})]:
            context = patch.object(target, name, return_value=paths)
            context.start(); self.addCleanup(context.stop)

    def execute(self, start=0, end=1, mode='range', **kwargs):
        save_project(self.root, self.p)
        request = preview.plan(self.p, self.s, start_frame=start, end_frame=end, mode=mode, height=kwargs.pop('height', 64))
        with project_write_lock(self.root):
            result = preview.preview_project(self.root, self.p, self.s, request=request, **kwargs)
        PREVIEW_RECEIPTS.append({'test': self.id(), **copy.deepcopy(result)})
        return result

    def reference(self, result):
        data = self.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', result['master'],
            '-map', '0:v:0', '-an', '-pix_fmt', 'gbrapf32le', '-fps_mode', 'passthrough', '-f', 'rawvideo', 'pipe:1'])
        request = result['request']
        planes = np.frombuffer(data, '<f4').reshape(request['frames'], 4, request['height'], request['width'])
        return np.moveaxis(planes[:, [2, 0, 1, 3]], 1, -1)

    def png(self, result):
        data = self.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', result['path'],
            '-an', '-pix_fmt', 'rgba64le', '-f', 'rawvideo', 'pipe:1'])
        request = result['request']
        return np.frombuffer(data, '<u2').reshape(request['height'], request['width'], 4)

    def pcm(self, result):
        return self.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', result['master'], '-map', '0:a:0',
            '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'])

    def transparent(self):
        self.p['settings']['canvas']['background'] = 'transparent'
        self.p['settings']['output'] = {'container': 'webm',
            'video': {'codec': 'libvpx-vp9', 'crf': 0, 'pixel_format': 'yuva420p'}, 'audio': {'codec': 'libopus'}}

    def assert_clean(self):
        self.assertFalse([t.name for t in threading.enumerate() if t.name.startswith(('float-encoder-', 'float-native-'))])
        inventory = preview.cache_list(self.root)
        self.assertFalse([v for v in inventory['entries'] if v['temporary']])

    def test_public_cli_png_preserves_all_65536_independent_gray_levels(self):
        codes = np.arange(65536, dtype=np.uint16).reshape(256, 256)
        rgba = np.ones((256, 256, 4), np.float32)
        rgba[:, :, :3] = codes[:, :, None].astype(np.float32)/65535
        self.visual(rgba); save_project(self.root, self.p)
        code, value = self.invoke('preview', 'frame', '--project', self.root, '--frame', 0, '--height', 256)
        self.assertEqual(code, 0, value)
        result = value['data']; actual = self.png(result)
        np.testing.assert_array_equal(actual[:, :, 0], codes)
        np.testing.assert_array_equal(actual[:, :, 1], codes)
        self.assertEqual(len(np.unique(actual[:, :, 2])), 65536)
        self.assertTrue(np.all(actual[:, :, 3] == 65535))
        self.assertEqual(Path(result['path']).read_bytes()[24:26], b'\x10\x06')
        self.assertTrue(result['pixel_pipeline']['providers_closed_before_publish']); self.assert_clean()

    def test_alpha16_png_and_float32_range_keep_every_original_alpha_code(self):
        codes = np.arange(65536, dtype=np.uint16).reshape(256, 256)
        rgba = np.ones((256, 256, 4), np.float32)
        rgba[:, :, :3] = [.125, .375, .875]; rgba[:, :, 3] = codes.astype(np.float32)/65535
        self.transparent(); self.visual(rgba)
        frame = self.execute(mode='frame', height=256)
        np.testing.assert_array_equal(self.png(frame)[:, :, 3], codes)
        result = self.execute(height=256)
        np.testing.assert_array_equal(self.reference(result)[0, :, :, 3], codes.astype(np.float32)/65535)
        self.assertEqual(result['request']['reference_pixel_format'], 'gbrapf32le'); self.assert_clean()

    def test_reference_retains_composite_changes_smaller_than_one_rgb16_step(self):
        self.s['duration_tick'] = 18000
        rgba = np.broadcast_to(np.array([.5, .25, .75, 1], np.float32), (2, 16, 32, 4)).copy()
        self.visual(rgba)
        self.s['tracks'][0]['clips'][0]['keyframes'] = [{'property': 'opacity', 'keyframes': [
            {'at_tick': 0, 'value': .5, 'interpolation': 'linear'},
            {'at_tick': 9000, 'value': .5000001, 'interpolation': 'linear'}]}]
        result = self.execute(0, 2)
        actual = self.reference(result)[:, 8, 16, 0]
        source = np.float32(32768/65535)
        expected = np.array([source*np.float32(.5), source*np.float32(.5000001)], np.float32)
        np.testing.assert_allclose(actual, expected, atol=3e-8, rtol=0)
        self.assertNotEqual(actual[0], actual[1])
        self.assertEqual(np.rint(actual[0]*65535), np.rint(actual[1]*65535))
        self.assertEqual(result['pixel_pipeline']['reference_float_component_bits'], 32)

    def test_range_keeps_every_pcm_sample_and_partial_author_end(self):
        self.s['duration_tick'] = 112501
        self.visual(np.broadcast_to(np.array([.2, .4, .6, 1], np.float32), (20, 16, 32, 4)).copy())
        samples = self.audio()
        result = self.execute(2, 13)
        expected = np.concatenate((samples[9600:], np.zeros((12001, 2), '<f4')))
        self.assertEqual(self.pcm(result), expected.tobytes())
        self.assertEqual(self.reference(result).shape[0], 11)
        self.assertEqual(result['verified_clock']['decoded_pcm_samples_48000'], 50401)
        self.assertEqual(result['request']['audio_end_sample_48000'], 60001); self.assert_clean()

    def test_nested_native_vfr_reverse_window_keeps_original_interval_oracle(self):
        self.s['duration_tick'] = 225000
        rgba = np.ones((8, 16, 32, 4), np.float32)
        for index in range(8): rgba[index, :, :, :3] = (index+1)/10
        self.visual(rgba, vfr=True)
        child = copy.deepcopy(self.s); child['id'] = 'child'; child['name'] = 'native VFR'
        child['tracks'][0]['id'] = 'child_video'; child['tracks'][1]['id'] = 'child_audio'
        child['tracks'][0]['clips'][0]['id'] = 'native_clip'; self.p['sequences'].append(child)
        self.s['tracks'][0]['clips'] = [{'id': 'container', 'sequence_id': 'child', 'timeline_start_tick': 0,
            'source_in_tick': 0, 'source_out_tick': 225000, 'duration_tick': 225000, 'reverse': True}]
        result = self.execute(3, 21)
        actual = self.reference(result)[:, 8, 16, 0]
        points = [Fraction(n, 8) for n in [0, 1, 3, 5, 8, 11, 15, 20]]
        indices = [max(0, bisect_left(points, Fraction(5, 2)-Fraction(n, 10))-1) for n in range(3, 21)]
        expected = np.array([np.rint(float(rgba[i, 0, 0, 0])*65535)/65535 for i in indices], np.float32)
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-7)
        self.assertEqual(result['pixel_pipeline']['source_receipts']['picture']['demux_origin'], '5')
        self.assertEqual(result['pixel_pipeline']['transport']['selected_author_frames'], [3, 21]); self.assert_clean()

    def test_resize_is_independent_linear_premultiplied_average_after_composite(self):
        tile = np.array([[[1, 0, 0, .125], [0, 1, 0, .375]],
                         [[0, 0, 1, .625], [.25, .5, .75, .875]]], np.float32)
        rgba = np.tile(tile, (64, 64, 1))
        self.transparent(); self.visual(rgba)
        result = self.execute(height=64)
        quantized = np.rint(tile.astype(np.float64)*65535).astype(np.float32)/65535
        alpha = quantized[:, :, 3].mean()
        rgb = (quantized[:, :, :3]*quantized[:, :, 3, None]).sum((0, 1))/(alpha*4)
        expected = np.concatenate((rgb, [alpha])).astype(np.float32)
        actual = self.reference(result)[0]
        np.testing.assert_allclose(actual, np.broadcast_to(expected, actual.shape), rtol=0, atol=2e-7)
        self.assertEqual(actual.shape, (64, 64, 4)); self.assert_clean()

    def test_verified_cache_hit_starts_no_graph_probe_encoder_or_provider(self):
        self.visual(); first = self.execute(mode='frame')
        before = project_file(self.root).read_bytes()
        request = preview.plan(self.p, self.s, start_frame=0, end_frame=1, mode='frame', height=64)
        with patch.object(preview, 'build_filter_graph', side_effect=AssertionError('legacy visual graph')), \
             patch.object(preview, 'run_process', side_effect=AssertionError('new process')), \
             patch.object(preview, 'probe_media', side_effect=AssertionError('new probe')), \
             patch.object(FloatRenderContext, '__enter__', side_effect=AssertionError('new provider')):
            second = preview.preview_project(self.root, self.p, self.s, request=request)
        self.assertTrue(second['cache_hit']); self.assertEqual(first['cache_key'], second['cache_key'])
        self.assertEqual(project_file(self.root).read_bytes(), before); self.assert_clean()

    def test_equal_size_restored_mtime_numerical_runtime_change_invalidates_cache(self):
        self.visual(); first = self.execute(mode='frame')
        stamp = self.numpy_runtime.stat()
        self.numpy_runtime.write_bytes(b'numpy runtime B')
        os.utime(self.numpy_runtime, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        second = self.execute(mode='frame')
        self.assertFalse(second['cache_hit']); self.assertNotEqual(first['cache_key'], second['cache_key'])
        self.assertEqual(self.numpy_runtime.stat().st_size, stamp.st_size)
        self.assertEqual(self.numpy_runtime.stat().st_mtime_ns, stamp.st_mtime_ns)

    def test_corrupt_reference_rejects_until_explicit_prune_without_overwrite(self):
        self.visual(); first = self.execute()
        master = Path(first['master']); master.write_bytes(b'changed reference')
        with self.assertRaises(AppError) as caught: self.execute()
        self.assertEqual(caught.exception.code, 'PREVIEW_CACHE_CORRUPT')
        self.assertEqual(master.read_bytes(), b'changed reference')
        preview.cache_prune(self.root)
        self.assertFalse(self.execute()['cache_hit']); self.assert_clean()

    def test_dry_run_keeps_entire_project_tree_and_never_opens_provider(self):
        self.visual(); save_project(self.root, self.p)
        def tree():
            return {p.relative_to(self.root).as_posix(): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
                    for p in self.root.rglob('*') if p.is_file()}
        before = tree(); request = preview.plan(self.p, self.s, start_frame=0, end_frame=1, mode='frame', height=64)
        with patch.object(FloatRenderContext, '__enter__', side_effect=AssertionError('provider opened')):
            result = preview.preview_project(self.root, self.p, self.s, request=request, dry_run=True)
        self.assertEqual(result['status'], 'planned'); self.assertEqual(tree(), before)
        self.assertFalse(preview.cache_root(self.root).exists())
        request['reference_pixel_format'] = 'bgra'
        with self.assertRaises(AppError) as caught:
            preview.preview_project(self.root, self.p, self.s, request=request, dry_run=True)
        self.assertEqual(caught.exception.code, 'PREVIEW_ARGUMENT_INVALID'); self.assertEqual(tree(), before)

    def test_unported_operator_rejects_without_legacy_fallback_and_cleans_sources(self):
        self.visual(); self.s['tracks'][0]['clips'][0]['effects'] = [{'type': 'hqdn3d', 'parameters': {'amount': 1}}]
        with patch.object(preview, 'build_filter_graph', side_effect=AssertionError('legacy fallback')):
            with self.assertRaises(AppError) as caught: self.execute()
        self.assertEqual(caught.exception.code, 'FLOAT_TIMELINE_UNSUPPORTED')
        self.assertEqual(preview.cache_list(self.root)['entries'], []); self.assert_clean()

    def test_actual_mid_frame_cancellation_keeps_no_cache_or_export_and_closes_threads(self):
        self.s['duration_tick'] = 18000
        self.visual(np.broadcast_to(np.array([.2, .4, .6, 1], np.float32), (2, 16, 32, 4)).copy())
        marker = self.base/'cancel'; original = FloatTimeline.render_frame
        def then_cancel(timeline, index):
            result = original(timeline, index); marker.write_bytes(b'cancel after real native frame'); return result
        target = self.root/'previews/cancelled'
        with patch.object(FloatTimeline, 'render_frame', then_cancel):
            with self.assertRaises(AppError) as caught: self.execute(0, 2, output=target, cancel_file=marker)
        self.assertEqual(caught.exception.code, 'CANCELLED'); self.assertFalse(target.exists())
        self.assertEqual(preview.cache_list(self.root)['entries'], []); self.assert_clean()

    def test_actual_failed_encoder_preserves_no_partial_cache_or_export(self):
        self.visual(); original = float_preview.FloatPreviewContext.command
        def invalid(context, inputs, graph, temporary):
            _, name = original(context, inputs, graph, temporary)
            return [ffmpeg_path(), '-nostdin', '-v', 'error', '-avk-invalid-option'], name
        with patch.object(float_preview.FloatPreviewContext, 'command', invalid):
            with self.assertRaises(AppError) as caught: self.execute(output=self.root/'previews/failed')
        self.assertEqual(caught.exception.code, 'FLOAT_STREAM_ENCODE')
        self.assertEqual(preview.cache_list(self.root)['entries'], []); self.assert_clean()

    def test_existing_export_is_preserved_before_any_float_provider_starts(self):
        self.visual(); target = self.root/'previews/existing'; target.mkdir(parents=True)
        sentinel = target/'keep'; sentinel.write_bytes(b'previous export')
        with patch.object(FloatRenderContext, '__enter__', side_effect=AssertionError('provider opened')):
            with self.assertRaises(AppError) as caught: self.execute(output=target)
        self.assertEqual(caught.exception.code, 'PREVIEW_OUTPUT_EXISTS')
        self.assertEqual(sentinel.read_bytes(), b'previous export')

    def test_exported_float_reference_survives_explicit_cache_pruning(self):
        self.visual(); target = self.root/'previews/owned-export'; result = self.execute(output=target)
        before = Path(result['master']).read_bytes(); preview.cache_prune(self.root)
        self.assertEqual(preview.cache_list(self.root)['entries'], [])
        self.assertEqual(Path(result['master']).read_bytes(), before)
        self.assertEqual(self.reference(result).shape, (1, 16, 32, 4)); self.assert_clean()

    def test_png_uses_declared_transfer_while_mp4_composites_over_linear_black(self):
        self.transparent(); self.visual(np.broadcast_to(np.array([.2, .2, .2, .25], np.float32), (16, 32, 4)).copy())
        self.p['settings']['pixel_pipeline']['output_signal']['transfer'] = 'srgb'
        self.p['settings']['color']['transfer'] = 'iec61966-2-1'
        frame = self.execute(mode='frame')
        linear = np.rint(.2*65535)/65535
        expected = np.rint((1.055*linear**(1/2.4)-.055)*65535)
        self.assertLessEqual(abs(int(self.png(frame)[8, 16, 0])-expected), 1)
        result = self.execute()
        value = self.reference(result)[0, 8, 16]
        self.assertAlmostEqual(float(value[0]), linear, places=6)
        luma = self.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', result['path'], '-map', '0:v:0',
            '-an', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', 'pipe:1'])[:32*16]
        black = linear*(np.rint(.25*65535)/65535)
        encoded = 4.5*black if black < .018 else 1.099*black**.45-.099
        self.assertLessEqual(abs(int(luma[8*32+16])-(16+219*encoded)), 2)

    def test_selected_sequence_canvas_does_not_rewrite_global_author_canvas(self):
        self.visual(np.broadcast_to(np.array([.2, .4, .6, 1], np.float32), (32, 64, 4)).copy())
        self.p['settings']['canvas'].update(width=128, height=64)
        self.s['canvas'] = {'width': 64, 'height': 32}
        save_project(self.root, self.p); before = copy.deepcopy(self.p)
        request = preview.plan(self.p, self.s, start_frame=0, end_frame=1, height=64)
        with project_write_lock(self.root):
            result = preview.preview_project(self.root, self.p, self.s, request=request)
        self.assertEqual(self.reference(result).shape, (1, 32, 64, 4))
        self.assertEqual(self.p, before); self.assertTrue(result['pixel_pipeline']['providers_closed_before_publish'])

    def test_space_admission_accounts_for_float_reference_instead_of_bgra8(self):
        self.p['settings']['canvas'].update(width=256, height=256); self.s['duration_tick'] = 90000
        legacy = copy.deepcopy(self.p); legacy['settings'].pop('pixel_pipeline')
        value = preview.plan(legacy, self.s, start_frame=0, end_frame=10, height=256, budget_mib=8)
        self.assertLessEqual(value['estimated_working_bytes'], 8*1024**2)
        with self.assertRaises(AppError) as caught:
            preview.plan(self.p, self.s, start_frame=0, end_frame=10, height=256, budget_mib=8)
        self.assertEqual(caught.exception.code, 'PREVIEW_BUDGET')


if __name__ == '__main__':
    unittest.main()
