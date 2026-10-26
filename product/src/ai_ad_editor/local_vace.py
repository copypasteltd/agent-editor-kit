"""Fixed-architecture, local-only Wan VACE registration and window planning."""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct

from .errors import AppError, argument_error
from .local_matting import manifest_hash
from .artifact_locks import artifact_entry as _entry
from .policy import resolve_local_path
from .utils import assert_id, now_iso, sha256_bytes

VACE_ENGINE = 'diffusers-wan-vace-local-v1'
VACE_PROTOCOL = 'agent-video-wan-vace-inpainting-v1'
IMPLEMENTATIONS = {'worker': 'vace_worker.py', 'frames': 'vace_frames.py', 'controller': 'local_vace.py',
                   'model_loader': 'vace_model.py', 'pipeline': 'local_matting.py', 'mask_controller': 'local_inpainting.py',
                   'rgba': 'matting_frames.py', 'guard': 'rvm_worker.py', 'artifact_verification': 'artifact_locks.py', 'io': 'utils.py', 'blend': 'repair_blend.py',
                   'cuda_admission': 'cuda_admission.py', 'outpaint': 'local_outpainting.py', 'diagnostics': 'pipeline_diagnostics.py', 'error_contract': 'errors.py', 'local_policy': 'policy.py',
                   'temporal_context': 'vace_context.py', 'model_session': 'model_session.py',
                   'session_worker': 'vace_session_worker.py', 'session_relay': 'vace_session_relay.py'}
CAPABILITIES = ['prompted_masked_video_editing', 'joint_temporal_windows', 'native_cuda_bfloat16', 'outside_rgb_and_alpha_preserved',
                'explicit_previous_generated_overlap_conditioning']
MODEL_FILES = {'model_index.json', 'scheduler/scheduler_config.json', 'text_encoder/config.json',
               'text_encoder/model.safetensors.index.json', 'tokenizer/special_tokens_map.json', 'tokenizer/spiece.model',
               'tokenizer/tokenizer.json', 'tokenizer/tokenizer_config.json', 'transformer/config.json',
               'transformer/diffusion_pytorch_model.safetensors.index.json', 'vae/config.json', 'vae/diffusion_pytorch_model.safetensors'}
MODEL_FILES |= {f'text_encoder/model-{i:05d}-of-00003.safetensors' for i in range(1, 4)}
MODEL_FILES |= {f'transformer/diffusion_pytorch_model-{i:05d}-of-00002.safetensors' for i in range(1, 3)}


def settings(*, device='cuda', threads=4, text_gpu_budget_mib=7168, text_cpu_budget_mib=8192):
    if device != 'cuda' or type(threads) is not int or not 1 <= threads <= 32:
        raise argument_error('VACE 要求显式 CUDA、1..32 线程，无 CPU/云回退', 'device/threads')
    if any(type(v) is not int or not 1024 <= v <= 65536 for v in (text_gpu_budget_mib, text_cpu_budget_mib)):
        raise argument_error('文本编码器权重分配预算须为 1024..65536 MiB', 'text_gpu_budget_mib/text_cpu_budget_mib')
    return {'device': device, 'threads': threads, 'precision': 'bfloat16', 'vae_precision': 'float32',
            'text_gpu_budget_mib': text_gpu_budget_mib, 'text_cpu_budget_mib': text_cpu_budget_mib,
            'text_offload': 'explicit-balanced-weights-then-release', 'state_budget_bytes': 512 * 1024**2}


def _unique(pairs):
    value = {}
    for k,v in pairs:
        if k in value: raise ValueError('duplicate JSON key')
        value[k] = v
    return value


def _json(path):
    if path.stat().st_size > 32 * 1024**2:
        raise ValueError('VACE JSON size budget')
    value = json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=_unique)
    def check(node):
        if isinstance(node, dict):
            if any(k in node for k in ('auto_map', 'custom_pipeline', 'trust_remote_code')):
                raise ValueError('custom model code is forbidden')
            for v in node.values(): check(v)
        elif isinstance(node, list):
            for v in node: check(v)
    check(value)
    return value


