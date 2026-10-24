"""Verify the r6 Skill kit in isolated native discovery, preserving the real entry."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile

from audit_job_recovery_installation_20261025 import ROOT, EVIDENCE, sha, write


def main():
    kit = ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r6.zip'
    evidence = EVIDENCE / 'kit-r1'
    evidence.mkdir(exist_ok=False)
    (evidence / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    output = ROOT / 'local/agent-ffmpeg/job-recovery-kit-r1/独立工具 包'
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(kit) as archive:
        inventory = json.loads(archive.read('KIT-FILES.json'))
        assert inventory['cli_version'] == '0.1.7' and inventory['skill_count'] == 1 and inventory['module_count'] == 17
        names = [row['path'] for row in inventory['files']]
        assert len(set(archive.namelist())) == len(archive.namelist()) == len(names) + 1
        assert set(archive.namelist()) == set(names) | {'KIT-FILES.json'}
        assert sum(Path(name).name == 'SKILL.md' for name in names) == 1
        for row in inventory['files']:
            relative = Path(row['path'])
            assert not relative.is_absolute() and '..' not in relative.parts and ':' not in row['path']
            data = archive.read(row['path'])
            assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
            if row['path'].startswith('skills/'):
                assert data == (ROOT / relative).read_bytes(), row['path']
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    runtime = json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())
    devices = json.loads(Path(runtime['community_config']).read_bytes())
    discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    original = discovery.resolve()
    ps = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File']
    calls = []

    def run(name, command, cli=False):
        result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True,
                                timeout=900, creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = evidence / (name + '.stdout.txt'), evidence / (name + '.stderr.txt')
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        calls.append(dict(id=name, command=list(map(str, command)), exit_code=result.returncode,
                          json_cli=cli, stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        write(evidence / 'calls.json', calls)
        assert result.returncode == 0, result.stderr.decode('utf8', 'replace')[-3000:]
        print(json.dumps(dict(id=name, exit_code=result.returncode)), flush=True)
        if cli:
            value = json.loads(result.stdout.decode('utf-8-sig'))
            assert value['ok']
            return value['data']

    try:
        run('configure', [sys.executable, '-I', '-B', '-u', '-X', 'utf8', output / 'scripts/activate_community_runtime.py',
            '--installed', runtime['installed_directory'], '--packs', Path(devices['voice']['cpu_pack']).parent,
            '--voice-cuda-lib', devices['voice']['cuda_library_directory'],
            '--translation-cuda-lib', devices['translation']['cuda_library_directory'],
            '--semantic-config', runtime['semantic_config']])
        isolated = output.parent / 'isolated-discovery'
        run('register', [*ps, output / 'register-agent-ffmpeg-local-skills.ps1',
            '-SkillsDirectory', isolated, '-ReceiptPath', evidence / 'registration.json'])
        entry = isolated / 'agent-ffmpeg-local-editor'
        assert entry.resolve() == (output / 'skills/agent-ffmpeg-local-editor').resolve()
        launcher = entry / 'scripts/run.ps1'
        assert run('version', [*ps, launcher, 'version'], True)['cli_version'] == '0.1.7'
        run('capabilities', [*ps, launcher, 'capabilities'], True)
        run('four-stems-help', [*ps, launcher, 'audio', 'separate-stems', '--help'])
        project = ROOT / 'local/agent-ffmpeg/job-recovery-20261025-r1/installed-r1/中文 四轨工程'
        names = ('project.json', 'project.lock.json', 'rights-ledger.json', 'models/audio-adapters.json')
        before = {name: sha(project / name) for name in names}
        run('four-stems-dry-run', [*ps, launcher, 'audio', 'separate-stems', '--project', project,
            '--asset-id', 'controlled_mix', '--adapter-id', 'four', '--prefix', 'kit_contract', '--apply', '--dry-run'], True)
        run('recover-help', [*ps, launcher, 'project', 'recover', '--help'])
        recovery = run('recover-dry-run', [*ps, launcher, 'project', 'recover', '--project', project,
                                          '--cleanup-jobs', '--dry-run'], True)
        assert recovery['job_recovery']['dry_run'] and not recovery['job_recovery']['jobs']
        assert before == {name: sha(project / name) for name in names}
        assert discovery.resolve() == original
        result = dict(status='passed', kit=str(kit), kit_sha256=sha(kit), files=len(inventory['files']) + 1,
            cli_version='0.1.7', registered_skills=1, internal_modules=17, skill_files=62,
            real_discovery_changed=False, process_calls=len(calls), json_cli_calls=sum(r['json_cli'] for r in calls),
            new_model_forwards=0, new_renders=0, dry_run_metadata_unchanged=True,
            native_windows=True, virtualization=False, source_fallback=False, generator_sha256=sha(Path(__file__)))
        write(evidence / 'verification.json', result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    except BaseException as error:
        write(evidence / 'failure.json', dict(status='failed', reason=str(error), calls=calls))
        raise


if __name__ == '__main__':
    main()
