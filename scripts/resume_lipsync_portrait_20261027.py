"""Reuse the registered portrait model; explicitly disable unused window context."""
from pathlib import Path
import json,subprocess,time
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
out=BASE/'portrait-source-r2';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
calls=json.loads((BASE/'portrait-source-r1/calls.json').read_bytes());command=calls[2]['command']+['--temporal-context','none']
launcher='C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1';started=time.monotonic()
r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',launcher,*command],cwd=ROOT,capture_output=True,timeout=2000,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'stdout.json').write_bytes(r.stdout);(out/'stderr.txt').write_bytes(r.stderr)
(out/'verification.json').write_text(json.dumps(dict(status='generated' if r.returncode==0 else 'failed',command=command,exit_code=r.returncode,seconds=time.monotonic()-started),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(exit_code=r.returncode,seconds=time.monotonic()-started)),flush=True)
assert r.returncode==0,(r.stdout[-2000:],r.stderr[-1000:])
