"""Publish a reviewed new alpha.4 release without overwriting public history.

Local validation is the default. --publish requires matching formal/portable/
actual-fault evidence and an already-pushed source commit. Credentials stay in
memory and are sent only to GitHub API/upload hosts with redirects forbidden.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

import delivery66_handoff as handoff

_git_path = os.environ.get('AEK_NATIVE_GIT') or shutil.which('git')
handoff.require(_git_path is not None and Path(_git_path).is_file(), 'A native Windows Git executable is required')
GIT = Path(_git_path).resolve()
GIT_ROOT = GIT.parent.parent if GIT.parent.name.casefold() in {'cmd', 'bin'} else GIT.parent
REPOSITORY = 'copypasteltd/agent-editor-kit'
REMOTE = 'git@github.com:' + REPOSITORY + '.git'


def git(*args, input=None, timeout=120):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    env['PATH'] = str(GIT_ROOT / 'cmd') + os.pathsep + env.get('PATH', '')
    result = subprocess.run([str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *args], cwd=handoff.ROOT, env=env,
        input=input, capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    handoff.require(result.returncode == 0, 'Git source verification failed')
    return result.stdout


def validate_files(directory):
    directory = handoff.local(directory)
    lock_path = directory / 'release-lock.json'
    lock = handoff.load(lock_path)
    handoff.require(lock.get('format') == 'agent-editor-reviewed-release-v1'
        and lock.get('repository') == REPOSITORY and lock.get('tag') == handoff.TAG
        and lock.get('cli_version') == handoff.VERSION and lock.get('runtime_release') == handoff.RELEASE
        and lock.get('public_model_media_included') is False, 'Wrong release scope')
    rows = lock.get('assets')
    handoff.require(isinstance(rows, list) and 6 <= len(rows) <= 16, 'Invalid attachment list')
    expected = set()
    for row in rows:
        name = row['name']
        handoff.require(len(handoff.member(name).parts) == 1 and len(name) <= 128
            and name not in expected and type(row['bytes']) is int and 0 < row['bytes'] < 2 * 1024**3
            and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'Invalid release attachment')
        expected.add(name)
        path = handoff.local(directory / name)
        handoff.require(path.is_file() and path.stat().st_size == row['bytes']
                        and handoff.sha(path) == row['sha256'], 'Release attachment changed: ' + name)
    handoff.require({path.name for path in directory.iterdir()} == expected | {'release-lock.json'},
                    'Release contains missing or unreviewed attachments')
    handoff.require({'RELEASE-NOTES.md', 'QUICKSTART.md', 'QUICKSTART.en.md',
                     'QUICKSTART.zh-TW.md', 'SHA256SUMS.txt'} <= expected, 'Three-language workflow is required')
    handoff.require(sum(name.endswith('.zip') for name in expected) == 2, 'Only application and one Skill ZIP may ship')
    expected_sums = ''.join(row['sha256'] + '  ' + row['name'] + '\n' for row in rows if row['name'] != 'SHA256SUMS.txt')
    handoff.require((directory / 'SHA256SUMS.txt').read_text(encoding='utf-8') == expected_sums, 'Checksum list differs')
    handoff.require(set(lock['gates']) == {'formal-entry', 'portable-kit', 'music-faults'}, 'Final delivery gates are missing')
    for role, row in lock['gates'].items():
        path = handoff.local(row['path'])
        handoff.require(handoff.sha(path) == row['sha256'], 'Delivery acceptance evidence changed')
        evidence = handoff.load(path)
        handoff.require(evidence.get('status') == 'passed' and evidence.get('cli_version') == handoff.VERSION,
                        'Final delivery acceptance is incomplete: ' + role)
    descriptor = handoff.local(lock['descriptor'])
    handoff.require(handoff.sha(descriptor) == lock['descriptor_sha256'], 'Reviewed descriptor changed')
    spec = handoff.load(descriptor)
    pins = spec['application_files']
    for role, row in lock['gates'].items():
        evidence = handoff.load(row['path'])
        handoff.require(evidence['application_files'] == pins, 'Final gate used another application')
    for row in spec['files']:
        handoff.require(handoff.sha(handoff.ROOT / row['path']) == row['sha256'], 'Current formal entry changed')
    config = handoff.load(handoff.ROOT / handoff.CONFIG)
    installed = handoff.local(config['installed_directory'])
    sys.path.insert(0, str(installed / 'site'))
    package = importlib.import_module('ai_ad_editor')
    handoff.require(Path(package.__file__).resolve() == installed / 'site/ai_ad_editor/__init__.py',
                    'Release validation must import its installed application')
    core = importlib.import_module('ai_ad_editor.delivery')
    skill_pins = {row['path']: row['sha256'] for row in spec['files'] if row['path'].startswith(handoff.SKILL)}
    for role, row in spec['gates'].items():
        core._gate(handoff.ROOT, role, row, handoff.VERSION, pins, skill_pins)
    for name, pin in lock['frozen_source'].items():
        handoff.require(handoff.sha(handoff.local(handoff.ROOT / name)) == pin, 'Frozen release source changed')
    return lock


def bind_commit(lock, commit):
    handoff.require(re.fullmatch('[0-9a-f]{40}', commit), 'Specify the reviewed full source commit')
    handoff.require(git('rev-parse', 'HEAD').decode().strip() == commit
        and git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
        and git('remote', 'get-url', '--push', 'origin').decode().strip() == REMOTE,
        'Release must use this repository main and its exact current commit')
    # Git attributes may normalize line endings. Compare Git's clean object IDs
    # while separately retaining the exact installed/frozen byte SHA256 above.
    names = sorted(lock['frozen_source'])
    committed = {}
    for start in range(0, len(names), 48):
        raw = git('ls-tree', '-r', '-z', commit, '--', *names[start:start + 48])
        for record in raw.split(b'\0'):
            if record:
                metadata, name = record.split(b'\t', 1)
                mode, kind, oid = metadata.split()
                handoff.require(mode == b'100644' and kind == b'blob', 'Release source is not a regular Git file')
                committed[name.decode('utf-8')] = oid.decode()
    handoff.require(set(committed) == set(names), 'Source commit omits frozen implementation files')
    handoff.require(all('\n' not in name and '\r' not in name and '"' not in name for name in names), 'Unsupported Git source path')
    clean_ids = git('hash-object', '--stdin-paths', input=('\n'.join(names) + '\n').encode('utf-8')).decode().splitlines()
    handoff.require(len(clean_ids) == len(names), 'Git source object count differs')
    for name, clean in zip(names, clean_ids):
        handoff.require(clean == committed[name], 'Source commit differs from the accepted implementation: ' + name)


def stored_github_token(raw):
    """Decode only GitHub token text, without logging a native secret blob."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 16384:
        return None
    for encoding in ('utf-8', 'utf-16-le'):
        try:
            value = raw.decode(encoding).strip('\x00\r\n ')
        except UnicodeError:
            continue
        if re.fullmatch(r'(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{10,512}', value):
            return value
    return None


