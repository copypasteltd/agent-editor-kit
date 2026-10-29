"""Isolated local VACE worker, paired source/mask input and lossless RGBA output."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time


def infer(request,response, *, source=None, sink=None, model_cache=None):
    from ai_ad_editor.local_matting import request_hash
    from ai_ad_editor.local_inpainting import mask_unchanged, normalize_options
    from ai_ad_editor.local_vace import VACE_ENGINE,VACE_PROTOCOL,normalize_generation,verify_adapter,window_plan
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.utils import atomic_write_json,sha256_file
    from ai_ad_editor.vace_frames import process_frames
    if request.get('engine')!=VACE_ENGINE or request.get('protocol')!=VACE_PROTOCOL or request.get('network')!='disabled' or request_hash(request)!=request.get('request_sha256'):raise ValueError('VACE_REQUEST_INVALID')
    adapter=request['adapter'];info=request['video'];generation=request['generation']
    if not verify_adapter(adapter)['ok'] or not mask_unchanged(request) or normalize_options(**request['inpainting'])!=request['inpainting']:raise ValueError('VACE_INPUT_INTEGRITY_FAILED')
    if normalize_generation(**generation,frames=info['frames'])!=generation or request['windows']!=window_plan(info['frames'],generation):raise ValueError('VACE_GENERATION_PLAN_INVALID')
    if 'sha256:'+sha256_file(Path(request['source']['path']))!=request['source']['sha256']:raise ValueError('VACE_SOURCE_CHANGED')
    os.environ['AI_AD_EDITOR_RUNTIME_DIR']=request['runtime_root'];configure_local_runtime()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
    import numpy as np
    import torch
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():raise ValueError('VACE_CUDA_BFLOAT16_UNAVAILABLE_NO_FALLBACK')
    if model_cache is None or not model_cache.torch_configured:
        torch.set_num_threads(adapter['settings']['threads']);torch.set_num_interop_threads(1)
        if model_cache is not None: model_cache.torch_configured = True
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.cuda.reset_peak_memory_stats()
    predictor=None;metadata={};completed=0;last=0.
    def phase(name):atomic_write_json(Path(request['progress']),{'frames':completed,'stage':name})
    def predict(images,masks,options):
        nonlocal predictor,metadata
        if predictor is None:
            if model_cache is not None:
                predictor, metadata = model_cache.predictor_for(adapter, generation, phase)
            else:
                from ai_ad_editor.vace_model import load_predictor
                predictor,metadata=load_predictor(adapter['model_path'],adapter['settings'],generation,progress=phase)
        return predictor(images,masks,options)
    def progress(frame):
        nonlocal completed,last
        completed=frame
        if frame==info['frames'] or time.monotonic()-last>=.5:phase('writing-lossless-rgba');last=time.monotonic()
    metrics=process_frames(source if source is not None else sys.stdin.buffer,sink if sink is not None else sys.stdout.buffer,width=info['width'],height=info['height'],frames=info['frames'],
                          infer=predict,options=request['inpainting'],generation=generation,channel=request['mask']['channel'],budget=adapter['settings']['state_budget_bytes'],progress=progress)
    phase('verifying-inputs-after-generation')
    if not verify_adapter(adapter)['ok'] or not mask_unchanged(request) or 'sha256:'+sha256_file(Path(request['source']['path']))!=request['source']['sha256']:raise ValueError('VACE_INPUT_CHANGED_DURING_GENERATION')
    response.update(status='succeeded',metrics=metrics,providers=['torch-cuda'],versions=metadata.get('versions',{'python':sys.version.split()[0],'numpy':np.__version__,'torch':torch.__version__}),
                    model_execution=metadata,model_loaded=predictor is not None,cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated())


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
    request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    events=[];response={'protocol':request.get('protocol'),'engine':request.get('engine'),'network':'disabled','blocked_network_events':events,
        'request_sha256':request.get('request_sha256'),'adapter_sha256':request.get('adapter',{}).get('sha256'),'source_sha256':request.get('source',{}).get('sha256'),
        'mask_sha256':request.get('mask',{}).get('sha256'),'mask_plan_sha256':request.get('mask',{}).get('plan_sha256'),'inpainting':request.get('inpainting'),
        'generation':request.get('generation'),'status':'failed'}
    if 'outpainting' in request: response['outpainting'] = request['outpainting']
    started=time.monotonic();install_network_guard(events)
    try:
        from ai_ad_editor.artifact_locks import verification_scope
        with verification_scope() as verification:
            infer(request,response)
            response['artifact_verification']=verification.summary() if verification else {'mode':'uncached-full-hashes'}
    except Exception as exc:
        response['error']=type(exc).__name__+': '+str(exc)
        from ai_ad_editor.cuda_admission import CudaAdmissionError
        if isinstance(exc,CudaAdmissionError):response['gpu_admission_failure']=exc.report
    response['elapsed_seconds']=time.monotonic()-started;atomic_write_json(Path(request['response']),response)
    return 0 if response['status']=='succeeded' else 1


if __name__=='__main__':raise SystemExit(main())
