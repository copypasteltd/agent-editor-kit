"""Write-ahead publication and recovery of owned semantic asset directories."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

from .utils import atomic_write_json, sha256_file

PREFIXES = {'semantic-index': 'assets/semantic', 'semantic-calibrate': 'assets/semantic-calibration'}
MAX_FILES = 4098  # 4096 preview rows, vectors and index manifest.


def identity(path):
    stat = path.stat()
    if not path.is_dir() or not stat.st_ino:
        raise ValueError('Publication requires an ordinary directory with stable identity')
    return dict(device=stat.st_dev, inode=stat.st_ino)


def inventory(root, directory):
    from .job_workspaces import _identity, _owned
    files, directories, stack = {}, {}, [directory]
    while stack:
        parent = _owned(root, stack.pop())
        for path in parent.iterdir():
            path = _owned(root, path)
            relative = path.relative_to(directory).as_posix()
            if path.is_dir():
                directories[relative] = identity(path); stack.append(path)
            elif path.is_file():
                files[relative] = dict(identity=_identity(path), sha256='sha256:' + sha256_file(path))
            else:
                raise ValueError('Unknown publication tree entry')
            if len(files) > MAX_FILES or len(files) + len(directories) > 10000:
                raise ValueError('Semantic publication tree budget exceeded')
    return files, directories


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or any(part in ('', '.', '..') for part in value.split('/'))
            or Path(value).is_absolute()):
        raise ValueError('Invalid publication tree member')
    return value


def plan(root, item, kind, references, *, preserve_outputs=False):
    from .job_workspaces import _owned
    prefix = PREFIXES.get(kind)
    if (not prefix or not isinstance(item, dict) or not isinstance(item.get('path'), str)
            or not re.fullmatch(re.escape(prefix) + r'/[0-9a-f]{24}', item['path'])
            or not isinstance(item.get('identity'), dict)
            or not isinstance(item.get('files'), dict) or not 1 <= len(item['files']) <= MAX_FILES
            or not isinstance(item.get('directories'), dict)):
        raise ValueError('Invalid semantic publication intent')
    directory = _owned(root, root / item['path'])
    for relative, entry in item['files'].items():
        _relative(relative)
        if (not isinstance(entry, dict) or not isinstance(entry.get('identity'), dict)
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', str(entry.get('sha256')))):
            raise ValueError('Invalid semantic publication file intent')
    for relative, entry in item['directories'].items():
        _relative(relative)
        if not isinstance(entry, dict):
            raise ValueError('Invalid semantic publication directory intent')
    status = 'missing'
    if directory.exists():
        if identity(directory) != item['identity']:
            status = 'changed_preserved'
        else:
            files, directories = inventory(root, directory)
            # Missing entries can be the result of interrupted explicit cleanup.
            changed = (any(item['files'].get(k) != v for k, v in files.items())
                or any(item['directories'].get(k) != v for k, v in directories.items()))
            if changed:
                status = 'changed_preserved'
            elif any(path == directory or path.is_relative_to(directory) for path in references):
                status = 'referenced_preserved'
            elif preserve_outputs:
                status = 'delivered_preserved'
            else:
                status = 'owned_unreferenced'
    return dict(path=item['path'], status=status, files=len(item['files']), identity=item['identity'])


def publish(workspace, stage, destination):
    from .job_workspaces import MAX_MANIFEST_BYTES, _owned
    stage, destination = _owned(workspace.root, stage), _owned(workspace.root, destination)
    if not stage.is_relative_to(workspace.path) or stage == workspace.path:
        raise ValueError('Semantic publication stage must belong to its managed job')
    if destination.exists() or workspace.record.get('trees'):
        raise FileExistsError('Semantic publication target exists or tree already planned')
    files, directories = inventory(workspace.root, stage)
    intent = dict(path=destination.relative_to(workspace.root).as_posix(), identity=identity(stage),
        files=files, directories=directories)
    plan(workspace.root, intent, workspace.record['kind'], set())
    # Flush before recording the identity/hash intent and making the public path.
    for relative in files:
        with (stage / relative).open('r+b') as stream:
            stream.flush(); os.fsync(stream.fileno())
    workspace.record['trees'] = [intent]
    if len(json.dumps(workspace.record, ensure_ascii=False, indent=2).encode('utf8')) >= MAX_MANIFEST_BYTES:
        workspace.record.pop('trees')
        raise ValueError('Semantic publication manifest byte budget exceeded')
    atomic_write_json(workspace.path / 'job.json', workspace.record)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # All supported execution is native Windows: rename refuses an existing target.
    os.rename(stage, destination)
    if identity(destination) != intent['identity']:
        raise ValueError('Semantic publication changed directory identity')


def remove(root, item, kind):
    from .job_workspaces import _identity, _owned
    if plan(root, item, kind, set())['status'] != 'owned_unreferenced':
        raise ValueError('Semantic publication changed before cleanup')
    directory = _owned(root, root / item['path'])
    for relative, expected in item['files'].items():
        path = _owned(root, directory / relative)
        if path.exists():
            if _identity(path) != expected['identity'] or 'sha256:' + sha256_file(path) != expected['sha256']:
                raise ValueError('Semantic output changed during cleanup')
            path.unlink()
    for relative in sorted(item['directories'], key=lambda name: len(Path(name).parts), reverse=True):
        path = _owned(root, directory / relative)
        if path.exists():
            if identity(path) != item['directories'][relative]:
                raise ValueError('Semantic directory changed during cleanup')
            path.rmdir()
    if identity(directory) != item['identity']:
        raise ValueError('Semantic root changed during cleanup')
    directory.rmdir()
