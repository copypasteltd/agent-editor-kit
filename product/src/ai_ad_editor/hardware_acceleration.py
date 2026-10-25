"""Local, per-render hardware probes and bounded, auditable fallback.

Backend option strategy adapted from OpenFilm encoders.mjs at
f6a65ae54fa1c10ec482eeb84dc9ffa6ef33c4d8 (MIT).
Copyright (c) 2026 OpenFilm contributors. See OPENFILM_LICENSE.txt.
The policy, forced hardware-frame verification and integration are local work.
"""
from __future__ import annotations

import re
import sys
import json
from pathlib import Path

from .errors import AppError
from .media import classify_path, ffmpeg_path, ffprobe_path, probe_media
from .utils import atomic_write_json, atomic_write_text, run_process, sha256_file

MODES = ('off', 'prefer', 'require')
ENCODERS = ('auto', 'nvenc', 'qsv', 'amf', 'mf')
DECODERS = ('auto', 'd3d11va', 'cuda')
CLI_FIELDS = {'hardware_encode': 'encode', 'hardware_decode': 'decode',
              'hardware_encoder': 'encoder', 'hardware_decoder': 'decoder'}
DEFAULTS = dict(encode='off', decode='off', encoder='auto', decoder='auto', probe_max_bytes=512*1024**2)
CODECS = {'libx264': 'h264', 'libx265': 'hevc', 'libaom-av1': 'av1', 'libvpx-vp9': 'vp9', 'libvpx': 'vp8'}
# H.273 tables adapted from the attributed OpenFilm source above.
PRIMARIES = dict(bt709=1, bt470m=4, bt470bg=5, smpte170m=6, smpte240m=7, film=8, bt2020=9, smpte428=10, smpte431=11, smpte432=12)
PRIMARIES['jedec-p22'] = 22
TRANSFERS = {'bt709':1, 'gamma22':4, 'gamma28':5, 'smpte170m':6, 'smpte240m':7, 'linear':8,
    'log100':9, 'log316':10, 'iec61966-2-4':11, 'bt1361e':12, 'iec61966-2-1':13,
    'bt2020-10':14, 'bt2020-12':15, 'smpte2084':16, 'smpte428':17, 'arib-std-b67':18}
MATRICES = {'gbr':0, 'bt709':1, 'fcc':4, 'bt470bg':5, 'smpte170m':6, 'smpte240m':7, 'ycgco':8,
    'bt2020nc':9, 'bt2020c':10, 'smpte2085':11, 'chroma-derived-nc':12, 'chroma-derived-c':13, 'ictcp':14}


def color_bitstream_args(codec, settings):
    kind = CODECS.get(codec)
    if kind not in ('h264', 'hevc'):
        return []
    color = settings.get('color') or {}
    fields = []
    for key, table, option in [('primaries', PRIMARIES, 'colour_primaries'),
        ('transfer', TRANSFERS, 'transfer_characteristics'), ('matrix', MATRICES, 'matrix_coefficients')]:
        if color.get(key) in table:
            fields.append(option+'='+str(table[color[key]]))
    if color.get('range') in ('limited', 'full', 'tv', 'pc'):
        fields.append('video_full_range_flag='+('1' if color['range'] in ('full', 'pc') else '0'))
    return ['-bsf:v', kind+'_metadata='+':'.join(fields)] if fields else []


def color_frame_filter(settings):
    color = settings.get('color') or {}
    values = []
    for key, option in [('primaries', 'color_primaries'), ('transfer', 'color_trc'), ('matrix', 'colorspace'), ('range', 'range')]:
        value = color.get(key)
        if value is not None:
            value = str(value)
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
                raise AppError('COLOR_METADATA_INVALID', '色彩标签值无效', exit_code=2, path='settings.color.'+key)
            values.append(option+'='+value)
    return 'setparams='+':'.join(values) if values else 'null'


def tag_output_frames(graph, label, settings):
    marker = '['+label+']'
    if graph.count(marker) != 1:
        raise AppError('HARDWARE_GRAPH_INVALID', '成片输出 pad 不能唯一定位', exit_code=6)
    temporary = '[hardware_color_output]'
    return graph.replace(marker, temporary)+';'+temporary+color_frame_filter(settings)+marker


