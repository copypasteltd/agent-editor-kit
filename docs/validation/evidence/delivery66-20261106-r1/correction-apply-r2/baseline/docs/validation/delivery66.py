"""Code-first delivery66: freeze, whole-suite checks, offline install, replay, stage."""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/delivery66-20261106-r1'
LOCAL = ROOT / 'local/agent-ffmpeg/delivery66'
SOURCE = ROOT / 'product/src/ai_ad_editor'
VERSION = '0.1.66'
RELEASE = 'v0.1.0-alpha.4-local.64'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def pins():
    paths = [*SOURCE.glob('*.py'), *(ROOT / 'product/tests').glob('*.py'),
             ROOT / 'product/pyproject.toml', *(ROOT / 'product/offline').glob('*.py')]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}


def formal_guard():
    manifest = load(ROOT / 'agent-ffmpeg-local-install-manifest.json')
    result = {p['path']: sha(ROOT / p['path']) for p in manifest['files']}
    for name in ('agent-ffmpeg-local-install-manifest.json', 'local/agent-ffmpeg/runtime.json'):
        result[name] = sha(ROOT / name)
    return result


def unchanged(freeze):
    assert pins() == freeze['file_hashes'], 'Frozen product or tests changed'
    assert all(sha(ROOT / name) == pin for name, pin in freeze['formal_guard'].items()), 'Formal entry changed'


def proof(action, run):
    path = BASE / (action + '-' + run)
    path.mkdir(parents=True)
    (path / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    return path


def call(out, name, command, *, timeout=1200, cli=False):
    env = dict(os.environ)
    temp = LOCAL / 'temp'
    temp.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1',
               PIP_NO_INDEX='1', PIP_NO_CACHE_DIR='1', PIP_CONFIG_FILE=os.devnull)
    began = time.monotonic()
    result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, capture_output=True,
        timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    (out / (name + '.stdout')).write_bytes(result.stdout)
    (out / (name + '.stderr')).write_bytes(result.stderr)
    previous = load(out / 'calls.json') if (out / 'calls.json').exists() else []
    previous.append(dict(name=name, argv=list(map(str, command)), exit_code=result.returncode,
                         elapsed_seconds=time.monotonic() - began))
    save(out / 'calls.json', previous)
    assert result.returncode == 0, (name, result.stdout[-2000:], result.stderr[-3000:])
    print(json.dumps(dict(step=name, status='passed', elapsed_seconds=previous[-1]['elapsed_seconds'])), flush=True)
    if cli:
        value = json.loads(result.stdout)
        assert value['ok'] and value['provenance']['cli_version'] == VERSION
        return value
    return result.stdout


def freeze_code(args):
    out = proof('freeze', args.run)
    for name in pins():
        if name.endswith('.py'):
            compile((ROOT / name).read_bytes(), name, 'exec')
    # The third-party DF3 NotImplemented branches guard invalid enum values;
    # its three declared configurations already have implementations.
    save(out / 'verification.json', dict(status='frozen', cli_version=VERSION, file_hashes=pins(),
        formal_guard=formal_guard(), implementation_units=['T01', 'T02', 'T03', 'T04', 'T05', 'T06'],
        code_completed_before_tests=True, functional_tests_started=False, model_forwards=0))
    print('All delivery66 code frozen before functional tests.', flush=True)


