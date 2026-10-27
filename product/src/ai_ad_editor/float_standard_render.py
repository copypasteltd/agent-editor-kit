"""Original native windows feed the shared render/queue/resume executor.

The author project selects this pixel pipeline explicitly. Existing audio,
encoders, quality checks and operation records stay in the common renderer.
Relative RGB stays Float32 until the final declared integer delivery edge.
"""
from contextlib import ExitStack
import copy
import hashlib
import os
import re
from pathlib import Path
import subprocess
import sys
from fractions import Fraction

import numpy as np

from .artifact_locks import artifact_entry
from .errors import AppError
from .float_color_signal import ColorSignal, convert_rgba
from .float_native_source import NativeSurfaceSource
from .float_stream import _EncoderPipe, _chunks, CHUNK_BYTES, QUEUE_CHUNKS
from .float_timeline import FloatTimeline
from .float_yuv import YUVSpec
from .media import ffmpeg_path, ffprobe_path, probe_media
from .native_audio_clock import cancel
from .native_video_index import IndexContext
from .policy import resolve_local_path
from .sequence_sampling import configuration as sampling_configuration
from .utils import sha256_file, atomic_write_json

ENGINE = 'float32-native-v1'
PROTOCOL = 'standard-render-native-float32-v1'
MAX_SOURCE_CACHE_BYTES = 8 * 1024**3


def error(code, message, **details):
    return AppError('FLOAT_RENDER_' + code, message, exit_code=2, diagnostics=details or None)


def _signal(value, field):
    if not isinstance(value, dict) or set(value) != {'primaries', 'transfer'}:
        raise error('SIGNAL', 'RGB信号必须明确指定primaries/transfer', field=field)
    return ColorSignal(**value)


