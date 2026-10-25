"""Cooperative native command budgets, including integrity reads before inference."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import math
from pathlib import Path
import time

from .errors import AppError, argument_error

_CURRENT = ContextVar('agent_editor_execution_budgets', default=())


class ExecutionInterrupted(AppError):
    """An operation interruption must not be relabeled as invalid model bytes."""


class _Budget:
    def __init__(self, timeout, cancel_file, root):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
            raise argument_error('timeout-seconds 须为 0..3600 的有限正数', 'timeout_seconds')
        self.deadline = time.monotonic() + timeout
        self.marker = None
        self.next_marker_probe = 0.
        if cancel_file:
            from .policy import require_local_reference
            require_local_reference(str(cancel_file), field='cancel_file')
            self.marker = Path(cancel_file).expanduser()
            if not self.marker.is_absolute():
                self.marker = Path(root) / self.marker

    def check(self, now, force):
        # Check deadlines every chunk; bound marker stat traffic to once/25ms.
        if self.marker is not None and (force or now >= self.next_marker_probe):
            self.next_marker_probe = now + .025
            if self.marker.exists():
                raise ExecutionInterrupted('CANCELLED', '任务已取消', exit_code=8, path=str(self.marker))
        if now >= self.deadline:
            raise ExecutionInterrupted('PROCESS_TIMEOUT', '任务已超时', exit_code=6, retryable=True)


def checkpoint(*, force=False):
    budgets = _CURRENT.get()
    if budgets:
        now = time.monotonic()
        for budget in budgets:
            budget.check(now, force)


@contextmanager
def operation_budget(timeout, cancel_file=None, *, root=Path('.')):
    """Nest budgets without extending an outer deadline; reset before cleanup.

    This is cooperative between bounded reads, not a preemption guarantee for
    an OS-blocked file read. Native model processes retain their own watchdog.
    """
    budget = _Budget(timeout, cancel_file, root)
    token = _CURRENT.set(_CURRENT.get() + (budget,))
    try:
        checkpoint(force=True)
        yield budget
    finally:
        _CURRENT.reset(token)
