"""Real file activation/rollback and native PowerShell; synthetic release fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor import delivery as d
from ai_ad_editor.errors import AppError
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.music_generation_pipeline import MusicDiagnosticSession


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / '中文 交付'
        self.root.mkdir()
        self.stage = self.root / 'local/candidate'
        self.stage.mkdir(parents=True)
        self.version = '0.1.66'
        self.release = 'test-only-synthetic-release'
        self.initial = {d.SKILL + 'SKILL.md': b'Old skill\n',
                        d.SKILL + 'scripts/run.ps1': b'Write-Output "old"\n'}
        for name, data in self.initial.items():
            self.put(self.root / name, data)
        manifest = dict(skill_count=1, module_count=17, cli_version='0.1.63', files=[
            dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            for name, data in self.initial.items()])
        self.put(self.root / d.MANIFEST, encoded(manifest))
        self.put(self.root / d.CONFIG, encoded(dict(release='old')))
        self.previous = {name: (self.root / name).read_bytes() for name in [*self.initial, d.CONFIG, d.MANIFEST]}
        installed = self.root / 'local/installed'
        self.put(installed / 'run.py', b'# Synthetic installed-launcher fixture\n')
        self.put(installed / 'site/ai_ad_editor/__init__.py', b'VERSION = "0.1.66"\n')
        self.put(installed / 'receipt.json', encoded(dict(manifest_sha256='sha256:' + 'a' * 64)))
        config = dict(release=self.release, installed_directory=str(installed), python='synthetic-never-invoked',
                      manifest_sha256='sha256:' + 'a' * 64, launcher_sha256=d.sha(installed / 'run.py'), native_only=True)
        self.next = {d.SKILL + 'SKILL.md': b'New synthetic skill\n',
            d.SKILL + 'scripts/run.ps1': b'Write-Output \'{"ok":true,"data":{"cli_version":"0.1.66"}}\'\n',
            d.SKILL + 'references/added.md': b'New reference\n', d.CONFIG: encoded(config)}
        manifest = dict(manifest, cli_version=self.version, release=self.release, runtime_config=d.CONFIG,
            manifest_sha256=config['manifest_sha256'], files=[dict(path=name, bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest()) for name, data in self.next.items() if name.startswith(d.SKILL)])
        self.next[d.MANIFEST] = encoded(manifest)
        rows = []
        for index, (name, data) in enumerate(self.next.items()):
            source = self.stage / f'{index}.bin'
            self.put(source, data)
            rows.append(dict(path=name, source=str(source), bytes=len(data), sha256=d.sha(source)))
        self.archive = self.root / 'local/release.zip'
        self.put(self.archive, b'Synthetic archive bytes; no product build claimed')
        pins = {'__init__.py': d.sha(installed / 'site/ai_ad_editor/__init__.py')}
        gates = {}
        for role in ('source-tests', 'installed-tests', 'package-replay', 'skill-entry'):
            report = dict(status='passed', cli_version=self.version, synthetic_fixture=True,
                tests=1, frozen_equal=True, failures=0, errors=0, skipped=0, source_fallback=False,
                file_hashes={'product/src/ai_ad_editor/' + name: pin for name, pin in pins.items()},
                complete_master_WAV_equal=True, complete_generation_recipe_equal=True,
                complete_rendered_RGBA_PCM_equal=True, actual_PowerShell_entry=True)
            path = self.stage / (role + '.json')
            self.put(path, encoded(report))
            gates[role] = dict(path=str(path), sha256=d.sha(path))
        self.spec = dict(format=d.FORMAT, cli_version=self.version, release=self.release,
            expected_current=d.inventory(self.root), files=rows, application_files=pins, gates=gates,
            archive=dict(path=str(self.archive), sha256=d.sha(self.archive)))
        self.descriptor = self.stage / 'delivery.json'
        self.save()

    def put(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save(self):
        self.put(self.descriptor, encoded(self.spec))

    def assert_previous(self):
        for name, data in self.previous.items():
            self.assertEqual((self.root / name).read_bytes(), data, name)
        self.assertFalse((self.root / (d.SKILL + 'references/added.md')).exists())

    def test_verified_activation_and_real_powershell_then_full_rollback(self):
        planned = d.activate(self.root, self.descriptor, dry_run=True)
        self.assertEqual(planned['status'], 'planned')
        self.assert_previous()
        result = d.activate(self.root, self.descriptor)
        self.assertEqual(result['status'], 'activated')
        self.assertTrue(result['actual_PowerShell_entry'])
        self.assertEqual(d.recover(self.root)['status'], 'committed')
        self.assertEqual(d.recover(self.root, rollback=True)['status'], 'rolled-back')
        self.assert_previous()
        self.assertEqual(d.recover(self.root)['status'], 'clean')

    def test_changed_candidate_late_in_list_never_starts_publication(self):
        Path(self.spec['files'][-1]['source']).write_bytes(b'corrupted late candidate')
        with patch.object(d, '_atomic_write_bytes', wraps=d._atomic_write_bytes) as write:
            with self.assertRaises(AppError):
                d.activate(self.root, self.descriptor)
            write.assert_not_called()
        self.assert_previous()

    def test_installed_source_changed_after_acceptance_is_rejected(self):
        (self.root / 'local/installed/site/ai_ad_editor/__init__.py').write_bytes(b'VERSION="0.1.66"\n# changed\n')
        with self.assertRaises(AppError):
            d.activate(self.root, self.descriptor)
        self.assert_previous()

    def test_failed_gate_and_foreign_source_pins_reject_without_changes(self):
        for field, value in [('failures', 1), ('frozen_equal', False), ('file_hashes', {})]:
            path = Path(self.spec['gates']['source-tests']['path'])
            original = json.loads(path.read_bytes())
            self.put(path, encoded(dict(original, **{field: value})))
            self.spec['gates']['source-tests']['sha256'] = d.sha(path)
            self.save()
            with self.subTest(field=field), self.assertRaises(AppError):
                d.activate(self.root, self.descriptor)
            self.assert_previous()
            self.put(path, encoded(original))
            self.spec['gates']['source-tests']['sha256'] = d.sha(path)
        self.save()

    def test_actual_write_failure_rolls_back_added_and_modified_files(self):
        original = d._atomic_write_bytes
        failed = []
        def write(path, data):
            if path.name == 'run.ps1' and not failed:
                failed.append(True)
                raise OSError('Synthetic publication I/O fault')
            return original(path, data)
        with patch.object(d, '_atomic_write_bytes', side_effect=write), self.assertRaises(OSError):
            d.activate(self.root, self.descriptor)
        self.assert_previous()
        self.assertEqual(d.read_json(d.pending(self.root))['status'], 'rolled-back')

    def test_entry_failure_rolls_back_all_files(self):
        row = next(row for row in self.spec['files'] if row['path'].endswith('run.ps1'))
        Path(row['source']).write_bytes(b'exit 1\n')
        row['sha256'] = d.sha(Path(row['source']))
        row['bytes'] = Path(row['source']).stat().st_size
        manifest_row = next(row for row in self.spec['files'] if row['path'] == d.MANIFEST)
        manifest = json.loads(Path(manifest_row['source']).read_bytes())
        entry = next(x for x in manifest['files'] if x['path'].endswith('run.ps1'))
        entry.update(sha256=row['sha256'], bytes=row['bytes'])
        self.put(Path(manifest_row['source']), encoded(manifest))
        manifest_row.update(sha256=d.sha(Path(manifest_row['source'])), bytes=Path(manifest_row['source']).stat().st_size)
        self.save()
        with self.assertRaises(AppError):
            d.activate(self.root, self.descriptor)
        self.assert_previous()

    def test_bad_last_backup_prevents_any_rollback_write(self):
        d.activate(self.root, self.descriptor)
        journal = d.read_json(d.pending(self.root))
        index = max(i for i, row in enumerate(journal['files']) if row['existed'])
        path = self.root / 'local/agent-ffmpeg/deliveries' / journal['delivery_id'] / f'{index:04d}.bin'
        path.write_bytes(b'corrupted saved baseline')
        with patch.object(d, '_atomic_write_bytes', wraps=d._atomic_write_bytes) as write:
            with self.assertRaises(AppError):
                d.recover(self.root, rollback=True)
            write.assert_not_called()

    def test_rollback_preserves_later_user_modifications(self):
        d.activate(self.root, self.descriptor)
        path = self.root / (d.SKILL + 'SKILL.md')
        path.write_bytes(b'User edits after installation')
        with self.assertRaises(AppError):
            d.recover(self.root, rollback=True)
        self.assertEqual(path.read_bytes(), b'User edits after installation')

    def test_recovery_of_prepared_transition_restores_previous_exact_bytes(self):
        d.activate(self.root, self.descriptor)
        journal = d.read_json(d.pending(self.root))
        journal['status'] = 'prepared'
        self.put(d.pending(self.root), encoded(journal))
        self.put(self.root / d.CONFIG, b'{"release":"interrupted-transition"}')
        self.assertEqual(d.recover(self.root)['status'], 'rolled-back')
        self.assert_previous()

    def test_descriptor_cannot_write_media_or_alias_paths(self):
        for value in ('assets/original.wav', d.SKILL + '../escape.md', d.SKILL + 'file:stream'):
            changed = copy.deepcopy(self.spec)
            changed['files'][-1]['path'] = value
            self.put(self.descriptor, encoded(changed))
            with self.subTest(path=value), self.assertRaises(AppError):
                d.activate(self.root, self.descriptor)
            self.assert_previous()

    def test_old_or_corrupt_archive_is_not_accepted(self):
        self.archive.write_bytes(b'Changed archive')
        with self.assertRaises(AppError):
            d.activate(self.root, self.descriptor)
        self.assert_previous()


class BoundedMusicProgressTests(unittest.TestCase):
    def test_oversized_progress_is_not_loaded_as_unbounded_json(self):
        temporary = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        session = MusicDiagnosticSession(root, {}, {})
        session.prepared_directory = root
        (root / 'progress.json').write_bytes(b' ' * (2 * 1024**2))
        value = session.read_progress()
        self.assertNotEqual(value.get('state'), 'read')

    def test_unknown_phase_and_invalid_clock_are_not_forwarded(self):
        temporary = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        session = MusicDiagnosticSession(root, {}, {})
        session.prepared_directory = root
        for changes in (dict(phase='foreign-phase'), dict(done=True), dict(total=0)):
            value = dict(phase='generating-music', done=1, total=8, worker_pid=123, **{})
            value.update(changes)
            (root / 'progress.json').write_bytes(encoded(value))
            self.assertEqual(session.read_progress()['state'], 'invalid_music_progress')
