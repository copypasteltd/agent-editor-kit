"""Project-local registry for explicitly supplied offline model adapters.

The registry records paths and content hashes without downloading or copying
large model files.  Runtime commands must resolve an adapter through this
registry before they can claim model-backed behavior.  Unknown engines remain
registered metadata until a dedicated local runner is implemented.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import AppError, argument_error
from .policy import require_local_reference
from .tracking import (
    MULTI_OBJECT_TRACKING_ENGINE,
    MULTI_OBJECT_TRACKING_OUTPUT_CONTRACT,
    MULTI_OBJECT_TRACKING_PROTOCOL,
    OBJECT_TRACKING_ENGINE,
    OBJECT_TRACKING_OUTPUT_CONTRACT,
    OBJECT_TRACKING_PROTOCOL,
)
from .utils import atomic_write_json, assert_id, load_json, now_iso, sha256_bytes, sha256_file
from .local_vision import YOLO_ENGINE, prepare_adapter as prepare_native_vision, verify_adapter as verify_native_vision
from .local_separation import DEMUCS_ENGINE, prepare_adapter as prepare_native_separation, verify_adapter as verify_native_separation
from .stem_separation import ENGINE as FOUR_STEM_ENGINE, prepare_adapter as prepare_four_stem, verify_adapter as verify_four_stem
from .local_enhancement import ENGINE as ENHANCEMENT_ENGINE, prepare_adapter as prepare_enhancement, verify_adapter as verify_enhancement
from .local_matting import MATTING_ENGINE, prepare_adapter as prepare_native_matting, verify_adapter as verify_native_matting
from .local_segmentation import SEGMENTATION_ENGINE, prepare_adapter as prepare_native_segmentation, verify_adapter as verify_native_segmentation
from .local_inpainting import INPAINT_ENGINE, prepare_adapter as prepare_native_inpainting, verify_adapter as verify_native_inpainting
from .local_vace import VACE_ENGINE, prepare_adapter as prepare_native_vace, verify_adapter as verify_native_vace
from .local_lipsync import ENGINE as LIPSYNC_ENGINE, prepare_adapter as prepare_lipsync, verify_adapter as verify_lipsync
from .local_interpolation import ENGINE as INTERPOLATION_ENGINE, prepare_adapter as prepare_interpolation, verify_adapter as verify_interpolation
from .local_music_generation import ENGINE as MUSIC_GENERATION_ENGINE, verify_adapter as verify_music_generation


MODEL_REGISTRY_VERSION = "0.1.0"
MODEL_REGISTRY_RELATIVE = Path("models") / "audio-adapters.json"
VISUAL_MODEL_REGISTRY_RELATIVE = Path("models") / "visual-adapters.json"
VALID_AUDIO_ADAPTER_ENGINES = {
    MUSIC_GENERATION_ENGINE,
    ENHANCEMENT_ENGINE,
    FOUR_STEM_ENGINE,
    DEMUCS_ENGINE,
    "ffmpeg-local-mid-side-v1",
    "command-json-v1",
    "onnx-audio-separation-v1",
    "demucs-local-v1",
    "open-unmix-local-v1",
    "uvr-local-v1",
}
VALID_VISUAL_ADAPTER_ENGINES = {
    INTERPOLATION_ENGINE,
    LIPSYNC_ENGINE,
    VACE_ENGINE,
    INPAINT_ENGINE,
    SEGMENTATION_ENGINE,
    MATTING_ENGINE,
    OBJECT_TRACKING_ENGINE,
    MULTI_OBJECT_TRACKING_ENGINE,
    YOLO_ENGINE,
}


def registry_path(root: Path) -> Path:
    return root / MODEL_REGISTRY_RELATIVE


def visual_registry_path(root: Path) -> Path:
    return root / VISUAL_MODEL_REGISTRY_RELATIVE


def _hash_path(path: Path) -> tuple[str, str, int]:
    """Return a stable hash, kind and file count for a local model artifact."""
    if path.is_file():
        return f"sha256:{sha256_file(path)}", "file", 1
    if not path.is_dir():
        raise AppError("MODEL_PATH_MISSING", f"本地模型路径不存在: {path}", exit_code=10, path=str(path))
    entries: list[str] = []
    count = 0
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(path).as_posix()
        entries.append(f"{relative}\t{item.stat().st_size}\t{sha256_file(item)}\n")
        count += 1
    if not entries:
        raise AppError("MODEL_PATH_EMPTY", f"本地模型目录为空: {path}", exit_code=10, path=str(path))
    payload = "".join(entries).encode("utf-8")
    return f"sha256:{sha256_bytes(payload)}", "directory", count


def load_model_registry(root: Path) -> dict[str, Any]:
    path = registry_path(root)
    if not path.exists():
        return {"schema_version": MODEL_REGISTRY_VERSION, "updated_at": now_iso(), "adapters": []}
    value = load_json(path)
    if not isinstance(value, dict):
        raise AppError("MODEL_REGISTRY_INVALID", "本地音频适配器 registry 必须是对象", exit_code=2, path=str(path))
    value.setdefault("schema_version", MODEL_REGISTRY_VERSION)
    value.setdefault("adapters", [])
    if not isinstance(value["adapters"], list):
        raise AppError("MODEL_REGISTRY_INVALID", "本地音频适配器 registry 的 adapters 必须是数组", exit_code=2, path=str(path))
    return value


def save_model_registry(root: Path, registry: dict[str, Any]) -> None:
    registry["schema_version"] = MODEL_REGISTRY_VERSION
    registry["updated_at"] = now_iso()
    atomic_write_json(registry_path(root), registry)


def adapter_for(registry: dict[str, Any], adapter_id: str) -> dict[str, Any] | None:
    for item in registry.get("adapters", []):
        if isinstance(item, dict) and str(item.get("adapter_id")) == str(adapter_id):
            return item
    return None


def prepare_audio_adapter(
    *,
    adapter_id: str,
    engine: str,
    model_path: str | Path | None,
    executable: str | Path | None,
    creator: str,
    license_spdx: str,
    license_url: str,
    permitted_uses: list[str],
    verification_status: str,
    evidence: str,
    root: Path | None = None,
    native_options: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate local adapter inputs and return registry/rights records."""
    try:
        assert_id(str(adapter_id), "adapter_id")
    except AppError:
        raise
    engine = str(engine or "").strip()
    if engine == MUSIC_GENERATION_ENGINE:
        raise argument_error('神经音乐请使用music generator-adapter register，显式提供runtime-root', 'engine')
    if engine in {DEMUCS_ENGINE, FOUR_STEM_ENGINE, ENHANCEMENT_ENGINE}:
        prepare = {FOUR_STEM_ENGINE:prepare_four_stem,ENHANCEMENT_ENGINE:prepare_enhancement,DEMUCS_ENGINE:prepare_native_separation}[engine]
        return prepare(root or Path.cwd(),adapter_id=adapter_id,model_path=str(model_path or ''),executable=str(executable or ''),evidence=evidence,creator=creator,license_spdx=license_spdx,license_url=license_url,permitted_uses=permitted_uses,verification_status=verification_status,options=native_options)
    if engine not in VALID_AUDIO_ADAPTER_ENGINES:
        raise argument_error(f"不支持的本地音频适配器 engine: {engine}", "engine")
    if verification_status not in {"unverified", "verified", "restricted"}:
        raise argument_error("verification_status 不在允许范围内", "verification_status")
    if engine == "ffmpeg-local-mid-side-v1" and (model_path or executable):
        raise argument_error("内置 FFmpeg mid/side 适配器不接受 model_path 或 executable", "engine")
    model: Path | None = None
    model_hash = None
    model_kind = None
    model_file_count = 0
    if model_path:
        model_text = require_local_reference(model_path, field="--model-path")
        model = Path(model_text).expanduser().resolve()
        model_hash, model_kind, model_file_count = _hash_path(model)
    elif engine != "ffmpeg-local-mid-side-v1":
        raise argument_error("模型适配器必须提供 --model-path；只有内置 mid/side 可省略模型", "model_path")
    runner: Path | None = None
    runner_hash = None
    if executable:
        runner_text = require_local_reference(executable, field="--executable")
        runner = Path(runner_text).expanduser().resolve()
        if not runner.exists() or not runner.is_file():
            raise AppError("MODEL_EXECUTABLE_MISSING", f"本地适配器 executable 不存在: {runner}", exit_code=10, path=str(runner))
        if engine == "command-json-v1" and runner.suffix.lower() in {".cmd", ".bat"}:
            raise AppError("MODEL_EXECUTABLE_UNSAFE", "command-json-v1 不允许登记 .cmd/.bat shell wrapper", exit_code=10, path=str(runner))
        runner_hash = f"sha256:{sha256_file(runner)}"
    if engine == "command-json-v1" and runner is None:
        raise argument_error("command-json-v1 必须提供 --executable", "executable")
    stamp = now_iso()
    registry_record = {
        "adapter_id": str(adapter_id),
        "kind": "audio-separation",
        "engine": engine,
        "model_path": str(model) if model else None,
        "model_sha256": model_hash,
        "model_kind": model_kind,
        "model_file_count": model_file_count,
        "executable": str(runner) if runner else None,
        "executable_sha256": runner_hash,
        "output_contract": "center_side_wav_v1",
        "network": "disabled",
        "registered_at": stamp,
        "verification_status": verification_status,
    }
    rights_id = f"adapter:{adapter_id}"
    evidence_value = evidence or ("local://builtin/ffmpeg-mid-side" if engine == "ffmpeg-local-mid-side-v1" and verification_status != "unverified" else "")
    rights_record = {
        "asset_id": rights_id,
        "kind": "model-adapter",
        "sha256": model_hash or f"sha256:{sha256_bytes(engine.encode('utf-8'))}",
        "source_url": f"local://adapter/{adapter_id}",
        "source_version": engine,
        "retrieved_at": stamp,
        "creator": creator,
        "license_spdx": license_spdx,
        "license_url": license_url,
        "attribution": "",
        "permitted_uses": list(dict.fromkeys(permitted_uses)),
        "permitted_channels": [],
        "restrictions": [],
        "derived_from": [],
        "evidence": evidence_value,
        "verification_status": verification_status,
        "verified_by": "ai-ad-editor" if verification_status == "verified" else "",
        "takedown_status": "clear",
        "notes": "Explicitly registered local audio separation adapter; network disabled",
    }
    return registry_record, rights_record


