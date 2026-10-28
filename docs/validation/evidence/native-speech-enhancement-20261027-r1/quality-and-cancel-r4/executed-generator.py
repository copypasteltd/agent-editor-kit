"""Installed C53 fragment rebinding and cancellation after actual CUDA inference."""
from pathlib import Path
import argparse,ctypes,hashlib,json,shutil,subprocess,threading,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
out=BASE/('quality-and-cancel-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
main=json.loads((BASE/'case-complete-r1/verification.json').read_bytes());assert main['status']=='passed'
project=Path(main['project']);work=project.parent;public=Path(main['public']);ff=shutil.which('ffmpeg');assert ff
prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File','C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1']
record=dict(status='running',registered_installed_skill=True,source_fallback=False,fake_worker=False,native_windows=True,
    virtualization=False,human_listening=False,continuous_playback=False,natural_quality_accepted=False,calls=[],checks=[])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save():(out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def check(name,ok):record['checks'].append(dict(name=name,ok=bool(ok)));save();assert ok,name
def run(name,argv,*,input=None,code=0):
    started=time.monotonic();r=subprocess.run(list(map(str,argv)),input=input,capture_output=True,cwd=ROOT,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
    stdout=out/(name+'.stdout.json');stderr=out/(name+'.stderr.txt');stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
    record['calls'].append(dict(name=name,command=list(map(str,argv)),exit_code=r.returncode,seconds=time.monotonic()-started,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)));save()
    print(json.dumps(dict(name=name,exit_code=r.returncode)),flush=True);assert r.returncode==code,(name,r.stdout[-3000:],r.stderr[-1200:]);return r.stdout
def cli(name,*argv):
    v=json.loads(run(name,[*prefix,*argv]));check(name+' actual installed CLI',v['ok'] and v['provenance']['cli_version']=='0.1.43');return v['data']
def json_file(name,v):
    p=work/(name+'.json');p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return p
def owned_pid_exited(pid):
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];k.OpenProcess.restype=ctypes.c_void_p
    k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)];k.CloseHandle.argtypes=[ctypes.c_void_p]
    h=k.OpenProcess(0x1000,False,pid)
    if not h:return ctypes.get_last_error()==87
    try:
        code=ctypes.c_uint32();return bool(k.GetExitCodeProcess(h,ctypes.byref(code))) and code.value!=259
    finally:k.CloseHandle(h)
