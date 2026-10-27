"""Project-aware registration, planning, generation and editable lip-sync reruns."""
import copy,math
from pathlib import Path
from . import lipsync_plan as planning
from .local_lipsync import ENGINE,PROTOCOL,prepare_adapter,verify_adapter,error
from .model_registry import load_visual_model_registry,save_visual_model_registry,visual_adapter_for
from .project import load_project,asset_map,find_sequence,find_track,create_snapshot,save_project
from .rights import load_ledger,save_ledger,active_records,add_record
from .utils import assert_id,atomic_write_json,load_json,now_iso,new_id
from .policy import resolve_local_path
from .artifact_locks import verification_scope
from .errors import AppError,argument_error


def add_parser(subs,leaf):
    domain=subs.add_parser('lipsync',help='原生CUDA音频驱动口型同步；显式图片/视频与人脸框')
    actions=domain.add_subparsers(dest='action',required=True)
    adapter=actions.add_parser('adapter');registrations=adapter.add_subparsers(dest='adapter_action',required=True)
    for action in ('register','list','inspect'):
        p=leaf(registrations.add_parser(action));p.add_argument('--project',required=True)
        if action!='list':p.add_argument('--adapter-id',required=True)
        if action=='register':
            p.add_argument('--model-path',required=True);p.add_argument('--executable',required=True);p.add_argument('--evidence',required=True)
            p.add_argument('--device',choices=['cuda'],default='cuda');p.add_argument('--threads',type=int,default=4);p.add_argument('--batch-size',type=int,default=2)
            p.add_argument('--license-spdx',default='LicenseRef-UNVERIFIED');p.add_argument('--license-url',default='')
            p.add_argument('--creator',default='unknown');p.add_argument('--permitted-use',action='append',default=['internal'])
            p.add_argument('--verification-status',choices=['unverified','verified','restricted'],default='unverified')
    p=leaf(actions.add_parser('generate'));p.add_argument('--project',required=True);p.add_argument('--adapter-id',required=True)
    p.add_argument('--asset-id',required=True);p.add_argument('--source-asset-id');p.add_argument('--audio-asset-id')
    p.add_argument('--recipe-asset-id',help='复用既有口型配方，参数可显式覆盖；新输出须使用新asset-id')
    box=p.add_mutually_exclusive_group();box.add_argument('--face-box',nargs=4,type=float,metavar=('X0','Y0','X1','Y1'));box.add_argument('--boxes-file')
    for name in ('audio-start-seconds','audio-end-seconds','source-start-seconds','source-end-seconds','mask-top','feather-pixels'):
        p.add_argument('--'+name,type=float)
    p.add_argument('--source-mode',choices=['once','hold','loop']);p.add_argument('--seed',type=int)
    p.add_argument('--storage-budget-mib',type=int,default=2048);p.add_argument('--timeout-seconds',type=float,default=3600);p.add_argument('--cancel-file')
    p.add_argument('--apply',action='store_true');p.add_argument('--sequence-id');p.add_argument('--video-track-id');p.add_argument('--audio-track-id')
    p.add_argument('--timeline-start-seconds',type=float,default=0)


def adapter_command(args):
    from .cli import _envelope,_operation
    with verification_scope():
        root,project=load_project(args.project);registry=load_visual_model_registry(root)
        if args.adapter_action=='list':return _envelope('lipsync.adapter.list',args,data=dict(adapters=[a for a in registry['adapters'] if a.get('engine')==ENGINE]))
        existing=visual_adapter_for(registry,args.adapter_id)
        if args.adapter_action=='inspect':
            if not existing or existing.get('engine')!=ENGINE:raise error('ADAPTER_MISSING','找不到指定口型适配器')
            return _envelope('lipsync.adapter.inspect',args,data=dict(adapter=existing,verification=verify_adapter(existing)))
        if existing:raise error('ADAPTER_EXISTS','适配器ID已存在，请选新ID')
        adapter,rights=prepare_adapter(root,adapter_id=args.adapter_id,model_path=args.model_path,executable=args.executable,evidence=args.evidence,
            creator=args.creator,license_spdx=args.license_spdx,license_url=args.license_url,permitted_uses=args.permitted_use,
            verification_status=args.verification_status,options=dict(device=args.device,threads=args.threads,batch_size=args.batch_size))
        data=dict(adapter=adapter,rights=rights)
        if args.dry_run:return _envelope('lipsync.adapter.register',args,status='planned',data=data)
        ledger=load_ledger(root);snapshot=create_snapshot(root,copy.deepcopy(project),label='before-lipsync-register');operation_id=new_id('op')
        registry['adapters'].append(adapter);add_record(ledger,rights)
        project['provenance'].setdefault('local_adapters',[]).append(dict(adapter_id=args.adapter_id,kind=adapter['kind'],engine=ENGINE,model_sha256=adapter['model_sha256'],registered_at=adapter['registered_at']))
        project['provenance']['change_log'].append(dict(command='lipsync.adapter.register',operation_id=operation_id,adapter_id=args.adapter_id,at=now_iso()))
        save_visual_model_registry(root,registry);save_ledger(root,ledger);save_project(root,project)
        _operation(root,operation_id,dict(command='lipsync.adapter.register',status='succeeded',snapshot_id=snapshot['snapshot_id'],created_at=now_iso()))
        return _envelope('lipsync.adapter.register',args,data=data,operation_id=operation_id)


