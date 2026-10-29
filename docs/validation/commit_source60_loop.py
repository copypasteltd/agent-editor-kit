"""Commit accepted source60 loop work; exclude any still-running test evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')

def main():
    accepted=['targeted-r1','source60-bootstrap-r1','source60-control-r1','source60-selection-r1',
        'source60-semantic-r1','actual-case-r1','source60-gpu-r1','publication-r1','documentation-audit-r1']
    for name in accepted:
        report=json.loads((BASE/name/'verification.json').read_bytes())
        assert report['status']=='passed'
        for path,pin in report.get('file_hashes',{}).items():
            assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==pin
    contract=BASE/'source60-contracts-r1/verification.json'
    if contract.exists():
        report=json.loads(contract.read_bytes());assert report['status']=='passed'
        accepted.append('source60-contracts-r1')
    files=['.gitattributes','README.md','README.en.md','README.zh-TW.md','product/pyproject.toml',
        'product/src/ai_ad_editor/__init__.py','product/src/ai_ad_editor/music_loop.py',
        'product/src/ai_ad_editor/community_cli.py','product/src/ai_ad_editor/capabilities.py',
        'product/src/ai_ad_editor/convert.py','product/tests/test_music_loop.py',
        'docs/product/MUSIC_LOOP.md','docs/product/CASES.md','docs/product/GOAL_GAPS_20261025.md',
        'docs/validation/CLI60循环修复_2026-10-29.md']
    scripts=['run_music_loop_regressions','run_music_loop_case','run_source60_compatibility',
        'run_source60_short_groups','publish_source60_loop','audit_source60_documentation',
        'prepare_source60_delivery','build_source60_delivery','prepare_source60_checks',
        'run_source60_gpu_case','run_source60_installed_regressions',
        'prepare_installed60_loop_case','run_installed60_loop_case','commit_source60_loop']
    files += ['docs/validation/'+name+'.py' for name in scripts]
    files += [p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/assets/music-loop60-20261029-r1').iterdir() if p.is_file()]
    for name in accepted:
        files += [p.relative_to(ROOT).as_posix() for p in (BASE/name).iterdir() if p.is_file()]
    files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
    out=ROOT/'local/agent-ffmpeg/source60-loop-commit-r1';out.mkdir(exist_ok=False)
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pathspec=out/'paths.nul';pathspec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    assert subprocess.check_output([*git,'branch','--show-current'],cwd=ROOT).strip()==b'main'
    assert subprocess.check_output([*git,'rev-parse','HEAD'],cwd=ROOT).strip()==b'f255162d8c7cf069134f4c8b697de4901cdf4532'
    steps=[('add',['add','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','feat: add editable sample-clock music loop overlap repair',
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
    report=dict(status='passed',refs=refs,accepted_groups=accepted,
        source_cli='0.1.60',installed_cli='0.1.59',skill_cli='0.1.59',formal_kit='r57',
        running_contract_evidence_excluded='source60-contracts-r1' not in accepted)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
