"""Resume remaining actual CLI66 acceptance after the retained audio-only replay failure."""
import argparse
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import delivery66_av_replay as replay

ROOT = replay.ROOT
HOME = ROOT / 'local/agent-ffmpeg/delivery66/r6-av-handoff-r1'
PYTHON = Path('E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe')
BOOT = 'import sys,runpy;from pathlib import Path;p=Path(sys.argv[1]).resolve();sys.path.insert(0,str(p.parent));sys.argv=sys.argv[1:];runpy.run_path(str(p),run_name="__main__")'
spec = importlib.util.spec_from_file_location('delivery66_native_identity', HERE / 'run_delivery66_native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def state(phase, **details):
    value = dict(phase=phase, observer=native.process_identity(os.getpid()),
                 observed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), **details)
    native.write(HOME / 'state.json', value)
    print(json.dumps(value, ensure_ascii=False), flush=True)


def call(label, tool, arguments):
    replay.check_contracts()
    replay.handoff.require(not (HOME / 'stop.marker').exists(), 'Explicit stop before next dependent action')
    command = [PYTHON, '-E', '-B', '-u', '-X', 'utf8', '-c', BOOT, tool, *arguments]
    env = dict(os.environ, TEMP=str(HOME / 'temp'), TMP=str(HOME / 'temp'),
               TMPDIR=str(HOME / 'temp'), PYTHONDONTWRITEBYTECODE='1')
    with (HOME / (label + '.stdout')).open('xb') as stdout, (HOME / (label + '.stderr')).open('xb') as stderr:
        child = subprocess.Popen(list(map(str, command)), cwd=ROOT, env=env,
            stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW)
        state(label, child=native.process_identity(child.pid), command=list(map(str, command)))
        code = child.wait()
    native.write(HOME / (label + '.result.json'), dict(exit_code=code,
        observed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat()))
    replay.handoff.require(code == 0, label + ' failed; preserve the original terminal and logs')


def supervise():
    try:
        replay.check_contracts()
        replay.handoff.require(not (HOME / 'temp').exists(), 'Do not restart an existing run')
        (HOME / 'temp').mkdir()
        replay_args = ['--run', 'r2', '--freeze-run', 'r6', '--tests-run', 'r6']
        call('av-package-r2', HERE / 'delivery66_av_replay.py', replay_args)
        package = replay.handoff.load(replay.delivery.BASE / 'package-replay-r2/verification.json')
        replay.handoff.require(package['status'] == 'passed'
            and package['source_generation_project_unchanged']
            and package['complete_rendered_RGBA_PCM_equal'], 'Actual full AV replay required')
        pins = ['--run', 'r1', '--freeze-run', 'r6', '--tests-run', 'r6', '--package-run', 'r2']
        call('descriptor-r1', HERE / 'delivery66.py', ['descriptor', *pins])
        for action in ['kit', 'verify-kit']:
            call(action + '-r1', HERE / 'delivery66_handoff.py', [action, *pins])
        qa = ROOT / 'local/agent-ffmpeg/cross-machine66-20261106-r1/prepare_transfer.py'
        prepared, preparation_error = False, None
        try:
            call('cross-machine-primary-r1', qa, ['primary'])
            call('cross-machine-parcels-r1', qa, ['parcels'])
            prepared = True
        except BaseException as exc:
            preparation_error = repr(exc)
            state('cross-machine-preparation-failed', error=preparation_error,
                  actual_fault_cases_still_required=True, remote_contacted=False)
        call('music-faults-r1', HERE / 'delivery66_music_faults.py', pins)
        faults = replay.handoff.load(replay.handoff.BASE / 'music-faults-r1/verification.json')
        replay.handoff.require(faults['status'] == 'passed'
            and set(faults['cases']) == {'cancel', 'timeout', 'publication-conflict'},
            'All three original actual-model fault cases are required')
        state('handoff-evidence-collected', both_whole_suites_passed=True,
            actual_CUDA_music_passed=True, complete_AV_package_replay_passed=True,
            portable_kit_passed=True, actual_model_faults_passed=True,
            cross_machine_inputs_prepared=prepared, cross_machine_preparation_error=preparation_error,
            remote_contacted=False, formal_activation=False, release_created=False, full_goal_closed=False)
    except BaseException as exc:
        state('failed', error=repr(exc), formal_activation=False, release_created=False)
        raise


def start():
    replay.check_contracts()
    replay.handoff.require(not HOME.exists(), 'Preserve earlier continuation; do not restart it')
    previous = ROOT / 'local/agent-ffmpeg/delivery66/r6-installed-handoff-observer-r1'
    old = replay.handoff.load(previous / 'state.json')
    replay.handoff.require(old['phase'] == 'failed' and not native.same_process(old['observer']),
                           'The original failed observer must be terminal')
    replay.handoff.require(replay.handoff.load(previous / 'package-r1.result.json')['exit_code'] == 1,
                           'Preserve the actual original failed replay')
    HOME.mkdir()
    with (HOME / 'observer.stdout').open('xb') as stdout, (HOME / 'observer.stderr').open('xb') as stderr:
        child = subprocess.Popen([str(PYTHON), '-E', '-B', '-u', '-X', 'utf8', str(Path(__file__).resolve()), 'supervise'],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP |
                          subprocess.CREATE_BREAKAWAY_FROM_JOB)
    identity = None
    for _ in range(40):
        identity = native.process_identity(child.pid)
        if identity is not None:
            break
        time.sleep(.05)
    native.write(HOME / 'owner.json', dict(observer=identity, pid=child.pid,
        created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        code_phase_sha256=replay.handoff.sha(replay.CODE_PHASE),
        original_suite_restarted=False, original_music_regenerated=False,
        remote_contacted=False, automatic_formal_activation=False))
    replay.handoff.require(identity is not None, 'Launch observation failed; inspect the same handle without restarting')
    print(json.dumps(dict(status='started', observer=identity, home=str(HOME)), ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'supervise', 'status'))
    args = parser.parse_args()
    replay.handoff.require(os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix
        and Path(sys.executable).resolve() == PYTHON.resolve(), 'Use the existing native embedded Python')
    if args.action == 'start':
        start()
    elif args.action == 'supervise':
        supervise()
    else:
        owner = replay.handoff.load(HOME / 'owner.json')
        value = replay.handoff.load(HOME / 'state.json')
        print(json.dumps(dict(state=value, observer_live=native.same_process(owner['observer']),
            child_live=native.same_process(value['child']) if 'child' in value else None), ensure_ascii=False))


if __name__ == '__main__':
    main()
