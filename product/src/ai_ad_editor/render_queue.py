"""Persistent local render queue primitives.

The queue is intentionally project-local and JSON based.  It gives an Agent a
stable place to enqueue render variants, inspect state, request cancellation,
and resume a failed job without introducing a service, daemon, database, or
network dependency.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error
from .utils import atomic_write_json, ensure_inside, load_json, new_id, now_iso


QUEUE_VERSION = "0.1.0"
QUEUE_FILENAME = "render-queue.json"
JOB_STATUSES = {"pending", "running", "succeeded", "failed", "cancelled"}


def _valid_job_id(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = str(value)
    return bool(text) and len(text) <= 128 and text.replace("_", "").replace("-", "").isalnum()


def queue_path(root: Path) -> Path:
    return root / "operations" / QUEUE_FILENAME


def cancel_path(root: Path, job_id: str) -> Path:
    if not _valid_job_id(job_id):
        raise argument_error("队列作业 ID 只能包含字母、数字、下划线和连字符", "job_id")
    return root / "operations" / "queue-cancel" / f"{job_id}.cancel"


def empty_queue(project_id: str | None = None) -> dict[str, Any]:
    return {
        "queue_version": QUEUE_VERSION,
        "project_id": project_id,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "jobs": [],
    }


def load_queue(root: Path, *, project_id: str | None = None) -> dict[str, Any]:
    path = queue_path(root)
    if not path.exists():
        return empty_queue(project_id)
    queue = load_json(path)
    version = str(queue.get("queue_version", ""))
    if version != QUEUE_VERSION:
        raise AppError("QUEUE_VERSION_UNSUPPORTED", f"不支持的渲染队列版本: {version or '<missing>'}", exit_code=2, path=str(path))
    jobs = queue.get("jobs")
    if not isinstance(jobs, list):
        raise AppError("QUEUE_INVALID", "渲染队列 jobs 必须是数组", exit_code=2, path=str(path))
    seen: set[str] = set()
    for index, job in enumerate(jobs):
        if not isinstance(job, dict) or not _valid_job_id(job.get("job_id", "")):
            raise AppError("QUEUE_INVALID", f"渲染队列 jobs[{index}] 的 job_id 无效", exit_code=2, path=str(path))
        job_id = str(job["job_id"])
        if job_id in seen:
            raise AppError("QUEUE_INVALID", f"渲染队列存在重复 job_id: {job_id}", exit_code=2, path=str(path))
        seen.add(job_id)
        if job.get("status") not in JOB_STATUSES:
            raise AppError("QUEUE_INVALID", f"渲染队列作业状态无效: {job.get('status')}", exit_code=2, path=str(path))
    if project_id and queue.get("project_id") not in {None, project_id}:
        raise AppError("QUEUE_PROJECT_MISMATCH", "渲染队列不属于当前项目", exit_code=2, path=str(path))
    queue.setdefault("project_id", project_id)
    return queue


def save_queue(root: Path, queue: dict[str, Any]) -> Path:
    queue["queue_version"] = QUEUE_VERSION
    queue["updated_at"] = now_iso()
    path = queue_path(root)
    atomic_write_json(path, queue)
    return path


def _relative_output(root: Path, value: Any, job_id: str, container: str = "mp4") -> str:
    if value in {None, ""}:
        suffix = {"mp4": ".mp4", "webm": ".webm", "mkv": ".mkv"}.get(container, ".mp4")
        return f"renders/queue_{job_id}{suffix}"
    raw = Path(str(value)).expanduser()
    candidate = ensure_inside(root, raw if raw.is_absolute() else root / raw)
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise argument_error("队列输出路径必须位于项目目录内", str(candidate)) from exc


def normalize_job(root: Path, raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise argument_error("渲染队列作业必须是对象")
    job_id = str(raw.get("job_id", raw.get("id", ""))).strip() or new_id("job")
    if not _valid_job_id(job_id):
        raise argument_error("队列作业 ID 只能包含字母、数字、下划线和连字符", "job_id")
    container = str(raw.get("container", "mp4")).lower()
    if container not in {"mp4", "webm", "mkv"}:
        raise argument_error(f"队列作业容器无效: {container}", "container")
    profile = raw.get("profile")
    if profile is not None and str(profile) not in {"vertical", "square", "landscape", "vertical_720", "landscape_720", "custom"}:
        raise argument_error(f"队列作业 profile 无效: {profile}", "profile")
    publish = raw.get("publish", False)
    if not isinstance(publish, bool):
        raise argument_error("队列作业 publish 必须是布尔值", "publish")
    normalized: dict[str, Any] = {
        "job_id": job_id,
        "label": str(raw.get("label", job_id)),
        "status": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "sequence_id": raw.get("sequence_id"),
        "output": _relative_output(root, raw.get("output"), job_id, container),
        "publish": publish,
        "container": container,
        "profile": profile,
        "width": raw.get("width"),
        "height": raw.get("height"),
        "video_codec": raw.get("video_codec"),
        "audio_codec": raw.get("audio_codec"),
        "crf": raw.get("crf"),
        "video_bitrate": raw.get("video_bitrate"),
        "audio_bitrate": raw.get("audio_bitrate"),
        "pixel_format": raw.get("pixel_format"),
        "sequence_sampling": raw.get('sequence_sampling'),
        "sequence_memory_mib": raw.get('sequence_memory_mib'),
        "attempts": 0,
        "operation_id": None,
        "cancel_requested": False,
        "errors": [],
        "warnings": [],
    }
    sampling = normalized['sequence_sampling']
    from .hardware_acceleration import CLI_FIELDS, apply_overrides
    for field in (*CLI_FIELDS, 'hardware_probe_mib'):
        normalized[field] = raw.get(field)
    apply_overrides({}, normalized)
    from .projection_opencl import CLI_FIELDS as PROJECTION_FIELDS, apply_overrides as projection_overrides
    for field in (*PROJECTION_FIELDS,'projection_memory_mib'):
        normalized[field]=raw.get(field)
    projection_overrides({},normalized)
    if sampling is not None and (not isinstance(sampling, str) or sampling not in {'bilinear','area'}):
        raise argument_error('队列 sequence_sampling 只允许 bilinear 或 area', 'sequence_sampling')
    memory_mib = normalized['sequence_memory_mib']
    if memory_mib is not None and (type(memory_mib) is not int or not 1 <= memory_mib <= 65536):
        raise argument_error('队列 sequence_memory_mib 必须为 1..65536 的整数', 'sequence_memory_mib')
    for field in ("width", "height", "crf"):
        if normalized[field] is not None:
            try:
                normalized[field] = int(normalized[field])
            except (TypeError, ValueError) as exc:
                raise argument_error(f"队列作业 {field} 必须是整数", field) from exc
    for field in ("video_codec", "audio_codec", "video_bitrate", "audio_bitrate", "pixel_format"):
        if normalized[field] is not None:
            normalized[field] = str(normalized[field])
    if normalized["profile"] == "custom" and (normalized["width"] is None or normalized["height"] is None):
        raise argument_error("队列作业 profile=custom 必须同时提供 width 和 height", "profile")
    if (normalized["width"] is None) != (normalized["height"] is None):
        raise argument_error("队列作业 width 和 height 必须同时提供", "width/height")
    if normalized["profile"] not in {None, "custom"} and (normalized["width"] is not None or normalized["height"] is not None):
        raise argument_error("预设 profile 不能同时提供 width/height；请使用 profile=custom", "profile")
    if normalized["width"] is not None:
        width, height = int(normalized["width"]), int(normalized["height"])
        if width < 64 or height < 64 or width > 8192 or height > 8192 or width % 2 or height % 2:
            raise argument_error("队列作业自定义画布必须是 64..8192 范围内的偶数宽高", "width/height")
    if normalized["container"] == "webm":
        # A WebM variant must be runnable without relying on an incompatible
        # project default (usually H.264/AAC).
        normalized["video_codec"] = normalized["video_codec"] or "libvpx-vp9"
        normalized["audio_codec"] = normalized["audio_codec"] or "libopus"
    return normalized


def enqueue(root: Path, project_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    queue = load_queue(root, project_id=project_id)
    raw_jobs = payload.get("jobs") if isinstance(payload.get("jobs"), list) else [payload]
    if not raw_jobs:
        raise argument_error("渲染队列作业不能为空")
    existing = {str(job.get("job_id")) for job in queue["jobs"] if isinstance(job, dict)}
    added: list[dict[str, Any]] = []
    for raw in raw_jobs:
        job = normalize_job(root, raw)
        if job["job_id"] in existing:
            raise argument_error(f"队列作业 ID 已存在: {job['job_id']}", "job_id")
        existing.add(job["job_id"])
        queue["jobs"].append(job)
        added.append(copy.deepcopy(job))
    queue["project_id"] = project_id
    save_queue(root, queue)
    return queue, added


def find_job(queue: dict[str, Any], job_id: str) -> dict[str, Any]:
    for job in queue.get("jobs", []):
        if isinstance(job, dict) and job.get("job_id") == job_id:
            return job
    raise AppError("QUEUE_JOB_NOT_FOUND", f"找不到渲染队列作业: {job_id}", exit_code=3, path="jobs")


def set_status(job: dict[str, Any], status: str, *, error: dict[str, Any] | None = None, operation_id: str | None = None) -> None:
    if status not in JOB_STATUSES:
        raise argument_error(f"队列状态无效: {status}", "status")
    job["status"] = status
    job["updated_at"] = now_iso()
    if error is not None:
        job.setdefault("errors", []).append(error)
    if operation_id:
        job["operation_id"] = operation_id
