"""Actual installed transition/audio/preview/queue/resume/editable-package case.

All visual and stereo source samples are self-authored here (CC0). The audio
oracle independently maps the original PCM and continuous child author clock.
"""
import argparse,copy,hashlib,json,shutil,subprocess,sys,time
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.19/final-r1/installed'
BASE=ROOT/'docs/validation/evidence/float-transition-20261026-r1'

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args()
    assert args.run.replace('-','').isalnum()
    out=BASE/('case-'+args.run);out.mkdir(parents=True,exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'workspace'/('float-transition-20261026-case-'+args.run);work.mkdir(parents=True,exist_ok=False)
    public=ROOT/'docs/assets'/('float-transition-20261026-'+args.run);public.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(INSTALL/'site'))
    import numpy as np
    from PIL import Image,ImageDraw
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.media import ffmpeg_path,probe_media
    from ai_ad_editor.project import create_project,save_project
    from ai_ad_editor.rights import add_record,load_ledger,save_ledger
    configure_local_runtime();ffmpeg=ffmpeg_path()
    prefix=[sys.executable,'-I','-S','-B','-u','-X','utf8',str(INSTALL/'run.py')]
    report=dict(status='running',installed=str(INSTALL),cli_version='0.1.21',calls=[],checks=[],
        virtualization=False,source_fallback=False,continuous_playback=False,human_listening=False,
        natural_quality_accepted=False,started_at_utc=datetime.now(timezone.utc).isoformat())
    def save(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,ok,**details):
        report['checks'].append(dict(name=name,ok=bool(ok),**details));save('verification.json',report)
        assert ok,name
    def run(name,command,allowed=(0,),timeout=600):
        command=list(map(str,command));start=time.perf_counter()
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout.log')).write_bytes(result.stdout);(out/(name+'.stderr.log')).write_bytes(result.stderr)
        report['calls'].append(dict(name=name,argv=command,exit_code=result.returncode,seconds=time.perf_counter()-start,
            stdout_sha256=sha(out/(name+'.stdout.log')),stderr_sha256=sha(out/(name+'.stderr.log'))))
        save('verification.json',report);print(json.dumps(dict(name=name,code=result.returncode)),flush=True)
        assert result.returncode in allowed,(name,result.stdout[-3000:].decode('utf8','replace'),result.stderr[-3000:].decode('utf8','replace'))
        return result.stdout
    def cli(name,*arguments,allowed=(0,)):
        result=json.loads(run(name,[*prefix,*arguments],allowed=allowed))
        if allowed==(0,):assert result['ok'],result
        return result
    try:
        w,h,fps,count=320,180,12,108;tps=90000
        y,x=np.indices((h,w),dtype=np.float64)
        raw=work/'original.gbrp16';colours=[(.8,.12,.08),(.05,.5,.8),(.08,.65,.2),(.65,.12,.8),(.9,.5,.04),(.1,.7,.7)]
        with raw.open('wb') as stream:
            for i in range(count):
                scene=min(5,i//18);base=np.array(colours[scene])[None,None,:]
                rgb=np.broadcast_to(base,(h,w,3)).copy()*(.5+.4*x[:,:,None]/(w-1))
                rgb+=.08*y[:,:,None]/(h-1)
                cx=40+(i%18)*13;cy=80+int(20*np.sin(i*.3))
                circle=(x-cx)**2+(y-cy)**2<24**2;rgb[circle]=(.95,.92,.8)
                for bit in range(7):rgb[12:24,12+bit*18:24+bit*18]=.95 if (i>>bit)&1 else .03
                rgb[140:148,20:20+35*(scene+1)]=.85
                codes=np.rint(np.clip(rgb,0,1)*65535).astype('<u2')
                stream.write(np.moveaxis(codes[:,:,[1,2,0]],2,0).tobytes())
                if i==0:
                    display=np.where(rgb<=.0031308,rgb*12.92,1.055*np.power(rgb,1/2.4)-.055)
                    Image.fromarray(np.rint(np.clip(display,0,1)*255).astype('uint8')).save(public/'original.png')
        original=public/'original.native.mkv'
        run('generate-original',[ffmpeg,'-nostdin','-v','error','-n','-f','rawvideo','-pixel_format','gbrp16le',
            '-video_size',f'{w}x{h}','-framerate',fps,'-i',raw,'-c:v','ffv1','-level','3','-g','1',original])
        n=np.arange(9*48000,dtype=np.float64);t=n/48000
        frequency=220+110*np.minimum(5,(t/1.5).astype(int))
        samples=np.stack((.12*np.sin(2*np.pi*frequency*t),.1*np.cos(2*np.pi*(frequency+73)*t)),1).astype('<f4')
        audio_raw=work/'original.f32';audio_raw.write_bytes(samples.tobytes());audio=public/'original.audio.wav'
        run('generate-audio',[ffmpeg,'-nostdin','-v','error','-n','-f','f32le','-ar',48000,'-ac',2,'-i',audio_raw,'-c:a','pcm_f32le',audio])
        root,p=create_project(work/'编辑 工程','Float32 real-handle transitions and reverse child','float_transition_case')
        p['settings']['canvas'].update(width=w,height=h,background='#102030')
        p['settings']['timebase']['display_fps']={'num':fps,'den':1}
        p['settings']['color'].update(primaries='bt709',transfer='linear',matrix='bt709',range='limited')
        p['settings']['output']={'container':'mkv','video':{'codec':'libx264','crf':0,'preset':'ultrafast','pixel_format':'yuv444p10le'},'audio':{'codec':'pcm_f32le'}}
        linear={'primaries':'bt709','transfer':'linear'}
        p['settings']['pixel_pipeline']={'engine':'float32-native-v1','working_signal':linear,'output_signal':linear,
            'window_frames':4,'sources':{'picture':{'source_signal':linear,'display_geometry':'square-unrotated'}}}
        ledger=load_ledger(root)
        for aid,kind,path in (('picture','video',original),('sound','audio',audio)):
            owned=root/'assets'/path.name;shutil.copyfile(path,owned)
            p['assets'].append(dict(id=aid,kind=kind,uri=owned.relative_to(root).as_posix(),sha256='sha256:'+sha(owned),
                probe=probe_media(owned),rights_ref=aid))
            add_record(ledger,dict(asset_id=aid,verification_status='verified',source_type='generated',source_url=str(path),
                license_spdx='CC0-1.0',evidence=str(Path(__file__)),permitted_uses=['all'],sha256='sha256:'+sha(owned),
                verified_by='self-authored-fixture-generator'))
        save_ledger(root,ledger)
        parent=p['sequences'][0];parent['duration_tick']=6*tps
        child=copy.deepcopy(parent);child['id']='child';child['name']='Six editable source clips'
        child['canvas']={'width':256,'height':144};child['source_transitions']=[]
        for track in child['tracks']:track['id']='child_'+track['id'];track['clips']=[]
        kinds=['wipe_left','dip_white','slide_up','dissolve','slide_right']
        for i in range(6):
            for track,asset in zip(child['tracks'][:2],('picture','sound')):
                cid=('v' if asset=='picture' else 'a')+str(i)
                track['clips'].append(dict(id=cid,asset_id=asset,timeline_start_tick=i*tps,duration_tick=tps,
                    source_in_tick=22500+135000*i,source_out_tick=112500+135000*i,link_id='shot'+str(i)))
            if i:
                child['source_transitions'].append(dict(id='cut'+str(i),type=kinds[i-1],duration_tick=37500,
                    from_clip_id='v'+str(i-1),to_clip_id='v'+str(i),
                    audio_pairs=[dict(from_clip_id='a'+str(i-1),to_clip_id='a'+str(i))]))
        for track in parent['tracks']:track['clips']=[]
        parent['tracks'][0]['clips']=[dict(id='reverse_child',sequence_id='child',timeline_start_tick=0,duration_tick=6*tps,
            source_in_tick=0,source_out_tick=6*tps,reverse=True,transform={'scale':.92},
            transition_in={'type':'wipe','direction':'right','duration':.25},
            transition_out={'type':'slide','direction':'left','duration':.25})]
        p['sequences'].append(child);save_project(root,p)
        authored=lambda:{'settings':p['settings'],'assets':p['assets'],'sequences':p['sequences']}
        before=copy.deepcopy(authored());rights_before=sha(root/'rights-ledger.json')
        cli('version','version');capabilities=cli('capabilities','capabilities');save('capabilities.json',capabilities)
        cli('validate','validate','--project',root)
        for frame in (0,11,24,36,48,60,71):
            cli('preview-'+str(frame),'preview','frame','--project',root,'--frame',frame,'--height',180)
        cli('render-dry-run','render','--project',root,'--output',root/'renders/planned.mkv','--dry-run')
        check('dry run did not create movie',not (root/'renders/planned.mkv').exists())
        actual=root/'renders/transitions.mkv';rendered=cli('render','render','--project',root,'--output',actual)
        check('actual Float32 transport frames',rendered['data']['delivery']['pixel_pipeline']['transport']['frames']==72)
        def decoded(name,path):
            video=run(name+'-frames',[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:v:0','-pix_fmt','rgba','-f','framemd5','pipe:1'])
            pcm=run(name+'-pcm',[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:a:0','-c:a','pcm_f32le','-f','f32le','pipe:1'])
            rows=[line for line in video.decode().splitlines() if line and not line.startswith('#')]
            check(name+' complete frame/PCM count',len(rows)==72 and len(pcm)==288000*8)
            return hashlib.sha256(video).hexdigest(),hashlib.sha256(pcm).hexdigest(),np.frombuffer(pcm,'<f4').reshape(-1,2)
        reference=decoded('actual',actual)
        # Independent original-source PCM oracle. Reverse source intervals are
        # half-open, gain stays on the continuous child presentation boundary.
        boundary=288000-np.arange(288000);expected=np.zeros((288000,2),np.float64)
        for i in range(6):
            start=i*48000-(8000 if i else 0);end=(i+1)*48000+(12000 if i<5 else 0)
            active=(boundary>start)&(boundary<=end);clock=boundary[active]
            index=12000+72000*i+clock-48000*i-1
            gain=np.ones(len(clock),np.float64)
            if i:gain*=np.clip((clock-(i*48000-8000))/20000,0.,1.)
            if i<5:gain*=1-np.clip((clock-((i+1)*48000-8000))/20000,0.,1.)
            expected[active]+=samples[index].astype(np.float64)*gain[:,None]
        error=float(np.abs(reference[2]-expected).max())
        check('every sample matches original PCM and independent author-clock envelopes',error<=3e-7,max_absolute_error=error,samples_per_channel=288000)
        marker=work/'cancel.flag';marker.write_text('cancel\n',encoding='utf8')
        cancelled=cli('cancel','render','--project',root,'--output',root/'renders/resumed.mkv','--cancel-file',marker,allowed=(8,))
        check('cancel creates no movie',not (root/'renders/resumed.mkv').exists() and not cancelled['ok'])
        marker.unlink();cli('resume','render','--project',root,'--resume',cancelled['operation_id'])
        resumed=decoded('resumed',root/'renders/resumed.mkv');check('resume all frames/clocks/PCM match',resumed[:2]==reference[:2])
        jobs=work/'jobs.json';jobs.write_text(json.dumps(dict(job_id='float-transitions',output='renders/queued.mkv'))+'\n',encoding='utf8')
        cli('queue-enqueue','queue','enqueue','--project',root,'--input',jobs)
        cli('queue-run','queue','run','--project',root,'--job-id','float-transitions')
        queued=decoded('queued',root/'renders/queued.mkv');check('queue all frames/clocks/PCM match',queued[:2]==reference[:2])
        cli('quality','quality','check','--project',root,'--input',actual)
        saved=json.loads((root/'project.json').read_bytes())
        check('authored settings/assets/sequences and rights unchanged',before=={k:saved[k] for k in before} and sha(root/'rights-ledger.json')==rights_before)
        mp4=public/'transitions.mp4';gif=public/'transitions.gif'
        run('display-mp4',[ffmpeg,'-nostdin','-v','error','-n','-i',actual,'-vf',
            'zscale=pin=709:tin=linear:min=709:rin=limited:p=709:t=709:m=709:r=limited,format=yuv420p',
            '-c:v','libx264','-preset','fast','-crf','18','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
            '-c:a','aac','-b:a','160k','-movflags','+faststart',mp4])
        run('display-gif',[ffmpeg,'-nostdin','-v','error','-n','-i',mp4,'-an','-filter_complex',
            'fps=8,split[a][b];[a]palettegen[p];[b][p]paletteuse',gif])
        run('display-still',[ffmpeg,'-nostdin','-v','error','-n','-ss','2.95','-i',mp4,'-frames:v','1',public/'midpoint.png'])
        run('decode-display',[ffmpeg,'-nostdin','-v','error','-i',mp4,'-f','null','-'])
        with Image.open(gif) as image:gif_frames=image.n_frames
        cli('export-package','convert','export','--project',root,'--target-format','package','--output',public/'editable-transitions.aevpkg.zip')
        (public/'SOURCE.txt').write_text('Self-authored geometric video and synthetic stereo tones: CC0-1.0.\nGenerator: scripts/run_float_transition_case_20261026.py\nActual installed CLI0.1.21 Float32 transitions, child reversal and linked source audio.\nGIF is silent; MP4 audio is synthetic verification tone, not voice/music quality evidence.\n',encoding='utf8',newline='\n')
        files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()]
        manifest=dict(files=files,display_mp4=probe_media(mp4),gif_frames=gif_frames,video_frames=72,seconds=6,fps=12)
        (public/'media-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',project=str(root),public_directory=str(public),public_files=files,
            actual_frames=72,seconds=6,display_fps=12,gif_frames=gif_frames,
            decoded_frame_clock_sha256=reference[0],full_pcm_sha256=reference[1],max_pcm_error=error,
            original_authoring_unchanged=True,real_source_handle_pairs=5,paired_audio_tracks=True,
            finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report)
        print(json.dumps({k:report[k] for k in ('status','project','actual_frames','max_pcm_error','gif_frames')}),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