def test_all(args, freeze):
    mode = 'installed-all' if args.installed else 'source-all'
    out = proof(mode, args.run)
    package = args.installed.resolve() / 'site/ai_ad_editor' if args.installed else SOURCE
    expected = {p.name: sha(p) for p in SOURCE.glob('*.py')}
    assert expected == {p.name: sha(p) for p in package.glob('*.py')}
    sys.path[:0] = [str(package.parent), str(ROOT / 'product/tests')]
    import ai_ad_editor
    from ai_ad_editor.runtime import configure_local_runtime
    assert ai_ad_editor.VERSION == VERSION and Path(ai_ad_editor.__file__).resolve() == package / '__init__.py'
    configure_local_runtime()
    # Preserve all existing tests, load_tests filters, deadlines and failures.
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'product/tests'), pattern='test_*.py')
    count = suite.countTestCases()
    print(json.dumps(dict(phase=mode, discovered_tests=count)), flush=True)
    began = time.monotonic()
    with (out / 'tests.stderr').open('w', encoding='utf-8', newline='\n') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    unchanged(freeze)
    assert expected == {p.name: sha(p) for p in package.glob('*.py')}
    report = dict(status='passed' if result.wasSuccessful() and not result.skipped else 'failed',
        cli_version=VERSION, tests=result.testsRun, discovered_tests=count, failures=len(result.failures),
        errors=len(result.errors), skipped=len(result.skipped), frozen_equal=True, file_hashes=freeze['file_hashes'],
        source_fallback=False if args.installed else None, installed=str(args.installed) if args.installed else None,
        loaded_package=str(package), elapsed_seconds=time.monotonic() - began,
        original_assertions_preserved=True, human_listening=False, natural_quality_accepted=False)
    save(out / 'verification.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'file_hashes'}), flush=True)
    return 0 if report['status'] == 'passed' else 1


def build(args, freeze):
    out = proof('candidate', args.run)
    source_tests = load(BASE / ('source-all-' + args.tests_run) / 'verification.json')
    assert source_tests['status'] == 'passed' and source_tests['file_hashes'] == freeze['file_hashes']
    directory = LOCAL / ('candidate-' + args.run)
    wheel_dir = directory / 'product-wheel'
    wheel_dir.mkdir(parents=True)
    builder = runpy.run_path(str(ROOT / 'product/offline/build.py'))
    generated = ROOT / 'product/build'
    builder['INSTALLER']['no_reparse'](generated)
    assert generated.resolve() == (ROOT / 'product/build').absolute()
    if generated.exists():
        shutil.rmtree(generated)
    call(out, 'wheel', [sys.executable, '-I', '-B', '-m', 'pip', 'wheel', '--no-index', '--no-deps',
        '--no-build-isolation', '--wheel-dir', wheel_dir, ROOT / 'product'])
    wheels = list(wheel_dir.glob('*.whl'))
    assert len(wheels) == 1
    wheel = wheels[0]
    payload = builder['validate_product_wheel'](wheel, VERSION,
        (ROOT / 'product/pyproject.toml').read_text(encoding='utf-8'), SOURCE, 'sha256:' + sha(wheel))
    bundle = directory / 'bundle'
    built = json.loads(call(out, 'bundle', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
        ROOT / 'product/offline/build.py', '--output', bundle, '--product-wheel', wheel,
        '--product-wheel-sha256', 'sha256:' + sha(wheel)]))
    installed = directory / 'installed'
    receipt = json.loads(call(out, 'install', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
        bundle / 'install.py', '--bundle', bundle, '--target', installed,
        '--manifest-sha256', built['manifest_sha256'], '--timeout-seconds', '600']))
    assert receipt['ok']
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', installed / 'run.py']
    call(out, 'version', [*prefix, 'version'], cli=True)
    expected = {p.name: sha(p) for p in SOURCE.glob('*.py')}
    assert expected == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    unchanged(freeze)
    save(out / 'verification.json', dict(status='installed-and-byte-verified', cli_version=VERSION,
        release=RELEASE, installed=str(installed), archive=built['archive'],
        archive_sha256=sha(built['archive']), manifest_sha256=built['manifest_sha256'], payload=payload,
        application_files=expected, source_fallback=False, formal_activation=False))


