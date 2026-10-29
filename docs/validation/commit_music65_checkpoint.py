"""Commit the audited CLI65 scope, preserving the real index and normal push hook."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-loading-20261030-r1'
GIT_ROOT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git')
GIT = GIT_ROOT / 'mingw64/bin/git.exe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and os.name == 'nt' and sys.dont_write_bytecode
    env = dict(os.environ)
    env['PATH'] = str(GIT_ROOT / 'cmd') + os.pathsep + env.get('PATH', '')

    def git(*arguments, input=None, alternate=None, timeout=1200):
        child_env = dict(env)
        if alternate:
            child_env['GIT_INDEX_FILE'] = str(alternate)
        command = [str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
            '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *arguments]
        assert len(subprocess.list2cmdline(command)) < 30000
        result = subprocess.run(command, input=input, cwd=ROOT, env=child_env,
            capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError(result.stderr[-5000:].decode('utf-8', errors='replace'))
        return result.stdout

    receipt = json.loads((BASE / ('checkpoint-' + args.run) / 'verification.json').read_bytes())
    assert receipt['status'] == 'passed' and receipt['live_actual_case_excluded']
    parent = receipt['base_commit']
    assert git('rev-parse', 'HEAD').decode().strip() == parent
    assert git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert git('remote', 'get-url', '--push', 'origin').strip() == b'git@github.com:copypasteltd/agent-editor-kit.git'
    assert all(sha(ROOT / name) == pin for name, pin in receipt['files'].items())
    hooks = ROOT / '.git/hooks'
    configured = subprocess.run([str(GIT), 'config', '--get', 'core.hooksPath'], cwd=ROOT,
        capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    assert configured.returncode in (0, 1)
    if configured.returncode == 0:
        path = Path(configured.stdout.decode().strip())
        hooks = path if path.is_absolute() else ROOT / path
    assert not any((hooks / name).exists() for name in ('pre-commit', 'prepare-commit-msg', 'commit-msg'))
    hook = hooks / 'post-commit'
    assert hook.is_file() and b'git-auto-push.ps1' in hook.read_bytes()
    hook_sha = sha(hook)
    pathspec = ROOT / ('local/agent-ffmpeg/music65-checkpoint-' + args.run + '.nul')
    scope = {name.decode('utf-8') for name in pathspec.read_bytes().split(b'\0') if name}
    assert set(receipt['files']) <= scope and not any('/actual-stage1/' in name for name in scope)
    parsed = {}
    for entry in git('ls-files', '--stage', '-z', '--', *sorted(scope)).split(b'\0')[:-1]:
        metadata, path = entry.split(b'\t', 1)
        mode, oid, stage = metadata.split()
        assert mode == b'100644' and stage == b'0'
        parsed[path.decode('utf-8')] = (mode, oid)
    assert set(parsed) == scope
    content = git('cat-file', '--batch', input=''.join(':' + name + '\n' for name in sorted(scope)).encode('utf-8'))
    offset = 0
    for name in sorted(scope):
        end = content.index(b'\n', offset)
        oid, kind, length = content[offset:end].split()
        assert kind == b'blob' and oid == parsed[name][1]
        length = int(length)
        data = content[end + 1:end + 1 + length]
        working = (ROOT / name).read_bytes()
        if data != working:
            assert not name.startswith('docs/validation/evidence/'), name
            assert git('hash-object', '--path', name, '--stdin', input=working).strip() == oid, name
        offset = end + length + 2
    assert offset == len(content)
    real_index = ROOT / '.git/index'
    real_index_sha = sha(real_index)
    private = ROOT / ('local/agent-ffmpeg/music65-checkpoint-commit-' + args.run)
    private.mkdir()
    alternate = private / 'index'
    old_index = ROOT / 'local/agent-ffmpeg/music64-terminal-commit-r2/index'
    assert old_index.is_file() and not old_index.with_name('index.lock').exists()
    shutil.copyfile(old_index, alternate)
    print('Verifying the exact parent index without scanning the working tree.', flush=True)
    assert git('write-tree', alternate=alternate).strip() == git('rev-parse', parent + '^{tree}').strip()
    additions = b''.join(mode + b' ' + oid + b' 0\t' + name.encode('utf-8') + b'\0'
        for name, (mode, oid) in sorted(parsed.items()))
    git('update-index', '-z', '--index-info', alternate=alternate, input=additions)
    tree = git('write-tree', alternate=alternate).decode().strip()
    changed = {name.decode('utf-8') for name in git('diff-tree', '--no-commit-id', '--name-only',
        '-r', '-z', parent, tree).split(b'\0') if name}
    assert changed and changed <= scope and sha(real_index) == real_index_sha and sha(hook) == hook_sha
    message = private / 'message.txt'
    message.write_text('feat: pin native music weight reads and report complete loading clocks\n',
        encoding='utf-8', newline='\n')
    commit = git('commit-tree', tree, '-p', parent, '-F', str(message)).decode().strip()
    assert git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert git('rev-parse', 'HEAD').decode().strip() == parent
    git('update-ref', '-m', 'commit: native music loader and complete clocks', 'HEAD', commit, parent)
    print('Running the unchanged post-commit hook and ordinary main push.', flush=True)
    pushed = subprocess.run([str(GIT_ROOT / 'usr/bin/sh.exe'), str(hook)], cwd=ROOT, env=env,
        capture_output=True, timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
    (private / 'post-commit.stdout').write_bytes(pushed.stdout)
    (private / 'post-commit.stderr').write_bytes(pushed.stderr)
    assert pushed.returncode == 0, pushed.stderr[-5000:]
    remote = git('ls-remote', 'origin', 'refs/heads/main', timeout=120).decode().split()[0]
    assert remote == commit and sha(real_index) == real_index_sha
    report = dict(status='committed-and-pushed', branch='main', parent=parent, commit=commit, remote=remote,
        tree=tree, scope_files=len(scope), changed_files=len(changed), force=False, real_index_unchanged=True,
        outside_scope_changes_committed=False, original_post_commit_hook_executed=True,
        post_commit_hook_sha256=hook_sha, formal_activation=False, actual_case_excluded=True,
        full_product_goal_closed=False)
    (private / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
