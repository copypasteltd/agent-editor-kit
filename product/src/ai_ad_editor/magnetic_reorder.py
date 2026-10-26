"""Gapless, whole-author main-track permutations with explicit attachments.

This project implements the ordering and attachment constraints here. Existing
linked-editor helpers supply lane, subtitle and binding preservation. No GUI
gesture, media process, model or network is involved in planning.
"""
from __future__ import annotations

import copy
from bisect import bisect_left, bisect_right
from collections import defaultdict

from .edit_planner import (_Draft, _content, _error, _identifier, _integer,
                           _plan_changes, project_fingerprint, validate_editing)
from .errors import AppError

ENGINE = 'agent-main-track-reorder-v1'
MAX_CLIPS = 20000
FADES = {None, '', 'fade', 'fade_in', 'fade_out'}


def start(clip):
    return clip['timeline_start_tick']


def end(clip):
    return start(clip) + clip['duration_tick']


def normalize(sequence, request):
    fields = {'action', 'clip_ids', 'before_clip_id', 'options', 'transition_policy', 'sync_span_policy'}
    if not isinstance(request, dict) or set(request) - fields or request.get('action') != 'reorder':
        _error('EDIT_REQUEST_INVALID', 'reorder 只接受 action/clip_ids/before_clip_id/options/transition_policy')
    ids = request.get('clip_ids')
    if not isinstance(ids, list) or not ids:
        _error('EDIT_REQUEST_INVALID', 'reorder clip_ids 必须非空')
    ids = [_identifier(value, 'edit.clip_ids') for value in ids]
    if len(set(ids)) != len(ids):
        _error('EDIT_REQUEST_INVALID', 'reorder clip_ids 不能重复')
    if 'before_clip_id' not in request:
        _error('EDIT_REQUEST_INVALID', '必须显式提供 before_clip_id，null 表示末尾')
    target = request['before_clip_id']
    if target is not None:
        target = _identifier(target, 'edit.before_clip_id')
    raw = request.get('options', {})
    if not isinstance(raw, dict) or set(raw) - {'sync', 'linkage', 'linked'}:
        _error('EDIT_REQUEST_INVALID', 'reorder options 只接受 sync/linkage/linked')
    options = validate_editing(sequence)
    for key, value in raw.items():
        if type(value) is not bool:
            _error('EDIT_REQUEST_INVALID', 'reorder 开关必须为布尔值', 'edit.options.' + key)
        options[key] = value
    policy = request.get('transition_policy', 'preserve')
    if policy not in ('preserve', 'drop_broken'):
        _error('EDIT_REQUEST_INVALID', 'transition_policy 只接受 preserve/drop_broken')
    span_policy = request.get('sync_span_policy', 'split' if options.get('magnetic') else 'reject')
    if not isinstance(span_policy, str) or span_policy not in ('reject', 'split'):
        _error('EDIT_REQUEST_INVALID', 'sync_span_policy 只接受 reject/split')
    return {'action': 'reorder', 'clip_ids': ids, 'before_clip_id': target,
            'options': options, 'transition_policy': policy, 'sync_span_policy': span_policy}


