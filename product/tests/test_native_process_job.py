"""Actual owned Windows processes must finish releasing files before close returns."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from ai_ad_editor.native_process_job import NativeProcessJob


@unittest.skipUnless(os.name == 'nt', 'Native Windows job ownership')
class NativeProcessJobTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2]/'local/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch, prefix='job-close-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.kernel.WaitForSingleObject.restype = ctypes.c_uint32
        self.kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        self.kernel.OpenProcess.restype = ctypes.c_void_p
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.kernel.CloseHandle.restype = ctypes.c_int

    def start(self, code):
        job = NativeProcessJob()
        self.addCleanup(job.close)
        process = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-c', code],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW | job.creationflags)
        try:
            job.attach_and_resume(process)
        except BaseException:
            process.kill()
            process.wait(timeout=10)
            raise
        self.addCleanup(lambda:process.wait(timeout=10))
        # Unittest cleanups are LIFO: close the job before waiting its root.
        self.addCleanup(job.close)
        return job,process

    def wait_ready(self, path):
        deadline = time.monotonic()+10
        while not path.exists() and time.monotonic()<deadline:
            time.sleep(.005)
        self.assertTrue(path.exists(), 'Owned child failed to open its actual file')

    def writer(self, path, ready):
        return ('import os,time;from pathlib import Path;'
            'f=open('+repr(str(path))+',"wb");f.write(b"owned");f.flush();'
            'Path('+repr(str(ready))+').write_text(str(os.getpid()));time.sleep(30)')

    def test_close_waits_actual_file_writer_in_twenty_independent_jobs(self):
        for i in range(20):
            path,ready = self.root/(str(i)+'.locked'),self.root/(str(i)+'.ready')
            job,process = self.start(self.writer(path,ready))
            self.wait_ready(ready)
            job.close()
            self.assertEqual(self.kernel.WaitForSingleObject(int(process._handle),0),0)
            path.unlink()  # No retry or sleep is allowed to hide asynchronous cleanup.
            self.assertIsNotNone(process.poll())

    def test_close_waits_descendant_after_its_parent_already_exited(self):
        path,ready = self.root/'descendant.locked',self.root/'descendant.ready'
        child = self.writer(path,ready)
        code = ('import subprocess,sys,time;from pathlib import Path;'
            'subprocess.Popen([sys.executable,"-I","-S","-B","-c",'+repr(child)+'], '
            'stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);'
            'p=Path('+repr(str(ready))+');'
            'exec("while not p.exists(): time.sleep(.005)")')
        job,parent = self.start(code)
        self.wait_ready(ready)
        parent.wait(timeout=10)
        handle = self.kernel.OpenProcess(0x00100000,False,int(ready.read_text()))
        self.assertTrue(handle)
        try:
            self.assertEqual(self.kernel.WaitForSingleObject(handle,0),258)
            job.close()
            self.assertEqual(self.kernel.WaitForSingleObject(handle,0),0)
            path.unlink()
        finally:
            self.kernel.CloseHandle(handle)

    def test_closing_one_job_preserves_the_other_owned_job(self):
        a,ar = self.root/'a.locked',self.root/'a.ready'
        b,br = self.root/'b.locked',self.root/'b.ready'
        first,p1 = self.start(self.writer(a,ar))
        second,p2 = self.start(self.writer(b,br))
        self.wait_ready(ar)
        self.wait_ready(br)
        first.close()
        a.unlink()
        self.assertEqual(self.kernel.WaitForSingleObject(int(p1._handle),0),0)
        self.assertEqual(self.kernel.WaitForSingleObject(int(p2._handle),0),258)
        with self.assertRaises(PermissionError):
            b.unlink()
        second.close()
        b.unlink()

    def test_empty_and_already_completed_jobs_close_idempotently(self):
        empty = NativeProcessJob()
        empty.close()
        empty.close()
        job,process = self.start('pass')
        process.wait(timeout=10)
        job.close()
        job.close()
        self.assertEqual(process.returncode,0)


if __name__ == '__main__':
    unittest.main()
