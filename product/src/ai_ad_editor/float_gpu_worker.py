"""Finite render-owned Windows worker. Only named shared buffers carry pixels."""
from __future__ import annotations

from contextlib import ExitStack
import json
import math
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
import re
import sys

import numpy as np

from .errors import AppError
from .float_gpu_native import NativeGPU, error
from .float_gpu_control import PROTOCOL as CONTROL_PROTOCOL, MAX_CONTROL, encode_packet, read_packet, write_packet
from .utils import read_json_snapshot

PROTOCOL = 'owned-float32-opencl-worker-v1'


def read(path):
    value = read_json_snapshot(path, MAX_CONTROL)
    if not isinstance(value, dict):
        raise error('PROTOCOL', 'GPU控制消息必须为对象')
    return value


def execute(gpu, request, nonce):
    op = request.get('op')
    if op not in {'over', 'affine', 'paint', 'select', 'particles','optics'}:
        raise error('PROTOCOL', 'GPU操作未登记')
    specs = request.get('buffers')
    if not isinstance(specs, list) or len(specs) != 3:
        raise error('PROTOCOL', 'GPU共享缓冲区必须有三个')
    with ExitStack() as stack:
        arrays, memories = [], []
        try:
            for i, spec in enumerate(specs):
                if (not isinstance(spec, dict) or set(spec) != {'name', 'shape', 'dtype'}
                        or not isinstance(spec['name'], str)
                        or not re.fullmatch('aekfg'+nonce+'_'+str(i)+r'_\d+', spec['name'])):
                    raise error('PROTOCOL', '共享缓冲区不属于本任务')
                shape, dtype = spec['shape'], spec['dtype']
                if (dtype not in ('float32', 'uint8') or not isinstance(shape, list)
                        or not 1 <= len(shape) <= 3 or any(type(x) is not int or not 1 <= x <= 67108864 for x in shape)):
                    raise error('PROTOCOL', '共享缓冲区形状无效')
                size = math.prod(shape)*np.dtype(dtype).itemsize
                if not 1 <= size <= 536870912:
                    raise error('BUDGET', '共享缓冲区超过512MiB')
                memory = SharedMemory(name=spec['name'], create=False)
                stack.callback(memory.close)
                memories.append(memory)
                if sum(m.size for m in memories) > gpu.limit:
                    raise error('BUDGET', '共享缓冲区超过主机配额')
                if size > memory.size:
                    raise error('PROTOCOL', '共享缓冲区短于声明形状')
                arrays.append(np.ndarray(shape, dtype=dtype, buffer=memory.buf))
            a, b, c = arrays
            output_shape = request.get('output_shape')
            if (not isinstance(output_shape, list) or len(output_shape) != 3 or output_shape[-1] != 4
                    or any(type(v) is not int or not 1 <= v <= 16384 for v in output_shape[:2])
                    or output_shape[0]*output_shape[1] > 16777216):
                raise error('PROTOCOL', 'GPU输出形状无效')
            needed = output_shape[0]*output_shape[1]*16
            if needed > memories[0].size:
                raise error('PROTOCOL', 'GPU输出共享区不足')
            output = np.ndarray(output_shape, dtype=np.float32, buffer=memories[0].buf)
            if op == 'over': gpu.over(a, b, output, request['opacity'], text_order=request.get('text_order', False))
            elif op == 'affine': gpu.affine(b, output, request['inverse'], request['nearest'])
            elif op == 'paint': gpu.paint(b, request['colors'], output, base=a if a.dtype == np.float32 and a.ndim == 3 else None)
            elif op == 'select': gpu.select(a, b, c, output)
            elif op == 'particles': gpu.particles(b, c, output)
            else: gpu.optics(b,output,request['kind'],request['parameters'],request['ghosts'],request['edge'])
            gpu.surface(output)
        finally:
            arrays.clear()
            a = b = c = output = None


