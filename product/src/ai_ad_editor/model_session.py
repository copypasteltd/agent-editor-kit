"""Explicit, bounded native Windows VACE sessions; local named pipes, JSON only."""
from __future__ import annotations

from contextlib import contextmanager
import json
import math
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

from .errors import AppError, argument_error
from .utils import atomic_write_json, now_iso

PROTOCOL = 'agent-editor-native-model-session-v1'
MESSAGE_LIMIT = 2 * 1024 * 1024
CHUNK_BYTES = 64 * 1024


def send_json(connection, value):
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    if len(raw) > MESSAGE_LIMIT: raise ValueError('MODEL_SESSION_MESSAGE_TOO_LARGE')
    connection.send_bytes(raw)


def receive_json(connection, *, timeout=30):
    if not connection.poll(timeout):
        raise AppError('MODEL_SESSION_TIMEOUT', '本地模型会话未在预算内响应', exit_code=8)
    result = json.loads(connection.recv_bytes(MESSAGE_LIMIT).decode('utf-8'))
    if not isinstance(result, dict): raise ValueError('MODEL_SESSION_JSON_OBJECT_REQUIRED')
    return result


def directory(root, identity):
    try:
        if str(uuid.UUID(identity)) != identity: raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise argument_error('会话ID须为规范UUID', 'model-session')
    base = Path(root).resolve() / 'cache' / 'model-sessions'
    result = base / identity
    for path in (base, result):
        if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
            raise AppError('MODEL_SESSION_PATH_INVALID', '会话目录不可为联接或符号链接', exit_code=10)
    return result


def read_config(root, identity):
    path = directory(root, identity) / 'private.json'
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MESSAGE_LIMIT:
        raise AppError('MODEL_SESSION_NOT_FOUND', '本地会话凭据不存在或无效', exit_code=10)
    value = json.loads(path.read_bytes())
    expected = r'\\.\pipe\agent-editor-' + identity
    if (value.get('protocol') != PROTOCOL or value.get('session_id') != identity
            or value.get('address') != expected or value.get('project_root') != str(Path(root).resolve())
            or not isinstance(value.get('auth'), str) or len(value['auth']) != 64):
        raise AppError('MODEL_SESSION_CONFIG_INVALID', '会话本地凭据或归属不符', exit_code=10)
    try: bytes.fromhex(value['auth'])
    except ValueError as exc: raise AppError('MODEL_SESSION_CONFIG_INVALID', '会话凭据格式无效', exit_code=10) from exc
    return value


def connect(config):
    if sys.platform != 'win32':
        raise AppError('MODEL_SESSION_WINDOWS_REQUIRED', '当前模型会话要求原生Windows命名管道', exit_code=10)
    from multiprocessing.connection import Client
    try:
        return Client(config['address'], family='AF_PIPE', authkey=bytes.fromhex(config['auth']))
    except (OSError, EOFError) as exc:
        raise AppError('MODEL_SESSION_UNAVAILABLE', '会话进程已停止；请新建会话', exit_code=10) from exc


def _accepted(response):
    if response.get('ok') is not True:
        raise AppError(response.get('code', 'MODEL_SESSION_REJECTED'), response.get('message', '本地模型会话拒绝请求'), exit_code=10)
    return response


def status(root, identity):
    config = read_config(root, identity)
    try:
        with connect(config) as connection:
            send_json(connection, dict(command='status', protocol=PROTOCOL))
            return _accepted(receive_json(connection))['state']
    except (AppError, OSError, EOFError) as exc:
        if isinstance(exc, AppError) and exc.code != 'MODEL_SESSION_UNAVAILABLE': raise
        path = directory(root, identity) / 'state.json'
        saved = json.loads(path.read_bytes()) if path.is_file() and path.stat().st_size <= MESSAGE_LIMIT else {}
        return dict(saved, status='unavailable', live=False, saved_status=saved.get('status'))


