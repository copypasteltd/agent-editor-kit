"""Finish authorized local CLI63 rollout only after terminal staged acceptance."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/job-enumeration-20261029-r1'
PYTHON = 'C:/Python313/python.exe'


def load(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    temporary = p.with_name('.' + p.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(p)


def active(pid):
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.OpenProcess(0x100000 | 0x1000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:
            return False
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        code = wintypes.DWORD()
        if not api.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return code.value == 259
    finally:
        api.CloseHandle(handle)


def main():
    assert load(ROOT / 'local/agent-ffmpeg/source63-recovery-optical-commit-r2/verification.json')['status'] == 'passed'
    assert load(ROOT / 'docs/validation/evidence/optical-pack-gallery-docs-20261029-r1/verification.json')['status'] == 'passed'
    installation = load(BASE / 'installation-candidate-r1/verification.json')
    old_files = installation['registered_skill_file_hashes']
    assert all(sha(Path(p)) == h for p, h in old_files.items())
    contracts = load(BASE / 'installed63-contracts-r2/verification.json')
    assert contracts['status'] == 'passed' and contracts['tests'] == 406
    assert contracts['failures'] == contracts['errors'] == contracts['skipped'] == 0
    assert all(sha(ROOT / n) == h for n, h in contracts['file_hashes'].items())
    assert sha(ROOT / 'docs/validation/activate_source63_skill.py') == load(BASE / 'activation-rollback-r4/verification.json')['script_sha256']
    out = BASE / 'formal-finish-controller-r1'
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    current = dict(phase='waiting-for-terminal-staged-acceptance', pid=None)
    calls = []
    stop = threading.Event()
    lock = threading.Lock()
    started = time.monotonic()

    def progress():
        with lock:
            value = dict(status='running', timestamp_utc=datetime.now(timezone.utc).isoformat(),
                         elapsed_seconds=time.monotonic() - started, current=dict(current), calls=list(calls))
        save(out / 'progress.json', value)

    def heartbeat():
        while not stop.wait(5):
            progress()

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    result = None
    try:
        staged_receipt = BASE / 'recovery-controller-r2/verification.json'
        while not staged_receipt.is_file():
            assert active(28192), 'Earlier controller ended without a terminal receipt; do not activate'
            assert time.monotonic() - started < 7200, 'Staged acceptance wait exceeded its bound'
            assert all(sha(Path(p)) == h for p, h in old_files.items())
            stop.wait(5)
        staged = load(staged_receipt)
        assert staged['status'] == 'passed' and staged['actual_staged_Skill_passed']
        assert not staged['formal_activation'] and staged['original_r1_preserved']
        assert load(BASE / 'skill-controller-r1/verification.json')['status'] == 'passed'
        # The earlier controller still checks the old namespace in its finalizer.
        # Wait for that owner to exit before changing the formal files.
        exit_deadline = time.monotonic() + 60
        while active(28192):
            assert time.monotonic() < exit_deadline
            stop.wait(1)
        prefix = [PYTHON, '-E', '-B', '-u', '-X', 'utf8']
        def command(script, *args):
            return [*prefix, str(ROOT / 'docs/validation' / script), *args]
        steps = [
            ('activation-dry-run', command('activate_source63_skill.py', '--run', 'r1')),
            ('activation-apply', command('activate_source63_skill.py', '--run', 'r1', '--apply')),
            ('registered-cases', command('run_source63_registered_acceptance.py')),
            ('registered-docs', command('complete_source63_rollout_docs.py', '--phase', 'registered')),
            ('kit-build', command('build_source63_final_kit.py', '--run', 'r1')),
            ('kit-independent', [PYTHON, '-I', '-S', '-B', '-u', '-X', 'utf8',
                str(ROOT / 'docs/validation/verify_source63_final_kit.py'), '--run', 'r1', '--package-json',
                str(BASE / 'formal-kit-build-r1/package.stdout')]),
            ('kit-docs', command('complete_source63_rollout_docs.py', '--phase', 'kit')),
        ]
        for phase, argv in steps:
            assert all(sha(ROOT / n) == h for n, h in contracts['file_hashes'].items())
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
        assert load(BASE / 'registered-controller-r1/verification.json')['status'] == 'passed'
        assert load(BASE / 'formal-kit-r1/verification.json')['status'] == 'passed'
        assert load(BASE / 'rollout-kit-docs-r1/verification.json')['README_rows'] == 528
        result = dict(status='passed', cli_version='0.1.63', calls=calls,
                      formal='0.1.63/local61/r58', actual_registered_cases_passed=True,
                      independently_accepted_kit=True, native_windows=True, virtualization=False,
                      commit_pending=True, public_release_changed=False, full_goal_closed=False)
    except BaseException as error:
        result = dict(status='failed', error=repr(error), calls=calls, full_goal_closed=False)
        raise
    finally:
        stop.set()
        thread.join(timeout=10)
        if result is not None:
            save(out / 'verification.json', result)
            save(out / 'progress.json', result)
            print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
