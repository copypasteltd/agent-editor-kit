"""Project-aware offline speech denoising, immutable recipes and editable audio."""
import copy,math
from pathlib import Path
from .local_enhancement import ENGINE,PROTOCOL,prepare_adapter,verify_adapter,error,options,settings
from . import enhancement_plan as planning
from .artifact_locks import verification_scope
from .model_registry import load_model_registry,save_model_registry,adapter_for
from .project import load_project,asset_map,find_sequence,find_track,create_snapshot,save_project
from .rights import load_ledger,save_ledger,active_records,add_record
from .policy import resolve_local_path
from .utils import assert_id,atomic_write_json,now_iso,new_id,sha256_file
from .errors import argument_error,AppError

def add_parser(actions,leaf):
    adapter=actions.add_parser('enhancement-adapter',help='显式登记本地DeepFilterNet3 CUDA对白增强模型')
    registrations=adapter.add_subparsers(dest='adapter_action',required=True)
    for action in ('register','list','inspect'):
        p=leaf(registrations.add_parser(action));p.add_argument('--project',required=True)
        if action!='list':p.add_argument('--adapter-id',required=True)
        if action=='register':
            p.add_argument('--model-path',required=True);p.add_argument('--executable',required=True);p.add_argument('--evidence',required=True)
            p.add_argument('--threads',type=int,default=4);p.add_argument('--segment-seconds',type=float,default=10.);p.add_argument('--overlap',type=float,default=.25)
            p.add_argument('--license-spdx',default='LicenseRef-UNVERIFIED');p.add_argument('--license-url',default='');p.add_argument('--creator',default='unknown')
            p.add_argument('--permitted-use',action='append',default=['internal']);p.add_argument('--verification-status',choices=['unverified','verified','restricted'],default='unverified')
    p=leaf(actions.add_parser('enhance',help='实际CUDA全带宽对白降噪；独立Float32音频资产与可编辑轨道'))
    p.add_argument('--project',required=True);p.add_argument('--adapter-id',required=True);p.add_argument('--asset-id',required=True,help='新输出ID')
    p.add_argument('--source-asset-id');p.add_argument('--recipe-asset-id');p.add_argument('--start-seconds',type=float);p.add_argument('--end-seconds',type=float)
    p.add_argument('--strength',type=float);p.add_argument('--attenuation-limit-db',type=float)
    p.add_argument('--storage-budget-mib',type=int,default=2048);p.add_argument('--timeout-seconds',type=float,default=900.)
    p.add_argument('--cancel-file');p.add_argument('--apply',action='store_true');p.add_argument('--sequence-id');p.add_argument('--track-id');p.add_argument('--timeline-start-seconds',type=float,default=0.)

def adapter_command(args):
    from .cli import _envelope,_operation
    with verification_scope():
        root,project=load_project(args.project);registry=load_model_registry(root)
        if args.adapter_action=='list':return _envelope('audio.enhancement-adapter.list',args,data=dict(adapters=[a for a in registry['adapters'] if a.get('engine')==ENGINE]))
        existing=adapter_for(registry,args.adapter_id)
        if args.adapter_action=='inspect':
            if not existing or existing.get('engine')!=ENGINE:raise error('ADAPTER_MISSING','找不到对白增强适配器')
            return _envelope('audio.enhancement-adapter.inspect',args,data=dict(adapter=existing,verification=verify_adapter(existing)))
        if existing:raise error('ADAPTER_EXISTS','适配器ID已存在，请使用新ID')
        adapter,rights=prepare_adapter(root,adapter_id=args.adapter_id,model_path=args.model_path,executable=args.executable,evidence=args.evidence,
            creator=args.creator,license_spdx=args.license_spdx,license_url=args.license_url,permitted_uses=args.permitted_use,verification_status=args.verification_status,
            options=dict(threads=args.threads,segment_seconds=args.segment_seconds,overlap=args.overlap))
        data=dict(adapter=adapter,rights=rights)
        if args.dry_run:return _envelope('audio.enhancement-adapter.register',args,status='planned',data=data)
        snapshot=create_snapshot(root,copy.deepcopy(project),label='before-enhancement-register');operation_id=new_id('op');ledger=load_ledger(root)
        registry['adapters'].append(adapter);add_record(ledger,rights);save_model_registry(root,registry);save_ledger(root,ledger)
        project['provenance'].setdefault('local_adapters',[]).append(dict(adapter_id=args.adapter_id,kind=adapter['kind'],engine=ENGINE,model_sha256=adapter['model_sha256'],registered_at=adapter['registered_at']))
        project['provenance']['change_log'].append(dict(command='audio.enhancement-adapter.register',operation_id=operation_id,adapter_id=args.adapter_id,at=now_iso()))
        save_project(root,project);_operation(root,operation_id,dict(command='audio.enhancement-adapter.register',status='succeeded',snapshot_id=snapshot['snapshot_id'],created_at=now_iso()))
        return _envelope('audio.enhancement-adapter.register',args,data=data,operation_id=operation_id)

