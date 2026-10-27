"""Retain actual RIFE failure, explicit hold alternative and native cancellation."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,threading,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-interpolation-20261027-r1'
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
out=BASE/('quality-and-cancel-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
main=json.loads((BASE/'case-r1/verification.json').read_bytes());assert main['status']=='passed'
project=Path(main['project']);public=ROOT/'docs/assets/native-interpolation-20261027-r1';work=project.parent
launcher='C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1';ffmpeg=shutil.which('ffmpeg');prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',launcher]
record=dict(status='running',registered_installed_skill=True,source_fallback=False,fake_worker=False,native_windows=True,virtualization=False,calls=[],checks=[],human_listening=False,continuous_playback=False,natural_quality_accepted=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save():(out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def check(name,ok):record['checks'].append(dict(name=name,ok=bool(ok)));save();assert ok,name
def run(name,command,*,binary=False,code=0):
    started=time.monotonic();r=subprocess.run(list(map(str,command)),capture_output=True,cwd=ROOT,timeout=1200,creationflags=subprocess.CREATE_NO_WINDOW)
    stdout=(work if binary else out)/(name+('.bin' if binary else '.stdout.json'));stderr=out/(name+'.stderr.txt');stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
    record['calls'].append(dict(name=name,command=list(map(str,command)),exit_code=r.returncode,seconds=time.monotonic()-started,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)));save()
    print(json.dumps(dict(name=name,exit_code=r.returncode,seconds=time.monotonic()-started)),flush=True)
    assert r.returncode==code,(name,r.stdout[-2500:],r.stderr[-1000:]);return r.stdout
def cli(name,*command):
    v=json.loads(run(name,[*prefix,*command]));check(name+' actual registered CLI',v['ok'] and v['provenance']['cli_version']=='0.1.42');return v['data']
def decode(name,path):return run(name,[ffmpeg,'-v','error','-i',path,'-an','-pix_fmt','rgba','-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
try:
    alternate=cli('explicit-hold','interpolate','generate','--project',project,'--adapter-id','rife425_local','--recipe-asset-id','sintel_4x','--asset-id','sintel_explicit_hold','--cut-after-frame','22','--scene-cut-threshold','0')
    generated=np.frombuffer(decode('hold-rgba',project/alternate['asset']['uri']),np.uint8).reshape(96,180,320,4)
    original=np.frombuffer(decode('reference-rgba',public/'original-reference.mov'),np.uint8).reshape(48,180,320,4)
    bad_master=project/main['natural_result']['asset']['uri'];bad=np.frombuffer(decode('unprotected-rgba',bad_master),np.uint8).reshape(96,180,320,4)
    check('explicit guard holds preceding original at problematic pair',np.array_equal(generated[88],generated[89]) and np.array_equal(generated[88],generated[90]) and np.array_equal(generated[88],generated[91]))
    m=alternate['generation']['worker']['metrics'];check('guard excludes exactly three actual neural forwards',m['cut_after_frames']==[22] and m['flow_forwards']==66)
    truth=original[45,:,:,:3].astype(float);failed=bad[90,:,:,:3].astype(float);guard=generated[90,:,:,:3].astype(float)
    failure_mse=float(((failed-truth)**2).mean());hold_mse=float(((guard-truth)**2).mean());check('local hold reduces measured failure without claiming smooth interpolation',hold_mse<failure_mse)
    sheet=Image.new('RGB',(960,214),(22,26,32));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14);draw=ImageDraw.Draw(sheet)
    for j,(image,label) in enumerate([(truth,'HELD-OUT ORIGINAL'),(failed,'RIFE / failed pair22'),(guard,'EXPLICIT HOLD / step tradeoff')]):
        sheet.paste(Image.fromarray(image.astype('uint8')),(j*320,34));draw.text((j*320+8,8),label,font=font,fill='white')
    sheet.save(public/'failure-and-hold.png')
    run('hold-preview',[ffmpeg,'-v','error','-n','-i',project/alternate['asset']['uri'],'-vf','setpts=4*PTS','-an','-c:v','libx264','-pix_fmt','yuv420p','-crf','18',public/'explicit-hold-slow.mp4'])
    # Cancel only after >=5% emitted frames, beyond original-only first anchor.
    marker=work/'real-interpolation-cancel.marker';before={str(p.relative_to(project)):sha(p) for p in project.rglob('*.json') if not any(p.is_relative_to(project/d) for d in ('cache','snapshots','renders/diagnostics'))}
    command=[*prefix,'interpolate','generate','--project',str(project),'--adapter-id','rife425_local','--recipe-asset-id','sintel_4x','--asset-id','cancel_unpublished',
        '--factor','8','--cancel-file',str(marker),'--progress','jsonl'];started=time.monotonic()
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
            if event.get('stage')=='interpolate.generate' and float(event.get('percent') or 0)>=5 and not triggered.is_set():
                marker.write_text('Cancel only this actual interpolation after neural frames.\n',encoding='utf8');triggered.set()
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
    response=json.loads(raw_stdout);check('real CUDA cancellation follows emitted neural frames',triggered.is_set() and process.returncode==8 and response['errors'][0]['code']=='CANCELLED')
    after={str(p.relative_to(project)):sha(p) for p in project.rglob('*.json') if not any(p.is_relative_to(project/d) for d in ('cache','snapshots','renders/diagnostics'))}
    check('cancellation rolls back all project metadata',before==after);check('no partial asset or owned workspace remains',not(project/'assets/derived/cancel_unpublished.mov').exists() and not list((project/'cache/managed-jobs').glob('job-*')))
    diagnostic=response['errors'][0].get('diagnostics',{});check('cancellation retains actual bounded diagnostic',diagnostic.get('status')=='stored')
    diagnostics=cli('cancel-diagnostic','diagnostics','show','--project',project,'--diagnostic-id',diagnostic['diagnostic_id'])
    processes=diagnostics['manifest']['processes'];check('all three owned native children exited',len(processes)==3 and all(p.get('state') in {'exited','terminated_by_cleanup'} and p.get('final_exit') is not None for p in processes))
    record.update(status='passed',actual_failure_pair=22,unguarded_MSE=failure_mse,explicit_hold_MSE=hold_mse,guard_forward_count=66,
        tradeoff='explicit hold removes this ghosting by freezing the interval; it does not solve natural interpolation or semantic scene detection',
        real_cancel_after_neural_frames=True,cancel_seconds=time.monotonic()-started,cancel_progress=events,cancellation_diagnostic=diagnostics,
        hold_recipe=alternate['asset']['source']['interpolation'],public_files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in (public/'failure-and-hold.png',public/'explicit-hold-slow.mp4')])
    save();print(json.dumps({k:v for k,v in record.items() if k in ('status','actual_failure_pair','unguarded_MSE','explicit_hold_MSE','real_cancel_after_neural_frames')}),flush=True)
except BaseException as exc:record.update(status='failed',error=repr(exc));save();raise
