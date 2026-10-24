"""Versioned offline community resources with per-file provenance and hashes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error
from .utils import ensure_inside, sha256_file

DATA = Path(__file__).with_name('material_data')
CATALOG_VERSION = '1.0.0'
KINDS = ('music', 'jingle', 'sfx', 'font')


def catalog() -> dict[str, Any]:
    path = DATA / 'catalog.json'
    if not path.is_file():
        raise AppError('MATERIAL_CATALOG_MISSING', '安装包缺少内置素材目录', exit_code=10, path=str(path))
    value = json.loads(path.read_text('utf-8'))
    records = value.get('records', [])
    if value.get('catalog_version') != CATALOG_VERSION or len({r['id'] for r in records}) != len(records):
        raise AppError('MATERIAL_CATALOG_INVALID', '内置素材目录版本或 ID 无效', exit_code=10)
    return value


def find(ident: str) -> tuple[dict[str, Any], dict[str, Any]]:
    data = catalog()
    row = next((r for r in data['records'] if r['id'] == ident or any(a['id'] == ident for a in r.get('aliases', []))), None)
    if row is None:
        raise argument_error('找不到内置素材 ID: ' + ident, 'id')
    collection = next(c for c in data['collections'] if c['id'] == row['collection_id'])
    return row, collection


def search(*, query: str = '', kind: str | None = None, category: str | None = None,
           limit: int = 40, offset: int = 0) -> dict[str, Any]:
    if not 1 <= limit <= 1000 or offset < 0:
        raise argument_error('limit 必须为 1–1000，offset 必须非负', 'limit/offset')
    data = catalog()
    collections = {c['id']: c for c in data['collections']}
    terms = query.casefold().split()
    matches = []
    for row in data['records']:
        if kind and row['kind'] != kind or category and row['category'] != category:
            continue
        col = collections[row['collection_id']]
        text = ' '.join([row['id'], row['name'], row['name_zh'], row['name_zh_tw'],
                         row['category'], *row['tags'], col['license']['spdx'], col['creator'],
                         *(a['id'] + ' ' + a['name'] for a in row.get('aliases', []))]).casefold()
        if all(term in text for term in terms):
            matches.append({**row, 'license_spdx': col['license']['spdx'], 'creator': col['creator']})
    return {'catalog_version': CATALOG_VERSION, 'counts': data['counts'], 'total_matches': len(matches),
            'limit': limit, 'offset': offset, 'records': matches[offset:offset + limit], 'network': 'disabled'}


def checked_path(relative: str, expected: str) -> Path:
    path = ensure_inside(DATA, DATA / relative)
    if not path.is_file() or sha256_file(path) != expected:
        raise AppError('MATERIAL_INTEGRITY_MISMATCH', '内置素材或许可证据缺失/摘要不符', exit_code=10, path=str(path))
    return path


def verify(ident: str) -> dict[str, Any]:
    row, collection = find(ident)
    source = checked_path(row['path'], row['sha256'])
    notice = checked_path(collection['notice_path'], collection['notice_sha256'])
    evidence = checked_path(collection['evidence_path'], collection['evidence_sha256'])
    return {'record': row, 'collection': collection, 'file': str(source), 'notice': str(notice),
            'evidence': str(evidence), 'verified': True, 'network': 'disabled'}


def voices(*, language: str | None = None, query: str = '') -> dict[str, Any]:
    data = json.loads((DATA / 'voices.json').read_text('utf-8'))
    data['voices'] = [r for r in data['voices'] if (not language or r['language'] == language)
                      and (not query or query.casefold() in (r['id'] + ' ' + r['gender'] + ' ' + r['description']).casefold())]
    return {**data, 'count': len(data['voices']), 'weights_in_base_package': False, 'network': 'disabled'}
