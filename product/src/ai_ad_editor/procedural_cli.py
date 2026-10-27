"""Agent-facing editable particles, through ordinary project transactions."""
from __future__ import annotations
import copy
import json
from pathlib import Path
from .errors import AppError
from .procedural_particles import normalize, identity, ParticleSource
from .procedural_presets import catalog, get, source, VERSION


def read_config(path):
    from .utils import read_json_snapshot
    try:
        return read_json_snapshot(Path(path), 1024**2)
    except (OSError, ValueError) as exc:
        raise AppError('PARTICLE_JSON', '粒子配置文件必须为不超过1MiB的可读取UTF-8 JSON',
            exit_code=2, path=str(path), cause=str(exc)) from exc


def add_parser(subs, common):
    parser=subs.add_parser('vfx',help='离线可编辑程序化粒子；真实原生浮点/GPU合成')
    actions=parser.add_subparsers(dest='action',required=True)
    common(actions.add_parser('list',help='列出六种有明确参数和限制的原创建效配方'))
    common(actions.add_parser('animation-properties',help='查询发射器动画属性、取值约束与原始源时钟'))
    from .particle_animation import PROPERTIES
    animate=common(actions.add_parser('animate',help='添加/替换/移除发射器源时钟关键帧；不重置片段剪辑'))
    for name in ('project','clip-id'):animate.add_argument('--'+name,required=True)
    animate.add_argument('--sequence-id');animate.add_argument('--track-id')
    animate.add_argument('--emitter-index',type=int,required=True)
    animate.add_argument('--property',choices=sorted(PROPERTIES),required=True)
    edit=animate.add_mutually_exclusive_group(required=True)
    edit.add_argument('--keyframes',dest='points',help='JSON关键帧数组；时间为原始generator tick')
    edit.add_argument('--remove',action='store_true')
    animate.add_argument('--replace',action='store_true',help='显式替换已存在的该发射器属性轨道')
    animate.set_defaults(config=None,preset=None,seed=None)
    inspect=common(actions.add_parser('inspect',help='查看预设的完整数值配方'))
    inspect.add_argument('--name',required=True)
    for action in ('apply','update','show'):
        p=common(actions.add_parser(action,help={'apply':'添加独立粒子源片段','update':'替换参数并保留原片段时间线与自动化','show':'查看可编辑参数及源时钟'}[action]))
        p.add_argument('--project',required=True);p.add_argument('--sequence-id');p.add_argument('--track-id');p.add_argument('--clip-id',required=action!='apply')
        if action=='show': continue
        recipe=p.add_mutually_exclusive_group(required=True)
        recipe.add_argument('--preset',choices=[v['id'] for v in catalog()]);recipe.add_argument('--config',help='完整粒子源JSON；未知字段会拒绝')
        p.add_argument('--seed',type=int)
        if action=='apply':
            p.add_argument('--start-tick',type=int,default=0);p.add_argument('--duration-tick',type=int,required=True)
            p.add_argument('--source-duration-tick',type=int)
            p.add_argument('--enable-native',action='store_true',help='明确切换到BT.709线性合成/sRGB交付；已有视觉媒体须给出信号')
            p.add_argument('--source-signals',help='已有视觉媒体的显式 pixel_pipeline.sources JSON')
    return parser


