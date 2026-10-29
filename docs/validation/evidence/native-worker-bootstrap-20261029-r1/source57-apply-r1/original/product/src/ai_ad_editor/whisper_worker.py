"""Isolated native Whisper subprocess; never resolves remote models or code."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

PROTOCOL = "agent-video-whisper-asr-v1"


def install_network_guard(events: list[str]) -> None:
    import socket
    socket.has_ipv6 = False  # avoid urllib3's import-time loopback bind probe
    def audit(event: str, args: tuple) -> None:
        if event in {"socket.connect", "socket.connect_ex", "socket.bind", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.sendto", "urllib.Request", "http.client.connect"}:
            events.append(event)
            raise RuntimeError(f"ASR_NETWORK_DISABLED: {event}")
    sys.addaudithook(audit)


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    response_path = Path(request["response"])
    response = {"protocol": PROTOCOL, "status": "failed", "network": "disabled", "blocked_network_events": []}
    started = time.monotonic()
    try:
        if request.get("protocol") != PROTOCOL or request.get("network") != "disabled":
            raise ValueError("Invalid offline ASR request")
        install_network_guard(response["blocked_network_events"])
        runtime = Path(request["runtime_root"])
        for key, name in {"TEMP": "temp", "TMP": "temp", "TMPDIR": "temp", "HF_HOME": "hf", "HF_HUB_CACHE": "hf/hub", "TORCH_HOME": "torch", "XDG_CACHE_HOME": "cache"}.items():
            path = runtime / name
            path.mkdir(parents=True, exist_ok=True)
            os.environ[key] = str(path)
        os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1", "TOKENIZERS_PARALLELISM": "false", "TQDM_DISABLE": "1"})
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from ai_ad_editor.local_asr import verify_adapter, checked_transcription
        from ai_ad_editor.utils import sha256_file
        adapter = request["adapter"]
        if not verify_adapter(adapter)["ok"]:
            raise ValueError("ASR_INTEGRITY_FAILED")
        source = Path(request["input"])
        if "sha256:" + sha256_file(source) != request["input_sha256"]:
            raise ValueError("ASR_INPUT_HASH_MISMATCH")
        import torch
        import transformers
        torch.set_num_threads(int(adapter["threads"]))
        if adapter["device"] == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("ASR_CUDA_UNAVAILABLE")
            torch.cuda.reset_peak_memory_stats()
        from ai_ad_editor.transcribe import transcribe_local
        from ai_ad_editor.media import probe_media
        # FFmpeg is inherited from the CLI's installed local executable. This
        # subprocess never searches model registries or accepts a model URL.
        duration = float(probe_media(source).get("duration_seconds") or 0)
        value = transcribe_local(source, model_path=adapter["model_path"], language=request.get("language"), device=adapter["device"])
        value = checked_transcription(value, duration)
        if response["blocked_network_events"]:
            raise RuntimeError("ASR_NETWORK_ATTEMPT_REJECTED")
        response.update({"status": "succeeded", "transcription": value, "input_sha256": request["input_sha256"], "source_sha256": request["source_sha256"], "adapter_sha256": adapter["sha256"], "device": torch.cuda.get_device_name(0) if adapter["device"] == "cuda" else "cpu", "threads": adapter["threads"], "peak_cuda_bytes": torch.cuda.max_memory_allocated(0) if adapter["device"] == "cuda" else None, "versions": {"python": sys.version.split()[0], "torch": torch.__version__, "transformers": transformers.__version__}, "module_paths": {"torch": str(torch.__file__), "transformers": str(transformers.__file__)}})
    except Exception as exc:
        response.update({"error_type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()[-4000:]})
    response["elapsed_seconds"] = round(time.monotonic() - started, 3)
    response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if response["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
