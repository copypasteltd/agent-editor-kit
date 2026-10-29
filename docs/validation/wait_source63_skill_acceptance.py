"""Observe the existing delivery handle, then test its immutable staged Skill."""
import argparse,json,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from run_source62_delivery_pipeline import OwnedProcess
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
def load(p):return json.loads(p.read_bytes())
def save(p,r):
 t=p.with_name('.'+p.name+'.tmp');t.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');t.replace(p)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--pipeline-pid',type=int,required=True);a=parser.parse_args();assert a.pipeline_pid>0
 out=BASE/'skill-wait-controller-r1';out.mkdir(exist_ok=False)
 (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
 handle=None;receipt=BASE/'delivery-pipeline-r1/verification.json'
 try:
  try:handle=OwnedProcess(a.pipeline_pid)
  except OSError:
   assert receipt.is_file() and load(receipt)['status']=='passed','Missing pipeline without accepted terminal receipt'
  while handle and handle.running():
   save(out/'progress.json',dict(status='waiting-existing-delivery',observed_pid=a.pipeline_pid,timestamp_utc=datetime.now(timezone.utc).isoformat(),formal_activation=False))
   time.sleep(5)
  assert receipt.is_file() and load(receipt)['status']=='passed','Existing delivery failed or lacks terminal receipt'
  save(out/'progress.json',dict(status='testing-staged-Skill',formal_activation=False))
  with (out/'skill.stdout').open('wb') as stdout,(out/'skill.stderr').open('wb') as stderr:
   result=subprocess.run(['C:/Python313/python.exe','-E','-B','-u','-X','utf8',str(ROOT/'docs/validation/run_source63_skill_acceptance.py')],cwd=ROOT,stdout=stdout,stderr=stderr)
  assert result.returncode==0,('Skill acceptance failed',result.returncode)
  assert load(BASE/'skill-controller-r1/verification.json')['status']=='passed'
  save(out/'verification.json',dict(status='passed',existing_pipeline_not_restarted=True,skill_checks_passed=True,formal_activation=False,full_goal_closed=False));return 0
 except BaseException as exc:
  save(out/'verification.json',dict(status='failed',error=repr(exc),existing_pipeline_not_restarted=True,formal_activation=False,full_goal_closed=False));raise
 finally:
  if handle:handle.close()
if __name__=='__main__':raise SystemExit(main())
