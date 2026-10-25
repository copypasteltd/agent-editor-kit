"""Actual installed OpenCL composition, paired measurements and Skill workflow."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time

from run_projection_scanline_case_20261026 import affinity

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/opencl-projection-20261026-r1'
INSTALLED=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.18/final-r1/installed'
PYTHON='C:/Python313/python.exe'

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('benchmark','controls','skill','preview'),required=True)
    parser.add_argument('--run',required=True);parser.add_argument('--project-run',default='r1')
    parser.add_argument('--assets-run',default='r1')
    args=parser.parse_args()
    for name in (args.run,args.project_run,args.assets_run):assert name.replace('-','').isalnum()
    out=BASE/(args.phase+'-'+args.run);out.mkdir(parents=True,exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/('workspace/opencl-projection-20261026-case-'+args.project_run)
    project=work/'原生 GPU 对照工程'
    assets=ROOT/('docs/assets/opencl-projection-20261026-'+args.assets_run)
    prefix=[PYTHON,'-I','-S','-B','-u','-X','utf8',INSTALLED/'run.py']
    skill=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
           'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1']
    report=dict(status='running',phase=args.phase,started_at_utc=datetime.now(timezone.utc).isoformat(),
        native_windows=True,virtualization=False,browser_ui=False,human_listening=False,
        continuous_playback=False,natural_motion_quality_acceptance=False,affinity=affinity())
    calls=[]
    def save(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def call(name,argv,*,binary=False,allow_failure=False,timeout=600):
        argv=list(map(str,argv));started=time.perf_counter()
        result=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        elapsed=time.perf_counter()-started
        stdout,stderr=out/(name+'.stdout'),out/(name+'.stderr')
        if binary:stdout.write_text(json.dumps(dict(bytes=len(result.stdout),sha256=hashlib.sha256(result.stdout).hexdigest()))+'\n',encoding='utf8')
        else:stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        record=dict(id=name,argv=argv,exit_code=result.returncode,elapsed_seconds=elapsed,
                    stdout_sha256=sha(stdout),stderr_sha256=sha(stderr))
        calls.append(record);save('calls.json',calls)
        print(json.dumps(dict(id=name,code=result.returncode,elapsed_seconds=round(elapsed,3))),flush=True)
        if not allow_failure:assert result.returncode==0,result.stderr.decode('utf8','replace')[-4000:]
        return result.stdout,record
    def cli(name,launcher,*arguments,allow_failure=False):
        raw,record=call(name,[*launcher,*arguments],allow_failure=allow_failure)
        value=json.loads(raw.decode('utf-8-sig'))
        if not allow_failure:assert value['ok'],value
        return value,record
    try:
        import shutil
        ffmpeg,ffprobe=shutil.which('ffmpeg'),shutil.which('ffprobe');assert ffmpeg and ffprobe
        version,_=call('ffmpeg-version',[ffmpeg,'-version'])
        report['ffmpeg']=dict(path=ffmpeg,sha256=sha(ffmpeg),version=version.decode('utf8').splitlines()[0])
        def decoded(name,path):
            raw,_=call(name+'-frames',[ffmpeg,'-v','error','-i',path,'-map','0:v:0','-an',
                '-fps_mode','passthrough','-pix_fmt','rgba','-f','framemd5','pipe:1'])
            rows=[line.strip() for line in raw.decode().splitlines() if line and not line.startswith('#')]
            assert len(rows)==120
            pcm,_=call(name+'-pcm',[ffmpeg,'-v','error','-i',path,'-map','0:a:0','-vn',
                '-acodec','pcm_f32le','-f','f32le','pipe:1'],binary=True)
            assert len(pcm)==4*48000*2*4
            return dict(frame_count=len(rows),frames=rows,pcm_bytes=len(pcm),pcm_sha256=hashlib.sha256(pcm).hexdigest())
        output_args=['--project',project,'--sequence-id','projection_demo','--container','mkv',
            '--audio-codec','pcm_f32le','--pixel-format','yuv444p','--crf','0','--hardware-encode','off']
        if args.phase=='benchmark':
            work.mkdir(parents=True,exist_ok=False)
            package=ROOT/'docs/assets/projection-scanline-20261026-r2/editable-projection.aevpkg.zip'
            assert sha(package)=='06180c1d6642152273ab9bf88429e540bca30cc71bfcf703dc6a4aaba9e94d24'
            response,_=cli('installed-version',prefix,'version');assert response['data']['cli_version']=='0.1.20'
            cli('import',prefix,'convert','import','--input',package,'--output',project)
            cli('validate',prefix,'validate','--project',project)
            original=json.loads((project/'project.json').read_bytes())
            frozen={p.relative_to(project).as_posix():sha(p) for p in [project/'rights-ledger.json',*sorted((project/'assets').rglob('*'))] if p.is_file()}
            baseline=None;times={'cpu':[],'opencl':[]};renders=[]
            for mode,number in (('opencl',1),('cpu',1),('cpu',2),('opencl',2),('opencl',3),('cpu',3)):
                name=f'{mode}-{number}';path=project/'renders'/(name+'.mkv')
                response,record=cli(name,prefix,'render',*output_args,'--output',path,
                    '--projection-acceleration','require' if mode=='opencl' else 'off',
                    '--projection-device','0.0','--projection-memory-mib','1024',
                    '--sequence-sampling','area','--sequence-memory-mib','1024')
                execution=response['data']['projection_acceleration']
                if mode=='opencl':
                    assert execution['status']=='verified' and len(execution['nodes'])>=3
                    assert all(n['selected']=='opencl' for n in execution['nodes'])
                    diagnostic=Path(execution['report']);destination=out/(name+'-diagnostics')
                    shutil.copytree(diagnostic.parent,destination)
                fingerprint=decoded(name,path)
                if baseline is None:baseline=fingerprint
                assert fingerprint==baseline,'Decoded frames/clock/PCM differ: '+name
                times[mode].append(record['elapsed_seconds'])
                renders.append(dict(id=name,path=str(path),sha256=sha(path),elapsed_seconds=record['elapsed_seconds'],
                    fingerprint=fingerprint,projection=execution,manifest=response['data']['manifest']))
            assert frozen=={p.relative_to(project).as_posix():sha(p) for p in [project/'rights-ledger.json',*sorted((project/'assets').rglob('*'))] if p.is_file()}
            import copy
            current=json.loads((project/'project.json').read_bytes());left,right=copy.deepcopy(original),copy.deepcopy(current)
            for value in (left,right):
                value['project'].pop('updated_at');value.pop('outputs');value['provenance'].pop('change_log')
            assert left==right
            assert len(current['outputs'])==len(original['outputs'])+6
            (out/'authored-project.json').write_bytes((project/'project.json').read_bytes())
            medians={mode:statistics.median(values) for mode,values in times.items()}
            report.update(timings_seconds=times,medians_seconds=medians,median_ratio=medians['cpu']/medians['opencl'],
                timeline_settings_assets_rights_unchanged=True,frames_and_clock_equal_all_six=True,audio_pcm_equal_all_six=True,
                frames_per_render=120,renders=renders,
                parameters='384x216/30fps/4s, native child480x270/source640x360, animated crop/affine/arc_push/reverse/area; libx264 CRF0/yuv444p/PCM f32, hardware encode off',
                interpretation='Same installed CLI0.1.20 and encoding; complete CLI/probes/checks included, decode measured separately; not universal GPU or 4K realtime throughput.')
        elif args.phase=='skill':
            version,_=cli('skill-version',skill,'version');assert version['data']['cli_version']=='0.1.20'
            cli('skill-capabilities',skill,'capabilities')
            path=project/'renders'/'skill-opencl.mkv'
            response,_=cli('skill-render',skill,'render',*output_args,'--output',path,
                '--projection-acceleration','require','--projection-device','0.0',
                '--sequence-sampling','area','--sequence-memory-mib','1024')
            reference=json.loads((BASE/('benchmark-'+args.project_run)/'verification.json').read_bytes())['renders'][0]['fingerprint']
            assert decoded('skill',path)==reference
            assert response['data']['projection_acceleration']['status']=='verified'
            shutil.copytree(Path(response['data']['projection_acceleration']['report']).parent,out/'projection-diagnostics')
            report.update(real_registered_skill=True,frames_equal=True,audio_pcm_equal=True,compared_frames=120,
                installed=str(INSTALLED),source_fallback=False)
        elif args.phase=='controls':
            failed,_=cli('required-device-failure',prefix,'render',*output_args,'--output',project/'renders/resumed.mkv',
                '--projection-acceleration','require','--projection-device','999.999',allow_failure=True)
            assert not failed['ok'] and failed['errors'][0]['code']=='PROJECTION_REQUIRED_UNAVAILABLE',failed
            save('failed-operation.json',failed)
            # CLI envelope exposes the persisted failed operation, never an
            # encoded fallback file. Resume retains the plan's other settings.
            operation=failed.get('operation_id') or failed.get('data',{}).get('operation_id')
            if not operation:operation=failed['errors'][0].get('operation_id')
            assert operation,failed
            resumed,_=cli('resume',prefix,'render','--project',project,'--sequence-id','projection_demo',
                '--resume',operation,'--projection-device','0.0','--projection-acceleration','require',
                '--sequence-sampling','area','--sequence-memory-mib','1024')
            assert resumed['data']['projection_acceleration']['status']=='verified'
            save('resume-operation.json',resumed)
            report.update(required_failure_preserved=True,resume_actual_opencl=True,operation_id=operation)
        else:
            assets.mkdir(parents=True,exist_ok=False)
            source=project/'renders/opencl-3.mkv';mp4=assets/'projection.mp4';gif=assets/'projection.gif'
            call('preview-mp4',[ffmpeg,'-v','error','-n','-i',source,'-an','-c:v','h264_nvenc','-preset','p5',
                '-cq','20','-pix_fmt','yuv420p','-movflags','+faststart',mp4])
            call('preview-gif',[ffmpeg,'-v','error','-n','-i',source,'-an','-filter_complex',
                'fps=10,scale=384:216:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',gif])
            for label,path,count in (('mp4',mp4,120),('gif',gif,40)):
                raw,_=call(label+'-probe',[ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',path])
                info=json.loads(raw);assert len(info['streams'])==1 and int(info['streams'][0]['nb_read_frames'])==count
                call(label+'-full-decode',[ffmpeg,'-v','error','-i',path,'-f','null','NUL'])
            call('midpoint',[ffmpeg,'-v','error','-n','-ss','2','-i',source,'-frames:v','1',assets/'midpoint.png'])
            (assets/'original.png').write_bytes((ROOT/'docs/assets/motion-pack-20261025-r1/original.png').read_bytes())
            (assets/'SOURCE.txt').write_text('Self-authored FIELD NOTES illustration, MIT; Noto font OFL.\nOriginal generator/rights: ../motion-pack-20261025-r1/SOURCE.txt\nActual installed CLI0.1.20 OpenCL crop/affine/sequence area composition; silent preview.\n',encoding='utf8',newline='\n')
            cli('export-editable',prefix,'convert','export','--project',project,'--target-format','package',
                '--output',assets/'editable-projection.aevpkg.zip')
            files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(assets.iterdir()) if p.is_file()]
            (assets/'media-manifest.json').write_text(json.dumps(dict(status='passed',cli_version='0.1.20',files=files,
                mp4_frames=120,gif_frames=40,seconds=4,silent=True,preview_encoder='h264_nvenc',
                composition='native OpenCL dynamic crop/affine/sequence area, CPU other filters, separate hardware preview encode',
                continuous_playback=False,human_aesthetic_acceptance=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
            report.update(public_files=files,mp4_frames=120,gif_frames=40,complete_decode=True,preview_encoder='h264_nvenc')
        report.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat());save('verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('renders','public_files')},ensure_ascii=False),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc),finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',report);raise

if __name__=='__main__':main()
