from __future__ import annotations

import json
import hashlib
import math
import os
import copy
import re
import threading
import subprocess
import time
from contextlib import ExitStack
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from .animation import bezier_samples
from .effect_automation import EffectAutomation, canonical as _runtime_effect_name
from .video_clock import registered_time_base, working_clock, frame_interval
from .audio_stretch import configuration as _audio_stretch_configuration, execute as _execute_audio_stretch, plan as _plan_audio_stretch
from .audio_tempo import (CONTEXT_FRAMES as _audio_context_frames,
                         MAX_TERMINAL_CONTEXT_PCM_BYTES as _audio_terminal_context_budget,
                         context_windows as _audio_context_windows)
from .artifact_locks import verification_scope
from .sequence_canvas import sequence_canvas, validate_output_alignment
from .sequence_sampling import configuration as _sequence_sampling_configuration, projection_budget, area_rectangle
from .source_transitions import compile_for_render as _compile_source_transitions
from .clip_windows import prepare as _prepare_clip_windows
from .inline_sequences import prepare as _prepare_inline_sequences, budget as _inline_sequence_budget

from .errors import AppError, dependency_error
from .hardware_acceleration import AccelerationSession, tag_output_frames
from .media import ffmpeg_path, probe_media
from .policy import resolve_local_path
from .project import asset_map
from .quality import check_output
from .text_layout import build_text_layout, graphemes, text_width, word_ranges
from .speed_curves import compile_curve
from .subtitle_clock import (
    authored_expression as _subtitle_authored_expression,
    clock_for_clip as _subtitle_clock_for_clip,
    make_clock as _make_subtitle_clock,
    restore_expression as _subtitle_restore_expression,
)
from .time_mapping import (
    audio_windows as _nested_audio_windows,
    compose_expression as _clock_expression,
    compose_time as _clock_time,
    curve_elapsed as _speed_curve_elapsed_seconds,
    curve_source_at_elapsed as _speed_curve_source_seconds_at_elapsed,
    make_map as _make_clock_map,
    unmap_time as _unmap_clock_time,
)
from .utils import atomic_write_json, atomic_write_text, new_id, now_iso, run_process, sha256_bytes, sha256_file


OUTPUT_PROFILES: dict[str, tuple[int, int]] = {
    "vertical": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
    "vertical_720": (720, 1280),
    "landscape_720": (1280, 720),
}

OUTPUT_CONTAINERS: dict[str, str] = {
    "mp4": "mp4",
    "webm": "webm",
    "mkv": "matroska",
}

OUTPUT_PIXEL_FORMATS = (
    "yuv420p",
    "yuv422p",
    "yuv444p",
    "yuv420p10le",
    "yuv422p10le",
    "yuv444p10le",
    "yuva420p",
)

ALPHA_OUTPUT_PIXEL_FORMATS = ("yuva420p",)


def _alpha_video_decoder(asset: dict[str, Any]) -> str | None:
    """The native VPX decoders omit WebM's separate alpha bitstream."""
    probe = asset.get('probe', {})
    stream = next((row for row in probe.get('streams', []) if row.get('codec_type') == 'video'), {})
    tags = stream.get('tags', {})
    alpha = next((value for key, value in tags.items() if str(key).lower() == 'alpha_mode'), None)
    if str(alpha) != '1':
        return None
    return {'vp8': 'libvpx', 'vp9': 'libvpx-vp9'}.get(stream.get('codec_name') or probe.get('video', {}).get('codec'))

# Names accepted by the local FFmpeg xfade filter.  ``crossfade``/``dissolve``
# and directional ``wipe``/``slide`` are Agent-friendly aliases; the remaining
# names map one-to-one so a template can expose the same transition catalog as
# the installed FFmpeg build without a GUI-only effect registry.
XFADE_TRANSITIONS = {
    "fade", "wipeleft", "wiperight", "wipeup", "wipedown", "slideleft", "slideright", "slideup", "slidedown",
    "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite", "radial", "smoothleft", "smoothright",
    "smoothup", "smoothdown", "circleopen", "circleclose", "horzopen", "horzclose", "vertopen", "vertclose",
    "diagtl", "diagtr", "diagbl", "diagbr", "hlslice", "hrslice", "vuslice", "vdslice", "pixelize", "zoomin",
    "fadefast", "fadeslow", "hlwind", "hrwind", "vuwind", "vdwind", "coverleft", "coverright", "coverup",
    "coverdown", "revealleft", "revealright", "revealup", "revealdown", "wipetl", "wipetr", "wipebl", "wipebr",
    "hblur", "fadegrays", "squeezeh", "squeezev",
}

TONE_MAP_ALGORITHMS = {"linear", "gamma", "clip", "reinhard", "hable", "mobius"}
TONE_MAP_INPUT_TRANSFERS = {"bt2020-10", "bt2020-12", "smpte2084", "arib-std-b67"}

DEFAULT_OUTPUT: dict[str, Any] = {
    "container": "mp4",
    "video": {"codec": "libx264", "preset": "medium", "crf": 18, "pixel_format": "yuv420p"},
    "audio": {"codec": "aac", "bitrate": "192k"},
}


