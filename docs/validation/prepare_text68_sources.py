"""Acquire pinned Unicode inputs and a pure-Python segmentation source archive.

Only a new E-drive staging directory is written. No install, environment,
runtime import, candidate activation or functional test takes place here.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def fetch(url, maximum):
    request = urllib.request.Request(url, headers={'User-Agent': 'agent-editor-kit-source-review/1'})
    with urllib.request.urlopen(request, timeout=45) as response:
        assert response.status == 200
        raw = response.read(maximum + 1)
    assert 0 < len(raw) <= maximum, 'Source response exceeded its explicit budget'
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and len(args.run) <= 32
    STAGE = ROOT / ('local/agent-ffmpeg/text68-20261106-' + args.run)
    upstream = STAGE / 'upstream'
    upstream.mkdir(parents=True, exist_ok=False)
    (STAGE / 'executed-preparation.py').write_bytes(Path(__file__).read_bytes())
    metadata_raw = fetch('https://pypi.org/pypi/uniseg/0.10.1/json', 2 * 1024**2)
    metadata = json.loads(metadata_raw)
    assert metadata['info']['version'] == '0.10.1'
    wheel = next(row for row in metadata['urls'] if row['filename'] == 'uniseg-0.10.1-py3-none-any.whl')
    assert wheel['url'].startswith('https://files.pythonhosted.org/')
    (upstream / 'pypi-uniseg-0.10.1.json').write_bytes(metadata_raw)
    archive = upstream / wheel['filename']
    assert 0 < wheel['size'] <= 16 * 1024**2
    raw = fetch(wheel['url'], 16 * 1024**2)
    assert hashlib.sha256(raw).hexdigest() == wheel['digests']['sha256'] and len(raw) == wheel['size']
    archive.write_bytes(raw)
    originals = upstream / 'uniseg-0.10.1'
    with zipfile.ZipFile(archive) as zipped:
        members = zipped.infolist()
        assert len(members) <= 128 and sum(row.file_size for row in members) <= 128 * 1024**2
        for row in members:
            name = PurePosixPath(row.filename)
            assert not name.is_absolute() and '..' not in name.parts and '\\' not in row.filename and ':' not in row.filename
            assert name.as_posix() == row.filename and (row.external_attr >> 16) & 0o170000 != 0o120000
        for row in members:
            if row.is_dir():
                continue
            target = originals / row.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zipped.read(row))
    base = 'https://www.unicode.org/Public/17.0.0/ucd/'
    inputs = {name: base + name for name in ('auxiliary/GraphemeBreakProperty.txt',
        'auxiliary/GraphemeBreakTest.txt', 'auxiliary/LineBreakTest.txt', 'LineBreak.txt',
        'DerivedCoreProperties.txt', 'UnicodeData.txt', 'EastAsianWidth.txt',
        'extracted/DerivedBidiClass.txt', 'emoji/emoji-data.txt')}
    inputs.update({'unicode-license.txt': 'https://www.unicode.org/license.txt',
        'UAX29-47.html': 'https://www.unicode.org/reports/tr29/tr29-47.html',
        'UAX14-55.html': 'https://www.unicode.org/reports/tr14/tr14-55.html',
        'UAX9-51.html': 'https://www.unicode.org/reports/tr9/tr9-51.html'})
    def acquire(pair):
        name, url = pair
        raw = fetch(url, 8 * 1024**2)
        raw.decode('utf-8-sig')
        target = upstream / 'unicode17' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
        return dict(path=target.relative_to(STAGE).as_posix(), url=url, bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest())
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(acquire, inputs.items()))
    rows.append(dict(path=archive.relative_to(STAGE).as_posix(), url=wheel['url'],
                     bytes=len(archive.read_bytes()), sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
    record = dict(status='downloaded-for-code-review', observed_at_utc=datetime.now(timezone.utc).isoformat(),
        sources=rows, uniseg_source_version='0.10.1', uniseg_original_Unicode_version='16.0.0',
        target_Unicode_version='17.0.0', licenses=['MIT', 'Unicode-3.0'],
        downloaded_code_executed=False, package_installed=False, virtual_environment=False,
        current_portrait_batch_modified=False, functional_tests_started=False)
    (STAGE / 'sources.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in record.items() if k != 'sources'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
