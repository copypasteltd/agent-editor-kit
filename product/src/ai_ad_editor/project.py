from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import ENGINE_ID, SCHEMA_VERSION, VERSION
from .errors import AppError, argument_error
from .utils import atomic_write_json, load_json, new_id, now_iso, project_root


TICKS_PER_SECOND = 90_000
MODEL_REGISTRY_FILES = ('models/audio-adapters.json', 'models/visual-adapters.json', 'config/html-motion-runtime.json')


def project_file(root: Path) -> Path:
    return root / "project.json"


def ledger_file(root: Path) -> Path:
    return root / "rights-ledger.json"


def lock_file(root: Path) -> Path:
    return root / "project.lock.json"


def write_lock_file(root: Path) -> Path:
    """Return the native process lock used to serialize project mutations."""
    return root / "operations" / "project-write.lock"


def transaction_journal_file(root: Path) -> Path:
    """Return the durable journal used for cross-file project metadata writes."""
    return root / "operations" / "project-transaction.json"


def transaction_backup_dir(root: Path, transaction_id: str) -> Path:
    return root / "operations" / "project-transaction-backups" / transaction_id


def _transaction_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _transaction_excluded(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    return (
        name in {"project-write.lock", "queue-cancel.lock"}
        or normalized == "operations/project-transaction.json"
        or normalized.startswith("operations/project-transaction-backups/")
        or name.endswith(".tmp")
    )


def _transaction_metadata_files(root: Path) -> list[Path]:
    """List small project records covered by the crash-recovery journal.

    Media under ``assets/`` and render outputs are deliberately excluded.  A
    recovery report can therefore identify those side effects without copying
    or deleting large user files.
    """
    candidates: list[Path] = []
    for fixed in (project_file(root), ledger_file(root), lock_file(root), root/'assets/lut-library.json', *(root/name for name in MODEL_REGISTRY_FILES)):
        if fixed.is_file():
            candidates.append(fixed)
    for directory_name in ("operations", "history", "validation", "exports"):
        directory = root / directory_name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file():
                relative = _transaction_relative(path, root)
                if not _transaction_excluded(relative):
                    candidates.append(path)
    return sorted(set(candidates), key=lambda value: _transaction_relative(value, root))


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Restore bytes through an fsynced same-directory replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".restore.tmp", dir=str(path.parent))
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _remove_transaction_tree(root: Path, transaction_id: str) -> None:
    backup_root = transaction_backup_dir(root, transaction_id)
    try:
        backup_root.resolve().relative_to((root / "operations" / "project-transaction-backups").resolve())
    except ValueError as exc:
        raise AppError("PROJECT_TRANSACTION_PATH_INVALID", "事务备份目录越出项目范围", exit_code=6, path=str(backup_root)) from exc
    if backup_root.exists():
        shutil.rmtree(backup_root)
    parent = backup_root.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()


def prepare_project_transaction(root_value: str | Path, *, command: str) -> dict[str, Any]:
    """Persist a prepared metadata transaction before a project mutation.

    The journal is intentionally JSON and local so an Agent can inspect it
    after a process or machine interruption.  Callers must hold
    :func:`project_write_lock` while using this API.
    """
    root = project_root(root_value)
    journal_path = transaction_journal_file(root)
    if journal_path.exists():
        pending = recover_pending_transaction(root)
        if pending.get("status") not in {"clean", "recovered", "committed_cleaned"}:
            raise AppError("PROJECT_TRANSACTION_PENDING", "项目仍有未恢复的事务", exit_code=6, retryable=True, path=str(journal_path))
    transaction_id = new_id("txn")
    backup_root = transaction_backup_dir(root, transaction_id)
    backup_root.mkdir(parents=True, exist_ok=False)
    files: list[dict[str, Any]] = []
    try:
        # Bound the number of in-flight copies. All files are flushed before
        # the prepared journal is published; no durability barrier is removed.
        from concurrent.futures import ThreadPoolExecutor
        sources = _transaction_metadata_files(root)
        entries = []
        for index, source in enumerate(sources):
            relative, checked = _recovery_entry_path(root, source.relative_to(root).as_posix())
            entries.append((index, relative, checked))

        def backup_one(entry):
            index, relative, source = entry
            destination = backup_root / f'{index:04d}.bin'
            digest, size = hashlib.sha256(), 0
            with source.open('rb') as reader, destination.open('xb') as writer:
                while chunk := reader.read(1024 * 1024):
                    writer.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            return dict(path=relative,
                backup=f'operations/project-transaction-backups/{transaction_id}/{index:04d}.bin',
                size=size, sha256=digest.hexdigest())

        with ThreadPoolExecutor(max_workers=min(4, max(1, len(entries))),
                                thread_name_prefix='project-backup') as executor:
            files = list(executor.map(backup_one, entries))
        journal = {
            "transaction_version": "0.1.0",
            "transaction_id": transaction_id,
            "status": "prepared",
            "command": command,
            "scope": "project-metadata-v1",
            "started_at": now_iso(),
            "files": files,
        }
        atomic_write_json(journal_path, journal)
        return journal
    except BaseException:
        if backup_root.exists():
            shutil.rmtree(backup_root)
        raise


