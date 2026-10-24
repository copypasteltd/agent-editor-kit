"""Configure the pinned native local build and explicitly installed model packs.

Only local configuration is written. The registrar remains the separate final
step; no model downloads, global package changes or GPU process control occur.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.pending-' + str(os.getpid()))
    with temporary.open('x', encoding='utf8', newline='\n') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--packs', type=Path, required=True)
    parser.add_argument('--voice-cuda-lib', type=Path)
    parser.add_argument('--translation-cuda-lib', type=Path)
    args = parser.parse_args()
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 13) or sys.prefix != sys.base_prefix or platform.machine().lower() not in {'amd64', 'x86_64'}:
        raise ValueError('Use native Windows CPython 3.13 x64')
    installed, packs = args.installed.resolve(strict=True), args.packs.resolve(strict=True)
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    receipt = json.loads((installed / 'receipt.json').read_bytes())
    if receipt['manifest_sha256'] != manifest['manifest_sha256']:
        raise ValueError('Installed application does not match this reviewed Skill kit')
    for row in manifest['files']:
        path = ROOT / row['path']
        if not path.resolve().is_relative_to(ROOT / 'skills/agent-ffmpeg-local-editor') or sha(path) != row['sha256']:
            raise ValueError('Skill inventory changed: ' + row['path'])
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    evidence = ROOT / 'local/agent-ffmpeg/activations' / stamp
    evidence.mkdir(parents=True, exist_ok=False)
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py')]
    verified = []
    for ident in ('kokoro-zh-en-int8', 'opus-zh-en-cpu-int8', 'kokoro-zh-en-cuda13', 'opus-zh-en-cuda12-int8'):
        pack = packs / ident
        if not pack.is_dir() and ident in {'kokoro-zh-en-cuda13', 'opus-zh-en-cuda12-int8'}:
            continue
        result = subprocess.run([*prefix, 'model-pack', 'verify', '--id', ident, '--pack', str(pack)],
                                capture_output=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
        (evidence / (ident + '.stdout.json')).write_bytes(result.stdout)
        (evidence / (ident + '.stderr.txt')).write_bytes(result.stderr)
        response = json.loads(result.stdout)
        if result.returncode or not response['ok']:
            raise ValueError('Model verification failed; earlier runtime configuration is preserved')
        verified.append(ident)
    config = {}
    for task, cpu, gpu, library in [
        ('voice', 'kokoro-zh-en-int8', 'kokoro-zh-en-cuda13', args.voice_cuda_lib),
        ('translation', 'opus-zh-en-cpu-int8', 'opus-zh-en-cuda12-int8', args.translation_cuda_lib)]:
        config[task] = dict(cpu_pack=str(packs / cpu))
        if gpu in verified:
            config[task]['gpu_pack'] = str(packs / gpu)
        if library:
            library = library.resolve(strict=True)
            if not library.is_dir():
                raise ValueError('CUDA library argument must be a local directory')
            config[task]['cuda_library_directory'] = str(library)
    directory = ROOT / 'local/agent-ffmpeg'
    runtime_path, community_path = directory / 'runtime.json', directory / 'community-runtime.json'
    for path in (runtime_path, community_path):
        if path.exists():
            (evidence / ('previous-' + path.name)).write_bytes(path.read_bytes())
    write_json(community_path, config)
    runtime = dict(release=manifest['release'], python=sys.executable, installed_directory=str(installed),
                   manifest_sha256=manifest['manifest_sha256'], launcher_sha256=sha(installed / 'run.py'),
                   native_only=True, community_config=str(community_path))
    write_json(runtime_path, runtime)
    report = dict(status='configured', release=runtime['release'], installed=str(installed),
                  community_config=str(community_path), verified_packs=verified, previous_config_preserved=True,
                  native_windows=True, network=False, virtual_environment=False, evidence=str(evidence))
    write_json(evidence / 'verification.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
