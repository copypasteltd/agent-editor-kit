"""Native byte coverage, bounded reusable masks and tiled linear text painting.

No media or authored RGB enters the byte rasterizer. The recipe preserves
ordered components and binary selection between two complete paragraphs.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal, convert_rgba
from .float_text_paint import PROTOCOL
from .media import ffmpeg_path
from .text_paint import COLOR_KEYS, resolve_color
from .utils import atomic_write_text

ENGINE = 'native-byte-coverage-tiled-linear-text-v1'
TILE_PIXELS = 16384


def error(code, message, **details):
    return AppError('FLOAT_TEXT_' + code, message, exit_code=2, diagnostics=details or None)


def scalar(expression, poll=lambda: None):
    """Interpret only the numeric expressions emitted by the subtitle compiler.

    This is not Python eval, an author expression evaluator or a wall clock.
    Conditional branches are lazy, matching native AVExpr's if semantics.
    """
    if len(expression) > 8192:
        raise error('EXPRESSION', '文字透明度表达式超过预算')
    try:
        tree = ast.parse(re.sub(r'\bif\s*\(', 'choose(', expression.strip("'")), mode='eval')
        if sum(1 for _ in ast.walk(tree)) > 512:
            raise ValueError('expression nodes')
        def read(node, depth=0):
            poll()
            if depth > 64:
                raise ValueError('expression depth')
            if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
                return float(node.value)
            child = lambda value: read(value, depth+1)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
                value = child(node.operand)
                return -value if isinstance(node.op, ast.USub) else value
            if isinstance(node, ast.BinOp):
                a, b = child(node.left), child(node.right)
                if isinstance(node.op, ast.Add): return a+b
                if isinstance(node.op, ast.Sub): return a-b
                if isinstance(node.op, ast.Mult): return a*b
                if isinstance(node.op, ast.Div): return a/b
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
                name = node.func.id
                if name == 'choose' and len(node.args) == 3:
                    return child(node.args[1] if child(node.args[0]) else node.args[2])
                args = [child(value) for value in node.args]
                if name in {'lt', 'lte', 'gt', 'gte'} and len(args) == 2:
                    a, b = args
                    return float({'lt': a < b, 'lte': a <= b, 'gt': a > b, 'gte': a >= b}[name])
                if name == 'clip' and len(args) == 3:
                    return max(args[1], min(args[2], args[0]))
            raise ValueError('unsupported expression node')
        result = read(tree.body)
        if not math.isfinite(result):
            raise ValueError('nonfinite expression')
        return result
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError, RecursionError) as exc:
        raise error('EXPRESSION', '编译后的文字透明度/开关表达式不可确定求值') from exc


class CoverageSnapshot:
    def __init__(self, host, width, height, author, frame_number, pipe_type):
        self.host, self.root = host, host.root
        self.width, self.height, self.author = width, height, author
        self.frame_number, self.pipe_type = frame_number, pipe_type
        self.nodes, self.paints, self.mask_records = {}, [], []

    def _token(self, node):
        token = 'coverage' + str(len(self.nodes))
        self.nodes[token] = node
        return token

    def __call__(self, parts):
        self.host.poll()
        options = dict(part.split('=', 1) for part in parts[1:] if '=' in part)
        enabled = {'boxcolor': options.get('box', '0') in {'1', 'true'},
                   'shadowcolor': bool(int(options.get('shadowx', '0')) or int(options.get('shadowy', '0'))),
                   'bordercolor': int(options.get('borderw', '0')) > 0, 'fontcolor': True}
        defaults = {'fontcolor': 'white', 'boxcolor': 'white', 'shadowcolor': 'black', 'bordercolor': 'black'}
        active = scalar(options.get('enable', '1'), self.host.poll) != 0
        parts = [re.sub(r'^drawtext@[^=]+=', 'drawtext=', parts[0]),
                 *(p for p in parts[1:] if p.split('=', 1)[0] not in {*COLOR_KEYS, 'enable', 'start_number'})]
        # Prefix text filenames contain the original author time. Address the
        # actual immutable text bytes so equal prefixes reuse the same mask.
        match = re.fullmatch(r"drawtext=textfile='([^']+)'", parts[0])
        if match:
            path = self.root / match[1]
            data = path.read_bytes()
            destination = self.root/'cache/float-text-coverage'/(hashlib.sha256(data).hexdigest()+'.txt')
            atomic_write_text(destination, data.decode('utf8'))
            parts[0] = "drawtext=textfile='"+destination.relative_to(self.root).as_posix()+"'"
        colors, components = [], []
        for key in COLOR_KEYS:
            if not enabled[key]:
                continue
            rgba, record = resolve_color(self.root, options.get(key, defaults[key]).strip("'"))
            converted, _ = convert_rgba(np.array([[rgba]], np.float32)/255,
                ColorSignal('bt709', 'srgb'), self.host.working, cancel=self.host.poll)
            linear = [float(value) for value in converted[0, 0]]
            colors.append({'component': key, **record, 'working_rgba': linear})
            if active and rgba[3]:
                mask = ':'.join([*parts, *(f'{k}={"white" if k == key else "black@0"}' for k in COLOR_KEYS)])
                components.append({'color': linear, 'mask': 'format=rgba,lutrgb=r=0:g=0:b=0:a=255,'+mask+',format=gbrap,extractplanes=r'})
        self.paints.append({'protocol': PROTOCOL, 'engine': ENGINE,
            'coverage': 'native-byte-white-glyph-on-opaque-black', 'colors': colors,
            'component_order': [k for k in COLOR_KEYS if enabled[k]],
            'alpha_application': 'coverage-times-authored-alpha-once',
            'media_color_rasterized_at_8bit': False})
        return self._token({'components': components})

    def select_coverage(self, normal, active, signals, mask):
        resolved = []
        for signal in signals:
            body, separator, expression = signal.rpartition(":enable=")
            if not separator:
                raise error('RECIPE', '逐词覆盖率开关缺失')
            if scalar(expression, self.host.poll):
                resolved.append(body)
        graph = 'format=gbrap,lutrgb=r=0:g=0:b=0:a=0,'
        if resolved:
            graph += ','.join(resolved)+','
        # Only the red plane carries a binary selection; no colors or alpha
        # are encoded into this mask and no Float32 canvas is needed here.
        graph += f"geq=r='{mask}':g=0:b=0:a=0,format=gbrap,extractplanes=r"
        return self._token({'normal': normal, 'active': active, 'selection': graph})

    def mask(self, graph, *, binary=False):
        self.host.poll()
        source = f'color=c=black:s={self.width}x{self.height}:r=1:d=1,'+graph+'[coverage]'
        if len(source.encode('utf8')) > 4*1024**2:
            raise error('BUDGET', '文字覆盖率图超过4MiB预算')
        digest = hashlib.sha256(source.encode('utf8')).hexdigest()
        cached = self.host.coverage_cache
        hit = digest in cached
        if hit:
            value = cached.pop(digest); cached[digest] = value
            self.host.metadata['coverage_cache_hits'] += 1
        else:
            path = self.root/'cache/float-text-coverage'/(digest+'.ffgraph')
            atomic_write_text(path, source)
            command = [ffmpeg_path(), '-nostdin', '-hide_banner', '-loglevel', 'error', '-filter_complex_threads', '1',
                '-filter_complex_script', str(path), '-map', '[coverage]', '-frames:v', '1', '-pix_fmt', 'gray', '-f', 'rawvideo', '-']
            expected = self.width*self.height
            with self.pipe_type(command, cwd=self.root, poll=self.host.poll, timeout=60) as pipe:
                raw = pipe.read(expected+1)
                if len(raw) != expected:
                    raise error('NATIVE', '文字覆盖率未返回完整字节栅格', expected_bytes=expected,
                                actual_bytes=len(raw), stderr=pipe.stderr())
                pipe.finish()
            value = np.frombuffer(raw, np.uint8).reshape(self.height, self.width)
            value.flags.writeable = False
            self.host.metadata['native_coverage_rasters'] += 1
            if value.nbytes <= self.host.cache_limit:
                while self.host.coverage_cached_bytes+value.nbytes > self.host.cache_limit and cached:
                    _, previous = cached.popitem(last=False)
                    self.host.coverage_cached_bytes -= previous.nbytes
                cached[digest] = value
                self.host.coverage_cached_bytes += value.nbytes
        if binary:
            for row in range(0, self.height, max(1, TILE_PIXELS//self.width)):
                self.host.poll()
                tile = value[row:row+max(1, TILE_PIXELS//self.width)]
                if np.any((tile != 0) & (tile != 255)):
                    raise error('SELECTION', '逐词选择必须返回二值覆盖率')
        self.mask_records.append({'graph_sha256': digest, 'cache_hit': hit, 'binary': binary})
        return value

    def over(self, target, *, color=None, coverage=None, surface=None, opacity=1.):
        gpu = self.host.gpu
        if gpu is not None and gpu.active and surface is not None:
            target[:] = gpu.over(target, surface, opacity, text_order=True)
            return
        rows = max(1, TILE_PIXELS//self.width)
        for y in range(0, self.height, rows):
            self.host.poll()
            bottom = target[y:y+rows].astype(np.float64)
            if surface is not None:
                top = surface[y:y+rows].astype(np.float64)
                rgb, alpha = top[:, :, :3], top[:, :, 3:4]*opacity
            else:
                rgb = np.asarray(color[:3], np.float64)
                alpha = coverage[y:y+rows, :, None].astype(np.float64)*(color[3]/255)*opacity
            previous = bottom[:, :, 3:4]
            total = alpha+previous*(1-alpha)
            numerator = rgb*alpha+bottom[:, :, :3]*previous*(1-alpha)
            result = target[y:y+rows]
            np.divide(numerator, total, out=numerator, where=total > 0)
            numerator[total[:, :, 0] == 0] = 0
            result[:, :, :3], result[:, :, 3:4] = numerator, total

    def evaluate(self, recipe):
        result = np.zeros((self.height, self.width, 4), np.float32)
        gpu = self.host.gpu
        for token in filter(None, recipe.split(',')):
            if token == 'null':
                continue
            node = self.nodes.get(token)
            if node is None:
                raise error('RECIPE', '未知文字覆盖率节点', token=token)
            if 'selection' in node:
                normal, active = self.evaluate(node['normal']), self.evaluate(node['active'])
                selection = self.mask(node['selection'], binary=True)
                if gpu is not None and gpu.active:
                    normal = gpu.select(normal, active, selection)
                else:
                    rows = max(1, TILE_PIXELS//self.width)
                    for y in range(0, self.height, rows):
                        self.host.poll()
                        selected = selection[y:y+rows] != 0
                        normal[y:y+rows][selected] = active[y:y+rows][selected]
                del active, selection
                self.over(result, surface=normal)
                del normal
            else:
                if gpu is not None and gpu.active and node['components']:
                    masks = np.stack([self.mask(c['mask']) for c in node['components']])
                    result = gpu.paint(masks, [c['color'] for c in node['components']], base=result)
                else:
                    for component in node['components']:
                        self.over(result, color=component['color'], coverage=self.mask(component['mask']))
        return result

    def render(self, plan, subtitles):
        from .render import _subtitle_filter
        layouts, warnings, recipes = [], [], []
        for subtitle in subtitles:
            self.host.poll()
            subtitle = json.loads(json.dumps(subtitle))
            for field in ('x', 'y'):
                if field in subtitle['style']:
                    subtitle['style'][field] = re.sub(r'\bn\b', str(self.frame_number), str(subtitle['style'][field]))
            alpha, layout = [], {}
            recipe = _subtitle_filter(self.root, subtitle, warnings, plan['id'], plan['start_tick']/self.host.tps,
                plan['duration_tick']/self.host.tps, rotation_supported=True, assets=self.host.assets,
                time_expression=format(self.author, '.17g'), animation_alpha=alpha, layout_evidence=layout, paint_text=self,
                render_clock={'maps': [], 'reverse_boundary_bias_seconds': 0.}, final_fps=str(self.host.fps),
                frame_origin=self.author, float_paint=True)
            if recipe:
                opacity = math.prod(scalar(expression, self.host.poll) for expression in alpha)
                if not 0 <= opacity <= 1:
                    raise error('ALPHA', '文字透明度须在0..1范围')
                layouts.append(layout); recipes.append({'recipe': recipe, 'opacity': opacity})
        if warnings:
            raise error('UNSUPPORTED', '文字编译包含近似或未支持操作', warnings=warnings)
        identity = json.dumps({'nodes': self.nodes, 'recipes': recipes}, sort_keys=True, ensure_ascii=False)
        if len(identity.encode('utf8')) > 4*1024**2:
            raise error('BUDGET', '文字覆盖率编排超过4MiB预算')
        digest = hashlib.sha256(identity.encode('utf8')).hexdigest()
        path = self.root/'cache/float-text-coverage'/(digest+'.recipe.json')
        atomic_write_text(path, identity)
        value = np.zeros((self.height, self.width, 4), np.float32)
        for record in recipes:
            self.host.poll()
            painted = self.evaluate(record['recipe'])
            # Apply animation to the complete paragraph once. The outer
            # source-over does not repaint any glyph or selected word.
            opacity = record['opacity']
            if opacity != 1:
                rows = max(1, TILE_PIXELS//self.width)
                for y in range(0, self.height, rows):
                    self.host.poll()
                    painted[y:y+rows, :, 3] *= opacity
                    if opacity == 0:
                        painted[y:y+rows, :, :3] = 0
            self.over(value, surface=painted)
            del painted
        self.host.metadata['native_snapshots'] += 1
        self.host.metadata['coverage_cached_bytes'] = self.host.coverage_cached_bytes
        return value, {'protocol': PROTOCOL, 'engine': ENGINE, 'author_seconds': self.author,
            'author_frame_number': self.frame_number, 'graph_sha256': digest,
            'graph': path.relative_to(self.root).as_posix(), 'pixels_sha256': hashlib.sha256(value.tobytes()).hexdigest(),
            'paints': self.paints, 'layouts': layouts, 'coverage_rasters': self.mask_records,
            'cache_hit': False, 'color_raster': 'Float32-RGBA', 'glyph_coverage_bits': 8,
            'media_pixels_in_native_graph': False, 'frame_grid_quantization': False,
            'component_arithmetic': 'GPU binary64;Float32 component boundary' if self.host.gpu is not None and self.host.gpu.active else 'Float64 tiled;Float32 component boundary',
            'GPU': self.host.gpu is not None and self.host.gpu.active, 'tile_pixels': TILE_PIXELS}
