"""One bounded offline native process; a model is reused for the complete batch."""
from __future__ import annotations

import json
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import time
import traceback


def main() -> int:
    sys.dont_write_bytecode=True
    application_root = str(Path(__file__).resolve().parents[1])
    # Pin only our own application package. Leaving the controller's site
    # directory first would replace the separately registered model runtime's
    # NumPy/Pillow in an installed bundle, invalidating its attested profile.
    sys.path.insert(0, application_root)
    try:
        import ai_ad_editor
    finally:
        sys.path.remove(application_root)
    if Path(ai_ad_editor.__file__).resolve() != Path(__file__).resolve().with_name('__init__.py'):
        raise RuntimeError('SEMANTIC_APPLICATION_CHANGED')
    from ai_ad_editor.semantic_contract import PROTOCOL, fingerprint, json_object, local_file
    request=json_object(Path(sys.argv[1]),max_bytes=2*1024**2)
    response_path=Path(request['response'])
    (response_path.parent/'worker-started.json').write_text(json.dumps(dict(pid=os.getpid(),
        request_sha256=request.get('request_sha256'),task=request.get('task')))+'\n',encoding='utf-8',newline='\n')
    started=time.monotonic()
    response=dict(protocol=PROTOCOL,status='failed',network='disabled',blocked_network_events=[],
                  request_sha256=request.get('request_sha256'))
    phases={}; previous=[None,started]
    def phase(name):
        now=time.monotonic()
        if previous[0] is not None:
            phases[previous[0]]=phases.get(previous[0],0.)+now-previous[1]
        previous[:]=[name,now]
        (response_path.parent/'worker-phase.json').write_text(json.dumps(dict(pid=os.getpid(),
            phase=name,elapsed_seconds=now-started,request_sha256=request.get('request_sha256')))+'\n',
            encoding='utf-8',newline='\n')
    cleanup=ExitStack()
    try:
        phase('request-and-environment')
        if (request.get('protocol')!=PROTOCOL or request.get('network')!='disabled'
                or request.get('request_sha256')!=fingerprint({k:v for k,v in request.items() if k!='request_sha256'})):
            raise ValueError('SEMANTIC_REQUEST_INVALID')
        from ai_ad_editor.execution_control import operation_budget
        cleanup.enter_context(operation_budget(request.get('budget_seconds',600),request.get('cancel_file'),root=Path.cwd()))
        from ai_ad_editor.whisper_worker import install_network_guard
        install_network_guard(response['blocked_network_events'])
        runtime=Path(request['runtime_root'])
        for key,name in {'TEMP':'temp','TMP':'temp','TMPDIR':'temp','HF_HOME':'hf','HF_HUB_CACHE':'hf/hub',
                         'TORCH_HOME':'torch','XDG_CACHE_HOME':'cache'}.items():
            path=runtime/name;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
                          DO_NOT_TRACK='1',TOKENIZERS_PARALLELISM='false',TQDM_DISABLE='1')
        phase('native-imports')
        from ai_ad_editor.artifact_locks import artifact_entry,verification_scope,verification_summary
        from ai_ad_editor.semantic_contract import DIMENSION, check_vectors, verify_adapter
        from ai_ad_editor.utils import sha256_file
        import numpy as np
        import torch
        import transformers
        import PIL
        from PIL import Image, ImageOps
        import tokenizers
        import safetensors
        from transformers import AutoTokenizer, SiglipImageProcessor, SiglipModel
        from transformers.models.siglip import modeling_siglip
        modules=dict(torch=torch,transformers=transformers,numpy=np,PIL=PIL,tokenizers=tokenizers,
                     safetensors=safetensors,siglip=modeling_siglip)
        versions={key:str(getattr(value,'__version__','bundled-with-transformers')) for key,value in modules.items()}
        versions['python']=sys.version.split()[0]
        module_paths={key:str(Path(value.__file__).resolve()) for key,value in modules.items()}
        response.update(versions=versions,module_paths=module_paths)
        phase('adapter-verification')
        if request['task']=='inspect':
            files={Path(path) for path in module_paths.values()}
            # Pin the selected Python/native inference components, including all
            # shipped Torch DLLs. This is not a claim to freeze every OS DLL.
            for module in (torch,np,PIL,tokenizers,safetensors):
                directory=Path(module.__file__).parent
                files.update(directory.glob('*.pyd'))
                files.update((directory/'lib').glob('*.dll'))
            files.update((Path(np.__file__).parent/'_core').glob('*.pyd'))
            files.update((Path(np.__file__).parent.parent/'numpy.libs').glob('*.dll'))
            files.update(p for name in ('python3.dll','python313.dll','python313.zip')
                         if (p:=Path(sys.executable).with_name(name)).is_file())
            if not 1<=len(files)<=128:raise ValueError('SEMANTIC_RUNTIME_INVENTORY_BUDGET')
            with verification_scope():
                response['runtime_artifacts']=[artifact_entry(local_file(path),'runtime') for path in sorted(files)]
                response['verification_scope']=verification_summary()
            response.update(status='succeeded',model_forward_calls=0)
        else:
            with verification_scope():
                adapter=request['adapter']
                if not verify_adapter(adapter)['ok']:raise ValueError('SEMANTIC_ADAPTER_INTEGRITY_FAILED')
                if versions!=adapter['runtime_versions'] or module_paths!=adapter['runtime_modules']:
                    raise ValueError('SEMANTIC_RUNTIME_CHANGED')
                device=request['device']; index=request['device_index']
                if device not in ('cpu','cuda') or type(index) is not int or index<0:
                    raise ValueError('SEMANTIC_DEVICE_INVALID')
                torch.set_num_threads(adapter['threads'])
                actual_device=f'cuda:{index}' if device=='cuda' else 'cpu'
                if device=='cuda':
                    if not torch.cuda.is_available() or index>=torch.cuda.device_count():
                        raise RuntimeError('SEMANTIC_CUDA_UNAVAILABLE')
                    torch.cuda.set_device(index);torch.cuda.reset_peak_memory_stats(index)
                dtype=torch.bfloat16 if device=='cuda' and torch.cuda.is_bf16_supported() else torch.float32
                items=request['items'];batch_size=request['batch_size']
                if (not isinstance(items,list) or not 1<=len(items)<=4096 or type(batch_size) is not int
                        or not 1<=batch_size<=32 or request['task'] not in ('text','image')):
                    raise ValueError('SEMANTIC_ITEMS_INVALID')
                if len({i['id'] for i in items})!=len(items):raise ValueError('SEMANTIC_ITEM_IDS_DUPLICATE')
                marker=Path(request['cancel_file']) if request.get('cancel_file') else None
                def cancelled():
                    if marker is not None and marker.exists():raise RuntimeError('SEMANTIC_CANCELLED')
                cancelled()
                tokenizer=None
                if request['task']=='text':
                    tokenizer=AutoTokenizer.from_pretrained(adapter['model_path'],local_files_only=True,trust_remote_code=False)
                    for item in items:
                        text=item['text']
                        if not isinstance(text,str) or not text.strip() or len(text)>1024:
                            raise ValueError('SEMANTIC_QUERY_INVALID')
                        ids=tokenizer(text.lower(),padding=False,truncation=False,add_special_tokens=True)['input_ids']
                        if len(ids)>64:raise ValueError('SEMANTIC_TEXT_TOKEN_BUDGET: input exceeds 64 tokens; not truncated')
                else:
                    for item in items:
                        path=local_file(item['path'])
                        entry=artifact_entry(path,'semantic-image-input')
                        if entry['bytes']>50*1024**2 or entry['sha256']!=item['sha256']:
                            raise ValueError('SEMANTIC_INPUT_HASH_MISMATCH_OR_BUDGET')
                load_start=time.monotonic()
                phase('model-loading')
                model,loading=SiglipModel.from_pretrained(adapter['model_path'],local_files_only=True,
                    trust_remote_code=False,use_safetensors=True,dtype=dtype,output_loading_info=True)
                if any(loading.get(key) for key in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')):
                    raise ValueError('SEMANTIC_MODEL_KEYS_MISMATCH')
                model=model.to(actual_device).eval()
                processor=SiglipImageProcessor.from_pretrained(adapter['model_path'],local_files_only=True)
                if device=='cuda':torch.cuda.synchronize(index)
                load_seconds=time.monotonic()-load_start
                phase('inference')
                values=[];calls=0;image_sizes=[]
                infer_start=time.monotonic()
                with torch.inference_mode():
                    for offset in range(0,len(items),batch_size):
                        cancelled();chunk=items[offset:offset+batch_size]
                        if request['task']=='text':
                            inputs=tokenizer([i['text'].lower() for i in chunk],padding='max_length',max_length=64,
                                             truncation=False,return_tensors='pt')
                            output=model.get_text_features(input_ids=inputs['input_ids'].to(actual_device))
                        else:
                            images=[]
                            try:
                                for item in chunk:
                                    with Image.open(item['path']) as original:
                                        if original.width*original.height>32_000_000:
                                            raise ValueError('SEMANTIC_IMAGE_PIXEL_BUDGET')
                                        image=ImageOps.exif_transpose(original).convert('RGB')
                                        images.append(image);image_sizes.append([image.width,image.height])
                                inputs=processor(images=images,return_tensors='pt')
                                output=model.get_image_features(pixel_values=inputs['pixel_values'].to(device=actual_device,dtype=dtype))
                            finally:
                                for image in images:image.close()
                        tensor=output.pooler_output if hasattr(output,'pooler_output') else output
                        tensor=tensor.float()
                        norms=tensor.norm(dim=-1,keepdim=True)
                        if not torch.isfinite(tensor).all() or torch.any(norms<=0):
                            raise ValueError('SEMANTIC_NONFINITE_FEATURES')
                        values.append((tensor/norms).cpu().numpy());calls+=1
                if device=='cuda':torch.cuda.synchronize(index)
                inference_seconds=time.monotonic()-infer_start
                array=check_vectors(np.concatenate(values,axis=0),len(items))
                cancelled()
                output=Path(request['output'])
                with output.open('xb') as stream:
                    stream.write(array.astype('<f4',copy=False).tobytes(order='C'));stream.flush();os.fsync(stream.fileno())
                if response['blocked_network_events']:raise RuntimeError('SEMANTIC_NETWORK_ATTEMPT_REJECTED')
                response.update(status='succeeded',output=str(output),output_sha256='sha256:'+sha256_file(output),
                    rows=len(items),dimension=DIMENSION,dtype='float32-little-endian',item_ids=[i['id'] for i in items],
                    task=request['task'],adapter_sha256=adapter['sha256'],device=device,device_index=index,
                    actual_device=torch.cuda.get_device_name(index) if device=='cuda' else 'cpu',
                    model_dtype=str(dtype),load_seconds=round(load_seconds,6),inference_seconds=round(inference_seconds,6),
                    peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(index) if device=='cuda' else None,
                    peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(index) if device=='cuda' else None,
                    model_loads=1,model_forward_calls=calls,batch_size=batch_size,image_sizes=image_sizes,
                    verification_scope=verification_summary(),
                    model_loading_keys_verified=True,text_normalization='lowercase; max_length=64; no truncation',
                    model_reuse_scope='complete current batch only; no persistent model service')
    except Exception as exc:
        message=str(exc)
        from ai_ad_editor.errors import AppError
        code=exc.code if isinstance(exc,AppError) else message.split(':',1)[0] if message.startswith('SEMANTIC_') else 'SEMANTIC_WORKER_FAILED'
        if request.get('device')=='cuda' and isinstance(exc,RuntimeError) and any(s in message.lower() for s in ('cuda','cublas','cudnn','out of memory')):
            code='SEMANTIC_CUDA_FAILED'
        response.update(code=code,error_type=type(exc).__name__,message=message,traceback=traceback.format_exc()[-6000:])
    finally:
        cleanup.close()
    phase('terminal')
    response['phase_seconds']={key:round(value,6) for key,value in phases.items()}
    response['elapsed_seconds']=round(time.monotonic()-started,6)
    response_path.write_text(json.dumps(response,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return 0 if response['status']=='succeeded' else 1


if __name__=='__main__':raise SystemExit(main())
