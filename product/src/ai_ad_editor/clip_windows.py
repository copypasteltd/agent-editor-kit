"""Non-destructive presentation cuts, after the complete authored clip graph.

The source range and every authored animation remain intact. A visible window
is measured on the clip's output clock, including reversal, retiming and freeze.
Track/sequence processing stays outside this clip boundary.
"""
from __future__ import annotations

import copy
import math
from fractions import Fraction

from .errors import AppError
from .utils import ID_RE
from .sequence_canvas import sequence_canvas

ENGINE = 'agent-presentation-window-v1'
OPERATIONS = {'split_clip', 'trim_clip', 'ripple_insert', 'ripple_delete'}


def fail(message, path='presentation_window', code='CLIP_WINDOW_INVALID'):
    raise AppError(code, message, exit_code=2, path=path)


def integer(value, path, minimum=0):
    if type(value) is not int or value < minimum:
        fail('必须为范围内的整数 tick，不能使用布尔值或浮点数', path)
    return value


def validate_track_transitions(track):
    if any(c.get('presentation_window') for c in track.get('clips',[])) and any(
        isinstance(c.get(field),dict) and c[field].get('type') not in {None,'','fade','fade_in','fade_out'}
        for c in track.get('clips',[]) for field in ('transition_in','transition_out')):
        fail('输出窗口轨道含旧式跨片段转场；请先移除或裁切完整嵌套容器',code='CLIP_WINDOW_TRANSITION_CONFLICT')


def validate_window(clip, *, allow_tracking=False):
    value = clip.get('presentation_window')
    if value is None and 'presentation_window' not in clip:
        return int(clip['duration_tick'])
    if not isinstance(value, dict) or set(value) != {'version', 'authored_start_tick', 'authored_duration_tick', 'offset_tick'}:
        fail('窗口必须包含 version/authored_start_tick/authored_duration_tick/offset_tick')
    if type(value['version']) is not int or value['version'] != 1:
        fail('窗口 version 必须为整数 1')
    integer(value['authored_start_tick'], 'presentation_window.authored_start_tick')
    duration = integer(value['authored_duration_tick'], 'presentation_window.authored_duration_tick', 1)
    offset = integer(value['offset_tick'], 'presentation_window.offset_tick')
    visible = integer(clip['duration_tick'], 'duration_tick', 1)
    if offset + visible > duration:
        fail('可见窗口不能越过完整作者时长')
    if clip.get('tracking_binding') and not allow_tracking:
        fail('跟踪绑定尚未接受输出窗口裁切；请先解除绑定', code='CLIP_WINDOW_BINDING_UNSUPPORTED')
    return duration


def slice_clip(clip, first, end, *, clip_id=None, start=None):
    validate_window(clip)
    integer(first, 'start_tick'); integer(end, 'end_tick', 1)
    if first >= end or end > clip['duration_tick']:
        fail('裁切窗口必须为当前可见片段内的非空半开区间')
    result = copy.deepcopy(clip)
    window = result.get('presentation_window') or {
        'version': 1, 'authored_start_tick': clip['timeline_start_tick'],
        'authored_duration_tick': clip['duration_tick'], 'offset_tick': 0}
    window['offset_tick'] += first
    result['presentation_window'] = window
    result['duration_tick'] = end-first
    result['timeline_start_tick'] = clip['timeline_start_tick']+first if start is None else start
    if clip_id is not None:
        result['id'] = clip_id
    validate_window(result)
    return result


