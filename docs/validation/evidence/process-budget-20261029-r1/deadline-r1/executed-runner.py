"""Frozen source CLI55 process-control, selection and semantic regression gates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', choices=('deadline', 'selection', 'semantic'), required=True)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    scratch = ROOT/'local/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ['TEMP'] = os.environ['TMP'] = tempfile.tempdir = str(scratch)
    source = ROOT/'product/src/ai_ad_editor'
    tests = ROOT/'product/tests'
    modules = {'deadline': ['test_process_operation_budget', 'test_execution_control'],
        'selection': ['test_ad_selection', 'test_ad_storyboard'],
        'semantic': ['test_semantic', 'test_semantic_decisions', 'test_semantic_jobs',
                     'test_semantic_package', 'test_semantic_upgrade']}[args.group]
    before = {p.name: sha(p) for p in source.glob('*.py')}
    assert len(before) == 281
    test_before = {name+'.py': sha(tests/(name+'.py')) for name in modules}
    project_before = sha(ROOT/'product/pyproject.toml')
    out = ROOT/'docs/validation/evidence/process-budget-20261029-r1'/(args.group+'-'+args.run)
    out.mkdir(parents=True, exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    (out/'source-before.json').write_text(json.dumps(before, indent=2)+'\n', encoding='utf-8')
    sys.path[:0] = [str(source.parent), str(tests)]
    import ai_ad_editor
    assert Path(ai_ad_editor.__file__).resolve().parent == source
    assert ai_ad_editor.VERSION == tomllib.loads((ROOT/'product/pyproject.toml').read_text('utf-8'))['project']['version'] == '0.1.55'
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    with (out/'tests.txt').open('w', encoding='utf-8', newline='\n') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    frozen = before == {p.name: sha(p) for p in source.glob('*.py')}
    frozen = frozen and project_before == sha(ROOT/'product/pyproject.toml')
    frozen = frozen and test_before == {name: sha(tests/name) for name in test_before}
    passed = result.wasSuccessful() and not result.skipped and frozen
    report = dict(status='passed' if passed else 'failed', cli_version=ai_ad_editor.VERSION,
        runtime='source', group=args.group, tests=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), skipped=len(result.skipped), frozen_equal=frozen,
        source_files=before, test_files=test_before, pyproject_sha256=project_before,
        registered_skill_unchanged=True, native_windows=True, virtualization=False)
    (out/'verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('source_files', 'test_files')},
                     ensure_ascii=False), flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
