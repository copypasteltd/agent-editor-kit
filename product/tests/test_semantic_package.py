"""Portable semantic data and transactional import; synthetic contracts, not model quality."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

import test_semantic as baseline
from ai_ad_editor import convert, semantic, semantic_decision as decision
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import asset_map, load_project, save_project
from ai_ad_editor.rights import load_ledger, record_for, record_history
from ai_ad_editor.semantic_contract import DIMENSION, ENGINE, PREPROCESSING, PROTOCOL, adapter_fingerprint


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')


class SemanticPackageTests(unittest.TestCase):
    def setUp(self):
        baseline.SemanticIndexIntegrityTests.setUp(self)
        self.adapter.update(engine=ENGINE, protocol=PROTOCOL, dimension=DIMENSION,
            preprocessing=PREPROCESSING, threads=4, model_path=str(self.base/'absent-model'),
            python_executable=str(self.base/'absent-python.exe'))
        self.adapter['sha256'] = adapter_fingerprint(self.adapter)
        self.project.setdefault('extensions', {})['local_semantic'] = dict(adapters=[self.adapter], indexes=[])
        save_project(self.root, self.project)
        self.package = self.base/'editable.aevpkg.zip'

    def fixture(self, *, external=False, profiles=1):
        if external:
            asset_map(self.project)['asset_visual']['uri'] = str(self.source)
            asset_map(self.project)['asset_visual'].setdefault('extensions', {})['external_authorized'] = True
            save_project(self.root, self.project)
        baseline.SemanticIndexIntegrityTests.build(self)
        self.embedding.stop()
        self.infer = patch.object(semantic, 'embed', side_effect=lambda root, adapter, items, task, **kwargs:
            (np.stack([baseline.basis(0 if v['text'].startswith('visual') else 1) for v in items]),
             dict(response=dict(device='cpu', device_index=0), contract_test_stub=True)))
        self.infer.start(); self.addCleanup(self.infer.stop)
        truth = dict(format=decision.DATASET_FORMAT, scope='Synthetic URI and integrity contract only.',
            queries=[dict(id='q'+str(i), text=('visual ' if i < 16 else 'unrelated ')+str(i),
                expected_asset_ids=['asset_visual'] if i < 16 else []) for i in range(32)])
        data = self.base/'truth.json'; data.write_bytes(encoded(truth))
        for i in range(profiles):
            decision.calibrate(self.root, self.project, index_id='index', calibration_id='accept'+str(i),
                input_path=str(data), device='cpu')
            self.project = load_project(self.root)[1]
        return self.project

    def export(self):
        return convert._export_project_package(self.root, self.project, self.package)

    def import_to(self, name='restored'):
        destination = self.base/name
        value = convert.import_external(self.package, destination)
        self.assertEqual(value['root'], str(destination))
        self.assertFalse(list(self.base.glob('.aek-package-*')))
        return destination, load_project(destination)[1], value

    def metadata(self):
        return {n:(self.root/n).read_bytes() for n in ('project.json', 'rights-ledger.json')}

    def repack(self, change):
        with zipfile.ZipFile(self.package) as archive:
            files = {n:archive.read(n) for n in archive.namelist()}
        change(files)
        manifest = json.loads(files[convert.PROJECT_PACKAGE_MANIFEST])
        manifest['files'] = [dict(path=n, size=len(v), sha256=hashlib.sha256(v).hexdigest())
            for n,v in sorted(files.items()) if n not in {convert.PROJECT_PACKAGE_MANIFEST, convert.PROJECT_PACKAGE_REPORT}]
        files[convert.PROJECT_PACKAGE_MANIFEST] = encoded(manifest)
        with zipfile.ZipFile(self.package, 'w') as archive:
            for n,v in files.items(): archive.writestr(n,v)

    def reject_import(self, *, empty=False):
        destination = self.base/'reject'
        if empty: destination.mkdir()
        with self.assertRaises((AppError, ValueError)):
            convert.import_external(self.package, destination)
        self.assertEqual(destination.exists(), empty)
        if empty: self.assertEqual(list(destination.iterdir()), [])
        self.assertFalse(list(self.base.glob('.aek-package-*')))

    def test_owned_namespace_and_all_semantic_bytes_are_preserved(self):
        self.fixture(profiles=2); before = self.metadata(); self.export()
        root, project, result = self.import_to()
        for asset in self.project['assets']:
            target = asset_map(project)[asset['id']]
            self.assertEqual(target, asset)
            self.assertEqual((root/target['uri']).read_bytes(), (self.root/asset['uri']).read_bytes())
        self.assertEqual(project['extensions']['local_semantic'], self.project['extensions']['local_semantic'])
        self.assertEqual((root/'rights-ledger.json').read_bytes(), before['rights-ledger.json'])
        self.assertEqual(self.metadata(), before)
        self.assertEqual([r['capability'] for r in result['report_data']['warnings']], ['semantic-native-runtime'])

    def test_index_only_package_keeps_runtime_external_and_does_not_infer(self):
        self.fixture(profiles=0)
        with (patch.object(semantic, 'embed', side_effect=AssertionError('no inference in conversion')),
              patch.object(semantic, 'verify_adapter', side_effect=AssertionError('no native runtime check'))):
            value = self.export(); self.import_to()
        self.assertEqual(value['report_data']['semantic_data']['new_model_forwards'], 0)
        self.assertFalse(Path(self.adapter['model_path']).exists())

    def test_search_after_source_project_is_moved_uses_imported_assets(self):
        self.fixture(); self.export(); root, project, _ = self.import_to()
        self.root.rename(self.base/'original-offline')
        for query, expected in [('visual subject', ['asset_visual']), ('unrelated subject', [])]:
            value = semantic.search(root, project, index_id='index', calibration_id='accept0', query=query, device='cpu')
            self.assertEqual([h['asset_id'] for h in value['results'][0]['hits']], expected)

    def test_external_source_rewrites_only_paths_and_dependent_fingerprints(self):
        self.fixture(external=True); before = self.metadata()
        old_index = semantic.read_index(self.root, self.project, 'index')[0]
        old_profile = decision.load_profile(self.root, self.project, 'accept0', old_index, kind=None)
        value = self.export(); root, project, _ = self.import_to()
        new_index = semantic.read_index(root, project, 'index')[0]
        new_profile = decision.load_profile(root, project, 'accept0', new_index, kind=None)
        self.assertTrue(value['report_data']['semantic_data']['indexes'][0]['uri_rewritten'])
        self.assertNotEqual(new_index['fingerprint'], old_index['fingerprint'])
        for field in ('vectors','adapter_sha256','preprocessing','sampling'):
            if field in old_index: self.assertEqual(new_index[field], old_index[field])
        for field in ('fit','observations','dataset_sha256','device','device_index','adapter_sha256'):
            self.assertEqual(new_profile[field], old_profile[field])
        self.assertEqual(project['extensions']['local_semantic']['adapters'], self.project['extensions']['local_semantic']['adapters'])
        self.assertFalse(Path(asset_map(project)['asset_visual']['uri']).is_absolute())
        for record in self.project['extensions']['local_semantic']['indexes'] + self.project['extensions']['local_semantic']['calibrations']:
            asset = asset_map(self.project)[record['asset_id']]
            old = record_for(load_ledger(self.root), asset['rights_ref'])
            new = record_for(load_ledger(root), asset['rights_ref'])
            for field in ('verification_status','license','permissions'): self.assertEqual(new.get(field), old.get(field))
            self.assertEqual(len(record_history(load_ledger(root), asset['rights_ref'])), 2)
        self.assertEqual(self.metadata(), before)
        self.source.rename(self.base/'external-offline.png')
        self.root.rename(self.base/'original-offline')
        self.assertEqual(semantic.search(root, project, index_id='index', query='visual',
            calibration_id='accept0', device='cpu')['results'][0]['hits'][0]['asset_id'], 'asset_visual')

    def test_second_export_import_preserves_first_relocation_bytes(self):
        self.fixture(external=True); self.export(); root, project, _ = self.import_to()
        second = self.base/'second.zip'; convert._export_project_package(root, project, second)
        destination = self.base/'second'; convert.import_external(second, destination)
        repeated = load_project(destination)[1]
        self.assertEqual(repeated['extensions']['local_semantic'], project['extensions']['local_semantic'])
        for asset in project['assets']:
            self.assertEqual((root/asset['uri']).read_bytes(), (destination/asset['uri']).read_bytes())

    def test_damaged_manifest_vector_preview_source_profile_dataset_each_refuse_export(self):
        self.fixture(); registered = self.project['extensions']['local_semantic']
        index, profile = registered['indexes'][0], registered['calibrations'][0]
        identifiers = [index['asset_id'], index['vector_asset_id'], index['frame_asset_ids'][0],
            'asset_visual', profile['asset_id'], profile['dataset_asset_id']]
        before = self.metadata()
        for ident in identifiers:
            path = self.root/asset_map(self.project)[ident]['uri']; original = path.read_bytes()
            path.write_bytes(original + b'!')
            with self.subTest(asset=ident), self.assertRaises((AppError, ValueError)): self.export()
            self.assertFalse(self.package.exists()); path.write_bytes(original)
        self.assertEqual(self.metadata(), before)

    def test_missing_index_rights_binding_refuses_even_for_unchanged_paths(self):
        self.fixture(); ledger = load_ledger(self.root)
        ident = self.project['extensions']['local_semantic']['indexes'][0]['asset_id']
        rights = asset_map(self.project)[ident]['rights_ref']
        ledger['records'] = [r for r in ledger['records'] if r['asset_id'] != rights]
        (self.root/'rights-ledger.json').write_bytes(encoded(ledger))
        with self.assertRaisesRegex(ValueError, 'rights/hash'): self.export()

    def test_rehashed_outer_manifest_does_not_hide_corrupt_vector(self):
        self.fixture(); self.export()
        uri = asset_map(self.project)[self.project['extensions']['local_semantic']['indexes'][0]['vector_asset_id']]['uri']
        self.repack(lambda files: files.__setitem__(uri, files[uri]+b'!'))
        self.reject_import()

    def test_rehashed_outer_manifest_does_not_hide_corrupt_dataset_or_profile(self):
        self.fixture()
        record = self.project['extensions']['local_semantic']['calibrations'][0]
        for field in ('dataset_asset_id','asset_id'):
            self.export(); uri = asset_map(self.project)[record[field]]['uri']
            self.repack(lambda files: files.__setitem__(uri, files[uri]+b' '))
            with self.subTest(field=field): self.reject_import(empty=True)
            (self.base/'reject').rmdir()

    def test_legacy_flattened_semantic_package_is_rejected_before_publication(self):
        self.fixture(); self.export()
        def flatten(files):
            project = json.loads(files['project.json'])
            for asset in project['assets']:
                old = asset['uri']; new = 'assets/'+asset['id']+'_'+Path(old).name
                files[new] = files.pop(old); asset['uri'] = new
            files['project.json'] = encoded(project)
        self.repack(flatten); self.reject_import()

    def test_duplicate_or_missing_semantic_registration_refuses(self):
        self.fixture(); original = copy.deepcopy(self.project)
        for collection, mutation in [('indexes','duplicate'), ('calibrations','duplicate'),
                                     ('indexes','missing'), ('calibrations','orphan'), ('adapters','malformed')]:
            self.project = copy.deepcopy(original); registry = self.project['extensions']['local_semantic']
            if mutation == 'duplicate': registry[collection].append(copy.deepcopy(registry[collection][0]))
            elif mutation == 'missing': registry[collection][0].pop('adapter_id')
            elif mutation == 'orphan': registry[collection][0]['index_id'] = 'absent'
            else: registry[collection].append(None)
            with self.subTest(collection=collection, mutation=mutation), self.assertRaises((AppError, ValueError)):
                self.export()
        self.project = original

    def test_adapter_metadata_fingerprint_cannot_be_silently_retrusted(self):
        self.fixture(); self.project['extensions']['local_semantic']['adapters'][0]['threads'] = 8
        with self.assertRaises(AppError): self.export()

    def test_profile_bound_to_another_index_refuses_export(self):
        self.fixture(); self.project['extensions']['local_semantic']['calibrations'][0]['index_id'] = 'other'
        with self.assertRaises(ValueError): self.export()

    def test_nonempty_destination_remains_untouched(self):
        self.fixture(); self.export(); destination = self.base/'existing'; destination.mkdir()
        marker = destination/'keep.txt'; marker.write_bytes(b'keep')
        with self.assertRaises(ValueError): convert.import_external(self.package, destination)
        self.assertEqual(marker.read_bytes(), b'keep'); self.assertEqual(list(destination.iterdir()), [marker])

    def test_invalid_zip_is_cleaned_before_publication(self):
        self.package.write_bytes(b'not a zip'); self.reject_import()

    def test_windows_alias_members_and_drive_relative_paths_refuse(self):
        self.fixture()
        for bad in ('assets/CON.txt', 'assets/a:stream', 'C:escape.txt', '../escape.txt',
                    'assets/../escape.txt', 'assets//ambiguous.txt', 'assets/space .txt ', 'PROJECT.JSON'):
            self.export()
            self.repack(lambda files: files.__setitem__(bad, b'bad'))
            with self.subTest(member=bad): self.reject_import()

    def test_publish_rename_failure_keeps_preexisting_empty_destination(self):
        self.fixture(); self.export(); destination = self.base/'existing-empty'; destination.mkdir()
        with patch.object(Path, 'rename', side_effect=OSError('injected publish failure')), self.assertRaises(OSError):
            convert._import_project_package(self.package, destination)
        self.assertTrue(destination.is_dir()); self.assertEqual(list(destination.iterdir()), [])
        self.assertFalse(list(self.base.glob('.aek-package-*')))


if __name__ == '__main__':
    unittest.main()
