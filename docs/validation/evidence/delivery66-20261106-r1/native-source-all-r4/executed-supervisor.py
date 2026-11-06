"""Persist a whole frozen regression beyond the lifetime of a terminal cell.

Native Windows only. No scheduler, service, shell process-tree kill or VM.
The supervisor retains its own Popen handle and records the real exit status.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/delivery66-20261106-r1'
LOCAL = ROOT / 'local/agent-ffmpeg/delivery66'


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def process_identity(pid):
    """Query one live OS process; a PID or parent number alone is not identity."""
    if os.name != 'nt' or type(pid) is not int or pid <= 0:
        raise ValueError('Native Windows process ID required')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    handle = kernel.OpenProcess(0x1000 | 0x00100000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:
            return None
        raise ctypes.WinError(error)
    try:
        state = kernel.WaitForSingleObject(handle, 0)
        if state == 0:
            return None
        if state != 258:
            raise ctypes.WinError(ctypes.get_last_error())
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(item) for item in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        buffer, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        stamp = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return dict(pid=pid, creation_filetime=stamp, executable=buffer.value)
    finally:
        kernel.CloseHandle(handle)


def same_process(expected):
    return expected is not None and process_identity(expected['pid']) == expected


def locations(args):
    mode = 'installed-all' if args.installed else 'source-all'
    out = BASE / ('native-' + mode + '-' + args.run)
    result = BASE / (mode + '-' + args.run) / 'verification.json'
    return out, result


def supervise(args):
    out, result_path = locations(args)
    launch = read(out / 'launch.json')
    if launch['runner_sha256'] != sha(ROOT / 'docs/validation/delivery66.py'):
        raise ValueError('Frozen round runner changed before launch')
    if (out / 'state.json').exists():
        raise ValueError('Supervisor evidence already exists')
    python = [sys.executable, '-E', '-B', '-u', '-X', 'utf8']
    command = [*python, str(ROOT / 'docs/validation/delivery66.py'), 'tests',
               '--run', args.run, '--freeze-run', args.freeze_run]
    if args.installed:
        command += ['--installed', str(args.installed)]
    temp = LOCAL / 'native-temp'
    temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp),
               PYTHONDONTWRITEBYTECODE='1')
    state = dict(status='starting', started_at_utc=utc(), command=command,
                 supervisor=process_identity(os.getpid()), result=str(result_path),
                 runner_sha256=launch['runner_sha256'], original_test_selection='whole-discovery')
    write(out / 'state.json', state)
    began = time.monotonic()
    try:
        with (out / 'child.stdout').open('xb') as stdout, (out / 'child.stderr').open('xb') as stderr:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
            state.update(status='running', child=process_identity(process.pid))
            write(out / 'state.json', state)
            code = process.wait()
        terminal = read(result_path) if result_path.is_file() else None
        passed = code == 0 and terminal is not None and terminal.get('status') == 'passed'
        state.update(status='passed' if passed else 'failed' if terminal else 'interrupted',
            exit_code=code, finished_at_utc=utc(), elapsed_seconds=time.monotonic() - began,
            terminal_result_present=terminal is not None,
            terminal_result_sha256=sha(result_path) if terminal else None)
        write(out / 'state.json', state)
        return 0 if passed else 1
    except BaseException as exc:
        state.update(status='supervisor-error', finished_at_utc=utc(), error=repr(exc),
                     elapsed_seconds=time.monotonic() - began)
        write(out / 'state.json', state)
        raise


def start(args):
    out, result = locations(args)
    if out.exists() or result.parent.exists():
        raise ValueError('Every native whole-suite attempt needs a new run directory')
    freeze = BASE / ('freeze-' + args.freeze_run) / 'verification.json'
    if read(freeze)['status'] != 'frozen':
        raise ValueError('A completed implementation freeze is required')
    for owner in BASE.glob('native-*/owner.json'):
        if same_process(read(owner).get('supervisor')):
            raise ValueError('A verified native supervisor is already live; inspect its same handle instead')
    out.mkdir(parents=True)
    (out / 'executed-supervisor.py').write_bytes(Path(__file__).read_bytes())
    write(out / 'launch.json', dict(status='requested', created_at_utc=utc(),
        runner_sha256=sha(ROOT / 'docs/validation/delivery66.py'),
        freeze_sha256=sha(freeze), native_windows=True, virtualization=False))
    command = [sys.executable, '-E', '-B', '-u', '-X', 'utf8', str(Path(__file__).resolve()),
               'supervise', '--run', args.run, '--freeze-run', args.freeze_run]
    if args.installed:
        command += ['--installed', str(args.installed)]
    # Break away explicitly, rather than relying on a terminal session to survive.
    # A host that forbids breakaway fails visibly; no silent in-session fallback.
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_BREAKAWAY_FROM_JOB
    try:
        with (out / 'supervisor.stdout').open('xb') as stdout, (out / 'supervisor.stderr').open('xb') as stderr:
            process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, creationflags=flags)
    except OSError as exc:
        write(out / 'state.json', dict(status='launch-failed', error_type=type(exc).__name__,
            error=str(exc), in_session_fallback=False, no_test_process_created=True, observed_at_utc=utc()))
        raise
    identity = process_identity(process.pid)
    write(out / 'owner.json', dict(supervisor=identity, spawned_at_utc=utc(), command=command))
    print(json.dumps(dict(status='started', identity=identity, evidence=str(out)), ensure_ascii=False), flush=True)


def status(args):
    out, result = locations(args)
    state = read(out / 'state.json') if (out / 'state.json').is_file() else dict(status='not-yet-started')
    owner = read(out / 'owner.json')['supervisor']
    observed = dict(state=state, supervisor_live=same_process(owner),
                    child_live=same_process(state.get('child')), result_present=result.is_file(),
                    observed_at_utc=utc())
    if result.is_file():
        observed['terminal_result_sha256'] = sha(result)
    print(json.dumps(observed, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'supervise', 'status'])
    parser.add_argument('--run', required=True)
    parser.add_argument('--freeze-run', default='r4')
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    if os.name != 'nt' or not sys.dont_write_bytecode or not all(
            value.isalnum() and len(value) <= 32 for value in (args.run, args.freeze_run)):
        raise ValueError('Use native Windows Python -B and bounded run IDs')
    if args.installed:
        args.installed = args.installed.resolve(strict=True)
        if not args.installed.is_relative_to(ROOT / 'local/agent-ffmpeg'):
            raise ValueError('Use an owned offline installation')
    return {'start': start, 'supervise': supervise, 'status': status}[args.action](args)


if __name__ == '__main__':
    raise SystemExit(main())
