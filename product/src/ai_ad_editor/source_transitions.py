"""Declarative, reversible transitions with real local source handles.

The add/resize/remove and linked-audio workflow was informed by OpenFilm's
MIT transitions.ts at b138595d4c2d1fa5262b4a8a8c7cd98187c4b077 (see
OPENFILM_LICENSE.txt). This is a native integer-tick planner, not a port of
its overlap/ripple arrangement: authored clips and sequence length stay put.
"""
from __future__ import annotations

import copy
from fractions import Fraction

from .edit_planner import project_fingerprint
from .errors import AppError
from .utils import ID_RE

ENGINE = 'agent-source-transition-v1'
TYPES = {'dissolve': 'fade', 'crossfade': 'fade', 'dip_black': 'custom',
         'dip_white': 'custom', 'wipe_left': 'wipeleft', 'wipe_right': 'wiperight',
         'wipe_up': 'wipeup', 'wipe_down': 'wipedown', 'slide_left': 'slideleft',
         'slide_right': 'slideright', 'slide_up': 'slideup', 'slide_down': 'slidedown'}
FIELDS = {'id', 'type', 'duration_tick', 'from_clip_id', 'to_clip_id', 'audio_pairs'}


def fail(code, message, path='sequence.source_transitions'):
    raise AppError(code, message, exit_code=2, path=path)


def identifier(value):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        fail('SOURCE_TRANSITION_INVALID', '转场/片段 ID 无效')
    return value


