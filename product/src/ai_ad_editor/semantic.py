"""Local visual embedding indexes, provenance and editable retrieval candidates."""
from __future__ import annotations

import copy
import math
from pathlib import Path
import shutil
import sys
import time

from .artifact_locks import artifact_entry, verification_summary
from .community_device import select as select_device
from .errors import AppError, argument_error
from .policy import require_local_reference
from .project import asset_map, create_snapshot, save_project
from .rights import active_records, add_record, load_ledger, save_ledger
from .semantic_contract import (DIMENSION, ENGINE, INDEX_FORMAT, MAX_ASSETS, MAX_ROWS, PREPROCESSING,
    PROTOCOL, adapter_fingerprint, check_vectors, fingerprint, implementation_files, json_object,
    local_file, model_files, rank, verify_adapter)
from .semantic_sampling import extract, owned, plan, png_probe, remaining
from .utils import assert_id, atomic_write_json, new_id, now_iso, run_process, sha256_file


def registry(project):
    result=project.get('extensions',{}).get('local_semantic',{'adapters':[],'indexes':[]})
    if not isinstance(result,dict) or any(not isinstance(result.get(k,[]),list) for k in ('adapters','indexes','calibrations')):
        raise AppError('SEMANTIC_REGISTRY_INVALID','语义登记表无效',exit_code=6)
    return result


def item(project, collection, ident):
    found=[r for r in registry(project).get(collection,[]) if r.get('adapter_id' if collection=='adapters' else 'index_id')==ident]
    if len(found)!=1:
        raise AppError('SEMANTIC_REGISTRATION_MISSING','语义登记项缺失或重复',exit_code=3,path=ident)
    return found[0]


def _config(timeout, cancel_file, root, *, batch_size=8, device_index=0):
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=3600:
        raise argument_error('timeout-seconds 须为 0..3600 的有限正数','timeout_seconds')
    if type(batch_size) is not int or not 1<=batch_size<=32 or type(device_index) is not int or not 0<=device_index<=31:
        raise argument_error('batch-size 须为 1–32，device-index 须为 0–31','semantic execution')
    marker=None
    if cancel_file:
        require_local_reference(str(cancel_file),field='cancel_file')
        marker=Path(cancel_file).expanduser()
        if not marker.is_absolute():marker=root/marker
    deadline=time.monotonic()+timeout
    remaining(deadline,marker)
    return deadline,marker


def _job(root):
    directory=owned(root,root/'cache/semantic-jobs')
    if directory.exists() and sum(1 for _ in directory.iterdir())>=256:
        raise AppError('SEMANTIC_JOB_BUDGET','语义任务记录已达 256 项；请先显式归档旧 cache/semantic-jobs 目录',exit_code=6)
    if shutil.disk_usage(root).free<256*1024**2:
        raise AppError('SEMANTIC_DISK_BUDGET','语义任务需要至少 256MiB 磁盘余量',exit_code=6)
    path=owned(root,directory/new_id('job'))
    path.mkdir(parents=True,exist_ok=False)
    return path


