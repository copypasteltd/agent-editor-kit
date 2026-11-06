"""Native second-host CLI66 install and explicit isolated 63/66 registration rollback."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import socket
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
STARTED = time.monotonic()
EXPECTED_ROOT = Path('C:/dev/agent-editor-kit-upgrade-20261106-r1')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    path = Path(path)
    assert path.is_file() and path.stat().st_size <= 8 * 1024**2
    return json.loads(path.read_bytes())


def save(name, value):
    target = ROOT / name
    assert target.parent == ROOT
    temporary = target.with_name(target.name + '.pending')
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    os.replace(temporary, target)


def state(phase, **values):
    save('state.json', dict(phase=phase, pid=os.getpid(), executable=sys.executable,
        observed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        elapsed_seconds=time.monotonic() - STARTED, **values))


def plain_directory(path):
    path = Path(path)
    assert path.is_dir() and not path.is_symlink() and not path.is_junction(), str(path)


def relative(name):
    assert isinstance(name, str) and name and '\\' not in name
    path = PurePosixPath(name)
    assert not path.is_absolute() and path.as_posix() == name
    assert all(part not in ('.', '..') and ':' not in part and not part.endswith(('.', ' ')) for part in path.parts)
    assert all(part.split('.', 1)[0].upper() not in {'CON','PRN','AUX','NUL',
        *('COM' + str(i) for i in range(1,10)), *('LPT' + str(i) for i in range(1,10))} for part in path.parts)
    return path


def extract(archive, target):
    assert not target.exists()
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        assert 0 < len(entries) <= 2048
        names = [entry.filename.casefold() for entry in entries]
        assert len(names) == len(set(names)) and sum(e.file_size for e in entries) <= 2048 * 1024**2
        for entry in entries:
            relative(entry.filename.rstrip('/'))
            assert stat.S_IFMT(entry.external_attr >> 16) != stat.S_IFLNK
            assert not entry.flag_bits & 1 and entry.file_size <= 512 * 1024**2
        assert zipped.testzip() is None
        target.mkdir()
        for entry in entries:
            path = target.joinpath(*PurePosixPath(entry.filename).parts)
            assert path.resolve().is_relative_to(target.resolve())
            if entry.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(entry) as source, path.open('xb') as output:
                    shutil.copyfileobj(source, output, 1024**2)


def call(name, argv, env, *, failure=False, timeout=600):
    assert name.replace('-', '').isalnum()
    state(name)
    with (ROOT / (name + '.stdout')).open('xb') as stdout, (ROOT / (name + '.stderr')).open('xb') as stderr:
        result = subprocess.run(list(map(str, argv)), cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    assert (result.returncode != 0) if failure else (result.returncode == 0), name + ': inspect retained logs'
    return (ROOT / (name + '.stdout')).read_bytes()


def application_files(installed):
    return {path.name: sha(path) for path in sorted((installed / 'site/ai_ad_editor').glob('*.py'))}


def kit_files(kit):
    inventory = load(kit / 'KIT-FILES.json')
    assert inventory['skill_count'] == 1 and inventory['module_count'] == 17
    records = {}
    for row in inventory['files']:
        name = relative(row['path']).as_posix()
        path = kit / name
        assert path.resolve().is_relative_to(kit.resolve()) and path.is_file()
        assert name.casefold() not in records and path.stat().st_size == row['bytes']
        assert sha(path) == row['sha256']
        records[name.casefold()] = row['sha256']
    return records


def global_skills():
    roots = {Path(os.environ['USERPROFILE']) / '.codex/skills'}
    if os.environ.get('CODEX_HOME'):
        roots.add(Path(os.environ['CODEX_HOME']) / 'skills')
    result = {}
    for folder in sorted(roots):
        if folder.is_dir():
            for entry in sorted(folder.iterdir()):
                document = entry / 'SKILL.md'
                result[str(entry)] = dict(target=str(entry.resolve()),
                    skill_sha256=sha(document) if document.is_file() else None)
    return result


def registrar(kit, discovery, receipt):
    return ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        kit / 'register-agent-ffmpeg-local-skills.ps1', '-SkillsDirectory', discovery,
        '-ReceiptPath', ROOT / receipt]


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def unlink_expected(discovery, target, label, env):
    assert discovery.is_relative_to(ROOT) and discovery.parent == ROOT
    plain_directory(discovery)
    link = discovery / 'agent-ffmpeg-local-editor'
    assert link.is_junction() and link.resolve() == target.resolve()
    command = f"""$ErrorActionPreference='Stop'
