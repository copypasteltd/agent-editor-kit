"""Cancel an actually live native worker and verify its process has exited.

This checks cancellation during worker startup/integrity work. It does not claim
to interrupt a CUDA kernel or prove cancellation latency during host hashing.
"""
from __future__ import annotations
import argparse,ctypes,hashlib,json,subprocess,time
from ctypes import wintypes
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True);parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--installed',type=Path)
    args=parser.parse_args();assert args.run.replace('-','').isalnum()
    project=args.project.resolve(strict=True)
    assert project.is_relative_to(ROOT/'workspace')
    evidence=ROOT/'docs/validation/evidence/semantic-20261025-r1'/('inflight-'+args.run)
    evidence.mkdir(parents=True,exist_ok=False);(evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    marker=evidence/'cancel-marker';old={str(p) for p in project.glob('cache/semantic-jobs/*/*/worker-started.json')}
    immutable={name:sha(project/name) for name in ('project.json','rights-ledger.json')}
    if args.installed:
        prefix=['C:/Python313/python.exe','-I','-S','-B','-u','-X','utf8',str(args.installed.resolve(strict=True)/'run.py')]
    else:
        prefix=['C:/Python313/python.exe','-E','-B','-u','-X','utf8','-c',
                'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())',str(ROOT/'product/src')]
    command=[*prefix,'semantic','search','--project',str(project),'--index-id','natural-gpu','--query','a cat',
             '--device','cpu','--cancel-file',str(marker),'--timeout-seconds','600']
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.GetExitCodeProcess.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    def live(handle):
        code=wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
        return code.value==259
    process=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    handle=None;started=time.monotonic();record=dict(status='running',command=command,cli_pid=process.pid,
        development_source_only=not bool(args.installed),cancel_ack_max_seconds=10.,cuda_kernel_interruption_tested=False)
    try:
        while time.monotonic()-started<540:
            assert process.poll() is None,'CLI exited before a live worker was observed'
            markers=[p for p in project.glob('cache/semantic-jobs/*/*/worker-started.json') if str(p) not in old]
            if markers:
                assert len(markers)==1
                worker_file=markers[0];worker=json.loads(worker_file.read_bytes());request=json.loads((worker_file.parent/'request.json').read_bytes())
                assert worker['task']=='text' and worker['request_sha256']==request['request_sha256']
                handle=kernel.OpenProcess(0x1000|0x100000,False,worker['pid'])
                assert handle and live(handle)
                parent=subprocess.run(['powershell.exe','-NoProfile','-Command',
                    '(Get-CimInstance Win32_Process -Filter "ProcessId = '+str(int(worker['pid']))+'").ParentProcessId'],
                    capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
                assert parent.returncode==0 and int(parent.stdout.strip())==process.pid
                assert live(handle)
                record.update(worker=worker,worker_marker=str(worker_file),worker_live_before_cancel=True,
                              worker_direct_child_verified=True,seconds_to_worker=time.monotonic()-started)
                break
            time.sleep(.2)
        else:raise TimeoutError('No live worker observed within the declared startup budget')
        cancelled=time.monotonic();marker.write_text('Cancel the verified live test worker.\n',encoding='utf8')
        stdout,stderr=process.communicate(timeout=30)
        (evidence/'stdout.json').write_bytes(stdout);(evidence/'stderr.txt').write_bytes(stderr)
        value=json.loads(stdout.decode('utf-8-sig'))
        elapsed=time.monotonic()-cancelled
        assert process.returncode and not value['ok'] and value['errors'][0]['code']=='CANCELLED'
        assert elapsed<=record['cancel_ack_max_seconds'] and not live(handle)
        assert all(sha(project/name)==digest for name,digest in immutable.items())
        record.update(status='passed',cancel_ack_seconds=elapsed,worker_live_after_cli_exit=False,
            cli_exit_code=process.returncode,project_and_rights_unchanged=True,
            test_scope='Actual worker startup/integrity cancellation; no claim of GPU-kernel or host-hash latency acceptance.',
            generator_sha256=sha(Path(__file__)))
        (evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        print(json.dumps(dict(status='passed',cancel_ack_seconds=elapsed,worker_exited=True)),flush=True)
    except BaseException as exc:
        record.update(status='failed',error=str(exc),generator_sha256=sha(Path(__file__)))
        (evidence/'failure.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        raise
    finally:
        if process.poll() is None:
            subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=20,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            process.communicate(timeout=20)
        if handle:kernel.CloseHandle(handle)


if __name__=='__main__':main()
