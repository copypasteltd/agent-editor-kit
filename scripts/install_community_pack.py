"""Install an explicitly supplied, pinned CPU or CUDA model ZIP with native Python.

No network, package manager, environment creation or source-runtime fallback.
Use the model-packs.json shipped with the installed CLI as --catalog.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import zipfile


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def local_path(value):
    path = Path(value).absolute()
    if str(path).startswith(('\\\\', '//')):
        raise ValueError('Use a local Windows drive')
    for part in [path, *path.parents]:
        if part.is_symlink() or part.is_junction():
            raise ValueError('Reparse points are not accepted')
    return path.resolve()


def safe_name(value):
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or '\\' in value or ':' in value
            or path.as_posix() != value or any(p in {'.', '..'} or p.endswith((' ', '.'))
                                             or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p)
                                             for p in path.parts)):
        raise ValueError('Invalid archive member: ' + value)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 13) or platform.machine().lower() not in {'amd64', 'x86_64'} or sys.prefix != sys.base_prefix:
        raise ValueError('Requires native Windows CPython 3.13 x64')
    archive, catalog, target = map(local_path, (args.archive, args.catalog, args.target))
    if target.exists() or not target.parent.is_dir():
        raise ValueError('Preserve existing target; its local parent must exist')
    expected_archive = args.sha256.removeprefix('sha256:')
    if not re.fullmatch('[a-f0-9]{64}', expected_archive) or sha(archive) != expected_archive:
        raise ValueError('Archive SHA-256 mismatch')
    lock = next(r for r in json.loads(catalog.read_bytes())['packs'] if r['id'] == args.id)
    with zipfile.ZipFile(archive) as z:
        raw = z.read('manifest.json')
        if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != lock['manifest_sha256']:
            raise ValueError('Manifest differs from the installed CLI pin')
        manifest = json.loads(raw)
        if manifest['id'] != args.id or manifest['protocol'] != 'agent-community-cpu-v1':
            raise ValueError('Model pack ID/protocol mismatch')
        expected = {r['path']: r for r in manifest['files']}
        allowed = set(expected) | {'manifest.json'}
        members = z.infolist()
        names = [m.filename for m in members]
        if set(names) != allowed or len(names) != len(allowed) or len({n.casefold() for n in names}) != len(names):
            raise ValueError('Archive has missing, extra or duplicate files')
        for m in members:
            safe_name(m.filename)
            size = len(raw) if m.filename == 'manifest.json' else expected[m.filename]['bytes']
            if m.file_size != size or ((m.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Archive file metadata differs from manifest')
        temporary = Path(tempfile.mkdtemp(prefix=target.name + '-install-', dir=target.parent)).resolve()
        try:
            for m in members:
                path = temporary / safe_name(m.filename)
                path.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with z.open(m) as source, path.open('xb') as out:
                    while data := source.read(1024 * 1024):
                        out.write(data)
                        digest.update(data)
                expected_digest = lock['manifest_sha256'] if m.filename == 'manifest.json' else expected[m.filename]['sha256']
                if digest.hexdigest() != expected_digest:
                    raise ValueError('Extracted file hash mismatch: ' + m.filename)
            temporary.rename(target)
        except BaseException:
            # Only remove the newly created, checked sibling staging folder.
            if temporary.parent != target.parent or not temporary.name.startswith(target.name + '-install-'):
                raise ValueError('Refusing cleanup outside staging directory')
            shutil.rmtree(temporary)
            raise
    print(json.dumps(dict(ok=True, id=args.id, target=str(target), files=len(expected),
                          archive_sha256=expected_archive, manifest_sha256=lock['manifest_sha256'],
                          network=False, virtual_environment=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
