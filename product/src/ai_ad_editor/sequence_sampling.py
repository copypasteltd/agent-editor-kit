"""Explicit projection kernel and deterministic working-raster admission quota."""
from __future__ import annotations

import json
from typing import Any

from .errors import AppError

DEFAULT_WORKING_BYTES = 1024**3
MAX_WORKING_BYTES = 64*1024**3


def configuration(value: Any) -> dict[str, Any]:
    """Normalize absent defaults without modifying an authored settings object."""
    path = 'settings.sequence_sampling'
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value)-{'method','max_working_bytes'}:
        raise AppError('SEQUENCE_SAMPLING_INVALID', '序列采样必须为 method/max_working_bytes 对象或 null', exit_code=2, path=path)
    method = value.get('method', 'bilinear')
    budget = value.get('max_working_bytes', DEFAULT_WORKING_BYTES)
    if not isinstance(method, str) or method not in {'bilinear','area'}:
        raise AppError('SEQUENCE_SAMPLING_INVALID', '序列采样 method 只允许 bilinear 或 area', exit_code=2, path=path+'.method')
    if type(budget) is not int or not 1 <= budget <= MAX_WORKING_BYTES:
        raise AppError('SEQUENCE_SAMPLING_INVALID', '投影配额必须为 1 字节到 64 GiB 的整数', exit_code=2, path=path+'.max_working_bytes')
    return {'method':method, 'max_working_bytes':budget}


def projection_budget(groups: dict[str, dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    """Charge every reachable filter instance, independent of time overlap.

    This is an admission quota for projection buffers, not a process RSS bound.
    Leaf effects, decoders, encoders, threading and concurrent jobs are outside
    its scope. The component breakdown is deliberately persisted for review.
    """
    nodes = []
    for group in groups.values():
        source, parent = group['canvas'], group['parent_canvas']
        work = {k:max(source[k],parent[k]) for k in ('width','height')}
        source_pixels = source['width']*source['height']
        parent_pixels = parent['width']*parent['height']
        work_pixels = work['width']*work['height']
        components = {'source_rgba_buffers':source_pixels*8, 'parent_rgba_buffers':parent_pixels*16,
                      'working_float_and_byte_buffers':work_pixels*56,
                      'summed_area_double_planes':work_pixels*32 if config['method']=='area' else 0}
        nodes.append({'clip_id':group['id'], 'parent_id':group['parent_id'],
                      'source_canvas':dict(source), 'parent_canvas':dict(parent), 'working_canvas':work,
                      'components_bytes':components, 'estimated_working_bytes':sum(components.values())})
    result = {'kind':'sequence-projection-budget', **config, 'nodes':nodes,
              'estimated_working_bytes':sum(n['estimated_working_bytes'] for n in nodes),
              'scope':'reachable-sequence-projection-instances-only-not-process-rss',
              'time_disjoint_instances_charged':True, 'unused_sequences_charged':False}
    if result['estimated_working_bytes'] > config['max_working_bytes']:
        raise AppError('SEQUENCE_PROJECTION_BUDGET_EXCEEDED', '序列投影工作栅格超过显式配额', exit_code=2,
                       path='settings.sequence_sampling.max_working_bytes', cause=json.dumps(result,ensure_ascii=False),
                       hint='请显式调整画布、容器数量或 --sequence-memory-mib；系统不会降低分辨率或自行放宽配额')
    return result


def area_rectangle(name: str, *, left: str = 'ld(8)', right: str = 'ld(9)',
                   top: str = 'ld(2)', bottom: str = 'ld(3)',
                   width: str = 'ld(4)', height: str = 'ld(5)') -> str:
    """Integrate piecewise-constant premultiplied pixels over fractional edges.

    FFmpeg *sum() queries round coordinates to integers. Interpolate four
    integer prefixes at each continuous edge instead. Registers supplied by
    the caller: 8/9 = left/right, 2/3 = top/bottom, 4/5 = full kernel width/height.
    The rectangle is clipped to the crop but normalization includes transparency
    beyond it. Callers may supply read-only expressions instead of registers;
    this lets scanline constants survive pixel evaluation within ten registers.
    """
    def prefix(x: str, y: str) -> str:
        ix, iy = f'floor({x})', f'floor({y})'
        fx, fy = f'({x}-{ix})', f'({y}-{iy})'
        function = name+'sum'
        return (f'((1-{fx})*(1-{fy})*{function}({ix}-1,{iy}-1)'
                f'+{fx}*(1-{fy})*{function}({ix},{iy}-1)'
                f'+(1-{fx})*{fy}*{function}({ix}-1,{iy})'
                f'+{fx}*{fy}*{function}({ix},{iy}))')
    return (f"({prefix(right,bottom)}-{prefix(left,bottom)}"
            f"-{prefix(right,top)}+{prefix(left,top)})/({width}*{height})")
