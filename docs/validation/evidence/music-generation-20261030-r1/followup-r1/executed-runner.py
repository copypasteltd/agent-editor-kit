"""Stage exact completed receipts with byte preservation; exclude live runs."""
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
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
EXPECTED_HEAD = '862445cefa7f0e0d38af352b225cc3d79dc806a3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args, input=None):
    result = subprocess.run([GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *args], cwd=ROOT, input=input,
        capture_output=True, timeout=1200, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:].decode('utf-8', errors='replace'))
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and os.name == 'nt' and sys.dont_write_bytecode
    assert git('rev-parse', 'HEAD').decode().strip() == EXPECTED_HEAD
    assert git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert git('remote', 'get-url', '--push', 'origin').strip() == b'git@github.com:copypasteltd/agent-editor-kit.git'
    proof = BASE / ('followup-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    previous = json.loads((BASE / 'checkpoint-r3/verification.json').read_bytes())
    raw = {p for p in previous['files'] if p.startswith('docs/validation/evidence/')}
    raw.update(['docs/validation/evidence/music-generation-20261030-r1/checkpoint-r3/executed-runner.py',
                'docs/validation/evidence/music-generation-20261030-r1/checkpoint-r3/verification.json'])
    assert all(sha(ROOT / p) == value for p,value in previous['files'].items()
               if p.startswith('docs/validation/evidence/'))
    completed = ['installed64-selection-r1', 'installed64-preflight-r1']
    for name in completed:
        directory = BASE / name
        report = json.loads((directory / 'verification.json').read_bytes())
        assert report['status'] == 'passed'
        if name.startswith('installed64-selection'):
            assert report['tests'] == 57 and report['frozen_equal'] and report['source_fallback'] is False
        else:
            assert report['cases'] == 6
        raw.update(p.relative_to(ROOT).as_posix() for p in directory.iterdir() if p.is_file())
    alternate = ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1/native-interface-r4/verification.json'
    value = json.loads(alternate.read_bytes())
    assert value['status'] == 'failed' and value['model_forwards'] == 0
    assert 'comfy_aimdo.storage' in value['error']
    raw.add(alternate.relative_to(ROOT).as_posix())
    # Add terminal stack captures only; active generation/contracts are excluded.
    diagnostic = BASE / 'process-diagnostic-r1'
    if (diagnostic / 'verification.json').is_file():
        raw.update(p.relative_to(ROOT).as_posix() for p in diagnostic.iterdir() if p.is_file())
    scope = {'.gitattributes', 'README.md', 'README.zh-TW.md', 'README.en.md',
        'docs/validation/update_source64_readmes.py', 'docs/validation/diagnose_music64_process.py',
        'docs/validation/record_music64_followup.py', 'docs/validation/CLI64原生神经配乐_2026-10-30.md', *raw}
    for filename in ['README.md', 'README.zh-TW.md', 'README.en.md']:
        old = git('show', 'HEAD:' + filename).decode('utf-8')
        new = (ROOT / filename).read_text(encoding='utf-8')
        old_rows = re.findall(r'^\| R\d+ \|.*$', old, re.M)
        rows = re.findall(r'^\| R\d+ \|.*$', new, re.M)
        assert len(old_rows) == 542 and set(old_rows) <= set(rows)
        assert len(rows) == len(set(rows)) == 544
        assert len(re.findall(r'^\| F\d+ \|', new, re.M)) == 87
    goal = 'docs/product/GOAL_GAPS_20261025.md'
    assert (ROOT / goal).read_bytes() == git('show', 'HEAD:' + goal)
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    assert manifest['cli_version'] == '0.1.63' and len(manifest['files']) == 93
    assert all(sha(ROOT / row['path']) == row['sha256'] for row in manifest['files'])
    for p in scope:
        file = ROOT / p
        assert file.is_file() and file.resolve().is_relative_to(ROOT.resolve())
        if file.suffix == '.py':
            compile(file.read_bytes(), str(file), 'exec')
    pathspec = ROOT / ('local/agent-ffmpeg/music64-followup-' + args.run + '.nul')
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    print('Staging bounded completed receipts and preserving original capture bytes.', flush=True)
    git('add', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    raw_spec = ROOT / ('local/agent-ffmpeg/music64-followup-raw-' + args.run + '.nul')
    raw_spec.write_bytes(('\0'.join(sorted(raw)) + '\0').encode('utf-8'))
    git('add', '--renormalize', '--pathspec-from-file=' + str(raw_spec), '--pathspec-file-nul')
    # Read the staged Git blobs, not a working-tree diff or an old receipt.
    ordered = sorted(raw)
    output = git('cat-file', '--batch', input=(''.join(':' + p + '\n' for p in ordered)).encode('utf-8'))
    cursor, blobs = 0, {}
    for relative in ordered:
        stop = output.index(b'\n', cursor)
        header = output[cursor:stop].split()
        assert len(header) == 3 and header[1] == b'blob', (relative, header)
        size = int(header[2])
        data = output[stop + 1:stop + 1 + size]
        assert len(data) == size and data == (ROOT / relative).read_bytes(), relative
        blobs[relative] = hashlib.sha256(data).hexdigest()
        cursor = stop + 1 + size + 1
    assert cursor == len(output)
    report = dict(status='passed', base_commit=EXPECTED_HEAD, README_rows=544,
        previous_542_rows_retained=True, raw_working_bytes_unchanged=True,
        raw_staged_Git_blobs_equal_captured_bytes=blobs,
        completed_installed_groups=completed, alternate_native_probe_status='failed',
        excluded_live_runs=['actual-piano4', 'source64-contracts-r1', 'installed64-semantic-r1'],
        files={p:sha(ROOT / p) for p in sorted(scope)},
        formal_cli='0.1.63', formal_skill_files=93, formal_activation=False,
        full_product_goal_closed=False, natural_music_quality_accepted=False)
    receipt = proof / 'verification.json'
    receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    scope.update(p.relative_to(ROOT).as_posix() for p in proof.iterdir() if p.is_file())
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    git('add', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    print(json.dumps(dict(status='passed', scope=str(pathspec), files=len(scope),
        raw_blobs=len(blobs), formal_activation=False)), flush=True)


if __name__ == '__main__':
    main()
