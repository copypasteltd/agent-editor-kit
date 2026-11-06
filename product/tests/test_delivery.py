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
        for role in ('source-tests', 'installed-tests', 'package-replay', 'skill-entry', 'native-music'):
            report = dict(status='passed', cli_version=self.version, synthetic_fixture=True,
                tests=1, discovered_tests=1, frozen_equal=True, failures=0, errors=0, skipped=0, source_fallback=False,
                file_hashes={'product/src/ai_ad_editor/' + name: pin for name, pin in pins.items()},
                complete_master_WAV_equal=True, complete_generation_recipe_equal=True,
                complete_rendered_RGBA_PCM_equal=True, actual_PowerShell_entry=True,
                application_files=pins, skill_files={name: hashlib.sha256(data).hexdigest()
                    for name, data in self.next.items() if name.startswith(d.SKILL)},
                actual_CUDA_music=True, complete_PCM_verified=True, project_placement_verified=True,
                owned_process_cleanup_verified=True,
                actual_generation=dict(complete_PCM_roundtrip_verified=True,
                    cleanup=dict(worker_exited=True, owner_job_closed=True),
                    worker=dict(output_PCM_sha256='sha256:' + 'b' * 64, model=dict(neural_backend='cuda',
                        forwards=dict(text=2, language_model=50, diffusion=8, vae=1),
                        forward_output_devices={name: ['cuda:0'] for name in ('text', 'language_model', 'diffusion', 'vae')}))))
            # These are explicitly synthetic protocol fixtures, never inference evidence.
            audio = self.stage / 'fixture.wav'
            import struct
            samples = b'\0' * 16
            wav = b'RIFF' + struct.pack('<I', 36 + len(samples)) + b'WAVEfmt ' + struct.pack('<IHHIIHH',
                16, 1, 1, 8000, 16000, 2, 16) + b'data' + struct.pack('<I', len(samples)) + samples
            self.put(audio, wav)
            request = self.stage / 'fixture-request.json'
            self.put(request, encoded(dict(synthetic_fixture=True)))
            project_manifest = self.stage / 'fixture-project.json'
            self.put(project_manifest, encoded(dict(synthetic_fixture=True)))
            report.update(master_audio=dict(path=str(audio), bytes=len(wav), sha256=d.sha(audio)),
                request_file=dict(path=str(request), bytes=request.stat().st_size, sha256=d.sha(request)),
                project_manifest=dict(path=str(project_manifest), bytes=project_manifest.stat().st_size, sha256=d.sha(project_manifest)),
                independent_PCM_sha256='sha256:' + 'b' * 64)
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
        self.sync_skill_pins()
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
        self.put(self.root / d.CONFIG, b'{"release":"delivery-switch-in-progress"}\n')
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

    def update_gate(self, role, **changes):
        row = self.spec['gates'][role]
        path = Path(row['path'])
        value = json.loads(path.read_bytes())
        value.update(changes)
        self.put(path, encoded(value))
        row['sha256'] = d.sha(path)

    def sync_skill_pins(self):
        pins = {row['path']: d.sha(Path(row['source'])) for row in self.spec['files'] if row['path'].startswith(d.SKILL)}
        for role in ('skill-entry', 'native-music'):
            self.update_gate(role, skill_files=pins)

    def test_all_descriptor_fields_reject_before_any_publication(self):
        original = copy.deepcopy(self.spec)
        for label, edit in (
            ('missing version', lambda v: v.pop('cli_version')),
            ('numeric version', lambda v: v.update(cli_version=66)),
            ('wrong release', lambda v: v.update(release=[])),
            ('missing files', lambda v: v.pop('files')),
            ('null row', lambda v: v['files'].__setitem__(0, None)),
            ('numeric path', lambda v: v['files'][0].update(path=1)),
            ('missing source', lambda v: v['files'][0].pop('source')),
            ('boolean size', lambda v: v['files'][0].update(bytes=True)),
            ('wrong digest type', lambda v: v['files'][0].update(sha256=[])),
            ('missing application pins', lambda v: v.pop('application_files')),
            ('null archive', lambda v: v.update(archive=None)),
            ('null gate', lambda v: v['gates'].update({'native-music': None})),
        ):
            value = copy.deepcopy(original)
            edit(value)
            self.put(self.descriptor, encoded(value))
            with self.subTest(label=label), patch.object(d, '_atomic_write_bytes', wraps=d._atomic_write_bytes) as write:
                with self.assertRaises(AppError):
                    d.activate(self.root, self.descriptor)
                write.assert_not_called()
            self.assert_previous()

    def test_current_cuda_evidence_is_required_and_not_just_version_entry(self):
        row = self.spec['gates'].pop('native-music')
        self.save()
        with self.assertRaises(AppError):
            d.activate(self.root, self.descriptor)
        self.assert_previous()
        self.spec['gates']['native-music'] = row
        for key, value in (('actual_CUDA_music', False), ('source_fallback', True),
                           ('complete_PCM_verified', False), ('owned_process_cleanup_verified', False)):
            path = Path(row['path'])
            previous = path.read_bytes()
            self.update_gate('native-music', **{key: value})
            self.save()
            with self.subTest(key=key), self.assertRaises(AppError):
                d.activate(self.root, self.descriptor)
            self.assert_previous()
            self.put(path, previous)
            row['sha256'] = d.sha(path)

    def test_actual_generation_cpu_forward_is_rejected(self):
        row = self.spec['gates']['native-music']
        report = json.loads(Path(row['path']).read_bytes())
        report['actual_generation']['worker']['model']['forward_output_devices']['vae'] = ['cpu']
        self.put(Path(row['path']), encoded(report))
        row['sha256'] = d.sha(Path(row['path']))
        self.save()
        with self.assertRaises(AppError):
            d.activate(self.root, self.descriptor)
        self.assert_previous()

    def test_actual_music_files_remain_pinned_until_activation(self):
        report = json.loads(Path(self.spec['gates']['native-music']['path']).read_bytes())
        for name in ('master_audio', 'request_file'):
            path = Path(report[name]['path'])
            previous = path.read_bytes()
            self.put(path, b'changed after actual verification')
            with self.subTest(name=name), self.assertRaises(AppError):
                d.activate(self.root, self.descriptor)
            self.assert_previous()
            self.put(path, previous)

    def test_replay_and_skill_proofs_bind_to_exact_candidate_bytes(self):
        for role, field in (('package-replay', 'application_files'), ('skill-entry', 'skill_files')):
            row = self.spec['gates'][role]
            path = Path(row['path'])
            previous = path.read_bytes()
            self.update_gate(role, **{field: {}})
            self.save()
            with self.subTest(role=role), self.assertRaises(AppError):
                d.activate(self.root, self.descriptor)
            self.assert_previous()
            self.put(path, previous)
            row['sha256'] = d.sha(path)

    def test_interrupted_recovery_preserves_foreign_user_changes(self):
        d.activate(self.root, self.descriptor)
        journal = d.read_json(d.pending(self.root))
        journal['status'] = 'prepared'
        self.put(d.pending(self.root), encoded(journal))
        path = self.root / (d.SKILL + 'SKILL.md')
        self.put(path, b'User edits made after interruption')
        with patch.object(d, '_atomic_write_bytes', wraps=d._atomic_write_bytes) as write:
            with self.assertRaises(AppError):
                d.recover(self.root)
            write.assert_not_called()
        self.assertEqual(path.read_bytes(), b'User edits made after interruption')

    def test_dry_run_checks_all_backups_without_restore(self):
        d.activate(self.root, self.descriptor)
        journal = d.read_json(d.pending(self.root))
        index = max(i for i, row in enumerate(journal['files']) if row['existed'])
        path = self.root / 'local/agent-ffmpeg/deliveries' / journal['delivery_id'] / f'{index:04d}.bin'
        path.unlink()
        with patch.object(d, '_atomic_write_bytes', wraps=d._atomic_write_bytes) as write:
            with self.assertRaises(AppError):
                d.recover(self.root, rollback=True, dry_run=True)
            write.assert_not_called()

    def test_malformed_journal_never_starts_recovery(self):
        d.activate(self.root, self.descriptor)
        original = d.read_json(d.pending(self.root))
        original['status'] = 'prepared'
        for label, edit in (
            ('bad row', lambda v: v['files'].__setitem__(-1, None)),
            ('bad path', lambda v: v['files'][-1].update(path=3)),
            ('boolean size', lambda v: v['files'][0].update(previous_bytes=True)),
            ('missing digest', lambda v: v['files'][0].pop('previous_sha256')),
            ('wrong existed', lambda v: v['files'][-1].update(existed=1)),
            ('invalid status', lambda v: v.update(status='unknown')),
        ):
            value = copy.deepcopy(original)
            edit(value)
            self.put(d.pending(self.root), encoded(value))
            with self.subTest(label=label), patch.object(d, '_atomic_write_bytes', wraps=d._atomic_write_bytes) as write:
                with self.assertRaises(AppError):
                    d.recover(self.root)
                write.assert_not_called()

    def test_windows_device_names_and_nonfinite_json_are_rejected(self):
        for name in (d.SKILL + 'CON.txt', d.SKILL + 'LPT1.md', d.SKILL + 'bad?.md'):
            with self.subTest(path=name), self.assertRaises(AppError):
                d.checked_path(self.root, name)
        for raw in (b'{"cli_version":"0.1.66","cli_version":"0.1.63"}', b'{"test":NaN}'):
            self.put(self.descriptor, raw)
            with self.subTest(raw=raw), self.assertRaises(AppError):
                d.verify(self.root, self.descriptor)
        self.assert_previous()