def _transitions(project, sequence, original, policy):
    """Keep exact partner relationships; removal always requires opt-in."""
    from .source_transitions import analyze
    removed, dropped_fields = [], []
    old_tracks = {track['id']: track for track in original['tracks']}
    old_context = {}
    for track in original['tracks']:
        order = sorted(track['clips'], key=lambda c: (start(c), c['id']))
        old_context.update({clip['id']: (order, index) for index, clip in enumerate(order)})
    for track in sequence['tracks']:
        old = sorted(old_tracks.get(track['id'], {}).get('clips', []), key=lambda c: (start(c), c['id']))
        new = sorted(track['clips'], key=lambda c: (start(c), c['id']))
        old_at = {clip['id']: index for index, clip in enumerate(old)}
        for index, clip in enumerate(new):
            if not any(isinstance(clip.get(field), dict) and clip[field].get('type') not in FADES
                       for field in ('transition_in', 'transition_out')):
                continue
            if clip['id'] not in old_at:
                # Relocated clips are resolved against their original track.
                source_order, old_index = old_context[clip['id']]
            else:
                source_order, old_index = old, old_at[clip['id']]
            for field, direction in (('transition_in', -1), ('transition_out', 1)):
                transition = clip.get(field)
                if not isinstance(transition, dict) or transition.get('type') in FADES:
                    continue
                a, b = old_index + direction, index + direction
                old_neighbor = source_order[a] if 0 <= a < len(source_order) else None
                new_neighbor = new[b] if 0 <= b < len(new) else None
                old_clip = source_order[old_index]
                def partner(own, neighbor):
                    return None if neighbor is None else (neighbor['id'], start(neighbor)-start(own))
                if partner(old_clip, old_neighbor) == partner(clip, new_neighbor):
                    continue
                if policy == 'preserve':
                    _error('EDIT_REORDER_TRANSITION_CONFLICT', '重排会改变旧式跨片段转场的邻居或相对时钟: ' + clip['id'])
                if track.get('locked', False):
                    _error('EDIT_TRACK_LOCKED', '不能从锁定片段移除转场: ' + clip['id'])
                clip.pop(field)
                dropped_fields.append({'clip_id': clip['id'], 'field': field,
                                       'old_neighbor_id': old_neighbor['id'] if old_neighbor else None})
    kept = []
    for declaration in sequence.get('source_transitions', []):
        trial = {**sequence, 'source_transitions': [declaration]}
        trial_project = {**project, 'sequences': [trial if s is sequence else s for s in project['sequences']]}
        try:
            analyze(trial_project, trial)
        except AppError as exc:
            if policy == 'preserve':
                _error('EDIT_REORDER_TRANSITION_CONFLICT', '重排无法保留真实源转场 ' + declaration['id'] + ': ' + exc.code)
            removed.append({'id': declaration['id'], 'reason': exc.code})
        else:
            kept.append(declaration)
    if 'source_transitions' in sequence:
        sequence['source_transitions'] = kept
    # Declarations can individually pass yet overlap after a permutation.
    # The complete analysis must also pass, without silently dropping extras.
    analyze(project, sequence)
    return removed, dropped_fields


