"""Explicit four-source separation and editable four-track application."""
from __future__ import annotations

import copy
import math
from pathlib import Path

from . import stem_separation as native
from .artifact_locks import artifact_entry, verification_scope, verification_summary
from .errors import AppError, argument_error
from .model_registry import adapter_for, load_model_registry
from .project import asset_map, create_snapshot, find_sequence, load_project, save_project
from .rights import active_records, add_record, load_ledger, save_ledger
from .utils import assert_id, atomic_write_json, ensure_inside, new_id, now_iso, sha256_file
from .validator import validate_project


def add_parser(actions, leaf):
    p = leaf(actions.add_parser('separate-stems', help='离线 HDemucs 独立鼓/贝斯/其他/人声四轨；可创建四条可编辑音轨'))
    p.add_argument('--project', required=True)
    p.add_argument('--asset-id', required=True, help='已有本地音频或视频资产')
    p.add_argument('--adapter-id', required=True, help='torchaudio-hdemucs-four-stem-local-v1 适配器')
    p.add_argument('--prefix', help='派生资产/音轨 ID 前缀；已有 ID 和文件不覆盖')
    p.add_argument('--sample-rate', type=int, default=44100)
    p.add_argument('--device', choices=('auto','cpu','cuda'), help='默认沿用登记设备；auto 优先 GPU，仅预检不足时回退 CPU')
    p.add_argument('--device-index', type=int, default=0)
    p.add_argument('--timeout-seconds', type=float, default=600.)
    p.add_argument('--cancel-file')
    p.add_argument('--sequence-id')
    p.add_argument('--timeline-start-seconds', type=float, default=0.)
    p.add_argument('--apply', action='store_true', help='新建四条独立音轨，原轨道和原音保留')


