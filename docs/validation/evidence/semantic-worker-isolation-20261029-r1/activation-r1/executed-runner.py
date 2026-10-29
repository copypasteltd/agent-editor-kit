"""Activate verified CLI56 native delivery without replacing the four model packs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/semantic-worker-isolation-20261029-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--pin-run', default='r1')
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and args.pin_run.replace('-', '').isalnum()
    pin = load(BASE/('skill-pin-'+args.pin_run)/'verification.json')
    assert pin['status'] == 'pinned-not-activated' and pin['cli_version'] == '0.1.56'
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    assert sha(namespace) == pin['namespace_manifest_sha256']
    manifest = load(namespace)
    assert manifest['cli_version'] == '0.1.56' and len(manifest['files']) == 93
    for row in manifest['files']:
        assert sha(ROOT/row['path']) == row['sha256']
    for gate in pin['gates'].values():
        assert sha(ROOT/gate['path']) == gate['sha256']
    installation = load(BASE/'installation-candidate-r1/verification.json')
    installed = Path(installation['installed'])
    assert installation['cli_version'] == '0.1.56' and installation['status'] == 'installed-and-byte-verified'
    source = ROOT/'product/src/ai_ad_editor'
    assert {p.name: sha(p) for p in source.glob('*.py')} == {
        p.name: sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
    runtime_path = ROOT/'local/agent-ffmpeg/runtime.json'
    runtime = load(runtime_path)
    devices = load(Path(runtime['community_config']))
    packs = Path(devices['voice']['cpu_pack']).parent
    expected = ['kokoro-zh-en-int8', 'opus-zh-en-cpu-int8', 'kokoro-zh-en-cuda13', 'opus-zh-en-cuda12-int8']
    assert all((packs/name).is_dir() for name in expected)
    assert Path(devices['voice']['gpu_pack']) == packs/'kokoro-zh-en-cuda13'
    assert Path(devices['translation']['cpu_pack']) == packs/'opus-zh-en-cpu-int8'
    assert Path(devices['translation']['gpu_pack']) == packs/'opus-zh-en-cuda12-int8'
    out = BASE/('activation-'+args.run)
    out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    (out/'previous-runtime.json').write_bytes(runtime_path.read_bytes())
    (out/'previous-community-runtime.json').write_bytes(Path(runtime['community_config']).read_bytes())
    command = [sys.executable, '-I', '-B', '-u', '-X', 'utf8', ROOT/'scripts/activate_community_runtime.py',
               '--installed', installed, '--packs', packs,
               '--voice-cuda-lib', devices['voice']['cuda_library_directory'],
               '--translation-cuda-lib', devices['translation']['cuda_library_directory'],
               '--semantic-config', runtime['semantic_config'], '--verify-timeout-seconds', '600']
    result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, timeout=2700,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'activation.stdout').write_bytes(result.stdout)
    (out/'activation.stderr').write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
    activation = json.loads(result.stdout)
    assert activation['status'] == 'configured' and set(activation['verified_packs']) == set(expected)
    for path in Path(activation['evidence']).iterdir():
        if path.is_file():
            (out/path.name).write_bytes(path.read_bytes())
    command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
               str(ROOT/'register-agent-ffmpeg-local-skills.ps1'), '-ReceiptPath', str(out/'registration.json')]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'registration.stdout').write_bytes(result.stdout)
    (out/'registration.stderr').write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
    discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert discovery.resolve() == (ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    active = load(runtime_path)
    assert Path(active['installed_directory']).resolve() == installed.resolve()
    assert active['manifest_sha256'] == installation['manifest_sha256']
    assert sha(namespace) == pin['namespace_manifest_sha256']
    save(out/'activation-and-registration.json', dict(status='passed', cli_version='0.1.56',
        activation=activation, registration=load(out/'registration.json'), public_entries=1,
        modules=17, skill_files=93, source_fallback=False, verified_model_packs=4,
        actual_registered_GPU_case_accepted=False, formal_kit_accepted=False))
    print(json.dumps(dict(status='activated-and-registered', cli_version='0.1.56',
                         verified_model_packs=4, actual_registered_case_required=True)), flush=True)


if __name__ == '__main__':
    main()
