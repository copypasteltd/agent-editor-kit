"""Bounded, linear-light, premultiplied Float32 video transitions.

The spatial formulae are adapted from FFmpeg n8.0 vf_xfade.c, copyright
(c) 2020 Paul B Mahol, LGPL-2.1-or-later. See float_transitions_NOTICE.txt
and COPYING.LGPLv2.1.txt. The surface/alpha, admission, cancellation and
author-clock integration are specific to agent editor kit.
"""
from __future__ import annotations
import math
import numpy as np
from .errors import AppError

PROTOCOL = 'linear-premultiplied-float32-transitions-v1'
TYPES = frozenset(('fade wipeleft wiperight wipeup wipedown slideleft slideright slideup slidedown '
    'circlecrop rectcrop distance fadeblack fadewhite radial smoothleft smoothright smoothup smoothdown '
    'circleopen circleclose horzopen horzclose vertopen vertclose diagtl diagtr diagbl diagbr '
    'hlslice hrslice vuslice vdslice pixelize zoomin fadefast fadeslow hlwind hrwind vuwind vdwind '
    'coverleft coverright coverup coverdown revealleft revealright revealup revealdown '
    'wipetl wipetr wipebl wipebr hblur fadegrays squeezeh squeezev dip_black dip_white').split())
MAX_WORKING_BYTES = 768 * 1024**2


def error(code, message):
    return AppError('FLOAT_TRANSITION_' + code, message, exit_code=2)


def resolve(config):
    if not isinstance(config, dict):
        raise error('CONFIG', '转场必须为显式对象')
    kind = str(config.get('source_type') or config.get('type', '')).lower().replace('-', '_')
    if kind in {'dissolve', 'crossfade', 'fade_in', 'fade_out'}:
        kind = 'fade'
    for prefix in ('wipe', 'slide'):
        if kind == prefix:
            direction = config.get('direction', 'left')
            if direction not in {'left', 'right', 'up', 'down'}:
                raise error('CONFIG', '转场 direction 必须为 left/right/up/down')
            kind += direction
        elif kind.startswith(prefix + '_'):
            kind = kind.replace('_', '')
    if kind not in TYPES:
        raise error('TYPE', '浮点转场类型尚未实现；未回退或替换为淡化')
    return kind


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0., 1.)
    return t * t * (3. - 2. * t)


def noise(x, y):
    # Pinned FFmpeg formula, evaluated explicitly in binary32. Its sinf is
    # platform dependent; no cross-libm / integer-xfade bit parity is claimed.
    r = np.sin(np.asarray(x, np.float32) * np.float32(12.9898)
               + np.asarray(y, np.float32) * np.float32(78.233)) * np.float32(43758.545)
    return (r - np.floor(r)).astype(np.float64)


def premultiply(value):
    value = value.astype(np.float64)
    value[:, :3] *= value[:, 3:4]
    return value


def mix(a, b, weight):
    return a * weight + b * (1. - weight)


