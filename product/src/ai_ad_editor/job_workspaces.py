"""Owned job workspaces and identity-checked recovery of interrupted output publication."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from .errors import AppError
from .utils import atomic_write_json, load_json, now_iso, sha256_file

FORMAT = 'agent-owned-job-workspace-v1'
JOB_RE = re.compile(r'job-[0-9a-f]{32}')
KINDS = {'four-stem-separation', 'subtitle-dubbing', 'semantic-register', 'semantic-index',
         'semantic-calibrate', 'semantic-search', 'video-generation', 'lip-sync', 'frame-interpolation'}
MAX_OUTPUTS = 4096
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
_SCOPE = ContextVar('agent_owned_job_scope', default=None)


def _owned(root, path):
    root, path = Path(root).absolute(), Path(path).absolute()
    if str(root).startswith('\\\\') or not path.is_relative_to(root):
        raise ValueError('Job path must stay in the local owned project')
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise ValueError('Job path cannot cross symlinks or junctions')
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Resolved job path escaped the project')
    return path.resolve()


class Lease:
    def __init__(self, path, *, create=False):
        self.path, self.handle = path, None
        handle = path.open('x+b' if create else 'r+b')
        try:
            if create:
                handle.write(b'0')
                handle.flush()
                os.fsync(handle.fileno())
            if os.fstat(handle.fileno()).st_size != 1:
                raise ValueError('Invalid job lease file')
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.handle = handle
        except BaseException:
            handle.close()
            raise

    def close(self):
        if self.handle is not None:
            self.handle.close()  # OS releases the lease, including on hard process termination.
            self.handle = None


def _identity(path):
    stat = path.stat()
    if not path.is_file() or not stat.st_ino:
        raise ValueError('Publication requires a regular file with stable filesystem identity')
    return dict(device=stat.st_dev, inode=stat.st_ino, bytes=stat.st_size)


def _references(root):
    project = load_json(root / 'project.json')
    result = set()
    for asset in project.get('assets', []):
        uri = asset.get('uri')
        if isinstance(uri, str) and uri and '://' not in uri:
            path = Path(uri)
            result.add((path if path.is_absolute() else root / path).resolve())
    from .rights import active_records, load_ledger
    for record in active_records(load_ledger(root)):
        for key in ('evidence', 'license_url'):
            value = record.get(key)
            if isinstance(value, str) and value:
                value = value.removeprefix('local://')
                if '://' not in value:
                    path = Path(value)
                    result.add((path if path.is_absolute() else root / path).resolve())
    return result


def _scan_owned_tree(root, job):
    """Verify final absolute paths before any recursive removal on Windows."""
    stack, count, total = [job], 0, 0
    while stack:
        directory = _owned(root, stack.pop())
        with os.scandir(directory) as entries:
            for entry in entries:
                path = _owned(root, Path(entry.path))
                count += 1
                if count > 10000:
                    raise ValueError('Job cleanup file budget exceeded')
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                else:
                    raise ValueError('Unknown job filesystem entry')
    return count, total


def _load_record(root, job):
    if job.parent != _owned(root, root / 'cache/managed-jobs') or not JOB_RE.fullmatch(job.name):
        raise ValueError('Unknown job directory')
    path = _owned(root, job / 'job.json')
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError('Job manifest exceeds byte budget')
    record = json.loads(path.read_text('utf8'))
    if (not isinstance(record, dict) or record.get('format') != FORMAT or record.get('job_id') != job.name
            or record.get('project') != str(root.resolve()) or record.get('kind') not in KINDS
            or not isinstance(record.get('outputs'), list) or len(record['outputs']) > MAX_OUTPUTS
            or not isinstance(record.get('trees', []), list) or len(record.get('trees', [])) > 1):
        raise ValueError('Job manifest ownership or format invalid')
    return record


def _plan(root, job, record, *, preserve_outputs=False):
    references = _references(root)
    outputs, seen = [], set()
    for item in record['outputs']:
        relative = item.get('path') if isinstance(item, dict) else None
        if (not isinstance(relative, str) or not relative.startswith('assets/derived/')
                or any(part in ('..', '.') for part in relative.split('/')) or ':' in relative or '\\' in relative
                or not isinstance(item.get('identity'), dict)
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', str(item.get('sha256')))):
            raise ValueError('Invalid publication intent')
        path = _owned(root, root / relative)
        if path in seen:
            raise ValueError('Duplicate publication intent')
        seen.add(path)
        if not path.exists():
            status = 'missing'
        elif preserve_outputs or path in references:
            status = 'referenced_preserved' if path in references else 'delivered_preserved'
        elif _identity(path) != item['identity'] or 'sha256:' + sha256_file(path) != item['sha256']:
            status = 'changed_preserved'
        else:
            status = 'owned_unreferenced'
        outputs.append(dict(path=relative, status=status, identity=item['identity'], sha256=item['sha256']))
    count, total = _scan_owned_tree(root, job)
    result = dict(job_id=job.name, kind=record['kind'], files=count, workspace_bytes=total, outputs=outputs)
    if record.get('trees'):
        from .job_trees import plan as tree_plan
        result['trees'] = [tree_plan(root, item, record['kind'], references,
            preserve_outputs=preserve_outputs) for item in record['trees']]
    return result


def _recover_one(root, job, *, dry_run=False, preserve_outputs=False, retain_workspace=False):
    lease = None
    try:
        job = _owned(root, job)
        _load_record(root, job)
        lease_path = _owned(root, job / 'owner.lock')
        try:
            lease = Lease(lease_path)
        except OSError:
            return dict(job_id=job.name, status='active_or_locked_preserved')
        record = _load_record(root, job)
        plan = _plan(root, job, record, preserve_outputs=preserve_outputs)
        if any(item['status'] == 'changed_preserved' for item in plan['outputs'] + plan.get('trees', [])):
            return dict(plan, status='changed_output_preserved')
        if dry_run:
            return dict(plan, status='cleanup_planned')
        # Recheck the absolute tree and all output identities immediately before mutation.
        _scan_owned_tree(root, job)
        if _plan(root, job, record, preserve_outputs=preserve_outputs) != plan:
            return dict(plan, status='changed_during_review_preserved')
        removed = []
        for item in plan['outputs']:
            if item['status'] == 'owned_unreferenced':
                path = _owned(root, root / item['path'])
                if _identity(path) != item['identity']:
                    raise ValueError('Output identity changed during recovery')
                path.unlink()
                removed.append(item['path'])
        for item, intent in zip(plan.get('trees', []), record.get('trees', [])):
            if item['status'] == 'owned_unreferenced':
                from .job_trees import remove as remove_tree
                remove_tree(root, intent, record['kind'])
                removed.append(item['path'])
        if retain_workspace:
            return dict(plan, status='preserved_for_review', removed_outputs=removed,
                path=str(job), reason=record.get('review_reason', 'semantic execution evidence'))
        lease.close()
        lease = None
        _scan_owned_tree(root, job)
        shutil.rmtree(job)
        return dict(plan, status='cleaned', removed_outputs=removed)
    except (OSError, ValueError, TypeError, KeyError, AppError) as exc:
        return dict(job_id=job.name, status='unverified_or_blocked_preserved', reason=str(exc))
    finally:
        if lease is not None:
            lease.close()


def recover_workspaces(root, *, dry_run=False):
    """Caller holds the project's mutation lock for actual cleanup."""
    root = Path(root).resolve()
    base = _owned(root, root / 'cache/managed-jobs')
    if not base.exists():
        return dict(format=FORMAT, jobs=[], cleaned=0, dry_run=dry_run, legacy_unmanaged='preserved')
    jobs = []
    with os.scandir(base) as entries:
        for entry in entries:
            if len(jobs) == 256:
                jobs.append(dict(status='scan_budget_reached', remaining='repeat explicit recovery'))
                break
            jobs.append(_recover_one(root, Path(entry.path), dry_run=dry_run))
    return dict(format=FORMAT, jobs=jobs, cleaned=sum(j['status'] == 'cleaned' for j in jobs),
        dry_run=dry_run, legacy_unmanaged='preserved')


