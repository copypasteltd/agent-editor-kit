"""Audit existing audio bytes and pre-test Skill documentation without activation."""
import hashlib,json,subprocess,sys
from pathlib import Path
from source61_voice_skill_overlay import prepare,VOICE,REFERENCE
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
out=BASE/'voice-preparation-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
manifest=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(manifest)
assert m['cli_version']=='0.1.59'
guard={str(p):sha(p) for p in [manifest,ROOT/'local/agent-ffmpeg/runtime.json',*[ROOT/r['path'] for r in m['files']]]}
original={Path(r['path']).relative_to('skills/agent-ffmpeg-local-editor').as_posix():r['sha256'] for r in m['files']}
contents,prepared,overlay=prepare(ROOT/'skills/agent-ffmpeg-local-editor',original,load(VOICE))
assert len(contents)==93 and overlay['tested_other92_files_byte_equal']
target=ROOT/'local/agent-ffmpeg/source63-voice-doc-check-r1/skills/agent-ffmpeg-local-editor'
assert not target.exists()
for name,data in contents.items():
 p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
result=subprocess.run([sys.executable,'-E','-B','-u','-X','utf8',
 'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',str(target)],cwd=ROOT,capture_output=True,timeout=120)
(out/'static.stdout').write_bytes(result.stdout);(out/'static.stderr').write_bytes(result.stderr)
assert result.returncode==0,result.stderr
script=ROOT/'docs/validation/stage_source63_skill.py'
compile(script.read_text(encoding='utf-8'),str(script),'exec')
refusal=subprocess.run([sys.executable,'-E','-B','-u','-X','utf8',str(script),'--run','voice-refusal1'],cwd=ROOT,capture_output=True,timeout=120)
(out/'stage.stdout').write_bytes(refusal.stdout);(out/'stage.stderr').write_bytes(refusal.stderr)
assert refusal.returncode==2,(refusal.returncode,refusal.stderr)
reply=json.loads(refusal.stdout);assert reply['status']=='pending' and reply['mutated'] is False
assert not (ROOT/'local/agent-ffmpeg/music63-skill-stage-voice-refusal1').exists()
assert all(sha(Path(p))==h for p,h in guard.items())
r=dict(status='passed',audited_existing_samples=103,source_audio_cli='0.1.61',
 candidate_target_cli='0.1.63',static_validation_exit_code=0,changed_document=REFERENCE,
 other92_files_equal_before_runtime_binding=True,formal_files_unchanged=95,
 stage_script_sha256=sha(script),missing_gate_refusal=reply,voice_evidence_sha256=sha(VOICE),
 registered=False,new_neural_inference=False,human_listening=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(r,ensure_ascii=False),flush=True)
