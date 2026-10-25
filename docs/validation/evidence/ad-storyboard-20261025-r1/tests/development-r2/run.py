import json, sys, unittest
sys.path[:0] = ['E:\\dev\\sandbox\\AI广告剪辑\\product\\src', 'E:\\dev\\sandbox\\AI广告剪辑\\product\\tests']
suite=unittest.TestSuite()
for pattern in ['test_ad_storyboard.py', 'test_sequence_canvas.py', 'test_sequence_compositing.py', 'test_source_edits.py', 'test_range_edits.py', 'test_job_recovery.py', 'test_execution_control.py', 'test_artifact_locks.py']: suite.addTests(unittest.defaultTestLoader.discover('E:\\dev\\sandbox\\AI广告剪辑\\product\\tests', pattern=pattern))
result=unittest.TextTestRunner(verbosity=2).run(suite)
print("AEK_RESULT="+json.dumps(dict(methods=result.testsRun,skipped=len(result.skipped),failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful())))
raise SystemExit(0 if result.wasSuccessful() else 1)
