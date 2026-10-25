"""Real file reads, native lock release and publication recovery under interruption."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor.artifact_locks import artifact_entry, verification_scope
from ai_ad_editor.execution_control import checkpoint, ExecutionInterrupted, operation_budget
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import create_project, load_project, save_project
from ai_ad_editor.semantic_contract import adapter_fingerprint, verify_adapter
from ai_ad_editor.semantic_jobs import current, managed
from ai_ad_editor.utils import sha256_file


class Clock:
    value = 100.

    def __call__(self):
        return self.value


class ExecutionControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / '模型 bytes.bin'
        self.path.write_bytes(b'unchanged real local bytes\0' * 100000)
        self.marker = self.root / '取消 marker'
        self.clock = Clock()
        self.digest_type = hashlib.sha256

    def controlled_digest(self, *, cancel=False):
        test = self

        class Digest:
            def __init__(self):
                self.digest = test.digest_type()

            def update(self, data):
                self.digest.update(data)
                test.clock.value += 2.
                if cancel:
                    test.marker.touch()

            def hexdigest(self):
                return self.digest.hexdigest()

        return Digest

    def test_unbudgeted_and_successful_budget_hash_all_actual_bytes(self):
        expected = self.digest_type(self.path.read_bytes()).hexdigest()
        self.assertEqual(sha256_file(self.path), expected)
        with operation_budget(30, root=self.root):
            self.assertEqual(sha256_file(self.path), expected)

    def test_timeout_during_unlocked_hash_preserves_input_and_has_no_result(self):
        original = self.path.read_bytes()
        with patch('ai_ad_editor.execution_control.time.monotonic', self.clock), \
                patch('ai_ad_editor.utils.hashlib.sha256', self.controlled_digest()):
            with self.assertRaises(ExecutionInterrupted) as error:
                with operation_budget(1, root=self.root):
                    sha256_file(self.path)
        self.assertEqual(error.exception.code, 'PROCESS_TIMEOUT')
        self.assertEqual(error.exception.diagnostics['phase'], 'integrity-read')
        self.assertGreater(error.exception.diagnostics['bytes_processed'], 0)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(sha256_file(self.path), self.digest_type(original).hexdigest())

    def test_relative_cancel_marker_is_observed_during_hash_and_scope_resets(self):
        with patch('ai_ad_editor.execution_control.time.monotonic', self.clock), \
                patch('ai_ad_editor.utils.hashlib.sha256', self.controlled_digest(cancel=True)):
            with self.assertRaises(ExecutionInterrupted) as error:
                with operation_budget(30, self.marker.name, root=self.root):
                    sha256_file(self.path)
        self.assertEqual(error.exception.code, 'CANCELLED')
        checkpoint(force=True)  # Expired/cancelled context must not leak.
        self.assertTrue(sha256_file(self.path))

    def test_native_partial_digest_is_not_cached_and_its_handle_is_closed(self):
        with verification_scope() as scope:
            with patch('ai_ad_editor.execution_control.time.monotonic', self.clock), \
                    patch('ai_ad_editor.artifact_locks.hashlib.sha256', self.controlled_digest()):
                with self.assertRaises(ExecutionInterrupted) as error:
                    with operation_budget(1, root=self.root):
                        artifact_entry(self.path, 'model')
            self.assertTrue(error.exception.diagnostics['partial_digest_discarded'])
            self.assertEqual(scope.summary()['files_hashed'], 0)
            self.assertEqual(scope.summary()['bytes_hashed'], 0)
            self.path.write_bytes(b'write possible after interrupted read')
            result = artifact_entry(self.path, 'model')
            self.assertEqual(result['sha256'], 'sha256:' + self.digest_type(self.path.read_bytes()).hexdigest())
            with self.assertRaises(PermissionError):
                self.path.unlink()

    def test_cached_locked_digest_still_obeys_deadline_without_releasing_outer_lock(self):
        with verification_scope() as scope:
            artifact_entry(self.path, 'model')
            with patch('ai_ad_editor.execution_control.time.monotonic', self.clock):
                with self.assertRaises(ExecutionInterrupted):
                    with operation_budget(1, root=self.root):
                        self.clock.value += 2
                        artifact_entry(self.path, 'model')
            self.assertEqual(scope.summary()['digest_reuses_while_locked'], 0)
            with self.assertRaises(PermissionError):
                self.path.write_bytes(b'forbidden')
        self.path.write_bytes(b'allowed')

    def test_nested_longer_budget_cannot_extend_outer_deadline(self):
        with patch('ai_ad_editor.execution_control.time.monotonic', self.clock):
            with operation_budget(1, root=self.root):
                with self.assertRaises(ExecutionInterrupted) as error:
                    with operation_budget(100, root=self.root):
                        self.clock.value += 2
                        checkpoint()
                self.assertEqual(error.exception.code, 'PROCESS_TIMEOUT')
        checkpoint()

    def test_existing_cancel_marker_refuses_before_read(self):
        self.marker.touch()
        with self.assertRaises(ExecutionInterrupted) as error:
            with operation_budget(30, self.marker, root=self.root):
                self.fail('cancelled work executed')
        self.assertEqual(error.exception.code, 'CANCELLED')

    def test_invalid_and_remote_controls_are_rejected(self):
        for value in (0, -1, True, float('nan'), float('inf'), 3601, '1'):
            with self.subTest(timeout=value), self.assertRaises(AppError):
                with operation_budget(value, root=self.root):
                    self.fail('invalid budget executed')
        with self.assertRaises(AppError):
            with operation_budget(1, 'https://example.com/cancel', root=self.root):
                self.fail('remote marker accepted')

    def test_adapter_verifier_preserves_interruption_code_during_artifact_verification(self):
        python = self.root / 'python.exe'; python.write_bytes(b'fixture')
        proof = self.root / 'evidence.txt'; proof.write_bytes(b'evidence')
        record = dict(engine='transformers-siglip-local-v1', protocol='agent-semantic-embedding-v1',
            dimension=768, preprocessing='siglip-local-rgb-lowercase-pad64-no-truncation-v1', threads=4,
            python_executable=str(python), model_path=str(self.root),
            runtime_artifacts=[dict(path=str(python), role='runtime')],
            artifacts=[dict(path=str(python), role='python'), dict(path=str(python), role='runtime'),
                dict(path=str(proof), role='evidence')])
        record['sha256'] = adapter_fingerprint(record)
        with patch('ai_ad_editor.semantic_contract.model_files', return_value=[]), \
                patch('ai_ad_editor.semantic_contract.implementation_files', return_value=[]), \
                patch('ai_ad_editor.semantic_contract.artifact_entry', side_effect=ExecutionInterrupted('CANCELLED', 'cancel', exit_code=8)):
            with self.assertRaises(ExecutionInterrupted) as error:
                verify_adapter(record)
        self.assertEqual(error.exception.code, 'CANCELLED')

    def test_expired_operation_still_recovers_uncommitted_published_tree(self):
        self.recovery_case(committed=False)

    def test_expired_operation_preserves_committed_tree_and_original_input(self):
        self.recovery_case(committed=True)

    def recovery_case(self, *, committed):
        root, project = create_project(self.root / '恢复 工程')
        destination = root / 'assets/semantic' / ('b' * 24)
        original = self.path.read_bytes()

        @managed('semantic-index')
        def operation(root, project, **options):
            job = current()
            stage = job.path / 'ready'; stage.mkdir()
            (stage / 'index.json').write_bytes(b'owned generated bytes')
            job.publish_tree(stage, destination)
            if committed:
                path = destination / 'index.json'
                project['assets'].append(dict(id='semantic_example', kind='generated',
                    uri=path.relative_to(root).as_posix(), sha256='sha256:' + sha256_file(path),
                    rights_ref='semantic_example', source={}, probe={}))
                save_project(root, project)
            self.clock.value += 2
            checkpoint()

        with patch('ai_ad_editor.execution_control.time.monotonic', self.clock):
            with self.assertRaises(ExecutionInterrupted):
                operation(root, project, timeout=1)
        self.assertEqual(destination.exists(), committed)
        self.assertEqual(bool(load_project(root)[1]['assets']), committed)
        self.assertEqual(self.path.read_bytes(), original)
        checkpoint(force=True)


if __name__ == '__main__':
    unittest.main()
