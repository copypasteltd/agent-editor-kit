"""Execute an isolated candidate project module against real disposable files."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/transaction-preflight-20261030-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    return {path.relative_to(root).as_posix(): sha(path)
            for path in root.rglob('*') if path.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and sys.dont_write_bytecode
    work = ROOT / ('local/agent-ffmpeg/recovery66-candidate-' + args.run)
    work.mkdir()
    proof = BASE / ('candidate-' + args.run)
    proof.mkdir(parents=True)
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    definitions = ROOT / 'docs/validation/recovery66_preflight_candidate.py'
    (proof / 'executed-candidate.py').write_bytes(definitions.read_bytes())
    source = ROOT / 'product/src/ai_ad_editor'
    pins = {path.relative_to(ROOT).as_posix(): sha(path) for path in source.glob('*.py')}
    assert len(pins) == 288
    original = (source / 'project.py').read_text(encoding='utf-8')
    tree = ast.parse(original)
    old = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name == 'recover_pending_transaction')
    candidate = definitions.read_text(encoding='utf-8')
    functions = [ast.get_source_segment(candidate, node) for node in ast.parse(candidate).body
                 if isinstance(node, ast.FunctionDef)]
    assert len(functions) == 4
    lines = original.splitlines(keepends=True)
    proposed = ''.join(lines[:old.lineno - 1]) + '\n\n'.join(functions) + '\n\n' + ''.join(lines[old.end_lineno:])
    candidate_path = work / 'project.py'
    candidate_path.write_text(proposed, encoding='utf-8', newline='\n')
    sys.path.insert(0, str(source.parent))
    from ai_ad_editor import VERSION
    from ai_ad_editor.errors import AppError
    assert VERSION == '0.1.65'
    module = types.ModuleType('ai_ad_editor.recovery66_candidate')
    module.__file__ = str(candidate_path)
    module.__package__ = 'ai_ad_editor'
    exec(compile(proposed, str(candidate_path), 'exec'), module.__dict__)

    class RecoveryCases(unittest.TestCase):
        def setUp(self):
            self.root, _ = module.create_project(work / self._testMethodName, name='Disposable recovery candidate')
            (self.root / 'assets/keep.wav').write_bytes(b'Synthetic media sentinel, not an audio example')
            self.media = sha(self.root / 'assets/keep.wav')
            self.baseline = {path.relative_to(self.root).as_posix(): sha(path)
                             for path in module._transaction_metadata_files(self.root)}
            with module.project_write_lock(self.root):
                self.journal = module.prepare_project_transaction(self.root, command='validation.recovery66')
            self.journal_path = module.transaction_journal_file(self.root)

        def interrupted(self):
            for row in self.journal['files']:
                (self.root / row['path']).write_bytes(b'interrupted disposable metadata')

        def save_journal(self):
            module.atomic_write_json(self.journal_path, self.journal)

        def rejected(self, code):
            before = snapshot(self.root)
            with module.project_write_lock(self.root), patch.object(module, '_atomic_write_bytes',
                    wraps=module._atomic_write_bytes) as writes:
                with self.assertRaises(AppError) as raised:
                    module.recover_pending_transaction(self.root)
                self.assertEqual(raised.exception.code, code)
                writes.assert_not_called()
            self.assertEqual(before, snapshot(self.root))
            self.assertTrue(self.journal_path.is_file())
            self.assertEqual(sha(self.root / 'assets/keep.wav'), self.media)

        def test_valid_snapshot_restores_all_metadata_and_preserves_media(self):
            self.interrupted()
            extra = self.root / 'operations/interrupted-new.json'
            extra.write_bytes(b'partial')
            with module.project_write_lock(self.root):
                result = module.recover_pending_transaction(self.root)
                second = module.recover_pending_transaction(self.root)
            self.assertTrue(result['recovered'])
            self.assertEqual(second['status'], 'clean')
            self.assertEqual(self.baseline, {p.relative_to(self.root).as_posix(): sha(p)
                for p in module._transaction_metadata_files(self.root)})
            self.assertFalse(extra.exists())
            self.assertEqual(sha(self.root / 'assets/keep.wav'), self.media)

        def test_same_size_corruption_is_rejected_before_any_restore(self):
            self.interrupted()
            backup = self.root / self.journal['files'][-1]['backup']
            data = backup.read_bytes()
            backup.write_bytes(bytes([data[0] ^ 1]) + data[1:])
            self.rejected('PROJECT_TRANSACTION_BACKUP_CHANGED')

        def test_size_mismatch_is_rejected_before_any_restore(self):
            self.interrupted()
            backup = self.root / self.journal['files'][-1]['backup']
            backup.write_bytes(backup.read_bytes() + b'!')
            self.rejected('PROJECT_TRANSACTION_BACKUP_CHANGED')

        def test_late_missing_backup_does_not_partially_restore(self):
            self.interrupted()
            (self.root / self.journal['files'][-1]['backup']).unlink()
            self.rejected('PROJECT_TRANSACTION_BACKUP_MISSING')

        def test_boolean_size_is_invalid(self):
            self.journal['files'][-1]['size'] = True
            self.save_journal()
            self.rejected('PROJECT_TRANSACTION_INVALID')

        def test_malformed_digest_is_invalid(self):
            self.journal['files'][-1]['sha256'] = 'not-a-sha256'
            self.save_journal()
            self.rejected('PROJECT_TRANSACTION_INVALID')

        def test_duplicate_destination_is_invalid(self):
            self.journal['files'][-1]['path'] = self.journal['files'][0]['path']
            self.save_journal()
            self.rejected('PROJECT_TRANSACTION_INVALID')

        def test_duplicate_backup_is_invalid(self):
            self.journal['files'][-1]['backup'] = self.journal['files'][0]['backup']
            self.save_journal()
            self.rejected('PROJECT_TRANSACTION_INVALID')

        def test_other_transaction_backup_is_rejected(self):
            other = self.root / 'operations/project-transaction-backups/txn_other/0000.bin'
            other.parent.mkdir()
            other.write_bytes((self.root / self.journal['files'][0]['backup']).read_bytes())
            self.journal['files'][0]['backup'] = other.relative_to(self.root).as_posix()
            self.save_journal()
            self.rejected('PROJECT_TRANSACTION_PATH_INVALID')

        def test_media_destination_is_rejected(self):
            self.journal['files'][-1]['path'] = 'assets/keep.wav'
            self.save_journal()
            self.rejected('PROJECT_TRANSACTION_PATH_INVALID')

        def test_journal_cannot_be_a_restore_destination(self):
            self.journal['files'][-1]['path'] = 'operations/project-transaction.json'
            self.save_journal()
            self.rejected('PROJECT_TRANSACTION_PATH_INVALID')

        def test_parent_alias_is_rejected(self):
            self.journal['files'][-1]['path'] = 'operations/../project.json'
            self.save_journal()
            self.rejected('PROJECT_TRANSACTION_PATH_INVALID')

        def test_unsafe_committed_identity_is_rejected(self):
            self.journal['transaction_id'] = '../other'
            self.journal['status'] = 'committed'
            self.save_journal()
            self.rejected('PROJECT_TRANSACTION_INVALID')

        def test_committed_cleanup_does_not_roll_back_user_metadata(self):
            self.journal['status'] = 'committed'
            self.save_journal()
            (self.root / 'project.json').write_bytes(b'committed metadata sentinel')
            result = module.recover_pending_transaction(self.root)
            self.assertEqual(result['status'], 'committed_cleaned')
            self.assertEqual((self.root / 'project.json').read_bytes(), b'committed metadata sentinel')
            self.assertFalse(self.journal_path.exists())
            self.assertEqual(sha(self.root / 'assets/keep.wav'), self.media)

        def test_interrupted_restore_retains_journal_and_can_retry(self):
            self.interrupted()
            native = module._atomic_write_bytes
            calls = []
            def fail_second(path, data):
                calls.append(path)
                if len(calls) == 2:
                    raise OSError('Injected restore failure in disposable project')
                return native(path, data)
            with module.project_write_lock(self.root), patch.object(module, '_atomic_write_bytes', side_effect=fail_second):
                with self.assertRaises(OSError):
                    module.recover_pending_transaction(self.root)
            self.assertTrue(self.journal_path.is_file())
            with module.project_write_lock(self.root):
                self.assertTrue(module.recover_pending_transaction(self.root)['recovered'])
            self.assertEqual(self.baseline, {p.relative_to(self.root).as_posix(): sha(p)
                for p in module._transaction_metadata_files(self.root)})
            self.assertEqual(sha(self.root / 'assets/keep.wav'), self.media)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryCases)
    assert suite.countTestCases() == 15
    with (proof / 'tests.stderr').open('w', encoding='utf-8', newline='\n') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    frozen = all(sha(ROOT / name) == pin for name, pin in pins.items())
    report = dict(status='passed' if result.wasSuccessful() and frozen and not result.skipped else 'failed',
        kind='isolated-unintegrated-recovery-candidate', source_cli=VERSION, tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        product_integrated=False, formal_activation=False, candidate_project_sha256=sha(candidate_path),
        candidate_definitions_sha256=sha(definitions), file_hashes=pins, frozen_equal=frozen,
        real_fsync_preserved=True, disposable_files_only=True, actual_neural_inference=False,
        limitations='Candidate module only. No installed CLI repair, full compatibility, concurrent hostile-writer guarantee, or multi-file atomicity acceptance.',
        full_product_goal_closed=False)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key:value for key,value in report.items() if key != 'file_hashes'}), flush=True)
    if report['status'] != 'passed':
        print((proof / 'tests.stderr').read_text(encoding='utf-8')[-7000:], flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
