"""Missing-gate refusals and fail-fast observation of real Windows processes."""
import contextlib,hashlib,importlib.util,io,json,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
out=BASE/'delivery-gate-check-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert m['cli_version']=='0.1.59'
protected=[ROOT/'agent-ffmpeg-local-install-manifest.json',ROOT/'local/agent-ffmpeg/runtime.json',*[ROOT/r['path'] for r in m['files']]]
def pins():return {p.relative_to(ROOT).as_posix():sha(p) for p in protected}
before=pins();assert len(before)==95
calls=[]
for name,args,code in [('build_source63_delivery.py',['--run','refusal1'],1),('run_source63_install_acceptance.py',[],2),('stage_source63_skill.py',['--run','refusal1'],2),('run_source63_delivery_pipeline.py',['--check-only'],2)]:
 script=ROOT/'docs/validation'/name;compile(script.read_text(encoding='utf-8'),str(script),'exec')
 r=subprocess.run([sys.executable,'-E','-B','-u','-X','utf8',str(script),*args],cwd=ROOT,capture_output=True)
 (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
 assert r.returncode==code,(name,r.returncode,r.stderr[-1000:])
 reply=json.loads(r.stderr if code==1 else r.stdout)
 assert reply['status'] in ('pending','rejected')
 calls.append(dict(script=name,exit_code=r.returncode,reply=reply,sha256=sha(script)))
# Simulate one failing task while the other two real native tasks remain alive.
script=ROOT/'docs/validation/run_source63_delivery_pipeline.py'
spec=importlib.util.spec_from_file_location('delivery63',script);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
fixture=out/'fail-fast-case';fixture.mkdir();module.BASE=fixture
children=[];handles=[];real_observer=module.OwnedProcess
try:
 for name in ('source','actual','cpu'):
  p=subprocess.Popen([sys.executable,'-I','-S','-B','-c','import sys;sys.stdin.buffer.read(1);sys.exit(3)'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
  children.append(p)
 def observe(pid):
  handle=real_observer(pid);handles.append(handle)
  if len(handles)==3:
   receipt=fixture/'actual-controller-r1/verification.json';receipt.parent.mkdir();receipt.write_text('{"status":"failed","fixture":true}\n',encoding='utf-8')
   children[1].stdin.write(b'x');children[1].stdin.close()
  return handle
 argv=['delivery63','--source-pid',str(children[0].pid),'--actual-pid',str(children[1].pid),'--cpu-pid',str(children[2].pid)]
 started=time.monotonic()
 with patch.object(module,'OwnedProcess',observe),patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
  try:module.main()
  except AssertionError as exc:observed_error=repr(exc)
  else:raise AssertionError('Failed task was accepted')
 elapsed=time.monotonic()-started
 assert elapsed<15 and children[0].poll() is None and children[2].poll() is None
 assert all(h.handle is None for h in handles)
 failure=load(fixture/'delivery-pipeline-r1/verification.json');assert failure['status']=='failed' and failure['calls']==[]
 assert not (fixture/'publication-r1').exists()
finally:
 for child in children:
  if child.poll() is None:child.kill()
  child.wait(timeout=30)
  if child.stdin and not child.stdin.closed:child.stdin.close()
assert before==pins()
assert not (BASE/'installation-candidate-refusal1').exists() and not (BASE/'installed-controller-r1').exists()
assert not (ROOT/'local/agent-ffmpeg/music63-skill-stage-refusal1').exists()
report=dict(status='passed',calls=calls,actual_Windows_process_fail_fast=True,fixture_failure_synthetic=True,failed_task_detected_while_other_tasks_live=True,observer_handles_closed=True,fixture_children_exited=True,fail_fast_seconds=elapsed,observed_error=observed_error,formal_files_unchanged=95,formal_activation=False,model_inference=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report,ensure_ascii=False))
