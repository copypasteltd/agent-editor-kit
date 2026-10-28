"""Original native-clock random access with bounded float pixel windows.

Windows read handles freeze inputs for this provider's complete lifetime.
Native indexes retain clocks only; no full-movie float intermediate is made.
Seek preroll is codec/GOP dependent and is not an O(N) reverse-play guarantee.
Display orientation/SAR are recorded, not applied to the native raster here.
"""
from __future__ import annotations
from array import array
from bisect import bisect_left, bisect_right
from collections import deque
from fractions import Fraction
import hashlib
from pathlib import Path
import re
import sys

from .artifact_locks import _Verification
from .errors import AppError
from .float_color_signal import ColorSignal, convert_rgba
from .float_native_pipe import NativePipe
from . import float_pixels, float_yuv
from .float_timeline import TimedSurfaceSource, MAX_SURFACE_BYTES
from .media import ffmpeg_path, ffprobe_path
from .native_audio_clock import cancel
from .native_video_index import IndexContext
from .policy import resolve_local_path
from .reverse_video_clock import probe_frames

PROTOCOL = 'locked-native-clock-window-float32-source-v1'
MAX_CACHE_BYTES = 256 * 1024**2
MAX_WINDOW_FRAMES = 256
MAX_LINE_BYTES = 4096
MAX_RECENT_WINDOWS = 64


def error(code, message, **details):
    return AppError('FLOAT_NATIVE_SOURCE_' + code, message, exit_code=6,
                    diagnostics=details or None)


def _records(pipe):
    pending = bytearray()
    for block in pipe.chunks():
        pending.extend(block)
        while (end := pending.find(b'\n')) >= 0:
            if end > MAX_LINE_BYTES:
                raise error('PROBE', '原生关键帧记录超过4096字节')
            line = bytes(pending[:end]).decode('utf8', 'strict').strip()
            del pending[:end + 1]
            if line:
                yield line
        if len(pending) > MAX_LINE_BYTES:
            raise error('PROBE', '原生关键帧记录超过4096字节')
    if pending:
        yield bytes(pending).decode('utf8', 'strict').strip()