def _invoke(python, request, job, name, deadline, marker):
    directory=owned(job,job/name);directory.mkdir(parents=True,exist_ok=False)
    response_path=directory/'response.json'
    request={**request,'protocol':PROTOCOL,'network':'disabled','runtime_root':str(directory/'runtime'),
             'response':str(response_path),'output':str(directory/'features.f32'),
             'cancel_file':str(marker) if marker else None}
    request['request_sha256']=fingerprint(request)
    request_path=directory/'request.json';atomic_write_json(request_path,request)
    command=[str(python),'-I','-B','-u','-X','utf8',str(Path(__file__).with_name('semantic_worker.py')),str(request_path)]
    try:
        result=run_process(command,timeout=remaining(deadline,marker),cancel_file=marker)
    except AppError as exc:
        atomic_write_json(directory/'process.json',{'status':'failed','command':command,'error':exc.as_dict()})
        raise
    (directory/'stdout.txt').write_text(result.stdout,encoding='utf-8',newline='\n')
    (directory/'stderr.txt').write_text(result.stderr,encoding='utf-8',newline='\n')
    if not response_path.is_file():
        raise AppError('SEMANTIC_WORKER_NO_RESPONSE','本地语义进程未返回响应',exit_code=6,
                       diagnostics={'job':str(directory),'exit_code':result.returncode,'stderr':result.stderr[-3000:]})
    response=json_object(response_path,max_bytes=2*1024**2)
    if (response.get('protocol')!=PROTOCOL or response.get('network')!='disabled'
            or response.get('request_sha256')!=request['request_sha256']
            or response.get('blocked_network_events')):
        raise AppError('SEMANTIC_WORKER_PROTOCOL_INVALID','语义进程响应绑定或离线协议无效',exit_code=6,path=str(response_path))
    if result.returncode or response.get('status')!='succeeded':
        code=response.get('code','SEMANTIC_WORKER_FAILED')
        if not isinstance(code,str) or not code.startswith('SEMANTIC_'):code='SEMANTIC_WORKER_FAILED'
        raise AppError(code,'本地语义推理失败',exit_code=6,cause=response.get('message'),
                       diagnostics={'job':str(directory),'response':str(response_path),'exit_code':result.returncode})
    remaining(deadline,marker)
    if request['task']=='inspect':return None,response
    if (response.get('task')!=request['task'] or response.get('adapter_sha256')!=request['adapter']['sha256']
            or response.get('item_ids')!=[i['id'] for i in request['items']]
            or response.get('rows')!=len(request['items']) or response.get('dimension')!=DIMENSION
            or response.get('dtype')!='float32-little-endian' or response.get('output')!=request['output']
            or response.get('device')!=request['device'] or response.get('device_index')!=request['device_index']
            or response.get('versions')!=request['adapter']['runtime_versions']
            or response.get('module_paths')!=request['adapter']['runtime_modules']):
        raise AppError('SEMANTIC_WORKER_PROTOCOL_INVALID','语义向量响应顺序、设备或执行器不匹配',exit_code=6)
    output=local_file(request['output'])
    if (output.stat().st_size!=len(request['items'])*DIMENSION*4
            or 'sha256:'+sha256_file(output)!=response.get('output_sha256')):
        raise AppError('SEMANTIC_VECTOR_INVALID','语义向量文件长度或摘要无效',exit_code=6)
    import numpy as np
    return check_vectors(np.fromfile(output,dtype='<f4').reshape(len(request['items']),DIMENSION),len(request['items'])),response


def _checked_adapter(root, project, adapter_id):
    adapter=item(project,'adapters',adapter_id)
    verification=verify_adapter(adapter)
    if not verification['ok']:
        raise AppError('SEMANTIC_ADAPTER_INTEGRITY_FAILED','语义模型、执行器或原生依赖已改变',exit_code=10,cause=verification['message'])
    rights=next((r for r in active_records(load_ledger(root)) if r['asset_id']==adapter['rights_ref']),None)
    if not rights or rights.get('sha256')!=adapter['sha256']:
        raise AppError('SEMANTIC_MODEL_RIGHTS_MISSING','语义模型缺少匹配的权利登记',exit_code=7)
    return adapter


