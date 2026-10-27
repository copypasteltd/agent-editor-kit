"""Seeded, random-access 2-D particle sources; no simulation state or assets."""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json
import math
import re
import struct

import numpy as np

from .errors import AppError

PROTOCOL = 'analytic-seeded-particle-source-v1'
SHAPES = ('disc', 'rectangle', 'diamond', 'star', 'ring')
MAX_ACTIVE = 4096
MAX_EMITTERS = 16
MAX_PIXELS = 4096 * 2160
MAX_RASTER_VISITS = 128 * 1024**2
TILE = 32
DEFAULT_EMITTER = {
    'rate': 24., 'lifetime': [2., 4.], 'position': [.5, -.05], 'spread': [1.2, .05],
    'velocity': [[-.04, .04], [.12, .24]], 'acceleration': [0., .025],
    'size': [.003, .009], 'size_end': .8, 'aspect': 1., 'rotation': [0., 360.],
    'spin': [-20., 20.], 'shape': 'disc', 'softness': .25, 'glow': 0.,
    'colors': ['#ffffff'], 'color_end': None, 'opacity': .8,
    'fade_in': .12, 'fade_out': .6, 'prewarm': True,
    'sway': [0., 0.], 'twinkle': [0., 0.],
}


def fail(code, message, **details):
    return AppError('PARTICLE_' + code, message, exit_code=2, diagnostics=details or None)


def number(value, low, high, field):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise fail('CONFIG', '粒子参数必须为范围内有限数字', field=field, minimum=low, maximum=high)
    return float(value)


def pair(value, low, high, field, *, ordered=False):
    if not isinstance(value, list) or len(value) != 2:
        raise fail('CONFIG', '粒子二维参数必须有两个数值', field=field)
    result = [number(v, low, high, field) for v in value]
    if ordered and result[0] > result[1]:
        raise fail('CONFIG', '粒子随机区间下界不能大于上界', field=field)
    return result


def color(value, field):
    if not isinstance(value, str) or not re.fullmatch('#[a-fA-F0-9]{6}', value):
        raise fail('CONFIG', '粒子颜色要求明确的sRGB六位十六进制', field=field)
    return value.lower()


def parameter(key,value):
    """One validator for static fields and complete scalar/vector key values."""
    scalar={'rate':(0,1024),'size_end':(0,4),'aspect':(.05,20),
            **{k:(0,1) for k in ('softness','glow','opacity','fade_in','fade_out')}}
    vectors={'lifetime':(.01,120,True),'position':(-4,4,False),'spread':(0,8,False),
             'size':(.0001,.5,True),'rotation':(-36000,36000,True),'spin':(-36000,36000,True),
             'acceleration':(-8,8,False),'sway':(0,16,False),'twinkle':(0,16,False)}
    if key in scalar:return number(value,*scalar[key],key)
    if key in vectors:
        lo,hi,ordered=vectors[key];result=pair(value,lo,hi,key,ordered=ordered)
        if (key=='sway' and result[0]>2) or (key=='twinkle' and result[0]>1):
            raise fail('CONFIG','摆动幅度最多2个画布宽，闪烁深度最多1')
        return result
    if key=='velocity':
        if not isinstance(value,list) or len(value)!=2:raise fail('CONFIG','velocity需要两个随机区间')
        return [pair(v,-8,8,key,ordered=True) for v in value]
    if key=='shape':
        if value not in SHAPES:raise fail('CONFIG','粒子形状不支持')
        return value
    if key=='prewarm':
        if type(value) is not bool:raise fail('CONFIG','粒子预热标记必须为布尔值')
        return value
    if key=='colors':
        if not isinstance(value,list) or not 1<=len(value)<=32:raise fail('CONFIG','粒子调色板要求1..32项')
        return [color(c,key) for c in value]
    if key=='color_end':return color(value,key) if value is not None else None
    raise fail('CONFIG','粒子参数未知',field=key)


