"""Finish one frozen CLI67 batch without replacing earlier evidence or releases.

Complete this driver before its code-phase freeze. Every action runs separately;
the continuation holds the original prerequisite process handle until its real
exit. Neural media remain private. Existing product gates and assertions apply.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / 'evidence/portrait67-20261106-r1'
LOCAL = ROOT / 'local/agent-ffmpeg/portrait67-20261106-r1'
VERSION = '0.1.67'
RELEASE = 'v0.1.0-alpha.4-local.65'
SKILL = 'skills/agent-ffmpeg-local-editor/'
MANIFEST = 'agent-ffmpeg-local-install-manifest.json'
CONFIG = 'local/agent-ffmpeg/runtime.json'
KIT_NAME = 'agent-editor-kit-community-unified-skill-r60.zip'
FILES = ('portrait67_delivery.py', 'portrait67.py', 'portrait67_case.py',
         'portrait67_gpu_oracle.py', 'delivery66.py', 'delivery66_handoff.py',
         'delivery66_av_replay.py', 'delivery66_music_faults.py',
         'run_portrait67_chain.py', 'run_delivery66_native.py', 'test_portrait67_delivery.py',
         'test_delivery66_av_replay.py')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def require(value, message):
    if not value:
        raise ValueError(message)


def begin(kind, run):
    out = BASE / (kind + '-' + run)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    return out


def tooling():
    # Configure reused validation utilities; product functions are never patched.
    sys.path.insert(0, str(HERE))
    wrapper = module('portrait67_delivery_wrapper', HERE / 'portrait67.py')
    h = wrapper.harness()
    helper = module('portrait67_delivery_archive_helpers', HERE / 'delivery66_handoff.py')
    helper.VERSION, helper.RELEASE = VERSION, RELEASE
    helper.ROUND, helper.BASE, helper.LOCAL = BASE, BASE, LOCAL
    helper.TAG = 'main'
    return h, helper


def input_pins():
    return {str((HERE / name).relative_to(ROOT)).replace('\\', '/'): sha(HERE / name) for name in FILES}


def phase(args):
    h, _ = tooling()
    frozen_path = BASE / ('freeze-' + args.freeze_run) / 'verification.json'
    frozen = load(frozen_path)
    h.unchanged(frozen)
    files = input_pins()
    for name in files:
        compile((ROOT / name).read_bytes(), name, 'exec')
    out = begin('delivery-code-phase', args.run)
    save(out / 'verification.json', dict(status='frozen', cli_version=VERSION,
        code_completed_before_functional_validation=True, functional_validation_started=False,
        files=files, product_freeze=dict(path=str(frozen_path), sha256=sha(frozen_path)),
        formal_guard=frozen['formal_guard'], original_assertions_preserved=True,
        planned_actions=['contracts', 'music', 'replay', 'faults', 'descriptor', 'kit', 'portable', 'formal'],
        actual_neural_inference=False, formal_activation=False, full_goal_closed=False))


def code_guard(args, *, formal_changed=False):
    h, helper = tooling()
    record = load(BASE / ('delivery-code-phase-' + args.phase_run) / 'verification.json')
    require(record['status'] == 'frozen' and record['code_completed_before_functional_validation'] is True
            and record['files'] == input_pins(), 'The complete delivery batch changed after freeze')
    pin = record['product_freeze']
    require(sha(pin['path']) == pin['sha256'], 'Original portrait freeze changed')
    frozen = load(pin['path'])
    # Formal delivery deliberately changes only the formal files. All frozen
    # product, test, packaging, tool and validator inputs remain immutable.
    require(h.pins() == frozen['file_hashes'], 'Frozen product or original tests changed')
    require(all(sha(ROOT / name) == digest for name, digest in frozen['delivery_tool_files'].items()),
            'Frozen portrait tools changed')
    require(h.packaging_sources() == frozen['packaging_source_files']
            and h.skill_validator_pin() == frozen['skill_validator'], 'Frozen packaging or validator changed')
    if not formal_changed:
        require(h.formal_guard() == frozen['formal_guard'], 'Formal CLI66 entry changed before acceptance')
    return h, helper, frozen


def ready(args, *, formal_changed=False, music=False, replay=False, descriptor=False):
    h, helper, frozen = code_guard(args, formal_changed=formal_changed)
    gate_contracts = load(BASE / ('delivery-contracts-' + args.contracts_run) / 'verification.json')
    require(gate_contracts.get('status') == 'passed'
            and gate_contracts.get('failures') == gate_contracts.get('errors') == gate_contracts.get('skipped') == 0
            and gate_contracts.get('tests') == gate_contracts.get('discovered_tests') == 17
            and gate_contracts.get('code_phase_sha256') == sha(BASE / ('delivery-code-phase-' + args.phase_run) / 'verification.json'),
            'The complete delivery contract suite must pass')
    for mode in ('source-all', 'installed-all'):
        value = load(BASE / (mode + '-' + args.tests_run) / 'verification.json')
        require(value.get('status') == 'passed' and value.get('cli_version') == VERSION
                and value.get('file_hashes') == frozen['file_hashes']
                and value.get('tests') == value.get('discovered_tests') == 4154
                and all(type(value.get(k)) is int and value[k] == 0 for k in ('failures', 'errors', 'skipped'))
                and value.get('frozen_equal') is True and value.get('original_assertions_preserved') is True,
                'Both original complete CLI67 regressions must pass')
        if mode == 'installed-all':
            require(value.get('source_fallback') is False, 'Installed source fallback is forbidden')
    candidate = load(BASE / ('candidate-' + args.candidate_run) / 'verification.json')
    installed = helper.local(candidate['installed'])
    expected = {p.name: sha(p) for p in h.SOURCE.glob('*.py')}
    require(candidate['status'] == 'installed-and-byte-verified' and candidate['cli_version'] == VERSION
            and candidate['application_files'] == expected
            and {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')} == expected
            and sha(candidate['archive']) == candidate['archive_sha256'], 'Offline candidate changed')
    staged = load(BASE / ('skill-entry-' + args.stage_run) / 'verification.json')
    home = helper.local(staged['home'])
    require(staged['status'] == 'passed' and staged['cli_version'] == VERSION
            and staged['application_files'] == expected and staged['source_fallback'] is False
            and staged['actual_PowerShell_entry'] is True and len(staged['skill_files']) == 96
            and all(sha(home / name) == pin for name, pin in staged['skill_files'].items()),
            'The exact 96-file candidate Skill is required')
    portrait = load(BASE / ('native-case-' + args.native_run) / 'verification.json')
    require(portrait.get('status') == 'passed' and portrait.get('cli_version') == VERSION
            and portrait.get('actual_installed_PowerShell_entry') is True
            and portrait.get('source_fallback') is False and portrait.get('source_mother_unchanged') is True
            and set(portrait['results']['faults']) == {'cancel', 'conflict', 'timeout'},
            'Real installed CUDA portrait, migration and fault terminal required')
    sys.path.insert(0, str(installed / 'site'))
    import ai_ad_editor
    from ai_ad_editor.runtime import configure_local_runtime
    require(Path(ai_ad_editor.__file__).resolve() == installed / 'site/ai_ad_editor/__init__.py'
            and ai_ad_editor.VERSION == VERSION, 'Do not mix source and installed imports')
    configure_local_runtime()
    context = dict(args=args, freeze=frozen, h=h, helper=helper, candidate=candidate,
                   installed=installed, staged=staged, home=home, portrait=portrait)
    if music:
        value = load(BASE / ('native-music-' + args.music_run) / 'verification.json')
        require(value.get('status') == 'passed' and value.get('cli_version') == VERSION
                and value.get('application_files') == expected and value.get('skill_files') == staged['skill_files']
                and value.get('source_fallback') is False, 'Matching CLI67 actual music is required')
        for key in ('actual_CUDA_music', 'complete_PCM_verified', 'project_placement_verified',
                    'owned_process_cleanup_verified', 'actual_PowerShell_entry'):
            require(value.get(key) is True, 'Missing actual music acceptance: ' + key)
        model = value['actual_generation']['worker']['model']
        require(model.get('neural_backend') == 'cuda' and model.get('CPU_fallback') is False
                and set(model['forwards']) == {'text', 'language_model', 'diffusion', 'vae'}
                and all(type(v) is int and v > 0 for v in model['forwards'].values())
                and all(model['forward_output_devices'][k] == ['cuda:0'] for k in model['forwards']),
                'All four actual CUDA components are required')
        for key in ('master_audio', 'request_file', 'project_manifest'):
            require(sha(value[key]['path']) == value[key]['sha256'], 'Accepted music input/output changed: ' + key)
        context['music'] = value
    if replay:
        value = load(BASE / ('package-replay-' + args.package_run) / 'verification.json')
        require(value.get('status') == 'passed' and value.get('cli_version') == VERSION
                and value.get('application_files') == expected and value.get('source_fallback') is False
                and all(value.get(key) is True for key in ('complete_master_WAV_equal',
                    'complete_generation_recipe_equal', 'complete_rendered_RGBA_PCM_equal'))
                and sha(value['project_package']) == value['project_package_sha256'],
                'Matching complete CLI67 AV package replay required')
        context['replay'] = value
    if descriptor:
        value = load(BASE / ('descriptor-' + args.descriptor_run) / 'verification.json')
        require(value['status'] == 'passed' and sha(value['descriptor']) == value['descriptor_sha256'],
                'Accepted descriptor changed')
        context['descriptor'] = Path(value['descriptor'])
        context['spec'] = load(value['descriptor'])
        from ai_ad_editor import delivery
        if formal_changed:
            for role, row in context['spec']['gates'].items():
                delivery._gate(ROOT, role, row, VERSION, expected, staged['skill_files'])
        else:
            delivery.verify(ROOT, context['descriptor'])
    return context


def execute(context, out, name, command, *, cli=False, timeout=1200):
    return context['helper'].execute(out, name, command, cli=cli, timeout=timeout)


def media_measure(context, out, label, movie):
    from ai_ad_editor.media import ffmpeg_path, ffprobe_path
    ffmpeg, decoded = ffmpeg_path(), {}
    for kind, options in [('RGBA', ['-map', '0:v:0', '-an', '-pix_fmt', 'rgba']),
                          ('PCM', ['-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le'])]:
        raw = execute(context, out, label + '-' + kind, [ffmpeg, '-nostdin', '-v', 'error', '-i', movie,
            *options, '-f', 'hash', '-hash', 'sha256', 'pipe:1'])
        value = raw.decode().strip()
        require(value.startswith('SHA256=') and len(value) == 71
                and all(c in '0123456789abcdef' for c in value[7:]), 'Invalid complete decoded hash')
        decoded[kind] = value
    probe = execute(context, out, label + '-probe', [ffprobe_path(), '-v', 'error', '-count_frames',
        '-show_streams', '-show_format', '-of', 'json', movie])
    # Never persist raw neural PCM in public evidence. Retain only measurements.
    completed = subprocess.run([str(ffmpeg), '-nostdin', '-v', 'error', '-i', str(movie), '-map', '0:a:0',
        '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'], cwd=ROOT, capture_output=True,
        timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
    require(completed.returncode == 0, 'Independent full PCM decode failed')
    av = module('portrait67_independent_av_measurements', HERE / 'delivery66_av_replay.py')
    measured = av.media_summary(json.loads(probe), completed.stdout)
    require(measured['audio']['complete_PCM_sha256'] == decoded['PCM'][7:], 'Independent PCM hash differs')
    return dict(decoded=decoded, measurements=measured)


def music_action(args):
    context = ready(args)
    context['h'].music(args, context['freeze'])


def contracts_action(args):
    import unittest
    code_guard(args)
    out = begin('delivery-contracts', args.run)
    sys.path.insert(0, str(HERE))
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern='test_portrait67_delivery.py')
    old = module('portrait67_existing_av_contracts', HERE / 'test_delivery66_av_replay.py')
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(old))
    discovered = suite.countTestCases()
    require(discovered == 17, 'Run the entire delivery contract set')
    with (out / 'tests.stderr').open('x', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    code_guard(args)
    save(out / 'verification.json', dict(status='passed' if result.wasSuccessful() and not result.skipped else 'failed',
        cli_version=VERSION, discovered_tests=discovered, tests=result.testsRun, failures=len(result.failures),
        errors=len(result.errors), skipped=len(result.skipped), fixture_only=True, actual_neural_inference=False,
        model_forwards=0, code_phase_sha256=sha(BASE / ('delivery-code-phase-' + args.phase_run) / 'verification.json'),
        formal_activation=False))
    require(result.wasSuccessful() and not result.skipped, 'Delivery contract tests failed')


def replay_action(args):
    context = ready(args, music=True)
    h, music = context['h'], context['music']
    out = begin('package-replay', args.run)
    work = LOCAL / ('package-' + args.run)
    work.mkdir(exist_ok=False)
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', context['installed'] / 'run.py']
    source = Path(music['artifacts']['project'])
    original_pins = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file()}
    original = work / 'original'
    shutil.copytree(source, original)
    project = load(original / 'project.json')
    project['settings']['canvas'].update(width=320, height=568)
    h.save(original / 'project.json', project)
    from ai_ad_editor.media import ffmpeg_path
    diagnostic = work / 'procedural-video.mp4'
    execute(context, out, 'make-diagnostic-video', [ffmpeg_path(), '-nostdin', '-v', 'error', '-n',
        '-f', 'lavfi', '-i', 'testsrc2=size=320x568:rate=30:duration=10', '-an', '-c:v', 'libx264',
        '-threads', '2', '-pix_fmt', 'yuv420p', diagnostic])
    video = execute(context, out, 'ingest-video', [*prefix, 'media', 'ingest', '--project', original,
        '--input', diagnostic], cli=True)['data']['asset']
    track = next(t for t in project['sequences'][0]['tracks'] if t['kind'] == 'video' and not t['locked'])
    changes = work / 'video-track.json'
    h.save(changes, dict(operations=[dict(op='append_clip', id='replay_diagnostic_video', asset_id=video['id'],
        track_id=track['id'], timeline_start_tick=0, duration_tick=900000, source_in_tick=0, source_out_tick=900000)]))
    execute(context, out, 'compose-video', [*prefix, 'timeline', 'compose', '--project', original,
        '--input', changes], cli=True)
    execute(context, out, 'validate-project', [*prefix, 'validate', '--project', original], cli=True)
    package, restored = work / 'music.aevpkg.zip', work / 'restored'
    execute(context, out, 'export', [*prefix, 'convert', 'export', '--project', original,
        '--target-format', 'package', '--output', package], cli=True)
    execute(context, out, 'import', [*prefix, 'convert', 'import', '--input', package, '--output', restored], cli=True)
    measurements = {}
    for label, folder in [('original', original), ('restored', restored)]:
        asset = next(a for a in load(folder / 'project.json')['assets'] if a['id'] == music['asset']['id'])
        require(sha(folder / asset['uri']) == music['master_audio']['sha256']
                and asset['source']['music_generation'] == music['asset']['source']['music_generation'],
                'Complete master WAV or generation recipe differs')
        movie = folder / 'renders/music.mp4'
        execute(context, out, label + '-render', [*prefix, 'render', '--project', folder, '--output', movie], cli=True)
        measurements[label] = media_measure(context, out, label, movie)
    require(measurements['original'] == measurements['restored'], 'Full decoded AV or clocks differ')
    require(original_pins == {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*') if p.is_file()},
            'The accepted generation project changed')
    code_guard(args)
    save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
        application_files=context['candidate']['application_files'], source_fallback=False,
        complete_master_WAV_equal=True, complete_generation_recipe_equal=True,
        complete_rendered_RGBA_PCM_equal=True, decoded={label + '_' + kind: value
            for label, row in measurements.items() for kind, value in row['decoded'].items()},
        measurements={label: row['measurements'] for label, row in measurements.items()},
        project_package=str(package), project_package_sha256=sha(package),
        generation_reference=dict(path=str(BASE / ('native-music-' + args.music_run) / 'verification.json'),
            sha256=sha(BASE / ('native-music-' + args.music_run) / 'verification.json')),
        source_generation_project_unchanged=True, original_audio_only_rejection_preserved=True,
        diagnostic_video=dict(kind='procedural FFmpeg testsrc2', natural_video=False, frames=300, duration_seconds=10),
        new_model_forwards=0, human_listening=False, natural_quality_accepted=False,
        media_published=False, formal_activation=False))


def faults_action(args):
    context = ready(args, music=True, replay=True)
    out = begin('music-faults', args.run)
    work = LOCAL / ('music-faults-' + args.run)
    work.mkdir(exist_ok=False)
    faults = module('portrait67_existing_music_fault_cases', HERE / 'delivery66_music_faults.py')
    faults.handoff = context['helper']
    cases = {}
    for name in ('cancel', 'timeout', 'publication-conflict'):
        cases[name] = faults.case(context, out, work, name, args.timeout_seconds, args.maximum_case_seconds)
    code_guard(args)
    save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
        application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
        cases=cases, actual_PowerShell_entry=True, source_fallback=False,
        model_functions_mocked=False, product_code_patched=False, formal_activation=False,
        human_listening=False, generated_audio_publication_approved=False))


def descriptor_action(args):
    context = ready(args, music=True, replay=True)
    context['h'].descriptor(args, context['freeze'])


def quickstart(context, language):
    text = context['helper'].quickstart(context, language)
    text = text.replace('agent-editor-kit-community-unified-skill-r59.zip', KIT_NAME)
    text = text.replace('agent-editor-kit-main-cp313-win_amd64.zip', 'agent-editor-kit-cli67-cp313-win_amd64.zip')
    title = {'zh': '人像区域使用', 'zh-TW': '人像區域使用', 'en': 'Portrait-region workflow'}[language]
    explanation = {
        'zh': '此候选为CLI67／local65、单Skill17模块96文件；不是已公开alpha.4附件。人像区域需要已有原生CUDA解释器和固定BiSeNet权重，基础安装不附带这些依赖。先登记适配器、解析并展示真实分区预览，再用新资产ID运行修饰。19类不含手或通用遮挡物，必须显式提供保护蒙版；连续结果、肤质与身份仍须人工检查。',
        'zh-TW': '此候選為CLI67／local65、單Skill17模組96檔案；不是已公開alpha.4附件。人像區域需要既有原生CUDA解譯器與固定BiSeNet權重，基礎安裝不附帶這些依賴。先登記適配器、解析並展示實際分區預覽，再以新素材ID執行修飾。19類不含手或一般遮擋物，必須明確提供保護遮罩；連續結果、膚質與身分仍須人工檢查。',
        'en': 'This is CLI67/local65 with one Skill, 17 modules and 96 files; it is separate from the public alpha.4 assets. Portrait regions require an existing native CUDA interpreter and the pinned BiSeNet weights. Register the adapter, parse and show its actual region preview, then retouch with new asset IDs. The 19 classes exclude hands and general occluders: provide explicit protection masks and review continuous skin texture and identity.'}[language]
    return '# Local CLI67 candidate / ' + RELEASE + '\n\n' + text + '\n\n## ' + title + '\n\n' + explanation + '\n\n[Commands and recipe contract](skills/agent-ffmpeg-local-editor/references/portrait-regions.md)\n'


def kit_action(args):
    context = ready(args, music=True, replay=True, descriptor=True)
    out = begin('kit', args.run)
    work = LOCAL / ('kit-' + args.run)
    work.mkdir(exist_ok=False)
    built = json.loads(execute(context, out, 'base-packager', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
        ROOT / 'scripts/package_community_skill.py', '--output', work / 'base', '--skill-source', context['home'],
        '--archive-name', 'base.zip', '--source-ref', 'main']))
    packaging = context['freeze']['packaging_source_files']
    require(built['packaging_source_files'] == {name: pin for name, pin in packaging.items()
            if name != 'docs/product/DELIVERY_CONTROLLER.md'}, 'Base packaging provenance differs')
    content = {}
    with zipfile.ZipFile(built['archive']) as zipped:
        context['helper'].archive_plan(zipped)
        for name in zipped.namelist():
            if name != 'KIT-FILES.json':
                content[name] = zipped.read(name)
    for language, suffix in [('zh', ''), ('zh-TW', '.zh-TW'), ('en', '.en')]:
        content['QUICKSTART' + suffix + '.md'] = quickstart(context, language).encode('utf-8')
    content['docs/product/DELIVERY_CONTROLLER.md'] = (ROOT / 'docs/product/DELIVERY_CONTROLLER.md').read_bytes()
    inventory = dict(format='agent-community-single-skill-v1', release=RELEASE, cli_version=VERSION,
        skill_count=1, module_count=17, packaging_source_files=packaging, documentation_source_ref='main',
        files=[dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
               for name, data in sorted(content.items())])
    content['KIT-FILES.json'] = (json.dumps(inventory, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    archive = work / KIT_NAME
    with zipfile.ZipFile(archive, 'x') as zipped:
        for name, data in sorted(content.items()):
            context['helper'].member(name)
            info = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o100644 << 16
            zipped.writestr(info, data)
    code_guard(args)
    save(out / 'verification.json', dict(status='built-not-yet-independently-accepted', cli_version=VERSION,
        archive=str(archive), archive_sha256=sha(archive), entries=len(content),
        application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
        packaging_source_files=packaging, documentation_source_ref='main', formal_activation=False,
        public_release_overwritten=False, model_media_included=False))


def replay_entry(context, out, prefix, work, label):
    project = work / (label + '-project')
    execute(context, out, label + '-import', [*prefix, 'convert', 'import', '--input',
        context['replay']['project_package'], '--output', project], cli=True)
    movie = project / 'renders/delivery.mp4'
    execute(context, out, label + '-render', [*prefix, 'render', '--project', project, '--output', movie], cli=True)
    measured = media_measure(context, out, label, movie)
    require(measured['decoded'] == {kind: context['replay']['decoded']['original_' + kind] for kind in ('RGBA', 'PCM')}
            and measured['measurements'] == context['replay']['measurements']['original'], 'Entry replay differs')
    music = context['music']
    asset = next(a for a in load(project / 'project.json')['assets'] if a['id'] == music['asset']['id'])
    require(sha(project / asset['uri']) == music['master_audio']['sha256']
            and asset['source']['music_generation'] == music['asset']['source']['music_generation'],
            'Entry lost master WAV or editable recipe')
    return dict(project=str(project), movie=str(movie), **measured, full_master_and_recipe_equal=True)


def portable_action(args):
    context = ready(args, music=True, replay=True, descriptor=True)
    out = begin('portable-kit', args.run)
    work = LOCAL / ('portable-' + args.run)
    work.mkdir(exist_ok=False)
    built = load(BASE / ('kit-' + args.kit_run) / 'verification.json')
    require(built['cli_version'] == VERSION and sha(built['archive']) == built['archive_sha256'], 'Kit changed')
    home = work / '工具包 中文 spaces'
    context['helper'].extract(built['archive'], home, skill=True)
    require(load(home / MANIFEST)['files'] == load(context['home'] / MANIFEST)['files'], 'Portable Skill differs')
    bundle, installed = work / 'application-bundle', work / 'application-installed'
    context['helper'].extract(context['candidate']['archive'], bundle)
    execute(context, out, 'portable-install', [sys.executable, '-E', '-B', '-u', '-X', 'utf8', bundle / 'install.py',
        '--bundle', bundle, '--target', installed, '--manifest-sha256', context['candidate']['manifest_sha256'],
        '--timeout-seconds', '600'])
    require({p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
            == context['candidate']['application_files'], 'Fresh portable application differs')
    configured = json.loads(execute(context, out, 'base-only', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
        home / 'scripts/activate_community_runtime.py', '--installed', installed, '--base-only']))
    require(configured['configuration_mode'] == 'base-only' and configured['verified_packs'] == []
            and configured['model_verification_performed'] is False
            and load(home / CONFIG)['installed_directory'] == str(installed)
            and load(home / 'local/agent-ffmpeg/community-runtime.json') == {}, 'Unexpected portable model binding')
    discovery = work / 'isolated-discovery'
    execute(context, out, 'register', ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        home / 'register-agent-ffmpeg-local-skills.ps1', '-SkillsDirectory', discovery,
        '-ReceiptPath', out / 'registration.json'])
    require((discovery / 'agent-ffmpeg-local-editor').resolve() == (home / SKILL).resolve(), 'Wrong portable discovery')
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
              discovery / 'agent-ffmpeg-local-editor/scripts/run.ps1']
    execute(context, out, 'version', [*prefix, 'version'], cli=True)
    classes = execute(context, out, 'portrait-classes', [*prefix, 'portrait', 'classes'], cli=True)
    require(len(classes['data']['labels']) == 19 and len(classes['data']['editable_regions']) == 7, 'Wrong portrait contract')
    replay = replay_entry(context, out, prefix, work, 'portable')
    code_guard(args)
    save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
        application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
        kit_archive=built['archive'], kit_sha256=built['archive_sha256'], fresh_offline_install=True,
        packaging_source_files=built['packaging_source_files'], documentation_source_ref='main',
        independent_registration=True, actual_PowerShell_entry=True, source_fallback=False,
        actual_base_only_configuration=True, complete_RGBA_PCM_replay=True, replay=replay,
        optional_model_packs_required=False, clean_host=False, cross_machine=False,
        formal_activation=False, human_listening=False, natural_quality_accepted=False))


def formal_action(args):
    context = ready(args, music=True, replay=True, descriptor=True)
    for kind, run in [('portable-kit', args.portable_run), ('music-faults', args.faults_run)]:
        value = load(BASE / (kind + '-' + run) / 'verification.json')
        require(value['status'] == 'passed' and value['cli_version'] == VERSION
                and value['application_files'] == context['candidate']['application_files']
                and value['skill_files'] == context['staged']['skill_files'], 'Matching gate required: ' + kind)
        if kind == 'music-faults':
            require(set(value['cases']) == {'cancel', 'timeout', 'publication-conflict'}
                    and all(row['passed'] is True for row in value['cases'].values()), 'Actual music faults required')
    discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    require(discovery.is_junction() and discovery.resolve() == (ROOT / SKILL).resolve(), 'Unrelated discovery is preserved')
    out = begin('formal-entry', args.run)
    work = LOCAL / ('formal-' + args.run)
    work.mkdir(exist_ok=False)
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', context['installed'] / 'run.py']
    real = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', discovery / 'scripts/run.ps1']
    execute(context, out, 'inspect', [*prefix, 'delivery', 'inspect', '--workspace', ROOT,
        '--descriptor', context['descriptor']], cli=True)
    execute(context, out, 'plan', [*prefix, 'delivery', 'activate', '--workspace', ROOT,
        '--descriptor', context['descriptor'], '--dry-run'], cli=True)
    active = False
    try:
        first = execute(context, out, 'activate-first', [*prefix, 'delivery', 'activate', '--workspace', ROOT,
            '--descriptor', context['descriptor']], cli=True)['data']
        active = True
        execute(context, out, 'discovered-first-version', [*real, 'version'], cli=True)
        execute(context, out, 'rollback-plan', [*prefix, 'delivery', 'rollback', '--workspace', ROOT, '--dry-run'], cli=True)
        execute(context, out, 'rollback', [*prefix, 'delivery', 'rollback', '--workspace', ROOT], cli=True)
        active = False
        code_guard(args)
        require(not (ROOT / SKILL / 'references/portrait-regions.md').exists(), 'Rollback left the newly added reference')
        old = json.loads(execute(context, out, 'previous-entry-version', [*real, 'version']))
        require(old['ok'] is True and old['data']['cli_version'] == '0.1.66', 'Previous runtime was not restored')
        second = execute(context, out, 'activate-final', [*prefix, 'delivery', 'activate', '--workspace', ROOT,
            '--descriptor', context['descriptor']], cli=True)['data']
        active = True
        execute(context, out, 'actual-discovery-version', [*real, 'version'], cli=True)
        execute(context, out, 'actual-discovery-classes', [*real, 'portrait', 'classes'], cli=True)
        replay = replay_entry(context, out, real, work, 'actual-discovery')
        for row in context['spec']['files']:
            require(sha(ROOT / row['path']) == row['sha256'], 'Formal file changed during acceptance')
        code_guard(args, formal_changed=True)
        save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
            application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
            actual_C_drive_discovery=True, actual_PowerShell_entry=True, source_fallback=False,
            explicit_rollback_byte_equal=True, rollback_removed_new_reference=True,
            previous_delivery_id=first['delivery_id'], delivery_id=second['delivery_id'],
            complete_RGBA_PCM_replay=True, replay=replay, formal_activation=True,
            backups_preserved=True, human_listening=False, natural_quality_accepted=False,
            public_release_overwritten=False, full_goal_closed=False))
    except BaseException as exc:
        recovery = None
        if active:
            try:
                recovery = execute(context, out, 'rollback-on-failed-acceptance',
                    [*prefix, 'delivery', 'rollback', '--workspace', ROOT], cli=True)
                code_guard(args)
            except BaseException as recovery_error:
                recovery = dict(error=repr(recovery_error), manual_recovery_required=True)
        save(out / 'verification.json', dict(status='failed', cli_version=VERSION, error=repr(exc),
            recovery=recovery, formal_activation=context['h'].formal_guard() != context['freeze']['formal_guard']))
        raise


def continue_action(args):
    code_guard(args)
    require(args.prerequisite_identity is not None, 'Bind the existing prerequisite process explicitly')
    native = module('portrait67_delivery_process_identity', HERE / 'run_delivery66_native.py')
    identity = load(args.prerequisite_identity)
    require(native.process_identity(identity['pid']) == identity
            and Path(identity['executable']).resolve() == Path(sys.executable).resolve(), 'Prerequisite identity changed')
    out = begin('delivery-chain', args.run)
    state = dict(status='waiting-existing-prerequisite', source_restarted=False,
        prerequisite_identity=identity, runner_identity=native.process_identity(os.getpid()), steps=[],
        code_completed_before_execution=True, formal_activation=False, full_goal_closed=False)
    save(out / 'verification.json', state)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    handle = kernel.OpenProcess(0x1000 | 0x00100000, False, identity['pid'])
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        require(native.process_identity(identity['pid']) == identity, 'Prerequisite identity changed before wait')
        while True:
            result = kernel.WaitForSingleObject(handle, 1000)
            if result == 0:
                break
            if result != 258:
                raise ctypes.WinError(ctypes.get_last_error())
        exit_code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        state['prerequisite_exit_code'] = exit_code.value
        require(exit_code.value == 0, 'Prerequisite failed; preserve its original terminal')
    except BaseException as exc:
        state.update(status='stopped', error=repr(exc))
        save(out / 'verification.json', state)
        raise
    finally:
        kernel.CloseHandle(handle)
    original = BASE / ('chain-' + args.prerequisite_run) / 'verification.json'
    require(load(original)['status'] == 'passed', 'Prerequisite chain has no passed terminal')
    state['prerequisite_terminal'] = dict(path=str(original), sha256=sha(original))
    ready(args)
    # All feature operations use fresh explicit installed entrypoints. Only the
    # Windows ownership helper is imported into this continuation process.
    _, _, frozen = code_guard(args)
    sys.path.insert(0, str(ROOT / 'product/src'))
    from ai_ad_editor.local_matting import _windows_job
    tail = ['--phase-run', args.phase_run, '--freeze-run', args.freeze_run,
        '--contracts-run', args.contracts_run,
        '--tests-run', args.tests_run, '--candidate-run', args.candidate_run, '--stage-run', args.stage_run,
        '--native-run', args.native_run, '--music-run', args.music_run, '--package-run', args.package_run,
        '--descriptor-run', args.descriptor_run, '--kit-run', args.kit_run, '--portable-run', args.portable_run,
        '--faults-run', args.faults_run]
    try:
        for action, run, budget in [('music', args.music_run, 5400), ('replay', args.package_run, 1800),
                ('faults', args.faults_run, 16000), ('descriptor', args.descriptor_run, 900),
                ('kit', args.kit_run, 900), ('portable', args.portable_run, 1800), ('formal', args.run, 1800)]:
            state.update(status='running', current_step=action)
            save(out / 'verification.json', state)
            argv = [sys.executable, '-E', '-B', '-u', '-X', 'utf8', str(Path(__file__)), action, '--run', run, *tail]
            began = time.monotonic()
            with _windows_job() as assign, (out / (action + '.stdout')).open('xb') as stdout, (out / (action + '.stderr')).open('xb') as stderr:
                process = subprocess.Popen(argv, cwd=ROOT, env=dict(os.environ), stdin=subprocess.DEVNULL,
                    stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
                assign(process)
                state['current_process'] = native.process_identity(process.pid)
                save(out / 'verification.json', state)
                try:
                    while process.poll() is None:
                        require(time.monotonic() - began <= budget, 'Owned delivery action exceeded its deadline: ' + action)
                        time.sleep(.5)
                    code = process.wait(timeout=15)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=15)
            state['steps'].append(dict(action=action, exit_code=code, elapsed_seconds=time.monotonic() - began))
            state.pop('current_process', None)
            save(out / 'verification.json', state)
            require(code == 0, 'Delivery action failed; no implicit retry: ' + action)
        state.update(status='passed', current_step=None, formal_activation=True)
        save(out / 'verification.json', state)
    except BaseException as exc:
        recovery = None
        if tooling()[0].formal_guard() != frozen['formal_guard']:
            # A supervisor deadline can interrupt the child's exception path.
            # Recover the existing owned journal using the accepted installation.
            try:
                installed = Path(load(BASE / ('candidate-' + args.candidate_run) / 'verification.json')['installed'])
                command = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py'),
                           'delivery', 'rollback', '--workspace', str(ROOT)]
                with (out / 'recovery.stdout').open('xb') as stdout, (out / 'recovery.stderr').open('xb') as stderr:
                    restored = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                        timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
                require(restored.returncode == 0 and tooling()[0].formal_guard() == frozen['formal_guard']
                        and not (ROOT / SKILL / 'references/portrait-regions.md').exists(), 'Exact old formal entry was not restored')
                recovery = dict(status='rolled-back', previous_CLI='0.1.66', exact_formal_files_equal=True)
            except BaseException as recovery_error:
                recovery = dict(error=repr(recovery_error), manual_recovery_required=True)
        state.update(status='stopped', error=repr(exc), recovery=recovery,
                     formal_activation=tooling()[0].formal_guard() != frozen['formal_guard'])
        save(out / 'verification.json', state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'contracts', 'music', 'replay', 'faults', 'descriptor', 'kit', 'portable', 'formal', 'continue'])
    parser.add_argument('--run', required=True)
    for name in ('phase', 'contracts', 'freeze', 'tests', 'candidate', 'stage', 'native', 'music', 'package', 'descriptor', 'kit', 'portable', 'faults', 'prerequisite'):
        parser.add_argument('--' + name + '-run', default='r1')
    parser.add_argument('--prerequisite-identity', type=Path)
    parser.add_argument('--timeout-seconds', type=float, default=120)
    parser.add_argument('--maximum-case-seconds', type=float, default=5200)
    args = parser.parse_args()
    require(os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix,
            'Use an existing native Windows interpreter with -B')
    require(all(isinstance(v, str) and v.isalnum() and len(v) <= 32
                for k, v in vars(args).items() if k == 'run' or k.endswith('_run')), 'Invalid run identifier')
    require(10 <= args.timeout_seconds <= 600 and 3600 <= args.maximum_case_seconds <= 10800, 'Invalid failure budgets')
    temporary = LOCAL / 'native-temp'
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ.update(TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary), PYTHONDONTWRITEBYTECODE='1')
    if args.action == 'freeze':
        return phase(args)
    try:
        return {'contracts': contracts_action, 'music': music_action, 'replay': replay_action, 'faults': faults_action,
                'descriptor': descriptor_action, 'kit': kit_action, 'portable': portable_action,
                'formal': formal_action, 'continue': continue_action}[args.action](args)
    except BaseException as exc:
        kind = {'contracts': 'delivery-contracts', 'music': 'native-music', 'replay': 'package-replay',
                'portable': 'portable-kit', 'formal': 'formal-entry', 'continue': 'delivery-chain'}.get(args.action, args.action)
        out = BASE / (kind + '-' + args.run)
        if out.is_dir() and not (out / 'verification.json').exists():
            save(out / 'verification.json', dict(status='failed', cli_version=VERSION, action=args.action,
                error=repr(exc), original_evidence_preserved=True, full_goal_closed=False))
        raise


if __name__ == '__main__':
    main()
