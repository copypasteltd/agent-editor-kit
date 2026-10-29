"""Real FFmpeg transport regression; synthetic worker, no neural quality claim."""
import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/validation/evidence/lipsync-storage-race-20261029-r1/source62-lipsync-r3'
OUT.mkdir(parents=True,exist_ok=False)
TEMP=ROOT/'local/agent-ffmpeg/source62-storage-race-temp';TEMP.mkdir(parents=True,exist_ok=True)
os.environ['TEMP']=os.environ['TMP']=str(TEMP);tempfile.tempdir=str(TEMP)
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
import test_lipsync
from ai_ad_editor import VERSION,lipsync_pipeline
assert VERSION=='0.1.62'
files=[ROOT/'product/src/ai_ad_editor'/n for n in ('__init__.py','lipsync_pipeline.py')]+[ROOT/'product/pyproject.toml',ROOT/'product/tests/test_lipsync.py']
pins={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
# Run the same real transport fault injection against the previous unsafe observer.
def legacy(work):return sum(p.stat().st_size for p in work.iterdir() if p.is_file())
case=test_lipsync.TransportTests('test_atomic_progress_rename_during_storage_scan_preserves_complete_transport')
with (OUT/'baseline.txt').open('w',encoding='utf-8') as stream:
 with patch.object(lipsync_pipeline,'workspace_bytes',legacy):
  baseline=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite([case]))
assert len(baseline.errors)==1 and 'FileNotFoundError' in baseline.errors[0][1]
with (OUT/'tests.txt').open('w',encoding='utf-8') as stream:
 result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_lipsync))
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in pins.items())
receipt=dict(status='passed' if result.wasSuccessful() else 'failed',version=VERSION,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),legacy_race_reproduced=True,real_FFmpeg=True,worker='synthetic',neural_inference=False,formal_activation=False,file_hashes=pins)
(OUT/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False));sys.exit(0 if result.wasSuccessful() else 1)
