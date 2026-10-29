"""Validate the unregistered Skill and invoke its actual native PS launcher."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and sys.dont_write_bytecode
    home = ROOT / 'local/agent-ffmpeg' / ('music64-skill-stage-' + args.run)
    staging_path = home / 'STAGING.json'
    if not staging_path.is_file():
        print(json.dumps(dict(status='pending', missing=['staged Skill'], mutated=False)), flush=True)
        return 2
    staging = load(staging_path)
    skill = Path(staging['skill'])
    assert skill.resolve().is_relative_to(home.resolve())
    assert staging['cli_version'] == '0.1.64' and staging['status'] == 'unregistered-candidate'
    files = {p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}
    assert files == staging['files'] and len(files) == 94
    assert all(sha(Path(path)) == pin for path,pin in staging['registered_files'].items())
    out = BASE / ('skill-stage-' + args.run)
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    calls = []

    def call(name, command):
        result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, timeout=300,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=list(map(str, command)), exit_code=result.returncode))
        assert result.returncode == 0, (name, result.stdout[-1000:], result.stderr[-1000:])
        return result.stdout

    try:
        validator = Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
        call('frontmatter', [sys.executable, '-E', '-B', '-X', 'utf8', validator, skill])
        compiled = []
        for relative in sorted(files):
            if relative.endswith('.py'):
                compile((skill / relative).read_bytes(), str(skill / relative), 'exec')
                compiled.append(relative)
        prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', skill / 'scripts/run.ps1']
        version = json.loads(call('version', [*prefix, 'version']))
        assert version['ok'] and version['data']['cli_version'] == '0.1.64'
        help_text = call('music-help', [*prefix, 'music', 'generate', '--help']).decode('utf-8')
        assert all(option in help_text for option in ('--input', '--recipe-asset-id', '--cancel-file', '--apply', '--storage-budget-mib'))
        assert files == {p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}
        assert all(sha(Path(path)) == pin for path,pin in staging['registered_files'].items())
        report = dict(status='passed', cli_version='0.1.64', files=files, calls=calls,
            frontmatter_validation_passed=True, compiled_scripts=compiled, actual_PowerShell_entry=True,
            formal_files_unchanged=True, formal_activation=False, source_fallback=False,
            actual_generation_executed=False, natural_quality_accepted=False)
    except BaseException as exc:
        report = dict(status='failed', cli_version='0.1.64', error=repr(exc), calls=calls)
        (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        raise
    (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status='passed', files=94, formal_activation=False)), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
