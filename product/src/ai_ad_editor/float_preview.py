"""Native Float32 timeline previews using the standard renderer's providers.

The range reference is straight BT.709 linear Float32 plus authored Float32
PCM. PNG is an explicit RGBA16 delivery; MP4 is a BT.709 viewing copy over
black. Neither the author project nor the default pixel pipeline is changed.
"""
import copy
import hashlib
from pathlib import Path

import numpy as np

from .float_audio_graph import prepare as prepare_audio
from .float_color_signal import ColorSignal, convert_rgba
from .float_hdr import LuminanceSignal, parse_signal, map_display
from .float_geometry import resample_rgba
from .float_standard_render import FloatRenderContext, configuration, error
from .float_stream import _EncoderPipe, _chunks, CHUNK_BYTES, QUEUE_CHUNKS
from .media import ffmpeg_path
from .render import output_settings
from .sequence_canvas import sequence_canvas

PROTOCOL = 'agent-native-float32-timeline-preview-v1'
REFERENCE_SIGNAL = ColorSignal('bt709', 'linear')


def runtime_paths():
    """Bind the actual local numerical implementation, including native DLLs."""
    package = Path(np.__file__).resolve().parent
    paths = {p for p in package.rglob('*') if p.is_file() and p.suffix in {'.py', '.pyd', '.dll'}}
    libraries = package.parent/'numpy.libs'
    if libraries.is_dir():
        paths.update(p for p in libraries.rglob('*.dll') if p.is_file())
    return paths


def reference_plan(project, mode):
    if mode not in {'frame', 'range'}:
        raise error('CONFIG', '浮点预览模式必须是frame/range')
    config = configuration(project['settings']['pixel_pipeline'], project['settings'], output_settings(project['settings']))
    mapping = config['mappings'].get('preview_mapping', config['mappings'].get('display_mapping'))
    origin = 'preview_mapping' if 'preview_mapping' in config['mappings'] else 'display_mapping'
    mapped = config['hdr_active'] or mapping is not None
    if mapped and mapping is None:
        raise error('HDR_PREVIEW', 'HDR工程预览须明确pixel_pipeline.preview_mapping；禁止默认截断或将PQ/HLG当作SDR图')
    signal = (LuminanceSignal('bt709', 'srgb' if mode == 'frame' else 'linear',
                  mapping['target_peak_nits']) if mapped
              else config['output'] if mode == 'frame' else REFERENCE_SIGNAL)
    return {'pixel_pipeline': config['engine'], 'pixel_protocol': PROTOCOL,
            'reference_pixel_format': 'rgba64be' if mode == 'frame' else 'gbrapf32le',
            'reference_signal': vars(signal),
            **({'display_mapping': mapping, 'display_mapping_source': origin, 'HDR_reference_preserved':False,
                 'reference_scope':'explicit SDR viewing trim; original HDR render and author graph unchanged'} if mapped else {}),
            'reference_bytes_per_pixel': 8 if mode == 'frame' else 16,
            'reference_resampling': 'premultiplied-linear-bilinear-after-full-author-composite'}


