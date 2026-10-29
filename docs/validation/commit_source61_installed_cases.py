"""Commit completed native installed cases and delivery gates; exclude live403."""
import hashlib,json,os,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(path.read_bytes())


def main():
    publications=[load(BASE/name/'verification.json') for name in
                  ['installed-cases-publication-r1','installed-lipsync-publication-r1']]
    pins={}
    for p in publications:
        assert p['status']=='passed';pins.update(p['file_hashes'])
    assert publications[-1]['README_rows']==491
    assert all(sha(ROOT/p)==h for p,h in pins.items())
    install=load(BASE/'installation-candidate-r1/verification.json')
    assert all(sha(p)==h for p,h in install['registered_skill_file_hashes'].items())
    groups=['installed61-semantic-r1','installed61-gpu-r1','installed-actual-case-r1',
            'installed61-lipsync-cuda-r1','installed-controller-r1','registered-delivery-gate-check-r1',
            'installed-cases-publication-r1','installed-lipsync-publication-r1']
    for name in groups:
        receipt=load(BASE/name/'verification.json');assert receipt['status']=='passed',name
        for p,h in receipt.get('file_hashes',{}).items():
            if name not in ['installed-cases-publication-r1','installed-lipsync-publication-r1']:
                assert sha(ROOT/p)==h
    scripts=['prepare_source61_registered_delivery','check_source61_registered_delivery_gate',
             'run_registered61_loop_case','run_registered61_gpu_case','run_registered61_lipsync_case',
             'build_source61_final_kit','verify_source61_final_kit','publish_source61_installed_cases',
             'publish_source61_installed_lipsync','commit_source61_installed_cases']
    files=list(pins)
    for name in scripts:
        path=ROOT/'docs/validation'/(name+'.py')
        compile(path.read_text(encoding='utf-8'),str(path),'exec');files.append(path.relative_to(ROOT).as_posix())
    for name in groups:
        files.extend(p.relative_to(ROOT).as_posix() for p in (BASE/name).iterdir() if p.is_file())
    files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
    out=ROOT/'local/agent-ffmpeg/source61-installed-cases-commit-r1';out.mkdir(exist_ok=False)
    spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
    assert get(['branch','--show-current'])=='main'
    assert get(['rev-parse','HEAD'])=='f25f1ef4d671e12ae632b14ca36f0ac01eacdeab'
    assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
    steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','test: accept installed CLI61 CUDA replay and guard registered delivery',
                        '--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
    for phase,args in steps:
        result=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
        (out/(phase+'.stdout')).write_bytes(result.stdout);(out/(phase+'.stderr')).write_bytes(result.stderr)
        print(json.dumps(dict(phase=phase,exit_code=result.returncode)),flush=True)
        if result.returncode:return result.returncode
    refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),
              remote=get(['ls-remote','origin','refs/heads/main']).split()[0])
    assert len(set(refs.values()))==1
    result=dict(status='passed',refs=refs,files=len(files),source='0.1.61',candidate='0.1.61',
                formal='0.1.59',README_rows=491,actual_installed_DF3_loop_MuseTalk=True,
                full403_excluded_until_terminal=True,formal_activation=False,full_goal_closed=False)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
