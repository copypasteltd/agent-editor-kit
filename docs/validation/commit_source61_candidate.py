"""Commit native61 candidate and completed short gates; exclude live services."""
import hashlib,json,os,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    publication=json.loads((BASE/'candidate-publication-r1/verification.json').read_bytes())
    assert publication['status']=='passed' and publication['README_rows']==486
    assert all(sha(ROOT/p)==h for p,h in publication['file_hashes'].items())
    installation=json.loads((BASE/'installation-candidate-r1/verification.json').read_bytes())
    assert installation['status']=='installed-and-byte-verified' and installation['cli_version']=='0.1.61'
    assert sha(installation['archive'])==installation['archive_sha256']
    assert all(sha(p)==h for p,h in installation['registered_skill_file_hashes'].items())
    groups=['installation-candidate-r1','installed61-bootstrap-r1','installed61-loop-r1',
        'installed61-control-r1','installed61-selection-r1','stage-gate-check-r1',
        'activation-gate-check-r1','candidate-publication-r1']
    for name in groups:
        d=json.loads((BASE/name/'verification.json').read_bytes())
        assert d['status']==('installed-and-byte-verified' if name=='installation-candidate-r1' else 'passed'),name
        assert all(sha(ROOT/p)==h for p,h in d.get('file_hashes',{}).items())
    scripts=['prepare_source61_skill','stage_source61_skill','run_installed61_lipsync_case',
        'check_source61_stage_gate','prepare_source61_skill_cases','run_staged61_loop_case',
        'run_staged61_gpu_case','run_staged61_lipsync_case','prepare_source61_activation',
        'activate_source61_skill','check_source61_activation_gate','run_source61_install_acceptance',
        'publish_source61_candidate','commit_source61_candidate']
    files=['README.md','README.en.md','README.zh-TW.md','docs/product/MUSIC_LOOP.md',
        'docs/validation/CLI61独立安装交付_2026-10-29.md']
    for name in scripts:
        p=ROOT/'docs/validation'/(name+'.py');compile(p.read_text(encoding='utf-8'),str(p),'exec')
        files.append(p.relative_to(ROOT).as_posix())
    for name in groups:files += [p.relative_to(ROOT).as_posix() for p in (BASE/name).iterdir() if p.is_file()]
    files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
    out=ROOT/'local/agent-ffmpeg/source61-candidate-commit-r1';out.mkdir(exist_ok=False)
    spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
    assert get(['branch','--show-current'])=='main'
    assert get(['rev-parse','HEAD'])=='dce96f8886222fd96d53d3b17be93909b6e57247'
    assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
    steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','build: deliver CLI61 native candidate with strict Skill promotion gates',
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
    r=dict(status='passed',refs=refs,files=len(files),source='0.1.61',candidate='0.1.61',candidate_local='local59',
        formal='0.1.59',README_rows=486,live_semantic_full403_and_model_cases_excluded=True,
        full_goal_closed=False)
    (out/'verification.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(json.dumps(r),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
