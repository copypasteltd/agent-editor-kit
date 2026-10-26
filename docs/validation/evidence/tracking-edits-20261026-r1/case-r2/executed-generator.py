"""Registered installed Skill: edit C36 source, follower and audio, then encode C37.

Reuses the published self-authored CC0 source/marker/tones and retained font
license. Every retained encoded frame and complete stereo PCM are compared to
the untouched input render; no inference or network provider is invoked.
"""
import argparse,copy,hashlib,json,shutil,subprocess,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-edits-20261026-r1'
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.25/final-r2/installed'

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args()
    assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False)
    work=ROOT/'workspace'/('tracking-edits-20261026-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/'docs/assets'/('tracking-edits-20261026-'+a.run);public.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    sys.path.insert(0,str(INSTALL/'site'))
    import numpy as np
    from PIL import Image
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.media import ffmpeg_path,probe_media
    from ai_ad_editor.project import save_project
    configure_local_runtime();ffmpeg=ffmpeg_path()
    entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(entry/'scripts/run.ps1')]
    report=dict(status='running',cli_version='0.1.27',installed=str(INSTALL),registered_skill=True,
        source_fallback=False,virtualization=False,new_model_forwards=0,natural_quality_accepted=False,
        continuous_playback=False,human_listening=False,calls=[],checks=[],
        diagnostic_delivery='H264 CRF0 yuv444p 8bit; Float32 composition checked separately',
        started_at_utc=datetime.now(timezone.utc).isoformat())
    def save(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,passed,**details):
        report['checks'].append(dict(name=name,ok=bool(passed),**details));save('verification.json',report)
        assert passed,(name,details)
    def run(name,argv,binary=False):
        argv=list(map(str,argv));start=time.perf_counter()
        r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        if binary:
            stdout=work/(name+'.stdout.bin');stdout.write_bytes(r.stdout)
        else:
            stdout=out/(name+'.stdout.log');stdout.write_bytes(r.stdout)
        stderr=out/(name+'.stderr.log');stderr.write_bytes(r.stderr)
        report['calls'].append(dict(name=name,argv=argv,exit_code=r.returncode,seconds=time.perf_counter()-start,
            stdout_path=str(stdout),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
        save('verification.json',report);print(json.dumps(dict(name=name,code=r.returncode)),flush=True)
        assert r.returncode==0,(name,r.stdout[-3500:],r.stderr[-2000:])
        return r.stdout
    def cli(name,*argv):
        value=json.loads(run(name,[*prefix,*argv]));assert value['ok'],value
        return value['data']
    def decoded(name,path,frames):
        raw=run(name+'-frames',[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:v:0','-pix_fmt','rgba64le','-f','framemd5','-'])
        rows=[line.split(',') for line in raw.decode().splitlines() if line and not line.startswith('#')]
        pcm=run(name+'-pcm',[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:a:0','-c:a','pcm_f32le','-f','f32le','-'],True)
        samples=np.frombuffer(pcm,'<f4').reshape(-1,2)
        check(name+' actual complete decoded sizes',len(rows)==frames and len(samples)==frames*4000,
            frames=len(rows),samples_per_channel=len(samples))
        check(name+' exact output frame clocks',[int(r[2]) for r in rows]==list(range(frames)))
        return [r[-1].strip() for r in rows],samples,hashlib.sha256(pcm).hexdigest()
    def observations(project):
        return [c['tracking_binding']['observations'] for seq in project['sequences'] for t in seq['tracks'] for c in t['clips'] if c.get('tracking_binding')]
    try:
        check('registered current installed version',cli('version','version')['cli_version']=='0.1.27')
        source=ROOT/'docs/assets/float-tracking-20261026-r5/editable-native-tracking.aevpkg.zip'
        project=work/'编辑 工程'
        cli('import-original','convert','import','--input',source,'--output',project)
        p=json.loads((project/'project.json').read_bytes())
        # Isolate the editable child as the root for a direct cut/splice oracle.
        # This fixture setup changes no source, keys, binding, audio or rights.
        child=next(s for s in p['sequences'] if s['id']=='child');p['sequences']=[child]
        # CRF0 with this machine's 10-bit x264 has transform bypass disabled.
        # Use an explicit 8-bit lossless diagnostic boundary; do not mistake
        # re-encoding a changed P-frame history for unchanged decoded pixels.
        p['settings']['output']['video']['pixel_format']='yuv444p'
        save_project(project,p);save('initial-author-project.json',p)
        ledger_sha=sha(project/'rights-ledger.json');original_observations=observations(p)[0]
        cli('validate-original','validate','--project',project)
        before=project/'renders/before.mkv'
        baseline=cli('render-before','render','--project',project,'--sequence-id','child','--output',before)
        untouched=decoded('before',before,36)
        operations=[dict(op='split_clip',clip_id='moving_source',at_tick=67500,left_id='source_left',right_id='source_right'),
            dict(op='split_clip',clip_id='follow_marker',at_tick=135000,left_id='follower_left',right_id='follower_right'),
            dict(op='split_clip',clip_id='child_sound',at_tick=67500,left_id='sound_left',right_id='sound_right'),
            dict(op='ripple_delete',at_tick=90000,duration_tick=45000)]
        edit=work/'edit.json';edit.write_text(json.dumps(dict(sequence_id='child',operations=operations)),encoding='utf8')
        before_dry=sha(project/'project.json')
        cli('compose-dry-run','timeline','compose','--project',project,'--input',edit,'--dry-run')
        check('dry run preserves authored bytes',sha(project/'project.json')==before_dry)
        cli('compose-apply','timeline','compose','--project',project,'--input',edit)
        cli('validate-edited','validate','--project',project)
        changed=json.loads((project/'project.json').read_bytes());save('edited-author-project.json',changed)
        bindings=[c['tracking_binding'] for t in changed['sequences'][0]['tracks'] for c in t['clips'] if c.get('tracking_binding')]
        check('both followers preserve original observations and reference',len(bindings)==2 and
            all(b['observations']==original_observations and b['reference_output_tick']==0 and len(b['source_fragments'])==3 for b in bindings))
        check('rights ledger unchanged',sha(project/'rights-ledger.json')==ledger_sha)
        from ai_ad_editor.float_standard_render import FloatRenderContext
        from ai_ad_editor.render import output_settings
        indices=list(range(12))+list(range(18,36));reference_pixels=[];reference_states=[]
        with FloatRenderContext(project,p,p['sequences'][0],output_settings(p['settings'])) as context:
            for i in indices:
                pixels,meta=context.timeline.render_frame(i);reference_pixels.append(pixels.copy())
                reference_states.append(next(r['tracking'] for r in meta['layers'] if 'tracking' in r))
        frame_checks=[]
        with FloatRenderContext(project,changed,changed['sequences'][0],output_settings(changed['settings'])) as context:
            for i,j in enumerate(indices):
                pixels,meta=context.timeline.render_frame(i)
                state=next(r['tracking'] for r in meta['layers'] if 'tracking' in r)
                equal=np.array_equal(pixels,reference_pixels[i])
                same_clock=all(state[k]==reference_states[i][k] for k in ('native_frame_index','native_pts','native_time','source_author_tick','values'))
                frame_checks.append(dict(frame=i,original_frame=j,pixels_equal=equal,clock_geometry_equal=same_clock,
                    float32_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),native_pts=state['native_pts'],native_frame_index=state['native_frame_index']))
        save('native-float-frame-oracles.json',frame_checks)
        check('all actual Float32 pixels native clocks and binding geometry unchanged',all(r['pixels_equal'] and r['clock_geometry_equal'] for r in frame_checks))
        actual=project/'renders/edited.mkv'
        rendered=cli('render-edited','render','--project',project,'--sequence-id','child','--output',actual)
        save('native-pipeline.json',rendered['delivery']['pixel_pipeline']);save('gpu-receipt.json',rendered['projection_acceleration'])
        gpu=rendered['projection_acceleration']
        check('actual GPU projection and owned cleanup',gpu['status']=='verified' and gpu['operations'].get('affine',0)>0 and gpu['worker_closed'] and gpu['shared_handles_closed'])
        encoded=decoded('edited',actual,30)
        check('every retained encoded pixel frame matches untouched render',encoded[0]==[untouched[0][i] for i in indices],original_frame_indices=indices)
        expected=np.concatenate((untouched[1][:48000],untouched[1][72000:]),axis=0)
        error=float(np.max(np.abs(encoded[1]-expected)))
        check('complete stereo PCM exact splice',np.array_equal(encoded[1],expected),max_absolute_error=error,samples_per_channel=120000)
        archive=public/'editable-tracking-edits.aevpkg.zip'
        cli('export-package','convert','export','--project',project,'--target-format','package','--output',archive)
        imported=work/'重导入 工程';cli('import-edited','convert','import','--input',archive,'--output',imported)
        cli('validate-imported','validate','--project',imported)
        restored=json.loads((imported/'project.json').read_bytes())
        check('package preserves every binding and complete original observation',
            [c.get('tracking_binding') for t in restored['sequences'][0]['tracks'] for c in t['clips']]==
            [c.get('tracking_binding') for t in changed['sequences'][0]['tracks'] for c in t['clips']])
        restored_path=imported/'renders/restored.mkv'
        cli('render-imported','render','--project',imported,'--sequence-id','child','--output',restored_path)
        restored_decoded=decoded('restored',restored_path,30)
        check('package restored all decoded frames and full PCM equal',restored_decoded[0]==encoded[0] and restored_decoded[2]==encoded[2])
        for frame in (0,11,12,29):cli('preview-'+str(frame),'preview','frame','--project',project,'--sequence-id','child','--frame',frame,'--height',180)
        cli('quality','quality','check','--project',project,'--input',actual)
        for label,path in [('before',before),('edited',actual)]:
            run(label+'-mp4',[ffmpeg,'-nostdin','-v','error','-n','-i',path,'-vf','zscale=transferin=linear:transfer=iec61966-2-1,format=yuv420p',
                '-c:v','libx264','-crf','17','-c:a','aac','-movflags','+faststart',public/(label+'.mp4')])
        run('edited-gif',[ffmpeg,'-nostdin','-v','error','-n','-i',public/'edited.mp4','-filter_complex',
            '[0:v]fps=8,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',public/'edited.gif'])
        run('midpoint',[ffmpeg,'-nostdin','-v','error','-n','-ss','1.25','-i',public/'edited.mp4','-frames:v','1',public/'midpoint.png'])
        with Image.open(public/'midpoint.png') as image:image.verify()
        with Image.open(public/'edited.gif') as image:gif_frames=image.n_frames
        check('actual preview files decode',gif_frames==20)
        (public/'SOURCE.txt').write_text('C37: self-authored controlled CC0 geometry, marker and synthetic stereo tones from C36.\nInput sources: ../float-tracking-20261026-r5/; original font license retained in editable package.\nSilent GIF; MP4 contains synthetic tones, not speech. Static frame inspection only; no continuous playback or human listening.\nReproduction: scripts/run_tracking_edits_case_20261026.py --run <new-run>.\n',encoding='utf8',newline='\n')
        files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()]
        (public/'media-manifest.json').write_text(json.dumps(dict(files=files,input_frames=36,output_frames=30,seconds=2.5,fps=12,gif_frames=gif_frames,
            before=probe_media(public/'before.mp4'),edited=probe_media(public/'edited.mp4')),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',project=str(project),imported_project=str(imported),public=str(public),
            original_frames=36,edited_frames=30,retained_frame_indices=indices,full_pcm_samples_per_channel=120000,max_pcm_error=error,
            restored_frames_and_pcm_equal=True,gif_frames=gif_frames,package_sha256=sha(archive),
            finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in {'calls','checks'}},ensure_ascii=False),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
