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
    paths = [*[path for path in SOURCE.rglob('*') if path.is_file() and path.suffix.lower() in {'.py', '.mjs', '.json', '.c', '.dll', '.txt', '.cube'}],
             ROOT / 'docs/specs/agent-project.schema.json', *(ROOT / 'product/tests').glob('*.py'),
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
    assert all(sha(ROOT / name) == pin for name, pin in freeze.get('delivery_tool_files', {}).items()), 'Frozen delivery tools changed'


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


class LiveRegressionResult(unittest.TextTestResult):
    """Persist errors as they occur while preserving unittest's full result."""
    def __init__(self, *args, event_path, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_path = Path(event_path)
        with self.event_path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(dict(event='result-created')) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def issue(self, kind, test, err):
        row = dict(event=kind, test_id=test.id(), tests_started=self.testsRun,
                   traceback=self._exc_info_to_string(err, test))
        with self.event_path.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def addError(self, test, err):
        super().addError(test, err)
        self.issue('error', test, err)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.issue('failure', test, err)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            kind = 'failure' if issubclass(err[0], test.failureException) else 'error'
            self.issue('subtest-' + kind, subtest, err)


NATIVE_TEST_IMPORTS = r'''
import importlib.metadata, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import ai_ad_editor
import cv2
import numpy
import PIL
import jsonschema
modules = {}
for name, module, distribution in [('numpy', numpy, 'numpy'), ('PIL', PIL, 'Pillow'),
                                  ('cv2', cv2, None), ('jsonschema', jsonschema, 'jsonschema')]:
    directory = Path(module.__file__).resolve().parent
    binaries = sorted(directory.glob('*.pyd'))
    if name == 'numpy':
        binaries += sorted((directory / '_core').glob('*.pyd'))
        binaries += sorted((directory.parent / 'numpy.libs').glob('*.dll'))
    if name == 'PIL':
        binaries += sorted((directory.parent / 'pillow.libs').glob('*.dll'))
    version = importlib.metadata.version(distribution) if distribution else module.__version__
    modules[name] = dict(version=version, file=str(Path(module.__file__).resolve()),
                         binaries=[str(path.resolve()) for path in binaries])
print(json.dumps(dict(python=sys.executable, isolated=sys.flags.isolated,
    application_file=str(Path(ai_ad_editor.__file__).resolve()),
    application_version=ai_ad_editor.VERSION, modules=modules)))
'''


def dependency_probe_files(record, package):
    """Reject unavailable isolated-worker imports before starting the full suite."""
    assert record.get('isolated') == 1, 'Native dependency probe was not isolated'
    assert Path(record['python']).resolve() == Path(sys.executable).resolve(), 'Native dependency probe used another Python'
    assert (record.get('application_version') == VERSION
            and Path(record['application_file']).resolve() == package / '__init__.py'), 'Native dependency probe imported another application'
    modules = record.get('modules')
    assert isinstance(modules, dict) and set(modules) == {'numpy', 'PIL', 'cv2', 'jsonschema'}, 'Native isolated dependencies are incomplete'
    bounds = {'numpy': ((2, 4, 2), (3,)), 'PIL': ((12, 1), (13,)),
              'jsonschema': ((4, 26), (5,)), 'cv2': ((4,), (6,))}
    files = {str(Path(sys.executable).resolve()): sha(sys.executable)}
    for name, row in modules.items():
        assert isinstance(row, dict) and isinstance(row.get('version'), str), 'Native dependency version is missing'
        match = re.fullmatch(r'(\d+(?:\.\d+){1,3})', row['version'])
        assert match is not None, 'Unrecognized native dependency version: ' + name
        version = tuple(map(int, match[1].split('.')))
        minimum, maximum = bounds[name]
        assert minimum <= version < maximum, 'Incompatible native dependency version: ' + name
        assert isinstance(row.get('binaries'), list), 'Native dependency binary inventory is missing'
        paths = [row['file'], *row['binaries']]
        assert len(paths) <= 128 and all(isinstance(path, str) for path in paths), 'Native dependency inventory exceeds its budget'
        for name in paths:
            path = Path(name).resolve(strict=True)
            assert path.is_file(), 'Native dependency is not an ordinary file'
            files[str(path)] = sha(path)
    return files


def freeze_code(args):
    out = proof('freeze', args.run)
    for name in pins():
        if name.endswith('.py'):
            compile((ROOT / name).read_bytes(), name, 'exec')
    tool_names = ('delivery66.py', 'run_delivery66_native.py', 'delivery66_handoff.py',
                  'delivery66_music_faults.py', 'publish_delivery66.py', 'test_delivery66_handoff.py')
    tools = {}
    for name in tool_names:
        path = ROOT / 'docs/validation' / name
        compile(path.read_bytes(), str(path), 'exec')
        tools[path.relative_to(ROOT).as_posix()] = sha(path)
    # The third-party DF3 NotImplemented branches guard invalid enum values;
    # its three declared configurations already have implementations.
    save(out / 'verification.json', dict(status='frozen', cli_version=VERSION, file_hashes=pins(),
        formal_guard=formal_guard(), delivery_tool_files=tools,
        implementation_units=['T01', 'T02', 'T03', 'T04', 'T05', 'T06', 'H01', 'H02', 'H03', 'H04', 'H05', 'H06', 'H07'],
        code_completed_before_tests=True, functional_tests_started=False, model_forwards=0))
    print('All delivery66 code frozen before functional tests.', flush=True)


def configure_test_dependencies(args, out, package):
    # -I synthetic workers cannot see the controller's per-user site packages.
    # Check their actual native imports, including OpenCV, before discovery.
    probe = json.loads(call(out, 'native-isolated-imports',
        [sys.executable, '-I', '-B', '-u', '-X', 'utf8', '-c', NATIVE_TEST_IMPORTS,
         str(package.parent)], timeout=180))
    expected = dependency_probe_files(probe, package)
    save(out / 'native-isolated-dependencies.json', dict(status='ready', **probe,
        files=expected, model_forwards=0, test_methods_executed=0))
    binary = args.rubberband.resolve(strict=True)
    audio = [binary, binary.with_name('COPYING.txt'), binary.with_name('sndfile.dll')]
    assert all(path.is_file() for path in audio), 'Existing native Rubber Band binary, DLL and license required'
    configuration_path = args.html_runtime.resolve(strict=True)
    configuration = load(configuration_path)
    from ai_ad_editor.html_motion import prepare_runtime
    from ai_ad_editor.media import ffmpeg_path
    runtime = prepare_runtime(ROOT, configuration)
    node = Path(configuration['node']).resolve(strict=True)
    chromium = Path(configuration['chromium']).resolve(strict=True)
    playwright = Path(configuration['playwright']).resolve(strict=True)
    assert node.is_file() and chromium.is_file() and (playwright / 'package.json').is_file()
    os.environ.update(AI_AD_EDITOR_TEST_RUBBERBAND=str(binary),
        AI_AD_EDITOR_TEST_HTML_RUNTIME=str(configuration_path),
        AI_AD_EDITOR_TEST_PACKAGE_ROOT=str(package.parent), PYTHONPATH=str(package.parent))
    os.environ['PATH'] = os.pathsep.join(map(str, (node.parent, binary.parent,
        Path(ffmpeg_path()).parent))) + os.pathsep + os.environ.get('PATH', '')
    files = [*audio, configuration_path, node, chromium, playwright / 'package.json']
    expected.update({str(path): sha(path) for path in files})
    call(out, 'native-audio-version', [binary, '--version'])
    call(out, 'native-node-version', [node, '--version'])
    record = dict(status='ready', files=expected, html_runtime=runtime,
        browser_launched_by_preflight=False, model_forwards=0, virtualization=False,
        installed_test_import_root=str(package.parent), original_assertions_preserved=True)
    save(out / 'native-dependencies.json', record)
    return expected


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
    dependencies = configure_test_dependencies(args, out, package)
    # Preserve all existing tests, load_tests filters, deadlines and failures.
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'product/tests'), pattern='test_*.py')
    count = suite.countTestCases()
    print(json.dumps(dict(phase=mode, discovered_tests=count)), flush=True)
    began = time.monotonic()
    event_path = out / 'issues.jsonl'
    with (out / 'tests.stderr').open('w', encoding='utf-8', newline='\n') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2,
            resultclass=lambda *a, **kw: LiveRegressionResult(*a, event_path=event_path, **kw)).run(suite)
    unchanged(freeze)
    assert expected == {p.name: sha(p) for p in package.glob('*.py')}
    assert all(sha(Path(name)) == pin for name, pin in dependencies.items())
    report = dict(status='passed' if result.wasSuccessful() and not result.skipped else 'failed',
        cli_version=VERSION, tests=result.testsRun, discovered_tests=count, failures=len(result.failures),
        errors=len(result.errors), skipped=len(result.skipped), frozen_equal=True, file_hashes=freeze['file_hashes'],
        source_fallback=False if args.installed else None, installed=str(args.installed) if args.installed else None,
        loaded_package=str(package), elapsed_seconds=time.monotonic() - began,
        native_dependency_files=dependencies, test_package_bindings='explicit-loaded-package',
        issue_journal=dict(path=str(event_path), sha256=sha(event_path)),
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
        'before describing new-version inference as accepted. CLI66 reports concurrent output occupation as '
        '`MUSIC_GENERATION_OUTPUT_CONFLICT` and other filesystem failures as `MUSIC_GENERATION_IO_FAILED`; '
        'inspect the transaction outcome, preserve foreign files and use a fresh asset ID for a deliberate retry.\n', encoding='utf-8', newline='\n')
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
    capabilities = call(out, 'capabilities', [*prefix, 'capabilities'], cli=True)
    assert capabilities['data']['capabilities']['verified_skill_delivery']['protocol'] == 'agent-editor-skill-delivery-v2'
    unchanged(freeze)
    save(out / 'verification.json', dict(status='passed', cli_version=VERSION, home=str(home),
        actual_PowerShell_entry=True, source_fallback=False, files=files, formal_activation=False,
        application_files=candidate['application_files'], skill_files={row['path']: row['sha256'] for row in files},
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
    historical = load(BASE / ('native-music-' + args.music_run) / 'verification.json')
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
        '--target-format', 'package', '--output', archive], cli=True)
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
        application_files=candidate['application_files'], complete_master_WAV_equal=True, complete_generation_recipe_equal=True,
        complete_rendered_RGBA_PCM_equal=True, decoded=decoded, generation_cli=VERSION,
        new_model_forwards=0, human_listening=False, natural_quality_accepted=False,
        media_published=False, preview_canvas=[320, 568], project_package=str(archive)))


