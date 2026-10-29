"""Acquire pinned open ACE-Step 1.5 tensors on E:, without installing packages."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
REVISION = '371bb1680f8c88d8c1083f6ffb6330d3d55bff76'
REPOSITORY = 'Comfy-Org/ACE-Step-1.5'
FILES = {
    'diffusion_model.safetensors': ('split_files/diffusion_models/acestep_v1.5_turbo.safetensors', 4787825604, '3f6e0797fad420a39bd33979eb6e840e30989e34a3794e843d23b60ec6e422d7'),
    'text_encoder.safetensors': ('split_files/text_encoders/qwen_0.6b_ace15.safetensors', 1191588248, 'fd4590c82153b8ddb67e15a2e7aaa8afa8b83a858c8a9b82a4831063156aa7a7'),
    'language_model.safetensors': ('split_files/text_encoders/qwen_1.7b_ace15.safetensors', 3708523360, 'ed63e9247d1f55f3ace04fa11e95b085fc82d459c82c5626f0b2e37b91ebd710'),
    'vae.safetensors': ('split_files/vae/ace_1.5_vae.safetensors', 337431732, '6de92e3a862acd287e08b024ac90f0783a8635451b728721a33ff03565bcb2bb'),
}


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024**2), b''):
            result.update(chunk)
    return result.hexdigest()


def save(path, value):
    temp = path.with_suffix('.temporary')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--endpoint', choices=['https://huggingface.co', 'https://hf-mirror.com'], default='https://hf-mirror.com')
    args = parser.parse_args()
    if not args.run.isalnum():
        raise ValueError('Use an alphanumeric run ID')
    proof = ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1' / ('acquisition-' + args.run)
    proof.mkdir()
    model = ROOT / 'product/.runtime/models/acestep15-20261029'
    model.mkdir(parents=True, exist_ok=True)
    report = dict(status='running', repository=REPOSITORY, revision=REVISION, endpoint=args.endpoint,
                  primary_source='https://huggingface.co/' + REPOSITORY, files=[],
                  mirror_is_transport_only=args.endpoint != 'https://huggingface.co', package_installations=0)
    started = time.monotonic()
    try:
        for name, (relative, size, expected) in FILES.items():
            target = model / name
            source = f'https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{relative}'
            transport = source.replace('https://huggingface.co', args.endpoint, 1)
            if not target.is_file():
                partial = target.with_suffix('.safetensors.partial')
                offset = partial.stat().st_size if partial.exists() else 0
                if offset > size:
                    raise ValueError('Existing partial exceeds the published file size')
                if offset < size:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    if offset:
                        headers['Range'] = f'bytes={offset}-'
                    request = urllib.request.Request(transport, headers=headers)
                    with urllib.request.urlopen(request, timeout=60) as response:
                        if offset and (response.status != 206 or not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-')):
                            raise ValueError('The transport did not preserve the requested byte range')
                        with partial.open('ab' if offset else 'xb') as output:
                            count = offset
                            announced = count // (64 * 1024**2)
                            while block := response.read(4 * 1024**2):
                                count += len(block)
                                if count > size:
                                    raise ValueError('Download exceeds the published byte count')
                                output.write(block)
                                if count // (64 * 1024**2) != announced:
                                    announced = count // (64 * 1024**2)
                                    save(proof / 'progress.json', dict(status='downloading', file=name, bytes=count, expected_bytes=size))
                                    print(json.dumps(dict(file=name, bytes=count, expected_bytes=size)), flush=True)
                    if partial.stat().st_size != size:
                        raise ValueError('Incomplete download; preserve partial for explicit resumption')
                if sha(partial) != expected:
                    raise ValueError('Downloaded bytes differ from the published LFS SHA-256')
                partial.replace(target)
            if target.stat().st_size != size or sha(target) != expected:
                raise ValueError('Existing model differs from the published LFS SHA-256')
            item = dict(file=name, upstream_path=relative, bytes=size, sha256=expected, source=source, transport=transport)
            report['files'].append(item)
            save(proof / 'progress.json', report)
            print(json.dumps(dict(verified=name, bytes=size, sha256=expected)), flush=True)
        report.update(status='passed', complete_model_tensors_sha_verified=True, elapsed_seconds=time.monotonic() - started)
        save(model / 'MODEL_SOURCES.json', report)
        save(proof / 'verification.json', report)
        return 0
    except BaseException as exc:
        report.update(status='failed', error=repr(exc), elapsed_seconds=time.monotonic() - started)
        save(proof / 'verification.json', report)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
