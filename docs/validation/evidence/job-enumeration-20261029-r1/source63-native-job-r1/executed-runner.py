"""Deterministic native cleanup contracts; synthetic API observations are labelled."""
import argparse,hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');args=parser.parse_args()
import test_native_process_job
from ai_ad_editor import VERSION
out=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'/('baseline62-r1' if args.baseline else 'source63-native-job-r1');out.mkdir(parents=True,exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
suite=unittest.TestSuite([test_native_process_job.NativeProcessJobTests('test_close_requeries_one_incomplete_snapshot_and_waits_actual_writer')]) if args.baseline else unittest.defaultTestLoader.loadTestsFromModule(test_native_process_job)
with (out/'tests.txt').open('w',encoding='utf-8',newline='\n') as stream:result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
report=dict(status='passed' if result.wasSuccessful() else 'failed',version=VERSION,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),actual_Windows_children=True,API_snapshot_injection=True,original_natural_failure_reproduced=False,formal_activation=False,file_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'product/src/ai_ad_editor/native_process_job.py',ROOT/'product/tests/test_native_process_job.py']})
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report),flush=True)
if args.baseline:assert len(result.errors)==1 and 'Owned process enumeration exceeds cleanup budget' in result.errors[0][1]
else:raise SystemExit(0 if result.wasSuccessful() else 1)