def register(root, project, *, adapter_id, python_executable, model_path, evidence, creator,
             license_spdx, verification_status='unverified', permitted_uses=None, threads=4,
             timeout=600, cancel_file=None, dry_run=False):
    assert_id(adapter_id,'adapter_id')
    if any(r.get('adapter_id')==adapter_id for r in registry(project).get('adapters',[])):
        raise AppError('SEMANTIC_REGISTRATION_EXISTS','语义模型登记 ID 已存在',exit_code=2)
    if sys.platform!='win32' or type(threads) is not int or not 1<=threads<=16:
        raise argument_error('需要原生 Windows 与 1–16 threads','semantic adapter')
    if verification_status not in ('unverified','verified','restricted') or not creator.strip() or not license_spdx.strip():
        raise argument_error('必须提供来源、许可与有效核验状态','semantic adapter rights')
    python=local_file(python_executable,root=root)
    if python.suffix.lower()!='.exe':raise argument_error('Python 必须是显式原生 .exe','python_executable')
    require_local_reference(str(model_path),field='model_path')
    model=Path(model_path).expanduser()
    if not model.is_absolute():model=root/model
    paths=model_files(model);model=model.resolve()
    proof=local_file(evidence,root=root)
    deadline,marker=_config(timeout,cancel_file,root)
    if dry_run:
        return dict(adapter_id=adapter_id,python_executable=str(python),model_path=str(model),
                    model_files=len(paths),native_runtime_probe_required=True,model_forward_calls=0)
    job=_job(root)
    _,runtime=_invoke(python,{'task':'inspect'},job,'runtime-inspection',deadline,marker)
    artifacts=[artifact_entry(python,'python'),artifact_entry(proof,'evidence')]
    artifacts += [artifact_entry(p,'model') for p in paths]
    artifacts += [artifact_entry(p,'implementation') for p in implementation_files()]
    dependencies=[artifact_entry(local_file(r['path']),'runtime') for r in runtime['runtime_artifacts']]
    if dependencies!=runtime['runtime_artifacts']:
        raise AppError('SEMANTIC_RUNTIME_CHANGED','原生执行器在登记探测后已改变',exit_code=10)
    artifacts+=dependencies
    record=dict(adapter_id=adapter_id,engine=ENGINE,protocol=PROTOCOL,python_executable=str(python),
                model_path=str(model),threads=threads,artifacts=artifacts,runtime_artifacts=dependencies,
                runtime_versions=runtime['versions'],runtime_modules=runtime['module_paths'],
                preprocessing=PREPROCESSING,dimension=DIMENSION,rights_ref='semantic_adapter_'+adapter_id,
                registered_at=now_iso(),network='disabled')
    record['sha256']=adapter_fingerprint(record)
    rights=dict(asset_id=record['rights_ref'],kind='semantic-model-adapter',sha256=record['sha256'],
        source_url='local://semantic/'+adapter_id,source_version=PROTOCOL,retrieved_at=now_iso(),
        creator=creator,license_spdx=license_spdx,license_url='',attribution='',
        permitted_uses=permitted_uses or ['internal'],permitted_channels=[],restrictions=[],derived_from=[],
        evidence=str(proof),verification_status=verification_status,takedown_status='clear',
        verified_by='explicit-local-registration' if verification_status=='verified' else '',
        notes='Local model evidence only; retrieval does not grant rights to the indexed media.')
    remaining(deadline,marker)
    snapshot=create_snapshot(root,project,label='before-semantic-adapter-register')
    candidate=copy.deepcopy(project)
    candidate.setdefault('extensions',{}).setdefault('local_semantic',{'adapters':[],'indexes':[]})['adapters'].append(record)
    operation_id=new_id('op')
    candidate.setdefault('provenance',{}).setdefault('change_log',[]).append(dict(command='semantic.adapter-register',
        at=now_iso(),operation_id=operation_id,adapter_id=adapter_id,snapshot_id=snapshot['snapshot_id']))
    ledger=load_ledger(root);add_record(ledger,rights)
    save_project(root,candidate);save_ledger(root,ledger)
    atomic_write_json(root/'operations'/f'{operation_id}.json',dict(status='succeeded',command='semantic.adapter-register',
                      operation_id=operation_id,adapter_id=adapter_id,job=str(job)))
    return dict(adapter=record,rights=rights,snapshot=snapshot,operation_id=operation_id,runtime_inspection=str(job),
                model_forward_calls=0,network='disabled',verification=verify_adapter(record))


def embed(root, adapter, items, task, *, job, device, device_index, batch_size, deadline, marker):
    if device not in ('auto','cpu','cuda'):raise argument_error('设备须为 auto/cpu/cuda','device')
    selection=select_device(device,adapter['model_path'],minimum_mib=3072,device_index=device_index)
    request=dict(task=task,adapter=adapter,items=items,batch_size=batch_size,device=selection['selected'],device_index=device_index)
    attempts=[]
    try:
        vectors,response=_invoke(adapter['python_executable'],request,job,'inference-'+selection['selected'],deadline,marker)
        attempts.append(dict(device=selection['selected'],status='succeeded',response=response))
    except AppError as exc:
        if device!='auto' or selection['selected']!='cuda' or exc.code not in ('SEMANTIC_CUDA_FAILED','SEMANTIC_CUDA_UNAVAILABLE'):
            raise
        attempts.append(dict(device='cuda',status='failed',error=exc.as_dict()))
        request['device']='cpu'
        vectors,response=_invoke(adapter['python_executable'],request,job,'inference-cpu-fallback',deadline,marker)
        attempts.append(dict(device='cpu',status='succeeded',response=response))
        selection.update(selected='cpu',fallback_reason='cuda_worker_failed',original_error=exc.as_dict())
    return vectors,dict(selection=selection,attempts=attempts,job=str(job),response=response)


