"""Commit completed installed59 candidate evidence; exclude live acceptance jobs."""
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-score-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')

def main():
    for name in ['installed59-score-case-r2','installed59-gpu-r1','skill59-draft-entry-r1','candidate-docs-r1']:
        assert json.loads((BASE/name/'verification.json').read_bytes())['status']=='passed'
    files=['.gitattributes','README.md','README.en.md','README.zh-TW.md',
        'docs/product/CASES.md','docs/product/MUSIC_SCORE.md',
        'docs/validation/CLI59独立安装交付_2026-10-29.md']
    files += ['docs/validation/'+name+'.py' for name in [
        'build_source59_delivery','run_source59_installed_regressions',
        'run_source59_install_acceptance','run_installed59_score_case',
        'run_source59_gpu_case','verify_source59_draft_entry',
        'complete_source59_candidate_docs','commit_source59_delivery']]
    names=['post-control-audit-r1','post-control-audit-r2','installation-candidate-r1',
        'source59-gpu-r1','source59-gpu-metadata-audit-r1','installed59-bootstrap-r1',
        'installed59-score-r1','installed59-control-r1','installed59-selection-r1',
        'installed59-semantic-r1','installed59-score-case-r1','installed59-score-case-r2',
        'installed59-gpu-r1','skill59-draft-r1','skill59-draft-entry-r1','candidate-docs-r1']
    # No recursion over large evidence trees, raw workspaces or private runtime files.
    for directory in [*(BASE/name for name in names),ROOT/'docs/assets/music-score59-installed-20261029-r1']:
        assert directory.is_dir()
        files += [p.relative_to(ROOT).as_posix() for p in directory.iterdir() if p.is_file()]
    files=sorted(set(files));assert all((ROOT/name).is_file() for name in files)
    out=ROOT/'local/agent-ffmpeg/source59-delivery-commit-r1';out.mkdir(exist_ok=False)
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pathspec=out/'paths.nul';pathspec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    assert subprocess.check_output([*git,'branch','--show-current'],cwd=ROOT).strip()==b'main'
    steps=[('add',['add','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','build: verify native CLI59 candidate and real music and CUDA replay',
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
