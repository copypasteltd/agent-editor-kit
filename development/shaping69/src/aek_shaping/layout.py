"""Visual OpenType glyph plans with source ranges and actual selection geometry."""
from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass, replace
import hashlib
import math

from aek_unicode17 import graphemes, line_breaks
from aek_unicode17._vendor.db import get_value
from .native import require, integer, ShapingError

MAX_SHAPES = 4096
MAX_LINES = 128
MAX_PIXELS = 3840 * 2160


def _invisible(char):
    value = ord(char)
    return (get_value('General_Category', value) == 'Cf' or get_value('Line_Break', value) in ('BK', 'CR', 'LF', 'NL')
            or 0xFE00 <= value <= 0xFE0F or 0xE0100 <= value <= 0xE01EF)


@dataclass
class Line:
    start: int
    end: int
    content_end: int
    paragraph_start: int
    context: str
    base: int
    width: int
    glyphs: list[dict]
    runs: list[dict]
    ascender: int
    descender: int
    height: int


@dataclass
class Plan:
    source: str
    lines: list[Line]
    fonts: list
    engine: object
    language: str
    features: dict
    max_width: int
    shape_calls: int
    source_sha256: str = ''
    revealed_end: int | None = None

    def data(self):
        return dict(format='aek-shaped-text-plan-v1', source=self.source,
            source_sha256=hashlib.sha256(self.source.encode('utf-8')).hexdigest(),
            offset_unit='unicode-scalar', geometry_unit='signed-26.6-pixels',
            engine_versions=self.engine.versions, native_binary_sha256=self.engine.manifest['binary_sha256'],
            fonts=[dict(sha256=font.spec.sha256, pixels=font.spec.pixels, index=font.spec.index,
                        variations=dict(font.native_variations)) for font in self.fonts],
            language=self.language, features=self.features, shape_calls=self.shape_calls,
            max_width=self.max_width, revealed_end=self.revealed_end,
            lines=[dict(start=line.start, end=line.end, content_end=line.content_end, base=line.base,
                        paragraph_start=line.paragraph_start,
                        width=line.width, ascender=line.ascender, descender=line.descender,
                        height=line.height, glyphs=line.glyphs, runs=line.runs) for line in self.lines],
            formal_product_integrated=False)


