"""Project-aware CUDA interpolation and independent editable slow-motion clips."""
import copy,math
from pathlib import Path
from . import interpolation_plan as planning
from .local_interpolation import ENGINE,PROTOCOL,prepare_adapter,verify_adapter,error
from .model_registry import load_visual_model_registry,save_visual_model_registry,visual_adapter_for
from .project import load_project,asset_map,find_sequence,find_track,create_snapshot,save_project
from .rights import load_ledger,save_ledger,active_records,add_record
from .utils import assert_id,atomic_write_json,now_iso,new_id
from .policy import resolve_local_path
from .artifact_locks import verification_scope
from .errors import AppError,argument_error

def add_parser(subs,leaf):
    domain=subs.add_parser('interpolate',help='本地CUDA RIFE神经补帧，保留原生CFR/VFR时钟及原音轨')
    actions=domain.add_subparsers(dest='action',required=True)
    adapter=actions.add_parser('adapter');registrations=adapter.add_subparsers(dest='adapter_action',required=True)
    for action in ('register','list','inspect'):
        p=leaf(registrations.add_parser(action));p.add_argument('--project',required=True)
        if action!='list':p.add_argument('--adapter-id',required=True)
        if action=='register':
            p.add_argument('--model-path',required=True);p.add_argument('--executable',required=True);p.add_argument('--evidence',required=True)
            p.add_argument('--device',choices=['cuda'],default='cuda');p.add_argument('--threads',type=int,default=4);p.add_argument('--scale',type=float,choices=[.25,.5,1.,2.],default=1.)
            p.add_argument('--license-spdx',default='LicenseRef-UNVERIFIED');p.add_argument('--license-url',default='');p.add_argument('--creator',default='unknown')
            p.add_argument('--permitted-use',action='append',default=['internal']);p.add_argument('--verification-status',choices=['unverified','verified','restricted'],default='unverified')
    p=leaf(actions.add_parser('generate'));p.add_argument('--project',required=True);p.add_argument('--adapter-id',required=True);p.add_argument('--asset-id',required=True)
    p.add_argument('--source-asset-id');p.add_argument('--recipe-asset-id');p.add_argument('--factor',type=int,choices=range(2,9))
    p.add_argument('--start-frame',type=int);p.add_argument('--end-frame',type=int)
    p.add_argument('--cut-after-frame',type=int,action='append');p.add_argument('--scene-cut-threshold',type=float)
    p.add_argument('--storage-budget-mib',type=int,default=2048);p.add_argument('--timeout-seconds',type=float,default=3600);p.add_argument('--cancel-file')
    p.add_argument('--apply',action='store_true');p.add_argument('--sequence-id');p.add_argument('--video-track-id');p.add_argument('--audio-track-id')
    p.add_argument('--timeline-start-seconds',type=float,default=0);p.add_argument('--playback-speed',type=float,default=1.)

def adapter_command(args):
    from .cli import _envelope,_operation
    with verification_scope():
        root,project=load_project(args.project);registry=load_visual_model_registry(root)
        if args.adapter_action=='list':return _envelope('interpolate.adapter.list',args,data=dict(adapters=[a for a in registry['adapters'] if a.get('engine')==ENGINE]))
        existing=visual_adapter_for(registry,args.adapter_id)
        if args.adapter_action=='inspect':
            if not existing or existing.get('engine')!=ENGINE:raise error('ADAPTER_MISSING','找不到补帧适配器')
            return _envelope('interpolate.adapter.inspect',args,data=dict(adapter=existing,verification=verify_adapter(existing)))
        if existing:raise error('ADAPTER_EXISTS','适配器ID已存在，请选新ID')
        adapter,rights=prepare_adapter(root,adapter_id=args.adapter_id,model_path=args.model_path,executable=args.executable,evidence=args.evidence,
            creator=args.creator,license_spdx=args.license_spdx,license_url=args.license_url,permitted_uses=args.permitted_use,
            verification_status=args.verification_status,options=dict(device=args.device,threads=args.threads,scale=args.scale))
        data=dict(adapter=adapter,rights=rights)
        if args.dry_run:return _envelope('interpolate.adapter.register',args,status='planned',data=data)
        ledger=load_ledger(root);snapshot=create_snapshot(root,copy.deepcopy(project),label='before-interpolate-register');operation_id=new_id('op')
        registry['adapters'].append(adapter);add_record(ledger,rights)
        project['provenance'].setdefault('local_adapters',[]).append(dict(adapter_id=args.adapter_id,kind=adapter['kind'],engine=ENGINE,model_sha256=adapter['model_sha256'],registered_at=adapter['registered_at']))
        project['provenance']['change_log'].append(dict(command='interpolate.adapter.register',operation_id=operation_id,adapter_id=args.adapter_id,at=now_iso()))
        save_visual_model_registry(root,registry);save_ledger(root,ledger);save_project(root,project)
        _operation(root,operation_id,dict(command='interpolate.adapter.register',status='succeeded',snapshot_id=snapshot['snapshot_id'],created_at=now_iso()))
        return _envelope('interpolate.adapter.register',args,data=data,operation_id=operation_id)

