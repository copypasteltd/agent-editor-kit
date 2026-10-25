"""Actual installed transition/audio/preview/queue/resume/editable-package case.

All visual and stereo source samples are self-authored here (CC0). The audio
oracle independently maps the original PCM and continuous child author clock.
"""
import argparse,copy,hashlib,json,shutil,subprocess,sys,time
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.21/final-r2/installed'
BASE=ROOT/'docs/validation/evidence/float-text-coverage-20261026-r1'

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--registered-skill',action='store_true');args=ap.parse_args()
    assert args.run.replace('-','').isalnum()
    out=BASE/('case-'+args.run);out.mkdir(parents=True,exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'workspace'/('float-text-coverage-20261026-case-'+args.run);work.mkdir(parents=True,exist_ok=False)
    public=ROOT/'docs/assets'/('float-text-coverage-20261026-'+args.run);public.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(INSTALL/'site'))
    import numpy as np
    from PIL import Image,ImageDraw
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.media import ffmpeg_path,probe_media
    from ai_ad_editor.project import create_project,save_project
    from ai_ad_editor.rights import add_record,load_ledger,save_ledger
    configure_local_runtime();ffmpeg=ffmpeg_path()
    prefix=[sys.executable,'-I','-S','-B','-u','-X','utf8',str(INSTALL/'run.py')]
    if args.registered_skill:
        entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(entry/'scripts/run.ps1')]
    report=dict(status='running',installed=str(INSTALL),cli_version='0.1.23',calls=[],checks=[],
        virtualization=False,source_fallback=False,continuous_playback=False,human_listening=False,
        natural_quality_accepted=False,registered_skill=args.registered_skill,started_at_utc=datetime.now(timezone.utc).isoformat())
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
        root,p=create_project(work/'编辑 工程','Float32 native text, transitions and reverse child','float_transition_case')
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
        p['sequences'].append(child)
        font_source=INSTALL/'site/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'
        font=root/'assets/noto-sans-sc-variable.ttf';shutil.copyfile(font_source,font)
        p['assets'].append(dict(id='font',kind='font',uri='assets/'+font.name,sha256='sha256:'+sha(font),rights_ref='font',probe={'streams':[]}))
        license_source=INSTALL/'site/ai_ad_editor/material_data/licenses/google-notosanssc.txt'
        (root/'fonts').mkdir(exist_ok=True);font_license=root/'fonts/Noto-Sans-SC-OFL.txt'
        shutil.copyfile(license_source,font_license);shutil.copyfile(license_source,public/'Noto-Sans-SC-OFL.txt')
        add_record(ledger,dict(asset_id='font',verification_status='verified',source_type='community',
            source_url=str(font_source),license_spdx='OFL-1.1',
            evidence='fonts/Noto-Sans-SC-OFL.txt',license_url='fonts/Noto-Sans-SC-OFL.txt',
            permitted_uses=['all'],sha256='sha256:'+sha(font),verified_by='bundled-license-catalog'))
        def title(cid,text,start,duration,**style):
            return dict(id=cid,generator={'type':'text'},timeline_start_tick=start,duration_tick=duration,
                source_in_tick=0,source_out_tick=duration,subtitle={'text':text,'style':dict(
                    font_asset_id='font',fontsize=20,fontcolor='#e8f3ffdd',box=True,boxcolor='#122438a0',
                    boxborderw=5,borderw=1,bordercolor='#08182899',shadowx=2,shadowy=2,
                    shadowcolor='#04081080',x='12',y='22',**style)})
        typing=title('typewriter','AGENT EDITOR KIT',0,3*tps)
        typing['subtitle']['animation']={'type':'typewriter','duration':2.4}
        typing['subtitle']['word_timing']=[dict(text=word,start=i,end=i+1) for i,word in enumerate(['AGENT','EDITOR','KIT'])]
        typing['subtitle']['style']['active_color']='#ffd080dd'
        rotation=title('rotate_title','文字 · 浮点合成',3*tps,3*tps)
        rotation['subtitle']['animation']={'type':'rotate','duration':.8,'from':-18,'to':0}
        rotation['transition_out']={'type':'wipe','direction':'left','duration':.3}
        child['tracks'].append(dict(id='child_titles',kind='subtitle',order=3,clips=[typing,rotation]))
        parent['tracks'][0]['clips'][0]['subtitle']={'text':'linear FLOAT32','style':dict(
            font_asset_id='font',fontsize=14,fontcolor='#a0d8ffbb',box=False,x='12',y='102')}
        srt=root/'assets/captions.srt'
        srt.write_text('1\n00:00:00,000 --> 00:00:02,000\n原生文字与旋转 · 逐词选色\n\n2\n00:00:02,000 --> 00:00:04,000\n父级倒放 · 原工程时间\n\n3\n00:00:04,000 --> 00:00:06,000\nSRT字幕 · 可编辑交付\n',encoding='utf8')
        p['assets'].append(dict(id='srt',kind='subtitle',uri='assets/captions.srt',sha256='sha256:'+sha(srt),rights_ref='srt',probe={'streams':[]}))
        add_record(ledger,dict(asset_id='srt',verification_status='verified',source_type='generated',
            source_url=str(Path(__file__)),license_spdx='CC0-1.0',evidence='Original test captions',
            permitted_uses=['all'],sha256='sha256:'+sha(srt),verified_by='self-authored-fixture-generator'))
        parent['tracks'].append(dict(id='root_captions',kind='subtitle',order=4,clips=[dict(
            id='captions',asset_id='srt',timeline_start_tick=0,duration_tick=6*tps,source_in_tick=0,source_out_tick=6*tps,
            subtitle={'asset_time_base':'sequence','style':dict(font_asset_id='font',fontsize=17,
                fontcolor='#fff0d8dd',box=True,boxcolor='#101828b0',boxborderw=5,x='12',y='150')})]))
        save_ledger(root,ledger);save_project(root,p)
        authored=lambda:{'settings':p['settings'],'assets':p['assets'],'sequences':p['sequences']}
        before=copy.deepcopy(authored());rights_before=sha(root/'rights-ledger.json')
        version=cli('version','version');assert version['data']['cli_version']=='0.1.23'
        capabilities=cli('capabilities','capabilities');save('capabilities.json',capabilities)
        cli('validate','validate','--project',root)
        for frame in (0,11,24,36,48,60,71):
            cli('preview-'+str(frame),'preview','frame','--project',root,'--frame',frame,'--height',180)
        cli('render-dry-run','render','--project',root,'--output',root/'renders/planned.mkv','--dry-run')
        check('dry run did not create movie',not (root/'renders/planned.mkv').exists())
        actual=root/'renders/native-text.mkv';rendered=cli('render','render','--project',root,'--output',actual)
        pipeline=rendered['data']['delivery']['pixel_pipeline']
        check('actual Float32 transport frames',pipeline['transport']['frames']==72)
        text=pipeline['timeline']['text'];save('native-text-receipt.json',text)
        check('actual Float32 native text plans and snapshots',len(text['plans'])==4 and text['native_snapshots']>30,
              snapshots=text['native_snapshots'],cache_hits=text['cache_hits'])
        check('all 256 native coverage codes exact',text['coverage_conversion']['max_code_error']==0)
        check('native text never receives media pixels',text['media_pixels_in_glyph_process'] is False)

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
        # Startup cancellation occurs before a resumable operation exists.
        # Request cancellation only after this owned encoder has created its
        # temporary movie, i.e. inside the protected render execution phase.
        marker=work/'cancel.flag'
        command=list(map(str,[*prefix,'render','--project',root,'--output',root/'renders/resumed.mkv','--cancel-file',marker]))
        start=time.perf_counter();observed=False
        stdout=out/'cancel.stdout.log';stderr=out/'cancel.stderr.log'
        with stdout.open('wb') as sout,stderr.open('wb') as serr:
            process=subprocess.Popen(command,cwd=ROOT,stdout=sout,stderr=serr,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline=time.monotonic()+300
                while process.poll() is None and time.monotonic()<deadline:
                    if list((root/'renders/.tmp').glob('*/resumed.mkv')):
                        marker.write_text('cancel after owned encoder output exists\n',encoding='utf8');observed=True;break
                    time.sleep(.05)
                if not observed:marker.write_text('cancel after unsuccessful readiness wait\n',encoding='utf8')
                code=process.wait(timeout=60)
            finally:
                if process.poll() is None:
                    marker.write_text('cancel owned test render\n',encoding='utf8')
                    try:process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=30)
        report['calls'].append(dict(name='cancel',argv=command,exit_code=code,seconds=time.perf_counter()-start,
            stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),owned_encoder_output_observed=observed))
        save('verification.json',report)
        assert observed and code==8,stdout.read_text(encoding='utf8')
        cancelled=json.loads(stdout.read_bytes());assert cancelled['operation_id'],cancelled
        check('cancel creates no movie',not (root/'renders/resumed.mkv').exists() and not cancelled['ok'])
        marker.unlink();cli('resume','render','--project',root,'--resume',cancelled['operation_id'])
        resumed=decoded('resumed',root/'renders/resumed.mkv');check('resume all frames/clocks/PCM match',resumed[:2]==reference[:2])
        jobs=work/'jobs.json';jobs.write_text(json.dumps(dict(job_id='float-transitions',output='renders/queued.mkv',
            container='mkv',video_codec='libx264',audio_codec='pcm_f32le',pixel_format='yuv444p10le',crf=0,
            hardware_encode='off',hardware_decode='off'))+'\n',encoding='utf8')
        cli('queue-enqueue','queue','enqueue','--project',root,'--input',jobs)
        cli('queue-run','queue','run','--project',root,'--job-id','float-transitions')
        queued=decoded('queued',root/'renders/queued.mkv');check('queue all frames/clocks/PCM match',queued[:2]==reference[:2])
        cli('quality','quality','check','--project',root,'--input',actual)
        saved=json.loads((root/'project.json').read_bytes())
        check('authored settings/assets/sequences and rights unchanged',before=={k:saved[k] for k in before} and sha(root/'rights-ledger.json')==rights_before)
        mp4=public/'native-text.mp4';gif=public/'native-text.gif'
        run('display-mp4',[ffmpeg,'-nostdin','-v','error','-n','-i',actual,'-vf',
            'zscale=pin=709:tin=linear:min=709:rin=limited:p=709:t=709:m=709:r=limited,format=yuv420p',
            '-c:v','libx264','-preset','fast','-crf','18','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
            '-c:a','aac','-b:a','160k','-movflags','+faststart',mp4])
        run('display-gif',[ffmpeg,'-nostdin','-v','error','-n','-i',mp4,'-an','-filter_complex',
            'fps=8,split[a][b];[a]palettegen[p];[b][p]paletteuse',gif])
        run('display-still',[ffmpeg,'-nostdin','-v','error','-n','-ss','2.95','-i',mp4,'-frames:v','1',public/'midpoint.png'])
        run('decode-display',[ffmpeg,'-nostdin','-v','error','-i',mp4,'-f','null','-'])
        with Image.open(gif) as image:gif_frames=image.n_frames
        cli('export-package','convert','export','--project',root,'--target-format','package','--output',public/'editable-native-text.aevpkg.zip')
        (public/'SOURCE.txt').write_text('Self-authored geometric video, captions and synthetic stereo tones: CC0-1.0. Noto Sans SC: OFL-1.1; original font and bundled license remain unchanged.\nGenerator: scripts/run_float_text_coverage_case_20261026.py\nActual installed CLI0.1.23 Float32 native text/typewriter/highlight/rotation/SRT, child reversal, transitions and linked source audio.\nGIF is silent; MP4 audio is synthetic verification tone, not voice/music quality evidence.\n',encoding='utf8',newline='\n')
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
