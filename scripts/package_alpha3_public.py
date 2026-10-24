"""Reproduce the alpha.3 public downloads without changing the runtime archive.

All ZIP member timestamps/order/permissions are fixed. New ZIPs are stored rather
than deflated, avoiding host zlib differences for already compressed gallery media.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.1.0-alpha.3'
RELEASE = ROOT / 'docs/releases' / TAG
PREFIX = 'agent-editor-kit-' + TAG
GALLERY = ROOT / 'docs/assets/looks-n002-20261024-r1'


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def text_bytes(path):
    return Path(path).read_text('utf-8-sig').replace('\r\n', '\n').encode('utf-8')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def archive(path, rows):
    names = set()
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as zipped:
        for name, source in sorted(rows):
            if name in names or name.startswith('/') or '\\' in name or ':' in name or '..' in Path(name).parts:
                raise ValueError('Invalid duplicate/archive member: ' + name)
            names.add(name)
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            with zipped.open(info, 'w', force_zip64=True) as destination:
                if isinstance(source, bytes):
                    destination.write(source)
                else:
                    with Path(source).open('rb') as incoming:
                        shutil.copyfileobj(incoming, destination, length=1024 * 1024)


def kit(output):
    content = {}
    for skill in sorted((ROOT / 'skills').glob('agent-ffmpeg-local-*')):
        for path in sorted(skill.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.pyo'}:
                content[path.relative_to(ROOT).as_posix()] = text_bytes(path) if path.suffix in {'.md', '.py', '.ps1', '.json'} else path.read_bytes()
    for name in ('install.py', 'run-example.py'):
        content[name] = text_bytes(ROOT / 'scripts/release_alpha3' / name)
    content['register-agent-ffmpeg-local-skills.ps1'] = text_bytes(ROOT / 'register-agent-ffmpeg-local-skills.ps1')
    content['LICENSE'] = text_bytes(ROOT / 'LICENSE')
    for name in ('QUICKSTART.md', 'QUICKSTART.zh-TW.md', 'QUICKSTART.en.md', 'THIRD_PARTY.md'):
        content[name] = text_bytes(RELEASE / name)
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    manifest.update(status='packaged', project_directory=None, codex_skills_directory=None)
    manifest.pop('registered_at_utc', None)
    for row in manifest['skills']:
        row.update(canonical_directory=None, registration_directory=None, registration_verified=False,
                   skill_md_sha256=hashlib.sha256(content['skills/' + row['name'] + '/SKILL.md']).hexdigest())
    content['agent-ffmpeg-local-install-manifest.json'] = encoded(manifest)
    old_inputs = ROOT / 'docs/assets/release-v0.1.0-alpha.1-r2'
    for name in ('card-1.png', 'card-2.png', 'pulse.wav'):
        content['demo/input/' + name] = (old_inputs / 'input' / name).read_bytes()
    content['demo/input/LICENSE.txt'] = (old_inputs / 'LICENSE.txt').read_bytes()
    inventory = {'release': TAG, 'files': [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                                          for name, data in sorted(content.items())]}
    content['KIT-FILES.json'] = encoded(inventory)
    path = output / (PREFIX + '-agent-kit.zip')
    archive(path, list(content.items()))
    return path


def gallery(output):
    manifest = json.loads((GALLERY / 'manifest.json').read_bytes())
    if len(manifest['records']) != 500:
        raise ValueError('Expected the complete existing 500-sample gallery')
    rows = [(p.relative_to(ROOT).as_posix(), p) for p in GALLERY.rglob('*') if p.is_file()]
    # Guides reference the online manuals for optional files outside this gallery.
    for source in sorted((ROOT / 'docs/local').glob('FILTER_GALLERY*.md')):
        text = source.read_text('utf-8')
        def externalize(match):
            target = match.group(2)
            if re.match(r'^[a-z]+:', target) or target.startswith('#'):
                return match.group()
            plain, marker, anchor = target.partition('#')
            resolved = (source.parent / plain).resolve()
            if resolved.is_relative_to(GALLERY) or resolved.name.startswith('FILTER_GALLERY'):
                return match.group()
            if not resolved.is_relative_to(ROOT):
                raise ValueError('Guide link outside repository')
            url = 'https://github.com/copypasteltd/agent-editor-kit/blob/' + TAG + '/' + resolved.relative_to(ROOT).as_posix()
            return match.group(1) + url + (marker + anchor if marker else '') + ')'
        text = re.sub(r'(!?\[[^\]]*\]\()([^\n)]+)\)', externalize, text)
        rows.append((source.relative_to(ROOT).as_posix(), text.replace('\r\n', '\n').encode('utf-8')))
    path = output / (PREFIX + '-gallery.zip')
    archive(path, rows)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    parser.add_argument('--kit-only', action='store_true', help='Prepare the small kit for native installation checks')
    parser.add_argument('--write-lock', type=Path)
    parser.add_argument('--check-lock', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Existing package output is preserved')
    output.mkdir(parents=True)
    files = [kit(output)]
    if args.kit_only:
        print(json.dumps({'status': 'prepared-kit-only', 'files': [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in files]}))
        return
    from assemble_look500_release import assemble
    runtime = output / (PREFIX + '-cp313-win_amd64.zip')
    assemble(RELEASE / 'artifacts', runtime)
    files += [runtime, gallery(output)]
    for name in ('QUICKSTART.md', 'QUICKSTART.zh-TW.md', 'QUICKSTART.en.md', 'RELEASE-NOTES.md', 'THIRD_PARTY.md'):
        path = output / name
        path.write_bytes(text_bytes(RELEASE / name))
        files.append(path)
    original = json.loads((RELEASE / 'artifacts/version.json').read_bytes())
    description = {'release': TAG, 'stage': 'alpha-prerelease', 'repository': 'copypasteltd/agent-editor-kit',
                   'source_ref': 'refs/tags/' + TAG, 'cli_version': '0.1.2', 'look_catalog_version': '2.0.0',
                   'look_count': 500, 'skill_count': 17, 'target': 'cp313-win_amd64',
                   'manifest_sha256': original['manifest_sha256'], 'runtime_archive_unchanged': True,
                   'python_included': False, 'ffmpeg_included': False, 'models_included': False,
                   'gui_required': False, 'runtime_network_downloads': False,
                   'full_capcut_parity_accepted': False,
                   'assets': [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(files)]}
    meta = output / 'release.json'
    meta.write_bytes(encoded(description))
    files.append(meta)
    checksums = output / 'SHA256SUMS.txt'
    checksums.write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in sorted(files)), encoding='ascii', newline='\n')
    files.append(checksums)
    lock = {'release': TAG, 'assets': [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(files)]}
    if args.check_lock and json.loads(args.check_lock.read_bytes()) != lock:
        raise ValueError('Reproduced public assets differ from the reviewed lock')
    if args.write_lock:
        args.write_lock.parent.mkdir(parents=True, exist_ok=True)
        with args.write_lock.open('xb') as handle:
            handle.write(encoded(lock))
    print(json.dumps({'status': 'prepared-and-lock-checked' if args.check_lock else 'prepared',
                      'output': str(output), 'assets': lock['assets']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