def configuration(value, settings, encoder):
    allowed = {'engine', 'working_signal', 'output_signal', 'background_signal', 'range_policy',
               'window_frames', 'max_source_cache_bytes', 'max_open_sources', 'native_timeout_seconds', 'sources'}
    if not isinstance(value, dict) or set(value) - allowed or value.get('engine') != ENGINE:
        raise error('CONFIG', 'pixel_pipeline必须使用完整且受支持的浮点配置')
    working = _signal(value.get('working_signal'), 'working_signal')
    output = _signal(value.get('output_signal'), 'output_signal')
    background = _signal(value.get('background_signal', {'primaries': 'bt709', 'transfer': 'srgb'}), 'background_signal')
    if working.transfer != 'linear':
        raise error('SIGNAL', '标准浮点合成要求显式线性光工作域')
    if output.primaries != 'bt709' or output.transfer not in {'linear', 'srgb', 'bt709-oetf'}:
        raise error('SIGNAL', '当前交付边界要求BT.709基色与明确相对传递函数')
    color = settings.get('color') or {}
    if not isinstance(color, dict):
        raise error('CONFIG', '输出色彩配置必须是对象')
    transfer = {'linear': 'linear', 'srgb': 'iec61966-2-1', 'bt709-oetf': 'bt709'}[output.transfer]
    if (color.get('primaries') != 'bt709' or color.get('transfer') != transfer or
            color.get('matrix') != 'bt709' or color.get('range') not in {'limited', 'full', 'tv', 'pc'}):
        raise error('COLOR_TAGS', '输出色彩标签必须与实际浮点交付转换一致')
    if color.get('tone_map', 'none') != 'none' or color.get('tone_mapping', 'none') != 'none':
        raise error('UNSUPPORTED', 'HDR色调映射尚未连接浮点标准渲染')
    acceleration = settings.get('acceleration') or {}
    if not isinstance(acceleration, dict):
        raise error('CONFIG', '硬件加速配置必须是对象')
    if acceleration.get('encode', 'off') != 'off' or acceleration.get('decode', 'off') != 'off':
        raise error('UNSUPPORTED', '浮点标准渲染的硬件加速尚未连接')
    sampling = sampling_configuration(settings.get('sequence_sampling'))
    if sampling['method'] != 'bilinear':
        raise error('UNSUPPORTED', '浮点标准渲染尚未连接area采样')
    aspect = settings['canvas'].get('pixel_aspect') or {'num': 1, 'den': 1}
    if aspect.get('num') != aspect.get('den'):
        raise error('GEOMETRY', '非方形输出像素尚未连接浮点标准渲染')
    policy = value.get('range_policy', 'reject')
    if policy not in {'reject', 'clip'}:
        raise error('CONFIG', 'RGB范围策略只允许reject/clip')
    normalized = dict(value)
    for field, default, limit in (('window_frames', 16, 256),
                                   ('max_source_cache_bytes', 256 * 1024**2, MAX_SOURCE_CACHE_BYTES),
                                   ('max_open_sources', 64, 256), ('native_timeout_seconds', 300, 3600)):
        number = value.get(field, default)
        if type(number) is not int or not 1 <= number <= limit:
            raise error('BUDGET', '浮点源窗口/缓存/数量/超时预算无效', field=field)
        normalized[field] = number
    sources = value.get('sources')
    if not isinstance(sources, dict) or len(sources) > 4096:
        raise error('CONFIG', 'sources必须是按已登记资产ID索引的显式信号表')
    for asset_id, spec in sources.items():
        allowed_source = {'source_signal', 'yuv_spec', 'scan', 'demux_origin', 'alpha_association', 'decoder', 'display_geometry'}
        if not isinstance(asset_id, str) or not isinstance(spec, dict) or set(spec) - allowed_source:
            raise error('CONFIG', '原始源信号配置字段无效', asset_id=asset_id)
        _signal(spec.get('source_signal'), asset_id)
        if spec.get('display_geometry') != 'square-unrotated':
            raise error('GEOMETRY', '须明确声明方形像素及未旋转原始栅格', asset_id=asset_id)
        if spec.get('alpha_association', 'straight') not in {'straight', 'premultiplied'}:
            raise error('CONFIG', '原始alpha表示无效', asset_id=asset_id)
        if spec.get('scan') not in (None, 'progressive'):
            raise error('CONFIG', '只支持明确逐行采样或未声明的RGB源', asset_id=asset_id)
        if 'decoder' in spec and (not isinstance(spec['decoder'], str) or
                not re.fullmatch('[A-Za-z0-9_]{1,64}', spec['decoder'])):
            raise error('CONFIG', '原始解码器名称无效', asset_id=asset_id)
        if 'demux_origin' in spec:
            origin = spec['demux_origin']
            if type(origin) is not int and (not isinstance(origin, str) or
                    not re.fullmatch(r'-?\d+(?:/\d+)?', origin)):
                raise error('CONFIG', '容器原点必须是整数或精确有理数', asset_id=asset_id)
            try:
                Fraction(origin)
            except (ValueError, ZeroDivisionError):
                raise error('CONFIG', '容器原点的有理数无效', asset_id=asset_id)
        if spec.get('yuv_spec') is not None:
            yuv = spec['yuv_spec']
            if not isinstance(yuv, dict) or set(yuv) != {'matrix', 'range', 'chroma_location'}:
                raise error('SIGNAL', 'YCbCr信号须明确矩阵/量程/采样位置', asset_id=asset_id)
            YUVSpec(**yuv)
            if spec.get('scan') != 'progressive':
                raise error('SIGNAL', 'YCbCr须明确逐行采样', asset_id=asset_id)
    normalized.update(working=working, output=output, background=background, range_policy=policy,
                      projection_working_bytes_limit=min(768 * 1024**2, sampling['max_working_bytes']),
                      alpha_output=encoder['video']['pixel_format'] == 'yuva420p',
                      output_range='pc' if color['range'] in {'pc', 'full'} else 'tv', transfer_tag=transfer)
    return normalized


