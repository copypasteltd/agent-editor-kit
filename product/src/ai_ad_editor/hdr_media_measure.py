"""Read-only post-codec light metering with native PTS and explicit colour.

No frame-rate conversion, inferred mastering values or RGB16 requantization.
The metric is conditional on caller-declared signal and YCbCr interpretation.
"""
from fractions import Fraction
import hashlib
from pathlib import Path

import numpy as np

from .artifact_locks import artifact_entry, verification_scope
from .float_hdr import parse_signal
from .float_video_source import NativeRGBSource, cancelled, digest
from .float_yuv import YUVSpec
from .float_yuv_source import NativeYUVSource
from .hdr_measure import LightMeter, canonical, error
from .native_video_index import IndexContext
from .policy import resolve_local_path
from .reverse_video_clock import probe_frames

PROTOCOL = 'native-decoded-media-light-measure-v1'
MAX_FRAMES = 1000000


def prepare(root, value, signal, *, pixel_family='rgb', yuv=None, scan=None,
            region=None, range_policy='reject'):
    root = Path(root).resolve()
    source = resolve_local_path(root, value, field='surface.measure-media.input')
    if not source.is_file() or not source.is_relative_to(root):
        raise error('INPUT', '成片测量须是工程内现有本地文件')
    parsed = parse_signal(signal)
    # Validate explicit nit units and region shape without probing/decoding.
    if region is not None and (not isinstance(region, (list, tuple)) or len(region) != 4 or
            any(type(v) is not int for v in region) or min(region[:2]) < 0 or min(region[2:]) < 1):
        raise error('REGION', '有效画面范围须明确非负x/y及正整数宽高')
    LightMeter(parsed, 1, 1, quantize_rgb16=False)
    if pixel_family not in ('rgb', 'yuv') or range_policy not in ('reject', 'clip'):
        raise error('ARGUMENT', '须明确支持的原生像素族及量程策略')
    if pixel_family == 'yuv':
        if not isinstance(yuv, dict) or set(yuv) != {'matrix', 'range', 'chroma_location'} or scan != 'progressive':
            raise error('SIGNAL', 'YCbCr须明确matrix/range/chroma_location与progressive')
        YUVSpec(**yuv)
    elif yuv is not None or scan is not None:
        raise error('SIGNAL', 'RGB输入不能指定YCbCr语义')
    recipe = dict(protocol=PROTOCOL, source=str(source), source_sha256=digest(source),
                  signal=vars(parsed), pixel_family=pixel_family, YCbCr=yuv, scan=scan,
                  active_region_xywh=None if region is None else list(region), range_policy=range_policy)
    return dict(status='planned', recipe=recipe,
                recipe_sha256='sha256:' + hashlib.sha256(canonical(recipe)).hexdigest(),
                native_decode_started=False, dimensions_and_clock_verified=False,
                author_project_rewritten=False, new_media=False)


def _clock(pts, durations, time_base):
    if not 0 < len(pts) <= MAX_FRAMES or len(pts) != len(durations):
        raise error('BUDGET', '原生测量帧数超过预算或时钟不完整')
    if any(v <= 0 for v in durations) or time_base <= 0:
        raise error('CLOCK', '原生帧时长必须明确且为正；不由平均帧率猜测末帧')
    if any(b <= a for a, b in zip(pts, pts[1:])):
        raise error('CLOCK', '原生PTS须严格递增')
    gaps = overlaps = 0
    for i in range(len(pts) - 1):
        delta = pts[i + 1] - pts[i] - durations[i]
        gaps += int(delta > 0); overlaps += int(delta < 0)
    return dict(first_pts=int(pts[0]), last_pts=int(pts[-1]), time_base=str(time_base),
                native_span_seconds=str((int(pts[-1]) + int(durations[-1]) - int(pts[0])) * time_base),
                gaps_between_declared_exposures=gaps, overlaps_between_declared_exposures=overlaps,
                duration_weighting='sum of native frame durations; gaps not filled and overlaps not normalized')


