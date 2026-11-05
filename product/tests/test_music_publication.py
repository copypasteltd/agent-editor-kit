"""Real CLI/transaction/output boundaries with an explicitly mocked worker.

These cases establish failure envelopes and file preservation, never inference.
The actual native CUDA failure suite lives in docs/validation separately.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_music_generation import ENGINE
from ai_ad_editor.project import create_project

BASE = Path(__file__).resolve().parents[1] / '.runtime/test-music-publication'
HASH = 'sha256:' + 'a' * 64


class MusicPublicationTests(unittest.TestCase):
    def setUp(self):
        BASE.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=BASE)
        self.addCleanup(temporary.cleanup)
        self.project, _ = create_project(Path(temporary.name) / 'project')
        self.output = self.project / 'assets/derived/attempt.wav'
        self.request = Path(temporary.name) / 'request.json'
        self.request.write_text(json.dumps(dict(format='agent-neural-music-v1',
            prompt='Fixture only; no neural execution.', lyrics='', instrumental=True, duration_seconds=10)), encoding='utf-8')
        self.before = self.metadata()
        adapter = dict(adapter_id='fixture', engine=ENGINE, rights_ref='fixture', sha256=HASH)
        for name, replacement in [('load_model_registry', dict(adapters=[adapter])),
                                  ('verify_adapter', dict(ok=True)),
                                  ('active_records', [dict(asset_id='fixture', sha256=HASH)])]:
            mock = patch('ai_ad_editor.music_generation_cli.' + name, return_value=replacement)
            mock.start()
            self.addCleanup(mock.stop)

    def metadata(self):
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.project.glob('*.json')}

    def invoke(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(['music', 'generate', '--project', str(self.project), '--adapter-id', 'fixture',
                '--input', str(self.request), '--new-asset-id', 'attempt'])
        value = json.loads(stdout.getvalue())
        self.assertNotEqual(code, 0)
        self.assertFalse(value['ok'])
        self.assertEqual(value['status'], 'failed')
        self.assertNotIn('Traceback', stderr.getvalue())
        self.assertEqual(self.metadata(), self.before)
        self.assertFalse(any(row['id'] == 'attempt' for row in json.loads((self.project / 'project.json').read_bytes())['assets']))
        self.assertEqual(list((self.project / 'cache/managed-jobs').glob('job-*')), [])
        return value['errors'][0]

    def test_real_exclusive_publication_conflict_preserves_foreign_file_and_metadata(self):
        sentinel = b'foreign file created during the mocked worker'
        def completed(root, job, *args, **kwargs):
            staged = job.path / 'generated.wav'
            staged.write_bytes(b'explicit non-model fixture')
            self.output.parent.mkdir(parents=True, exist_ok=True)
            self.output.write_bytes(sentinel)
            return staged, {}
        with patch('ai_ad_editor.music_generation_pipeline.execute', side_effect=completed):
            error = self.invoke()
        self.assertEqual(error['code'], 'MUSIC_GENERATION_OUTPUT_CONFLICT')
        self.assertEqual(error['diagnostics']['cause'], 'FileExistsError')
        self.assertEqual(self.output.read_bytes(), sentinel)

    def test_native_file_permission_failure_is_a_structured_error(self):
        with patch('ai_ad_editor.music_generation_pipeline.execute', side_effect=PermissionError('fixture access denied')):
            error = self.invoke()
        self.assertEqual(error['code'], 'MUSIC_GENERATION_IO_FAILED')
        self.assertEqual(error['diagnostics']['cause'], 'PermissionError')
        self.assertFalse(self.output.exists())

    def test_existing_product_cancellation_retains_its_original_error_code(self):
        with patch('ai_ad_editor.music_generation_pipeline.execute', side_effect=AppError('CANCELLED', 'fixture cancellation', exit_code=8)):
            error = self.invoke()
        self.assertEqual(error['code'], 'CANCELLED')
        self.assertFalse(self.output.exists())

    def test_secondary_report_cleanup_error_does_not_mask_original_file_failure(self):
        original_unlink = Path.unlink
        def denied_report(path, *args, **kwargs):
            if path.parent == self.project / 'validation' and path.name.startswith('music_generation_'):
                raise PermissionError('secondary report cleanup fixture')
            return original_unlink(path, *args, **kwargs)
        with (patch('ai_ad_editor.music_generation_pipeline.execute', side_effect=FileExistsError('original fixture conflict')),
                patch.object(Path, 'unlink', denied_report)):
            error = self.invoke()
        self.assertEqual(error['code'], 'MUSIC_GENERATION_OUTPUT_CONFLICT')
        self.assertEqual(error['diagnostics']['cause'], 'FileExistsError')


if __name__ == '__main__':
    unittest.main()