def _tile(kind, a, b, x, y, w, h, p, cut_fraction, fetch, progress):
    """Return premultiplied binary64 samples. p is outgoing coverage."""
    def weighted(weight):
        return mix(a, b, np.asarray(weight).reshape(-1, 1))
    if kind == 'fade':
        return weighted(p)
    if kind in {'dip_black', 'dip_white'}:
        q = progress
        matte = np.array([1., 1., 1., 1.] if kind == 'dip_white' else [0., 0., 0., 1.])
        if q < cut_fraction:
            return mix(a, matte, 1. - q / cut_fraction)
        return mix(matte, b, (1. - q) / (1. - cut_fraction)) if cut_fraction < 1. else matte + np.zeros_like(a)
    if kind in {'fadeblack', 'fadewhite', 'fadegrays'}:
        if kind == 'fadegrays':
            ca, cb = a.copy(), b.copy()
            ca[:, :3] = a[:, :3].mean(axis=1, keepdims=True)
            cb[:, :3] = b[:, :3].mean(axis=1, keepdims=True)
        else:
            ca = cb = np.array([1., 1., 1., 1.] if kind == 'fadewhite' else [0., 0., 0., 1.])
        return mix(mix(a, ca, smooth(.8, 1., p)), mix(cb, b, smooth(.2, 1., p)), p)
    if kind in {'fadefast', 'fadeslow'}:
        delta = np.abs(a[:, :3] - b[:, :3])
        exponent = 1. + np.log(1. + delta if kind == 'fadefast' else 2. - delta)
        output = weighted(p)
        output[:, :3] = mix(a[:, :3], b[:, :3], p ** exponent)
        return output
    if kind == 'distance':
        choose_a = (np.linalg.norm(a - b, axis=1) <= p).reshape(-1, 1)
        return mix(np.where(choose_a, a, b), b, p)
    if kind.startswith('wipe'):
        if kind in {'wipeleft', 'wiperight', 'wipeup', 'wipedown'}:
            mask = {'wipeleft': x <= int(w*p), 'wiperight': x > int(w*(1-p)),
                    'wipeup': y <= int(h*p), 'wipedown': y > int(h*(1-p))}[kind]
        else:
            mask = ((y <= int(h*p)) if kind in {'wipetl', 'wipetr'} else (y > int(h*(1-p))))
            mask &= ((x <= int(w*p)) if kind in {'wipetl', 'wipebl'} else (x > int(w*(1-p))))
        return np.where(mask[:, None], a, b)
    if kind.startswith(('slide', 'cover', 'reveal')):
        horizontal = kind.endswith(('left', 'right'))
        axis, length = (x, w) if horizontal else (y, h)
        shift = int((-p if kind.endswith(('left', 'up')) else p) * length)
        moving = axis + shift
        xx, yy = (moving % w, y) if horizontal else (x, moving % h)
        inside = ((moving >= 0) & (moving < length))[:, None]
        if kind.startswith('slide'):
            return np.where(inside, fetch(1, xx, yy), fetch(0, xx, yy))
        if kind.startswith('cover'):
            return np.where(inside, fetch(1, xx, yy), a)
        return np.where(inside, b, fetch(0, xx, yy))
    if kind in {'circlecrop', 'rectcrop'}:
        if kind == 'circlecrop':
            radius = (2*abs(p-.5))**3 * math.hypot(w//2, h//2)
            inside = np.hypot(x-w//2, y-h//2) <= radius
        else:
            inside = (np.abs(x-w//2) < int(abs(p-.5)*w)) & (np.abs(y-h//2) < int(abs(p-.5)*h))
        return np.where(inside[:, None], a if p >= .5 else b, [0., 0., 0., 1.])
    if kind == 'radial':
        s = np.arctan2(x-w//2, y-h//2) - (p-.5)*(math.pi*2.5)
        return weighted(1.-smooth(0., 1., s))
    if kind.startswith('smooth'):
        t = {'smoothleft': x/w, 'smoothright': (w-1-x)/w,
             'smoothup': y/h, 'smoothdown': (h-1-y)/h}[kind]
        return weighted(1.-smooth(0., 1., 1.+t-2*p))
    if kind in {'circleopen', 'circleclose'}:
        diagonal = math.hypot(w//2, h//2)
        distance = np.hypot(x-w//2, y-h//2) / (diagonal or 1.)
        s = distance + ((p if kind == 'circleopen' else 1.-p)-.5)*3.
        weight = smooth(0., 1., s)
        return weighted(weight if kind == 'circleopen' else 1.-weight)
    if kind in {'vertopen', 'vertclose', 'horzopen', 'horzclose'}:
        position = np.abs((x-w/2)/(w/2)) if kind.startswith('vert') else np.abs((y-h/2)/(h/2))
        s = 2.-position-2*p if kind.endswith('open') else 1.+position-2*p
        return weighted(1.-smooth(0., 1., s))
    if kind.startswith('diag'):
        tx = x if kind in {'diagtl', 'diagbl'} else w-1-x
        ty = y if kind in {'diagtl', 'diagtr'} else h-1-y
        return weighted(1.-smooth(0., 1., 1.+tx/w*ty/h-2*p))
    if kind.endswith('slice'):
        t = {'hlslice': x/w, 'hrslice': (w-1-x)/w, 'vuslice': y/h, 'vdslice': (h-1-y)/h}[kind]
        s = smooth(-.5, 0., t-1.5*p)
        return weighted((s <= (10*t-np.floor(10*t))).astype(np.float64))
    if kind.endswith('wind'):
        if kind in {'hlwind', 'hrwind'}:
            f = 1.-x/w if kind == 'hlwind' else x/w
            r = noise(np.zeros_like(y), y)
        else:
            f = 1.-y/h if kind == 'vuwind' else y/h
            r = noise(x, np.zeros_like(x))
        return weighted(1.-smooth(0., -.2, f*.8+.2*r-(1.-p)*1.2))
    if kind == 'pixelize':
        distance = math.ceil(min(p, 1.-p)*50)/50
        size = 2*distance*min(w, h)/20
        xx = np.minimum((np.floor(x/size)+.5)*size, w-1).astype(np.int64)
        yy = np.minimum((np.floor(y/size)+.5)*size, h-1).astype(np.int64)
        return mix(fetch(0, xx, yy), fetch(1, xx, yy), p)
    if kind in {'squeezeh', 'squeezev'}:
        z = .5+((y/h if kind == 'squeezeh' else x/w)-.5)/p
        inside = (z >= 0.) & (z <= 1.)
        coordinate = np.rint(np.clip(z, 0., 1.)*((h if kind == 'squeezeh' else w)-1)).astype(np.int64)
        xx, yy = (x, coordinate) if kind == 'squeezeh' else (coordinate, y)
        return np.where(inside[:, None], fetch(0, xx, yy), b)
    if kind == 'zoomin':
        zoom = smooth(.5, 1., p)
        xx = np.ceil((.5+(x/w-.5)*zoom)*(w-1)).astype(np.int64)
        yy = np.ceil((.5+(y/h-.5)*zoom)*(h-1)).astype(np.int64)
        return mix(fetch(0, xx, yy), b, smooth(0., .5, p))
    raise error('TYPE', '转场分块未实现')


def transition_rgba(outgoing, incoming, progress, *, config=None, kind='fade', cut_fraction=.5,
                    tile_pixels=16384, max_working_bytes=MAX_WORKING_BYTES, cancel=None):
    """Mix complete matched linear RGB surfaces; never change either input.

    Progress runs from outgoing=0 to incoming=1. Exact endpoints are owned
    copies with zero-alpha hidden RGB cleared. Colour-dependent fast/slow
    require visible RGB 0..1; other patterns retain finite extended RGB.
    The memory quota is an allocation estimate, not total process RSS.
    """
    kind = resolve(config if config is not None else {'type': kind})
    if cancel is not None and not callable(cancel):
        raise error('ARGUMENT', '取消回调无效')
    poll = cancel if cancel is not None else lambda: None
    poll()
    for value in (outgoing, incoming):
        if not isinstance(value, np.ndarray) or value.dtype != np.float32 or value.ndim != 3 or value.shape[-1] != 4 or not value.flags.c_contiguous:
            raise error('SURFACE', '转场输入必须为连续 H×W×4 Float32')
    if outgoing.shape != incoming.shape:
        raise error('SURFACE', '转场输入画布必须完全一致')
    h, w = outgoing.shape[:2]
    pixels = w*h
    if min(w, h) < 1 or max(w, h) > 16384 or pixels > 16777216:
        raise error('BUDGET', '转场画布超限')
    for value in (progress, cut_fraction):
        if isinstance(value, (bool, np.bool_)):
            raise error('PROGRESS', '转场进度和剪口比例必须为有限 0..1 数值')
        try:
            valid = math.isfinite(value) and 0 <= value <= 1
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            raise error('PROGRESS', '转场进度和剪口比例必须为有限 0..1 数值')
    progress, cut_fraction = float(progress), float(cut_fraction)
    if type(tile_pixels) is not int or not 1 <= tile_pixels <= 262144 or type(max_working_bytes) is not int or not 1 <= max_working_bytes <= MAX_WORKING_BYTES:
        raise error('BUDGET', '转场分块或工作区配额无效')
    line_scratch = max(1048576, (w+1)*512) if kind == 'hblur' else 1048576
    fixed = 3*outgoing.nbytes + line_scratch
    capacity = (max_working_bytes-fixed)//2048
    if capacity < 1:
        raise error('BUDGET', '两输入、输出和最小转场工作区估算超限')
    tile_pixels = min(tile_pixels, pixels, capacity)
    flat = (outgoing.reshape(-1, 4), incoming.reshape(-1, 4))
    # Validate all pixels, including samples not selected by the current wipe.
    for value in flat:
        for start in range(0, pixels, tile_pixels):
            poll()
            tile = value[start:start+tile_pixels]
            if not np.isfinite(tile).all() or np.any(tile[:, 3] < 0) or np.any(tile[:, 3] > 1):
                raise error('VALUES', '转场 RGB 必须有限，alpha 必须为 0..1')
            if kind in {'fadefast', 'fadeslow'}:
                visible = tile[tile[:, 3] > 0, :3]
                if np.any(visible < 0) or np.any(visible > 1):
                    raise error('DOMAIN', 'fadefast/fadeslow 要求可见线性 RGB 为 0..1；不隐式截断')
    result = np.empty_like(flat[0])
    p = 1.-progress
    def fetch(which, x, y):
        return premultiply(flat[which][y*w+x])
    blur_row = None
    def forward_blur(row, size):
        values = premultiply(row)
        sums = np.empty((w+1, 4), np.float64)
        sums[0] = 0.
        np.cumsum(values, axis=0, dtype=np.float64, out=sums[1:])
        x = np.arange(w)
        end = np.minimum(w, x+size)
        return (sums[end]-sums[x])/(end-x)[:, None]
    for start in range(0, pixels, tile_pixels):
        poll()
        end = min(pixels, start+tile_pixels)
        if progress in (0., 1.):
            values = flat[int(progress)][start:end].copy()
            values[values[:, 3] == 0., :3] = 0.
            result[start:end] = values
            continue
        indices = np.arange(start, end, dtype=np.int64)
        y, x = np.divmod(indices, w)
        a, b = premultiply(flat[0][start:end]), premultiply(flat[1][start:end])
        if kind == 'hblur':
            values = np.empty_like(a)
            size = 1+int((w//2)*2*min(p, 1.-p))
            for row in np.unique(y):
                poll()
                if blur_row is None or blur_row[0] != row:
                    first, last = int(row)*w, (int(row)+1)*w
                    blur_row = (row, mix(forward_blur(flat[0][first:last], size), forward_blur(flat[1][first:last], size), p))
                selected = y == row
                values[selected] = blur_row[1][x[selected]]
        else:
            values = _tile(kind, a, b, x, y, w, h, p, cut_fraction, fetch, progress)
        alpha = np.clip(values[:, 3:4], 0., 1.)
        rgb = np.divide(values[:, :3], alpha, out=np.zeros_like(values[:, :3]), where=alpha > 0.)
        result[start:end, :3] = rgb
        result[start:end, 3:4] = alpha
        if not np.isfinite(result[start:end]).all():
            raise error('VALUES', '转场结果超过 Float32 有限范围')
    poll()
    return result.reshape(h, w, 4), {'protocol': PROTOCOL, 'type': kind, 'progress': progress,
        'cut_fraction': cut_fraction, 'alpha': 'linear-light premultiplied mix;public straight RGBA;zero-alpha RGB cleared',
        'arithmetic': 'Float64 tiles;Float32 public boundary;wind hash explicitly Float32',
        'RGB_domain': 'visible-normalized-0..1' if kind in {'fadefast', 'fadeslow'} else 'finite extended RGB',
        'endpoints': 'exact outgoing/incoming;hidden RGB canonicalized', 'tile_pixels': tile_pixels,
        'estimated_working_bytes': fixed+tile_pixels*2048, 'estimated_bytes_are_peak_RSS': False,
        'GPU': False, 'integer_xfade_bit_parity': False, 'HDR_delivery_accepted': False}
