"""Native prefix shaping on a stable paragraph, scheduled on the CFR grid."""
from __future__ import annotations

import bisect
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Callable
import unicodedata

from .errors import AppError
from .media import ffmpeg_path
from .text_highlight import file_fingerprint, paragraph_alignment, paragraph_origin, _quoted
from .text_layout import TextLayout, graphemes
from .time_mapping import compose_time
from .utils import atomic_write_text, run_process, sha256_file


@lru_cache(maxsize=8)
def _runtime_text_supported(executable: str, fingerprint: str) -> bool:
    result = run_process([executable, '-hide_banner', '-h', 'filter=drawtext'], timeout=30)
    return result.returncode == 0 and bool(re.search(
        r'^\s+text\s+<string>\s+\S*T\S*\s', result.stdout + result.stderr, re.M))


def _command_token(text: str) -> str:
    # sendcmd tokenization has one quoting layer. A quote must leave its
    # quoted section, be escaped outside, then reopen it. Backslashes and
    # delimiters inside the quoted sections remain literal text.
    return "'" + text.replace("'", "'\\''") + "'"


class TypingParagraph:
    """One command stream updates all named native glyph coverage paints.

    Prefixes are shaped as whole native runs. Frame decisions use the same
    compiled ancestral maps as the text clock; commands are placed between
    adjacent CFR samples to avoid timestamp-quantization races at boundaries.
    """
    def __init__(self, root: Path, layout: TextLayout, style: dict[str, Any], font: Path,
                 size: int, clock: dict[str, Any], fps: str, origin: float,
                 start: float, duration: float, delay: float, clip_id: str,
                 authored_expression: str, *, snapshot: bool = False):
        self.root, self.layout, self.style = root, layout, style
        self.clock, self.fps, self.origin = clock, float(Fraction(fps)), float(origin)
        self.snapshot = snapshot
        self.units = [unit for unit in graphemes(layout.source) if unit[2] != '\n']
        if len(self.units) > 512 or len(layout.source) > 16384 or len(layout.lines) > 128:
            raise AppError('SUBTITLE_TYPEWRITER_BUDGET', '打字机最多 512 字素、16384 源字符和 128 行', exit_code=2)
        if any(ord(c) < 32 and c not in '\n\t' or ord(c) == 127 for c in layout.source):
            raise AppError('SUBTITLE_TYPEWRITER_CONTROL_UNSUPPORTED', '打字机不接受换行和制表之外的控制字符', exit_code=2)
        if any(unicodedata.bidirectional(c) in {'R', 'AL', 'AN', 'RLE', 'RLO', 'RLI', 'LRE', 'LRO', 'LRI', 'FSI', 'PDI', 'PDF'} for c in layout.source):
            raise AppError('SUBTITLE_TYPEWRITER_BIDI_UNSUPPORTED', '双向文字的打字机视觉锚点尚未实现', exit_code=2)
        if style.get('expansion', 'none') != 'none' and '%' in layout.source:
            raise AppError('SUBTITLE_TYPEWRITER_EXPANSION_UNSUPPORTED', '打字机百分号文字需要 expansion=none', exit_code=2)
        if re.search(r'\b(?:rand|random|st|ld|print|metadata|x|y)\b', str(style.get('x', ''))+' '+str(style.get('y', ''))):
            raise AppError('SUBTITLE_TYPEWRITER_POSITION_UNSUPPORTED', '打字机需要无状态且无 x/y 相互引用的位置表达式', exit_code=2)
        executable = Path(ffmpeg_path()).resolve()
        self.ffmpeg_sha256, self.font_sha256 = file_fingerprint(executable), file_fingerprint(font)
        if not snapshot and not _runtime_text_supported(str(executable), self.ffmpeg_sha256):
            raise AppError('SUBTITLE_TYPEWRITER_NATIVE_COMMAND_UNAVAILABLE', '本地 FFmpeg 必须支持 drawtext 的 text 运行时命令', exit_code=6)
        self.starts = [start+delay+i*duration/max(1, len(self.units)) if snapshot else
            round(start+delay+i*duration/max(1, len(self.units)), 9) for i in range(len(self.units))]
        boundary=format(start+delay,'.17g') if snapshot else format(start+delay,'.9f')
        self.first_enable = f'gte(({authored_expression}),{boundary})'
        identity = {'protocol': 'drawtext-native-prefix-cfr-v1', 'source': layout.source, 'style': style,
                    'font_sha256': self.font_sha256, 'ffmpeg_sha256': self.ffmpeg_sha256, 'fontsize': size,
                    'clock': clock, 'fps': fps, 'origin': origin, 'starts': self.starts, 'clip_id': clip_id,
                    'lines': [(line.text, line.start, line.end) for line in layout.lines]}
        # FFmpeg truncates filter instance names in its graph parser. Keep
        # room for the paint/component suffix so sendcmd resolves every target.
        self.token = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:16]
        self.directory = root/'cache'/'text-typing'/self.token
        self.directory.mkdir(parents=True, exist_ok=True)
        self.serial = 0
        self.targets: dict[str, int] = {}
        self.initial = self.prefixes(self.count(self.author_time(self.origin)))

    def author_time(self, display: float) -> float:
        return compose_time(self.clock.get('maps', []), display, inverse=True) - self.clock.get('reverse_boundary_bias_seconds', 0.)

    def count(self, author: float) -> int:
        return bisect.bisect_right(self.starts, author)

    def prefixes(self, count: int) -> list[str]:
        end = self.units[count-1][1] if count else 0
        return [line.text[:max(0, min(line.end, end)-line.start)] for line in self.layout.lines]

    def text_option(self, text: str, target: str | None = None) -> str:
        path = self.directory/(hashlib.sha256(text.encode('utf-8')).hexdigest()+'.txt')
        atomic_write_text(path, text)
        return ('drawtext@'+target if target else 'drawtext')+'=textfile='+_quoted(path.relative_to(self.root).as_posix())

    def paint(self, parts: list[str], metrics: dict[str, dict[str, Any]], values: dict[str, Any],
              base_x: str, base_y: str, paint: Callable[[list[str]], str] | None) -> str:
        if self.style.get('boxw') and float(self.style['boxw']) < values['text_w'] or self.style.get('boxh') and float(self.style['boxh']) < values['text_h']:
            raise AppError('SUBTITLE_TYPEWRITER_BOX_CLIP_UNSUPPORTED', '打字机显式文字框不能小于完整段落', exit_code=2)
        draw = paint or (lambda options: ':'.join(options))
        x, y = paragraph_origin(base_x, base_y, values, self.style)
        x, y = (re.sub(r'\bN\b', 'n', re.sub(r'\bT\b', 't', value)) for value in (x, y))
        center, right, oy, boxw = paragraph_alignment(self.style, values)
        common = [part for part in parts[1:] if not re.match(r'(?:x|y|box|boxcolor|boxborderw|boxw|boxh|text_align|fix_bounds|expansion)=', part)]
        filters = []
        if self.units and self.style.get('box', True):
            background = [part for part in parts[1:] if not re.match(r'(?:x|y|fontcolor|borderw|shadowx|shadowy|fix_bounds|expansion|boxw|boxh|enable)=', part)]
            enabled = [part.split('=', 1)[1].strip("'") for part in parts[1:] if part.startswith('enable=')]
            enable = '*'.join([f'({value})' for value in enabled] + [self.first_enable])
            filters.append(draw([self.text_option(' '), *background, 'fontcolor=white@0', 'borderw=0', 'shadowx=0', 'shadowy=0',
                f'boxw={int(boxw)}', f'boxh={int(self.style.get("boxh") or values["text_h"])}',
                f'x={_quoted(x)}', f'y={_quoted(y)}', 'fix_bounds=0', 'expansion=none', f'enable={_quoted(enable)}']))
        step = values['line_h']+int(self.style.get('line_spacing', 0))
        serial = self.serial; self.serial += 1
        for index, line in enumerate(self.layout.lines):
            if not line.text: continue
            target = f'avk_typing_{self.token}_{serial}_{index}'
            self.targets[target] = index
            width = metrics[line.text]['text_w']
            ox = math.trunc((boxw-width)/(2 if center else 1)) if center or right else 0
            baseline = oy+index*step+values['top_a']
            filters.append(draw([self.text_option(self.initial[index], target), *common,
                f'x={_quoted(f"({x})+{ox}")}', f'y={_quoted(f"({y})+{baseline:.9f}-top_a")}',
                'box=0', 'fix_bounds=0', 'expansion=none']))
        return ','.join(filters) or 'null'

    def finish(self, value: str, command_targets: dict[str, list[str]]) -> tuple[str, dict[str, Any]]:
        if self.snapshot:
            return value, {'protocol': 'drawtext-native-prefix-snapshot-v1',
                'engine': 'native-prefix-author-clock-snapshot', 'author_seconds': self.author_time(self.origin),
                'grapheme_count': len(self.units), 'revealed_graphemes': self.count(self.author_time(self.origin)),
                'line_count': len(self.layout.lines), 'paint_count': self.serial, 'command_count': 0,
                'paragraph_anchor': 'complete-paragraph-fixed-origin-and-baselines',
                'prefix_shaping': 'whole-native-run', 'newline_consumes_step': False,
                'authored_whitespace_consumes_step': True, 'frame_grid_quantization': False}
        bias = self.clock.get('reverse_boundary_bias_seconds', 0.)
        candidates = {0}
        for author in self.starts:
            display = compose_time(self.clock.get('maps', []), author+bias)
            near = math.floor((display-self.origin)*self.fps)
            candidates.update(max(0, near+delta) for delta in (-2, -1, 0, 1, 2, 3))
        previous = self.initial
        lines, states = [], []
        commands = 0
        targets = {name: command_targets.get(name, [name]) for name in self.targets}
        for frame in sorted(candidates):
            display = self.origin+frame/self.fps
            author = self.author_time(display)
            count = self.count(author)
            prefixes = self.prefixes(count)
            changed = [i for i, (left, right) in enumerate(zip(previous, prefixes)) if left != right]
            if not changed: continue
            events = []
            for name, index in self.targets.items():
                if index in changed:
                    events.extend(f'drawtext@{target} text {_command_token(prefixes[index])}' for target in targets[name])
            if events:
                at = max(0., self.origin+(frame-.5)/self.fps)
                lines.append(f'{at:.12f} '+', '.join(events)+';')
                commands += len(events)
            states.append({'frame': frame, 'display_seconds': display, 'author_seconds': author,
                           'revealed_graphemes': count, 'line_prefix_lengths': [len(prefix) for prefix in prefixes]})
            previous = prefixes
        text = '\n'.join(lines)+'\n'
        if len(text.encode('utf-8')) > 4*1024*1024 or commands > 16384:
            raise AppError('SUBTITLE_TYPEWRITER_BUDGET', '打字机命令超过 4 MiB / 16384 命令预算', exit_code=2)
        evidence = {'protocol': 'drawtext-native-prefix-cfr-v1', 'engine': 'native-prefix-runtime-text',
                    'ffmpeg_sha256': self.ffmpeg_sha256, 'font_sha256': self.font_sha256,
                    'grapheme_count': len(self.units), 'line_count': len(self.layout.lines), 'paint_count': self.serial,
                    'native_target_count': sum(len(items) for items in targets.values()), 'command_count': commands,
                    'fps': self.fps, 'frame_origin_seconds': self.origin, 'sampling': 'compiled-author-clock-at-CFR-samples',
                    'commands_between_adjacent_samples': True, 'initial_line_prefix_lengths': [len(prefix) for prefix in self.initial],
                    'states': states, 'paragraph_anchor': 'complete-paragraph-fixed-origin-and-baselines',
                    'prefix_shaping': 'whole-native-run', 'newline_consumes_step': False, 'authored_whitespace_consumes_step': True}
        if lines:
            # Different paint graphs can share paragraph/clock identity. Keep
            # their command streams immutable for stored plans and replay.
            path = self.directory/('commands-'+hashlib.sha256(text.encode('utf-8')).hexdigest()+'.ffcmd')
            atomic_write_text(path, text)
            evidence.update(command_file=path.relative_to(self.root).as_posix(), command_file_sha256=sha256_file(path))
            value = 'sendcmd=filename='+_quoted(path.relative_to(self.root).as_posix())+','+value
        return value, evidence