def _validate_transaction_path(root: Path, relative: str, *, allow_backup: bool = False) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise AppError("PROJECT_TRANSACTION_PATH_INVALID", "事务路径越出项目范围", exit_code=6, path=relative) from exc
    if not allow_backup and _transaction_excluded(relative) and relative != "operations/project-transaction.json":
        raise AppError("PROJECT_TRANSACTION_PATH_INVALID", "事务不能覆盖锁文件或备份目录", exit_code=6, path=relative)
    return candidate


def _recovery_transaction_identity(journal, journal_path):
    import re
    if (not isinstance(journal, dict)
            or journal.get('transaction_version') != '0.1.0'
            or journal.get('scope') != 'project-metadata-v1'
            or not isinstance(journal.get('transaction_id'), str)
            or not re.fullmatch(r'txn_[A-Za-z0-9_-]{1,128}', journal['transaction_id'])
            or not isinstance(journal.get('files'), list)
            or not journal['files']
            or journal.get('status') not in {'prepared', 'committed'}):
        raise AppError('PROJECT_TRANSACTION_INVALID', '事务身份、版本、状态或文件清单无效',
                       exit_code=6, path=str(journal_path))
    return journal['transaction_id'], journal['status']

def _recovery_entry_path(root, value, *, backup_prefix=None):
    if not isinstance(value, str) or not value:
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务相对路径无效', exit_code=6)
    relative = value.replace('\\', '/')
    parts = relative.split('/')
    if any(not part or part in {'.', '..'} or ':' in part or '\0' in part
           or part.endswith(('.', ' ')) for part in parts):
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务路径含别名或无效部分',
                       exit_code=6, path=value)
    if backup_prefix is None:
        fixed = {'project.json', 'rights-ledger.json', 'project.lock.json',
                 'assets/lut-library.json', *MODEL_REGISTRY_FILES}
        allowed = relative in fixed or (len(parts) > 1 and parts[0] in {
            'operations', 'history', 'validation', 'exports'})
        if not allowed or _transaction_excluded(relative):
            raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务不能恢复该项目范围',
                           exit_code=6, path=value)
    elif not relative.startswith(backup_prefix + '/') or '/' in relative[len(backup_prefix) + 1:]:
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '备份不属于当前事务',
                       exit_code=6, path=value)
    candidate = root
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
            raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务恢复拒绝链接路径',
                           exit_code=6, path=str(candidate))
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务路径越出工程',
                       exit_code=6, path=value)
    return relative, resolved

