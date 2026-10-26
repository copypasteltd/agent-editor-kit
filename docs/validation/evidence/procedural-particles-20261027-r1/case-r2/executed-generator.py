"""C45: actual registered Skill -> editable six-cell GPU movie -> package roundtrip."""
from __future__ import annotations
from pathlib import Path
import argparse,copy,hashlib,json,os,shutil,subprocess,sys,time
from datetime import datetime,timezone
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/procedural-particles-20261027-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    public=ROOT/('docs/assets/procedural-particles-20261027-'+a.run);public.mkdir(parents=True,exist_ok=False)
    work=ROOT/('local/agent-ffmpeg/particle-case-'+a.run);work.mkdir(exist_ok=False)
    project=work/'project';calls=[]
    def run(name,argv,*,cli=False,timeout=900):
        argv=list(map(str,argv));started=time.monotonic()
        r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout=out/(name+'.stdout.json' if cli else name+'.stdout.bin');stderr=out/(name+'.stderr.txt')
        stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
        calls.append({'id':name,'argv':argv,'exit_code':r.returncode,'seconds':time.monotonic()-started,
            'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr)})
        save(out/'calls.json',calls);print(json.dumps({'id':name,'exit_code':r.returncode}),flush=True)
        assert r.returncode==0,(name,r.stdout[-4000:],r.stderr[-4000:])
        if cli:
            value=json.loads(r.stdout);assert value['ok'];return value['data']
        return r.stdout
    def invoke(name,*argv):return run(name,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',SKILL,*argv],cli=True)
    report={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'native_windows':True,
        'source_fallback':False,'synthetic_diagnostic':True,'natural_quality_accepted':False,'listening_accepted':False}
    try:
        runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');installed=Path(runtime['installed_directory'])
        report.update(installed=str(installed),manifest_sha256=runtime['manifest_sha256'])
        ffmpeg=Path(shutil.which('ffmpeg') or 'missing-ffmpeg');ffprobe=Path(shutil.which('ffprobe') or 'missing-ffprobe')
        assert ffmpeg.is_file() and ffprobe.is_file()
        report['native_tools']={str(p):sha(p) for p in (ffmpeg,ffprobe)}
        version=invoke('version','version');assert version['cli_version']=='0.1.35'
        invoke('init','project','init',project,'--name','C45 editable particle preview')
        p=load(project/'project.json');p['settings']['canvas'].update(width=960,height=360,background='#101d2c')
        p['settings']['timebase']['display_fps']={'num':12,'den':1};save(project/'project.json',p)
        names=['snow','confetti','embers','bokeh','rain','sparkles'];ops=[];configs={}
        for i,name in enumerate(names):
            preset=invoke('inspect-'+name,'vfx','inspect','--name',name)['preset']
            config={'type':'particles','protocol':preset['protocol'],'seed':73+i,'canvas':{'width':320,'height':180},
                'fps':{'num':12,'den':1},'duration_tick':360000,'ticks_per_second':90000,'emitters':preset['emitters']}
            path=work/(name+'.json');save(path,config)
            value=invoke('apply-'+name,'vfx','apply','--project',project,'--config',path,'--clip-id',name,
                '--duration-tick','360000','--enable-native')
            configs[name]=value['clip']['generator']
            ops.append({'op':'update_clip','clip_id':name,'patch':{'transform':{'scale':.5,
                'position':{'x':(i%3+.5)/3,'y':(i//3+.5)/2}}}})
        edits=work/'layout.json';save(edits,{'operations':ops})
        invoke('layout','timeline','compose','--project',project,'--input',edits)
        invoke('validate','validate','--project',project)
        preview=invoke('preview','preview','frame','--project',project,'--frame','18','--height','360')
        rendered=invoke('render','render','--project',project,'--output','renders/particle-grid.mp4',
            '--projection-acceleration','require','--projection-device','0.0')
        movie=Path(rendered['path']);manifest=load(movie.with_suffix('.mp4.manifest.json'))
        gpu=manifest['delivery']['pixel_pipeline']['projection_acceleration']
        assert gpu['operations']['particles']==6*48 and gpu['worker_closed']
        exported=invoke('package','convert','export','--project',project,'--output','exports/editable-particle-grid.aevpkg.zip','--target-format','package')
        package=Path(exported['output']);restored=work/'restored'
        invoke('import','convert','import','--input',package,'--output',restored)
        migrated=load(restored/'project.json')
        preserved={c['id']:c['generator'] for s in migrated['sequences'] for t in s['tracks'] for c in t['clips'] if c.get('generator')}
        assert configs==preserved
        restored_render=invoke('render-restored','render','--project',restored,'--output','renders/restored.mp4',
            '--projection-acceleration','require','--projection-device','0.0')
        raw=[]
        for name,path in [('original',movie),('restored',Path(restored_render['path']))]:
            raw.append(run('decode-'+name,[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:v:0','-an',
                '-pix_fmt','rgb24','-fps_mode','passthrough','-f','rawvideo','pipe:1']))
        assert len(raw[0])==48*960*360*3 and raw[0]==raw[1]
        audio=run('decode-audio',[ffmpeg,'-nostdin','-v','error','-i',movie,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        # AAC delay/container trimming is inspected, not asserted to be PCM-master identical.
        assert len(audio)>0 and len(audio)%8==0 and all(v==0 for v in memoryview(audio).cast('f'))
        for data in out.glob('decode-*.stdout.bin'):
            save(data.with_suffix('.summary.json'),{'bytes':data.stat().st_size,'sha256':sha(data),'raw_retained_in_memory_only':True})
            data.unlink()
        shutil.copy2(movie,public/'particle-grid.mp4');shutil.copy2(package,public/'editable-particle-grid.aevpkg.zip')
        font=ImageFont.load_default(size=17);frames=[]
        def label(image):
            draw=ImageDraw.Draw(image)
            for i,name in enumerate(names):
                x,y=(i%3)*320,(i//3)*180
                draw.rectangle((x,y,x+319,y+24),fill='#101d2c')
                draw.text((x+9,y+4),str(i+1)+' / '+name,font=font,fill='#f0f2f6')
            return image
        before=label(Image.new('RGB',(960,360),'#101d2c'));before.save(public/'before.png')
        for i in range(48):
            frame=Image.frombytes('RGB',(960,360),raw[0][i*960*360*3:(i+1)*960*360*3])
            label(frame)
            if i==18:frame.save(public/'contact.png')
            frames.append(frame.resize((720,270),Image.Resampling.LANCZOS))
        frames[0].save(public/'particle-grid.gif',save_all=True,append_images=frames[1:],duration=83,loop=0,optimize=False)
        with Image.open(public/'particle-grid.gif') as g:
            gif_frames=g.n_frames;gif_ms=sum((g.seek(i) or g.info['duration']) for i in range(g.n_frames))
        save(public/'recipes.json',configs)
        (public/'SOURCE.txt').write_text('Original diagnostic procedural particle scene by agent editor kit contributors.\n'
            'Recipes and implementation: MIT. Original generated pixels/labels: CC0-1.0. No third-party photos, models, music or fonts redistributed.\n'
            'MP4 is actual registered Skill GPU rendering; GIF and contact image decode it and add numeric/English recipe labels.\n'
            'Input: a solid #101d2c background. Layout: snow/confetti/embers above bokeh/rain/sparkles.\n'
            '48 frames, 12 FPS, 960x360, four authored seconds. GIF duration is separately recorded; silent audio, no human listening acceptance.\n'
            'Reproduce: scripts/run_particle_case_20261027.py against installed CLI0.1.35.\n',encoding='utf8',newline='\n')
        files={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in public.iterdir() if p.is_file()}
        save(public/'media-manifest.json',{'files':files,'video_frames':48,'video_fps':'12/1','authored_seconds':4,
            'encoded_seconds':4,'GIF_frames':gif_frames,'GIF_duration_ms':gif_ms,'post_labels':True})
        report.update(status='passed',cli_version='0.1.35',public=str(public.relative_to(ROOT)),
            project=str(project),source_configs=configs,frame_count=48,fps='12/1',all_decoded_package_frames_equal=True,
            actual_gpu_particle_dispatches=288,GPU=gpu,preview=preview,package_sha256=sha(package),
            decoded_audio_samples_per_channel=len(audio)//8,decoded_audio_all_zero=True,
            GIF_frames=gif_frames,GIF_duration_ms=gif_ms,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('GPU','source_configs','preview')},ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save(out/'verification.json',report);raise
if __name__=='__main__':main()
