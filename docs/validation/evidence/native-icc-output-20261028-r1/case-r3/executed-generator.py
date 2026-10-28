"""C58: installed Skill, original ICC CLUT, GPU editing and exact delivery replay."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,hashlib,json,shutil,subprocess,sys,time,zlib,struct
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-icc-output-20261028-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
W,H,N=640,360,48
LINEAR=dict(primaries='bt709',transfer='linear');OUTPUT=dict(primaries='bt709',transfer='srgb')
PATCHES=np.array([[.02,.02,.02],[.06,.06,.06],[.12,.12,.12],[.25,.25,.25],[.3,.08,.04],[.04,.25,.08],[.06,.1,.3],[.2,.16,.06]])
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def load(p):return json.loads(Path(p).read_bytes())
def pixels(path):
    data=Path(path).read_bytes();offset=8;parts=[]
    while offset<len(data):
        n=int.from_bytes(data[offset:offset+4],'big');kind=data[offset+4:offset+8]
        if kind==b'IDAT':parts.append(data[offset+8:offset+8+n])
        offset+=n+12
    raw=zlib.decompress(b''.join(parts));rows=np.frombuffer(raw,np.uint8).reshape(H,W*8+1);assert not rows[:,0].any()
    return np.frombuffer(rows[:,1:].tobytes(),'>u2').reshape(H,W,4)
def frames():
    yy,xx=np.mgrid[:H,:W];mask=Image.new('L',(W,H),0);d=ImageDraw.Draw(mask)
    d.text((20,18),'AGENT EDITOR KIT / REAL ICC OUTPUT + SOFT PROOF',font=ImageFont.load_default(size=16),fill=255)
    d.text((20,51),'Original bidirectional RGB CLUT / diagnostic, not a printer match',font=ImageFont.load_default(size=13),fill=255)
    d.text((20,176),'Linear source > editable GPU Bloom > profile-embedded PNG16',font=ImageFont.load_default(size=13),fill=255)
    coverage=np.asarray(mask,float)/255
    for i in range(N):
        rgb=np.broadcast_to((.04+.11*xx/W)[...,None],(H,W,3)).copy()
        for j,v in enumerate(PATCHES):rgb[96:154,20+75*j:85+75*j]=v
        cx=80+480*i/(N-1);light=np.exp(-((xx-cx)**2+(yy-270)**2)/(2*17**2))
        rgb[218:325]+=light[218:325,:,None]*np.array([.8,.65,.45])
        rgb=rgb*(1-coverage[...,None])+.75*coverage[...,None]
        yield np.rint(np.clip(rgb,0,1)*65535).astype('<u2')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('native-icc-output-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/('docs/assets/native-icc-output-20261028-'+a.run);public.mkdir(exist_ok=False)
    project=work/'project';calls=[];checks=[];ffmpeg=shutil.which('ffmpeg');assert ffmpeg
    def run(name,argv,cli=False):
        argv=list(map(str,argv));start=time.perf_counter();r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=1800,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout=(out if cli else work)/(name+('.stdout.json' if cli else '.bin'));stdout.write_bytes(r.stdout)
        stderr=out/(name+'.stderr.txt');stderr.write_bytes(r.stderr)
        calls.append(dict(id=name,argv=argv,exit_code=r.returncode,seconds=time.perf_counter()-start,stdout_bytes=len(r.stdout),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
        save(out/'calls.json',calls);print(json.dumps(dict(id=name,exit_code=r.returncode)),flush=True)
        assert r.returncode==0,(name,r.stdout[-3000:],r.stderr[-3000:])
        if cli:
            value=json.loads(r.stdout);assert value['ok'] and value['provenance']['cli_version']=='0.1.48';return value['data']
        return r.stdout
    def invoke(name,*args):return run(name,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',SKILL,*args],True)
    def check(name,ok,**more):
        checks.append(dict(name=name,ok=bool(ok),**more));save(out/'checks.json',checks);assert ok,name
    def decoded(name,path,audio=False):return run(name,[ffmpeg,'-nostdin','-v','error','-i',path,*(['-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le'] if audio else ['-map','0:v:0','-an','-pix_fmt','yuv444p10le','-fps_mode','passthrough','-f','rawvideo']),'pipe:1'])
    report=dict(status='running',registered_skill=True,native_windows=True,virtualization=False,source_fallback=False,
        started_at_utc=datetime.now(timezone.utc).isoformat(),human_listening=False,continuous_human_playback=False,
        display_or_printer_accepted=False,full_goal_complete=False)
    try:
        assert invoke('version','version')['cli_version']=='0.1.48'
        assert len(invoke('capabilities','capabilities')['capabilities'])==87
        source=list(frames());raw=work/'source.gbrp16le';raw.write_bytes(b''.join(np.moveaxis(v[...,[1,2,0]],-1,0).tobytes() for v in source))
        run('source-encode',[ffmpeg,'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrp16le','-video_size',f'{W}x{H}',
            '-framerate','12','-i',raw,'-c:v','ffv1','-level','3','-pix_fmt','gbrp16le',public/'source-linear.mkv'])
        t=np.arange(192000,dtype=float)/48000;sound=np.stack((.12*np.sin(2*np.pi*347*t),.1*np.cos(2*np.pi*523*t)),1).astype('<f4')
        (work/'source.f32').write_bytes(sound.tobytes())
        run('source-audio',[ffmpeg,'-nostdin','-v','error','-f','f32le','-ar','48000','-ac','2','-i',work/'source.f32','-c:a','pcm_f32le',public/'source-stereo.wav'])
        invoke('init','project','init',project,'--name','C58 native ICC output and proof')
        for asset,path in [('chart',public/'source-linear.mkv'),('tones',public/'source-stereo.wav')]:
            invoke('ingest-'+asset,'media','ingest','--project',project,'--input',path,'--asset-id',asset,'--license-spdx','CC0-1.0',
                '--verification-status','verified','--permitted-use','all','--evidence','Original contributor-generated C58 diagnostic chart and tones; no external footage.')
        installed=Path(load(BASE/'installation-final-r1/verification.json')['installed'])
        sys.path[:0]=[str(installed/'site'),str(ROOT/'product/tests')]
        from test_icc_output import create_clut
        signal=create_clut(project/'original-proof.icc');profile={k:v for k,v in vars(signal).items() if v is not None};save(public/'profile.json',profile)
        shutil.copyfile(project/'original-proof.icc',public/'original-proof.icc')
        p=load(project/'project.json');s=p['settings'];s['canvas'].update(width=W,height=H,background='#000000')
        s['timebase']['display_fps']=dict(num=12,den=1);s['color']=dict(primaries='bt709',transfer='iec61966-2-1',matrix='bt709',range='limited')
        s['projection_acceleration']=dict(mode='require',device='0.0',max_working_bytes=256*1024**2)
        s['output']=dict(container='mkv',video=dict(codec='libx264',preset='ultrafast',crf=0,pixel_format='yuv444p10le'),audio=dict(codec='pcm_f32le'))
        s['pixel_pipeline']=dict(engine='float32-native-v1',working_signal=LINEAR,output_signal=OUTPUT,range_policy='clip',
            sources=dict(chart=dict(source_signal=LINEAR,demux_origin=0,display_geometry='square-unrotated')),
            proofing=dict(profile=profile,simulation_intent='relative-colorimetric'))
        save(project/'project.json',p);ops=[]
        for track,kind,asset in [('picture','video','chart'),('sound','audio','tones')]:
            ops.append(dict(op='add_track',track_id=track,kind=kind,order=3 if kind=='video' else 4))
            clip=dict(op='append_clip',track_id=track,id=track+'-clip',asset_id=asset,timeline_start_tick=0,duration_tick=360000,source_in_tick=0,source_out_tick=360000)
            if kind=='video':clip['effects']=[dict(type='bloom',parameters=dict(radius=4,threshold=.6,knee=.05,gain=.2,intensity=.35))]
            ops.append(clip)
        save(work/'compose.json',dict(operations=ops));invoke('compose','timeline','compose','--project',project,'--input',work/'compose.json')
        invoke('validate','validate','--project',project);save(work/'profile.json',profile)
        seq=load(project/'project.json')['sequences'][0]['id']
        def sequence(name,root,target):
            save(work/(name+'-target.json'),target)
            result=invoke(name,'surface','render','--project',root,'--sequence-id',seq,'--output',root/'renders'/name,
                '--output-profile-json',work/(name+'-target.json'),'--range-policy','clip')
            verified=invoke(name+'-inspect','surface','inspect-output','--project',root,'--input',result['output'])
            m=load(result['manifest']);g=m['timeline']['projection_acceleration']
            check(name+'-GPU',g['operations']['glow']==N and g['worker_closed'] and g['control']['threads_closed'],glow_calls=g['operations']['glow'])
            check(name+'-all-frames-and-PCM',verified['frames']==N and verified['audio_scalars']==384000)
            return result,m,verified
        first,manifest,verified=sequence('icc-delivery',project,profile)
        matrix=np.array([[.4360747,.3850649,.1430804],[.2225045,.7168786,.0606169],[.0139322,.0971045,.7141733]])
        errors=[];records=[]
        for i in range(N):
            actual=pixels(Path(first['output'])/f'frame-{i:09d}.png')
            for j in range(8):
                rgb=source[i][120,50+75*j].astype(np.float32).astype(float)/65535;xyz=matrix@rgb
                # Independent separable table interpolation in ICC XYZ16 PCS.
                position=xyz*8;lo=np.floor(position).astype(int);f=position-lo
                table=lambda index:np.rint((.05+.12*(index/8)**2)*65535)
                expected=table(lo)*(1-f)+table(lo+1)*f
                error=float(np.max(np.abs(actual[120,50+75*j,:3].astype(float)-expected)))
                errors.append(error);records.append(dict(frame=i,patch=j,error_codes=error))
        check('independent-every-frame-B2A-patches',max(errors)<5,comparisons=len(errors),maximum_error_codes=max(errors))
        save(out/'independent-every-frame-patches.json',dict(status='passed',comparisons=len(errors),maximum_error_codes=max(errors),records=records))
        movie=invoke('proof-master','render','--project',project,'--output',project/'renders/proof-master.mkv')
        m=load(movie['manifest']);proof=m['delivery']['pixel_pipeline']['ICC_proofing']
        check('actual-common-native-proof',proof['converted_frames']==N and proof['native_handles_closed'])
        before=(project/'project.json').read_bytes()
        frame=invoke('preview-frame','preview','frame','--project',project,'--frame','24','--height',str(H))
        preview=invoke('preview-range','preview','range','--project',project,'--start-frame','0','--end-frame',str(N),'--height',str(H))
        check('previews-preserve-author',before==(project/'project.json').read_bytes())
        package=public/'editable-icc-output.aevpkg.zip';invoke('export','convert','export','--project',project,'--output',package,'--target-format','package')
        restored=work/'restored';invoke('import','convert','import','--input',package,'--output',restored);invoke('validate-restored','validate','--project',restored)
        restored_profile=load(restored/'project.json')['settings']['pixel_pipeline']['proofing']['profile']
        check('proof-profile-portable',restored_profile['icc_profile'].startswith('assets/color-profiles/') and sha(restored/restored_profile['icc_profile'])==profile['sha256'][7:])
        replay,replay_manifest,replay_verified=sequence('icc-replayed',restored,restored_profile)
        check('all-PNG-pixels-replay-exact',verified['ordered_pixel_hashes_sha256']==replay_verified['ordered_pixel_hashes_sha256'])
        check('all-PNG-file-bytes-exact',all((Path(first['output'])/f'frame-{i:09d}.png').read_bytes()==(Path(replay['output'])/f'frame-{i:09d}.png').read_bytes() for i in range(N)))
        check('all-PCM-replay-exact',(Path(first['output'])/'audio.f32le').read_bytes()==(Path(replay['output'])/'audio.f32le').read_bytes()==sound.tobytes())
        replay_movie=invoke('proof-master-replay','render','--project',restored,'--output',restored/'renders/proof-master-replay.mkv')
        video=decoded('original-all-video',movie['path']);other=decoded('replayed-all-video',replay_movie['path'])
        audio=decoded('original-all-PCM',movie['path'],True);other_audio=decoded('replayed-all-PCM',replay_movie['path'],True)
        check('all-proof-master-video-and-audio-exact',video==other and len(video)==N*W*H*6 and audio==other_audio==sound.tobytes())
        for src,name in [(Path(movie['path']),'proof-master.mkv'),(Path(movie['manifest']),'proof-master.mkv.manifest.json'),(Path(frame['path']),'actual-frame.png'),(Path(preview['path']),'actual-preview.mp4'),
            (Path(first['output'])/'frame-000000024.png','actual-device-frame.png'),(Path(first['manifest']),'sequence.json')]:shutil.copyfile(src,public/name)
        run('gif',[ffmpeg,'-nostdin','-v','error','-i',public/'actual-preview.mp4','-vf','fps=6,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse','-loop','0',public/'actual-preview.gif'])
        with Image.open(public/'actual-preview.gif') as im:
            count=im.n_frames;duration=0
            for i in range(count):im.seek(i);duration+=im.info['duration']
        check('GIF-clock',count==24 and abs(duration-4000)<=10)
        sheet=Image.new('RGB',(W*2,H+90),'#111927');draw=ImageDraw.Draw(sheet)
        # Left deliberately mathematical source control, not an engine render.
        v=source[24].astype(float)/65535;control=np.where(v<=.0031308,12.92*v,1.055*v**(1/2.4)-.055)
        sheet.paste(Image.fromarray(np.rint(control*255).astype(np.uint8)),(0,0));sheet.paste(Image.open(public/'actual-frame.png').convert('RGB'),(W,0))
        font=ImageFont.load_default(size=16)
        draw.text((18,H+16),'INDEPENDENT SOURCE sRGB CONTROL / no glow or proof',font=font,fill='white')
        draw.text((W+18,H+16),'ACTUAL NATIVE SOFT PROOF / GPU Bloom',font=font,fill='white')
        draw.text((18,H+47),'Original synthetic RGB CLUT; diagnostic only, not calibrated printer/display matching.',font=font,fill='white')
        sheet.save(public/'comparison.png')
        (public/'SOURCE.txt').write_text('C58 / agent editor kit CLI0.1.48\nOriginal contributor-generated RGB16 diagnostic chart, lettering, tones and synthetic bidirectional RGB/XYZ ICC CLUT: CC0-1.0.\nProfile is an explicit numerical diagnostic, not a vendor printer or monitor characterization.\nActual native Windows/OpenCL Bloom, LittleCMS CPU output/softproof, individually embedded RGBA16 PNG delivery and authored Float32 stereo PCM.\nComparison left: independent source-to-sRGB/no-glow mathematical control; right: actual native proof preview.\nNo human continuous playback/listening or physical display/printer/artistic matching acceptance.\n',encoding='utf8')
        files=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()]
        save(public/'media-manifest.json',dict(case='C58',files=files,rights='Original contributor CC0 diagnostics',continuous_human_playback=False,human_listening=False,device_matching_accepted=False))
        report.update(status='passed',checks=checks,project=str(project),restored=str(restored),public_directory=str(public),
            PNG_frames=N,PNG_pixel_bytes=N*W*H*8,PCM_scalar_samples=384000,decoded_video_bytes=len(video),
            maximum_patch_error_codes=max(errors),comparisons=len(errors),GPU_glow_calls_per_sequence=N,files=files,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('files','checks')},ensure_ascii=False),flush=True)
    except BaseException as e:report.update(status='failed',error=repr(e),checks=checks);save(out/'verification.json',report);raise
if __name__=='__main__':main()
