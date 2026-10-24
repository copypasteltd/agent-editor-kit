"""Freeze the latest installed-goal assessment separately from candidate work.

No rendering, model inference or product-code mutation is performed here.
Candidate test/setup receipts are copies of prior executions, not reruns.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/validation/evidence/goal-gaps-20261025-r3"
GIT = Path("C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe")


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8", newline="\n")


def git(*args):
    return subprocess.run([str(GIT), "--no-optional-locks", "-c", "core.fsmonitor=false",
                           "-c", "core.quotePath=false", *args], cwd=ROOT,
                          capture_output=True, encoding="utf8", check=True).stdout


def collect():
    inventory = read(BASE / "inventory.json")
    assert len(inventory["calls"]) == 6
    assert all(c["exit_code"] == 0 and c["ok"] is True and c["status"] == "succeeded"
               for c in inventory["calls"])
    assert inventory["capability_count"] == 72
    assert inventory["capability_status_counts"] == dict(
        implemented=20, implemented_with_limits=44, local_adapter_only=7, degraded=1)
    assert read(BASE / "logs/version.stdout.json")["data"]["cli_version"] == "0.1.4"
    installed = Path(inventory["runtime"]["installed_directory"])
    candidate_base = ROOT / "docs/validation/evidence/semantic-20261025-r1"
    copies = []
    for source, name in [
        (candidate_base / "contract-tests-r2.json", "candidate-contract-tests.json"),
        (candidate_base / "contract-tests-r2.log", "candidate-contract-tests.log"),
        (candidate_base / "development-r1/setup/verification.json", "candidate-setup.json"),
        (candidate_base / "development-r1/setup/calls.json", "candidate-setup-calls.json"),
    ]:
        destination = BASE / name
        assert not destination.exists()
        destination.write_bytes(source.read_bytes())
        copies.append(dict(source=source.relative_to(ROOT).as_posix(), copy=name,
                           bytes=destination.stat().st_size, sha256=sha(destination), reexecuted=False))
    tests = read(BASE / "candidate-contract-tests.json")
    setup = read(BASE / "candidate-setup.json")
    assert tests["methods"] == 25 and tests["terminal_ok"] and tests["frozen_equal"] and tests["skipped"] == 0
    assert setup["status"] == "passed" and setup["commands"] == 13 and setup["development_source_only"]
    candidate_files = []
    for name in ("semantic_contract.py", "semantic_sampling.py", "semantic_worker.py", "semantic.py", "semantic_cli.py"):
        path = ROOT / "product/src/ai_ad_editor" / name
        candidate_files.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path),
            exists_in_installed_package=(installed / "site/ai_ad_editor" / name).exists(),
            equals_tested_source=("sha256:" + sha(path) == tests["frozen_after"][path.relative_to(ROOT).as_posix()])))
    assert all(row["equals_tested_source"] and not row["exists_in_installed_package"] for row in candidate_files)
    alignment = read(ROOT / "docs/validation/evidence/implementation-20261025-r1/native-aligner-research/quality.json")
    errors = [c["max_error_ms"] for c in alignment["results"][0]["cases"]]
    assert errors == [220.0, 161.0] and not alignment["results"][0]["passed_both_fixtures"]
    report = dict(status="reviewed", checked_at_utc=datetime.now(timezone.utc).isoformat(),
        source_commit=inventory["source_commit"], inventory_sha256=sha(BASE / "inventory.json"),
        candidate_evidence_copies=copies, candidate_files=candidate_files,
        candidate_semantic=dict(contract_tests_passed=25, setup_commands_passed=13,
            test_scope="Contract/integrity tests include mocked embeddings; setup performs no model forward.",
            installed=False, delivered_via_skill=False, relevance_accepted=False,
            complete_G26=False, separate_live_inference_is_not_this_read_only_assessment=True),
        historical_alignment=dict(threshold_ms=1000 * 2 / 30, maximum_errors_ms=errors,
                                   passed=False, rerun=False),
        gap_group_ids=[f"G{i:02}" for i in range(1, 39)], fully_closed_gap_groups=[],
        public_release=inventory["public_release_check"],
        overall_completion_percentage_established=False,
        fresh_installed_read_only_calls=6, fresh_model_forwards=0, fresh_renders=0,
        human_listening=False, human_quality_acceptance=False, historical_full_regression_rerun=False,
        new_competitor_feature_audit=False, browser_tabs_opened=0, virtualization_used=False,
        generator_sha256=sha(Path(__file__)))
    save(BASE / "review.json", report)
    print(json.dumps(dict(status=report["status"], installed_cli="0.1.4", installed_capabilities=72,
          candidate_contract_tests=25, candidate_setup_commands=13, closed_gap_groups=0), ensure_ascii=False))


def verify():
    report = read(BASE / "review.json")
    paths = [ROOT / name for name in ("README.md", "README.zh-TW.md", "README.en.md")]
    commands = []
    for path in paths:
        content = path.read_text("utf8")
        previous = git("show", report["source_commit"] + ":" + path.name)
        for prefix, count in (("F",49),("S",17),("K",17),("R",44)):
            ids = re.findall(r"^\| (" + prefix + r"\d\d)(?: /| \|)", content, re.M)
            assert len(ids) == len(set(ids)) == count, (path.name,prefix)
        for row in re.findall(r"^\| R\d\d \|.*$",previous,re.M):
            assert row in content, (path.name,"historical row changed")
        assert len(content) >= len(previous)
        commands.append(re.findall(r"```powershell\n(.*?)```",content,re.S))
    assert commands[0] == commands[1] == commands[2]
    paths += [ROOT / name for name in ("docs/README.md", "docs/product/GOAL_GAPS_20261025.md",
                                       "docs/product/IMPLEMENTATION_PLAN_20261025.md")]
    gaps = (ROOT / "docs/product/GOAL_GAPS_20261025.md").read_text("utf8")
    assert re.findall(r"^\| (G\d\d) \|",gaps,re.M) == report["gap_group_ids"]
    paths += list((ROOT / "skills/agent-ffmpeg-local-editor").rglob("*.md"))
    links = 0
    for path in paths:
        content = re.sub(r"```[\s\S]*?```", "", path.read_text("utf8"))
        content = re.sub(r"`[^`\n]+`", "", content)
        for target in re.findall(r"!?\[[^\]]*\]\(([^\n)]+)\)", content):
            if re.match(r"^[a-z]+:",target) or target.startswith("#"): continue
            assert (path.parent / unquote(target.split("#")[0])).resolve().exists(), (path,target)
            links += 1
    for row in report["candidate_evidence_copies"]:
        assert sha(BASE / row["copy"]) == row["sha256"]
    result = dict(status="passed", checked_at_utc=datetime.now(timezone.utc).isoformat(),
        readme_counts=dict(F=49,S=17,K=17,R=44), preserved_historical_verification_rows=129,
        three_readme_command_blocks_identical=True, readmes_not_shortened=True,
        stable_gap_ids=38, fully_closed_gap_groups=0, local_links_checked=links,
        review_sha256=sha(BASE / "review.json"), document_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths},
        generator_sha256=sha(Path(__file__)), complete_goal_accepted=False)
    save(BASE / "documentation-verification.json",result)
    print(json.dumps({k:v for k,v in result.items() if k!="document_hashes"},ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("collect","verify"))
    args = parser.parse_args()
    (collect if args.phase=="collect" else verify)()