def _tensor_keys(path):
    with path.open('rb') as stream:
        length_raw = stream.read(8)
        if len(length_raw) != 8: raise ValueError('safetensors length missing')
        length = struct.unpack('<Q', length_raw)[0]
        if not 2 <= length <= 16 * 1024**2: raise ValueError('safetensors header budget')
        header = json.loads(stream.read(length), object_pairs_hook=_unique)
    if not isinstance(header, dict) or not 1 <= len(header) <= 20000:
        raise ValueError('safetensors inventory budget')
    end = path.stat().st_size - 8 - length
    spans = []
    for key, item in header.items():
        if key == '__metadata__': continue
        if not isinstance(item, dict) or item.get('dtype') not in {'F32', 'F16', 'BF16'}:
            raise ValueError('unsupported tensor dtype')
        shape, offsets = item.get('shape'), item.get('data_offsets')
        if not isinstance(shape, list) or len(shape) > 8 or any(type(x) is not int or x < 1 for x in shape):
            raise ValueError('invalid tensor shape')
        if not isinstance(offsets, list) or len(offsets) != 2 or any(type(x) is not int for x in offsets):
            raise ValueError('invalid tensor offsets')
        a, b = offsets
        if not 0 <= a < b <= end or b-a != math.prod(shape) * (4 if item['dtype'] == 'F32' else 2):
            raise ValueError('tensor byte range mismatch')
        spans.append((a, b))
    spans.sort()
    if not spans or spans[0][0] != 0 or spans[-1][1] != end or any(a[1] != b[0] for a, b in zip(spans, spans[1:])):
        raise ValueError('tensor gaps/overlap/extra bytes')
    return set(header) - {'__metadata__'}


