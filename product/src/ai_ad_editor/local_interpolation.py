"""Fixed native CUDA RIFE4.25 registration and immutable local artifact contract."""
import json
from pathlib import Path
from .artifact_locks import artifact_entry
from .errors import AppError,argument_error
from .local_lipsync import tensor_file
from .local_matting import manifest_hash
from .policy import resolve_local_path
from .utils import assert_id,now_iso,sha256_bytes,sha256_file
ENGINE='rife425-native-cuda-v1'
PROTOCOL='agent-native-frame-interpolation-v1'
CONFIG_SHA256='ab6b952788180b412209e44a343759a285b349fdabd4fc566c5eec13cd50f62a'
MODEL_FILES={'config.json','model.safetensors','conversion.json','LICENSE.txt'}
IMPLEMENTATIONS={'controller':'local_interpolation.py','tensor_format':'local_lipsync.py',
    'graph':'interpolation_graph.py','model_loader':'interpolation_model.py','clock':'interpolation_clock.py',
    'frames':'interpolation_frames.py','plan':'interpolation_plan.py','pipeline':'interpolation_pipeline.py',
    'worker':'interpolation_worker.py','cli':'interpolation_cli.py','native_frame_index':'reverse_video_clock.py',
    'artifact_verification':'artifact_locks.py','network_guard':'rvm_worker.py','cuda_admission':'cuda_admission.py',
    'windows_job':'local_matting.py','io':'utils.py','owned_jobs':'job_workspaces.py'}
CAPABILITIES=['actual_RIFE425_CUDA_flow','native_CFR_and_VFR_subdivision','all_original_RGBA_anchors_preserved',
    'flow_premultiplied_alpha','explicit_scene_cut_holds','original_selected_PCM_preserved',
    'portable_rerunnable_recipe','editable_linked_slow_motion','owned_cancel_timeout_recovery']
def error(code,message,**details):return AppError('INTERPOLATION_'+code,message,exit_code=2,diagnostics=details or None)
def settings(*,device='cuda',threads=4,scale=1.):
    if device!='cuda' or type(threads)is not int or not 1<=threads<=32 or type(scale)not in (int,float) or scale not in (.25,.5,1.,2.):
        raise argument_error('神经补帧要求原生CUDA、1..32线程及scale=0.25/0.5/1/2','device/threads/scale')
    return dict(device=device,threads=threads,scale=float(scale),precision='float32',state_budget_bytes=512*1024**2)
def model_files(model):
    model=Path(model)
    if not model.is_dir() or model.is_symlink() or getattr(model,'is_junction',lambda:False)():raise error('MODEL','须为本地普通模型目录')
    paths=[]
    try:
        for name in sorted(MODEL_FILES):
            p=model/name
            if not p.is_file() or p.is_symlink() or not 1<=p.stat().st_size<=256*1024**2:raise ValueError('model component size/type')
            if name.endswith('.safetensors'):tensor_file(p)
            if name=='config.json' and sha256_file(p)!=CONFIG_SHA256:raise ValueError('fixed RIFE4.25 configuration changed')
            paths.append(p)
    except (OSError,ValueError,TypeError,KeyError) as exc:raise error('MODEL','须为完整固定RIFE4.25 safetensors模型目录',cause=str(exc)) from exc
    return paths
def model_digest(model,artifacts):
    rows=[dict(path=Path(a['path']).relative_to(model).as_posix(),sha256=a['sha256'],bytes=a['bytes']) for a in artifacts if a['role']=='model']
    return 'sha256:'+sha256_bytes(json.dumps(sorted(rows,key=lambda r:r['path']),sort_keys=True,separators=(',',':')).encode())
def prepare_adapter(root,*,adapter_id,model_path,executable,evidence,creator,license_spdx,license_url,permitted_uses,verification_status,options):
    assert_id(adapter_id,'adapter-id')
    if verification_status not in {'unverified','verified','restricted'}:raise error('RIGHTS','核验状态无效')
    model=resolve_local_path(root,model_path,field='model-path');python=resolve_local_path(root,executable,field='python-executable');proof=resolve_local_path(root,evidence,field='evidence')
    if python.suffix.lower()!='.exe':raise error('PYTHON','要求原生Python .exe')
    artifacts=[artifact_entry(p,'model') for p in model_files(model)]+[artifact_entry(python,'python'),artifact_entry(proof,'evidence')]
    artifacts.extend(artifact_entry(Path(__file__).with_name(name),role) for role,name in IMPLEMENTATIONS.items())
    record=dict(adapter_id=adapter_id,kind='frame-interpolation',engine=ENGINE,protocol=PROTOCOL,output_contract='rgba_video_v1',
        model_path=str(model),model_sha256=model_digest(model,artifacts),model_kind='directory',model_file_count=len(MODEL_FILES),
        executable=str(python),executable_sha256=next(a['sha256'] for a in artifacts if a['role']=='python'),
        rights_ref='visual_adapter_'+adapter_id,capabilities=CAPABILITIES.copy(),settings=settings(**options),artifacts=artifacts,network='disabled',registered_at=now_iso(),verification_status=verification_status)
    record['sha256']=manifest_hash(record)
    rights=dict(asset_id=record['rights_ref'],kind='model-adapter',sha256=record['sha256'],source_url='local://visual-adapter/'+adapter_id,
        source_version=ENGINE,retrieved_at=record['registered_at'],creator=creator,license_spdx=license_spdx,license_url=license_url,attribution='',
        permitted_uses=list(dict.fromkeys(permitted_uses)),permitted_channels=[],restrictions=[],derived_from=[],evidence=str(proof),
        verification_status=verification_status,verified_by='explicit-local-registration' if verification_status=='verified' else '',takedown_status='clear',notes='Model, source media and generated content rights remain separate.')
    return record,rights
def verify_adapter(record):
    try:
        if any(record.get(k)!=v for k,v in dict(engine=ENGINE,protocol=PROTOCOL,kind='frame-interpolation',network='disabled',output_contract='rgba_video_v1',capabilities=CAPABILITIES).items()):raise ValueError('adapter protocol')
        cfg=record['settings']
        if cfg!=settings(**{k:cfg[k] for k in ('device','threads','scale')}) or manifest_hash(record)!=record['sha256']:raise ValueError('settings/digest')
        model=Path(record['model_path']);paths=model_files(model)
        expected={(str(p.resolve()),'model') for p in paths}|{(str(Path(record['executable']).resolve()),'python')}
        expected|={(str(Path(__file__).with_name(n).resolve()),role) for role,n in IMPLEMENTATIONS.items()}
        actual={(a['path'],a['role']) for a in record['artifacts']}
        if len(actual)!=len(record['artifacts']) or not expected<=actual or len(actual-expected)!=1 or next(iter(actual-expected))[1]!='evidence':raise ValueError('artifact inventory')
        if record['model_sha256']!=model_digest(model,record['artifacts']) or record['model_kind']!='directory' or record['model_file_count']!=len(paths):raise ValueError('model inventory')
        if record['rights_ref']!='visual_adapter_'+record['adapter_id'] or next(a['sha256'] for a in record['artifacts'] if a['role']=='python')!=record['executable_sha256']:raise ValueError('adapter references')
        if any(artifact_entry(Path(a['path']),a['role'])!=a for a in record['artifacts']):raise ValueError('artifact bytes changed')
    except (AppError,OSError,ValueError,TypeError,KeyError,StopIteration) as exc:return dict(ok=False,engine=ENGINE,findings=[dict(code='INTERPOLATION_ADAPTER_CHANGED',message=str(exc))])
    return dict(ok=True,engine=ENGINE,network='disabled',findings=[])
