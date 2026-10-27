"""Generate the probe's explicit synthetic speech through the registered Skill."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
out=BASE/'voice-probe-r1';out.mkdir(exist_ok=False)
project=ROOT/'local/agent-ffmpeg/lipsync-voice-probe-r1'
launcher='C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
commands=[['project','init',str(project),'--name','Synthetic lip sync development'],
    ['voice','synthesize','--project',str(project),'--voice','zf_001','--text','这是人工合成的口型演示。声音和画面都可以单独编辑。',
     '--device','cuda','--asset-id','synthetic_speech','--output','assets/derived/synthetic-speech.wav']]
for i,command in enumerate(commands):
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',launcher,*command],
        cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/(str(i)+'.stdout.json')).write_bytes(result.stdout);(out/(str(i)+'.stderr.txt')).write_bytes(result.stderr)
    assert result.returncode==0,(result.returncode,result.stderr.decode('utf8','replace')[-2000:])
    value=json.loads(result.stdout.decode('utf-8-sig'));assert value['ok']
print(json.dumps({'status':'generated','project':str(project),'registered_skill':True,'voice_device':'cuda','source_fallback':False}))
