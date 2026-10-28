"""All-frame authored-delivery metering, with explicit nits and no hidden mastering.

Measures exactly the common encoder's RGB16 input, before codec/YUV conversion.
MaxRGB and CIE Y are reported separately; neither is a measured physical display.
"""
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .artifact_locks import artifact_entry, verification_scope
from .colour_audit import ColourAudit
from .errors import AppError
from .float_audio_graph import project_digest
from .float_chromatic import white_of
from .float_color_signal import _rgb_to_xyz
from .float_hdr import has_luminance, to_linear
from .float_standard_render import FloatRenderContext, configuration
from .float_stream import _chunks
from .native_audio_clock import cancel
from .render import output_settings
from .sequence_canvas import sequence_canvas
from .utils import sha256_file

PROTOCOL = 'authored-delivery-rgb16-light-measure-v1'
MAX_WORKING_BYTES = 768 * 1024**2
TILE_PIXELS = 65536


def error(code, message, **details):
    return AppError('HDR_MEASURE_' + code, message, exit_code=2, diagnostics=details or None)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


class LightMeter:
    """One bounded row/tile at a time; no movie or per-frame result cache."""
    def __init__(self, signal, width, height, *, region=None, cancel=None, quantize_rgb16=True):
        if not has_luminance(signal): raise error('SIGNAL', '测量须明确输出reference_white_nits，禁止由标签推断')
        if any(type(v) is not int or v < 1 or v > 16384 for v in (width, height)) or width * height > 16777216:
            raise error('BUDGET', '测量表面尺寸超出预算')
        region = [0, 0, width, height] if region is None else region
        if (not isinstance(region, (list, tuple)) or len(region) != 4 or
                any(type(v) is not int for v in region)):
            raise error('REGION', '有效画面范围须明确整数x/y/width/height')
        x, y, w, h = region
        if min(x, y) < 0 or min(w, h) < 1 or x + w > width or y + h > height:
            raise error('REGION', '有效画面范围必须完全位于画布内')
        if type(quantize_rgb16) is not bool: raise error('ARGUMENT', 'RGB16量化模式须为布尔值')
        self.quantize_rgb16 = quantize_rgb16
        self.signal, self.width, self.height = signal, width, height
        self.region = list(region)
        self.poll = cancel or (lambda: None)
        self.weights = _rgb_to_xyz(signal.primaries, white_of(signal))[1]
        self.frames = 0
        self.first = self.last = None
        self.duration = Fraction(0)
        self.weighted = {'maxrgb': 0., 'cie_y': 0.}
        self.peaks = {}
        self.falls = {}
        self.frame_hash = hashlib.sha256()
        self.minimum = math.inf

    def add(self, index, surface, duration, *, range_policy='reject'):
        if type(index) is not int or index < 0 or (self.last is not None and index != self.last + 1):
            raise error('CLOCK', '测量要求连续且严格递增的作者帧号')
        if not isinstance(duration, Fraction) or duration <= 0:
            raise error('CLOCK', '每帧时长必须是正的有理数')
        if (not isinstance(surface, np.ndarray) or surface.dtype != np.float32 or
                surface.shape != (self.height, self.width, 4)):
            raise error('SURFACE', '测量须为声明尺寸的Float32 RGBA表面')
        if range_policy not in ('reject', 'clip'): raise error('RANGE', '量程策略须明确reject或clip')
        x, y, w, h = self.region
        sums = {'maxrgb': [], 'cie_y': []}
        frame_peaks = {}
        # Validate alpha/full canvas, including outside the selected active area.
        for row in surface:
            self.poll()
            if not np.isfinite(row).all() or np.any(row[:, 3] != 1):
                raise error('ALPHA', '光量测量要求有限且完全不透明的最终输出；先明确合成背景')
            if range_policy == 'reject' and np.any((row[:, :3] < 0) | (row[:, :3] > 1)):
                raise error('RANGE', '测量须遵守真实整数交付的reject量程策略')
        for row_index in range(y, y + h):
            for column in range(x, x + w, TILE_PIXELS):
                self.poll()
                values = surface[row_index, column:min(column + TILE_PIXELS, x + w), :3].astype(np.float64)
                values = np.clip(values, 0, 1)
                if self.quantize_rgb16: values = np.rint(values * 65535) / 65535
                rgb = to_linear(values, self.signal) * self.signal.reference_white_nits
                if not np.isfinite(rgb).all() or np.any(rgb < 0):
                    raise error('DOMAIN', '交付光量必须是有限非负的显示线性nit')
                self.minimum = min(self.minimum, float(np.min(rgb)))
                metrics = {'maxrgb': np.max(rgb, axis=1),
                           'cie_y': rgb[:, 0] * self.weights[0] + rgb[:, 1] * self.weights[1] + rgb[:, 2] * self.weights[2]}
                for key, values in metrics.items():
                    # fsum combines fixed row/tile reductions without retaining frames.
                    sums[key].append(float(np.sum(values, dtype=np.float64)))
                    pixel = int(np.argmax(values)); value = float(values[pixel])
                    if key not in frame_peaks or value > frame_peaks[key]['nits']:
                        frame_peaks[key] = dict(nits=value, frame=index, x=column + pixel, y=row_index)
        averages = {key: math.fsum(values) / (w * h) for key, values in sums.items()}
        for key, peak in frame_peaks.items():
            if key not in self.peaks or peak['nits'] > self.peaks[key]['nits']: self.peaks[key] = peak
            if key not in self.falls or averages[key] > self.falls[key]['nits']:
                self.falls[key] = dict(nits=averages[key], frame=index)
            self.weighted[key] += averages[key] * float(duration)
        receipt = dict(frame=index, duration_seconds=str(duration), peaks=frame_peaks, averages=averages)
        encoded = canonical(receipt)
        self.frame_hash.update(len(encoded).to_bytes(8, 'big')); self.frame_hash.update(encoded)
        self.duration += duration
        if self.first is None: self.first = index
        self.last = index
        self.frames += 1

    def result(self):
        if not self.frames: raise error('EMPTY', '没有完整测量帧，禁止返回部分峰值')
        return dict(protocol=PROTOCOL, frames=self.frames, first_frame=self.first, last_frame=self.last,
                    active_region_xywh=list(self.region), active_pixels_per_frame=self.region[2] * self.region[3],
                    analyzed_duration_seconds=str(self.duration), minimum_RGB_component_nits=self.minimum,
                    peak_pixel=self.peaks, maximum_frame_average=self.falls,
                    duration_weighted_frame_average_nits={k: v / float(self.duration) for k, v in self.weighted.items()},
                    framed_metrics_sha256='sha256:' + self.frame_hash.hexdigest(),
                    input_signal=vars(self.signal), RGB16_quantization=('Float64 nearest-even; exactly common encoder input' if self.quantize_rgb16 else 'none; native decoded Float32 code values promoted to Float64'),
                    metric_definitions={'maxrgb': 'max of decoded display-linear R/G/B nit components at each pixel',
                                        'cie_y': 'decoded display-linear RGB dot declared-primary XYZ Y row in nits'},
                    measurement_edge=('after display mapping, native proof, signal conversion, range policy and RGB16 quantization; before YUV/codec' if self.quantize_rgb16 else 'after native media decode and explicit YCbCr reconstruction; no RGB16 requantization'),
                    codec_output_measured=not self.quantize_rgb16, automatically_written_SEI=False, filtered_outliers=False,
                    whole_movie_pixel_cache=False, HDR_monitor_accepted=False)


