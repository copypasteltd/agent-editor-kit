"""Adversarial delivery-tool contracts; no model, registration or public writes."""
import copy
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import delivery66 as round_runner
import delivery66_handoff as handoff
import publish_delivery66 as publisher
from run_delivery66_native import process_identity, same_process


class HandoffContracts(unittest.TestCase):
    def setUp(self):
        root = handoff.LOCAL / 'contract-temp'
        root.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def archive(self, entries):
        archive = self.root / 'input.zip'
        with zipfile.ZipFile(archive, 'x') as zipped:
            for name, data in entries:
                zipped.writestr(name, data)
        return archive

    def reject(self, entries):
        archive = self.archive(entries)
        destination = self.root / 'output'
        with self.assertRaises((ValueError, zipfile.BadZipFile)):
            handoff.extract(archive, destination)
        self.assertFalse(destination.exists())

    def test_windows_aliases_and_traversal_are_rejected(self):
        for name in ('../escape', 'a/../escape', '/absolute', 'NUL.png', 'a./b', 'a /b', 'C:escape',
                     'a\\b', 'a//b', 'a/./b', 'LPT1.txt', 'control\x00file'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                handoff.member(name)

    def test_case_alias_archive_fails_before_output_creation(self):
        self.reject([('safe', b'first'), ('SAFE', b'second')])

    def test_file_directory_prefix_conflict_fails_before_output_creation(self):
        self.reject([('parent', b'file'), ('parent/child', b'file')])

    def test_zip_symlink_is_not_followed(self):
        entry = zipfile.ZipInfo('link')
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.reject([(entry, b'../external')])

    def test_corrupt_late_member_does_not_leave_earlier_files(self):
        archive = self.archive([('first', b'valid'), ('last', b'unique-corruption-target')])
        data = archive.read_bytes()
        archive.write_bytes(data.replace(b'unique-corruption-target', b'unique-corruption-targex', 1))
        destination = self.root / 'output'
        with self.assertRaises(zipfile.BadZipFile):
            handoff.extract(archive, destination)
        self.assertFalse(destination.exists())

    def test_entry_size_budget_is_checked_before_extraction(self):
        archive = self.archive([('small', b'12345')])
        with zipfile.ZipFile(archive) as zipped, self.assertRaises(ValueError):
            handoff.archive_plan(zipped, maximum_file=4)

    def test_total_size_budget_is_checked_before_extraction(self):
        archive = self.archive([('one', b'1234'), ('two', b'5678')])
        with zipfile.ZipFile(archive) as zipped, self.assertRaises(ValueError):
            handoff.archive_plan(zipped, maximum_total=7)

    def kit(self, *, bad_digest=False, second_skill=False):
        entries = {handoff.SKILL + 'SKILL.md': b'---\nname: agent-ffmpeg-local-editor\n---\nfixture only\n'}
        if second_skill:
            entries['skills/unwanted/SKILL.md'] = b'fixture'
        rows = [dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()) for name, data in entries.items()]
        if bad_digest:
            rows[0]['sha256'] = '0' * 64
        inventory = dict(cli_version=handoff.VERSION, skill_count=1, module_count=17, files=rows)
        entries['KIT-FILES.json'] = handoff.encoded(inventory)
        return self.archive(list(entries.items()))

    def test_one_skill_inventory_extracts_exact_bytes(self):
        archive = self.kit()
        target = self.root / 'output'
        inventory = handoff.extract(archive, target, skill=True)
        self.assertEqual(inventory['skill_count'], 1)
        self.assertEqual(len(list(target.rglob('SKILL.md'))), 1)
        self.assertEqual((target / handoff.SKILL / 'SKILL.md').read_bytes(),
                         b'---\nname: agent-ffmpeg-local-editor\n---\nfixture only\n')

    def test_changed_skill_bytes_fail_before_any_destination(self):
        archive = self.kit(bad_digest=True)
        target = self.root / 'output'
        with self.assertRaises(ValueError):
            handoff.extract(archive, target, skill=True)
        self.assertFalse(target.exists())

    def test_second_public_skill_is_rejected(self):
        archive = self.kit(second_skill=True)
        target = self.root / 'output'
        with self.assertRaises(ValueError):
            handoff.extract(archive, target, skill=True)
        self.assertFalse(target.exists())

    def test_existing_destination_is_preserved(self):
        archive = self.archive([('file', b'new')])
        target = self.root / 'output'
        target.mkdir()
        (target / 'accepted').write_bytes(b'previous')
        with self.assertRaises(ValueError):
            handoff.extract(archive, target)
        self.assertEqual((target / 'accepted').read_bytes(), b'previous')

    def test_duplicate_and_nonfinite_evidence_json_is_rejected(self):
        for value in (b'{"status":"passed","status":"failed"}', b'{"size":NaN}', b'{"size":Infinity}', b'[]'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                handoff.decode(value)

    def test_running_or_partial_source_suite_cannot_build_a_kit(self):
        freeze = dict(status='frozen', cli_version=handoff.VERSION, file_hashes={}, formal_guard={})
        args = SimpleNamespace(freeze_run='fixture', tests_run='fixture', run='fixture')
        for status, completed, discovered in [('running', 3, 10), ('passed', 3, 10)]:
            proof = dict(status=status, cli_version=handoff.VERSION, file_hashes={}, tests=completed,
                         discovered_tests=discovered, failures=0, errors=0, skipped=0)
            with (patch.object(handoff, 'source_unchanged'), patch.object(handoff, 'guards_equal', return_value=True),
                  patch.object(handoff, 'load', side_effect=[copy.deepcopy(freeze), proof]),
                  patch.object(handoff, 'begin') as begin, self.assertRaises(ValueError)):
                handoff.kit(args)
            begin.assert_not_called()

    def test_local_output_cannot_escape_the_project(self):
        with self.assertRaises(ValueError):
            handoff.local(handoff.ROOT.parent / 'unowned-output')

    def test_publishing_rejects_an_unreviewed_extra_attachment(self):
        directory = self.root / 'assets'
        directory.mkdir()
        names = ['app.zip', 'skill.zip', 'RELEASE-NOTES.md', 'QUICKSTART.md', 'QUICKSTART.en.md', 'QUICKSTART.zh-TW.md']
        rows = []
        for name in names:
            path = directory / name
            path.write_bytes(b'explicit contract fixture')
            rows.append(dict(name=name, bytes=path.stat().st_size, sha256=handoff.sha(path)))
        (directory / 'SHA256SUMS.txt').write_text(''.join(row['sha256'] + '  ' + row['name'] + '\n' for row in rows), encoding='utf-8')
        rows.append(dict(name='SHA256SUMS.txt', bytes=(directory / 'SHA256SUMS.txt').stat().st_size,
                         sha256=handoff.sha(directory / 'SHA256SUMS.txt')))
        handoff.save(directory / 'release-lock.json', dict(format=handoff.RELEASE_LOCK_FORMAT,
            repository=publisher.REPOSITORY, tag=handoff.TAG, cli_version=handoff.VERSION,
            runtime_release=handoff.RELEASE, public_model_media_included=False, assets=rows))
        (directory / 'unreviewed.wav').write_bytes(b'never upload')
        with self.assertRaisesRegex(ValueError, 'unreviewed attachments'):
            publisher.validate_files(directory)

    def test_authenticated_http_redirect_is_refused(self):
        with self.assertRaises(ValueError):
            publisher.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://unrelated.invalid/')

    def test_process_reuse_is_checked_by_creation_time(self):
        identity = process_identity(os.getpid())
        self.assertTrue(same_process(identity))
        stale = dict(identity, creation_filetime=identity['creation_filetime'] + 1)
        self.assertFalse(same_process(stale))

    def test_native_git_uses_the_available_executable_and_correct_checkout(self):
        self.assertTrue(publisher.GIT.is_file())
        root = publisher.git('rev-parse', '--show-toplevel').decode('utf-8').strip()
        self.assertEqual(Path(root).resolve(), handoff.ROOT.resolve())

    def test_explicit_publishing_token_never_opens_credential_stores(self):
        with (patch.dict(publisher.os.environ, {'GITHUB_TOKEN': 'fixture-explicit-token',
                                               'GH_TOKEN': 'fixture-other-token'}, clear=True),
              patch.object(publisher, 'native_gh_credential') as native,
              patch.object(publisher, 'git') as git):
            self.assertEqual(publisher.credential(), 'fixture-explicit-token')
        native.assert_not_called()
        git.assert_not_called()

    def test_native_gh_store_precedes_unusable_legacy_git_credential(self):
        with (patch.dict(publisher.os.environ, {}, clear=True),
              patch.object(publisher, 'native_gh_credential', return_value='fixture-native-token') as native,
              patch.object(publisher, 'git') as git):
            self.assertEqual(publisher.credential(), 'fixture-native-token')
        native.assert_called_once_with()
        git.assert_not_called()

    def test_legacy_helper_remains_available_without_native_gh_credential(self):
        with (patch.dict(publisher.os.environ, {}, clear=True),
              patch.object(publisher, 'native_gh_credential', return_value=None),
              patch.object(publisher, 'git', return_value=b'host=github.com\npassword=fixture-legacy-token\n') as git):
            self.assertEqual(publisher.credential(), 'fixture-legacy-token')
        git.assert_called_once_with('credential', 'fill',
            input=b'protocol=https\nhost=github.com\n\n', timeout=30)

    def test_native_gh_store_decodes_utf8_and_utf16_token_formats(self):
        token = 'gho_fixture_only_not_a_real_credential'
        for raw in (token.encode('utf-8'), token.encode('utf-16-le')):
            with self.subTest(encoding_size=len(raw)):
                self.assertEqual(publisher.stored_github_token(raw), token)

    def test_malformed_or_oversized_stored_credentials_are_not_logged(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            for raw in (None, b'', b'\xff', b'x' * 16385, b'{"token":"fixture"}',
                        b'gho_fixture_with\nembedded_newline', b'gho_short'):
                with self.subTest(input_type=type(raw).__name__):
                    self.assertIsNone(publisher.stored_github_token(raw))
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(stderr.getvalue(), '')

    def test_local_only_validation_never_reads_credentials_or_publishes(self):
        stdout = io.StringIO()
        argv = ['publish_delivery66.py', '--assets', str(self.root),
                '--source-commit', '0' * 40, '--run', 'fixture']
        with (patch.object(publisher.sys, 'argv', argv),
              patch.object(publisher, 'validate_files', return_value={'assets': []}),
              patch.object(publisher, 'bind_commit'),
              patch.object(handoff, 'begin', return_value=self.root / 'proof'),
              patch.object(handoff, 'save') as save,
              patch.object(publisher, 'credential') as credential,
              patch.object(publisher, 'publish') as publish,
              redirect_stdout(stdout)):
            publisher.main()
        credential.assert_not_called()
        publish.assert_not_called()
        self.assertEqual(save.call_args.args[1]['status'], 'validated-not-published')

    def release_source_fixture(self):
        home = self.root / 'reviewed-source'
        home.mkdir()
        product = ('product/src/ai_ad_editor/__init__.py', 'product/tests/test_fixture.py')
        skill = (handoff.SKILL + 'SKILL.md', handoff.SKILL + 'scripts/run.ps1')
        packaging_names = round_runner.packaging_source_names()
        names = [*product, *sorted(handoff.SOURCE_TOOLS), *packaging_names, *skill, handoff.MANIFEST,
                 handoff.CONFIG, *handoff.SOURCE_READMES]
        for name in names:
            path = home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('# Explicit source-binding fixture; never executed: ' + name + '\r\n').encode())
        (home / '.gitattributes').write_bytes(
            b'*.py text eol=lf\n*.md text eol=lf\n*.ps1 text eol=lf\n*.json text eol=lf\n')
        context = dict(freeze=dict(status='frozen', cli_version=handoff.VERSION,
            file_hashes={name: handoff.sha(home / name) for name in product},
            delivery_tool_files={name: handoff.sha(home / name) for name in handoff.SOURCE_TOOLS},
            packaging_source_files={name: handoff.sha(home / name) for name in packaging_names},
            skill_validator=round_runner.skill_validator_pin()),
            spec=dict(files=[dict(path=name, sha256=handoff.sha(home / name))
                             for name in (*skill, handoff.MANIFEST, handoff.CONFIG)]))
        return home, context, self.release_source_lock(home, context)

    def release_source_lock(self, home, context):
        with patch.object(handoff, 'ROOT', home):
            binding = handoff.capture_release_source(context)
        descriptor = home / 'docs/validation/reviewed-descriptor.json'
        handoff.save(descriptor, context['spec'])
        return dict(format=handoff.RELEASE_LOCK_FORMAT, frozen_source=context['freeze']['file_hashes'],
                    source_binding=binding, frozen_packaging_sources=context['freeze']['packaging_source_files'],
                    descriptor=str(descriptor), descriptor_sha256=handoff.sha(descriptor))

    @contextmanager
    def release_git_environment(self, home):
        environment = {name: value for name, value in os.environ.items()
                       if not name.upper().startswith('GIT_')}
        with patch.object(handoff, 'ROOT', home), patch.dict(os.environ, environment, clear=True):
            yield

    def commit_release_source_fixture(self, home, lock, *, omit=None):
        # Native Git only, inside an owned E: fixture. No hooks, models or network.
        with self.release_git_environment(home):
            publisher.git('init', '--quiet', '--initial-branch=main', '--object-format=sha1', '--template=')
            publisher.git('config', 'core.autocrlf', 'false')
            publisher.git('config', 'core.safecrlf', 'false')
            publisher.git('remote', 'add', 'origin', publisher.REMOTE)
            names = sorted(publisher.reviewed_source(lock))
            publisher.git('add', '-f', '--', '.gitattributes', *(name for name in names if name != omit))
            tree = publisher.git('write-tree').decode().strip()
            commit = publisher.git('-c', 'user.name=Agent Editor Kit contract',
                '-c', 'user.email=contract@example.invalid', 'commit-tree', tree,
                input=b'Explicit local source-binding contract fixture\n').decode().strip()
            publisher.git('update-ref', 'refs/heads/main', commit)
        return commit

    def test_release_source_binding_covers_public_roles_and_rejects_missing_or_private_rows(self):
        home, context, lock = self.release_source_fixture()
        binding = lock['source_binding']
        files = handoff.release_source_files(binding, lock['frozen_source'], context['spec']['files'], context['freeze']['packaging_source_files'])
        self.assertEqual(set(files), set(context['freeze']['file_hashes']) | handoff.SOURCE_TOOLS
            | {row['path'] for row in context['spec']['files'] if row['path'] != handoff.CONFIG}
            | set(handoff.SOURCE_READMES) | set(context['freeze']['packaging_source_files']))
        self.assertNotIn(handoff.CONFIG, files)
        self.assertFalse(binding['local_runtime_config_committed'])
        for role, rows in binding['groups'].items():
            for name in rows:
                changed = copy.deepcopy(binding)
                del changed['groups'][role][name]
                with self.subTest(role=role, omitted=name), self.assertRaises(ValueError):
                    handoff.release_source_files(changed, lock['frozen_source'], context['spec']['files'], context['freeze']['packaging_source_files'])
        changed = copy.deepcopy(binding)
        changed['format'] = 'agent-editor-release-source-legacy'
        with self.assertRaises(ValueError):
            handoff.release_source_files(changed, lock['frozen_source'], context['spec']['files'], context['freeze']['packaging_source_files'])
        changed = copy.deepcopy(binding)
        changed['local_runtime_config_committed'] = True
        with self.assertRaises(ValueError):
            handoff.release_source_files(changed, lock['frozen_source'], context['spec']['files'], context['freeze']['packaging_source_files'])
        for name in (handoff.CONFIG, handoff.SKILL + 'SKILL.md'):
            changed = copy.deepcopy(binding)
            frozen = dict(lock['frozen_source'], **{name: handoff.sha(home / name)})
            changed['groups']['product'] = frozen
            with self.subTest(injected=name), self.assertRaises(ValueError):
                handoff.release_source_files(changed, frozen, context['spec']['files'], context['freeze']['packaging_source_files'])

    def test_release_source_capture_and_frozen_tools_reject_byte_drift(self):
        home, context, lock = self.release_source_fixture()
        names = [next(iter(context['freeze']['file_hashes'])), sorted(handoff.SOURCE_TOOLS)[0],
                 handoff.SKILL + 'SKILL.md', handoff.MANIFEST]
        for name in names:
            path, original = home / name, (home / name).read_bytes()
            try:
                path.write_bytes(original + b'# Changed after acceptance\n')
                with (self.subTest(changed=name), patch.object(handoff, 'ROOT', home),
                      self.assertRaisesRegex(ValueError, 'Reviewed release source changed')):
                    handoff.capture_release_source(context)
                if name in context['freeze']['file_hashes'] or name in handoff.SOURCE_TOOLS:
                    with patch.object(handoff, 'ROOT', home), self.assertRaisesRegex(ValueError, 'Frozen'):
                        handoff.source_unchanged(context['freeze'])
            finally:
                path.write_bytes(original)

    def test_reviewed_source_commit_accepts_actual_git_line_normalization(self):
        home, context, lock = self.release_source_fixture()
        commit = self.commit_release_source_fixture(home, lock)
        name = handoff.SKILL + 'SKILL.md'
        with self.release_git_environment(home):
            publisher.bind_commit(lock, commit)
            blob = publisher.git('show', commit + ':' + name)
        raw = (home / name).read_bytes()
        self.assertNotEqual(raw, blob)
        self.assertEqual(raw.replace(b'\r\n', b'\n'), blob)

    def test_reviewed_source_commit_rejects_each_uncommitted_public_surface(self):
        home, context, lock = self.release_source_fixture()
        commit = self.commit_release_source_fixture(home, lock)
        names = [sorted(handoff.SOURCE_TOOLS)[0], handoff.SKILL + 'SKILL.md',
                 handoff.MANIFEST, *handoff.SOURCE_READMES]
        for name in names:
            path, original = home / name, (home / name).read_bytes()
            changed = copy.deepcopy(context)
            try:
                path.write_bytes(original + b'# New reviewed bytes not present in the commit\n')
                if name in changed['freeze']['delivery_tool_files']:
                    changed['freeze']['delivery_tool_files'][name] = handoff.sha(path)
                for row in changed['spec']['files']:
                    if row['path'] == name:
                        row['sha256'] = handoff.sha(path)
                updated = self.release_source_lock(home, changed)
                with (self.subTest(uncommitted=name), self.release_git_environment(home),
                      self.assertRaisesRegex(ValueError, 'Source commit differs')):
                    publisher.bind_commit(updated, commit)
            finally:
                path.write_bytes(original)
                self.release_source_lock(home, context)

    def test_reviewed_source_commit_rejects_an_omitted_bound_file(self):
        home, context, lock = self.release_source_fixture()
        commit = self.commit_release_source_fixture(home, lock, omit=handoff.SKILL + 'SKILL.md')
        with self.release_git_environment(home), self.assertRaisesRegex(ValueError, 'omits reviewed release files'):
            publisher.bind_commit(lock, commit)

    def test_reviewed_source_rejects_raw_drift_when_git_clean_object_is_equal(self):
        home, context, lock = self.release_source_fixture()
        commit = self.commit_release_source_fixture(home, lock)
        name = handoff.SKILL + 'SKILL.md'
        with self.release_git_environment(home):
            before = publisher.git('hash-object', '--stdin-paths', input=(name + '\n').encode())
            path = home / name
            path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
            after = publisher.git('hash-object', '--stdin-paths', input=(name + '\n').encode())
            self.assertEqual(before, after)
            with self.assertRaisesRegex(ValueError, 'Reviewed release source changed'):
                publisher.bind_commit(lock, commit)

    def package_stage_fixture(self, home):
        source = home / 'staged'
        skill = source / handoff.SKILL / 'SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_bytes(b'# Explicit packaging fixture; never registered or executed.\n')
        handoff.save(source / handoff.MANIFEST, dict(release=handoff.RELEASE, cli_version=handoff.VERSION,
            skill_count=1, module_count=17, files=[dict(path=handoff.SKILL + 'SKILL.md',
            bytes=skill.stat().st_size, sha256=handoff.sha(skill))]))
        return source

    def package_native_fixture(self, source, output, ref):
        environment = dict(os.environ, TEMP=str(self.root), TMP=str(self.root), TMPDIR=str(self.root),
                           PYTHONDONTWRITEBYTECODE='1')
        return subprocess.run([round_runner.sys.executable, '-E', '-B', '-u', '-X', 'utf8',
            str(handoff.ROOT / 'scripts/package_community_skill.py'), '--output', str(output),
            '--skill-source', str(source), '--archive-name', 'fixture.zip', '--source-ref', ref],
            cwd=handoff.ROOT, env=environment, capture_output=True, text=True, encoding='utf-8',
            timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)

    def test_native_packager_records_source_inputs_and_immutable_documentation_ref(self):
        source = self.package_stage_fixture(self.root)
        result = self.package_native_fixture(source, self.root / 'native-package', handoff.TAG)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        expected = {name: pin for name, pin in round_runner.packaging_sources().items()
                    if name != 'docs/product/DELIVERY_CONTROLLER.md'}
        self.assertEqual(report['packaging_source_files'], expected)
        self.assertEqual(report['documentation_source_ref'], handoff.TAG)
        self.assertNotIn(handoff.CONFIG, expected)
        with zipfile.ZipFile(report['archive']) as zipped:
            inventory = handoff.decode(zipped.read('KIT-FILES.json'))
            self.assertEqual(inventory['packaging_source_files'], expected)
            self.assertEqual(inventory['documentation_source_ref'], handoff.TAG)
            guides = b'\n'.join(zipped.read(name) for name in zipped.namelist() if name.startswith('docs/'))
            self.assertIn(('/blob/' + handoff.TAG + '/').encode(), guides)
            for guide in ('COMMUNITY_LOCAL_DELIVERY.md', 'COMMUNITY_MATERIALS.md',
                          'COMMUNITY_MATERIALS.en.md', 'COMMUNITY_MATERIALS.zh-TW.md'):
                current = zipped.read('docs/product/' + guide).decode('utf-8').split('\n\n', 2)[1]
                self.assertIn('CLI' + handoff.VERSION, current)
                self.assertIn(handoff.RELEASE, current)
            self.assertEqual(report['packaging_source_files'], expected)

    def test_packager_rejects_invalid_documentation_refs_before_outputs(self):
        source = self.package_stage_fixture(self.root)
        for index, ref in enumerate(('../escape', 'other/branch', 'v0.1.0-alpha.4/../main', 'https://invalid/', '')):
            output = self.root / ('invalid-ref-' + str(index))
            with self.subTest(ref=ref):
                result = self.package_native_fixture(source, output, ref)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Use main, a full reviewed commit or a release tag', result.stderr)
                self.assertFalse(output.exists())

    def test_packager_missing_or_changing_sources_fail_before_output_publication(self):
        script = handoff.ROOT / 'scripts/package_community_skill.py'
        for mode in ('missing', 'changed'):
            with self.subTest(mode=mode):
                home = self.root / mode
                home.mkdir()
                namespace = round_runner.runpy.run_path(str(script), run_name='packaging_fault_contract')
                globals_ = namespace['main'].__globals__
                globals_['ROOT'] = home
                for name in namespace['source_names']():
                    path = home / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b'# Explicit input-corpus fixture; helpers are never executed.\n')
                source = self.package_stage_fixture(home)
                guide = home / 'docs/product' / namespace['PACKAGE_GUIDES'][0]
                output = home / 'output'
                argv = [str(script), '--output', str(output), '--skill-source', str(source),
                        '--archive-name', 'fixture.zip', '--source-ref', handoff.TAG]
                if mode == 'missing':
                    guide.unlink()
                    with patch.object(round_runner.sys, 'argv', argv):
                        with self.assertRaises(OSError):
                            namespace['main']()
                else:
                    original = namespace['source_inventory']
                    calls = []
                    def observed_inputs():
                        pins = original()
                        calls.append(pins)
                        if len(calls) == 1:
                            guide.write_bytes(b'# Changed while packaging was reading its declared inputs.\n')
                        return pins
                    with (patch.object(round_runner.sys, 'argv', argv),
                          patch.dict(globals_, source_inventory=observed_inputs),
                          self.assertRaisesRegex(ValueError, 'changed before output publication')):
                        namespace['main']()
                    self.assertEqual(len(calls), 2)
                self.assertFalse(output.exists())

    def test_changed_packaging_input_rejects_kit_before_creating_outputs(self):
        home, context, lock = self.release_source_fixture()
        guide = home / 'docs/product/DELIVERY_CONTROLLER.md'
        guide.write_bytes(guide.read_bytes() + b'# Unfrozen documentation edit\n')
        args = SimpleNamespace(freeze_run='fixture', tests_run='fixture', run='fixture')
        with (patch.object(handoff, 'ROOT', home),
              patch.object(handoff, 'load', return_value=context['freeze']),
              patch.object(handoff, 'begin') as begin,
              self.assertRaisesRegex(ValueError, 'Frozen packaging input changed')):
            handoff.kit(args)
        begin.assert_not_called()

    def test_reviewed_commit_rejects_uncommitted_packaging_helpers_license_and_guides(self):
        home, context, lock = self.release_source_fixture()
        commit = self.commit_release_source_fixture(home, lock)
        for name in ('register-agent-ffmpeg-local-skills.ps1', 'scripts/install_community_pack.py',
                     'LICENSE', 'docs/product/COMMUNITY_LOCAL_DELIVERY.md', 'docs/product/DELIVERY_CONTROLLER.md'):
            path, original = home / name, (home / name).read_bytes()
            try:
                path.write_bytes(original + b'# Accepted packaging input not present in the source commit\n')
                changed = copy.deepcopy(context)
                changed['freeze']['packaging_source_files'][name] = handoff.sha(path)
                updated = self.release_source_lock(home, changed)
                with (self.subTest(uncommitted=name), self.release_git_environment(home),
                      self.assertRaisesRegex(ValueError, 'Source commit differs')):
                    publisher.bind_commit(updated, commit)
            finally:
                path.write_bytes(original)
                self.release_source_lock(home, context)

    def test_changed_skill_validator_rejects_staging_before_any_output(self):
        validator = self.root / 'validator.py'
        validator.write_bytes(b'# Explicit source-pin fixture; never executed.\n')
        pin = handoff.sha(validator)
        with (patch.object(round_runner, 'SKILL_VALIDATOR', validator),
              patch.object(round_runner, 'SKILL_VALIDATOR_SHA256', pin)):
            frozen = dict(skill_validator=round_runner.skill_validator_pin())
            validator.write_bytes(b'# Changed validator must not authorize staged Skill files.\n')
            with (patch.object(round_runner, 'proof') as begin,
                  self.assertRaisesRegex(ValueError, 'validator differs')):
                round_runner.stage(SimpleNamespace(run='fixture'), frozen)
            begin.assert_not_called()

    def dependency_fixture(self):
        package = self.root / 'site/ai_ad_editor'
        package.mkdir(parents=True)
        (package / '__init__.py').write_bytes(b'# Explicit dependency-protocol fixture only.\n')
        modules = {}
        for name, version in [('numpy', '2.4.2'), ('PIL', '12.1.0'),
                              ('cv2', '5.0.0.93'), ('jsonschema', '4.26.0')]:
            path = self.root / (name + '.py')
            path.write_bytes(b'# Not imported or used for media processing.\n')
            modules[name] = dict(version=version, file=str(path), binaries=[])
        for name, relative in [('numpy', 'numpy-native/linalg/sample.pyd'),
                               ('cv2', 'cv2-native/videoio.dll')]:
            binary = self.root / relative
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'Explicit inventory fixture; never loaded.\n')
            modules[name]['binaries'].append(str(binary))
        record = dict(python=round_runner.sys.executable, isolated=1, dependency_scope='application',
            application_file=str(package / '__init__.py'),
            application_version=round_runner.VERSION, modules=modules)
        return package, record

    def test_isolated_dependency_preflight_requires_opencv_and_compatible_core_versions(self):
        package, record = self.dependency_fixture()
        pins = round_runner.dependency_probe_files(record, package)
        self.assertIn(str(Path(round_runner.sys.executable).resolve()), pins)
        self.assertEqual(len(pins), 7)
        for name in ('numpy', 'cv2'):
            binary = Path(record['modules'][name]['binaries'][0])
            self.assertEqual(pins[str(binary.resolve())], round_runner.sha(binary))
        bare = dict(record, dependency_scope='bare-worker', application_file=None,
                    application_version=None)
        self.assertEqual(round_runner.dependency_probe_files(bare, None), pins)
        with self.assertRaisesRegex(AssertionError, 'injected an application'):
            round_runner.dependency_probe_files(dict(bare, application_file=record['application_file']), None)
        with self.assertRaisesRegex(AssertionError, 'scope'):
            round_runner.dependency_probe_files(bare, package)
        missing = copy.deepcopy(record)
        del missing['modules']['cv2']
        with self.assertRaisesRegex(AssertionError, 'incomplete'):
            round_runner.dependency_probe_files(missing, package)
        for name, version in [('numpy', '2.4.1'), ('PIL', '13.0.0'),
                              ('cv2', '3.4.0'), ('jsonschema', '4.25.0')]:
            altered = copy.deepcopy(record)
            altered['modules'][name]['version'] = version
            with self.subTest(dependency=name), self.assertRaisesRegex(AssertionError, 'Incompatible'):
                round_runner.dependency_probe_files(altered, package)

    def test_isolated_dependency_preflight_rejects_another_application_or_python(self):
        package, record = self.dependency_fixture()
        for changes, reason in [({'isolated': 0}, 'not isolated'),
                                ({'python': str(self.root / 'other-python.exe')}, 'another Python'),
                                ({'application_version': '0.1.63'}, 'another application'),
                                ({'application_file': str(self.root / 'other/__init__.py')}, 'another application')]:
            with self.subTest(changes=changes), self.assertRaisesRegex(AssertionError, reason):
                round_runner.dependency_probe_files(dict(record, **changes), package)

    def test_live_issue_journal_preserves_subtests_and_continues_the_whole_suite(self):
        journal = self.root / 'issues.jsonl'
        observed = []
        with patch.object(round_runner.sys, 'path',
                          [str(handoff.ROOT / 'product/src'), *round_runner.sys.path]):
            from ai_ad_editor.errors import AppError

        class DeliberateProblems(unittest.TestCase):
            def error(self):
                raise AppError('FIXTURE_WORKER_FAILED', 'fixture primary error',
                               cause='fixture missing dependency details')

            def failure(self):
                self.fail('fixture primary assertion')

            def subtest_failure(self):
                with self.subTest(kind='assertion'):
                    self.fail('fixture subtest assertion')

            def subtest_error(self):
                with self.subTest(kind='exception'):
                    raise ValueError('fixture subtest error')

            def later_test(self):
                rows = [json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines()]
                observed.extend(rows)
                self.assertEqual([row['event'] for row in rows],
                    ['result-created', 'error', 'failure', 'subtest-failure', 'subtest-error'])

        suite = unittest.TestSuite(DeliberateProblems(name) for name in
            ['error', 'failure', 'subtest_failure', 'subtest_error', 'later_test'])
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=2,
            resultclass=lambda *a, **kw: round_runner.LiveRegressionResult(
                *a, event_path=journal, **kw)).run(suite)
        self.assertEqual(result.testsRun, 5)
        self.assertEqual(len(result.errors), 2)
        self.assertEqual(len(result.failures), 2)
        self.assertEqual(result.skipped, [])
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(len(observed), 5)
        self.assertTrue(all(row['traceback'] and row['test_id'] for row in observed[1:]))
        self.assertEqual(observed[1]['application_error'],
            dict(code='FIXTURE_WORKER_FAILED', cause='fixture missing dependency details'))

    def basic_configuration_fixture(self):
        home = self.root / 'configuration-kit'
        script = home / 'scripts/activate_community_runtime.py'
        script.parent.mkdir(parents=True)
        script.write_bytes((handoff.ROOT / 'scripts/activate_community_runtime.py').read_bytes())
        skill = home / 'skills/agent-ffmpeg-local-editor/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_bytes(b'# Explicit configurator inventory fixture only.\n')
        expected = 'sha256:' + '0' * 64
        manifest = dict(release=handoff.RELEASE, manifest_sha256=expected,
            files=[dict(path=skill.relative_to(home).as_posix(), sha256=handoff.sha(skill))])
        (home / 'agent-ffmpeg-local-install-manifest.json').write_bytes(handoff.encoded(manifest))
        installed = self.root / 'basic-installed'
        installed.mkdir()
        (installed / 'receipt.json').write_bytes(handoff.encoded(dict(manifest_sha256=expected)))
        # This is a rejecting CLI fixture, never a model inference implementation.
        (installed / 'run.py').write_text(
            'from pathlib import Path\n'
            'Path(__file__).with_name("model-verification-called").write_text("called")\n'
            'print(\'{"ok": false}\')\n'
            'raise SystemExit(7)\n', encoding='utf-8')
        directory = home / 'local/agent-ffmpeg'
        directory.mkdir(parents=True)
        previous = {
            'runtime.json': handoff.encoded(dict(release='prior',
                semantic_config=str(self.root / 'missing-foreign-machine/profile.json'))),
            'community-runtime.json': b'{"voice":{"cpu_pack":"E:/foreign-machine/voice"}}\n'}
        for name, raw in previous.items():
            (directory / name).write_bytes(raw)
        return home, installed, previous

    def configure_fixture(self, home, installed, options):
        environment = dict(os.environ, TEMP=str(self.root), TMP=str(self.root),
                           TMPDIR=str(self.root), PYTHONDONTWRITEBYTECODE='1')
        return subprocess.run([round_runner.sys.executable, '-E', '-B', '-u', '-X', 'utf8',
            str(home / 'scripts/activate_community_runtime.py'), '--installed', str(installed),
            *map(str, options)], cwd=handoff.ROOT, env=environment,
            capture_output=True, text=True, encoding='utf-8', timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW)

    def test_base_only_native_configuration_backs_up_and_replaces_foreign_model_paths(self):
        home, installed, previous = self.basic_configuration_fixture()
        result = self.configure_fixture(home, installed, ['--base-only'])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'configured')
        self.assertEqual(report['configuration_mode'], 'base-only')
        self.assertEqual(report['verified_packs'], [])
        self.assertFalse(report['model_configuration_requested'])
        self.assertFalse(report['model_verification_performed'])
        configuration = handoff.load(home / 'local/agent-ffmpeg/runtime.json')
        self.assertEqual(configuration['installed_directory'], str(installed.resolve()))
        self.assertEqual(configuration['launcher_sha256'], handoff.sha(installed / 'run.py'))
        self.assertNotIn('semantic_config', configuration)
        self.assertEqual(handoff.load(home / 'local/agent-ffmpeg/community-runtime.json'), {})
        evidence = Path(report['evidence'])
        for name, raw in previous.items():
            self.assertEqual((evidence / ('previous-' + name)).read_bytes(), raw)
        self.assertFalse(list(evidence.glob('*.stdout.json')))
        self.assertFalse((installed / 'model-verification-called').exists())

    def test_basic_configuration_rejects_ambiguous_or_model_specific_arguments_before_writes(self):
        home, installed, previous = self.basic_configuration_fixture()
        cases = [[], ['--base-only', '--packs', self.root],
            ['--base-only', '--voice-cuda-lib', self.root],
            ['--base-only', '--translation-cuda-lib', self.root],
            ['--base-only', '--semantic-config', self.root / 'profile.json']]
        for options in cases:
            with self.subTest(options=options):
                result = self.configure_fixture(home, installed, options)
                self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
                for name, raw in previous.items():
                    self.assertEqual((home / 'local/agent-ffmpeg' / name).read_bytes(), raw)
        self.assertFalse((home / 'local/agent-ffmpeg/activations').exists())
        self.assertFalse((installed / 'model-verification-called').exists())

    def test_base_only_configuration_rejects_an_unmatched_installation_before_writes(self):
        home, installed, previous = self.basic_configuration_fixture()
        (installed / 'receipt.json').write_bytes(handoff.encoded(
            dict(manifest_sha256='sha256:' + '1' * 64)))
        result = self.configure_fixture(home, installed, ['--base-only'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not match this reviewed Skill kit', result.stderr)
        for name, raw in previous.items():
            self.assertEqual((home / 'local/agent-ffmpeg' / name).read_bytes(), raw)
        self.assertFalse((installed / 'model-verification-called').exists())

    def test_model_configuration_still_requires_installed_pack_verification(self):
        home, installed, previous = self.basic_configuration_fixture()
        packs = self.root / 'empty-packs'
        packs.mkdir()
        result = self.configure_fixture(home, installed, ['--packs', packs])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Model verification failed', result.stderr)
        self.assertTrue((installed / 'model-verification-called').exists())
        for name, raw in previous.items():
            self.assertEqual((home / 'local/agent-ffmpeg' / name).read_bytes(), raw)



if __name__ == '__main__':
    unittest.main(verbosity=2)
