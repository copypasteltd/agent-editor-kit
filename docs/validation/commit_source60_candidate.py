"""Commit independently accepted CLI60 candidate; never include live400 logs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')

def main():
    accepted=['source60-contracts-r1','installation-candidate-r1','stage-gate-check-r1',
        'acceptance-docs-r1','candidate-docs-r1','installed60-bootstrap-r1','installed60-loop-r1',
        'installed60-control-r1','installed60-selection-r1','installed60-semantic-r1',
        'installed60-gpu-r1','installed-actual-case-r1','installed-publication-r1','candidate-audit-r1']
    for name in accepted:
        r=json.loads((BASE/name/'verification.json').read_bytes())
        assert r['status']==('installed-and-byte-verified' if name=='installation-candidate-r1' else 'passed')
        for path,pin in r.get('file_hashes',{}).items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==pin
    terminal=BASE/'installed60-contracts-r1/verification.json'
    if terminal.exists():
        r=json.loads(terminal.read_bytes());assert r['status']=='passed';accepted.append('installed60-contracts-r1')
    files=['.gitattributes','README.md','README.en.md','README.zh-TW.md','docs/product/MUSIC_LOOP.md',
        'docs/product/CASES.md','docs/validation/CLI60循环修复_2026-10-29.md',
        'docs/validation/CLI60独立安装交付_2026-10-29.md']
    scripts=['stage_source60_skill','check_source60_stage_gate','run_source60_install_acceptance',
        'prepare_source60_skill_cases','run_staged60_loop_case','run_staged60_gpu_case',
        'update_source60_acceptance_docs','publish_source60_candidate_docs','publish_installed60_loop',
        'audit_source60_candidate','commit_source60_candidate']
    files += ['docs/validation/'+n+'.py' for n in scripts]
    files += [p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/assets/music-loop60-installed-20261029-r1').iterdir() if p.is_file()]
    for name in accepted:files += [p.relative_to(ROOT).as_posix() for p in (BASE/name).iterdir() if p.is_file()]
    files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
    out=ROOT/'local/agent-ffmpeg/source60-candidate-commit-r1';out.mkdir(exist_ok=False)
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pathspec=out/'paths.nul';pathspec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    assert subprocess.check_output([*git,'branch','--show-current'],cwd=ROOT).strip()==b'main'
    preliminary=ROOT/'local/agent-ffmpeg/source60-native-build-commit-r1/verification.json'
    expected='19af0377978e7160c935b58122d1b3c11462054e'
    if preliminary.exists():
        p=json.loads(preliminary.read_bytes());assert p['status']=='passed';expected=p['refs']['head']
    assert subprocess.check_output([*git,'rev-parse','HEAD'],cwd=ROOT).decode().strip()==expected
    steps=[('add',['add','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','build: verify native CLI60 candidate and installed loop audio',
        '--pathspec-from-file='+str(pathspec),'--pathspec-file-nul'])]
    for name,args in steps:
        p=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
        (out/(name+'.stdout')).write_bytes(p.stdout);(out/(name+'.stderr')).write_bytes(p.stderr)
        print(json.dumps(dict(phase=name,exit_code=p.returncode)),flush=True)
        if p.returncode:print(p.stderr.decode('utf-8','replace')[-2000:],flush=True);return p.returncode
    refs={}
    for name,args in [('head',['rev-parse','HEAD']),('origin',['rev-parse','origin/main']),('remote',['ls-remote','origin','refs/heads/main'])]:
        refs[name]=subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().split()[0]
    assert len(set(refs.values()))==1
    report=dict(status='passed',refs=refs,accepted_groups=accepted,candidate_cli='0.1.60',formal_skill_cli='0.1.59',
        candidate_local_release='local58',formal_local_release='local57',formal_kit='r57',
        installed400_live_evidence_excluded='installed60-contracts-r1' not in accepted)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
