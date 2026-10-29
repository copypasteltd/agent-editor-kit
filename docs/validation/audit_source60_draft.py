"""Audit the actual unregistered Skill and preserve unchanged formal59 discovery."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())

def main():
    stage=ROOT/'local/agent-ffmpeg/music60-skill-stage-r1';r=load(stage/'STAGING.json')
    skill=Path(r['skill']);assert r['status']=='unregistered-draft' and r['cli_version']=='0.1.60'
    assert r['requires_installed400_before_activation'] and r['strict_release_gate_unchanged']
    assert r['pending_gates']==['installed60_contracts'] and not r['installed400_accepted']
    pins={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}
    assert len(pins)==93 and pins==r['candidate_files']
    assert len(list((skill/'references/modules').glob('*/module.md')))==17
    assert all(sha(Path(p))==pin for p,pin in r['protected_files'].items())
    assert sha(ROOT/'docs/validation/stage_source60_skill.py')=='786e14aad83c677adb78bef35555d22c8edb420c08e584693f62f5430a137a1d'
    loop=load(BASE/'staged-actual-case-r1/verification.json')
    assert loop['status']=='passed' and loop['actual_PowerShell_entry'] and loop['candidate_files']==pins
    assert loop['complete_source_installed_PCM_equal'] and loop['complete_package_recipe_repair_PCM_equal']
    gate=load(BASE/'activation-gate-check-r1/verification.json')
    assert gate['status']=='passed' and gate['installed400_still_required'] and gate['protected_files_unchanged']==95
    discovery=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert discovery.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    out=BASE/'draft-audit-r1';out.mkdir(exist_ok=False)
    p=subprocess.run([sys.executable,'-E','-B','-u','-X','utf8',
        'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',str(skill)],
        cwd=ROOT,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'quick-validate.stdout').write_bytes(p.stdout);(out/'quick-validate.stderr').write_bytes(p.stderr)
    assert p.returncode==0,(p.stdout,p.stderr)
    report=dict(status='passed',cli_version='0.1.60',public_entries=1,modules=17,files=93,
        actual_PowerShell_loop_passed=True,complete_loop_PCM_bytes=2557440,quick_validate=True,
        protected_formal_files_unchanged=95,formal_cli='0.1.59',registered=False,activated=False,
        installed400_accepted=False,installed400_required_before_activation=True,strict_stage_unchanged=True,
        candidate_files=pins)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='candidate_files'}),flush=True)

if __name__=='__main__':main()