def build_reorder_plan(project, sequence_id, request):
    candidate = copy.deepcopy(project)
    sequence = next((s for s in candidate['sequences'] if s['id'] == sequence_id), None)
    if sequence is None:
        _error('EDIT_SEQUENCE_NOT_FOUND', '找不到编辑序列: ' + sequence_id)
    original = copy.deepcopy(sequence)
    normalized = normalize(sequence, request)
    options = normalized['options']
    total = sum(len(t['clips']) for t in sequence['tracks'])
    if total > MAX_CLIPS:
        _error('EDIT_REORDER_RESOURCE_LIMIT', '重排最多接受 20000 个片段；未丢弃或缩减输入')
    main_id = options['main_track_id']
    main = next((t for t in sequence['tracks'] if t['id'] == main_id), None)
    if main is None:
        _error('EDIT_MAIN_TRACK_REQUIRED', 'reorder 需要本序列的 video 主轨')
    if main.get('locked', False):
        _error('EDIT_TRACK_LOCKED', '不能重排锁定主轨')
    ordered = sorted(main['clips'], key=lambda c: (start(c), c['id']))
    main_ids = {c['id'] for c in ordered}
    for clip in ordered:
        _integer(start(clip), 'timeline_start_tick', 0)
        _integer(clip['duration_tick'], 'duration_tick', 1)
    if any(end(left) > start(right) for left, right in zip(ordered, ordered[1:])):
        _error('EDIT_REORDER_MAIN_OVERLAP', '主轨已有重叠；请先明确剪口，重排不会自动裁切')
    if any(cid not in main_ids for cid in normalized['clip_ids']):
        _error('EDIT_REORDER_MAIN_SELECTION_REQUIRED', 'clip_ids 必须全部是当前主轨片段')
    target = normalized['before_clip_id']
    if target is not None and target not in main_ids:
        _error('EDIT_REORDER_TARGET_INVALID', '目标必须是主轨片段或 null')
    selected = set(normalized['clip_ids'])
    if options['linked']:
        links = {c.get('link_id') for c in ordered if c['id'] in selected} - {None}
        selected.update(c['id'] for c in ordered if c.get('link_id') in links)
    if target in selected:
        _error('EDIT_REORDER_TARGET_SELECTED', '目标位于关联扩展后的选择中')
    block = [c for c in ordered if c['id'] in selected]
    remaining = [c for c in ordered if c['id'] not in selected]
    insertion = next((i for i, c in enumerate(remaining) if c['id'] == target), len(remaining))
    packed = remaining[:insertion] + block + remaining[insertion:]
    old_starts = {c['id']: start(c) for c in ordered}
    cursor, main_deltas = 0, {}
    for clip in packed:
        main_deltas[clip['id']] = cursor-old_starts[clip['id']]
        cursor += clip['duration_tick']

    splits = []
    if normalized['sync_span_policy'] == 'split':
        from .magnetic_sync import split_sync
        splits = split_sync(candidate, sequence, ordered, main_deltas, options, MAX_CLIPS)
    draft = _Draft(candidate, sequence, normalized, compute_anchors=False)
    proposals = {cid: (delta, 'main-track') for cid, delta in main_deltas.items()}
    groups = defaultdict(list)
    for cid, (_, clip) in draft.before.items():
        if clip.get('link_id') is not None:
            groups[clip['link_id']].append(cid)
    if options['linked']:
        for members in groups.values():
            deltas = {main_deltas[cid] for cid in members if cid in main_deltas}
            if len(deltas) > 1:
                _error('EDIT_REORDER_LINK_CONFLICT', '同一关联组的主轨成员需要不同位移；请先明确解除关联')
            if deltas:
                delta = next(iter(deltas))
                proposals.update({cid: (delta, 'linked') for cid in members if cid not in main_ids})

    starts = [old_starts[c['id']] for c in ordered]
    ends = [old_starts[c['id']]+c['duration_tick'] for c in ordered]
    cuts = sorted(set(starts + ends))
    old_order = [draft.before[c['id']][1] for c in ordered]
    def host(clip):
        index = bisect_right(starts, start(clip))-1
        if index >= 0 and (start(clip) < ends[index] or index == len(ends)-1 and start(clip) >= ends[index]):
            return index
        return None
    def sync_delta(clip, index):
        first, last = bisect_right(ends, start(clip)), bisect_left(starts, end(clip))
        touched = list(range(first, last))
        if not touched:
            return main_deltas[old_order[index]['id']]
        deltas = {main_deltas[old_order[i]['id']] for i in touched}
        covered = sum(min(end(clip), ends[i])-max(start(clip), starts[i]) for i in touched)
        expected = min(end(clip), ends[-1])-start(clip)
        if len(deltas) != 1 or covered != expected:
            _error('EDIT_REORDER_SYNC_SPAN_UNSUPPORTED', '同步片段跨越不同位移或原主轨间隙；请先显式拆分: ' + clip['id'])
        return next(iter(deltas))
    for cid, (track, clip) in draft.before.items():
        if cid in proposals or track.get('locked', False):
            continue
        index = host(clip)
        if index is None:
            continue
        if options['sync']:
            if track.get('sync_lock', True):
                proposals[cid] = (sync_delta(clip, index), 'sync-host')
        elif options['linkage']:
            crossed = bisect_left(cuts, end(clip))-bisect_right(cuts, start(clip))
            if crossed <= 1:
                proposals[cid] = (main_deltas[old_order[index]['id']], 'rider-host')
    if options['linked']:
        for members in groups.values():
            if any(cid in main_ids for cid in members):
                continue
            deltas = {proposals[cid][0] for cid in members if cid in proposals}
            if len(deltas) > 1:
                _error('EDIT_REORDER_LINK_CONFLICT', '副轨关联组的附着宿主需要不同位移')
            if deltas:
                delta = next(iter(deltas))
                proposals.update({cid: (delta, 'linked-rider') for cid in members})
    moves = []
    for track in sequence['tracks']:
        for clip in track['clips']:
            delta, reason = proposals.get(clip['id'], (0, 'anchored'))
            if delta and track.get('locked', False):
                _error('EDIT_TRACK_LOCKED', '重排涉及需要移动的锁定关联成员: ' + clip['id'])
            if start(clip)+delta < 0:
                _error('EDIT_NEGATIVE_TIME', '重排会把附着片段移动到负时间: ' + clip['id'])
            if delta:
                moves.append({'clip_id': clip['id'], 'track_id': track['id'], 'delta_tick': delta, 'reason': reason})
                clip['timeline_start_tick'] += delta
    main['clips'] = packed
    draft.settle()
    from .bindings import native_clock_project
    native = native_clock_project(candidate)
    binding_changes = []
    if native:
        from .binding_edits import replan
        # Split descendants must be traced to the pre-cut author graph. The
        # generic draft starts after split_sync and cannot recover that lineage.
        origins = {cid:cid for cid in draft.before}
        origins.update({piece['clip_id']:split['clip_id'] for split in splits for piece in split['pieces']})
        binding_changes = replan(candidate, sequence, original, origins)
        draft.rebound.extend(row['clip_id'] for row in binding_changes)
    else:
        draft.repair_bindings()
    draft.retime_subtitles()
    removed, dropped = _transitions(candidate, sequence, original, normalized['transition_policy'])
    now = {c['id']: c for t in sequence['tracks'] for c in t['clips']}
    drop_fields = {(row['clip_id'], row['field']) for row in dropped}
    for cid, (_, old) in draft.before.items():
        expected = copy.deepcopy(old)
        for field in ('transition_in', 'transition_out'):
            if (cid, field) in drop_fields:
                expected.pop(field, None)
        if cid in draft.rebound:
            if native:
                expected['tracking_binding'] = copy.deepcopy(now[cid]['tracking_binding'])
            else:
                expected['tracking_binding']['source_track_id'] = now[cid]['tracking_binding']['source_track_id']
        if _content(expected) != _content(now[cid]):
            _error('EDIT_CONTENT_INVARIANT_FAILED', '重排不能重写原作者内容: ' + cid)
    for track in original['tracks']:
        if track.get('locked', False) and draft.track(track['id']) != track:
            _error('EDIT_LOCK_INVARIANT_FAILED', '重排不能改变锁定轨道')
    sequence['duration_tick'] = max([1, *(end(c) for t in sequence['tracks'] for c in t['clips'])])
    anchored = sorted(cid for cid, (track, _) in draft.before.items()
                      if track['id'] != main_id and not proposals.get(cid, (0,))[0])
    warnings = ([{'code': 'EDIT_REORDER_TRANSITIONS_REMOVED', 'message': '按显式 drop_broken 移除受影响转场',
                  'source_transitions': removed, 'legacy_fields': dropped}] if removed or dropped else [])
    locations = {c['id']: (t['id'], start(c), end(c)) for t in sequence['tracks'] for c in t['clips']}
    for split in splits:
        for piece in split['pieces']:
            tid, first, last = locations[piece['clip_id']]
            piece.update(after_track_id=tid, after_range_tick=[first, last])
    plan = {'engine': ENGINE, 'base_project_sha256': project_fingerprint(project),
            'sequence_id': sequence_id, 'request': normalized, 'main_track_id': main_id,
            'selected_clip_ids': [c['id'] for c in ordered if c['id'] in selected],
            'before_main_order': [c['id'] for c in ordered], 'after_main_order': [c['id'] for c in packed],
            'removed_gap_tick': max(ends, default=0)-sum(c['duration_tick'] for c in ordered),
            'moves': moves, 'shifts': [{'clip_ids': [row['clip_id']], 'delta_tick': row['delta_tick']} for row in moves],
            'anchored_clip_ids': anchored, 'short_tick': 0, 'changes': _plan_changes(original, sequence),
            'new_track_ids': draft.new_tracks, 'new_tracks': [copy.deepcopy(draft.track(tid)) for tid in draft.new_tracks],
            'rebound_clip_ids': draft.rebound, 'retimed_subtitle_ids': draft.retimed_subtitles,
            'removed_transition_ids': [row['id'] for row in removed], 'dropped_legacy_transition_fields': dropped,
            'sync_splits': splits,
            'tracking_binding_changes': binding_changes,
            'before_duration_tick': original['duration_tick'], 'after_duration_tick': sequence['duration_tick'],
            'warnings': warnings,
            'limits': ['explicit-whole-clip-reorder-not-a-persistent-magnet-mode-or-screen-snap-gesture',
                       'sync_span_policy_split_partitions_full_author_windows_otherwise_rejects',
                       'markers-remain-absolute', 'effect-and-ducking-bus-relocation-rejects',
                       'original-author-graph-preserved-track-and-root-effects-evaluate-at-new-time',
                       '20000-clip-admission-is-not-a-total-RSS-or-long-film-benchmark']}
    return candidate, plan