def apply_operation(project, sequence_id, request):
    """Detached deterministic compose operation; caller owns validation/commit."""
    candidate = copy.deepcopy(project)
    sequence = next(s for s in candidate['sequences'] if s['id'] == sequence_id)
    op = request['op']
    if op not in OPERATIONS:
        fail('未知的输出窗口操作', 'op')
    common={'op','sequence_id','track_id'}
    fields={'split_clip':{'clip_id','id','at_tick','left_id','right_id'},
        'trim_clip':{'clip_id','id','start_tick','end_tick','timeline_start_tick'},
        'ripple_insert':{'at_tick','duration_tick'},'ripple_delete':{'at_tick','duration_tick'}}
    if set(request)-common-fields[op]:
        fail('窗口操作包含未知字段，未静默忽略', 'operations')
    ids = {str(x['id']) for s in candidate['sequences'] for t in s['tracks'] for x in [t, *t['clips']]}
    ids.update(str(s['id']) for s in candidate['sequences'])
    ids.update(str(a['id']) for a in candidate['assets'])
    changed = []

    def new_id(proposed):
        if not isinstance(proposed, str) or not ID_RE.fullmatch(proposed) or proposed in ids:
            fail('生成的 ID 无效或在项目中已经存在', 'clip_id')
        ids.add(proposed)
        return proposed

    def generated(base):
        result, serial = base, 1
        while result in ids:
            serial += 1; result = f'{base}_{serial}'
        return new_id(result)

    def guard(track, clip):
        if track.get('locked'):
            fail('不能修改锁定轨道', 'track_id', 'EDIT_TRACK_LOCKED')
        if clip.get('tracking_binding') or any(c.get('tracking_binding', {}).get('source_clip_id') == clip['id']
            for t in sequence['tracks'] for c in t['clips']):
            fail('裁切影响跟踪绑定，尚未实现对应引用重规划', code='CLIP_WINDOW_BINDING_UNSUPPORTED')
        # Transition declarations refer to exact cut endpoints; never silently
        # retarget them after surgery. Other, unaffected declarations survive.
        if any(clip['id'] == d.get('from_clip_id') or clip['id'] == d.get('to_clip_id')
               or any(clip['id'] in pair.values() for pair in d.get('audio_pairs', []))
               for d in sequence.get('source_transitions', [])):
            fail('请先移除受影响的真实源句柄转场', code='CLIP_WINDOW_TRANSITION_CONFLICT')
        changed.append(clip['id'])

    tracks = sequence['tracks']
    if request.get('track_id'):
        tracks = [t for t in tracks if t['id'] == request['track_id']]
        if not tracks:
            fail('轨道不存在', 'track_id')
    if op in {'split_clip', 'trim_clip'}:
        found = [(t, c) for t in tracks for c in t['clips'] if c['id'] == request.get('clip_id', request.get('id'))]
        if len(found) != 1:
            fail('片段不存在或不唯一', 'clip_id')
        track, clip = found[0]; guard(track, clip)
        if op == 'split_clip':
            cut = integer(request.get('at_tick'), 'at_tick', 1)
            if cut >= clip['duration_tick']:
                fail('split_clip 的 at_tick 必须位于片段内部', 'at_tick')
            left = slice_clip(clip, 0, cut, clip_id=new_id(request.get('left_id', clip['id']+'_a')))
            right = slice_clip(clip, cut, clip['duration_tick'], clip_id=new_id(request.get('right_id', clip['id']+'_b')))
            position = track['clips'].index(clip)
            track['clips'][position:position+1] = [left, right]
        else:
            first = integer(request.get('start_tick', 0), 'start_tick')
            end = integer(request.get('end_tick', clip['duration_tick']), 'end_tick', 1)
            start = request.get('timeline_start_tick')
            if start is not None:
                integer(start, 'timeline_start_tick')
            track['clips'][track['clips'].index(clip)] = slice_clip(clip, first, end, start=start)
    else:
        at = integer(request.get('at_tick'), 'at_tick')
        delta = integer(request.get('duration_tick'), 'duration_tick', 1)
        if op == 'ripple_delete' and at+delta > sequence['duration_tick']:
            fail('删除区间越过序列时长', 'duration_tick')
        affected = {c['id'] for t in tracks for c in t['clips'] if c['timeline_start_tick']+c['duration_tick'] > at}
        links = {c.get('link_id') for t in tracks for c in t['clips'] if c['id'] in affected and c.get('link_id')}
        if any(c.get('link_id') in links and c['id'] not in affected for t in sequence['tracks'] if t not in tracks for c in t['clips']):
            fail('单轨波纹会拆开关联组；请选择全部相关轨道', code='CLIP_WINDOW_LINK_CONFLICT')
        for track in tracks:
            retained = []
            for clip in track['clips']:
                start, duration = clip['timeline_start_tick'], clip['duration_tick']
                end = start+duration
                if end <= at:
                    retained.append(clip); continue
                guard(track, clip)
                if op == 'ripple_insert':
                    if start >= at:
                        # Even whole-clip movement must retain file subtitle
                        # and animation author clocks. A zero-offset window
                        # performs this without rewriting their payload.
                        retained.append(slice_clip(clip, 0, duration, start=start+delta))
                    else:
                        retained.extend([slice_clip(clip, 0, at-start),
                            slice_clip(clip, at-start, duration, clip_id=generated(clip['id']+'_after'), start=at+delta)])
                else:
                    cut_end = at+delta
                    if start >= cut_end:
                        retained.append(slice_clip(clip, 0, duration, start=start-delta))
                    else:
                        if start < at:
                            retained.append(slice_clip(clip, 0, at-start))
                        if end > cut_end:
                            retained.append(slice_clip(clip, cut_end-start, duration,
                                clip_id=generated(clip['id']+'_after') if start < at else clip['id'], start=at))
            track['clips'] = retained
        natural = max([1, *(c['timeline_start_tick']+c['duration_tick'] for t in sequence['tracks'] for c in t['clips'])])
        sequence['duration_tick'] = max(natural, max(sequence['duration_tick'],at)+delta if op == 'ripple_insert' else sequence['duration_tick']-delta)
    for track in sequence['tracks']:
        validate_track_transitions(track)
    sequence['duration_tick'] = max([sequence['duration_tick'], *(c['timeline_start_tick']+c['duration_tick'] for t in sequence['tracks'] for c in t['clips'])])
    return candidate, {'engine': ENGINE, 'operation': op, 'changed_clip_ids': changed,
        'clock': 'complete-authored-output-before-visible-window',
        'markers': 'absolute-sequence-ticks-unchanged', 'sequence_id': sequence_id}


