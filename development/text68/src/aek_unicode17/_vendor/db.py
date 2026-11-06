"""Pinned Unicode 17 property lookup; no host unicodedata dependency."""
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
