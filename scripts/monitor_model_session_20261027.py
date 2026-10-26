"""Read-only native process working-set/private bytes and device VRAM sampling."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/model-session-20261027-r1'


class Counters(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
        *[(name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage',
          'QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case-run',required=True);parser.add_argument('--run',required=True);args=parser.parse_args()
    assert all(x.replace('-','').isalnum() for x in (args.case_run,args.run))
    out=BASE/('resources-'+args.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    case=BASE/('case-'+args.case_run)/'verification.json'
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD];psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    started=time.monotonic();samples=0;peak_working=peak_private=0;handle=None;pid=None;gpu_queries=[];last_gpu=0;status='waiting'
    try:
        with (out/'samples.jsonl').open('x',encoding='utf8',newline='\n') as stream:
            while time.monotonic()-started<7200:
                try:record=json.loads(case.read_bytes())
                except (OSError,ValueError):record={}
                observed=record.get('session_start',{}).get('state',{}).get('pid')
                if observed and pid is None:
                    pid=observed;handle=kernel.OpenProcess(0x410,False,pid)
                    if not handle:raise ctypes.WinError(ctypes.get_last_error())
                    status='sampling'
                row=dict(at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,pid=pid)
                if handle:
                    counters=Counters();counters.cb=ctypes.sizeof(counters)
                    if psapi.GetProcessMemoryInfo(handle,ctypes.byref(counters),counters.cb):
                        row.update(working_set_bytes=counters.WorkingSetSize,peak_working_set_bytes=counters.PeakWorkingSetSize,
                            private_bytes=counters.PrivateUsage,peak_pagefile_bytes=counters.PeakPagefileUsage)
                        peak_working=max(peak_working,counters.PeakWorkingSetSize);peak_private=max(peak_private,counters.PrivateUsage)
                        samples+=1
                if time.monotonic()-last_gpu>=5:
                    result=subprocess.run(['nvidia-smi','--query-gpu=uuid,memory.used,memory.free','--format=csv,noheader,nounits'],
                        capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
                    raw=dict(at_utc=row['at_utc'],exit_code=result.returncode,stdout=result.stdout.decode('utf8','replace'),stderr=result.stderr.decode('utf8','replace'))
                    gpu_queries.append(raw);row['gpu_query_index']=len(gpu_queries)-1;last_gpu=time.monotonic()
                stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
                if record.get('status') not in (None,'running'):
                    status='completed' if record['status']=='passed_actual_cuda_resident_reuse_and_cancel' else 'case-failed';break
                time.sleep(.5)
        report=dict(status=status,worker_pid=pid,process_samples=samples,peak_working_set_bytes=peak_working,maximum_sampled_private_bytes=peak_private,
            per_process_cuda_peak='Recorded by Torch in each real inference response; excludes context and other applications.',
            gpu_samples_scope='whole GPU device, includes other applications; not process attribution or a reservation',
            sampling_scope='Resident worker after session readiness; excludes startup hashing and controller/decoder/encoder process totals.',
            process_termination_or_gpu_mutation=False,gpu_queries=gpu_queries)
        (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        print(json.dumps({k:v for k,v in report.items() if k!='gpu_queries'}),flush=True)
    finally:
        if handle:kernel.CloseHandle(handle)


if __name__=='__main__':main()
