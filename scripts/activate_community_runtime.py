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
    parser.add_argument('--semantic-config', type=Path, help='existing local semantic-model profile; preserve a prior profile when omitted')
    parser.add_argument('--verify-timeout-seconds', type=int, default=600,
                        help='per-model-pack integrity verification deadline, 1..3600 seconds (default600)')
    args = parser.parse_args()
    if not 1 <= args.verify_timeout_seconds <= 3600:
        parser.error('--verify-timeout-seconds must be within1..3600')
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
        try:
            result = subprocess.run([*prefix, 'model-pack', 'verify', '--id', ident, '--pack', str(pack)],
                                    capture_output=True, timeout=args.verify_timeout_seconds,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired as exc:
            (evidence / (ident + '.stdout.json')).write_bytes(exc.stdout or b'')
            (evidence / (ident + '.stderr.txt')).write_bytes(exc.stderr or b'')
            write_json(evidence / 'verification.json', dict(status='verification-timeout',
                pack_id=ident, verify_timeout_seconds=args.verify_timeout_seconds,
                verified_packs=verified, earlier_runtime_configuration_unchanged=True,
                model_checks_skipped=False, network=False, virtual_environment=False))
            raise ValueError('Model-pack verification timed out; earlier runtime configuration is unchanged. '
                             'Review local I/O and set --verify-timeout-seconds explicitly.') from exc
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
    semantic_config = args.semantic_config
    if semantic_config is None and runtime_path.exists():
        previous_runtime = json.loads(runtime_path.read_bytes())
        if previous_runtime.get('semantic_config'):
            semantic_config = Path(previous_runtime['semantic_config'])
    if semantic_config is not None:
        semantic_config = semantic_config.resolve(strict=True)
        profile = json.loads(semantic_config.read_bytes())
        if profile.get('format') != 'agent-local-semantic-runtime-v1':
            raise ValueError('Unsupported semantic runtime profile; previous configuration is preserved')
        for key in ('python_executable', 'model_path', 'evidence'):
            local = Path(profile[key])
            if not local.is_absolute() or str(local).startswith('\\\\') or not local.exists():
                raise ValueError('Semantic profile requires existing absolute local paths')
    for path in (runtime_path, community_path):
        if path.exists():
            (evidence / ('previous-' + path.name)).write_bytes(path.read_bytes())
    write_json(community_path, config)
    runtime = dict(release=manifest['release'], python=sys.executable, installed_directory=str(installed),
                   manifest_sha256=manifest['manifest_sha256'], launcher_sha256=sha(installed / 'run.py'),
                   native_only=True, community_config=str(community_path))
    if semantic_config is not None:
        runtime['semantic_config'] = str(semantic_config)
    write_json(runtime_path, runtime)
    report = dict(status='configured', release=runtime['release'], installed=str(installed),
                  community_config=str(community_path), verified_packs=verified, previous_config_preserved=True,
                  native_windows=True, network=False, virtual_environment=False, evidence=str(evidence))
    report['semantic_config'] = str(semantic_config) if semantic_config else None
    report['verify_timeout_seconds'] = args.verify_timeout_seconds
    write_json(evidence / 'verification.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
