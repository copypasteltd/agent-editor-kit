"""CLI67 complete-batch freeze, regression, offline build and isolated Skill stage.

Reuses the already reviewed native full-suite/build harness without changing
its discovery, assertions or isolation. The formal CLI66 entry remains pinned.
"""
from __future__ import annotations
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = HERE/'evidence/portrait67-20261106-r1'
LOCAL = ROOT/'local/agent-ffmpeg/portrait67-20261106-r1'
VERSION = '0.1.67'
RELEASE = 'v0.1.0-alpha.4-local.65'


def harness():
    spec = importlib.util.spec_from_file_location('portrait67_existing_harness', HERE/'delivery66.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.VERSION = VERSION; module.RELEASE = RELEASE; module.BASE = BASE; module.LOCAL = LOCAL
    def proof(action, run):
        path = BASE/(action+'-'+run); path.mkdir(parents=True, exist_ok=False)
        (path/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
        (path/'reused-harness.py').write_bytes((HERE/'delivery66.py').read_bytes())
        return path
    module.proof = proof
    return module


def freeze(args, h):
    out = h.proof('freeze', args.run); product = h.pins()
    names = ('portrait67.py', 'portrait67_case.py', 'portrait67_gpu_oracle.py', 'delivery66.py', 'run_delivery66_native.py')
    tools = {str((HERE/name).relative_to(ROOT)).replace('\\', '/'): h.sha(HERE/name) for name in names}
    reference = ROOT/'docs/product/PORTRAIT_REGIONS_SKILL.md'
    tools[reference.relative_to(ROOT).as_posix()] = h.sha(reference)
    for name in (*product, *tools):
        if name.endswith('.py'): compile((ROOT/name).read_bytes(), name, 'exec')
    checkpoint = h.load(LOCAL/'before.json')
    assert all(h.sha(ROOT/name) == value for name, value in checkpoint['formal_files'].items())
    h.save(out/'verification.json', dict(status='frozen', cli_version=VERSION, file_hashes=product,
        formal_guard=h.formal_guard(), delivery_tool_files=tools, packaging_source_files=h.packaging_sources(),
        skill_validator=h.skill_validator_pin(), code_completed_before_tests=True, functional_tests_started=False,
        implementation_units=['pinned-adapter', 'exact-source-clock', 'semantic-labels', 'CUDA-regional-operators',
            'protected-stream-contract', 'owned-lossless-pipeline', 'CLI-recipes-rights-transactions',
            'package-fragment-rebinding', 'single-Skill-routing', 'adversarial-contract-tests', 'independent-GPU-oracle', 'real-installed-case'],
        original_assertions_preserved=True, model_forwards=0, formal_activation=False, full_goal_closed=False))
    print('Complete portrait67 batch frozen before functional tests.', flush=True)


def contracts(args, h, frozen):
    out = h.proof('contracts', args.run)
    sys.path[:0] = [str(h.SOURCE.parent), str(ROOT/'product/tests')]
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    suite = unittest.defaultTestLoader.discover(str(ROOT/'product/tests'), pattern='test_portrait.py')
    with (out/'tests.stderr').open('w', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    h.unchanged(frozen)
    record = dict(status='passed' if result.wasSuccessful() and not result.skipped else 'failed', tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        synthetic_processors_only=True, model_forwards=0, GPU_inference=False, original_assertions_preserved=True)
    h.save(out/'verification.json', record); print(json.dumps(record), flush=True)
    return 0 if record['status'] == 'passed' else 1


def stage(args, h, frozen):
    out = h.proof('skill-entry', args.run); candidate = h.load(BASE/('candidate-'+args.candidate_run)/'verification.json')
    installed = Path(candidate['installed']); home = LOCAL/('stage-'+args.run); home.mkdir()
    folder = home/'skills/agent-ffmpeg-local-editor'; manifest = copy.deepcopy(h.load(ROOT/'agent-ffmpeg-local-install-manifest.json'))
    for row in manifest['files']:
        target = home/row['path']; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes((ROOT/row['path']).read_bytes())
    entry = folder/'SKILL.md'; text = entry.read_text('utf-8')
    assert '`v0.1.0-alpha.4-local.64` / CLI `0.1.66`' in text
    text = text.replace('`v0.1.0-alpha.4-local.64` / CLI `0.1.66`', '`'+RELEASE+'` / CLI `'+VERSION+'`')
    text += '\nFor real CUDA semantic portrait regions and protected regional grading, read [portrait regions](references/portrait-regions.md). Show the actual region preview before selecting edits; explicit protection is required for occluders.\n'
    entry.write_text(text, 'utf-8', newline='\n')
    (folder/'references/portrait-regions.md').write_bytes((ROOT/'docs/product/PORTRAIT_REGIONS_SKILL.md').read_bytes())
    module = folder/'references/modules/local-models/module.md'
    with module.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('\nFor semantic face/skin/hair regions and explicit protected retouch, read [portrait regions](../../portrait-regions.md). Use the installed portrait commands and actual CUDA receipts; the 19 classes do not include hands/general occluders.\n')
    launcher = folder/'scripts/run.py'; text = launcher.read_text('utf-8')
    for key, value in [('MANIFEST', candidate['manifest_sha256']), ('RELEASE', RELEASE)]:
        text, count = re.subn(r'^'+key+r" = '[^']+'$", key+' = '+repr(value), text, flags=re.M); assert count == 1
    launcher.write_text(text, 'utf-8', newline='\n')
    config = copy.deepcopy(h.load(ROOT/'local/agent-ffmpeg/runtime.json'))
    config.update(release=RELEASE, installed_directory=str(installed), manifest_sha256=candidate['manifest_sha256'], launcher_sha256=h.sha(installed/'run.py'))
    h.save(home/'local/agent-ffmpeg/runtime.json', config)
    files = [dict(path=p.relative_to(home).as_posix(), bytes=p.stat().st_size, sha256=h.sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
    assert len(files) == 96 and len(list((folder/'references/modules').glob('*/module.md'))) == 17
    manifest.update(release=RELEASE, cli_version=VERSION, manifest_sha256=candidate['manifest_sha256'], files=files)
    manifest['skills'][0]['skill_md_sha256'] = h.sha(entry)
    h.save(home/'agent-ffmpeg-local-install-manifest.json', manifest)
    h.call(out, 'frontmatter', [sys.executable, '-E', '-B', '-X', 'utf8', h.SKILL_VALIDATOR, folder])
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', folder/'scripts/run.ps1']
    h.call(out, 'version', [*prefix, 'version'], cli=True)
    classes = h.call(out, 'portrait-classes', [*prefix, 'portrait', 'classes'], cli=True)
    assert len(classes['data']['labels']) == 19 and len(classes['data']['editable_regions']) == 7
    schema = h.call(out, 'schema', [*prefix, 'schema', 'show'], cli=True)
    h.unchanged(frozen)
    h.save(out/'verification.json', dict(status='passed', cli_version=VERSION, home=str(home), installed=str(installed),
        actual_PowerShell_entry=True, source_fallback=False, files=files, formal_activation=False,
        skill_files={row['path']: row['sha256'] for row in files}, modules=17, public_Skills=1,
        application_files=candidate['application_files'], schema_path=schema.get('data', {}).get('path')))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['freeze', 'contracts', 'tests', 'build', 'stage', 'native'])
    parser.add_argument('--run', required=True); parser.add_argument('--freeze-run', default='r1'); parser.add_argument('--tests-run', default='r1')
    parser.add_argument('--candidate-run', default='r1'); parser.add_argument('--stage-run', default='r1'); parser.add_argument('--installed', type=Path)
    parser.add_argument('--rubberband', type=Path, default=ROOT/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe')
    parser.add_argument('--html-runtime', type=Path, default=ROOT/'product/.runtime/html-motion-runtime-20261018-e2.json')
    parser.add_argument('--source-image', type=Path, default=Path('E:/dev/sandbox/视频拆解/新片俄式艺术重制_v4_2026-10-23/output/imagegen/raw/N002.png'))
    parser.add_argument('--native-python', type=Path, default=Path('E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe'))
    args = parser.parse_args()
    assert os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix
    assert all(s.isalnum() for s in (args.run, args.freeze_run, args.tests_run, args.candidate_run, args.stage_run))
    LOCAL.mkdir(parents=True, exist_ok=True); temp = LOCAL/'native-temp'; temp.mkdir(exist_ok=True)
    os.environ.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1')
    h = harness()
    if args.action == 'freeze': return freeze(args, h)
    frozen = h.load(BASE/('freeze-'+args.freeze_run)/'verification.json'); h.unchanged(frozen)
    if args.action == 'native':
        spec = importlib.util.spec_from_file_location('portrait67_actual_case', HERE/'portrait67_case.py'); case = importlib.util.module_from_spec(spec); spec.loader.exec_module(case)
        return case.run(args, h, frozen)
    return {'contracts': contracts, 'tests': lambda a, m, f: m.test_all(a, f), 'build': lambda a, m, f: m.build(a, f), 'stage': stage}[args.action](args, h, frozen)


if __name__ == '__main__':
    raise SystemExit(main())
