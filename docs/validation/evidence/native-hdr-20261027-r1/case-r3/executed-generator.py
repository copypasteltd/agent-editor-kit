"""Actual registered installed Skill: owned HDR chart, GPU edit, SDR trim and package."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,hashlib,json,math,shutil,subprocess,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-hdr-20261027-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
W,H,N=640,360,48
PQ=dict(primaries='bt2020',transfer='pq-st2084',reference_white_nits=203)
WORK=dict(primaries='bt2020',transfer='linear',reference_white_nits=203)
MAP=dict(operator='reinhard-luminance',source_peak_nits=1000,target_peak_nits=100,exposure_stops=0,gamut_policy='clip')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def load(p):return json.loads(Path(p).read_bytes())


def source_frames():
    yy,xx=np.mgrid[:H,:W]
    mask=Image.new('L',(W,H),0);d=ImageDraw.Draw(mask)
    font=ImageFont.load_default(size=18)
    d.text((28,20),'AGENT EDITOR KIT / HDR DISPLAY LIGHT',font=font,fill=255)
    d.text((28,53),'PQ + HLG  |  linear edit + GPU bloom',font=ImageFont.load_default(size=14),fill=200)
    levels=[.1,1,10,50,100,203,400,700]
    for j,nits in enumerate(levels):d.text((30+73*j,161),str(nits),font=ImageFont.load_default(size=13),fill=255)
    d.text((28,190),'patch levels: cd/m2  |  paper white 203',font=ImageFont.load_default(size=14),fill=220)
    coverage=np.asarray(mask,np.float64)/255
    for i in range(N):
        rgb=np.broadcast_to((.5+12*xx/W)[...,None],(H,W,3)).copy()
        for j,nits in enumerate(levels):rgb[100:154,28+73*j:95+73*j,:]=nits
        center=90+460*i/(N-1)
        light=np.exp(-((xx-center)**2+(yy-264)**2)/(2*17**2))
        rgb[216:310,:,:]+=light[216:310,:,None]*np.array([680,460,220])
        rgb=rgb*(1-coverage[...,None])+203*coverage[...,None]
        # Scalar constants are independently written from the standard, without
        # importing the product implementation or using a source fallback.
        power=(rgb/10000)**(1305/8192)
        pq=((107/128+(2413/128)*power)/(1+(2392/128)*power))**(2523/32)
        yield np.moveaxis(np.rint(pq*65535).astype('<u2')[...,[1,2,0]],-1,0).tobytes()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('native-hdr-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/('docs/assets/native-hdr-20261027-'+a.run);public.mkdir(exist_ok=False)
    calls=[];project=work/'project'
    def run(name,argv,cli=False):
        argv=list(map(str,argv));started=time.perf_counter()
        r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=1200,creationflags=subprocess.CREATE_NO_WINDOW)
        output=(out if cli else work)/(name+('.stdout.json' if cli else '.bin'))
        output.write_bytes(r.stdout);stderr=out/(name+'.stderr.txt');stderr.write_bytes(r.stderr)
        calls.append(dict(id=name,argv=argv,exit_code=r.returncode,seconds=time.perf_counter()-started,
            stdout_sha256=sha(output),stdout_bytes=len(r.stdout),stderr_sha256=sha(stderr)))
        save(out/'calls.json',calls);print(json.dumps(dict(id=name,code=r.returncode)),flush=True)
        assert r.returncode==0,(name,r.stdout[-3000:],r.stderr[-3000:])
        if cli:
            v=json.loads(r.stdout);assert v['ok'];return v['data']
        return r.stdout
    def invoke(name,*args):return run(name,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',SKILL,*args],True)
    def native_video(name,movie):return run(name,[ffmpeg,'-nostdin','-v','error','-i',movie,'-map','0:v:0','-an',
        '-pix_fmt','yuv444p10le','-fps_mode','passthrough','-f','rawvideo','pipe:1'])
    def pcm(name,movie):return run(name,[ffmpeg,'-nostdin','-v','error','-i',movie,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
    def render(name,root):
        result=invoke(name,'render','--project',root,'--output',root/('renders/'+name+'.mkv'),'--container','mkv',
            '--video-codec','libx264','--crf','0','--pixel-format','yuv444p10le','--audio-codec','pcm_f32le',
            '--hardware-encode','off','--projection-acceleration','require','--projection-device','0.0')
        movie=Path(result['path']);manifest=load(movie.with_suffix('.mkv.manifest.json'))
        gp=manifest['delivery']['pixel_pipeline']['projection_acceleration']
        assert gp['operations']['glow']==N and gp['worker_closed'] and gp['shared_handles_closed']
        assert gp['control']['threads_closed'] and gp['control']['streams_closed']
        return movie,manifest
    report=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),registered_skill=True,
        native_windows=True,virtualization=False,source_fallback=False,synthetic_diagnostic=True,
        continuous_human_playback=False,human_listening=False,HDR_monitor_accepted=False,natural_quality_accepted=False)
    try:
        ffmpeg=Path(shutil.which('ffmpeg'));ffprobe=Path(shutil.which('ffprobe'))
        report['native_tools']={str(p):sha(p) for p in (ffmpeg,ffprobe)}
        report['manifest_sha256']=load(ROOT/'local/agent-ffmpeg/runtime.json')['manifest_sha256']
        assert invoke('version','version')['cli_version']=='0.1.40'
        assert invoke('capabilities','capabilities')['capabilities']['native_hdr_display_pipeline']['status']=='implemented_with_limits'
        raw=work/'source.gbrp16';raw.write_bytes(b''.join(source_frames()))
        run('source-encode',[ffmpeg,'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrp16le','-video_size',f'{W}x{H}',
            '-framerate','12','-i',raw,'-c:v','ffv1','-level','3','-pix_fmt','gbrp16le','-color_primaries','bt2020',
            '-color_trc','smpte2084','-colorspace','rgb','-color_range','pc',public/'source-pq.mkv'])
        badge=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(badge)
        d.rounded_rectangle((24,318,400,350),radius=6,fill=(230,240,255,225))
        d.text((34,325),'SDR ASSET / declared white 100 cd/m2',font=ImageFont.load_default(size=15),fill=(15,27,45,255))
        badge.save(public/'source-sdr-badge.png')
        t=np.arange(192000,dtype=np.float64)/48000
        sound=np.stack((.12*np.sin(2*np.pi*347*t),.10*np.cos(2*np.pi*523*t)),1).astype('<f4')
        audio=work/'original.f32';audio.write_bytes(sound.tobytes())
        run('source-audio',[ffmpeg,'-nostdin','-v','error','-f','f32le','-ar','48000','-ac','2','-i',audio,'-c:a','pcm_f32le',public/'source-stereo.wav'])
        invoke('init','project','init',project,'--name','C50 native HDR PQ HLG and SDR viewing')
        for asset,path in [('pq-chart',public/'source-pq.mkv'),('sdr-badge',public/'source-sdr-badge.png'),('stereo-tone',public/'source-stereo.wav')]:
            invoke('ingest-'+asset,'media','ingest','--project',project,'--input',path,'--asset-id',asset,
                '--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','all',
                '--evidence','Original contributor-generated diagnostic chart/badge/stereo tones; no external media.')
        p=load(project/'project.json');s=p['settings'];s['canvas'].update(width=W,height=H,background='#000000')
        s['timebase']['display_fps']={'num':12,'den':1};s['color']=dict(primaries='bt2020',transfer='smpte2084',matrix='bt2020nc',range='limited')
        s['output']=dict(container='mkv',video=dict(codec='libx264',crf=0,preset='ultrafast',pixel_format='yuv444p10le'),audio=dict(codec='pcm_f32le'))
        s['pixel_pipeline']=dict(engine='float32-native-v1',working_signal=WORK,output_signal=PQ,range_policy='clip',preview_mapping=MAP,sources={
            'pq-chart':dict(source_signal=PQ,demux_origin=0,display_geometry='square-unrotated'),
            'sdr-badge':dict(source_signal=dict(primaries='bt709',transfer='srgb',reference_white_nits=100),demux_origin=0,display_geometry='square-unrotated')})
        save(project/'project.json',p)
        effect=dict(type='bloom',parameters=dict(threshold=1,knee=.2,radius=4,gain=.25,intensity=.4),
            keyframes=[dict(property='intensity',keyframes=[dict(at_tick=0,value=.15,interpolation='ease_in_out'),
                dict(at_tick=360000,value=.6,interpolation='linear')])])
        ops=[]
        for track,kind,order,asset,fx in [('hdr','video',3,'pq-chart',[effect]),('badge','video',4,'sdr-badge',[]),('tone','audio',5,'stereo-tone',[])]:
            ops.append(dict(op='add_track',track_id=track,kind=kind,order=order))
            clip=dict(op='append_clip',track_id=track,id=track+'-clip',asset_id=asset,timeline_start_tick=0,duration_tick=360000,source_in_tick=0,source_out_tick=360000)
            if fx:clip['effects']=fx
            ops.append(clip)
        composition=work/'composition.json';save(composition,dict(operations=ops))
        invoke('compose','timeline','compose','--project',project,'--input',composition)
        invoke('validate','validate','--project',project)
        authored=load(project/'project.json');original_bytes=(project/'project.json').read_bytes()
        frame=invoke('frame-preview','preview','frame','--project',project,'--frame','24','--height',str(H))
        preview=invoke('range-preview','preview','range','--project',project,'--start-frame','0','--end-frame',str(N),'--height',str(H))
        assert (project/'project.json').read_bytes()==original_bytes
        pq_movie,pq_manifest=render('pq',project)
        exported=invoke('package','convert','export','--project',project,'--output',project/'exports/native-hdr.aevpkg.zip','--target-format','package')
        package=Path(exported['output']);restored=work/'restored';invoke('import','convert','import','--input',package,'--output',restored)
        migrated=load(restored/'project.json');assert migrated['settings']['pixel_pipeline']==authored['settings']['pixel_pipeline']
        restored_movie,restored_manifest=render('restored',restored)
        video=native_video('decode-pq',pq_movie);other=native_video('decode-restored',restored_movie)
        assert len(video)==N*W*H*6 and video==other
        audio_before=pcm('audio-pq',pq_movie);audio_after=pcm('audio-restored',restored_movie)
        assert len(audio_before)==384000*4 and audio_before==audio_after and np.max(np.abs(np.frombuffer(audio_before,'<f4')))>.1
        variant=work/'hlg';invoke('hlg-import','convert','import','--input',package,'--output',variant)
        hp=load(variant/'project.json');hp['settings']['pixel_pipeline']['output_signal']=dict(primaries='bt2020',transfer='hlg-bt2100',reference_white_nits=203,display_peak_nits=1000,system_gamma=1.2)
        hp['settings']['color']['transfer']='arib-std-b67';save(variant/'project.json',hp)
        invoke('hlg-validate','validate','--project',variant);hlg_movie,hlg_manifest=render('hlg',variant)
        trim=work/'sdr';invoke('sdr-import','convert','import','--input',package,'--output',trim)
        sp=load(trim/'project.json');sp['settings']['pixel_pipeline']['output_signal']=dict(primaries='bt709',transfer='srgb',reference_white_nits=100)
        sp['settings']['pixel_pipeline']['display_mapping']=MAP
        sp['settings']['color']=dict(primaries='bt709',transfer='iec61966-2-1',matrix='bt709',range='limited');save(trim/'project.json',sp)
        invoke('sdr-validate','validate','--project',trim);sdr_movie,sdr_manifest=render('sdr',trim)
        streams={}
        for name,movie,transfer in [('pq',pq_movie,'smpte2084'),('hlg',hlg_movie,'arib-std-b67'),('sdr',sdr_movie,'iec61966-2-1')]:
            probed=json.loads(run('probe-'+name,[ffprobe,'-v','error','-show_streams','-show_format','-of','json',movie]))
            v=next(v for v in probed['streams'] if v['codec_type']=='video')
            assert v['pix_fmt']=='yuv444p10le' and v['color_transfer']==transfer
            assert v['color_primaries']==('bt709' if name=='sdr' else 'bt2020')
            streams[name]=v
            shutil.copyfile(movie,public/(name+'-master.mkv'))
            shutil.copyfile(movie.with_suffix('.mkv.manifest.json'),public/(name+'-master.mkv.manifest.json'))
        shutil.copyfile(package,public/'editable-native-hdr.aevpkg.zip')
        shutil.copyfile(frame['path'],public/'preview-frame.png')
        shutil.copyfile(preview['path'],public/'sdr-preview.mp4')
        decoded=run('gif-source',[ffmpeg,'-nostdin','-v','error','-i',public/'sdr-preview.mp4','-an','-pix_fmt','rgb24','-fps_mode','passthrough','-f','rawvideo','pipe:1'])
        assert len(decoded)==N*W*H*3
        images=[Image.fromarray(np.frombuffer(decoded[i*W*H*3:(i+1)*W*H*3],np.uint8).reshape(H,W,3)) for i in range(N)]
        images[0].save(public/'hdr-sdr-view.gif',save_all=True,append_images=images[1:],duration=[80,80,90]*16,loop=0,optimize=False,disposal=2)
        with Image.open(public/'hdr-sdr-view.gif') as gif:
            assert gif.n_frames==N
            duration=sum((gif.seek(i),gif.info.get('duration',0))[1] for i in range(gif.n_frames));assert duration==4000
        save(public/'recipes.json',dict(PQ=PQ,working=WORK,preview_mapping=MAP,effect=effect,HDR_output='BT2020 NCL 10bit',SDR_badge_white_nits=100))
        (public/'SOURCE.txt').write_text('Original contributor-generated diagnostic chart, rendered lettering, badge and stereo tones: CC0-1.0. Reproduce with scripts/run_hdr_case_20261027.py. GIF/MP4 are explicit SDR viewing trims, not HDR monitor evidence.\n',encoding='utf8')
        save(public/'media-manifest.json',dict(files=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()],frames=N,width=W,height=H,fps=12,duration_seconds=4,license='CC0-1.0',HDR_monitor_accepted=False))
        report.update(status='passed',frames=N,all_48_decoded_10bit_frames_equal=True,all_384000_PCM_equal=True,
            PCM_nonzero=True,decoded_video_sha256=hashlib.sha256(video).hexdigest(),decoded_PCM_sha256=hashlib.sha256(audio_before).hexdigest(),
            package_sha256=sha(public/'editable-native-hdr.aevpkg.zip'),editable_absolute_signals_preserved=True,
            author_bytes_unchanged_by_preview=True,GIF_frames=N,GIF_duration_ms=duration,
            streams=streams,GPU=pq_manifest['delivery']['pixel_pipeline']['projection_acceleration'],
            output_boundary=pq_manifest['delivery']['pixel_pipeline']['last_output_color_boundary'],
            SDR_mapping=sdr_manifest['delivery']['pixel_pipeline']['last_display_mapping'],
            HLG_output_boundary=hlg_manifest['delivery']['pixel_pipeline']['last_output_color_boundary'],
            public=str(public),finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('streams','GPU','native_tools','output_boundary','SDR_mapping','HLG_output_boundary')},ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save(out/'verification.json',report);raise

if __name__=='__main__':main()
