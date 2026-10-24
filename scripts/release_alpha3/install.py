"""Install the pinned native alpha.3 runtime beside this downloaded Agent kit.

Requires existing Windows x64 CPython 3.13 and FFmpeg/ffprobe. Uses no network,
virtual environment, global package installation, or source-code fallback.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import struct
import subprocess
import sys
import zipfile

HOME = Path(__file__).resolve().parent
TAG = 'v0.1.0-alpha.3'
ARCHIVE_SHA = '1a967e4def2afc14e9f110c6cad90e172ff457a77ef405cb83932f1f1187b968'
MANIFEST_SHA = 'sha256:3bc0a74144953b97a769db01f3d2d863889da80f010d78ab7e4a2b4eedf1ceea'


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True, help='Downloaded native runtime ZIP')
    args = parser.parse_args()
    if (sys.platform != 'win32' or platform.python_implementation() != 'CPython'
            or sys.version_info[:2] != (3, 13) or struct.calcsize('P') != 8
            or sys.prefix != sys.base_prefix):
        raise ValueError('Use existing native Windows x64 CPython 3.13, outside a virtual environment')
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            raise ValueError(tool + ' must already be available on PATH')
    archive = args.archive.resolve(strict=True)
    if sha(archive) != ARCHIVE_SHA:
        raise ValueError('Runtime ZIP SHA-256 differs; existing files are preserved')
    inventory = json.loads((HOME / 'KIT-FILES.json').read_bytes())
    if inventory['release'] != TAG:
        raise ValueError('Wrong Agent kit version')
    for row in inventory['files']:
        target = (HOME / row['path']).resolve(strict=True)
        if not target.is_relative_to(HOME) or not target.is_file() or sha(target) != row['sha256']:
            raise ValueError('Agent kit file differs: ' + row['path'])
    release_home = HOME / 'local/agent-ffmpeg' / TAG
    config_path = HOME / 'local/agent-ffmpeg/runtime.json'
    if release_home.exists() or config_path.exists():
        raise ValueError('An existing installation is preserved; use its launcher or a new Agent kit directory')
    with zipfile.ZipFile(archive) as zipped:
        seen = set()
        expanded = 0
        for member in zipped.infolist():
            name = member.filename.rstrip('/')
            path = PurePosixPath(name)
            if (not name or path.is_absolute() or path.as_posix() != name or '\\' in name or ':' in name
                    or any(p in {'.', '..'} for p in path.parts) or name.casefold() in seen
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError('Invalid runtime archive member: ' + name)
            seen.add(name.casefold())
            expanded += member.file_size
        if expanded > 512 * 1024 ** 2:
            raise ValueError('Runtime archive exceeds its reviewed expansion budget')
        if 'sha256:' + hashlib.sha256(zipped.read('bundle/manifest.json')).hexdigest() != MANIFEST_SHA:
            raise ValueError('Embedded bundle manifest differs')
        release_home.mkdir(parents=True)
        unpacked = release_home / 'release'
        zipped.extractall(unpacked)
    installed = release_home / 'installed'
    temporary = release_home / 'temp'
    temporary.mkdir()
    env = dict(os.environ, TMP=str(temporary), TEMP=str(temporary), TMPDIR=str(temporary),
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    command = [sys.executable, '-I', '-B', '-X', 'utf8', str(unpacked / 'bundle/install.py'),
               '--target', str(installed), '--manifest-sha256', MANIFEST_SHA]
    result = subprocess.run(command, env=env, capture_output=True, timeout=300,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (release_home / 'install.stdout.json').write_bytes(result.stdout)
    (release_home / 'install.stderr.txt').write_bytes(result.stderr)
    if result.returncode or not json.loads(result.stdout).get('ok'):
        raise RuntimeError('Offline wheel installation failed; install logs are retained')
    version = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(installed / 'run.py'), 'version'],
                             env=env, capture_output=True, timeout=60,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (release_home / 'version.json').write_bytes(version.stdout)
    response = json.loads(version.stdout)
    if version.returncode or not response.get('ok') or response['data']['cli_version'] != '0.1.2':
        raise RuntimeError('Installed CLI version check failed; existing logs are retained')
    runtime = {'release': TAG, 'python': sys.executable, 'installed_directory': str(installed),
               'manifest_sha256': MANIFEST_SHA, 'launcher_sha256': sha(installed / 'run.py'),
               'zip_sha256': ARCHIVE_SHA, 'native_only': True}
    write_new(config_path, runtime)
    report = {'ok': True, 'release': TAG, 'installed_directory': str(installed),
              'runtime_config': str(config_path), 'runtime_archive_sha256': ARCHIVE_SHA,
              'network_downloads': 0, 'virtual_environments_created': 0,
              'next': 'Run register-agent-ffmpeg-local-skills.ps1; then run-example.py --output a-new-directory'}
    write_new(release_home / 'installation.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(json.dumps({'ok': False, 'status': 'failed-preserved', 'message': str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
