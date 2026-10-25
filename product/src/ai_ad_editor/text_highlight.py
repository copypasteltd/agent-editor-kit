"""Native drawtext measurements and whole-paragraph highlight selection.

Normal and active paints contain the identical shaped paragraph. A binary
selection chooses pixels between them; a timed word is never painted twice.
No Pillow/average advance participates in the selection coordinates.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .errors import AppError
from .media import ffmpeg_path
from .text_layout import TextLayout, graphemes
from .utils import atomic_write_json, atomic_write_text, run_process, sha256_file

FIELDS = ('text_w', 'text_h', 'ascent', 'descent', 'font_a', 'font_d',
          'top_a', 'bottom_d', 'line_h', 'max_glyph_h', 'max_glyph_w')


@lru_cache(maxsize=16)
def _fingerprint(path: str, size: int, modified: int) -> str:
    return sha256_file(Path(path))


def file_fingerprint(path: Path) -> str:
    stat = path.stat()
    return _fingerprint(str(path.resolve()), stat.st_size, stat.st_mtime_ns)


def _quoted(value: str) -> str:
    return "'" + value.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'") + "'"


def native_metrics(root: Path, font: Path, size: int, texts: list[str], style: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Measure on the same local FFmpeg binary/font used to paint the title.

    drawtext's diagnostic width64 preserves fractional native advance. Public
    expression variables are emitted with unique numeric tags, independently
    of logger addresses/order. Unsupported diagnostic formats fail explicitly.
    """
    texts = list(dict.fromkeys(texts))
    if len(texts) > 512 or sum(len(text) for text in texts) > 131072:
        raise AppError('SUBTITLE_WORD_LAYOUT_BUDGET', '逐字布局超过本地度量预算（512 项 / 131072 字符）', exit_code=2)
    executable = Path(ffmpeg_path()).resolve()
    identity = {'protocol': 'drawtext-native-metrics-v1', 'ffmpeg_sha256': file_fingerprint(executable),
                'font_sha256': file_fingerprint(font), 'fontsize': size, 'texts': texts,
                'line_spacing': int(style.get('line_spacing', 0)), 'tabsize': int(style.get('tabsize', 4)),
                'text_shaping': bool(style.get('text_shaping', True))}
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    directory = root / 'cache' / 'text-metrics' / digest
    directory.mkdir(parents=True, exist_ok=True)
    cached = directory / 'metrics.json'
    if cached.is_file():
        try:
            record = json.loads(cached.read_text(encoding='utf-8-sig'))
            if record['identity'] == identity and set(record['metrics']) == set(texts):
                values = record['metrics']
                if all(set(FIELDS) <= set(value) and all(isinstance(value[key], (int, float)) and math.isfinite(value[key]) for key in FIELDS)
                       and isinstance(value.get('lines64'), list) and value['lines64'] and all(isinstance(width, int) and 0 <= width < 2**30 for width in value['lines64']) for value in values.values()):
                    return values, {'protocol': identity['protocol'], 'cache_key': digest, 'ffmpeg_sha256': identity['ffmpeg_sha256'],
                                    'font_sha256': identity['font_sha256'], 'query_count': len(texts)}
        except (OSError, KeyError, TypeError, ValueError):
            pass
    # Only ASCII project-relative textfile names enter the filter graph. Font
    # path is supplied through the local runtime's existing path alias helper.
    from .render import _filter_file_path
    font_name = _filter_file_path(root, font)
    metrics: dict[str, dict[str, Any]] = {}
    for first in range(0, len(texts), 24):
        filters = []
        batch = texts[first:first+24]
        for offset, text in enumerate(batch):
            index = first + offset
            path = directory / f'text-{index:03}.txt'
            atomic_write_text(path, text)
            prints = '+'.join(f'0*print({name}+{(offset*len(FIELDS)+field+1)*1000000},24)' for field, name in enumerate(FIELDS))
            filters.append(f'drawtext@avk_m{offset}=textfile={_quoted(path.relative_to(root).as_posix())}'
                           + f':fontfile={_quoted(font_name)}:fontsize={size}:expansion=none'
                           + f":line_spacing={identity['line_spacing']}:tabsize={identity['tabsize']}"
                           + f":text_shaping={int(identity['text_shaping'])}:x={_quoted(prints)}:y=0")
        graph = directory / f'probe-{first:03}.ffgraph'
        atomic_write_text(graph, ','.join(filters))
        result = run_process([str(executable), '-hide_banner', '-loglevel', 'debug', '-f', 'lavfi',
                              '-i', 'color=c=black:s=16x16:r=1:d=1', '-filter_script:v', str(graph),
                              '-frames:v', '1', '-f', 'null', '-'], cwd=root, timeout=60)
        atomic_write_text(directory / f'probe-{first:03}.log', result.stderr)
        if result.returncode:
            raise AppError('SUBTITLE_NATIVE_METRICS_FAILED', '本地 FFmpeg 字形度量失败', exit_code=6, cause=result.stderr[-3000:])
        tagged = {}
        for match in re.finditer(r'^(?:\[Eval[^\]]*\]\s*)?([0-9]+\.[0-9]+)\s*$', result.stderr, re.MULTILINE):
            value = float(match[1])
            tag = math.floor((value + 100000) / 1000000)
            tagged[tag] = value - tag * 1000000
        for offset, text in enumerate(batch):
            widths = {}
            for match in re.finditer(r'\[drawtext@avk_m' + str(offset) + r'\s+@[^\]]+\]\s+Line:\s+(\d+).*?width64:\s+(\d+)', result.stderr):
                widths[int(match[1])] = int(match[2])
            value = {name: tagged.get(offset*len(FIELDS)+field+1) for field, name in enumerate(FIELDS)}
            value['lines64'] = [widths[i] for i in range(len(widths))]
            if widths and max(widths.values()) > 500000*64:
                raise AppError('SUBTITLE_WORD_LAYOUT_BUDGET','原生单行字宽超过 500000 像素度量上限',exit_code=2)
            if any(value[name] is None for name in FIELDS) or len(widths) != text.count('\n')+1:
                raise AppError('SUBTITLE_NATIVE_METRICS_UNAVAILABLE', '当前 FFmpeg 未返回完整的原生字形度量；不能退回平均字宽', exit_code=10)
            metrics[text] = value
    atomic_write_json(cached, {'identity': identity, 'metrics': metrics})
    return metrics, {'protocol': identity['protocol'], 'cache_key': digest, 'ffmpeg_sha256': identity['ffmpeg_sha256'],
                     'font_sha256': identity['font_sha256'], 'query_count': len(texts)}


