"""Prepare an entire correction batch without touching the live frozen suite."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/delivery66-20261106-r1'
CANDIDATE = ROOT / 'docs/validation/candidates/delivery66-r2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def replace_once(value, old, new):
    assert value.count(old) == 1, old[:120]
    return value.replace(old, new, 1)


def guard(freeze):
    assert all(sha(ROOT / name) == pin for name, pin in freeze['file_hashes'].items())
    assert all(sha(ROOT / name) == pin for name, pin in freeze['formal_guard'].items())


def prepare():
    freeze = load(BASE / 'freeze-r1/verification.json')
    guard(freeze)
    receipt = CANDIDATE / 'implementation.json'
    assert not receipt.exists()
    mapping = {'delivery.py': 'product/src/ai_ad_editor/delivery.py',
        'capabilities.py': 'product/src/ai_ad_editor/capabilities.py',
        'test_delivery.py': 'product/tests/test_delivery.py',
        'runner.py': 'docs/validation/delivery66.py',
        'DELIVERY_CONTROLLER.md': 'docs/product/DELIVERY_CONTROLLER.md'}
    capability = (ROOT / mapping['capabilities.py']).read_text(encoding='utf-8')
    capability = replace_once(capability, '"capabilities": {', '''"capabilities": {
            'verified_skill_delivery': {
                'status': 'implemented_with_limits', 'protocol': 'agent-editor-skill-delivery-v2',
                'commands': ['delivery.inspect', 'delivery.activate', 'delivery.recover', 'delivery.rollback'],
                'scope': ['one_public_Skill', '17_internal_modules', 'runtime_configuration', 'registration_manifest'],
                'required_gates': ['source-tests', 'installed-tests', 'package-replay', 'skill-entry', 'native-music'],
                'features': ['exact_application_and_Skill_byte_pins', 'actual_CUDA_music_required',
                    'complete_backup_preflight', 'native_lock', 'durable_backups', 'explicit_recovery_and_rollback',
                    'preserve_foreign_user_changes', 'bounded_JSON_and_file_reads', 'dry_run_restore_preflight'],
                'limits': {'files': 512, 'file_bytes': 33554432, 'total_bytes': 134217728},
                'network': False, 'source_fallback': False,
                'unsupported': ['multi_file_atomic_replacement', 'automatic_model_downloads',
                    'clean_host_acceptance', 'automatic_natural_quality_acceptance', 'full_G34_G38_parity']},''')
    (CANDIDATE / 'capabilities.py').write_text(capability, encoding='utf-8', newline='\n')
    tests = (ROOT / mapping['test_delivery.py']).read_text(encoding='utf-8')
    tests = replace_once(tests, "for role in ('source-tests', 'installed-tests', 'package-replay', 'skill-entry'):",
        "for role in ('source-tests', 'installed-tests', 'package-replay', 'skill-entry', 'native-music'):")
    tests = replace_once(tests, 'tests=1, frozen_equal=True', 'tests=1, discovered_tests=1, frozen_equal=True')
    tests = replace_once(tests, 'complete_rendered_RGBA_PCM_equal=True, actual_PowerShell_entry=True)', '''complete_rendered_RGBA_PCM_equal=True, actual_PowerShell_entry=True,
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
            samples = b'\\0' * 16
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
                independent_PCM_sha256='sha256:' + 'b' * 64)''')
    tests = replace_once(tests, 'b\'{"release":"interrupted-transition"}\'', 'b\'{"release":"delivery-switch-in-progress"}\\n\'')
    tests = replace_once(tests, "manifest_row.update(sha256=d.sha(Path(manifest_row['source'])), bytes=Path(manifest_row['source']).stat().st_size)\n        self.save()",
        "manifest_row.update(sha256=d.sha(Path(manifest_row['source'])), bytes=Path(manifest_row['source']).stat().st_size)\n        self.sync_skill_pins()\n        self.save()")
    extra = (CANDIDATE / 'extra_tests.py').read_text(encoding='utf-8').split('\n', 1)[1]
    tests = replace_once(tests, '\n\nclass BoundedMusicProgressTests', '\n' + extra + '\n\nclass BoundedMusicProgressTests')
    (CANDIDATE / 'test_delivery.py').write_text(tests, encoding='utf-8', newline='\n')
    runner = (ROOT / mapping['runner.py']).read_text(encoding='utf-8')
    runner = replace_once(runner, "'--target-format', 'agent-package'", "'--target-format', 'package'")
    runner = replace_once(runner, "historical = load(ROOT / 'docs/validation/evidence/music-loading-20261030-r1/actual-stage1/verification.json')",
        "historical = load(BASE / ('native-music-' + args.music_run) / 'verification.json')")
    runner = replace_once(runner, "historical_generation_cli='0.1.65'", "generation_cli=VERSION")
    runner = replace_once(runner, 'complete_master_WAV_equal=True, complete_generation_recipe_equal=True,',
        "application_files=candidate['application_files'], complete_master_WAV_equal=True, complete_generation_recipe_equal=True,")
    runner = replace_once(runner, "actual_PowerShell_entry=True, source_fallback=False, files=files, formal_activation=False,",
        "actual_PowerShell_entry=True, source_fallback=False, files=files, formal_activation=False,\n        application_files=candidate['application_files'], skill_files={row['path']: row['sha256'] for row in files},")
    runner = replace_once(runner, "call(out, 'delivery-help', [*prefix, 'delivery', '--help'])",
        "call(out, 'delivery-help', [*prefix, 'delivery', '--help'])\n    capabilities = call(out, 'capabilities', [*prefix, 'capabilities'], cli=True)\n    assert capabilities['data']['capabilities']['verified_skill_delivery']['protocol'] == 'agent-editor-skill-delivery-v2'")
    runner = replace_once(runner, '\ndef descriptor(args, freeze):',
        '\n' + (CANDIDATE / 'round_additions.py').read_text(encoding='utf-8') + '\n\ndef descriptor(args, freeze):')
    runner = replace_once(runner, "'skill-entry': BASE / ('skill-entry-' + args.stage_run) / 'verification.json'}",
        "'skill-entry': BASE / ('skill-entry-' + args.stage_run) / 'verification.json',\n        'native-music': BASE / ('native-music-' + args.music_run) / 'verification.json'}")
    runner = replace_once(runner, "'stage', 'package', 'descriptor'))", "'stage', 'music', 'package', 'descriptor'))")
    runner = replace_once(runner, "parser.add_argument('--package-run', default='r1')", "parser.add_argument('--package-run', default='r1')\n    parser.add_argument('--music-run', default='r1')")
    runner = replace_once(runner, 'args.tests_run, args.candidate_run, args.stage_run, args.package_run))',
        'args.tests_run, args.candidate_run, args.stage_run, args.package_run, args.music_run))')
    runner = replace_once(runner, "'stage': stage, 'package': package", "'stage': stage, 'music': music, 'package': package")
    runner = replace_once(runner, '    LOCAL.mkdir(parents=True, exist_ok=True)',
        "    assert (ROOT / 'product/src/ai_ad_editor').is_dir(), 'Apply the complete candidate before running the round tool'\n    LOCAL.mkdir(parents=True, exist_ok=True)")
    (CANDIDATE / 'runner.py').write_text(runner, encoding='utf-8', newline='\n')
    document = (ROOT / mapping['DELIVERY_CONTROLLER.md']).read_text(encoding='utf-8')
    document = document.replace('# Verified local delivery / CLI0.1.66', '# Local delivery candidate / CLI0.1.66')
    document = document.replace('and four independent gates:', 'and five independent gates:')
    document = document.replace('PowerShell entry. A gate', 'PowerShell entry, plus actual CUDA music on this exact application and Skill. A gate')
    document += ('\nThe v2 descriptor requires separate source, installed, replay, Skill-entry and native-music receipts. '
        'Replay uses the newly generated candidate audio. Music receipts bind every application/Skill file, '
        'request and master WAV, all four actual CUDA forward devices, full PCM, placement and cleanup. '
        'Synthetic protocol fixtures do not establish model execution. Malformed fields, missing backups, '
        'Windows aliases, nonfinite JSON and foreign user changes reject before restoration. '
        'Recover/rollback dry runs inspect all backups. v1 descriptors/journals are not silently reinterpreted.\n')
    (CANDIDATE / 'DELIVERY_CONTROLLER.md').write_text(document, encoding='utf-8', newline='\n')
    for name in ('delivery.py', 'capabilities.py', 'test_delivery.py', 'runner.py'):
        compile((CANDIDATE / name).read_bytes(), name, 'exec')
    for name in ('extra_tests.py', 'round_additions.py'):
        compile((CANDIDATE / name).read_bytes(), name, 'exec')
    guard(freeze)
    report = dict(status='complete-correction-code-not-tested', cli_version='0.1.66',
        original_suite_unchanged=True, formal_activation=False, functional_tests_executed=False,
        items=['C01', 'C02', 'C03', 'C04'], mapping=mapping,
        predecessor={target: sha(ROOT / target) for target in mapping.values()},
        files={name: sha(CANDIDATE / name) for name in mapping},
        support_files={name: sha(CANDIDATE / name) for name in ('extra_tests.py', 'round_additions.py')},
        preparer_sha256=sha(Path(__file__)))
    out = BASE / 'correction-code-r1'
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    save(receipt, report)
    save(out / 'verification.json', report)
    print('Complete correction batch prepared; frozen source and tests remain unchanged.', flush=True)


def apply(original_pid):
    freeze = load(BASE / 'freeze-r1/verification.json')
    guard(freeze)
    terminal = load(BASE / 'source-all-r1/verification.json')
    assert terminal['status'] in {'passed', 'failed'} and terminal['discovered_tests'] == 4101
    assert terminal['file_hashes'] == freeze['file_hashes'] and terminal['frozen_equal']
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1000, False, original_pid)
    if handle:
        try:
            code = wintypes.DWORD()
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != 259, 'Original test owner still live'
        finally:
            kernel.CloseHandle(handle)
    report = load(CANDIDATE / 'implementation.json')
    assert report['status'] == 'complete-correction-code-not-tested'
    assert all(sha(ROOT / name) == pin for name, pin in report['predecessor'].items())
    assert all(sha(CANDIDATE / name) == pin for name, pin in (report['files'] | report['support_files']).items())
    out = BASE / 'correction-apply-r1'
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    for name, target in report['mapping'].items():
        backup = out / 'baseline' / target
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes((ROOT / target).read_bytes())
    for name, target in report['mapping'].items():
        path = ROOT / target
        temporary = path.with_name(path.name + '.delivery66-correction.tmp')
        with temporary.open('xb') as handle:
            handle.write((CANDIDATE / name).read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    assert all(sha(ROOT / name) == pin for name, pin in freeze['formal_guard'].items())
    save(out / 'verification.json', dict(status='correction-applied-not-tested', cli_version='0.1.66',
        original_test_terminal=terminal['status'], original_process_stopped=True, formal_activation=False,
        mapping=report['mapping'], new_hashes={target: sha(ROOT / target) for target in report['mapping'].values()}))
    print('Whole correction applied after terminal test evidence; freeze r2 before testing.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--original-pid', type=int, default=32376)
    args = parser.parse_args()
    assert os.name == 'nt' and sys.dont_write_bytecode
    apply(args.original_pid) if args.apply else prepare()