def configuration(raw=None):
    if raw is None:
        return dict(DEFAULTS)
    if not isinstance(raw, dict) or set(raw)-set(DEFAULTS):
        raise AppError('ACCELERATION_CONFIG_INVALID', 'acceleration 必须为受支持的严格对象', exit_code=2, path='settings.acceleration')
    value = {**DEFAULTS, **raw}
    for field, allowed in [('encode', MODES), ('decode', MODES), ('encoder', ENCODERS), ('decoder', DECODERS)]:
        if not isinstance(value[field], str) or value[field] not in allowed:
            raise AppError('ACCELERATION_CONFIG_INVALID', f'{field} 必须属于 {allowed}', exit_code=2, path='settings.acceleration.'+field)
    budget = value['probe_max_bytes']
    if type(budget) is not int or not 1024**2 <= budget <= 1024**3:
        raise AppError('ACCELERATION_CONFIG_INVALID', 'probe_max_bytes 必须为 1 MiB..1 GiB 整数', exit_code=2, path='settings.acceleration.probe_max_bytes')
    return value


def apply_overrides(settings, values):
    patch = {field: values[key] for key, field in CLI_FIELDS.items() if values.get(key) is not None}
    if values.get('hardware_probe_mib') is not None:
        mib = values['hardware_probe_mib']
        if type(mib) is not int or not 1 <= mib <= 1024:
            raise AppError('ACCELERATION_CONFIG_INVALID', 'hardware_probe_mib 必须为 1..1024 整数', exit_code=2)
        patch['probe_max_bytes'] = mib*1024**2
    config = configuration(settings.get('acceleration'))
    if patch:
        settings['acceleration'] = configuration({**config, **patch})
    return configuration(settings.get('acceleration'))


def encoder_candidates(codec, backend, platform=None):
    if (platform or sys.platform) != 'win32':
        return []
    kind = CODECS.get(codec)
    supported = {'h264': ('nvenc', 'qsv', 'amf', 'mf'), 'hevc': ('nvenc', 'qsv', 'amf', 'mf'),
                 'av1': ('nvenc', 'qsv', 'amf'), 'vp9': ('qsv',)}.get(kind, ())
    return [kind+'_'+item for item in supported if backend in ('auto', item)]


def hardware_options(encoder, bitrate, container):
    # Bitrate stays an explicit authored value. CRF is deliberately not translated.
    args = ['-c:v', encoder]
    if encoder.endswith('_nvenc'):
        args += ['-preset', 'p5', '-rc', 'vbr']
    elif encoder.endswith('_qsv'):
        args += ['-preset', 'medium']
    elif encoder.endswith('_amf'):
        args += ['-quality', 'quality', '-rc', 'vbr_peak']
    elif encoder.endswith('_mf'):
        args += ['-hw_encoding', '1', '-rate_control', 'u_vbr']
    args += ['-b:v', str(bitrate)]
    if encoder.startswith('hevc_') and container == 'mp4':
        args += ['-tag:v', 'hvc1']
    return args


def encoder_pixel_format(pixel_format):
    # Semiplanar input is the native Direct3D/NVENC transport. Planar CPU input
    # can pass a standalone probe but fail with a decoder-created D3D11 device.
    # This changes transport, never the required bitstream format/depth.
    return {'yuv420p': 'nv12', 'yuv420p10le': 'p010le'}.get(pixel_format, pixel_format)


def frame_hashes(stdout):
    # Include PTS, duration and byte count, not only pixel hashes.
    return [','.join(part.strip() for part in line.split(','))
            for line in stdout.splitlines() if line.strip() and not line.startswith('#')]


def download_filter(pix_fmt):
    return 'hwdownload,format='+('p010le' if pix_fmt == 'yuv420p10le' else 'nv12')+',format='+pix_fmt


def hardware_input_flags(backend):
    return ['-hwaccel', backend, '-hwaccel_output_format', 'd3d11' if backend == 'd3d11va' else 'cuda']


