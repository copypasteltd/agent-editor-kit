"""Owned native second-host installation and real CLI63 upgrade baseline."""
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


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def save(name, value):
    target = ROOT / name
    temporary = target.with_name(target.name + '.pending')
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    os.replace(temporary, target)


def state(phase, **values):
    save('state.json', dict(phase=phase, pid=os.getpid(), executable=sys.executable,
                           elapsed_seconds=time.monotonic() - STARTED, **values))


def extract(archive, target):
    assert not target.exists()
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        assert 0 < len(entries) <= 2048
        names = [e.filename.casefold() for e in entries]
        assert len(set(names)) == len(names)
        assert sum(e.file_size for e in entries) <= 2048 * 1024**2
        for entry in entries:
            p = PurePosixPath(entry.filename)
            assert not p.is_absolute() and '\\' not in entry.filename
            assert all(part not in ('.', '..') and ':' not in part and not part.endswith(('.', ' ')) for part in p.parts)
            assert stat.S_IFMT(entry.external_attr >> 16) != stat.S_IFLNK and not entry.flag_bits & 1
            assert entry.file_size <= 512 * 1024**2
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


def call(name, argv, env, timeout=600):
    state(name)
    with (ROOT / (name + '.stdout')).open('xb') as stdout, (ROOT / (name + '.stderr')).open('xb') as stderr:
        result = subprocess.run(list(map(str, argv)), cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, timeout=timeout,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, name + ' failed; inspect stdout/stderr'
    return (ROOT / (name + '.stdout')).read_bytes()


def main():
    config = load(ROOT / 'transfer.json')
    assert os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix
    assert sys.version_info[:2] == (3, 13) and platform.machine().lower() in ('amd64', 'x86_64')
    assert socket.gethostname().casefold() == config['remote_hostname'].casefold()
    assert ROOT == Path('C:/dev/agent-editor-kit-validation-20261106-r2')
    assert not ROOT.is_symlink() and not getattr(ROOT, 'is_junction', lambda: False)()
    assert shutil.disk_usage(ROOT).free >= 5 * 1024**3
    temporary = ROOT / 'temp'
    temporary.mkdir()
    env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary),
               PYTHONDONTWRITEBYTECODE='1', PIP_NO_INDEX='1', PIP_NO_CACHE_DIR='1', PIP_CONFIG_FILE=os.devnull)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    downloads = ROOT / 'downloads'
    downloads.mkdir()
    pins = {}
    for row in config['files']:
        assert Path(row['name']).name == row['name'] and row['bytes'] <= 600 * 1024**2
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
    state('extracting')
    bundle, kit, tools = ROOT / 'bundle', ROOT / 'kit 中文 spaces', ROOT / 'tools'
    extract(downloads / 'application.zip', bundle)
    extract(downloads / 'skill.zip', kit)
    extract(downloads / 'tools.zip', tools)
    env['PATH'] = str(tools) + os.pathsep + env.get('PATH', '')
    installed = ROOT / 'installed 中文 spaces'
    manifest = load(kit / 'agent-ffmpeg-local-install-manifest.json')
    assert manifest['cli_version'] == '0.1.63' and manifest['manifest_sha256'] == config['manifest_sha256']
    inventory = load(kit / 'KIT-FILES.json')
    for row in inventory['files']:
        assert sha(kit / row['path']) == row['sha256']
    call('offline-install', [sys.executable, '-E', '-B', '-u', '-X', 'utf8', bundle / 'install.py',
         '--bundle', bundle, '--target', installed, '--manifest-sha256', config['manifest_sha256'],
         '--timeout-seconds', '600'], env)
    assert load(installed / 'receipt.json')['manifest_sha256'] == config['manifest_sha256']
    local = kit / 'local/agent-ffmpeg'
    local.mkdir(parents=True, exist_ok=True)
    # Legacy r58 predates --base-only. Configure only private host paths, leaving
    # every archived Skill/helper/guide byte unchanged; no model pack is bound.
    (local / 'community-runtime.json').write_text('{}\n', encoding='utf-8')
    (local / 'runtime.json').write_text(json.dumps(dict(release=manifest['release'], python=sys.executable,
        installed_directory=str(installed), manifest_sha256=config['manifest_sha256'],
        launcher_sha256=sha(installed / 'run.py'), native_only=True,
        community_config=str(local / 'community-runtime.json')), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    discovery = ROOT / 'isolated-discovery'
    call('isolated-registration', ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
         kit / 'register-agent-ffmpeg-local-skills.ps1', '-SkillsDirectory', discovery,
         '-ReceiptPath', ROOT / 'registration.json'], env)
    actual_skill = discovery / 'agent-ffmpeg-local-editor'
    assert actual_skill.resolve() == (kit / 'skills/agent-ffmpeg-local-editor').resolve()
    case = ROOT / 'actual-case'
    call('actual-cross-host-replay', [sys.executable, '-I', '-B', '-u', '-X', 'utf8', downloads / 'case.py',
        'replay', '--root', case, '--installed', installed, '--tools', tools,
        '--package', downloads / 'baseline.aevpkg.zip', '--expected', downloads / 'expected.json',
        '--entry', actual_skill / 'scripts/run.ps1'], env)
    accepted = load(case / 'verification.json')
    assert accepted['status'] == 'cross-host-baseline-passed'
    for row in inventory['files']:
        assert sha(kit / row['path']) == row['sha256']
    save('verification.json', dict(status='cross-machine-cli63-baseline-passed', cli_version='0.1.63',
        remote_hostname=socket.gethostname(), native_python=sys.executable, version=sys.version,
        downloads_verified=pins, actual_offline_install=True, actual_isolated_registration=True,
        accepted=accepted, kit_bytes_unchanged=True, global_registration_changed=False,
        global_PATH_changed=False, process_PATH_tools=str(tools), legacy_private_configuration=True,
        base_only_configurator_tested=False, gpu_render=False, model_inference=False,
        human_listening=False, natural_quality_accepted=False, clean_host=False, cross_machine=True,
        cli66_accepted=False, elapsed_seconds=time.monotonic()-STARTED))
    state('passed')


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        save('failure.json', dict(status='failed', error=repr(exc), cli66_accepted=False))
        state('failed', error=repr(exc))
        raise
