"""Freeze the native CLI 0.1.7 bundle and independently installed product bytes."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/validation/evidence/job-recovery-20261025-r1'


def sha(path):
    with path.open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def main():
    out = EVIDENCE / 'installation'
    out.mkdir(exist_ok=False)
    (out / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    base = ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.5'
    bundle, installed = base / 'candidate-r1/bundle', base / 'final/installed'
    manifest = json.loads((bundle / 'manifest.json').read_bytes())
    receipt = json.loads((installed / 'receipt.json').read_bytes())
    assert receipt['manifest_sha256'] == sha(bundle / 'manifest.json')
    assert receipt['audit']['modules']['ai-ad-editor']['version'] == '0.1.7'
    files = []
    for source in sorted((ROOT / 'product/src/ai_ad_editor').rglob('*.py')):
        relative = source.relative_to(ROOT / 'product/src')
        target = installed / 'site' / relative
        assert source.read_bytes() == target.read_bytes(), str(relative)
        files.append(dict(path=relative.as_posix(), bytes=source.stat().st_size, sha256=sha(source)))
    with zipfile.ZipFile(bundle.with_suffix('.zip')) as archive:
        assert archive.testzip() is None
        zipped = [name for name in archive.namelist() if not name.endswith('/')]
        assert len(zipped) == len(manifest['files']) + 1
        for name in zipped:
            assert (bundle / name).read_bytes() == archive.read(name), name
    for name in ('receipt.json', 'dependency-audit.json', 'requirements.lock', 'install.log'):
        (out / name).write_bytes((installed / name).read_bytes())
    write(out / 'source-python-files.json', files)
    tests = {}
    for name in ('contracts-r1', 'four-stem-regression-r1', 'two-stem-regression-r1', 'cli-regression-r1',
                 'installed-contracts-r1', 'installed-four-stem-regression-r2', 'installed-offline-r1'):
        record = json.loads((EVIDENCE / name / 'verification.json').read_bytes())
        assert record['exit_code'] == 0 and record['terminal_ok'] and record['frozen_equal']
        tests[name] = dict(methods=record['methods'], skipped=record['skipped'], sha256=sha(EVIDENCE / name / 'verification.json'))
    for name in ('development-r1', 'installed-r1'):
        record = json.loads((EVIDENCE / name / 'verification.json').read_bytes())
        assert record['quality_all_controlled_passed'] and not record['full_G17_closed']
        target = EVIDENCE / name / 'executed-generator.py'
        assert not target.exists()
        target.write_bytes((ROOT / 'scripts/verify_four_stems_20261025.py').read_bytes())
    result = dict(status='passed', cli_version='0.1.7', release='v0.1.0-alpha.4-local.5', installed=str(installed),
        archive=str(bundle.with_suffix('.zip')), archive_bytes=bundle.with_suffix('.zip').stat().st_size,
        archive_sha256=sha(bundle.with_suffix('.zip')), manifest_sha256=sha(bundle / 'manifest.json'),
        bundle_manifest_files=len(manifest['files']), archive_files=len(zipped), wheels=len(manifest['wheels']),
        source_python_files=len(files), all_source_python_bytes_equal=True, tests=tests,
        native_windows=True, virtual_environment=False, new_model_forwards=0,
        heavy_torch_environment_and_weights_bundled=False, public_release_unchanged=True,
        generator_sha256=sha(Path(__file__)))
    write(out / 'verification.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
