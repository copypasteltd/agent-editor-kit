"""Preserve the real failed job and verify its cleanup without reusing a PID."""
import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'


def load(path):
    return json.loads(path.read_bytes())


def main():
    case = BASE / 'actual-piano3'
    failed = load(case / 'verification.json')
    envelope = load(case / 'generate.stdout')
    assert failed['status'] == 'failed' and envelope['errors'][0]['code'] == 'MUSIC_GENERATION_TIMEOUT'
    project = ROOT / 'local/agent-ffmpeg/music-generation64-piano3/project'
    receipt = envelope['errors'][0]['diagnostics']
    manifest = project / receipt['manifest']
    assert 'sha256:' + hashlib.sha256(manifest.read_bytes()).hexdigest() == receipt['manifest_sha256']
    diagnostic = load(manifest)
    worker = next(p for p in diagnostic['processes'] if p['role'] == 'worker')
    assert worker['state'] == 'terminated_by_cleanup' and worker['final_exit']['raw'] == 1
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.GetProcessTimes.argtypes = [w.HANDLE, *([ctypes.POINTER(w.FILETIME)] * 4)]
    kernel.GetProcessTimes.restype = w.BOOL
    kernel.WaitForSingleObject.argtypes, kernel.WaitForSingleObject.restype = [w.HANDLE, w.DWORD], w.DWORD
    handle = kernel.OpenProcess(0x1000 | 0x100000, False, worker['pid'])
    reused, original_alive = False, False
    if handle:
        try:
            created, exited, system, user = (w.FILETIME() for _ in range(4))
            assert kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(system), ctypes.byref(user))
            timestamp = (((created.dwHighDateTime << 32) | created.dwLowDateTime) / 10_000_000 - 11644473600)
            started = datetime.fromisoformat(worker['started_at_utc']).timestamp()
            reused = timestamp > started + 5
            original_alive = not reused and kernel.WaitForSingleObject(handle, 0) == 258
        finally:
            kernel.CloseHandle(handle)
    else:
        assert ctypes.get_last_error() == 87, ctypes.get_last_error()
    assert not original_alive
    metadata = load(project / 'project.json')
    assert not metadata['assets'] and not (project / 'assets/derived/piano.wav').exists()
    assert not list((project / 'cache/managed-jobs').iterdir())
    out = BASE / 'timeout-piano3-r1'
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    for name in ('manifest.json', *diagnostic['files']):
        assert '/' not in name and '\\' not in name
        data = (manifest.parent / name).read_bytes()
        assert len(data) < 65536
        (out / name).write_bytes(data)
    calls = load(case / 'calls.json')
    report = dict(status='passed', acceptance='actual-timeout-cleanup-only', cli_version='0.1.64',
        actual_generation_status='failed', actual_generation_error='MUSIC_GENERATION_TIMEOUT',
        original_worker_exited=True, original_pid_reused=reused, process_cleanup=worker,
        assets_after_failure=0, output_published=False, managed_workspace_empty=True,
        pre_generation_metadata_hashes_persisted=False, complete_metadata_byte_rollback_accepted=False,
        command_elapsed_seconds=next(c['elapsed_seconds'] for c in calls if c['name'] == 'generate'),
        worker_budget_seconds=1800, last_reported_phase=diagnostic['progress']['phase'],
        root_cause=diagnostic['root_cause'], model_result_observed=False,
        inference_time_measured=False, musical_quality_accepted=False,
        checked_at_utc=datetime.now(timezone.utc).isoformat(),
        original_case_sha256=hashlib.sha256((case / 'verification.json').read_bytes()).hexdigest())
    (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
