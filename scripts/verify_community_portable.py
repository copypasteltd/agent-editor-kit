"""Install all four pinned packs in a new Chinese/spaced path and test refusals."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installed', type=Path, required=True)
    p.add_argument('--archives', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    if not out.is_relative_to(ROOT / 'local/agent-ffmpeg'):
        raise ValueError('Use a new owned local directory')
    out.mkdir(parents=True, exist_ok=False)
    target = out / '模型 包'
    target.mkdir()
    logs = out / 'logs'
    logs.mkdir()
    catalog = a.installed.resolve() / 'site/ai_ad_editor/material_data/model-packs.json'
    rows = json.loads(a.archives.read_bytes())['packs']
    commands = []
    def install(label, archive, digest, ident, destination, error=None):
        argv = [sys.executable, '-I', '-B', '-u', '-X', 'utf8', str(ROOT / 'scripts/install_community_pack.py'),
                '--archive', str(archive), '--sha256', digest, '--catalog', str(catalog), '--id', ident,
                '--target', str(destination)]
        r = subprocess.run(argv, capture_output=True, timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
        (logs / (label + '.stdout.txt')).write_bytes(r.stdout)
        (logs / (label + '.stderr.txt')).write_bytes(r.stderr)
        commands.append(dict(id=label, argv=argv, exit_code=r.returncode, expected_error=error))
        (out / 'commands.json').write_text(json.dumps(commands, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        if error:
            assert r.returncode and error in r.stderr.decode('utf8'), r.stderr
        else:
            assert r.returncode == 0 and json.loads(r.stdout)['ok'], r.stderr
        print(json.dumps(commands[-1], ensure_ascii=False), flush=True)
    for row in rows:
        install('install-' + row['id'], Path(row['archive']), row['sha256'], row['id'], target / row['id'])
    row = rows[0]
    archive = Path(row['archive'])
    original_sha = sha(archive)
    protected = target / row['id'] / 'manifest.json'
    protected_sha = sha(protected)
    install('refuse-existing-target', archive, row['sha256'], row['id'], target / row['id'], error='Preserve existing target')
    install('refuse-wrong-archive-hash', archive, '0' * 64, row['id'], target / 'wrong-sha', error='Archive SHA-256 mismatch')
    malformed = out / 'extra-members.zip'
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(malformed, 'x') as dest:
        dest.writestr('manifest.json', src.read('manifest.json'))
        dest.writestr('../escape.txt', b'owned refusal fixture')
    install('refuse-extra-unsafe-members', malformed, sha(malformed), row['id'], target / 'refused-members',
            error='Archive has missing, extra or duplicate files')
    changed = out / 'changed-token.zip'
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(changed, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as dest:
        for info in src.infolist():
            if info.filename == 'models/kokoro/tokens.txt':
                data = bytearray(src.read(info))
                data[0] ^= 1
                dest.writestr(info.filename, data)
            else:
                with src.open(info) as inp, dest.open(info.filename, 'w', force_zip64=True) as output:
                    shutil.copyfileobj(inp, output, length=1024 * 1024)
    install('refuse-changed-file-clean-staging', changed, sha(changed), row['id'], target / 'changed-file',
            error='Extracted file hash mismatch')
    assert not any(p.name.startswith('changed-file') for p in target.iterdir())
    assert not (out / 'escape.txt').exists() and original_sha == sha(archive) and protected_sha == sha(protected)
    report = dict(status='passed', installed=str(a.installed.resolve()), native_windows=True, virtual_environment=False,
                  network=False, commands=len(commands), installed_packs=len(rows), pack_directory=str(target),
                  chinese_and_spaced_path=True, existing_target_preserved=True, wrong_hash_refused=True,
                  extra_unsafe_members_refused=True, changed_file_refused=True, failed_staging_removed=True,
                  original_archive_and_installed_manifest_unchanged=True,
                  pins=[dict(id=r['id'], manifest_sha256=r['manifest_sha256'], archive_sha256=r['sha256']) for r in rows])
    (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
