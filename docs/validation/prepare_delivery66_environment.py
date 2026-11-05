"""Complete r3: explicit native dependencies and installed-package test bindings."""
import argparse
import ast
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/delivery66-20261106-r1'
PREVIOUS = ROOT / 'docs/validation/candidates/delivery66-r2'
CANDIDATE = ROOT / 'docs/validation/candidates/delivery66-r3'

DEPENDENCY_FUNCTION = '''def configure_test_dependencies(args, out, package):
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
    expected = {str(path): sha(path) for path in files}
    call(out, 'native-audio-version', [binary, '--version'])
    call(out, 'native-node-version', [node, '--version'])
    record = dict(status='ready', files=expected, html_runtime=runtime,
        browser_launched_by_preflight=False, model_forwards=0, virtualization=False,
        installed_test_import_root=str(package.parent), original_assertions_preserved=True)
    save(out / 'native-dependencies.json', record)
    return expected


'''

PACKAGE_HELPER = '''"""Bind test subprocesses/resources to the explicitly loaded product package."""
import os
from pathlib import Path
import ai_ad_editor

IMPORT_ROOT = Path(ai_ad_editor.__file__).resolve().parent.parent
requested = os.environ.get('AI_AD_EDITOR_TEST_PACKAGE_ROOT')
if requested:
    assert IMPORT_ROOT == Path(requested).resolve(), 'Test package differs from explicit source/install selection'
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def once(value, old, new):
    assert value.count(old) == 1, old[:100]
    return value.replace(old, new, 1)


def guard(freeze):
    assert all(sha(ROOT / name) == pin for name, pin in freeze['file_hashes'].items())
    assert all(sha(ROOT / name) == pin for name, pin in freeze['formal_guard'].items())


def bind_test_file(source):
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    offsets, offset = [], 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    root_forms = {ast.dump(ast.parse(value, mode='eval').body, include_attributes=False) for value in (
        "Path(__file__).resolve().parents[1]", "Path(__file__).parents[1]")}
    full_forms = {ast.dump(ast.parse(value, mode='eval').body, include_attributes=False) for value in (
        "ROOT / 'product' / 'src'",)}
    replacements = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            continue
        expression = None
        if ast.dump(node, include_attributes=False) in full_forms:
            expression = 'IMPORT_ROOT'
        elif ast.dump(node.left, include_attributes=False) in root_forms and isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
            relative = node.right.value
            if relative == 'src':
                expression = 'IMPORT_ROOT'
            elif relative.startswith('src/'):
                expression = '(IMPORT_ROOT / ' + repr(relative[4:]) + ')'
        if expression:
            # AST columns count UTF-8 bytes, while these slices use characters.
            begin = offsets[node.lineno - 1] + len(lines[node.lineno - 1].encode()[:node.col_offset].decode())
            end = offsets[node.end_lineno - 1] + len(lines[node.end_lineno - 1].encode()[:node.end_col_offset].decode())
            replacements.append((begin, end, expression))
    if not replacements:
        return source, 0
    chosen = []
    for item in sorted(replacements, key=lambda item: (item[0], -item[1])):
        if not chosen or item[0] >= chosen[-1][1]:
            chosen.append(item)
    result = source
    for begin, end, replacement in reversed(chosen):
        result = result[:begin] + replacement + result[end:]
    parsed = ast.parse(result)
    insert = 0
    for index, node in enumerate(parsed.body):
        if (index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)) or (isinstance(node, ast.ImportFrom) and node.module == '__future__'):
            insert = node.end_lineno
        else:
            break
    changed_lines = result.splitlines(keepends=True)
    changed_lines.insert(insert, 'from package_under_test import IMPORT_ROOT\n')
    result = ''.join(changed_lines)
    before_names = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')]
    after_names = [node.name for node in ast.walk(ast.parse(result)) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')]
    assert before_names == after_names
    return result, len(chosen)


def prepare():
    freeze = load(BASE / 'freeze-r1/verification.json')
    guard(freeze)
    previous = load(PREVIOUS / 'implementation.json')
    assert previous['status'] == 'complete-correction-code-not-tested'
    assert all(sha(PREVIOUS / name) == pin for name, pin in (previous['files'] | previous['support_files']).items())
    CANDIDATE.mkdir()
    for name in previous['files']:
        shutil.copyfile(PREVIOUS / name, CANDIDATE / name)
    mapping = dict(previous['mapping'])
    runner = (CANDIDATE / 'runner.py').read_text(encoding='utf-8')
    runner = once(runner, '\ndef test_all(args, freeze):', '\n' + DEPENDENCY_FUNCTION + 'def test_all(args, freeze):')
    runner = once(runner, "    configure_local_runtime()\n    # Preserve all existing tests", "    configure_local_runtime()\n    dependencies = configure_test_dependencies(args, out, package)\n    # Preserve all existing tests")
    runner = once(runner, "    assert expected == {p.name: sha(p) for p in package.glob('*.py')}\n    report =", "    assert expected == {p.name: sha(p) for p in package.glob('*.py')}\n    assert all(sha(Path(name)) == pin for name, pin in dependencies.items())\n    report =")
    runner = once(runner, "        original_assertions_preserved=True, human_listening=False", "        native_dependency_files=dependencies, test_package_bindings='explicit-loaded-package',\n        original_assertions_preserved=True, human_listening=False")
    runner = once(runner, "    parser.add_argument('--installed', type=Path)", "    parser.add_argument('--installed', type=Path)\n    parser.add_argument('--rubberband', type=Path, default=ROOT / 'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe')\n    parser.add_argument('--html-runtime', type=Path, default=ROOT / 'product/.runtime/html-motion-runtime-20261018-e2.json')")
    runner = once(runner, "    paths = [*SOURCE.glob('*.py'), *(ROOT / 'product/tests').glob('*.py'),", "    paths = [*[path for path in SOURCE.rglob('*') if path.is_file() and path.suffix.lower() in {'.py', '.mjs', '.json', '.c', '.dll', '.txt', '.cube'}],\n             ROOT / 'docs/specs/agent-project.schema.json', *(ROOT / 'product/tests').glob('*.py'),")
    (CANDIDATE / 'runner.py').write_text(runner, encoding='utf-8', newline='\n')
    changes = {}
    for path in sorted((ROOT / 'product/tests').glob('test_*.py')):
        generated = CANDIDATE / 'tests' / path.name
        current = CANDIDATE / 'test_delivery.py' if path.name == 'test_delivery.py' else path
        text = current.read_text(encoding='utf-8')
        rewritten, count = bind_test_file(text)
        if count:
            generated.parent.mkdir(exist_ok=True)
            generated.write_text(rewritten, encoding='utf-8', newline='\n')
            mapping['tests/' + path.name] = path.relative_to(ROOT).as_posix()
            changes[path.name] = count
    helper = CANDIDATE / 'tests/package_under_test.py'
    helper.parent.mkdir(exist_ok=True)
    helper.write_text(PACKAGE_HELPER, encoding='utf-8', newline='\n')
    mapping['tests/package_under_test.py'] = 'product/tests/package_under_test.py'
    for name in mapping:
        if name.endswith('.py'):
            compile((CANDIDATE / name).read_bytes(), name, 'exec')
    guard(freeze)
    report = dict(status='complete-correction-code-not-tested', cli_version='0.1.66',
        original_suite_unchanged=True, formal_activation=False, functional_tests_executed=False,
        items=['C01', 'C02', 'C03', 'C04', 'C05-native-dependencies', 'C05-installed-bindings'],
        predecessor={target: sha(ROOT / target) if (ROOT / target).is_file() else None for target in mapping.values()},
        mapping=mapping, files={name: sha(CANDIDATE / name) for name in mapping},
        original_test_names_preserved=True, test_path_rewrites=changes, preparer_sha256=sha(Path(__file__)))
    out = BASE / 'correction-code-r2'
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    save(CANDIDATE / 'implementation.json', report)
    save(out / 'verification.json', report)
    print(json.dumps(dict(status=report['status'], changed_test_files=len(changes), source_modified=False)), flush=True)


def owner_stopped(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        assert ctypes.get_last_error() == 87, 'Unable to verify original owner state'
        return
    try:
        code = wintypes.DWORD()
        assert kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != 259, 'Original test owner still live'
    finally:
        kernel.CloseHandle(handle)


def apply(pid):
    freeze = load(BASE / 'freeze-r1/verification.json')
    guard(freeze)
    terminal = load(BASE / 'source-all-r1/verification.json')
    assert terminal['status'] in {'passed', 'failed', 'interrupted'}
    assert terminal['discovered_tests'] == 4101 and terminal['frozen_equal']
    assert terminal['file_hashes'] == freeze['file_hashes']
    owner_stopped(pid)
    report = load(CANDIDATE / 'implementation.json')
    assert report['status'] == 'complete-correction-code-not-tested'
    for name, pin in report['predecessor'].items():
        assert (sha(ROOT / name) == pin) if pin is not None else not (ROOT / name).exists(), name
    assert all(sha(CANDIDATE / name) == pin for name, pin in report['files'].items())
    out = BASE / 'correction-apply-r2'
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    for name, pin in report['predecessor'].items():
        if pin is not None:
            backup = out / 'baseline' / name
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes((ROOT / name).read_bytes())
    for name, target in report['mapping'].items():
        path = ROOT / target
        temporary = path.with_name(path.name + '.delivery66-correction.tmp')
        with temporary.open('xb') as handle:
            handle.write((CANDIDATE / name).read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    assert all(sha(ROOT / name) == pin for name, pin in freeze['formal_guard'].items())
    save(out / 'verification.json', dict(status='correction-applied-not-tested', cli_version='0.1.66',
        original_test_terminal=terminal['status'], original_process_stopped=True,
        formal_activation=False, mapping=report['mapping'],
        new_hashes={target: sha(ROOT / target) for target in report['mapping'].values()}))
    print('Complete r3 correction applied after verified original termination; freeze r2 before testing.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--original-pid', type=int, default=32376)
    args = parser.parse_args()
    assert os.name == 'nt' and sys.dont_write_bytecode
    apply(args.original_pid) if args.apply else prepare()
