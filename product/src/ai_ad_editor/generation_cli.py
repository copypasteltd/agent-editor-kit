"""Project transaction integration for native local video generation."""
from __future__ import annotations

import copy
from contextlib import ExitStack
import math
from pathlib import Path

from . import video_generation as generation
from .artifact_locks import verification_scope
from .errors import AppError, argument_error
from .job_workspaces import managed_workspace
from .local_vace import VACE_ENGINE
from .model_registry import load_visual_model_registry, visual_adapter_for
from .policy import resolve_local_path
from .project import load_project, asset_map, find_sequence, find_track, create_snapshot, save_project
from .rights import active_records, load_ledger, add_record, save_ledger
from .utils import assert_id, atomic_write_json, now_iso, new_id
from .validator import validate_project


def add_parser(subs, leaf):
    p = leaf(subs.add_parser('generate', help='本地GPU文生/图生/首尾帧视频，登记资产并可编辑入轨'))
    p.add_argument('--project', required=True); p.add_argument('--adapter-id', required=True)
    p.add_argument('--asset-id', required=True, help='新生成视频资产ID')
    p.add_argument('--mode', choices=tuple(generation.MODES), default='text-to-video')
    p.add_argument('--first-asset-id'); p.add_argument('--last-asset-id')
    p.add_argument('--width', type=int, default=512); p.add_argument('--height', type=int, default=288)
    p.add_argument('--frames', type=int, default=81); p.add_argument('--fps', default='16')
    p.add_argument('--image-fit', choices=tuple(sorted(generation.FITS)), default='contain')
    p.add_argument('--prompt', required=True); p.add_argument('--negative-prompt', default='')
    p.add_argument('--seed', type=int, default=0); p.add_argument('--inference-steps', type=int, default=30)
    p.add_argument('--guidance-scale', type=float, default=5); p.add_argument('--conditioning-scale', type=float, default=1)
    p.add_argument('--flow-shift', type=float, default=3); p.add_argument('--prompt-max-tokens', type=int, default=512)
    p.add_argument('--window-frames', type=int, default=17); p.add_argument('--window-overlap', type=int, default=4)
    p.add_argument('--temporal-context', choices=['none', 'previous'], default='previous')
    p.add_argument('--storage-budget-mib', type=int, default=2048)
    p.add_argument('--sequence-id'); p.add_argument('--track-id'); p.add_argument('--apply', action='store_true')
    p.add_argument('--timeline-start-seconds', type=float, default=0)
    p.add_argument('--timeout-seconds', type=float, default=3600); p.add_argument('--cancel-file')
    p.add_argument('--model-session', help='复用显式启动的同工程VACE会话UUID；提示词须相同')
    return p


