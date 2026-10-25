"""Verify staged product blobs retain the exact separately installed Python bytes."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def main():
    def git(*args, input=None):
        return subprocess.check_output([GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false',
            '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args], cwd=ROOT, input=input)
    raw = git('ls-files', '--stage', '-z', '--', 'product/src/ai_ad_editor/*.py')
    indexed = []
    for item in raw.decode('utf-8').split('\0'):
        if not item:
            continue
        detail, name = item.split('\t', 1)
        mode, digest, stage = detail.split()
        assert stage == '0' and mode == '100644'
        indexed.append((name, digest))
    assert len(indexed) == 195
    raw_hashes = git('hash-object', '--no-filters', '--stdin-paths',
        input=('\n'.join(name for name, _ in indexed) + '\n').encode('utf-8')).decode('ascii').splitlines()
    assert len(raw_hashes) == len(indexed)
    installed = Path(json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())['installed_directory'])
    comparisons = []
    for (name, staged), actual in zip(indexed, raw_hashes):
        source = ROOT / name
        data = source.read_bytes()
        assert staged == actual
        assert data == (installed / 'site' / source.relative_to(ROOT / 'product/src')).read_bytes()
        comparisons.append(dict(path=name, staged_git_blob=staged, sha256=hashlib.sha256(data).hexdigest()))
    output = ROOT / 'docs/validation/evidence/goal-gaps-20261025-r8/staged-source-comparison.json'
    assert not output.exists()
    output.write_text(json.dumps(dict(status='passed', files=195, staged_raw_and_installed_equal=True,
        comparisons=comparisons), ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(status='passed', files=195, staged_raw_and_installed_equal=True)), flush=True)


if __name__ == '__main__':
    main()
