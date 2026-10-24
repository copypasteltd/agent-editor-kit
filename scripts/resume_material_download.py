"""Resume a terminal failed development download into a new owned attempt.

The original partial remains unchanged. The server prefix is compared first;
Range/If-Match and ZIP CRC checks prevent joining unrelated object versions.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile

from acquire_material_community_sources import ROOT, OUTPUT, SOURCE, TLS, candidates, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', required=True)
    parser.add_argument('--attempt', type=int, required=True)
    args = parser.parse_args()
    row = next(row for row in candidates() if row['id'] == args.id)
    original = OUTPUT / (row['name'] + '.partial')
    original_size = original.stat().st_size
    output = OUTPUT / (Path(row['name']).stem + '-r' + str(args.attempt) + Path(row['name']).suffix)
    if output.exists() or output.with_name(output.name + '.partial').exists():
        raise ValueError('Earlier retry output is preserved')
    headers = {'User-Agent': 'agent-editor-kit-community-materials', 'Accept-Encoding': 'identity'}
    req = urllib.request.Request(row['url'], headers=headers, method='HEAD')
    with urllib.request.urlopen(req, timeout=40, context=TLS) as response:
        total = int(response.headers['Content-Length'])
        etag = response.headers['ETag']
        assert response.headers.get('Accept-Ranges') == 'bytes'
    assert 0 < original_size < total
    prefix_req = urllib.request.Request(row['url'], headers={**headers, 'Range': f'bytes=0-{original_size-1}', 'If-Match': etag})
    digest = hashlib.sha256()
    with urllib.request.urlopen(prefix_req, timeout=120, context=TLS) as response:
        assert response.status == 206
        assert response.headers['Content-Range'].startswith(f'bytes 0-{original_size-1}/')
        while block := response.read1(65536):
            digest.update(block)
    assert digest.hexdigest() == sha(original), 'Upstream prefix changed; original preserved'
    partial = output.with_name(output.name + '.partial')
    shutil.copyfile(original, partial)
    request = urllib.request.Request(row['url'], headers={**headers, 'Range': f'bytes={original_size}-', 'If-Match': etag})
    with urllib.request.urlopen(request, timeout=120, context=TLS) as response, partial.open('ab') as handle:
        assert response.status == 206
        assert response.headers['Content-Range'] == f'bytes {original_size}-{total-1}/{total}'
        next_progress = original_size + 8 * 1024 * 1024
        while block := response.read1(65536):
            handle.write(block)
            if handle.tell() >= next_progress:
                print(json.dumps({'id': row['id'], 'bytes': handle.tell(), 'total': total}), flush=True)
                next_progress += 8 * 1024 * 1024
    assert partial.stat().st_size == total
    with zipfile.ZipFile(partial) as archive:
        assert archive.testzip() is None
    partial.rename(output)
    result = {**row, 'status': 'downloaded', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'path': output.relative_to(ROOT).as_posix(), 'sha256': sha(output), 'bytes': total,
              'etag': etag, 'original_partial': original.relative_to(ROOT).as_posix(),
              'original_partial_sha256': sha(original), 'remote_prefix_verified': True,
              'zip_crc_verified': True, 'publisher_hash_verified': bool(row.get('sha256'))}
    receipt = SOURCE / (args.id + '-resume-r' + str(args.attempt) + '.json')
    with receipt.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
