"""Actual E-drive rollback with explicitly synthetic gate/CLI inputs.

This checks disk transactions, not model acceptance or real C-drive discovery.
Production files and receipts are never mutated or reused as fixture outputs.
"""
import copy,hashlib,json,runpy,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,r):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
manifest=ROOT/'agent-ffmpeg-local-install-manifest.json';live=load(manifest);assert live['cli_version']=='0.1.59'
protected={str(p):sha(p) for p in [manifest,ROOT/'local/agent-ffmpeg/runtime.json',*[ROOT/r['path'] for r in live['files']]]}
out=BASE/'activation-rollback-r3';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
script=ROOT/'docs/validation/activate_source63_skill.py'
home=ROOT/'local/agent-ffmpeg/source63-activation-rollback-r3';home.mkdir(exist_ok=False)
results=[]
for scenario,fail_write in [('after-transition',1),('after-first-skill-write',2),('entry-verification',None)]:
 root=home/scenario;root.mkdir();base=root/'docs/validation/evidence/job-enumeration-20261029-r1'
 folder=root/'skills/agent-ffmpeg-local-editor'
 for row in live['files']:
  p=root/row['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/row['path']).read_bytes())
 namespace=root/'agent-ffmpeg-local-install-manifest.json';save(namespace,live)
 runtime=root/'local/agent-ffmpeg/runtime.json';runtime.parent.mkdir(parents=True,exist_ok=True);runtime.write_bytes((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
 original={str(p):p.read_bytes() for p in [namespace,runtime,*[root/r['path'] for r in live['files']]]}
 installed=root/'local/agent-ffmpeg/v0.1.0-alpha.4-local.61/final-r1/installed'
 for p in (ROOT/'product/src/ai_ad_editor').glob('*.py'):
  for target in [root/'product/src/ai_ad_editor'/p.name,installed/'site/ai_ad_editor'/p.name]:
   target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
 (installed/'run.py').write_text('# Synthetic fixture launcher;never executed.\n',encoding='utf-8')
 stage=root/'local/agent-ffmpeg/music63-skill-stage-r1/skills/agent-ffmpeg-local-editor'
 for row in live['files']:
  relative=Path(row['path']).relative_to('skills/agent-ffmpeg-local-editor');target=stage/relative
  target.parent.mkdir(parents=True,exist_ok=True);data=(folder/relative).read_bytes()
  if relative.as_posix()=='SKILL.md':data+=b'\nSynthetic CLI63 rollback fixture,not a deliverable.\n'
  target.write_bytes(data)
 files={p.relative_to(stage).as_posix():sha(p) for p in stage.rglob('*') if p.is_file()};assert len(files)==93
 voice=root/'docs/validation/evidence/voice-auditions-20261029-r1/r2/verification.json'
 save(voice,dict(status='passed',synthetic_fixture=True,not_model_acceptance=True))
 provenance=dict(source_cli_version='0.1.61',applied_before_candidate_tests=True,voice_evidence_sha256=sha(voice),actual_voice_samples=103,synthetic_fixture=True)
 save(stage.parents[1]/'STAGING.json',dict(status='unregistered-candidate',cli_version='0.1.63',candidate_files=files,voice_auditions=provenance,gates={str(voice):sha(voice)}))
 def receipt(name,r):save(base/name/'verification.json',{**r,'synthetic_fixture':True,'not_model_acceptance':True})
 receipt('installation-candidate-r1',dict(status='installed-and-byte-verified',cli_version='0.1.63',installed=str(installed),manifest_sha256='sha256:'+'f'*64,registered_skill_file_hashes={p:hashlib.sha256(b).hexdigest() for p,b in original.items()}))
 for mode in ['source63','installed63']:
  pins={p.relative_to(root).as_posix():sha(p) for p in (root/'product/src/ai_ad_editor').glob('*.py')}
  for group,count in [('bootstrap',31),('control',26),('selection',57),('semantic',104),('contracts',406),('loop',37)]:
   run='r2' if mode=='installed63' and group=='contracts' else 'r1'
   receipt(mode+'-'+group+'-'+run,dict(status='passed',cli_version='0.1.63',tests=count,frozen_equal=True,failures=0,errors=0,skipped=0,file_hashes=pins,source_fallback=False,source_and_installed_equal=True,installed=str(installed)))
 for mode in ['source63','installed63','staged63']:
  gpu=copy.deepcopy(load(BASE/'source63-gpu-r1/verification.json'))
  gpu.update(installed=str(installed),source_fallback=False,complete_source_installed_PCM_equal=True,actual_PowerShell_entry=True,candidate_files_unchanged=True,candidate_files=files)
  receipt(mode+'-gpu-r1',gpu)
  lip=copy.deepcopy(load(BASE/'source63-lipsync-cuda-r1/verification.json'))
  lip.update(installed=str(installed),complete_source_installed_master_and_render_equal=True,actual_PowerShell_entry=True,candidate_files_unchanged=True,candidate_files=files)
  receipt(mode+'-lipsync-cuda-r1',lip)
 for name in ['actual-case-r1','installed-actual-case-r1','staged-actual-case-r1']:
  loop=copy.deepcopy(load(BASE/'actual-case-r1/verification.json'))
  loop.update(installed=str(installed),source_fallback=False,complete_source_installed_PCM_equal=True,actual_PowerShell_entry=True,candidate_files=files)
  receipt(name,loop)
 receipt('skill-controller-r1',dict(status='passed',candidate_files=files,installed406_accepted=True,actual_PowerShell_loop_DF3_MuseTalk_passed=True,voice_documentation_tested=True))
 module=runpy.run_path(str(script));main=module['main'];g=main.__globals__
 g['ROOT']=root;g['BASE']=base
 # Map the hardcoded discovery constructor to this E-drive fixture only.
 def fixture_path(value):
  return folder if str(value)=='C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor' else Path(value)
 g['Path']=fixture_path;atomic=g['atomic'];writes=[];cli_calls=[]
 def injected_atomic(path,data):
  atomic(path,data);writes.append(str(path.relative_to(root)))
  if fail_write and len(writes)==fail_write:raise OSError('Injected failure after actual atomic replacement')
 def failed_entry(argv,**kwargs):
  cli_calls.append(list(argv));return SimpleNamespace(returncode=9,stdout=b'',stderr=b'Synthetic entry failure;no child process launched')
 g['atomic']=injected_atomic
 with patch.object(sys,'argv',['activation-fixture','--run','r1','--apply']),patch.object(g['subprocess'],'run',failed_entry):
  try:main()
  except (OSError,AssertionError) as exc:error=repr(exc)
  else:raise AssertionError('Injected failure did not abort activation')
 report=load(base/'skill63-activation-r1/verification.json');assert report['status']=='rolled-back'
 assert len(original)==95 and all(Path(p).read_bytes()==data for p,data in original.items())
 assert not any(p.name.endswith('.tmp') for p in folder.rglob('*')) and not list(runtime.parent.glob('*.tmp'))
 results.append(dict(scenario=scenario,status='passed',actual_atomic_writes=len(writes),restored_files=95,error=error,synthetic_CLI_calls=len(cli_calls),real_C_drive_touched=False,model_inference=False))
assert all(sha(Path(p))==h for p,h in protected.items())
report=dict(status='passed',cases=results,synthetic_gate_inputs=True,synthetic_CLI_failure=True,
 actual_E_drive_file_replacements=True,actual_95_file_rollback=True,production_files_unchanged=95,
 real_C_drive_discovery_tested=False,model_inference=False,formal_activation=False,
 script_sha256=sha(script),full_goal_closed=False)
save(out/'verification.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