def _float_chunks(surface, *, range_policy, poll, stats):
    rows = surface.reshape(-1, 4)
    for channel in (1, 2, 0, 3):
        for start in range(0, len(rows), CHUNK_BYTES//4):
            poll()
            values = rows[start:start+CHUNK_BYTES//4, channel]
            outside = (values < 0) | (values > 1)
            if not np.isfinite(values).all():
                raise error('RANGE', '浮点预览包含非有限通道')
            if np.any(outside):
                if channel == 3 or range_policy == 'reject':
                    raise error('RANGE', '预览交付范围之外的RGB须显式选择clip策略')
                stats['clipped_RGB_components'] += int(np.count_nonzero(outside))
                values = np.clip(values, 0, 1)
            yield values.astype('<f4').tobytes()


class FloatPreviewContext:
    def __init__(self, root, project, sequence, request, *, cancel_file=None):
        effective = copy.deepcopy(project)
        effective['settings']['canvas'] = {**effective['settings']['canvas'], **sequence_canvas(project, sequence)}
        self.root = Path(root).resolve()
        self.request = request
        self.renderer = FloatRenderContext(self.root, effective, sequence, output_settings(effective['settings']), cancel_file=cancel_file)
        self.metadata = self.renderer.metadata
        self.metadata.update(protocol=PROTOCOL, source_render_protocol='standard-render-native-float32-v1',
            standard_render_selected=False, preview_selected=True,
            selected_author_frames=[request['start_frame'], request['end_frame']],
            reference_signal=request['reference_signal'], reference_pixel_format=request['reference_pixel_format'],
            reference_quantization_bits=16 if request['mode'] == 'frame' else None,
            reference_float_component_bits=32 if request['mode'] == 'range' else None,
            MP4_view={'primaries': 'bt709', 'transfer': 'bt709-oetf', 'matrix': 'bt709', 'range': 'limited',
                      'background': 'black-composited-in-linear-light', 'lossless': False},
            resampling=request['reference_resampling'], realtime_accepted=False)

    def __enter__(self):
        self.renderer.__enter__()
        return self

    def __exit__(self, kind, value, trace):
        # The caller verifies and closes providers before publishing its cache
        # directory. Do not re-poll cancellation after a successful publication.
        if kind is None and self.renderer.sources_closed:
            self.renderer.published = True
        return self.renderer.__exit__(kind, value, trace)

    def graph(self):
        r = self.renderer
        request = self.request
        audio = prepare_audio(self.root, r.project, r.sequence['id'], cancel_file=r.marker)
        self.audio = audio
        self.metadata.update(audio_project_sha256=audio['project_sha256'],
            audio_samples_48000=request['audio_samples_48000'], original_audio_graph_reused=True)
        number = audio['inputs'].count('-i')
        pixel_format = 'gbrap16le' if request['mode'] == 'frame' else 'gbrapf32le'
        preview_transfer = {'linear':'linear','srgb':'iec61966-2-1','bt709-oetf':'bt709'}[request['reference_signal']['transfer']]
        raw = ['-thread_queue_size', '2', '-f', 'rawvideo', '-pixel_format', pixel_format,
            '-video_size', f'{request["width"]}x{request["height"]}', '-framerate', str(r.timeline.fps),
            '-color_range', 'pc', '-colorspace', 'rgb', '-color_primaries', 'bt709',
            '-color_trc', preview_transfer, '-i', 'pipe:0']
        graph = audio['filter_complex'] + f';[{number}:v:0]null[preview_v]'
        if request['mode'] == 'frame' or request['audio_samples_48000'] == 0:
            graph += ';[aout]anullsink'
        else:
            graph += (f';[aout]atrim=start_sample={request["audio_start_sample_48000"]}:'
                f'end_sample={request["audio_end_sample_48000"]},asetpts=N/SR/TB[preview_a]')
        metadata = list(audio['metadata']) + [{'kind': 'float-native-preview', 'float_pipeline': self.metadata}]
        return [*audio['inputs'], *raw], graph, metadata, list(audio['warnings'])

    def command(self, inputs, graph, temporary):
        request = self.request
        args = [ffmpeg_path(), '-nostdin', '-hide_banner', '-y', '-loglevel', 'error',
            '-filter_complex_threads', '1', *inputs, '-filter_complex', graph, '-map', '[preview_v]']
        if request['mode'] == 'frame':
            name = 'frame.png'
            args += ['-frames:v', '1', '-c:v', 'png', '-pix_fmt', 'rgba64be', '-update', '1',
                '-color_primaries', 'bt709', '-color_trc', {'linear':'linear','srgb':'iec61966-2-1','bt709-oetf':'bt709'}[request['reference_signal']['transfer']],
                '-colorspace', 'rgb', '-color_range', 'pc', str(temporary/name)]
        else:
            name = 'master.nut'
            if request['audio_samples_48000']:
                args += ['-map', '[preview_a]', '-c:a', 'pcm_f32le']
            args += ['-c:v', 'rawvideo', '-pix_fmt', 'gbrapf32le', '-fps_mode', 'passthrough',
                '-color_primaries', 'bt709', '-color_trc', 'linear', '-colorspace', 'rgb', '-color_range', 'pc',
                '-f', 'nut', str(temporary/name)]
        return args, name

    def delivery_command(self, temporary):
        # zimg's linear -> 709 transfer uses its display-referred curve, which
        # differs from our declared BT.709 camera OETF. Apply that OETF explicitly
        # after linear-black composition; keep the zscale transfer unchanged.
        def oetf(channel):
            value = f'{channel}(X,Y)*alpha(X,Y)'
            expression = f'if(lt({value},0.018),4.5*({value}),1.099*pow({value},0.45)-0.099)'
            return "'"+expression+"'"
        opaque = ':'.join(f'{c}={oetf(c)}' for c in ('r', 'g', 'b'))
        scale = (f'geq={opaque}:a=1:interpolation=nearest,setparams=alpha_mode=straight,format=gbrpf32le,'
            'zscale=primariesin=709:transferin=709:matrixin=gbr:rangein=full:'
            'primaries=709:transfer=709:matrix=709:range=limited:chromal=left:dither=none,format=yuv420p')
        return [ffmpeg_path(), '-nostdin', '-hide_banner', '-y', '-loglevel', 'error',
            '-filter_complex_threads', '1', '-i', str(temporary/'master.nut'), '-vf', scale,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-pix_fmt', 'yuv420p',
            '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv',
            '-chroma_sample_location', 'left', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
            str(temporary/'preview.mp4')]

    def run(self, command):
        r, request = self.renderer, self.request
        r.verify()
        start, end = request['start_frame'], request['end_frame']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= r.timeline.frame_count:
            raise error('CLOCK', '预览区间不是有效的完整作者帧范围')
        target = parse_signal(request['reference_signal'])
        frames, payload = 0, hashlib.sha256()
        stats = {'clipped_RGB_components': 0}
        pipe = _EncoderPipe(command, cwd=self.root, cancel_file=r.marker, timeout=3600)
        try:
            for index in range(start, end):
                r.poll(); pipe.check()
                surface, _ = r.timeline.render_frame(index)
                signal = r.config['working']
                inherited = request.get('display_mapping_source') == 'display_mapping'
                if inherited:
                    # Match the actual SDR delivery edge before downsampling:
                    # mapping, proof and output conversion must not be omitted
                    # or applied twice. Resize in display-linear BT.709.
                    surface, boundary = r.delivery_surface(surface, stats=stats)
                    linear = LuminanceSignal('bt709', 'linear', request['display_mapping']['target_peak_nits'])
                    surface, _ = convert_rgba(surface, r.config['output'], linear,
                        max_working_bytes=r.config['projection_working_bytes_limit'], cancel=r.poll)
                    signal = linear
                    self.metadata['last_preview_mapping'] = r.metadata['last_display_mapping']
                    self.metadata['preview_delivery_boundary'] = boundary
                if not r.config['alpha_output'] and np.any(surface[:, :, 3] != 1):
                    raise error('ALPHA', '不透明作者输出不能在预览中静默丢弃alpha')
                height, width = surface.shape[:2]
                if (request['width'], request['height']) != (width, height):
                    sx, sy = width/request['width'], height/request['height']
                    surface, geometry = r.timeline.resample(surface, [request['width'], request['height']],
                        [[sx, 0, (sx-1)/2], [0, sy, (sy-1)/2]])
                    self.metadata['preview_geometry'] = geometry
                if 'display_mapping' in request and not inherited:
                    surface, signal, mapping = map_display(surface, signal, request['display_mapping'],
                        max_working_bytes=r.config['projection_working_bytes_limit'], cancel=r.poll, gpu=r.gpu)
                    self.metadata['last_preview_mapping'] = mapping
                    if 'perceptual_gamut' in mapping:
                        from .colour_audit import GAMUT_COUNTERS
                        for key in GAMUT_COUNTERS:
                            stats[key] = stats.get(key, 0) + mapping['perceptual_gamut'][key]
                    for key in ('negative_components_clipped','over_one_components_clipped','above_declared_peak_pixels'):
                        stats[key] = stats.get(key, 0) + mapping[key]
                if not inherited:
                    surface = r.proof_surface(surface,signal)
                delivered, _ = convert_rgba(surface, signal, target,
                    max_working_bytes=r.config['projection_working_bytes_limit'], cancel=r.poll)
                chunks = _chunks if request['mode'] == 'frame' else _float_chunks
                for block in chunks(delivered, range_policy=r.config['range_policy'], poll=pipe.check, stats=stats):
                    payload.update(block); pipe.put(block)
                frames += 1
            pipe.finish()
            r.verify()
            expected = frames*request['width']*request['height']*(8 if request['mode'] == 'frame' else 16)
            if pipe.bytes_written != expected:
                raise error('PAYLOAD', '预览实际像素字节数不符合作者帧范围')
            pipe.close()
            self.metadata['transport'] = {'frames': frames, 'selected_author_frames': [start, end],
                'video_input_bytes': expected, 'video_input_sha256': 'sha256:'+payload.hexdigest(), **stats,
                'chunk_bytes': CHUNK_BYTES, 'stdin_queue_chunks': QUEUE_CHUNKS,
                'maximum_queued_chunks': pipe.maximum_queued_chunks,
                'owned_process_pid': pipe.process.pid, 'owned_process_exit_code': pipe.process.returncode,
                'owned_threads_closed': all(not t.is_alive() for t in pipe.threads), 'whole_movie_pixel_cache': False}
            return pipe.stderr()
        finally:
            pipe.close()

    def finish_sources(self):
        self.renderer.finish_sources()
