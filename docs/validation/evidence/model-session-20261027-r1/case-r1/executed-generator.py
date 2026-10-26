"""C44: installed real CUDA cold/warm model reuse, deterministic reset and cancellation.

Model output publication rights remain unverified. Outputs stay in local workspace;
only numeric evidence and original CC0 condition images are published.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/model-session-20261027-r1'
PYTHON='C:/Python313/python.exe'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--installation-run',default='r2')
    args=parser.parse_args();assert all(x.replace('-','').isalnum() for x in (args.run,args.installation_run))
    out=BASE/('case-'+args.run);out.mkdir(exist_ok=False)
    work=ROOT/'workspace'/('model-session-20261027-'+args.run);work.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    installed=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.32'/('final-'+args.installation_run)/'installed'
    prefix=[PYTHON,'-I','-S','-B','-u','-X','utf8',str(installed/'run.py')]
    record=dict(status='running',at_utc=datetime.now(timezone.utc).isoformat(),cli_version='0.1.34',installed=str(installed),
        source_fallback=False,native_windows=True,virtualization=False,synthetic_model=False,models_downloaded=False,
        other_user_processes_modified=False,model_output_publication_accepted=False,natural_quality_accepted=False,
        continuous_playback=False,human_listening=False,calls=[],checks=[],jobs=[])
    project=work/'可编辑 常驻模型工程';session_id=None
    def save(): (out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,ok):
        record['checks'].append(dict(name=name,ok=bool(ok)));save();assert ok,name
    def run(name,argv,*,code=0,timeout=3600,binary=False,cancel=False):
        argv=list(map(str,argv));started=time.monotonic();cancel_sent=False;progress_record=None
        destination=(work if binary else out)/(name+('.bin' if binary else '.stdout.json'));error=out/(name+'.stderr.log')
        with destination.open('xb') as stdout,error.open('xb') as stderr:
            process=subprocess.Popen(argv,cwd=ROOT,stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                while process.poll() is None:
                    if time.monotonic()-started>timeout:raise TimeoutError(name)
                    if cancel and not cancel_sent:
                        for path in (project/'cache/managed-jobs').glob('job-*/pipeline/rgba-*/progress.json'):
                            try:progress=json.loads(path.read_bytes())
                            except (OSError,ValueError):continue
                            if progress.get('stage','').startswith('joint-video-denoising-step-'):
                                (project/'cancel-live.flag').write_text('cancel after actual denoising step\n',encoding='utf8')
                                cancel_sent=True;progress_record=progress;break
                    time.sleep(.1)
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=20)
        data=destination.read_bytes()
        row=dict(name=name,argv=argv,exit_code=process.returncode,expected_exit_code=code,seconds=time.monotonic()-started,
            stdout_sha256=sha(destination),stderr_sha256=sha(error))
        if cancel:row.update(cancel_sent_after_denoising=cancel_sent,progress_when_cancelled=progress_record)
        record['calls'].append(row);save();print(json.dumps(row,ensure_ascii=False),flush=True)
        assert process.returncode==code,(name,data[-5000:],error.read_bytes()[-3000:])
        if cancel:check('actual denoising started before cancellation',cancel_sent)
        return data
    def cli(name,*arguments,code=0,timeout=3600,cancel=False):
        result=json.loads(run(name,[*prefix,*arguments],code=code,timeout=timeout,cancel=cancel))
        assert result['ok']==(code==0),result
        return result
    try:
        frozen={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        check('230 installed source files exactly match source',len(frozen)==230 and all(sha(installed/'site/ai_ad_editor'/n)==s for n,s in frozen.items()))
        check('installed version',cli('version','version')['data']['cli_version']=='0.1.34')
        run('gpu-before',['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.used','--format=csv,noheader'])
        cli('init','project','init',project)
        author=json.loads((project/'project.json').read_bytes());author['settings']['canvas'].update(width=256,height=144,fps=dict(num=12,den=1))
        (project/'project.json').write_text(json.dumps(author,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        conditions=ROOT/'docs/assets/video-generation-20261026-r1'
        evidence=work/'conditions-rights.txt';evidence.write_text('Reuse original self-authored C43 geometric bottle conditions, CC0-1.0. No third-party images or voices.\n',encoding='utf8')
        images={}
        for name in ('first','last'):
            images[name]=cli('ingest-'+name,'media','ingest','--project',project,'--input',conditions/(name+'.png'),
                '--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','internal','--permitted-use','commercial_ad',
                '--evidence',evidence)['data']['asset']['id']
        prior=json.loads((ROOT/'docs/validation/evidence/video-generation-20261026-r1/case-r1/verification.json').read_bytes())['model_adapter']
        adapter=cli('register-vace','media','adapter','register','--project',project,'--adapter-id','vace_session',
            '--engine',prior['engine'],'--model-path',prior['model_path'],'--executable',prior['executable'],
            '--evidence',next(a['path'] for a in prior['artifacts'] if a['role']=='evidence'),'--device','cuda',
            '--license-spdx','Apache-2.0','--verification-status','unverified','--permitted-use','internal')['data']['adapter']
        record['adapter']=adapter;save()
        started=cli('session-start','media','model-session','start','--project',project,'--adapter-id',adapter['adapter_id'],
            '--idle-seconds','300','--lifetime-seconds','14400','--max-jobs','8','--startup-timeout-seconds','1800')['data']
        session_id=started['session_id'];record['session_start']=started;save()
        check('resident model startup hashes and locks every adapter artifact',
            started['state']['artifact_verification']['files_hashed']==len(adapter['artifacts']) and
            started['state']['artifact_verification']['bytes_hashed']==sum(a['bytes'] for a in adapter['artifacts']))
        prompt='An amber glass perfume bottle with a black cap stands on a blue tabletop in a quiet studio. Soft side lighting, realistic glass reflections. A slow smooth camera move to the right. The bottle remains upright. No text, no people.'
        def generate(asset,mode,index,seed=240):
            arguments=['media','generate','--project',project,'--adapter-id',adapter['adapter_id'],'--asset-id',asset,
                '--model-session',session_id,'--mode',mode,'--width','256','--height','144','--frames','17','--fps','12',
                '--image-fit','reject','--prompt',prompt,'--negative-prompt','watermark, text, people, distorted objects, jitter',
                '--seed',str(seed),'--inference-steps','18','--guidance-scale','5','--flow-shift','3','--window-frames','17',
                '--window-overlap','4','--apply','--track-id','track_video_1','--timeline-start-seconds',str(index*17/12),'--timeout-seconds','1800']
            if mode in ('image-to-video','first-last-to-video'):arguments+=['--first-asset-id',images['first']]
            if mode=='first-last-to-video':arguments+=['--last-asset-id',images['last']]
            return arguments
        arrays=[]
        for i,(asset,mode,seed) in enumerate([('cold','first-last-to-video',240),('warm-replay','first-last-to-video',240),('warm-new','image-to-video',241)]):
            data=cli(asset,*generate(asset,mode,i,seed))['data'];result=data['generation']['result'];worker=result['worker'];execution=worker['model_execution']
            movie=project/data['asset']['uri'];raw=run(asset+'-decode',['ffmpeg','-nostdin','-v','error','-i',movie,'-an','-pix_fmt','rgba',
                '-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
            pixels=np.frombuffer(raw,np.uint8).reshape(17,144,256,4);arrays.append(pixels)
            check(asset+' actual CUDA model and independent complete RGBA hash',worker['providers']==['torch-cuda'] and worker['model_loaded'] is True
                and worker['metrics']['model_calls']==1 and execution['window_input_shapes']==[[17,144,256]]
                and 'sha256:'+hashlib.sha256(raw).hexdigest()==worker['metrics']['rgba_sha256'])
            check(asset+' reuses model exactly once and resets per-job metrics',execution['resident_model']['reused']==bool(i)
                and execution['resident_model']['predictor_loads']==1 and execution['resident_model']['inference_job']==i+1
                and len(execution['window_seconds'])==1 and execution['gpu_admission']['windows']['count']==1)
            check(asset+' overlapping parent locks avoid repeated model hashes',result['artifact_verification']['bytes_hashed']==0
                and result['artifact_verification']['session_attested_files']==len(adapter['artifacts'])
                and worker['artifact_verification']['bytes_hashed']==sum(a['bytes'] for a in adapter['artifacts']))
            preview=work/(asset+'.mp4');run(asset+'-preview',['ffmpeg','-nostdin','-v','error','-n','-i',movie,'-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',preview])
            views=[Image.fromarray(frame[:,:,:3]) for frame in pixels]
            durations=[(round((j+1)*100/12)-round(j*100/12))*10 for j in range(17)]
            views[0].save(work/(asset+'.gif'),save_all=True,append_images=views[1:],duration=durations,loop=0,disposal=2)
            record['jobs'].append(dict(asset_id=asset,mode=mode,seed=seed,output=str(movie),sha256=sha(movie),
                rgba_sha256=worker['metrics']['rgba_sha256'],elapsed_seconds=result['elapsed_seconds'],
                model_execution=execution,cuda_peak_allocated_bytes=worker['cuda_peak_allocated_bytes'],
                endpoint_checks=data['generation']['endpoint_checks'],preview=str(preview)));save()
        diff=arrays[0].astype(np.int16)-arrays[1].astype(np.int16)
        record['replay_comparison']=dict(frames=17,equal=not np.any(diff),changed_channels=int(np.count_nonzero(diff)),maximum_absolute_difference=int(np.abs(diff).max()))
        check('same-seed warm replay resets scheduler and is pixel-identical on this host',record['replay_comparison']['equal'])
        run('gpu-resident',['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.used','--format=csv,noheader'])
        status=cli('session-after-three','media','model-session','status','--project',project,'--session-id',session_id)['data']
        check('one live process completes all three jobs',status['live'] and status['completed_jobs']==3 and status['model_loaded'])
        before={name:(project/name).read_bytes() for name in ('project.json','rights-ledger.json')}
        changed=generate('different-prompt','first-last-to-video',3);changed[changed.index('--prompt')+1]='A different scene.'
        cli('changed-prompt-rejected',*changed,code=10)
        check('different prompt does not mutate project or unload resident model',all((project/n).read_bytes()==b for n,b in before.items())
              and cli('session-after-prompt-reject','media','model-session','status','--project',project,'--session-id',session_id)['data']['live'])
        cancellation=generate('cancelled-live','first-last-to-video',3,242)+['--cancel-file',str(project/'cancel-live.flag')]
        cli('actual-denoise-cancelled',*cancellation,code=8,cancel=True)
        check('cancelled inference never publishes project or asset',all((project/n).read_bytes()==b for n,b in before.items())
            and not (project/'assets/derived/cancelled-live.mov').exists())
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            state=cli('after-cancel-status-'+str(len(record['calls'])),'media','model-session','status','--project',project,'--session-id',session_id)['data']
            if not state['live']:break
            time.sleep(.2)
        check('cancelled actual CUDA session has exited',not state['live'])
        record['stopped_session']=state
        run('gpu-after-cancel',['nvidia-smi','--query-gpu=uuid,name,memory.total,memory.used','--format=csv,noheader'])
        check('editable project validates after cancellation',cli('validate','validate','--project',project)['data']['ok'])
        cli('rights-expected-reject','rights','check','--project',project,code=7)
        cli('package','convert','export','--project',project,'--target-format','package','--output',work/'editable-resident-videos.aevpkg.zip')
        check('source and installed product files remain frozen',frozen=={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
              and all(sha(installed/'site/ai_ad_editor'/n)==s for n,s in frozen.items()))
        cold=next(c['seconds'] for c in record['calls'] if c['name']=='cold')
        warm=[c['seconds'] for c in record['calls'] if c['name'] in ('warm-replay','warm-new')]
        record.update(status='passed_actual_cuda_resident_reuse_and_cancel',project=str(project),
            cold_cli_seconds=cold,warm_cli_seconds=warm,cold_to_warm_replay_ratio=cold/warm[0],
            startup_cost_accounted_separately=True,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save();print(json.dumps(dict(status=record['status'],cold_cli_seconds=cold,warm_cli_seconds=warm)),flush=True)
    except BaseException as exc:
        record.update(status='failed',error=repr(exc));save()
        if session_id:
            try:cli('failure-cleanup-stop','media','model-session','stop','--project',project,'--session-id',session_id)
            except Exception:pass
        raise


if __name__=='__main__':main()
