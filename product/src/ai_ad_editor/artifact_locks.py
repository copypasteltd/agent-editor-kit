"""Reuse verified digests only while native read handles deny write/delete."""
from __future__ import annotations

import contextlib
from contextvars import ContextVar
import hashlib
import os
from pathlib import Path
import sys

from .errors import AppError
from .execution_control import checkpoint, ExecutionInterrupted

_CURRENT = ContextVar('agent_video_artifact_verification', default=None)


class _Verification:
    def __init__(self):
        self.entries = {}
        self.bytes_hashed = 0
        self.cache_hits = 0

    def entry(self, path: Path, role: str) -> dict:
        checkpoint()
        if str(path).startswith('\\\\') or path.is_symlink() or getattr(path, 'is_junction', lambda: False)() or not path.is_file():
            raise AppError('LOCAL_ARTIFACT_LOCK_FAILED', '模型依赖必须为本地普通文件', exit_code=10, path=str(path))
        path = path.resolve()
        key = str(path)
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        if stat.st_size < 1:
            raise AppError('LOCAL_ARTIFACT_LOCK_FAILED', '模型依赖不能为空', exit_code=10, path=key)
        if key in self.entries:
            cached = self.entries[key]
            if identity != cached['identity']:
                raise AppError('LOCAL_ARTIFACT_IDENTITY_CHANGED', '持锁文件路径或元数据变化', exit_code=10, path=key)
            self.cache_hits += 1
            return {'path': key, 'role': role, 'bytes': stat.st_size, 'sha256': cached['sha256']}
        import ctypes
        from ctypes import wintypes
        import msvcrt
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        # FILE_SHARE_READ permits model loaders and denies writers/deletion.
        handle = kernel.CreateFileW(key, 0x80000000, 1, None, 3, 0x08000080, None)
        if handle == ctypes.c_void_p(-1).value:
            error = ctypes.WinError(ctypes.get_last_error())
            raise AppError('LOCAL_ARTIFACT_LOCK_FAILED', '无法冻结本地模型依赖，拒绝复用摘要', exit_code=10, path=key, cause=str(error)) from error
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            raise
        stream = os.fdopen(fd, 'rb')
        try:
            locked = os.fstat(fd)
            locked_identity = (locked.st_dev, locked.st_ino, locked.st_size, locked.st_mtime_ns)
            if locked_identity != identity:
                raise AppError('LOCAL_ARTIFACT_IDENTITY_CHANGED', '加锁期间模型依赖发生变化', exit_code=10, path=key)
            digest = hashlib.sha256()
            size = 0
            while True:
                checkpoint()
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
            checkpoint(force=True)
            if size != locked.st_size:
                raise AppError('LOCAL_ARTIFACT_IDENTITY_CHANGED', '模型依赖读取长度变化', exit_code=10, path=key)
            value = 'sha256:' + digest.hexdigest()
            self.entries[key] = {'stream': stream, 'identity': locked_identity, 'sha256': value}
            self.bytes_hashed += size
            return {'path': key, 'role': role, 'bytes': size, 'sha256': value}
        except BaseException as exc:
            stream.close()
            if isinstance(exc, ExecutionInterrupted):
                exc.diagnostics = dict(phase='integrity-read', path=key,
                    bytes_processed=size, total_bytes=locked.st_size,
                    partial_digest_discarded=True, digest_cached=False)
            raise

    def summary(self):
        return {'mode': 'windows-read-lock-command-scope', 'files_hashed': len(self.entries),
                'bytes_hashed': self.bytes_hashed, 'digest_reuses_while_locked': self.cache_hits,
                'write_and_delete_sharing': False, 'persists_across_commands': False}

    def close(self):
        for entry in self.entries.values():
            entry['stream'].close()
        self.entries.clear()


@contextlib.contextmanager
def verification_scope():
    current = _CURRENT.get()
    if current is not None or sys.platform != 'win32':
        yield current
        return
    current = _Verification()
    token = _CURRENT.set(current)
    try:
        yield current
    finally:
        _CURRENT.reset(token)
        current.close()


def artifact_entry(path: Path, role: str) -> dict:
    current = _CURRENT.get()
    if current is not None:
        return current.entry(path, role)
    from .local_matting import _entry
    return _entry(path, role)


def verification_entries():
    """Return immutable identities observed under the current native read locks."""
    current = _CURRENT.get()
    if current is None:
        return []
    return [{'path': path, 'bytes': item['identity'][2], 'sha256': item['sha256']}
            for path, item in sorted(current.entries.items())]


def verification_summary():
    current = _CURRENT.get()
    return current.summary() if current is not None and current.entries else None
