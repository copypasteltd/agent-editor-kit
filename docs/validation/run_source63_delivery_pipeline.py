"""Fail-fast native CLI63 delivery, observing all existing tasks concurrently."""
import argparse,hashlib,json,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from run_source62_delivery_pipeline import OwnedProcess
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
C='C:/Python313/python.exe'
TASKS={'source':'source-controller-r1','actual':'actual-controller-r1','cpu':'cpu-delivery-controller-r1'}
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,r):
 tmp=p.with_name('.'+p.name+'.tmp');tmp.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');tmp.replace(p)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--check-only',action='store_true')
 for name in TASKS:parser.add_argument('--'+name+'-pid',type=int)
 args=parser.parse_args()
 if args.check_only:
  missing=[];rejected=[]
  for name,directory in TASKS.items():
   path=BASE/directory/'verification.json'
   if not path.is_file():missing.append(name)
   elif load(path)['status']!='passed':rejected.append(name)
  print(json.dumps(dict(status='ready' if not missing and not rejected else 'pending',ready=not missing and not rejected,missing=missing,rejected=rejected,mutated=False)),flush=True)
  return 0 if not missing and not rejected else 2
 assert all(getattr(args,name+'_pid') and getattr(args,name+'_pid')>0 for name in TASKS)
 out=BASE/'delivery-pipeline-r1';out.mkdir(exist_ok=False)
 (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
 pending={};handles=[];completed={};calls=[];started=time.monotonic()
 def state(phase):save(out/'progress.json',dict(status='running',phase=phase,timestamp_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,pending={n:h.pid for n,h in pending.items()},completed=list(completed),calls=calls))
 def run(script,*argv):
  state(script)
  with (out/(script+'.stdout')).open('wb') as stdout,(out/(script+'.stderr')).open('wb') as stderr:
   r=subprocess.run([C,'-E','-B','-u','-X','utf8',str(ROOT/'docs/validation'/script),*argv],cwd=ROOT,stdout=stdout,stderr=stderr)
  calls.append(dict(script=script,exit_code=r.returncode));save(out/'calls.json',calls);print(json.dumps(calls[-1]),flush=True)
  assert r.returncode==0,(script,r.returncode)
 try:
  for name,directory in TASKS.items():
   receipt=BASE/directory/'verification.json'
   if receipt.exists():assert load(receipt)['status']=='passed',(name,load(receipt)['status'])
   try:handle=OwnedProcess(getattr(args,name+'_pid'))
   except OSError:
    assert receipt.is_file() and load(receipt)['status']=='passed',('Missing process without passed terminal evidence',name)
    completed[name]=load(receipt)
   else:handles.append(handle);pending[name]=handle
  while pending:
   for name,handle in list(pending.items()):
    if handle.running():continue
    receipt=BASE/TASKS[name]/'verification.json'
    assert receipt.is_file(),('Process ended without terminal evidence',name,handle.pid)
    report=load(receipt);assert report['status']=='passed',(name,report.get('status'))
    completed[name]=report;del pending[name]
   state('waiting-existing-tasks')
   if pending:time.sleep(5)
  pub=BASE/'publication-r1';pub.mkdir(exist_ok=False)
  docs=['README.md','README.zh-TW.md','README.en.md','docs/validation/CLI63原生进程清理_2026-10-29.md']
  assert all('| R507 |' in (ROOT/p).read_text(encoding='utf-8') for p in docs[:3])
  save(pub/'verification.json',dict(status='passed',cli_version='0.1.63',formal_activation=False,file_hashes={p:sha(ROOT/p) for p in docs},full_goal_closed=False,scope='source documentation; no installed/Skill acceptance'))
  run('build_source63_delivery.py','--run','r1')
  run('run_source63_install_acceptance.py')
  run('stage_source63_skill.py','--run','r1')
  report=dict(status='passed',calls=calls,existing_tasks_not_restarted=True,formal_activation=False,stage_scope='unregistered; actual Skill cases and final kit remain required',full_goal_closed=False)
  save(out/'verification.json',report);print(json.dumps(report),flush=True);return 0
 except BaseException as exc:
  save(out/'verification.json',dict(status='failed',error=repr(exc),calls=calls,completed=list(completed),formal_activation=False,full_goal_closed=False));raise
 finally:
  for handle in handles:handle.close()
if __name__=='__main__':raise SystemExit(main())
