"""Commit only terminal CLI63 delivery evidence, tested Skill bytes and gallery docs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/job-enumeration-20261029-r1'
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')


def load(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows(text, prefix):
    return re.findall(r'^\| ' + prefix + r'\d+ \|.*$', text, re.M)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True)
    a = p.parse_args()
    assert re.fullmatch(r'r[1-9]\d*', a.run)
    required = ['recovery-controller-r2', 'formal-finish-controller-r1', 'registered-controller-r1', 'installed63-contracts-r2',
                'formal-kit-r1', 'rollout-registered-docs-r1', 'rollout-kit-docs-r1']
    missing = [n for n in required if not (BASE / n / 'verification.json').is_file()]
    if missing:
        print(json.dumps(dict(status='pending', missing=missing, mutated=False)), flush=True)
        return 2
    reports = {n: load(BASE / n / 'verification.json') for n in required}
    assert all(r['status'] == 'passed' for r in reports.values())
    contracts = reports['installed63-contracts-r2']
    assert contracts['tests'] == 406 and contracts['failures'] == contracts['errors'] == contracts['skipped'] == 0
    assert contracts['frozen_equal'] and contracts['source_and_installed_equal']
    assert all(sha(ROOT / n) == h for n, h in contracts['file_hashes'].items())
    activation = load(BASE / 'skill63-activation-r1/verification.json')
    assert activation['status'] == 'activated-and-entry-verified' and activation['cli_version'] == '0.1.63'
    assert not activation['post_test_document_changes']
    namespace = ROOT / 'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT / 'local/agent-ffmpeg/runtime.json'
    manifest = load(namespace)
    assert manifest['cli_version'] == '0.1.63' and len(manifest['files']) == 93
    assert sha(namespace) == activation['namespace_sha256'] and sha(runtime) == activation['runtime_sha256']
    assert all(sha(ROOT / r['path']) == r['sha256'] for r in manifest['files'])
    protected = {namespace: sha(namespace), runtime: sha(runtime)}
    protected.update({ROOT / r['path']: r['sha256'] for r in manifest['files']})
    assert reports['registered-controller-r1']['actual_loop_DF3_MuseTalk_passed']
    kit = ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r58.zip'
    assert sha(kit) == reports['formal-kit-r1']['kit_sha256']
    assert sha(ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r57.zip') == '46815047a247e32b85d4c5516062486c3f181c54a8d38b9c21710b1757e3b7fd'
    gallery = ROOT / 'docs/validation/evidence/optical-pack-gallery-docs-20261029-r1/verification.json'
    assert load(gallery)['status'] == 'passed' and load(gallery)['README_rows'] == 525
    n002_gallery = ROOT / 'docs/validation/evidence/optical-n002-gallery-20261029-r1/verification.json'
    assert load(n002_gallery)['status'] == 'passed' and len(load(n002_gallery)['choices']) == 8
    assert reports['rollout-kit-docs-r1']['README_rows'] == 528
    names = ['README.md', 'README.zh-TW.md', 'README.en.md', 'agent-ffmpeg-local-install-manifest.json',
             'docs/product/OPTICAL_EFFECT_PACK.md', 'docs/product/MUSIC_LOOP.md', 'docs/product/MUSIC_SCORE.md',
             'docs/product/GOAL_GAPS_20261025.md', 'docs/validation/CLI63统一Skill切换_2026-10-29.md',
             'docs/validation/光效选型页实测_2026-10-29.md', 'docs/validation/check_optical_pack_gallery.cjs',
             'docs/validation/document_optical_gallery.py', 'docs/validation/complete_source63_rollout_docs.py',
             'docs/validation/commit_source63_formal_delivery.py',
             'docs/validation/finish_source63_delivery.py',
             'docs/validation/stage_source63_skill.py', 'docs/validation/run_optical_n002_previews.py',
             'docs/validation/publish_optical_n002_previews.py', 'docs/validation/check_optical_n002_gallery.cjs',
             'docs/product/OPTICAL_N002_PREVIEWS.md',
             'docs/skills/UNIFIED_SKILL.md', 'docs/skills/UNIFIED_SKILL.en.md', 'docs/skills/UNIFIED_SKILL.zh-TW.md',
             'docs/skills/agent-editor-kit-community-unified-skill-r58.zip',
             'docs/skills/community-unified-skill-package-0.1.63-r58.json']
    names += [r['path'] for r in manifest['files']]
    directories = [BASE / n for n in ['recovery-controller-r2', 'formal-finish-controller-r1', 'installed63-contracts-r2', 'installed63-gpu-r1',
        'installed-actual-case-r1', 'installed63-lipsync-cuda-r1', 'staged-actual-case-r1', 'staged63-gpu-r1',
        'staged63-lipsync-cuda-r1', 'skill-controller-r1', 'skill63-activation-r1',
        'registered-controller-r1', 'registered-actual-case-r1', 'registered63-gpu-r1',
        'registered63-lipsync-cuda-r1', 'formal-kit-build-r1', 'formal-kit-r1',
        'rollout-registered-docs-r1', 'rollout-kit-docs-r1']]
    directories += [ROOT / 'docs/validation/evidence' / n for n in
                    ['optical-pack-gallery-20261029-r1', 'optical-pack-gallery-docs-20261029-r1',
                     'optical-n002-20261029-r1', 'optical-n002-publication-20261029-r1',
                     'optical-n002-gallery-20261029-r1']]
    directories += [ROOT / 'docs/assets/optical-n002-20261029-r1', ROOT / 'docs/assets/optical-n002-gallery-20261029-r1']
    for folder in directories:
        names += [p.relative_to(ROOT).as_posix() for p in folder.iterdir() if p.is_file()]
    old_folder = BASE / 'skill63-activation-r1/previous-skill'
    current_folder = ROOT / 'skills/agent-ffmpeg-local-editor'
    old_manifest = load(BASE / 'skill63-activation-r1/previous-namespace.json')
    assert old_manifest['cli_version'] == '0.1.59' and len(old_manifest['files']) == 93
    old_protected = {
        old_folder / (ROOT / r['path']).relative_to(current_folder): r['sha256']
        for r in old_manifest['files']
    }
    assert all(sha(p) == h for p, h in old_protected.items())
    protected.update(old_protected)
    names += [(old_folder / (ROOT / r['path']).relative_to(current_folder)).relative_to(ROOT).as_posix()
              for r in manifest['files']]
    names += ['docs/assets/optical-pack-gallery-20261029-r1/' + n for n in ['desktop.png', 'mobile.png']]
    names = sorted(set(names))
    assert not any(n.startswith(('product/', 'local/')) for n in names)
    assert all((ROOT / n).is_file() for n in names)
    for n in names:
        if n.endswith('.py'):
            compile((ROOT / n).read_text(encoding='utf-8'), n, 'exec')
    env = dict(os.environ)
    env['PATH'] = str(GIT.parent) + os.pathsep + env.get('PATH', '')
    git = [str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=0']
    def get(args):
        return subprocess.check_output([*git, *args], cwd=ROOT, env=env).decode('utf-8').strip()
    expected_head = '3cf6b9bfbcb23d035341da7be16ae41644043b7e'
    assert get(['branch', '--show-current']) == 'main'
    assert get(['rev-parse', 'HEAD']) == get(['rev-parse', 'origin/main']) == expected_head
    assert get(['remote', 'get-url', 'origin']) == 'git@github.com:copypasteltd/agent-editor-kit.git'
    for n in ('README.md', 'README.zh-TW.md', 'README.en.md'):
        old = rows(get(['show', 'HEAD:' + n]), 'R')
        new = rows((ROOT / n).read_text(encoding='utf-8'), 'R')
        assert len(old) == 524 and len(new) == 528 and new[:524] == old
    n = 'docs/product/GOAL_GAPS_20261025.md'
    old = rows(get(['show', 'HEAD:' + n]), 'G')
    assert len(old) == 38 and rows((ROOT / n).read_text(encoding='utf-8'), 'G') == old
    out = ROOT / ('local/agent-ffmpeg/source63-formal-delivery-commit-' + a.run)
    out.mkdir()
    spec = out / 'paths.nul'
    spec.write_bytes(b'\0'.join(n.encode('utf-8') for n in names) + b'\0')
    # The original 93-file backup is immutable evidence. Its upstream Markdown
    # contains existing trailing spaces; normalizing it would break the rollback
    # record. Verify its original hashes above instead of applying text styling.
    old_prefix = old_folder.relative_to(ROOT).as_posix() + '/'
    check_names = [n for n in names if Path(n).suffix not in {'.stdout', '.stderr'}
                   and not n.startswith(old_prefix)]
    steps = [('add', ['add', '--pathspec-from-file=' + str(spec), '--pathspec-file-nul'])]
    steps += [('check-' + str(i // 60), ['-c', 'core.whitespace=trailing-space,space-before-tab,cr-at-eol',
              'diff', '--cached', '--check', '--', *check_names[i:i + 60]]) for i in range(0, len(check_names), 60)]
    steps += [('commit', ['commit', '--only', '-m', 'feat: deliver tested CLI63 unified Skill and optical gallery previews',
                         '--pathspec-from-file=' + str(spec), '--pathspec-file-nul'])]
    for phase, args in steps:
        result = subprocess.run([*git, *args], cwd=ROOT, env=env, capture_output=True)
        (out / (phase + '.stdout')).write_bytes(result.stdout)
        (out / (phase + '.stderr')).write_bytes(result.stderr)
        print(json.dumps(dict(phase=phase, exit_code=result.returncode)), flush=True)
        assert result.returncode == 0, (phase, result.stdout[-1600:], result.stderr[-1600:])
    refs = dict(head=get(['rev-parse', 'HEAD']), origin=get(['rev-parse', 'origin/main']),
                remote=get(['ls-remote', 'origin', 'refs/heads/main']).split()[0])
    assert len(set(refs.values())) == 1
    assert all(sha(p) == h for p, h in protected.items())
    report = dict(status='passed', refs=refs, files=len(names), source='0.1.63', candidate='0.1.63/local61',
                  formal='0.1.63/local61/r58', README_rows=528, original_goal_rows_preserved=38,
                  original_backup_files_hash_verified=len(old_protected),
                  actual_loop_DF3_MuseTalk_passed=True, independent_kit_passed=True,
                  public_release_changed=False, full_goal_closed=False)
    (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
