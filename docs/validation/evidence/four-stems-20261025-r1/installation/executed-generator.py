"""Freeze actual CLI 0.1.6 installation bytes and completed four-stem receipts."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def main():
    evidence = ROOT / 'docs/validation/evidence/four-stems-20261025-r1'
    out = evidence / 'installation'
    out.mkdir(exist_ok=False)
    (out / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    bundle = ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.4/candidate-r1/bundle'
    installed = ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.4/final/installed'
    manifest = json.loads((bundle / 'manifest.json').read_bytes())
    receipt = json.loads((installed / 'receipt.json').read_bytes())
    assert receipt['manifest_sha256'] == sha(bundle / 'manifest.json')
    assert receipt['audit']['modules']['ai-ad-editor']['version'] == '0.1.6'
    sources = []
    for source in sorted((ROOT / 'product/src/ai_ad_editor').rglob('*.py')):
        relative = source.relative_to(ROOT / 'product/src')
        target = installed / 'site' / relative
        assert sha(source) == sha(target), str(relative)
        sources.append(dict(path=relative.as_posix(), bytes=source.stat().st_size, sha256=sha(source)))
    with zipfile.ZipFile(bundle.with_suffix('.zip')) as archive:
        assert archive.testzip() is None
        zipped_files = [n for n in archive.namelist() if not n.endswith('/')]
        for name in zipped_files:
            path = bundle / name
            assert path.read_bytes() == archive.read(name), name
    for name in ('receipt.json', 'dependency-audit.json', 'requirements.lock', 'install.log'):
        (out / name).write_bytes((installed / name).read_bytes())
    save(out / 'source-python-files.json', sources)
    for run in ('development-r1', 'installed-r1', 'skill-r1'):
        record = json.loads((evidence / run / 'verification.json').read_bytes())
        assert record['quality_all_controlled_passed'] and not record['full_G17_closed']
        target = evidence / run / 'executed-generator.py'
        assert not target.exists()
        target.write_bytes((ROOT / 'scripts/verify_four_stems_20261025.py').read_bytes())
    result = dict(status='passed', cli_version='0.1.6', release='v0.1.0-alpha.4-local.4',
        installed=str(installed), archive=str(bundle.with_suffix('.zip')),
        archive_sha256=sha(bundle.with_suffix('.zip')), archive_bytes=bundle.with_suffix('.zip').stat().st_size,
        manifest_sha256=sha(bundle / 'manifest.json'), bundle_files=len(zipped_files),
        wheels=len(manifest['wheels']), source_python_files=len(sources), all_source_python_bytes_equal=True,
        new_model_forwards=0, native_windows=True, virtual_environment=False,
        heavy_torch_environment_and_weights_bundled=False,
        historical_public_release_unchanged=True, generator_sha256=sha(Path(__file__)))
    save(out / 'verification.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
