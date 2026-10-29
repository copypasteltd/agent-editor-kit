"""Capture bounded primary license/source declarations, without model execution."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
REVISION = '371bb1680f8c88d8c1083f6ffb6330d3d55bff76'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    if not args.run.isalnum():
        raise ValueError('Alphanumeric run identifier required')
    out = ROOT / f'docs/validation/evidence/acestep15-admission-20261029-r1/notices-{args.run}'
    out.mkdir()
    items = []
    unavailable = []

    def record(name, raw, **metadata):
        if not raw or len(raw) > 2 * 1024**2:
            raise ValueError('Notice exceeds its bounded budget')
        (out / name).write_bytes(raw)
        items.append(dict(file=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), **metadata))

    try:
        gh = shutil.which('gh')
        if gh:
            result = subprocess.run([gh, 'api', 'repos/ace-step/ACE-Step-1.5/license'],
                                    cwd=ROOT, capture_output=True, timeout=90,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if not result.returncode:
                value = json.loads(result.stdout)
                record('ace-step-source-LICENSE.txt', base64.b64decode(value['content']),
                       primary_url=value['html_url'], upstream_blob_sha=value['sha'], declared_spdx=value['license']['spdx_id'])
            else:
                unavailable.append(dict(source='optional upstream code license capture', reason='GitHub request failed'))
        else:
            unavailable.append(dict(source='optional upstream code license capture', reason='No preinstalled GitHub client on PATH; not installed'))
        request = urllib.request.Request(
            f'https://hf-mirror.com/Comfy-Org/ACE-Step-1.5/resolve/{REVISION}/README.md',
            headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read(2 * 1024**2 + 1)
        assert b'license: apache-2.0' in raw
        record('comfy-repack-README.md', raw, primary_url=f'https://huggingface.co/Comfy-Org/ACE-Step-1.5/blob/{REVISION}/README.md',
               transport='hf-mirror.com', revision=REVISION, declared_spdx='Apache-2.0')
        request = urllib.request.Request('https://www.apache.org/licenses/LICENSE-2.0.txt',
                                         headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read(2 * 1024**2 + 1)
        record('Apache-2.0.txt', raw, primary_url='https://www.apache.org/licenses/LICENSE-2.0.txt')
        runtime = Path('E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/ComfyUI')
        record('native-comfy-LICENSE.txt', (runtime / 'LICENSE').read_bytes(),
               local_source=str(runtime / 'LICENSE'), primary_url='https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE')
        report = dict(status='passed', notices=items, unavailable=unavailable, model_revision=REVISION,
                      generated_output_license_verified=False, external_native_runtime_bundled=False)
    except BaseException as exc:
        report = dict(status='failed', notices=items, unavailable=unavailable, error=repr(exc))
    (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