def model_files(model):
    try:
        if not model.is_dir(): raise ValueError('existing model directory required')
        paths = []
        for p in model.rglob('*'):
            if p.is_symlink() or getattr(p,'is_junction',lambda:False)(): raise ValueError('linked model artifacts forbidden')
            if p.is_file():
                name = p.relative_to(model).as_posix()
                if name not in MODEL_FILES: raise ValueError('unrecognized model file: '+name)
                if not 0 < p.stat().st_size <= 12 * 1024**3: raise ValueError('model file budget')
                paths.append(p)
        if {p.relative_to(model).as_posix() for p in paths} != MODEL_FILES or sum(p.stat().st_size for p in paths) > 32 * 1024**3:
            raise ValueError('incomplete or oversized model inventory')
        data = {p.relative_to(model).as_posix(): _json(p) for p in paths if p.suffix == '.json'}
        index = data['model_index.json']; config = data['transformer/config.json']
        if index.get('_class_name') != 'WanVACEPipeline' or config.get('_class_name') != 'WanVACETransformer3DModel':
            raise ValueError('fixed VACE pipeline/transformer required')
        components = {'scheduler':['diffusers','UniPCMultistepScheduler'],'text_encoder':['transformers','UMT5EncoderModel'],
                      'tokenizer':['transformers','T5TokenizerFast'],'transformer':['diffusers','WanVACETransformer3DModel'],'vae':['diffusers','AutoencoderKLWan']}
        if any(index.get(k)!=v for k,v in components.items()) or set(index)-set(components)-{'_class_name','_diffusers_version'}:
            raise ValueError('fixed local component factories required')
        for name, expected in {'num_attention_heads': 12, 'attention_head_dim': 128, 'num_layers': 30, 'in_channels': 16,
                               'out_channels': 16, 'text_dim': 4096, 'vace_in_channels': 96, 'patch_size': [1, 2, 2],
                               'ffn_dim':8960,'freq_dim':256,'vace_layers':list(range(0,30,2)),'image_dim':None,'added_kv_proj_dim':None}.items():
            if config.get(name) != expected: raise ValueError('only Wan2.1 VACE 1.3B architecture is supported: '+name)
        text=data['text_encoder/config.json'];vae=data['vae/config.json'];scheduler=data['scheduler/scheduler_config.json']
        if any(text.get(k)!=v for k,v in {'architectures':['UMT5EncoderModel'],'d_model':4096,'d_ff':10240,'d_kv':64,'num_heads':64,'num_layers':24,'vocab_size':256384,'feed_forward_proj':'gated-gelu'}.items()):
            raise ValueError('fixed UMT5-XXL text encoder required')
        if any(vae.get(k)!=v for k,v in {'_class_name':'AutoencoderKLWan','base_dim':96,'dim_mult':[1,2,4,4],'num_res_blocks':2,'temperal_downsample':[False,True,True],'z_dim':16,'attn_scales':[]}.items()):
            raise ValueError('fixed Wan VAE required')
        for name in ('latents_mean','latents_std'):
            vals=vae.get(name)
            if not isinstance(vals,list) or len(vals)!=16 or any(type(v) not in {int,float} or not math.isfinite(v) or abs(v)>10000 or name=='latents_std' and v<1e-8 for v in vals):raise ValueError('invalid Wan latent normalization')
        if any(scheduler.get(k)!=v for k,v in {'_class_name':'UniPCMultistepScheduler','prediction_type':'flow_prediction','use_flow_sigmas':True,'num_train_timesteps':1000,'solver_order':2}.items()):
            raise ValueError('fixed Wan UniPC flow scheduler required')
        headers = {p.relative_to(model).as_posix(): _tensor_keys(p) for p in paths if p.suffix == '.safetensors'}
        for folder, stem in [('text_encoder', 'model'), ('transformer', 'diffusion_pytorch_model')]:
            weight_map = data[f'{folder}/{stem}.safetensors.index.json'].get('weight_map')
            if not isinstance(weight_map, dict) or not weight_map or len(weight_map) > 20000:
                raise ValueError('invalid sharded weight map')
            expected = {(key, f'{folder}/{file}') for key, file in weight_map.items() if isinstance(file, str) and '/' not in file and '\\' not in file and ':' not in file}
            actual = {(key, file) for file, keys in headers.items() if file.startswith(folder+'/') for key in keys}
            if len(expected) != len(weight_map) or expected != actual or len({key for key, _ in actual}) != len(actual):
                raise ValueError('weight map does not match complete local shard headers')
        return sorted(paths)
    except (ValueError, TypeError, KeyError, OSError, RecursionError, struct.error) as exc:
        raise AppError('VACE_MODEL_INVALID', '要求完整的固定 Wan2.1-VACE-1.3B safetensors 本地目录', exit_code=10, cause=str(exc)) from exc


def model_digest(model, artifacts):
    rows = [{'path': Path(a['path']).relative_to(model).as_posix(), 'sha256': a['sha256'], 'bytes': a['bytes']} for a in artifacts if a['role'] == 'model']
    return 'sha256:'+sha256_bytes(json.dumps(sorted(rows, key=lambda a: a['path']), sort_keys=True, separators=(',', ':')).encode())