def _preflight_transaction_recovery(root, journal, journal_path):
    import re
    transaction_id = journal['transaction_id']
    prefix = 'operations/project-transaction-backups/' + transaction_id
    seen_paths, seen_backups, prepared = set(), set(), []
    for index, item in enumerate(journal['files']):
        if (not isinstance(item, dict)
                or type(item.get('size')) is not int or item['size'] < 0
                or not isinstance(item.get('sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', item['sha256'])):
            raise AppError('PROJECT_TRANSACTION_INVALID', '事务文件大小或摘要无效',
                           exit_code=6, path=str(journal_path))
        relative, destination = _recovery_entry_path(root, item.get('path'))
        backup_relative, backup = _recovery_entry_path(root, item.get('backup'), backup_prefix=prefix)
        if (relative.casefold() in seen_paths or backup_relative.casefold() in seen_backups
                or backup_relative != prefix + f'/{index:04d}.bin'):
            raise AppError('PROJECT_TRANSACTION_INVALID', '事务文件重复或备份顺序无效',
                           exit_code=6, path=str(journal_path))
        seen_paths.add(relative.casefold())
        seen_backups.add(backup_relative.casefold())
        prepared.append((relative, destination, backup, item['size'], item['sha256']))
    try:
        buffer = bytearray(64 * 1024)
        view = memoryview(buffer)
        for relative, destination, backup, expected_size, expected_digest in prepared:
            if not backup.is_file():
                raise AppError('PROJECT_TRANSACTION_BACKUP_MISSING', '事务备份缺失，拒绝部分恢复',
                               exit_code=6, path=str(backup))
            digest, actual_size = hashlib.sha256(), 0
            with backup.open('rb') as handle:
                while count := handle.readinto(buffer):
                    actual_size += count
                    digest.update(view[:count])
            if actual_size != expected_size or digest.hexdigest() != expected_digest:
                raise AppError('PROJECT_TRANSACTION_BACKUP_CHANGED', '事务备份大小或摘要不符，未写回任何文件',
                               exit_code=6, path=str(backup))
    except (OSError, MemoryError) as exc:
        raise AppError('PROJECT_TRANSACTION_BACKUP_UNREADABLE', '无法完整核验所有事务备份，拒绝部分恢复',
                       exit_code=6, path=str(journal_path)) from exc
    try:
        cleanup = []
        baseline = {relative for relative, *_ in prepared}
        for path in _transaction_metadata_files(root):
            relative, candidate = _recovery_entry_path(root, _transaction_relative(path, root))
            if relative not in baseline:
                cleanup.append((relative, candidate))
    except (OSError, ValueError) as exc:
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '无法核验待清理的元数据范围',
                       exit_code=6, path=str(journal_path)) from exc
    return prepared, cleanup

def recover_pending_transaction(root_value):
    """Preflight every known backup before any restore or metadata cleanup.

    Recovery remains retryable after an interrupted write. Cooperating callers
    must hold the project write lock; this is not multi-file atomic replacement.
    """
    root = project_root(root_value)
    journal_path = transaction_journal_file(root)
    if not journal_path.exists():
        return {'status': 'clean', 'recovered': False, 'journal': str(journal_path)}
    if journal_path.is_symlink() or getattr(journal_path, 'is_junction', lambda: False)():
        raise AppError('PROJECT_TRANSACTION_PATH_INVALID', '事务日志不能是链接',
                       exit_code=6, path=str(journal_path))
    journal = load_json(journal_path)
    transaction_id, status = _recovery_transaction_identity(journal, journal_path)
    prefix = 'operations/project-transaction-backups/' + transaction_id
    # Validate all ancestors even when a committed backup was already removed.
    _recovery_entry_path(root, prefix + '/0000.bin', backup_prefix=prefix)
    if status == 'committed':
        _remove_transaction_tree(root, transaction_id)
        journal_path.unlink(missing_ok=True)
        return {'status': 'committed_cleaned', 'recovered': False,
                'transaction_id': transaction_id, 'journal': str(journal_path)}
    prepared, cleanup = _preflight_transaction_recovery(root, journal, journal_path)
    restored = []
    for relative, destination, backup, expected_size, expected_digest in prepared:
        data = backup.read_bytes()
        if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_digest:
            raise AppError('PROJECT_TRANSACTION_BACKUP_CHANGED', '备份在预检后发生改变，保留日志以便检查',
                           exit_code=6, path=str(backup))
        _atomic_write_bytes(destination, data)
        restored.append(relative)
    removed = []
    for relative, path in cleanup:
        path.unlink()
        removed.append(relative)
    _remove_transaction_tree(root, transaction_id)
    journal_path.unlink(missing_ok=True)
    return {'status': 'recovered', 'recovered': True, 'transaction_id': transaction_id,
            'command': journal.get('command'), 'restored': restored,
            'removed_metadata': removed, 'side_effect_scope': ['assets', 'renders', 'cache'],
            'journal': str(journal_path)}



