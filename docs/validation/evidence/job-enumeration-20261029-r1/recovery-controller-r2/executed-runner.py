"""Resume only after the interrupted CLI63 owners are authoritatively absent.

Keep r1 logs immutable. Reuse the five completed groups; rerun the complete
406-case installed suite as r2, then perform the real cases and staged Skill.
"""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/job-enumeration-20261029-r1'
C = 'C:/Python313/python.exe'
D = 'D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'
OLD_PIDS = (30156, 34996, 39660, 29408)


def load(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    temporary = p.with_name('.' + p.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(p)


def absent(pid):
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.OpenProcess(0x100000 | 0x1000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:
            return True
        raise ctypes.WinError(error)
    try:
        code = wintypes.DWORD()
        if not api.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return code.value != 259
    finally:
        api.CloseHandle(handle)


def main():
    assert all(absent(pid) for pid in OLD_PIDS), 'An original owner is still active; do not duplicate it'
    assert not (BASE / 'installed63-contracts-r1/verification.json').exists()
    assert not (BASE / 'delivery-pipeline-r1/verification.json').exists()
    installation = load(BASE / 'installation-candidate-r1/verification.json')
    assert installation['status'] == 'installed-and-byte-verified'
    assert installation['cli_version'] == '0.1.63'
    installed = installation['installed']
    protected = installation['registered_skill_file_hashes']
    assert all(sha(Path(p)) == h for p, h in protected.items())
    for group, count in [('bootstrap', 31), ('loop', 37), ('control', 26), ('selection', 57), ('semantic', 104)]:
        r = load(BASE / ('installed63-' + group + '-r1/verification.json'))
        assert r['status'] == 'passed' and r['tests'] == count and r['frozen_equal']
        assert r['failures'] == r['errors'] == r['skipped'] == 0
        assert all(sha(ROOT / p) == h for p, h in r['file_hashes'].items())
    out = BASE / 'recovery-controller-r2'
    out.mkdir(exist_ok=False)
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    interrupted = [BASE / 'installed63-contracts-r1' / n for n in
                   ('executed-runner.py', 'isolated-dependencies.stdout', 'isolated-dependencies.stderr', 'tests.stderr')]
    interrupted += [BASE / 'delivery-pipeline-r1/progress.json',
                    BASE / 'installed-controller-r1/calls.json',
                    BASE / 'skill-wait-controller-r1/progress.json']
    pins = {str(p): sha(p) for p in interrupted}
    save(out / 'interruption.json', dict(status='interrupted-without-terminal-receipt',
         checked_at_utc=datetime.now(timezone.utc).isoformat(), original_pids_absent=list(OLD_PIDS),
         preserved_original_files=pins, original_complete_contract_acceptance=False,
         interruption_cause='not established', formal_activation=False))
    calls, current = [], {}
    stop = threading.Event()
    lock = threading.Lock()
    started = time.monotonic()
    def progress():
        with lock:
            value = dict(status='running', timestamp_utc=datetime.now(timezone.utc).isoformat(),
                         elapsed_seconds=time.monotonic() - started, calls=list(calls),
                         current=dict(current), formal_activation=False)
        save(out / 'progress.json', value)
    def heartbeat():
        while not stop.wait(5):
            progress()
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    steps = [('installed406-r2', D, '-I', 'run_source63_regressions.py',
              ['--group', 'contracts', '--run', 'r2', '--installed', installed])]
    for script in ('run_source63_gpu_case.py', 'run_installed63_loop_case.py', 'run_installed63_lipsync_case.py'):
        steps.append((script, C, '-E', script, ['--run', 'r1', '--installed', installed]))
    steps += [('stage', C, '-E', 'stage_source63_skill.py', ['--run', 'r1']),
              ('staged-Skill', C, '-E', 'run_source63_skill_acceptance.py', [])]
    try:
        for phase, python, isolation, script, args in steps:
            assert all(sha(Path(p)) == h for p, h in protected.items())
            assert all(sha(Path(p)) == h for p, h in pins.items())
            argv = [python, isolation, '-B', '-u', '-X', 'utf8', str(ROOT / 'docs/validation' / script), *args]
            with (out / (phase + '.stdout')).open('wb') as stdout, (out / (phase + '.stderr')).open('wb') as stderr:
                child = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr,
                                         creationflags=subprocess.CREATE_NO_WINDOW)
                with lock:
                    current.update(phase=phase, pid=child.pid, argv=argv,
                                   started_at_utc=datetime.now(timezone.utc).isoformat())
                progress()
                code = child.wait()
            with lock:
                calls.append(dict(phase=phase, exit_code=code))
            save(out / 'calls.json', calls)
            print(json.dumps(calls[-1]), flush=True)
            assert code == 0, (phase, code)
        assert load(BASE / 'installed63-contracts-r2/verification.json')['status'] == 'passed'
        assert load(BASE / 'skill-controller-r1/verification.json')['status'] == 'passed'
        assert all(sha(Path(p)) == h for p, h in protected.items())
        assert all(sha(Path(p)) == h for p, h in pins.items())
        result = dict(status='passed', calls=calls, original_r1_preserved=True,
                      installed_complete_contract_run='r2', actual_staged_Skill_passed=True,
                      formal_activation=False, registered_cases_pending=True, full_goal_closed=False)
        save(out / 'verification.json', result)
        print(json.dumps(result), flush=True)
        return 0
    except BaseException as exc:
        save(out / 'verification.json', dict(status='failed', calls=calls, error=repr(exc),
             formal_activation=False, full_goal_closed=False))
        raise
    finally:
        stop.set()
        thread.join(timeout=10)


if __name__ == '__main__':
    raise SystemExit(main())
