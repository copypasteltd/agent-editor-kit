from __future__ import annotations

import array
import contextlib
import hashlib
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from package_under_test import utf8_script_command

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_tts import SOULX_ENGINE, SOULX_PROTOCOL, synthesize_soulx, verify_adapter
from ai_ad_editor.media import probe_media
from ai_ad_editor.project import ledger_file
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, run_process, sha256_file


def invoke(*argv: str) -> tuple[int, dict]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(list(argv))
    return code, json.loads(output.getvalue())


def pcm(path: Path, seconds: float = 2, sample_rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = array.array("h", (round(10000 * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(round(seconds * sample_rate))))
    if sys.byteorder != "little":
        values.byteswap()
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(values.tobytes())


class LocalTtsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_local_runtime()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="agent-tts-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "中文项目"
        self.assertEqual(invoke("project", "init", str(self.root))[0], 0)
        self.source, self.packages, self.model = (self.base / name for name in ("source", "packages", "model"))
        self.model.mkdir()
        files = ["config.json", "soulxpodcast_config.json", "flow.pt", "hift.pt", "campplus.onnx", "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "special_tokens_map.json", "added_tokens.json", "generation_config.json", "one.safetensors"]
        for name in files:
            (self.model / name).write_bytes(b"local-test-artifact")
        (self.model / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {"tensor": "one.safetensors"}}), encoding="utf-8")
        for relative in ["soulxpodcast/utils/parser.py", "soulxpodcast/utils/infer_utils.py", "soulxpodcast/models/soulxpodcast.py", "LICENSE"]:
            file = self.source / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("# explicitly local test fixture\n", encoding="utf-8")
        package = self.packages / "s3tokenizer" / "__init__.py"
        package.parent.mkdir(parents=True)
        package.write_text("# local tokenizer fixture\n", encoding="utf-8")
        self.tokenizer = self.base / "speech_tokenizer_v2_25hz.onnx"
        self.tokenizer.write_bytes(b"registered-tokenizer-fixture")
        token_patch = patch("ai_ad_editor.local_tts.S3_TOKENIZER_SHA256", sha256_file(self.tokenizer))
        token_patch.start()
        self.addCleanup(token_patch.stop)
        self.evidence = self.base / "evidence.txt"
        self.evidence.write_text("Internal synthetic fixture only, no commercial or human identity claim", encoding="utf-8")
        self.reference = self.base / "reference.wav"
        pcm(self.reference)
        code, ingested = invoke("media", "ingest", "--project", str(self.root), "--input", str(self.reference))
        self.assertEqual(code, 0, ingested)
        self.reference_id = ingested["data"]["asset"]["id"]
        self.adapter_options = ["--project", str(self.root), "--adapter-id", "soulx", "--python-executable", sys.executable, "--source-root", str(self.source), "--package-root", str(self.packages), "--model-path", str(self.model), "--tokenizer-path", str(self.tokenizer), "--evidence", str(self.evidence)]
        self.prompt = "我們會把責任扛起來。\n原樣逐字稿。"

    def project(self) -> dict:
        return json.loads((self.root / "project.json").read_text(encoding="utf-8"))

    def register(self) -> None:
        code, result = invoke("tts", "adapter", "register", *self.adapter_options)
        self.assertEqual(code, 0, result)
        code, result = invoke("tts", "voice", "register", "--project", str(self.root), "--voice-id", "voice_s4", "--asset-id", self.reference_id, "--prompt-text", self.prompt, "--evidence", str(self.evidence))
        self.assertEqual(code, 0, result)

    def synth_options(self) -> list[str]:
        return ["tts", "synthesize", "--project", str(self.root), "--adapter-id", "soulx", "--voice-id", "voice_s4", "--text", "让创作变得更加简单。", "--asset-id", "generated_voice"]

    def fake_synthesis(self, root, text, output, **kwargs) -> dict:
        pcm(output, seconds=0.4, sample_rate=kwargs["sample_rate"])
        # The CLI still validates, hashes, registers and renders a real PCM file.
        return {"engine": SOULX_ENGINE, "output": str(output), "probe": probe_media(output), "text_sha256": "sha256:" + hashlib.sha256(text.encode()).hexdigest(), "sample_rate": kwargs["sample_rate"], "channels": 1, "natural_duration": True}

    def test_registration_dry_run_is_read_only_and_inspection_is_hash_based(self) -> None:
        baseline = (self.root / "project.json").read_bytes()
        code, planned = invoke("tts", "adapter", "register", *self.adapter_options, "--dry-run")
        self.assertEqual(code, 0, planned)
        self.assertEqual((self.root / "project.json").read_bytes(), baseline)
        self.assertNotIn("local_tts", self.project().get("extensions", {}))
        self.register()
        baseline = (self.root / "project.json").read_bytes()
        code, result = invoke("tts", "adapter", "inspect", "--project", str(self.root), "--adapter-id", "soulx")
        self.assertEqual(code, 0, result)
        self.assertTrue(result["data"]["verification"]["ok"])
        self.assertGreater(result["data"]["verification"]["checked_files"], 15)
        self.assertEqual((self.root / "project.json").read_bytes(), baseline)
        voice = self.project()["extensions"]["local_tts"]["voices"][0]
        self.assertEqual(voice["prompt_text"], self.prompt)

    def test_missing_shard_and_network_reference_fail_before_registration(self) -> None:
        (self.model / "one.safetensors").unlink()
        code, failed = invoke("tts", "adapter", "register", *self.adapter_options)
        self.assertEqual(code, 10, failed)
        self.assertEqual(failed["errors"][0]["code"], "TTS_MODEL_INCOMPLETE")
        code, failed = invoke("tts", "voice", "register", "--project", str(self.root), "--voice-id", "v", "--asset-id", self.reference_id, "--prompt-text", self.prompt, "--evidence", "https://example.invalid/proof")
        self.assertEqual(code, 2, failed)
        self.assertNotIn("local_tts", self.project().get("extensions", {}))

    def test_model_mutation_blocks_runner_even_for_dry_run(self) -> None:
        self.register()
        (self.model / "one.safetensors").write_bytes(b"altered-model")
        with patch("ai_ad_editor.cli.synthesize_soulx") as runner:
            code, failed = invoke(*self.synth_options(), "--dry-run")
        self.assertEqual(code, 10, failed)
        self.assertEqual(failed["errors"][0]["code"], "TTS_INPUT_INTEGRITY_FAILED")
        runner.assert_not_called()
        self.assertNotIn("generated_voice", [item["id"] for item in self.project()["assets"]])

    def test_runtime_path_mutation_cannot_reuse_original_manifest(self) -> None:
        self.register()
        adapter = self.project()["extensions"]["local_tts"]["adapters"][0]
        adapter["source_root"] = str(self.base)
        result = verify_adapter(adapter)
        self.assertFalse(result["ok"])
        self.assertIn("TTS_ADAPTER_PATH_MISMATCH", [item["code"] for item in result["findings"]])

    def test_transcript_and_evidence_changes_block_inference(self) -> None:
        self.register()
        project = self.project()
        project["extensions"]["local_tts"]["voices"][0]["prompt_text"] = "被改写的逐字稿"
        atomic_write_json(self.root / "project.json", project)
        with patch("ai_ad_editor.cli.synthesize_soulx") as runner:
            code, failed = invoke(*self.synth_options())
        self.assertEqual(code, 10, failed)
        runner.assert_not_called()
        self.assertIn("TTS_TRANSCRIPT_HASH_MISMATCH", str(failed))

    def test_synthesis_registers_rights_natural_duration_track_and_render(self) -> None:
        self.register()
        audio_track = next(item for item in self.project()["sequences"][0]["tracks"] if item["kind"] == "audio")
        with patch("ai_ad_editor.cli.synthesize_soulx", side_effect=self.fake_synthesis):
            code, result = invoke(*self.synth_options(), "--apply", "--track-id", audio_track["id"], "--channels", "1", "--timeline-start-seconds", "0.2")
        self.assertEqual(code, 0, result)
        project = self.project()
        self.assertNotIn("RIGHTS_RECORD_MISSING", str(result["data"]["validation"]["rights"].get("failures", [])))
        asset = next(item for item in project["assets"] if item["id"] == "generated_voice")
        self.assertEqual(asset["sha256"], "sha256:" + sha256_file(self.root / asset["uri"]))
        self.assertEqual(asset["source"]["generation"]["text"], "让创作变得更加简单。")
        tps = project["settings"]["timebase"]["ticks_per_second"]
        clip = result["data"]["generated_clip"]
        self.assertEqual(clip["timeline_start_tick"], round(0.2 * tps))
        self.assertEqual(clip["duration_tick"], round(0.4 * tps))
        self.assertEqual(set(result["data"]["rights"]["derived_from"]), {"tts_adapter_soulx", "tts_voice_voice_s4"})
        code, gate = invoke("rights", "check", "--project", str(self.root))
        self.assertEqual(code, 7, gate)
        self.assertIn("unverified", json.dumps(gate))
        plate = self.base / "plate.mp4"
        encoded = run_process(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=24:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(plate)])
        self.assertEqual(encoded.returncode, 0, encoded.stderr)
        code, visual = invoke("media", "ingest", "--project", str(self.root), "--input", str(plate))
        self.assertEqual(code, 0, visual)
        video_track = next(item for item in project["sequences"][0]["tracks"] if item["kind"] == "video")
        plan = self.root / "cache" / "plate.json"
        atomic_write_json(plan, {"operations": [{"op": "append_clip", "track_id": video_track["id"], "asset_id": visual["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": round(0.6 * tps)}]})
        code, composed = invoke("timeline", "compose", "--project", str(self.root), "--input", str(plan))
        self.assertEqual(code, 0, composed)
        output = self.root / "renders" / "voice.mp4"
        code, rendered = invoke("render", "--project", str(self.root), "--output", str(output), "--profile", "custom", "--width", "160", "--height", "90")
        self.assertEqual(code, 0, rendered)
        self.assertTrue(probe_media(output)["audio"]["codec"])
        code, policy = invoke("policy", "audit", "--project", str(self.root))
        self.assertEqual(code, 0, policy)

    def test_existing_output_and_invalid_track_never_execute_or_destroy_files(self) -> None:
        self.register()
        output = self.root / "assets" / "existing.wav"
        output.write_bytes(b"preserve-existing-user-file")
        with patch("ai_ad_editor.cli.synthesize_soulx") as runner:
            code, failed = invoke(*self.synth_options(), "--output", str(output))
        self.assertEqual(code, 2, failed)
        runner.assert_not_called()
        self.assertEqual(output.read_bytes(), b"preserve-existing-user-file")
        video = next(item for item in self.project()["sequences"][0]["tracks"] if item["kind"] == "video")
        with patch("ai_ad_editor.cli.synthesize_soulx") as runner:
            code, failed = invoke(*self.synth_options(), "--apply", "--track-id", video["id"])
        self.assertEqual(code, 2, failed)
        runner.assert_not_called()

    def test_failed_metadata_commit_rolls_back_and_removes_new_audio(self) -> None:
        self.register()
        baseline = (self.root / "project.json").read_bytes()
        ledger_baseline = ledger_file(self.root).read_bytes()
        with patch("ai_ad_editor.cli.synthesize_soulx", side_effect=self.fake_synthesis), patch("ai_ad_editor.cli.save_project", side_effect=AppError("TEST_COMMIT_FAILED", "injected failure", exit_code=6)):
            code, failed = invoke(*self.synth_options())
        self.assertEqual(code, 6, failed)
        self.assertEqual((self.root / "project.json").read_bytes(), baseline)
        self.assertEqual(ledger_file(self.root).read_bytes(), ledger_baseline)
        self.assertFalse((self.root / "assets" / "tts" / "generated_voice.wav").exists())
        self.assertFalse((self.root / "operations" / "project-transaction.json").exists())

    def test_voice_and_model_registries_restore_with_project_snapshot(self) -> None:
        code, registered = invoke("tts", "adapter", "register", *self.adapter_options)
        self.assertEqual(code, 0, registered)
        snapshot = registered["data"]["snapshot"]["snapshot_id"]
        self.assertTrue(self.project()["extensions"]["local_tts"]["adapters"])
        code, restored = invoke("project", "restore", "--project", str(self.root), "--snapshot", snapshot)
        self.assertEqual(code, 0, restored)
        self.assertNotIn("local_tts", self.project().get("extensions", {}))

    def test_synthesis_idempotency_does_not_repeat_generation(self) -> None:
        self.register()
        with patch("ai_ad_editor.cli.synthesize_soulx", side_effect=self.fake_synthesis) as runner:
            code, first = invoke(*self.synth_options(), "--channels", "1", "--idempotency-key", "one-generation")
            self.assertEqual(code, 0, first)
            code, repeated = invoke(*self.synth_options(), "--channels", "1", "--idempotency-key", "one-generation")
        self.assertEqual(code, 0, repeated)
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(first["operation_id"], repeated["operation_id"])
        self.assertIn("IDEMPOTENT_REPLAY", str(repeated["warnings"]))
        self.assertEqual(sum(item["id"] == "generated_voice" for item in self.project()["assets"]), 1)

    def test_changed_voice_evidence_blocks_generation(self) -> None:
        self.register()
        self.evidence.write_text("changed evidence", encoding="utf-8")
        with patch("ai_ad_editor.cli.synthesize_soulx") as runner:
            code, failed = invoke(*self.synth_options())
        self.assertEqual(code, 10, failed)
        runner.assert_not_called()
        self.assertIn("TTS_VOICE_EVIDENCE_CHANGED", str(failed))

    def test_worker_raw_hash_mismatch_never_publishes_output(self) -> None:
        output = self.root / "assets" / "bad-hash.wav"
        adapter = {"python_executable": sys.executable, "adapter_id": "fixture", "sha256": "sha256:" + "0" * 64}
        voice = {"prompt_text": "fixture", "audio_sha256": "sha256:" + sha256_file(self.reference), "voice_id": "fixture"}

        def runner(argv, **kwargs):
            request = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
            pcm(Path(request["raw_output"]), seconds=0.2)
            atomic_write_json(Path(request["response"]), {"protocol": SOULX_PROTOCOL, "status": "succeeded", "raw_output": request["raw_output"], "raw_sha256": "sha256:" + "0" * 64, "blocked_network_events": [], "network": "disabled"})
            return subprocess.CompletedProcess(argv, 0, "", "")

        with patch("ai_ad_editor.local_tts.run_process", side_effect=runner), self.assertRaises(AppError) as raised:
            synthesize_soulx(self.root, "中文", output, adapter=adapter, voice=voice, audio=self.reference, operation_id="op_hash", sample_rate=48000, channels=1, seed=1)
        self.assertEqual(raised.exception.code, "TTS_OUTPUT_INVALID")
        self.assertFalse(output.exists())

    def test_worker_wrong_protocol_never_publishes_output(self) -> None:
        output = self.root / "assets" / "bad-worker.wav"
        adapter = {"python_executable": sys.executable, "adapter_id": "fixture", "sha256": "sha256:" + "0" * 64}
        voice = {"prompt_text": "fixture", "audio_sha256": "sha256:" + sha256_file(self.reference), "voice_id": "fixture"}

        def runner(argv, **kwargs):
            request = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
            pcm(Path(request["raw_output"]), seconds=0.2)
            atomic_write_json(Path(request["response"]), {"protocol": "wrong", "status": "succeeded", "raw_output": request["raw_output"]})
            return subprocess.CompletedProcess(argv, 0, "", "")

        with patch("ai_ad_editor.local_tts.run_process", side_effect=runner), self.assertRaises(AppError) as raised:
            synthesize_soulx(self.root, "中文", output, adapter=adapter, voice=voice, audio=self.reference, operation_id="op_bad", sample_rate=48000, channels=1, seed=1)
        self.assertEqual(raised.exception.code, "TTS_WORKER_FAILED")
        self.assertFalse(output.exists())

    def test_worker_normalization_produces_real_pcm_and_preserves_natural_duration(self) -> None:
        output = self.root / "assets" / "normalized.wav"
        adapter = {"python_executable": sys.executable, "adapter_id": "fixture", "sha256": "sha256:" + "0" * 64}
        voice = {"prompt_text": "fixture", "audio_sha256": "sha256:" + sha256_file(self.reference), "voice_id": "fixture"}

        def runner(argv, **kwargs):
            if argv[0] == sys.executable:
                request = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
                pcm(Path(request["raw_output"]), seconds=0.5)
                atomic_write_json(Path(request["response"]), {"protocol": SOULX_PROTOCOL, "status": "succeeded", "raw_output": request["raw_output"], "raw_sha256": "sha256:" + sha256_file(Path(request["raw_output"])), "blocked_network_events": [], "network": "disabled"})
                return subprocess.CompletedProcess(argv, 0, "", "")
            return run_process(argv, **kwargs)

        with patch("ai_ad_editor.local_tts.run_process", side_effect=runner):
            result = synthesize_soulx(self.root, "中文", output, adapter=adapter, voice=voice, audio=self.reference, operation_id="op_good", sample_rate=48000, channels=2, seed=1)
        self.assertEqual(result["probe"]["audio"]["channels"], 2)
        self.assertEqual(result["probe"]["audio"]["sample_rate"], 48000)
        self.assertAlmostEqual(result["probe"]["duration_seconds"], 0.5, places=3)
        self.assertFalse(list(output.parent.glob(".*.wav")))

    def test_python_network_guard_blocks_connection_before_network_io(self) -> None:
        script = "from ai_ad_editor.soulx_worker import install_network_guard; import socket; events=[]; install_network_guard(events)\ntry:\n socket.create_connection(('127.0.0.1',9),timeout=0.1)\nexcept RuntimeError as e:\n print(str(e)); print(events)\nelse:\n raise SystemExit(3)"
        result = subprocess.run(utf8_script_command(script), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TTS_NETWORK_DISABLED", result.stdout)
        self.assertIn("socket.getaddrinfo", result.stdout)


if __name__ == "__main__":
    unittest.main()
