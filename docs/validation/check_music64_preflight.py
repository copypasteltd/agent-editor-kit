"""Exercise public CLI failures before model launch, preserving project bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and sys.dont_write_bytecode
    mode = 'installed64' if args.installed else 'source64'
    out = BASE / (mode + '-preflight-' + args.run)
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT / 'local/agent-ffmpeg' / ('music-generation64-preflight-' + mode + '-' + args.run)
    work.mkdir()
    source = ROOT / 'product/src/ai_ad_editor'
    frozen = {p.name:sha(p) for p in source.glob('*.py')}
    if args.installed:
        installed = args.installed.resolve()
        assert installed.is_relative_to((ROOT / 'local/agent-ffmpeg').resolve())
        assert frozen == {p.name:sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
        prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py')]
    else:
        entry = work / 'source_entry.py'
        entry.write_text('import sys\nsys.path.insert(0,' + repr(str(source.parent)) + ')\n'
                         'from ai_ad_editor.cli import main\nraise SystemExit(main())\n', encoding='utf-8')
        prefix = [sys.executable, '-E', '-B', '-u', '-X', 'utf8', str(entry)]
    calls = []

    def call(name, argv, expected=None):
        started = time.monotonic()
        command = [*prefix, *map(str, argv)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=120,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        value = json.loads(result.stdout)
        assert value['provenance']['cli_version'] == '0.1.64'
        code = value['errors'][0]['code'] if value.get('errors') else None
        calls.append(dict(name=name, argv=command, exit_code=result.returncode, error_code=code,
                          elapsed_seconds=time.monotonic() - started))
        save(out / 'calls.json', calls)
        assert (result.returncode != 0 and not value['ok'] and code == expected) if expected else (result.returncode == 0 and value['ok'])
        return value

    try:
        project = work / 'project'
        call('init', ['project', 'init', project])
        before = {name:sha(project / name) for name in ('project.json', 'rights-ledger.json')}
        request = work / 'request.json'
        base = dict(format='agent-neural-music-v1', prompt='Original acoustic instrumental.',
                    lyrics='', instrumental=True, duration_seconds=10)
        save(request, base)
        common = ['music', 'generate', '--project', project, '--adapter-id', 'unregistered',
                  '--input', request, '--new-asset-id', 'must_not_exist']
        marker = work / 'cancel.txt'
        marker.write_text('Explicit pre-launch cancellation\n', encoding='utf-8')
        call('cancel-before-launch', [*common, '--cancel-file', marker], 'CANCELLED')
        call('zero-timeout', [*common, '--timeout-seconds', '0'], 'ARGUMENT_INVALID')
        call('below-storage-budget', [*common, '--storage-budget-mib', '63'], 'ARGUMENT_INVALID')
        save(request, dict(base, duration_seconds=10.01))
        call('non-native-clock', common, 'ARGUMENT_INVALID')
        save(request, dict(base, instrumental=False))
        call('missing-singing-lyrics', common, 'ARGUMENT_INVALID')
        save(request, base)
        call('missing-adapter', common, 'MUSIC_GENERATION_ADAPTER_UNAVAILABLE')
        assert before == {name:sha(project / name) for name in before}
        assert not (project / 'cache/managed-jobs').exists() or not list((project / 'cache/managed-jobs').iterdir())
        assert not (project / 'assets/derived/must_not_exist.wav').exists()
        assert frozen == {p.name:sha(p) for p in source.glob('*.py')}
        save(out / 'verification.json', dict(status='passed', cli_version='0.1.64',
            cases=6, calls=calls, project_and_rights_unchanged=True, output_published=False,
            owned_worker_started=False, model_forwards=0, source_hashes=frozen,
            installed=str(args.installed.resolve()) if args.installed else None,
            source_fallback=False if args.installed else None,
            mid_inference_cancellation_accepted=False, natural_quality_accepted=False))
        print(json.dumps(dict(status='passed', cases=6, model_forwards=0)), flush=True)
    except BaseException as exc:
        save(out / 'verification.json', dict(status='failed', cli_version='0.1.64', error=repr(exc), calls=calls))
        raise


if __name__ == '__main__':
    main()