def native_gh_credential():
    """Read the existing default gh entry on native Windows; never sign in."""
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes

    class NativeCredential(ctypes.Structure):
        _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD),
            ('TargetName', wintypes.LPWSTR), ('Comment', wintypes.LPWSTR),
            ('LastWritten', wintypes.FILETIME), ('CredentialBlobSize', wintypes.DWORD),
            ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)), ('Persist', wintypes.DWORD),
            ('AttributeCount', wintypes.DWORD), ('Attributes', ctypes.c_void_p),
            ('TargetAlias', wintypes.LPWSTR), ('UserName', wintypes.LPWSTR)]

    try:
        api = ctypes.WinDLL('Advapi32.dll', use_last_error=True)
        api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.POINTER(ctypes.POINTER(NativeCredential))]
        api.CredReadW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredFree.restype = None
        pointer = ctypes.POINTER(NativeCredential)()
        if not api.CredReadW('gh:github.com:', 1, 0, ctypes.byref(pointer)):
            return None
        try:
            size = pointer.contents.CredentialBlobSize
            if not 0 < size <= 16384 or not pointer.contents.CredentialBlob:
                return None
            return stored_github_token(ctypes.string_at(pointer.contents.CredentialBlob, size))
        finally:
            api.CredFree(pointer)
    except (AttributeError, OSError, ValueError):
        return None


def credential():
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token:
        return token
    # gh and Git Credential Manager can belong to different GitHub identities.
    # Prefer the existing native gh entry before the legacy default Git helper.
    token = native_gh_credential()
    if token:
        return token
    # Capture only inside this process; never print or persist credential output.
    try:
        raw = git('credential', 'fill', input=b'protocol=https\nhost=github.com\n\n', timeout=30)
        value = dict(line.split('=', 1) for line in raw.decode().splitlines() if '=' in line)
        if value.get('host', 'github.com') == 'github.com' and value.get('password'):
            return value['password']
    except (ValueError, subprocess.TimeoutExpired, UnicodeError):
        pass
    raise ValueError('No GitHub publishing credential is available; reviewed local attachments are preserved')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise ValueError('Authenticated GitHub requests must not redirect')