def shape_line(engine, text, fonts, *, start=0, end=None, base='auto-ltr', language='und', features=None):
    """Shape one line using full logical paragraph context and visual bidi runs."""
    units = graphemes(text)
    end = len(text) if end is None else end
    edges = {0, len(text)} | {unit.start for unit in units} | {unit.end for unit in units}
    require(integer(start, 0, len(text)) and integer(end, start, len(text)) and start in edges and end in edges,
            'TEXT_CLUSTER_RANGE', 'Line range must preserve complete extended grapheme clusters')
    require(1 <= len(fonts) <= 8 and all(font.engine is engine for font in fonts),
            'TEXT_FONT_STACK', 'Use one to eight explicitly loaded fonts from this native engine')
    require(features is None or isinstance(features, dict), 'TEXT_FEATURE', 'OpenType features must be an object')
    features = features or {}
    metrics = dict(ascender=max(font.metrics['ascender'] for font in fonts),
                   descender=min(font.metrics['descender'] for font in fonts),
                   height=max(font.metrics['height'] for font in fonts))
    if start == end:
        return dict(width=0, glyphs=[], runs=[], base=1 if base in ('rtl', 'auto-rtl') else 0, **metrics)
    bidi = engine.bidi(text, base=base, start=start, end=end)
    scripts = engine.scripts(text)
    assignments = []
    for unit in units:
        visible = [char for char in unit.text if not _invisible(char)]
        font_index = next((index for index, font in enumerate(fonts) if all(font.nominal(char) for char in visible)), None)
        require(font_index is not None, 'TEXT_MISSING_GLYPH',
                'No explicitly selected font covers a complete source grapheme at offset ' + str(unit.start))
        if assignments and assignments[-1]['font'] == font_index:
            assignments[-1]['end'] = unit.end
        else:
            assignments.append(dict(start=unit.start, end=unit.end, font=font_index))
    glyphs, visual_runs, cursor = [], [], 0
    for bidi_run in bidi['runs']:
        pieces = []
        for script in scripts:
            for assignment in assignments:
                first = max(start, bidi_run['start'], script['start'], assignment['start'])
                last = min(end, bidi_run['end'], script['end'], assignment['end'])
                if first < last:
                    require(first in edges and last in edges, 'TEXT_CLUSTER_ITEMIZATION',
                            'The script/bidi/font boundary divides a grapheme; this combination needs a dedicated itemizer')
                    pieces.append(dict(start=first, end=last, script=script['tag'],
                                       level=bidi_run['level'], font=assignment['font']))
        pieces.sort(key=lambda piece: piece['start'], reverse=bool(bidi_run['level'] & 1))
        for piece in pieces:
            font = fonts[piece['font']]
            shaped = font.shape(text, piece['start'], piece['end'], piece['level'], piece['script'], language, features)
            require(all(glyph['id'] != 0 for glyph in shaped), 'TEXT_MISSING_SHAPED_GLYPH', 'Shaping returned a .notdef glyph')
            boundaries = sorted({glyph['cluster'] for glyph in shaped} | {piece['end']})
            cluster_ends = {value: boundaries[index + 1] for index, value in enumerate(boundaries[:-1])}
            require(all(piece['start'] <= glyph['cluster'] < piece['end'] for glyph in shaped),
                    'TEXT_NATIVE_CLUSTER', 'Native cluster escaped its authored item range')
            pen_x = pen_y = 0
            native_positions = []
            pens = [0]
            for glyph in shaped:
                native_positions.append((glyph, pen_x, pen_y))
                pen_x += glyph['x_advance']
                pen_y += glyph['y_advance']
                pens.append(pen_x)
            origin, advance = -min(pens), max(pens) - min(pens)
            require(advance <= 65536 * 64 and cursor + advance <= 65536 * 64,
                    'TEXT_GEOMETRY_BUDGET', 'Text geometry exceeds the 65536-pixel line budget')
            run_index = len(visual_runs)
            visual_runs.append(dict(**piece, origin=cursor, width=advance,
                script_tag=piece['script'].to_bytes(4, 'big').decode('ascii'), glyph_count=len(shaped)))
            for glyph, px, py in native_positions:
                glyphs.append(dict(**glyph, font=piece['font'], run=run_index, level=piece['level'],
                    source_start=glyph['cluster'], source_end=cluster_ends[glyph['cluster']],
                    x=cursor + origin + px + glyph['x_offset'], y=py + glyph['y_offset'],
                    advance_start=cursor + origin + px, advance_end=cursor + origin + px + glyph['x_advance']))
            cursor += advance
    return dict(width=cursor, glyphs=glyphs, runs=visual_runs, base=bidi['base'], **metrics)


def _paragraphs(text):
    start = index = 0
    while index < len(text):
        if get_value('Bidi_Class', ord(text[index])) == 'B':
            end = index + 1 + int(text[index] == '\r' and index + 1 < len(text) and text[index + 1] == '\n')
            yield start, index, end
            start = index = end
        else:
            index += 1
    yield start, len(text), len(text)


