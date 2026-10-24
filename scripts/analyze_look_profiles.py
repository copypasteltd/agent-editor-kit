"""Describe installed look bytes and compare historical native PNGs, offline.

This documentation analysis never edits/rebuilds the installed app or renders
new videos. The RGB samples are encoded SDR values, not linear-light readings.
"""
from __future__ import annotations

import colorsys
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from build_look_catalog import tetra


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/validation/evidence/look-profiles-20261024-r1"
MEDIA = ROOT / "docs/assets/look-profiles-20261024-r1"
HISTORICAL = ROOT / "docs/assets/look-presets-20261024-r1"
GRAY_CODES = [0., 25.5, 63.75, 127.5, 191.25, 229.5, 255.]
SAMPLE_CODES = np.array(
    [[v] * 3 for v in GRAY_CODES]
    + [[245, 219, 198], [207, 155, 123], [129, 84, 56],
       [192, 64, 64], [64, 160, 80], [64, 112, 192]],
    dtype=np.float64,
)
SAMPLE_KEYS = ["gray_0", "gray_10", "gray_25", "gray_50", "gray_75",
               "gray_90", "gray_100", "skin_light", "skin_medium",
               "skin_dark", "red", "green", "blue"]
WEIGHTS = np.array([.2126, .7152, .0722])


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sample_info(rgb):
    rounded = np.rint(np.clip(rgb, 0, 1) * 255).astype(int)
    h, s, v = colorsys.rgb_to_hsv(*np.clip(rgb, 0, 1))
    return {"rgb_code": [round(float(x) * 255, 6) for x in rgb],
            "hex": "#" + "".join(f"{x:02X}" for x in rounded),
            "y_code": round(float(rgb @ WEIGHTS * 255), 6),
            "hsv": {"h_degrees": round(h * 360, 6), "s": round(s, 6), "v": round(v, 6)}}


def read_cube(raw, expected_size):
    lines = raw.decode("ascii").splitlines()
    assert f"LUT_3D_SIZE {expected_size}" in lines
    assert "DOMAIN_MIN 0 0 0" in lines and "DOMAIN_MAX 1 1 1" in lines
    rows = [line for line in lines if line and (line[0].isdigit() or line[0] in "-+.")]
    table = np.loadtxt(rows, dtype=np.float64)
    assert table.shape == (expected_size ** 3, 3) and np.isfinite(table).all()
    return table


def palette(records, first, last):
    selected = records[first - 1:last]
    width, row_height, label_width, cell = 1460, 34, 290, 88
    height = 140 + (len(selected) + 1) * row_height + 48
    picture = Image.new("RGB", (width, height), "#101820")
    draw = ImageDraw.Draw(picture)
    heading = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 15)
    small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 13)
    draw.text((18, 14), f"agent editor kit | measured LUT palettes {first:03}-{last:03}", font=heading, fill="white")
    draw.text((18, 49), "Encoded SDR RGB; strength 1; direct LUT samples, not new video renders.", font=font, fill="#d5dfe8")
    draw.text((18, 72), "Gray levels: 0 / 10 / 25 / 50 / 75 / 90 / 100%. Skin: light / medium / dark. R/G/B: muted test colors.", font=small, fill="#d5dfe8")
    labels = ["0%", "10%", "25%", "50%", "75%", "90%", "100%", "Skin L", "Skin M", "Skin D", "Red", "Green", "Blue"]
    for i, label in enumerate(labels):
        draw.text((label_width + i * cell + 7, 109), label, font=small, fill="white")
    input_samples = {key: sample_info(rgb) for key, rgb in zip(SAMPLE_KEYS, SAMPLE_CODES / 255)}
    for line, record in enumerate([None] + selected):
        y = 140 + line * row_height
        label = "INPUT (before)" if record is None else f"{record['number']:03}  {record['name']}"
        draw.text((18, y + 7), label, font=font, fill="white")
        samples = input_samples if record is None else record["samples"]
        for i, key in enumerate(SAMPLE_KEYS):
            x = label_width + i * cell
            draw.rectangle((x, y + 2, x + cell - 6, y + row_height - 4), fill=samples[key]["hex"])
    draw.text((18, height - 29), "Pinned alpha.2 installed bytes; names retained from upstream; numerical details in LOOK_PRESET_DETAILS.md.", font=small, fill="#d5dfe8")
    target = MEDIA / f"palette-{first:03}-{last:03}.png"
    picture.save(target)
    return {"path": target.relative_to(ROOT).as_posix(), "sha256": sha(target.read_bytes()),
            "width": width, "height": height, "kind": "calculated LUT sample palette; not native video"}


