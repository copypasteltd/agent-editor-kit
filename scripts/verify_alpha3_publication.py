"""Read the public alpha.3 release and stream-hash every own generated attachment."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPO = 'copypasteltd/agent-editor-kit'
TAG = 'v0.1.0-alpha.3'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Existing publication receipt is preserved')
    lock = json.loads((ROOT / 'docs/releases' / TAG / 'public/assets.lock.json').read_bytes())
    expected = {row['name']: row for row in lock['assets']}
    base = 'https://api.github.com/repos/' + REPO

    def request(url):
        return urllib.request.Request(url, headers={'User-Agent': 'agent-editor-kit-alpha3-verifier',
                                                    'Accept': 'application/vnd.github+json', 'Cache-Control': 'no-cache'})

    def get(url):
        with urllib.request.urlopen(request(url), timeout=60) as response:
            return json.load(response)

    release = get(base + '/releases/tags/' + TAG)
    if release['draft'] or not release['prerelease'] or release['tag_name'] != TAG:
        raise ValueError('Unexpected release stage')
    if set(expected) != {row['name'] for row in release['assets']}:
        raise ValueError('Public attachment names differ')
    tag = get(base + '/git/ref/tags/' + TAG)['object']
    if tag['type'] == 'tag':
        tag = get(tag['url'])['object']
    if tag['sha'] != args.commit:
        raise ValueError('Remote tag commit differs')
    runs = get(base + '/actions/runs?per_page=20')['workflow_runs']
    run = next(r for r in runs if r['name'] == 'Publish agent editor kit alpha.3' and r['head_sha'] == args.commit)
    if run['conclusion'] != 'success':
        raise ValueError('Publication workflow has not completed successfully')
    verified = []
    for asset in sorted(release['assets'], key=lambda row: row['name']):
        row = expected[asset['name']]
        if asset['size'] != row['bytes'] or asset.get('digest') != 'sha256:' + row['sha256']:
            raise ValueError('GitHub attachment metadata differs: ' + asset['name'])
        digest = hashlib.sha256()
        size = 0
        next_progress = 64 * 1024 * 1024
        # Only this project's generated release archives/docs, without credentials.
        download = urllib.request.Request(asset['browser_download_url'], headers={'User-Agent': 'agent-editor-kit-alpha3-verifier', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(download, timeout=120) as response:
            while block := response.read(1024 * 1024):
                size += len(block)
                digest.update(block)
                if size >= next_progress:
                    print(json.dumps({'status': 'downloading-for-verification', 'name': row['name'],
                                      'bytes_read': size, 'total_bytes': row['bytes']}), flush=True)
                    next_progress += 64 * 1024 * 1024
        if size != row['bytes'] or digest.hexdigest() != row['sha256']:
            raise ValueError('Downloaded attachment differs: ' + asset['name'])
        verified.append({'name': row['name'], 'bytes': size, 'sha256': 'sha256:' + digest.hexdigest(),
                         'download_verified': True, 'download_url': asset['browser_download_url']})
        print(json.dumps({'status': 'download-verified', 'name': row['name'], 'bytes': size}), flush=True)
    result = {'status': 'published-and-download-verified', 'release': TAG,
              'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'html_url': release['html_url'],
              'published_at': release['published_at'], 'release_commit': args.commit,
              'draft': False, 'prerelease': True, 'workflow_url': run['html_url'],
              'workflow_conclusion': run['conclusion'], 'assets': verified,
              'runtime_archive_unchanged': True, 'full_capcut_parity': False,
              'product_runtime_network': False, 'publication_verification_network': True,
              'new_model_inferences': 0, 'browser_invoked': False, 'virtualization_invoked': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': result['status'], 'url': result['html_url'], 'assets': len(verified)}), flush=True)


if __name__ == '__main__':
    main()
