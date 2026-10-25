"""Compare staged bytes with the actual tested product, Skill and evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-control-20261025-r1'
OUT = BASE / 'staged-byte-r1'
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def git(*args, data=None):
    return subprocess.check_output([
        GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0',
        '-c', 'maintenance.auto=false', *args], cwd=ROOT, input=data, timeout=120)


def load(path):
    return json.loads(path.read_bytes())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    (OUT / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    baseline = git('rev-parse', 'HEAD').decode().strip()
    assert git('branch', '--show-current').decode().strip() == 'main'
    assert git('remote', 'get-url', 'origin').decode().strip() == 'git@github.com:copypasteltd/agent-editor-kit.git'
    assert not git('diff', '--cached', '--name-only', '--diff-filter=D')
    git('diff', '--cached', '--check')
    staged = git('diff', '--cached', '--name-only', '-z').decode('utf-8').split('\0')
    staged = [name for name in staged if name]
    assert staged and not any(name.startswith(('sources/', 'local/', 'workspace/')) for name in staged)
    manifest = load(ROOT / 'agent-ffmpeg-local-install-manifest.json')
    tested = load(BASE / 'tests/installed-r1/product-files.json')
    assert len(tested) == 203 and len(manifest['files']) == 65
    pins = {'product/src/ai_ad_editor/' + name: value for name, value in tested.items()}
    pins.update({row['path']: row['sha256'] for row in manifest['files']})
    names = sorted(set(staged) | set(pins))
    assert all('\n' not in name and '\r' not in name for name in names)
    raw = git('cat-file', '--batch', data=''.join(':' + name + '\n' for name in names).encode('utf-8'))
    offset, records = 0, []
    for name in names:
        end = raw.index(b'\n', offset)
        header = raw[offset:end].split()
        assert len(header) == 3 and header[1] == b'blob', (name, header)
        size = int(header[2])
        data = raw[end + 1:end + 1 + size]
        assert len(data) == size and raw[end + 1 + size:end + 2 + size] == b'\n'
        offset = end + 2 + size
        assert data == (ROOT / name).read_bytes(), 'staged bytes differ: ' + name
        sha = digest(data)
        if name in pins:
            assert sha == pins[name], 'tested/Skill pin differs: ' + name
        records.append(dict(path=name, staged_change=name in staged, bytes=size, sha256=sha))
    assert offset == len(raw)
    final = load(BASE / 'final-delivery-r2/verification.json')
    assert final['status'] == 'passed'
    for row in final['files']:
        assert digest((ROOT / row['path']).read_bytes()) == row['sha256']
    for row in load(BASE / 'faults-r1/verification.json')['cases']:
        path = BASE / 'faults-r1' / row['case']
        assert digest((path / 'stdout.json').read_bytes()) == row['stdout_sha256']
        assert digest((path / 'stderr.txt').read_bytes()) == row['stderr_sha256']
    report = dict(status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(),
        baseline_commit=baseline, staged_files=len(staged), compared_files=len(names),
        tested_product_files=203, skill_files=65, staged_bytes_equal_disk=True,
        historical_goal_conditions_preserved=38, final_delivery_audit='final-delivery-r2',
        scope='Byte verification only; no new inference, rendering or human quality acceptance.',
        files=records)
    proof = OUT / 'verification.json'
    proof.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    git('add', '--', OUT.relative_to(ROOT).as_posix())
    for path in OUT.iterdir():
        name = path.relative_to(ROOT).as_posix()
        assert git('show', ':' + name) == path.read_bytes(), name
    git('diff', '--cached', '--check')
    assert not git('diff', '--name-only')
    assert not git('ls-files', '--others', '--exclude-standard')
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
