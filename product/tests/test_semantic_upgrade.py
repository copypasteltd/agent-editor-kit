"""Runtime relocation contracts use small real files, synthetic vectors, no model quality claims."""
import contextlib
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

import test_semantic_package as baseline
from ai_ad_editor import semantic, semantic_contract, semantic_upgrade as upgrade
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import asset_map, load_project, save_project
from ai_ad_editor.rights import add_record, load_ledger, save_ledger, record_for
from ai_ad_editor.semantic_contract import adapter_fingerprint


def invoke(*arguments):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(list(map(str, arguments)))
    return code, json.loads(output.getvalue())


class SemanticUpgradeTests(unittest.TestCase):
    fixture = baseline.SemanticPackageTests.fixture
    metadata = baseline.SemanticPackageTests.metadata

    def setUp(self):
        baseline.SemanticPackageTests.setUp(self)
        self.model = self.base/'model'; self.model.mkdir()
        model_file = self.model/'weights.data'; model_file.write_bytes(b'fixture model bytes')
        runtime = self.base/'runtime.dll'; runtime.write_bytes(b'fixture native bytes')
        python = self.base/'python.exe'; python.write_bytes(b'fixture native exe bytes')
        proof = self.base/'LICENSE.txt'; proof.write_bytes(b'fixture rights evidence')
        self.old_site, self.new_site = self.base/'old-site', self.base/'new-site'
        self.old_site.mkdir(); self.new_site.mkdir()
        for name in ('semantic_worker.py', 'semantic_contract.py'):
            (self.old_site/name).write_bytes(b'# identical implementation fixture\n')
            (self.new_site/name).write_bytes(b'# identical implementation fixture\n')
        current = sorted(self.new_site.glob('*.py'))
        for target, name, value in ((semantic_contract, 'model_files', [model_file]),
                                    (semantic_contract, 'implementation_files', current),
                                    (upgrade, 'implementation_files', current)):
            mocked = patch.object(target, name, return_value=value); mocked.start(); self.addCleanup(mocked.stop)
        self.adapter.update(model_path=str(self.model), python_executable=str(python),
            runtime_versions={'fixture': 'not-inference'}, runtime_modules={'fixture': str(runtime)})
        entries = [upgrade.artifact_entry(p, role) for p, role in
            [(python, 'python'), (proof, 'evidence'), (model_file, 'model'), (runtime, 'runtime')]]
        entries += [upgrade.artifact_entry(path, 'implementation') for path in sorted(self.old_site.glob('*.py'))]
        self.adapter.update(artifacts=entries, runtime_artifacts=[entries[3]])
        self.adapter['sha256'] = adapter_fingerprint(self.adapter)
        ledger = load_ledger(self.root)
        add_record(ledger, dict(asset_id=self.adapter['rights_ref'], sha256=self.adapter['sha256'], kind='semantic-model-adapter',
            verification_status='restricted', permitted_uses=['internal'], restrictions=['fixture only'],
            creator='Fixture author', license_spdx='LicenseRef-Fixture', evidence=str(proof), takedown_status='clear'))
        save_ledger(self.root, ledger)
        self.project['extensions']['local_semantic']['adapters'] = [self.adapter]
        save_project(self.root, self.project)

    def make(self, profiles=1):
        self.fixture(profiles=profiles)
        self.checked.stop()
        self.project = load_project(self.root)[1]
        return self.project

    def run_upgrade(self, *extra):
        return invoke('project', 'upgrade-semantic', '--project', self.root, '--adapter-id', 'model',
            '--new-adapter-id', 'relocated', '--id-prefix', 'u15', *extra)

    def originals(self):
        return {a['id']: (self.root/a['uri']).read_bytes() for a in self.project['assets']}

    def assert_originals(self, original_project, original_files, original_rights):
        current = load_project(self.root)[1]
        self.assertEqual(current['sequences'], original_project['sequences'])
        for key in ('adapters', 'indexes', 'calibrations'):
            for record in original_project['extensions']['local_semantic'].get(key, []):
                self.assertIn(record, current['extensions']['local_semantic'][key])
        for asset in original_project['assets']:
            self.assertEqual(asset_map(current)[asset['id']], asset)
            self.assertEqual((self.root/asset['uri']).read_bytes(), original_files[asset['id']])
        ledger = load_ledger(self.root)
        for record in original_rights['records']:
            self.assertIn(record, ledger['records'])

    def test_old_installation_can_be_missing_and_all_originals_survive(self):
        self.make(profiles=2)
        project, files, rights = copy.deepcopy(self.project), self.originals(), load_ledger(self.root)
        self.old_site.rename(self.base/'old-installation-offline')
        code, result = self.run_upgrade(); self.assertEqual(code, 0, result)
        self.assertEqual(result['data']['model_forward_calls'], 0)
        self.assertEqual(len(result['data']['calibration_mappings']), 2)
        self.assert_originals(project, files, rights)
        current = load_project(self.root)[1]
        adapter = semantic.item(current, 'adapters', 'relocated')
        self.assertTrue(semantic.verify_adapter(adapter)['ok'])
        new_rights = record_for(load_ledger(self.root), adapter['rights_ref'])
        old_rights = record_for(rights, self.adapter['rights_ref'])
        for field in ('verification_status', 'permitted_uses', 'restrictions', 'license_spdx'):
            self.assertEqual(new_rights[field], old_rights[field])
        index = result['data']['index_mappings'][0]['target']
        manifest, vectors, _ = semantic.read_index(self.root, current, index)
        old_manifest, old_vectors, _ = semantic.read_index_payload(self.root, current, 'index')
        self.assertEqual(vectors.tobytes(), old_vectors.tobytes())
        self.assertEqual([r['sample_seconds'] for r in manifest['rows']], [r['sample_seconds'] for r in old_manifest['rows']])
        for mapping in result['data']['calibration_mappings']:
            old_record = next(r for r in self.project['extensions']['local_semantic']['calibrations'] if r['calibration_id'] == mapping['source'])
            new_record = next(r for r in current['extensions']['local_semantic']['calibrations'] if r['calibration_id'] == mapping['target'])
            old_profile = json.loads((self.root/asset_map(current)[old_record['asset_id']]['uri']).read_bytes())
            new_profile = json.loads((self.root/asset_map(current)[new_record['asset_id']]['uri']).read_bytes())
            for field in ('fit', 'observations', 'inference', 'dataset_sha256', 'device', 'device_index', 'query_protocol'):
                self.assertEqual(new_profile[field], old_profile[field])
        value = semantic.search(self.root, current, index_id=index, calibration_id=result['data']['calibration_mappings'][0]['target'], query='visual subject', device='cpu')
        self.assertEqual(value['results'][0]['hits'][0]['asset_id'], 'asset_visual')

    def test_dry_run_creates_no_project_files_or_jobs(self):
        self.make()
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        code, result = self.run_upgrade('--dry-run'); self.assertEqual(code, 0, result)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(result['status'], 'planned')

    def test_bundled_native_modules_relocate_only_with_identical_bytes(self):
        old_site, new_site = self.base/'old-runtime/site', self.base/'new-runtime/site'
        old_package, new_package = old_site/'ai_ad_editor', new_site/'ai_ad_editor'
        old_package.mkdir(parents=True); new_package.mkdir(parents=True)
        for source in self.old_site.glob('*.py'):
            (old_package/source.name).write_bytes(source.read_bytes())
            (new_package/source.name).write_bytes(source.read_bytes())
        runtime_files = []
        for name in ('numpy/__init__.py', 'numpy/_core/native.pyd', 'numpy.libs/native.dll', 'PIL/__init__.py'):
            data = ('fixture bundled native bytes '+name).encode()
            for site in (old_site, new_site):
                path = site/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            runtime_files.append(upgrade.artifact_entry(old_site/name, 'runtime'))
        self.adapter['artifacts'] = [row for row in self.adapter['artifacts'] if row['role'] != 'implementation']
        self.adapter['artifacts'] += [upgrade.artifact_entry(path, 'implementation') for path in sorted(old_package.glob('*.py'))]
        self.adapter['artifacts'] += runtime_files
        self.adapter['runtime_artifacts'] += runtime_files
        self.adapter['runtime_modules'].update(numpy=str(old_site/'numpy/__init__.py'), PIL=str(old_site/'PIL/__init__.py'))
        self.adapter['sha256'] = adapter_fingerprint(self.adapter)
        ledger = load_ledger(self.root)
        record_for(ledger,self.adapter['rights_ref'])['sha256'] = self.adapter['sha256'];save_ledger(self.root,ledger)
        save_project(self.root,self.project)
        with patch.object(semantic_contract,'implementation_files',return_value=sorted(new_package.glob('*.py'))), \
                patch.object(upgrade,'implementation_files',return_value=sorted(new_package.glob('*.py'))):
            self.make(profiles=2); before = self.metadata()
            self.base.joinpath('old-runtime').rename(self.base/'old-runtime-unavailable')
            real_entry = upgrade.artifact_entry
            def interrupted(path, role):
                if role == 'runtime' and Path(path).is_relative_to(new_site):
                    raise upgrade.ExecutionInterrupted('CANCELLED', 'native copy check interrupted', exit_code=8)
                return real_entry(path,role)
            with patch.object(upgrade,'artifact_entry',side_effect=interrupted):
                code,result=self.run_upgrade('--dry-run')
                self.assertEqual(code,8);self.assertEqual(result['errors'][0]['code'],'CANCELLED')
                self.assertEqual(before,self.metadata())
            changed = new_site/'numpy/_core/native.pyd'; original_bytes = changed.read_bytes()
            changed.write_bytes(original_bytes+b'changed')
            code,result = self.run_upgrade('--dry-run')
            self.assertNotEqual(code,0);self.assertEqual(result['errors'][0]['code'],'SEMANTIC_UPGRADE_DEPENDENCY_CHANGED')
            self.assertEqual(before,self.metadata());changed.write_bytes(original_bytes)
            changed.rename(changed.with_suffix('.offline'))
            code,result = self.run_upgrade('--dry-run')
            self.assertNotEqual(code,0);self.assertEqual(result['errors'][0]['code'],'SEMANTIC_UPGRADE_DEPENDENCY_CHANGED')
            changed.with_suffix('.offline').rename(changed)
            code,result = self.run_upgrade();self.assertEqual(code,0,result)
            adapter=result['data']['adapter']
            self.assertEqual(adapter['runtime_upgrade']['relocated_bundled_runtime_files'],4)
            self.assertEqual(adapter['runtime_modules']['numpy'],str(new_site/'numpy/__init__.py'))
            self.assertEqual(adapter['runtime_modules']['PIL'],str(new_site/'PIL/__init__.py'))
            self.assertEqual(adapter['runtime_modules']['fixture'],self.adapter['runtime_modules']['fixture'])
            self.assertTrue(semantic.verify_adapter(adapter)['ok'])
            self.assertEqual(result['data']['model_forward_calls'],0)

    def test_changed_current_implementation_requires_rebuild(self):
        self.make(); before = self.metadata()
        (self.new_site/'semantic_worker.py').write_bytes(b'# changed numeric implementation\n')
        code, result = self.run_upgrade(); self.assertNotEqual(code, 0)
        self.assertEqual(result['errors'][0]['code'], 'SEMANTIC_UPGRADE_REBUILD_REQUIRED')
        self.assertEqual(before, self.metadata())

    def test_changed_model_runtime_python_and_evidence_are_each_rejected(self):
        self.make(); before = self.metadata()
        for row in self.adapter['artifacts']:
            if row['role'] == 'implementation': continue
            path = Path(row['path']); data = path.read_bytes()
            path.write_bytes(data+b'!')
            with self.subTest(role=row['role']):
                code, result = self.run_upgrade(); self.assertNotEqual(code, 0)
                self.assertEqual(result['errors'][0]['code'], 'SEMANTIC_UPGRADE_DEPENDENCY_CHANGED')
                self.assertEqual(before, self.metadata())
            path.write_bytes(data)

    def test_corrupt_vector_preview_source_and_dataset_each_reject(self):
        self.make(); before = self.metadata()
        record = self.project['extensions']['local_semantic']['indexes'][0]
        profile = self.project['extensions']['local_semantic']['calibrations'][0]
        for ident in [record['vector_asset_id'], record['frame_asset_ids'][0], 'asset_visual', profile['dataset_asset_id'], profile['asset_id']]:
            path = self.root/asset_map(self.project)[ident]['uri']; data = path.read_bytes(); path.write_bytes(data+b'!')
            with self.subTest(asset=ident):
                code, result = self.run_upgrade(); self.assertNotEqual(code, 0, result)
                self.assertEqual(before, self.metadata())
            path.write_bytes(data)

    def test_cancel_before_upgrade_keeps_originals(self):
        self.make(); marker = self.root/'cancel'; marker.touch(); before = self.metadata()
        code, result = self.run_upgrade('--cancel-file', marker)
        self.assertNotEqual(code, 0); self.assertEqual(result['errors'][0]['code'], 'CANCELLED')
        self.assertEqual(before, self.metadata())

    def test_duplicate_target_is_preserved_and_idempotency_replays(self):
        self.make()
        code, result = self.run_upgrade('--idempotency-key', 'upgrade-once'); self.assertEqual(code, 0, result)
        before = self.metadata()
        code, replay = self.run_upgrade('--idempotency-key', 'upgrade-once'); self.assertEqual(code, 0, replay)
        self.assertEqual(before, self.metadata())
        self.assertIn('IDEMPOTENT_REPLAY', {r['code'] for r in replay['warnings']})
        code, result = self.run_upgrade(); self.assertNotEqual(code, 0)
        self.assertEqual(result['errors'][0]['code'], 'SEMANTIC_UPGRADE_TARGET_EXISTS')
        self.assertEqual(before, self.metadata())

    def test_save_failure_rolls_back_metadata_and_published_trees(self):
        self.make(); before = self.metadata(); files = self.originals()
        before_assets = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in (self.root/'assets').rglob('*') if p.is_file()}
        original_save = upgrade.save_project
        def fault(*args):
            original_save(*args)
            raise AppError('TEST_UPGRADE_COMMIT', 'Injected fault after real project save', exit_code=6)
        with patch.object(upgrade, 'save_project', side_effect=fault):
            code, result = self.run_upgrade()
        self.assertNotEqual(code, 0); self.assertEqual(result['errors'][0]['code'], 'TEST_UPGRADE_COMMIT')
        self.assertEqual(before, self.metadata())
        self.assertEqual(files, self.originals())
        self.assertEqual(before_assets, {p.relative_to(self.root).as_posix(): p.read_bytes() for p in (self.root/'assets').rglob('*') if p.is_file()})

    def test_disk_budget_rejects_without_changing_metadata(self):
        self.make(); before = self.metadata()
        usage = type('Usage', (), {'free': 1})()
        with patch.object(upgrade.shutil, 'disk_usage', return_value=usage):
            code, result = self.run_upgrade()
        self.assertNotEqual(code, 0); self.assertEqual(result['errors'][0]['code'], 'SEMANTIC_UPGRADE_DISK_BUDGET')
        self.assertEqual(before, self.metadata())

    def test_two_indexes_and_profiles_publish_as_independently_owned_trees(self):
        self.make()
        with patch.object(semantic, '_checked_adapter', return_value=self.adapter), patch.object(semantic, 'embed',
                return_value=(np.tile(np.eye(1, semantic_contract.DIMENSION, dtype=np.float32), (1, 1)), {'contract_test_stub': True})):
            semantic.build_index(self.root, self.project, index_id='second-index', adapter_id='model', asset_ids=['asset_visual'])
        self.project = load_project(self.root)[1]
        original_profile = self.project['extensions']['local_semantic']['calibrations'][0]
        data = self.root/asset_map(self.project)[original_profile['dataset_asset_id']]['uri']
        with patch.object(semantic, '_checked_adapter', return_value=self.adapter):
            baseline.decision.calibrate(self.root, self.project, index_id='second-index', calibration_id='second-profile', input_path=str(data), device='cpu')
        self.project = load_project(self.root)[1]
        code, result = self.run_upgrade(); self.assertEqual(code, 0, result)
        self.assertEqual(len(result['data']['index_mappings']), 2)
        self.assertEqual(len(result['data']['calibration_mappings']), 2)
        self.assertEqual(len(result['data']['managed_workspaces']), 4)
        self.assertEqual(len({r['path'] for r in result['data']['managed_workspaces']}), 4)

    def test_explicit_index_selection_refuses_unknown_or_duplicate_ids(self):
        self.make(); before = self.metadata()
        for args in [('--index-id', 'absent'), ('--index-id', 'index', '--index-id', 'index')]:
            code, result = self.run_upgrade(*args)
            self.assertNotEqual(code, 0); self.assertEqual(before, self.metadata())
        code, result = self.run_upgrade('--index-id', 'index', '--dry-run')
        self.assertEqual(code, 0, result); self.assertEqual(len(result['data']['index_mappings']), 1)

    def test_missing_original_rights_and_orphan_profile_refuse(self):
        self.make(); before = self.metadata()
        ledger = load_ledger(self.root)
        ledger['records'] = [r for r in ledger['records'] if r['asset_id'] != self.adapter['rights_ref']]
        save_ledger(self.root, ledger)
        code, result = self.run_upgrade(); self.assertNotEqual(code, 0)
        (self.root/'rights-ledger.json').write_bytes(before['rights-ledger.json'])
        self.project['extensions']['local_semantic']['calibrations'][0]['index_id'] = 'missing'
        save_project(self.root, self.project)
        code, result = self.run_upgrade(); self.assertNotEqual(code, 0)

    def test_added_or_removed_implementation_inventory_requires_rebuild(self):
        self.make(); before = self.metadata()
        with patch.object(upgrade, 'implementation_files', return_value=[self.new_site/'semantic_worker.py']):
            code, result = self.run_upgrade()
        self.assertNotEqual(code, 0); self.assertEqual(result['errors'][0]['code'], 'SEMANTIC_UPGRADE_REBUILD_REQUIRED')
        self.assertEqual(before, self.metadata())

    def test_copy_interruption_removes_partial_stages_and_retains_metadata(self):
        self.make(); before = self.metadata()
        before_files = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in (self.root/'assets').rglob('*') if p.is_file()}
        original_copy = upgrade._copy
        def interrupted(*args):
            original_copy(*args)
            raise AppError('CANCELLED', 'Contract interruption after one complete real copy', exit_code=6)
        with patch.object(upgrade, '_copy', side_effect=interrupted):
            code, result = self.run_upgrade()
        self.assertNotEqual(code, 0); self.assertEqual(result['errors'][0]['code'], 'CANCELLED')
        self.assertEqual(before, self.metadata())
        self.assertEqual(before_files, {p.relative_to(self.root).as_posix(): p.read_bytes() for p in (self.root/'assets').rglob('*') if p.is_file()})

    def test_no_profiles_still_preserves_valid_searchable_index(self):
        self.make(profiles=0)
        code, result = self.run_upgrade(); self.assertEqual(code, 0, result)
        self.assertEqual(result['data']['calibration_mappings'], [])
        current = load_project(self.root)[1]
        self.assertEqual(len(semantic.read_index(self.root, current, result['data']['index_mappings'][0]['target'])[1]), 1)

    def test_native_read_locks_cover_profile_and_dataset_during_planning(self):
        self.make(); record = self.project['extensions']['local_semantic']['calibrations'][0]
        targets = [self.root/asset_map(self.project)[record[key]]['uri'] for key in ('asset_id', 'dataset_asset_id')]
        original = upgrade.load_profile
        attempts = []
        def inspect(*args, **kwargs):
            for path in targets:
                with self.assertRaises(PermissionError):
                    with path.open('r+b'):
                        pass
                attempts.append(path)
            return original(*args, **kwargs)
        with patch.object(upgrade, 'load_profile', side_effect=inspect):
            code, result = self.run_upgrade('--dry-run')
        self.assertEqual(code, 0, result); self.assertEqual(len(attempts), 2)


if __name__ == '__main__':
    unittest.main()