class Workspace:
    def __init__(self, root, kind):
        self.root = Path(root).resolve()
        if kind not in KINDS:
            raise ValueError('Unknown owned workspace kind')
        base = _owned(self.root, self.root / 'cache/managed-jobs')
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / ('job-' + uuid.uuid4().hex)
        self.path.mkdir(exist_ok=False)
        self.lease = Lease(self.path / 'owner.lock', create=True)
        self.record = dict(format=FORMAT, project=str(self.root), job_id=self.path.name,
            kind=kind, owner_pid=os.getpid(), created_at=now_iso(), outputs=[])
        try:
            atomic_write_json(self.path / 'job.json', self.record)
        except BaseException:
            self.lease.close()
            raise

    def publish(self, stage, destination):
        if len(self.record['outputs']) >= MAX_OUTPUTS:
            raise ValueError('Job output budget exceeded')
        stage, destination = _owned(self.root, stage), _owned(self.root, destination)
        if not stage.is_relative_to(self.path) or not destination.is_relative_to(self.root / 'assets/derived'):
            raise ValueError('Publication must move an owned stage into derived assets')
        if destination.exists():
            raise FileExistsError(str(destination))
        relative = destination.relative_to(self.root).as_posix()
        if any(row['path'] == relative for row in self.record['outputs']):
            raise ValueError('Output already planned')
        with stage.open('r+b') as stream:
            stream.flush()
            os.fsync(stream.fileno())
        self.record['outputs'].append(dict(path=relative, identity=_identity(stage), sha256='sha256:' + sha256_file(stage)))
        if len(json.dumps(self.record, ensure_ascii=False, indent=2).encode('utf-8')) > MAX_MANIFEST_BYTES-1:
            self.record['outputs'].pop()
            raise ValueError('Job manifest byte budget exceeded')
        atomic_write_json(self.path / 'job.json', self.record)  # write-ahead intent before any public path exists
        destination.parent.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt':
            os.rename(stage, destination)  # Windows same-volume rename fails if destination exists.
        else:
            os.link(stage, destination)  # exclusive creation; preserve the recorded file identity
            stage.unlink()
        if _identity(destination) != self.record['outputs'][-1]['identity']:
            raise ValueError('Atomic publication changed file identity')

    def finish(self, *, preserve_outputs=False):
        self.lease.close()
        if self.record['kind'].startswith('semantic-') and self.record.get('review_reason'):
            return _recover_one(self.root, self.path, preserve_outputs=preserve_outputs, retain_workspace=True)
        if self.record.get('review_reason'):
            return dict(job_id=self.path.name, kind=self.record['kind'], status='preserved_for_review',
                path=str(self.path), reason=self.record['review_reason'])
        return _recover_one(self.root, self.path, preserve_outputs=preserve_outputs)

    def hold_for_review(self, reason):
        self.record['review_reason'] = str(reason)[:512]
        atomic_write_json(self.path / 'job.json', self.record)

    def publish_tree(self, stage, destination):
        from .job_trees import publish
        publish(self, stage, destination)


class WorkspaceScope:
    def __init__(self, root):
        self.root, self.jobs = Path(root).resolve(), []

    def finish(self):
        result, self.jobs = self.jobs, []
        return [job.finish() for job in result]


@contextmanager
def workspace_scope(root):
    scope = WorkspaceScope(root)
    token = _SCOPE.set(scope)
    try:
        yield scope
    finally:
        for job in scope.jobs:
            job.lease.close()  # Preserve durable manifests if a higher-level recovery itself failed.
        _SCOPE.reset(token)


@contextmanager
def managed_workspace(root, kind):
    job = Workspace(root, kind)
    scope = _SCOPE.get()
    if scope is not None:
        if scope.root != job.root:
            job.finish()
            raise ValueError('Workspace and transaction project differ')
        scope.jobs.append(job)
    succeeded = False
    try:
        yield job
        succeeded = True
    finally:
        if scope is None:
            job.finish(preserve_outputs=succeeded)
