"""Actual source64 music through the public CLI; no service, GUI, or fake worker."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'
PYTHON = 'C:/Python313/python.exe'
MODEL_PYTHON = 'E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe'
NATIVE_CORE = 'E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/ComfyUI'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--case', choices=['piano', 'funk', 'singing'], default='piano')
    parser.add_argument('--unit-run', default='r5')
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and sys.dont_write_bytecode
    acquisition = load(ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1/acquisition-r1/verification.json')
    interface = load(ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1/native-interface-r3/verification.json')
    notices = ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1/notices-r2/verification.json'
    assert acquisition['status'] == interface['status'] == load(notices)['status'] == 'passed'
    unit = load(BASE.parent / f'music-generation-20261030-{args.unit_run}/unit/verification.json')
    assert unit['status'] == 'passed' and unit['tests'] == 25
    assert all(sha(ROOT / row['path']) == row['sha256'] for row in unit['files'])
    out = BASE / ('actual-' + args.run)
    out.mkdir(parents=True)
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT / 'local/agent-ffmpeg' / ('music-generation64-' + args.run)
    work.mkdir()
    entry = work / 'source_entry.py'
    entry.write_text('import sys\nsys.path.insert(0,' + repr(str(ROOT / 'product/src')) + ')\n'
                     'from ai_ad_editor.cli import main\nraise SystemExit(main())\n', encoding='utf-8')
    source = ROOT / 'product/src/ai_ad_editor'
    frozen = {p.relative_to(ROOT).as_posix():sha(p) for p in source.glob('*.py')}
    manifest = ROOT / 'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT / 'local/agent-ffmpeg/runtime.json'
    registered = load(manifest)
    guard = {str(p):sha(p) for p in (manifest, runtime)}
    guard.update({str(ROOT / row['path']):row['sha256'] for row in registered['files']})
    calls = []

    def cli(name, *argv):
        command = [PYTHON, '-E', '-B', '-u', '-X', 'utf8', str(entry), *map(str, argv)]
        started = time.monotonic()
        with (out / (name + '.stdout')).open('xb') as stdout, (out / (name + '.stderr')).open('xb') as stderr:
            result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                    timeout=3600, creationflags=subprocess.CREATE_NO_WINDOW)
        calls.append(dict(name=name, argv=command, exit_code=result.returncode,
                          elapsed_seconds=time.monotonic() - started))
        save(out / 'calls.json', calls)
        print(json.dumps(dict(name=name, exit_code=result.returncode)), flush=True)
        value = load(out / (name + '.stdout'))
        assert result.returncode == 0 and value['ok'], (name, value)
        assert value['provenance']['cli_version'] == '0.1.64'
        return value['data']

    project = work / 'project'
    try:
        cli('version', 'version')
        cli('init', 'project', 'init', project)
        adapter = cli('register', 'music', 'generator-adapter', 'register', '--project', project,
            '--adapter-id', 'ace15', '--model-path', ROOT / 'product/.runtime/models/acestep15-20261029',
            '--runtime-root', NATIVE_CORE, '--executable', MODEL_PYTHON, '--evidence', notices,
            '--creator', 'ACE-Step / Comfy-Org; existing native ComfyUI core',
            '--license-spdx', 'Apache-2.0 AND GPL-3.0-only',
            '--license-url', notices.parent / 'Apache-2.0.txt', '--threads', '4')
        generation = dict(format='agent-neural-music-v1',
            prompt='Intimate acoustic piano instrumental, gentle melodic phrases, warm upright bass, soft brushed drums, elegant quiet evening atmosphere, original chamber jazz, clean studio recording.',
            lyrics='', instrumental=True, duration_seconds=10, bpm=90, language='unknown',
            keyscale='D minor', timesignature=4, seed=20261030, steps=8, generate_audio_codes=True)
        if args.case == 'funk':
            generation.update(prompt='Upbeat instrumental funk for a product advertisement, tight syncopated bass guitar, punchy acoustic drums, bright rhythm guitar and clean horn stabs, energetic playful groove, clean studio recording.',
                              duration_seconds=16, bpm=120, keyscale='C major', seed=20261031)
        elif args.case == 'singing':
            generation.update(prompt='Chinese Mandarin pop song, clear gentle female singing voice, acoustic guitar, soft piano and light drums, hopeful warm melody, clean studio recording.',
                              lyrics='[Verse]\n迎着晨光向前走\n让每个愿望慢慢开花\n[Chorus]\n把温暖留在心里\n一起迎接新的开始',
                              instrumental=False, duration_seconds=16, bpm=100, language='zh', keyscale='C major', seed=20261032)
        request = work / 'request.json'
        save(request, generation)
        inspected = cli('inspect', 'music', 'inspect-generation', '--input', request)
        assert inspected['samples'] == round(generation['duration_seconds'] * 48000)
        before = {name:sha(project / name) for name in ('project.json', 'rights-ledger.json')}
        cli('dry-run', 'music', 'generate', '--project', project, '--adapter-id', 'ace15', '--input', request,
            '--new-asset-id', args.case, '--apply', '--track-id', 'track_audio_1', '--dry-run')
        assert all(sha(project / name) == value for name, value in before.items())
        result = cli('generate', 'music', 'generate', '--project', project, '--adapter-id', 'ace15', '--input', request,
            '--new-asset-id', args.case, '--apply', '--track-id', 'track_audio_1', '--timeout-seconds', '1800')
        audio = project / result['asset']['uri']
        run = result['generation']
        assert run['complete_PCM_roundtrip_verified'] and run['cleanup']['worker_exited'] and run['cleanup']['owner_job_closed']
        assert run['worker']['model']['neural_backend'] == 'cuda'
        assert run['worker']['samples'] == inspected['samples'] and 'sha256:' + sha(audio) == result['asset']['sha256']
        assert result['rights']['verification_status'] == 'unverified' and result['rights']['permitted_uses'] == ['internal']
        assert result['clip']['asset_id'] == args.case
        assert all(sha(ROOT / name) == value for name, value in frozen.items())
        assert all(sha(Path(name)) == value for name, value in guard.items())
        save(out / 'request.json', generation)
        save(out / 'verification.json', dict(status='passed', cli_version='0.1.64', source_only=True,
            case=args.case, adapter_sha256=adapter['adapter']['sha256'], actual_generation=run,
            asset=result['asset'], rights=result['rights'], clip=result['clip'],
            source_frozen_equal=True, source_hashes=frozen, registered_skill_unchanged=True,
            registered_skill_cli=registered['cli_version'], dry_run_readonly=True,
            complete_PCM_roundtrip_verified=True, human_listening=False, natural_quality_accepted=False,
            generated_audio_publication_approved=False, full_product_goal_closed=False,
            artifacts=dict(project=str(project), wav=str(audio), request=str(request))))
        print(json.dumps(dict(status='passed', case=args.case, native_samples=run['worker']['samples'],
                              actual_cuda_forwards=run['worker']['model']['forwards'])), flush=True)
    except BaseException as exc:
        save(out / 'verification.json', dict(status='failed', case=args.case, cli_version='0.1.64',
                                            source_only=True, error=repr(exc), calls=calls))
        raise


if __name__ == '__main__':
    main()