def layout(engine, text, fonts, *, max_width=1024, base='auto-ltr', language='und', features=None,
           overflow='reject', trim_line_end=True):
    """Wrap with measured visual glyph runs, then retain every original source range."""
    graphemes(text)
    require('\t' not in text and all(ord(char) >= 32 or char in '\r\n\v\f' for char in text),
            'TEXT_CONTROL_POLICY', 'Tab stops and non-layout C0 controls require an explicit future layout profile')
    require(integer(max_width, 1, 65536) and overflow in ('preserve', 'reject') and isinstance(trim_line_end, bool),
            'TEXT_LAYOUT_OPTION', 'Invalid width, overflow or line-end policy')
    lines, calls = [], 0
    require(features is None or isinstance(features, dict), 'TEXT_FEATURE', 'OpenType features must be an object')
    features = dict(features or {})
    for paragraph_start, content_end, separator_end in _paragraphs(text):
        paragraph = text[paragraph_start:content_end]
        paragraph_base = engine.bidi(paragraph, base=base)['base']
        forced_base = 'rtl' if paragraph_base else 'ltr'
        breaks = line_breaks(paragraph)
        legal = sorted({item.offset for item in breaks} | {len(paragraph)})
        mandatory = [item.offset for item in breaks if item.kind == 'mandatory']
        cursor, cache = 0, {}
        while True:
            require(len(lines) < MAX_LINES, 'TEXT_LINE_BUDGET', 'At most 128 shaped lines are supported')
            stop = next((value for value in mandatory if value > cursor), len(paragraph))
            candidates = [value for value in legal if cursor < value <= stop] or [len(paragraph)]
            choices = []
            for end in candidates:
                visible_end = end
                while visible_end > cursor and get_value('Line_Break', ord(paragraph[visible_end - 1])) in ('BK', 'CR', 'LF', 'NL'):
                    visible_end -= 1
                if trim_line_end:
                    while visible_end > cursor and paragraph[visible_end - 1] in ' \t':
                        visible_end -= 1
                key = (cursor, visible_end)
                if key not in cache:
                    require(calls < MAX_SHAPES, 'TEXT_SHAPING_BUDGET', 'Whole-line shaping budget exceeded')
                    cache[key] = shape_line(engine, paragraph, fonts, start=cursor, end=visible_end,
                        base=forced_base, language=language, features=features)
                    calls += 1
                choices.append((end, visible_end, cache[key]))
            fitting = [choice for choice in choices if choice[2]['width'] <= max_width * 64]
            end, visible_end, shaped = fitting[-1] if fitting else choices[0]
            require(fitting or overflow == 'preserve', 'TEXT_LINE_OVERFLOW', 'An unsplittable shaped source unit exceeds the requested width')
            glyphs = [dict(glyph, source_start=glyph['source_start'] + paragraph_start,
                           source_end=glyph['source_end'] + paragraph_start) for glyph in shaped['glyphs']]
            final = end == len(paragraph)
            lines.append(Line(paragraph_start + cursor, separator_end if final else paragraph_start + end,
                paragraph_start + visible_end, paragraph_start, paragraph, shaped['base'], shaped['width'],
                glyphs, shaped['runs'], shaped['ascender'], shaped['descender'], shaped['height']))
            if final:
                break
            cursor = end
    return Plan(text, lines, fonts, engine, language, features, max_width, calls)


def selection(plan, ranges, *, partial='strict'):
    """Map logical ranges to actual glyphs and GDEF caret geometry.

    Strict mode rejects a partial ligature without a complete authoritative
    GDEF caret map. Explicit cluster mode expands that request to the full
    indivisible shaped cluster and reports the expansion. No prefix-width
    estimate, equal subdivision or silent font/selection substitution is used.
    """
    require(partial in ('strict', 'cluster') and isinstance(ranges, (list, tuple)) and len(ranges) <= 512,
            'TEXT_SELECTION', 'Invalid selection policy or range budget')
    edges = {0, len(plan.source)} | {span.end for span in graphemes(plan.source)}
    requested = []
    for pair in ranges:
        require(isinstance(pair, (list, tuple)) and len(pair) == 2 and
                integer(pair[0], 0, len(plan.source)) and integer(pair[1], pair[0], len(plan.source)) and
                pair[0] in edges and pair[1] in edges, 'TEXT_SELECTION_BOUNDARY',
                'Selections must use complete source grapheme boundaries')
        if pair[0] < pair[1]:
            requested.append(tuple(pair))
    windows, details = {}, []
    for line_index, line in enumerate(plan.lines):
        groups = {}
        for index, glyph in enumerate(line.glyphs):
            groups.setdefault((glyph['run'], glyph['source_start'], glyph['source_end']), []).append(index)
        for (_, start, end), indexes in groups.items():
            spans = [(max(start, first), min(end, last)) for first, last in requested if first < end and last > start]
            if not spans:
                continue
            merged_spans = []
            for first, last in sorted(spans):
                if merged_spans and first <= merged_spans[-1][1]:
                    merged_spans[-1] = (merged_spans[-1][0], max(last, merged_spans[-1][1]))
                else:
                    merged_spans.append((first, last))
            spans = merged_spans
            glyphs = [line.glyphs[index] for index in indexes]
            low = min(min(glyph['advance_start'], glyph['advance_end']) for glyph in glyphs)
            high = max(max(glyph['advance_start'], glyph['advance_end']) for glyph in glyphs)
            complete = any(first == start and last == end for first, last in spans)
            expanded = False
            intervals = [(None, None)]
            caret_source = 'complete-cluster'
            if not complete:
                local_edges = [start] + [span.end + start for span in graphemes(plan.source[start:end])]
                caret_values = plan.fonts[glyphs[0]['font']].carets(glyphs[0]['id'], glyphs[0]['level']) if len(glyphs) == 1 else []
                caret_values = sorted(glyphs[0]['x'] + value for value in caret_values)
                good = len(caret_values) == len(local_edges) - 2 and all(low < value < high for value in caret_values) and len(set(caret_values)) == len(caret_values)
                if not good:
                    require(partial == 'cluster', 'TEXT_PARTIAL_LIGATURE_CARETS',
                            'This partial shaped cluster has no complete GDEF caret map; choose a complete cluster explicitly')
                    expanded, caret_source = True, 'explicit-cluster-expansion'
                else:
                    coordinates = [low] + caret_values + [high]
                    if glyphs[0]['level'] & 1:
                        coordinates.reverse()
                    intervals = []
                    for first, last in spans:
                        a, b = sorted((coordinates[local_edges.index(first)], coordinates[local_edges.index(last)]))
                        intervals.append((None if a == low else a, None if b == high else b))
                    caret_source = 'font-GDEF-through-HarfBuzz'
            for index in indexes:
                windows[(line_index, index)] = intervals
            details.append(dict(line=line_index, source_start=start, source_end=end, requested=spans,
                                expanded=expanded, caret_source=caret_source, intervals=intervals,
                                advance_left=low, advance_right=high, glyph_indexes=indexes))
    return dict(requested=requested, partial_policy=partial, glyph_windows=windows, clusters=details)


