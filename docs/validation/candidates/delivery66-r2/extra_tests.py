class DeliveryCorrectionCases:
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

