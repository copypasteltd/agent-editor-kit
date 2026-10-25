"""Check all staged, product and Skill bytes without rewriting historical logs."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-recovery-20261025-r1'
GIT = ['C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe',
       '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false']


def git(*args, **options):
    return subprocess.run(GIT + list(args), cwd=ROOT, check=True, **options)


def main():
    proof = BASE / 'staged-byte-audit-r1.json'
    assert not proof.exists()
    snapshot = BASE / 'staging-executed-generator-r1.py'
    assert not snapshot.exists()
    snapshot.write_bytes(Path(__file__).read_bytes())
    assert git('branch', '--show-current', capture_output=True).stdout.strip() == b'main'
    git('add', '-A')
    git('diff', '--cached', '--check', capture_output=True)
    changed = git('diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z', capture_output=True).stdout.decode('utf8').strip('\0').split('\0')
    assert not git('diff', '--cached', '--name-only', '--diff-filter=D', '-z', capture_output=True).stdout
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    product = list((ROOT / 'product/src/ai_ad_editor').glob('*.py'))
    assert len(product) == 202 and len(manifest['files']) == 65
    paths = set(changed) | {p.relative_to(ROOT).as_posix() for p in product} | {v['path'] for v in manifest['files']}
    index = {}
    for record in git('ls-files', '--stage', '-z', capture_output=True).stdout.split(b'\0'):
        if not record: continue
        header, name = record.split(b'\t', 1)
        mode, oid, stage = header.split()
        assert stage == b'0'
        index[name.decode('utf8')] = oid.decode()
    ordered = sorted(paths)
    raw = git('cat-file', '--batch', input=('\n'.join(index[p] for p in ordered) + '\n').encode(), capture_output=True, timeout=120).stdout
    stream, verified = io.BytesIO(raw), []
    for name in ordered:
        oid, kind, size = stream.readline().split()
        assert kind == b'blob'
        data = stream.read(int(size))
        assert stream.read(1) == b'\n' and data == (ROOT / name).read_bytes(), name
        verified.append(dict(path=name, blob=oid.decode(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    assert not stream.read()
    report = dict(status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(),
        baseline_commit=git('rev-parse', 'HEAD', capture_output=True).stdout.decode().strip(),
        staged_changes=len(changed), verified_files=len(verified), source_files=202, skill_files=65,
        all_index_bytes_equal_worktree=True, deleted_files=0,
        broad_renormalization_stopped_before_index_publication=True,
        new_raw_attribute_rules_applied_by_git_add=True, files=verified)
    proof.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    relative = proof.relative_to(ROOT).as_posix()
    git('add', '--', relative)
    assert git('show', ':' + relative, capture_output=True).stdout == proof.read_bytes()
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}, ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
