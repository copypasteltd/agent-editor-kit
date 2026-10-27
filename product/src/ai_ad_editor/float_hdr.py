"""Explicit display-light PQ/HLG and bounded, opt-in SDR viewing transforms.

Original MIT implementation of ITU-R BT.2100-3 tables 4/5. PQ is the
display EOTF/inverse, not the camera OETF. HLG includes the RGB-coupled
OOTF, with caller-declared display peak/system gamma and ideal zero black.
No automatic luminance inference, ICC, dynamic metadata or monitor acceptance.
"""
from dataclasses import dataclass
import math

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal, PRIMARIES, TRANSFERS

PROTOCOL = 'explicit-display-nits-PQ-HLG-float32-v1'
HDR_TRANSFERS = {'pq-st2084', 'hlg-bt2100'}
M1, M2 = 2610 / 16384, 2523 / 32
C1, C2, C3 = 3424 / 4096, 2413 / 128, 2392 / 128
HLG_A = .17883277
HLG_B = 1 - 4 * HLG_A
HLG_C = .5 - HLG_A * math.log(4 * HLG_A)
HLG_Y = (.2627, .6780, .0593)


def error(code, message):
    return AppError('FLOAT_HDR_' + code, message, exit_code=2)


def number(value, low, high, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise error('SIGNAL', name + '须是明确、有限且在支持范围内的数值')
    return float(value)


@dataclass(frozen=True)
class LuminanceSignal(ColorSignal):
    reference_white_nits: float
    display_peak_nits: float | None = None
    system_gamma: float | None = None

    def __post_init__(self):
        if not isinstance(self.primaries, str) or self.primaries not in PRIMARIES:
            raise error('SIGNAL', '须明确支持的D65 RGB基色')
        if not isinstance(self.transfer, str) or self.transfer not in TRANSFERS | HDR_TRANSFERS:
            raise error('SIGNAL', '须明确相对传递函数或display-light PQ/HLG解释')
        number(self.reference_white_nits, .01, 10000, 'reference_white_nits')
        if self.transfer in HDR_TRANSFERS and self.primaries != 'bt2020':
            raise error('SIGNAL', '当前BT.2100 HDR信号要求BT.2020基色')
        if self.transfer == 'hlg-bt2100':
            number(self.display_peak_nits, 100, 10000, 'display_peak_nits')
            number(self.system_gamma, .5, 3, 'system_gamma')
        elif self.display_peak_nits is not None or self.system_gamma is not None:
            raise error('SIGNAL', 'display_peak_nits/system_gamma只适用于HLG')


def parse_signal(value):
    if not isinstance(value, dict):
        raise error('SIGNAL', 'RGB信号须是明确的对象')
    if set(value) == {'primaries', 'transfer'}:
        return ColorSignal(**value)
    allowed = {'primaries', 'transfer', 'reference_white_nits', 'display_peak_nits', 'system_gamma'}
    if set(value) - allowed or not {'primaries', 'transfer', 'reference_white_nits'} <= set(value):
        raise error('SIGNAL', 'RGB信号字段无效；绝对亮度须明确reference_white_nits')
    return LuminanceSignal(**value)


def has_luminance(signal):
    return isinstance(signal, LuminanceSignal)


def domain(values, low, high, *, policy='reject', stage):
    if not isinstance(policy, str) or policy not in {'reject', 'clip'}:
        raise error('POLICY', 'HDR域策略只允许reject/clip')
    outside = (values < low) | (values > high)
    count = int(np.count_nonzero(outside))
    if count and policy == 'reject':
        raise error('DOMAIN', stage + '超出明确HDR信号域；须修正输入或显式选择输出clip')
    return (np.clip(values, low, high) if count else values), count


def to_linear(values, signal):
    """Return display-linear RGB in units of signal.reference_white_nits."""
    from .float_color_signal import _to_linear
    if signal.transfer not in HDR_TRANSFERS:
        return _to_linear(values, signal.transfer)
    values, _ = domain(values, 0, 1, stage='输入PQ/HLG编码RGB')
    if signal.transfer == 'pq-st2084':
        root = values ** (1 / M2)
        return 10000 / signal.reference_white_nits * (np.maximum(root - C1, 0) / (C2 - C3 * root)) ** (1 / M1)
    scene = np.empty_like(values)
    toe = values <= .5
    scene[toe] = values[toe] ** 2 / 3
    scene[~toe] = (np.exp((values[~toe] - HLG_C) / HLG_A) + HLG_B) / 12
    luminance = scene[:, 0] * HLG_Y[0] + scene[:, 1] * HLG_Y[1] + scene[:, 2] * HLG_Y[2]
    scale = np.zeros_like(luminance)
    positive = luminance > 0
    scale[positive] = luminance[positive] ** (signal.system_gamma - 1)
    return scene * scale[:, None] * (signal.display_peak_nits / signal.reference_white_nits)


def from_linear(values, signal, *, policy='reject'):
    from .float_color_signal import _from_linear
    if signal.transfer not in HDR_TRANSFERS:
        return _from_linear(values, signal.transfer), 0
    absolute = values * signal.reference_white_nits
    maximum = 10000 if signal.transfer == 'pq-st2084' else signal.display_peak_nits
    absolute, clipped = domain(absolute, 0, maximum, policy=policy, stage='输出display-linear RGB亮度')
    if signal.transfer == 'pq-st2084':
        power = (absolute / 10000) ** M1
        return ((C1 + C2 * power) / (1 + C3 * power)) ** M2, clipped
    display = absolute / signal.display_peak_nits
    luminance = display[:, 0] * HLG_Y[0] + display[:, 1] * HLG_Y[1] + display[:, 2] * HLG_Y[2]
    scene = np.zeros_like(display)
    positive = luminance > 0
    # Yd = Ys**gamma; multiplying by Yd**((1-gamma)/gamma)
    # inverts the *coupled* RGB OOTF. Per-channel gamma is incorrect.
    scene[positive] = display[positive] * luminance[positive, None] ** ((1 - signal.system_gamma) / signal.system_gamma)
    scene, more = domain(scene, 0, 1, policy=policy, stage='输出HLG scene-linear RGB')
    encoded = np.empty_like(scene)
    toe = scene <= 1 / 12
    encoded[toe] = np.sqrt(3 * scene[toe])
    encoded[~toe] = HLG_A * np.log(12 * scene[~toe] - HLG_B) + HLG_C
    return encoded, clipped + more


def mapping_configuration(value):
    allowed = {'operator', 'source_peak_nits', 'target_peak_nits', 'exposure_stops', 'gamut_policy'}
    if not isinstance(value, dict) or set(value) != allowed or value.get('operator') != 'reinhard-luminance':
        raise error('MAPPING', '显示映射须完整指定reinhard-luminance、峰值、曝光和gamut_policy')
    source = number(value['source_peak_nits'], 1, 10000, 'source_peak_nits')
    target = number(value['target_peak_nits'], 1, 1000, 'target_peak_nits')
    exposure = number(value['exposure_stops'], -16, 16, 'exposure_stops')
    if source < target or not isinstance(value['gamut_policy'], str) or value['gamut_policy'] not in {'reject', 'clip'}:
        raise error('MAPPING', '源峰值须不小于目标峰值；色域策略须明确reject/clip')
    return {**value, 'source_peak_nits': source, 'target_peak_nits': target, 'exposure_stops': exposure}


def map_display(surface, working_signal, mapping, *, target_primaries='bt709',
                max_working_bytes=768*1024**2, cancel=None):
    """An explicit creative SDR trim; not BT.2390 or automatic mastering.

    Modified Reinhard is applied to target-gamut linear luminance; source peak
    is a caller-declared white point of the shoulder, not measured metadata.
    Relative scalar arithmetic is bounded and split into the shared colour
    converter's 65536-pixel tiles. Every clamped component is reported.
    """
    from .float_color_signal import _rgb_to_xyz, convert_rgba
    mapping = mapping_configuration(mapping)
    if not has_luminance(working_signal) or working_signal.transfer != 'linear':
        raise error('MAPPING', '显示映射要求明确reference_white_nits的线性RGB工作域')
    target = LuminanceSignal(target_primaries, 'linear', mapping['target_peak_nits'])
    # Reserve a conservative tile workspace in addition to the conversion's
    # owned output; neither estimate purports to be total process RSS.
    if isinstance(max_working_bytes, bool) or not isinstance(max_working_bytes, (int,np.integer)) or not 1 <= max_working_bytes <= 768*1024**2:
        raise error('BUDGET', '显示映射工作区预算无效')
    pixels = int(np.prod(surface.shape[:2])) if isinstance(surface, np.ndarray) and surface.ndim == 3 else 0
    estimate = 2 * getattr(surface, 'nbytes', 0) + min(pixels, 65536) * 512 + 4096
    if estimate > max_working_bytes:
        raise error('BUDGET', '显示映射超过显式算子工作区预算')
    result, conversion = convert_rgba(surface, working_signal, target,
        max_working_bytes=max_working_bytes, cancel=cancel)
    rows = result.reshape(-1, 4)
    weights = _rgb_to_xyz(target_primaries)[1]
    white = mapping['source_peak_nits'] / mapping['target_peak_nits']
    exposure = 2 ** mapping['exposure_stops']
    counts = {'negative_components_clipped': 0, 'over_one_components_clipped': 0,
              'above_declared_peak_pixels': 0}
    for start in range(0, len(rows), 65536):
        if cancel is not None: cancel()
        rgb = rows[start:start+65536, :3].astype(np.float64)
        negative = rgb < 0
        count = int(np.count_nonzero(negative))
        if count and mapping['gamut_policy'] == 'reject':
            raise error('GAMUT', '映射目标RGB含负值；须修正色域或显式选择clip')
        counts['negative_components_clipped'] += count
        rgb = np.maximum(rgb, 0)
        y = (rgb[:, 0]*weights[0] + rgb[:, 1]*weights[1] + rgb[:, 2]*weights[2]) * exposure
        counts['above_declared_peak_pixels'] += int(np.count_nonzero(y > white))
        shoulder = y * (1 + y / (white * white)) / (1 + y)
        ratio = np.zeros_like(y)
        np.divide(shoulder * exposure, y, out=ratio, where=y > 0)
        rgb *= ratio[:, None]
        outside = rgb > 1
        count = int(np.count_nonzero(outside))
        if count and mapping['gamut_policy'] == 'reject':
            raise error('GAMUT', '亮度映射后RGB超出SDR色域；须修正或显式选择clip')
        counts['over_one_components_clipped'] += count
        rows[start:start+len(rgb), :3] = np.minimum(rgb, 1)
    if cancel is not None: cancel()
    return result, target, {'protocol': PROTOCOL, 'operator': 'modified-Reinhard-on-target-linear-luminance',
        'configuration': mapping, 'source_signal': vars(working_signal), 'target_signal': vars(target),
        'gamut_matrix': conversion['linear_gamut_matrix'], **counts,
        'alpha': 'bit-exact', 'automatic_peak_inference': False, 'BT2390_claimed': False,
        'estimated_working_bytes': estimate, 'estimated_bytes_are_peak_RSS': False,
        'HDR_monitor_accepted': False}