def normalize(config):
    if not isinstance(config, dict) or set(config) - {'type', 'protocol', 'seed', 'canvas', 'fps', 'duration_tick', 'ticks_per_second', 'emitters'}:
        raise fail('CONFIG', '粒子生成器含未知字段')
    if config.get('type') != 'particles' or config.get('protocol', PROTOCOL) != PROTOCOL:
        raise fail('PROTOCOL', '粒子生成器类型或协议不支持')
    seed = config.get('seed', 0)
    if type(seed) is not int or not 0 <= seed < 2**63:
        raise fail('CONFIG', '粒子seed必须为0..2^63-1整数')
    canvas = config.get('canvas')
    if not isinstance(canvas, dict) or set(canvas) != {'width', 'height'} or any(type(v) is not int or not 2 <= v <= 8192 for v in canvas.values()):
        raise fail('CONFIG', '粒子源需要明确宽高，每边2..8192像素')
    if canvas['width'] * canvas['height'] > MAX_PIXELS:
        raise fail('BUDGET', '粒子源画布超过4096×2160像素预算')
    fps = config.get('fps')
    if not isinstance(fps, dict) or set(fps) != {'num', 'den'} or any(type(v) is not int or not 1 <= v <= 120000 for v in fps.values()):
        raise fail('CONFIG', '粒子源需要明确的有理数帧率')
    rate = Fraction(fps['num'], fps['den'])
    if not 1 <= rate <= 120:
        raise fail('BUDGET', '粒子源帧率必须为1..120')
    tps, duration = config.get('ticks_per_second'), config.get('duration_tick')
    if type(tps) is not int or not 1 <= tps <= 1000000000 or type(duration) is not int or not 0 < duration <= 600 * tps:
        raise fail('CONFIG', '粒子源需要明确整数时钟与不超过600秒的时长')
    raw = config.get('emitters')
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_EMITTERS:
        raise fail('BUDGET', '粒子源要求1..16个发射器')
    emitters, active = [], 0
    for index, supplied in enumerate(raw):
        if not isinstance(supplied, dict) or set(supplied) - (set(DEFAULT_EMITTER)|{'keyframes'}):
            raise fail('CONFIG', '粒子发射器含未知字段', emitter=index)
        e = {**copy.deepcopy(DEFAULT_EMITTER), **copy.deepcopy(supplied)}
        e={key:parameter(key,value) for key,value in e.items() if key!='keyframes'}
        from .particle_animation import normalize_tracks,maximum
        if 'keyframes' in supplied:e['keyframes']=normalize_tracks(supplied['keyframes'],duration,parameter)
        max_rate=maximum(e,'rate');max_life=maximum(e,'lifetime',1)
        active += math.ceil(max_rate*max_life)+1 if max_rate else 0
        emitters.append(e)
    if active > MAX_ACTIVE:
        raise fail('BUDGET', '发射率与最大寿命的总活动粒子预算超过4096', active_upper_bound=active)
    return dict(type='particles', protocol=PROTOCOL, seed=seed, canvas=copy.deepcopy(canvas),
                fps={'num': rate.numerator, 'den': rate.denominator}, duration_tick=duration,
                ticks_per_second=tps, emitters=emitters)


def identity(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode('utf8')).hexdigest()


def uniform(seed, emitter, particle):
    # Own stable hash protocol; independent of NumPy's RNG, Python hash seed,
    # frame order, chunk size and prior renders. Negative births enable prewarm.
    raw = hashlib.sha512(struct.pack('<QIq', seed, emitter, particle)).digest()
    return [(v >> 11) / 2**53 for v in struct.unpack('<8Q', raw)]


def _linear(hex_color):
    value = np.array([int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)], np.float32)
    return np.where(value <= .04045, value / np.float32(12.92),
                    ((value + np.float32(.055)) / np.float32(1.055))**np.float32(2.4))


def bounds(row, width, height):
    x, y, rx, ry = (float(v) for v in row[:4])
    support = (math.sqrt(2) if row[10] == 1 else 1.) * (1. + float(row[11]))
    extent = max(rx, ry) * max(4. if row[12] else 0., support) + 2
    return (max(0, math.floor(x-extent)), min(width, math.ceil(x+extent)+1),
            max(0, math.floor(y-extent)), min(height, math.ceil(y+extent)+1))


