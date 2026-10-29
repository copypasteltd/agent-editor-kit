"""Run matching CLI54 gates against only the independently installed package."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--group', choices=('deadline', 'selection', 'semantic'), required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--cli-version', choices=('0.1.54', '0.1.55'), default='0.1.54')
    parser.add_argument('--evidence-series', default='ad-selection-20261029-r1')
    args = parser.parse_args()
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    assert args.run.replace('-', '').isalnum()
    assert args.evidence_series.replace('-', '').isalnum()
    scratch = ROOT/'local/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ['TEMP'] = os.environ['TMP'] = str(scratch)
    import tempfile
    tempfile.tempdir = str(scratch)
    installed = args.installed.resolve()
    site = installed/'site'
    package = site/'ai_ad_editor'
    source = ROOT/'product/src/ai_ad_editor'
    tests = ROOT/'product/tests'
    modules = (['test_process_operation_budget', 'test_execution_control'] if args.group == 'deadline' else
               ['test_ad_selection', 'test_ad_storyboard'] if args.group == 'selection' else
        ['test_semantic', 'test_semantic_decisions', 'test_semantic_jobs',
         'test_semantic_package', 'test_semantic_upgrade'])
    out = ROOT/'docs/validation/evidence'/args.evidence_series/args.run
    out.mkdir(parents=True, exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    observed = {p.name: digest(p) for p in source.glob('*.py')}
    installed_before = {p.name: digest(p) for p in package.glob('*.py')}
    assert len(observed) == 281 and observed == installed_before
    test_before = {name+'.py': digest(tests/(name+'.py')) for name in modules}
    # A fixture helper lives in test_ad_storyboard, also needed by selection.
    if args.group == 'selection':
        test_before['test_ad_storyboard.py'] = digest(tests/'test_ad_storyboard.py')
    (out/'source-before.json').write_text(json.dumps(observed, indent=2)+'\n', encoding='utf-8')
    sys.path[:0] = [str(site), str(tests)]
    assert all(Path(value).resolve() != source.parent.resolve() for value in sys.path if value)
    import ai_ad_editor
    assert Path(ai_ad_editor.__file__).resolve().parent == package and ai_ad_editor.VERSION == args.cli_version
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    with (out/'tests.txt').open('w', encoding='utf-8', newline='\n') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    frozen = (observed == {p.name: digest(p) for p in source.glob('*.py')}
        == {p.name: digest(p) for p in package.glob('*.py')}
        and test_before == {name: digest(tests/name) for name in test_before})
    passed = result.wasSuccessful() and not result.skipped and frozen
    report = dict(status='passed' if passed else 'failed', tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        isolated=True, no_site=True, no_bytecode=True, source_fallback=False,
        installed=str(installed), package=str(package), loaded_app=str(ai_ad_editor.__file__),
        cli_version=ai_ad_editor.VERSION, group=args.group, modules=modules,
        frozen_equal=frozen, installed_code_files=len(installed_before),
        source_files=observed, test_files=test_before)
    (out/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                                       encoding='utf-8', newline='\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('source_files', 'test_files')},
                     ensure_ascii=False), flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
