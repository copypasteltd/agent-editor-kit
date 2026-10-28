"""C56: registered native Skill, independent colour oracles and GPU package replay."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,shutil,subprocess,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-icc-20261028-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
W,H,N=640,360,48
D60=[.32168,.33767];D65=[.3127,.329]
SOURCE=None
WORK=dict(primaries='aces-ap1',transfer='linear',white_xy=D60)
OUTPUT=dict(primaries='bt709',transfer='srgb')
# Independent published reference matrices, not imported from product code.
CAT=np.array([[.955473421488075,-.02309845494876471,.06325924320057072],
    [-.0283697093338637,1.0099953980813041,.021041441191917323],
    [.012314014864481998,-.020507649298898964,1.330365926242124]])
PROPHOTO=np.array([[.7977666449006423,.13518129740053308,.0313477341283922],
    [.2880748288194013,.711835234241873,.00008993693872564],[0,0,.8251046025104602]])
BT709=np.array([[506752/1228815,87881/245763,12673/70218],
    [87098/409605,175762/245763,12673/175545],[7918/409605,87881/737289,1001167/1053270]])
AP1=np.array([[.6624541811,.1340042065,.1561876870],[.2722287168,.6740817658,.0536895174],
    [-.0055746495,.0040607335,1.0103391003]])
PATCHES=np.array([[.1,.1,.1],[.25,.25,.25],[.5,.5,.5],[.7,.7,.7],
    [.68,.45,.35],[.3,.6,.46],[.3,.42,.64],[.65,.42,.55]])

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def load(p):return json.loads(Path(p).read_bytes())
def decode(v):return np.where(np.abs(v)<=1/32,v/16,np.sign(v)*np.abs(v)**1.8)
def srgb(v):return np.where(np.abs(v)<=.0031308,12.92*v,np.sign(v)*(1.055*np.abs(v)**(1/2.4)-.055))

def source_frames():
    yy,xx=np.mgrid[:H,:W];mask=Image.new('L',(W,H),0);d=ImageDraw.Draw(mask)
    d.text((22,18),'AGENT EDITOR KIT / NATIVE ICC SOURCE PROFILE',font=ImageFont.load_default(size=16),fill=255)
    d.text((22,48),'RGB ICC D50 > linear AP1 D60 > BT.709 D65',font=ImageFont.load_default(size=16),fill=230)
    d.text((22,173),'Neutral / colour patches | moving highlight + editable GPU Bloom',font=ImageFont.load_default(size=13),fill=230)
    coverage=np.asarray(mask,np.float64)/255
    for i in range(N):
        rgb=np.broadcast_to((.12+.18*xx/W)[...,None],(H,W,3)).copy()
        for j,v in enumerate(PATCHES):rgb[94:154,20+75*j:85+75*j]=v
        cx=85+470*i/(N-1);light=np.exp(-((xx-cx)**2+(yy-265)**2)/(2*19**2))
        rgb[210:320]+=light[210:320,:,None]*np.array([.72,.58,.4])
        rgb=rgb*(1-coverage[...,None])+.86*coverage[...,None]
        yield np.rint(np.clip(rgb,0,1)*65535).astype('<u2')

PROFILE_AUTHOR="from pathlib import Path\nimport ctypes as C,json,sys\ninstalled=Path(sys.argv[1]);sys.path.insert(0,str(installed/'site'))\nfrom ai_ad_editor import icc_profiles as icc\na=icc.api(icc.runtime_paths()[2]);p=C.c_void_p\nfor name,result,args in [('cmsSetProfileVersion',None,[p,C.c_double]),('cmsMLUalloc',p,[p,C.c_uint32]),('cmsMLUsetASCII',C.c_int,[p,C.c_char_p,C.c_char_p,C.c_char_p]),('cmsMLUfree',None,[p]),('cmsWriteTag',C.c_int,[p,C.c_uint32,p])]:\n f=getattr(a,name);f.restype=result;f.argtypes=args\nctx=a.cmsCreateContext(None,None);curve=a.cmsBuildGamma(ctx,1.8);white=icc.xyY(.3457,.3585,1)\nprim=icc.Primaries(*(icc.xyY(x,y,1) for x,y in ((.7347,.2653),(.1596,.8404),(.0366,.0001))))\nprofile=None;mlu=None\ntry:\n profile=a.cmsCreateRGBProfileTHR(ctx,C.byref(white),C.byref(prim),(p*3)(curve,curve,curve));assert profile\n a.cmsSetProfileVersion(profile,4.3);mlu=a.cmsMLUalloc(ctx,1);assert mlu\n assert a.cmsMLUsetASCII(mlu,b'en',b'US',b'AEK original C56 ProPhoto D50 gamma1.8 diagnostic / CC0')\n assert a.cmsWriteTag(profile,int.from_bytes(b'desc','big'),mlu)\n n=C.c_uint32();assert a.cmsSaveProfileToMem(profile,None,C.byref(n));buffer=C.create_string_buffer(n.value)\n assert a.cmsSaveProfileToMem(profile,buffer,C.byref(n));Path(sys.argv[2]).write_bytes(buffer.raw[:n.value])\nfinally:\n if mlu:a.cmsMLUfree(mlu)\n if profile:a.cmsCloseProfile(profile)\n a.cmsFreeToneCurve(curve);a.cmsDeleteContext(ctx)\nprint(json.dumps(dict(profile=str(sys.argv[2]),sha256=icc.sha(sys.argv[2]),original_generated=True,native_handles_closed=True,product_module=str(icc.__file__))))\n"

def main():
    global SOURCE
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('native-icc-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/('docs/assets/native-icc-20261028-'+a.run);public.mkdir(exist_ok=False)
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
            v=json.loads(r.stdout);assert v['ok'] and v['provenance']['cli_version']=='0.1.46';return v['data']
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
        continuous_human_playback=False,human_listening=False,HDR_monitor_accepted=False,ICC_profile_parsed=True,full_ACES_transform=False)
    try:
        assert invoke('version','version')['cli_version']=='0.1.46'
        caps=invoke('capabilities','capabilities')['capabilities'];assert len(caps)==85 and caps['native_icc_source_profiles']['status']=='implemented_with_limits'
        frames=list(source_frames());raw=work/'source.gbrp16le';raw.write_bytes(b''.join(np.moveaxis(v[...,[1,2,0]],-1,0).tobytes() for v in frames))
        run('original-encode',[ffmpeg,'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrp16le','-video_size',f'{W}x{H}',
            '-framerate','12','-i',raw,'-c:v','ffv1','-level','3','-pix_fmt','gbrp16le',public/'source-prophoto-d50.mkv'])
        t=np.arange(192000,dtype=np.float64)/48000;sound=np.stack((.12*np.sin(2*np.pi*347*t),.1*np.cos(2*np.pi*523*t)),1).astype('<f4')
        soundfile=work/'source.f32';soundfile.write_bytes(sound.tobytes())
        run('original-audio',[ffmpeg,'-nostdin','-v','error','-f','f32le','-ar','48000','-ac','2','-i',soundfile,'-c:a','pcm_f32le',public/'source-stereo.wav'])
        invoke('init','project','init',project,'--name','C56 native ICC source management')
        helper=out/'executed-profile-author.py';helper.write_text(PROFILE_AUTHOR,encoding='utf8',newline='\n')
        installed=Path(load(ROOT/'local/agent-ffmpeg/runtime.json')['installed_directory'])
        run('original-ICC-author',['C:/Python313/python.exe','-I','-S','-B','-u','-X','utf8',helper,installed,public/'source.icc'])
        shutil.copyfile(public/'source.icc',project/'assets/source.icc')
        SOURCE=dict(icc_profile='assets/source.icc',sha256='sha256:'+sha(public/'source.icc'),intent='relative-colorimetric',black_point_compensation=False)
        inspection=invoke('inspect-ICC','surface','inspect-profile','--project',project,'--input','assets/source.icc')
        check('actual-native-ICC-inspection',inspection['CMM_encoded_version']==2190 and inspection['matrix_shaper'] and inspection['native_handles_closed'])
        for asset,path in [('chart',public/'source-prophoto-d50.mkv'),('tones',public/'source-stereo.wav')]:
            invoke('ingest-'+asset,'media','ingest','--project',project,'--input',path,'--asset-id',asset,
                '--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','all','--evidence','Original contributor-generated C56 diagnostic media; no external footage.')
        p=load(project/'project.json');s=p['settings'];s['canvas'].update(width=W,height=H,background='#000000')
        s['timebase']['display_fps']=dict(num=12,den=1);s['color']=dict(primaries='bt709',transfer='iec61966-2-1',matrix='bt709',range='limited')
        s['output']=dict(container='mkv',video=dict(codec='libx264',preset='ultrafast',crf=0,pixel_format='yuv444p10le'),audio=dict(codec='pcm_f32le'))
        s['pixel_pipeline']=dict(engine='float32-native-v1',working_signal=WORK,output_signal=OUTPUT,range_policy='clip',
            sources=dict(chart=dict(source_signal=SOURCE,demux_origin=0,display_geometry='square-unrotated')))
        save(project/'project.json',p)
        effect=dict(type='bloom',parameters=dict(radius=4,threshold=.75,knee=.05,gain=.2,intensity=.35))
        ops=[]
        for track,kind,order,asset in [('picture','video',3,'chart'),('audio','audio',4,'tones')]:
            ops.append(dict(op='add_track',track_id=track,kind=kind,order=order))
            clip=dict(op='append_clip',track_id=track,id=track+'-clip',asset_id=asset,timeline_start_tick=0,duration_tick=360000,source_in_tick=0,source_out_tick=360000)
            if kind=='video':clip['effects']=[effect]
            ops.append(clip)
        composition=work/'composition.json';save(composition,dict(operations=ops));invoke('compose','timeline','compose','--project',project,'--input',composition)
        invoke('validate','validate','--project',project);authored=load(project/'project.json')['settings']['pixel_pipeline']
        surface=invoke('surface','surface','export','--project',project,'--asset-id','chart','--output',project/'renders/ap1-surface',
            '--source-icc-profile','assets/source.icc','--source-icc-sha256',SOURCE['sha256'],'--source-icc-intent','relative-colorimetric','--working-primaries','aces-ap1','--working-transfer','linear',
            '--working-white-xy',*map(str,D60),'--stop-frame','1')
        # Independent D60->D65 Bradford matrix; published D50->D65 is above.
        b=np.array([[.8951,.2664,-.1614],[-.7502,1.7135,.0367],[.0389,-.0685,1.0296]])
        def white(xy):return np.array([xy[0]/xy[1],1,(1-sum(xy))/xy[1]])
        d60to65=np.linalg.inv(b)@np.diag((b@white(D65))/(b@white(D60)))@b
        matrix=np.linalg.inv(AP1)@np.linalg.inv(d60to65)@CAT@PROPHOTO
        source32=frames[0].astype(np.float32)/65535
        expected=np.einsum('ij,hwj->hwi',matrix,decode(source32.astype(float)))
        actual=np.fromfile(Path(surface['output'])/'frames.rgba-f32le','<f4').reshape(H,W,4)
        error=float(np.max(np.abs(actual[...,:3]-expected)))
        check('independent-entire-first-surface',error<2e-4 and np.all(actual[...,3]==1),pixels=W*H,maximum_error=error)
        first,manifest=render('edited',project);master=Path(first['path']);video=decoded('original-all-video',master)
        cmm=manifest['delivery']['pixel_pipeline']['source_receipts']['chart']['ICC_transform']
        check('actual-render-native-CMM',cmm['native_handles_closed'] and cmm['source_profile']==SOURCE|dict(reference_white_nits=None) and cmm['rendering_intent']=='relative-colorimetric')
        planes=np.frombuffer(video,'<u2').reshape(N,3,H,W);patch_errors=[]
        for j in range(8):
            rgb=frames[0][120,50+75*j].astype(np.float32)/65535
            mapped=np.linalg.inv(BT709)@CAT@PROPHOTO@decode(rgb.astype(float))
            # Final SDR integer delivery explicitly clips encoded RGB. The
            # independent oracle must include that boundary, not signed RGB.
            expected_y=64+876*(np.clip(srgb(mapped),0,1)@np.array([.2126,.7152,.0722]))
            seen=float(planes[:,0,110:138,35+75*j:70+75*j].mean());patch_errors.append(abs(seen-expected_y))
        check('actual-encoded-neutral-and-colour-patches',max(patch_errors)<1.6,patch_count=8,frames=N,maximum_luma_code_error=max(patch_errors))
        before=(project/'project.json').read_bytes()
        frame=invoke('preview-frame','preview','frame','--project',project,'--frame','24','--height',str(H))
        preview=invoke('preview-range','preview','range','--project',project,'--start-frame','0','--end-frame',str(N),'--height',str(H))
        check('previews-preserve-author',(project/'project.json').read_bytes()==before)
        package=public/'editable-icc.aevpkg.zip';invoke('export','convert','export','--project',project,'--output',package,'--target-format','package')
        restored=work/'restored';invoke('import-replay','convert','import','--input',package,'--output',restored);invoke('validate-replay','validate','--project',restored)
        check('package-preserves-all-signals',load(restored/'project.json')['settings']['pixel_pipeline']==authored)
        check('package-preserves-exact-ICC',sha(restored/'assets/source.icc')==sha(public/'source.icc'))
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
        control=np.einsum('ij,hwj->hwi',np.linalg.inv(BT709)@PROPHOTO,decode(control32.astype(float)))
        control=Image.fromarray(np.rint(np.clip(srgb(control),0,1)*255).astype(np.uint8));control.save(public/'independent-no-CAT-control.png')
        sheet=Image.new('RGB',(W*2,H+110),'#111927');sheet.paste(control,(0,0));sheet.paste(Image.open(public/'actual-frame.png').convert('RGB'),(W,0))
        draw=ImageDraw.Draw(sheet);font=ImageFont.load_default(size=18)
        for x,lines in [(20,['INDEPENDENT NO-ADAPTATION CONTROL / no glow','D50 XYZ interpreted without white matching']),
                        (W+20,['ACTUAL ENGINE / ICC D50 > D60 > D65 + GPU Bloom','Native LittleCMS ICC; not full ACES output'])]:
            for i,line in enumerate(lines):draw.text((x,H+15+i*31),line,font=font,fill='#f1f4ff')
        sheet.save(public/'comparison.png')
        (public/'SOURCE.txt').write_text('C56 / agent editor kit CLI0.1.46\nOriginal contributor-generated diagnostic chart,lettering,stereo tones: CC0-1.0.\n'
            'Original RGB ICC v4.3 gamma1.8 ProPhoto D50 profile generated by installed LittleCMS; CC0 diagnostic data. All source code values exceed the ProPhoto toe. Profile is explicit,not inferred from embedded metadata.\n'
            'Actual native Windows/OpenCL edit and CPU x264 encoding. Mathematical no-CAT control is independent and has no glow.\n'
            'Published colour constants: W3C CSS Color4 and Academy ACEScg specification. No copied library implementation.\n'
            'Actual native ICC source conversion to linear AP1 D60. No arbitrary output ICC,softproof,CMYK,automatic embedded-profile/physical-white inference or full ACES output transform.\n'
            'No human continuous playback/listening,HDR monitor or natural-footage acceptance claimed.\n',encoding='utf8')
        files=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()]
        save(public/'media-manifest.json',dict(case='C56',files=files,public_media_rights='Original contributor-generated CC0 diagnostic media',
            human_listening=False,continuous_human_playback=False,HDR_monitor_accepted=False,mathematical_control_is_engine_render=False))
        report.update(status='passed',checks=checks,project=str(project),restored=str(restored),public_directory=str(public),
            decoded_video_bytes=len(video),PCM_scalar_samples=384000,GPU_glow_calls_per_render=N,render_count=2,
            independent_surface_pixels=W*H,maximum_surface_error=error,maximum_patch_luma_code_error=max(patch_errors),original_ICC_sha256=sha(public/'source.icc'),
            files=files,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('files','checks')},ensure_ascii=False),flush=True)
    except BaseException as e:report.update(status='failed',error=repr(e),checks=checks);save(out/'verification.json',report);raise
if __name__=='__main__':main()
