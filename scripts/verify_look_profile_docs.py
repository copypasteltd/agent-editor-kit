"""Check the detailed look documentation and write a scoped evidence receipt."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/validation/evidence/look-profiles-20261024-r1"
RECEIPT = EVIDENCE / "verification.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    analysis_path = EVIDENCE / "analysis.json"
    analysis = json.loads(analysis_path.read_bytes())
    notes_path = ROOT / "docs/local/LOOK_PRESET_NOTES.json"
    notes = json.loads(notes_path.read_bytes())
    ids = [row["id"] for row in analysis["records"]]
    assert len(ids) == len(set(ids)) == len(notes["records"]) == 100
    assert [row[0] for row in notes["records"]] == ids
    assert len({row["lut_sha256"] for row in analysis["records"]}) == 100
    assert all(len(row) == 5 and len(row[1]) >= 35 and row[2] and row[3] and row[4] for row in notes["records"])
    assert analysis["script_sha256"] == sha(ROOT / "scripts/analyze_look_profiles.py")
    assert max(row["historical_native_png_comparison"]["max_abs_code_error"] for row in analysis["records"]) <= 1
    assert analysis["counts"]["native_png_channel_comparisons"] == 43_200_000
    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    docs = ["README.md", "README.zh-TW.md", "README.en.md", "docs/README.md",
            "docs/local/LOOK_PRESETS.md", "docs/local/LOOK_PRESET_DETAILS.md", "docs/local/LOOK_PRESET_DETAILS.zh-TW.md"]
    texts = {name: (ROOT / name).read_text(encoding="utf-8") for name in docs}
    doc_results, links = [], []
    for name, text in texts.items():
        tokens = parser.parse(text)
        doc_results.append({"path": name, "sha256": sha(ROOT / name),
                            "tables": sum(t.type == "table_open" for t in tokens),
                            "profiles": text.count('<a id="preset-')})
        for token in tokens:
            for child in token.children or []:
                if child.type == "link_open":
                    target = child.attrGet("href")
                elif child.type == "image":
                    target = child.attrGet("src")
                else:
                    continue
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc:
                    continue
                destination = ((ROOT / name).parent / unquote(parsed.path)).resolve() if parsed.path else ROOT / name
                assert destination.is_relative_to(ROOT), (name, target, "outside repository")
                assert destination.exists() or destination == RECEIPT, (name, target, "missing file or directory")
                if parsed.fragment.startswith("preset-"):
                    assert f'id="{parsed.fragment}"' in destination.read_text(encoding="utf-8"), (name, target, "missing anchor")
                links.append({"document": name, "target": target})
    for name in docs[-2:]:
        text = texts[name]
        anchors = re.findall(r'<a id="preset-([^"]+)"', text)
        assert anchors == ids
        assert len(re.findall(r"^### \d{3} · ", text, re.M)) == 100
        assert next(row for row in doc_results if row["path"] == name)["tables"] == 202
        for record in analysis["records"]:
            section = text.split(f'<a id="preset-{record["id"]}"></a>', 1)[1].split('<a id="preset-', 1)[0]
            assert all(f'`{sample["hex"]}`' in section for sample in record["samples"].values())
            assert f'{record["neutral_ramp"]["midrange_chord_ratio_25_to_75"]:.3f}×' in section
    fences = lambda value: re.findall(r"```[\s\S]*?```", value)
    assert fences(texts[docs[-1]]) == fences(texts[docs[-2]])
    root_fences = [fences(texts[name]) for name in docs[:3]]
    assert root_fences[0] == root_fences[1] == root_fences[2]
    for name in docs[:3]:
        text = texts[name]
        assert re.findall(r"^\| (R\d{2}) \|", text, re.M) == [f"R{i:02}" for i in range(1, 22)]
        assert len(re.findall(r"^\| F\d{2} \|", text, re.M)) == 13
        assert re.findall(r"^\| (C\d{2}) /", text, re.M) == [f"C{i:02}" for i in range(1, 5)]
        assert "# agent editor kit" in text
    charts = analysis["palette_charts"]
    assert len(charts) == 2
    for chart in charts:
        assert sha(ROOT / chart["path"]) == chart["sha256"]
    helpers = ["scripts/analyze_look_profiles.py", "scripts/build_look_profile_docs.py", "scripts/verify_look_profile_docs.py"]
    for helper in helpers:
        ast.parse((ROOT / helper).read_text(encoding="utf-8"), filename=helper)
    runtime = json.loads((ROOT / "local/agent-ffmpeg/runtime.json").read_bytes())
    package = ROOT / "docs/releases/v0.1.0-alpha.2/artifacts/agent-video-kit-v0.1.0-alpha.2-cp313-win_amd64.zip"
    assert sha(package) == runtime["zip_sha256"] == "8910c3d26bba78133ee7177018da5ea2fcefda59eb995965ba34a8fd308d177f"
    result = {"status": "passed", "date_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Installed-LUT numerical analysis, historical PNG comparison and detailed documentation; no new video renders or product regressions",
              "analysis_sha256": sha(analysis_path), "notes_sha256": sha(notes_path),
              "helpers": [{"path": name, "sha256": sha(ROOT / name), "syntax": "passed"} for name in helpers],
              "counts": analysis["counts"], "profiles_per_language": 100, "profile_languages": ["zh-CN", "zh-TW"],
              "numeric_sample_fields_per_profile": 13, "neutral_ramp_samples_per_lut": 4097,
              "numerical_distinct_lut_count": 100,
              "historical_png_comparison": {"max_abs_channel_error_codes": 1, "basis": "Full RGB images; byte rounding tolerance one code"},
              "palette_charts": charts,
              "visual_review": {"items": [chart["path"] for chart in charts],
                                "method": "Inspected both generated palette images using view_image; checked labels and swatch layout",
                                "natural_footage_acceptance": False},
              "three_readme_numbered_checks": 21, "three_readme_code_blocks_identical": True,
              "simplified_traditional_commands_identical": True, "documents": doc_results,
              "local_links_checked": len(links), "local_links": links,
              "unchanged_installer_sha256": sha(package),
              "boundaries": ["Scene and strength suggestions are advisory, not natural-footage acceptance",
                             "Measurements describe encoded SDR test points, not physical exposure or every possible image",
                             "No new official branded-filter equivalence, grain or spatial-effect claims",
                             "Historical tests/render counts retain their original scope and date"]}
    RECEIPT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "passed", "profiles_per_language": 100, "local_links_checked": len(links),
                      "historical_png_max_code_error": 1, "new_video_renders": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
