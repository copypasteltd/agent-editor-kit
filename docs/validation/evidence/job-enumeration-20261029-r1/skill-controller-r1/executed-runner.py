"""Exercise the final staged CLI63 Skill after all installed gates pass."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 path=ROOT/'local/agent-ffmpeg/music63-skill-stage-r1/STAGING.json'
 if not path.is_file():
  print(json.dumps(dict(status='pending',missing=['accepted-staged-Skill'],mutated=False)),flush=True);return 2
 stage=load(path);assert stage['status']=='unregistered-candidate' and stage['cli_version']=='0.1.63'
 assert stage['requires_installed406'] and stage['voice_auditions']['applied_before_candidate_tests']
 for p,h in stage['gates'].items():assert sha(Path(p))==h
 contract=load(BASE/'installed63-contracts-r2/verification.json')
 assert contract['status']=='passed' and contract['tests']==406 and contract['frozen_equal']
 assert contract['failures']==contract['errors']==contract['skipped']==0
 assert all(sha(ROOT/p)==h for p,h in contract['file_hashes'].items())
 skill=Path(stage['skill']);installed=stage['installed'];guard=stage['protected_files']
 def check():
  assert all(sha(Path(p))==h for p,h in guard.items())
  assert stage['candidate_files']=={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}
 check()
 out=BASE/'skill-controller-r1';out.mkdir(exist_ok=False)
 (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
 prefix=['C:/Python313/python.exe','-E','-B','-u','-X','utf8']
 cases=[('static',[*prefix,'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',str(skill)])]
 for name in ('loop','gpu','lipsync'):
  cases.append((name,[*prefix,str(ROOT/f'docs/validation/run_staged63_{name}_case.py'),'--run','r1','--installed',installed,'--skill',str(skill)]))
 calls=[]
 try:
  for phase,command in cases:
   check();print(json.dumps(dict(phase=phase,status='starting')),flush=True)
   with (out/(phase+'.stdout')).open('wb') as stdout,(out/(phase+'.stderr')).open('wb') as stderr:
    r=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr,timeout=7200,creationflags=subprocess.CREATE_NO_WINDOW)
   calls.append(dict(phase=phase,command=command,exit_code=r.returncode));save(out/'calls.json',calls)
   assert r.returncode==0,(phase,r.returncode)
   check();print(json.dumps(dict(phase=phase,status='passed')),flush=True)
  save(out/'verification.json',dict(status='passed',calls=calls,installed406_accepted=True,
   actual_PowerShell_loop_DF3_MuseTalk_passed=True,candidate_files=stage['candidate_files'],
   voice_documentation_tested=True,protected_files_unchanged=95,formal_activation=False,full_goal_closed=False))
  return 0
 except BaseException as exc:
  save(out/'verification.json',dict(status='failed',calls=calls,error=repr(exc),formal_activation=False,full_goal_closed=False));raise
if __name__=='__main__':raise SystemExit(main())
