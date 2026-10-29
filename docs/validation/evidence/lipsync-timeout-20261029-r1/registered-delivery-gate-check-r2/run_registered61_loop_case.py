"""Real independently installed61 music fragment, repeated-loop PCM and portable recipe replay."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import wave
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
PYTHON='C:/Python313/python.exe'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def pcm(p):
    with wave.open(str(p),'rb') as w:
        assert (w.getframerate(),w.getnchannels(),w.getsampwidth())==(48000,2,2)
        return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).copy()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--installed',type=Path,required=True);parser.add_argument('--skill',type=Path,required=True);a=parser.parse_args()
    assert a.run.replace('-','').isalnum()
    installed=a.installed.resolve()
    skill=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert a.skill==skill and skill.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    activation=load(BASE/'skill61-activation-r1/verification.json')
    assert activation['status']=='activated-and-entry-verified'
    contracts=load(BASE/'installed61-contracts-r1/verification.json')
    assert contracts['status']=='passed' and contracts['tests']==403 and contracts['frozen_equal']
    assert Path(contracts['installed']).resolve()==installed
    assert sha(ROOT/'agent-ffmpeg-local-install-manifest.json')==activation['namespace_sha256']
    assert sha(ROOT/'local/agent-ffmpeg/runtime.json')==activation['runtime_sha256']
    stage=load(ROOT/'local/agent-ffmpeg/music61-skill-stage-r1/STAGING.json')
    from source61_voice_skill_overlay import validate_registered
    stage=validate_registered(stage,activation)
    assert stage['status'] in ('unregistered-candidate','unregistered-draft') and stage['cli_version']=='0.1.61'
    if stage['status']=='unregistered-draft':assert stage['requires_installed403_before_activation']
    assert stage['candidate_files']=={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}
    assert installed.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())
    gate=load(BASE/'installed61-loop-r1/verification.json')
    assert gate['status']=='passed' and gate['tests']==37 and gate['frozen_equal']
    assert gate['source_and_installed_equal']
    assert all(sha(ROOT/name)==pin for name,pin in gate['file_hashes'].items())
    work=ROOT/'local/agent-ffmpeg'/('music-loop61-registered-case-'+a.run);work.mkdir(exist_ok=False)
    out=BASE/('registered-actual-case-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    namespace=ROOT/'agent-ffmpeg-local-install-manifest.json';runtime=ROOT/'local/agent-ffmpeg/runtime.json'
    manifest=load(namespace);assert manifest['cli_version']=='0.1.61'
    guard={str(namespace):sha(namespace),str(runtime):sha(runtime)}
    guard.update({str(ROOT/r['path']):r['sha256'] for r in manifest['files']})
    calls=[]
    def cli(name,*args):
        argv=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(skill/'scripts/run.ps1'),*map(str,args)]
        p=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout')).write_bytes(p.stdout);(out/(name+'.stderr')).write_bytes(p.stderr)
        calls.append(dict(name=name,argv=argv,exit_code=p.returncode));save(out/'calls.json',calls)
        assert p.returncode==0,(name,p.stdout[-1800:],p.stderr[-1000:])
        v=json.loads(p.stdout);assert v['ok'] and v['provenance']['cli_version']=='0.1.61'
        print(json.dumps(dict(name=name,status='passed')),flush=True);return v['data']
    try:
        original=ROOT/'docs/assets/music-score59-20261029-r1/actual.wav'
        source=work/'original-fragment.wav';data=pcm(original)[:641760]
        assert len(data)==641760
        with wave.open(str(source),'wb') as w:
            w.setparams((2,2,48000,0,'NONE','not compressed'));w.writeframes(data.tobytes())
        notice=work/'SOURCE.txt'
        notice.write_text('CC0-1.0 original C75 analytical score/audio, first641760 samples (13.37s). No copied recordings or model weights. Loop overlap repair is CPU DSP; source61 MIT. Listening/natural-quality acceptance pending. Diagnostic waveform/GIF authored from actual measured PCM, not a GUI recording.\n',encoding='utf-8')
        project=work/'project';cli('version','version');cli('init','project','init',project)
        cli('ingest','media','ingest','--project',project,'--input',source,'--asset-id','original',
            '--license-spdx','CC0-1.0','--verification-status','verified','--creator','Agent Editor Kit original C75 fixture','--evidence',notice)
        before=[(project/name).read_bytes() for name in ['project.json','rights-ledger.json']]
        cli('dry-run','music','repair-loop','--project',project,'--asset-id','original','--crossfade-ms','50','--dry-run')
        assert before==[(project/name).read_bytes() for name in ['project.json','rights-ledger.json']]
        repaired=cli('repair','music','repair-loop','--project',project,'--asset-id','original',
            '--crossfade-ms','50','--new-asset-id','repaired','--apply','--track-id','track_audio_1')
        stats=repaired['audio_stats'];unit=project/repaired['asset']['uri'];fixed=pcm(unit)
        assert len(fixed)==639360 and stats['shortened_frames']==2400
        np.testing.assert_array_equal(fixed[:636960],data[2400:-2400])
        delta=lambda x:float(np.max(np.abs(x[0].astype(np.int32)-x[-1].astype(np.int32))))/32768.
        assert stats['original_boundary_delta']==delta(data) and stats['repaired_boundary_delta']==delta(fixed)
        raw=cli('repeat-original','music','prepare','--project',project,'--asset-id','original',
            '--duration-seconds','40.11','--loop','--new-asset-id','before_repeat')
        after=cli('repeat-repaired','music','prepare','--project',project,'--asset-id','repaired',
            '--duration-seconds','39.96','--loop','--new-asset-id','after_repeat')
        before_wav,after_wav=project/raw['asset']['uri'],project/after['asset']['uri']
        np.testing.assert_array_equal(pcm(before_wav),np.tile(data,(3,1)))
        np.testing.assert_array_equal(pcm(after_wav),np.tile(fixed,(3,1)))
        package=work/'editable-loop.zip';cli('export','convert','export','--project',project,'--output',package,'--target-format','package')
        replay=work/'replay';cli('import','convert','import','--input',package,'--output',replay)
        recipe=replay/repaired['recipe_uri'];assert recipe.read_bytes()==(project/repaired['recipe_uri']).read_bytes()
        again=cli('repair-replay','music','repair-loop','--project',replay,'--input',recipe,'--new-asset-id','repaired_again')
        np.testing.assert_array_equal(pcm(replay/again['asset']['uri']),fixed)
        reference=load(BASE/'actual-case-r1/verification.json')
        assert reference['status']=='passed'
        assert fixed.nbytes==reference['complete_repaired_PCM_bytes']
        assert hashlib.sha256(fixed.tobytes()).hexdigest()==reference['complete_repaired_PCM_sha256']
        image=Image.new('RGB',(960,480),'#101925');draw=ImageDraw.Draw(image)
        draw.text((25,16),'ACTUAL LOOP REPAIR / original C75 music fragment / CPU overlap / not neural',fill='white')
        draw.text((25,40),'13.37s source -> 13.32s cycle / 50ms overlap / original body PCM unchanged',fill='#aabed0')
        regions=[np.concatenate([x[-480:,0],x[:480,0]]).astype(float)/32768 for x in [data,fixed]]
        scale=max(np.max(np.abs(x)) for x in regions)*1.15 or 1
        for i,(samples,label,color) in enumerate(zip(regions,['SOURCE boundary','REPAIRED boundary'],['#f49b8f','#65d3cb'])):
            y=160+i*170;draw.text((25,y-65),label,fill=color)
            points=[(25+j*910/959,y-float(v)/scale*48) for j,v in enumerate(samples)]
            draw.line(points,fill=color,width=1);draw.line((480,y-56,480,y+56),fill='#ffca6b')
            draw.text((25,y+58),f'Boundary delta (both channels): {delta(data if i==0 else fixed):.9f}',fill=color)
        draw.text((25,452),'Shared plot scale; no audio normalization. Sample continuity is not listening acceptance.',fill='#aabed0')
        image.save(work/'actual.png');image.save(work/'actual.gif',save_all=True,duration=1500,loop=0)
        assert all(sha(ROOT/name)==pin for name,pin in gate['file_hashes'].items())
        assert stage['candidate_files']=={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}
        assert all(sha(Path(name))==pin for name,pin in guard.items())
        report=dict(status='passed',cli_version='0.1.61',source_only=False,source_fallback=False,actual_PowerShell_entry=True,candidate_registered=True,actual_C_drive_entry=True,activated=True,candidate_files_unchanged=True,candidate_files=stage['candidate_files'],installed403_accepted=stage.get('installed403_accepted',True),skill=str(skill),installed=str(installed),complete_source_installed_PCM_equal=True,
            statistics=stats,source_original_frames=len(data),repaired_cycle_frames=len(fixed),
            shortened_per_cycle_frames=2400,repeat_count=3,complete_repeated_PCM_equal=True,
            before_repeated_frames=1925280,after_repeated_frames=1918080,
            complete_repaired_PCM_bytes=fixed.nbytes,complete_repaired_PCM_sha256=hashlib.sha256(fixed.tobytes()).hexdigest(),
            complete_package_recipe_repair_PCM_equal=True,unprocessed_body_PCM_equal=True,
            human_listening=False,natural_music_seamlessness_accepted=False,model_forwards=0,
            original_media_license='CC0-1.0',registered_skill_cli='0.1.61',registered_skill_unchanged=True,
            frozen_equal=True,artifacts=dict(source=str(source),unit=str(unit),before=str(before_wav),after=str(after_wav),
                png=str(work/'actual.png'),gif=str(work/'actual.gif'),package=str(package),recipe=str(project/repaired['recipe_uri']),notice=str(notice)))
        save(out/'verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ['artifacts','statistics']}),flush=True)
    except BaseException as error:
        save(out/'verification.json',dict(status='failed',error=repr(error),cli_version='0.1.61',source_only=True));raise

if __name__=='__main__':main()