def prepare_adapter(root, *, adapter_id, model_path, executable, evidence, creator, license_spdx, license_url, permitted_uses, verification_status, options):
    assert_id(adapter_id, 'adapter_id')
    if verification_status not in {'unverified', 'verified', 'restricted'}: raise argument_error('未知核验状态', 'verification_status')
    model = resolve_local_path(root, model_path, field='model_path'); python = resolve_local_path(root, executable, field='executable')
    proof = resolve_local_path(root, evidence, field='evidence') if evidence else None
    if python.suffix.lower() != '.exe' or proof is None: raise argument_error('VACE 要求原生 Python .exe 及本地证据', 'executable/evidence')
    artifacts = [_entry(p, 'model') for p in model_files(model)]
    artifacts += [_entry(python, 'python'), _entry(proof, 'evidence')]
    artifacts += [_entry(Path(__file__).with_name(file), role) for role, file in IMPLEMENTATIONS.items()]
    record = {'adapter_id': adapter_id, 'kind': 'video-inpainting', 'engine': VACE_ENGINE, 'protocol': VACE_PROTOCOL,
              'output_contract': 'rgba_video_v1', 'model_path': str(model), 'model_sha256': model_digest(model, artifacts),
              'model_kind': 'directory', 'model_file_count': len(MODEL_FILES), 'executable': str(python), 'executable_sha256': next(a['sha256'] for a in artifacts if a['role']=='python'),
              'rights_ref': 'visual_adapter_'+adapter_id, 'capabilities': CAPABILITIES.copy(), 'settings': settings(**options),
              'artifacts': artifacts, 'network': 'disabled', 'registered_at': now_iso(), 'verification_status': verification_status}
    record['sha256'] = manifest_hash(record)
    rights = {'asset_id': record['rights_ref'], 'kind': 'model-adapter', 'sha256': record['sha256'], 'source_url': 'local://visual-adapter/'+adapter_id,
              'source_version': VACE_ENGINE, 'retrieved_at': record['registered_at'], 'creator': creator, 'license_spdx': license_spdx, 'license_url': license_url,
              'attribution': '', 'permitted_uses': list(dict.fromkeys(permitted_uses)), 'permitted_channels': [], 'restrictions': [], 'derived_from': [], 'evidence': str(proof),
              'verification_status': verification_status, 'verified_by': 'explicit-local-registration' if verification_status=='verified' else '', 'takedown_status': 'clear',
              'notes': 'Joint local video windows; text/transformer/VAE/tokenizer, source, mask and generated-content rights require review'}
    return record, rights


def _verify_adapter(record, entry):
    findings=[]
    try:
        if any(record.get(k)!=v for k,v in {'engine':VACE_ENGINE,'protocol':VACE_PROTOCOL,'kind':'video-inpainting','network':'disabled','output_contract':'rgba_video_v1','capabilities':CAPABILITIES}.items()): raise ValueError('VACE registry contract')
        cfg=record['settings']
        if cfg != settings(**{k:cfg[k] for k in ('device','threads','text_gpu_budget_mib','text_cpu_budget_mib')}) or manifest_hash(record)!=record['sha256'] or record['rights_ref']!='visual_adapter_'+record['adapter_id']: raise ValueError('VACE settings/manifest changed')
        model=Path(record['model_path']);files=model_files(model)
        expected={(str(p.resolve()),'model') for p in files}|{(str(Path(record['executable']).resolve()),'python')}
        expected|={(str(Path(__file__).with_name(file).resolve()),role) for role,file in IMPLEMENTATIONS.items()}
        actual={(a['path'],a['role']) for a in record['artifacts']}
        if len(actual)!=len(record['artifacts']) or not expected.issubset(actual) or len(actual-expected)!=1 or next(iter(actual-expected))[1]!='evidence':raise ValueError('VACE artifact inventory')
        if record['model_kind']!='directory' or record['model_file_count']!=len(files) or record['model_sha256']!=model_digest(model,record['artifacts']):raise ValueError('VACE model manifest')
        if next(a['sha256'] for a in record['artifacts'] if a['role']=='python')!=record['executable_sha256'] or any(entry(Path(a['path']),a['role'])!=a for a in record['artifacts']):raise ValueError('VACE artifact changed')
    except (AppError,ValueError,TypeError,KeyError,OSError,StopIteration) as exc:findings.append({'code':getattr(exc,'code','VACE_REGISTRY_INVALID'),'message':str(exc)})
    return {'adapter_id':record.get('adapter_id'),'engine':record.get('engine'),'network':'disabled','ok':not findings,'findings':findings}


def verify_adapter(record):
    return _verify_adapter(record, _entry)


def verify_launch_contract(record):
    """Pre-spawn code/executable checks; child hashes model bytes before ready."""
    artifacts = {(a['path'], a['role']): a for a in record.get('artifacts', [])}
    def entry(path, role):
        if role == 'model': return artifacts[(str(path), role)]
        return _entry(path, role)
    return dict(_verify_adapter(record, entry), model_bytes_verified=False)


