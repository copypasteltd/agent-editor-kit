"""Actual missing-installation and missing-stage checks, preserving formal files."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-storage-race-20261029-r1'
out=BASE/'install-stage-gate-check-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
m=json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes());assert m['cli_version']=='0.1.59'
paths=[ROOT/'agent-ffmpeg-local-install-manifest.json',ROOT/'local/agent-ffmpeg/runtime.json',*[ROOT/r['path'] for r in m['files']]]
def pins():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before=pins();assert len(before)==95
calls=[]
for name,args in [('run_source62_install_acceptance.py',[]),('stage_source62_skill.py',['--run','refusal1'])]:
 script=ROOT/'docs/validation'/name;compile(script.read_text(encoding='utf-8'),str(script),'exec')
 result=subprocess.run([sys.executable,'-E','-B','-u','-X','utf8',str(script),*args],cwd=ROOT,capture_output=True)
 (out/(name+'.stdout')).write_bytes(result.stdout);(out/(name+'.stderr')).write_bytes(result.stderr)
 reply=json.loads(result.stdout);assert result.returncode==2 and reply['status']=='pending' and reply['mutated'] is False and reply['missing']
 calls.append(dict(script=name,exit_code=result.returncode,response=reply,sha256=hashlib.sha256(script.read_bytes()).hexdigest()))
assert before==pins()
assert not (BASE/'installed-controller-r1').exists()
assert not (ROOT/'local/agent-ffmpeg/music62-skill-stage-refusal1').exists()
report=dict(status='passed',calls=calls,formal_cli='0.1.59',protected_files=95,registered_files_unchanged=True,no_candidate_or_stage_created=True,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report,ensure_ascii=False))
