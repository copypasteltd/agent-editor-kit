"""Acquire reviewed upstream material candidates on E:; runtime never calls this.

This development tool preserves original archives and records every downloaded
byte hash. Wheel and sherpa assets additionally match publisher-provided hashes.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import ssl
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'sources/materials-20261024'
OUTPUT = ROOT / 'product/.runtime/materials-20261024/downloads'
TLS = ssl.create_default_context()
try:
    import certifi
    TLS.load_verify_locations(cafile=certifi.where())
except ImportError:
    pass


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def candidates():
    rows = []
    for slug in ('music-jingles', 'interface-sounds', 'impact-sounds'):
        page = SOURCE / 'research' / ('kenney-' + slug + '.html')
        links = re.findall(r'href=[\"\']([^\"\']+)[\"\']', page.read_text('utf-8'))
        url = next(link for link in links if link.startswith('https://kenney.nl/media/') and link.endswith('.zip'))
        rows.append({'id': 'kenney-' + slug, 'name': url.rsplit('/', 1)[1], 'url': url,
                     'source': 'https://kenney.nl/assets/' + slug, 'license': 'CC0-1.0'})
    music = [
        ('oga-action', 'oga-action.zip', 'https://opengameart.org/sites/default/files/5%20Action%20Chiptunes%20By%20Juhani%20Junkala.zip', '5-chiptunes-action', 'CC0-1.0'),
        ('oga-gt-rpg', 'oga-gt-rpg.zip', 'https://opengameart.org/sites/default/files/gt-rpg-sountrack_2.zip', 'gt-rpg-soundtrack', 'CC-BY-4.0'),
        ('oga-searching', 'Searching.ogg', 'https://opengameart.org/sites/default/files/Searching.ogg', 'searching', 'CC0-1.0'),
        ('oga-mindstream', 'DST-MindStream.mp3', 'https://opengameart.org/sites/default/files/DST-MindStream.mp3', 'mindstream', 'CC0-1.0'),
    ]
    rows.extend({'id': ident, 'name': name, 'url': url, 'source': 'https://opengameart.org/content/' + slug,
                 'license': license} for ident, name, url, slug, license in music)
    releases = json.loads((SOURCE / 'research/sherpa-tts-assets.json').read_bytes())
    model = next(row for row in releases['assets'] if row['name'] == 'kokoro-int8-multi-lang-v1_1.tar.bz2')
    rows.append({'id': 'kokoro-zh-en-int8', 'name': model['name'], 'url': model['browser_download_url'],
                 'sha256': model['digest'].removeprefix('sha256:'), 'license': 'Apache-2.0',
                 'source': 'https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh'})
    for pair, language_pair, license in [('zh-en', 'zho-eng', 'CC-BY-4.0'), ('en-zh', 'eng-zho', 'CC-BY-4.0')]:
        rows.append({'id': 'opus-' + pair, 'name': 'opus-' + pair + '-20200717.zip',
                     'url': 'https://object.pouta.csc.fi/Tatoeba-MT-models/' + language_pair + '/opus-2020-07-17.zip',
                     'source': 'https://huggingface.co/Helsinki-NLP/opus-mt-' + pair, 'license': license})
    for package in ('sherpa-onnx', 'sherpa-onnx-core', 'ctranslate2', 'sentencepiece', 'pyyaml'):
        data = json.loads((SOURCE / 'research' / (package + '.json')).read_bytes())
        wheel = next(row for row in data['urls'] if row['filename'].endswith('cp313-cp313-win_amd64.whl')
                     or (package == 'sherpa-onnx-core' and row['filename'].endswith('py3-none-win_amd64.whl')))
        rows.append({'id': package, 'name': wheel['filename'], 'url': wheel['url'],
                     'sha256': wheel['digests']['sha256'], 'source': 'https://pypi.org/project/' + package + '/' + data['info']['version'] + '/',
                     'license': 'see-wheel-notices'})
    return rows


def acquire(row):
    path = OUTPUT / row['name']
    partial = path.with_name(path.name + '.partial')
    if not path.exists():
        if partial.exists():
            raise ValueError('Earlier incomplete download is preserved: ' + str(partial))
        request = urllib.request.Request(row['url'], headers={'User-Agent': 'agent-editor-kit-community-materials'})
        with urllib.request.urlopen(request, timeout=60, context=TLS) as response, partial.open('xb') as handle:
            while block := response.read(1024 * 1024):
                handle.write(block)
        partial.rename(path)
    digest = sha(path)
    if row.get('sha256') and row['sha256'] != digest:
        raise ValueError('Upstream digest mismatch: ' + row['name'])
    return {**row, 'bytes': path.stat().st_size, 'sha256': digest,
            'publisher_hash_verified': bool(row.get('sha256'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ids', nargs='*', help='Limit to listed candidate IDs')
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = [row for row in candidates() if not args.ids or row['id'] in args.ids]
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(acquire, row): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                result = future.result()
                results.append({'status': 'downloaded', **result})
                print(json.dumps({'status': 'downloaded', 'id': row['id'], 'bytes': result['bytes']}), flush=True)
            except Exception as exc:
                results.append({'status': 'failed-preserved', **row, 'error': str(exc)})
                print(json.dumps({'status': 'failed-preserved', 'id': row['id'], 'error': str(exc)}), flush=True)
    receipt = SOURCE / ('acquisition-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json')
    receipt.write_text(json.dumps({'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                                   'development_network_only': True, 'results': sorted(results, key=lambda row: row['id'])},
                                  ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    if any(row['status'] != 'downloaded' for row in results):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
