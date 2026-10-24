"""Review existing evidence and check the current goal-assessment documentation.

No media rendering, inference, test-suite execution or human acceptance occurs.
The six fresh installed queries are recorded by assess_goal_gaps_20261025.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/validation/evidence/goal-gaps-20261025-r2"
GIT = Path("C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe")


def read(path: Path) -> dict:
    return json.loads(path.read_bytes())


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        [str(GIT), "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.quotePath=false", *args],
        cwd=ROOT, capture_output=True, encoding="utf-8", check=True,
    ).stdout


def main() -> None:
    review_path = BASE / "review.json"
    verification_path = BASE / "documentation-verification.json"
    assert not review_path.exists() and not verification_path.exists()
    inventory = read(BASE / "inventory.json")
    assert len(inventory["calls"]) == 6
    assert all(c["exit_code"] == 0 and c["ok"] is True and c["status"] == "succeeded"
               for c in inventory["calls"])
    assert inventory["runtime"]["release"] == "v0.1.0-alpha.4-local.2"
    assert read(BASE / "logs/version.stdout.json")["data"]["cli_version"] == "0.1.4"
    assert inventory["capability_count"] == 72
    assert inventory["capability_status_counts"] == {
        "implemented": 20, "implemented_with_limits": 44, "local_adapter_only": 7, "degraded": 1,
    }
    assert inventory["public_release_check"]["status"] == "checked"
    assert inventory["public_release_check"]["latest_published_tag"] == "v0.1.0-alpha.3"

    historical_paths = [
        "audio-channel-tests-r1.json", "audio-regression-r1.json", "installed-channel-tests-r1.json",
        "native-capture-installed-r3/verification.json", "native-aligner-research/quality.json",
        "skill/verification.json",
    ]
    historical = []
    implementation = ROOT / "docs/validation/evidence/implementation-20261025-r1"
    for relative in historical_paths:
        path = implementation / relative
        data = read(path)
        historical.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
                           "status": data.get("status"), "methods": data.get("methods"),
                           "commands": data.get("commands"), "reexecuted_in_this_review": False})
    quality = read(implementation / "native-aligner-research/quality.json")
    assert quality["unchanged_max_error_seconds"] == 2 / 30
    assert [c["max_error_ms"] for c in quality["results"][0]["cases"]] == [220.0, 161.0]
    assert quality["results"][0]["passed_both_fixtures"] is False

    installed_site = Path(inventory["runtime"]["installed_directory"]) / "site/ai_ad_editor"
    development = []
    for name in ("semantic_contract.py", "semantic.py", "semantic_worker.py", "semantic_cli.py"):
        path = ROOT / "product/src/ai_ad_editor" / name
        development.append({"path": path.relative_to(ROOT).as_posix(), "exists_in_working_tree": path.exists(),
                            "sha256": sha(path) if path.exists() else None,
                            "exists_in_installed_package": (installed_site / name).exists()})
    assert development[0]["exists_in_working_tree"]
    assert not any(r["exists_in_working_tree"] for r in development[1:])
    assert not any(r["exists_in_installed_package"] for r in development)
    acquisition = ROOT / "docs/validation/evidence/semantic-20261025-r1/acquisition/inventory.json"
    acquisition_data = read(acquisition)
    assert acquisition_data["status"] == "downloaded_verified"
    report = {
        "status": "evidence_reviewed", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": inventory["source_commit"], "inventory_sha256": sha(BASE / "inventory.json"),
        "historical_evidence": historical,
        "alignment": {"threshold_ms": 1000 * 2 / 30, "maximum_errors_ms": [220.0, 161.0],
                      "passed": False, "reference_kind": "authored word blocks, not human phonetic annotation",
                      "rerun_in_this_review": False},
        "semantic_development": {"files": development,
            "acquisition_receipt_sha256": sha(acquisition),
            "acquisition_state": acquisition_data["status"],
            "receipt_committed_at_review": bool(git("ls-files", "--", acquisition.relative_to(ROOT).as_posix()).strip()),
            "product_index_and_search_implemented": False, "relevance_benchmark_executed": False,
            "included_in_installed_capabilities": False,
            "scope": "Development preparation only; the acquisition and partial source are not this documentation delivery."},
        "gap_group_ids": [f"G{i:02}" for i in range(1, 39)], "fully_closed_gap_groups": [],
        "group_count_is_not_a_completion_percentage": True,
        "fresh_renders": 0, "fresh_model_inferences": 0, "human_listening": False,
        "historical_regression_reexecuted": False, "new_competitor_feature_audit": False,
        "browser_tabs_opened": 0, "virtualization_used": False,
        "generator_sha256": sha(Path(__file__)),
    }
    review_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    docs = [ROOT / n for n in ("README.md", "README.zh-TW.md", "README.en.md")]
    commands = []
    for path in docs:
        text = path.read_text("utf-8")
        previous = git("show", f"{inventory['source_commit']}:{path.name}")
        for prefix, expected in (("F", 49), ("S", 17), ("K", 17), ("R", 43)):
            ids = re.findall(r"^\| (" + prefix + r"\d\d)(?: /| \|)", text, re.M)
            assert len(ids) == len(set(ids)) == expected, (path.name, prefix)
        for row in re.findall(r"^\| R\d\d \|.*$", previous, re.M):
            assert row in text, (path.name, "historical verification row changed")
        assert len(text) > 35000 and len(text) >= len(previous)
        commands.append(re.findall(r"```powershell\n(.*?)```", text, re.S))
    assert commands[0] == commands[1] == commands[2]
    gap_path = ROOT / "docs/product/GOAL_GAPS_20261025.md"
    assert re.findall(r"^\| (G\d\d) \|", gap_path.read_text("utf-8"), re.M) == report["gap_group_ids"]
    docs += [ROOT / n for n in ("docs/README.md", "docs/product/GOAL_GAPS_20261025.md",
                                "docs/product/IMPLEMENTATION_PLAN_20261025.md")]
    docs += list((ROOT / "skills/agent-ffmpeg-local-editor").rglob("*.md"))
    links = 0
    for path in docs:
        text = re.sub(r"```[\s\S]*?```", "", path.read_text("utf-8"))
        text = re.sub(r"`[^`\n]+`", "", text)
        for target in re.findall(r"!?\[[^\]]*\]\(([^\n)]+)\)", text):
            if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                continue
            assert (path.parent / unquote(target.split("#")[0])).resolve().exists(), (path, target)
            links += 1
    result = {"status": "passed", "readme_ids": {"F": 49, "S": 17, "K": 17, "R": 43},
              "all_126_historical_readme_rows_preserved": True,
              "three_readme_commands_identical": True, "readmes_not_shortened": True,
              "stable_gap_ids": 38, "fully_closed_gap_groups": 0,
              "local_links_checked": links, "review_sha256": sha(review_path),
              "document_hashes": {p.relative_to(ROOT).as_posix(): sha(p) for p in docs},
              "generator_sha256": sha(Path(__file__)), "complete_goal_accepted": False}
    verification_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "document_hashes"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