def verify_audio_adapter(adapter: dict[str, Any]) -> dict[str, Any]:
    """Verify registered artifact existence and hashes without executing it."""
    if adapter.get('engine') == MUSIC_GENERATION_ENGINE:
        return verify_music_generation(adapter)
    if adapter.get('engine') == ENHANCEMENT_ENGINE:
        return verify_enhancement(adapter)
    if adapter.get('engine') == FOUR_STEM_ENGINE:
        return verify_four_stem(adapter)
    if adapter.get('engine') == DEMUCS_ENGINE:
        return verify_native_separation(adapter)
    findings: list[dict[str, Any]] = []
    model_path = adapter.get("model_path")
    if model_path:
        path = Path(str(model_path))
        if not path.exists():
            findings.append({"code": "MODEL_PATH_MISSING", "path": str(path)})
        else:
            try:
                actual, _, _ = _hash_path(path)
            except AppError as exc:
                findings.append({"code": exc.code, "path": str(path), "message": exc.message})
            else:
                if actual != adapter.get("model_sha256"):
                    findings.append({"code": "MODEL_HASH_MISMATCH", "path": str(path), "expected": adapter.get("model_sha256"), "actual": actual})
    executable = adapter.get("executable")
    if executable:
        path = Path(str(executable))
        if not path.exists() or not path.is_file():
            findings.append({"code": "MODEL_EXECUTABLE_MISSING", "path": str(path)})
        else:
            actual = f"sha256:{sha256_file(path)}"
            if actual != adapter.get("executable_sha256"):
                findings.append({"code": "MODEL_EXECUTABLE_HASH_MISMATCH", "path": str(path), "expected": adapter.get("executable_sha256"), "actual": actual})
    return {"adapter_id": adapter.get("adapter_id"), "engine": adapter.get("engine"), "network": adapter.get("network"), "ok": not findings, "findings": findings}


