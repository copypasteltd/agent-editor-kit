"""Render C49 through the registered installed Skill and compare every frame/PCM."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,hashlib,json,shutil,subprocess,time
from PIL import Image,ImageDraw,ImageFont
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/highlight-glow-20261027-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
W,H=960,540

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def track(prop,a,b,c=None):
    points=[dict(at_tick=0,value=a,interpolation='ease_in_out')]
    if c is None:points.append(dict(at_tick=360000,value=b,interpolation='linear'))
    else:points.extend([dict(at_tick=180000,value=b,interpolation='ease_in_out'),dict(at_tick=360000,value=c,interpolation='linear')])
    return dict(property=prop,keyframes=points)

def recipes():
    return [dict(id='original',effects=[]),
        dict(id='bloom',effects=[dict(type='bloom',parameters=dict(radius=8,threshold=.35,knee=.12,gain=1.4),
            keyframes=[track('radius',4,14),track('intensity',.25,1,.25)])]),
        dict(id='halation',effects=[dict(type='halation',parameters=dict(radius=5,threshold=.45,knee=.08,
            gain=4,red=1,green=.14,blue=.03,core_suppression=1),
            keyframes=[track('radius',3,9),track('intensity',.2,1,.2)])]),
        dict(id='combined',effects=[dict(type='bloom',parameters=dict(radius=8,threshold=.4,knee=.12,gain=.9),
            keyframes=[track('radius',4,12)]),dict(type='halation',parameters=dict(radius=4,threshold=.5,
            gain=3,red=1,green=.14,blue=.03),keyframes=[track('intensity',.1,1,.1)])])]

def draw_source(path):
    y,x=np.mgrid[:270,:480];rgb=np.empty((270,480,3),np.uint8)
    for channel,(base,dx,dy) in enumerate([(17,17,8),(27,22,8),(47,36,12)]):
        rgb[:,:,channel]=np.clip(base+dx*x/479+dy*y/269,0,255)
    im=Image.fromarray(rgb);d=ImageDraw.Draw(im);font=ImageFont.load_default(size=16)
    for xx in range(24,480,24):d.line((xx,0,xx,270),fill='#293f56',width=1)
    for yy in range(24,270,24):d.line((0,yy,480,yy),fill='#293f56',width=1)
    d.ellipse((330,50,437,157),outline='#9fcfff',width=3)
    d.ellipse((344,64,423,143),outline='#ffffff',width=1)
    d.ellipse((130,232,343,257),fill='#111b2c')
    d.rounded_rectangle((192,67,287,240),radius=20,fill='#64b9ad',outline='#d5fff0',width=3)
    d.rounded_rectangle((211,44,267,83),radius=7,fill='#b9d5d7',outline='#f0fafb',width=2)
    d.rectangle((201,127,278,199),fill='#edf8f1')
    d.text((212,144),'A E K',font=font,fill='#173a43')
    d.text((210,171),'LOCAL',font=ImageFont.load_default(size=13),fill='#173a43')
    d.line((204,95,204,116),fill='#e0fff8',width=4)
    d.text((27,60),'GLOW',font=ImageFont.load_default(size=22),fill='#eff5ff')
    d.text((27,87),'STUDY / 01',font=font,fill='#a9bfd3')
    for i,color in enumerate(('#ef5b58','#f5c34b','#8fcfa4','#75b7ec','#e5e8ef')):
        d.rectangle((32+i*24,201,47+i*24,217),fill=color)
    d.line((34,150,136,124),fill='#f7f9ff',width=2)
    d.ellipse((345,65,422,142),outline='#ffffff',width=4)
    for xx,yy in ((350,185),(400,220),(437,175)):
        d.ellipse((xx-4,yy-4,xx+4,yy+4),fill='#fff8db')
    d.line((160,34,305,34),fill='#fffaf0',width=3)
    im.save(path)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('highlight-glow-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/('docs/assets/highlight-glow-20261027-'+a.run);public.mkdir(exist_ok=False)
    project=work/'project';calls=[]
    def run(name,argv,cli=False,timeout=900):
        argv=list(map(str,argv));started=time.perf_counter()
        r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout=(out if cli else work)/(name+('.stdout.json' if cli else '.bin'));stderr=out/(name+'.stderr.txt')
        stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
        calls.append(dict(id=name,argv=argv,exit_code=r.returncode,seconds=time.perf_counter()-started,
            stdout_bytes=len(r.stdout),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
        save(out/'calls.json',calls);print(json.dumps(dict(id=name,code=r.returncode)),flush=True)
        assert r.returncode==0,(name,r.stdout[-3000:],r.stderr[-3000:])
        if cli:
            value=json.loads(r.stdout);assert value['ok'];return value['data']
        return r.stdout
    def invoke(name,*args):return run(name,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',SKILL,*args],True)
    def render(name,root,expected):
        value=invoke(name,'render','--project',root,'--output',root/('renders/'+name+'.mkv'),'--container','mkv',
            '--video-codec','libx264','--crf','0','--pixel-format','yuv444p10le','--audio-codec','pcm_f32le',
            '--hardware-encode','off','--projection-acceleration','require','--projection-device','0.0')
        movie=Path(value['path']);manifest=load(movie.with_suffix('.mkv.manifest.json'))
        gpu=manifest['delivery']['pixel_pipeline']['projection_acceleration']
        assert gpu['operations'].get('glow',0)==expected and gpu['worker_closed'] and gpu['shared_handles_closed']
        assert gpu['control']['threads_closed'] and gpu['control']['streams_closed']
        return movie,gpu
    def decode(name,movie,fmt):return run(name,[ffmpeg,'-nostdin','-v','error','-i',movie,
        '-map','0:v:0','-an','-pix_fmt',fmt,'-fps_mode','passthrough','-f','rawvideo','pipe:1'])
    report=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),registered_skill=True,
        native_windows=True,virtualization=False,source_fallback=False,synthetic_diagnostic=True,
        continuous_human_playback=False,human_listening=False,natural_quality_accepted=False)
    try:
        runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');report['manifest_sha256']=runtime['manifest_sha256']
        ffmpeg=Path(shutil.which('ffmpeg'));ffprobe=Path(shutil.which('ffprobe'))
        report['native_tools']={str(p):sha(p) for p in (ffmpeg,ffprobe)}
        assert invoke('version','version')['cli_version']=='0.1.39'
        catalog=invoke('optical-catalog','effects','list','--query','native:float32-glow');assert catalog['count']==2
        invoke('init','project','init',project,'--name','C49 editable highlight glow')
        draw_source(public/'original-source.png')
        ingest=invoke('ingest','media','ingest','--project',project,'--input',public/'original-source.png',
            '--asset-id','original-study','--license-spdx','CC0-1.0','--verification-status','verified',
            '--permitted-use','all',
            '--evidence','Original contributor-drawn synthetic product chart; no external imagery.')
        p=load(project/'project.json');s=p['settings'];s['canvas'].update(width=W,height=H,background='#111b2c')
        s['timebase']['display_fps']={'num':12,'den':1};s['color']['transfer']='iec61966-2-1'
        s['pixel_pipeline']=dict(engine='float32-native-v1',working_signal=dict(primaries='bt709',transfer='linear'),
            output_signal=dict(primaries='bt709',transfer='srgb'),range_policy='clip',sources={
            'original-study':dict(source_signal=dict(primaries='bt709',transfer='srgb'),demux_origin='0',
                display_geometry='square-unrotated')})
        save(project/'project.json',p);cells=recipes();ops=[]
        for i,cell in enumerate(cells):
            video_track='glow-track-'+str(i)
            ops.append(dict(op='add_track',track_id=video_track,kind='video',order=i+3))
            ops.append(dict(op='append_clip',track_id=video_track,id=cell['id'],asset_id='original-study',
                timeline_start_tick=0,duration_tick=360000,source_in_tick=0,source_out_tick=360000,
                effects=cell['effects'],transform=dict(scale=.5,position=dict(x=(i%2+.5)/2,y=(i//2+.5)/2))))
        path=work/'composition.json';save(path,dict(operations=ops))
        invoke('compose','timeline','compose','--project',project,'--input',path)
        invoke('validate','validate','--project',project)
        authored=load(project/'project.json')
        effects={c['id']:c.get('effects',[]) for seq in authored['sequences'] for t in seq['tracks'] for c in t['clips']}
        assert sum(len(e.get('keyframes',[])) for chain in effects.values() for e in chain)==6
        preview=invoke('preview','preview','frame','--project',project,'--frame','24','--height',str(H))
        movie,gpu=render('animated',project,192) # Four active glow operators across 48 frames; each runs four device kernels.
        exported=invoke('package','convert','export','--project',project,'--output',project/'exports/editable-highlight-glow.aevpkg.zip','--target-format','package')
        package=Path(exported['output']);restored=work/'restored'
        invoke('import','convert','import','--input',package,'--output',restored)
        migrated=load(restored/'project.json')
        restored_effects={c['id']:c.get('effects',[]) for seq in migrated['sequences'] for t in seq['tracks'] for c in t['clips']}
        assert effects==restored_effects
        restored_movie,restored_gpu=render('restored',restored,192)
        video=decode('decode-animated',movie,'yuv444p10le');other=decode('decode-restored',restored_movie,'yuv444p10le')
        frame_size=W*H*3*2;assert len(video)==48*frame_size and video==other
        audio=[]
        for label,path in [('animated',movie),('restored',restored_movie)]:
            audio.append(run('audio-'+label,[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn',
                '-c:a','pcm_f32le','-f','f32le','pipe:1']))
        assert len(audio[0])==4*48000*2*4 and audio[0]==audio[1]
        assert all(v==0 for v in memoryview(audio[0]).cast('f'))
        before=work/'before';invoke('before-import','convert','import','--input',package,'--output',before)
        doc=load(before/'project.json')
        for seq in doc['sequences']:
            for t in seq['tracks']:
                for c in t['clips']:c.pop('effects',None)
        save(before/'project.json',doc);before_movie,before_gpu=render('without-effects',before,0)
        rgb=decode('decode-rgb',movie,'rgb24');rgb_before=decode('decode-before-rgb',before_movie,'rgb24')
        assert len(rgb)==len(rgb_before)==48*W*H*3 and rgb!=rgb_before
        run('delivery-mp4',[ffmpeg,'-nostdin','-v','error','-i',movie,'-map','0:v:0','-map','0:a:0',
            '-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k',
            '-movflags','+faststart',public/'highlight-glow.mp4'])
        shutil.copy2(movie,public/'highlight-glow.mkv');shutil.copy2(package,public/'editable-highlight-glow.aevpkg.zip')
        def picture(data,index):
            size=W*H*3;im=Image.frombytes('RGB',(W,H),data[index*size:(index+1)*size]);d=ImageDraw.Draw(im)
            for i,c in enumerate(cells):
                x,y=(i%2)*480,(i//2)*270;d.rectangle((x,y,x+479,y+25),fill='#101b2c')
                d.text((x+10,y+4),str(i+1)+' / '+c['id'],font=ImageFont.load_default(size=17),fill='#f0f4fa')
            d.text((875,518),f'{index/12:.2f}s',font=ImageFont.load_default(size=15),fill='#f0f4fa');return im
        picture(rgb_before,24).save(public/'before.png');picture(rgb,24).save(public/'contact.png')
        frames=[picture(rgb,i) for i in range(48)]
        durations=[10*(round((i+1)*100/12)-round(i*100/12)) for i in range(48)]
        frames[0].save(public/'highlight-glow.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=False)
        with Image.open(public/'highlight-glow.gif') as g:
            count=g.n_frames;milliseconds=sum((g.seek(i) or g.info['duration']) for i in range(g.n_frames))
        assert count==48 and milliseconds==4000
        # Execute the exact documented update_clip JSON in an independent import.
        # Verify dry-run invariance before applying and previewing the edit.
        import re
        documented=(ROOT/'docs/product/HIGHLIGHT_GLOW.md').read_text('utf8')
        sample=json.loads(re.search(r'```json\n(.*?)\n```',documented,re.S)[1])
        usage=work/'usage-example';invoke('usage-import','convert','import','--input',package,'--output',usage)
        composition=work/'usage-composition.json';save(composition,sample)
        original_usage=(usage/'project.json').read_bytes()
        invoke('usage-dry-run','timeline','compose','--project',usage,'--input',composition,'--dry-run')
        assert (usage/'project.json').read_bytes()==original_usage
        invoke('usage-apply','timeline','compose','--project',usage,'--input',composition)
        invoke('usage-validate','validate','--project',usage)
        invoke('usage-preview','preview','frame','--project',usage,'--frame','24','--height',str(H))
        usage_doc=load(usage/'project.json')
        edited=next(c for seq in usage_doc['sequences'] for t in seq['tracks'] for c in t['clips'] if c['id']=='bloom')
        assert edited['effects']==sample['operations'][0]['patch']['effects']
        save(public/'usage-composition.json',sample)
        save(public/'recipes.json',effects)
        (public/'SOURCE.txt').write_text('Original C49 synthetic highlight chart by agent editor kit contributors.\n'
            'Original PNG/pixels/labels: CC0-1.0. Implementation/recipes: MIT. No external media or model weights.\n'
            'MKV: actual registered installed CLI0.1.39 GPU render, 48 frames/12FPS/960x540/4s.\n'
            'MP4: playable encode; GIF/contact add labels to decoded master. before.png: effects removed, separately GPU rendered.\n'
            'Six editable numeric channels; actual image highlight extraction, separable bloom and tinted core-suppressed halation.\n'
            'No physical lens or calibrated film simulation claim; no continuous human playback/listening acceptance.\n'
            'Reproduce scripts/run_highlight_glow_case_20261027.py.\n',encoding='utf8',newline='\n')
        save(public/'media-manifest.json',dict(files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in public.iterdir() if p.is_file()},
            video_frames=48,video_fps='12/1',duration_seconds=4,GIF_frames=count,GIF_duration_ms=milliseconds,labels_added=True))
        report.update(status='passed',cli_version='0.1.39',public=public.relative_to(ROOT).as_posix(),project=str(project),
            effects=effects,animation_tracks=6,all_effects_and_tracks_preserved=True,frame_count=48,
            documented_composition_executed=True,documented_dry_run_author_bytes_unchanged=True,
            frame_sha256=[hashlib.sha256(video[i*frame_size:(i+1)*frame_size]).hexdigest() for i in range(48)],
            video_sha256=hashlib.sha256(video).hexdigest(),audio_sha256=hashlib.sha256(audio[0]).hexdigest(),
            all_48_decoded_10bit_frames_equal=True,all_384000_PCM_equal=True,decoded_audio_all_zero=True,
            GPU=gpu,restored_GPU=restored_gpu,before_GPU=before_gpu,preview=preview,package_sha256=sha(package),
            GIF_frames=count,GIF_duration_ms=milliseconds,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out/'verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('GPU','restored_GPU','before_GPU','preview','effects','frame_sha256','native_tools')},ensure_ascii=False))
    except BaseException as e:
        report.update(status='failed',error=repr(e));save(out/'verification.json',report);raise

if __name__=='__main__':main()
