"""Offline Windows-owned DF3 worker; decoder/resamplers inherit its process job."""
import json,math,os,shutil,sys,time,traceback
from pathlib import Path
from array import array

def main():
    request_path=Path(sys.argv[1]);request=json.loads(request_path.read_bytes())
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from ai_ad_editor.rvm_worker import install_network_guard
    from ai_ad_editor.local_enhancement import ENGINE,PROTOCOL,verify_adapter,error
    from ai_ad_editor.enhancement_plan import sample_range,digest
    from ai_ad_editor.enhancement_dsp import process_pcm
    from ai_ad_editor.artifact_locks import artifact_entry,verification_scope
    from ai_ad_editor.utils import atomic_write_json,run_process,sha256_file
    from ai_ad_editor import native_audio_clock as clock
    started=time.monotonic();events=[];install_network_guard(events)
    response=dict(protocol=PROTOCOL,status='failed',network='disabled',blocked_network_events=events)
    work=request_path.parent;marker=Path(request['cancel_file']) if request.get('cancel_file') else None
    def check():clock.cancel(marker)
    def phase(name,done=0,total=1):
        check();atomic_write_json(work/'progress.json',dict(phase=name,done=done,total=total,worker_pid=os.getpid()))
    def tool(argv):
        check();completed=run_process(argv,timeout=max(1,request['timeout_seconds']-(time.monotonic()-started)),cancel_file=marker)
        if completed.returncode:raise error('MEDIA_TOOL','增强音频处理失败',stderr=completed.stderr[-2500:])
    try:
        if request.get('protocol')!=PROTOCOL or request.get('network')!='disabled' or request.get('request_sha256')!=digest({k:v for k,v in request.items() if k!='request_sha256'}):raise error('REQUEST','增强请求摘要无效')
        with verification_scope():
            adapter=request['adapter'];source=request['source']
            if not verify_adapter(adapter)['ok'] or artifact_entry(Path(source['path']),'source')['sha256']!=source['sha256']:raise error('INPUT_CHANGED','增强模型或源文件改变')
            ff=request['ffmpeg']['path']
            if artifact_entry(Path(ff),'ffmpeg')!=request['ffmpeg']:raise error('MEDIA_TOOL_CHANGED','FFmpeg字节发生改变')
            runtime=work/'runtime'
            for key,name in {'TEMP':'temp','TMP':'temp','TMPDIR':'temp','HF_HOME':'hf','TORCH_HOME':'torch','XDG_CACHE_HOME':'cache'}.items():
                directory=runtime/name;directory.mkdir(parents=True,exist_ok=True);os.environ[key]=str(directory)
            os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
            phase('indexing-native-audio-clock')
            native_recipe=clock.recipe(source['path'],source['sha256'])
            rows,info,stats=clock.probe(native_recipe,marker)
            rate=stats['native_sample_rate'];channels=stats['channels'];logical=stats['logical_frames']
            if not 8000<=rate<=96000 or channels not in (1,2) or not 0<logical<=1800*rate:raise error('INPUT_FORMAT','原始音频须为8..96kHz、单/双声道，完整原生时钟不超过1800秒')
            selected=sample_range(request['selection'],rate,logical);n=selected['samples'];model_n=max(1,round(n*48000/rate))
            estimate=logical*channels*4+n*channels*20+model_n*channels*12+64*1024**2
            if estimate>request['storage_budget_bytes'] or estimate+64*1024**2>shutil.disk_usage(work).free:raise error('STORAGE','原生源、重采样与输出的保守存储估算超过预算',estimated_bytes=estimate)
            phase('decoding-native-clock')
            native=work/'native.f32';decoded_hash=clock._decode(native_recipe,rows,stats,native,marker)
            import numpy as np
            full=np.memmap(native,dtype='<f4',mode='r',shape=(logical,channels))
            original=work/'selected.f32'
            try:
                with original.open('xb') as out:
                    for start in range(selected['start_sample'],selected['end_sample'],65536):
                        check();block=np.asarray(full[start:min(selected['end_sample'],start+65536)])
                        if not np.isfinite(block).all():raise error('NONFINITE','源包含非有限PCM')
                        out.write(block.tobytes())
            finally:full._mmap.close()
            opts=request['options'];strength=opts['strength'];limit=opts['attenuation_limit_db']
            wet=strength*(1-10**(-limit/20)) if limit is not None else strength
            final=work/'enhanced.f32';model_metadata=None
            if wet==0:
                shutil.copyfile(original,final);metrics=dict(samples=model_n,channels=channels,model_calls=0,segments=0,bypass=True)
            else:
                phase('resampling-to-model-clock')
                model_input=work/'model-input.f32'
                if rate==48000:shutil.copyfile(original,model_input)
                else:tool([ff,'-nostdin','-v','error','-n','-f','f32le','-ar',str(rate),'-ac',str(channels),'-i',str(original),
                    '-af',f'aresample=48000:filter_size=32,apad=whole_len={model_n},atrim=end_sample={model_n}',
                    '-c:a','pcm_f32le','-f','f32le',str(model_input)])
                if model_input.stat().st_size!=model_n*channels*4:raise error('MODEL_CLOCK','模型48kHz输入样本数不符')
                from ai_ad_editor.enhancement_model import load_predictor
                predictor,model_metadata=load_predictor(adapter['model_path'],adapter['settings'],phase=lambda name:phase(name))
                phase('neural-enhancement')
                model_output=work/'model-output.f32'
                cfg=adapter['settings']
                metrics=process_pcm(model_input,model_output,channels=channels,segment_seconds=cfg['segment_seconds'],overlap=cfg['overlap'],
                    strength=1.,attenuation_limit_db=None,infer=predictor,check=check,
                    progress=lambda done,total:phase('neural-enhancement',done,total))
                model_metadata=predictor.finish();del predictor
                phase('resampling-to-native-clock')
                native_wet=work/'wet-native.f32'
                if rate==48000:shutil.copyfile(model_output,native_wet)
                else:tool([ff,'-nostdin','-v','error','-n','-f','f32le','-ar','48000','-ac',str(channels),'-i',str(model_output),
                    '-af',f'aresample={rate}:filter_size=32,apad=whole_len={n},atrim=end_sample={n}',
                    '-c:a','pcm_f32le','-f','f32le',str(native_wet)])
                if native_wet.stat().st_size!=n*channels*4:raise error('OUTPUT_CLOCK','原生输出样本数不符')
                dry=np.memmap(original,dtype='<f4',mode='r',shape=(n,channels));processed=np.memmap(native_wet,dtype='<f4',mode='r',shape=(n,channels))
                try:
                    with final.open('xb') as out:
                        for first in range(0,n,65536):
                            check();a=np.asarray(dry[first:first+65536]);b=np.asarray(processed[first:first+65536]);mixed=a+(b-a)*np.float32(wet)
                            if not np.isfinite(mixed).all():raise error('NONFINITE','增强混合包含非有限PCM')
                            out.write(mixed.tobytes())
                finally:dry._mmap.close();processed._mmap.close()
            phase('encoding-lossless-native-audio')
            wav=work/'enhanced.wav'
            tool([ff,'-nostdin','-v','error','-n','-f','f32le','-ar',str(rate),'-ac',str(channels),'-i',str(final),'-map_metadata','-1','-c:a','pcm_f32le',str(wav)])
            check()
            if not verify_adapter(adapter)['ok'] or artifact_entry(Path(source['path']),'source')['sha256']!=source['sha256']:raise error('INPUT_CHANGED','发布前模型或源字节改变')
            if events:raise error('NETWORK','推理出现被拒绝的网络请求')
            final_map=np.memmap(final,dtype='<f4',mode='r',shape=(n,channels));peak=power=0.
            try:
                for i in range(0,n,65536):
                    check();block=np.asarray(final_map[i:i+65536]);peak=max(peak,float(np.abs(block).max()));power+=float(np.square(block,dtype=np.float64).sum())
            finally:final_map._mmap.close()
            response.update(status='succeeded',request_sha256=request['request_sha256'],source_sha256=source['sha256'],adapter_sha256=adapter['sha256'],
                range=selected,channels=channels,model_samples=model_n,model=model_metadata,metrics=metrics,
                effective_wet=wet,native_clock=stats,decoded_pcm_sha256=decoded_hash,
                input_PCM_sha256='sha256:'+sha256_file(original),output_PCM_sha256='sha256:'+sha256_file(final),
                output_bytes=n*channels*4,output_peak=peak,output_rms=math.sqrt(power/(n*channels)),
                output_sha256='sha256:'+sha256_file(wav),output_wav_bytes=wav.stat().st_size,
                resampler='ffmpeg-swr-filter_size32-explicit-nearest-sample-count' if rate!=48000 and wet else 'none',
                native_rate_preserved=True,channel_count_preserved=True,estimated_storage_bytes=estimate,
                bypass_bit_exact=wet==0,natural_quality_accepted=False)
    except BaseException as exc:response.update(error_type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()[-5000:])
    response['elapsed_seconds']=time.monotonic()-started
    atomic_write_json(work/'response.json',response)
    return 0 if response['status']=='succeeded' else 1

if __name__=='__main__':raise SystemExit(main())
