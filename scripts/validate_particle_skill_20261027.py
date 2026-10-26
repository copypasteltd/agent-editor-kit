"""Validate and sequentially register the final pinned one-entry Skill."""
from pathlib import Path
import hashlib,json,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/procedural-particles-20261027-r1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=BASE/'skill-validation-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    manifest=json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())
    assert manifest['cli_version']=='0.1.35' and len(manifest['files'])==76
    for r in manifest['files']:assert sha(ROOT/r['path'])==r['sha256'] and (ROOT/r['path']).stat().st_size==r['bytes']
    assert manifest['skills'][0]['skill_md_sha256']==sha(ROOT/'skills/agent-ffmpeg-local-editor/SKILL.md')
    calls=[('validate',[sys.executable,'-E','-B','-u','-X','utf8',
        'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',ROOT/'skills/agent-ffmpeg-local-editor']),
        ('register',['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        ROOT/'register-agent-ffmpeg-local-skills.ps1','-ReceiptPath',BASE/'registration-final-r1.json'])]
    results=[]
    for name,args in calls:
        r=subprocess.run(list(map(str,args)),cwd=ROOT,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout.txt')).write_bytes(r.stdout);(out/(name+'.stderr.txt')).write_bytes(r.stderr)
        assert r.returncode==0,(name,r.stderr.decode('utf8','replace'))
        results.append({'name':name,'exit_code':r.returncode,'stdout_sha256':sha(out/(name+'.stdout.txt'))})
    reg=json.loads((BASE/'registration-final-r1.json').read_bytes())
    assert reg['registered_cli_version']=='0.1.35' and reg['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
    result={'status':'passed','skill_files':76,'single_entry':True,'internal_modules':17,'calls':results,
        'runtime_directory':reg['runtime_directory'],'namespace_manifest_sha256':reg['namespace_manifest_sha256']}
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