def output_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized, JSON-safe output encoder configuration."""
    raw = settings.get("output") if isinstance(settings.get("output"), dict) else {}
    video_raw = raw.get("video") if isinstance(raw.get("video"), dict) else {}
    audio_raw = raw.get("audio") if isinstance(raw.get("audio"), dict) else {}
    container = str(raw.get("container", DEFAULT_OUTPUT["container"])).lower()
    if container not in OUTPUT_CONTAINERS:
        raise AppError("OUTPUT_CONTAINER_UNSUPPORTED", f"不支持的输出容器: {container}", exit_code=2, path="settings.output.container")
    video_codec = str(video_raw.get("codec", DEFAULT_OUTPUT["video"]["codec"]))
    audio_codec = str(audio_raw.get("codec", DEFAULT_OUTPUT["audio"]["codec"]))
    if audio_codec == "opus":
        audio_codec = "libopus"
    if video_codec not in {"libx264", "libx265", "libvpx-vp9", "libvpx", "libaom-av1"}:
        raise AppError("OUTPUT_VIDEO_CODEC_UNSUPPORTED", f"不支持的视频编码器: {video_codec}", exit_code=2, path="settings.output.video.codec")
    if audio_codec not in {"aac", "libopus", "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le"}:
        raise AppError("OUTPUT_AUDIO_CODEC_UNSUPPORTED", f"不支持的音频编码器: {audio_codec}", exit_code=2, path="settings.output.audio.codec")
    try:
        crf = int(video_raw.get("crf", DEFAULT_OUTPUT["video"]["crf"]))
    except (TypeError, ValueError) as exc:
        raise AppError("OUTPUT_CRF_INVALID", "视频 CRF 必须是整数", exit_code=2, path="settings.output.video.crf") from exc
    max_crf = 51 if video_codec in {"libx264", "libx265"} else 63
    if crf < 0 or crf > max_crf:
        raise AppError("OUTPUT_CRF_INVALID", f"{video_codec} 的 CRF 必须在 0 到 {max_crf} 之间", exit_code=2, path="settings.output.video.crf")
    pixel_format = str(video_raw.get("pixel_format", DEFAULT_OUTPUT["video"]["pixel_format"]))
    if pixel_format not in set(OUTPUT_PIXEL_FORMATS):
        raise AppError("OUTPUT_PIXEL_FORMAT_INVALID", f"不支持的像素格式: {pixel_format}", exit_code=2, path="settings.output.video.pixel_format")
    if pixel_format in ALPHA_OUTPUT_PIXEL_FORMATS and (container != "webm" or video_codec not in {"libvpx-vp9", "libvpx"}):
        raise AppError("OUTPUT_ALPHA_UNSUPPORTED", "透明视频当前只支持 WebM + VP9/VP8 + yuva420p", exit_code=2, path="settings.output")
    if container == "webm" and (video_codec not in {"libvpx-vp9", "libvpx", "libaom-av1"} or audio_codec not in {"libopus", "opus"}):
        raise AppError("OUTPUT_CODEC_CONTAINER_MISMATCH", "webm 需要 VP8/VP9/AV1 视频和 Opus 音频", exit_code=2, path="settings.output")
    if container == "mp4" and audio_codec in {"libopus", "opus"}:
        raise AppError("OUTPUT_CODEC_CONTAINER_MISMATCH", "mp4 当前只接受 AAC 音频", exit_code=2, path="settings.output.audio.codec")
    if container == "mp4" and audio_codec.startswith('pcm_'):
        raise AppError("OUTPUT_CODEC_CONTAINER_MISMATCH", "mp4 不支持当前 PCM 音频输出，请使用 AAC 或 MKV", exit_code=2, path="settings.output.audio.codec")
    normalized = {
        "container": container,
        "video": {"codec": video_codec, "preset": str(video_raw.get("preset", DEFAULT_OUTPUT["video"]["preset"])), "crf": crf, "pixel_format": pixel_format},
        "audio": {"codec": audio_codec, "bitrate": str(audio_raw.get("bitrate", DEFAULT_OUTPUT["audio"]["bitrate"]))},
    }
    if video_raw.get("bitrate"):
        normalized["video"]["bitrate"] = str(video_raw["bitrate"])
    for branch in ("video", "audio"):
        bitrate = normalized[branch].get("bitrate")
        if bitrate is not None and not re.fullmatch(r"[1-9][0-9]*(?:\.[0-9]+)?[kKmM]?", str(bitrate)):
            raise AppError("OUTPUT_BITRATE_INVALID", "码率必须是正数及可选 k/M 后缀，例如 192k 或 8M", exit_code=2, path=f"settings.output.{branch}.bitrate")
    if normalized["video"]["preset"] not in {"ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"}:
        raise AppError("OUTPUT_PRESET_INVALID", "编码 preset 不在支持列表中", exit_code=2, path="settings.output.video.preset")
    return normalized


def _output_color_args(settings: dict[str, Any]) -> list[str]:
    """Translate project color metadata into explicit FFmpeg output flags."""
    color = settings.get("color") if isinstance(settings.get("color"), dict) else {}
    values = {
        "-color_primaries": color.get("primaries"),
        "-color_trc": color.get("transfer"),
        "-colorspace": color.get("matrix"),
    }
    raw_range = str(color.get("range", "")).strip().lower()
    if raw_range:
        values["-color_range"] = {"limited": "tv", "full": "pc"}.get(raw_range, raw_range)
    args: list[str] = []
    for flag, raw_value in values.items():
        if raw_value is None or str(raw_value).strip() == "":
            continue
        value = str(raw_value).strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise AppError("COLOR_METADATA_INVALID", f"色彩元数据值无效: {value}", exit_code=2, path="settings.color")
        args.extend([flag, value])
    return args


def _sec(tick: int, tps: int) -> float:
    return tick / float(tps)


def _quoted(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _filter_file_path(root: Path, path: Path) -> str:
    # FFmpeg runs from the project root. Relative, forward-slash font paths
    # avoid Windows drive/backslash parsing and FreeType failures when the
    # absolute project directory contains non-ASCII characters.
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _num(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _tone_map_filters(settings: dict[str, Any], warnings: list[dict[str, Any]], clip_id: str, *, transparent: bool = False) -> list[str]:
    """Build an explicit local HDR-to-SDR tonemap chain when requested.

    The project color block describes the output metadata by default. HDR input
    details are opt-in under ``input_*`` fields so SDR projects never pay the
    zscale/float conversion cost or silently reinterpret their footage.
    """
    color = settings.get("color") if isinstance(settings.get("color"), dict) else {}
    algorithm = str(color.get("tone_map", color.get("tone_mapping", "none"))).strip().lower()
    if not algorithm or algorithm == "none":
        return []
    if algorithm not in TONE_MAP_ALGORITHMS:
        warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "hdr_tonemap", "message": f"不支持的 HDR tone map 算法: {algorithm}"})
        return []
    if transparent:
        warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "hdr_tonemap_with_alpha", "message": "当前 HDR tone map 不与透明 yuva 画布组合，已跳过"})
        return []
    input_transfer = str(color.get("input_transfer", "smpte2084")).strip().lower()
    input_primaries = str(color.get("input_primaries", "bt2020")).strip().lower()
    input_matrix = str(color.get("input_matrix", "bt2020nc")).strip().lower()
    input_range = str(color.get("input_range", "limited")).strip().lower()
    if input_transfer not in TONE_MAP_INPUT_TRANSFERS or input_primaries not in {"bt2020", "bt709"} or input_matrix not in {"bt2020nc", "bt2020c", "bt709"} or input_range not in {"limited", "full", "tv", "pc"}:
        warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "hdr_tonemap", "message": "HDR 输入色彩字段无效，已跳过 tone map"})
        return []
    range_name = {"limited": "tv", "full": "pc", "tv": "tv", "pc": "pc"}[input_range]
    desat = max(0.0, _num(color.get("tone_map_desat", 2.0), 2.0))
    peak = max(0.0, _num(color.get("tone_map_peak", 0.0), 0.0))
    tonemap = f"tonemap=tonemap={algorithm}:desat={desat:.4f}"
    if peak > 0:
        tonemap += f":peak={peak:.4f}"
    return [
        f"zscale=rin={range_name}:pin={input_primaries}:tin={input_transfer}:min={input_matrix}:t=linear:m=bt2020nc:p=bt2020:r=tv",
        "format=gbrpf32le",
        tonemap,
        "zscale=t=bt709:m=bt709:p=bt709:r=tv",
        "format=rgba",
    ]


def _tick(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _expr_arg(expression: str) -> str:
    """Keep commas in a quoted FFmpeg expression inside one filter argument."""
    return "'" + expression.replace("'", "\\'") + "'"


def _drawtext_arg(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace(",", "\\,").replace("%", "\\%")


def _wrap_subtitle_text(text: str, style: dict[str, Any], font_size: int, warnings: list[dict[str, Any]], clip_id: str, font_metrics: Any = None) -> str:
    """Wrap with the selected local font, disclosing the fallback explicitly."""
    layout = build_text_layout(text, style, font_metrics, font_size)
    if style.get("max_width", style.get("wrap_width")) is not None and font_metrics is None:
        warnings.append({
            "code": "RENDER_FEATURE_APPROXIMATE",
            "clip_id": clip_id,
            "feature": "subtitle_layout_wrap",
            "message": "字幕 max_width 使用本地平均字宽换行；精确字形度量仍由字体 golden render 校准",
        })
    return layout.text


def _subtitle_font_path(root: Path, style: dict[str, Any], assets: dict[str, dict[str, Any]] | None = None) -> Path | None:
    font_id = style.get("font_asset_id")
    if font_id:
        font_asset = (assets or {}).get(str(font_id))
        if not font_asset or font_asset.get("kind") != "font":
            raise AppError("SUBTITLE_FONT_REFERENCE_INVALID", "font_asset_id 必须引用本地 font 资产", exit_code=2, path=str(font_id))
        font_value = font_asset.get("uri")
    else:
        font_value = style.get("fontfile")
    if font_value:
        font = resolve_local_path(root, font_value, field="subtitle.style.fontfile")
        if not font.is_file():
            raise AppError("SUBTITLE_FONT_MISSING", "字幕字体文件不存在", exit_code=3, path=str(font))
        return font.resolve()
    windir = Path(os.environ.get("WINDIR", "C:/Windows"))
    return next((candidate for candidate in (windir / "Fonts" / "arial.ttf", windir / "Fonts" / "segoeui.ttf", windir / "Fonts" / "msyh.ttc", windir / "Fonts" / "simhei.ttf") if candidate.is_file()), None)


def _load_subtitle_font_metrics(font_path: Path | None, font_size: int) -> Any:
    """Load optional local Pillow metrics without making Pillow a hard dependency."""
    if font_path is None or not font_path.exists():
        return None
    try:
        from PIL import ImageFont

        return ImageFont.truetype(str(font_path), size=max(1, int(font_size)))
    except Exception:
        return None


def _subtitle_text_width(font_metrics: Any, text: str, font_size: int) -> float:
    return text_width(font_metrics, text, font_size)


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _mask_keyframe_expr(
    clip: dict[str, Any],
    mask: dict[str, Any],
    properties: tuple[str, ...],
    default: float,
    clip_start: float,
    tps: int,
) -> str:
    """Resolve a mask scalar from clip or mask-local keyframes.

    Mask-local tracks use the same shape as regular clip keyframes.  Keeping
    the evaluator shared makes mask motion deterministic and means Agents can
    author either ``mask.cx`` or a local ``cx`` property without another
    timing dialect.
    """
    aliases = tuple(dict.fromkeys(value if value.startswith("mask.") else f"mask.{value}" for value in properties))
    local_tracks = mask.get("keyframes") if isinstance(mask.get("keyframes"), list) else []
    clip_tracks = clip.get("keyframes") if isinstance(clip.get("keyframes"), list) else []

    def normalize(item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        name = str(item.get("property", ""))
        if name.startswith("mask.") or name.startswith("transform.") or name.startswith("audio."):
            return item
        return {**item, "property": f"mask.{name}"}

    normalized_clip = [item for raw in clip_tracks if (item := normalize(raw)) is not None]
    normalized_local = [item for raw in local_tracks if (item := normalize(raw)) is not None]
    if normalized_local or normalized_clip != clip_tracks:
        merged = dict(clip)
        merged["keyframes"] = [*normalized_clip, *normalized_local]
    else:
        merged = clip
    expression = _keyframe_expr(merged, aliases, default, clip_start, tps, time_variable="T")
    return f"clip(({expression}),0,1)"


def _mask_has_keyframe(clip: dict[str, Any], mask: dict[str, Any], properties: tuple[str, ...]) -> bool:
    """Return whether a mask scalar is animated in either keyframe location."""
    aliases = {name if name.startswith("mask.") else f"mask.{name}" for name in properties}
    tracks = []
    if isinstance(clip.get("keyframes"), list):
        tracks.extend(clip["keyframes"])
    if isinstance(mask.get("keyframes"), list):
        tracks.extend(mask["keyframes"])
    for track in tracks:
        if not isinstance(track, dict):
            continue
        name = str(track.get("property", ""))
        normalized = name if name.startswith("mask.") else f"mask.{name}"
        if normalized in aliases:
            return True
    return False


def _crop_keyframe_expr(
    clip: dict[str, Any],
    crop: dict[str, Any],
    properties: tuple[str, ...],
    default: float,
    clip_start: float,
    tps: int,
    *,
    time_variable: str = "t",
) -> str:
    """Resolve a crop scalar from clip or crop-local keyframes.

    Crop-local tracks may use short names (``x``/``y``); clip-level tracks use
    the explicit ``crop.x``/``crop.y`` namespace so they cannot collide with
    mask geometry tracks.  Native crop uses ``t`` for animated position;
    the fixed-canvas inverse sampler uses ``T`` for position and size.
    """
    aliases = tuple(dict.fromkeys(name if name.startswith("crop.") else f"crop.{name}" for name in properties))
    clip_tracks = clip.get("keyframes") if isinstance(clip.get("keyframes"), list) else []
    local_tracks = crop.get("keyframes") if isinstance(crop.get("keyframes"), list) else []
    normalized_local: list[dict[str, Any]] = []
    for item in local_tracks:
        if not isinstance(item, dict):
            continue
        name = str(item.get("property", ""))
        if not name.startswith("crop."):
            item = {**item, "property": f"crop.{name}"}
        normalized_local.append(item)
    merged = dict(clip)
    merged["keyframes"] = [*clip_tracks, *normalized_local]
    return _keyframe_expr(merged, aliases, default, clip_start, tps, time_variable=time_variable)


def _crop_has_keyframe(clip: dict[str, Any], crop: dict[str, Any], properties: tuple[str, ...]) -> bool:
    """Return whether a crop scalar is animated in either keyframe location."""
    aliases = {name if name.startswith("crop.") else f"crop.{name}" for name in properties}
    for track in clip.get("keyframes", []):
        if not isinstance(track, dict):
            continue
        if str(track.get("property", "")) in aliases:
            return True
    for track in crop.get("keyframes", []):
        if not isinstance(track, dict):
            continue
        name = str(track.get("property", ""))
        normalized = name if name.startswith("crop.") else f"crop.{name}"
        if normalized in aliases:
            return True
    return False


def _dynamic_crop_filters(
    clip: dict[str, Any],
    crop: dict[str, Any],
    canvas_width: int,
    canvas_height: int,
    source_width: int,
    source_height: int,
    clip_start: float,
    tps: int,
    *,
    alpha: bool = False,
    projection=None,
) -> list[str]:
    """Animate a crop window while keeping every output frame the same size.

    geq samples RGB and alpha planes with bilinear interpolation. Alpha
    inputs stay premultiplied through both geq and the final resize.
    It keeps the native raster size until the final canvas resize, so small
    crop windows do not allocate an enormous zoomed intermediate frame. Fit
    bars follow the static crop/pad alpha contract. Each plane
    has its own expression state; pure window/fit values are initialized at X=0
    on every scanline. Pixel/stateful expressions retain per-pixel evaluation.
    """
    normalized = str(crop.get("unit", "pixels")).lower() in {"normalized", "relative"}
    default_width = 1.0 if normalized else float(source_width or canvas_width)
    default_height = 1.0 if normalized else float(source_height or canvas_height)

    def scalar(names: tuple[str, ...], default: float) -> str:
        return _crop_keyframe_expr(clip, crop, names, default, clip_start, tps, time_variable="T")

    window_width = scalar(("width", "w"), _num(crop.get("width", crop.get("w", default_width)), default_width))
    window_height = scalar(("height", "h"), _num(crop.get("height", crop.get("h", default_height)), default_height))
    origin_x = scalar(("x",), _num(crop.get("x", 0), 0))
    origin_y = scalar(("y",), _num(crop.get("y", 0), 0))
    raw_window = [window_width,window_height,origin_x,origin_y]
    if normalized:
        window_width, window_height = f"W*({window_width})", f"H*({window_height})"
        origin_x, origin_y = f"W*({origin_x})", f"H*({origin_y})"
    # Clamp size before position so overshooting easing or a moving origin
    # cannot sample beyond the source. Tiny positive windows have a two-pixel
    # floor, the same minimum as the native static crop implementation.
    setup = (
        f"st(0,min(W,max(2,({window_width}))));"
        f"st(1,min(H,max(2,({window_height}))));"
        f"st(2,clip(({origin_x}),0,W-ld(0)));"
        f"st(3,clip(({origin_y}),0,H-ld(1)));"
    )
    fit = str(crop.get("fit", crop.get("mode", "fit"))).lower()
    pixel_setup = ""
    if fit == "stretch":
        pixel_setup = (
            "st(7,ld(2)+(X+0.5)*ld(0)/W-0.5);"
            "st(8,ld(3)+(Y+0.5)*ld(1)/H-0.5);st(9,1);"
        )
    else:
        scale_function = "max" if fit == "fill" else "min"
        destination_x = f"((X+0.5)*{canvas_width}/W)"
        destination_y = f"((Y+0.5)*{canvas_height}/H)"
        setup += (
            f"st(4,{scale_function}({canvas_width}/ld(0),{canvas_height}/ld(1)));"
            f"st(5,({canvas_width}-ld(0)*ld(4))/2);"
            f"st(6,({canvas_height}-ld(1)*ld(4))/2);"
        )
        pixel_setup = (
            f"st(7,ld(2)+({destination_x}-ld(5))/ld(4)-0.5);"
            f"st(8,ld(3)+({destination_y}-ld(6))/ld(4)-0.5);"
        )
        if fit == "fill":
            pixel_setup += "st(9,1);"
        else:
            pixel_setup += (
                f"st(9,gte({destination_x},ld(5))*lt({destination_x},ld(5)+ld(0)*ld(4))"
                f"*gte({destination_y},ld(6))*lt({destination_y},ld(6)+ld(1)*ld(4)));"
            )
    if _geq_row_invariant([window_width, window_height, origin_x, origin_y]):
        setup = f"if(eq(X,0),{setup.rstrip(';')},0);"
    setup += pixel_setup
    sample_x = "clip(ld(7),ld(2),ld(2)+ld(0)-1)"
    sample_y = "clip(ld(8),ld(3),ld(3)+ld(1)-1)"

    def plane(name: str, outside: int) -> str:
        return _expr_arg(f"{setup}if(ld(9),{name}({sample_x},{sample_y}),{outside})")

    prefix = ['format=gbrapf32le', 'premultiply=inplace=1'] if alpha else ['format=gbrap']
    suffix = ['unpremultiply=inplace=1', 'format=rgba'] if alpha else []
    cpu = prefix + [
        f"geq=r={plane('r', 0)}:g={plane('g', 0)}:b={plane('b', 0)}:a={plane('alpha', 0 if alpha else 255)}:interpolation=bilinear",
        f"scale={canvas_width}:{canvas_height}:flags=lanczos",
        "setsar=1",
    ] + suffix
    if projection is not None:
        from .projection_opencl import crop_body
        return projection.select(cpu,kind='dynamic-crop',expressions=raw_window+['0'],
            alpha_expressions=raw_window+['0' if alpha else '255'],
            source=(source_width,source_height),target=(source_width,source_height),
            body=crop_body((canvas_width,canvas_height),normalized=normalized,fit=fit),
            prefix=prefix,suffix=[f'scale={canvas_width}:{canvas_height}:flags=lanczos','setsar=1']+suffix,
            pure=_geq_row_invariant(raw_window),integer=not alpha,native_target=True)
    return cpu


def _mask_point(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        raw_x, raw_y = value.get("x"), value.get("y")
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        raw_x, raw_y = value[0], value[1]
    else:
        return None
    try:
        x, y = float(raw_x), float(raw_y)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))


def _sample_mask_path(mask: dict[str, Any], warnings: list[dict[str, Any]], clip_id: str) -> list[tuple[float, float]]:
    """Return polygon samples for a static line/cubic path contract.

    FFmpeg's expression evaluator can rasterize a fixed polygon efficiently,
    while it has no path primitive.  Sampling cubic segments at render-plan
    time keeps the project schema expressive and deterministic; the validator
    bounds the sample count and reports this as an explicit approximation.
    """
    raw_segments = mask.get("segments", mask.get("curve_segments", mask.get("curves")))
    if not isinstance(raw_segments, list) or not raw_segments:
        raw_points = mask.get("points")
        points: list[tuple[float, float]] = []
        if isinstance(raw_points, list):
            for raw_point in raw_points[:32]:
                point = _mask_point(raw_point)
                if point is not None:
                    points.append(point)
        return points
    points: list[tuple[float, float]] = []
    invalid = False
    for segment_index, segment in enumerate(raw_segments[:8]):
        if not isinstance(segment, dict):
            invalid = True
            continue
        segment_type = str(segment.get("type", "cubic")).lower().replace("-", "_")
        if segment_type in {"line", "linear"}:
            start = _mask_point(segment.get("from", segment.get("p0", segment.get("start"))))
            end = _mask_point(segment.get("to", segment.get("p1", segment.get("end"))))
            if start is None or end is None:
                invalid = True
                continue
            candidates = [start, end]
        elif segment_type in {"cubic", "bezier", "cubic_bezier"}:
            p0 = _mask_point(segment.get("from", segment.get("p0", segment.get("start"))))
            p1 = _mask_point(segment.get("control1", segment.get("p1", segment.get("c1"))))
            p2 = _mask_point(segment.get("control2", segment.get("p2", segment.get("c2"))))
            p3 = _mask_point(segment.get("to", segment.get("p3", segment.get("end"))))
            if any(point is None for point in (p0, p1, p2, p3)):
                invalid = True
                continue
            sample_count = max(2, min(16, int(_num(segment.get("samples", 8), 8))))
            assert p0 is not None and p1 is not None and p2 is not None and p3 is not None
            candidates = []
            for sample_index in range(sample_count + 1):
                u = sample_index / sample_count
                inv = 1.0 - u
                candidates.append((
                    inv * inv * inv * p0[0] + 3.0 * inv * inv * u * p1[0] + 3.0 * inv * u * u * p2[0] + u * u * u * p3[0],
                    inv * inv * inv * p0[1] + 3.0 * inv * inv * u * p1[1] + 3.0 * inv * u * u * p2[1] + u * u * u * p3[1],
                ))
        else:
            invalid = True
            continue
        for point in candidates:
            if points and abs(points[-1][0] - point[0]) < 1e-9 and abs(points[-1][1] - point[1]) < 1e-9:
                continue
            points.append(point)
            if len(points) >= 32:
                break
        if len(points) >= 32:
            break
    if invalid:
        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "mask:path_curve", "message": "路径曲线包含无效或未知段，已跳过无效段并使用剩余采样点"})
    return points[:32]


def _mask_has_segment_keyframe(clip: dict[str, Any], mask: dict[str, Any]) -> bool:
    pattern = re.compile(r"(?:mask\.)?(?:segments|curve_segments|curves)\.\d+\.(?:from|p0|start|control1|p1|c1|control2|p2|c2|to|p3|end)\.(?:x|y)")
    tracks: list[Any] = []
    if isinstance(clip.get("keyframes"), list):
        tracks.extend(clip["keyframes"])
    if isinstance(mask.get("keyframes"), list):
        tracks.extend(mask["keyframes"])
    return any(isinstance(track, dict) and pattern.fullmatch(str(track.get("property", ""))) for track in tracks)


def _sample_mask_path_expressions(
    mask: dict[str, Any],
    clip: dict[str, Any],
    clip_start: float,
    tps: int,
    warnings: list[dict[str, Any]],
    clip_id: str,
) -> tuple[list[tuple[str, str, float, float]], str]:
    """Sample curve segments while calculating each animated control point once."""
    raw_field = next((field for field in ("segments", "curve_segments", "curves") if isinstance(mask.get(field), list)), None)
    raw_segments = mask.get(raw_field) if raw_field else None
    if not isinstance(raw_segments, list) or not raw_segments:
        return [], ""

    registers: dict[tuple[int, str, str], int] = {}
    setup: list[str] = []
    register_limit_warning = False
    clip_tracks = clip.get("keyframes") if isinstance(clip.get("keyframes"), list) else []
    mask_tracks = mask.get("keyframes") if isinstance(mask.get("keyframes"), list) else []

    def has_component_keyframe(segment_index: int, aliases: tuple[str, ...], axis: str) -> bool:
        names = {
            f"{field}.{segment_index}.{alias}.{axis}"
            for field in ("segments", "curve_segments", "curves")
            for alias in aliases
        }
        for track in (*clip_tracks, *mask_tracks):
            if not isinstance(track, dict):
                continue
            property_name = str(track.get("property", ""))
            if property_name.removeprefix("mask.") in names:
                return True
        return False

    def raw_point(segment: dict[str, Any], aliases: tuple[str, ...]) -> tuple[float, float] | None:
        return _mask_point(next((segment[name] for name in aliases if name in segment), None))

    def component_expression(segment_index: int, aliases: tuple[str, ...], axis: str, default: float) -> str:
        nonlocal register_limit_warning
        key = (segment_index, aliases[0], axis)
        properties = tuple(
            f"mask.{field}.{segment_index}.{alias}.{axis}"
            for field in (raw_field, "segments", "curve_segments", "curves")
            for alias in aliases
        )
        if not has_component_keyframe(segment_index, aliases, axis):
            return f"{default:.8f}"
        if key not in registers:
            if len(registers) >= 10:
                register_limit_warning = True
                return _mask_keyframe_expr(clip, mask, properties, default, clip_start, tps)
            register = len(registers)
            registers[key] = register
            expression = _mask_keyframe_expr(clip, mask, properties, default, clip_start, tps)
            setup.append(f"st({register},({expression}))")
        return f"ld({registers[key]})"

    sampled: list[tuple[str, str, float, float]] = []
    invalid = False
    for segment_index, segment in enumerate(raw_segments[:8]):
        if not isinstance(segment, dict):
            invalid = True
            continue
        segment_type = str(segment.get("type", "cubic")).lower().replace("-", "_")
        if segment_type in {"line", "linear"}:
            point_aliases = (("from", "p0", "start"), ("to", "p1", "end"))
            defaults = [raw_point(segment, names) for names in point_aliases]
            if any(point is None for point in defaults):
                invalid = True
                continue
            candidates = [(0.0, point_aliases[0], defaults[0]), (1.0, point_aliases[1], defaults[1])]
        elif segment_type in {"cubic", "bezier", "cubic_bezier"}:
            point_aliases = (("from", "p0", "start"), ("control1", "p1", "c1"), ("control2", "p2", "c2"), ("to", "p3", "end"))
            defaults = [raw_point(segment, names) for names in point_aliases]
            if any(point is None for point in defaults):
                invalid = True
                continue
            sample_count = max(2, min(16, int(_num(segment.get("samples", 8), 8))))
            candidates = [(sample_index / sample_count, None, None) for sample_index in range(sample_count + 1)]
        else:
            invalid = True
            continue
        for progress, endpoint_aliases, static_value in candidates:
            if segment_type in {"line", "linear"}:
                assert static_value is not None
                x_default, y_default = static_value
                point_aliases_for_expression = endpoint_aliases if endpoint_aliases is not None else point_aliases[0]
                x_expression = component_expression(segment_index, point_aliases_for_expression, "x", x_default)
                y_expression = component_expression(segment_index, point_aliases_for_expression, "y", y_default)
            else:
                u = progress
                inv = 1.0 - u
                weights = (inv * inv * inv, 3.0 * inv * inv * u, 3.0 * inv * u * u, u * u * u)
                x_default = sum(weights[index] * defaults[index][0] for index in range(4) if defaults[index] is not None)
                y_default = sum(weights[index] * defaults[index][1] for index in range(4) if defaults[index] is not None)
                x_expression = "+".join(f"{weights[index]:.8f}*({component_expression(segment_index, point_aliases[index], 'x', defaults[index][0])})" for index in range(4) if defaults[index] is not None)
                y_expression = "+".join(f"{weights[index]:.8f}*({component_expression(segment_index, point_aliases[index], 'y', defaults[index][1])})" for index in range(4) if defaults[index] is not None)
            if sampled and abs(sampled[-1][2] - x_default) < 1e-9 and abs(sampled[-1][3] - y_default) < 1e-9:
                continue
            sampled.append((x_expression, y_expression, x_default, y_default))
            if len(sampled) >= 32:
                break
        if len(sampled) >= 32:
            break
    if invalid:
        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "mask:path_curve", "message": "路径曲线包含无效或未知段，已跳过无效段并使用剩余采样点"})
    if register_limit_warning:
        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "mask:path_curve_register_limit", "message": "路径动画控制点超过 FFmpeg 表达式寄存器上限，超出的关键帧直接展开表达式"})
    return sampled[:32], ";".join(setup)


def _mask_filter(
    mask: Any,
    warnings: list[dict[str, Any]],
    clip_id: str,
    *,
    clip: dict[str, Any] | None = None,
    clip_start: float = 0.0,
    tps: int = 90_000,
) -> str | None:
    """Compile normalized masks into an RGBA alpha expression.

    Rectangle/circle/ellipse geometry can be animated through regular clip
    keyframes or mask-local keyframes.  ``feather`` is normalized to the
    shortest output dimension and applied to alpha only, leaving colour sharp.
    """
    if not isinstance(mask, dict):
        return None
    clip_value = clip if isinstance(clip, dict) else {}
    mask_type = str(mask.get("type", "rectangle")).lower().replace("-", "_")
    if mask_type in {"none", "off"}:
        return None
    soft_edge: str | None = None
    dynamic_segment_setup = ""
    if mask_type == "rectangle":
        x = _mask_keyframe_expr(clip_value, mask, ("mask.x", "mask.position.x", "x"), _clamp(mask.get("x", 0.0), 0.0, 1.0, 0.0), clip_start, tps)
        y = _mask_keyframe_expr(clip_value, mask, ("mask.y", "mask.position.y", "y"), _clamp(mask.get("y", 0.0), 0.0, 1.0, 0.0), clip_start, tps)
        width = _mask_keyframe_expr(clip_value, mask, ("mask.width", "mask.w", "width", "w"), _clamp(mask.get("width", mask.get("w", 1.0)), 0.0, 1.0, 1.0), clip_start, tps)
        height = _mask_keyframe_expr(clip_value, mask, ("mask.height", "mask.h", "height", "h"), _clamp(mask.get("height", mask.get("h", 1.0)), 0.0, 1.0, 1.0), clip_start, tps)
        expression = (
            f"if(gte(X,W*({x}))*lte(X,W*min(1,({x})+({width})))"
            f"*gte(Y,H*({y}))*lte(Y,H*min(1,({y})+({height}))),255,0)"
        )
        soft_edge = f"min(min(X-W*({x}),W*(({x})+({width}))-X),min(Y-H*({y}),H*(({y})+({height}))-Y))"
    elif mask_type == "circle":
        cx = _mask_keyframe_expr(clip_value, mask, ("mask.cx", "mask.center_x", "cx", "center_x"), _clamp(mask.get("cx", mask.get("center_x", 0.5)), 0.0, 1.0, 0.5), clip_start, tps)
        cy = _mask_keyframe_expr(clip_value, mask, ("mask.cy", "mask.center_y", "cy", "center_y"), _clamp(mask.get("cy", mask.get("center_y", 0.5)), 0.0, 1.0, 0.5), clip_start, tps)
        radius = _mask_keyframe_expr(clip_value, mask, ("mask.radius", "radius"), _clamp(mask.get("radius", 0.5), 0.0, 1.0, 0.5), clip_start, tps)
        expression = (
            f"if(lte((X-W*({cx}))*(X-W*({cx}))+(Y-H*({cy}))*(Y-H*({cy})),"
            f"(min(W,H)*({radius}))*(min(W,H)*({radius}))),255,0)"
        )
        distance = f"sqrt((X-W*({cx}))*(X-W*({cx}))+(Y-H*({cy}))*(Y-H*({cy})))"
        soft_edge = f"(min(W,H)*({radius})-({distance}))"
    elif mask_type == "ellipse":
        cx = _mask_keyframe_expr(clip_value, mask, ("mask.cx", "mask.center_x", "cx", "center_x"), _clamp(mask.get("cx", mask.get("center_x", 0.5)), 0.0, 1.0, 0.5), clip_start, tps)
        cy = _mask_keyframe_expr(clip_value, mask, ("mask.cy", "mask.center_y", "cy", "center_y"), _clamp(mask.get("cy", mask.get("center_y", 0.5)), 0.0, 1.0, 0.5), clip_start, tps)
        rx = _mask_keyframe_expr(clip_value, mask, ("mask.rx", "mask.radius_x", "rx", "radius_x"), max(0.001, _clamp(mask.get("rx", mask.get("radius_x", 0.5)), 0.0, 1.0, 0.5)), clip_start, tps)
        ry = _mask_keyframe_expr(clip_value, mask, ("mask.ry", "mask.radius_y", "ry", "radius_y"), max(0.001, _clamp(mask.get("ry", mask.get("radius_y", 0.5)), 0.0, 1.0, 0.5)), clip_start, tps)
        rx, ry = f"max(0.000001,({rx}))", f"max(0.000001,({ry}))"
        norm_x = f"((X-W*({cx}))/(W*({rx})))"
        norm_y = f"((Y-H*({cy}))/(H*({ry})))"
        expression = f"if(lte(({norm_x})*({norm_x})+({norm_y})*({norm_y}),1),255,0)"
        distance = f"sqrt(({norm_x})*({norm_x})+({norm_y})*({norm_y}))"
        soft_edge = f"((1-({distance}))*min(W*({rx}),H*({ry})))"
    elif mask_type in {"path", "polygon"}:
        dynamic_segment_points, dynamic_segment_setup = _sample_mask_path_expressions(mask, clip_value, clip_start, tps, warnings, clip_id) if _mask_has_segment_keyframe(clip_value, mask) else ([], "")
        points = [(item[2], item[3]) for item in dynamic_segment_points] if dynamic_segment_points else _sample_mask_path(mask, warnings, clip_id)
        if len(points) < 3:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": f"mask:{mask_type}", "message": "path/polygon 遮罩至少需要三个合法点或有效曲线采样"})
            return None
        def point_expr(index: int, axis: str, default: float) -> str:
            if dynamic_segment_points:
                return dynamic_segment_points[index][0 if axis == "x" else 1]
            return _mask_keyframe_expr(
                clip_value,
                mask,
                (
                    f"mask.points.{index}.{axis}",
                    f"mask.points[{index}].{axis}",
                    f"mask.point.{index}.{axis}",
                    f"mask.point[{index}].{axis}",
                    f"points.{index}.{axis}",
                    f"points[{index}].{axis}",
                    f"point.{index}.{axis}",
                    f"point[{index}].{axis}",
                ),
                default,
                clip_start,
                tps,
            )

        crossings: list[str] = []
        for point_index, (x1, y1) in enumerate(points):
            x2, y2 = points[(point_index + 1) % len(points)]
            x1_expr = f"W*({point_expr(point_index, 'x', x1)})"
            y1_expr = f"H*({point_expr(point_index, 'y', y1)})"
            next_index = (point_index + 1) % len(points)
            x2_expr = f"W*({point_expr(next_index, 'x', x2)})"
            y2_expr = f"H*({point_expr(next_index, 'y', y2)})"
            denominator = f"({y2_expr}-{y1_expr})"
            x_intersection = f"if(eq({denominator},0),{x1_expr},({x1_expr}+({x2_expr}-{x1_expr})*(Y-({y1_expr}))/({denominator})))"
            crosses = f"((gte({y1_expr},Y)*lt({y2_expr},Y))+(lt({y1_expr},Y)*gte({y2_expr},Y)))"
            crossings.append(f"if(({crosses}*lt(X,{x_intersection})),1,0)")
        expression = f"if(eq(mod({'+'.join(crossings) or '0'},2),1),255,0)"
        # A polygon's signed distance is approximated by the minimum distance
        # to its animated line segments.  Combined with the winding result,
        # this gives a deterministic inner alpha feather without a GUI mask
        # rasterizer.  Point count stays fixed by the validator.
        edge_distances: list[str] = []
        for point_index in range(len(points)):
            next_index = (point_index + 1) % len(points)
            x1_expr = f"W*({point_expr(point_index, 'x', points[point_index][0])})"
            y1_expr = f"H*({point_expr(point_index, 'y', points[point_index][1])})"
            x2_expr = f"W*({point_expr(next_index, 'x', points[next_index][0])})"
            y2_expr = f"H*({point_expr(next_index, 'y', points[next_index][1])})"
            dx = f"({x2_expr}-{x1_expr})"
            dy = f"({y2_expr}-{y1_expr})"
            length_squared = f"max(0.000001,({dx})*({dx})+({dy})*({dy}))"
            projection = f"clip(((X-({x1_expr}))*({dx})+(Y-({y1_expr}))*({dy}))/({length_squared}),0,1)"
            closest_x = f"({x1_expr}+({projection})*({dx}))"
            closest_y = f"({y1_expr}+({projection})*({dy}))"
            edge_distances.append(f"sqrt((X-({closest_x}))*(X-({closest_x}))+(Y-({closest_y}))*(Y-({closest_y})))")
        if edge_distances:
            # Distance to a segment is positive on both sides of an edge.
            # Gate it with the winding result so pixels outside the polygon
            # remain transparent while the inner edge receives feathering.
            edge_distance = edge_distances[0]
            for candidate in edge_distances[1:]:
                edge_distance = f"min(({edge_distance}),({candidate}))"
            soft_edge = f"if(gt(({expression}),0),({edge_distance}),-1)"
    else:
        warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": f"mask:{mask_type}", "message": "当前 FFmpeg 后端支持 rectangle、circle、ellipse 和固定点数动态 path/polygon 遮罩"})
        return None
    feather = max(0.0, min(0.5, _num(mask.get("feather", 0), 0)))
    dynamic_feather = _mask_has_keyframe(clip_value, mask, ("mask.feather", "feather"))
    if dynamic_feather and soft_edge is not None:
        feather_expr = f"min(0.5,max(0,({_mask_keyframe_expr(clip_value, mask, ('mask.feather', 'feather'), feather, clip_start, tps)})))"
        expression = f"if(gt(({feather_expr}),0),clip(({soft_edge})/max(0.000001,min(W,H)*({feather_expr})),0,1)*255,({expression}))"
    elif dynamic_feather:
        warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "mask_dynamic_feather", "message": "当前遮罩类型没有可用的动态羽化表达式，使用静态羽化值"})
    if bool(mask.get("invert", False)):
        expression = f"(255-({expression}))"
    # Multiply by the existing alpha so transparent inputs and clip opacity
    # survive masking instead of becoming opaque inside the shape.
    alpha_expr = f"alpha(X,Y)*({expression})/255"
    if dynamic_segment_setup:
        alpha_expr = f"{dynamic_segment_setup};{alpha_expr}"
    alpha_filter = f"geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':a={_expr_arg(alpha_expr)}"
    if feather > 0 and not dynamic_feather:
        # Feather is normalized against the shortest output dimension. FFmpeg
        # evaluates this as alpha-only blur, preserving the source colour.
        radius = f"min(w,h)*{min(0.5, feather):.8f}"
        alpha_filter += f",boxblur=luma_radius=0:chroma_radius=0:alpha_radius={_expr_arg(radius)}:alpha_power=2"
    return alpha_filter


def render_fingerprints(project: dict[str, Any], sequence: dict[str, Any], settings: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """Return the dependency fingerprints required for a safe render resume."""
    project_payload = {"project": project, "sequence_id": sequence.get("id"), "settings": settings}
    project_fingerprint = sha256_bytes(json.dumps(project_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    sequence_map = {str(item.get("id")): item for item in project.get("sequences", []) if item.get("id")}
    asset_ids: set[str] = set()
    local_files: set[str] = set()
    seen_sequences: set[str] = set()
    particle_sources: list[dict[str, Any]] = []

    def collect(sequence_value: dict[str, Any]) -> None:
        sequence_id = str(sequence_value.get("id"))
        if sequence_id in seen_sequences:
            return
        seen_sequences.add(sequence_id)
        for track in sequence_value.get("tracks", []):
            for clip in track.get("clips", []):
                if isinstance(clip.get('generator'),dict) and clip['generator'].get('type')=='particles':
                    particle_sources.append(clip['generator'])
                if clip.get("asset_id"):
                    asset_ids.add(str(clip.get("asset_id")))
                subtitle = clip.get("subtitle") if isinstance(clip.get("subtitle"), dict) else {}
                subtitle_style = subtitle.get("style") if isinstance(subtitle.get("style"), dict) else {}
                if subtitle_style.get("font_asset_id"):
                    asset_ids.add(str(subtitle_style.get("font_asset_id")))
                for local_value in (subtitle.get("asset_uri"), subtitle_style.get("fontfile")):
                    if local_value:
                        local_files.add(str(local_value))
                if clip.get("sequence_id") in sequence_map:
                    collect(sequence_map[str(clip.get("sequence_id"))])

    collect(sequence)
    assets = {str(asset.get("id")): asset for asset in project.get("assets", []) if asset.get("id") in asset_ids}
    input_hashes: dict[str, str | None] = {}
    if (project.get('settings',{}).get('pixel_pipeline') or {}).get('engine')=='float32-native-v1':
        for name in ('float_optics','float_optics_kernel','float_glow','float_glow_kernel','float_color_signal','float_hdr','float_effect_chain','float_gpu','float_gpu_worker','float_gpu_native'):
            input_hashes['runtime:optics:'+name]='sha256:'+sha256_file(Path(__file__).with_name(name+'.py'))
    if particle_sources:
        for name in ('procedural_particles','particle_animation','float_timeline','float_gpu','float_gpu_worker','float_gpu_native','float_gpu_control'):
            input_hashes['runtime:particles:'+name]='sha256:'+sha256_file(Path(__file__).with_name(name+'.py'))
    for asset_id in sorted(assets):
        asset = assets[asset_id]
        digest = asset.get("sha256")
        uri = asset.get("uri")
        if uri:
            source = Path(str(uri))
            if root is not None and not source.is_absolute():
                source = root / source
            if source.exists() and source.is_file():
                digest = f"sha256:{sha256_file(source)}"
        input_hashes[asset_id] = digest
    if root is not None:
        for local_value in sorted(local_files):
            try:
                source = resolve_local_path(root, local_value, field="render.input")
            except AppError:
                continue
            digest = f"sha256:{sha256_file(source)}" if source.is_file() else None
            input_hashes[f"local:{local_value}"] = digest
    return {"project_fingerprint": project_fingerprint, "input_hashes": input_hashes}


def _bezier_progress_expr(progress: str, controls: Any) -> str:
    """Approximate a normalized cubic Bezier easing curve for FFmpeg.

    The Agent project contract accepts either ``[y1, y2]`` (fixed timing
    handles) or ``[x1, y1, x2, y2]`` (normalized CSS-style handles). FFmpeg's
    expression language has no inverse cubic solver, so solve x(u)=progress
    while building the filter graph and emit a small piecewise-linear lookup.
    This keeps the result frame-evaluable while preserving the intended value
    range exactly at both endpoints.
    """
    samples = bezier_samples(controls)
    if samples is None:
        return progress
    sample_count = len(samples)-1
    expression = f"{samples[-1]:.8f}"
    for index in range(sample_count - 1, -1, -1):
        start = index / sample_count
        end = (index + 1) / sample_count
        slope = (samples[index + 1] - samples[index]) / (end - start)
        segment = f"({samples[index]:.8f}+({slope:.8f})*((({progress})-{start:.8f})))"
        expression = f"if(lt(({progress}),{end:.8f}),{segment},{expression})"
    return f"if(lt(({progress}),0),{samples[0]:.8f},{expression})"


def _keyframe_expr(
    clip: dict[str, Any],
    properties: tuple[str, ...],
    default: float,
    clip_start: float,
    tps: int,
    *,
    time_variable: str = "t",
) -> str:
    tracks = {str(item.get("property")): item for item in clip.get("keyframes", []) if item.get("property")}
    track = next((tracks[name] for name in properties if name in tracks), None)
    if not track:
        return f"{default:.8f}"
    nested_clock = track.get('_nested_clock')
    if nested_clock is None and not str(track.get('property', '')).startswith('nested.parent.'):
        fallback = clip.get('_nested_keyframe_clock')
        if isinstance(fallback, dict):
            nested_clock = {**fallback, 'keyframes': track.get('keyframes', [])}
    authored = nested_clock.get('keyframes', []) if isinstance(nested_clock, dict) else track.get('keyframes', [])
    pairs: list[tuple[float, float, str, Any]] = []
    for item in authored:
        try:
            # Validated project keyframes are non-negative. Internal nested
            # parent tracks may intentionally use negative local offsets so
            # each child starts at the parent's already-interpolated value.
            pairs.append((float(item.get("at_tick", 0)) / tps, float(item.get("value")), str(item.get("interpolation", "linear")), item.get("control_points")))
        except (TypeError, ValueError):
            continue
    if not pairs:
        return f"{default:.8f}"
    pairs.sort(key=lambda item: item[0])
    local = f"({time_variable}-{clip_start:.8f})"
    if isinstance(nested_clock, dict):
        # Video filters receive the final timeline clock; audio automation
        # receives clip-local time. Reconstruct global time before undoing
        # the ancestors, then evaluate the original easing in its own clock.
        absolute = f'(({local})+{int(clip.get("timeline_start_tick", 0)) / tps:.12f})'
        original = _clock_expression(nested_clock['maps'], absolute, inverse=True)
        local = f'(({original})-{nested_clock["authored_start"]:.12f})'
    if len(pairs) == 1:
        return f"{pairs[0][1]:.8f}"
    segments: list[str] = []
    for index in range(len(pairs)-1):
        left_t, left_v, interpolation, controls = pairs[index]
        right_t, right_v, _, _ = pairs[index + 1]
        span = max(right_t - left_t, 1e-9)
        progress = f"clip((({local}-{left_t:.8f})/{span:.8f}),0,1)"
        if interpolation == "hold":
            eased = "0"
        elif interpolation == "ease_in":
            eased = f"({progress})*({progress})"
        elif interpolation == "ease_out":
            eased = f"1-(1-({progress}))*(1-({progress}))"
        elif interpolation == "ease_in_out":
            eased = f"if(lt({progress},0.5),2*({progress})*({progress}),1-((-2*({progress})+2)*(-2*({progress})+2))/2)"
        elif interpolation == "bezier":
            eased = _bezier_progress_expr(progress, controls)
        else:
            eased = progress
        interpolated = f"({left_v:.8f}+({right_v-left_v:.8f})*({eased}))"
        segments.append(interpolated)
    segments.append(f"{pairs[-1][1]:.8f}")
    # A balanced decision tree keeps long frame-sampled bindings below the
    # expression parser's recursion limit. Segment endpoint semantics remain
    # identical to the original right-recursive expression.
    def branch(low: int, high: int) -> str:
        if low == high:
            return segments[low]
        middle = (low+high+1)//2
        return f"if(lt({local},{pairs[middle][0]:.8f}),{branch(low,middle-1)},{branch(middle,high)})"
    expression = branch(0,len(segments)-1)
    return f"if(lt({local},{pairs[0][0]:.8f}),{pairs[0][1]:.8f},{expression})"


def _reverse_keyframe_controls(keyframe: dict[str, Any]) -> None:
    """Reverse a normalized easing curve when its timeline plays backwards."""
    if str(keyframe.get("interpolation", "linear")) != "bezier":
        return
    controls = keyframe.get("control_points")
    if not isinstance(controls, list):
        return
    try:
        values = [float(value) for value in controls]
    except (TypeError, ValueError):
        return
    if len(values) == 2:
        keyframe["control_points"] = [1.0 - values[1], 1.0 - values[0]]
    elif len(values) == 4:
        keyframe["control_points"] = [1.0 - values[2], 1.0 - values[3], 1.0 - values[0], 1.0 - values[1]]


def _transform_exprs(clip: dict[str, Any], start: float, tps: int) -> dict[str, str]:
    transform = clip.get("transform") if isinstance(clip.get("transform"), dict) else {}
    position = transform.get("position") if isinstance(transform.get("position"), dict) else {}
    anchor = transform.get("anchor") if isinstance(transform.get("anchor"), dict) else {}
    child_exprs = {
        "scale": _keyframe_expr(clip, ("transform.scale", "scale"), _num(transform.get("scale", 1.0), 1.0), start, tps),
        "rotation": _keyframe_expr(clip, ("transform.rotation", "rotation"), _num(transform.get("rotation", 0.0), 0.0), start, tps),
        "opacity": _keyframe_expr(clip, ("transform.opacity", "opacity"), _num(transform.get("opacity", 1.0), 1.0), start, tps, time_variable="T"),
        "position_x": _keyframe_expr(clip, ("transform.position.x", "position.x", "position_x"), _num(position.get("x", transform.get("position_x", 0.5)), 0.5), start, tps),
        "position_y": _keyframe_expr(clip, ("transform.position.y", "position.y", "position_y"), _num(position.get("y", transform.get("position_y", 0.5)), 0.5), start, tps),
        "anchor_x": _keyframe_expr(clip, ("transform.anchor.x", "anchor.x", "anchor_x"), _num(anchor.get("x", transform.get("anchor_x", 0.5)), 0.5), start, tps),
        "anchor_y": _keyframe_expr(clip, ("transform.anchor.y", "anchor.y", "anchor_y"), _num(anchor.get("y", transform.get("anchor_y", 0.5)), 0.5), start, tps),
    }
    raw_layers = clip.get("_nested_parent_transforms")
    layers: list[dict[str, Any]] = []
    if isinstance(raw_layers, list):
        layers = [item for item in raw_layers if isinstance(item, dict)]
    if not layers:
        parent = clip.get("_nested_parent_transform")
        if isinstance(parent, dict):
            layers = [{"transform": parent}]
    if not layers:
        return child_exprs

    # Layers are stored from outermost to innermost. Apply the innermost
    # parent first so position offsets are rotated/scaled in the same order as
    # static `combine_transforms` composition.
    result = child_exprs
    layer_count = len(layers)
    for layer_index in range(layer_count - 1, -1, -1):
        layer = layers[layer_index]
        parent = layer.get("transform") if isinstance(layer.get("transform"), dict) else layer
        parent_position = parent.get("position") if isinstance(parent.get("position"), dict) else {}
        prefix = "nested.parent.transform" if layer_count == 1 else f"nested.parent.{layer_index}.transform"
        parent_scale = _keyframe_expr(
            clip, (f"{prefix}.scale",), _num(parent.get("scale", 1.0), 1.0), start, tps,
        )
        parent_rotation = _keyframe_expr(
            clip, (f"{prefix}.rotation",), _num(parent.get("rotation", 0.0), 0.0), start, tps,
        )
        parent_opacity = _keyframe_expr(
            clip, (f"{prefix}.opacity",), _num(parent.get("opacity", 1.0), 1.0), start, tps, time_variable="T",
        )
        parent_x = _keyframe_expr(
            clip, (f"{prefix}.position.x",), _num(parent_position.get("x", parent.get("position_x", 0.5)), 0.5), start, tps,
        )
        parent_y = _keyframe_expr(
            clip, (f"{prefix}.position.y",), _num(parent_position.get("y", parent.get("position_y", 0.5)), 0.5), start, tps,
        )
        child_dx = f"(({result['position_x']})-0.5)*({parent_scale})"
        child_dy = f"(({result['position_y']})-0.5)*({parent_scale})"
        angle = f"(({parent_rotation})*PI/180)"
        result = {
            "scale": f"({parent_scale})*({result['scale']})",
            "rotation": f"({parent_rotation})+({result['rotation']})",
            "opacity": f"clip(({parent_opacity})*({result['opacity']}),0,1)",
            "position_x": f"({parent_x})+({child_dx})*cos({angle})-({child_dy})*sin({angle})",
            "position_y": f"({parent_y})+({child_dx})*sin({angle})+({child_dy})*cos({angle})",
            "anchor_x": result["anchor_x"],
            "anchor_y": result["anchor_y"],
        }
    return result


def _scale_filters(expression: str, *, alpha: bool = False) -> list[str]:
    """Keep invisible RGB out of the visible edge of a resized alpha layer.

    FFmpeg scale interpolates straight RGB and alpha independently. Weight
    RGB by alpha before filtering and divide afterwards, in float planar RGB
    so faint coverage is not lost to an 8-bit premultiplication round trip.
    Compositors and subsequent effects still receive straight RGBA.
    """
    if not alpha:
        return [expression]
    return ['format=gbrapf32le', 'premultiply=inplace=1', expression,
            'unpremultiply=inplace=1', 'format=rgba']


def _video_overlay_position(transform: dict[str, str], width: int, height: int) -> tuple[str, str]:
    """Return overlay coordinates that keep the authored anchor on position.

    Video layers are normalized to the output canvas before the transform
    chain. That makes the pre-rotation dimensions deterministic and lets the
    overlay expression compensate for FFmpeg's rotate filter expanding its
    bounding box. The subtitle compositor intentionally keeps its existing
    full-canvas rotation contract.
    """
    position_x = transform["position_x"]
    position_y = transform["position_y"]
    anchor_x = transform["anchor_x"]
    anchor_y = transform["anchor_y"]
    if transform["rotation"] == "0.00000000":
        return (
            f"({position_x})*W-w*({anchor_x})",
            f"({position_y})*H-h*({anchor_y})",
        )
    angle = f"(({transform['rotation']})*PI/180)"
    scaled_width = f"max(2,{width}*({transform['scale']}))"
    scaled_height = f"max(2,{height}*({transform['scale']}))"
    rotated_width = f"(abs(({scaled_width})*cos({angle}))+abs(({scaled_height})*sin({angle})))"
    rotated_height = f"(abs(({scaled_width})*sin({angle}))+abs(({scaled_height})*cos({angle})))"
    delta_x = f"(({anchor_x})-0.5)*({scaled_width})"
    delta_y = f"(({anchor_y})-0.5)*({scaled_height})"
    anchor_output_x = f"(({rotated_width})/2+({delta_x})*cos({angle})-({delta_y})*sin({angle}))"
    anchor_output_y = f"(({rotated_height})/2+({delta_x})*sin({angle})+({delta_y})*cos({angle}))"
    return (
        f"({position_x})*W-({anchor_output_x})",
        f"({position_y})*H-({anchor_output_y})",
    )


def _geq_row_invariant(expressions: list[str]) -> bool:
    """Only known pure, pixel-independent expressions may share scanline state."""
    functions = {'abs', 'acos', 'asin', 'atan', 'atan2', 'between', 'bitand', 'bitor',
                 'ceil', 'clip', 'cos', 'cosh', 'eq', 'exp', 'floor', 'gauss', 'gcd',
                 'gt', 'gte', 'hypot', 'if', 'ifnot', 'isinf', 'isnan', 'lerp', 'log',
                 'lt', 'lte', 'max', 'min', 'mod', 'not', 'pow', 'round', 'sgn',
                 'sin', 'sinh', 'sqrt', 'squish', 'tan', 'tanh', 'trunc'}
    return all(not re.search(r'\b(?:X|Y)\b', value)
               and set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', value)) <= functions
               for value in expressions)


def _geq_scanline_expression(definitions: dict[str, str], body: str, registers: tuple[int, ...]) -> str:
    """Compile a pure row DAG into disjoint persistent and pixel registers.

    Cache selection estimates repeated evaluation by expanded text length.
    This heuristic only chooses storage: it does not approximate expressions.
    Definitions are ordered dependencies. Pixel code must not write registers
    offered here; initialization repeats at X=0 for each plane/slice/scanline.
    """
    token = re.compile(r'@\{([a-z_]+)\}')
    seen: set[str] = set()
    for name, value in definitions.items():
        if not set(token.findall(value)) <= seen:
            raise ValueError('Row expression definitions must be topologically ordered')
        seen.add(name)
    if not set(token.findall(body)) <= seen or len(set(registers)) != len(registers):
        raise ValueError('Invalid row expression body/register allocation')
    if any(type(r) is not int or not 0 <= r < 10 for r in registers):
        raise ValueError('AVExpr has exactly ten registers')
    if set(map(int, re.findall(r'\bst\s*\(\s*(\d+)\s*,', body))) & set(registers):
        raise ValueError('Pixel writes cannot overwrite scanline registers')
    if not _geq_row_invariant(list(definitions.values())):
        raise ValueError('Row caching requires pure pixel-independent definitions')
    selected: set[str] = set()
    def cost(expression: str, cache: set[str], memo: dict[str, int]) -> int:
        total, offset = 0, 0
        for match in token.finditer(expression):
            name = match[1]
            if name in cache:
                weight = 5  # ld(n), independent of register allocation
            else:
                if name not in memo:
                    memo[name] = cost(definitions[name], cache, memo)+2
                weight = memo[name]
            total += match.start()-offset+weight
            offset = match.end()
        return total+len(expression)-offset
    for _ in registers:
        before = cost(body, selected, {})
        choices = [(before-cost(body, selected|{name}, {}), name)
                   for name in definitions if name not in selected]
        if not choices:
            break
        # Stable definition order resolves equal scores reproducibly.
        gain, name = max(choices, key=lambda item: item[0])
        if gain <= 0:
            break
        selected.add(name)
    allocation = dict(zip((name for name in definitions if name in selected), registers))
    memo: dict[str, str] = {}
    def expand(expression: str) -> str:
        def replace(match: re.Match[str]) -> str:
            name = match[1]
            if name in allocation:
                return f'ld({allocation[name]})'
            if name not in memo:
                memo[name] = '('+expand(definitions[name])+')'
            return memo[name]
        return token.sub(replace, expression)
    initialize = ';'.join(f'st({register},{expand(definitions[name])})'
                          for name, register in allocation.items())
    return (f'if(eq(X,0),{initialize},0);' if initialize else '')+expand(body)


def _affine_video_filters(transform: dict[str, str], *, projection=None, width=0, height=0) -> list[str]:
    """Sample a rotated layer onto its fixed output canvas around its anchor.

    The old rotate filter retained the input rectangle while its overlay
    position assumed an expanded rectangle. Inverse sampling keeps rotation,
    scale and placement in one pixel coordinate system, without allocating a
    scale-dependent intermediate image or clipping at the input rectangle.
    """
    values = {k: re.sub(r'\bt\b', 'T', v) for k,v in transform.items()}
    angle = f"({values['rotation']})*PI/180"
    setup = (
        f"st(0,cos({angle}));st(1,sin({angle}));"
        f"st(2,X+0.5-({values['position_x']})*W);"
        f"st(3,Y+0.5-({values['position_y']})*H);"
        f"st(4,max(0.00000001,abs({values['scale']})));"
        f"st(5,({values['anchor_x']})*W+(ld(2)*ld(0)+ld(3)*ld(1))/ld(4)-0.5);"
        f"st(6,({values['anchor_y']})*H+(-ld(2)*ld(1)+ld(3)*ld(0))/ld(4)-0.5);"
        "st(7,gte(ld(5),-0.5)*lt(ld(5),W-0.5)*gte(ld(6),-0.5)*lt(ld(6),H-0.5));"
    )
    # geq owns an AVExpr per plane/slice and visits every scanline from X=0.
    # Reinitialize each row instead of keying on T/N: timestamps may repeat,
    # slices may move, and each plane has its own register state. Keep the
    # original arithmetic order and sampling kernel; only pure row-invariant
    # transform calculations are reused. Stateful/pixel-dependent expressions
    # retain the original path to avoid changing their evaluation semantics.
    pure = _geq_row_invariant(list(values.values()))
    if pure:
        initialize = (
            f"st(7,{angle});st(0,cos(ld(7)));st(1,sin(ld(7)));"
            f"st(2,({values['position_x']})*W);st(3,({values['position_y']})*H);"
            f"st(4,max(0.00000001,abs({values['scale']})));"
            f"st(5,({values['anchor_x']})*W);st(6,({values['anchor_y']})*H)"
        )
        dx, dy = '(X+0.5-ld(2))', '(Y+0.5-ld(3))'
        setup = (
            f"if(eq(X,0),{initialize},0);"
            f"st(7,ld(5)+({dx}*ld(0)+{dy}*ld(1))/ld(4)-0.5);"
            f"st(8,ld(6)+(-{dx}*ld(1)+{dy}*ld(0))/ld(4)-0.5);"
            "st(9,gte(ld(7),-0.5)*lt(ld(7),W-0.5)*gte(ld(8),-0.5)*lt(ld(8),H-0.5));"
        )
    def plane(name: str) -> str:
        if pure:
            return _expr_arg(setup+f"if(ld(9),{name}(clip(ld(7),0,W-1),clip(ld(8),0,H-1)),0)")
        return _expr_arg(setup+f"if(ld(7),{name}(clip(ld(5),0,W-1),clip(ld(6),0,H-1)),0)")
    prefix=['format=gbrapf32le','premultiply=inplace=1']
    suffix=['unpremultiply=inplace=1','format=rgba']
    cpu = prefix+[
            f"geq=r={plane('r')}:g={plane('g')}:b={plane('b')}:a={plane('alpha')}:interpolation=bilinear",
            ]+suffix
    if projection is not None:
        from .projection_opencl import affine_body
        expressions=[f'cos({angle})',f'sin({angle})',values['position_x'],values['position_y'],
            f"max(0.00000001,abs({values['scale']}))",values['anchor_x'],values['anchor_y']]
        return projection.select(cpu,kind='affine',expressions=expressions,source=(width,height),
            target=(width,height),body=affine_body(),prefix=prefix,suffix=suffix,pure=pure,native_target=True)
    return cpu


def _speed_curve_segments(clip: dict[str, Any], source_span_tick: int, tps: int) -> list[tuple[float, float, float, float]]:
    """Preserve authored hold/linear/eased speed with a bounded clock compiler."""
    return compile_curve(clip, source_span_tick, tps)


def _reverse_speed_curve_segments(segments: list[tuple[float, float, float, float]]) -> list[tuple[float, float, float, float]]:
    """Map source-relative speed segments into the reversed clip clock.

    ``reverse`` reverses decoded frame order before the generated ``setpts``
    expression runs.  Reflecting each segment around the source span and
    swapping its endpoint speeds keeps each speed attached to its authored
    source position, instead of applying the forward ramp to the newly
    reversed frames.
    """
    if not segments:
        return []
    total = max(0.0, float(segments[-1][1]))
    reflected = [
        (max(0.0, total - end), max(0.0, total - start), right_speed, left_speed)
        for start, end, left_speed, right_speed in reversed(segments)
        if end > start
    ]
    reflected.sort(key=lambda item: item[0])
    return reflected


def _speed_curve_audio_parts(segments: list[tuple[float, float, float, float]]) -> list[tuple[float, float, float]]:
    """Approximate a varying speed curve with short constant-tempo audio parts.

    FFmpeg's ``atempo`` takes one scalar tempo per filter instance. Splitting
    each varying curve segment into bounded pieces keeps audio close to the
    same integrated duration as the video remap while remaining fully local
    and deterministic. Constant segments stay exact.
    """
    parts: list[tuple[float, float, float]] = []
    for start, end, left_speed, right_speed in segments:
        span = max(0.0, end - start)
        if span <= 1e-9:
            continue
        subdivisions = 1 if right_speed == left_speed else max(2, min(16, int(math.ceil(span * 8.0))))
        for index in range(subdivisions):
            part_start = start + span * index / subdivisions
            part_end = start + span * (index + 1) / subdivisions
            part_left_speed = left_speed + (right_speed - left_speed) * index / subdivisions
            part_right_speed = left_speed + (right_speed - left_speed) * (index + 1) / subdivisions
            # Match each part's analytic duration rather than its midpoint
            # speed.  Audio still uses constant-tempo windows, but their
            # cumulative boundaries share the video's integrated clock.
            if part_right_speed == part_left_speed:
                speed = part_left_speed
            else:
                speed = (part_right_speed - part_left_speed) / math.log1p((part_right_speed-part_left_speed)/part_left_speed)
            parts.append((part_start, part_end, max(0.01, speed)))
    return parts


def _tempo_chain(speed: float) -> str:
    """Keep each native atempo stage within 0.5..2, preserving unity identity."""
    remaining = float(speed)
    if not math.isfinite(remaining) or remaining <= 0:
        raise AppError('SPEED_INVALID', '音频 tempo 必须是有限正数', exit_code=2)
    if abs(remaining - 1.0) <= 1e-9:
        return 'anull'
    tempo: list[str] = []
    while remaining > 2.0:
        tempo.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        tempo.append("atempo=0.5")
        remaining /= 0.5
    tempo.append(f"atempo={remaining:.8f}")
    return ",".join(tempo)


def speed_curve_duration_seconds(clip: dict[str, Any], source_span_tick: int, tps: int) -> float | None:
    segments = _speed_curve_segments(clip, source_span_tick, tps)
    if not segments:
        return None
    return max(0.001, _speed_curve_elapsed_seconds(segments, segments[-1][1]))



def _speed_curve_setpts(segments: list[tuple[float, float, float, float]], timeline_start: float,
                        *, source_expression: str = '((PTS-STARTPTS)*TB)',
                        timeline_clock_ticks: int | None = None) -> str:
    """Use the same stable source integral as nested and authored clocks."""
    if not segments:
        return f'setpts=PTS-STARTPTS+{timeline_start:.12f}/TB'
    mapping = {'source_start': 0., 'source_end': segments[-1][1],
               'timeline_start': timeline_start if timeline_clock_ticks is None else 0.,
               'timeline_duration': _speed_curve_elapsed_seconds(segments, segments[-1][1]),
               'speed': 1., 'reverse': False, 'segments': segments, 'curve_scale': 1.}
    expression = _clock_expression([mapping], source_expression, scratch_register=0)
    value = f'({expression})/TB'
    if timeline_clock_ticks is not None:
        value += f'+{timeline_clock_ticks}'
    return 'setpts=' + _expr_arg(value)


def _insert_audio_freeze(
    filters: list[str],
    audio_chain: list[str],
    prefix: str,
    content_duration: float,
    freeze_at: float,
    freeze_duration: float,
) -> list[str]:
    """Insert sample-bounded silence before clip audio effects/automation.

    The timeline is quantized to 48 kHz once, then split by sample index.
    Padding/trim on the decoded input absorbs codec/atempo tail rounding and
    keeps the insertion at the same clip-local time for mono/stereo assets.
    """
    sample_rate = 48000
    content_samples = max(1, int(round(content_duration * sample_rate)))
    at_samples = max(0, min(content_samples, int(round(freeze_at * sample_rate))))
    hold_samples = max(1, int(round(freeze_duration * sample_rate)))
    base = f"{prefix}base"
    silence = f"{prefix}silence"
    frozen = f"{prefix}out"
    filters.append(
        ",".join(audio_chain)
        + f",aformat=sample_fmts=fltp:sample_rates={sample_rate}:channel_layouts=stereo,"
        f"apad=whole_len={content_samples},atrim=end_sample={content_samples},asetpts=N/SR/TB[{base}]"
    )
    filters.append(
        f"anullsrc=r={sample_rate}:cl=stereo,atrim=end_sample={hold_samples},aformat=sample_fmts=fltp:sample_rates={sample_rate}:channel_layouts=stereo,asetpts=N/SR/TB[{silence}]"
    )
    if at_samples == 0:
        parts = [silence, base]
    elif at_samples == content_samples:
        parts = [base, silence]
    else:
        pre_input, post_input = f"{prefix}prein", f"{prefix}postin"
        pre, post = f"{prefix}pre", f"{prefix}post"
        filters.append(f"[{base}]asplit=2[{pre_input}][{post_input}]")
        filters.append(f"[{pre_input}]atrim=end_sample={at_samples},asetpts=N/SR/TB[{pre}]")
        filters.append(f"[{post_input}]atrim=start_sample={at_samples},asetpts=N/SR/TB[{post}]")
        parts = [pre, silence, post]
    filters.append(
        "".join(f"[{part}]" for part in parts)
        + f"concat=n={len(parts)}:v=0:a=1,asetpts=N/SR/TB[{frozen}]"
    )
    # The first item must name a filter as well as its input label; joining a
    # bare label with commas would introduce an empty FFmpeg filter.
    return [f"[{frozen}]anull"]


def _effect_keyframe_tracks(effect: dict[str, Any], parameters: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized parameter keyframe tracks for one effect.

    Effects keep their own keyframe namespace so an Agent can animate a
    filter without colliding with clip transform/audio tracks.  Both the
    explicit top-level ``effect.keyframes`` form and the convenient
    ``parameters.keyframes`` form are accepted; aliases such as
    ``effect.brightness`` and ``parameters.brightness`` are normalized to
    ``brightness`` before the shared keyframe evaluator runs.
    """
    raw_tracks = effect.get("keyframes")
    if not isinstance(raw_tracks, list):
        raw_tracks = parameters.get("keyframes") if isinstance(parameters.get("keyframes"), list) else []
    effect_name = str(effect.get("type", "")).lower().replace("-", "_")
    prefixes = ("effect.", "parameters.", f"{effect_name}.") if effect_name else ("effect.", "parameters.")
    tracks: list[dict[str, Any]] = []
    for item in raw_tracks:
        if not isinstance(item, dict):
            continue
        property_name = str(item.get("property", "")).strip().lower().replace("-", "_")
        for prefix in prefixes:
            if property_name.startswith(prefix):
                property_name = property_name[len(prefix):]
                break
        if not property_name:
            continue
        tracks.append({**item, "property": property_name})
    return tracks


def _effect_has_keyframe(effect: dict[str, Any], parameters: dict[str, Any], aliases: tuple[str, ...]) -> bool:
    names = {str(alias).lower().replace("-", "_") for alias in aliases}
    return any(str(item.get("property", "")) in names for item in _effect_keyframe_tracks(effect, parameters))


def _effect_keyframe_expr(
    effect: dict[str, Any],
    parameters: dict[str, Any],
    aliases: tuple[str, ...],
    default: float,
    clip_start: float,
    tps: int,
    *, clip: dict[str, Any] | None = None,
) -> str:
    tracks = _effect_keyframe_tracks(effect, parameters)
    if not tracks:
        return f"{default:.8f}"
    return _keyframe_expr(
        {**(clip or {}), "keyframes": tracks},
        tuple(str(alias).lower().replace("-", "_") for alias in aliases),
        default,
        clip_start,
        tps,
        time_variable="t",
    )


