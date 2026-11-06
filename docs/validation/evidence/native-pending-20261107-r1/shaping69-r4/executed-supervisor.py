"""Supervise frozen native Windows batches independently of a terminal session.

Launch this file through Win32_Process.Create with ShowWindow=0. This runner
never installs dependencies, changes a freeze, retries a failed gate, or edits
formal Skill files itself. The original frozen delivery gates retain authority.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'docs/validation'
BASE = HERE / 'evidence/native-pending-20261107-r1'
LOCAL = ROOT / 'local/agent-ffmpeg/native-pending-20261107-r1'
GPU_PYTHON = Path('E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe')
UTILITY_PYTHON = Path('C:/Python313/python.exe')
FFMPEG_BIN = Path('C:/Users/carzy/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1-full_build/bin')
PORTRAIT = HERE / 'evidence/portrait67-20261106-r1'
SHAPING = HERE / 'evidence/shaping69-20261107-r1'


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def command(python, script, *args):
    flags = ['-E', '-B', '-u', '-X', 'utf8'] if python == GPU_PYTHON else ['-I', '-B', '-u', '-X', 'utf8']
    return [str(python), *flags, str(HERE / script), *map(str, args)]


def plan(args):
    run = args.run
    work = LOCAL / (args.profile + '-' + run)
    if args.profile == 'portrait67':
        identities = {name: work / (name + '-process.json') for name in ('source', 'prerequisite')}
        return [
            dict(name='source', argv=command(GPU_PYTHON, 'portrait67.py', 'tests', '--run', run,
                 '--freeze-run', args.freeze_run), deadline=18000,
                 terminal=str(PORTRAIT / ('source-all-' + run) / 'verification.json')),
            dict(name='prerequisite', argv=command(GPU_PYTHON, 'run_portrait67_chain.py',
                 '--source-identity', identities['source'], '--run', run, '--source-run', run,
                 '--freeze-run', args.freeze_run), deadline=42000,
                 terminal=str(PORTRAIT / ('chain-' + run) / 'verification.json')),
            dict(name='delivery', argv=command(GPU_PYTHON, 'portrait67_delivery.py', 'continue',
                 '--run', run, '--phase-run', 'r1', '--contracts-run', 'r1',
                 '--freeze-run', args.freeze_run, '--prerequisite-identity', identities['prerequisite'],
                 *[part for key in ('tests', 'candidate', 'stage', 'native', 'music', 'package',
                                   'descriptor', 'kit', 'portable', 'faults', 'prerequisite')
                   for part in ('--' + key + '-run', run)]), deadline=72000,
                 terminal=str(PORTRAIT / ('delivery-chain-' + run) / 'verification.json')),
        ]
    return [
        dict(name='build', argv=command(UTILITY_PYTHON, 'build_shaping69.py', '--run', run,
             '--freeze-run', args.freeze_run, '--source-run', args.source_run), deadline=2400,
             terminal=str(SHAPING / ('build-' + run) / 'verification.json'),
             expected_status='built-not-yet-functionally-validated'),
        dict(name='tests', argv=command(UTILITY_PYTHON, 'validate_shaping69.py', 'tests',
             '--run', args.tests_run, '--freeze-run', args.freeze_run, '--build-run', run), deadline=14400,
             terminal=str(SHAPING / ('tests-' + args.tests_run) / 'verification.json')),
        dict(name='case', argv=command(UTILITY_PYTHON, 'shaping69_case.py', '--run', args.case_run,
             '--freeze-run', args.freeze_run, '--build-run', run, '--tests-run', args.tests_run,
             '--ffmpeg', FFMPEG_BIN / 'ffmpeg.exe', '--ffprobe', FFMPEG_BIN / 'ffprobe.exe'), deadline=3600,
             terminal=str(SHAPING / ('case-' + args.case_run) / 'verification.json')),
    ]


def supervise(args):
    assert os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix
    assert ROOT.drive.upper() == 'E:' and Path(sys.executable).resolve() == UTILITY_PYTHON.resolve()
    out = BASE / (args.profile + '-' + args.run)
    work = LOCAL / (args.profile + '-' + args.run)
    assert not out.exists() and not work.exists(), 'Use fresh evidence and scratch directories'
    rows = plan(args)
    for row in rows:
        assert not Path(row['terminal']).exists(), 'A prior terminal must never be overwritten'
    out.mkdir(parents=True)
    work.mkdir(parents=True)
    scratch = work / 'temp'
    scratch.mkdir()
    env = dict(os.environ)
    env.update(TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1')
    env['PATH'] = str(FFMPEG_BIN) + os.pathsep + str(Path(os.environ['SystemRoot']) / 'System32') + os.pathsep + env.get('PATH', '')
    os.environ.update({key: env[key] for key in ('TEMP', 'TMP', 'TMPDIR', 'PYTHONDONTWRITEBYTECODE', 'PATH')})
    native = module('pending_windows_identity', HERE / 'run_delivery66_native.py')
    pins = {str(path): sha(path) for path in (Path(__file__).resolve(), HERE / 'run_delivery66_native.py')}
    state = dict(status='preflight', created_at_utc=utc(), heartbeat_at_utc=utc(),
                 profile=args.profile, run=args.run, supervisor_identity=native.process_identity(os.getpid()),
                 native_windows=True, virtualization=False, terminal_session_required=False,
                 formal_activation=False, full_goal_closed=False, input_pins=pins, plan=rows, steps=[])
    save(out / 'state.json', state)
    (out / 'executed-supervisor.py').write_bytes(Path(__file__).read_bytes())
    processes = []
    logs = []

    def guard():
        assert all(sha(path) == expected for path, expected in pins.items()), 'Supervisor input changed'

    def start(row):
        guard()
        stdout = (out / (row['name'] + '.stdout')).open('xb')
        stderr = (out / (row['name'] + '.stderr')).open('xb')
        logs.extend((stdout, stderr))
        process = subprocess.Popen(row['argv'], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        identity = native.process_identity(process.pid)
        assert identity is not None, 'Child disappeared before its native identity could be retained'
        save(work / (row['name'] + '-process.json'), identity)
        step = dict(name=row['name'], identity=identity, started_at_utc=utc(), status='running')
        state['steps'].append(step)
        state['status'] = 'running'
        save(out / 'state.json', state)
        item = (row, process, step, time.monotonic())
        processes.append(item)
        return item

    def finished(item):
        row, process, step, began = item
        code = process.poll()
        if code is None:
            if time.monotonic() - began > row['deadline']:
                raise TimeoutError('Owned batch exceeded its explicit deadline: ' + row['name'])
            return False
        if step['status'] != 'running':
            return True
        terminal = Path(row['terminal'])
        proof = read(terminal) if terminal.is_file() else None
        passed = code == 0 and proof is not None and proof.get('status') == row.get('expected_status', 'passed')
        step.update(status='passed' if passed else 'failed', exit_code=code, finished_at_utc=utc(),
                    elapsed_seconds=time.monotonic() - began, terminal_present=proof is not None,
                    terminal_sha256=sha(terminal) if proof is not None else None)
        save(out / 'state.json', state)
        if not passed:
            raise RuntimeError('Gate failed or lacks a passed terminal; no retry: ' + row['name'])
        return True

    try:
        with (out / 'supervisor.stdout').open('x', encoding='utf-8') as stdout, (out / 'supervisor.stderr').open('x', encoding='utf-8') as stderr, contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            if args.profile == 'portrait67':
                delivery = module('pending_portrait_delivery', HERE / 'portrait67_delivery.py')
                delivery.code_guard(type('Args', (), dict(phase_run='r1'))())
                for row in rows:
                    item = start(row)
                    # The continuation runners must open the original child's
                    # live process handle before that child's work can finish.
                    assert native.process_identity(item[1].pid) == item[2]['identity']
                while not all(finished(item) for item in processes):
                    state['heartbeat_at_utc'] = utc()
                    save(out / 'state.json', state)
                    time.sleep(2)
                state['formal_activation'] = read(rows[-1]['terminal']).get('formal_activation', False)
            else:
                for row in rows:
                    item = start(row)
                    while not finished(item):
                        state['heartbeat_at_utc'] = utc()
                        save(out / 'state.json', state)
                        time.sleep(2)
            guard()
            state.update(status='passed', finished_at_utc=utc(), heartbeat_at_utc=utc())
            save(out / 'state.json', state)
            save(out / 'verification.json', state)
        return 0
    except BaseException as exc:
        # No implicit retry or formal rewrite. Original child gates own their
        # jobs and any rollback; allow already started dependent waiters to exit.
        state.update(status='stopped', error=repr(exc), finished_at_utc=utc(), heartbeat_at_utc=utc())
        state['still_live_children'] = [native.process_identity(process.pid) for _, process, _, _ in processes if process.poll() is None]
        save(out / 'state.json', state)
        save(out / 'verification.json', state)
        raise
    finally:
        for stream in logs:
            stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('portrait67', 'shaping69'), required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--freeze-run', required=True)
    parser.add_argument('--source-run', default='r3')
    parser.add_argument('--tests-run', default='r1')
    parser.add_argument('--case-run', default='r1')
    parser.add_argument('--plan', action='store_true')
    args = parser.parse_args()
    assert all(value.isalnum() and len(value) <= 32 for key, value in vars(args).items() if key not in ('profile', 'plan'))
    if args.plan:
        print(json.dumps(plan(args), ensure_ascii=False, indent=2))
        return 0
    return supervise(args)


if __name__ == '__main__':
    raise SystemExit(main())
