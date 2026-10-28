"""Explicit HDR10 static declarations, HEVC SEI writing and decoded verification.

Coordinates use CIE 1931 xy; luminance uses cd/m2. No peak measurement,
automatic mastering, HDR10+ or Dolby Vision is implied by these declarations.
"""
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
import math

from .errors import AppError

PROTOCOL = 'declared-hdr10-static-sei-v1'
MAX_PROBE_PACKETS = 32


def error(code, message, **details):
    return AppError('HDR_METADATA_' + code, message, exit_code=2,
                    diagnostics=details or None)


def quantize(value, scale, low, high, name):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise error('VALUE', name + '须是支持范围内的有限数值')
    scaled = Decimal(str(value)) * scale
    if scaled != scaled.to_integral_value():
        raise error('PRECISION', name + '不能无提示舍入；须使用明确的码流单位', units='1/' + str(scale))
    return int(scaled)


def point(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise error('VALUE', name + '须为两个数值的xy数组')
    x = quantize(value[0], 50000, 0, 1, name + '.x')
    y = quantize(value[1], 50000, .00002, 1, name + '.y')
    if x + y > 50000:
        raise error('VALUE', name + '的x+y不能大于1')
    return x, y


def normalize(value):
    required = {'mastering_display', 'content_light'}
    if not isinstance(value, dict) or set(value) != required:
        raise error('CONFIG', 'hdr10须完整声明mastering_display与content_light')
    display = value['mastering_display']
    fields = {'red_xy', 'green_xy', 'blue_xy', 'white_xy', 'min_luminance_nits', 'max_luminance_nits'}
    if not isinstance(display, dict) or set(display) != fields:
        raise error('CONFIG', '母版显示信息字段缺失或含未知字段')
    points = {name: point(display[name + '_xy'], name) for name in ('red', 'green', 'blue', 'white')}
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    r, g, b, w = (points[name] for name in ('red', 'green', 'blue', 'white'))
    area = cross(r, g, b)
    if not area or any(cross(a, z, w) * area <= 0 for a, z in ((r,g), (g,b), (b,r))):
        raise error('GAMUT', '母版基色三角形须非退化，白点须位于其内部')
    low = quantize(display['min_luminance_nits'], 10000, 0, 10000, 'min_luminance_nits')
    high = quantize(display['max_luminance_nits'], 10000, .0001, 10000, 'max_luminance_nits')
    if low >= high:
        raise error('VALUE', '母版最小亮度须小于最大亮度')
    light = value['content_light']
    if not isinstance(light, dict) or set(light) != {'max_cll_nits', 'max_fall_nits'}:
        raise error('CONFIG', '内容亮度须完整声明max_cll_nits/max_fall_nits')
    for name, number in light.items():
        if type(number) is not int or not 0 <= number <= 10000:
            raise error('VALUE', name + '须为0–10000的整数nit；0表示未知')
    if light['max_cll_nits'] and light['max_fall_nits'] > light['max_cll_nits']:
        raise error('VALUE', '已知MaxFALL不能超过已知MaxCLL')
    # Return independent JSON data; callers cannot mutate an accepted plan.
    return {'mastering_display': {**{name + '_xy': list(display[name + '_xy']) for name in points},
            'min_luminance_nits': display['min_luminance_nits'],
            'max_luminance_nits': display['max_luminance_nits']}, 'content_light': dict(light)}


def validate_context(value, settings, encoder):
    value = normalize(value)
    pipeline = settings.get('pixel_pipeline') or {}
    if not isinstance(pipeline, dict):
        raise error('CONTEXT', 'HDR10静态声明要求明确原生管线对象')
    output = pipeline.get('output_signal') or {}
    working = pipeline.get('working_signal') or {}
    color = settings.get('color') or {}
    if not all(isinstance(v, dict) for v in (output, working, color)):
        raise error('CONTEXT', 'HDR10信号和色彩上下文须是对象')
    if (pipeline.get('engine') != 'float32-native-v1' or
            output.get('transfer') != 'pq-st2084' or output.get('primaries') != 'bt2020' or
            'reference_white_nits' not in output or 'reference_white_nits' not in working or
            'display_mapping' in pipeline or
            encoder['container'] not in {'mp4', 'mkv'} or
            encoder['video']['codec'] != 'libx265' or
            encoder['video']['pixel_format'] != 'yuv420p10le' or
            color.get('primaries') != 'bt2020' or color.get('transfer') != 'smpte2084' or
            color.get('matrix') != 'bt2020nc' or color.get('range') not in {'limited', 'tv'}):
        raise error('CONTEXT', 'HDR10静态声明要求原生明确nit/PQ BT.2020 NCL有限量程、libx265、10-bit 4:2:0及MP4/MKV')
    return value


def encoded_fields(value):
    value = normalize(value)
    d = value['mastering_display']
    result = {}
    for name in ('red', 'green', 'blue', 'white'):
        x, y = point(d[name + '_xy'], name)
        result[name + '_x'] = Fraction(x, 50000)
        result[name + '_y'] = Fraction(y, 50000)
    result['min_luminance'] = Fraction(quantize(d['min_luminance_nits'], 10000, 0, 10000, 'min'), 10000)
    result['max_luminance'] = Fraction(quantize(d['max_luminance_nits'], 10000, .0001, 10000, 'max'), 10000)
    return result


def encoder_arguments(value):
    if value is None:
        return []
    fields = encoded_fields(value)
    xy = lambda name: ','.join(str(int(fields[name + '_' + axis] * 50000)) for axis in ('x', 'y'))
    luminance = ','.join(str(int(fields[name + '_luminance'] * 10000)) for name in ('max', 'min'))
    light = value['content_light']
    # Fixed grammar only; no caller-controlled x265 flags or shell expansion.
    options = ('master-display=G(' + xy('green') + ')B(' + xy('blue') + ')R(' + xy('red') +
               ')WP(' + xy('white') + ')L(' + luminance + '):max-cll=' +
               str(light['max_cll_nits']) + ',' + str(light['max_fall_nits']) + ':hdr10=1:cll=1')
    return ['-x265-params', options]


def verify_probe(raw, value):
    """Verify observed decoded prefix; never claim all-frame or measured peaks."""
    expected = encoded_fields(value)
    light = value['content_light']
    if not isinstance(raw, dict):
        raise error('PROBE', 'HDR10核验须返回对象')
    streams = raw.get('streams')
    frames = raw.get('frames')
    if not isinstance(streams, list) or len(streams) != 1 or not isinstance(frames, list) or not frames:
        raise error('PROBE', '缺少HEVC视频流或实际解码帧')
    stream = streams[0]
    tags = dict(codec_name='hevc', pix_fmt='yuv420p10le', color_primaries='bt2020',
                color_transfer='smpte2084', color_space='bt2020nc', color_range='tv')
    if not isinstance(stream, dict):
        raise error('PROBE', 'HDR10视频流不是对象')
    if any(stream.get(k) != v for k, v in tags.items()):
        raise error('MISMATCH', '实际编码精度/格式/色彩标签与HDR10声明不匹配', actual={k:stream.get(k) for k in tags})
    observed = []
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict) or not isinstance(frame.get('side_data_list', []), list):
            raise error('PROBE', 'HDR10解码帧不是受支持对象', frame=index)
        sides = frame.get('side_data_list', [])
        if not all(isinstance(v, dict) for v in sides):
            raise error('PROBE', 'HDR10解码附加数据不是对象', frame=index)
        mastering = [v for v in sides if v.get('side_data_type') == 'Mastering display metadata']
        content = [v for v in sides if v.get('side_data_type') == 'Content light level metadata']
        if len(mastering) != 1 or len(content) != 1:
            raise error('MISSING', '实际解码帧缺少唯一母版显示/内容亮度SEI', frame=index)
        try:
            actual = {k: Fraction(str(mastering[0][k.replace('white_', 'white_point_')])) for k in expected}
            actual_light = [Fraction(str(content[0]['max_content'])), Fraction(str(content[0]['max_average']))]
        except (KeyError, ValueError, TypeError, ZeroDivisionError, InvalidOperation) as exc:
            raise error('PROBE', '解码SEI字段无效', frame=index) from exc
        if actual != expected or actual_light != [light['max_cll_nits'], light['max_fall_nits']]:
            raise error('MISMATCH', '实际解码SEI与作者声明不一致', frame=index)
        observed.append({'frame_index': index, 'best_effort_timestamp': frame.get('best_effort_timestamp')})
    return dict(protocol=PROTOCOL, status='verified', declaration=normalize(value),
                verified_decoded_frames=len(observed), observed_frames=observed,
                probe_packet_limit=MAX_PROBE_PACKETS, scope='decoded-prefix-only',
                values_are_author_declarations=True, content_peaks_measured=False,
                HDR_monitor_accepted=False, dynamic_metadata=False)


def verify_output(path, value, *, cancel_file=None):
    from .media import ffprobe_path
    from .utils import run_process
    result = run_process([ffprobe_path(), '-v', 'error', '-select_streams', 'v:0',
        '-read_intervals', '%+#' + str(MAX_PROBE_PACKETS), '-show_streams', '-show_frames',
        '-show_entries', 'stream=codec_name,pix_fmt,color_primaries,color_transfer,color_space,color_range:frame=best_effort_timestamp:frame_side_data',
        '-of', 'json', str(path)], timeout=60, cancel_file=cancel_file)
    if result.returncode != 0:
        raise error('PROBE', '无法解码核验HDR10静态SEI', cause=result.stderr[-2000:])
    try:
        raw = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise error('PROBE', 'HDR10核验返回无效JSON') from exc
    return verify_probe(raw, value)
