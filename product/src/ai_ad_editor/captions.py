from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

from .errors import AppError, argument_error
from .utils import atomic_write_text


TIME_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3})"
)
ASS_TIME_RE = re.compile(r"^(?P<h>\d+):(?P<m>\d{2}):(?P<s>\d{2})[.,](?P<cs>\d{1,3})$")


def parse_timestamp(value: str) -> float:
    raw = value.strip().replace(",", ".")
    parts = raw.split(":")
    try:
        if len(parts) == 2:
            minutes, seconds = parts
            return max(0.0, float(minutes) * 60.0 + float(seconds))
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return max(0.0, float(hours) * 3600.0 + float(minutes) * 60.0 + float(seconds))
    except ValueError as exc:
        raise ValueError(f"无效时间码: {value}") from exc
    raise ValueError(f"无效时间码: {value}")


def _parse_ass_timestamp(value: str) -> float:
    match = ASS_TIME_RE.fullmatch(value.strip())
    if not match:
        return parse_timestamp(value)
    fraction = match.group("cs")
    milliseconds = int((fraction + "00")[:3])
    return int(match.group("h")) * 3600 + int(match.group("m")) * 60 + int(match.group("s")) + milliseconds / 1000.0


def _clean_ass_text(value: str) -> str:
    value = re.sub(r"\{[^}]*\}", "", value)
    return value.replace(r"\N", "\n").replace(r"\n", "\n").replace(r"\h", " ").strip()


def _cue(start: float, end: float, text: str, *, index: int | None = None, source_format: str = "unknown") -> dict[str, Any]:
    item: dict[str, Any] = {
        "start": round(float(start), 3),
        "end": round(float(end), 3),
        "text": text.replace("\r\n", "\n").replace("\r", "\n").strip(),
        "source_format": source_format,
    }
    if index is not None:
        item["index"] = index
    return item


def parse_srt(text: str) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n").strip())
    for block_number, block in enumerate(blocks, start=1):
        lines = [line.strip("\ufeff") for line in block.split("\n")]
        if not lines:
            continue
        timing_index = next((i for i, line in enumerate(lines) if TIME_RE.search(line)), None)
        if timing_index is None:
            continue
        match = TIME_RE.search(lines[timing_index])
        assert match is not None
        try:
            start = parse_timestamp(match.group("start"))
            end = parse_timestamp(match.group("end"))
        except ValueError as exc:
            raise argument_error(str(exc), f"cue[{block_number}]") from exc
        body = "\n".join(lines[timing_index + 1 :]).strip()
        cues.append(_cue(start, end, body, index=block_number, source_format="srt"))
    return cues


