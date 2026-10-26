"""Local source bounds, linked slips and genuine authored-range extensions.

Extension holds each boundary speed outside its original source curve. It
reanchors authored automation and freeze points, and reuses the native graph;
it never encodes a replacement asset or manufactures missing source frames.
"""
from __future__ import annotations

import copy
import math
from fractions import Fraction

from .clip_windows import validate_window
from .errors import AppError
from .speed_curves import compile_curve
from .time_mapping import curve_elapsed

ENGINE = 'agent-source-edit-v1'


def fail(code, message, path='edit'):
    raise AppError(code, message, exit_code=2, path=path)


def source_bounds(project, clip):
    """Exact bounds as recorded in the local asset/sequence, in project ticks."""
    tps = project['settings']['timebase']['ticks_per_second']
    if isinstance(clip.get('generator'),dict) and clip['generator'].get('type')=='particles':
        from .procedural_particles import normalize, identity
        config=normalize(clip['generator'])
        return {'kind':'particles','source_id':identity(config),
                'end_tick':Fraction(config['duration_tick']*tps,config['ticks_per_second'])}
    sid = clip.get('sequence_id')
    if sid:
        sequence = next((s for s in project['sequences'] if s['id'] == sid), None)
        if sequence is None:
            fail('SOURCE_EDIT_REFERENCE', '源序列不存在')
        return {'kind': 'sequence', 'source_id': sid, 'end_tick': Fraction(sequence['duration_tick'])}
    asset = next((a for a in project.get('assets', []) if a['id'] == clip.get('asset_id')), None)
    if not asset or asset.get('kind') not in {'video', 'audio'}:
        fail('SOURCE_EDIT_KIND_UNSUPPORTED', '源编辑接受已登记本地视频、音频和序列；静态内容时长使用普通时间线接口')
    try:
        duration = Fraction(str(asset['probe']['duration_seconds']))
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        fail('SOURCE_EDIT_BOUND_UNKNOWN', '素材未登记有限源时长；请先重新探测本地素材')
    if duration <= 0:
        fail('SOURCE_EDIT_BOUND_UNKNOWN', '素材源时长必须为正数')
    return {'kind': asset['kind'], 'source_id': asset['id'], 'end_tick': duration*tps}


def checked_range(bounds, first, last):
    if first < 0 or last <= first or last > bounds['end_tick']:
        fail('SOURCE_EDIT_HANDLE_SHORTFALL', '真实源范围不足；没有补帧、补静音、循环或截短请求')


def clock(clip, duration, tps):
    span = clip['source_out_tick']-clip['source_in_tick']
    segments = compile_curve(clip, span, tps)
    try:
        base = Fraction(str(clip.get('speed', 1)))
    except (ValueError, TypeError, ZeroDivisionError):
        fail('SOURCE_EDIT_CLOCK_INVALID', '源速度必须为有限正数')
    if base <= 0:
        fail('SOURCE_EDIT_CLOCK_INVALID', '源速度必须为正数')
    freeze = clip.get('freeze') or {}
    extra = freeze.get('duration_tick', 0)
    if segments:
        content = curve_elapsed(segments, span/tps)*tps
        raw = clip['speed_curve']
        points = raw.get('keyframes', []) if isinstance(raw, dict) else raw
        points = sorted({p['at_tick']: p for p in points}.values(), key=lambda p: p['at_tick'])
        low = Fraction(str(max(.01, float(points[0].get('speed', points[0].get('value', base)))))) if points[0]['at_tick'] == 0 else max(Fraction('0.01'), base)
        high = Fraction(str(max(.01, float(points[-1].get('speed', points[-1].get('value', base))))))
    else:
        content = Fraction(span)/base
        low = high = base
    # A short authored window may crop the processed content. An author that
    # outlasts all content contains padding, not a physical source handle.
    nested_curve = bool(clip.get('sequence_id') and segments)
    if not nested_curve and float(duration-extra-content) > 1:
        fail('SOURCE_EDIT_PADDED_AUTHOR', '完整作者时长含超出真实内容的填充；请先明确重建该作者范围，再外扩')
    if freeze and freeze.get('at_tick', 0) > float(content)+1:
        fail('SOURCE_EDIT_FREEZE_CLOCK_INVALID', '原定格点超出真实内容钟，不能借外扩静默更换定格源帧')
    return {'segments': segments, 'content_tick': content, 'freeze_tick': extra, 'nested_curve': nested_curve,
        'low_speed': low, 'high_speed': high}


