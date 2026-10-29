"""Wait on existing owned Windows processes, then deliver an unregistered candidate.

Never restarts a timed-out observation, never activates the formal Skill, and
never treats missing/failed evidence as acceptance. No Docker, WSL or network.
"""
import argparse,ctypes,hashlib,json,subprocess,sys,time
from ctypes import wintypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-storage-race-20261029-r1'
C='C:/Python313/python.exe'
class OwnedProcess:
 def __init__(self,pid):
  self.pid=pid;self.api=ctypes.WinDLL('kernel32',use_last_error=True)
  self.api.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];self.api.OpenProcess.restype=wintypes.HANDLE
  self.api.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];self.api.WaitForSingleObject.restype=wintypes.DWORD
  self.api.CloseHandle.argtypes=[wintypes.HANDLE];self.api.CloseHandle.restype=wintypes.BOOL
  self.handle=self.api.OpenProcess(0x00100000,False,pid)
  if not self.handle:raise OSError(ctypes.get_last_error(),'Cannot open existing process',pid)
 def running(self):
  status=self.api.WaitForSingleObject(self.handle,0)
  if status==0:return False
  if status==258:return True
  raise OSError(ctypes.get_last_error(),'Process observation failed',self.pid)
 def close(self):
  if self.handle:self.api.CloseHandle(self.handle);self.handle=None
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--lipsync-pid',type=int,required=True);parser.add_argument('--contracts-pid',type=int,required=True);parser.add_argument('--cpu-pid',type=int,required=True);args=parser.parse_args()
 assert all(p>0 for p in (args.lipsync_pid,args.contracts_pid,args.cpu_pid))
 out=BASE/'delivery-pipeline-r1';out.mkdir(exist_ok=False)
 (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
 calls=[];handles=[];started=time.monotonic()
 def state(phase,**extra):save(out/'progress.json',dict(status='running',phase=phase,elapsed_seconds=time.monotonic()-started,calls=calls,**extra))
 def wait(process,receipt,phase):
  state(phase,observed_existing_pid=process.pid)
  while process.running():time.sleep(5)
  assert receipt.is_file(),('Process ended without terminal evidence',process.pid,str(receipt))
  r=load(receipt);assert r['status']=='passed',(phase,r.get('status'))
  return r
 def run(script,*argv):
  phase=script.removesuffix('.py');state(phase)
  command=[C,'-E','-B','-u','-X','utf8',str(ROOT/'docs/validation'/script),*argv]
  with (out/(phase+'.stdout')).open('wb') as stdout,(out/(phase+'.stderr')).open('wb') as stderr:
   result=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr)
  calls.append(dict(script=script,exit_code=result.returncode));save(out/'calls.json',calls)
  print(json.dumps(calls[-1]),flush=True);assert result.returncode==0,(phase,result.returncode)
 try:
  for pid in (args.lipsync_pid,args.contracts_pid,args.cpu_pid):handles.append(OwnedProcess(pid))
  lip=wait(handles[0],BASE/'source62-lipsync-cuda-r1/verification.json','waiting-existing-MuseTalk')
  assert lip['actual_MuseTalk_CUDA'] and lip['owned_process_cleanup_passed'] and lip['complete_package_rendered_RGBA_PCM_equal']
  # GPU work is serial: the already-running MuseTalk controller has exited.
  run('run_source62_gpu_case.py','--run','r1')
  contracts=wait(handles[1],BASE/'source62-contracts-r1/verification.json','waiting-existing-contracts')
  assert contracts['tests']==406 and contracts['frozen_equal'] and contracts['failures']==contracts['errors']==contracts['skipped']==0
  assert all(sha(ROOT/p)==h for p,h in contracts['file_hashes'].items())
  wait(handles[2],BASE/'cpu-delivery-controller-r1/verification.json','waiting-existing-CPU-cases')
  # The builder independently revalidates every source proof and frozen hash.
  pub=BASE/'publication-r1';pub.mkdir(exist_ok=False)
  files=['README.md','README.zh-TW.md','README.en.md','docs/validation/CLI62口型存储竞争修复_2026-10-29.md']
  assert all('| R499 |' in (ROOT/p).read_text(encoding='utf-8') for p in files[:3])
  save(pub/'verification.json',dict(status='passed',cli_version='0.1.62',file_hashes={p:sha(ROOT/p) for p in files},formal_cli='0.1.59',full_goal_closed=False,source_actual_cases_separate=True,publication_scope='documentation/source candidate; not formal activation'))
  run('build_source62_delivery.py','--run','r1')
  run('run_source62_install_acceptance.py')
  run('stage_source62_skill.py','--run','r1')
  report=dict(status='passed',calls=calls,existing_processes_not_restarted=True,formal_activation=False,stage_scope='unregistered candidate; actual staged Skill cases still required',full_goal_closed=False)
  save(out/'verification.json',report);print(json.dumps(report),flush=True);return 0
 except BaseException as exc:
  save(out/'verification.json',dict(status='failed',error=repr(exc),calls=calls,formal_activation=False,full_goal_closed=False));raise
 finally:
  for handle in handles:handle.close()
if __name__=='__main__':raise SystemExit(main())
