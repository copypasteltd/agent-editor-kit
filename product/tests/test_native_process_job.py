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

    def observe_id_queries(self,job,transform):
        real=job.kernel;queries=[]
        class Observe:
            def __getattr__(self,name):return getattr(real,name)
            def QueryInformationJobObject(self,handle,kind,buffer,size,length):
                result=real.QueryInformationJobObject(handle,kind,buffer,size,length)
                if kind==3:
                    info=ctypes.cast(buffer,ctypes.POINTER(job.ProcessIds)).contents
                    queries.append((int(info.Assigned),int(info.Count)))
                    return transform(info,len(queries),result)
                return result
        job.kernel=Observe()
        return queries

    def test_close_requeries_one_incomplete_snapshot_and_waits_actual_writer(self):
        path,ready=self.root/'partial.locked',self.root/'partial.ready'
        job,process=self.start(self.writer(path,ready));self.wait_ready(ready)
        def incomplete(info,n,result):
            if n==1:info.Assigned=1;info.Count=0
            return result
        queries=self.observe_id_queries(job,incomplete)
        try:
            job.close()
            self.assertGreaterEqual(len(queries),2)
            self.assertEqual(self.kernel.WaitForSingleObject(int(process._handle),0),0)
            path.unlink()
        finally:
            if process.poll() is None:process.wait(timeout=10)

    def test_close_requeries_more_data_without_hiding_other_API_errors(self):
        path,ready=self.root/'more.locked',self.root/'more.ready'
        job,process=self.start(self.writer(path,ready));self.wait_ready(ready)
        def more(info,n,result):
            if n==1:ctypes.set_last_error(234);return 0
            return result
        queries=self.observe_id_queries(job,more)
        try:
            job.close();self.assertGreaterEqual(len(queries),2)
            self.assertEqual(self.kernel.WaitForSingleObject(int(process._handle),0),0)
            path.unlink()
        finally:
            if process.poll() is None:process.wait(timeout=10)

    def test_incomplete_snapshot_retries_are_bounded_and_do_not_claim_success(self):
        path,ready=self.root/'unstable.locked',self.root/'unstable.ready'
        job,process=self.start(self.writer(path,ready));self.wait_ready(ready)
        def incomplete(info,n,result):info.Assigned=1;info.Count=0;return result
        queries=self.observe_id_queries(job,incomplete)
        try:
            with self.assertRaisesRegex(OSError,'did not stabilize.*assigned=1.*count=0'):
                job.close()
            self.assertEqual(len(queries),32)
        finally:process.wait(timeout=10)
        self.assertEqual(self.kernel.WaitForSingleObject(int(process._handle),0),0)
        path.unlink()

    def test_process_list_limit_remains_4096_with_count_diagnostics(self):
        path,ready=self.root/'budget.locked',self.root/'budget.ready'
        job,process=self.start(self.writer(path,ready));self.wait_ready(ready)
        def oversized(info,n,result):info.Assigned=4097;return result
        queries=self.observe_id_queries(job,oversized)
        try:
            with self.assertRaisesRegex(OSError,'exceeds cleanup budget.*assigned=4097'):
                job.close()
            self.assertEqual(len(queries),1)
        finally:process.wait(timeout=10)
        path.unlink()

    def test_query_access_denied_is_not_retried_or_hidden(self):
        path,ready=self.root/'denied.locked',self.root/'denied.ready'
        job,process=self.start(self.writer(path,ready));self.wait_ready(ready)
        def denied(info,n,result):ctypes.set_last_error(5);return 0
        queries=self.observe_id_queries(job,denied)
        try:
            with self.assertRaises(OSError) as caught:job.close()
            self.assertEqual(caught.exception.winerror,5)
            self.assertEqual(len(queries),1)
        finally:process.wait(timeout=10)
        path.unlink()

    def test_partial_descendant_snapshot_preserves_another_job_and_waits_file_release(self):
        path,ready=self.root/'partial-child.locked',self.root/'partial-child.ready'
        child=self.writer(path,ready)
        code=('import subprocess,sys,time;from pathlib import Path;'
              'subprocess.Popen([sys.executable,"-I","-S","-B","-c",'+repr(child)+'],'
              'stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);'
              'p=Path('+repr(str(ready))+');exec("while not p.exists(): time.sleep(.005)")')
        job,parent=self.start(code);self.wait_ready(ready);parent.wait(timeout=10)
        child_handle=self.kernel.OpenProcess(0x00100000,False,int(ready.read_text()))
        self.assertTrue(child_handle)
        other_path,other_ready=self.root/'other.locked',self.root/'other.ready'
        other,other_process=self.start(self.writer(other_path,other_ready));self.wait_ready(other_ready)
        def incomplete(info,n,result):
            if n==1:info.Assigned=max(1,info.Assigned);info.Count=0
            return result
        queries=self.observe_id_queries(job,incomplete)
        try:
            job.close();self.assertGreaterEqual(len(queries),2)
            self.assertEqual(self.kernel.WaitForSingleObject(child_handle,0),0)
            path.unlink()
            self.assertEqual(self.kernel.WaitForSingleObject(int(other_process._handle),0),258)
            with self.assertRaises(PermissionError):other_path.unlink()
        finally:self.kernel.CloseHandle(child_handle)
        other.close();other_path.unlink()

    def test_invalid_count_larger_than_assigned_is_rejected_with_diagnostics(self):
        path,ready=self.root/'invalid.locked',self.root/'invalid.ready'
        job,process=self.start(self.writer(path,ready));self.wait_ready(ready)
        def invalid(info,n,result):info.Assigned=0;info.Count=1;return result
        queries=self.observe_id_queries(job,invalid)
        try:
            with self.assertRaisesRegex(OSError,'Invalid owned process enumeration.*assigned=0.*count=1'):
                job.close()
            self.assertEqual(len(queries),1)
        finally:process.wait(timeout=10)
        path.unlink()

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