def _extend_curve(original, source_left, source_right):
    value = original.get('speed_curve')
    if not value:
        return None
    span = original['source_out_tick']-original['source_in_tick']
    raw = value.get('keyframes', []) if isinstance(value, dict) else value
    points = sorted({p['at_tick']: copy.deepcopy(p) for p in raw}.values(), key=lambda p: p['at_tick'])
    if not points:
        return copy.deepcopy(value)
    base = max(.01, float(original.get('speed', 1)))
    if points[0]['at_tick'] > 0:
        points.insert(0, {'at_tick': 0, 'speed': base, 'interpolation': 'hold'})
    first_speed = max(.01, float(points[0].get('speed', points[0].get('value', base))))
    last_speed = max(.01, float(points[-1].get('speed', points[-1].get('value', base))))
    if points[-1]['at_tick'] < span:
        points.append({'at_tick': span, 'speed': last_speed, 'interpolation': 'hold'})
    for point in points:
        point['at_tick'] += source_left
    if source_left:
        points.insert(0, {'at_tick': 0, 'speed': first_speed, 'interpolation': 'hold'})
    if source_right:
        points[-1]['interpolation'] = 'hold'
        points[-1].pop('control_points', None)
        points.append({'at_tick': span+source_left+source_right, 'speed': last_speed, 'interpolation': 'hold'})
    if isinstance(value, dict):
        result = copy.deepcopy(value); result['keyframes'] = points
        return result
    return points


def slip(project, clip, delta):
    if not delta:
        return copy.deepcopy(clip), {'clip_id': clip['id'], 'source_delta_tick': 0, 'noop': True}
    bounds = source_bounds(project, clip)
    first, last = clip['source_in_tick']+delta, clip['source_out_tick']+delta
    checked_range(bounds, first, last)
    result = copy.deepcopy(clip)
    result['source_in_tick'], result['source_out_tick'] = first, last
    return result, {'clip_id': clip['id'], 'source_delta_tick': delta,
        'source_id': bounds['source_id'], 'source_kind': bounds['kind'],
        'source_bound_tick': str(bounds['end_tick']),
        'before_source': [clip['source_in_tick'], clip['source_out_tick']], 'after_source': [first, last],
        'timeline_duration_automation_and_window_unchanged': True}


def _shift_automation(value, delta):
    """Reanchor output-local keys, including clip and audio effect automation."""
    count = 0
    if isinstance(value, dict):
        if type(value.get('at_tick')) is int:
            value['at_tick'] += delta
            count += 1
        for item in value.values():
            if isinstance(item, (dict, list)):
                count += _shift_automation(item, delta)
    elif isinstance(value, list):
        for item in value:
            count += _shift_automation(item, delta)
    return count


