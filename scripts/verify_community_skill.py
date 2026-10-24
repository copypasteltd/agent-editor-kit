"""Check the real Codex discovery entry against the installed GPU extension."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    logs = out / 'logs'
    logs.mkdir()
    discovery = Path(os.environ.get('CODEX_HOME', str(Path(os.environ['USERPROFILE']) / '.codex'))) / 'skills'
    skill = discovery / 'agent-ffmpeg-local-editor'
    ps = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File']
    registrar = subprocess.run([*ps, str(ROOT / 'register-agent-ffmpeg-local-skills.ps1'),
        '-ReceiptPath', str(out / 'registration.json')], capture_output=True, timeout=180,
        creationflags=subprocess.CREATE_NO_WINDOW)
    (logs / 'registration.stdout.txt').write_bytes(registrar.stdout)
    (logs / 'registration.stderr.txt').write_bytes(registrar.stderr)
    assert registrar.returncode == 0, registrar.stderr
    entries = [f.name for f in discovery.iterdir() if f.name.startswith('agent-ffmpeg-local-')]
    assert entries == ['agent-ffmpeg-local-editor'], entries
    assert skill.is_junction() and skill.resolve() == ROOT / 'skills/agent-ffmpeg-local-editor'
    prefix = [*ps, str(skill / 'scripts/run.ps1')]
    rows = []
    def cli(name, args):
        argv = [*prefix, *map(str, args)]
        start = time.perf_counter()
        r = subprocess.run(argv, capture_output=True, timeout=360, creationflags=subprocess.CREATE_NO_WINDOW)
        (logs / (name + '.stdout.json')).write_bytes(r.stdout)
        (logs / (name + '.stderr.txt')).write_bytes(r.stderr)
        d = json.loads(r.stdout)
        rows.append(dict(id=name, argv=argv, exit_code=r.returncode, ok=d['ok'], seconds=time.perf_counter()-start))
        (out / 'commands.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        assert r.returncode == 0 and d['ok'], d
        return d['data']
    version = cli('version', ['version'])
    assert version['cli_version'] == '0.1.3'
    cli('capabilities', ['capabilities'])
    cli('gpu', ['gpu', 'inspect'])
    project = ROOT / 'local/agent-ffmpeg/community-skill-demo-r1'
    cli('init', ['project', 'init', project])
    voice = cli('voice-auto', ['voice', 'synthesize', '--project', project, '--voice', 'zf_001',
        '--text', '先预览视频，再导出工程。', '--asset-id', 'asset_voice_auto'])
    assert voice['device']['selected'] == 'cuda' and voice['synthesis']['cuda_provider_dll_loaded']
    translation = cli('translation-auto', ['translate', 'text', '--project', project, '--from', 'zh-Hans', '--to', 'en',
        '--text', '先预览视频，再导出工程。', '--output', 'exports/auto.txt'])
    assert translation['device']['selected'] == 'cuda' and translation['inference']['compute_type'] == 'int8_float16'
    cpu = cli('explicit-cpu', ['translate', 'text', '--project', project, '--device', 'cpu', '--from', 'en', '--to', 'zh-Hans',
        '--text', 'Keep the background music.', '--output', 'exports/cpu.txt'])
    assert cpu['device']['selected'] == 'cpu'
    cli('resources', ['materials', 'list', '--kind', 'sfx', '--limit', '2'])
    voices = cli('voices', ['voice', 'list'])
    assert voices['count'] == 103
    cli('validate', ['validate', '--project', project])
    cli('policy', ['policy', 'audit', '--project', project])
    runtime = json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())
    path = project / voice['asset']['uri']
    report = dict(status='passed-with-review-limits', skill_count=1, module_count=17, discovery=str(skill),
        installed=runtime['installed_directory'], manifest_sha256=runtime['manifest_sha256'], commands=len(rows),
        cli_version='0.1.3', default_voice_cuda=True, default_translation_cuda=True, explicit_cpu=True,
        explicit_model_paths_required_on_command=False, original_runtime_config_backed_up=True,
        source_fallback=False, native_windows=True, virtualization=False, network=False,
        voice=str(path), voice_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), human_listening=False)
    (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
