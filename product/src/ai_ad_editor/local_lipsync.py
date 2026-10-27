"""Explicit local MuseTalk registration and output-clock face region plans."""
from pathlib import Path
import json,math,struct

from .artifact_locks import artifact_entry
from .errors import AppError,argument_error
from .local_matting import manifest_hash
from .policy import resolve_local_path
from .utils import assert_id,now_iso,sha256_bytes,sha256_file

ENGINE='musetalk-v15-native-cuda-v1'
PROTOCOL='agent-native-lipsync-v1'
MODEL_FILES={'unet/config.json','unet/diffusion_pytorch_model.safetensors','vae/config.json',
    'vae/diffusion_pytorch_model.safetensors','whisper/config.json','whisper/preprocessor_config.json',
    'whisper/model.safetensors','parser/model.safetensors','conversion.json','licenses/MuseTalk-LICENSE.txt'}
CONFIG_HASHES={'unet/config.json':'5b6923aee04d71692e0e9846c471e0a4ea07a4f686d39545e472bd4ba17e1b47',
    'vae/config.json':'92d3dfb746fca211a2c9e019e285f8597412211728dce3c5bcf4eda0f2d62e7e',
    'whisper/config.json':'ffdccec4f3211f4c63310f2b7098f309fe70f3952cedc5e4d11e43f5b2379b98',
    'whisper/preprocessor_config.json':'9b5cd03a36fbb8a627c64d98a5b5b126ead95a77720723944487311f0110b666'}
IMPLEMENTATIONS={'controller':'local_lipsync.py','worker':'lipsync_worker.py','model_loader':'lipsync_model.py',
    'plan':'lipsync_plan.py','cli':'lipsync_cli.py',
    'face_parser':'lipsync_parser.py','frames':'lipsync_frames.py','pipeline':'lipsync_pipeline.py',
    'artifact_verification':'artifact_locks.py','network_guard':'rvm_worker.py','cuda_admission':'cuda_admission.py',
    'windows_job':'local_matting.py','io':'utils.py','owned_jobs':'job_workspaces.py'}
CAPABILITIES=['audio_driven_face_lip_sync','image_or_video_source','explicit_output_clock_boxes',
    'semantic_face_blending','source_alpha_and_outside_region_preserved','native_cuda_no_CPU_fallback',
    'lossless_RGBA_and_complete_PCM','bounded_batches_and_owned_cancellation']


def error(code,message,**details):return AppError('LIPSYNC_'+code,message,exit_code=2,diagnostics=details or None)


def settings(*,device='cuda',threads=4,batch_size=2):
    if device!='cuda' or type(threads) is not int or not 1<=threads<=32 or type(batch_size) is not int or not 1<=batch_size<=8:
        raise argument_error('口型同步要求原生CUDA、1..32线程及1..8帧批次','device/threads/batch-size')
    return dict(device=device,threads=threads,batch_size=batch_size,state_budget_bytes=512*1024**2,
        precision={'unet':'float16','vae':'float32','whisper':'float16','parser':'float32'})


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate JSON key')
        result[key]=value
    return result


def tensor_file(path):
    with path.open('rb') as stream:
        raw=stream.read(8)
        if len(raw)!=8:raise ValueError('safetensors header missing')
        size=struct.unpack('<Q',raw)[0]
        if not 2<=size<=16*1024**2:raise ValueError('safetensors header budget')
        data=json.loads(stream.read(size),object_pairs_hook=_unique)
    spans=[]
    for key,row in data.items():
        if key=='__metadata__':continue
        if not isinstance(row,dict) or set(row)!={'dtype','shape','data_offsets'} or row['dtype'] not in {'F16','F32','I64'}:
            raise ValueError('unsupported model tensor')
        if not isinstance(row['shape'],list) or len(row['shape'])>8 or any(type(v)is not int or not 0<=v<=100000 for v in row['shape']):
            raise ValueError('invalid tensor dimensions')
        ends=row['data_offsets'];count=math.prod(row['shape'])*{'F16':2,'F32':4,'I64':8}[row['dtype']]
        if not isinstance(ends,list) or len(ends)!=2 or any(type(v)is not int for v in ends) or ends[0]<0 or ends[1]-ends[0]!=count:
            raise ValueError('invalid tensor offsets')
        spans.append(tuple(ends))
    spans.sort()
    if not spans or spans[0][0]!=0 or any(a[1]!=b[0] for a,b in zip(spans,spans[1:])) or spans[-1][1]!=path.stat().st_size-size-8:
        raise ValueError('incomplete tensor payload')


def model_files(model):
    model=Path(model)
    if not model.is_dir() or model.is_symlink() or getattr(model,'is_junction',lambda:False)():raise error('MODEL','要求本地普通模型目录')
    paths=[]
    try:
        for name in sorted(MODEL_FILES):
            path=model/name
            if not path.is_file() or path.is_symlink() or not 1<=path.stat().st_size<=2*1024**3:raise ValueError('missing/oversize model component')
            if name.endswith('.safetensors'):tensor_file(path)
            if name in CONFIG_HASHES and sha256_file(path)!=CONFIG_HASHES[name]:raise ValueError('fixed model configuration changed')
            paths.append(path)
    except (OSError,ValueError,TypeError,KeyError,struct.error) as exc:raise error('MODEL','模型须为完整固定MuseTalk1.5/Whisper-tiny/VAE/BiSeNet safetensors目录',cause=str(exc)) from exc
    return paths


def model_digest(model,artifacts):
    rows=[{'path':Path(a['path']).relative_to(model).as_posix(),'sha256':a['sha256'],'bytes':a['bytes']} for a in artifacts if a['role']=='model']
    return 'sha256:'+sha256_bytes(json.dumps(sorted(rows,key=lambda r:r['path']),sort_keys=True,separators=(',',':')).encode())


