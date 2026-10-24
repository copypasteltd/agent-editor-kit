"""Evaluate the native Transformers checkpoint on unchanged independent fixtures.

Development research only. No model integration or perceptual acceptance is
implied by a successful forward pass. Reference boundaries are not model inputs.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
import wave

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "product/.runtime/models/qwen3-aligner-0.6b-hf-20261025"
EVIDENCE = ROOT / "docs/validation/evidence/implementation-20261025-r1/native-aligner-research"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=False)
    report = {"status": "failed", "research_only": True, "product_engine_registered": False,
              "blocked_network_events": [], "model_forward_calls": 0, "cases": [],
              "generator_sha256": sha(Path(__file__))}
    started = time.monotonic()
    try:
        sys.path.insert(0, str(ROOT / "product/src"))
        from ai_ad_editor.whisper_worker import install_network_guard
        install_network_guard(report["blocked_network_events"])
        runtime = ROOT / "product/.runtime/qwen-native-alignment-20261025"
        for variable, subdirectory in {"TEMP": "temp", "TMP": "temp", "TMPDIR": "temp", "HF_HOME": "hf",
             "HF_HUB_CACHE": "hf/hub", "TORCH_HOME": "torch", "XDG_CACHE_HOME": "cache"}.items():
            path = runtime / subdirectory
            path.mkdir(parents=True, exist_ok=True)
            os.environ[variable] = str(path)
        os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                          DO_NOT_TRACK="1", TOKENIZERS_PARALLELISM="false", TQDM_DISABLE="1")
        acquisition = json.loads((EVIDENCE.parent / "aligner-acquisition/inventory.json").read_bytes())
        assert acquisition["status"] == "downloaded_verified"
        def verify():
            for record in acquisition["files"]:
                path = MODEL / record["file"]
                assert path.stat().st_size == record["expected_bytes"] and sha(path) == record["sha256"]
        verify()
        import numpy as np
        import torch
        import transformers
        from transformers import AutoProcessor, AutoModelForTokenClassification
        torch.set_num_threads(4)
        assert torch.cuda.is_available(), "This experiment requires actual GPU execution; no CPU fallback"
        torch.cuda.reset_peak_memory_stats()
        report["versions"] = {"python": sys.version.split()[0], "torch": torch.__version__,
                              "transformers": transformers.__version__, "numpy": np.__version__}
        processor = AutoProcessor.from_pretrained(str(MODEL), local_files_only=True, trust_remote_code=False)
        model = AutoModelForTokenClassification.from_pretrained(str(MODEL), local_files_only=True,
                    trust_remote_code=False, dtype=torch.bfloat16, attn_implementation="eager").to("cuda:0").eval()
        report["device"] = str(model.device)
        report["loaded_seconds"] = round(time.monotonic() - started, 3)
        for fixture in ("ctc-alignment-20261018", "boundary-heldout-20261018"):
            folder = ROOT / "docs/assets" / fixture
            path = (folder / "input.wav").resolve()
            transcript = (folder / "transcript.txt").read_text("utf-8").strip()
            with wave.open(str(path), "rb") as stream:
                assert stream.getframerate() == 16000 and stream.getnchannels() == 1 and stream.getsampwidth() == 2
                samples = stream.getnframes()
                audio = np.frombuffer(stream.readframes(samples), dtype="<i2").astype(np.float32) / 32768
            local_started = time.monotonic()
            inputs, word_lists = processor.prepare_forced_aligner_inputs(audio=audio, transcript=transcript,
                    language="English", return_tensors="pt")
            inputs = inputs.to(model.device, model.dtype)
            with torch.inference_mode():
                outputs = model(**inputs)
            torch.cuda.synchronize()
            report["model_forward_calls"] += 1
            timestamps = processor.decode_forced_alignment(logits=outputs.logits, input_ids=inputs["input_ids"],
                word_lists=word_lists, timestamp_token_id=model.config.timestamp_token_id)[0]
            # Also preserve the pre-monotonic-repair class predictions separately.
            positions = inputs["input_ids"][0] == model.config.timestamp_token_id
            raw_ms = (outputs.logits.argmax(dim=-1)[0][positions].float() * model.config.timestamp_segment_time).cpu().tolist()
            units = [{"text": row["text"], "raw_start_ms": raw_ms[2*i], "raw_end_ms": raw_ms[2*i+1],
                      "official_decoded_start_ms": row["start_time"] * 1000,
                      "official_decoded_end_ms": row["end_time"] * 1000} for i, row in enumerate(timestamps)]
            case = {"audio": {"path": str(path), "sha256": sha(path)}, "samples": samples,
                    "sample_rate": 16000, "original_text": transcript, "language": "English",
                    "posthoc_timestamp_fix_applied": False, "units": units,
                    "elapsed_seconds": round(time.monotonic() - local_started, 3)}
            report["cases"].append(case)
            print(json.dumps({"fixture": fixture, "units": units, "elapsed_seconds": case["elapsed_seconds"]}), flush=True)
        verify()
        report.update(status="inference_succeeded", peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                      peak_reserved_bytes=torch.cuda.max_memory_reserved(), human_listening=False)
    except BaseException as exc:
        report.update(error=repr(exc), traceback=traceback.format_exc())
        raise
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (EVIDENCE / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
