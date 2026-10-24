"""Publish only reviewed alpha.3 downloads to the configured GitHub repository.

Run inside native GitHub Actions with its repository-scoped GITHUB_TOKEN. Never
replace an existing published asset, release tag, or attachment with other bytes.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO = 'copypasteltd/agent-editor-kit'
TAG = 'v0.1.0-alpha.3'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    lock = json.loads(args.lock.read_bytes())
    if lock['release'] != TAG or not re.fullmatch('[0-9a-f]{40}', args.commit):
        raise ValueError('Exact reviewed release and commit required')
    if {p.name for p in args.assets.iterdir()} != {row['name'] for row in lock['assets']}:
        raise ValueError('Public asset set differs from the reviewed lock')
    for row in lock['assets']:
        path = args.assets / row['name']
        if path.name != row['name'] or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('Public asset bytes differ: ' + row['name'])
    with zipfile.ZipFile(args.assets / ('agent-editor-kit-' + TAG + '-cp313-win_amd64.zip')) as zipped:
        manifest = json.loads(zipped.read('bundle/manifest.json'))
        version = json.loads(zipped.read('version.json'))
        if version['release'] != TAG or len(manifest['wheels']) != 8:
            raise ValueError('Wrong runtime wheel profile')
        if 'sha256:' + hashlib.sha256(zipped.read('bundle/manifest.json')).hexdigest() != version['manifest_sha256']:
            raise ValueError('Runtime manifest differs')
        for row in manifest['files']:
            data = zipped.read('bundle/' + row['path'])
            if len(data) != row['bytes'] or 'sha256:' + hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('Embedded runtime input differs: ' + row['path'])
    if not args.publish:
        print(json.dumps({'status': 'validated', 'tag': TAG, 'commit': args.commit, 'assets': lock['assets']}))
        return
    token = os.environ.get('GITHUB_TOKEN')
    if not token or os.environ.get('GITHUB_REPOSITORY') != REPO:
        raise ValueError('Repository-scoped GitHub Actions token required for the exact target repository')
    base = 'https://api.github.com/repos/' + REPO

    def request(method, url, body=None, file=None):
        if urllib.parse.urlparse(url).hostname not in {'api.github.com', 'uploads.github.com'}:
            raise ValueError('Refusing credential forwarding outside GitHub API/upload hosts')
        headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                   'User-Agent': 'agent-editor-kit-alpha3-publisher', 'X-GitHub-Api-Version': '2022-11-28'}
        if file is not None:
            headers.update({'Content-Type': 'application/octet-stream', 'Content-Length': str(file.stat().st_size)})
            with file.open('rb') as handle:
                req = urllib.request.Request(url, data=handle, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=180) as response:
                    return json.load(response)
        data = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(body).encode('utf-8')
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=60) as response:
            return json.load(response)

    tag = request('GET', base + '/git/ref/tags/' + TAG)
    target = tag['object']
    if target['type'] == 'tag':
        target = request('GET', target['url'])['object']
    if target['type'] != 'commit' or target['sha'] != args.commit:
        raise ValueError('Remote tag does not identify the checked-out source commit')
    releases = request('GET', base + '/releases?per_page=100')
    release = next((item for item in releases if item['tag_name'] == TAG), None)
    marker = '<!-- agent-editor-kit-source:' + args.commit + ' -->'
    if release is None:
        notes = (args.assets / 'RELEASE-NOTES.md').read_text('utf-8')
        release = request('POST', base + '/releases', {'tag_name': TAG, 'target_commitish': args.commit,
            'name': 'agent editor kit ' + TAG + ' — Agent CLI + 500 looks', 'draft': True,
            'prerelease': True, 'make_latest': 'false', 'body': notes + '\n\nSource commit: `' + args.commit + '`\n' + marker})
    elif marker not in release.get('body', ''):
        raise ValueError('An existing release from another source is preserved')
    existing = {item['name']: item for item in release['assets']}
    for row in lock['assets']:
        if row['name'] in existing:
            item = existing[row['name']]
            if item['size'] != row['bytes'] or item.get('digest') != 'sha256:' + row['sha256']:
                raise ValueError('Existing attachment differs; preserving it: ' + row['name'])
            continue
        if not release['draft']:
            raise ValueError('Published release is incomplete; refusing to mutate it')
        print(json.dumps({'status': 'uploading', 'name': row['name'], 'bytes': row['bytes']}), flush=True)
        upload = release['upload_url'].split('{', 1)[0] + '?' + urllib.parse.urlencode({'name': row['name']})
        item = request('POST', upload, file=args.assets / row['name'])
        if item['size'] != row['bytes'] or item.get('digest') != 'sha256:' + row['sha256']:
            raise ValueError('Uploaded attachment differs: ' + row['name'])
    release = request('GET', base + '/releases/' + str(release['id']))
    if {item['name'] for item in release['assets']} != {row['name'] for row in lock['assets']}:
        raise ValueError('Final attachment set differs')
    if release['draft']:
        release = request('PATCH', base + '/releases/' + str(release['id']),
                          {'draft': False, 'prerelease': True, 'make_latest': 'false'})
    print(json.dumps({'status': 'published', 'release': TAG, 'source_commit': args.commit,
                      'html_url': release['html_url'], 'published_at': release['published_at'],
                      'prerelease': release['prerelease'], 'assets': [
                          {'name': a['name'], 'bytes': a['size'], 'sha256': a.get('digest'),
                           'download_url': a['browser_download_url']} for a in release['assets']]}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as exc:
        try:
            message = json.load(exc).get('message', 'GitHub API rejected the request')
        except Exception:
            message = 'GitHub API rejected the request'
        print(json.dumps({'status': 'failed-preserved', 'http_status': exc.code, 'message': message}), flush=True)
        raise SystemExit(1)
