"""Author crop/fit/TRS in one bounded, premultiplied Float32 projection.

The independent NumPy sampler retains crop-window texel edges until the final
parent canvas. A rotated fill can therefore reveal its original crop texture.
It performs no file I/O and never negotiates an integer intermediate surface.
"""
from dataclasses import dataclass
import json
import math

import numpy as np

from .animation import keyframe_value
from .errors import AppError

PROTOCOL = 'author-clock-float32-crop-projection-v1'
MAX_PIXELS = 16777216
MAX_DIMENSION = 16384
MAX_TILE_PIXELS = 262144
MAX_WORKING_BYTES = 768*1024**2
ALIASES = (('x',), ('y',), ('width', 'w'), ('height', 'h'))


def error(code, message):
    return AppError('FLOAT_CROP_'+code, message, exit_code=2)


def number(value, *, low=None, high=None):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise error('ARGUMENT', '裁剪参数须为有限数字')
    try:
        value = float(value)
    except (OverflowError, ValueError) as caught:
        raise error('ARGUMENT', '裁剪数字超出有限范围') from caught
    if not math.isfinite(value) or low is not None and value < low or high is not None and value > high:
        raise error('ARGUMENT', '裁剪数字超出声明范围')
    return value


def integer(value, low, high):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or not low <= value <= high:
        raise error('ARGUMENT', '裁剪尺寸或预算须为范围内整数')
    return int(value)


@dataclass(frozen=True)
class CropPlan:
    payload: str
    properties: frozenset[str]


def compile_crop(clip):
    crop = clip.get('crop')
    if crop is None:
        return None
    if not isinstance(crop, dict):
        raise error('ARGUMENT', 'crop须为对象')
    if set(crop)-{'unit', 'fit', 'mode', 'x', 'y', 'width', 'w', 'height', 'h', 'keyframes'}:
        raise error('ARGUMENT', 'crop包含未执行字段')
    unit = crop.get('unit', 'pixels')
    fit = crop.get('fit', crop.get('mode', 'fit'))
    if unit not in ('pixels', 'pixel', 'normalized', 'relative') or fit not in ('fit', 'fill', 'stretch'):
        raise error('ARGUMENT', '裁剪单位或fit模式无效')
    if 'mode' in crop and 'fit' in crop and crop['mode'] != crop['fit']:
        raise error('ARGUMENT', 'fit和mode声明冲突')
    normalized = unit in ('normalized', 'relative')
    fields = {}
    for aliases in ALIASES:
        values = [number(crop[n], low=0, high=1 if normalized else None) for n in aliases if n in crop]
        if len(set(values)) > 1:
            raise error('ARGUMENT', '裁剪尺寸别名冲突')
        fields[aliases[0]] = values[0] if values else (0 if aliases[0] in ('x', 'y') else None)
    properties, tracks = set(), []
    allowed = {'crop.'+v for aliases in ALIASES for v in aliases}
    for local, raw in ((False, clip.get('keyframes', [])), (True, crop.get('keyframes', []))):
        if not isinstance(raw, list) or len(raw) > 128:
            raise error('ARGUMENT', '裁剪关键帧轨道须为最多128项数组')
        seen = set()
        for track in raw:
            if not isinstance(track, dict) or not isinstance(track.get('property'), str):
                raise error('ARGUMENT', '关键帧轨道须有属性名')
            name = track['property']
            canonical = name if name.startswith('crop.') else 'crop.'+name
            if not local and not name.startswith('crop.'):
                continue
            if canonical not in allowed or canonical in seen:
                raise error('ARGUMENT', '裁剪关键帧属性未知或同层重复')
            seen.add(canonical)
            keys = track.get('keyframes')
            if set(track)-{'property', 'keyframes'} or not isinstance(keys, list) or not 1 <= len(keys) <= 1024:
                raise error('ARGUMENT', '裁剪关键帧须为1到1024项')
            previous = -1
            for key in keys:
                if not isinstance(key, dict) or set(key)-{'at_tick', 'value', 'interpolation', 'control_points'}:
                    raise error('ARGUMENT', '裁剪关键帧包含未知字段')
                at = key.get('at_tick')
                if type(at) is not int or at <= previous:
                    raise error('ARGUMENT', '裁剪关键帧须为递增非负整数时钟')
                previous = at
                value = number(key.get('value'), low=0, high=1 if normalized else None)
                if canonical in ('crop.width', 'crop.w', 'crop.height', 'crop.h') and value <= 0:
                    raise error('ARGUMENT', '裁剪宽高关键帧必须大于零')
                mode = key.get('interpolation', 'linear')
                if mode not in ('linear', 'hold', 'ease_in', 'ease_out', 'ease_in_out', 'bezier'):
                    raise error('ARGUMENT', '裁剪关键帧插值未知')
                if mode == 'bezier':
                    cp = key.get('control_points')
                    if not isinstance(cp, list) or len(cp) not in (2, 4):
                        raise error('ARGUMENT', 'Bezier须有2或4个控制值')
                    cp = [number(v) for v in cp]
                    if len(cp) == 4 and (not 0 <= cp[0] <= 1 or not 0 <= cp[2] <= 1):
                        raise error('ARGUMENT', 'Bezier横向控制值须在0到1')
            tracks.append({'property':canonical, 'keyframes':keys})
            if not local:
                properties.add(name)
    return CropPlan(json.dumps({'fields':fields, 'tracks':tracks, 'fit':fit, 'normalized':normalized,
        'nested':bool(clip.get('sequence_id'))}, sort_keys=True, allow_nan=False, separators=(',', ':')), frozenset(properties))


