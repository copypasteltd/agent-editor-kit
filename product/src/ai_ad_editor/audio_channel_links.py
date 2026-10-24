"""Preserve exact source-channel identities after nonlinear time stretching.

Independent-channel phase processing can break even an exact R = -L input.
Only silence, sample-exact copies and sample-exact sign inversions are linked.
Near correlations and arbitrary stereo phase are deliberately not inferred.
The original source and the engine's raw output remain separately auditable.
"""
from __future__ import annotations

from pathlib import Path
import struct

from .errors import AppError

POLICY = "exact-channel-identity-and-inversion-v1"
BLOCK_FRAMES = 65536


def _checkpoint(cancel_file: Path | None) -> None:
    if cancel_file is not None and cancel_file.exists():
        raise AppError("CANCELLED", "声道关系核验或重建已取消", exit_code=8, path=str(cancel_file))


def detect_links(source: Path, pcm: dict, *, cancel_file: Path | None = None) -> dict:
    import numpy as np

    channels, frames = pcm["channels"], pcm["frames"]
    if not 1 <= channels <= 8 or frames < 1:
        raise AppError("AUDIO_CHANNEL_LINK_PCM_INVALID", "声道关系需要非空的 1..8 声道 PCM", exit_code=6)
    same = np.ones((channels, channels), dtype=bool)
    inverse = same.copy()
    silent = np.ones(channels, dtype=bool)
    checked = 0
    with source.open("rb") as stream:
        stream.seek(pcm["data_offset"])
        while checked < frames:
            _checkpoint(cancel_file)
            count = min(BLOCK_FRAMES, frames - checked)
            raw = stream.read(count * channels * 4)
            if len(raw) != count * channels * 4:
                raise AppError("AUDIO_CHANNEL_LINK_PCM_INVALID", "声道关系输入 PCM 截断", exit_code=6)
            block = np.frombuffer(raw, dtype="<f4").reshape(count, channels)
            if not np.isfinite(block).all():
                raise AppError("AUDIO_CHANNEL_LINK_PCM_INVALID", "声道关系输入含 NaN/Inf", exit_code=6)
            silent &= np.all(block == 0, axis=0)
            for channel in range(1, channels):
                for reference in range(channel):
                    if same[channel, reference]:
                        same[channel, reference] = np.array_equal(block[:, channel], block[:, reference])
                    if inverse[channel, reference]:
                        inverse[channel, reference] = np.array_equal(block[:, channel], -block[:, reference])
            checked += count
    _checkpoint(cancel_file)
    links = []
    for channel in range(channels):
        if silent[channel]:
            links.append({"channel": channel, "reference": None, "gain": 0})
            continue
        for reference in range(channel):
            if same[channel, reference] or inverse[channel, reference]:
                links.append({"channel": channel, "reference": reference,
                              "gain": 1 if same[channel, reference] else -1})
                break
    return {"policy": POLICY, "input_pcm_sha256": pcm["sha256"],
            "verified_source_frames": checked, "channels": channels, "links": links,
            "equality": "all-source-samples-exact-no-correlation-threshold",
            "arbitrary_stereo_phase_accepted": False}


def canonical_linked_pcm(source: Path, destination: Path, pcm: dict, proof: dict,
                         *, start_frame: int = 0, frames: int | None = None,
                         cancel_file: Path | None = None) -> dict:
    """Crop engine output and restore only independently proven channel links."""
    import numpy as np

    channels = pcm["channels"]
    frames = pcm["frames"] - start_frame if frames is None else frames
    links = proof.get("links")
    valid = (proof.get("policy") == POLICY and proof.get("channels") == channels
             and type(start_frame) is int and type(frames) is int and frames > 0
             and start_frame >= 0 and start_frame + frames <= pcm["frames"]
             and isinstance(links, list))
    seen = set()
    if valid:
        for item in links:
            if not isinstance(item, dict) or set(item) != {"channel", "reference", "gain"}:
                valid = False
                break
            channel, reference, gain = item["channel"], item["reference"], item["gain"]
            if (type(channel) is not int or channel in seen or not 0 <= channel < channels
                    or type(gain) is not int or gain not in (-1, 0, 1)
                    or (gain == 0 and reference is not None)
                    or (gain != 0 and (type(reference) is not int or not 0 <= reference < channel))):
                valid = False
                break
            seen.add(channel)
    if not valid:
        raise AppError("AUDIO_CHANNEL_LINKS_INVALID", "声道关系或输出采样范围无效", exit_code=6)
    _checkpoint(cancel_file)
    links = sorted(links, key=lambda row: row["channel"])
    size = frames * channels * 4
    fmt = struct.pack("<HHIIHH", 3, channels, 48000, 48000 * channels * 4, channels * 4, 32)
    deltas = {row["channel"]: 0.0 for row in links}
    with source.open("rb") as stream, destination.open("xb") as target:
        target.write(b"RIFF" + struct.pack("<I", size + 36) + b"WAVEfmt " + struct.pack("<I", 16)
                     + fmt + b"data" + struct.pack("<I", size))
        stream.seek(pcm["data_offset"] + start_frame * channels * 4)
        remaining = frames
        while remaining:
            _checkpoint(cancel_file)
            count = min(BLOCK_FRAMES, remaining)
            raw = stream.read(count * channels * 4)
            if len(raw) != count * channels * 4:
                raise AppError("AUDIO_CHANNEL_LINK_PCM_INVALID", "声道关系输出 PCM 截断", exit_code=6)
            original = np.frombuffer(raw, dtype="<f4").reshape(count, channels)
            if not np.isfinite(original).all():
                raise AppError("AUDIO_CHANNEL_LINK_PCM_INVALID", "声道关系输出含 NaN/Inf", exit_code=6)
            block = original.copy()
            for link in links:
                channel, reference, gain = link["channel"], link["reference"], link["gain"]
                block[:, channel] = 0 if gain == 0 else block[:, reference] * gain
                deltas[channel] = max(deltas[channel], float(np.max(np.abs(
                    block[:, channel].astype(np.float64) - original[:, channel]))))
            target.write(block.tobytes())
            remaining -= count
        _checkpoint(cancel_file)
    return {**proof, "output_frames": frames,
            "engine_output_max_abs_change": [{"channel": channel, "maximum": delta}
                                              for channel, delta in sorted(deltas.items())],
            "unlinked_channel_pcm_bytes_preserved": True,
            "arbitrary_stereo_phase_accepted": False}
