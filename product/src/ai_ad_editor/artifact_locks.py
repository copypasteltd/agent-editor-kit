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
    def __init__(self, *, session=False):
        self.entries = {}
        self.bytes_hashed = 0
        self.cache_hits = 0
        self.session = session
        self.attested_files = 0
        self.attested_bytes = 0

    def entry(self, path: Path, role: str, *, attested=None) -> dict:
        checkpoint()
        if str(path).startswith('\\\\') or path.is_symlink() or getattr(path, 'is_junction', lambda: False)() or not path.is_file():
            raise AppError('LOCAL_ARTIFACT_LOCK_FAILED', '模型依赖必须为本地普通文件', exit_code=10, path=str(path))
        path = path.resolve()
        key = str(path)
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        if attested is not None and (list(identity) != attested['identity'] or stat.st_size != attested['bytes']):
            raise AppError('LOCAL_ARTIFACT_ATTESTATION_CHANGED', '会话持锁依赖与本地身份不同', exit_code=10, path=key)
        if stat.st_size < 1:
            raise AppError('LOCAL_ARTIFACT_LOCK_FAILED', '模型依赖不能为空', exit_code=10, path=key)
        if key in self.entries:
            cached = self.entries[key]
            if identity != cached['identity'] or attested is not None and cached['sha256'] != attested['sha256']:
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
            if attested is not None:
                self.entries[key] = {'stream': stream, 'identity': locked_identity, 'sha256': attested['sha256']}
                self.attested_files += 1
                self.attested_bytes += locked.st_size
                return {'path': key, 'role': role, 'bytes': locked.st_size, 'sha256': attested['sha256']}
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
        value = {'mode': 'windows-read-lock-model-session' if self.session else 'windows-read-lock-command-scope',
                'files_hashed': len(self.entries) - self.attested_files,
                'bytes_hashed': self.bytes_hashed, 'digest_reuses_while_locked': self.cache_hits,
                'write_and_delete_sharing': False, 'persists_across_commands': self.session}
        if self.attested_files:
            value.update(session_attested_files=self.attested_files, session_attested_bytes=self.attested_bytes,
                         attestation_transfer='authenticated-local-pipe-with-overlapping-deny-write-locks')
        return value

    def close(self):
        for entry in self.entries.values():
            entry['stream'].close()
        self.entries.clear()


@contextlib.contextmanager
def verification_scope(*, session=False):
    current = _CURRENT.get()
    if current is not None or sys.platform != 'win32':
        yield current
        return
    current = _Verification(session=session)
    token = _CURRENT.set(current)
    try:
        yield current
    finally:
        _CURRENT.reset(token)
        current.close()


@contextlib.contextmanager
def shared_verification_scope(verification):
    """Use the resident owner's still-open handles in a sequential job thread."""
    token = _CURRENT.set(verification)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def locked_attestation():
    current = _CURRENT.get()
    if current is None or not current.session:
        raise AppError('LOCAL_ARTIFACT_ATTESTATION_UNAVAILABLE', '需要持锁原生模型会话', exit_code=10)
    return [dict(path=path, bytes=item['identity'][2], identity=list(item['identity']), sha256=item['sha256'])
            for path, item in sorted(current.entries.items())]


def adopt_locked_attestation(proofs, artifacts):
    """Called only with a live authenticated lease; acquire local locks before release.

    A persistent file or a previous process receipt is never a valid attestation.
    The controller keeps its authenticated lease open through command completion.
    """
    current = _CURRENT.get()
    if current is None or not isinstance(proofs, list) or len(proofs) != len(artifacts):
        raise AppError('LOCAL_ARTIFACT_ATTESTATION_INVALID', '会话依赖证明缺少命令文件锁范围', exit_code=10)
    expected = {a['path']: a for a in artifacts}
    if len(expected) != len(artifacts) or len({p.get('path') for p in proofs if isinstance(p, dict)}) != len(proofs):
        raise AppError('LOCAL_ARTIFACT_ATTESTATION_INVALID', '会话依赖证明清单重复', exit_code=10)
    for proof in proofs:
        if (not isinstance(proof, dict) or set(proof) != {'path', 'bytes', 'identity', 'sha256'}
                or proof['path'] not in expected or proof['sha256'] != expected[proof['path']]['sha256']
                or proof['bytes'] != expected[proof['path']]['bytes'] or not isinstance(proof['identity'], list)
                or len(proof['identity']) != 4 or any(type(v) is not int or v < 0 for v in proof['identity'])):
            raise AppError('LOCAL_ARTIFACT_ATTESTATION_INVALID', '会话依赖证明与适配器不符', exit_code=10)
    for proof in proofs:
        current.entry(Path(proof['path']), expected[proof['path']]['role'], attested=proof)


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
