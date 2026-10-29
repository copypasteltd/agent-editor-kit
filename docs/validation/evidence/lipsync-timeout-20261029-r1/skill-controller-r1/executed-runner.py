"""Stage and actually exercise the CLI61 Skill only after installed403 passes.

This controller never changes the registered Skill or activates a candidate.
"""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
PYTHON='C:/Python313/python.exe'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    contract=BASE/'installed61-contracts-r1/verification.json'
    if not contract.exists():
        print(json.dumps(dict(status='pending',missing=['installed61-contracts-r1'],mutated=False)),flush=True)
        return 2
    report=json.loads(contract.read_bytes())
    assert report['status']=='passed' and report['tests']==403 and report['frozen_equal']
    assert report['failures']==report['errors']==report['skipped']==0
    assert all(sha(ROOT/p)==h for p,h in report['file_hashes'].items())
    installation=json.loads((BASE/'installation-candidate-r1/verification.json').read_bytes())
    installed=installation['installed']
    assert Path(report['installed']).resolve()==Path(installed).resolve()
    guard=installation['registered_skill_file_hashes']
    assert all(sha(p)==h for p,h in guard.items())
    out=BASE/'skill-controller-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    prefix=[PYTHON,'-E','-B','-u','-X','utf8']
    skill=ROOT/'local/agent-ffmpeg/music61-skill-stage-r1/skills/agent-ffmpeg-local-editor'
    cases=[('stage',[*prefix,str(ROOT/'docs/validation/stage_source61_skill.py'),'--run','r1']),
           ('static',[*prefix,'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',str(skill)])]
    for name in ['loop','gpu','lipsync']:
        cases.append((name,[*prefix,str(ROOT/'docs/validation'/('run_staged61_'+name+'_case.py')),
                            '--run','r1','--installed',installed,'--skill',str(skill)]))
    calls=[]
    for phase,command in cases:
        print(json.dumps(dict(phase=phase,status='starting')),flush=True)
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=7200,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(phase+'.stdout')).write_bytes(result.stdout);(out/(phase+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(phase=phase,command=command,exit_code=result.returncode));save(out/'calls.json',calls)
        print(json.dumps(dict(phase=phase,exit_code=result.returncode)),flush=True)
        if result.returncode:
            save(out/'verification.json',dict(status='failed',calls=calls,activation_performed=False))
            return result.returncode
    assert all(sha(p)==h for p,h in guard.items())
    save(out/'verification.json',dict(status='passed',calls=calls,installed403_accepted=True,
         actual_PowerShell_loop_DF3_MuseTalk_passed=True,static_skill_validation_passed=True,
         protected_files_unchanged=95,activation_performed=False))
    print(json.dumps(dict(status='passed',activated=False,formal_cli='0.1.59')),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