def prepare(root, project, sequence, build_graph, *, stack=(), video_only=False):
    """Compile visible takes into native full-precision AV graph pads.

    This is a render-only lowering, not nested author data or a cached encoded
    clip. All source windows, curves and animation values remain in the project.
    """
    windows = [(t, c) for t in sequence['tracks'] if not t.get('muted') and not (video_only and t['kind']=='audio') for c in t['clips'] if c.get('presentation_window')]
    if not windows:
        return project, sequence, [], [], []
    if len(windows) > 64 or len(stack) > 16:
        fail('输出窗口图超过 64 个直接窗口或 16 层递归配额', code='CLIP_WINDOW_BUDGET_EXCEEDED')
    from .inline_sequences import graph_namespace
    detached = copy.deepcopy(project)
    target = next(s for s in detached['sequences'] if s['id'] == sequence['id'])
    inputs, filters, metadata = [], [], []
    tps = project['settings']['timebase']['ticks_per_second']
    fps = project['settings']['timebase']['display_fps']
    rate = Fraction(fps['num'], fps['den'])
    for ordinal, (track, clip) in enumerate(windows):
        authored_duration = validate_window(clip)
        window = clip['presentation_window']
        child_project = copy.deepcopy(project)
        child_project['settings'].pop('adjustments', None)
        # This selects the renderer's existing transparent-canvas mode. No
        # child encoder runs: its actual graph pad remains full RGBA.
        child_project['settings'].setdefault('output', {}).setdefault('video', {})['pixel_format'] = 'yuva420p'
        authored = copy.deepcopy(clip)
        authored.pop('presentation_window')
        # A transparent compiler surface must not change the author's opaque
        # contain/padding choice and reveal lower tracks through black bars.
        authored['_window_original_canvas_alpha'] = str(project['settings'].get('output',{}).get('video',{}).get('pixel_format','')) in {'yuva420p'}
        authored['timeline_start_tick'] = window['authored_start_tick']
        authored['duration_tick'] = authored_duration
        blend = authored.pop('blend', None)
        blend_tracks = [k for k in authored.get('keyframes', []) if k.get('property') in {'blend.opacity', 'blend_opacity'}]
        authored['keyframes'] = [k for k in authored.get('keyframes', []) if k not in blend_tracks]
        sid = f'__window_{sequence["id"]}_{ordinal}'
        while any(s['id'] == sid for s in child_project['sequences']):
            sid += '_'
        child = {'id': sid, 'canvas': sequence_canvas(project, sequence),
            'duration_tick': window['authored_start_tick']+authored_duration,
            'tracks': [{'id': '__window_track', 'kind': track['kind'], 'order': 0, 'clips': [authored]}]}
        child_project['sequences'].append(child)
        child_inputs, graph, child_meta, warnings = build_graph(root, child_project, child,
            _allow_audio_only=(track['kind'] == 'audio'), _inline_stack=(*stack, sequence['id']))
        prefix = f'window{ordinal}_'
        offset = inputs.count('-i'); inputs.extend(child_inputs)
        filters.append(graph_namespace(graph, prefix, offset))
        first_tick = window['authored_start_tick']+window['offset_tick']
        first_frame = math.ceil(Fraction(first_tick, tps)*rate)
        end_frame = math.ceil(Fraction(first_tick+clip['duration_tick'], tps)*rate)
        first_sample = math.ceil(Fraction(first_tick*48000, tps))
        count = math.ceil(Fraction((clip['timeline_start_tick']+clip['duration_tick'])*48000, tps))-math.ceil(Fraction(clip['timeline_start_tick']*48000, tps))
        aid = f'__window_asset_{sequence["id"]}_{ordinal}'
        while any(a['id'] == aid for a in detached['assets']):
            aid += '_'
        picture, sound = prefix+'picture', prefix+'sound'
        if track['kind'] != 'audio':
            # A positive sub-frame window has at least its first sampled frame.
            filters.append(f'[{prefix}vout]trim=start_frame={first_frame}:end_frame={max(first_frame+1,end_frame)},setpts=PTS-STARTPTS[{picture}]')
        else:
            filters.append(f'[{prefix}vout]nullsink')
        if track['kind'] == 'audio' or clip.get('sequence_id'):
            filters.append(f'[{prefix}aout]atrim=start_sample={first_sample}:end_sample={first_sample+count},asetpts=N/SR/TB,apad=whole_len={count},atrim=end_sample={count}[{sound}]')
        else:
            filters.append(f'[{prefix}aout]anullsink')
            sound = None
        terminal = {'id': clip['id'], 'asset_id': aid, 'timeline_start_tick': clip['timeline_start_tick'],
            'duration_tick': clip['duration_tick'], 'source_in_tick': 0, 'source_out_tick': clip['duration_tick'],
            '_presentation_surface': {'video': picture if track['kind'] != 'audio' else None, 'audio': sound,
                'video_frame_count': max(1,end_frame-first_frame) if track['kind'] != 'audio' else 0},
            'audio': {k:v for k,v in (clip.get('audio') or {}).items() if k in {'role', 'ducking', 'duck_under_voice'}}}
        if blend is not None:
            terminal['blend'] = blend
            terminal['keyframes'] = copy.deepcopy(blend_tracks)
            terminal['_nested_keyframe_clock'] = {'maps': [], 'authored_start': (clip['timeline_start_tick']-window['offset_tick'])/tps}
        target_track = next(t for t in target['tracks'] if t['id'] == track['id'])
        target_track['clips'][next(i for i,c in enumerate(target_track['clips']) if c['id'] == clip['id'])] = terminal
        detached['assets'].append({'id': aid, 'kind': 'video', 'probe': {}})
        metadata.append({'kind': 'sequence-inline-surface', 'purpose': 'clip-presentation-window',
            'clip_id': clip['id'], 'sequence_id': sequence['id'], 'inputs': child_meta, 'warnings': warnings,
            'authored_start_tick': window['authored_start_tick'], 'authored_duration_tick': authored_duration,
            'offset_tick': window['offset_tick'], 'visible_duration_tick': clip['duration_tick'],
            'source_first_frame': first_frame, 'source_end_frame': end_frame, 'source_start_sample': first_sample,
            'selected_sample_count': count, 'input_count': len(child_inputs) and child_inputs.count('-i'),
            'video_clock': 'complete-authored-clip-before-output-cut', 'audio_path': 'processed-author-clip-before-sample-cut',
            'native_canvas': child['canvas'], 'intermediate_files': 0,
            'estimated_surface_working_bytes': child['canvas']['width']*child['canvas']['height']*16})
    return detached, target, inputs, filters, metadata
