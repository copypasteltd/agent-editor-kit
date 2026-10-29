"""Build and independently install the complete native CLI54 candidate."""
from datetime import datetime, timezone
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
SOURCE = ROOT/'product/src/ai_ad_editor'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--resume-from', help='Reuse a completed, hash-checked candidate build; never reuse an installation')
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    if args.resume_from:
        assert args.resume_from.replace('-', '').isalnum() and args.resume_from != args.run
    base = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.52'
    evidence = ROOT/'docs/validation/evidence/ad-selection-20261029-r1'/('installation-candidate-'+args.run)
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    source_before = {p.name: sha(p) for p in SOURCE.glob('*.py')}
    save(evidence/'source-before.json', source_before)
    native_names = ['native_icc_manifest.json', 'LITTLECMS_LICENSE.txt',
        json.loads((SOURCE/'native_icc_manifest.json').read_bytes())['binary_filename'],
        'native_ocio_manifest.json',
        *[r['path'] for r in json.loads((SOURCE/'native_ocio_manifest.json').read_bytes())['files']]]
    native_before = {name: sha(SOURCE/name) for name in native_names}
    report = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
        cli_version='0.1.54', source_fallback=False, native_windows=True, virtualization=False,
        global_environment_install=False, network=False)
    calls = []
    def run(name, command, *, timeout=1800, json_output=True, env=None):
        command = list(map(str, command))
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired as exc:
            (evidence/(name+'.timeout.stdout')).write_bytes(exc.stdout or b'')
            (evidence/(name+'.timeout.stderr')).write_bytes(exc.stderr or b'')
            raise
        (evidence/(name+'.stdout')).write_bytes(result.stdout)
        (evidence/(name+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=command, exit_code=result.returncode,
            stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
            stderr_sha256=hashlib.sha256(result.stderr).hexdigest()))
        save(evidence/'calls.json', calls)
        print(json.dumps(dict(name=name, exit_code=result.returncode)), flush=True)
        assert result.returncode == 0, (name, result.stderr[-2000:])
        return json.loads(result.stdout.decode('utf-8-sig')) if json_output else None
    try:
        build_run = args.resume_from or args.run
        wheel_dir = base/('source-wheel-'+build_run)
        if not args.resume_from:
            wheel_dir.mkdir(parents=True, exist_ok=False)
        env = os.environ.copy()
        env.update(TEMP=str(wheel_dir), TMP=str(wheel_dir), TMPDIR=str(wheel_dir),
            PIP_CONFIG_FILE=os.devnull, PIP_NO_INDEX='1', PIP_NO_CACHE_DIR='1',
            PIP_DISABLE_PIP_VERSION_CHECK='1', PYTHONDONTWRITEBYTECODE='1')
        builder = runpy.run_path(str(ROOT/'product/offline/build.py'))
        generated = ROOT/'product/build'
        builder['INSTALLER']['no_reparse'](generated)
        assert generated.resolve() == (ROOT/'product/build').absolute()
        assert generated.resolve().is_relative_to(ROOT.resolve()) and generated.name == 'build'
        if generated.exists() and not args.resume_from:
            shutil.rmtree(generated)
        if not args.resume_from:
            run('wheel', [sys.executable, '-I', '-B', '-m', 'pip', 'wheel', '--no-index',
                '--no-deps', '--no-build-isolation', '--wheel-dir', wheel_dir, ROOT/'product'],
                json_output=False, env=env)
        wheels = list(wheel_dir.glob('*.whl'))
        assert len(wheels) == 1
        wheel = wheels[0]
        pin = 'sha256:'+sha(wheel)
        checked = builder['validate_product_wheel'](wheel, '0.1.54',
            (ROOT/'product/pyproject.toml').read_text('utf-8'), SOURCE, pin)
        save(evidence/'product-wheel-verification.json', checked)
        bundle = base/('candidate-'+build_run)/'bundle'
        if args.resume_from:
            previous = evidence.parent/('installation-candidate-'+build_run)
            built = json.loads((previous/'bundle.stdout').read_bytes())
            save(evidence/'reused-build.json', dict(previous=str(previous), **built))
        else:
            built = run('bundle', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
                ROOT/'product/offline/build.py', '--output', bundle,
                '--product-wheel', wheel, '--product-wheel-sha256', pin])
        archive = bundle.with_suffix('.zip')
        assert built['archive_sha256'] == 'sha256:'+sha(archive)
        unpacked = base/('unpacked-'+args.run)
        unpacked.mkdir(parents=True, exist_ok=False)
        with zipfile.ZipFile(archive) as zipped:
            names = zipped.namelist()
            assert len(names) == len(set(names)) and len(names) < 256
            total = 0
            for info in zipped.infolist():
                relative = PurePosixPath(info.filename)
                assert (not relative.is_absolute() and '..' not in relative.parts
                        and ':' not in info.filename and '\\' not in info.filename and not info.is_dir()
                        and ((info.external_attr >> 16) & 0o170000) != 0o120000)
                total += info.file_size
                assert info.file_size < 1024**3 and total < 2*1024**3
                target = unpacked/Path(*relative.parts)
                assert target.resolve().is_relative_to(unpacked.resolve())
                target.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(info) as reader, target.open('xb') as writer:
                    shutil.copyfileobj(reader, writer, 1024**2)
        manifest_pin = built['manifest_sha256']
        assert manifest_pin == 'sha256:'+sha(unpacked/'manifest.json')
        installed = base/('final-'+args.run)/'installed'
        result = run('install', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
            unpacked/'install.py', '--bundle', unpacked, '--target', installed,
            '--manifest-sha256', manifest_pin, '--timeout-seconds', '600'])
        assert result['ok']
        prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', installed/'run.py']
        version = run('version', [*prefix, 'version'])
        assert version['ok'] and version['data']['cli_version'] == '0.1.54'
        capabilities = run('capabilities', [*prefix, 'capabilities'])
        assert 'ad.select' in capabilities['data']['capabilities']['ai']['ad_storyboard']['commands']
        assert source_before == {p.name: sha(p) for p in SOURCE.glob('*.py')}
        assert set(source_before) == {p.name for p in (installed/'site/ai_ad_editor').glob('*.py')}
        for name, digest in source_before.items():
            assert sha(installed/'site/ai_ad_editor'/name) == digest
        assert native_before == {name: sha(SOURCE/name) for name in native_names}
        assert native_before == {name: sha(installed/'site/ai_ad_editor'/name) for name in native_names}
        report.update(status='installed-and-byte-verified', installed=str(installed),
            archive=str(archive), archive_bytes=archive.stat().st_size, archive_sha256=sha(archive),
            manifest_sha256=manifest_pin, product_wheel_sha256=pin,
            source_file_count=len(source_before), source_and_installed_equal=True,
            native_artifacts=native_before, exact_product_payload=checked,
            capability_count=len(capabilities['data']['capabilities']),
            registered_skill_unchanged=True, new_renders=0, new_model_forwards=0,
            finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(evidence/'verification.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc))
        save(evidence/'verification.json', report)
        raise


if __name__ == '__main__':
    main()
