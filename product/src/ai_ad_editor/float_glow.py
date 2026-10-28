"""Highlight-derived bloom/halation with bounded, separable Float32 FIR stages.

Original MIT implementation. These artistic light-spread operators use actual
image highlights; they do not claim a physical lens or film-stock simulation.
"""
from dataclasses import dataclass
import math

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal, _rgb_to_xyz
from .float_numeric_automation import number, compile_tracks, sample_tracks, raw_tracks, validate_duration
from .float_spatial_budget import admit_spatial, MAX_WORKING_BYTES

PROTOCOL = 'highlight-derived-separable-float32-glow-v1'
ALIASES = {'bloom': 'bloom', 'highlight_bloom': 'bloom',
           'halation': 'halation', 'film_halation': 'halation'}
COMMON = {'intensity': (1., 0., 1.), 'threshold': (.7, 0., 16.), 'knee': (.2, 0., 4.),
          'radius': (12., 0., 32.), 'gain': (1., 0., 8.)}
SPECS = {
    'bloom': {**COMMON, 'red': (1., 0., 4.), 'green': (1., 0., 4.), 'blue': (1., 0., 4.)},
    'halation': {**COMMON, 'radius': (6., 0., 32.), 'red': (1., 0., 4.),
                 'green': (.2, 0., 4.), 'blue': (.05, 0., 4.), 'core_suppression': (1., 0., 1.)},
}
MAX_NEIGHBOR_SAMPLES = 2**32


def error(kind, message, **details):
    return AppError('FLOAT_GLOW_' + kind, message, exit_code=2, diagnostics=details or None)


def bounds(kind):
    return {k: (v[1], v[2]) for k, v in SPECS[kind].items()}


def parameter_names(name):
    return frozenset(SPECS[ALIASES[name]])


@dataclass(frozen=True)
class GlowPlan:
    effect_type: str
    values: tuple
    tracks_json: str
    edge: str


def validate_state(kind, values, edge):
    if not isinstance(kind, str) or kind not in SPECS or not isinstance(values, dict) or values.keys() != SPECS[kind].keys():
        raise error('ARGUMENT', '高光扩散类型或数值通道无效')
    if edge not in ('clamp', 'transparent'):
        raise error('ARGUMENT', '高光扩散边界须为clamp或transparent')
    return {k: number(v, *bounds(kind)[k]) for k, v in values.items()}


def compile_glow(effect):
    if not isinstance(effect, dict) or set(effect) - {'id', 'type', 'enabled', 'parameters', 'keyframes'}:
        raise error('ARGUMENT', '高光扩散含未知字段；参数须置于parameters')
    name = str(effect.get('type', '')).strip().lower().replace('-', '_')
    if name not in ALIASES or type(effect.get('enabled', True)) is not bool:
        raise error('ARGUMENT', '高光扩散类型或enabled无效')
    kind = ALIASES[name]
    p = effect.get('parameters', {})
    if not isinstance(p, dict) or set(p) - (set(SPECS[kind]) | {'edge', 'keyframes'}):
        raise error('ARGUMENT', '高光扩散参数未知')
    edge = p.get('edge', 'transparent')
    values = validate_state(kind, {k: p.get(k, v[0]) for k, v in SPECS[kind].items()}, edge)
    tracks = compile_tracks(raw_tracks(effect, p), bounds(kind), {}, name)
    return GlowPlan(kind, tuple(sorted(values.items())), tracks, edge)


def state_at(plan, tick):
    if not isinstance(plan, GlowPlan) or not isinstance(plan.values, tuple):
        raise error('ARGUMENT', '高光扩散须为不可变编译计划')
    if any(not isinstance(row, tuple) or len(row) != 2 or not isinstance(row[0], str) for row in plan.values):
        raise error('ARGUMENT', '高光扩散计划通道无效')
    values = dict(plan.values)
    if len(values) != len(plan.values):
        raise error('ARGUMENT', '高光扩散计划通道重复')
    values = validate_state(plan.effect_type, values, plan.edge)
    values.update(sample_tracks(plan.tracks_json, bounds(plan.effect_type), {}, plan.effect_type, tick))
    return validate_state(plan.effect_type, values, plan.edge)


