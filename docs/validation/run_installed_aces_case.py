"""Isolated installed CLI53 ACES rendering, complete encoded replay and public previews."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/aces-delivery-20261029-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--installed',type=Path,required=True);a=p.parse_args();assert a.run.replace('-','').isalnum()
    ns=ROOT/'agent-ffmpeg-local-install-manifest.json';pin=sha(ns)
    installation=load(BASE/'installation-final-r2/verification.json')
    assert installation['status']=='installed-and-byte-verified' and a.installed.resolve()==Path(installation['installed']).resolve()
    assert sys.flags.isolated and sys.flags.no_site
    assert SKILL.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    out=BASE/('installed-case-'+a.run);out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('installed-aces-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/'docs/assets'/('aces-installed-20261029-'+a.run);public.mkdir(exist_ok=False)
    ffmpeg=shutil.which('ffmpeg');assert ffmpeg
    calls=[]
    def call(name,args,cli=False,binary=False):
        args=list(map(str,args));r=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        ((work if binary else out)/(name+('.raw' if binary else '.stdout'))).write_bytes(r.stdout)
        (out/(name+'.stderr')).write_bytes(r.stderr)
        calls.append(dict(name=name,argv=args,exit_code=r.returncode,stdout_sha256=hashlib.sha256(r.stdout).hexdigest()))
        save(out/'calls.json',calls);print(json.dumps(dict(name=name,exit_code=r.returncode)),flush=True)
        assert r.returncode==0,(name,r.stdout[-1500:],r.stderr[-1500:])
        if cli:
            v=json.loads(r.stdout);assert v['ok'] and v['provenance']['cli_version']=='0.1.53';return v['data']
        return r.stdout
    def cli(name,*args):return call(name,[sys.executable,'-I','-S','-B','-u','-X','utf8',a.installed/'run.py',*args],cli=True)
    project=work/'project';original=ROOT/'docs/assets/aces-timeline-20261029-r1'
    cli('import','convert','import','--input',original/'editable-project.zip','--output',project)
    authored=load(project/'project.json');seq=authored['sequences'][0]['id']
    movie=project/'renders/installed-aces.mkv'
    result=cli('render','render','--project',project,'--sequence-id',seq,'--output',movie)
    pipeline=result['delivery']['pixel_pipeline'];assert pipeline['aces_display']['frames']==8 and pipeline['ACES_processors_closed']
    after=(project/'project.json').read_bytes()
    frame=cli('frame','preview','frame','--project',project,'--frame','7','--height','128')
    window=cli('range','preview','range','--project',project,'--start-frame','0','--end-frame','8','--height','64')
    assert frame['pixel_pipeline']['transport']['frames']==1 and window['pixel_pipeline']['transport']['frames']==8
    measured=cli('meter','surface','measure','--project',project,'--sequence-id',seq)
    package=project/'exports/editable-aces.zip'
    cli('export','convert','export','--project',project,'--output',package,'--target-format','package')
    replay=work/'replay';cli('reimport','convert','import','--input',package,'--output',replay)
    cli('revalidate','validate','--project',replay)
    again=replay/'renders/installed-aces.mkv';cli('replay-render','render','--project',replay,'--sequence-id',seq,'--output',again)
    assert after==(project/'project.json').read_bytes() and sha(ns)==pin
    def pixels(name,path):return call(name,[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:v:0','-an','-pix_fmt','yuv444p10le','-f','rawvideo','pipe:1'],binary=True)
    actual=pixels('render-yuv',movie)
    assert actual==pixels('replay-yuv',again)==pixels('source-case-yuv',original/'author-aces.mkv')
    assert len(actual)==8*96*128*3*2
    def pcm(name,path):return call(name,[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'],binary=True)
    audio=pcm('render-pcm',movie);assert audio==pcm('replay-pcm',again)==pcm('source-case-pcm',original/'author-aces.mkv')
    assert len(audio)==38400*2*4
    def rgba(name,path):return call(name,[ffmpeg,'-nostdin','-v','error','-i',path,'-pix_fmt','rgba64le','-f','rawvideo','pipe:1'],binary=True)
    assert rgba('frame-rgba',frame['path'])==rgba('source-case-rgba',original/'frame7.png')
    for source,name in [(movie,'aces.mkv'),(again,'replay.mkv'),(package,'editable-aces.zip'),(Path(frame['path']),'frame7.png'),(Path(window['path']),'preview.mp4')]:shutil.copyfile(source,public/name)
    call('gif',[ffmpeg,'-nostdin','-v','error','-i',public/'preview.mp4','-filter_complex','[0:v]fps=10,scale=288:384:flags=neighbor,split[a][b];[a]palettegen[p];[b][p]paletteuse','-loop','0',public/'preview.gif'])
    save(public/'SOURCE.json',dict(license='CC0-1.0',source='Original C65 scene-linear AP1 chart and original stereo tones; actual isolated installed CLI53 execution; registered Skill remains unchanged.',
        frames=8,fps=10,duration_seconds=.8,natural_footage=False,human_continuous_watch_or_listening=False,physical_monitor_acceptance=False,
        files=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir())]))
    report=dict(status='passed',cli_version='0.1.53',registered_skill_used=False,isolated=True,no_site=True,source_fallback=False,namespace_manifest_sha256=pin,
        formal_native_ACES=True,complete_YUV_original_installed_replay_equal=True,YUV_bytes=len(actual),
        complete_PCM_original_installed_replay_equal=True,PCM_bytes=len(audio),preview_RGBA16_source_case_equal=True,
        preview_and_meter_author_bytes_unchanged=True,new_renders=2,new_model_forwards=0,public=str(public),meter=measured)
    save(out/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k!='meter'},ensure_ascii=False))

if __name__=='__main__':main()