$AekLink={literal(link)}
$AekExpected={literal(target)}
$AekItem=Get-Item -LiteralPath $AekLink -Force
if ($AekItem.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$AekItem.Target).TrimEnd('\\') -ne [IO.Path]::GetFullPath($AekExpected).TrimEnd('\\')) {{ throw 'Preserve unexpected registration' }}
[IO.Directory]::Delete($AekLink)
"""
    call('unlink-' + label, ['powershell.exe', '-NoProfile', '-Command', command], env)
    assert not link.exists() and target.is_dir()


def register(label, kit, discovery, version, env):
    receipt = 'registration-' + label + '.json'
    call('register-' + label, registrar(kit, discovery, receipt), env)
    value = load(ROOT / receipt)
    assert value['status'] == 'registered' and value['registered_cli_version'] == version
    assert value['skill_count'] == 1 and value['module_count'] == 17 and value['launcher_preflight_verified']
    assert [p.name for p in discovery.iterdir()] == ['agent-ffmpeg-local-editor']
    assert (discovery / 'agent-ffmpeg-local-editor').resolve() == (kit / 'skills/agent-ffmpeg-local-editor').resolve()


def transition(label, previous, current, discovery, version, previous_version, env):
    unlink_expected(discovery, previous / 'skills/agent-ffmpeg-local-editor', label, env)
    try:
        register(label, current, discovery, version, env)
    except BaseException:
        link = discovery / 'agent-ffmpeg-local-editor'
        if not link.exists() and not link.is_junction():
            register('restore-' + label, previous, discovery, previous_version, env)
        raise


def replay(label, version, installed, discovery, package, expected, tools, env):
    output = ROOT / ('case-' + label)
    call('replay-' + label, [sys.executable, '-I', '-B', '-u', '-X', 'utf8', ROOT / 'downloads/case.py',
        'replay', '--cli-version', version, '--root', output, '--installed', installed, '--tools', tools,
        '--package', package, '--expected', expected,
        '--entry', discovery / 'agent-ffmpeg-local-editor/scripts/run.ps1'], env)
    result = load(output / 'verification.json')
    assert result['status'] == 'cross-host-baseline-passed' and result['cli_version'] == version
    assert result['complete_RGBA_PCM_equal'] and result['complete_master_assets_equal']
    assert result['actual_registered_Skill'] and result['source_fallback'] is False
    return result


def main():
    assert os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix
    assert sys.version_info[:2] == (3, 13) and platform.machine().lower() in ('amd64', 'x86_64')
    assert ROOT == EXPECTED_ROOT and Path(sys.executable).resolve() == Path('C:/dev/comfyUI/python_embeded/python.exe').resolve()
    plain_directory(ROOT)
    config = load(ROOT / 'transfer.json')
    assert socket.gethostname().casefold() == config['remote_hostname'].casefold()
    assert config['cli_version'] == '0.1.66' and config['primary_installed_whole_passed'] is True
    assert config['primary_portable_kit_passed'] is True and shutil.disk_usage(ROOT).free >= 5 * 1024**3
    previous = config['previous']
    old_root = Path(previous['remote_root'])
    assert old_root == Path('C:/dev/agent-editor-kit-validation-20261106-r2')
    plain_directory(old_root)
    assert load(old_root / 'ownership.json')['owner_id'] == previous['owner_id']
    assert sha(old_root / 'verification.json') == previous['remote_verification_sha256']
    assert load(old_root / 'state.json')['phase'] == 'passed'
    old_kit, old_installed, tools = old_root / 'kit 中文 spaces', old_root / 'installed 中文 spaces', old_root / 'tools'
    for directory in (old_kit, old_installed, tools):
        plain_directory(directory)
    old_expected, old_package = old_root / 'downloads/expected.json', old_root / 'downloads/baseline.aevpkg.zip'
    assert sha(old_expected) == previous['expected_sha256'] and sha(old_package) == previous['package_sha256']
    expected_old = load(old_expected)
    assert expected_old['cli_version'] == '0.1.63'
    assert application_files(old_installed) == expected_old['application_files'] and len(expected_old['application_files']) == 283
    assert all(sha(tools / name) == pin for name, pin in expected_old['tools'].items())
    old_inventory = kit_files(old_kit)
    private_paths = ('local/agent-ffmpeg/runtime.json', 'local/agent-ffmpeg/community-runtime.json')
    old_private = {name: sha(old_kit / name) for name in private_paths}
    globals_before, path_before = global_skills(), os.environ.get('PATH')
    temporary = ROOT / 'temp'
    temporary.mkdir()
    env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary),
        PYTHONDONTWRITEBYTECODE='1', PIP_NO_INDEX='1', PIP_NO_CACHE_DIR='1', PIP_CONFIG_FILE=os.devnull)
    env['PATH'] = str(tools) + os.pathsep + env.get('PATH', '')
    downloads = ROOT / 'downloads'
    downloads.mkdir()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    pins = {}
    for row in config['files']:
        assert Path(row['name']).name == row['name'] and 0 < row['bytes'] <= 600 * 1024**2
        target = downloads / row['name']
        pending = target.with_suffix(target.suffix + '.part')
        completed, last = 0, 0.0
        with opener.open(config['base_url'] + '/' + row['name'], timeout=60) as response, pending.open('xb') as output:
            while block := response.read(1024**2):
                completed += len(block)
                assert completed <= row['bytes']
                output.write(block)
                if time.monotonic() - last >= 1:
                    state('downloading', name=row['name'], completed_bytes=completed, total_bytes=row['bytes'])
                    last = time.monotonic()
            output.flush()
            os.fsync(output.fileno())
        assert completed == row['bytes'] and sha(pending) == row['sha256'], row['name']
        assert not target.exists()
        os.replace(pending, target)
        pins[row['name']] = row['sha256']
    save('downloads-verified.json', dict(status='verified', files=pins))
    bundle, kit = ROOT / 'bundle', ROOT / '工具包 中文 spaces'
    extract(downloads / 'application.zip', bundle)
    extract(downloads / 'skill.zip', kit)
    new_inventory = kit_files(kit)
    inventory = load(kit / 'KIT-FILES.json')
    assert inventory['packaging_source_files'] == config['packaging_source_files']
    manifest = load(kit / 'agent-ffmpeg-local-install-manifest.json')
    assert manifest['cli_version'] == '0.1.66' and len(manifest['files']) == 95
    assert manifest['manifest_sha256'] == config['manifest_sha256']
    installed = ROOT / '安装版 中文 spaces'
    call('offline-install', [sys.executable, '-E', '-B', '-u', '-X', 'utf8', bundle / 'install.py',
        '--bundle', bundle, '--target', installed, '--manifest-sha256', config['manifest_sha256'],
        '--timeout-seconds', '600'], env)
    expected = load(downloads / 'expected.json')
    assert expected['cli_version'] == '0.1.66' and expected['installed_manifest_sha256'] == config['manifest_sha256']
    assert application_files(installed) == expected['application_files'] and len(expected['application_files']) == 289
    configuration = json.loads(call('base-configuration', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
        kit / 'scripts/activate_community_runtime.py', '--installed', installed, '--base-only'], env))
    assert configuration['configuration_mode'] == 'base-only' and configuration['verified_packs'] == []
    assert configuration['model_verification_performed'] is False
    assert load(kit / 'local/agent-ffmpeg/community-runtime.json') == {}
    assert Path(load(kit / 'local/agent-ffmpeg/runtime.json')['installed_directory']) == installed
    discovery = ROOT / 'isolated-discovery'
    cases = {}
    register('before63', old_kit, discovery, '0.1.63', env)
    cases['before63'] = replay('before63', '0.1.63', old_installed, discovery, old_package, old_expected, tools, env)
    conflict_receipt = ROOT / 'registration-conflict.json'
    call('registration-conflict', registrar(kit, discovery, conflict_receipt.name), env, failure=True)
    assert not conflict_receipt.exists()
    assert (discovery / 'agent-ffmpeg-local-editor').resolve() == (old_kit / 'skills/agent-ffmpeg-local-editor').resolve()
    transition('upgrade66', old_kit, kit, discovery, '0.1.66', '0.1.63', env)
    cases['upgrade66'] = replay('upgrade66', '0.1.66', installed, discovery,
        downloads / 'baseline.aevpkg.zip', downloads / 'expected.json', tools, env)
    transition('rollback63', kit, old_kit, discovery, '0.1.63', '0.1.66', env)
    cases['rollback63'] = replay('rollback63', '0.1.63', old_installed, discovery, old_package, old_expected, tools, env)
    transition('final66', old_kit, kit, discovery, '0.1.66', '0.1.63', env)
    cases['final66'] = replay('final66', '0.1.66', installed, discovery,
        downloads / 'baseline.aevpkg.zip', downloads / 'expected.json', tools, env)
    assert cases['upgrade66']['actual']['decoded'] == cases['final66']['actual']['decoded']
    assert cases['before63']['actual']['decoded'] == cases['rollback63']['actual']['decoded']
    assert new_inventory == kit_files(kit) and old_inventory == kit_files(old_kit)
    assert old_private == {name: sha(old_kit / name) for name in private_paths}
    assert application_files(old_installed) == expected_old['application_files']
    assert globals_before == global_skills() and path_before == os.environ.get('PATH')
    save('verification.json', dict(status='cross-machine-cli66-cpu-upgrade-rollback-passed', cli_version='0.1.66',
        remote_hostname=socket.gethostname(), native_python=sys.executable, version=sys.version,
        downloads_verified=pins, actual_offline_install=True, actual_base_only_configuration=True,
        actual_isolated_registration=True, registration_conflict_preserved=True,
        actual_registration_transitions=['0.1.63','0.1.66','0.1.63','0.1.66'],
        transition_method='explicit-owned-isolated-junction-unlink-then-original-registrar',
        generic_delivery_controller_tested=False, cases=cases, old_application_modules=283, new_application_modules=289,
        old_archive_files_unchanged=True, old_private_configuration_unchanged=True, new_archive_files_unchanged=True,
        global_registration_changed=False, global_PATH_changed=False, gpu_render=False, model_inference=False,
        human_listening=False, natural_quality_accepted=False, clean_host=False, cross_machine=True,
        cli66_cpu_upgrade_accepted=True, full_G34_accepted=False, full_goal_closed=False,
        elapsed_seconds=time.monotonic() - STARTED))
    state('passed')


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        save('failure.json', dict(status='failed', error=repr(exc), full_G34_accepted=False))
        state('failed', error=repr(exc))
        raise
