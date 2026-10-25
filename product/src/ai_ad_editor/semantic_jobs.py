"""Managed semantic workspaces; explicit recovery preserves original evidence."""
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
import shutil

from .errors import AppError
from .job_workspaces import _owned, managed_workspace

_CURRENT = ContextVar('agent_semantic_job', default=None)


def current():
    job = _CURRENT.get()
    if job is None:
        raise AppError('SEMANTIC_JOB_SCOPE_MISSING', '语义执行缺少受管任务工作目录', exit_code=6)
    return job


def managed(kind):
    def decorate(function):
        @wraps(function)
        def execute(root, project, **options):
            if options.get('dry_run'):
                return function(root, project, **options)
            root = Path(root).resolve()
            base = _owned(root, root / 'cache/managed-jobs')
            if base.exists() and sum(1 for _ in base.iterdir()) >= 256:
                raise AppError('SEMANTIC_JOB_BUDGET', '受管任务已达 256 项，请先预览并显式恢复清理', exit_code=6)
            if shutil.disk_usage(root).free < 256 * 1024**2:
                raise AppError('SEMANTIC_DISK_BUDGET', '语义任务需要至少 256MiB 磁盘余量', exit_code=6)
            with managed_workspace(root, kind) as job:
                job.hold_for_review('Semantic requests/responses retained; explicit project recover --cleanup-jobs can reclaim this workspace')
                token = _CURRENT.set(job)
                try:
                    result = function(root, project, **options)
                    result['managed_workspace'] = dict(job_id=job.path.name, kind=kind, path=str(job.path),
                        evidence_retained=True, explicit_cleanup='project recover --cleanup-jobs')
                    return result
                finally:
                    _CURRENT.reset(token)
        return execute
    return decorate
