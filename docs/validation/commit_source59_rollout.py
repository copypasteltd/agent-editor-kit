"""Commit accepted CLI59/r57 rollout; retain private rollback files only on E."""
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-score-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')

def main():
    for name in ['installed59-contracts-r1','registered59-score-entry-r1','registered59-gpu-r1',
                 'formal-kit-r1','rollout-docs-r1','rollout-current-audit-r1']:
        assert json.loads((BASE/name/'verification.json').read_bytes())['status']=='passed'
    activation=json.loads((BASE/'skill59-activation-r1/verification.json').read_bytes())
    assert activation['status']=='activated-and-entry-verified'
    files=['README.md','README.en.md','README.zh-TW.md','agent-ffmpeg-local-install-manifest.json',
        'scripts/package_community_skill.py','docs/product/COMMUNITY_LOCAL_DELIVERY.md',
        'docs/product/MUSIC_SCORE.md','docs/product/MUSIC_BACKEND_ADMISSION.md',
        'docs/product/GOAL_GAPS_20261025.md','docs/product/SKILLS.md','docs/product/CASES.md',
        'docs/local/INSTALLATION.md','docs/skills/agent-editor-kit-community-unified-skill-r57.zip',
        'docs/skills/community-unified-skill-package-0.1.59-r57.json']
    files += ['docs/product/COMMUNITY_MATERIALS'+suffix+'.md' for suffix in ['', '.en','.zh-TW']]
    files += ['docs/skills/UNIFIED_SKILL'+suffix+'.md' for suffix in ['', '.en','.zh-TW']]
    files += ['docs/validation/'+name+'.md' for name in ['CLI59谱面合成_2026-10-29',
        'CLI59独立安装交付_2026-10-29','CLI59统一Skill切换_2026-10-29']]
    files += ['docs/validation/'+name+'.py' for name in ['run_source59_staged_gpu_case',
        'activate_source59_skill','verify_source59_registered_score','run_source59_registered_gpu_case',
        'build_source59_final_kit','verify_source59_final_kit','complete_source59_rollout_docs',
        'commit_source59_rollout']]
    files += ['skills/agent-ffmpeg-local-editor/'+name for name in ['SKILL.md',
        'references/community-materials.md','references/runtime.md','scripts/run.py']]
    for name in ['installed59-contracts-r1','staged59-gpu-r1','skill59-activation-r1',
        'registered59-score-entry-r1','registered59-gpu-r1','formal-kit-build-r1',
        'formal-kit-r1','rollout-docs-r1','rollout-current-audit-r1']:
        # Backup directories/configs intentionally excluded, no recursive traversal.
        files += [p.relative_to(ROOT).as_posix() for p in (BASE/name).iterdir()
                  if p.is_file() and not p.name.startswith('previous-')]
    files=sorted(set(files));assert all((ROOT/name).is_file() for name in files)
    out=ROOT/'local/agent-ffmpeg/source59-rollout-commit-r1';out.mkdir(exist_ok=False)
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pathspec=out/'paths.nul';pathspec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    assert subprocess.check_output([*git,'branch','--show-current'],cwd=ROOT).strip()==b'main'
    steps=[('add',['add','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','release: activate CLI59 unified Skill and verify portable r57 kit',
        '--pathspec-from-file='+str(pathspec),'--pathspec-file-nul'])]
    for name,args in steps:
        p=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
        (out/(name+'.stdout')).write_bytes(p.stdout);(out/(name+'.stderr')).write_bytes(p.stderr)
        print(json.dumps(dict(phase=name,exit_code=p.returncode)),flush=True)
        if p.returncode:
            print(p.stderr.decode('utf-8','replace')[-2000:],flush=True);return p.returncode
    refs={}
    for name,args in [('head',['rev-parse','HEAD']),('origin',['rev-parse','origin/main']),('remote',['ls-remote','origin','refs/heads/main'])]:
        refs[name]=subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().split()[0]
    assert len(set(refs.values()))==1
    (out/'verification.json').write_text(json.dumps(dict(status='passed',refs=refs),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(refs),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
