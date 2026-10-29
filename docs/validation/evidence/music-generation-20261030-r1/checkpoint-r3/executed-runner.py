"""Freeze a bounded, truthful development checkpoint without touching live evidence."""
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
PRODUCT = ['local_music_generation', 'music_generation_model', 'music_generation_worker',
    'music_generation_pipeline', 'music_generation_cli', '__init__', 'community_cli', 'cli',
    'model_registry', 'job_workspaces', 'validator', 'capabilities']
SCRIPTS = ['acquire_acestep15_backend', 'acquire_acestep15_notices', 'probe_acestep15_native',
    'validate_music_generation_unit', 'run_source64_regressions', 'run_neural_music_case',
    'replay_neural_music_package', 'build_music64_candidate', 'prepare_music64_skill',
    'update_source64_readmes', 'check_music64_preflight', 'activate_music64_skill',
    'check_music64_skill_stage', 'record_music64_checkpoint', 'record_music64_timeout']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def git(*args):
    result = subprocess.run([GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *args], cwd=ROOT, capture_output=True,
        timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr[-1000:]
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and sys.dont_write_bytecode
    proof = BASE / ('checkpoint-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    assert git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert git('remote', 'get-url', '--push', 'origin').strip() == b'git@github.com:copypasteltd/agent-editor-kit.git'
    head = git('rev-parse', 'HEAD').decode().strip()
    goal = 'docs/product/GOAL_GAPS_20261025.md'
    assert (ROOT / goal).read_bytes() == git('show', 'HEAD:' + goal)
    manifest = load(ROOT / 'agent-ffmpeg-local-install-manifest.json')
    assert manifest['cli_version'] == '0.1.63' and len(manifest['files']) == 93
    assert all(sha(ROOT / row['path']) == row['sha256'] for row in manifest['files'])
    assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve() == (ROOT / 'skills/agent-ffmpeg-local-editor').resolve()
    source = {p.name:sha(p) for p in (ROOT / 'product/src/ai_ad_editor').glob('*.py')}
    assert len(source) == 288
    files = ['README.md', 'README.zh-TW.md', 'README.en.md', 'product/pyproject.toml',
        'product/tests/test_music_generation.py', 'product/tests/test_native_worker_imports.py',
        'scripts/package_community_skill.py', 'docs/product/MUSIC_BACKEND_ADMISSION.md',
        'docs/product/NEURAL_MUSIC_GENERATION.md', 'docs/validation/CLI64原生神经配乐_2026-10-30.md']
    files += ['product/src/ai_ad_editor/' + name + '.py' for name in PRODUCT]
    files += ['docs/validation/' + name + '.py' for name in SCRIPTS]
    for filename in files[:3]:
        current = (ROOT / filename).read_text('utf-8')
        previous = git('show', 'HEAD:' + filename).decode('utf-8')
        old_rows = re.findall(r'^\| R\d+ \|.*$', previous, re.M)
        current_rows = re.findall(r'^\| R\d+ \|.*$', current, re.M)
        assert len(old_rows) == 528
        assert {row for row in old_rows if not row.startswith('| R466 |')} <= set(current_rows)
        assert {re.match(r'^\| (R\d+) \|', row)[1] for row in old_rows} <= {re.match(r'^\| (R\d+) \|', row)[1] for row in current_rows}
        assert len(current_rows) == len(set(current_rows)) == 542
        assert len(re.findall(r'^\| F\d+ \|', current, re.M)) == 87
        for target in re.findall(r'\]\(([^)]+)\)', current):
            if target.startswith(('http:', 'https:', '#', 'mailto:', 'app:', 'codex:')):
                continue
            plain = target.partition('#')[0]
            if plain:
                assert (ROOT / plain).exists(), (filename, target)
    reports, pending = {}, []
    admission = ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1'
    for parent in [admission, *(ROOT / 'docs/validation/evidence' / ('music-generation-20261030-r' + str(i)) for i in range(1, 6))]:
        assert parent.is_dir()
        for directory in sorted(parent.iterdir()):
            if not directory.is_dir() or directory.name.startswith('checkpoint-'):
                if directory.is_file() and directory.suffix == '.json':
                    files.append(directory.relative_to(ROOT).as_posix())
                continue
            receipt = directory / 'verification.json'
            if not receipt.is_file():
                pending.append(directory.relative_to(ROOT).as_posix())
                continue
            value = load(receipt)
            reports[receipt.relative_to(ROOT).as_posix()] = dict(status=value['status'], sha256=sha(receipt))
            for path in directory.rglob('*'):
                assert not path.is_symlink() and not path.is_junction()
                if path.is_file():
                    assert path.stat().st_size < 16 * 1024**2
                    assert path.suffix.lower() not in {'.wav', '.mp4', '.f32', '.safetensors', '.whl', '.zip'}
                    files.append(path.relative_to(ROOT).as_posix())
    for group,count in dict(music=62, bootstrap=33, control=26, selection=57, semantic=104).items():
        report = load(BASE / ('source64-' + group + '-r1/verification.json'))
        assert report['status'] == 'passed' and report['tests'] == count and report['frozen_equal']
        assert report['failures'] == report['errors'] == report['skipped'] == 0
        assert all(sha(ROOT / path) == pin for path,pin in report['file_hashes'].items())
    assert load(BASE / 'source64-preflight-r1/verification.json')['cases'] == 6
    files = sorted(set(files))
    for relative in files:
        path = ROOT / relative
        assert path.is_file() and path.resolve().is_relative_to(ROOT.resolve())
        if path.suffix == '.py':
            compile(path.read_bytes(), str(path), 'exec')
    report = dict(status='passed', cli_version='0.1.64', source_hashes=source, base_commit=head,
        files={path:sha(ROOT / path) for path in files}, completed_reports=reports,
        pending_directories=pending, readonly_formal_cli='0.1.63', formal_skill_files=93,
        original_38_G_conditions_unchanged=True, README_rows=542, historical_528_rows_retained=True,
        historical_rows_corrected=['R466: link points to actual CLI59 installed400 receipt; module count282'],
        formal_activation=False, public_release_unchanged=True, natural_quality_accepted=False,
        full_product_goal_closed=False)
    (proof / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    files += [(proof / 'executed-runner.py').relative_to(ROOT).as_posix(), (proof / 'verification.json').relative_to(ROOT).as_posix()]
    scope = ROOT / 'local/agent-ffmpeg' / ('music64-checkpoint-' + args.run + '.nul')
    scope.write_bytes(('\0'.join(files) + '\0').encode('utf-8'))
    print(json.dumps(dict(status='passed', files=len(files), scope=str(scope),
                         completed_reports=len(reports), pending=pending, formal_activation=False)), flush=True)


if __name__ == '__main__':
    main()
