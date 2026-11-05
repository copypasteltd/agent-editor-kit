"""Finish a frozen delivery: independent kit replay, reversible activation, assets.

Uses the existing offline installer, single-Skill packager and product delivery
controller. A running/partial regression cannot authorize any of these actions.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ROUND = ROOT / 'docs/validation/evidence/delivery66-20261106-r1'
BASE = ROOT / 'docs/validation/evidence/delivery66-handoff-20261106-r1'
LOCAL = ROOT / 'local/agent-ffmpeg/delivery66-handoff'
VERSION, RELEASE, TAG = '0.1.66', 'v0.1.0-alpha.4-local.64', 'v0.1.0-alpha.4'
SKILL = 'skills/agent-ffmpeg-local-editor/'
CONFIG, MANIFEST = 'local/agent-ffmpeg/runtime.json', 'agent-ffmpeg-local-install-manifest.json'
RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def decode(raw):
    def unique(rows):
        value = {}
        for key, item in rows:
            require(key not in value, 'Duplicate JSON field')
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    require(isinstance(value, dict), 'Expected an evidence object')
    return value


def load(path, limit=8 * 1024**2):
    with Path(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'Evidence exceeds its read budget')
    return decode(raw)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('xb') as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def local(path, root=ROOT):
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    require(not str(path).startswith(('\\\\', '//')) and path.is_relative_to(root), 'Use an owned local path')
    for part in (path, *path.parents):
        require(not part.is_symlink() and not getattr(part, 'is_junction', lambda: False)(),
                'Owned paths must not cross reparse points')
    require(path.resolve().is_relative_to(root.resolve()), 'Owned path escaped its root')
    return path


def member(name):
    require(isinstance(name, str) and name and '\\' not in name, 'Archive name must be canonical')
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name and all(
        part not in {'.', '..'} and not part.endswith(('.', ' '))
        and part.split('.', 1)[0].casefold() not in RESERVED
        and all(ord(c) >= 32 and c not in ':<>"|?*' for c in part) for part in path.parts),
        'Invalid Windows archive member: ' + name)
    return path


def archive_plan(zipped, *, maximum_file=32 * 1024**2, maximum_total=128 * 1024**2):
    entries = zipped.infolist()
    require(0 < len(entries) <= 2048, 'Archive entry budget exceeded')
    names = [entry.filename for entry in entries]
    folded = {name.casefold() for name in names}
    require(len(folded) == len(names), 'Duplicate or case-alias archive names')
    total = 0
    for entry in entries:
        path = member(entry.filename)
        require(not entry.is_dir() and stat.S_IFMT(entry.external_attr >> 16) != stat.S_IFLNK,
                'Archive directories and links are forbidden')
        require(not entry.flag_bits & 1 and 0 <= entry.file_size <= maximum_file, 'Invalid or oversized archive member')
        require(not any(parent.as_posix().casefold() in folded for parent in path.parents if str(parent) != '.'),
                'Archive file/directory prefix conflict')
        total += entry.file_size
    require(total <= maximum_total, 'Archive total byte budget exceeded')
    return entries


def extract(archive, destination, *, skill=False):
    destination = local(destination)
    require(not destination.exists(), 'Existing extraction target is preserved')
    with zipfile.ZipFile(local(archive)) as zipped:
        entries = archive_plan(zipped, maximum_file=(32 if skill else 512) * 1024**2,
                               maximum_total=(128 if skill else 2048) * 1024**2)
        inventory = None
        if skill:
            require('KIT-FILES.json' in zipped.namelist(), 'Skill kit inventory is required')
            require(zipped.getinfo('KIT-FILES.json').file_size <= 2 * 1024**2, 'Oversized kit inventory')
            inventory = decode(zipped.read('KIT-FILES.json'))
            rows = inventory['files']
            require(isinstance(rows, list) and len(rows) <= 512, 'Invalid kit inventory')
            expected = {row['path']: row for row in rows}
            require(len(expected) == len(rows) and set(expected) | {'KIT-FILES.json'} == set(zipped.namelist()),
                    'Kit inventory differs from archive contents')
            require(inventory['cli_version'] == VERSION and inventory['skill_count'] == 1
                    and inventory['module_count'] == 17, 'Wrong kit version or Skill layout')
            require([name for name in expected if PurePosixPath(name).name == 'SKILL.md'] == [SKILL + 'SKILL.md'],
                    'Exactly one public Skill entry is required')
            for name, row in expected.items():
                require(type(row['bytes']) is int and row['bytes'] == zipped.getinfo(name).file_size
                        and isinstance(row['sha256'], str) and re.fullmatch('[0-9a-f]{64}', row['sha256']),
                        'Invalid inventory size or digest')
        # Validate every input digest before creating the destination.
        for entry in entries:
            with zipped.open(entry) as source:
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
            if inventory and entry.filename != 'KIT-FILES.json':
                require(digest == expected[entry.filename]['sha256'], 'Corrupt Skill kit content')
        destination.mkdir(parents=True)
        for entry in entries:
            target = local(destination / Path(*member(entry.filename).parts), destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(entry) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
    return inventory


def report_path(kind, run):
    require(isinstance(run, str) and run.isalnum() and len(run) <= 32, 'Use bounded alphanumeric run IDs')
    return BASE / (kind + '-' + run) / 'verification.json'


def begin(kind, run):
    out = report_path(kind, run).parent
    require(not out.exists(), 'Existing evidence is immutable; choose a fresh run ID')
    out.mkdir(parents=True)
    for name in ('delivery66_handoff.py', 'delivery66_music_faults.py', 'publish_delivery66.py'):
        source = Path(__file__).with_name(name)
        require(source.is_file(), 'Complete all handoff code before executing a round')
        (out / name).write_bytes(source.read_bytes())
    return out


def execute(out, name, command, *, expected=0, cli=False, timeout=1200):
    env = dict(os.environ)
    temporary = LOCAL / 'temp'
    temporary.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary),
               PYTHONDONTWRITEBYTECODE='1', PIP_NO_INDEX='1', PIP_CONFIG_FILE=os.devnull)
    began = time.monotonic()
    with (out / (name + '.stdout')).open('xb') as stdout, (out / (name + '.stderr')).open('xb') as stderr:
        result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    calls = load(out / 'calls.json')['calls'] if (out / 'calls.json').is_file() else []
    calls.append(dict(name=name, argv=list(map(str, command)), exit_code=result.returncode,
                      elapsed_seconds=time.monotonic() - began))
    save(out / 'calls.json', dict(calls=calls))
    require(result.returncode == 0 if expected == 0 else result.returncode != 0,
            name + ': unexpected exit status; retained stdout/stderr identify the failure')
    print(json.dumps(dict(step=name, exit_code=result.returncode)), flush=True)
    if cli:
        value = load(out / (name + '.stdout'))
        require(value.get('ok') is (expected == 0), name + ': CLI envelope mismatch')
        require(value['provenance']['cli_version'] == VERSION, name + ': wrong installed CLI')
        return value
    return (out / (name + '.stdout')).read_bytes()


def source_unchanged(freeze):
    for name, pin in freeze['file_hashes'].items():
        require(sha(local(ROOT / name)) == pin, 'Frozen source, tests or offline code changed: ' + name)


def guards_equal(guards):
    return all(local(ROOT / name).is_file() and sha(ROOT / name) == pin for name, pin in guards.items())


def ready(args, *, formal_changed=False):
    freeze = load(ROUND / ('freeze-' + args.freeze_run) / 'verification.json')
    require(freeze['status'] == 'frozen' and freeze['cli_version'] == VERSION, 'Wrong implementation freeze')
    source_unchanged(freeze)
    if not formal_changed:
        require(guards_equal(freeze['formal_guard']), 'Formal entry changed since source freeze')
    for mode in ('source-all', 'installed-all'):
        proof = load(ROUND / (mode + '-' + args.tests_run) / 'verification.json')
        require(proof.get('status') == 'passed' and proof.get('cli_version') == VERSION
                and proof.get('file_hashes') == freeze['file_hashes']
                and type(proof.get('tests')) is int and proof['tests'] > 0
                and proof['tests'] == proof.get('discovered_tests')
                and all(type(proof.get(key)) is int and proof[key] == 0 for key in ('failures', 'errors', 'skipped')),
                'Whole source and installed regressions must both pass without skips')
        if mode == 'installed-all':
            require(proof.get('source_fallback') is False, 'Installed regression used a source fallback')
    candidate = load(ROUND / ('candidate-' + args.candidate_run) / 'verification.json')
    require(candidate['status'] == 'installed-and-byte-verified' and candidate['cli_version'] == VERSION,
            'Accepted offline candidate required')
    installed = local(candidate['installed'])
    expected = candidate['application_files']
    require(expected == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}, 'Installed application changed')
    require(sha(local(candidate['archive'])) == candidate['archive_sha256'], 'Offline application ZIP changed')
    staged = load(ROUND / ('skill-entry-' + args.stage_run) / 'verification.json')
    require(staged['status'] == 'passed' and staged['application_files'] == expected, 'Skill entry acceptance required')
    home = local(staged['home'])
    for name, pin in staged['skill_files'].items():
        require(sha(local(home / name)) == pin, 'Staged Skill changed')
    sys.path.insert(0, str(installed / 'site'))
    package = importlib.import_module('ai_ad_editor')
    require(Path(package.__file__).resolve() == installed / 'site/ai_ad_editor/__init__.py'
            and package.VERSION == VERSION, 'Do not mix source and installed imports')
    core = importlib.import_module('ai_ad_editor.delivery')
    descriptor_report = load(ROUND / ('descriptor-' + args.descriptor_run) / 'verification.json')
    descriptor = local(descriptor_report['descriptor'])
    require(descriptor_report['status'] == 'passed'
            and sha(descriptor) == descriptor_report['descriptor_sha256'], 'Delivery descriptor changed')
    spec = load(descriptor)
    if formal_changed:
        for role, row in spec['gates'].items():
            core._gate(ROOT, role, row, VERSION, expected, staged['skill_files'])
    else:
        core.verify(ROOT, descriptor)
    return dict(freeze=freeze, candidate=candidate, installed=installed, staged=staged,
                home=home, descriptor=descriptor, spec=spec, core=core)


def ps(home):
    return ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            Path(home) / SKILL / 'scripts/run.ps1']


def accepted(kind, run, context):
    path = report_path(kind, run)
    value = load(path)
    require(value.get('status') == 'passed' and value.get('cli_version') == VERSION
            and value.get('application_files') == context['candidate']['application_files']
            and value.get('skill_files') == context['staged']['skill_files'], 'Missing matching acceptance: ' + kind)
    return value


def quickstart(context, language):
    manifest = context['candidate']['manifest_sha256']
    intro = {
        'zh': '原生Windows CPython3.13 x64应用与单一Skill。应用ZIP不包含Python、FFmpeg、驱动、模型权重或完整音乐运行库；这些依赖需要另行准备。',
        'zh-TW': '原生Windows CPython3.13 x64應用與單一Skill。應用ZIP不包含Python、FFmpeg、驅動、模型權重或完整音樂執行庫；這些依賴需要另行準備。',
        'en': 'Native Windows CPython3.13 x64 application and one public Skill. Python, FFmpeg, drivers, model weights and the complete music runtime are separate dependencies.',
    }[language]
    steps = {
        'zh': '解包应用与Skill到新的本地路径，核对SHA256。执行应用自带安装器，再配置本地模型包，最后注册一个Skill。每次编辑先检查版本及依赖，导入授权素材，展示真实滤镜/音色预览，记录选择，再预检、编辑、渲染、检查及重放工程包。',
        'zh-TW': '解包應用與Skill到新的本機路徑，核對SHA256。執行應用自帶安裝器，再設定本機模型包，最後註冊一個Skill。每次編輯先檢查版本及依賴，匯入授權素材，展示實際濾鏡/音色預覽，記錄選擇，再預檢、編輯、算圖、檢查及重放工程包。',
        'en': 'Extract both archives to new local directories and verify SHA256. Run the shipped application installer, configure explicit local model packs, then register the one Skill. For editing: version/doctor, ingest authorized media, show actual look/voice previews, record choices, dry-run, edit/generate, render, inspect, export and replay.',
    }[language]
    return ('# agent editor kit / CLI' + VERSION + '\n\n' + intro + '\n\n' + steps + '\n\n'
        '```powershell\n$python = "C:/Python313/python.exe"\n'
        '$bundle = "E:/video-tools/application-bundle"\n$installed = "E:/video-tools/application-installed"\n'
        '& $python -E -B -X utf8 "$bundle/install.py" --bundle $bundle --target $installed '
        '--manifest-sha256 "' + manifest + '"\n'
        '# Run inside the extracted Skill kit; PACKS is the parent of verified local model-pack directories.\n'
        '& $python -E -B -X utf8 ./scripts/activate_community_runtime.py --installed $installed --packs "E:/video-tools/model-packs"\n'
        '& ./register-agent-ffmpeg-local-skills.ps1\n'
        '$entry = "./skills/agent-ffmpeg-local-editor/scripts/run.ps1"\n'
        '& $entry version\n& $entry doctor\n& $entry capabilities\n'
        '& $entry project init "E:/video-work/new-project"\n'
        '& $entry music generate --help\n& $entry delivery --help\n```\n\n'
        'Runtime release: `' + RELEASE + '`. Public entry: `$agent-ffmpeg-local-editor`; 17 internal modules.\n\n'
        'CUDA voice/translation require the corresponding local packs and explicit library configuration. '
        'Neural music additionally requires its reviewed native model adapter and runtime; no automatic download occurs. '
        'The model/output rights ledger, human listening and natural quality remain explicit review steps. '
        'Same-host portable acceptance does not establish clean-host or cross-machine support. '
        'Full CapCut parity and all original G01–G38 conditions remain open.\n')


def kit(args):
    context = ready(args)
    out = begin('kit', args.run)
    work = local(LOCAL / ('kit-' + args.run))
    require(not work.exists(), 'Preserve earlier kit outputs')
    work.mkdir(parents=True)
    execute(out, 'base-packager', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
        ROOT / 'scripts/package_community_skill.py', '--output', work / 'base',
        '--skill-source', context['home'], '--archive-name', 'base.zip'])
    content = {}
    with zipfile.ZipFile(work / 'base/base.zip') as zipped:
        archive_plan(zipped)
        for name in zipped.namelist():
            if name != 'KIT-FILES.json':
                content[name] = zipped.read(name)
    for language, suffix in [('zh', ''), ('zh-TW', '.zh-TW'), ('en', '.en')]:
        content['QUICKSTART' + suffix + '.md'] = quickstart(context, language).encode('utf-8')
    content['docs/product/DELIVERY_CONTROLLER.md'] = (ROOT / 'docs/product/DELIVERY_CONTROLLER.md').read_bytes()
    inventory = dict(format='agent-community-single-skill-v1', release=RELEASE, cli_version=VERSION,
        skill_count=1, module_count=17, files=[dict(path=name, bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest()) for name, data in sorted(content.items())])
    content['KIT-FILES.json'] = encoded(inventory)
    destination = work / 'agent-editor-kit-community-unified-skill-r59.zip'
    with zipfile.ZipFile(destination, 'x') as zipped:
        for name, data in sorted(content.items()):
            member(name)
            info = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o100644 << 16
            zipped.writestr(info, data)
    source_unchanged(context['freeze'])
    require(guards_equal(context['freeze']['formal_guard']), 'Formal entry changed during packaging')
    save(out / 'verification.json', dict(status='built-not-yet-independently-accepted', cli_version=VERSION,
        archive=str(destination), archive_sha256=sha(destination), entries=len(content),
        application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
        actual_registered_entry_tested=False, formal_activation=False))


def replay(context, out, prefix, work, label):
    reference = load(ROUND / ('package-replay-' + context['args'].package_run) / 'verification.json')
    package = local(reference['project_package'])
    project = work / (label + '-project')
    execute(out, label + '-import', [*prefix, 'convert', 'import', '--input', package, '--output', project], cli=True)
    movie = project / 'renders/handoff.mp4'
    execute(out, label + '-render', [*prefix, 'render', '--project', project, '--output', movie], cli=True)
    ffmpeg = importlib.import_module('ai_ad_editor.media').ffmpeg_path()
    result = {}
    for kind, options in [('RGBA', ['-map', '0:v:0', '-an', '-pix_fmt', 'rgba']),
                          ('PCM', ['-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le'])]:
        raw = execute(out, label + '-' + kind, [ffmpeg, '-nostdin', '-v', 'error', '-i', movie,
            *options, '-f', 'hash', '-hash', 'sha256', 'pipe:1'])
        result[kind] = raw.decode().strip()
        require(result[kind] == reference['decoded']['original_' + kind], 'Whole replay media differs: ' + kind)
    music = load(ROUND / ('native-music-' + context['args'].music_run) / 'verification.json')
    asset = next(row for row in load(project / 'project.json')['assets'] if row['id'] == music['asset']['id'])
    require(sha(project / asset['uri']) == music['master_audio']['sha256']
            and asset['source']['music_generation'] == music['asset']['source']['music_generation'],
            'Portable replay lost master audio or editable recipe')
    return dict(project=str(project), movie=str(movie), decoded=result, full_master_and_recipe_equal=True)


def verify_kit(args):
    context = ready(args)
    context['args'] = args
    built = load(report_path('kit', args.kit_run))
    require(built['cli_version'] == VERSION and sha(local(built['archive'])) == built['archive_sha256'], 'Kit archive changed')
    out = begin('portable-kit', args.run)
    work = local(LOCAL / ('portable-' + args.run))
    require(not work.exists(), 'Preserve earlier portable verification')
    work.mkdir(parents=True)
    home = work / '工具包 中文 spaces'
    extract(built['archive'], home, skill=True)
    require(load(home / MANIFEST)['files'] == load(context['home'] / MANIFEST)['files'], 'Kit changed Skill inventory')
    bundle = work / 'application-bundle'
    extract(context['candidate']['archive'], bundle)
    installed = work / 'application-installed'
    execute(out, 'portable-install', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
        bundle / 'install.py', '--bundle', bundle, '--target', installed,
        '--manifest-sha256', context['candidate']['manifest_sha256'], '--timeout-seconds', '600'])
    require({p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
            == context['candidate']['application_files'], 'Fresh portable application differs')
    configuration = copy.deepcopy(load(context['home'] / CONFIG))
    configuration.update(installed_directory=str(installed), launcher_sha256=sha(installed / 'run.py'))
    save(home / CONFIG, configuration)
    discovery = work / 'isolated-discovery'
    execute(out, 'portable-register', ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        home / 'register-agent-ffmpeg-local-skills.ps1', '-SkillsDirectory', discovery,
        '-ReceiptPath', out / 'registration.json'])
    require((discovery / 'agent-ffmpeg-local-editor').resolve() == (home / SKILL).resolve(), 'Registration did not select portable Skill')
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
              discovery / 'agent-ffmpeg-local-editor/scripts/run.ps1']
    execute(out, 'portable-version', [*prefix, 'version'], cli=True)
    capabilities = execute(out, 'portable-capabilities', [*prefix, 'capabilities'], cli=True)
    require(capabilities['data']['capabilities']['verified_skill_delivery']['protocol'] == 'agent-editor-skill-delivery-v2',
            'Portable entry does not discover the delivery controller')
    result = replay(context, out, prefix, work, 'portable')
    source_unchanged(context['freeze'])
    require(guards_equal(context['freeze']['formal_guard']), 'Portable test changed formal discovery')
    save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
        application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
        kit_archive=built['archive'], kit_sha256=built['archive_sha256'], fresh_offline_install=True,
        independent_registration=True, actual_PowerShell_entry=True, source_fallback=False,
        complete_RGBA_PCM_replay=True, replay=result, clean_host=False, cross_machine=False,
        formal_activation=False, human_listening=False, natural_quality_accepted=False))


def activate(args):
    context = ready(args)
    context['args'] = args
    accepted('portable-kit', args.kit_verify_run, context)
    faults = accepted('music-faults', args.faults_run, context)
    require(set(faults.get('cases', {})) == {'cancel', 'timeout', 'publication-conflict'}
            and all(row.get('passed') is True for row in faults['cases'].values()), 'Actual music fault cases required')
    out = begin('formal-entry', args.run)
    work = local(LOCAL / ('formal-' + args.run))
    work.mkdir(parents=True)
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', context['installed'] / 'run.py']
    execute(out, 'inspect', [*prefix, 'delivery', 'inspect', '--workspace', ROOT, '--descriptor', context['descriptor']], cli=True)
    execute(out, 'plan', [*prefix, 'delivery', 'activate', '--workspace', ROOT, '--descriptor', context['descriptor'], '--dry-run'], cli=True)
    active = False
    try:
        first = execute(out, 'activate-first', [*prefix, 'delivery', 'activate', '--workspace', ROOT,
            '--descriptor', context['descriptor']], cli=True)['data']
        active = True
        execute(out, 'registered-first-version', [*ps(ROOT), 'version'], cli=True)
        execute(out, 'rollback-plan', [*prefix, 'delivery', 'rollback', '--workspace', ROOT, '--dry-run'], cli=True)
        execute(out, 'rollback-first', [*prefix, 'delivery', 'rollback', '--workspace', ROOT], cli=True)
        active = False
        require(guards_equal(context['freeze']['formal_guard']), 'Explicit rollback did not restore exact formal files')
        old = execute(out, 'previous-entry-version', [*ps(ROOT), 'version'])
        require(json.loads(old)['data']['cli_version'] == '0.1.63', 'Rollback did not restore previous actual runtime')
        second = execute(out, 'activate-final', [*prefix, 'delivery', 'activate', '--workspace', ROOT,
            '--descriptor', context['descriptor']], cli=True)['data']
        active = True
        discovery = Path.home() / '.codex/skills/agent-ffmpeg-local-editor'
        require(discovery.resolve() == (ROOT / SKILL).resolve(), 'The real discovered Skill is not this installation')
        real_prefix = ps(ROOT)
        real_prefix[-1] = discovery / 'scripts/run.ps1'
        execute(out, 'actual-discovery-version', [*real_prefix, 'version'], cli=True)
        result = replay(context, out, real_prefix, work, 'actual-discovery')
        for row in context['spec']['files']:
            require(sha(ROOT / row['path']) == row['sha256'], 'Formal file changed during acceptance')
        source_unchanged(context['freeze'])
        save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
            application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
            actual_C_drive_discovery=True, actual_PowerShell_entry=True, source_fallback=False,
            explicit_rollback_byte_equal=True, previous_delivery_id=first['delivery_id'],
            delivery_id=second['delivery_id'], complete_RGBA_PCM_replay=True, replay=result,
            formal_activation=True, backups_preserved=True, human_listening=False, natural_quality_accepted=False))
    except BaseException as exc:
        recovery = None
        if active:
            try:
                recovery = execute(out, 'rollback-on-failed-acceptance', [*prefix, 'delivery', 'rollback', '--workspace', ROOT], cli=True)
            except BaseException as recovery_error:
                recovery = dict(error=repr(recovery_error), manual_recovery_required=True)
        save(out / 'verification.json', dict(status='failed', cli_version=VERSION, error=repr(exc), recovery=recovery,
            formal_activation=not guards_equal(context['freeze']['formal_guard'])))
        raise


def assets(args):
    context = ready(args, formal_changed=True)
    formal = accepted('formal-entry', args.formal_run, context)
    portable = accepted('portable-kit', args.kit_verify_run, context)
    for row in context['spec']['files']:
        require(sha(ROOT / row['path']) == row['sha256'], 'Formal entry changed after acceptance')
    out = begin('release-assets', args.run)
    directory = local(LOCAL / ('release-assets-' + args.run))
    require(not directory.exists(), 'Earlier release assets are immutable')
    directory.mkdir(parents=True)
    sources = {
        'agent-editor-kit-' + TAG + '-cp313-win_amd64.zip': local(context['candidate']['archive']),
        'agent-editor-kit-community-unified-skill-r59.zip': local(portable['kit_archive']),
    }
    require(sha(sources['agent-editor-kit-community-unified-skill-r59.zip']) == portable['kit_sha256'], 'Accepted kit changed')
    for name, source in sources.items():
        shutil.copyfile(source, directory / name)
        require(sha(directory / name) == sha(source), 'Release attachment changed while copying')
    for language, suffix in [('zh', ''), ('zh-TW', '.zh-TW'), ('en', '.en')]:
        (directory / ('QUICKSTART' + suffix + '.md')).write_text(quickstart(context, language), encoding='utf-8', newline='\n')
    notes = ('# agent editor kit ' + TAG + '\n\n'
        'CLI0.1.66, one public Skill and 17 internal modules. Includes complete restore preflight, '
        'bounded durable transaction backups, bounded music progress reads and the v2 verified delivery controller.\n\n'
        'Acceptance: matching whole-source/installed regressions, actual CUDA neural music, complete PCM and '
        'editable project replay, actual cancellation/timeout/publication-conflict cases, fresh same-host offline '
        'installation, portable Skill registration, formal activation and explicit rollback.\n\n'
        'Python3.13 x64, FFmpeg, drivers, model weights and external music runtime are separate dependencies. '
        'Neural outputs remain internal/unverified and are excluded from these attachments. No human listening, '
        'clean-host/cross-machine certification or full CapCut parity is claimed. The original G01–G38 scope remains open.\n\n'
        '简体：先校验摘要，再离线安装应用、配置模型、注册统一Skill；使用前查看QUICKSTART.md。\n\n'
        '繁體：先核對摘要，再離線安裝應用、設定模型、註冊統一Skill；使用前查看QUICKSTART.zh-TW.md。\n')
    (directory / 'RELEASE-NOTES.md').write_text(notes, encoding='utf-8', newline='\n')
    rows = [dict(name=path.name, bytes=path.stat().st_size, sha256=sha(path)) for path in sorted(directory.iterdir())]
    (directory / 'SHA256SUMS.txt').write_text(''.join(row['sha256'] + '  ' + row['name'] + '\n' for row in rows), encoding='utf-8', newline='\n')
    rows.append(dict(name='SHA256SUMS.txt', bytes=(directory / 'SHA256SUMS.txt').stat().st_size, sha256=sha(directory / 'SHA256SUMS.txt')))
    gates = {kind: dict(path=str(report_path(kind, run)), sha256=sha(report_path(kind, run))) for kind, run in
             [('formal-entry', args.formal_run), ('portable-kit', args.kit_verify_run), ('music-faults', args.faults_run)]}
    lock = dict(format='agent-editor-reviewed-release-v1', repository='copypasteltd/agent-editor-kit', tag=TAG,
        runtime_release=RELEASE, cli_version=VERSION, assets=rows, gates=gates,
        frozen_source=context['freeze']['file_hashes'], descriptor=str(context['descriptor']),
        descriptor_sha256=sha(context['descriptor']), formal_delivery_id=formal['delivery_id'],
        public_model_media_included=False, created_at_utc=datetime.now(timezone.utc).isoformat())
    save(directory / 'release-lock.json', lock)
    save(out / 'verification.json', dict(status='ready-not-published', cli_version=VERSION,
        directory=str(directory), lock_sha256=sha(directory / 'release-lock.json'),
        assets=rows, formal_activation=True, publication_attempted=False))


def arguments(parser=None):
    parser = parser or argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    for name, default in [('freeze', 'r4'), ('tests', 'r4'), ('candidate', 'r1'), ('stage', 'r1'),
                           ('music', 'r1'), ('package', 'r1'), ('descriptor', 'r1'), ('kit', 'r1'),
                           ('kit-verify', 'r1'), ('faults', 'r1'), ('formal', 'r1')]:
        parser.add_argument('--' + name + '-run', default=default)
    return parser


def main():
    parser = arguments()
    parser.add_argument('action', choices=['kit', 'verify-kit', 'activate', 'assets'])
    args = parser.parse_args()
    require(os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix,
            'Use native Windows Python -B without a virtual environment')
    for name, value in vars(args).items():
        if name == 'run' or name.endswith('_run'):
            require(value.isalnum() and len(value) <= 32, 'Invalid run ID')
    return {'kit': kit, 'verify-kit': verify_kit, 'activate': activate, 'assets': assets}[args.action](args)


if __name__ == '__main__':
    raise SystemExit(main())
