"""Publication/recovery contracts; artificial bytes do not measure model quality."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor.job_workspaces import Workspace, managed_workspace, recover_workspaces
from ai_ad_editor.project import create_project, load_project, project_transaction, save_project
from ai_ad_editor.rights import add_record, load_ledger, save_ledger
from ai_ad_editor.utils import atomic_write_json, sha256_file


class SemanticJobTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root, _ = create_project(Path(self.temporary.name) / '中文 空格 工程')

    def prepare(self, kind='semantic-index'):
        job = Workspace(self.root, kind)
        self.addCleanup(job.lease.close)
        stage = job.path / 'ready'; (stage / 'frames').mkdir(parents=True)
        (stage / 'index.json').write_bytes(b'index fixture')
        (stage / 'vectors.f32').write_bytes(b'vector fixture')
        (stage / 'frames/000.png').write_bytes(b'preview fixture')
        prefix = 'assets/semantic-calibration' if kind == 'semantic-calibrate' else 'assets/semantic'
        destination = self.root / prefix / ('a' * 24)
        return job, stage, destination

    def published(self, kind='semantic-index'):
        job, stage, destination = self.prepare(kind)
        job.publish_tree(stage, destination)
        return job, destination

    def recovered(self, job, **options):
        job.lease.close()
        return recover_workspaces(self.root, **options)['jobs'][0]

    def reference(self, destination):
        project = load_project(self.root)[1]
        path = destination / 'index.json'
        project['assets'].append(dict(id='semantic_example', kind='generated',
            uri=path.relative_to(self.root).as_posix(), sha256='sha256:' + sha256_file(path),
            rights_ref='semantic_example', source={}, probe={}))
        save_project(self.root, project)

    def test_live_owner_prevents_cleanup_of_the_whole_tree(self):
        job, destination = self.published()
        report = recover_workspaces(self.root, dry_run=True)['jobs'][0]
        self.assertEqual(report['status'], 'active_or_locked_preserved')
        self.assertTrue((destination / 'vectors.f32').is_file())

    def test_dry_run_plans_without_changing_any_evidence(self):
        job, destination = self.published(); job.lease.close()
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        report = recover_workspaces(self.root, dry_run=True)['jobs'][0]
        self.assertEqual(report['trees'][0]['status'], 'owned_unreferenced')
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_explicit_recovery_removes_only_the_owned_unreferenced_tree(self):
        source = self.root / 'assets/user.png'; source.write_bytes(b'original user source')
        legacy = self.root / 'cache/semantic-jobs/legacy'; legacy.mkdir(parents=True)
        (legacy / 'old.txt').write_bytes(b'preserve old diagnostic bytes')
        job, destination = self.published()
        report = self.recovered(job)
        self.assertEqual(report['status'], 'cleaned')
        self.assertFalse(destination.exists()); self.assertFalse(job.path.exists())
        self.assertEqual(source.read_bytes(), b'original user source')
        self.assertTrue((legacy / 'old.txt').is_file())

    def test_any_registered_asset_preserves_the_complete_semantic_tree(self):
        job, destination = self.published(); self.reference(destination)
        self.assertEqual(self.recovered(job)['trees'][0]['status'], 'referenced_preserved')
        self.assertTrue((destination / 'frames/000.png').is_file())

    def test_rights_evidence_alone_preserves_the_tree(self):
        job, destination = self.published()
        ledger = load_ledger(self.root)
        add_record(ledger, dict(asset_id='model_evidence', kind='semantic-model-adapter',
            evidence=str(destination / 'index.json'), verification_status='unverified',
            takedown_status='clear', sha256='sha256:' + sha256_file(destination / 'index.json')))
        save_ledger(self.root, ledger)
        self.assertEqual(self.recovered(job)['trees'][0]['status'], 'referenced_preserved')

    def test_modified_file_preserves_tree_and_job(self):
        job, destination = self.published()
        (destination / 'vectors.f32').write_bytes(b'user edit')
        self.assertEqual(self.recovered(job)['status'], 'changed_output_preserved')
        self.assertTrue(job.path.exists()); self.assertTrue((destination / 'index.json').exists())

    def test_same_bytes_replaced_file_is_preserved(self):
        job, destination = self.published()
        target = destination / 'index.json'; replacement = destination / 'replacement'
        replacement.write_bytes(target.read_bytes()); os.replace(replacement, target)
        self.assertEqual(self.recovered(job)['status'], 'changed_output_preserved')

    def test_same_bytes_replaced_root_is_preserved(self):
        job, destination = self.published()
        original = destination.with_name('saved-original'); destination.rename(original)
        import shutil
        shutil.copytree(original, destination)
        self.assertEqual(self.recovered(job)['status'], 'changed_output_preserved')

    def test_added_file_preserves_all_outputs(self):
        job, destination = self.published(); (destination / 'user.txt').write_bytes(b'new')
        self.assertEqual(self.recovered(job)['status'], 'changed_output_preserved')
        self.assertTrue((destination / 'index.json').exists())

    def test_added_empty_directory_is_preserved(self):
        job, destination = self.published(); (destination / 'user-directory').mkdir()
        self.assertEqual(self.recovered(job)['status'], 'changed_output_preserved')

    def test_interrupted_cleanup_can_reclaim_remaining_original_entries(self):
        job, destination = self.published(); (destination / 'index.json').unlink()
        self.assertEqual(self.recovered(job)['status'], 'cleaned')
        self.assertFalse(destination.exists())

    def test_prepublication_crash_workspace_is_reclaimed(self):
        job, stage, destination = self.prepare()
        self.assertEqual(self.recovered(job)['status'], 'cleaned')
        self.assertFalse(stage.exists()); self.assertFalse(destination.exists())

    def test_write_ahead_intent_precedes_atomic_directory_publication(self):
        job, stage, destination = self.prepare()
        rename = os.rename
        def observe(source, target):
            record = json.loads((job.path / 'job.json').read_bytes())
            self.assertEqual(len(record['trees'][0]['files']), 3)
            self.assertTrue(stage.is_dir()); self.assertFalse(destination.exists())
            rename(source, target)
        with patch('ai_ad_editor.job_trees.os.rename', side_effect=observe):
            job.publish_tree(stage, destination)

    def test_rename_failure_preserves_evidence_without_publishing(self):
        job, stage, destination = self.prepare()
        with patch('ai_ad_editor.job_trees.os.rename', side_effect=OSError('injected rename failure')):
            with self.assertRaises(OSError): job.publish_tree(stage, destination)
        self.assertFalse(destination.exists()); self.assertTrue(stage.exists())
        self.assertEqual(self.recovered(job)['status'], 'cleaned')

    def test_existing_destination_is_never_overwritten(self):
        job, stage, destination = self.prepare(); destination.mkdir(parents=True)
        (destination / 'user.txt').write_bytes(b'original')
        with self.assertRaises(FileExistsError): job.publish_tree(stage, destination)
        self.assertEqual((destination / 'user.txt').read_bytes(), b'original')

    def test_tree_namespaces_are_restricted_by_task_kind(self):
        for kind in ('four-stem-separation', 'subtitle-dubbing', 'semantic-search', 'semantic-register'):
            with self.subTest(kind=kind):
                job, stage, destination = self.prepare(kind)
                with self.assertRaises(ValueError): job.publish_tree(stage, destination)
                self.assertFalse(destination.exists()); job.lease.close()

    def test_calibration_uses_its_separate_owned_namespace(self):
        job, destination = self.published('semantic-calibrate')
        self.assertIn('/semantic-calibration/', destination.as_posix())
        self.assertEqual(self.recovered(job)['status'], 'cleaned')

    def test_outside_stage_and_outside_publication_root_are_rejected(self):
        job, stage, destination = self.prepare()
        with self.assertRaises(ValueError): job.publish_tree(self.root / 'assets', destination)
        with self.assertRaises(ValueError): job.publish_tree(stage, self.root / 'assets/derived' / ('a' * 24))
        self.assertTrue(stage.exists())

    def test_normal_failure_rolls_back_metadata_and_reclaims_only_its_publication(self):
        original = (self.root / 'project.json').read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'injected rollback'):
            with project_transaction(self.root, command='semantic.index'):
                with managed_workspace(self.root, 'semantic-index') as job:
                    job.hold_for_review('test evidence retained')
                    stage = job.path / 'ready'; stage.mkdir()
                    (stage / 'index.json').write_bytes(b'diagnostic index')
                    destination = self.root / 'assets/semantic' / ('b' * 24)
                    job.publish_tree(stage, destination)
                    (self.root / 'project.json').write_bytes(b'incomplete metadata')
                    raise RuntimeError('injected rollback')
        self.assertEqual((self.root / 'project.json').read_bytes(), original)
        self.assertFalse(destination.exists()); self.assertTrue(job.path.is_dir())
        self.assertEqual(self.recovered(job)['status'], 'cleaned')

    def test_committed_metadata_keeps_tree_on_explicit_diagnostic_cleanup(self):
        with project_transaction(self.root, command='semantic.index'):
            with managed_workspace(self.root, 'semantic-index') as job:
                job.hold_for_review('test successful execution evidence')
                stage = job.path / 'ready'; stage.mkdir()
                (stage / 'index.json').write_bytes(b'committed index')
                destination = self.root / 'assets/semantic' / ('c' * 24)
                job.publish_tree(stage, destination); self.reference(destination)
        self.assertTrue(job.path.exists()); self.assertTrue(destination.is_dir())
        self.assertEqual(self.recovered(job)['trees'][0]['status'], 'referenced_preserved')
        self.assertTrue((destination / 'index.json').is_file())

    def test_tampered_intent_is_preserved(self):
        job, destination = self.published(); job.lease.close()
        value = json.loads((job.path / 'job.json').read_bytes())
        value['trees'][0]['path'] = 'assets/derived/' + 'a' * 24
        atomic_write_json(job.path / 'job.json', value)
        self.assertEqual(recover_workspaces(self.root)['jobs'][0]['status'], 'unverified_or_blocked_preserved')
        self.assertTrue(destination.is_dir())

    def test_tree_output_budget_is_enforced_before_publication(self):
        job, stage, destination = self.prepare()
        with patch('ai_ad_editor.job_trees.MAX_FILES', 2), self.assertRaises(ValueError):
            job.publish_tree(stage, destination)
        self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
