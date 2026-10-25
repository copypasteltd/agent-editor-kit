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
BASE = ROOT/'docs/validation/evidence/affine-scanline-20261025-r1'
WORK = ROOT/'workspace/affine-scanline-20261025-r1'
PROJECT = WORK/'对照工程'
ASSETS = ROOT/'docs/assets/affine-scanline-20261025-r1'
PYTHON = 'C:/Python313/python.exe'
OLD = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.14/final-r2/installed'
NEW = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.15/final-r1/installed'


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
    global WORK, PROJECT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('benchmark','verify','skill','preview'),required=True)
    parser.add_argument('--run',default='r1')
    args=parser.parse_args();assert args.run.replace('-','').isalnum()
    WORK=ROOT/('workspace/affine-scanline-20261025-'+args.run)
    PROJECT=WORK/'对照工程'
    out=BASE/(args.phase+'-'+args.run);out.mkdir(parents=True,exist_ok=False)
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
            for name,directory,wanted in (('old',OLD,'0.1.16'),('new',NEW,'0.1.17')):
                response,_=cli(name+'-version',prefix(directory),'version')
                assert response['data']['cli_version']==wanted
            cli('import',prefix(NEW),'convert','import','--input',package,'--output',PROJECT)
            frozen={str(p.relative_to(PROJECT)):sha(p) for p in [PROJECT/'rights-ledger.json',*sorted((PROJECT/'assets').rglob('*'))] if p.is_file()}
            initial=json.loads((PROJECT/'project.json').read_bytes())
            renders=[];times={'old':[],'new':[]};baseline=None
            for runtime,number in (('old',1),('new',1),('new',2),('old',2),('old',3),('new',3)):
                name=f'{runtime}-{number}';path=PROJECT/'renders'/(name+'.mkv')
                response,record=cli(name,prefix(OLD if runtime=='old' else NEW),'render',
                    '--project',PROJECT,'--sequence-id','motion_detail_scan','--output',path,
                    '--container','mkv','--audio-codec','pcm_f32le','--pixel-format','yuv444p',
                    '--crf','0','--hardware-encode','off')
                fingerprint=decoded(name,path)
                if baseline is None:baseline=fingerprint
                assert fingerprint==baseline,'Decoded video/audio changed: '+name
                times[runtime].append(record['elapsed_seconds'])
                renders.append(dict(id=name,path=str(path),sha256=sha(path),elapsed_seconds=record['elapsed_seconds'],
                    fingerprint=fingerprint,manifest=str(path)+'.manifest.json'))
            assert frozen=={str(p.relative_to(PROJECT)):sha(p) for p in [PROJECT/'rights-ledger.json',*sorted((PROJECT/'assets').rglob('*'))] if p.is_file()}
            current=json.loads((PROJECT/'project.json').read_bytes())
            assert all(initial[key]==current[key] for key in ('settings','sequences','assets'))
            medians={name:statistics.median(values) for name,values in times.items()}
            report.update(timings_seconds=times,medians_seconds=medians,median_ratio=medians['old']/medians['new'],
                timeline_settings_assets_and_rights_unchanged=True,render_output_registration_expected=True,
                frames_equal_all_six=True,audio_pcm_equal_all_six=True,
                frames_per_render=120,renders=renders,parameters='640x360/30fps/4s; libx264 CRF0/yuv444p/PCM float32; hardware encode off',
                interpretation='Paired CPU render measurement on this machine and fixture; not a GPU speedup or universal throughput guarantee.')
        elif args.phase=='verify':
            # Recheck actual preserved outputs/commands from the completed six
            # measurements. Do not rerun timers or overwrite the failed helper.
            import copy, zipfile
            measured=BASE/('benchmark-'+args.run)
            prior=json.loads((measured/'verification.json').read_bytes())
            assert prior['status']=='failed' and prior['error']=='AssertionError()'
            captured=json.loads((measured/'calls.json').read_bytes())
            for row in captured:
                assert row['exit_code']==0
                assert sha(measured/(row['id']+'.stdout'))==row['stdout_sha256']
                assert sha(measured/(row['id']+'.stderr'))==row['stderr_sha256']
            package=ROOT/'workspace/motion-pack-20261025-installed-r1/editable-motion.aevpkg.zip'
            assert sha(package)=='0c842a82ef864b73e0d7200c5bfe45c67f3a9290c990b5cf585a7e78227fc85c'
            current=json.loads((PROJECT/'project.json').read_bytes())
            with zipfile.ZipFile(package) as zipped:
                original=json.loads(zipped.read('project.json'))
                (out/'original-project.json').write_bytes(zipped.read('project.json'))
                assert hashlib.sha256(zipped.read('rights-ledger.json')).hexdigest()==sha(PROJECT/'rights-ledger.json')
                assets=[name for name in zipped.namelist() if name.startswith('assets/')]
                assert set(assets)==set(p.relative_to(PROJECT).as_posix() for p in (PROJECT/'assets').rglob('*') if p.is_file())
                for name in assets:assert hashlib.sha256(zipped.read(name)).hexdigest()==sha(PROJECT/name)
            sequence=['old-1','new-1','new-2','old-2','old-3','new-3']
            expected_paths=[str(PROJECT/'renders'/(name+'.mkv')) for name in sequence]
            assert original['outputs']==current['outputs'][:-6]
            assert [row['path'] for row in current['outputs'][-6:]]==expected_paths
            assert original['provenance']['change_log']==current['provenance']['change_log'][:-6]
            assert all(row['command']=='render' for row in current['provenance']['change_log'][-6:])
            assert [row['output'] for row in current['provenance']['change_log'][-6:]]==expected_paths
            left,right=copy.deepcopy(original),copy.deepcopy(current)
            for document in (left,right):
                document['project'].pop('updated_at');document.pop('outputs');document['provenance'].pop('change_log')
            assert left==right, 'Only normal render output/updated_at/change_log records may differ'
            (out/'measured-project.json').write_bytes((PROJECT/'project.json').read_bytes())
            renders=[];times={'old':[],'new':[]};baseline=None
            for name in sequence:
                row=next(row for row in captured if row['id']==name)
                value=json.loads((measured/(name+'.stdout')).read_bytes());assert value['ok']
                path=PROJECT/'renders'/(name+'.mkv');fingerprint=decoded(name,path)
                if baseline is None:baseline=fingerprint
                assert fingerprint==baseline
                times[name.split('-')[0]].append(row['elapsed_seconds'])
                renders.append(dict(id=name,path=str(path),sha256=sha(path),elapsed_seconds=row['elapsed_seconds'],fingerprint=fingerprint))
            medians={name:statistics.median(values) for name,values in times.items()}
            report.update(timings_seconds=times,medians_seconds=medians,median_ratio=medians['old']/medians['new'],
                source_measurements=str(measured),source_measurement_report_status='failed_final_helper_assertion',
                measurements_reexecuted=0,preserved_measurement_affinity=prior['affinity'],renders=renders,
                timeline_settings_assets_and_rights_unchanged=True,render_output_registration_expected=True,
                only_metadata_changes=['project.updated_at','six_appended_outputs','six_appended_render_change_log_records'],
                frames_equal_all_six=True,audio_pcm_equal_all_six=True,frames_per_render=120,
                parameters='640x360/30fps/4s; libx264 CRF0/yuv444p/PCM float32; hardware encode off')
        elif args.phase=='skill':
            launcher=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
            skill=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',launcher]
            response,_=cli('skill-version',skill,'version');assert response['data']['cli_version']=='0.1.17'
            cli('skill-capabilities',skill,'capabilities')
            target=PROJECT/'renders'/'skill.mkv'
            cli('skill-render',skill,'render','--project',PROJECT,'--sequence-id','motion_detail_scan','--output',target,
                '--container','mkv','--audio-codec','pcm_f32le','--pixel-format','yuv444p','--crf','0','--hardware-encode','off')
            reference=json.loads((BASE/('verify-'+args.run)/'verification.json').read_bytes())['renders'][0]['fingerprint']
            assert decoded('skill',target)==reference
            cli('skill-validate',skill,'validate','--project',PROJECT)
            report.update(real_registered_skill=True,frames_equal=True,audio_pcm_equal=True,compared_frames=120,
                          installed=str(NEW),source_fallback=False)
        else:
            ASSETS.mkdir(parents=True,exist_ok=False)
            source=PROJECT/'renders/new-3.mkv';mp4=ASSETS/'detail-scan.mp4';gif=ASSETS/'detail-scan.gif'
            call('preview-mp4',[ffmpeg,'-v','error','-n','-i',source,'-an','-c:v','h264_nvenc','-preset','p5',
                '-cq','20','-pix_fmt','yuv420p','-movflags','+faststart',mp4])
            call('preview-gif',[ffmpeg,'-v','error','-n','-i',source,'-an','-filter_complex',
                'fps=10,scale=480:270:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',gif])
            for label,path,count in (('mp4',mp4,120),('gif',gif,40)):
                raw,_=call(label+'-probe',[ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',path])
                info=json.loads(raw);assert len(info['streams'])==1 and int(info['streams'][0]['nb_read_frames'])==count
                call(label+'-full-decode',[ffmpeg,'-v','error','-i',path,'-f','null','NUL'])
            png=ASSETS/'midpoint.png'
            call('midpoint',[ffmpeg,'-v','error','-n','-ss','2','-i',source,'-frames:v','1',png])
            original=ROOT/'docs/assets/motion-pack-20261025-r1/original.png'
            (ASSETS/'original.png').write_bytes(original.read_bytes())
            (ASSETS/'SOURCE.txt').write_text('Self-authored FIELD NOTES illustration; original generator and OFL font source:\n../motion-pack-20261025-r1/SOURCE.txt\nActual CLI 0.1.17 installed render of the unchanged detail_scan default recipe; silent.\n',encoding='utf8',newline='\n')
            files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(ASSETS.iterdir()) if p.is_file()]
            (ASSETS/'media-manifest.json').write_text(json.dumps(dict(status='passed',cli_version='0.1.17',files=files,
                mp4_frames=120,gif_frames=40,seconds=4,silent=True,preview_encoder='h264_nvenc',composition='CPU scanline parameter reuse',
                continuous_playback=False,human_aesthetic_acceptance=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
            report.update(public_files=files,mp4_frames=120,gif_frames=40,complete_decode=True,preview_encoder='h264_nvenc')
        report.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('renders','public_files')},ensure_ascii=False),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc),finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report);raise


if __name__=='__main__':main()