def validate_glow(effect, *, duration_tick=None):
    if effect.get('enabled', True) is False:
        return []
    try:
        plan = compile_glow(effect)
        validate_duration(plan.tracks_json, duration_tick)
    except AppError as exc:
        return [{'code': exc.code, 'message': str(exc), 'suffix': '.parameters'}]
    return []


def luma_coefficients(primaries,white_xy=None):
    ColorSignal(primaries, 'linear')
    if white_xy is not None:
        from .float_chromatic import validate_RGB_white
        validate_RGB_white(primaries,white_xy)
    return tuple(float(v) for v in _rgb_to_xyz(primaries,white_xy)[1])


def kernel(radius):
    """Three-sigma truncation; normalized finite support, also at sigma zero."""
    radius = number(radius, 0., 32.)
    support = math.ceil(3 * radius)
    weights = [math.exp((-.5 * (i / radius)) * (i / radius)) for i in range(-support, support + 1)] if support else [1.]
    return support, tuple(weights), sum(weights)


def admit_neighborhood(pixels, radius):
    if type(pixels) is not int or pixels < 1:
        raise error('BUDGET', '邻域像素数无效')
    support, weights, norm = kernel(radius)
    visits = pixels * len(weights) * 2
    if visits > MAX_NEIGHBOR_SAMPLES:
        raise error('BUDGET', '分离卷积邻域访问超过单帧预算', neighbor_samples=visits, limit=MAX_NEIGHBOR_SAMPLES)
    return support, weights, norm, visits


def highlight(values, v, coefficients):
    rgb = np.maximum(values[:, :3].astype(np.float64), 0.)
    luminance = (rgb[:, 0] * coefficients[0] + rgb[:, 1] * coefficients[1]) + rgb[:, 2] * coefficients[2]
    contribution = np.maximum(luminance - v['threshold'], 0.)
    if v['knee']:
        soft = np.clip(luminance - v['threshold'] + v['knee'], 0., 2 * v['knee'])
        contribution = np.maximum(contribution, soft * soft / (4 * v['knee']))
    contribution = np.minimum(contribution, luminance)
    gate = np.divide(contribution, luminance, out=np.zeros_like(luminance), where=luminance > 0)
    return rgb * (gate * values[:, 3].astype(np.float64))[:, None]


def _blur_axis(source, weights, norm, axis, edge, tile, poll):
    h, w = source.shape[:2]
    flat = source.reshape(-1, 4)
    output = np.empty_like(source)
    dest = output.reshape(-1, 4)
    support = len(weights) // 2
    for start in range(0, h * w, tile):
        poll()
        index = np.arange(start, min(start + tile, h * w), dtype=np.int64)
        x, y = index % w, index // w
        total = np.zeros((len(index), 4), np.float64)
        for offset, weight in zip(range(-support, support + 1), weights):
            poll()
            xx, yy = (x + offset, y) if axis == 1 else (x, y + offset)
            sample = flat[np.clip(yy, 0, h - 1) * w + np.clip(xx, 0, w - 1)].astype(np.float64)
            if edge == 'transparent':
                sample[(xx < 0) | (xx >= w) | (yy < 0) | (yy >= h)] = 0
            total += sample * weight
        dest[start:start + len(index)] = total / norm
    return output