def _capture_failed_operation_records(root: Path, error: BaseException) -> list[tuple[Path, bytes]]:
    """Keep failure facts and an explicitly referenced validation diagnostic."""
    operations = root / "operations"
    candidates = list(operations.glob("*.json")) if operations.is_dir() else []
    if isinstance(error, AppError) and error.path:
        try:
            diagnostic = Path(error.path).resolve()
        except (OSError, ValueError):
            diagnostic = None
        if diagnostic is not None and diagnostic.is_relative_to((root / "validation").resolve()) and diagnostic.suffix.lower() == '.json':
            candidates.append(diagnostic)
    captured: list[tuple[Path, bytes]] = []
    for path in candidates:
        if path.name == transaction_journal_file(root).name or not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        diagnostic_versioned = path.parent == operations or isinstance(payload, dict) and payload.get('report_version')
        if diagnostic_versioned and isinstance(payload, dict) and payload.get("status") in {"failed", "cancelled", "partial"}:
            captured.append((path, path.read_bytes()))
    return captured


def commit_project_transaction(root_value: str | Path, transaction_id: str) -> dict[str, Any]:
    """Mark a prepared transaction committed and remove its recovery files."""
    root = project_root(root_value)
    journal_path = transaction_journal_file(root)
    journal = load_json(journal_path)
    if journal.get("transaction_id") != transaction_id or journal.get("status") != "prepared":
        raise AppError("PROJECT_TRANSACTION_INVALID", "只能提交当前 prepared 事务", exit_code=6, path=str(journal_path))
    journal["status"] = "committed"
    journal["committed_at"] = now_iso()
    atomic_write_json(journal_path, journal)
    _remove_transaction_tree(root, transaction_id)
    journal_path.unlink(missing_ok=True)
    return {"status": "committed", "transaction_id": transaction_id}


@contextmanager
def project_transaction(root_value: str | Path, *, command: str):
    """Wrap one cooperating CLI mutation in a recoverable metadata transaction."""
    root = project_root(root_value)
    if not project_file(root).exists():
        yield {"active": False, "recovered": False}
        return
    recovered = recover_pending_transaction(root)
    journal = prepare_project_transaction(root, command=command)
    info = {"active": True, "transaction_id": journal["transaction_id"], "recovered": bool(recovered.get("recovered")), "recovery": recovered}
    from .job_workspaces import workspace_scope
    with workspace_scope(root) as jobs:
        try:
            yield info
            commit_project_transaction(root, journal["transaction_id"])
        except BaseException as error:
            failure_records = _capture_failed_operation_records(root, error)
            recover_pending_transaction(root)
            for path, data in failure_records:
                _atomic_write_bytes(path, data)
            info['job_cleanup'] = jobs.finish()
            raise
        else:
            info['job_cleanup'] = jobs.finish()


