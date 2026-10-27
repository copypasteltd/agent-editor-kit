"""Create a fictional engineering portrait through the current installed CUDA CLI."""
from pathlib import Path
import json,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1/portrait-source-r1'
OUT.mkdir(exist_ok=False);(OUT/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
project=ROOT/'local/agent-ffmpeg/lipsync-portrait-source-r1'
launcher='C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
old=json.loads((ROOT/'workspace/vace-smoke-20261016-controlled-v2/summary.json').read_bytes())['adapter']
commands=[['project','init',str(project),'--name','Fictional synthetic portrait source'],
 ['media','adapter','register','--project',str(project),'--adapter-id','portrait_generator','--engine',old['engine'],
 '--model-path',old['model_path'],'--executable',old['executable'],'--evidence',next(a['path'] for a in old['artifacts'] if a['role']=='evidence'),
 '--device','cuda','--license-spdx','Apache-2.0','--verification-status','unverified','--permitted-use','internal'],
 ['media','generate','--project',str(project),'--adapter-id','portrait_generator','--asset-id','fictional_portrait',
 '--mode','text-to-video','--width','512','--height','512','--frames','5','--fps','25','--inference-steps','25',
 '--window-frames','5','--window-overlap','0','--seed','1027','--prompt',
 'A clear studio head-and-shoulders portrait of one fictional adult woman, directly facing the camera, symmetrical frontal face, closed lips, unobstructed mouth and chin, long dark hair behind shoulders, simple teal shirt, neutral light gray background, soft even light, realistic skin, eyes open, static camera, no writing.',
 '--negative-prompt','text, logo, watermark, duplicate face, hand, profile, teeth, open mouth, beard, face covering, blur',
 '--timeout-seconds','1800']]
calls=[]
for i,command in enumerate(commands):
 started=time.monotonic();r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',launcher,*command],cwd=ROOT,
 capture_output=True,timeout=2000,creationflags=subprocess.CREATE_NO_WINDOW)
 (OUT/(str(i)+'.stdout.json')).write_bytes(r.stdout);(OUT/(str(i)+'.stderr.txt')).write_bytes(r.stderr)
 calls.append(dict(command=command,exit_code=r.returncode,seconds=time.monotonic()-started))
 (OUT/'calls.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps(dict(step=i,exit_code=r.returncode,seconds=time.monotonic()-started)),flush=True)
 assert r.returncode==0,(r.stdout[-2000:],r.stderr[-1000:])
print(json.dumps(dict(status='generated',project=str(project),native_CUDA=True,installed_skill=True,real_person_reference=False)))
