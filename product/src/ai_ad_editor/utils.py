from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .errors import AppError, argument_error
from .execution_control import checkpoint, ExecutionInterrupted


ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a local file with one reusable buffer and bounded allocation.

    A full native regression observed MemoryError in allocating read(size).
    Reserve before opening the file, then read into the same storage; failed
    reservation cannot advance a stream or yield a partial digest.
    """
    checkpoint()
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ValueError('chunk_size must be a positive integer')
    requested = min(chunk_size, 64 * 1024)
    buffer = None
    for budget in dict.fromkeys((requested, min(requested, 8192), min(requested, 1024))):
        try:
            buffer = bytearray(budget)
            break
        except MemoryError:
            continue
    if buffer is None:
        raise AppError('FILE_HASH_MEMORY_EXHAUSTED', '无法为本地文件摘要保留有界读取缓冲区',
                       exit_code=6, path=str(path))
    view = memoryview(buffer)
    digest = hashlib.sha256()
    processed = 0
    try:
        with path.open("rb", buffering=0) as handle:
            while True:
                checkpoint()
                count = handle.readinto(buffer)
                if count == 0:
                    break
                if not isinstance(count, int) or not 0 < count <= len(buffer):
                    raise OSError('Local file returned an invalid read count')
                digest.update(view[:count])
                processed += count
        checkpoint(force=True)
    except ExecutionInterrupted as exc:
        exc.diagnostics = dict(phase='integrity-read', path=str(path), bytes_processed=processed,
            partial_digest_discarded=True, digest_cached=False)
        raise
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request_fingerprint(command: str, args: Any) -> str:
    """Create a stable fingerprint for a project-bound CLI request.

    Request IDs, output formatting and progress transport are presentation details;
    input paths and file contents remain part of the fingerprint so reusing a key
    with a changed edit plan is rejected instead of silently replaying stale work.
    """
    values = dict(vars(args)) if hasattr(args, "__dict__") else dict(args)
    for field in ("request_id", "format", "progress", "idempotency_key", "dry_run"):
        values.pop(field, None)
    for field in ("project", "input", "output", "variables", "report", "rules", "corrections", "transcript"):
        value = values.get(field)
        if not isinstance(value, str) or not value:
            continue
        candidate = Path(value).expanduser()
        if field == 'transcript' and not candidate.is_absolute() and values.get('project'):
            candidate = Path(values['project']) / candidate
        candidate = candidate.resolve()
        values[field] = str(candidate)
        # Output/report files and project.json are products of the operation.
        # Hashing their new contents would invalidate an otherwise identical
        # replay as soon as the first operation succeeded.
        if field in {"input", "variables", "rules", "corrections", "transcript"} and candidate.is_file():
            try:
                values[field + "_sha256"] = sha256_file(candidate)
            except OSError:
                values[field + "_unreadable"] = True
    payload = json.dumps({"command": command, "request": values}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def idempotency_record_path(root: Path, command: str, key: str) -> Path:
    digest = sha256_bytes(f"{command}\n{key}".encode("utf-8"))
    return root / "operations" / "idempotency" / f"{digest}.json"


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise AppError("FILE_NOT_FOUND", f"文件不存在: {path}", exit_code=3, path=str(path)) from exc
    except json.JSONDecodeError as exc:
        raise AppError("JSON_INVALID", f"JSON 无法解析: {path}: {exc}", exit_code=2, path=str(path)) from exc
    if not isinstance(value, dict):
        raise AppError("JSON_OBJECT_REQUIRED", "顶层 JSON 必须是对象", exit_code=2, path=str(path))
    return value


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False)


def _windows_replace_open_file(source: Path, destination: Path) -> None:
    """Rename atomically while preserving handles that explicitly share deletion.

    MoveFileExW (used by os.replace) can reject an open destination even when
    its readers share deletion. FileRenameInfoEx with POSIX semantics keeps
    those readers on the old file; new opens see the complete replacement.
    Handles that deny deletion still prevent the rename, including model locks.
    """
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL

    class RenameInfo(ctypes.Structure):
        _fields_ = [('Flags', wintypes.DWORD), ('RootDirectory', wintypes.HANDLE),
                    ('FileNameLength', wintypes.DWORD), ('FileName', wintypes.WCHAR * 1)]

    handle = kernel.CreateFileW(str(source.absolute()), 0x10000, 7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        name = str(destination.absolute()).encode('utf-16-le')
        buffer = ctypes.create_string_buffer(RenameInfo.FileName.offset + len(name) + 2)
        info = ctypes.cast(buffer, ctypes.POINTER(RenameInfo)).contents
        info.Flags = 3  # FILE_RENAME_REPLACE_IF_EXISTS | FILE_RENAME_POSIX_SEMANTICS
        info.RootDirectory = None
        info.FileNameLength = len(name)
        ctypes.memmove(ctypes.addressof(buffer) + RenameInfo.FileName.offset, name, len(name))
        if not kernel.SetFileInformationByHandle(handle, 22, buffer, len(buffer)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)


def _replace_atomic_file(source: Path, destination: Path) -> None:
    for attempt in range(6):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            if sys.platform != 'win32' or getattr(exc, 'winerror', None) not in {5, 32, 33}:
                raise
            try:
                _windows_replace_open_file(source, destination)
                return
            except OSError as native_exc:
                if getattr(native_exc, 'winerror', None) in {50, 87, 120}:
                    # An older filesystem/API may only support the original
                    # rename after transient readers release their handles.
                    if attempt == 5:
                        raise exc from native_exc
                elif getattr(native_exc, 'winerror', None) not in {5, 32, 33} or attempt == 5:
                    raise
            time.sleep(.05 * 2**attempt)


@contextlib.contextmanager
def shared_binary_reader(path: Path):
    """Read a stable handle while allowing Windows atomic file replacement."""
    if sys.platform != 'win32':
        with path.open('rb') as stream:
            yield stream
        return
    if str(path).startswith('\\\\'):
        raise ValueError('Local snapshot path required')
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0x80000000, 7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(fd, 'rb') as stream:
        yield stream


def read_json_snapshot(path: Path, max_bytes: int = 64 * 1024):
    if type(max_bytes) is not int or not 1 <= max_bytes <= 1024**2:
        raise ValueError('Snapshot byte budget invalid')
    with shared_binary_reader(path) as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError('Snapshot byte budget exceeded')
    return json.loads(raw.decode('utf-8-sig'))


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _replace_atomic_file(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def atomic_write_text(path: Path, value: str) -> None:
    """Write UTF-8 text through a same-directory temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_atomic_file(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def atomic_replace(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)


def project_root(path: str | Path) -> Path:
    root = Path(path).expanduser().resolve()
    if root.suffix.lower() == ".json" and root.name.lower() == "project.json":
        root = root.parent
    return root


def ensure_inside(root: Path, candidate: Path, *, allow_external: bool = False) -> Path:
    root = root.resolve()
    candidate = candidate.expanduser().resolve()
    if allow_external:
        return candidate
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise argument_error(f"路径越过项目根目录: {candidate}", str(candidate)) from exc
    return candidate


def safe_filename(name: str) -> str:
    name = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name).strip("._")
    return cleaned or "asset.bin"


