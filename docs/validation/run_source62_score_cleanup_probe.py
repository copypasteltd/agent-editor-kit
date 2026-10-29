"""Repeat only the original failing score case with native snapshot observation."""
import ctypes,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
from ai_ad_editor.native_process_job import NativeProcessJob
import test_music_score
out=ROOT/'docs/validation/evidence/lipsync-storage-race-20261029-r1/score-cleanup-probe-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
original=NativeProcessJob.__init__;snapshots=[]
def observed(job):
 original(job)
 if job.handle is None:return
 real=job.kernel
 class Observe:
  def __getattr__(self,name):return getattr(real,name)
  def QueryInformationJobObject(self,handle,kind,buffer,size,length):
   result=real.QueryInformationJobObject(handle,kind,buffer,size,length)
   if kind==3 and result:
    value=ctypes.cast(buffer,ctypes.POINTER(job.ProcessIds)).contents
    snapshots.append(dict(assigned=int(value.Assigned),count=int(value.Count)))
   return result
 job.kernel=Observe()
name='test_four_effects_are_actual_editable_non_silent_audio'
with patch.object(NativeProcessJob,'__init__',observed),(out/'tests.txt').open('w',encoding='utf-8') as stream:
 result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite(test_music_score.ScoreCliTests(name) for _ in range(10)))
report=dict(status='not-reproduced' if result.wasSuccessful() else 'failed',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),snapshot_count=len(snapshots),incomplete_snapshots=[r for r in snapshots if r['assigned']>r['count']],fabricated_counts=False,original_failed_case_still_unaccepted=True,formal_activation=False)
(out/'observations.json').write_text(json.dumps(snapshots,indent=2)+'\n',encoding='utf-8',newline='\n')
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report),flush=True)
