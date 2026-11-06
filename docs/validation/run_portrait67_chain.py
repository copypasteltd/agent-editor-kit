"""Continue one already-live native source suite, then run dependent gates once.

The source process must be bound by PID, creation FILETIME and executable.
Observation never restarts a task. Any failed/missing terminal stops the chain.
"""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE/'evidence/portrait67-20261106-r1'
LOCAL = ROOT/'local/agent-ffmpeg/portrait67-20261106-r1'


def load_module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path, value):
    temporary=path.with_name(path.name+'.pending')
    with temporary.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-identity',type=Path,required=True)
    parser.add_argument('--run',required=True)
    parser.add_argument('--freeze-run',default='r1')
    parser.add_argument('--source-run',default='r1')
    args=parser.parse_args()
    assert os.name=='nt' and sys.dont_write_bytecode and sys.prefix==sys.base_prefix
    assert all(value.isalnum() for value in (args.run,args.freeze_run,args.source_run))
    native=load_module('portrait_existing_process_identity',HERE/'run_delivery66_native.py')
    wrapper=load_module('portrait_complete_batch',HERE/'portrait67.py')
    h=wrapper.harness();frozen=h.load(BASE/('freeze-'+args.freeze_run)/'verification.json')
    h.unchanged(frozen)
    identity=h.load(args.source_identity)
    assert native.process_identity(identity['pid'])==identity,'The original source-suite process is no longer this live process'
    assert Path(identity['executable']).resolve()==Path(sys.executable).resolve()
    out=BASE/('chain-'+args.run);out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    retained={str(path):sha(path) for path in (Path(__file__),HERE/'portrait67.py',HERE/'run_delivery66_native.py',
        args.source_identity,BASE/('freeze-'+args.freeze_run)/'verification.json')}
    state=dict(status='waiting-existing-source',source_identity=identity,runner_pid=os.getpid(),
        source_restarted=False,code_completed_before_execution=True,retained_inputs=retained,steps=[],
        formal_activation=False,full_goal_closed=False)
    save(out/'verification.json',state)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.GetExitCodeProcess.restype=wintypes.BOOL
    handle=kernel.OpenProcess(0x1000|0x00100000,False,identity['pid'])
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    try:
        assert native.process_identity(identity['pid'])==identity
        while True:
            result=kernel.WaitForSingleObject(handle,1000)
            if result==0:break
            if result!=258:raise ctypes.WinError(ctypes.get_last_error())
        exit_code=wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(exit_code)):raise ctypes.WinError(ctypes.get_last_error())
        state['original_source_exit_code']=exit_code.value
        assert exit_code.value==0,'Original source suite failed; no downstream gate may start'
    except BaseException as exc:
        state.update(status='stopped',failure_phase='source-all',error=repr(exc));save(out/'verification.json',state)
        raise
    finally:kernel.CloseHandle(handle)
    source_path=BASE/('source-all-'+args.source_run)/'verification.json'
    source=h.load(source_path)
    assert source['status']=='passed' and source['tests']==source['discovered_tests'] and source['file_hashes']==frozen['file_hashes']
    assert all(source[k]==0 for k in ('failures','errors','skipped'))
    state['source_terminal']=dict(path=str(source_path),sha256=sha(source_path),tests=source['tests'])
    sys.path.insert(0,str(ROOT/'product/src'))
    from ai_ad_editor.local_matting import _windows_job
    # This controller imports only the frozen Windows process-group helper.
    # Feature operations below always run fresh, explicit source/installed entrypoints.
    def execute(name, arguments, timeout):
        h.unchanged(frozen)
        assert all(sha(path)==pin for path,pin in retained.items())
        command=[sys.executable,'-E','-B','-u','-X','utf8',str(HERE/'portrait67.py'),*map(str,arguments)]
        state.update(status='running',current_step=name);save(out/'verification.json',state)
        began=time.monotonic()
        with _windows_job() as assign,(out/(name+'.stdout')).open('xb') as stdout,(out/(name+'.stderr')).open('xb') as stderr:
            process=subprocess.Popen(command,cwd=ROOT,env=dict(os.environ),stdout=stdout,stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW)
            assign(process)
            state['current_process']=native.process_identity(process.pid);save(out/'verification.json',state)
            try:
                while process.poll() is None:
                    if time.monotonic()-began>timeout:raise TimeoutError('Owned gate exceeded its complete deadline: '+name)
                    time.sleep(.5)
                code=process.wait(timeout=10)
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=10)
        row=dict(name=name,argv=command,exit_code=code,elapsed_seconds=time.monotonic()-began,process_exited=True)
        state['steps'].append(row);state.pop('current_process',None);save(out/'verification.json',state)
        assert code==0,'Downstream gate failed; preserve logs and do not retry: '+name
        h.unchanged(frozen);print(json.dumps(dict(step=name,status='passed',elapsed_seconds=row['elapsed_seconds'])),flush=True)
    try:
        tail=['--freeze-run',args.freeze_run]
        execute('build',['build','--run',args.run,'--tests-run',args.source_run,*tail],1800)
        execute('stage',['stage','--run',args.run,'--candidate-run',args.run,*tail],600)
        installed=h.load(BASE/('candidate-'+args.run)/'verification.json')['installed']
        execute('installed-all',['tests','--run',args.run,'--installed',installed,*tail],14400)
        execute('native-case',['native','--run',args.run,'--candidate-run',args.run,'--stage-run',args.run,*tail],3600)
        state.update(status='passed',current_step=None,formal_activation=False,full_goal_closed=False)
        save(out/'verification.json',state);print(json.dumps(dict(status='passed',formal_activation=False,full_goal_closed=False)),flush=True)
    except BaseException as exc:
        state.update(status='stopped',error=repr(exc));save(out/'verification.json',state)
        raise


if __name__=='__main__':main()
