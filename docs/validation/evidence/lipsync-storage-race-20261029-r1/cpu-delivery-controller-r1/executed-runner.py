"""Native CPU acceptance gates, followed by the original music-loop case."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-storage-race-20261029-r1'
D='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'
C='C:/Python313/python.exe'
out=BASE/'cpu-delivery-controller-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
commands=[(g,[D,'-I','-B','-u','-X','utf8',str(ROOT/'docs/validation/run_source62_regressions.py'),'--group',g,'--run','r1']) for g in ('control','selection','semantic','loop')]
commands += [('actual-loop',[C,'-E','-B','-u','-X','utf8',str(ROOT/'docs/validation/run_source62_loop_case.py'),'--run','r1'])]
calls=[]
for name,command in commands:
 print(json.dumps(dict(phase=name,status='starting')),flush=True)
 with (out/(name+'.stdout')).open('wb') as stdout,(out/(name+'.stderr')).open('wb') as stderr:
  result=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr)
 calls.append(dict(name=name,exit_code=result.returncode));(out/'calls.json').write_text(json.dumps(calls,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(calls[-1]),flush=True)
 if result.returncode:break
report=dict(status='passed' if len(calls)==len(commands) and all(r['exit_code']==0 for r in calls) else 'failed',calls=calls,formal_activation=False,complete_contracts_separate=True)
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');raise SystemExit(0 if report['status']=='passed' else 1)