def rewrite_command(args, graph, selected_encoder, selected_decoders, video, container):
    result = list(args)
    if selected_encoder:
        start = result.index('-c:v', result.index('-filter_complex'))
        end = result.index('-pix_fmt', start)
        result[start:end] = hardware_options(selected_encoder, video['bitrate'], container)
        result[result.index('-pix_fmt', start)+1] = encoder_pixel_format(video['pixel_format'])
    # Input indices are the actual physical -i ordinals, including images/audio.
    positions = [i for i, value in enumerate(result) if value == '-i']
    for index, item in sorted(selected_decoders.items(), reverse=True):
        pos = positions[index]
        result[pos:pos] = hardware_input_flags(item['backend'])
    rewritten = graph
    prefixes = []
    for index, item in sorted(selected_decoders.items()):
        label = f'[hardware_input_{index}]'
        rewritten = rewritten.replace(f'[{index}:v]', label).replace(f'[{index}:v:0]', label)
        prefixes.append(f'[{index}:v]{download_filter(item["pix_fmt"])}{label}')
    if prefixes:
        rewritten = ';'.join(prefixes)+';'+rewritten
    result[result.index('-filter_complex')+1] = rewritten
    return result, rewritten


def hardware_failure(stderr):
    # Do not retry IO/content/quality failures just because a GPU was requested.
    text = stderr.lower()
    if any(word in text for word in ('no space left', 'permission denied', 'invalid data found', 'no such file', 'input/output error',
                                    'opencl', 'aek_projection')):
        return False
    return any(word in text for word in ('nvenc', 'cuda', 'cuvid', 'd3d11', 'qsv', 'mfx', 'amf',
                                        'hwdownload', 'hwaccel', 'hardware device', 'device lost', 'hw_encoding'))


