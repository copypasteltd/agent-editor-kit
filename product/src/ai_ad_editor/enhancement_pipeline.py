"""Owned cancellable enhancement execution and complete encoded PCM verification."""
import contextlib,json,math,re,shutil,stat,subprocess,time
from pathlib import Path
from fractions import Fraction
from .local_enhancement import ENGINE,PROTOCOL,verify_adapter,error
from .lipsync_plan import digest
from .artifact_locks import artifact_entry
from .media import ffmpeg_path,ffprobe_path,probe_media
from .native_process_job import NativeProcessJob
from .native_audio_clock import cancel
from .utils import atomic_write_json,run_process,sha256_file
from .pipeline_diagnostics import Session,_limited_json,SUMMARY_LIMIT


class AudioDiagnosticSession(Session):
    def read_progress(self):
        value,metadata=_limited_json(self.prepared_directory,'progress.json',SUMMARY_LIMIT)
        if not isinstance(value,dict):return metadata
        phase=value.get('phase');done=value.get('done');total=value.get('total');pid=value.get('worker_pid')
        phases={'indexing-native-audio-clock','decoding-native-clock','resampling-to-model-clock','loading-fixed-deepfilternet3',
            'neural-enhancement','resampling-to-native-clock','encoding-lossless-native-audio'}
        if (phase not in phases or type(done)is not int or type(total)is not int or not 0<=done<=total<=65536
                or total<1 or type(pid)is not int or pid<1):return dict(state='invalid_audio_progress')
        return dict(state='read',phase=phase,segments_done=done,segments_total=total,worker_pid=pid)

def workspace_bytes(work):
    """Observe storage while atomic worker receipts can disappear.

    A renamed temporary file is no longer resident at its old path. Other
    stat failures remain errors; permissions and I/O faults are not hidden.
    """
    total=0
    for path in work.rglob('*'):
        try:info=path.stat()
        except FileNotFoundError:continue
        if stat.S_ISREG(info.st_mode):total+=info.st_size
    return total


