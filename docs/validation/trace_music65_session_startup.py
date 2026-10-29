"""Time the unchanged session test through memory-only child instrumentation."""
import argparse
import hashlib
import json
import mmap
from pathlib import Path
import struct
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[2]
CAPACITY = 256 * 1024


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and sys.flags.isolated and sys.dont_write_bytecode and sys.platform == 'win32'
    source, tests = ROOT / 'product/src/ai_ad_editor', ROOT / 'product/tests'
    pins = {path.relative_to(ROOT).as_posix(): sha(path) for path in [*source.glob('*.py'), *tests.glob('*.py')]}
    sys.path[:0] = [str(source.parent), str(tests)]
    import ai_ad_editor
    from ai_ad_editor.runtime import configure_local_runtime
    assert ai_ad_editor.VERSION == '0.1.65'
    configure_local_runtime()
    proof = ROOT / 'docs/validation/evidence/music-loading-20261030-r1' / ('session-startup-trace-' + args.run)
    proof.mkdir(parents=True)
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    tag = 'Local\\agent-editor-music65-trace-' + uuid.uuid4().hex
    shared = mmap.mmap(-1, CAPACITY, tagname=tag, access=mmap.ACCESS_WRITE)
    native_popen = subprocess.Popen
    children = []
    instrumentation = r'''
import mmap as _trace_mmap, struct as _trace_struct, time as _trace_time, json as _trace_json
_trace_area = _trace_mmap.mmap(-1, TRACE_CAPACITY, tagname=TRACE_TAG, access=_trace_mmap.ACCESS_WRITE)
def _trace_event(name):
    payload = _trace_json.dumps(dict(event=name, monotonic=_trace_time.monotonic()), separators=(',', ':')).encode('utf-8')
    used = _trace_struct.unpack_from('<I', _trace_area, 0)[0]
    if used + len(payload) + 9 < TRACE_CAPACITY:
        _trace_area[4+used:4+used+len(payload)+1] = payload + b'\n'
        _trace_struct.pack_into('<I', _trace_area, 0, used+len(payload)+1)
_trace_event('interpreter-ready')
'''.replace('TRACE_CAPACITY', str(CAPACITY)).replace('TRACE_TAG', repr(tag))
    observer = '''
_trace_event('cli-imported')
import os as _trace_os
from ai_ad_editor import project as _trace_project
_trace_fsync_native = _trace_os.fsync
_trace_prepare_native = _trace_project.prepare_project_transaction
def _trace_fsync(fd):
    _trace_event('fsync-begin')
    try:
        return _trace_fsync_native(fd)
    finally:
        _trace_event('fsync-end')
def _trace_prepare(*args, **kwargs):
    _trace_event('prepare-transaction-begin')
    try:
        return _trace_prepare_native(*args, **kwargs)
    finally:
        _trace_event('prepare-transaction-end')
_trace_os.fsync = _trace_fsync
_trace_project.prepare_project_transaction = _trace_prepare
'''

    def spawn(command, *positional, **options):
        arguments = list(command)
        target = '--model-session' in arguments and '-c' in arguments
        if target:
            index = arguments.index('-c') + 1
            program = arguments[index]
            assert 'from ai_ad_editor.cli import main;' in program
            prefix, tail = program.split('from ai_ad_editor.cli import main;', 1)
            arguments[index] = instrumentation + '\n' + prefix + '\nfrom ai_ad_editor.cli import main\n' + observer + '\n' + tail
        child = native_popen(arguments, *positional, **options)
        if target:
            children.append(dict(pid=child.pid, spawned_monotonic=time.monotonic()))
        return child

    suite = unittest.defaultTestLoader.loadTestsFromName(
        'test_model_session.NativeSessionTests.test_control_cli_remains_available_during_active_project_write')
    assert suite.countTestCases() == 1
    began = time.monotonic()
    try:
        with (proof / 'tests.stderr').open('w', encoding='utf-8', newline='\n') as log:
            with patch('subprocess.Popen', side_effect=spawn):
                result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        used = struct.unpack_from('<I', shared, 0)[0]
        assert used < CAPACITY - 4
        raw = bytes(shared[4:4 + used])
        (proof / 'child-events.jsonl').write_bytes(raw)
        events = [json.loads(line) for line in raw.splitlines()]
        assert len(children) == 1
        frozen = all(sha(ROOT / name) == pin for name, pin in pins.items())
        completed = []
        pending = None
        for event in events:
            if event['event'] == 'fsync-begin':
                assert pending is None
                pending = event['monotonic']
            elif event['event'] == 'fsync-end':
                assert pending is not None
                completed.append(event['monotonic'] - pending)
                pending = None
        report = dict(status='passed' if result.wasSuccessful() and frozen else 'failed',
            kind='instrumented-original-single-test', cli_version='0.1.65', tests=result.testsRun,
            failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
            frozen_equal=frozen, file_hashes=pins, children=children, events=events,
            completed_fsync_seconds=completed, last_fsync_unfinished_at_child_exit=pending is not None,
            elapsed_seconds=time.monotonic() - began, original_assertions_and_deadlines=True,
            real_fsync_preserved=True, trace_io='named anonymous Windows memory mapping; no trace file I/O in child',
            neural_music_generated=False, formal_activation=False, full_443_accepted=False)
        (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        print(json.dumps({key: value for key, value in report.items() if key not in {'file_hashes', 'events'}}), flush=True)
        return 0 if report['status'] == 'passed' else 1
    finally:
        shared.close()


if __name__ == '__main__':
    raise SystemExit(main())