def load_visual_model_registry(root: Path) -> dict[str, Any]:
    path = visual_registry_path(root)
    if not path.exists():
        return {"schema_version": MODEL_REGISTRY_VERSION, "updated_at": now_iso(), "adapters": []}
    value = load_json(path)
    if not isinstance(value, dict):
        raise AppError("VISUAL_MODEL_REGISTRY_INVALID", "本地视觉适配器 registry 必须是对象", exit_code=2, path=str(path))
    value.setdefault("schema_version", MODEL_REGISTRY_VERSION)
    value.setdefault("adapters", [])
    if not isinstance(value["adapters"], list):
        raise AppError("VISUAL_MODEL_REGISTRY_INVALID", "本地视觉适配器 registry 的 adapters 必须是数组", exit_code=2, path=str(path))
    return value


def save_visual_model_registry(root: Path, registry: dict[str, Any]) -> None:
    registry["schema_version"] = MODEL_REGISTRY_VERSION
    registry["updated_at"] = now_iso()
    atomic_write_json(visual_registry_path(root), registry)


def visual_adapter_for(registry: dict[str, Any], adapter_id: str) -> dict[str, Any] | None:
    for item in registry.get("adapters", []):
        if isinstance(item, dict) and str(item.get("adapter_id")) == str(adapter_id):
            return item
    return None


