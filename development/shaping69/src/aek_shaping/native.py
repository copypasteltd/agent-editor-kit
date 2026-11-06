"""Strict ctypes binding to the explicitly pinned, offline text-engine build."""
from __future__ import annotations
import ctypes as c
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import threading


class ShapingError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, code, message):
    if not condition:
        raise ShapingError(code, message)


def integer(value, minimum, maximum):
    return not isinstance(value, bool) and isinstance(value, int) and minimum <= value <= maximum


def tag(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9 ]{4}', value) is not None,
            'TEXT_TAG', 'OpenType tags must contain exactly four ASCII letters, numbers or spaces')
    return int.from_bytes(value.encode('ascii'), 'big')


class Run(c.Structure):
    _fields_ = [(name, c.c_uint32) for name in ('start', 'length', 'level', 'tag')]


class Glyph(c.Structure):
    _fields_ = [(name, c.c_uint32) for name in ('id', 'cluster', 'flags')] + [
        (name, c.c_int32) for name in ('x_advance', 'y_advance', 'x_offset', 'y_offset',
                                     'x_bearing', 'y_bearing', 'width', 'height')]


class Feature(c.Structure):
    _fields_ = [('tag', c.c_uint32), ('value', c.c_uint32)]


class Axis(c.Structure):
    _fields_ = [('tag', c.c_uint32), ('value', c.c_float)]


@dataclass(frozen=True)
class FontSpec:
    path: Path
    sha256: str
    pixels: int
    index: int = 0
    variations: dict[str, float] = field(default_factory=dict)


class Engine:
    def __init__(self, manifest: Path):
        require(os.name == 'nt' and c.sizeof(c.c_void_p) == 8, 'TEXT_PLATFORM', 'This build profile requires native Windows x64')
        manifest = Path(manifest).resolve()
        data = json.loads(manifest.read_bytes())
        require(data['format'] == 'aek-shaping69-native-v1', 'TEXT_NATIVE_MANIFEST', 'Unsupported native text manifest')
        binary = (manifest.parent / data['binary_filename']).resolve()
        require(binary.parent == manifest.parent and binary.suffix == '.dll', 'TEXT_NATIVE_PATH', 'Native library must be beside its manifest')
        require(hashlib.sha256(binary.read_bytes()).hexdigest() == data['binary_sha256'],
                'TEXT_NATIVE_DIGEST', 'Native text library bytes changed')
        self.manifest = data
        self.binary = binary
        self.dll = d = c.CDLL(str(binary), winmode=0x00000100 | 0x00001000)
        u, i, p = c.c_uint32, c.c_int32, c.c_void_p
        U, I, B = c.POINTER(u), c.POINTER(i), c.POINTER(c.c_uint8)
        self._bind('aek_text_abi', [], u)
        self._bind('aek_sheen_version', [], c.c_char_p)
        self._bind('aek_harfbuzz_version', [], c.c_char_p)
        self._bind('aek_freetype_version', [I, I, I], None)
        self._bind('aek_bidi', [U, u, u, u, u, B, U, U, c.POINTER(Run), u, U, U], i)
        self._bind('aek_scripts', [U, u, c.POINTER(Run), u, U], i)
        self._bind('aek_font_create', [B, u, u, u, c.POINTER(Axis), u, I], p)
        self._bind('aek_font_destroy', [p], None)
        self._bind('aek_font_nominal', [p, u], u)
        self._bind('aek_font_metrics', [p, I], i)
        self._bind('aek_shape', [p, U, u, u, u, u, u, c.c_char_p, c.POINTER(Feature), u,
                                 c.POINTER(Glyph), u, U], i)
        self._bind('aek_carets', [p, u, u, I, u, U], i)
        self._bind('aek_bitmap', [p, u, u, u, B, u, I], i)
        version = [i() for _ in range(3)]
        d.aek_freetype_version(*(c.byref(value) for value in version))
        self.versions = dict(sheenbidi=d.aek_sheen_version().decode('ascii'),
                             harfbuzz=d.aek_harfbuzz_version().decode('ascii'),
                             freetype='.'.join(str(value.value) for value in version))
        require(d.aek_text_abi() == 1 and self.versions == data['versions'],
                'TEXT_NATIVE_VERSION', 'Loaded text engine versions differ from the pinned build')

    def _bind(self, name, args, result):
        function = getattr(self.dll, name)
        function.argtypes, function.restype = args, result

    def codepoints(self, text):
        require(isinstance(text, str) and len(text) <= 16384 and
                all(not 0xD800 <= ord(char) <= 0xDFFF for char in text),
                'TEXT_SOURCE', 'Text must contain at most 16384 Unicode scalar values')
        return (c.c_uint32 * len(text))(*(ord(char) for char in text))

    def bidi(self, text, *, base='auto-ltr', start=0, end=None):
        source = self.codepoints(text)
        end = len(text) if end is None else end
        modes = {'ltr': 0, 'rtl': 1, 'auto-ltr': 254, 'auto-rtl': 253}
        require(base in modes and integer(start, 0, len(text)) and integer(end, start, len(text)),
                'TEXT_BIDI_RANGE', 'Invalid paragraph direction or line range')
        if not text:
            return dict(levels=[], order=[], runs=[], base=1 if base in ('rtl', 'auto-rtl') else 0)
        require(start < end, 'TEXT_BIDI_RANGE', 'A nonempty paragraph needs a nonempty line')
        n = len(text)
        levels, order, runs = (c.c_uint8 * n)(), (c.c_uint32 * n)(), (Run * n)()
        order_count, run_count, resolved = c.c_uint32(), c.c_uint32(), c.c_uint32()
        result = self.dll.aek_bidi(source, n, modes[base], start, end - start, levels, order,
                                   c.byref(order_count), runs, n, c.byref(run_count), c.byref(resolved))
        require(result == 0, 'TEXT_BIDI_NATIVE', 'Bidirectional analysis failed with native status ' + str(result))
        return dict(levels=list(levels), order=list(order[:order_count.value]),
                    runs=[dict(start=run.start, end=run.start + run.length, level=run.level)
                          for run in runs[:run_count.value]], base=resolved.value)

    def scripts(self, text):
        source = self.codepoints(text)
        if not text:
            return []
        runs, count = (Run * len(text))(), c.c_uint32()
        result = self.dll.aek_scripts(source, len(text), runs, len(text), c.byref(count))
        require(result == 0, 'TEXT_SCRIPT_NATIVE', 'Script analysis failed')
        return [dict(start=run.start, end=run.start + run.length, tag=run.tag)
                for run in runs[:count.value]]

    def font(self, spec):
        return Font(self, spec)


