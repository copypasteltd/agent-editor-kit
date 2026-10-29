"""Check registered-entry and final-kit missing-gate refusal without promotion."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
out=BASE/'registered-preflight-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
m=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert m['cli_version']=='0.1.59'
guard={str(p):sha(p) for p in [ROOT/'agent-ffmpeg-local-install-manifest.json',ROOT/'local/agent-ffmpeg/runtime.json',*[ROOT/r['path'] for r in m['files']]]}
names=['prepare_source63_registered_checks.py','run_source63_registered_acceptance.py','build_source63_final_kit.py','verify_source63_final_kit.py',*[f'run_registered63_{n}_case.py' for n in ['loop','gpu','lipsync']]]
script_hashes={}
for name in names:
 p=ROOT/'docs/validation'/name;compile(p.read_text(encoding='utf-8'),str(p),'exec');script_hashes[name]=sha(p)
calls=[]
for name,args in [('run_source63_registered_acceptance.py',[]),('build_source63_final_kit.py',['--run','preflight1'])]:
 r=subprocess.run([sys.executable,'-E','-B','-u','-X','utf8',str(ROOT/'docs/validation'/name),*args],cwd=ROOT,capture_output=True,timeout=120)
 (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
 assert r.returncode==2,(name,r.stderr)
 reply=json.loads(r.stdout);assert reply['status']=='pending' and reply['mutated'] is False
 calls.append(dict(script=name,exit_code=r.returncode,reply=reply))
assert not (BASE/'registered-controller-r1').exists() and not (BASE/'formal-kit-build-preflight1').exists()
assert not (ROOT/'local/agent-ffmpeg/music63-kit-preflight1').exists()
assert all(sha(Path(p))==h for p,h in guard.items())
report=dict(status='passed',calls=calls,compiled_scripts=script_hashes,formal_files_unchanged=95,
 registered_case_executed=False,final_kit_built=False,formal_activation=False,model_inference=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
