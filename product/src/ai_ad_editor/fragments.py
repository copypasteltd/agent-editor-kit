"""Immutable offline edited groups, inspired by OpenFilm Saved (MIT).

Workflow reference: openfilm/openfilm eefd6a8d379289102141359a4718dbab12170526,
studio/server/saved.mjs and studio/ui/src/lib/saved-insert.ts. Copyright (c)
2026 OpenFilm contributors; see OPENFILM_LICENSE.txt. This implementation uses
native author clocks, resource hashes and Rights Ledger histories, not HTML.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any

from .artifact_locks import artifact_entry
from .edit_planner import project_fingerprint
from .errors import AppError
from .lut_library import find_lut
from .policy import reference_kind, resolve_local_path
from .project import _native_byte_lock, find_sequence, find_track
from .rights import active_records, check_project_rights
from .sequence_canvas import sequence_canvas
from .utils import ID_RE, load_json, sha256_file

VERSION = '0.1.0'
ENGINE = 'agent-local-fragment-library-v1'
MAX_FILES = 4096
MAX_MANIFEST = 32 * 1024**2
DEFAULT_MAX_BYTES = 4 * 1024**3
MAX_BYTES = 64 * 1024**3
HASH_RE = re.compile(r'^sha256:[0-9a-f]{64}$')


def fail(code: str, message: str, path: str = 'fragment') -> None:
    raise AppError(code, message, exit_code=2, path=path)


def _id(value, field='id') -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        fail('FRAGMENT_REQUEST_INVALID', '片段组标识符无效', field)
    return value


def _int(value, field, minimum=0) -> int:
    if type(value) is not int or value < minimum:
        fail('FRAGMENT_REQUEST_INVALID', '必须为范围内整数，不能是布尔或浮点数', field)
    return value


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')


def digest(value: Any) -> str:
    return 'sha256:' + hashlib.sha256(json_bytes(value)).hexdigest()


def library_path(value: str | Path) -> Path:
    root = resolve_local_path(Path.cwd(), str(value), field='library')
    if str(root).startswith('\\\\'):
        fail('FRAGMENT_LIBRARY_INVALID', '片段组库要求本地磁盘目录', 'library')
    return root


def entry_path(library: Path, group_id: str, version: int) -> Path:
    _id(group_id)
    _int(version, 'version', 1)
    path = library / 'entries' / hashlib.sha256(group_id.encode('utf-8')).hexdigest() / str(version)
    if not path.resolve().is_relative_to(library.resolve()):
        fail('FRAGMENT_PATH_INVALID', '片段组版本目录不能通过目录联接移出本地库', str(path))
    return path


def byte_budget(value: int) -> int:
    if type(value) is not int or not 1 <= value <= MAX_BYTES:
        fail('FRAGMENT_BUDGET_INVALID', '资源字节上限必须为 1..64 GiB 的整数', 'max_bytes')
    return value


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _runtime_context(settings: dict) -> dict:
    if settings.get('adjustments') or settings.get('audio_stretch'):
        fail('FRAGMENT_CONTEXT_UNSUPPORTED', '片段组首版不搬运全局调节层或外部音频执行配置', 'settings')
    # Dimensions are fixed per saved sequence. Output encoding is a delivery
    # choice; all remaining execution settings must match exactly on insertion.
    return {k: copy.deepcopy(v) for k, v in settings.items() if k not in {'canvas', 'output', 'adjustments', 'audio_stretch'}}


def _selection(project: dict, sequence: dict, requested: list[str] | None):
    index = {c['id']: c for t in sequence['tracks'] for c in t['clips']}
    if requested is None:
        selected = set(index)
    else:
        if not isinstance(requested, list) or not requested or any(not isinstance(c, str) for c in requested) or len(set(requested)) != len(requested):
            fail('FRAGMENT_SELECTION_INVALID', 'clip_ids 必须为非空且无重复的数组', 'clip_ids')
        for cid in requested:
            _id(cid, 'clip_ids')
        selected = set(requested)
    if not selected or selected-set(index):
        fail('FRAGMENT_SELECTION_INVALID', '选择为空或片段不在指定序列', 'clip_ids')
    original = set(selected)
    from .magnetic_mode import enabled as magnetic_enabled
    if sequence.get('audio_routing') is not None or magnetic_enabled(sequence):
        # Nonlinear buses and the magnetic main invariant belong to the full
        # sequence. Report expanded selection instead of changing either clock.
        selected.update(index)
    while True:
        prior = set(selected)
        links = {index[c].get('link_id') for c in selected}-{None, ''}
        selected.update(cid for cid, c in index.items() if c.get('link_id') in links)
        for cid in sorted(selected):
            binding = index[cid].get('tracking_binding')
            if isinstance(binding, dict):
                source = binding.get('source_clip_id')
                if source not in index:
                    fail('FRAGMENT_REFERENCE_MISSING', '跟踪绑定源不在当前序列')
                selected.add(source)
        for tr in sequence.get('source_transitions', []):
            refs = {tr['from_clip_id'], tr['to_clip_id']}
            for pair in tr.get('audio_pairs', []):
                refs.update((pair['from_clip_id'], pair['to_clip_id']))
            if refs & selected:
                selected.update(refs)
        if selected-set(index):
            fail('FRAGMENT_REFERENCE_MISSING', '转场依赖片段缺失')
        if selected == prior:
            break
    if selected != set(index):
        for value in _walk(sequence):
            if value.get('duck_under_voice') or isinstance(value.get('ducking'), dict):
                fail('FRAGMENT_PARTIAL_BUS_UNSUPPORTED', '含闪避音频总线时须保存完整序列')
    return selected, sorted(original), sorted(selected-original)


class Collector:
    """Hold only metadata and file paths; media bytes are streamed at publish."""
    def __init__(self, root: Path, project: dict, ledger: dict, max_bytes: int):
        self.root = root
        self.assets = {a['id']: a for a in project['assets']}
        self.records = {r['asset_id']: r for r in active_records(ledger)}
        self.files: dict[str, dict] = {}
        self.sources: dict[str, Path] = {}
        self.asset_ids: set[str] = set()
        self.rights_ids: set[str] = set()
        self.max_bytes = byte_budget(max_bytes)
        self.warnings: list[dict] = []
        self.adaptations: list[dict] = []

    def file(self, value: str, *, expected=None, role='resource') -> tuple[str, dict]:
        if str(value).startswith('\\\\'):
            fail('FRAGMENT_REMOTE_REFERENCE', '资源不能来自网络共享', role)
        path = resolve_local_path(self.root, value, field=role)
        if str(path).startswith('\\\\'):
            fail('FRAGMENT_REMOTE_REFERENCE', '资源不能来自网络共享', role)
        if not path.is_file():
            fail('FRAGMENT_RESOURCE_MISSING', '片段组本地资源文件缺失', str(path))
        size = path.stat().st_size
        if size < 1 or size > self.max_bytes:
            fail('FRAGMENT_BUDGET_EXCEEDED', '资源为空或超过总量上限', str(path))
        entry = artifact_entry(path, 'fragment-'+role)
        if expected is not None and entry['sha256'] != expected:
            fail('FRAGMENT_RESOURCE_HASH_MISMATCH', '资源实际摘要与登记摘要不符', str(path))
        suffix = path.suffix.lower()
        if not re.fullmatch(r'\.[a-z0-9]{1,12}', suffix):
            suffix = '.bin'
        relative = f"files/{entry['sha256'][7:]}{suffix}"
        if relative not in self.files:
            if len(self.files) >= MAX_FILES or sum(x['bytes'] for x in self.files.values())+size > self.max_bytes:
                fail('FRAGMENT_BUDGET_EXCEEDED', '片段组资源超过文件数或字节总量限制')
            self.files[relative] = {'path': relative, 'sha256': entry['sha256'], 'bytes': size}
            self.sources[relative] = path
        return relative, entry

    def rights_for_file(self, entry: dict, role: str) -> dict:
        matches = [r for r in self.records.values() if r.get('sha256') == entry['sha256']]
        if not matches:
            fail('FRAGMENT_RIGHTS_MISSING', '文件依赖必须先登记对应摘要的权利记录', role)
        # Include all matching records, rather than choosing a more permissive
        # registration and accidentally bypassing a restriction or takedown.
        self.rights_ids.update(r['asset_id'] for r in matches)
        return {'rights_ref': sorted(r['asset_id'] for r in matches)[0], 'sha256': entry['sha256']}

    def resources(self, value: Any) -> None:
        for obj in list(_walk(value)):
            for key, child in list(obj.items()):
                if key == 'asset_id' or key.endswith('_asset_id'):
                    if child is not None:
                        if not isinstance(child, str) or child not in self.assets:
                            fail('FRAGMENT_REFERENCE_MISSING', '依赖资产未登记: '+str(child), key)
                        self.asset_ids.add(child)
                elif key == 'rights_ref' and child:
                    self.rights_ids.add(str(child))
            if obj.get('lut_id'):
                lut = find_lut(self.root, str(obj['lut_id']))
                if not lut:
                    fail('FRAGMENT_REFERENCE_MISSING', 'LUT ID 未登记', 'lut_id')
                relative, entry = self.file(lut['uri'], expected=lut['sha256'], role='lut')
                dep = self.rights_for_file(entry, 'lut')
                self.adaptations.append({'kind': 'lut_id_to_fixed_file', 'lut_id': obj.pop('lut_id'),
                                         'path': relative, 'rights_ref': dep['rights_ref']})
                for alias in ('file', 'lut'):
                    obj.pop(alias, None)
                obj['path'] = relative
            for key in ('asset_uri', 'fontfile'):
                if isinstance(obj.get(key), str) and obj[key]:
                    relative, entry = self.file(obj[key], role=key)
                    self.rights_for_file(entry, key)
                    obj[key] = relative
            kind = str(obj.get('type', '')).lower().replace('-', '_')
            if kind in {'lut', 'lut3d'}:
                params = obj.get('parameters') if isinstance(obj.get('parameters'), dict) else obj
                # A registered LUT may already have been converted by a later
                # object in the traversal; parameters are processed separately.
                if not params.get('lut_id'):
                    for key in ('path', 'file', 'lut'):
                        raw = params.get(key)
                        if isinstance(raw, str) and raw and raw not in self.files:
                            relative, entry = self.file(raw, role='lut')
                            self.rights_for_file(entry, 'lut')
                            params[key] = relative


def prepare_save(root: Path, project: dict, ledger: dict, request: dict, *, max_bytes=DEFAULT_MAX_BYTES):
    allowed = {'id', 'version', 'name', 'tags', 'sequence_id', 'clip_ids'}
    if not isinstance(request, dict) or set(request)-allowed:
        fail('FRAGMENT_REQUEST_INVALID', '保存请求包含未知字段')
    gid = _id(request.get('id'))
    version = _int(request.get('version'), 'version', 1)
    name = request.get('name', gid)
    tags = request.get('tags', [])
    if not isinstance(name, str) or not name.strip() or len(name) > 256 or not isinstance(tags, list) or len(tags) > 64 or any(not isinstance(t, str) or not t or len(t) > 128 for t in tags):
        fail('FRAGMENT_REQUEST_INVALID', '名称或标签格式无效')
    context = _runtime_context(project['settings'])
    source = find_sequence(project, _id(request.get('sequence_id'), 'sequence_id'))
    selected, original, expanded = _selection(project, source, request.get('clip_ids'))
    group = copy.deepcopy(source)
    for track in group['tracks']:
        track['clips'] = [c for c in track['clips'] if c['id'] in selected]
    group['source_transitions'] = [tr for tr in group.get('source_transitions', []) if tr['from_clip_id'] in selected]
    clips = [c for t in group['tracks'] for c in t['clips']]
    origin = min(c['timeline_start_tick'] for c in clips)
    end = max(c['timeline_start_tick']+c['duration_tick'] for c in clips)
    # Keep the full author duration for source handles and markers. The entry
    # container selects origin..end without changing any author clock.
    sequences = [group]
    included = {group['id']}
    pending = [c['sequence_id'] for c in clips if c.get('sequence_id')]
    while pending:
        sid = pending.pop()
        if sid in included:
            continue
        child = copy.deepcopy(find_sequence(project, sid))
        included.add(sid)
        sequences.append(child)
        pending.extend(c['sequence_id'] for t in child['tracks'] for c in t['clips'] if c.get('sequence_id'))
    for sequence in sequences:
        sequence['canvas'] = sequence_canvas(project, sequence)
    collector = Collector(root, project, ledger, max_bytes)
    collector.resources(sequences)
    for seq in sequences:
        for track in seq['tracks']:
            for clip in track['clips']:
                if isinstance(clip.get('subtitle'), dict):
                    style = clip['subtitle'].get('style') or {}
                    if not style.get('fontfile') and not style.get('font_asset_id'):
                        collector.warnings.append({'code': 'FRAGMENT_SYSTEM_FONT_CONTEXT', 'clip_id': clip['id'],
                            'message': '未固定字体文件；另一机器的字体回退可能改变字形与布局'})
    assets = []
    done = set()
    while collector.asset_ids-done:
        for aid in sorted(collector.asset_ids-done):
            done.add(aid)
            asset = copy.deepcopy(collector.assets[aid])
            collector.resources(asset)
            relative, entry = collector.file(asset['uri'], expected=asset.get('sha256'), role='asset')
            if not asset.get('sha256'):
                fail('FRAGMENT_RESOURCE_HASH_MISSING', '保存资产必须具有明确的登记摘要', aid)
            asset['uri'] = relative
            # Proxies are caches, not the authoritative edited media. Keep their
            # original metadata only in the source snapshot, not executable URIs.
            for key in ('proxy_uri', 'thumbnail_uri', 'waveform_uri'):
                asset.pop(key, None)
            assets.append(asset)
    # Transitive rights-only records (including model provenance) do not imply
    # that executable adapters or model weights should be copied or executed.
    rights_done = set()
    while collector.rights_ids-rights_done:
        for aid in sorted(collector.rights_ids-rights_done):
            rights_done.add(aid)
            record = collector.records.get(aid)
            if not record:
                fail('FRAGMENT_RIGHTS_MISSING', '片段组权利依赖缺失: '+aid, 'rights_ref')
            for historical in ledger.get('records', []):
                if historical.get('asset_id') != aid:
                    continue
                parents = historical.get('derived_from', [])
                if isinstance(parents, str):
                    parents = [parents]
                if not isinstance(parents, list) or any(not isinstance(p, str) or not p for p in parents):
                    fail('FRAGMENT_RIGHTS_INVALID', '权利 derived_from 无效', aid)
                collector.rights_ids.update(parents)
            for decision in ledger.get('decisions', []):
                if decision.get('asset_id') == aid and decision.get('replacement_asset_id'):
                    collector.rights_ids.add(decision['replacement_asset_id'])
    # Attach every non-asset right to an entry clip, so release gates traverse
    # LUT/font/model dependencies even when no source asset was registered.
    dependencies = clips[0].setdefault('rights_dependencies', [])
    for aid in sorted(collector.rights_ids):
        record = collector.records[aid]
        sha = record.get('sha256')
        if HASH_RE.fullmatch(str(sha)) and not any(d.get('rights_ref') == aid for d in dependencies):
            dependencies.append({'rights_ref': aid, 'sha256': sha})
    saved_ledger = copy.deepcopy(ledger)
    for field in ('records', 'events', 'decisions'):
        saved_ledger[field] = [r for r in saved_ledger.get(field, []) if r.get('asset_id') in collector.rights_ids]
    # Evidence files are supporting data, not code. Missing historical labels
    # remain explicit; this operation never upgrades their verification state.
    for record in saved_ledger['records']:
        def evidence(value):
            if isinstance(value, str):
                if not value:
                    return value
                if reference_kind(value) in {'remote', 'provider'}:
                    fail('FRAGMENT_REMOTE_REFERENCE', '权利证据不能使用远程引用', 'evidence')
                path = resolve_local_path(root, value, field='rights.evidence')
                if path.is_file():
                    return collector.file(value, role='evidence')[0]
                collector.warnings.append({'code': 'FRAGMENT_HISTORICAL_EVIDENCE_UNAVAILABLE', 'asset_id': record.get('asset_id'), 'reference': value})
                return value
            if isinstance(value, list):
                return [evidence(v) for v in value]
            if isinstance(value, dict):
                return {k: evidence(v) if k in {'path', 'uri', 'reference'} else v for k, v in value.items()}
            return value
        if 'evidence' in record:
            record['evidence'] = evidence(record['evidence'])
    fragment_project = {'schema_version': project['schema_version'], 'project': copy.deepcopy(project['project']),
                        'settings': copy.deepcopy(project['settings']), 'sequences': sequences, 'assets': assets,
                        'templates': [], 'outputs': [], 'provenance': {'change_log': []}}
    payload = {'fragment_version': VERSION, 'engine': ENGINE, 'id': gid, 'version': version, 'name': name,
               'tags': sorted(set(tags)), 'source': {'project_id': project['project']['id'],
                   'project_sha256': project_fingerprint(project), 'rights_sha256': digest(ledger)},
               'entry': {'sequence_id': group['id'], 'origin_tick': origin, 'duration_tick': end-origin},
               'selection': {'requested': original, 'included': sorted(selected), 'expanded': expanded},
               'context': context, 'project': fragment_project, 'rights_ledger': saved_ledger,
               'files': sorted(collector.files.values(), key=lambda x: x['path']),
               'adaptations': collector.adaptations, 'warnings': collector.warnings}
    if len(json_bytes(payload)) > MAX_MANIFEST:
        fail('FRAGMENT_MANIFEST_TOO_LARGE', '片段组元数据超过 32 MiB')
    return payload, collector.sources


def save(library: Path, payload: dict, sources: dict[str, Path]) -> dict:
    destination = entry_path(library, payload['id'], payload['version'])
    with _native_byte_lock(library/'fragment-write.lock', timeout=0.0,
                          error_code='FRAGMENT_LIBRARY_LOCKED', message='片段组库正被其他保存操作使用'):
        if destination.exists():
            fail('FRAGMENT_VERSION_EXISTS', '片段组版本已存在；请使用新版本号', str(destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.fragment-', dir=destination.parent))
        try:
            for item in payload['files']:
                target = stage/item['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(sources[item['path']], target)
                if target.stat().st_size != item['bytes'] or 'sha256:'+sha256_file(target) != item['sha256']:
                    fail('FRAGMENT_COPY_CHANGED', '复制资源与已核对摘要不符', str(target))
            (stage/'fragment.json').write_bytes(json_bytes(payload))
            os.rename(stage, destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return {'path': str(destination/'fragment.json'), 'fragment_sha256': digest(payload),
            'files': len(payload['files']), 'bytes': sum(i['bytes'] for i in payload['files'])}


def _relative(value: str) -> str:
    if not isinstance(value, str) or '\\' in value or ':' in value:
        fail('FRAGMENT_PATH_INVALID', '资源路径必须为版本内 POSIX 相对路径')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or '.' in p.parts or len(p.parts) != 2 or p.parts[0] != 'files' or p.as_posix() != value:
        fail('FRAGMENT_PATH_INVALID', '资源路径越界或不规范', value)
    return value


def inspect(library: Path, group_id: str, version: int, *, max_bytes=DEFAULT_MAX_BYTES):
    root = entry_path(library, group_id, version)
    path = root/'fragment.json'
    if not path.is_file():
        fail('FRAGMENT_NOT_FOUND', '本地片段组版本不存在', str(path))
    if path.stat().st_size > MAX_MANIFEST:
        fail('FRAGMENT_MANIFEST_TOO_LARGE', '片段组元数据超过 32 MiB')
    artifact_entry(path, 'fragment-manifest')
    payload = load_json(path)
    if payload.get('fragment_version') != VERSION or payload.get('engine') != ENGINE or payload.get('id') != group_id or payload.get('version') != version:
        fail('FRAGMENT_MANIFEST_INVALID', '片段组格式、ID 或版本不符')
    files = payload.get('files')
    if not isinstance(files, list) or len(files) > MAX_FILES:
        fail('FRAGMENT_MANIFEST_INVALID', '片段组文件清单无效')
    total, seen = 0, set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {'path', 'sha256', 'bytes'}:
            fail('FRAGMENT_MANIFEST_INVALID', '资源清单字段无效')
        relative = _relative(item['path'])
        if relative in seen or type(item['bytes']) is not int or item['bytes'] <= 0 or not HASH_RE.fullmatch(str(item['sha256'])):
            fail('FRAGMENT_MANIFEST_INVALID', '资源清单重复或大小/摘要无效')
        seen.add(relative)
        total += item['bytes']
        if total > byte_budget(max_bytes):
            fail('FRAGMENT_BUDGET_EXCEEDED', '片段组超过资源字节上限')
        resource = root/relative
        if not resource.resolve().is_relative_to(root.resolve()):
            fail('FRAGMENT_PATH_INVALID', '片段组资源解析后越出版本目录', relative)
        entry = artifact_entry(resource, 'fragment-resource')
        if entry['sha256'] != item['sha256'] or entry['bytes'] != item['bytes']:
            fail('FRAGMENT_RESOURCE_HASH_MISMATCH', '片段组资源已损坏或改变', relative)
    project = payload.get('project')
    if not isinstance(project, dict) or not isinstance(payload.get('rights_ledger'), dict):
        fail('FRAGMENT_MANIFEST_INVALID', '缺少工程或权利快照')
    if _runtime_context(project['settings']) != payload.get('context'):
        fail('FRAGMENT_CONTEXT_INVALID', '片段组执行上下文与快照不符')
    # All executable resource fields must be listed and confined. Historical
    # source_url/evidence descriptions are metadata, not execution entrypoints.
    def resource_ref(value):
        if value not in seen:
            fail('FRAGMENT_RESOURCE_UNLISTED', '运行时依赖不在资源清单中', str(value))
    for asset in project.get('assets', []):
        resource_ref(asset.get('uri'))
        actual = next(i for i in files if i['path'] == asset['uri'])
        if actual['sha256'] != asset.get('sha256'):
            fail('FRAGMENT_RESOURCE_HASH_MISMATCH', '资产声明摘要与文件清单不符', asset.get('id', 'asset'))
    for obj in _walk(project['sequences']):
        for key in ('asset_uri', 'fontfile'):
            if obj.get(key):
                resource_ref(obj[key])
        if obj.get('lut_id'):
            fail('FRAGMENT_REFERENCE_UNSUPPORTED', '便携片段组不得保留外部 LUT ID')
        if str(obj.get('type', '')).lower().replace('-', '_') in {'lut', 'lut3d'}:
            params = obj.get('parameters') if isinstance(obj.get('parameters'), dict) else obj
            for key in ('path', 'file', 'lut'):
                if params.get(key):
                    resource_ref(params[key])
    entry = payload.get('entry', {})
    sequence = find_sequence(project, _id(entry.get('sequence_id'), 'entry.sequence_id'))
    origin = _int(entry.get('origin_tick'), 'entry.origin_tick')
    duration = _int(entry.get('duration_tick'), 'entry.duration_tick', 1)
    if origin+duration > sequence['duration_tick']:
        fail('FRAGMENT_MANIFEST_INVALID', '入口范围超出保存序列')
    from .validator import validate_project
    validation = validate_project(root, project, strict_rights=False)
    # Validator reads rights-ledger.json from disk; snapshot rights are checked
    # separately below without creating any file during inspection or dry-run.
    semantic = [e for e in validation['errors'] if not str(e.get('code', '')).startswith('RIGHTS_')]
    if semantic:
        fail('FRAGMENT_PROJECT_INVALID', json.dumps(semantic, ensure_ascii=False))
    rights = check_project_rights(project, payload['rights_ledger'], strict=True)
    missing = [f for f in rights.get('failures', []) if f.get('code') in {'RIGHTS_RECORD_MISSING', 'RIGHTS_HASH_MISMATCH', 'RIGHTS_TEMPLATE_DEPENDENCY_MISSING'}]
    if missing:
        fail('FRAGMENT_RIGHTS_INVALID', json.dumps(missing, ensure_ascii=False))
    return payload, {'path': str(path), 'fragment_sha256': 'sha256:'+sha256_file(path),
                     'files': len(files), 'bytes': total, 'validation': {'ok': True, 'warnings': validation.get('warnings', [])},
                     'rights': rights}


def list_fragments(library: Path, query: str = '') -> list[dict]:
    result = []
    if not library.exists():
        return result
    query = query.casefold().strip()
    for path in sorted((library/'entries').glob('*/*/fragment.json')):
        # A staged manifest is not published until the version directory is
        # atomically renamed. Interrupted saves must stay invisible to readers.
        if path.parent.name.startswith('.fragment-'):
            continue
        if not path.resolve().is_relative_to(library.resolve()) or path.stat().st_size > MAX_MANIFEST:
            fail('FRAGMENT_PATH_INVALID', '库清单越界或过大', str(path))
        payload = load_json(path)
        if payload.get('fragment_version') != VERSION:
            fail('FRAGMENT_MANIFEST_INVALID', '库清单版本不支持', str(path))
        if query and query not in ' '.join([str(payload.get('id', '')), str(payload.get('name', '')), *payload.get('tags', [])]).casefold():
            continue
        if path.parent != entry_path(library, payload['id'], payload['version']):
            fail('FRAGMENT_MANIFEST_INVALID', '库目录与声明 ID/版本不符', str(path))
        result.append({k: copy.deepcopy(payload.get(k)) for k in ('id', 'version', 'name', 'tags', 'entry', 'source')})
        result[-1].update(fragment_sha256='sha256:'+sha256_file(path), resources_verified=False)
    return result


REF_KIND = {'sequence_id': 'sequence', 'source_sequence_id': 'sequence',
            'track_id': 'track', 'source_track_id': 'track', 'target_track_id': 'track', 'main_track_id': 'track',
            'clip_id': 'clip', 'source_clip_id': 'clip', 'target_clip_id': 'clip', 'from_clip_id': 'clip', 'to_clip_id': 'clip',
            'link_id': 'link', 'rights_ref': 'right', 'record_id': 'record', 'previous_record_id': 'record',
            'event_id': 'event', 'decision_id': 'decision'}


def _mapped_id(instance, kind, original):
    return 'fg_'+hashlib.sha256(f'{instance}\n{kind}\n{original}'.encode('utf-8')).hexdigest()[:40]


def prepare_apply(project: dict, ledger: dict, payload: dict, info: dict, request: dict):
    fields = {'id', 'version', 'sequence_id', 'track_id', 'at_tick', 'instance_id'}
    if not isinstance(request, dict) or set(request)-fields:
        fail('FRAGMENT_REQUEST_INVALID', '插入请求包含未知字段')
    if request.get('id') != payload['id'] or request.get('version') != payload['version']:
        fail('FRAGMENT_REQUEST_INVALID', '请求片段组与已核对清单不符')
    sequence = find_sequence(project, _id(request.get('sequence_id'), 'sequence_id'))
    track = find_track(sequence, _id(request.get('track_id'), 'track_id'))
    start = _int(request.get('at_tick'), 'at_tick')
    if track.get('locked') or track.get('kind') != 'video':
        fail('FRAGMENT_TARGET_TRACK_INVALID', '插入目标必须为未锁定的视频轨道', 'track_id')
    if _runtime_context(project['settings']) != payload['context']:
        fail('FRAGMENT_CONTEXT_MISMATCH', '源与目标的时基/帧率/色彩/音频执行设置不同，首版不做隐式转换', 'settings')
    if project['settings']['canvas'].get('pixel_aspect', {'num': 1, 'den': 1}) != payload['project']['settings']['canvas'].get('pixel_aspect', {'num': 1, 'den': 1}):
        fail('FRAGMENT_CONTEXT_MISMATCH', '源与目标像素宽高比不同', 'settings.canvas.pixel_aspect')
    duration = payload['entry']['duration_tick']
    if any(start < c['timeline_start_tick']+c['duration_tick'] and start+duration > c['timeline_start_tick'] for c in track['clips']):
        fail('FRAGMENT_TARGET_COLLISION', '插入区间与目标轨道已有片段重叠')
    instance = _id(request.get('instance_id', 'group_'+digest({'project': project_fingerprint(project), 'fragment': info['fragment_sha256'], 'request': request})[7:31]), 'instance_id')
    maps: dict[str, dict[str, str]] = {k: {} for k in ('sequence', 'track', 'clip', 'asset', 'right', 'link', 'transition', 'marker', 'record', 'event', 'decision')}
    source_project = payload['project']
    for asset in source_project['assets']:
        maps['asset'][asset['id']] = _mapped_id(instance, 'asset', asset['id'])
    for seq in source_project['sequences']:
        maps['sequence'][seq['id']] = _mapped_id(instance, 'sequence', seq['id'])
        for t in seq['tracks']:
            maps['track'][t['id']] = _mapped_id(instance, 'track', t['id'])
            for c in t['clips']:
                maps['clip'][c['id']] = _mapped_id(instance, 'clip', c['id'])
                if c.get('link_id'):
                    maps['link'][c['link_id']] = _mapped_id(instance, 'link', c['link_id'])
        for kind, field in (('transition', 'source_transitions'), ('marker', 'markers')):
            for item in seq.get(field, []):
                if item.get('id'):
                    maps[kind][item['id']] = _mapped_id(instance, kind, item['id'])
    saved_ledger = payload['rights_ledger']
    for record in saved_ledger.get('records', []):
        aid = record['asset_id']
        maps['right'][aid] = maps['asset'].get(aid, _mapped_id(instance, 'right', aid))
    for field, key, kind in (('records', 'record_id', 'record'), ('events', 'event_id', 'event'), ('decisions', 'decision_id', 'decision')):
        for item in saved_ledger.get(field, []):
            if item.get(key):
                maps[kind][item[key]] = _mapped_id(instance, kind, item[key])
    base = 'assets/fragments/'+hashlib.sha256(instance.encode('utf-8')).hexdigest()[:40]
    file_map = {item['path']: base+'/'+item['path'] for item in payload['files']}

    def ref(kind, value, key):
        if value is None:
            return value
        if value not in maps[kind]:
            fail('FRAGMENT_REFERENCE_MISSING', '待插入内容引用闭包之外的 ID: '+str(value), key)
        return maps[kind][value]

    def rewrite(value, *, history=False):
        if isinstance(value, list):
            return [rewrite(v, history=history) for v in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, child in value.items():
            if (key == 'asset_id' or key.endswith('_asset_id')) and isinstance(child, str):
                kind = 'right' if history else 'asset'
                # Historical replacement references are rights-only metadata.
                result[key] = ref(kind, child, key)
            elif key in REF_KIND and isinstance(child, str):
                result[key] = ref(REF_KIND[key], child, key)
            elif history and key in {'supersedes', 'superseded_by'} and child:
                kind = 'decision' if value.get('decision_id') else 'record'
                result[key] = ref(kind, child, key)
            elif history and key == 'derived_from':
                result[key] = [ref('right', v, key) for v in child] if isinstance(child, list) else ref('right', child, key) if child else child
            elif history and key == 'evidence':
                def evidence_paths(v):
                    if isinstance(v, str):
                        return file_map.get(v, v)
                    if isinstance(v, list):
                        return [evidence_paths(i) for i in v]
                    if isinstance(v, dict):
                        return {k: evidence_paths(i) if k in {'path', 'uri', 'reference'} else i for k, i in v.items()}
                    return v
                result[key] = evidence_paths(child)
            elif key in {'uri', 'asset_uri', 'fontfile', 'path', 'file', 'lut'} and isinstance(child, str) and child in file_map:
                result[key] = file_map[child]
            elif key.endswith(('_clip_id', '_track_id', '_sequence_id')) and child is not None:
                fail('FRAGMENT_REFERENCE_UNSUPPORTED', '尚不支持的 ID 引用字段', key)
            else:
                result[key] = rewrite(child, history=history)
        return result

    imported = rewrite(source_project)
    for a in imported['assets']:
        a['id'] = maps['asset'][a['id']]
    original_assets = {a['id']: a for a in source_project['assets']}
    for original, asset in zip(source_project['assets'], imported['assets'], strict=True):
        source = original.get('source') or {}
        if source.get('speech_enhancement') is not None:
            from .enhancement_plan import rebind_recipe
            asset['source']['speech_enhancement'] = rebind_recipe(source['speech_enhancement'], mapping=maps['asset'], asset=original, assets=original_assets)
            asset['source']['derived_from'] = [maps['asset'][v] for v in source['derived_from']]
        if source.get('interpolation') is not None:
            from .interpolation_plan import rebind_recipe
            asset['source']['interpolation'] = rebind_recipe(source['interpolation'], mapping=maps['asset'], asset=original, assets=original_assets)
            asset['source']['derived_from'] = [maps['asset'][v] for v in source['derived_from']]
        if source.get('lipsync') is not None:
            from .lipsync_plan import rebind_recipe
            asset['source']['lipsync'] = rebind_recipe(source['lipsync'], mapping=maps['asset'], asset=original, assets=original_assets)
            asset['source']['derived_from'] = [maps['asset'][v] for v in source['derived_from']]
        if source.get('outpainting') is not None:
            from .local_outpainting import rebind_recipe
            asset['source']['outpainting'] = rebind_recipe(source['outpainting'],
                source_asset_id=maps['asset'][source['outpainting']['source_asset_id']],
                asset=original, assets=original_assets)
            asset['source']['derived_from'] = [maps['asset'][v] for v in source['derived_from']]
        if source.get('video_generation') is not None:
            from .video_generation import rebind_recipe
            asset['source']['video_generation'] = rebind_recipe(source['video_generation'],
                mapping=maps['asset'], asset=original, assets=original_assets)
            asset['source']['derived_from'] = [maps['asset'][v] for v in source['derived_from']]
    for s in imported['sequences']:
        s['id'] = maps['sequence'][s['id']]
        for t in s['tracks']:
            t['id'] = maps['track'][t['id']]
            for c in t['clips']:
                c['id'] = maps['clip'][c['id']]
        for kind, field in (('transition', 'source_transitions'), ('marker', 'markers')):
            for item in s.get(field, []):
                if item.get('id'):
                    item['id'] = maps[kind][item['id']]
    candidate = copy.deepcopy(project)
    target = find_sequence(candidate, sequence['id'])
    target_track = find_track(target, track['id'])
    wrapper = {'id': _mapped_id(instance, 'entry', 'clip'), 'sequence_id': maps['sequence'][payload['entry']['sequence_id']],
               'timeline_start_tick': start, 'duration_tick': duration, 'source_in_tick': payload['entry']['origin_tick'],
               'source_out_tick': payload['entry']['origin_tick']+duration,
               'extensions': {'fragment': {'id': payload['id'], 'version': payload['version'], 'instance_id': instance,
                   'fragment_sha256': info['fragment_sha256'], 'source': copy.deepcopy(payload['source'])}}}
    occupied = {o['id'] for o in _walk(project) if isinstance(o.get('id'), str)}
    occupied.update(r.get('asset_id') for r in ledger.get('records', []))
    occupied.update(r.get('record_id') for r in ledger.get('records', []))
    new_ids = {v for m in maps.values() for v in m.values()} | {wrapper['id']}
    if occupied & new_ids:
        fail('FRAGMENT_INSTANCE_EXISTS', '实例 ID 已使用或生成 ID 与目标冲突', 'instance_id')
    target_track['clips'].append(wrapper)
    target_track['clips'].sort(key=lambda c: (c['timeline_start_tick'], c['id']))
    target['duration_tick'] = max(target['duration_tick'], start+duration)
    candidate['assets'].extend(imported['assets'])
    candidate['sequences'].extend(imported['sequences'])
    candidate_ledger = copy.deepcopy(ledger)
    cloned_history = rewrite(saved_ledger, history=True)
    for field in ('records', 'events', 'decisions'):
        candidate_ledger.setdefault(field, []).extend(cloned_history.get(field, []))
    rights = check_project_rights(candidate, candidate_ledger, strict=True)
    plan = {'engine': ENGINE, 'project_sha256': project_fingerprint(project), 'fragment_sha256': info['fragment_sha256'],
            'instance_id': instance, 'sequence_id': sequence['id'], 'track_id': track['id'], 'entry_clip': wrapper,
            'source_entry': copy.deepcopy(payload['entry']), 'selection': copy.deepcopy(payload['selection']),
            'id_maps': maps, 'resource_directory': base, 'files': copy.deepcopy(payload['files']),
            'bytes': info['bytes'], 'rights': rights, 'adaptations': copy.deepcopy(payload.get('adaptations', [])),
            'limits': ['native_nested_group_not_expanded_lanes', 'same_execution_context_required',
                'source_rights_changes_do_not_automatically_propagate', 'crash_may_leave_unreferenced_resources']}
    return candidate, candidate_ledger, plan


def copy_resources(project_root: Path, entry_root: Path, plan: dict) -> Path:
    destination = project_root/plan['resource_directory']
    if not destination.resolve().is_relative_to(project_root.resolve()/'assets'/'fragments'):
        fail('FRAGMENT_PATH_INVALID', '实例资源目录越界')
    if destination.exists():
        fail('FRAGMENT_INSTANCE_EXISTS', '实例资源目录已存在', str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.fragment-', dir=destination.parent))
    try:
        for item in plan['files']:
            relative = _relative(item['path'])
            target = stage/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry_root/relative, target)
            if target.stat().st_size != item['bytes'] or 'sha256:'+sha256_file(target) != item['sha256']:
                fail('FRAGMENT_COPY_CHANGED', '插入资源复制时改变', relative)
        os.rename(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination
