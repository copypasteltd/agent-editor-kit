"""Refresh the four built model pins after verifying their complete inventories."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve(strict=True)
    if not directory.is_relative_to(ROOT / 'local/agent-ffmpeg'):
        raise ValueError('Use explicitly built local packs in this workspace')
    catalog_path = ROOT / 'product/src/ai_ad_editor/material_data/model-packs.json'
    catalog = json.loads(catalog_path.read_bytes())
    for row in catalog['packs']:
        pack = directory / row['id']
        path = pack / 'manifest.json'
        manifest = json.loads(path.read_bytes())
        expected = {r['path'] for r in manifest['files']} | {'manifest.json'}
        actual = {p.relative_to(pack).as_posix() for p in pack.rglob('*') if p.is_file()}
        assert actual == expected and manifest['id'] == row['id']
        for record in manifest['files']:
            file = pack / record['path']
            assert file.stat().st_size == record['bytes'] and sha(file) == record['sha256'], record['path']
        row.update(manifest_sha256=sha(path), engine=manifest['engine'], files=len(manifest['files']),
                   uncompressed_bytes=sum(r['bytes'] for r in manifest['files']),
                   local_pack_path_hint=pack.relative_to(ROOT).as_posix())
        if 'gpu_runtime_terms' in manifest:
            row['gpu_runtime_terms'] = manifest['gpu_runtime_terms']
        if 'optional_dependency_notice' in manifest:
            row['optional_dependency_notice'] = manifest['optional_dependency_notice']
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(dict(ok=True, pins=[dict(id=r['id'], sha256=r['manifest_sha256'], files=r['files']) for r in catalog['packs']])))


if __name__ == '__main__':
    main()
