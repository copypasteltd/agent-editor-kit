"""Commit terminal delivery checks and stricter builder; exclude running403."""
import hashlib,json,os,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    pub=json.loads((BASE/'delivery-publication-r1/verification.json').read_bytes())
    assert pub['status']=='passed' and pub['README_rows']==481
    assert all(sha(ROOT/p)==h for p,h in pub['file_hashes'].items())
    groups=['source61-control-r1','source61-selection-r1','source61-semantic-r1',
        'actual-case-r1','source61-gpu-r1','source61-lipsync-cuda-r1',
        'delivery-checks-controller-r1','build-gate-check-r2','delivery-publication-r1']
    for name in groups:
        d=json.loads((BASE/name/'verification.json').read_bytes());assert d['status']=='passed',name
        if name.startswith('source61-') and 'file_hashes' in d:
            assert all(sha(ROOT/p)==h for p,h in d['file_hashes'].items())
    negative=json.loads((BASE/'build-gate-check-r2/verification.json').read_bytes())
    assert sha(ROOT/'docs/validation/build_source61_delivery.py')==negative['builder_sha256']
    failed=json.loads((BASE/'build-gate-check-r1/verification.json').read_bytes())
    assert failed['status']=='failed' and failed['scope']=='audit-path-comparison'
    scripts=['prepare_source61_delivery','run_source61_delivery_checks','run_source61_loop_case',
        'run_source61_gpu_case','run_installed61_loop_case','run_source61_lipsync_case',
        'build_source61_delivery','check_source61_build_gate','publish_source61_delivery_checks',
        'commit_source61_delivery_checks']
    files=['README.md','README.en.md','README.zh-TW.md','docs/validation/CLI61原生交付核验_2026-10-29.md']
    for name in scripts:
        p=ROOT/'docs/validation'/(name+'.py');compile(p.read_text(encoding='utf-8'),str(p),'exec')
        files.append(p.relative_to(ROOT).as_posix())
    for name in [*groups,'build-gate-check-r1']:
        files += [p.relative_to(ROOT).as_posix() for p in (BASE/name).iterdir() if p.is_file()]
    files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
    assert not any('source61-contracts-r1/' in p for p in files)
    out=ROOT/'local/agent-ffmpeg/source61-delivery-checks-commit-r1';out.mkdir(exist_ok=False)
    spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
    assert get(['branch','--show-current'])=='main'
    assert get(['rev-parse','HEAD'])=='00b724855d4d76c58d55697a1170589b1d73da56'
    assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
    steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','build: verify CLI61 real CUDA replay and fail-closed delivery gates',
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
    r=dict(status='passed',refs=refs,files=len(files),source='0.1.61',installed_candidate='0.1.60',
        formal='0.1.59',real_DF3_and_MuseTalk_CUDA=True,full403_excluded=True,full_goal_closed=False)
    (out/'verification.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(json.dumps(r),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
