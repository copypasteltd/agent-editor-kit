"""C59: real registered Skill, independent HDR oracle, GPU proof and full replay."""
from pathlib import Path
from datetime import datetime, timezone
from fractions import Fraction
import argparse, copy, hashlib, json, math, shutil, subprocess, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-hdr-measure-20261028-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
W,H,N,FPS=640,360,48,12


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def load(path):return json.loads(Path(path).read_bytes())


def originals():
    yy,xx=np.mgrid[:H,:W]
    mask=Image.new('L',(W,H));draw=ImageDraw.Draw(mask)
    draw.text((20,42),'AGENT EDITOR KIT / ALL-FRAME HDR LIGHT METER',font=ImageFont.load_default(size=17),fill=255)
    draw.text((20,72),'Early bright frame / explicit nits / MaxRGB differs from CIE Y',font=ImageFont.load_default(size=13),fill=255)
    draw.text((20,306),'Actual SDR viewing copy; HDR master and full metrics linked',font=ImageFont.load_default(size=13),fill=255)
    cover=np.asarray(mask,float)/255
    for index in range(N):
        rgb=np.zeros((H,W,3),float);rgb[36:324]=.025
        for j,color in enumerate([[.6,.08,.03],[.03,.6,.08],[.06,.08,.6],[.4]*3]):
            rgb[112:184,20+150*j:155+150*j]=color
        # Brightest single pixel is early; brightest frame average is later.
        if index==0:rgb[220:242,40:62]=.95
        if 18<=index<24:rgb[194:286,20:620]=.7
        cx=90+460*index/(N-1);light=np.exp(-((xx-cx)**2+(yy-255)**2)/(2*12**2))
        rgb+=light[...,None]*np.array([.3,.16,.06])
        rgb=rgb*(1-cover[...,None])+.25*cover[...,None]
        yield np.rint(np.clip(rgb,0,1)*65535).astype('<u2')