def stage(args, freeze):
    out = proof('skill-entry', args.run)
    candidate = load(BASE / ('candidate-' + args.candidate_run) / 'verification.json')
    installed = Path(candidate['installed'])
    home = LOCAL / ('stage-' + args.run)
    home.mkdir()
    folder = home / 'skills/agent-ffmpeg-local-editor'
    manifest = copy.deepcopy(load(ROOT / 'agent-ffmpeg-local-install-manifest.json'))
    for row in manifest['files']:
        target = home / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / row['path']).read_bytes())
    entry = folder / 'SKILL.md'
    text = entry.read_text(encoding='utf-8')
    text = text.replace('`v0.1.0-alpha.4-local.61` / CLI `0.1.63`', '`' + RELEASE + '` / CLI `' + VERSION + '`')
    text += ('\nFor local CUDA neural music, requests, real audition evidence and limitations, read '
        '[neural music](references/neural-music.md). For verified upgrades, interrupted activation '
        'recovery and rollback, read [delivery](references/delivery.md).\n')
    entry.write_text(text, encoding='utf-8', newline='\n')
    old = (ROOT / 'docs/validation/prepare_music65_skill.py').read_text(encoding='utf-8')
    reference = next(ast.literal_eval(n.value) for n in ast.parse(old).body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'REFERENCE' for t in n.targets))
    (folder / 'references/neural-music.md').write_text(reference.replace('0.1.65', VERSION) +
        '\nHistorical actual CUDA generation was verified on CLI65. Confirm the actual CLI66 receipts '
        'before describing new-version inference as accepted.\n', encoding='utf-8', newline='\n')
    (folder / 'references/delivery.md').write_bytes((ROOT / 'docs/product/DELIVERY_CONTROLLER.md').read_bytes())
    launcher = folder / 'scripts/run.py'
    text = launcher.read_text(encoding='utf-8')
    for key, value in [('MANIFEST', candidate['manifest_sha256']), ('RELEASE', RELEASE)]:
        text, count = re.subn(r'^' + key + r" = '[^']+'$", key + ' = ' + repr(value), text, flags=re.M)
        assert count == 1
    launcher.write_text(text, encoding='utf-8', newline='\n')
    config = copy.deepcopy(load(ROOT / 'local/agent-ffmpeg/runtime.json'))
    config.update(release=RELEASE, installed_directory=str(installed),
                  manifest_sha256=candidate['manifest_sha256'], launcher_sha256=sha(installed / 'run.py'))
    save(home / 'local/agent-ffmpeg/runtime.json', config)
    files = [dict(path=p.relative_to(home).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
             for p in sorted(folder.rglob('*')) if p.is_file()]
    assert len(files) == 95 and len(list((folder / 'references/modules').glob('*/module.md'))) == 17
    manifest.update(release=RELEASE, cli_version=VERSION, manifest_sha256=candidate['manifest_sha256'], files=files)
    manifest['skills'][0]['skill_md_sha256'] = sha(entry)
    save(home / 'agent-ffmpeg-local-install-manifest.json', manifest)
    validator = Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    call(out, 'frontmatter', [sys.executable, '-E', '-B', '-X', 'utf8', validator, folder])
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', folder / 'scripts/run.ps1']
    call(out, 'version', [*prefix, 'version'], cli=True)
    call(out, 'delivery-help', [*prefix, 'delivery', '--help'])
    unchanged(freeze)
    save(out / 'verification.json', dict(status='passed', cli_version=VERSION, home=str(home),
        actual_PowerShell_entry=True, source_fallback=False, files=files, formal_activation=False,
        natural_quality_accepted=False, model_forwards=0))


def package(args, freeze):
    out = proof('package-replay', args.run)
    candidate = load(BASE / ('candidate-' + args.candidate_run) / 'verification.json')
    installed = Path(candidate['installed'])
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', installed / 'run.py']
    sys.path.insert(0, str(installed / 'site'))
    from ai_ad_editor.media import ffmpeg_path
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    historical = load(ROOT / 'docs/validation/evidence/music-loading-20261030-r1/actual-stage1/verification.json')
    assert historical['status'] == 'passed'
    source = Path(historical['artifacts']['project'])
    work = LOCAL / ('package-' + args.run)
    work.mkdir()
    original = work / 'original'
    shutil.copytree(source, original)
    project = load(original / 'project.json')
    # Explicit preview-sized replay; the original project/audio are preserved.
    project['settings']['canvas'].update(width=320, height=568)
    save(original / 'project.json', project)
    archive, restored = work / 'music.aevpkg.zip', work / 'restored'
    call(out, 'export', [*prefix, 'convert', 'export', '--project', original,
        '--target-format', 'agent-package', '--output', archive], cli=True)
    call(out, 'import', [*prefix, 'convert', 'import', '--input', archive, '--output', restored], cli=True)
    asset_id = historical['asset']['id']
    assets = [next(a for a in load(root / 'project.json')['assets'] if a['id'] == asset_id)
              for root in (original, restored)]
    assert assets[0]['source']['music_generation'] == assets[1]['source']['music_generation'] == historical['asset']['source']['music_generation']
    assert sha(original / assets[0]['uri']) == sha(restored / assets[1]['uri']) == sha(historical['artifacts']['wav'])
    decoded = {}
    for label, root in (('original', original), ('restored', restored)):
        movie = root / 'renders/music.mp4'
        call(out, label + '-render', [*prefix, 'render', '--project', root, '--output', movie], cli=True)
        for kind, options in [('RGBA', ['-map', '0:v:0', '-an', '-pix_fmt', 'rgba']),
                              ('PCM', ['-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le'])]:
            data = call(out, label + '-' + kind, [ffmpeg_path(), '-nostdin', '-v', 'error',
                '-i', movie, *options, '-f', 'hash', '-hash', 'sha256', 'pipe:1'])
            decoded[label + '_' + kind] = data.decode().strip()
    assert decoded['original_RGBA'] == decoded['restored_RGBA']
    assert decoded['original_PCM'] == decoded['restored_PCM']
    unchanged(freeze)
    save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
        complete_master_WAV_equal=True, complete_generation_recipe_equal=True,
        complete_rendered_RGBA_PCM_equal=True, decoded=decoded, historical_generation_cli='0.1.65',
        new_model_forwards=0, human_listening=False, natural_quality_accepted=False,
        media_published=False, preview_canvas=[320, 568], project_package=str(archive)))