class Font:
    def __init__(self, engine, spec):
        require(isinstance(spec, FontSpec) and integer(spec.pixels, 4, 512) and integer(spec.index, 0, 1024),
                'TEXT_FONT_SPEC', 'Invalid explicit font specification')
        require(re.fullmatch(r'[0-9a-f]{64}', spec.sha256 or '') is not None,
                'TEXT_FONT_DIGEST', 'An explicit lowercase SHA256 is required for every font')
        path = Path(spec.path).resolve()
        require(path.is_file() and 12 <= path.stat().st_size <= 64 * 1024**2,
                'TEXT_FONT_SIZE', 'Font bytes are missing or exceed the 64 MiB budget')
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == spec.sha256, 'TEXT_FONT_DIGEST', 'Explicit font bytes changed')
        require(isinstance(spec.variations, dict) and len(spec.variations) <= 32,
                'TEXT_FONT_AXES', 'At most 32 explicit variation axes are supported')
        import math
        axes = []
        for key, value in sorted(spec.variations.items()):
            require(not isinstance(value, bool) and isinstance(value, (int, float)) and abs(value) <= 32767 and math.isfinite(value),
                    'TEXT_FONT_AXES', 'Variation axis values must be finite design coordinates')
            axes.append(Axis(tag(key), float(value)))
        values = (Axis * len(axes))(*axes)
        buffer = (c.c_uint8 * len(raw)).from_buffer_copy(raw)
        error = c.c_int32()
        handle = engine.dll.aek_font_create(buffer, len(raw), spec.index, spec.pixels, values, len(axes), c.byref(error))
        require(bool(handle) and error.value == 0, 'TEXT_FONT_NATIVE', 'Font profile rejected with native status ' + str(error.value))
        self.engine, self.spec, self.handle = engine, spec, handle
        self.native_variations = tuple(sorted((key, float(value)) for key, value in spec.variations.items()))
        self.lock = threading.RLock()
        self._nominal_cache = {}
        metrics = (c.c_int32 * 4)()
        if engine.dll.aek_font_metrics(handle, metrics) != 0:
            self.close()
            raise ShapingError('TEXT_FONT_NATIVE', 'Font metrics unavailable')
        self.metrics = dict(zip(('ascender', 'descender', 'height', 'upem'), metrics))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        with self.lock:
            if self.handle:
                self.engine.dll.aek_font_destroy(self.handle)
                self.handle = None

    def _open(self):
        require(bool(self.handle), 'TEXT_FONT_CLOSED', 'Font handle has been explicitly closed')

    def nominal(self, char):
        require(isinstance(char, str) and len(char) == 1 and not 0xD800 <= ord(char) <= 0xDFFF,
                'TEXT_CODEPOINT', 'A nominal lookup requires one Unicode scalar')
        with self.lock:
            self._open()
            codepoint = ord(char)
            if codepoint not in self._nominal_cache:
                self._nominal_cache[codepoint] = self.engine.dll.aek_font_nominal(self.handle, codepoint)
            return self._nominal_cache[codepoint]

    def shape(self, text, start, end, level, script, language='und', features=None):
        features = features or {}
        require(isinstance(features, dict) and len(features) <= 64,
                'TEXT_FEATURE', 'At most 64 global OpenType features are supported')
        require(isinstance(language, str) and re.fullmatch(r'[A-Za-z0-9-]{1,64}', language) is not None,
                'TEXT_LANGUAGE', 'Language must be a bounded language tag')
        values = []
        for key, value in sorted(features.items()):
            require(integer(value, 0, 65535), 'TEXT_FEATURE', 'Feature values must be bounded integers')
            values.append(Feature(tag(key), value))
        native_features = (Feature * len(values))(*values)
        source = self.engine.codepoints(text)
        require(integer(start, 0, len(text)) and integer(end, start, len(text)) and integer(level, 0, 125),
                'TEXT_SHAPE_RANGE', 'Invalid shaping range or level')
        capacity = min(65536, max(32, (end - start) * 16))
        glyphs, count = (Glyph * capacity)(), c.c_uint32()
        with self.lock:
            self._open()
            result = self.engine.dll.aek_shape(self.handle, source, len(text), start, end - start,
                level & 1, script, language.encode('ascii'), native_features, len(values), glyphs, capacity, c.byref(count))
        require(result == 0, 'TEXT_SHAPE_NATIVE', 'Shaping failed with native status ' + str(result))
        return [{name: getattr(glyph, name) for name, _ in Glyph._fields_} for glyph in glyphs[:count.value]]

    def carets(self, glyph, level):
        require(integer(glyph, 0, 0xFFFFFFFF) and integer(level, 0, 125), 'TEXT_CARET_RANGE', 'Invalid glyph or bidi level')
        positions, count = (c.c_int32 * 256)(), c.c_uint32()
        with self.lock:
            self._open()
            result = self.engine.dll.aek_carets(self.handle, glyph, level & 1, positions, 256, c.byref(count))
        require(result == 0, 'TEXT_CARET_NATIVE', 'Ligature carets exceeded the native budget')
        return list(positions[:count.value])

    def bitmap(self, glyph, phase_x, phase_y):
        require(integer(glyph, 0, 0xFFFFFFFF) and integer(phase_x, 0, 63) and integer(phase_y, 0, 63),
                'TEXT_BITMAP_PHASE', 'Invalid glyph or origin phase')
        metrics = (c.c_int32 * 4)()
        with self.lock:
            self._open()
            result = self.engine.dll.aek_bitmap(self.handle, glyph, phase_x, phase_y, None, 0, metrics)
            require(result == 0, 'TEXT_BITMAP_NATIVE', 'Glyph rasterization failed')
            length = metrics[0] * metrics[1]
            if not length:
                return tuple(metrics), b''
            pixels = (c.c_uint8 * length)()
            result = self.engine.dll.aek_bitmap(self.handle, glyph, phase_x, phase_y, pixels, length, metrics)
            require(result == 0, 'TEXT_BITMAP_NATIVE', 'Glyph bitmap copy failed')
        return tuple(metrics), bytes(pixels)
