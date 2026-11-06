"""Unicode 17 segmentation, lossless wrap ranges and integer reveal clocks.

Offsets are Python scalar/code-point indices, never bytes or UTF-16 units.
This module does not reorder glyphs, shape fonts or render RTL selections.
The caller supplies whole-string shaping advances to wrap_text. No average
character width fallback, locale dictionary, hyphen insertion or font fallback
is silently substituted. Original source, separators and spaces stay intact.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math

from ._vendor.db import get_value
from ._vendor.graphemecluster import grapheme_cluster_boundaries
from ._vendor.linebreak import line_break_boundaries

UNICODE_VERSION = '17.0.0'
MAX_CODEPOINTS = 16384
MAX_GRAPHEMES = 4096
MAX_LINES = 512
MAX_MEASUREMENTS = 32768
_HARD = frozenset(('BK', 'CR', 'LF', 'NL'))


class TextError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _text(text: str) -> None:
    if not isinstance(text, str):
        raise TextError('TEXT_TYPE', 'Text must be a string')
    if len(text) > MAX_CODEPOINTS:
        raise TextError('TEXT_BUDGET', 'Text exceeds the explicit 16384-code-point budget')
    if any(0xD800 <= ord(char) <= 0xDFFF for char in text):
        raise TextError('TEXT_SURROGATE', 'Text contains a lone surrogate rather than Unicode scalar values')


def _integer(name: str, value: int, minimum: int, maximum: int = 2**53 - 1) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise TextError('TEXT_INTEGER', f'{name} must be an integer in [{minimum}, {maximum}]')


def _finite(value) -> bool:
    try:
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Break:
    offset: int
    kind: str  # soft, mandatory, end


@dataclass(frozen=True)
class Line:
    start: int
    end: int
    content_start: int
    content_end: int
    text: str
    width: float
    overflow: bool
    break_kind: str


@dataclass(frozen=True)
class Layout:
    source: str
    lines: tuple[Line, ...]
    max_width: float
    measurement_count: int
    unicode_version: str = UNICODE_VERSION
    profile: str = 'uax14-egc17-v1'


@dataclass(frozen=True)
class Reveal:
    frame: int
    end: int
    grapheme_count: int


def graphemes(text: str) -> tuple[Span, ...]:
    """Default extended grapheme clusters (UAX29 revision 47)."""
    _text(text)
    positions = list(grapheme_cluster_boundaries(text))
    if max(0, len(positions) - 1) > MAX_GRAPHEMES:
        raise TextError('TEXT_GRAPHEME_BUDGET', 'Text exceeds the explicit 4096-grapheme budget')
    return tuple(Span(start, end, text[start:end]) for start, end in zip(positions, positions[1:]))


def line_breaks(text: str, *, preserve_graphemes: bool = True) -> tuple[Break, ...]:
    """UAX14 rev55 opportunities, optionally tailored to preserve UAX29 EGCs.

    False returns the default UAX14 boundaries. True intersects with EGC
    boundaries. Mandatory breaks and the end are identified separately.
    """
    _text(text)
    if not isinstance(preserve_graphemes, bool):
        raise TextError('TEXT_OPTION', 'preserve_graphemes must be a boolean')
    positions = tuple(line_break_boundaries(text)) if text else (0,)
    allowed = {span.end for span in graphemes(text)} | {0} if preserve_graphemes else None
    result = []
    for offset in positions:
        if allowed is not None and offset not in allowed:
            continue
        before = get_value('Line_Break', ord(text[offset - 1])) if offset else ''
        kind = 'mandatory' if before in _HARD else 'end' if offset == len(text) else 'soft'
        result.append(Break(offset, kind))
    return tuple(result)


def _paragraphs(text: str):
    """Yield content and separator ends; CRLF is one authored separator."""
    start = cursor = 0
    while cursor < len(text):
        value = get_value('Line_Break', ord(text[cursor]))
        if value in _HARD:
            end = cursor + 1
            if value == 'CR' and end < len(text) and text[end] == '\n':
                end += 1
            yield start, cursor, end, 'mandatory'
            start = cursor = end
        else:
            cursor += 1
    # A final hard separator leaves a real empty final line.
    yield start, len(text), len(text), 'end'


def wrap_text(text: str, max_width: float, measure: Callable[[str], float], *,
              overflow: str = 'preserve', trim_line_end: bool = True) -> Layout:
    """Wrap using legal Unicode boundaries and authoritative shaped advances.

    Each Line.start:end is a contiguous, lossless source range including any
    separator. content_start:content_end is the visible source slice. Only ASCII
    SP/TAB can be omitted at line ends, never NBSP, NNBSP or a word joiner.
    Unsplittable overwide units are preserved and marked, or rejected explicitly.
    Shaping advances need not be monotonic: every legal candidate is considered.
    """
    _text(text)
    if not _finite(max_width) or max_width <= 0:
        raise TextError('TEXT_WIDTH', 'max_width must be a finite positive number')
    if not callable(measure):
        raise TextError('TEXT_MEASURE', 'A whole-string shaping measure is required')
    if overflow not in ('preserve', 'reject') or not isinstance(trim_line_end, bool):
        raise TextError('TEXT_OPTION', 'Unknown overflow or trimming policy')
    spans = graphemes(text)
    edges = {span.end for span in spans} | {0}
    legal = {item.offset for item in line_breaks(text, preserve_graphemes=False)} & edges
    measured: dict[tuple[int, int], float] = {}

    def extent(start: int, end: int) -> tuple[int, float]:
        if trim_line_end:
            while end > start and text[end - 1] in ' \t':
                end -= 1
        if start == end:
            return end, 0.0
        key = (start, end)
        if key not in measured:
            if len(measured) >= MAX_MEASUREMENTS:
                raise TextError('TEXT_MEASURE_BUDGET', 'Shaping measurement budget exceeded')
            try:
                raw = measure(text[start:end])
            except Exception as exc:
                raise TextError('TEXT_MEASURE', 'Whole-string shaping measurement failed') from exc
            if not _finite(raw) or raw < 0:
                raise TextError('TEXT_MEASURE', 'Shaping advance must be finite and nonnegative')
            measured[key] = float(raw)
        return end, measured[key]

    lines = []
    for paragraph_start, content_end, separator_end, terminal_kind in _paragraphs(text):
        cursor = paragraph_start
        while True:
            if len(lines) >= MAX_LINES:
                raise TextError('TEXT_LINE_BUDGET', 'Text exceeds the explicit 512-line budget')
            candidates = sorted(end for end in legal if cursor < end <= content_end)
            if content_end not in candidates:
                candidates.append(content_end)
            choices = [(end, *extent(cursor, end)) for end in candidates]
            fitting = [choice for choice in choices if choice[2] <= max_width]
            end, visible_end, width = fitting[-1] if fitting else choices[0]
            overwide = width > max_width
            if overwide and overflow == 'reject':
                raise TextError('TEXT_OVERFLOW', 'An unsplittable Unicode unit exceeds max_width')
            last = end == content_end
            lines.append(Line(cursor, separator_end if last else end, cursor, visible_end,
                              text[cursor:visible_end], width, overwide, terminal_kind if last else 'soft'))
            if last:
                break
            cursor = end
    return Layout(text, tuple(lines), float(max_width), len(measured))


def scalar_to_utf16(text: str, offset: int) -> int:
    _text(text)
    _integer('offset', offset, 0, len(text))
    return sum(2 if ord(char) > 0xFFFF else 1 for char in text[:offset])


def utf16_to_scalar(text: str, offset: int) -> int:
    _text(text)
    _integer('offset', offset, 0, len(text) * 2)
    units = 0
    for index, char in enumerate(text):
        if units == offset:
            return index
        units += 2 if ord(char) > 0xFFFF else 1
        if units > offset:
            raise TextError('TEXT_UTF16_BOUNDARY', 'UTF-16 offset splits a surrogate pair')
    if units == offset:
        return len(text)
    raise TextError('TEXT_UTF16_BOUNDARY', 'UTF-16 offset exceeds the source')


def paragraph_direction(text: str, *, default: str = 'ltr') -> str:
    """UAX9 P2/P3 base direction only, respecting nested isolate contents.

    This is not a UAX9 reorderer or a glyph-cluster selection implementation.
    The first paragraph only is considered. Explicit embedding/override
    characters do not themselves set the P2/P3 paragraph direction.
    """
    _text(text)
    if default not in ('ltr', 'rtl'):
        raise TextError('TEXT_DIRECTION', 'default direction must be ltr or rtl')
    isolates = 0
    for char in text:
        bidi = get_value('Bidi_Class', ord(char))
        if bidi == 'B':
            break
        if bidi in ('LRI', 'RLI', 'FSI'):
            isolates += 1
        elif bidi == 'PDI':
            isolates = max(0, isolates - 1)
        elif isolates == 0 and bidi in ('L', 'R', 'AL'):
            return 'ltr' if bidi == 'L' else 'rtl'
    return default


def reveal_plan(text: str, *, start_tick: int, duration_ticks: int,
                clock_hz: int, fps_num: int, fps_den: int = 1) -> tuple[Reveal, ...]:
    """Logical EGC reveal events at exact authored rational times, rounded up.

    First reveal is at start+duration/N, final reveal at start+duration.
    Events sharing a frame collapse to the longest complete source prefix.
    Logical segmentation is independent of direction; glyph shaping is external.
    """
    for name, value, minimum in [('start_tick', start_tick, 0), ('duration_ticks', duration_ticks, 1),
                                 ('clock_hz', clock_hz, 1), ('fps_num', fps_num, 1), ('fps_den', fps_den, 1)]:
        _integer(name, value, minimum)
    spans = graphemes(text)
    count = len(spans)
    events = []
    for index, span in enumerate(spans, 1):
        numerator = (start_tick * count + duration_ticks * index) * fps_num
        denominator = clock_hz * count * fps_den
        frame = (numerator + denominator - 1) // denominator
        event = Reveal(frame, span.end, index)
        if events and events[-1].frame == frame:
            events[-1] = event
        else:
            events.append(event)
    return tuple(events)
