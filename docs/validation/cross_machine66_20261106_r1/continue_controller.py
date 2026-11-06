"""Run one gated native CLI66 cross-host CPU acceptance; never retry a start."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import subprocess
import sys
import time
import urllib.parse

PROJECT = Path(__file__).resolve().parents[3]
PRIVATE = PROJECT / 'local/agent-ffmpeg/cross-machine66-20261106-r1'
OPERATION = PROJECT / 'local/agent-ffmpeg/cross-machine66-controller-20261106-r1'
PUBLIC = PROJECT / 'docs/validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1'
CLIENT = Path('C:/Users/carzy/.codex/skills/remote-4090/scripts/windows_mcp.py')
NATIVE = PROJECT / 'docs/validation/run_delivery66_native.py'
EMBEDDED = Path('E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe')
REMOTE_ROOT = 'C:/dev/agent-editor-kit-upgrade-20261106-r1'
REMOTE_PYTHON = 'C:/dev/comfyUI/python_embeded/python.exe'
VERSIONS = {'before63': '0.1.63', 'upgrade66': '0.1.66', 'rollback63': '0.1.63', 'final66': '0.1.66'}


class ClientStillRunning(Exception):
    """Do not issue another device call while this owned client is still alive."""


def load(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value, *, replace=False):
    path = Path(path)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if not replace:
        with path.open('xb') as stream:
            stream.write(raw)
        return
    pending = path.with_suffix(path.suffix + '.pending')
    with pending.open('xb') as stream:
        stream.write(raw)
    os.replace(pending, path)


def state(phase, **details):
    save(OPERATION / 'state.json', dict(phase=phase,
        observed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), **details), replace=True)


def relative(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\0' in name:
        raise ValueError('Invalid evidence path')
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('Unsafe evidence path')
    allowed = bool(re.fullmatch(r'(verification|failure|state|launch|downloads-verified)\.json', name)
        or re.fullmatch(r'[a-zA-Z0-9_-]+\.(stdout|stderr)', name)
        or re.fullmatch(r'registration-[a-zA-Z0-9_-]+\.json', name)
        or re.fullmatch(r'case-(before63|upgrade66|rollback63|final66)/(verification|calls)\.json', name)
        or re.fullmatch(r'case-(before63|upgrade66|rollback63|final66)/imported/renders/cross-host\.mp4', name)
        or re.fullmatch(r'case-(before63|upgrade66|rollback63|final66)/logs/[a-zA-Z0-9_-]+\.(stdout|stderr)', name))
    if not allowed:
        raise ValueError('Evidence role is not allowed')
    return path


def classify(value, owner):
    if not isinstance(value, dict) or type(value.get('actual_process_live')) is not bool:
        raise ValueError('Remote observation lacks actual process state')
    for key in ('downloads_verified', 'verification_present', 'failure_present'):
        if type(value.get(key)) is not bool:
            raise ValueError('Invalid remote observation flag')
    launch = value.get('launch')
    if launch is not None:
        if not isinstance(launch, dict) or launch.get('owner_id') != owner['owner_id']:
            raise ValueError('Unexpected remote owner')
        for key in ('pid', 'creation_filetime'):
            if type(launch.get(key)) is not int or launch[key] <= 0:
                raise ValueError('Invalid native process identity')
        if str(launch.get('root', '')).replace('\\', '/').rstrip('/') != REMOTE_ROOT:
            raise ValueError('Unexpected owned root')
        if str(launch.get('executable', '')).replace('\\', '/').lower() != REMOTE_PYTHON.lower():
            raise ValueError('Unexpected remote interpreter')
    elif value['actual_process_live']:
        raise ValueError('Live observation has no process identity')
    if value['actual_process_live']:
        return 'running'
    remote_state=value.get('state')
    if remote_state is not None and not isinstance(remote_state,dict):
        raise ValueError('Malformed remote job state')
    phase = (remote_state or {}).get('phase')
    if value['failure_present'] or phase == 'failed':
        return 'failed'
    if launch is not None and phase == 'passed' and value['verification_present']:
        if not value['downloads_verified']:
            raise ValueError('Passed terminal has no verified download record')
        return 'passed'
    return 'bootstrap-pending' if launch is None else 'stopped-without-terminal'


def validate_preflight(summary, screenshot_hash, now):
    if summary.get('ok') is not True or summary.get('control', {}).get('state') not in ('ready', 'ai'):
        raise ValueError('Device preflight did not pass')
    device = summary.get('device', {})
    desktop = device.get('inputDesktop', {})
    owner = (device.get('foregroundOwner') or {}).get('Name', '').lower()
    if device.get('computerName', '').upper() != 'DESKTOP-TE44HE1':
        raise ValueError('Unexpected preflight host')
    if desktop.get('opened') is not True or desktop.get('name', '').lower() != 'default' or owner in ('lockapp.exe', 'logonui.exe'):
        raise ValueError('Remote desktop is unavailable')
    stamp = dt.datetime.fromisoformat(summary['startedAt'])
    if stamp.tzinfo is None or not 0 <= (now - stamp).total_seconds() <= 900:
        raise ValueError('Device preflight is stale')
    images = [Path(path) for row in summary.get('calls', []) if row.get('name') == 'Screenshot' for path in row.get('images', [])]
    if len(images) != 1 or not re.fullmatch('[a-f0-9]{64}', screenshot_hash):
        raise ValueError('One explicitly reviewed screenshot is required')
    if not images[0].is_file() or sha(images[0]) != screenshot_hash:
        raise ValueError('Reviewed screenshot differs from the device preflight')
    return images[0]


def validate_acceptance(root, parcels, references):
    report = load(root / 'verification.json')
    if report.get('status') != 'cross-machine-cli66-cpu-upgrade-rollback-passed' or report.get('cli_version') != '0.1.66':
        raise ValueError('Remote acceptance did not pass')
    for key in ('actual_offline_install', 'actual_base_only_configuration', 'actual_isolated_registration',
                'registration_conflict_preserved', 'old_archive_files_unchanged', 'old_private_configuration_unchanged',
                'new_archive_files_unchanged', 'cross_machine', 'cli66_cpu_upgrade_accepted'):
        if report.get(key) is not True:
            raise ValueError('Missing actual cross-host acceptance condition: ' + key)
    for key in ('generic_delivery_controller_tested', 'global_registration_changed', 'global_PATH_changed',
                'gpu_render', 'model_inference', 'human_listening', 'natural_quality_accepted', 'clean_host',
                'full_G34_accepted', 'full_goal_closed'):
        if report.get(key) is not False:
            raise ValueError('Unexpected scope claim: ' + key)
    if report.get('remote_hostname', '').upper() != 'DESKTOP-TE44HE1':
        raise ValueError('Unexpected accepted host')
    if report.get('old_application_modules') != 283 or report.get('new_application_modules') != 289:
        raise ValueError('Application inventory changed')
    if report.get('actual_registration_transitions') != list(VERSIONS.values()):
        raise ValueError('Missing upgrade or rollback transition')
    if report.get('downloads_verified') != {row['name']: row['sha256'] for row in parcels['files']}:
        raise ValueError('Downloaded artifacts differ from the primary parcels')
    if set(report.get('cases', {})) != set(VERSIONS):
        raise ValueError('Incomplete four-case acceptance')
    for label, version in VERSIONS.items():
        case = report['cases'][label]
        if case != load(root / ('case-' + label) / 'verification.json') or case.get('cli_version') != version:
            raise ValueError('Case receipt mismatch')
        for key in ('complete_RGBA_PCM_equal', 'complete_master_assets_equal', 'actual_registered_Skill'):
            if case.get(key) is not True:
                raise ValueError('Incomplete media replay')
        if case.get('source_fallback') is not False or case.get('status') != 'cross-host-baseline-passed':
            raise ValueError('Unexpected case implementation')
        actual, expected = case['actual'], case['expected']
        if expected != references[version]:
            raise ValueError('Case reference differs from the pinned primary version')
        if actual['decoded'] != expected['complete_decoded'] or actual['video'] != expected['video']:
            raise ValueError('Complete media or video clocks differ')
        if int(actual['video']['nb_read_frames']) != 60 or actual['audio'].get('finite_non_silent') is not True:
            raise ValueError('Incomplete or silent reference')
        movie = root / ('case-' + label) / 'imported/renders/cross-host.mp4'
        if not movie.is_file() or sha(movie) != actual['movie_sha256']:
            raise ValueError('Returned movie differs from the accepted remote output')
    for first, second in (('before63', 'rollback63'), ('upgrade66', 'final66')):
        if report['cases'][first]['actual']['decoded'] != report['cases'][second]['actual']['decoded']:
            raise ValueError('Repeated-version replay differs')
    return report


def run_action(label, script, arguments=(), timeout=300):
    with (OPERATION / (label + '.stdout')).open('xb') as stdout, (OPERATION / (label + '.stderr')).open('xb') as stderr:
        process = subprocess.Popen([str(EMBEDDED), '-E', '-B', '-u', '-X', 'utf8', str(script), *map(str, arguments)],
            cwd=PROJECT, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        identity = BOOT['process_identity'](process.pid)
        save(OPERATION / (label + '.process.json'), identity)
        deadline=time.monotonic()+timeout
        while True:
            try:
                code=process.wait(timeout=min(30,max(0.1,deadline-time.monotonic())))
                break
            except subprocess.TimeoutExpired:
                # Continue observing the SAME local handle before another RPC.
                state('local-client-still-running',action=label,client_identity=identity)
                if time.monotonic()>=deadline:
                    raise ClientStillRunning('Inspect the original local client handle; no second device call was issued')
    raw = (OPERATION / (label + '.stdout')).read_bytes()
    save(OPERATION / (label + '.result.json'), dict(exit_code=code, stdout_bytes=len(raw)))
    if code:
        raise RuntimeError('Retain and inspect the failed client action: ' + label)
    return json.loads(raw)


def stop_transfer(server):
    marker = PRIVATE / 'stop-transfer.marker'
    if not marker.exists():
        marker.touch(exist_ok=False)
    try:
        server.wait(timeout=15)
    except subprocess.TimeoutExpired:
        state('transfer-stop-still-pending', server=BOOT['process_identity'](server.pid))
        raise RuntimeError('Owned transfer has not closed; inspect its actual handle')
    if BOOT['same_process'](load(OPERATION / 'transfer.process.json')):
        raise RuntimeError('Owned transfer process still exists')


def publish_return(source, secrets):
    records=[]
    for path in source.rglob('*'):
        if not path.is_file():
            continue
        name=path.relative_to(source).as_posix()
        relative(name)
        ancestry=[path,*[parent for parent in path.parents if parent.is_relative_to(source)]]
        if any(getattr(parent.lstat(),'st_file_attributes',0)&0x400 for parent in ancestry):
            raise ValueError('Returned evidence contains a reparse point')
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()) or path.stat().st_size > 2 * 1024**2:
            raise ValueError('Unexpected returned evidence file')
        data=path.read_bytes()
        if any(value.encode('utf-8') in data for value in secrets if len(value)>=8):
            raise ValueError('Private transport material found in returned evidence')
        records.append((name,data))
    if sum(len(data) for name,data in records)>8*1024**2:
        raise ValueError('Returned evidence exceeds the aggregate budget')
    if PUBLIC.exists():
        raise FileExistsError('Preserve existing published cross-host evidence')
    pending=PUBLIC.with_name(PUBLIC.name+'.pending')
    pending.mkdir(parents=True,exist_ok=False)
    for name,data in records:
        target=pending/name
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(data)
    os.rename(pending,PUBLIC)
    return len(records)


def main(args):
    global BOOT
    assert os.name=='nt' and sys.dont_write_bytecode and sys.prefix==sys.base_prefix
    assert Path(sys.executable).resolve()==EMBEDDED.resolve()
    assert not OPERATION.exists(), 'Inspect the original controller; never restart this run blindly'
    BOOT=runpy.run_path(str(NATIVE),run_name='cross_machine_native_identity')
    config=load(CLIENT.parents[1]/'device.json')
    controller_root=Path(config['controller_root']).resolve()
    preflight=Path(args.preflight).resolve(strict=True)
    assert preflight.is_relative_to(controller_root), 'Use the installed Skill status record'
    summary=load(preflight)
    image=validate_preflight(summary,args.reviewed_screenshot_sha256,dt.datetime.now(dt.timezone.utc))
    assert image.resolve().is_relative_to(controller_root)
    code_phase=load(PROJECT/'docs/validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-controller-code-phase-r1/verification.json')
    contracts=load(PROJECT/'docs/validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-controller-contracts-r1/verification.json')
    assert code_phase['status']=='code-complete-frozen' and code_phase['code_completed_before_contract_tests']
    assert contracts['status']=='passed' and contracts['failures']==contracts['errors']==contracts['skipped']==0
    assert contracts['code_phase_sha256']==sha(PROJECT/'docs/validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-controller-code-phase-r1/verification.json')
    assert all(sha(PROJECT/name)==pin for name,pin in code_phase['files'].items())
    preparation=runpy.run_path(str(PRIVATE/'prepare_transfer.py'),run_name='cross_machine_readiness')
    preparation['ready']()
    parcels=load(PRIVATE/'parcels.json')
    assert parcels['primary_installed_whole_passed'] and parcels['primary_portable_kit_passed']
    assert len(parcels['files'])==6
    for row in parcels['files']:
        assert sha(row['path'])==row['sha256'] and Path(row['path']).stat().st_size==row['bytes']
    assert not any((PRIVATE/name).exists() for name in ('start-intent.json','transfer.json','stop-transfer.marker'))
    OPERATION.mkdir()
    save(OPERATION/'owner.json',dict(controller=BOOT['process_identity'](os.getpid()),
        script_sha256=sha(__file__),preflight_sha256=sha(preflight),reviewed_screenshot_sha256=sha(image),
        created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),native_only=True))
    server=None
    try:
        state('starting-owned-transfer')
        with (OPERATION/'transfer.stdout').open('xb') as stdout,(OPERATION/'transfer.stderr').open('xb') as stderr:
            server=subprocess.Popen([str(EMBEDDED),'-E','-B','-u','-X','utf8',str(PRIVATE/'transfer_server.py')],
                cwd=PRIVATE,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        save(OPERATION/'transfer.process.json',BOOT['process_identity'](server.pid))
        deadline=time.monotonic()+30
        while not (PRIVATE/'transfer.json').is_file():
            if server.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Owned transfer did not become ready')
            time.sleep(0.2)
        transfer=load(PRIVATE/'transfer.json')
        state('starting-remote-once')
        try:
            run_action('start',PRIVATE/'remote_control.py',['start'])
        except RuntimeError:
            if not (PRIVATE/'start-intent.json').is_file():raise
            state('start-observation-unconfirmed',restart_attempted=False)
        owner=load(PRIVATE/'start-intent.json')
        deadline=time.monotonic()+3600
        stopped=0
        latest=None
        for attempt in range(1,122):
            if time.monotonic()>deadline:raise TimeoutError('Retain the owned remote job and inspect its actual process')
            try:
                latest=run_action('status-'+str(attempt),PRIVATE/'remote_control.py',['status'])
            except RuntimeError:
                state('remote-observation-retry',attempt=attempt,restart_attempted=False)
                time.sleep(30)
                continue
            phase=classify(latest,owner)
            state('remote-'+phase,attempt=attempt,remote=latest,restart_attempted=False)
            if latest['downloads_verified'] and server is not None:
                stop_transfer(server);server=None
            if phase in ('passed','failed'):break
            stopped=stopped+1 if phase=='stopped-without-terminal' else 0
            if stopped>=2:break
            time.sleep(30)
        else:raise TimeoutError('Remote observation budget exhausted; preserve the existing run')
        fetched=run_action('fetch',PRIVATE/'remote_control.py',['fetch'])
        source=Path(fetched['directory']).resolve(strict=True)
        assert source.is_relative_to((PRIVATE/'remote-observations').resolve())
        if phase!='passed':
            state('remote-not-accepted',remote=latest,private_evidence=str(source),restart_attempted=False)
            return 1
        references={'0.1.66':load(PRIVATE/'primary/expected.json'),
                    '0.1.63':load(PROJECT/'local/agent-ffmpeg/cross-machine63-20261106-r2/primary/expected.json')}
        report=validate_acceptance(source,parcels,references)
        secrets=[transfer['base_url'],urllib.parse.urlsplit(transfer['base_url']).path.strip('/')]
        def secret_values(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if isinstance(item,str) and any(word in key.lower() for word in ('key','token','secret','password','authorization')):yield item
                    else:yield from secret_values(item)
            elif isinstance(value,list):
                for item in value:yield from secret_values(item)
        secrets.extend(secret_values(config))
        files=publish_return(source,secrets)
        state('passed',remote_verification_sha256=sha(source/'verification.json'),published_files=files,
            public_evidence=str(PUBLIC),actual_offline_install=report['actual_offline_install'],
            actual_transitions=report['actual_registration_transitions'],gpu_render=False,clean_host=False,
            full_G34_accepted=False,full_goal_closed=False)
        return 0
    except BaseException as exc:
        state('failed',error_type=type(exc).__name__,message='Inspect retained private controller logs',restart_attempted=False)
        raise
    finally:
        if server is not None:
            original_error=sys.exc_info()[0] is not None
            try:stop_transfer(server)
            except BaseException as cleanup_error:
                save(OPERATION/'cleanup-failure.json',dict(error_type=type(cleanup_error).__name__,
                     message='Inspect the original owned transfer process handle'))
                if not original_error:raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight',required=True,help='Fresh remote-4090 status summary.json after agent screenshot review')
    parser.add_argument('--reviewed-screenshot-sha256',required=True)
    sys.exit(main(parser.parse_args()))