def stop(root, identity):
    config = read_config(root, identity)
    with connect(config) as connection:
        send_json(connection, dict(command='stop', protocol=PROTOCOL))
        result = _accepted(receive_json(connection))
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]; kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]; kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]; kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x100000, False, result['pid'])
    if handle:
        try:
            if kernel.WaitForSingleObject(handle, 20000) != 0:
                raise AppError('MODEL_SESSION_STOP_TIMEOUT', '会话未在释放预算内退出', exit_code=8)
        finally: kernel.CloseHandle(handle)
    result.update(process_exit_confirmed=True, gpu_release='owned-process-context-destroyed')
    return result


def launch(root, adapter, *, runtime_root, startup_timeout=1800, idle_seconds=300, lifetime_seconds=14400,
           max_jobs=32, cancel_file=None):
    if sys.platform != 'win32': raise argument_error('模型会话要求原生Windows', 'platform')
    for name, value, lo, hi in [('startup_timeout', startup_timeout, 1, 3600), ('idle_seconds', idle_seconds, 10, 3600),
                                ('lifetime_seconds', lifetime_seconds, 60, 86400), ('max_jobs', max_jobs, 1, 1024)]:
        if type(value) is not int or not lo <= value <= hi: raise argument_error('会话预算超范围', name)
    # Verify the executable, implementation bytes and structural model inventory
    # before spawning. The child must hash and lock ALL model bytes before ready.
    from .local_vace import verify_launch_contract
    if not verify_launch_contract(adapter)['ok']:
        raise AppError('MODEL_ADAPTER_HASH_INVALID', '原生会话启动依赖变化', exit_code=10)
    identity = str(uuid.uuid4()); work = directory(root, identity); work.mkdir(parents=True, exist_ok=False)
    config = dict(protocol=PROTOCOL, session_id=identity, project_root=str(Path(root).resolve()),
        address=r'\\.\pipe\agent-editor-' + identity, auth=secrets.token_hex(32), adapter=adapter,
        runtime_root=str(runtime_root), idle_seconds=idle_seconds, lifetime_seconds=lifetime_seconds, max_jobs=max_jobs)
    atomic_write_json(work / 'private.json', config)
    atomic_write_json(work / 'state.json', dict(protocol=PROTOCOL, session_id=identity, status='starting', live=False))
    command = [adapter['executable'], '-I', '-B', '-u', '-X', 'utf8',
               str(Path(__file__).with_name('vace_session_worker.py')), str(work / 'private.json')]
    started = time.monotonic(); process = None
    try:
        with (work / 'worker.log').open('xb') as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
        while True:
            if cancel_file and Path(cancel_file).exists(): raise AppError('CANCELLED', '模型会话启动已取消', exit_code=8)
            if time.monotonic() - started >= startup_timeout:
                raise AppError('MODEL_SESSION_STARTUP_TIMEOUT', '全模型校验超出启动预算', exit_code=8)
            state = json.loads((work / 'state.json').read_bytes())
            if state.get('status') == 'ready':
                return dict(status='ready', session_id=identity, state=status(root, identity),
                            startup_seconds=time.monotonic() - started, credentials_in_output=False)
            if process.poll() is not None or state.get('status') == 'failed':
                raise AppError('MODEL_SESSION_START_FAILED', '模型会话未完成全模型校验，查看本地worker.log', exit_code=10,
                               path=str(work / 'worker.log'), diagnostics=state)
            time.sleep(.1)
    except BaseException:
        if process is not None and process.poll() is None:
            process.kill(); process.wait(timeout=20)
        atomic_write_json(work / 'startup-failure.json', dict(status='failed', session_id=identity,
            owned_process_stopped=process is None or process.poll() is not None, at=now_iso()))
        raise