def probe(gpu):
    # Independent CPU oracle: native 16-bit levels, subpixel geometry, extended
    # RGB, coverage and word selection. Probe pixels never enter the project.
    from .float_composite import composite_rgba
    from .float_geometry import resample_rgba
    levels = np.arange(65536, dtype=np.float32).reshape(256, 256)/np.float32(65535)
    a = np.stack([levels, 1-levels, levels*2-0.3, levels], axis=-1)
    b = np.ascontiguousarray(a[::-1]); out = np.empty_like(a)
    gpu.over(a, b, out, 0.63)
    ref, _ = composite_rgba(a, b, opacity=0.63)
    errors = {'over': float(np.max(np.abs(ref-out)))}
    inverse = [[0.91, 0.11, -0.25], [-0.08, 1.03, 0.4]]
    gpu.affine(a, out, inverse)
    ref, _ = resample_rgba(a, (256, 256), inverse)
    errors['affine'] = float(np.max(np.abs(ref-out)))
    masks = np.stack([np.arange(65536, dtype=np.uint16).reshape(256, 256).astype(np.uint8),
                      np.full((256, 256), 127, np.uint8)])
    colors = [[0.123456789, 0.8, -0.1, 0.37], [1.2, 0.2, 0.4, 0.81]]
    gpu.paint(masks, colors, out)
    ref = np.zeros_like(a)
    for mask, color in zip(masks, colors):
        alpha = mask.astype(np.float64)[:, :, None]*(color[3]/255)
        previous = ref.astype(np.float64)
        total = alpha+previous[:, :, 3:4]*(1-alpha)
        numerator = np.asarray(color[:3])*alpha+previous[:, :, :3]*previous[:, :, 3:4]*(1-alpha)
        ref[:, :, :3] = np.divide(numerator, total, out=np.zeros_like(numerator), where=total > 0)
        ref[:, :, 3:4] = total
    errors['paint'] = float(np.max(np.abs(ref-out)))
    selection = np.where(masks[0] % 2, 255, 0).astype(np.uint8)
    gpu.select(a, b, selection, out)
    errors['select'] = float(np.max(np.abs(np.where(selection[:, :, None] != 0, b, a)-out)))
    bits = np.array([0, 1, 2, 0x007fffff, 0x00800000, 0x00800001, 0x3f7fffff, 0x3f800000], np.uint32)
    tiny = np.empty((1, len(bits), 4), np.float32)
    tiny[:, :, :3] = [.12345678, -.333333, 1.234567]; tiny[:, :, 3] = bits.view(np.float32)
    tiny_out = np.empty_like(tiny)
    gpu.over(np.zeros_like(tiny), tiny, tiny_out)
    tiny_ref, _ = composite_rgba(np.zeros_like(tiny), tiny)
    tiny_over_exact = bool(np.array_equal(tiny_out, tiny_ref))
    gpu.affine(tiny, tiny_out, [[1, 0, 0], [0, 1, 0]])
    tiny_ref, _ = resample_rgba(tiny, (len(bits), 1), [[1, 0, 0], [0, 1, 0]])
    tiny_affine_exact = bool(np.array_equal(tiny_out, tiny_ref))
    if not tiny_over_exact or not tiny_affine_exact:
        raise error('PRECISION', 'GPU未保留Float32次正规alpha与颜色', over_exact=tiny_over_exact, affine_exact=tiny_affine_exact)
    # Affine/alpha math tolerance is below one Float32 display code; ordinary
    # source-over, paint and binary selection should normally be bit identical.
    if any(value > 3e-7 for value in errors.values()):
        raise error('PRECISION', 'GPU独立精度探测未通过', max_errors=errors)
    from .float_optics import SPECS,compile_optics,state_at,apply_optics
    from .float_color_signal import ColorSignal
    optical_errors={};optical=np.ascontiguousarray(a[:11,:13]);optical_out=np.empty_like(optical)
    for kind in SPECS:
        plan=compile_optics({'type':kind});values=state_at(plan,0)
        reference,_=apply_optics(optical,plan,0,working_signal=ColorSignal('bt709','linear'))
        gpu.optics(optical,optical_out,kind,values,plan.ghosts,plan.edge)
        optical_errors[kind]=float(np.max(np.abs(reference-optical_out)))
    if any(v>3e-6 for v in optical_errors.values()):
        raise error('PRECISION','GPU光学精度探测未通过',max_errors=optical_errors)
    return {'pixels_per_case': 65536, 'max_errors': errors, 'absolute_limit': 3e-7,
            'all_16bit_levels_present': True, 'actual_gpu_operations': 9,
            'optical_max_errors':optical_errors,'optical_absolute_limit':3e-6,'optical_gpu_operations':3,
            'subnormal_over_bit_exact': tiny_over_exact, 'subnormal_affine_bit_exact': tiny_affine_exact,
            'subnormal_alpha_input_bits': bits.tolist()}


def main():
    root = Path(sys.argv[1]).resolve()
    config = read(root/'init.json')
    nonce = config.get('nonce')
    if not isinstance(nonce, str) or not re.fullmatch('[0-9a-f]{32}', nonce):
        raise error('PROTOCOL', 'GPU工作区标识无效')
    if config.get('control_protocol') != CONTROL_PROTOCOL:
        raise error('PROTOCOL', 'GPU工作进程需要任务自有管道协议')
    def respond(value): write_packet(sys.stdout.buffer, encode_packet(value))
    sequence = 0
    try:
        with NativeGPU(config['device'], config['max_device_bytes']) as gpu:
            evidence = probe(gpu)
            respond({'nonce': nonce, 'sequence': 0, 'ok': True,
                'metadata': gpu.metadata, 'probe': evidence, 'protocol': PROTOCOL,
                'control_protocol': CONTROL_PROTOCOL})
            while True:
                request = read_packet(sys.stdin.buffer)
                if request is None: break
                if request.get('nonce') != nonce:
                    raise error('PROTOCOL', 'GPU控制消息标识不匹配')
                current = request.get('sequence')
                if type(current) is not int or current != sequence+1:
                    raise error('PROTOCOL', 'GPU控制消息序号不连续')
                sequence = current
                if request.get('op') == 'close': break
                execute(gpu, request, nonce)
                respond({'nonce': nonce, 'sequence': sequence, 'ok': True, 'metadata': gpu.metadata})
    except Exception as exc:
        problem = exc if isinstance(exc, AppError) else error('WORKER', '本任务GPU执行失败', exception=type(exc).__name__, detail=str(exc)[:4000])
        try:
            respond({'nonce': nonce, 'sequence': sequence, 'ok': False,
                     'error': problem.as_dict(), 'exit_code': problem.exit_code})
        except (OSError, AppError): pass  # A departed owner has already closed its private pipe.
        raise SystemExit(problem.exit_code)


if __name__ == '__main__': main()