def command(args):
    # Lazy import avoids making CLI startup depend on this domain's writer.
    from .cli import (_envelope,_find_clip,_recompute_sequence_duration,_operation)
    from .project import load_project,find_sequence,save_project,create_snapshot
    from .validator import validate_project
    from .utils import new_id,now_iso
    if args.action=='list':
        return _envelope('vfx.list',args,data={'catalog_version':VERSION,'presets':catalog(),'count':len(catalog()),'network':False})
    if args.action=='inspect':
        return _envelope('vfx.inspect',args,data={'preset':get(args.name)})
    if args.action=='animation-properties':
        from .particle_animation import PROPERTIES,BIRTH,LIVE,PROTOCOL,INTERPOLATIONS,MAX_POINTS
        from .schema_contract import read_contract
        definitions=read_contract()[1]['$defs']['particleEmitter']['properties']
        return _envelope('vfx.animation-properties',args,data={'protocol':PROTOCOL,
            'clock':'original generator ticks; independent of clip/output retime','max_points':MAX_POINTS,
            'interpolations':list(INTERPOLATIONS),'properties':[{'property':k,
                'scope':'integrated-emission-rate' if k=='rate' else 'at-birth' if k in BIRTH else 'live-source-time',
                'value_schema':definitions[k]} for k in sorted(PROPERTIES)]})
    root,original=load_project(args.project);project=copy.deepcopy(original)
    sequence=find_sequence(project,args.sequence_id);tps=project['settings']['timebase']['ticks_per_second']
    track=clip=None
    if args.action!='apply':
        track,clip=_find_clip(sequence,args.clip_id,args.track_id)
        if not isinstance(clip.get('generator'),dict) or clip['generator'].get('type')!='particles':
            raise AppError('PARTICLE_CLIP','目标片段不是独立粒子源',exit_code=2)
        if args.action=='show':
            config=normalize(clip['generator']);p=ParticleSource(config)
            return _envelope('vfx.show',args,data={'sequence_id':sequence['id'],'track_id':track['id'],
                'clip':clip,'generator':config,'source_sha256':identity(config),'source_frames':p.frames,
                'source_fps':str(p.fps),'source_duration_seconds':str(p.duration)})
        if track.get('locked'):
            raise AppError('PARTICLE_TRACK_LOCKED','目标轨道已锁定',exit_code=2)
    settings=project['settings'];pipeline=settings.get('pixel_pipeline')
    if args.action=='apply':
        if args.source_signals and not args.enable_native:
            raise AppError('PARTICLE_SOURCE_SIGNAL_ARGUMENT','--source-signals 需要 --enable-native',exit_code=2)
        if args.source_duration_tick is not None and (args.source_duration_tick<=0 or args.config):
            raise AppError('PARTICLE_SOURCE_DURATION_ARGUMENT','source-duration-tick 必须为正数且只用于预设；自定义源时长在config中声明',exit_code=2)
    if args.action=='apply' and args.enable_native:
        if pipeline is None:
            from .float_standard_render import ENGINE
            signals=read_config(args.source_signals) if args.source_signals else {}
            if not isinstance(signals,dict):
                raise AppError('PARTICLE_SOURCE_SIGNAL_REQUIRED','source-signals 必须为按资产ID索引的对象',exit_code=2)
            visual={a['id'] for a in project['assets'] if a['kind'] in ('video','image')}
            if visual-set(signals):
                raise AppError('PARTICLE_SOURCE_SIGNAL_REQUIRED','切换原生合成前须通过 --source-signals 明确所有已登记视频/图片信号',exit_code=2)
            pipeline={'engine':ENGINE,'working_signal':{'primaries':'bt709','transfer':'linear'},
                'output_signal':{'primaries':'bt709','transfer':'srgb'},'range_policy':'clip','sources':signals}
            settings['pixel_pipeline']=pipeline
            settings['color'].update(primaries='bt709',transfer='iec61966-2-1',matrix='bt709',range='limited',tone_map='none')
        elif args.source_signals:
            raise AppError('PARTICLE_PIPELINE_EXISTS','已有原生合成配置；请通过普通工程设置接口显式更新信号',exit_code=2)
    if pipeline is None:
        raise AppError('PARTICLE_NATIVE_PIPELINE_REQUIRED','粒子使用原生浮点合成；新工程可使用 --enable-native，已有媒体须显式提供 --source-signals',exit_code=2)
    if args.action=='animate':
        config=copy.deepcopy(clip['generator']);index=args.emitter_index
        if not 0<=index<len(config['emitters']):
            raise AppError('PARTICLE_EMITTER','发射器索引越界；未修改工程',exit_code=2)
        emitter=config['emitters'][index];tracks=emitter.get('keyframes',[])
        existing=next((t for t in tracks if t['property']==args.property),None)
        if args.remove:
            if args.replace or existing is None:
                raise AppError('PARTICLE_ANIMATION_CONFLICT','移除要求既有属性且不能同时replace',exit_code=2)
        elif existing and not args.replace:
            raise AppError('PARTICLE_ANIMATION_CONFLICT','该属性已有发射器关键帧；须显式replace',exit_code=2)
        updated=[t for t in tracks if t['property']!=args.property]
        if not args.remove:updated.append({'property':args.property,'keyframes':read_config(args.points)})
        if updated:emitter['keyframes']=updated
        else:emitter.pop('keyframes',None)
        config=normalize(config)
    elif args.config:
        config=normalize(read_config(args.config))
        if args.seed is not None:
            config['seed']=args.seed;config=normalize(config)
    else:
        from .sequence_canvas import sequence_canvas
        old=clip.get('generator') if clip else None
        config=source(args.preset,canvas=(old['canvas'] if old else {k:sequence_canvas(project,sequence)[k] for k in ('width','height')}),
            fps=old['fps'] if old else settings['timebase']['display_fps'],
            duration_tick=old['duration_tick'] if old else (args.source_duration_tick if args.source_duration_tick is not None else args.duration_tick),
            ticks_per_second=old['ticks_per_second'] if old else tps,
            seed=args.seed if args.seed is not None else (old['seed'] if old else 0))
    if args.action=='apply':
        if args.start_tick<0 or args.duration_tick<=0:
            raise AppError('PARTICLE_RANGE','开始tick必须非负，时长必须为正',exit_code=2)
        if args.track_id:
            track=next((t for t in sequence['tracks'] if t['id']==args.track_id),None)
            if not track or track['kind'] not in ('video','overlay'):
                raise AppError('PARTICLE_TRACK','指定轨道必须为既有video/overlay',exit_code=2)
            if track.get('locked'):
                raise AppError('PARTICLE_TRACK_LOCKED','目标轨道已锁定',exit_code=2)
        else:
            track={'id':new_id('track'),'kind':'overlay','order':max((t.get('order',0) for t in sequence['tracks']),default=-1)+1,'clips':[]}
            sequence['tracks'].append(track)
        clip={'id':args.clip_id or new_id('clip'),'timeline_start_tick':args.start_tick,'duration_tick':args.duration_tick,
            'source_in_tick':0,'source_out_tick':args.duration_tick,'generator':config}
        track['clips'].append(clip);_recompute_sequence_duration(sequence)
    else: clip['generator']=config
    validation=validate_project(root,project,strict_rights=False)
    if not validation['ok']:
        raise AppError('PROJECT_INVALID','粒子操作产生无效工程；未写入',exit_code=2,cause=json.dumps(validation,ensure_ascii=False))
    data={'sequence_id':sequence['id'],'track_id':track['id'],'clip':clip,'source_sha256':identity(config),
        'validation':validation,'render_backend':'native-float32','assets_downloaded':False}
    if args.dry_run:return _envelope('vfx.'+args.action,args,status='planned',data=data)
    snapshot=create_snapshot(root,original,label='before-vfx-'+args.action);oid=new_id('op')
    record={'operation_id':oid,'command':'vfx.'+args.action,'at':now_iso(),'clip_id':clip['id'],
        'sequence_id':sequence['id'],'source_sha256':identity(config),'preset':args.preset,'before_snapshot_id':snapshot['snapshot_id']}
    if args.action=='animate':record.update(emitter_index=args.emitter_index,property=args.property,
        edit='remove' if args.remove else 'replace' if args.replace else 'add')
    project.setdefault('provenance',{}).setdefault('change_log',[]).append(record)
    save_project(root,project);_operation(root,oid,{**record,'status':'succeeded'})
    return _envelope('vfx.'+args.action,args,data={**data,'operation_id':oid,'before_snapshot_id':snapshot['snapshot_id']})
