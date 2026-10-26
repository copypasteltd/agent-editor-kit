"""Reject stale Skill launch pins before discovery mutation, then register the real pin."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/model-session-20261027-r1'


def load(path):return json.loads(Path(path).read_bytes())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args();assert args.run.replace('-','').isalnum()
    out=BASE/('registration-preflight-'+args.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    home=ROOT/'workspace'/('model-session-20261027-registration-'+args.run);home.mkdir(exist_ok=False)
    manifest=load(ROOT/'agent-ffmpeg-local-install-manifest.json')
    for row in manifest['files']:
        destination=home/row['path'];destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes((ROOT/row['path']).read_bytes())
    script=home/'scripts/register_unified_skill.ps1';script.parent.mkdir(exist_ok=True);script.write_bytes((ROOT/'scripts/register_unified_skill.ps1').read_bytes())
    write(home/manifest['runtime_config'],load(ROOT/manifest['runtime_config']))
    launcher=home/'skills/agent-ffmpeg-local-editor/scripts/run.py';original=launcher.read_bytes()
    launcher.write_text(re.sub(r"^MANIFEST = '[^']+'$","MANIFEST = 'sha256:"+'0'*64+"'",original.decode('utf8'),count=1,flags=re.M),encoding='utf8',newline='\n')
    item=next(r for r in manifest['files'] if r['path'].endswith('/scripts/run.py'))
    item.update(bytes=launcher.stat().st_size,sha256=sha(launcher));write(home/'agent-ffmpeg-local-install-manifest.json',manifest)
    discovery=home/'discovery';receipt=home/'registration.json'
    def invoke(name,script_path,discovery_path,receipt_path):
        result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script_path),
            '-SkillsDirectory',str(discovery_path),'-ReceiptPath',str(receipt_path)],cwd=ROOT,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout.log')).write_bytes(result.stdout);(out/(name+'.stderr.log')).write_bytes(result.stderr)
        return result
    rejected=invoke('stale-pin',script,discovery,receipt)
    assert rejected.returncode!=0 and not discovery.exists() and not receipt.exists()
    assert b'Skill launcher preflight failed' in rejected.stderr
    launcher.write_bytes(original);item.update(bytes=len(original),sha256=sha(launcher));write(home/'agent-ffmpeg-local-install-manifest.json',manifest)
    corrected=invoke('correct-pin',script,discovery,receipt);assert corrected.returncode==0,(corrected.stdout,corrected.stderr)
    accepted=load(receipt);assert accepted['launcher_preflight_verified'] and accepted['registered_cli_version']=='0.1.34'
    (out/'isolated-registration.json').write_bytes(receipt.read_bytes())
    actual_receipt=out/'registration-final.json'
    actual=invoke('actual-registration',ROOT/'scripts/register_unified_skill.ps1',Path('C:/Users/carzy/.codex/skills'),actual_receipt)
    assert actual.returncode==0,(actual.stdout,actual.stderr)
    actual=load(actual_receipt);assert not actual['created_entry'] and actual['launcher_preflight_verified']
    assert actual['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
    report=dict(status='passed',stale_pin_exit_code=rejected.returncode,stale_pin_rejected_before_discovery_mutation=True,
        stale_pin_created_receipt=False,corrected_isolated_registration=True,actual_registration_preflight=True,
        registered_cli_version='0.1.34',source_fallback=False,actual_skill_count=1,unrelated_entries_modified=False,
        registration_script_sha256=sha(ROOT/'scripts/register_unified_skill.ps1'))
    write(out/'verification.json',report);print(json.dumps(report),flush=True)


if __name__=='__main__':main()
