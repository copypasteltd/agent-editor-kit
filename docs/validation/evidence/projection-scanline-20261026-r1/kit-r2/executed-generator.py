"""Verify the single-entry r20 kit without changing actual Codex discovery."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/projection-scanline-20261026-r1'


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
    kit = ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r20.zip'
    home = ROOT / 'local/agent-ffmpeg' / ('projection-scanline-kit-' + args.run) / '独立工具 包'
    home.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(kit) as archive:
        inventory = json.loads(archive.read('KIT-FILES.json'))
        assert inventory['cli_version'] == '0.1.19'
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
        assert run('version', [*ps, launcher, 'version'], True)['cli_version'] == '0.1.19'
        run('capabilities', [*ps, launcher, 'capabilities'], True)
        run('motion-help', [*ps, launcher, 'motion', 'pack', 'apply', '--help'])
        # Import into this verifier's own directory. A separate registered
        # Skill render must never change our dry-run byte-invariance fixture.
        project = home.parent / '独立验收 工程'
        package = ROOT / 'workspace/motion-pack-20261025-installed-r1/editable-motion.aevpkg.zip'
        assert sha(package) == '0c842a82ef864b73e0d7200c5bfe45c67f3a9290c990b5cf585a7e78227fc85c'
        run('import-case', [*ps, launcher, 'convert', 'import', '--input', package, '--output', project], True)
        paths = [project / name for name in ('project.json', 'rights-ledger.json')]
        paths.extend(sorted((project / 'assets').rglob('*')))
        paths = [path for path in paths if path.is_file()]
        before = {str(path): sha(path) for path in paths}
        inspected = run('motion-inspect', [*ps, launcher, 'motion', 'pack', 'inspect', '--name', 'arc_push'], True)
        assert inspected['pack']['id'] == 'arc_push'
        planned = run('motion-dry-run', [*ps, launcher, 'motion', 'pack', 'apply', '--project', project,
            '--sequence-id', 'reused_arc', '--clip-id', 'reused_hero', '--name', 'arc_push', '--replace', '--dry-run'], True)
        assert planned['motion']['keyframe_count'] == 195 and planned['validation']['ok']
        run('validate', [*ps, launcher, 'validate', '--project', project], True)
        assert before == {str(path): sha(path) for path in paths}
        assert actual.resolve() == original_target
        report = dict(status='passed', kit=str(kit), kit_sha256=sha(kit), files=len(names) + 1,
            skill_files=sum(name.startswith('skills/') for name in names), cli_version='0.1.19',
            registered_skills=1, internal_modules=17, process_calls=len(calls),
            json_cli_calls=sum(row['json_cli'] for row in calls), real_discovery_changed=False,
            dry_run_metadata_unchanged=True, dry_run_assets_unchanged=True,
            scope='Actual parameterized motion inspection, compilation dry-run and project validation on this native host.',
            new_model_forwards=0, new_renders=0,
            native_windows=True, virtualization=False, source_fallback=False, generator_sha256=sha(Path(__file__)))
        save('verification.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except BaseException as exc:
        save('failure.json', dict(status='failed', error=repr(exc), calls=calls))
        raise


if __name__ == '__main__':
    main()
