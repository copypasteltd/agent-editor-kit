"""Build and publish the first stable distribution of the accepted CLI66 engine.

Distribution v1.0.0 is deliberately independent of the existing engine build
identifier 0.1.66. Unaccepted working-copy changes never enter the distribution.
All stage receipts distinguish historical engine tests from this release's runs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'local/agent-ffmpeg/release-v1-20261107'
EVIDENCE = ROOT / 'docs/validation/evidence/release-v1-20261107'
TAG, VERSION, REVISION = 'v1.0.0', '0.1.66', 'r60'
GIT = Path('C:/Program Files/Git/mingw64/bin/git.exe')
PYTHON = Path('C:/Python313/python.exe')
REPO = 'copypasteltd/agent-editor-kit'
SKILL = 'skills/agent-ffmpeg-local-editor'
README_NAMES = ('README.md', 'README.zh-TW.md', 'README.en.md')
OLD_LOCK = ROOT / 'local/agent-ffmpeg/delivery66-handoff/release-assets-r1/release-lock.json'
OLD_LOCK_SHA = '8b16bbf8e4047cc9a255644a8aa50fe267deb6aa1f65035a3237ae976e5d0bbd'
ENV = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never',
           PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    pending.write_bytes(encoded(value))
    os.replace(pending, path)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    item = importlib.util.module_from_spec(spec)
    sys.modules[name] = item
    spec.loader.exec_module(item)
    return item


def git(*args, data=None):
    result = subprocess.run([str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *map(str, args)], input=data,
        cwd=ROOT, env=ENV, capture_output=True, timeout=180,
        creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('Git operation failed: ' + str(args[:2]))
    return result.stdout


def call(out, name, command, *, expected=0, json_result=False, timeout=1200, cwd=ROOT):
    out.mkdir(parents=True, exist_ok=True)
    temporary = WORK / 'temp'
    temporary.mkdir(parents=True, exist_ok=True)
    env = dict(ENV, TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
    began = time.monotonic()
    with (out / (name + '.stdout')).open('xb') as stdout, (out / (name + '.stderr')).open('xb') as stderr:
        process = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
            stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW)
    save(out / (name + '.exit.json'), dict(exit_code=process.returncode,
        elapsed_seconds=time.monotonic() - began, expected_exit_code=expected))
    assert process.returncode == expected, name + ': unexpected exit; inspect retained logs'
    raw = (out / (name + '.stdout')).read_bytes()
    result = json.loads(raw) if json_result else raw
    if json_result and expected == 0 and 'ok' in result:
        assert result['ok'], name + ': command did not succeed'
    return result


def member(name):
    assert isinstance(name, str) and name and '\\' not in name and ':' not in name
    assert not name.startswith('/') and all(p not in ('', '.', '..') for p in name.split('/'))
    return name


def extract(archive, target):
    assert not target.exists(), 'Preserve earlier installations and evidence'
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        assert len(names) == len(set(names))
        assert sum(row.file_size for row in zipped.infolist()) < 2 * 1024**3
        for row in zipped.infolist():
            if row.is_dir():
                continue
            member(row.filename)
            assert ((row.external_attr >> 16) & 0o170000) != 0o120000
            path = target / row.filename
            path.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(row) as source, path.open('xb') as stream:
                shutil.copyfileobj(source, stream)


def inventory(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def checked_history():
    assert sha(OLD_LOCK) == OLD_LOCK_SHA
    old = load(OLD_LOCK)
    for kind in ('source-all-r6', 'installed-all-r6'):
        report = load(ROOT / 'docs/validation/evidence/delivery66-20261106-r1' / kind / 'verification.json')
        assert report['status'] == 'passed' and report['tests'] == 4124
        assert report['failures'] == report['errors'] == report['skipped'] == 0
    return old


def prepare():
    assert not (WORK / 'source').exists()
    WORK.mkdir(parents=True, exist_ok=True)
    old = checked_history()
    parent = git('rev-parse', 'HEAD').decode().strip()
    assert git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert git('remote', 'get-url', '--push', 'origin').decode().strip() == 'git@github.com:' + REPO + '.git'
    stage = WORK / 'source'
    selected = set(old['frozen_source']) | set(old['source_binding']['groups']['packaging'])
    selected |= set(old['source_binding']['groups']['skill'])
    selected |= {'scripts/package_community_skill.py', 'scripts/activate_community_runtime.py',
                 'agent-ffmpeg-local-install-manifest.json'}
    # Export only the frozen build inputs. The broad product tree also carries
    # historical test recordings; they do not belong in a build staging copy.
    for record in git('ls-tree', '-z', parent + ':product').split(b'\0'):
        if record:
            header, name = record.split(b'\t', 1)
            if header.split()[1] == b'blob':
                selected.add('product/' + name.decode('utf-8'))
    # Git archive reads the accepted main commit, never the unaccepted CLI67 worktree.
    # Feed long path lists through stdin, below Windows CreateProcess limits.
    selected = sorted(selected)
    raw = git('cat-file', '--batch', data=''.join(parent + ':' + name + '\n' for name in selected).encode('utf-8'))
    offset = 0
    stage.mkdir()
    for name in selected:
        boundary = raw.index(b'\n', offset)
        header = raw[offset:boundary].split()
        assert len(header) == 3 and header[1] == b'blob', 'Missing reviewed source: ' + name
        size = int(header[2])
        offset = boundary + 1
        target = stage / member(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw[offset:offset + size])
        offset += size
        assert raw[offset:offset + 1] == b'\n'
        offset += 1
    assert offset == len(raw)
    original = load(ROOT / 'docs/validation/evidence/delivery66-20261106-r1/candidate-r1/verification.json')
    installed = Path(original['installed']) / 'site/ai_ad_editor'
    # Restore the exact accepted package bytes, including native cores and LUTs.
    for relative, pin in inventory(installed).items():
        destination = stage / 'product/src/ai_ad_editor' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, destination)
        assert sha(destination) == pin
    # Reconstitute the original Windows line endings from the accepted freeze.
    for name, pin in old['frozen_source'].items():
        path = stage / name
        assert path.is_file(), name
        if sha(path) != pin:
            actual = path.read_bytes()
            candidates = (actual.replace(b'\r\n', b'\n'), actual.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
            chosen = next((raw for raw in candidates if hashlib.sha256(raw).hexdigest() == pin), None)
            assert chosen is not None, 'Accepted source mismatch: ' + name
            path.write_bytes(chosen)
    assert all(sha(stage / name) == pin for name, pin in old['frozen_source'].items())
    for name in README_NAMES:
        path = WORK / 'readmes-before' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    save(WORK / 'before.json', dict(parent=parent, engine_version=VERSION,
        distribution=TAG, source_origin='accepted-main-and-exact-installed-payload',
        historical_source_tests=4124, historical_installed_tests=4124,
        historical_tests_newly_executed=False, accepted_product_pins=old['frozen_source'],
        application_payload=inventory(installed), source_worktree_version='0.1.67',
        source_worktree_modified=False, formal_config=load(ROOT / 'local/agent-ffmpeg/runtime.json'),
        formal_skill_inventory=load(ROOT / 'agent-ffmpeg-local-install-manifest.json'),
        working_copy_python={p.relative_to(ROOT).as_posix(): sha(p)
            for folder in (ROOT / 'product/src/ai_ad_editor', ROOT / 'product/tests')
            for p in folder.glob('*.py')},
        paused_batches_resumed=False))
    print(json.dumps(dict(status='prepared', parent=parent, frozen_files=len(old['frozen_source']),
        package_files=len(inventory(installed))), ensure_ascii=False), flush=True)


def build():
    before = load(WORK / 'before.json')
    stage = WORK / 'source'
    out = EVIDENCE / 'build-r1'
    assert not out.exists()
    assert all(sha(stage / name) == pin for name, pin in before['accepted_product_pins'].items())
    wheels = WORK / 'product-wheel'
    wheels.mkdir()
    call(out, 'wheel', [PYTHON, '-I', '-B', '-X', 'utf8', '-m', 'pip', 'wheel',
        '--no-index', '--no-deps', '--no-build-isolation', '--wheel-dir', wheels, stage / 'product'])
    wheel, = wheels.glob('*.whl')
    bundle = WORK / 'application-bundle'
    result = call(out, 'bundle', [PYTHON, '-I', '-B', '-u', '-X', 'utf8', stage / 'product/offline/build.py',
        '--output', bundle, '--wheelhouse', ROOT / 'sources/python-runtime/cp313-win_amd64-media',
        '--product-wheel', wheel, '--product-wheel-sha256', 'sha256:' + sha(wheel)], json_result=True)
    # v1.0.0 is the distribution contract; CLI66 remains the accepted engine identifier.
    release = dict(format='agent-editor-kit-distribution-v1', distribution_version=TAG,
        engine_cli_version=VERSION, skill_revision=REVISION,
        baseline_source_commit=before['parent'], application_payload=before['application_payload'],
        historical_acceptance=dict(source_tests=4124, installed_tests=4124,
            newly_executed_in_stable_release=False), candidate_CLI67_included=False,
        candidate_typography_included=False, python_included=False, ffmpeg_included=False,
        model_weights_included=False, whole_CapCut_parity=False)
    save(bundle / 'DISTRIBUTION.json', release)
    manifest = load(bundle / 'manifest.json')
    manifest['distribution_version'] = TAG
    manifest['engine_cli_version'] = VERSION
    manifest['files'].append(dict(path='DISTRIBUTION.json', bytes=(bundle / 'DISTRIBUTION.json').stat().st_size,
                                  sha256='sha256:' + sha(bundle / 'DISTRIBUTION.json')))
    save(bundle / 'manifest.json', manifest)
    assets = WORK / 'assets'
    assets.mkdir()
    application = assets / ('agent-editor-kit-' + TAG + '-cp313-win_amd64.zip')
    with zipfile.ZipFile(application, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                zipped.write(path, path.relative_to(bundle).as_posix())
    receipt = dict(status='built', distribution_version=TAG, cli_version=VERSION,
        archive=str(application), sha256=sha(application), bytes=application.stat().st_size,
        manifest_sha256='sha256:' + sha(bundle / 'manifest.json'), product_wheel_sha256=sha(wheel),
        accepted_source_byte_equal=True, actual_new_wheel_build=True, actual_new_offline_bundle=True,
        source_worktree_modified=False, application_payload=before['application_payload'])
    save(out / 'verification.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'application_payload'}), flush=True)


def kit():
    built = load(EVIDENCE / 'build-r1/verification.json')
    stage = WORK / 'source'
    folder = stage / SKILL
    entry = folder / 'SKILL.md'
    # Start with the currently accepted 95-file Skill, not an older candidate.
    current = load(WORK / 'before.json')['formal_skill_inventory']
    for row in current['files']:
        target = stage / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / row['path'], target)
    entry.write_text(entry.read_text(encoding='utf-8').replace('`v0.1.0-alpha.4-local.64`', '`v1.0.0`') +
        '\nStable distribution v1.0.0 uses the accepted CLI0.1.66 engine, one public Skill and 17 internal modules. '
        'Read [stable delivery](references/stable-release.md) for installation, customer preview selection, '
        'optional model prerequisites and dated verification boundaries. CLI67 portrait and experimental '
        'typography are excluded from this distribution.\n', encoding='utf-8', newline='\n')
    stable_ref = ROOT / 'docs/releases/v1.0.0/SKILL.md'
    assert stable_ref.exists(), 'Finish the complete documentation batch before packaging'
    (folder / 'references/stable-release.md').write_bytes(stable_ref.read_bytes())
    launcher = folder / 'scripts/run.py'
    text = launcher.read_text(encoding='utf-8')
    for key, value in [('MANIFEST', built['manifest_sha256']), ('RELEASE', TAG)]:
        text, count = re.subn(r'^' + key + r" = '[^']+'$", key + ' = ' + repr(value), text, flags=re.M)
        assert count == 1
    launcher.write_text(text, encoding='utf-8', newline='\n')
    current.update(release=TAG, distribution_version=TAG, cli_version=VERSION,
                   skill_revision=REVISION, manifest_sha256=built['manifest_sha256'])
    current['files'] = [dict(path=p.relative_to(stage).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
                        for p in sorted(folder.rglob('*')) if p.is_file()]
    current['skills'][0]['skill_md_sha256'] = sha(entry)
    save(stage / 'agent-ffmpeg-local-install-manifest.json', current)
    out = EVIDENCE / 'kit-r1'
    call(out, 'package', [PYTHON, '-I', '-B', '-X', 'utf8', stage / 'scripts/package_community_skill.py',
        '--output', stage / 'kit-output', '--archive-name', 'base.zip', '--source-ref', TAG], json_result=True)
    content = {}
    with zipfile.ZipFile(stage / 'kit-output/base.zip') as zipped:
        content = {name: zipped.read(name) for name in zipped.namelist() if name != 'KIT-FILES.json'}
    for path in (ROOT / 'docs/releases/v1.0.0').glob('*.md'):
        content['docs/releases/v1.0.0/' + path.name] = path.read_bytes()
        if path.name.startswith('QUICKSTART'):
            content[path.name] = path.read_bytes()
    # The small toolkit intentionally externalizes public media instead of
    # shipping all original stills/audio/models. Keep included-file links local.
    for name in list(content):
        if not name.endswith('.md') or name.startswith('skills/'):
            continue
        basis = 'docs/releases/v1.0.0/' + name if name.startswith('QUICKSTART') else name
        def externalize(match):
            target = match[2]
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                return match.group()
            plain, mark, fragment = target.partition('#')
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(basis), plain))
            assert not resolved.startswith('../'), 'Documentation link escapes the public repository'
            if resolved in content:
                replacement = posixpath.relpath(resolved, posixpath.dirname(name) or '.')
            else:
                prefix = ('https://raw.githubusercontent.com/' + REPO + '/' + TAG + '/' if match[1].startswith('!')
                          else 'https://github.com/' + REPO + '/blob/' + TAG + '/')
                replacement = prefix + urllib.parse.quote(resolved, safe='/')
            return match[1] + replacement + (mark + fragment if mark else '') + match[3]
        text = re.sub(r'(!?\[[^\]\n]*\]\()([^\s)]+)(\))', externalize, content[name].decode('utf-8'))
        content[name] = text.encode('utf-8')
    inventory_value = dict(format='agent-community-single-skill-v1', release=TAG, cli_version=VERSION,
        skill_revision=REVISION, skill_count=1, module_count=17, documentation_source_ref=TAG,
        files=[dict(path=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
               for name, raw in sorted(content.items())])
    content['KIT-FILES.json'] = encoded(inventory_value)
    archive = WORK / 'assets/agent-editor-kit-v1.0.0-unified-skill-r60.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for name, raw in sorted(content.items()):
            member(name)
            zipped.writestr(name, raw)
    save(out / 'verification.json', dict(status='built-not-yet-installed', distribution_version=TAG,
        cli_version=VERSION, archive=str(archive), sha256=sha(archive), bytes=archive.stat().st_size,
        skill_count=1, module_count=17, skill_files=len(current['files']), source_fallback=False))
    print('Unified Skill r60 built', flush=True)


def accept(label='local-r1', assets=None, *, resume_validation=False):
    assets = assets or WORK / 'assets'
    built = load(EVIDENCE / 'build-r1/verification.json')
    out = EVIDENCE / label
    assert not out.exists() or resume_validation
    directory = WORK / label
    bundle, home, installed = directory / 'application', directory / '工具包 中文 spaces', directory / '已安装 中文 spaces'
    if not resume_validation:
        extract(assets / 'agent-editor-kit-v1.0.0-cp313-win_amd64.zip', bundle)
        extract(assets / 'agent-editor-kit-v1.0.0-unified-skill-r60.zip', home)
    kit_inventory = load(home / 'KIT-FILES.json')
    assert kit_inventory['release'] == TAG and kit_inventory['cli_version'] == VERSION
    assert all(sha(home / row['path']) == row['sha256'] for row in kit_inventory['files'])
    if not resume_validation:
        call(out, 'install', [PYTHON, '-I', '-B', '-u', '-X', 'utf8', bundle / 'install.py', '--bundle', bundle,
            '--target', installed, '--manifest-sha256', built['manifest_sha256'], '--timeout-seconds', '600'], json_result=True)
    else:
        assert load(installed / 'receipt.json')['manifest_sha256'] == built['manifest_sha256']
        assert load(out / 'bad-manifest-rejected.exit.json')['exit_code'] == 2
        for prior in ('install', 'configure', 'register', 'version', 'capabilities', 'doctor', 'schema', 'looks', 'look-inspect', 'voices'):
            assert load(out / (prior + '.exit.json'))['exit_code'] == 0
        with zipfile.ZipFile(assets / 'agent-editor-kit-v1.0.0-unified-skill-r60.zip') as zipped:
            assert load(home / 'KIT-FILES.json') == json.loads(zipped.read('KIT-FILES.json'))
    assert inventory(installed / 'site/ai_ad_editor') == built['application_payload']
    if not resume_validation:
        call(out, 'bad-manifest-rejected', [PYTHON, '-I', '-B', '-X', 'utf8', bundle / 'install.py', '--bundle', bundle,
            '--target', directory / 'must-not-exist', '--manifest-sha256', 'sha256:' + '0' * 64], expected=2)
    assert not (directory / 'must-not-exist').exists()
    if not resume_validation:
        call(out, 'configure', [PYTHON, '-I', '-B', '-X', 'utf8', home / 'scripts/activate_community_runtime.py',
            '--installed', installed, '--base-only'], json_result=True)
    discovery = directory / 'discovery'
    ps = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File']
    if not resume_validation:
        call(out, 'register', [*ps, home / 'register-agent-ffmpeg-local-skills.ps1',
            '-SkillsDirectory', discovery, '-ReceiptPath', out / 'registration.json'])
    entry = discovery / 'agent-ffmpeg-local-editor/scripts/run.ps1'
    prefix = [*ps, entry]
    if not resume_validation:
        for command in ('version', 'capabilities', 'doctor'):
            result = call(out, command, [*prefix, command], json_result=True)
            assert result['provenance']['cli_version'] == VERSION
        call(out, 'schema', [*prefix, 'schema', 'show'], json_result=True)
        call(out, 'looks', [*prefix, 'look', 'list'], json_result=True)
        call(out, 'look-inspect', [*prefix, 'look', 'inspect', '--id', 't3-kodak-gold-200'], json_result=True)
        call(out, 'voices', [*prefix, 'voice', 'list'], json_result=True)
    validator = Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    validator_python = Path('E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe')
    call(out, 'skill-validation-native', [validator_python, '-E', '-B', '-X', 'utf8', validator, home / SKILL])
    tools = Path(shutil.which('ffmpeg')).parent
    case = ROOT / 'docs/validation/cross_machine66_20261106_r1/case.py'
    baseline = directory / 'authored-case'
    call(out, 'case-prepare', [PYTHON, '-I', '-B', '-u', '-X', 'utf8', case, 'prepare',
        '--cli-version', VERSION, '--root', baseline, '--installed', installed, '--tools', tools], json_result=True)
    replay = directory / 'skill-replay'
    call(out, 'case-replay', [PYTHON, '-I', '-B', '-u', '-X', 'utf8', case, 'replay',
        '--cli-version', VERSION, '--root', replay, '--installed', installed, '--tools', tools,
        '--entry', entry, '--expected', baseline / 'expected.json', '--package', baseline / 'baseline.aevpkg.zip'], json_result=True)
    proof = load(replay / 'verification.json')
    if label == 'local-r1':
        public_media = ROOT / 'docs/assets/release-v1-20261107'
        public_media.mkdir(parents=True, exist_ok=False)
        movie = replay / 'imported/renders/cross-host.mp4'
        shutil.copyfile(movie, public_media / 'actual.mp4')
        shutil.copyfile(baseline / 'pattern.mp4', public_media / 'input-pattern.mp4')
        shutil.copyfile(baseline / 'tone.wav', public_media / 'input-tone.wav')
        shutil.copyfile(baseline / 'baseline.aevpkg.zip', public_media / 'editable.aevpkg.zip')
        ffmpeg = tools / 'ffmpeg.exe'
        call(out, 'public-still', [ffmpeg, '-nostdin', '-v', 'error', '-ss', '0.5', '-i', movie,
            '-frames:v', '1', public_media / 'preview.png'])
        call(out, 'public-gif', [ffmpeg, '-nostdin', '-v', 'error', '-i', movie,
            '-filter_complex', 'fps=10,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',
            '-loop', '0', public_media / 'actual.gif'])
        (public_media / 'SOURCE_AND_LICENSES.md').write_text(
            '# v1.0.0 diagnostic case\n\n'
            'Actual output from the new native installed CLI0.1.66 / single Skill. '
            'Input video is FFmpeg testsrc2; audio is an explicitly generated 440Hz test tone. '
            'These diagnostic sources are generated by docs/validation/cross_machine66_20261106_r1/case.py, '
            'invoked by docs/validation/release_v1.py. No stock footage, model output or client image is included. '
            'Application editing adds the t3-kodak-gold-200 creative LUT at strength 0.65. '
            'LUT notices remain in docs/releases/v0.1.0-alpha.3/THIRD_PARTY.md. '
            'Actual output: 320x180, 30fps, 60 video frames, independent 48kHz stereo audio. '
            'The 10fps GIF is a silent preview. Whole-media hashes and AAC decode padding are recorded '
            'in the acceptance receipt; no human listening or natural-quality approval is claimed.\n',
            encoding='utf-8', newline='\n')
        save(public_media / 'FILES.json', dict(files=inventory(public_media),
            source_script='docs/validation/cross_machine66_20261106_r1/case.py',
            source_script_sha256=sha(case), video_frames=60, duration_seconds=2,
            frame_rate='30/1', gif_frame_rate='10/1', model_inference=False, human_listening=False))
    # A wrong runtime pin must not fall back to the checkout.
    config = load(home / 'local/agent-ffmpeg/runtime.json')
    config['release'] = 'wrong-distribution'
    save(home / 'local/agent-ffmpeg/runtime.json', config)
    rejected = call(out, 'wrong-release-rejected', [*prefix, 'version'], expected=2, json_result=True)
    assert rejected['ok'] is False
    config['release'] = TAG
    save(home / 'local/agent-ffmpeg/runtime.json', config)
    result = dict(status='passed', distribution_version=TAG, cli_version=VERSION,
        fresh_native_offline_install=True, installed=str(installed), kit=str(home),
        accepted_application_byte_equal=True, package_files=len(built['application_payload']),
        skill_count=1, module_count=17, skill_files=len(load(home / 'agent-ffmpeg-local-install-manifest.json')['files']),
        actual_PowerShell_entry=True, unicode_space_paths=True, source_fallback=False,
        whole_RGBA_PCM_and_source_asset_replay=True, replay=proof,
        rejected_bad_manifest=True, rejected_wrong_runtime_pin=True,
        newly_executed_full_engine_tests=False, historical_engine_tests=dict(source=4124, installed=4124),
        models_executed=False, GPU_executed=False, clean_host=False, human_listening=False,
        whole_CapCut_parity=False)
    result['validation_helper_resumed_after_missing_PyYAML'] = resume_validation
    save(out / 'verification.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'replay'}, ensure_ascii=False), flush=True)


def finalize_assets():
    assert load(EVIDENCE / 'local-r1/verification.json')['status'] == 'passed'
    assets = WORK / 'assets'
    for name in ('QUICKSTART.md', 'QUICKSTART.zh-TW.md', 'QUICKSTART.en.md', 'RELEASE-NOTES.md'):
        shutil.copyfile(ROOT / 'docs/releases/v1.0.0' / name, assets / name)
    rows = [dict(name=p.name, bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(assets.iterdir()) if p.is_file()]
    sums = ''.join(row['sha256'] + '  ' + row['name'] + '\n' for row in rows)
    (assets / 'SHA256SUMS.txt').write_text(sums, encoding='utf-8', newline='\n')
    shutil.copyfile(assets / 'SHA256SUMS.txt', ROOT / 'docs/releases/v1.0.0/SHA256SUMS.txt')
    rows.append(dict(name='SHA256SUMS.txt', bytes=(assets / 'SHA256SUMS.txt').stat().st_size,
                     sha256=sha(assets / 'SHA256SUMS.txt')))
    save(WORK / 'release-lock.json', dict(format='agent-editor-stable-release-v1', repository=REPO,
        tag=TAG, cli_version=VERSION, skill_revision=REVISION, prerelease=False,
        build_receipt_sha256=sha(EVIDENCE / 'build-r1/verification.json'),
        acceptance_receipt_sha256=sha(EVIDENCE / 'local-r1/verification.json'), assets=rows))
    print('Seven stable assets finalized', flush=True)


def scan(paths):
    helper = module('release_secret_scanner', ROOT / 'local/agent-ffmpeg/status-detail-checkpoint-20261106-r9/review.py')
    needles = [value.encode('utf-8') for value in helper.configured_secrets()]
    assert needles
    count = 0
    for path in paths:
        raw = Path(path).read_bytes()
        if Path(path).suffix == '.zip':
            with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
                for name in zipped.namelist():
                    if name.endswith('/'):
                        continue
                    payload = zipped.read(name)
                    assert not any(value in payload for value in needles), 'Private configuration found in archive'
        else:
            assert not any(value in raw for value in needles), 'Private configuration found in release scope'
        count += 1
    return count


def api(method, url, body=None, file=None, *, token=None, missing=False):
    parsed = urllib.parse.urlsplit(url)
    assert parsed.scheme == 'https' and parsed.hostname in {'api.github.com', 'uploads.github.com'}
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'agent-editor-kit-stable-release',
               'X-GitHub-Api-Version': '2022-11-28'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError('Authenticated redirects are forbidden')
    opener = urllib.request.build_opener(NoRedirect())
    def request(data):
        try:
            with opener.open(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=600) as response:
                raw = response.read(8 * 1024**2)
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            if missing and exc.code == 404:
                return None
            raise RuntimeError('GitHub operation rejected: HTTP' + str(exc.code)) from None
    if file:
        headers.update({'Content-Type': 'application/octet-stream', 'Content-Length': str(file.stat().st_size)})
        with file.open('rb') as stream:
            return request(stream)
    if body is not None:
        headers['Content-Type'] = 'application/json'
    return request(None if body is None else encoded(body))


def publish(commit):
    assert re.fullmatch('[0-9a-f]{40}', commit)
    assert git('rev-parse', 'HEAD').decode().strip() == commit
    assert git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit
    lock = load(WORK / 'release-lock.json')
    assets = WORK / 'assets'
    assert all(sha(assets / row['name']) == row['sha256'] for row in lock['assets'])
    scan(assets / row['name'] for row in lock['assets'])
    sys.path.insert(0, str(ROOT / 'docs/validation'))
    publisher = module('stable_release_credentials', ROOT / 'docs/validation/publish_delivery66.py')
    publisher.GIT = GIT
    token = publisher.credential()
    base = 'https://api.github.com/repos/' + REPO
    old = api('GET', base + '/releases/tags/v0.1.0-alpha.4')
    if not (WORK / 'old-alpha4-before.json').exists():
        save(WORK / 'old-alpha4-before.json', old)
    tag = api('GET', base + '/git/ref/tags/' + TAG, token=token, missing=True)
    if tag is None:
        tag = api('POST', base + '/git/refs', dict(ref='refs/tags/' + TAG, sha=commit), token=token)
    assert tag['object']['type'] == 'commit' and tag['object']['sha'] == commit
    marker = '<!-- agent-editor-kit-stable-source:' + commit + ';lock:' + sha(WORK / 'release-lock.json') + ' -->'
    release = api('GET', base + '/releases/tags/' + TAG, token=token, missing=True)
    # GitHub's tag endpoint can hide a draft even from its publisher. Enumerate
    # authenticated drafts and bind by our exact source/lock marker before POST.
    owned_drafts = []
    if release is None:
        listed = api('GET', base + '/releases?per_page=100', token=token)
        owned_drafts = [row for row in listed if row['tag_name'] == TAG
                        and row['draft'] and marker in row.get('body', '')]
        if owned_drafts:
            release = max(owned_drafts, key=lambda row: (len(row['assets']), -row['id']))
    if release is None:
        release = api('POST', base + '/releases', dict(tag_name=TAG, target_commitish=commit,
            name='agent editor kit v1.0.0 — first stable native Agent CLI release',
            draft=True, prerelease=False, make_latest='false',
            body=(assets / 'RELEASE-NOTES.md').read_text(encoding='utf-8') + '\n' + marker), token=token)
    assert marker in release['body'], 'Preserve an existing release owned by another source lock'
    save(WORK / 'pending-release-identity.json', dict(release_id=release['id'], tag=TAG,
        source_commit=commit, lock_sha256=sha(WORK / 'release-lock.json')))
    expected = {row['name']: row for row in lock['assets']}
    existing = {row['name']: row for row in release['assets']}
    assert set(existing) <= set(expected)
    for name, row in expected.items():
        item = existing.get(name)
        if item is None:
            assert release['draft']
            url = release['upload_url'].split('{', 1)[0] + '?' + urllib.parse.urlencode({'name': name})
            item = api('POST', url, file=assets / name, token=token)
        assert item['size'] == row['bytes'] and item['digest'] == 'sha256:' + row['sha256']
        print('Verified remote asset: ' + name, flush=True)
    release = api('GET', base + '/releases/' + str(release['id']), token=token)
    assert {row['name'] for row in release['assets']} == set(expected)
    if release['draft']:
        release = api('PATCH', base + '/releases/' + str(release['id']),
                      dict(draft=False, prerelease=False, make_latest='true'), token=token)
    assert not release['draft'] and not release['prerelease']
    removed = []
    for duplicate in owned_drafts:
        if duplicate['id'] == release['id']:
            continue
        current = api('GET', base + '/releases/' + str(duplicate['id']), token=token)
        assert current['draft'] and current['tag_name'] == TAG and marker in current.get('body', '')
        api('DELETE', base + '/releases/' + str(current['id']), token=token)
        removed.append(current['id'])
    result = dict(status='published', distribution_version=TAG, cli_version=VERSION,
        source_commit=commit, release_id=release['id'], url=release['html_url'],
        published_at=release['published_at'], prerelease=False, draft=False,
        discarded_own_duplicate_drafts=removed, publication_controller_sha256=sha(Path(__file__)),
        assets=[dict(name=row['name'], bytes=row['size'], sha256=row['digest'],
                     download_url=row['browser_download_url']) for row in release['assets']])
    save(EVIDENCE / 'publication-r1/verification.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


def public_accept():
    published = load(EVIDENCE / 'publication-r1/verification.json')
    lock = load(WORK / 'release-lock.json')
    base = 'https://api.github.com/repos/' + REPO
    release = api('GET', base + '/releases/tags/' + TAG)
    latest = api('GET', base + '/releases/latest')
    assert not release['prerelease'] and not release['draft'] and latest['tag_name'] == TAG
    tag = api('GET', base + '/git/ref/tags/' + TAG)
    assert tag['object']['sha'] == published['source_commit']
    assert {row['name'] for row in release['assets']} == {row['name'] for row in lock['assets']}
    folder = WORK / 'public-download'
    folder.mkdir()
    for row in published['assets']:
        request = urllib.request.Request(row['download_url'], headers={'User-Agent': 'agent-editor-kit-public-acceptance'})
        target = folder / row['name']
        with urllib.request.urlopen(request, timeout=600) as response, target.open('xb') as stream:
            shutil.copyfileobj(response, stream, 1024**2)
        assert sha(target) == row['sha256'].removeprefix('sha256:') and target.stat().st_size == row['bytes']
        print('Anonymous redownload verified: ' + row['name'], flush=True)
    accept('public-r1', folder)
    old = api('GET', base + '/releases/tags/v0.1.0-alpha.4')
    before = load(WORK / 'old-alpha4-before.json')
    assert old == before, 'Previous public release metadata or attachments changed'
    save(EVIDENCE / 'public-download-r1/verification.json', dict(status='passed', tag=TAG,
        public_url=release['html_url'], anonymous_redownload_assets=len(lock['assets']),
        all_download_hashes_equal=True, latest_stable=True, source_commit=published['source_commit'],
        old_alpha4_unchanged=True, fresh_install_and_actual_single_skill_replay=True,
        clean_host=False, models_executed=False, whole_CapCut_parity=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'build', 'kit', 'accept', 'assets', 'publish', 'public-accept'))
    parser.add_argument('--commit')
    parser.add_argument('--resume-validation', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare': prepare()
    elif args.action == 'build': build()
    elif args.action == 'kit': kit()
    elif args.action == 'accept': accept(resume_validation=args.resume_validation)
    elif args.action == 'assets': finalize_assets()
    elif args.action == 'publish': publish(args.commit)
    elif args.action == 'public-accept': public_accept()


if __name__ == '__main__':
    main()