def generate_command(args):
    from .cli import _envelope,_operation,_progress,_recompute_sequence_duration
    from .job_workspaces import managed_workspace
    from .validator import validate_project
    from .native_audio_clock import cancel
    with verification_scope():
        root,project=load_project(args.project);assets=asset_map(project);assert_id(args.asset_id,'asset-id')
        if not math.isfinite(args.timeout_seconds) or not 0<args.timeout_seconds<=604800 or not math.isfinite(args.timeline_start_seconds) or args.timeline_start_seconds<0:
            raise argument_error('须指定有限正超时与非负时间线起点')
        old=None
        if args.recipe_asset_id:
            parent=assets.get(args.recipe_asset_id)
            if not parent or not (old:=parent.get('source',{}).get('lipsync')):raise error('RECIPE_MISSING','指定资产没有可复用口型配方')
            planning.validate_recipe(old,asset=parent,assets=assets)
        source_id=args.source_asset_id or (old['source_asset_id'] if old else None);audio_id=args.audio_asset_id or (old['audio_asset_id'] if old else None)
        source=planning.reference(root,assets.get(source_id),'source');audio=planning.reference(root,assets.get(audio_id),'audio')
        adapter=visual_adapter_for(load_visual_model_registry(root),args.adapter_id)
        if not adapter or adapter.get('engine')!=ENGINE or not verify_adapter(adapter)['ok']:raise error('ADAPTER_UNAVAILABLE','要求显式登记且字节匹配的MuseTalk CUDA适配器')
        face_boxes=load_json(resolve_local_path(root,args.boxes_file,field='boxes-file')) if args.boxes_file else (
            dict(clock='output-frame-25fps',keys=[dict(frame=0,box=args.face_box)]) if args.face_box else copy.deepcopy(old['boxes']) if old else None)
        selected={}
        for name,default in dict(source_mode='once',source_start_seconds=0,source_end_seconds=None,audio_start_seconds=0,audio_end_seconds=None,seed=0,mask_top=.45,feather_pixels=3).items():
            supplied=getattr(args,name)
            if supplied is not None:selected[name]=supplied
            elif old and name in old['options']:selected[name]=old['options'][name]
            elif old and name.startswith('source_') and source_id==old['source_asset_id']:
                selected[name]=old['range'][{'source_mode':'source_mode','source_start_seconds':'start_seconds','source_end_seconds':'end_seconds'}[name]]
            elif old and name.startswith('audio_') and audio_id==old['audio_asset_id']:
                selected[name]=old['audio']['start_sample' if name=='audio_start_seconds' else 'end_sample']/old['audio']['sample_rate']
            else:selected[name]=default
        if selected['source_mode']=='loop' and args.source_end_seconds is None:selected['source_end_seconds']=None
        plan=planning.configuration(source,audio,face_boxes=face_boxes,settings=adapter['settings'],storage_budget_mib=args.storage_budget_mib,**selected)
        ledger=load_ledger(root);rights={r['asset_id']:r for r in active_records(ledger)}
        if args.asset_id in assets or args.asset_id in rights:raise error('OUTPUT_EXISTS','新资产ID已存在，原内容保留')
        dependencies=[]
        for ident,digest in [(adapter['rights_ref'],adapter['sha256']),*[(assets[i].get('rights_ref') or i,assets[i]['sha256']) for i in (source_id,audio_id)]]:
            if ident not in rights or rights[ident]['sha256']!=digest:raise error('RIGHTS_MISSING','模型或输入缺少摘要匹配的权利记录')
            if ident not in dependencies:dependencies.append(ident)
        if args.apply!=bool(args.video_track_id and args.audio_track_id) or not args.apply and (args.video_track_id or args.audio_track_id):
            raise argument_error('--apply须同时指定video-track-id与audio-track-id')
        tps=project['settings']['timebase']['ticks_per_second'];start=round(args.timeline_start_seconds*tps);duration=round(plan['video']['duration_seconds']*tps)
        sequence=find_sequence(project,args.sequence_id);tracks=[]
        if args.apply:
            for ident,kind in [(args.video_track_id,'video'),(args.audio_track_id,'audio')]:
                track=find_track(sequence,ident)
                if track.get('locked') or track['kind'] not in ({'video','overlay'} if kind=='video' else {'audio'}):raise argument_error('须使用未锁定且类型匹配的画面/音频轨道')
                if track.get('overlap_policy','reject')!='allow' and any(max(start,c['timeline_start_tick'])<min(start+duration,c['timeline_start_tick']+c['duration_tick']) for c in track['clips']):raise argument_error('入轨区间与现有片段重叠')
                tracks.append(track)
        output=root/'assets/derived'/(args.asset_id+'.mov')
        if output.exists():raise error('OUTPUT_EXISTS','输出路径已存在，原内容保留')
        marker=resolve_local_path(root,args.cancel_file,field='cancel-file') if args.cancel_file else None
        warnings=[dict(code='LIPSYNC_REVIEW_REQUIRED',message='实际神经口型输出需逐帧和听音复核；256脸部模型保留源运镜，无法生成完整身体/表演。源与声音的授权和生成内容权利需分别确认。')]
        if args.dry_run:return _envelope('lipsync.generate',args,status='planned',data=dict(configuration=plan,source=source,audio=audio,rights_dependencies=dependencies,model_inference_executed=False),warnings=warnings)
        cancel(marker);snapshot=create_snapshot(root,copy.deepcopy(project),label='before-lipsync-generate');operation_id=new_id('op');report_path=root/'validation'/('lipsync_'+operation_id+'.json')
        try:
            with managed_workspace(root,'lip-sync') as job:
                from .lipsync_pipeline import execute
                _progress(args,operation_id,'started','lipsync.generate',0,'执行本地CUDA音频驱动口型同步')
                stage,result=execute(root,job,plan,source,audio,adapter,timeout=args.timeout_seconds,cancel_file=marker,operation_id=operation_id,
                    progress=lambda frame,total:_progress(args,operation_id,'progress','lipsync.generate',round(90*frame/total),f'口型 {frame}/{total} 帧'))
                cancel(marker);job.publish(stage,output)
                asset=dict(id=args.asset_id,kind='video',uri=output.relative_to(root).as_posix(),sha256=result['sha256'],rights_ref=args.asset_id,probe=result['probe'],
                    source=dict(source_url='local://lipsync/'+operation_id,retrieved_at=now_iso(),original_name=output.name,
                        derived_from=list(dict.fromkeys((source_id,audio_id))),lipsync=result['recipe']))
                project['assets'].append(asset)
                record=dict(asset_id=args.asset_id,kind='video',sha256=asset['sha256'],source_url=asset['source']['source_url'],source_version=PROTOCOL,retrieved_at=now_iso(),
                    creator='local-neural-lipsync',license_spdx='LicenseRef-UNVERIFIED',license_url='',attribution='',permitted_uses=['internal'],permitted_channels=[],restrictions=[],
                    derived_from=dependencies,evidence='',verification_status='unverified',verified_by='',takedown_status='clear',notes='Audio-driven synthetic face; source, voice, model and generated rights remain separate.')
                add_record(ledger,record);save_ledger(root,ledger);clips=[]
                link_id=new_id('link_lipsync') if tracks else None
                for track in tracks:
                    clip=dict(id=new_id('clip_lipsync'),asset_id=args.asset_id,timeline_start_tick=start,source_in_tick=0,source_out_tick=duration,duration_tick=duration,link_id=link_id)
                    track['clips'].append(clip);clips.append(dict(track_id=track['id'],clip=clip))
                if tracks:_recompute_sequence_duration(sequence)
                if (project['settings'].get('pixel_pipeline') or {}).get('engine')=='float32-native-v1':
                    project['settings']['pixel_pipeline']['sources'][args.asset_id]=dict(source_signal=dict(primaries='bt709',transfer='srgb'),scan='progressive',display_geometry='square-unrotated')
                validation=validate_project(root,project)
                if not validation['ok']:raise AppError('LIPSYNC_PROJECT_INVALID','口型资产入库后工程校验失败，事务回滚',exit_code=2,diagnostics=validation)
                report=dict(protocol=PROTOCOL,operation_id=operation_id,asset=asset,rights=record,clips=clips,generation=result,configuration=plan,snapshot_id=snapshot['snapshot_id'],validation=validation)
                atomic_write_json(report_path,report);project['provenance']['change_log'].append(dict(command='lipsync.generate',operation_id=operation_id,asset_id=args.asset_id,report=str(report_path),at=now_iso()))
                cancel(marker);save_project(root,project);_operation(root,operation_id,dict(command='lipsync.generate',operation_id=operation_id,status='succeeded',report=str(report_path),created_at=now_iso()))
                _progress(args,operation_id,'completed','lipsync.generate',100,'神经口型、完整RGBA/PCM往返与可编辑工程已核验')
                return _envelope('lipsync.generate',args,data=report,warnings=warnings,operation_id=operation_id)
        except BaseException:
            report_path.unlink(missing_ok=True);raise
