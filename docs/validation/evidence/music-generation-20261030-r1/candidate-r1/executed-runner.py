"""Build and independently install64 after frozen source gates; never register it."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import runpy
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'
SOURCE = ROOT / 'product/src/ai_ad_editor'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--case-run', default='piano3')
    parser.add_argument('--package-run', default='r1')
    parser.add_argument('--for-validation', action='store_true',
                        help='Build a candidate while only actual/long-contract gates remain pending; never activate')
    args = parser.parse_args()
    assert all(v.replace('-', '').isalnum() for v in (args.run, args.case_run, args.package_run))
    required = {group:BASE / ('source64-' + group + '-r1/verification.json') for group in (
        'music', 'bootstrap', 'control', 'selection', 'semantic', 'contracts')}
    required['actual'] = BASE / ('actual-' + args.case_run + '/verification.json')
    required['package'] = BASE / ('package-' + args.package_run + '/verification.json')
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing and (not args.for_validation or set(missing) - {'contracts', 'actual', 'package'}):
        print(json.dumps(dict(status='pending', missing=missing, mutated=False, skill_activated=False)), flush=True)
        return 2
    expected = dict(music=62, bootstrap=33, control=26, selection=57, semantic=104, contracts=431)
    reports = {name:load(path) for name, path in required.items() if path.is_file()}
    for name, report in reports.items():
        assert report['status'] == 'passed', name
        assert report['cli_version'] == '0.1.64'
        if name in expected:
            assert report['tests'] == expected[name] and report['frozen_equal']
            assert report['failures'] == report['errors'] == report['skipped'] == 0
            assert all(sha(ROOT / path) == pin for path, pin in report['file_hashes'].items())
    if 'actual' in reports:
        assert reports['actual']['complete_PCM_roundtrip_verified']
        assert reports['actual']['actual_generation']['worker']['model']['neural_backend'] == 'cuda'
    if 'package' in reports:
        assert reports['package']['complete_master_WAV_equal'] and reports['package']['complete_generation_recipe_equal']
        assert reports['package']['complete_rendered_RGBA_PCM_equal']
    pins = {p.name:sha(p) for p in SOURCE.glob('*.py')}
    assert len(pins) == 288
    if 'actual' in reports:
        assert pins == {Path(p).name:h for p,h in reports['actual']['source_hashes'].items()}
    namespace, runtime = ROOT / 'agent-ffmpeg-local-install-manifest.json', ROOT / 'local/agent-ffmpeg/runtime.json'
    manifest = load(namespace)
    assert manifest['cli_version'] == '0.1.63' and manifest['skill_count'] == 1
    guard = {str(p):sha(p) for p in (namespace, runtime)}
    guard.update({str(ROOT / row['path']):row['sha256'] for row in manifest['files']})
    assert all(sha(Path(path)) == pin for path,pin in guard.items())
    out = BASE / ('candidate-' + args.run)
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    base = ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.62'
    wheel_dir = base / ('source-wheel-' + args.run)
    wheel_dir.mkdir(parents=True)
    env = os.environ.copy()
    env.update(TEMP=str(wheel_dir), TMP=str(wheel_dir), TMPDIR=str(wheel_dir),
               PIP_CONFIG_FILE=os.devnull, PIP_NO_INDEX='1', PIP_NO_CACHE_DIR='1',
               PIP_DISABLE_PIP_VERSION_CHECK='1', PYTHONDONTWRITEBYTECODE='1')
    calls = []

    def run(name, argv, structured=True):
        result = subprocess.run(list(map(str, argv)), cwd=ROOT, env=env, capture_output=True,
                                timeout=1800, creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=list(map(str, argv)), exit_code=result.returncode))
        save(out / 'calls.json', calls)
        assert result.returncode == 0, (name, result.stdout[-1500:], result.stderr[-1500:])
        print(json.dumps(dict(name=name, exit_code=0)), flush=True)
        return json.loads(result.stdout) if structured else None

    try:
        builder = runpy.run_path(str(ROOT / 'product/offline/build.py'))
        generated = ROOT / 'product/build'
        builder['INSTALLER']['no_reparse'](generated)
        assert generated.resolve() == (ROOT / 'product/build').absolute() and generated.resolve().is_relative_to(ROOT.resolve())
        if generated.exists():
            shutil.rmtree(generated)
        run('wheel', [sys.executable, '-I', '-B', '-m', 'pip', 'wheel', '--no-index', '--no-deps',
                      '--no-build-isolation', '--wheel-dir', wheel_dir, ROOT / 'product'], False)
        wheels = list(wheel_dir.glob('*.whl'))
        assert len(wheels) == 1
        wheel = wheels[0]
        payload = builder['validate_product_wheel'](wheel, '0.1.64',
            (ROOT / 'product/pyproject.toml').read_text('utf-8'), SOURCE, 'sha256:' + sha(wheel))
        save(out / 'wheel-verification.json', payload)
        bundle = base / ('candidate-' + args.run) / 'bundle'
        built = run('bundle', [sys.executable, '-E', '-B', '-u', '-X', 'utf8', ROOT / 'product/offline/build.py',
                    '--output', bundle, '--product-wheel', wheel, '--product-wheel-sha256', 'sha256:' + sha(wheel)])
        archive = bundle.with_suffix('.zip')
        assert built['archive_sha256'] == 'sha256:' + sha(archive)
        unpacked = base / ('unpacked-' + args.run)
        unpacked.mkdir()
        with zipfile.ZipFile(archive) as zipped:
            names = zipped.namelist()
            assert len(names) == len(set(names)) and len(names) < 256
            total = 0
            for info in zipped.infolist():
                relative = PurePosixPath(info.filename)
                assert not relative.is_absolute() and '..' not in relative.parts and ':' not in info.filename
                assert '\\' not in info.filename and not info.is_dir() and ((info.external_attr >> 16) & 0o170000) != 0o120000
                total += info.file_size
                assert info.file_size < 1024**3 and total < 2 * 1024**3
                target = unpacked / Path(*relative.parts)
                assert target.resolve().is_relative_to(unpacked.resolve())
                target.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(info) as reader, target.open('xb') as writer:
                    shutil.copyfileobj(reader, writer, 1024**2)
        assert built['manifest_sha256'] == 'sha256:' + sha(unpacked / 'manifest.json')
        installed = base / ('final-' + args.run) / 'installed'
        installed_result = run('install', [sys.executable, '-E', '-B', '-u', '-X', 'utf8', unpacked / 'install.py',
            '--bundle', unpacked, '--target', installed, '--manifest-sha256', built['manifest_sha256'], '--timeout-seconds', '600'])
        assert installed_result['ok']
        version = run('version', [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', installed / 'run.py', 'version'])
        assert version['ok'] and version['data']['cli_version'] == '0.1.64'
        assert pins == {p.name:sha(p) for p in SOURCE.glob('*.py')} == {p.name:sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
        assert all(sha(Path(path)) == pin for path,pin in guard.items())
        save(out / 'verification.json', dict(status='installed-and-byte-verified', cli_version='0.1.64',
            local_release='v0.1.0-alpha.4-local.62', archive=str(archive), archive_bytes=archive.stat().st_size,
            archive_sha256=sha(archive), manifest_sha256=built['manifest_sha256'], installed=str(installed),
            payload=payload, source_hashes=pins, source_and_installed_equal=True,
            gates={name:dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path)) for name,path in required.items() if name in reports},
            pending_gates=missing, built_for_validation_only=bool(missing),
            registered_files=guard, registered_skill_unchanged=True, skill_activated=False,
            actual_installed_generation=False, external_music_weights_and_runtime_bundled=False,
            clean_host_accepted=False, new_model_forwards=0))
        print(json.dumps(dict(status='installed-and-byte-verified', installed=str(installed), skill_activated=False)), flush=True)
    except BaseException as exc:
        save(out / 'verification.json', dict(status='failed', cli_version='0.1.64', error=repr(exc), calls=calls))
        raise


if __name__ == '__main__':
    raise SystemExit(main())
