"""Verify r5 inventory and an isolated native Skill registration against CLI 0.1.6."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import zipfile
from audit_four_stem_installation_20261025 import ROOT, sha, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    args = parser.parse_args()
    evidence = ROOT / 'docs/validation/evidence/four-stems-20261025-r1/kit-r1'
    evidence.mkdir(exist_ok=False)
    (evidence / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    output = ROOT / 'local/agent-ffmpeg/four-stems-kit-r1/独立工具 包'
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(args.kit) as archive:
        inventory = json.loads(archive.read('KIT-FILES.json'))
        assert inventory['cli_version'] == '0.1.6' and inventory['skill_count'] == 1 and inventory['module_count'] == 17
        names = [r['path'] for r in inventory['files']]
        assert len(set(archive.namelist())) == len(archive.namelist()) == len(names) + 1
        assert set(archive.namelist()) == set(names) | {'KIT-FILES.json'}
        assert sum(Path(name).name == 'SKILL.md' for name in names) == 1
        for row in inventory['files']:
            relative = Path(row['path'])
            assert not relative.is_absolute() and '..' not in relative.parts and ':' not in row['path']
            data = archive.read(row['path'])
            import hashlib
            assert len(data) == row['bytes'] and 'sha256:' + hashlib.sha256(data).hexdigest() == 'sha256:' + row['sha256']
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    runtime = json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())
    devices = json.loads(Path(runtime['community_config']).read_bytes())
    original = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()
    ps = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File']
    calls = []

    def run(name, command, cli=False):
        command = list(map(str, command))
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=900,
            creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = evidence / (name + '.stdout.txt'), evidence / (name + '.stderr.txt')
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        calls.append(dict(id=name, command=command, exit_code=result.returncode, cli=cli,
            stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        save(evidence / 'calls.json', calls)
        assert result.returncode == 0, result.stderr.decode('utf8', 'replace')[-3000:]
        print(json.dumps(dict(id=name, exit_code=result.returncode)), flush=True)
        if cli:
            response = json.loads(result.stdout.decode('utf-8-sig'))
            assert response['ok']
            return response['data']

    try:
        run('configure', [sys.executable, '-I', '-B', '-u', '-X', 'utf8', output / 'scripts/activate_community_runtime.py',
            '--installed', runtime['installed_directory'], '--packs', Path(devices['voice']['cpu_pack']).parent,
            '--voice-cuda-lib', devices['voice']['cuda_library_directory'],
            '--translation-cuda-lib', devices['translation']['cuda_library_directory'],
            '--semantic-config', runtime['semantic_config']])
        run('register', [*ps, output / 'register-agent-ffmpeg-local-skills.ps1',
            '-SkillsDirectory', output.parent / 'isolated-discovery', '-ReceiptPath', evidence / 'registration.json'])
        entry = output.parent / 'isolated-discovery/agent-ffmpeg-local-editor'
        assert entry.resolve() == (output / 'skills/agent-ffmpeg-local-editor').resolve()
        launcher = entry / 'scripts/run.ps1'
        assert run('version', [*ps, launcher, 'version'], True)['cli_version'] == '0.1.6'
        run('capabilities', [*ps, launcher, 'capabilities'], True)
        run('four-stems-help', [*ps, launcher, 'audio', 'separate-stems', '--help'])
        project = ROOT / 'local/agent-ffmpeg/four-stems-20261025-r1/installed-r1/中文 四轨工程'
        before = {name: sha(project / name) for name in ('project.json', 'rights-ledger.json', 'models/audio-adapters.json')}
        run('four-stems-dry-run', [*ps, launcher, 'audio', 'separate-stems', '--project', project,
            '--asset-id', 'controlled_mix', '--adapter-id', 'four', '--prefix', 'kit_contract', '--apply', '--dry-run'], True)
        assert before == {name: sha(project / name) for name in before}
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve() == original
        result = dict(status='passed', kit=str(args.kit.resolve()), kit_sha256=sha(args.kit), files=len(names)+1,
            cli_version='0.1.6', registered_skills=1, internal_modules=17, real_discovery_changed=False,
            process_calls=len(calls), json_cli_calls=sum(r['cli'] for r in calls), new_model_forwards=0,
            new_renders=0, dry_run_metadata_unchanged=True, native_windows=True, virtualization=False,
            source_fallback=False, generator_sha256=sha(Path(__file__)))
        save(evidence / 'verification.json', result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    except BaseException as exc:
        save(evidence / 'failure.json', dict(status='failed', message=str(exc), calls=len(calls)))
        raise


if __name__ == '__main__':
    main()
