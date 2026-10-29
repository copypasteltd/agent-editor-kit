"""Audit terminal receipts and stage only this round's exact document scope."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/mingw64/bin/git.exe')
PARENT = 'c2ed15c7432f58ec33f6bf3036666552f19592bd'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def git(*arguments, input=None):
    result = subprocess.run([str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *arguments], cwd=ROOT,
        input=input, capture_output=True, timeout=1200, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:].decode('utf-8', errors='replace'))
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and os.name == 'nt' and sys.dont_write_bytecode
    assert git('rev-parse', 'HEAD').decode().strip() == PARENT
    assert git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert git('remote', 'get-url', '--push', 'origin').strip() == b'git@github.com:copypasteltd/agent-editor-kit.git'
    goal = 'docs/product/GOAL_GAPS_20261025.md'
    assert (ROOT / goal).read_bytes() == git('show', 'HEAD:' + goal)
    before = load(BASE / 'followup-r2/verification.json')
    assert before['status'] == 'passed'
    previous_raw = before['raw_staged_Git_blobs_equal_captured_bytes']
    assert all(sha(ROOT / path) == pin for path, pin in previous_raw.items())
    manifest = load(ROOT / 'agent-ffmpeg-local-install-manifest.json')
    assert manifest['cli_version'] == '0.1.63' and len(manifest['files']) == 93
    refusal = load(BASE / 'activation-refusal-r2/verification.json')
    assert refusal['status'] == 'passed' and refusal['apply_requested']
    formal = refusal['registered_files_after']
    assert formal == refusal['registered_files_before'] and len(formal) == 95
    assert all(sha(ROOT / name) == pin for name, pin in formal.items())
    candidate = load(BASE / 'candidate-r1/verification.json')
    source = load(BASE / 'actual-piano4/verification.json')
    full = load(BASE / 'source64-contracts-r1/verification.json')
    installed = load(BASE / 'installed-package-stage1/verification.json')
    assert source['status'] == 'passed' and source['complete_PCM_roundtrip_verified']
    assert candidate['cli_version'] == '0.1.64' and candidate['source_and_installed_equal']
    normalized_source = {Path(name).relative_to('product/src/ai_ad_editor').as_posix(): pin
        for name, pin in source['source_hashes'].items()}
    assert candidate['source_hashes'] == normalized_source and len(normalized_source) == 288
    assert all(sha(ROOT / name) == pin for name, pin in source['source_hashes'].items())
    installed_root = Path(candidate['installed']).resolve()
    for name, pin in candidate['source_hashes'].items():
        assert sha(installed_root / 'site/ai_ad_editor' / name) == pin
    assert full['status'] == 'failed' and full['tests'] == 431 and full['failures'] == 1
    assert full['errors'] == full['skipped'] == 0 and full['frozen_equal']
    assert all(sha(ROOT / name) == pin for name, pin in full['file_hashes'].items())
    assert installed['status'] == 'passed' and installed['new_model_forwards'] == 0
    assert installed['actual_PowerShell_entry'] and not installed['source_fallback']
    assert not installed['independent_installed_generation_accepted']
    native = ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1/native-interface-r6'
    probe = load(native / 'verification.json')
    assert probe['status'] == 'passed' and probe['model_forwards'] == 0
    assert not probe['product_cli_legacy_compatibility_accepted']
    assert probe['inventory_files'] == 580 and probe['imported_runtime_files'] == 278
    assert not probe['outside_inventory']

    proof = BASE / ('terminal-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    expected = {
        'source64-contracts-r1': 'failed', 'source64-session-control-r3': 'failed',
        'source64-session-control-r4': 'passed', 'process-diagnostic-r3': 'captured',
        'process-diagnostic-r4': 'captured', 'activation-refusal-r1': 'passed',
        'activation-refusal-r2': 'passed', 'actual-piano4': 'passed',
        'package-r1': 'passed', 'transaction-latency-r1': 'passed',
        'round-finalization-r1': 'passed', 'round-closure-r1': 'passed',
        'installed-package-stage1': 'passed', 'terminal-r1': 'failed'}
    raw = set()
    for directory, status in expected.items():
        folder = BASE / directory
        assert load(folder / 'verification.json')['status'] == status, directory
        for path in folder.iterdir():
            assert path.is_file(), str(path)
            assert path.stat().st_size < 16 * 1024**2
            raw.add(path.relative_to(ROOT).as_posix())
    raw.update(path.relative_to(ROOT).as_posix() for path in native.iterdir() if path.is_file())
    raw.add((proof / 'executed-runner.py').relative_to(ROOT).as_posix())
    authored = {'.gitattributes', 'README.md', 'README.zh-TW.md', 'README.en.md',
        'docs/validation/CLI64原生神经配乐_2026-10-30.md',
        'docs/product/NEURAL_MUSIC_GENERATION.md', 'docs/product/CASES.md',
        *('docs/validation/' + name for name in (
            'activate_music64_skill.py', 'probe_acestep15_native.py',
            'commit_music64_followup.py', 'measure_music64_transaction.py',
            'check_music64_activation_refusal.py', 'finalize_music64_round.py',
            'check_music64_installed_package.py', 'close_music64_round.py',
            'record_music64_terminal.py', 'commit_music64_terminal.py'))}
    for name in ('README.md', 'README.zh-TW.md', 'README.en.md'):
        old = git('show', 'HEAD:' + name).decode('utf-8')
        text = (ROOT / name).read_text(encoding='utf-8')
        old_rows = re.findall(r'^\| R\d+ \|.*$', old, re.M)
        rows = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(old_rows) == 546 and set(old_rows) <= set(rows)
        assert len(rows) == len(set(rows)) == 555
        assert len(re.findall(r'^\| F\d+ \|', text, re.M)) == 87
        assert [int(value[1:]) for value in re.findall(r'^\| (R\d+) \|', text, re.M)] == list(range(1, 556))
        for number in range(547, 556):
            row = next(line for line in rows if line.startswith(f'| R{number} |'))
            targets = re.findall(r'\]\((docs/validation/[^)]+)\)', row)
            assert targets and all((ROOT / target).is_file() for target in targets)
    attributes = (ROOT / '.gitattributes').read_text(encoding='utf-8')
    for name in authored:
        path = ROOT / name
        assert path.is_file() and path.resolve().is_relative_to(ROOT.resolve())
        if path.suffix == '.py':
            compile(path.read_bytes(), name, 'exec')
            assert name + ' text eol=lf' in attributes
    scope = raw | authored
    banned = {'.wav', '.mp4', '.mp3', '.zip', '.png', '.exe', '.safetensors', '.f32', '.pcm', '.rgba'}
    assert all(Path(name).suffix.lower() not in banned for name in scope)
    frozen = {name: sha(ROOT / name) for name in scope}
    pathspec = ROOT / ('local/agent-ffmpeg/music64-terminal-' + args.run + '.nul')
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    print('Staging terminal evidence and the exact authored scope.', flush=True)
    git('add', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    ordered = sorted(raw | set(previous_raw))
    output = git('cat-file', '--batch', input=''.join(':' + path + '\n' for path in ordered).encode('utf-8'))
    cursor, blobs = 0, {}
    for name in ordered:
        stop = output.index(b'\n', cursor)
        oid, kind, length = output[cursor:stop].split()
        assert kind == b'blob'
        length = int(length)
        data = output[stop + 1:stop + 1 + length]
        assert data == (ROOT / name).read_bytes(), name
        blobs[name] = hashlib.sha256(data).hexdigest()
        cursor = stop + length + 2
    assert cursor == len(output)
    assert all(sha(ROOT / name) == pin for name, pin in frozen.items())
    report = dict(status='passed', base_commit=PARENT, README_rows=555,
        previous_546_rows_retained=True, feature_rows=87, original_goal_document_unchanged=True,
        original_goal_document_sha256=sha(ROOT / goal), full_431_status='failed',
        source_cli='0.1.64', candidate='v0.1.0-alpha.4-local.62', formal_cli='0.1.63',
        formal_skill_files=93, formal_configurations=2, formal_activation=False,
        source_and_installed_modules=288, independent_installed_generation_accepted=False,
        raw_staged_Git_blobs_equal_captured_bytes=blobs, files=frozen,
        terminal_groups=expected, media_published=False, natural_music_quality_accepted=False,
        audit_runner_initial_errors=[
            'Before staging: compared module-relative keys to project-relative keys. Corrected only the key prefix; all 288 hashes still required to match.',
            'Before staging: expected R1..R9 but historical identifiers are R01..R09. Preserved original identifiers and checked numeric ordering. The failed audit snapshot remains terminal-r1.'],
        full_product_goal_closed=False, unrelated_staged_changes_included=False)
    (proof / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    scope.add((proof / 'verification.json').relative_to(ROOT).as_posix())
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    git('add', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    print(json.dumps(dict(status='passed', scope_files=len(scope), raw_blobs=len(blobs),
        README_rows=555, formal_activation=False)), flush=True)


if __name__ == '__main__':
    main()
