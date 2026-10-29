"""Replay actual music through an isolated installation or staged unified Skill."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'


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
    parser.add_argument('--skill-entry', type=Path)
    args = parser.parse_args()
    assert args.run.isalnum() and sys.dont_write_bytecode
    candidate = load(BASE / 'candidate-r1/verification.json')
    case = load(BASE / 'actual-piano4/verification.json')
    original = load(BASE / 'package-r1/verification.json')
    assert candidate['status'] == 'installed-and-byte-verified'
    assert case['status'] == original['status'] == 'passed'
    installed = Path(candidate['installed']).resolve()
    site = installed / 'site'
    expected = candidate['source_hashes']
    assert len(expected) == 288 and {p.name:sha(p) for p in (site / 'ai_ad_editor').glob('*.py')} == expected
    assert all(sha(Path(path)) == pin for path,pin in candidate['registered_files'].items())
    guard = dict(candidate['registered_files'])
    skill_files = None
    if args.skill_entry:
        entry = args.skill_entry.resolve()
        stage = ROOT / 'local/agent-ffmpeg/music64-skill-stage-r1'
        skill = stage / 'skills/agent-ffmpeg-local-editor'
        assert entry == skill / 'scripts/run.ps1'
        skill_files = load(stage / 'STAGING.json')['files']
        assert len(skill_files) == 94 and all(sha(skill / p) == pin for p,pin in skill_files.items())
        prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(entry)]
    else:
        prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py')]
    proof = BASE / ('installed-package-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT / ('local/agent-ffmpeg/music64-installed-package-' + args.run)
    work.mkdir()
    calls = []

    def command(name, argv, cli=False):
        began = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=ROOT, capture_output=True, timeout=600,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (proof / (name + '.stdout')).write_bytes(result.stdout)
        (proof / (name + '.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=list(map(str, argv)), exit_code=result.returncode,
                          elapsed_seconds=time.monotonic() - began))
        save(proof / 'calls.json', calls)
        assert result.returncode == 0, (name, result.stdout[-2000:], result.stderr[-2000:])
        if cli:
            value = json.loads(result.stdout)
            assert value['ok'] and value['provenance']['cli_version'] == '0.1.64'
        print(json.dumps(dict(name=name, status='passed')), flush=True)

    try:
        # Parent decoding utilities also load only the installed application.
        sys.path.insert(0, str(site))
        os.environ['AI_AD_EDITOR_RUNTIME_DIR'] = str(installed / 'runtime')
        import ai_ad_editor
        from ai_ad_editor.runtime import configure_local_runtime
        from ai_ad_editor.media import ffmpeg_path
        assert Path(ai_ad_editor.__file__).resolve() == site / 'ai_ad_editor/__init__.py'
        runtime = configure_local_runtime()
        ffmpeg = ffmpeg_path()
        project = work / 'project'
        command('version', [*prefix, 'version'], True)
        command('import', [*prefix, 'convert', 'import', '--input', original['artifacts']['package'], '--output', project], True)
        asset = next(row for row in load(project / 'project.json')['assets'] if row['id'] == case['asset']['id'])
        assert asset['source']['music_generation'] == case['asset']['source']['music_generation']
        assert sha(project / asset['uri']) == sha(Path(case['artifacts']['wav']))
        movie = project / 'renders/installed-neural-music.mp4'
        command('render', [*prefix, 'render', '--project', project, '--output', movie], True)
        decoded = {}
        for kind, options in [('RGBA', ['-an', '-pix_fmt', 'rgba', '-f', 'rawvideo']),
                              ('PCM', ['-vn', '-c:a', 'pcm_f32le', '-f', 'f32le'])]:
            target = work / ('installed.' + kind.lower())
            command('decode-' + kind, [ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', movie, *options, target])
            decoded[kind] = dict(bytes=target.stat().st_size, sha256=sha(target))
            assert decoded[kind] == original['decoded']['original_' + kind]
        assert {p.name:sha(p) for p in (site / 'ai_ad_editor').glob('*.py')} == expected
        assert all(sha(Path(path)) == pin for path,pin in guard.items())
        if skill_files:
            assert all(sha(skill / p) == pin for p,pin in skill_files.items())
        report = dict(status='passed', cli_version='0.1.64', installed=str(installed),
            source_fallback=False, entrypoint=prefix, actual_PowerShell_entry=bool(args.skill_entry),
            registered_C_drive_entry=False, staged_skill_files=94 if skill_files else None,
            complete_master_WAV_equal=True, complete_generation_recipe_equal=True,
            complete_rendered_RGBA_PCM_equal=True, decoded=decoded,
            new_model_forwards=0, independent_installed_generation_accepted=False,
            registered_skill_unchanged=True, registered_skill_cli='0.1.63',
            runtime_root=runtime['root'], decoder_sha256=sha(Path(ffmpeg)),
            source_case_sha256=sha(BASE / 'actual-piano4/verification.json'),
            source_package_sha256=sha(BASE / 'package-r1/verification.json'),
            human_listening=False, natural_quality_accepted=False, media_published=False,
            artifacts=dict(project=str(project), movie=str(movie), master=str(project / asset['uri'])))
        save(proof / 'verification.json', report)
        print(json.dumps({k:v for k,v in report.items() if k != 'artifacts'}), flush=True)
        return 0
    except BaseException as exc:
        save(proof / 'verification.json', dict(status='failed', error=repr(exc), calls=calls,
                                              actual_PowerShell_entry=bool(args.skill_entry), formal_activation=False))
        raise


if __name__ == '__main__':
    raise SystemExit(main())