def _source(root, asset):
    source=local_file(asset['uri'],root=root)
    observed=artifact_entry(source,'semantic-source')
    expected='sha256:'+str(asset.get('sha256','')).lower().removeprefix('sha256:')
    if observed['sha256']!=expected:
        raise AppError('SEMANTIC_SOURCE_CHANGED','源素材与工程登记摘要不一致',exit_code=3,path=str(source))
    return source,observed


def build_index(root, project, *, index_id, adapter_id, asset_ids=None, all_visual=False, interval=2.,
                max_per_asset=128, device='auto', device_index=0, batch_size=8, timeout=600,
                cancel_file=None, dry_run=False):
    assert_id(index_id,'index_id')
    if any(r.get('index_id')==index_id for r in registry(project).get('indexes',[])):
        raise AppError('SEMANTIC_INDEX_EXISTS','索引 ID 已存在，请使用新的 ID',exit_code=2)
    deadline,marker=_config(timeout,cancel_file,root,batch_size=batch_size,device_index=device_index)
    adapter=_checked_adapter(root,project,adapter_id)
    assets=asset_map(project)
    selected=list(asset_ids or [])
    if bool(selected)==bool(all_visual):raise argument_error('明确提供 asset-id 或 all-visual-assets，二选一','asset_id')
    if all_visual:selected=[a['id'] for a in assets.values() if a['kind'] in ('image','video') and not a.get('source',{}).get('semantic_preview')]
    if not 1<=len(selected)<=MAX_ASSETS or len(set(selected))!=len(selected):
        raise argument_error('需要 1–512 个不同的图片/视频资产','asset_id')
    # Validate the sampling profile even for an image-only collection.
    from .semantic_contract import sample_times
    sample_times(1.,interval=interval,per_asset=max_per_asset)
    sources=[];plans=[];total=0
    for ident in selected:
        remaining(deadline,marker)
        asset=assets.get(ident)
        if not asset or asset['kind'] not in ('image','video'):raise argument_error('资产缺失或不是图片/视频: '+ident,'asset_id')
        source,entry=_source(root,asset)
        samples,sampling=plan(source,asset['kind'],interval=interval,per_asset=max_per_asset,deadline=deadline,marker=marker)
        total+=len(samples)
        if total>MAX_ROWS:raise AppError('SEMANTIC_SAMPLE_BUDGET_EXCEEDED','索引最多 4096 行；请减少资产或增大间隔',exit_code=2)
        sources.append(dict(asset_id=ident,uri=asset['uri'],sha256=entry['sha256'],bytes=entry['bytes'],
                            kind=asset['kind'],rights_ref=asset['rights_ref'],sampling=sampling))
        plans.append((asset,source,samples))
    key=fingerprint(index_id).removeprefix('sha256:')[:24]
    destination=owned(root,root/'assets/semantic'/key)
    if destination.exists():raise AppError('SEMANTIC_INDEX_EXISTS','索引产物目录已存在，保留原内容',exit_code=2,path=str(destination))
    if dry_run:return dict(index_id=index_id,adapter_id=adapter_id,sources=sources,rows=total,destination=str(destination),model_forward_calls=0)
    if shutil.disk_usage(root).free<total*(512*512*3+DIMENSION*4)+256*1024**2:
        raise AppError('SEMANTIC_DISK_BUDGET','采样 PNG、向量与任务记录的磁盘预算不足',exit_code=6)
    job=_job(root);ready=job/'ready';ready.mkdir()
    rows=[];extractions=[];items=[]
    try:
        for source_index,(asset,source,samples) in enumerate(plans):
            values,extraction=extract(source,asset['kind'],samples,ready/f'frames{source_index:04}',deadline=deadline,marker=marker)
            extractions.append(dict(asset_id=asset['id'],**extraction))
            for value in values:
                ordinal=len(rows)
                frame_path=Path(value.pop('preview_path'));relative=frame_path.relative_to(ready)
                frame_id=f'sem_{key}_frame_{ordinal:04}'
                row=dict(**value,asset_id=asset['id'],kind=asset['kind'],source_uri=asset['uri'],
                         source_sha256=sources[source_index]['sha256'],rights_ref=asset['rights_ref'],
                         preview_asset_id=frame_id,preview_uri=(destination/relative).relative_to(root).as_posix())
                rows.append(row)
                items.append(dict(id=str(ordinal),path=str(frame_path),sha256=value['preview_sha256']))
        unique_items=[];by_hash={};row_to_unique=[]
        for entry in items:
            if entry['sha256'] not in by_hash:
                by_hash[entry['sha256']]=len(unique_items)
                unique_items.append(dict(entry,id=str(len(unique_items))))
            row_to_unique.append(by_hash[entry['sha256']])
        unique_vectors,inference=embed(root,adapter,unique_items,'image',job=job,device=device,device_index=device_index,
            batch_size=batch_size,deadline=deadline,marker=marker)
        vectors=check_vectors(unique_vectors[row_to_unique],len(rows))
        inference['deduplication']=dict(index_rows=len(rows),unique_image_inputs=len(unique_items),
                                       key='exact thumbnail SHA-256; source and time records remain separate')
        vector_path=ready/'vectors.f32'
        with vector_path.open('xb') as stream:stream.write(vectors.astype('<f4',copy=False).tobytes(order='C'))
        vector_hash='sha256:'+sha256_file(vector_path)
        manifest=dict(format=INDEX_FORMAT,index_id=index_id,created_at=now_iso(),adapter_id=adapter_id,
            adapter_sha256=adapter['sha256'],engine=ENGINE,preprocessing=PREPROCESSING,dimension=DIMENSION,
            dtype='float32-little-endian',rows=rows,sources=sources,
            vectors=dict(uri=(destination/'vectors.f32').relative_to(root).as_posix(),sha256=vector_hash,bytes=vector_path.stat().st_size),
            extraction=extractions,inference=inference,network='disabled',
            warnings=['SAMPLED_VISUAL_SIMILARITY_REQUIRES_REVIEW','SOURCE_AND_MODEL_RIGHTS_REMAIN_SEPARATE'])
        manifest['fingerprint']=fingerprint(manifest)
        atomic_write_json(ready/'index.json',manifest)
        for entry in items:
            if 'sha256:'+sha256_file(Path(entry['path']))!=entry['sha256']:
                raise AppError('SEMANTIC_INPUT_CHANGED','缩略图在推理后发生变化',exit_code=6)
        for asset,_,_ in plans:_source(root,asset)
        remaining(deadline,marker)
        destination.parent.mkdir(parents=True,exist_ok=True)
        ready.rename(destination)
        generated=[]
        index_asset_id=f'sem_{key}_index';vector_asset_id=f'sem_{key}_vectors'
        for aid,path,kind,probe in [(index_asset_id,destination/'index.json','generated',{}),
                                   (vector_asset_id,destination/'vectors.f32','generated',{}),
                                   *[(r['preview_asset_id'],root/r['preview_uri'],'image',r['preview_probe']) for r in rows]]:
            if aid in assets:raise AppError('SEMANTIC_ASSET_EXISTS','语义产物资产 ID 已存在',exit_code=2,path=aid)
            generated.append(dict(id=aid,kind=kind,uri=path.relative_to(root).as_posix(),sha256='sha256:'+sha256_file(path),
                probe=probe,rights_ref=aid,source=dict(semantic_index=index_id,semantic_preview=kind=='image',
                source_url='local://semantic/'+index_id,retrieved_at=now_iso())))
        record=dict(index_id=index_id,adapter_id=adapter_id,adapter_sha256=adapter['sha256'],asset_id=index_asset_id,
                    vector_asset_id=vector_asset_id,frame_asset_ids=[r['preview_asset_id'] for r in rows],
                    manifest_sha256=generated[0]['sha256'],created_at=now_iso())
        record['sha256']=fingerprint(record)
        ledger=load_ledger(root)
        dependencies=list(dict.fromkeys([s['rights_ref'] for s in sources]+[adapter['rights_ref']]))
        for asset in generated:
            add_record(ledger,dict(asset_id=asset['rights_ref'],kind='semantic-index-evidence',sha256=asset['sha256'],
                source_url='local://semantic/'+index_id,source_version=INDEX_FORMAT,retrieved_at=now_iso(),
                creator='Local source/model derivation',license_spdx='LicenseRef-Source-And-Model-Dependencies',
                license_url='',attribution='',permitted_uses=['internal'],permitted_channels=[],restrictions=[],
                derived_from=dependencies,evidence=generated[0]['uri'],verification_status='verified',
                verified_by='local-semantic-source-and-model-hash',takedown_status='clear',
                notes='Verified derivation, not a grant of rights to source media or model outputs.'))
        candidate=copy.deepcopy(project);candidate.setdefault('assets',[]).extend(generated)
        candidate.setdefault('extensions',{}).setdefault('local_semantic',{'adapters':[],'indexes':[]}).setdefault('indexes',[]).append(record)
        from .validator import validate_project
        validation=validate_project(root,candidate,rights_ledger=ledger,strict_rights=False)
        if not validation['ok']:raise AppError('SEMANTIC_PROJECT_INVALID','索引登记后的工程校验失败',exit_code=2,diagnostics=validation)
        snapshot=create_snapshot(root,project,label='before-semantic-index')
        operation_id=new_id('op')
        candidate.setdefault('provenance',{}).setdefault('change_log',[]).append(dict(command='semantic.index',
            operation_id=operation_id,index_id=index_id,at=now_iso(),snapshot_id=snapshot['snapshot_id']))
        save_project(root,candidate);save_ledger(root,ledger)
        atomic_write_json(root/'operations'/f'{operation_id}.json',dict(command='semantic.index',operation_id=operation_id,
                          status='succeeded',index_id=index_id,job=str(job)))
        return dict(index=record,manifest=str(destination/'index.json'),rows=len(rows),source_assets=len(sources),
                    generated_assets=len(generated),inference=inference,validation=validation,snapshot=snapshot,
                    operation_id=operation_id,verification_scope=verification_summary(),network='disabled')
    except BaseException:
        # Only a fresh, operation-owned output tree is removed. Diagnostic job
        # records survive; the CLI transaction restores metadata on exceptions.
        if destination.exists():shutil.rmtree(destination)
        if ready.exists():shutil.rmtree(ready)
        raise