class NativeSurfaceSource(TimedSurfaceSource):
    """An explicitly signalled registered video/image, with owned frame copies.

    Construction opens the provider; context exit releases its own locks and
    native processes only. A shared IndexContext is optional, with the same
    root, persistence and cancellation contract. Persisting requires the common
    project writer lock, as in the existing native-index API.
    """
    def __init__(self, root, asset, *, source_signal, working_signal,
                 yuv_spec=None, scan=None, demux_origin=None,
                 alpha_association='straight', window_frames=16,
                 cache_bytes=MAX_CACHE_BYTES, index_context=None,
                 persist_index=False, decoder=None, cancel_file=None,
                 timeout=300, hdr_input_range_policy='reject'):
        self.closed = True
        self.guard = None
        self.pipe = None
        self.cache = []
        self.cache_start = -1
        self.metadata = {'protocol': PROTOCOL, 'network': False,
                         'default_renderer_integrated': False, 'HDR_accepted': False}
        if sys.platform != 'win32':
            raise error('PLATFORM', '该原生持锁实现当前要求Windows')
        if not isinstance(source_signal, ColorSignal) or not isinstance(working_signal, ColorSignal):
            raise error('SIGNAL', '原始与工作RGB信号须明确提供')
        if not isinstance(hdr_input_range_policy, str) or hdr_input_range_policy not in {'reject','clip'}:
            raise error('SIGNAL', 'HDR输入编码域策略须明确reject/clip')
        self.hdr_input_range_policy=hdr_input_range_policy
        if not isinstance(asset, dict) or asset.get('kind') not in ('image', 'video'):
            raise error('ASSET', '帧源要求已登记的视频或图片资产')
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', str(asset.get('sha256', ''))):
            raise error('ASSET', '帧源要求原始资产SHA-256')
        if alpha_association not in ('straight', 'premultiplied'):
            raise error('ALPHA', '原始透明度表示必须明确')
        if yuv_spec is not None and not isinstance(yuv_spec, float_yuv.YUVSpec):
            raise error('SIGNAL', 'YCbCr矩阵、量程和采样位置必须明确')
        for value, limit in ((window_frames, MAX_WINDOW_FRAMES), (cache_bytes, MAX_CACHE_BYTES)):
            if type(value) is not int or not 1 <= value <= limit:
                raise error('BUDGET', '像素窗口或缓存预算无效')
        if decoder is not None and not re.fullmatch('[A-Za-z0-9_]{1,64}', str(decoder)):
            raise error('DECODER', '解码器名称无效')
        # Validate this before a probe is allowed to start, not only at pipe open.
        import math
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
            raise error('BUDGET', '单次原生操作超时须在0..3600秒范围')
        self.root = Path(root).resolve()
        self.marker = Path(cancel_file) if cancel_file is not None else None
        self.source = resolve_local_path(self.root, asset.get('uri', ''), field='float-native-source.asset')
        self.input_signal = source_signal
        self.target_signal = working_signal
        self.yuv_spec = yuv_spec
        self.alpha_association = alpha_association
        self.decoder = decoder
        self.timeout = timeout
        self.expected_sha = asset['sha256']
        self.recent = deque(maxlen=MAX_RECENT_WINDOWS)
        self.history = hashlib.sha256()
        self.poll()
        if index_context is not None and (not isinstance(index_context, IndexContext)
                or index_context.root.resolve() != self.root
                or index_context.persist != persist_index
                or index_context.cancel_file != self.marker):
            raise error('INDEX', '共享索引须匹配工程、持久化和取消配置')
        context = index_context or IndexContext(self.root, persist=persist_index, cancel_file=self.marker)
        self.guard = _Verification()
        self.closed = False
        try:
            files = {'source': self.source, 'ffmpeg': Path(ffmpeg_path()).resolve(),
                     'ffprobe': Path(ffprobe_path()).resolve()}
            for name in ('float_native_source', 'float_native_pipe', 'float_pixels', 'float_yuv',
                         'float_color_signal', 'float_hdr', 'float_chromatic', 'float_timeline', 'native_video_index',
                         'reverse_video_clock', 'artifact_locks', 'native_audio_clock', 'policy', 'media'):
                files[name] = Path(__file__).with_name(name + '.py')
            self.artifacts = {name: self.guard.entry(path, 'float-native-source-' + name)
                              for name, path in files.items()}
            if self.artifacts['source']['sha256'] != self.expected_sha:
                raise error('INPUT_CHANGED', '原始资产字节与登记SHA不一致')
            def probe(path, *, cancel_file=None, decoder=None):
                return probe_frames(path, timeout=self.timeout, cancel_file=cancel_file, decoder=decoder)
            pts, durations, self.stream, self.format_info, index = context.acquire(
                self.source, self.expected_sha, probe, decoder=decoder)
            self.points = pts
            self.native_time_base = Fraction(self.stream['time_base'])
            for name, row in index.get('files', {}).items():
                locked = self.guard.entry(Path(row['path']), 'float-native-index-' + name)
                if locked['sha256'] != row['sha256']:
                    raise error('INDEX', '原生帧索引在加锁前发生变化')
                self.artifacts['index-' + name] = locked
            self.width, self.height = int(self.stream['width']), int(self.stream['height'])
            self.native_format = self.stream['pix_fmt']
            self.pixel_format = self.native_format
            if self.native_format.startswith('yuvj'):
                if yuv_spec is None or yuv_spec.range != 'full':
                    raise error('SIGNAL', 'JPEG YCbCr要求显式full量程，不能依据标签猜测')
                # yuvj is an 8-bit full-range label; the planar bytes are identical.
                self.pixel_format = 'yuv' + self.native_format[4:]
            self.pixel_module = float_yuv if yuv_spec is not None else float_pixels
            self.raw_bytes = self.pixel_module.frame_bytes(self.pixel_format, self.width, self.height)
            if yuv_spec is not None and scan != 'progressive':
                raise error('SCAN', 'YCbCr原生读取须明确声明逐行色度语义')
            self.float_bytes = self.width * self.height * 16
            if self.float_bytes > min(cache_bytes, MAX_SURFACE_BYTES):
                raise error('BUDGET', '缓存预算不足以容纳一个原始Float32帧')
            self.window_size = min(window_frames, cache_bytes // self.float_bytes)
            self.keys, key_probe = self._probe_keys()
            field_order = key_probe['field_order']
            if field_order not in (None, 'unknown', 'progressive'):
                raise error('SCAN', '已知隔行源要求专用适配，不能作为逐行表面交付', field_order=field_order)
            recorded = self.format_info.get('start_time')
            recorded = Fraction(recorded) if recorded not in (None, '', 'N/A') else None
            if demux_origin is None:
                if recorded is None:
                    raise error('CLOCK', '容器起点未知，调用者须显式指定')
                origin = recorded
            else:
                origin = Fraction(demux_origin)
                if recorded is not None and origin != recorded:
                    raise error('CLOCK', '显式容器起点与解复用记录不一致')
            super().__init__(map(int, pts), map(int, durations), self.native_time_base, origin,
                             self._fetch, signal=working_signal, source_sha256=self.expected_sha,
                             verify=self._verify, still=asset['kind'] == 'image')
            self.metadata.update(source=str(self.source), source_sha256=self.expected_sha,
                native_frame_clock=True, native_time_base=str(self.time_base), demux_origin=str(origin),
                origin_from_caller=recorded is None, native_stream=self.stream, format_info=self.format_info,
                native_index=index, native_format=self.native_format, pixel_byte_layout=self.pixel_format,
                source_signal=vars(source_signal), working_signal=vars(working_signal),
                source_color_spec=vars(yuv_spec) if yuv_spec is not None else None,
                color_spec_overrides_tags=yuv_spec is not None, alpha_association=alpha_association,
                field_order=field_order, scan_assumption=scan, scan_automatically_verified=field_order == 'progressive',
                progressive_only=True, native_raster_orientation_applied=False, sample_aspect_ratio_applied=False,
                CFR_normalization=False, source_frames=len(pts), key_probe=key_probe,
                requested_window_frames=window_frames, effective_window_frames=self.window_size,
                cache_limit_bytes=cache_bytes, maximum_cached_float_bytes=0, cache_hits=0, decoded_windows=0,
                delivered_native_frames=0, logical_preroll_frame_distance_total=0,
                logical_preroll_is_actual_decoder_work=False, frame_copies_owned=True,
                recent_windows_limit=MAX_RECENT_WINDOWS, whole_movie_pixel_cache=False,
                cache_budget_is_total_RSS_limit=False, index_maximum_frames=1000000,
                reverse_complexity_guaranteed_linear=False, artifacts=self.artifacts)
            self._verify()
        except BaseException:
            self.close(verify=False)
            raise

    def poll(self):
        cancel(self.marker)

    def _probe_keys(self):
        command = [self.artifacts['ffprobe']['path'], '-v', 'error', '-protocol_whitelist', 'file,pipe',
            '-select_streams', 'v:0', '-skip_frame', 'nokey', '-show_frames', '-show_streams',
            '-show_entries', 'frame=key_frame,best_effort_timestamp:frame_side_data=:stream=field_order:stream_disposition=:stream_tags=:stream_side_data=',
            '-of', 'compact=p=1:nk=0', *(['-c:v', self.decoder] if self.decoder else []), str(self.source)]
        keys = array('q')
        field_order = None
        with NativePipe(command, cwd=self.root, cancel_file=self.marker, timeout=self.timeout) as pipe:
            for line in _records(pipe):
                parts = line.split('|')
                row = dict(part.split('=', 1) for part in parts[1:] if '=' in part)
                if parts[0] == 'frame' and row.get('key_frame') == '1':
                    try: point = int(row['best_effort_timestamp'])
                    except (ValueError, KeyError) as caught:
                        raise error('PROBE', '原生关键帧缺少明确PTS') from caught
                    at = bisect_left(self.points, point)
                    if at == len(self.points) or self.points[at] != point or (keys and point <= keys[-1]):
                        raise error('PROBE', '关键帧PTS未按原生索引严格递增')
                    keys.append(point)
                elif parts[0] == 'stream':
                    field_order = row.get('field_order')
            pipe.finish()
            receipt = {'command': command, 'exit_code': pipe.process.returncode,
                       'keyframes': len(keys), 'field_order': field_order,
                       'stdout_bytes': pipe.bytes_read, 'maximum_queued_chunks': pipe.maximum_queued_chunks,
                       'chunk_bytes': 65536, 'queue_chunks_limit': 4,
                       'all_owned_threads_exited': all(not t.is_alive() for t in pipe.threads)}
        return keys, receipt

    def _check(self):
        self.poll()
        if self.closed:
            raise error('CLOSED', '原生窗口帧源已经关闭')

    def _verify(self):
        self._check()
        for row in self.artifacts.values():
            if self.guard.entry(Path(row['path']), row['role'])['sha256'] != row['sha256']:
                raise error('INPUT_CHANGED', '原始素材、索引、实现或工具发生变化')
        self.metadata['locks'] = self.guard.summary()

    def _decode_window(self, start, end):
        self._verify()
        key_at = bisect_right(self.keys, self.pts[start]) - 1
        key = self.keys[key_at] if key_at >= 0 else self.pts[0]
        seek = key * self.time_base - self.origin
        # FFmpeg input times are microsecond based. Round toward earlier time;
        # rounding to nearest can seek just after the independently known key.
        micros = seek.numerator * 1000000 // seek.denominator
        seek_text = f'{micros // 1000000}.{micros % 1000000:06d}' if micros > 0 and key_at >= 0 else None
        trim = f'trim=start_pts={self.pts[start]}'
        if end < len(self.pts):
            trim += f':end_pts={self.pts[end]}'
        command = [self.artifacts['ffmpeg']['path'], '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-copyts', '-protocol_whitelist', 'file,pipe', '-threads', '1', '-filter_threads', '1',
            '-noautorotate', *(['-noaccurate_seek', '-ss', seek_text] if seek_text else []),
            *(['-c:v', self.decoder] if self.decoder else []), '-i', str(self.source),
            '-map', '0:v:0', '-an', '-sn', '-dn', '-vf', trim, '-fps_mode', 'passthrough',
            '-pix_fmt', '+' + self.native_format, '-frames:v', str(end - start), '-f', 'rawvideo', 'pipe:1']
        frames = []
        self.cache.clear()
        self.cache_start = -1
        receipt = {'first_frame': start, 'end_frame_exclusive': end, 'command': command,
                   'seek_seconds': seek_text, 'previous_known_key_pts': int(key),
                   'logical_preroll_frame_distance': start - bisect_left(self.pts, key)}
        try:
            with NativePipe(command, cwd=self.root, cancel_file=self.marker, timeout=self.timeout) as pipe:
                self.pipe = pipe
                receipt['owned_pid'] = pipe.process.pid
                for frame_index in range(start, end):
                    raw = pipe.read(self.raw_bytes)
                    if len(raw) != self.raw_bytes:
                        raise error('TRUNCATED', '局部解码未交付原生索引对应的完整帧', frame=frame_index,
                                    expected_bytes=self.raw_bytes, actual_bytes=len(raw), stderr=pipe.stderr())
                    options = {'spec': self.yuv_spec} if self.yuv_spec is not None else {}
                    value, pixel_metadata = self.pixel_module.decode_frame(raw, self.pixel_format,
                        self.width, self.height, alpha_association=self.alpha_association,
                        cancel=self.poll, **options)
                    value, color_metadata = convert_rgba(value, self.input_signal, self.target_signal, cancel=self.poll,
                        hdr_input_range_policy=self.hdr_input_range_policy)
                    if 'hdr_input_components_clipped' in color_metadata:
                        self.metadata['HDR_input_components_clipped_across_decoded_windows'] = self.metadata.get('HDR_input_components_clipped_across_decoded_windows',0) + color_metadata['hdr_input_components_clipped']
                    frames.append(value)
                if pipe.read(1):
                    raise error('COUNT', '局部解码返回了额外帧字节')
                pipe.finish()
                receipt.update(status='passed', exit_code=pipe.process.returncode,
                    stdout_bytes=pipe.bytes_read, maximum_queued_chunks=pipe.maximum_queued_chunks,
                    all_owned_threads_exited=all(not t.is_alive() for t in pipe.threads))
            self._verify()
            self.cache = frames
            self.cache_start = start
            cached = sum(v.nbytes for v in frames)
            self.metadata['maximum_cached_float_bytes'] = max(self.metadata['maximum_cached_float_bytes'], cached)
            self.metadata['delivered_native_frames'] += len(frames)
            self.metadata['logical_preroll_frame_distance_total'] += receipt['logical_preroll_frame_distance']
            self.metadata.update(pixel_boundary=pixel_metadata, color_boundary=color_metadata)
        except BaseException as caught:
            receipt.update(status='failed-preserved-in-provider-receipt', error=repr(caught))
            frames.clear()
            raise
        finally:
            if self.pipe is not None:
                receipt.update(exit_code=self.pipe.process.poll(),
                    all_owned_threads_exited=all(not t.is_alive() for t in self.pipe.threads))
            self.pipe = None
            self.recent.append(receipt)
            from .native_video_index import canonical
            self.history.update(canonical(receipt))
            self.metadata.update(decoded_windows=self.metadata['decoded_windows'] + 1,
                recent_windows=list(self.recent), window_history_sha256='sha256:' + self.history.hexdigest())

    def _fetch(self, index):
        self._check()
        if type(index) is not int or not 0 <= index < len(self.pts):
            raise error('RANGE', '原生帧索引越界')
        # Denying file writes also excludes temporary modifications later undone.
        self.guard.entry(self.source, 'float-native-source-source')
        if not self.cache_start <= index < self.cache_start + len(self.cache):
            start = index // self.window_size * self.window_size
            self._decode_window(start, min(len(self.pts), start + self.window_size))
        else:
            self.metadata['cache_hits'] += 1
        result = self.cache[index - self.cache_start].copy(order='C')
        self._check()
        return result

    def close(self, *, verify=True):
        if self.closed:
            return
        try:
            if verify:
                self._verify()
        finally:
            try:
                if self.pipe is not None:
                    self.pipe.close()
            finally:
                self.pipe = None
                self.cache.clear()
                if self.guard is not None:
                    self.metadata['locks_at_close'] = self.guard.summary()
                    self.guard.close()
                self.closed = True
                self.metadata['closed'] = True

    def __enter__(self):
        self._check()
        return self

    def __exit__(self, kind, value, trace):
        self.close(verify=kind is None)