def resolve_crop(plan, source_size, author_tick):
    """Resolve only authored geometry, independently of pixel allocations."""
    if not isinstance(plan, CropPlan):
        raise error('ARGUMENT', '须使用编译的crop计划')
    if not isinstance(source_size, (list, tuple)) or len(source_size) != 2:
        raise error('ARGUMENT', '源尺寸须为宽高二元组')
    sw, sh = (integer(v, 1, MAX_DIMENSION) for v in source_size)
    if isinstance(author_tick, (bool, np.bool_)):
        raise error('ARGUMENT', '作者时钟不能为布尔值')
    try:
        tick = float(author_tick)
    except (ValueError, TypeError, OverflowError) as caught:
        raise error('ARGUMENT', '作者时钟须为有限数字') from caught
    if not math.isfinite(tick):
        raise error('ARGUMENT', '作者时钟须为有限数字')
    record = json.loads(plan.payload)
    tracks = {t['property']:t for t in record['tracks']}
    values = []
    for aliases, extent in zip(ALIASES, (sw, sh, sw, sh)):
        default = record['fields'][aliases[0]]
        if default is None:
            default = 1 if record['normalized'] else extent
        value = keyframe_value({'keyframes':record['tracks']}, tuple('crop.'+n for n in aliases), default, tick)
        if record['normalized']:
            value *= extent
        if not math.isfinite(value):
            raise error('ARGUMENT', '裁剪插值结果非有限')
        values.append(value)
    x, y, width, height = values
    dynamic_size = any(n in tracks for n in ('crop.width', 'crop.w', 'crop.height', 'crop.h'))
    if record['nested'] or dynamic_size:
        # Compound rasters retain continuous source units. Width/height tracks
        # use the existing fixed-canvas contract, including overshoot clamps.
        width, height = min(sw, max(2., width)), min(sh, max(2., height))
        x, y = min(sw-width, max(0., x)), min(sh-height, max(0., y))
        rounding = 'continuous-child-or-animated-size'
    else:
        # Static native leaf crop dimensions have Python ties-to-even rounding.
        # Position-only native crop expressions also use ties-to-even rounding
        # (verified against actual planar-float FFmpeg at half-pixel ties).
        static_x, static_y = record['fields']['x'], record['fields']['y']
        static_x = round(static_x*sw if record['normalized'] else static_x)
        static_y = round(static_y*sh if record['normalized'] else static_y)
        static_x, static_y = min(max(0, sw-2), max(0, static_x)), min(max(0, sh-2), max(0, static_y))
        width = min(sw, max(2, min(round(width), sw if 'crop.x' in tracks else max(2, sw-static_x))))
        height = min(sh, max(2, min(round(height), sh if 'crop.y' in tracks else max(2, sh-static_y))))
        x = round(min(sw-width, max(0., x))) if 'crop.x' in tracks else static_x
        y = round(min(sh-height, max(0., y))) if 'crop.y' in tracks else static_y
        rounding = 'leaf-fixed-size-ties-even-static-and-animated-origin'
    return {'window':[float(x), float(y), float(width), float(height)], 'fit':record['fit'],
        'author_tick':tick, 'rounding':rounding, 'nested':record['nested'], 'dynamic_size':dynamic_size}


