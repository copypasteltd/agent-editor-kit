"""Owned native CUDA interpolation, exact packet PTS/durations and PCM proofs."""
import contextlib,json,math,re,shutil,subprocess,time
from fractions import Fraction
from pathlib import Path
from .local_interpolation import ENGINE,PROTOCOL,verify_adapter,error
from .local_matting import _windows_job,request_hash
from .media import ffmpeg_path,probe_media,MAX_INPUT_BYTES
from .utils import atomic_write_json,run_process,sha256_file
from .pipeline_diagnostics import Session
from .native_audio_clock import cancel
from .interpolation_clock import packet_filter,clock_digest

def validate_response(response,request):
    try:
        for k,v in dict(status='succeeded',engine=ENGINE,protocol=PROTOCOL,network='disabled',blocked_network_events=[],
            request_sha256=request['request_sha256'],adapter_sha256=request['adapter']['sha256'],source_sha256=request['source']['sha256'],providers=['torch-cuda'],model_loaded=True).items():
            if response.get(k)!=v:raise ValueError(k)
        m=response['metrics'];v=request['video'];execution=response['model_execution'];n=v['source_frames'];factor=v['factor'];cfg=request['adapter']['settings']
        for k,expected in dict(width=v['width'],height=v['height'],source_frames=n,frames=n*factor,factor=factor,rgba_bytes=v['width']*v['height']*4*n*factor,
            final_interval='hold-last-source-frame',anchors='bit-exact-decoded-RGBA',synthesized_alpha='flow-mask-premultiplied-RGBA-zero-hidden-RGB').items():
            if m[k]!=expected or type(m[k])is not type(expected):raise ValueError(k)
        for k in ('rgba_sha256','source_rgba_sha256','anchor_rgba_sha256'):
            if not isinstance(m[k],str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',m[k]):raise ValueError(k)
        if m['source_rgba_sha256']!=m['anchor_rgba_sha256']:raise ValueError('original anchor hash')
        for key in ('cut_after_frames','static_pairs'):
            indices=m[key]
            if not isinstance(indices,list) or indices!=sorted(set(indices)) or any(type(i)is not int or not 0<=i<n-1 for i in indices):raise ValueError(key)
        if not set(request['options']['cut_after_frame'])<=set(m['cut_after_frames']):raise ValueError('explicit cut missing')
        scores=m['cut_scores'];threshold=request['options']['scene_cut_threshold'];explicit=request['options']['cut_after_frame']
        if not isinstance(scores,list) or [r['after_frame'] for r in scores]!=m['cut_after_frames']:raise ValueError('cut score inventory')
        for row in scores:
            if set(row)!={'after_frame','mean_RGB_difference','explicit'} or type(row['mean_RGB_difference'])not in (int,float) or not math.isfinite(row['mean_RGB_difference']) or not 0<=row['mean_RGB_difference']<=1 or type(row['explicit'])is not bool or row['explicit']!=(row['after_frame'] in explicit):raise ValueError('cut score contract')
            if not row['explicit'] and (threshold is None or row['mean_RGB_difference']<threshold):raise ValueError('unsubstantiated automatic cut')
        forwards=(n-1-len(set(m['cut_after_frames']+m['static_pairs'])))*(factor-1)
        queries={str(k)+'/'+str(factor):forwards//(factor-1) for k in range(1,factor)} if forwards else {}
        for k,expected in dict(flow_forwards=forwards,generated_frames=forwards,time_queries=queries,held_inserted_frames=n*(factor-1)-forwards).items():
            if m[k]!=expected or execution.get(k,m[k])!=expected:raise ValueError('forward/hold accounting '+k)
        if m['owned_array_budget_bytes']!=cfg['state_budget_bytes'] or type(m['owned_array_peak_bytes'])is not int or not 0<m['owned_array_peak_bytes']<=cfg['state_budget_bytes']:raise ValueError('CPU array budget')
        expected=dict(engine=ENGINE,precision='float32',network='disabled',CPU_fallback=False,weight_reader='safetensors-pread',model_loads=1,scale=cfg['scale'],padding='replicate',alpha_transport='same-flow-mask-premultiplied-RGBA')
        if any(execution.get(k)!=v for k,v in expected.items()) or any(k not in execution for k in ('flow_forwards','generated_frames','time_queries')):raise ValueError('actual execution provider')
        if type(execution['cuda_peak_allocated_bytes'])is not int or execution['cuda_peak_allocated_bytes']<=0:raise ValueError('GPU execution')
    except (ValueError,KeyError,TypeError,AttributeError) as exc:raise error('WORKER_CONTRACT','补帧推理报告未通过协议、原帧或实际forward核验',cause=str(exc)) from exc

def decoder_command(base,source,plan):
    r=plan['range']
    return [*base,'-noautorotate','-i',source['path'],'-map',f"0:{source['stream_index']}",'-an','-sn','-dn','-vf',
        f"trim=start_frame={r['start_frame']}:end_frame={r['end_frame']},setsar=1,format=rgba",'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1']

def execute(root,job,plan,source,adapter,*,timeout,cancel_file=None,progress=None,operation_id=None):
    started=time.monotonic();work=job.path/'pipeline';work.mkdir();v=plan['video'];a=plan['audio'];padded=work/'aligned.wav'
    if not math.isfinite(timeout) or not 0<timeout<=604800:raise error('TIMEOUT','须指定有限正超时')
    def remaining():
        cancel(cancel_file);left=timeout-(time.monotonic()-started)
        if left<=0:raise AppError('TIMEOUT','补帧超过完整管道时间预算',exit_code=8)
        return left
    from .artifact_locks import artifact_entry,verification_summary
    from .reverse_video_clock import probe_frames
    from .errors import AppError
    remaining()
    if not verify_adapter(adapter)['ok']:raise error('ADAPTER_CHANGED','适配器字节变化，须重新登记')
    if artifact_entry(Path(source['path']),'input')['sha256']!=source['sha256']:raise error('SOURCE_CHANGED','源资产发生变化')
    ffmpeg=Path(ffmpeg_path()).resolve();ffmpeg_record=artifact_entry(ffmpeg,'ffmpeg')
    from .media import ffprobe_path
    ffprobe=Path(ffprobe_path()).resolve();ffprobe_record=artifact_entry(ffprobe,'ffprobe')
    if shutil.disk_usage(work).free<plan['estimated_workspace_bytes']+128*1024**2:raise error('DISK_BUDGET','可用磁盘不足保守工作空间估算')
    base=[str(ffmpeg),'-nostdin','-v','error','-threads','1','-filter_threads','1','-protocol_whitelist','file,pipe']
    def tool(command):
        result=run_process(command,timeout=remaining(),cancel_file=cancel_file)
        if result.returncode:raise error('MEDIA_TOOL','本地补帧媒体处理失败',stderr=result.stderr[-2500:])
        return result
    def hash_stream(path,role,filters=None):
        extra=['-vf',filters] if filters else []
        arguments=['-an','-pix_fmt','rgba','-fps_mode','passthrough'] if role=='v' else ['-vn','-c:a','pcm_f32le']
        value=tool([*base,'-i',str(path),'-map',f'0:{role}:0',*extra,*arguments,'-f','hash','-hash','sha256','pipe:1']).stdout.strip().lower()
        if not re.fullmatch('sha256=[0-9a-f]{64}',value):raise error('STREAM_HASH','媒体工具未返回完整流摘要')
        return 'sha256:'+value[7:]
    pcm_hash=None
    if a:
        selected=work/'selected.wav'
        if a['samples']:
            tool([*base,'-n','-i',source['path'],'-map',f"0:{a['stream_index']}",'-vn','-af',f"atrim=start_sample={a['start_sample']}:end_sample={a['end_sample']},asetpts=PTS-STARTPTS",'-c:a','pcm_f32le',str(selected)])
            probe=probe_media(selected);stream=next(s for s in probe['streams'] if s['codec_type']=='audio')
            if (probe['audio']['sample_rate'],probe['audio']['channels'])!=(a['sample_rate'],a['channels']) or int(stream['duration_ts'])*Fraction(stream['time_base'])*a['sample_rate']!=a['samples']:raise error('AUDIO_RANGE','实际选择样本数与原生时钟不符，未截断未知样本')
            tool([*base,'-n','-i',str(selected),'-af',f"adelay=delays={a['leading_zero_samples']}S:all=1,apad=whole_len={a['output_samples']},atrim=end_sample={a['output_samples']}",'-c:a','pcm_f32le',str(padded)])
        else:
            tool([*base,'-n','-f','lavfi','-i',f"anullsrc=r={a['sample_rate']}:cl={a['channels']}c",'-af',f"atrim=end_sample={a['output_samples']}",'-c:a','pcm_f32le',str(padded)])
        ap=probe_media(padded);stream=next(s for s in ap['streams'] if s['codec_type']=='audio')
        if int(stream['duration_ts'])*Fraction(stream['time_base'])*a['sample_rate']!=a['output_samples']:raise error('AUDIO_PADDING','PCM补零时钟不符')
        pcm_hash=hash_stream(padded,'a')
    expression=work/'packet-clock.txt';expression.write_text(packet_filter(plan['output_clock']),encoding='ascii',newline='\n')
    request={**plan,'source':source,'adapter':adapter,'response':str(work/'response.json'),'progress':str(work/'progress.json'),'ffmpeg':ffmpeg_record}
    request['request_sha256']=request_hash(request);request_path=work/'request.json';atomic_write_json(request_path,request)
    staged=work/'generated.mov';denominator=Fraction(plan['output_clock']['time_base']).denominator
    encoder=[*base,'-n','-f','rawvideo','-pixel_format','rgba','-video_size',f"{v['width']}x{v['height']}",'-framerate','30','-i','pipe:0']
    if a:encoder+=['-protocol_whitelist','file,pipe','-i',str(padded)]
    encoder+=['-map','0:v:0']+(['-map','1:a:0','-c:a','pcm_f32le'] if a else [])
    encoder+=['-c:v','qtrle','-pix_fmt','argb','-fps_mode','passthrough','-enc_time_base',f'1/{denominator}',
        '-/bsf:v',str(expression),'-video_track_timescale',str(denominator),'-map_metadata','-1',str(staged)]
    commands=[decoder_command(base,source,plan),[adapter['executable'],'-I','-B','-u','-X','utf8',str(Path(__file__).with_name('interpolation_worker.py')),str(request_path)],encoder]
    diagnostic=Session(root,plan,adapter,operation_id);diagnostic.prepare(work,request);processes=[];cleanup=[]
    try:
        with contextlib.ExitStack() as stack:
            assign=stack.enter_context(_windows_job());logs=[stack.enter_context((work/(name+'.log')).open('w+b')) for name in ('decoder','worker','encoder')]
            try:
                previous=None
                for i,(role,command) in enumerate(zip(('decoder','worker','encoder'),commands)):
                    remaining();diagnostic.start_failure_role=role
                    p=subprocess.Popen(command,stdin=previous.stdout if previous else subprocess.DEVNULL,stdout=subprocess.PIPE if i<2 else subprocess.DEVNULL,
                        stderr=logs[i],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    processes.append(p);diagnostic.processes.started(role,p);assign(p);diagnostic.start_failure_role=None
                    if previous:previous.stdout.close()
                    previous=p
                diagnostic.stage='running';last=-1
                while any(p.poll()is None for p in processes):
                    remaining();diagnostic.observe()
                    if any(p.poll()not in (None,0) for p in processes):break
                    if sum(p.stat().st_size for p in work.iterdir() if p.is_file())>plan['storage_budget_bytes'] or staged.exists() and staged.stat().st_size>MAX_INPUT_BYTES:raise error('OUTPUT_BUDGET','实际输出超过存储预算')
                    if progress:
                        with contextlib.suppress(OSError,ValueError,KeyError,TypeError):
                            frame=json.loads((work/'progress.json').read_bytes())['frames']
                            if type(frame)is int and 0<=frame<=v['frames'] and frame!=last:progress(frame,v['frames']);last=frame;diagnostic.last_reported_frame=frame
                    time.sleep(.05)
                if any(p.poll()!=0 for p in processes):raise AppError('INTERPOLATION_PIPELINE_FAILED','原生补帧管道失败',exit_code=6,cause=diagnostic.failure_text())
            finally:
                if diagnostic.start_failure_role:diagnostic.processes.start_failed(diagnostic.start_failure_role)
                diagnostic.processes.before_cleanup()
                for p in processes:
                    if p.poll()is None:
                        try:p.kill()
                        except OSError:cleanup.append(dict(code='INTERPOLATION_CHILD_KILL_FAILED',pid=p.pid))
                for p in processes:
                    try:p.wait(timeout=10)
                    except (OSError,subprocess.TimeoutExpired):cleanup.append(dict(code='INTERPOLATION_CHILD_WAIT_FAILED',pid=p.pid))
                    finally:
                        if p.stdout:p.stdout.close()
                diagnostic.processes.finished();diagnostic.cleanup_warnings.extend(cleanup)
            if cleanup:raise error('CLEANUP','补帧子进程未能完整回收')
        diagnostic.stage='validating-response'
        if not (work/'response.json').is_file() or (work/'response.json').stat().st_size>2*1024**2:raise error('WORKER_RESPONSE','推理报告缺失或过大')
        response=json.loads((work/'response.json').read_bytes());validate_response(response,request)
        diagnostic.stage='verifying-output';result_probe=probe_media(staged);vp=result_probe['video'];ap=result_probe['audio']
        if (vp['width'],vp['height'],vp['codec'],vp['pix_fmt'])!=(v['width'],v['height'],'qtrle','argb'):raise error('OUTPUT_VIDEO','编码后无损RGBA格式不符')
        points,durations,stream,_=probe_frames(staged,timeout=remaining(),cancel_file=cancel_file)
        actual=dict(time_base=stream['time_base'],pts=list(points),durations=list(durations))
        if actual!=plan['output_clock']:raise error('OUTPUT_CLOCK','编码后每帧PTS/持续时间与原生细分时钟不符',expected_sha256=clock_digest(plan['output_clock']),actual_sha256=clock_digest(actual))
        if a and (ap['codec'],ap['sample_rate'],ap['channels'])!=('pcm_f32le',a['sample_rate'],a['channels']) or not a and ap.get('codec'):raise error('OUTPUT_AUDIO','编码后PCM格式或存在性不符')
        rgba=hash_stream(staged,'v');anchors=hash_stream(staged,'v',f"select=not(mod(n\\,{v['factor']}))")
        pcm=hash_stream(staged,'a') if a else None
        if rgba!=response['metrics']['rgba_sha256'] or anchors!=response['metrics']['source_rgba_sha256'] or pcm!=pcm_hash:raise error('ROUNDTRIP','完整RGBA、每个源帧或PCM编码往返摘要不一致')
        remaining()
        if not verify_adapter(adapter)['ok'] or artifact_entry(Path(source['path']),'input')['sha256']!=source['sha256'] or artifact_entry(ffmpeg,'ffmpeg')!=ffmpeg_record or artifact_entry(ffprobe,'ffprobe')!=ffprobe_record:raise error('INPUT_CHANGED','发布前源/模型/媒体工具变化')
        from .interpolation_plan import recipe
        return staged,dict(protocol=PROTOCOL,recipe=recipe(plan,source),sha256='sha256:'+sha256_file(staged),probe=result_probe,worker=response,
            complete_RGBA_roundtrip_verified=True,all_original_anchors_roundtrip_verified=True,all_native_PTS_and_durations_verified=True,
            complete_PCM_roundtrip_verified=bool(a),PCM_sha256=pcm_hash,output_clock_sha256=clock_digest(actual),ffmpeg=ffmpeg_record,ffprobe=ffprobe_record,
            artifact_verification=verification_summary(),elapsed_seconds=time.monotonic()-started,
            cleanup=dict(processes=[dict(role=r,pid=p.pid,returncode=p.returncode,exited=p.poll()is not None,stdout_closed=p.stdout is None or p.stdout.closed) for r,p in zip(('decoder','worker','encoder'),processes)],warnings=cleanup),natural_quality_accepted=False)
    except BaseException as exc:diagnostic.capture(work,exc);raise