def command(args):
    from .cli import _envelope,_operation,_progress,_recompute_sequence_duration
    from .job_workspaces import managed_workspace
    from .validator import validate_project
    from .native_audio_clock import cancel
    from .media import probe_media
    with verification_scope():
        root,project=load_project(args.project);assets=asset_map(project);assert_id(args.asset_id,'asset-id')
        if not math.isfinite(args.timeout_seconds) or not 0<args.timeout_seconds<=7200 or not math.isfinite(args.timeline_start_seconds) or args.timeline_start_seconds<0:raise argument_error('超时须为0..7200正秒数，时间线起点须非负')
        if type(args.storage_budget_mib)is not int or not 64<=args.storage_budget_mib<=8192:raise argument_error('storage-budget-mib须为64..8192')
        if bool(args.apply)!=bool(args.track_id):raise argument_error('--apply须同时指定独立音频track-id')
        marker=resolve_local_path(root,args.cancel_file,field='cancel-file') if args.cancel_file else None;cancel(marker)
        previous=None
        if args.recipe_asset_id:
            parent=assets.get(args.recipe_asset_id)
            if not parent or not (previous:=parent.get('source',{}).get('speech_enhancement')):raise error('RECIPE_MISSING','指定资产没有对白增强配方')
            planning.validate_recipe(previous,asset=parent,assets=assets)
        source_id=args.source_asset_id or (previous['source_asset_id'] if previous else None);asset=assets.get(source_id)
        if not asset or asset['kind'] not in {'audio','video'}:raise error('SOURCE','须明确选择已有本地音频/视频资产')
        path=resolve_local_path(root,asset['uri'],field='source-asset');cancel(marker)
        if not path.is_file() or 'sha256:'+sha256_file(path)!=asset['sha256']:raise error('SOURCE_CHANGED','源资产字节与登记摘要不符')
        probe=probe_media(path);audio=probe.get('audio') or {};duration=audio.get('duration_seconds') or probe.get('duration_seconds')
        if not audio.get('codec') or not 8000<=audio['sample_rate']<=96000 or audio['channels'] not in (1,2) or duration is not None and (not math.isfinite(duration) or not 0<duration<=1800):raise error('SOURCE_FORMAT','要求8..96kHz单/双声道，完整源时钟不超过1800秒')
        source=dict(asset_id=source_id,path=str(path),sha256=asset['sha256'])
        adapter=adapter_for(load_model_registry(root),args.adapter_id)
        if not adapter or adapter.get('engine')!=ENGINE or not verify_adapter(adapter)['ok']:raise error('ADAPTER_UNAVAILABLE','须显式登记且字节匹配的DeepFilterNet3 CUDA模型')
        if previous and previous['model_sha256']!=adapter['model_sha256']:raise error('RECIPE_MODEL','重跑须使用配方中相同模型字节')
        selection=planning.selection(**{k:getattr(args,k) if getattr(args,k)is not None else (previous['selection'][k] if previous else default) for k,default in dict(start_seconds=0.,end_seconds=None).items()})
        opts=options(**{k:getattr(args,k) if getattr(args,k)is not None else (previous['options'][k] if previous else default) for k,default in dict(strength=1.,attenuation_limit_db=None).items()})
        if previous:
            adapter=copy.deepcopy(adapter)
            # Recurrent/overlap boundaries are part of an immutable replay.
            if {k:adapter['settings'][k] for k in previous['model_settings']}!=previous['model_settings']:raise error('RECIPE_SETTINGS','配方重跑须登记相同分段、重叠和线程设置')
        ledger=load_ledger(root);rights={r['asset_id']:r for r in active_records(ledger)}
        if args.asset_id in assets or args.asset_id in rights:raise error('OUTPUT_EXISTS','输出ID已存在，须使用新ID')
        dependencies=[]
        for ident,digest_ in [(asset.get('rights_ref') or source_id,asset['sha256']),(adapter['rights_ref'],adapter['sha256'])]:
            if ident not in rights or rights[ident]['sha256']!=digest_:raise error('RIGHTS_MISSING','源或模型缺少摘要匹配的权利记录')
            if ident not in dependencies:dependencies.append(ident)
        sequence=find_sequence(project,args.sequence_id);track=find_track(sequence,args.track_id) if args.apply else None
        if track and (track.get('locked') or track['kind']!='audio'):raise argument_error('增强须使用未锁定的独立音频轨道')
        output=root/'assets/derived'/(args.asset_id+'.wav')
        if output.exists():raise error('OUTPUT_EXISTS','增强输出文件已存在')
        warnings=[dict(code='ENHANCEMENT_LISTENING_REVIEW_REQUIRED',message='须试听对白误伤、金属音、混响和立体声变化；该模型不是完整去混响或音乐保真内核。分段状态重置，48kHz外采样率明确重采样。')]
        planned=dict(engine=ENGINE,source=source,adapter_id=args.adapter_id,selection=selection,options=opts,model_settings=adapter['settings'],
            output=str(output),apply=args.apply,network='disabled',native_clock_deferred=True,model_inference_executed=False)
        if args.dry_run:return _envelope('audio.enhance',args,status='planned',data=planned,warnings=warnings)
        cancel(marker);snapshot=create_snapshot(root,copy.deepcopy(project),label='before-audio-enhance');operation_id=new_id('op');report_path=root/'validation'/('enhancement_'+operation_id+'.json')
        try:
            with managed_workspace(root,'speech-enhancement') as job:
                from .enhancement_pipeline import execute
                def progress(phase,done,total):_progress(args,operation_id,'progress','audio.enhance',min(95,round(90*done/total)),phase)
                _progress(args,operation_id,'started','audio.enhance',0,'执行原生CUDA对白增强')
                stage,result=execute(root,job,source,adapter,selection=selection,options=opts,storage_budget_bytes=args.storage_budget_mib*1024**2,
                    timeout=args.timeout_seconds,cancel_file=marker,operation_id=operation_id,progress=progress)
                cancel(marker);r=result['worker']['range'];tps=project['settings']['timebase']['ticks_per_second'];start=round(args.timeline_start_seconds*tps);span=round(r['samples']*tps/r['sample_rate'])
                if span<1:raise error('TIMELINE_CLOCK','增强选区不足一个工程tick')
                if track and track.get('overlap_policy','reject')!='allow' and any(max(start,c['timeline_start_tick'])<min(start+span,c['timeline_start_tick']+c['duration_tick']) for c in track['clips']):raise argument_error('增强入轨区间与现有片段重叠')
                job.publish(stage,output)
                generated=dict(id=args.asset_id,kind='audio',uri=output.relative_to(root).as_posix(),sha256=result['sha256'],rights_ref=args.asset_id,probe=result['probe'],
                    source=dict(source_url='local://speech-enhancement/'+operation_id,retrieved_at=now_iso(),original_name=output.name,derived_from=[source_id],speech_enhancement=result['recipe']))
                project['assets'].append(generated)
                record=dict(asset_id=args.asset_id,kind='audio',sha256=generated['sha256'],source_url=generated['source']['source_url'],source_version=PROTOCOL,retrieved_at=now_iso(),
                    creator='local-speech-enhancement',license_spdx='LicenseRef-UNVERIFIED',license_url='',attribution='',permitted_uses=['internal'],permitted_channels=[],restrictions=[],derived_from=dependencies,
                    evidence='',verification_status='unverified',verified_by='',takedown_status='clear',notes='Enhanced audio inherits source/model rights; requires listening review.')
                add_record(ledger,record);save_ledger(root,ledger);clip=None
                if track:
                    clip=dict(id=new_id('clip_enhance'),asset_id=args.asset_id,timeline_start_tick=start,duration_tick=span,source_in_tick=0,source_out_tick=span)
                    track['clips'].append(clip);_recompute_sequence_duration(sequence)
                validation=validate_project(root,project)
                if not validation['ok']:raise AppError('ENHANCEMENT_PROJECT_INVALID','增强入库后工程校验失败，事务回滚',exit_code=2,diagnostics=validation)
                report=dict(protocol=PROTOCOL,operation_id=operation_id,asset=generated,rights=record,generation=result,clip=clip,snapshot_id=snapshot['snapshot_id'],validation=validation)
                atomic_write_json(report_path,report);project['provenance']['change_log'].append(dict(command='audio.enhance',operation_id=operation_id,asset_id=args.asset_id,report=str(report_path),at=now_iso()))
                cancel(marker);save_project(root,project);_operation(root,operation_id,dict(command='audio.enhance',operation_id=operation_id,status='succeeded',report=str(report_path),created_at=now_iso()))
                _progress(args,operation_id,'completed','audio.enhance',100,'CUDA增强、完整PCM往返和可编辑入轨已核验')
                return _envelope('audio.enhance',args,data=report,warnings=warnings,operation_id=operation_id)
        except BaseException:report_path.unlink(missing_ok=True);raise