def prefix_plan(plan, end):
    """Reshape only revealed logical text, retaining the final line layout/base.

    Hidden suffixes never participate in joining. Line breaks and paragraph
    bases come from the full author plan, so neutral prefixes and RTL starts
    retain an explicit stable anchor. The final source remains lossless.
    """
    edges = {0, len(plan.source)} | {span.end for span in graphemes(plan.source)}
    require(integer(end, 0, len(plan.source)) and end in edges,
            'TEXT_REVEAL_BOUNDARY', 'A reveal must end at a complete source grapheme')
    lines, calls = [], 0
    for line in plan.lines:
        cut = max(line.start, min(end, line.content_end))
        if end <= line.start:
            lines.append(replace(line, width=0, glyphs=[], runs=[], content_end=line.start))
            continue
        context_end = min(len(line.context), max(0, end - line.paragraph_start))
        context = line.context[:context_end]
        result = shape_line(plan.engine, context, plan.fonts,
            start=line.start - line.paragraph_start, end=cut - line.paragraph_start,
            base='rtl' if line.base else 'ltr', language=plan.language, features=plan.features)
        glyphs = [dict(glyph, source_start=glyph['source_start'] + line.paragraph_start,
                       source_end=glyph['source_end'] + line.paragraph_start) for glyph in result['glyphs']]
        lines.append(replace(line, width=result['width'], glyphs=glyphs, runs=result['runs'],
                             context=context, content_end=cut))
        calls += 1
    return replace(plan, lines=lines, shape_calls=calls, revealed_end=end)


