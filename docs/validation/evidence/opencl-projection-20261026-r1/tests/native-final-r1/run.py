import json,sys,unittest
sys.path[:0]=['E:\\dev\\sandbox\\AI广告剪辑\\local\\agent-ffmpeg\\v0.1.0-alpha.4-local.18\\final-r2\\installed\\site', 'E:\\dev\\sandbox\\AI广告剪辑\\product\\tests']
suite=unittest.defaultTestLoader.loadTestsFromNames(['native_opencl_projection.NativeOpenCLProjectionTests'])
assert suite.countTestCases()>0
result=unittest.TextTestRunner(verbosity=2).run(suite)
print("AEK_RESULT="+json.dumps(dict(methods=result.testsRun,skipped=len(result.skipped),failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful())))
raise SystemExit(0 if result.wasSuccessful() else 1)