def generate_command(args):
    from .cli import _envelope,_operation,_progress,_recompute_sequence_duration
    from .job_workspaces import managed_workspace
    from .validator import validate_project
    from .native_audio_clock import cancel
    from .reverse_video_clock import probe_frames
    with verification_scope():
        root,project=load_project(args.project);assets=asset_map(project);assert_id(args.asset_id,'asset-id')
        if not math.isfinite(args.timeout_seconds) or not 0<args.timeout_seconds<=604800 or not math.isfinite(args.timeline_start_seconds) or args.timeline_start_seconds<0 or not math.isfinite(args.playback_speed) or not .01<=args.playback_speed<=100:
            raise argument_error('须指定有限正超时、非负时间线起点与0.01..100播放速度')
        if not args.apply and args.playback_speed!=1:raise argument_error('playback-speed仅在--apply入轨时生效；生成资产保留源时长')
        marker=resolve_local_path(root,args.cancel_file,field='cancel-file') if args.cancel_file else None;cancel(marker)
        old=None
        if args.recipe_asset_id:
            parent=assets.get(args.recipe_asset_id)
            if not parent or not (old:=parent.get('source',{}).get('interpolation')):raise error('RECIPE_MISSING','指定资产没有补帧配方')
            planning.validate_recipe(old,asset=parent,assets=assets)
        source_id=args.source_asset_id or (old['source_asset_id'] if old else None)
        source=planning.reference(root,assets.get(source_id));cancel(marker)
        adapter=visual_adapter_for(load_visual_model_registry(root),args.adapter_id)
        if not adapter or adapter.get('engine')!=ENGINE or not verify_adapter(adapter)['ok']:raise error('ADAPTER_UNAVAILABLE','须显式登记且字节匹配的RIFE4.25 CUDA适配器')
        pts,durations,stream,_=probe_frames(Path(source['path']),timeout=min(args.timeout_seconds,300),cancel_file=marker)
        clock=dict(time_base=stream['time_base'],pts=list(pts),durations=list(durations))
        if (int(stream['width']),int(stream['height']))!=(source['probe']['video']['width'],source['probe']['video']['height']):raise error('SOURCE_RASTER','原生帧画幅与资产探测不符')
        selected={}
        for name,default in dict(factor=2,start_frame=0,end_frame=None,cut_after_frame=[],scene_cut_threshold=.35).items():
            supplied=getattr(args,name)
            if supplied is not None:selected[name]=None if name=='scene_cut_threshold' and supplied==0 else supplied
            elif old and name in old['options']:selected[name]=old['options'][name]
            elif old and name=='factor':selected[name]=old['video']['factor']
            elif old and name in old['range'] and source_id==old['source_asset_id']:selected[name]=old['range'][name]
            else:selected[name]=default
        plan=planning.configuration(source,clock,settings=adapter['settings'],storage_budget_mib=args.storage_budget_mib,**selected)
        ledger=load_ledger(root);rights={r['asset_id']:r for r in active_records(ledger)}
        if args.asset_id in assets or args.asset_id in rights:raise error('OUTPUT_EXISTS','新资产ID已存在，原内容保留')
        dependencies=[]
        for ident,digest in [(adapter['rights_ref'],adapter['sha256']),(assets[source_id].get('rights_ref') or source_id,assets[source_id]['sha256'])]:
            if ident not in rights or rights[ident]['sha256']!=digest:raise error('RIGHTS_MISSING','模型或源缺少摘要匹配的权利记录')
            if ident not in dependencies:dependencies.append(ident)
        expected_tracks=bool(args.video_track_id) and bool(args.audio_track_id)==bool(plan['audio'])
        if args.apply and not expected_tracks or not args.apply and (args.video_track_id or args.audio_track_id):raise argument_error('--apply须指定画面轨，有源音轨时还须指定音频轨')
        tps=project['settings']['timebase']['ticks_per_second'];start=round(args.timeline_start_seconds*tps);source_span=round(plan['video']['duration_seconds']*tps);duration=round(source_span/args.playback_speed)
        if source_span<1 or duration<1:raise error('TIMELINE_CLOCK','选择不足一个项目时钟tick')
        sequence=find_sequence(project,args.sequence_id);tracks=[]
        if args.apply:
            for ident,kind in [(args.video_track_id,'video')]+([(args.audio_track_id,'audio')] if plan['audio'] else []):
                track=find_track(sequence,ident)
                if track.get('locked') or track['kind'] not in ({'video','overlay'} if kind=='video' else {'audio'}):raise argument_error('须使用未锁定且类型匹配的轨道')
                if track.get('overlap_policy','reject')!='allow' and any(max(start,c['timeline_start_tick'])<min(start+duration,c['timeline_start_tick']+c['duration_tick']) for c in track['clips']):raise argument_error('入轨区间与现有片段重叠')
                tracks.append(track)
        output=root/'assets/derived'/(args.asset_id+'.mov')
        if output.exists():raise error('OUTPUT_EXISTS','输出路径已存在，原内容保留')
        warnings=[dict(code='INTERPOLATION_REVIEW_REQUIRED',message='神经补帧须复核遮挡/细线/快速运动；差分阈值不是语义切镜识别，切镜可显式指定。末帧区间明确保持，不外推。')]
        if args.dry_run:return _envelope('interpolate.generate',args,status='planned',data=dict(configuration=plan,source=source,rights_dependencies=dependencies,model_inference_executed=False,preflight_native_frame_probe_executed=True,pipeline_timeout_excludes_preflight=True),warnings=warnings)
        cancel(marker);snapshot=create_snapshot(root,copy.deepcopy(project),label='before-interpolate-generate');operation_id=new_id('op');report_path=root/'validation'/('interpolation_'+operation_id+'.json')
        try:
            with managed_workspace(root,'frame-interpolation') as job:
                from .interpolation_pipeline import execute
                _progress(args,operation_id,'started','interpolate.generate',0,'执行本地CUDA神经补帧')
                stage,result=execute(root,job,plan,source,adapter,timeout=args.timeout_seconds,cancel_file=marker,operation_id=operation_id,
                    progress=lambda frame,total:_progress(args,operation_id,'progress','interpolate.generate',round(90*frame/total),f'补帧 {frame}/{total}'))
                cancel(marker);job.publish(stage,output)
                asset=dict(id=args.asset_id,kind='video',uri=output.relative_to(root).as_posix(),sha256=result['sha256'],rights_ref=args.asset_id,probe=result['probe'],
                    source=dict(source_url='local://interpolation/'+operation_id,retrieved_at=now_iso(),original_name=output.name,derived_from=[source_id],interpolation=result['recipe']))
                project['assets'].append(asset)
                record=dict(asset_id=args.asset_id,kind='video',sha256=asset['sha256'],source_url=asset['source']['source_url'],source_version=PROTOCOL,retrieved_at=now_iso(),
                    creator='local-neural-interpolation',license_spdx='LicenseRef-UNVERIFIED',license_url='',attribution='',permitted_uses=['internal'],permitted_channels=[],restrictions=[],
                    derived_from=dependencies,evidence='',verification_status='unverified',verified_by='',takedown_status='clear',notes='Original source, model and generated content rights remain separate.')
                add_record(ledger,record);save_ledger(root,ledger);clips=[];link_id=new_id('link_interpolate') if tracks else None
                for track in tracks:
                    clip=dict(id=new_id('clip_interpolate'),asset_id=args.asset_id,timeline_start_tick=start,source_in_tick=0,source_out_tick=source_span,duration_tick=duration,speed=args.playback_speed,link_id=link_id)
                    track['clips'].append(clip);clips.append(dict(track_id=track['id'],clip=clip))
                if tracks:_recompute_sequence_duration(sequence)
                if (project['settings'].get('pixel_pipeline') or {}).get('engine')=='float32-native-v1':
                    project['settings']['pixel_pipeline']['sources'][args.asset_id]=dict(source_signal=dict(primaries='bt709',transfer='srgb'),scan='progressive',display_geometry='square-unrotated')
                validation=validate_project(root,project)
                if not validation['ok']:raise AppError('INTERPOLATION_PROJECT_INVALID','补帧资产入库后工程校验失败，事务回滚',exit_code=2,diagnostics=validation)
                report=dict(protocol=PROTOCOL,operation_id=operation_id,asset=asset,rights=record,clips=clips,generation=result,configuration=plan,snapshot_id=snapshot['snapshot_id'],validation=validation,
                    playback_speed=args.playback_speed,pipeline_timeout_excludes_preflight=True)
                atomic_write_json(report_path,report);project['provenance']['change_log'].append(dict(command='interpolate.generate',operation_id=operation_id,asset_id=args.asset_id,report=str(report_path),at=now_iso()))
                cancel(marker);save_project(root,project);_operation(root,operation_id,dict(command='interpolate.generate',operation_id=operation_id,status='succeeded',report=str(report_path),created_at=now_iso()))
                _progress(args,operation_id,'completed','interpolate.generate',100,'神经补帧、原帧/PCM和原生时钟往返及可编辑入轨已核验')
                return _envelope('interpolate.generate',args,data=report,warnings=warnings,operation_id=operation_id)
        except BaseException:report_path.unlink(missing_ok=True);raise