def measure(root, plan, *, cancel_file=None, progress=None):
    root = Path(root).resolve()
    marker = resolve_local_path(root, cancel_file, field='surface.measure-media.cancel') if cancel_file else None
    poll = lambda: cancelled(marker)
    poll()
    recipe = plan['recipe']
    expected = prepare(root, recipe['source'], recipe['signal'], pixel_family=recipe['pixel_family'],
                       yuv=recipe['YCbCr'], scan=recipe['scan'], region=recipe['active_region_xywh'],
                       range_policy=recipe['range_policy'])
    if plan != expected:
        raise error('INPUT_CHANGED', '成片测量计划、信号或输入SHA变化')
    context = IndexContext(root, persist=False, cancel_file=marker)
    pts, durations, stream, _, index = context.acquire(Path(recipe['source']), recipe['source_sha256'], probe_frames)
    clock = _clock(pts, durations, Fraction(stream['time_base']))
    width, height = int(stream['width']), int(stream['height'])
    meter = LightMeter(parse_signal(recipe['signal']), width, height,
                       region=recipe['active_region_xywh'], cancel=poll, quantize_rgb16=False)
    # Includes reader surface and conservative row/tile temporary space. Not RSS/VRAM.
    estimated = width * height * 64 + width * 256 + 2 * len(pts) * 8
    if estimated > 768 * 1024**2:
        raise error('BUDGET', '成片测量自有工作区估算超过768MiB')
    source_type = NativeYUVSource if recipe['pixel_family'] == 'yuv' else NativeRGBSource
    kwargs = dict(spec=YUVSpec(**recipe['YCbCr']), scan=recipe['scan']) if recipe['pixel_family'] == 'yuv' else {}
    reader = source_type(root, recipe['source'], recipe['source_sha256'], index_context=context,
                         cancel_file=marker, **kwargs)
    pixels = hashlib.sha256(); clocks = hashlib.sha256()
    negative = over_one = 0
    with verification_scope():
        implementations = [artifact_entry(Path(__file__), 'media-light-measure'),
                           artifact_entry(Path(__file__).with_name('hdr_measure.py'), 'media-light-measure')]
        try:
            with reader:
                for frame in reader:
                    poll()
                    # Hash unmodified decoded RGBA, before any caller-authorized clipping.
                    pixels.update(frame.rgba.astype('<f4', copy=False).tobytes())
                    record = canonical(dict(frame=frame.index, pts=frame.pts, duration=frame.duration,
                                            time_base=str(frame.time_base)))
                    clocks.update(len(record).to_bytes(8, 'big')); clocks.update(record)
                    for row in frame.rgba:
                        poll()
                        negative += int(np.count_nonzero(row[:, :3] < 0))
                        over_one += int(np.count_nonzero(row[:, :3] > 1))
                    meter.add(frame.index, frame.rgba, frame.duration * frame.time_base,
                              range_policy=recipe['range_policy'])
                    if progress: progress(frame.index + 1, len(pts))
            poll()
            for row in implementations:
                if digest(row['path']) != row['sha256']:
                    raise error('INPUT_CHANGED', '成片测量实现字节发生变化')
            result = meter.result()
            result.update(protocol=PROTOCOL, status='measured', recipe=recipe, recipe_sha256=plan['recipe_sha256'],
                          native_clock=clock, index=index, all_source_frames_measured=meter.frames == len(pts),
                          full_canvas_measured=meter.region == [0, 0, width, height],
                          decoded_RGBA32_sha256='sha256:' + pixels.hexdigest(),
                          native_clock_sha256='sha256:' + clocks.hexdigest(),
                          range_counts=dict(policy=recipe['range_policy'], negative_components=negative,
                                            over_one_components=over_one, clipped_components=negative + over_one
                                            if recipe['range_policy'] == 'clip' else 0),
                          source_reader=reader.metadata, implementation_artifacts=implementations,
                          native_decoder_exit_code=reader.pipe.process.poll(),
                          owned_threads_terminated=all(not t.is_alive() for t in reader.pipe.threads),
                          estimated_operator_bytes=estimated, estimate_is_peak_RSS=False,
                          conditional_on_declared_signal=True, automatically_inferred_signal=False,
                          decoded_code_precision='native samples/explicit YCbCr reconstruction to Float32, then Float64 light math',
                          author_project_rewritten=False, new_media=False, audio_measured=False,
                          native_windows=True, network=False)
            return result
        finally:
            reader.close()
