"""Own Windows subprocess trees, including when their CLI owner is terminated."""
from __future__ import annotations

import os


class NativeProcessJob:
    """Create suspended children and attach them before any application code runs.

    An unnamed non-inherited KILL_ON_JOB_CLOSE handle belongs only to this
    caller. Nested Windows jobs preserve the executor's existing job limits.
    This is process lifetime management, not a VM or an OS security sandbox.
    """

    def __init__(self):
        self.handle = None
        self.creationflags = 0
        if os.name != 'nt':
            return
        import ctypes
        from ctypes import wintypes as w
        self.ctypes = ctypes
        kernel = self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        size = ctypes.c_size_t

        class BasicLimits(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64),
                ('LimitFlags', w.DWORD), ('MinimumWorkingSetSize', size), ('MaximumWorkingSetSize', size),
                ('ActiveProcessLimit', w.DWORD), ('Affinity', size), ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ('ReadOperationCount', 'WriteOperationCount',
                'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IOCounters),
                ('ProcessMemoryLimit', size), ('JobMemoryLimit', size), ('PeakProcessMemoryUsed', size), ('PeakJobMemoryUsed', size)]

        class ThreadEntry(ctypes.Structure):
            _fields_ = [('dwSize', w.DWORD), ('cntUsage', w.DWORD), ('th32ThreadID', w.DWORD),
                ('th32OwnerProcessID', w.DWORD), ('tpBasePri', w.LONG), ('tpDeltaPri', w.LONG), ('dwFlags', w.DWORD)]
        self.ThreadEntry = ThreadEntry
        signatures = {
            'CreateJobObjectW': ([w.LPVOID, w.LPCWSTR], w.HANDLE),
            'SetInformationJobObject': ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD], w.BOOL),
            'AssignProcessToJobObject': ([w.HANDLE, w.HANDLE], w.BOOL),
            'CloseHandle': ([w.HANDLE], w.BOOL),
            'CreateToolhelp32Snapshot': ([w.DWORD, w.DWORD], w.HANDLE),
            'Thread32First': ([w.HANDLE, ctypes.POINTER(ThreadEntry)], w.BOOL),
            'Thread32Next': ([w.HANDLE, ctypes.POINTER(ThreadEntry)], w.BOOL),
            'OpenThread': ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            'GetProcessIdOfThread': ([w.HANDLE], w.DWORD),
            'ResumeThread': ([w.HANDLE], w.DWORD),
        }
        for name, (args, result) in signatures.items():
            function = getattr(kernel, name)
            function.argtypes, function.restype = args, result
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle = handle
        try:
            limits = ExtendedLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.close()
            raise
        self.creationflags = 0x4  # CREATE_SUSPENDED; primary thread resumed only after assignment

    def attach_and_resume(self, process):
        if self.handle is None:
            return
        ctypes, kernel = self.ctypes, self.kernel
        if not kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        snapshot = kernel.CreateToolhelp32Snapshot(0x4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = self.ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            found = kernel.Thread32First(snapshot, ctypes.byref(entry))
            while found:
                if entry.th32OwnerProcessID == process.pid:
                    thread = kernel.OpenThread(0x0802, False, entry.th32ThreadID)
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if kernel.GetProcessIdOfThread(thread) != process.pid:
                            raise OSError('Suspended process thread ownership changed')
                        previous = kernel.ResumeThread(thread)
                        if previous != 1:
                            raise OSError('Expected one initial primary-thread suspension, got %s' % previous)
                        return
                    finally:
                        kernel.CloseHandle(thread)
                found = kernel.Thread32Next(snapshot, ctypes.byref(entry))
            raise OSError('Suspended process primary thread unavailable')
        finally:
            kernel.CloseHandle(snapshot)

    def close(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            if not self.kernel.CloseHandle(handle):
                raise self.ctypes.WinError(self.ctypes.get_last_error())
