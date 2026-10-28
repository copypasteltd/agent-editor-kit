"""C57: registered native Skill, independent colour oracles and GPU package replay."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,shutil,subprocess,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hlg-black-20261028-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
W,H,N=640,360,48
D60=[.32168,.33767];D65=[.3127,.329]
SOURCE=dict(primaries='bt2020',transfer='hlg-bt2100',reference_white_nits=203,display_peak_nits=1000,system_gamma=1.2,display_black_nits=.5)
WORK=dict(primaries='bt2020',transfer='linear',reference_white_nits=203)
OUTPUT=dict(primaries='bt2020',transfer='pq-st2084',reference_white_nits=203)
MAPPING=dict(operator='reinhard-luminance',source_peak_nits=1000,target_peak_nits=100,exposure_stops=0,gamut_policy='clip')
PATCHES=np.repeat(np.array([0,.002,.01,.03,.07,.2,.5,.9])[:,None],3,axis=1)
BT2020=np.array([[.6369580483012914,.14461690358620832,.1688809751641721],
    [.2627002120112671,.6779980715188708,.05930171646986196],[0,.028072693049087428,1.060985057710791]])
BT709=np.array([[506752/1228815,87881/245763,12673/70218],
    [87098/409605,175762/245763,12673/175545],[7918/409605,87881/737289,1001167/1053270]])

def hlg_nits(v,black=.5):
    # Independent Table5 scalar constants/vector math, no product imports.
    import math
    lift=math.sqrt(3)*math.exp(math.log(black/1000)/2.4) if black else 0
    x=lift+(1-lift)*v;aa=.17883277;bb=1-4*aa;cc=.5-aa*math.log(4*aa)
    scene=np.where(x<=.5,x*x/3,(np.exp((x-cc)/aa)+bb)/12)
    lum=scene@np.array([.2627,.678,.0593])
    return 1000*scene*lum[...,None]**.2

def pq(v):
    p=(np.maximum(v,0)/10000)**(2610/16384)
    return ((3424/4096+2413/128*p)/(1+2392/128*p))**(2523/32)

def display(v):
    x=np.einsum('ij,...j->...i',np.linalg.inv(BT709)@BT2020,v)/100
    lum=np.maximum(x@np.array([.2126,.7152,.0722]),0)
    mapped=lum*(1+lum/100)/(1+lum)
    return srgb(np.clip(x*np.divide(mapped,lum,out=np.zeros_like(lum),where=lum!=0)[...,None],0,1))

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def load(p):return json.loads(Path(p).read_bytes())
def decode(v):return np.where(np.abs(v)<=1/32,v/16,np.sign(v)*np.abs(v)**1.8)
def srgb(v):return np.where(np.abs(v)<=.0031308,12.92*v,np.sign(v)*(1.055*np.abs(v)**(1/2.4)-.055))

def source_frames():
    yy,xx=np.mgrid[:H,:W];mask=Image.new('L',(W,H),0);d=ImageDraw.Draw(mask)
    d.text((22,18),'AGENT EDITOR KIT / EXPLICIT HLG DISPLAY BLACK',font=ImageFont.load_default(size=16),fill=255)
    d.text((22,48),'HLG / 0.5 nit black / 1000 nit peak > linear > PQ',font=ImageFont.load_default(size=16),fill=230)
    d.text((22,173),'Neutral shadow patches | moving highlight + editable GPU Bloom',font=ImageFont.load_default(size=13),fill=230)
    coverage=np.asarray(mask,np.float64)/255
    for i in range(N):
        rgb=np.broadcast_to((.12+.18*xx/W)[...,None],(H,W,3)).copy()
        for j,v in enumerate(PATCHES):rgb[94:154,20+75*j:85+75*j]=v
        cx=85+470*i/(N-1);light=np.exp(-((xx-cx)**2+(yy-265)**2)/(2*19**2))
        rgb[210:320]+=light[210:320,:,None]*np.array([.72,.58,.4])
        rgb=rgb*(1-coverage[...,None])+.86*coverage[...,None]
        yield np.rint(np.clip(rgb,0,1)*65535).astype('<u2')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('native-hlg-black-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/('docs/assets/native-hlg-black-20261028-'+a.run);public.mkdir(exist_ok=False)
    ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
    project=work/'project';calls=[];checks=[]
    def run(name,argv,cli=False):
        argv=list(map(str,argv));start=time.perf_counter();r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=1500,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout=(out if cli else work)/(name+('.stdout.json' if cli else '.bin'));stdout.write_bytes(r.stdout)
        stderr=out/(name+'.stderr.txt');stderr.write_bytes(r.stderr)
        calls.append(dict(id=name,argv=argv,exit_code=r.returncode,seconds=time.perf_counter()-start,
            stdout_bytes=len(r.stdout),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
        save(out/'calls.json',calls);print(json.dumps(dict(id=name,exit_code=r.returncode)),flush=True)
        assert r.returncode==0,(name,r.stdout[-2000:],r.stderr[-2000:])
        if cli:
            v=json.loads(r.stdout);assert v['ok'] and v['provenance']['cli_version']=='0.1.47';return v['data']
        return r.stdout
    def invoke(name,*args):return run(name,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',SKILL,*args],True)
    def check(name,ok,**more):
        checks.append(dict(name=name,ok=bool(ok),**more));save(out/'checks.json',checks);assert ok,name
    def decoded(name,movie,audio=False):return run(name,[ffmpeg,'-nostdin','-v','error','-i',movie,
        *(['-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le'] if audio else
          ['-map','0:v:0','-an','-pix_fmt','yuv444p10le','-fps_mode','passthrough','-f','rawvideo']),'pipe:1'])
    def render(name,root):
        r=invoke(name,'render','--project',root,'--output',root/('renders/'+name+'.mkv'),
            '--hardware-encode','off','--projection-acceleration','require','--projection-device','0.0')
        m=load(r['manifest']);gpu=m['delivery']['pixel_pipeline']['projection_acceleration']
        check(name+'-actual-GPU',gpu['operations']['glow']==N and gpu['worker_closed'] and gpu['shared_handles_closed']
              and gpu['control']['threads_closed'] and gpu['control']['streams_closed'],glow_calls=gpu['operations']['glow'])
        return r,m
    report=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),registered_skill=True,
        native_windows=True,virtualization=False,source_fallback=False,synthetic_diagnostic=True,
        continuous_human_playback=False,human_listening=False,HDR_monitor_accepted=False,ICC_profile_parsed=False,full_ACES_transform=False)
    try:
        assert invoke('version','version')['cli_version']=='0.1.47'
        caps=invoke('capabilities','capabilities')['capabilities'];assert len(caps)==86 and caps['native_hlg_black_level']['status']=='implemented_with_limits'
        frames=list(source_frames());raw=work/'source.gbrp16le';raw.write_bytes(b''.join(np.moveaxis(v[...,[1,2,0]],-1,0).tobytes() for v in frames))
        run('original-encode',[ffmpeg,'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrp16le','-video_size',f'{W}x{H}',
            '-framerate','12','-i',raw,'-c:v','ffv1','-level','3','-pix_fmt','gbrp16le',public/'source-hlg-black.mkv'])
        t=np.arange(192000,dtype=np.float64)/48000;sound=np.stack((.12*np.sin(2*np.pi*347*t),.1*np.cos(2*np.pi*523*t)),1).astype('<f4')
        soundfile=work/'source.f32';soundfile.write_bytes(sound.tobytes())
        run('original-audio',[ffmpeg,'-nostdin','-v','error','-f','f32le','-ar','48000','-ac','2','-i',soundfile,'-c:a','pcm_f32le',public/'source-stereo.wav'])
        invoke('init','project','init',project,'--name','C57 native HLG display black')
        for asset,path in [('chart',public/'source-hlg-black.mkv'),('tones',public/'source-stereo.wav')]:
            invoke('ingest-'+asset,'media','ingest','--project',project,'--input',path,'--asset-id',asset,
                '--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','all','--evidence','Original contributor-generated C57 diagnostic media; no external footage.')
        p=load(project/'project.json');s=p['settings'];s['canvas'].update(width=W,height=H,background='#000000')
        s['timebase']['display_fps']=dict(num=12,den=1);s['color']=dict(primaries='bt2020',transfer='smpte2084',matrix='bt2020nc',range='limited')
        s['output']=dict(container='mkv',video=dict(codec='libx264',preset='ultrafast',crf=0,pixel_format='yuv444p10le'),audio=dict(codec='pcm_f32le'))
        s['pixel_pipeline']=dict(engine='float32-native-v1',working_signal=WORK,output_signal=OUTPUT,range_policy='clip',preview_mapping=MAPPING,
            sources=dict(chart=dict(source_signal=SOURCE,demux_origin=0,display_geometry='square-unrotated')))
        save(project/'project.json',p)
        effect=dict(type='bloom',parameters=dict(radius=4,threshold=3,knee=.05,gain=.2,intensity=.35))
        ops=[]
        for track,kind,order,asset in [('picture','video',3,'chart'),('audio','audio',4,'tones')]:
            ops.append(dict(op='add_track',track_id=track,kind=kind,order=order))
            clip=dict(op='append_clip',track_id=track,id=track+'-clip',asset_id=asset,timeline_start_tick=0,duration_tick=360000,source_in_tick=0,source_out_tick=360000)
            if kind=='video':clip['effects']=[effect]
            ops.append(clip)
        composition=work/'composition.json';save(composition,dict(operations=ops));invoke('compose','timeline','compose','--project',project,'--input',composition)
        invoke('validate','validate','--project',project);authored=load(project/'project.json')['settings']['pixel_pipeline']
        source_json=work/'source-signal.json';working_json=work/'working-signal.json'
        save(source_json,SOURCE);save(working_json,WORK)
        surface=invoke('surface','surface','export','--project',project,'--asset-id','chart','--output',project/'renders/linear-surface',
            '--source-signal-json',source_json,'--working-signal-json',working_json,'--stop-frame','1')
        source32=frames[0].astype(np.float32)/65535
        expected=hlg_nits(source32.astype(float))/203
        actual=np.fromfile(Path(surface['output'])/'frames.rgba-f32le','<f4').reshape(H,W,4)
        error=float(np.max(np.abs(actual[...,:3]-expected)))
        check('independent-entire-first-surface',error<1e-6 and np.all(actual[...,3]==1),pixels=W*H,maximum_error=error)
        first,manifest=render('edited',project);master=Path(first['path']);video=decoded('original-all-video',master)
        planes=np.frombuffer(video,'<u2').reshape(N,3,H,W);patch_errors=[];patch_records=[]
        for index in range(N):
          for j in range(8):
            rgb=frames[index][120,50+75*j].astype(np.float32)/65535
            expected_y=64+876*(pq(hlg_nits(rgb.astype(float)))@np.array([.2627,.678,.0593]))
            seen=float(planes[index,0,110:138,35+75*j:70+75*j].mean());patch_errors.append(abs(seen-expected_y))
            patch_records.append(dict(frame=index,patch=j,expected=float(expected_y),actual=seen,error=abs(seen-expected_y)))
        save(out/'independent-every-frame-patches.json',dict(status='passed' if max(patch_errors)<1.6 else 'failed',comparisons=len(patch_records),maximum_luma_code_error=max(patch_errors),product_code_imported=False,records=patch_records))
        check('actual-encoded-neutral-and-colour-patches',max(patch_errors)<1.6,patch_count=8,frames=N,maximum_luma_code_error=max(patch_errors))
        before=(project/'project.json').read_bytes()
        frame=invoke('preview-frame','preview','frame','--project',project,'--frame','24','--height',str(H))
        preview=invoke('preview-range','preview','range','--project',project,'--start-frame','0','--end-frame',str(N),'--height',str(H))
        check('previews-preserve-author',(project/'project.json').read_bytes()==before)
        package=public/'editable-hlg-black.aevpkg.zip';invoke('export','convert','export','--project',project,'--output',package,'--target-format','package')
        restored=work/'restored';invoke('import-replay','convert','import','--input',package,'--output',restored);invoke('validate-replay','validate','--project',restored)
        check('package-preserves-all-signals',load(restored/'project.json')['settings']['pixel_pipeline']==authored)
        second,replay=render('replayed',restored);other=decoded('replayed-all-video',second['path'])
        a1=decoded('original-all-PCM',master,True);a2=decoded('replayed-all-PCM',second['path'],True)
        check('all-decoded-video-identical',video==other and len(video)==N*W*H*6,frames=N,bytes=len(video))
        check('all-PCM-identical',a1==a2 and len(a1)==384000*4 and np.max(np.abs(np.frombuffer(a1,'<f4')))>.1,scalar_samples=384000)
        for src,dst in [(master,'edited-master.mkv'),(Path(first['manifest']),'edited-master.mkv.manifest.json'),(Path(frame['path']),'actual-frame.png'),(Path(preview['path']),'actual-preview.mp4')]:shutil.copyfile(src,public/dst)
        save(public/'signals.json',dict(source=SOURCE,working=WORK,output=OUTPUT,automatic_ICC_inference=False))
        run('gif',[ffmpeg,'-nostdin','-v','error','-i',public/'actual-preview.mp4','-vf',
            'fps=6,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse','-loop','0',public/'actual-preview.gif'])
        with Image.open(public/'actual-preview.gif') as im:
            duration=0;count=im.n_frames
            for i in range(count):im.seek(i);duration+=im.info['duration']
        check('actual-GIF-clock',count==24 and abs(duration-4000)<=10,frames=count,duration_ms=duration)
        # Explicitly labelled mathematical control; not falsely presented as an engine render.
        control32=frames[24].astype(np.float32)/65535
        control=Image.fromarray(np.rint(np.clip(display(hlg_nits(control32.astype(float),black=0)),0,1)*255).astype(np.uint8))
        control.save(public/'independent-zero-black-control.png')
        sheet=Image.new('RGB',(W*2,H+110),'#111927');sheet.paste(control,(0,0));sheet.paste(Image.open(public/'actual-frame.png').convert('RGB'),(W,0))
        draw=ImageDraw.Draw(sheet);font=ImageFont.load_default(size=18)
        for x,lines in [(20,['INDEPENDENT ZERO-BLACK CONTROL / no glow','Same HLG codes; ideal zero-nit display black']),
                        (W+20,['ACTUAL ENGINE / 0.5-nit HLG black + GPU Bloom','Explicit display declaration; SDR review only'])]:
            for i,line in enumerate(lines):draw.text((x,H+15+i*31),line,font=font,fill='#f1f4ff')
        sheet.save(public/'comparison.png')
        (public/'SOURCE.txt').write_text('C57 / agent editor kit CLI0.1.47\nOriginal generated RGB16 chart, lettering and stereo tones: CC0-1.0.\n'
            'Declared BT.2020 HLG: reference203, peak1000, black0.5 nits, gamma1.2. Black0.5 is an intentional diagnostic declaration, not measured monitor calibration.\n'
            'Actual native Windows/OpenCL Bloom, CPU x264 ten-bit PQ master; separate explicit modified-Reinhard SDR previews.\n'
            'Independent zero-black/no-glow mathematical control; published ITU-R BT.2100-3 Table5 facts, original implementation, no copied standard pages.\n'
            'No human continuous playback/listening, natural-image aesthetic or HDR monitor acceptance claimed.\n',encoding='utf8')
        files=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()]
        save(public/'media-manifest.json',dict(case='C57',files=files,public_media_rights='Original contributor-generated CC0 diagnostic media',
            human_listening=False,continuous_human_playback=False,HDR_monitor_accepted=False,mathematical_control_is_engine_render=False,declared_black_nits=.5))
        report.update(status='passed',checks=checks,project=str(project),restored=str(restored),public_directory=str(public),
            decoded_video_bytes=len(video),PCM_scalar_samples=384000,GPU_glow_calls_per_render=N,render_count=2,
            independent_surface_pixels=W*H,maximum_surface_error=error,maximum_patch_luma_code_error=max(patch_errors),
            files=files,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('files','checks')},ensure_ascii=False),flush=True)
    except BaseException as e:report.update(status='failed',error=repr(e),checks=checks);save(out/'verification.json',report);raise
if __name__=='__main__':main()
