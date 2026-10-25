"""Paired installed-render measurements, actual Skill render and public previews."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/projection-scanline-20261026-r1'
WORK = ROOT/'workspace/projection-scanline-20261026-r1'
PROJECT = WORK/'对照工程'
ASSETS = ROOT/'docs/assets/projection-scanline-20261026-r1'
PYTHON = 'C:/Python313/python.exe'
OLD = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.15/final-r1/installed'
NEW = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.17/final-r1/installed'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream, 'sha256').hexdigest()


def affinity():
    # Restrict only this evidence process and its inherited child processes.
    # Other applications/GPU workloads and host affinity remain untouched.
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.GetProcessAffinityMask.argtypes=[wintypes.HANDLE,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
    kernel.SetProcessAffinityMask.argtypes=[wintypes.HANDLE,ctypes.c_size_t]
    process=kernel.GetCurrentProcess();available=ctypes.c_size_t();system=ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(process,ctypes.byref(available),ctypes.byref(system)):
        raise ctypes.WinError(ctypes.get_last_error())
    cores=[n for n in range(ctypes.sizeof(ctypes.c_size_t)*8) if available.value&(1<<n)][:4]
    selected=sum(1<<n for n in cores)
    if not kernel.SetProcessAffinityMask(process,selected):raise ctypes.WinError(ctypes.get_last_error())
    return dict(original_mask=available.value,selected_mask=selected,logical_processors=cores,
                scope='This evidence process and its children only; not an isolated host benchmark.')


def main():
    global WORK, PROJECT, ASSETS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('benchmark','skill','preview'),required=True)
    parser.add_argument('--run',default='r1')
    parser.add_argument('--evidence-run', help='New evidence attempt, retaining the existing project run.')
    parser.add_argument('--assets-run', default='r1', help='New public asset directory for a preview attempt.')
    args=parser.parse_args()
    for value in (args.run,args.evidence_run or args.run,args.assets_run):
        assert value.replace('-','').isalnum()
    WORK=ROOT/('workspace/projection-scanline-20261026-'+args.run)
    PROJECT=WORK/'对照工程'
    ASSETS=ROOT/('docs/assets/projection-scanline-20261026-'+args.assets_run)
    out=BASE/(args.phase+'-'+(args.evidence_run or args.run));out.mkdir(parents=True,exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def save(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    report=dict(status='running',phase=args.phase,started_at_utc=datetime.now(timezone.utc).isoformat(),
        native_windows=True,virtualization=False,browser_ui=False,human_listening=False,
        continuous_playback=False,natural_motion_quality_acceptance=False,affinity=affinity())
    calls=[]
    def call(name,argv,*,binary=False,timeout=420):
        argv=list(map(str,argv));started=time.perf_counter()
        result=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        elapsed=time.perf_counter()-started
        stdout,stderr=out/(name+'.stdout'),out/(name+'.stderr')
        if binary:
            stdout.write_text(json.dumps(dict(bytes=len(result.stdout),sha256=hashlib.sha256(result.stdout).hexdigest()))+'\n',encoding='utf8')
        else:stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        record=dict(id=name,argv=argv,exit_code=result.returncode,elapsed_seconds=elapsed,
                    stdout_sha256=sha(stdout),stderr_sha256=sha(stderr))
        calls.append(record);save('calls.json',calls)
        print(json.dumps(dict(id=name,code=result.returncode,elapsed_seconds=round(elapsed,3))),flush=True)
        assert result.returncode==0,result.stderr.decode('utf8','replace')[-4000:]
        return result.stdout,record
    def cli(name,prefix,*arguments):
        raw,record=call(name,[*prefix,*arguments]);value=json.loads(raw.decode('utf-8-sig'))
        assert value['ok'],value
        return value,record
    prefix=lambda directory:[PYTHON,'-I','-S','-B','-u','-X','utf8',directory/'run.py']
    try:
        # Use exactly the FFmpeg resolved by the installed runtime.
        environment=json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
        import shutil
        ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
        version,_=call('ffmpeg-version',[ffmpeg,'-version'])
        report['ffmpeg']=dict(path=ffmpeg,sha256=sha(ffmpeg),version=version.decode('utf8').splitlines()[0])
        report['ffmpeg_threads']='unchanged native default; both runtimes inherit the same four-logical-CPU affinity'
        def decoded(name,path):
            raw,_=call(name+'-frames',[ffmpeg,'-v','error','-i',path,'-map','0:v:0','-an',
                '-fps_mode','passthrough','-pix_fmt','rgba','-f','framemd5','pipe:1'])
            frames=[line.rsplit(',',1)[-1].strip() for line in raw.decode().splitlines() if line and not line.startswith('#')]
            assert len(frames)==120
            pcm,_=call(name+'-pcm',[ffmpeg,'-v','error','-i',path,'-map','0:a:0','-vn','-acodec','pcm_f32le','-f','f32le','pipe:1'],binary=True)
            assert len(pcm)==4*48000*2*4
            return dict(frame_count=len(frames),frames=frames,pcm_bytes=len(pcm),pcm_sha256=hashlib.sha256(pcm).hexdigest())
        if args.phase=='benchmark':
            WORK.mkdir(parents=True,exist_ok=False)
            package=ROOT/'workspace/motion-pack-20261025-installed-r1/editable-motion.aevpkg.zip'
            assert sha(package)=='0c842a82ef864b73e0d7200c5bfe45c67f3a9290c990b5cf585a7e78227fc85c'
            for name,directory,wanted in (('old',OLD,'0.1.17'),('new',NEW,'0.1.19')):
                response,_=cli(name+'-version',prefix(directory),'version')
                assert response['data']['cli_version']==wanted
            cli('import',prefix(NEW),'convert','import','--input',package,'--output',PROJECT)
            # Author a new native-canvas combination through the installed CLI.
            project = json.loads((PROJECT/'project.json').read_bytes())
            project['settings']['sequence_sampling'] = {'method':'area','max_working_bytes':1024**3}
            (PROJECT/'project.json').write_text(json.dumps(project,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
            asset = project['assets'][0]['id']
            duration=360000
            key=lambda prop,first,last:dict(property=prop,keyframes=[
                dict(at_tick=0,value=first,interpolation='bezier',control_points=[.25,.1,.75,.9]),
                dict(at_tick=duration,value=last,interpolation="linear")])
            operations=[
                dict(op='add_sequence',id='native_panel',canvas=dict(width=480,height=270),duration_tick=duration),
                dict(op='append_clip',sequence_id='native_panel',track_id='native_panel_video_1',id='cropped_leaf',
                    asset_id=asset,source_in_tick=0,source_out_tick=duration,timeline_start_tick=0,duration_tick=duration,
                    crop=dict(unit='normalized',x=.04,y=.05,width=.88,height=.86,fit='fill'),
                    keyframes=[key('crop.x',.04,.11),key('crop.width',.88,.76),key('transform.rotation',-3.,5.)]),
                dict(op='add_sequence',id='projection_demo',canvas=dict(width=384,height=216),duration_tick=duration),
                dict(op='append_sequence_clip',sequence_id='projection_demo',track_id='projection_demo_video_1',id='projected_panel',
                    nested_sequence_id='native_panel',source_in_tick=0,source_out_tick=duration,timeline_start_tick=0,
                    duration_tick=duration,reverse=True,crop=dict(unit='normalized',x=.02,y=.03,width=.94,height=.91,fit='fit'),
                    keyframes=[key('crop.x',.02,.05),key('crop.height',.91,.83)]),
            ]
            changes=WORK/'combination.json';save('combination.json',dict(operations=operations))
            changes.write_bytes((out/'combination.json').read_bytes())
            cli('compose',prefix(NEW),'timeline','compose','--project',PROJECT,'--input',changes)
            cli('motion',prefix(NEW),'motion','pack','apply','--project',PROJECT,'--sequence-id','projection_demo',
                '--clip-id','projected_panel','--name','arc_push')
            cli('validate',prefix(NEW),'validate','--project',PROJECT)
            (out/'authored-project.json').write_bytes((PROJECT/'project.json').read_bytes())
            frozen={str(p.relative_to(PROJECT)):sha(p) for p in [PROJECT/'rights-ledger.json',*sorted((PROJECT/'assets').rglob('*'))] if p.is_file()}
            initial=json.loads((PROJECT/'project.json').read_bytes())
            renders=[];times={'old':[],'new':[]};baseline=None
            for runtime,number in (('old',1),('new',1),('new',2),('old',2),('old',3),('new',3)):
                name=f'{runtime}-{number}';path=PROJECT/'renders'/(name+'.mkv')
                response,record=cli(name,prefix(OLD if runtime=='old' else NEW),'render',
                    '--project',PROJECT,'--sequence-id','projection_demo','--output',path,
                    '--container','mkv','--audio-codec','pcm_f32le','--pixel-format','yuv444p',
                    '--crf','0','--hardware-encode','off')
                fingerprint=decoded(name,path)
                if baseline is None:baseline=fingerprint
                assert fingerprint==baseline,'Decoded video/audio changed: '+name
                times[runtime].append(record['elapsed_seconds'])
                renders.append(dict(id=name,path=str(path),sha256=sha(path),elapsed_seconds=record['elapsed_seconds'],
                    fingerprint=fingerprint,manifest=str(path)+'.manifest.json'))
            assert frozen=={str(p.relative_to(PROJECT)):sha(p) for p in [PROJECT/'rights-ledger.json',*sorted((PROJECT/'assets').rglob('*'))] if p.is_file()}
            import copy
            current=json.loads((PROJECT/'project.json').read_bytes())
            assert initial['outputs']==current['outputs'][:-6]
            assert initial['provenance']['change_log']==current['provenance']['change_log'][:-6]
            expected=[str(PROJECT/'renders'/(row['id']+'.mkv')) for row in renders]
            assert [row['path'] for row in current['outputs'][-6:]]==expected
            assert [row['output'] for row in current['provenance']['change_log'][-6:]]==expected
            assert all(row['command']=='render' for row in current['provenance']['change_log'][-6:])
            left,right=copy.deepcopy(initial),copy.deepcopy(current)
            for document in (left,right):
                document['project'].pop('updated_at');document.pop('outputs');document['provenance'].pop('change_log')
            assert left==right
            (out/'measured-project.json').write_bytes((PROJECT/'project.json').read_bytes())
            medians={name:statistics.median(values) for name,values in times.items()}
            report.update(timings_seconds=times,medians_seconds=medians,median_ratio=medians['old']/medians['new'],
                timeline_settings_assets_and_rights_unchanged=True,render_output_registration_expected=True,
                frames_equal_all_six=True,audio_pcm_equal_all_six=True,
                frames_per_render=120,renders=renders,parameters='384x216/30fps/4s; native child480x270, source640x360; area; reverse container; libx264 CRF0/yuv444p/PCM float32; hardware encode off',
                interpretation='Paired CPU render measurement on this machine and fixture; not a GPU speedup or universal throughput guarantee.')
        elif args.phase=='skill':
            launcher=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
            skill=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',launcher]
            response,_=cli('skill-version',skill,'version');assert response['data']['cli_version']=='0.1.19'
            cli('skill-capabilities',skill,'capabilities')
            target=PROJECT/'renders'/'skill.mkv'
            cli('skill-render',skill,'render','--project',PROJECT,'--sequence-id','projection_demo','--output',target,
                '--container','mkv','--audio-codec','pcm_f32le','--pixel-format','yuv444p','--crf','0','--hardware-encode','off')
            reference=json.loads((BASE/('benchmark-'+args.run)/'verification.json').read_bytes())['renders'][0]['fingerprint']
            assert decoded('skill',target)==reference
            cli('skill-validate',skill,'validate','--project',PROJECT)
            report.update(real_registered_skill=True,frames_equal=True,audio_pcm_equal=True,compared_frames=120,
                          installed=str(NEW),source_fallback=False)
        else:
            ASSETS.mkdir(parents=True,exist_ok=False)
            source=PROJECT/'renders/new-3.mkv';mp4=ASSETS/'projection.mp4';gif=ASSETS/'projection.gif'
            call('preview-mp4',[ffmpeg,'-v','error','-n','-i',source,'-an','-c:v','h264_nvenc','-preset','p5',
                '-cq','20','-pix_fmt','yuv420p','-movflags','+faststart',mp4])
            call('preview-gif',[ffmpeg,'-v','error','-n','-i',source,'-an','-filter_complex',
                'fps=10,scale=384:216:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',gif])
            for label,path,count in (('mp4',mp4,120),('gif',gif,40)):
                raw,_=call(label+'-probe',[ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',path])
                info=json.loads(raw);assert len(info['streams'])==1 and int(info['streams'][0]['nb_read_frames'])==count
                call(label+'-full-decode',[ffmpeg,'-v','error','-i',path,'-f','null','NUL'])
            png=ASSETS/'midpoint.png'
            call('midpoint',[ffmpeg,'-v','error','-n','-ss','2','-i',source,'-frames:v','1',png])
            original=ROOT/'docs/assets/motion-pack-20261025-r1/original.png'
            (ASSETS/'original.png').write_bytes(original.read_bytes())
            (ASSETS/'SOURCE.txt').write_text('Self-authored FIELD NOTES illustration; original generator and OFL font source:\n../motion-pack-20261025-r1/SOURCE.txt\nActual CLI 0.1.19 installed area render with animated crop, native child canvas, reverse clock and arc_push; silent.\n',encoding='utf8',newline='\n')
            cli('export-editable',prefix(NEW),'convert','export','--project',PROJECT,'--target-format','package','--output',ASSETS/'editable-projection.aevpkg.zip')
            files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(ASSETS.iterdir()) if p.is_file()]
            (ASSETS/'media-manifest.json').write_text(json.dumps(dict(status='passed',cli_version='0.1.19',files=files,
                mp4_frames=120,gif_frames=40,seconds=4,silent=True,preview_encoder='h264_nvenc',composition='CPU crop and sequence scanline parameter reuse',
                continuous_playback=False,human_aesthetic_acceptance=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
            report.update(public_files=files,mp4_frames=120,gif_frames=40,complete_decode=True,preview_encoder='h264_nvenc')
        report.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('renders','public_files')},ensure_ascii=False),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc),finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report);raise


if __name__=='__main__':main()
