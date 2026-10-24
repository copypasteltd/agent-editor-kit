"""Collect original redistribution notices for the optional CT2 Windows GPU wheel.

Development-only network access; does not install Intel software or start it.
The CPU Ruy build does not ship these proprietary numerical dependencies.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import base64
import hashlib
import json
import urllib.request
import zipfile

from acquire_material_community_sources import TLS, acquire

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'product/.runtime/materials-20261024'
SOURCE = ROOT / 'sources/materials-20261024'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    output = SOURCE / 'vendor-notices/ctranslate2-4.8.3-win'
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'provenance.json').exists():
        raise ValueError('Completed acquisition receipt is preserved')
    rows = []
    for package in ('intel-openmp', 'mkl'):
        meta = json.loads((SOURCE / 'research' / (package + '-2025.3.json')).read_bytes())
        record = next(row for row in meta['urls'] if row['filename'].endswith('win_amd64.whl'))
        rows.append(dict(id=package, name=record['filename'], url=record['url'],
                         sha256=record['digests']['sha256'], source='https://pypi.org/project/' + package + '/2025.3.0/'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        downloads = list(pool.map(acquire, rows))
    receipts = []
    wheel_omp = WORK / 'downloads' / downloads[0]['name']
    existing_omp = ROOT / 'local/agent-ffmpeg/community-packs-r4/opus-zh-en-cuda12-int8/site/ctranslate2/libiomp5md.dll'
    for row in downloads:
        notices = []
        with zipfile.ZipFile(WORK / 'downloads' / row['name']) as zipped:
            for name in zipped.namelist():
                if not name.endswith('/') and any(term in Path(name).name.lower() for term in ('license', 'notice', 'copying', 'eula')):
                    target = output / row['id'] / Path(name).name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    data = zipped.read(name)
                    if target.exists() and target.read_bytes() != data:
                        raise ValueError('Preserve earlier differing notice: ' + str(target))
                    if not target.exists():
                        target.write_bytes(data)
                    notices.append(dict(wheel_path=name, path=target.relative_to(SOURCE).as_posix(), sha256=sha(target)))
        if not notices:
            raise ValueError('Original wheel has no redistribution notices: ' + row['id'])
        receipts.append({**row, 'notices': notices})
    with zipfile.ZipFile(wheel_omp) as zipped:
        omp_name = next(name for name in zipped.namelist() if name.endswith('/libiomp5md.dll'))
        wheel_sha = hashlib.sha256(zipped.read(omp_name)).hexdigest()
    if sha(existing_omp) != wheel_sha:
        raise ValueError('Intel OpenMP DLL does not match the official 2025.3 wheel')
    for name in ('LICENSE', 'THIRD-PARTY-PROGRAMS'):
        url = 'https://raw.githubusercontent.com/oneapi-src/oneDNN/v3.1.1/' + name
        api_url = 'https://api.github.com/repos/oneapi-src/oneDNN/contents/' + name + '?ref=v3.1.1'
        request = urllib.request.Request(api_url, headers={'User-Agent': 'agent-editor-kit-source-notices'})
        with urllib.request.urlopen(request, context=TLS, timeout=60) as response:
            api = json.loads(response.read())
            data = base64.b64decode(api['content'])
        target = output / 'oneDNN-3.1.1' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Preserve earlier differing notice: ' + str(target))
        if not target.exists():
            target.write_bytes(data)
        receipts.append(dict(source_url=url, path=target.relative_to(SOURCE).as_posix(), bytes=len(data), sha256=sha(target)))
    report = dict(downloads=receipts, runtime_install=False, global_changes=False,
                  libiomp5md_sha256=wheel_sha, official_wheel_dll_matches=True,
                  version_source='CTranslate2 4.8.3 python/tools/prepare_build_environment_windows.sh',
                  mkl_note='Upstream Windows build script selects oneAPI 2025.3; preserve the corresponding MKL wheel notices for the linked numerical code.')
    (output / 'provenance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(dict(ok=True, output=str(output), libiomp5md_sha256=wheel_sha, official_wheel_dll_matches=True)), flush=True)


if __name__ == '__main__':
    main()