def executable(name: str) -> str | None:
    return shutil.which(name)


def run_process(
    args: Iterable[str],
    *,
    timeout: float | None = None,
    cwd: Path | None = None,
    cancel_file: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = list(args)
    if cancel_file is not None and cancel_file.exists():
        raise AppError("CANCELLED", "任务在启动前已被取消", exit_code=8, path=str(cancel_file), retryable=False)
    from .native_process_job import NativeProcessJob
    job = None
    process = None
    try:
        job = NativeProcessJob()
        process = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | job.creationflags,
        )
        try:
            job.attach_and_resume(process)
        except BaseException:
            process.kill()
            process.wait(timeout=5)
            raise
        result: dict[str, str] = {}

        def collect() -> None:
            stdout, stderr = process.communicate()
            result["stdout"] = stdout or ""
            result["stderr"] = stderr or ""

        reader = threading.Thread(target=collect, name="ai-ad-editor-process-reader", daemon=True)
        reader.start()
        started = time.monotonic()

        def stop_process() -> None:
            job.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            reader.join(timeout=5)

        while reader.is_alive():
            if cancel_file is not None and cancel_file.exists():
                stop_process()
                raise AppError("CANCELLED", "任务已取消，临时产物将被清理", exit_code=8, path=str(cancel_file), retryable=False, cause=result.get("stderr", "")[-2000:])
            if timeout is not None and time.monotonic() - started > timeout:
                stop_process()
                raise AppError("PROCESS_TIMEOUT", f"子进程超时: {command[0]}", exit_code=6, retryable=True, cause=result.get("stderr", "")[-2000:])
            if process.poll() is not None:
                # A departed child can leave descendants holding its pipes open.
                # Closing our owned job ends those descendants before joining.
                job.close()
            reader.join(timeout=0.1)
        return subprocess.CompletedProcess(command, process.returncode, result.get("stdout", ""), result.get("stderr", ""))
    except OSError as exc:
        raise AppError("PROCESS_START_FAILED", f"无法启动子进程: {command[0]}", exit_code=10, cause=str(exc)) from exc
    finally:
        if job is not None:
            job.close()


def assert_id(value: str, path: str) -> None:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise argument_error("ID 不符合规范", path)