def command(args):
    from .cli import _envelope, _operation, _progress, _recompute_sequence_duration
    with verification_scope(), ExitStack() as contexts:
        root, project = load_project(args.project); assets = asset_map(project); assert_id(args.asset_id, 'asset-id')
        if not math.isfinite(args.timeout_seconds) or not 0 < args.timeout_seconds <= 604800 or not math.isfinite(args.timeline_start_seconds) or args.timeline_start_seconds < 0:
            raise argument_error('生成须有有限的正超时和非负时间线起点', 'timeout-seconds/timeline-start-seconds')
        config = generation.configuration(mode=args.mode, width=args.width, height=args.height, frames=args.frames,
            fps=args.fps, image_fit=args.image_fit, storage_budget_mib=args.storage_budget_mib,
            sampling={k: getattr(args, k) for k in ('prompt', 'negative_prompt', 'seed', 'inference_steps', 'guidance_scale',
                'conditioning_scale', 'flow_shift', 'prompt_max_tokens', 'window_frames', 'window_overlap', 'temporal_context')})
        specified = {name: getattr(args, name + '_asset_id') for name in ('first', 'last') if getattr(args, name + '_asset_id')}
        if set(specified) != set(generation.MODES[args.mode]):
            raise argument_error('生成模式与首/尾图参数不一致', 'mode/first-asset-id/last-asset-id')
        references = {name: generation.image_reference(root, assets.get(identity)) for name, identity in specified.items()}
        # Image-fit admission is part of dry-run too, before any job or snapshot.
        for row in references.values(): generation.prepared_image(row['path'], config)
        adapter = visual_adapter_for(load_visual_model_registry(root), args.adapter_id)
        if not adapter or adapter.get('engine') != VACE_ENGINE:
            raise AppError('VIDEO_GENERATION_ADAPTER_UNAVAILABLE', '生成要求显式登记的本地VACE CUDA适配器', exit_code=10)
        session = None
        if getattr(args, 'model_session', None):
            from .model_session import lease
            session = contexts.enter_context(lease(root, args.model_session, adapter, config['sampling'], timeout=args.timeout_seconds))
        from .local_vace import verify_adapter
        if not verify_adapter(adapter)['ok']:
            raise AppError('MODEL_ADAPTER_HASH_INVALID', '生成模型或运行依赖变化，请重新登记', exit_code=10)
        ledger = load_ledger(root); rights = {r['asset_id']: r for r in active_records(ledger)}
        if args.asset_id in assets or args.asset_id in rights:
            raise argument_error('新资产或权利ID已存在', 'asset-id')
        dependencies = [adapter['rights_ref']]
        for item, expected in [(adapter['rights_ref'], adapter['sha256'])] + [
            (assets[identity].get('rights_ref') or identity, assets[identity]['sha256']) for identity in specified.values()]:
            if item not in rights or rights[item]['sha256'] != expected:
                raise AppError('VIDEO_GENERATION_RIGHTS_MISSING', '模型或首尾图缺少摘要匹配的权利记录', exit_code=7)
            if item not in dependencies: dependencies.append(item)
        if args.apply != bool(args.track_id): raise argument_error('--apply与--track-id须同时指定', 'apply/track-id')
        sequence = find_sequence(project, args.sequence_id); track = None
        tps = project['settings']['timebase']['ticks_per_second']
        start = round(args.timeline_start_seconds * tps); duration = max(1, round(config['duration_seconds'] * tps))
        if args.apply:
            track = find_track(sequence, args.track_id)
            if track.get('locked') or track['kind'] not in {'video', 'overlay'}:
                raise argument_error('目标须为未锁定video/overlay轨道', 'track-id')
            if track.get('overlap_policy', 'reject') != 'allow' and any(max(start, c['timeline_start_tick']) < min(start + duration, c['timeline_start_tick'] + c['duration_tick']) for c in track['clips']):
                raise argument_error('目标区间与已有片段重叠', 'timeline-start-seconds')
        output = root / 'assets/derived' / (args.asset_id + '.mov')
        if output.exists(): raise argument_error('生成输出已存在，保留原文件', 'asset-id')
        marker = resolve_local_path(root, args.cancel_file, field='cancel-file') if args.cancel_file else None
        warnings = [dict(code='VIDEO_GENERATION_REVIEW_REQUIRED', message='完整生成无声音；首尾图按明确适配与黑底SDR保留，内部帧为真实模型输出。提示遵循、动态/身份/衔接和内容权利需复核。')]
        if args.dry_run:
            return _envelope('media.generate', args, status='planned', data=dict(configuration=config, images=references,
                asset_id=args.asset_id, output=str(output), rights_dependencies=dependencies, model_inference_executed=False), warnings=warnings)
        from .native_audio_clock import cancel
        cancel(marker)
        snapshot = create_snapshot(root, copy.deepcopy(project), label='before-media-generate'); operation_id = new_id('op')
        report_path = root / 'validation' / ('generation_' + operation_id + '.json')
        try:
            with managed_workspace(root, 'video-generation') as job:
                _progress(args, operation_id, 'started', 'media.generate', 0, '准备完整生成条件与本地GPU推理')
                stage, result = generation.execute(root, job, config, references, adapter, timeout=args.timeout_seconds,
                    cancel_file=marker, operation_id=operation_id, **({'session': session} if session is not None else {}), progress=lambda frame, total:
                        _progress(args, operation_id, 'progress', 'media.generate', round(90 * frame / total), f'生成 {frame}/{total} 帧'))
                cancel(marker); generated = result['result']; job.publish(stage, output)
                asset = dict(id=args.asset_id, kind='video', uri=output.relative_to(root).as_posix(), sha256=generated['sha256'],
                    rights_ref=args.asset_id, probe=generated['probe'], source=dict(source_url='local://generated-video/' + operation_id,
                        retrieved_at=now_iso(), original_name=output.name, derived_from=list(dict.fromkeys(specified.values())),
                        video_generation=result['recipe']))
                project['assets'].append(asset)
                record = dict(asset_id=args.asset_id, kind='video', sha256=asset['sha256'], source_url=asset['source']['source_url'],
                    source_version=generation.PROTOCOL, retrieved_at=now_iso(), creator='local-model-generation',
                    license_spdx='LicenseRef-UNVERIFIED', license_url='', attribution='', permitted_uses=['internal'], permitted_channels=[],
                    restrictions=[], derived_from=dependencies, evidence='', verification_status='unverified', verified_by='',
                    takedown_status='clear', notes='Generated content rights require review; model and image terms remain dependencies.')
                add_record(ledger, record); save_ledger(root, ledger)
                clip = None
                if track is not None:
                    clip = dict(id=new_id('clip_generated'), asset_id=args.asset_id, timeline_start_tick=start,
                        source_in_tick=0, source_out_tick=duration, duration_tick=duration)
                    track['clips'].append(clip); _recompute_sequence_duration(sequence)
                if (project['settings'].get('pixel_pipeline') or {}).get('engine') == 'float32-native-v1':
                    project['settings']['pixel_pipeline']['sources'][args.asset_id] = dict(
                        source_signal=dict(primaries='bt709', transfer='srgb'), scan='progressive', display_geometry='square-unrotated')
                validation = validate_project(root, project)
                if not validation['ok']: raise AppError('VIDEO_GENERATION_PROJECT_INVALID', '生成入库工程校验失败，事务回滚', exit_code=2, diagnostics=validation)
                report = dict(protocol=generation.PROTOCOL, operation_id=operation_id, asset=asset, rights=record,
                    generated_clip=clip, generation=result, snapshot_id=snapshot['snapshot_id'], validation=validation)
                atomic_write_json(report_path, report)
                project['provenance']['change_log'].append(dict(command='media.generate', operation_id=operation_id,
                    asset_id=args.asset_id, report=str(report_path), at=now_iso()))
                cancel(marker); save_project(root, project)
                _operation(root, operation_id, dict(command='media.generate', operation_id=operation_id, status='succeeded',
                    asset_id=args.asset_id, report=str(report_path), created_at=now_iso()))
                _progress(args, operation_id, 'completed', 'media.generate', 100, '真实生成、RGBA往返和可编辑入轨已核验')
                return _envelope('media.generate', args, data=report, warnings=warnings, operation_id=operation_id)
        except OSError as exc:
            report_path.unlink(missing_ok=True)
            raise AppError('VIDEO_GENERATION_IO_FAILED', '视频生成文件或工程写入失败，事务回滚', exit_code=6, cause=str(exc)) from exc
        except BaseException:
            report_path.unlink(missing_ok=True)
            raise
