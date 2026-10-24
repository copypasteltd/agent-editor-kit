"""Extract the locked optional gallery beside a fresh installed Agent kit and use its Skill."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (args.kit / 'docs').exists() or args.output.exists():
        raise ValueError('Existing gallery or check outputs are preserved')
    lock = json.loads((ROOT / 'docs/releases/v0.1.0-alpha.3/public/assets.lock.json').read_bytes())
    expected = next(row for row in lock['assets'] if row['name'].endswith('-gallery.zip'))
    assert args.archive.name == expected['name'] and sha(args.archive) == expected['sha256']
    with zipfile.ZipFile(args.archive) as zipped:
        for name in zipped.namelist():
            target = PurePosixPath(name)
            assert not target.is_absolute() and '..' not in target.parts and '\\' not in name and ':' not in name
            assert not (args.kit / name).exists()
        zipped.extractall(args.kit)
        members = len(zipped.namelist())
    gallery = args.kit / 'docs/assets/looks-n002-20261024-r1'
    manifest = json.loads((gallery / 'manifest.json').read_bytes())
    assert len(manifest['records']) == 500 and sha(gallery / 'source.png') == manifest['source']['sha256']
    for row in manifest['records']:
        assert sha(gallery / row['full']) == row['full_sha256']
        assert sha(gallery / row['thumbnail']) == row['thumbnail_sha256']
    args.output.mkdir(parents=True)
    helper = args.kit / 'skills/agent-ffmpeg-local-editor/scripts/look_gallery.py'
    calls = []
    for name, tail in [('search', ['--query', '黑白', '--limit', '6']),
                       ('board', ['--ids', 't3-fuji-superia-800', 'nt-bw-agfa-apx-100', 'fl-0000634-darkblue',
                                  '--output', str((args.output / 'client-board').resolve())])]:
        command = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(helper), *tail]
        result = subprocess.run(command, capture_output=True, timeout=90)
        (args.output / (name + '.stdout.json')).write_bytes(result.stdout)
        (args.output / (name + '.stderr.txt')).write_bytes(result.stderr)
        response = json.loads(result.stdout)
        assert result.returncode == 0 and response['ok']
        calls.append({'name': name, 'argv': command, 'exit_code': result.returncode, 'ok': response['ok']})
    report = {'status': 'passed', 'gallery_archive_sha256': expected['sha256'], 'extracted_members': members,
              'source_sha256_verified': True, 'full_previews_verified': 500, 'thumbnails_verified': 500,
              'helper_calls': calls, 'new_model_inferences': 0, 'new_look_renders': 0,
              'browser_invoked': False, 'virtualization_invoked': False, 'runtime_network_downloads': 0}
    (args.output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': 'passed', 'extracted_members': members, 'verified_previews': 500, 'helper_calls': 2}))


if __name__ == '__main__':
    main()
