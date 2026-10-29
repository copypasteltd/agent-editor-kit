"""Commit an audited exact scope without refreshing unrelated HDD files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    assert args.run.isalnum() and sys.dont_write_bytecode
    env = dict(os.environ)
    env['PATH'] = str(GIT.parent) + os.pathsep + env.get('PATH', '')

    native_git = GIT.parent.parent / 'mingw64/bin/git.exe'
    assert native_git.is_file()

    def git(*arguments, input=None, alternate=None, timeout=1200):
        child_env = dict(env)
        if alternate:
            child_env['GIT_INDEX_FILE'] = str(alternate)
        command = [str(native_git), '--no-optional-locks', '-c', 'core.fsmonitor=false',
            '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *arguments]
        assert len(subprocess.list2cmdline(command)) < 30000
        result = subprocess.run(command, input=input, cwd=ROOT, env=child_env,
            capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError(result.stderr[-5000:].decode('utf-8', errors='replace'))
        return result.stdout

    receipt = json.loads((BASE / ('followup-' + args.run) / 'verification.json').read_bytes())
    assert receipt['status'] == 'passed'
    before = receipt['base_commit']
    assert git('rev-parse', 'HEAD').decode().strip() == before
    assert git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert git('remote', 'get-url', '--push', 'origin').strip() == b'git@github.com:copypasteltd/agent-editor-kit.git'
    assert all(sha(ROOT / p) == pin for p,pin in receipt['files'].items())
    hooks = ROOT / '.git/hooks'
    configured = subprocess.run([str(GIT), 'config', '--get', 'core.hooksPath'], cwd=ROOT,
        capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    assert configured.returncode in (0, 1)
    if configured.returncode == 0:
        configured_path = Path(configured.stdout.decode().strip())
        hooks = configured_path if configured_path.is_absolute() else ROOT / configured_path
    # No validation/message hook may be skipped by the exact-tree operation.
    assert not any((hooks / name).exists() for name in ('pre-commit', 'prepare-commit-msg', 'commit-msg'))
    post = hooks / 'post-commit'
    assert post.is_file() and b'git-auto-push.ps1' in post.read_bytes()
    hook_sha = sha(post)
    scope_file = ROOT / ('local/agent-ffmpeg/music64-followup-' + args.run + '.nul')
    scope = {p.decode('utf-8') for p in scope_file.read_bytes().split(b'\0') if p}
    self_relative = Path(__file__).resolve().relative_to(ROOT).as_posix()
    git('add', '--', self_relative)
    scope.add(self_relative)
    assert all((ROOT / p).is_file() for p in scope)
    # Capture only stage0 entries of this audited scope, retaining any other index entries.
    staged = git('ls-files', '--stage', '-z', '--', *sorted(scope))
    entries = staged.split(b'\0')[:-1]
    parsed = {}
    for entry in entries:
        metadata, path = entry.split(b'\t', 1)
        mode, oid, stage = metadata.split()
        assert stage == b'0' and mode == b'100644'
        parsed[path.decode('utf-8')] = (mode, oid)
    assert set(parsed) == scope
    # Raw captures match exact bytes. Authored text follows its Git clean rule.
    data = git('cat-file', '--batch', input=''.join(':' + p + '\n' for p in sorted(scope)).encode('utf-8'))
    offset = 0
    for path in sorted(scope):
        stop = data.index(b'\n', offset)
        oid, kind, size = data[offset:stop].split()
        assert kind == b'blob' and oid == parsed[path][1]
        size = int(size)
        working = (ROOT / path).read_bytes()
        if data[stop + 1:stop + 1 + size] != working:
            assert path not in receipt['raw_staged_Git_blobs_equal_captured_bytes'], path
            assert git('hash-object', '--path', path, '--stdin', input=working).strip() == oid, path
        offset = stop + size + 2
    assert offset == len(data)
    real_index = ROOT / '.git/index'
    original_index_sha = sha(real_index)
    private = ROOT / ('local/agent-ffmpeg/music64-exact-commit-' + args.run)
    private.mkdir(exist_ok=args.resume)
    alternate = private / 'index'
    if args.resume:
        assert alternate.is_file() and not (private / 'index.lock').exists()
        assert git('write-tree', alternate=alternate).strip() == git('rev-parse', before + '^{tree}').strip()
    else:
        git('read-tree', before, alternate=alternate)
    additions = b''.join(mode + b' ' + oid + b' 0\t' + path.encode('utf-8') + b'\0'
        for path,(mode,oid) in sorted(parsed.items()))
    git('update-index', '-z', '--index-info', alternate=alternate, input=additions)
    tree = git('write-tree', alternate=alternate).decode().strip()
    changed = {p.decode('utf-8') for p in git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', before, tree).split(b'\0') if p}
    assert changed and changed <= scope
    assert sha(real_index) == original_index_sha
    message = private / 'message.txt'
    message.write_text('docs: preserve neural music evidence and report installed validation\n', encoding='utf-8', newline='\n')
    commit = git('commit-tree', tree, '-p', before, '-F', str(message)).decode().strip()
    assert git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert sha(post) == hook_sha and sha(real_index) == original_index_sha
    git('update-ref', '-m', 'commit: preserve music evidence and installed validation', 'HEAD', commit, before)
    assert git('rev-parse', 'HEAD').decode().strip() == commit
    # Execute the unchanged existing post-commit hook, including the normal push.
    shell = GIT.parent.parent / 'usr/bin/sh.exe'
    assert shell.is_file()
    pushed = subprocess.run([str(shell), str(post)], cwd=ROOT, env=env, capture_output=True,
        timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
    (private / 'post-commit.stdout').write_bytes(pushed.stdout)
    (private / 'post-commit.stderr').write_bytes(pushed.stderr)
    if pushed.returncode:
        raise RuntimeError(pushed.stderr[-5000:].decode('utf-8', errors='replace'))
    remote = git('ls-remote', 'origin', 'refs/heads/main', timeout=120).decode().split()[0]
    assert remote == commit and sha(real_index) == original_index_sha
    report = dict(status='committed-and-pushed', branch='main', commit=commit, remote=remote,
        parent=before, tree=tree, files=len(changed), scope_files=len(scope), force=False,
        method='audited stage0 entries over parent tree; atomic HEAD compare-and-swap',
        real_index_unchanged=True, outside_scope_changes_committed=False,
        pre_commit_or_message_hooks_present=False, original_post_commit_hook_executed=True,
        post_commit_hook_sha256=hook_sha, formal_activation=False,
        full_product_goal_closed=False, natural_music_quality_accepted=False)
    output = ROOT / ('local/agent-ffmpeg/music64-followup-commit-' + args.run + '.json')
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