def _key_with_input_alpha(native_filter: str, target: str) -> str:
    """The native key replaces alpha. Combine its matte with stage input alpha.

    Branches have the same frame clock; RGB comes directly from the key stage.
    Labels are allocated by the root compiler, including static key effects.
    """
    if not native_filter.startswith(('colorkey=', 'colorkey@')):
        raise AppError('EFFECT_AUTOMATION_FILTER_INVALID', '抠像覆盖只能包装固定 colorkey 映射', exit_code=6)
    source,key,original,colors,matte,coverage,combined=(target+'_'+name for name in
        ('source','key','original','colors','matte','coverage','combined'))
    return (f'format=rgba,split=2[{source}][{key}];'
            f'[{source}]alphaextract[{original}];'
            f'[{key}]{native_filter},split=2[{colors}][{matte}];'
            f'[{matte}]alphaextract[{coverage}];'
            f"[{original}][{coverage}]blend=all_expr='floor(A*B/255+0.5)':shortest=1[{combined}];"
            f'[{colors}][{combined}]alphamerge')


def _effect_filters(
    effects: Any,
    warnings: list[dict[str, Any]],
    clip_id: str,
    *,
    root: Path | None = None,
    clip: dict[str, Any] | None = None,
    clip_start: float = 0.0,
    tps: int = 90000,
    automation: EffectAutomation | None = None,
    automation_meta: list[dict[str, Any]] | None = None,
) -> list[str]:
    filters: list[str] = []
    clip_value = clip if isinstance(clip, dict) else {}
    for effect_index, effect in enumerate(effects or []):
        if isinstance(effect, dict) and effect.get("enabled", True) is False:
            continue
        if isinstance(effect, str):
            effect_type, parameters = effect, {}
            effect_value: dict[str, Any] = {"type": effect_type}
        elif isinstance(effect, dict):
            effect_type = str(effect.get("type", ""))
            parameters = effect.get("parameters") if isinstance(effect.get("parameters"), dict) else effect
            effect_value = effect
        else:
            continue
        name = effect_type.strip().lower().replace("-", "_")
        from .float_glow import ALIASES as GLOW_ALIASES
        if name in GLOW_ALIASES:
            raise AppError('FLOAT_GLOW_NATIVE_PIPELINE_REQUIRED','高光扩散必须通过原生线性Float32管线执行',exit_code=2)
        from .float_optics import ALIASES as OPTICAL_ALIASES
        if name in OPTICAL_ALIASES:
            raise AppError('FLOAT_OPTICS_NATIVE_PIPELINE_REQUIRED','光学效果必须通过原生线性Float32管线执行',exit_code=2)
        effect_tracks = _effect_keyframe_tracks(effect_value, parameters)

        def expression(aliases: tuple[str, ...], default: float) -> str:
            return _effect_keyframe_expr(effect_value, parameters, aliases, default, clip_start, tps, clip=clip_value)

        def has_track(aliases: tuple[str, ...]) -> bool:
            return _effect_has_keyframe(effect_value, parameters, aliases)

        def warn_unsupported_tracks() -> None:
            if effect_tracks and _runtime_effect_name(name) is None:
                warnings.append({
                    "code": "RENDER_FEATURE_APPROXIMATE",
                    "clip_id": clip_id,
                    "feature": f"effect_keyframes:{effect_type}",
                    "message": "当前效果滤镜不支持逐帧参数表达式，使用静态参数值",
                })

        def invalid_parameter(message: str) -> None:
            warnings.append({
                "code": "EFFECT_PARAMETER_INVALID",
                "clip_id": clip_id,
                "feature": f"effect:{effect_type}",
                "message": message,
            })

        if name in {'curves', 'curve', 'rgb_curves', 'rgb_curve', 'channel_curves'} and effect_tracks:
            if automation is None:
                raise AppError('EFFECT_AUTOMATION_CONTEXT_MISSING', '动态曲线需要共享根图实例与命令预算', exit_code=6)
            duration = int(clip_value.get('duration_tick', 0))/tps
            generated, evidence = automation.bind_curves(effect_value, clip_value, clip_start, clip_start+duration)
            filters.extend(generated)
            if automation_meta is not None:
                automation_meta.append(evidence)
            continue
        if name in {'selective_hsl', 'hsl_bands', 'eight_band_hsl'}:
            from .selective_hsl import compile_filter
            from .hsl_native import compile_native
            kernel, evidence = compile_filter(effect_value, expression)
            kernel, evidence = compile_native(effect_value, expression, kernel, evidence)
            if automation is None:
                raise AppError('SELECTIVE_HSL_CONTEXT_MISSING', '分色 HSL 需要根渲染图配额上下文', exit_code=6)
            duration = int(clip_value.get('duration_tick', 0))/tps
            automation.reserve_hsl(evidence, clip_value, clip_start, clip_start+duration)
            if kernel:
                filters.append(kernel)
            if automation_meta is not None:
                automation_meta.append(evidence)
        elif name in {"lut", "lut3d", "cube", "look"}:
            raw_lut_path = parameters.get("path", parameters.get("file", parameters.get("lut")))
            lut_id = parameters.get("lut_id")
            if lut_id is not None and str(lut_id).strip():
                if root is None:
                    warnings.append({"code": "LUT_ID_CONTEXT_MISSING", "clip_id": clip_id, "feature": "lut3d", "message": "lut_id 引用需要项目根目录上下文"})
                    continue
                from .lut_library import resolve_lut_path

                resolved_lut = resolve_lut_path(root, str(lut_id).strip())
                if resolved_lut is None:
                    warnings.append({"code": "LUT_ID_MISSING", "clip_id": clip_id, "feature": "lut3d", "message": f"LUT 库中不存在: {lut_id}"})
                    continue
                raw_lut_path = resolved_lut[0]
            if not raw_lut_path:
                warnings.append({"code": "LUT_FILE_MISSING", "clip_id": clip_id, "feature": "lut3d", "message": "LUT 效果没有提供 path/file"})
                continue
            raw_lut_text = str(raw_lut_path)
            if raw_lut_text.lower().startswith("file://"):
                raw_lut_text = raw_lut_text[7:]
            lut_path = Path(raw_lut_text)
            if not lut_path.is_absolute() and root is not None:
                lut_path = root / lut_path
            if not lut_path.exists() or not lut_path.is_file():
                warnings.append({"code": "LUT_FILE_MISSING", "clip_id": clip_id, "feature": "lut3d", "message": f"LUT 文件不存在: {lut_path}"})
                continue
            intensity = _num(parameters.get("intensity", 1.0), 1.0)
            if not math.isfinite(intensity) or intensity < 0.0 or intensity > 1.0:
                warnings.append({"code": "EFFECT_PARAMETER_INVALID", "clip_id": clip_id, "feature": "lut3d", "message": "LUT intensity 必须位于 0..1，已跳过该效果"})
                continue
            # A zero-strength LUT is an exact no-op.  Static intermediate
            # strengths are materialized as a deterministic project-local CUBE
            # so the regular FFmpeg lut3d filter remains single-input and can
            # still be used by subtitle, adjustment, and nested clip chains.
            if not effect_tracks and intensity <= 1e-9:
                continue
            if not effect_tracks and intensity < 1.0 - 1e-9:
                if root is None:
                    warnings.append({"code": "LUT_INTENSITY_CONTEXT_MISSING", "clip_id": clip_id, "feature": "lut3d", "message": "LUT intensity 派生缓存需要项目根目录上下文，已跳过该效果"})
                    continue
                try:
                    from .lut_library import prepare_lut_intensity

                    lut_path = prepare_lut_intensity(root, lut_path, intensity)
                except AppError as exc:
                    if exc.code in {'LUT_INTENSITY_CACHE_HASH_MISMATCH', 'LUT_SOURCE_CHANGED'}:
                        raise
                    warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "lut_intensity", "message": str(exc)})
                    continue
                warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "lut_intensity", "message": "静态强度由 red-fastest identity 混合 CUBE 执行；域外/非线性和舍入结果可能与像素混合不同"})
            interpolation = str(parameters.get("interpolation", parameters.get("interp", "tetrahedral"))).lower()
            if interpolation not in {"nearest", "trilinear", "tetrahedral", "pyramid", "prism"}:
                warnings.append({"code": "LUT_INTERPOLATION_INVALID", "clip_id": clip_id, "feature": "lut3d", "message": f"LUT interpolation 无效，已回退 tetrahedral: {interpolation}"})
                interpolation = "tetrahedral"
            if effect_tracks:
                warn_unsupported_tracks()
            filters.append(f"lut3d=file='{_quoted(str(lut_path))}':interp={interpolation}")
        elif name in {"grayscale", "black_white", "blackandwhite"}:
            filters.append("hue=s=0")
        elif name == "sepia":
            filters.append("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131")
        elif name in {"blur", "gaussian_blur", "gblur"}:
            radius = max(0.0, min(128.0, _num(parameters.get('radius', parameters.get('sigma', 4)), 4)))
            filters.append(f"gblur=sigma={radius:.6f}:sigmaV={radius:.6f}")
        elif name in {"avgblur", "average_blur"}:
            if effect_tracks:
                warn_unsupported_tracks()
            size_x = max(1, min(1024, int(round(_num(parameters.get("size_x", parameters.get("sizeX", 2)), 2)))))
            size_y = max(0, min(1024, int(round(_num(parameters.get("size_y", parameters.get("sizeY", 2)), 2)))))
            planes = max(0, min(15, int(round(_num(parameters.get("planes", 15), 15)))))
            filters.append(f"avgblur=sizeX={size_x}:sizeY={size_y}:planes={planes}")
        elif name in {"box_blur", "boxblur"}:
            radius = max(1.0, _num(parameters.get("radius", 4), 4))
            power = max(1.0, min(4.0, _num(parameters.get("power", 1), 1)))
            filters.append(f"boxblur=luma_radius={radius:.4f}:luma_power={power:.4f}")
        elif name == "smartblur":
            if effect_tracks:
                warn_unsupported_tracks()
            radius = max(0.1, min(5.0, _num(parameters.get("radius", parameters.get("luma_radius", 1)), 1)))
            strength = max(-1.0, min(1.0, _num(parameters.get("strength", parameters.get("luma_strength", 1)), 1)))
            threshold = max(-30, min(30, int(round(_num(parameters.get("threshold", parameters.get("luma_threshold", 0)), 0)))))
            filters.append(f"smartblur=lr={radius:.4f}:ls={strength:.4f}:lt={threshold}")
        elif name in {"sharpen", "unsharp"}:
            filters.append(f"unsharp=5:5:{_num(parameters.get('amount', 1), 1):.4f}:5:5:0")
        elif name in {"brightness", "contrast", "saturation", "color"}:
            brightness = _num(parameters.get("brightness", parameters.get("amount", 0)), 0)
            contrast = _num(parameters.get("contrast", 1), 1)
            saturation = _num(parameters.get("saturation", 1), 1)
            dynamic_aliases = {
                "brightness": ("brightness", "amount", "value"),
                "contrast": ("contrast", "amount", "value"),
                "saturation": ("saturation", "amount", "value"),
            }
            if name == "brightness":
                brightness = expression(dynamic_aliases[name], brightness)
            elif name == "contrast":
                contrast = expression(dynamic_aliases[name], contrast)
            elif name == "saturation":
                saturation = expression(dynamic_aliases[name], saturation)
            else:
                brightness = expression(("brightness",), brightness)
                contrast = expression(("contrast",), contrast)
                saturation = expression(("saturation",), saturation)
            if effect_tracks:
                supported = any(has_track(aliases) for aliases in dynamic_aliases.values())
                if supported:
                    filters.append(
                        f"eq=brightness={_expr_arg(str(brightness))}:contrast={_expr_arg(str(contrast))}:"
                        f"saturation={_expr_arg(str(saturation))}:eval=frame"
                    )
                else:
                    warn_unsupported_tracks()
                    filters.append(f"eq=brightness={_num(brightness, 0):.6f}:contrast={_num(contrast, 1):.6f}:saturation={_num(saturation, 1):.6f}")
            else:
                filters.append(f"eq=brightness={_num(brightness, 0):.6f}:contrast={_num(contrast, 1):.6f}:saturation={_num(saturation, 1):.6f}")
        elif name in {"hue", "hue_rotate"}:
            hue_value = _num(parameters.get("degrees", parameters.get("angle", 0)), 0)
            hue_aliases = ("degrees", "angle", "hue", "value")
            if has_track(hue_aliases):
                filters.append(f"hue=h={_expr_arg(expression(hue_aliases, hue_value))}")
            else:
                if effect_tracks:
                    warn_unsupported_tracks()
                filters.append(f"hue=h={hue_value:.6f}")
        elif name in {"hsl", "hsl_adjust"}:
            hue_value = max(-360.0, min(360.0, _num(parameters.get("hue", parameters.get("degrees", 0)), 0)))
            saturation_value = max(0.0, min(4.0, _num(parameters.get("saturation", 1), 1)))
            lightness_value = max(-1.0, min(1.0, _num(parameters.get("lightness", parameters.get("brightness", 0)), 0)))
            hue_aliases = ("hue", "degrees", "angle", "value")
            saturation_aliases = ("saturation", "value")
            lightness_aliases = ("lightness", "brightness", "value")
            if effect_tracks and any(has_track(aliases) for aliases in (hue_aliases, saturation_aliases, lightness_aliases)):
                hue_expr = expression(hue_aliases, hue_value)
                saturation_expr = expression(saturation_aliases, saturation_value)
                lightness_expr = expression(lightness_aliases, lightness_value)
                filters.append(
                    f"hue=h={_expr_arg(str(hue_expr))}:s={_expr_arg(str(saturation_expr))}:"
                    f"b={_expr_arg(str(lightness_expr))}"
                )
            else:
                if effect_tracks:
                    warn_unsupported_tracks()
                filters.append(f"hue=h={hue_value:.6f}:s={saturation_value:.6f}:b={lightness_value:.6f}")
        elif name in {"gamma", "gamma_adjust"}:
            gamma_value = max(0.1, min(10.0, _num(parameters.get("gamma", parameters.get("amount", 1)), 1)))
            gamma_aliases = ("gamma", "amount", "value")
            if has_track(gamma_aliases):
                filters.append(f"eq=gamma={_expr_arg(expression(gamma_aliases, gamma_value))}:eval=frame")
            else:
                if effect_tracks:
                    warn_unsupported_tracks()
                filters.append(f"eq=gamma={gamma_value:.6f}")
        elif name in {"color_temperature", "temperature", "warmth"}:
            kelvin = max(1000.0, min(40000.0, _num(parameters.get("kelvin", 6500), 6500)))
            delta = max(-1.0, min(1.0, (kelvin - 6500.0) / 6500.0))
            filters.append(f"colorbalance=rs={-delta * 0.30:.6f}:gs={-delta * 0.05:.6f}:bs={delta * 0.30:.6f}")
        elif name in {"color_balance", "colorbalance"}:
            red = max(-1.0, min(1.0, _num(parameters.get("red", parameters.get("rs", 0)), 0)))
            green = max(-1.0, min(1.0, _num(parameters.get("green", parameters.get("gs", 0)), 0)))
            blue = max(-1.0, min(1.0, _num(parameters.get("blue", parameters.get("bs", 0)), 0)))
            filters.append(f"colorbalance=rs={red:.6f}:gs={green:.6f}:bs={blue:.6f}")
        elif name in {"color_wheel", "three_way_color", "three_way_wheel"}:
            if effect_tracks:
                warn_unsupported_tracks()
            shadows = [max(-1.0, min(1.0, _num(parameters.get(f"shadows_{channel}", 0), 0))) for channel in ("red", "green", "blue")]
            midtones = [max(-1.0, min(1.0, _num(parameters.get(f"midtones_{channel}", 0), 0))) for channel in ("red", "green", "blue")]
            highlights = [max(-1.0, min(1.0, _num(parameters.get(f"highlights_{channel}", 0), 0))) for channel in ("red", "green", "blue")]
            preserve_raw = parameters.get("preserve_luma", parameters.get("pl", False))
            if isinstance(preserve_raw, bool):
                preserve = preserve_raw
            else:
                preserve = str(preserve_raw).strip().lower() in {"1", "true", "yes", "on", "lum"}
            filters.append(
                "colorbalance="
                f"rs={shadows[0]:.6f}:gs={shadows[1]:.6f}:bs={shadows[2]:.6f}:"
                f"rm={midtones[0]:.6f}:gm={midtones[1]:.6f}:bm={midtones[2]:.6f}:"
                f"rh={highlights[0]:.6f}:gh={highlights[1]:.6f}:bh={highlights[2]:.6f}:pl={int(preserve)}"
            )
        elif name == "exposure":
            if effect_tracks:
                warn_unsupported_tracks()
            exposure = max(-3.0, min(3.0, _num(parameters.get("amount", parameters.get("exposure", 0)), 0)))
            black = max(-1.0, min(1.0, _num(parameters.get("black", 0), 0)))
            filters.append(f"exposure=exposure={exposure:.6f}:black={black:.6f}")
        elif name in {"color_levels", "levels", "colorlevels"}:
            if effect_tracks:
                warn_unsupported_tracks()
            input_black = max(-1.0, min(1.0, _num(parameters.get("input_black", parameters.get("rimin", 0)), 0)))
            input_white = max(-1.0, min(1.0, _num(parameters.get("input_white", parameters.get("rimax", 1)), 1)))
            output_black = max(0.0, min(1.0, _num(parameters.get("output_black", parameters.get("romin", 0)), 0)))
            output_white = max(0.0, min(1.0, _num(parameters.get("output_white", parameters.get("romax", 1)), 1)))
            preserve = str(parameters.get("preserve", "none")).strip().lower()
            if preserve in {"false", "0", "none", "off", ""}:
                preserve = "none"
            elif preserve in {"true", "1", "lum", "max", "avg", "sum", "nrm", "pwr"}:
                preserve = "lum" if preserve in {"true", "1"} else preserve
            else:
                invalid_parameter(f"color_levels preserve 无效: {preserve}")
                preserve = "none"
            filters.append(
                "colorlevels="
                f"rimin={input_black:.6f}:gimin={input_black:.6f}:bimin={input_black:.6f}:"
                f"rimax={input_white:.6f}:gimax={input_white:.6f}:bimax={input_white:.6f}:"
                f"romin={output_black:.6f}:gomin={output_black:.6f}:bomin={output_black:.6f}:"
                f"romax={output_white:.6f}:gomax={output_white:.6f}:bomax={output_white:.6f}:preserve={preserve}"
            )
        elif name in {"curves", "curve"}:
            if effect_tracks:
                warn_unsupported_tracks()
            curve_spec = str(parameters.get("all", parameters.get("master", "0/0 1/1"))).strip()
            tokens = curve_spec.split()
            valid = bool(tokens) and all(
                len(token.split("/")) == 2
                and all(0.0 <= _num(part, -1.0) <= 1.0 for part in token.split("/"))
                and re.fullmatch(r"[0-9eE+./-]+", token) is not None
                for token in tokens
            )
            if not valid:
                invalid_parameter("curves all/master 必须是由 0..1 范围 x/y 点组成的空格分隔字符串")
            else:
                filters.append(f"curves=all={_expr_arg(curve_spec)}")
        elif name in {"rgb_curves", "rgb_curve", "channel_curves"}:
            if effect_tracks:
                warn_unsupported_tracks()

            def valid_curve(value: str) -> bool:
                tokens = value.split()
                return bool(tokens) and all(
                    len(token.split("/")) == 2
                    and all(0.0 <= _num(part, -1.0) <= 1.0 for part in token.split("/"))
                    and re.fullmatch(r"[0-9eE+./-]+", token) is not None
                    for token in tokens
                )

            curve_specs: list[tuple[str, str]] = []
            curve_invalid = False
            for parameter_name, option_name in (
                ("all", "all"),
                ("red", "red"),
                ("green", "green"),
                ("blue", "blue"),
            ):
                if parameter_name not in parameters:
                    continue
                raw_curve = str(parameters.get(parameter_name, "")).strip()
                if not raw_curve:
                    continue
                if not valid_curve(raw_curve):
                    invalid_parameter(f"rgb_curves {parameter_name} 必须是由 0..1 范围 x/y 点组成的空格分隔字符串")
                    curve_invalid = True
                    continue
                curve_specs.append((option_name, raw_curve))
            if curve_specs and not curve_invalid:
                filters.append("curves=" + ":".join(f"{option}={_expr_arg(value)}" for option, value in curve_specs))
        elif name in {"color_contrast", "colorcontrast"}:
            if effect_tracks:
                warn_unsupported_tracks()
            red = max(-1.0, min(1.0, _num(parameters.get("red", parameters.get("rc", 0)), 0)))
            green = max(-1.0, min(1.0, _num(parameters.get("green", parameters.get("gm", 0)), 0)))
            blue = max(-1.0, min(1.0, _num(parameters.get("blue", parameters.get("by", 0)), 0)))
            red_weight = max(0.0, min(1.0, _num(parameters.get("red_weight", parameters.get("rcw", 0)), 0)))
            green_weight = max(0.0, min(1.0, _num(parameters.get("green_weight", parameters.get("gmw", 0)), 0)))
            blue_weight = max(0.0, min(1.0, _num(parameters.get("blue_weight", parameters.get("byw", 0)), 0)))
            preserve = max(0.0, min(1.0, _num(parameters.get("preserve_luma", parameters.get("pl", 0)), 0)))
            filters.append(f"colorcontrast=rc={red:.6f}:gm={green:.6f}:by={blue:.6f}:rcw={red_weight:.6f}:gmw={green_weight:.6f}:byw={blue_weight:.6f}:pl={preserve:.6f}")
        elif name == "vignette":
            angle = _num(parameters.get("angle", 0.785398), 0.785398)
            angle_aliases = ("angle", "value")
            if has_track(angle_aliases):
                filters.append(f"vignette=angle={_expr_arg(expression(angle_aliases, angle))}:eval=frame")
            else:
                if effect_tracks:
                    warn_unsupported_tracks()
                filters.append(f"vignette=angle={angle:.6f}")
        elif name in {"noise", "film_grain"}:
            if effect_tracks:
                warn_unsupported_tracks()
            filters.append(f"noise=alls={max(1, int(_num(parameters.get('amount', 8), 8)))}:allf=t+u")
        elif name in {"invert", "negative", "negate"}:
            filters.append("negate")
        elif name in {"edge", "edges", "edgedetect"}:
            low = max(0.0, min(1.0, _num(parameters.get("low", 0.1), 0.1)))
            high = max(low, min(1.0, _num(parameters.get("high", 0.4), 0.4)))
            filters.append(f"edgedetect=low={low:.6f}:high={high:.6f}")
        elif name in {"deband", "debanding"}:
            threshold = max(0.001, min(0.5, _num(parameters.get("threshold", 0.02), 0.02)))
            radius = max(1, min(64, int(_num(parameters.get("range", 16), 16))))
            filters.append(f"deband=1thr={threshold:.6f}:2thr={threshold:.6f}:3thr={threshold:.6f}:4thr={threshold:.6f}:range={radius}")
        elif name == "deflicker":
            if effect_tracks:
                warn_unsupported_tracks()
            size = max(2, min(129, int(round(_num(parameters.get("size", 5), 5)))))
            mode = str(parameters.get("mode", "am")).strip().lower()
            if mode not in {"am", "gm", "hm", "qm", "cm", "pm", "median"}:
                invalid_parameter(f"deflicker mode 无效: {mode}")
                mode = "am"
            filters.append(f"deflicker=size={size}:mode={mode}")
        elif name == "dctdnoiz":
            if effect_tracks:
                warn_unsupported_tracks()
            sigma = max(0.0, min(999.0, _num(parameters.get("sigma", 0), 0)))
            overlap = max(-1, min(15, int(round(_num(parameters.get("overlap", -1), -1)))))
            block_bits = parameters.get("block_bits")
            if block_bits is None and parameters.get("block_size") is not None:
                block_size = max(8, min(16, int(round(_num(parameters.get("block_size"), 8)))))
                block_bits = 4 if block_size >= 16 else 3
            block_bits = max(3, min(4, int(round(_num(block_bits, 3)))))
            filters.append(f"dctdnoiz=sigma={sigma:.6f}:overlap={overlap}:n={block_bits}")
        elif name in {"frame_interpolation", "minterpolate", "optical_flow", "smooth_slow_motion", "slow_motion"}:
            if effect_tracks:
                warn_unsupported_tracks()
            fps = max(1.0, min(240.0, _num(parameters.get("fps", 60.0), 60.0)))
            mi_mode = str(parameters.get("mi_mode", "mci")).strip().lower()
            if mi_mode not in {"dup", "blend", "mci"}:
                invalid_parameter(f"frame_interpolation mi_mode 无效: {mi_mode}")
                mi_mode = "mci"
            mc_mode = str(parameters.get("mc_mode", "obmc")).strip().lower()
            if mc_mode not in {"obmc", "aobmc"}:
                invalid_parameter(f"frame_interpolation mc_mode 无效: {mc_mode}")
                mc_mode = "obmc"
            me_mode = str(parameters.get("me_mode", "bilat")).strip().lower()
            if me_mode not in {"bidir", "bilat"}:
                invalid_parameter(f"frame_interpolation me_mode 无效: {me_mode}")
                me_mode = "bilat"
            me = str(parameters.get("me", parameters.get("me_method", "epzs"))).strip().lower()
            if me not in {"esa", "tss", "tdls", "ntss", "fss", "ds", "hexbs", "epzs", "umh"}:
                invalid_parameter(f"frame_interpolation me 无效: {me}")
                me = "epzs"
            mb_size = max(4, min(16, int(round(_num(parameters.get("mb_size", 16), 16)))))
            search_param = max(4, min(512, int(round(_num(parameters.get("search_param", 32), 32)))))
            vsbmc_raw = parameters.get("vsbmc", False)
            vsbmc = int(vsbmc_raw) if isinstance(vsbmc_raw, bool) else int(_num(vsbmc_raw, 0) >= 0.5)
            scd = str(parameters.get("scd", "fdiff")).strip().lower()
            if scd not in {"none", "fdiff"}:
                invalid_parameter(f"frame_interpolation scd 无效: {scd}")
                scd = "fdiff"
            scd_threshold = max(0.0, min(100.0, _num(parameters.get("scd_threshold", 10.0), 10.0)))
            filters.append(
                f"minterpolate=fps={fps:.6f}:mi_mode={mi_mode}:mc_mode={mc_mode}:me_mode={me_mode}:"
                f"me={me}:mb_size={mb_size}:search_param={search_param}:vsbmc={vsbmc}:scd={scd}:scd_threshold={scd_threshold:.6f}"
            )
        elif name == "hqdn3d":
            if effect_tracks:
                warn_unsupported_tracks()
            luma_spatial = max(0.0, min(30.0, _num(parameters.get("luma_spatial", parameters.get("ls", 4)), 4)))
            chroma_spatial = max(0.0, min(30.0, _num(parameters.get("chroma_spatial", parameters.get("cs", 3)), 3)))
            luma_temporal = max(0.0, min(30.0, _num(parameters.get("luma_temporal", parameters.get("lt", 6)), 6)))
            chroma_temporal = max(0.0, min(30.0, _num(parameters.get("chroma_temporal", parameters.get("ct", 4.5)), 4.5)))
            filters.append(f"hqdn3d={luma_spatial:.4f}:{chroma_spatial:.4f}:{luma_temporal:.4f}:{chroma_temporal:.4f}")
        elif name in {"deshake", "stabilize"}:
            radius = max(1, min(128, int(_num(parameters.get("radius", 16), 16))))
            filters.append(f"deshake=rx={radius}:ry={radius}")
        elif name in {"histeq", "histogram_equalize"}:
            filters.append("histeq")
        elif name in {"gradfun", "gradient_smooth"}:
            filters.append(f"gradfun=thr={max(0.1, min(64.0, _num(parameters.get('threshold', 1.2), 1.2))):.4f}:radius={max(1, min(32, int(_num(parameters.get('radius', 8), 8))))}")
        elif name in {"posterize", "posterization"}:
            levels = max(2, min(256, int(_num(parameters.get("levels", 8), 8))))
            step = max(1, round(255 / (levels - 1)))
            filters.append(f"lutrgb=r='floor(val/{step})*{step}':g='floor(val/{step})*{step}':b='floor(val/{step})*{step}'")
        elif name == "solarize":
            if effect_tracks:
                warn_unsupported_tracks()
            threshold = max(0, min(255, int(round(_num(parameters.get("threshold", 128), 128)))))
            expression = f"if(gt(val,{threshold}),255-val,val)"
            filters.append(f"lutrgb=r={_expr_arg(expression)}:g={_expr_arg(expression)}:b={_expr_arg(expression)}")
        elif name == "threshold":
            if effect_tracks:
                warn_unsupported_tracks()
            threshold = max(0, min(255, int(round(_num(parameters.get("value", parameters.get("threshold", 128)), 128)))))
            expression = f"if(gte(val,{threshold}),255,0)"
            filters.append(f"lutyuv=y={_expr_arg(expression)}")
        elif name == "tmix":
            if effect_tracks:
                warn_unsupported_tracks()
            frames = max(1, min(1024, int(round(_num(parameters.get("frames", 3), 3)))))
            parts = [f"tmix=frames={frames}"]
            if "scale" in parameters:
                parts.append(f"scale={max(0.0, min(32767.0, _num(parameters.get('scale'), 0))):.6f}")
            filters.append(":".join(parts))
        elif name == "tblend":
            if effect_tracks:
                warn_unsupported_tracks()
            mode = str(parameters.get("mode", "average")).strip().lower()
            allowed_modes = {"normal", "addition", "addition128", "and", "average", "burn", "darken", "difference", "difference128", "divide", "dodge", "exclusion", "extremity", "freeze", "glow", "grainextract", "hardlight", "hardmix", "heat", "lighten", "linearlight", "multiply", "multiply128", "negation", "or", "overlay", "phoenix", "pinlight", "reflect", "screen", "softdifference", "softlight", "stain", "subtract", "vividlight", "xor", "geometric", "harmonic", "bleach", "interpolate", "hardoverlay"}
            if mode not in allowed_modes:
                invalid_parameter(f"tblend mode 无效: {mode}")
                mode = "average"
            filters.append(f"tblend=all_mode={mode}")
        elif name in {"lens_correction", "lenscorrection"}:
            if effect_tracks:
                warn_unsupported_tracks()
            k1 = max(-1.0, min(1.0, _num(parameters.get("k1", 0), 0)))
            k2 = max(-1.0, min(1.0, _num(parameters.get("k2", 0), 0)))
            cx = max(0.0, min(1.0, _num(parameters.get("cx", 0.5), 0.5)))
            cy = max(0.0, min(1.0, _num(parameters.get("cy", 0.5), 0.5)))
            filters.append(f"lenscorrection=k1={k1:.6f}:k2={k2:.6f}:cx={cx:.6f}:cy={cy:.6f}")
        elif name in {"draw_box", "drawbox", "rectangle"}:
            if effect_tracks:
                warn_unsupported_tracks()
            x = max(0.0, min(1.0, _num(parameters.get("x", 0.05), 0.05)))
            y = max(0.0, min(1.0, _num(parameters.get("y", 0.05), 0.05)))
            width = max(0.0, min(1.0, _num(parameters.get("width", 0.9), 0.9)))
            height = max(0.0, min(1.0, _num(parameters.get("height", 0.9), 0.9)))
            color = str(parameters.get("color", "white@0.8"))
            if not re.fullmatch(r"[A-Za-z0-9#@._+\-]+", color):
                invalid_parameter("draw_box color 只能包含 FFmpeg 颜色 token 字符")
                color = "white@0.8"
            thickness = max(1, min(256, int(round(_num(parameters.get("thickness", parameters.get("t", 4)), 4)))))
            filters.append(f"drawbox=x=iw*{x:.6f}:y=ih*{y:.6f}:w=iw*{width:.6f}:h=ih*{height:.6f}:color={_quoted(color)}:t={thickness}")
        elif name in {"chroma_key", "chromakey", "green_screen"}:
            color = str(parameters.get("color", "0x00ff00"))
            similarity = max(0.00001, min(1.0, _num(parameters.get("similarity", 0.1), 0.1)))
            blend = max(0.0, min(1.0, _num(parameters.get("blend", 0), 0)))
            filters.append(f"colorkey={_quoted(color)}:{similarity:.6f}:{blend:.6f}")
        elif name in {"flip", "horizontal_flip", "hflip"}:
            if effect_tracks:
                warn_unsupported_tracks()
            filters.append("hflip")
        elif name in {"vertical_flip", "vflip"}:
            if effect_tracks:
                warn_unsupported_tracks()
            filters.append("vflip")
        else:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": f"effect:{effect_type}", "message": "当前 FFmpeg 后端没有安全映射"})
        if effect_tracks and _runtime_effect_name(name) is not None:
            if automation is None:
                raise AppError('EFFECT_AUTOMATION_CONTEXT_MISSING', '动态效果需要完整根图的实例与命令预算上下文', exit_code=6)
            duration = int(clip_value.get('duration_tick', 0))/tps
            if _runtime_effect_name(name) == 'lut3d':
                generated, evidence = automation.bind_lut(effect_value, filters[-1], lut_path,
                                                           clip_value, clip_start, clip_start+duration)
            else:
                generated, evidence = automation.bind(effect_value, filters[-1], clip_value,
                                                       clip_start, clip_start+duration)
            filters[-1:] = generated
            if automation_meta is not None:
                automation_meta.append(evidence)
        if name in {'chroma_key', 'chromakey', 'green_screen'}:
            if automation is not None:
                alpha_target = automation.reserve_key_alpha()
            else:
                # Internal standalone static callers have no recursive root.
                # Product render paths always supply the shared compiler.
                identity = f'{clip_id}|{clip_start}|{effect_index}|{filters[-1]}'
                alpha_target = 'avk_key_local_'+hashlib.sha256(identity.encode('utf8')).hexdigest()[:16]
            filters[-1] = _key_with_input_alpha(filters[-1], alpha_target)
            if automation_meta is not None:
                automation_meta.append({'kind':'colorkey-alpha-coverage', 'clip_id':clip_id,
                    'target':alpha_target, 'operation':'round(input_alpha_at_key_stage*native_key_coverage/255)',
                    'precision':'8-bit', 'input_coverage_preserved':True})
    return filters


