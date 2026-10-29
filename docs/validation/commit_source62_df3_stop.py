"""Commit actual DF3 and explicit stopped-candidate evidence."""
import json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-storage-race-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
r=json.loads((BASE/'source62-lipsync-r3/verification.json').read_bytes())
assert json.loads((BASE/'process-observer-check-r1/verification.json').read_bytes())['status']=='passed'
lip=json.loads((BASE/'source62-lipsync-cuda-r1/verification.json').read_bytes())
assert lip['status']=='passed' and lip['actual_MuseTalk_CUDA'] and lip['complete_package_rendered_RGBA_PCM_equal']
loop=json.loads((BASE/'source62-loop-r1/verification.json').read_bytes())
assert loop['status']=='failed' and loop['tests']==37 and loop['errors']==1
assert json.loads((BASE/'job-enumeration-probe-r1/verification.json').read_bytes())['status']=='not-reproduced'
semantic=json.loads((BASE/'source62-semantic-r1/verification.json').read_bytes())
assert semantic['status']=='passed' and semantic['tests']==104 and semantic['frozen_equal']
selection=json.loads((BASE/'source62-selection-r1/verification.json').read_bytes())
assert selection['status']=='passed' and selection['tests']==57 and selection['frozen_equal']
assert json.loads((BASE/'install-stage-gate-check-r1/verification.json').read_bytes())['status']=='passed'
control=json.loads((BASE/'source62-control-r1/verification.json').read_bytes())
assert control['status']=='passed' and control['tests']==19 and control['frozen_equal']
assert json.loads((BASE/'build-gate-check-r1/verification.json').read_bytes())['status']=='passed'
assert r['status']=='passed' and r['legacy_race_reproduced'] and r['tests']==34 and r['skips']==0
import hashlib
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in r['file_hashes'].items())
files=['README.md','README.zh-TW.md','README.en.md','docs/validation/CLI62口型存储竞争修复_2026-10-29.md','docs/validation/run_source62_score_cleanup_probe.py','docs/validation/commit_source62_df3_stop.py']
for directory in (BASE/'source62-gpu-r1',BASE/'source62-contracts-r1',BASE/'delivery-pipeline-r1'):
 files += [p.relative_to(ROOT).as_posix() for p in directory.iterdir() if p.is_file()]
gpu=json.loads((BASE/'source62-gpu-r1/verification.json').read_bytes())
assert gpu['status']=='passed' and gpu['actual_CUDA_model'] and gpu['complete_PCM_replay_equal']
assert json.loads((BASE/'source62-contracts-r1/verification.json').read_bytes())['status']=='interrupted'
assert json.loads((BASE/'delivery-pipeline-r1/verification.json').read_bytes())['status']=='failed'
files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
out=ROOT/'local/agent-ffmpeg/source62-df3-stop-commit-r2';out.mkdir(exist_ok=False)
spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
assert get(['branch','--show-current'])=='main'
assert get(['rev-parse','HEAD'])=='5361f6051c3440b7ffffb6bfee0a9fe216dfab25'
assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
for phase,args in [('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul']),('check',['diff','--cached','--check','--',*[p for p in files if not p.endswith('source62-contracts-r1/tests.stderr')]]),('check-interrupted-raw',['-c','core.whitespace=-blank-at-eol','diff','--cached','--check','--','docs/validation/evidence/lipsync-storage-race-20261029-r1/source62-contracts-r1/tests.stderr']),('commit',['commit','--only','-m','test: accept actual CLI62 DF3 and preserve interrupted candidate','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]:
 result=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
 (out/(phase+'.stdout')).write_bytes(result.stdout);(out/(phase+'.stderr')).write_bytes(result.stderr)
 print(json.dumps(dict(phase=phase,exit_code=result.returncode)),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),remote=get(['ls-remote','origin','refs/heads/main']).split()[0]);assert len(set(refs.values()))==1
receipt=dict(status='passed',refs=refs,files=len(files),source='0.1.62',candidate='0.1.61',formal='0.1.59',tests=34,README_rows=503,formal_activation=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