def prepare(project, sequence_id, *, start_frame=0, stop_frame=None, region=None):
    sequence = next((s for s in project['sequences'] if s['id'] == sequence_id), None)
    if sequence is None: raise error('SEQUENCE', '测量序列不存在')
    encoder = output_settings(project['settings'])
    cfg = configuration(project['settings'].get('pixel_pipeline'), project['settings'], encoder)
    # An ACES scene-relative input has no display-light nit unit. Its explicit
    # Output Transform defines the display edge; only that output needs nits.
    # Other pipelines retain the existing two-sided display-light contract.
    if not has_luminance(cfg['output']) or (not has_luminance(cfg['working']) and 'aces_display' not in cfg):
        raise error('SIGNAL', '测量须明确输出reference_white_nits；非ACES工作域也须明确亮度单位')
    if cfg['alpha_output']: raise error('ALPHA', '光量测量要求不透明交付；透明交付须先明确背景')
    canvas = sequence_canvas(project, sequence); width, height = canvas['width'], canvas['height']
    meter = LightMeter(cfg['output'], width, height, region=region)
    fps = Fraction(project['settings']['timebase']['display_fps']['num'], project['settings']['timebase']['display_fps']['den'])
    duration = Fraction(sequence['duration_tick'], project['settings']['timebase']['ticks_per_second'])
    count = math.ceil(duration * fps); stop = count if stop_frame is None else stop_frame
    if any(type(v) is not int for v in (start_frame, stop)) or not 0 <= start_frame < stop <= count or stop - start_frame > 1000000:
        raise error('CLOCK', '测量须为有效且有界的半开CFR帧区间')
    estimate = 2 * width * height * 16 + min(width, TILE_PIXELS) * 256 + height * 64 + 4096
    if estimate > MAX_WORKING_BYTES: raise error('BUDGET', '测量自有表面与分块估算超过768MiB')
    recipe = dict(protocol=PROTOCOL, project_sha256=project_digest(project), sequence_id=sequence_id,
                  start_frame=start_frame, stop_frame_exclusive=stop, total_timeline_frames=count,
                  fps=str(fps), authored_duration_seconds=str(duration), width=width, height=height,
                  active_region_xywh=meter.region, estimated_operator_bytes=estimate,
                  estimate_is_peak_RSS=False, output_signal=vars(cfg['output']))
    return dict(status='planned', recipe=recipe, recipe_sha256='sha256:' + hashlib.sha256(canonical(recipe)).hexdigest(),
                native_decode_started=False, author_project_rewritten=False, new_media=False)


