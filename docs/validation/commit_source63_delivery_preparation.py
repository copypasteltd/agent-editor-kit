"""Commit verified CLI63 cleanup code and scoped evidence; normal main autopush."""
import hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=load(BASE/'source63-native-job-r2/verification.json');assert r['status']=='passed' and r['tests']==11
assert all(sha(ROOT/p)==h for p,h in r['file_hashes'].items())
assert load(BASE/'baseline62-r1/verification.json')['status']=='failed'
for group,n in [('bootstrap',31),('control',26),('loop',37)]:
 r=load(BASE/f'source63-{group}-r1/verification.json');assert r['status']=='passed' and r['tests']==n and r['frozen_equal']
 assert all(sha(ROOT/p)==h for p,h in r['file_hashes'].items())
m=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert m['cli_version']=='0.1.59'
assert all(sha(ROOT/r['path'])==r['sha256'] for r in m['files'])
gate=load(BASE/'delivery-gate-check-r1/verification.json');assert gate['status']=='passed' and gate['formal_files_unchanged']==95
assert gate['failed_task_detected_while_other_tasks_live'] and gate['observer_handles_closed']
for call in gate['calls']:assert sha(ROOT/'docs/validation'/call['script'])==call['sha256']
selection=load(BASE/'source63-selection-r1/verification.json');assert selection['status']=='passed' and selection['tests']==57 and selection['frozen_equal']
assert all(sha(ROOT/p)==h for p,h in selection['file_hashes'].items())
names=['run_source63_loop_case','build_source63_delivery','run_source63_install_acceptance','run_installed63_loop_case','run_installed63_lipsync_case','stage_source63_skill','run_source63_cpu_delivery','run_source63_delivery_pipeline','check_source63_delivery_gates','commit_source63_delivery_preparation']
files=['README.md','README.zh-TW.md','README.en.md','docs/validation/CLI63候选交付门禁_2026-10-29.md']+['docs/validation/'+n+'.py' for n in names]
for n in names:
 p=ROOT/'docs/validation'/(n+'.py');compile(p.read_text(encoding='utf-8'),str(p),'exec')
for directory in (BASE/'source63-selection-r1',BASE/'delivery-gate-check-r1',BASE/'delivery-gate-check-r1/fail-fast-case/actual-controller-r1',BASE/'delivery-gate-check-r1/fail-fast-case/delivery-pipeline-r1'):
 files += [p.relative_to(ROOT).as_posix() for p in directory.iterdir() if p.is_file()]
files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
out=ROOT/'local/agent-ffmpeg/source63-delivery-preparation-commit-r1';out.mkdir(exist_ok=False)
spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
assert get(['branch','--show-current'])=='main'
assert get(['rev-parse','HEAD'])=='93f99919e6d997da67bcae1f55dbb6790779dd7e'
assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
steps += [('commit',['commit','--only','-m','feat: gate CLI63 native delivery and observe existing tasks concurrently','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
for phase,args in steps:
 result=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
 (out/(phase+'.stdout')).write_bytes(result.stdout);(out/(phase+'.stderr')).write_bytes(result.stderr)
 print(json.dumps(dict(phase=phase,exit_code=result.returncode)),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),remote=get(['ls-remote','origin','refs/heads/main']).split()[0]);assert len(set(refs.values()))==1
receipt=dict(status='passed',refs=refs,files=len(files),source='0.1.63',candidate='0.1.61',formal='0.1.59',README_rows=509,native_tests=11,control_tests=26,loop_tests=37,bootstrap_tests=31,formal_activation=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
