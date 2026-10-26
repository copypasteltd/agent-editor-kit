"""Actual installed transition/audio/preview/queue/resume/editable-package case.

All visual and stereo source samples are self-authored here (CC0). The audio
oracle independently maps the original PCM and continuous child author clock.
"""
import argparse,copy,hashlib,json,shutil,subprocess,sys,time
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.24/final-r2/installed'
BASE=ROOT/'docs/validation/evidence/float-tracking-20261026-r1'

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--registered-skill',action='store_true');args=ap.parse_args()
    assert args.run.replace('-','').isalnum()
    out=BASE/('case-'+args.run);out.mkdir(parents=True,exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'workspace'/('float-tracking-20261026-case-'+args.run);work.mkdir(parents=True,exist_ok=False)
    public=ROOT/'docs/assets'/('float-tracking-20261026-'+args.run);public.mkdir(parents=True,exist_ok=False)
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
    report=dict(status='running',installed=str(INSTALL),cli_version='0.1.26',calls=[],checks=[],
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
        w,h,fps,count=320,180,12,36;tps=90000
        y,x=np.indices((h,w),dtype=np.float64);positions=[]
        raw=work/'original.gbrp16'
        with raw.open('wb') as stream:
            for i in range(count):
                left=40+4*i;top=64+4*(i%8 if i%16<8 else 15-i%16);positions.append((left+10,top+10))
                rgb=np.zeros((h,w,3),np.float64);rgb[:]=(.025,.045,.075)
                rgb+=.035*x[:,:,None]/w+.015*y[:,:,None]/h
                target=rgb[top:top+20,left:left+20];target[:]=(.04,.68,.08)
                target[3:7,3:7]=(.88,.94,.82);target[12:17,12:17]=(.02,.2,.04)
                for bit in range(6):rgb[150:156,16+bit*12:22+bit*12]=.65 if (i>>bit)&1 else .02
                codes=np.rint(rgb*65535).astype('<u2');stream.write(np.moveaxis(codes[:,:,[1,2,0]],2,0).tobytes())
                if i==0:
                    display=np.where(rgb<=.0031308,rgb*12.92,1.055*np.power(rgb,1/2.4)-.055)
                    Image.fromarray(np.rint(np.clip(display,0,1)*255).astype('uint8')).save(public/'original.png')
        original=public/'original.native.mkv'
        run('generate-original',[ffmpeg,'-nostdin','-v','error','-n','-f','rawvideo','-pixel_format','gbrp16le',
            '-video_size',f'{w}x{h}','-framerate',fps,'-i',raw,'-c:v','ffv1','-level','3','-g','1',original])
        marker_image=Image.new('RGBA',(20,20));draw=ImageDraw.Draw(marker_image)
        draw.rectangle((0,0,19,19),outline=(255,32,16,255),width=2)
        draw.line((10,0,10,4),fill=(255,32,16,255),width=2)
        marker_path=public/'tracking-marker.png';marker_image.save(marker_path)
        n=np.arange(3*48000,dtype=np.float64);t=n/48000
        samples=np.stack((.12*np.sin(2*np.pi*347*t),.1*np.cos(2*np.pi*619*t)),1).astype('<f4')
        audio_raw=work/'original.f32';audio_raw.write_bytes(samples.tobytes());audio=public/'original.audio.wav'
        run('generate-audio',[ffmpeg,'-nostdin','-v','error','-n','-f','f32le','-ar',48000,'-ac',2,'-i',audio_raw,'-c:a','pcm_f32le',audio])
        root,p=create_project(work/'编辑 工程','Native PTS tracking, crop/TRS and reversed overlay child sound','float_tracking_case')
        p['settings']['projection_acceleration']={'mode':'require','device':'0.0','max_working_bytes':1024**3}
        p['settings']['canvas'].update(width=w,height=h,background='#102030')
        p['settings']['timebase']['display_fps']={'num':fps,'den':1}
        p['settings']['color'].update(primaries='bt709',transfer='linear',matrix='bt709',range='limited')
        p['settings']['output']={'container':'mkv','video':{'codec':'libx264','crf':0,'preset':'ultrafast','pixel_format':'yuv444p10le'},'audio':{'codec':'pcm_f32le'}}
        linear={'primaries':'bt709','transfer':'linear'}
        p['settings']['pixel_pipeline']={'engine':'float32-native-v1','working_signal':linear,'output_signal':linear,
            'window_frames':4,'sources':{key:{'source_signal':linear,'display_geometry':'square-unrotated'} for key in ('picture','marker')}}
        ledger=load_ledger(root)
        for aid,kind,path in (('picture','video',original),('marker','image',marker_path),('sound','audio',audio)):
            owned=root/'assets'/path.name;shutil.copyfile(path,owned)
            p['assets'].append(dict(id=aid,kind=kind,uri=owned.relative_to(root).as_posix(),sha256='sha256:'+sha(owned),probe=probe_media(owned),rights_ref=aid))
            add_record(ledger,dict(asset_id=aid,verification_status='verified',source_type='generated',source_url=str(path),
                license_spdx='CC0-1.0',evidence=str(Path(__file__)),permitted_uses=['all'],sha256='sha256:'+sha(owned),verified_by='self-authored-fixture-generator'))
        parent=p['sequences'][0];parent['duration_tick']=3*tps
        child=copy.deepcopy(parent);child['id']='child';child['name']='Editable source and following marker';child['canvas']={'width':w,'height':h}
        for track in child['tracks']:track['id']='child_'+track['id'];track['clips']=[]
        source=dict(id='moving_source',asset_id='picture',timeline_start_tick=0,duration_tick=3*tps,source_in_tick=0,source_out_tick=3*tps,
            crop=dict(unit='pixels',x=16,y=8,width=288,height=164,fit='stretch',keyframes=[dict(property='x',keyframes=[
                dict(at_tick=0,value=16,interpolation='linear'),dict(at_tick=135000,value=28,interpolation='linear'),dict(at_tick=270000,value=16,interpolation='linear')])]),
            keyframes=[dict(property='transform.scale',keyframes=[dict(at_tick=0,value=.9),dict(at_tick=135000,value=1.,interpolation='linear'),dict(at_tick=270000,value=.9)]),
                dict(property='transform.rotation',keyframes=[dict(at_tick=0,value=-8,interpolation='linear'),dict(at_tick=270000,value=8,interpolation='linear')])])
        child['tracks'][0]['clips']=[source]
        child['tracks'][1]['clips']=[dict(id='child_sound',asset_id='sound',timeline_start_tick=0,duration_tick=3*tps,source_in_tick=0,source_out_tick=3*tps)]
        child['tracks'].append(dict(id='child_labels',kind='overlay',order=2,clips=[dict(id='follow_marker',asset_id='marker',timeline_start_tick=0,
            duration_tick=3*tps,source_in_tick=0,source_out_tick=3*tps,transform={'scale':.17})]))
        for track in parent['tracks']:track['clips']=[]
        parent['tracks'].append(dict(id='overlay_group',kind='overlay',order=2,clips=[dict(id='reverse_child',sequence_id='child',
            timeline_start_tick=0,duration_tick=3*tps,source_in_tick=0,source_out_tick=3*tps,reverse=True)]))
        p['sequences'].append(child)
        font_source=INSTALL/'site/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'
        font=root/'assets/noto-sans-sc-variable.ttf';shutil.copyfile(font_source,font)
        p['assets'].append(dict(id='font',kind='font',uri='assets/'+font.name,sha256='sha256:'+sha(font),rights_ref='font',probe={'streams':[]}))
        license_source=INSTALL/'site/ai_ad_editor/material_data/licenses/google-notosanssc.txt'
        (root/'fonts').mkdir(exist_ok=True);font_license=root/'fonts/Noto-Sans-SC-OFL.txt';shutil.copyfile(license_source,font_license)
        shutil.copyfile(license_source,public/'Noto-Sans-SC-OFL.txt')
        add_record(ledger,dict(asset_id='font',verification_status='verified',source_type='community',source_url=str(font_source),license_spdx='OFL-1.1',
            evidence='fonts/Noto-Sans-SC-OFL.txt',license_url='fonts/Noto-Sans-SC-OFL.txt',permitted_uses=['all'],sha256='sha256:'+sha(font),verified_by='bundled-license-catalog'))
        parent['tracks'].append(dict(id='root_titles',kind='subtitle',order=3,clips=[dict(id='title',generator={'type':'text'},
            timeline_start_tick=0,duration_tick=3*tps,source_in_tick=0,source_out_tick=3*tps,
            subtitle=dict(text='原生 PTS 跟踪 · 可编辑绑定',style=dict(font_asset_id='font',fontsize=16,fontcolor='#f8e8d8',
                box=True,boxcolor='#102030b0',boxborderw=4,x='12',y='14')))]))
        save_ledger(root,ledger);save_project(root,p)
        version=cli('version','version');assert version['data']['cli_version']=='0.1.26'
        capabilities=cli('capabilities','capabilities');save('capabilities.json',capabilities)
        bind=cli('track-bind','media','track-bind','--project',root,'--asset-id','picture','--sequence-id','child',
            '--source-track-id',child['tracks'][0]['id'],'--source-clip-id','moving_source','--target-track-id','child_labels','--target-clip-id','follow_marker',
            '--roi','0.125,0.35555555555555557,0.0625,0.1111111111111111','--step-frames',1,'--search-radius',16,'--max-width',320,'--max-samples',100,
            '--scale-mode','roi','--rotation-mode','source','--apply')
        plan=bind['data']['plan'];save('binding-plan.json',plan)
        check('actual local template analysis and declarative native binding',plan['engine']=='local-template-matching' and
            plan['sampled_frames']==0 and plan['keyframes']==[] and len(plan['tracking_binding']['observations'])==36)
        p=json.loads((root/'project.json').read_bytes());parent=p['sequences'][0]
        authored=lambda:{'settings':p['settings'],'assets':p['assets'],'sequences':p['sequences']}
        before=copy.deepcopy(authored());rights_before=sha(root/'rights-ledger.json')
        cli('validate','validate','--project',root)
        for frame in (0,11,18,24,35):cli('preview-'+str(frame),'preview','frame','--project',root,'--frame',frame,'--height',180)
        cli('render-dry-run','render','--project',root,'--output',root/'renders/planned.mkv','--dry-run')
        check('dry run did not create movie',not (root/'renders/planned.mkv').exists())
        actual=root/'renders/native-tracking.mkv';rendered=cli('render','render','--project',root,'--output',actual)
        pipeline=rendered['data']['delivery']['pixel_pipeline'];save('native-pipeline.json',pipeline)
        gpu=rendered['data']['projection_acceleration'];save('gpu-receipt.json',gpu)
        tracking=pipeline['timeline']['tracking'];save('tracking-receipt.json',tracking)
        check('native binding used on every selected output frame',tracking['bindings']==1 and tracking['evaluations']==36 and not tracking['display_keyframes_baked'])
        check('actual scoped GPU render and owned cleanup',gpu['status']=='verified' and gpu['worker_closed'] and gpu['shared_handles_closed'])
        check('actual GPU marker text and compositing',all(gpu['operations'].get(k,0)>0 for k in ('affine','over','paint')))
        check('actual Float32 transport frames',pipeline['transport']['frames']==36)
        from ai_ad_editor.float_standard_render import FloatRenderContext
        from ai_ad_editor.render import output_settings
        rows=[];max_error=0.;centroid_error=0.
        with FloatRenderContext(root,p,parent,output_settings(p['settings'])) as context:
            for i in range(36):
                pixels,metadata=context.timeline.render_frame(i)
                bound=next(row for row in metadata['layers'] if row['clip']=='child/follow_marker')['tracking']
                visual=next(row for row in metadata['layers'] if row['clip']=='child/moving_source')
                check_index=35-i;assert bound['native_frame_index']==visual['native_frame_index']==check_index
                q=(36-i)/36;triangle=2*min(q,1-q);cropx=round(16+12*triangle);scale=.9+.1*triangle;angle=np.deg2rad(-8+16*q)
                cx,cy=positions[check_index];dx=((cx-cropx)*320/288-160)*scale;dy=((cy-8)*180/164-90)*scale
                want=np.array([160+dx*np.cos(angle)-dy*np.sin(angle),90+dx*np.sin(angle)+dy*np.cos(angle)])
                observed=np.array([bound['values']['position.x']*w,bound['values']['position.y']*h])
                error=float(np.max(np.abs(want-observed)));max_error=max(max_error,error)
                assert error<.05,(i,want,observed,error)
                assert abs(bound['values']['scale']-.17*scale/.9)<1e-9
                assert abs(bound['values']['rotation']-16*q)<1e-9
                red=(pixels[:,:,0]>.5)&(pixels[:,:,1]<.12)&(pixels[:,:,2]<.12)
                yy,xx=np.nonzero(red);assert len(xx)>20
                centre=np.array([xx.mean()+.5,yy.mean()+.5]);pixel_error=float(np.max(np.abs(centre-observed)))
                centroid_error=max(centroid_error,pixel_error);assert pixel_error<1.,(i,pixel_error)
                rows.append(dict(frame=i,source_index=check_index,actual_source_index=visual['native_frame_index'],
                    tracking=bound,independent_expected_edge_position=want.tolist(),max_anchor_error_pixels=error,red_marker_centroid_error_pixels=pixel_error))
        save('independent-frame-oracles.json',rows)
        check('all native source indices geometry and actual marker centroids',len(rows)==36,max_anchor_error_pixels=max_error,max_red_marker_centroid_error_pixels=centroid_error)
        def decoded(name,path):
            video=run(name+'-frames',[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:v:0','-pix_fmt','rgba','-f','framemd5','pipe:1'])
            pcm=run(name+'-pcm',[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:a:0','-c:a','pcm_f32le','-f','f32le','pipe:1'])
            rows=[line for line in video.decode().splitlines() if line and not line.startswith('#')]
            check(name+' complete frame/PCM count',len(rows)==36 and len(pcm)==144000*8)
            return hashlib.sha256(video).hexdigest(),hashlib.sha256(pcm).hexdigest(),np.frombuffer(pcm,'<f4').reshape(-1,2)
        reference=decoded('actual',actual)
        error=float(np.abs(reference[2]-samples[::-1]).max())
        check('all original stereo samples reverse through nested overlay container',error<=3e-8,max_absolute_error=error,samples_per_channel=144000)
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
        jobs=work/'jobs.json';jobs.write_text(json.dumps(dict(job_id='float-tracking',output='renders/queued.mkv',
            container='mkv',video_codec='libx264',audio_codec='pcm_f32le',pixel_format='yuv444p10le',crf=0,
            hardware_encode='off',hardware_decode='off'))+'\n',encoding='utf8')
        cli('queue-enqueue','queue','enqueue','--project',root,'--input',jobs)
        cli('queue-run','queue','run','--project',root,'--job-id','float-tracking')
        queued=decoded('queued',root/'renders/queued.mkv');check('queue all frames/clocks/PCM match',queued[:2]==reference[:2])
        cli('quality','quality','check','--project',root,'--input',actual)
        saved=json.loads((root/'project.json').read_bytes())
        check('authored settings/assets/sequences and rights unchanged',before=={k:saved[k] for k in before} and sha(root/'rights-ledger.json')==rights_before)
        mp4=public/'native-tracking.mp4';gif=public/'native-tracking.gif'
        run('display-mp4',[ffmpeg,'-nostdin','-v','error','-n','-i',actual,'-vf',
            'zscale=pin=709:tin=linear:min=709:rin=limited:p=709:t=709:m=709:r=limited,format=yuv420p',
            '-c:v','libx264','-preset','fast','-crf','18','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
            '-c:a','aac','-b:a','160k','-movflags','+faststart',mp4])
        run('display-gif',[ffmpeg,'-nostdin','-v','error','-n','-i',mp4,'-an','-filter_complex',
            'fps=8,split[a][b];[a]palettegen[p];[b][p]paletteuse',gif])
        run('display-still',[ffmpeg,'-nostdin','-v','error','-n','-ss','2.95','-i',mp4,'-frames:v','1',public/'midpoint.png'])
        run('decode-display',[ffmpeg,'-nostdin','-v','error','-i',mp4,'-f','null','-'])
        with Image.open(gif) as image:gif_frames=image.n_frames
        cli('export-package','convert','export','--project',root,'--target-format','package','--output',public/'editable-native-tracking.aevpkg.zip')
        (public/'SOURCE.txt').write_text('Self-authored geometric moving object, transparent marker and synthetic stereo tones: CC0-1.0. Noto Sans SC: OFL-1.1; original font/license retained.\nGenerator: scripts/run_float_tracking_case_20261026.py\nActual registered Skill CLI0.1.26: local template analysis, saved original-source observations, native PTS dynamic binding, animated crop/scale/rotation, GPU marker/text composition, reversed overlay child with intact stereo audio. Coordinate evaluation and crop execute on CPU.\nGIF is silent; MP4 has synthetic verification tones. This controlled fixture does not establish natural identity/occlusion tracking quality.\n',encoding='utf8',newline='\n')
        files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()]
        manifest=dict(files=files,display_mp4=probe_media(mp4),gif_frames=gif_frames,video_frames=36,seconds=3,fps=12)
        (public/'media-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',project=str(root),public_directory=str(public),public_files=files,
            actual_frames=36,seconds=3,display_fps=12,gif_frames=gif_frames,
            decoded_frame_clock_sha256=reference[0],full_pcm_sha256=reference[1],max_pcm_error=error,
            tracking_bindings=1,tracking_observations=36,max_anchor_error_pixels=max_error,max_red_marker_centroid_error_pixels=centroid_error,
            binding_observations_sha256=hashlib.sha256(json.dumps(plan['tracking_binding'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            original_authoring_unchanged=True,nested_overlay_audio=True,
            finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report)
        print(json.dumps({k:report[k] for k in ('status','project','actual_frames','max_pcm_error','gif_frames')}),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
