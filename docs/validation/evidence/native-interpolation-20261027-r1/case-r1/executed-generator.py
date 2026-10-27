"""C52 actual installed RIFE CUDA; held-out animation, VFR alpha and full packages."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,math,shutil,subprocess,time,threading
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-interpolation-20261027-r1'
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
out=BASE/('case-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
work=ROOT/'local/agent-ffmpeg'/('native-interpolation-case-'+a.run);work.mkdir(exist_ok=False)
public=ROOT/'docs/assets'/('native-interpolation-20261027-'+a.run);public.mkdir(exist_ok=False)
launcher='C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1';ffmpeg=shutil.which('ffmpeg');assert ffmpeg
prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',launcher]
record=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),source_fallback=False,native_windows=True,virtualization=False,
    registered_skill=True,synthetic_protocol_worker=False,continuous_playback=False,human_listening=False,natural_quality_accepted=False,calls=[],checks=[])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save():(out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def check(name,value):record['checks'].append(dict(name=name,ok=bool(value)));save();assert value,name
def run(name,command,timeout=1200,binary=False,code=0,input=None):
    command=list(map(str,command));started=time.monotonic();r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW,input=input)
    stdout=(work if binary else out)/(name+('.bin' if binary else '.stdout.json'));stderr=out/(name+'.stderr.txt');stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
    record['calls'].append(dict(name=name,command=command,exit_code=r.returncode,expected_exit_code=code,seconds=time.monotonic()-started,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
    save();print(json.dumps(dict(name=name,exit_code=r.returncode,seconds=time.monotonic()-started)),flush=True)
    assert r.returncode==code,(name,r.stdout[-3500:],r.stderr[-1200:]);return r.stdout
def cli(name,*command,timeout=1200):
    value=json.loads(run(name,[*prefix,*command],timeout=timeout));check(name+' registered CLI0.1.42',value['ok'] and value['provenance']['cli_version']=='0.1.42');return value['data']
def decode(name,path):return run(name,[ffmpeg,'-nostdin','-v','error','-i',path,'-an','-pix_fmt','rgba','-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
def pcm(name,path):return run(name,[ffmpeg,'-nostdin','-v','error','-i',path,'-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'],binary=True)
def encode(name,images,path,rate=12,expression=None,timescale=None):
    command=[ffmpeg,'-nostdin','-v','error','-n','-f','rawvideo','-pixel_format','rgba','-video_size',f'{images.shape[2]}x{images.shape[1]}','-framerate',str(rate),'-i','pipe:0','-an','-c:v','qtrle','-pix_fmt','argb','-fps_mode','passthrough']
    if expression:command+=['-enc_time_base','1/'+str(timescale),'-/bsf:v',expression,'-video_track_timescale',str(timescale)]
    run(name,[*command,path],input=images.tobytes())
try:
    cli('version','version');project=work/'可编辑 补帧工程';cli('init','project','init',project)
    # Native source animation at24fps; odd frames are never provided to RIFE.
    trailer=ROOT/'product/.runtime/models/rife-v4.25-20261027/sintel-trailer.mp4'
    raw=run('extract-original',[ffmpeg,'-nostdin','-v','error','-ss','12','-i',trailer,'-t','2','-vf','scale=320:180:flags=lanczos,fps=24','-pix_fmt','rgba','-f','rawvideo','pipe:1'],binary=True)
    reference=np.frombuffer(raw,np.uint8).reshape(-1,180,320,4).copy();check('known original reference has48 frames',len(reference)==48)
    sparse=reference[::2].copy();encode('original-reference',reference,public/'original-reference.mov',24);encode('sparse-source',sparse,public/'sparse-source.mov',12)
    run('original-preview',[ffmpeg,'-v','error','-n','-i',public/'original-reference.mov','-c:v','libx264','-pix_fmt','yuv420p','-crf','18',public/'original-reference.mp4'])
    proof=public/'SOURCE.txt';proof.write_text('Sintel trailer excerpt: (c) copyright Blender Foundation | durian.blender.org. CC BY3.0 https://creativecommons.org/licenses/by/3.0/ ; primary license https://durian.blender.org/sharing/ ; downloaded W3C sample https://media.w3.org/2010/05/sintel/trailer.mp4 . Excerpt12..14s, resized320x180,24fps reference. Even frames only form12fps input. Odd originals are held-out references; no original odd frame is supplied to RIFE. Derived interpolation, slow motion and comparisons modified by agent editor kit. This is animation, not live-action. Synthetic transparency/clock fixture is original CC0 diagnostic art and tones. No artificial result is labelled original ground truth.\n',encoding='utf8')
    source=cli('ingest-natural','media','ingest','--project',project,'--input',public/'sparse-source.mov','--license-spdx','CC-BY-3.0','--creator','Blender Foundation','--evidence',proof)['asset']['id']
    model=ROOT/'product/.runtime/models/rife-v4.25-20261027';native='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'
    adapter=cli('register','interpolate','adapter','register','--project',project,'--adapter-id','rife425_local','--model-path',model,'--executable',native,'--evidence',BASE/'weight-conversion.json','--device','cuda','--threads','4','--scale','1','--license-spdx','MIT','--creator','Practical-RIFE contributors')['adapter']
    author=json.loads((project/'project.json').read_bytes());author['settings']['canvas'].update(width=320,height=180,fps=dict(num=24,den=1));(project/'project.json').write_text(json.dumps(author,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    command=['interpolate','generate','--project',project,'--adapter-id','rife425_local','--source-asset-id',source,'--asset-id','sintel_4x','--factor','4','--scene-cut-threshold','0','--apply','--video-track-id','track_video_1','--playback-speed','.25']
    before=(project/'project.json').read_bytes();cli('dry-run',*command,'--dry-run');check('dry-run project bytes unchanged',before==(project/'project.json').read_bytes())
    result=cli('generate-natural',*command);master=project/result['asset']['uri'];frames=np.frombuffer(decode('natural-master',master),np.uint8).reshape(96,180,320,4)
    check('every actual original RGBA anchor preserved',np.array_equal(frames[::4],sparse));execution=result['generation']['worker']['model_execution']
    check('actual CUDA69 forwards with arbitrary quarter-time queries',execution['flow_forwards']==69 and execution['time_queries']=={'1/4':23,'2/4':23,'3/4':23} and result['generation']['worker']['blocked_network_events']==[])
    generated=frames[np.arange(23)*4+2,:,:,:3].astype(np.float64);truth=reference[np.arange(23)*2+1,:,:,:3].astype(np.float64)
    hold=sparse[:23,:,:,:3].astype(np.float64);linear=(sparse[:23,:,:,:3].astype(np.float64)+sparse[1:,:,:,:3].astype(np.float64))/2
    mse=((generated-truth)**2).mean(axis=(1,2,3));hold_mse=((hold-truth)**2).mean(axis=(1,2,3));linear_mse=((linear-truth)**2).mean(axis=(1,2,3))
    record['held_out_comparison']=dict(count=23,scope='24fps_odd_originals_at_output_even_midpoints_only_no_ground_truth_at_quarters',
        model_mse=float(mse.mean()),hold_mse=float(hold_mse.mean()),linear_blend_mse=float(linear_mse.mean()),
        model_better_than_hold_frames=int((mse<hold_mse).sum()),model_better_than_blend_frames=int((mse<linear_mse).sum()),
        per_frame=[dict(pair=i,model_mse=float(x),hold_mse=float(y),linear_blend_mse=float(z)) for i,(x,y,z) in enumerate(zip(mse,hold_mse,linear_mse))])
    worst=int(np.argmax(mse));Image.fromarray(np.concatenate((truth[worst],generated[worst],np.clip(np.abs(generated[worst]-truth[worst])*4,0,255)),axis=1).astype('uint8')).save(public/'held-out-worst.png')
    check('held-out results measured independently without quality pass threshold',len(mse)==23 and np.isfinite(mse).all())
    # Independent original CC0 diagnostic, genuinely variable intervals and alpha.
    y,x=np.mgrid[:120,:192];images=[]
    for i in range(12):
        image=np.stack(((x*3+y*5)%256,(x*7-y)%256,(x*y)%256,np.zeros_like(x)),axis=-1).astype('uint8');cx=36+8*i
        distance=np.sqrt((x-cx)**2+(y-60)**2);image[:,:,3]=np.clip((28-distance)*40,0,255).astype('uint8');image[:,:,0]=np.where(distance<28,220,image[:,:,0]);images.append(image)
    images=np.stack(images);images[6:,:,:,:3]=255-images[6:,:,:,:3]
    durations=[80,120]*6;pts=np.cumsum([0]+durations[:-1]).tolist();clock=dict(time_base='1/1000',pts=pts,durations=durations)
    # Clock expression is a local producer fixture, independent of product lookup.
    def expression(values):
        result=str(values[-1])
        for i in range(len(values)-2,-1,-1):result=f'if(eq(N,{i}),{values[i]},{result})'
        return result
    option=work/'source-clock.txt';option.write_text("setts=ts='"+expression(pts)+"':duration='"+expression(durations)+"':time_base=1/1000",encoding='ascii')
    silent=work/'alpha-silent.mov';encode('alpha-source-video',images,silent,expression=option,timescale=1000)
    alpha_source=public/'alpha-vfr-source.mov'
    run('alpha-source-audio',[ffmpeg,'-v','error','-n','-i',silent,'-f','lavfi','-i','sine=frequency=523:sample_rate=44100:duration=1.2','-map','0:v','-map','1:a','-c:v','copy','-c:a','pcm_f32le','-ac','2','-video_track_timescale','1000',alpha_source])
    alpha_id=cli('ingest-alpha','media','ingest','--project',project,'--input',alpha_source,'--license-spdx','CC0-1.0','--evidence',proof)['asset']['id']
    alpha=cli('generate-alpha','interpolate','generate','--project',project,'--adapter-id','rife425_local','--asset-id','alpha_vfr_3x','--source-asset-id',alpha_id,'--factor','3','--scene-cut-threshold','0','--cut-after-frame','5','--apply','--video-track-id','track_video_1','--audio-track-id','track_audio_1','--timeline-start-seconds','8.2')
    alpha_master=project/alpha['asset']['uri'];alpha_frames=np.frombuffer(decode('alpha-master',alpha_master),np.uint8).reshape(36,120,192,4)
    check('all original VFR RGBA including hidden RGB equal',np.array_equal(alpha_frames[::3],images));check('explicit cut holds without crossing model',np.array_equal(alpha_frames[15],alpha_frames[16]) and np.array_equal(alpha_frames[15],alpha_frames[17]) and alpha['generation']['worker']['metrics']['cut_after_frames']==[5])
    synthetic=alpha_frames[np.arange(36)%3!=0];check('all synthesized alpha0 pixels have zero hidden RGB except explicit holds',all(not np.any(alpha_frames[i,:,:,:3][alpha_frames[i,:,:,3]==0]) for i in range(36) if i%3 and i//3 not in (5,11)))
    source_pcm=pcm('alpha-source-pcm',alpha_source);output_pcm=pcm('alpha-output-pcm',alpha_master);check('all original stereo44100 PCM scalars preserved',source_pcm==output_pcm)
    check('native VFR all PTS and durations verified',alpha['generation']['all_native_PTS_and_durations_verified']);check('linked independent video audio slowmotion clips',len(alpha['clips'])==2 and alpha['clips'][0]['clip']['link_id']==alpha['clips'][1]['clip']['link_id'])
    cli('validate','validate','--project',project);rendered=project/'renders/slow.mp4';cli('render','render','--project',project,'--output',rendered)
    export=cli('export','convert','export','--project',project,'--target-format','package','--output',project/'exports/interpolation.aevpkg.zip')
    restored=work/'restored';cli('import','convert','import','--input',export['output'],'--output',restored);restored_data=json.loads((restored/'project.json').read_bytes())
    for item in (result,alpha):
        asset=next(v for v in restored_data['assets'] if v['id']==item['asset']['id']);check(item['asset']['id']+' package preserves master and native recipe',sha(restored/asset['uri'])==sha(project/item['asset']['uri']) and asset['source']['interpolation']==item['asset']['source']['interpolation'])
    restored_movie=restored/'renders/restored.mp4';cli('restored-render','render','--project',restored,'--output',restored_movie)
    check('complete rendered RGBA equality after package import',decode('rendered-rgba',rendered)==decode('restored-rgba',restored_movie));check('complete rendered decoded PCM equality after package import',pcm('rendered-pcm',rendered)==pcm('restored-pcm',restored_movie))
    cli('rerun-plan','interpolate','generate','--project',project,'--adapter-id','rife425_local','--recipe-asset-id','sintel_4x','--asset-id','sintel_new_factor','--factor','3','--dry-run')
    shutil.copy2(rendered,public/'slow-motion.mp4');shutil.copy2(export['output'],public/'editable-interpolation.aevpkg.zip')
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);sheets=[]
    for i,image in enumerate(frames):
        sheet=Image.new('RGB',(640,214),(22,26,32));sheet.paste(Image.fromarray(sparse[i//4,:,:,:3]),(0,34));sheet.paste(Image.fromarray(image[:,:,:3]),(320,34));draw=ImageDraw.Draw(sheet)
        draw.text((8,8),'SOURCE12fps / slowed4x',font=font,fill='white');draw.text((328,8),'RIFE CUDA4x / slowed4x',font=font,fill='white');sheets.append(sheet)
    gif_durations=[round((i+1)*800/96)*10-round(i*800/96)*10 for i in range(96)]
    sheets[0].save(public/'comparison.gif',save_all=True,append_images=sheets[1:],duration=gif_durations,loop=0,optimize=False,disposal=2);sheets[48].save(public/'comparison.png')
    with Image.open(public/'comparison.gif') as gif:gif_ms=sum((gif.seek(i),gif.info.get('duration',0))[1] for i in range(gif.n_frames))
    check('GIF actual clock8 seconds',gif_ms==8000)
    record.update(status='passed',source_frames=24,generated_frames=96,actual_model_forwards=execution['flow_forwards'],source_duration_seconds=2,slow_motion_seconds=8,
        alpha_VFR_source_frames=12,alpha_VFR_generated_frames=36,alpha_model_forwards=alpha['generation']['worker']['model_execution']['flow_forwards'],
        selected_PCM_scalars=len(source_pcm)//4,all_package_rendered_frames_equal=True,all_package_rendered_PCM_equal=True,GIF_duration_ms=gif_ms,
        source_asset_id=source,alpha_asset_id=alpha_id,project=str(project),adapter_sha256=adapter['sha256'],natural_result=result,alpha_result=alpha,
        public_files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in public.iterdir() if p.is_file()],finished_at_utc=datetime.now(timezone.utc).isoformat())
    save();print(json.dumps({k:v for k,v in record.items() if k in ('status','source_frames','generated_frames','actual_model_forwards','alpha_model_forwards','selected_PCM_scalars','held_out_comparison')},ensure_ascii=False),flush=True)
except BaseException as exc:record.update(status='failed',error=repr(exc));save();raise