def projection_geometry(plan, source_size, output_size, author_tick, *, scale=1,
                        rotation=0, position=(.5, .5), anchor=(.5, .5)):
    """The sampler's exact pure inverse, also used to project tracking anchors."""
    if not isinstance(source_size, (list, tuple)) or len(source_size) != 2:
        raise error('ARGUMENT', '源尺寸须为宽高二元组')
    if not isinstance(output_size, (list, tuple)) or len(output_size) != 2:
        raise error('ARGUMENT', '输出尺寸须为宽高二元组')
    sw, sh = (integer(v, 1, MAX_DIMENSION) for v in source_size)
    ow, oh = (integer(v, 1, MAX_DIMENSION) for v in output_size)
    scale, rotation = number(scale, low=0), number(rotation)
    if scale == 0 or not isinstance(position, (list, tuple)) or len(position) != 2 or not isinstance(anchor, (list, tuple)) or len(anchor) != 2:
        raise error('ARGUMENT', 'TRS须有正缩放和二维position/anchor')
    px, py = (number(v) for v in position)
    ax, ay = (number(v) for v in anchor)
    resolved = resolve_crop(plan, (sw, sh), author_tick)
    x, y, width, height = resolved['window']
    fx, fy = ow/width, oh/height
    if resolved['fit'] != 'stretch':
        fx = fy = (max if resolved['fit'] == 'fill' else min)(fx, fy)
    angle = math.radians(rotation)
    c, s = math.cos(angle), math.sin(angle)
    try:
        matrix = np.asarray([[c/(scale*fx), s/(scale*fx), 0], [-s/(scale*fy), c/(scale*fy), 0]], np.float64)
        matrix[0, 2] = x+ax*width-.5+matrix[0, 0]*(.5-px*ow)+matrix[0, 1]*(.5-py*oh)
        matrix[1, 2] = y+ay*height-.5+matrix[1, 0]*(.5-px*ow)+matrix[1, 1]*(.5-py*oh)
    except (OverflowError, ZeroDivisionError) as caught:
        raise error('ARGUMENT', '裁剪TRS超出有限逆映射范围') from caught
    if not np.isfinite(matrix).all() or np.max(np.abs(matrix)) > 1e9:
        raise error('ARGUMENT', '裁剪逆矩阵超出有限系数预算')
    return resolved, matrix


