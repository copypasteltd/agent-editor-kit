"""C51 actual moving-video boxes, recipe override and real CUDA cancellation."""
from pathlib import Path
import argparse,hashlib,json,math,shutil,subprocess,threading,time
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
out=BASE/('video-and-cancel-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
main=json.loads((BASE/'case-r1/verification.json').read_bytes());assert main['status']=='passed'
project=Path(main['project']);public=ROOT/'docs/assets/native-lipsync-20261027-r1';work=project.parent
launcher='C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1';ffmpeg=shutil.which('ffmpeg');prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',launcher]
record=dict(status='running',registered_installed_skill=True,source_fallback=False,fake_worker=False,native_windows=True,virtualization=False,calls=[],checks=[],human_listening=False,natural_quality_accepted=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save():(out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def check(name,ok):record['checks'].append(dict(name=name,ok=bool(ok)));save();assert ok,name
def run(name,command,*,binary=False,code=0):
    started=time.monotonic();r=subprocess.run(list(map(str,command)),capture_output=True,cwd=ROOT,timeout=1200,creationflags=subprocess.CREATE_NO_WINDOW)
    stdout=(work if binary else out)/(name+('.bin' if binary else '.stdout.json'));stderr=out/(name+'.stderr.txt');stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
    record['calls'].append(dict(name=name,command=list(map(str,command)),exit_code=r.returncode,seconds=time.monotonic()-started,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)));save()
    print(json.dumps(dict(name=name,exit_code=r.returncode,seconds=time.monotonic()-started)),flush=True)
    assert r.returncode==code,(name,r.stdout[-2000:],r.stderr[-1000:]);return r.stdout
def cli(name,*command):
    v=json.loads(run(name,[*prefix,*command]));check(name+' actual registered CLI',v['ok'] and v['provenance']['cli_version']=='0.1.41');return v['data']
try:
    image=Image.open(public/'portrait.png').convert('RGBA');width,height=image.size;n=30;base=list(map(int,main['image_result']['configuration']['boxes']['keys'][0]['box']))
    offsets=[];source=[]
    for i in range(n):
        x=round(12*i/15) if i<=15 else round(12*(29-i)/14);offsets.append(x)
        frame=Image.new('RGBA',(width,height),(34,47,61,255));frame.paste(image,(x,0));source.append(np.asarray(frame).copy())
    raw=np.stack(source).tobytes();movie=public/'moving-source.mov'
    encoded=subprocess.run([ffmpeg,'-nostdin','-v','error','-n','-f','rawvideo','-pixel_format','rgba','-video_size',f'{width}x{height}','-framerate','25','-i','pipe:0',
        '-an','-c:v','qtrle','-pix_fmt','argb',str(movie)],input=raw,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'source-encode.stderr.txt').write_bytes(encoded.stderr);check('source encoding succeeds',encoded.returncode==0)
    decoded=run('moving-source-rgba',[ffmpeg,'-v','error','-i',movie,'-an','-pix_fmt','rgba','-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True);check('all moving source frames lossless',decoded==raw)
    source_id=cli('ingest-moving','media','ingest','--project',project,'--input',movie,'--license-spdx','LicenseRef-Generated-Demo','--evidence',public/'SOURCE.txt')['asset']['id']
    keys=dict(clock='output-frame-25fps',keys=[dict(frame=i,box=[base[0]+x,base[1],base[2]+x,base[3]]) for i,x in [(0,0),(15,12),(29,0)]])
    box_file=public/'moving-boxes.json';box_file.write_text(json.dumps(keys,indent=2)+'\n',encoding='utf8')
    result=cli('generate-moving','lipsync','generate','--project',project,'--adapter-id','musetalk_local','--recipe-asset-id','spoken_portrait','--asset-id','moving_spoken',
        '--source-asset-id',source_id,'--boxes-file',box_file,'--source-mode','once','--source-start-seconds','0','--source-end-seconds','1.2',
        '--audio-start-seconds','0','--audio-end-seconds','1.2','--apply','--video-track-id','track_video_1','--audio-track-id','track_audio_1',
        '--timeline-start-seconds',str(main['duration_seconds']+.2))
    output=project/result['asset']['uri'];generated=run('moving-output-rgba',[ffmpeg,'-v','error','-i',output,'-an','-pix_fmt','rgba','-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
    frames=np.frombuffer(generated,np.uint8).reshape(n,height,width,4);original=np.stack(source)
    check('all moving alpha bytes preserved',np.array_equal(frames[:,:,:,3],original[:,:,:,3]))
    for i,x in enumerate(offsets):
        outside=np.ones((height,width),bool);outside[base[1]:base[3],base[0]+x:base[2]+x]=False
        check('moving frame '+str(i)+' outside box RGB',np.array_equal(frames[i,outside,:3],original[i,outside,:3]))
    worker=result['generation']['worker'];check('actual moving neural CUDA and all 30 frames',worker['providers']==['torch-cuda'] and sum(worker['model_execution']['batch_frames'])==30 and worker['blocked_network_events']==[])
    check('recipe carries source override and moving box keys',result['asset']['source']['lipsync']['source_asset_id']==source_id and result['asset']['source']['lipsync']['boxes']==keys)
    run('moving-preview',[ffmpeg,'-v','error','-n','-i',output,'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',public/'moving-spoken.mp4'])
    cli('validate-moving','validate','--project',project)
    # Cancel only after a genuine worker reports nonzero emitted frames.
    marker=work/'real-lipsync-cancel.marker';before={str(p.relative_to(project)):sha(p) for p in project.rglob('*.json') if not p.is_relative_to(project/'cache') and not p.is_relative_to(project/'snapshots') and not p.is_relative_to(project/'renders/diagnostics')}
    command=[*prefix,'lipsync','generate','--project',str(project),'--adapter-id','musetalk_local','--recipe-asset-id','spoken_portrait','--asset-id','cancel_unpublished',
        '--cancel-file',str(marker),'--progress','jsonl'];started=time.monotonic()
    process=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    stdout=[];stderr=[];events=[];triggered=threading.Event()
    def read_stdout():
        while chunk:=process.stdout.read(65536):stdout.append(chunk)
    def read_stderr():
        for line in iter(process.stderr.readline,b''):
            stderr.append(line)
            try:event=json.loads(line)
            except (ValueError,TypeError):continue
            events.append(event)
            if event.get('stage')=='lipsync.generate' and float(event.get('percent') or 0)>0 and not triggered.is_set():
                marker.write_text('Cancel only this actual lip-sync operation after emitted neural frames.\n',encoding='utf8');triggered.set()
    readers=[threading.Thread(target=read_stdout),threading.Thread(target=read_stderr)]
    for thread in readers:thread.start()
    try:process.wait(timeout=900)
    except subprocess.TimeoutExpired:
        marker.write_text('Owned cancellation deadline\n',encoding='utf8')
        try:process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW);raise
    finally:
        for thread in readers:thread.join(timeout=20)
        for stream in (process.stdout,process.stderr):stream.close()
    raw_stdout=b''.join(stdout);raw_stderr=b''.join(stderr);(out/'cancel.stdout.json').write_bytes(raw_stdout);(out/'cancel.stderr.jsonl').write_bytes(raw_stderr)
    response=json.loads(raw_stdout);check('real cancellation follows emitted model frames',triggered.is_set() and process.returncode==8 and response['errors'][0]['code']=='CANCELLED')
    after={str(p.relative_to(project)):sha(p) for p in project.rglob('*.json') if not p.is_relative_to(project/'cache') and not p.is_relative_to(project/'snapshots') and not p.is_relative_to(project/'renders/diagnostics')}
    check('real cancellation rolls back all project metadata',before==after);check('no partial asset or owned workspace remains',not(project/'assets/derived/cancel_unpublished.mov').exists() and not list((project/'cache/managed-jobs').glob('job-*')))
    diagnostic=response['errors'][0].get('diagnostics',{});check('real cancellation retains diagnostic evidence',diagnostic.get('status')=='stored')
    diagnostics=cli('cancel-diagnostic','diagnostics','show','--project',project,'--diagnostic-id',diagnostic['diagnostic_id'])
    processes=diagnostics['manifest']['processes'];check('all cancelled native pipeline children exited',len(processes)==3 and all(p.get('state') in {'exited','terminated_by_cleanup'} and p.get('final_exit') is not None for p in processes))
    record.update(status='passed',moving_frames=30,model_execution=worker['model_execution'],all_moving_source_alpha_and_outside_RGB_equal=True,
        moving_recipe=result['asset']['source']['lipsync'],real_cancel_after_neural_frames=True,cancel_seconds=time.monotonic()-started,cancel_progress=events,
        cancellation_diagnostic=diagnostics,public_files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in (movie,box_file,public/'moving-spoken.mp4')])
    save();print(json.dumps(dict(status='passed',moving_frames=30,real_cancel_after_neural_frames=True)),flush=True)
except BaseException as exc:record.update(status='failed',error=repr(exc));save();raise
