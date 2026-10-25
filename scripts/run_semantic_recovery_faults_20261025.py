"""Actual installed model faults; source/old evidence and unrelated processes survive."""
from datetime import datetime, timezone
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-recovery-20261025-r1'
LIGHT = 'C:/Python313/python.exe'
FROZEN = ROOT / 'docs/validation/evidence/semantic-decision-20261025-r1/frozen'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')


def inventory(root):
    project = json.loads((root / 'project.json').read_bytes())
    return dict(metadata={name: sha(root / name) for name in ('project.json', 'rights-ledger.json')},
        assets={a['id']: sha(root / a['uri']) for a in project['assets']})


class WorkerHandle:
    def __init__(self, pid):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.OpenProcess(0x101000, False, pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def exited(self):
        return self.kernel.WaitForSingleObject(self.handle, 0) == 0

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle); self.handle = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--case', required=True, choices=('index-publication', 'calibration-publication',
        'calibration-commit', 'search-hard-stop', 'search-cancel', 'search-timeout', 'cleanup'))
    args = parser.parse_args(); assert args.run.replace('-', '').isalnum()
    installed = args.installed.resolve(strict=True)
    code = {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    assert code == {p.name: sha(p) for p in (ROOT / 'product/src/ai_ad_editor').glob('*.py')}
    out = BASE / args.run / args.case; out.mkdir(parents=True, exist_ok=False)
    (out / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    (out / 'fault-child.py').write_bytes((ROOT / 'scripts/semantic_recovery_fault_child_20261025.py').read_bytes())
    work = ROOT / 'workspace' / ('semantic-recovery-20261025-' + args.run)
    work.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'workspace/semantic-recovery-20261025-installed-r1/source'
    prefix = [LIGHT, '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py')]
    calls = []
    def cli(*arguments, success=True):
        argv = prefix + list(map(str, arguments)); started = time.monotonic()
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=1200, creationflags=subprocess.CREATE_NO_WINDOW)
        number = len(calls) + 1
        stdout, stderr = out / f'{number:02}.stdout.json', out / f'{number:02}.stderr.txt'
        stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
        value = json.loads(result.stdout.decode('utf-8-sig'))
        calls.append(dict(argv=argv, exit_code=result.returncode, ok=value.get('ok'), status=value.get('status'),
            elapsed_seconds=time.monotonic() - started, stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        save(out / 'calls.json', calls)
        print(json.dumps(dict(case=args.case, call=number, command=value.get('command'), status=value.get('status')), ensure_ascii=False), flush=True)
        assert bool(result.returncode == 0 and value['ok']) == success, value
        return value
    report = dict(status='running', case=args.case, installed=str(installed),
        started_at_utc=datetime.now(timezone.utc).isoformat(), native_windows=True, virtualization=False,
        fault_hooks_only_in_verification_harness=True, human_quality_acceptance=False)
    process, worker = None, None
    try:
        if args.case == 'cleanup':
            before = inventory(source)
            plan = cli('project', 'recover', '--project', source, '--cleanup-jobs', '--dry-run')
            assert inventory(source) == before
            recovery = cli('project', 'recover', '--project', source, '--cleanup-jobs')
            assert inventory(source) == before
            assert recovery['data']['job_recovery']['cleaned'] > 0
            queried = cli('semantic', 'search', '--project', source, '--index-id', 'images-v1',
                '--query', '一只猫，不是一杯咖啡', '--calibration-id', 'accept-cuda', '--kind', 'image', '--device', 'cuda')
            assert queried['data']['results'][0]['hits'][0]['asset_id'] in {'asset_c2', 'asset_i1'}
            assert inventory(source) == before
            report.update(status='passed', committed_assets_rights_and_profiles_unchanged=True,
                cleaned=recovery['data']['job_recovery']['cleaned'], real_query_after_cleanup=True)
        else:
            archive = work / (args.case + '.aevpkg.zip')
            project = work / args.case
            cli('convert', 'export', '--project', source, '--target-format', 'package', '--output', archive)
            cli('convert', 'import', '--input', archive, '--output', project)
            before = inventory(project); save(out / 'before.json', before)
            cancel = work / (args.case + '.cancel')
            common = ['--project', str(project), '--device', 'cuda', '--timeout-seconds', '600']
            if args.case == 'index-publication':
                arguments = ['semantic', 'index', *common, '--index-id', 'crash-index', '--adapter-id', 'siglip2', '--all-visual-assets']
            elif args.case.startswith('calibration-'):
                arguments = ['semantic', 'calibrate', *common, '--index-id', 'images-v1', '--calibration-id', 'crash-cal',
                    '--input', str(FROZEN / 'calibration.json'), '--kind', 'image', '--false-accept-rate', '.05', '--minimum-coverage', '.75']
            else:
                arguments = ['semantic', 'search', *common, '--index-id', 'images-v1', '--query', 'a cat',
                    '--kind', 'image', '--calibration-id', 'accept-cuda']
                if args.case == 'search-cancel': arguments += ['--cancel-file', str(cancel)]
                if args.case == 'search-timeout':
                    arguments[arguments.index('--timeout-seconds') + 1] = '1'
            checkpoint = out / 'checkpoint.json'
            spec = out / 'fault-spec.json'
            hook = 'after-commit' if args.case == 'calibration-commit' else 'after-publication'
            save(spec, dict(installed=str(installed), arguments=arguments, checkpoint=str(checkpoint), hook=hook))
            stdout, stderr = out / 'fault.stdout.txt', out / 'fault.stderr.txt'
            with stdout.open('xb') as first, stderr.open('xb') as second:
                argv = [LIGHT, '-I', '-S', '-B', '-u', '-X', 'utf8', str(out / 'fault-child.py'), str(spec)]
                fault_started = time.monotonic()
                process = subprocess.Popen(argv, cwd=ROOT, stdout=first, stderr=second, creationflags=subprocess.CREATE_NO_WINDOW)
                report['fault_process'] = dict(argv=argv, pid=process.pid)
                deadline = time.monotonic() + 1100
                observed = None
                while process.poll() is None:
                    if checkpoint.is_file():
                        try: observed = json.loads(checkpoint.read_bytes())
                        except (OSError, ValueError): pass
                        if observed: break
                    if args.case in ('search-hard-stop', 'search-cancel'):
                        for path in (project / 'cache/managed-jobs').glob('*/inference-cuda/worker-phase.json'):
                            try: phase = json.loads(path.read_bytes())
                            except (OSError, ValueError): continue
                            if phase.get('phase') == 'model-loading':
                                worker = WorkerHandle(phase['pid']); observed = dict(worker=phase, job=str(path.parents[1])); break
                        if observed: break
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Owned fault process still live beyond bounded test execution')
                    time.sleep(.05)
                if args.case == 'search-timeout':
                    process.wait(timeout=60)
                    value = json.loads(stdout.read_bytes())
                    assert process.returncode != 0 and any(r['code'] == 'PROCESS_TIMEOUT' for r in value['errors']), value
                    report.update(actual_timeout=True, timeout_stage='full command, may precede model loading')
                else:
                    assert observed is not None and process.poll() is None
                    save(out / 'observed-checkpoint.json', observed)
                    active = cli('project', 'recover', '--project', project, '--cleanup-jobs', '--dry-run')
                    assert any(r['status'] == 'active_or_locked_preserved' for r in active['data']['job_recovery']['jobs'])
                    if args.case == 'search-cancel':
                        cancel.write_text('cancel this owned semantic job\n', encoding='utf8')
                        process.wait(timeout=60)
                        value = json.loads(stdout.read_bytes())
                        assert process.returncode != 0 and any(r['code'] == 'CANCELLED' for r in value['errors']), value
                    else:
                        process.kill(); process.wait(timeout=30)
                    if worker:
                        end = time.monotonic() + 20
                        while not worker.exited() and time.monotonic() < end: time.sleep(.05)
                        assert worker.exited(), 'Owned model worker remained live'
                        report['owned_worker_handle_observed_exited'] = True
                    report['observed_fault_boundary'] = observed
            report['fault_process'].update(exit_code=process.returncode, elapsed_seconds=time.monotonic() - fault_started,
                stdout_sha256=sha(stdout), stderr_sha256=sha(stderr))
            frozen = inventory(project)
            plan = cli('project', 'recover', '--project', project, '--cleanup-jobs', '--dry-run')
            assert inventory(project) == frozen
            recovered = cli('project', 'recover', '--project', project, '--cleanup-jobs')
            after = inventory(project)
            if args.case == 'calibration-commit':
                assert before != after and after == frozen
                assert any(r['trees'][0]['status'] == 'referenced_preserved' for r in recovered['data']['job_recovery']['jobs'])
                value = cli('semantic', 'search', '--project', project, '--index-id', 'images-v1', '--query', 'a cat',
                    '--calibration-id', 'crash-cal', '--kind', 'image', '--device', 'cuda')
                assert value['data']['results'][0]['hits'][0]['asset_id'] in {'asset_c2', 'asset_i1'}
                report['real_query_of_committed_recovered_profile'] = True
            else:
                assert before == after
                for tree in ('semantic', 'semantic-calibration'):
                    assert not any('crash-' in p.read_text('utf8', errors='replace') for p in (project / 'assets' / tree).glob('*/index.json'))
                if observed and 'destination' in observed: assert not Path(observed['destination']).exists()
            assert recovered['data']['job_recovery']['cleaned'] > 0
            save(out / 'after.json', after)
            cli('validate', '--project', project)
            report.update(status='passed', dry_run_metadata_unchanged=True,
                original_inputs_preserved=True, cleaned=recovered['data']['job_recovery']['cleaned'],
                metadata_rollback_verified=args.case != 'calibration-commit',
                committed_metadata_preserved=args.case == 'calibration-commit')
        assert code == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
        report.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), installed_bytes_unchanged=True, calls=len(calls))
        save(out / 'verification.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except BaseException as exc:
        if process is not None and process.poll() is None:
            process.kill(); process.wait(timeout=30)
        report.update(status='failed', error=repr(exc), finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out / 'verification.json', report)
        raise
    finally:
        if worker is not None: worker.close()


if __name__ == '__main__': main()
