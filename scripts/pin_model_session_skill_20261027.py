"""Update the actual unified Skill launcher pin and preserve the rejected call."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/model-session-20261027-r1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    assert args.run.replace('-','').isalnum()
    out=BASE/('skill-registration-'+args.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r3/verification.json')
    launcher=ROOT/'skills/agent-ffmpeg-local-editor/scripts/run.py';before=sha(launcher)
    text=launcher.read_text('utf8')
    text,n=re.subn(r"^MANIFEST = '[^']+'$","MANIFEST = "+repr(install['manifest_sha256']),text,count=1,flags=re.M);assert n==1
    text,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.32'",text,count=1,flags=re.M);assert n==1
    launcher.write_text(text,encoding='utf8',newline='\n')
    namespace=ROOT/'agent-ffmpeg-local-install-manifest.json';manifest=load(namespace)
    manifest['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted((ROOT/'skills/agent-ffmpeg-local-editor').rglob('*')) if p.is_file()]
    assert len(manifest['files'])==75
    namespace.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    commands=[('validate',[sys.executable,'-E','-B','-X','utf8','C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',str(ROOT/'skills/agent-ffmpeg-local-editor')]),
        ('register',['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'register-agent-ffmpeg-local-skills.ps1'),'-ReceiptPath',str(out/'registration.json')]),
        ('version',['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File','C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1','version'])]
    for name,argv in commands:
        value=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout.log')).write_bytes(value.stdout);(out/(name+'.stderr.log')).write_bytes(value.stderr)
        assert value.returncode==0,(name,value.stdout,value.stderr)
        if name=='version':assert json.loads(value.stdout)['data']['cli_version']=='0.1.34'
    registration=load(out/'registration.json');assert registration['namespace_manifest_sha256']==sha(namespace)
    failed=load(BASE/'render-roundtrip-r1/verification.json');assert failed['status']=='failed' and failed['calls'][0]['exit_code']==2
    record=dict(status='passed',skill_files=75,skill_count=1,module_count=17,source_fallback=False,
        old_launcher_sha256=before,launcher_sha256=sha(launcher),manifest_sha256=install['manifest_sha256'],namespace_sha256=sha(namespace),
        failed_call_retained='render-roundtrip-r1',reason='Updated the release and full manifest pin in the actual Skill launcher; native installation verification remains enabled.',
        registered_version='0.1.34',skill_structure_validated=True)
    (out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(record),flush=True)


if __name__=='__main__':main()