def command(args, envelope):
    from .audio_separation import _validate_sample_rate
    from .cli import _operation, _recompute_sequence_duration
    with verification_scope():
        root, project = load_project(args.project)
        deadline, marker = native.execution(root, timeout=args.timeout_seconds, cancel_file=args.cancel_file,
                                             device=args.device, device_index=args.device_index)
        if not math.isfinite(args.timeline_start_seconds) or args.timeline_start_seconds < 0:
            raise argument_error('timeline-start-seconds 须为有限非负数', 'timeline_start_seconds')
        rate = _validate_sample_rate(args.sample_rate)
        adapter = adapter_for(load_model_registry(root), args.adapter_id)
        if not adapter or adapter.get('engine') != native.ENGINE:
            raise AppError('FOUR_STEM_ADAPTER_REQUIRED', '四轨命令需要显式登记的四轨 HDemucs 适配器', exit_code=10)
        if not native.verify_adapter(adapter)['ok']:
            raise AppError('MODEL_ADAPTER_HASH_INVALID', '四轨模型登记完整性失败', exit_code=10)
        source_asset = asset_map(project).get(args.asset_id)
        if not source_asset:
            raise argument_error('找不到源资产', 'asset_id')
        source = native.local_file(source_asset['uri'], root)
        if artifact_entry(source,'source')['sha256'] != source_asset.get('sha256'):
            raise AppError('SEPARATION_SOURCE_HASH_MISMATCH', '四轨源素材与登记摘要不符', exit_code=10)
        ledger = load_ledger(root)
        records = {record['asset_id']:record for record in active_records(ledger)}
        parent_ref = source_asset.get('rights_ref') or args.asset_id
        parent = records.get(parent_ref)
        if not parent or adapter['rights_ref'] not in records:
            raise AppError('RIGHTS_RECORD_MISSING', '源素材或四轨模型权利记录缺失', exit_code=7)
        prefix = args.prefix or new_id('stems')
        assert_id(prefix, 'prefix')
        if len(prefix) > 80: raise argument_error('prefix 最长 80 字符', 'prefix')
        ids = {role:prefix+'_'+role for role in native.ROLES}
        tracks = {role:'track_'+ident for role,ident in ids.items()}
        destinations = {role:ensure_inside(root, root/'assets/derived'/(ident+'.wav')) for role,ident in ids.items()}
        for ident in (*ids.values(), *tracks.values()): assert_id(ident,'derived_id')
        existing_tracks = {track['id'] for sequence in project['sequences'] for track in sequence['tracks']}
        if (set(ids.values()) & set(asset_map(project)) or (args.apply and set(tracks.values()) & existing_tracks)
                or any(path.exists() for path in destinations.values())):
            raise argument_error('四轨派生 ID、音轨或输出已存在；请换 prefix', 'prefix')
        sequence = find_sequence(project,args.sequence_id)
        planned = dict(engine=native.ENGINE,source_asset_id=args.asset_id,adapter=adapter,
            outputs={role:dict(asset_id=ids[role],output=str(destinations[role]),track_id=tracks[role] if args.apply else None)
                     for role in native.ROLES},device=args.device or adapter['settings']['device'],device_index=args.device_index,
            apply=args.apply,network='disabled',mixture_projection='none',max_audio_seconds=native.MAX_SECONDS)
        if args.dry_run:
            planned['verification_scope'] = verification_summary()
            return envelope('audio.separate-stems',args,status='planned',data=planned)
        native.remaining(deadline,marker)
        snapshot = create_snapshot(root,copy.deepcopy(project),label='before-audio-separate-stems')
        operation_id = new_id('op'); separation = None; report_path = None
        try:
            separation = native.separate(root,source,destinations,adapter=adapter,sample_rate=rate,device=args.device,
                device_index=args.device_index,timeout=native.remaining(deadline,marker),cancel_file=marker)
            assets = {}; rights = {}; generated = {}
            tps = int(project['settings']['timebase']['ticks_per_second'])
            start_tick = round(args.timeline_start_seconds*tps)
            order = max((track['order'] for track in sequence['tracks']),default=-1)+1
            for offset, role in enumerate(native.ROLES):
                details = separation['stems'][role]; destination = destinations[role]; ident = ids[role]
                asset = dict(id=ident,kind='audio',uri=destination.relative_to(root).as_posix(),sha256=details['sha256'],
                    probe=details['probe'],rights_ref=ident,source=dict(source_url='local://'+str(destination),
                    retrieved_at=now_iso(),original_name=destination.name,derived_from=[args.asset_id]))
                record = copy.deepcopy(parent)
                record.update(asset_id=ident,kind='audio',sha256=details['sha256'],source_url='local://'+str(destination),
                    source_version=native.ENGINE,retrieved_at=now_iso(),derived_from=[parent_ref,adapter['rights_ref']],
                    notes='Independent HDemucs '+role+' estimate; inherits source and model dependencies; raw sum is not projected')
                assets[role] = asset; rights[role] = record
                project.setdefault('assets',[]).append(asset); add_record(ledger,record)
                if args.apply:
                    duration = max(1,round(details['samples']*tps/rate))
                    clip = dict(id=new_id('clip_'+role),asset_id=ident,timeline_start_tick=start_tick,duration_tick=duration,
                                source_in_tick=0,source_out_tick=duration)
                    sequence['tracks'].append(dict(id=tracks[role],kind='audio',order=order+offset,muted=False,locked=False,clips=[clip]))
                    generated[role] = dict(track_id=tracks[role],clip=clip)
            if args.apply: _recompute_sequence_duration(sequence)
            save_ledger(root,ledger)
            validation = validate_project(root,project,strict_rights=False)
            if not validation['ok']:
                raise AppError('FOUR_STEM_APPLY_INVALID', '四轨写入后工程校验失败', exit_code=2, cause=str(validation))
            native.remaining(deadline,marker)
            report_path = root/'validation'/('audio_stems_'+operation_id+'.json')
            report = dict(report_version='1.0.0',created_at=now_iso(),operation_id=operation_id,
                snapshot_id=snapshot['snapshot_id'],source_asset_id=args.asset_id,assets=assets,rights=rights,
                separation=separation,generated_tracks=generated,validation=validation)
            atomic_write_json(report_path,report)
            project.setdefault('provenance',{}).setdefault('change_log',[]).append(dict(operation_id=operation_id,
                command='audio.separate-stems',asset_ids=list(ids.values()),source_asset_id=args.asset_id,
                snapshot_id=snapshot['snapshot_id'],report=str(report_path),at=now_iso()))
            save_project(root,project)
            _operation(root,operation_id,dict(operation_id=operation_id,command='audio.separate-stems',status='succeeded',
                asset_ids=list(ids.values()),snapshot_id=snapshot['snapshot_id'],report=str(report_path),created_at=now_iso()))
            return envelope('audio.separate-stems',args,operation_id=operation_id,data=dict(assets=assets,rights=rights,
                snapshot=snapshot,report=str(report_path),separation=separation,generated_tracks=generated,validation=validation,
                verification_scope=verification_summary()),warnings=separation['warnings'])
        except BaseException:
            # Transaction-scoped workspaces remove only identity/hash-matching
            # unreferenced outputs after metadata rollback, including hard-crash recovery.
            if report_path: report_path.unlink(missing_ok=True)
            raise
