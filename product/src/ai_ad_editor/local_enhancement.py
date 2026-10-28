"""Immutable local speech-enhancement adapter and explicit finite options."""
import math
from pathlib import Path
from .artifact_locks import artifact_entry
from .errors import argument_error,AppError
from .local_lipsync import tensor_file,model_digest
from .local_matting import manifest_hash
from .policy import resolve_local_path
from .utils import assert_id,now_iso,sha256_file

ENGINE='deepfilternet3-native-cuda-v1'
PROTOCOL='agent-native-speech-enhancement-v1'
CONFIG_SHA256='7c609e234c5acf6c7dc436d4ffcee0fc0e6f7742faf48531843698f9963a90db'
MODEL_FILES={'config.json','model.safetensors','conversion.json','LICENSE-MIT.txt','LICENSE-APACHE.txt'}
IMPLEMENTATIONS={k:k+'.py' for k in ('local_enhancement','enhancement_graph','enhancement_layers','enhancement_dsp','enhancement_model',
    'enhancement_worker','enhancement_pipeline','enhancement_plan','enhancement_cli','native_audio_clock',
    'artifact_locks','rvm_worker','cuda_admission','native_process_job','job_workspaces','separation_dsp','utils')}

def error(suffix,message,**details):return AppError('ENHANCEMENT_'+suffix,message,exit_code=6,diagnostics=details or None)

def settings(*,threads=4,segment_seconds=10.,overlap=.25):
    if (type(threads)is not int or not 1<=threads<=32 or any(type(v)not in (int,float) or not math.isfinite(v) for v in (segment_seconds,overlap))
            or not 1<=segment_seconds<=30 or not 0<=overlap<=.75):raise argument_error('增强要求1..32线程、1..30秒分段及0..0.75重叠比例')
    return dict(threads=threads,segment_seconds=float(segment_seconds),overlap=float(overlap),device='cuda',precision='float32',
        model_sample_rate=48000,state_budget_bytes=512*1024**2)

def options(*,strength=1.,attenuation_limit_db=None):
    if type(strength)not in (int,float) or not math.isfinite(strength) or not 0<=strength<=1:raise argument_error('strength须为有限0..1')
    if attenuation_limit_db is not None and (type(attenuation_limit_db)not in (int,float) or not math.isfinite(attenuation_limit_db) or not 0<=attenuation_limit_db<=100):raise argument_error('attenuation-limit-db须为0..100；0旁路，未指定为完整模型估计')
    return dict(strength=float(strength),attenuation_limit_db=float(attenuation_limit_db) if attenuation_limit_db is not None else None)

def model_files(model):
    model=Path(model)
    if not model.is_dir() or model.is_symlink() or getattr(model,'is_junction',lambda:False)():raise error('MODEL','要求本地普通模型目录')
    paths=[]
    try:
        for name in sorted(MODEL_FILES):
            p=model/name
            if not p.is_file() or p.is_symlink() or not 1<=p.stat().st_size<=32*1024**2:raise ValueError('model file type/size')
            if name.endswith('.safetensors'):tensor_file(p)
            if name=='config.json' and sha256_file(p)!=CONFIG_SHA256:raise ValueError('fixed model configuration')
            paths.append(p)
    except (OSError,ValueError,KeyError,TypeError) as exc:raise error('MODEL','要求固定48kHz DeepFilterNet3完整safetensors模型',cause=str(exc)) from exc
    return paths

def prepare_adapter(root,*,adapter_id,model_path,executable,evidence,creator,license_spdx,license_url,permitted_uses,verification_status,options=None):
    assert_id(adapter_id,'adapter-id')
    if verification_status not in {'unverified','verified','restricted'}:raise argument_error('核验状态无效')
    model=resolve_local_path(root,model_path,field='model-path');python=resolve_local_path(root,executable,field='executable');proof=resolve_local_path(root,evidence,field='evidence')
    if python.suffix.lower()!='.exe' or not proof.is_file() or proof.stat().st_size>2*1024**2:raise error('FILES','须为原生Python.exe及不超过2MiB的权利证据')
    artifacts=[artifact_entry(p,'model') for p in model_files(model)]+[artifact_entry(python,'python'),artifact_entry(proof,'evidence')]
    artifacts.extend(artifact_entry(Path(__file__).with_name(n),k) for k,n in IMPLEMENTATIONS.items())
    record=dict(adapter_id=adapter_id,kind='speech-enhancement',engine=ENGINE,protocol=PROTOCOL,output_contract='native-clock-float32-audio-v1',
        model_path=str(model),model_sha256=model_digest(model,artifacts),model_kind='directory',model_file_count=len(MODEL_FILES),
        executable=str(python),executable_sha256=next(a['sha256'] for a in artifacts if a['role']=='python'),
        rights_ref='audio_adapter_'+adapter_id,settings=settings(**(options or {})),artifacts=artifacts,network='disabled',registered_at=now_iso(),verification_status=verification_status)
    record['sha256']=manifest_hash(record)
    rights=dict(asset_id=record['rights_ref'],kind='model-adapter',sha256=record['sha256'],source_url='local://audio-adapter/'+adapter_id,
        source_version=ENGINE,retrieved_at=record['registered_at'],creator=creator,license_spdx=license_spdx,license_url=license_url,attribution='',
        permitted_uses=list(dict.fromkeys(permitted_uses)),permitted_channels=[],restrictions=[],derived_from=[],evidence=str(proof),
        verification_status=verification_status,verified_by='explicit-local-registration' if verification_status=='verified' else '',takedown_status='clear',
        notes='Model/source/output rights are separate; licensing does not establish listening quality.')
    return record,rights

def verify_adapter(record):
    try:
        expected=dict(engine=ENGINE,protocol=PROTOCOL,kind='speech-enhancement',output_contract='native-clock-float32-audio-v1',network='disabled')
        if any(record.get(k)!=v for k,v in expected.items()) or manifest_hash(record)!=record['sha256']:raise ValueError('adapter protocol/digest')
        cfg=record['settings']
        if cfg!=settings(**{k:cfg[k] for k in ('threads','segment_seconds','overlap')}):raise ValueError('settings')
        model=Path(record['model_path']);paths=model_files(model)
        entries={(str(p.resolve()),'model') for p in paths}|{(str(Path(record['executable']).resolve()),'python')}
        entries|={(str(Path(__file__).with_name(n).resolve()),k) for k,n in IMPLEMENTATIONS.items()}
        actual={(a['path'],a['role']) for a in record['artifacts']}
        if len(actual)!=len(record['artifacts']) or not entries<=actual or len(actual-entries)!=1 or next(iter(actual-entries))[1]!='evidence':raise ValueError('artifact inventory')
        if record['model_sha256']!=model_digest(model,record['artifacts']) or record['model_kind']!='directory' or record['model_file_count']!=len(paths):raise ValueError('model inventory')
        if record['rights_ref']!='audio_adapter_'+record['adapter_id'] or next(a['sha256'] for a in record['artifacts'] if a['role']=='python')!=record['executable_sha256']:raise ValueError('adapter references')
        if any(artifact_entry(Path(a['path']),a['role'])!=a for a in record['artifacts']):raise ValueError('artifact bytes changed')
    except (AppError,OSError,ValueError,TypeError,KeyError,StopIteration) as exc:return dict(ok=False,engine=ENGINE,findings=[dict(code='ENHANCEMENT_ADAPTER_CHANGED',message=str(exc))])
    return dict(ok=True,engine=ENGINE,network='disabled',findings=[])
