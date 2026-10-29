"""Owned, cancellable RGBA model pipeline with complete PCM and encoding proofs."""
import contextlib,json,math,shutil,stat,subprocess,time
from pathlib import Path
from .errors import AppError
from .local_lipsync import ENGINE,PROTOCOL,verify_adapter,error
from .local_matting import _windows_job,request_hash
from .media import ffmpeg_path,probe_media,MAX_INPUT_BYTES
from .utils import atomic_write_json,run_process,sha256_file
from .pipeline_diagnostics import Session
from .native_audio_clock import cancel



def storage_bytes(path):
    """Observe one regular file; atomic renames may remove a scanned entry.

    Only disappearance is tolerated. Permission and I/O failures remain visible.
    This is a live budget observation, not an atomic directory snapshot.
    """
    try:
        info=path.stat()
    except FileNotFoundError:
        return 0
    return info.st_size if stat.S_ISREG(info.st_mode) else 0


def workspace_bytes(work):
    """Count immediate regular files without an is_file/stat race."""
    return sum(storage_bytes(path) for path in work.iterdir())


def validate_response(response,request):
    from .local_lipsync import settings
    try:
        for k,v in dict(status='succeeded',engine=ENGINE,protocol=PROTOCOL,network='disabled',blocked_network_events=[],
            request_sha256=request['request_sha256'],adapter_sha256=request['adapter']['sha256'],source_sha256=request['source']['sha256'],
            audio_sha256=request['audio_source']['sha256'],providers=['torch-cuda'],model_loaded=True).items():
            if response.get(k)!=v:raise ValueError(k)
        m=response['metrics'];v=request['video'];execution=response['model_execution'];n=v['frames'];batch=request['adapter']['settings']['batch_size']
        import re
        for key in ('rgba_sha256','source_rgba_sha256','input_alpha_sha256','output_alpha_sha256'):
            if not re.fullmatch(r'sha256:[0-9a-f]{64}',m[key]):raise ValueError(key)
        for k in ('width','height','frames'):
            if type(m[k])is not int or m[k]!=v[k]:raise ValueError(k)
        expected=[min(batch,n-i) for i in range(0,n,batch)]
        if m['rgba_bytes']!=v['width']*v['height']*4*n or m['model_frames']!=n or m['batches']!=len(expected) or m['input_alpha_sha256']!=m['output_alpha_sha256']:raise ValueError('frame/alpha contract')
        if type(m['owned_array_peak_bytes'])is not int or not 0<m['owned_array_peak_bytes']<=m['owned_array_budget_bytes'] or m['owned_array_budget_bytes']!=request['adapter']['settings']['state_budget_bytes']:raise ValueError('array budget')
        if any(type(m[k])is not int or not 0<=m[k]<=v['width']*v['height']*n for k in ('semantic_mask_pixels','changed_RGB_pixels')) or m['semantic_mask_pixels']==0:raise ValueError('empty or invalid region')
        if (m['alpha_mode'],m['outside_region_RGB'],m['blend_domain'],m['source_alpha'])!=('straight','preserve','encoded-8bit-SDR-RGB','bit-exact'):raise ValueError('pixel policy')
        calls=execution['calls'];conditioned=n-execution['cache_hits']
        if execution['batch_frames']!=expected or calls!=dict(audio_encoder=math.ceil(n*640/480000),vae_encoder=conditioned*2,unet=len(expected),vae_decoder=len(expected),face_parser=conditioned):raise ValueError('actual forward counts')
        if not 1<=conditioned<=n or execution['model_loads']!=1 or execution['engine']!=ENGINE or execution['CPU_fallback'] is not False or execution['network']!='disabled' or execution['weight_reader']!='safetensors-pread' or execution['precision']!=settings()['precision']:raise ValueError('execution provider')
        if type(execution['cuda_peak_allocated_bytes'])is not int or execution['cuda_peak_allocated_bytes']<=0:raise ValueError('GPU execution')
    except (ValueError,KeyError,TypeError,AttributeError) as exc:raise error('WORKER_CONTRACT','口型推理报告未通过完整协议校验',cause=str(exc)) from exc


