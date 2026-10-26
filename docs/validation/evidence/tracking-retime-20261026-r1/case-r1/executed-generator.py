"""C40: shared-author tracking retime, original even-frame oracle and independent tempo PCM."""
import argparse,copy,hashlib,json,subprocess,sys,time
from bisect import bisect_right
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-retime-20261026-r1'
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.28/final-r1/installed'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False)
    work=ROOT/'workspace'/('tracking-retime-20261026-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/'docs/assets'/('tracking-retime-20261026-'+a.run);public.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    sys.path.insert(0,str(INSTALL/'site'))
    import numpy as np
    from PIL import Image
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.media import ffmpeg_path,ffprobe_path,probe_media
    from ai_ad_editor.policy import resolve_local_path
    from ai_ad_editor.project import save_project
    from ai_ad_editor.float_standard_render import FloatRenderContext
    from ai_ad_editor.render import output_settings
    configure_local_runtime();ffmpeg=ffmpeg_path()
    entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',entry/'scripts/run.ps1']
    report=dict(status='running',cli_version='0.1.30',installed=str(INSTALL),registered_skill=True,
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
        check(name+' all decoded clocks and samples',len(rows)==(36 if name=='before' else 18) and len(samples)==(144000 if name=='before' else 72000) and [int(r[2]) for r in rows]==list(range(36 if name=='before' else 18)))
        return [r[-1].strip() for r in rows],samples,hashlib.sha256(pcm).hexdigest()
    try:
        check('actual registered CLI',cli('version','version')['cli_version']=='0.1.30')
        project=work/'编辑 工程'
        cli('import-source','convert','import','--input',ROOT/'docs/assets/float-tracking-20261026-r5/editable-native-tracking.aevpkg.zip','--output',project)
        p=json.loads((project/'project.json').read_bytes());seq=next(s for s in p['sequences'] if s['id']=='child');p['sequences']=[seq]
        p['settings']['output']['video']['pixel_format']='yuv444p'
        initial_rows={c['id']:c for t in seq['tracks'] for c in t['clips']}
        for clip in initial_rows.values():clip['link_id']='c40_av_follow'
        seq['editing']=dict(main_track_id='child_track_video_1',magnetic=True)
        save_project(project,p);save('initial-author-project.json',p)
        rights=sha(project/'rights-ledger.json');observed=copy.deepcopy(initial_rows['follow_marker']['tracking_binding']['observations'])
        cli('validate-initial','validate','--project',project)
        before=project/'renders/before.mkv';cli('render-before','render','--project',project,'--sequence-id','child','--output',before)
        request=work/'request.json';request.write_text(json.dumps(dict(action='retime',clip_ids=['moving_source'],
            transform=dict(speed=2))),encoding='utf8')
        frozen=sha(project/'project.json')
        planned=cli('edit-plan','timeline','edit','--project',project,'--sequence-id','child','--input',request,'--dry-run')
        plan=planned['plan'];save('magnetic-plan.json',plan)
        check('dry-run preserves author',sha(project/'project.json')==frozen)
        context=plan['steps'][0]['shared_author_context'];save('shared-author-context.json',context)
        check('source follower and audio share one complete author graph',set(context['context_clip_ids'])=={'moving_source','follow_marker','child_sound'} and
            len(plan['created_sequences'])==1 and len(plan['steps'][0]['retimed_members'])==3)
        check('new content clock is exact half duration',plan['after_duration_tick']==135000)
        cli('edit-apply','timeline','edit','--project',project,'--sequence-id','child','--input',request,
            '--expected-project-sha256',plan['base_project_sha256'])
        cli('validate-edited','validate','--project',project)
        changed=json.loads((project/'project.json').read_bytes());save('edited-author-project.json',changed)
        followers=[c['tracking_binding'] for seq in changed['sequences'] for t in seq['tracks'] for c in t['clips'] if c.get('tracking_binding')]
        check('original observations preserved without baking',len(followers)==1 and followers[0]['observations']==observed)
        parent_rows=[c for t in changed['sequences'][0]['tracks'] for c in t['clips']]
        check('independent parent slots select same author context',len(parent_rows)==3 and all('sequence_clip_id' in c for c in parent_rows) and
            len({c['sequence_id'] for c in parent_rows})==1 and len({c['link_id'] for c in parent_rows})==1)
        check('rights unchanged',sha(project/'rights-ledger.json')==rights)
        permutation=list(range(0,36,2));original=[];edited_hash=[];original_clocks=[];edited_clocks=[]
        for author,destination,clocks in ((p,original,original_clocks),(changed,edited_hash,edited_clocks)):
            with FloatRenderContext(project,author,author['sequences'][0],output_settings(author['settings'])) as ctx:
                for frame in range(ctx.timeline.frame_count):
                    pixels,meta=ctx.timeline.render_frame(frame);destination.append(hashlib.sha256(pixels.tobytes()).hexdigest())
                    state=next(r['tracking'] for r in meta['layers'] if r.get('tracking'))
                    clocks.append({k:state.get(k) for k in ('native_frame_index','native_pts','source_author_tick','source_time','values','active')})
        comparisons=[dict(frame=i,original_frame=old,actual=edited_hash[i],expected=original[old],
            pixels_equal=edited_hash[i]==original[old],clock_geometry_equal=edited_clocks[i]==original_clocks[old],
            original_native_frame=original_clocks[old]['native_frame_index'],actual_native_frame=edited_clocks[i]['native_frame_index']) for i,old in enumerate(permutation)]
        save('native-float-frame-oracles.json',comparisons)
        check('all Float32 pixels retain the independently specified original frame order',all(r['pixels_equal'] for r in comparisons))
        check('all native PTS author clocks and dynamic geometry retained',all(r['clock_geometry_equal'] for r in comparisons))
        edited=project/'renders/edited.mkv';rendered=cli('render-edited','render','--project',project,'--sequence-id','child','--output',edited)
        gpu=rendered['projection_acceleration'];save('gpu-receipt.json',gpu)
        check('actual GPU and owned cleanup',gpu['status']=='verified' and gpu['operations']['affine']>=18 and gpu['worker_closed'] and gpu['shared_handles_closed'])
        original_encoded=decoded('before',before);encoded=decoded('edited',edited)
        check('every decoded frame follows original permutation',encoded[0]==[original_encoded[0][i] for i in permutation])
        oracle=run('independent-tempo-pcm',[ffmpeg,'-nostdin','-v','error','-i',before,'-map','0:a:0',
            '-af','aformat=sample_fmts=flt,atempo=2.0,apad=whole_len=72000,atrim=end_sample=72000,asetpts=N/SR/TB',
            '-c:a','pcm_f32le','-f','f32le','-'],True)
        expected_pcm=np.frombuffer(oracle,'<f4').reshape(-1,2)
        error=float(np.max(np.abs(encoded[1]-expected_pcm)))
        check('complete stereo PCM equals independent tempo over original authored sound',np.array_equal(encoded[1],expected_pcm),max_absolute_error=error,samples=72000)
        package=public/'editable-tracking-retime.aevpkg.zip';cli('export-package','convert','export','--project',project,'--target-format','package','--output',package)
        restored=work/'重导入 工程';cli('import-edited','convert','import','--input',package,'--output',restored)
        cli('validate-imported','validate','--project',restored)
        r=json.loads((restored/'project.json').read_bytes());check('all bindings survive package',[c['tracking_binding'] for seq in r['sequences'] for t in seq['tracks'] for c in t['clips'] if c.get('tracking_binding')]==followers)
        restored_movie=restored/'renders/restored.mkv';cli('render-imported','render','--project',restored,'--sequence-id','child','--output',restored_movie)
        redone=decoded('restored',restored_movie);check('all encoded frames and full PCM preserved',redone[0]==encoded[0] and redone[2]==encoded[2])
        for frame in (0,1,5,9,12,17):cli('preview-'+str(frame),'preview','frame','--project',project,'--sequence-id','child','--frame',frame,'--height','180')
        cli('quality','quality','check','--project',project,'--input',edited)
        for label,path in [('before',before),('edited',edited)]:
            run(label+'-mp4',[ffmpeg,'-nostdin','-v','error','-n','-i',path,'-vf','zscale=transferin=linear:transfer=iec61966-2-1,format=yuv420p',
                '-c:v','libx264','-crf','17','-c:a','aac','-movflags','+faststart',public/(label+'.mp4')])
        run('gif',[ffmpeg,'-nostdin','-v','error','-n','-i',public/'edited.mp4','-filter_complex',
            '[0:v]fps=8,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',public/'edited.gif'])
        run('midpoint',[ffmpeg,'-nostdin','-v','error','-n','-ss','0.75','-i',public/'edited.mp4','-frames:v','1',public/'midpoint.png'])
        with Image.open(public/'edited.gif') as image:gif_frames=image.n_frames
        (public/'SOURCE.txt').write_text('C40: self-authored CC0 C36 geometry/marker and synthetic stereo tones; font license retained.\nInput ../float-tracking-20261026-r5/.\nReproduce scripts/run_tracking_magnetic_case_20261026.py --run <new-run>.\nActual shared-author 2x output, original video frames 0,2,...,34; independent native atempo PCM oracle. Silent GIF, synthetic-audio MP4. No continuous playback, natural quality or human listening acceptance.\n',encoding='utf8',newline='\n')
        files=[dict(path=f.relative_to(ROOT).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(public.iterdir()) if f.is_file()]
        save('public-media.json',files)
        (public/'media-manifest.json').write_text(json.dumps(dict(files=files,output_frames=18,seconds=1.5,fps=12,gif_frames=gif_frames,
            before=probe_media(public/'before.mp4'),edited=probe_media(public/'edited.mp4')),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',project=str(project),imported_project=str(restored),public=str(public),edited_frames=18,
            independent_float32_frames_equal=18,original_frame_permutation=permutation,all_tracking_clocks_geometry_equal=True,
            full_pcm_samples_per_channel=72000,max_pcm_error=error,restored_frames_and_pcm_equal=True,
            shared_author_members=3,gif_frames=gif_frames,package_sha256=sha(package),finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('calls','checks')},ensure_ascii=False),flush=True)
    except BaseException as exc:report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