def normalize_generation(*, prompt, negative_prompt=None, seed=None, inference_steps=None, guidance_scale=None, conditioning_scale=None,
                         window_frames=None, window_overlap=None, prompt_max_tokens=None, scene_cut_frames=None, flow_shift=None, model_input_scale=None, temporal_context=None, frames=None):
    values={'negative_prompt':'' if negative_prompt is None else negative_prompt,'seed':0 if seed is None else seed,
            'inference_steps':30 if inference_steps is None else inference_steps,'guidance_scale':5. if guidance_scale is None else guidance_scale,
            'conditioning_scale':1. if conditioning_scale is None else conditioning_scale,'window_frames':17 if window_frames is None else window_frames,
            'window_overlap':4 if window_overlap is None else window_overlap,'prompt_max_tokens':256 if prompt_max_tokens is None else prompt_max_tokens,
            'flow_shift':3. if flow_shift is None else flow_shift,'model_input_scale':1 if model_input_scale is None else model_input_scale}
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>8000 or not isinstance(values['negative_prompt'],str) or len(values['negative_prompt'])>8000: raise argument_error('VACE 要求非空原文 prompt；正/负提示词各最多 8000 字符','prompt')
    for name,lo,hi in [('seed',0,2**63-1),('inference_steps',1,1000),('window_frames',5,81),('window_overlap',0,32),('prompt_max_tokens',16,512)]:
        if type(values[name]) is not int or not lo<=values[name]<=hi:raise argument_error('VACE 整数参数超预算',name)
    if type(values['model_input_scale']) is not int or values['model_input_scale'] not in {1,2,4}:
        raise argument_error('模型输入放大倍率须为 1、2 或 4；输出画布保持原尺寸','model_input_scale')
    if values['window_frames']%4!=1 or values['window_overlap']>=values['window_frames']:raise argument_error('窗口须 4k+1 帧，重叠须小于窗口','window_frames/window_overlap')
    if temporal_context not in (None, 'none', 'previous'):
        raise argument_error('时序上下文须为 none 或 previous', 'temporal_context')
    if temporal_context == 'previous':
        if values['window_overlap'] < 1:
            raise argument_error('前窗生成上下文要求 window-overlap 大于零', 'temporal_context/window_overlap')
        values['temporal_context'] = temporal_context
    for name,lo,hi in [('guidance_scale',1,20),('conditioning_scale',0,2),('flow_shift',.1,32)]:
        v=values[name]
        if type(v) not in {int,float} or not math.isfinite(v) or not lo<=v<=hi:raise argument_error('VACE 有限比例超预算',name)
        values[name]=float(v)
    cuts=[] if scene_cut_frames is None else scene_cut_frames
    if not isinstance(cuts,list) or len(cuts)>256 or any(type(v) is not int or v<1 or frames is not None and v>=frames for v in cuts) or len(cuts)!=len(set(cuts)):raise argument_error('场景切点须为范围/CFR 后不重复的内部帧，最多 256 项','scene_cut_frame')
    return {'prompt':prompt,**values,'scene_cut_frames':sorted(cuts)}


def window_plan(frames, generation):
    result=[];window=generation['window_frames'];overlap=generation['window_overlap']
    for begin,end in zip([0,*generation['scene_cut_frames']],[*generation['scene_cut_frames'],frames]):
        start=begin
        while start<end:
            stop=min(start+window,end);actual=stop-start;padded=(actual-1+3)//4*4+1
            result.append({'start':start,'end':stop,'model_frames':padded,'scene_start':begin,'scene_end':end,
                           'seed':(generation['seed']+len(result))%(2**63)})
            if stop==end:break
            start=stop-overlap
    return result


def buffer_budget(width, height, generation, model_max_edge):
    w=max(64, min((width+15)//16*16,(model_max_edge+15)//16*16))
    h=max(64, min((height+15)//16*16,(model_max_edge+15)//16*16))
    context_bytes = width*height*4*generation['window_overlap'] if generation.get('temporal_context') == 'previous' else 0
    return width*height*(generation['window_frames']*40+generation['window_overlap']*16+32)+w*h*generation['window_frames']*40*generation.get('model_input_scale',1)**2+context_bytes


def plan_digest(windows):
    return 'sha256:'+sha256_bytes(json.dumps(windows,sort_keys=True,separators=(',', ':')).encode())
