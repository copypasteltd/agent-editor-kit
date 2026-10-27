"""C51 actual installed MuseTalk CUDA inference; synthetic source/speech, no fake workers."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,math,shutil,subprocess,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--face-box',nargs=4,type=int,required=True);a=ap.parse_args()
assert a.run.replace('-','').isalnum()
out=BASE/('case-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
work=ROOT/'local/agent-ffmpeg'/('native-lipsync-case-'+a.run);work.mkdir(exist_ok=False)
public=ROOT/'docs/assets'/('native-lipsync-20261027-'+a.run);public.mkdir(exist_ok=False)
launcher='C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
ffmpeg=shutil.which('ffmpeg');assert ffmpeg
record=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),source_fallback=False,native_windows=True,virtualization=False,
    registered_skill=True,synthetic_protocol_worker=False,real_person_reference=False,continuous_playback=False,human_listening=False,
    natural_quality_accepted=False,full_digital_human_accepted=False,calls=[],checks=[])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save():(out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def check(name,value):record['checks'].append(dict(name=name,ok=bool(value)));save();assert value,name
def run(name,command,timeout=1200,binary=False,code=0):
    command=list(map(str,command));started=time.monotonic();r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
    stdout=(work if binary else out)/(name+('.bin' if binary else '.stdout.json'));stderr=out/(name+'.stderr.txt');stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
    record['calls'].append(dict(name=name,command=command,exit_code=r.returncode,expected_exit_code=code,seconds=time.monotonic()-started,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
    save();print(json.dumps(dict(name=name,exit_code=r.returncode,seconds=time.monotonic()-started)),flush=True)
    assert r.returncode==code,(name,r.stdout[-2500:],r.stderr[-1200:]);return r.stdout
def cli(name,*command,timeout=1200):
    value=json.loads(run(name,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',launcher,*command],timeout=timeout));check(name+' registered CLI0.1.41',value['ok'] and value['provenance']['cli_version']=='0.1.41');return value['data']
def decode(name,path,pixel_format='rgba'):
    return run(name,[ffmpeg,'-nostdin','-v','error','-i',path,'-an','-pix_fmt',pixel_format,'-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
def pcm(name,path):return run(name,[ffmpeg,'-nostdin','-v','error','-i',path,'-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'],binary=True)
try:
    cli('version','version');project=work/'可编辑 口型工程';cli('init','project','init',project)
    source_movie=ROOT/'local/agent-ffmpeg/lipsync-portrait-source-r1/assets/derived/fictional_portrait.mov'
    run('source-frame',[ffmpeg,'-nostdin','-v','error','-n','-ss','0.08','-i',source_movie,'-frames:v','1',public/'portrait-base.png'])
    image=np.asarray(Image.open(public/'portrait-base.png').convert('RGBA')).copy();image[:,0,3]=0;image[:,0,:3]=[31,73,111];image[:,-1,3]=129
    Image.fromarray(image).save(public/'portrait.png');height,width=image.shape[:2]
    speech=ROOT/'local/agent-ffmpeg/lipsync-voice-probe-r1/assets/derived/synthetic-speech.wav';shutil.copy2(speech,public/'speech.wav')
    proof=public/'SOURCE.txt';proof.write_text('C51 fictional portrait: actual local Wan2.1 VACE1.3B text-to-video, no real person reference. Original prompt/seed in evidence. Source frame2; original diagnostic alpha borders. Synthetic Mandarin speech from registered local Kokoro voice zf_001 on CUDA, explicitly saying this is artificial. Model/source/audio terms remain separate; engineering demonstration, not a naturalness or likeness endorsement. No third-party portrait/test video.\n',encoding='utf8')
    source=cli('ingest-image','media','ingest','--project',project,'--input',public/'portrait.png','--license-spdx','LicenseRef-Generated-Demo','--evidence',proof)['asset']['id']
    audio=cli('ingest-speech','media','ingest','--project',project,'--input',public/'speech.wav','--license-spdx','LicenseRef-Generated-Demo','--evidence',proof)['asset']['id']
    model=ROOT/'product/.runtime/models/musetalk-v15-20261027';native='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'
    adapter=cli('register','lipsync','adapter','register','--project',project,'--adapter-id','musetalk_local','--model-path',model,'--executable',native,
        '--evidence',BASE/'acquisition-metadata.json','--device','cuda','--threads','4','--batch-size','2','--license-spdx','MIT AND Apache-2.0','--creator','MuseTalk and model contributors')['adapter']
    author=json.loads((project/'project.json').read_bytes());author['settings']['canvas'].update(width=width,height=height,fps=dict(num=25,den=1));(project/'project.json').write_text(json.dumps(author,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    command=['lipsync','generate','--project',project,'--adapter-id','musetalk_local','--source-asset-id',source,'--audio-asset-id',audio,'--asset-id','spoken_portrait',
        '--face-box',*map(str,a.face_box),'--seed','17','--mask-top','.45','--feather-pixels','3','--apply','--video-track-id','track_video_1','--audio-track-id','track_audio_1']
    before=(project/'project.json').read_bytes();cli('dry-run',*command,'--dry-run');check('dry-run leaves project bytes unchanged',before==(project/'project.json').read_bytes())
    result=cli('generate-image',*command,timeout=1800);record['image_result']=result;save();generation=result['generation'];worker=generation['worker'];n=result['configuration']['video']['frames']
    master=project/result['asset']['uri'];raw=decode('master-rgba',master);frames=np.frombuffer(raw,np.uint8).reshape(n,height,width,4)
    check('all generated RGBA frames match real worker hash','sha256:'+hashlib.sha256(raw).hexdigest()==worker['metrics']['rgba_sha256'])
    check('actual real CUDA MuseTalk UNet and all audio frames',worker['providers']==['torch-cuda'] and worker['model_execution']['calls']['unet']==math.ceil(n/2) and sum(worker['model_execution']['batch_frames'])==n and worker['blocked_network_events']==[])
    check('all source alpha samples preserved',np.array_equal(frames[:,:,:,3],np.broadcast_to(image[:,:,3],(n,height,width))))
    x0,y0,x1,y1=a.face_box;outside=np.ones((height,width),bool);outside[y0:y1,x0:x1]=False
    check('all outside-region and invisible RGB preserved',np.array_equal(frames[:,outside,:3],np.broadcast_to(image[outside,:3],(n,int(outside.sum()),3))) and np.array_equal(frames[:,:,0,:3],np.broadcast_to(image[:,0,:3],(n,height,3))))
    source_pcm=pcm('source-pcm',public/'speech.wav');output_pcm=pcm('master-pcm',master);clock=result['configuration']['audio'];scalars=clock['samples']*clock['channels']
    check('all original selected PCM scalars bit equal',output_pcm[:len(source_pcm)]==source_pcm and len(source_pcm)==scalars*4)
    check('only explicit tail silence added',not np.any(np.frombuffer(output_pcm[len(source_pcm):],'<f4')) and clock['padding_seconds']<.04)
    check('real output changes mouth across time',np.count_nonzero(frames[:,y0:y1,x0:x1,:3]!=image[None,y0:y1,x0:x1,:3])>0 and np.abs(frames[0].astype(float)-frames[n//2].astype(float)).mean()>0)
    check('two independently editable linked clips',len(result['clips'])==2 and len({c['clip']['link_id'] for c in result['clips']})==1)
    check('all owned child processes and stdout handles closed',all(p['exited'] and p['stdout_closed'] for p in generation['cleanup']['processes']) and not generation['cleanup']['warnings'])
    cli('validate','validate','--project',project)
    rendered=project/'renders/spoken.mp4';cli('render','render','--project',project,'--output',rendered)
    export=cli('export','convert','export','--project',project,'--target-format','package','--output',project/'exports/lipsync.aevpkg.zip')
    restored=work/'restored';cli('import','convert','import','--input',export['output'],'--output',restored)
    restored_data=json.loads((restored/'project.json').read_bytes());restored_asset=next(v for v in restored_data['assets'] if v['id']=='spoken_portrait')
    check('package carries unchanged master source and rerunnable recipe',sha(restored/restored_asset['uri'])==sha(master) and restored_asset['source']['lipsync']==result['asset']['source']['lipsync'])
    restored_movie=restored/'renders/restored.mp4';cli('restored-render','render','--project',restored,'--output',restored_movie)
    rendered_raw=decode('rendered-rgba',rendered);restored_raw=decode('restored-rgba',restored_movie)
    check('all rendered frames match after editable package import',rendered_raw==restored_raw)
    check('all rendered decoded PCM matches after package import',pcm('rendered-pcm',rendered)==pcm('restored-pcm',restored_movie))
    cli('rerun-plan','lipsync','generate','--project',project,'--adapter-id','musetalk_local','--recipe-asset-id','spoken_portrait','--asset-id','spoken_new_seed','--seed','23','--dry-run')
    shutil.copy2(rendered,public/'spoken.mp4');shutil.copy2(export['output'],public/'editable-lipsync.aevpkg.zip')
    preview=np.frombuffer(decode('preview-rgb',rendered,'rgb24'),np.uint8).reshape(n,height,width,3)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16);comparison=[]
    for i in range(n):
        sheet=Image.new('RGB',(width*2,height+34),(22,26,32));sheet.paste(Image.fromarray(image).convert('RGB'),(0,34));sheet.paste(Image.fromarray(preview[i]),(width,34))
        draw=ImageDraw.Draw(sheet);draw.text((12,8),'SOURCE / synthetic portrait',font=font,fill='white');draw.text((width+12,8),'MuseTalk CUDA / synthetic lip sync',font=font,fill='white')
        comparison.append(sheet.resize((768,round((height+34)*768/(width*2))),Image.Resampling.LANCZOS))
    comparison[0].save(public/'comparison.gif',save_all=True,append_images=comparison[1:],duration=40,loop=0,optimize=False,disposal=2)
    comparison[0].save(public/'frame-first.png');comparison[n//2].save(public/'frame-middle.png');comparison[-1].save(public/'frame-last.png')
    with Image.open(public/'comparison.gif') as gif:
        duration=sum((gif.seek(i),gif.info.get('duration',0))[1] for i in range(gif.n_frames));check('GIF uses complete output clock',duration==n*40)
    record.update(status='passed',frames=n,fps=25,duration_seconds=n/25,selected_PCM_scalars=scalars,padded_PCM_scalars=clock['padded_samples']*clock['channels'],
        all_source_PCM_equal=True,all_source_alpha_equal=True,all_outside_region_RGB_equal=True,all_package_rendered_frames_equal=True,all_package_rendered_PCM_equal=True,
        GIF_duration_ms=duration,adapter_sha256=adapter['sha256'],model_execution=worker['model_execution'],project=str(project),
        public_files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in public.iterdir() if p.is_file()],finished_at_utc=datetime.now(timezone.utc).isoformat())
    save();print(json.dumps({k:v for k,v in record.items() if k not in ('image_result','calls','checks','public_files','model_execution')},ensure_ascii=False),flush=True)
except BaseException as exc:record.update(status='failed',error=repr(exc));save();raise
