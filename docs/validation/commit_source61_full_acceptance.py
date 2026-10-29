"""Commit terminal full403 and private visual-review evidence; never live build logs."""
import hashlib,json,os,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    accepted=json.loads((BASE/'source-acceptance-r1/verification.json').read_bytes())
    assert accepted['status']=='passed' and accepted['full_contracts']==403 and accepted['README_rows']==483
    assert all(sha(ROOT/p)==h for p,h in accepted['file_hashes'].items())
    full=json.loads((BASE/'source61-contracts-r1/verification.json').read_bytes())
    assert full['status']=='passed' and full['frozen_equal']
    assert all(sha(ROOT/p)==h for p,h in full['file_hashes'].items())
    preview=json.loads((BASE/'private-frame-preview-r1/verification.json').read_bytes())
    assert preview['status']=='passed' and sha(preview['contact_sheet'])==preview['contact_sheet_sha256']
    scripts=['inspect_source61_lipsync_frames','publish_source61_final_checks',
        'run_source61_install_acceptance','commit_source61_full_acceptance']
    files=['README.md','README.en.md','README.zh-TW.md',
        'docs/validation/CLI61完整源码验收_2026-10-29.md',
        'docs/validation/CLI61口型抽帧目检_2026-10-29.md']
    for name in scripts:
        p=ROOT/'docs/validation'/(name+'.py');compile(p.read_text(encoding='utf-8'),str(p),'exec')
        files.append(p.relative_to(ROOT).as_posix())
    for name in ['source-acceptance-r1','source61-contracts-r1','private-frame-preview-r1']:
        files += [p.relative_to(ROOT).as_posix() for p in (BASE/name).iterdir() if p.is_file()]
    files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
    assert all(not p.endswith(('.png','.mp4','.raw')) for p in files)
    out=ROOT/'local/agent-ffmpeg/source61-full-acceptance-commit-r1';out.mkdir(exist_ok=False)
    spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
    assert get(['branch','--show-current'])=='main'
    assert get(['rev-parse','HEAD'])=='1eb65e2b8445c315a534649d307033a0603cf03d'
    assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
    steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','test: accept CLI61 full contracts and record lip-sync visual limits',
        '--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
    for name,args in steps:
        p=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
        (out/(name+'.stdout')).write_bytes(p.stdout);(out/(name+'.stderr')).write_bytes(p.stderr)
        print(json.dumps(dict(phase=name,exit_code=p.returncode)),flush=True)
        if p.returncode:
            print(p.stdout.decode('utf-8','replace')[-1500:]+p.stderr.decode('utf-8','replace')[-1500:],flush=True)
            return p.returncode
    refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),remote=get(['ls-remote','origin','refs/heads/main']).split()[0])
    assert len(set(refs.values()))==1
    r=dict(status='passed',refs=refs,files=len(files),source='0.1.61',source403_accepted=True,
        formal='0.1.59',new_native_build_excluded=True,README_rows=483,
        agent_visual_review=True,natural_quality_accepted=False,full_goal_closed=False)
    (out/'verification.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(json.dumps(r),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
