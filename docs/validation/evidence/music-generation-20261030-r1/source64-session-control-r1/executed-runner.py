"""Reproduce one observed compatibility failure without relaxing its assertions."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
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
    began = time.monotonic()
    with (proof / 'tests.stderr').open('w', encoding='utf-8', newline='\n') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    frozen = all(sha(ROOT / path) == pin for path,pin in pins.items())
    report = dict(status='passed' if result.wasSuccessful() and frozen and not result.skipped else 'failed',
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        target=name, cli_version=ai_ad_editor.VERSION, frozen_equal=frozen, elapsed_seconds=time.monotonic() - began,
        test_assertions_changed=False, process_deadlines_changed=False,
        interpreter=sys.executable, file_hashes=pins, full_431_group_accepted=False, music_generation_accepted=False)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'file_hashes'}), flush=True)
    print((proof / 'tests.stderr').read_text(encoding='utf-8'), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