@contextmanager
def lease(root, identity, adapter, generation, *, timeout):
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 604800:
        raise argument_error('模型会话任务超时须为有限正数，最多7天', 'timeout')
    from .artifact_locks import adopt_locked_attestation
    config = read_config(root, identity)
    with connect(config) as connection:
        send_json(connection, dict(protocol=PROTOCOL, command='acquire', adapter_sha256=adapter['sha256'],
                                   generation=generation, timeout=timeout))
        response = _accepted(receive_json(connection))
        descriptor = dict(session_id=identity, project_root=str(Path(root).resolve()), lease_id=response['lease_id'])
        success = False
        try:
            adopt_locked_attestation(response['artifacts'], adapter['artifacts'])
            yield descriptor
            success = True
        finally:
            try:
                send_json(connection, dict(command='release', lease_id=descriptor['lease_id'], success=success))
                _accepted(receive_json(connection))
            except (OSError, EOFError, AppError):
                if success: raise


class PipeReader:
    def __init__(self, connection):
        self.connection = connection; self.buffer = b''; self.eof = False

    def read(self, count):
        if type(count) is not int or not 0 <= count <= 64 * 1024**2:
            raise ValueError('MODEL_SESSION_BOUNDED_READ_REQUIRED')
        result = bytearray(count); filled = 0
        while filled < count:
            if not self.buffer and not self.eof:
                self.buffer = self.connection.recv_bytes(CHUNK_BYTES)
                if not self.buffer: self.eof = True
            if not self.buffer: break
            take = min(count - filled, len(self.buffer))
            result[filled:filled + take] = self.buffer[:take]
            self.buffer = self.buffer[take:]; filled += take
        return bytes(result[:filled])


class PipeWriter:
    def __init__(self, connection): self.connection = connection

    def write(self, value):
        view = memoryview(value).cast('B')
        for start in range(0, len(view), CHUNK_BYTES): self.connection.send_bytes(view[start:start + CHUNK_BYTES])
        return len(view)

    def flush(self): pass


def add_parser(subs, leaf):
    p = subs.add_parser('model-session', help='显式启动、检查和释放本地GPU模型会话')
    actions = p.add_subparsers(dest='session_action', required=True)
    start = leaf(actions.add_parser('start'))
    start.add_argument('--project', required=True); start.add_argument('--adapter-id', required=True)
    start.add_argument('--startup-timeout-seconds', type=int, default=1800)
    start.add_argument('--idle-seconds', type=int, default=300); start.add_argument('--lifetime-seconds', type=int, default=14400)
    start.add_argument('--max-jobs', type=int, default=32); start.add_argument('--cancel-file')
    for name in ('status', 'stop'):
        action = leaf(actions.add_parser(name)); action.add_argument('--project', required=True); action.add_argument('--session-id', required=True)


def command(args):
    from .cli import _envelope
    from .project import load_project
    root, _ = load_project(args.project)
    action = args.session_action
    if action == 'start':
        from .local_vace import VACE_ENGINE
        from .model_registry import load_visual_model_registry, visual_adapter_for
        from .policy import resolve_local_path
        from .runtime import configure_local_runtime
        adapter = visual_adapter_for(load_visual_model_registry(root), args.adapter_id)
        if not adapter or adapter.get('engine') != VACE_ENGINE:
            raise argument_error('模型会话要求已登记的VACE CUDA适配器', 'adapter-id')
        if args.dry_run:
            return _envelope('media.model-session.start', args, status='planned', data=dict(adapter_id=args.adapter_id,
                model_loaded=False, full_model_hashes_verified=False, persistent_process_started=False))
        marker = resolve_local_path(root, args.cancel_file, field='cancel-file') if args.cancel_file else None
        result = launch(root, adapter, runtime_root=configure_local_runtime()['root'], startup_timeout=args.startup_timeout_seconds,
            idle_seconds=args.idle_seconds, lifetime_seconds=args.lifetime_seconds, max_jobs=args.max_jobs, cancel_file=marker)
    elif action == 'status': result = status(root, args.session_id)
    elif args.dry_run: result = dict(status='planned', session_id=args.session_id, process_stopped=False)
    else: result = stop(root, args.session_id)
    return _envelope('media.model-session.' + action, args, data=result)
