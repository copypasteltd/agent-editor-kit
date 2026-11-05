from __future__ import annotations

import contextlib
import copy
from fractions import Fraction
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor import mask_edit
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import ledger_file, project_write_lock
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json


def invoke(*args):
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        code = main(list(map(str, args)))
    return code, json.loads(capture.getvalue())


class MaskEditCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mask-edit-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base/'project'
        self.raw = bytearray()
        for f in range(4):
            for y in range(48):
                for x in range(64):
                    alpha = 255 if 8+f <= x < 16+f and 8 <= y < 32 else [20, 64, 100, 180][f]
                    self.raw.extend((19, 101, 207, alpha))
        self.input = self.base/'input.mov'
        self.encode(self.input, self.raw, '8')
        self.assertEqual(invoke('project', 'init', self.root)[0], 0)
        code, result = invoke('media', 'ingest', '--project', self.root, '--input', self.input, '--asset-id', 'mask')
        self.assertEqual(code, 0, result)
        self.asset = result['data']['asset']
        self.edits_path = self.base/'edits.json'
        self.value = self.document()
        atomic_write_json(self.edits_path, self.value)

    def encode(self, path, raw, rate):
        argv = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'rawvideo', '-pixel_format', 'rgba',
                '-video_size', '64x48', '-framerate', rate, '-i', 'pipe:0', '-an']
        argv += ['-frames:v', '1', '-c:v', 'png', '-pix_fmt', 'rgba'] if path.suffix == '.png' else [
                '-c:v', 'qtrle', '-pix_fmt', 'argb', '-video_track_timescale', str(Fraction(rate).numerator)]
        result = subprocess.run([*argv, str(path)], input=raw, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def decode(self, path):
        result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-an', '-pix_fmt', 'rgba',
            '-fps_mode', 'passthrough', '-f', 'rawvideo', 'pipe:1'], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def document(self, asset=None, fps='8', frames=4, channel='alpha'):
        asset = asset or self.asset
        return {'version': '1.0.0', 'coordinate_space': 'normalized-output', 'scene_cut_frames': [],
            'mask': {'asset_id': asset['id'], 'sha256': asset['sha256'], 'channel': channel,
                     'width': 64, 'height': 48, 'frames': frames, 'fps': fps},
            'operations': [{'id': 'missing-part', 'mode': 'add', 'type': 'rectangle', 'start_frame': 1, 'end_frame': 3,
                'interpolation': 'linear', 'keyframes': [{'frame': 1, 'box': [.5, .25, .75, .75]},
                                                      {'frame': 2, 'box': [.625, .25, .875, .75]}]}]}

    def edit(self, *flags, derived='fixed', asset='mask', path=None):
        return invoke('media', 'mask-edit', '--project', self.root, '--asset-id', asset,
                      '--derived-asset-id', derived, '--edits', path or self.edits_path, *flags)

    def metadata(self):
        return [(self.root/n).read_bytes() for n in ('project.json', 'rights-ledger.json')]

    def test_encoded_rgba_matches_independent_authored_pixel_rectangles(self):
        original = self.metadata()
        code, result = self.edit()
        self.assertEqual(code, 0, result)
        item = result['data']; actual = self.decode(self.root/item['asset']['uri'])
        expected = bytearray()
        for f in range(4):
            for y in range(48):
                for x in range(64):
                    alpha = self.raw[(f*48*64+y*64+x)*4+3]
                    if f in (1, 2) and 12 <= y < 36 and (32 if f == 1 else 40) <= x < (48 if f == 1 else 56):
                        alpha = 255
                    expected.extend((255, 255, 255, alpha))
        self.assertEqual(actual, expected)
        self.assertNotEqual(original, self.metadata())
        self.assertTrue(item['mask_edit']['rgba_roundtrip_verified'])
        self.assertTrue(item['mask_edit']['every_pts_exact'])
        self.assertEqual([f['changed_pixels'] for f in item['mask_edit']['frames']], [0, 384, 384, 0])
        self.assertEqual(item['rights']['derived_from'], ['mask'])
        self.assertFalse(item['mask_edit']['semantic_quality_accepted'])
        self.assertEqual(item['asset']['source']['mask_edit']['plan']['mask']['sha256'], self.asset['sha256'])
        self.assertEqual(invoke('validate', '--project', self.root)[0], 0)
        code, audited = invoke('policy', 'audit', '--project', self.root)
        self.assertEqual(code, 0, audited)

    def test_fractional_rate_exact_duration_does_not_invent_terminal_frame(self):
        source = self.base/'fractional.mov'; self.encode(source, self.raw, '30000/1001')
        code, result = invoke('media', 'ingest', '--project', self.root, '--input', source, '--asset-id', 'fractional')
        self.assertEqual(code, 0, result)
        value = self.document(result['data']['asset'], fps='30000/1001')
        atomic_write_json(self.edits_path, value)
        code, result = self.edit(asset='fractional')
        self.assertEqual(code, 0, result)
        self.assertEqual(len(self.decode(self.root/result['data']['asset']['uri'])), len(self.raw))
        self.assertTrue(result['data']['mask_edit']['every_pts_exact'])
        code, review = invoke('quality', 'mask', '--project', self.root, '--asset-id', 'fixed')
        self.assertEqual(code, 0, review)
        self.assertEqual(len(review['data']['frames']), 4)

    def test_image_alpha_and_opaque_luma_have_correct_channel_binding(self):
        image = self.base/'image.png'; self.encode(image, self.raw[:64*48*4], '1')
        code, result = invoke('media', 'ingest', '--project', self.root, '--input', image, '--asset-id', 'image')
        self.assertEqual(code, 0, result)
        asset = result['data']['asset']
        for channel in ('alpha', 'luma'):
            value = self.document(asset, fps='1', frames=1, channel=channel)
            value['operations'][0].update(start_frame=0, end_frame=1, keyframes=[{'frame': 0, 'box': [.5, .25, .75, .75]}])
            atomic_write_json(self.edits_path, value)
            code, edited = self.edit('--channel', channel, asset='image', derived=channel)
            self.assertEqual(code, 0, edited)
            path = self.root/edited['data']['asset']['uri']
            self.assertEqual(path.suffix, '.png')
            decoded = self.decode(path)
            self.assertEqual(decoded[(20*64+40)*4+3], 255)
            if channel == 'alpha':
                self.assertEqual(decoded[3], 20)
            else:
                reference = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(image), '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1'], capture_output=True)
                self.assertEqual(decoded[3], reference.stdout[0])

    def test_dry_run_is_metadata_and_artifact_free(self):
        before = self.metadata(); files = set(self.root.rglob('*'))
        with patch('ai_ad_editor.mask_edit.execute') as executor:
            code, result = self.edit('--dry-run')
        self.assertEqual(code, 0, result); executor.assert_not_called()
        self.assertEqual(result['status'], 'planned')
        self.assertEqual(self.metadata(), before)
        self.assertEqual(set(self.root.rglob('*')), files)

    def test_bound_plan_rejects_wrong_source_grid_channel_and_unknown_fields(self):
        for field, value in [('sha256', 'sha256:'+'9'*64), ('frames', 3), ('width', True), ('channel', 'luma'), ('asset_id', 'wrong')]:
            bad = copy.deepcopy(self.value); bad['mask'][field] = value
            atomic_write_json(self.edits_path, bad)
            with self.subTest(field=field), patch('ai_ad_editor.mask_edit.execute') as executor:
                code, result = self.edit()
                self.assertEqual(code, 2, result); executor.assert_not_called()
        bad = copy.deepcopy(self.value); bad['online_provider'] = 'invalid'
        atomic_write_json(self.edits_path, bad)
        self.assertEqual(self.edit()[0], 2)

    def test_duplicate_json_keys_and_remote_inputs_are_rejected(self):
        self.edits_path.write_text('{"version":"1.0.0","version":"1.0.0"}', encoding='utf-8')
        self.assertEqual(self.edit()[0], 2)
        for value in ('https://example.invalid/edits.json', '\\\\server\\share\\edits.json'):
            with self.subTest(path=value):
                self.assertNotEqual(self.edit(path=value)[0], 0)

    def test_work_budget_rejects_before_decode(self):
        value = copy.deepcopy(self.value)
        value['operations'] = [{**copy.deepcopy(value['operations'][0]), 'id': f'op{i}', 'start_frame': 0, 'end_frame': 4,
            'keyframes': [{'frame': 0, 'box': [0., 0., 1., 1.]}]} for i in range(64)]
        value['samples_per_axis'] = 4
        atomic_write_json(self.edits_path, value)
        with patch('ai_ad_editor.mask_edit.execute') as executor:
            code, result = self.edit('--work-budget-million', '1')
        self.assertEqual(code, 2, result); executor.assert_not_called()
        self.assertEqual(result['errors'][0]['code'], 'MASK_EDIT_BUDGET_EXCEEDED')

    def test_native_rational_overflow_rejects_before_decode(self):
        with patch('ai_ad_editor.mask_edit.execute') as executor:
            code, result = self.edit('--fps', '2147483648/2147483647')
        self.assertEqual(code, 2, result); executor.assert_not_called()
        self.assertIn('32', result['errors'][0]['message'])

    def test_reused_plan_with_unknown_engine_rejects(self):
        code, result = self.edit()
        self.assertEqual(code, 0, result)
        document = json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        next(a for a in document['assets'] if a['id'] == 'fixed')['source']['mask_edit']['engine'] = 'future-unsupported'
        atomic_write_json(self.root/'project.json', document)
        with patch('ai_ad_editor.mask_edit.execute') as executor:
            code, result = invoke('media', 'mask-edit', '--project', self.root, '--asset-id', 'mask',
                '--derived-asset-id', 'rebuilt', '--edits-from-asset', 'fixed')
        self.assertEqual(code, 2, result); executor.assert_not_called()

    def test_preexecution_cancel_and_short_timeout_leave_metadata_unchanged(self):
        before = self.metadata(); flag = self.base/'cancel.flag'; flag.write_text('cancel', encoding='utf-8')
        code, result = self.edit('--cancel-file', flag)
        self.assertEqual(code, 8, result)
        self.assertEqual(result['errors'][0]['code'], 'CANCELLED')
        self.assertEqual(self.metadata(), before)
        code, result = self.edit('--timeout-seconds', '0.00000001')
        self.assertNotEqual(code, 0, result)
        self.assertEqual(self.metadata(), before)
        self.assertFalse((self.root/'assets/derived/fixed.mov').exists())

    def test_input_tamper_between_preflight_and_read_lock_rejects(self):
        original = mask_edit.execute; before = self.metadata()
        def tamper(*args, **kwargs):
            with (self.root/self.asset['uri']).open('ab') as source:
                source.write(b'changed after plan')
            return original(*args, **kwargs)
        with patch('ai_ad_editor.mask_edit.execute', side_effect=tamper):
            code, result = self.edit()
        self.assertEqual(code, 6, result)
        self.assertEqual(result['errors'][0]['code'], 'MASK_EDIT_INPUT_CHANGED')
        self.assertEqual(self.metadata(), before)

    def test_native_encode_failure_rolls_back_and_cleans_temporary_files(self):
        original = mask_edit.run_process; calls = []; before = self.metadata()
        def fail(command, **kwargs):
            calls.append(command)
            return original(command, **kwargs) if len(calls) == 1 else subprocess.CompletedProcess(command, 1, '', 'forced native encode failure')
        with patch('ai_ad_editor.mask_edit.run_process', side_effect=fail):
            code, result = self.edit()
        self.assertEqual(code, 6, result)
        self.assertEqual(self.metadata(), before)
        self.assertFalse(list((self.root/'cache/mask-edit').iterdir()))
        self.assertFalse((self.root/'assets/derived/fixed.mov').exists())

    def test_metadata_failure_after_publication_removes_only_new_artifact(self):
        before = self.metadata()
        with patch('ai_ad_editor.cli.save_project', side_effect=OSError('forced metadata failure')):
            code, result = self.edit()
        self.assertEqual(code, 6, result)
        self.assertEqual(self.metadata(), before)
        self.assertFalse((self.root/'assets/derived/fixed.mov').exists())
        self.assertEqual(self.decode(self.root/self.asset['uri']), self.raw)

    def test_idempotent_replay_does_not_reencode_and_conflict_fails(self):
        code, result = self.edit('--idempotency-key', 'same')
        self.assertEqual(code, 0, result)
        path = self.root/result['data']['asset']['uri']; before = path.stat().st_mtime_ns
        with patch('ai_ad_editor.mask_edit.execute') as executor:
            code, replay = self.edit('--idempotency-key', 'same')
        self.assertEqual(code, 0, replay); executor.assert_not_called()
        self.assertEqual(path.stat().st_mtime_ns, before)
        self.assertEqual(self.edit('--idempotency-key', 'same', derived='different')[0], 2)

    def test_package_keeps_editable_plan_and_rebuilds_same_encoded_alpha(self):
        code, result = self.edit()
        self.assertEqual(code, 0, result)
        expected = self.decode(self.root/result['data']['asset']['uri'])
        package = self.base/'mask.aevpkg.zip'
        self.assertEqual(invoke('convert', 'export', '--project', self.root, '--output', package, '--target-format', 'package')[0], 0)
        imported = self.base/'imported'
        code, result = invoke('convert', 'import', '--input', package, '--output', imported)
        self.assertEqual(code, 0, result)
        code, result = invoke('media', 'mask-edit', '--project', imported, '--asset-id', 'mask',
            '--derived-asset-id', 'rebuilt', '--edits-from-asset', 'fixed')
        self.assertEqual(code, 0, result)
        self.assertEqual(self.decode(imported/result['data']['asset']['uri']), expected)
        self.assertEqual(result['data']['rights']['derived_from'], ['mask', 'fixed'])

    def test_write_lock_and_existing_output_cannot_be_overwritten(self):
        with project_write_lock(self.root):
            code, result = self.edit()
        self.assertEqual(code, 6, result)
        self.assertEqual(result['errors'][0]['code'], 'PROJECT_WRITE_LOCKED')
        path = self.root/'assets/derived/fixed.mov'; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'preexisting user file')
        self.assertEqual(self.edit()[0], 2)
        self.assertEqual(path.read_bytes(), b'preexisting user file')

    def test_native_host_cli_runs_without_numpy_pillow_or_torch(self):
        import jsonschema
        program = '''import builtins,sys
original=builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0] in {'numpy','PIL','torch'}: raise ImportError('optional modules deliberately unavailable')
    return original(name,*args,**kwargs)
builtins.__import__=guarded
sys.path.insert(0,sys.argv[1])
sys.path.insert(1,sys.argv[2])
from ai_ad_editor.cli import main
raise SystemExit(main(sys.argv[3:]))'''
        command = [sys.executable, '-I', '-B', '-X', 'utf8', '-c', program, str(Path(__file__).resolve().parents[1]/'src'),
            str(Path(jsonschema.__file__).resolve().parent.parent),
            'media', 'mask-edit', '--project', str(self.root), '--asset-id', 'mask', '--derived-asset-id', 'pure', '--edits', str(self.edits_path)]
        result = subprocess.run(command, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout.decode('utf-8')+result.stderr.decode('utf-8'))
        self.assertTrue(json.loads(result.stdout)['data']['mask_edit']['rgba_roundtrip_verified'])


if __name__ == '__main__':
    unittest.main()