def _subtitle_filter(
    root: Path,
    subtitle: Any,
    warnings: list[dict[str, Any]],
    clip_id: str,
    clip_start: float = 0.0,
    clip_duration: float = 0.0,
    *,
    timeline_window: bool = False,
    rotation_supported: bool = False,
    assets: dict[str, dict[str, Any]] | None = None,
    time_expression: str = 't',
    visible_window: tuple[float, float] | None = None,
    animation_alpha: list[str] | None = None,
    layout_evidence: dict[str, Any] | None = None,
    dynamic_raster: bool = False,
    paint_text: Callable[[list[str]], str] | None = None,
    command_targets: dict[str, list[str]] | None = None,
    render_clock: dict[str, Any] | None = None,
    final_fps: str = '30',
    frame_origin: float = 0.,
    float_paint: bool = False,
) -> str | None:
    if not isinstance(subtitle, dict):
        return None
    if subtitle.get("asset_uri"):
        path = resolve_local_path(root, subtitle["asset_uri"], field="subtitle.asset_uri")
        if path.exists():
            if subtitle.get("animation") or isinstance(subtitle.get("style"), dict) and subtitle["style"].get("animation"):
                warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "subtitle_asset_animation", "message": "外部字幕文件的文字动画未执行"})
            options = [f"subtitles=filename='{_quoted(_filter_file_path(root, path))}'", "alpha=1"]
            style = subtitle.get('style') if isinstance(subtitle.get('style'), dict) else {}
            if style.get('fontfile') or style.get('font_asset_id'):
                font_path = _subtitle_font_path(root, style, assets)
                options.append(f"fontsdir='{_quoted(_filter_file_path(root, font_path.parent))}'")
                metrics = _load_subtitle_font_metrics(font_path, 16)
                family = metrics.getname()[0] if metrics is not None else ''
                overrides = []
                if family and not any(c in family for c in ',=\r\n'):
                    overrides.append('Fontname=' + family)
                else:
                    warnings.append({'code': 'SUBTITLE_ASSET_FONT_FAMILY_UNAVAILABLE', 'clip_id': clip_id,
                                     'message': '外部字幕可读取本地字体目录，但未取得可用的字体族名称；需核验最终字体'})
                if 'fontsize' in style:
                    overrides.append(f"Fontsize={max(1, int(_num(style['fontsize'], 52)))}")
                if overrides:
                    options.append(f"force_style='{_quoted(','.join(overrides))}'")
            return ':'.join(options)
        warnings.append({"code": "SUBTITLE_ASSET_MISSING", "clip_id": clip_id, "message": f"字幕文件不存在: {path}"})
        return None
    if subtitle.get("text") is None:
        return None
    draw = paint_text or (lambda options: ':'.join(options))
    style = subtitle.get("style") if isinstance(subtitle.get("style"), dict) else {}
    source_subtitle_text = str(subtitle.get("text"))
    subtitle_text = source_subtitle_text
    font_size = max(1, int(_num(style.get("fontsize", 52), 52)))
    resolved_font_path = _subtitle_font_path(root, style, assets)
    font_metrics = _load_subtitle_font_metrics(resolved_font_path, font_size)
    subtitle_text = _wrap_subtitle_text(subtitle_text, style, font_size, warnings, clip_id, font_metrics)
    parts = [f"drawtext=text='{_drawtext_arg(subtitle_text)}'", f"fontcolor={_quoted(style.get('fontcolor', 'white'))}", f"fontsize={font_size}"]
    def add_alpha(expression: str) -> None:
        if animation_alpha is None:
            parts.append(f"alpha={_expr_arg(expression)}")
        else:
            # drawtext's own alpha option squares opacity on transparent
            # rasters. Apply authored opacity to normalized glyph alpha.
            animation_alpha.append(expression)

    window_start, window_duration = visible_window or (clip_start, clip_duration)
    window_expression = f'gte(t,{window_start:.9f})*lt(t,{window_start + max(0.001, window_duration):.9f})'
    if timeline_window:
        parts.append(f"enable={_expr_arg(window_expression)}")
    if resolved_font_path is not None:
        parts.append(f"fontfile='{_quoted(_filter_file_path(root, resolved_font_path))}'")
    integer_options = {
        "line_spacing": ("line_spacing", -2000, 2000),
        "borderw": ("borderw", 0, 100),
        "shadowx": ("shadowx", -2000, 2000),
        "shadowy": ("shadowy", -2000, 2000),
        "boxw": ("boxw", 0, 10000),
        "boxh": ("boxh", 0, 10000),
        "tabsize": ("tabsize", 0, 256),
    }
    for style_key, (drawtext_key, low, high) in integer_options.items():
        if style_key not in style:
            continue
        number = int(round(_clamp(style.get(style_key), low, high, 0)))
        parts.append(f"{drawtext_key}={number}")
    for style_key, drawtext_key in (("bordercolor", "bordercolor"), ("shadowcolor", "shadowcolor")):
        if style_key in style:
            parts.append(f"{drawtext_key}={_quoted(style.get(style_key))}")
    text_align = style.get("text_align", style.get("align"))
    if text_align is not None:
        alignment_tokens = [token.strip().lower() for token in re.split(r"[+|, ]+", str(text_align)) if token.strip()]
        allowed_alignment = {"left", "right", "center", "top", "bottom", "middle", "l", "r", "c", "t", "b", "m"}
        if alignment_tokens and all(token in allowed_alignment for token in alignment_tokens):
            parts.append(f"text_align={'+'.join(alignment_tokens)}")
        else:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "subtitle_text_align", "message": "字幕 text_align 包含当前 drawtext 不支持的方向"})
    if "boxborderw" in style or "box_padding" in style:
        box_border = int(round(_clamp(style.get("boxborderw", style.get("box_padding", 12)), 0, 1000, 12)))
    else:
        box_border = 12
    if style.get("text_shaping") is not None:
        parts.append(f"text_shaping={'1' if bool(style.get('text_shaping')) else '0'}")
    if style.get("fix_bounds") is not None:
        parts.append(f"fix_bounds={'1' if bool(style.get('fix_bounds')) else '0'}")
    if style.get("expansion") is not None:
        expansion = str(style.get("expansion")).lower()
        if expansion in {"none", "normal", "strftime"}:
            parts.append(f"expansion={expansion}")
        else:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": "subtitle_expansion", "message": "字幕 expansion 必须是 none、normal 或 strftime"})
    base_x = str(style.get("x", "(w-text_w)/2"))
    base_y = str(style.get("y", "h-text_h-120"))
    if time_expression != 't':
        base_x = re.sub(r'\bt\b', lambda _: f'({time_expression})', base_x)
        base_y = re.sub(r'\bt\b', lambda _: f'({time_expression})', base_y)
    word_timing = subtitle.get("word_timing")
    typing_plan = None
    def finish(value: str, evidence: dict[str, Any] | None = None) -> str:
        if evidence and layout_evidence is not None:
            layout_evidence.update(evidence)
        if typing_plan is not None:
            value, typing_evidence = typing_plan.finish(value, command_targets or {})
            if layout_evidence is not None:
                layout_evidence['typing'] = typing_evidence
        return value
    animation = subtitle.get("animation") if isinstance(subtitle.get("animation"), dict) else style.get("animation") if isinstance(style.get("animation"), dict) else {}
    animation_type = str(animation.get("type", "")).lower().replace("-", "_")
    clock_number = lambda v: format(v,'.17g') if float_paint else format(v,'.6f')
    if animation_type:
        animation_duration = max(0.001, _num(animation.get("duration", min(0.3, max(0.05, clip_duration / 4 or 0.3))), 0.3))
        delay = max(0.0, _num(animation.get("delay", 0.0), 0.0))
        start_expr = f"({clock_number(clip_start)}+{clock_number(delay)})"
        end_expr = f"({clock_number(clip_start)}+{clock_number(delay + animation_duration)})"
        progress = f"clip((({time_expression})-{start_expr})/{clock_number(animation_duration)},0,1)"
        if animation_type in {"fade_in", "fade"}:
            add_alpha(f'if(lt(({time_expression}),{start_expr}),0,{progress})')
        elif animation_type == "fade_out":
            fade_start = clip_start + max(0.0, clip_duration - animation_duration)
            add_alpha(f'if(gt(({time_expression}),{clock_number(fade_start)}),clip(({clock_number(clip_start + clip_duration)}-({time_expression}))/{clock_number(animation_duration)},0,1),1)')
        elif animation_type in {"slide_up", "slide_down", "slide_left", "slide_right"}:
            distance = max(0.0, _num(animation.get("distance", 80), 80))
            if animation_type == "slide_up":
                y_expr = f"({base_y})+((1-({progress}))*{distance:.4f})"
                parts.append(f"y={_expr_arg(y_expr)}")
            elif animation_type == "slide_down":
                y_expr = f"({base_y})-((1-({progress}))*{distance:.4f})"
                parts.append(f"y={_expr_arg(y_expr)}")
            elif animation_type == "slide_left":
                x_expr = f"({base_x})+((1-({progress}))*{distance:.4f})"
                parts.append(f"x={_expr_arg(x_expr)}")
            else:
                x_expr = f"({base_x})-((1-({progress}))*{distance:.4f})"
                parts.append(f"x={_expr_arg(x_expr)}")
        elif animation_type in {"typewriter", "typing"}:
            if dynamic_raster:
                warnings.append({'code': 'RENDER_FEATURE_APPROXIMATE', 'clip_id': clip_id,
                                 'feature': 'subtitle_typewriter_dynamic_raster',
                                 'message': '动态尺寸内嵌打字机沿用旧定位；请使用独立字幕层'})
                if word_timing:
                    warnings.append({'code': 'RENDER_FEATURE_UNSUPPORTED', 'clip_id': clip_id,
                                     'feature': 'subtitle_word_animation',
                                     'message': '动态尺寸内嵌打字机与高亮尚未联合实现，保留整句'})
                else:
                    chars = [item[2] for item in graphemes(subtitle_text) if item[2] != "\n"]
                    if not chars:
                        return None
                    char_step = animation_duration / max(1, len(chars))
                    char_filters: list[str] = []
                    prefix_text = ""
                    for index, char in enumerate(chars):
                        char_parts = [f"drawtext=text='{_drawtext_arg(char)}'", *parts[1:]]
                        char_parts = [part for part in char_parts if not part.startswith("enable=")]
                        prefix_width = _subtitle_text_width(font_metrics, prefix_text, font_size)
                        x_expr = f"({base_x})+({prefix_width:.6f})"
                        char_parts.append(f"x={_expr_arg(x_expr)}")
                        char_parts.append(f"y={_expr_arg(base_y)}")
                        enable_expr = f"gte(({time_expression}),{clip_start + delay + index * char_step:.9f})"
                        if timeline_window:
                            enable_expr = f"({enable_expr})*({window_expression})"
                        char_parts.append(f"enable={_expr_arg(enable_expr)}")
                        if style.get("box", True):
                            char_parts.extend(["box=1", f"boxcolor={_quoted(style.get('boxcolor', 'black@0.45'))}", f"boxborderw={box_border}"])
                        char_filters.append(draw(char_parts))
                        prefix_text += char
                    return ",".join(char_filters)
            else:
                if resolved_font_path is None:
                    raise AppError('SUBTITLE_TYPEWRITER_FONT_REQUIRED', '原生打字机需要可用的本地字体', exit_code=2)
                from .text_typing import TypingParagraph
                typing_plan = TypingParagraph(root,
                    build_text_layout(source_subtitle_text, style, font_metrics, font_size),
                    style, resolved_font_path, font_size, render_clock or {}, final_fps, frame_origin,
                    clip_start, animation_duration, delay, clip_id, time_expression,
                    snapshot=float_paint)
        elif animation_type == "pop":
            distance = max(0.0, _num(animation.get("distance", 40), 40))
            add_alpha(f'if(lt(({time_expression}),{start_expr}),0,{progress})')
            parts.append(f"y={_expr_arg(f'({base_y})+((1-({progress}))*{distance:.4f})')}")
        elif animation_type == "bounce":
            distance = max(0.0, _num(animation.get("distance", 36), 36))
            bounce_expr = f"({base_y})-abs(sin((({time_expression})-{start_expr})*PI*2))*{distance:.4f}*({progress})"
            parts.append(f"y={_expr_arg(bounce_expr)}")
        elif animation_type == "rotate":
            add_alpha(f'if(lt(({time_expression}),{start_expr}),0,{progress})')
            if not rotation_supported:
                warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "subtitle_animation:rotate", "message": "片段内字幕仍使用淡入近似；独立字幕轨道支持透明文字层旋转"})
        else:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": clip_id, "feature": f"subtitle_animation:{animation_type}", "message": "未知字幕动画类型"})
    base_x = next((option[3:-1] for option in parts if option.startswith("x='")), base_x)
    base_y = next((option[3:-1] for option in parts if option.startswith("y='")), base_y)
    if word_timing:
        entries: list[tuple[str, float, float, int]] = []
        tick_base = max(1, int(_num(subtitle.get("ticks_per_second", 90000), 90000)))
        resolved_words: dict[int, tuple[int, int]] = {}
        if isinstance(word_timing, list):
            try:
                resolved_words = {
                    id(item): (start, end)
                    for item, start, end in word_ranges(source_subtitle_text, [item for item in word_timing if isinstance(item, dict)])
                }
            except ValueError as exc:
                raise AppError("SUBTITLE_WORD_TIMING_TEXT_MISMATCH", str(exc), exit_code=2, path=f"clips[{clip_id}].subtitle.word_timing") from exc
            for word_index, item in enumerate(word_timing):
                if not isinstance(item, dict):
                    continue
                word = str(item.get("text", item.get("word", "")))
                start_value = item.get("start", item.get("start_seconds"))
                end_value = item.get("end", item.get("end_seconds"))
                if start_value is None and item.get("start_tick") is not None:
                    start_value = _num(item.get("start_tick"), 0) / tick_base
                if end_value is None and item.get("end_tick") is not None:
                    end_value = _num(item.get("end_tick"), 0) / tick_base
                try:
                    start_value = float(start_value)
                    end_value = float(end_value)
                except (TypeError, ValueError):
                    continue
                if word and 0 <= start_value < end_value:
                    entries.append((word, start_value, end_value, word_index))
        if not entries:
            warnings.append({"code": "SUBTITLE_WORD_TIMING_INVALID", "clip_id": clip_id, "message": "word_timing 没有可执行的正时间范围，已回退为整句字幕"})
        else:
            base_parts = list(parts)
            if not any(part.startswith("x=") for part in base_parts):
                base_parts.append(f"x={_expr_arg(base_x)}")
            if not any(part.startswith("y=") for part in base_parts):
                base_parts.append(f"y={_expr_arg(base_y)}")
            if style.get("box", True):
                base_parts.extend(["box=1", f"boxcolor={_quoted(style.get('boxcolor', 'black@0.45'))}", f"boxborderw={box_border}"])
            if dynamic_raster:
                warnings.append({'code': 'RENDER_FEATURE_UNSUPPORTED', 'clip_id': clip_id,
                                 'feature': 'subtitle_word_dynamic_raster',
                                 'message': '动态尺寸内嵌逐字高亮尚不支持，保留整句；请使用独立字幕层'})
                if '\n' in subtitle_text and resolved_font_path is not None:
                    from .text_highlight import multiline_filter
                    return multiline_filter(root, resolved_font_path, font_size,
                                            build_text_layout(source_subtitle_text, style, font_metrics, font_size),
                                            style, base_parts, base_x, base_y, paint_text)[0]
                return draw(base_parts)
            if resolved_font_path is None:
                raise AppError('SUBTITLE_WORD_FONT_REQUIRED', '逐字高亮需要明确的本地字体文件', exit_code=2)
            if int(style.get('line_spacing', 0)) < 0:
                warnings.append({'code': 'RENDER_FEATURE_APPROXIMATE', 'clip_id': clip_id,
                                 'feature': 'subtitle_word_overlapping_lines',
                                 'message': '负行距可能使相邻行笔画重叠，逐字颜色需目检'})
            from .text_highlight import highlight_filter
            active_color = _quoted(style.get('active_color', style.get('highlight_color', 'yellow')))
            active_parts = [f'fontcolor={active_color}' if part.startswith('fontcolor=') else part for part in base_parts]
            timed = {id(word_timing[index]): (start, end) for _, start, end, index in entries}
            selected_ranges = [(item, *resolved_words[id(item)]) for item in word_timing if isinstance(item, dict) and id(item) in timed]
            value, evidence = highlight_filter(
                root, resolved_font_path, font_size,
                build_text_layout(source_subtitle_text, style, font_metrics, font_size), style,
                selected_ranges, timed, base_parts, active_parts,
                base_x, base_y, time_expression, clip_start, clip_id,
                window_expression if timeline_window else None,
                paint_text, typing_plan,
                float_paint=float_paint,
            )
            return finish(value, evidence)
    if not any(part.startswith("x=") for part in parts):
        parts.append(f"x={_expr_arg(base_x)}")
    if not any(part.startswith("y=") for part in parts):
        parts.append(f"y={_expr_arg(base_y)}")
    if style.get("box", True):
        parts.extend(["box=1", f"boxcolor={_quoted(style.get('boxcolor', 'black@0.45'))}", f"boxborderw={box_border}"])
    if ('\n' in subtitle_text or typing_plan is not None) and resolved_font_path is not None:
        from .text_highlight import multiline_filter
        x = next(part[3:-1] for part in parts if part.startswith("x='"))
        y = next(part[3:-1] for part in parts if part.startswith("y='"))
        value, evidence = multiline_filter(root, resolved_font_path, font_size,
                                            build_text_layout(source_subtitle_text, style, font_metrics, font_size),
                                            style, parts, x, y, paint_text, typing_plan)
        return finish(value, evidence)
    return finish(draw(parts))


def _compiled_subtitle_filter(
    root: Path, subtitle: Any, warnings: list[dict[str, Any]], clip: dict[str, Any],
    start: float, duration: float, tps: int, fps_value: str,
    assets: dict[str, dict[str, Any]], *, independent: bool = False, dynamic_raster: bool = False,
) -> tuple[str | None, dict[str, Any]]:
    """Paint at authoring time while keeping the final frame clock intact."""
    clock = _subtitle_clock_for_clip(clip, start, duration)
    if not isinstance(subtitle, dict):
        return None, clock
    time_base = subtitle.get('asset_time_base', 'sequence')
    if not isinstance(time_base, str) or time_base not in {'sequence', 'clip'}:
        raise AppError('SUBTITLE_ASSET_TIME_BASE_INVALID', 'asset_time_base 只支持 sequence 或 clip', exit_code=2)
    author_start = clock['authored_start_seconds']
    author_duration = clock['authored_duration_seconds']
    isolated_raster = independent or not dynamic_raster
    external = bool(subtitle.get('asset_uri'))
    cue_offset = subtitle.get('asset_time_offset_tick', 0)
    if type(cue_offset) is not int:
        raise AppError('SUBTITLE_ASSET_OFFSET_INVALID', '文件字幕时钟偏移必须为整数 tick', exit_code=2)
    cue_offset_seconds = cue_offset / tps
    straight_paint = isolated_raster and not external
    animation_alpha: list[str] = []
    layout_evidence: dict[str, Any] = {}
    paint_records: list[dict[str, Any]] = []
    command_targets: dict[str, list[str]] = {}
    def paint_text(parts: list[str]) -> str:
        from .text_paint import paint_drawtext
        result, evidence = paint_drawtext(root, parts, f'{clip.get("id")}-{len(paint_records)}')
        paint_records.append(evidence)
        command_targets.update(evidence.get('command_targets', {}))
        return result
    value = _subtitle_filter(
        root, subtitle, warnings, str(clip.get('id')), author_start, author_duration,
        timeline_window=independent, rotation_supported=independent, assets=assets,
        time_expression=_subtitle_authored_expression(clock), visible_window=(start, duration),
        animation_alpha=animation_alpha,
        layout_evidence=layout_evidence, dynamic_raster=dynamic_raster and not independent,
        paint_text=paint_text if straight_paint else None,
        command_targets=command_targets, render_clock=clock, final_fps=fps_value,
        frame_origin=0. if independent else start,
    )
    if value and animation_alpha and dynamic_raster and not independent:
        # FFmpeg's implicit format converters pin the first geometry in a
        # branched raster; changing clip dimensions can fail or crash it.
        # Retain the executable legacy drawtext path and disclose its opacity.
        value = _subtitle_filter(
            root, subtitle, warnings, str(clip.get('id')), author_start, author_duration,
            assets=assets, time_expression=_subtitle_authored_expression(clock),
            dynamic_raster=True,
        )
        warnings.append({'code': 'RENDER_FEATURE_APPROXIMATE', 'clip_id': clip.get('id'),
                         'feature': 'subtitle_inline_dynamic_alpha',
                         'message': '动态尺寸片段的嵌入文字保留原作者时钟，但透明度仍为原生 drawtext 近似；需使用独立字幕层并单独验收'})
        animation_alpha = []
    if value and external:
        relative = time_base == 'clip'
        if clock['maps'] or relative or cue_offset:
            paint_time = _subtitle_authored_expression(clock, 'PTS*TB', sequential=True)
            if relative:
                paint_time = f'(({paint_time})-{author_start:.14g})'
            if cue_offset:
                paint_time = f'(({paint_time})+({cue_offset_seconds:.14g}))'
            if independent:
                # The title source covers the whole final timeline from 0.
                # Rebuild that untouched CFR counter outside the visible clip
                # too, where an ancestor inverse deliberately clamps time.
                restore = f'N/({fps_value})/TB'
            else:
                restore_clock = f'(PTS*TB-({cue_offset_seconds:.14g}))' if cue_offset else 'PTS*TB'
                restored = _subtitle_restore_expression(clock, restore_clock, clip_relative=relative)
                restore = f'round(({restored})/TB)'
            value = (f'settb=expr=1/900000000,setpts={_expr_arg(f"({paint_time})/TB")},'
                     + value + f',setpts={_expr_arg(restore)},settb=expr=1/({fps_value})')
        if independent:
            window = f'gte(T,{start:.9f})*lt(T,{start + duration:.9f})'
            value += (",format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a="
                      + _expr_arg(f'alpha(X,Y)*({window})') + ',format=rgba')
    if value and isolated_raster:
        if not straight_paint:
            value += ',format=gbrapf32le,unpremultiply=inplace=1,format=rgba'
        if animation_alpha:
            opacity = '*'.join(f'({expression})' for expression in animation_alpha)
            value += (",format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a="
                      + _expr_arg('alpha(X,Y)*(' + re.sub(r'\bt\b', 'T', opacity) + ')') + ',format=rgba')
    if value and not independent and isolated_raster:
        # Paint onto a separate transparent raster. drawtext/libass alpha on
        # an existing RGBA image otherwise modifies the base alpha too; a
        # subsequent compositor can darken even an originally opaque clip.
        token = hashlib.sha256(str(clip.get('id')).encode('utf-8')).hexdigest()[:16]
        base, paint, layer = (f'caption_{token}_{name}' for name in ('base', 'paint', 'layer'))
        value = (f'split=2[{base}][{paint}];[{paint}]format=rgba,'
                 + 'lutrgb=r=0:g=0:b=0:a=0,' + value
                 + f'[{layer}];'
                 + f'[{base}][{layer}]overlay=x=0:y=0:format=auto:shortest=1')
    clock = {**clock, 'asset_time_base': time_base if external else 'clip-local-inline',
             'asset_time_offset_tick': cue_offset if external else 0,
             'engine': 'libass' if external else layout_evidence.get('engine', 'drawtext'),
             'frame_clock': 'restored-to-final-display-grid' if external else 'unchanged',
             'continuous_playback_reviewed': False}
    if layout_evidence:
        clock['text_layout'] = layout_evidence
    if value and straight_paint:
        clock['text_paint'] = {'engine': 'straight-component-source-over', 'paints': paint_records,
                               'working_color': 'encoded-rgb-8bit', 'linear_light_accepted': False}
    elif value and not external and not isolated_raster:
        clock['text_paint'] = {'engine': 'legacy-dynamic-inline-drawtext', 'color_alpha_accepted': False}
        warnings.append({'code': 'RENDER_FEATURE_APPROXIMATE', 'clip_id': clip.get('id'),
                         'feature': 'subtitle_inline_dynamic_color',
                         'message': '动态尺寸内嵌文字沿用原生 drawtext 颜色混合；颜色/透明度组合未验收，请使用独立文字层'})
    if value and clock.get('freeze_semantics_approximate'):
        warnings.append({'code': 'RENDER_FEATURE_APPROXIMATE', 'clip_id': clip.get('id'),
                         'feature': 'subtitle_freeze_clock',
                         'message': '字幕已使用原作者时钟；定格暂停区间尚未精确联合映射，不能据此接受定格字幕对应'})
    return value, clock


