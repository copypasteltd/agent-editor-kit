"""Exact authored transition windows, independent of pixel execution."""
from fractions import Fraction
import math
from .clip_windows import validate_window
from .float_transitions import error, resolve


def duration_ticks(config, tps):
    value = config.get('duration', .25)
    if isinstance(value, bool):
        raise error('DURATION', '转场时长必须是有限正数')
    try:
        if not math.isfinite(float(value)):
            raise ValueError('nonfinite')
        ticks = Fraction(str(value))*tps
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise error('DURATION', '转场时长必须是有限正数') from exc
    if ticks <= 0:
        raise error('DURATION', '转场时长必须是有限正数')
    return ticks


def compile_track(track, tps, source_plan=None):
    clips = track.get('clips', [])
    by_id = {c['id']: c for c in clips}
    pairs, consumed, edges = [], set(), {}
    for row in (source_plan or {}).get('transitions', []):
        left, right = row['from_clip_id'], row['to_clip_id']
        if left not in by_id or right not in by_id:
            continue
        pairs.append({'id': row['id'], 'from': left, 'to': right, 'start': Fraction(row['start_tick']),
            'end': Fraction(row['end_tick']), 'type': resolve({'type': row['type']}),
            'cut_fraction': Fraction(row['pre_tick'], row['duration_tick']), 'real_source_handles': True})
        consumed.update(((left, 'out'), (right, 'in')))
    ordered = sorted(enumerate(clips), key=lambda row: (row[1]['timeline_start_tick'], row[0]))
    for (_, left), (_, right) in zip(ordered, ordered[1:]):
        a, b = left.get('transition_out'), right.get('transition_in')
        available_a = a and (left['id'], 'out') not in consumed
        available_b = b and (right['id'], 'in') not in consumed
        if not (available_a or available_b):
            continue
        # A fade/fade_in/fade_out is an independent edge envelope. Dissolve,
        # crossfade and spatial patterns request a two-source overlap when one
        # exists; unmatched spatial edges transition against transparent RGBA.
        config = b if available_b else a
        raw_kind = config.get('type')
        start = Fraction(right['timeline_start_tick'])
        end = Fraction(left['timeline_start_tick']+left['duration_tick'])
        duration = duration_ticks(config, tps)
        if end <= start or raw_kind in {'fade', 'fade_in', 'fade_out'}:
            continue
        if end-start != duration:
            raise error('WINDOW', '两源转场重叠必须精确等于声明时长；未克隆帧或缩短窗口')
        if available_a and available_b and (resolve(a) != resolve(b) or duration_ticks(a, tps) != duration):
            raise error('PAIR_CONFLICT', '同一转场两端类型或时长不一致')
        pairs.append({'id': left['id']+'->'+right['id'], 'from': left['id'], 'to': right['id'],
            'start': start, 'end': end, 'type': resolve(config), 'cut_fraction': Fraction(1, 2),
            'real_source_handles': False})
        if available_a: consumed.add((left['id'], 'out'))
        if available_b: consumed.add((right['id'], 'in'))
    for pair in pairs:
        for cid in (pair['from'], pair['to']):
            if (by_id[cid].get('blend') or {}).get('mode', 'normal') != 'normal':
                raise error('BLEND', '两源转场需 normal 图层混合；非 normal 尚无统一转场前语义')
        if any(other is not pair and pair['start'] < other['end'] and other['start'] < pair['end'] for other in pairs):
            raise error('WINDOW_OVERLAP', '同轨两源转场窗口不能相交')
    for clip in clips:
        authored = validate_window(clip)
        envelopes = []
        for edge in ('in', 'out'):
            config = clip.get('transition_'+edge)
            if not config or (clip['id'], edge) in consumed:
                continue
            if config.get('source_transition_id'):
                raise error('PAIR_CONFLICT', '真实源句柄转场未找到完整配对')
            if config.get('auto_handle') or config.get('handle_policy') == 'auto':
                raise error('HANDLE_POLICY', '浮点转场不克隆尾帧；使用显式重叠或 source_transitions 真实句柄')
            d = duration_ticks(config, tps)
            if d > authored:
                raise error('WINDOW', '图层转场不能长于作者片段')
            envelopes.append({'edge': edge, 'duration': d, 'type': resolve(config), 'authored_duration': authored})
        if sum((e['duration'] for e in envelopes), Fraction()) > authored:
            raise error('WINDOW_OVERLAP', '同一图层入场和出场窗口不能相交')
        edges[clip['id']] = envelopes
    return {'pairs': pairs, 'edges': edges}
