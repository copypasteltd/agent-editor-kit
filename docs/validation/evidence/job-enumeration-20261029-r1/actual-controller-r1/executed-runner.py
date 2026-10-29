"""Run actual CUDA models serially after source bootstrap; preserve all failures."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
out=BASE/'actual-controller-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes());calls=[]
for name in ('run_source63_lipsync_case.py','run_source63_gpu_case.py'):
 print(json.dumps(dict(script=name,status='starting')),flush=True)
 with (out/(name+'.stdout')).open('wb') as stdout,(out/(name+'.stderr')).open('wb') as stderr:
  result=subprocess.run(['C:/Python313/python.exe','-E','-B','-u','-X','utf8',str(ROOT/'docs/validation'/name),'--run','r1'],cwd=ROOT,stdout=stdout,stderr=stderr)
 calls.append(dict(script=name,exit_code=result.returncode));(out/'calls.json').write_text(json.dumps(calls,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(calls[-1]),flush=True)
 if result.returncode:break
report=dict(status='passed' if len(calls)==2 and all(r['exit_code']==0 for r in calls) else 'failed',calls=calls,formal_activation=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');raise SystemExit(0 if report['status']=='passed' else 1)
