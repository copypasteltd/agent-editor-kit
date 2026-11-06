"""Adversarial delivery admission fixtures, without product/model execution."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import portrait67_delivery as delivery


class DeliveryAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=delivery.LOCAL, prefix='delivery-contract-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.args = types.SimpleNamespace(phase_run='r1', contracts_run='r1', tests_run='r1', candidate_run='r1',
            stage_run='r1', native_run='r1', music_run='r1', package_run='r1', descriptor_run='r1')
        self.source = self.base / 'source'
        self.installed = self.base / 'installed'
        self.home = self.base / 'stage'
        for folder in (self.source, self.installed / 'site/ai_ad_editor', self.home):
            folder.mkdir(parents=True)
        for folder in (self.source, self.installed / 'site/ai_ad_editor'):
            (folder / '__init__.py').write_text("VERSION = '0.1.67'\n", encoding='utf-8')
        self.archive = self.base / 'application.zip'
        self.archive.write_bytes(b'fixture archive, never installed')
        self.pins = {'__init__.py': delivery.sha(self.source / '__init__.py')}
        self.frozen = dict(file_hashes={'fixture': 'frozen'})
        self.reports = {}
        self.put('delivery-code-phase', dict(status='fixture'))
        self.put('delivery-contracts', dict(status='passed', failures=0, errors=0, skipped=0,
            tests=17, discovered_tests=17,
            code_phase_sha256=delivery.sha(self.path('delivery-code-phase'))))
        regression = dict(status='passed', cli_version='0.1.67', tests=4154, discovered_tests=4154,
            file_hashes=self.frozen['file_hashes'], failures=0, errors=0, skipped=0,
            original_assertions_preserved=True, frozen_equal=True, source_fallback=False)
        self.put('source-all', regression)
        self.put('installed-all', regression)
        self.put('candidate', dict(status='installed-and-byte-verified', cli_version='0.1.67',
            application_files=self.pins, installed=str(self.installed), archive=str(self.archive),
            archive_sha256=delivery.sha(self.archive)))
        skills = {}
        for i in range(96):
            name = 'skills/agent-ffmpeg-local-editor/references/' + str(i) + '.md'
            path = self.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Fixture ' + str(i), encoding='utf-8')
            skills[name] = delivery.sha(path)
        self.put('skill-entry', dict(status='passed', cli_version='0.1.67', home=str(self.home),
            application_files=self.pins, source_fallback=False, actual_PowerShell_entry=True, skill_files=skills))
        self.put('native-case', dict(status='failed', cli_version='0.1.67', source_fallback=False,
            actual_installed_PowerShell_entry=True, source_mother_unchanged=True,
            results=dict(faults=dict(cancel={}, conflict={}, timeout={}))))
        fake_harness = types.SimpleNamespace(SOURCE=self.source)
        fake_helper = types.SimpleNamespace(local=lambda path: Path(path).resolve(strict=True))
        self.patch_base = patch.object(delivery, 'BASE', self.base)
        self.patch_guard = patch.object(delivery, 'code_guard', return_value=(fake_harness, fake_helper, self.frozen))
        self.patch_base.start()
        self.patch_guard.start()
        self.addCleanup(self.patch_base.stop)
        self.addCleanup(self.patch_guard.stop)

    def path(self, kind):
        return self.base / (kind + '-r1') / 'verification.json'

    def put(self, kind, value):
        path = self.path(kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(copy.deepcopy(value)), encoding='utf-8')

    def modify(self, kind, **changes):
        value = json.loads(self.path(kind).read_bytes())
        value.update(changes)
        self.put(kind, value)

    def rejected(self, message):
        with self.assertRaisesRegex(ValueError, message):
            delivery.ready(self.args)
        # Admission never creates a delivery journal or publishes a Skill.
        self.assertFalse((self.base / 'delivery-journal.json').exists())

    def test_running_source_is_not_a_terminal(self):
        self.modify('source-all', status='running')
        self.rejected('original complete')

    def test_partial_or_skipped_suite_cannot_authorize_delivery(self):
        for changes in (dict(tests=4153), dict(discovered_tests=4153), dict(skipped=1), dict(errors=True)):
            with self.subTest(changes=changes):
                before = json.loads(self.path('source-all').read_bytes())
                self.modify('source-all', **changes)
                self.rejected('original complete')
                self.put('source-all', before)

    def test_old_version_and_weakened_assertions_are_rejected(self):
        for changes in (dict(cli_version='0.1.66'), dict(original_assertions_preserved=False), dict(frozen_equal=False)):
            with self.subTest(changes=changes):
                before = json.loads(self.path('source-all').read_bytes())
                self.modify('source-all', **changes)
                self.rejected('original complete')
                self.put('source-all', before)

    def test_installed_source_fallback_is_rejected(self):
        self.modify('installed-all', source_fallback=True)
        self.rejected('source fallback')

    def test_tampered_application_or_archive_is_rejected(self):
        target = self.installed / 'site/ai_ad_editor/__init__.py'
        original = target.read_bytes()
        target.write_bytes(original + b'# changed\n')
        self.rejected('Offline candidate changed')
        target.write_bytes(original)
        self.archive.write_bytes(b'changed archive')
        self.rejected('Offline candidate changed')

    def test_skill_tamper_and_missing_new_file_are_rejected(self):
        target = self.home / 'skills/agent-ffmpeg-local-editor/references/95.md'
        original = target.read_bytes()
        target.write_bytes(b'changed reference')
        self.rejected('96-file candidate')
        target.write_bytes(original)
        staged = json.loads(self.path('skill-entry').read_bytes())
        staged['skill_files'].pop('skills/agent-ffmpeg-local-editor/references/95.md')
        self.put('skill-entry', staged)
        self.rejected('96-file candidate')

    def test_synthetic_contracts_cannot_replace_real_portrait_terminal(self):
        self.rejected('Real installed CUDA portrait')
        self.modify('native-case', status='passed', cli_version='0.1.66')
        self.rejected('Real installed CUDA portrait')

    def test_portrait_faults_and_no_fallback_are_required(self):
        self.modify('native-case', status='passed', source_fallback=True)
        self.rejected('Real installed CUDA portrait')
        self.modify('native-case', source_fallback=False, results=dict(faults=dict(cancel={}, timeout={})))
        self.rejected('Real installed CUDA portrait')

    def test_contract_receipt_is_bound_to_the_frozen_driver(self):
        self.modify('delivery-contracts', code_phase_sha256='0' * 64)
        self.rejected('delivery contract suite')


if __name__ == '__main__':
    unittest.main()
