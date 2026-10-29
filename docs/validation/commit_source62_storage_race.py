"""Scoped native commit/push after verified CLI62 storage-race regressions."""
import json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-storage-race-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
r=json.loads((BASE/'source62-lipsync-r3/verification.json').read_bytes())
assert r['status']=='passed' and r['legacy_race_reproduced'] and r['tests']==34 and r['skips']==0
import hashlib
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in r['file_hashes'].items())
files=list(r['file_hashes'])+['README.md','README.zh-TW.md','README.en.md','docs/validation/CLI62口型存储竞争修复_2026-10-29.md','docs/validation/run_source62_storage_race.py','docs/validation/commit_source62_storage_race.py','docs/validation/run_source62_storage_delivery.py','docs/validation/run_source62_regressions.py']
for directory in (BASE/'source62-bootstrap-r1',BASE/'source62-lipsync-r1',BASE/'source62-lipsync-r2',BASE/'source62-lipsync-r3',ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1/skill-controller-r1',ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1/staged61-lipsync-cuda-r1'):
 files += [p.relative_to(ROOT).as_posix() for p in directory.iterdir() if p.is_file()]
files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
out=ROOT/'local/agent-ffmpeg/source62-storage-race-commit-r1';out.mkdir(exist_ok=False)
spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
assert get(['branch','--show-current'])=='main'
assert get(['rev-parse','HEAD'])=='37e3309c40a5c6f87d859bc7afa516445983ba8f'
assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
for phase,args in [('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul']),('check',['diff','--cached','--check','--',*files]),('commit',['commit','--only','-m','fix: tolerate atomic progress renames in lipsync storage budgets','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]:
 result=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
 (out/(phase+'.stdout')).write_bytes(result.stdout);(out/(phase+'.stderr')).write_bytes(result.stderr)
 print(json.dumps(dict(phase=phase,exit_code=result.returncode)),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),remote=get(['ls-remote','origin','refs/heads/main']).split()[0]);assert len(set(refs.values()))==1
receipt=dict(status='passed',refs=refs,files=len(files),source='0.1.62',candidate='0.1.61',formal='0.1.59',tests=34,README_rows=497,formal_activation=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