def parse_vtt(text: str) -> list[dict[str, Any]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    cues: list[dict[str, Any]] = []
    index = 0
    line_number = 0
    while line_number < len(lines):
        line = lines[line_number].strip()
        if not line or line == "WEBVTT" or line.startswith(("NOTE", "STYLE", "REGION")):
            line_number += 1
            continue
        timing_index = line_number
        if "-->" not in line and line_number + 1 < len(lines) and "-->" in lines[line_number + 1]:
            timing_index += 1
        match = TIME_RE.search(lines[timing_index]) if timing_index < len(lines) else None
        if not match:
            line_number += 1
            continue
        try:
            start = parse_timestamp(match.group("start"))
            end = parse_timestamp(match.group("end"))
        except ValueError as exc:
            raise argument_error(str(exc), f"cue[{len(cues) + 1}]") from exc
        body_start = timing_index + 1
        body_end = body_start
        while body_end < len(lines) and lines[body_end].strip():
            body_end += 1
        index += 1
        cues.append(_cue(start, end, "\n".join(lines[body_start:body_end]), index=index, source_format="vtt"))
        line_number = body_end + 1
    return cues


def parse_ass(text: str) -> list[dict[str, Any]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    format_fields: list[str] = []
    cues: list[dict[str, Any]] = []
    section = ''
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            section = stripped.lower()
            continue
        if stripped.lower().startswith("format:") and section in {'', '[events]'}:
            format_fields = [item.strip().lower() for item in stripped.split(":", 1)[1].split(",")]
            continue
        if not stripped.lower().startswith("dialogue:"):
            continue
        raw = stripped.split(":", 1)[1].lstrip()
        expected = len(format_fields) or 10
        fields = raw.split(",", expected - 1)
        if format_fields:
            record = {key: fields[i].strip() for i, key in enumerate(format_fields) if i < len(fields)}
            start_value = record.get("start", "")
            end_value = record.get("end", "")
            text_value = record.get("text", "")
        else:
            if len(fields) < 10:
                continue
            start_value, end_value, text_value = fields[1], fields[2], ",".join(fields[9:])
        try:
            start = _parse_ass_timestamp(start_value)
            end = _parse_ass_timestamp(end_value)
        except ValueError as exc:
            raise argument_error(f"ASS 时间码无效: {start_value} -> {end_value}", "dialogue") from exc
        cues.append(_cue(start, end, _clean_ass_text(text_value), index=len(cues) + 1, source_format="ass"))
    return cues


def _ttml_local_name(value: str) -> str:
    return str(value).rsplit("}", 1)[-1].split(":", 1)[-1].lower()


def _ttml_attribute(element: ET.Element, name: str, default: str | None = None) -> str | None:
    for key, value in element.attrib.items():
        if _ttml_local_name(key) == name.lower():
            return str(value)
    return default


def _parse_ttml_time(value: str, *, frame_rate: float, tick_rate: float) -> float:
    raw = str(value).strip()
    if not raw:
        raise ValueError("TTML 时间不能为空")
    # TTML clock time: hh:mm:ss[.fraction], mm:ss[.fraction], or ss[.fraction].
    if ":" in raw:
        return parse_timestamp(raw)
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(h|m|s|ms|f|t)?", raw, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"不支持的 TTML 时间: {value}")
    number = float(match.group(1))
    unit = (match.group(2) or "s").lower()
    if number < 0:
        raise ValueError(f"TTML 时间不能为负数: {value}")
    if unit == "h":
        return number * 3600.0
    if unit == "m":
        return number * 60.0
    if unit == "ms":
        return number / 1000.0
    if unit == "f":
        return number / max(frame_rate, 1e-9)
    if unit == "t":
        return number / max(tick_rate, 1e-9)
    return number


def _ttml_text(element: ET.Element) -> str:
    chunks: list[str] = []
    if element.text:
        chunks.append(element.text)
    for child in list(element):
        if _ttml_local_name(child.tag) == "br":
            chunks.append("\n")
        else:
            chunks.append(_ttml_text(child))
        if child.tail:
            chunks.append(child.tail)
    return "".join(chunks)


def parse_ttml(text: str) -> list[dict[str, Any]]:
    """Parse common TTML/DFXP cues into the shared caption contract.

    The parser intentionally accepts clock and offset time expressions only.
    It rejects external entity declarations and unsupported timing syntax so a
    local Agent cannot silently invent cue boundaries.
    """
    if re.search(r"<!DOCTYPE|<!ENTITY|SYSTEM\s+['\"]", text, flags=re.IGNORECASE):
        raise argument_error("TTML 不允许外部实体或 DTD", "input")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise argument_error(f"TTML XML 无效: {exc}", "input") from exc
    if _ttml_local_name(root.tag) not in {"tt", "ttml"}:
        raise argument_error("XML 不是 TTML/DFXP 文档", "input")
    try:
        frame_rate = float(_ttml_attribute(root, "frameRate", "30") or 30.0)
        multiplier = (_ttml_attribute(root, "frameRateMultiplier", "1 1") or "1 1").split()
        if len(multiplier) == 2:
            frame_rate *= float(multiplier[0]) / max(float(multiplier[1]), 1e-9)
        tick_rate = float(_ttml_attribute(root, "tickRate", "1") or 1.0)
    except (TypeError, ValueError) as exc:
        raise argument_error("TTML frameRate/frameRateMultiplier/tickRate 无效", "input") from exc
    if frame_rate <= 0 or tick_rate <= 0:
        raise argument_error("TTML frameRate 和 tickRate 必须大于 0", "input")
    cues: list[dict[str, Any]] = []

    def walk(element: ET.Element, parent_begin: float = 0.0, parent_end: float | None = None) -> None:
        begin_raw = _ttml_attribute(element, "begin")
        end_raw = _ttml_attribute(element, "end")
        dur_raw = _ttml_attribute(element, "dur")
        try:
            begin = parent_begin + (_parse_ttml_time(begin_raw, frame_rate=frame_rate, tick_rate=tick_rate) if begin_raw else 0.0)
            end = parent_end
            if end_raw:
                end = parent_begin + _parse_ttml_time(end_raw, frame_rate=frame_rate, tick_rate=tick_rate)
            elif dur_raw:
                end = begin + _parse_ttml_time(dur_raw, frame_rate=frame_rate, tick_rate=tick_rate)
        except ValueError as exc:
            raise argument_error(str(exc), "input") from exc
        if _ttml_local_name(element.tag) == "p":
            if end is None:
                raise argument_error("TTML cue 缺少 end 或 dur", "input")
            body = _ttml_text(element).strip()
            if body:
                cues.append(_cue(begin, end, body, index=len(cues) + 1, source_format="ttml"))
        for child in list(element):
            walk(child, begin, end)

    walk(root)
    return sorted(cues, key=lambda item: (float(item["start"]), float(item["end"])))


def parse_caption_text(text: str, suffix: str = ".srt") -> list[dict[str, Any]]:
    suffix = suffix.lower()
    if suffix == ".vtt":
        return parse_vtt(text)
    if suffix in {".ass", ".ssa"}:
        return parse_ass(text)
    if suffix in {".ttml", ".dfxp", ".xml"}:
        return parse_ttml(text)
    return parse_srt(text)


def parse_caption_file(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        raise AppError("SUBTITLE_FILE_MISSING", f"字幕文件不存在: {path}", exit_code=3, path=str(path))
    try:
        return parse_caption_text(path.read_text(encoding="utf-8-sig"), path.suffix)
    except UnicodeDecodeError as exc:
        raise AppError("SUBTITLE_ENCODING_INVALID", f"字幕不是有效 UTF-8 文件: {path}", exit_code=3, path=str(path), cause=str(exc)) from exc


def validate_cues(cues: Iterable[dict[str, Any]], duration: float | None = None, *, allow_overlap: bool = False) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    normalized = sorted((dict(item) for item in cues), key=lambda item: (float(item.get("start", 0)), float(item.get("end", 0))))
    previous_end = 0.0
    for index, cue in enumerate(normalized, start=1):
        try:
            start = float(cue.get("start"))
            end = float(cue.get("end"))
        except (TypeError, ValueError):
            errors.append({"code": "SUBTITLE_TIME_INVALID", "index": index, "message": "字幕时间码不是数字"})
            continue
        if start < 0 or end <= start:
            errors.append({"code": "SUBTITLE_TIME_RANGE_INVALID", "index": index, "message": "字幕起点必须小于终点且不小于 0"})
        if not str(cue.get("text", "")).strip():
            errors.append({"code": "SUBTITLE_TEXT_EMPTY", "index": index, "message": "字幕文本不能为空"})
        if not allow_overlap and start < previous_end - 1e-6:
            errors.append({"code": "SUBTITLE_OVERLAP", "index": index, "message": "字幕 cue 发生时间重叠"})
        if duration is not None and end > duration + 1e-6:
            errors.append({"code": "SUBTITLE_OUTSIDE_DURATION", "index": index, "message": "字幕超出媒体时长", "duration": duration, "end": end})
        previous_end = max(previous_end, end)
    return {"ok": not errors, "count": len(normalized), "duration": duration, "errors": errors, "cues": normalized}


def _stamp(value: float) -> str:
    milliseconds = max(0, int(round(float(value) * 1000)))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def cues_to_srt(cues: Iterable[dict[str, Any]], *, preserve_order: bool = False) -> str:
    lines: list[str] = []
    ordered = cues if preserve_order else sorted(cues, key=lambda item: (float(item.get("start", 0)), float(item.get("end", 0))))
    for index, cue in enumerate(ordered, start=1):
        lines.extend([str(index), f"{_stamp(float(cue.get('start', 0)))} --> {_stamp(float(cue.get('end', 0)))}", str(cue.get("text", "")).strip(), ""])
    return "\n".join(lines)


def write_srt_file(path: Path, cues: Iterable[dict[str, Any]], *, preserve_order: bool = False) -> None:
    atomic_write_text(path, cues_to_srt(cues, preserve_order=preserve_order))