def project_crop(source, plan, author_tick, output_size, *, scale=1, rotation=0, position=(.5, .5),
                 anchor=(.5, .5), interpolation='bilinear', tile_pixels=65536,
                 max_working_bytes=MAX_WORKING_BYTES, cancel=None):
    """Project crop/fit and TRS together; return owned straight Float32 RGBA.

    Crop cell edges are half-open. Inside samples clamp to the crop's first and
    last centres, then bilinear taps clamp at the physical source edge. The
    source remains read-only, including cancellation and late invalid pixels.
    Transparent bars do not occlude lower tracks. This sampler is not an area
    filter and does not establish severe-minification or HDR/RSS acceptance.
    """
    if cancel is not None and not callable(cancel):
        raise error('ARGUMENT', '取消回调无效')
    poll = cancel if cancel is not None else lambda:None
    poll()
    if not isinstance(source, np.ndarray) or source.dtype != np.dtype('float32') or source.ndim != 3 or source.shape[-1] != 4 or not source.flags.c_contiguous:
        raise error('SURFACE', '输入须为连续H×W×4 Float32')
    sh, sw = source.shape[:2]
    integer(sw, 1, MAX_DIMENSION); integer(sh, 1, MAX_DIMENSION)
    if not isinstance(output_size, (tuple, list)) or len(output_size) != 2:
        raise error('ARGUMENT', '输出尺寸须为宽高二元组')
    ow, oh = (integer(v, 1, MAX_DIMENSION) for v in output_size)
    if sw*sh > MAX_PIXELS or ow*oh > MAX_PIXELS:
        raise error('BUDGET', '输入或输出超过像素预算')
    tile_pixels = integer(tile_pixels, 1, MAX_TILE_PIXELS)
    max_working_bytes = integer(max_working_bytes, 1, MAX_WORKING_BYTES)
    if interpolation not in ('nearest', 'bilinear'):
        raise error('ARGUMENT', '裁剪重采样只支持显式nearest或bilinear')
    resolved, matrix = projection_geometry(plan, (sw, sh), (ow, oh), author_tick,
        scale=scale, rotation=rotation, position=position, anchor=anchor)
    x, y, width, height = resolved['window']
    pixels, tile = ow*oh, min(ow*oh, tile_pixels)
    estimated = int(source.nbytes+pixels*16+max(tile, min(tile_pixels, sw*sh))*416+4096)
    if estimated > max_working_bytes:
        raise error('BUDGET', '裁剪输入、输出及分块估算超过工作区预算')
    flat = source.reshape(-1, 4)
    for start in range(0, len(flat), tile_pixels):
        poll()
        chunk = flat[start:start+tile_pixels]
        if not np.isfinite(chunk).all() or np.any(chunk[:, 3] < 0) or np.any(chunk[:, 3] > 1):
            raise error('SURFACE', 'RGB须有限且覆盖率须在0至1范围')
    output = np.empty((pixels, 4), np.float32)
    for start in range(0, pixels, tile):
        poll()
        indices = np.arange(start, min(pixels, start+tile), dtype=np.int64)
        dy, dx = np.divmod(indices, ow)
        sx = matrix[0, 0]*dx+matrix[0, 1]*dy+matrix[0, 2]
        sy = matrix[1, 0]*dx+matrix[1, 1]*dy+matrix[1, 2]
        inside = (sx >= x-.5) & (sx < x+width-.5) & (sy >= y-.5) & (sy < y+height-.5)
        sx, sy = np.clip(sx, x, x+width-1), np.clip(sy, y, y+height-1)
        if interpolation == 'nearest':
            ix, iy = np.floor(sx+.5).astype(np.int64), np.floor(sy+.5).astype(np.int64)
            values = source[np.clip(iy, 0, sh-1), np.clip(ix, 0, sw-1)].copy()
            values[~inside] = 0
            values[values[:, 3] == 0] = 0
        else:
            x0, y0 = np.floor(sx).astype(np.int64), np.floor(sy).astype(np.int64)
            tx, ty = sx-x0, sy-y0
            values = np.zeros((len(indices), 4), np.float64)
            for ox, oy, weight in ((0, 0, (1-tx)*(1-ty)), (1, 0, tx*(1-ty)), (0, 1, (1-tx)*ty), (1, 1, tx*ty)):
                sample = source[np.clip(y0+oy, 0, sh-1), np.clip(x0+ox, 0, sw-1)].astype(np.float64)
                sample[:, :3] *= sample[:, 3:4]
                values += sample*(weight*inside)[:, None]
            np.divide(values[:, :3], values[:, 3:4], out=values[:, :3], where=values[:, 3:4] > 0)
        output[start:start+len(indices)] = values
    poll()
    return output.reshape(oh, ow, 4), {
        'protocol':PROTOCOL, **resolved, 'inverse':matrix.tolist(), 'input_size':[sw, sh], 'output_size':[ow, oh],
        'surface':'straight-float32-RGBA', 'interpolation':interpolation, 'filtering_alpha':'premultiplied-RGB-and-alpha',
        'pixel_centres':'integer;half-pixel-cell-edges', 'outside':'transparent-black',
        'crop_border':'clamped-centres;physical-source-taps-clamped', 'projection_passes':1,
        'tile_pixels':tile, 'estimated_working_bytes':estimated, 'working_bytes_limit':max_working_bytes,
        'estimated_bytes_are_peak_RSS':False, 'integer_intermediate':False,
        'severe_minification_antialiasing_accepted':False, 'HDR_accepted':False, 'full_capcut_parity':False,
    }