def publish(directory, lock, commit):
    handoff.require(git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit,
                    'Push the accepted source commit before publishing')
    token = credential()
    opener = urllib.request.build_opener(NoRedirect())
    base = 'https://api.github.com/repos/' + REPOSITORY
    def request(method, url, body=None, file=None, *, missing=False):
        parsed = urllib.parse.urlparse(url)
        handoff.require(parsed.scheme == 'https' and parsed.hostname in {'api.github.com', 'uploads.github.com'}
                        and not parsed.username and not parsed.password, 'Refusing credential forwarding')
        headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                   'User-Agent': 'agent-editor-kit-reviewed-delivery', 'X-GitHub-Api-Version': '2022-11-28'}
        if file is not None:
            headers.update({'Content-Type': 'application/octet-stream', 'Content-Length': str(file.stat().st_size)})
            with file.open('rb') as stream:
                req = urllib.request.Request(url, data=stream, headers=headers, method=method)
                with opener.open(req, timeout=600) as response:
                    raw = response.read(8 * 1024**2 + 1)
        else:
            if body is not None:
                headers['Content-Type'] = 'application/json'
            req = urllib.request.Request(url, data=None if body is None else handoff.encoded(body), headers=headers, method=method)
            try:
                with opener.open(req, timeout=60) as response:
                    raw = response.read(8 * 1024**2 + 1)
            except urllib.error.HTTPError as exc:
                if missing and exc.code == 404:
                    return None
                raise ValueError('GitHub API rejected the operation with HTTP' + str(exc.code)) from None
        handoff.require(len(raw) <= 8 * 1024**2, 'GitHub response exceeds budget')
        return json.loads(raw)
    tag = request('GET', base + '/git/ref/tags/' + handoff.TAG, missing=True)
    if tag is None:
        tag = request('POST', base + '/git/refs', dict(ref='refs/tags/' + handoff.TAG, sha=commit))
    target = tag['object']
    if target['type'] == 'tag':
        target = request('GET', base + '/git/tags/' + target['sha'])['object']
    handoff.require(target['type'] == 'commit' and target['sha'] == commit, 'Existing tag identifies other source; preserve it')
    marker = '<!-- agent-editor-kit-source:' + commit + ';lock:' + handoff.sha(directory / 'release-lock.json') + ' -->'
    release = request('GET', base + '/releases/tags/' + handoff.TAG, missing=True)
    if release is None:
        release = request('POST', base + '/releases', dict(tag_name=handoff.TAG, target_commitish=commit,
            name='agent editor kit ' + handoff.TAG + ' / CLI' + handoff.VERSION, draft=True, prerelease=True,
            make_latest='false', body=(directory / 'RELEASE-NOTES.md').read_text(encoding='utf-8') + '\n' + marker))
    handoff.require(marker in release.get('body', ''), 'Existing release belongs to other reviewed bytes; preserve it')
    expected = {row['name']: row for row in lock['assets']}
    existing = {item['name']: item for item in release['assets']}
    handoff.require(set(existing) <= set(expected), 'Existing release has unreviewed attachments; preserve it')
    for name, row in expected.items():
        item = existing.get(name)
        if item is None:
            handoff.require(release['draft'], 'Do not add attachments to an already published release')
            url = release['upload_url'].split('{', 1)[0] + '?' + urllib.parse.urlencode({'name': name})
            item = request('POST', url, file=directory / name)
        handoff.require(item['size'] == row['bytes'] and item.get('digest') == 'sha256:' + row['sha256'],
                        'Remote attachment digest differs; no attachment is overwritten')
    release = request('GET', base + '/releases/' + str(release['id']))
    handoff.require({item['name'] for item in release['assets']} == set(expected), 'Final attachment set differs')
    if release['draft']:
        release = request('PATCH', base + '/releases/' + str(release['id']), dict(draft=False, prerelease=True, make_latest='false'))
    return dict(status='published', cli_version=handoff.VERSION, source_commit=commit, tag=handoff.TAG,
        html_url=release['html_url'], published_at=release['published_at'], old_releases_unchanged=True,
        assets=[dict(name=item['name'], bytes=item['size'], sha256=item['digest'],
            download_url=item['browser_download_url']) for item in release['assets']])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', required=True, type=Path)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    directory = handoff.local(args.assets)
    lock = validate_files(directory)
    bind_commit(lock, args.source_commit)
    out = handoff.begin('publication', args.run)
    result = dict(status='validated-not-published', cli_version=handoff.VERSION,
                  source_commit=args.source_commit, assets=lock['assets'])
    try:
        if args.publish:
            result = publish(directory, lock, args.source_commit)
        handoff.save(out / 'verification.json', result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    except BaseException as exc:
        handoff.save(out / 'verification.json', dict(status='failed-preserved', error_type=type(exc).__name__,
            error=str(exc), source_commit=args.source_commit, reviewed_local_assets_preserved=True))
        raise


if __name__ == '__main__':
    main()
