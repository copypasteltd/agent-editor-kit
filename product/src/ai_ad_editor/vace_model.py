"""Staged native CUDA loading of existing fixed Wan VACE components."""
from __future__ import annotations

import gc
import copy
import threading
from pathlib import Path
import time


WEIGHT_FILES = {
    'text_encoder': [f'model-{i:05d}-of-00003.safetensors' for i in range(1, 4)],
    'transformer': [f'diffusion_pytorch_model-{i:05d}-of-00002.safetensors' for i in range(1, 3)],
    'vae': ['diffusion_pytorch_model.safetensors'],
}


def prompt_identity(generation):
    """One resident session retains exactly one explicit text embedding pair."""
    return tuple(generation[key] for key in ('prompt', 'negative_prompt', 'prompt_max_tokens'))


def load_local_weights(loader, directory, *, read_report, **options):
    """Select the public pread backend in this isolated worker's load call only.

    Transformers holds a local safe_open alias, while Diffusers uses the alias
    in safetensors.torch. Restore both even on loader or reader failure. Existing
    artifact locks and hashes remain responsible for the complete weight bytes.
    """
    import safetensors
    import safetensors.torch as tensor_io
    import transformers.modeling_utils as transformer_io
    directory = Path(directory).resolve(strict=True)
    expected = WEIGHT_FILES.get(directory.name)
    if not expected or options.get('local_files_only') is not True or options.get('use_safetensors') is not True:
        raise ValueError('VACE_LOCAL_SAFETENSORS_LOAD_REQUIRED')
    native = safetensors.safe_open
    targets = ((transformer_io, 'safe_open'), (tensor_io, 'safe_open'))
    if any(getattr(module, name) is not native for module, name in targets):
        raise ValueError('VACE_UNEXPECTED_SAFETENSORS_READER')
    allowed = {directory/name for name in expected}
    if any(not path.is_file() or path.is_symlink() for path in allowed):
        raise ValueError('VACE_LOCAL_SAFETENSORS_FILE_MISSING')
    opened = {}; lock = threading.Lock()

    def local_open(filename, framework, device='cpu', *, backend='mmap'):
        path = Path(filename).resolve(strict=True)
        if path not in allowed or framework != 'pt' or backend not in {'mmap', 'pread'}:
            raise ValueError('VACE_SAFETENSORS_READ_OUTSIDE_COMPONENT')
        # An old native library rejecting this keyword fails closed; never retry
        # with mmap or deserialize pickle as a fallback.
        pointer = native(str(path), framework=framework, device=device, backend='pread')
        with lock:
            opened[path.name] = opened.get(path.name, 0) + 1
        return pointer

    try:
        for module, name in targets:
            setattr(module, name, local_open)
        result = loader(str(directory), **options)
        if set(opened) != set(expected):
            raise ValueError('VACE_SAFETENSORS_READER_NOT_USED_FOR_ALL_SHARDS')
    finally:
        for module, name in targets:
            setattr(module, name, native)
    read_report.append({'component': directory.name, 'backend': 'pread',
        'files': [{'path': directory.name+'/'+name, 'opens': opened[name]} for name in sorted(opened)]})
    return result


