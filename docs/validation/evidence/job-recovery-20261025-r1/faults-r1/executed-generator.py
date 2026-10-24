"""Hard-stop real installed four-source jobs at explicit lifecycle boundaries."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import time

from verify_four_stems_20261025 import ROOT, ROLES, sha, write

WRAPPER = '''from pathlib import Path
import json,os,sys,time
installed,phase,barrier=Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3])
sys.path[:]=[str(installed/'site'),*[p for p in sys.path if not {'site-packages','dist-packages'} & set(Path(p).parts)]]
os.environ.setdefault('AI_AD_EDITOR_RUNTIME_DIR',str(installed/'runtime'))
from ai_ad_editor.cli import main
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.job_workspaces import Workspace
from ai_ad_editor import project
def pause(point):
 atomic_write_json(barrier,dict(phase=point,cli_pid=os.getpid(),injection='observation barrier only; no DSP/model/quality changes'))
 while True: time.sleep(.1)
original_publish=Workspace.publish
def publish(self,stage,destination):
 original_publish(self,stage,destination)
 if phase=='first-publication': pause(phase)
Workspace.publish=publish
original_commit=project.commit_project_transaction
def commit(root,transaction_id):
 if phase=='prepared-metadata': pause(phase)
 result=original_commit(root,transaction_id)
 if phase=='committed-metadata': pause(phase)
 return result
project.commit_project_transaction=commit
raise SystemExit(main(sys.argv[4:]))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    installed, project, evidence = args.installed.resolve(strict=True), args.project.resolve(strict=True), args.evidence.resolve()
    assert project.is_relative_to(ROOT / 'local') and evidence.is_relative_to(ROOT / 'docs/validation/evidence')
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    wrapper = evidence / 'boundary-wrapper.py'
    wrapper.write_text(WRAPPER, encoding='utf8', newline='\n')
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py')]
    calls, cases = [], []

    def invoke(*argv):
        command = [*prefix, *map(str, argv)]
        started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=900, creationflags=subprocess.CREATE_NO_WINDOW)
        name = '%02d' % (len(calls) + 1)
        (evidence / (name + '-stdout.json')).write_bytes(result.stdout)
        (evidence / (name + '-stderr.txt')).write_bytes(result.stderr)
        calls.append(dict(argv=list(map(str, argv)), exit_code=result.returncode, seconds=time.monotonic()-started))
        write(evidence / 'calls.json', calls)
        assert result.returncode == 0, result.stderr.decode('utf8', 'replace')[-3000:]
        value = json.loads(result.stdout.decode('utf-8-sig'))
        assert value['ok'], value
        return value

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD], wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes, kernel.WaitForSingleObject.restype = [wintypes.HANDLE,wintypes.DWORD], wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    names = ('project.json','project.lock.json','rights-ledger.json','models/audio-adapters.json')
    metadata = lambda: {name:sha(project/name) for name in names}
    original_source = project / 'assets' / 'source-preservation-marker.bin'
    assert not original_source.exists()
    original_source.write_bytes(b'Fixture: preserve unregistered user source during cleanup')
    source_hash = sha(original_source)
    try:
        assert invoke('version')['data']['cli_version'] == '0.1.7'
        for phase in ('worker-loading','first-publication','prepared-metadata','committed-metadata'):
            before = metadata()
            initial_jobs = set(project.glob('cache/managed-jobs/job-*'))
            assert not initial_jobs, 'Start with no owned stale jobs; do not reset a live or failed run'
            case_dir = evidence / phase
            case_dir.mkdir()
            marker, barrier = case_dir/'cancel', case_dir/'barrier.json'
            stem_prefix = 'crash_' + phase.replace('-', '_')
            command = [sys.executable,'-I','-S','-B','-u','-X','utf8',str(wrapper),str(installed),phase,str(barrier),
                'audio','separate-stems','--project',str(project),'--asset-id','controlled_mix','--adapter-id','four',
                '--prefix',stem_prefix,'--apply','--device','cuda','--timeout-seconds','600','--cancel-file',str(marker)]
            process = subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
            handle, child = None, None
            started = time.monotonic()
            try:
                while time.monotonic()-started < 600:
                    assert process.poll() is None, 'Owner ended before the requested observation boundary'
                    if phase == 'worker-loading':
                        requests = list(project.glob('cache/managed-jobs/job-*/request.json'))
                        if requests:
                            query = '$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); Get-CimInstance Win32_Process -Filter "ParentProcessId = '+str(process.pid)+'" | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress'
                            result = subprocess.run(['powershell.exe','-NoProfile','-Command',query],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
                            if result.returncode == 0 and result.stdout.strip():
                                rows=json.loads(result.stdout.decode('utf-8-sig')); rows=rows if isinstance(rows,list) else [rows]
                                found=[row for row in rows if 'stem_separation_worker.py' in str(row.get('CommandLine'))]
                                if found:
                                    assert len(found)==1
                                    child=found[0]
                                    handle=kernel.OpenProcess(0x1000|0x100000,False,int(child['ProcessId']))
                                    assert handle and kernel.WaitForSingleObject(handle,0)==258
                                    requests=list(project.glob('cache/managed-jobs/job-*/request.json'))
                                    assert any(str(path).casefold() in child['CommandLine'].casefold() for path in requests)
                                    break
                    elif barrier.is_file():
                        record=json.loads(barrier.read_bytes())
                        assert record['phase']==phase and record['cli_pid']==process.pid
                        break
                    time.sleep(.05)
                else:
                    raise TimeoutError('Requested boundary not observed; live owner will be cancelled, not restarted')
                jobs = list(project.glob('cache/managed-jobs/job-*'))
                assert len(jobs)==1
                job=jobs[0]
                descriptor=json.loads((job/'job.json').read_bytes())
                write(case_dir/'job-before-stop.json',descriptor)
                if (job/'response.json').exists():
                    write(case_dir/'worker-before-stop.json',json.loads((job/'response.json').read_bytes()))
                before_stop=metadata()
                journal_pending=(project/'operations/project-transaction.json').exists()
                expected_outputs=0 if phase=='worker-loading' else (1 if phase=='first-publication' else 4)
                assert len(descriptor['outputs'])==expected_outputs
                if phase in ('worker-loading','first-publication'):
                    assert before_stop==before
                elif phase=='prepared-metadata':
                    assert journal_pending and before_stop['project.json']!=before['project.json']
                else:
                    assert not journal_pending and before_stop['project.json']!=before['project.json']
                stopped=time.monotonic()
                process.kill()  # Deliberately only the known CLI owner; native job must end its descendants.
                stdout,stderr=process.communicate(timeout=20)
                (case_dir/'stopped-stdout.txt').write_bytes(stdout);(case_dir/'stopped-stderr.txt').write_bytes(stderr)
                if handle:
                    assert kernel.WaitForSingleObject(handle,5000)==0, 'Owned native worker survived owner termination'
                after_stop=metadata()
                planned=invoke('project','recover','--project',project,'--cleanup-jobs','--dry-run')
                assert metadata()==after_stop and job.exists(), 'Dry run changed interrupted state'
                recovered=invoke('project','recover','--project',project,'--cleanup-jobs')
                cleanup=recovered['data']['job_recovery']
                assert cleanup['cleaned']==1 and not job.exists(),cleanup
                files=[project/'assets/derived'/(stem_prefix+'_'+role+'.wav') for role in ROLES]
                if phase=='committed-metadata':
                    assert all(path.is_file() for path in files)
                    assert metadata()==before_stop
                    assert all(row['status']=='referenced_preserved' for row in cleanup['jobs'][0]['outputs'])
                else:
                    assert not any(path.exists() for path in files)
                    assert metadata()==before
                invoke('validate','--project',project)
                repeated=invoke('project','recover','--project',project,'--cleanup-jobs')
                assert repeated['data']['job_recovery']['cleaned']==0
                assert sha(original_source)==source_hash
                case=dict(phase=phase,cli_pid=process.pid,worker=child,hard_stop_owner_only=True,
                    worker_exit_confirmed=bool(handle),stop_and_recovery_seconds=time.monotonic()-stopped,
                    journal_pending_before_stop=journal_pending,published_outputs_before_stop=expected_outputs,
                    dry_run_metadata_unchanged=True,metadata_recovered_or_committed_preserved=True,
                    unregistered_user_source_preserved=True,cleanup=cleanup,
                    real_model_forwards=0 if phase=='worker-loading' else 2,
                    barrier_injection='none' if phase=='worker-loading' else 'pause only; actual installed model/DSP/publication/transaction unchanged')
                cases.append(case);write(case_dir/'verification.json',dict(status='passed',**case))
                print(json.dumps(dict(phase=phase,status='passed',published=expected_outputs)),flush=True)
            finally:
                if process.poll() is None:
                    marker.touch()
                    try:process.communicate(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill();process.communicate(timeout=10)
                if handle:kernel.CloseHandle(handle)
        result=dict(status='passed',installed=str(installed),project=str(project),regular_cli_calls=len(calls),
            hard_stopped_cli_calls=len(cases),real_model_forwards=sum(case['real_model_forwards'] for case in cases),
            native_windows=True,virtualization=False,taskkill_used=False,source_fallback=False,cases=cases,
            human_listening=False,full_G33_closed=False,generator_sha256=sha(Path(__file__)))
        write(evidence/'verification.json',result)
    except BaseException as error:
        write(evidence/'failure.json',dict(status='failed',reason=str(error),cases=cases,calls=calls))
        raise


if __name__=='__main__':main()
