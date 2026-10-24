"""Development-only acquisition of a pinned official ModelScope model snapshot.

Inference never imports this downloader or resolves a remote model identifier.
Existing complete files and resumable partials are verified, never overwritten.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "Qwen/Qwen3-ForcedAligner-0.6B-hf"
REVISION = "053506a54ad1c9deea6105050330d7c500b9f098"
TARGET = ROOT / "product/.runtime/models/qwen3-aligner-0.6b-hf-20261025"
EVIDENCE = ROOT / "docs/validation/evidence/implementation-20261025-r1/aligner-acquisition"


def save(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024**2):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    metadata_path = ROOT / "sources/alignment-20261025/native-modelscope.json"
    metadata = json.loads(metadata_path.read_bytes())
    files = [row for row in metadata["Data"]["Files"] if row["Type"] == "blob"]
    if not files or any(row["Revision"] != REVISION or Path(row["Path"]).name != row["Path"] for row in files):
        raise ValueError("Snapshot revision or file paths do not match the pinned official snapshot")
    TARGET.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    state = {"repository": REPOSITORY, "revision": REVISION, "source": "official ModelScope Qwen organization",
             "metadata_sha256": digest(metadata_path), "development_network": True,
             "runtime_downloads": False, "weights_executed": False, "files": []}
    save(EVIDENCE / "inventory.json", state)
    # Configuration and licensing documentation are verified before the large weight file.
    files.sort(key=lambda row: (row["Path"] == "model.safetensors", row["Path"]))
    for row in files:
        name, expected_size, expected_sha = row["Path"], row["Size"], row["Sha256"]
        path = TARGET / name
        part = TARGET / (name + ".part")
        url = "https://modelscope.cn/api/v1/models/" + REPOSITORY + "/repo?" + urllib.parse.urlencode(
            {"Revision": REVISION, "FilePath": name})
        record = {"file": name, "expected_bytes": expected_size, "sha256": expected_sha,
                  "source_url": url, "attempts": []}
        if not path.exists():
            for attempt in range(4):
                received = part.stat().st_size if part.exists() else 0
                if received > expected_size:
                    raise ValueError("Partial file exceeds pinned size")
                if received == expected_size:
                    break
                headers = {"User-Agent": "agent-editor-kit-development-model-acquisition"}
                if received:
                    headers["Range"] = f"bytes={received}-"
                step = {"offset": received}
                record["attempts"].append(step)
                try:
                    started = time.monotonic()
                    request = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(request, timeout=30) as response:
                        if received and (response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {received}-")):
                            raise ValueError("Server did not honor resume; partial preserved")
                        with part.open("ab" if received else "xb") as stream:
                            reported = received
                            while block := response.read(4 * 1024**2):
                                if received + len(block) > expected_size:
                                    raise ValueError("Response exceeds pinned size")
                                stream.write(block)
                                received += len(block)
                                if received - reported >= 32 * 1024**2:
                                    save(EVIDENCE / "progress.json", {"file": name, "received": received,
                                         "expected": expected_size, "elapsed_seconds": round(time.monotonic() - started, 3)})
                                    reported = received
                            stream.flush()
                            os.fsync(stream.fileno())
                    if received != expected_size:
                        raise ValueError("Incomplete response")
                    break
                except Exception as exc:
                    step["error"] = repr(exc)
                    save(EVIDENCE / "current.json", record)
                    if attempt == 3:
                        raise
            if part.stat().st_size != expected_size or digest(part) != expected_sha:
                raise ValueError("Acquired model file did not match the pinned SHA-256")
            part.rename(path)
        if path.stat().st_size != expected_size or digest(path) != expected_sha:
            raise ValueError("Existing model file did not match the pinned SHA-256")
        record["status"] = "verified"
        state["files"].append(record)
        save(EVIDENCE / "inventory.json", state)
        print(json.dumps({"file": name, "bytes": expected_size, "status": "verified"}), flush=True)
    state["status"] = "downloaded_verified"
    state["generator_sha256"] = digest(Path(__file__))
    save(EVIDENCE / "inventory.json", state)


if __name__ == "__main__":
    main()
