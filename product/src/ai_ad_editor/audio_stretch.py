"""Explicit local offline time stretching; plans never decode media."""
from __future__ import annotations

import array
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import tempfile

from .artifact_locks import artifact_entry, verification_scope
from .audio_channel_links import POLICY as CHANNEL_LINK_POLICY
from .errors import AppError
from .media import ffmpeg_path
from .policy import resolve_local_path
from .utils import atomic_write_text, run_process, sha256_file

ENGINE = 'rubberband-r3-offline-v1'
RATE = 48000
MAX_PCM_BYTES = 512 * 1024**2


def _error(code, message, field='settings.audio_stretch'):
    return AppError(code, message, exit_code=2, path=field)


def configuration(root: Path, raw) -> dict | None:
    if raw is None:
        return None
    allowed = {'engine', 'executable', 'sha256', 'dependencies', 'license_path', 'license_sha256', 'license_spdx', 'channel_mode', 'source_context_ms'}
    if not isinstance(raw, dict) or set(raw)-allowed or raw.get('engine') != ENGINE:
        raise _error('AUDIO_STRETCH_CONFIG_INVALID', 'audio_stretch 要求显式本地 rubberband-r3-offline-v1 配置')
    channel_mode = raw.get('channel_mode', 'together')
    if not isinstance(channel_mode, str) or channel_mode not in ('together', 'apart'):
        raise _error('AUDIO_STRETCH_CONFIG_INVALID', 'channel_mode 只接受 together 或 apart', 'settings.audio_stretch.channel_mode')
    context_ms = raw.get('source_context_ms', 0)
    if type(context_ms) is not int or not 0 <= context_ms <= 1000:
        raise _error('AUDIO_STRETCH_CONFIG_INVALID', 'source_context_ms 必须为 0..1000 的整数', 'settings.audio_stretch.source_context_ms')
    if not isinstance(raw.get('license_spdx'), str) or not raw['license_spdx'].strip():
        raise _error('AUDIO_STRETCH_CONFIG_INVALID', '需要记录本地伸缩工具的 license_spdx')
    dependencies = raw.get('dependencies')
    if not isinstance(dependencies, list) or not 0 <= len(dependencies) <= 32:
        raise _error('AUDIO_STRETCH_CONFIG_INVALID', 'dependencies 必须为最多 32 个本地依赖')
    values = [('executable', raw.get('executable'), raw.get('sha256')),
              ('license', raw.get('license_path'), raw.get('license_sha256'))]
    for item in dependencies:
        if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
            raise _error('AUDIO_STRETCH_CONFIG_INVALID', '每项 dependency 只接受 path 与 sha256')
        values.append(('dependency', item['path'], item['sha256']))
    artifacts = []
    for role, value, expected in values:
        if not isinstance(expected, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', expected):
            raise _error('AUDIO_STRETCH_CONFIG_INVALID', '伸缩工具及依赖须提供明确的 sha256: 摘要')
        path = resolve_local_path(root, value, field='settings.audio_stretch.'+role)
        if not path.is_file() or not 0 < path.stat().st_size <= 64*1024**2:
            raise _error('AUDIO_STRETCH_ARTIFACT_INVALID', '本地伸缩工具依赖必须为非空普通文件且不超过 64 MiB')
        entry = artifact_entry(path, 'audio-stretch-'+role)
        if entry['sha256'] != expected:
            raise AppError('AUDIO_STRETCH_HASH_MISMATCH', '本地伸缩工具或依赖 SHA-256 不匹配', exit_code=6, path=str(path))
        artifacts.append(entry)
    executable = Path(artifacts[0]['path'])
    if sys.platform == 'win32' and executable.suffix.lower() != '.exe':
        raise _error('AUDIO_STRETCH_ARTIFACT_INVALID', 'Windows 伸缩引擎要求已有原生 .exe')
    if sys.platform == 'win32':
        required = executable.with_name('sndfile.dll')
        if str(required) not in {a['path'] for a in artifacts[2:]}:
            raise _error('AUDIO_STRETCH_DEPENDENCY_MISSING', 'Windows Rubber Band CLI 的同目录 sndfile.dll 须显式登记摘要')
    return {'engine': ENGINE, 'executable': str(executable), 'artifacts': artifacts, 'channel_mode': channel_mode, 'source_context_ms': context_ms,
            'license_spdx': raw['license_spdx'].strip(), 'network': 'disabled'}


def plan(root: Path, engine: dict, asset: dict, source: Path, start: float, end: float,
         parts: list, duration: float, reverse: bool) -> dict:
    start_sample, end_sample = round(start*RATE), round(end*RATE)
    source_frames, target_frames = end_sample-start_sample, round(duration*RATE)
    channels = int((asset.get('probe', {}).get('audio') or {}).get('channels', 0))
    if not 1 <= channels <= 8 or min(source_frames, target_frames) < 1 or max(source_frames, target_frames)*channels*4 > MAX_PCM_BYTES:
        raise _error('AUDIO_STRETCH_BUDGET_EXCEEDED', '离线伸缩要求 1..8 声道、非空输入/输出及每份 PCM 不超过 512 MiB')
    anchors = [(0, 0)]
    for _, right, _, elapsed in parts:
        pair = (round(right*RATE), round(elapsed*RATE))
        if pair != anchors[-1]:
            anchors.append(pair)
    anchors[-1:] = [(source_frames, target_frames)] if len(anchors) > 1 else anchors[-1:]
    if len(anchors) == 1:
        anchors.append((source_frames, target_frames))
    if len(anchors) > 16385 or any(b[0] <= a[0] or b[1] <= a[1] for a, b in zip(anchors, anchors[1:])):
        raise _error('AUDIO_STRETCH_TIME_MAP_INVALID', '离线伸缩时间映射必须严格递增且不超过 16385 个锚点')
    context_ms = engine.get('source_context_ms', 0)
    head = tail = 0
    if context_ms:
        bound = (asset.get('probe') or {}).get('duration_seconds')
        if (type(bound) not in (int, float) or not math.isfinite(bound) or bound <= 0
                or start_sample < 0 or end_sample > math.floor(bound*RATE+1e-6)):
            raise _error('AUDIO_STRETCH_CONTEXT_BOUND_INVALID', '源上下文要求有限的已探测时长及有效选区')
        requested = context_ms*RATE//1000
        head = min(requested, start_sample)
        tail = min(requested, math.floor(bound*RATE+1e-6)-end_sample)
    first_slope = Fraction(anchors[1][1]-anchors[0][1], anchors[1][0]-anchors[0][0])
    last_slope = Fraction(anchors[-1][1]-anchors[-2][1], anchors[-1][0]-anchors[-2][0])
    head_out, tail_out = round(head*first_slope), round(tail*last_slope)
    if (head and head_out < 1) or (tail and tail_out < 1):
        raise _error('AUDIO_STRETCH_CONTEXT_GRID_INVALID', '上下文映射不足一个输出采样；未静默删除上下文')
    context_map = [(0, 0)] if head else []
    context_map.extend((a+head, b+head_out) for a,b in anchors)
    if tail:
        context_map.append((source_frames+head+tail, target_frames+head_out+tail_out))
    full_source, full_target = source_frames+head+tail, target_frames+head_out+tail_out
    if max(full_source, full_target)*channels*4 > MAX_PCM_BYTES:
        raise _error('AUDIO_STRETCH_BUDGET_EXCEEDED', '真实源上下文扩展后的每份 PCM 不能超过 512 MiB')
    context = {'requested_ms': context_ms, 'source_head_frames': head, 'source_tail_frames': tail,
               'output_head_frames': head_out, 'output_tail_frames': tail_out,
               'decode_start_sample': start_sample-head, 'decode_end_sample': end_sample+tail,
               'source_frames': full_source, 'target_frames': full_target, 'time_map': context_map,
               'edge_interval_output_per_source': [str(first_slope), str(last_slope)],
               'selection': 'real-source-handles-only-no-repetition-or-zero-padding',
               'author_output_frames': target_frames, 'output_crop': [head_out, head_out+target_frames]}
    implementation = 'sha256:'+sha256_file(Path(__file__))
    job = {'protocol': 'agent-video-offline-audio-stretch-v1', 'engine': engine,
           'source': str(source.resolve()), 'source_sha256': asset['sha256'],
           'source_start_sample': start_sample, 'source_end_sample': end_sample,
           'source_frames': source_frames, 'target_frames': target_frames,
           'channels': channels, 'sample_rate': RATE, 'time_map': anchors,
           'source_context': context,
           'source_audio_clock': 'native-decoded-audio-interval-clock-v1',
           'native_audio_clock_implementation':artifact_entry(Path(__file__).with_name('native_audio_clock.py'),'audio-clock-implementation'),
           'channel_link_policy': CHANNEL_LINK_POLICY,
           'channel_links_implementation': artifact_entry(Path(__file__).with_name('audio_channel_links.py'), 'audio-channel-links-implementation'),
           'reverse_after_stretch': bool(reverse), 'implementation_sha256': implementation,
           'ffmpeg': artifact_entry(Path(ffmpeg_path()).resolve(), 'audio-stretch-ffmpeg')}
    key = hashlib.sha256(json.dumps(job, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    job.update(key=key, output=str(root/'cache/audio-stretch'/f'{key}.wav'))
    return job


def inspect_pcm(path: Path) -> dict:
    """Stream native float WAV statistics without NumPy or loading whole clips."""
    with path.open('rb') as stream:
        head = stream.read(12)
        if len(head) != 12 or head[:4] != b'RIFF' or head[8:] != b'WAVE':
            raise _error('AUDIO_STRETCH_PCM_INVALID', '需要 RIFF/WAVE 本地浮点 PCM')
        channels = None;offset = size = None
        while header := stream.read(8):
            if len(header) != 8:
                raise _error('AUDIO_STRETCH_PCM_INVALID', 'WAV 区块头损坏')
            kind, length = struct.unpack('<4sI', header)
            if length > MAX_PCM_BYTES or stream.tell()+length > path.stat().st_size:
                raise _error('AUDIO_STRETCH_PCM_INVALID', 'WAV 区块长度或预算无效')
            if kind == b'fmt ':
                if not 16 <= length <= 4096:
                    raise _error('AUDIO_STRETCH_PCM_INVALID', 'WAV fmt 长度无效')
                fmt = stream.read(length);code, channels, rate, _, align, bits = struct.unpack('<HHIIHH', fmt[:16])
                if code == 0xfffe and len(fmt) >= 40:
                    code = struct.unpack('<I', fmt[24:28])[0]
                if code != 3 or not 1 <= channels <= 8 or rate != RATE or bits != 32 or align != channels*4:
                    raise _error('AUDIO_STRETCH_PCM_INVALID', '伸缩 PCM 须为 48 kHz/32-bit float、1..8 声道')
            elif kind == b'data':
                if offset is not None:
                    raise _error('AUDIO_STRETCH_PCM_INVALID', '不支持多个 WAV data 区块')
                offset, size = stream.tell(), length;stream.seek(length, 1)
            else:
                stream.seek(length, 1)
            if length % 2:
                stream.seek(1, 1)
        if channels is None or size is None or size == 0 or size % (channels*4):
            raise _error('AUDIO_STRETCH_PCM_INVALID', 'WAV 缺少有效 fmt/data')
        stream.seek(offset);remaining=size;nonzero=[0]*channels;squares=[0.]*channels;maximum=[0.]*channels
        while remaining:
            count=min(remaining, channels*4*65536);raw=stream.read(count)
            if len(raw) != count:
                raise _error('AUDIO_STRETCH_PCM_INVALID', 'WAV PCM 截断')
            values=array.array('f');values.frombytes(raw)
            if sys.byteorder != 'little':values.byteswap()
            for index,value in enumerate(values):
                if not math.isfinite(value):
                    raise _error('AUDIO_STRETCH_PCM_INVALID', 'WAV PCM 含 NaN/Inf')
                channel=index % channels;nonzero[channel]+=value != 0;squares[channel]+=value*value;maximum[channel]=max(maximum[channel],abs(value))
            remaining-=count
    frames=size//(channels*4)
    return {'frames': frames, 'channels': channels, 'sample_rate': RATE, 'data_offset':offset, 'data_bytes':size, 'nonzero_samples': nonzero,
            'rms': [math.sqrt(x/frames) for x in squares], 'maximum_absolute_sample': maximum,
            'sha256': 'sha256:'+sha256_file(path)}


def _canonical_pcm(source: Path, destination: Path, pcm: dict, *, start_frame=0, frames=None) -> None:
    # libsndfile's PEAK chunk includes wall time. Keep every PCM byte while
    # excluding time-dependent metadata from immutable derived WAV artifacts.
    frames = pcm['frames']-start_frame if frames is None else frames
    if (type(start_frame) is not int or type(frames) is not int or min(start_frame,frames)<0
            or not frames or start_frame+frames>pcm['frames']):
        raise _error('AUDIO_STRETCH_PCM_INVALID','PCM 选区必须位于实际解码采样内')
    channels=pcm['channels'];size=frames*channels*4
    fmt=struct.pack('<HHIIHH',3,channels,RATE,RATE*channels*4,channels*4,32)
    with source.open('rb') as src, destination.open('xb') as dst:
        dst.write(b'RIFF'+struct.pack('<I',size+36)+b'WAVEfmt '+struct.pack('<I',16)+fmt+b'data'+struct.pack('<I',size))
        src.seek(pcm['data_offset']+start_frame*channels*4);remaining=size
        while remaining:
            raw=src.read(min(remaining,1024*1024))
            if not raw:raise _error('AUDIO_STRETCH_PCM_INVALID','离线 PCM 规范化时输入截断')
            dst.write(raw);remaining-=len(raw)


def _decode_clocked_source(root,job,context,destination,cancel_file):
    from .native_audio_clock import normalized_input,verify_materialized
    from .media import probe_media
    with normalized_input(root,Path(job['source']),job['source_sha256'],persist=True,cancel_file=cancel_file) as clock:
        filters=[f'aresample={RATE}:osf=flt:first_pts=0']
        bound={'policy':'native-decoded-audio-end','padding_samples':0}
        native_end=round(Fraction(clock['stats']['logical_frames']*RATE,clock['stats']['native_sample_rate']))
        if context['decode_end_sample']>native_end:
            # A shorter audio stream may leave genuine silence inside a video
            # asset. Verify its video display end, rather than trusting an asset's
            # stored container duration or inventing source handles past EOF.
            actual=probe_media(Path(job['source']));author_end=native_end
            if actual.get('video',{}).get('codec'):
                from .multicam import _video_coverage
                coverage=_video_coverage(Path(job['source']),job['source_sha256'],project_root=root)
                author_end=max(author_end,math.floor(Fraction(coverage['end_seconds_rational'])*RATE))
                bound.update(policy='verified-native-audio-and-video-display-end',video_coverage=coverage)
            if context['decode_end_sample']>author_end:
                raise AppError('AUDIO_STRETCH_SOURCE_LENGTH_MISMATCH','作者音频范围超出实际源覆盖；未以补零伪造上下文',exit_code=6)
            bound.update(padding_samples=context['decode_end_sample']-native_end,verified_source_end_sample_48000=author_end)
            filters.append(f"apad=whole_len={context['decode_end_sample']}")
        filters.extend([f"atrim=start_sample={context['decode_start_sample']}:end_sample={context['decode_end_sample']}",'asetpts=N/SR/TB'])
        command=[job['ffmpeg']['path'],'-hide_banner','-loglevel','error','-y',*clock['input_args'],
            '-map','0:a:0','-vn','-af',','.join(filters),'-c:a','pcm_f32le',str(destination)]
        verify_materialized(root,[{'native_audio_clock':clock}],cancel_file=cancel_file)
        result=run_process(command,timeout=3600,cwd=root,cancel_file=cancel_file)
        verify_materialized(root,[{'native_audio_clock':clock}],cancel_file=cancel_file)
        return result,command,clock,bound


def execute(root: Path, job: dict, temp_dir: Path, *, cancel_file: Path | None = None) -> dict:
    """Study/process once per whole clip, and preserve immutable derived bytes."""
    with verification_scope():
        for expected in [*job['engine']['artifacts'], job['ffmpeg'],job['native_audio_clock_implementation'],job['channel_links_implementation'],
                         {'path': job['source'], 'sha256': job['source_sha256']}]:
            actual = artifact_entry(Path(expected['path']), 'audio-stretch-execution')
            if actual['sha256'] != expected['sha256']:
                raise AppError('AUDIO_STRETCH_HASH_MISMATCH', '离线伸缩输入或程序在规划后变化', exit_code=6, path=expected['path'])
        with tempfile.TemporaryDirectory(prefix='audio-stretch-', dir=str(temp_dir)) as scratch:
            work = Path(scratch);source=work/'input.wav';result=work/'output.wav';mapping=work/'time-map.txt'
            context=job.get('source_context') or {
                'source_frames':job['source_frames'],'target_frames':job['target_frames'],
                'decode_start_sample':job['source_start_sample'],'decode_end_sample':job['source_end_sample'],
                'source_head_frames':0,'source_tail_frames':0,'output_head_frames':0,
                'time_map':job['time_map']}
            # R3 treats 0 -> 0 as a zero-length ratio and can emit NaN.
            # Endpoints remain in the plan; only interior anchors go to CLI.
            engine_anchors=[(a,b) for a,b in context['time_map'] if 0<a<context['source_frames'] and 0<b<context['target_frames']]
            if context.get('requested_ms',0) and all(a*context['target_frames']==b*context['source_frames'] for a,b in engine_anchors):
                engine_anchors=[]
            mapping_text=''.join(f'{a} {b}\n' for a,b in engine_anchors)
            atomic_write_text(mapping, mapping_text)
            decoded,decode,native_clock,source_bound=_decode_clocked_source(root,job,context,source,cancel_file)
            if decoded.returncode != 0:
                raise AppError('AUDIO_STRETCH_DECODE_FAILED', '本地伸缩音频解码失败', exit_code=6, cause=decoded.stderr[-6000:])
            before=inspect_pcm(source)
            if before['frames'] != context['source_frames'] or before['channels'] != job['channels']:
                raise AppError('AUDIO_STRETCH_SOURCE_LENGTH_MISMATCH', '音频实际范围不足或声道与计划不符；不以补零替代输入', exit_code=6)
            context_input=before
            if context['source_head_frames'] or context['source_tail_frames']:
                selected_input=work/'selected-input.wav'
                _canonical_pcm(source,selected_input,before,start_frame=context['source_head_frames'],frames=job['source_frames'])
                before=inspect_pcm(selected_input)
            # R3's general stereo-phase tradeoff remains explicit. Exact source
            # copies/inversions are a stronger invariant and can be restored
            # without guessing a correlation or changing independent channels.
            from .audio_channel_links import detect_links, canonical_linked_pcm
            if job.get('channel_link_policy') != CHANNEL_LINK_POLICY:
                raise _error('AUDIO_CHANNEL_LINKS_INVALID', '离线计划的声道关系策略无效')
            channel_links = detect_links(source, context_input, cancel_file=cancel_file)
            channel_mode=job['engine'].get('channel_mode', 'together')
            if channel_mode not in ('together', 'apart'):
                raise _error('AUDIO_STRETCH_CONFIG_INVALID', '离线计划的 channel_mode 无效')
            command=[job['engine']['executable'], '-3', '--no-threads',
                     *(['--centre-focus'] if channel_mode == 'together' else []), '-q',
                     '-t', format(context['target_frames']/context['source_frames'], '.17g'),
                     *(['--timemap', str(mapping)] if engine_anchors else []), str(source), str(result)]
            processed=run_process(command, timeout=3600, cwd=root, cancel_file=cancel_file)
            if processed.returncode != 0 or not result.is_file() or 'NaN or Inf presented' in processed.stderr:
                raise AppError('AUDIO_STRETCH_FAILED', '本地 Rubber Band R3 离线执行失败', exit_code=6, cause=processed.stderr[-6000:])
            after=inspect_pcm(result)
            if after['frames'] != context['target_frames'] or after['channels'] != job['channels']:
                raise AppError('AUDIO_STRETCH_OUTPUT_LENGTH_MISMATCH', '离线伸缩输出采样数或声道错误；不静默补齐', exit_code=6, cause=json.dumps({'expected_frames':context['target_frames'],'actual_pcm':after,'engine_stderr':processed.stderr[-6000:]}))
            if cancel_file is not None and cancel_file.exists():
                raise AppError('CANCELLED', '离线伸缩结束后任务已取消', exit_code=8, path=str(cancel_file))
            raw_output=after;canonical=work/'canonical.wav'
            if channel_links['links']:
                channel_links = canonical_linked_pcm(result, canonical, raw_output, channel_links,
                    start_frame=context['output_head_frames'], frames=job['target_frames'], cancel_file=cancel_file)
            else:
                _canonical_pcm(result,canonical,raw_output,start_frame=context['output_head_frames'],frames=job['target_frames'])
            after=inspect_pcm(canonical)
            if any(a and not b for a,b in zip(before['nonzero_samples'],after['nonzero_samples'])):
                raise AppError('AUDIO_STRETCH_CONTENT_LOST', '离线伸缩将非零输入声道变为全静音', exit_code=6)
            output=Path(job['output']);output.parent.mkdir(parents=True,exist_ok=True)
            if output.exists():
                if 'sha256:'+sha256_file(output) != after['sha256']:
                    raise AppError('AUDIO_STRETCH_CACHE_CONFLICT', '相同计划的离线音频缓存字节不一致；保留原文件', exit_code=6, path=str(output))
            else:
                # CLI holds the project write lock; identical cached bytes
                # remain immutable when later controls or plans are built.
                os.replace(canonical,output)
            pinned=artifact_entry(output,'audio-stretch-output')
            if pinned['sha256'] != after['sha256']:
                raise AppError('AUDIO_STRETCH_HASH_MISMATCH', '离线音频缓存加锁时字节变化', exit_code=6, path=str(output))
            return {'status':'succeeded','decode_command':decode,'command':command,'channel_mode':channel_mode,
                    'decode_stderr':decoded.stderr,'engine_stderr':processed.stderr,
                    'input_pcm':before,'engine_raw_output_pcm':raw_output,'output_pcm':after,
                    'canonicalization':('float32-pcm-exact-channel-links-no-wall-time-metadata' if channel_links['links'] else 'float32-pcm-bytes-preserved-no-wall-time-metadata'),
                    'exact_channel_links':channel_links,'time_map_utf8':mapping_text,
                    'source_context':context,'context_input_pcm':context_input,
                    'native_audio_clock':native_clock,'source_clock_bound':source_bound,
                    'engine_time_map':engine_anchors,'time_map_sha256':'sha256:'+hashlib.sha256(mapping_text.encode('ascii')).hexdigest(),
                    'output_artifact':pinned,'pitch_and_listening_accepted':False,'stereo_phase_accepted':False}
