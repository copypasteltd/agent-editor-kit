"""Explicit development-time download of pinned upstream native GPU sources.

Normal editing/inference never calls this script. All bytes stay on E:.
"""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import tarfile
import time
import urllib.request
from acquire_material_community_sources import TLS

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'product/.runtime/materials-20261024'


def acquire(item):
    archive = WORK / 'downloads' / item['name']
    if not archive.exists():
        part = archive.with_name(archive.name + '.part')
        start = part.stat().st_size if part.exists() else 0
        url = item['url'] + '?download=' + str(int(time.time())) if item['name'].startswith('sherpa-onnx-') else item['browser_download_url'] + '?download=1'
        request = urllib.request.Request(url, headers={'User-Agent': 'agent-editor-kit-native-gpu', 'Accept': 'application/octet-stream',
                                         **({'Range': 'bytes=' + str(start) + '-'} if start else {})})
        with urllib.request.urlopen(request, timeout=90, context=TLS) as response:
            if start and response.status != 206:
                raise ValueError('Resume refused; partial file preserved')
            with part.open('ab' if start else 'xb') as handle:
                total, reported = start, start
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
                    total += len(chunk)
                    if total - reported >= 64 * 1024 * 1024:
                        print(json.dumps(dict(name=item['name'], downloaded=total, expected=item['size'])), flush=True)
                        reported = total
        assert part.stat().st_size == item['size']
        with part.open('rb') as handle:
            assert 'sha256:' + hashlib.file_digest(handle, 'sha256').hexdigest() == item['digest']
        part.rename(archive)
    with archive.open('rb') as handle:
        assert 'sha256:' + hashlib.file_digest(handle, 'sha256').hexdigest() == item['digest']
    destination = WORK / 'gpu-sources-r1' / item['name'].removesuffix('.tar.bz2')
    if destination.exists():
        print(json.dumps(dict(status='verified-archive-existing-extraction-preserved', name=item['name'])), flush=True)
        return
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, 'r:bz2') as tar:
        tar.extractall(destination, filter='data')
    print(json.dumps(dict(status='downloaded-and-extracted', name=item['name'], sha256=item['digest'], path=str(destination))), flush=True)


def main():
    research = ROOT / 'sources/materials-20261024/research'
    binaries = json.loads((research / 'sherpa-gpu-v2.json').read_bytes())['assets']
    models = json.loads((research / 'kokoro-tts-release.json').read_bytes())['assets']
    selected = [next(a for a in binaries if a['name'] == 'sherpa-onnx-v2.0.0-cuda-13.x-cudnn-9.x-onnxruntime1.28.2-win-x64-cuda.tar.bz2'),
                next(a for a in models if a['name'] == 'kokoro-multi-lang-v1_1.tar.bz2')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for task in [pool.submit(acquire, item) for item in selected]:
            task.result()


if __name__ == '__main__':
    main()