def read_index(root, project, index_id):
    record=item(project,'indexes',index_id)
    try:
        if record['sha256']!=fingerprint({k:v for k,v in record.items() if k!='sha256'}):
            raise ValueError('Index registration fingerprint changed')
        adapter=_checked_adapter(root,project,record['adapter_id'])
        if adapter['sha256']!=record['adapter_sha256']:raise ValueError('Index model or implementation is stale')
        assets=asset_map(project)
        index_asset=assets[record['asset_id']];path=local_file(index_asset['uri'],root=root)
        if not path.is_relative_to(owned(root,root/'assets/semantic')):
            raise ValueError('Manifest outside project semantic asset tree')
        actual=artifact_entry(path,'semantic-index')
        if actual['sha256']!=record['manifest_sha256'] or actual['sha256']!=index_asset['sha256']:
            raise ValueError('Index manifest hash changed')
        manifest=json_object(path,max_bytes=32*1024**2)
        if (manifest['format']!=INDEX_FORMAT or manifest['index_id']!=index_id or manifest['dimension']!=DIMENSION
                or manifest['dtype']!='float32-little-endian' or manifest['preprocessing']!=PREPROCESSING
                or manifest['adapter_sha256']!=adapter['sha256']
                or manifest['fingerprint']!=fingerprint({k:v for k,v in manifest.items() if k!='fingerprint'})):
            raise ValueError('Index manifest contract changed')
        rows,sources=manifest['rows'],manifest['sources']
        if not isinstance(rows,list) or not 1<=len(rows)<=MAX_ROWS or not isinstance(sources,list) or not 1<=len(sources)<=MAX_ASSETS:
            raise ValueError('Index row/source budget invalid')
        if len({s['asset_id'] for s in sources})!=len(sources):raise ValueError('Duplicate source records')
        source_map={s['asset_id']:s for s in sources}
        for source in sources:
            asset=assets[source['asset_id']]
            if any(asset.get(key)!=source[key] for key in ('uri','kind','rights_ref')):
                raise ValueError('Source project binding changed')
            _,observed=_source(root,asset)
            if observed['sha256']!=source['sha256'] or observed['bytes']!=source['bytes']:
                raise ValueError('Indexed source changed')
        if [r['preview_asset_id'] for r in rows]!=record['frame_asset_ids']:
            raise ValueError('Frame inventory changed')
        for row in rows:
            source=source_map[row['asset_id']]
            if (row['kind']!=source['kind'] or row['source_sha256']!=source['sha256'] or row['source_uri']!=source['uri']
                    or type(row['sample_seconds']) not in (int,float) or not math.isfinite(row['sample_seconds'])
                    or not isinstance(row['requested_seconds'],list) or not row['requested_seconds']
                    or any(type(t) not in (int,float) or not math.isfinite(t) or t<0 for t in row['requested_seconds'])):
                raise ValueError('Invalid frame/source/time binding')
            preview=local_file(row['preview_uri'],root=root)
            if not preview.is_relative_to(path.parent):raise ValueError('Preview outside index tree')
            entry=artifact_entry(preview,'semantic-preview')
            asset=assets[row['preview_asset_id']]
            if entry['sha256']!=row['preview_sha256'] or asset['uri']!=row['preview_uri'] or asset['sha256']!=entry['sha256']:
                raise ValueError('Preview hash/binding changed')
            png_probe(preview)
        vector=local_file(manifest['vectors']['uri'],root=root)
        if vector!=path.with_name('vectors.f32'):raise ValueError('Vector outside expected index file')
        entry=artifact_entry(vector,'semantic-vectors');asset=assets[record['vector_asset_id']]
        if (entry['bytes']!=len(rows)*DIMENSION*4 or entry['bytes']!=manifest['vectors']['bytes']
                or entry['sha256']!=manifest['vectors']['sha256'] or entry['sha256']!=asset['sha256']
                or asset['uri']!=manifest['vectors']['uri']):
            raise ValueError('Vector hash, byte budget or project binding changed')
        import numpy as np
        vectors=check_vectors(np.fromfile(vector,dtype='<f4').reshape(len(rows),DIMENSION),len(rows))
        return manifest,vectors,adapter
    except (KeyError,ValueError,TypeError,AttributeError,OSError) as exc:
        raise AppError('SEMANTIC_INDEX_INVALID','索引已损坏、过期或工程引用已改变',exit_code=6,cause=str(exc)) from exc


