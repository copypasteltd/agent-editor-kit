"""Explicit Float32 GPU policy, bounded shared buffers and owned worker lifetime."""
from __future__ import annotations

from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

import numpy as np

from .artifact_locks import artifact_entry
from .errors import AppError
from .float_gpu_native import NativeGPU, error
from .float_gpu_control import OwnedPipeControl, PROTOCOL as CONTROL_PROTOCOL
from .projection_opencl import configuration
from .utils import atomic_write_json, sha256_file

PROTOCOL = 'render-owned-float32-opencl-v1'


class FloatGPUSession:
    def __init__(self, root, settings, *, operation_id=None, dry_run=False, cancel=None, timeout=300, max_pixels=65536):
        self.root = Path(root).resolve()
        self.config = configuration(settings.get('projection_acceleration'))
        self.enabled = self.config['mode'] != 'off'
        self.dry_run, self.poll, self.timeout = dry_run, cancel or (lambda: None), timeout
        self.nonce = uuid.uuid4().hex
        if operation_id is not None and (not isinstance(operation_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', operation_id)):
            raise error('PROTOCOL', 'GPU操作ID不可作为相对路径')
        self.directory = self.root/'cache/float-gpu'/(operation_id or 'float-'+self.nonce)
        self.path = self.directory/'receipt.json'
        self.process = None
        self.control = None
        self.directory_owned = False
        self.segments = []
        self.capacities = []
        self.generation = self.sequence = 0
        self.ready = self.closed = False
        self.planned_pixels = max_pixels
        self.evidence = {'engine': PROTOCOL, 'request': dict(self.config),
            'status': 'planned' if self.enabled else 'off', 'dry_run': dry_run,
            'operations': {}, 'CPU_scope': ['glyph-rasterization', 'color-conversion', 'effects-except-native-optics-and-glow', 'masks', 'crop',
                'transitions', 'non-normal-blends', 'audio', 'delivery-encoding'],
            'GPU_scope': ['premultiplied-affine', 'normal-source-over', 'text-color-components', 'binary-word-selection', 'seeded-particle-rasterization','analytic-optical-effects'],
            'host_shared_bytes_limit': self.config['max_working_bytes'], 'retained_host_shared_bytes': 0,
            'device_bytes_limit': self.config['max_working_bytes'], 'limits_are_peak_RSS': False,
            'free_VRAM_reserved': False, 'integer_media_conversion': False, 'worker_closed': False,
            'runtime_failure_CPU_fallback': False, 'artifacts': []}
        if type(max_pixels) is not int or not 1 <= max_pixels <= 16777216:
            raise error('BUDGET', 'GPU计划表面超过像素预算')
        self.evidence['planned_maximum_pixels'] = max_pixels
        self.evidence['planned_device_bytes'] = max_pixels*48
        self.evidence['planned_host_shared_bytes'] = max_pixels*33+768
        self.artifacts = [artifact_entry(Path(__file__).with_name(name+'.py'), 'float-gpu-execution')
                          for name in ('float_gpu', 'float_gpu_worker', 'float_gpu_native', 'float_gpu_control', 'procedural_particles', 'particle_animation','float_optics','float_optics_kernel','float_glow','float_glow_kernel','float_color_signal','float_hdr','float_hlg_black','float_chromatic')]
        self.evidence['artifacts'] = self.artifacts

    @property
    def active(self): return self.ready and not self.closed

    def save(self):
        if self.enabled and not self.dry_run and self.directory_owned:
            atomic_write_json(self.path, self.evidence)

    def verify_programs(self):
        self.poll()
        for entry in self.artifacts:
            if 'sha256:'+sha256_file(Path(entry['path'])) != entry['sha256']:
                raise error('INPUT_CHANGED', 'GPU执行实现发生变化', artifact=entry['path'])

    def _wait(self, number, timeout):
        deadline = time.monotonic()+timeout
        while True:
            self.poll()
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise error('TIMEOUT', '本任务GPU操作超时', timeout_seconds=timeout, sequence=number)
            value = self.control.receive(min(.02, remaining))
            if value is not None:
                if value.get('nonce') != self.nonce: raise error('PROTOCOL', 'GPU响应不属于本任务')
                current = value.get('sequence')
                if type(current) is not int or current < 0 or current > number:
                    raise error('PROTOCOL', 'GPU响应序号不连续')
                if not value.get('ok'):
                    self.evidence['worker_error_response'] = value
                    item = value.get('error') or {}
                    raise AppError(item.get('code', 'FLOAT_GPU_WORKER'), item.get('message', 'GPU执行失败'),
                        exit_code=value.get('exit_code', 6), diagnostics=item.get('diagnostics'))
                if current == number:
                    return value
            if self.process.poll() is not None:
                raise error('WORKER_EXIT', '本任务GPU进程提前退出', returncode=self.process.returncode)

    def __enter__(self):
        self.poll()
        if not self.enabled or self.dry_run: return self
        try:
            self.directory.mkdir(parents=True, exist_ok=False)
            self.directory_owned = True
            if max(self.evidence['planned_device_bytes'], self.evidence['planned_host_shared_bytes']) > self.config['max_working_bytes']:
                raise error('BUDGET', '计划表面超过GPU或主机共享配额',
                    planned_device_bytes=self.evidence['planned_device_bytes'], planned_host_shared_bytes=self.evidence['planned_host_shared_bytes'])
            atomic_write_json(self.directory/'init.json', {'nonce': self.nonce, 'device': self.config['device'],
                'max_device_bytes': self.config['max_working_bytes'], 'control_protocol': CONTROL_PROTOCOL})
            self.evidence['status'] = 'probing'; self.save()
            # Explicit existing NumPy site is needed by the isolated Windows
            # worker, both in a development checkout and in the offline bundle.
            bootstrap = 'import sys;sys.path[:0]='+repr([str(Path(__file__).resolve().parent.parent),
                str(Path(np.__file__).resolve().parent.parent)])+';from ai_ad_editor.float_gpu_worker import main;main()'
            command = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', '-c', bootstrap, str(self.directory)]
            self.process = subprocess.Popen(command, cwd=self.root, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.evidence['owned_worker_pid'] = self.process.pid
            self.control = OwnedPipeControl(self.process)
            self.evidence['control'] = self.control.evidence
            result = self._wait(0, self.config['probe_timeout_seconds'])
            if result.get('control_protocol') != CONTROL_PROTOCOL:
                raise error('PROTOCOL', 'GPU进程未确认任务自有管道协议')
            self.evidence.update(native=result['metadata'], probe=result['probe'], status='prepared')
            self.ready = True; self.save()
        except BaseException as exc:
            self._stop()
            self.evidence.update(status='preflight_failed', error=exc.as_dict() if isinstance(exc, AppError) else str(exc))
            self.save()
            if (not isinstance(exc, (AppError, OSError)) or self.config['mode'] == 'require' or
                    isinstance(exc, AppError) and exc.code in {'CANCELLED', 'PROCESS_TIMEOUT', 'FLOAT_GPU_TIMEOUT', 'FLOAT_GPU_INPUT_CHANGED'}):
                raise
            self.evidence['status'] = 'cpu_fallback'; self.save()
        return self

    def _buffers(self, sizes):
        wanted = [max(256, int(s)) for s in sizes]
        if sum(wanted) > self.config['max_working_bytes']:
            raise error('BUDGET', 'GPU共享缓冲区超过明确主机配额', required_bytes=sum(wanted), limit=self.config['max_working_bytes'])
        if len(self.segments) == 3 and all(n <= old for n, old in zip(wanted, self.capacities)): return
        self._free_shared()
        self.generation += 1
        try:
            for index, size in enumerate(wanted):
                self.segments.append(SharedMemory(name=f'aekfg{self.nonce}_{index}_{self.generation}', create=True, size=size))
                self.capacities.append(size)
        except BaseException:
            self._free_shared(); raise
        self.evidence['retained_host_shared_bytes'] = sum(wanted)
        self.evidence['maximum_host_shared_bytes'] = max(self.evidence.get('maximum_host_shared_bytes', 0), sum(wanted))

    def _call(self, op, shape, values, **params):
        self.poll()
        if not self.active: raise error('STATE', 'GPU尚未完成实际探测或已关闭')
        self.verify_programs()
        start = time.monotonic()
        output_bytes = int(shape[0])*int(shape[1])*16
        sizes = [max(output_bytes, values[0].nbytes), values[1].nbytes, values[2].nbytes]
        self._buffers(sizes)
        specs = []
        for index, value in enumerate(values):
            if not value.flags.c_contiguous: raise error('SURFACE', '禁止隐式复制非连续GPU输入')
            target = np.ndarray(value.shape, dtype=value.dtype, buffer=self.segments[index].buf)
            target[:] = value
            specs.append({'name': self.segments[index].name, 'shape': list(value.shape), 'dtype': str(value.dtype)})
            del target
        self.sequence += 1
        try:
            self.control.send({'nonce': self.nonce, 'sequence': self.sequence,
                'op': op, 'output_shape': list(shape), 'buffers': specs, **params})
            result = self._wait(self.sequence, self.timeout)
            self.evidence['native'] = result['metadata']
            self.evidence['operations'][op] = self.evidence['operations'].get(op, 0)+1
            output = np.ndarray(shape, dtype=np.float32, buffer=self.segments[0].buf).copy()
            NativeGPU.surface(output)
            self.poll()
            self.evidence['operation_elapsed_seconds'] = self.evidence.get('operation_elapsed_seconds', 0)+time.monotonic()-start
            return output
        except BaseException as exc:
            self.evidence.update(status='cancelled' if isinstance(exc, AppError) and exc.code == 'CANCELLED' else 'failed',
                                 error=exc.as_dict() if isinstance(exc, AppError) else str(exc))
            self._stop(); self.save(); raise

    @staticmethod
    def _dummy(): return np.zeros(1, np.uint8)

    def over(self, a, b, opacity=1., *, text_order=False):
        NativeGPU.surface(a); NativeGPU.surface(b)
        if a.shape != b.shape: raise error('SURFACE', 'GPU合成输入形状不一致')
        return self._call('over', a.shape, [a, b, self._dummy()], opacity=opacity, text_order=text_order)

    def resample(self, source, size, inverse):
        NativeGPU.surface(source)
        if (not isinstance(size, (list, tuple)) or len(size) != 2 or
                any(type(v) is not int or not 1 <= v <= 16384 for v in size) or size[0]*size[1] > 16777216):
            raise error('GEOMETRY', 'GPU输出尺寸无效')
        # Slot zero reserves the complete destination. Its bytes are not input
        # pixels, so no extra host Float32 scratch surface is required.
        out_shape = (size[1], size[0], 4)
        placeholder = np.zeros(1, np.uint8)
        output = self._call('affine', out_shape, [placeholder, source, self._dummy()], inverse=inverse, nearest=False)
        return output, {'protocol': PROTOCOL, 'GPU': True, 'interpolation': 'bilinear', 'inverse': inverse,
                        'filtering_alpha': 'premultiplied-RGB-and-alpha', 'integer_media_conversion': False}

    def paint(self, masks, colors, *, base=None):
        if (not isinstance(masks, np.ndarray) or masks.dtype != np.uint8 or masks.ndim != 3
                or not 1 <= len(masks) <= 4): raise error('MASK', 'GPU文字组件覆盖率无效')
        shape = (masks.shape[1], masks.shape[2], 4)
        if base is not None:
            NativeGPU.surface(base)
            if base.shape != shape: raise error('SURFACE', 'GPU文字底图尺寸不一致')
        return self._call('paint', shape, [base if base is not None else self._dummy(), masks, self._dummy()], colors=[list(c) for c in colors])

    def select(self, normal, active, selection):
        NativeGPU.surface(normal); NativeGPU.surface(active)
        return self._call('select', normal.shape, [normal, active, selection])

    def prepare(self, args, graph):
        self.verify_programs(); self.save()
        return args, graph

    def particles(self, scene, tiles, size):
        from .procedural_particles import validate_scene
        validate_scene(scene, tiles, size)
        return self._call('particles', (size[1], size[0], 4), [self._dummy(), scene, tiles])

    def optics(self, source, kind, values, ghosts=0, edge='clamp'):
        from .float_optics import validate_state
        values=validate_state(kind,values,ghosts,edge);NativeGPU.surface(source)
        return self._call('optics',source.shape,[self._dummy(),source,self._dummy()],kind=kind,
            parameters=values,ghosts=ghosts,edge=edge)

    def glow(self, source, kind, values, edge, primaries,*,white_xy=None):
        from .float_glow import validate_state,luma_coefficients,admit_neighborhood
        values=validate_state(kind,values,edge);luma_coefficients(primaries,white_xy);NativeGPU.surface(source)
        admit_neighborhood(source.shape[0]*source.shape[1],values['radius'])
        return self._call('glow',source.shape,[self._dummy(),source,self._dummy()],kind=kind,
            parameters=values,edge=edge,primaries=primaries,white_xy=white_xy)

    def finish(self, result):
        if self.ready:
            if not self.evidence['operations']:
                self.evidence['status'] = 'not_applicable'; self.save()
                if self.config['mode'] == 'require':
                    raise error('NOT_APPLICABLE', '工程没有实际执行受支持的GPU浮点算子')
                return
            self.evidence.update(render_exit_code=result.returncode,
                status='encoded_pending_quality' if result.returncode == 0 else 'render_failed')
        self.save()

    def _free_shared(self):
        for segment in self.segments:
            segment.close()
            try: segment.unlink()
            except FileNotFoundError: pass
        self.segments.clear(); self.capacities.clear()
        self.evidence['retained_host_shared_bytes'] = 0

    def _stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=5)
            self.evidence['worker_returncode'] = self.process.returncode
        if self.control is not None:
            self.control.close()
        self.ready = False
        self._free_shared()
        self.evidence['worker_closed'] = self.process is None or self.process.poll() is not None
        self.evidence['shared_handles_closed'] = not self.segments
        if self.directory_owned:
            for name in ('init.json', 'request.json', 'response.json'):
                (self.directory/name).unlink(missing_ok=True)

    def __exit__(self, kind, value, trace):
        if self.closed: return
        if self.process is not None and self.process.poll() is None and kind is None:
            self.sequence += 1
            try:
                self.control.send({'nonce': self.nonce, 'sequence': self.sequence, 'op': 'close'})
                self.process.wait(timeout=2)
            except (subprocess.TimeoutExpired, AppError, OSError): pass
        if value is not None:
            self.evidence.update(status='cancelled' if isinstance(value, AppError) and value.code == 'CANCELLED' else 'failed')
        self._stop(); self.closed = True; self.save()
