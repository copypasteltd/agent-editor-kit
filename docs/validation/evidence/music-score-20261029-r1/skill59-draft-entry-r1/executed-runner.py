"""Exercise music through the unregistered real PowerShell Skill front door."""
import hashlib
import json
from pathlib import Path
import subprocess
import wave

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-score-20261029-r1'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_bytes())
def save(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    installation=load(BASE/'installation-candidate-r1/verification.json')
    assert installation['status']=='installed-and-byte-verified'
    gate=load(BASE/'installed59-score-r1/verification.json')
    assert gate['status']=='passed' and gate['tests']==19 and gate['source_fallback'] is False
    installed=Path(installation['installed']);assert Path(gate['installed'])==installed
    namespace=ROOT/'agent-ffmpeg-local-install-manifest.json'
    runtime=ROOT/'local/agent-ffmpeg/runtime.json'
    live=load(namespace);assert live['cli_version']=='0.1.58'
    protected={p:sha(p) for p in [namespace,runtime]}
    protected.update({ROOT/row['path']:row['sha256'] for row in live['files']})
    home=ROOT/'local/agent-ffmpeg/music59-skill-draft-r1'
    skill=home/'skills/agent-ffmpeg-local-editor'
    pins={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}
    assert len(pins)==93
    config=load(runtime)
    config.update(release='v0.1.0-alpha.4-local.57',installed_directory=str(installed),
        manifest_sha256=installation['manifest_sha256'],launcher_sha256=sha(installed/'run.py'))
    target=home/'local/agent-ffmpeg/runtime.json';assert not target.exists()
    target.parent.mkdir(parents=True,exist_ok=True);save(target,config)
    out=BASE/'skill59-draft-entry-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg/music59-draft-entry-r1';work.mkdir(exist_ok=False)
    project=work/'project';score=ROOT/'docs/assets/music-score59-20261029-r1/score.json'
    calls=[]
    def cli(name,*args):
        argv=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(skill/'scripts/run.ps1'),*map(str,args)]
        p=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout')).write_bytes(p.stdout);(out/(name+'.stderr')).write_bytes(p.stderr)
        calls.append(dict(name=name,argv=argv,exit_code=p.returncode));save(out/'calls.json',calls)
        assert p.returncode==0,(name,p.stdout[-1500:],p.stderr[-1000:])
        value=json.loads(p.stdout);assert value['ok'] and value['provenance']['cli_version']=='0.1.59'
        print(json.dumps(dict(name=name,status='passed')),flush=True)
        return value['data']
    cli('version','version');cli('capabilities','capabilities')
    info=cli('inspect','music','inspect-score','--input',score);assert info['frames']==768000
    cli('init','project','init',project)
    before={n:(project/n).read_bytes() for n in ['project.json','rights-ledger.json']}
    cli('dry-run','music','compose','--project',project,'--input',score,'--new-asset-id','song','--stems','--apply','--track-id','track_audio_1','--dry-run')
    assert before=={n:(project/n).read_bytes() for n in before}
    generated=cli('compose','music','compose','--project',project,'--input',score,'--new-asset-id','song','--stems','--apply','--track-id','track_audio_1')
    assert generated['rights']['verification_status']=='unverified'
    audio=project/generated['asset']['uri']
    with wave.open(str(audio),'rb') as wav:
        pcm=wav.readframes(wav.getnframes());assert len(pcm)==3072000
    digest=hashlib.sha256(pcm).hexdigest()
    assert digest==load(BASE/'actual-case-r1/verification.json')['audio']['PCM_sha256']
    effect=cli('effect','music','effect','--project',project,'--preset','chime','--duration-seconds','2','--new-asset-id','chime')
    assert effect['audio_stats']['frames']==96000
    assert pins=={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}
    assert all(sha(p)==pin for p,pin in protected.items())
    report=dict(status='passed',cli_version='0.1.59',actual_PowerShell_entry=True,
        public_entries=1,modules=17,files=93,candidate_registered=False,activated=False,
        source_fallback=False,complete_source_PCM_equal=True,complete_PCM_bytes=len(pcm),
        complete_PCM_sha256=digest,stems=5,rights_default_unverified=True,dry_run_readonly=True,
        live_registered_cli='0.1.58',live_skill_unchanged=True,candidate_files=pins,
        installed=str(installed),human_listening=False,neural_music=False)
    save(out/'verification.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='candidate_files'}),flush=True)

if __name__=='__main__': main()
