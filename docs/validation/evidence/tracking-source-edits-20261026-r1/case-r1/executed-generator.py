"""C38: registered native source slip/extension, independent pixels and full PCM."""
import argparse,copy,hashlib,json,subprocess,sys,time
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-source-edits-20261026-r1'
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.26/final-r1/installed'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False)
    work=ROOT/'workspace'/('tracking-source-edits-20261026-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/'docs/assets'/('tracking-source-edits-20261026-'+a.run);public.mkdir(exist_ok=False)
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
    entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',entry/'scripts/run.ps1']
    report=dict(status='running',cli_version='0.1.28',installed=str(INSTALL),registered_skill=True,
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
        assert r.returncode==0,(name,r.stdout[-2500:],r.stderr[-1500:]);return r.stdout
    def cli(name,*args):
        v=json.loads(run(name,[*prefix,*args]));assert v['ok'];return v['data']
    def decoded(name,path):
        raw=run(name+'-frames',[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:v:0','-pix_fmt','rgba64le','-f','framemd5','-'])
        rows=[line.split(',') for line in raw.decode().splitlines() if line and not line.startswith('#')]
        pcm=run(name+'-pcm',[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:a:0','-c:a','pcm_f32le','-f','f32le','-'],True)
        samples=np.frombuffer(pcm,'<f4').reshape(-1,2)
        check(name+' all decoded clocks and samples',len(rows)==36 and len(samples)==144000 and [int(r[2]) for r in rows]==list(range(36)))
        return [r[-1].strip() for r in rows],samples,hashlib.sha256(pcm).hexdigest()
    try:
        check('actual registered CLI',cli('version','version')['cli_version']=='0.1.28')
        project=work/'编辑 工程'
        cli('import-source','convert','import','--input',ROOT/'docs/assets/float-tracking-20261026-r5/editable-native-tracking.aevpkg.zip','--output',project)
        p=json.loads((project/'project.json').read_bytes());seq=next(s for s in p['sequences'] if s['id']=='child');p['sequences']=[seq]
        p['settings']['output']['video']['pixel_format']='yuv444p'
        byid={c['id']:c for t in seq['tracks'] for c in t['clips']};source=byid['moving_source'];audio=byid['child_sound'];marker=byid['follow_marker']
        # Independently author a finite interior source range and its linked
        # audio. Remove C36 camera processing to make a direct pixel oracle.
        for clip in (source,audio):
            for key in ('crop','keyframes','transform','effects','presentation_window','freeze','speed_curve','audio'):clip.pop(key,None)
            clip.update(timeline_start_tick=45000,duration_tick=180000,source_in_tick=45000,source_out_tick=225000,link_id='source_sound')
        marker['tracking_binding'].update(scale_mode='none',rotation_mode='none')
        marker['tracking_binding']['base'].update(opacity=1,opacity_keyframes=[],rotation=0)
        save_project(project,p);save('initial-author-project.json',p)
        rights=sha(project/'rights-ledger.json');original=copy.deepcopy(marker['tracking_binding']['observations'])
        cli('validate-initial','validate','--project',project)
        before=project/'renders/before.mkv';cli('render-before','render','--project',project,'--sequence-id','child','--output',before)
        operations=[dict(action='slip',clip_id='moving_source',delta_source_tick=22500),
            dict(action='extend_source',clip_id='moving_source',head_tick=22500,tail_tick=22500)]
        for number,operation in enumerate(operations):
            request=work/('request-'+str(number)+'.json');request.write_text(json.dumps(operation),encoding='utf8')
            frozen=sha(project/'project.json')
            plan=cli('edit-plan-'+str(number),'timeline','edit','--project',project,'--sequence-id','child','--input',request,'--dry-run')
            check('dry-run preserves author '+str(number),sha(project/'project.json')==frozen)
            check('source and audio selected '+str(number),set(plan['plan']['selected_clip_ids'])=={'moving_source','child_sound'})
            cli('edit-apply-'+str(number),'timeline','edit','--project',project,'--sequence-id','child','--input',request,
                '--expected-project-sha256',plan['plan']['base_project_sha256'])
        cli('validate-edited','validate','--project',project)
        changed=json.loads((project/'project.json').read_bytes());save('edited-author-project.json',changed)
        rows={c['id']:c for t in changed['sequences'][0]['tracks'] for c in t['clips']};binding=rows['follow_marker']['tracking_binding']
        check('original observations and fragment clock preserved',binding['observations']==original and binding['reference_output_tick']==0 and
            binding['source_fragments']==[dict(track_id=seq['tracks'][0]['id'],clip_id='moving_source',author_offset_tick=22500)])
        check('rights unchanged',sha(project/'rights-ledger.json')==rights)
        for cid in ('moving_source','child_sound'):
            check(cid+' exact independently specified physical range',
                [rows[cid][k] for k in ('timeline_start_tick','duration_tick','source_in_tick','source_out_tick')]==[22500,225000,45000,270000])
        # Independent unbound project: explicit physical ranges and per-frame
        # held positions derived from the saved source observations. No edit
        # planner, binding evaluator or source-window inference creates it.
        oracle=copy.deepcopy(p);oracle_rows={c['id']:c for t in oracle['sequences'][0]['tracks'] for c in t['clips']}
        for cid in ('moving_source','child_sound'):
            oracle_rows[cid].update(timeline_start_tick=22500,duration_tick=225000,source_in_tick=45000,source_out_tick=270000)
        target=oracle_rows['follow_marker'];target.pop('tracking_binding');base=marker['tracking_binding']['base'];target['transform']={'scale':base['scale'],'opacity':1,'rotation':0}
        points={'transform.position.x':[],'transform.position.y':[],'transform.opacity':[]}
        expected_indices=[]
        for frame in range(36):
            active=3<=frame<33;idx=frame+3 if active else None;expected_indices.append(idx)
            if active:
                at=Fraction(idx,12);left=original[0];right=original[-1]
                for first,last in zip(original,original[1:]):
                    if Fraction(str(first['at_seconds']))<=at<=Fraction(str(last['at_seconds'])):left,right=first,last;break
                q=max(0,min(1,float((at-Fraction(str(left['at_seconds'])))/(Fraction(str(right['at_seconds']))-Fraction(str(left['at_seconds'])))))) if left is not right else 0
                xy={k:left[k]+(right[k]-left[k])*q for k in ('x','y')}
            else:xy={'x':.5,'y':.5}
            for prop,value in [('transform.position.x',(xy['x']*320-.5+.5)/320),
                ('transform.position.y',(xy['y']*180-.5+.5)/180),('transform.opacity',int(active))]:
                points[prop].append(dict(at_tick=frame*7500,value=value,interpolation='hold'))
        target['keyframes']=[dict(property=prop,keyframes=keys) for prop,keys in points.items()]
        save('independent-unbound-oracle.json',oracle);expected=[];actual=[];clocks=[]
        for author,destination in ((oracle,expected),(changed,actual)):
            with FloatRenderContext(project,author,author['sequences'][0],output_settings(author['settings'])) as ctx:
                for frame in range(36):
                    pixels,meta=ctx.host.render_frame(frame);destination.append(hashlib.sha256(pixels.tobytes()).hexdigest())
                    if author is changed:
                        row=next((r for r in meta['layers'] if r.get('tracking')),None)
                        index=row['tracking'].get('native_frame_index') if row else None
                        active=bool(row and row['tracking']['active'])
                        clocks.append(dict(frame=frame,expected_native_frame=expected_indices[frame],native_frame=index,active=active))
        save('native-float-oracles.json',[dict(frame=i,actual=a,independent_unbound=e,pixels_equal=a==e,**{k:v for k,v in clocks[i].items() if k!='frame'}) for i,(a,e) in enumerate(zip(actual,expected))])
        check('all Float32 pixels equal independent unbound authoring',actual==expected)
        check('all original native frame indices',all((r['native_frame']==r['expected_native_frame'] if r['expected_native_frame'] is not None else not r['active']) for r in clocks))
        edited=project/'renders/edited.mkv';rendered=cli('render-edited','render','--project',project,'--sequence-id','child','--output',edited)
        gpu=rendered['projection_acceleration'];save('gpu-receipt.json',gpu)
        check('actual GPU and owned cleanup',gpu['status']=='verified' and gpu['operations']['affine']>=30 and gpu['worker_closed'] and gpu['shared_handles_closed'])
        encoded=decoded('edited',edited)
        asset=next(a for a in changed['assets'] if a['id']=='sound')
        from ai_ad_editor.policy import resolve_local_path
        sound=resolve_local_path(project,asset['uri'],field='case.audio')
        pcm=run('original-source-pcm',[ffmpeg,'-nostdin','-v','error','-i',sound,'-map','0:a:0','-c:a','pcm_f32le','-f','f32le','-'],True)
        source_samples=np.frombuffer(pcm,'<f4').reshape(-1,2);expected_pcm=np.zeros((144000,2),np.float32);expected_pcm[12000:132000]=source_samples[24000:144000]
        error=float(np.max(np.abs(encoded[1]-expected_pcm)));check('complete independent stereo PCM',np.array_equal(encoded[1],expected_pcm),max_absolute_error=error,samples=144000)
        package=public/'editable-tracking-source-edits.aevpkg.zip';cli('export-package','convert','export','--project',project,'--target-format','package','--output',package)
        restored=work/'重导入 工程';cli('import-edited','convert','import','--input',package,'--output',restored)
        cli('validate-imported','validate','--project',restored)
        r=json.loads((restored/'project.json').read_bytes());check('binding survives package',next(c['tracking_binding'] for t in r['sequences'][0]['tracks'] for c in t['clips'] if c.get('tracking_binding'))==binding)
        restored_movie=restored/'renders/restored.mkv';cli('render-imported','render','--project',restored,'--sequence-id','child','--output',restored_movie)
        redone=decoded('restored',restored_movie);check('all encoded frames and full PCM preserved',redone[0]==encoded[0] and redone[2]==encoded[2])
        for frame in (2,3,18,32,33):cli('preview-'+str(frame),'preview','frame','--project',project,'--sequence-id','child','--frame',frame,'--height','180')
        cli('quality','quality','check','--project',project,'--input',edited)
        for label,path in [('before',before),('edited',edited)]:
            run(label+'-mp4',[ffmpeg,'-nostdin','-v','error','-n','-i',path,'-vf','zscale=transferin=linear:transfer=iec61966-2-1,format=yuv420p',
                '-c:v','libx264','-crf','17','-c:a','aac','-movflags','+faststart',public/(label+'.mp4')])
        run('gif',[ffmpeg,'-nostdin','-v','error','-n','-i',public/'edited.mp4','-filter_complex',
            '[0:v]fps=8,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',public/'edited.gif'])
        run('midpoint',[ffmpeg,'-nostdin','-v','error','-n','-ss','1.5','-i',public/'edited.mp4','-frames:v','1',public/'midpoint.png'])
        with Image.open(public/'edited.gif') as image:gif_frames=image.n_frames
        (public/'SOURCE.txt').write_text('C38 uses self-authored CC0 C36 moving geometry, transparent marker and synthetic stereo tones. Original font license retained in package.\nInput: ../float-tracking-20261026-r5/\nReproduce: scripts/run_tracking_source_edits_case_20261026.py --run <new-run>\nSilent GIF; MP4 synthetic tones. Static inspection, no continuous playback or human listening/natural quality acceptance.\n',encoding='utf8',newline='\n')
        files=[dict(path=f.relative_to(ROOT).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(public.iterdir()) if f.is_file()]
        save('public-media.json',files)
        (public/'media-manifest.json').write_text(json.dumps(dict(files=files,output_frames=36,seconds=3,fps=12,gif_frames=gif_frames,
            before=probe_media(public/'before.mp4'),edited=probe_media(public/'edited.mp4')),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',project=str(project),imported_project=str(restored),public=str(public),edited_frames=36,
            independent_float32_frames_equal=36,actual_bound_frames=30,full_pcm_samples_per_channel=144000,max_pcm_error=error,
            restored_frames_and_pcm_equal=True,gif_frames=gif_frames,package_sha256=sha(package),finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('calls','checks')},ensure_ascii=False),flush=True)
    except BaseException as exc:report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
