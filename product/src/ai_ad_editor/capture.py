"""Bounded native Windows capture into editable projects, without a GUI service."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import sys

from .errors import AppError, argument_error
from .material_project import commit_asset, new_asset_id
from .media import ffmpeg_path, probe_media
from .policy import resolve_local_path
from .project import load_project
from .utils import atomic_write_json, ensure_inside, new_id, now_iso, run_process, sha256_file

ENGINE = "ffmpeg-windows-capture-v1"


def parse_devices(stderr: str) -> list[dict]:
    """Parse actual dshow output; an inventory ID binds kind and device path."""
    devices = []
    for line in stderr.splitlines():
        match = re.search(r'\] "(.*)" \((video|audio)\)\s*$', line)
        if match:
            devices.append({"name": match[1], "kind": match[2], "alternative_name": None})
        else:
            match = re.search(r'\]   Alternative name "(.*)"\s*$', line)
            if match and devices:
                devices[-1]["alternative_name"] = match[1]
    seen = set()
    for row in devices:
        identity = row["kind"] + "\0" + (row["alternative_name"] or row["name"])
        row["id"] = "device_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        if row["id"] in seen:
            raise AppError("CAPTURE_DEVICE_AMBIGUOUS", "设备枚举含重复标识", exit_code=6)
        seen.add(row["id"])
    return devices


def list_devices() -> dict:
    if sys.platform != "win32":
        raise AppError("CAPTURE_PLATFORM_UNSUPPORTED", "原生采集当前需要 Windows", exit_code=10)
    result = run_process([ffmpeg_path(), "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"], timeout=25)
    # dshow's list-only command intentionally exits with 1 after enumeration.
    rows = parse_devices(result.stderr)
    if not rows and not any(marker in result.stderr for marker in ("Could not enumerate", "Alternative name")):
        raise AppError("CAPTURE_ENUMERATION_FAILED", "当前 FFmpeg 无法枚举 DirectShow 设备", exit_code=10, cause=result.stderr[-1500:])
    return {"engine": ENGINE, "platform": "win32", "devices": rows,
            "screen_backends": ["gdigrab-desktop", "gdigrab-window-title"],
            "camera_count": sum(row["kind"] == "video" for row in rows),
            "microphone_count": sum(row["kind"] == "audio" for row in rows),
            "network": "disabled", "capture_started": False}


def _dshow_token(name: str) -> str:
    # av_get_token has its own single-quote syntax, independently of Windows argv.
    return "'" + name.replace("'", "'\\''") + "'"


def select_device(devices: list[dict], ident: str | None, kind: str) -> dict:
    selected = [row for row in devices if row["id"] == ident and row["kind"] == kind]
    if len(selected) != 1:
        raise argument_error("设备 ID 未在当前枚举中匹配指定类型；先运行 capture devices", "device_id")
    return selected[0]


def validate_options(args) -> None:
    if args.kind not in {"screen", "window", "camera", "microphone"}:
        raise argument_error("未知采集来源", "kind")
    if type(args.duration_seconds) not in (int, float) or not math.isfinite(args.duration_seconds) or not .25 <= args.duration_seconds <= 3600:
        raise argument_error("采集时长须为 0.25–3600 秒", "duration_seconds")
    if type(args.fps) is not int or not 1 <= args.fps <= 60:
        raise argument_error("帧率须为 1–60 的整数", "fps")
    if args.encoder not in {"auto", "libx264", "h264_nvenc"}:
        raise argument_error("编码器须为 auto/libx264/h264_nvenc", "encoder")
    if bool(args.window_title) != (args.kind == "window") or (args.window_title and (len(args.window_title) > 512 or any(ord(c) < 32 for c in args.window_title))):
        raise argument_error("window 类型必须显式指定非空窗口标题，其他类型不接受该参数", "window_title")
    if bool(args.camera_id) != (args.kind == "camera"):
        raise argument_error("camera 类型必须显式指定 camera-id", "camera_id")
    if args.kind == "microphone" and not args.microphone_id:
        raise argument_error("录音必须显式指定 microphone-id", "microphone_id")
    if (args.width is None) != (args.height is None):
        raise argument_error("宽高须一起提供", "width/height")
    if args.width is not None and any(type(v) is not int or not 16 <= v <= 8192 for v in (args.width, args.height)):
        raise argument_error("采集宽高须为 16–8192 的整数", "width/height")
    if any(type(v) is not int or not -32768 <= v <= 32767 for v in (args.offset_x, args.offset_y)):
        raise argument_error("采集偏移须为 -32768–32767 的整数", "offset_x/offset_y")
    if args.kind in {"camera", "microphone"} and (args.offset_x or args.offset_y or args.draw_mouse):
        raise argument_error("相机/录音不接受屏幕偏移或光标选项", "kind")
    if args.kind == "microphone" and (args.width is not None or args.encoder != "auto" or args.fps != 30):
        raise argument_error("纯录音不接受视频参数", "kind")


def build_command(args, target: Path, camera: dict | None, microphone: dict | None, encoder: str) -> list[str]:
    command = [ffmpeg_path(), "-hide_banner", "-loglevel", "warning", "-nostdin", "-n"]
    video = args.kind != "microphone"
    if args.kind in {"screen", "window"}:
        command += ["-thread_queue_size", "512", "-f", "gdigrab", "-framerate", str(args.fps),
                    "-draw_mouse", "1" if args.draw_mouse else "0", "-offset_x", str(args.offset_x), "-offset_y", str(args.offset_y)]
        if args.width is not None:
            command += ["-video_size", f"{args.width}x{args.height}"]
        command += ["-i", "desktop" if args.kind == "screen" else "title=" + args.window_title]
    elif camera:
        command += ["-thread_queue_size", "512", "-f", "dshow", "-framerate", str(args.fps)]
        if args.width is not None:
            command += ["-video_size", f"{args.width}x{args.height}"]
        command += ["-i", "video=" + _dshow_token(camera["alternative_name"] or camera["name"])]
    if microphone:
        command += ["-thread_queue_size", "512", "-f", "dshow", "-i",
                    "audio=" + _dshow_token(microphone["alternative_name"] or microphone["name"])]
    command += ["-t", str(args.duration_seconds)]
    if video:
        command += ["-map", "0:v:0", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-r", str(args.fps),
                    "-fps_mode", "cfr", "-c:v", encoder, "-pix_fmt", "yuv420p"]
        command += ["-preset", "p4", "-cq", "20"] if encoder == "h264_nvenc" else ["-preset", "veryfast", "-crf", "20", "-threads", "2"]
    if microphone:
        command += ["-map", ("1:a:0" if video else "0:a:0"), "-af", "aresample=async=1000:first_pts=0", "-ar", "48000",
                    "-c:a", "aac" if video else "pcm_s16le"]
        if video:
            command += ["-b:a", "192k"]
    else:
        command += ["-an"]
    if video:
        command += ["-movflags", "+faststart"]
    return command + [str(target)]


def command(args, envelope):
    if args.action == "devices":
        return envelope("capture.devices", args, data=list_devices())
    validate_options(args)
    if sys.platform != "win32":
        raise AppError("CAPTURE_PLATFORM_UNSUPPORTED", "原生采集当前需要 Windows", exit_code=10)
    root, project = load_project(args.project)
    cancel = resolve_local_path(root, args.cancel_file, field="cancel_file") if args.cancel_file else None
    if cancel and cancel.exists():
        raise AppError("CANCELLED", "采集在启动前已取消", exit_code=8)
    inventory = list_devices() if args.camera_id or args.microphone_id else {"devices": []}
    camera = select_device(inventory["devices"], args.camera_id, "video") if args.camera_id else None
    microphone = select_device(inventory["devices"], args.microphone_id, "audio") if args.microphone_id else None
    aid = new_asset_id(project, args.asset_id, "capture")
    directory = ensure_inside(root, root / "assets/captures" / aid)
    if directory.exists():
        raise argument_error("采集输出目录已存在；不会覆盖", str(directory))
    video = args.kind != "microphone"
    encoder, fallback = args.encoder, None
    if encoder == "auto":
        from .community_device import inspect
        encoder = "h264_nvenc" if video and inspect()["available"] else "libx264"
        if video and encoder == "libx264":
            fallback = "nvidia_gpu_unavailable"
    destination = directory / ("capture.mp4" if video else "capture.wav")
    plan = {"engine": ENGINE, "kind": args.kind, "duration_seconds": args.duration_seconds,
            "fps": args.fps if video else None, "requested_encoder": args.encoder, "selected_encoder": encoder if video else None,
            "cpu_fallback_reason": fallback, "camera": camera, "microphone": microphone,
            "window_title": args.window_title, "output": str(destination), "network": "disabled",
            "av_sync_review_required": bool(video and microphone), "rights_verified": False}
    if args.dry_run:
        plan["command"] = build_command(args, destination, camera, microphone, encoder)
        return envelope("capture.record", args, status="planned", data=plan)
    job = root / "cache/capture" / new_id("run")
    job.mkdir(parents=True, exist_ok=False)
    atomic_write_json(job / "plan.json", plan)
    ffmpeg_sha = sha256_file(Path(ffmpeg_path()))
    attempts = []
    published_files = []
    owned_directory = False
    started = datetime.now(timezone.utc).isoformat()
    try:
        for selected in ([encoder, "libx264"] if video and args.encoder == "auto" and encoder == "h264_nvenc" else [encoder]):
            temporary = job / (selected + (".mp4" if video else ".wav"))
            cmd = build_command(args, temporary, camera, microphone, selected)
            result = run_process(cmd, timeout=args.duration_seconds + 60, cancel_file=cancel)
            attempts.append({"encoder": selected if video else None, "returncode": result.returncode,
                             "stderr": result.stderr[-16000:], "command": cmd})
            atomic_write_json(job / "attempts.json", {"attempts": attempts})
            if result.returncode == 0:
                encoder = selected
                break
            if args.encoder == "auto" and selected == "h264_nvenc":
                plan["cpu_fallback_reason"] = "nvenc_capture_failed"
        else:
            raise AppError("CAPTURE_INPUT_FAILED", "原生采集失败；诊断和部分文件保留在 cache/capture", exit_code=6, cause=result.stderr[-1500:])
        if cancel and cancel.exists():
            raise AppError("CANCELLED", "采集输出登记前已取消", exit_code=8)
        if sha256_file(Path(ffmpeg_path())) != ffmpeg_sha:
            raise AppError("CAPTURE_EXECUTABLE_CHANGED", "采集过程中 FFmpeg 发生变化", exit_code=10)
        probe = probe_media(temporary)
        duration = probe.get("duration_seconds")
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or abs(duration - args.duration_seconds) > max(.15, 2 / args.fps if video else .05):
            raise AppError("CAPTURE_DURATION_INVALID", "实际采集时长未满足声明；不登记半成品", exit_code=6)
        if (video and not probe.get("video", {}).get("codec")) or (microphone and not probe.get("audio", {}).get("codec")):
            raise AppError("CAPTURE_STREAM_MISSING", "采集输出缺少请求的音视频流", exit_code=6)
        decoded = run_process([ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-nostdin", "-xerror", "-i", str(temporary), "-f", "null", "-"],
                              timeout=args.duration_seconds + 60, cancel_file=cancel)
        if decoded.returncode:
            raise AppError("CAPTURE_DECODE_FAILED", "采集输出未通过完整解码", exit_code=6, cause=decoded.stderr[-1500:])
        plan.update(selected_encoder=encoder if video else None, started_at_utc=started,
                    completed_at_utc=datetime.now(timezone.utc).isoformat(), ffmpeg_sha256=ffmpeg_sha,
                    full_decode=True, probe=probe, attempts=attempts)
        directory.mkdir(parents=True, exist_ok=False)
        owned_directory = True
        # A fresh owned destination and xb preserve existing media even on a race.
        with temporary.open("rb") as source, destination.open("xb") as output:
            published_files.append(destination)
            shutil.copyfileobj(source, output)
            output.flush()
            os.fsync(output.fileno())
        digest = "sha256:" + sha256_file(destination)
        evidence = directory / "SOURCE.json"
        if cancel and cancel.exists():
            raise AppError("CANCELLED", "采集登记前已取消", exit_code=8)
        atomic_write_json(evidence, {**plan, "sha256": digest})
        published_files.append(evidence)
        relative_evidence = evidence.relative_to(root).as_posix()
        kind = "video" if video else "audio"
        asset = {"id": aid, "kind": kind, "uri": destination.relative_to(root).as_posix(), "sha256": digest,
                 "probe": probe, "rights_ref": aid, "source": {"source_url": "local://" + relative_evidence,
                 "source_version": ENGINE, "retrieved_at": now_iso(), "original_name": destination.name}}
        rights = {"asset_id": aid, "kind": kind, "sha256": digest, "source_url": "local://" + relative_evidence,
                  "source_version": ENGINE, "creator": "local capture", "license_spdx": "LicenseRef-UNVERIFIED",
                  "license_url": "", "attribution": "", "permitted_uses": ["internal"], "restrictions": [],
                  "evidence": relative_evidence, "verification_status": "unverified", "verified_by": "",
                  "takedown_status": "clear", "retrieved_at": now_iso(),
                  "notes": "Capture does not grant rights to screen, camera, speech or underlying content."}
        data = commit_asset(root, project, asset, rights, command="capture.record", report=plan)
        atomic_write_json(job / "success.json", {"asset_id": aid, "sha256": digest, "full_decode": True})
        return envelope("capture.record", args, data={**data, "capture": plan}, operation_id=data["operation_id"],
                        warnings=[{"code": "CAPTURE_REVIEW_REQUIRED", "message": "检查采集画面/声音、音画同步与内容权利"}])
    except BaseException as exc:
        for path in published_files:
            if path.is_file() and not path.is_symlink():
                path.unlink()
        if owned_directory and directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
        atomic_write_json(job / "failure.json", {"status": "failed", "error": str(exc), "code": getattr(exc, "code", None),
                          "asset_registered": False, "diagnostics_preserved": True})
        raise


def add_parser(subs, leaf):
    parser = subs.add_parser("capture", help="原生 Windows 窗口、屏幕、摄像头和麦克风采集")
    actions = parser.add_subparsers(dest="action", required=True)
    leaf(actions.add_parser("devices", help="只枚举 DirectShow 设备，不启动录制"))
    record = leaf(actions.add_parser("record", help="有界录制、完整解码并登记为可编辑素材"))
    record.add_argument("--project", required=True)
    record.add_argument("--kind", choices=("screen", "window", "camera", "microphone"), required=True)
    record.add_argument("--duration-seconds", type=float, required=True)
    record.add_argument("--window-title")
    record.add_argument("--camera-id")
    record.add_argument("--microphone-id")
    record.add_argument("--width", type=int)
    record.add_argument("--height", type=int)
    record.add_argument("--offset-x", type=int, default=0)
    record.add_argument("--offset-y", type=int, default=0)
    record.add_argument("--draw-mouse", action="store_true")
    record.add_argument("--fps", type=int, default=30)
    record.add_argument("--encoder", choices=("auto", "libx264", "h264_nvenc"), default="auto")
    record.add_argument("--asset-id")
    record.add_argument("--cancel-file")