class BoundedMusicProgressTests(unittest.TestCase):
    def test_oversized_progress_is_not_loaded_as_unbounded_json(self):
        temporary = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        session = MusicDiagnosticSession(root, {}, {})
        session.prepare(root, {})
        (root / 'progress.json').write_bytes(b' ' * (2 * 1024**2))
        value = session.read_progress()
        self.assertNotEqual(value.get('state'), 'read')

    def test_unknown_phase_and_invalid_clock_are_not_forwarded(self):
        temporary = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        session = MusicDiagnosticSession(root, {}, {})
        session.prepare(root, {})
        for changes in (dict(phase='foreign-phase'), dict(done=True), dict(total=0)):
            value = dict(phase='generating-music', done=1, total=8, worker_pid=123, **{})
            value.update(changes)
            (root / 'progress.json').write_bytes(encoded(value))
            self.assertEqual(session.read_progress()['state'], 'invalid_music_progress')


    def session(self):
        temporary = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        session = MusicDiagnosticSession(root, {}, {})
        session.prepare(root, {})
        return root, session

    def test_valid_progress_forwards_only_approved_fields(self):
        root, session = self.session()
        value = dict(phase='generating-music', done=1, total=8, worker_pid=123)
        (root / 'progress.json').write_bytes(encoded({**value, 'state': 'forged',
            'private_path': 'E:/private/customer.wav', 'unknown': {'large': 'ignored'}}))
        self.assertEqual(session.read_progress(), dict(state='read', **value))

    def test_nonobject_unhashable_and_wrong_typed_progress_is_invalid(self):
        root, session = self.session()
        valid = dict(phase='generating-music', done=1, total=8, worker_pid=123)
        values = [None, [], 'text', 1, True]
        values += [{**valid, **change} for change in (
            dict(phase=[]), dict(phase={}), dict(phase=None), dict(phase=True),
            dict(done=1.0), dict(done=-1), dict(done=9), dict(total=True),
            dict(total=65537), dict(worker_pid=True), dict(worker_pid=0), dict(worker_pid=1.5))]
        values += [{key: value for key, value in valid.items() if key != omitted} for omitted in valid]
        for value in values:
            with self.subTest(value=value):
                (root / 'progress.json').write_bytes(encoded(value))
                self.assertEqual(session.read_progress(), dict(state='invalid_music_progress'))

    def test_missing_and_malformed_progress_keep_bounded_diagnostics(self):
        root, session = self.session()
        self.assertEqual(session.read_progress()['state'], 'missing')
        for raw in (b'{', b'\xff', b'{"phase":"generating-music","phase":"forged"}', b'{"done":NaN}'):
            with self.subTest(raw=raw):
                (root / 'progress.json').write_bytes(raw)
                value = session.read_progress()
                self.assertEqual(value['state'], 'invalid_json')
                self.assertLessEqual(value['bytes_read'], len(raw))

    def test_nonordinary_progress_returns_unavailable_without_consuming_it(self):
        root, session = self.session()
        (root / 'progress.json').mkdir()
        value = session.read_progress()
        self.assertEqual(value, dict(state='unavailable', code='DIAGNOSTIC_FILE_INVALID'))

    def test_unprepared_music_progress_is_explicit(self):
        temporary = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(temporary.cleanup)
        session = MusicDiagnosticSession(Path(temporary.name), {}, {})
        self.assertEqual(session.read_progress(), dict(state='not_prepared'))