try:
    adapter_id='df3_final_'+a.run
    cli('register-final','audio','enhancement-adapter','register','--project',project,'--adapter-id',adapter_id,
        '--model-path',ROOT/'product/.runtime/models/deepfilternet3-20261027',
        '--executable','D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe',
        '--evidence',BASE/'conversion.json','--license-spdx','MIT OR Apache-2.0','--creator','DeepFilterNet contributors',
        '--threads','4','--segment-seconds','2','--overlap','.25')
    for old_id,name in (('english_enhanced','english'),('chinese_enhanced','chinese')):
        replay=cli('final-replay-'+name,'audio','enhance','--project',project,'--adapter-id',adapter_id,
            '--recipe-asset-id',old_id,'--asset-id','final_replay_'+name+'_'+a.run)
        master=project/replay['asset']['uri'];original=public/(name+'-enhanced.wav')
        check(name+' final installed inference exactly matches published master WAV',sha(master)==sha(original)
            and replay['generation']['worker']['model']['neural_backend']=='cuda' and replay['generation']['complete_PCM_roundtrip_verified'])
    lib=work/('reusable-denoised-fragment-'+a.run);request=json_file('fragment-save-'+a.run,dict(id='speech_enhanced',version=1,name='Actual CUDA dialogue',sequence_id='seq_main',clip_ids=[main['english_result']['clip']['id']]))
    cli('fragment-save','fragment','save','--project',project,'--library',lib,'--input',request)
    target=work/('fragment-target-'+a.run);cli('fragment-init','project','init',target)
    target_project=json.loads((target/'project.json').read_bytes());target_project['settings']=json.loads((project/'project.json').read_bytes())['settings']
    (target/'project.json').write_text(json.dumps(target_project,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    cli('collision-ingest','media','ingest','--project',target,'--input',public/'chinese-noisy.wav','--asset-id','english_enhanced','--evidence',public/'SOURCE.txt')
    request=json_file('fragment-apply-'+a.run,dict(id='speech_enhanced',version=1,sequence_id='seq_main',track_id='track_video_1',at_tick=0,instance_id='denoise_instance'))
    imported=cli('fragment-apply','fragment','apply','--project',target,'--library',lib,'--input',request)
    p=json.loads((target/'project.json').read_bytes());asset=next(v for v in p['assets'] if v.get('source',{}).get('speech_enhancement'))
    recipe=asset['source']['speech_enhancement'];source=next(v for v in p['assets'] if v['id']==recipe['source_asset_id'])
    check('real fragment asset collision rebinds generated and source IDs',asset['id']!='english_enhanced' and source['id']!=main['source_ids']['english-noisy']
        and source['sha256']==main['english_result']['asset']['source']['speech_enhancement']['source_sha256'])
    check('fragment source and master bytes preserved',sha(target/asset['uri'])==sha(public/'english-enhanced.wav'))
    cli('fragment-validate','validate','--project',target)
    # Long actual model input gives the controller time to cancel after a neural segment.
    data=np.fromfile(work/'decode-english-enhanced.bin',dtype='<f4');data=np.tile(data,30)[:60*48000]
    long_path=work/('long-cancel-source-'+a.run+'.wav')
    run('long-source',[ff,'-nostdin','-v','error','-n','-f','f32le','-ar','48000','-ac','1','-i','pipe:0','-c:a','pcm_f32le',long_path],input=data.tobytes())
    long_id=cli('long-ingest','media','ingest','--project',project,'--input',long_path,'--evidence',public/'SOURCE.txt','--license-spdx','CC-BY-4.0')['asset']['id']
    frozen={str(p.relative_to(project)):sha(p) for p in project.rglob('*.json') if not any(p.is_relative_to(project/d) for d in ('cache','snapshots','validation','operations','renders'))}
    marker=work/('cancel-after-actual-enhancement-'+a.run+'.marker');argv=[*prefix,'audio','enhance','--project',str(project),'--adapter-id',adapter_id,
        '--source-asset-id',long_id,'--asset-id','cancel_unpublished','--cancel-file',str(marker),'--progress','jsonl']
    process=subprocess.Popen(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    stdout=[];stderr=[]
    def drain(stream,parts):
        while block:=stream.read(65536):parts.append(block)
    readers=[threading.Thread(target=drain,args=(process.stdout,stdout)),threading.Thread(target=drain,args=(process.stderr,stderr))]
    for t in readers:t.start()
    trigger=None;started=time.monotonic()
    try:
        while process.poll()is None and time.monotonic()-started<600:
            for path in (project/'cache/managed-jobs').glob('job-*/progress.json'):
                try:v=json.loads(path.read_bytes())
                except (OSError,ValueError):continue
                if v.get('phase')=='neural-enhancement' and 1<=v.get('done',0)<v.get('total',0) and trigger is None:
                    trigger=v;marker.write_text('Cancel only this CUDA enhancement after a completed neural segment.\n',encoding='utf8')
            time.sleep(.025)
        if process.poll()is None:
            marker.write_text('Owned cancellation deadline\n',encoding='utf8');process.wait(timeout=30)
    finally:
        if process.poll()is None:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
        for t in readers:t.join(timeout=20)
        process.stdout.close();process.stderr.close()
    raw=b''.join(stdout);(out/'cancel.stdout.json').write_bytes(raw);(out/'cancel.stderr.jsonl').write_bytes(b''.join(stderr));response=json.loads(raw)
    check('actual CUDA cancellation after completed neural inference',trigger is not None and process.returncode==8 and response['errors'][0]['code']=='CANCELLED')
    check('all frozen project metadata unchanged',all((project/p).is_file() and sha(project/p)==digest for p,digest in frozen.items()))
    check('no half asset and no managed job remains',not(project/'assets/derived/cancel_unpublished.wav').exists() and not list((project/'cache/managed-jobs').glob('job-*')))
    reference=response['errors'][0]['diagnostics'];check('CLI exposes persistent bounded diagnostic',reference['status']=='stored')
    diagnostic=cli('cancel-diagnostic','diagnostics','show','--project',project,'--diagnostic-id',reference['diagnostic_id'])['manifest']
    row=next(p for p in diagnostic['processes'] if p['role']=='worker')
    check('owned Windows worker exited and bounded diagnostic retained',row['state']=='terminated_by_cleanup' and row['final_exit'] is not None
        and row['pid']==trigger['worker_pid'] and owned_pid_exited(trigger['worker_pid']) and diagnostic['progress']['segments_done']>=1)
    check('internal decoder and encoder were not misreported as separately observed children',all(p['state']=='not_started' for p in diagnostic['processes'] if p['role']!='worker'))
    for path in (project/reference['manifest']).parent.iterdir():
        if path.is_file():shutil.copy2(path,out/('retained-'+path.name))
    record.update(status='passed',fragment_generated_id=asset['id'],fragment_source_id=source['id'],fragment_recipe=recipe,
        cancellation_trigger=trigger,cancellation_diagnostic=diagnostic,worker_pid_confirmed_exited=True,
        cancel_elapsed_seconds=time.monotonic()-started,partial_asset_absent=True,metadata_rollback_verified=True)
    save();print(json.dumps(dict(status='passed',fragment_generated_id=asset['id'],real_neural_cancel=True)),flush=True)
except BaseException as exc:record.update(status='failed',error=repr(exc));save();raise
