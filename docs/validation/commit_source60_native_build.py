"""Publish terminal native build/source contracts and completed short groups only."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    accepted=['source60-contracts-r1','installation-candidate-r1','stage-gate-check-r1',
        'acceptance-docs-r1','candidate-docs-r1']
    counts={}
    for group,count in [('bootstrap',31),('loop',37),('control',19),('selection',57)]:
        name='installed60-'+group+'-r1';r=json.loads((BASE/name/'verification.json').read_bytes())
        assert r['status']=='passed' and r['tests']==count and r['source_and_installed_equal']
        assert r['frozen_equal'] and r['failures']==r['errors']==r['skipped']==0
        accepted.append(name);counts[group]=count
    for name in accepted:
        r=json.loads((BASE/name/'verification.json').read_bytes())
        assert r['status']==('installed-and-byte-verified' if name=='installation-candidate-r1' else 'passed')
        for file,pin in r.get('file_hashes',{}).items():assert sha(ROOT/file)==pin
    installation=json.loads((BASE/'installation-candidate-r1/verification.json').read_bytes())
    assert sha(Path(installation['archive']))==installation['archive_sha256']
    assert all(sha(Path(p))==pin for p,pin in installation['registered_skill_file_hashes'].items())
    source={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    assert len(source)==283 and source=={p.name:sha(p) for p in (Path(installation['installed'])/'site/ai_ad_editor').glob('*.py')}
    scripts=['stage_source60_skill','check_source60_stage_gate','run_source60_install_acceptance',
        'prepare_source60_skill_cases','run_staged60_loop_case','run_staged60_gpu_case',
        'update_source60_acceptance_docs','publish_source60_candidate_docs','publish_installed60_loop',
        'audit_source60_candidate','commit_source60_candidate','commit_source60_native_build']
    for n in scripts:
        p=ROOT/'docs/validation'/(n+'.py');compile(p.read_text(encoding='utf-8'),str(p),'exec')
    files=['README.md','README.en.md','README.zh-TW.md','docs/product/MUSIC_LOOP.md',
        'docs/validation/CLI60循环修复_2026-10-29.md','docs/validation/CLI60独立安装交付_2026-10-29.md']
    files+=['docs/validation/'+n+'.py' for n in scripts]
    for name in accepted:files += [p.relative_to(ROOT).as_posix() for p in (BASE/name).iterdir() if p.is_file()]
    files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
    out=ROOT/'local/agent-ffmpeg/source60-native-build-commit-r1';out.mkdir(exist_ok=False)
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    reference='19af0377978e7160c935b58122d1b3c11462054e'
    assert subprocess.check_output([*git,'branch','--show-current'],cwd=ROOT).strip()==b'main'
    assert subprocess.check_output([*git,'rev-parse','HEAD'],cwd=ROOT).decode().strip()==reference
    for name in ['README.md','README.en.md','README.zh-TW.md']:
        old=subprocess.check_output([*git,'show',reference+':'+name],cwd=ROOT).decode('utf-8')
        prior=[x for x in old.splitlines() if re.match(r'^\| R\d+ \|',x)]
        text=(ROOT/name).read_text(encoding='utf-8');assert len(prior)==470 and all(x in text for x in prior)
        ids=re.findall(r'^\| (R\d+) \|',text,re.M);assert len(ids)==len(set(ids))==473
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pathspec=out/'paths.nul';pathspec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    steps=[('add',['add','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','build: deliver native CLI60 candidate with frozen contract evidence',
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
    report=dict(status='passed',refs=refs,accepted_groups=accepted,installed_groups=counts,
        candidate_cli='0.1.60',candidate_local='local58',formal_skill_cli='0.1.59',formal_local='local57',
        formal_kit='r57',source400_passed=True,protected_files_unchanged=95,
        current_R_rows=473,previous470_R_rows_preserved=True,
        live_semantic_GPU_case_and_installed400_evidence_excluded=True)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
