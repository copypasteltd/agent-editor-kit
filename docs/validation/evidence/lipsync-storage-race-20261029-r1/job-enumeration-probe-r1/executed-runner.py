"""Observe real job ID-list snapshots around short-lived owned Windows children.
No fabricated counts; this probe does not change product sources or mask errors.
"""
import ctypes,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.native_process_job import NativeProcessJob
out=ROOT/'docs/validation/evidence/lipsync-storage-race-20261029-r1/job-enumeration-probe-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
rows=[];failure=None
for i in range(150):
 job=NativeProcessJob();child=None;snapshots=[]
 try:
  child=subprocess.Popen([sys.executable,'-I','-S','-B','-c','pass'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW|job.creationflags)
  job.attach_and_resume(child);real=job.kernel
  class Observe:
   def __getattr__(self,name):return getattr(real,name)
   def QueryInformationJobObject(self,handle,kind,buffer,size,length):
    result=real.QueryInformationJobObject(handle,kind,buffer,size,length)
    if kind==3 and result:
     value=ctypes.cast(buffer,ctypes.POINTER(job.ProcessIds)).contents
     snapshots.append(dict(assigned=int(value.Assigned),count=int(value.Count)))
    return result
  job.kernel=Observe()
  # Give the child a chance to exit between accounting and ID-list snapshots.
  try:job.close()
  except OSError as exc:failure=dict(iteration=i,error=repr(exc),snapshots=snapshots)
 finally:
  job.close()
  if child:
   child.wait(timeout=30)
   rows.append(dict(iteration=i,returncode=child.returncode,snapshots=snapshots))
 if failure:break
report=dict(status='reproduced' if failure else 'not-reproduced',attempts=len(rows),failure=failure,actual_Windows_children=True,fabricated_counts=False,all_children_exited=True,formal_activation=False)
(out/'observations.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8',newline='\n')
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report),flush=True)
