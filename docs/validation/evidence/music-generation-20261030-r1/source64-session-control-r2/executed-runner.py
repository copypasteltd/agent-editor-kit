"""Reproduce one observed compatibility failure without relaxing its assertions."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    assert args.run.isalnum() and sys.dont_write_bytecode and sys.flags.isolated
    source, tests = ROOT / 'product/src/ai_ad_editor', ROOT / 'product/tests'
    pins = {p.relative_to(ROOT).as_posix():sha(p) for p in [*source.glob('*.py'), *tests.glob('*.py')]}
    assert len(list(source.glob('*.py'))) == 288
    sys.path[:0] = [str(source.parent), str(tests)]
    import ai_ad_editor
    assert ai_ad_editor.VERSION == '0.1.64' and Path(ai_ad_editor.__file__).resolve() == source / '__init__.py'
    proof = ROOT / ('docs/validation/evidence/music-generation-20261030-r1/source64-session-control-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    name = 'test_model_session.NativeSessionTests.test_control_cli_remains_available_during_active_project_write'
    suite = unittest.defaultTestLoader.loadTestsFromName(name)
    assert suite.countTestCases() == 1
    original_spawn = subprocess.Popen
    traces = []
    threads = []

    def spawn(command, *positional, **options):
        command = list(command)
        target = '--model-session' in command and '-c' in command
        if target and args.trace:
            index = command.index('-c') + 1
            tracefile = str(proof / 'child-startup.jsonl')
            prelude = ('import time,json;from pathlib import Path;'
                + 'tracefile=Path(' + repr(tracefile) + ');'
                + 'trace=lambda phase:tracefile.open("a",encoding="utf8").write(json.dumps(dict(phase=phase,monotonic=time.monotonic()))+"\\n");'
                + 'trace("interpreter-ready");')
            command[index] = prelude + command[index].replace('from ai_ad_editor.cli import main',
                'trace("before-cli-import");from ai_ad_editor.cli import main;trace("after-cli-import")')
        child = original_spawn(command, *positional, **options)
        if target and args.trace:
            from diagnose_music64_process import identity, TOOL_PIN
            tool = ROOT / 'local/agent-ffmpeg/music64-process-diagnostic-r1/py-spy.exe'
            assert sha(tool) == TOOL_PIN
            before = identity(child.pid)

            def capture():
                time.sleep(10)
                if child.poll() is not None or identity(child.pid) != before:
                    return
                with (proof / 'child-stack.stdout').open('wb') as out, (proof / 'child-stack.stderr').open('wb') as err:
                    proc = original_spawn([str(tool), 'dump', '--pid', str(child.pid)],
                        stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
                    code = proc.wait(timeout=15)
                traces.append(dict(before=before, dump_exit_code=code, generation_child=True))
            thread = threading.Thread(target=capture, daemon=True)
            thread.start()
            threads.append(thread)
        return child

    began = time.monotonic()
    with (proof / 'tests.stderr').open('w', encoding='utf-8', newline='\n') as log:
        with patch('subprocess.Popen', side_effect=spawn) if args.trace else patch('subprocess.Popen', original_spawn):
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    for thread in threads:
        thread.join(timeout=30)
    frozen = all(sha(ROOT / path) == pin for path,pin in pins.items())
    report = dict(status='passed' if result.wasSuccessful() and frozen and not result.skipped else 'failed',
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        target=name, cli_version=ai_ad_editor.VERSION, frozen_equal=frozen, elapsed_seconds=time.monotonic() - began,
        test_assertions_changed=False, process_deadlines_changed=False,
        interpreter=sys.executable, file_hashes=pins, full_431_group_accepted=False, music_generation_accepted=False)
    report.update(startup_trace_requested=args.trace, startup_traces=traces,
                  command_instrumentation='phase timestamps only' if args.trace else None)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'file_hashes'}), flush=True)
    print((proof / 'tests.stderr').read_text(encoding='utf-8'), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