def validate_weight_reads(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError('VACE_SAFETENSORS_READ_REPORT_MISSING')
    components = set()
    for row in value:
        if not isinstance(row, dict) or set(row) != {'component', 'backend', 'files'}:
            raise ValueError('VACE_SAFETENSORS_READ_REPORT_INVALID')
        component = row['component']
        if component not in WEIGHT_FILES or component in components or row['backend'] != 'pread':
            raise ValueError('VACE_SAFETENSORS_READ_BACKEND_OR_COMPONENT_INVALID')
        components.add(component)
        expected = [component+'/'+name for name in sorted(WEIGHT_FILES[component])]
        files = row['files']
        if not isinstance(files, list) or len(files) != len(expected):
            raise ValueError('VACE_SAFETENSORS_READ_INVENTORY_INVALID')
        for item, name in zip(files, expected, strict=True):
            if (not isinstance(item, dict) or set(item) != {'path', 'opens'} or item['path'] != name
                    or type(item['opens']) is not int or not 1 <= item['opens'] <= 1024):
                raise ValueError('VACE_SAFETENSORS_READ_INVENTORY_INVALID')


def load_predictor(model_path, settings, generation, *, progress=None):
    # Imports happen only inside the isolated network-guarded worker.
    import torch
    from .cuda_admission import HEADROOM_BYTES, POLICY, admit_cuda, record_window, window_summary

    started=time.monotonic();root=Path(model_path);read_report=[]
    phase_callback = [progress]
    def phase(name):
        if phase_callback[0]:phase_callback[0](name)
    phase('admitting-text-gpu-memory')
    text_check=admit_cuda(torch,settings['text_gpu_budget_mib']*1024**2+HEADROOM_BYTES,'text-weights')
    import accelerate
    from accelerate.hooks import remove_hook_from_module
    import diffusers
    import numpy as np
    from PIL import Image
    import safetensors
    import transformers
    from transformers import AutoTokenizer, UMT5Config, UMT5EncoderModel
    from diffusers import AutoencoderKLWan, UniPCMultistepScheduler, WanVACEPipeline, WanVACETransformer3DModel

    phase('tokenizing-local-prompt')
    tokenizer=AutoTokenizer.from_pretrained(str(root/'tokenizer'),local_files_only=True,trust_remote_code=False)
    token_count={}
    def tokens(text,name):
        plain=tokenizer(text,add_special_tokens=True,truncation=False)['input_ids']
        token_count[name]=len(plain)
        if len(plain)>generation['prompt_max_tokens']:raise ValueError('VACE_PROMPT_TOKEN_BUDGET_EXCEEDED_NO_TRUNCATION: '+name)
        return tokenizer(text,padding='max_length',max_length=generation['prompt_max_tokens'],truncation=False,return_attention_mask=True,return_tensors='pt')
    positive=tokens(generation['prompt'],'prompt');negative=tokens(generation['negative_prompt'],'negative_prompt')
    phase('loading-local-text-encoder')
    config=UMT5Config.from_pretrained(str(root/'text_encoder'),local_files_only=True)
    with torch.device('meta'):
        skeleton=UMT5EncoderModel(config)
    needed=sum(p.numel() for p in skeleton.parameters())*2;del skeleton
    if needed>(settings['text_gpu_budget_mib']+settings['text_cpu_budget_mib'])*1024**2:
        raise ValueError('VACE_TEXT_WEIGHT_BUDGET_INSUFFICIENT_NO_DISK_FALLBACK')
    encoder,loading=load_local_weights(UMT5EncoderModel.from_pretrained,root/'text_encoder',read_report=read_report,dtype=torch.bfloat16,local_files_only=True,use_safetensors=True,
        device_map='auto',max_memory={0:settings['text_gpu_budget_mib']*1024**2,'cpu':settings['text_cpu_budget_mib']*1024**2},
        low_cpu_mem_usage=True,output_loading_info=True)
    if loading.get('missing_keys') or loading.get('unexpected_keys') or loading.get('mismatched_keys') or loading.get('error_msgs'):
        raise ValueError('VACE_TEXT_WEIGHT_LOADING_MISMATCH: '+str(loading))
    placement={k:str(v) for k,v in encoder.hf_device_map.items()}
    if any(v=='disk' for v in placement.values()):raise ValueError('VACE_TEXT_DISK_FALLBACK_FORBIDDEN')
    encoder.eval();phase('encoding-local-prompt')
    def encode(value):
        with torch.inference_mode():
            encoded=encoder(value.input_ids.to('cuda'),attention_mask=value.attention_mask.to('cuda')).last_hidden_state
            length=int(value.attention_mask.sum())
            result=encoded.detach().to('cpu',dtype=torch.bfloat16)
            result[:,length:]=0
            return result
    prompt_embeds=encode(positive);negative_embeds=encode(negative)
    phase('releasing-local-text-encoder')
    remove_hook_from_module(encoder,recurse=True)
    del encoder,positive,negative
    gc.collect();torch.cuda.synchronize();torch.cuda.empty_cache()
    text_seconds=time.monotonic()-started
    phase('loading-local-video-transformer-and-vae')
    transformer,loading=load_local_weights(WanVACETransformer3DModel.from_pretrained,root/'transformer',read_report=read_report,local_files_only=True,use_safetensors=True,
                                                                torch_dtype=torch.bfloat16,low_cpu_mem_usage=True,output_loading_info=True)
    if any(loading.get(k) for k in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')):raise ValueError('VACE_TRANSFORMER_WEIGHT_LOADING_MISMATCH: '+str(loading))
    vae,loading=load_local_weights(AutoencoderKLWan.from_pretrained,root/'vae',read_report=read_report,local_files_only=True,use_safetensors=True,
                                                torch_dtype=torch.float32,low_cpu_mem_usage=True,output_loading_info=True)
    if any(loading.get(k) for k in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')):raise ValueError('VACE_VAE_WEIGHT_LOADING_MISMATCH: '+str(loading))
    scheduler=UniPCMultistepScheduler.from_pretrained(str(root/'scheduler'),local_files_only=True)
    scheduler=UniPCMultistepScheduler.from_config(scheduler.config,flow_shift=generation['flow_shift'])
    transformer.eval();vae.eval();vae.enable_tiling()
    pipe=WanVACEPipeline(tokenizer=tokenizer,text_encoder=None,transformer=transformer,vae=vae,scheduler=scheduler)
    video_weight_bytes=sum(value.numel()*value.element_size() for model in (transformer,vae)
                           for values in (model.parameters(),model.buffers()) for value in values)
    prompt_embedding_bytes=sum(value.numel()*value.element_size() for value in (prompt_embeds,negative_embeds))
    phase('admitting-video-gpu-memory')
    video_check=admit_cuda(torch,video_weight_bytes+prompt_embedding_bytes+HEADROOM_BYTES,'video-weights',
                          expected_uuid=text_check['device_uuid'])
    pipe.to('cuda');pipe.set_progress_bar_config(disable=True)
    stability=tuple(transformer._keep_in_fp32_modules)
    dtypes={}
    for name,p in transformer.named_parameters():
        allowed={torch.bfloat16,torch.float32} if any(part in stability for part in name.split('.')) else {torch.bfloat16}
        if p.device.type!='cuda' or p.dtype not in allowed:raise ValueError('VACE_TRANSFORMER_DEVICE_OR_PRECISION_MISMATCH: '+name)
        dtypes[str(p.dtype)]=dtypes.get(str(p.dtype),0)+p.numel()
    if any(p.device.type!='cuda' or p.dtype!=torch.float32 for p in vae.parameters()):raise ValueError('VACE_VAE_DEVICE_OR_PRECISION_MISMATCH')
    metadata={'versions':{'python':__import__('sys').version.split()[0],'numpy':np.__version__,'torch':torch.__version__,'diffusers':diffusers.__version__,
                         'transformers':transformers.__version__,'accelerate':accelerate.__version__,'safetensors':safetensors.__version__},
              'local_weight_reads':read_report,'text_device_map':placement,'text_weight_bytes_bfloat16':needed,'text_encoder_released_before_generation':True,
              'text_offload_hooks_removed_before_generation':True,
              'prompt_token_counts':token_count,'prompt_truncated':False,'prompt_extension':False,'text_phase_seconds':text_seconds,
              'load_seconds':time.monotonic()-started,'cuda_device':torch.cuda.get_device_name(0),'cuda_total_bytes':text_check['torch_total_bytes'],
              'gpu_admission':{'policy':POLICY,'reservation':False,'oom_guarantee':False,'headroom_bytes':HEADROOM_BYTES,
                               'text':text_check,'video':video_check,'video_weight_bytes':video_weight_bytes,
                               'prompt_embedding_bytes':prompt_embedding_bytes,'windows':window_summary()},
              'transformer_precision':'bfloat16-with-declared-float32-stability-modules','transformer_parameter_dtype_elements':dtypes,
              'float32_stability_modules':list(stability),'vae_precision':'float32','vae_spatial_tiling':True,'window_seconds':[],
              'flow_shift':float(scheduler.config.flow_shift),'model_input_scale':generation['model_input_scale'],
              'window_input_shapes':[]}
    from .vace_context import ConditioningTrace
    conditioning_trace=ConditioningTrace() if generation.get('temporal_context')=='previous' else None
    original_prompt = prompt_identity(generation)
    initial = copy.deepcopy(metadata)

    def begin_generation(options, *, progress=None):
        nonlocal generation, conditioning_trace
        if prompt_identity(options) != original_prompt:
            raise ValueError('VACE_SESSION_PROMPT_CHANGED_START_NEW_SESSION')
        # A fresh scheduler and trace prevent step, scene or previous-frame state
        # leaking across projects/jobs. Only weights and text embeddings persist.
        generation = copy.deepcopy(options)
        phase_callback[0] = progress
        pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=options['flow_shift'])
        metadata.clear(); metadata.update(copy.deepcopy(initial))
        metadata.update(load_seconds=0., initial_load_seconds=initial['load_seconds'], text_phase_seconds=0.,
                        flow_shift=options['flow_shift'], model_input_scale=options['model_input_scale'])
        metadata['gpu_admission']['windows'] = window_summary()
        conditioning_trace = ConditioningTrace() if options.get('temporal_context') == 'previous' else None
        return metadata
    def predict(images,masks,window_generation):
        if {k:v for k,v in window_generation.items() if k!='seed'}!={k:v for k,v in generation.items() if k!='seed'}:raise ValueError('VACE_GENERATION_SETTINGS_CHANGED')
        phase('admitting-video-window-gpu-memory')
        summary=metadata['gpu_admission']['windows']
        check=admit_cuda(torch,HEADROOM_BYTES,'video-window-'+str(summary['count']+1),expected_uuid=text_check['device_uuid'])
        record_window(summary,check)
        phase('joint-video-denoising');begin=time.monotonic()
        def step_callback(_pipe,_step,_time,kwargs):
            phase('joint-video-denoising-step-'+str(_step+1));return kwargs
        if conditioning_trace is not None:
            conditioning_trace.add(images,masks)
            metadata['conditioning_trace']=conditioning_trace.snapshot()
        with torch.inference_mode():
            value=pipe(video=[Image.fromarray(x) for x in images],mask=[Image.fromarray(x).convert('RGB') for x in masks],
                prompt_embeds=prompt_embeds.to('cuda'),negative_prompt_embeds=negative_embeds.to('cuda'),
                height=images.shape[1],width=images.shape[2],num_frames=len(images),
                num_inference_steps=window_generation['inference_steps'],guidance_scale=window_generation['guidance_scale'],
                conditioning_scale=window_generation['conditioning_scale'],generator=torch.Generator(device='cuda').manual_seed(window_generation['seed']),
                max_sequence_length=window_generation['prompt_max_tokens'],output_type='np',callback_on_step_end=step_callback).frames[0]
        metadata['window_seconds'].append(time.monotonic()-begin)
        metadata['window_input_shapes'].append(list(images.shape[:3]))
        return np.asarray(value,dtype=np.float32)
    phase('local-video-model-ready')
    predict.begin_generation = begin_generation
    return predict,metadata
