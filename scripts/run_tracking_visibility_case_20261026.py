"""C41: actual registered mask/slide bindings vs independent authored transforms."""
import argparse,copy,hashlib,json,math,subprocess,sys,time
from bisect import bisect_right
from datetime import datetime,timezone
from fractions import Fraction as F
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-visibility-20261026-r1'
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.29/final-r1/installed'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False)
    work=ROOT/'workspace'/('tracking-visibility-20261026-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/'docs/assets'/('tracking-visibility-20261026-'+a.run);public.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    sys.path.insert(0,str(INSTALL/'site'))
    import numpy as np
    from PIL import Image
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.media import ffmpeg_path,probe_media
    from ai_ad_editor.project import save_project
    from ai_ad_editor.float_standard_render import FloatRenderContext
    from ai_ad_editor.render import output_settings
    configure_local_runtime();ffmpeg=ffmpeg_path()
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')]
    report=dict(status='running',cli_version='0.1.31',installed=str(INSTALL),registered_skill=True,
        source_fallback=False,virtualization=False,new_model_forwards=0,natural_quality_accepted=False,
        continuous_playback=False,human_listening=False,calls=[],checks=[],started_at_utc=datetime.now(timezone.utc).isoformat())
    def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,value,**details):
        report['checks'].append(dict(name=name,ok=bool(value),**details));save('verification.json',report)
        assert value,(name,details)
    def run(name,args,binary=False):
        args=list(map(str,args));start=time.perf_counter()
        r=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout=(work if binary else out)/(name+('.bin' if binary else '.stdout.log'));stdout.write_bytes(r.stdout)
        stderr=out/(name+'.stderr.log');stderr.write_bytes(r.stderr)
        report['calls'].append(dict(name=name,argv=args,exit_code=r.returncode,seconds=time.perf_counter()-start,
            stdout_path=str(stdout),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
        save('verification.json',report);print(json.dumps(dict(name=name,code=r.returncode)),flush=True)
        assert r.returncode==0,(name,r.stdout[-3000:],r.stderr[-2000:]);return r.stdout
    def cli(name,*args):
        v=json.loads(run(name,[*prefix,*args]));assert v['ok'];return v['data']
    def decoded(name,path):
        raw=run(name+'-frames',[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:v:0','-pix_fmt','rgba64le','-f','framemd5','-'])
        rows=[line.split(',') for line in raw.decode().splitlines() if line and not line.startswith('#')]
        pcm=run(name+'-pcm',[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:a:0','-c:a','pcm_f32le','-f','f32le','-'],True)
        check(name+' full clocks and PCM length',len(rows)==36 and len(pcm)==144000*2*4 and [int(r[2]) for r in rows]==list(range(36)))
        return [r[-1].strip() for r in rows],hashlib.sha256(pcm).hexdigest()
    try:
        check('actual registered CLI',cli('version','version')['cli_version']=='0.1.31')
        project=work/'编辑 工程'
        cli('import-source','convert','import','--input',ROOT/'docs/assets/float-tracking-20261026-r5/editable-native-tracking.aevpkg.zip','--output',project)
        p=json.loads((project/'project.json').read_bytes());seq=next(s for s in p['sequences'] if s['id']=='child');p['sequences']=[seq]
        source=seq['tracks'][0]['clips'][0];label=next(c for t in seq['tracks'] for c in t['clips'] if c.get('tracking_binding'))
        for c in (source,label):c.pop('link_id',None)
        source.pop('crop',None);source['keyframes']=[]
        source.update(duration_tick=202500,source_out_tick=202500,transition_out=dict(type='slide',direction='left',duration=.75))
        source['mask']=dict(type='rectangle',x=0,y=0,width=.7,height=1,feather=.08,keyframes=[
            dict(property='width',keyframes=[dict(at_tick=0,value=.7),dict(at_tick=90000,value=.25),dict(at_tick=202500,value=.85)]),
            dict(property='feather',keyframes=[dict(at_tick=0,value=.08),dict(at_tick=202500,value=.08)])])
        peer=copy.deepcopy(source);peer.update(id='incoming_source',timeline_start_tick=135000,duration_tick=135000,source_out_tick=135000)
        for row in source['mask']['keyframes']:
            for key in row['keyframes']:key['interpolation']='linear'
        peer.pop('transition_out');peer.pop('mask');peer['transition_in']=dict(type='slide',direction='left',duration=.75)
        seq['tracks'][0]['clips'].append(peer);seq['tracks'][0]['overlap_policy']='allow'
        label.update(duration_tick=202500,source_out_tick=202500)
        label['tracking_binding'].update(scale_mode='none',rotation_mode='none')
        other=copy.deepcopy(label);other.update(id='incoming_marker',timeline_start_tick=135000,duration_tick=135000,source_out_tick=135000)
        other['tracking_binding']['source_clip_id']='incoming_source'
        label_track=next(t for t in seq['tracks'] if label in t['clips']);label_track['clips'].append(other);label_track['overlap_policy']='allow'
        p['settings']['output']['video']['pixel_format']='yuv444p'
        save_project(project,p);save('initial-author-project.json',p)
        rights=sha(project/'rights-ledger.json');authored=copy.deepcopy(p)
        cli('validate-initial','validate','--project',project)
        plan=cli('render-plan','render','--project',project,'--sequence-id','child','--output',project/'renders/edited.mkv','--dry-run')
        check('visibility protocol in actual render plan','native-transition-point-footprint-v1' in json.dumps(plan))
        before_p=copy.deepcopy(p)
        for c in before_p['sequences'][0]['tracks'][0]['clips']:
            for key in ('mask','transition_in','transition_out'):c.pop(key,None)
        save_project(project,before_p);before=project/'renders/before.mkv'
        cli('render-before','render','--project',project,'--sequence-id','child','--output',before)
        save_project(project,p)
        # Independent oracle: sampled unbound source surfaces, saved native PTS
        # interpolation, explicit integer slide branches, ordinary transform keys.
        yy,xx=np.indices((180,320));keys={c['id']:[] for c in (label,other)};oracles=[];native=[]
        with FloatRenderContext(project,p,seq,output_settings(p['settings'])) as ctx:
            h=ctx.timeline;canvas={'width':320,'height':180}
            for frame in range(36):
                pixels,meta=h.render_frame(frame);native.append(hashlib.sha256(pixels.tobytes()).hexdigest());at=F(frame,12)
                states={r['clip'].split('/')[-1]:r['tracking'] for r in meta['layers'] if r.get('tracking')}
                for source_clip,target in ((source,label),(peer,other)):
                    start=F(source_clip['timeline_start_tick'],90000);end=start+F(source_clip['duration_tick'],90000)
                    if not start<=at<end:continue
                    provider=h.sources[source_clip['asset_id']];_,index=provider.sample(at-start)
                    pts=provider.pts[index-provider.source_frame_start];time_native=pts*provider.time_base-provider.origin
                    obs=target['tracking_binding']['observations'];times=[F(str(r['at_seconds'])) for r in obs]
                    i=bisect_right(times,time_native);lo=max(0,i-1);hi=min(i,len(times)-1)
                    ratio=0 if lo==hi else max(0.,min(1.,float((time_native-times[lo])/(times[hi]-times[lo]))))
                    px=(obs[lo]['x']+(obs[hi]['x']-obs[lo]['x'])*ratio)*320-.5
                    py=(obs[lo]['y']+(obs[hi]['y']-obs[lo]['y'])*ratio)*180-.5
                    raw,_,_,_=h._layer('child',source_clip,at,canvas,[],0,False)
                    field=np.maximum(0,1-np.abs(xx-px))*np.maximum(0,1-np.abs(yy-py))*raw[:,:,3]
                    paired=F(3,2)<=at<F(9,4)
                    if paired:
                        q=(at-F(3,2))/F(3,4);shift=int(-(1-float(q))*320);moving=xx+shift
                        chosen=(moving>=0)&(moving<320)
                        chosen=chosen if target is other else ~chosen
                        field=np.where(chosen,field[yy,moving%320],0.)
                        mass=float(field.sum());cx=float((field*xx).sum()/mass) if mass else px;cy=float((field*yy).sum()/mass) if mass else py
                    else:
                        mass=float(field.sum());cx,cy=px,py
                    want={'position.x':(cx+.5)/320,'position.y':(cy+.5)/180,'opacity':min(1.,mass)}
                    state=states[target['id']];error=max(abs(state['values'][k]-v) for k,v in want.items())
                    oracles.append(dict(frame=frame,target=target['id'],native_frame=index,native_pts=pts,paired=paired,
                        actual=state['values'],expected=want,max_error=error,active=state['active'],reason=state['reason']))
                    keys[target['id']].append((int((at-start)*90000),want))
        save('independent-footprint-oracles.json',oracles)
        check('all native PTS and footprint transforms match independent integer slide oracle',
            all(r['max_error']<1e-12 for r in oracles),rows=len(oracles),max_error=max(r['max_error'] for r in oracles))
        reference=copy.deepcopy(p)
        for t in reference['sequences'][0]['tracks']:
            for c in t['clips']:
                if c['id'] not in keys:continue
                c.pop('tracking_binding');c['keyframes']=[dict(property=k,keyframes=[dict(at_tick=at,value=want[k],interpolation='hold')
                    for at,want in keys[c['id']]]) for k in ('position.x','position.y','opacity')]
        save('independent-unbound-oracle-project.json',reference)
        with FloatRenderContext(project,reference,reference['sequences'][0],output_settings(reference['settings'])) as ctx:
            expected=[hashlib.sha256(ctx.timeline.render_frame(i)[0].tobytes()).hexdigest() for i in range(36)]
        save('native-float-frame-oracles.json',[dict(frame=i,actual=a,expected=b,pixels_equal=a==b) for i,(a,b) in enumerate(zip(native,expected))])
        check('all Float32 frames equal independent unbound authored-transform oracle',native==expected)
        oracle_movie=project/'renders/oracle.mkv';save_project(project,reference)
        cli('render-oracle','render','--project',project,'--sequence-id','child','--output',oracle_movie)
        save_project(project,p);edited=project/'renders/edited.mkv'
        rendered=cli('render-edited','render','--project',project,'--sequence-id','child','--output',edited)
        gpu=rendered['projection_acceleration'];save('gpu-receipt.json',gpu)
        check('actual GPU and owned cleanup',gpu['status']=='verified' and gpu['operations']['affine']>=36 and gpu['worker_closed'] and gpu['shared_handles_closed'])
        original=decoded('before',before);actual=decoded('edited',edited);independent=decoded('oracle',oracle_movie)
        check('all decoded frames match independent unbound render',actual[0]==independent[0])
        check('complete stereo PCM unchanged by masks and transitions',original[1]==actual[1]==independent[1],samples=144000)
        package=public/'editable-tracking-visibility.aevpkg.zip'
        cli('export-package','convert','export','--project',project,'--target-format','package','--output',package)
        restored=work/'重导入 工程';cli('import-edited','convert','import','--input',package,'--output',restored)
        cli('validate-imported','validate','--project',restored)
        restored_movie=restored/'renders/restored.mkv';cli('render-imported','render','--project',restored,'--sequence-id','child','--output',restored_movie)
        restored_data=decoded('restored',restored_movie)
        check('all encoded frames and full PCM preserved by native package',restored_data==actual)
        current=json.loads((project/'project.json').read_bytes())
        check('original observations author graph and rights retained',all(current[k]==authored[k] for k in ('settings','sequences','assets')) and sha(project/'rights-ledger.json')==rights)
        for frame in (0,9,17,18,22,26,27,35):cli('preview-'+str(frame),'preview','frame','--project',project,'--sequence-id','child','--frame',frame,'--height','180')
        cli('quality','quality','check','--project',project,'--input',edited)
        for label,path in [('before',before),('edited',edited)]:
            run(label+'-mp4',[ffmpeg,'-nostdin','-v','error','-n','-i',path,'-vf','zscale=transferin=linear:transfer=iec61966-2-1,format=yuv420p',
                '-c:v','libx264','-crf','17','-c:a','aac','-movflags','+faststart',public/(label+'.mp4')])
        run('gif',[ffmpeg,'-nostdin','-v','error','-n','-i',public/'edited.mp4','-filter_complex',
            '[0:v]fps=8,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',public/'edited.gif'])
        run('midpoint',[ffmpeg,'-nostdin','-v','error','-n','-ss','1.833333','-i',public/'edited.mp4','-frames:v','1',public/'midpoint.png'])
        with Image.open(public/'edited.gif') as image:gif_frames=image.n_frames
        (public/'SOURCE.txt').write_text('C41: self-authored CC0 C36 geometry/marker and synthetic stereo tones; font license retained.\nInput ../float-tracking-20261026-r5/.\nReproduce scripts/run_tracking_visibility_case_20261026.py --run <new-run>.\nActual animated feather mask and dual-source slide with outgoing/incoming labels; independent integer-slide footprint/ordinary transform-key render oracle; complete stereo PCM unchanged. Silent GIF, synthetic-audio MP4. No continuous playback, natural quality or human listening acceptance.\n',encoding='utf8',newline='\n')
        files=[dict(path=f.relative_to(ROOT).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(public.iterdir()) if f.is_file()]
        (public/'media-manifest.json').write_text(json.dumps(dict(files=files,output_frames=36,seconds=3,fps=12,gif_frames=gif_frames,
            before=probe_media(public/'before.mp4'),edited=probe_media(public/'edited.mp4')),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',project=str(project),imported_project=str(restored),public=str(public),edited_frames=36,
            independent_float32_frames_equal=36,independent_binding_rows=len(oracles),max_binding_error=max(r['max_error'] for r in oracles),
            hidden_rows=sum(not r['active'] for r in oracles),full_pcm_samples_per_channel=144000,max_pcm_error=0,
            restored_frames_and_pcm_equal=True,gif_frames=gif_frames,package_sha256=sha(package),finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('calls','checks')},ensure_ascii=False),flush=True)
    except BaseException as exc:report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
