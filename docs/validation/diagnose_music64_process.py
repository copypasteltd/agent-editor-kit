"""Capture a bounded read-only Python stack from the current owned music worker."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
URL = 'https://files.pythonhosted.org/packages/6f/ed/1409cdb557e558a6c98003ab12fdd4284699e158c167c187cb0f124eea4c/py_spy-0.4.2-py2.py3-none-win_amd64.whl'
PIN = '8b06a353c177677e4e1701b288d8c58e2f8d4208ee81a8048d9f72ba800918f8'
TOOL_PIN = '6e83ab095f40453742d01a2719a178f308534015da519ec0659d2584139dc995'
NATIVE = Path('E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe')


def identity(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(system), ctypes.byref(user)):
            raise ctypes.WinError(ctypes.get_last_error())
        length = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(length.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        return dict(pid=pid, created_filetime=(created.dwHighDateTime << 32) | created.dwLowDateTime,
                    executable=path.value)
    finally:
        kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--tool', type=Path)
    args = parser.parse_args()
    assert os.name == 'nt' and sys.dont_write_bytecode and args.run.isalnum()
    work = args.work.resolve()
    assert work.is_relative_to((ROOT / 'local/agent-ffmpeg').resolve())
    request = json.loads((work / 'request.json').read_bytes())
    progress = json.loads((work / 'progress.json').read_bytes())
    pid = progress['worker_pid']
    assert isinstance(pid, int) and pid > 0
    before = identity(pid)
    assert Path(before['executable']).resolve() == NATIVE.resolve()
    # The PID must still name the current music worker with this exact request.
    command = f'Get-CimInstance Win32_Process -Filter "ProcessId={pid}" | Select-Object -ExpandProperty CommandLine'
    queried = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
        capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    actual = queried.stdout.decode('utf-8', errors='replace')
    if 'music_generation_worker.py' not in actual:
        # PowerShell's legacy console encoding may encode the Chinese path.
        actual = queried.stdout.decode('gb18030', errors='replace')
    assert queried.returncode == 0 and 'music_generation_worker.py' in actual
    assert work.name in actual and 'request.json' in actual
    assert identity(pid) == before
    private = ROOT / ('local/agent-ffmpeg/music64-process-diagnostic-' + args.run)
    private.mkdir()
    proof = ROOT / ('docs/validation/evidence/music-generation-20261030-r1/process-diagnostic-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    # Standalone wheel extraction into E: only; no pip or global environment change.
    if args.tool:
        tool = args.tool.resolve()
        assert tool.is_relative_to((ROOT / 'local/agent-ffmpeg').resolve())
    else:
        with urllib.request.urlopen(URL, timeout=45) as response:
            archive = response.read(2 * 1024**2 + 1)
        assert len(archive) == 1894002 and hashlib.sha256(archive).hexdigest() == PIN
        (private / 'py-spy.whl').write_bytes(archive)
        with zipfile.ZipFile(io.BytesIO(archive)) as wheel:
            names = [n for n in wheel.namelist() if n.endswith('/py-spy.exe')]
            assert len(names) == 1
            tool = private / 'py-spy.exe'
            tool.write_bytes(wheel.read(names[0]))
    assert hashlib.sha256(tool.read_bytes()).hexdigest() == TOOL_PIN
    assert identity(pid) == before
    result = subprocess.run([str(tool), 'dump', '--pid', str(pid)], capture_output=True,
        timeout=45, creationflags=subprocess.CREATE_NO_WINDOW, cwd=private)
    (proof / 'stack.stdout').write_bytes(result.stdout)
    (proof / 'stack.stderr').write_bytes(result.stderr)
    after = identity(pid)
    report = dict(status='captured' if result.returncode == 0 and after == before else 'failed',
        tool='py-spy0.4.2', tool_source='https://pypi.org/project/py-spy/0.4.2/',
        archive_url=URL, archive_sha256=PIN, tool_sha256=TOOL_PIN, verified_tool_reused=bool(args.tool),
        worker_before=before, worker_after=after, request_sha256=hashlib.sha256((work / 'request.json').read_bytes()).hexdigest(),
        phase_observed=progress['phase'], exit_code=result.returncode, local_variables_requested=False,
        global_environment_changed=False, model_forwards_proven=False, generation_accepted=False,
        stack_stdout_sha256=hashlib.sha256(result.stdout).hexdigest(), stack_stderr_sha256=hashlib.sha256(result.stderr).hexdigest())
    (proof / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report['status'] == 'captured' else 1


if __name__ == '__main__':
    raise SystemExit(main())
