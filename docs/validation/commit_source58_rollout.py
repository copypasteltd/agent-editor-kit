"""Commit only the accepted CLI58 rollout, docs, Skill files and bounded evidence."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
BASE = ROOT/'docs/validation/evidence/ad-content-uniqueness-20261029-r1'


def main():
    for name in ['installed58-contracts-r1', 'registered58-gpu-r1', 'formal-kit-r3', 'rollout-docs-r1']:
        assert json.loads((BASE/name/'verification.json').read_bytes())['status'] == 'passed'
    files = ['README.md', 'README.en.md', 'README.zh-TW.md', 'agent-ffmpeg-local-install-manifest.json',
             'scripts/package_community_skill.py', 'docs/product/COMMUNITY_LOCAL_DELIVERY.md',
             'docs/product/GOAL_GAPS_20261025.md', 'docs/product/MUSIC_BACKEND_ADMISSION.md',
             'docs/validation/CLI58统一Skill切换_2026-10-29.md', 'docs/validation/CLI58独立安装交付_2026-10-29.md',
             'docs/validation/build_source58_final_kit.py', 'docs/validation/verify_source58_final_kit.py',
             'docs/validation/complete_source58_rollout_docs.py', 'docs/validation/probe_yue2_native.py',
             'docs/validation/commit_source58_rollout.py',
             'docs/skills/agent-editor-kit-community-unified-skill-r56.zip',
             'docs/skills/community-unified-skill-package-0.1.58-r56.json']
    files += ['skills/agent-ffmpeg-local-editor/'+name for name in ['SKILL.md', 'references/ad-selection.md', 'references/runtime.md', 'scripts/run.py']]
    files += ['docs/skills/UNIFIED_SKILL'+suffix+'.md' for suffix in ['', '.en', '.zh-TW']]
    for name in ['installed58-contracts-r1', 'skill58-candidate-r1', 'staged58-gpu-r1',
                 'skill58-activation-r1', 'registered58-gpu-r1', 'formal-kit-build-r1',
                 'formal-kit-build-r2', 'formal-kit-r1', 'formal-kit-r2', 'formal-kit-r3', 'rollout-docs-r1']:
        for path in sorted((BASE/name).iterdir()):
            if path.is_file() and not path.name.startswith('previous-'):
                files.append(path.relative_to(ROOT).as_posix())
    files = sorted(set(files))
    assert all((ROOT/name).is_file() for name in files)
    out = ROOT/'local/agent-ffmpeg/source58-commit-r6'
    out.mkdir(exist_ok=False)
    (out/'paths.json').write_text(json.dumps(files, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    env = dict(os.environ)
    env['PATH'] = str(GIT.parent)+os.pathsep+env.get('PATH', '')
    git = [str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=0']
    steps = [('add', ['add', '--', *files]), ('check', ['diff', '--cached', '--check', '--', *files]),
             ('commit', ['commit', '--only', '-m', 'release: activate CLI58 unified Skill and verify portable r56 kit', '--', *files])]
    for name, argv in steps:
        result = subprocess.run([*git, *argv], cwd=ROOT, env=env, capture_output=True)
        (out/(name+'.stdout')).write_bytes(result.stdout)
        (out/(name+'.stderr')).write_bytes(result.stderr)
        print(json.dumps(dict(phase=name, exit_code=result.returncode)), flush=True)
        if result.returncode:
            print(result.stderr.decode('utf-8', 'replace')[-3000:], flush=True)
            return result.returncode
    result = subprocess.run([*git, 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, check=True)
    print(result.stdout.decode('ascii').strip(), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