def _flatten_sequence_tracks(
    project: dict[str, Any], sequence: dict[str, Any], warnings: list[dict[str, Any]],
    *, groups: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Flatten nested sequence clips into renderable asset clips.

    Nested sequences remain first-class in the project model, while FFmpeg
    receives a single filter graph. Nonlinear clocks keep a composed analytic
    map through source trimming, video PTS and authored keyframe evaluation.
    With ``groups`` the production renderer keeps spatial operations on an
    isolated transparent sequence canvas. Without it, the legacy temporal
    diagnostic view distributes parent properties. Direct parent
    transform keyframes are projected onto the final sequence clock so an
    animation keeps one phase across adjacent child clips and multiple parent
    layers compose in one expression; reverse interpolation and multiple masks
    in different coordinate spaces remain explicit approximation warnings.
    """
    sequences = {str(item.get("id")): item for item in project.get("sequences", []) if item.get("id")}
    inline_asset_ids = {a['id'] for a in project.get('assets', []) if a.get('_inline_video')}
    inline_audio_asset_ids = {a['id'] for a in project.get('assets', []) if a.get('_inline_audio')}
    collected: dict[tuple[str, str], dict[str, Any]] = {}

    def transform_values(raw: Any) -> dict[str, float]:
        value = raw if isinstance(raw, dict) else {}
        position = value.get("position") if isinstance(value.get("position"), dict) else {}
        anchor = value.get("anchor") if isinstance(value.get("anchor"), dict) else {}
        return {
            "x": _num(position.get("x", value.get("position_x", 0.5)), 0.5),
            "y": _num(position.get("y", value.get("position_y", 0.5)), 0.5),
            "scale": _num(value.get("scale", 1.0), 1.0),
            "rotation": _num(value.get("rotation", 0.0), 0.0),
            "opacity": _num(value.get("opacity", 1.0), 1.0),
            "anchor_x": _num(anchor.get("x", value.get("anchor_x", 0.5)), 0.5),
            "anchor_y": _num(anchor.get("y", value.get("anchor_y", 0.5)), 0.5),
        }

    def combine_transforms(parent: Any, child: Any) -> dict[str, Any] | None:
        if not isinstance(parent, dict) and not isinstance(child, dict):
            return None
        outer = transform_values(parent)
        inner = transform_values(child)
        offset_x = (inner["x"] - 0.5) * outer["scale"]
        offset_y = (inner["y"] - 0.5) * outer["scale"]
        angle = math.radians(outer["rotation"])
        rotated_x = offset_x * math.cos(angle) - offset_y * math.sin(angle)
        rotated_y = offset_x * math.sin(angle) + offset_y * math.cos(angle)
        return {
            "position": {
                "x": outer["x"] + rotated_x,
                "y": outer["y"] + rotated_y,
            },
            "scale": outer["scale"] * inner["scale"],
            "rotation": outer["rotation"] + inner["rotation"],
            "opacity": max(0.0, min(1.0, outer["opacity"] * inner["opacity"])),
            # Anchor is a leaf-layer placement reference. Parent pivot
            # composition remains explicit in the capability limitations.
            "anchor": {"x": inner["anchor_x"], "y": inner["anchor_y"]},
        }

    def transform_keyframe_tracks(clip: dict[str, Any]) -> list[dict[str, Any]]:
        supported = {
            "transform.position.x", "position.x", "position_x",
            "transform.position.y", "position.y", "position_y",
            "transform.scale", "scale", "transform.rotation", "rotation",
            "transform.opacity", "opacity", "transform.anchor.x", "anchor.x", "anchor_x",
            "transform.anchor.y", "anchor.y", "anchor_y",
        }
        return [
            copy.deepcopy(item)
            for item in clip.get("keyframes", [])
            if isinstance(item, dict) and str(item.get("property", "")) in supported and isinstance(item.get("keyframes"), list)
        ]

    def context_for(parent: dict[str, Any], clip: dict[str, Any]) -> dict[str, Any]:
        clip_transform = clip.get("transform") if isinstance(clip.get("transform"), dict) else None
        clip_effects = clip.get("effects") if isinstance(clip.get("effects"), list) else []
        clip_mask = clip.get("mask") if isinstance(clip.get("mask"), dict) else None
        clip_blend = clip.get("blend") if isinstance(clip.get("blend"), dict) else None
        clip_transform_tracks = transform_keyframe_tracks(clip)
        inherited_layers = parent.get("dynamic_layers") if isinstance(parent.get("dynamic_layers"), list) else []
        parent_transform = parent.get("transform") if isinstance(parent.get("transform"), dict) else None
        parent_anchor = parent_transform.get("anchor") if isinstance(parent_transform, dict) and isinstance(parent_transform.get("anchor"), dict) else {}
        parent_anchor_x = _num(parent_anchor.get("x", parent_transform.get("anchor_x", 0.5) if isinstance(parent_transform, dict) else 0.5), 0.5)
        parent_anchor_y = _num(parent_anchor.get("y", parent_transform.get("anchor_y", 0.5) if isinstance(parent_transform, dict) else 0.5), 0.5)
        if abs(parent_anchor_x - 0.5) > 1e-9 or abs(parent_anchor_y - 0.5) > 1e-9:
            warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "nested_sequence_parent_anchor", "message": "嵌套序列父级 anchor 目前按叶片放置参考点近似，父级枢轴不会改变子层旋转中心"})
        if not inherited_layers and parent.get("dynamic_transform") and isinstance(parent.get("transform"), dict):
            inherited_layers = [{"transform": copy.deepcopy(parent["transform"]), "tracks": copy.deepcopy(parent.get("transform_keyframes", [])), "clock": "global"}]
        has_clip_transform = isinstance(clip_transform, dict) and bool(clip_transform)
        dynamic_transform = bool(inherited_layers or clip_transform_tracks)
        if dynamic_transform:
            dynamic_layers = copy.deepcopy(inherited_layers)
            if has_clip_transform or clip_transform_tracks:
                dynamic_layers.append({"transform": copy.deepcopy(clip_transform) if isinstance(clip_transform, dict) else {}, "tracks": clip_transform_tracks, "clock": "local"})
            combined_transform = copy.deepcopy(clip_transform) if isinstance(clip_transform, dict) else {}
        else:
            combined_transform = combine_transforms(parent.get("transform"), clip_transform)
            dynamic_layers = []
        inherited_masks = parent.get("masks") if isinstance(parent.get("masks"), list) else []
        if not inherited_masks and isinstance(parent.get("mask"), dict):
            inherited_masks = [parent.get("mask")]
        masks = [*copy.deepcopy(inherited_masks)]
        if clip_mask is not None:
            masks.append(copy.deepcopy(clip_mask))
        if len(masks) > 1:
            warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "nested_sequence_multiple_masks", "message": "嵌套序列父子 mask 将按顺序合成 alpha，坐标空间差异保留近似边界"})
        if parent.get("blend") is not None and clip_blend is not None:
            warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "nested_sequence_multiple_blends", "message": "嵌套序列父子同时设置 blend 时采用内层 blend"})
        return {
            "transform": combined_transform,
            "dynamic_transform": dynamic_transform,
            "dynamic_layers": dynamic_layers,
            "transform_keyframes": clip_transform_tracks if dynamic_transform else [],
            "keyframe_duration_tick": max(1, int(clip.get("duration_tick", 1))),
            "effects": [*parent.get("effects", []), *copy.deepcopy(clip_effects)],
            "masks": masks,
            "mask": copy.deepcopy(masks[-1]) if masks else None,
            "blend": copy.deepcopy(clip_blend if clip_blend is not None else parent.get("blend")),
        }

    def apply_context(clip: dict[str, Any], context: dict[str, Any]) -> None:
        dynamic_layers = context.get("dynamic_layers") if isinstance(context.get("dynamic_layers"), list) else []
        if context.get("dynamic_transform") and dynamic_layers:
            clip["_nested_parent_transforms"] = copy.deepcopy(dynamic_layers)
            if len(dynamic_layers) == 1 and isinstance(dynamic_layers[0], dict):
                layer_transform = dynamic_layers[0].get("transform") if isinstance(dynamic_layers[0].get("transform"), dict) else dynamic_layers[0]
                clip["_nested_parent_transform"] = copy.deepcopy(layer_transform)
            child_duration = max(1, int(clip.get("duration_tick", 1)))
            inherited_tracks: list[dict[str, Any]] = []
            layer_count = len(dynamic_layers)
            for layer_index, layer in enumerate(dynamic_layers):
                tracks = layer.get("tracks", []) if isinstance(layer, dict) else []
                prefix = "nested.parent.transform" if layer_count == 1 else f"nested.parent.{layer_index}.transform"
                for track in tracks:
                    property_name = str(track.get("property", ""))
                    if property_name.startswith("transform."):
                        property_name = f"{prefix}.{property_name[len('transform.') :]}"
                    elif property_name in {"position.x", "position.y", "position_x", "position_y", "scale", "rotation", "opacity", "anchor.x", "anchor.y", "anchor_x", "anchor_y"}:
                        property_name = f"{prefix}.{property_name}"
                    else:
                        continue
                    mapped_track = {**copy.deepcopy(track), "property": property_name, "keyframes": []}
                    for keyframe in track.get("keyframes", []):
                        if not isinstance(keyframe, dict):
                            continue
                        mapped = copy.deepcopy(keyframe)
                        raw_at = _num(keyframe.get("at_tick", 0), 0)
                        if context.get("keyframes_are_global"):
                            # Keep values before the child start. The shared
                            # evaluator uses them to calculate the parent's
                            # interpolated value at this child boundary instead
                            # of resetting every child to the first keyframe.
                            mapped["at_tick"] = int(round(raw_at - _num(clip.get("timeline_start_tick", 0), 0)))
                        else:
                            parent_duration = max(1, int(context.get("keyframe_duration_tick", 1)))
                            mapped["at_tick"] = int(round(raw_at / parent_duration * child_duration))
                        mapped_track["keyframes"].append(mapped)
                    if mapped_track["keyframes"]:
                        inherited_tracks.append(mapped_track)
            if inherited_tracks:
                clip["keyframes"] = [*copy.deepcopy(clip.get("keyframes", [])), *inherited_tracks]
        elif context.get("transform") is not None:
            clip["transform"] = combine_transforms(context.get("transform"), clip.get("transform"))
        inherited_effects = context.get("effects") if isinstance(context.get("effects"), list) else []
        if inherited_effects:
            child_effects = clip.get("effects") if isinstance(clip.get("effects"), list) else []
            clip["effects"] = [*copy.deepcopy(inherited_effects), *copy.deepcopy(child_effects)]
        inherited_masks = context.get("masks") if isinstance(context.get("masks"), list) else []
        if inherited_masks:
            if isinstance(clip.get("mask"), dict):
                warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "nested_sequence_multiple_masks", "message": "嵌套序列父子 mask 将按顺序合成 alpha，坐标空间差异保留近似边界"})
            clip["_nested_parent_masks"] = copy.deepcopy(inherited_masks)
        if context.get("blend") is not None and not isinstance(clip.get("blend"), dict):
            clip["blend"] = copy.deepcopy(context["blend"])

    def visit(
        current: dict[str, Any],
        origin_tick: int,
        scale: float,
        source_window: tuple[int, int],
        prefix: str,
        stack: tuple[str, ...],
        inherited: dict[str, Any] | None = None,
        reverse_time: bool = False,
        time_mapper: Callable[[float], float] | None = None,
        clock_maps: list[dict[str, Any]] | None = None,
        group_id: str | None = None,
        audio_enabled: bool = True,
        video_enabled: bool = True,
    ) -> None:
        current_id = str(current.get("id"))
        if current_id in stack:
            raise AppError("SEQUENCE_CYCLE", "嵌套序列存在循环引用，拒绝渲染", exit_code=2, path="sequences")
        next_stack = stack + (current_id,)
        window_start, window_end = source_window
        clock_maps = clock_maps or []
        tps_local = int(project.get('settings', {}).get('timebase', {}).get('ticks_per_second', 90000))
        if video_enabled and current.get('_inline_video_asset_id'):
            reserved = set(sequences) | set(stack)
            reserved.update(str(t.get('id')) for t in current.get('tracks', []))
            reserved.update(str(c.get('id')) for t in current.get('tracks', []) for c in t.get('clips', []))
            def internal_id(base):
                while base in reserved:
                    base += '_'
                reserved.add(base)
                return base
            surface = {'id': internal_id(current_id+'__surface'), 'duration_tick':current['duration_tick'], 'tracks':[
                {'id':internal_id('__surface_video'),'kind':'video','order':0,'clips':[
                    {'id':internal_id('__surface_picture'),'asset_id':current['_inline_video_asset_id'],
                     'timeline_start_tick':0,'duration_tick':current['duration_tick'],
                     'source_in_tick':0,'source_out_tick':current['duration_tick']}]}]}
            visit(surface, origin_tick, scale, source_window, prefix, stack, inherited,
                  reverse_time, time_mapper, clock_maps, group_id, False, True)
            video_enabled = False

        def current_to_final(tick: float) -> float:
            if clock_maps:
                return _clock_time(clock_maps, tick / tps_local) * tps_local
            if time_mapper is not None:
                return float(time_mapper(float(tick)))
            if reverse_time:
                return float(origin_tick + (window_end - tick) * scale)
            return float(origin_tick + (tick - window_start) * scale)

        # Solo belongs to the authored sequence, not to every flattened audio
        # track in the project. A nested solo must not silence root siblings.
        local_solo = {str(t.get('id')) for t in current.get('tracks', [])
                      if t.get('kind') == 'audio' and isinstance(t.get('audio'), dict) and t['audio'].get('solo')}
        for track in sorted(current.get("tracks", []), key=lambda item: int(item.get("order", 0))):
            if track.get("muted"):
                continue
            kind = str(track.get("kind", "video"))
            track_audio = track.get('audio') if isinstance(track.get('audio'), dict) else {}
            track_audio_enabled = audio_enabled and not (track_audio.get('mute') or track_audio.get('muted'))
            if kind == 'audio' and local_solo and str(track.get('id')) not in local_solo:
                track_audio_enabled = False
            virtual_id = f"{prefix}{track.get('id', 'track')}"
            key = (kind, virtual_id)
            output_track = collected.setdefault(
                key,
                {
                    "id": virtual_id,
                    "kind": kind,
                    "order": int(track.get("order", 0)),
                    "muted": False,
                    "locked": False,
                    "overlap_policy": track.get("overlap_policy"),
                    "role": track.get("role"),
                    "duck_under_voice": track.get("duck_under_voice"),
                    "audio": copy.deepcopy(track.get("audio")) if isinstance(track.get("audio"), dict) else {},
                    "clips": [],
                },
            )
            for clip in sorted(track.get("clips", []), key=lambda item: int(item.get("timeline_start_tick", 0))):
                if not video_enabled and kind != 'audio' and not clip.get('sequence_id'):
                    continue
                clip_start = int(clip.get("timeline_start_tick", 0))
                clip_end = clip_start + int(clip.get("duration_tick", 0))
                overlap_start = max(clip_start, window_start)
                overlap_end = min(clip_end, window_end)
                if overlap_end <= overlap_start:
                    continue
                if clip.get('speed_curve'):
                    compiled = _speed_curve_segments(clip, max(1, int(clip.get('source_out_tick', 1))-int(clip.get('source_in_tick', 0))), tps_local)
                    certificate = getattr(compiled, 'certificate', {})
                    if certificate.get('adaptive'):
                        warnings.append({'code': 'SPEED_CURVE_COMPILED', 'clip_id': clip.get('id'),
                                         'feature': 'speed_curve_easing', 'certificate': copy.deepcopy(certificate),
                                         'message': '速度 easing/Bezier 已按有界源时钟编译；未退回端点线性曲线'})
                mapped_left = current_to_final(overlap_start)
                mapped_right = current_to_final(overlap_end)
                mapped_start = int(round(min(mapped_left, mapped_right)))
                mapped_duration = max(1, int(round(abs(mapped_right - mapped_left))))
                if clip.get("sequence_id"):
                    if clip.get('freeze'):
                        warnings.append({'code': 'RENDER_FEATURE_APPROXIMATE', 'clip_id': clip.get('id'),
                                         'feature': 'nested_sequence_freeze_clock',
                                         'message': '嵌套容器定格尚无精确联合时钟；不能据此接受其视频、动画或音频对应'})
                    child = sequences.get(str(clip.get("sequence_id")))
                    if child is None:
                        raise AppError("SEQUENCE_REFERENCE_MISSING", f"找不到嵌套序列: {clip.get('sequence_id')}", exit_code=2, path=f"clip[{clip.get('id')}].sequence_id")
                    source_base = int(clip.get("source_in_tick", 0))
                    source_limit = int(clip.get("source_out_tick", source_base + int(child.get("duration_tick", 1))))
                    source_limit = max(source_base + 1, source_limit)
                    effective_reverse = bool(reverse_time) ^ bool(clip.get("reverse"))
                    source_span_tick = max(1, source_limit - source_base)
                    speed_segments = _speed_curve_segments(clip, source_span_tick, int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90000)))
                    clip_clock = _make_clock_map(clip, speed_segments, tps_local)
                    if clip.get('freeze'):
                        clip_clock['freeze_semantics_approximate'] = True
                    source_bounds = [
                        _unmap_clock_time(clip_clock, overlap_start / tps_local),
                        _unmap_clock_time(clip_clock, overlap_end / tps_local),
                    ]
                    child_source_in = int(round(min(source_bounds) * tps_local))
                    child_source_out = int(round(max(source_bounds) * tps_local))

                    def child_to_final(child_tick: float) -> float:
                        return _clock_time([clip_clock, *clock_maps], child_tick / tps_local) * tps_local

                    child_source_in = max(source_base, min(source_limit - 1, child_source_in))
                    child_source_out = max(child_source_in + 1, min(source_limit, child_source_out))
                    child_group_id = group_id
                    if groups is not None:
                        child_group_id = f"{prefix}{clip.get('id')}"
                        group_clip = copy.deepcopy(clip)
                        group_clip['id'] = child_group_id
                        group_clip['_composite_authored_duration_tick'] = int(clip.get('duration_tick', 1))
                        group_clip['timeline_start_tick'] = mapped_start
                        group_clip['duration_tick'] = mapped_duration
                        # Container animation belongs to the containing
                        # sequence, not to its own retimed source sequence.
                        group_clip['_nested_keyframe_clock'] = {
                            'maps': copy.deepcopy(clock_maps), 'authored_start': clip_start / tps_local,
                        }
                        if child_group_id in groups:
                            # Piecewise temporal windows can visit the same
                            # authored container more than once. Composite its
                            # spatial state once over the union of those spans.
                            previous = groups[child_group_id]['clip']
                            left = min(previous['timeline_start_tick'], mapped_start)
                            right = max(previous['timeline_start_tick'] + previous['duration_tick'], mapped_start + mapped_duration)
                            previous['timeline_start_tick'], previous['duration_tick'] = left, right-left
                        else:
                            groups[child_group_id] = {
                                'id': child_group_id, 'parent_id': group_id,
                                'track_id': virtual_id, 'track_order': int(track.get('order', 0)),
                                'layer_order': len(groups), 'clip': group_clip,
                                'canvas': sequence_canvas(project, child),
                                'parent_canvas': sequence_canvas(project, current),
                                'video_enabled': video_enabled,
                            }
                        parent_context = {}
                    else:
                        parent_context = context_for(inherited or {"transform": None, "effects": [], "masks": [], "mask": None, "blend": None}, clip)
                    if parent_context.get("dynamic_transform"):
                        # Parent keyframes live in the current sequence clock.
                        # Convert each newly-created local layer once to the
                        # final timeline clock before visiting children;
                        # inherited layers are already global and must not be
                        # remapped at every nesting level.
                        global_layers: list[dict[str, Any]] = []
                        for layer in parent_context.get("dynamic_layers", []):
                            mapped_layer = copy.deepcopy(layer)
                            if str(mapped_layer.get("clock", "local")) == "local":
                                global_tracks: list[dict[str, Any]] = []
                                for track_value in mapped_layer.get("tracks", []):
                                    mapped_track = copy.deepcopy(track_value)
                                    mapped_track["keyframes"] = []
                                    if speed_segments or any(item['segments'] for item in clock_maps):
                                        mapped_track['_nested_clock'] = {
                                            'maps': copy.deepcopy(clock_maps),
                                            'authored_start': clip_start / tps_local,
                                            'keyframes': copy.deepcopy(track_value.get('keyframes', [])),
                                        }
                                    for keyframe in track_value.get("keyframes", []):
                                        if not isinstance(keyframe, dict):
                                            continue
                                        mapped = copy.deepcopy(keyframe)
                                        local_at = _num(keyframe.get("at_tick", 0), 0)
                                        if effective_reverse:
                                            local_at = int(clip.get("duration_tick", 1)) - local_at
                                            _reverse_keyframe_controls(mapped)
                                        if time_mapper is not None:
                                            mapped["at_tick"] = int(round(current_to_final(clip_start + local_at)))
                                        else:
                                            mapped["at_tick"] = int(round(
                                                origin_tick + ((clip_start + local_at - window_start) * scale)
                                            ))
                                        mapped_track["keyframes"].append(mapped)
                                    if mapped_track["keyframes"]:
                                        global_tracks.append(mapped_track)
                                mapped_layer["tracks"] = global_tracks
                                mapped_layer["clock"] = "global"
                            global_layers.append(mapped_layer)
                        parent_context["dynamic_layers"] = global_layers
                        parent_context["keyframes_are_global"] = True
                    child_windows: list[tuple[int, int]] = [(child_source_in, child_source_out)]
                    complete_surface = any(c.get('asset_id') in inline_audio_asset_ids
                        for t in child.get('tracks', []) for c in t.get('clips', []))
                    if speed_segments and not getattr(speed_segments, 'certificate', {}).get('adaptive') and not complete_surface:
                        tps_local = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90000))
                        split_windows: list[tuple[int, int]] = []
                        for segment_start, segment_end, _, _ in speed_segments:
                            segment_source_start = source_base + int(round(segment_start * tps_local))
                            segment_source_end = source_base + int(round(segment_end * tps_local))
                            part_start = max(child_source_in, segment_source_start)
                            part_end = min(child_source_out, segment_source_end)
                            if part_end > part_start:
                                split_windows.append((part_start, part_end))
                        if split_windows:
                            child_windows = split_windows
                    for child_window in child_windows:
                        clip_audio = clip.get('audio') if isinstance(clip.get('audio'), dict) else {}
                        visit(
                            child,
                            0,
                            1.0,
                            child_window,
                            f"{prefix}{clip.get('id')}.",
                            next_stack,
                            parent_context,
                            effective_reverse,
                            child_to_final,
                            [clip_clock, *clock_maps],
                            child_group_id,
                            track_audio_enabled and not (clip_audio.get('mute') or clip_audio.get('muted')),
                            video_enabled,
                        )
                    continue
                child_clip = copy.deepcopy(clip)
                child_clip["id"] = f"{prefix}{clip.get('id', 'clip')}"
                child_clip["timeline_start_tick"] = mapped_start
                child_clip["duration_tick"] = mapped_duration
                child_clip['_audio_scope_enabled'] = bool(track_audio_enabled)
                source_handle = clip.get('_source_handle')
                authored_start_tick = source_handle['authored_start_tick'] if source_handle else clip_start
                # Effect tracks are separate from clip transform tracks. Even
                # a constant-speed ancestor needs their original author clock;
                # mapping only exact/nonlinear source handles restarts or
                # reverses the picture without reversing its color animation.
                if clock_maps:
                    for authored_effect in child_clip.get('effects') or []:
                        if not isinstance(authored_effect, dict):
                            continue
                        params = authored_effect.get('parameters')
                        tracks = authored_effect.get('keyframes')
                        if not isinstance(tracks, list) and isinstance(params, dict):
                            tracks = params.get('keyframes')
                        if isinstance(tracks, list):
                            for effect_track in tracks:
                                if isinstance(effect_track, dict) and isinstance(effect_track.get('keyframes'), list):
                                    effect_track['_nested_clock'] = {
                                        'maps': copy.deepcopy(clock_maps),
                                        'authored_start': authored_start_tick/tps_local,
                                        'keyframes': copy.deepcopy(effect_track['keyframes'])}
                if source_handle and clock_maps:
                    child_clip['_nested_keyframe_clock'] = {'maps':copy.deepcopy(clock_maps),
                                                           'authored_start':authored_start_tick/tps_local}
                    child_clip['_source_envelope_clock'] = {'maps':copy.deepcopy(clock_maps)}
                if clock_maps and (clip.get('subtitle') or kind == 'subtitle'):
                    child_clip['_nested_subtitle_clock'] = _make_subtitle_clock(
                        clip, clock_maps, tps_local, reverse=reverse_time,
                        approximate_freeze=bool(clip.get('freeze') or any(
                            value.get('freeze_semantics_approximate') for value in clock_maps)),
                    )
                leaf_span_tick = max(1, int(clip.get('source_out_tick', 1)) - int(clip.get('source_in_tick', 0)))
                leaf_segments = _speed_curve_segments(clip, leaf_span_tick, tps_local)
                nonlinear_nested = bool(clock_maps) and bool(leaf_segments or any(item['segments'] for item in clock_maps))
                nonlinear_nested = nonlinear_nested or bool(getattr(leaf_segments, 'certificate', {}).get('adaptive'))
                # Even a constant-speed composed surface needs the precise
                # clock path. Dividing its coarse 1/fps PTS directly makes
                # adjacent frames collide, advancing 2x playback by one frame.
                exact_nested = (nonlinear_nested or bool(clock_maps and (
                    source_handle or clip.get('asset_id') in inline_asset_ids))) and not clip.get('freeze')
                if nonlinear_nested and clip.get('freeze'):
                    warnings.append({'code': 'RENDER_FEATURE_APPROXIMATE', 'clip_id': clip.get('id'),
                                     'feature': 'nested_sequence_freeze_clock',
                                     'message': '嵌套非线性速度与定格的联合时钟尚未精确映射；保留显式近似边界'})
                # A nested sequence reverse (or speed/time remap) changes the
                # leaf clip's local clock as well as its source frames. Map
                # every authored keyframe through the same clock function so
                # transform/crop/mask/audio automation follows the visual
                # content. Bezier easing is reversed analytically when the
                # parent timeline runs backwards. Nonlinear ancestors also
                # retain the original track/clock for frame-time evaluation.
                original_keyframe_tracks = child_clip.get("keyframes")
                if isinstance(original_keyframe_tracks, list):
                    mapped_keyframe_tracks: list[dict[str, Any]] = []
                    for track_value in original_keyframe_tracks:
                        if not isinstance(track_value, dict) or not isinstance(track_value.get("keyframes"), list):
                            mapped_keyframe_tracks.append(track_value)
                            continue
                        mapped_track = copy.deepcopy(track_value)
                        mapped_track["keyframes"] = []
                        if exact_nested:
                            mapped_track['_nested_clock'] = {
                                'maps': copy.deepcopy(clock_maps),
                                'authored_start': authored_start_tick / tps_local,
                                'keyframes': copy.deepcopy(track_value.get('keyframes', [])),
                            }
                        for keyframe_value in track_value.get("keyframes", []):
                            if not isinstance(keyframe_value, dict):
                                continue
                            mapped_keyframe = copy.deepcopy(keyframe_value)
                            local_at = _num(keyframe_value.get("at_tick", 0), 0.0)
                            final_at = current_to_final((authored_start_tick if clock_maps else clip_start) + local_at)
                            mapped_keyframe["at_tick"] = int(round(final_at - mapped_start))
                            if reverse_time:
                                _reverse_keyframe_controls(mapped_keyframe)
                            mapped_track["keyframes"].append(mapped_keyframe)
                        mapped_keyframe_tracks.append(mapped_track)
                    child_clip["keyframes"] = mapped_keyframe_tracks
                # `scale` is the child-timeline to final-timeline ratio. A
                # nested sequence that plays at 2x therefore needs its leaf
                # clips to render at 1/scale so FFmpeg emits the mapped
                # duration instead of the original child duration.
                effective_leaf_scale = scale
                if time_mapper is not None:
                    effective_leaf_scale = abs(mapped_right - mapped_left) / max(1.0, float(overlap_end - overlap_start))
                if not exact_nested and abs(effective_leaf_scale - 1.0) > 1e-9:
                    child_speed = max(0.01, _num(child_clip.get("speed", 1.0), 1.0))
                    child_clip["speed"] = child_speed / max(1e-9, effective_leaf_scale)
                if exact_nested:
                    leaf_clock = _make_clock_map(clip, leaf_segments, tps_local)
                    source_bounds = [
                        _unmap_clock_time(leaf_clock, overlap_start / tps_local),
                        _unmap_clock_time(leaf_clock, overlap_end / tps_local),
                    ]
                    child_clip['source_in_tick'] = int(round(min(source_bounds) * tps_local))
                    child_clip['source_out_tick'] = max(child_clip['source_in_tick'] + 1, int(round(max(source_bounds) * tps_local)))
                    child_clip['_nested_time_maps'] = [leaf_clock, *copy.deepcopy(clock_maps)]
                    child_clip['_nested_keyframe_clock'] = {
                        'maps': copy.deepcopy(clock_maps), 'authored_start': authored_start_tick / tps_local,
                    }
                    child_clip['reverse'] = bool(reverse_time) ^ bool(clip.get('reverse'))
                    child_clip['speed'] = (child_clip['source_out_tick'] - child_clip['source_in_tick']) / mapped_duration
                    child_clip.pop('speed_curve', None)
                elif reverse_time or overlap_start != clip_start or overlap_end != clip_end:
                    source_in = int(child_clip.get("source_in_tick", 0))
                    source_out = int(child_clip.get("source_out_tick", source_in + max(1, int(child_clip.get("duration_tick", 1)))))
                    source_span = max(1, source_out - source_in)
                    clip_span = max(1, clip_end - clip_start)
                    left_ratio = max(Fraction(0), min(Fraction(1), Fraction(overlap_start - clip_start, clip_span)))
                    right_ratio = max(left_ratio, min(Fraction(1), Fraction(overlap_end - clip_start, clip_span)))
                    # Select the original leaf's displayed source interval
                    # before applying its parent's direction. A reversed
                    # leaf starts at source_out, including any source gap.
                    # Cropping it from source_in instead selects other frames.
                    if bool(clip.get('reverse')):
                        source_left = source_out - round(source_span * right_ratio)
                        source_right = source_out - round(source_span * left_ratio)
                    else:
                        source_left = source_in + round(source_span * left_ratio)
                        source_right = source_in + round(source_span * right_ratio)
                    child_clip["source_in_tick"] = source_left
                    child_clip["source_out_tick"] = max(source_left + 1, source_right)
                    if reverse_time:
                        child_clip["reverse"] = not bool(child_clip.get("reverse"))
                if groups is not None:
                    child_clip['_composite_group'] = group_id
                elif inherited:
                    apply_context(child_clip, inherited)
                if any(existing.get("id") == child_clip["id"] for existing in output_track["clips"]):
                    base_id = child_clip["id"]
                    part_index = 2
                    while any(existing.get("id") == f"{base_id}.part{part_index}" for existing in output_track["clips"]):
                        part_index += 1
                    child_clip["id"] = f"{base_id}.part{part_index}"
                output_track["clips"].append(child_clip)

    visit(sequence, 0, 1.0, (0, int(sequence.get("duration_tick", 1))), "", (), {"transform": None, "effects": [], "masks": [], "mask": None, "blend": None})
    return list(collected.values())


def _build_subtitle_layer(
    root: Path,
    overlay: dict[str, Any],
    subtitle_index: int,
    filters: list[str],
    warnings: list[dict[str, Any]],
    *,
    width: int,
    height: int,
    fps_value: str,
    duration: float,
    tps: int,
    automation: EffectAutomation | None = None,
    automation_meta: list[dict[str, Any]] | None = None,
    projection=None,
) -> dict[str, Any]:
    """Compile one independent text clip into a reusable transparent layer.

    The returned spec deliberately matches the video compositor's contract.
    Keeping text and media layers in the same queue makes ``track.order`` a
    deterministic z-order for mixed video/title timelines, while the text
    raster remains transparent outside its authored timeline window.
    """
    animation = overlay.get("animation") if isinstance(overlay.get("animation"), dict) else {}
    clip_value = overlay.get("clip") if isinstance(overlay.get("clip"), dict) else {}
    clip_id = str(overlay.get("clip_id"))
    clip_start = float(overlay.get("start", 0.0))
    clip_duration = max(0.001, float(overlay.get("duration", 0.001)))
    subtitle_clock = overlay.get('subtitle_clock') or _subtitle_clock_for_clip(clip_value, clip_start, clip_duration)
    authored_start = subtitle_clock['authored_start_seconds']
    authored_duration = subtitle_clock['authored_duration_seconds']
    animation_time = _subtitle_authored_expression(subtitle_clock)
    animation_time_upper = _subtitle_authored_expression(subtitle_clock, 'T')
    transform = _transform_exprs(clip_value, clip_start, tps)
    canvas_label = f"subtitlecanvas{subtitle_index}"
    layer_label = f"subtitlelayer{subtitle_index}"
    filters.append(f"color=c=black@0.0:s={width}x{height}:r={fps_value}:d={duration:.6f},format=rgba[{canvas_label}]")
    # drawtext blends onto transparent black as premultiplied RGB. Convert
    # this raster to the straight-alpha contract before effects/transforms;
    # otherwise coverage is multiplied again and glyph edges turn dark.
    filters.append(f"[{canvas_label}]{overlay['filter']},format=rgba[{layer_label}]")

    rotation_expression = transform["rotation"]
    if overlay.get("animation_type") == "rotate":
        animation_start = authored_start + max(0.0, _num(animation.get("delay", 0.0), 0.0))
        animation_duration = max(0.001, _num(animation.get("duration", 0.3), 0.3))
        from_degrees = _num(animation.get("from_degrees", animation.get("from", -90.0)), -90.0)
        to_degrees = _num(animation.get("to_degrees", animation.get("to", animation.get("angle", 0.0))), 0.0)
        progress = f"clip((({animation_time})-{animation_start:.6f})/{animation_duration:.6f},0,1)"
        animation_angle = f"({from_degrees:.6f}+({to_degrees - from_degrees:.6f})*{progress})"
        rotation_expression = f"({transform['rotation']})+({animation_angle})"
    affine_text = (rotation_expression != '0.00000000' or bool(clip_value.get('tracking_binding'))
                   or (clip_value.get('_composite_group') is not None and transform['scale'] != '1.00000000'))
    if affine_text:
        affine_label = f'subtitle_affine{subtitle_index}'
        filters.append(f'[{layer_label}]'+','.join(_affine_video_filters({**transform,'rotation':rotation_expression},projection=projection,width=width,height=height))+f'[{affine_label}]')
        layer_label = affine_label
    else:
        if transform["scale"] != "1.00000000":
            scale_w = _expr_arg(f"max(2,iw*({transform['scale']}))")
            scale_h = _expr_arg(f"max(2,ih*({transform['scale']}))")
            scaled_label = f"subtitle_scaled{subtitle_index}"
            scale_chain = _scale_filters(f"scale=w={scale_w}:h={scale_h}:eval=frame", alpha=True)
            filters.append(f"[{layer_label}]"+','.join(scale_chain)+f"[{scaled_label}]")
            layer_label = scaled_label


    effect_filters = _effect_filters(
        clip_value.get("effects"),
        warnings,
        clip_id,
        root=root,
        clip=clip_value,
        clip_start=clip_start,
        tps=tps,
        automation=automation,
        automation_meta=automation_meta,
    )
    if effect_filters:
        effect_label = f"subtitle_effects{subtitle_index}"
        filters.append(f"[{layer_label}]" + ",".join(effect_filters) + f",format=rgba[{effect_label}]")
        layer_label = effect_label

    if transform["opacity"] != "1.00000000":
        opacity_label = f"subtitle_opacity{subtitle_index}"
        alpha_expr = f"alpha(X,Y)*clip(({transform['opacity']}),0,1)"
        filters.append(f"[{layer_label}]format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha_expr)},format=rgba[{opacity_label}]")
        layer_label = opacity_label

    mask_values: list[dict[str, Any]] = []
    inherited_masks = clip_value.get("_nested_parent_masks")
    if isinstance(inherited_masks, list):
        mask_values.extend(item for item in inherited_masks if isinstance(item, dict))
    if isinstance(clip_value.get("mask"), dict):
        mask_values.append(clip_value["mask"])
    for mask_index, mask_value in enumerate(mask_values):
        mask_filter = _mask_filter(mask_value, warnings, clip_id, clip=clip_value, clip_start=clip_start, tps=tps)
        if mask_filter:
            masked_label = f"subtitle_mask{subtitle_index}_{mask_index}"
            filters.append(f"[{layer_label}]format=rgba,{mask_filter}[{masked_label}]")
            layer_label = masked_label

    incoming = clip_value.get("transition_in") if isinstance(clip_value.get("transition_in"), dict) else {}
    outgoing = clip_value.get("transition_out") if isinstance(clip_value.get("transition_out"), dict) else {}
    transition_opacity = "1.00000000"
    wipe_alpha = "1.00000000"
    position_x_expr = "0" if affine_text else f"({transform['position_x']})*W-w*({transform['anchor_x']})"
    position_y_expr = "0" if affine_text else f"({transform['position_y']})*H-h*({transform['anchor_y']})"
    unsupported_transitions: list[str] = []

    def _spatial_transition(raw_type: str, config: dict[str, Any]) -> tuple[str, str] | None:
        normalized = raw_type.lower().replace("-", "_")
        aliases = {
            "slideleft": ("slide", "left"),
            "slideright": ("slide", "right"),
            "slideup": ("slide", "up"),
            "slidedown": ("slide", "down"),
            "wipeleft": ("wipe", "left"),
            "wiperight": ("wipe", "right"),
            "wipeup": ("wipe", "up"),
            "wipedown": ("wipe", "down"),
        }
        if normalized in aliases:
            return aliases[normalized]
        if normalized not in {"slide", "slide_in", "slide_out", "wipe", "wipe_in", "wipe_out"}:
            return None
        direction = str(config.get("direction", "left")).lower().replace("-", "_")
        direction = {"top": "up", "bottom": "down"}.get(direction, direction)
        if direction not in {"left", "right", "up", "down"}:
            direction = "left"
        return ("wipe" if normalized.startswith("wipe") else "slide", direction)

    def _slide_offset(direction: str) -> str:
        distance = "(W+w)" if direction in {"left", "right"} else "(H+h)"
        sign = "-" if direction in {"left", "up"} else "+"
        return f"{sign}{distance}"

    def _wipe_visibility(direction: str, progress: str, *, entering: bool) -> str:
        if direction == "left":
            condition = f"lt(X,W*({progress}))" if entering else f"gt(X,W*(1-({progress})))"
        elif direction == "right":
            condition = f"gt(X,W*(1-({progress})))" if entering else f"lt(X,W*({progress}))"
        elif direction == "up":
            condition = f"gt(Y,H*(1-({progress})))" if entering else f"lt(Y,H*({progress}))"
        else:
            condition = f"lt(Y,H*({progress}))" if entering else f"gt(Y,H*(1-({progress})))"
        return f"if({condition},1,0)"

    def _apply_spatial(config: dict[str, Any], raw_type: str, *, entering: bool) -> bool:
        nonlocal position_x_expr, position_y_expr, wipe_alpha
        spatial = _spatial_transition(raw_type, config)
        if spatial is None:
            return False
        spatial_type, direction = spatial
        transition_duration = max(0.001, _num(config.get("duration", 0.25), 0.25))
        time_variable = animation_time_upper if spatial_type == 'wipe' else animation_time
        if entering:
            progress = f"clip((({time_variable})-{authored_start:.6f})/{transition_duration:.6f},0,1)"
        else:
            transition_start = authored_start + max(0.0, authored_duration - transition_duration)
            progress = f"clip((({time_variable})-{transition_start:.6f})/{transition_duration:.6f},0,1)"
        if spatial_type == "slide":
            offset = _slide_offset(direction)
            if entering:
                position_x_expr = f"({position_x_expr})+((1-({progress}))*({offset if direction in {'left', 'right'} else '0'}))"
                position_y_expr = f"({position_y_expr})+((1-({progress}))*({offset if direction in {'up', 'down'} else '0'}))"
            else:
                position_x_expr = f"({position_x_expr})+(({progress})*({offset if direction in {'left', 'right'} else '0'}))"
                position_y_expr = f"({position_y_expr})+(({progress})*({offset if direction in {'up', 'down'} else '0'}))"
        else:
            wipe_alpha = f"({wipe_alpha})*({_wipe_visibility(direction, progress, entering=entering)})"
        return True

    incoming_type = str(incoming.get("type", "")).lower().replace("-", "_")
    if incoming_type:
        if incoming_type in {"fade", "fade_in", "dissolve", "crossfade"}:
            transition_duration = max(0.001, _num(incoming.get("duration", 0.25), 0.25))
            transition_expr = f"if(lt(({animation_time_upper}),{authored_start:.6f}),0,clip((({animation_time_upper})-{authored_start:.6f})/{transition_duration:.6f},0,1))"
            transition_opacity = f"({transition_opacity})*({transition_expr})"
        elif not _apply_spatial(incoming, incoming_type, entering=True):
            unsupported_transitions.append(f"transition_in:{incoming_type}")
    outgoing_type = str(outgoing.get("type", "")).lower().replace("-", "_")
    if outgoing_type:
        if outgoing_type in {"fade", "fade_out", "dissolve", "crossfade"}:
            transition_duration = max(0.001, _num(outgoing.get("duration", 0.25), 0.25))
            fade_start = authored_start + max(0.0, authored_duration - transition_duration)
            fade_end = authored_start + authored_duration
            transition_expr = f"if(gt(({animation_time_upper}),{fade_start:.6f}),clip(({fade_end:.6f}-({animation_time_upper}))/{transition_duration:.6f},0,1),1)"
            transition_opacity = f"({transition_opacity})*({transition_expr})"
        elif not _apply_spatial(outgoing, outgoing_type, entering=False):
            unsupported_transitions.append(f"transition_out:{outgoing_type}")
    if transition_opacity != "1.00000000" or wipe_alpha != "1.00000000":
        transition_label = f"subtitle_transition_opacity{subtitle_index}"
        alpha_expr = f"alpha(X,Y)*clip(({transition_opacity}),0,1)*clip(({wipe_alpha}),0,1)"
        filters.append(f"[{layer_label}]format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha_expr)},format=rgba[{transition_label}]")
        layer_label = transition_label
    if unsupported_transitions:
        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip_id, "feature": "subtitle_transition", "message": f"独立文字层已执行 fade/dissolve alpha、slide/wipe 空间转场；以下转场仍保留基础文字时间窗: {','.join(unsupported_transitions)}"})
    return {
        "label": layer_label,
        "position": f"x={_expr_arg(position_x_expr)}:y={_expr_arg(position_y_expr)}",
        "track_id": overlay.get("track_id"),
        "track_order": int(overlay.get("track_order", 0)),
        "layer_order": subtitle_index,
        "clip_id": clip_id,
        "keyframes": copy.deepcopy(clip_value.get("keyframes", [])),
        "start": clip_start,
        "duration": clip_duration,
        "blend": clip_value.get("blend"),
        "kind": "subtitle",
        "group_id": overlay.get('group_id'),
        "clock": copy.deepcopy(clip_value.get('_nested_keyframe_clock')),
    }


def _resolve_source_visual_transitions(specs, filters, *, prefix=''):
    """Fold declared source-handle chains before legacy edge transitions.

    Every participating picture is already on its own full canvas. The
    source windows overlap exactly; no frame replication is permitted here.
    """
    tracks = {}
    for spec in specs:
        tracks.setdefault(str(spec.get('track_id')), []).append(spec)
    result = []
    count = 0
    for rows in tracks.values():
        rows.sort(key=lambda s: (s['start'], str(s.get('clip_id'))))
        i = 0
        while i < len(rows):
            current = rows[i]
            while (current.get('outgoing') or {}).get('source_transition_id'):
                config = current['outgoing']
                following = rows[i+1] if i+1 < len(rows) else None
                if following is None or (following.get('incoming') or {}).get('source_transition_id') != config['source_transition_id']:
                    raise AppError('SOURCE_TRANSITION_RENDER_PAIR', '真实句柄转场未找到同组入片；未退回近似', exit_code=2)
                seconds = float(config['duration'])
                if abs(current['start']+current['duration']-following['start']-seconds) > 1e-7:
                    raise AppError('SOURCE_TRANSITION_RENDER_CLOCK', '真实句柄窗口未精确重叠；未补帧', exit_code=2)
                a, b, out = (f'{prefix}source_tr{count}_{side}' for side in ('a', 'b', 'out'))
                count += 1
                for spec, label in ((current, a), (following, b)):
                    raster = ',format=gbrap' if config['type'] == 'custom' else ''
                    filters.append(f"[{spec['label']}]trim=start={spec['start']:.12f}:end={spec['start']+spec['duration']:.12f},setpts=PTS-STARTPTS,settb=AVTB{raster}[{label}]")
                expression = ''
                if config['type'] == 'custom':
                    # xfade P runs from 1 to 0. A cut-centred dip is two
                    # separate ramps through an opaque RGB black/white frame;
                    # the built-in fadewhite/black curves have other timing.
                    split = 1-float(config['cut_fraction'])
                    color = '255' if config['source_type'] == 'dip_white' else 'if(eq(PLANE,3),255,0)'
                    if split >= 1:
                        value = f'B*(1-P)+({color})*P'
                    else:
                        value = (f'if(gte(P,{split:.14g}),'
                                 f'A*(P-{split:.14g})/{1-split:.14g}+({color})*(1-P)/{1-split:.14g},'
                                 f'B*({split:.14g}-P)/{split:.14g}+({color})*P/{split:.14g})')
                    expression = ':expr='+_expr_arg(value)
                filters.append(f"[{a}][{b}]xfade=transition={config['type']}:duration={seconds:.12f}:offset={current['duration']-seconds:.12f}{expression},setpts=PTS-STARTPTS+{current['start']:.12f}/TB[{out}]")
                current = {**current, 'label': out,
                           'clip_id': f"{current.get('clip_id')}+{following.get('clip_id')}",
                           'duration': following['start']+following['duration']-current['start'],
                           'incoming': {}, 'outgoing': following.get('outgoing'), 'keyframes': [], 'clock': None}
                i += 1
            if (current.get('incoming') or {}).get('source_transition_id'):
                raise AppError('SOURCE_TRANSITION_RENDER_PAIR', '真实句柄入片没有出片；未退回近似', exit_code=2)
            result.append(current)
            i += 1
    return result


def _resolve_visual_transitions(
    specs: list[dict[str, Any]], filters: list[str], warnings: list[dict[str, Any]],
    fps: dict[str, int], *, prefix: str = '',
) -> list[dict[str, Any]]:
    """Resolve adjacent visual transitions inside one compositing scope."""
    specs = _resolve_source_visual_transitions(specs, filters, prefix=prefix)
    final_specs: list[dict[str, Any]] = []
    by_track: dict[str, list[dict[str, Any]]] = {}
    for spec in specs:
        by_track.setdefault(str(spec.get("track_id")), []).append(spec)
    complex_types = (XFADE_TRANSITIONS - {"fade"}) | {"crossfade", "dissolve", "wipe", "slide"}
    for track_specs in by_track.values():
        track_specs.sort(key=lambda item: (float(item["start"]), str(item.get("clip_id"))))
        index = 0
        while index < len(track_specs):
            current_spec = track_specs[index]
            next_spec = track_specs[index + 1] if index + 1 < len(track_specs) else None
            incoming_transition = next_spec.get("incoming") if next_spec and isinstance(next_spec.get("incoming"), dict) else {}
            outgoing_transition = current_spec.get("outgoing") if isinstance(current_spec.get("outgoing"), dict) else {}
            transition = incoming_transition if str(incoming_transition.get("type", "")) else outgoing_transition
            transition_type = str(transition.get("type", "")).lower()
            if next_spec and transition_type in complex_types:
                transition_duration = max(0.001, _num(transition.get("duration", 0.25), 0.25))
                expected_start = float(current_spec["start"]) + float(current_spec["duration"]) - transition_duration
                frame_tolerance = max(1.0 / max(1, int(fps["num"])), 0.01)
                overlap_handles = abs(float(next_spec["start"]) - expected_start) <= frame_tolerance
                contiguous = abs(float(next_spec["start"]) - (float(current_spec["start"]) + float(current_spec["duration"]))) <= frame_tolerance
                auto_handle = bool(transition.get("auto_handle", False)) or str(transition.get("handle_policy", "")).lower() == "auto"
                if transition_duration < float(current_spec["duration"]) and transition_duration < float(next_spec["duration"]) and (overlap_handles or (auto_handle and contiguous)):
                    left_trim = f"{prefix}tr{len(final_specs)}a"
                    right_trim = f"{prefix}tr{len(final_specs)}b"
                    output_label = f"{prefix}transition{len(final_specs)}"
                    filters.append(f"[{current_spec['label']}]trim=start={float(current_spec['start']):.6f}:end={float(current_spec['start']) + float(current_spec['duration']):.6f},setpts=PTS-STARTPTS[{left_trim}]")
                    filters.append(f"[{next_spec['label']}]trim=start={float(next_spec['start']):.6f}:end={float(next_spec['start']) + float(next_spec['duration']):.6f},setpts=PTS-STARTPTS[{right_trim}]")
                    direction = str(transition.get("direction", "left")).lower()
                    transition_name = {"crossfade": "fade", "dissolve": "fade"}.get(transition_type, transition_type)
                    if transition_type == "wipe":
                        transition_name = {"left": "wipeleft", "right": "wiperight", "up": "wipeup", "down": "wipedown"}.get(direction, "wipeleft")
                    elif transition_type == "slide":
                        transition_name = {"left": "slideleft", "right": "slideright", "up": "slideup", "down": "slidedown"}.get(direction, "slideright")
                    if transition_name not in XFADE_TRANSITIONS:
                        transition_name = "fade"
                    preserve_contiguous_duration = auto_handle and contiguous and not overlap_handles
                    tail_padding = f",tpad=stop_mode=clone:stop_duration={transition_duration:.6f}" if preserve_contiguous_duration else ""
                    filters.append(f"[{left_trim}][{right_trim}]xfade=transition={transition_name}:duration={transition_duration:.6f}:offset={float(current_spec['duration']) - transition_duration:.6f}{tail_padding},setpts=PTS-STARTPTS+{float(current_spec['start']):.6f}/TB[{output_label}]")
                    if preserve_contiguous_duration:
                        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": next_spec.get("clip_id"), "feature": "complex_transition_auto_handle", "message": "相邻片段没有重叠句柄，已用本地 xfade 并保持原时间线长度；转场尾部使用最后一帧填充"})
                    final_specs.append({"label": output_label, "position": current_spec["position"], "track_id": current_spec.get("track_id"), "track_order": current_spec.get("track_order", 0), "layer_order": current_spec.get("layer_order", len(final_specs)), "group_id": current_spec.get("group_id"), "clip_id": f"{current_spec.get('clip_id')}+{next_spec.get('clip_id')}", "start": current_spec["start"], "duration": float(current_spec["duration"]) + float(next_spec["duration"]) if preserve_contiguous_duration else float(current_spec["duration"]) + float(next_spec["duration"]) - transition_duration})
                    index += 2
                    continue
                warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": next_spec.get("clip_id"), "feature": "complex_transition", "message": "复杂转场要求相邻片段有匹配的重叠时间句柄，当前已保留但未执行"})
            elif transition_type in complex_types:
                warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": current_spec.get("clip_id"), "feature": "complex_transition", "message": "没有可配对的相邻片段，复杂转场未执行"})
            final_specs.append(current_spec)
            index += 1
    return final_specs


def _composite_visual_layers(
    final_specs: list[dict[str, Any]], base: str, filters: list[str], warnings: list[dict[str, Any]],
    *, width: int, height: int, fps_value: str, duration: float, tps: int,
    prefix: str = '', preserve_alpha: bool = False,
    automation: EffectAutomation | None = None, automation_meta: list[dict[str, Any]] | None = None,
) -> str:
    """Source-over or blend positioned layers on a single canvas."""
    current = base
    for pos, spec in enumerate(final_specs):
        target = f"{prefix}vo{pos}"
        blend = spec.get("blend") if isinstance(spec.get("blend"), dict) else {}
        blend_mode = str(blend.get("mode", "normal")).lower().replace("-", "_")
        from .blend_automation import track_for as _blend_track
        saved_animation = blend.get('opacity_animation') if _blend_track(spec) is None else None
        native_opacity = None
        if saved_animation is not None:
            if automation is None:
                raise AppError('BLEND_AUTOMATION_COMPILER_MISSING', '混合动画需要共享根图编译器', exit_code=6)
            native_opacity, evidence = automation.bind_blend(saved_animation,
                {'id': spec.get('clip_id'), 'timeline_start_tick': round(float(spec.get('start', 0))*tps),
                 '_nested_keyframe_clock': spec.get('clock')},
                float(spec.get('start', 0)), float(spec.get('start', 0))+float(spec.get('duration', 0)))
            if automation_meta is not None:
                automation_meta.append(evidence)
        if blend_mode in {"normal", "source_over", ""}:
            opacity = _clamp(blend.get("opacity", 1.0), 0.0, 1.0, 1.0)
            blend_opacity_expr = _keyframe_expr(
                {"keyframes": spec.get("keyframes", []), "_nested_keyframe_clock": spec.get("clock"), "timeline_start_tick": round(float(spec.get("start", 0.0))*tps)}, ("blend.opacity", "blend_opacity"),
                opacity, float(spec.get("start", 0.0)), tps, time_variable="T",
            )
            source_label = spec['label']
            if native_opacity is not None:
                source_label = f"{prefix}normalopacity{pos}"
                filters.append(f"[{spec['label']}]format=rgba,{','.join(native_opacity)}[{source_label}]")
            elif blend_opacity_expr != "1.00000000":
                source_label = f"{prefix}normalopacity{pos}"
                alpha_expr = f"alpha(X,Y)*clip(({blend_opacity_expr}),0,1)"
                filters.append(f"[{spec['label']}]format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha_expr)},format=rgba[{source_label}]")
            filters.append(f"[{current}][{source_label}]overlay={spec['position']}:eof_action=pass:format=auto[{target}]")
        elif blend_mode in {"addition", "addition128", "and", "average", "burn", "darken", "difference", "divide", "dodge", "exclusion", "freeze", "glow", "hardlight", "hard_mix", "lighten", "multiply", "negation", "or", "phoenix", "pinlight", "reflect", "screen", "softlight", "subtract", "vivid", "xor"}:
            # FFmpeg's blend filter requires two same-sized frames and has no
            # notion of the clip's timeline position or alpha coverage.  Build
            # a transparent, positioned canvas first, then use its alpha as a
            # masked merge so pixels outside the layer remain untouched.  This
            # keeps multiply/screen/etc. consistent with source-over behavior.
            opacity = _clamp(blend.get("opacity", 1.0), 0.0, 1.0, 1.0)
            ffmpeg_mode = {"hard_mix": "hardmix", "vivid": "vividlight"}.get(blend_mode, blend_mode)
            layer_prefix = prefix + ("subtitle_" if spec.get("kind") == "subtitle" else "")
            blend_index = int(spec.get("layer_order", pos)) if spec.get("kind") == "subtitle" else pos
            blend_canvas = f"{layer_prefix}blendcanvas{blend_index}"
            blend_source = f"{layer_prefix}blendsource{blend_index}"
            blend_layer = f"{layer_prefix}blendlayer{blend_index}"
            blend_base = f"{layer_prefix}blendbase{blend_index}"
            blend_under = f"{layer_prefix}blendunder{blend_index}"
            blend_result = f"{layer_prefix}blendresult{blend_index}"
            blend_alpha = f"{layer_prefix}blendalpha{blend_index}"
            blend_color_layer = f"{layer_prefix}blendcolor{blend_index}"
            blend_mask_layer = f"{layer_prefix}blendmask{blend_index}"
            filters.append(f"color=c=black@0.0:s={width}x{height}:r={fps_value}:d={duration:.6f},format=rgba[{blend_canvas}]")
            filters.append(f"[{spec['label']}]format=rgba[{blend_source}]")
            filters.append(f"[{blend_canvas}][{blend_source}]overlay={spec['position']}:eof_action=pass:format=auto,format=rgba[{blend_layer}]")
            blend_opacity_expr = _keyframe_expr(
                {"keyframes": spec.get("keyframes", []), "_nested_keyframe_clock": spec.get("clock"), "timeline_start_tick": round(float(spec.get("start", 0.0))*tps)},
                ("blend.opacity", "blend_opacity"),
                opacity,
                float(spec.get("start", 0.0)),
                tps,
                time_variable="T",
            )
            dynamic_blend_opacity = any(
                isinstance(item, dict) and str(item.get("property", "")) in {"blend.opacity", "blend_opacity"}
                for item in spec.get("keyframes", [])
            )
            if native_opacity is not None:
                filters.append(f"[{blend_layer}]format=rgba,{','.join(native_opacity)}[{blend_layer}o]")
                blend_layer = f"{blend_layer}o"
            elif dynamic_blend_opacity:
                alpha_expr = f"alpha(X,Y)*clip(({blend_opacity_expr}),0,1)"
                filters.append(f"[{blend_layer}]format=gbrap,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha_expr)},format=rgba[{blend_layer}o]")
                blend_layer = f"{blend_layer}o"
            elif opacity < 1.0:
                filters.append(f"[{blend_layer}]colorchannelmixer=aa={opacity:.6f}[{blend_layer}o]")
                blend_layer = f"{blend_layer}o"
            if preserve_alpha:
                # W3C isolated blend: Cs'=(1-Ab)*Cs+Ab*B(Cb,Cs), then
                # source-over Cs' with the original As. Blending against
                # invisible black RGB alone would turn multiply transparent
                # regions black and discard the group's coverage.
                filters.append(f"[{blend_layer}]split=3[{blend_color_layer}][{blend_color_layer}plain][{blend_mask_layer}]")
                filters.append(f"[{current}]split=3[{blend_base}][{blend_under}][{blend_base}alpha]")
                filters.append(f"[{blend_base}]format=gbrp[{blend_base}r]")
                filters.append(f"[{blend_color_layer}]format=gbrp[{blend_color_layer}r]")
                filters.append(f"[{blend_color_layer}plain]format=gbrp[{blend_color_layer}plainr]")
                filters.append(f"[{blend_base}r][{blend_color_layer}r]blend=all_mode={ffmpeg_mode}:all_opacity=1[{blend_result}]")
                filters.append(f"[{blend_base}alpha]format=rgba,alphaextract,format=gbrp[{blend_alpha}]")
                filters.append(f"[{blend_color_layer}plainr][{blend_result}][{blend_alpha}]maskedmerge[{blend_result}rgb]")
                filters.append(f"[{blend_mask_layer}]format=rgba,alphaextract[{blend_mask_layer}a]")
                filters.append(f"[{blend_result}rgb][{blend_mask_layer}a]alphamerge,format=rgba[{blend_result}rgba]")
                filters.append(f"[{blend_under}][{blend_result}rgba]overlay=x=0:y=0:eof_action=pass:format=auto,format=rgba[{target}]")
                current = target
                continue
            # Keep independent pixel-format negotiations for the blend math
            # and alpha mask; otherwise FFmpeg may negotiate the shared stream
            # to a non-alpha format before alphaextract sees it.
            filters.append(f"[{blend_layer}]split=2[{blend_color_layer}][{blend_mask_layer}]")
            filters.append(f"[{current}]split=2[{blend_base}][{blend_under}]")
            filters.append(f"[{blend_base}]format=gbrp[{blend_base}r]")
            filters.append(f"[{blend_under}]format=gbrp[{blend_under}r]")
            filters.append(f"[{blend_color_layer}]format=gbrp[{blend_color_layer}r]")
            filters.append(f"[{blend_base}r][{blend_color_layer}r]blend=all_mode={ffmpeg_mode}:all_opacity=1[{blend_result}]")
            # All three maskedmerge inputs must share the RGB plane format.
            # A gray alpha plane alone would otherwise negotiate the entire
            # merge to grayscale and discard the composite's color channels.
            filters.append(f"[{blend_mask_layer}]format=rgba,alphaextract,format=gbrp[{blend_alpha}]")
            filters.append(f"[{blend_under}r][{blend_result}][{blend_alpha}]maskedmerge[{target}]")
        else:
            warnings.append({"code": "RENDER_FEATURE_UNSUPPORTED", "clip_id": spec.get("clip_id"), "feature": f"blend:{blend_mode}", "message": "当前 FFmpeg 后端不支持该混合模式，已回退 source-over"})
            filters.append(f"[{current}][{spec['label']}]overlay={spec['position']}:eof_action=pass:format=auto[{target}]")
        current = target
    return current


def _sequence_raster_filters(
    clip: dict[str, Any], transform: dict[str, str], source: dict[str, int], target: dict[str, int],
    start: float, tps: int, *, sampling: str = 'bilinear', projection=None,
) -> list[str]:
    """Project a child raster into its parent's canvas around the child anchor.

    Retain the complete native texture on a padded working raster and sample
    its crop/fit/TRS coordinates once. Rotation may reveal source content
    hidden by fill at the resting pose. The output rectangle is cropped only
    after sampling; interpolation is premultiplied, before the parent mask.
    """
    sw, sh = source['width'], source['height']
    tw, th = target['width'], target['height']
    crop = clip.get('crop') or {}
    normalized = str(crop.get('unit', 'pixels')).lower() in {'normalized', 'relative'}
    def scalar(names: tuple[str, ...], default: float, extent: int) -> str:
        value = next((crop[n] for n in names if n in crop), default)
        result = _crop_keyframe_expr(clip, crop, names, _num(value, default), start, tps, time_variable='T')
        return f'({result})*{extent}' if normalized else result
    w = scalar(('width', 'w'), 1. if normalized else sw, sw)
    h = scalar(('height', 'h'), 1. if normalized else sh, sh)
    x = scalar(('x',), 0., sw)
    y = scalar(('y',), 0., sh)
    fit = str(crop.get('fit', crop.get('mode', 'fit'))).lower()
    if fit == 'stretch':
        fit_x, fit_y = f'{tw}/ld(0)', f'{th}/ld(1)'
    else:
        select = 'max' if fit == 'fill' else 'min'
        fit_x = fit_y = f'{select}({tw}/ld(0),{th}/ld(1))'
    values = {k: re.sub(r'\bt\b', 'T', v) for k,v in transform.items()}
    angle = f"({values['rotation']})*PI/180"
    dx, dy = f"(X+0.5-({values['position_x']})*{tw})", f"(Y+0.5-({values['position_y']})*{th})"
    scale = f"max(0.00000001,abs({values['scale']}))"
    setup = (
        f'st(0,clip(({w}),2,{sw}));st(1,clip(({h}),2,{sh}));'
        f'st(2,clip(({x}),0,{sw}-ld(0)));st(3,clip(({y}),0,{sh}-ld(1)));'
        f'st(4,{fit_x});st(5,{fit_y});'
        f"st(6,ld(2)+({values['anchor_x']})*ld(0)+({dx}*cos({angle})+{dy}*sin({angle}))/({scale}*ld(4))-0.5);"
        f"st(7,ld(3)+({values['anchor_y']})*ld(1)+(-{dx}*sin({angle})+{dy}*cos({angle}))/({scale}*ld(5))-0.5);"
    )
    sample_x = 'clip(ld(6),ld(2),ld(2)+ld(0)-1)'
    sample_y = 'clip(ld(7),ld(3),ld(3)+ld(1)-1)'
    pure = _geq_row_invariant([w, h, x, y, *values.values()])
    # A projection has more row constants than AVExpr's ten registers. Keep
    # the most expensive repeated nodes, with disjoint pixel scratch storage.
    # The area kernel reads its top/bottom edges without overwriting constants.
    definitions = {
        'crop_w': f'clip(({w}),2,{sw})', 'crop_h': f'clip(({h}),2,{sh})',
        'crop_x': f'clip(({x}),0,{sw}-@{{crop_w}})',
        'crop_y': f'clip(({y}),0,{sh}-@{{crop_h}})',
        'fit_x': f'{tw}/@{{crop_w}}' if fit == 'stretch' else f'{select}({tw}/@{{crop_w}},{th}/@{{crop_h}})',
        'fit_y': f'{th}/@{{crop_h}}' if fit == 'stretch' else '@{fit_x}',
        'cosine': f'cos({angle})', 'sine': f'sin({angle})',
        'position_x': f"({values['position_x']})*{tw}",
        'position_y': f"({values['position_y']})*{th}",
        'scale': scale, 'anchor_x': f"({values['anchor_x']})", 'anchor_y': f"({values['anchor_y']})",
    }
    pixel_coordinates = (
        'st(6,@{crop_x}+@{anchor_x}*@{crop_w}'
        '+((X+0.5-@{position_x})*@{cosine}+(Y+0.5-@{position_y})*@{sine})/(@{scale}*@{fit_x})-0.5);'
        'st(7,@{crop_y}+@{anchor_y}*@{crop_h}'
        '+(-(X+0.5-@{position_x})*@{sine}+(Y+0.5-@{position_y})*@{cosine})/(@{scale}*@{fit_y})-0.5);'
    )
    def plane(name: str) -> str:
        if pure:
            if sampling == 'area':
                area_definitions = {**definitions,
                    'kernel_x': 'max(1,1/(@{scale}*@{fit_x}))',
                    'kernel_y': 'max(1,1/(@{scale}*@{fit_y}))'}
                edges = (
                    'st(8,clip(ld(6)+0.5-@{kernel_x}/2,@{crop_x},@{crop_x}+@{crop_w}));'
                    'st(9,clip(ld(6)+0.5+@{kernel_x}/2,@{crop_x},@{crop_x}+@{crop_w}));'
                    # X has now been consumed. Reuse its register for top;
                    # bottom still reads the original Y before replacing it.
                    'st(6,clip(ld(7)+0.5-@{kernel_y}/2,@{crop_y},@{crop_y}+@{crop_h}));'
                    'st(7,clip(ld(7)+0.5+@{kernel_y}/2,@{crop_y},@{crop_y}+@{crop_h}));'
                )
                integral = area_rectangle(name,
                    top='ld(6)', bottom='ld(7)',
                    width='@{kernel_x}', height='@{kernel_y}')
                body = f'if(lt(X,{tw})*lt(Y,{th}),'+pixel_coordinates+edges+integral+',0)'
                return _expr_arg(_geq_scanline_expression(area_definitions, body, (0,1,2,3,4,5)))
            inside = ('gte(ld(6),@{crop_x}-0.5)*lt(ld(6),@{crop_x}+@{crop_w}-0.5)'
                      '*gte(ld(7),@{crop_y}-0.5)*lt(ld(7),@{crop_y}+@{crop_h}-0.5)')
            px = 'clip(ld(6),@{crop_x},@{crop_x}+@{crop_w}-1)'
            py = 'clip(ld(7),@{crop_y},@{crop_y}+@{crop_h}-1)'
            body = pixel_coordinates+f'if({inside},{name}({px},{py}),0)'
            return _expr_arg(_geq_scanline_expression(definitions, body, (0,1,2,3,4,5,8,9)))
        if sampling == 'area':
            # Reuse registers only after their old values have been consumed.
            edges = (f'st(4,max(1,1/({scale}*ld(4))));st(5,max(1,1/({scale}*ld(5))));'
                     'st(8,clip(ld(6)+0.5-ld(4)/2,ld(2),ld(2)+ld(0)));'
                     'st(9,clip(ld(6)+0.5+ld(4)/2,ld(2),ld(2)+ld(0)));'
                     'st(2,clip(ld(7)+0.5-ld(5)/2,ld(3),ld(3)+ld(1)));'
                     'st(3,clip(ld(7)+0.5+ld(5)/2,ld(3),ld(3)+ld(1)));')
            return _expr_arg(f'if(lt(X,{tw})*lt(Y,{th}),'+setup+edges+area_rectangle(name)+',0)')
        inside = 'st(8,gte(ld(6),ld(2)-0.5)*lt(ld(6),ld(2)+ld(0)-0.5)*gte(ld(7),ld(3)-0.5)*lt(ld(7),ld(3)+ld(1)-0.5));'
        return _expr_arg(setup+inside+f'if(ld(8),{name}({sample_x},{sample_y}),0)')
    cpu = ['format=rgba', f'pad={max(sw,tw)}:{max(sh,th)}:0:0:color=black@0', 'setsar=1',
            'format=gbrapf32le', 'premultiply=inplace=1',
            f"geq=r={plane('r')}:g={plane('g')}:b={plane('b')}:a={plane('alpha')}:interpolation=bilinear",
            f'crop={tw}:{th}:0:0:exact=1', 'unpremultiply=inplace=1', 'format=rgba']
    if projection is not None:
        from .projection_opencl import expand_definitions,sequence_body
        area=sampling=='area'
        gpu_definitions={**definitions}
        if area:
            gpu_definitions.update(kernel_x='max(1,1/(@{scale}*@{fit_x}))',
                                   kernel_y='max(1,1/(@{scale}*@{fit_y}))')
        return projection.select(cpu,kind='sequence',expressions=expand_definitions(gpu_definitions),
            source=(sw,sh),target=(tw,th),body=sequence_body(area=area),area=area,pure=pure,
            prefix=['format=rgba','setsar=1','format=gbrapf32le','premultiply=inplace=1'],
            suffix=['unpremultiply=inplace=1','format=rgba'])
    return cpu


def _build_compositing_tree(
    root: Path, specs: list[dict[str, Any]], groups: dict[str, dict[str, Any]],
    filters: list[str], warnings: list[dict[str, Any]], input_meta: list[dict[str, Any]],
    *, width: int, height: int, fps: dict[str, int], fps_value: str, duration: float,
    tps: int, transparent_canvas: bool, sampling: str = 'bilinear',
    automation: EffectAutomation | None = None,
    projection=None,
) -> str:
    """Composite complete child sequences before applying container operations.

    All streams retain the final display clock. Each scope has a transparent
    full-canvas base, independent z-order and labels; no lossy intermediate
    file, GUI, background server or second render is needed.
    """
    buckets: dict[str | None, list[dict[str, Any]]] = {}
    quota_nodes = {node['clip_id']:node for item in input_meta if item.get('kind')=='sequence-projection-budget'
                   for node in item['nodes']}
    for spec in specs:
        buckets.setdefault(spec.get('group_id'), []).append(spec)

    def canvas(label: str, *, alpha: bool, raster: dict[str, int] | None = None) -> None:
        color = 'black@0.0' if alpha else 'black'
        pixel_format = ',format=rgba' if alpha else ''
        cw, ch = (raster['width'], raster['height']) if raster else (width, height)
        filters.append(f'color=c={color}:s={cw}x{ch}:r={fps_value}:d={duration:.6f}{pixel_format}[{label}]')

    # Children were registered after their parents. Reverse insertion order
    # is a postorder even when a temporal window revisits an existing group.
    for ordinal, group in reversed(list(enumerate(groups.values()))):
        if not group.get('video_enabled', True):
            continue
        group_id = group['id']
        source_canvas, parent_canvas = group['canvas'], group['parent_canvas']
        prefix = f'group{ordinal}_'
        group_specs = _resolve_visual_transitions(buckets.get(group_id, []), filters, warnings, fps, prefix=prefix)
        group_specs.sort(key=lambda item: (int(item.get('track_order', 0)), float(item.get('start', 0.0)), int(item.get('layer_order', 0))))
        base = prefix+'base'
        canvas(base, alpha=True, raster=source_canvas)
        composite = _composite_visual_layers(group_specs, base, filters, warnings, width=source_canvas['width'], height=source_canvas['height'],
                                             fps_value=fps_value, duration=duration, tps=tps, prefix=prefix, preserve_alpha=True,
                                             automation=automation, automation_meta=input_meta)
        clip = group['clip']
        start = int(clip['timeline_start_tick'])/tps
        end = start+int(clip['duration_tick'])/tps
        chain = ['format=rgba']
        crop = clip.get('crop')
        transform = _transform_exprs(clip, start, tps)
        identity = {'scale':'1.00000000','rotation':'0.00000000','position_x':'0.50000000',
                    'position_y':'0.50000000','anchor_x':'0.50000000','anchor_y':'0.50000000'}
        adapt_raster = source_canvas != parent_canvas or bool(crop) or sampling == 'area'
        if adapt_raster:
            chain.extend(_sequence_raster_filters(clip, transform, source_canvas, parent_canvas, start, tps, sampling=sampling,projection=projection))
        else:
            if any(transform[key] != value for key,value in identity.items()):
                chain.extend(_affine_video_filters(transform,projection=projection,width=source_canvas['width'],height=source_canvas['height']))
        if transform['opacity'] != '1.00000000':
            alpha = f"alpha(X,Y)*clip(({transform['opacity']}),0,1)"
            chain.extend(['format=gbrap',f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha)}",'format=rgba'])
        chain.extend(_effect_filters(clip.get('effects'), warnings, group_id, root=root, clip=clip,
                                     clip_start=start, tps=tps, automation=automation, automation_meta=input_meta))
        mask = _mask_filter(clip.get('mask'), warnings, group_id, clip=clip, clip_start=start, tps=tps)
        if mask:
            chain.extend(['format=rgba', mask])
        transition_alpha = '1'
        authored = clip.get('_nested_keyframe_clock') or {'maps':[], 'authored_start':start}
        local_clock = f"(({_clock_expression(authored['maps'], 'T', inverse=True)})-{authored['authored_start']:.12f})"
        original_duration = int(clip['_composite_authored_duration_tick'])/tps
        for name, accepted in (('transition_in', {'fade','fade_in'}), ('transition_out', {'fade','fade_out'})):
            transition = clip.get(name)
            if isinstance(transition, dict) and str(transition.get('type', '')).lower() in accepted:
                seconds = max(.001, _num(transition.get('duration', .25), .25))
                numerator = local_clock if name == 'transition_in' else f'({original_duration:.12f}-({local_clock}))'
                transition_alpha += f'*clip(({numerator})/{seconds:.12f},0,1)'
        if transition_alpha != '1':
            alpha = f'alpha(X,Y)*({transition_alpha})'
            chain.extend(['format=gbrap', f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha)}", 'format=rgba'])
        # Trim on the global display grid. An isolated canvas must not leave a
        # frozen final frame or opacity outside its half-open visible interval.
        # trim=start/end quantizes seconds to its input timebase with nearest
        # rounding; this can drop a final partial frame or expose a clip one
        # tick early. Every scope starts on frame zero of the global CFR grid.
        numerator,denominator=int(fps['num']),tps*int(fps['den'])
        left=Fraction(int(clip['timeline_start_tick'])*numerator,denominator)
        right=Fraction((int(clip['timeline_start_tick'])+int(clip['duration_tick']))*numerator,denominator)
        chain.append(f'trim=start_frame={math.ceil(left)}:end_frame={math.ceil(right)}')
        label = prefix+'out'
        filters.append(f'[{composite}]'+','.join(chain)+f'[{label}]')
        buckets.setdefault(group['parent_id'], []).append({
            'label':label,'position':'x=0:y=0','track_id':group['track_id'],'track_order':group['track_order'],
            'layer_order':group['layer_order'],'clip_id':group_id,'group_id':group['parent_id'],
            'start':start,'duration':end-start,'keyframes':copy.deepcopy(clip.get('keyframes', [])),
            'clock':copy.deepcopy(clip.get('_nested_keyframe_clock')),'blend':copy.deepcopy(clip.get('blend')),
            'incoming':copy.deepcopy(clip.get('transition_in')),'outgoing':copy.deepcopy(clip.get('transition_out')),
        })
        input_meta.append({'kind':'sequence-composite','clip_id':group_id,'parent_id':group['parent_id'],
                           'sequence_id':clip.get('sequence_id'),'canvas':{**source_canvas,'alpha':True},
                           'parent_canvas':copy.deepcopy(parent_canvas),'anchor_space':'cropped-child-canvas',
                           'raster_adaptation':'crop-fit-trs-inverse-sampling' if adapt_raster else 'same-raster',
                           'working_canvas':{'width':max(source_canvas['width'],parent_canvas['width']),
                                             'height':max(source_canvas['height'],parent_canvas['height'])} if adapt_raster else copy.deepcopy(source_canvas),
                           'spatial_sampler':f'native-premultiplied-{sampling}-once' if adapt_raster else 'legacy-same-raster',
                           'sampling_kernel':'source-axis-separable-box-minimum-one-pixel' if sampling == 'area' else 'bilinear',
                           'projection_working_bytes':quota_nodes[group_id]['estimated_working_bytes'],
                           'compositing':'isolated-source-over','child_layer_count':len(group_specs),
                           'timeline_start_tick':int(clip['timeline_start_tick']),'duration_tick':int(clip['duration_tick']),
                           'spatial_order':['child-composite','crop','transform','opacity','effects','mask','fade'],
                           'intermediate_files':0})
    root_specs = _resolve_visual_transitions(buckets.get(None, []), filters, warnings, fps)
    root_specs.sort(key=lambda item: (int(item.get('track_order', 0)), float(item.get('start', 0.0)), int(item.get('layer_order', 0))))
    canvas('base', alpha=transparent_canvas)
    return _composite_visual_layers(root_specs, 'base', filters, warnings, width=width, height=height,
                                    fps_value=fps_value, duration=duration, tps=tps, preserve_alpha=transparent_canvas,
                                    automation=automation, automation_meta=input_meta)


def _audio_processing_filters(
    clip: dict[str, Any], audio_settings: dict[str, Any], tps: int,
    *, audio_keyframe_time: str = "t", clip_start: float = 0.0,
    fade_clock: str = "t", authored_duration: float = 0.0,
) -> list[str]:
    """Apply clip or bus processing once; automation uses a sample clock."""
    chain: list[str] = []
    volume = _num(audio_settings.get("volume", clip.get("volume", 1.0)), 1.0)
    volume_expr = _keyframe_expr(clip, ("audio.volume", "volume"), volume, clip_start, tps, time_variable=audio_keyframe_time)
    if volume_expr != f"{volume:.8f}" or abs(volume - 1.0) > 1e-9:
        if volume_expr != f"{volume:.8f}":
            gain_expression = f'val(ch)*({volume_expr})'
            chain.append(f"aeval=exprs={_expr_arg(gain_expression)}:c=same")
        else:
            chain.append(f"volume=volume={volume:.8f}")
    if audio_settings.get("noise_reduction") or audio_settings.get("denoise"):
        reduction = _num(audio_settings.get("noise_reduction", audio_settings.get("denoise", -25)), -25)
        if isinstance(audio_settings.get('noise_reduction',audio_settings.get('denoise')),bool):reduction=-25
        chain.append(f"afftdn=nf={reduction:.2f}")
    if audio_settings.get("compressor"):
        compressor = audio_settings.get("compressor") if isinstance(audio_settings.get("compressor"), dict) else {}
        chain.append(
            "acompressor="
            f"threshold={_num(compressor.get('threshold', 0.125), 0.125):.6f}:"
            f"ratio={max(1.0, _num(compressor.get('ratio', 2.0), 2.0)):.6f}:"
            f"attack={max(0.01, _num(compressor.get('attack', 20), 20)):.3f}:"
            f"release={max(1.0, _num(compressor.get('release', 250), 250)):.3f}"
        )
    equalizer = audio_settings.get("equalizer", audio_settings.get("eq"))
    if isinstance(equalizer, dict):
        frequency = max(20.0, min(20000.0, _num(equalizer.get("frequency", equalizer.get("f", 1000)), 1000)))
        gain = max(-24.0, min(24.0, _num(equalizer.get("gain", equalizer.get("g", 0)), 0)))
        bandwidth = max(0.05, min(10.0, _num(equalizer.get("width", equalizer.get("w", 1)), 1)))
        chain.append(f"equalizer=f={frequency:.3f}:t=q:w={bandwidth:.4f}:g={gain:.4f}")
    if audio_settings.get("highpass"):
        chain.append(f"highpass=f={max(20.0, min(20000.0, _num(audio_settings.get('highpass'), 80))):.3f}")
    if audio_settings.get("lowpass"):
        chain.append(f"lowpass=f={max(20.0, min(20000.0, _num(audio_settings.get('lowpass'), 16000))):.3f}")
    if audio_settings.get("dialogue_enhance") or audio_settings.get("voice_enhance"):
        chain.append("dialoguenhance")
    pitch = audio_settings.get("pitch_semitones")
    if pitch is not None and abs(_num(pitch, 0)) > 1e-6:
        semitones = max(-24.0, min(24.0, _num(pitch, 0)))
        chain.append(f"rubberband=pitch={2 ** (semitones / 12.0):.8f}")
    reverb = audio_settings.get("reverb")
    if isinstance(reverb, dict):
        in_gain = max(0.0, min(1.0, _num(reverb.get("in_gain", 0.8), 0.8)))
        out_gain = max(0.0, min(1.0, _num(reverb.get("out_gain", 0.9), 0.9)))
        delays = str(reverb.get("delays", "60|90"))
        decays = str(reverb.get("decays", "0.25|0.15"))
        chain.append(f"aecho={in_gain:.4f}:{out_gain:.4f}:{delays}:{decays}")
    loudnorm = audio_settings.get("loudnorm")
    if isinstance(loudnorm, dict):
        integrated = _num(loudnorm.get("i", loudnorm.get("integrated", -16)), -16)
        true_peak = _num(loudnorm.get("tp", loudnorm.get("true_peak", -1.5)), -1.5)
        loudness_range = _num(loudnorm.get("lra", 11), 11)
        chain.append(f"loudnorm=I={integrated:.3f}:TP={true_peak:.3f}:LRA={max(1.0, loudness_range):.3f}")
    pan = audio_settings.get("pan")
    raw_pan_expression = False
    if isinstance(pan, str) and pan.strip():
        try:
            float(pan)
        except (TypeError, ValueError):
            raw_pan_expression = True
    if raw_pan_expression:
        chain.append(f"pan={pan.strip()}")
    else:
        # Numeric pan is normalized to -1 (left) .. +1 (right).
        # Normalize every source to stereo, then apply a frame-
        # evaluated balance expression. This duplicates mono
        # sources but preserves independent left/right channels
        # for stereo assets instead of collapsing them to mono.
        raw_pan = pan if pan is not None else clip.get("pan", 0.0)
        try:
            pan_value = float(raw_pan)
        except (TypeError, ValueError):
            pan_value = 0.0
        pan_tracks = [
            item for item in clip.get("keyframes", [])
            if isinstance(item, dict) and str(item.get("property", "")) in {"audio.pan", "pan"}
        ]
        if pan_tracks or abs(pan_value) > 1e-9:
            pan_expr = _keyframe_expr(clip, ("audio.pan", "pan"), pan_value, clip_start, tps, time_variable=audio_keyframe_time)
            pan_expr = f"clip(({pan_expr}),-1,1)"
            left_expr = f"val(0)*(1-max(({pan_expr}),0))"
            right_expr = f"val(1)*(1+min(({pan_expr}),0))"
            chain.extend([
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo",
                f"aeval=exprs={_expr_arg(left_expr + '|' + right_expr)}:c=stereo",
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo",
            ])

    fade_in = _num(audio_settings.get("fade_in", 0.0), 0.0)
    fade_out = _num(audio_settings.get("fade_out", 0.0), 0.0)
    envelope = []
    if fade_in > 0:
        envelope.append(f"clip(({fade_clock})/{fade_in:.12f},0,1)")
    if fade_out > 0:
        envelope.append(f"clip(({authored_duration:.12f}-({fade_clock}))/{fade_out:.12f},0,1)")
    if envelope:
        chain.append(f"aeval=exprs={_expr_arg('val(ch)*('+ '*'.join(envelope)+')')}:c=same")
    return chain


def _build_audio_bus_tree(
    specs: list[dict[str, Any]], groups: dict[str, dict[str, Any]], tracks: list[dict[str, Any]],
    filters: list[str], warnings: list[dict[str, Any]], input_meta: list[dict[str, Any]],
    *, duration_tick: int, tps: int, routing_sequence: dict[str, Any] | None = None,
) -> str | None:
    """Mix child clips, process tracks, then process each containing sequence.

    Every input is on the final 48-kHz sample grid. Unnormalized float sums
    make grouping transparent and prevent mute/input-count dependent gain.
    Clip automation is evaluated before this stage; container automation is
    evaluated in its containing sequence's authored clock, once after mixing.
    """
    track_map = {str(track['id']): track for track in tracks}
    buckets: dict[str | None, list[dict[str, Any]]] = {}
    for spec in specs:
        buckets.setdefault(spec.get('group_id'), []).append(copy.deepcopy(spec))
    next_label = 0

    def label() -> str:
        nonlocal next_label
        next_label += 1
        return f'abus{next_label}'

    def mix(items: list[str]) -> str:
        target = label()
        filters.append(''.join(f'[{item}]' for item in items)
                       + f'amix=inputs={len(items)}:duration=longest:dropout_transition=0:normalize=0[{target}]')
        return target

    def scope(items: list[dict[str, Any]], scope_id: str | None) -> str | None:
        routed = scope_id is None and routing_sequence is not None and routing_sequence.get('audio_routing') is not None
        if not items and not routed:
            return None
        voices: list[dict[str, Any]] = []
        ducked: list[dict[str, Any]] = []
        for item in items:
            track = track_map[item['track_id']]
            control = track.get('audio') if isinstance(track.get('audio'), dict) else {}
            audio = item.get('audio') or {}
            role = str(audio.get('role', control.get('role', track.get('role') or 'other'))).lower()
            if role in {'voice', 'dialogue', 'narration', 'speech'}:
                voices.append(item)
            if role in {'music', 'bgm', 'background'} and (
                audio.get('duck_under_voice') or isinstance(audio.get('ducking'), dict)
                or control.get('duck_under_voice') or track.get('duck_under_voice')
            ):
                ducked.append(item)
        if voices and ducked:
            detectors: list[str] = []
            for voice in voices:
                audible, detector = label(), label()
                filters.append(f'[{voice["label"]}]asplit=2[{audible}][{detector}]')
                voice['label'] = audible
                detectors.append(detector)
            detector_bus = mix(detectors)
            sidechains = [label() for _ in ducked]
            filters.append(f'[{detector_bus}]asplit={len(sidechains)}'+''.join(f'[{v}]' for v in sidechains))
            for item, detector in zip(ducked, sidechains):
                target = label()
                filters.append(f'[{item["label"]}][{detector}]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300:makeup=1[{target}]')
                item['label'] = target
            warnings.append({'code':'AUDIO_DUCKING_APPLIED','scope_id':scope_id,
                             'voice_inputs':len(voices),'ducked_inputs':len(ducked),
                             'message':'已在所属序列内使用本地 sidechaincompress；检测支路显式拆分，其他序列不参与'})
        by_track: dict[str, list[str]] = {}
        for item in items:
            by_track.setdefault(item['track_id'], []).append(item['label'])
        if routed:
            from .audio_routing import compile_graph
            return compile_graph(routing_sequence, by_track, filters, input_meta, warnings, tps=tps,
                                 process=lambda clip, control: _audio_processing_filters(
                                     clip, control, tps, authored_duration=duration_tick/tps))
        outputs = []
        for track_id, children in by_track.items():
            track = track_map[track_id]
            control = copy.deepcopy(track.get('audio') or {})
            # Track fades have no authored clip interval. Keep them explicit
            # rather than pretending they mean each child's fade envelope.
            for field in ('fade_in', 'fade_out'):
                if control.pop(field, None):
                    warnings.append({'code':'RENDER_FEATURE_UNSUPPORTED','track_id':track_id,
                                     'feature':'track_audio.'+field,'message':'轨道没有片段包络；请在片段或序列容器上声明音频淡入淡出'})
            mixed = mix(children)
            chain = _audio_processing_filters({}, control, tps)
            if chain:
                target = label()
                filters.append(f'[{mixed}]'+','.join(chain)+f'[{target}]')
                mixed = target
            outputs.append(mixed)
            input_meta.append({'kind':'audio-track-bus','track_id':track_id,'scope_id':scope_id,
                               'child_input_count':len(children),'mixing':'float-sum-normalize-disabled',
                               'processing':copy.deepcopy(control),'sample_rate':48000})
        return mix(outputs)

    for group_id, group in reversed(list(groups.items())):
        items = buckets.get(group_id, [])
        composite = scope(items, group_id)
        if composite is None:
            continue
        clip = group['clip']
        start_tick = int(clip['timeline_start_tick'])
        end_tick = start_tick+int(clip['duration_tick'])
        first = math.ceil(Fraction(start_tick*48000,tps))
        end = math.ceil(Fraction(end_tick*48000,tps))
        if end <= first:
            filters.append(f'[{composite}]anullsink')
            continue
        authored = clip.get('_nested_keyframe_clock') or {'maps':[], 'authored_start':start_tick/tps}
        original_duration = int(clip.get('_composite_authored_duration_tick',clip['duration_tick']))/tps
        # The visible cut can be inside an ancestor's source window. Recover
        # the original container envelope rather than restarting at this cut.
        absolute = f'(t+{first/48000:.12f})'
        fade_clock = f'(({_clock_expression(authored["maps"],absolute,inverse=True)})-{authored["authored_start"]:.12f})'
        sample_clip = copy.deepcopy(clip)
        # Account for ceil-to-sample placement before undoing ancestor maps.
        # _keyframe_expr restores timeline_start itself, so supply the small
        # residual in its local time argument.
        local_time = f'(t+{first/48000-start_tick/tps:.12f})'
        chain = [f'apad=whole_len={end}',f'atrim=start_sample={first}:end_sample={end}','asetpts=N/SR/TB']
        control = copy.deepcopy(clip.get('audio') or {})
        chain.extend(_audio_processing_filters(sample_clip,control,tps,audio_keyframe_time=local_time,
                                               fade_clock=fade_clock,authored_duration=original_duration))
        # Effects such as reverb may have tails. The container's sample window
        # clips them before the bus is placed back on its parent's timeline.
        chain.extend(['aresample=48000',f'apad=whole_len={end-first}',f'atrim=end_sample={end-first}',
                      'asetpts=N/SR/TB',f'adelay={first}S:all=1'])
        target = label()
        filters.append(f'[{composite}]'+','.join(chain)+f'[{target}]')
        buckets.setdefault(group['parent_id'], []).append({'label':target,'group_id':group['parent_id'],
                   'track_id':group['track_id'],'clip_id':group_id,'audio':control})
        input_meta.append({'kind':'sequence-audio-bus','clip_id':group_id,'parent_id':group['parent_id'],
                           'sequence_id':clip.get('sequence_id'),'child_input_count':len(items),
                           'sample_rate':48000,'start_sample':first,'end_sample':end,
                           'mixing':'float-sum-normalize-disabled','processing':control,
                           'authored_clock':copy.deepcopy(authored),
                           'processing_order':['child-clips','local-ducking','track-sum','track-processing',
                                               'sequence-sum','container-volume-effects-pan-fade','sample-window'],
                           'intermediate_files':0})
    root_inputs = buckets.get(None, [])
    root_bus = scope(root_inputs, None)
    input_meta.append({'kind':'sequence-audio-root','sample_rate':48000,
                       'output_samples':max(1,round(Fraction(duration_tick*48000,tps))),
                       'child_input_count':len(root_inputs),'mixing':'float-sum-normalize-disabled',
                       'automatic_limiter':False,'has_audible_inputs':root_bus is not None})
    return root_bus


def _native_reverse_chain(root,uri,asset,metadata,decoder,inputs,video_input,clock_filter,runtime,clip_id):
    from .reverse_video_clock import reserve_buffer
    try:
        reserve_buffer(runtime,metadata,clip_id)
        return [f'{video_input}trim=start_frame={metadata["source_frame_start"]}:end_frame={metadata["source_frame_end_exclusive"]}',
                'reverse',clock_filter],None
    except AppError as caught:
        if caught.code!='REVERSE_VIDEO_BUFFER_BUDGET_EXCEEDED':raise
    from .reverse_cache import plan,input_orientation
    job=plan(root,uri,asset['sha256'],metadata,decoder=decoder)
    assert inputs[-2]=='-i';inputs[-1]=job['output']
    orientation=input_orientation(metadata)
    if decoder:
        assert inputs[-4]=='-c:v';inputs[-3]='ffv1';inputs[-2:-2]=orientation
    else:inputs[-2:-2]=['-c:v','ffv1',*orientation]
    metadata.update(frame_buffer_strategy='native-sequential-lossless-reverse-cache',
        cache_storage_clock='25Hz-frame-index-only-original-intervals-reapplied',planned_chunk_count=len(job['recipe']['ranges']))
    return [f'{video_input}{clock_filter}'],job


def build_filter_graph(root: Path, project: dict[str, Any], sequence: dict[str, Any], *, _video_only: bool = False,
                       _inline_stack: tuple[str, ...] = (), _allow_audio_only: bool = False,
                       _effect_runtime: EffectAutomation | None = None,
                       _frame_index_context=None, _persist_video_index: bool = False,
                       _audio_clock_context=None,
                       _projection_runtime=None,
                       _cancel_file: Path | None = None) -> tuple[list[str], str, list[dict[str, Any]], list[dict[str, Any]]]:
    if any(isinstance(c.get('generator'),dict) and c['generator'].get('type')=='particles'
           for s in project['sequences'] for t in s['tracks'] for c in t['clips']):
        raise AppError('PARTICLE_NATIVE_PIPELINE_REQUIRED','可编辑粒子源要求显式的原生浮点 pixel_pipeline；旧版图不会静默丢弃生成器',exit_code=2)
    if any('sequence_clip_id' in c for s in project['sequences'] for t in s['tracks'] for c in t['clips']):
        raise AppError('SEQUENCE_SELECTION_NATIVE_REQUIRED', '作者单片段输出必须由浮点宿主渲染；音频需先编译独立选择实例', exit_code=2)
    if _frame_index_context is None:
        from .native_video_index import IndexContext
        _frame_index_context=IndexContext(root,persist=_persist_video_index,cancel_file=_cancel_file)
    if _audio_clock_context is None:
        from .native_audio_clock import AudioClockContext
        _audio_clock_context=AudioClockContext(root,persist=_persist_video_index,cancel_file=_cancel_file)
    root_effect_runtime = _effect_runtime is None
    if _effect_runtime is None:
        base = project['settings']['timebase']
        fps = base['display_fps']
        _effect_runtime = EffectAutomation(root, str(Fraction(fps['num'], fps['den'])), int(base['ticks_per_second']))
    def child_builder(*args, **kwargs):
        return build_filter_graph(*args, **kwargs, _effect_runtime=_effect_runtime,
                                  _frame_index_context=_frame_index_context,
                                  _audio_clock_context=_audio_clock_context,
                                  _projection_runtime=_projection_runtime)
    if any(c.get('tracking_binding') for s in project.get('sequences',[]) for t in s.get('tracks',[]) for c in t.get('clips',[])):
        from .bindings import compile_project_bindings,validate_project_bindings
        findings = validate_project_bindings(project,root)
        if findings:
            raise AppError('TRACK_BIND_GEOMETRY_INVALID','绑定引用或源文件完整性检查失败',exit_code=2,cause=json.dumps(findings,ensure_ascii=False))
        project = compile_project_bindings(project)
        sequence = next(s for s in project['sequences'] if s['id'] == sequence['id'])
    project, sequence, source_transition_plan = _compile_source_transitions(project, sequence['id'])
    project, sequence, window_inputs, window_filters, window_meta = _prepare_clip_windows(
        root, project, sequence, child_builder, stack=_inline_stack, video_only=_video_only)
    project, sequence, inline_inputs, inline_filters, inline_meta = _prepare_inline_sequences(
        root, project, sequence, child_builder, stack=_inline_stack)
    if window_inputs or window_filters:
        from .inline_sequences import graph_namespace
        inline_filters = [graph_namespace(g, 'afterwindow_', window_inputs.count('-i')) for g in inline_filters]
        for a in project['assets']:
            if a.get('_inline_video'):
                a['_inline_video']['label'] = 'afterwindow_'+a['_inline_video']['label']
            if a.get('_inline_audio'):
                a['_inline_audio']['label'] = 'afterwindow_'+a['_inline_audio']['label']
    inline_inputs = window_inputs+inline_inputs
    inline_filters = window_filters+inline_filters
    inline_meta = window_meta+inline_meta
    settings = project["settings"]
    tps = int(settings["timebase"]["ticks_per_second"])
    root_canvas = sequence_canvas(project, sequence)
    width, height = root_canvas['width'], root_canvas['height']
    fps = settings["timebase"].get("display_fps", {"num": 30, "den": 1})
    fps_value = f"{fps['num']}/{fps['den']}"
    frame_duration = max(1e-6, float(fps.get("den", 1)) / max(1.0, float(fps.get("num", 30))))
    duration = max(_sec(int(sequence.get("duration_tick", 1)), tps), 1 / max(1, int(fps["num"])))
    raw_output = settings.get("output") if isinstance(settings.get("output"), dict) else {}
    raw_video_output = raw_output.get("video") if isinstance(raw_output.get("video"), dict) else {}
    transparent_canvas = str(raw_video_output.get("pixel_format", "")).lower() in ALPHA_OUTPUT_PIXEL_FORMATS
    color_tone_map = str((settings.get("color") or {}).get("tone_map", (settings.get("color") or {}).get("tone_mapping", "none"))).lower() if isinstance(settings.get("color"), dict) else "none"
    assets = asset_map(project)
    inputs: list[str] = list(inline_inputs)
    filters: list[str] = list(inline_filters)
    video_labels: list[str] = []
    video_positions: list[str] = []
    video_specs: list[dict[str, Any]] = []
    audio_specs: list[dict[str, Any]] = []
    input_meta: list[dict[str, Any]] = list(inline_meta)
    if source_transition_plan:
        input_meta.append({'kind': 'source-transition-plan', **source_transition_plan})
    warnings: list[dict[str, Any]] = []
    for surface in inline_meta:
        for finding in surface.get('warnings', []):
            warnings.append({**finding, 'inline_sequence_path':[
                surface['sequence_id'], *finding.get('inline_sequence_path', [])]})
    subtitle_overlays: list[dict[str, Any]] = []
    adjustment_layers: list[tuple[str, list[Any], float, float]] = []
    raw_adjustments = settings.get("adjustments")
    if isinstance(raw_adjustments, list):
        for adjustment_index, raw_layer in enumerate(raw_adjustments):
            layer_id = f"adjustment_{adjustment_index}"
            if isinstance(raw_layer, str):
                adjustment_layers.append((layer_id, [raw_layer], 0.0, duration))
                continue
            if not isinstance(raw_layer, dict) or raw_layer.get("enabled", True) is False:
                continue
            if isinstance(raw_layer.get("effects"), list):
                effects = list(raw_layer["effects"])
            elif raw_layer.get("type"):
                effects = [raw_layer]
            else:
                effects = []
            if effects:
                start_tick = max(0, _tick(raw_layer.get("start_tick"), 0))
                duration_tick = _tick(raw_layer.get("duration_tick"), 0)
                start = min(duration, _sec(start_tick, tps))
                end = duration if duration_tick <= 0 else min(duration, start + _sec(duration_tick, tps))
                adjustment_layers.append((str(raw_layer.get("id", layer_id)), effects, start, end))
    has_adjustments = bool(adjustment_layers)
    index = physical_index = inputs.count('-i')
    composite_groups: dict[str, dict[str, Any]] = {}
    render_tracks = _flatten_sequence_tracks(project, sequence, warnings, groups=composite_groups)
    sampling_config = _sequence_sampling_configuration(settings.get('sequence_sampling'))
    projection = projection_budget({k:g for k,g in composite_groups.items() if g.get('video_enabled',True)}, sampling_config)
    input_meta.append(projection)
    if inline_meta:
        input_meta.append(_inline_sequence_budget(inline_meta, projection, sampling_config))
    # A recursive temporal graph may consume one external surface while the
    # project also carries surfaces owned by its caller. Only drain unused
    # outputs actually produced by this graph, never the caller's other pads.
    owned_surfaces = {item.get('asset_id') for item in inline_meta}
    surface_labels = {}
    for asset_id, asset in assets.items():
        if not asset.get('_inline_video'):
            continue
        count = sum(c.get('asset_id') == asset_id for t in render_tracks if t.get('kind') == 'video' for c in t.get('clips', []))
        source_label = asset['_inline_video']['label']
        if count:
            labels = [f'{source_label}_use{i}' for i in range(count)]
            filters.append(f'[{source_label}]split={count}'+''.join(f'[{label}]' for label in labels))
            surface_labels[asset_id] = labels
        elif asset_id in owned_surfaces:
            filters.append(f'[{source_label}]nullsink')
    audio_surface_labels = {}
    for aid, asset in assets.items():
        if not asset.get('_inline_audio'):
            continue
        count = 0 if _video_only else sum(c.get('asset_id') == aid for t in render_tracks if t.get('kind') == 'audio' for c in t.get('clips', []))
        source_label = asset['_inline_audio']['label']
        if count:
            labels = [f'{source_label}_audio{i}' for i in range(count)]
            filters.append(f'[{source_label}]asplit={count}'+''.join(f'[{label}]' for label in labels))
            audio_surface_labels[aid] = labels
        elif aid in owned_surfaces:
            filters.append(f'[{source_label}]anullsink')
    local_audio_engine = _audio_stretch_configuration(root, settings.get('audio_stretch'))
    for track in sorted(render_tracks, key=lambda item: int(item.get("order", 0))):
        if _video_only and track.get('kind') == 'audio':
            continue
        track_audio = track.get("audio") if isinstance(track.get("audio"), dict) else {}
        track_id = str(track.get("id"))
        if track.get("muted"):
            continue
        for clip in sorted(track.get("clips", []), key=lambda item: int(item.get("timeline_start_tick", 0))):
            clip_canvas = composite_groups[clip['_composite_group']]['canvas'] if clip.get('_composite_group') else root_canvas
            width, height = clip_canvas['width'], clip_canvas['height']
            if clip.get('_tracking_binding_plan'):
                binding_plan = clip['_tracking_binding_plan']
                input_meta.append({'kind':'tracking-binding','clip_id':clip['id'],**binding_plan})
                warnings.extend({'code':'TRACK_BIND_REVIEW_REQUIRED','clip_id':clip['id'],'message':message} for message in binding_plan['warnings'])
                if clip.get('_nested_parent_transforms') or clip.get('_nested_parent_transform'):
                    warnings.append({'code':'TRACK_BIND_NESTED_COORDINATES_APPROXIMATE','clip_id':clip['id'],'message':'绑定随嵌套父层展开；父枢轴与不同坐标空间仍需视觉验收'})
            asset = assets.get(clip.get("asset_id"))
            if clip.get('_presentation_surface'):
                surface = clip['_presentation_surface']
                start_tick = clip['timeline_start_tick']
                start, span = start_tick/tps, clip['duration_tick']/tps
                if surface.get('video'):
                    label = f'window_picture{index}'
                    clock_filter, clock_metadata = working_clock(1/Fraction(fps_value), fps_value, tps)
                    first_frame, end_frame = frame_interval(start_tick,clip['duration_tick'],tps,fps_value)
                    clock_expression=f'PTS*TB+({start_tick}/{tps})'
                    expected_frames=surface.get('video_frame_count')
                    if isinstance(expected_frames,int) and not isinstance(expected_frames,bool) and expected_frames>0:
                        clock_expression=f'if(gte(N,{expected_frames}),({start_tick+clip["duration_tick"]}/{tps}),{clock_expression})'
                        clock_metadata['complete_surface_eof_guard']={'expected_frames':expected_frames,'author_end_tick':start_tick+clip['duration_tick']}
                    filters.append(f'[{surface["video"]}]{clock_filter},setpts='+_expr_arg('('+clock_expression+')/TB')+','
                                   f'fps={fps_value}:round=up:eof_action=pass,'
                                   f'trim=start_pts={first_frame}:end_pts={end_frame}[{label}]')
                    input_meta.append({'kind':'video-frame-clock','clip_id':clip['id'],
                                       'surface':'presentation-window',**clock_metadata,
                                       'output_frame_start':first_frame,'output_frame_end_exclusive':end_frame})
                    video_labels.append(label)
                    video_specs.append({'label':label,'position':"x=0:y=0",'track_id':track_id,
                        'track_order':int(track.get('order',0)),'layer_order':len(video_specs),
                        'group_id':clip.get('_composite_group'),'clock':copy.deepcopy(clip.get('_nested_keyframe_clock')),
                        'clip_id':clip['id'],'keyframes':copy.deepcopy(clip.get('keyframes',[])),
                        'start':start,'duration':span,'incoming':{},'outgoing':{},'blend':clip.get('blend')})
                if surface.get('audio') and not _video_only and clip.get('_audio_scope_enabled',True):
                    label = f'window_sound{index}'
                    delay = math.ceil(Fraction(start_tick*48000,tps))
                    filters.append(f'[{surface["audio"]}]adelay={delay}S:all=1[{label}]')
                    audio_specs.append({'label':label,'group_id':clip.get('_composite_group'),
                        'track_id':track_id,'clip_id':clip['id'],'audio':copy.deepcopy(clip.get('audio',{}))})
                elif surface.get('audio'):
                    filters.append(f'[{surface["audio"]}]anullsink')
                index += 1
                continue
            if track.get("kind") == "subtitle":
                subtitle = clip.get("subtitle") if isinstance(clip.get("subtitle"), dict) else None
                if subtitle is None and asset and asset.get("kind") == "subtitle":
                    subtitle = {"asset_uri": asset.get("uri")}
                elif subtitle is not None and asset and asset.get('kind') == 'subtitle' and not subtitle.get('asset_uri') and 'text' not in subtitle:
                    subtitle = {'asset_uri': asset.get('uri'), **subtitle}
                if subtitle is None:
                    warnings.append({"code": "SUBTITLE_TRACK_EMPTY", "clip_id": clip.get("id"), "feature": "subtitle_track", "message": "独立字幕轨道片段缺少内联 subtitle 或 subtitle 资产"})
                    continue
                clip_start = _sec(int(clip.get("timeline_start_tick", 0)), tps)
                clip_duration = max(0.001, _sec(int(clip.get("duration_tick", 1)), tps))
                subtitle_filter, subtitle_clock = _compiled_subtitle_filter(
                    root, subtitle, warnings, clip, clip_start, clip_duration,
                    tps, fps_value, assets, independent=True,
                )
                if subtitle_filter:
                    input_meta.append({'kind': 'subtitle', 'clip_id': clip.get('id'),
                                       'subtitle_time_mapping': copy.deepcopy(subtitle_clock)})
                    animation = subtitle.get("animation") if isinstance(subtitle.get("animation"), dict) else subtitle.get("style", {}).get("animation") if isinstance(subtitle.get("style"), dict) and isinstance(subtitle.get("style", {}).get("animation"), dict) else {}
                    animation_type = str(animation.get("type", "")).lower().replace("-", "_")
                    subtitle_overlays.append({
                        "clip_id": str(clip.get("id")),
                        "track_id": str(track.get("id")),
                        "track_order": int(track.get("order", 0)),
                        "clip": copy.deepcopy(clip),
                        "group_id": clip.get('_composite_group'),
                        "filter": subtitle_filter,
                        "start": clip_start,
                        "duration": clip_duration,
                        "animation_type": animation_type,
                        "animation": animation,
                        "subtitle_clock": subtitle_clock,
                    })
                continue
            if not asset:
                continue
            for keyframe_track in clip.get("keyframes", []):
                for keyframe in keyframe_track.get("keyframes", []):
                    if keyframe.get("interpolation") == "bezier" and not isinstance(keyframe.get("control_points"), list):
                        warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "bezier_keyframe", "message": "Bezier 关键帧未提供控制点，使用默认三次曲线控制点"})
            inline_surface = asset.get('_inline_video')
            uri = None if inline_surface else Path(str(asset["uri"]))
            if uri is not None:
                if not uri.is_absolute():
                    uri = root / uri
                if not uri.exists():
                    raise AppError("ASSET_FILE_MISSING", f"渲染输入不存在: {uri}", exit_code=3, path=str(uri))
            source_index = physical_index
            kind = asset.get("kind", "video")
            if kind in {"video", "image"} and track.get("kind") == "video":
                alpha_decoder = None
                reverse_cache_job = None
                if inline_surface:
                    video_input = '['+surface_labels[asset['id']].pop(0)+']'
                elif kind == "image":
                    inputs.extend(["-loop", "1", "-i", str(uri)])
                    physical_index += 1
                else:
                    alpha_decoder = _alpha_video_decoder(asset)
                    if alpha_decoder:
                        inputs.extend(['-c:v', alpha_decoder])
                    inputs.extend(["-i", str(uri)])
                    physical_index += 1
                if not inline_surface:
                    video_input = f'[{source_index}:v]'
                src_in = _sec(int(clip.get("source_in_tick", 0)), tps)
                src_out = _sec(int(clip.get("source_out_tick", clip.get("duration_tick", 1))), tps)
                start = _sec(int(clip.get("timeline_start_tick", 0)), tps)
                label = f"v{index}"
                speed = _num(clip.get("speed", 1.0), 1.0)
                if speed <= 0:
                    raise AppError("SPEED_INVALID", "speed 必须大于 0", exit_code=2, path=f"clips[{clip.get('id')}].speed")
                source_span_tick = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
                speed_segments = _speed_curve_segments(clip, source_span_tick, tps)
                curve_duration = speed_curve_duration_seconds(clip, source_span_tick, tps)
                if speed_segments:
                    mapped_speed_segments = _reverse_speed_curve_segments(speed_segments) if bool(clip.get("reverse")) else speed_segments
                    setpts = _speed_curve_setpts(mapped_speed_segments, start)
                else:
                    origin = f'({int(clip.get("timeline_start_tick", 0))}/{tps})'
                    setpts = f"setpts=(PTS-STARTPTS)/{speed:.8f}+{origin}/TB" if abs(speed - 1.0) > 1e-9 else f"setpts=PTS-STARTPTS+{origin}/TB"
                transforms = _transform_exprs(clip, start, tps)
                chain = [f"{video_input}trim=start={src_in:.6f}:end={src_out:.6f}"]
                nested_maps = clip.get('_nested_time_maps')
                native_nested = bool(nested_maps) and not inline_surface and kind=='video'
                if native_nested:
                    from .reverse_video_clock import reverse_intervals,forward_intervals
                    nominal_value=None
                    nested_input_base,nested_clock_source=registered_time_base(asset,uri)
                    native_filter,native_clock=working_clock(nested_input_base,fps_value,tps)
                    common=dict(expected_time_base=nested_input_base,decoder=alpha_decoder,
                        index_context=_frame_index_context,source_sha256=asset['sha256'])
                    if bool(clip.get('reverse')):
                        _,_,native_reverse,sampling_metadata=reverse_intervals(uri,
                            int(clip.get('source_in_tick',0)),int(clip.get('source_out_tick',1)),
                            tps,native_clock['working_time_base'],**common)
                        chain,reverse_cache_job=_native_reverse_chain(root,uri,asset,sampling_metadata,
                            alpha_decoder,inputs,video_input,native_filter,_effect_runtime,clip.get('id'))
                        source_clock=f'({int(clip.get("source_out_tick",1))}/{tps})-(({native_reverse})*TB)'
                    else:
                        first,end,source_clock,sampling_metadata=forward_intervals(uri,
                            int(clip.get('source_in_tick',0)),int(clip.get('source_out_tick',1)),tps,**common)
                        chain=[f'{video_input}trim=start_frame={first}:end_frame={end}',native_filter]
                    setpts='setpts='+_expr_arg(f'({_clock_expression(nested_maps,source_clock,scratch_register=0)})/TB')
                    curve_duration=int(clip.get('duration_tick',1))/tps
                    output_rate=Fraction(fps_value)
                    first_output_frame=math.ceil(Fraction(int(clip.get('timeline_start_tick',0)),tps)*output_rate)
                    end_output_frame=math.ceil(Fraction(int(clip.get('timeline_start_tick',0))+int(clip.get('duration_tick',1)),tps)*output_rate)
                    sampling_metadata.update(output_frame_start=first_output_frame,output_frame_end_exclusive=end_output_frame,
                        output_interval='authored-half-open-on-global-cfr-grid')
                elif isinstance(nested_maps, list) and nested_maps:
                    source_probe = asset.get('probe', {}).get('video', {})
                    try:
                        nominal_fps = Fraction(str(source_probe.get('fps') or fps_value))
                        if nominal_fps <= 0 or nominal_fps > 1000:
                            raise ValueError('invalid source frame rate')
                    except (ValueError, ZeroDivisionError):
                        nominal_fps = Fraction(fps_value)
                    nominal_value = f'{nominal_fps.numerator}/{nominal_fps.denominator}'
                    # Make the display clock explicit before a possible
                    # reverse. This is CFR normalization, not a claim of
                    # retaining every original VFR presentation timestamp.
                    # A decoded CFR frame represents [k/fps, (k+1)/fps).
                    # Keep both partially covered endpoint frames. Decimal
                    # trim seconds otherwise round to the coarse 1/fps TB,
                    # and can remove an endpoint or the entire short clip.
                    first_source_frame = math.floor(Fraction(int(clip.get('source_in_tick', 0)), tps) * nominal_fps)
                    end_source_frame = math.ceil(Fraction(int(clip.get('source_out_tick', 1)), tps) * nominal_fps)
                    source_frame_count = end_source_frame - first_source_frame
                    chain = [f'{video_input}fps={nominal_value}:start_time=0:round=up:eof_action=pass',
                             f'trim=start_pts={first_source_frame}:end_pts={end_source_frame}']
                    reverse_source = bool(clip.get('reverse'))
                    first_source_time, eof_source_time = (src_out, src_in) if reverse_source else (src_in, src_out)
                    interior_source = f'({end_source_frame}-N)/({nominal_value})' if reverse_source else '(PTS*TB)'
                    # setpts evaluates N once more for the native EOF event.
                    # Map that event to the true authored boundary after all
                    # selected frames, including a partial final interval.
                    # A genuinely short input cannot reach this count and is
                    # not silently extended to the declared source endpoint.
                    source_clock = (f'if(eq(N,0),{first_source_time:.12f},'
                                    f'if(gte(N,{source_frame_count}),{eof_source_time:.12f},{interior_source}))')
                    setpts = 'setpts=' + _expr_arg(f'({_clock_expression(nested_maps, source_clock, scratch_register=0)})/TB')
                    curve_duration = int(clip.get('duration_tick', 1)) / tps
                    output_rate = Fraction(fps_value)
                    first_output_frame = math.ceil(Fraction(int(clip.get('timeline_start_tick', 0)), tps) * output_rate)
                    end_output_frame = math.ceil(Fraction(int(clip.get('timeline_start_tick', 0)) + int(clip.get('duration_tick', 1)), tps) * output_rate)
                    sampling_metadata = {
                        'protocol': 'covering-source-cfr-half-open-v1',
                        'source_frame_start': first_source_frame, 'source_frame_end_exclusive': end_source_frame,
                        'expected_source_frames': source_frame_count,
                        'output_frame_start': first_output_frame, 'output_frame_end_exclusive': end_output_frame,
                        'first_source_seconds': first_source_time, 'eof_source_seconds': eof_source_time,
                        'eof_event': 'authored-boundary-after-expected-source-frame-count',
                        'output_interval': 'authored-half-open-on-global-cfr-grid',
                    }
                    warnings.append({'code': 'NESTED_SOURCE_CFR_NORMALIZED', 'clip_id': clip.get('id'),
                                     'fps': nominal_value, 'message': '嵌套非线性变速以登记帧率建立源显示时钟；VFR 原始时间戳等效未验收'})
                if bool(clip.get("reverse")) and not native_nested:
                    chain.append("reverse")
                input_base, clock_source = registered_time_base(asset,uri,
                    normalized_rate=nominal_value if nested_maps else fps_value if inline_surface else None)
                clock_filter, clock_metadata = working_clock(input_base, fps_value, tps)
                clock_metadata['input_time_base_source'] = clock_source
                if native_nested:
                    clock_metadata.update(source_clock_anchor='original-native-intervals-before-nested-author-map',
                                          native_source_intervals=sampling_metadata)
                if not nested_maps and not inline_surface and bool(clip.get('reverse')) and kind == 'video':
                    from .reverse_video_clock import reverse_intervals, reserve_buffer
                    first_source, end_source, reverse_clock, reverse_metadata = reverse_intervals(
                        uri, int(clip.get('source_in_tick', 0)), int(clip.get('source_out_tick', 1)),
                        tps, clock_metadata['working_time_base'], expected_time_base=input_base,decoder=alpha_decoder,
                        index_context=_frame_index_context,source_sha256=asset['sha256'])
                    chain,reverse_cache_job=_native_reverse_chain(root,uri,asset,reverse_metadata,
                        alpha_decoder,inputs,video_input,clock_filter,_effect_runtime,clip.get('id'))
                    clock_base = Fraction(clock_metadata['working_time_base'])
                    timeline_origin = Fraction(int(clip.get('timeline_start_tick', 0)),tps)/clock_base
                    assert timeline_origin.denominator == 1
                    if speed_segments:
                        setpts = _speed_curve_setpts(speed_segments, 0.,
                            source_expression=f'(({reverse_clock})*TB)',
                            timeline_clock_ticks=int(timeline_origin))
                    else:
                        setpts = 'setpts=' + _expr_arg(f'({reverse_clock})/{speed:.8f}+{int(timeline_origin)}')
                    clock_metadata.update(source_clock_anchor='reversed-native-source-intervals',
                        source_prefix_preserved_for_covering_frame=True, reverse_frame_intervals=reverse_metadata)
                elif not nested_maps and not inline_surface and not bool(clip.get('reverse')):
                    # Keep the frame covering a fractional source in-point.
                    # trim(start=...) followed by PTS-STARTPTS discards it
                    # and restarts the clock at the next decoded frame.
                    # Decode the prefix, anchor at the requested source tick,
                    # and discard its output samples on the global CFR grid.
                    clock_base = Fraction(clock_metadata['working_time_base'])
                    source_origin = Fraction(int(clip.get('source_in_tick', 0)),tps)/clock_base
                    source_end = Fraction(int(clip.get('source_out_tick', 1)),tps)/clock_base
                    timeline_origin = Fraction(int(clip.get('timeline_start_tick', 0)),tps)/clock_base
                    assert source_origin.denominator == source_end.denominator == timeline_origin.denominator == 1
                    chain = [f'{video_input}{clock_filter},trim=end_pts={int(source_end)}']
                    if speed_segments:
                        setpts = _speed_curve_setpts(speed_segments, 0.,
                            source_expression=f'((PTS-{int(source_origin)})*TB)',
                            timeline_clock_ticks=int(timeline_origin))
                    else:
                        setpts = f'setpts=(PTS-{int(source_origin)})/{speed:.8f}+{int(timeline_origin)}'
                    clock_metadata.update(source_clock_anchor='requested-author-source-in-tick',
                        source_prefix_preserved_for_covering_frame=True,
                        source_in_tick=int(clip.get('source_in_tick', 0)))
                elif not native_nested:
                    chain.append(clock_filter)
                chain.append(setpts)
                # A fractional segment boundary must not reset fps rounding
                # to that segment's local phase. Leave start_time unset for
                # composed clocks so every part uses the global frame grid.
                chain.append(f'fps={fps_value}:round=up:eof_action=pass')
                if not nested_maps:
                    exact_start = Fraction(int(clip.get('timeline_start_tick', 0)),tps)
                    content_span = Fraction(str(curve_duration)) if curve_duration is not None else Fraction(source_span_tick,tps)/Fraction(f'{speed:.8f}')
                    first_output_frame = math.ceil(exact_start*Fraction(fps_value))
                    end_output_frame = math.ceil((exact_start+content_span)*Fraction(fps_value))
                chain.append(f'trim=start_pts={first_output_frame}:end_pts={end_output_frame}')
                clock_metadata.update(output_frame_start=first_output_frame,
                    output_frame_end_exclusive=end_output_frame,output_interval='global-CFR-half-open',
                    short_input_padded=False)
                if alpha_decoder:
                    # Pin straight RGBA before blending. Negotiating a decoded
                    # yuva420p directly with an opaque YUV canvas would blend
                    # subsampled chroma using neighbouring alpha coverage.
                    chain.append('format=rgba')
                if kind == "video" and not inline_surface and color_tone_map not in {"", "none"}:
                    chain.extend(_tone_map_filters(settings, warnings, str(clip.get("id")), transparent=transparent_canvas))
                crop = clip.get("crop") if isinstance(clip.get("crop"), dict) else {}
                crop_fit = str(crop.get("fit", crop.get("mode", "fit"))).lower()
                source_probe = asset.get("probe", {}).get("video", {}) if isinstance(asset.get("probe"), dict) else {}
                pixel_format = str(source_probe.get('pix_fmt') or '')
                alpha_padding = clip.get('_window_original_canvas_alpha',transparent_canvas) or alpha_decoder is not None or clip.get('_composite_group') is not None or pixel_format.startswith(('rgba','bgra','argb','abgr','yuva','gbrap','ya')) or pixel_format == 'pal8'
                source_width = max(0, int(_num(source_probe.get("width", 0), 0)))
                source_height = max(0, int(_num(source_probe.get("height", 0), 0)))
                dynamic_crop_rendered = False
                if crop:
                    crop_unit = str(crop.get("unit", "pixels")).lower()
                    normalized_crop = crop_unit in {"normalized", "relative"}
                    default_width = 1.0 if normalized_crop else source_width
                    default_height = 1.0 if normalized_crop else source_height
                    raw_width = _num(crop.get("width", crop.get("w", default_width)), default_width)
                    raw_height = _num(crop.get("height", crop.get("h", default_height)), default_height)
                    raw_x = _num(crop.get("x", 0), 0)
                    raw_y = _num(crop.get("y", 0), 0)
                    dynamic_x = _crop_has_keyframe(clip, crop, ("crop.x", "x"))
                    dynamic_y = _crop_has_keyframe(clip, crop, ("crop.y", "y"))
                    dynamic_width = _crop_has_keyframe(clip, crop, ("crop.width", "crop.w", "width", "w"))
                    dynamic_height = _crop_has_keyframe(clip, crop, ("crop.height", "crop.h", "height", "h"))
                    if crop_unit in {"normalized", "relative"} and source_width and source_height:
                        crop_width = int(round(raw_width * source_width))
                        crop_height = int(round(raw_height * source_height))
                        crop_x = int(round(raw_x * source_width))
                        crop_y = int(round(raw_y * source_height))
                    else:
                        crop_width = int(round(raw_width))
                        crop_height = int(round(raw_height))
                        crop_x = int(round(raw_x))
                        crop_y = int(round(raw_y))
                    crop_x = max(0, crop_x)
                    crop_y = max(0, crop_y)
                    if source_width:
                        crop_x = min(crop_x, max(0, source_width - 2))
                        crop_width = min(crop_width, source_width if dynamic_x else max(2, source_width - crop_x))
                    if source_height:
                        crop_y = min(crop_y, max(0, source_height - 2))
                        crop_height = min(crop_height, source_height if dynamic_y else max(2, source_height - crop_y))
                    crop_width = max(2, crop_width)
                    crop_height = max(2, crop_height)
                    if (dynamic_width or dynamic_height) and source_width and source_height:
                        chain.extend(_dynamic_crop_filters(clip, crop, width, height, source_width, source_height, start, tps, alpha=alpha_padding,projection=_projection_runtime))
                        dynamic_crop_rendered = True
                    elif crop_width >= 2 and crop_height >= 2:
                        if dynamic_x or dynamic_y:
                            x_expression = _crop_keyframe_expr(clip, crop, ("crop.x", "x"), raw_x, start, tps)
                            y_expression = _crop_keyframe_expr(clip, crop, ("crop.y", "y"), raw_y, start, tps)
                            if crop_unit in {"normalized", "relative"}:
                                x_expression = f"({x_expression})*iw"
                                y_expression = f"({y_expression})*ih"
                            # FFmpeg crop accepts per-frame x/y expressions, but
                            # its output dimensions must stay fixed.  Clamp the
                            # animated origin so every frame remains in bounds.
                            x_expression = f"max(0,min(iw-out_w,({x_expression})))"
                            y_expression = f"max(0,min(ih-out_h,({y_expression})))"
                            chain.append(f"crop={crop_width}:{crop_height}:x={_expr_arg(x_expression)}:y={_expr_arg(y_expression)}:exact=1")
                        else:
                            chain.append(f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y}:exact=1")
                if not dynamic_crop_rendered:
                    if not crop and source_width == width and source_height == height:
                        # A native-size surface needs no resampling. Avoid a
                        # redundant rgba -> float -> rgba conversion: swscale
                        # can round an 8-bit alpha ramp upwards by one here,
                        # which would accumulate through compound levels.
                        chain.append('setsar=1')
                    elif crop_fit == "fill":
                        chain.extend(_scale_filters(f"scale={width}:{height}:force_original_aspect_ratio=increase", alpha=alpha_padding))
                        chain.extend([f"crop={width}:{height}:(iw-ow)/2:(ih-oh)/2", "setsar=1"])
                    elif crop_fit == "stretch":
                        chain.extend(_scale_filters(f"scale={width}:{height}", alpha=alpha_padding))
                        chain.append("setsar=1")
                    else:
                        pad_color = 'black@0' if alpha_padding else 'black'
                        chain.extend(_scale_filters(f"scale={width}:{height}:force_original_aspect_ratio=decrease", alpha=alpha_padding))
                        chain.extend([f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={pad_color}", "setsar=1"])
                clip_content_duration = max(
                    0.001,
                    curve_duration if curve_duration is not None else (src_out - src_in) / max(speed, 1e-9),
                )
                freeze = clip.get("freeze") if isinstance(clip.get("freeze"), dict) else None
                freeze_extra = 0.0
                if freeze:
                    freeze_extra = max(0.0, _sec(int(freeze.get("duration_tick", 0)), tps))
                    if freeze_extra > 0:
                        # The stream is already sampled on the display grid.
                        # Repeat one frame in place, then rebuild its CFR clock;
                        # split/tpad/concat counted the held frame twice and
                        # shifted every later frame away from audio/labels.
                        requested_at = _sec(int(freeze.get("at_tick", int(round(clip_content_duration*tps)))), tps)
                        freeze_at = max(0.0,min(clip_content_duration,requested_at))
                        hold_frames = max(1,int(round(freeze_extra/frame_duration)))
                        # FFmpeg loop starts capturing when its consumed-frame
                        # count reaches start (start=4 holds source index 3).
                        start_frame = max(0,int(math.ceil(freeze_at/frame_duration-1e-8)))
                        first_clock = math.ceil(start/frame_duration-1e-8)*frame_duration
                        chain.append(f"loop=loop={hold_frames}:size=1:start={start_frame}")
                        chain.append(f"setpts=N+{first_output_frame}")
                        if abs(hold_frames*frame_duration-freeze_extra) > 1e-6:
                            warnings.append({"code":"FREEZE_FRAME_QUANTIZED","clip_id":clip.get("id"),"message":"定格时长已量化到显示帧率","requested_seconds":freeze_extra,"actual_seconds":hold_frames*frame_duration})
                # RGBA overlay caches the first secondary raster dimensions.
                # Keep a retimed/animated child on a fixed canvas instead of
                # feeding a scale filter whose output dimensions vary by frame.
                affine_canvas = (bool(clip.get('_source_handle')) or transforms['rotation'] != '0.00000000' or bool(clip.get('_tracking_binding_source'))
                                 or (clip.get('_composite_group') is not None and transforms['scale'] != '1.00000000'))
                if affine_canvas:
                    chain.extend(_affine_video_filters(transforms,projection=_projection_runtime,width=width,height=height))
                elif transforms["scale"] != "1.00000000":
                    scale_expr = _expr_arg(f"max(2,iw*({transforms['scale']}))")
                    height_expr = _expr_arg(f"max(2,ih*({transforms['scale']}))")
                    chain.extend(_scale_filters(f"scale=w={scale_expr}:h={height_expr}:eval=frame", alpha=alpha_padding))
                if transforms["opacity"] != "1.00000000":
                    alpha_expr = f"alpha(X,Y)*clip(({transforms['opacity']}),0,1)"
                    chain.extend(["format=gbrap", f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a={_expr_arg(alpha_expr)}", "format=rgba"])
                chain.extend(
                    _effect_filters(
                        clip.get("effects"),
                        warnings,
                        str(clip.get("id")),
                        root=root,
                        clip=clip,
                        clip_start=start,
                        tps=tps,
                        automation=_effect_runtime,
                        automation_meta=input_meta,
                    )
                )
                if speed_segments and curve_duration is not None and abs(curve_duration - (src_out - src_in) / max(speed, 1e-9)) > 1e-6:
                    speed = max(0.01, (src_out - src_in) / max(1e-9, curve_duration))
                subtitle, subtitle_clock = _compiled_subtitle_filter(
                    root, clip.get('subtitle'), warnings, clip, start,
                    max(0.001, curve_duration if curve_duration is not None else (src_out - src_in) / max(speed, 1e-9)),
                    tps, fps_value, assets,
                    dynamic_raster=not affine_canvas and not bool(re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', transforms['scale'])),
                )
                if subtitle:
                    chain.append(subtitle)
                mask_values: list[dict[str, Any]] = []
                inherited_masks = clip.get("_nested_parent_masks")
                if isinstance(inherited_masks, list):
                    mask_values.extend(item for item in inherited_masks if isinstance(item, dict))
                if isinstance(clip.get("mask"), dict):
                    mask_values.append(clip["mask"])
                for mask_value in mask_values:
                    mask_filter = _mask_filter(
                        mask_value,
                        warnings,
                        str(clip.get("id")),
                        clip=clip,
                        clip_start=start,
                        tps=tps,
                    )
                    if mask_filter:
                        chain.append("format=rgba")
                        chain.append(mask_filter)
                incoming = clip.get("transition_in") if isinstance(clip.get("transition_in"), dict) else {}
                outgoing = clip.get("transition_out") if isinstance(clip.get("transition_out"), dict) else {}
                if not incoming.get('source_transition_id') and str(incoming.get("type", "")).lower() in {"fade", "fade_in", "dissolve"}:
                    chain.append(f"fade=t=in:st=0:d={max(0.001, _num(incoming.get('duration', 0.25), 0.25)):.6f}")
                if not outgoing.get('source_transition_id') and str(outgoing.get("type", "")).lower() in {"fade", "fade_out", "dissolve"}:
                    fade_duration = max(0.001, _num(outgoing.get("duration", 0.25), 0.25))
                    chain.append(f"fade=t=out:st={max(0.0, clip_content_duration + freeze_extra-fade_duration):.6f}:d={fade_duration:.6f}")
                filters.append(",".join(chain) + f"[{label}]")
                video_labels.append(label)
                overlay_x, overlay_y = ('0','0') if affine_canvas else _video_overlay_position(transforms, width, height)
                position_x_expr = _expr_arg(overlay_x)
                position_y_expr = _expr_arg(overlay_y)
                position = f"x={position_x_expr}:y={position_y_expr}"
                video_positions.append(position)
                video_specs.append({
                    "label": label,
                    "position": position,
                    "track_id": track.get("id"),
                    "track_order": int(track.get("order", 0)),
                    "layer_order": len(video_specs),
                    "group_id": clip.get('_composite_group'),
                    "clock": copy.deepcopy(clip.get('_nested_keyframe_clock')),
                    "clip_id": clip.get("id"),
                    "keyframes": copy.deepcopy(clip.get("keyframes", [])),
                    "start": start,
                    "duration": max(0.001, clip_content_duration + freeze_extra),
                    "incoming": incoming,
                    "outgoing": outgoing,
                    "blend": clip.get("blend"),
                })
                input_meta.append({"asset_id": asset["id"], "clip_id": clip.get("id"), "input": None if inline_surface else source_index, "kind": "video", "source_in_tick": int(clip.get("source_in_tick", 0)), "source_out_tick": int(clip.get("source_out_tick", 0))})
                input_meta[-1]['video_frame_clock'] = clock_metadata
                if reverse_cache_job:
                    input_meta[-1]['reverse_cache']=reverse_cache_job
                if alpha_decoder:
                    input_meta[-1]['decoder'] = {'name': 'ffv1' if reverse_cache_job else alpha_decoder, 'reason': 'lossless-reverse-cache' if reverse_cache_job else 'webm-alpha-mode'}
                if inline_surface:
                    input_meta[-1]['inline_sequence_id'] = inline_surface['sequence_id']
                if subtitle:
                    input_meta[-1]['subtitle_time_mapping'] = copy.deepcopy(subtitle_clock)
                if nested_maps:
                    input_meta[-1]['nested_time_mapping'] = {'version': '1', 'maps': copy.deepcopy(nested_maps),
                                                            'source_display_fps': nominal_value,
                                                            'video_pts': 'analytic-composition', 'keyframes': 'authored-clock',
                                                            'frame_sampling': sampling_metadata}
                index += 1
            elif kind in {"video", "audio"} and track.get("kind") == "audio":
                if not clip.get('_audio_scope_enabled', True) or (isinstance(clip.get('audio'), dict) and (clip['audio'].get('muted') or clip['audio'].get('mute'))):
                    continue
                if not asset.get("probe", {}).get("audio", {}).get("codec"):
                    warnings.append({"code": "AUDIO_STREAM_MISSING", "clip_id": clip.get("id"), "message": "音频轨道引用的素材没有音频流，已跳过"})
                    continue
                inline_audio = asset.get('_inline_audio')
                audio_clock = None
                audio_input_start = len(inputs)
                if inline_audio:
                    audio_input = '['+audio_surface_labels[asset['id']].pop(0)+']'
                else:
                    audio_clock = _audio_clock_context.acquire(uri,asset['sha256'])
                    inputs.extend(audio_clock['input_args'])
                    physical_index += 1
                    audio_input = f'[{source_index}:a]'
                src_in = _sec(int(clip.get("source_in_tick", 0)), tps)
                src_out = _sec(int(clip.get("source_out_tick", clip.get("duration_tick", 1))), tps)
                label = f"a{index}"
                speed = _num(clip.get("speed", 1.0), 1.0)
                if speed <= 0:
                    raise AppError("SPEED_INVALID", "speed 必须大于 0", exit_code=2, path=f"clips[{clip.get('id')}].speed")
                source_span_tick = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
                speed_segments = _speed_curve_segments(clip, source_span_tick, tps)
                curve_duration = speed_curve_duration_seconds(clip, source_span_tick, tps)
                nested_maps = clip.get('_nested_time_maps')
                if nested_maps:
                    try:
                        audio_parts = _nested_audio_windows(nested_maps, src_in, src_out)
                    except ValueError as exc:
                        raise AppError('NESTED_AUDIO_TIME_MAPPING_LIMIT', str(exc), exit_code=2,
                                       path=f'clips[{clip.get("id")}].speed_curve') from exc
                    curve_duration = int(clip.get('duration_tick', 1)) / tps
                elif speed_segments:
                    audio_parts = [(left, right, rate, _speed_curve_elapsed_seconds(speed_segments, right))
                                   for left, right, rate in _speed_curve_audio_parts(speed_segments)]
                else:
                    audio_parts = []
                audio_stretch_job = None
                audio_context_plan = None
                requires_retime = any(abs(p[2]-1.) > 1e-9 for p in audio_parts) if audio_parts else abs(speed-1.) > 1e-9
                if local_audio_engine and requires_retime and inline_audio:
                    raise AppError('CLIP_WINDOW_INLINE_R3_UNSUPPORTED', '处理后的窗口子序列暂不能重新送入文件型 R3；请使用 FFmpeg 模式或先导出无损音频',exit_code=2)
                if local_audio_engine and requires_retime:
                    target_duration = curve_duration if curve_duration is not None else (src_out-src_in)/speed
                    audio_stretch_job = _plan_audio_stretch(root, local_audio_engine, asset, uri, src_in, src_out,
                                                            audio_parts, target_duration, bool(clip.get('reverse')))
                    inputs[audio_input_start:] = ['-i',audio_stretch_job['output']]
                    audio_chain = [f'{audio_input}anull']
                    if bool(clip.get('reverse')):
                        audio_chain.append('areverse')
                    warnings.append({'code':'RENDER_FEATURE_APPROXIMATE','clip_id':clip.get('id'),
                                     'feature':'offline_audio_time_map','message':'本地 R3 对整段音频离线伸缩；采样锚点为引擎约束，局部时序、极短窗音高与听感须独立核验'})
                    if audio_stretch_job['source_context']['requested_ms']:
                        warnings.append({'code':'AUDIO_STRETCH_SOURCE_CONTEXT','clip_id':clip.get('id'),
                                         'source_context':audio_stretch_job['source_context'],
                                         'message':'显式使用相邻真实源音频作为变速分析上下文，输出裁回作者选区；附近瞬态、音高、相位与自然听感仍须复核'})
                elif audio_parts:
                    source_start_sample = round(src_in * 48000)
                    source_end_sample = round(src_out * 48000)
                    mapped_duration = audio_parts[-1][3]
                    clip_duration_seconds = int(clip.get('duration_tick', 1))/tps
                    has_audio_freeze = isinstance(clip.get('freeze'),dict) and int(clip['freeze'].get('duration_tick',0)) > 0
                    if not has_audio_freeze and abs(mapped_duration-clip_duration_seconds) <= 1/tps:
                        # The clip owns a half-open global sample interval;
                        # do not leave one rounded-away sample at its end.
                        target_samples = max(1, math.ceil(Fraction((int(clip.get('timeline_start_tick', 0))+int(clip.get('duration_tick', 1)))*48000,tps))-math.ceil(Fraction(int(clip.get('timeline_start_tick', 0))*48000,tps)))
                    else:
                        # Freeze insertion or an explicitly different authored
                        # clip window is handled after this content retime.
                        target_samples = max(1, math.ceil(mapped_duration*48000))
                    audio_context_plan = _audio_context_windows(audio_parts, source_end_sample-source_start_sample,
                                                               target_samples=target_samples,
                                                               channels=max(1,int((asset.get('probe',{}).get('audio') or {}).get('channels',2))))
                    split_labels = [f"asplit{index}_{part_index}" for part_index in range(len(audio_parts))]
                    filters.append(
                        f"{audio_input}aresample=48000:first_pts=0,aformat=sample_fmts=flt,apad=whole_len={source_end_sample},atrim=start_sample={source_start_sample}:end_sample={source_end_sample},asetpts=N/SR/TB,"
                        f"asplit={len(split_labels)}" + "".join(f"[{label}]" for label in split_labels)
                    )
                    part_labels: list[str] = []
                    for part_index, part in enumerate(audio_context_plan):
                        part_label = f"aspeed{index}_{part_index}"
                        part_labels.append(part_label)
                        part_samples = part['output_samples']
                        if part['output_selection'] == 'last-retimed-samples':
                            core_selection = f'areverse,atrim=end_sample={part_samples},areverse,'
                        else:
                            core_selection = f"atrim=start_sample={part['retimed_trim_start_sample']}:end_sample={part['retimed_trim_end_sample']},"
                        filters.append(
                            f"[{split_labels[part_index]}]atrim=start_sample={part['context_start_sample']}:end_sample={part['context_end_sample']},"
                            f"asetpts=N/SR/TB,{_tempo_chain(part['tempo'])},"
                            f"{core_selection}"
                            f"apad=whole_len={part_samples},"
                            f"atrim=end_sample={part_samples},asetpts=N/SR/TB[{part_label}]"
                        )
                    speed_label = f"aspeed{index}"
                    concat_chain = "".join(f"[{label}]" for label in part_labels) + f"concat=n={len(part_labels)}:v=0:a=1"
                    if bool(clip.get("reverse")):
                        concat_chain += ",areverse"
                    filters.append(f"{concat_chain}[{speed_label}]")
                    # concat uses a microsecond timebase. After areverse the
                    # inherited timestamps need not describe sample positions;
                    # automation must see the continuous local sample clock.
                    audio_chain = [f"[{speed_label}]aresample=48000", "asetpts=N/SR/TB"]
                    warnings.append({"code": "RENDER_FEATURE_APPROXIMATE", "clip_id": clip.get("id"), "feature": "audio_speed_curve_piecewise", "message": "音频速度曲线按带选区内上下文的短段 atempo 近似，末段按真实伸缩末端选取；累计采样锚点对齐，局部时序、段间相位、瞬态、极短选区与听感仍须独立核验；输出不足仍可能补静音"})
                else:
                    # FFmpeg input PTS are demux-relative. Preserve any source-leading
                    # gap before selecting the author window or reversing/retiming it.
                    # first_pts normalizes the beginning only; async drift correction
                    # is deliberately not enabled.
                    # Resample in float before selecting source samples. Negotiating
                    # an integer first stage would requantize low-rate PCM before
                    # the later floating-point mix, even with lossless output.
                    # Pad within the authored source window before reversal. Padding
                    # the reversed result would move source EOF silence to the end.
                    source_end_sample = max(1,round(src_out*48000))
                    audio_chain = [f"{audio_input}aresample=48000:osf=flt:first_pts=0,apad=whole_len={source_end_sample},atrim=start={src_in:.6f}:end={src_out:.6f}", "asetpts=PTS-STARTPTS", "aresample=48000"]
                    if bool(clip.get("reverse")):
                        audio_chain.append("areverse")
                    if abs(speed - 1.0) > 1e-9:
                        audio_chain.append(_tempo_chain(speed))
                audio_settings = clip.get("audio") if isinstance(clip.get("audio"), dict) else {}
                freeze = clip.get("freeze") if isinstance(clip.get("freeze"), dict) else None
                freeze_audio_mode = str(freeze.get("audio_mode", "silence")).lower() if freeze else "silence"
                freeze_duration = max(0.0, _sec(int(freeze.get("duration_tick", 0)), tps)) if freeze else 0.0
                content_duration = max(
                    0.001,
                    curve_duration if curve_duration is not None else (src_out - src_in) / max(speed, 1e-9),
                )
                audio_keyframe_time = "t"
                if freeze_duration > 0 and freeze_audio_mode == "silence":
                    freeze_at = max(0.0, min(content_duration, _sec(int(freeze.get("at_tick", int(round(content_duration * tps)))), tps)))
                    audio_chain = _insert_audio_freeze(filters, audio_chain, f"afreeze{index}", content_duration, freeze_at, freeze_duration)
                    # Audio automation is authored against the pre-freeze
                    # clip clock. During the inserted silence, hold the value
                    # at the freeze point; after it, subtract the insertion
                    # so later keyframes keep their authored positions.
                    audio_keyframe_time = (
                        f"if(lt(t,{freeze_at:.8f}),t,"
                        f"if(lt(t,{freeze_at + freeze_duration:.8f}),{freeze_at:.8f},"
                        f"t-{freeze_duration:.8f}))"
                    )
                elif freeze_duration > 0:
                    audio_chain.append(f"apad=pad_dur={freeze_duration:.6f}")
                source_handle = clip.get('_source_handle')
                envelope_clock = clip.get('_source_envelope_clock')
                source_author_time = (_clock_expression(envelope_clock['maps'], f'(t+{int(clip["timeline_start_tick"])/tps:.12f})', inverse=True)
                                      if envelope_clock else None)
                fade_clock = (f'({source_author_time}-{source_handle["authored_start_tick"]/tps:.12f})' if source_author_time
                              else 't' if not source_handle else f'(t-{source_handle["head_tick"]/tps:.12f})')
                authored_audio_duration = (content_duration+freeze_duration if not source_handle
                                           else source_handle['authored_duration_tick']/tps)
                audio_chain.extend(_audio_processing_filters(
                    clip, audio_settings, tps, audio_keyframe_time=audio_keyframe_time,
                    fade_clock=fade_clock, authored_duration=authored_audio_duration,
                ))
                for envelope in clip.get('_source_audio_envelopes', []):
                    local_start = (envelope['start_tick']-int(clip['timeline_start_tick']))/tps
                    progress = (f'clip(({source_author_time}-{envelope["start_tick"]/tps:.12f})/{envelope["duration_tick"]/tps:.12f},0,1)' if source_author_time
                                else f'clip((t-{local_start:.12f})/{envelope["duration_tick"]/tps:.12f},0,1)')
                    gain = progress if envelope['edge'] == 'in' else f'(1-({progress}))'
                    audio_chain.append(f"aeval=exprs={_expr_arg('val(ch)*('+gain+')')}:c=same")
                audio_samples = max(1, math.ceil(Fraction((int(clip.get('timeline_start_tick', 0))+int(clip.get('duration_tick', 1)))*48000,tps))-math.ceil(Fraction(int(clip.get('timeline_start_tick', 0))*48000,tps)))
                audio_start_sample = max(0, math.ceil(Fraction(int(clip.get('timeline_start_tick', 0))*48000,tps)))
                audio_chain.extend([f'apad=whole_len={audio_samples}', f'atrim=end_sample={audio_samples}',
                                    'asetpts=N/SR/TB', f'adelay={audio_start_sample}S:all=1'])
                filters.append(",".join(audio_chain) + f"[{label}]")
                audio_specs.append({'label':label,'group_id':clip.get('_composite_group'),
                                    'track_id':track_id,'clip_id':clip.get('id'),'audio':copy.deepcopy(audio_settings)})
                input_meta.append({"asset_id": asset["id"], "clip_id": clip.get("id"), "track_id": track_id, "input": None if inline_audio else source_index, "kind": "audio", "source_in_tick": int(clip.get("source_in_tick", 0)), "source_out_tick": int(clip.get("source_out_tick", 0))})
                input_meta[-1].update(timeline_start_sample=audio_start_sample,duration_samples=audio_samples,
                                      sample_rate=48000,group_id=clip.get('_composite_group'))
                if audio_clock is not None:
                    input_meta[-1]['native_audio_clock'] = audio_clock
                if audio_stretch_job:
                    input_meta[-1]['audio_stretch'] = audio_stretch_job
                if audio_context_plan is not None:
                    input_meta[-1]['audio_tempo_context'] = {
                        'engine': 'ffmpeg-atempo-source-context-v2', 'sample_rate': 48000,
                        'core_sample_format': 'float32',
                        'source_start_sample': source_start_sample, 'source_end_sample': source_end_sample,
                        'source_selection_samples': source_end_sample-source_start_sample,
                        'context_policy_samples': _audio_context_frames, 'context_outside_selection': False,
                        'terminal_context_pcm_budget_bytes': _audio_terminal_context_budget,
                        'terminal_core_alignment': 'actual-retimed-source-end',
                        'windows': audio_context_plan, 'shortfall_policy': 'zero-pad-core',
                        'continuous_phase_accepted': False, 'pitch_and_listening_accepted': False,
                        'local_content_sample_alignment_accepted': False,
                    }
                if nested_maps:
                    input_meta[-1]['nested_time_mapping'] = {'version': '1', 'maps': copy.deepcopy(nested_maps),
                                                            'tempo_windows': len(audio_parts), 'sample_rate': 48000,
                                                            'audio_tempo': 'offline-r3-time-map' if audio_stretch_job else 'piecewise-source-context-integrated-boundaries'}
                index += 1
    if not video_labels and not subtitle_overlays and not _video_only and not _allow_audio_only:
        raise AppError("VIDEO_TRACK_EMPTY", "没有可渲染的视频片段或独立文字轨道", exit_code=2, path="sequences[].tracks")
    width, height = root_canvas['width'], root_canvas['height']
    subtitle_specs = [
        _build_subtitle_layer(
            root,
            overlay,
            subtitle_index,
            filters,
            warnings,
            width=composite_groups[overlay['group_id']]['canvas']['width'] if overlay.get('group_id') else width,
            height=composite_groups[overlay['group_id']]['canvas']['height'] if overlay.get('group_id') else height,
            fps_value=fps_value,
            duration=duration,
            tps=tps,
            automation=_effect_runtime,
            automation_meta=input_meta,
            projection=_projection_runtime,
        )
        for subtitle_index, overlay in enumerate(subtitle_overlays)
    ]
    current = _build_compositing_tree(
        root, [*video_specs, *subtitle_specs], composite_groups, filters, warnings, input_meta,
        width=width, height=height, fps=fps, fps_value=fps_value, duration=duration,
        tps=tps, transparent_canvas=transparent_canvas, sampling=sampling_config['method'],
        automation=_effect_runtime,
        projection=_projection_runtime,
    )
    if not has_adjustments:
        filters.append(f"[{current}]null[vout]")
        current = 'vout'
    if has_adjustments:
        for adjustment_index, (adjustment_id, effects, adjustment_start, adjustment_end) in enumerate(adjustment_layers):
            effect_clip = {"id": adjustment_id, "effects": effects,
                           "timeline_start_tick": 0, "duration_tick": round((adjustment_end-adjustment_start)*tps)}
            effect_filters = _effect_filters(
                effects,
                warnings,
                adjustment_id,
                root=root,
                clip=effect_clip,
                clip_start=0.0,
                tps=tps,
                automation=_effect_runtime,
                automation_meta=input_meta,
            )
            if not effect_filters:
                continue
            target = f"adjusted{adjustment_index}"
            if adjustment_start <= 1e-9 and adjustment_end >= duration - 1e-9:
                filters.append(f"[{current}]" + ",".join(effect_filters) + f"[{target}]")
                current = target
                continue
            segment_labels: list[str] = []
            # Each interval consumes its own copy of the composed surface.
            # Reusing one consumed label can bind subsequent inputs to a
            # similarly named input stream and bypass compositing/fps filters.
            interval_inputs = [f'adjustment{adjustment_index}input{i}' for i in range(
                1+int(adjustment_start > 1e-9)+int(adjustment_end < duration-1e-9))]
            filters.append(f'[{current}]split={len(interval_inputs)}'+''.join(f'[{label}]' for label in interval_inputs))
            interval_iter = iter(interval_inputs)
            if adjustment_start > 1e-9:
                pre = f"adjustment{adjustment_index}pre"
                filters.append(f"[{next(interval_iter)}]trim=start=0:end={adjustment_start:.6f},setpts=PTS-STARTPTS,format=rgba[{pre}]")
                segment_labels.append(pre)
            mid_input = f"adjustment{adjustment_index}midin"
            mid = f"adjustment{adjustment_index}mid"
            filters.append(f"[{next(interval_iter)}]trim=start={adjustment_start:.6f}:end={adjustment_end:.6f},setpts=PTS-STARTPTS,format=rgba[{mid_input}]")
            filters.append(f"[{mid_input}]" + ",".join(effect_filters) + f",format=rgba[{mid}]")
            segment_labels.append(mid)
            if adjustment_end < duration - 1e-9:
                post = f"adjustment{adjustment_index}post"
                filters.append(f"[{next(interval_iter)}]trim=start={adjustment_end:.6f}:end={duration:.6f},setpts=PTS-STARTPTS,format=rgba[{post}]")
                segment_labels.append(post)
            filters.append("".join(f"[{label}]" for label in segment_labels) + f"concat=n={len(segment_labels)}:v=1:a=0,format=rgba,setpts=PTS-STARTPTS[{target}]")
            current = target
        adjusted_output = "vout"
        filters.append(f"[{current}]" + ("format=rgba," if transparent_canvas else "") + f"null[{adjusted_output}]")
        current = adjusted_output

    audio_root = _build_audio_bus_tree(audio_specs, composite_groups, render_tracks, filters, warnings, input_meta,
                                      duration_tick=int(sequence['duration_tick']), tps=tps,
                                      routing_sequence=sequence if not _video_only else None)
    audio_target_samples = max(1, math.ceil(Fraction(int(sequence['duration_tick'])*48000, tps)))
    if audio_root:
        filters.append(f'[{audio_root}]aresample=48000,apad=whole_len={audio_target_samples},'
                       f'atrim=end_sample={audio_target_samples},asetpts=N/SR/TB[aout]')
    else:
        # atempo on native u8 silence can round 128 to 127 (-256 in s16).
        # Keep generated empty buses floating point before any ancestor tempo.
        filters.append(f'anullsrc=r=48000:cl=stereo,atrim=end_sample={audio_target_samples},aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aout]')
    if root_effect_runtime and _effect_runtime.targets:
        input_meta.append(_effect_runtime.summary())
    return inputs, ";".join(filters), input_meta, warnings


def _execution_filter_graph(root: Path, args: list[str], graph: str, *, write: bool) -> tuple[list[str], dict[str, Any]]:
    """Move large graphs to a content-addressed file before CreateProcess."""
    def units(argv: list[str]) -> int:
        return len(subprocess.list2cmdline(argv).encode('utf-16-le')) // 2 + 1
    digest = sha256_bytes(graph.encode('utf-8'))
    info: dict[str, Any] = {'mode':'inline', 'sha256':'sha256:'+digest, 'utf8_bytes':len(graph.encode('utf-8')), 'logical_command_utf16_units':units(args)}
    if units(args) <= 28_000:
        return args, info
    path = root/'cache'/'render-filtergraphs'/f'{digest}.ffgraph'
    if path.exists() and sha256_file(path) != digest:
        raise AppError('RENDER_FILTER_GRAPH_HASH_MISMATCH', '本地滤镜图缓存哈希不匹配', exit_code=6, path=str(path))
    execution = list(args)
    index = execution.index('-filter_complex')
    execution[index:index+2] = ['-/filter_complex', str(path)]
    if units(execution) > 28_000:
        raise AppError('RENDER_ARGUMENT_LIMIT', '输入参数超过 Windows 命令行预算，请拆分输入序列', exit_code=2)
    if write and not path.exists():
        atomic_write_text(path, graph)
    info.update({'mode':'local-file', 'path':str(path), 'execution_command_utf16_units':units(execution)})
    return execution, info


@verification_scope()
def render_project(
    root: Path,
    project: dict[str, Any],
    sequence: dict[str, Any],
    output: Path,
    *,
    dry_run: bool = False,
    render_settings: dict[str, Any] | None = None,
    profile: str | None = None,
    cancel_file: Path | None = None,
    progress_callback: Callable[[str, str, float | None, str], None] | None = None,
    resume_of: str | None = None,
) -> dict[str, Any]:
    with ExitStack() as runtime:
        return _render_project(root, project, sequence, output, dry_run=dry_run,
            render_settings=render_settings, profile=profile, cancel_file=cancel_file,
            progress_callback=progress_callback, resume_of=resume_of, _runtime=runtime)


def _render_project(root, project, sequence, output, *, dry_run=False, render_settings=None,
                    profile=None, cancel_file=None, progress_callback=None, resume_of=None, _runtime):
    effective_project = dict(project)
    effective_project['settings'] = copy.deepcopy(render_settings if render_settings is not None else project['settings'])
    if render_settings is None:
        effective_project['settings']['canvas'] = {**effective_project['settings']['canvas'], **sequence_canvas(project, sequence)}
    render_sequence = sequence
    if sequence.get('canvas') is not None:
        # A profile overrides only this render's selected root; explicitly
        # authored child rasters remain independent. Keep fingerprint inputs
        # and persisted project data in their original authoring state.
        render_sequence = {**sequence, 'canvas': {k: int(effective_project['settings']['canvas'][k]) for k in ('width', 'height')}}
        effective_project['sequences'] = [render_sequence if s.get('id') == sequence.get('id') else s for s in project['sequences']]
    encoder = output_settings(effective_project["settings"])
    validate_output_alignment(sequence_canvas(effective_project, render_sequence), str(encoder['video']['pixel_format']))
    operation_id = new_id('render')
    from .projection_opencl import ProjectionSession
    projection = ProjectionSession(root,effective_project['settings'],operation_id,cancel_file=cancel_file)
    float_renderer = None
    if effective_project['settings'].get('pixel_pipeline') is not None:
        from .float_standard_render import FloatRenderContext
        float_renderer = _runtime.enter_context(FloatRenderContext(root, effective_project, render_sequence,
            encoder, dry_run=dry_run, cancel_file=cancel_file, operation_id=operation_id))
        projection = float_renderer.gpu
        inputs, graph, input_meta, warnings = float_renderer.graph()
    else:
        inputs, graph, input_meta, warnings = build_filter_graph(root, effective_project, render_sequence,
            _persist_video_index=not dry_run,_cancel_file=cancel_file,_projection_runtime=projection)
    fingerprints = render_fingerprints(project, sequence, effective_project["settings"], root)
    if not dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
    acceleration = AccelerationSession(root, effective_project['settings'], encoder, operation_id, cancel_file)
    temp_dir = root / "renders" / ".tmp" / operation_id
    if not dry_run:
        temp_dir.mkdir(parents=True, exist_ok=True)
    temp_output = temp_dir / output.name
    progress_file = temp_dir / "ffmpeg-progress.log"
    container = encoder["container"]
    video_encoder = encoder["video"]
    audio_encoder = encoder["audio"]
    lossless_vp9 = (video_encoder['codec'] == 'libvpx-vp9' and
                    video_encoder['crf'] == 0 and not video_encoder.get('bitrate'))
    delivery: dict[str, Any] = {}
    video_output = 'float_vout' if float_renderer is not None else 'vout'
    if float_renderer is not None:
        delivery['pixel_pipeline'] = float_renderer.metadata
    if float_renderer is None and video_encoder['pixel_format'] in ALPHA_OUTPUT_PIXEL_FORMATS:
        # swscale's combined RGBA -> YUVA conversion can round alpha levels
        # 128..254 upwards. Keep the original byte plane outside color math.
        graph += (';[vout]format=rgba,split=2[delivery_rgb][delivery_a]'
                  ';[delivery_a]alphaextract,format=gray[delivery_alpha]'
                  ';[delivery_rgb]format=yuv420p[delivery_yuv]'
                  ';[delivery_yuv][delivery_alpha]alphamerge,format=yuva420p[delivery_vout]')
        video_output = 'delivery_vout'
        delivery['alpha'] = {'conversion': 'separate-original-8-bit-plane',
                             'encoding_precision': 'lossless-yuv-alpha' if lossless_vp9 else 'lossy-yuv-alpha',
                             'rgba_lossless': False, 'pixel_format': 'yuva420p',
                             'decoder': 'libvpx-vp9' if video_encoder['codec'] == 'libvpx-vp9' else 'libvpx'}
    # FFmpeg rounds an output -t on the encoder frame timebase. Keep every
    # display frame whose start belongs to the author's half-open interval;
    # audio is separately trimmed to its exact authored sample count in aout.
    output_rate = Fraction(effective_project['settings']['timebase']['display_fps']['num'],
                           effective_project['settings']['timebase']['display_fps']['den'])
    authored_seconds = Fraction(max(int(sequence.get('duration_tick', 1)), 1),
                                int(project['settings']['timebase']['ticks_per_second']))
    encoded_end = Fraction(math.ceil(authored_seconds*output_rate), 1)/output_rate
    delivery['clock'] = {'authored_duration_tick': int(sequence['duration_tick']),
                          'ticks_per_second': int(project['settings']['timebase']['ticks_per_second']),
                          'expected_video_frames': math.ceil(authored_seconds*output_rate),
                          'expected_video_end_seconds': float(encoded_end),
                          'expected_audio_samples_48000': math.ceil(authored_seconds*48000)}
    if acceleration.enabled:
        graph = tag_output_frames(graph, video_output, effective_project['settings'])
    args = [
        ffmpeg_path(), "-hide_banner", "-y", "-loglevel", "error",
        *(['-nostdin', '-filter_complex_threads', '1'] if float_renderer is not None else []),
        "-progress", str(progress_file),
        *inputs, "-filter_complex", graph, "-map", f"[{video_output}]", "-map", "[aout]",
        *([] if float_renderer is not None else ["-t", f"{float(encoded_end):.9f}"]),
        "-c:v", str(video_encoder["codec"]),
    ]
    if str(video_encoder.get("codec")) in {"libx264", "libx265"}:
        args.extend(["-preset", str(video_encoder.get("preset", "medium"))])
    if video_encoder.get("bitrate"):
        args.extend(["-b:v", str(video_encoder["bitrate"])])
    else:
        args.extend(["-crf", str(video_encoder.get("crf", 18))])
    if str(video_encoder.get("codec")) in {"libvpx-vp9", "libvpx"} and not video_encoder.get("bitrate"):
        args.extend(["-b:v", "0"])
    if lossless_vp9:
        args.extend(['-lossless', '1'])
    if video_encoder['codec'] == 'libvpx' and video_encoder['pixel_format'] in ALPHA_OUTPUT_PIXEL_FORMATS:
        args.extend(['-auto-alt-ref', '0'])
    args.extend(["-pix_fmt", str(video_encoder.get("pixel_format", "yuv420p"))])
    args.extend(_output_color_args(effective_project["settings"]))
    if float_renderer is not None:
        args.extend(['-chroma_sample_location', 'left'])
    args.extend(["-c:a", str(audio_encoder["codec"])])
    if not str(audio_encoder.get("codec", '')).startswith('pcm_'):
        args.extend(["-b:a", str(audio_encoder.get("bitrate", "192k"))])
    if container == "mp4":
        args.extend(["-movflags", "+faststart"])
    args.extend(["-f", OUTPUT_CONTAINERS[container], str(temp_output)])
    execution_args, graph_transport = _execution_filter_graph(root, args, graph, write=not dry_run)
    plan = {"operation_id": operation_id, "command": args, "execution_command":execution_args, "filter_graph_transport":graph_transport, "filter_complex": graph, "inputs": input_meta, "output": str(output), "encoder": encoder, "delivery": delivery, "warnings": warnings, **fingerprints, "resume_of": resume_of}
    plan['acceleration'] = acceleration.evidence
    plan['projection_acceleration'] = projection.evidence
    if dry_run:
        if progress_callback:
            progress_callback(operation_id, "planned", 0.0, "渲染计划已生成")
        return {"status": "planned", "plan": plan}
    if progress_callback:
        progress_callback(operation_id, "render_started", 0.0, "FFmpeg 渲染开始")
    progress_stop = threading.Event()
    expected_seconds = max(0.001, int(sequence.get("duration_tick", 1)) / int(effective_project["settings"]["timebase"]["ticks_per_second"]))

    def watch_progress() -> None:
        last_percent = -1.0
        while not progress_stop.is_set():
            try:
                raw = progress_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                raw = ""
            values: dict[str, str] = {}
            for line in raw.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
            if values.get("out_time_ms"):
                try:
                    percent = max(0.0, min(100.0, float(values["out_time_ms"]) / 1_000_000.0 / expected_seconds * 100.0))
                except (TypeError, ValueError):
                    percent = None
                if percent is not None and percent - last_percent >= 1.0:
                    last_percent = percent
                    if progress_callback:
                        try:
                            progress_callback(operation_id, "render_progress", round(percent, 2), "FFmpeg 渲染进行中")
                        except Exception:
                            pass
            if values.get("progress") == "end" and progress_callback:
                try:
                    progress_callback(operation_id, "render_progress", 100.0, "FFmpeg 已完成编码")
                except Exception:
                    pass
            progress_stop.wait(0.2)

    progress_thread = threading.Thread(target=watch_progress, name="ai-ad-editor-render-progress", daemon=True)
    progress_thread.start()
    try:
        if cancel_file is not None and cancel_file.exists():
            raise AppError("CANCELLED", "任务在启动前已被取消", exit_code=8, path=str(cancel_file), retryable=False)
        plan['acceleration'] = acceleration.evidence
        from .reverse_cache import materialize as materialize_reverse, verify_materialized as verify_reverse
        reverse_jobs=materialize_reverse(root,input_meta,temp_dir,cancel_file=cancel_file)
        def check_acceleration_inputs():
            if render_fingerprints(project, sequence, effective_project['settings'], root) != fingerprints:
                raise AppError('RENDER_INPUT_CHANGED', '探测或渲染期间输入指纹变化，拒绝重试和发布', exit_code=6)
            if projection.evidence['status'] in ('prepared','encoded_pending_quality','verified'):
                projection.verify_programs()
        if projection.enabled:
            check_acceleration_inputs()
            args,graph=projection.prepare(args,graph)
            check_acceleration_inputs()
            execution_args,graph_transport=_execution_filter_graph(root,args,graph,write=True)
            plan.update(command=args,execution_command=execution_args,filter_complex=graph,filter_graph_transport=graph_transport)
        acceleration.prepare(inputs, input_meta, effective_project, temp_dir, _output_color_args(effective_project['settings']))
        for item in input_meta:
            if job := item.get('audio_stretch'):
                job['execution'] = _execute_audio_stretch(root, job, temp_dir, cancel_file=cancel_file)
        from .native_audio_clock import verify_materialized as verify_audio_clocks
        verify_audio_clocks(root,input_meta,cancel_file=cancel_file)
        if acceleration.enabled:
            result, execution_args, graph_transport = acceleration.execute(args, graph,
                lambda command, current_graph: _execution_filter_graph(root, command, current_graph, write=True),
                check_acceleration_inputs)
        elif float_renderer is not None:
            result = float_renderer.run(execution_args)
        else:
            result = run_process(execution_args, timeout=3600, cwd=root, cancel_file=cancel_file)
        projection.finish(result)
        plan.update(execution_command=execution_args,filter_graph_transport=graph_transport)
        if result.returncode != 0:
            raise AppError("RENDER_FAILED", "FFmpeg 渲染失败", exit_code=6, retryable=True, cause=result.stderr[-6000:])
        if not temp_output.exists() or temp_output.stat().st_size == 0:
            raise AppError("RENDER_EMPTY", "FFmpeg 未生成有效输出", exit_code=6)
        inspected = probe_media(temp_output)
        if acceleration.enabled:
            acceleration.verify_output(inspected, temp_output)
        quality = check_output(temp_output, effective_project["settings"], _sec(_tick(sequence.get("duration_tick"), 1), int(effective_project["settings"]["timebase"]["ticks_per_second"])), run_expensive=False)
        if not quality["ok"]:
            raise AppError("RENDER_QUALITY_FAILED", "输出未通过结构质量检查", exit_code=6, cause=str(quality["errors"]))
        if acceleration.enabled:
            check_acceleration_inputs()
            acceleration.evidence.update(status='verified_pending_publish', quality=quality, output_probe=inspected)
            acceleration.save()
        if projection.enabled:
            check_acceleration_inputs()
        if reverse_jobs:
            verify_reverse(root,reverse_jobs,cancel_file=cancel_file)
            check_acceleration_inputs()
        from .native_video_index import verify_materialized as verify_native_indexes
        verify_native_indexes(root,input_meta,cancel_file=cancel_file)
        verify_audio_clocks(root,input_meta,cancel_file=cancel_file)
        if float_renderer is not None:
            float_renderer.finish_sources()
            check_acceleration_inputs()
        if acceleration.enabled:
            acceleration.evidence['status'] = 'verified'
            acceleration.save()
        if projection.evidence['status']=='encoded_pending_quality':
            projection.evidence['status']='verified';projection.save()
        manifest = {
            "manifest_version": "0.1.0",
            "operation_id": operation_id,
            "project_id": project["project"]["id"],
            "sequence_id": sequence["id"],
            "output": str(output),
            "sha256": sha256_file(temp_output),
            "probe": inspected,
            "command": execution_args,
            "filter_graph_transport": graph_transport,
            "filter_complex": graph,
            "inputs": input_meta,
            "profile": profile,
            "settings": effective_project["settings"],
            "delivery": delivery,
            "acceleration": acceleration.evidence,
            "projection_acceleration": projection.evidence,
            "warnings": warnings,
            "quality": quality,
            **fingerprints,
            "resume_of": resume_of,
        }
        manifest_path = output.with_suffix(output.suffix + ".manifest.json")
        if float_renderer is not None:
            float_renderer.publish(temp_output, output, manifest, operation_id)
        else:
            try:
                os.replace(temp_output, output)
            except OSError as exc:
                raise AppError('RENDER_PUBLISH_FAILED', '无法原子发布成片', exit_code=6, path=str(output), cause=str(exc)) from exc
            atomic_write_json(manifest_path, manifest)
        if progress_callback:
            progress_callback(operation_id, "artifact_written", 100.0, "渲染产物和 manifest 已写入")
            progress_callback(operation_id, "completed", 100.0, "渲染完成")
        return {"status": "succeeded", "operation_id": operation_id, "path": str(output), "manifest": str(manifest_path), "filter_graph_transport":graph_transport, "profile": profile, "settings": effective_project["settings"], "delivery": delivery, "acceleration": acceleration.evidence, "projection_acceleration":projection.evidence, "probe": inspected, "warnings": warnings + quality.get("warnings", []), "quality": quality, **fingerprints, "resume_of": resume_of}
    except AppError as exc:
        projection.evidence.update(status='cancelled' if exc.code=='CANCELLED' else 'failed',error=exc.as_dict())
        projection.save()
        acceleration.evidence.update(status='cancelled' if exc.code == 'CANCELLED' else 'failed', error=exc.as_dict())
        acceleration.save()
        # Make the persisted operation discoverable from the CLI error envelope so
        # callers can invoke `render --resume <operation_id>` without scanning files.
        exc.operation_id = operation_id
        if progress_callback:
            progress_callback(operation_id, "cancelled" if exc.code == "CANCELLED" else "failed", None, "渲染已取消" if exc.code == "CANCELLED" else "渲染失败")
        atomic_write_json(
            root / "operations" / f"{operation_id}.json",
            {
                "operation_id": operation_id,
                "command": "render",
                "status": "cancelled" if exc.code == "CANCELLED" else "failed",
                "output": str(output),
                "profile": profile,
                "project_id": project["project"]["id"],
                "sequence_id": sequence["id"],
                "settings": effective_project["settings"],
                "error": exc.as_dict(),
                "plan": plan,
                **fingerprints,
                "resume_of": resume_of,
                "created_at": now_iso(),
            },
        )
        raise
    finally:
        progress_stop.set()
        progress_thread.join(timeout=2)
        try:
            for child in temp_dir.glob("*"):
                child.unlink(missing_ok=True)
            temp_dir.rmdir()
            temp_dir.parent.rmdir() if not any(temp_dir.parent.iterdir()) else None
        except OSError:
            pass

