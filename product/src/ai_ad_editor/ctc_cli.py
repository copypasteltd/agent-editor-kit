"""Transactional CLI application of real, registered local CTC alignment."""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path

from .artifact_locks import artifact_entry, verification_scope, verification_summary
from .captions import cues_to_srt
from .ctc_alignment import SAMPLE_RATE, fail, frame_windows, read_transcript
from .local_ctc import ENGINE, align_registered, prepare_text
from .local_asr import registry_item, verify_adapter
from .media import probe_media
from .policy import resolve_local_path
from .project import asset_map, create_snapshot, find_sequence, find_track, load_project, save_project
from .rights import active_records, add_record, load_ledger, save_ledger
from .utils import ensure_inside, new_id, now_iso, sha256_file
from .validator import validate_project


def command_subtitle_align(args):
    with verification_scope():
        return _locked(args)


def _locked(args):
    from .cli import _envelope, _operation
    root, project = load_project(args.project)
    if not all(math.isfinite(x) for x in (args.window_seconds, args.context_seconds, args.timeout)) or not 0 < args.window_seconds <= 30 or args.context_seconds <= 0 or not 0 < args.timeout <= 86400:
        raise fail('ALIGNMENT_OPTIONS_INVALID', '窗口须为 0–30 秒，context/timeout 必须为有限正数（超时最多一天）')
    if not 0 <= args.timeline_start_tick <= 2**63 - 1:
        raise fail('ALIGNMENT_OPTIONS_INVALID', '时间线偏移须为非负 int64')
    if not args.apply and (args.track_id or args.sequence_id or args.font_asset_id or args.replace_track or args.timeline_start_tick):
        raise fail('ALIGNMENT_OPTIONS_INVALID', '入轨选项需要 --apply')
    cancel_file = resolve_local_path(root, args.cancel_file, field='cancel_file') if args.cancel_file else None
    def checkpoint():
        if cancel_file and cancel_file.exists():
            raise fail('CANCELLED', '对齐任务已取消', exit_code=8)
    checkpoint()
    assets, ledger = asset_map(project), load_ledger(root)
    source_asset = assets.get(args.asset_id)
    if not source_asset or source_asset.get('kind') not in {'audio', 'video'}:
        raise fail('ALIGNMENT_SOURCE_INVALID', '需要已登记的本地音频/视频资产')
    source = resolve_local_path(root, source_asset['uri'], field='asset_id')
    source_digest = artifact_entry(source, 'alignment-source')['sha256']
    source_ref = str(source_asset.get('rights_ref') or source_asset['id'])
    records = {r['asset_id']: r for r in active_records(ledger)}
    if source_digest != source_asset.get('sha256') or records.get(source_ref, {}).get('sha256') != source_digest:
        raise fail('ALIGNMENT_SOURCE_INVALID', '源资产或权利摘要不匹配', exit_code=7)
    adapter = registry_item(project, args.adapter_id)
    if adapter.get('engine') != ENGINE or not verify_adapter(adapter)['ok']:
        raise fail('ALIGNMENT_INTEGRITY_FAILED', '需要完整的已登记 Wav2Vec2 CTC 模型', exit_code=10)
    if records.get(adapter['rights_ref'], {}).get('sha256') != adapter['sha256']:
        raise fail('ALIGNMENT_MODEL_RIGHTS_MISSING', '对齐模型缺少匹配的权利记录', exit_code=7)
    transcript_path = resolve_local_path(root, args.transcript, field='transcript')
    transcript_digest = artifact_entry(transcript_path, 'alignment-transcript')['sha256']
    prepared = prepare_text(read_transcript(transcript_path), adapter, case=args.case, granularity=args.granularity,
                            boundary_mode=args.boundary_mode)
    frame_windows(1, prepared['stride_samples'], prepared['receptive_samples'],
        window_samples=round(args.window_seconds * SAMPLE_RATE), context_samples=round(args.context_seconds * SAMPLE_RATE))
    probe = probe_media(source)
    duration = float(probe.get('duration_seconds') or 0)
    if not probe.get('audio', {}).get('codec') or not math.isfinite(duration) or not 0 < duration <= 1800:
        raise fail('ALIGNMENT_SOURCE_INVALID', '源必须包含有效音频，且不超过 1800 秒')
    output = resolve_local_path(root, args.output, field='output')
    srt = output.with_suffix('.srt')
    copied_text = output.with_name(output.stem + '.transcript' + transcript_path.suffix.lower())
    paths = [output, srt, copied_text]
    if output.suffix.lower() != '.json' or len(set(paths)) != 3:
        raise fail('ALIGNMENT_OUTPUT_INVALID', '输出须为项目 assets 内新的 JSON')
    for path in paths:
        ensure_inside(root / 'assets', path)
        if path.exists():
            raise fail('ALIGNMENT_OUTPUT_EXISTS', '输出已存在，禁止覆盖: ' + str(path))
    sequence = find_sequence(project, args.sequence_id) if args.apply else None
    track = find_track(sequence, args.track_id, None) if args.apply and args.track_id else None
    if args.apply and (track is None or track.get('kind') != 'subtitle' or track.get('locked')):
        raise fail('ALIGNMENT_TRACK_INVALID', '入轨需要未锁定的 subtitle 目标轨道')
    if args.font_asset_id:
        font = assets.get(args.font_asset_id)
        if not font or font.get('kind') != 'font':
            raise fail('ALIGNMENT_FONT_INVALID', '字体必须为已登记字体资产')
        if artifact_entry(resolve_local_path(root, font['uri'], field='font'), 'alignment-font')['sha256'] != font['sha256']:
            raise fail('ALIGNMENT_FONT_INVALID', '登记字体内容已变化', exit_code=10)
    if args.apply:
        for segment in prepared['segments']:
            count = len(segment['tokens']) if args.granularity == 'character' else len(segment['text'].split())
            if count > 128:
                raise fail('ALIGNMENT_DISPLAY_BUDGET_EXCEEDED', '每个高亮字幕段最多 128 个范围；请使用明确的 SRT 段落')
    data = {'output': str(output), 'srt': str(srt), 'transcript_copy': str(copied_text),
            'source_sha256': source_digest, 'transcript_sha256': transcript_digest,
            'adapter_id': args.adapter_id, 'model_sha256': adapter['sha256'], 'prepared': prepared,
            'applied': bool(args.apply), 'network': 'disabled'}
    if args.dry_run:
        return _envelope('subtitle.align', args, status='planned', data=data,
                         warnings=[{'code': 'ALIGNMENT_REVIEW_REQUIRED', 'message': '尚未推理；真实对齐仍须核验'}])
    result = align_registered(root, source, adapter=adapter, prepared=prepared,
        window_seconds=args.window_seconds, context_seconds=args.context_seconds, timeout=args.timeout, cancel_file=cancel_file)
    tps = int(project['settings']['timebase']['ticks_per_second'])
    def tick(sample):
        return (sample * tps + SAMPLE_RATE // 2) // SAMPLE_RATE
    cues = []
    for segment in result['segments']:
        start, end = tick(segment['units'][0]['start_sample']), tick(segment['units'][-1]['end_sample'])
        if end <= start or end + args.timeline_start_tick > 2**63 - 1:
            raise fail('ALIGNMENT_DISPLAY_CLOCK_INVALID', '量化后的字幕时间范围无效')
        cue = {'text': segment['text'], 'start_tick': start + args.timeline_start_tick,
               'end_tick': end + args.timeline_start_tick, 'source_start_char': segment['start_char'],
               'word_timing': [{'text': unit['text'], 'start_char': unit['start_char'] - segment['start_char'],
                   'start': (tick(unit['start_sample']) - start) / tps,
                   'end': (tick(unit['end_sample']) - start) / tps} for unit in segment['units']]}
        cues.append(cue)
    if track and not args.replace_track:
        for cue in cues:
            if any(max(cue['start_tick'], c['timeline_start_tick']) < min(cue['end_tick'], c['timeline_start_tick'] + c['duration_tick']) for c in track.get('clips', [])):
                raise fail('ALIGNMENT_TRACK_OVERLAP', '对齐字幕与既有片段重叠，需要显式 --replace-track')
    checkpoint()
    if artifact_entry(transcript_path, 'alignment-transcript')['sha256'] != transcript_digest:
        raise fail('ALIGNMENT_TRANSCRIPT_CHANGED', '推理过程中逐字稿已变化', exit_code=10)
    operation_id = new_id('op')
    result.update({'operation_id': operation_id, 'transcript_sha256': transcript_digest,
                   'transcript_format': prepared['format'], 'timeline_start_tick': args.timeline_start_tick,
                   'ticks_per_second': tps, 'display_cues': cues})
    created = []
    def write_new(path: Path, value: bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            created.append(path)
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    try:
        snapshot = create_snapshot(root, project, label='before-subtitle-align')
        write_new(copied_text, transcript_path.read_bytes())
        write_new(output, (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))
        srt_cues = [{'start': c['start_tick'] / tps, 'end': c['end_tick'] / tps, 'text': c['text']} for c in cues]
        write_new(srt, cues_to_srt(srt_cues).encode('utf-8'))
        registered = []
        for path, kind in ((copied_text, 'generated'), (output, 'generated'), (srt, 'subtitle')):
            aid = new_id('aligned_subtitle')
            digest = 'sha256:' + sha256_file(path)
            parents = [] if path == copied_text else ([source_ref, adapter['rights_ref'], registered[0]['rights_ref']] if path == output else [registered[1]['rights_ref']])
            asset = {'id': aid, 'kind': kind, 'uri': path.relative_to(root).as_posix(), 'sha256': digest,
                'rights_ref': aid, 'probe': {'duration_tick': max(c['end_tick'] for c in cues)},
                'source': {'source_url': f'local://{path}', 'original_name': path.name, 'retrieved_at': now_iso()}}
            record = {'asset_id': aid, 'kind': kind, 'sha256': digest, 'source_url': f'local://{path}',
                'source_version': 'agent-ctc-alignment-v1', 'retrieved_at': now_iso(), 'creator': 'unknown',
                'license_spdx': 'LicenseRef-UNVERIFIED', 'license_url': '', 'attribution': '',
                'permitted_uses': ['internal'], 'permitted_channels': [], 'restrictions': [],
                'derived_from': parents, 'evidence': f'local://{output}', 'verification_status': 'unverified',
                'verified_by': '', 'takedown_status': 'clear', 'notes': 'Forced alignment is not text correctness or rights clearance'}
            project.setdefault('assets', []).append(asset)
            add_record(ledger, record)
            registered.append(asset)
        generated = []
        if track:
            style = {'fontsize': 52, 'fontcolor': 'white', 'borderw': 3, 'bordercolor': 'black',
                     'x': '(w-text_w)/2', 'y': 'h-text_h-40'}
            if args.font_asset_id:
                style['font_asset_id'] = args.font_asset_id
            for cue in cues:
                duration_tick = cue['end_tick'] - cue['start_tick']
                generated.append({'id': new_id('aligned_piece'), 'timeline_start_tick': cue['start_tick'],
                    'duration_tick': duration_tick, 'source_in_tick': 0, 'source_out_tick': duration_tick,
                    'generator': {'type': 'text'}, 'subtitle': {'text': cue['text'], 'style': copy.deepcopy(style),
                        'word_timing': copy.deepcopy(cue['word_timing'])},
                    'rights_dependencies': [{'rights_ref': registered[-1]['rights_ref'], 'sha256': registered[-1]['sha256']}],
                    'extensions': {'ctc_alignment': {'asset_id': registered[1]['id'], 'source_start_char': cue['source_start_char']}}})
            if args.replace_track:
                track['clips'] = []
            track.setdefault('clips', []).extend(generated)
            sequence['duration_tick'] = max(int(sequence.get('duration_tick', 1)), max(c['end_tick'] for c in cues))
        validation = validate_project(root, project, strict_rights=False, rights_ledger=ledger)
        if not validation['ok']:
            raise fail('ALIGNMENT_APPLY_INVALID', '对齐字幕应用失败: ' + json.dumps(validation, ensure_ascii=False), exit_code=2)
        checkpoint()
        change = {'operation_id': operation_id, 'command': 'subtitle.align', 'created_at': now_iso(),
                  'report': output.relative_to(root).as_posix(), 'source_sha256': source_digest,
                  'transcript_sha256': transcript_digest, 'before_snapshot_id': snapshot['snapshot_id']}
        project.setdefault('provenance', {}).setdefault('change_log', []).append(change)
        save_ledger(root, ledger)
        save_project(root, project)
        _operation(root, operation_id, {**change, 'status': 'succeeded'})
        data.update({'result': result, 'registered_assets': registered, 'generated_clips': generated,
                     'validation': validation, 'before_snapshot': snapshot, 'verification': verification_summary()})
        return _envelope('subtitle.align', args, data=data, operation_id=operation_id,
                         warnings=[{'code': 'ALIGNMENT_REVIEW_REQUIRED', 'message': 'CTC 后验不是校准准确率；应核验逐字稿、字边界及自然语音效果'}])
    except BaseException as exc:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        if isinstance(exc, OSError):
            raise fail('ALIGNMENT_IO_FAILED', '字幕文件写入失败，项目事务与本轮新输出已回滚: ' + str(exc), exit_code=9) from exc
        raise
