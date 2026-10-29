"""Exercise the actual PowerShell front door of an unregistered CLI55 Skill."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/process-budget-20261029-r1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    installation = load(BASE/'installation-candidate-r1/verification.json')
    assert installation['status'] == 'installed-and-byte-verified' and installation['cli_version'] == '0.1.55'
    for group, count in [('deadline', 15), ('selection', 45), ('semantic', 104)]:
        gate = load(BASE/('installed-'+group+'-r1')/'verification.json')
        assert gate['status'] == 'passed' and gate['tests'] == count and gate['frozen_equal']
        assert gate['installed'] == installation['installed']
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT/'local/agent-ffmpeg/runtime.json'
    namespace_pin, runtime_pin = sha(namespace), sha(runtime)
    live = load(namespace)
    assert live['cli_version'] == '0.1.53' and len(live['files']) == 92
    discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert discovery.resolve() == (ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    home = ROOT/'local/agent-ffmpeg/ad-selection-skill-stage-r2'
    skill = home/'skills/agent-ffmpeg-local-editor'
    files = {p.relative_to(skill).as_posix(): sha(p) for p in skill.rglob('*') if p.is_file()}
    assert len(files) == 93 and sum(Path(n).name == 'SKILL.md' for n in files) == 1
    config = load(runtime)
    config.update(release='v0.1.0-alpha.4-local.53', installed_directory=installation['installed'],
        manifest_sha256=installation['manifest_sha256'], launcher_sha256=sha(Path(installation['installed'])/'run.py'))
    config_path = home/'local/agent-ffmpeg/runtime.json'
    assert not config_path.exists()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    save(config_path, config)
    out = BASE/('skill-candidate-'+args.run)
    out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    calls = []
    for command in ('version', 'capabilities'):
        argv = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                str(skill/'scripts/run.ps1'), command]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=300,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(command+'.stdout')).write_bytes(result.stdout)
        (out/(command+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(argv=argv, exit_code=result.returncode))
        save(out/'calls.json', calls)
        assert result.returncode == 0, (command, result.stdout[-1000:], result.stderr[-1000:])
        value = json.loads(result.stdout)
        assert value['ok'] and value['provenance']['cli_version'] == '0.1.55'
        if command == 'capabilities':
            assert 'ad.select' in value['data']['capabilities']['ai']['ad_storyboard']['commands']
    assert files == {p.relative_to(skill).as_posix(): sha(p) for p in skill.rglob('*') if p.is_file()}
    assert sha(namespace) == namespace_pin and sha(runtime) == runtime_pin
    assert all(sha(ROOT/r['path']) == r['sha256'] for r in live['files'])
    assert discovery.resolve() == (ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    report = dict(status='passed', cli_version='0.1.55', actual_PowerShell_entry=True,
        candidate_registered=False, live_skill_changed=False, source_fallback=False,
        public_entries=1, modules=17, files=93, calls=2, actual_GPU_forwards=0,
        namespace_sha256=namespace_pin, live_runtime_sha256=runtime_pin,
        candidate_files=files, actual_installed_case_required_before_activation=True)
    save(out/'verification.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'candidate_files'}), flush=True)


if __name__ == '__main__':
    main()
