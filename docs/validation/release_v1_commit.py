"""Commit only reviewed stable-release files while preserving unrelated staging."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_v1 as r

HOOK_SHA = 'e967944116d6d1b35ed5da2ea10b0664fd32c1c9f858f5be414d00a008b37dfd'


def entries(raw):
    rows = {}
    for record in raw.split(b'\0'):
        if record:
            header, name = record.split(b'\t', 1)
            mode, oid, stage = header.split()
            assert stage == b'0', 'Do not commit across unresolved index conflicts'
            rows[name] = (mode, oid, record)
    return rows


def outside(raw, scope):
    digest = hashlib.sha256()
    count = 0
    for name, (_, _, record) in sorted(entries(raw).items()):
        if name not in scope:
            digest.update(record + b'\0')
            count += 1
    return dict(sha256=digest.hexdigest(), entries=count)


def tree(parent, scoped):
    class Node:
        def __init__(self, oid=None):
            self.children = {}
            if oid:
                for record in r.git('ls-tree', '-z', oid).split(b'\0'):
                    if record:
                        header, name = record.split(b'\t', 1)
                        self.children[name] = tuple(header.split())
        def update(self, parts, mode, oid):
            name = parts[0]
            if len(parts) == 1:
                self.children[name] = (mode, b'blob', oid)
                return
            value = self.children.get(name)
            if not isinstance(value, Node):
                assert value is None or value[1] == b'tree'
                value = Node(value[2].decode() if value else None)
                self.children[name] = value
            value.update(parts[1:], mode, oid)
        def write(self):
            rows = []
            for name, value in self.children.items():
                if isinstance(value, Node):
                    value = (b'040000', b'tree', value.write())
                rows.append(b' '.join(value) + b'\t' + name + b'\0')
            return r.git('mktree', '-z', data=b''.join(rows)).strip()
    node = Node(r.git('rev-parse', parent + '^{tree}').decode().strip())
    for path, (mode, oid) in scoped.items():
        node.update(path.split(b'/'), mode, oid)
    result = node.write().decode()
    changed = set(filter(None, r.git('diff-tree', '--no-commit-id', '--name-only',
        '--no-renames', '-r', '-z', parent, result).split(b'\0')))
    assert changed == set(scoped), 'Tree must change precisely the reviewed files'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', type=Path, required=True)
    parser.add_argument('--message', type=Path, required=True)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z0-9-]+', args.run)
    scope = r.load(args.scope)
    assert isinstance(scope, dict) and scope
    assert all(isinstance(name, str) and '\n' not in name and '\r' not in name
        and name in ('README.md', 'README.zh-TW.md', 'README.en.md', 'agent-ffmpeg-local-install-manifest.json')
        or isinstance(name, str) and name.startswith(('docs/', 'skills/agent-ffmpeg-local-editor/')) for name in scope)
    assert all(r.sha(r.ROOT / name) == pin for name, pin in scope.items())
    r.scan(r.ROOT / name for name in scope)
    scratch = r.WORK / ('commit-' + args.run)
    scratch.mkdir()
    parent = r.git('rev-parse', 'HEAD').decode().strip()
    assert r.git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert r.git('remote', 'get-url', '--push', 'origin').decode().strip() == 'git@github.com:' + r.REPO + '.git'
    names = {name.encode('utf-8') for name in scope}
    before = outside(r.git('ls-files', '--stage', '-z'), names)
    (scratch / 'index.before').write_bytes(r.git('ls-files', '--stage', '-z'))
    objects = r.git('hash-object', '-w', '--stdin-paths', data=('\n'.join(scope) + '\n').encode('utf-8')).splitlines()
    assert len(objects) == len(scope)
    scoped = {name.encode('utf-8'): (b'100644', oid) for name, oid in zip(scope, objects)}
    new_tree = tree(parent, scoped)
    r.git('diff-tree', '--check', parent, new_tree)
    commit = r.git('commit-tree', new_tree, '-p', parent, '-F', args.message).decode().strip()
    hook = Path(r.git('rev-parse', '--path-format=absolute', '--git-path', 'hooks/post-commit').decode().strip())
    assert r.sha(hook) == HOOK_SHA
    state = dict(status='prepared', parent=parent, commit=commit, scope_files=len(scope),
        outside_scope_staging_before=before, main=True, force=False)
    r.save(scratch / 'state.json', state)
    r.git('update-ref', 'refs/heads/main', commit, parent)
    r.git('update-index', '-z', '--index-info', data=b''.join(
        mode + b' ' + oid + b'\t' + path + b'\0' for path, (mode, oid) in scoped.items()))
    assert outside(r.git('ls-files', '--stage', '-z'), names) == before
    state['status'] = 'committed'
    r.save(scratch / 'state.json', state)
    shell = Path('C:/Program Files/Git/bin/bash.exe')
    env = dict(r.ENV, PATH=str(r.GIT.parent) + os.pathsep + str(shell.parent) + os.pathsep + r.ENV.get('PATH', ''))
    with (scratch / 'push.stdout').open('xb') as stdout, (scratch / 'push.stderr').open('xb') as stderr:
        result = subprocess.run([str(shell), str(hook)], cwd=r.ROOT, env=env,
            stdout=stdout, stderr=stderr, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
    state['push_exit_code'] = result.returncode
    r.save(scratch / 'state.json', state)
    assert result.returncode == 0, 'Push did not succeed; retain commit and inspect logs'
    assert r.git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit
    assert outside(r.git('ls-files', '--stage', '-z'), names) == before
    assert all(r.sha(r.ROOT / name) == pin for name, pin in scope.items())
    state.update(status='committed-and-pushed', outside_scope_staging_unchanged=True)
    r.save(scratch / 'verification.json', state)
    print(json.dumps(state), flush=True)


if __name__ == '__main__':
    main()
