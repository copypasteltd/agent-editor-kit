"""Frozen source CLI57 bootstrap or native-service contract regressions."""
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
    'bootstrap': ['test_native_worker_imports', 'test_semantic_worker_imports'],
    'contracts': ['test_local_asr', 'test_local_vision', 'test_local_face', 'test_local_ocr',
        'test_local_matting', 'test_local_inpainting', 'test_local_vace', 'test_model_session',
        'test_lipsync', 'test_interpolation', 'test_speech_enhancement', 'test_local_separation',
        'test_stem_separation', 'test_ctc_activity', 'test_ctc_alignment', 'test_vace_context'],
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
    out = ROOT/'docs/validation/evidence/native-worker-bootstrap-20261029-r1'/(
        'source57-'+args.group+'-'+args.run)
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(Path(__file__), out/'executed-runner.py')
    files = [*package.glob('*.py'), *(tests/(name+'.py') for name in GROUPS[args.group])]
    pins = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    assert len(list(package.glob('*.py'))) == 281
    sys.path.insert(0, str(package.parent))
    sys.path.insert(0, str(tests))
    import ai_ad_editor
    assert Path(ai_ad_editor.__file__).resolve() == package/'__init__.py'
    assert ai_ad_editor.VERSION == '0.1.57'
    from ai_ad_editor.runtime import configure_local_runtime
    runtime = configure_local_runtime()
    assert Path(runtime['root']).resolve().is_relative_to(ROOT)
    child_dependencies = None
    if args.group == 'contracts':
        # Several transport fixtures launch this exact interpreter with -I.
        # A parent-only user-site import does not satisfy that child contract.
        code = ('import json,sys,numpy,PIL,jsonschema;'
                'print(json.dumps(dict(python=sys.executable,numpy=numpy.__version__,'
                'numpy_path=numpy.__file__,PIL=PIL.__version__,PIL_path=PIL.__file__,'
                'jsonschema_path=jsonschema.__file__)))')
        preflight = subprocess.run([sys.executable, '-I', '-B', '-u', '-X', 'utf8', '-c', code],
                                  capture_output=True, timeout=120,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'isolated-dependencies.stdout').write_bytes(preflight.stdout)
        (out/'isolated-dependencies.stderr').write_bytes(preflight.stderr)
        if preflight.returncode:
            (out/'verification.json').write_text(json.dumps(dict(status='prerequisite-failed',
                group=args.group, interpreter=sys.executable, tests=0,
                reason='isolated transport interpreter lacks required native dependencies'))+'\n',
                encoding='utf-8', newline='\n')
            return 2
        child_dependencies = json.loads(preflight.stdout)
    suite = unittest.defaultTestLoader.loadTestsFromNames(GROUPS[args.group])
    count = suite.countTestCases()
    if args.group == 'bootstrap':
        assert count == 31
    with (out/'tests.stderr').open('w', encoding='utf-8', newline='\n') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    frozen = pins == {name: sha(ROOT/name) for name in pins}
    report = dict(status='passed' if result.wasSuccessful() and frozen and not result.skipped else 'failed',
        group=args.group, cli_version=ai_ad_editor.VERSION, tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        source_package=str(package), frozen_equal=frozen, file_hashes=pins,
        runtime_root=runtime['root'],
        interpreter=sys.executable, isolated_child_dependencies=child_dependencies,
        neural_quality_accepted=False, installed57_accepted=False,
        isolated_bootstrap=bool(sys.flags.isolated and sys.flags.no_site))
    (out/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n',
                                       encoding='utf-8', newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'file_hashes'}), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