def prepare_adapter(root,*,adapter_id,model_path,executable,evidence,creator,license_spdx,license_url,
                    permitted_uses,verification_status,options):
    assert_id(adapter_id,'adapter-id')
    if verification_status not in {'unverified','verified','restricted'}:raise error('RIGHTS','核验状态无效')
    model=resolve_local_path(root,model_path,field='model-path');python=resolve_local_path(root,executable,field='python-executable')
    proof=resolve_local_path(root,evidence,field='evidence')
    if python.suffix.lower()!='.exe':raise error('PYTHON','要求原生Python .exe')
    artifacts=[artifact_entry(p,'model') for p in model_files(model)]+[artifact_entry(python,'python'),artifact_entry(proof,'evidence')]
    artifacts.extend(artifact_entry(Path(__file__).with_name(n),role) for role,n in IMPLEMENTATIONS.items())
    record=dict(adapter_id=adapter_id,kind='video-lip-sync',engine=ENGINE,protocol=PROTOCOL,output_contract='rgba_video_v1',
        model_path=str(model),model_sha256=model_digest(model,artifacts),model_kind='directory',model_file_count=len(MODEL_FILES),
        executable=str(python),executable_sha256=next(a['sha256'] for a in artifacts if a['role']=='python'),
        rights_ref='visual_adapter_'+adapter_id,capabilities=CAPABILITIES.copy(),settings=settings(**options),
        artifacts=artifacts,network='disabled',registered_at=now_iso(),verification_status=verification_status)
    record['sha256']=manifest_hash(record)
    rights=dict(asset_id=record['rights_ref'],kind='model-adapter',sha256=record['sha256'],source_url='local://visual-adapter/'+adapter_id,
        source_version=ENGINE,retrieved_at=record['registered_at'],creator=creator,license_spdx=license_spdx,license_url=license_url,
        attribution='',permitted_uses=list(dict.fromkeys(permitted_uses)),permitted_channels=[],restrictions=[],derived_from=[],
        evidence=str(proof),verification_status=verification_status,verified_by='explicit-local-registration' if verification_status=='verified' else '',
        takedown_status='clear',notes='Model, source portrait/video, speech and generated content rights remain separate.')
    return record,rights


def verify_adapter(record):
    try:
        if any(record.get(k)!=v for k,v in dict(engine=ENGINE,protocol=PROTOCOL,kind='video-lip-sync',network='disabled',
                output_contract='rgba_video_v1',capabilities=CAPABILITIES).items()):raise ValueError('adapter protocol changed')
        cfg=record['settings']
        if cfg!=settings(**{k:cfg[k] for k in ('device','threads','batch_size')}) or manifest_hash(record)!=record['sha256']:
            raise ValueError('adapter settings/digest changed')
        model=Path(record['model_path']);files=model_files(model)
        expected={(str(p.resolve()),'model') for p in files}|{(str(Path(record['executable']).resolve()),'python')}
        expected|={(str(Path(__file__).with_name(n).resolve()),role) for role,n in IMPLEMENTATIONS.items()}
        actual={(a['path'],a['role']) for a in record['artifacts']}
        if len(actual)!=len(record['artifacts']) or not expected<=actual or len(actual-expected)!=1 or next(iter(actual-expected))[1]!='evidence':raise ValueError('artifact inventory changed')
        if record['model_sha256']!=model_digest(model,record['artifacts']) or record['model_kind']!='directory' or record['model_file_count']!=len(files):raise ValueError('model manifest changed')
        if record['rights_ref']!='visual_adapter_'+record['adapter_id'] or next(a['sha256'] for a in record['artifacts'] if a['role']=='python')!=record['executable_sha256']:raise ValueError('adapter reference changed')
        if any(artifact_entry(Path(a['path']),a['role'])!=a for a in record['artifacts']):raise ValueError('artifact bytes changed')
    except (AppError,OSError,ValueError,TypeError,KeyError,StopIteration) as exc:
        return dict(ok=False,engine=ENGINE,findings=[dict(code='LIPSYNC_ADAPTER_CHANGED',message=str(exc))])
    return dict(ok=True,engine=ENGINE,network='disabled',findings=[])


def boxes(value,width,height,frames):
    if not isinstance(value,dict) or set(value)!={'clock','keys'} or value['clock']!='output-frame-25fps' or not isinstance(value['keys'],list) or not 1<=len(value['keys'])<=min(frames,15000):
        raise error('BOXES','须明确output-frame-25fps时钟及有序人脸框关键帧')
    previous=-1
    for key in value['keys']:
        if not isinstance(key,dict) or set(key)!={'frame','box'} or type(key['frame'])is not int or not previous<key['frame']<frames:
            raise error('BOXES','人脸框帧须严格递增且位于输出范围')
        box=key['box']
        if not isinstance(box,list) or len(box)!=4 or any(type(v)not in (int,float) or not math.isfinite(v) for v in box):raise error('BOXES','人脸框须为有限x0,y0,x1,y1像素')
        x0,y0,x1,y1=box
        if not 0<=x0<x1<=width or not 0<=y0<y1<=height or min(x1-x0,y1-y0)<32:raise error('BOXES','人脸框须在画布内且每边至少32像素')
        previous=key['frame']
    if value['keys'][0]['frame']!=0:raise error('BOXES','首个人脸框须从输出帧0开始')
    return value


def box_at(plan,frame):
    keys=plan['keys'];a=keys[0]
    for b in keys[1:]:
        if frame<=b['frame']:
            t=(frame-a['frame'])/(b['frame']-a['frame'])
            return [round(x+(y-x)*t) for x,y in zip(a['box'],b['box'])]
        a=b
    return [round(v) for v in a['box']]