class AccelerationSession:
    def __init__(self, root, settings, encoder, operation_id, cancel_file=None):
        self.root, self.settings, self.encoder = root, settings, encoder
        self.config = configuration(settings.get('acceleration'))
        self.enabled = any(self.config[key] != 'off' for key in ('encode', 'decode'))
        if self.config['encode'] != 'off' and not encoder['video'].get('bitrate'):
            raise AppError('ACCELERATION_BITRATE_REQUIRED', '硬件编码必须显式提供视频码率', exit_code=2, path='settings.output.video.bitrate')
        # Render diagnostics are side effects, outside authoring-metadata rollback.
        # Failed/cancelled CLI transactions must retain full logs, not just a JSON tail.
        self.directory = root/'renders'/'diagnostics'/('acceleration_'+operation_id)
        self.path = self.directory/'report.json'
        self.cancel_file = cancel_file
        self.selected_encoder = None
        self.selected_decoders = {}
        self.evidence = {'version': '1', 'request': self.config, 'status': 'planned', 'probes': [], 'attempts': [],
                         'decisions': [], 'device': 'driver-default; identity not certified',
                         'report': str(self.path) if self.enabled else None}

    def save(self):
        if self.enabled:
            self.evidence['selected_encoder'] = self.selected_encoder
            self.evidence['selected_decoders'] = {str(k): v for k, v in self.selected_decoders.items()}
            atomic_write_json(self.path, self.evidence)

    def command(self, args, label, *, timeout=30, attempt=False):
        record = {'id': label, 'command': args, 'status': 'running'}
        self.evidence['attempts' if attempt else 'probes'].append(record)
        self.save()
        try:
            result = run_process(args, cwd=self.root, timeout=timeout, cancel_file=self.cancel_file)
        except AppError as exc:
            record.update(status='interrupted', error=exc.as_dict(), stderr_scope='partial executor tail')
            self.save()
            raise
        for name in ('stdout', 'stderr'):
            path = self.directory/(label+'.'+name+'.log')
            atomic_write_text(path, getattr(result, name) or '')
            record[name] = {'path': str(path), 'sha256': sha256_file(path), 'scope': 'complete decoded UTF-8, replacement on errors'}
        record.update(status='completed', returncode=result.returncode)
        self.save()
        return result

    def decision(self, axis, reason, **details):
        self.evidence['decisions'].append({'axis': axis, 'reason': reason, **details})
        self.save()
        if self.config[axis] == 'require':
            raise AppError('HARDWARE_REQUIRED_UNAVAILABLE', f'必须硬件{axis}，但当前候选不满足要求', exit_code=6, path=str(self.path), cause=reason)

    def budget(self, width, height, pix_fmt):
        # Conservative RGBA16 four-frame estimate, independent of compressed size.
        estimate = width*height*8*4
        return 0 < estimate <= self.config['probe_max_bytes']

    def verify_output(self, probe, path=None):
        video = probe.get('video', {})
        expected = self.encoder['video']
        canvas = self.settings['canvas']
        mismatches = {key: (video.get(key), value) for key, value in {
            'codec': CODECS[expected['codec']], 'pix_fmt': expected['pixel_format'],
            'width': canvas['width'], 'height': canvas['height']}.items() if video.get(key) != value}
        stream = next((s for s in probe.get('streams', []) if s.get('codec_type') == 'video'), {})
        frame = {}
        if path is not None and self.settings.get('color'):
            result = self.command([ffprobe_path(), '-v', 'error', '-protocol_whitelist', 'file,pipe',
                '-select_streams', 'v:0', '-read_intervals', '%+#16', '-show_frames', '-show_entries',
                'frame=color_primaries,color_transfer,color_space,color_range', '-of', 'json', str(path)],
                'color-metadata-'+str(len(self.evidence['probes'])))
            try:
                frame = json.loads(result.stdout)['frames'][0] if result.returncode == 0 else {}
            except (ValueError, KeyError, IndexError, TypeError):
                frame = {}
            probe['hardware_decoded_color_frame'] = frame
        if (expected['pixel_format'] == 'yuva420p' and video.get('pix_fmt') == 'yuv420p' and
            str(stream.get('tags', {}).get('alpha_mode', '0')) == '1'):
            mismatches.pop('pix_fmt', None)
        for key, field in [('primaries', 'color_primaries'), ('transfer', 'color_transfer'), ('matrix', 'color_space'), ('range', 'color_range')]:
            value = (self.settings.get('color') or {}).get(key)
            if value is not None:
                value = {'limited': 'tv', 'full': 'pc'}.get(value, value) if key == 'range' else value
                actual = stream.get(field, frame.get(field))
                if actual != value or (path is not None and frame.get(field) != value):
                    mismatches[field] = ({'stream': stream.get(field), 'decoded_frame': frame.get(field)}, value)
        if mismatches:
            raise AppError('HARDWARE_OUTPUT_MISMATCH', '编解码输出改变了声明的格式或色彩标签', exit_code=6, cause=str(mismatches))

    def prepare(self, inputs, input_meta, project, temp_dir, color_args):
        if not self.enabled:
            return
        self.evidence['status'] = 'probing'
        ffmpeg = ffmpeg_path()
        self.evidence['ffmpeg'] = {'path': ffmpeg, 'sha256': sha256_file(Path(ffmpeg))}
        self.save()
        if self.config['encode'] != 'off':
            video, canvas = self.encoder['video'], self.settings['canvas']
            candidates = encoder_candidates(video['codec'], self.config['encoder'])
            if 'a' in video['pixel_format'] or not self.budget(canvas['width'], canvas['height'], video['pixel_format']):
                candidates = []
            listing = self.command([ffmpeg, '-hide_banner', '-encoders'], 'encoder-list')
            fps = self.settings['timebase']['display_fps']
            for i, candidate in enumerate(candidates):
                if not re.search(r'\b'+re.escape(candidate)+r'\b', listing.stdout):
                    continue
                target = temp_dir/f'encoder-probe-{i}.mkv'
                args = [ffmpeg, '-hide_banner', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                        f'testsrc2=size={canvas["width"]}x{canvas["height"]}:rate={fps["num"]}/{fps["den"]}',
                        '-frames:v', '4', '-an', '-vf', color_frame_filter(self.settings), *hardware_options(candidate, video['bitrate'], 'mkv'),
                        '-pix_fmt', encoder_pixel_format(video['pixel_format']), *color_args,
                        *color_bitstream_args(video['codec'], self.settings), '-f', 'matroska', str(target)]
                result = self.command(args, f'encoder-{i}')
                if result.returncode:
                    continue
                inspected = probe_media(target)
                encoder_record = self.evidence['probes'][-1]
                encoder_record['probe'] = inspected
                try:
                    self.verify_output(inspected, target)
                except AppError as exc:
                    if exc.code in ('CANCELLED', 'PROCESS_TIMEOUT', 'PROCESS_START_FAILED'):
                        raise
                    encoder_record['rejected'] = exc.as_dict()
                    self.save()
                    continue
                self.selected_encoder = candidate
                break
            if not self.selected_encoder:
                self.decision('encode', 'no verified encoder for actual raster, pixel format, color and budget')
        if self.config['decode'] != 'off':
            paths = [inputs[i+1] for i, value in enumerate(inputs) if value == '-i']
            assets = {a.get('id'): a for a in project.get('assets', [])}
            indices = sorted({m['input'] for m in input_meta if m.get('kind') == 'video' and type(m.get('input')) is int
                              and assets.get(m.get('asset_id'), {}).get('kind') != 'image'})
            for index in indices:
                path = Path(paths[index])
                if not path.is_absolute():
                    path = self.root/path
                if classify_path(path) == 'image':
                    continue
                inspected = probe_media(path)
                video = inspected['video']; pix_fmt = video.get('pix_fmt')
                stream = next((s for s in inspected.get('streams', []) if s.get('codec_type') == 'video'), {})
                if (video.get('codec') not in ('h264', 'hevc', 'vp9', 'av1', 'mpeg2video') or
                    pix_fmt not in ('yuv420p', 'yuv420p10le') or
                    str(stream.get('tags', {}).get('alpha_mode', '0')) == '1' or
                    not self.budget(video.get('width', 0), video.get('height', 0), pix_fmt)):
                    self.decision('decode', 'source codec, alpha, pixel format or budget unsupported', input=index)
                    continue
                common = ['-i', str(path), '-map', '0:v:0', '-frames:v', '4', '-an', '-sn', '-dn']
                cpu = self.command([ffmpeg, '-hide_banner', '-loglevel', 'error', '-hwaccel', 'none', *common,
                                    '-pix_fmt', pix_fmt, '-f', 'framemd5', '-'], f'decode-{index}-cpu')
                if cpu.returncode or not frame_hashes(cpu.stdout):
                    raise AppError('HARDWARE_SOURCE_PROBE_FAILED', 'CPU 无法解码探测输入，拒绝硬件重试', exit_code=6, path=str(path))
                candidates = ['d3d11va', 'cuda'] if sys.platform == 'win32' else []
                if self.config['decoder'] != 'auto':
                    candidates = [c for c in candidates if c == self.config['decoder']]
                for candidate in candidates:
                    result = self.command([ffmpeg, '-hide_banner', '-loglevel', 'error', *hardware_input_flags(candidate),
                                           *common, '-vf', download_filter(pix_fmt), '-pix_fmt', pix_fmt,
                                           '-f', 'framemd5', '-'], f'decode-{index}-{candidate}')
                    same = result.returncode == 0 and frame_hashes(result.stdout) == frame_hashes(cpu.stdout)
                    self.evidence['probes'][-1]['matches_cpu'] = same
                    if same:
                        self.selected_decoders[index] = {'backend': candidate, 'pix_fmt': pix_fmt,
                            'source': str(path), 'sha256': sha256_file(path), 'frames_compared': len(frame_hashes(cpu.stdout))}
                        break
                if index not in self.selected_decoders:
                    self.decision('decode', 'no forced hardware-frame decoder matches CPU probe', input=index)
            if not indices:
                self.evidence['decisions'].append({'axis': 'decode', 'reason': 'no applicable file-video inputs', 'status': 'not_applicable'})
        self.evidence['status'] = 'prepared'
        self.save()

    def execute(self, args, graph, transport, check_inputs):
        if not self.enabled:
            executed, graph_transport = transport(args, graph)
            return run_process(executed, timeout=3600, cwd=self.root, cancel_file=self.cancel_file), executed, graph_transport
        for attempt in range(3):
            check_inputs()
            variant, rewritten = rewrite_command(args, graph, self.selected_encoder, self.selected_decoders,
                                                 self.encoder['video'], self.encoder['container'])
            variant[-1:-1] = color_bitstream_args(self.encoder['video']['codec'], self.settings)
            executed, graph_transport = transport(variant, rewritten)
            self.evidence['status'] = 'rendering'
            result = self.command(executed, f'render-{attempt}', timeout=3600, attempt=True)
            self.evidence['attempts'][-1].update(encoder=self.selected_encoder or self.encoder['video']['codec'],
                decoders={str(k): v['backend'] for k, v in self.selected_decoders.items()})
            self.save()
            if result.returncode == 0:
                self.evidence['status'] = 'encoded_pending_quality'
                self.save()
                return result, executed, graph_transport
            if not hardware_failure(result.stderr):
                break
            if self.selected_decoders and self.config['decode'] == 'prefer':
                self.selected_decoders = {}
                self.decision('decode', 'runtime hardware failure; retry with CPU decode')
            elif self.selected_encoder and self.config['encode'] == 'prefer':
                self.selected_encoder = None
                self.decision('encode', 'runtime hardware failure; retry with CPU encode')
            else:
                break
        return result, executed, graph_transport