def _position(expression: str, values: dict[str, Any]) -> str:
    aliases = {'tw': 'text_w', 'th': 'text_h', 'lh': 'line_h', 'max_glyph_a': 'ascent', 'max_glyph_d': 'descent'}
    expression = re.sub(r'\b(?:' + '|'.join((*values, *aliases)) + r')\b',
                        lambda m: f"({float(values[aliases.get(m[0], m[0])]):.9f})", expression)
    names = {'main_w': 'W', 'w': 'W', 'main_h': 'H', 'h': 'H', 't': 'T', 'n': 'N',
             'sar': '1', 'dar': '(W/H)', 'hsub': '1', 'vsub': '1'}
    return re.sub(r'\b(?:' + '|'.join(names) + r')\b', lambda m: names[m[0]], expression)


def paragraph_metrics(layout: TextLayout, metrics: dict[str, dict[str, Any]], style: dict[str, Any]) -> dict[str, Any]:
    """Measure real lines; some drawtext builds shape LF as a visible glyph."""
    exemplar = metrics.get('Mg') or next(iter(metrics.values()))
    lines = [metrics.get(line.text) for line in layout.lines]
    first, last = lines[0], lines[-1]
    values = {key: exemplar[key] for key in FIELDS}
    values['text_w'] = max((line['text_w'] if line else 0. for line in lines), default=0.)
    values['top_a'] = first['top_a'] if first else 0.
    values['bottom_d'] = last['bottom_d'] if last else 0.
    values['text_h'] = (len(lines)-1)*(values['line_h']+int(style.get('line_spacing',0)))+values['top_a']+values['bottom_d']
    values['ascent'] = max((line['ascent'] for line in lines if line), default=0.)
    values['descent'] = min((line['descent'] for line in lines if line), default=0.)
    values['max_glyph_h'] = values['ascent']-values['descent']
    values['max_glyph_w'] = max((line['max_glyph_w'] for line in lines if line), default=0.)
    return values


