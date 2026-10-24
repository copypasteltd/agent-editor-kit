"""Retain real native model, installed-release and registered-Skill evidence."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ENGINE = 'torchaudio-hdemucs-four-stem-local-v1'
ROLES = ('drums','bass','other','vocals')
RATE = 44100
HEAVY = Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe')
MODEL = ROOT/'product/.runtime/models/audio/hdemucs_high_musdbhq_only.pt'
PROOF = MODEL.with_suffix('.evidence.json')


def sha(path): return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def decode(path, *, start=None, seconds=None):
    command=['ffmpeg','-nostdin','-hide_banner','-loglevel','error']
    if start is not None: command += ['-ss',str(start)]
    command += ['-i',str(path)]
    if seconds is not None: command += ['-t',str(seconds)]
    result=subprocess.run([*command,'-ar',str(RATE),'-ac','2','-f','f32le','pipe:1'],capture_output=True,check=True,timeout=120)
    return np.frombuffer(result.stdout,dtype='<f4').reshape(-1,2).copy()
def encode(path,data):
    subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','f32le','-ar',str(RATE),'-ac','2','-i','pipe:0',
        '-c:a','pcm_f32le',str(path)],input=np.asarray(data,dtype='<f4').tobytes(),capture_output=True,check=True,timeout=120)
def si_sdr(reference,estimate):
    ref=reference.astype(np.float64).reshape(-1); est=estimate.astype(np.float64).reshape(-1)
    ref-=ref.mean(); est-=est.mean()
    projection=ref*(float(ref@est)/max(1e-15,float(ref@ref)))
    return 10*math.log10(max(1e-15,float(projection@projection))/max(1e-15,float((est-projection)@(est-projection))))


def prepare(output):
    if output.exists(): raise ValueError('Existing fixture is preserved')
    output.mkdir(parents=True)
    count=6*RATE; t=np.arange(count)/RATE
    voice=decode(ROOT/'workspace/separation-smoke-20261016-b/reference-vocals.wav')[:count]
    bass=np.stack([.12*np.sin(2*np.pi*82.405*t+phase)+.025*np.sin(2*np.pi*164.81*t+phase) for phase in (0,.12)],axis=1)
    other=np.zeros((count,2),np.float64)
    for channel in range(2):
        for frequency in (220,261.63,329.63,392):
            other[:,channel]+=.07*np.sin(2*np.pi*frequency*t+channel*.25)*(1+.2*np.sin(2*np.pi*.75*t))
    drums=np.zeros((count,2),np.float64); rng=np.random.default_rng(20261025)
    for at in np.arange(0,6,.5):
        start=round(at*RATE); length=min(count-start,round(.18*RATE)); elapsed=np.arange(length)/RATE
        hit=.28*rng.normal(0,1,length)*np.exp(-elapsed/.025)+.2*np.sin(2*np.pi*(70*elapsed-22*elapsed**2))*np.exp(-elapsed/.04)
        drums[start:start+length]+=hit[:,None]
    sources=dict(drums=drums,bass=bass,other=other,vocals=voice.astype(np.float64))
    # Predetermined equal RMS: never alter levels based on model predictions.
    for role,value in sources.items(): sources[role]=value*(.04/max(1e-8,float(np.sqrt(np.mean(value**2)))))
    mixture=sum(sources.values()); gain=min(1.,.9/float(np.abs(mixture).max()))
    for role in ROLES: encode(output/(role+'.wav'),sources[role]*gain)
    encode(output/'mixture.wav',mixture*gain)
    catalog=json.loads((ROOT/'product/src/ai_ad_editor/material_data/catalog.json').read_text('utf-8'))
    stock=next(r for r in catalog['records'] if r['collection_id']=='oga-mindstream')
    collection=next(r for r in catalog['collections'] if r['id']==stock['collection_id'])
    stock_path=ROOT/'product/src/ai_ad_editor/material_data'/stock['path']
    assert sha(stock_path)=='sha256:'+stock['sha256']
    natural=decode(stock_path,start=20,seconds=6); assert len(natural)==count
    encode(output/'natural-music.wav',natural)
    record=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),samples=count,sample_rate=RATE,seed=20261025,
        fixture_kind='controlled existing Chinese speech plus independently synthesized drums/bass/chords; not natural multitrack truth',
        speech_source=dict(path='workspace/separation-smoke-20261016-b/reference-vocals.wav',
            sha256=sha(ROOT/'workspace/separation-smoke-20261016-b/reference-vocals.wav'),rights='unverified; internal validation only'),
        natural_music=dict(record=stock,collection=collection,source_start_seconds=20,duration_seconds=6,
            ground_truth_stems=False,rights='input CC0; model license remains unverified'),
        gates=dict(all_four_stem_si_sdr_improvement_db_min=3.,cpu_gpu_max_abs_error_max=.005,
            cpu_gpu_rms_error_max=.0001,raw_sum='diagnostic only: unprojected independent estimates',
            natural_quality='no per-stem truth; no quality acceptance or human listening inferred'),
        files={path.name:dict(sha256=sha(path),bytes=path.stat().st_size) for path in output.glob('*.wav')},
        model=dict(path=str(MODEL),sha256=sha(MODEL),evidence_sha256=sha(PROOF),license_status='unverified'),
        public_audio_redistribution=False)
    write(output/'frozen.json',record)
    print(json.dumps(dict(fixture=str(output),sha256=sha(output/'frozen.json'))))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',type=Path)
    p.add_argument('--fixture',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--evidence',type=Path)
    p.add_argument('--installed',type=Path)
    p.add_argument('--skill',type=Path)
    p.add_argument('--devices',nargs='+',choices=('cpu','cuda','auto'),default=['cpu','cuda'])
    p.add_argument('--skip-natural',action='store_true')
    p.add_argument('--skip-roundtrip',action='store_true')
    args=p.parse_args()
    if args.prepare: prepare(args.prepare.resolve()); return 0
    assert args.fixture and args.output and args.evidence
    fixture=args.fixture.resolve(strict=True); record=json.loads((fixture/'frozen.json').read_text('utf-8'))
    for name,entry in record['files'].items(): assert sha(fixture/name)==entry['sha256']
    assert record['model']['sha256']==sha(MODEL)
    output=args.output.resolve(); evidence=args.evidence.resolve()
    assert not output.exists() and not evidence.exists(),'Use new output/evidence directories'
    output.mkdir(parents=True); evidence.mkdir(parents=True)
    if args.skill:
        command=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(args.skill.resolve(strict=True))]
        mode='actual registered Skill' if str(args.skill).startswith('C:') else 'explicit Skill kit'
    elif args.installed:
        command=[sys.executable,'-I','-S','-B','-X','utf8',str(args.installed.resolve(strict=True)/'run.py')]; mode='explicit installed release'
    else:
        bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())'
        command=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,str(ROOT/'product/src')]; mode='explicit source development'
    checks=[]
    def invoke(*argv,expected=0):
        at=time.monotonic(); cmd=[*command,*map(str,argv)]
        result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1800)
        number=len(checks)+1; name=f'{number:02d}'
        (evidence/(name+'-stdout.json')).write_text(result.stdout,encoding='utf-8',newline='\n')
        (evidence/(name+'-stderr.txt')).write_text(result.stderr,encoding='utf-8',newline='\n')
        response=json.loads(result.stdout)
        check=dict(argv=list(map(str,argv)),exit_code=result.returncode,command=response['command'],status=response['status'],
            seconds=time.monotonic()-at,expected_exit_code=expected,stdout_sha256=sha(evidence/(name+'-stdout.json')))
        checks.append(check); write(evidence/'calls.json',checks)
        print(json.dumps({k:check[k] for k in ('command','status','exit_code','seconds')}),flush=True)
        assert result.returncode==expected,(cmd,response)
        assert response['ok']==(expected==0),response
        return response
    version=invoke('version'); project=output/'中文 四轨工程'
    invoke('project','init',project)
    asset=invoke('media','ingest','--project',project,'--input',fixture/'mixture.wav','--asset-id','controlled_mix',
                 '--evidence',fixture/'frozen.json')['data']['asset']['id']
    invoke('audio','adapter','register','--project',project,'--adapter-id','four','--engine',ENGINE,
        '--model-path',MODEL,'--executable',HEAVY,'--evidence',PROOF,'--device','auto','--threads','4','--segment-seconds','4','--overlap','.25')
    invoke('audio','adapter','inspect','--project',project,'--adapter-id','four')
    results={}; decoded={}
    mixture=decode(fixture/'mixture.wav')
    for device in args.devices:
        cmd=['audio','separate-stems','--project',project,'--asset-id',asset,'--adapter-id','four','--prefix',device,
            '--device',device,'--apply','--sample-rate','44100']
        invoke(*cmd,'--dry-run')
        value=invoke(*cmd)['data']; worker=value['separation']['worker']
        if device=='cuda': assert worker['device']=='cuda' and worker['peak_cuda_bytes']>0
        if device=='cpu': assert worker['device']=='cpu'
        assert worker['metrics']['model_calls']>=1 and not worker['blocked_network_events']
        scores={}; decoded[device]={}
        for role in ROLES:
            estimate=decode(project/value['assets'][role]['uri']); decoded[device][role]=estimate
            truth=decode(fixture/(role+'.wav')); assert estimate.shape==truth.shape==mixture.shape
            baseline=si_sdr(truth,mixture); score=si_sdr(truth,estimate)
            scores[role]=dict(si_sdr_db=score,baseline_si_sdr_db=baseline,improvement_db=score-baseline,
                target_improvement_db=record['gates']['all_four_stem_si_sdr_improvement_db_min'],
                passed=score-baseline>=record['gates']['all_four_stem_si_sdr_improvement_db_min'])
        results[device]=dict(scores=scores,all_four_quality_passed=all(row['passed'] for row in scores.values()),
            worker=worker,device_selection=value['separation']['device_selection'],assets=value['assets'],generated_tracks=value['generated_tracks'])
    comparison={}
    if 'cpu' in decoded and 'cuda' in decoded:
        for role in ROLES:
            difference=decoded['cpu'][role].astype(np.float64)-decoded['cuda'][role]
            peak=float(np.abs(difference).max()); rms=float(np.sqrt(np.mean(difference**2)))
            comparison[role]=dict(max_abs=peak,rms=rms,passed=peak<=record['gates']['cpu_gpu_max_abs_error_max'] and rms<=record['gates']['cpu_gpu_rms_error_max'])
    natural_result=None
    if not args.skip_natural:
        natural=invoke('media','ingest','--project',project,'--input',fixture/'natural-music.wav','--asset-id','natural_music',
            '--license-spdx','CC0-1.0','--verification-status','verified','--evidence',fixture/'frozen.json')['data']['asset']['id']
        value=invoke('audio','separate-stems','--project',project,'--asset-id',natural,'--adapter-id','four','--prefix','natural',
                     '--device','auto')['data']
        natural_result=dict(worker=value['separation']['worker'],assets=value['assets'],device_selection=value['separation']['device_selection'],
            quality='not accepted: no independent four-stem ground truth or listening',source=record['natural_music'])
    # Original tracks remain, so choose one actual four-track mix explicitly.
    document=json.loads((project/'project.json').read_text('utf-8'))
    selected='cuda' if 'cuda' in args.devices else args.devices[0]
    operations=[dict(op='update_track',track_id=track['id'],patch=dict(muted=not track['id'].startswith('track_'+selected+'_')))
                for track in document['sequences'][0]['tracks'] if track['kind']=='audio']
    # Use the product edit operation rather than silently modifying project JSON.
    edit=output/'select-tracks.json'; write(edit,dict(operations=operations))
    invoke('timeline','compose','--project',project,'--input',edit)
    invoke('validate','--project',project); invoke('policy','audit','--project',project)
    rights=invoke('rights','check','--project',project,expected=7)
    roundtrip=None
    if not args.skip_roundtrip:
        package=output/'four-stems.aevpkg.zip'
        invoke('convert','export','--project',project,'--target-format','package','--output',package)
        restored=output/'往返 工程'
        invoke('convert','import','--input',package,'--output',restored)
        invoke('validate','--project',restored)
        before=json.loads((project/'project.json').read_text('utf-8')); after=json.loads((restored/'project.json').read_text('utf-8'))
        for item in before['assets']:
            match=next(row for row in after['assets'] if row['id']==item['id'])
            assert sha(project/item['uri'])==sha(restored/match['uri'])==item['sha256']
        assert before['sequences']==after['sequences']
        roundtrip=dict(archive_sha256=sha(package),asset_count=len(before['assets']),sequences_exact=True)
    summary=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),mode=mode,version=version['data'],
        command=command,project=str(project),fixture_sha256=sha(fixture/'frozen.json'),calls=checks,
        controlled=results,cpu_gpu=comparison,natural=natural_result,roundtrip=roundtrip,
        rights_check=rights['data'],quality_all_controlled_passed=all(row['all_four_quality_passed'] for row in results.values()),
        runtime_network='disabled',public_audio_redistribution=False,human_listening=False,full_G17_closed=False)
    write(evidence/'verification.json',summary)
    print(json.dumps(dict(evidence=str(evidence),calls=len(checks),quality_all_controlled_passed=summary['quality_all_controlled_passed'])),flush=True)
    return 0


if __name__=='__main__': raise SystemExit(main())
