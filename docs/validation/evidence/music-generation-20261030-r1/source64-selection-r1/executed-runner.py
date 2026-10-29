"""Frozen source64 or isolated installed64 regression groups; no quality claim."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
GROUPS = {
    'music':['test_music_generation', 'test_music_loop', 'test_music_score'],
    'bootstrap':['test_native_worker_imports', 'test_semantic_worker_imports'],
    'selection':['test_ad_content_uniqueness', 'test_ad_selection', 'test_ad_storyboard'],
    'semantic':['test_semantic', 'test_semantic_decisions', 'test_semantic_jobs', 'test_semantic_package', 'test_semantic_upgrade'],
    'control':['test_native_process_job', 'test_process_operation_budget', 'test_execution_control'],
    'contracts':['test_local_asr', 'test_local_vision', 'test_local_face', 'test_local_ocr', 'test_local_matting',
        'test_local_inpainting', 'test_local_vace', 'test_model_session', 'test_lipsync', 'test_interpolation',
        'test_speech_enhancement', 'test_local_separation', 'test_stem_separation', 'test_ctc_activity',
        'test_ctc_alignment', 'test_vace_context', 'test_music_generation'],
}
EXPECTED = dict(music=62, bootstrap=33, selection=57, semantic=104, control=26, contracts=431)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', required=True, choices=GROUPS)
    parser.add_argument('--run', required=True)
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and sys.dont_write_bytecode
    source, tests = ROOT / 'product/src/ai_ad_editor', ROOT / 'product/tests'
    package = args.installed.resolve() / 'site/ai_ad_editor' if args.installed else source
    assert package.is_dir()
    if args.installed:
        assert args.installed.resolve().is_relative_to((ROOT / 'local/agent-ffmpeg').resolve())
    expected = {p.name:sha(p) for p in source.glob('*.py')}
    assert len(expected) == 288 and expected == {p.name:sha(p) for p in package.glob('*.py')}
    pins = {p.relative_to(ROOT).as_posix():sha(p) for p in [*package.glob('*.py'), *tests.glob('*.py')]}
    out = ROOT / 'docs/validation/evidence/music-generation-20261030-r1' / (
        ('installed64-' if args.installed else 'source64-') + args.group + '-' + args.run)
    out.mkdir(parents=True)
    shutil.copyfile(Path(__file__), out / 'executed-runner.py')
    sys.path[:0] = [str(package.parent), str(tests)]
    import ai_ad_editor
    from ai_ad_editor.runtime import configure_local_runtime
    assert ai_ad_editor.VERSION == '0.1.64' and Path(ai_ad_editor.__file__).resolve() == package / '__init__.py'
    runtime = configure_local_runtime()
    dependencies = None
    if args.group == 'contracts':
        result = subprocess.run([sys.executable, '-I', '-B', '-u', '-X', 'utf8', '-c',
            'import json,numpy,PIL,jsonschema,cv2;print(json.dumps(dict(numpy=numpy.__version__,PIL=PIL.__version__,cv2=cv2.__version__)))'],
            cwd=ROOT, capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
        (out / 'isolated-dependencies.stdout').write_bytes(result.stdout)
        (out / 'isolated-dependencies.stderr').write_bytes(result.stderr)
        assert not result.returncode, 'Use the existing complete native model interpreter; no global installs'
        dependencies = json.loads(result.stdout)
    suite = unittest.defaultTestLoader.loadTestsFromNames(GROUPS[args.group])
    assert suite.countTestCases() == EXPECTED[args.group], suite.countTestCases()
    started = time.monotonic()
    with (out / 'tests.stderr').open('w', encoding='utf-8', newline='\n') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    frozen = all(sha(ROOT / path) == value for path, value in pins.items())
    frozen = frozen and expected == {p.name:sha(p) for p in source.glob('*.py')} == {p.name:sha(p) for p in package.glob('*.py')}
    report = dict(status='passed' if result.wasSuccessful() and frozen and not result.skipped else 'failed',
        cli_version=ai_ad_editor.VERSION, group=args.group, tests=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), skipped=len(result.skipped), elapsed_seconds=time.monotonic() - started,
        frozen_equal=frozen, file_hashes=pins, loaded_package=str(package),
        installed=str(args.installed.resolve()) if args.installed else None,
        source_fallback=False if args.installed else None, runtime_root=runtime['root'],
        interpreter=sys.executable, isolated_child_dependencies=dependencies, natural_quality_accepted=False)
    (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'file_hashes'}), flush=True)
    if not result.wasSuccessful():
        print((out / 'tests.stderr').read_text(encoding='utf-8')[-12000:], flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