def descriptor(args, freeze):
    out = proof('descriptor', args.run)
    candidate = load(BASE / ('candidate-' + args.candidate_run) / 'verification.json')
    staged = load(BASE / ('skill-entry-' + args.stage_run) / 'verification.json')
    home = Path(staged['home'])
    roles = {'source-tests': BASE / ('source-all-' + args.tests_run) / 'verification.json',
        'installed-tests': BASE / ('installed-all-' + args.tests_run) / 'verification.json',
        'package-replay': BASE / ('package-replay-' + args.package_run) / 'verification.json',
        'skill-entry': BASE / ('skill-entry-' + args.stage_run) / 'verification.json'}
    gates = {role: dict(path=str(path), sha256=sha(path)) for role, path in roles.items()}
    paths = [*staged['files'], {'path': 'agent-ffmpeg-local-install-manifest.json'},
             {'path': 'local/agent-ffmpeg/runtime.json'}]
    rows = [dict(path=row['path'], source=str(home / row['path']), bytes=(home / row['path']).stat().st_size,
                 sha256=sha(home / row['path'])) for row in paths]
    sys.path.insert(0, str(SOURCE.parent))
    from ai_ad_editor.delivery import FORMAT, inventory, verify
    spec = dict(format=FORMAT, cli_version=VERSION, release=RELEASE, expected_current=inventory(ROOT),
        files=rows, application_files=candidate['application_files'], gates=gates,
        archive=dict(path=candidate['archive'], sha256=candidate['archive_sha256']))
    path = home / 'delivery.json'
    save(path, spec)
    verify(ROOT, path)
    unchanged(freeze)
    save(out / 'verification.json', dict(status='passed', cli_version=VERSION, descriptor=str(path),
        descriptor_sha256=sha(path), formal_activation=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('freeze', 'tests', 'build', 'stage', 'package', 'descriptor'))
    parser.add_argument('--run', required=True)
    parser.add_argument('--freeze-run', default='r1')
    parser.add_argument('--tests-run', default='r1')
    parser.add_argument('--candidate-run', default='r1')
    parser.add_argument('--stage-run', default='r1')
    parser.add_argument('--package-run', default='r1')
    parser.add_argument('--installed', type=Path)
    args = parser.parse_args()
    assert sys.dont_write_bytecode and all(x.isalnum() for x in (args.run, args.freeze_run,
        args.tests_run, args.candidate_run, args.stage_run, args.package_run))
    LOCAL.mkdir(parents=True, exist_ok=True)
    if args.action == 'freeze':
        return freeze_code(args)
    freeze = load(BASE / ('freeze-' + args.freeze_run) / 'verification.json')
    unchanged(freeze)
    if args.action == 'tests':
        return test_all(args, freeze)
    return {'build': build, 'stage': stage, 'package': package, 'descriptor': descriptor}[args.action](args, freeze)


if __name__ == '__main__':
    raise SystemExit(main())