def paragraph_origin(base_x: str, base_y: str, values: dict[str, Any], style: dict[str, Any]) -> tuple[str,str]:
    x, y = _position(base_x, values), _position(base_y, values)
    if style.get('fix_bounds'):
        border = max(0, int(style.get('borderw', 0)))
        padding = max(0, int(style.get('boxborderw', style.get('box_padding', 12)))) if style.get('box', True) else 0
        sx, sy = int(style.get('shadowx', 0)), int(style.get('shadowy', 0))
        lo, hi = max(padding, border, -sx), max(padding, border, sx)
        top, bottom = max(padding, border, -sy), max(padding, border, sy)
        x = f'if(gt(max(({x}),{lo})+{values["text_w"]}+{hi},W),max(W-{values["text_w"]}-{hi},0),max(({x}),{lo}))'
        y = f'if(gt(max(({y}),{top})+{values["text_h"]}+{bottom},H),max(H-{values["text_h"]}-{bottom},0),max(({y}),{top}))'
    return x,y


def paragraph_alignment(style: dict[str, Any], values: dict[str, Any]) -> tuple[bool,bool,int,float]:
    align = {v.lower() for v in re.split(r'[+|, ]+', str(style.get('text_align', style.get('align', ''))))}
    left, right = bool(align & {'left', 'l'}), bool(align & {'right', 'r'})
    top, bottom = bool(align & {'top', 't'}), bool(align & {'bottom', 'b'})
    center = bool(align & {'center', 'c'}) or left and right
    middle = bool(align & {'middle', 'm'}) or top and bottom
    boxw = float(style.get('boxw') or values['text_w'])
    boxh = float(style.get('boxh') or values['text_h'])
    oy = math.trunc((boxh-values['text_h']) / (2 if middle else 1)) if middle or bottom else 0
    return center,right,oy,boxw


def paint_paragraph(root: Path, layout: TextLayout, style: dict[str, Any], parts: list[str],
                    metrics: dict[str, dict[str, Any]], values: dict[str, Any], base_x: str, base_y: str,
                    paint: Callable[[list[str]], str] | None = None, typing: Any = None) -> str:
    """Paint whole lines at a common paragraph origin/baseline, one box."""
    def text_option(text):
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        path = root/'cache'/'text-paints'/f'{digest}.txt'
        atomic_write_text(path,text)
        return 'drawtext=textfile='+_quoted(path.relative_to(root).as_posix())
    draw = paint or (lambda options: ':'.join(options))
    if typing is not None:
        return typing.paint(parts, metrics, values, base_x, base_y, paint)
    if len(layout.lines)==1:
        return draw([text_option(layout.text), *(p for p in parts[1:] if not p.startswith('expansion=')), 'expansion=none'])
    if style.get('boxw') and float(style['boxw']) < values['text_w'] or style.get('boxh') and float(style['boxh']) < values['text_h']:
        raise AppError('SUBTITLE_PARAGRAPH_BOX_CLIP_UNSUPPORTED','多行文字的显式 boxw/boxh 不能小于完整段落尺寸',exit_code=2)
    x,y=paragraph_origin(base_x,base_y,values,style)
    # geq and drawtext expose different time/frame variable names.
    x=re.sub(r'\bN\b','n',re.sub(r'\bT\b','t',x))
    y=re.sub(r'\bN\b','n',re.sub(r'\bT\b','t',y))
    common=[p for p in parts[1:] if not re.match(r'(?:x|y|box|boxcolor|boxborderw|boxw|boxh|text_align|fix_bounds|expansion)=',p)]
    center,right,oy,boxw=paragraph_alignment(style,values)
    filters=[]
    if style.get('box',True):
        background=[p for p in parts[1:] if not re.match(r'(?:x|y|fontcolor|borderw|shadowx|shadowy|fix_bounds|expansion|boxw|boxh)=',p)]
        filters.append(draw([text_option(' '),*background,'fontcolor=white@0','borderw=0','shadowx=0','shadowy=0',
                                 f'boxw={int(boxw)}',f'boxh={int(style.get("boxh") or values["text_h"])}',
                                 f'x={_quoted(x)}',f'y={_quoted(y)}','fix_bounds=0','expansion=none']))
    step=values['line_h']+int(style.get('line_spacing',0))
    for index,line in enumerate(layout.lines):
        if not line.text:continue
        width=metrics[line.text]['text_w']
        ox=math.trunc((boxw-width)/(2 if center else 1)) if center or right else 0
        offset_y=oy+index*step+values['top_a']-metrics[line.text]['top_a']
        filters.append(draw([text_option(line.text),*common,f'x={_quoted(f"({x})+{ox}")}',
                                 f'y={_quoted(f"({y})+{offset_y:.9f}")}', 'box=0','fix_bounds=0','expansion=none']))
    return ','.join(filters)


