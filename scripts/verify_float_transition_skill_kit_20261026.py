"""Verify the single-entry r22 kit without changing actual Codex discovery."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/float-transition-20261026-r1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*', args.run)
    OUT = BASE / ('kit-' + args.run)
    OUT.mkdir(exist_ok=False)
    def save(name, value):
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (OUT / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    kit = ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r22.zip'
    home = ROOT / 'local/agent-ffmpeg' / ('float-transition-kit-' + args.run) / '独立工具 包'
    home.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(kit) as archive:
        inventory = json.loads(archive.read('KIT-FILES.json'))
        assert inventory['cli_version'] == '0.1.21'
        assert inventory['skill_count'] == 1 and inventory['module_count'] == 17
        names = [row['path'] for row in inventory['files']]
        assert set(archive.namelist()) == set(names) | {'KIT-FILES.json'}
        assert len(archive.namelist()) == len(set(archive.namelist())) == len(names) + 1
        assert sum(Path(name).name == 'SKILL.md' for name in names) == 1
        for row in inventory['files']:
            relative = Path(row['path'])
            assert not relative.is_absolute() and '..' not in relative.parts and ':' not in row['path']
            data = archive.read(row['path'])
            assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
            if row['path'].startswith('skills/'):
                assert data == (ROOT / relative).read_bytes()
            target = home / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    runtime = json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())
    devices = json.loads(Path(runtime['community_config']).read_bytes())
    actual = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    original_target = actual.resolve()
    ps = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File']
    calls = []
    def run(name, command, cli=False):
        command = list(map(str, command))
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=900, creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = OUT / (name + '.stdout.txt'), OUT / (name + '.stderr.txt')
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        calls.append(dict(id=name, argv=command, exit_code=result.returncode, json_cli=cli,
                          stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        save('calls.json', calls)
        assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')[-3000:]
        print(json.dumps(dict(id=name, code=result.returncode)), flush=True)
        if cli:
            value = json.loads(result.stdout.decode('utf-8-sig'))
            assert value['ok']
            return value['data']
    try:
        run('configure', [sys.executable, '-I', '-B', '-u', '-X', 'utf8', home / 'scripts/activate_community_runtime.py',
            '--installed', runtime['installed_directory'], '--packs', Path(devices['voice']['cpu_pack']).parent,
            '--voice-cuda-lib', devices['voice']['cuda_library_directory'],
            '--translation-cuda-lib', devices['translation']['cuda_library_directory'],
            '--semantic-config', runtime['semantic_config']])
        discovery = home.parent / 'isolated-discovery'
        run('register', [*ps, home / 'register-agent-ffmpeg-local-skills.ps1', '-SkillsDirectory', discovery,
                         '-ReceiptPath', OUT / 'registration.json'])
        entry = discovery / 'agent-ffmpeg-local-editor'
        assert entry.resolve() == (home / 'skills/agent-ffmpeg-local-editor').resolve()
        launcher = entry / 'scripts/run.ps1'
        assert run('version', [*ps, launcher, 'version'], True)['cli_version'] == '0.1.21'
        run('capabilities', [*ps, launcher, 'capabilities'], True)
        run('transition-help', [*ps, launcher, 'timeline', 'transition', '--help'])
        # Import into this verifier's own directory. A separate registered
        # Skill render must never change our dry-run byte-invariance fixture.
        project = home.parent / '独立验收 工程'
        package = ROOT / 'docs/assets/float-transition-20261026-r3/editable-transitions.aevpkg.zip'
        media = json.loads((package.parent / 'media-manifest.json').read_bytes())
        package_pin = next(row for row in media['files'] if row['path'].endswith('/'+package.name))
        assert sha(package) == package_pin['sha256']
        run('import-case', [*ps, launcher, 'convert', 'import', '--input', package, '--output', project], True)
        paths = [project / name for name in ('project.json', 'rights-ledger.json')]
        paths.extend(sorted((project / 'assets').rglob('*')))
        paths = [path for path in paths if path.is_file()]
        before = {str(path): sha(path) for path in paths}
        planned = run('float-render-dry-run', [*ps, launcher, 'render', '--project', project,
            '--output', project / 'renders/isolated-plan.mkv', '--container', 'mkv',
            '--hardware-encode', 'off', '--dry-run'], True)
        transitions = planned['plan']['delivery']['pixel_pipeline']['timeline']['transitions']
        assert transitions['GPU'] is False and transitions['group_spatial_edges'] is True
        assert len(transitions['patterns']) == 59
        assert sum(len(plan['transitions']) for plan in transitions['source_handle_plans']) == 5
        assert not (project / 'renders/isolated-plan.mkv').exists()
        run('validate', [*ps, launcher, 'validate', '--project', project], True)
        assert before == {str(path): sha(path) for path in paths}
        assert actual.resolve() == original_target
        report = dict(status='passed', kit=str(kit), kit_sha256=sha(kit), files=len(names) + 1,
            skill_files=sum(name.startswith('skills/') for name in names), cli_version='0.1.21',
            registered_skills=1, internal_modules=17, process_calls=len(calls),
            json_cli_calls=sum(row['json_cli'] for row in calls), real_discovery_changed=False,
            dry_run_metadata_unchanged=True, dry_run_assets_unchanged=True,
            scope='Actual native Float32 transition planning and project validation from a fresh isolated kit registration; dry-run does not render or perform inference.',
            new_model_forwards=0, new_renders=0,
            native_windows=True, virtualization=False, source_fallback=False, generator_sha256=sha(Path(__file__)))
        assert report['files'] == 98 and report['skill_files'] == 70
        report['transition_plan'] = transitions
        save('verification.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except BaseException as exc:
        save('failure.json', dict(status='failed', error=repr(exc), calls=calls))
        raise


if __name__ == '__main__':
    main()
