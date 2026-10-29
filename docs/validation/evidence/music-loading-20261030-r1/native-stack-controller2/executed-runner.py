"""Capture one read-only stack after checking the exact owned native process."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--script', choices=['probe_music65_reader.py', 'music_generation_worker.py', 'run.py'], required=True)
    parser.add_argument('--native-executable', type=Path, required=True)
    parser.add_argument('--project', type=Path)
    args = parser.parse_args()
    assert args.run.isalnum() and args.pid > 0 and sys.dont_write_bytecode
    helper_path = ROOT / 'docs/validation/diagnose_music64_process.py'
    spec = importlib.util.spec_from_file_location('owned_music_identity', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    identity = helper.identity
    before = identity(args.pid)
    assert Path(before['executable']).resolve() == args.native_executable.resolve()
    queried = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        '[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); '
        'Get-CimInstance Win32_Process -Filter "ProcessId=' + str(args.pid) + '" | Select-Object -ExpandProperty CommandLine'],
        cwd=ROOT, capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    command = queried.stdout.decode('utf-8', errors='replace')
    assert queried.returncode == 0 and args.script in command and '-B' in command and '-I' in command
    if args.script == 'run.py':
        expected = ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.63/final-r1/installed/run.py'
        assert args.project and args.project.resolve().is_relative_to((ROOT / 'local/agent-ffmpeg').resolve())
        normalized = command.replace('\\', '/').casefold()
        assert expected.as_posix().casefold() in normalized and 'music generate --project' in normalized
        assert args.project.resolve().as_posix().casefold() in normalized
    assert identity(args.pid) == before
    tool = ROOT / 'local/agent-ffmpeg/music64-process-diagnostic-r1/py-spy.exe'
    assert hashlib.sha256(tool.read_bytes()).hexdigest() == helper.TOOL_PIN
    proof = ROOT / 'docs/validation/evidence/music-loading-20261030-r1' / ('native-stack-' + args.run)
    proof.mkdir(parents=True)
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    (proof / 'command.stdout').write_bytes(queried.stdout)
    (proof / 'command.stderr').write_bytes(queried.stderr)
    with (proof / 'stack.stdout').open('xb') as out, (proof / 'stack.stderr').open('xb') as err:
        result = subprocess.run([str(tool), 'dump', '--pid', str(args.pid)], stdout=out, stderr=err,
            timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    after = identity(args.pid)
    report = dict(status='captured' if result.returncode == 0 and before == after else 'failed',
        before=before, after=after, process_identity_equal=before == after,
        script=args.script, dump_exit_code=result.returncode, requested_locals=False,
        tool_sha256=helper.TOOL_PIN, model_generation_acceptance=False,
        sample_does_not_establish_complete_duration_cause=True)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report), flush=True)
    return 0 if report['status'] == 'captured' else 1


if __name__ == '__main__':
    raise SystemExit(main())
