"""Register exactly tested64 Skill bytes with a recoverable E-drive transition."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'
COUNTS = dict(music=62, bootstrap=33, control=26, selection=57, semantic=104, contracts=431)


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.cli64-' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--stage-run', default='r1')
    parser.add_argument('--case-run', default='stage1')
    parser.add_argument('--package-run', default='stage1')
    parser.add_argument('--source-case-run', default='piano3')
    parser.add_argument('--source-package-run', default='r1')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    assert all(v.replace('-', '').isalnum() for v in (args.run, args.stage_run, args.case_run, args.package_run,
                                                     args.source_case_run, args.source_package_run))
    gates = {'candidate':BASE / 'candidate-r1/verification.json',
             'actual_source':BASE / ('actual-' + args.source_case_run + '/verification.json'),
             'package_source':BASE / ('package-' + args.source_package_run + '/verification.json'),
             'actual_staged':BASE / ('actual-' + args.case_run + '/verification.json'),
             'package_staged':BASE / ('package-' + args.package_run + '/verification.json'),
             'skill_validation':BASE / ('skill-stage-' + args.stage_run + '/verification.json')}
    for mode in ('source64', 'installed64'):
        for group in COUNTS:
            gates[mode + '_' + group] = BASE / (mode + '-' + group + '-r1/verification.json')
        gates[mode + '_preflight'] = BASE / (mode + '-preflight-r1/verification.json')
    missing = [name for name,path in gates.items() if not path.is_file()]
    failed = {name:dict(path=path.relative_to(ROOT).as_posix(), status=load(path).get('status'))
              for name,path in gates.items() if path.is_file()
              and load(path).get('status') != ('installed-and-byte-verified' if name == 'candidate' else 'passed')}
    if missing or failed:
        print(json.dumps(dict(status='rejected' if failed else 'pending', missing=missing,
                              failed=failed, mutated=False, activated=False)), flush=True)
        return 2
    reports = {name:load(path) for name,path in gates.items()}
    for name,report in reports.items():
        assert report['status'] == ('installed-and-byte-verified' if name == 'candidate' else 'passed'), name
    candidate = reports['candidate']
    installed = Path(candidate['installed']).resolve()
    assert candidate['cli_version'] == '0.1.64'
    assert installed.is_relative_to((ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.62').resolve())
    for mode in ('source64', 'installed64'):
        for group,count in COUNTS.items():
            report = reports[mode + '_' + group]
            assert report['cli_version'] == '0.1.64' and report['tests'] == count and report['frozen_equal']
            assert report['failures'] == report['errors'] == report['skipped'] == 0
            assert all(sha(ROOT / path) == pin for path,pin in report['file_hashes'].items())
            if mode == 'installed64':
                assert report['source_fallback'] is False and Path(report['installed']).resolve() == installed
        preflight = reports[mode + '_preflight']
        assert preflight['cases'] == 6 and preflight['project_and_rights_unchanged']
        assert preflight['owned_worker_started'] is False and preflight['model_forwards'] == 0
    actual, replay = reports['actual_staged'], reports['package_staged']
    original, original_replay = reports['actual_source'], reports['package_source']
    assert original['complete_PCM_roundtrip_verified'] and original['source_frozen_equal']
    assert original['actual_generation']['worker']['model']['neural_backend'] == 'cuda'
    assert original_replay['complete_master_WAV_equal'] and original_replay['complete_generation_recipe_equal']
    assert original_replay['complete_rendered_RGBA_PCM_equal']
    assert all(sha(ROOT / path) == pin for path,pin in original['source_hashes'].items())
    assert actual['actual_PowerShell_entry'] and actual['source_fallback'] is False
    assert Path(actual['installed']).resolve() == installed and actual['complete_PCM_roundtrip_verified']
    assert actual['actual_generation']['worker']['model']['CPU_fallback'] is False
    assert actual['actual_generation']['cleanup']['worker_exited'] and actual['actual_generation']['cleanup']['owner_job_closed']
    assert replay['complete_master_WAV_equal'] and replay['complete_generation_recipe_equal']
    assert replay['complete_rendered_RGBA_PCM_equal'] and replay['actual_PowerShell_entry']
    assert replay['actual_case_sha256'] == sha(gates['actual_staged'])
    stage_home = ROOT / 'local/agent-ffmpeg' / ('music64-skill-stage-' + args.stage_run)
    stage = stage_home / 'skills/agent-ffmpeg-local-editor'
    staging = load(stage_home / 'STAGING.json')
    files = {p.relative_to(stage).as_posix():sha(p) for p in stage.rglob('*') if p.is_file()}
    assert files == staging['files'] == actual['skill_files'] == reports['skill_validation']['files']
    assert len(files) == 94 and reports['skill_validation']['frontmatter_validation_passed']
    namespace, runtime = ROOT / 'agent-ffmpeg-local-install-manifest.json', ROOT / 'local/agent-ffmpeg/runtime.json'
    assert all(sha(Path(path)) == pin for path,pin in candidate['registered_files'].items())
    manifest = load(namespace)
    assert manifest['cli_version'] == '0.1.63' and len(manifest['files']) == 93
    assert manifest['skill_count'] == 1 and manifest['module_count'] == 17
    folder = ROOT / 'skills/agent-ffmpeg-local-editor'
    discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert discovery.resolve(strict=True) == folder.resolve()
    source = {p.name:sha(p) for p in (ROOT / 'product/src/ai_ad_editor').glob('*.py')}
    assert source == candidate['source_hashes'] == {p.name:sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    assert len(source) == 288
    if not args.apply:
        print(json.dumps(dict(status='ready', mutated=False, activated=False, files=94)), flush=True)
        return 0
    out = BASE / ('skill64-activation-' + args.run)
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    old_namespace, old_runtime = namespace.read_bytes(), runtime.read_bytes()
    old_files = {Path(row['path']).relative_to('skills/agent-ffmpeg-local-editor').as_posix():
                 (ROOT / row['path']).read_bytes() for row in manifest['files']}
    (out / 'previous-namespace.json').write_bytes(old_namespace)
    (out / 'previous-runtime.json').write_bytes(old_runtime)
    for name, content in old_files.items():
        target = out / 'previous-skill' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    next_config = load(stage_home / 'local/agent-ffmpeg/runtime.json')
    transition = copy.deepcopy(load(runtime))
    transition['release'] = 'transition-cli64-not-ready'
    pins = {name:dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path)) for name,path in gates.items()}
    journal = dict(status='prepared', cli_version='0.1.64', gates=pins,
        added_files=sorted(set(files) - set(old_files)),
        crash_recovery='Restore previous Skill files, remove only added_files, restore previous namespace and runtime; keep backups on E.')
    (out / 'journal.json').write_bytes(encoded(journal))
    calls = []
    try:
        atomic(runtime, encoded(transition))
        for name in files:
            content = (stage / name).read_bytes()
            if old_files.get(name) != content:
                atomic(folder / name, content)
        manifest.update(release=next_config['release'], cli_version='0.1.64', manifest_sha256=candidate['manifest_sha256'])
        manifest['skills'][0]['skill_md_sha256'] = sha(folder / 'SKILL.md')
        manifest['skills'][0]['purpose_zh'] += '、原生CUDA神经配乐与生成请求'
        manifest['files'] = [dict(path=(folder / name).relative_to(ROOT).as_posix(),
                                 bytes=(folder / name).stat().st_size, sha256=pin) for name,pin in sorted(files.items())]
        atomic(namespace, encoded(manifest))
        atomic(runtime, encoded(next_config))
        for name, options in [('version', ['version']), ('capabilities', ['capabilities']),
                              ('music-help', ['music', 'generate', '--help'])]:
            argv = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    str(discovery / 'scripts/run.ps1'), *options]
            result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=300,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            (out / (name + '.stdout')).write_bytes(result.stdout)
            (out / (name + '.stderr')).write_bytes(result.stderr)
            calls.append(dict(name=name, argv=argv, exit_code=result.returncode))
            assert result.returncode == 0, name
            if name != 'music-help':
                value = json.loads(result.stdout)
                assert value['ok'] and value['provenance']['cli_version'] == '0.1.64'
        assert files == {p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}
        assert discovery.resolve(strict=True) == folder.resolve()
        assert all(sha(gates[name]) == pin['sha256'] for name,pin in pins.items())
    except BaseException as exc:
        atomic(runtime, encoded(transition))
        for name in set(files) - set(old_files):
            (folder / name).unlink(missing_ok=True)
        for name,content in old_files.items():
            if (folder / name).read_bytes() != content:
                atomic(folder / name, content)
        atomic(namespace, old_namespace)
        atomic(runtime, old_runtime)
        journal.update(status='rolled-back', error=repr(exc), calls=calls)
        (out / 'verification.json').write_bytes(encoded(journal))
        raise
    journal['status'] = 'committed'
    (out / 'journal.json').write_bytes(encoded(journal))
    (out / 'verification.json').write_bytes(encoded(dict(status='activated-and-entry-verified',
        cli_version='0.1.64', release=next_config['release'], public_entries=1, modules=17, skill_files=94,
        actual_C_drive_entry=True, native_windows=True, source_fallback=False, calls=calls, gates=pins,
        namespace_sha256=sha(namespace), runtime_sha256=sha(runtime), tested_candidate_files=files,
        old_skill_backup_hashes={name:hashlib.sha256(content).hexdigest() for name,content in old_files.items()},
        discovery_unchanged=True, post_test_document_changes=False, registered_model_case_pending=True,
        natural_quality_accepted=False, full_product_goal_closed=False)))
    print(json.dumps(dict(status='activated-and-entry-verified', cli_version='0.1.64', skill_files=94)), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