def music(args, freeze):
    out = proof('native-music', args.run)
    candidate = load(BASE / ('candidate-' + args.candidate_run) / 'verification.json')
    stage_report = load(BASE / ('skill-entry-' + args.stage_run) / 'verification.json')
    for mode in ('source-all', 'installed-all'):
        report = load(BASE / (mode + '-' + args.tests_run) / 'verification.json')
        assert report['status'] == 'passed' and report['file_hashes'] == freeze['file_hashes']
    installed = Path(candidate['installed'])
    sys.path.insert(0, str(installed / 'site'))
    import ai_ad_editor
    from ai_ad_editor.media import ffmpeg_path
    from ai_ad_editor.runtime import configure_local_runtime
    assert Path(ai_ad_editor.__file__).resolve() == installed / 'site/ai_ad_editor/__init__.py'
    assert ai_ad_editor.VERSION == VERSION
    configure_local_runtime()
    expected = {p.name: sha(p) for p in SOURCE.glob('*.py')}
    assert candidate['application_files'] == expected
    assert expected == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    home = Path(stage_report['home'])
    skill_files = {row['path']: row['sha256'] for row in stage_report['files']}
    assert all(sha(home / name) == pin for name, pin in skill_files.items())
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
              home / 'skills/agent-ffmpeg-local-editor/scripts/run.ps1']
    interface_path = ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1/native-interface-r6/verification.json'
    interface = load(interface_path)
    assert interface['status'] == 'passed'
    readers = [load(path) for path in (ROOT / 'docs/validation/evidence/music-loading-20261030-r1').glob('native-reader-*/verification.json')]
    reader = next(value for value in readers if value.get('status') == 'passed'
        and value.get('actual_BF16_tensor_values_equal') is True
        and value.get('model_helper_sha256') == sha(SOURCE / 'music_generation_model.py')
        and Path(value['executable']).resolve() == Path(interface['executable']).resolve())
    notices = ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1/notices-r2/verification.json'
    assert load(notices)['status'] == 'passed'
    work = LOCAL / ('music-' + args.run)
    work.mkdir()
    project = work / 'project'
    try:
        call(out, 'version', [*prefix, 'version'], cli=True)
        call(out, 'init', [*prefix, 'project', 'init', project], cli=True)
        adapter = call(out, 'register', [*prefix, 'music', 'generator-adapter', 'register',
            '--project', project, '--adapter-id', 'ace15', '--model-path',
            ROOT / 'product/.runtime/models/acestep15-20261029', '--runtime-root', interface['runtime_root'],
            '--executable', interface['executable'], '--evidence', notices,
            '--creator', 'ACE-Step / Comfy-Org; existing native ComfyUI core',
            '--license-spdx', 'Apache-2.0 AND GPL-3.0-only', '--license-url',
            notices.parent / 'Apache-2.0.txt', '--threads', '4'], cli=True)['data']
        request = work / 'request.json'
        save(request, dict(format='agent-neural-music-v1',
            prompt='Intimate acoustic piano instrumental, gentle melodic phrases, warm upright bass, soft brushed drums, elegant quiet evening atmosphere, original chamber jazz, clean studio recording.',
            lyrics='', instrumental=True, duration_seconds=10, bpm=90, language='unknown',
            keyscale='D minor', timesignature=4, seed=20261030, steps=8, generate_audio_codes=True))
        inspected = call(out, 'inspect', [*prefix, 'music', 'inspect-generation', '--input', request], cli=True)['data']
        assert inspected['samples'] == 480000
        before = {name: sha(project / name) for name in ('project.json', 'rights-ledger.json')}
        call(out, 'dry-run', [*prefix, 'music', 'generate', '--project', project, '--adapter-id', 'ace15',
            '--input', request, '--new-asset-id', 'piano66', '--apply', '--track-id', 'track_audio_1', '--dry-run'], cli=True)
        assert all(sha(project / name) == pin for name, pin in before.items())
        result = call(out, 'generate', [*prefix, 'music', 'generate', '--project', project, '--adapter-id', 'ace15',
            '--input', request, '--new-asset-id', 'piano66', '--apply', '--track-id', 'track_audio_1',
            '--timeout-seconds', '3600'], timeout=4800, cli=True)['data']
        run, model = result['generation'], result['generation']['worker']['model']
        assert model['neural_backend'] == 'cuda' and model['dynamic_vram'] is False
        assert set(model['forwards']) == {'text', 'language_model', 'diffusion', 'vae'}
        assert all(type(value) is int and value > 0 for value in model['forwards'].values())
        assert all(model['forward_output_devices'][name] == ['cuda:0'] for name in model['forwards'])
        assert run['worker']['samples'] == 480000 and run['complete_PCM_roundtrip_verified'] is True
        assert run['cleanup']['worker_exited'] is True and run['cleanup']['owner_job_closed'] is True
        assert result['clip']['asset_id'] == 'piano66'
        audio = project / result['asset']['uri']
        assert result['asset']['sha256'] == 'sha256:' + sha(audio)
        pcm = call(out, 'independent-full-PCM', [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', audio,
            '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'hash', '-hash', 'sha256', 'pipe:1'])
        independent_pcm = 'sha256:' + pcm.decode().strip().split('=', 1)[1].lower()
        assert independent_pcm == run['worker']['output_PCM_sha256']
        saved = load(project / 'project.json')
        assert any(value['id'] == 'piano66' and value['sha256'] == result['asset']['sha256'] for value in saved['assets'])
        def objects(value):
            if isinstance(value, dict):
                yield value
                for child in value.values():
                    yield from objects(child)
            elif isinstance(value, list):
                for child in value:
                    yield from objects(child)
        assert any(value.get('id') == result['clip']['id'] and value.get('asset_id') == 'piano66'
                   for value in objects(saved['sequences']))
        assert result['rights']['verification_status'] == 'unverified' and result['rights']['permitted_uses'] == ['internal']
        assert all(sha(home / name) == pin for name, pin in skill_files.items())
        assert expected == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
        unchanged(freeze)
        def pin(path):
            return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))
        save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
            actual_PowerShell_entry=True, actual_CUDA_music=True, source_fallback=False,
            complete_PCM_verified=True, project_placement_verified=True, owned_process_cleanup_verified=True,
            application_files=expected, skill_files=skill_files, master_audio=pin(audio), request_file=pin(request),
            independent_PCM_sha256=independent_pcm, project_manifest=pin(project / 'project.json'),
            actual_generation=run, asset=result['asset'], rights=result['rights'], clip=result['clip'],
            adapter_sha256=adapter['adapter']['sha256'], interface_sha256=sha(interface_path),
            artifacts=dict(project=str(project), wav=str(audio), request=str(request)),
            human_listening=False, natural_quality_accepted=False, generated_audio_publication_approved=False,
            formal_activation=False, full_product_goal_closed=False))
    except BaseException as exc:
        save(out / 'verification.json', dict(status='failed', cli_version=VERSION,
            error=repr(exc), actual_PowerShell_entry=True, formal_activation=False))
        raise