def main():
    runtime = json.loads((ROOT / "local/agent-ffmpeg/runtime.json").read_bytes())
    installed = Path(runtime["installed_directory"]) / "site/ai_ad_editor/look_data"
    source = ROOT / "product/src/ai_ad_editor/look_data"
    catalog_bytes = (installed / "catalog.json").read_bytes()
    assert catalog_bytes == (source / "catalog.json").read_bytes()
    catalog = json.loads(catalog_bytes)
    assert catalog["count"] == len(catalog["records"]) == 100
    reference_path = HISTORICAL / "reference.png"
    reference = np.asarray(Image.open(reference_path).convert("RGB"))
    assert reference.shape == (300, 480, 3)
    inputs = SAMPLE_CODES / 255
    neutral = np.repeat(np.linspace(0, 1, 4097)[:, None], 3, axis=1)
    records = []
    for number, row in enumerate(catalog["records"], 1):
        packed = (installed / row["lut"]).read_bytes()
        assert packed == (source / row["lut"]).read_bytes()
        assert sha(packed) == row["packed_sha256"]
        raw = gzip.decompress(packed)
        assert sha(raw) == row["sha256"] and len(raw) == row["bytes"]
        table = read_cube(raw, row["grid_size"])
        clipped = np.clip(tetra(table, inputs), 0, 1)
        samples = {key: sample_info(value) for key, value in zip(SAMPLE_KEYS, clipped)}
        curve = np.clip(tetra(table, neutral), 0, 1)
        curve_y = curve @ WEIGHTS * 255
        native_path = HISTORICAL / "previews" / f"{row['id']}.png"
        native = np.asarray(Image.open(native_path).convert("RGB"))
        assert native.shape == reference.shape
        expected = np.rint(np.clip(tetra(table, reference.reshape(-1, 3) / 255), 0, 1) * 255).reshape(reference.shape)
        errors = np.abs(expected - native.astype(float))
        # FFmpeg and float64 NumPy may round a channel at adjacent byte codes.
        assert errors.max() <= 1, (row["id"], errors.max())
        samples_y = np.array([samples[key]["y_code"] for key in SAMPLE_KEYS])
        contrast = (samples_y[4] - samples_y[2]) / 127.5
        chroma = np.ptp(curve, axis=1) * 255
        vertex_chroma = np.ptp(np.clip(table, 0, 1), axis=1) * 255
        record = {"number": number, "id": row["id"], "name": row["name"], "category": row["category"],
                  "grid_size": row["grid_size"], "lut_sha256": row["sha256"],
                  "source": row["source"], "license": row["license"],
                  "normalization": row["normalization"], "samples": samples,
                  "cube_vertices": {"max_channel_spread_code": round(float(vertex_chroma.max()), 6),
                                    "mean_channel_spread_code": round(float(vertex_chroma.mean()), 6),
                                    "all_vertices_achromatic_within_one_code": bool(vertex_chroma.max() <= 1)},
                  "neutral_ramp": {"points": 4097, "monotonic_y_with_tolerance_1e_7": bool(np.diff(curve_y).min() >= -1e-7),
                                   "max_channel_spread_code": round(float(chroma.max()), 6),
                                   "midrange_chord_ratio_25_to_75": round(float(contrast), 6),
                                   "min_y_code": round(float(curve_y.min()), 6), "max_y_code": round(float(curve_y.max()), 6)},
                  "historical_native_png_comparison": {"path": native_path.relative_to(ROOT).as_posix(),
                                                       "sha256": sha(native_path.read_bytes()), "channel_samples": int(errors.size),
                                                       "max_abs_code_error": int(errors.max()),
                                                       "mean_abs_code_error": round(float(errors.mean()), 9)}}
        records.append(record)
        print(f"{number:03} {row['id']} analyzed; historical PNG max code error {errors.max():.0f}", flush=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    charts = [palette(records, 1, 49), palette(records, 50, 100)]
    result = {"scope": "2026-10-24 installed alpha.2 look documentation analysis", "catalog_version": catalog["version"],
              "runtime_release": runtime["release"], "catalog_sha256": sha(catalog_bytes),
              "script_sha256": sha(Path(__file__).read_bytes()), "record_count": len(records),
              "method": {"strength": 1.0, "interpolation": "tetrahedral", "domain": "encoded SDR RGB 0..1",
                         "grid_order": "red fastest; green next; blue slowest", "output_clamp": "0..1",
                         "gray_percent_inputs": [0, 10, 25, 50, 75, 90, 100],
                         "gray_percentage_is_code_level_not_scene_exposure": True,
                         "y_code": "255 * (0.2126 R' + 0.7152 G' + 0.0722 B'); code proxy, not linear light",
                         "contrast_ratio": "(Y'(gray 75%) - Y'(gray 25%)) / 127.5; tonal chord, not a perceptual contrast score",
                         "rounding": "hex is nearest 8-bit code via numpy.rint; measurements retain float64",
                         "inputs": {key: sample_info(value) for key, value in zip(SAMPLE_KEYS, inputs)},
                         "synthetic_reference_sha256": sha(reference_path.read_bytes()),
                         "native_comparison": "Full 480x300 historical FFmpeg PNGs; maximum permitted channel difference 1 byte code"},
              "counts": {"installed_luts_analyzed": 100, "source_bytes_equal_to_install": 100, "historical_pngs_compared": 100,
                         "native_png_channel_comparisons": 100 * 480 * 300 * 3, "new_native_renders": 0,
                         "natural_footage_reviews": 0, "new_product_regressions": 0},
              "palette_charts": charts, "records": records}
    save_json(EVIDENCE / "analysis.json", result)
    print(json.dumps({"status": "passed", "records": len(records), "evidence": str(EVIDENCE / 'analysis.json'),
                      "png_max_error": max(r['historical_native_png_comparison']['max_abs_code_error'] for r in records)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
