from __future__ import annotations

"""Local, loss-aware interchange for readable Jianying-style draft JSON.

This module implements file mappings, not a Jianying runtime. No upstream
package, effect resource, cloud loader or GUI is imported or executed.
"""

import copy
import json
import math
import os
import re
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .errors import AppError
from .policy import reference_kind, resolve_local_path
from .project import TICKS_PER_SECOND, create_project, initial_ledger, save_project
from .rights import add_record, save_ledger
from .sequence_canvas import sequence_canvas
from .utils import ID_RE, atomic_write_json, new_id, now_iso, safe_filename, sha256_bytes, sha256_file
from .validator import validate_project


ADAPTER_VERSION = "0.1.0"
DRAFT_PROFILE = "jianying-plaintext-v1"
DRAFT_FORMAT = "jianying-draft-json"
MICROSECONDS = 1_000_000
MEDIA_GROUPS = {"videos", "images", "audios", "stickers"}
KEYFRAME_PROPERTIES = {
    "KFTypePositionX": "transform.position.x",
    "KFTypePositionY": "transform.position.y",
    "KFTypeRotation": "transform.rotation",
    "UNIFORM_SCALE": "transform.scale",
    "KFTypeAlpha": "transform.opacity",
    "KFTypeVolume": "audio.volume",
}


def is_draft(payload: Any) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("materials"), dict) and isinstance(payload.get("tracks"), list) and isinstance(payload.get("canvas_config"), dict)


def _number(value: Any, field: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} 必须为有限数值")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum) or (maximum is not None and result > maximum):
        raise ValueError(f"{field} 数值越界或非有限数值")
    return result


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    number = _number(value, field, minimum=minimum)
    if not number.is_integer():
        raise ValueError(f"{field} 必须为整数")
    return int(number)


def _tick(microseconds: Any, field: str, *, positive: bool = False) -> int:
    value = _integer(microseconds, field, minimum=1 if positive else 0)
    return max(1 if positive else 0, round(Fraction(value * TICKS_PER_SECOND, MICROSECONDS)))


def _us(ticks: int, tps: int) -> int:
    return round(Fraction(int(ticks) * MICROSECONDS, tps))


def _item(items: list[dict[str, Any]], capability: str, status: str, source: str, target: str | None = None, detail: str = "", *, preserved_source: Any = None) -> None:
    reason = {"Exact":"DIRECT_COPY", "Mapped":"FIELD_MAPPING", "Approximate":"TARGET_APPROXIMATION", "Baked":"EFFECT_BAKED", "Unsupported":"TARGET_CAPABILITY_MISSING", "Failed":"ADAPTER_ERROR"}[status]
    entry = {"item_id":f"item_{len(items):04d}", "capability": capability, "status": status, "source": source, "target": target, "detail": detail, "source_path":source, "target_path":target, "reason_code":reason, "message":detail}
    if preserved_source is not None:
        entry["preserved_source"] = _preserve(preserved_source)
    items.append(entry)


