"""Actual installed failure controls, rendered mix and editable roundtrip."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from verify_four_stems_20261025 import ROOT, ROLES, sha, write


def pcm(path,rate=48000):
    result=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-i',str(path),'-vn','-ac','2','-ar',str(rate),
        '-f','f32le','pipe:1'],capture_output=True,check=True,timeout=180)
    return np.frombuffer(result.stdout,dtype='<f4').reshape(-1,2).copy()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('controls','demo'),required=True)
    parser.add_argument('--installed',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--run-evidence',type=Path,required=True)
    args=parser.parse_args()
    original=json.loads((args.run_evidence/'verification.json').read_text('utf-8'))
    project=Path(original['project']); assert project.is_relative_to(ROOT/'local')
    evidence=args.evidence.resolve(); evidence.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    prefix=[sys.executable,'-I','-S','-B','-u','-X','utf8',str(args.installed.resolve(strict=True)/'run.py')]
    checks=[]
    def invoke(*argv,expected=0):
        command=[*prefix,*map(str,argv)]; started=time.monotonic()
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=1800)
        name=f'{len(checks)+1:02d}'
        (evidence/(name+'-stdout.json')).write_bytes(result.stdout); (evidence/(name+'-stderr.txt')).write_bytes(result.stderr)
        value=json.loads(result.stdout.decode('utf-8-sig'))
        checks.append(dict(argv=list(map(str,argv)),exit_code=result.returncode,expected_exit_code=expected,
            seconds=time.monotonic()-started,command=value['command'],status=value['status']))
        write(evidence/'calls.json',checks)
        print(json.dumps(checks[-1]),flush=True)
        assert result.returncode==expected,value
        return value
    base=['audio','separate-stems','--project',project,'--asset-id','controlled_mix','--adapter-id','four','--device','cuda']
    def metadata():
        return {name:sha(project/name) for name in ('project.json','project.lock.json','rights-ledger.json','models/audio-adapters.json')}
    if args.mode=='controls':
        before=metadata()
        invoke(*base,'--prefix','cpu',expected=2)  # pre-existing assets and files
        invoke(*base,'--prefix','bad_device','--device-index','31',expected=10)
        marker=evidence/'pre-cancel'; marker.touch()
        invoke(*base,'--prefix','pre_cancel','--cancel-file',marker,expected=8)
        assert before==metadata()
        marker=evidence/'running-cancel'
        command=[*prefix,*map(str,[*base,'--device','cpu','--prefix','running_cancel','--cancel-file',marker,'--timeout-seconds','600'])]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.GetExitCodeProcess.restype=wintypes.BOOL
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        def live(handle):
            code=wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
            return code.value==259
        process=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        handle=None; started=time.monotonic(); cancellation={}
        try:
            while time.monotonic()-started<120:
                assert process.poll() is None,'CLI exited before worker observation'
                requests=list(project.glob('cache/four-stem-separation/hdemucs-*/request.json'))
                if requests:
                    query='Get-CimInstance Win32_Process -Filter "ParentProcessId = '+str(process.pid)+'" | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress'
                    result=subprocess.run(['powershell','-NoProfile','-Command',query],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode==0 and result.stdout.strip():
                        entries=json.loads(result.stdout.decode('utf-8-sig')); entries=entries if isinstance(entries,list) else [entries]
                        children=[row for row in entries if 'stem_separation_worker.py' in str(row.get('CommandLine'))]
                        if children:
                            assert len(children)==1
                            child=children[0]; handle=kernel.OpenProcess(0x1000|0x100000,False,int(child['ProcessId']))
                            assert handle and live(handle) and child['ParentProcessId']==process.pid
                            cancellation=dict(cli_pid=process.pid,worker=child,worker_live_before_cancel=True,
                                seconds_to_worker=time.monotonic()-started,scope='actual worker startup/integrity cancellation; no GPU-kernel or host-hash latency claim')
                            write(evidence/'cancel-request.json',json.loads(requests[0].read_text('utf-8')))
                            break
                time.sleep(.1)
            else:raise TimeoutError('No verified live worker within startup budget')
            cancelled=time.monotonic(); marker.touch()
            stdout,stderr=process.communicate(timeout=30)
            (evidence/'cancel-stdout.json').write_bytes(stdout); (evidence/'cancel-stderr.txt').write_bytes(stderr)
            value=json.loads(stdout.decode('utf-8-sig')); elapsed=time.monotonic()-cancelled
            assert process.returncode==8 and value['errors'][0]['code']=='CANCELLED' and elapsed<10
            assert not live(handle) and before==metadata()
            assert not list(project.glob('cache/four-stem-separation/hdemucs-*'))
            assert not list(project.glob('assets/derived/running_cancel_*'))
            cancellation.update(exit_code=8,cancel_ack_seconds=elapsed,worker_exited=True,
                project_ledger_registry_unchanged=True,temporary_pcm_and_partial_outputs_cleaned=True)
        finally:
            if process.poll() is None:
                # Only the test process tree created immediately above is owned here.
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
                process.communicate(timeout=20)
            if handle:kernel.CloseHandle(handle)
        write(evidence/'verification.json',dict(status='passed',mode='actual installed controls',calls=checks,
            cancellation=cancellation,metadata_before=before,metadata_after=metadata(),generator_sha256=sha(Path(__file__))))
        return 0
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    public=ROOT/'docs/assets/four-stems-20261025-r1'
    public.mkdir(parents=True,exist_ok=False)
    figure,axis=plt.subplots(figsize=(12.8,7.2),dpi=100)
    figure.patch.set_facecolor('#101821');axis.set_facecolor('#101821')
    x=np.arange(4)
    cpu=[original['controlled']['cpu']['scores'][role]['improvement_db'] for role in ROLES]
    gpu=[original['controlled']['cuda']['scores'][role]['improvement_db'] for role in ROLES]
    axis.bar(x-.18,cpu,.36,label='CPU',color='#78b9ce');axis.bar(x+.18,gpu,.36,label='CUDA / RTX 3060',color='#f2bc75')
    axis.axhline(3,color='#cd7777',linestyle='--',label='Frozen 3 dB improvement target')
    axis.set_xticks(x,ROLES,color='white',fontsize=17);axis.set_ylim(0,20)
    axis.set_ylabel('SI-SDR improvement over mixture (dB)',color='white',fontsize=15)
    axis.tick_params(axis='y',colors='white');axis.spines[['top','right']].set_visible(False)
    for index,(a,b) in enumerate(zip(cpu,gpu)):
        axis.text(index, max(a,b)+.6, f'{a:.2f} / {b:.2f}',ha='center',color='white',fontsize=16)
    axis.legend(facecolor='#e9edf0',loc='upper right',fontsize=11)
    axis.set_title('agent editor kit 0.1.6 | 4 independent neural stems',color='white',fontsize=22,pad=24)
    figure.text(.5,.045,'Actual installed model results | 6s controlled fixture | Natural quality and listening remain open',
                ha='center',color='#d6e1e6',fontsize=13)
    figure.tight_layout(rect=(.02,.08,.98,.98)); image=public/'installed-metrics.png';figure.savefig(image);plt.close(figure)
    write(public/'SOURCE.json',dict(kind='original numeric diagnostic graphic, not source audio reproduction',
        creator='agent editor kit',license_spdx='CC0-1.0',data= str((args.run_evidence/'verification.json').relative_to(ROOT)),
        data_sha256=sha(args.run_evidence/'verification.json'),source_image_sha256=sha(image),
        third_party_audio_redistributed=False,model_license='unverified',audio_outputs_local_only=True))
    invoke('media','ingest','--project',project,'--input',image,'--asset-id','metrics_board','--creator','agent editor kit',
        '--license-spdx','CC0-1.0','--verification-status','verified','--evidence',public/'SOURCE.json')
    changes=project.parent/'demo-changes.json'
    write(changes,dict(operations=[dict(op='update_sequence',sequence_id='seq_main',patch=dict(canvas=dict(width=640,height=360))),
        dict(op='append_clip',track_id='track_video_1',asset_id='metrics_board',source_in_tick=0,source_out_tick=540000,
             timeline_start_tick=0,duration_tick=540000)]))
    invoke('timeline','compose','--project',project,'--input',changes)
    video=project/'renders/four-stem-mix.mkv'
    invoke('render','--project',project,'--output',video,'--container','mkv','--audio-codec','pcm_f32le','--width','640','--height','360')
    invoke('quality','check','--project',project,'--input',video,'--width','640','--height','360','--require-audio')
    estimate=pcm(video); expected=sum(pcm(project/original['controlled']['cuda']['assets'][role]['uri']) for role in ROLES)
    assert estimate.shape==expected.shape==(288000,2)
    error=float(np.max(np.abs(estimate.astype(np.float64)-expected.astype(np.float64))))
    assert error<=3e-6,('Rendered four-track sum differs',error)
    package=project.parent/'demo-four-stems.aevpkg.zip'
    invoke('convert','export','--project',project,'--target-format','package','--output',package)
    restored=project.parent/'演示往返 工程'
    invoke('convert','import','--input',package,'--output',restored)
    invoke('validate','--project',restored)
    after=restored/'renders/four-stem-mix.mkv'
    invoke('render','--project',restored,'--output',after,'--container','mkv','--audio-codec','pcm_f32le','--width','640','--height','360')
    assert np.array_equal(estimate,pcm(after))
    protected=project/'renders/must-not-publish.mkv'
    invoke('render','--project',project,'--output',protected,'--container','mkv','--audio-codec','pcm_f32le',
           '--width','640','--height','360','--publish',expected=7)
    assert not protected.exists()
    ffmpeg=[]
    def ff(*args):
        result=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',*map(str,args)],capture_output=True,timeout=180)
        ffmpeg.append(dict(argv=list(map(str,args)),exit_code=result.returncode)); assert result.returncode==0,result.stderr
        return result.stdout
    raw=[]
    for path in (video,after):
        pixels=ff('-i',path,'-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'); assert len(pixels)==640*360*3*180
        import hashlib
        raw.append(hashlib.sha256(pixels).hexdigest())
    assert raw[0]==raw[1]
    public_video=public/'installed-diagnostic-silent.mp4'
    ff('-n','-i',video,'-map','0:v:0','-c:v','copy','-an',public_video)
    gif=public/'installed-diagnostic-silent.gif'
    ff('-n','-i',public_video,'-vf','fps=10,scale=640:360:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse','-an',gif)
    from PIL import Image
    with Image.open(gif) as opened:
        frames=opened.n_frames; millis=0
        for index in range(frames):opened.seek(index);millis+=opened.info.get('duration',0)
    assert frames==60 and millis==6000
    summary=dict(status='passed',mode='actual installed four-track render',calls=checks,
        samples=288000,sample_rate=48000,channels=2,float_mix_max_abs_error=error,roundtrip_pcm_exact=True,
        roundtrip_decoded_rgb_sha256=raw[0],frames=180,fps=30,duration_seconds=6,
        local_audio_render=str(video),local_project_package=str(package),package_sha256=sha(package),
        published_media='original numeric board and silent diagnostic video/GIF only; source/model audio not redistributed',
        public_files={path.name:dict(bytes=path.stat().st_size,sha256=sha(path)) for path in public.iterdir() if path.is_file()},
        gif=dict(frames=frames,duration_milliseconds=millis,audio=False),ffmpeg=ffmpeg,
        model_audio_publish_expected_denied=True,human_listening=False,matplotlib=matplotlib.__version__)
    write(evidence/'verification.json',summary)
    print(json.dumps(dict(status='passed',float_mix_error=error,frames=180,roundtrip_pcm_exact=True)),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