class FloatRenderContext:
    def __init__(self, root, project, sequence, encoder, *, dry_run=False, cancel_file=None, operation_id=None):
        self.root = Path(root).resolve()
        self.project = project
        self.sequence = sequence
        self.encoder = encoder
        self.marker = cancel_file
        self.dry_run = dry_run
        self.operation_id = operation_id
        self.gpu = None
        self.config = configuration(project['settings']['pixel_pipeline'], project['settings'], encoder)
        self.stack = ExitStack()
        self.sources = {}
        self.timeline = None
        self.receipt = None
        self.sources_closed = False
        self.published = False
        self.metadata = {'protocol': PROTOCOL, 'engine': ENGINE, 'standard_render_selected': True,
                         'author_project_rewritten': False, 'whole_movie_pixel_cache': False,
                         'working_signal': vars(self.config['working']), 'output_signal': vars(self.config['output']),
                         'background_signal': vars(self.config['background']), 'range_policy': self.config['range_policy'],
                         'HDR_accepted': False, 'network': False, 'source_receipts': {}}

    def poll(self):
        cancel(self.marker)

    def __enter__(self):
        try:
            self._prepare_sources()
            return self
        except BaseException:
            self.stack.__exit__(*sys.exc_info())
            raise

    def __exit__(self, kind, value, trace):
        if kind is None and not self.published:
            try:
                self.verify()
            except BaseException:
                self.stack.__exit__(*sys.exc_info())
                raise
        # Forward the real exception. close() would tell child providers this
        # was a success, re-poll cancellation and replace the recorded operation.
        self.stack.__exit__(kind, value, trace)

    def _prepare_sources(self):
        from .render import _alpha_video_decoder
        self.poll()
        assets = {a['id']: a for a in self.project['assets']}
        sequences = {s['id']: s for s in self.project['sequences']}
        needed = set()
        def collect(sequence_id, parents=()):
            if sequence_id in parents or len(parents) >= 16 or sequence_id not in sequences:
                raise error('SEQUENCE', '序列循环、缺失或嵌套过深')
            for track in sequences[sequence_id]['tracks']:
                if track.get('muted') or track['kind'] not in ('video','overlay'):
                    continue
                for clip in track['clips']:
                    if clip.get('sequence_id'):
                        collect(clip['sequence_id'], (*parents, sequence_id))
                    elif not (isinstance(clip.get('generator'),dict) and clip['generator'].get('type')=='particles'):
                        needed.add(clip.get('asset_id'))
        collect(self.sequence['id'])
        if len(needed) > self.config['max_open_sources']:
            raise error('BUDGET', '原始浮点源数量超过显式预算', sources=len(needed))
        if set(self.config['sources']) - set(assets) or needed - set(self.config['sources']):
            raise error('SOURCE', '可达视频/图片缺少显式信号，或配置含未登记资产')
        paths = [Path(ffmpeg_path()).resolve(), Path(ffprobe_path()).resolve()]
        paths += [Path(__file__).with_name(name + '.py') for name in
                  ('float_standard_render', 'float_stream', 'float_audio_graph', 'render', 'float_color_signal',
                   'float_timeline', 'float_tracking', 'bindings', 'animation', 'float_crop', 'float_adjustments', 'float_effect_chain', 'float_transitions', 'float_transition_plan', 'source_transitions',
                   'float_text','float_text_paint','float_text_coverage','text_paint','text_layout','text_highlight','text_typing','captions',
                   'float_gpu','float_gpu_native','float_gpu_worker','float_gpu_control','procedural_particles','particle_animation','float_optics','float_optics_kernel')]
        self.artifacts = [artifact_entry(p, 'standard-float-render-runtime') for p in paths]
        context = IndexContext(self.root, persist=not self.dry_run, cancel_file=self.marker)
        per_source = min(256 * 1024**2, self.config['max_source_cache_bytes'] // max(1, len(needed)))
        self.metadata.update(source_count=len(needed), per_source_cache_limit_bytes=per_source,
                             total_source_cache_limit_bytes=self.config['max_source_cache_bytes'],
                             cache_limit_is_process_RSS_limit=False, artifacts=self.artifacts)
        from .sequence_canvas import sequence_canvas
        planned_pixels = max(c['width']*c['height'] for c in [sequence_canvas(self.project, s) for s in sequences.values()])
        for sequence in sequences.values():
            for track in sequence['tracks']:
                for clip in track['clips']:
                    generator=clip.get('generator') or {}
                    if generator.get('type')=='particles':
                        from .procedural_particles import normalize
                        c=normalize(generator)['canvas'];planned_pixels=max(planned_pixels,c['width']*c['height'])
        for asset_id in sorted(needed):
            self.poll()
            asset = assets.get(asset_id)
            if asset is None or asset.get('kind') not in {'image', 'video'}:
                raise error('SOURCE', '可达视觉片段需要本地视频或图片', asset_id=asset_id)
            path = resolve_local_path(self.root, asset['uri'], field='float-render.asset')
            locked = artifact_entry(path, 'standard-float-render-original')
            if locked['sha256'] != asset['sha256']:
                raise error('SOURCE_CHANGED', '原始资产实际SHA与登记值不一致', asset_id=asset_id)
            inspected = probe_media(path)
            video = next((s for s in inspected.get('streams', []) if s.get('codec_type') == 'video'), {})
            planned_pixels = max(planned_pixels, int(video.get('width', 0))*int(video.get('height', 0)))
            aspect = str(video.get('sample_aspect_ratio', ''))
            if aspect not in {'', 'N/A', '0:1'}:
                try: square = Fraction(aspect.replace(':', '/')) == 1
                except (ValueError, ZeroDivisionError): square = False
                if not square:
                    raise error('GEOMETRY', '已知非方形源像素尚未连接浮点投影', asset_id=asset_id)
            if any('display matrix' in str(s.get('side_data_type', '')).lower() for s in video.get('side_data_list', [])):
                raise error('GEOMETRY', '源显示矩阵尚未连接浮点投影', asset_id=asset_id)
            if str((video.get('tags') or {}).get('rotate', '0')) not in {'0', '0.0'}:
                raise error('GEOMETRY', '源旋转尚未连接浮点投影', asset_id=asset_id)
            spec = self.config['sources'][asset_id]
            required_decoder = _alpha_video_decoder({'probe': inspected})
            decoder = spec.get('decoder', required_decoder)
            if required_decoder and decoder != required_decoder:
                raise error('ALPHA', 'WebM透明源须使用保留alpha的解码器', asset_id=asset_id)
            source = self.stack.enter_context(NativeSurfaceSource(self.root, asset,
                source_signal=_signal(spec['source_signal'], asset_id), working_signal=self.config['working'],
                yuv_spec=YUVSpec(**spec['yuv_spec']) if spec.get('yuv_spec') is not None else None,
                scan=spec.get('scan'), demux_origin=spec.get('demux_origin'),
                alpha_association=spec.get('alpha_association', 'straight'),
                window_frames=self.config['window_frames'], cache_bytes=per_source, index_context=context,
                persist_index=not self.dry_run, decoder=decoder, cancel_file=self.marker,
                timeout=self.config['native_timeout_seconds']))
            self.sources[asset_id] = source
            self.metadata['source_receipts'][asset_id] = source.metadata
        from .float_gpu import FloatGPUSession
        self.gpu = self.stack.enter_context(FloatGPUSession(self.root, self.project['settings'],
            operation_id=self.operation_id, dry_run=self.dry_run, cancel=self.poll,
            timeout=self.config['native_timeout_seconds'], max_pixels=planned_pixels))
        if self.gpu.active:
            from .float_preview import runtime_paths
            paths = runtime_paths() | {Path(sys.executable).resolve(), Path('C:/Windows/System32/OpenCL.dll')}
            self.metadata['empty_numerical_package_markers'] = [str(p) for p in sorted(paths) if p.stat().st_size == 0]
            self.artifacts.extend(artifact_entry(p, 'float-gpu-numerical-runtime') for p in sorted(paths) if p.stat().st_size > 0)
        self.timeline = FloatTimeline(self.project, self.sequence['id'], self.sources,
            working_signal=self.config['working'], background_signal=self.config['background'], cancel=self.poll,
            max_working_bytes=self.config['projection_working_bytes_limit'],resource_root=self.root,gpu=self.gpu)
        self.artifacts.extend(self.timeline.text_host.artifacts.values())
        chains = [*self.timeline.effect_plans.values(), *(p.effects for p in self.timeline.adjustments.plans)]
        for dependency in self.timeline.effects.dependencies(chains):
            entry = artifact_entry(Path(dependency.path), 'float-effect-resource')
            if entry['sha256'] != dependency.sha256 or entry['bytes'] != dependency.size:
                raise error('INPUT_CHANGED', '浮点效果资源在编译与加锁之间变化', artifact=dependency.path)
            self.artifacts.append(entry)
        self.metadata.update(projection_working_bytes_limit=self.config['projection_working_bytes_limit'],
                             projection_budget_scope='each float projection/composite/delivery call; not total process RSS')
        self.metadata['timeline'] = self.timeline.metadata
        self.metadata['projection_acceleration'] = self.gpu.evidence

    def graph(self):
        from .float_audio_graph import prepare
        audio = prepare(self.root, self.project, self.sequence['id'], cancel_file=self.marker, persist_clock=not self.dry_run)
        canvas = self.project['settings']['canvas']
        number = audio['inputs'].count('-i')
        raw = ['-thread_queue_size', '2', '-f', 'rawvideo', '-pixel_format', 'gbrap16le',
               '-video_size', f'{canvas["width"]}x{canvas["height"]}', '-framerate', str(self.timeline.fps),
               '-color_range', 'pc', '-colorspace', 'rgb', '-color_primaries', 'bt709',
               '-color_trc', self.config['transfer_tag'], '-i', 'pipe:0']
        pixel = self.encoder['video']['pixel_format']
        transfer = {'linear': 'linear', 'srgb': 'iec61966-2-1', 'bt709-oetf': '709'}[self.config['output'].transfer]
        output_range = 'full' if self.config['output_range'] == 'pc' else 'limited'
        scale = (f'zscale=primariesin=709:transferin={transfer}:matrixin=gbr:rangein=full:'
                 f'primaries=709:transfer={transfer}:matrix=709:range={output_range}:chromal=left:dither=none')
        if self.config['alpha_output']:
            visual = (f'[{number}:v:0]split=2[float_rgb][float_a];'
                      '[float_a]alphaextract,format=gray[float_alpha];'
                      f'[float_rgb]format=gbrp16le,{scale},format=yuv420p[float_yuv];'
                      '[float_yuv][float_alpha]alphamerge,format=yuva420p[float_vout]')
        else:
            visual = f'[{number}:v:0]format=gbrp16le,{scale},format={pixel}[float_vout]'
        self.metadata.update(audio_project_sha256=audio['project_sha256'],
                             audio_samples_48000=audio['expected_samples_48000'],
                             delivery_pixel_format=pixel, alpha_quantization_bits=8 if self.config['alpha_output'] else None,
                             integer_colour_conversion='zscale explicit RGB full/BT709 YCbCr; unchanged transfer; left chroma',
                             source_lifecycle='original inputs locked through publication; providers closed on render context exit')
        self.audio_plan = audio
        meta = list(audio['metadata']) + [{'kind': 'float-native-video', 'float_pipeline': self.metadata}]
        return [*audio['inputs'], *raw], audio['filter_complex'] + ';' + visual, meta, list(audio['warnings'])

    def verify(self):
        self.poll()
        if self.timeline is not None and not self.sources_closed:
            self.timeline.verify_sources()
        for entry in self.artifacts:
            if 'sha256:' + sha256_file(Path(entry['path'])) != entry['sha256']:
                raise error('INPUT_CHANGED', '浮点渲染执行实现或工具发生变化', artifact=entry['path'])
        if self.timeline is not None and self.timeline.project != self.project:
            raise error('INPUT_CHANGED', '浮点渲染期间作者工程发生变化')

    def finish_sources(self):
        # The common verification scope still holds the original input handles
        # through publication. Record completed provider/process cleanup first.
        self.verify()
        self.stack.close()
        self.sources_closed = True
        self.metadata['providers_closed_before_publish'] = all(s.closed for s in self.sources.values())

    def publish(self, temporary, output, manifest, operation_id):
        """Rollback the movie/manifest pair on caught publication IO errors.

        Same-directory hard links retain old files without copying whole movies.
        This does not make the pair atomic across process termination/power loss.
        Backups survive if rollback itself fails; only owned paths are removed.
        """
        self.verify()
        manifest_path = output.with_suffix(output.suffix + '.manifest.json')
        staged = temporary.with_name('delivery-manifest.json')
        backups = {}
        installed = []
        try:
            atomic_write_json(staged, manifest)
            for target in (output, manifest_path):
                if target.exists():
                    backup = target.with_name('.' + target.name + '.' + operation_id + '.rollback')
                    os.link(target, backup)  # atomic no-clobber, same filesystem
                    backups[target] = backup
            self.poll()
            for source, target in ((temporary, output), (staged, manifest_path)):
                os.replace(source, target)
                installed.append(target)
        except OSError as exc:
            failures = []
            for target in reversed(installed):
                try:
                    if target in backups:
                        os.replace(backups[target], target)
                    else:
                        target.unlink()
                except OSError as rollback:
                    failures.append({'target': str(target), 'cause': str(rollback)})
            for backup in backups.values():
                if not failures:
                    backup.unlink(missing_ok=True)
            raise error('PUBLISH', '成片/manifest发布失败；已尝试恢复原文件',
                        cause=str(exc), rollback_failures=failures,
                        retained_backups=[str(p) for p in backups.values() if p.exists()]) from exc
        except BaseException:
            # Cancellation before replacements keeps the existing pair intact.
            for backup in backups.values():
                backup.unlink(missing_ok=True)
            raise
        self.published = True
        for backup in backups.values():
            try:
                backup.unlink()
            except OSError:
                self.metadata.setdefault('retained_publication_backups', []).append(str(backup))
        return manifest_path

    def run(self, command, *, timeout=3600):
        self.verify()
        payload = hashlib.sha256()
        stats = {'clipped_RGB_components': 0}
        frames = 0
        pipe = _EncoderPipe(command, cwd=self.root, cancel_file=self.marker, timeout=timeout)
        try:
            for index in range(self.timeline.frame_count):
                self.poll()
                pipe.check()
                surface, _ = self.timeline.render_frame(index)
                if not self.config['alpha_output'] and np.any(surface[:, :, 3] != 1):
                    raise error('ALPHA', '不透明输出不能丢弃实际alpha；请设置不透明背景或选择透明输出')
                delivered, _ = convert_rgba(surface, self.config['working'], self.config['output'],
                    max_working_bytes=self.config['projection_working_bytes_limit'], cancel=self.poll)
                for chunk in _chunks(delivered, range_policy=self.config['range_policy'], poll=pipe.check,
                                     stats=stats, alpha_bits=8 if self.config['alpha_output'] else 16):
                    payload.update(chunk)
                    pipe.put(chunk)
                frames += 1
            pipe.finish()
            self.verify()
            canvas = self.project['settings']['canvas']
            expected = frames * canvas['width'] * canvas['height'] * 8
            if pipe.bytes_written != expected:
                raise error('PAYLOAD', '原始浮点交付字节数量不一致')
            pipe.close()
            self.receipt = {'protocol': PROTOCOL, 'frames': frames, 'video_input_bytes': expected,
                'video_input_sha256': 'sha256:' + payload.hexdigest(), **stats,
                'RGB_quantization_bits': 16, 'alpha_quantization_bits': 8 if self.config['alpha_output'] else 16,
                'quantization': 'Float64 nearest-even at declared final delivery; alpha8 expanded by 257 for isolated alpha plane',
                'chunk_bytes': CHUNK_BYTES, 'stdin_queue_chunks': QUEUE_CHUNKS,
                'maximum_queued_chunks': pipe.maximum_queued_chunks, 'whole_movie_pixel_cache': False,
                'owned_process_pid': pipe.process.pid, 'owned_process_exit_code': pipe.process.returncode,
                'owned_threads_closed': all(not t.is_alive() for t in pipe.threads), 'network': False}
            self.metadata['transport'] = self.receipt
            return subprocess.CompletedProcess(command, 0, stdout='', stderr=pipe.stderr())
        finally:
            pipe.close()