def validate_response(response,request):
    if (not isinstance(response,dict) or response.get('protocol')!=PROTOCOL or response.get('status')!='succeeded'
            or response.get('network')!='disabled' or response.get('blocked_network_events')!=[]
            or response.get('request_sha256')!=request['request_sha256'] or response.get('source_sha256')!=request['source']['sha256']
            or response.get('adapter_sha256')!=request['adapter']['sha256']):raise error('WORKER_RESPONSE','增强工作进程协议或状态无效',response=response)
    try:
        r=response['range'];n=r['samples'];rate=r['sample_rate'];c=response['channels']
        if any(type(v)is not int for v in (*r.values(),c)) or set(r)!={'start_sample','end_sample','samples','sample_rate'} or c not in (1,2) or not 8000<=rate<=96000 or not 0<=r['start_sample']<r['end_sample'] or n!=r['end_sample']-r['start_sample'] or n>600*rate:raise ValueError('clock')
        if response['output_bytes']!=n*c*4 or response['model_samples']!=max(1,round(n*48000/rate)):raise ValueError('PCM bytes/model clock')
        for k in ('input_PCM_sha256','output_PCM_sha256','output_sha256'):
            if not isinstance(response[k],str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',response[k]):raise ValueError('hash')
        if any(type(response[k])not in (int,float) or not math.isfinite(response[k]) or response[k]<0 for k in ('output_peak','output_rms','effective_wet','elapsed_seconds')):raise ValueError('signal metrics')
        wet=request['options']['strength'];limit=request['options']['attenuation_limit_db']
        if limit is not None:wet*=1-10**(-limit/20)
        if response['effective_wet']!=wet or response['bypass_bit_exact']!=(wet==0):raise ValueError('mix settings')
        if wet==0:
            if response['model'] is not None or response['metrics']['model_calls']!=0 or response['input_PCM_sha256']!=response['output_PCM_sha256']:raise ValueError('false bypass')
        else:
            model=response['model'];calls=response['metrics']['model_calls']
            if model['neural_backend']!='cuda' or model['frontend_backend']!='numpy-cpu' or model['CPU_fallback'] is not False or type(calls)is not int or calls<0 or model['model_forwards']!=calls or model['channel_forwards']!=calls*c:raise ValueError('actual inference counters')
        from .enhancement_plan import sample_range
        expected=sample_range(request['selection'],rate,response['native_clock']['logical_frames'])
        if r!=expected or response['native_clock']['channels']!=c or response['native_clock']['native_sample_rate']!=rate:raise ValueError('native clock selection')
    except (ValueError,TypeError,KeyError,OverflowError) as exc:raise error('WORKER_RESPONSE','增强响应时钟、推理计数或PCM摘要无效',cause=str(exc)) from exc

def execute(root,job,source,adapter,*,selection,options,storage_budget_bytes,timeout,cancel_file,operation_id,progress=lambda *_:None):
    work=job.path;started=time.monotonic();deadline=started+timeout
    def remaining():
        cancel(cancel_file);left=deadline-time.monotonic()
        if left<=0:raise error('TIMEOUT','增强管道超过总超时预算')
        return left
    request=dict(protocol=PROTOCOL,engine=ENGINE,network='disabled',source=source,adapter=adapter,selection=selection,options=options,
        storage_budget_bytes=storage_budget_bytes,timeout_seconds=timeout,cancel_file=str(cancel_file) if cancel_file else None,
        ffmpeg=artifact_entry(Path(ffmpeg_path()),'ffmpeg'),ffprobe=artifact_entry(Path(ffprobe_path()),'ffprobe'))
    request['request_sha256']=digest(request);atomic_write_json(work/'request.json',request)
    process=None;cleanup={};owned=None
    diagnostic=AudioDiagnosticSession(root,request,adapter,operation_id);diagnostic.prepare(work,request)
    try:
        remaining();owned=NativeProcessJob()
        with (work/'worker.log').open('w+b') as log:
            command=[adapter['executable'],'-I','-B','-u','-X','utf8',str(Path(__file__).with_name('enhancement_worker.py')),str(work/'request.json')]
            diagnostic.start_failure_role='worker'
            process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=log,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|owned.creationflags)
            diagnostic.processes.started('worker',process);diagnostic.start_failure_role=None
            try:
                owned.attach_and_resume(process);last=None;diagnostic.stage='running'
                while process.poll()is None:
                    remaining();diagnostic.observe()
                    if workspace_bytes(work)>storage_budget_bytes:raise error('STORAGE','实际增强工作空间超过预算')
                    p=work/'progress.json'
                    if p.is_file() and p.stat().st_size<=16384:
                        with contextlib.suppress(ValueError,TypeError,KeyError,OSError):
                            info=json.loads(p.read_bytes());value=(info['phase'],info['done'],info['total'])
                            if value!=last and type(value[1])is int and type(value[2])is int and 0<=value[1]<=value[2] and value[2]>0:
                                progress(*value);last=value
                    time.sleep(.1)
            finally:
                diagnostic.processes.before_cleanup()
                owned.close();owned=None
                if process.poll()is None:process.kill()
                process.wait(timeout=10)
                cleanup=dict(worker_pid=process.pid,returncode=process.returncode,worker_exited=process.poll()is not None,
                    process_tree='native-Windows-KILL_ON_JOB_CLOSE-before-worker-code',owner_job_closed=True)
                diagnostic.processes.finished()
        remaining();diagnostic.stage='validating-response';path=work/'response.json'
        if not path.is_file() or path.stat().st_size>1024**2:raise error('WORKER_RESPONSE','增强进程未返回有界响应',returncode=process.returncode)
        response=json.loads(path.read_bytes())
        if process.returncode:raise error('WORKER_FAILED','增强工作进程失败',response=response)
        validate_response(response,request)
        diagnostic.stage='verifying-output';staged=work/'enhanced.wav';r=response['range'];rate=r['sample_rate'];channels=response['channels']
        if not staged.is_file() or staged.stat().st_size!=response['output_wav_bytes'] or 'sha256:'+sha256_file(staged)!=response['output_sha256']:raise error('OUTPUT_CHANGED','增强输出尺寸或摘要不符')
        probe=probe_media(staged);stream=next(s for s in probe['streams'] if s['codec_type']=='audio')
        if (stream['codec_name'],int(stream['sample_rate']),int(stream['channels']))!=('pcm_f32le',rate,channels) or int(stream['duration_ts'])*Fraction(stream['time_base'])*rate!=r['samples']:raise error('OUTPUT_CLOCK','编码后原生PCM格式或完整样本数不符')
        result=run_process([request['ffmpeg']['path'],'-nostdin','-v','error','-i',str(staged),'-map','0:a:0','-c:a','pcm_f32le','-f','hash','-hash','sha256','pipe:1'],timeout=remaining(),cancel_file=cancel_file)
        hashed=result.stdout.strip().lower()
        if result.returncode or not re.fullmatch('sha256=[0-9a-f]{64}',hashed) or 'sha256:'+hashed[7:]!=response['output_PCM_sha256']:raise error('ROUNDTRIP','完整编码后PCM摘要与推理输出不符')
        if not verify_adapter(adapter)['ok'] or artifact_entry(Path(source['path']),'source')['sha256']!=source['sha256'] or any(artifact_entry(Path(request[k]['path']),k)!=request[k] for k in ('ffmpeg','ffprobe')):raise error('INPUT_CHANGED','发布前增强源、模型或媒体工具改变')
        remaining()
        from .enhancement_plan import recipe
        return staged,dict(protocol=PROTOCOL,sha256=response['output_sha256'],probe=probe,worker=response,cleanup=cleanup,
            complete_PCM_roundtrip_verified=True,native_sample_clock_verified=True,original_channels_verified=True,
            recipe=recipe(source,adapter,r,channels=channels,selection_=selection,options_=options),
            elapsed_seconds=time.monotonic()-started,natural_quality_accepted=False)
    except BaseException as exc:
        if diagnostic.start_failure_role:diagnostic.processes.start_failed(diagnostic.start_failure_role)
        diagnostic.capture(work,exc);raise
    finally:
        if owned is not None:owned.close()
