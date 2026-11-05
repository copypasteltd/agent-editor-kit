from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.mask_review import analyze_frames, load_expectations, prepare, review
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.project import ledger_file
from ai_ad_editor.utils import atomic_write_json


def invoke(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out): code = main(list(map(str, args)))
    return code, json.loads(out.getvalue())


def plan(width, height, frames, *, events=None, cuts=(), threshold=127):
    return {'video': {'width': width, 'height': height, 'frames': frames, 'fps': '2/1'},
            'threshold': threshold, 'events': events or {}, 'expectations': {'sha256': 'fixture'} if events else None,
            'scene_cut_frames': cuts}


class MaskMeasurementTests(unittest.TestCase):
    def test_exact_threshold_half_open_bounds_and_no_semantic_claim(self):
        data = bytes([0, 127, 128, 0, 0, 0, 255, 0, 0, 0, 0, 0])
        result = analyze_frames(io.BytesIO(data), plan(4, 3, 1))
        row = result['frames'][0]
        self.assertEqual(row['selected_pixels'], 2)
        self.assertEqual(row['bbox_pixels'], [2, 0, 3, 2])
        self.assertEqual(row['bbox_normalized'], [.5, 0, .75, 2/3])
        self.assertFalse(result['expectations_checked'])
        self.assertFalse(result['semantic_quality_accepted'])

    def test_endpoint_coordinates_clipped_neighborhood_and_negative_assertions(self):
        points = [{'x': 1., 'y': 1., 'expected': 'selected', 'radius_pixels': 0, 'minimum_fraction': 1},
                  {'x': 0., 'y': 0., 'expected': 'clear', 'radius_pixels': 1, 'minimum_fraction': .75}]
        result = analyze_frames(io.BytesIO(bytes([255, 0, 0, 255])), plan(2, 2, 1, events={0: points}))
        self.assertFalse(result['ok'])
        self.assertTrue(result['frames'][0]['checks'][0]['passed'])
        self.assertEqual(result['failed_points'][0]['window_pixels'], [0, 0, 2, 2])
        self.assertEqual(result['failed_points'][0]['observed_fraction'], .5)

    def test_iou_area_presence_and_scene_cuts_are_review_only(self):
        raw = bytes([255, 0, 0, 0, 255, 255, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0])
        result = analyze_frames(io.BytesIO(raw), plan(4, 1, 4))
        self.assertTrue(result['ok'])
        self.assertEqual(result['frames'][1]['previous_frame_iou'], .25)
        self.assertIn('MASK_AREA_JUMP', result['frames'][1]['review_flags'])
        self.assertIn('MASK_PRESENCE_CHANGED', result['frames'][2]['review_flags'])
        self.assertIsNone(result['frames'][3]['previous_frame_iou'])
        cut = analyze_frames(io.BytesIO(raw), plan(4, 1, 4, cuts=[1]))
        self.assertIsNone(cut['frames'][1]['previous_frame_iou'])
        self.assertNotIn('MASK_AREA_JUMP', cut['frames'][1]['review_flags'])

    def test_empty_mask_is_measured_but_positive_check_fails(self):
        point = {'x': .5, 'y': .5, 'expected': 'selected', 'radius_pixels': 0, 'minimum_fraction': 1}
        result = analyze_frames(io.BytesIO(bytes(4)), plan(2, 2, 1, events={0: [point]}))
        self.assertFalse(result['ok'])
        self.assertIsNone(result['frames'][0]['bbox_pixels'])
        self.assertEqual(result['errors'][0]['code'], 'MASK_EXPECTATION_FAILED')

    def test_truncated_and_extra_raw_frames_fail(self):
        for raw in [bytes(3), bytes(5)]:
            with self.assertRaises(AppError): analyze_frames(io.BytesIO(raw), plan(2, 2, 1))


class MaskReviewCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mask-review-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base/'project'
        self.source = self.base/'mask.mov'
        frames = []
        for index in range(4):
            pixels = bytearray()
            for y in range(48):
                for x in range(64):
                    alpha = 255 if 8+index <= x < 24+index and 8 <= y < 40 else 0
                    pixels.extend((80, 120, 160, alpha))
            frames.append(bytes(pixels))
        self.raw = b''.join(frames)
        process = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', '64x48', '-r', '8',
                                  '-i', 'pipe:0', '-an', '-c:v', 'qtrle', '-pix_fmt', 'argb', str(self.source)], input=self.raw, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(invoke('project', 'init', self.root)[0], 0)
        code, data = invoke('media', 'ingest', '--project', self.root, '--input', self.source, '--asset-id', 'mask')
        self.assertEqual(code, 0, data)
        self.asset = data['data']['asset']
        self.expected = self.base/'expectations.json'
        self.write_expectations(1)

    def write_expectations(self, x):
        atomic_write_json(self.expected, {'version': '1.0.0', 'coordinate_space': 'normalized-output', 'frames': [
            {'frame': 0, 'points': [{'x': x, 'y': .5, 'expected': 'selected'}]},
            {'frame': 3, 'points': [{'x': 0., 'y': .5, 'expected': 'clear', 'radius_pixels': 1}]}]})

    def run_review(self, *extra):
        return invoke('quality', 'mask', '--project', self.root, '--asset-id', 'mask', *extra)

    def test_real_lossless_alpha_decode_extent_and_explicit_failure_report(self):
        code, result = self.run_review('--expectations', self.expected, '--report', 'validation/failed.json')
        self.assertEqual(code, 2, result)
        report = json.loads((self.root/'validation/failed.json').read_text(encoding='utf-8'))
        self.assertEqual([r['selected_pixels'] for r in report['frames']], [512]*4)
        self.assertEqual(report['frames'][3]['bbox_pixels'], [11, 8, 27, 40])
        self.assertEqual(report['failed_points'][0]['observed_fraction'], 0)
        self.assertEqual(report['plan']['video']['fps'], '8')
        self.assertFalse(report['semantic_quality_accepted'])

    def test_matching_expectations_pass_without_mutating_project_or_ledger(self):
        self.write_expectations(.2)
        metadata = [self.root/'project.json', ledger_file(self.root)]
        before = [p.read_bytes() for p in metadata]
        code, result = self.run_review('--expectations', self.expected)
        self.assertEqual(code, 0, result)
        self.assertTrue(result['data']['expectations_checked'])
        self.assertEqual(result['data']['checked_points'], 2)
        self.assertEqual(before, [p.read_bytes() for p in metadata])

    def test_dry_run_does_not_decode_or_create_report(self):
        before = set(self.root.rglob('*'))
        with patch('ai_ad_editor.cli.review_mask') as decoder:
            code, result = self.run_review('--dry-run')
        self.assertEqual(code, 0, result); decoder.assert_not_called()
        self.assertEqual(set(self.root.rglob('*')), before)

    def test_limits_paths_missing_assets_and_source_tamper_preflight(self):
        for flags in [('--threshold', '255'), ('--max-frames', '1'), ('--max-frames', '0'), ('--budget-mib', '0'), ('--fps', 'nan'),
                      ('--scene-cut-frame', '0'), ('--scene-cut-frame', '1', '--scene-cut-frame', '1'),
                      ('--report', 'project.json'), ('--report', 'validation/out.txt'), ('--report', 'https://example.invalid/report.json')]:
            with self.subTest(flags=flags), patch('ai_ad_editor.cli.review_mask') as decoder:
                code, result = self.run_review(*flags)
                self.assertNotEqual(code, 0, result); decoder.assert_not_called()
        code, result = invoke('quality', 'mask', '--project', self.root, '--asset-id', 'missing')
        self.assertNotEqual(code, 0, result)
        with (self.root/self.asset['uri']).open('ab') as handle: handle.write(b'changed')
        code, result = self.run_review()
        self.assertEqual(result['errors'][0]['code'], 'MASK_REVIEW_SOURCE_CHANGED')

    def test_bad_expectations_and_input_report_collision_are_rejected(self):
        bad = [True, float('inf'), 10**1000, -1]
        for value in bad:
            self.write_expectations(value)
            code, result = self.run_review('--expectations', self.expected)
            self.assertEqual(code, 2, result)
        self.write_expectations(.2)
        body = json.loads(self.expected.read_text(encoding='utf-8')); body['frames'][0]['points'][0]['radius_pixels'] = True
        atomic_write_json(self.expected, body)
        self.assertEqual(self.run_review('--expectations', self.expected)[0], 2)
        self.write_expectations(.2)
        inside = self.root/'validation/input.json'; inside.write_bytes(self.expected.read_bytes())
        self.assertEqual(self.run_review('--expectations', inside, '--report', 'validation/input.json')[0], 2)

    def test_decode_failure_and_during_execution_tamper_do_not_write_report(self):
        from ai_ad_editor import mask_review
        real = mask_review.run_process
        def tamper(args, **kwargs):
            result = real(args, **kwargs)
            with (self.root/self.asset['uri']).open('ab') as handle: handle.write(b'changed')
            return result
        with patch('ai_ad_editor.mask_review.run_process', side_effect=tamper):
            code, result = self.run_review('--report', 'validation/must-not-exist.json')
        self.assertEqual(code, 6, result)
        self.assertEqual(result['errors'][0]['code'], 'MASK_REVIEW_INPUT_CHANGED')
        self.assertFalse((self.root/'validation/must-not-exist.json').exists())
        self.assertFalse(list((self.root/'cache/mask-review').iterdir()))

    def test_image_luma_and_no_alpha_rejection(self):
        image = self.base/'gray.png'
        raw = bytes([255 if 8 <= x < 24 and 8 <= y < 40 else 0 for y in range(48) for x in range(64)])
        result = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', '64x48', '-i', 'pipe:0', '-frames:v', '1', str(image)], input=raw, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        code, result = invoke('media', 'ingest', '--project', self.root, '--input', image, '--asset-id', 'gray')
        self.assertEqual(code, 0, result)
        args = ['quality', 'mask', '--project', self.root, '--asset-id', 'gray']
        self.assertEqual(invoke(*args)[0], 2)
        code, result = invoke(*args, '--channel', 'luma')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['data']['frames'][0]['selected_pixels'], 512)
        self.assertEqual(result['data']['plan']['video']['frames'], 1)

    def test_storage_budget_rejects_before_decode(self):
        from ai_ad_editor.mask_review import probe_media
        probe = probe_media(self.root/self.asset['uri'])
        probe['streams'][0].update(width=4096, height=4096)
        with patch('ai_ad_editor.mask_review.probe_media', return_value=probe), patch('ai_ad_editor.cli.review_mask') as decoder:
            code, result = self.run_review('--budget-mib', '1', '--max-edge', '0')
        self.assertEqual(code, 2, result); decoder.assert_not_called()

    def test_explicit_cfr_sampling_and_channel_selection(self):
        code, result = self.run_review('--fps', '4', '--scene-cut-frame', '1')
        self.assertEqual(code, 0, result)
        self.assertEqual(len(result['data']['frames']), 2)
        self.assertEqual(result['data']['frames'][1]['seconds'], .25)
        self.assertIsNone(result['data']['frames'][1]['previous_frame_iou'])
        code, result = self.run_review('--channel', 'luma')
        self.assertEqual(code, 0, result)
        self.assertTrue(all(r['selected_pixels'] == 0 for r in result['data']['frames']))

    def test_ffmpeg_failure_cleans_temporary_output(self):
        with patch('ai_ad_editor.mask_review.run_process', return_value=subprocess.CompletedProcess(['ffmpeg'], 1, '', 'decode failed')):
            code, result = self.run_review('--report', 'validation/must-not-exist.json')
        self.assertEqual(code, 6, result)
        self.assertEqual(result['errors'][0]['code'], 'MASK_REVIEW_DECODE_FAILED')
        self.assertFalse((self.root/'validation/must-not-exist.json').exists())
        self.assertFalse(list((self.root/'cache/mask-review').iterdir()))

    def test_real_cli_mask_review_runs_when_numpy_import_is_blocked(self):
        program = '''import builtins,sys
original=builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0]=='numpy': raise ImportError('NumPy deliberately unavailable')
    return original(name,*args,**kwargs)
builtins.__import__=guarded
sys.path.insert(0,sys.argv[1])
from ai_ad_editor.cli import main
code=main(sys.argv[2:])
assert 'numpy' not in sys.modules
sys.exit(code)
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c', program, str(Path(__file__).resolve().parents[1]/'src'),
                                 'quality', 'mask', '--project', str(self.root), '--asset-id', 'mask'], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr+result.stdout)
        self.assertTrue(json.loads(result.stdout)['data']['ok'])


if __name__ == '__main__': unittest.main()
