"""Native glyph coverage with Float32 linear-light component composition.

Only glyph coverage is rasterized at eight bits. Authored colors are converted
to the declared working signal before any source-over operation. No media
image enters this graph and no float color surface is converted back to RGBA8.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

from .float_color_signal import ColorSignal, convert_rgba
from .text_paint import COLOR_KEYS, resolve_color

PROTOCOL = 'native-glyph-linear-float32-paint-v1'
FORMAT = 'gbrapf32le'


def over_graph(background: str, foreground: str, target: str) -> str:
    """Join equal straight-alpha Float32 rasters and source-over in Float32."""
    incoming = 'alpha(X+W/2,Y)'
    previous = 'alpha(X,Y)'
    alpha = f'({incoming}+{previous}*(1-{incoming}))'
    expressions = []
    for key in ('r', 'g', 'b'):
        color = f'({key}(X+W/2,Y)*{incoming}+{key}(X,Y)*{previous}*(1-{incoming}))'
        expressions.append(f"{key}='if(gt({alpha},0),{color}/max({alpha},1e-30),0)'")
    expressions.append(f"a='{alpha}'")
    return (f'[{background}][{foreground}]hstack=inputs=2,'
            + 'geq=' + ':'.join(expressions)
            + f',crop=iw/2:ih:0:0,format={FORMAT}[{target}]')


def select_graph(normal: str, active: str, mask: str) -> str:
    """Select complete float paragraph pixels using a binary coverage mask."""
    expressions = [f"{key}='if(gt(r(X+2*W/3,Y),0.5),{key}(X+W/3,Y),{key}(X,Y))'"
                   for key in ('r', 'g', 'b')]
    expressions.append("a='if(gt(r(X+2*W/3,Y),0.5),alpha(X+W/3,Y),alpha(X,Y))'")
    return (f'[{normal}][{active}][{mask}]hstack=inputs=3,geq='
            + ':'.join(expressions) + f',crop=iw/3:ih:0:0,format={FORMAT}')


def paint_drawtext(root, parts, scope, *, working_signal, coverage_profile, cancel=None):
    """Keep native shaping/layout and paint box, shadow, border and fill."""
    poll = cancel or (lambda: None)
    poll()
    options = dict(part.split('=', 1) for part in parts[1:] if '=' in part)
    enabled = {'boxcolor': options.get('box', '0') in {'1', 'true'},
               'shadowcolor': bool(int(options.get('shadowx', '0')) or int(options.get('shadowy', '0'))),
               'bordercolor': int(options.get('borderw', '0')) > 0, 'fontcolor': True}
    defaults = {'fontcolor': 'white', 'boxcolor': 'white', 'shadowcolor': 'black', 'bordercolor': 'black'}
    components, colors = [], []
    for key in COLOR_KEYS:
        poll()
        if not enabled[key]:
            continue
        rgba, record = resolve_color(root, options.get(key, defaults[key]).strip("'"))
        converted, _ = convert_rgba(np.array([[rgba]], np.float32) / 255,
            ColorSignal('bt709', 'srgb'), working_signal, cancel=poll)
        linear = [float(v) for v in converted[0, 0]]
        colors.append({'component': key, **record, 'working_rgba': linear})
        if rgba[3]:
            components.append((key, linear))
    evidence = {'protocol': PROTOCOL, 'coverage': 'native-white-glyph-on-opaque-black-8bit',
                'working_color': vars(working_signal), 'authored_color': {'primaries': 'bt709', 'transfer': 'srgb'},
                'component_order': [key for key, _ in components], 'colors': colors,
                'alpha_application': 'coverage-times-authored-alpha-once',
                'component_composition': 'Float32-straight-source-over-with-zero-alpha-RGB-cleared',
                'media_color_rasterized_at_8bit': False, 'coverage_conversion': coverage_profile}
    if not components:
        return f'format={FORMAT}', evidence
    token = hashlib.sha256((scope + json.dumps(parts) + str(working_signal)).encode('utf8')).hexdigest()[:16]
    base = f'fpaint_{token}_base'
    masks = [f'fpaint_{token}_mask{i}' for i in range(len(components))]
    filters = [f'split={len(components)+1}[{base}]' + ''.join(f'[{name}]' for name in masks)]
    previous = base
    for index, ((component, rgba), mask) in enumerate(zip(components, masks)):
        poll()
        paint = [parts[0], *(part for part in parts[1:] if part.split('=', 1)[0] not in COLOR_KEYS)]
        paint.extend(f'{key}={"white" if key == component else "black@0"}' for key in COLOR_KEYS)
        colored, target = f'fpaint_{token}_color{index}', f'fpaint_{token}_over{index}'
        red, green, blue, alpha = (format(value, '.17g') for value in rgba)
        black = format(coverage_profile['black'], '.17g')
        scale = coverage_profile['code_scale']
        coverage = f'(clip(round((r(X,Y)-({black}))*{scale}),0,255)/255)'
        # drawtext only sees an opaque black coverage raster. The format
        # conversion normalizes coverage to 0..1 without a transfer function.
        filters.append(f'[{mask}]format=rgba,lutrgb=r=0:g=0:b=0:a=255,' + ':'.join(paint)
            + f",format=gbrap,format={FORMAT},geq=r={red}:g={green}:b={blue}:a='({coverage})*{alpha}'[{colored}]")
        filters.append(over_graph(previous, colored, target))
        previous = target
    filters.append(f'[{previous}]format={FORMAT}')
    return ';'.join(filters), evidence
