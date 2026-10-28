"""Opt-in reuse of committed outputs within one serial queue invocation.

Batch planning is inspired by OpenFilm exports.mjs startAll/cloneOf at
71922644da5d6b67db2cc796d4e057f98999944f (MIT). This implementation uses
deep content snapshots, independent target verification and fresh provenance.
Copyright (c) 2026 OpenFilm contributors. See OPENFILM_LICENSE.txt.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from .errors import AppError
from .hardware_acceleration import configuration as hardware_configuration
from .projection_opencl import configuration as projection_configuration
from .lut_library import resolve_lut_path
from .media import ffmpeg_path, ffprobe_path, probe_media
from .policy import resolve_local_path
from .project import ledger_file, project_file
from .quality import check_output
from .render import render_fingerprints
from .sequence_sampling import configuration as sampling_configuration
from .utils import atomic_write_json, ensure_inside, load_json, new_id, now_iso

PROTOCOL = 'agent-video-queue-reuse-v1'
CHUNK_BYTES = 1024 * 1024
MAX_FILES = 4096
SELF_CONTAINED_FORMATS = {
    'mov', 'mp4', 'm4a', '3gp', '3g2', 'mj2', 'matroska', 'webm', 'avi',
    'wav', 'flac', 'mp3', 'ogg', 'aac', 'nut', 'mpegts', 'mpeg', 'mxf',
    'png_pipe', 'jpeg_pipe', 'webp_pipe', 'bmp_pipe', 'tiff_pipe', 'gif',
    'apng', 'image2', 'image2pipe',
}


def _error(code: str, message: str, path: Any = None) -> AppError:
    return AppError(code, message, exit_code=6, path=str(path) if path else None)


def _cancel(marker: Path | None) -> None:
    if marker is not None and marker.exists():
        raise AppError('CANCELLED', '同批次结果复用收到取消请求', exit_code=8, path=str(marker))


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as exc:
        raise _error('QUEUE_REUSE_SNAPSHOT_INVALID', '复用快照必须是有限值的 JSON') from exc


def file_entry(path: Path, marker: Path | None = None, *, allow_empty: bool = False) -> dict:
    path = path.resolve()
    digest, size = hashlib.sha256(), 0
    try:
        with path.open('rb') as stream:
            while True:
                _cancel(marker)
                chunk = stream.read(CHUNK_BYTES)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
        _cancel(marker)
        if not size and not allow_empty:
            raise _error('QUEUE_REUSE_INPUT_EMPTY', '复用依赖不得为空', path)
        return {'path': str(path), 'sha256': digest.hexdigest(), 'bytes': size}
    except OSError as exc:
        raise _error('QUEUE_REUSE_INPUT_UNREADABLE', '不能完整读取复用依赖', path) from exc


def author_payload(project: dict, sequence: dict, settings: dict) -> dict:
    value = copy.deepcopy(project)
    value.pop('outputs', None)
    value.get('provenance', {}).pop('change_log', None)
    value.get('project', {}).pop('updated_at', None)
    value['settings'] = copy.deepcopy(settings)
    value['settings']['acceleration'] = hardware_configuration(settings.get('acceleration'))
    value['settings']['sequence_sampling'] = sampling_configuration(settings.get('sequence_sampling'))
    if value['settings'].get('audio_stretch') is None:
        value['settings'].pop('audio_stretch', None)
    return {'project': value, 'sequence_id': sequence['id']}


def _objects(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from _objects(item)


def _probe_input_format(path: Path) -> str:
    return str(probe_media(path).get('format', ''))


def _dependency_paths(root: Path, project: dict, settings: dict) -> set[Path]:
    hw = hardware_configuration(settings.get('acceleration'))
    projection=projection_configuration(settings.get('projection_acceleration'))
    if (hw['encode'] != 'off' or hw['decode'] != 'off' or projection['mode'] != 'off'
            or settings.get('audio_stretch') is not None):
        raise _error('QUEUE_REUSE_UNSUPPORTED', '逐作业硬件/投影探测或外部音频伸缩尚不支持结果复用')
    paths: set[Path] = set()
    from .aces_pipeline import dependency_paths
    paths.update(dependency_paths(settings.get('pixel_pipeline')))
    if settings.get('pixel_pipeline') is not None:
        from .float_preview import runtime_paths
        paths.update(p for p in runtime_paths() if p.stat().st_size>0)
    assets = {a['id']: a for a in project.get('assets', [])}
    for asset in assets.values():
        if not asset.get('uri'):
            raise _error('QUEUE_REUSE_UNSUPPORTED', '复用要求全部资产有实际本地文件', asset.get('id'))
        path = resolve_local_path(root, asset['uri'], field='queue.reuse.asset')
        if asset.get('kind') in {'video', 'audio', 'image'}:
            formats = set(str(asset.get('probe', {}).get('format', '')).split(','))
            if not formats or not formats <= SELF_CONTAINED_FORMATS:
                raise _error('QUEUE_REUSE_UNSUPPORTED', '复用只接纳已探测的单文件媒体容器', path)
            actual_formats = set(_probe_input_format(path).split(','))
            if not actual_formats or not actual_formats <= SELF_CONTAINED_FORMATS:
                raise _error('QUEUE_REUSE_UNSUPPORTED', '实际探测不是可枚举依赖的单文件容器', path)
        paths.add(path)
    for obj in _objects({'project': project, 'settings': settings}):
        if obj.get('tracking_binding'):
            raise _error('QUEUE_REUSE_UNSUPPORTED', '引用外部跟踪报告的绑定暂不支持复用')
        subtitle = obj.get('subtitle')
        if isinstance(subtitle, dict):
            if subtitle.get('asset_uri'):
                raise _error('QUEUE_REUSE_UNSUPPORTED', '外部字幕的字体回退依赖尚不支持复用')
            if subtitle.get('text') is not None:
                style = subtitle.get('style') or {}
                font_id = style.get('font_asset_id')
                font = assets.get(str(font_id), {}).get('uri') if font_id else style.get('fontfile')
                if not font:
                    raise _error('QUEUE_REUSE_UNSUPPORTED', '内联字幕复用要求显式字体文件或字体资产')
                paths.add(resolve_local_path(root, font, field='queue.reuse.font'))
        name = str(obj.get('type', '')).strip().lower().replace('-', '_')
        if isinstance(obj.get('effects'), list) and any(
                isinstance(item, str) and item.strip().lower().replace('-', '_') in {'noise', 'film_grain'}
                for item in obj['effects']):
            raise _error('QUEUE_REUSE_UNSUPPORTED', '未显式固定随机种子的颗粒不支持复用')
        if name in {'noise', 'film_grain'}:
            raise _error('QUEUE_REUSE_UNSUPPORTED', '未显式固定随机种子的颗粒不支持复用')
        if name in {'lut', 'lut3d', 'cube', 'look'}:
            params = obj.get('parameters') if isinstance(obj.get('parameters'), dict) else obj
            lut_id = params.get('lut_id')
            if lut_id:
                found = resolve_lut_path(root, str(lut_id))
                if found is None:
                    raise _error('QUEUE_REUSE_INPUT_UNREADABLE', 'LUT 登记不存在', lut_id)
                paths.add(found[0])
            else:
                raw = params.get('path', params.get('file', params.get('lut')))
                if not raw:
                    raise _error('QUEUE_REUSE_INPUT_UNREADABLE', 'LUT 没有实际文件')
                paths.add(resolve_local_path(root, raw, field='queue.reuse.lut'))
        for item in obj.values():
            if isinstance(item, str) and ('random(' in item.lower() or item.lower() in {'random', 'bikeshed'}):
                raise _error('QUEUE_REUSE_UNSUPPORTED', '非确定性表达式或颜色不支持复用')
    for sidecar in (ledger_file(root), root / 'assets/lut-library.json'):
        if sidecar.exists():
            paths.add(sidecar)
    return paths


def _runtime_paths() -> set[Path]:
    package = Path(__file__).resolve().parent
    paths = {p for p in package.iterdir() if p.is_file() and p.suffix in {'.py', '.mjs', '.json', '.txt'}}
    paths.add(Path(sys.executable).resolve())
    for tool in (Path(ffmpeg_path()).resolve(), Path(ffprobe_path()).resolve()):
        paths.add(tool)
        paths.update(tool.parent.glob('*.dll'))
    # Explicit-font inline captions may use Pillow/FreeType before FFmpeg.
    import PIL
    pillow = Path(PIL.__file__).resolve().parent
    paths.update(p for p in pillow.rglob('*') if p.is_file() and p.suffix in {'.py', '.pyd', '.dll'})
    for directory in (pillow.parent / 'pillow.libs', Path(sys.executable).parent):
        if directory.is_dir():
            paths.update(directory.glob('*.dll'))
    return paths


def cache_inventory(root: Path, marker: Path | None = None) -> list[dict]:
    directory = root / 'cache'
    paths = sorted(p for p in directory.rglob('*') if p.is_file()) if directory.is_dir() else []
    if len(paths) > MAX_FILES:
        raise _error('QUEUE_REUSE_BUDGET', '复用派生缓存文件数超过 4096')
    # A successful renderer may bind empty derived artifacts, e.g. a continuous
    # native audio index deliberately has no replacement PCM. Their empty SHA
    # and size still form part of the immutable cache inventory. Authored media,
    # runtime executables and committed outputs retain the nonempty gate.
    return [file_entry(ensure_inside(root, p), marker, allow_empty=True) for p in paths]


def check_entries(entries: list[dict], marker: Path | None = None, *, code='QUEUE_REUSE_DERIVED_CHANGED') -> None:
    for expected in entries:
        if file_entry(Path(expected['path']), marker, allow_empty=True) != expected:
            raise _error(code, '已绑定文件的实际字节已变化', expected['path'])


class ReuseSession:
    """A process-local index; never loads prior queue successes as cache."""
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.entries: dict[str, dict] = {}
        self.runtime: list[dict] | None = None
        self.encoded = 0
        self.reused = 0

    def snapshot(self, project: dict, sequence: dict, settings: dict, marker: Path | None = None) -> dict:
        disk_project = load_json(project_file(self.root))
        if author_payload(disk_project, sequence, disk_project['settings']) != author_payload(project, sequence, project['settings']):
            raise _error('QUEUE_REUSE_AUTHOR_CHANGED', '磁盘作者数据与当前持锁项目不一致')
        paths = _dependency_paths(self.root, project, settings)
        runtime_paths = _runtime_paths()
        if len(paths) + len(runtime_paths) > MAX_FILES:
            raise _error('QUEUE_REUSE_BUDGET', '复用依赖文件数超过 4096')
        runtime = [file_entry(p, marker) for p in sorted(runtime_paths)]
        if self.runtime is not None and self.runtime != runtime:
            raise _error('QUEUE_REUSE_RUNTIME_CHANGED', '本次调用中的实现或工具字节已变化')
        self.runtime = runtime
        payload = {'protocol': PROTOCOL, **author_payload(project, sequence, settings),
                   'dependencies': [file_entry(p, marker) for p in sorted(paths)], 'runtime': runtime}
        return {'signature': hashlib.sha256(canonical(payload)).hexdigest(), **payload}

    def unchanged(self, before: dict, project: dict, sequence: dict, settings: dict, marker=None) -> None:
        if self.snapshot(project, sequence, settings, marker) != before:
            raise _error('QUEUE_REUSE_INPUT_CHANGED', '执行期间作者数据、权利或实际依赖字节变化')

    def capture(self, snapshot: dict, result: dict, job_id: str) -> dict:
        source = ensure_inside(self.root, Path(result['path']))
        manifest = ensure_inside(self.root, Path(result['manifest']))
        output_entry, manifest_entry = file_entry(source), file_entry(manifest)
        record = load_json(manifest)
        if (record.get('sha256') != output_entry['sha256'] or record.get('operation_id') != result['operation_id']
                or record.get('output') != str(source) or not record.get('quality', {}).get('ok')):
            raise _error('QUEUE_REUSE_SOURCE_INVALID', '已提交来源 manifest 与成片不一致', manifest)
        derived = cache_inventory(self.root)
        result['reuse'] = {'protocol': PROTOCOL, 'signature': snapshot['signature'],
                           'encoding_executed': True, 'snapshot': copy.deepcopy(snapshot), 'derived_files': derived}
        record['reuse'] = copy.deepcopy(result['reuse'])
        atomic_write_json(manifest, record)
        manifest_entry = file_entry(manifest)
        return {'snapshot': copy.deepcopy(snapshot),
            'result': copy.deepcopy(result), 'job_id': job_id, 'output': output_entry, 'manifest': manifest_entry,
            'derived_files': derived}

    def remember(self, entry: dict) -> None:
        self.entries[entry['snapshot']['signature']] = entry
        self.encoded += 1

    def assert_new_target(self, output: Path) -> None:
        ensure_inside(self.root, output)
        for path in (output, output.with_suffix(output.suffix + '.manifest.json')):
            if path.exists() or path.is_symlink():
                raise _error('QUEUE_REUSE_TARGET_EXISTS', '开启复用时目标及 manifest 必须是新路径', path)

    def clone(self, entry: dict, snapshot: dict, project: dict, sequence: dict, settings: dict,
              output: Path, *, profile=None, marker=None, progress_callback=None) -> dict:
        operation_id = new_id('reuse')
        manifest_path = output.with_suffix(output.suffix + '.manifest.json')
        temporary: Path | None = None
        published = False
        try:
            self.assert_new_target(output)
            self.unchanged(snapshot, project, sequence, settings, marker)
            check_entries(entry['derived_files'], marker)
            for key in ('output', 'manifest'):
                if file_entry(Path(entry[key]['path']), marker) != entry[key]:
                    raise _error('QUEUE_REUSE_SOURCE_CHANGED', '已成功来源成片或 manifest 已变化', entry[key]['path'])
            source_manifest = load_json(Path(entry['manifest']['path']))
            output.parent.mkdir(parents=True, exist_ok=True)
            fd, raw = tempfile.mkstemp(prefix='.queue-reuse-', suffix=output.suffix, dir=output.parent)
            temporary = Path(raw)
            digest = hashlib.sha256()
            with os.fdopen(fd, 'wb') as target, Path(entry['output']['path']).open('rb') as source:
                if progress_callback:
                    progress_callback(operation_id, 'reuse_started', 0.0, '复制本批次已成功的相同结果')
                while True:
                    _cancel(marker)
                    chunk = source.read(CHUNK_BYTES)
                    if not chunk:
                        break
                    target.write(chunk)
                    digest.update(chunk)
                target.flush()
                os.fsync(target.fileno())
            if digest.hexdigest() != entry['output']['sha256']:
                raise _error('QUEUE_REUSE_SOURCE_CHANGED', '来源在复制期间发生变化')
            inspected = probe_media(temporary)
            expected = int(sequence['duration_tick']) / int(settings['timebase']['ticks_per_second'])
            quality = check_output(temporary, settings, expected, run_expensive=False)
            if not quality['ok']:
                raise _error('QUEUE_REUSE_QUALITY_FAILED', '复制产物未通过独立结构核验')
            self.unchanged(snapshot, project, sequence, settings, marker)
            check_entries(entry['derived_files'], marker)
            for key in ('output', 'manifest'):
                if file_entry(Path(entry[key]['path']), marker) != entry[key]:
                    raise _error('QUEUE_REUSE_SOURCE_CHANGED', '来源在复制核验期间变化')
            self.assert_new_target(output)
            _cancel(marker)
            # Native Windows rename fails if another file occupies the target.
            os.rename(temporary, output)
            published = True
            fingerprints = render_fingerprints(project, sequence, settings, self.root)
            reuse = {'protocol': PROTOCOL, 'signature': snapshot['signature'], 'source_job_id': entry['job_id'],
                     'source_operation_id': entry['result']['operation_id'], 'source_output': entry['output'],
                     'source_manifest': entry['manifest'], 'snapshot': snapshot,
                     'source_derived_files': entry['derived_files'],
                     'encoding_executed': False, 'copy_sha256': digest.hexdigest(),
                     'source_encoding_evidence': {'command': source_manifest.get('command'),
                         'acceleration': source_manifest.get('acceleration'),
                         'filter_graph_transport': source_manifest.get('filter_graph_transport')}}
            warnings = copy.deepcopy(entry['result'].get('warnings', [])) + [
                {'code': 'QUEUE_RESULT_REUSED', 'message': '本次复制已完成产物；编码器与设备观测属于来源操作'}]
            acceleration = {'status': 'reused_existing_output', 'executed': False,
                            'source_operation_id': entry['result']['operation_id']}
            result = {'status': 'succeeded', 'operation_id': operation_id, 'path': str(output),
                      'manifest': str(manifest_path), 'filter_graph_transport': {'mode': 'not_executed_copy'},
                      'profile': profile, 'settings': copy.deepcopy(settings), 'delivery': source_manifest.get('delivery', {}),
                      'acceleration': acceleration, 'probe': inspected, 'warnings': warnings,
                      'quality': quality, **fingerprints, 'resume_of': None, 'reuse': reuse}
            manifest = {'manifest_version': '0.1.0', 'operation_id': operation_id,
                        'project_id': project['project']['id'], 'sequence_id': sequence['id'], 'output': str(output),
                        'sha256': digest.hexdigest(), 'command': [], 'inputs': source_manifest.get('inputs', []),
                        'created_at': now_iso(), **{k: v for k, v in result.items() if k not in {'status', 'path', 'manifest'}}}
            atomic_write_json(manifest_path, manifest)
            _cancel(marker)
            if progress_callback:
                progress_callback(operation_id, 'completed', 100.0, '复制及独立核验完成')
            return result
        except BaseException as exc:
            if published:
                output.unlink(missing_ok=True)
                manifest_path.unlink(missing_ok=True)
            if isinstance(exc, AppError):
                exc.operation_id = operation_id
                raise
            if isinstance(exc, OSError):
                raise _error('QUEUE_REUSE_COPY_FAILED', '复制或发布本地成片失败', output) from exc
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