def queries_from(*,query=None,queries_file=None,image=None,root):
    if sum(v is not None for v in (query,queries_file,image))!=1:
        raise argument_error('query、queries-file、image 必须三选一','semantic search')
    if image is not None:
        path=local_file(image,root=root);entry=artifact_entry(path,'semantic-query-image')
        if entry['bytes']>50*1024**2:raise argument_error('参考图最多 50MiB','image')
        return 'image',[dict(id='reference',path=str(path),sha256=entry['sha256'])]
    values=[dict(id='query',text=query)] if query is not None else json_object(local_file(queries_file,root=root),max_bytes=1024**2).get('queries')
    if not isinstance(values,list) or not 1<=len(values)<=128:raise argument_error('查询文件需要 1–128 项 queries','queries_file')
    identifiers=set();items=[]
    for value in values:
        if (not isinstance(value,dict) or not {'id','text'}<=set(value)
                or set(value)-{'id','text','include','exclude'}):
            raise argument_error('每项查询允许 id/text/include/exclude；不接收标签或参考答案','queries_file')
        assert_id(value['id'],'query_id')
        if (value['id'] in identifiers or not isinstance(value['text'],str) or not value['text'].strip()
                or len(value['text'])>1024):raise argument_error('查询 ID 须唯一，文本须为 1–1024 字符','query')
        identifiers.add(value['id']);items.append(dict(value))
    return 'text',items


def search(root,project,*,index_id,query=None,queries_file=None,image=None,limit=5,minimum=-1.,
           kind=None,distinct_assets=True,device='auto',device_index=0,batch_size=8,timeout=600,
           cancel_file=None,dry_run=False,calibration_id=None,query_mode='clauses'):
    from .semantic_queries import prepare, rank_clauses
    from .semantic_decision import load_profile
    deadline,marker=_config(timeout,cancel_file,root,batch_size=batch_size,device_index=device_index)
    manifest,vectors,adapter=read_index(root,project,index_id)
    # Validate ranking options before any model load or derivative job.
    rank(vectors,vectors[0],manifest['rows'],limit=limit,minimum=minimum,kind=kind,distinct_assets=distinct_assets)
    task,items=queries_from(query=query,queries_file=queries_file,image=image,root=root)
    if query_mode not in ('raw','clauses'):
        raise argument_error('query-mode 须为 clauses/raw','query_mode')
    if (calibration_id and (task!='text' or query_mode!='clauses')
            or (query_mode=='raw' and any(set(v)-{'id','text'} for v in items))):
        raise argument_error('校准仅用于 clauses 文本查询；raw 不接受结构条件','query_mode')
    plans,inputs=prepare(items) if task=='text' and query_mode=='clauses' else (None,items)
    profile=load_profile(root,project,calibration_id,manifest,kind=kind) if calibration_id else None
    if dry_run:return dict(index_id=index_id,task=task,queries=items,index_rows=len(vectors),model_forward_calls=0,
                           text_token_budget_checked_by_worker=task=='text',query_mode=query_mode,clauses=plans,
                           calibration_id=calibration_id,calibration_verified=bool(profile))
    job=_job(root)
    features,inference=embed(root,adapter,inputs,task,job=job,device=device,device_index=device_index,
        batch_size=batch_size,deadline=deadline,marker=marker)
    if profile and (inference['response']['device']!=profile['device']
                    or inference['response']['device_index']!=profile['device_index']):
        raise AppError('SEMANTIC_CALIBRATION_DEVICE_MISMATCH',
            '当前推理设备与校准设备不符；请使用匹配档案或分别校准 CPU/GPU',exit_code=6)
    ledger={r['asset_id']:r for r in active_records(load_ledger(root))}
    results=[]
    tps=project.get('settings',{}).get('timebase',{}).get('ticks_per_second',1_000_000)
    for ordinal,value in enumerate(items):
        if plans is not None:
            hits=rank_clauses(vectors,features,manifest['rows'],plans[ordinal],limit=limit,minimum=minimum,
                kind=kind,distinct_assets=distinct_assets,cutoff=profile['fit']['cutoff'] if profile else None)
        else:
            hits=rank(vectors,features[ordinal],manifest['rows'],limit=limit,minimum=minimum,
                      kind=kind,distinct_assets=distinct_assets)
        for hit in hits:
            hit['rights_verification_status']=ledger.get(hit['rights_ref'],{}).get('verification_status','missing')
            hit['editable_reference']=dict(asset_id=hit['asset_id'],source_seek_seconds=hit['requested_seconds'][0],
                source_in_tick=round(hit['requested_seconds'][0]*tps),point_sample_only=True,duration_requires_review=True)
        results.append(dict(query=value,hits=hits,clauses=plans[ordinal] if plans is not None else None,
            decision=('calibrated_match' if hits else 'no_calibrated_match') if profile else 'candidates_require_review',
            calibration_id=calibration_id,semantic_truth_verified=False))
    remaining(deadline,marker)
    return dict(index_id=index_id,task=task,results=results,limit=limit,minimum_score=minimum,kind=kind,
        distinct_assets=distinct_assets,inference=inference,network='disabled',
        query_mode=query_mode,calibration_id=calibration_id,
        calibration_fit=profile['fit'] if profile else None,
        score_kind='minimum_clause_cosine_not_probability' if plans is not None else 'cosine_similarity_not_probability',
        rights_checked_for_publication=False,
        warnings=['SAMPLED_VISUAL_SIMILARITY_REQUIRES_REVIEW',
                  'CALIBRATION_IS_EMPIRICAL_NOT_UNIVERSAL_REJECTION' if profile else 'OPEN_SET_REQUIRES_CALIBRATION_PROFILE',
                  'EXCLUSIONS_ARE_RELATIVE_FRAME_EVIDENCE_NOT_OBJECT_DETECTION',
                  'MODEL_SIMILARITY_DOES_NOT_PROVE_ACTION_IDENTITY_OR_MEDIA_RIGHTS'])
