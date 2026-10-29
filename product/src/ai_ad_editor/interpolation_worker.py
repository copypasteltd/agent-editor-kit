"""Offline native CUDA RIFE worker; stdin/stdout contain only decoded RGBA."""
import json,os,sys,time
from pathlib import Path

def infer(request,response):
    from ai_ad_editor.local_interpolation import ENGINE,PROTOCOL,verify_adapter
    from ai_ad_editor.interpolation_plan import configuration
    from ai_ad_editor.local_matting import request_hash
    from ai_ad_editor.utils import atomic_write_json
    from ai_ad_editor.artifact_locks import artifact_entry
    if (request.get('engine'),request.get('protocol'),request.get('network'))!=(ENGINE,PROTOCOL,'disabled') or request_hash(request)!=request.get('request_sha256'):raise ValueError('INTERPOLATION_REQUEST_INVALID')
    adapter=request['adapter'];source=request['source'];info=request['video']
    if not verify_adapter(adapter)['ok']:raise ValueError('INTERPOLATION_ADAPTER_CHANGED')
    if artifact_entry(Path(source['path']),'source')['sha256']!=source['sha256']:raise ValueError('INTERPOLATION_INPUT_CHANGED')
    normalized=configuration(source,request['source_clock'],settings=adapter['settings'],**request['range'],factor=info['factor'],
        storage_budget_mib=request['storage_budget_bytes']//1024**2,**request['options'])
    if any(request.get(k)!=v for k,v in normalized.items()):raise ValueError('INTERPOLATION_PLAN_INVALID')
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    completed=0;last=0.
    def phase(stage):atomic_write_json(Path(request['progress']),dict(frames=completed,stage=stage))
    from ai_ad_editor.interpolation_model import load_predictor
    predictor,metadata=load_predictor(adapter['model_path'],adapter['settings'],width=info['width'],height=info['height'],phase=phase)
    def progress(frame):
        nonlocal completed,last
        completed=frame
        if frame==info['frames'] or time.monotonic()-last>.25:phase('writing-lossless-interpolated-rgba');last=time.monotonic()
    from ai_ad_editor.interpolation_frames import process_frames
    metrics=process_frames(sys.stdin.buffer,sys.stdout.buffer,width=info['width'],height=info['height'],frames=info['source_frames'],factor=info['factor'],
        predictor=predictor,options=request['options'],budget=adapter['settings']['state_budget_bytes'],progress=progress)
    execution=predictor.finish()
    if not verify_adapter(adapter)['ok'] or artifact_entry(Path(source['path']),'source')['sha256']!=source['sha256']:raise ValueError('INTERPOLATION_INPUT_CHANGED_DURING_INFERENCE')
    response.update(status='succeeded',metrics=metrics,model_execution=execution,model_loaded=True,providers=['torch-cuda'],versions=execution['versions'])

def main():
    application_root = str(Path(__file__).resolve().parents[1])
    sys.path.insert(0, application_root)
    try:
        import ai_ad_editor
    finally:
        sys.path.remove(application_root)
    if Path(ai_ad_editor.__file__).resolve() != Path(__file__).resolve().with_name('__init__.py'):
        raise RuntimeError('NATIVE_WORKER_APPLICATION_CHANGED')
    from ai_ad_editor.rvm_worker import install_network_guard
    from ai_ad_editor.utils import atomic_write_json
    path=Path(sys.argv[1])
    if not 1<=path.stat().st_size<=16*1024**2:raise ValueError('INTERPOLATION_REQUEST_SIZE')
    request=json.loads(path.read_bytes());events=[];install_network_guard(events);started=time.monotonic()
    response=dict(status='failed',protocol=request.get('protocol'),engine=request.get('engine'),network='disabled',blocked_network_events=events,
        request_sha256=request.get('request_sha256'),adapter_sha256=request.get('adapter',{}).get('sha256'),source_sha256=request.get('source',{}).get('sha256'))
    try:
        from ai_ad_editor.artifact_locks import verification_scope
        with verification_scope() as verification:
            infer(request,response);response['artifact_verification']=verification.summary() if verification else {'mode':'uncached-full-hashes'}
    except Exception as exc:
        response['error']=type(exc).__name__+': '+str(exc)
        from ai_ad_editor.cuda_admission import CudaAdmissionError
        if isinstance(exc,CudaAdmissionError):response['gpu_admission_failure']=exc.report
    response['elapsed_seconds']=time.monotonic()-started;atomic_write_json(Path(request['response']),response)
    return 0 if response['status']=='succeeded' else 1

if __name__=='__main__':raise SystemExit(main())
