"""C47: registered CLI37 emitter animation, actual GPU video and editable package."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,hashlib,json,shutil,subprocess,time
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/emitter-animation-20261027-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def point(t,value,ease='linear',controls=None):
    v=dict(at_tick=round(t*90000),value=value,interpolation=ease)
    if controls is not None:v['control_points']=controls
    return v
def recipes():
    return [
        dict(id='moving-trail',preset='sparkles',base=dict(prewarm=False,rate=38,lifetime=[.85,.85],
            position=[.12,.7],spread=[.025,.04],velocity=[[0,0],[0,0]],size=[.012,.02],size_end=.35,
            glow=.5,twinkle=[.2,1],spin=[20,50],colors=['#ffe6a0','#ffab69']),tracks={
            'position':[point(0,[.12,.7]),point(2,[.88,.3],'ease_in_out'),point(4,[.12,.7])],
            'rate':[point(0,24,'ease_in'),point(2,70,'ease_out'),point(4,24)]}),
        dict(id='timed-confetti',preset='confetti',base=dict(prewarm=False,rate=0,lifetime=[1.4,1.8],
            position=[.5,.04],spread=[.9,.04],velocity=[[-.16,.16],[.18,.32]],size=[.011,.019],
            acceleration=[0,.23],fade_in=.05,fade_out=.25),tracks={
            'rate':[point(0,0,'hold'),point(.5,85,'hold'),point(1.15,0,'hold'),
                    point(2.2,85,'hold'),point(2.85,0,'hold'),point(4,0,'hold')],
            'rotation':[point(0,[-45,45]),point(4,[-180,180])],
            'spin':[point(0,[-120,120]),point(4,[-300,300])]}),
        dict(id='live-look',preset='bokeh',base=dict(rate=10,lifetime=[3,3],prewarm=True,
            position=[.5,.5],spread=[.9,.85],velocity=[[-.015,.015],[-.015,.015]],
            size=[.045,.065],opacity=.55,colors=['#ffca74','#ff8d66','#ffe1a3']),tracks={
            'colors':[point(0,['#ffca74','#ff8d66','#ffe1a3']),
                point(2,['#78caff','#9d8dff','#a6f3dd']),point(4,['#ffca74','#ff8d66','#ffe1a3'])],
            'size':[point(0,[.03,.045],'ease_in_out'),point(2,[.075,.11],'ease_in_out'),point(4,[.03,.045])],
            'shape':[point(0,'disc','hold'),point(2,'ring','hold')],
            'softness':[point(0,.8),point(2,.2),point(4,.8)],
            'opacity':[point(0,.5),point(2,.8),point(4,.5)]}),
        dict(id='star-easing',preset='sparkles',base=dict(rate=22,lifetime=[2,2],prewarm=True,
            position=[.5,.5],spread=[.9,.85],velocity=[[-.01,.01],[-.015,.015]],
            colors=['#f9edff','#9eeaff'],size=[.012,.035],twinkle=[.35,1]),tracks={
            'size':[point(0,[.006,.012],'bezier',[.3,.05,.7,.95]),
                    point(2,[.025,.055],'bezier',[.3,.05,.7,.95]),point(4,[.006,.012])],
            'glow':[point(0,.1,'ease_in'),point(2,.8,'ease_out'),point(4,.1)],
            'opacity':[point(0,.9,'ease_out'),point(2,.25,'ease_in'),point(4,.9)],
            'shape':[point(0,'diamond','hold'),point(1.3,'star','hold'),point(3,'ring','hold')]}),
    ]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('emitter-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/('docs/assets/emitter-animation-20261027-'+a.run);public.mkdir(exist_ok=False)
    project=work/'project';calls=[]
    def run(name,argv,cli=False,timeout=900):
        argv=list(map(str,argv));start=time.perf_counter()
        result=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout=(out if cli else work)/(name+('.stdout.json' if cli else '.bin'));err=out/(name+'.stderr.txt')
        stdout.write_bytes(result.stdout);err.write_bytes(result.stderr)
        calls.append(dict(id=name,argv=argv,exit_code=result.returncode,seconds=time.perf_counter()-start,
            stdout_bytes=len(result.stdout),stdout_sha256=sha(stdout),stderr_sha256=sha(err)))
        save(out/'calls.json',calls);print(json.dumps(dict(id=name,code=result.returncode)),flush=True)
        assert result.returncode==0,(name,result.stdout[-3000:],result.stderr[-3000:])
        if cli:
            value=json.loads(result.stdout);assert value['ok'];return value['data']
        return result.stdout
    def invoke(name,*args):return run(name,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',SKILL,*args],True)
    def render(name,root):
        value=invoke(name,'render','--project',root,'--output',root/('renders/'+name+'.mkv'),'--container','mkv',
            '--video-codec','libx264','--crf','0','--pixel-format','yuv444p10le','--audio-codec','pcm_f32le',
            '--hardware-encode','off','--projection-acceleration','require','--projection-device','0.0')
        path=Path(value['path']);manifest=load(path.with_suffix('.mkv.manifest.json'))
        gpu=manifest['delivery']['pixel_pipeline']['projection_acceleration']
        assert 0<gpu['operations']['particles']<=4*48 and gpu['worker_closed'] and gpu['shared_handles_closed']
        assert gpu['control']['threads_closed'] and gpu['control']['streams_closed']
        return path,gpu
    def decode(name,movie,fmt):return run(name,[ffmpeg,'-nostdin','-v','error','-i',movie,'-map','0:v:0','-an',
        '-pix_fmt',fmt,'-fps_mode','passthrough','-f','rawvideo','pipe:1'])
    report=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),registered_skill=True,
        native_windows=True,virtualization=False,source_fallback=False,synthetic_diagnostic=True,
        continuous_human_playback=False,human_listening=False,natural_quality_accepted=False)
    try:
        runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');report['manifest_sha256']=runtime['manifest_sha256']
        ffmpeg=Path(shutil.which('ffmpeg'));ffprobe=Path(shutil.which('ffprobe'))
        report['native_tools']={str(p):sha(p) for p in (ffmpeg,ffprobe)}
        assert invoke('version','version')['cli_version']=='0.1.37'
        assert len(invoke('properties','vfx','animation-properties')['properties'])==21
        invoke('init','project','init',project,'--name','C47 source-clock emitter keyframes')
        p=load(project/'project.json');p['settings']['canvas'].update(width=640,height=360,background='#101d2c')
        p['settings']['timebase']['display_fps']={'num':12,'den':1};save(project/'project.json',p)
        cells=recipes();ops=[]
        for i,cell in enumerate(cells):
            preset=invoke('inspect-'+cell['id'],'vfx','inspect','--name',cell['preset'])['preset']
            emitters=copy.deepcopy(preset['emitters']);emitters[0].update(cell['base'])
            config=dict(type='particles',protocol=preset['protocol'],seed=173+i,canvas=dict(width=320,height=180),
                fps=dict(num=12,den=1),duration_tick=360000,ticks_per_second=90000,emitters=emitters)
            path=work/(cell['id']+'.json');save(path,config)
            invoke('apply-'+cell['id'],'vfx','apply','--project',project,'--config',path,'--clip-id',cell['id'],
                '--duration-tick','360000','--enable-native')
            for field,points in cell['tracks'].items():
                path=work/(cell['id']+'-'+field+'.json');save(path,points)
                invoke('animate-'+cell['id']+'-'+field,'vfx','animate','--project',project,'--clip-id',cell['id'],
                    '--emitter-index','0','--property',field,'--keyframes',path)
            ops.append(dict(op='update_clip',clip_id=cell['id'],patch=dict(transform=dict(scale=.5,
                position=dict(x=(i%2+.5)/2,y=(i//2+.5)/2)))))
        path=work/'layout.json';save(path,dict(operations=ops))
        invoke('layout','timeline','compose','--project',project,'--input',path)
        invoke('validate','validate','--project',project)
        authored=load(project/'project.json')
        configs={c['id']:c['generator'] for s in authored['sequences'] for t in s['tracks'] for c in t['clips'] if c.get('generator')}
        assert sum(len(c['emitters'][0]['keyframes']) for c in configs.values())==14
        preview=invoke('preview','preview','frame','--project',project,'--frame','24','--height','360')
        movie,gpu=render('animated',project)
        exported=invoke('package','convert','export','--project',project,'--output',project/'exports/editable-emitter-animation.aevpkg.zip','--target-format','package')
        package=Path(exported['output']);restored=work/'restored'
        invoke('import','convert','import','--input',package,'--output',restored)
        migrated=load(restored/'project.json')
        restored_configs={c['id']:c['generator'] for s in migrated['sequences'] for t in s['tracks'] for c in t['clips'] if c.get('generator')}
        assert configs==restored_configs
        restored_movie,restored_gpu=render('restored',restored)
        assert gpu['operations']['particles']==restored_gpu['operations']['particles']
        video=decode('decode-animated',movie,'yuv444p10le');other=decode('decode-restored',restored_movie,'yuv444p10le')
        size=640*360*3*2;assert len(video)==48*size and video==other
        audio=[]
        for label,path in [('animated',movie),('restored',restored_movie)]:
            audio.append(run('audio-'+label,[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1']))
        assert len(audio[0])==4*48000*2*4 and audio[0]==audio[1]
        assert all(v==0 for v in memoryview(audio[0]).cast('f'))
        static=work/'static';invoke('static-import','convert','import','--input',package,'--output',static)
        doc=load(static/'project.json')
        for s in doc['sequences']:
            for t in s['tracks']:
                for c in t['clips']:
                    for e in c.get('generator',{}).get('emitters',[]):e.pop('keyframes',None)
        save(static/'project.json',doc);static_movie,static_gpu=render('static-before',static)
        rgb=decode('decode-rgb',movie,'rgb24');rgb_before=decode('decode-static-rgb',static_movie,'rgb24')
        assert len(rgb)==len(rgb_before)==48*640*360*3 and rgb!=rgb_before
        # Public playable delivery is encoded from the actual lossless diagnostic master.
        run('delivery-mp4',[ffmpeg,'-nostdin','-v','error','-i',movie,'-map','0:v:0','-map','0:a:0',
            '-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',public/'emitter-animation.mp4'])
        shutil.copy2(movie,public/'emitter-animation.mkv');shutil.copy2(package,public/'editable-emitter-animation.aevpkg.zip')
        frame_bytes=640*360*3;font=ImageFont.load_default(size=15)
        def image(data,index):
            im=Image.frombytes('RGB',(640,360),data[index*frame_bytes:(index+1)*frame_bytes]);draw=ImageDraw.Draw(im)
            for i,c in enumerate(cells):
                x,y=(i%2)*320,(i//2)*180;draw.rectangle((x,y,x+319,y+23),fill='#101d2c')
                draw.text((x+8,y+4),str(i+1)+' / '+c['id'],font=font,fill='#f0f2f6')
            draw.text((550,340),f'{index/12:.2f}s',font=font,fill='#f0f2f6');return im
        image(rgb_before,24).save(public/'before.png');image(rgb,24).save(public/'contact.png')
        frames=[image(rgb,i) for i in range(48)]
        durations=[10*(round((i+1)*100/12)-round(i*100/12)) for i in range(48)]
        frames[0].save(public/'emitter-animation.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=False)
        with Image.open(public/'emitter-animation.gif') as g:
            count=g.n_frames;milliseconds=sum((g.seek(i) or g.info['duration']) for i in range(g.n_frames))
        assert milliseconds==4000
        save(public/'recipes.json',configs)
        (public/'SOURCE.txt').write_text('Original C47 diagnostic by agent editor kit contributors.\n'
            'Implementation/recipes: MIT. Original generated pixels and numeric labels: CC0-1.0.\n'
            'No external photos, model weights, people, music, logos or font files redistributed.\n'
            '48 actual rendered frames, 12 FPS, 640x360, 4 seconds.\n'
            'MKV: actual registered CLI0.1.37 GPU output, lossless 10-bit H.264/Float32 PCM.\n'
            'MP4: playable encode of that master; GIF/contact: decoded master plus labels.\n'
            'before.png: separately GPU-rendered same project with all emitter tracks removed.\n'
            'GIF exact authored 4000ms using 10ms cumulative rounding. No human playback/listening acceptance.\n'
            'Reproduce scripts/run_emitter_case_20261027.py.\n',encoding='utf8',newline='\n')
        save(public/'media-manifest.json',dict(files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in public.iterdir() if p.is_file()},
            video_frames=48,video_fps='12/1',duration_seconds=4,GIF_frames=count,GIF_duration_ms=milliseconds,labels_added=True))
        report.update(status='passed',cli_version='0.1.37',public=public.relative_to(ROOT).as_posix(),
            project=str(project),source_configs=configs,frame_count=48,frame_sha256=[hashlib.sha256(video[i*size:(i+1)*size]).hexdigest() for i in range(48)],
            video_sha256=hashlib.sha256(video).hexdigest(),audio_sha256=hashlib.sha256(audio[0]).hexdigest(),
            all_48_decoded_10bit_frames_equal=True,all_384000_PCM_equal=True,decoded_audio_all_zero=True,
            GPU=gpu,restored_GPU=restored_gpu,static_GPU=static_gpu,preview=preview,package_sha256=sha(package),
            animation_tracks=14,all_animated_tracks_preserved=True,GIF_frames=count,GIF_duration_ms=milliseconds,
            finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out/'verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('GPU','restored_GPU','static_GPU','preview','source_configs','frame_sha256','native_tools')},ensure_ascii=False))
    except BaseException as e:
        report.update(status='failed',error=repr(e));save(out/'verification.json',report);raise
if __name__=='__main__':main()
