"""Offline, attributable creative look presets; project copies stay portable."""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from typing import Any

from .errors import AppError, argument_error
from .lut_library import find_lut, load_lut_library, save_lut_library
from .policy import require_local_reference, resolve_local_path
from .project import find_sequence
from .rights import add_record, record_for
from .utils import atomic_write_json, ensure_inside, now_iso, sha256_file

DATA = Path(__file__).with_name("look_data")
MAX_CUBE_BYTES = 16 * 1024 * 1024
CATALOG_VERSION = "2.0.0"
LOOK_COUNT = 500
PRESET_MARKERS = {"avk-looks-1.0.0", "aek-looks-2.0.0"}


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resource(relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or any(p in {".", ".."} for p in path.parts) or "\\" in relative or ":" in relative:
        raise AppError("LOOK_CATALOG_INVALID", "非法预设资源路径", exit_code=2)
    result = (DATA / relative).resolve()
    if not result.is_relative_to(DATA.resolve()):
        raise AppError("LOOK_CATALOG_INVALID", "预设资源越界", exit_code=2)
    return result


def catalog() -> dict[str, Any]:
    try:
        value = json.loads((DATA / "catalog.json").read_bytes())
        rows = value["records"]
        if (value["version"] != CATALOG_VERSION or value["count"] != LOOK_COUNT
                or len(rows) != LOOK_COUNT or len({r["id"] for r in rows}) != LOOK_COUNT):
            raise ValueError("Expected 500 unique look IDs in catalog 2.0.0")
        return value
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AppError("LOOK_CATALOG_INVALID", "内置预设目录缺失或损坏", exit_code=2, cause=str(exc)) from exc


def list_looks(query: str = "", category: str | None = None) -> dict[str, Any]:
    value = catalog()
    query = query.casefold().strip()
    rows = [r for r in value["records"] if (not category or r["category"] == category)
            and (not query or query in json.dumps([r["id"], r["name"], r["name_zh"], r.get("name_zh_tw", ""),
                r["tags"], r.get("description_zh", ""), r.get("description_en", ""),
                r.get("suggested_use_zh", ""), r["license"]["spdx"]], ensure_ascii=False).casefold())]
    return {"catalog_version":value["version"], "total":value["count"], "count":len(rows), "looks":rows,
            "categories":sorted({r["category"] for r in value["records"]}),
            "license_counts":value["license_counts"],
            "color_contract":value["color_contract"], "network":"disabled"}


def get_look(look_id: str) -> dict[str, Any]:
    for row in catalog()["records"]:
        if row["id"] == look_id:
            return row
    raise AppError("LOOK_NOT_FOUND", f"找不到内置风格: {look_id}", exit_code=3, path="--id")


def _payload(row: dict[str, Any]) -> tuple[bytes, bytes]:
    try:
        packed = _resource(row["lut"]).read_bytes()
        if _hash(packed) != row["packed_sha256"]:
            raise ValueError("Packed LUT hash mismatch")
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as zipped:
            raw = zipped.read(MAX_CUBE_BYTES + 1)
        notice = _resource(row["license"]["file"]).read_bytes()
        if (len(raw) > MAX_CUBE_BYTES or len(raw) != row["bytes"] or _hash(raw) != row["sha256"]
                or _hash(notice) != row["license"]["sha256"]):
            raise ValueError("LUT or license hash mismatch")
        return raw, notice
    except (OSError, EOFError, ValueError) as exc:
        raise AppError("LOOK_RESOURCE_INVALID", "风格 LUT/许可资源损坏", exit_code=2, cause=str(exc)) from exc


def inspect_look(look_id: str) -> dict[str, Any]:
    row = get_look(look_id)
    _payload(row)
    preview = _resource(row["preview"])
    if not preview.is_file() or sha256_file(preview) != row["preview_sha256"]:
        raise AppError("LOOK_RESOURCE_INVALID", "风格缩略图损坏", exit_code=2)
    return {"look":row, "catalog_version":catalog()["version"], "verified":True,
            "preview_path":str(preview), "color_contract":catalog()["color_contract"], "network":"disabled"}


def strength_value(value: float) -> float:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise argument_error("风格强度必须为有限数值 0..1", "--strength")
    return value


def plan_apply(project: dict[str, Any], look_id: str, strength: float, *, clip_id: str | None,
               sequence_id: str = "seq_main", global_scope: bool = False, append: bool = False):
    row = get_look(look_id)
    strength_value(strength)
    _payload(row)  # No files are written by planning, including dry runs.
    candidate = copy.deepcopy(project)
    settings = candidate["settings"]
    if settings.get("pixel_pipeline") is not None:
        raise AppError("LOOK_COLOR_PIPELINE_UNSUPPORTED", "预设应用首版使用默认 SDR FFmpeg 管线；Float32 需显式色彩域配置", exit_code=2)
    if settings.get("color", {}).get("transfer", "bt709").lower() not in {"bt709", "srgb", "iec61966-2-1"}:
        raise AppError("LOOK_COLOR_PIPELINE_UNSUPPORTED", "请先将 Log/HDR 素材显式转换到 SDR 再应用创意预设", exit_code=2)
    lut_id = "look_" + row["id"]
    effect = {"id":"preset_"+row["id"], "type":"lut3d", "enabled":True,
              "parameters":{"lut_id":lut_id, "intensity":strength, "interpolation":"tetrahedral"},
              "source":{"look_catalog":"aek-looks-"+CATALOG_VERSION, "look_id":row["id"]}}
    if global_scope:
        owner = settings
        field = "adjustments"
        target = {"scope":"global"}
    else:
        sequence = find_sequence(candidate, sequence_id)
        match = [(t,c) for t in sequence.get("tracks", []) for c in t.get("clips", []) if c.get("id") == clip_id]
        if not match:
            raise argument_error("找不到目标片段", "--clip-id")
        track, owner = match[0]
        if track.get("locked") or owner.get("locked"):
            raise AppError("LOOK_TARGET_LOCKED", "目标片段或轨道已锁定", exit_code=2)
        if track.get("kind") != "video":
            raise argument_error("风格预设仅适用于视频轨道片段", "--clip-id")
        field = "effects"
        target = {"scope":"clip", "sequence_id":sequence_id, "clip_id":clip_id}
    effects = owner.get(field, [])
    if not isinstance(effects, list):
        raise argument_error("目标效果字段必须为数组", field)
    def is_preset(item):
        return isinstance(item, dict) and isinstance(item.get("source"), dict) and item["source"].get("look_catalog") in PRESET_MARKERS
    kept = effects[:] if append else [item for item in effects if not is_preset(item)]
    insertion = len(kept)
    if not append:
        first = next((i for i,item in enumerate(effects) if is_preset(item)), len(effects))
        insertion = len([item for item in effects[:first] if not is_preset(item)])
    # IDs stay unique when callers explicitly stack the same preset.
    effect["id"] += "_" + str(len(kept))
    owner[field] = kept[:insertion] + [effect] + kept[insertion:]
    return candidate, {"look_id":row["id"], "lut_id":lut_id, "strength":strength, "target":target,
                       "replaced_count":len(effects)-len(kept), "effect":effect}


def install_in_project(root: Path, look_id: str, ledger: dict[str, Any]) -> dict[str, Any]:
    row = get_look(look_id)
    raw, notice = _payload(row)
    lut_id = "look_"+look_id
    rel = f"assets/luts/{lut_id}.cube"
    evidence_rel = f"assets/look-evidence/{look_id}"
    provenance = {"look":row, "catalog_version":catalog()["version"], "license_notice":f"{evidence_rel}/LICENSE.txt",
                  "conversion":"Creative LUT. See source commit, SHA-256, grid size and normalization measurements above."}
    files = {rel:raw, f"{evidence_rel}/LICENSE.txt":notice,
             f"{evidence_rel}/provenance.json":(json.dumps(provenance, ensure_ascii=False, indent=2)+"\n").encode("utf-8")}
    existing = find_lut(root, lut_id)
    if existing and (existing["sha256"] != "sha256:"+row["sha256"] or existing["uri"] != rel):
        raise AppError("LOOK_PROJECT_CONFLICT", "项目已将预设 ID 绑定到其他 LUT", exit_code=2)
    for name, data in files.items():
        path = root / name
        ensure_inside(root, path)
        if path.exists() and (not path.is_file() or path.read_bytes() != data):
            if (name.endswith("/provenance.json") and path.is_file()
                    and _hash(path.read_bytes()) == row.get("legacy_provenance_sha256")):
                continue  # Preserve the exact released alpha.2 provenance bytes.
            raise AppError("LOOK_PROJECT_CONFLICT", "项目内预设/许可被修改；请保留并另建预设", exit_code=2, path=name)
    record = record_for(ledger, lut_id)
    if record and (record.get("sha256") != "sha256:"+row["sha256"] or record.get("verification_status") != "verified"
                   or record.get("takedown_status", "clear") != "clear"):
        raise AppError("LOOK_RIGHTS_CONFLICT", "既有预设权利记录与内置资源不匹配或受限制", exit_code=2)
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(data)
    if not existing:
        library = load_lut_library(root)
        library["records"].append({"id":lut_id, "name":row["name_zh"], "uri":rel, "sha256":"sha256:"+row["sha256"],
            "bytes":len(raw), "extension":".cube", "metadata":{"format":"cube", "lut_3d_size":row['grid_size'],
                "sample_count":row['grid_size']**3, "expected_samples":row['grid_size']**3, "sample_count_valid":True, "domain_min":[0,0,0], "domain_max":[1,1,1]},
            "registered_at":now_iso(), "source":{"original_name":row["source"]["path"], "source_url":"local://"+rel}})
        library["records"].sort(key=lambda r:r["id"])
        save_lut_library(root, library)
    if not record:
        record = add_record(ledger, {"asset_id":lut_id, "kind":"lut", "sha256":"sha256:"+row["sha256"],
            "source_url":"local://"+rel, "source_version":row["source"]["commit"], "retrieved_at":now_iso(),
            "creator":row["license"]["creator"], "license_spdx":row["license"]["spdx"], "license_url":f"{evidence_rel}/LICENSE.txt",
            "attribution":row["license"]["creator"]+"; "+row["license"]["spdx"]+"; source and changes in provenance", "permitted_uses":["internal","commercial_ad","redistribution"],
            "restrictions":row["license"].get("obligations", ["Retain source license notice"]), "evidence":f"{evidence_rel}/provenance.json",
            "verification_status":"verified", "verified_by":"bundled-open-look-hash-verification", "takedown_status":"clear",
            "notes":"Pinned source bytes and bundled license evidence verified. Apply the per-resource license, including attribution/share-alike where specified. Trademark names do not imply endorsement."})
    return {"lut_id":lut_id, "uri":rel, "sha256":row["sha256"], "rights":record, "evidence":evidence_rel}


def preview(look_id: str, output: str, *, input_path: str | None = None, strength: float = 1., dry_run: bool = False):
    row = get_look(look_id)
    strength_value(strength)
    raw, _ = _payload(row)
    target = resolve_local_path(Path.cwd(), output, field="--output")
    if target.suffix.lower() != ".png":
        raise argument_error("预览输出必须为 .png", "--output")
    if target.exists():
        raise AppError("OUTPUT_EXISTS", "预览输出已存在", exit_code=2, path=str(target))
    source = resolve_local_path(Path.cwd(), input_path, field="--input") if input_path else _resource("previews/reference.png")
    if not source.is_file():
        raise argument_error("预览输入不存在", "--input")
    result = {"look_id":look_id,"input":str(source),"output":str(target),"strength":strength,"network":"disabled"}
    if dry_run:
        return result
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AppError("DEPENDENCY_UNAVAILABLE", "缺少本地 FFmpeg", exit_code=4)
    from .lut_library import prepare_lut_intensity
    target.parent.mkdir(parents=True, exist_ok=True)
    # Temporary output is encoded before an exclusive final copy; existing files survive races.
    with tempfile.TemporaryDirectory(prefix="look-preview-") as tmp:
        temp = Path(tmp)
        cube = temp / "look.cube"
        cube.write_bytes(raw)
        if 0 < strength < 1:
            cube = prepare_lut_intensity(temp, cube, strength)
        # Run with a relative CUBE path: no filtergraph escaping of user-supplied paths.
        chain = "null" if strength == 0 else f"lut3d=file='{cube.relative_to(temp).as_posix()}':interp=tetrahedral"
        command = [ffmpeg, "-v", "error", "-nostdin", "-threads", "1", "-filter_threads", "1",
                   "-protocol_whitelist", "file,pipe", "-i", str(source),
                   "-vf", chain, "-frames:v", "1", "-update", "1", str(temp / "preview.png")]
        try:
            done = subprocess.run(command, capture_output=True, cwd=temp, timeout=90,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AppError("LOOK_PREVIEW_FAILED", "预览执行失败", exit_code=5, cause=str(exc)) from exc
        if done.returncode:
            raise AppError("LOOK_PREVIEW_FAILED", "FFmpeg 风格预览失败", exit_code=5, cause=done.stderr.decode("utf-8", "replace")[-2000:])
        try:
            with target.open("xb") as handle:
                handle.write((temp / "preview.png").read_bytes())
        except FileExistsError as exc:
            raise AppError("OUTPUT_EXISTS", "预览输出已存在", exit_code=2, path=str(target)) from exc
    result["sha256"] = sha256_file(target)
    result["warnings"] = ["Static partial strength interpolates the LUT with identity in encoded RGB."] if 0 < strength < 1 else []
    return result
