"""Verify missing-gate refusal and actual atomic file cleanup without activation."""
import hashlib,json,runpy,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
out=BASE/'activation-preflight-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
manifest=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(manifest);assert m['cli_version']=='0.1.59'
guard={str(p):sha(p) for p in [manifest,ROOT/'local/agent-ffmpeg/runtime.json',*[ROOT/r['path'] for r in m['files']]]}
script=ROOT/'docs/validation/activate_source63_skill.py';calls=[]
for name,args in [('dry-run',[]),('apply-refusal',['--apply'])]:
 r=subprocess.run([sys.executable,'-E','-B','-u','-X','utf8',str(script),'--run','preflight1',*args],cwd=ROOT,capture_output=True,timeout=120)
 (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
 assert r.returncode==2,(name,r.stderr)
 reply=json.loads(r.stdout);assert reply['status']=='pending' and reply['mutated'] is False and reply['activated'] is False
 calls.append(dict(name=name,exit_code=r.returncode,reply=reply))
assert not (BASE/'skill63-activation-preflight1').exists()
atomic=runpy.run_path(str(script))['atomic']
work=ROOT/'local/agent-ffmpeg/source63-activation-atomic-check-r1';work.mkdir(exist_ok=False)
target=work/'target.txt';atomic(target,b'old');atomic(target,b'new');assert target.read_bytes()==b'new'
directory=work/'directory';directory.mkdir()
try:atomic(directory,b'cannot replace directory')
except OSError as exc:failure=type(exc).__name__
else:raise AssertionError('Directory replacement unexpectedly accepted')
assert directory.is_dir() and not list(work.glob('*.tmp'))
assert all(sha(Path(p))==pin for p,pin in guard.items())
report=dict(status='passed',calls=calls,formal_files_unchanged=95,actual_atomic_replacement=True,
 actual_failed_replace_temp_cleanup=True,failed_replace_error=failure,script_sha256=sha(script),
 rollback_transition_executed=False,formal_activation=False,model_inference=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
