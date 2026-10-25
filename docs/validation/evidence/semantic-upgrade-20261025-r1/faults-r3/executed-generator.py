"""Native semantic-upgrade timeout/cancel checks; no model or timing hooks."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-upgrade-20261025-r1'
LIGHT = 'C:/Python313/python.exe'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


class IO(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ('read_operations', 'write_operations',
        'other_operations', 'read_bytes', 'write_bytes', 'other_bytes')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--adapter-id', default='active15')
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    installed, project = args.installed.resolve(strict=True), args.project.resolve(strict=True)
    out = BASE / args.run; out.mkdir(parents=True, exist_ok=False)
    (out / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    spec = ROOT / 'docs/specs/语义工程运行时升级契约_20261025.md'
    (out / 'frozen-spec.md').write_bytes(spec.read_bytes())
    prefix = [LIGHT, '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py')]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO)]
    kernel.GetProcessIoCounters.restype = wintypes.BOOL
    code = {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    (out / 'product-files.json').write_text(json.dumps(code, indent=2)+'\n', encoding='utf-8', newline='\n')
    metadata = {name: sha(project / name) for name in ('project.json', 'rights-ledger.json')}
    assets = {p.relative_to(project).as_posix(): sha(p) for p in (project / 'assets').rglob('*') if p.is_file()}
    report = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
        installed=str(installed), project=str(project), specification_sha256=sha(spec),
        native_windows=True, virtualization=False, timing_or_model_hooks=False,
        performance_benchmark=False, cases=[], human_quality_acceptance=False)
    save(out / 'verification.json', report)
    try:
        for name, cancel, budget, wall_gate, require_read, threshold in (
                ('startup-timeout',False,1,8,False,None),('read-timeout',False,5,12,True,None),
                ('early-cancel',True,600,None,False,64*1024**2),('read-cancel',True,600,None,True,512*1024**2)):
            case = out / name; case.mkdir()
            marker = case / 'cancel marker'
            command = [*prefix, 'project', 'upgrade-semantic', '--project', str(project),
                '--adapter-id', args.adapter_id, '--new-adapter-id', 'fault15'+str(int(cancel)),
                '--id-prefix', 'fault15'+str(int(cancel)),
                '--timeout-seconds', str(budget)]
            if cancel:
                command += ['--cancel-file', str(marker)]
            started = time.monotonic()
            cancelled_at, read_bytes = None, None
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                while process.poll() is None:
                    now = time.monotonic()
                    if now - started > 45:
                        raise TimeoutError('Owned CLI did not terminate within the fixed observation limit')
                    if cancel and cancelled_at is None:
                        counters = IO()
                        if not kernel.GetProcessIoCounters(wintypes.HANDLE(int(process._handle)), ctypes.byref(counters)):
                            if process.poll() is not None:
                                break
                            raise ctypes.WinError(ctypes.get_last_error())
                        if counters.read_bytes > threshold:
                            read_bytes = counters.read_bytes
                            marker.touch(exist_ok=False)
                            cancelled_at = time.monotonic()
                            save(case / 'actual-cancel-observation.json', dict(pid=process.pid,
                                observed_read_bytes=read_bytes, elapsed_before_marker=cancelled_at-started,
                                marker=str(marker), threshold_bytes=threshold))
                    time.sleep(.01)
                stdout, stderr = process.communicate(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()  # Only this verified live, owned Popen handle.
                    process.communicate(timeout=15)
            finished = time.monotonic()
            (case / 'stdout.json').write_bytes(stdout); (case / 'stderr.txt').write_bytes(stderr)
            value = json.loads(stdout.decode('utf-8-sig'))
            assert value['provenance']['cli_version'] == '0.1.15'
            error = value['errors'][0]
            actual = dict(case=name, argv=command, pid=process.pid, exit_code=process.returncode,
                elapsed_seconds=finished-started, cancel_to_exit_seconds=finished-cancelled_at if cancelled_at else None,
                observed_read_bytes_at_cancel=read_bytes, error=error, deadline_seconds=budget, wall_gate_seconds=wall_gate, require_integrity_read=require_read,
                stdout_sha256=sha(case / 'stdout.json'), stderr_sha256=sha(case / 'stderr.txt'))
            save(case / 'verification.json', actual)
            report['cases'].append(actual); save(out / 'verification.json', report)
            assert not value['ok'] and error['code'] == ('CANCELLED' if cancel else 'PROCESS_TIMEOUT'), value
            assert process.returncode == (8 if cancel else 6)
            if require_read or 'diagnostics' in error:
                assert error['diagnostics']['phase'] == 'integrity-read'
                assert error['diagnostics']['bytes_processed'] > 0
                assert error['diagnostics']['partial_digest_discarded'] and not error['diagnostics']['digest_cached']
            assert (cancelled_at is not None and actual['cancel_to_exit_seconds'] <= 3) if cancel else actual['elapsed_seconds'] <= wall_gate
            assert metadata == {n: sha(project / n) for n in metadata}
            assert assets == {p.relative_to(project).as_posix(): sha(p) for p in (project / 'assets').rglob('*') if p.is_file()}
            print(json.dumps({key: actual[key] for key in ('case', 'elapsed_seconds', 'cancel_to_exit_seconds')}) , flush=True)
        assert code == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
        report.update(status='passed', finished_at_utc=datetime.now(timezone.utc).isoformat(),
            installed_bytes_unchanged=True, original_assets_and_metadata_unchanged=True,
            timed_model_forwards=0, timing_gates=dict(startup_timeout_total_seconds=8, read_timeout_total_seconds=12, cancel_to_exit_seconds=3))
        save(out / 'verification.json', report)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc)); save(out / 'verification.json', report)
        raise


if __name__ == '__main__':
    main()