def multiline_filter(root: Path, font: Path, size: int, layout: TextLayout, style: dict[str, Any],
                     parts: list[str], base_x: str, base_y: str,
                     paint: Callable[[list[str]], str] | None = None, typing: Any = None) -> tuple[str, dict[str, Any]]:
    if re.search(r'\b(?:rand|random|st|ld|print|metadata|x|y)\b',base_x+' '+base_y):
        raise AppError('SUBTITLE_PARAGRAPH_POSITION_UNSUPPORTED','多行段落需要无状态、无 x/y 互相引用的位置表达式',exit_code=2)
    metrics,evidence=native_metrics(root,font,size,['Mg',*(line.text for line in layout.lines if line.text)],style)
    values=paragraph_metrics(layout,metrics,style)
    return paint_paragraph(root,layout,style,parts,metrics,values,base_x,base_y,paint,typing),{
        **evidence,'engine':'drawtext-lines-shared-paragraph-metrics','paragraph_metrics':values,
        'line_count':len(layout.lines),'newline_glyph_painted':False}


def highlight_filter(root: Path, font: Path, size: int, layout: TextLayout, style: dict[str, Any],
                     ranges: list[tuple[dict[str, Any], int, int]], timings: dict[int, tuple[float, float]],
                     normal: list[str], active: list[str], base_x: str, base_y: str, clock: str, clip_start: float,
                     clip_id: str, visible: str | None,
                     paint: Callable[[list[str]], str] | None = None, typing: Any = None,
                     *, float_paint: bool = False) -> tuple[str, dict[str, Any]]:
    """Choose a whole-paragraph paint with word/line rectangles in its space."""
    boundaries = {0, len(layout.source), *(x for a, b, _ in graphemes(layout.source) for x in (a, b))}
    if any(start not in boundaries or end not in boundaries for _, start, end in ranges):
        raise AppError('SUBTITLE_WORD_GRAPHEME_BOUNDARY', '逐字范围不能拆开组合字符或 emoji 字素', exit_code=2)
    for _, start, end in ranges:
        for boundary in (start, end):
            if 0 < boundary < len(layout.source):
                pair = layout.source[boundary-1:boundary+1]
                if all(character.isalnum() and unicodedata.east_asian_width(character) not in {'W', 'F'} for character in pair):
                    raise AppError('SUBTITLE_WORD_CLUSTER_LAYOUT_UNSUPPORTED', '词内部的连字/塑形簇范围尚未实现；请为完整词提供时间范围', exit_code=2)
    if any(unicodedata.bidirectional(c) in {'R', 'AL', 'AN', 'RLE', 'RLO', 'RLI', 'LRE', 'LRO', 'LRI', 'FSI', 'PDI', 'PDF'} for c in layout.source):
        raise AppError('SUBTITLE_WORD_BIDI_UNSUPPORTED', '双向文字的字素与视觉顺序映射尚未实现；请使用整句字幕', exit_code=2)
    if len(ranges) > 128 or len(layout.source) > 16384:
        raise AppError('SUBTITLE_WORD_LAYOUT_BUDGET', '逐字布局最多 128 范围 / 16384 字符', exit_code=2)
    if re.search(r'\b(?:rand|random|st|ld|print|metadata|x|y)\b', base_x + ' ' + base_y):
        raise AppError('SUBTITLE_WORD_POSITION_UNSUPPORTED', '逐字字幕位置只支持无状态表达式，不能引用 x/y 或随机/存储函数', exit_code=2)
    if style.get('expansion', 'none') != 'none' and '%' in layout.source:
        raise AppError('SUBTITLE_WORD_EXPANSION_UNSUPPORTED', '逐字字幕含百分号时需指定 expansion=none', exit_code=2)
    queries = ['Mg']
    fragments = []
    for line_index, line in enumerate(layout.lines):
        if line.text:
            queries.append(line.text)
        for entry, start, end in ranges:
            if id(entry) not in timings:
                continue
            left, right = max(start, line.start), min(end, line.end)
            if right <= left:
                continue
            # Space midpoints keep bearings/antialiasing inside the selected
            # word without moving, redrawing or cutting the adjacent glyph.
            a, b = left-line.start, right-line.start
            before = line.text[:a]
            after = line.text[:b]
            trimmed = before.rstrip()
            trailing = b
            while trailing < len(line.text) and line.text[trailing].isspace():
                trailing += 1
            through = line.text[:trailing]
            queries.extend(value for value in (before, after, trimmed, through) if value)
            fragments.append((line_index, line.text, entry, before, after, trimmed, through, a == 0, b == len(line.text)))
    metrics, evidence = native_metrics(root, font, size, queries, style)
    paragraph = paragraph_metrics(layout,metrics,style)
    normal=paint_paragraph(root,layout,style,normal,metrics,paragraph,base_x,base_y,paint,typing)
    active=paint_paragraph(root,layout,style,active,metrics,paragraph,base_x,base_y,paint,typing)
    values = {key: paragraph[key] for key in FIELDS}
    x,y=paragraph_origin(base_x,base_y,values,style)
    center,right,oy,boxw=paragraph_alignment(style,values)
    spacing = int(style.get('line_spacing', 0))
    step = paragraph['line_h']+spacing
    selections, rectangles, signals = [], [], []
    markers = {}
    for entry, _, _ in ranges:
        if id(entry) not in timings:
            continue
        marker = len(markers)
        markers[id(entry)] = marker
        begin, finish = timings[id(entry)]
        begin_value=format(clip_start+begin,'.17g') if float_paint else format(clip_start+begin,'.9f')
        end_value=format(clip_start+finish,'.17g') if float_paint else format(clip_start+finish,'.9f')
        timing = f'gte(({clock}),{begin_value})*lt(({clock}),{end_value})'
        if visible:
            timing += f'*({visible})'
        signals.append(f'drawbox=x={_quoted(f"mod({marker},iw)")}:y={_quoted(f"trunc({marker}/iw)")}:w=1:h=1:color=white:t=fill:replace=1:enable={_quoted(timing)}')
    def advance(text):
        return metrics[text]['lines64'][0] / 64 if text else 0.
    def row_boundary(index):
        previous=metrics.get(layout.lines[index-1].text,{})
        following=metrics.get(layout.lines[index].text,{})
        # Separate the actual glyph extents, not the baselines. Cap height
        # can exceed half a line advance, so a baseline midpoint can recolor
        # the top row of the following word even with positive line spacing.
        return (oy+paragraph['top_a']+(index-1)*step
                +(previous.get('bottom_d',0.)+step-following.get('top_a',0.))/2)
    for line_index, line, entry, before, after, trimmed, through, first, last in fragments:
        line_width = math.ceil(metrics[line]['lines64'][0]/64)
        ox = math.trunc((boxw-line_width) / (2 if center else 1)) if center or right else 0
        left = (advance(before)+advance(trimmed))/2
        end = (advance(after)+advance(through))/2
        # The outer rows/edges may include strokes extending beyond advance.
        # Both variants have identical box/border/shadow pixels there.
        horizontal = []
        if not first:
            horizontal.append(f'gte(X,({x})+{ox+left:.9f})')
        if not last:
            horizontal.append(f'lt(X,({x})+{ox+end:.9f})')
        vertical = []
        if line_index:
            row_top = row_boundary(line_index)
            vertical.append(f'gte(Y,({y})+{row_top:.9f})')
        if line_index < len(layout.lines)-1:
            row_bottom = row_boundary(line_index+1)
            vertical.append(f'lt(Y,({y})+{row_bottom:.9f})')
        start, stop = timings[id(entry)]
        marker = markers[id(entry)]
        spatial = '*'.join([*horizontal, *vertical]) or '1'
        # The enable expression is evaluated once per frame by drawbox. Read
        # its 1-pixel flag here, instead of evaluating an entire nested Bezier
        # inverse separately for every pixel/channel of the mask.
        expression = f'if(gt(r(mod({marker},W),trunc({marker}/W)),128),{spatial},0)'
        selections.append(expression)
        rectangles.append({'source_start': next(a for item, a, _ in ranges if item is entry),
                           'line': line_index, 'advance_left': left, 'advance_right': end,
                           'start_seconds': start, 'end_seconds': stop})
    mask = '255*gt(' + '+'.join(f'({value})' for value in selections) + ',0)' if selections else '0'
    mask = re.sub(r'\bt\b', 'T', mask)
    if float_paint and callable(getattr(paint, 'select_coverage', None)):
        value = paint.select_coverage(normal, active, signals, mask)
        return value, {**evidence, 'engine': 'drawtext-whole-paragraph-masked-highlight',
                       'paragraph_metrics': values, 'word_rectangles': rectangles,
                       'line_count':len(layout.lines),'newline_glyph_painted':False,
                       'color_selection': 'binary-whole-paragraph-paints',
                       'timing_evaluation': 'compiled-constant-native-enable-per-word', 'paint_count': 2}
    token = hashlib.sha256((clip_id+normal+active).encode('utf-8')).hexdigest()[:16]
    a, b, c, painted, colored, selected = [f'word_{token}_{v}' for v in ('a','b','c','normal','active','mask')]
    pixel_format = 'gbrapf32le' if float_paint else 'gbrap'
    value = (f'split=3[{a}][{b}][{c}];[{a}]'+normal+f',format={pixel_format}[{painted}];'
             +f'[{b}]'+active+f',format={pixel_format}[{colored}];'
             +f'[{c}]format=gbrap,lutrgb=r=0:g=0:b=0:a=0,'+','.join(signals)
             +f',geq=r={_quoted(mask)}:g={_quoted(mask)}:b={_quoted(mask)}:a={_quoted(mask)}'
             +(f',format=gbrap,format={pixel_format}' if float_paint else '')+f'[{selected}];')
    if float_paint:
        from .float_text_paint import select_graph
        value += select_graph(painted, colored, selected)
    else:
        value += f'[{painted}][{colored}][{selected}]maskedmerge=planes=15,format=rgba'
    return value, {**evidence, 'engine': 'drawtext-whole-paragraph-masked-highlight',
                   'paragraph_metrics': values, 'word_rectangles': rectangles,
                   'line_count':len(layout.lines),'newline_glyph_painted':False,
                   'color_selection': 'binary-whole-paragraph-paints', 'timing_evaluation': 'one-native-enable-per-word-per-frame', 'paint_count': 2}