class BoundedAudioProgressTests(unittest.TestCase):
    def session(self, *, prepare=True):
        from ai_ad_editor.enhancement_pipeline import AudioDiagnosticSession
        temporary = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        session = AudioDiagnosticSession(root, {}, {})
        if prepare:session.prepare(root, {})
        return root, session

    def test_audio_progress_preserves_segment_clock_and_approved_fields_only(self):
        root, session = self.session()
        payload = dict(phase='neural-enhancement', done=2, total=8, worker_pid=123)
        (root / 'progress.json').write_bytes(encoded({**payload, 'state': 'forged',
            'private_path': 'E:/private/customer.wav'}))
        self.assertEqual(session.read_progress(), dict(state='read', phase='neural-enhancement',
            segments_done=2, segments_total=8, worker_pid=123))

    def test_audio_progress_rejects_nonobjects_unhashable_phases_and_invalid_clocks(self):
        root, session = self.session()
        valid = dict(phase='neural-enhancement', done=2, total=8, worker_pid=123)
        values = [None, [], 'text', 1, True]
        values += [{**valid, **change} for change in (
            dict(phase=[]), dict(phase={}), dict(phase=None), dict(phase='unknown'),
            dict(done=True), dict(done=1.5), dict(done=-1), dict(done=9),
            dict(total=True), dict(total=0), dict(total=65537), dict(worker_pid=True), dict(worker_pid=0))]
        for value in values:
            with self.subTest(value=value):
                (root / 'progress.json').write_bytes(encoded(value))
                self.assertEqual(session.read_progress(), dict(state='invalid_audio_progress'))

    def test_audio_progress_read_failures_keep_bounded_diagnostic_states(self):
        root, session = self.session(prepare=False)
        self.assertEqual(session.read_progress(), dict(state='not_prepared'))
        session.prepare(root, {})
        progress = root / 'progress.json'
        self.assertEqual(session.read_progress()['state'], 'missing')
        for raw in (b'{', b'\xff', b'{"phase":"neural-enhancement","phase":"forged"}'):
            with self.subTest(raw=raw):
                progress.write_bytes(raw)
                self.assertEqual(session.read_progress()['state'], 'invalid_json')
        progress.write_bytes(b' ' * (2 * 1024**2))
        self.assertNotEqual(session.read_progress()['state'], 'read')
        progress.unlink()
        progress.mkdir()
        self.assertEqual(session.read_progress(), dict(state='unavailable', code='DIAGNOSTIC_FILE_INVALID'))
