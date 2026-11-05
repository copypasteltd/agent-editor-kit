from __future__ import annotations

import array
import contextlib
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

from ai_ad_editor.asr_quality import character_error_rate
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_asr import ASR_PROTOCOL, checked_transcription, registry_item, transcribe_registered
from ai_ad_editor.project import ledger_file
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.transcribe import _extract_segments
from ai_ad_editor.transcribe import transcribe_local_ffmpeg_whisper
from ai_ad_editor.utils import atomic_write_json, run_process


def invoke(*argv: str) -> tuple[int, dict]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(list(argv))
    return code, json.loads(output.getvalue())


class LocalAsrTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_local_runtime()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="agent-asr-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "中文项目"
        self.assertEqual(invoke("project", "init", str(self.root))[0], 0)
        self.model = self.base / "whisper"
        self.model.mkdir()
        for name in ("config.json", "preprocessor_config.json", "tokenizer_config.json", "generation_config.json", "tokenizer.json", "vocab.json"):
            atomic_write_json(self.model / name, {"model_type": "whisper"} if name == "config.json" else {})
        (self.model / "merges.txt").write_text("# offline fixture", encoding="utf-8")
        (self.model / "model.safetensors").write_bytes(b"small fixture, not a model quality test")
        self.evidence = self.base / "evidence.json"
        atomic_write_json(self.evidence, {"use": "internal-synthetic-fixture"})
        self.source = self.base / "source.wav"
        values = array.array("h", (round(10000 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(32000)))
        if sys.byteorder != "little":
            values.byteswap()
        with wave.open(str(self.source), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(16000)
            f.writeframes(values.tobytes())
        code, result = invoke("media", "ingest", "--project", str(self.root), "--input", str(self.source))
        self.assertEqual(code, 0, result)
        self.asset_id = result["data"]["asset"]["id"]
        plan = self.root / "cache" / "track.json"
        atomic_write_json(plan, {"operations": [{"op": "add_track", "track_id": "captions", "kind": "subtitle", "order": 3}]})
        self.assertEqual(invoke("timeline", "compose", "--project", str(self.root), "--input", str(plan))[0], 0)
        self.options = ["--project", str(self.root), "--adapter-id", "whisper", "--python-executable", sys.executable, "--model-path", str(self.model), "--evidence", str(self.evidence)]
        self.worker_calls = 0
        self.payload_change = None

    def project(self) -> dict:
        return json.loads((self.root / "project.json").read_text(encoding="utf-8"))

    def metadata(self) -> tuple[bytes, bytes, bytes]:
        return tuple(p.read_bytes() for p in (self.root / "project.json", self.root / "project.lock.json", ledger_file(self.root)))

    def register(self) -> dict:
        code, value = invoke("asr", "adapter", "register", *self.options)
        self.assertEqual(code, 0, value)
        return value

    def transcribe_options(self) -> list[str]:
        return ["subtitle", "transcribe", "--project", str(self.root), "--asset-id", self.asset_id, "--adapter-id", "whisper", "--output", "assets/subtitles/new.srt", "--language", "zh", "--apply", "--track-id", "captions"]

    def fake_runner(self, argv, **kwargs):
        if any(str(item).endswith("whisper_worker.py") for item in argv):
            self.worker_calls += 1
            self.assertIn("-I", argv)
            request = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
            self.assertEqual(request["network"], "disabled")
            value = {"protocol": ASR_PROTOCOL, "status": "succeeded", "network": "disabled", "blocked_network_events": [], "input_sha256": request["input_sha256"], "source_sha256": request["source_sha256"], "adapter_sha256": request["adapter"]["sha256"], "transcription": {"status": "ok", "network": "disabled", "segments": [{"start": 0.0, "end": 0.5, "text": "First caption"}, {"start": 0.6, "end": 1.8, "text": "Second caption"}]}}
            if self.payload_change:
                self.payload_change(value)
            atomic_write_json(Path(request["response"]), value)
            return subprocess.CompletedProcess(argv, 0, "", "")
        return run_process(argv, **kwargs)

    def test_registration_and_inspection_are_read_only_and_dry_run_is_not_registration(self) -> None:
        baseline = self.metadata()
        code, value = invoke("asr", "adapter", "register", *self.options, "--dry-run")
        self.assertEqual(code, 0, value)
        self.assertEqual(self.metadata(), baseline)
        self.assertNotIn("local_asr", self.project().get("extensions", {}))
        self.register()
        baseline = self.metadata()
        for action in ("list", "inspect"):
            args = [] if action == "list" else ["--adapter-id", "whisper"]
            code, value = invoke("asr", "adapter", action, "--project", str(self.root), *args)
            self.assertEqual(code, 0, value)
            self.assertTrue(value["data"]["adapters"][0]["verification"]["ok"])
            self.assertEqual(self.metadata(), baseline)

    def test_missing_shard_and_custom_code_are_rejected(self) -> None:
        atomic_write_json(self.model / "model.safetensors.index.json", {"weight_map": {"encoder": "missing.safetensors"}})
        code, _ = invoke("asr", "adapter", "register", *self.options)
        self.assertEqual(code, 10)
        atomic_write_json(self.model / "model.safetensors.index.json", {"weight_map": {"encoder": "../model.safetensors"}})
        self.assertEqual(invoke("asr", "adapter", "register", *self.options)[0], 10)
        (self.model / "model.safetensors.index.json").unlink()
        atomic_write_json(self.model / "config.json", {"model_type": "whisper", "auto_map": {"AutoModel": "custom.Module"}})
        self.assertEqual(invoke("asr", "adapter", "register", *self.options)[0], 10)

    def test_remote_model_and_native_wrapper_are_rejected(self) -> None:
        args = list(self.options)
        args[args.index("--model-path") + 1] = "https://invalid.example/model"
        self.assertEqual(invoke("asr", "adapter", "register", *args)[0], 2)
        wrapper = self.base / "python.cmd"
        wrapper.write_text("exit /b 0", encoding="utf-8")
        args = list(self.options)
        args[args.index("--python-executable") + 1] = str(wrapper)
        self.assertEqual(invoke("asr", "adapter", "register", *args)[0], 2)

    def test_model_tamper_stops_before_worker(self) -> None:
        self.register()
        (self.model / "tokenizer.json").write_text('{"changed":true}', encoding="utf-8")
        with patch("ai_ad_editor.local_asr.run_process") as runner:
            code, value = invoke(*self.transcribe_options())
        self.assertEqual(code, 10, value)
        runner.assert_not_called()
        self.assertFalse((self.root / "assets/subtitles/new.srt").exists())

    def test_relative_output_applies_timing_and_model_rights_and_renders(self) -> None:
        self.register()
        with patch("ai_ad_editor.local_asr.run_process", side_effect=self.fake_runner):
            code, value = invoke(*self.transcribe_options(), "--timeline-start-seconds", "0.25")
        self.assertEqual(code, 0, value)
        output = self.root / "assets/subtitles/new.srt"
        self.assertEqual(Path(value["data"]["output"]), output)
        self.assertTrue(output.is_file())
        clips = value["data"]["generated_clips"]
        tps = self.project()["settings"]["timebase"]["ticks_per_second"]
        self.assertEqual(clips[0]["timeline_start_tick"], round(0.25 * tps))
        self.assertEqual(clips[1]["duration_tick"], round(1.2 * tps))
        self.assertIn("asr_adapter_whisper", value["data"]["rights"]["derived_from"])
        self.assertTrue(value["data"]["validation"]["ok"])
        self.assertNotIn("RIGHTS_RECORD_MISSING", json.dumps(value["data"]["validation"]))
        rendered = self.root / "renders/captions.mp4"
        code, result = invoke("render", "--project", str(self.root), "--output", str(rendered), "--profile", "custom", "--width", "320", "--height", "180")
        self.assertEqual(code, 0, result)
        self.assertGreater(rendered.stat().st_size, 100)
        self.assertEqual(invoke("rights", "check", "--project", str(self.root))[0], 7)
        code, policy = invoke("policy", "audit", "--project", str(self.root))
        self.assertEqual(code, 0, policy)

    def test_idempotent_transcription_does_not_run_worker_twice(self) -> None:
        self.register()
        options = self.transcribe_options()
        options[options.index("--output") + 1] = str(self.root / "assets/subtitles/new.srt")
        with patch("ai_ad_editor.local_asr.run_process", side_effect=self.fake_runner):
            first = invoke(*options, "--idempotency-key", "one-transcription")
            second = invoke(*options, "--idempotency-key", "one-transcription")
        self.assertEqual(first[0], 0, first[1])
        self.assertEqual(second[0], 0, second[1])
        self.assertEqual(first[1]["operation_id"], second[1]["operation_id"])
        self.assertEqual(self.worker_calls, 1)

    def test_snapshot_restore_removes_registration_and_its_rights_together(self) -> None:
        result = self.register()
        snapshot_id = result["data"]["snapshot"]["snapshot_id"]
        code, restored = invoke("project", "restore", "--project", str(self.root), "--snapshot", snapshot_id)
        self.assertEqual(code, 0, restored)
        self.assertNotIn("local_asr", self.project().get("extensions", {}))
        ledger = json.loads(ledger_file(self.root).read_text(encoding="utf-8"))
        self.assertNotIn("asr_adapter_whisper", [item["asset_id"] for item in ledger["records"]])

    def test_registered_source_hash_change_is_rejected_before_worker(self) -> None:
        self.register()
        asset = next(item for item in self.project()["assets"] if item["id"] == self.asset_id)
        source = self.root / asset["uri"]
        source.write_bytes(source.read_bytes() + b"changed")
        with patch("ai_ad_editor.local_asr.run_process") as runner:
            code, value = invoke(*self.transcribe_options())
        self.assertEqual(code, 10, value)
        self.assertEqual(value["errors"][0]["code"], "ASR_SOURCE_HASH_MISMATCH")
        runner.assert_not_called()

    def test_font_ingest_validates_native_font_and_rejects_invalid_font_bytes(self) -> None:
        font = Path(__file__).resolve().parents[2] / "sources/upstream/concat/src/crates/concat-text/fonts/SpaceGrotesk-Regular.ttf"
        self.assertTrue(font.is_file())
        code, value = invoke("media", "ingest", "--project", str(self.root), "--input", str(font))
        self.assertEqual(code, 0, value)
        self.assertEqual(value["data"]["asset"]["kind"], "font")
        self.assertEqual(value["data"]["asset"]["probe"]["font"]["family"], "Space Grotesk")
        invalid = self.base / "invalid.ttf"
        invalid.write_bytes(b"not a font")
        code, value = invoke("media", "ingest", "--project", str(self.root), "--input", str(invalid))
        self.assertEqual(code, 3, value)
        self.assertEqual(value["errors"][0]["code"], "FONT_PROBE_FAILED")

    def test_existing_srt_and_invalid_offsets_never_run_worker(self) -> None:
        self.register()
        output = self.root / "assets/subtitles/new.srt"
        output.parent.mkdir(parents=True)
        output.write_text("preserve existing output", encoding="utf-8")
        with patch("ai_ad_editor.local_asr.run_process") as runner:
            self.assertEqual(invoke(*self.transcribe_options())[0], 2)
            for offset in ("nan", "inf", "-1"):
                self.assertEqual(invoke(*self.transcribe_options(), "--timeline-start-seconds", offset)[0], 2)
        self.assertEqual(output.read_text(encoding="utf-8"), "preserve existing output")
        runner.assert_not_called()

    def test_ffmpeg_whisper_preserves_an_existing_destination(self) -> None:
        output = self.base / "existing.srt"
        output.write_text("keep", encoding="utf-8")
        with patch("ai_ad_editor.transcribe.ffmpeg_whisper_available", return_value=True), patch("ai_ad_editor.transcribe.run_process") as runner:
            with self.assertRaises(AppError):
                transcribe_local_ffmpeg_whisper(self.source, model_path=self.model / "model.safetensors", output_srt=output)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep")
        runner.assert_not_called()

    def test_validation_failure_rolls_back_project_ledger_and_new_srt(self) -> None:
        self.register()
        baseline = self.metadata()
        with patch("ai_ad_editor.local_asr.run_process", side_effect=self.fake_runner), patch("ai_ad_editor.cli.validate_project", return_value={"ok": False, "errors": [{"code": "injected"}]}):
            code, value = invoke(*self.transcribe_options())
        self.assertEqual(code, 2, value)
        self.assertEqual(self.metadata(), baseline)
        self.assertFalse((self.root / "assets/subtitles/new.srt").exists())

    def test_project_save_failure_rolls_back_candidate_rights_and_srt(self) -> None:
        self.register()
        baseline = self.metadata()
        with patch("ai_ad_editor.local_asr.run_process", side_effect=self.fake_runner), patch("ai_ad_editor.cli.save_project", side_effect=OSError("injected write failure")):
            code, value = invoke(*self.transcribe_options())
        self.assertEqual(code, 9, value)
        self.assertEqual(self.metadata(), baseline)
        self.assertFalse((self.root / "assets/subtitles/new.srt").exists())

    def test_wrong_protocol_or_input_hash_never_publishes_srt(self) -> None:
        self.register()
        for key, changed in (("protocol", "unknown"), ("input_sha256", "sha256:" + "0" * 64), ("blocked_network_events", ["socket.connect"])):
            with self.subTest(key=key):
                self.payload_change = lambda payload, key=key, changed=changed: payload.update({key: changed})
                with patch("ai_ad_editor.local_asr.run_process", side_effect=self.fake_runner):
                    code, result = invoke(*self.transcribe_options())
                self.assertEqual(code, 6, result)
                self.assertFalse((self.root / "assets/subtitles/new.srt").exists())

    def test_registered_media_understand_returns_actual_segment_text(self) -> None:
        self.register()
        with patch("ai_ad_editor.local_asr.run_process", side_effect=self.fake_runner):
            code, result = invoke("media", "understand", "--project", str(self.root), "--asset-id", self.asset_id, "--transcribe", "--adapter-id", "whisper")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["data"]["result"]["transcription"]["text"], "First caption Second caption")
        self.assertNotIn("srt", result["data"]["result"]["transcription"])


class AsrTextAndProtocolTests(unittest.TestCase):
    def test_tensor_tokens_are_converted_to_lists_before_tokenizer_decode(self) -> None:
        class Tokens:
            def detach(self): return self
            def cpu(self): return self
            def tolist(self): return [1, 2, 3]
        class Processor:
            def batch_decode(self, values, **kwargs):
                if not isinstance(values[0], list):
                    raise TypeError("Tokenizer requires integer lists")
                return ["真实中文"]
        value = _extract_segments(Processor(), {"segments": [[{"start": 0, "end": 1, "tokens": Tokens()}]]})
        self.assertEqual(value, [{"start": 0.0, "end": 1.0, "text": "真实中文"}])

    def test_empty_nonfinite_overlapping_and_out_of_range_segments_are_rejected(self) -> None:
        for segments in ([{"start": 0, "end": 1, "text": ""}], [{"start": 0, "end": float("nan"), "text": "a"}], [{"start": 0, "end": 2.1, "text": "a"}], [{"start": 0, "end": 1, "text": "a"}, {"start": .5, "end": 2, "text": "b"}]):
            with self.subTest(segments=segments), self.assertRaises(AppError):
                checked_transcription({"status": "ok", "network": "disabled", "segments": segments}, 2)

    def test_only_quantized_timestamp_tail_is_clamped(self) -> None:
        value = checked_transcription({"status": "ok", "network": "disabled", "segments": [{"start": 0, "end": 2.02, "text": "tail"}]}, 2)
        self.assertEqual(value["segments"][0]["end"], 2)
        self.assertIn("ASR_TIMESTAMP_END_CLAMPED", value["warnings"])

    def test_cer_counts_substitutions_deletions_and_insertions(self) -> None:
        for hypothesis, field in (("adc", "substitutions"), ("ab", "deletions"), ("abxc", "insertions")):
            with self.subTest(hypothesis=hypothesis):
                value = character_error_rate("abc", hypothesis)
                self.assertEqual(value[field], 1)
                self.assertEqual(value["edit_distance"], 1)
                self.assertAlmostEqual(value["cer"], 1 / 3)

    def test_cer_normalization_is_explicit_and_never_converts_chinese_script(self) -> None:
        self.assertEqual(character_error_rate("Ａ，B １", "ab1")["cer"], 0)
        self.assertEqual(character_error_rate("A", "a", normalization="raw")["cer"], 1)
        self.assertAlmostEqual(character_error_rate("让创作", "讓創作")["cer"], 2 / 3)
        with self.assertRaises(AppError):
            character_error_rate("！", "a")

    def test_threshold_failure_retains_report_without_mutating_project(self) -> None:
        configure_local_runtime()
        with tempfile.TemporaryDirectory(prefix="agent-cer-") as directory:
            root = Path(directory) / "project"
            self.assertEqual(invoke("project", "init", str(root))[0], 0)
            (root / "cache/ref.txt").write_text("abc", encoding="utf-8")
            (root / "cache/hyp.txt").write_text("adc", encoding="utf-8")
            before = (root / "project.json").read_bytes()
            args = ["subtitle", "evaluate", "--project", str(root), "--input", "cache/hyp.txt", "--reference", "cache/ref.txt", "--max-cer", "0", "--report", "validation/cer.json"]
            code, result = invoke(*args)
            self.assertEqual(code, 6, result)
            report = root / "validation/cer.json"
            self.assertAlmostEqual(json.loads(report.read_text(encoding="utf-8"))["cer"], 1 / 3)
            self.assertEqual((root / "project.json").read_bytes(), before)
            baseline = report.read_bytes()
            self.assertEqual(invoke(*args)[0], 2)
            self.assertEqual(report.read_bytes(), baseline)

    def test_native_python_guard_blocks_network_without_a_connection(self) -> None:
        worker = Path(__file__).resolve().parents[1] / "src/ai_ad_editor/whisper_worker.py"
        script = "import runpy,socket; m=runpy.run_path(" + repr(str(worker)) + "); events=[]; m['install_network_guard'](events);\ntry: socket.getaddrinfo('invalid.example',443)\nexcept RuntimeError: pass\nelse: raise AssertionError('network guard failed')\nassert events == ['socket.getaddrinfo']"
        result = run_process([sys.executable, "-I", "-B", "-X", "utf8", "-c", script], timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
