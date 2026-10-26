"""Bounded native glyph snapshots for authored Float32 titles and captions.

Text is evaluated at the original presentation clock, including nested reverse
limits. FFmpeg rasterizes glyph coverage, then composites each authored color
in linear Float32. Media pixels never enter the native glyph process.
"""
from __future__ import annotations

from collections import OrderedDict
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

from .artifact_locks import artifact_entry
from .captions import parse_srt
from .clip_windows import validate_window
from .errors import AppError
from .float_native_pipe import NativePipe
from .float_text_paint import PROTOCOL
from .float_text_coverage import CoverageSnapshot, TILE_PIXELS
from .media import ffmpeg_path
from .policy import resolve_local_path

MAX_TEXT_BYTES = 64 * 1024
MAX_CUE_BYTES = 4 * 1024**2
MAX_CUES = 8192
DEFAULT_CACHE_BYTES = 64 * 1024**2
STYLE_FIELDS = {'font_asset_id', 'fontfile', 'fontsize', 'fontcolor', 'active_color', 'highlight_color',
    'box', 'boxcolor', 'boxborderw', 'box_padding', 'borderw', 'bordercolor', 'shadowx', 'shadowy',
    'shadowcolor', 'text_align', 'align', 'line_spacing', 'boxw', 'boxh', 'tabsize', 'text_shaping',
    'fix_bounds', 'expansion', 'max_width', 'wrap_width', 'animation', 'x', 'y'}


def error(code, message, **details):
    return AppError('FLOAT_TEXT_' + code, message, exit_code=2, diagnostics=details or None)


class _TextPipe(NativePipe):
    def __init__(self, *args, poll, **kwargs):
        self.poll = poll
        super().__init__(*args, **kwargs)

    def check(self):
        self.poll()
        super().check()


