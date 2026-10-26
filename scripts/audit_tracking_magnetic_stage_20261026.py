"""Compare every staged byte with disk, installed test pins and unified Skill pins."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/tracking-magnetic-20261026-r1'
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def git(*args, data=None):
    return subprocess.check_output([GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0',
        '-c', 'maintenance.auto=false', *args], cwd=ROOT, input=data, timeout=600)


def load(path):
    return json.loads(path.read_bytes())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',default='r1');args=parser.parse_args()
    assert __import__('re').fullmatch(r'r[1-9][0-9]*',args.run)
    OUT=BASE/('staged-byte-'+args.run)
    OUT.mkdir(exist_ok=False)
    (OUT/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    baseline = git('rev-parse', 'HEAD').decode().strip()
    assert baseline == '8dd9e69c56ad5f46e723f6f1c2d2a4a866f4b3bd'
    assert git('branch', '--show-current').decode().strip() == 'main'
    assert git('remote', 'get-url', 'origin').decode().strip() == 'git@github.com:copypasteltd/agent-editor-kit.git'
    assert not git('diff', '--cached', '--name-only', '--diff-filter=D')
    git('diff', '--cached', '--check')
    staged = [name for name in git('diff', '--cached', '--name-only', '-z').decode('utf8').split('\0') if name]
    assert staged and not any(name.startswith(('sources/', 'local/', 'workspace/')) for name in staged)
    manifest = load(ROOT/'agent-ffmpeg-local-install-manifest.json')
    tested = load(BASE/'final-delivery-r2/product-files.json')
    assert len(tested) == 220 and len(manifest['files']) == 73
    pins = {'product/src/ai_ad_editor/'+name: value for name, value in tested.items()}
    pins.update({row['path']: row['sha256'] for row in manifest['files']})
    names = sorted(set(staged)|set(pins))
    assert all('\n' not in name and '\r' not in name for name in names)
    raw = git('cat-file', '--batch', data=''.join(':'+name+'\n' for name in names).encode('utf8'))
    offset, records = 0, []
    for name in names:
        end = raw.index(b'\n', offset); header = raw[offset:end].split()
        assert len(header) == 3 and header[1] == b'blob', (name, header)
        size = int(header[2]); data = raw[end+1:end+1+size]
        assert len(data) == size and raw[end+1+size:end+2+size] == b'\n'
        offset = end+2+size
        assert data == (ROOT/name).read_bytes(), 'Staged bytes differ: '+name
        checksum = digest(data)
        if name in pins:
            assert checksum == pins[name], 'Tested/Skill pin differs: '+name
        records.append(dict(path=name, staged_change=name in staged, bytes=size, sha256=checksum))
    assert offset == len(raw)
    final = load(BASE/'final-delivery-r2/verification.json')
    assert final['status'] == 'passed'
    for row in final['files']:
        assert digest((ROOT/row['path']).read_bytes()) == row['sha256']
    import re
    from urllib.parse import unquote
    extra_links = 0
    for name in staged:
        if not name.endswith('.md'):
            continue
        path = ROOT/name
        for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)', path.read_text('utf-8-sig')):
            target = match[1].strip().strip('<>')
            if re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I) or target.startswith('#'):
                continue
            assert (path.parent/unquote(target.split('#',1)[0])).exists(), (name,target)
            extra_links += 1
    report = dict(extra_staged_document_links=extra_links, status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(), baseline_commit=baseline,
        staged_files=len(staged), compared_files=len(names), tested_product_files=220, skill_files=73,
        staged_bytes_equal_disk=True, historical_goal_conditions_preserved=38, final_delivery_audit='final-delivery-r2',
        scope='Byte verification only; no new inference, rendering or human quality acceptance.',
        files=records)
    (OUT/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    git('add', '--', OUT.relative_to(ROOT).as_posix())
    for path in OUT.iterdir():
        assert git('show', ':'+path.relative_to(ROOT).as_posix()) == path.read_bytes(), path
    git('diff', '--cached', '--check')
    assert not git('diff', '--name-only')
    assert not git('ls-files', '--others', '--exclude-standard')
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
