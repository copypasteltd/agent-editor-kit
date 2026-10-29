"""Inherited command controls must stop actual owned Windows subprocesses."""
import ctypes
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from ai_ad_editor.errors import AppError
from ai_ad_editor.execution_control import checkpoint, operation_budget
from ai_ad_editor.utils import run_process


@unittest.skipUnless(os.name == 'nt', 'Native Windows process-job contract')
class ProcessOperationBudgetTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2]/'local/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch, prefix='process-budget-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pid_file = self.root/'child.pid'
        self.completed = self.root/'completed'
        self.cancel = self.root/'cancel-marker'

    def child(self, *, cancel=False):
        script = ('import os,time;from pathlib import Path;'
            'Path('+repr(str(self.pid_file))+').write_text(str(os.getpid()));'
            + ('Path('+repr(str(self.cancel))+').touch();' if cancel else '')
            + 'time.sleep(2);Path('+repr(str(self.completed))+').touch()')
        return [sys.executable, '-I', '-S', '-B', '-c', script]

    def assert_owned_process_closed(self):
        self.assertFalse(self.completed.exists(), 'Child completed after an inherited interruption')
        self.assertFalse(any(t.name == 'ai-ad-editor-process-reader' for t in threading.enumerate()))
        if self.pid_file.exists():
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel.WaitForSingleObject.restype = ctypes.c_uint32
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.OpenProcess(0x00100000, False, int(self.pid_file.read_text()))
            if handle:
                try:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0, 'Owned child is still live')
                finally:
                    kernel.CloseHandle(handle)
        checkpoint(force=True)  # The ended context must not leak.

    def test_inherited_shorter_deadline_stops_longer_child_budget(self):
        with self.assertRaises(AppError) as error:
            with operation_budget(.2, root=self.root):
                with operation_budget(10, root=self.root):
                    run_process(self.child(), timeout=10)
        self.assertEqual(error.exception.code, 'PROCESS_TIMEOUT')
        self.assert_owned_process_closed()

    def test_relative_outer_cancel_is_observed_without_child_cancel_argument(self):
        with self.assertRaises(AppError) as error:
            with operation_budget(10, self.cancel.name, root=self.root):
                run_process(self.child(cancel=True), timeout=10)
        self.assertEqual(error.exception.code, 'CANCELLED')
        self.assertTrue(self.cancel.exists())
        self.assert_owned_process_closed()

    def test_expired_outer_budget_refuses_process_start(self):
        with self.assertRaises(AppError) as error:
            with operation_budget(.01, root=self.root):
                time.sleep(.02)
                run_process(self.child(), timeout=10)
        self.assertEqual(error.exception.code, 'PROCESS_TIMEOUT')
        self.assertFalse(self.pid_file.exists())
        self.assert_owned_process_closed()

    def test_child_specific_deadline_remains_effective(self):
        with self.assertRaises(AppError) as error:
            with operation_budget(10, root=self.root):
                run_process(self.child(), timeout=.2)
        self.assertEqual(error.exception.code, 'PROCESS_TIMEOUT')
        self.assert_owned_process_closed()


if __name__ == '__main__':
    unittest.main()