def prepare_visual_adapter(
    *,
    adapter_id: str,
    engine: str,
    model_path: str | Path | None,
    executable: str | Path | None,
    creator: str,
    license_spdx: str,
    license_url: str,
    permitted_uses: list[str],
    verification_status: str,
    evidence: str,
    root: Path | None = None,
    native_options: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate and register an explicitly supplied offline visual runner."""
    assert_id(str(adapter_id), "adapter_id")
    engine = str(engine or "").strip()
    if engine == LIPSYNC_ENGINE:
        return prepare_lipsync(root or Path.cwd(), adapter_id=adapter_id, model_path=str(model_path or ''), executable=str(executable or ''), evidence=evidence, creator=creator, license_spdx=license_spdx, license_url=license_url, permitted_uses=permitted_uses, verification_status=verification_status, options=native_options or {})
    if engine == INTERPOLATION_ENGINE:
        return prepare_interpolation(root or Path.cwd(), adapter_id=adapter_id, model_path=str(model_path or ''), executable=str(executable or ''), evidence=evidence, creator=creator, license_spdx=license_spdx, license_url=license_url, permitted_uses=permitted_uses, verification_status=verification_status, options=native_options or {})
    if engine == VACE_ENGINE:
        return prepare_native_vace(root or Path.cwd(), adapter_id=adapter_id, model_path=str(model_path or ''), executable=str(executable or ''), evidence=evidence, creator=creator, license_spdx=license_spdx, license_url=license_url, permitted_uses=permitted_uses, verification_status=verification_status, options=native_options or {})
    if engine == INPAINT_ENGINE:
        return prepare_native_inpainting(root or Path.cwd(), adapter_id=adapter_id, model_path=str(model_path or ''), executable=str(executable or ''), evidence=evidence, creator=creator, license_spdx=license_spdx, license_url=license_url, permitted_uses=permitted_uses, verification_status=verification_status, options=native_options or {})
    if engine == SEGMENTATION_ENGINE:
        return prepare_native_segmentation(root or Path.cwd(), adapter_id=adapter_id, model_path=str(model_path or ''), executable=str(executable or ''), evidence=evidence, creator=creator, license_spdx=license_spdx, license_url=license_url, permitted_uses=permitted_uses, verification_status=verification_status, options=native_options or {})
    if engine == MATTING_ENGINE:
        return prepare_native_matting(root or Path.cwd(), adapter_id=adapter_id, model_path=str(model_path or ''), executable=str(executable or ''), evidence=evidence, creator=creator, license_spdx=license_spdx, license_url=license_url, permitted_uses=permitted_uses, verification_status=verification_status, options=native_options or {})
    if engine == YOLO_ENGINE:
        return prepare_native_vision(root or Path.cwd(), adapter_id=adapter_id, model_path=str(model_path or ''), executable=str(executable or ''), evidence=evidence, creator=creator, license_spdx=license_spdx, license_url=license_url, permitted_uses=permitted_uses, verification_status=verification_status, options=native_options or {})
    if engine not in VALID_VISUAL_ADAPTER_ENGINES:
        raise argument_error(f"不支持的本地视觉适配器 engine: {engine}", "engine")
    if verification_status not in {"unverified", "verified", "restricted"}:
        raise argument_error("verification_status 不在允许范围内", "verification_status")
    if not model_path:
        raise argument_error("视觉模型适配器必须提供 --model-path", "model_path")
    if not executable:
        raise argument_error("视觉模型适配器必须提供 --executable", "executable")
    model_text = require_local_reference(model_path, field="--model-path")
    model = Path(model_text).expanduser().resolve()
    model_hash, model_kind, model_file_count = _hash_path(model)
    runner_text = require_local_reference(executable, field="--executable")
    runner = Path(runner_text).expanduser().resolve()
    if not runner.exists() or not runner.is_file():
        raise AppError("MODEL_EXECUTABLE_MISSING", f"本地视觉适配器 executable 不存在: {runner}", exit_code=10, path=str(runner))
    if runner.suffix.lower() in {".cmd", ".bat", ".ps1", ".psm1", ".vbs", ".wsf", ".sh", ".bash", ".zsh"}:
        raise AppError("MODEL_EXECUTABLE_UNSAFE", "本地视觉 command-json runner 不允许 shell/script wrapper", exit_code=10, path=str(runner))
    runner_hash = f"sha256:{sha256_file(runner)}"
    stamp = now_iso()
    is_multi_object = engine == MULTI_OBJECT_TRACKING_ENGINE
    registry_record = {
        "adapter_id": str(adapter_id),
        "kind": "object-tracking",
        "engine": engine,
        "model_path": str(model),
        "model_sha256": model_hash,
        "model_kind": model_kind,
        "model_file_count": model_file_count,
        "executable": str(runner),
        "executable_sha256": runner_hash,
        "output_contract": MULTI_OBJECT_TRACKING_OUTPUT_CONTRACT if is_multi_object else OBJECT_TRACKING_OUTPUT_CONTRACT,
        "protocol": MULTI_OBJECT_TRACKING_PROTOCOL if is_multi_object else OBJECT_TRACKING_PROTOCOL,
        "capabilities": ["multi_object_bbox"] if is_multi_object else ["single_object_bbox"],
        "network": "disabled",
        "registered_at": stamp,
        "verification_status": verification_status,
    }
    rights_id = f"adapter:{adapter_id}"
    rights_record = {
        "asset_id": rights_id,
        "kind": "model-adapter",
        "sha256": model_hash,
        "source_url": f"local://adapter/{adapter_id}",
        "source_version": engine,
        "retrieved_at": stamp,
        "creator": creator,
        "license_spdx": license_spdx,
        "license_url": license_url,
        "attribution": "",
        "permitted_uses": list(dict.fromkeys(permitted_uses)),
        "permitted_channels": [],
        "restrictions": [],
        "derived_from": [],
        "evidence": evidence,
        "verification_status": verification_status,
        "verified_by": "ai-ad-editor" if verification_status == "verified" else "",
        "takedown_status": "clear",
        "notes": "Explicitly registered local object-tracking adapter; network disabled",
    }
    return registry_record, rights_record


def verify_visual_adapter(adapter: dict[str, Any]) -> dict[str, Any]:
    """Verify registered visual model and runner paths without executing them."""
    if adapter.get('engine') == LIPSYNC_ENGINE:
        return verify_lipsync(adapter)
    if adapter.get('engine') == INTERPOLATION_ENGINE:
        return verify_interpolation(adapter)
    if adapter.get('engine') == VACE_ENGINE:
        return verify_native_vace(adapter)
    if adapter.get('engine') == INPAINT_ENGINE:
        return verify_native_inpainting(adapter)
    if adapter.get('engine') == SEGMENTATION_ENGINE:
        return verify_native_segmentation(adapter)
    if adapter.get('engine') == MATTING_ENGINE:
        return verify_native_matting(adapter)
    if adapter.get('engine') == YOLO_ENGINE:
        return verify_native_vision(adapter)
    findings: list[dict[str, Any]] = []
    model_path = adapter.get("model_path")
    if not model_path:
        findings.append({"code": "MODEL_PATH_MISSING"})
    else:
        path = Path(str(model_path))
        if not path.exists():
            findings.append({"code": "MODEL_PATH_MISSING", "path": str(path)})
        else:
            try:
                actual, _, _ = _hash_path(path)
            except AppError as exc:
                findings.append({"code": exc.code, "path": str(path), "message": exc.message})
            else:
                if actual != adapter.get("model_sha256"):
                    findings.append({"code": "MODEL_HASH_MISMATCH", "path": str(path), "expected": adapter.get("model_sha256"), "actual": actual})
    executable = adapter.get("executable")
    if not executable:
        findings.append({"code": "MODEL_EXECUTABLE_MISSING"})
    else:
        path = Path(str(executable))
        if not path.exists() or not path.is_file():
            findings.append({"code": "MODEL_EXECUTABLE_MISSING", "path": str(path)})
        else:
            actual = f"sha256:{sha256_file(path)}"
            if actual != adapter.get("executable_sha256"):
                findings.append({"code": "MODEL_EXECUTABLE_HASH_MISMATCH", "path": str(path), "expected": adapter.get("executable_sha256"), "actual": actual})
    return {"adapter_id": adapter.get("adapter_id"), "engine": adapter.get("engine"), "network": adapter.get("network"), "ok": not findings, "findings": findings}
