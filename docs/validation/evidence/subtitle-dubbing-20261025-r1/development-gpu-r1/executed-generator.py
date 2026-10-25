"""Run actual native OPUS/Kokoro batches; keep generated voices local pending review."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',type=Path,required=True)
    parser.add_argument('--launcher',type=Path)
    parser.add_argument('--label',required=True)
    parser.add_argument('--device',choices=['cpu','cuda'],required=True)
    parser.add_argument('--basic-only',action='store_true')
    args=parser.parse_args()
    site=args.site.resolve(strict=True)
    assert args.label.replace('-','').isalnum()
    output=ROOT/'docs/validation/evidence/subtitle-dubbing-20261025-r1'/args.label
    work=ROOT/'local/agent-ffmpeg/dubbing-20261025-r1'/args.label
    output.mkdir(parents=True,exist_ok=False)
    work.mkdir(parents=True,exist_ok=False)
    (output/'logs').mkdir()
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    command=([str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(args.launcher.resolve(strict=True))] if args.launcher else
        [sys.executable,'-E','-B','-u','-X','utf8','-c','import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())',str(site)])
    env=dict(os.environ,AEK_COMMUNITY_DEVICE_CONFIG=str(ROOT/'local/agent-ffmpeg/community-runtime.json'),
        PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
    frozen=lambda:[dict(path=str(path.relative_to(site)),sha256=sha(path)) for path in sorted((site/'ai_ad_editor').glob('*.py'))]
    record=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),site=str(site),
        launcher=str(args.launcher) if args.launcher else None,device=args.device,work=str(work),
        frozen_before=frozen(),calls=[],cases=[],new_model_inference=True,native_windows=True,
        virtualization=False,browser_ui=False,human_listening=False,human_semantic_acceptance=False,
        raw_voice_publication=False,generator_sha256=sha(Path(__file__)))
    with zipfile.ZipFile(output/'executed-product-python.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((site/'ai_ad_editor').glob('*.py')):
            archive.write(path,path.relative_to(site))
    def run(name,argv,expected=0):
        started=time.monotonic()
        result=subprocess.run([*command,*map(str,argv)],cwd=ROOT,env=env,capture_output=True,timeout=1200,
            creationflags=subprocess.CREATE_NO_WINDOW)
        stdout,stderr=output/'logs'/(name+'.stdout.json'),output/'logs'/(name+'.stderr.txt')
        stdout.write_bytes(result.stdout);stderr.write_bytes(result.stderr)
        response=json.loads(result.stdout.decode('utf-8-sig'))
        call=dict(name=name,argv=[*command,*map(str,argv)],exit_code=result.returncode,ok=response.get('ok'),
            status=response.get('status'),elapsed_seconds=time.monotonic()-started,
            stdout_sha256=sha(stdout),stderr_sha256=sha(stderr))
        record['calls'].append(call)
        write(output/'progress.json',dict(calls=record['calls'],last=name))
        print(json.dumps(dict(name=name,exit_code=result.returncode,elapsed_seconds=call['elapsed_seconds'])),flush=True)
        assert result.returncode==expected,(name,result.returncode,response)
        return response
    def srt(cues):
        def clock(ms):
            return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
        return '\n\n'.join(f'{i+1}\n{clock(start)} --> {clock(end)}\n{text}' for i,(start,end,text) in enumerate(cues))+'\n'
    source_language,target_language=('en','zh-Hans') if args.device=='cuda' else ('zh-Hans','en')
    texts=(['Keep every original clip.','Choose a clear product story.','Create another version in seconds.'] if args.device=='cuda'
        else ['保留每一个原始片段。','选择清楚的产品故事。','创建另一个版本。'])
    base_cues=[(0,6000,texts[0]),(6500,12500,texts[1]),(13000,19000,texts[2])]
    def prepare(name,cues,apply=False,mix=False):
        project=work/name
        source=output/(name+'.srt')
        source.write_text(srt(cues),encoding='utf-8')
        run(name+'-init',['project','init',project,'--name','Subtitle dubbing acceptance '+name])
        flags=[]
        if apply:
            fonts=run(name+'-fonts',['materials','list','--kind','font','--limit','2'])['data']['records']
            run(name+'-font',['materials','ingest','--project',project,'--id',fonts[0]['id'],'--asset-id','caption_font'])
            path=project/'project.json'
            payload=json.loads(path.read_text('utf-8'))
            payload['settings']['canvas'].update(width=1280,height=720)
            payload['sequences'][0]['tracks'].append(dict(id='captions',kind='subtitle',order=0,clips=[],locked=False,muted=False))
            if mix:
                for track in payload['sequences'][0]['tracks']:
                    track['overlap_policy']='allow'
            write(path,payload)  # Explicit fixture setup, not a dubbing implementation shortcut.
            flags=['--apply','--audio-track-id','track_audio_1','--subtitle-track-id','captions','--font-asset-id','caption_font']
        return project,['dub','subtitles','--project',project,'--input',source,'--from',source_language,'--to',target_language,
            '--device',args.device,*flags]
    def metadata(project):
        return {name:sha(project/name) for name in ('project.json','rights-ledger.json')}
    def check_success(name,response):
        data=response['data']
        report_path=Path(data['report'])
        report=json.loads(report_path.read_text('utf-8'))
        verified=[]
        for cue in report['cues']:
            for index,attempt in enumerate(cue['attempts']):
                # Derive the project from the returned report, independently of staging paths.
                project=report_path
                while project.name!='assets':
                    project=project.parent
                path=project.parent/attempt['output']
                with wave.open(str(path),'rb') as wav:
                    frames=wav.getnframes()
                    assert wav.getframerate()==24000 and wav.getnchannels()==1 and wav.getsampwidth()==2
                    pcm=wav.readframes(frames)
                    assert len(pcm)==frames*2 and frames==attempt['samples']
                assert 'sha256:'+sha(path)==attempt['sha256']
                if index==len(cue['attempts'])-1:
                    assert frames<=cue['slot_samples']
                verified.append(dict(cue=cue['index'],attempt=index+1,speed=attempt['speed'],samples=frames,
                    pcm_sha256=hashlib.sha256(pcm).hexdigest(),wave_sha256=sha(path)))
        assert data['model_initializations']==1
        assert all(device['selected']==args.device for device in data['devices'].values())
        assert not report['truncation'] and report['timing_scope']=='cue_windows_not_phonetic_alignment_or_lip_sync'
        record['cases'].append(dict(name=name,status='passed',report=str(report_path),report_sha256=sha(report_path),
            cue_count=len(report['cues']),generations=data['total_generations'],voice_model_initializations=1,
            actual_successful_model_workers=len(report['translation_attempts'])+len(report['voice_attempts']),
            wave_checks=verified,devices=data['devices']))
        return report
    try:
        project,argv=prepare('basic',base_cues,apply=True)
        mapping=output/'basic-voices.json'
        mapping.write_text(json.dumps({'cues':{'2':'zf_002','3':'zf_003'} if args.device=='cuda' else {'2':'af_sol','3':'bf_vale'}}),encoding='utf-8')
        argv.extend(['--voice-map',mapping])
        before=metadata(project)
        planned=run('basic-dry-run',[*argv,'--dry-run'])
        assert planned['status']=='planned' and not planned['data']['actual_audio_duration_known'] and before==metadata(project)
        basic=check_success('basic',run('basic-generate',argv))
        run('basic-validate',['validate','--project',project])
        replay_key='native-batch-replay'
        replay_project,replay_argv=prepare('replay',base_cues[:1])
        first=run('replay-first',[*replay_argv,'--idempotency-key',replay_key])
        second=run('replay-second',[*replay_argv,'--idempotency-key',replay_key])
        assert first['data']['report']==second['data']['report']
        assert any(w['code']=='IDEMPOTENT_REPLAY' for w in second['warnings'])
        check_success('replay',first)
        if not args.basic_only:
            for name,fit,maximum in [('overflow','reject',1.5),('speed-cap','speed',1.1)]:
                failed,command_args=prepare(name,[(0,1,texts[0])])
                before=metadata(failed)
                result=run(name,[*command_args,'--fit',fit,'--max-speed',str(maximum)],expected=2)
                error=result['errors'][0]
                assert error['code']=='DUBBING_CUE_OVERFLOW' and metadata(failed)==before
                failure_path=Path(error['path'])
                failure=json.loads(failure_path.read_text('utf-8'))
                waves=list(failure_path.parent.rglob('*.wav'))
                assert waves and all(path.stat().st_size>44 for path in waves)
                assert not any(path.is_file() for path in (failed/'assets/derived').rglob('*'))
                record['cases'].append(dict(name=name,status='expected-overflow',metadata_unchanged=True,
                    failure_report=str(failure_path),failure_report_sha256=sha(failure_path),preserved_waves=len(waves),
                    measured=failure['measured']))
                run(name+'-cleanup-preview',['project','recover','--project',failed,'--cleanup-jobs','--dry-run'])
            natural=basic['cues'][0]['attempts'][0]['samples']
            slot_ms=int(natural/24*.8)
            speed_project,speed_argv=prepare('speed',[(0,slot_ms,texts[0])])
            speed=check_success('speed',run('speed',[*speed_argv,'--fit','speed','--max-speed','1.6']))
            assert len(speed['cues'][0]['attempts'])>=2
            assert speed['cues'][0]['attempts'][0]['samples']>slot_ms*24
            mixed,mix_argv=prepare('mix',[(0,6000,texts[0]),(1000,7000,texts[1])],apply=True,mix=True)
            check_success('mix',run('mix',[*mix_argv,'--overlap-policy','mix']))
            run('mix-validate',['validate','--project',mixed])
        record['status']='passed-with-natural-quality-and-rights-review-open'
    except BaseException as error:
        record.update(status='failed',error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after']
        write(output/'verification.json',record)
        print(json.dumps({key:record[key] for key in ('status','frozen_equal','finished_at_utc')}) ,flush=True)
    assert record['frozen_equal']


if __name__=='__main__':
    main()