def decoder_command(base,source,plan):
    v=plan['video'];r=plan['range'];command=[*base]
    if source['kind']=='image':command+=['-loop','1']
    elif r['source_mode']=='loop':command+=['-stream_loop','-1']
    command+=['-noautorotate','-i',source['path'],'-map',f"0:{source['stream_index']}",'-an','-sn','-dn']
    filters=['setpts=PTS-STARTPTS']
    if source['kind']!='image' and r['source_mode']!='loop':
        filters += [f"trim=start={r['start_seconds']:.12f}:end={r['end_seconds']:.12f}",'setpts=PTS-STARTPTS']
    filters+=['fps=fps=25:start_time=0:round=near']
    if r['source_mode']=='hold':filters += [f"tpad=stop_mode=clone:stop_duration={v['duration_seconds']:.12f}"]
    filters+=['setsar=1','format=rgba']
    return [*command,'-vf',','.join(filters),'-frames:v',str(v['frames']),'-f','rawvideo','-pix_fmt','rgba','pipe:1']


def execute(root,job,plan,source,audio,adapter,*,timeout,cancel_file=None,progress=None,operation_id=None):
    started=time.monotonic();work=job.path/'pipeline';work.mkdir();v=plan['video'];a=plan['audio'];source_pcm=work/'selected.wav';padded_pcm=work/'padded.wav';model_pcm=work/'model.f32le'
    if not math.isfinite(timeout) or not 0<timeout<=604800:raise error('TIMEOUT','须指定有限正超时')
    def remaining():
        cancel(cancel_file);left=timeout-(time.monotonic()-started)
        if left<=0:raise AppError('TIMEOUT','口型同步超过完整时间预算',exit_code=8)
        return left
    from .artifact_locks import artifact_entry,verification_summary
    remaining()
    if not verify_adapter(adapter)['ok']:raise error('ADAPTER_CHANGED','适配器字节变化，须重新登记')
    for row in (source,audio):
        if artifact_entry(Path(row['path']),'input')['sha256']!=row['sha256']:raise error('SOURCE_CHANGED','输入资产字节发生变化')
    ffmpeg=Path(ffmpeg_path()).resolve();ffmpeg_record=artifact_entry(ffmpeg,'ffmpeg')
    if shutil.disk_usage(work).free<plan['estimated_workspace_bytes']+128*1024**2:raise error('DISK_BUDGET','可用磁盘不足保守工作空间估算')
    base=[str(ffmpeg),'-nostdin','-v','error','-protocol_whitelist','file,pipe']
    def tool(command):
        try:
            r=run_process(command,timeout=remaining(),cancel_file=cancel_file)
        except AppError as exc:
            # Each media command consumes the same operation deadline. The
            # subprocess helper has already reclaimed its owned process tree.
            if exc.code!='PROCESS_TIMEOUT':raise
            raise AppError('TIMEOUT','口型同步超过完整时间预算',exit_code=8,
                cause=f'{exc.code}: {exc.message}'+(f'; {exc.cause}' if exc.cause else '')) from exc
        if r.returncode:raise error('MEDIA_TOOL','本地口型媒体处理失败',stderr=r.stderr[-2500:])
        return r
    tool([*base,'-n','-i',audio['path'],'-map',f"0:{audio['stream_index']}",'-vn','-af',
        f"atrim=start_sample={a['start_sample']}:end_sample={a['end_sample']},asetpts=PTS-STARTPTS",'-c:a','pcm_f32le',str(source_pcm)])
    selected_probe=probe_media(source_pcm);ap=selected_probe['audio']
    stream=next(s for s in selected_probe['streams'] if s['codec_type']=='audio')
    from fractions import Fraction
    actual_samples=round(int(stream.get('duration_ts',0))*Fraction(stream.get('time_base','0'))*a['sample_rate'])
    if actual_samples!=a['samples'] or ap['sample_rate']!=a['sample_rate'] or ap['channels']!=a['channels']:raise error('AUDIO_RANGE','实际解码样本数与选择范围不符；未截断或补偿未知时长')
    tool([*base,'-n','-i',str(source_pcm),'-af',f"apad=whole_len={a['output_samples']},atrim=end_sample={a['output_samples']}",'-c:a','pcm_f32le',str(padded_pcm)])
    pcm_hash=tool([*base,'-i',str(padded_pcm),'-map','0:a:0','-c:a','pcm_f32le','-f','hash','-hash','sha256','pipe:1']).stdout.strip().lower()
    tool([*base,'-n','-i',str(padded_pcm),'-ac','1','-ar','16000','-af',f"aresample=16000,apad=whole_len={v['frames']*640},atrim=end_sample={v['frames']*640}",'-f','f32le',str(model_pcm)])
    if model_pcm.stat().st_size!=v['frames']*640*4:raise error('MODEL_AUDIO_CLOCK','16k模型音频长度不符')
    request={**plan,'source':source,'audio_source':audio,'model_audio':dict(path=str(model_pcm),sha256='sha256:'+sha256_file(model_pcm)),
        'adapter':adapter,'response':str(work/'response.json'),'progress':str(work/'progress.json'),'ffmpeg':ffmpeg_record}
    request['request_sha256']=request_hash(request);request_path=work/'request.json';atomic_write_json(request_path,request)
    staged=work/'generated.mov';encoder=[*base,'-n','-f','rawvideo','-pixel_format','rgba','-video_size',f"{v['width']}x{v['height']}",'-framerate','25','-i','pipe:0',
        '-protocol_whitelist','file,pipe','-i',str(padded_pcm),'-map','0:v:0','-map','1:a:0','-c:v','qtrle','-pix_fmt','argb','-c:a','pcm_f32le',
        '-fps_mode','passthrough','-map_metadata','-1',str(staged)]
    commands=[decoder_command(base,source,plan),[adapter['executable'],'-I','-B','-u','-X','utf8',str(Path(__file__).with_name('lipsync_worker.py')),str(request_path)],encoder]
    diagnostic=Session(root,plan,adapter,operation_id);diagnostic.prepare(work,request);processes=[];cleanup=[]
    try:
        with contextlib.ExitStack() as stack:
            assign=stack.enter_context(_windows_job());logs=[stack.enter_context((work/(name+'.log')).open('w+b')) for name in ('decoder','worker','encoder')]
            try:
                previous=None
                for i,(role,command) in enumerate(zip(('decoder','worker','encoder'),commands)):
                    remaining();diagnostic.start_failure_role=role
                    p=subprocess.Popen(command,stdin=previous.stdout if previous else subprocess.DEVNULL,
                        stdout=subprocess.PIPE if i<2 else subprocess.DEVNULL,stderr=logs[i],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    processes.append(p);diagnostic.processes.started(role,p);assign(p);diagnostic.start_failure_role=None
                    if previous:previous.stdout.close()
                    previous=p
                diagnostic.stage='running';last=-1
                while any(p.poll()is None for p in processes):
                    remaining();diagnostic.observe()
                    if any(p.poll()not in (None,0) for p in processes):break
                    if workspace_bytes(work)>plan['storage_budget_bytes'] or storage_bytes(staged)>MAX_INPUT_BYTES:raise error('OUTPUT_BUDGET','实际输出超过存储预算')
                    if progress:
                        with contextlib.suppress(OSError,ValueError,KeyError,TypeError):
                            frame=json.loads((work/'progress.json').read_bytes())['frames']
                            if type(frame)is int and 0<=frame<=v['frames'] and frame!=last:progress(frame,v['frames']);last=frame;diagnostic.last_reported_frame=frame
                    time.sleep(.05)
                if any(p.poll()!=0 for p in processes):raise AppError('LIPSYNC_PIPELINE_FAILED','原生口型同步管道失败',exit_code=6,cause=diagnostic.failure_text())
            finally:
                if diagnostic.start_failure_role:diagnostic.processes.start_failed(diagnostic.start_failure_role)
                diagnostic.processes.before_cleanup()
                for p in processes:
                    if p.poll()is None:
                        try:p.kill()
                        except OSError:cleanup.append(dict(code='LIPSYNC_CHILD_KILL_FAILED',pid=p.pid))
                for p in processes:
                    try:p.wait(timeout=10)
                    except (OSError,subprocess.TimeoutExpired):cleanup.append(dict(code='LIPSYNC_CHILD_WAIT_FAILED',pid=p.pid))
                    finally:
                        if p.stdout:p.stdout.close()
                diagnostic.processes.finished();diagnostic.cleanup_warnings.extend(cleanup)
            if cleanup:raise error('CLEANUP','口型同步子进程未能完整回收')
        diagnostic.stage='validating-response'
        if not (work/'response.json').is_file() or (work/'response.json').stat().st_size>128*1024:raise error('WORKER_RESPONSE','推理报告缺失或过大')
        response=json.loads((work/'response.json').read_bytes());validate_response(response,request)
        diagnostic.stage='verifying-output';result_probe=probe_media(staged);vp=result_probe['video'];ap=result_probe['audio'];stream=next(s for s in result_probe['streams'] if s['codec_type']=='video')
        if (vp['width'],vp['height'],vp['codec'],vp['pix_fmt'],Fraction(vp['fps']),int(stream.get('nb_frames',0)))!=(v['width'],v['height'],'qtrle','argb',Fraction(25),v['frames']) or abs(vp['duration_seconds']-v['duration_seconds'])>.0001:raise error('OUTPUT_VIDEO','编码后视频格式、时钟或帧数不符')
        if (ap['codec'],ap['sample_rate'],ap['channels'])!=('pcm_f32le',a['sample_rate'],a['channels']):raise error('OUTPUT_AUDIO','编码后PCM格式不符')
        rgba=tool([*base,'-i',str(staged),'-map','0:v:0','-an','-pix_fmt','rgba','-fps_mode','passthrough','-f','hash','-hash','sha256','pipe:1']).stdout.strip().lower()
        pcm=tool([*base,'-i',str(staged),'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','hash','-hash','sha256','pipe:1']).stdout.strip().lower()
        if rgba!='sha256='+response['metrics']['rgba_sha256'][7:] or pcm!=pcm_hash:raise error('ROUNDTRIP','完整RGBA/PCM编码往返摘要不一致')
        remaining()
        if not verify_adapter(adapter)['ok'] or any(artifact_entry(Path(row['path']),'input')['sha256']!=row['sha256'] for row in (source,audio)) or artifact_entry(ffmpeg,'ffmpeg')!=ffmpeg_record:raise error('INPUT_CHANGED','发布前输入/模型/工具变化')
        from .lipsync_plan import recipe
        return staged,dict(protocol=PROTOCOL,recipe=recipe(plan,source,audio),sha256='sha256:'+sha256_file(staged),probe=result_probe,worker=response,
            rgba_roundtrip_verified=True,complete_PCM_roundtrip_verified=True,PCM_sha256='sha256:'+pcm_hash.removeprefix('sha256='),
            ffmpeg=ffmpeg_record,artifact_verification=verification_summary(),elapsed_seconds=time.monotonic()-started,
            cleanup=dict(processes=[dict(role=r,pid=p.pid,returncode=p.returncode,exited=p.poll()is not None,stdout_closed=p.stdout is None or p.stdout.closed) for r,p in zip(('decoder','worker','encoder'),processes)],warnings=cleanup),
            natural_quality_accepted=False)
    except BaseException as exc:
        diagnostic.capture(work,exc);raise
