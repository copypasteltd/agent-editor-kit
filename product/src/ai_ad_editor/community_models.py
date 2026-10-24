"""Verify pinned optional offline packs before starting an isolated CPU worker."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import AppError, argument_error
from .policy import require_local_reference
from .utils import atomic_write_json, ensure_inside, new_id, run_process, sha256_file

PROTOCOL = 'agent-community-cpu-v1'


def pack_catalog() -> dict[str, Any]:
    path = Path(__file__).with_name('material_data') / 'model-packs.json'
    if not path.is_file():
        raise AppError('MODEL_PACK_CATALOG_MISSING', '安装包缺少离线模型包锁定清单', exit_code=10)
    return json.loads(path.read_text('utf-8'))


def verify_pack(value: str, pack_id: str) -> tuple[Path, dict[str, Any]]:
    require_local_reference(value, field='pack')
    root = Path(value).expanduser().resolve()
    lock = next((r for r in pack_catalog()['packs'] if r['id'] == pack_id), None)
    if not lock:
        raise argument_error('没有受支持的离线模型包 ID', 'pack_id')
    path = root / 'manifest.json'
    if not path.is_file() or sha256_file(path) != lock['manifest_sha256']:
        raise AppError('MODEL_PACK_MANIFEST_MISMATCH', '离线模型包清单缺失或摘要与本版锁定值不符', exit_code=10, path=str(path))
    manifest = json.loads(path.read_text('utf-8'))
    if manifest.get('id') != pack_id or manifest.get('protocol') != PROTOCOL:
        raise AppError('MODEL_PACK_INVALID', '离线模型包协议或 ID 不符', exit_code=10)
    if (sys.implementation.name != 'cpython' or sys.version_info[:2] != (3, 13)
            or sys.platform != 'win32' or platform.machine().lower() not in {'amd64', 'x86_64'}):
        raise AppError('MODEL_PACK_ABI_MISMATCH', '此模型包需要原生 CPython 3.13 Windows x64', exit_code=10)
    expected = {}
    for row in manifest['files']:
        relative = PurePosixPath(row['path'])
        if relative.is_absolute() or not relative.parts or any(p in {'..', '.'} for p in relative.parts) or '\\' in row['path'] or ':' in row['path']:
            raise AppError('MODEL_PACK_PATH_INVALID', '模型包文件路径无效', exit_code=10)
        key = row['path'].casefold()
        if key in expected:
            raise AppError('MODEL_PACK_PATH_INVALID', '模型包出现重复路径', exit_code=10)
        expected[key] = row
        target = ensure_inside(root, root / relative)
        if not target.is_file() or target.stat().st_size != row['bytes'] or sha256_file(target) != row['sha256']:
            raise AppError('MODEL_PACK_FILE_MISMATCH', '离线模型包文件缺失或被修改', exit_code=10, path=str(target))
    actual = {p.relative_to(root).as_posix().casefold() for p in root.rglob('*') if p.is_file()}
    if actual != set(expected) | {'manifest.json'}:
        raise AppError('MODEL_PACK_EXTRA_FILES', '模型包包含未锁定文件；请使用完整原包', exit_code=10)
    return root, manifest


def infer(root: Path, *, pack: str, pack_id: str, task: str, payload: dict[str, Any],
          dry_run: bool = False, timeout: float = 1800) -> dict[str, Any]:
    pack_root, manifest = verify_pack(pack, pack_id)
    summary = {'id': pack_id, 'manifest_sha256': sha256_file(pack_root / 'manifest.json'),
               'verified_files': len(manifest['files']), 'engine': manifest['engine'], 'provider': payload.get('device', 'cpu')}
    if dry_run:
        return {'pack': summary, 'task': task, 'network': 'disabled', 'model_inference': False}
    operation = new_id('community_model')
    request = ensure_inside(root, root / 'validation' / (operation + '-request.json'))
    response = request.with_name(operation + '-response.json')
    base_site = Path(__file__).resolve().parent.parent
    body = dict(protocol=PROTOCOL, task=task, pack=str(pack_root), base_site=str(base_site),
                payload=payload, response=str(response))
    atomic_write_json(request, body)
    worker = Path(__file__).with_name('community_worker.py')
    result = run_process([sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(worker), str(request)],
                         cwd=pack_root, timeout=timeout)
    log = request.with_name(operation + '-worker.txt')
    log.write_text(result.stdout[-8000:] + '\n' + result.stderr[-8000:], encoding='utf-8')
    if result.returncode or not response.is_file():
        raise AppError('COMMUNITY_MODEL_FAILED', '本地 CPU 模型推理失败', exit_code=6,
                       cause=result.stderr[-4000:], path=str(log))
    data = json.loads(response.read_text('utf-8'))
    if data.get('protocol') != PROTOCOL or data.get('task') != task or not data.get('ok'):
        raise AppError('COMMUNITY_MODEL_RESPONSE_INVALID', '模型响应协议或状态无效', exit_code=6)
    return {**data, 'pack': summary, 'request': str(request), 'response': str(response), 'worker_log': str(log)}
