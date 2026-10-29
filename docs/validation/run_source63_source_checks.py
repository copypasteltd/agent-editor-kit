"""Verify critical cleanup consumers before starting full native contracts."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
C='C:/Python313/python.exe'
D='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'
out=BASE/'source-controller-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes());calls=[]
for group in ('bootstrap','control','loop','lipsync','contracts'):
 prefix=[C,'-I','-S','-B','-u','-X','utf8'] if group=='bootstrap' else [D,'-I','-B','-u','-X','utf8']
 command=[*prefix,str(ROOT/'docs/validation/run_source63_regressions.py'),'--group',group,'--run','r1']
 print(json.dumps(dict(group=group,status='starting')),flush=True)
 with (out/(group+'.stdout')).open('wb') as stdout,(out/(group+'.stderr')).open('wb') as stderr:
  result=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr)
 calls.append(dict(group=group,exit_code=result.returncode));(out/'calls.json').write_text(json.dumps(calls,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(calls[-1]),flush=True)
 if result.returncode:break
report=dict(status='passed' if len(calls)==5 and all(r['exit_code']==0 for r in calls) else 'failed',calls=calls,formal_activation=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');raise SystemExit(0 if report['status']=='passed' else 1)
