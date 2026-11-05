"""Retain a knowingly misconfigured run, verify termination, never label it passed."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/delivery66-20261106-r1'
OUT = BASE / 'source-all-r1-interruption-r1'
PID = 32376


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def guard():
    freeze = load(BASE / 'freeze-r1/verification.json')
    for group in ('file_hashes', 'formal_guard'):
        assert all(sha(ROOT / name) == pin for name, pin in freeze[group].items())
    return freeze


def process():
    command = ["powershell.exe", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process -Filter 'ProcessId=32376' | Select-Object ProcessId,ParentProcessId,CommandLine,CreationDate | ConvertTo-Json -Compress"]
    result = subprocess.run(command, capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0
    return json.loads(result.stdout.decode('utf-8-sig')) if result.stdout.strip() else None


def stop():
    guard()
    candidate = ROOT / 'docs/validation/candidates/delivery66-r3'
    report = load(candidate / 'implementation.json')
    assert report['status'] == 'complete-correction-code-not-tested'
    assert all(sha(candidate / name) == pin for name, pin in report['files'].items())
    assert report['original_suite_unchanged'] and not report['formal_activation']
    terminal = BASE / 'source-all-r1/verification.json'
    assert not terminal.exists()
    log = (BASE / 'source-all-r1/tests.stderr').read_text(encoding='utf-8')
    assert "skipped 'requires explicitly supplied existing native Rubber Band'" in log
    owner = process()
    assert owner and owner['ProcessId'] == PID and PID != os.getpid()
    command = owner['CommandLine']
    assert 'delivery66.py' in command and 'tests --run r1' in command
    OUT.mkdir()
    (OUT / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    save(OUT / 'owner-before.json', owner)
    # Never traverse numeric parent IDs: Windows can reuse a departed child's PID.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1001, False, PID)
    assert handle
    try:
        current = process()
        assert current == owner, 'Test owner changed before termination'
        assert kernel.TerminateProcess(handle, 0xC000013A)
    finally:
        kernel.CloseHandle(handle)
    save(OUT / 'stop-request.json', dict(exit_code=0, owner_pid=PID, method='verified-owner-handle-only',
        reason='known missing native dependency configuration violates zero-skip gate',
        observed_timeout=False, original_log_preserved=True, candidate_complete_before_stop=True))
    print('Stopped only the verified misconfigured test owner; retain the session exit.', flush=True)


def finish(exit_code):
    freeze = guard()
    assert process() is None, 'Original process still live'
    request = load(OUT / 'stop-request.json')
    if request['exit_code'] != 0:
        output = (OUT / 'taskkill.stdout').read_bytes().decode('gb18030', errors='replace')
        assert '成功' in output and f'PID {PID} ' in output
    (OUT / 'executed-finish.py').write_bytes(Path(__file__).read_bytes())
    terminal = BASE / 'source-all-r1/verification.json'
    assert not terminal.exists()
    log = BASE / 'source-all-r1/tests.stderr'
    text = log.read_text(encoding='utf-8')
    skipped = [line for line in text.splitlines() if '... skipped ' in line]
    assert skipped
    report = dict(status='interrupted', cli_version='0.1.66', discovered_tests=4101,
        tests=None, failures=None, errors=None, skipped=None, observed_skips=len(skipped),
        observed_skip_lines=skipped, frozen_equal=True, file_hashes=freeze['file_hashes'],
        original_assertions_preserved=True, original_log_sha256=sha(log),
        process_exit_code=exit_code, owner_pid=PID, owner_confirmed_stopped=True,
        stop_tool_exit_code=request['exit_code'], descendants_confirmed_stopped=False,
        numeric_descendant_ownership_not_assumed=True,
        reason='deliberate configuration correction after observed native-dependency skips; not an observation timeout',
        original_log_preserved=True, formal_activation=False, source_fallback=None,
        human_listening=False, natural_quality_accepted=False, full_product_goal_closed=False)
    save(terminal, report)
    save(OUT / 'verification.json', report)
    print(json.dumps({key: report[key] for key in ('status', 'observed_skips', 'owner_confirmed_stopped', 'formal_activation')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('stop', 'finish'))
    parser.add_argument('--exit-code', type=int)
    args = parser.parse_args()
    assert os.name == 'nt' and sys.dont_write_bytecode
    if args.action == 'stop':
        stop()
    else:
        assert args.exit_code is not None
        finish(args.exit_code)