def apply_glow(surface, plan, author_tick, *, working_signal, retained_table_bytes=0,
               max_working_bytes=MAX_WORKING_BYTES, tile_pixels=16384, cancel=None, gpu=None):
    if cancel is not None and not callable(cancel):
        raise error('ARGUMENT', '取消回调须可调用')
    def poll():
        if cancel and cancel():
            raise AppError('RENDER_CANCELLED', '高光扩散已取消', exit_code=6)
    poll()
    values = state_at(plan, author_tick)
    if not isinstance(working_signal, ColorSignal) or working_signal.transfer != 'linear':
        raise error('SIGNAL', '高光扩散要求明确线性RGB工作域')
    if not isinstance(surface, np.ndarray) or surface.dtype != np.float32 or surface.ndim != 3 or surface.shape[-1] != 4 or not surface.flags.c_contiguous:
        raise error('SURFACE', '高光扩散输入须为连续H×W×4 Float32')
    h, w = surface.shape[:2]
    pixels = h * w
    if min(h, w) < 1 or max(h, w) > 16384 or pixels > 16777216:
        raise error('BUDGET', '高光扩散表面超过尺寸预算')
    tile, estimate, admission = admit_spatial(surface_bytes=int(surface.nbytes), pixels=pixels,
        tile_pixels=tile_pixels, tracks_bytes=len(plan.tracks_json.encode('utf8')),
        retained_table_bytes=retained_table_bytes, max_working_bytes=max_working_bytes, error=error)
    support, weights, norm, visits = admit_neighborhood(pixels, values['radius'])
    source = surface.reshape(-1, 4)
    for start in range(0, pixels, tile):
        poll()
        part = source[start:start + tile]
        if not np.isfinite(part).all() or np.any(part[:, 3] < 0) or np.any(part[:, 3] > 1):
            raise error('VALUES', 'RGB须有限且alpha须为0..1')
    active = bool(values['intensity'] and values['gain'] and any(values[c] for c in ('red', 'green', 'blue')))
    if plan.effect_type == 'halation' and values['radius'] == 0 and values['core_suppression'] == 1:
        active = False
    used_gpu = bool(active and gpu is not None and gpu.active)
    white_xy=getattr(working_signal,'white_xy',None)
    coefficients = luma_coefficients(working_signal.primaries,white_xy)
    if not active:
        result = surface.copy()
    elif used_gpu:
        result = gpu.glow(surface, plan.effect_type, values, plan.edge, working_signal.primaries,
                          **({'white_xy':list(white_xy)} if white_xy is not None else {}))
    else:
        bright = np.zeros_like(surface)
        flat = bright.reshape(-1, 4)
        for start in range(0, pixels, tile):
            poll()
            flat[start:start + tile, :3] = highlight(source[start:start + tile], values, coefficients)
        horizontal = _blur_axis(bright, weights, norm, 1, plan.edge, tile, poll)
        del flat, bright
        blurred = _blur_axis(horizontal, weights, norm, 0, plan.edge, tile, poll)
        del horizontal
        result = np.empty_like(surface)
        dest, spread = result.reshape(-1, 4), blurred.reshape(-1, 4)
        tint = np.array([values[c] for c in ('red', 'green', 'blue')], np.float64)
        for start in range(0, pixels, tile):
            poll()
            part = source[start:start + tile]
            light = spread[start:start + tile, :3].astype(np.float64)
            if plan.effect_type == 'halation':
                # Recompute the same Float32 bright-pass boundary used by both backends.
                core = highlight(part, values, coefficients).astype(np.float32).astype(np.float64)
                light = np.maximum(light - values['core_suppression'] * core, 0.)
            target = dest[start:start + len(part)]
            with np.errstate(over='ignore', invalid='ignore'):
                target[:, :3] = part[:, :3].astype(np.float64) + (light * tint) * (values['intensity'] * values['gain'])
            target[:, 3] = part[:, 3]
            target[part[:, 3] == 0, :3] = 0
    poll()
    for start in range(0, pixels, tile):
        if not np.isfinite(result.reshape(-1, 4)[start:start + tile]).all():
            raise error('OVERFLOW', '高光扩散产生非有限Float32像素')
    return result, dict(protocol=PROTOCOL, effect_type=plan.effect_type, author_tick=str(author_tick),
        parameters=values, edge=plan.edge, alpha='input-bits-preserved', zero_alpha_RGB='zero-when-active',
        bright_pass='coverage-weighted-positive-linear-RGB;declared-working-white-luminance;soft-knee',
        luma_coefficients=list(coefficients), working_primaries=working_signal.primaries,
        kernel='normalized-three-sigma-separable-Gaussian-FIR', sigma_source_pixels=values['radius'],
        support_radius_pixels=support, taps_per_axis=len(weights), planned_neighbor_samples=visits,
        neighbor_samples_limit=MAX_NEIGHBOR_SAMPLES, stage_boundaries='Float32-bright-horizontal-vertical-merge',
        active=active, GPU=used_gpu, GPU_kernels_per_active_operation=4 if used_gpu else 0,
        backend='OpenCL' if used_gpu else 'CPU', integer_intermediate=False,
        physical_film_accepted=False, natural_quality_accepted=False, HDR_accepted=False,
        estimated_working_bytes=estimate, **admission)
