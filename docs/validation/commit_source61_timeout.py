"""Commit actual source61 fix plus terminal CLI60 evidence; exclude live logs."""
import hashlib,json,os,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
OLD=ROOT/'docs/validation/evidence/music-loop-20261029-r1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    publication=json.loads((BASE/'publication-r1/verification.json').read_bytes())
    assert publication['status']=='passed' and publication['source_cli']=='0.1.61'
    assert all(sha(ROOT/p)==v for p,v in publication['file_hashes'].items())
    groups=['source61-lipsync-r1','source61-bootstrap-r1','source61-loop-r1','publication-r1']
    for n in groups:
        r=json.loads((BASE/n/'verification.json').read_bytes());assert r['status']=='passed'
        assert all(sha(ROOT/p)==v for p,v in r.get('file_hashes',{}).items())
    oldgroups=['installed60-semantic-r1','installed60-gpu-r1','installed-actual-case-r1',
        'installed-publication-r1','candidate-audit-r1','candidate-audit-r2','native-cuda-probe-r1',
        'staged-actual-case-r1','staged60-gpu-r1','draft-audit-r1','activation-gate-check-r1',
        'installed60-contracts-r1']
    for n in oldgroups:
        r=json.loads((OLD/n/'verification.json').read_bytes())
        assert r['status']==('failed' if n in ['candidate-audit-r1','installed60-contracts-r1'] else 'passed'),(n,r['status'])
    files=['.gitattributes','README.md','README.en.md','README.zh-TW.md',
        'product/pyproject.toml','product/src/ai_ad_editor/__init__.py',
        'product/src/ai_ad_editor/lipsync_pipeline.py','product/tests/test_lipsync.py',
        'scripts/package_community_skill.py','docs/product/LIP_SYNC.md','docs/product/MUSIC_LOOP.md',
        'docs/product/CASES.md','docs/validation/CLI60循环修复_2026-10-29.md',
        'docs/validation/CLI60独立安装交付_2026-10-29.md',
        'docs/validation/CLI60统一Skill草稿验收_2026-10-29.md',
        'docs/validation/CLI61口型超时修复_2026-10-29.md']
    scripts=['prepare_source60_skill_cases','run_staged60_loop_case','run_staged60_gpu_case',
        'publish_installed60_loop','audit_source60_candidate','probe_source60_native_cuda',
        'prepare_source60_draft','draft_source60_skill','audit_source60_draft',
        'prepare_source60_activation','activate_source60_skill','check_source60_activation_gate',
        'prepare_registered60_cases','run_registered60_loop_case','run_registered60_gpu_case',
        'prepare_source60_final_kit','build_source60_final_kit','verify_source60_final_kit',
        'run_source61_regressions','publish_source61_timeout','commit_source61_timeout']
    for n in scripts:
        p=ROOT/'docs/validation'/(n+'.py');compile(p.read_text(encoding='utf-8'),str(p),'exec')
        files.append(p.relative_to(ROOT).as_posix())
    for base,names in [(BASE,groups),(OLD,oldgroups)]:
        for n in names:
            files += [p.relative_to(ROOT).as_posix() for p in (base/n).iterdir() if p.is_file()]
    files += [p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/assets/music-loop60-installed-20261029-r1').iterdir() if p.is_file()]
    files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
    out=ROOT/'local/agent-ffmpeg/source61-timeout-commit-r1';out.mkdir(exist_ok=False)
    spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
    assert get(['branch','--show-current'])=='main'
    assert get(['rev-parse','HEAD'])=='3989e4a166c46daa576880c6544a86e5080d9f5d'
    assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
    steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','fix: unify lip-sync operation timeout and preserve failed install evidence',
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
    r=dict(status='passed',refs=refs,files=len(files),source='0.1.61',candidate='0.1.60',formal='0.1.59',
        failed_installed400_preserved=True,live_source403_excluded=True,full_goal_closed=False)
    (out/'verification.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(json.dumps(r),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