def integer(value, field, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        fail('SOURCE_TRANSITION_INVALID', f'{field} 必须是整数 tick，不能是布尔或小数')
    return value


def _index(sequence):
    return {c['id']: (t, c) for t in sequence.get('tracks', []) for c in t.get('clips', [])}


def _start(c):
    return integer(c.get('timeline_start_tick'), 'timeline_start_tick')


def _duration(c):
    return integer(c.get('duration_tick'), 'duration_tick', positive=True)


def _end(c):
    return _start(c) + _duration(c)


def _frame_tick(project):
    try:
        tb = project['settings']['timebase']
        fps = tb.get('display_fps', {'num': 30, 'den': 1})
        frame = Fraction(int(tb['ticks_per_second']) * int(fps['den']), int(fps['num']))
        if frame <= 0:
            raise ValueError('nonpositive clock')
        return frame
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        fail('SOURCE_TRANSITION_FRAME_GRID', '项目时基/显示帧率无效')


def _grid(tick, frame):
    if (Fraction(tick) / frame).denominator != 1:
        fail('SOURCE_TRANSITION_FRAME_GRID', '剪口、片段边界和转场时长须精确落在显示帧网格；未静默取整')


def _handles(project, track, clip, head, tail, assets):
    if clip.get('presentation_window') is not None:
        fail('SOURCE_TRANSITION_ENDPOINT_UNSUPPORTED', '输出裁切窗口尚不支持真实源句柄扩展')
    duration = _duration(clip)
    if clip.get('sequence_id') or clip.get('speed_curve') or clip.get('freeze') or clip.get('tracking_binding'):
        fail('SOURCE_TRANSITION_CLIP_UNSUPPORTED', '真实句柄暂不支持嵌套容器、曲线变速、定格或跟踪绑定片段')
    if clip.get('transition_in') or clip.get('transition_out'):
        fail('SOURCE_TRANSITION_EDGE_CONFLICT', '参与片段已有旧式转场；请先显式移除')
    if clip.get('blend') or any(k.get('property') in {'blend.opacity', 'blend_opacity'} for k in clip.get('keyframes', [])):
        fail('SOURCE_TRANSITION_CLIP_UNSUPPORTED', '单片段混合模式/混合透明度尚无转场前的独立合成语义')
    asset = assets.get(clip.get('asset_id'), {})
    particle=isinstance(clip.get('generator'),dict) and clip['generator'].get('type')=='particles'
    if not particle and asset.get('kind') not in ({'video'} if track.get('kind') == 'video' else {'video', 'audio'}):
        fail('SOURCE_TRANSITION_CLIP_UNSUPPORTED', '真实句柄只接受本地视频及显式音轨媒体；图片/生成器另行验收')
    source_in = integer(clip.get('source_in_tick'), 'source_in_tick')
    source_out = integer(clip.get('source_out_tick'), 'source_out_tick', positive=True)
    try:
        speed = Fraction(str(clip.get('speed', 1)))
        if particle:
            from .source_edits import source_bounds
            bound=source_bounds(project,clip)['end_tick']
        else:
            bound = Fraction(str(asset['probe']['duration_seconds'])) * project['settings']['timebase']['ticks_per_second']
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        fail('SOURCE_TRANSITION_SOURCE_BOUND', '源时长或速度未登记为有限数值')
    if speed <= 0 or source_out-source_in != speed*duration:
        fail('SOURCE_TRANSITION_CLOCK_MISMATCH', '源范围/恒定速度必须与片段时长精确一致')
    source_head, source_tail = head*speed, tail*speed
    if source_head.denominator != 1 or source_tail.denominator != 1:
        fail('SOURCE_TRANSITION_SOURCE_GRID', '请求的额外源范围不能用整数 tick 精确表达')
    if clip.get('reverse'):
        new_in, new_out = source_in-int(source_tail), source_out+int(source_head)
    else:
        new_in, new_out = source_in-int(source_head), source_out+int(source_tail)
    if new_in < 0 or new_out > bound:
        fail('SOURCE_TRANSITION_HANDLE_SHORTFALL', f'片段 {clip["id"]} 缺少真实源句柄；未补帧/补静音/缩短转场')
    return {'clip_id': clip['id'], 'track_id': track['id'], 'head_tick': head, 'tail_tick': tail,
            'authored_start_tick': _start(clip), 'authored_duration_tick': duration,
            'timeline_start_tick': _start(clip)-head, 'duration_tick': duration+head+tail,
            'source_in_tick': new_in, 'source_out_tick': new_out,
            'authored_source_in_tick': source_in, 'authored_source_out_tick': source_out,
            'reverse': bool(clip.get('reverse')), 'speed': str(speed)}


def analyze(project, sequence):
    """Validate declarations and produce exact, non-mutating render windows."""
    declarations = sequence.get('source_transitions', [])
    if not isinstance(declarations, list) or len(declarations) > 256:
        fail('SOURCE_TRANSITION_INVALID', 'source_transitions 必须是最多 256 项的数组')
    if not declarations:
        return {'engine': ENGINE, 'transitions': [], 'handles': []}
    # Ancestor freeze now pauses the complete child composite and bus. The
    # transition endpoints themselves still pass the direct-clip restrictions.
    index, assets, frame = _index(sequence), {a['id']: a for a in project.get('assets', [])}, _frame_tick(project)
    used_ids = {v['id'] for s in project.get('sequences', []) for v in [s, *s.get('tracks', []),
                *(c for t in s.get('tracks', []) for c in t.get('clips', []))]}
    used_ids.update(a['id'] for a in project.get('assets', []))
    other_ids = [d['id'] for s in project.get('sequences', []) if s is not sequence
                 for d in (s.get('source_transitions') if isinstance(s.get('source_transitions'), list) else [])
                 if isinstance(d, dict) and isinstance(d.get('id'), str)]
    used_ids.update(other_ids)
    extensions, plans, windows = {}, [], {}
    for declaration in declarations:
        if not isinstance(declaration, dict) or set(declaration) != FIELDS:
            fail('SOURCE_TRANSITION_INVALID', '转场声明必须包含且仅包含约定的六个字段')
        tid = identifier(declaration['id'])
        if tid in used_ids:
            fail('SOURCE_TRANSITION_ID_DUPLICATE', f'重复 ID: {tid}')
        used_ids.add(tid)
        kind = declaration['type']
        if not isinstance(kind, str) or kind not in TYPES:
            fail('SOURCE_TRANSITION_TYPE_UNSUPPORTED', '不支持的真实句柄转场类型')
        d = integer(declaration['duration_tick'], 'duration_tick', positive=True)
        _grid(d, frame)
        # An odd frame count puts the extra frame after the cut. Both halves
        # must remain exact integer ticks (including fractional-rate grids).
        pre = (d // frame // 2) * frame
        if pre.denominator != 1:
            fail('SOURCE_TRANSITION_FRAME_GRID', '半窗不能用整数 tick 精确表达；请调整转场帧数')
        pre, post = int(pre), d-int(pre)
        left, right = identifier(declaration['from_clip_id']), identifier(declaration['to_clip_id'])
        pairs = declaration['audio_pairs']
        if not isinstance(pairs, list) or len(pairs) > len(index):
            fail('SOURCE_TRANSITION_INVALID', 'audio_pairs 必须是有界片段配对数组')
        if left not in index or right not in index or left == right:
            fail('SOURCE_TRANSITION_REFERENCE', '转场片段引用缺失或自配对')
        lt, lc = index[left]
        rt, rc = index[right]
        cut = _end(lc)
        if lt is not rt or lt.get('kind') != 'video' or cut != _start(rc):
            fail('SOURCE_TRANSITION_CUT', '图像对必须位于同一视频轨道的精确连续剪口')
        pair_list = [(left, right, 'video')]
        seen = {left, right}
        for pair in pairs:
            if not isinstance(pair, dict) or set(pair) != {'from_clip_id', 'to_clip_id'}:
                fail('SOURCE_TRANSITION_INVALID', '音频配对字段无效')
            a, b = identifier(pair['from_clip_id']), identifier(pair['to_clip_id'])
            if a == b or a in seen or b in seen or a not in index or b not in index:
                fail('SOURCE_TRANSITION_REFERENCE', '音频引用缺失、重复或自配对')
            seen.update((a, b))
            pair_list.append((a, b, 'audio'))
        for a, b, track_kind in pair_list:
            at, ac = index[a]
            bt, bc = index[b]
            if at is not bt or at.get('kind') != track_kind or _end(ac) != cut or _start(bc) != cut:
                fail('SOURCE_TRANSITION_CUT', '每组音画对必须位于同轨、同一剪口')
            for c in (ac, bc):
                _grid(_start(c), frame)
                _grid(_end(c), frame)
            if d >= min(_duration(ac), _duration(bc)):
                fail('SOURCE_TRANSITION_WINDOW', '转场时长必须小于每个参与片段的原时长')
            if cut-pre < 0 or cut+post > sequence['duration_tick']:
                fail('SOURCE_TRANSITION_WINDOW', '转场窗口越过序列范围')
            rows = windows.setdefault(at['id'], [])
            if any(cut-pre < end and start < cut+post for start, end in rows):
                fail('SOURCE_TRANSITION_WINDOW_OVERLAP', '同轨转场窗口不能相交或重复；未复合叠加')
            rows.append((cut-pre, cut+post))
            for cid, head, tail in ((a, 0, post), (b, pre, 0)):
                ext = extensions.setdefault(cid, [0, 0])
                ext[0], ext[1] = max(ext[0], head), max(ext[1], tail)
        plans.append({**copy.deepcopy(declaration), 'cut_tick': cut, 'start_tick': cut-pre,
                      'end_tick': cut+post, 'pre_tick': pre, 'post_tick': post,
                      'xfade': TYPES[kind], 'pairs': [list(p) for p in pair_list]})
    handles = [_handles(project, *index[cid], head, tail, assets)
               for cid, (head, tail) in sorted(extensions.items())]
    return {'engine': ENGINE, 'transitions': plans, 'handles': handles}


def _linked_audio(sequence, left, right):
    index = _index(sequence)
    a, b = index[left][1], index[right][1]
    if not a.get('link_id') or not b.get('link_id'):
        return []
    result = []
    for track in sequence['tracks']:
        if track.get('kind') != 'audio':
            continue
        aa = [c for c in track['clips'] if c.get('link_id') == a['link_id']]
        bb = [c for c in track['clips'] if c.get('link_id') == b['link_id']]
        if not aa and not bb:
            continue
        if len(aa) != 1 or len(bb) != 1 or aa[0]['id'] == bb[0]['id'] or _end(aa[0]) != _end(a) or _start(bb[0]) != _start(b):
            fail('SOURCE_TRANSITION_LINK_EDGE_MISMATCH', '关联音轨不能唯一配到同一剪口；可显式选择 audio=none')
        result.append({'from_clip_id': aa[0]['id'], 'to_clip_id': bb[0]['id']})
    return result


def build_plan(project, sequence_id, request):
    if not isinstance(request, dict):
        fail('SOURCE_TRANSITION_INVALID', '请求必须是对象')
    action = request.get('action')
    fields = {'add': {'action', 'id', 'type', 'duration_tick', 'from_clip_id', 'to_clip_id', 'audio'},
              'resize': {'action', 'id', 'duration_tick', 'type'}, 'remove': {'action', 'id'}}
    if not isinstance(action, str) or action not in fields or set(request)-fields[action]:
        fail('SOURCE_TRANSITION_INVALID', '操作或请求字段无效')
    candidate = copy.deepcopy(project)
    sequence = next((s for s in candidate['sequences'] if s['id'] == sequence_id), None)
    if sequence is None:
        fail('SOURCE_TRANSITION_REFERENCE', '序列不存在')
    tid = identifier(request.get('id'))
    declarations = sequence.setdefault('source_transitions', [])
    if not isinstance(declarations, list) or any(not isinstance(d, dict) for d in declarations):
        fail('SOURCE_TRANSITION_INVALID', '现有转场声明必须是对象数组')
    existing = next((d for d in declarations if d.get('id') == tid), None)
    before = copy.deepcopy(existing)
    if action == 'add':
        if existing:
            fail('SOURCE_TRANSITION_ID_DUPLICATE', '转场 ID 已存在')
        audio = request.get('audio', 'linked')
        if not isinstance(audio, str) or audio not in {'linked', 'none'}:
            fail('SOURCE_TRANSITION_INVALID', 'audio 只能是 linked 或 none')
        left, right = identifier(request.get('from_clip_id')), identifier(request.get('to_clip_id'))
        if left not in _index(sequence) or right not in _index(sequence):
            fail('SOURCE_TRANSITION_REFERENCE', '片段不存在')
        existing = {'id': tid, 'type': request.get('type', 'dissolve'),
                    'duration_tick': request.get('duration_tick'), 'from_clip_id': left, 'to_clip_id': right,
                    'audio_pairs': _linked_audio(sequence, left, right) if audio == 'linked' else []}
        declarations.append(existing)
    elif existing is None:
        fail('SOURCE_TRANSITION_REFERENCE', '转场 ID 不存在')
    elif action == 'remove':
        declarations.remove(existing)
    else:
        existing['duration_tick'] = request.get('duration_tick')
        if 'type' in request:
            existing['type'] = request['type']
    affected = before or existing
    ids = [affected['from_clip_id'], affected['to_clip_id']]
    ids += [p[k] for p in affected['audio_pairs'] for k in ('from_clip_id', 'to_clip_id')]
    index = _index(sequence)
    if any(index.get(cid, ({}, {}))[0].get('locked') for cid in ids):
        fail('SOURCE_TRANSITION_LOCKED', '参与音画轨道被锁定；整组操作拒绝')
    compiled = analyze(candidate, sequence)
    if not declarations:
        sequence.pop('source_transitions', None)
    return candidate, {'engine': ENGINE, 'action': action, 'transition_id': tid,
                       'project_sha256': project_fingerprint(project), 'sequence_id': sequence_id,
                       'before': before, 'after': None if action == 'remove' else copy.deepcopy(existing),
                       'affected_clip_ids': ids, 'authored_clips_unchanged': True,
                       'sequence_duration_tick': sequence['duration_tick'], 'render_plan': compiled}


def compile_for_render(project, sequence_id):
    """Only a detached render copy receives extended source/timeline ranges."""
    sequence = next(s for s in project['sequences'] if s['id'] == sequence_id)
    if not sequence.get('source_transitions'):
        return project, sequence, None
    plan = analyze(project, sequence)
    project = copy.deepcopy(project)
    sequence = next(s for s in project['sequences'] if s['id'] == sequence_id)
    index = _index(sequence)
    tps = project['settings']['timebase']['ticks_per_second']
    for h in plan['handles']:
        clip = index[h['clip_id']][1]
        clip['_source_handle'] = copy.deepcopy(h)
        for key in ('timeline_start_tick', 'duration_tick', 'source_in_tick', 'source_out_tick'):
            clip[key] = h[key]
        clip['_nested_keyframe_clock'] = {'maps': [], 'authored_start': h['authored_start_tick']/tps}
        clip['_nested_subtitle_clock'] = {'version': '1', 'maps': [],
            'authored_start_seconds': h['authored_start_tick']/tps,
            'authored_duration_seconds': h['authored_duration_tick']/tps,
            'reverse_boundary_bias_seconds': 0., 'freeze_semantics_approximate': False,
            'clock': 'original-sequence-presentation-time'}
    for transition in plan['transitions']:
        config = {'type': transition['xfade'], 'duration': transition['duration_tick']/tps,
                  'source_transition_id': transition['id'], 'source_type': transition['type'],
                  'cut_fraction': transition['pre_tick']/transition['duration_tick']}
        for a, b, kind in transition['pairs']:
            if kind == 'video':
                index[a][1]['transition_out'] = copy.deepcopy(config)
                index[b][1]['transition_in'] = copy.deepcopy(config)
            else:
                for cid, edge in ((a, 'out'), (b, 'in')):
                    index[cid][1].setdefault('_source_audio_envelopes', []).append({
                        'edge': edge, 'start_tick': transition['start_tick'],
                        'duration_tick': transition['duration_tick'], 'transition_id': transition['id']})
    return project, sequence, plan