def measure(root, project, plan, *, cancel_file=None, progress=None):
    recipe = plan['recipe']; root = Path(root).resolve(); poll = lambda: cancel(cancel_file)
    poll()
    if plan['recipe_sha256'] != 'sha256:' + hashlib.sha256(canonical(recipe)).hexdigest():
        raise error('RECIPE', '测量配方摘要变化')
    if recipe['project_sha256'] != project_digest(project): raise error('INPUT_CHANGED', '测量计划后的作者工程变化')
    # Revalidate caller-visible plan, including geometry, region and all budgets.
    expected = prepare(project, recipe['sequence_id'], start_frame=recipe['start_frame'],
                       stop_frame=recipe['stop_frame_exclusive'], region=recipe['active_region_xywh'])
    if expected != plan: raise error('RECIPE', '测量计划与当前完整上下文不一致')
    sequence = next(s for s in project['sequences'] if s['id'] == recipe['sequence_id'])
    payload = hashlib.sha256(); audit = ColourAudit(); stats = {'clipped_RGB_components': 0}
    with verification_scope():
        artifacts = [artifact_entry(Path(__file__), 'light-measure-implementation'),
                     artifact_entry(Path(__file__).with_name('colour_audit.py'), 'light-measure-implementation')]
        with FloatRenderContext(root, project, sequence, output_settings(project['settings']), cancel_file=cancel_file) as renderer:
            meter = LightMeter(renderer.config['output'], recipe['width'], recipe['height'], region=recipe['active_region_xywh'], cancel=poll)
            fps = Fraction(recipe['fps']); duration = Fraction(recipe['authored_duration_seconds'])
            for index in range(recipe['start_frame'], recipe['stop_frame_exclusive']):
                poll(); surface, _ = renderer.timeline.render_frame(index)
                delivered, boundary = renderer.delivery_surface(surface, stats=stats)
                audit.add(index, boundary)
                for chunk in _chunks(delivered, range_policy=renderer.config['range_policy'], poll=poll, stats=stats): payload.update(chunk)
                dt = min(Fraction(1, 1) / fps, duration - Fraction(index, 1) / fps)
                meter.add(index, delivered, dt, range_policy=renderer.config['range_policy'])
                if progress: progress(index - recipe['start_frame'] + 1, recipe['stop_frame_exclusive'] - recipe['start_frame'])
            renderer.finish_sources()
            metadata = renderer.metadata
        poll()
        if recipe['project_sha256'] != project_digest(project): raise error('INPUT_CHANGED', '测量期间作者工程变化')
        for row in artifacts:
            if 'sha256:' + sha256_file(Path(row['path'])) != row['sha256']: raise error('INPUT_CHANGED', '测量实现字节变化')
        result = meter.result()
        result.update(status='measured', recipe=recipe, recipe_sha256=plan['recipe_sha256'],
                      all_timeline_frames_measured=recipe['start_frame'] == 0 and recipe['stop_frame_exclusive'] == recipe['total_timeline_frames'],
                      full_canvas_measured=recipe['active_region_xywh'] == [0, 0, recipe['width'], recipe['height']],
                      encoder_RGB16_input_sha256='sha256:' + payload.hexdigest(),
                      encoder_RGBA16_input_bytes=meter.frames * recipe['width'] * recipe['height'] * 8,
                      colour_boundary_all_frames=audit.result(), transport_range_counts=stats,
                      timeline=metadata, implementation_artifacts=artifacts,
                      author_project_rewritten=False, new_media=False, audio_measured=False,
                      native_windows=True, network=False)
        return result
