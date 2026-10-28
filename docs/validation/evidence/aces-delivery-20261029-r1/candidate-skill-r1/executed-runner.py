"""Exercise an unregistered CLI53 Skill candidate without changing live discovery."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/aces-delivery-20261029-r1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();assert a.run.replace('-','').isalnum()
    assert sys.flags.isolated and sys.flags.no_site
    install=load(BASE/'installation-final-r2/verification.json');assert install['status']=='installed-and-byte-verified'
    for label,count in [('installed-special-r1',18),('installed-meter-r1',46)]:
        report=load(BASE/label/'verification.json');assert report['status']=='passed' and report['tests']==count and report['frozen_equal']
        for name,digest in report['files'].items():assert sha(ROOT/'product/src/ai_ad_editor'/name)==digest==sha(Path(install['installed'])/'site/ai_ad_editor'/name)
    out=BASE/('candidate-skill-'+a.run);out.mkdir(exist_ok=False);(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    namespace=ROOT/'agent-ffmpeg-local-install-manifest.json';namespace_pin=sha(namespace)
    runtime=ROOT/'local/agent-ffmpeg/runtime.json';runtime_pin=sha(runtime)
    discovery=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor');target=discovery.resolve()
    assert target==(ROOT/'skills/agent-ffmpeg-local-editor').resolve() and load(namespace)['cli_version']=='0.1.52'
    for row in load(namespace)['files']:assert sha(ROOT/row['path'])==row['sha256']
    home=ROOT/'local/agent-ffmpeg/aces-skill-stage51';skill=home/'skills/agent-ffmpeg-local-editor'
    runner=skill/'scripts/run.py';(out/'previous-candidate-runner.py').write_bytes(runner.read_bytes())
    text=runner.read_text('utf-8')
    text,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),text,count=1,flags=re.M);assert n==1
    text,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.51'",text,count=1,flags=re.M);assert n==1
    runner.write_text(text,encoding='utf-8',newline='\n')
    config=load(runtime);config.update(release='v0.1.0-alpha.4-local.51',installed_directory=install['installed'],manifest_sha256=install['manifest_sha256'],launcher_sha256=sha(Path(install['installed'])/'run.py'))
    cfg=home/'local/agent-ffmpeg/runtime.json';cfg.parent.mkdir(parents=True,exist_ok=True);assert not cfg.exists();save(cfg,config)
    files={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()};assert len(files)==92
    calls=[];ps=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File']
    def cli(name,*args):
        command=[*ps,str(skill/'scripts/run.ps1'),*map(str,args)]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout.json')).write_bytes(r.stdout);(out/(name+'.stderr.txt')).write_bytes(r.stderr)
        calls.append(dict(name=name,argv=command,exit_code=r.returncode));save(out/'calls.json',calls)
        print(json.dumps(dict(name=name,exit_code=r.returncode)),flush=True);assert r.returncode==0,(name,r.stdout[-1000:],r.stderr[-1000:])
        v=json.loads(r.stdout);assert v['ok'] and v['provenance']['cli_version']=='0.1.53';return v['data']
    assert cli('version','version')['cli_version']=='0.1.53'
    capabilities=cli('capabilities','capabilities')['capabilities'];assert len(capabilities)==90 and 'native_aces_display' in capabilities
    catalog=cli('catalog','surface','ocio-configs','--config','aces-2.1');assert catalog['version']=='2.6.0'
    project=home/('case-'+a.run)
    cli('import','convert','import','--input',ROOT/'docs/assets/aces-installed-20261029-r1/editable-aces.zip','--output',project)
    cli('validate','validate','--project',project);author=(project/'project.json').read_bytes()
    frame=cli('frame','preview','frame','--project',project,'--frame','7','--height','128')
    assert frame['pixel_pipeline']['transport']['frames']==1
    assert sha(frame['path'])==sha(ROOT/'docs/assets/aces-installed-20261029-r1/frame7.png')
    measured=cli('measure','surface','measure','--project',project,'--sequence-id',load(project/'project.json')['sequences'][0]['id'])
    assert (project/'project.json').read_bytes()==author
    assert files=={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}
    assert sha(namespace)==namespace_pin and sha(runtime)==runtime_pin and discovery.resolve()==target
    for row in load(namespace)['files']:assert sha(ROOT/row['path'])==row['sha256']
    report=dict(status='passed',candidate_registered=False,live_discovery_changed=False,live_skill_cli='0.1.52',candidate_cli='0.1.53',
        skill_files=92,public_entries=1,modules=17,source_fallback=False,actual_pinned_launcher_used=True,capabilities=90,
        actual_native_catalog=True,actual_frame_PNG_byte_equal=True,readonly_measurement=True,author_bytes_unchanged=True,
        candidate_files=files,namespace_manifest_sha256=namespace_pin,live_runtime_sha256=runtime_pin,calls=len(calls),measurement=measured)
    save(out/'verification.json',report)
    save(home/'STAGING.json',dict(status='behavior-verified-unregistered-candidate',live_skill_changed=False,public_entries=1,modules=17,files=92,runtime_launcher_pin=install['manifest_sha256'],candidate_cli='0.1.53'))
    print(json.dumps({k:v for k,v in report.items() if k not in ['candidate_files','measurement']},ensure_ascii=False))

if __name__=='__main__':main()