class Renderer:
    def __init__(self, plan, *, padding=32, align='start', line_spacing=8):
        require(integer(padding, 0, 512) and integer(line_spacing, 0, 512) and align in ('start', 'left', 'center', 'right'),
                'TEXT_RENDER_OPTION', 'Invalid explicit text rendering options')
        self.plan, self.padding, self.align, self.spacing = plan, padding, align, line_spacing
        self.cache, self.cache_bytes = OrderedDict(), 0
        self.cache_budget = 32 * 1024**2
        self.box_width = max((line.width for line in plan.lines), default=0)
        self.origins = []
        y = padding
        for line in plan.lines:
            right = align == 'right' or align == 'start' and line.base == 1
            offset = (self.box_width - line.width) // (2 if align == 'center' else 1) if right or align == 'center' else 0
            self.origins.append((padding * 64 + offset, y * 64 + line.ascender))
            y += math.ceil(max(line.height, line.ascender - line.descender) / 64) + line_spacing
        self.width = max(1, math.ceil(self.box_width / 64) + padding * 2)
        self.height = max(1, y - line_spacing + padding)
        require(self.width <= 4096 and self.height <= 4096 and self.width * self.height <= MAX_PIXELS,
                'TEXT_CANVAS_BUDGET', 'Text canvas exceeds the explicit 4K pixel budget')

    def _bitmap(self, glyph, phase_x, phase_y):
        key = (glyph['font'], glyph['id'], phase_x, phase_y)
        if key in self.cache:
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        value = self.plan.fonts[glyph['font']].bitmap(glyph['id'], phase_x, phase_y)
        size = len(value[1])
        while self.cache and self.cache_bytes + size > self.cache_budget:
            _, removed = self.cache.popitem(last=False)
            self.cache_bytes -= len(removed[1])
        if size <= self.cache_budget:
            self.cache[key], self.cache_bytes = value, self.cache_bytes + size
        return value

    def render(self, selected=None, *, foreground=(239, 239, 239), active=(35, 214, 207), display_plan=None):
        for color in (foreground, active):
            require(isinstance(color, (tuple, list)) and len(color) == 3 and all(integer(v, 0, 255) for v in color),
                    'TEXT_COLOR', 'Text colors must contain three 8-bit RGB channels')
        display_plan = self.plan if display_plan is None else display_plan
        require(display_plan.source == self.plan.source and display_plan.fonts == self.plan.fonts and
                len(display_plan.lines) == len(self.plan.lines), 'TEXT_RENDER_PLAN', 'Reveal plans must retain the frozen full layout')
        selected = selection(display_plan, []) if selected is None else selected
        coverage = bytearray(self.width * self.height)
        contribution = bytearray(len(coverage))
        origins = []
        for line_index, line in enumerate(display_plan.lines):
            origin_x, baseline = self.origins[line_index]
            difference = self.plan.lines[line_index].width - line.width
            if self.align == 'right' or self.align == 'start' and line.base == 1:
                origin_x += difference
            elif self.align == 'center':
                origin_x += difference // 2
            origins.append((origin_x, baseline))
            for glyph_index, glyph in enumerate(line.glyphs):
                x, phase_x = divmod(origin_x + glyph['x'], 64)
                y, phase_y = divmod(baseline - glyph['y'], 64)
                (width, height, left, top), bitmap = self._bitmap(glyph, phase_x, phase_y)
                if not bitmap:
                    continue
                left, top = x + left, y - top
                require(0 <= left and 0 <= top and left + width <= self.width and top + height <= self.height,
                        'TEXT_INK_OVERFLOW', 'Actual glyph ink leaves the declared canvas; increase explicit padding')
                windows = selected['glyph_windows'].get((line_index, glyph_index), [])
                for row in range(height):
                    for column in range(width):
                        alpha = bitmap[row * width + column]
                        if not alpha:
                            continue
                        pixel = (top + row) * self.width + left + column
                        amount = 0
                        if windows:
                            begin, end = (left + column) * 64 - origin_x, (left + column + 1) * 64 - origin_x
                            pieces = sorted((max(begin, a) if a is not None else begin,
                                             min(end, b) if b is not None else end) for a, b in windows)
                            merged = []
                            for a, b in pieces:
                                if a < b:
                                    if merged and a <= merged[-1][1]: merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
                                    else: merged.append((a, b))
                            fraction = sum(b - a for a, b in merged)
                            amount = (alpha * fraction + 32) // 64
                        coverage[pixel] = alpha + (coverage[pixel] * (255 - alpha) + 127) // 255
                        contribution[pixel] = amount + (contribution[pixel] * (255 - alpha) + 127) // 255
        rgba = bytearray(len(coverage) * 4)
        for pixel, alpha in enumerate(coverage):
            if not alpha:
                continue
            selected_alpha = contribution[pixel]
            require(selected_alpha <= alpha, 'TEXT_COVERAGE_INVARIANT', 'Selected coverage escaped total glyph coverage')
            for channel in range(3):
                rgba[pixel * 4 + channel] = (foreground[channel] * (alpha - selected_alpha) + active[channel] * selected_alpha + alpha // 2) // alpha
            rgba[pixel * 4 + 3] = alpha
        return bytes(rgba), dict(width=self.width, height=self.height,
            coverage_sha256=hashlib.sha256(coverage).hexdigest(),
            selected_coverage_sha256=hashlib.sha256(contribution).hexdigest(),
            selected_pixels=sum(value > 0 for value in contribution),
            alpha=bytes(coverage), selected_alpha=bytes(contribution),
            clusters=selected['clusters'], cache_bytes=self.cache_bytes, origins_26_6=origins)
