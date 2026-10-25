"""Portable, declarative motion recipes compiled into ordinary author-clock keys.

No Python/FFmpeg expressions or asset paths are accepted in a recipe. Spatial
paths are finite samples, while captured easing remains native keyframe data.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json
import math
import re

from .clip_windows import validate_window
from .errors import AppError
from .execution_control import checkpoint
from .utils import ID_RE

FORMAT = 'agent-editor-motion-pack'
VERSION = 1
ENGINE = 'agent-motion-pack-v1'
MAX_BYTES = 1024 * 1024
MAX_POINTS = 1025
EASINGS = {'hold', 'linear', 'ease_in', 'ease_out', 'ease_in_out', 'bezier'}
ALIASES = {
    'transform.position.x': ('transform.position.x', 'position.x', 'position_x'),
    'transform.position.y': ('transform.position.y', 'position.y', 'position_y'),
    'transform.scale': ('transform.scale', 'scale'),
    'transform.rotation': ('transform.rotation', 'rotation'),
    'transform.opacity': ('transform.opacity', 'opacity'),
    'transform.anchor.x': ('transform.anchor.x', 'anchor.x', 'anchor_x'),
    'transform.anchor.y': ('transform.anchor.y', 'anchor.y', 'anchor_y'),
}
DEFAULTS = {'transform.position.x': .5, 'transform.position.y': .5,
            'transform.scale': 1., 'transform.rotation': 0.,
            'transform.opacity': 1., 'transform.anchor.x': .5, 'transform.anchor.y': .5}


def fail(message, path='motion_pack', code='MOTION_PACK_INVALID'):
    raise AppError(code, message, exit_code=2, path=path)


def number(value, path):
    if type(value) not in (int, float) or abs(value) > 1e9 or not math.isfinite(value):
        fail('必须为有界有限数字，不能是布尔值', path)
    return float(value)


def _fields(value, required, optional=(), *, path='motion_pack'):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        fail('缺少必要字段或包含未知字段', path)


def _text(value, path, maximum=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or '\x00' in value:
        fail('必须为长度受限的非空文本', path)
    return value


def canonical_property(name):
    return next((prop for prop, aliases in ALIASES.items() if name in aliases), None)


def _fraction(value, path):
    if not isinstance(value, list) or len(value) != 2 or any(type(x) is not int for x in value):
        fail('归一化时间必须是 [整数分子, 正整数分母]', path)
    numerator, denominator = value
    if not 1 <= denominator <= 10**12 or not 0 <= numerator <= denominator:
        fail('归一化时间必须位于 0..1，分母不能超过 10^12', path)
    return Fraction(numerator, denominator)


def _bound(value, parameters, path):
    if isinstance(value, dict):
        _fields(value, ('parameter', 'factor', 'offset'), path=path)
        if not isinstance(value['parameter'], str) or value['parameter'] not in parameters:
            fail('数值绑定引用了未声明参数', path)
        factor = number(value['factor'], path + '.factor')
        offset = number(value['offset'], path + '.offset')
        spec = parameters[value['parameter']]
        return tuple(offset + factor * spec[x] for x in ('minimum', 'maximum'))
    scalar = number(value, path)
    return scalar, scalar


def validate_pack(pack):
    _fields(pack, ('format', 'format_version', 'id', 'version', 'name', 'description',
                   'creator', 'license', 'parameters', 'tracks'), ('sampling', 'capture'))
    if pack['format'] != FORMAT or type(pack['format_version']) is not int or pack['format_version'] != VERSION:
        fail('不支持的运镜包格式/格式版本')
    if not isinstance(pack['id'], str) or not ID_RE.fullmatch(pack['id']):
        fail('运镜包 ID 无效', 'id')
    if not isinstance(pack['version'], str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', pack['version']):
        fail('运镜包 version 必须为三段非负语义版本', 'version')
    for field in ('name', 'description', 'creator', 'license'):
        _text(pack[field], field)
    parameters = pack['parameters']
    if not isinstance(parameters, dict) or len(parameters) > 16:
        fail('parameters 必须为最多 16 项的对象', 'parameters')
    for name, spec in parameters.items():
        if not isinstance(name, str) or not ID_RE.fullmatch(name):
            fail('参数名称无效', 'parameters')
        _fields(spec, ('default', 'minimum', 'maximum', 'description'), path='parameters.' + name)
        low, high, default = (number(spec[k], 'parameters.' + name + '.' + k)
                              for k in ('minimum', 'maximum', 'default'))
        if not low <= default <= high:
            fail('参数 default 必须位于声明范围', 'parameters.' + name)
        _text(spec['description'], 'parameters.' + name + '.description')
    if not isinstance(pack['tracks'], list) or not 1 <= len(pack['tracks']) <= len(ALIASES):
        fail('tracks 必须为 1..7 个规范 transform 属性', 'tracks')
    seen = set()
    for index, track in enumerate(pack['tracks']):
        checkpoint()
        path = f'tracks[{index}]'
        _fields(track, ('property', 'mode', 'keyframes'), path=path)
        prop = track['property']
        if not isinstance(prop, str) or prop not in ALIASES or prop in seen:
            fail('属性必须规范且唯一', path + '.property')
        seen.add(prop)
        if track['mode'] not in ('absolute', 'add', 'multiply'):
            fail('mode 必须为 absolute/add/multiply', path + '.mode')
        points = track['keyframes']
        if not isinstance(points, list) or not 2 <= len(points) <= MAX_POINTS:
            fail('每属性必须包含 2..1025 个关键帧', path + '.keyframes')
        previous = Fraction(-1)
        for n, point in enumerate(points):
            pp = f'{path}.keyframes[{n}]'
            _fields(point, ('at', 'value', 'interpolation'), ('control_points',), path=pp)
            at = _fraction(point['at'], pp + '.at')
            if at <= previous:
                fail('关键帧归一化时间必须严格递增', pp + '.at')
            previous = at
            values = _bound(point['value'], parameters, pp + '.value')
            easing = point['interpolation']
            if not isinstance(easing, str) or easing not in EASINGS:
                fail('插值类型无效', pp + '.interpolation')
            if easing == 'bezier':
                controls = point.get('control_points')
                if not isinstance(controls, list) or len(controls) not in (2, 4):
                    fail('Bezier 必须提供 2 或 4 个控制值', pp + '.control_points')
                for k, control in enumerate(controls):
                    number(control, pp + '.control_points')
                    if len(controls) == 4 and k in (0, 2) and not 0 <= control <= 1:
                        fail('Bezier 横向控制值必须位于 0..1', pp + '.control_points')
            elif 'control_points' in point:
                fail('非 Bezier 点不接受 control_points', pp)
            if prop == 'transform.scale' and track['mode'] != 'add' and min(values) <= 0:
                fail('缩放系数必须为正数', pp + '.value')
            if track['mode'] == 'absolute' and prop in ('transform.opacity', 'transform.anchor.x', 'transform.anchor.y') and not all(0 <= x <= 1 for x in values):
                fail('绝对透明度/锚点必须位于 0..1', pp + '.value')
        if _fraction(points[0]['at'], path) != 0 or _fraction(points[-1]['at'], path) != 1:
            fail('每条属性轨必须显式包含 0 和 1 两个端点', path)
    if 'sampling' in pack:
        _fields(pack['sampling'], ('kind', 'intervals', 'error_note'), path='sampling')
        if pack['sampling']['kind'] != 'uniform-linear' or type(pack['sampling']['intervals']) is not int or not 1 <= pack['sampling']['intervals'] <= 1024:
            fail('采样说明无效', 'sampling')
        _text(pack['sampling']['error_note'], 'sampling.error_note')
    if 'capture' in pack:
        _fields(pack['capture'], ('clock', 'authored_duration_tick', 'properties'), path='capture')
        if pack['capture']['clock'] != 'complete-authored-output' or type(pack['capture']['authored_duration_tick']) is not int or not 1 <= pack['capture']['authored_duration_tick'] <= 10**12 or pack['capture']['properties'] != [t['property'] for t in pack['tracks']]:
            fail('捕获说明无效', 'capture')
    if len(canonical_bytes(pack)) > MAX_BYTES:
        fail('运镜包超过 1MiB', code='MOTION_PACK_TOO_LARGE')
    return pack


def canonical_bytes(pack):
    return json.dumps(pack, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(pack):
    return 'sha256:' + hashlib.sha256(canonical_bytes(pack)).hexdigest()


def decode_pack(raw):
    if len(raw) > MAX_BYTES:
        fail('运镜包超过 1MiB', code='MOTION_PACK_TOO_LARGE')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail('JSON 包含重复字段', key)
            result[key] = value
        return result
    try:
        return validate_pack(json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs))
    except (UnicodeError, ValueError, RecursionError) as exc:
        fail('运镜包不是有效的 UTF-8 JSON: ' + str(exc)[:160])


def _base(clip, prop):
    transform = clip.get('transform') or {}
    suffix = prop.removeprefix('transform.')
    if '.' in suffix:
        parent, leaf = suffix.split('.')
        return number((transform.get(parent) or {}).get(leaf, transform.get(parent + '_' + leaf, DEFAULTS[prop])), prop)
    return number(transform.get(suffix, DEFAULTS[prop]), prop)


def _resolve(value, parameters):
    return value['offset'] + parameters[value['parameter']] * value['factor'] if isinstance(value, dict) else value


def compile_pack(pack, clip, *, parameters=None, start_tick=0, end_tick=None, replace=False):
    validate_pack(pack)
    authored_duration = validate_window(clip)
    duration = clip['duration_tick']
    if end_tick is None:
        end_tick = duration
    if type(start_tick) is not int or type(end_tick) is not int or not 0 <= start_tick < end_tick <= duration:
        fail('应用区间必须位于当前可见片段输出时段', 'start_tick/end_tick', 'MOTION_PACK_TIME_INVALID')
    if clip.get('tracking_binding'):
        fail('跟踪绑定轨迹不能被运镜包静默替换', code='MOTION_PACK_TRACKING_CONFLICT')
    values = parameters if parameters is not None else {}
    if not isinstance(values, dict) or set(values) - set(pack['parameters']):
        fail('含有未声明的参数', 'parameters')
    values = {k: number(values.get(k, s['default']), 'parameters.' + k) for k, s in pack['parameters'].items()}
    for key, value in values.items():
        spec = pack['parameters'][key]
        if not spec['minimum'] <= value <= spec['maximum']:
            fail('参数超出包声明范围', 'parameters.' + key)
    properties = {t['property'] for t in pack['tracks']}
    conflicts = [t['property'] for t in clip.get('keyframes', []) if canonical_property(t.get('property')) in properties]
    if conflicts and not replace:
        fail('已有同属性动画；显式 --replace 才会替换整条属性轨', ','.join(conflicts), 'MOTION_PACK_CONFLICT')
    offset = (clip.get('presentation_window') or {}).get('offset_tick', 0)
    compiled = []
    for track in pack['tracks']:
        checkpoint()
        prop = track['property']; base = _base(clip, prop)
        keys = []; previous = -1
        for point in track['keyframes']:
            at = offset + start_tick + round(_fraction(point['at'], prop) * (end_tick-start_tick))
            if at <= previous or at > authored_duration:
                fail('应用区间太短，归一化点舍入到相同 tick', prop, 'MOTION_PACK_TIME_COLLISION')
            value = float(_resolve(point['value'], values))
            if track['mode'] == 'add':
                value += base
            elif track['mode'] == 'multiply':
                value *= base
            number(value, prop)
            if prop == 'transform.scale' and not .001 <= value <= 100:
                fail('编译后缩放必须位于 .001..100', prop)
            if prop in ('transform.opacity', 'transform.anchor.x', 'transform.anchor.y') and not 0 <= value <= 1:
                fail('编译后透明度/锚点必须位于 0..1', prop)
            key = dict(at_tick=at, value=value, interpolation=point['interpolation'])
            if 'control_points' in point:
                key['control_points'] = copy.deepcopy(point['control_points'])
            keys.append(key); previous = at
        compiled.append(dict(property=prop, keyframes=keys))
    result = copy.deepcopy(clip)
    result['keyframes'] = [copy.deepcopy(t) for t in clip.get('keyframes', []) if canonical_property(t.get('property')) not in properties] + compiled
    receipt = dict(engine=ENGINE, pack_id=pack['id'], pack_version=pack['version'],
                   content_sha256=digest(pack), parameters=values,
                   clock='authored-output', visible_start_tick=start_tick, visible_end_tick=end_tick,
                   author_start_tick=offset+start_tick, author_end_tick=offset+end_tick,
                   properties=[t['property'] for t in compiled], keyframe_count=sum(len(t['keyframes']) for t in compiled),
                   replaced_properties=conflicts, license=pack['license'], creator=pack['creator'],
                   recipe=copy.deepcopy(pack))
    warnings = []
    if conflicts:
        warnings.append(dict(code='MOTION_PACK_REPLACED_TRACKS', message='已显式替换整条属性轨，区间外旧点也被替换', properties=conflicts))
    if start_tick or end_tick != duration:
        warnings.append(dict(code='MOTION_PACK_ENDPOINT_HOLD', message='应用区间外使用新轨道首尾值；未保留该属性的旧动画'))
    return result, receipt, warnings


def capture_pack(clip, *, pack_id, name, creator, license, version='1.0.0', properties=None):
    duration = validate_window(clip)
    if duration > 10**12:
        fail('作者时长超过格式范围', 'duration_tick')
    selected = properties if properties is not None else list(ALIASES)
    if not isinstance(selected, list) or not selected or any(not isinstance(p, str) or p not in ALIASES for p in selected) or len(selected) != len(set(selected)):
        fail('capture properties 必须是唯一规范属性列表', 'properties')
    tracks = []
    for prop in selected:
        found = [t for t in clip.get('keyframes', []) if canonical_property(t.get('property')) == prop]
        if len(found) > 1:
            fail('源片段含相同属性的多条别名轨，不能猜测优先级', prop, 'MOTION_PACK_ALIAS_CONFLICT')
        if not found:
            continue
        points = copy.deepcopy(found[0].get('keyframes', []))
        if not points:
            fail('源属性没有关键帧', prop)
        if any(type(p.get('at_tick')) is not int or not 0 <= p['at_tick'] <= duration for p in points) or any(a['at_tick'] >= b['at_tick'] for a,b in zip(points, points[1:])):
            fail('源关键帧时间无效或重复', prop)
        if points[0]['at_tick'] > 0:
            points.insert(0, dict(at_tick=0, value=points[0]['value'], interpolation='hold'))
        if points[-1]['at_tick'] < duration:
            points.append(dict(at_tick=duration, value=points[-1]['value'], interpolation='hold'))
        keys = []
        for point in points:
            ratio = Fraction(point['at_tick'], duration)
            key = dict(at=[ratio.numerator,ratio.denominator], value=point['value'], interpolation=point['interpolation'])
            if 'control_points' in point:
                key['control_points'] = point['control_points']
            keys.append(key)
        tracks.append(dict(property=prop, mode='absolute', keyframes=keys))
    if not tracks:
        fail('没有可捕获的 transform 动画', code='MOTION_PACK_EMPTY')
    pack = dict(format=FORMAT, format_version=VERSION, id=pack_id, version=version,
        name=name, description='Captured complete authored transform animation / 完整作者变换动画',
        creator=creator, license=license, parameters={}, tracks=tracks,
        capture=dict(clock='complete-authored-output', authored_duration_tick=duration, properties=[t['property'] for t in tracks]))
    return validate_pack(pack)


BUILTIN_NAMES = ('orbit_focus', 'arc_push', 'bezier_sweep', 'whip_settle', 'breathe_float', 'detail_scan')


def builtin(name):
    if name not in BUILTIN_NAMES:
        fail('未知的内置运镜包', 'name')
    parameters = {}
    tracks = []
    def parameter(key, default, low, high, description):
        parameters[key] = dict(default=default, minimum=low, maximum=high, description=description)
    def path(prop, mode, parameter_name, factors, offset=0.):
        tracks.append(dict(property='transform.'+prop, mode=mode, keyframes=[
            dict(at=[i,64], value=dict(parameter=parameter_name, factor=float(factor), offset=offset), interpolation='linear')
            for i, factor in enumerate(factors)]))
    t = [i/64 for i in range(65)]
    parameter('zoom', .15, 0., .5, 'Relative scale increase / 相对缩放增量')
    descriptions = {
        'orbit_focus': 'Orbit focus / 绕中心椭圆运镜',
        'arc_push': 'Arc push / 弧形推进',
        'bezier_sweep': 'Cubic sweep / 三次贝塞尔 S 路径扫过',
        'whip_settle': 'Whip and settle / 甩入后衰减停稳',
        'breathe_float': 'Breathing float / 呼吸缩放与漂浮',
        'detail_scan': 'Detail scan / 停顿式细节扫视',
    }
    if name == 'orbit_focus':
        parameter('radius', .12, 0., .35, 'Normalized ellipse radius / 归一化椭圆半径')
        path('position.x','add','radius',[math.cos(2*math.pi*u) for u in t])
        path('position.y','add','radius',[.6*math.sin(2*math.pi*u) for u in t])
        path('scale','multiply','zoom',[1.]*65,1.)
    elif name == 'arc_push':
        parameter('travel',.20,-.6,.6,'Horizontal travel / 水平位移')
        parameter('height',.10,-.4,.4,'Arc height / 弧线高度')
        path('position.x','add','travel',[u-.5 for u in t])
        path('position.y','add','height',[-4*u*(1-u) for u in t])
        path('scale','multiply','zoom',t,1.)
    elif name == 'bezier_sweep':
        parameter('travel',.35,-.8,.8,'Cubic horizontal extent / 三次曲线水平跨度')
        parameter('height',.25,-.6,.6,'Cubic control height / 三次曲线控制高度')
        path('position.x','add','travel',[-.5*(1-u)**3-.75*(1-u)**2*u+.75*(1-u)*u*u+.5*u**3 for u in t])
        path('position.y','add','height',[-3*(1-u)**2*u+3*(1-u)*u*u for u in t])
        path('scale','multiply','zoom',[4*u*(1-u) for u in t],1.)
    elif name == 'whip_settle':
        parameter('travel',.35,-.8,.8,'Initial throw / 初始甩入幅度')
        path('position.x','add','travel',[-math.exp(-8*u)*math.cos(4*math.pi*u) if u<1 else 0. for u in t])
        path('scale','multiply','zoom',[1-math.exp(-6*u) if u<1 else 1. for u in t],1.)
    elif name == 'breathe_float':
        parameter('height',.06,-.3,.3,'Vertical breathing amplitude / 上下漂浮幅度')
        path('position.y','add','height',[math.sin(2*math.pi*u) for u in t])
        path('scale','multiply','zoom',[(1-math.cos(2*math.pi*u))/2 for u in t],1.)
    else:
        parameter('travel',.3,-.8,.8,'Scan horizontal extent / 扫视水平幅度')
        parameter('tilt',5.,-45.,45.,'Rotation degrees / 旋转角度')
        # Three intentional rests connected by smoothstep segments.
        def scan(u):
            if u < .2:return -.5
            if u < .45:
                v=(u-.2)/.25;return -.5+.5*v*v*(3-2*v)
            if u < .6:return 0.
            if u < .85:
                v=(u-.6)/.25;return .5*v*v*(3-2*v)
            return .5
        path('position.x','add','travel',[scan(u) for u in t])
        path('rotation','add','tilt',[math.sin(2*math.pi*u) for u in t])
        path('scale','multiply','zoom',[1.]*65,1.)
    return validate_pack(dict(format=FORMAT, format_version=VERSION, id=name, version='1.0.0',
        name=descriptions[name], description=descriptions[name]+'; editable 65-sample transform keys',
        creator='agent editor kit contributors', license='MIT', parameters=parameters, tracks=tracks,
        sampling=dict(kind='uniform-linear', intervals=64,
                      error_note='Finite 65-point polyline, not analytic spatial interpolation; inspect at the target size and duration.')))


def catalog():
    return [dict(id=name, version='1.0.0', name=(pack:=builtin(name))['name'],
                 parameters=pack['parameters'], properties=[t['property'] for t in pack['tracks']],
                 content_sha256=digest(pack), keyframe_count=sum(len(t['keyframes']) for t in pack['tracks']),
                 sampling=pack['sampling']) for name in BUILTIN_NAMES]
