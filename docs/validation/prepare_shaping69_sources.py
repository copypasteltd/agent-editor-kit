"""Download open text-engine sources and licensed fonts for review, not execution.

Uses a new E-drive owned directory. Does not install packages, invoke a build,
load a native library, alter CLI67 or register a Skill. Archives are inspected
and only regular files in explicitly selected source folders are copied.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import tarfile
from urllib.parse import quote
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PINS = {
    'sheenbidi-v3.0.0.tar.gz': '86c56014034739ba39a24c23eb00323b0bf6f737354f665786015fca842af786',
    'harfbuzz-15.1.0.tar.gz': '5c057929413b8664592fea67edea5c2c47b4ffb0bf5f4accb5164bc6acc69d94',
    'BidiTest.txt': '888bdfc8090652272d1f859cdb00ae659e2dc6c26740be61ef1d03998a687620',
    'BidiCharacterTest.txt': 'a3e6e905ab5afbe318a96df5401d0372a04cd73ef139ab5e3cf0ae241c255488',
}


def fetch(url, budget):
    request = urllib.request.Request(url, headers={'User-Agent': 'agent-editor-kit-source-review/1'})
    with urllib.request.urlopen(request, timeout=50) as response:
        assert response.status == 200
        raw = response.read(budget + 1)
    assert 0 < len(raw) <= budget
    return raw


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def font_names(raw):
    count = struct.unpack_from('>H', raw, 4)[0]
    assert 0 < count <= 256
    table = None
    for index in range(count):
        tag, _, offset, length = struct.unpack_from('>4sIII', raw, 12 + index * 16)
        assert offset + length <= len(raw)
        if tag == b'name':
            table = raw[offset:offset + length]
    assert table is not None
    _, count, offset = struct.unpack_from('>HHH', table)
    result = {}
    for index in range(count):
        platform, encoding, language, name, length, start = struct.unpack_from('>HHHHHH', table, 6 + index * 12)
        if name not in (0, 1, 13, 14):
            continue
        assert offset + start + length <= len(table)
        text = table[offset + start:offset + start + length].decode('utf-16-be' if platform in (0, 3) else 'mac_roman')
        result.setdefault(name, set()).add(text)
    return {str(key): sorted(value) for key, value in result.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--seed-run')
    args = parser.parse_args()
    assert args.run.isalnum() and len(args.run) <= 32
    assert args.seed_run is None or args.seed_run.isalnum() and len(args.seed_run) <= 32
    stage = ROOT / ('local/agent-ffmpeg/shaping69-20261106-' + args.run)
    if args.resume:
        assert stage.is_dir() and not (stage / 'sources.json').exists()
        assert (stage / 'executed-preparation.py').is_file()
        write(stage / 'executed-resumption.py', Path(__file__).read_bytes())
    else:
        stage.mkdir(parents=True, exist_ok=False)
        write(stage / 'executed-preparation.py', Path(__file__).read_bytes())
    base = 'https://www.unicode.org/Public/17.0.0/ucd/'
    requests = [
        ('sheenbidi-v3.0.0.tar.gz', 'https://codeload.github.com/Tehreer/SheenBidi/tar.gz/refs/tags/v3.0.0', 32 * 1024**2),
        ('harfbuzz-15.1.0.tar.gz', 'https://codeload.github.com/harfbuzz/harfbuzz/tar.gz/refs/tags/15.1.0', 64 * 1024**2),
        ('freetype-2.15.0.tar.gz', 'https://codeload.github.com/freetype/freetype/tar.gz/refs/tags/VER-2-15-0', 16 * 1024**2),
        ('BidiTest.txt', base + 'BidiTest.txt', 16 * 1024**2),
        ('BidiCharacterTest.txt', base + 'BidiCharacterTest.txt', 16 * 1024**2),
        ('freetype_py-2.5.1-py3-none-win_amd64.whl', 'https://files.pythonhosted.org/packages/93/6e/bd7fbfacca077bc6f34f1a1109800a2c41ab50f4704d3a0507ba41009915/freetype_py-2.5.1-py3-none-win_amd64.whl', 2 * 1024**2),
    ]
    for project, folder, family in [('arabic', 'notosansarabic', 'NotoSansArabic'),
                                    ('hebrew', 'notosanshebrew', 'NotoSansHebrew'),
                                    ('latin-greek-cyrillic', 'notoserif', 'NotoSerif'),
                                    ('devanagari', 'notosansdevanagari', 'NotoSansDevanagari')]:
        build = 'unhinted' if family == 'NotoSerif' else 'full'
        font_url = 'https://notofonts.github.io/' + project + '/fonts/' + family + '/' + build + '/ttf/' + family + '-Regular.ttf'
        requests.append(('fonts/' + folder + '/' + family + '-Regular.ttf', font_url, 8 * 1024**2))
    def acquire(row):
        name, url, budget = row
        target = stage / 'upstream' / name
        cached = args.resume and target.is_file()
        seed = ROOT / ('local/agent-ffmpeg/shaping69-20261106-' + args.seed_run) / 'upstream' / name if args.seed_run else None
        seeded = seed is not None and name in SOURCE_PINS and seed.is_file()
        extra = {}
        if cached:
            raw = target.read_bytes()
        elif seeded:
            raw = seed.read_bytes()
        elif name.startswith('fonts/'):
            raw = fetch(url, budget)
        else:
            raw = fetch(url, budget)
        if name.startswith('fonts/'):
            names = font_names(raw)
            assert any('SIL Open Font License' in value for value in names['13'])
            assert any('openfontlicense.org' in value or 'scripts.sil.org/OFL' in value for value in names['14'])
            standard = (ROOT / 'product/src/ai_ad_editor/material_data/licenses/google-notosanssc.txt').read_text('utf-8')
            standard = standard[standard.index('SIL OPEN FONT LICENSE Version 1.1'):]
            license_text = '\n'.join(names['0']) + '\n\n' + '\n'.join(names['13']) + '\n' + '\n'.join(names['14']) + '\n\n' + standard
            license_path = target.parent / 'OFL.txt'
            if license_path.exists():
                assert license_path.read_bytes() == license_text.encode('utf-8')
            else:
                write(license_path, license_text.encode('utf-8'))
            extra['embedded_font_names'] = names
            extra['license_path'] = (target.parent / 'OFL.txt').relative_to(stage).as_posix()
            extra['license_sha256'] = hashlib.sha256(license_text.encode('utf-8')).hexdigest()
        assert 0 < len(raw) <= budget
        if name in SOURCE_PINS:
            assert hashlib.sha256(raw).hexdigest() == SOURCE_PINS[name]
        if name.endswith('.whl'):
            assert hashlib.sha256(raw).hexdigest() == '0b7f8e0342779f65ca13ef8bc103938366fecade23e6bb37cb671c2b8ad7f124'
        if not cached:
            write(target, raw)
        return dict(path='upstream/' + name, url=url, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), reused_download_bytes=cached or seeded, **extra)
    def recorded(row):
        try:
            return acquire(row)
        except Exception as exc:
            return dict(path='upstream/' + row[0], url=row[1], error=type(exc).__name__, detail=str(exc))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(recorded, requests))
    errors = [row for row in results if 'error' in row]
    if errors:
        name = 'resumption-download-failures.json' if args.resume else 'download-failures.json'
        write(stage / name, (json.dumps(dict(status='download-incomplete-no-source-executed', sources=results), ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        print(json.dumps(dict(status='download-incomplete-no-source-executed', failures=errors), ensure_ascii=False))
        return 1
    extracted = []
    for archive_name, folders, extras in [
        ('sheenbidi-v3.0.0.tar.gz', ('Source/', 'Headers/'), ('LICENSE', 'CMakeLists.txt', 'README.md')),
        ('harfbuzz-15.1.0.tar.gz', ('src/',), ('COPYING', 'README.md', 'meson.build')),
        ('freetype-2.15.0.tar.gz', ('src/', 'include/', 'docs/'), ('LICENSE.TXT',)),
    ]:
        target = stage / 'upstream' / archive_name.removesuffix('.tar.gz')
        with tarfile.open(fileobj=io.BytesIO((stage / 'upstream' / archive_name).read_bytes()), mode='r:gz') as archived:
            rows = archived.getmembers()
            assert len(rows) <= 30000 and sum(row.size for row in rows) <= 512 * 1024**2
            for row in rows:
                path = PurePosixPath(row.name)
                assert not path.is_absolute() and '..' not in path.parts and '\\' not in row.name and ':' not in row.name
                if len(path.parts) < 2 or not row.isreg():
                    continue
                relative = PurePosixPath(*path.parts[1:]).as_posix()
                if relative not in extras and not relative.startswith(folders):
                    continue
                stream = archived.extractfile(row)
                assert stream is not None
                raw = stream.read()
                assert len(raw) == row.size
                output = target / relative
                write(output, raw)
                extracted.append(dict(path=output.relative_to(stage).as_posix(), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    wheel = stage / 'upstream/freetype_py-2.5.1-py3-none-win_amd64.whl'
    with zipfile.ZipFile(wheel) as zipped:
        rows = zipped.infolist()
        assert len(rows) <= 256 and sum(row.file_size for row in rows) <= 16 * 1024**2
        for row in rows:
            path = PurePosixPath(row.filename)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in row.filename and ':' not in row.filename
            assert (row.external_attr >> 16) & 0o170000 != 0o120000
            if row.is_dir():
                continue
            raw = zipped.read(row)
            output = stage / 'upstream/freetype-py-2.5.1' / row.filename
            write(output, raw)
            extracted.append(dict(path=output.relative_to(stage).as_posix(), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    record = dict(status='downloaded-for-review-not-executed', observed_at_utc=datetime.now(timezone.utc).isoformat(),
        sources=results, extracted=extracted, licenses_to_review=['Apache-2.0', 'HarfBuzz', 'MIT', 'FTL', 'OFL-1.1', 'Unicode-3.0'],
        source_code_executed=False, native_libraries_loaded=False, packages_installed=False,
        virtual_environment=False, current_product_or_skill_modified=False, functional_tests_started=False)
    write(stage / 'sources.json', (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({key: value for key, value in record.items() if key not in ('sources', 'extracted')}, ensure_ascii=False))
    print(json.dumps(dict(downloaded=len(results), extracted=len(extracted))))


if __name__ == '__main__':
    raise SystemExit(main())
