"""Stage publisher-hashed Windows wheels and model candidates for native validation."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import shutil
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'product/.runtime/materials-20261024'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def relative(name):
    path = PurePosixPath(name.rstrip('/'))
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Invalid upstream member: ' + name)
    return Path(*path.parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New native staging directory')
    args = parser.parse_args()
    from acquire_material_community_sources import candidates
    target_root = args.output.resolve()
    if not target_root.is_relative_to(WORK.resolve()):
        raise ValueError('Use an owned materials staging directory')
    site = target_root / 'site'
    models = target_root / 'models'
    if target_root.exists():
        raise ValueError('Existing staging is preserved')
    site.mkdir(parents=True)
    models.mkdir()
    rows = []
    for row in candidates():
        if not row['name'].endswith('.whl'):
            continue
        path = WORK / 'downloads' / row['name']
        assert sha(path) == row['sha256']
        with zipfile.ZipFile(path) as zipped:
            for member in zipped.infolist():
                name = relative(member.filename)
                if member.is_dir():
                    continue
                parts = name.parts
                if parts[0].endswith('.data'):
                    if parts[1:3] != ('data', 'Scripts'):
                        raise ValueError('Unsupported wheel data layout: ' + member.filename)
                    target = target_root / 'bin' / Path(*parts[3:])
                else:
                    target = site / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as handle:
                    handle.write(zipped.read(member))
        rows.append({'name': row['name'], 'bytes': path.stat().st_size, 'sha256': row['sha256']})
    model = next(row for row in candidates() if row['id'] == 'kokoro-zh-en-int8')
    path = WORK / 'downloads' / model['name']
    assert sha(path) == model['sha256']
    with tarfile.open(path, 'r:bz2') as archived:
        for member in archived:
            name = relative(member.name)
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('No links or special files in a material model')
            target = models / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archived.extractfile(member) as incoming, target.open('xb') as outgoing:
                shutil.copyfileobj(incoming, outgoing)
    report = {'status': 'staged-for-native-validation', 'wheels': rows, 'model_sha256': model['sha256'],
              'virtual_environments_created': 0, 'global_packages_changed': False,
              'site': str(site), 'models': str(models)}
    (target_root / 'staging.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
