"""Compute the known parent tree using an isolated copy of its index."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/mingw64/bin/git.exe')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and sys.dont_write_bytecode
    prior = ROOT / 'local/agent-ffmpeg/music64-terminal-commit-r2'
    receipt = json.loads((prior / 'verification.json').read_bytes())
    assert receipt['status'] == 'committed-and-pushed'
    assert receipt['commit'] == 'f3f007c8fd7e360efc0943de4f1919914a0934aa'
    source = prior / 'index'
    original = sha(source)
    private = ROOT / ('local/agent-ffmpeg/music65-tree-probe-' + args.run)
    private.mkdir()
    index = private / 'index'
    shutil.copyfile(source, index)
    assert sha(index) == original
    proof = ROOT / 'docs/validation/evidence/music-loading-20261030-r1' / ('tree-probe-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    began = time.monotonic()
    command = [str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', 'write-tree', '--missing-ok']
    report = dict(status='failed', actual_parent=receipt['commit'], expected_tree=receipt['tree'],
        real_index_used=False, source_parent_index_changed=False, branch_mutated=False,
        full_product_goal_closed=False)
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=90,
            creationflags=subprocess.CREATE_NO_WINDOW)
        (proof / 'tree.stdout').write_bytes(result.stdout)
        (proof / 'tree.stderr').write_bytes(result.stderr)
        actual = result.stdout.decode('ascii').strip()
        assert result.returncode == 0 and actual == receipt['tree']
        assert sha(source) == original
        report.update(status='passed', actual_tree=actual, original_parent_index_sha256=original,
            copied_index=str(index), tree_matches_known_committed_parent=True,
            meaning='Computes the identical parent tree in a separate index. This alone does not verify all referenced object payloads or authorize a commit.')
    except BaseException as error:
        report.update(error=repr(error))
    report['elapsed_seconds'] = time.monotonic() - began
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
