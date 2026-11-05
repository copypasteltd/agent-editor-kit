"""Real product recovery against disposable files, including the original defects."""
from pathlib import Path
import hashlib
import tempfile
import threading
import unittest
from unittest.mock import patch

from ai_ad_editor import project as module
from ai_ad_editor.errors import AppError
from ai_ad_editor.runtime import configure_local_runtime


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}


class IntegratedRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(temporary.cleanup)
        self.root, _ = module.create_project(Path(temporary.name) / '中文 工程', name='Integrated recovery')
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

    def test_parallel_backup_keeps_every_fsync_before_journal_publication(self):
        module.recover_pending_transaction(self.root)
        real_fsync, real_write = module.os.fsync, module.atomic_write_json
        completed = []
        guard = threading.Lock()
        def flush(fd):
            result = real_fsync(fd)
            if threading.current_thread().name.startswith('project-backup'):
                with guard:
                    completed.append(fd)
            return result
        observations = []
        def publish(path, payload):
            if path == self.journal_path:
                observations.append((len(completed), len(payload['files'])))
            return real_write(path, payload)
        with module.project_write_lock(self.root), patch.object(module.os, 'fsync', side_effect=flush), \
                patch.object(module, 'atomic_write_json', side_effect=publish):
            result = module.prepare_project_transaction(self.root, command='flush-order')
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0][0], observations[0][1])
        for row in result['files']:
            self.assertEqual(sha(self.root / row['backup']), row['sha256'])

    def test_backup_failure_never_publishes_prepared_journal(self):
        module.recover_pending_transaction(self.root)
        real_fsync = module.os.fsync
        def flush(fd):
            if threading.current_thread().name.startswith('project-backup'):
                raise OSError('Injected durable backup failure')
            return real_fsync(fd)
        with module.project_write_lock(self.root), patch.object(module.os, 'fsync', side_effect=flush):
            with self.assertRaises(OSError):
                module.prepare_project_transaction(self.root, command='failed-backup')
        self.assertFalse(self.journal_path.exists())
        self.assertEqual(self.baseline, {p.relative_to(self.root).as_posix(): sha(p)
            for p in module._transaction_metadata_files(self.root)})

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
