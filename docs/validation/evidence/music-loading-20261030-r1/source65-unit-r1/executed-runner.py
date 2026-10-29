"""Frozen CLI65 checks; fixtures are not neural music quality evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GROUPS = {
    'unit': ['test_music_generation', 'test_music_loading'],
    'music': ['test_music_generation', 'test_music_loading', 'test_music_loop', 'test_music_score'],
    'bootstrap': ['test_native_worker_imports', 'test_semantic_worker_imports'],
    'control': ['test_native_process_job', 'test_process_operation_budget', 'test_execution_control'],
    'session': ['test_model_session'],
    'contracts': ['test_local_asr', 'test_local_vision', 'test_local_face', 'test_local_ocr',
        'test_local_matting', 'test_local_inpainting', 'test_local_vace', 'test_model_session',
        'test_lipsync', 'test_interpolation', 'test_speech_enhancement', 'test_local_separation',
        'test_stem_separation', 'test_ctc_activity', 'test_ctc_alignment', 'test_vace_context',
        'test_music_generation', 'test_music_loading'],
}
COUNTS = dict(unit=37, music=74, bootstrap=33, control=26, contracts=443)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--group', choices=GROUPS, required=True)
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    assert args.run.isalnum() and sys.dont_write_bytecode
    source = ROOT / 'product/src/ai_ad_editor'
    tests = ROOT / 'product/tests'
    package = args.installed.resolve() / 'site/ai_ad_editor' if args.installed else source
    source_hashes = {path.name: sha(path) for path in source.glob('*.py')}
    assert len(source_hashes) == 288
    assert source_hashes == {path.name: sha(path) for path in package.glob('*.py')}
    pins = {path.relative_to(ROOT).as_posix(): sha(path) for path in [*source.glob('*.py'), *package.glob('*.py'), *tests.glob('*.py')]}
    sys.path[:0] = [str(package.parent), str(tests)]
    import ai_ad_editor
    from ai_ad_editor.runtime import configure_local_runtime
    assert ai_ad_editor.VERSION == '0.1.65' and Path(ai_ad_editor.__file__).resolve() == package / '__init__.py'
    proof = ROOT / 'docs/validation/evidence/music-loading-20261030-r1' / (
        ('installed65-' if args.installed else 'source65-') + args.group + '-' + args.run)
    proof.mkdir(parents=True)
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    temporary = ROOT / 'local/agent-ffmpeg' / ('music65-check-' + args.group + '-' + args.run)
    temporary.mkdir()
    os.environ['TEMP'] = os.environ['TMP'] = str(temporary)
    runtime = configure_local_runtime()
    if args.group in {'contracts', 'session'}:
        dependency = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c',
            'import numpy,PIL,jsonschema,cv2;print("native dependencies ready")'], cwd=ROOT,
            capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
        (proof / 'dependencies.stdout').write_bytes(dependency.stdout)
        (proof / 'dependencies.stderr').write_bytes(dependency.stderr)
        assert not dependency.returncode
    suite = unittest.defaultTestLoader.loadTestsFromNames(GROUPS[args.group])
    if args.group in COUNTS:
        assert suite.countTestCases() == COUNTS[args.group], suite.countTestCases()
    began = time.monotonic()
    with (proof / 'tests.stderr').open('w', encoding='utf-8', newline='\n') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    frozen = all(sha(ROOT / name) == pin for name, pin in pins.items())
    frozen = frozen and source_hashes == {path.name: sha(path) for path in source.glob('*.py')}
    frozen = frozen and source_hashes == {path.name: sha(path) for path in package.glob('*.py')}
    report = dict(status='passed' if result.wasSuccessful() and frozen and not result.skipped else 'failed',
        cli_version='0.1.65', group=args.group, tests=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), skipped=len(result.skipped), elapsed_seconds=time.monotonic() - began,
        frozen_equal=frozen, file_hashes=pins, installed=str(args.installed.resolve()) if args.installed else None,
        loaded_package=str(package), source_fallback=False if args.installed else None,
        runtime_root=runtime['root'], music_generated=False, natural_quality_accepted=False,
        previous_431_failure_overwritten=False)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'file_hashes'}), flush=True)
    if report['status'] != 'passed':
        print((proof / 'tests.stderr').read_text(encoding='utf-8')[-10000:], flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
