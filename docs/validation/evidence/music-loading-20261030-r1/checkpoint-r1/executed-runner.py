"""Audit and stage a bounded CLI65 checkpoint, excluding the live music case."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-loading-20261030-r1'
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/mingw64/bin/git.exe')
PARENT = 'f3f007c8fd7e360efc0943de4f1919914a0934aa'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def git(*arguments, input=None):
    command = [str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *arguments]
    assert len(subprocess.list2cmdline(command)) < 30000
    result = subprocess.run(command, input=input, cwd=ROOT, capture_output=True,
        timeout=1200, creationflags=subprocess.CREATE_NO_WINDOW)
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
    unit = load(BASE / 'source65-unit-r1/verification.json')
    assert unit['status'] == 'passed' and unit['tests'] == 37 and unit['frozen_equal']
    assert len(unit['file_hashes']) == 288 + 194
    assert all(sha(ROOT / name) == pin for name, pin in unit['file_hashes'].items())
    candidate = load(BASE / 'candidate-r1/verification.json')
    assert candidate['status'] == 'installed-and-byte-verified' and candidate['cli_version'] == '0.1.65'
    assert candidate['local_release'] == 'v0.1.0-alpha.4-local.63' and candidate['built_for_validation_only']
    assert candidate['source_and_installed_equal'] and not candidate['skill_activated']
    installed = Path(candidate['installed']).resolve()
    assert installed.is_relative_to((ROOT / 'local/agent-ffmpeg').resolve())
    source = ROOT / 'product/src/ai_ad_editor'
    assert len(candidate['source_hashes']) == 288
    for name, pin in candidate['source_hashes'].items():
        assert sha(source / name) == sha(installed / 'site/ai_ad_editor' / name) == pin
    formal = candidate['registered_files']
    assert len(formal) == 95 and all(sha(Path(name)) == pin for name, pin in formal.items())
    manifest = load(ROOT / 'agent-ffmpeg-local-install-manifest.json')
    assert manifest['cli_version'] == '0.1.63' and manifest['release'] == 'v0.1.0-alpha.4-local.61'
    assert manifest['skill_count'] == 1 and manifest['module_count'] == 17 and len(manifest['files']) == 93
    stage = load(BASE / 'skill-stage-r1/verification.json')
    assert stage['status'] == 'passed' and len(stage['files']) == 94 and stage['formal_files_unchanged']
    staged_root = ROOT / 'local/agent-ffmpeg/music65-skill-stage-r1/skills/agent-ffmpeg-local-editor'
    assert all(sha(staged_root / name) == pin for name, pin in stage['files'].items())
    proof = BASE / ('checkpoint-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    expected = {
        'source65-unit-r1': 'passed', 'source65-music-r1': 'passed',
        'source65-bootstrap-r1': 'passed', 'source65-control-r1': 'passed',
        'source65-session-r1': 'failed', 'native-reader-r1': 'passed',
        'native-reader-d1': 'passed', 'native-stack-reader1': 'captured',
        'candidate-r1': 'installed-and-byte-verified', 'skill-stage-r1': 'passed',
        'documentation-r1': 'passed', 'session-startup-trace-r1': 'passed',
        'recovery-integrity-r1': 'reproduced', 'installed65-music-i1': 'passed',
        'installed65-bootstrap-i1': 'passed', 'installed65-control-i1': 'passed',
        'documentation-close-r1': 'passed'}
    raw = set()
    for directory, status in expected.items():
        folder = BASE / directory
        assert load(folder / 'verification.json')['status'] == status, directory
        for path in folder.iterdir():
            assert path.is_file() and path.stat().st_size < 16 * 1024**2
            raw.add(path.relative_to(ROOT).as_posix())
    raw.add((proof / 'executed-runner.py').relative_to(ROOT).as_posix())
    helpers = ('run_music65_checks.py', 'probe_music65_reader.py',
        'capture_music65_native_stack.py', 'build_music65_candidate.py',
        'prepare_music65_skill.py', 'check_music65_skill_stage.py',
        'run_neural_music65_case.py', 'update_music65_docs.py',
        'trace_music65_session_startup.py', 'reproduce_music65_recovery_integrity.py',
        'finalize_music65_docs.py', 'record_music65_checkpoint.py', 'commit_music65_checkpoint.py')
    authored = {'.gitattributes', 'README.md', 'README.zh-TW.md', 'README.en.md',
        'product/src/ai_ad_editor/music_generation_model.py',
        'product/src/ai_ad_editor/music_generation_pipeline.py',
        'product/src/ai_ad_editor/local_music_generation.py',
        'product/src/ai_ad_editor/__init__.py', 'product/pyproject.toml',
        'product/tests/test_music_generation.py', 'product/tests/test_music_loading.py',
        'docs/product/NEURAL_MUSIC_LOADING.md', 'docs/product/NEURAL_MUSIC_GENERATION.md',
        'docs/validation/CLI65配乐读取与计时_2026-10-30.md',
        *('docs/validation/' + name for name in helpers)}
    for filename in ('README.md', 'README.zh-TW.md', 'README.en.md'):
        old = git('show', 'HEAD:' + filename).decode('utf-8')
        text = (ROOT / filename).read_text(encoding='utf-8')
        old_rows = re.findall(r'^\| R\d+ \|.*$', old, re.M)
        rows = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(old_rows) == 555 and set(old_rows) <= set(rows)
        assert len(rows) == len(set(rows)) == 570
        assert [int(value[1:]) for value in re.findall(r'^\| (R\d+) \|', text, re.M)] == list(range(1, 571))
        old_features = re.findall(r'^\| F\d+ \|.*$', old, re.M)
        features = re.findall(r'^\| F\d+ \|.*$', text, re.M)
        assert len(old_features) == 87 and set(old_features) <= set(features) and len(features) == 88
        assert '<!-- aek-cli65-current -->' in text
        for number in range(556, 571):
            row = next(value for value in rows if value.startswith(f'| R{number} |'))
            targets = re.findall(r'\]\((docs/validation/[^)]+)\)', row)
            assert targets and all((ROOT / name).is_file() for name in targets)
    attributes = (ROOT / '.gitattributes').read_text(encoding='utf-8')
    assert 'docs/validation/evidence/music-loading-20261030-r1/** -text -whitespace' in attributes
    for name in authored:
        path = ROOT / name
        assert path.is_file() and path.resolve().is_relative_to(ROOT.resolve())
        if path.suffix == '.py':
            compile(path.read_bytes(), name, 'exec')
        if name.startswith('docs/validation/') and path.suffix == '.py':
            assert name + ' text eol=lf' in attributes
    scope = raw | authored
    assert not any('/actual-stage1/' in name for name in scope)
    banned = {'.wav', '.mp4', '.mp3', '.zip', '.png', '.exe', '.safetensors', '.f32', '.pcm', '.rgba'}
    assert all(Path(name).suffix.lower() not in banned for name in scope)
    frozen = {name: sha(ROOT / name) for name in scope}
    pathspec = ROOT / ('local/agent-ffmpeg/music65-checkpoint-' + args.run + '.nul')
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    print('Staging only audited CLI65 files and terminal receipts; live inference excluded.', flush=True)
    git('add', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    ordered = sorted(raw)
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
    assert cursor == len(output) and all(sha(ROOT / name) == pin for name, pin in frozen.items())
    report = dict(status='passed', base_commit=PARENT, README_rows=570, previous_555_rows_retained=True,
        previous_87_features_retained=True, feature_rows=88, original_goal_document_unchanged=True,
        original_goal_document_sha256=sha(ROOT / goal), source_cli='0.1.65',
        candidate='v0.1.0-alpha.4-local.63', formal_cli='0.1.63', formal_skill_files=93,
        formal_configurations=2, formal_activation=False, source_modules=288, test_modules=194,
        full_443_accepted=False, original_session_group_status='failed',
        backup_defects_reproduced=2, backup_defects_repaired=False, actual65_generation_accepted=False,
        live_actual_case_excluded=True, terminal_groups=expected, files=frozen,
        raw_staged_Git_blobs_equal_captured_bytes=blobs, media_published=False,
        full_product_goal_closed=False, unrelated_staged_changes_included=False)
    (proof / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8', newline='\n')
    scope.add((proof / 'verification.json').relative_to(ROOT).as_posix())
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    git('add', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    print(json.dumps(dict(status='passed', scope_files=len(scope), raw_blobs=len(blobs), README_rows=570,
        original_goal_document_unchanged=True, formal_activation=False)), flush=True)


if __name__ == '__main__':
    main()