@contextmanager
def _native_byte_lock(path: Path, *, timeout: float, error_code: str, message: str):
    """Acquire one byte of a local file with a bounded non-blocking retry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    started = time.monotonic()
    acquired = False
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except (OSError, BlockingIOError):
                if timeout <= 0 or time.monotonic() - started >= timeout:
                    raise AppError(error_code, message, exit_code=6, path=str(path), retryable=True)
                time.sleep(min(0.05, max(0.01, timeout / 10)))
        yield {"path": str(path), "acquired": True}
    finally:
        if acquired:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
        else:
            handle.close()


def cancel_lock_file(root: Path) -> Path:
    """Return the short-lived lock for cancellation marker arbitration."""
    return root / "operations" / "queue-cancel.lock"


@contextmanager
def project_write_lock(root_value: str | Path, *, timeout: float = 0.0):
    """Serialize project-bound mutations with a native file lock.

    The lock is advisory at the operating-system level and is held for the
    complete CLI operation, including its read-modify-write phase.  Windows
    uses ``msvcrt.locking``; POSIX is supported for deterministic unit tests and
    future portability.  A zero timeout fails immediately so an Agent can
    retry from the structured ``PROJECT_WRITE_LOCKED`` response.
    """
    root = project_root(root_value)
    if not project_file(root).exists() and not transaction_journal_file(root).exists():
        # Let the command handler return its normal project-not-found/schema
        # error without creating an operations directory as a side effect.
        yield {"path": str(write_lock_file(root)), "root": str(root), "acquired": False}
        return
    path = write_lock_file(root)
    with _native_byte_lock(path, timeout=timeout, error_code="PROJECT_WRITE_LOCKED", message=f"项目正在被另一个本地操作写入: {root}") as info:
        yield {"path": info["path"], "root": str(root), "acquired": True}


@contextmanager
def queue_cancel_lock(root_value: str | Path, *, timeout: float = 1.0):
    """Serialize short cancellation marker/state transitions.

    This lock is deliberately separate from the project write lock so a cancel
    request can arbitrate with queue start/finalization without waiting for the
    render itself to finish.
    """
    root = project_root(root_value)
    path = cancel_lock_file(root)
    with _native_byte_lock(path, timeout=timeout, error_code="QUEUE_CANCEL_CHANNEL_BUSY", message=f"队列取消通道正在处理另一个请求: {root}") as info:
        yield {"path": info["path"], "root": str(root), "acquired": True}


def history_dir(root: Path) -> Path:
    """Return the project-local immutable snapshot directory."""
    return root / "history"


def initial_project(name: str, project_id: str | None = None) -> dict[str, Any]:
    stamp = now_iso()
    pid = project_id or new_id("proj")
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "id": pid,
            "name": name,
            "created_at": stamp,
            "updated_at": stamp,
            "creator": "ai-ad-editor",
            "source_revision": "local",
        },
        "settings": {
            "timebase": {"ticks_per_second": TICKS_PER_SECOND, "display_fps": {"num": 30, "den": 1}},
            "canvas": {"width": 1080, "height": 1920, "pixel_aspect": {"num": 1, "den": 1}},
            "color": {"primaries": "bt709", "transfer": "bt709", "matrix": "bt709", "range": "limited"},
            "audio": {"sample_rate": 48_000, "channels": 2},
            "output": {"container": "mp4", "video": {"codec": "libx264", "preset": "medium", "crf": 18, "pixel_format": "yuv420p"}, "audio": {"codec": "aac", "bitrate": "192k"}},
        },
        "assets": [],
        "sequences": [
            {
                "id": "seq_main",
                "name": "Main",
                "duration_tick": 1,
                "tracks": [
                    {"id": "track_video_1", "kind": "video", "order": 0, "muted": False, "locked": False, "clips": []},
                    {"id": "track_audio_1", "kind": "audio", "order": 0, "muted": False, "locked": False, "clips": []},
                ],
                "markers": [],
            }
        ],
        "templates": [],
        "outputs": [],
        "provenance": {
            "cli_version": VERSION,
            "engine_version": ENGINE_ID,
            "model_versions": [],
            "input_hashes": [],
            "change_log": [],
        },
    }


def initial_ledger() -> dict[str, Any]:
    return {
        "schema_version": "0.2.0",
        "updated_at": now_iso(),
        "records": [],
        "events": [],
        "decisions": [],
        "policy": {"default_target": "commercial_ad", "unverified_publish": False},
    }


def create_project(root_value: str | Path, name: str | None = None, project_id: str | None = None) -> tuple[Path, dict[str, Any]]:
    root = project_root(root_value)
    if root.exists() and any(root.iterdir()):
        raise AppError("PROJECT_EXISTS", f"项目目录非空，拒绝覆盖: {root}", exit_code=2, path=str(root))
    root.mkdir(parents=True, exist_ok=True)
    for directory in ("assets", "renders", "operations", "validation", "exports", "cache", "history"):
        (root / directory).mkdir(exist_ok=True)
    write_lock_file(root).write_bytes(b"0")
    project = initial_project(name or root.name, project_id)
    atomic_write_json(project_file(root), project)
    atomic_write_json(ledger_file(root), initial_ledger())
    atomic_write_json(
        lock_file(root),
        {
            "lock_version": "0.1.0",
            "created_at": now_iso(),
            "cli_version": VERSION,
            "schema_version": SCHEMA_VERSION,
            "engine": {"id": ENGINE_ID, "version": "pending-doctor"},
            "platform": "windows-native",
            "network": "disabled-by-default",
            "upstream_runtime": "none",
        },
    )
    return root, project


def load_project(value: str | Path) -> tuple[Path, dict[str, Any]]:
    root = project_root(value)
    return root, load_json(project_file(root))


def save_project(root: Path, project: dict[str, Any]) -> None:
    project.setdefault("provenance", {}).setdefault("change_log", [])
    project["project"]["updated_at"] = now_iso()
    atomic_write_json(project_file(root), project)


def create_snapshot(root: Path, project: dict[str, Any], *, label: str = "manual") -> dict[str, Any]:
    """Persist a self-contained project/rights snapshot before a mutation.

    Snapshots are append-only JSON records. They are deliberately local and
    human-readable so an Agent can inspect or restore a prior edit state.
    """
    snapshot_id = new_id("snap")
    ledger = load_json(ledger_file(root)) if ledger_file(root).exists() else initial_ledger()
    lock = load_json(lock_file(root)) if lock_file(root).exists() else {}
    payload = {
        "snapshot_version": "0.1.0",
        "snapshot_id": snapshot_id,
        "created_at": now_iso(),
        "label": label,
        "project_id": project.get("project", {}).get("id"),
        "project": copy.deepcopy(project),
        "rights_ledger": copy.deepcopy(ledger),
        "lock": copy.deepcopy(lock),
        "model_registries": {name: load_json(root/name) if (root/name).is_file() else None for name in MODEL_REGISTRY_FILES},
    }
    path = history_dir(root) / f"{snapshot_id}.json"
    atomic_write_json(path, payload)
    return {"snapshot_id": snapshot_id, "path": str(path), "label": label, "created_at": payload["created_at"]}


def load_snapshot(root: Path, snapshot_id: str) -> dict[str, Any]:
    path = history_dir(root) / f"{snapshot_id}.json"
    return load_json(path)


def restore_snapshot(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Restore a validated snapshot's project files atomically."""
    project = payload.get("project")
    ledger = payload.get("rights_ledger")
    if not isinstance(project, dict) or not isinstance(ledger, dict):
        raise AppError("SNAPSHOT_INVALID", "快照缺少 project 或 rights_ledger", exit_code=2)
    registries = payload.get('model_registries')
    if registries is not None and (not isinstance(registries, dict) or set(registries) != set(MODEL_REGISTRY_FILES) or any(value is not None and (not isinstance(value, dict) or not isinstance(value.get('adapters'), list)) for value in registries.values())):
        raise AppError('SNAPSHOT_INVALID', '快照模型登记侧车格式无效', exit_code=2)
    atomic_write_json(project_file(root), project)
    atomic_write_json(ledger_file(root), ledger)
    if isinstance(payload.get("lock"), dict):
        atomic_write_json(lock_file(root), payload["lock"])
    if registries is not None:
        for name, value in registries.items():
            destination = root/name
            if value is not None:
                atomic_write_json(destination, value)
            elif destination.is_file():
                destination.unlink()
    return {"project": str(project_file(root)), "ledger": str(ledger_file(root)), "project_id": project.get("project", {}).get("id")}


def find_sequence(project: dict[str, Any], sequence_id: str | None = None) -> dict[str, Any]:
    sequences = project.get("sequences", [])
    if not sequences:
        raise AppError("SEQUENCE_MISSING", "项目没有序列", exit_code=2, path="sequences")
    wanted = sequence_id or sequences[0].get("id")
    for sequence in sequences:
        if sequence.get("id") == wanted:
            return sequence
    raise AppError("SEQUENCE_NOT_FOUND", f"找不到序列: {wanted}", exit_code=2, path="sequences")


def find_track(sequence: dict[str, Any], track_id: str | None = None, kind: str | None = None) -> dict[str, Any]:
    tracks = sequence.get("tracks", [])
    for track in tracks:
        if track_id and track.get("id") == track_id:
            return track
        if not track_id and kind and track.get("kind") == kind and not track.get("locked", False):
            return track
    descriptor = track_id or kind or "<default>"
    raise AppError("TRACK_NOT_FOUND", f"找不到轨道: {descriptor}", exit_code=2, path="sequences[].tracks")


def asset_map(project: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(asset.get("id")): asset for asset in project.get("assets", []) if asset.get("id")}


def clone_project(project: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(project)