def tile_index(scene, size, *, cancel=None):
    """CSR tile lists retain emitter/birth order, with a finite kernel budget."""
    poll = cancel or (lambda: None); w, h = size
    cols, rows = math.ceil(w/TILE), math.ceil(h/TILE)
    bins = [[] for _ in range(cols*rows)]; visits = 0
    for index, row in enumerate(scene):
        poll(); x0, x1, y0, y1 = bounds(row, w, h)
        if x0 >= x1 or y0 >= y1: continue
        for y in range(y0//TILE, (y1-1)//TILE+1):
            for x in range(x0//TILE, (x1-1)//TILE+1):
                visits += min(TILE, w-x*TILE)*min(TILE, h-y*TILE)
                if visits > MAX_RASTER_VISITS:
                    raise fail('BUDGET', '单帧粒子覆盖超过128Mi候选像素；请减小尺寸或密度', candidate_visits=visits)
                bins[y*cols+x].append(index)
    offsets = [0]
    for bucket in bins: offsets.append(offsets[-1]+len(bucket))
    # Header: tile columns, tile rows, offset count. Followed by offsets then IDs.
    return np.asarray([cols, rows, len(offsets), *offsets, *(i for b in bins for i in b)], '<u4').view(np.uint8)


def validate_scene(scene, tiles, size):
    if (not isinstance(scene, np.ndarray) or scene.dtype != np.float32 or not scene.flags.c_contiguous
            or scene.ndim != 2 or scene.shape[1] != 13 or not 1 <= len(scene) <= MAX_ACTIVE
            or not np.isfinite(scene).all() or np.max(np.abs(scene)) > 1e9
            or np.any(scene[:, 2:4] <= 0) or np.any(scene[:, 2:4] > 1000000)
            or np.any((scene[:, 6:10] < 0) | (scene[:, 6:10] > 1))
            or np.any((scene[:, 11:13] < 0) | (scene[:, 11:13] > 1))
            or np.any(scene[:, 10] != scene[:, 10].astype(int))
            or np.any((scene[:, 10] < 0) | (scene[:, 10] >= len(SHAPES)))):
        raise fail('SCENE', 'GPU粒子场景无效或超过明确边界')
    expected = tile_index(scene, size)
    if (not isinstance(tiles, np.ndarray) or tiles.dtype != np.uint8 or tiles.ndim != 1
            or not tiles.flags.c_contiguous or not np.array_equal(tiles, expected)):
        raise fail('SCENE', 'GPU分块索引不匹配场景；拒绝未校验的设备索引')


class ParticleSource:
    def __init__(self, config, *, cancel=None):
        self.config = normalize(config); self.sha256 = identity(self.config)
        self.width, self.height = (self.config['canvas'][k] for k in ('width', 'height'))
        self.fps = Fraction(**{'numerator': self.config['fps']['num'], 'denominator': self.config['fps']['den']})
        self.duration = Fraction(self.config['duration_tick'], self.config['ticks_per_second'])
        self.frames = math.ceil(self.duration * self.fps)
        self.poll = cancel or (lambda: None)
        self.palette = [[_linear(c) for c in e['colors']] for e in self.config['emitters']]
        self.ends = [_linear(e['color_end']) if e['color_end'] else None for e in self.config['emitters']]
        from .particle_animation import EmitterAnimation
        self.animations=[EmitterAnimation(e,self.config['ticks_per_second'],self.config['duration_tick'],_linear,cancel=self.poll)
                         if e.get('keyframes') else None for e in self.config['emitters']]
        self.animation_metadata={str(i):a.metadata for i,a in enumerate(self.animations) if a is not None}

    def index_at(self, seconds, *, right_edge=False):
        point = Fraction(seconds)
        if point < 0 or point > self.duration or point == self.duration and not right_edge or point == 0 and right_edge:
            return None
        sample = point * self.fps
        index = math.ceil(sample) - 1 if right_edge else math.floor(sample)
        return max(0, min(self.frames - 1, index))

    def scene(self, frame):
        if type(frame) is not int or not 0 <= frame < self.frames:
            raise fail('FRAME', '粒子源帧索引越界')
        self.poll(); at = Fraction(frame, 1) / self.fps; particles = []
        for emitter, e in enumerate(self.config['emitters']):
            animation=self.animations[emitter]
            if animation:
                live=animation.live(at);palette=[np.asarray(c,np.float32) for c in live.pop('colors')]
                end=live.pop('color_end');end=np.asarray(end,np.float32) if end is not None else None
                births=animation.schedule.births(at,animation.max_lifetime,e['prewarm'])
            else:
                rate = Fraction(str(e['rate']))
                if not rate:continue
                first = math.ceil((at - Fraction(str(e['lifetime'][1]))) * rate)
                if not e['prewarm']: first = max(0, first)
                births=((birth,Fraction(birth,1)/rate) for birth in range(first,math.floor(at*rate)+1))
                palette=self.palette[emitter];end=self.ends[emitter]
            for birth,born_at in births:
                if len(particles) % 32 == 0: self.poll()
                u = uniform(self.config['seed'], emitter, birth)
                if animation:e={**e,**animation.born(born_at),**live}
                def mix(v, random): return v[0] + (v[1] - v[0]) * random
                life = mix(e['lifetime'], u[0]); age = max(0.,float(at-born_at))
                if not 0 <= age < life: continue
                q = age / life
                opacity = e['opacity']
                if e['fade_in']: opacity *= min(1., q / e['fade_in'])
                if e['fade_out']: opacity *= min(1., (1. - q) / e['fade_out'])
                phase = u[7] * math.tau
                opacity *= 1. - e['twinkle'][0] * (.5 + .5 * math.sin(math.tau * e['twinkle'][1] * age + phase))
                radius = mix(e['size'], u[3]) * (1. + (e['size_end'] - 1.) * q) * self.height
                if opacity <= 0 or radius <= 0: continue
                x = e['position'][0] + (u[1] - .5) * e['spread'][0] + mix(e['velocity'][0], u[4]) * age + .5 * e['acceleration'][0] * age**2
                x += e['sway'][0] * (math.sin(math.tau * e['sway'][1] * age + phase) - math.sin(phase))
                y = e['position'][1] + (u[2] - .5) * e['spread'][1] + mix(e['velocity'][1], u[5]) * age + .5 * e['acceleration'][1] * age**2
                angle = math.radians(mix(e['rotation'], u[6]) + mix(e['spin'], u[7]) * age)
                rgb = palette[min(len(palette)-1, int(u[6] * len(palette)))]
                if end is not None: rgb = rgb * np.float32(1-q) + end * np.float32(q)
                particles.append([x * self.width - .5, y * self.height - .5, radius, radius / e['aspect'],
                                  math.cos(angle), math.sin(angle), *rgb, opacity,
                                  SHAPES.index(e['shape']), e['softness'], e['glow']])
        return np.asarray(particles, np.float32).reshape(-1, 13)

    def frame(self, index, *, gpu=None, max_working_bytes=768*1024**2):
        self.poll()
        if type(max_working_bytes) is not int or max_working_bytes <= 0:
            raise fail('BUDGET', '粒子工作区配额必须为正整数字节')
        if self.width * self.height * 32 > max_working_bytes:
            raise fail('BUDGET', '粒子栅格工作区超过显式预算', required_bytes=self.width*self.height*32)
        scene = self.scene(index)
        tiles = tile_index(scene, (self.width, self.height), cancel=self.poll)
        self.last_frame_receipt={'source_frame_index':index,'active_particles':len(scene),
            'emitter_animation':self.animation_metadata,
            'rasterization':'GPU' if len(scene) and gpu is not None and gpu.active else 'CPU',
            'tile_count':math.ceil(self.width/TILE)*math.ceil(self.height/TILE),
            'tile_index_bytes':tiles.nbytes,'maximum_candidate_visits':MAX_RASTER_VISITS}
        if not len(scene):
            return np.zeros((self.height, self.width, 4), np.float32)
        if gpu is not None and gpu.active:
            return gpu.particles(scene, tiles, (self.width, self.height))
        result = np.zeros((self.height, self.width, 4), np.float32)
        for row in scene:
            self.poll(); x, y, rx, ry, c, s, red, green, blue, opacity, shape, soft, glow = row
            x0, x1, y0, y1 = bounds(row, self.width, self.height)
            if x0 >= x1 or y0 >= y1: continue
            # Row strips bound temporary masks even for a very large particle.
            for top in range(y0, y1, 64):
                self.poll(); bottom = min(top+64, y1)
                dx = np.arange(x0, x1, dtype=np.float32)[None, :] - x
                dy = np.arange(top, bottom, dtype=np.float32)[:, None] - y
                a = (dx*c + dy*s) / rx; b = (-dx*s + dy*c) / ry
                radial = np.sqrt(a*a + b*b)
                if shape == 1: distance = 1. - np.maximum(np.abs(a), np.abs(b))
                elif shape == 2: distance = 1. - np.abs(a) - np.abs(b)
                elif shape == 3: distance = .68 + .32 * np.cos(5. * np.arctan2(b, a)) - radial
                elif shape == 4: distance = .16 - np.abs(radial - .82)
                else: distance = 1. - radial
                coverage = np.clip(.5 + distance / max(float(soft), 1./max(float(min(rx, ry)), .0001)), 0, 1)
                if glow:
                    halo = np.exp(-radial*radial) * glow
                    coverage = 1. - (1.-coverage) * (1.-halo)
                alpha = (coverage * opacity).astype(np.float32)
                target = result[top:bottom, x0:x1]
                remain = np.float32(1.) - alpha
                target[:, :, :3] *= remain[:, :, None]
                target[:, :, :3] += alpha[:, :, None] * row[6:9]
                target[:, :, 3] = alpha + target[:, :, 3] * remain
        alpha = result[:, :, 3:4]
        np.divide(result[:, :, :3], alpha, out=result[:, :, :3], where=alpha > 0)
        result[:, :, :3][result[:, :, 3] == 0] = 0
        return result

    def sample(self, seconds, *, right_edge=False, **kwargs):
        index = self.index_at(seconds, right_edge=right_edge)
        return (None, None) if index is None else (self.frame(index, **kwargs), index)