class FloatTextHost:
    def __init__(self, root, assets, working_signal, tps, fps, *, cancel=None,
                 max_working_bytes=768 * 1024**2, cache_bytes=DEFAULT_CACHE_BYTES, gpu=None):
        self.root = Path(root).resolve() if root is not None else None
        self.assets, self.working, self.tps, self.fps = assets, working_signal, tps, fps
        self.poll = cancel or (lambda: None)
        self.gpu = gpu
        if type(cache_bytes) is not int or not 0 <= cache_bytes <= 256 * 1024**2:
            raise error('BUDGET', '文字表面缓存必须在0..256MiB范围')
        if type(max_working_bytes) is not int or not 1 <= max_working_bytes <= 768*1024**2:
            raise error('BUDGET', '文字工作区预算必须在1..768MiB范围')
        self.max_working_bytes = max_working_bytes
        # Cache is a ceiling, not a compulsory allocation. Keep small explicit
        # workspaces useful for small canvases while reserving both ceilings.
        self.cache_limit = min(cache_bytes, max_working_bytes//4)
        self.cache, self.cached_bytes, self.artifacts = OrderedDict(), 0, {}
        self.coverage_cache, self.coverage_cached_bytes = OrderedDict(), 0
        self.coverage_profile = None
        self.metadata = {'protocol': PROTOCOL, 'authored_color': {'primaries': 'bt709', 'transfer': 'srgb'},
            'working_signal': vars(working_signal), 'glyph_coverage_bits': 8, 'color_component_bits': 32,
            'media_pixels_in_glyph_process': False, 'cache_limit_bytes': self.cache_limit,
            'requested_cache_limit_bytes': cache_bytes,
            'cached_bytes': 0, 'cache_hits': 0, 'native_snapshots': 0, 'plans': [],
            'coverage_cache_limit_bytes': self.cache_limit, 'coverage_cached_bytes': 0,
            'coverage_cache_hits': 0, 'native_coverage_rasters': 0,
            'admission': {'max_working_bytes': max_working_bytes, 'float_surfaces': 4,
                          'native_and_scratch_bytes_per_pixel': 8, 'two_cache_limits_reserved': True,
                          'tile_pixels': TILE_PIXELS, 'estimate_is_peak_RSS': False},
            'GPU': bool(gpu is not None and gpu.active), 'GPU_scope': 'color-components/paragraph-over/word-selection;glyph-rasterization-on-CPU',
            'HDR_accepted': False, 'whole_movie_cache': False}

    def _pin(self, path, role, expected=None):
        self.poll()
        entry = artifact_entry(Path(path).resolve(), role)
        if expected is not None and entry['sha256'] != expected:
            raise error('INPUT_CHANGED', '文字依赖与登记SHA不一致', path=str(path))
        old = self.artifacts.get(entry['path'])
        if old is not None and entry['sha256'] != old['sha256']:
            raise error('INPUT_CHANGED', '文字依赖在同一执行过程中改变', path=entry['path'])
        self.artifacts[entry['path']] = entry
        return entry

    def prepare(self, clip, *, independent):
        self.poll()
        if self.root is None or not self.root.is_dir():
            raise error('ROOT', '浮点文字需要明确的本地工程根目录')
        if self.working.transfer != 'linear':
            raise error('SIGNAL', '文字组件合成要求明确线性光工作域')
        generator = clip.get('generator')
        if generator and (not independent or generator != {'type': 'text'}):
            raise error('GENERATOR', '当前文字生成器要求subtitle轨道及明确type=text')
        subtitle = copy.deepcopy(clip.get('subtitle') or {})
        if not isinstance(subtitle, dict):
            raise error('CONFIG', 'subtitle必须是对象')
        allowed={'text','style','word_timing','ticks_per_second','animation','asset_uri','asset_time_base','asset_time_offset_tick'}
        if set(subtitle)-allowed:
            raise error('CONFIG','尚未移植的字幕字段不得忽略',fields=sorted(set(subtitle)-allowed))
        asset = self.assets.get(clip.get('asset_id'))
        if independent and asset and asset.get('kind') == 'subtitle' and 'text' not in subtitle:
            subtitle.setdefault('asset_uri', asset['uri'])
        if not isinstance(subtitle.get('style', {}), dict):
            raise error('CONFIG', '文字style必须是对象')
        style = subtitle.setdefault('style', {})
        if set(style) - STYLE_FIELDS:
            raise error('STYLE', '尚未移植的文字样式不得忽略', fields=sorted(set(style) - STYLE_FIELDS))
        if not style.get('font_asset_id') and not style.get('fontfile'):
            raise error('FONT_REQUIRED', '浮点文字要求明确的本地font资产或fontfile，不采用系统字体回退')
        from .render import _subtitle_font_path, _load_subtitle_font_metrics
        font = _subtitle_font_path(self.root, style, self.assets)
        registered = self.assets.get(style.get('font_asset_id'))
        self._pin(font, 'float-text-font', registered.get('sha256') if registered else None)
        if _load_subtitle_font_metrics(font, int(style.get('fontsize', 52))) is None:
            raise error('FONT_METRICS', '本地字体无法读取真实布局度量，未退回平均字宽')
        self._pin(ffmpeg_path(), 'float-text-native-runtime')
        import PIL
        for dependency in sorted(Path(PIL.__file__).parent.rglob('*')):
            if dependency.is_file() and dependency.suffix.lower() in {'.py','.pyd','.dll'}:
                self._pin(dependency, 'float-text-font-metrics-runtime')
        for name in ('float_text', 'float_text_paint', 'float_text_coverage', 'text_paint', 'text_layout', 'text_highlight', 'text_typing', 'render', 'captions'):
            self._pin(Path(__file__).with_name(name + '.py'), 'float-text-implementation')
        cues = None
        if subtitle.get('asset_uri'):
            path = resolve_local_path(self.root, subtitle['asset_uri'], field='subtitle.asset_uri')
            if path.suffix.lower() != '.srt':
                raise error('ASSET_FORMAT', '浮点文件字幕当前接受纯文本SRT；ASS/VTT富样式尚未移植，不使用8位libass回落')
            if path.stat().st_size > MAX_CUE_BYTES:
                raise error('BUDGET', 'SRT超过4MiB预算')
            self._pin(path, 'float-text-srt', asset.get('sha256') if asset and asset.get('kind') == 'subtitle' and asset['uri'] == subtitle['asset_uri'] else None)
            text = path.read_text('utf-8-sig')
            cues = parse_srt(text)
            if len(cues) != len(re.split(r'\n\s*\n', text.replace('\r\n', '\n').replace('\r', '\n').strip())):
                raise error('CUES', 'SRT包含未解析的非空块，不能跳过错误字幕')
            if not cues or len(cues) > MAX_CUES:
                raise error('CUES', 'SRT必须包含1..8192条明确字幕')
            for cue in cues:
                if not all(math.isfinite(cue[k]) for k in ('start', 'end')) or cue['end'] <= cue['start'] or re.search(r'<[^>]+>|\{[^}]+\}', cue['text']):
                    raise error('CUES', 'SRT要求正时窗与纯文字；富样式标签必须先显式转换')
                self._check_text(cue['text'])
            if subtitle.get('word_timing') or subtitle.get('animation') or style.get('animation'):
                raise error('CUES_ANIMATION', '文件字幕的逐词或动画需先转换成可编辑文字片段，不能静默丢弃')
        else:
            if 'text' not in subtitle:
                raise error('CONFIG', '文字片段需要text或SRT资产')
            self._check_text(subtitle['text'])
            words=subtitle.get('word_timing')
            if words is not None:
                base=subtitle.get('ticks_per_second',90000)
                if type(base) is not int or base<1 or not isinstance(words,list) or not 1<=len(words)<=128:
                    raise error('WORDS','逐词字幕需要1..128项及正整数ticks_per_second')
                for word in words:
                    if not isinstance(word,dict) or not word.get('text',word.get('word')):
                        raise error('WORDS','逐词字幕每项需要明确文字及正时间范围')
                    begin=word.get('start',word.get('start_seconds'))
                    end=word.get('end',word.get('end_seconds'))
                    if begin is None and type(word.get('start_tick')) is int:begin=word['start_tick']/base
                    if end is None and type(word.get('end_tick')) is int:end=word['end_tick']/base
                    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (begin,end)) or not 0<=begin<end:
                        raise error('WORDS','逐词字幕每项需要有限正时间范围，不能跳过错误条目')
        if subtitle.get('asset_time_base', 'sequence') not in {'clip', 'sequence'} or type(subtitle.get('asset_time_offset_tick', 0)) is not int:
            raise error('CLOCK', '文件字幕需要sequence/clip时钟及整数tick偏移')
        # Expressions are snapshots of a deterministic author clock. Stateful
        # random/metadata/wall-clock expansion cannot be cached or replayed.
        for field in ('x', 'y'):
            if re.search(r'\b(?:rand|random|st|ld|print|metadata)\b', str(style.get(field, ''))):
                raise error('EXPRESSION', '浮点文字位置要求无状态确定性表达式', field=field)
        if style.get('expansion', 'none') != 'none':
            raise error('EXPANSION', '浮点文字要求expansion=none，不能使用墙钟或外部元数据展开')
        style['expansion'] = 'none'
        animation = subtitle.get('animation') or style.get('animation') or {}
        if not isinstance(animation,dict):
            raise error('ANIMATION','文字animation必须是对象')
        kind = str(animation.get('type', '')).lower().replace('-', '_')
        if kind not in {'', 'fade', 'fade_in', 'fade_out', 'slide_up', 'slide_down', 'slide_left', 'slide_right',
                        'typewriter', 'typing', 'pop', 'bounce', 'rotate'}:
            raise error('ANIMATION', '尚未实现的文字动画不得近似替代', kind=kind)
        handle = clip.get('_source_handle') or {}
        start = int(handle.get('authored_start_tick', (clip.get('presentation_window') or {}).get('authored_start_tick',clip['timeline_start_tick'])))
        duration = int(handle.get('authored_duration_tick', validate_window(clip,allow_tracking=True)))
        if kind=='rotate':
            animation=copy.deepcopy(animation)
            animation.setdefault('duration',min(.3,max(.05,duration/self.tps/4 or .3)))
        identity = hashlib.sha256(json.dumps({'clip': clip, 'subtitle': subtitle, 'working': vars(self.working)},
            ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf8')).hexdigest()
        plan = {'id': clip['id'], 'identity': identity, 'subtitle': subtitle, 'cues': cues,
                'start_tick': start, 'duration_tick': duration, 'independent': independent,
                'animation_type': kind, 'animation': animation}
        self.metadata['plans'].append({'clip': clip['id'], 'identity': identity, 'independent': independent,
            'source': 'plain-SRT' if cues is not None else 'editable-text', 'cue_count': len(cues) if cues else 0,
            'font': str(font), 'font_sha256': self.artifacts[str(font.resolve())]['sha256'],
            'clock': 'original-presentation-including-trim-offset; exact-parent-left-limit'})
        self.metadata['artifacts']=list(self.artifacts.values())
        return plan

    @staticmethod
    def _check_text(text):
        if not isinstance(text, str) or len(text.encode('utf8')) > MAX_TEXT_BYTES:
            raise error('BUDGET', '文字必须是64KiB以内的字符串')
        if any(ord(c) < 32 and c not in '\n\t\r' or ord(c) == 127 for c in text):
            raise error('CONTROL', '文字不能包含换行/制表之外的控制字符')

    def sample(self, plan, sequence_time, animation_tick, size, *, left_limit=False):
        self.poll()
        width, height = size
        if any(type(value) is not int or value < 2 for value in size):
            raise error('BUDGET', '文字画布尺寸必须为至少2的整数')
        # Four full Float32 surfaces cover the outer result and a selected
        # normal/active paragraph. Native masks are one byte per pixel and
        # are rendered sequentially. Reserve native scratch, both bounded
        # caches and Float64 tile scratch; this is not a process RSS cap.
        estimate = width * height * 72 + min(width*height, TILE_PIXELS)*512 + 2*self.cache_limit + 4096
        if min(width, height) < 2 or estimate > self.max_working_bytes:
            raise error('BUDGET', '文字原生栅格工作区估算超过显式单次预算', estimated_working_bytes=estimate,
                        max_working_bytes=self.max_working_bytes, width=width, height=height)
        author_exact = Fraction(plan['start_tick'], self.tps) + Fraction(animation_tick) / self.tps
        author = float(author_exact)
        if left_limit:
            author = math.nextafter(author, -math.inf)
        frame_number = max(0, math.ceil(author_exact * self.fps) - 1 if left_limit else math.floor(author_exact * self.fps))
        subtitle = copy.deepcopy(plan['subtitle'])
        active = [subtitle]
        if plan['cues'] is not None:
            cue_time = Fraction(sequence_time) if subtitle.get('asset_time_base', 'sequence') == 'sequence' else Fraction(animation_tick) / self.tps
            cue_time += Fraction(subtitle.get('asset_time_offset_tick', 0), self.tps)
            active = []
            for cue in plan['cues']:
                begin, end = Fraction(str(cue['start'])), Fraction(str(cue['end']))
                if (begin < cue_time <= end) if left_limit else (begin <= cue_time < end):
                    active.append({'text': cue['text'], 'style': subtitle['style']})
            if len(active) > 16:
                raise error('BUDGET', '同一文字片段最多16条同时活动的SRT字幕')
        dynamic = bool(plan['animation_type'] or subtitle.get('word_timing') or
            re.search(r'\b(?:t|n)\b', str(subtitle['style'].get('x', '')) + ' ' + str(subtitle['style'].get('y', ''))))
        # Static shapes can share their surface across authored times. Animated
        # snapshots are keyed by the exact host time, not by a CFR source cache.
        key = (plan['identity'], width, height, json.dumps(active, sort_keys=True, ensure_ascii=False),
               author.hex() if dynamic else None, frame_number if dynamic else None)
        if key in self.cache:
            value, record = self.cache.pop(key); self.cache[key] = (value, record)
            self.metadata['cache_hits'] += 1
            return value.copy(), {**copy.deepcopy(record), 'cache_hit': True, 'author_seconds': author,
                                  'author_frame_number': frame_number}
        if not active or all(not item.get('text') for item in active):
            value = np.zeros((height, width, 4), np.float32)
            record = {'protocol': PROTOCOL, 'author_seconds': author, 'empty_text': True, 'cache_hit': False}
        else:
            value, record = self._native(plan, active, author, frame_number, width, height)
            record['estimated_working_bytes'] = estimate
        if value.nbytes <= self.cache_limit:
            while self.cached_bytes + value.nbytes > self.cache_limit and self.cache:
                _, (old, _) = self.cache.popitem(last=False); self.cached_bytes -= old.nbytes
            self.cache[key] = (value, copy.deepcopy(record)); self.cached_bytes += value.nbytes
            self.metadata['cached_bytes'] = self.cached_bytes
        return value.copy(), record

    def _native(self, plan, subtitles, author, frame_number, width, height):
        if self.coverage_profile is None:
            self._coverage_conversion()
        return CoverageSnapshot(self, width, height, author, frame_number, _TextPipe).render(plan, subtitles)

    def _coverage_conversion(self):
        # Validate the byte plane directly. No swscale Float32 conversion or
        # discrete recovery classifier participates in glyph coverage now.
        graph = 'nullsrc=s=256x2:r=1:d=1,format=gbrap,geq=r=X:g=X:b=X:a=255,format=gbrap,extractplanes=r'
        command = [ffmpeg_path(), '-nostdin', '-v', 'error', '-filter_threads', '1', '-f', 'lavfi', '-i', graph,
            '-frames:v', '1', '-pix_fmt', 'gray', '-f', 'rawvideo', '-']
        expected = 256 * 2
        with _TextPipe(command, cwd=self.root, poll=self.poll, timeout=30) as pipe:
            raw = pipe.read(expected + 1)
            if len(raw) != expected:
                raise error('COVERAGE', '字形覆盖率转换探针未返回完整原始栅格', stderr=pipe.stderr())
            pipe.finish()
        planes = np.frombuffer(raw, np.uint8).reshape(2, 256)
        maximum = float(np.max(np.abs(planes.astype(np.float64) - np.arange(256, dtype=np.float64)[None, :])))
        if maximum != 0:
            raise error('COVERAGE', '字形覆盖率转换不满足256码值独立参考，不使用近似回落', max_absolute_error=maximum)
        self.coverage_profile = {'protocol': 'native-byte-glyph-coverage-ramp-v1', 'black': 0, 'white': 255,
            'code_scale': 1, 'codes_checked': 256, 'max_code_error': maximum,
            'raw_sha256': hashlib.sha256(raw).hexdigest(),
            'ffmpeg_sha256': self.artifacts[str(Path(ffmpeg_path()).resolve())]['sha256']}
        self.metadata['coverage_conversion'] = self.coverage_profile

    def rotation(self, plan, animation_tick):
        if plan['animation_type'] != 'rotate':
            return 0.
        animation = plan['animation']
        delay = max(0., float(animation.get('delay', 0.)))
        duration = max(.001, float(animation.get('duration', .3)))
        progress = max(0., min(1., (float(animation_tick) / self.tps - delay) / duration))
        start = float(animation.get('from_degrees', animation.get('from', -90.)))
        end = float(animation.get('to_degrees', animation.get('to', animation.get('angle', 0.))))
        if not all(math.isfinite(v) for v in (duration, delay, start, end)):
            raise error('ANIMATION', '文字旋转动画必须为有限值')
        return start + (end - start) * progress

    def verify(self):
        for previous in self.artifacts.values():
            self.poll()
            if artifact_entry(Path(previous['path']), previous['role'])['sha256'] != previous['sha256']:
                raise error('INPUT_CHANGED', '文字字体、字幕或执行实现发生变化', path=previous['path'])