def descriptor(args, freeze):
    out = proof('descriptor', args.run)
    candidate = load(BASE / ('candidate-' + args.candidate_run) / 'verification.json')
    staged = load(BASE / ('skill-entry-' + args.stage_run) / 'verification.json')
    home = Path(staged['home'])
    roles = {'source-tests': BASE / ('source-all-' + args.tests_run) / 'verification.json',
        'installed-tests': BASE / ('installed-all-' + args.tests_run) / 'verification.json',
        'package-replay': BASE / ('package-replay-' + args.package_run) / 'verification.json',
        'skill-entry': BASE / ('skill-entry-' + args.stage_run) / 'verification.json',
        'native-music': BASE / ('native-music-' + args.music_run) / 'verification.json'}
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
    parser.add_argument('action', choices=('freeze', 'tests', 'build', 'stage', 'music', 'package', 'descriptor'))
    parser.add_argument('--run', required=True)
    parser.add_argument('--freeze-run', default='r4')
    parser.add_argument('--tests-run', default='r4')
    parser.add_argument('--candidate-run', default='r1')
    parser.add_argument('--stage-run', default='r1')
    parser.add_argument('--package-run', default='r1')
    parser.add_argument('--music-run', default='r1')
    parser.add_argument('--installed', type=Path)
    parser.add_argument('--rubberband', type=Path, default=ROOT / 'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe')
    parser.add_argument('--html-runtime', type=Path, default=ROOT / 'product/.runtime/html-motion-runtime-20261018-e2.json')
    args = parser.parse_args()
    assert sys.dont_write_bytecode and all(x.isalnum() for x in (args.run, args.freeze_run,
        args.tests_run, args.candidate_run, args.stage_run, args.package_run, args.music_run))
    assert (ROOT / 'product/src/ai_ad_editor').is_dir(), 'Apply the complete candidate before running the round tool'
    LOCAL.mkdir(parents=True, exist_ok=True)
    if args.action == 'freeze':
        return freeze_code(args)
    freeze = load(BASE / ('freeze-' + args.freeze_run) / 'verification.json')
    unchanged(freeze)
    if args.action == 'tests':
        return test_all(args, freeze)
    return {'build': build, 'stage': stage, 'music': music, 'package': package, 'descriptor': descriptor}[args.action](args, freeze)


if __name__ == '__main__':
    raise SystemExit(main())
