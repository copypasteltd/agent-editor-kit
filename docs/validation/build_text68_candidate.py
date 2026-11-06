"""Build the isolated text68 source candidate without importing or testing it.

Only reviewed MIT algorithm sources and Unicode data are redistributed. The
downloaded annex HTML documents remain private research inputs. No product67
file, registered Skill, Python installation or active environment is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'development/text68/src/aek_unicode17'
PINS = {
    'auxiliary/GraphemeBreakProperty.txt': 'd6b51d1d2ae5c33b451b7ed994b48f1f4dc62b2272a5831e7fd418514a6bae89',
    'auxiliary/GraphemeBreakTest.txt': 'e2d134d2c52919bace503ebb6a551c1855fe1a1faec18478c78fff254a1793ec',
    'auxiliary/LineBreakTest.txt': 'e69884e0dde6a8724873f885d68c52dc14518abf9ae4ca9e2283b8773db3b752',
    'LineBreak.txt': 'e6a18fa91f8f6a6f8e534b1d3f128c21ada45bfe152eb6b1bcc5e15fd8ac92e6',
    'DerivedCoreProperties.txt': '24c7fed1195c482faaefd5c1e7eb821c5ee1fb6de07ecdbaa64b56a99da22c08',
    'UnicodeData.txt': '2e1efc1dcb59c575eedf5ccae60f95229f706ee6d031835247d843c11d96470c',
    'EastAsianWidth.txt': 'ea7ce50f3444a050333448dffef1cadd9325af55cbb764b4a2280faf52170a33',
    'extracted/DerivedBidiClass.txt': '4867b4b7f0731ed1bfcd34cc6251211ff1542541fce0734b6fbda139ee80b3a4',
    'emoji/emoji-data.txt': '2cb2bb9455cda83e8481541ecf5b6dfda66a3bb89efa3fa7c5297eccf607b72b',
    'unicode-license.txt': 'e7a93b009565cfce55919a381437ac4db883e9da2126fa28b91d12732bc53d96',
}
WHEEL_SHA = '74fe3f7b4ee46bbd703a70ea1e5cd28e04f63eee5af9a10388d93316c554e358'
LIMIT = 0x110000


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def code_range(value: str) -> tuple[int, int]:
    parts = value.strip().split('..')
    assert 1 <= len(parts) <= 2
    first, last = int(parts[0], 16), int(parts[-1], 16)
    assert 0 <= first <= last < LIMIT
    return first, last


def compact(values: list[str], default: str) -> dict:
    rows = []
    start, current = 0, values[0]
    for index in range(1, LIMIT + 1):
        if index == LIMIT or values[index] != current:
            if current != default:
                rows.append([start, index - 1, current])
            if index < LIMIT:
                start, current = index, values[index]
    return {'default': default, 'ranges': rows}


def property_table(raw: str, default: str, selected: str | None = None,
                   aliases: dict[str, str] | None = None) -> dict:
    values = [default] * LIMIT
    aliases = aliases or {}
    missing, explicit = [], []
    for line in raw.splitlines():
        match = re.search(r'#\s*@missing:\s*(.*)', line)
        body = match.group(1) if match else line.split('#', 1)[0].strip()
        if not body:
            continue
        fields = [field.strip() for field in body.split(';')]
        if selected is not None:
            if fields[1] != selected:
                continue
            value = fields[2] if len(fields) > 2 else 'Yes'
        else:
            value = fields[1]
        first, last = code_range(fields[0])
        target = missing if match else explicit
        target.append((first, last, aliases.get(value, value)))
    for first, last, value in missing + explicit:
        values[first:last + 1] = [value] * (last - first + 1)
    return compact(values, default)


def category_table(raw: str) -> dict:
    values = ['Cn'] * LIMIT
    pending = None
    for line in raw.splitlines():
        fields = line.split(';')
        first = int(fields[0], 16)
        if fields[1].endswith(', First>'):
            assert pending is None
            pending = (first, fields[1][:-8], fields[2])
        elif fields[1].endswith(', Last>'):
            assert pending is not None and pending[1] == fields[1][:-7] and pending[2] == fields[2]
            values[pending[0]:first + 1] = [fields[2]] * (first - pending[0] + 1)
            pending = None
        else:
            assert pending is None
            values[first] = fields[2]
    assert pending is None
    return compact(values, 'Cn')


DB_CODE = '''"""Pinned Unicode 17 property lookup; no host unicodedata dependency."""
from bisect import bisect_right
from functools import lru_cache
import hashlib
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _tables():
    folder = Path(__file__).resolve().parent.parent
    raw = (folder / 'data/unicode17.json').read_bytes()
    manifest = json.loads((folder / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    if hashlib.sha256(raw).hexdigest() != manifest['property_data_sha256']:
        raise RuntimeError('Pinned Unicode property data digest mismatch')
    data = json.loads(raw)
    if data['unicode_version'] != '17.0.0':
        raise RuntimeError('Wrong Unicode version')
    result = {}
    for name, table in data['tables'].items():
        rows = table['ranges']
        result[name] = (tuple(row[0] for row in rows), rows, table['default'])
    return result


def get_handle(table_name):
    if table_name not in _tables():
        raise KeyError(table_name)
    return table_name


def get_value(handle, codepoint, /):
    if isinstance(codepoint, bool) or not isinstance(codepoint, int) or not 0 <= codepoint < 0x110000:
        raise ValueError('Code point out of range')
    starts, rows, default = _tables()[handle]
    index = bisect_right(starts, codepoint) - 1
    if index >= 0 and codepoint <= rows[index][1]:
        return rows[index][2]
    return default
'''

DERIVED_CODE = '''"""Unicode 17 Indic_Conjunct_Break, backed by pinned UCD data."""
from .db import get_value
from .unicodeproperty import EnumProperty, character_property

class IndicConjunctBreak(EnumProperty):
    NONE = 'None'
    LINKER = 'Linker'
    CONSONANT = 'Consonant'
    EXTEND = 'Extend'

InCB = IndicConjunctBreak

@character_property
def indic_conjunct_break(c, /):
    return InCB(get_value('InCB', ord(c)))
'''

EMOJI_CODE = '''"""Unicode 17 Extended_Pictographic, backed by pinned UCD data."""
from .db import get_value
from .unicodeproperty import character_property

@character_property
def extended_pictographic(c, /):
    return get_value('Extended_Pictographic', ord(c)) == 'Yes'
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', required=True)
    args = parser.parse_args()
    assert args.source_run.isalnum() and len(args.source_run) <= 32
    stage = ROOT / ('local/agent-ffmpeg/text68-20261106-' + args.source_run)
    ucd = stage / 'upstream/unicode17'
    wheel = stage / 'upstream/uniseg-0.10.1-py3-none-any.whl'
    assert sha(wheel.read_bytes()) == WHEEL_SHA
    raws = {}
    for name, digest in PINS.items():
        raw = (ucd / name).read_bytes()
        assert sha(raw) == digest, name
        raws[name] = raw.decode('utf-8-sig')
    originals = stage / 'upstream/uniseg-0.10.1/uniseg'
    # Every copied member must match the original verified wheel bytes.
    import zipfile
    copied = ['breaking.py', 'unicodeproperty.py', 'graphemecluster.py', 'linebreak.py']
    with zipfile.ZipFile(wheel) as zipped:
        for name in copied:
            assert (originals / name).read_bytes() == zipped.read('uniseg/' + name)
        assert (originals.parent / 'uniseg-0.10.1.dist-info/licenses/LICENSE').read_bytes() == zipped.read('uniseg-0.10.1.dist-info/licenses/LICENSE')
    source_hashes = {}
    for name in copied:
        raw = (originals / name).read_bytes()
        source_hashes[name] = sha(raw)
        text = raw.decode('utf-8').replace('from uniseg.', 'from .')
        if name == 'graphemecluster.py':
            text = text.replace('Unicode 16.0.0', 'Unicode 17.0.0').replace('tr29-45.html', 'tr29-47.html')
        if name == 'linebreak.py':
            text = text.replace('Unicode 16.0.0', 'Unicode 17.0.0').replace('tr14-53.html', 'tr14-55.html')
            text = text.replace("    HY = 'HY'", "    HH = 'HH'\n    # Unicode 17 Unambiguous_Hyphen (UAX14 revision 55).\n\n    HY = 'HY'")
            text = text.replace('(LB.SP, LB.BA, LB.HY)', '(LB.SP, LB.BA, LB.HY, LB.HH)')
            begin, end = text.index('        # LB20a'), text.index('        # LB21\n')
            text = text[:begin] + '''        # LB20a, Unicode 17: word-initial HY/HH binds to AL/HL.
        elif (
            (run0 := run.is_following((LB.HY, LB.HH)))
            and (
                run0.prev in (LB.BK, LB.CR, LB.LF, LB.NL, LB.SP, LB.ZW, LB.CB, LB.GL)
                or run0.is_sot()
            )
            and run.curr in (LB.AL, LB.HL)
        ):
            run.do_not_break_here()
''' + text[end:]
            text = text.replace('(LB.BA, LB.HY, LB.NS)', '(LB.BA, LB.HY, LB.HH, LB.NS)')
            text = text.replace('run.is_following((LB.HY, LB.BA)).prev == LB.HL',
                                'run.is_following((LB.HY, LB.HH)).prev == LB.HL')
        notice = '# Adapted from uniseg 0.10.1, Copyright (c) 2013-2024 Masaaki Shibata.\n# MIT; see ../LICENSE_UNISEG.txt. AEK changes: relative imports and pinned Unicode 17.\n'
        write(DEST / '_vendor' / name, (notice + text).encode('utf-8'))
    write(DEST / '_vendor/__init__.py', b'"""Reviewed MIT segmentation algorithms with pinned Unicode 17 data."""\n')
    for name, code in [('db.py', DB_CODE), ('derived.py', DERIVED_CODE), ('emoji.py', EMOJI_CODE)]:
        write(DEST / '_vendor' / name, code.encode('utf-8'))
    categories = 'Lu Ll Lt Lm Lo Mn Mc Me Nd Nl No Pc Pd Ps Pe Pi Pf Po Sm Sc Sk So Zs Zl Zp Cc Cf Cs Co Cn'.split()
    enums = ['"""Unicode 17 property enums. All values come from bundled tables."""',
             'from .unicodeproperty import EnumProperty, character_property', 'from .db import get_value',
             'class Category(EnumProperty):']
    enums += [f'    {value.upper()} = {value!r}' for value in categories]
    enums += ['GC = Category', 'class EastAsianWidth(EnumProperty):']
    enums += [f'    {value.upper()} = {value!r}' for value in ['A', 'F', 'H', 'N', 'Na', 'W']]
    enums += ['EA = EastAsianWidth', '@character_property', 'def category(c, /):',
              "    return GC(get_value('General_Category', ord(c)))", '@character_property',
              'def east_asian_width(c, /):', "    return EA(get_value('East_Asian_Width', ord(c)))"]
    write(DEST / '_vendor/unicodedatawrapper.py', ('\n'.join(enums) + '\n').encode('utf-8'))
    tables = {
        'Grapheme_Cluster_Break': property_table(raws['auxiliary/GraphemeBreakProperty.txt'], 'Other'),
        'InCB': property_table(raws['DerivedCoreProperties.txt'], 'None', 'InCB'),
        'Extended_Pictographic': property_table(raws['emoji/emoji-data.txt'], 'No', 'Extended_Pictographic'),
        'Line_Break': property_table(raws['LineBreak.txt'], 'XX'),
        'General_Category': category_table(raws['UnicodeData.txt']),
        'East_Asian_Width': property_table(raws['EastAsianWidth.txt'], 'N'),
        'Bidi_Class': property_table(raws['extracted/DerivedBidiClass.txt'], 'L', aliases={
            'Left_To_Right': 'L', 'Right_To_Left': 'R', 'Arabic_Letter': 'AL', 'European_Terminator': 'ET'}),
    }
    data = json.dumps({'unicode_version': '17.0.0', 'tables': tables}, separators=(',', ':'), sort_keys=True).encode('utf-8')
    write(DEST / 'data/unicode17.json', data)
    license_path = originals.parent / 'uniseg-0.10.1.dist-info/licenses/LICENSE'
    write(DEST / 'LICENSE_UNISEG.txt', license_path.read_bytes())
    write(DEST / 'LICENSE_UNICODE.txt', (ucd / 'unicode-license.txt').read_bytes())
    manifest = dict(unicode_version='17.0.0', upstream_uniseg='0.10.1', upstream_unicode_version='16.0.0',
        upstream_wheel_sha256=WHEEL_SHA, original_algorithm_sha256=source_hashes,
        property_data_sha256=sha(data), ucd_sources=PINS,
        changes=['Relative imports; standalone namespace', 'All property lookups use pinned Unicode 17 data',
                 'UAX14 rev55 HH class and LB12a/LB20a/LB21/LB21a changes',
                 'No host unicodedata, regex, network, subprocess or optional package dependency'],
        annex_html_redistributed=False, product67_modified=False, tests_started=False)
    write(DEST / 'SOURCE_MANIFEST.json', (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    print(json.dumps({'status': 'candidate-sources-written-not-tested', 'data_bytes': len(data),
                      'range_counts': {key: len(value['ranges']) for key, value in tables.items()}}, sort_keys=True))


if __name__ == '__main__':
    main()
