import json, sys, unittest
sys.path[:0] = ['E:\\dev\\sandbox\\AI广告剪辑\\local\\agent-ffmpeg\\v0.1.0-alpha.4-local.11\\final-r1\\installed\\site', 'E:\\dev\\sandbox\\AI广告剪辑\\product\\tests']
suite=unittest.TestSuite()
for pattern in ['test_execution_control.py', 'test_artifact_locks.py', 'test_semantic.py', 'test_semantic_decisions.py', 'test_semantic_package.py', 'test_semantic_jobs.py', 'test_job_recovery.py', 'test_native_job_start.py', 'test_stem_separation.py', 'test_dubbing.py']: suite.addTests(unittest.defaultTestLoader.discover('E:\\dev\\sandbox\\AI广告剪辑\\product\\tests', pattern=pattern))
result=unittest.TextTestRunner(verbosity=2).run(suite)
print("AEK_RESULT="+json.dumps(dict(methods=result.testsRun,skipped=len(result.skipped),failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful())))
raise SystemExit(0 if result.wasSuccessful() else 1)