def expand_author(project, clip, head, tail):
    """Reauthor a genuine finite source extension on the native clip clock.

    Head extension requires an exact source-tick boundary. The tail may crop
    already authored source output, then grows the physical source only as
    needed; a fractional final source tick is conservatively included. Recompile
    the extended curve to check its actual bounded approximation covers output.
    """
    from .bindings import native_clock_project
    native_tracking=native_clock_project(project)
    duration = validate_window(clip,allow_tracking=native_tracking)
    bounds = source_bounds(project, clip)
    tps = project['settings']['timebase']['ticks_per_second']
    mapping = clock(clip, duration, tps)
    reverse = bool(clip.get('reverse'))
    head_speed = mapping['high_speed'] if reverse else mapping['low_speed']
    tail_speed = mapping['low_speed'] if reverse else mapping['high_speed']
    head_source = head*head_speed
    if head_source.denominator != 1:
        fail('SOURCE_EDIT_SOURCE_GRID', '头部外扩无法用整数源 tick 精确表达；未静默四舍五入')
    head_source = int(head_source)
    # Nested curves retain their native duration-normalized semantics. This
    # reauthoring differs from selecting an unchanged old processing window.
    needed_content = (mapping['content_tick']+tail if mapping['nested_curve']
                      else duration+tail-mapping['freeze_tick'])
    deficit = needed_content-mapping['content_tick']
    tail_source = max(0, math.ceil(deficit*tail_speed))
    result = copy.deepcopy(clip)
    for attempt in range(8):
        source_left, source_right = (tail_source, head_source) if reverse else (head_source, tail_source)
        first, last = clip['source_in_tick']-source_left, clip['source_out_tick']+source_right
        checked_range(bounds, first, last)
        result['source_in_tick'], result['source_out_tick'] = first, last
        curve = _extend_curve(clip, source_left, source_right)
        if curve is not None:
            result['speed_curve'] = curve
        segments = compile_curve(result, last-first, tps)
        content = curve_elapsed(segments, (last-first)/tps)*tps if segments else Fraction(last-first)/head_speed
        # After adding the exact prefix, the old author's requested final
        # frame/sample must still fit. Include, never clone, one extra source
        # tick when the compiler's changed subdivision requires it.
        missing = (mapping['content_tick']+head+tail-content if mapping['nested_curve']
                   else duration+head+tail-mapping['freeze_tick']-content)
        if float(missing) <= 1e-7:
            break
        tail_source += max(1, math.ceil(missing*tail_speed))
    else:
        fail('SOURCE_EDIT_CURVE_BUDGET', '扩展曲线在八次有界重编译内不能覆盖目标时钟')
    old_start = clip.get('presentation_window', {}).get('authored_start_tick', clip['timeline_start_tick'])
    new_start = max(0, old_start-head)
    shifted = sum(_shift_automation(value, head) for value in
                  (result.get('keyframes', []), result.get('effects', []),
                   result.get('audio', {}).get('effects', [])))
    binding_keys=(result.get('tracking_binding') or {}).get('base',{}).get('opacity_keyframes',[])
    shifted_binding_keys=_shift_automation(binding_keys,head)
    if result.get('freeze'):
        result['freeze']['at_tick'] += head
    cue_shift = old_start-(new_start+head)
    subtitle = result.get('subtitle')
    if isinstance(subtitle, dict) and subtitle.get('asset_uri') and subtitle.get('asset_time_base', 'sequence') == 'sequence':
        subtitle['asset_time_offset_tick'] = subtitle.get('asset_time_offset_tick', 0)+cue_shift
    window = result.setdefault('presentation_window', {'version': 1, 'authored_start_tick': old_start,
        'authored_duration_tick': duration, 'offset_tick': 0})
    window['authored_start_tick'] = new_start
    window['authored_duration_tick'] = duration+head+tail
    window['offset_tick'] += head
    validate_window(result,allow_tracking=native_tracking)
    return result, {'clip_id': clip['id'], 'engine': ENGINE, 'source_kind': bounds['kind'], 'source_id': bounds['source_id'],
        'source_bound_tick': str(bounds['end_tick']), 'head_tick': head, 'tail_tick': tail,
        'source_left_tick': source_left, 'source_right_tick': source_right,
        'before_source': [clip['source_in_tick'], clip['source_out_tick']], 'after_source': [first, last],
        'before_author_duration_tick': duration, 'after_author_duration_tick': duration+head+tail,
        'head_speed': str(head_speed), 'tail_speed': str(tail_speed), 'curve_recompile_count': attempt+1,
        'actual_content_tick': float(content), 'shifted_keyframe_count': shifted,
        'shifted_binding_opacity_keys':shifted_binding_keys,
        'native_nested_curve_renormalized': mapping['nested_curve'],
        'before_nested_curve_scale': float(duration/mapping['content_tick']) if mapping['nested_curve'] else None,
        'after_nested_curve_scale': float((duration+head+tail)/content) if mapping['nested_curve'] else None,
        'freeze_shift_tick': head if result.get('freeze') else 0,
        'boundary_speed_policy': 'hold-authored-boundary-speeds',
        'automation_policy': 'shift-output-keyframes-and-freeze-by-prefix;edge-fades-and-native-retiming-reauthored',
        'tail_source_tick_policy': 'include-minimum-whole-tick-covering-native-compiled-clock'}
