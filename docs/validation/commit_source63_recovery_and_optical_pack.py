"""Commit the recovered gate wiring and actual reusable optical content; normal main push."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='r2')
    args = parser.parse_args()
    assert re.fullmatch(r'r[1-9]\d*', args.run)
    proof = ROOT / 'docs/validation/evidence/optical-pack-publication-20261029-r1/verification.json'
    assert proof.is_file()
    published = load(proof)
    assert published['status'] == 'published-and-documented' and published['templates'] == 8
    assert published['actual_registered_cli'] == '0.1.59' and published['registered_candidate_complete_RGBA_PCM_equal']
    assert published['README_rows'] == 524
    prep = load(BASE / 'recovery-preparation-r1/verification.json')
    assert prep['status'] == 'passed' and prep['formal_files_unchanged'] == 95
    assert not prep['formal_activation'] and not prep['full_installed_contracts_accepted']
    installation = load(BASE / 'installation-candidate-r1/verification.json')
    assert all(sha(Path(p)) == h for p, h in installation['registered_skill_file_hashes'].items())
    assert load(ROOT / 'agent-ffmpeg-local-install-manifest.json')['cli_version'] == '0.1.59'
    rollback = load(BASE / 'activation-rollback-r4/verification.json')
    assert rollback['status'] == 'passed'
    assert rollback['script_sha256'] == sha(ROOT / 'docs/validation/activate_source63_skill.py')
    assert sha(ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r57.zip') == '46815047a247e32b85d4c5516062486c3f181c54a8d38b9c21710b1757e3b7fd'
    names = ['README.md', 'README.zh-TW.md', 'README.en.md', 'docs/product/GOAL_GAPS_20261025.md',
             'docs/product/OPTICAL_EFFECT_PACK.md', 'docs/product/CASES.md',
             'docs/validation/CLI63安装回归中断与恢复_2026-10-29.md',
             'docs/validation/CLI63候选交付门禁_2026-10-29.md']
    scripts = ['stage_source63_skill.py', 'activate_source63_skill.py', 'run_source63_skill_acceptance.py',
               'run_registered63_gpu_case.py', 'run_registered63_lipsync_case.py', 'run_registered63_loop_case.py',
               'prepare_source63_registered_checks.py', 'prepare_source63_activation.py',
               'prepare_source63_recovery_rollback.py', 'check_source63_recovery_rollback.py',
               'check_source63_recovery_full_rollback.py', 'update_source63_recovery_docs.py',
               'resume_source63_delivery.py', 'complete_source63_rollout_docs.py',
               'build_optical_effect_pack.py', 'run_optical_effect_pack_case.py',
               'run_registered_optical_pack_smoke.py', 'publish_optical_effect_pack.py',
               'commit_source63_recovery_and_optical_pack.py']
    names += ['docs/validation/' + s for s in scripts]
    for directory in [ROOT / 'docs/content/effect-packs/optical-v1',
                      ROOT / 'docs/assets/optical-pack-20261029-r1',
                      ROOT / 'docs/validation/evidence/optical-pack-20261029-r1',
                      ROOT / 'docs/validation/evidence/optical-pack-20261029-registered59-r1',
                      ROOT / 'docs/validation/evidence/optical-pack-publication-20261029-r1',
                      BASE / 'installed63-contracts-r1', BASE / 'activation-rollback-r3',
                      BASE / 'activation-rollback-r4', BASE / 'recovery-preparation-r1']:
        names += [p.relative_to(ROOT).as_posix() for p in directory.iterdir() if p.is_file()]
    names += ['docs/content/effect-packs/optical-v1.zip', 'docs/content/effect-packs/optical-v1.sha256.json']
    names += [(BASE / 'recovery-controller-r2' / n).relative_to(ROOT).as_posix()
              for n in ('executed-runner.py', 'interruption.json')]
    names = sorted(set(names))
    assert not any(n.startswith(('product/', 'skills/')) for n in names)
    for n in names:
        p = ROOT / n
        assert p.is_file()
        if p.suffix == '.py':
            compile(p.read_text(encoding='utf-8'), str(p), 'exec')
    for n in ('README.md', 'README.zh-TW.md', 'README.en.md'):
        assert len(re.findall(r'^\| R\d+ \|', (ROOT / n).read_text(encoding='utf-8'), re.M)) == 524
    out = ROOT / ('local/agent-ffmpeg/source63-recovery-optical-commit-' + args.run)
    out.mkdir(exist_ok=False)
    spec = out / 'paths.nul'
    spec.write_bytes(b'\0'.join(n.encode('utf-8') for n in names) + b'\0')
    env = dict(os.environ)
    env['PATH'] = str(GIT.parent) + os.pathsep + env.get('PATH', '')
    git = [str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=0']
    def get(args):
        return subprocess.check_output([*git, *args], cwd=ROOT, env=env).decode('utf-8').strip()
    assert get(['branch', '--show-current']) == 'main'
    assert get(['rev-parse', 'HEAD']) == '6a0029b1ebb6fa65c83d04fd80eb13de1f73b3b5'
    assert get(['remote', 'get-url', 'origin']) == 'git@github.com:copypasteltd/agent-editor-kit.git'
    old = re.findall(r'^\| G\d\d \|.*$', get(['show', 'HEAD:docs/product/GOAL_GAPS_20261025.md']), re.M)
    new = re.findall(r'^\| G\d\d \|.*$', (ROOT / 'docs/product/GOAL_GAPS_20261025.md').read_text(encoding='utf-8'), re.M)
    assert len(old) == 38 and new == old
    steps = [('add', ['add', '--pathspec-from-file=' + str(spec), '--pathspec-file-nul'])]
    # Raw subprocess captures retain their original bytes, including an interrupted
    # unittest progress line's trailing space; do not edit immutable evidence.
    check_names = [n for n in names if Path(n).suffix not in {'.stdout', '.stderr'}]
    # Some original captures and provenance notes deliberately preserve CRLF.
    steps += [('check-' + str(i // 60), ['-c', 'core.whitespace=trailing-space,space-before-tab,cr-at-eol',
              'diff', '--cached', '--check', '--', *check_names[i:i + 60]]) for i in range(0, len(check_names), 60)]
    steps += [('commit', ['commit', '--only', '-m', 'feat: add eight editable optical templates with real GPU previews and replay',
                         '--pathspec-from-file=' + str(spec), '--pathspec-file-nul'])]
    for phase, args in steps:
        result = subprocess.run([*git, *args], cwd=ROOT, env=env, capture_output=True)
        (out / (phase + '.stdout')).write_bytes(result.stdout)
        (out / (phase + '.stderr')).write_bytes(result.stderr)
        print(json.dumps(dict(phase=phase, exit_code=result.returncode)), flush=True)
        assert result.returncode == 0, (phase, result.stderr[-2000:])
    refs = dict(head=get(['rev-parse', 'HEAD']), origin=get(['rev-parse', 'origin/main']),
                remote=get(['ls-remote', 'origin', 'refs/heads/main']).split()[0])
    assert len(set(refs.values())) == 1
    assert all(sha(Path(p)) == h for p, h in installation['registered_skill_file_hashes'].items())
    receipt = dict(status='passed', refs=refs, files=len(names), source='0.1.63',
                   candidate='0.1.63/local61', formal='0.1.59/local57/r57',
                   README_rows=524, optical_templates=8, full_goal_closed=False)
    (out / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
