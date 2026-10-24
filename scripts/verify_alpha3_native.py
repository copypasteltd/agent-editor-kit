"""Retain native, installed-kit integration evidence and its actual demo media."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil
import subprocess
import sys


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('kit', 'demo', 'discovery', 'archive', 'evidence', 'assets'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.evidence.exists() or args.assets.exists():
        raise ValueError('Existing evidence and media are preserved')
    args.evidence.mkdir(parents=True)
    args.assets.mkdir(parents=True)
    runtime_home = args.kit / 'local/agent-ffmpeg/v0.1.0-alpha.3'
    installation = json.loads((runtime_home / 'installation.json').read_bytes())
    demo = json.loads((args.demo / 'verification.json').read_bytes())
    commands = json.loads((args.demo / 'commands.json').read_bytes())
    assert installation['ok'] and demo['ok'] and len(commands) == 20
    assert all(row['exit_code'] == 0 and row['ok'] for row in commands)
    shutil.copytree(args.demo / 'logs', args.evidence / 'demo/logs')
    for name in ('commands.json', 'verification.json', 'changes.json', 'probe.json', 'decode.log'):
        shutil.copyfile(args.demo / name, args.evidence / 'demo' / name)
    for name in ('installation.json', 'install.stdout.json', 'install.stderr.txt', 'version.json'):
        shutil.copyfile(runtime_home / name, args.evidence / ('installation-' + name))
    shutil.copyfile(args.kit / 'agent-ffmpeg-local-install-manifest.json', args.evidence / 'skill-registration.json')
    manifest = json.loads((args.kit / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    registered = []
    for row in manifest['skills']:
        path = args.discovery / row['name']
        target = args.kit / 'skills' / row['name']
        assert path.is_junction() and path.resolve() == target.resolve()
        assert sha(path / 'SKILL.md') == row['skill_md_sha256']
        registered.append({'name': row['name'], 'junction_verified': True, 'skill_sha256': sha(path / 'SKILL.md')})
    assert len(registered) == 17
    launcher = args.discovery / 'agent-ffmpeg-local-editor/scripts/run.ps1'
    queried = []
    for name, tail in [('version', ['version']), ('doctor', ['doctor']),
                       ('capabilities', ['capabilities']), ('look-inspect', ['look', 'inspect', '--id', 't3-kodak-gold-200'])]:
        command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(launcher), *tail]
        result = subprocess.run(command, capture_output=True, timeout=90)
        (args.evidence / (name + '.stdout.json')).write_bytes(result.stdout)
        (args.evidence / (name + '.stderr.txt')).write_bytes(result.stderr)
        response = json.loads(result.stdout)
        assert result.returncode == 0 and response['ok'] and not response.get('errors')
        queried.append({'command': command, 'exit_code': result.returncode, 'ok': response['ok']})
    # Refusals use owned fixture files and verify that successful work is preserved.
    protected = [args.kit / 'local/agent-ffmpeg/runtime.json', args.demo / 'project/project.json',
                 args.demo / 'project/renders/demo.mp4', args.demo / 'demo.aevpkg.zip']
    before = {str(path): sha(path) for path in protected}
    wrong = args.evidence / 'wrong-runtime.zip'
    wrong.write_bytes(b'owned negative fixture: not the pinned runtime ZIP\n')
    refused = []
    for name, command in [
        ('wrong-runtime', [sys.executable, '-I', '-B', '-X', 'utf8', str(args.kit / 'install.py'), '--archive', str(wrong)]),
        ('existing-demo', [sys.executable, '-I', '-B', '-X', 'utf8', str(args.kit / 'run-example.py'), '--output', str(args.demo)]),
    ]:
        result = subprocess.run(command, capture_output=True, timeout=90)
        (args.evidence / (name + '.stdout.json')).write_bytes(result.stdout)
        (args.evidence / (name + '.stderr.txt')).write_bytes(result.stderr)
        response = json.loads(result.stdout)
        assert result.returncode == 2 and response['ok'] is False and response['status'] == 'failed-preserved'
        assert before == {str(path): sha(path) for path in protected}
        refused.append({'case': name, 'command': command, 'exit_code': result.returncode,
                        'status': response['status'], 'existing_outputs_unchanged': True})
    source = args.demo / 'project/renders/demo.mp4'
    shutil.copyfile(source, args.assets / 'demo.mp4')
    shutil.copytree(args.demo / 'input', args.assets / 'input')
    shutil.copyfile(args.demo / 'input/LICENSE.txt', args.assets / 'LICENSE.txt')
    for name, tail in [
        ('poster', ['-ss', '1', '-frames:v', '1', str(args.assets / 'poster.png')]),
        ('gif', ['-vf', 'fps=10,scale=270:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse', '-loop', '0', str(args.assets / 'demo.gif')]),
    ]:
        command = ['ffmpeg', '-nostdin', '-v', 'error', '-n', '-i', str(source), *tail]
        result = subprocess.run(command, capture_output=True, timeout=120)
        (args.evidence / (name + '.log')).write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0
    media = [{'path': p.relative_to(args.assets).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(args.assets.rglob('*')) if p.is_file()]
    save(args.assets / 'manifest.json', {'case': 'alpha3-portable-kit', 'release': 'v0.1.0-alpha.3',
        'source_demo_sha256': demo['video_sha256'], 'frames': 180, 'fps': '30/1', 'seconds': 6,
        'license': 'CC0-1.0', 'assets': media, 'gif_has_audio': False,
        'continuous_playback_review': False, 'listening_review': False})
    report = {'status': 'passed-with-open-product-limits', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'release': 'v0.1.0-alpha.3', 'installation': installation, 'native_path_has_chinese_and_spaces': True,
        'skills': registered, 'registered_skill_queries': queried, 'demo': demo,
        'actual_cli_calls': 20, 'additional_registered_launcher_queries': 4, 'expected_refusals': refused,
        'initial_orchestration_failure': {'operation': 'exec_command with not-yet-created workdir',
            'installer_started': False, 'resolution': 'Extract from an existing parent, then Set-Location into the new Agent kit'},
        'network_downloads_in_product_flow': 0, 'new_model_inferences': 0, 'virtualization_invoked': False,
        'browser_invoked': False, 'historical_2930_suite_rerun': False,
        'clean_second_host_test': False, 'full_capcut_parity_accepted': False,
        'listening_review': False, 'natural_footage_acceptance': False,
        'open_limits': ['Native Windows CPython 3.13 x64 only', 'Existing native FFmpeg/ffprobe required',
                        'Optional models and browser adapters are not installed by this kit',
                        'Historical quality failures remain open; see goal-gap assessment']}
    save(args.evidence / 'verification.json', report)
    print(json.dumps({'status': report['status'], 'demo_cli_calls': 20, 'registered_skills': 17,
                      'registered_queries': 4, 'refusals': len(refused), 'media': len(media)}))


if __name__ == '__main__':
    main()