def independent_frame(codes):
    """Original equations/declared source clock, no product colour/meter imports."""
    normalized=codes.astype(np.float32)/np.float32(65535)
    working=(normalized.astype(np.float64)*(1000/203)).astype(np.float32)
    absolute=working.astype(np.float64)*203
    p=(absolute/10000)**(2610/16384)
    encoded=(((3424/4096)+(2413/128)*p)/(1+(2392/128)*p))**(2523/32)
    delivered=encoded.astype(np.float32)
    quantized=np.rint(delivered.astype(np.float64)*65535).astype('<u2')
    q=quantized.astype(np.float64)/65535
    root=q**(32/2523)
    nits=10000*(np.maximum(root-3424/4096,0)/(2413/128-(2392/128)*root))**(16384/2610)
    return quantized,nits


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args();assert args.run.replace('-','').isalnum()
    out=BASE/('case-'+args.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('native-hdr-measure-case-'+args.run);work.mkdir(exist_ok=False)
    public=ROOT/'docs/assets'/('native-hdr-measure-20261029-'+args.run);public.mkdir(exist_ok=False)
    project=work/'project';calls=[];checks=[];ffmpeg=shutil.which('ffmpeg');assert ffmpeg
    def run(name,argv,cli=False):
        argv=list(map(str,argv));start=time.perf_counter();r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=1800,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout=(out if cli else work)/(name+('.stdout.json' if cli else '.bin'));stdout.write_bytes(r.stdout)
        stderr=out/(name+'.stderr.txt');stderr.write_bytes(r.stderr)
        calls.append(dict(id=name,argv=argv,exit_code=r.returncode,seconds=time.perf_counter()-start,stdout_sha256=sha(stdout),stdout_bytes=len(r.stdout),stderr_sha256=sha(stderr)))
        save(out/'calls.json',calls);print(json.dumps(dict(id=name,exit_code=r.returncode)),flush=True)
        assert r.returncode==0,(name,r.stdout[-2500:],r.stderr[-2500:])
        if cli:
            value=json.loads(r.stdout);assert value['ok'] and value['provenance']['cli_version']=='0.1.49';return value['data']
        return r.stdout
    def cli(name,*argv):return run(name,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',SKILL,*argv],True)
    def check(name,condition,**details):
        checks.append(dict(name=name,ok=bool(condition),**details));save(out/'checks.json',checks);assert condition,name
    def decode(name,path,audio=False):
        return run(name,[ffmpeg,'-nostdin','-v','error','-i',path,*(['-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le'] if audio else ['-map','0:v:0','-an','-pix_fmt','yuv444p10le','-fps_mode','passthrough','-f','rawvideo']),'pipe:1'])
    report=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),registered_skill=True,
                native_windows=True,virtualization=False,source_fallback=False,whole_goal_complete=False,
                human_listening=False,continuous_human_playback=False,HDR_monitor_accepted=False)
    try:
        assert cli('version','version')['cli_version']=='0.1.49'
        assert len(cli('capabilities','capabilities')['capabilities'])==88
        source=list(originals());raw=work/'source.gbrp16le'
        raw.write_bytes(b''.join(np.moveaxis(frame[...,[1,2,0]],-1,0).tobytes() for frame in source))
        run('original-source',[ffmpeg,'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrp16le','-video_size',f'{W}x{H}','-framerate',FPS,'-i',raw,'-c:v','ffv1','-level','3','-pix_fmt','gbrp16le',public/'source-linear.mkv'])
        t=np.arange(192000,dtype=float)/48000;sound=np.stack((.1*np.sin(2*np.pi*347*t),.1*np.cos(2*np.pi*523*t)),1).astype('<f4')
        (work/'sound.f32').write_bytes(sound.tobytes())
        run('original-audio',[ffmpeg,'-nostdin','-v','error','-f','f32le','-ar','48000','-ac','2','-i',work/'sound.f32','-c:a','pcm_f32le',public/'source-stereo.wav'])
        cli('init','project','init',project,'--name','C59 all-frame HDR metering')
        for asset,path in [('chart',public/'source-linear.mkv'),('tones',public/'source-stereo.wav')]:
            cli('ingest-'+asset,'media','ingest','--project',project,'--input',path,'--asset-id',asset,'--license-spdx','CC0-1.0',
                '--verification-status','verified','--permitted-use','all','--evidence','Original contributor-generated C59 diagnostic chart and tones; no external footage.')
        p=load(project/'project.json');s=p['settings'];s['canvas'].update(width=W,height=H,background='#000000')
        s['timebase']['display_fps']=dict(num=FPS,den=1);s['color']=dict(primaries='bt2020',transfer='smpte2084',matrix='bt2020nc',range='limited')
        s['output']=dict(container='mkv',video=dict(codec='libx264',preset='ultrafast',crf=0,pixel_format='yuv444p10le'),audio=dict(codec='pcm_f32le'))
        s['pixel_pipeline']=dict(engine='float32-native-v1',working_signal=dict(primaries='bt2020',transfer='linear',reference_white_nits=203),
            output_signal=dict(primaries='bt2020',transfer='pq-st2084',reference_white_nits=203),range_policy='reject',
            preview_mapping=dict(operator='reinhard-luminance',source_peak_nits=1000,target_peak_nits=100,exposure_stops=0,gamut_policy='clip'),
            sources=dict(chart=dict(source_signal=dict(primaries='bt2020',transfer='linear',reference_white_nits=1000),demux_origin=0,display_geometry='square-unrotated')))
        save(project/'project.json',p);ops=[]
        for track,kind,asset in [('picture','video','chart'),('sound','audio','tones')]:
            ops += [dict(op='add_track',track_id=track,kind=kind,order=3 if kind=='video' else 4),
                    dict(op='append_clip',track_id=track,id=track+'-clip',asset_id=asset,timeline_start_tick=0,duration_tick=360000,source_in_tick=0,source_out_tick=360000)]
        save(work/'compose.json',dict(operations=ops));cli('compose','timeline','compose','--project',project,'--input',work/'compose.json')
        p=load(project/'project.json');seq=p['sequences'][0]['id'];cli('validate','validate','--project',project)
        before=(project/'project.json').read_bytes()
        cli('measure-dryrun','surface','measure','--project',project,'--sequence-id',seq,'--dry-run')
        measured=cli('measure','surface','measure','--project',project,'--sequence-id',seq)
        region=cli('measure-active','surface','measure','--project',project,'--sequence-id',seq,'--active-region',0,36,W,288)
        partial=cli('measure-partial','surface','measure','--project',project,'--sequence-id',seq,'--start-frame',12,'--stop-frame',24)
        check('readonly-author',before==(project/'project.json').read_bytes())
        check('all-frame-scope',measured['frames']==N and measured['all_timeline_frames_measured'] and measured['full_canvas_measured'])
        check('partial-active-not-full',not region['full_canvas_measured'] and not partial['all_timeline_frames_measured'])
        payload=hashlib.sha256();peaks={'maxrgb':0.,'cie_y':0.};falls=dict(peaks);peak_frames={};fall_frames={};all_error=[]
        # Independent BT2020/D65 coefficients from primary coordinates, not product matrix code.
        xyz=np.array([[.708/.292,.170/.797,.131/.046],[1.,1.,1.],[(1-.708-.292)/.292,(1-.170-.797)/.797,(1-.131-.046)/.046]])
        scales=np.linalg.solve(xyz,np.array([.3127/.329,1.,(1-.3127-.329)/.329]));weights=scales
        for index,codes in enumerate(source):
            q,nits=independent_frame(codes)
            for c in (1,2,0):payload.update(q[...,c].astype('<u2').tobytes())
            payload.update(np.full((H,W),65535,'<u2').tobytes())
            metrics=dict(maxrgb=np.max(nits,axis=2),cie_y=nits[...,0]*weights[0]+nits[...,1]*weights[1]+nits[...,2]*weights[2])
            for key,values in metrics.items():
                peak,fall=float(np.max(values)),float(np.mean(values,dtype=np.float64))
                if peak>peaks[key]:peaks[key]=peak;peak_frames[key]=index
                if fall>falls[key]:falls[key]=fall;fall_frames[key]=index
        for key in peaks:
            all_error.extend([abs(peaks[key]-measured['peak_pixel'][key]['nits']),abs(falls[key]-measured['maximum_frame_average'][key]['nits'])])
            check('independent-'+key+'-frames',peak_frames[key]==measured['peak_pixel'][key]['frame'] and fall_frames[key]==measured['maximum_frame_average'][key]['frame'])
        check('independent-all-frame-transport',measured['encoder_RGB16_input_sha256']=='sha256:'+payload.hexdigest())
        check('independent-nit-metrics',max(all_error)<1e-8,maximum_error_nits=max(all_error))
        save(out/'independent-oracle.json',dict(status='passed',product_modules_imported=False,frames=N,pixels=N*W*H,
            peak_nits=peaks,frame_average_maximum_nits=falls,peak_frames=peak_frames,average_peak_frames=fall_frames,maximum_error_nits=max(all_error),encoder_RGB16_input_sha256='sha256:'+payload.hexdigest()))
        rendered=cli('render','render','--project',project,'--sequence-id',seq,'--output',project/'renders/hdr-master.mkv')
        check('actual-render-input-match',rendered['delivery']['pixel_pipeline']['transport']['video_input_sha256']==measured['encoder_RGB16_input_sha256'])
        original_video=decode('original-video',rendered['path']);original_audio=decode('original-pcm',rendered['path'],True)
        check('all-master-video-and-audio',len(original_video)==N*W*H*6 and original_audio==sound.tobytes(),video_bytes=len(original_video),PCM_scalar_count=sound.size)
        shutil.copyfile(rendered['path'],public/'hdr-master.mkv');shutil.copyfile(rendered['manifest'],public/'hdr-master.manifest.json')
        preview_before=(project/'project.json').read_bytes()
        frame=cli('frame','preview','frame','--project',project,'--sequence-id',seq,'--frame',0,'--height',360)
        preview=cli('preview','preview','range','--project',project,'--sequence-id',seq,'--start-frame',0,'--end-frame',48,'--height',360)
        check('preview-readonly',preview_before==(project/'project.json').read_bytes())
        # Actual preview result shape is intentionally inspected, not guessed.
        save(out/'preview-paths.json',dict(frame=frame,preview=preview))
        def media_path(value,suffix):
            for candidate in value.values():
                if isinstance(candidate,str) and candidate.lower().endswith(suffix) and Path(candidate).is_file():return Path(candidate)
            for candidate in value.values():
                if isinstance(candidate,dict):
                    try:return media_path(candidate,suffix)
                    except AssertionError:pass
            raise AssertionError(('Missing actual media path',suffix,value))
        shutil.copyfile(media_path(frame,'.png'),public/'actual-frame.png');shutil.copyfile(media_path(preview,'.mp4'),public/'actual-preview.mp4')
        run('gif',[ffmpeg,'-nostdin','-v','error','-i',public/'actual-preview.mp4','-vf','fps=6,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse','-loop','0',public/'actual-preview.gif'])
        converted=cli('package','convert','export','--project',project,'--target-format','package','--output',project/'renders/editable-hdr-measure.aevpkg.zip')
        package=project/'renders/editable-hdr-measure.aevpkg.zip';assert package.is_file();shutil.copyfile(package,public/package.name)
        restored=work/'restored';cli('import','convert','import','--input',package,'--output',restored)
        cli('restore-validate','validate','--project',restored)
        replay=cli('replay-measure','surface','measure','--project',restored,'--sequence-id',seq)
        check('all-replay-metrics',all(replay[k]==measured[k] for k in ('peak_pixel','maximum_frame_average','framed_metrics_sha256','encoder_RGB16_input_sha256','analyzed_duration_seconds')))
        second=cli('replay-render','render','--project',restored,'--sequence-id',seq,'--output',restored/'renders/replay.mkv')
        check('complete-master-replay',decode('replay-video',second['path'])==original_video and decode('replay-pcm',second['path'],True)==original_audio)
        # Separate actual 48-frame visible GPU Bloom + native ICC proof combination.
        gpu_root=work/'gpu-proof';cli('gpu-import','convert','import','--input',ROOT/'docs/assets/native-icc-output-20261028-r3/editable-icc-output.aevpkg.zip','--output',gpu_root)
        gp=load(gpu_root/'project.json');pipe=gp['settings']['pixel_pipeline']
        for key in ('working_signal','output_signal'):pipe[key]['reference_white_nits']=100
        for spec in pipe['sources'].values():spec['source_signal']['reference_white_nits']=100
        save(gpu_root/'project.json',gp);gseq=gp['sequences'][0]['id'];gbefore=(gpu_root/'project.json').read_bytes()
        gm=cli('gpu-measure','surface','measure','--project',gpu_root,'--sequence-id',gseq)
        check('gpu-measure-readonly',gbefore==(gpu_root/'project.json').read_bytes())
        gr=cli('gpu-render','render','--project',gpu_root,'--sequence-id',gseq,'--output',gpu_root/'renders/measure-match.mkv')
        gpu=gm['timeline']['projection_acceleration'];proof=gm['timeline']['ICC_proofing']
        check('actual-GPU-and-native-proof',gpu['operations']['glow']==48 and gpu['worker_closed'] and gpu['control']['threads_closed'] and proof['converted_frames']==48 and proof['native_handles_closed'])
        check('GPU-proof-transport-match',gm['encoder_RGB16_input_sha256']==gr['delivery']['pixel_pipeline']['transport']['video_input_sha256'])
        save(public/'measurement.json',measured);save(public/'active-area-measurement.json',region);save(public/'partial-measurement.json',partial);save(public/'GPU-proof-measurement.json',gm)
        (public/'SOURCE.txt').write_text('Original contributor-generated C59 RGB16 diagnostic chart and stereo347/523Hz tones: CC0-1.0. Source RGB unit white=1000nits, working/output white=203nits; HDR master PQ BT2020. Preview is an explicit Reinhard SDR viewing copy,not HDR monitoring. Separate GPU proof case reuses original CC0 C58 media/profile with explicit100nit units. Automated all-frame/oracle/PCM checks; no human listening/continuous playback/physical monitor acceptance.\n',encoding='utf8')
        with Image.open(public/'actual-preview.gif') as gif:
            gif_frames=gif.n_frames;gif_duration=0
            for i in range(gif_frames):gif.seek(i);gif_duration+=gif.info.get('duration',0)
        check('actual-GIF',gif_frames>=20 and 3800<=gif_duration<=4100,gif_frames=gif_frames,gif_duration_ms=gif_duration)
        save(public/'media-manifest.json',dict(status='passed',rights='Original contributor CC0 diagnostics',width=W,height=H,frames=N,fps=FPS,duration_seconds=4,
            files=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file() and p.name!='media-manifest.json']))
        report.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat(),frames=N,independent_pixels=N*W*H,
            independent_maximum_error_nits=max(all_error),encoded_video_bytes=len(original_video),PCM_scalar_count=sound.size,
            GPU_Bloom_calls=48,native_proof_frames=48,full_movie_replay=True,all_metrics_replayed=True,
            calls=len(calls),checks=len(checks),public=str(public),work=str(work))
    except BaseException as caught:
        report.update(status='failed',failure=repr(caught));raise
    finally:save(out/'verification.json',report)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
