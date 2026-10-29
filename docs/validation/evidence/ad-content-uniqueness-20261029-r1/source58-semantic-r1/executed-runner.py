"""Frozen CLI58 content-selection, semantic and execution-control regressions."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
GROUPS = {
    'selection': (57, ['test_ad_content_uniqueness', 'test_ad_selection', 'test_ad_storyboard']),
    'semantic': (104, ['test_semantic', 'test_semantic_decisions', 'test_semantic_jobs',
                       'test_semantic_package', 'test_semantic_upgrade']),
    'control': (19, ['test_native_process_job', 'test_process_operation_budget', 'test_execution_control']),
    'bootstrap': (31, ['test_native_worker_imports', 'test_semantic_worker_imports']),
    'contracts': (400, ['test_local_asr', 'test_local_vision', 'test_local_face', 'test_local_ocr',
        'test_local_matting', 'test_local_inpainting', 'test_local_vace', 'test_model_session',
        'test_lipsync', 'test_interpolation', 'test_speech_enhancement', 'test_local_separation',
        'test_stem_separation', 'test_ctc_activity', 'test_ctc_alignment', 'test_vace_context']),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=GROUPS, required=True)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and sys.dont_write_bytecode
    if args.group == 'bootstrap':
        assert sys.flags.isolated and sys.flags.no_site
    package, tests = ROOT/'product/src/ai_ad_editor', ROOT/'product/tests'
    sys.path[:0] = [str(package.parent), str(tests)]
    import ai_ad_editor
    assert Path(ai_ad_editor.__file__).resolve() == package/'__init__.py'
    assert ai_ad_editor.VERSION == '0.1.58'
    from ai_ad_editor.runtime import configure_local_runtime
    runtime = configure_local_runtime()
    assert Path(runtime['root']).resolve().is_relative_to(ROOT)
    out = ROOT/'docs/validation/evidence/ad-content-uniqueness-20261029-r1'/('source58-'+args.group+'-'+args.run)
    out.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), out/'executed-runner.py')
    expected, modules = GROUPS[args.group]
    files = [*package.glob('*.py'), *tests.glob('*.py')]
    if args.group == 'selection':
        assert tests/'test_ad_storyboard.py' in files
    pins = {p.relative_to(ROOT).as_posix():sha(p) for p in files}
    assert len(list(package.glob('*.py'))) == 281
    if args.group == 'contracts':
        check = subprocess.run([sys.executable, '-I', '-B', '-c',
            'import json,numpy,PIL,jsonschema,cv2;print(json.dumps(dict(numpy=numpy.__version__,PIL=PIL.__version__,cv2=cv2.__version__)))'],
            capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'isolated-dependencies.stdout').write_bytes(check.stdout)
        (out/'isolated-dependencies.stderr').write_bytes(check.stderr)
        if check.returncode:
            (out/'verification.json').write_text(json.dumps(dict(status='prerequisite-failed',tests=0,
                interpreter=sys.executable))+'\n',encoding='utf-8',newline='\n')
            return 2
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    assert suite.countTestCases() == expected
    with (out/'tests.stderr').open('w', encoding='utf-8', newline='\n') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    frozen = pins == {name:sha(ROOT/name) for name in pins}
    passed = result.wasSuccessful() and frozen and not result.skipped
    report = dict(status='passed' if passed else 'failed', cli_version=ai_ad_editor.VERSION,
        group=args.group, tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), frozen_equal=frozen, file_hashes=pins, modules=modules,
        runtime_root=runtime['root'], source_only=True, installed58_accepted=False,
        actual_neural_quality_accepted=False)
    (out/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                                       encoding='utf-8', newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'file_hashes'}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
