"""Bake native tracking into ordinary hold keys and verify every display frame.

Only the binding is baked. Original media, clocks, masks, transitions, audio and
the project graph remain editable. An external player's capabilities are a
separate question; a successful bake never certifies an external renderer.
"""
import copy
from fractions import Fraction
import hashlib
import json
import math

from .animation import keyframe_value
from .bindings import apply_compiled_binding
from .errors import AppError
from .native_audio_clock import cancel

PROTOCOL = 'native-PTS-tracking-frame-verified-bake-v1'
MAX_FRAMES = 20_000
MAX_SAMPLES = 256_000
PROPERTIES = {
    'position.x': ('transform.position.x', 'position.x', 'position_x'),
    'position.y': ('transform.position.y', 'position.y', 'position_y'),
    'opacity': ('transform.opacity', 'opacity'),
    'scale': ('transform.scale', 'scale'),
    'rotation': ('transform.rotation', 'rotation'),
}


def error(kind, message, **details):
    return AppError('TRACK_BIND_BAKE_' + kind, message, exit_code=2,
                    diagnostics=details or None)


def _digest(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True,
        ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _surface_digest(surface):
    return hashlib.sha256(surface.tobytes(order='C')).hexdigest()


def _defaults(clip, tick, properties):
    transform = clip.get('transform') or {}
    position = transform.get('position') or {}
    defaults = {'position.x': position.get('x', transform.get('position_x', .5)),
                'position.y': position.get('y', transform.get('position_y', .5)),
                'opacity': transform.get('opacity', 1), 'scale': transform.get('scale', 1),
                'rotation': transform.get('rotation', 0)}
    return {prop: keyframe_value(clip, PROPERTIES[prop], float(defaults[prop]), tick)
            for prop in properties}


def compile_samples(clip, samples):
    """Find integer hold keys without rounding values or moving a sampled step.

    Fractional display/retime clocks need not themselves be integer ticks. A
    step may be placed on an integer between consecutive demands only when
    evaluating it at every original floating author tick gives the exact value.
    Conflicting left/right limits or sub-tick changes are rejected explicitly.
    """
    binding = clip['tracking_binding']
    properties = ['position.x', 'position.y', 'opacity']
    if binding['scale_mode'] == 'roi': properties.append('scale')
    if binding['rotation_mode'] == 'source': properties.append('rotation')
    demands = {}
    for tick, overrides in samples:
        tick = float(tick)
        if not math.isfinite(tick): raise error('CLOCK', '绑定作者时钟必须有限')
        values = _defaults(clip, tick, properties)
        values.update({key: value for key, value in overrides.items() if key in values})
        if not all(math.isfinite(v) for v in values.values()):
            raise error('VALUES', '绑定烘焙值必须有限', clip=clip['id'])
        if tick in demands and demands[tick] != values:
            raise error('CLOCK_CONFLICT', '同一作者时刻需要不同绑定值；请保留活动绑定工程包', clip=clip['id'], tick=str(tick))
        demands[tick] = values
    if not demands:
        # A muted/unreachable target cannot affect this frozen display graph.
        return None
    tracks = []
    ordered = sorted(demands.items())
    for prop in properties:
        keys = []; previous_tick = None
        for tick, values in ordered:
            value = values[prop]
            if not keys or value != keys[-1]['value']:
                at = max(0, math.floor(tick))
                if keys and at <= previous_tick:
                    raise error('SUBTICK', '整数关键帧无法保留相邻原生采样的变化；请提高工程时基或保留活动绑定工程包',
                                clip=clip['id'], property=prop, previous_tick=str(previous_tick), tick=str(tick))
                keys.append(dict(at_tick=at, value=value, interpolation='hold'))
            previous_tick = tick
        # Linear replay check; sorting/scanning all keys at every demand would
        # be quadratic at the declared long-project budget. The second actual
        # render below independently checks the renderer's ordinary evaluator.
        cursor = 0
        for tick, values in ordered:
            while cursor + 1 < len(keys) and keys[cursor + 1]['at_tick'] <= tick: cursor += 1
            if keys[cursor]['value'] != values[prop]:
                raise error('CLOCK', '整数关键帧回读未保持原生采样值', clip=clip['id'], property=prop)
        tracks.append(dict(property='transform.' + prop, keyframes=keys))
    return dict(keyframes=tracks, samples=len(ordered))


def bake(root, project, *, cancel_file=None, context_factory=None):
    """Return a copy and a receipt; never write an author project or output file."""
    from .float_standard_render import FloatRenderContext
    from .render import output_settings
    poll = lambda: cancel(cancel_file)
    poll()
    original = _digest(project)
    timebase = project['settings']['timebase']
    tps = timebase['ticks_per_second']; rate = timebase['display_fps']
    if any(type(v) is not int or v <= 0 for v in (tps, rate['num'], rate['den'])):
        raise error('CLOCK', '烘焙时基和显示帧率必须为正整数比')
    fps = Fraction(rate['num'], rate['den'])
    sequences = project['sequences']
    if any(type(s['duration_tick']) is not int or s['duration_tick'] < 1 for s in sequences):
        raise error('CLOCK', '序列时长必须为正整数tick')
    if len({s['id'] for s in sequences}) != len(sequences):
        raise error('CLOCK', '序列ID不能重复')
    counts = {s['id']: math.ceil(Fraction(s['duration_tick'], tps) * fps) for s in sequences}
    if sum(counts.values()) > MAX_FRAMES:
        raise error('BUDGET', '绑定烘焙超过20000个序列显示帧；未开始像素读取', frames=sum(counts.values()))
    targets = {s['id'] + '/' + c['id']: c for s in sequences for t in s['tracks'] for c in t['clips']
               if c.get('tracking_binding')}
    samples = {path: [] for path in targets}
    hashes = {}; receipts = []; total = 0
    factory = context_factory or FloatRenderContext
    encoder = output_settings(project['settings'])
    for sequence in sequences:
        poll(); frames = []
        with factory(root, project, sequence, encoder, cancel_file=cancel_file) as context:
            host = context.timeline
            for index in range(host.frame_count):
                poll(); surface, _ = host.render_frame(index)
                frames.append(_surface_digest(surface))
                # Include nested instances and actual transition-peer reads.
                # Pinned ROI reference queries disappear with the binding and
                # must not become contradictory playback keyframe demands.
                for (path, at, left_limit, record), state in host.tracking.cache.items():
                    if not record or path not in samples: continue
                    total += 1
                    if total > MAX_SAMPLES:
                        raise error('BUDGET', '绑定烘焙超过256000个目标采样')
                    clip = targets[path]
                    _, tick, _ = host._source_time(clip, at * host.tps - clip['timeline_start_tick'],
                                                   path, left_limit=left_limit)
                    samples[path].append((tick, dict(state['values'])))
            context.finish_sources()
            receipts.append(dict(sequence_id=sequence['id'], phase='sample', frames=len(frames),
                providers_closed=context.metadata.get('providers_closed_before_publish', False),
                projection_acceleration=copy.deepcopy(context.metadata.get('projection_acceleration'))))
        hashes[sequence['id']] = frames
    result = copy.deepcopy(project); baked = []; unsampled = []
    for sequence in result['sequences']:
        for track in sequence['tracks']:
            for clip in track['clips']:
                path = sequence['id'] + '/' + clip['id']
                if path not in samples: continue
                plan = compile_samples(clip, samples[path])
                if plan is None: unsampled.append(path)
                else: apply_compiled_binding(clip, plan)
                clip.pop('tracking_binding')
                clip.pop('_tracking_binding_source', None); clip.pop('_tracking_binding_plan', None)
                baked.append(path)
    for sequence in result['sequences']:
        poll()
        with factory(root, result, sequence, encoder, cancel_file=cancel_file) as context:
            host = context.timeline
            if host.frame_count != len(hashes[sequence['id']]):
                raise error('VERIFY', '烘焙后序列帧数变化', sequence=sequence['id'])
            for index, digest in enumerate(hashes[sequence['id']]):
                poll(); surface, _ = host.render_frame(index)
                if _surface_digest(surface) != digest:
                    raise error('VERIFY', '烘焙后Float32 RGBA与原绑定工程不同；目标未导出', sequence=sequence['id'], frame=index)
            context.finish_sources()
            receipts.append(dict(sequence_id=sequence['id'], phase='verify', frames=host.frame_count,
                providers_closed=context.metadata.get('providers_closed_before_publish', False),
                projection_acceleration=copy.deepcopy(context.metadata.get('projection_acceleration'))))
    if original != _digest(project): raise error('INPUT_CHANGED', '烘焙期间作者工程发生变化')
    poll()
    return result, dict(protocol=PROTOCOL, source_project_sha256=original, baked_project_sha256=_digest(result),
        sequences=[dict(sequence_id=k, frames=v) for k, v in counts.items()],
        verified_frames=sum(counts.values()), samples=total, baked_paths=baked, unsampled_paths=unsampled,
        all_float32_frames_equal=True, integer_intermediate=False, model_inference=False, network=False,
        original_project_modified=False, external_renderer_verified=False, audio_modified=False,
        interpolation='hold at representable integer author ticks; exact value replay required',
        certification_scope='this frozen graph and display FPS; re-bake after clock/geometry/visibility edits',
        max_frames=MAX_FRAMES, max_samples=MAX_SAMPLES, receipts=receipts)