def _preserve(value: Any) -> Any:
    """Keep unsupported data auditable without retaining executable endpoints."""
    if isinstance(value, dict):
        return {str(key): _preserve(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_preserve(child) for child in value]
    if isinstance(value, str):
        # Text materials wrap rich text in a JSON string; redact references in
        # that structure as well rather than hiding a URL inside an opaque blob.
        if value.lstrip().startswith(("{", "[")):
            try:
                return json.dumps(_preserve(json.loads(value)), ensure_ascii=False)
            except ValueError:
                pass
        if reference_kind(value) == "provider" or ("://" in value and reference_kind(value) == "remote"):
            return {"redacted_reference_sha256": sha256_bytes(value.encode("utf-8"))}
    return value


def _path(value: Any, base: Path, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 缺少本地路径")
    text = value.strip()
    parsed = urlsplit(text)
    if text.startswith(("\\\\", "//")) or (parsed.scheme.lower() == "file" and parsed.netloc not in {"", "localhost"}):
        raise ValueError(f"{field} 禁止 UNC 或远程文件主机")
    result = resolve_local_path(base, text, field=field)
    if str(result).startswith(("\\\\", "//")):
        raise ValueError(f"{field} 禁止网络文件路径")
    return result


def _identifier(raw: Any, prefix: str, items: list[dict[str, Any]]) -> str:
    text = str(raw or "")
    if ID_RE.fullmatch(text):
        return text
    result = f"{prefix}_{sha256_bytes(text.encode('utf-8'))[:20]}"
    _item(items, "identifier", "Mapped", prefix, result, "外部 ID 规范化为稳定的 Agent ID")
    return result


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {state.lower(): sum(item["status"] == state for item in items) for state in ("Exact", "Mapped", "Approximate", "Baked", "Unsupported", "Failed")}
    counts["status"] = "partial" if counts["failed"] else "success_with_warnings" if any(counts[state] for state in ("approximate", "baked", "unsupported")) else "success"
    return counts


def _strict_gate(items: list[dict[str, Any]], strict: bool) -> None:
    losses = [item for item in items if item["status"] in {"Approximate", "Baked", "Unsupported", "Failed"}]
    if strict and losses:
        raise AppError("CONVERSION_STRICT_REJECTED", "严格转换拒绝存在近似、不支持或失败的草稿；目标未写入", exit_code=2, cause=json.dumps({"summary": _summary(items), "items": losses}, ensure_ascii=False))


def _report(source: Path, direction: str, items: list[dict[str, Any]], *, strict: bool, source_version: Any = None) -> dict[str, Any]:
    return {
        "conversion_id":new_id("conversion"),
        "report_version": "0.1.0", "direction": direction,
        "source_format": DRAFT_FORMAT if direction == "import" else "agent-project/0.1.0",
        "target_format": "agent-project/0.1.0" if direction == "import" else DRAFT_FORMAT,
        "source_sha256": f"sha256:{sha256_file(source)}", "source_version": source_version,
        "adapter_version": ADAPTER_VERSION, "profile": DRAFT_PROFILE, "created_at": now_iso(),
        "source":{"format":DRAFT_FORMAT if direction == "import" else "agent-project", "version":source_version, "sha256":f"sha256:{sha256_file(source)}", "adapter_version":ADAPTER_VERSION},
        "target":{"format":"agent-project" if direction == "import" else DRAFT_FORMAT, "schema_version":"0.1.0" if direction == "import" else DRAFT_PROFILE},
        "policy": {"mode": "strict" if strict else "best_effort", "bake_effects": False, "network": "disabled", "jianying_runtime": False},
        "summary": _summary(items), "items": items,
        "warnings": [item for item in items if item["status"] in {"Approximate", "Baked", "Unsupported"}],
        "failures": [item for item in items if item["status"] == "Failed"],
        "errors": [item for item in items if item["status"] == "Failed"],
        "artifacts":[], "provenance":{"engine":"agent-video-kit-local-draft-adapter", "runtime_compatibility_verified":False},
    }


def _material_index(payload: dict[str, Any], source: Path) -> dict[str, tuple[str, dict[str, Any]]]:
    result: dict[str, tuple[str, dict[str, Any]]] = {}
    for group, entries in payload["materials"].items():
        if not isinstance(entries, list):
            raise ValueError(f"materials.{group} 必须为数组")
        for index, material in enumerate(entries):
            if not isinstance(material, dict) or not material.get("id"):
                raise ValueError(f"materials.{group}[{index}] 必须有唯一 id")
            identity = str(material["id"])
            if identity in result:
                raise ValueError(f"草稿素材 id 重复: {identity}")
            result[identity] = (group, material)
            # Gate every media path before staging/copying even when unused or
            # a local alternative exists next to a remote path.
            if group in MEDIA_GROUPS:
                for field in ("path", "media_path", "file_path"):
                    if material.get(field):
                        _path(material[field], source.parent, f"materials.{group}[{index}].{field}")
            if group == "texts":
                content = material.get("content")
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except ValueError:
                        content = {}
                if isinstance(content, dict):
                    styles = content.get("styles") or []
                    if not isinstance(styles, list):
                        raise ValueError(f"materials.texts[{index}].styles 必须为数组")
                    for style in styles:
                        if isinstance(style, dict) and isinstance(style.get("font"), dict) and style["font"].get("path"):
                            _path(style["font"]["path"], source.parent, f"materials.texts[{index}].font.path")
    return result


def _map_keyframes(segment: dict[str, Any], clip: dict[str, Any], items: list[dict[str, Any]], source_path: str) -> None:
    lists = segment.get("common_keyframes", [])
    if not isinstance(lists, list):
        raise ValueError(f"{source_path}.common_keyframes 必须为数组")
    seen: set[str] = set()
    for index, frames in enumerate(lists):
        field = f"{source_path}.common_keyframes[{index}]"
        if not isinstance(frames, dict):
            raise ValueError(f"{field} 必须为对象")
        prop = KEYFRAME_PROPERTIES.get(str(frames.get("property_type")))
        if prop is None:
            _item(items, "keyframes", "Unsupported", field, clip["id"], "未建立该属性映射，原始关键帧保留在报告中", preserved_source=frames)
            continue
        if prop in seen:
            raise ValueError(f"{field} 重复属性: {prop}")
        seen.add(prop)
        points = frames.get("keyframe_list")
        if not isinstance(points, list) or not points:
            raise ValueError(f"{field}.keyframe_list 必须为非空数组")
        mapped = []
        previous = -1
        for point_index, point in enumerate(points):
            if not isinstance(point, dict) or not isinstance(point.get("values"), list) or len(point["values"]) != 1:
                raise ValueError(f"{field} 关键点必须包含一个 values 数值")
            at = _tick(point.get("time_offset"), f"{field}.time_offset")
            if at <= previous or at > clip["duration_tick"]:
                raise ValueError(f"{field} 时间必须严格递增且位于片段范围内")
            previous = at
            value = _number(point["values"][0], f"{field}.values")
            if prop == "transform.position.x":
                value = 0.5 + value / 2
            elif prop == "transform.position.y":
                value = 0.5 - value / 2
            key = {"at_tick": at, "value": value, "interpolation": "linear"}
            curve = str(point.get("curveType", "Line")).lower()
            if curve == "bezier":
                left, right = point.get("left_control", {}), point.get("right_control", {})
                if not isinstance(left, dict) or not isinstance(right, dict):
                    raise ValueError(f"{field} Bezier 控制点必须为对象")
                key["interpolation"] = "bezier"
                key["control_points"] = [_number(left.get("x", 0), field, minimum=0, maximum=1), _number(left.get("y", 0), field), _number(right.get("x", 1), field, minimum=0, maximum=1), _number(right.get("y", 1), field)]
                _item(items, "keyframe-interpolation", "Approximate", f"{field}.keyframe_list[{point_index}]", clip["id"], "Bezier 控制点按本地归一化缓动解释，商业运行时曲线语义未验收")
            elif curve not in {"line", "linear"}:
                _item(items, "keyframe-interpolation", "Approximate", field, clip["id"], "未知曲线回退线性，原始点保留", preserved_source=point)
            mapped.append(key)
        clip.setdefault("keyframes", []).append({"property": prop, "keyframes": mapped})
        _item(items, "keyframes", "Mapped", field, clip["id"], f"微秒转 tick；属性 {prop}")


def _map_visual(segment: dict[str, Any], material: dict[str, Any], clip: dict[str, Any], items: list[dict[str, Any]], source_path: str) -> None:
    visual = segment.get("clip") or {}
    if not isinstance(visual, dict):
        raise ValueError(f"{source_path}.clip 必须为对象或 null")
    position, scale = visual.get("transform") or {}, visual.get("scale") or {}
    if not isinstance(position, dict) or not isinstance(scale, dict) or not isinstance(visual.get("flip", {}), dict):
        raise ValueError(f"{source_path}.clip 的 transform/scale/flip 必须为对象")
    sx = _number(scale.get("x", 1), source_path, minimum=0.000001)
    sy = _number(scale.get("y", sx), source_path, minimum=0.000001)
    clip["transform"] = {
        "position": {"x": 0.5 + _number(position.get("x", 0), source_path) / 2, "y": 0.5 - _number(position.get("y", 0), source_path) / 2},
        "scale": sx, "rotation": _number(visual.get("rotation", 0), source_path),
        "opacity": _number(visual.get("alpha", 1), source_path, minimum=0, maximum=1),
    }
    if abs(sx - sy) > 1e-9:
        _item(items, "anisotropic-scale", "Approximate", source_path, clip["id"], "当前 Agent transform 为等比缩放，使用 X 缩放；Y 原值保留", preserved_source=scale)
    flip = visual.get("flip") or {}
    for axis, effect in (("horizontal", "hflip"), ("vertical", "vflip")):
        if flip.get(axis):
            clip.setdefault("effects", []).append({"type": effect})
    crop = material.get("crop")
    if isinstance(crop, dict) and crop:
        x0 = _number(crop.get("upper_left_x", 0), source_path, minimum=0, maximum=1)
        y0 = _number(crop.get("upper_left_y", 0), source_path, minimum=0, maximum=1)
        x1 = _number(crop.get("lower_right_x", 1), source_path, minimum=0, maximum=1)
        y1 = _number(crop.get("lower_right_y", 1), source_path, minimum=0, maximum=1)
        corners = (crop.get("upper_right_x", x1), crop.get("upper_right_y", y0), crop.get("lower_left_x", x0), crop.get("lower_left_y", y1))
        if corners != (x1, y0, x0, y1):
            _item(items, "crop", "Unsupported", source_path, clip["id"], "透视/斜四边形裁切无法映射为矩形裁切", preserved_source=crop)
        elif x1 <= x0 or y1 <= y0:
            raise ValueError(f"{source_path} 裁切宽高必须大于零")
        elif (x0, y0, x1, y1) != (0, 0, 1, 1):
            clip["crop"] = {"unit": "normalized", "x": x0, "y": y0, "width": x1-x0, "height": y1-y0, "fit": "fit"}
            _item(items, "crop", "Mapped", source_path, clip["id"], "轴对齐四角映射为归一化矩形")
    _item(items, "transform", "Mapped", source_path, clip["id"], "中心原点/向上 Y 映射到左上原点归一化画布；缩放、角度与 alpha 保留")


def _text(material: dict[str, Any], height: int, clip: dict[str, Any], items: list[dict[str, Any]], source_path: str, source: Path, root: Path, project: dict[str, Any], ledger: dict[str, Any], font_assets: dict[str, dict[str, Any]]) -> None:
    content = material.get("content", "")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except ValueError:
            content = {"text": content, "styles": []}
    if not isinstance(content, dict) or not isinstance(content.get("text"), str):
        raise ValueError(f"{source_path} 文本 content 必须包含 text")
    styles = content.get("styles") or []
    if not isinstance(styles, list) or any(not isinstance(style, dict) for style in styles):
        raise ValueError(f"{source_path} 文本 styles 必须为对象数组")
    first = styles[0] if styles else {}
    fill = first.get("fill", {})
    for name in ("content", "solid"):
        if not isinstance(fill, dict):
            raise ValueError(f"{source_path} 文本 fill 必须为嵌套对象")
        fill = fill.get(name, {})
    if not isinstance(fill, dict):
        raise ValueError(f"{source_path} 文本 solid 必须为对象")
    color = fill.get("color", [1, 1, 1])
    if not isinstance(color, list) or len(color) != 3:
        raise ValueError(f"{source_path} 文本颜色必须为 RGB 三元组")
    rgb = [round(_number(channel, source_path, minimum=0, maximum=1)*255) for channel in color]
    alpha = _number(material.get("global_alpha", 1), source_path, minimum=0, maximum=1)
    style = {"fontsize": max(1, round(_number(first.get("size", 8), source_path, minimum=0.000001)*height/100)), "fontcolor": "#"+"".join(f"{channel:02x}" for channel in rgb)+f"@{alpha:.6f}", "x": "(w-text_w)/2", "y": "(h-text_h)/2", "text_align": {0:"left", 1:"center", 2:"right"}.get(material.get("alignment", 1), "center"), "box": False}
    clip["generator"] = {"type": "text"}
    clip["subtitle"] = {"text": content["text"], "style": style}
    _item(items, "text", "Mapped", source_path, clip["id"], "文字内容、颜色、对齐和独立时间范围已映射")
    _item(items, "text-layout", "Approximate", source_path, clip["id"], "字号按画布高度百分比映射；富文本/字距/描边/阴影/竖排的商业排版未等效验收", preserved_source=material)
    for index, source_style in enumerate(styles):
        font = source_style.get("font")
        if font:
            if not isinstance(font, dict):
                raise ValueError(f"{source_path}.font 必须为对象")
            path = _path(font["path"], source.parent, f"{source_path}.font.path") if font.get("path") else None
            if index == 0 and path and path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                key = os.path.normcase(str(path))
                asset = font_assets.get(key)
                if asset is None:
                    import shutil

                    identity = new_id("font")
                    relative = f"assets/{identity}_{safe_filename(path.name)}"
                    shutil.copy2(path, root/relative)
                    digest = f"sha256:{sha256_file(root/relative)}"
                    asset = {"id":identity,"kind":"font","uri":relative,"sha256":digest,"probe":{},"rights_ref":identity}
                    project["assets"].append(asset)
                    add_record(ledger,{"asset_id":identity,"kind":"font","sha256":digest,"source_url":f"local://{path}","license_spdx":"LicenseRef-UNVERIFIED","permitted_uses":["internal"],"verification_status":"unverified","takedown_status":"clear","evidence":"","notes":"Imported local draft font; verify before publishing"})
                    font_assets[key] = asset
                style["font_asset_id"] = asset["id"]
                _item(items,"font","Mapped",f"{source_path}.styles[{index}].font",asset["id"],"本地字体复制与哈希登记；权利默认未核验")
            else:
                _item(items, "font", "Unsupported", f"{source_path}.styles[{index}].font", clip["id"], "字体缺失、仅资源 ID 或富文本局部字体尚未支持；未下载或自动授权", preserved_source=font)


def _extras(segment: dict[str, Any], clip: dict[str, Any], materials: dict[str, tuple[str, dict[str, Any]]], items: list[dict[str, Any]], source_path: str, used: set[str]) -> None:
    refs = segment.get("extra_material_refs", [])
    if not isinstance(refs, list):
        raise ValueError(f"{source_path}.extra_material_refs 必须为数组")
    for ref in refs:
        identity = str(ref)
        if identity not in materials:
            _item(items, "material-reference", "Failed", source_path, clip["id"], "附加素材 ID 不存在", preserved_source={"id": identity})
            continue
        used.add(identity)
        group, material = materials[identity]
        if group == "speeds" and not material.get("curve_speed"):
            _item(items, "constant-speed", "Mapped", source_path, clip["id"], "使用片段源/目标范围及固定速度")
        elif group == "audio_fades":
            for source_key, target_key in (("fade_in_duration", "fade_in"), ("fade_out_duration", "fade_out")):
                microseconds = _integer(material.get(source_key, 0), source_key)
                if microseconds > _us(clip["duration_tick"], TICKS_PER_SECOND):
                    raise ValueError(f"{source_path} 音频淡入/淡出超过片段时长")
                clip["audio"][target_key] = microseconds/MICROSECONDS
            _item(items, "audio-fade", "Mapped", source_path, clip["id"], "引用音频淡入淡出映射为秒")
        else:
            _item(items, group, "Unsupported", source_path, clip["id"], "私有效果/转场/动画/曲线速度未执行，保留源参数供后续映射或本地烘焙", preserved_source=material)
    if segment.get("keyframe_refs"):
        _item(items, "keyframe-refs", "Unsupported", source_path, clip["id"], "外部关键帧引用尚未展开", preserved_source=segment["keyframe_refs"])
    if segment.get("is_tone_modify"):
        _item(items, "audio-pitch-speed", "Approximate", source_path, clip["id"], "变速跟随音调标记未映射，本地使用保调变速")


def import_draft(source: Path, destination: Path, payload: dict[str, Any], asset_loader: Callable, *, strict: bool = False) -> dict[str, Any]:
    if not is_draft(payload):
        raise ValueError("不是受支持的明文草稿 JSON")
    canvas = payload["canvas_config"]
    width = _integer(canvas.get("width"), "canvas_config.width", minimum=1)
    height = _integer(canvas.get("height"), "canvas_config.height", minimum=1)
    if max(width, height) > 8192:
        raise ValueError("草稿画布不能超过 8192 像素")
    fps = Fraction(str(_number(payload.get("fps", 30), "fps", minimum=1, maximum=240))).limit_denominator(100_000)
    declared_duration = _tick(payload.get("duration", 0), "duration")
    materials = _material_index(payload, source)
    config = payload.get("config") or {}
    if not isinstance(config, dict) or not isinstance(config.get("video_mute", False), bool):
        raise ValueError("草稿 config 必须为对象，video_mute 必须为布尔值")
    if not isinstance(payload.get("keyframes", {}), dict):
        raise ValueError("草稿顶层 keyframes 必须为对象")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("转换输出目录必须不存在或为空")
    items: list[dict[str, Any]] = []
    _item(items, "project-model", "Mapped", DRAFT_PROFILE, "agent-project/0.1.0", "仅处理本地明文数据；不启动商业运行时")
    _item(items, "timebase", "Mapped", "microseconds", "90000 ticks/second", "以有理数换算并四舍五入到最近 tick；最大误差半个 tick")
    if payload.get("version",360000) != 360000 or payload.get("new_version","110.0.0") != "110.0.0":
        _item(items,"draft-version","Approximate","version/new_version",DRAFT_PROFILE,"输入版本超出当前固定文件轮廓；仅按可识别字段转换，未验证该商业版本兼容性",preserved_source={"version":payload.get("version"),"new_version":payload.get("new_version")})
    if config.get("video_mute"):
        _item(items, "video-mute", "Mapped", "config.video_mute", detail="视频原声的派生音轨静音；画面仍保留")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".draft-import-", dir=str(destination.parent)) as temporary:
        root, project = create_project(Path(temporary)/"project", name=str(payload.get("name") or source.stem))
        ledger = initial_ledger()
        project["settings"]["canvas"].update({"width": width, "height": height})
        project["settings"]["timebase"]["display_fps"] = {"num": fps.numerator, "den": fps.denominator}
        sequence = project["sequences"][0]
        sequence.update({"tracks": [], "duration_tick": max(1, declared_duration)})
        asset_by_path: dict[str, dict[str, Any]] = {}
        font_assets: dict[str, dict[str, Any]] = {}
        used_materials: set[str] = set()
        track_ids: set[str] = set()
        clip_ids: set[str] = set()
        for track_index, raw_track in enumerate(payload["tracks"]):
            if not isinstance(raw_track, dict) or not isinstance(raw_track.get("segments", []), list):
                raise ValueError("草稿轨道必须为对象且 segments 为数组")
            source_track = f"tracks[{track_index}]"
            kind = str(raw_track.get("type", ""))
            if kind not in {"video", "audio", "text", "sticker"}:
                _item(items, "track", "Unsupported", source_track, detail=f"未映射轨道类型: {kind}", preserved_source=raw_track)
                continue
            track_id = _identifier(raw_track.get("id") or f"draft_track_{track_index}", "track", items)
            if track_id in track_ids:
                raise ValueError("草稿轨道 ID 重复")
            track_ids.add(track_id)
            mute = bool(_integer(raw_track.get("attribute", 0), source_track) & 1)
            track = {"id": track_id, "kind": "subtitle" if kind == "text" else "audio" if kind == "audio" else "video", "order": track_index, "muted": mute, "locked": False, "clips": []}
            sequence["tracks"].append(track)
            _item(items, "track", "Mapped", source_track, track_id, "轨道类型、静音与片段目标范围映射")
            for segment_index, segment in enumerate(raw_track.get("segments", [])):
                source_path = f"{source_track}.segments[{segment_index}]"
                if not isinstance(segment, dict):
                    raise ValueError(f"{source_path} 必须为对象")
                identity = str(segment.get("material_id", ""))
                if identity not in materials:
                    _item(items, "media-reference", "Failed", source_path, detail="片段素材 ID 不存在", preserved_source=segment)
                    continue
                used_materials.add(identity)
                group, material = materials[identity]
                target = segment.get("target_timerange")
                if not isinstance(target, dict):
                    raise ValueError(f"{source_path}.target_timerange 必须为对象")
                duration = _tick(target.get("duration"), source_path, positive=True)
                start = _tick(target.get("start", 0), source_path)
                render_order = _integer(segment.get("render_index", raw_track.get("render_index", 15000 if kind == "text" else track_index)), source_path)
                if not track["clips"]:
                    track["order"] = render_order
                elif track["order"] != render_order:
                    _item(items, "layer-order", "Approximate", source_path, track_id, "单轨混合 render_index 使用首片段层级", preserved_source={"render_index":render_order})
                sequence["duration_tick"] = max(sequence["duration_tick"], start+duration)
                clip_id = _identifier(segment.get("id") or f"draft_clip_{track_index}_{segment_index}", "clip", items)
                if clip_id in clip_ids:
                    raise ValueError("草稿片段 ID 重复")
                clip_ids.add(clip_id)
                if segment.get("visible") is False:
                    _item(items, "clip-visibility", "Mapped", source_path, detail="隐藏片段保留时间空隙并跳过渲染", preserved_source=segment)
                    continue
                clip = {"id": clip_id, "timeline_start_tick": start, "duration_tick": duration, "source_in_tick": 0, "source_out_tick": duration,
                        "audio": {"volume": _number(segment.get("volume", 1), source_path, minimum=0)}, "reverse": bool(segment.get("reverse", False))}
                if kind == "text" and group == "texts":
                    _text(material, height, clip, items, source_path, source, root, project, ledger, font_assets)
                elif group in MEDIA_GROUPS and track["kind"] != "subtitle":
                    raw_path = material.get("path") or material.get("media_path") or material.get("file_path")
                    if not raw_path:
                        _item(items, "media-reference", "Failed", source_path, clip_id, "素材只有资源 ID，没有可执行的本地文件；不会下载", preserved_source=material)
                        continue
                    path = _path(raw_path, source.parent, source_path)
                    if not path.is_file():
                        _item(items, "media-reference", "Failed", source_path, clip_id, "本地素材缺失", preserved_source={"path":str(path)})
                        continue
                    path_key = os.path.normcase(str(path))
                    if path_key not in asset_by_path:
                        asset, rights = asset_loader(path, root)
                        project["assets"].append(asset)
                        add_record(ledger, rights)
                        asset_by_path[path_key] = asset
                    asset = asset_by_path[path_key]
                    if track["kind"] == "audio" and not asset["probe"].get("audio", {}).get("codec"):
                        _item(items, "audio-stream", "Failed", source_path, clip_id, "音频轨道素材没有音频流")
                        continue
                    if track["kind"] == "video" and asset["kind"] not in {"video", "image"}:
                        _item(items, "video-stream", "Failed", source_path, clip_id, "画面轨道素材没有视频/图像流")
                        continue
                    clip["asset_id"] = asset["id"]
                    speed = _number(segment.get("speed", 1), source_path, minimum=0.000001)
                    source_range = segment.get("source_timerange") or {"start":0, "duration":round(target["duration"]*speed)}
                    if not isinstance(source_range, dict):
                        raise ValueError(f"{source_path}.source_timerange 必须为对象或 null")
                    source_start = _tick(source_range.get("start", 0), source_path)
                    source_end = _tick(_integer(source_range.get("start", 0), source_path)+_integer(source_range.get("duration"), source_path, minimum=1), source_path, positive=True)
                    if source_end <= source_start:
                        raise ValueError(f"{source_path} 源范围短于一个 tick")
                    clip.update({"source_in_tick": source_start, "source_out_tick": source_end, "speed": (source_end-source_start)/duration})
                    if abs(clip["speed"]-speed) > max(1e-4, speed*1e-4):
                        _item(items, "speed", "Approximate", source_path, clip_id, "speed 与源/目标范围冲突；以明确范围比率为准", preserved_source={"speed":speed})
                    _item(items, "media-reference", "Mapped", source_path, clip_id, "本地素材复制、探测、哈希登记；发布权利默认未核验")
                else:
                    _item(items, "material", "Unsupported", source_path, clip_id, "轨道与素材类型不匹配", preserved_source=material)
                    continue
                if track["kind"] != "audio":
                    _map_visual(segment, material, clip, items, source_path)
                _map_keyframes(segment, clip, items, source_path)
                _extras(segment, clip, materials, items, source_path, used_materials)
                track["clips"].append(clip)
                # Draft video segments contain sound. The Agent renderer has
                # explicit audio tracks, so preserve that sound as a linked
                # audio clip rather than silently dropping or double-mixing it.
                asset = next((asset for asset in project["assets"] if asset["id"] == clip.get("asset_id")), None)
                volume_frames = [point for frame in clip.get("keyframes", []) if frame["property"] == "audio.volume" for point in frame["keyframes"]]
                audible_original = clip["audio"]["volume"] > 0 or any(point["value"] > 0 for point in volume_frames)
                if track["kind"] == "video" and asset and asset["probe"].get("audio", {}).get("codec") and audible_original:
                    linked_id = _identifier(f"{clip_id[:100]}.draft-audio", "audio", items)
                    if linked_id in clip_ids:
                        raise ValueError("草稿派生音频 ID 与片段冲突")
                    clip_ids.add(linked_id)
                    audio_clip = {key: copy.deepcopy(value) for key, value in clip.items() if key in {"asset_id", "timeline_start_tick", "duration_tick", "source_in_tick", "source_out_tick", "speed", "reverse", "audio"}}
                    audio_clip.update({"id": linked_id, "keyframes": [copy.deepcopy(frame) for frame in clip.get("keyframes", []) if frame["property"].startswith("audio.")], "extensions": {"draft_embedded_audio_for": clip_id}})
                    audio_track_id = f"{track_id[:105]}.draft-audio"
                    audio_track = next((entry for entry in sequence["tracks"] if entry["id"] == audio_track_id), None)
                    if audio_track is None:
                        if audio_track_id in track_ids:
                            raise ValueError("草稿派生音轨 ID 冲突")
                        track_ids.add(audio_track_id)
                        audio_track = {"id":audio_track_id, "kind":"audio", "order":track["order"], "muted":mute or bool(config.get("video_mute")), "locked":False, "clips":[]}
                        sequence["tracks"].append(audio_track)
                    audio_track["clips"].append(audio_clip)
                    _item(items, "embedded-audio", "Mapped", source_path, linked_id, "视频原声转换为显式关联音轨")
        for track in sequence['tracks']:
            end = -1; overlaps = []
            for clip in sorted(track['clips'], key=lambda c:c['timeline_start_tick']):
                if clip['timeline_start_tick'] < end: overlaps.append(clip['id'])
                end = max(end, clip['timeline_start_tick'] + clip['duration_tick'])
            if overlaps:
                track['overlap_policy'] = 'allow'
                _item(items, 'timeline-overlap', 'Approximate', track['id'], track['id'],
                    '保留原片段目标区间及输入叠放/混音顺序；显式允许重叠，未重建私有转场或推断剪口',
                    preserved_source={'overlapping_clip_ids':overlaps})
        for identity, (group, material) in materials.items():
            if identity not in used_materials and group not in MEDIA_GROUPS | {"texts", "speeds"}:
                _item(items, "unused-material", "Unsupported", f"materials.{group}", detail="未消费的附加/全局素材保留供复核", preserved_source=material)
        if any(payload.get("keyframes", {}).values()):
            _item(items, "global-keyframes", "Unsupported", "keyframes", detail="顶层关键帧尚未映射", preserved_source=payload["keyframes"])
        _strict_gate(items, strict)
        validation = validate_project(root, project)
        if not validation["ok"]:
            raise AppError("CONVERSION_PROJECT_INVALID", "草稿映射结果未通过项目校验，目标未写入", exit_code=2, cause=json.dumps(validation["errors"], ensure_ascii=False))
        report = _report(source, "import", items, strict=strict, source_version=payload.get("new_version") or payload.get("version"))
        report["preserved_source"] = "validation/source-draft.json"
        project["provenance"]["change_log"].append({"command":"convert.import", "source_format":DRAFT_FORMAT, "profile":DRAFT_PROFILE, "adapter_version":ADAPTER_VERSION, "source_sha256":report["source_sha256"], "at":now_iso()})
        save_project(root, project)
        save_ledger(root, ledger)
        report_path = root/"validation"/"draft-conversion-report.json"
        atomic_write_json(report_path, report)
        atomic_write_json(root/"validation"/"source-draft.json", _preserve(payload))
        was_empty = destination.exists()
        if was_empty:
            destination.rmdir()
        try:
            os.replace(root, destination)
        except OSError:
            if was_empty and not destination.exists():
                destination.mkdir()
            raise
    return {"root":str(destination), "project":str(destination/"project.json"), "report":str(destination/"validation"/"draft-conversion-report.json"), "report_data":report, "validation":validation}


def _export_keyframes(clip: dict[str, Any], tps: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reverse_properties = {value:key for key, value in KEYFRAME_PROPERTIES.items()}
    result = []
    for index, track in enumerate(clip.get("keyframes", [])):
        prop = str(track.get("property", ""))
        if prop not in reverse_properties:
            _item(items, "keyframes", "Unsupported", f"clips[{clip['id']}].keyframes[{index}]", detail="未建立外部属性映射", preserved_source=track)
            continue
        points = []
        for point in track.get("keyframes", []):
            value = _number(point.get("value"), prop)
            if prop == "transform.position.x":
                value = (value-0.5)*2
            elif prop == "transform.position.y":
                value = (0.5-value)*2
            interpolation = point.get("interpolation", "linear")
            controls = point.get("control_points", [0,0,1,1])
            if interpolation in {"ease_in", "ease_out", "ease_in_out"}:
                controls = {"ease_in":[0.42,0,1,1], "ease_out":[0,0,0.58,1], "ease_in_out":[0.42,0,0.58,1]}[interpolation]
            elif len(controls) == 2:
                controls = [1/3,controls[0],2/3,controls[1]]
            curve = "Line" if interpolation == "linear" else "Bezier"
            if interpolation == "hold":
                curve = "Line"
                _item(items, "keyframe-interpolation", "Approximate", clip["id"], detail="hold 关键帧回退线性", preserved_source=point)
            elif curve == "Bezier":
                _item(items, "keyframe-interpolation", "Approximate", clip["id"], detail="Bezier 商业运行时语义未验收", preserved_source=point)
            points.append({"id":f"kf_{len(result)}_{len(points)}", "time_offset":_us(point["at_tick"],tps), "values":[value], "curveType":curve, "graphID":"", "left_control":{"x":controls[0],"y":controls[1]}, "right_control":{"x":controls[2],"y":controls[3]}})
        if points:
            result.append({"id":f"keyframes_{clip['id']}_{index}","property_type":reverse_properties[prop],"material_id":"","keyframe_list":points})
    return result


def _export_text(root: Path, clip: dict[str, Any], assets: dict[str, dict[str, Any]], canvas: dict[str, Any], material_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    subtitle = clip["subtitle"]
    style = subtitle.get("style") or {}
    token, _, opacity = str(style.get("fontcolor", "white")).strip().rpartition("@")
    if not token:
        token, opacity = str(style.get("fontcolor", "white")), "1"
    names = {"white":"ffffff", "black":"000000", "red":"ff0000", "green":"008000", "blue":"0000ff", "yellow":"ffff00", "cyan":"00ffff", "magenta":"ff00ff", "orange":"ffa500", "gray":"808080", "grey":"808080", "transparent":"00000000"}
    hex_color = names.get(token.lower(), token.removeprefix("#").removeprefix("0x"))
    alpha = _number(float(opacity), "fontcolor alpha", minimum=0, maximum=1)
    if re.fullmatch(r"[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", hex_color):
        rgb = [int(hex_color[index:index+2], 16)/255 for index in (0, 2, 4)]
        if len(hex_color) == 8:
            alpha *= int(hex_color[6:], 16)/255
    else:
        rgb = [1, 1, 1]
        _item(items, "text-color", "Unsupported", clip["id"], detail="当前适配器只映射 RGB 十六进制和基础命名颜色；其余保存在旁车", preserved_source={"fontcolor":style.get("fontcolor")})
    target_style = {"range":[0,len(str(subtitle["text"]))], "size":float(style.get("fontsize",52))/canvas["height"]*100, "fill":{"content":{"solid":{"color":rgb}}}}
    font_id = style.get("font_asset_id")
    if font_id:
        asset = assets.get(font_id)
        if not asset or asset.get("kind") != "font":
            raise ValueError("字幕 font_asset_id 未引用已登记字体")
        path = _path(asset["uri"],root,"font.uri")
        if not path.is_file() or sha256_file(path) != str(asset.get("sha256", "")).removeprefix("sha256:"):
            raise AppError("CONVERSION_ASSET_HASH_MISMATCH", "字体缺失或与登记哈希不一致，目标未写入", exit_code=2, path=str(path))
        target_style["font"] = {"id":font_id, "path":str(path)}
        _item(items,"font","Mapped",font_id,material_id,"本地字体路径与哈希已核验；权利状态不自动提升")
    content = {"text":str(subtitle["text"]), "styles":[target_style]}
    _item(items,"text-layout","Approximate",clip["id"],material_id,"文本、字号、RGB/alpha、对齐和本地字体可编辑；字距、描边、阴影、换行、局部样式与商业排版需独立验收",preserved_source=subtitle)
    return {"id":material_id, "type":"text", "content":json.dumps(content,ensure_ascii=False), "alignment":{"left":0,"center":1,"right":2}.get(style.get("text_align"),1), "global_alpha":alpha}


def _export_crop(clip: dict[str, Any], material: dict[str, Any], items: list[dict[str, Any]]) -> None:
    crop = clip.get("crop")
    if not crop:
        return
    if str(crop.get("fit",crop.get("mode","fit"))).lower() != "fit":
        _item(items,"crop-fit","Unsupported",clip["id"],detail="外部画幅填充/拉伸未建立等效映射；保留默认 fit",preserved_source=crop)
    normalized = str(crop.get("unit","pixels")).lower() in {"normalized","relative"}
    width, height = float(material["width"]), float(material["height"])
    x = float(crop.get("x",0))/(1 if normalized else width)
    y = float(crop.get("y",0))/(1 if normalized else height)
    w = float(crop.get("width",crop.get("w",1 if normalized else width)))/(1 if normalized else width)
    h = float(crop.get("height",crop.get("h",1 if normalized else height)))/(1 if normalized else height)
    clamped_w, clamped_h = min(1,w), min(1,h)
    clamped_x, clamped_y = min(max(0,x),1-clamped_w), min(max(0,y),1-clamped_h)
    if (x,y,w,h) != (clamped_x,clamped_y,clamped_w,clamped_h):
        _item(items,"crop-bounds","Approximate",clip["id"],detail="越界裁切按本地渲染规则钳制到素材范围",preserved_source=crop)
    x0,y0,x1,y1 = clamped_x,clamped_y,clamped_x+clamped_w,clamped_y+clamped_h
    material["crop"] = {"upper_left_x":x0,"upper_left_y":y0,"upper_right_x":x1,"upper_right_y":y0,"lower_left_x":x0,"lower_left_y":y1,"lower_right_x":x1,"lower_right_y":y1}
    _item(items,"crop","Mapped",clip["id"],material["id"],"静态像素/归一化矩形映射为四角；动态裁切关键帧仍单独报告")


def export_draft(root: Path, project: dict[str, Any], output: Path, *, strict: bool = False) -> dict[str, Any]:
    original_project = project
    items: list[dict[str, Any]] = []
    protected = {(root/name).resolve() for name in ("project.json","rights-ledger.json","project.lock.json")}
    for asset in project.get("assets", []):
        protected.add(_path(asset["uri"], root, "asset.uri"))
    if any(path.resolve() in protected for path in (output, output.with_suffix(output.suffix+".conversion-report.json"), output.with_suffix(output.suffix+".source-agent.json"))):
        raise ValueError("草稿输出及旁车不能覆盖源项目文件或已登记素材")
    validation = validate_project(root, project)
    if not validation["ok"]:
        raise AppError("CONVERSION_PROJECT_INVALID", "源项目校验失败，拒绝生成草稿", exit_code=2, cause=json.dumps(validation["errors"], ensure_ascii=False))
    from .bindings import bake_interchange_bindings
    bake_receipt = {}
    project,bound_clips = bake_interchange_bindings(project, root, receipt=bake_receipt)
    for clip_id in bound_clips:
        _item(items,'tracking-binding','Baked',clip_id,detail='按当前画布和源片段重算为普通关键帧；外部工程不保留活动绑定，完整源保存在旁车')
    tps = int(project["settings"]["timebase"]["ticks_per_second"])
    fps = project["settings"]["timebase"]["display_fps"]
    sequence = project["sequences"][0]
    canvas = {**project['settings']['canvas'], **sequence_canvas(project, sequence)}
    materials: dict[str, list[dict[str, Any]]] = {group:[] for group in ("videos","audios","texts","speeds","audio_fades","effects","transitions","stickers","images")}
    tracks = []
    assets = {asset["id"]:asset for asset in project["assets"]}
    clips_by_id = {clip["id"]:clip for track in sequence["tracks"] for clip in track["clips"] if track["kind"] == "video"}
    video_tracks = {clip["id"]:track for track in sequence["tracks"] if track["kind"] == "video" for clip in track["clips"]}
    foldable: dict[str, str] = {}
    for track in sequence["tracks"]:
        if track["kind"] != "audio" or track.get("audio"):
            continue
        for clip in track["clips"]:
            linked = clip.get("extensions",{}).get("draft_embedded_audio_for")
            if linked not in clips_by_id or bool(track.get("muted")) != bool(video_tracks[linked].get("muted")):
                continue
            video = clips_by_id[linked]
            fields = ("asset_id","timeline_start_tick","duration_tick","source_in_tick","source_out_tick","speed","reverse","audio")
            audio_frames = [frame for frame in video.get("keyframes",[]) if str(frame.get("property","")).startswith("audio.")]
            if all(clip.get(field) == video.get(field) for field in fields) and clip.get("keyframes",[]) == audio_frames and linked not in foldable.values():
                foldable[clip["id"]] = linked
    _item(items, "project-model", "Mapped", "agent-project/0.1.0", DRAFT_PROFILE, "本地明文文件；商业版本可打开性与视觉结果需独立验收")
    if project['settings'].get('sequence_sampling') is not None:
        _item(items, 'sequence-sampling', 'Unsupported', 'settings.sequence_sampling',
              detail='外部草稿不执行本地序列面积核或工作配额；原值只保存在旁车',
              preserved_source=project['settings']['sequence_sampling'])
    from .edit_planner import interchange_features
    for field in interchange_features(project):
        _item(items, 'timeline-editing', 'Unsupported', field,
              detail='外部草稿不执行本地命名音频路由、关联/同步锁/主轨跟随、真实源句柄转场或文件字幕时钟偏移；原生配置只在旁车保留')
    if str(canvas.get("background","black")).lower() not in {"black","#000000","0x000000"}:
        _item(items,"canvas-background","Unsupported","settings.canvas.background",detail="非黑色或透明画布尚未映射到外部草稿；源值保存在旁车",preserved_source=canvas.get("background"))
    if len(project["sequences"]) > 1:
        _item(items,"sequences","Unsupported","sequences",detail="仅导出第一条序列；其他序列与嵌套结构保存在旁车",preserved_source=project["sequences"][1:])
    if project["settings"].get("adjustments"):
        _item(items,"adjustments","Unsupported","settings.adjustments",detail="调节层未映射",preserved_source=project["settings"]["adjustments"])
    if sequence.get("markers"):
        _item(items,"markers","Unsupported","markers",detail="标记保存在旁车，未映射到外部 time_marks",preserved_source=sequence["markers"])
    for track in sorted(sequence["tracks"], key=lambda entry:entry["order"]):
        if track["kind"] not in {"video","audio","subtitle"}:
            _item(items,"track","Unsupported",track["id"],detail="数据轨道未映射",preserved_source=track)
            continue
        target_track = {"id":track["id"],"type":{"video":"video","audio":"audio","subtitle":"text"}[track["kind"]],"name":track.get("name",track["id"]),"attribute":int(bool(track.get("muted"))),"flag":0,"is_default_name":False,"segments":[]}
        for clip in track["clips"]:
            if clip["id"] in foldable:
                _item(items,"embedded-audio","Mapped",clip["id"],foldable[clip["id"]],"未修改的派生原声合并回视频片段，避免双重混音")
                continue
            if clip.get("sequence_id"):
                _item(items,"nested-sequence","Unsupported",clip["id"],detail="嵌套序列需要显式本地烘焙",preserved_source=clip)
                continue
            if track["kind"] == "subtitle" and clip.get("subtitle",{}).get("text") is None:
                _item(items,"subtitle-asset","Unsupported",clip["id"],detail="外部字幕资产尚未展开为草稿文字片段；源字幕引用保存在旁车",preserved_source=clip)
                continue
            if track["kind"] != "subtitle" and clip.get("subtitle"):
                _item(items,"embedded-subtitle","Unsupported",clip["id"],detail="视频内嵌字幕尚未拆成草稿文字轨道；源值保存在旁车",preserved_source=clip["subtitle"])
            if track["kind"] == "subtitle" and clip.get("crop"):
                _item(items,"text-crop","Unsupported",clip["id"],detail="文字画布裁切未建立映射；源值保存在旁车",preserved_source=clip["crop"])
            segment = {"id":clip["id"],"material_id":f"material_{clip['id']}","target_timerange":{"start":_us(clip["timeline_start_tick"],tps),"duration":max(1,_us(clip["duration_tick"],tps))},"source_timerange":{"start":_us(clip["source_in_tick"],tps),"duration":max(1,_us(clip["source_out_tick"]-clip["source_in_tick"],tps))},"reverse":bool(clip.get("reverse",False)),"speed":float(clip.get("speed",1)),"volume":float(clip.get("audio",{}).get("volume",1)),"visible":True,"render_index":track["order"],"track_render_index":track["order"],"track_attribute":0,"common_keyframes":_export_keyframes(clip,tps,items),"keyframe_refs":[],"extra_material_refs":[],"is_tone_modify":False}
            transform = clip.get("transform") or {}
            position = transform.get("position") or {}
            anchor = transform.get("anchor") or {}
            if float(anchor.get("x",transform.get("anchor_x",0.5))) != 0.5 or float(anchor.get("y",transform.get("anchor_y",0.5))) != 0.5:
                _item(items,"transform-anchor","Unsupported",clip["id"],detail="外部草稿锚点未建立映射；中心锚点回退会影响放置和旋转，原值保存在旁车",preserved_source=transform)
            segment["clip"] = None if track["kind"] == "audio" else {"alpha":transform.get("opacity",1),"rotation":transform.get("rotation",0),"scale":{"x":transform.get("scale",1),"y":transform.get("scale",1)},"transform":{"x":(position.get("x",0.5)-0.5)*2,"y":(0.5-position.get("y",0.5))*2},"flip":{"horizontal":False,"vertical":False}}
            if track["kind"] == "subtitle" and clip.get("subtitle",{}).get("text") is not None:
                materials["texts"].append(_export_text(root,clip,assets,canvas,segment["material_id"],items))
                segment["source_timerange"] = None
            else:
                asset = assets.get(clip.get("asset_id"))
                if asset is None:
                    _item(items,"media-reference","Failed",clip["id"],detail="缺少可映射的本地媒体资产")
                    continue
                path = _path(asset["uri"],root,f"assets[{asset['id']}].uri")
                if not path.is_file():
                    _item(items,"media-reference","Failed",clip["id"],detail="源媒体缺失")
                    continue
                if sha256_file(path) != str(asset.get("sha256","")).removeprefix("sha256:"):
                    raise AppError("CONVERSION_ASSET_HASH_MISMATCH","源媒体与登记哈希不一致，目标未写入",exit_code=2,path=str(path))
                material = {"id":segment["material_id"],"path":str(path),"duration":_us(asset.get("probe",{}).get("duration_tick",0),TICKS_PER_SECOND),"local_material_id":asset["id"],"material_name":path.name,"source_platform":0}
                if track["kind"] == "audio":
                    material.update({"type":"extract_music","name":path.name,"music_id":material["id"]})
                    materials["audios"].append(material)
                    if asset["kind"] == "video":
                        _item(items,"audio-container","Approximate",clip["id"],detail="音轨引用视频容器；本地适配器可读，商业草稿可能要求先提取 WAV")
                else:
                    material.update({"type":"photo" if asset["kind"]=="image" else "video","width":asset["probe"]["video"].get("width",canvas["width"]),"height":asset["probe"]["video"].get("height",canvas["height"]),"crop":{"upper_left_x":0,"upper_left_y":0,"upper_right_x":1,"upper_right_y":0,"lower_left_x":0,"lower_left_y":1,"lower_right_x":1,"lower_right_y":1}})
                    _export_crop(clip,material,items)
                    materials["videos"].append(material)
                    if asset["probe"].get("audio",{}).get("codec") and clip["id"] not in foldable.values():
                        # Agent video tracks carry no implicit sound. Do not
                        # introduce an extra soundtrack on external import.
                        segment["volume"] = 0
                        segment["common_keyframes"] = [frame for frame in segment["common_keyframes"] if frame["property_type"]!="KFTypeVolume"]
                _item(items,"media-reference","Mapped",clip["id"],material["id"],"本地绝对路径与素材哈希已核验；未复制媒体，跨机器请使用 Agent 项目包")
            for field in ("speed_curve","freeze","mask","blend","transition_in","transition_out"):
                if clip.get(field):
                    _item(items,field,"Unsupported",clip["id"],detail="外部字段未建立等效映射；完整参数保存在旁车",preserved_source=clip[field])
            if track["kind"] != "subtitle":
                speed_id = f"speed_{clip['id']}"
                materials["speeds"].append({"id":speed_id,"type":"speed","mode":0,"speed":segment["speed"],"curve_speed":None})
                segment["extra_material_refs"].append(speed_id)
            for effect in clip.get("effects",[]):
                name = effect if isinstance(effect,str) else effect.get("type","")
                if name in {"hflip","vflip"} and segment["clip"] is not None:
                    segment["clip"]["flip"]["horizontal" if name=="hflip" else "vertical"] = True
                else:
                    _item(items,"effect","Unsupported",clip["id"],detail="本地 FFmpeg 效果未映射为私有资源 ID",preserved_source=effect)
            audio = clip.get("audio") or {}
            if audio.get("fade_in") or audio.get("fade_out"):
                fade_id = f"fade_{clip['id']}"
                materials["audio_fades"].append({"id":fade_id,"type":"audio_fade","fade_in_duration":round(float(audio.get("fade_in",0))*MICROSECONDS),"fade_out_duration":round(float(audio.get("fade_out",0))*MICROSECONDS),"fade_type":0})
                segment["extra_material_refs"].append(fade_id)
            if set(audio)-{"volume","fade_in","fade_out"}:
                _item(items,"audio-processing","Unsupported",clip["id"],detail="额外音频处理保存在旁车",preserved_source=audio)
            target_track["segments"].append(segment)
        if target_track["segments"]:
            tracks.append(target_track)
        if track.get("audio"):
            _item(items,"audio-track-controls","Unsupported",track["id"],detail="轨道级音频参数未下推到外部片段",preserved_source=track["audio"])
    _strict_gate(items,strict)
    payload = {"id":project["project"]["id"],"name":project["project"]["name"],"version":360000,"new_version":"110.0.0","fps":fps["num"]/fps["den"],"duration":_us(sequence["duration_tick"],tps),"canvas_config":{"width":canvas["width"],"height":canvas["height"],"ratio":"original"},"materials":materials,"tracks":tracks,"keyframes":{},"config":{"maintrack_adsorb":False},"platform":{},"last_modified_platform":{},"agent_video_kit":{"profile":DRAFT_PROFILE,"adapter_version":ADAPTER_VERSION,"network":"disabled","source_sha256":f"sha256:{sha256_file(root/'project.json')}"}}
    report = _report(root/"project.json","export",items,strict=strict,source_version=project.get("schema_version"))
    report["runtime_compatibility_verified"] = False
    if bake_receipt: report['tracking_bake'] = bake_receipt
    report_path = output.with_suffix(output.suffix+".conversion-report.json")
    sidecar = output.with_suffix(output.suffix+".source-agent.json")
    report["preserved_source"] = sidecar.name
    # Build and check the full payload before publishing any output files.
    atomic_write_json(sidecar,_preserve(original_project))
    atomic_write_json(report_path,report)
    atomic_write_json(output,payload)
    return {"output":str(output),"report":str(report_path),"report_data":report,"source_sidecar":str(sidecar)}
