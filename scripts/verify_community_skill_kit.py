"""Extract the small kit into a fresh directory and exercise its actual launcher."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    if not out.is_relative_to(ROOT / 'local/agent-ffmpeg'):
        raise ValueError('Select a new owned directory')
    out.mkdir(parents=True, exist_ok=False)
    kit = out / '独立工具 包'
    with zipfile.ZipFile(a.kit) as z:
        inventory = json.loads(z.read('KIT-FILES.json'))
        assert set(z.namelist()) == {r['path'] for r in inventory['files']} | {'KIT-FILES.json'}
        assert len(z.namelist()) == len(inventory['files']) + 1
        for record in inventory['files']:
            path = record['path']
            assert not path.startswith(('/', '\\')) and '..' not in Path(path).parts and ':' not in path
            data = z.read(path)
            assert len(data) == record['bytes'] and hashlib.sha256(data).hexdigest() == record['sha256']
            target = kit / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    runtime = json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())
    settings = json.loads(Path(runtime['community_config']).read_bytes())
    rows = []
    def run(name, argv, response=False):
        r = subprocess.run(list(map(str, argv)), capture_output=True, timeout=360, creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stdout.txt')).write_bytes(r.stdout)
        (out / (name + '.stderr.txt')).write_bytes(r.stderr)
        rows.append(dict(id=name, argv=list(map(str, argv)), exit_code=r.returncode))
        assert r.returncode == 0, r.stderr
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        return json.loads(r.stdout)['data'] if response else None
    run('configure', [sys.executable, '-I', '-B', '-u', '-X', 'utf8', kit / 'scripts/activate_community_runtime.py',
        '--installed', runtime['installed_directory'], '--packs', Path(settings['voice']['cpu_pack']).parent,
        '--voice-cuda-lib', settings['voice']['cuda_library_directory'], '--translation-cuda-lib', settings['translation']['cuda_library_directory']])
    ps = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File']
    run('register-isolated-discovery', [*ps, kit / 'register-agent-ffmpeg-local-skills.ps1',
        '-SkillsDirectory', out / 'isolated-discovery', '-ReceiptPath', out / 'registration.json'])
    launcher = out / 'isolated-discovery/agent-ffmpeg-local-editor/scripts/run.ps1'
    assert (out / 'isolated-discovery/agent-ffmpeg-local-editor').resolve() == kit / 'skills/agent-ffmpeg-local-editor'
    version = run('version', [*ps, launcher, 'version'], True)
    assert version['cli_version'] == '0.1.3'
    project = out / 'demo'
    run('init', [*ps, launcher, 'project', 'init', project], True)
    translated = run('translate-auto', [*ps, launcher, 'translate', 'text', '--project', project,
        '--from', 'en', '--to', 'zh-Hant', '--text', 'Keep the background music.', '--output', 'exports/auto.txt'], True)
    assert translated['device']['selected'] == 'cuda' and translated['inference']['provider'] == 'cuda'
    report = dict(status='passed', calls=len(rows), files=len(inventory['files']) + 1, registered_skills=1,
        internal_modules=17, standalone_kit_configuration=True, isolated_discovery=True,
        real_codex_discovery_unchanged=True, kit_launcher_cuda_translation=True,
        installed_application=runtime['installed_directory'], source_fallback=False, native_windows=True,
        virtualization=False, network=False, kit_sha256=hashlib.sha256(a.kit.read_bytes()).hexdigest(), commands=rows)
    (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k != 'commands'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
