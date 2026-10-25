"""Freeze and run meaningful recovery/semantic contracts or the full CLI scope."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-control-20261025-r1/tests'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--scope', choices=('trees', 'contracts', 'cli'), required=True)
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    out = BASE / args.run; out.mkdir(parents=True, exist_ok=False)
    (out / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    source = ROOT / 'product/src/ai_ad_editor'
    package = args.installed.resolve() / 'site/ai_ad_editor' if args.installed else source
    before = {p.name: sha(p) for p in source.glob('*.py')}
    assert before == {p.name: sha(p) for p in package.glob('*.py')}
    tests = (['test_execution_control.py', 'test_artifact_locks.py'] if args.scope == 'trees' else ['test_cli.py'] if args.scope == 'cli' else
        ['test_execution_control.py', 'test_artifact_locks.py', 'test_semantic.py', 'test_semantic_decisions.py', 'test_semantic_package.py', 'test_semantic_jobs.py',
         'test_job_recovery.py', 'test_native_job_start.py', 'test_stem_separation.py', 'test_dubbing.py'])
    runner = out / 'run.py'
    runner.write_text('import json, sys, unittest\n'
        + 'sys.path[:0] = ' + repr([str(package.parent), str(ROOT / 'product/tests')]) + '\n'
        + 'suite=unittest.TestSuite()\n'
        + 'for pattern in ' + repr(tests) + ': suite.addTests(unittest.defaultTestLoader.discover('
        + repr(str(ROOT / 'product/tests')) + ', pattern=pattern))\n'
        + 'result=unittest.TextTestRunner(verbosity=2).run(suite)\n'
        + 'print("AEK_RESULT="+json.dumps(dict(methods=result.testsRun,skipped=len(result.skipped),'
        + 'failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful())))\n'
        + 'raise SystemExit(0 if result.wasSuccessful() else 1)\n', encoding='utf8', newline='\n')
    environment = dict(os.environ)
    temp = ROOT / 'workspace/semantic-control-20261025-tests' / args.run
    temp.mkdir(parents=True, exist_ok=False)
    environment.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1')
    started = datetime.now(timezone.utc).isoformat()
    with (out / 'tests.log').open('xb') as stream:
        result = subprocess.run([sys.executable, '-E', '-B', '-u', '-X', 'utf8', str(runner)],
            cwd=ROOT, env=environment, stdout=stream, stderr=subprocess.STDOUT, timeout=3600,
            creationflags=subprocess.CREATE_NO_WINDOW)
    log = (out / 'tests.log').read_text('utf8')
    terminal = [line.removeprefix('AEK_RESULT=') for line in log.splitlines() if line.startswith('AEK_RESULT=')]
    report = dict(status='passed' if result.returncode == 0 and terminal else 'failed',
        scope=args.scope, installed=str(args.installed) if args.installed else None,
        started_at_utc=started, finished_at_utc=datetime.now(timezone.utc).isoformat(),
        exit_code=result.returncode, source_files=len(before),
        frozen_equal=before == {p.name: sha(p) for p in source.glob('*.py')},
        installed_frozen_equal=before == {p.name: sha(p) for p in package.glob('*.py')},
        log_sha256=sha(out / 'tests.log'), model_quality_claim=False,
        result=json.loads(terminal[-1]) if terminal else None)
    (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    raise SystemExit(0 if report['status'] == 'passed' and report['frozen_equal'] else 1)


if __name__ == '__main__':
    main()
