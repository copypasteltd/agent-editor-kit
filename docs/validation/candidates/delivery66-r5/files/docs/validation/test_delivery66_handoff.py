"""Adversarial delivery-tool contracts; no model, registration or public writes."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

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
        handoff.save(directory / 'release-lock.json', dict(format='agent-editor-reviewed-release-v1',
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
