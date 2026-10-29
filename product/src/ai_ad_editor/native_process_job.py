"""Own Windows subprocess trees, including when their CLI owner is terminated."""
from __future__ import annotations

import os
import time


class NativeProcessJob:
    """Create suspended children and attach them before any application code runs.

    An unnamed non-inherited KILL_ON_JOB_CLOSE handle belongs only to this
    caller. Nested Windows jobs preserve the executor's existing job limits.
    This is process lifetime management, not a VM or an OS security sandbox.
    """

    def __init__(self):
        self.handle = None
        self._processes = []
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

        class BasicAccounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int64) for name in ('TotalUserTime', 'TotalKernelTime',
                'ThisPeriodTotalUserTime', 'ThisPeriodTotalKernelTime')] + [
                (name, w.DWORD) for name in ('TotalPageFaultCount', 'TotalProcesses',
                    'ActiveProcesses', 'TotalTerminatedProcesses')]
        self.BasicAccounting = BasicAccounting

        class ProcessIds(ctypes.Structure):
            _fields_ = [('Assigned', w.DWORD), ('Count', w.DWORD),
                        ('Ids', ctypes.c_size_t * 4096)]
        self.ProcessIds = ProcessIds
        self.BOOL = w.BOOL
        signatures = {
            'CreateJobObjectW': ([w.LPVOID, w.LPCWSTR], w.HANDLE),
            'SetInformationJobObject': ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD], w.BOOL),
            'AssignProcessToJobObject': ([w.HANDLE, w.HANDLE], w.BOOL),
            'CloseHandle': ([w.HANDLE], w.BOOL),
            'TerminateJobObject': ([w.HANDLE, w.UINT], w.BOOL),
            'QueryInformationJobObject': ([w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPDWORD], w.BOOL),
            'OpenProcess': ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            'IsProcessInJob': ([w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)], w.BOOL),
            'WaitForSingleObject': ([w.HANDLE, w.DWORD], w.DWORD),
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
        self._processes.append(process)
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
        """Terminate only this owned job and wait until its processes exit.

        KILL_ON_JOB_CLOSE alone returns before Windows releases process file
        handles. Keep the job queryable until its active count is zero and
        wait the explicitly owned root process objects before returning.
        """
        if self.handle is None:
            return
        handle, self.handle = self.handle, None
        ctypes, kernel = self.ctypes, self.kernel
        retained = {}
        try:
            def active():
                information = self.BasicAccounting()
                if not kernel.QueryInformationJobObject(handle, 1, ctypes.byref(information),
                                                       ctypes.sizeof(information), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                return information.ActiveProcesses

            deadline = time.monotonic() + 10

            def retain_owned_process_handles():
                # A live job can change while its ID list is being observed.
                # Preserve returned handles before retrying an incomplete list;
                # never treat a partial list as complete ownership evidence.
                assigned = count = last_error = 0
                for attempt in range(32):
                    information = self.ProcessIds()
                    ok = kernel.QueryInformationJobObject(handle, 3, ctypes.byref(information),
                                                           ctypes.sizeof(information), None)
                    if not ok:
                        last_error = ctypes.get_last_error()
                        if last_error != 234:  # ERROR_MORE_DATA only.
                            raise ctypes.WinError(last_error)
                    else:
                        assigned, count = int(information.Assigned), int(information.Count)
                        if count > 4096 or assigned > 4096:
                            raise OSError('Owned process enumeration exceeds cleanup budget '
                                          f'(assigned={assigned}, count={count}, limit=4096)')
                        if count > assigned:
                            raise OSError('Invalid owned process enumeration '
                                          f'(assigned={assigned}, count={count})')
                        for pid in information.Ids[:count]:
                            if pid in retained:
                                continue
                            if len(retained) >= 4096:
                                raise OSError('Retained owned process handles exceed cleanup budget '
                                              '(limit=4096)')
                            process_handle = kernel.OpenProcess(0x00101000, False, pid)
                            if not process_handle:
                                if ctypes.get_last_error() == 87:  # PID already disappeared.
                                    continue
                                raise ctypes.WinError(ctypes.get_last_error())
                            belongs = self.BOOL()
                            try:
                                if not kernel.IsProcessInJob(process_handle, handle, ctypes.byref(belongs)):
                                    raise ctypes.WinError(ctypes.get_last_error())
                                if belongs.value:
                                    retained[pid] = process_handle
                                    process_handle = None
                            finally:
                                if process_handle:
                                    kernel.CloseHandle(process_handle)
                        if count == assigned:
                            return
                    if attempt == 31 or time.monotonic() >= deadline:
                        break
                    time.sleep(.005)
                raise OSError('Owned process enumeration did not stabilize '
                              f'(assigned={assigned}, count={count}, attempts={attempt+1}, '
                              f'last_error={last_error})')

            # Keep kernel handles before terminating. Accounting can reach
            # zero before a descendant's process object is signaled.
            retain_owned_process_handles()
            if active():
                if not kernel.TerminateJobObject(handle, 1):
                    raise ctypes.WinError(ctypes.get_last_error())
            retain_owned_process_handles()
            for process in self._processes:
                process.wait(timeout=max(0., deadline-time.monotonic()))
            retain_owned_process_handles()
            for process_handle in retained.values():
                milliseconds = max(0, int((deadline-time.monotonic())*1000))
                if kernel.WaitForSingleObject(process_handle, milliseconds) != 0:
                    raise OSError('Owned descendant process did not signal termination')
            while active():
                if time.monotonic() >= deadline:
                    raise OSError('Owned native process tree did not exit within cleanup budget')
                time.sleep(.005)
        finally:
            for process_handle in retained.values():
                kernel.CloseHandle(process_handle)
            self._processes.clear()
            if not kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
