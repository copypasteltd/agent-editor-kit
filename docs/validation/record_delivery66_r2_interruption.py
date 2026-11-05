"""Preserve a missing-owner regression without inventing an exit code or result."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/delivery66-20261106-r1'


def main():
    folder = BASE / 'source-all-r2'
    target = folder / 'verification.json'
    retained = BASE / 'source-all-r2-interruption-r1'
    if target.exists() or retained.exists():
        raise ValueError('Preserve existing terminal/interruption evidence')
    query = "@(Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | Where-Object { $_.CommandLine -like '*delivery66.py*' } | Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine) | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', query], cwd=ROOT,
        capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode or result.stdout.strip() not in (b'', b'[]'):
        raise ValueError('A live runner may remain; do not classify or restart it')
    runner = runpy.run_path(str(ROOT / 'docs/validation/delivery66.py'))
    freeze = json.loads((BASE / 'freeze-r2/verification.json').read_bytes())
    if runner['pins']() != freeze['file_hashes'] or runner['formal_guard']() != freeze['formal_guard']:
        raise ValueError('The original frozen state changed; investigate separately')
    raw = (folder / 'tests.stderr').read_bytes()
    lines = raw.decode('utf-8', errors='replace').splitlines()
    report = dict(status='interrupted', cli_version='0.1.66', discovered_tests=4110,
        tests=None, failures=None, errors=None, skipped=None,
        observed_skip_lines=[line for line in lines if ' ... skipped' in line],
        observed_failure_lines=[line for line in lines if ' ... FAIL' in line or ' ... ERROR' in line],
        original_owner_pid=22948, original_owner_started_local='2026-11-06T05:57:49+08:00',
        original_tool_session=75402, tool_session_unavailable=True,
        owner_confirmed_absent=True, no_live_delivery66_runner_observed=True,
        observed_at_utc=datetime.now(timezone.utc).isoformat(),
        exit_code=None, interruption_cause='unknown', numeric_descendant_ownership_not_assumed=True,
        descendants_confirmed_stopped=False, termination_requested_by_this_recorder=False,
        frozen_equal=True, file_hashes=freeze['file_hashes'], original_log_preserved=True,
        log_sha256=hashlib.sha256(raw).hexdigest(), terminal_test_summary_present=False,
        formal_activation=False, model_inference_claimed=False)
    retained.mkdir(parents=True)
    (retained / 'executed-recorder.py').write_bytes(Path(__file__).read_bytes())
    (retained / 'live-runner-query.stdout').write_bytes(result.stdout)
    (retained / 'live-runner-query.stderr').write_bytes(result.stderr)
    encoded = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (retained / 'verification.json').write_bytes(encoded)
    with target.open('xb') as stream:
        stream.write(encoded)
    print(json.dumps({key:value for key,value in report.items() if key != 'file_hashes'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
