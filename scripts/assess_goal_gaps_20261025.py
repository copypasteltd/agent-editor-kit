"""Read-only installed-release inventory for the 2026-10-25 goal assessment.

This records declarations and existing evidence; it does not render media,
perform model inference, or establish human quality acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
GIT = Path("C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe")


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "docs/validation/evidence") or output.exists():
        raise ValueError("Use a new evidence directory under this project's docs/validation/evidence.")
    output.mkdir(parents=True)
    logs = output / "logs"
    logs.mkdir()
    skill_root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills"
    launcher = skill_root / "agent-ffmpeg-local-editor/scripts/run.ps1"
    if launcher.resolve() != (ROOT / "skills/agent-ffmpeg-local-editor/scripts/run.ps1").resolve():
        raise ValueError("Discovery launcher must resolve to this checkout's canonical Skill.")
    runtime = json.loads((ROOT / "local/agent-ffmpeg/runtime.json").read_bytes())
    calls = []
    responses = {}
    for name, arguments in [
        ("version", ["version"]),
        ("doctor", ["doctor"]),
        ("capabilities", ["capabilities"]),
        ("schema", ["schema", "show"]),
        ("gpu", ["gpu", "inspect"]),
        ("packs", ["model-pack", "list"]),
    ]:
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(launcher), *arguments]
        start = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180)
        elapsed = time.monotonic() - start
        stdout_path = logs / f"{name}.stdout.json"
        stderr_path = logs / f"{name}.stderr.txt"
        stdout_path.write_bytes(result.stdout)
        stderr_path.write_bytes(result.stderr)
        data = json.loads(result.stdout.decode("utf-8-sig"))
        call = {"name": name, "argv": command, "exit_code": result.returncode,
                "ok": data.get("ok"), "status": data.get("status"),
                "elapsed_seconds": elapsed, "stdout_sha256": sha(stdout_path),
                "stderr_sha256": sha(stderr_path)}
        calls.append(call)
        save_json(output / "calls.json", calls)
        if result.returncode != 0 or data.get("ok") is not True or data.get("status") != "succeeded":
            raise RuntimeError(f"Installed read-only call failed: {name}")
        responses[name] = data
        print(json.dumps(call, ensure_ascii=False), flush=True)

    caps = responses["capabilities"]["data"]["capabilities"]
    previous = json.loads((ROOT / "docs/product/capabilities.json").read_bytes())
    old_caps = previous.get("data", previous)["capabilities"]
    unchanged = [key for key in old_caps if caps.get(key) == old_caps[key]]
    changed = [key for key in old_caps if caps.get(key) != old_caps[key]]
    materials = json.loads((ROOT / "product/src/ai_ad_editor/material_data/catalog.json").read_bytes())
    voices = json.loads((ROOT / "product/src/ai_ad_editor/material_data/voices.json").read_bytes())
    source_commit = subprocess.run([str(GIT), "--no-optional-locks", "-c", "core.fsmonitor=false", "rev-parse", "HEAD"],
                                   cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    existing = []
    base = ROOT / "docs/validation/evidence/community-materials-20261025-r1"
    for folder in ("cpu", "gpu", "portable", "skill", "kit", "cpu/presentation-correction"):
        path = base / folder / "verification.json"
        data = json.loads(path.read_bytes())
        existing.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
                         "status": data.get("status"), "commands": data.get("commands"),
                         "reexecuted_in_this_assessment": False})

    release_url = "https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10"
    release_check = {"url": release_url, "status": "unavailable"}
    try:
        request = Request(release_url, headers={"Accept": "application/vnd.github+json", "User-Agent": "agent-editor-kit-goal-assessment"})
        with urlopen(request, timeout=25) as response:
            body = response.read(2_000_000)
        (output / "github-releases.json").write_bytes(body)
        releases = json.loads(body)
        published = [r for r in releases if not r.get("draft") and r.get("published_at")]
        latest = max(published, key=lambda r: r["published_at"]) if published else None
        release_check.update(status="checked", latest_published_tag=latest["tag_name"] if latest else None,
                             latest_published_url=latest["html_url"] if latest else None,
                             latest_is_prerelease=latest["prerelease"] if latest else None,
                             response_sha256=sha(output / "github-releases.json"))
    except Exception as exc:
        release_check["error"] = f"{type(exc).__name__}: {exc}"

    report = {
        "status": "passed_read_only_inventory", "checked_at_taipei": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).isoformat(),
        "source_commit": source_commit, "runtime": runtime,
        "registered_skill": "agent-ffmpeg-local-editor", "internal_modules": 17,
        "calls": calls, "capability_count": len(caps),
        "capability_status_counts": dict(Counter(v.get("status", "unknown") for v in caps.values())),
        "previous_alpha3_capabilities": len(old_caps), "unchanged_alpha3_capabilities": len(unchanged),
        "changed_alpha3_capabilities": changed, "added_capabilities": sorted(set(caps) - set(old_caps)),
        "material_counts": materials["counts"], "voice_catalog_shape": list(voices) if isinstance(voices, dict) else "list",
        "existing_evidence": existing, "public_release_check": release_check,
        "fresh_render_count": 0, "fresh_model_inference_count": 0,
        "historical_full_regression_rerun": False, "human_listening_performed": False,
        "new_capcut_market_audit": False, "overall_completion_percentage_established": False,
        "scope": "Frozen project baseline versus installed CLI declarations and prior evidence; not full CapCut acceptance.",
    }
    save_json(output / "inventory.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"calls", "runtime", "existing_evidence"}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
