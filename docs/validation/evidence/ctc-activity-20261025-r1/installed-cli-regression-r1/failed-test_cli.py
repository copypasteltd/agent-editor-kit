from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from PIL import Image

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import probe_media
from ai_ad_editor.render import _effect_filters, _expr_arg, _flatten_sequence_tracks, _keyframe_expr, _reverse_speed_curve_segments, _transform_exprs
from ai_ad_editor.utils import run_process
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.migration import migrate_project_payload
from ai_ad_editor.project import prepare_project_transaction, recover_pending_transaction
from ai_ad_editor.template import instantiate


ROOT = Path(__file__).resolve().parents[2]


def invoke(*argv: str) -> tuple[int, dict]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main(list(argv))
    return code, json.loads(stream.getvalue())


class P0CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_local_runtime()

    def make_media(self, directory: Path, name: str = "fixture.mp4") -> Path:
        target = directory / name
        completed = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=green:s=320x180:r=24:d=1",
                "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:d=1",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(target),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return target

    def make_image(self, directory: Path, name: str = "fixture.png") -> Path:
        target = directory / name
        completed = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180", "-frames:v", "1", str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return target

    def make_pulse_audio(self, directory: Path, name: str = "pulse.wav") -> Path:
        target = directory / name
        completed = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "aevalsrc=if(lt(mod(t\\,0.5)\\,0.12)\\,0.8*sin(2*PI*880*t)\\,0):s=48000:d=2", "-c:a", "pcm_s16le", str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return target

    def test_local_p0_pipeline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            code, result = invoke("project", "init", str(project), "--name", "P0")
            self.assertEqual(code, 0)
            code, result = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://fixture", "--license-spdx", "CC0-1.0",
                "--license-url", "local://license", "--evidence", "local://evidence",
            )
            self.assertEqual(code, 0, result)
            asset_id = result["data"]["asset"]["id"]
            ingest_operation = result["operation_id"]
            code, operation_result = invoke("operation", "inspect", "--project", str(project), "--operation-id", ingest_operation)
            self.assertEqual(code, 0, operation_result)
            self.assertEqual(operation_result["data"]["operation"]["status"], "succeeded")
            code, understanding = invoke("media", "understand", "--project", str(project), "--asset-id", asset_id)
            self.assertEqual(code, 0, understanding)
            self.assertEqual(understanding["data"]["result"]["engine"], "ffmpeg-local")
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"sequence_id": "seq_main", "operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_audio_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            code, result = invoke("validate", "--project", str(project), "--strict-rights")
            self.assertEqual(code, 0, result)
            output = project / "renders" / "p0.mp4"
            code, result = invoke("render", "--project", str(project), "--publish", "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            probe = probe_media(output)
            self.assertEqual(probe["video"]["width"], 1080)
            self.assertEqual(probe["video"]["height"], 1920)
            self.assertGreater(probe["duration_seconds"], 0.8)
            self.assertTrue((output.with_suffix(".mp4.manifest.json")).exists())
            code, quality = invoke("quality", "check", "--project", str(project), "--input", str(output), "--require-audio")
            self.assertEqual(code, 0, quality)
            self.assertTrue(quality["data"]["ok"])
            code, expensive_quality = invoke("quality", "check", "--project", str(project), "--input", str(output), "--require-audio", "--expensive", "--max-av-sync-ms", "80", "--target-lufs", "-14", "--lufs-tolerance", "20", "--max-true-peak-dbfs", "-1")
            self.assertEqual(code, 0, expensive_quality)
            self.assertIn("black_intervals", expensive_quality["data"]["metrics"])
            self.assertIn("av_duration_delta_seconds", expensive_quality["data"]["metrics"])
            self.assertIn("integrated_lufs", expensive_quality["data"]["metrics"])
            self.assertIn("true_peak_dbfs", expensive_quality["data"]["metrics"])
            exported = workspace / "with-assets.json"
            code, result = invoke("convert", "export", "--project", str(project), "--output", str(exported))
            self.assertEqual(code, 0, result)
            imported = workspace / "with-assets-imported"
            code, result = invoke("convert", "import", "--input", str(exported), "--output", str(imported))
            self.assertEqual(code, 0, result)
            imported_project = json.loads((imported / "project.json").read_text(encoding="utf-8"))
            self.assertTrue((imported / imported_project["assets"][0]["uri"]).exists())
            otio = workspace / "timeline.otio"
            code, otio_result = invoke("convert", "export", "--project", str(project), "--output", str(otio), "--target-format", "otio")
            self.assertEqual(code, 0, otio_result)
            self.assertEqual(json.loads(otio.read_text(encoding="utf-8"))["OTIO_SCHEMA"], "Timeline.1")
            otio_imported = workspace / "otio-imported"
            code, otio_import_result = invoke("convert", "import", "--input", str(otio), "--output", str(otio_imported))
            self.assertEqual(code, 0, otio_import_result)
            self.assertTrue((otio_imported / "project.json").exists())

    def test_local_policy_rejects_remote_ingest_metadata_and_audits_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-policy-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, rejected = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--source-url", "https://closed.example/media.mp4",
            )
            self.assertEqual(code, 2, rejected)
            self.assertEqual(rejected["errors"][0]["code"], "ARGUMENT_INVALID")
            self.assertEqual(json.loads((project / "project.json").read_text(encoding="utf-8"))["assets"], [])

            remote_operation = project / "operations" / "remote.json"
            remote_operation.write_text(json.dumps({"provider": "https://api.example.invalid/render"}), encoding="utf-8")
            code, audit = invoke("policy", "audit", "--project", str(project))
            self.assertEqual(code, 2, audit)
            self.assertEqual(audit["status"], "failed")
            self.assertEqual(audit["errors"][0]["code"], "POLICY_REMOTE_REFERENCE")
            self.assertFalse(audit["data"]["ok"])

    def test_local_project_package_roundtrip_and_tamper_gate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-package-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace, "素材 包.mp4")
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project), "--name", "包测试")[0], 0)
            code, ingested = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://package-fixture", "--license-spdx", "CC0-1.0",
                "--license-url", "local://license", "--evidence", "local://evidence",
            )
            self.assertEqual(code, 0, ingested)
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingested["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            package = workspace / "project.aevpkg.zip"
            code, exported = invoke("convert", "export", "--project", str(project), "--output", str(package), "--target-format", "package")
            self.assertEqual(code, 0, exported)
            self.assertTrue(package.is_file())
            with zipfile.ZipFile(package) as archive:
                names = set(archive.namelist())
                self.assertIn("package-manifest.json", names)
                self.assertIn("project.json", names)
                self.assertIn("rights-ledger.json", names)
                self.assertTrue(any(name.startswith("assets/") for name in names))
                packaged = json.loads(archive.read("project.json"))
                self.assertFalse(Path(packaged["assets"][0]["uri"]).is_absolute())
                self.assertNotIn("renders/", "".join(names))
            imported = workspace / "imported"
            code, result = invoke("convert", "import", "--input", str(package), "--output", str(imported))
            self.assertEqual(code, 0, result)
            imported_project = json.loads((imported / "project.json").read_text(encoding="utf-8"))
            imported_asset = imported / imported_project["assets"][0]["uri"]
            self.assertTrue(imported_asset.is_file())
            self.assertEqual(imported_project["sequences"][0]["tracks"][0]["clips"][0]["asset_id"], imported_project["assets"][0]["id"])
            self.assertEqual(result["data"]["report_data"]["failures"], [])

            tampered = workspace / "tampered.zip"
            with zipfile.ZipFile(package, "r") as source_archive, zipfile.ZipFile(tampered, "w") as target_archive:
                for info in source_archive.infolist():
                    data = source_archive.read(info.filename)
                    if info.filename.startswith("assets/"):
                        data = data + b"tamper"
                    target_archive.writestr(info, data)
            rejected = workspace / "tampered-import"
            code, rejected_result = invoke("convert", "import", "--input", str(tampered), "--output", str(rejected))
            self.assertEqual(code, 2, rejected_result)
            self.assertEqual(rejected_result["errors"][0]["code"], "ARGUMENT_INVALID")
            self.assertFalse((rejected / "project.json").exists())

    def test_otio_canonical_stack_gap_and_metadata_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-otio-canonical-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            self.assertEqual(code, 0, ingested)
            asset_id = ingested["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "id": "otio_gap_clip", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000, "timeline_start_tick": 45000,
                "transform": {"position": {"x": 0.63, "y": 0.38}}, "effects": [{"type": "grayscale"}],
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            otio = workspace / "canonical.otio"
            code, exported = invoke("convert", "export", "--project", str(project), "--output", str(otio), "--target-format", "otio")
            self.assertEqual(code, 0, exported)
            payload = json.loads(otio.read_text(encoding="utf-8"))
            self.assertEqual(payload["tracks"]["OTIO_SCHEMA"], "Stack.1")
            video_track = next(item for item in payload["tracks"]["children"] if item["name"] == "track_video_1")
            self.assertEqual(video_track["children"][0]["OTIO_SCHEMA"], "Gap.1")
            exported_clip = next(item for item in video_track["children"] if item["OTIO_SCHEMA"] == "Clip.2")
            self.assertEqual(exported_clip["source_range"]["duration"]["rate"], 90000)
            self.assertEqual(exported_clip["metadata"]["ai_ad_editor"]["clip"]["id"], "otio_gap_clip")
            imported = workspace / "imported"
            code, result = invoke("convert", "import", "--input", str(otio), "--output", str(imported))
            self.assertEqual(code, 0, result)
            imported_project = json.loads((imported / "project.json").read_text(encoding="utf-8"))
            imported_clip = next(clip for track in imported_project["sequences"][0]["tracks"] for clip in track["clips"] if clip["id"] == "otio_gap_clip")
            self.assertEqual(imported_clip["timeline_start_tick"], 45000)
            self.assertEqual(imported_clip["transform"]["position"]["x"], 0.63)
            self.assertEqual(imported_clip["effects"][0]["type"], "grayscale")

    def test_kdenlive_profile_blank_and_metadata_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-kdenlive-timing-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            self.assertEqual(code, 0, ingested)
            asset_id = ingested["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "id": "mlt_gap_clip", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000, "timeline_start_tick": 45000,
                "transform": {"scale": 0.74}, "transition_in": {"type": "fade", "duration": 0.2},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            xml_path = workspace / "timeline.kdenlive"
            code, exported = invoke("convert", "export", "--project", str(project), "--output", str(xml_path), "--target-format", "kdenlive-xml")
            self.assertEqual(code, 0, exported)
            xml_text = xml_path.read_text(encoding="utf-8")
            self.assertIn('frame_rate_num="30"', xml_text)
            self.assertIn('<blank length="15"', xml_text)
            self.assertIn("ai_ad_editor_clip_json", xml_text)
            imported = workspace / "imported"
            code, result = invoke("convert", "import", "--input", str(xml_path), "--output", str(imported))
            self.assertEqual(code, 0, result)
            imported_project = json.loads((imported / "project.json").read_text(encoding="utf-8"))
            imported_clip = next(clip for track in imported_project["sequences"][0]["tracks"] for clip in track["clips"] if clip["id"] == "mlt_gap_clip")
            self.assertEqual(imported_clip["timeline_start_tick"], 45000)
            self.assertEqual(imported_clip["transform"]["scale"], 0.74)
            self.assertEqual(imported_clip["transition_in"]["type"], "fade")

    def test_persistent_render_queue_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-queue-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ingested = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://fixture", "--license-spdx", "CC0-1.0",
                "--license-url", "local://license", "--evidence", "local://evidence",
            )
            self.assertEqual(code, 0, ingested)
            asset_id = ingested["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_audio_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            jobs = workspace / "queue.json"
            jobs.write_text(json.dumps({"jobs": [
                {"job_id": "queue-a", "sequence_id": "seq_main", "output": "renders/queue-a.mp4", "profile": "custom", "width": 320, "height": 180},
                {"job_id": "queue-b", "sequence_id": "seq_main", "output": "renders/queue-b.mp4", "profile": "custom", "width": 320, "height": 180},
            ]}), encoding="utf-8")
            code, enqueued = invoke("queue", "enqueue", "--project", str(project), "--input", str(jobs))
            self.assertEqual(code, 0, enqueued)
            self.assertEqual(enqueued["data"]["count"], 2)
            self.assertTrue((project / "operations" / "render-queue.json").exists())
            code, listed = invoke("queue", "list", "--project", str(project), "--status", "pending")
            self.assertEqual(code, 0, listed)
            self.assertEqual(listed["data"]["counts"]["pending"], 2)
            code, inspected = invoke("queue", "inspect", "--project", str(project), "--job-id", "queue-a")
            self.assertEqual(code, 0, inspected)
            self.assertEqual(inspected["data"]["job"]["status"], "pending")
            code, rendered = invoke("queue", "run", "--project", str(project), "--job-id", "queue-a")
            self.assertEqual(code, 0, rendered)
            self.assertEqual(rendered["data"]["summary"]["succeeded"], 1)
            self.assertTrue((project / "renders" / "queue-a.mp4").exists())
            code, inspected = invoke("queue", "inspect", "--project", str(project), "--job-id", "queue-a")
            self.assertEqual(code, 0, inspected)
            self.assertEqual(inspected["data"]["job"]["status"], "succeeded")
            code, cancelled = invoke("queue", "cancel", "--project", str(project), "--job-id", "queue-b")
            self.assertEqual(code, 0, cancelled)
            self.assertEqual(cancelled["data"]["job"]["status"], "cancelled")
            self.assertTrue(cancelled["data"]["acknowledged"])
            self.assertTrue(cancelled["data"]["confirmed"])
            code, inspected = invoke("queue", "inspect", "--project", str(project), "--job-id", "queue-b")
            self.assertEqual(code, 0, inspected)
            self.assertEqual(inspected["data"]["job"]["status"], "cancelled")
            kdenlive = workspace / "timeline.kdenlive"
            code, kdenlive_result = invoke("convert", "export", "--project", str(project), "--output", str(kdenlive), "--target-format", "kdenlive-xml")
            self.assertEqual(code, 0, kdenlive_result)
            self.assertIn("<mlt", kdenlive.read_text(encoding="utf-8"))
            kdenlive_imported = workspace / "kdenlive-imported"
            code, kdenlive_import_result = invoke("convert", "import", "--input", str(kdenlive), "--output", str(kdenlive_imported))
            self.assertEqual(code, 0, kdenlive_import_result)
            self.assertTrue((kdenlive_imported / "project.json").exists())

    def test_render_queue_bounded_parallel_workers_commit_each_job(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-queue-workers-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ingested = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://fixture", "--license-spdx", "CC0-1.0",
                "--license-url", "local://license", "--evidence", "local://evidence",
            )
            self.assertEqual(code, 0, ingested)
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": ingested["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_audio_1", "asset_id": ingested["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            jobs = workspace / "queue.json"
            jobs.write_text(json.dumps({"jobs": [
                {"job_id": "parallel-a", "output": "renders/parallel-a.mp4", "profile": "custom", "width": 320, "height": 180},
                {"job_id": "parallel-b", "output": "renders/parallel-b.mp4", "profile": "custom", "width": 320, "height": 180},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("queue", "enqueue", "--project", str(project), "--input", str(jobs))[0], 0)
            code, result = invoke("queue", "run", "--project", str(project), "--workers", "2", "--continue-on-error")
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["workers"], 2)
            self.assertEqual(result["data"]["summary"]["succeeded"], 2)
            self.assertEqual(result["data"]["summary"]["failed"], 0)
            self.assertTrue((project / "renders" / "parallel-a.mp4").exists())
            self.assertTrue((project / "renders" / "parallel-b.mp4").exists())
            queue_payload = json.loads((project / "operations" / "render-queue.json").read_text(encoding="utf-8"))
            self.assertEqual({job["status"] for job in queue_payload["jobs"]}, {"succeeded"})

    def test_render_queue_workers_require_continue_on_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-queue-workers-guard-") as raw:
            project = Path(raw) / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("queue", "run", "--project", str(project), "--workers", "2")
            self.assertEqual(code, 2, result)
            self.assertEqual(result["errors"][0]["code"], "ARGUMENT_INVALID")

    def test_project_write_lock_rejects_competing_mutation_and_releases(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-write-lock-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            ready = workspace / "lock-ready.txt"
            script = (
                "import time\n"
                "from pathlib import Path\n"
                "from ai_ad_editor.project import project_write_lock\n"
                f"project = Path({str(project)!r})\n"
                f"ready = Path({str(ready)!r})\n"
                "with project_write_lock(project):\n"
                "    ready.write_text('ready', encoding='utf-8')\n"
                "    time.sleep(2.5)\n"
            )
            child_env = os.environ.copy()
            child_env["PYTHONPATH"] = str(ROOT / "product" / "src")
            child = subprocess.Popen(
                [sys.executable, "-X", "utf8", "-c", script],
                env=child_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.monotonic() + 3.0
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(ready.exists(), "child did not acquire project lock")
                code, rejected = invoke("media", "ingest", "--project", str(project), "--input", str(source))
                self.assertEqual(code, 6, rejected)
                self.assertEqual(rejected["errors"][0]["code"], "PROJECT_WRITE_LOCKED")
                self.assertTrue(rejected["errors"][0]["retryable"])
            finally:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)
            code, accepted = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            self.assertEqual(code, 0, accepted)
            self.assertTrue((project / "operations" / "project-write.lock").exists())

    def test_queue_cancel_acknowledges_while_project_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-queue-cancel-lock-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            jobs = workspace / "queue.json"
            jobs.write_text(json.dumps({"jobs": [{"job_id": "locked-job", "output": "renders/locked.mp4", "profile": "custom", "width": 320, "height": 180}]}), encoding="utf-8")
            code, enqueued = invoke("queue", "enqueue", "--project", str(project), "--input", str(jobs))
            self.assertEqual(code, 0, enqueued)
            ready = workspace / "lock-ready.txt"
            script = (
                "import time\n"
                "from pathlib import Path\n"
                "from ai_ad_editor.project import project_write_lock\n"
                f"project = Path({str(project)!r})\n"
                f"ready = Path({str(ready)!r})\n"
                "with project_write_lock(project):\n"
                "    ready.write_text('ready', encoding='utf-8')\n"
                "    time.sleep(2.5)\n"
            )
            child_env = os.environ.copy()
            child_env["PYTHONPATH"] = str(ROOT / "product" / "src")
            child = subprocess.Popen([sys.executable, "-X", "utf8", "-c", script], env=child_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 3.0
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(ready.exists(), "child did not acquire project lock")
                code, requested = invoke("queue", "cancel", "--project", str(project), "--job-id", "locked-job")
                self.assertEqual(code, 0, requested)
                self.assertTrue(requested["data"]["acknowledged"])
                self.assertFalse(requested["data"]["confirmed"])
                self.assertEqual(requested["data"]["job"]["status"], "pending")
                self.assertTrue((project / "operations" / "queue-cancel" / "locked-job.cancel").exists())
                code, inspected = invoke("queue", "inspect", "--project", str(project), "--job-id", "locked-job")
                self.assertEqual(code, 0, inspected)
                self.assertTrue(inspected["data"]["job"]["cancel_requested"])
            finally:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)
            code, cancelled = invoke("queue", "run", "--project", str(project), "--job-id", "locked-job")
            self.assertEqual(code, 2, cancelled)
            self.assertEqual(cancelled["status"], "partial")
            self.assertEqual(cancelled["data"]["summary"]["cancelled"], 1)
            self.assertEqual(cancelled["data"]["jobs"][0]["status"], "cancelled")
            self.assertFalse((project / "operations" / "queue-cancel" / "locked-job.cancel").exists())
            code, retried = invoke("queue", "run", "--project", str(project), "--job-id", "locked-job")
            self.assertEqual(code, 2, retried)
            self.assertEqual(retried["data"]["summary"]["selected"], 1)
            self.assertEqual(retried["data"]["summary"]["cancelled"], 0)
            self.assertEqual(retried["data"]["summary"]["failed"], 1)
            self.assertEqual(retried["data"]["jobs"][0]["status"], "failed")

    def test_project_snapshots_restore_edit_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-snapshot-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, snapshot = invoke("project", "snapshot", "--project", str(project), "--label", "baseline")
            self.assertEqual(code, 0, snapshot)
            snapshot_id = snapshot["data"]["snapshot_id"]
            self.assertTrue((project / "history" / f"{snapshot_id}.json").exists())
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "add_marker", "id": "hook", "at_tick": 0, "label": "Hook",
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project_json["sequences"][0]["markers"][0]["id"], "hook")
            code, restored = invoke("project", "restore", "--project", str(project), "--snapshot", str(project / "history" / f"{snapshot_id}.json"))
            self.assertEqual(code, 0, restored)
            restored_project = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(restored_project["sequences"][0]["markers"], [])
            self.assertTrue(restored["data"]["backup"]["snapshot_id"])

    def test_project_transaction_recovery_restores_metadata_and_removes_new_records(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-transaction-recovery-") as raw:
            project = Path(raw) / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            project_before = (project / "project.json").read_bytes()
            ledger_before = (project / "rights-ledger.json").read_bytes()
            journal = prepare_project_transaction(project, command="test.interrupted")
            self.assertEqual(journal["status"], "prepared")
            changed = json.loads(project_before.decode("utf-8"))
            changed["project"]["name"] = "partially-written"
            (project / "project.json").write_text(json.dumps(changed), encoding="utf-8")
            (project / "rights-ledger.json").write_text(json.dumps({"partial": True}), encoding="utf-8")
            (project / "operations" / "partial-operation.json").write_text(json.dumps({"partial": True}), encoding="utf-8")
            recovered = recover_pending_transaction(project)
            self.assertEqual(recovered["status"], "recovered")
            self.assertTrue(recovered["recovered"])
            self.assertEqual((project / "project.json").read_bytes(), project_before)
            self.assertEqual((project / "rights-ledger.json").read_bytes(), ledger_before)
            self.assertFalse((project / "operations" / "partial-operation.json").exists())
            self.assertFalse((project / "operations" / "project-transaction.json").exists())

    def test_project_recover_cli_reports_noop_and_dry_run_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-project-recover-") as raw:
            project = Path(raw) / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            before = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))
            code, planned = invoke("project", "recover", "--project", str(project), "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertTrue(planned["data"]["pending"] is False)
            self.assertEqual(sorted(path.relative_to(project).as_posix() for path in project.rglob("*")), before)
            code, result = invoke("project", "recover", "--project", str(project))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["recovery"]["status"], "clean")

    def test_project_migrate_legacy_defaults_and_backup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-migrate-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            payload["schema_version"] = "0.0.0"
            payload["settings"].pop("output", None)
            payload["settings"].pop("audio", None)
            payload["settings"].pop("color", None)
            payload["sequences"][0].pop("markers", None)
            payload["sequences"][0]["tracks"][0].pop("muted", None)
            payload["sequences"][0]["tracks"][0].pop("locked", None)
            payload["provenance"] = {"change_log": []}
            payload["extensions"] = {"legacy_payload": {"unknown": "preserved"}}
            (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
            original = (project / "project.json").read_bytes()
            migrated_once = migrate_project_payload(payload, timestamp="2026-10-13T00:00:00Z")
            self.assertEqual(migrated_once, migrate_project_payload(payload, timestamp="2026-10-13T00:00:00Z"))
            self.assertEqual(payload["schema_version"], "0.0.0")
            code, planned = invoke("project", "migrate", "--project", str(project), "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertEqual((project / "project.json").read_bytes(), original)
            self.assertFalse(list((project / "history").iterdir()))
            code, result = invoke("project", "migrate", "--project", str(project))
            self.assertEqual(code, 0, result)
            self.assertTrue(result["data"]["migration"]["changed"])
            self.assertTrue(result["data"]["backup"]["snapshot_id"])
            migrated = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(migrated["schema_version"], "0.1.0")
            self.assertEqual(migrated["settings"]["output"]["container"], "mp4")
            self.assertEqual(migrated["extensions"], payload["extensions"])
            backup = json.loads(Path(result["data"]["backup"]["path"]).read_text(encoding="utf-8"))
            self.assertEqual(backup["project"], payload)
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)
            saved = (project / "project.json").read_bytes()
            code, repeated = invoke("project", "migrate", "--project", str(project))
            self.assertEqual(code, 0, repeated)
            self.assertFalse(repeated["data"]["migration"]["changed"])
            self.assertEqual((project / "project.json").read_bytes(), saved)
            code, relative_report = invoke("project", "migrate", "--project", str(project), "--report", "relative.json")
            self.assertEqual(code, 0, relative_report)
            self.assertEqual(Path(relative_report["data"]["report"]), project / "validation" / "relative.json")
            self.assertTrue((project / "validation" / "relative.json").exists())

    def test_project_migrate_rejects_unlocatable_legacy_asset(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-migrate-invalid-") as raw:
            project = Path(raw) / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            payload["schema_version"] = "0.0.0"
            payload["assets"] = [{"id": "asset_legacy", "kind": "video", "uri": "assets/missing.mp4", "probe": {}, "rights_ref": "asset_legacy"}]
            (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
            code, result = invoke("project", "migrate", "--project", str(project))
            self.assertEqual(code, 3, result)
            self.assertEqual(result["errors"][0]["code"], "MIGRATION_ASSET_HASH_MISSING")
            for version in ("0.2.0", "unknown", None):
                payload["schema_version"] = version
                (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
                before = (project / "project.json").read_bytes()
                code, rejected = invoke("project", "migrate", "--project", str(project))
                self.assertEqual(code, 2, rejected)
                self.assertEqual(rejected["errors"][0]["code"], "SCHEMA_VERSION_UNSUPPORTED")
                self.assertEqual((project / "project.json").read_bytes(), before)

    def test_missing_asset_can_be_relinked_by_content_hash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-relink-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingested["data"]["asset"]["id"]
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            missing = project / project_json["assets"][0]["uri"]
            missing.unlink()
            code, result = invoke("media", "relink", "--project", str(project), "--search-root", str(workspace))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["relinked"], 1)
            self.assertEqual(result["data"]["entries"][0]["status"], "Exact")
            relinked_project = json.loads((project / "project.json").read_text(encoding="utf-8"))
            relinked_path = project / relinked_project["assets"][0]["uri"]
            self.assertTrue(relinked_path.exists())
            self.assertEqual(relinked_project["assets"][0]["id"], asset_id)
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)

    def test_media_understand_exposes_local_beat_anchors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-beats-") as raw:
            workspace = Path(raw)
            source = self.make_pulse_audio(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("media", "understand", "--project", str(project), "--input", str(source), "--beats")
            self.assertEqual(code, 0, result)
            beats = result["data"]["result"]["beat_anchors"]
            self.assertIn(beats["status"], {"ok", "no_peaks", "insufficient_signal", "no_audio"})
            self.assertNotEqual(beats["status"], "failed")

    def test_local_beat_cut_plan_and_apply_writes_timeline_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-beat-cut-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            pulse = self.make_pulse_audio(workspace)
            project = workspace / "project"
            code, _ = invoke("project", "init", str(project), "--name", "Beat cut")
            self.assertEqual(code, 0)
            code, ingested = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://beat-source", "--license-spdx", "CC0-1.0",
                "--license-url", "local://license", "--evidence", "local://evidence",
            )
            self.assertEqual(code, 0, ingested)
            asset_id = ingested["data"]["asset"]["id"]
            code, result = invoke(
                "media", "beat-cut", "--project", str(project), "--input", str(pulse),
                "--source-asset-id", asset_id, "--track-id", "track_video_1",
                "--apply", "--replace-track", "--max-clips", "16",
            )
            self.assertEqual(code, 0, result)
            plan = result["data"]["plan"]
            self.assertTrue(plan["clips"])
            self.assertEqual(plan["engine"], "ffmpeg-local-energy-beat-v1")
            self.assertTrue(Path(result["data"]["report"]).exists())
            self.assertEqual(result["data"]["before_snapshot"]["label"], "before-beat-cut")
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            clips = payload["sequences"][0]["tracks"][0]["clips"]
            self.assertEqual(len(clips), len(plan["clips"]))
            self.assertTrue(all(item["asset_id"] == asset_id for item in clips))
            self.assertTrue(all(item["source_out_tick"] <= 90000 for item in clips))
            code, validation = invoke("validate", "--project", str(project), "--strict-rights")
            self.assertEqual(code, 0, validation)
            self.assertTrue(validation["data"]["ok"])

    def test_local_asr_requires_explicit_offline_model(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-asr-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("media", "understand", "--project", str(project), "--input", str(source), "--transcribe")
            self.assertEqual(code, 2, result)
            self.assertEqual(result["errors"][0]["code"], "ARGUMENT_INVALID")
            missing = workspace / "missing-model"
            code, result = invoke("media", "understand", "--project", str(project), "--input", str(source), "--transcribe", "--model-path", str(missing))
            self.assertEqual(code, 10, result)
            self.assertEqual(result["errors"][0]["code"], "LOCAL_ASR_MODEL_MISSING")

    def test_local_flite_tts_generates_project_wav_and_rejects_unsupported_locale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-tts-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            output = project / "assets" / "voice.wav"
            code, result = invoke(
                "tts",
                "synthesize",
                "--project",
                str(project),
                "--text",
                "Hello local advertising voice",
                "--output",
                str(output),
            )
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            self.assertEqual(result["data"]["engine"], "ffmpeg-flite-local")
            self.assertEqual(result["data"]["probe"]["audio"]["sample_rate"], 48_000)
            self.assertGreater(result["data"]["probe"]["duration_seconds"], 0.1)
            self.assertTrue((project / "operations" / f"{result['operation_id']}.json").exists())
            code, rejected = invoke("tts", "synthesize", "--project", str(project), "--text", "本地广告旁白")
            self.assertEqual(code, 2, rejected)
            self.assertEqual(rejected["errors"][0]["code"], "TTS_LOCALE_UNSUPPORTED")
            failed_output = project / "assets" / "failed.wav"
            code, failed = invoke("tts", "synthesize", "--project", str(project), "--text", "Hello", "--voice", "missing_voice", "--output", str(failed_output))
            self.assertEqual(code, 6, failed)
            self.assertEqual(failed["errors"][0]["code"], "TTS_SYNTHESIS_FAILED")
            self.assertFalse(failed_output.exists())

    def test_subtitle_formats_validate_and_normalize(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-subtitle-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            srt = workspace / "captions.srt"
            srt.write_text("1\n00:00:00,000 --> 00:00:00,500\n第一句\n\n2\n00:00:00,500 --> 00:00:01,000\n第二句\n", encoding="utf-8")
            code, result = invoke("subtitle", "validate", "--project", str(project), "--input", str(srt))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["count"], 2)
            normalized = project / "validation" / "normalized.srt"
            code, result = invoke("subtitle", "normalize", "--project", str(project), "--input", str(srt), "--output", str(normalized))
            self.assertEqual(code, 0, result)
            self.assertIn("第一句", normalized.read_text(encoding="utf-8"))
            vtt = workspace / "captions.vtt"
            vtt.write_text("WEBVTT\n\n00:00.000 --> 00:00.750\nVTT cue\n", encoding="utf-8")
            self.assertEqual(invoke("subtitle", "validate", "--input", str(vtt))[0], 0)
            ass = workspace / "captions.ass"
            ass.write_text("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.00,0:00:00.80,Default,,0,0,0,,ASS cue\n", encoding="utf-8")
            code, result = invoke("subtitle", "validate", "--input", str(ass))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["count"], 1)
            ttml = workspace / "captions.ttml"
            ttml.write_text(
                '<tt xmlns="http://www.w3.org/ns/ttml" ttp:frameRate="25" xmlns:ttp="http://www.w3.org/ns/ttml#parameter">'
                '<body begin="0s"><div><p begin="1s" dur="750ms">TTML <span>cue</span><br/>第二行</p></div></body></tt>',
                encoding="utf-8",
            )
            code, result = invoke("subtitle", "validate", "--input", str(ttml))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["count"], 1)
            self.assertEqual(result["data"]["cues"][0]["source_format"], "ttml")
            self.assertIn("第二行", result["data"]["cues"][0]["text"])
            ttml_normalized = project / "validation" / "ttml-normalized.srt"
            code, result = invoke("subtitle", "normalize", "--project", str(project), "--input", str(ttml), "--output", str(ttml_normalized))
            self.assertEqual(code, 0, result)
            self.assertIn("TTML cue", ttml_normalized.read_text(encoding="utf-8"))
            unsafe_ttml = workspace / "unsafe.ttml"
            unsafe_ttml.write_text('<!DOCTYPE tt SYSTEM "https://example.invalid/ttml.dtd"><tt/>', encoding="utf-8")
            code, rejected = invoke("subtitle", "validate", "--input", str(unsafe_ttml))
            self.assertEqual(code, 2, rejected)
            self.assertEqual(rejected["errors"][0]["code"], "ARGUMENT_INVALID")
            _, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(srt))
            self.assertEqual(ingested["data"]["asset"]["kind"], "subtitle")

    def test_local_library_index_and_search(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-library-") as raw:
            workspace = Path(raw)
            media_dir = workspace / "library"
            media_dir.mkdir()
            source = self.make_media(media_dir, "product.mp4")
            sidecar = media_dir / "product.srt"
            sidecar.write_text("1\n00:00:00,000 --> 00:00:00,500\nLocal product launch\n", encoding="utf-8")
            duplicate = media_dir / "product-copy.mp4"
            duplicate.write_bytes(source.read_bytes())
            catalog = workspace / "catalog.json"
            code, result = invoke("library", "index", "--root", str(media_dir), "--output", str(catalog))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["indexed_count"], 3)
            catalog_payload = json.loads(catalog.read_text(encoding="utf-8"))
            self.assertEqual(catalog_payload["catalog_version"], "0.3.0")
            product_record = next(item for item in catalog_payload["records"] if item["name"] == source.name)
            self.assertEqual(product_record["semantic"]["source"], "deterministic-local")
            self.assertIn("local", product_record["semantic"]["facets"]["subtitle_text"].casefold())
            self.assertTrue(product_record["semantic"]["facets"]["has_audio"])
            code, result = invoke("library", "search", "--catalog", str(catalog), "--query", "launch", "--kind", "video")
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["count"], 1)
            self.assertEqual(result["data"]["results"][0]["name"], source.name)
            code, result = invoke("library", "search", "--catalog", str(catalog), "--query", "product", "--has-audio")
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["count"], 2)
            code, result = invoke("library", "search", "--catalog", str(catalog), "--duplicate-only", "--kind", "video")
            self.assertEqual(code, 0, result)
            self.assertEqual({item["name"] for item in result["data"]["results"]}, {source.name, duplicate.name})
            code, result = invoke("library", "duplicates", "--catalog", str(catalog))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["method"], "sha256-exact")
            self.assertEqual(result["data"]["count"], 1)
            self.assertEqual(result["data"]["groups"][0]["count"], 2)

            code, result = invoke(
                "library", "index", "--root", str(media_dir), "--output", str(catalog),
                "--previous", str(catalog), "--incremental",
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["index_refresh"]["mode"], "incremental")
            self.assertEqual(result["data"]["index_refresh"]["reused_count"], 3)
            self.assertEqual(result["data"]["index_refresh"]["reindexed_count"], 0)

            sidecar.write_text("1\n00:00:00,000 --> 00:00:00,500\nLocal product launch v2\n", encoding="utf-8")
            changed_catalog = workspace / "changed-catalog.json"
            code, result = invoke(
                "library", "index", "--root", str(media_dir), "--output", str(changed_catalog),
                "--previous", str(catalog), "--incremental",
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["index_refresh"]["reused_count"], 1)
            self.assertEqual(result["data"]["index_refresh"]["reindexed_count"], 2)

            visual_catalog = workspace / "visual-catalog.json"
            code, result = invoke("library", "index", "--root", str(media_dir), "--output", str(visual_catalog), "--visual-hash")
            self.assertEqual(code, 0, result)
            visual_payload = json.loads(visual_catalog.read_text(encoding="utf-8"))
            self.assertEqual(visual_payload["index_refresh"]["visual_hash_count"], 2)
            code, result = invoke("library", "similar", "--catalog", str(visual_catalog), "--max-distance", "0")
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["method"], "ahash-v1")
            self.assertGreaterEqual(result["data"]["count"], 1)

            duplicate.unlink()
            removed_catalog = workspace / "removed-catalog.json"
            code, result = invoke(
                "library", "index", "--root", str(media_dir), "--output", str(removed_catalog),
                "--previous", str(visual_catalog), "--incremental",
            )
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["index_refresh"]["removed_count"], 1)

            code, result = invoke("library", "index", "--root", str(media_dir), "--output", str(workspace / "invalid.json"), "--incremental")
            self.assertEqual(code, 2, result)
            self.assertEqual(result["errors"][0]["code"], "ARGUMENT_INVALID")

    def test_local_asr_transcribe_applies_timestamped_subtitle_track(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-auto-subtitle-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project), "--name", "Auto captions")[0], 0)
            code, ingested = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://fixture", "--license-spdx", "CC0-1.0",
                "--license-url", "local://license", "--evidence", "local://evidence",
            )
            self.assertEqual(code, 0, ingested)
            source_asset_id = ingested["data"]["asset"]["id"]
            changes = workspace / "subtitle-track.json"
            changes.write_text(json.dumps({"operations": [{"op": "add_track", "track_id": "track_titles", "kind": "subtitle", "order": 3}]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)

            def fake_transcribe(root: Path, source_path: Path, *, engine: str, model_path: str | Path | None, language: str | None, output_srt: Path, use_gpu: bool = False) -> dict[str, Any]:
                output_srt.parent.mkdir(parents=True, exist_ok=True)
                output_srt.write_text("1\n00:00:00,000 --> 00:00:00,500\nLocal caption\n\n2\n00:00:00,500 --> 00:00:01,000\nSecond caption\n", encoding="utf-8")
                return {"status": "ok", "provider": "test-local-asr", "engine": engine, "model_path": str(model_path), "language": language, "text": "Local caption Second caption", "segments": [{"start": 0.0, "end": 0.5, "text": "Local caption"}, {"start": 0.5, "end": 1.0, "text": "Second caption"}], "timed": True, "srt": str(output_srt), "network": "disabled", "use_gpu": use_gpu}

            with patch("ai_ad_editor.cli._transcribe_with_local_engine", side_effect=fake_transcribe):
                code, result = invoke(
                    "subtitle", "transcribe", "--project", str(project), "--asset-id", source_asset_id,
                    "--model-path", str(workspace / "model"), "--track-id", "track_titles", "--apply",
                )
            self.assertEqual(code, 0, result)
            self.assertTrue(result["data"]["applied"])
            self.assertTrue(Path(result["data"]["output"]).exists())
            self.assertTrue(Path(result["data"]["report"]).exists())
            self.assertTrue((project / "history" / f"{result['data']['before_snapshot']['snapshot_id']}.json").exists())
            saved = json.loads((project / "project.json").read_text(encoding="utf-8"))
            subtitle_track = next(track for track in saved["sequences"][0]["tracks"] if track["id"] == "track_titles")
            self.assertEqual([clip["subtitle"]["text"] for clip in subtitle_track["clips"]], ["Local caption", "Second caption"])
            self.assertEqual(invoke("validate", "--project", str(project), "--strict-rights")[0], 0)

    def test_quality_scopes_generate_local_color_review_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-scopes-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("quality", "scopes", "--project", str(project), "--input", str(source), "--at-seconds", "0.2")
            self.assertEqual(code, 0, result)
            self.assertEqual(result["command"], "quality.scopes")
            self.assertEqual(result["data"]["engine"], "ffmpeg-local")
            self.assertEqual({item["type"] for item in result["data"]["artifacts"]}, {"waveform", "vectorscope", "histogram"})
            self.assertTrue(Path(result["data"]["report"]).exists())
            for artifact in result["data"]["artifacts"]:
                self.assertTrue(Path(artifact["path"]).exists())
                self.assertGreater(artifact["bytes"], 0)

    def test_quality_golden_capture_and_verify_reports_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-golden-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            capture_args = (
                "quality", "golden", "--project", str(project), "--input", str(source),
                "--mode", "capture", "--profile", "custom", "--width", "320", "--height", "180", "--require-audio",
            )
            code, captured = invoke(*capture_args)
            self.assertEqual(code, 0, captured)
            manifest_path = Path(captured["data"]["manifest"])
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["golden_version"], "0.1.0")
            self.assertTrue(manifest["artifact"]["sha256"].startswith("sha256:"))
            code, verified = invoke(
                "quality", "golden", "--project", str(project), "--input", str(source),
                "--mode", "verify", "--profile", "custom", "--width", "320", "--height", "180",
            )
            self.assertEqual(code, 0, verified)
            self.assertEqual(verified["data"]["mismatches"], [])
            source.write_bytes(source.read_bytes() + b"golden-drift")
            code, drifted = invoke(
                "quality", "golden", "--project", str(project), "--input", str(source),
                "--mode", "verify", "--profile", "custom", "--width", "320", "--height", "180",
            )
            self.assertEqual(code, 2, drifted)
            self.assertTrue(any(item["code"] == "QUALITY_GOLDEN_HASH_MISMATCH" for item in drifted["errors"]))

    def test_media_prepare_generates_proxy_thumbnail_and_waveform(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-prepare-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            code, result = invoke("media", "prepare", "--project", str(project), "--asset-id", asset_id, "--proxy-width", "160", "--thumbnail", "--waveform")
            self.assertEqual(code, 0, result)
            self.assertTrue(Path(result["data"]["proxy"]).exists())
            self.assertTrue(Path(result["data"]["thumbnail"]).exists())
            self.assertTrue(Path(result["data"]["waveform"]).exists())
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            asset = project_json["assets"][0]
            self.assertEqual(asset["proxy"]["width"], 160)
            self.assertIn("thumbnail", asset)
            self.assertIn("waveform", asset)

    def test_media_stabilize_creates_derived_asset_with_inherited_rights(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-stabilize-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingested = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--asset-id", "source-video", "--verification-status", "verified",
                "--permitted-use", "commercial_ad", "--source-url", "local://stabilize-source",
                "--license-spdx", "CC0-1.0", "--evidence", "local://stabilize-source",
            )
            source_id = ingested["data"]["asset"]["id"]
            code, planned = invoke(
                "media", "stabilize", "--project", str(project), "--asset-id", source_id,
                "--derived-asset-id", "stabilized-dry-run", "--smoothing", "3", "--dry-run",
            )
            self.assertEqual(code, 0, planned)
            self.assertEqual(planned["status"], "planned")
            self.assertEqual(planned["data"]["engine"], "ffmpeg-local:vidstabdetect+vidstabtransform")
            self.assertFalse((project / "assets" / "derived" / "stabilized_stabilized-dry-run.mp4").exists())
            output = project / "assets" / "derived" / "stabilized-source-video.mp4"
            code, applied = invoke(
                "media", "stabilize", "--project", str(project), "--asset-id", source_id,
                "--derived-asset-id", "stabilized-source-video", "--output", str(output),
                "--shakiness", "4", "--accuracy", "8", "--smoothing", "3",
            )
            self.assertEqual(code, 0, applied)
            self.assertTrue(output.exists())
            self.assertGreater(probe_media(output)["duration_seconds"], 0.5)
            self.assertEqual(applied["data"]["snapshot"]["label"], "before-stabilize")
            report = Path(applied["data"]["report"])
            self.assertTrue(report.exists())
            report_payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(report_payload["stabilization"]["engine"], "ffmpeg-local:vidstabdetect+vidstabtransform")
            self.assertEqual(report_payload["stabilization"]["parameters"]["smoothing"], 3)
            rights = applied["data"]["rights"]
            self.assertEqual(rights["derived_from"], [source_id])
            self.assertEqual(rights["verification_status"], "verified")
            self.assertEqual(rights["license_spdx"], "CC0-1.0")
            code, validated = invoke("validate", "--project", str(project), "--strict-rights")
            self.assertEqual(code, 0, validated)

    def test_local_audio_extract_registers_derived_asset_and_applies_audio_clip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-audio-extract-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace, "camera.mp4")
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            self.assertEqual(code, 0, ingested)
            asset_id = ingested["data"]["asset"]["id"]
            before = (project / "project.json").read_text(encoding="utf-8")
            code, planned = invoke(
                "audio", "extract", "--project", str(project), "--asset-id", asset_id,
                "--derived-asset-id", "camera_audio", "--track-id", "track_audio_1", "--apply", "--dry-run",
            )
            self.assertEqual(code, 0, planned)
            self.assertEqual(planned["data"]["engine"], "ffmpeg-local-audio-extract-v1")
            self.assertEqual((project / "project.json").read_text(encoding="utf-8"), before)
            code, applied = invoke(
                "audio", "extract", "--project", str(project), "--asset-id", asset_id,
                "--derived-asset-id", "camera_audio", "--track-id", "track_audio_1", "--apply",
            )
            self.assertEqual(code, 0, applied)
            self.assertEqual(applied["data"]["snapshot"]["label"], "before-audio-extract")
            self.assertEqual(applied["data"]["rights"]["derived_from"], [asset_id])
            output = Path(applied["data"]["asset"]["uri"])
            self.assertTrue(output.exists() or (project / output).exists())
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            derived = next(item for item in payload["assets"] if item["id"] == "camera_audio")
            self.assertEqual(derived["kind"], "audio")
            audio_track = next(track for track in payload["sequences"][0]["tracks"] if track["id"] == "track_audio_1")
            self.assertEqual(audio_track["clips"][0]["asset_id"], "camera_audio")
            code, audit = invoke("policy", "audit", "--project", str(project))
            self.assertEqual(code, 0, audit)

    def test_local_audio_separate_writes_mid_side_stems_and_applies_selected_stem(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-audio-separate-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace, "camera.mp4")
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            self.assertEqual(code, 0, ingested)
            source_id = ingested["data"]["asset"]["id"]
            before = (project / "project.json").read_text(encoding="utf-8")
            code, planned = invoke(
                "audio", "separate", "--project", str(project), "--asset-id", source_id,
                "--center-asset-id", "camera_center", "--side-asset-id", "camera_side",
                "--track-id", "track_audio_1", "--stem", "center", "--apply", "--dry-run",
            )
            self.assertEqual(code, 0, planned)
            self.assertEqual(planned["data"]["engine"], "ffmpeg-local-mid-side-v1")
            self.assertEqual((project / "project.json").read_text(encoding="utf-8"), before)
            code, applied = invoke(
                "audio", "separate", "--project", str(project), "--asset-id", source_id,
                "--center-asset-id", "camera_center", "--side-asset-id", "camera_side",
                "--track-id", "track_audio_1", "--stem", "center", "--apply",
            )
            self.assertEqual(code, 0, applied)
            self.assertEqual(applied["data"]["snapshot"]["label"], "before-audio-separate")
            self.assertEqual(applied["data"]["separation"]["method"], "mid-side")
            self.assertEqual(applied["warnings"][0]["code"], "AUDIO_SEPARATION_APPROXIMATE")
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual({item["id"] for item in payload["assets"][-2:]}, {"camera_center", "camera_side"})
            audio_track = next(track for track in payload["sequences"][0]["tracks"] if track["id"] == "track_audio_1")
            self.assertEqual(audio_track["clips"][0]["asset_id"], "camera_center")
            ledger = json.loads((project / "rights-ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ledger["records"]), 3)

            code, audit = invoke("policy", "audit", "--project", str(project))
            self.assertEqual(code, 0, audit)

    def test_local_audio_adapter_registry_hashes_and_gates_unimplemented_runner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-audio-adapter-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace, "camera.mp4")
            model = workspace / "demucs-model.bin"
            model.write_bytes(b"local model fixture v1")
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            self.assertEqual(code, 0, ingested)
            source_id = ingested["data"]["asset"]["id"]

            code, planned = invoke(
                "audio", "adapter", "register", "--project", str(project),
                "--adapter-id", "demucs_fixture", "--engine", "demucs-local-v1",
                "--model-path", str(model), "--dry-run",
            )
            self.assertEqual(code, 0, planned)
            self.assertEqual(planned["status"], "planned")
            self.assertFalse((project / "models" / "audio-adapters.json").exists())

            code, registered = invoke(
                "audio", "adapter", "register", "--project", str(project),
                "--adapter-id", "demucs_fixture", "--engine", "demucs-local-v1",
                "--model-path", str(model), "--license-spdx", "CC0-1.0",
                "--verification-status", "verified", "--evidence", "local://model-evidence",
            )
            self.assertEqual(code, 0, registered)
            self.assertEqual(registered["data"]["snapshot"]["label"], "before-audio-adapter-register")
            self.assertTrue(registered["data"]["adapter"]["model_sha256"].startswith("sha256:"))
            self.assertEqual(registered["data"]["rights"]["kind"], "model-adapter")

            code, listed = invoke("audio", "adapter", "list", "--project", str(project))
            self.assertEqual(code, 0, listed)
            self.assertEqual(listed["data"]["count"], 1)
            self.assertTrue(listed["data"]["adapters"][0]["verification"]["ok"])
            code, inspected = invoke("audio", "adapter", "inspect", "--project", str(project), "--adapter-id", "demucs_fixture")
            self.assertEqual(code, 0, inspected)
            self.assertTrue(inspected["data"]["verification"]["ok"])

            code, rejected = invoke(
                "audio", "separate", "--project", str(project), "--asset-id", source_id,
                "--adapter-id", "demucs_fixture",
            )
            self.assertEqual(code, 10, rejected)
            self.assertEqual(rejected["errors"][0]["code"], "AUDIO_SEPARATION_ADAPTER_UNAVAILABLE")

            model.write_bytes(b"local model fixture v2")
            code, tampered = invoke("audio", "adapter", "inspect", "--project", str(project), "--adapter-id", "demucs_fixture")
            self.assertEqual(code, 0, tampered)
            self.assertFalse(tampered["data"]["verification"]["ok"])
            self.assertEqual(tampered["data"]["verification"]["findings"][0]["code"], "MODEL_HASH_MISMATCH")
            ledger = json.loads((project / "rights-ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["records"][-1]["asset_id"], "adapter:demucs_fixture")


    def test_command_json_audio_adapter_runs_local_protocol_and_registers_stems(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-command-json-audio-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace, "camera.mp4")
            model = workspace / "model.bin"
            model.write_bytes(b"command-json model fixture v1")
            runner = workspace / "runner.py"
            runner.write_text(
                """import json
import subprocess
import sys

request = json.load(sys.stdin)
assert request[\"protocol\"] == \"agent-video-audio-separation-v1\"
for stem in (\"center\", \"side\"):
    output = request[\"outputs\"][stem]
    subprocess.run([
        \"ffmpeg\", \"-hide_banner\", \"-loglevel\", \"error\", \"-y\",
        \"-i\", request[\"source\"][\"path\"], \"-map\", \"0:a:0\",
        \"-c:a\", \"pcm_s16le\", output,
    ], check=True)
print(json.dumps({
    \"protocol\": \"agent-video-audio-separation-v1\",
    \"status\": \"ok\",
    \"stems\": request[\"outputs\"],
    \"network\": \"disabled\",
}))
""",
                encoding="utf-8",
            )
            unsafe_runner = workspace / "runner.cmd"
            unsafe_runner.write_text("@echo off\necho unsafe\n", encoding="utf-8")
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            source_id = ingested["data"]["asset"]["id"]
            code, unsafe = invoke(
                "audio", "adapter", "register", "--project", str(project),
                "--adapter-id", "unsafe_command_json", "--engine", "command-json-v1",
                "--model-path", str(model), "--executable", str(unsafe_runner), "--dry-run",
            )
            self.assertEqual(code, 10, unsafe)
            self.assertEqual(unsafe["errors"][0]["code"], "MODEL_EXECUTABLE_UNSAFE")
            code, registered = invoke(
                "audio", "adapter", "register", "--project", str(project),
                "--adapter-id", "command_json_fixture", "--engine", "command-json-v1",
                "--model-path", str(model), "--executable", str(runner),
                "--license-spdx", "CC0-1.0", "--verification-status", "verified",
                "--evidence", "local://command-json-fixture",
            )
            self.assertEqual(code, 0, registered)
            code, separated = invoke(
                "audio", "separate", "--project", str(project), "--asset-id", source_id,
                "--adapter-id", "command_json_fixture", "--center-asset-id", "json_center",
                "--side-asset-id", "json_side",
            )
            self.assertEqual(code, 0, separated)
            separation = separated["data"]["separation"]
            self.assertEqual(separation["engine"], "command-json-v1")
            self.assertEqual(separation["method"], "command-json")
            self.assertEqual(separation["protocol"], "agent-video-audio-separation-v1")
            self.assertTrue(Path(separation["stems"]["center"]["output"]).exists())
            self.assertTrue(Path(separation["stems"]["side"]["output"]).exists())
            self.assertTrue(any(item["code"] == "AUDIO_SEPARATION_LOCAL_RUNNER_REVIEW" for item in separated["warnings"]))
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual({item["id"] for item in payload["assets"][-2:]}, {"json_center", "json_side"})
            operation = json.loads((project / "operations" / f"{separated['operation_id']}.json").read_text(encoding="utf-8"))
            self.assertEqual(operation["engine"], "command-json-v1")


    def test_local_highlight_recommendation_writes_auditable_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-highlights-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("media", "highlights", "--project", str(project), "--input", str(source), "--beats", "--top-k", "3")
            self.assertEqual(code, 0, result)
            report = Path(result["data"]["report"])
            self.assertTrue(report.exists())
            recommendation = result["data"]["recommendation"]
            self.assertEqual(recommendation["engine"], "local-heuristic")
            self.assertEqual(recommendation["network"], "disabled")
            self.assertLessEqual(len(recommendation["candidates"]), 3)

    def test_local_highlights_apply_writes_timeline_with_snapshot_and_review_warning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-highlights-apply-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            self.assertEqual(code, 0, ingested)
            asset_id = ingested["data"]["asset"]["id"]
            report = project / "validation" / "highlights-apply.json"
            code, applied = invoke(
                "media", "highlights", "--project", str(project), "--asset-id", asset_id,
                "--track-id", "track_video_1", "--top-k", "3", "--replace-track", "--apply",
                "--output", str(report),
            )
            self.assertEqual(code, 0, applied)
            self.assertTrue(report.exists())
            self.assertTrue(any(item["code"] == "HIGHLIGHTS_HEURISTIC" for item in applied["warnings"]))
            self.assertTrue(any(item["code"] == "HIGHLIGHTS_REVIEW_REQUIRED" for item in applied["warnings"]))
            self.assertEqual(applied["data"]["before_snapshot"]["label"], "before-highlights")
            self.assertGreaterEqual(len(applied["data"]["generated_clips"]), 1)
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            video_track = next(track for track in payload["sequences"][0]["tracks"] if track["id"] == "track_video_1")
            self.assertEqual(len(video_track["clips"]), len(applied["data"]["generated_clips"]))
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)

    def test_local_smart_cut_plan_and_apply_links_audio(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-smart-cut-") as raw:
            workspace = Path(raw)
            source = workspace / "speech-pauses.mp4"
            audio_expr = r"aevalsrc=if(between(t\,0\,0.8)+between(t\,1.8\,3)\,0.8*sin(2*PI*880*t)\,0):s=48000:d=3"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=24:d=3",
                    "-f", "lavfi", "-i", audio_expr,
                    "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingested["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "id": "speech_clip", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 270000},
                {"op": "append_clip", "track_id": "track_audio_1", "id": "speech_audio", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 270000},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            code, planned = invoke(
                "media", "smart-cut", "--project", str(project), "--clip-id", "speech_clip", "--track-id", "track_video_1",
                "--linked-track-id", "track_audio_1", "--linked-clip-id", "speech_audio", "--min-silence-seconds", "0.5", "--dry-run",
            )
            self.assertEqual(code, 0, planned)
            self.assertTrue(planned["data"]["plan"]["changed"])
            self.assertGreater(planned["data"]["plan"]["removed_seconds"], 0.2)
            code, applied = invoke(
                "media", "smart-cut", "--project", str(project), "--clip-id", "speech_clip", "--track-id", "track_video_1",
                "--linked-track-id", "track_audio_1", "--linked-clip-id", "speech_audio", "--min-silence-seconds", "0.5", "--apply",
            )
            self.assertEqual(code, 0, applied)
            self.assertTrue(applied["data"]["plan"]["changed"])
            self.assertTrue(applied["data"]["before_snapshot"]["snapshot_id"])
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            sequence = project_json["sequences"][0]
            for track_id in ("track_video_1", "track_audio_1"):
                track = next(item for item in sequence["tracks"] if item["id"] == track_id)
                self.assertEqual(len(track["clips"]), len(applied["data"]["plan"]["kept_ranges"]))
                prefix = "speech_clip.smart" if track_id == "track_video_1" else "speech_audio.smart"
                self.assertTrue(all(item["id"].startswith(prefix) for item in track["clips"]))
            self.assertLess(sequence["duration_tick"], 270000)
            output = project / "renders" / "smart-cut.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertLess(probe_media(output)["duration_seconds"], 3.0)

    def test_local_smart_cut_removes_explicit_transcript_phrase_cue(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-smart-cut-transcript-") as raw:
            workspace = Path(raw)
            source = workspace / "continuous-speech.mp4"
            audio_expr = r"aevalsrc=0.8*sin(2*PI*880*t):s=48000:d=3"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=green:s=320x180:r=24:d=3",
                    "-f", "lavfi", "-i", audio_expr,
                    "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingested["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "id": "phrase_clip", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 270000},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            transcript = project / "validation" / "captions.srt"
            transcript.write_text("1\n00:00:01,000 --> 00:00:01,250\n嗯\n\n2\n00:00:01,250 --> 00:00:03,000\n保留内容\n", encoding="utf-8")
            common = (
                "media", "smart-cut", "--project", str(project), "--clip-id", "phrase_clip", "--track-id", "track_video_1",
                "--transcript", str(transcript), "--remove-phrase", "嗯", "--min-silence-seconds", "10", "--min-segment-seconds", "0.05",
            )
            code, planned = invoke(*common, "--dry-run")
            self.assertEqual(code, 0, planned)
            plan = planned["data"]["plan"]
            self.assertEqual(plan["semantic"]["matches"][0]["phrases"], ["嗯"])
            self.assertEqual(plan["semantic"]["ranges"][0]["start_seconds"], 1.0)
            self.assertGreater(plan["removed_seconds"], 0.2)
            self.assertTrue(any(item["code"] == "SMART_CUT_SEMANTIC_CUE_GRANULARITY" for item in planned["warnings"]))
            code, applied = invoke(*common, "--apply")
            self.assertEqual(code, 0, applied)
            self.assertEqual(applied["data"]["before_snapshot"]["label"], "before-smart-cut")
            self.assertEqual(len(applied["data"]["replacements"][0]["piece_ids"]), 2)

    def test_local_multicam_audio_sync_and_cut(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-multicam-") as raw:
            workspace = Path(raw)
            reference = workspace / "reference.mp4"
            candidate = workspace / "candidate.mp4"
            expression = "0.8*sin(2*PI*(300+100*t)*t)+0.3*sin(2*PI*(700+50*t)*t)"
            commands = [
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=green:s=320x180:r=24:d=4",
                    "-f", "lavfi", "-i", f"aevalsrc={expression}:s=48000:d=4",
                    "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(reference),
                ],
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=24:d=4.5",
                    "-f", "lavfi", "-i", f"aevalsrc={expression}:s=48000:d=4",
                    "-filter_complex", "[1:a]adelay=500|500[a]", "-map", "0:v:0", "-map", "[a]", "-t", "4.5",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(candidate),
                ],
            ]
            for command in commands:
                completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ref_result = invoke("media", "ingest", "--project", str(project), "--input", str(reference))
            self.assertEqual(code, 0, ref_result)
            code, candidate_result = invoke("media", "ingest", "--project", str(project), "--input", str(candidate))
            self.assertEqual(code, 0, candidate_result)
            reference_id = ref_result["data"]["asset"]["id"]
            candidate_id = candidate_result["data"]["asset"]["id"]
            project_before_dry_run = (project / "project.json").read_text(encoding="utf-8")
            common = (
                "media", "multicam", "--project", str(project),
                "--source-asset-id", reference_id, "--source-asset-id", candidate_id,
                "--reference-asset-id", reference_id, "--sample-rate", "4000", "--analysis-seconds", "5",
                "--max-offset-seconds", "1", "--switch-seconds", "1", "--track-id", "track_video_1",
            )
            code, planned = invoke(*common, "--dry-run")
            self.assertEqual(code, 0, planned)
            offsets = planned["data"]["plan"]["sync"]["offsets"]
            candidate_offset = next(item for item in offsets if item["asset_id"] == candidate_id)
            self.assertAlmostEqual(candidate_offset["relative_delay_seconds"], 0.5, delta=0.1)
            self.assertEqual(len(planned["data"]["plan"]["segments"]), 4)
            self.assertIsNone(planned["data"]["report"])
            self.assertEqual((project / "project.json").read_text(encoding="utf-8"), project_before_dry_run)
            code, applied = invoke(*common, "--apply", "--replace-track")
            self.assertEqual(code, 0, applied)
            self.assertEqual(applied["data"]["before_snapshot"]["label"], "before-multicam")
            self.assertEqual(len(applied["data"]["generated_clips"]), 4)
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            video_track = next(track for track in project_payload["sequences"][0]["tracks"] if track["id"] == "track_video_1")
            self.assertEqual(len(video_track["clips"]), 4)
            self.assertEqual([clip["asset_id"] for clip in video_track["clips"]], [reference_id, candidate_id, reference_id, candidate_id])

    def test_local_ad_plan_writes_timed_phases_and_markers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-plan-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            brief = workspace / "brief.json"
            brief.write_text(json.dumps({
                "product": "Local Camera",
                "audience": "短视频创作者",
                "duration_seconds": 12,
                "cta": "立即试用",
                "hook": "三秒完成自动剪辑",
                "benefit": "离线快速导出",
                "profile": "vertical",
            }), encoding="utf-8")
            code, result = invoke("ad", "plan", "--project", str(project), "--input", str(brief))
            self.assertEqual(code, 0, result)
            plan = result["data"]["plan"]
            self.assertEqual(plan["engine"], "local-ad-plan")
            self.assertEqual(plan["network"], "disabled")
            self.assertEqual(plan["duration_tick"], sum(item["duration_tick"] for item in plan["phases"]))
            self.assertEqual(len(plan["markers"]), len(plan["phases"]))
            self.assertTrue(Path(result["data"]["output"]).exists())

    def test_local_ad_plan_apply_writes_markers_with_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-plan-apply-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            brief = workspace / "brief.json"
            brief.write_text(json.dumps({"product": "Local Camera", "duration_seconds": 6, "cta": "立即试用"}), encoding="utf-8")
            code, planned = invoke("ad", "plan", "--project", str(project), "--input", str(brief))
            self.assertEqual(code, 0, planned)
            plan_path = planned["data"]["output"]
            code, applied = invoke("ad", "apply", "--project", str(project), "--input", plan_path)
            self.assertEqual(code, 0, applied)
            self.assertTrue(applied["data"]["before_snapshot"]["snapshot_id"])
            self.assertIn("set_sequence_duration", [item["op"] for item in applied["data"]["applied"]])
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["sequences"][0]["markers"]), 6)
            self.assertEqual(payload["sequences"][0]["duration_tick"], 540000)
            code, duplicate = invoke("ad", "apply", "--project", str(project), "--input", plan_path)
            self.assertEqual(code, 2, duplicate)
            self.assertEqual(duplicate["errors"][0]["code"], "ARGUMENT_INVALID")
            code, replaced = invoke("ad", "apply", "--project", str(project), "--input", plan_path, "--replace-markers")
            self.assertEqual(code, 0, replaced)

    def test_capabilities_manifest_is_local_and_agent_readable(self) -> None:
        code, result = invoke("capabilities")
        self.assertEqual(code, 0, result)
        manifest = result["data"]
        self.assertEqual(manifest["engine"]["network"], "disabled")
        self.assertIn("bezier", manifest["capabilities"]["keyframes"]["interpolation"])
        self.assertIn("transform.anchor.x", manifest["capabilities"]["keyframes"]["properties"])
        self.assertIn("transform.anchor.y", manifest["capabilities"]["keyframes"]["properties"])
        self.assertIn("transform_anchor", manifest["capabilities"]["timeline"]["features"])
        self.assertIn("crossfade", manifest["capabilities"]["transitions"]["features"])
        self.assertIn("safe_resume", manifest["capabilities"]["render"]["features"])
        self.assertIn("sequential_run", manifest["capabilities"]["queue"]["features"])
        self.assertIn("bounded_local_workers", manifest["capabilities"]["queue"]["features"])
        self.assertIn("serial_metadata_commit", manifest["capabilities"]["queue"]["features"])
        self.assertIn("cancel_ack_while_project_lock_held", manifest["capabilities"]["queue"]["features"])
        self.assertIn("snapshot", manifest["capabilities"]["project"]["features"])
        self.assertIn("native_process_write_lock", manifest["capabilities"]["project"]["features"])
        self.assertIn("relink_by_hash", manifest["capabilities"]["media"]["features"])
        self.assertIn("local_auto_reframe", manifest["capabilities"]["media"]["features"])
        self.assertIn("local_multi_object_tracking", manifest["capabilities"]["media"]["features"])
        self.assertIn("multi_object_tracking_apply_requires_explicit_object_selection", manifest["capabilities"]["media"]["limits"])
        self.assertIn("target_lufs_gate", manifest["capabilities"]["quality"]["features"])
        self.assertIn("vectorscope", manifest["capabilities"]["quality"]["features"])
        self.assertIn("independent_text_track", manifest["capabilities"]["subtitles"]["features"])
        self.assertIn("independent_rotate_text_layer", manifest["capabilities"]["subtitles"]["features"])
        self.assertIn("independent_text_transform_keyframes", manifest["capabilities"]["subtitles"]["features"])
        self.assertIn("independent_text_masks", manifest["capabilities"]["subtitles"]["features"])
        self.assertIn("independent_text_blend", manifest["capabilities"]["subtitles"]["features"])
        self.assertIn("mixed_video_text_track_order", manifest["capabilities"]["subtitles"]["features"])
        self.assertIn("independent_text_fade_transitions", manifest["capabilities"]["subtitles"]["features"])
        self.assertIn("independent_text_spatial_transitions", manifest["capabilities"]["subtitles"]["features"])
        self.assertIn("otio_stack_track_gap_clip", manifest["capabilities"]["interoperability"]["features"])
        self.assertIn("portable_agent_project_package", manifest["capabilities"]["interoperability"]["features"])
        self.assertIn("package_sha256_manifest", manifest["capabilities"]["interoperability"]["features"])
        self.assertIn("kdenlive_blank_gap_mapping", manifest["capabilities"]["interoperability"]["features"])
        self.assertIn("effect_parameter_keyframes", manifest["capabilities"]["effects"]["features"])
        self.assertIn("sequence_adjustments", manifest["capabilities"]["effects"]["features"])
        self.assertIn("lut3d_project_local", manifest["capabilities"]["effects"]["features"])
        self.assertIn("yuv420p10le", manifest["capabilities"]["output"]["pixel_formats"])
        self.assertIn("yuva420p", manifest["capabilities"]["output"]["pixel_formats"])
        self.assertIn("hable", manifest["capabilities"]["output"]["tone_mapping"])
        self.assertIn("local_flite_tts", manifest["capabilities"]["ai"]["features"])
        self.assertIn("local_ad_plan_apply", manifest["capabilities"]["ai"]["features"])
        self.assertIn("smart_cut_silence", manifest["capabilities"]["media"]["features"])
        self.assertIn("smart_cut_linked_audio", manifest["capabilities"]["media"]["features"])
        self.assertIn("beat_cut_timeline", manifest["capabilities"]["media"]["features"])
        self.assertIn("media_beat_cut", manifest["capabilities"]["media"]["beat_cut_contract"])
        self.assertIn("heuristic_highlights", manifest["capabilities"]["media"]["features"])
        self.assertIn("highlight_rough_cut_apply", manifest["capabilities"]["media"]["features"])
        self.assertIn("media_highlights", manifest["capabilities"]["media"]["highlights_contract"])
        self.assertIn("heuristic_highlights", manifest["capabilities"]["ai"]["features"])
        self.assertIn("stabilize_vidstab_two_pass", manifest["capabilities"]["media"]["features"])
        self.assertIn("media_stabilize", manifest["capabilities"]["media"]["stabilize_contract"])
        self.assertIn("track_mute", manifest["capabilities"]["audio"]["features"])
        self.assertIn("track_solo", manifest["capabilities"]["audio"]["features"])
        self.assertIn("track_volume", manifest["capabilities"]["audio"]["features"])
        self.assertIn("offline_adapter_registry", manifest["capabilities"]["audio"]["features"])
        self.assertIn("unknown_audio_adapter_never_falls_back_to_mid_side", manifest["capabilities"]["audio"]["limits"])
        self.assertEqual(manifest["capabilities"]["effects"]["catalog_version"], "0.9.0")
        self.assertIn("exposure", manifest["capabilities"]["effects"]["catalog_features"])
        self.assertIn("hsl", manifest["capabilities"]["effects"]["catalog_features"])
        self.assertIn("rgb_curves", manifest["capabilities"]["effects"]["catalog_features"])
        self.assertIn("color_wheel", manifest["capabilities"]["effects"]["catalog_features"])
        self.assertIn("hsl", manifest["capabilities"]["effects"]["features"])
        self.assertIn("rgb_curves", manifest["capabilities"]["effects"]["features"])
        self.assertIn("color_wheel", manifest["capabilities"]["effects"]["features"])
        self.assertIn("effect_catalog_cli", manifest["capabilities"]["effects"]["features"])
        self.assertIn("deterministic_token_search", manifest["capabilities"]["library"]["features"])
        self.assertIn("incremental_stat_refresh", manifest["capabilities"]["library"]["features"])
        self.assertIn("ffmpeg_average_hash_candidates", manifest["capabilities"]["library"]["features"])
        self.assertEqual(manifest["capabilities"]["library"]["catalog_version"], "0.3.0")
        self.assertFalse(manifest["capabilities"]["library"]["vector_index"])
        self.assertIn("typed_variables", manifest["capabilities"]["templates"]["features"])
        self.assertIn("inline_string_placeholders", manifest["capabilities"]["templates"]["features"])
        self.assertIn("motion_preset_apply", manifest["capabilities"]["timeline"]["features"])
        self.assertEqual(manifest["capabilities"]["motion"]["catalog_version"], "0.1.0")
        self.assertIn("apply", manifest["capabilities"]["motion"]["features"])
        self.assertEqual(manifest["capabilities"]["motion"]["source"], "local-catalog")
        self.assertEqual(manifest["policies"]["jianying_runtime_enabled"], False)

    def test_effect_catalog_cli_is_local_and_queryable(self) -> None:
        code, result = invoke("effects", "list", "--query", "color")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["command"], "effects.list")
        self.assertEqual(result["data"]["source"], "ffmpeg-local")
        self.assertEqual(result["data"]["network"], "disabled")
        effect_ids = {item["id"] for item in result["data"]["effects"]}
        self.assertIn("color_levels", effect_ids)
        self.assertIn("color_contrast", effect_ids)
        self.assertIn("hsl", effect_ids)
        self.assertIn("rgb_curves", effect_ids)
        self.assertIn("color_wheel", effect_ids)

        code, catalog = invoke("effects", "list")
        self.assertEqual(code, 0, catalog)
        self.assertEqual(catalog["data"]["catalog_version"], "0.9.0")
        self.assertEqual(catalog["data"]["count"], 46)
        frame_interpolation = next(item for item in catalog["data"]["effects"] if item["id"] == "frame_interpolation")
        self.assertEqual(frame_interpolation["backend"], "ffmpeg:minterpolate")
        self.assertIn("fps", frame_interpolation["parameters"])

        code, inspected = invoke("effects", "inspect", "--name", "levels")
        self.assertEqual(code, 0, inspected)
        self.assertEqual(inspected["data"]["effect"]["id"], "color_levels")
        self.assertEqual(inspected["data"]["effect"]["backend"], "ffmpeg:colorlevels")
        self.assertIn("input_black", inspected["data"]["effect"]["parameters"])

        code, hsl = invoke("effects", "inspect", "--name", "hsl-adjust")
        self.assertEqual(code, 0, hsl)
        self.assertTrue(hsl["data"]["effect"]["keyframable"])
        self.assertIn("lightness", hsl["data"]["effect"]["parameters"])

        code, rejected = invoke("effects", "inspect", "--name", "remote-effect")
        self.assertEqual(code, 2)
        self.assertEqual(rejected["errors"][0]["code"], "ARGUMENT_INVALID")

    def test_motion_catalog_is_local_and_aliases_are_queryable(self) -> None:
        code, result = invoke("motion", "list", "--query", "zoom")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["command"], "motion.list")
        self.assertEqual(result["data"]["source"], "local-catalog")
        self.assertEqual(result["data"]["network"], "disabled")
        self.assertEqual({item["id"] for item in result["data"]["presets"]}, {"zoom_in", "zoom_out"})

        code, inspected = invoke("motion", "inspect", "--name", "push-in")
        self.assertEqual(code, 0, inspected)
        self.assertEqual(inspected["data"]["preset"]["id"], "zoom_in")
        self.assertEqual(inspected["data"]["preset"]["engine"], "timeline-keyframes")
        self.assertIn("transform.scale", inspected["data"]["preset"]["properties"])

        code, rejected = invoke("motion", "inspect", "--name", "remote-motion")
        self.assertEqual(code, 2)
        self.assertEqual(rejected["errors"][0]["code"], "ARGUMENT_INVALID")

    def test_motion_apply_writes_keyframes_snapshot_and_operation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-motion-apply-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            self.assertEqual(code, 0, ingested)
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "id": "motion_clip",
                "asset_id": ingested["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)

            code, applied = invoke(
                "motion", "apply", "--project", str(project), "--clip-id", "motion_clip",
                "--preset", "push-in", "--amount", "0.2", "--start-tick", "1000", "--end-tick", "80000",
            )
            self.assertEqual(code, 0, applied)
            self.assertEqual(applied["data"]["motion"]["preset"], "zoom_in")
            self.assertEqual(applied["data"]["motion"]["requested_preset"], "push-in")
            self.assertTrue(applied["data"]["before_snapshot"]["snapshot_id"])
            self.assertEqual(applied["data"]["validation"]["ok"], True)
            operation = json.loads((project / "operations" / f'{applied["operation_id"]}.json').read_text(encoding="utf-8"))
            self.assertEqual(operation["command"], "motion.apply")
            self.assertEqual(operation["motion"]["catalog_version"], "0.1.0")
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            clip = payload["sequences"][0]["tracks"][0]["clips"][0]
            scale_track = next(item for item in clip["keyframes"] if item["property"] == "transform.scale")
            self.assertEqual([item["at_tick"] for item in scale_track["keyframes"]], [1000, 80000])

            code, dry_run = invoke("motion", "apply", "--project", str(project), "--clip-id", "motion_clip", "--preset", "shake", "--dry-run")
            self.assertEqual(code, 0, dry_run)
            self.assertEqual(dry_run["status"], "planned")
            self.assertNotIn("transform.position.x", [item["property"] for item in clip["keyframes"]])

            code, invalid = invoke("motion", "apply", "--project", str(project), "--clip-id", "motion_clip", "--preset", "zoom-in", "--amount", "2")
            self.assertEqual(code, 2)
            self.assertEqual(invalid["errors"][0]["code"], "ARGUMENT_INVALID")
            code, invalid_points = invoke("motion", "apply", "--project", str(project), "--clip-id", "motion_clip", "--preset", "shake", "--points", "1")
            self.assertEqual(code, 2)
            self.assertEqual(invalid_points["errors"][0]["code"], "ARGUMENT_INVALID")

    def test_effect_parameter_whitelists_reject_filtergraph_injection(self) -> None:
        warnings = []
        filters = _effect_filters([
            {"type": "curves", "all": "0/0,format=yuv420p"},
            {"type": "rgb_curves", "red": "0/0,format=yuv420p"},
            {"type": "draw_box", "color": "white@0.8:format=yuv420p"},
            {"type": "tblend", "mode": "average:format=yuv420p"},
        ], warnings, "clip_security")
        self.assertEqual(len(filters), 2)
        self.assertIn("drawbox=", filters[0])
        self.assertEqual(filters[1], "tblend=all_mode=average")
        self.assertEqual([item["code"] for item in warnings], ["EFFECT_PARAMETER_INVALID"] * 4)

    def test_project_lut_library_registers_and_resolves_lut_id(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-lut-library-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            source = workspace / "neutral.cube"
            source.write_text(
                '\n'.join([
                    'TITLE "Neutral"',
                    "LUT_3D_SIZE 2",
                    "DOMAIN_MIN 0 0 0",
                    "DOMAIN_MAX 1 1 1",
                    "0 0 0", "0 0 1", "0 1 0", "0 1 1",
                    "1 0 0", "1 0 1", "1 1 0", "1 1 1",
                    "",
                ]),
                encoding="utf-8",
            )
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, registered = invoke(
                "lut", "register", "--project", str(project), "--input", str(source),
                "--lut-id", "lut_neutral", "--license-spdx", "CC0-1.0",
                "--verification-status", "verified",
            )
            self.assertEqual(code, 0, registered)
            self.assertEqual(registered["data"]["lut"]["id"], "lut_neutral")
            self.assertEqual(registered["data"]["lut"]["metadata"]["lut_3d_size"], 2)
            registered_path = project / "assets" / "luts" / "lut_neutral.cube"
            self.assertTrue(registered_path.exists())
            self.assertTrue((project / "assets" / "lut-library.json").exists())
            code, listed = invoke("lut", "list", "--project", str(project), "--query", "neutral")
            self.assertEqual(code, 0, listed)
            self.assertEqual(listed["data"]["count"], 1)
            code, inspected = invoke("lut", "inspect", "--project", str(project), "--lut-id", "lut_neutral")
            self.assertEqual(code, 0, inspected)
            self.assertTrue(inspected["data"]["exists"])
            self.assertTrue(inspected["data"]["hash_matches"])
            warnings: list[dict] = []
            filters = _effect_filters(
                [{"type": "lut3d", "parameters": {"lut_id": "lut_neutral"}}],
                warnings,
                "lut_clip",
                root=project,
            )
            self.assertEqual(warnings, [])
            self.assertEqual(len(filters), 1)
            self.assertIn("lut3d=file=", filters[0])
            self.assertIn("lut_neutral.cube", filters[0])
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(self.make_media(workspace)))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "effects": [{"type": "lut3d", "parameters": {"lut_id": "lut_neutral"}}],
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            code, validated = invoke("validate", "--project", str(project))
            self.assertEqual(code, 0, validated)
            registered_path.write_text(registered_path.read_text(encoding="utf-8") + "\n# changed after registration\n", encoding="utf-8")
            code, rejected = invoke("validate", "--project", str(project))
            self.assertEqual(code, 2, rejected)
            self.assertTrue(any(item.get("code") == "LUT_HASH_MISMATCH" for item in rejected["errors"]), rejected)

    def test_runtime_storage_is_local_to_product(self) -> None:
        paths = configure_local_runtime()
        self.assertEqual(Path(paths["root"]).resolve(), (ROOT / "product" / ".runtime").resolve())
        self.assertTrue(Path(paths["temp"]).is_dir())
        self.assertTrue(Path(paths["cache"]).is_dir())

    def test_cli_unicode_paths_and_progress_use_utf8_pipes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-utf8-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "广告项目🎬"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "product" / "src")
            env["PYTHONUTF8"] = "0"
            env["PYTHONIOENCODING"] = "ascii:strict"
            completed = subprocess.run(
                [sys.executable, "-m", "ai_ad_editor", "media", "ingest", "--project", str(project),
                 "--input", str(source), "--progress", "jsonl", "--request-id", "请求_中文路径🎬"],
                env=env, capture_output=True, timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8"))
            response = json.loads(completed.stdout.decode("utf-8"))
            self.assertTrue(response["ok"])
            self.assertEqual(response["request_id"], "请求_中文路径🎬")
            events = [json.loads(line) for line in completed.stderr.decode("utf-8").splitlines()]
            self.assertEqual([event["type"] for event in events], ["started", "completed"])
            self.assertEqual(events[0]["message"], "开始导入本地素材")
            self.assertTrue((project / "project.json").exists())

    def test_template_batch_creates_isolated_local_renders(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-batch-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            template = workspace / "template.json"
            template.write_text(json.dumps({"id": "batch.test", "version": "0.1.0", "variables": [{"name": "asset_id", "required": True}], "operations": [{"op": "append_clip", "track_id": "track_video_1", "asset_id": "{{asset_id}}", "source_in_tick": 0, "source_out_tick": 90000}]}), encoding="utf-8")
            variants = workspace / "variants.json"
            variants.write_text(json.dumps({"variants": [{"id": "hook-a", "variables": {"asset_id": asset_id}}, {"id": "hook-b", "variables": {"asset_id": asset_id}}]}), encoding="utf-8")
            output_root = project / "exports" / "batch"
            code, result = invoke("template", "batch", "--project", str(project), "--input", str(template), "--variables", str(variants), "--output", str(output_root))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["succeeded"], 2)
            for variant_id in ("hook-a", "hook-b"):
                self.assertTrue((output_root / variant_id / "project.json").exists())
                self.assertTrue((output_root / variant_id / "renders" / f"{variant_id}.mp4").exists())

    def test_rights_gate_blocks_unverified_publish(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-rights-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            self.assertEqual(code, 0)
            code, result = invoke("rights", "check", "--project", str(project))
            self.assertEqual(code, 7)
            self.assertFalse(result["ok"])
            self.assertTrue(result["data"]["failures"])

    def test_rights_revision_takedown_history_recovery_and_release_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-rights-revision-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, ingested = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--source-url", "local://source",
                "--license-spdx", "CC0-1.0", "--license-url", "local://license",
                "--evidence", "local://evidence", "--permitted-use", "commercial_ad",
            )
            self.assertEqual(code, 0, ingested)
            asset_id = ingested["data"]["asset"]["id"]

            code, listed = invoke("rights", "list", "--project", str(project))
            self.assertEqual(code, 0, listed)
            self.assertEqual(listed["data"]["count"], 1)
            self.assertEqual(listed["data"]["records"][0]["record_version"], 1)

            code, takedown = invoke("rights", "update", "--project", str(project), "--asset-id", asset_id, "--status", "takedown", "--reason", "notice received", "--actor", "reviewer")
            self.assertEqual(code, 0, takedown)
            self.assertTrue(takedown["data"]["snapshot"]["snapshot_id"])
            self.assertEqual(takedown["data"]["revision"]["record"]["record_version"], 2)
            self.assertEqual(takedown["data"]["revision"]["record"]["takedown_status"], "notice")

            code, history = invoke("rights", "history", "--project", str(project), "--asset-id", asset_id)
            self.assertEqual(code, 0, history)
            self.assertEqual(len(history["data"]["records"]), 2)
            self.assertTrue(history["data"]["events"])

            code, blocked = invoke("rights", "check", "--project", str(project))
            self.assertEqual(code, 7, blocked)
            self.assertTrue(any(item["code"] == "RIGHTS_STATUS_BLOCKED" for item in blocked["data"]["failures"]))

            code, reopen_required = invoke("rights", "update", "--project", str(project), "--asset-id", asset_id, "--status", "verified", "--reason", "try recovery")
            self.assertEqual(code, 2, reopen_required)
            self.assertEqual(reopen_required["errors"][0]["code"], "RIGHTS_REOPEN_REQUIRED")

            code, recovered = invoke(
                "rights", "update", "--project", str(project), "--asset-id", asset_id,
                "--status", "verified", "--reopen", "--reason", "notice cleared",
                "--evidence", "local://new-evidence",
            )
            self.assertEqual(code, 0, recovered)
            self.assertEqual(recovered["data"]["revision"]["record"]["record_version"], 3)
            self.assertEqual(recovered["data"]["revision"]["record"]["takedown_status"], "clear")

            code, allowed = invoke("rights", "check", "--project", str(project))
            self.assertEqual(code, 0, allowed)
            release = project / "exports" / "release.json"
            code, exported = invoke("rights", "export", "--project", str(project), "--output", str(release))
            self.assertEqual(code, 0, exported)
            self.assertTrue(release.exists())
            manifest = json.loads(release.read_text(encoding="utf-8"))
            self.assertTrue(manifest["rights_check"]["ok"])
            self.assertTrue(manifest["manifest_sha256"].startswith("sha256:"))
            self.assertEqual(manifest["assets"][0]["record_version"], 3)

    def test_rights_template_dependencies_batch_update_and_retract_impact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-rights-deps-") as raw:
            workspace = Path(raw)
            primary_source = self.make_media(workspace, "primary.mp4")
            parent_source = self.make_media(workspace, "parent.mp4")
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            ingest_args = [
                "--project", str(project), "--verification-status", "verified", "--source-url", "local://source",
                "--license-spdx", "CC0-1.0", "--license-url", "local://license", "--evidence", "local://evidence",
                "--permitted-use", "commercial_ad",
            ]
            _, primary = invoke("media", "ingest", "--input", str(primary_source), "--asset-id", "primary", *ingest_args)
            _, parent = invoke("media", "ingest", "--input", str(parent_source), "--asset-id", "parent", *ingest_args)
            primary_asset = primary["data"]["asset"]
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            project_payload["assets"] = [primary_asset]
            project_payload["templates"] = [{"id": "tpl-dependency", "version": "1.0.0", "assets": ["parent"]}]
            (project / "project.json").write_text(json.dumps(project_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            code, checked = invoke("rights", "check", "--project", str(project))
            self.assertEqual(code, 0, checked)
            self.assertEqual(checked["data"]["required_records"], 2)

            updates = workspace / "rights-updates.json"
            updates.write_text(json.dumps({"updates": [
                {"asset_id": "primary", "patch": {"notes": "batch reviewed"}, "reason": "batch review"},
                {"asset_id": "parent", "patch": {"notes": "batch reviewed"}, "reason": "batch review"},
            ]}), encoding="utf-8")
            code, batched = invoke("rights", "batch-update", "--project", str(project), "--input", str(updates))
            self.assertEqual(code, 0, batched)
            self.assertEqual(batched["data"]["count"], 2)

            release = project / "exports" / "dependency-release.json"
            code, exported = invoke("rights", "export", "--project", str(project), "--output", str(release))
            self.assertEqual(code, 0, exported)
            manifest = json.loads(release.read_text(encoding="utf-8"))
            self.assertEqual([item["asset_id"] for item in manifest["rights_dependencies"]], ["parent", "primary"])

            code, retracted = invoke("rights", "retract", "--project", str(project), "--asset-id", "parent", "--reason", "license notice")
            self.assertEqual(code, 0, retracted)
            self.assertTrue(any(item["path"] == "exports/dependency-release.json" for item in retracted["data"]["impacted_artifacts"]))
            code, impact = invoke("rights", "impact", "--project", str(project), "--asset-id", "parent")
            self.assertEqual(code, 0, impact)
            self.assertGreaterEqual(impact["data"]["count"], 1)
            code, blocked = invoke("rights", "check", "--project", str(project))
            self.assertEqual(code, 7, blocked)
            self.assertTrue(any(item["code"] == "RIGHTS_STATUS_BLOCKED" and item["context"] == "derived_dependency" for item in blocked["data"]["failures"]))

    def test_rights_disposition_decision_blocks_release_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-rights-disposition-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace, "historical.mp4")
            replacement_source = self.make_media(workspace, "replacement.mp4")
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            ingest_args = [
                "--project", str(project), "--verification-status", "verified", "--source-url", "local://source",
                "--license-spdx", "CC0-1.0", "--license-url", "local://license", "--evidence", "local://evidence",
                "--permitted-use", "commercial_ad",
            ]
            _, historical = invoke("media", "ingest", "--input", str(source), "--asset-id", "historical", *ingest_args)
            _, replacement = invoke("media", "ingest", "--input", str(replacement_source), "--asset-id", "replacement", *ingest_args)
            self.assertEqual(historical["data"]["asset"]["id"], "historical")
            self.assertEqual(replacement["data"]["asset"]["id"], "replacement")
            historical_artifact = project / "exports" / "historical-release.json"
            historical_artifact.write_text(json.dumps({"asset_id": "historical", "output": "renders/old.mp4"}), encoding="utf-8")
            historical_render = project / "renders" / "old.mp4"
            historical_render.write_bytes(source.read_bytes())
            original_artifact = historical_artifact.read_bytes()
            original_render = historical_render.read_bytes()
            decision_args = ("rights", "decide", "--project", str(project), "--asset-id", "historical", "--action", "replace", "--replacement-asset-id", "replacement", "--reason", "license replacement", "--actor", "reviewer")

            code, planned = invoke(*decision_args, "--status", "approved", "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertEqual(planned["status"], "planned")
            self.assertEqual(json.loads((project / "rights-ledger.json").read_text(encoding="utf-8"))["decisions"], [])

            code, orphan = invoke(*decision_args, "--status", "cancelled")
            self.assertEqual(code, 2, orphan)
            self.assertEqual(orphan["errors"][0]["code"], "RIGHTS_DISPOSITION_PREDECESSOR_REQUIRED")
            code, proposed = invoke(*decision_args)
            self.assertEqual(code, 0, proposed)
            proposed_id = proposed["data"]["decision"]["decision_id"]
            code, pending = invoke("rights", "check", "--project", str(project))
            self.assertEqual(code, 0, pending)
            self.assertTrue(any(item["code"] == "RIGHTS_DISPOSITION_PROPOSED" for item in pending["data"]["warnings"]))

            dependency_patch = workspace / "dependency-patch.json"
            dependency_patch.write_text(json.dumps({"derived_from": ["missing-parent"]}), encoding="utf-8")
            code, updated = invoke("rights", "update", "--project", str(project), "--asset-id", "replacement", "--patch", str(dependency_patch), "--reason", "dependency registration")
            self.assertEqual(code, 0, updated)
            ledger_before = (project / "rights-ledger.json").read_bytes()
            code, rejected = invoke(*decision_args, "--status", "approved", "--supersedes-decision-id", proposed_id)
            self.assertEqual(code, 7, rejected)
            self.assertEqual(rejected["errors"][0]["code"], "RIGHTS_REPLACEMENT_NOT_PUBLISHABLE")
            self.assertIn("missing-parent", rejected["errors"][0]["cause"])
            self.assertEqual((project / "rights-ledger.json").read_bytes(), ledger_before)
            dependency_patch.write_text(json.dumps({"derived_from": []}), encoding="utf-8")
            self.assertEqual(invoke("rights", "update", "--project", str(project), "--asset-id", "replacement", "--patch", str(dependency_patch), "--reason", "dependency corrected")[0], 0)

            code, decided = invoke(*decision_args, "--status", "approved", "--supersedes-decision-id", proposed_id)
            self.assertEqual(code, 0, decided)
            decision = decided["data"]["decision"]
            self.assertEqual(decision["action"], "replace")
            self.assertEqual(decision["status"], "approved")
            self.assertEqual(decision["supersedes"], proposed_id)
            self.assertEqual(decision["affected_artifacts"], proposed["data"]["decision"]["affected_artifacts"])
            self.assertTrue(any(item["path"] == "exports/historical-release.json" for item in decision["affected_artifacts"]))

            code, history = invoke("rights", "history", "--project", str(project), "--asset-id", "historical")
            self.assertEqual(code, 0, history)
            self.assertEqual(len(history["data"]["decisions"]), 2)
            self.assertEqual(history["data"]["effective_decisions"][0]["decision_id"], decision["decision_id"])
            code, blocked = invoke("rights", "check", "--project", str(project))
            self.assertEqual(code, 7, blocked)
            self.assertTrue(any(item["code"] == "RIGHTS_DISPOSITION_BLOCKED" for item in blocked["data"]["failures"]))
            release = project / "exports" / "disposition-release.json"
            code, exported = invoke("rights", "export", "--project", str(project), "--output", str(release))
            self.assertEqual(code, 7, exported)
            manifest = json.loads(release.read_text(encoding="utf-8"))
            self.assertEqual(manifest["rights_check"]["effective_disposition_decisions"][0]["decision_id"], decision["decision_id"])

            code, stale = invoke(*decision_args, "--status", "cancelled", "--supersedes-decision-id", proposed_id)
            self.assertEqual(code, 2, stale)
            self.assertEqual(stale["errors"][0]["code"], "RIGHTS_DISPOSITION_STALE")
            code, mismatch = invoke(*decision_args, "--status", "cancelled", "--supersedes-decision-id", decision["decision_id"], "--target", "all")
            self.assertEqual(code, 2, mismatch)
            self.assertEqual(mismatch["errors"][0]["code"], "RIGHTS_DISPOSITION_SCOPE_MISMATCH")
            code, downgrade = invoke(*decision_args, "--status", "proposed", "--supersedes-decision-id", decision["decision_id"])
            self.assertEqual(code, 2, downgrade)
            self.assertEqual(downgrade["errors"][0]["code"], "RIGHTS_DISPOSITION_TRANSITION_INVALID")
            code, cancelled = invoke(*decision_args, "--status", "cancelled", "--supersedes-decision-id", decision["decision_id"])
            self.assertEqual(code, 0, cancelled)
            code, cleared = invoke("rights", "check", "--project", str(project))
            self.assertEqual(code, 0, cleared)
            self.assertEqual(cleared["data"]["warnings"], [])
            code, history = invoke("rights", "history", "--project", str(project), "--asset-id", "historical")
            self.assertEqual(code, 0, history)
            self.assertEqual(len(history["data"]["decisions"]), 3)
            self.assertEqual(history["data"]["effective_decisions"][0]["status"], "cancelled")
            self.assertEqual(historical_artifact.read_bytes(), original_artifact)
            self.assertEqual(historical_render.read_bytes(), original_render)

            code, deleted = invoke("rights", "decide", "--project", str(project), "--asset-id", "historical", "--action", "delete", "--status", "approved", "--reason", "historical deletion plan")
            self.assertEqual(code, 0, deleted)
            self.assertEqual(invoke("rights", "check", "--project", str(project))[0], 7)
            self.assertEqual(historical_render.read_bytes(), original_render)

    def test_ingest_dry_run_does_not_change_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-dry-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--dry-run")
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "planned")
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project_json["assets"], [])
            self.assertFalse(list((project / "assets").iterdir()))

    def test_rights_disposition_apply_updates_current_timeline_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-rights-apply-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace, "historical.mp4")
            replacement_source = self.make_media(workspace, "replacement.mp4")
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            ingest_args = [
                "--project", str(project), "--verification-status", "verified", "--source-url", "local://source",
                "--license-spdx", "CC0-1.0", "--license-url", "local://license", "--evidence", "local://evidence",
                "--permitted-use", "commercial_ad",
            ]
            historical = invoke("media", "ingest", "--input", str(source), "--asset-id", "historical", *ingest_args)[1]
            replacement = invoke("media", "ingest", "--input", str(replacement_source), "--asset-id", "replacement", *ingest_args)[1]
            self.assertEqual(historical["data"]["asset"]["id"], "historical")
            self.assertEqual(replacement["data"]["asset"]["id"], "replacement")
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{"op": "append_clip", "track_id": "track_video_1", "asset_id": "historical", "source_in_tick": 0, "source_out_tick": 90000}]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            historical_artifact = project / "exports" / "historical-release.json"
            historical_artifact.write_text(json.dumps({"asset_id": "historical", "output": "renders/old.mp4"}), encoding="utf-8")
            historical_render = project / "renders" / "old.mp4"
            historical_render.write_bytes(source.read_bytes())
            original_artifact = historical_artifact.read_bytes()
            original_render = historical_render.read_bytes()
            code, decided = invoke("rights", "decide", "--project", str(project), "--asset-id", "historical", "--action", "replace", "--replacement-asset-id", "replacement", "--status", "approved", "--reason", "replace current project references")
            self.assertEqual(code, 0, decided)
            decision_id = decided["data"]["decision"]["decision_id"]
            project_before = (project / "project.json").read_bytes()
            code, planned = invoke("rights", "apply", "--project", str(project), "--decision-id", decision_id, "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertEqual(planned["status"], "planned")
            self.assertEqual((project / "project.json").read_bytes(), project_before)
            code, applied = invoke("rights", "apply", "--project", str(project), "--decision-id", decision_id)
            self.assertEqual(code, 0, applied)
            updated = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual({item["id"] for item in updated["assets"]}, {"replacement"})
            clips = [clip for sequence in updated["sequences"] for track in sequence["tracks"] for clip in track["clips"]]
            self.assertEqual([clip["asset_id"] for clip in clips], ["replacement"])
            self.assertEqual(invoke("rights", "check", "--project", str(project))[0], 0)
            self.assertEqual(historical_artifact.read_bytes(), original_artifact)
            self.assertEqual(historical_render.read_bytes(), original_render)
            ledger = json.loads((project / "rights-ledger.json").read_text(encoding="utf-8"))
            self.assertTrue(any(item.get("event") == "disposition_applied" and item.get("decision_id") == decision_id for item in ledger["events"]))

    def test_project_bound_idempotency_replays_and_rejects_conflict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-idempotency-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            first_code, first = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--idempotency-key", "ingest-1")
            self.assertEqual(first_code, 0, first)
            second_code, second = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--idempotency-key", "ingest-1")
            self.assertEqual(second_code, 0, second)
            self.assertEqual(first["operation_id"], second["operation_id"])
            self.assertTrue(any(item.get("code") == "IDEMPOTENT_REPLAY" for item in second["warnings"]))
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(len(project_json["assets"]), 1)
            conflict_code, conflict = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--license-spdx", "CC0-1.0", "--idempotency-key", "ingest-1")
            self.assertEqual(conflict_code, 2, conflict)
            self.assertEqual(conflict["errors"][0]["code"], "IDEMPOTENCY_CONFLICT")

    def test_project_init_dry_run_and_agent_export_import(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-convert-") as raw:
            workspace = Path(raw)
            planned = workspace / "planned"
            code, result = invoke("project", "init", str(planned), "--dry-run")
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "planned")
            self.assertFalse(planned.exists())
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            exported = workspace / "exported.json"
            code, result = invoke("convert", "export", "--project", str(project), "--output", str(exported))
            self.assertEqual(code, 0, result)
            imported = workspace / "imported"
            code, result = invoke("convert", "import", "--input", str(exported), "--output", str(imported))
            self.assertEqual(code, 0, result)
            self.assertTrue((imported / "project.json").exists())

    def test_published_json_schema_rejects_invalid_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-schema-") as raw:
            project = Path(raw) / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            del project_json["settings"]
            (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
            code, result = invoke("validate", "--project", str(project))
            self.assertEqual(code, 2, result)
            self.assertEqual(result["data"]["schema_engine"], "jsonschema")
            self.assertTrue(any(item["code"] == "SCHEMA_VALIDATION_FAILED" for item in result["errors"]))

    def test_bezier_control_points_are_schema_and_semantically_validated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-bezier-validation-") as raw:
            project = Path(raw) / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            project_json["sequences"][0]["tracks"][0]["clips"].append({
                "id": "clip_bezier",
                "sequence_id": "seq_main",
                "timeline_start_tick": 0,
                "duration_tick": 1,
                "source_in_tick": 0,
                "source_out_tick": 1,
                "keyframes": [{
                    "property": "transform.scale",
                    "keyframes": [{"at_tick": 0, "value": 0.8, "interpolation": "bezier", "control_points": [1.2, 0.4, 0.8, 0.9]}],
                }],
            })
            (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
            code, result = invoke("validate", "--project", str(project))
            self.assertEqual(code, 2, result)
            self.assertTrue(any(item["code"] == "BEZIER_CONTROL_POINT_RANGE" for item in result["errors"]))

    def test_bezier_keyframe_expression_preserves_value_endpoints(self) -> None:
        """Cubic easing must interpolate the property range exactly once."""
        clip = {
            "keyframes": [{
                "property": "transform.scale",
                "keyframes": [
                    {"at_tick": 0, "value": 2.0, "interpolation": "bezier", "control_points": [0.0, 0.2, 0.8, 1.0]},
                    {"at_tick": 90000, "value": 4.0, "interpolation": "linear"},
                ],
            }],
        }
        expression = _keyframe_expr(clip, ("transform.scale",), 1.0, 0.0, 90000, time_variable="t")
        decoded = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", f"aevalsrc=exprs={_expr_arg(expression)}:s=1000:d=1",
                "-f", "f32le", "pipe:1",
            ],
            capture_output=True,
        )
        self.assertEqual(decoded.returncode, 0, decoded.stderr.decode("utf-8", "replace"))
        samples = memoryview(decoded.stdout).cast("f")
        self.assertGreater(len(samples), 900)
        self.assertAlmostEqual(samples[0], 2.0, delta=0.02)
        self.assertAlmostEqual(samples[-1], 4.0, delta=0.02)
        self.assertTrue(2.0 < samples[500] < 4.0, samples[500])

    def test_transform_anchor_changes_layer_placement_and_is_keyframable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-anchor-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000,
                "transform": {"position": {"x": 0.5, "y": 0.5}, "scale": 0.5, "anchor": {"x": 0.0, "y": 0.0}},
                "keyframes": [{"property": "transform.anchor.x", "keyframes": [
                    {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                    {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                ]}],
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "anchor.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180", "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("w*(if(lt", graph)
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project_payload["sequences"][0]["tracks"][0]["clips"][0]["transform"]["anchor"]["x"], 0.0)
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            frame = workspace / "anchor.png"
            completed = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "0.5", "-i", str(output), "-frames:v", "1", str(frame)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            with Image.open(frame) as image:
                self.assertGreater(image.convert("RGB").getpixel((170, 100))[0], 150)
            project_payload["sequences"][0]["tracks"][0]["clips"][0]["transform"]["rotation"] = 45.0
            (project / "project.json").write_text(json.dumps(project_payload), encoding="utf-8")
            code, rotated_plan = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180", "--dry-run")
            self.assertEqual(code, 0, rotated_plan)
            self.assertIn("abs(", rotated_plan["data"]["plan"]["filter_complex"])
            code, rotated_render = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rotated_render)
            project_payload["sequences"][0]["tracks"][0]["clips"][0]["transform"]["anchor"]["x"] = 1.1
            (project / "project.json").write_text(json.dumps(project_payload), encoding="utf-8")
            code, invalid = invoke("validate", "--project", str(project))
            self.assertNotEqual(code, 0, invalid)
            self.assertIn("TRANSFORM_ANCHOR_RANGE", json.dumps(invalid, ensure_ascii=False))

    def test_template_snapshot_applies_local_change_set(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-template-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            template = workspace / "template.json"
            template.write_text(json.dumps({"id": "tpl.test", "version": "0.1.0", "variables": [{"name": "asset_id", "required": True}], "operations": [{"op": "append_clip", "track_id": "track_video_1", "asset_id": "{{asset_id}}", "source_in_tick": 0, "source_out_tick": 90000}]}), encoding="utf-8")
            variables = workspace / "variables.json"
            variables.write_text(json.dumps({"asset_id": asset_id}), encoding="utf-8")
            code, result = invoke("template", "apply", "--project", str(project), "--input", str(template), "--variables", str(variables))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["template_snapshot"]["id"], "tpl.test")
            self.assertEqual(len(result["data"]["applied"]), 1)

    def test_template_variables_are_typed_inline_and_non_mutating(self) -> None:
        template = {
            "id": "typed.test",
            "version": "0.2.0",
            "variables": [
                {"name": "headline", "type": "string", "required": True, "min_length": 2},
                {"name": "accent", "type": "color", "default": "#ffffff"},
                {"name": "aspect", "type": "enum", "values": ["vertical", "square"]},
                {"name": "zoom", "type": "number", "default": 1.0, "min": 0.5, "max": 2.0},
            ],
            "operations": [{"op": "add_marker", "label": "{{headline}} / {{aspect}}"}],
        }
        variables = {"headline": "Sale", "aspect": "vertical", "zoom": 1.25}
        resolved = instantiate(template, variables)
        self.assertEqual(variables, {"headline": "Sale", "aspect": "vertical", "zoom": 1.25})
        self.assertEqual(resolved["operations"][0]["label"], "Sale / vertical")
        self.assertEqual(resolved["template_snapshot"]["variables"]["accent"], "#ffffff")
        self.assertEqual(resolved["template_snapshot"]["variables"]["zoom"], 1.25)
        with self.assertRaises(ValueError):
            instantiate(template, {"headline": "x", "aspect": "vertical"})
        with self.assertRaises(ValueError):
            instantiate(template, {"headline": "Sale", "aspect": "landscape"})

    def test_template_operations_replace_slots_and_add_markers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-template-ops-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingested["data"]["asset"]["id"]
            template = workspace / "template.json"
            template.write_text(json.dumps({
                "id": "slot-ops.test",
                "version": "0.2.0",
                "variables": [
                    {"name": "asset_id", "type": "asset", "required": True},
                    {"name": "headline", "type": "string", "required": True},
                    {"name": "marker_tick", "type": "integer", "default": 45000},
                ],
                "operations": [
                    {"op": "append_clip", "id": "slot", "track_id": "track_video_1", "asset_id": "{{asset_id}}", "source_in_tick": 0, "source_out_tick": 90000},
                    {"op": "update_clip", "clip_id": "slot", "patch": {"subtitle": {"text": "{{headline}}"}, "transform": {"scale": 0.8}}},
                    {"op": "replace_clip", "clip_id": "slot", "asset_id": "{{asset_id}}"},
                    {"op": "add_marker", "id": "hook", "at_tick": "{{marker_tick}}", "label": "{{headline}}"},
                ],
            }), encoding="utf-8")
            variables = workspace / "variables.json"
            variables.write_text(json.dumps({"asset_id": asset_id, "headline": "Local sale"}), encoding="utf-8")
            code, result = invoke("template", "apply", "--project", str(project), "--input", str(template), "--variables", str(variables))
            self.assertEqual(code, 0, result)
            self.assertEqual([item["op"] for item in result["data"]["applied"]], ["append_clip", "update_clip", "replace_clip", "add_marker"])
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            clip = project_payload["sequences"][0]["tracks"][0]["clips"][0]
            self.assertEqual(clip["subtitle"]["text"], "Local sale")
            self.assertEqual(clip["transform"]["scale"], 0.8)
            self.assertEqual(project_payload["sequences"][0]["markers"][0]["at_tick"], 45000)
            template_variables = {item["name"]: item["value"] for item in project_payload["templates"][0]["variables"]}
            self.assertEqual(template_variables["marker_tick"], 45000)

    def test_image_clip_renders_with_local_loop(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-image-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://image", "--license-spdx", "CC0-1.0", "--evidence", "local://image")
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000}]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "image.mp4"
            code, result = invoke("render", "--project", str(project), "--publish", "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())

    def test_keyframes_effects_subtitle_and_audio_automation_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-effects-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://effects", "--license-spdx", "CC0-1.0", "--evidence", "local://effects")
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "transform": {"position": {"x": 0.5, "y": 0.5}}, "keyframes": [{"property": "transform.scale", "keyframes": [{"at_tick": 0, "value": 0.8, "interpolation": "bezier", "control_points": [0.2, 0.82, 0.8, 0.98]}, {"at_tick": 90000, "value": 1.0, "interpolation": "linear"}]}], "effects": [{"type": "grayscale"}], "subtitle": {"text": "Local ad", "style": {"fontsize": 36, "line_spacing": 8, "borderw": 2, "bordercolor": "black", "shadowx": 2, "shadowy": 2, "shadowcolor": "black@0.7", "text_align": "center+middle", "boxborderw": 14, "text_shaping": True, "fix_bounds": True, "expansion": "none", "animation": {"type": "slide_up", "duration": 0.25, "distance": 80}}}, "transition_in": {"type": "fade", "duration": 0.1}},
                {"op": "append_clip", "track_id": "track_audio_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "audio": {"volume": 0.5, "fade_in": 0.1, "fade_out": 0.1, "equalizer": {"frequency": 1000, "gain": 2, "width": 1}, "highpass": 60, "lowpass": 18000}}
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "effects.mp4"
            code, result = invoke("render", "--project", str(project), "--publish", "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            warnings = result["data"]["warnings"]
            self.assertEqual([item["feature"] for item in warnings], ["subtitle_inline_dynamic_color"])
            self.assertEqual(warnings[0]["code"], "RENDER_FEATURE_APPROXIMATE")

    def test_extended_effects_and_typewriter_subtitle_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-effects-extended-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://extended-effects", "--license-spdx", "CC0-1.0", "--evidence", "local://extended-effects")
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "effects": [
                    {"type": "posterize", "levels": 8},
                    {"type": "color_temperature", "kelvin": 7200},
                    {"type": "deband", "threshold": 0.02, "range": 8},
                ],
                "speed_curve": {"keyframes": [{"at_tick": 0, "speed": 1.0}, {"at_tick": 45000, "speed": 2.0, "interpolation": "linear"}, {"at_tick": 90000, "speed": 1.0}]},
                "subtitle": {"text": "Type", "style": {"fontsize": 32, "animation": {"type": "typewriter", "duration": 0.4}}},
            }, {
                "op": "append_clip", "track_id": "track_audio_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "speed_curve": {"keyframes": [{"at_tick": 0, "speed": 1.0}, {"at_tick": 45000, "speed": 2.0, "interpolation": "linear"}, {"at_tick": 90000, "speed": 1.0}]},
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "extended-effects.mp4"
            code, result = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            unsupported = [item for item in result["data"]["warnings"] if item.get("code") == "RENDER_FEATURE_UNSUPPORTED"]
            self.assertEqual(unsupported, [])
            self.assertTrue(any(item.get("feature") == "audio_speed_curve_piecewise" for item in result["data"]["warnings"]))

    def test_native_effect_catalog_filters_render_without_unsupported_warning(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-native-effects-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://native-effects", "--license-spdx", "CC0-1.0", "--evidence", "local://native-effects")
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "effects": [
                    {"type": "exposure", "amount": 0.15},
                    {"type": "color_levels", "input_black": 0.02, "output_white": 0.96},
                    {"type": "curves", "all": "0/0 0.5/0.45 1/1"},
                    {"type": "hsl", "hue": 12, "saturation": 1.1, "lightness": 0.05},
                    {"type": "rgb_curves", "all": "0/0 1/1", "red": "0/0 0.5/0.6 1/1", "green": "0/0 1/1", "blue": "0/0 0.45/0.4 1/1"},
                    {"type": "color_wheel", "shadows_red": 0.05, "midtones_blue": -0.04, "highlights_green": 0.03, "preserve_luma": True},
                    {"type": "hqdn3d", "luma_spatial": 2.0},
                    {"type": "smartblur", "radius": 0.6, "strength": 0.4},
                    {"type": "avgblur", "size_x": 1, "size_y": 1},
                    {"type": "tmix", "frames": 2},
                    {"type": "tblend", "mode": "average"},
                    {"type": "lens_correction", "k1": 0.01, "k2": -0.01},
                    {"type": "draw_box", "x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8, "color": "white@0.35", "thickness": 2},
                    {"type": "color_contrast", "red": 0.1, "preserve_luma": 0.25},
                    {"type": "solarize", "threshold": 220},
                    {"type": "threshold", "value": 8},
                    {"type": "deflicker", "size": 3},
                    {"type": "dctdnoiz", "sigma": 0.2},
                    {"type": "frame_interpolation", "fps": 48, "mi_mode": "blend", "scd": "fdiff"},
                ],
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "native-effects.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertIn("exposure=", planned["data"]["plan"]["filter_complex"])
            self.assertIn("curves=all=", planned["data"]["plan"]["filter_complex"])
            self.assertIn("hue=h=", planned["data"]["plan"]["filter_complex"])
            self.assertIn("colorbalance=rs=", planned["data"]["plan"]["filter_complex"])
            self.assertIn("minterpolate=fps=48.000000:mi_mode=blend", planned["data"]["plan"]["filter_complex"])
            self.assertNotIn("RENDER_FEATURE_UNSUPPORTED", {item.get("code") for item in planned["data"]["plan"]["warnings"]})
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertNotIn("RENDER_FEATURE_UNSUPPORTED", {item.get("code") for item in rendered["data"]["warnings"]})

    def test_effect_parameter_keyframes_render_with_frame_evaluation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-effect-keyframes-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://effect-keyframes", "--license-spdx", "CC0-1.0",
                "--evidence", "local://effect-keyframes",
            )
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "effects": [{
                    "type": "brightness", "parameters": {"amount": 0.0},
                    "keyframes": [{"property": "amount", "keyframes": [
                        {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 0.7, "interpolation": "ease_in_out"},
                    ]}],
                }, {
                    "type": "hsl", "parameters": {"hue": 0.0, "saturation": 1.0, "lightness": 0.0},
                    "keyframes": [{"property": "saturation", "keyframes": [
                        {"at_tick": 0, "value": 1.0, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 1.25, "interpolation": "linear"},
                    ]}],
                }],
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "effect-keyframes.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("eq=brightness='", graph)
            self.assertIn("hue=h=", graph)
            self.assertIn(":s='", graph)
            self.assertIn(":eval=frame", graph)
            self.assertEqual(planned["data"]["plan"]["warnings"], [])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)

            def center_luma(at_seconds: float) -> float:
                completed = subprocess.run(
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at_seconds), "-i", str(output),
                        "-frames:v", "1", "-vf", "crop=100:100:490:910,format=gray", "-f", "rawvideo", "-",
                    ], capture_output=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
                self.assertGreater(len(completed.stdout), 0)
                return sum(completed.stdout) / len(completed.stdout)

            self.assertGreater(center_luma(0.85), center_luma(0.10) + 15.0)

    def test_sequence_adjustment_stack_applies_after_track_composite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-sequence-adjustment-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            project_payload["settings"]["adjustments"] = [{
                "id": "global_grade",
                "effects": [{
                    "type": "brightness",
                    "parameters": {"amount": 0.0},
                    "keyframes": [{"property": "amount", "keyframes": [
                        {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 0.7, "interpolation": "linear"},
                    ]}],
                }],
            }]
            (project / "project.json").write_text(json.dumps(project_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            output = project / "renders" / "sequence-adjustment.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180", "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("null[vout]", graph)
            self.assertIn("eq=brightness='", graph)
            self.assertEqual(planned["data"]["plan"]["warnings"], [])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

            def center_luma(at_seconds: float) -> float:
                completed = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at_seconds), "-i", str(output),
                     "-frames:v", "1", "-vf", "crop=100:100:110:40,format=gray", "-f", "rawvideo", "-"],
                    capture_output=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
                self.assertGreater(len(completed.stdout), 0)
                return sum(completed.stdout) / len(completed.stdout)

            self.assertGreater(center_luma(0.85), center_luma(0.10) + 15.0)

    def test_interval_adjustment_layer_reassembles_sequence_clock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-interval-adjustment-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            project_payload["settings"]["adjustments"] = [{
                "id": "mid_grade",
                "start_tick": 36000,
                "duration_tick": 27000,
                "effects": [{"type": "brightness", "parameters": {"amount": 0.7}}],
            }]
            (project / "project.json").write_text(json.dumps(project_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            output = project / "renders" / "interval-adjustment.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180", "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("trim=start=0.400000:end=0.700000", graph)
            self.assertIn("concat=n=3:v=1:a=0", graph)
            self.assertEqual(planned["data"]["plan"]["warnings"], [])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)

            def center_luma(at_seconds: float) -> float:
                completed = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at_seconds), "-i", str(output),
                     "-frames:v", "1", "-vf", "crop=100:100:110:40,format=gray", "-f", "rawvideo", "-"],
                    capture_output=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
                self.assertGreater(len(completed.stdout), 0)
                return sum(completed.stdout) / len(completed.stdout)

            before = center_luma(0.20)
            during = center_luma(0.55)
            after = center_luma(0.90)
            self.assertGreater(during, before + 15.0)
            self.assertLess(abs(after - before), 8.0)

    def test_project_local_lut3d_is_validated_and_rendered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-lut-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            lut_path = project / "luts" / "red.cube"
            lut_path.parent.mkdir(parents=True, exist_ok=True)
            lut_path.write_text(
                'TITLE "Solid Red"\nLUT_3D_SIZE 2\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n'
                + "\n".join(["1.0 0.0 0.0"] * 8) + "\n",
                encoding="utf-8",
            )
            invalid_changes = workspace / "invalid-lut.json"
            invalid_changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "effects": [{"type": "lut3d", "parameters": {"path": "https://example.invalid/look.cube"}}],
            }]}), encoding="utf-8")
            code, rejected = invoke("timeline", "compose", "--project", str(project), "--input", str(invalid_changes))
            self.assertEqual(code, 2, rejected)
            self.assertIn("LUT_PATH_NETWORK", rejected["errors"][0].get("cause", ""))

            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "effects": [{"type": "lut3d", "parameters": {"path": "luts/red.cube", "interpolation": "tetrahedral"}}],
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "lut.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertEqual(rendered["data"]["warnings"], [])
            frame = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                capture_output=True,
            )
            self.assertEqual(frame.returncode, 0, frame.stderr.decode("utf-8", errors="replace"))
            center = (90 * 320 + 160) * 3
            self.assertGreater(frame.stdout[center], 180)
            self.assertLess(frame.stdout[center + 1], 90)

            # Static partial strength is materialized as a deterministic
            # project-local identity-mixed CUBE and remains renderable through
            # the same single-input FFmpeg lut3d chain.
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            project_payload["sequences"][0]["tracks"][0]["clips"][0]["effects"][0]["parameters"]["intensity"] = 0.5
            (project / "project.json").write_text(json.dumps(project_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            half_output = project / "renders" / "lut-half.mp4"
            code, half_rendered = invoke("render", "--project", str(project), "--output", str(half_output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, half_rendered)
            self.assertTrue(any(item.get("feature") == "lut_intensity" for item in half_rendered["data"]["warnings"]))
            self.assertTrue((project / "cache" / "luts").exists())
            half_frame = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(half_output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                capture_output=True,
            )
            self.assertEqual(half_frame.returncode, 0, half_frame.stderr.decode("utf-8", errors="replace"))
            self.assertGreater(half_frame.stdout[center], 70)
            self.assertGreater(half_frame.stdout[center + 1], 50)

            project_payload["sequences"][0]["tracks"][0]["clips"][0]["effects"][0]["parameters"]["intensity"] = 1.1
            (project / "project.json").write_text(json.dumps(project_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            code, invalid = invoke("validate", "--project", str(project))
            self.assertEqual(code, 2, invalid)
            self.assertTrue(any(item.get("code") == "LUT_INTENSITY_INVALID" for item in invalid["errors"]))

    def test_10bit_pixel_format_and_color_metadata_reach_ffmpeg_plan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-10bit-output-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "10bit.mp4"
            code, planned = invoke(
                "render", "--project", str(project), "--output", str(output),
                "--profile", "custom", "--width", "320", "--height", "180",
                "--pixel-format", "yuv420p10le", "--dry-run",
            )
            self.assertEqual(code, 0, planned)
            command = planned["data"]["plan"]["command"]
            self.assertIn("yuv420p10le", command)
            self.assertIn("-color_primaries", command)
            self.assertIn("bt709", command)
            self.assertIn("-color_trc", command)
            self.assertIn("-colorspace", command)
            self.assertIn("-color_range", command)
            code, rendered = invoke(
                "render", "--project", str(project), "--output", str(output),
                "--profile", "custom", "--width", "320", "--height", "180",
                "--pixel-format", "yuv420p10le",
            )
            self.assertEqual(code, 0, rendered)
            self.assertEqual(probe_media(output)["video"]["pix_fmt"], "yuv420p10le")

    def test_transparent_webm_output_uses_project_alpha_canvas(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-alpha-output-") as raw:
            workspace = Path(raw)
            source = workspace / "overlay.png"
            Image.new("RGBA", (64, 64), (255, 0, 0, 96)).save(source)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://alpha", "--license-spdx", "CC0-1.0", "--evidence", "local://alpha")
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "alpha.webm"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "64", "--height", "64", "--container", "webm", "--video-codec", "libvpx-vp9", "--audio-codec", "libopus", "--pixel-format", "yuva420p", "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertIn("yuva420p", planned["data"]["plan"]["command"])
            self.assertIn("color=c=black@0.0", planned["data"]["plan"]["filter_complex"])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "64", "--height", "64", "--container", "webm", "--video-codec", "libvpx-vp9", "--audio-codec", "libopus", "--pixel-format", "yuva420p")
            self.assertEqual(code, 0, rendered)
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream_tags=alpha_mode", "-of", "json", str(output)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertEqual(json.loads(probe.stdout)["streams"][0]["tags"].get("alpha_mode"), "1")

    def test_hdr_tone_map_chain_is_local_and_renders(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-hdr-tonemap-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            project_payload["settings"]["color"].update({
                "tone_map": "hable",
                "input_transfer": "smpte2084",
                "input_primaries": "bt2020",
                "input_matrix": "bt2020nc",
                "input_range": "limited",
                "tone_map_desat": 0.5,
            })
            (project / "project.json").write_text(json.dumps(project_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            output = project / "renders" / "tonemapped.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180", "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("zscale=rin=tv:pin=bt2020:tin=smpte2084", graph)
            self.assertIn("tonemap=tonemap=hable", graph)
            self.assertEqual(planned["data"]["plan"]["warnings"], [])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

    def test_reverse_speed_curve_reflects_ramp_without_approximation_warning(self) -> None:
        segments = [(0.0, 0.25, 1.0, 1.0), (0.25, 0.75, 2.0, 2.0), (0.75, 1.0, 4.0, 4.0)]
        self.assertEqual(_reverse_speed_curve_segments(segments), [
            (0.0, 0.25, 4.0, 4.0),
            (0.25, 0.75, 2.0, 2.0),
            (0.75, 1.0, 1.0, 1.0),
        ])
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-reverse-speed-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            curve = {"keyframes": [
                {"at_tick": 0, "speed": 1.0, "interpolation": "hold"},
                {"at_tick": 22500, "speed": 2.0, "interpolation": "hold"},
                {"at_tick": 67500, "speed": 4.0, "interpolation": "hold"},
                {"at_tick": 90000, "speed": 4.0, "interpolation": "hold"},
            ]}
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000, "speed_curve": curve, "reverse": True,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            code, planned = invoke("render", "--project", str(project), "--output", str(project / "renders" / "reverse.mp4"), "--dry-run")
            self.assertEqual(code, 0, planned)
            warnings = planned["data"]["plan"]["warnings"]
            self.assertFalse(any(item.get("feature") == "speed_curve_reverse" for item in warnings))
            authored = json.loads((project / "project.json").read_text(encoding="utf-8-sig"))
            self.assertEqual(authored["sequences"][0]["tracks"][0]["clips"][0]["duration_tick"], 50625)
            code, rendered = invoke("render", "--project", str(project), "--output", str(project / "renders" / "reverse.mp4"))
            self.assertEqual(code, 0, rendered)
            self.assertTrue((project / "renders" / "reverse.mp4").exists())
            probe = json.loads(subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                "-show_entries", "stream=nb_read_frames,duration", "-of", "json",
                str(project / "renders" / "reverse.mp4"),
            ], capture_output=True, check=True).stdout)["streams"][0]
            self.assertEqual(int(probe["nb_read_frames"]), 17)
            self.assertLessEqual(abs(float(probe["duration"]) - .5625), 1 / 30)

    def test_speed_curve_with_nonzero_source_in_uses_clip_local_clock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-speed-source-in-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 45000, "source_out_tick": 90000,
                "speed_curve": {"keyframes": [{"at_tick": 0, "speed": 1.0}, {"at_tick": 45000, "speed": 1.0}]},
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "source-in-speed.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            inputs = planned["data"]["plan"]["inputs"]
            clock = next(item["video_frame_clock"] for item in inputs
                         if item.get("asset_id") == asset_id and "video_frame_clock" in item)
            self.assertEqual(clock["protocol"], "rational-local-video-clock-v1")
            self.assertEqual(clock["source_clock_anchor"], "requested-author-source-in-tick")
            self.assertEqual(clock["source_in_tick"], 45000)
            self.assertTrue(clock["source_prefix_preserved_for_covering_frame"])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertAlmostEqual(probe_media(output)["duration_seconds"], 0.5, delta=0.12)

    def test_word_timing_subtitle_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-word-timing-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://word-timing", "--license-spdx", "CC0-1.0", "--evidence", "local://word-timing")
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000,
                "subtitle": {"text": "hello world", "word_timing": [{"text": "hello", "start": 0.0, "end": 0.35}, {"text": "world", "start": 0.35, "end": 0.8}], "style": {"fontsize": 34, "max_width": 160, "active_color": "yellow"}},
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "word-timing.mp4"
            code, result = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("code") == "RENDER_FEATURE_UNSUPPORTED" for item in result["data"]["warnings"]))

    def test_independent_subtitle_track_and_rotation_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-text-track-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000},
                {"op": "add_track", "track_id": "track_titles", "kind": "subtitle", "order": 3},
                {"op": "append_clip", "track_id": "track_titles", "id": "headline", "generator": {"type": "text"}, "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000, "transform": {"position": {"x": 0.65, "y": 0.42}, "scale": 0.82, "rotation": 8, "opacity": 0.9}, "mask": {"type": "circle", "cx": 0.5, "cy": 0.5, "radius": 0.48}, "blend": {"mode": "screen", "opacity": 0.85}, "transition_in": {"type": "fade", "duration": 0.2}, "transition_out": {"type": "dissolve", "duration": 0.2}, "subtitle": {"text": "Local title", "style": {"fontsize": 34, "box": False, "x": "(w-text_w)/2", "y": "(h-text_h)/2"}, "animation": {"type": "rotate", "from_degrees": -30, "to_degrees": 15, "duration": 0.4}}},
                {"op": "add_track", "track_id": "track_foreground", "kind": "video", "order": 5},
                {"op": "append_clip", "track_id": "track_foreground", "id": "foreground", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000, "transform": {"position": {"x": 0.5, "y": 0.5}, "scale": 0.22}},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "text-track.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("subtitlecanvas0", graph)
            self.assertIn("subtitle_affine0", graph)
            self.assertIn("subtitle_mask0_0", graph)
            self.assertIn("subtitle_blendcanvas0", graph)
            self.assertIn("subtitle_transition_opacity0", graph)
            self.assertIn("st(0,cos(", graph)
            self.assertIn("drawtext=text='Local title'", graph)
            self.assertLess(graph.index("[base][v0]overlay"), graph.index("subtitle_blendcanvas0"))
            self.assertLess(graph.index("subtitle_blendcanvas0"), graph.rindex("[v1]overlay"))
            self.assertNotIn("subtitle_animation:rotate", " ".join(str(item) for item in planned.get("warnings", [])))
            self.assertNotIn("subtitle_transition", " ".join(str(item) for item in planned.get("warnings", [])))
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

    def test_independent_subtitle_spatial_transitions_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-text-spatial-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000},
                {"op": "add_track", "track_id": "track_titles", "kind": "subtitle", "order": 3},
                {"op": "append_clip", "track_id": "track_titles", "id": "spatial-title", "generator": {"type": "text"}, "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000, "transition_in": {"type": "slide", "direction": "left", "duration": 0.25}, "transition_out": {"type": "wipe", "direction": "right", "duration": 0.25}, "subtitle": {"text": "Spatial title", "style": {"fontsize": 34, "box": False, "x": "(w-text_w)/2", "y": "(h-text_h)/2"}}},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "spatial-text.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("subtitle_transition_opacity0", graph)
            self.assertIn("W+w", graph)
            self.assertIn("lt(X,W*(clip", graph)
            self.assertFalse(any(item.get("feature") == "subtitle_transition" for item in planned.get("warnings", [])), planned)
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

    def test_text_only_subtitle_sequence_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-text-only-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_track", "track_id": "track_titles", "kind": "subtitle", "order": 3},
                {"op": "append_clip", "track_id": "track_titles", "id": "title_card", "generator": {"type": "text"}, "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000, "subtitle": {"text": "Text only", "style": {"fontsize": 34, "box": False, "x": "(w-text_w)/2", "y": "(h-text_h)/2"}}},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "text-only.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertNotIn("VIDEO_TRACK_EMPTY", json.dumps(planned, ensure_ascii=False))
            self.assertIn("drawtext=text=", planned["data"]["plan"]["filter_complex"])
            self.assertIn("Text only", planned["data"]["plan"]["filter_complex"])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

    def test_local_object_tracking_report_and_keyframe_apply(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-tracking-") as raw:
            workspace = Path(raw)
            source = workspace / "moving-object.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:r=12:d=1",
                    "-f", "lavfi", "-i", "color=c=white:s=36x36:r=12:d=1",
                    "-filter_complex", "overlay=x='20+80*t':y=55:eval=frame:shortest=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "id": "track_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            report_path = project / "validation" / "tracking.json"
            code, tracked = invoke(
                "media", "track", "--project", str(project), "--asset-id", asset_id,
                "--roi", "0.05,0.28,0.14,0.24", "--clip-id", "track_clip", "--output", str(report_path),
            )
            self.assertEqual(code, 0, tracked)
            self.assertTrue(report_path.exists())
            self.assertGreaterEqual(len(tracked["data"]["result"]["frames"]), 2)
            trajectory = tracked["data"]["result"]["frames"]
            self.assertGreater(trajectory[-1]["x"], trajectory[0]["x"] + 0.08)
            self.assertIn("transform.position.x", tracked["data"]["applied_properties"])
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            clip = project_json["sequences"][0]["tracks"][0]["clips"][0]
            self.assertTrue(any(item.get("property") == "transform.position.x" for item in clip.get("keyframes", [])))
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)

    def test_command_json_visual_tracking_adapter_runs_local_protocol(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-command-json-tracking-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            model = workspace / "tracking-model.bin"
            model.write_bytes(b"local tracking model fixture v1")
            runner = workspace / "tracking-runner.py"
            runner.write_text(
                """import json
import sys

request = json.loads(sys.stdin.read())
assert request[\"protocol\"] == \"agent-video-object-tracking-v1\"
assert request[\"network\"] == \"disabled\"
print(json.dumps({
    \"protocol\": \"agent-video-object-tracking-v1\",
    \"status\": \"ok\",
    \"engine\": \"fixture-local-tracker\",
    \"frames\": [
        {\"at_seconds\": 0.0, \"x\": 0.25, \"y\": 0.5, \"width\": 0.2, \"height\": 0.3, \"confidence\": 0.97},
        {\"at_seconds\": 0.5, \"x\": 0.42, \"y\": 0.5, \"width\": 0.2, \"height\": 0.3, \"confidence\": 0.91}
    ],
    \"metadata\": {\"fixture\": True}
}))
""",
                encoding="utf-8",
            )
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            code, registered = invoke(
                "media", "adapter", "register", "--project", str(project), "--adapter-id", "fixture_tracker",
                "--engine", "command-json-tracking-v1", "--model-path", str(model), "--executable", str(runner),
                "--license-spdx", "CC0-1.0", "--verification-status", "verified", "--evidence", "local://fixture-tracker",
            )
            self.assertEqual(code, 0, registered)
            self.assertEqual(registered["data"]["adapter"]["output_contract"], "tracking_frames_v1")
            code, listed = invoke("media", "adapter", "list", "--project", str(project))
            self.assertEqual(code, 0, listed)
            self.assertTrue(listed["data"]["adapters"][0]["verification"]["ok"])
            report_path = project / "validation" / "command-json-tracking.json"
            code, tracked = invoke(
                "media", "track", "--project", str(project), "--asset-id", asset_id,
                "--adapter-id", "fixture_tracker", "--roi", "0.1,0.3,0.2,0.3", "--end-seconds", "0.8",
                "--output", str(report_path),
            )
            self.assertEqual(code, 0, tracked)
            self.assertEqual(tracked["data"]["result"]["engine"], "command-json-tracking-v1")
            self.assertEqual(tracked["data"]["result"]["protocol"], "agent-video-object-tracking-v1")
            self.assertEqual(tracked["data"]["result"]["runner"]["metadata"]["fixture"], True)
            self.assertEqual(tracked["warnings"][0]["code"], "TRACKING_EXTERNAL_REVIEW")
            self.assertEqual(len(tracked["data"]["result"]["keyframes"]), 2)
            self.assertTrue(report_path.exists())

    def test_command_json_multi_object_tracking_supports_selection_and_apply_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-command-json-multi-tracking-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            model = workspace / "multi-tracking-model.bin"
            model.write_bytes(b"local multi object tracking model fixture v1")
            runner = workspace / "multi-tracking-runner.py"
            runner.write_text(
                """import json
import sys

request = json.loads(sys.stdin.read())
assert request["protocol"] == "agent-video-object-tracking-v2"
assert request["engine"] == "command-json-tracking-multi-v1"
assert request["network"] == "disabled"
selected = request["selection"]["object_id"]
assert request["selection"]["all_objects"] == (selected is None)
print(json.dumps({
    "protocol": "agent-video-object-tracking-v2",
    "status": "ok",
    "engine": "fixture-local-multi-tracker",
    "objects": [
        {"object_id": "person_1", "label": "person", "frames": [
            {"at_seconds": 0.0, "x": 0.20, "y": 0.40, "width": 0.20, "height": 0.30, "confidence": 0.97, "rotation_degrees": 0.0},
            {"at_seconds": 0.5, "x": 0.30, "y": 0.40, "width": 0.20, "height": 0.30, "confidence": 0.93, "rotation_degrees": 4.0}
        ], "metadata": {"fixture": "person-1"}},
        {"object_id": "person_2", "label": "person", "frames": [
            {"at_seconds": 0.0, "x": 0.60, "y": 0.40, "width": 0.18, "height": 0.28, "confidence": 0.94},
            {"at_seconds": 0.5, "x": 0.55, "y": 0.40, "width": 0.18, "height": 0.28, "confidence": 0.90}
        ], "metadata": {"fixture": "person-2"}}
    ],
    "metadata": {"fixture": True}
}))
""",
                encoding="utf-8",
            )
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_track", "track_id": "track_titles", "kind": "subtitle", "order": 3},
                {"op": "append_clip", "track_id": "track_video_1", "id": "multi_video", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_titles", "id": "multi_title", "generator": {"type": "text"}, "source_in_tick": 0, "source_out_tick": 90000, "subtitle": {"text": "Multi", "style": {"fontsize": 30}}},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            code, registered = invoke(
                "media", "adapter", "register", "--project", str(project), "--adapter-id", "fixture_multi_tracker",
                "--engine", "command-json-tracking-multi-v1", "--model-path", str(model), "--executable", str(runner),
                "--license-spdx", "CC0-1.0", "--verification-status", "verified", "--evidence", "local://fixture-multi-tracker",
            )
            self.assertEqual(code, 0, registered)
            self.assertEqual(registered["data"]["adapter"]["output_contract"], "tracking_objects_v1")
            self.assertEqual(registered["data"]["adapter"]["protocol"], "agent-video-object-tracking-v2")
            report_path = project / "validation" / "multi-tracking.json"
            code, tracked = invoke(
                "media", "track", "--project", str(project), "--asset-id", asset_id,
                "--adapter-id", "fixture_multi_tracker", "--roi", "0.1,0.3,0.2,0.3", "--object-id", "person_2",
                "--clip-id", "multi_video", "--track-id", "track_video_1", "--output", str(report_path),
            )
            self.assertEqual(code, 0, tracked)
            result = tracked["data"]["result"]
            self.assertEqual(result["protocol"], "agent-video-object-tracking-v2")
            self.assertEqual(result["object_count"], 2)
            self.assertEqual(result["object_id"], "person_2")
            self.assertEqual(len(result["frames"]), 2)
            self.assertEqual(tracked["warnings"][0]["code"], "TRACKING_MULTI_OBJECT_REVIEW")
            self.assertTrue(report_path.exists())
            code, all_objects = invoke(
                "media", "track", "--project", str(project), "--asset-id", asset_id,
                "--adapter-id", "fixture_multi_tracker", "--roi", "0.1,0.3,0.2,0.3", "--all-objects",
            )
            self.assertEqual(code, 0, all_objects)
            self.assertEqual(len(all_objects["data"]["result"]["objects"]), 2)
            self.assertIsNone(all_objects["data"]["result"]["object_id"])
            code, bound = invoke(
                "media", "track-bind", "--project", str(project), "--asset-id", asset_id,
                "--adapter-id", "fixture_multi_tracker", "--object-id", "person_1", "--roi", "0.1,0.3,0.2,0.3",
                "--target-clip-id", "multi_title", "--target-track-id", "track_titles", "--apply",
            )
            self.assertEqual(code, 0, bound)
            self.assertEqual(bound["data"]["plan"]["object_id"], "person_1")
            code, reframed = invoke(
                "media", "reframe", "--project", str(project), "--asset-id", asset_id,
                "--adapter-id", "fixture_multi_tracker", "--object-id", "person_1", "--roi", "0.1,0.3,0.2,0.3",
                "--clip-id", "multi_video", "--track-id", "track_video_1", "--apply",
            )
            self.assertEqual(code, 0, reframed)
            self.assertEqual(reframed["data"]["plan"]["object_id"], "person_1")
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)

    def test_local_tracking_binds_to_independent_text_clip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-track-bind-") as raw:
            workspace = Path(raw)
            source = workspace / "moving-object.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:r=12:d=1",
                    "-f", "lavfi", "-i", "color=c=white:s=36x36:r=12:d=1",
                    "-filter_complex", "overlay=x='20+80*t':y=55:eval=frame:shortest=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_track", "track_id": "track_titles", "kind": "subtitle", "order": 3},
                {"op": "append_clip", "track_id": "track_titles", "id": "bound_title", "generator": {"type": "text"}, "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000, "subtitle": {"text": "Tracked", "style": {"fontsize": 34}}},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            report_path = project / "validation" / "track-bind.json"
            code, bound = invoke(
                "media", "track-bind", "--project", str(project), "--asset-id", asset_id,
                "--roi", "0.05,0.28,0.14,0.24", "--target-clip-id", "bound_title",
                "--target-track-id", "track_titles", "--scale-mode", "roi", "--apply",
                "--output", str(report_path),
            )
            self.assertEqual(code, 0, bound)
            self.assertTrue(report_path.exists())
            self.assertTrue(bound["data"]["applied"])
            self.assertEqual(bound["data"]["before_snapshot"]["label"], "before-track-bind")
            self.assertIn("transform.position.x", [item["property"] for item in bound["data"]["plan"]["keyframes"]])
            self.assertIn("transform.scale", [item["property"] for item in bound["data"]["plan"]["keyframes"]])
            saved = json.loads((project / "project.json").read_text(encoding="utf-8"))
            title_track = next(track for track in saved["sequences"][0]["tracks"] if track["id"] == "track_titles")
            title_clip = title_track["clips"][0]
            properties = {item["property"] for item in title_clip.get("keyframes", [])}
            self.assertEqual(properties, {"transform.position.x", "transform.position.y", "transform.scale"})
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)

    def test_local_auto_reframe_applies_target_aspect_crop_keyframes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-reframe-") as raw:
            workspace = Path(raw)
            source = workspace / "moving-object.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:r=12:d=1",
                    "-f", "lavfi", "-i", "color=c=white:s=36x36:r=12:d=1",
                    "-filter_complex", "overlay=x='20+80*t':y=55:eval=frame:shortest=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
                ], capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "id": "reframe_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            report_path = project / "validation" / "reframe.json"
            code, applied = invoke(
                "media", "reframe", "--project", str(project), "--asset-id", asset_id,
                "--roi", "0.05,0.28,0.14,0.24", "--clip-id", "reframe_clip", "--track-id", "track_video_1",
                "--output", str(report_path), "--apply",
            )
            self.assertEqual(code, 0, applied)
            self.assertTrue(applied["data"]["before_snapshot"]["snapshot_id"])
            self.assertEqual(applied["data"]["plan"]["fit"], "fill")
            self.assertGreaterEqual(applied["data"]["plan"]["frames"], 2)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            clip = project_json["sequences"][0]["tracks"][0]["clips"][0]
            self.assertEqual(clip["crop"]["unit"], "normalized")
            crop_tracks = {item["property"]: item["keyframes"] for item in clip["keyframes"] if str(item.get("property", "")).startswith("crop.")}
            self.assertEqual(set(crop_tracks), {"crop.x", "crop.y", "crop.width", "crop.height"})
            self.assertGreater(crop_tracks["crop.x"][-1]["value"], crop_tracks["crop.x"][0]["value"])
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)
            output = project / "renders" / "reframe.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

    def test_nested_sequence_render_and_cycle_rejection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-nested-sequence-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://nested", "--license-spdx", "CC0-1.0", "--evidence", "local://nested")
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_sequence", "id": "seq_nested", "name": "Nested", "duration_tick": 90000},
                {"op": "append_clip", "sequence_id": "seq_nested", "track_id": "seq_nested_video_1", "id": "nested_a", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 45000, "duration_tick": 45000, "mask": {"type": "circle", "cx": 0.5, "cy": 0.5, "radius": 0.42}},
                {"op": "append_clip", "sequence_id": "seq_nested", "track_id": "seq_nested_video_1", "id": "nested_b", "asset_id": asset_id, "source_in_tick": 45000, "source_out_tick": 90000, "timeline_start_tick": 45000, "duration_tick": 45000, "mask": {"type": "circle", "cx": 0.5, "cy": 0.5, "radius": 0.42}},
                {"op": "append_sequence_clip", "sequence_id": "seq_main", "track_id": "track_video_1", "nested_sequence_id": "seq_nested", "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000, "reverse": True, "mask": {"type": "rectangle", "x": 0.08, "y": 0.08, "width": 0.84, "height": 0.84}, "transform": {"position": {"x": 0.7, "y": 0.5}, "scale": 0.5}, "keyframes": [{"property": "transform.scale", "keyframes": [{"at_tick": 0, "value": 1.0, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.75, "interpolation": "linear"}]}], "effects": [{"type": "grayscale"}]},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "nested.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("feature") == "nested_sequence_inherited_properties" for item in rendered["data"]["warnings"]))
            self.assertFalse(any(item.get("feature") == "nested_sequence_reverse" for item in rendered["data"]["warnings"]))
            self.assertFalse(any(item.get("feature") == "nested_sequence_multiple_masks" for item in rendered["data"]["warnings"]))
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            nested = next(item for item in project_json["sequences"] if item["id"] == "seq_nested")
            nested["tracks"][0]["clips"].append({"id": "cycle", "sequence_id": "seq_main", "timeline_start_tick": 0, "duration_tick": 1, "source_in_tick": 0, "source_out_tick": 1})
            (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
            code, rejected = invoke("validate", "--project", str(project))
            self.assertEqual(code, 2, rejected)
            self.assertTrue(any(item.get("code") == "SEQUENCE_CYCLE" for item in rejected["errors"]))

    def test_nested_sequence_speed_and_parent_rotation_are_composed(self) -> None:
        project = {
            "sequences": [
                {
                    "id": "seq_main", "duration_tick": 90000,
                    "tracks": [{"id": "main_video", "kind": "video", "order": 0, "clips": [{
                        "id": "nested", "sequence_id": "seq_child", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 180000,
                        "speed": 2.0, "transform": {"position": {"x": 0.5, "y": 0.5}, "rotation": 90.0},
                        "keyframes": [{"property": "transform.scale", "keyframes": [
                            {"at_tick": 0, "value": 1.0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": 0.5, "interpolation": "linear"},
                        ]}],
                    }]}],
                },
                {
                    "id": "seq_child", "duration_tick": 180000,
                    "tracks": [{"id": "child_video", "kind": "video", "order": 0, "clips": [
                        {
                            "id": "child_clip_a", "asset_id": "asset", "timeline_start_tick": 0,
                            "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                            "transform": {"position": {"x": 0.75, "y": 0.5}, "scale": 0.5},
                        },
                        {
                            "id": "child_clip_b", "asset_id": "asset", "timeline_start_tick": 90000,
                            "duration_tick": 90000, "source_in_tick": 90000, "source_out_tick": 180000,
                            "transform": {"position": {"x": 0.75, "y": 0.5}, "scale": 0.5},
                        },
                    ]}],
                },
            ],
        }
        warnings: list[dict] = []
        flattened = _flatten_sequence_tracks(project, project["sequences"][0], warnings)
        clips = next(track["clips"] for track in flattened if track["clips"])
        self.assertEqual(len(clips), 2)
        first, second = clips
        self.assertEqual((first["source_in_tick"], first["source_out_tick"], first["duration_tick"]), (0, 90000, 45000))
        self.assertEqual((second["source_in_tick"], second["source_out_tick"], second["duration_tick"]), (90000, 180000, 45000))
        self.assertAlmostEqual(first["speed"], 2.0, places=6)
        self.assertAlmostEqual(second["speed"], 2.0, places=6)
        for clip in clips:
            self.assertAlmostEqual(clip["transform"]["position"]["x"], 0.75, places=6)
            self.assertAlmostEqual(clip["transform"]["position"]["y"], 0.5, places=6)
            self.assertAlmostEqual(clip["transform"].get("rotation", 0.0), 0.0, places=6)
            self.assertAlmostEqual(clip["transform"]["scale"], 0.5, places=6)
            self.assertAlmostEqual(clip["_nested_parent_transform"]["rotation"], 90.0, places=6)
            self.assertTrue(any(item.get("property") == "nested.parent.transform.scale" for item in clip["keyframes"]))
        first_scale = next(item for item in first["keyframes"] if item.get("property") == "nested.parent.transform.scale")["keyframes"]
        second_scale = next(item for item in second["keyframes"] if item.get("property") == "nested.parent.transform.scale")["keyframes"]
        self.assertEqual([item["at_tick"] for item in first_scale], [0, 90000])
        self.assertEqual([item["at_tick"] for item in second_scale], [-45000, 45000])
        self.assertEqual([item["value"] for item in second_scale], [1.0, 0.5])
        self.assertIn("clip(", _transform_exprs(second, 45000 / 90000, 90000)["scale"])
        self.assertFalse(any(item.get("feature") == "nested_sequence_speed_curve" for item in warnings))

    def test_nested_reverse_reverses_parent_bezier_easing(self) -> None:
        project = {
            "sequences": [
                {
                    "id": "seq_main", "duration_tick": 90000,
                    "tracks": [{"id": "main_video", "kind": "video", "order": 0, "clips": [{
                        "id": "nested", "sequence_id": "seq_child", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                        "reverse": True,
                        "transform": {"scale": 1.0},
                        "keyframes": [{"property": "transform.scale", "keyframes": [
                            {"at_tick": 0, "value": 0.8, "interpolation": "bezier", "control_points": [0.1, 0.2, 0.7, 0.9]},
                            {"at_tick": 90000, "value": 1.2, "interpolation": "linear"},
                        ]}],
                    }]}],
                },
                {
                    "id": "seq_child", "duration_tick": 90000,
                    "tracks": [{"id": "child_video", "kind": "video", "order": 0, "clips": [{
                        "id": "child_clip", "asset_id": "asset", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                        "keyframes": [{"property": "transform.scale", "keyframes": [
                            {"at_tick": 0, "value": 0.8, "interpolation": "bezier", "control_points": [0.1, 0.2, 0.7, 0.9]},
                            {"at_tick": 90000, "value": 1.2, "interpolation": "linear"},
                        ]}],
                    }]}],
                },
            ],
        }
        warnings: list[dict] = []
        flattened = _flatten_sequence_tracks(project, project["sequences"][0], warnings)
        leaf = next(track["clips"][0] for track in flattened if track["clips"])
        track = next(item for item in leaf["keyframes"] if item.get("property") == "nested.parent.transform.scale")
        points = sorted(track["keyframes"], key=lambda item: item["at_tick"])
        self.assertEqual([item["at_tick"] for item in points], [0, 90000])
        self.assertEqual(len(points[1]["control_points"]), 4)
        for actual, expected in zip(points[1]["control_points"], [0.3, 0.1, 0.9, 0.8]):
            self.assertAlmostEqual(actual, expected, places=9)
        leaf_track = next(item for item in leaf["keyframes"] if item.get("property") == "transform.scale")
        leaf_points = sorted(leaf_track["keyframes"], key=lambda item: item["at_tick"])
        self.assertEqual([item["at_tick"] for item in leaf_points], [0, 90000])
        for actual, expected in zip(leaf_points[1]["control_points"], [0.3, 0.1, 0.9, 0.8]):
            self.assertAlmostEqual(actual, expected, places=9)
        self.assertFalse(any(item.get("feature") == "nested_sequence_reverse_keyframes" for item in warnings))

    def test_nested_sequence_speed_curve_maps_source_boundaries(self) -> None:
        project = {
            "sequences": [
                {
                    "id": "seq_main", "duration_tick": 124766,
                    "tracks": [{"id": "main_video", "kind": "video", "order": 0, "clips": [{
                        "id": "nested", "sequence_id": "seq_child", "timeline_start_tick": 0,
                        "duration_tick": 124766, "source_in_tick": 0, "source_out_tick": 180000,
                        "speed_curve": {"keyframes": [
                            {"at_tick": 0, "speed": 1.0},
                            {"at_tick": 90000, "speed": 2.0, "interpolation": "linear"},
                            {"at_tick": 180000, "speed": 1.0},
                        ]},
                    }]}],
                },
                {
                    "id": "seq_child", "duration_tick": 180000,
                    "tracks": [{"id": "child_video", "kind": "video", "order": 0, "clips": [
                        {"id": "child_all", "asset_id": "asset", "timeline_start_tick": 0, "duration_tick": 180000, "source_in_tick": 0, "source_out_tick": 180000},
                    ]}],
                },
            ],
        }
        warnings: list[dict] = []
        flattened = _flatten_sequence_tracks(project, project["sequences"][0], warnings)
        clips = sorted(next(track["clips"] for track in flattened if track["clips"]), key=lambda item: item["timeline_start_tick"])
        self.assertEqual([(clip["timeline_start_tick"], clip["duration_tick"]) for clip in clips], [(0, 62383), (62383, 62383)])
        self.assertEqual([(clip["source_in_tick"], clip["source_out_tick"]) for clip in clips], [(0, 90000), (90000, 180000)])
        self.assertEqual(len({clip["id"] for clip in clips}), 2)
        self.assertTrue(all(abs(clip["speed"] - 1.4427007358) < 1e-6 for clip in clips))
        self.assertTrue(all(clip.get('_nested_time_maps') for clip in clips))
        self.assertFalse(any(item.get("feature") == "nested_sequence_speed_curve_piecewise" for item in warnings))
        self.assertFalse(any(item.get("feature") == "nested_sequence_speed_curve" for item in warnings))

    def test_nested_sequence_speed_curve_renders_locally(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-nested-speed-curve-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://nested-speed-curve", "--license-spdx", "CC0-1.0", "--evidence", "local://nested-speed-curve")
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_sequence", "id": "seq_speed_child", "name": "Speed child", "duration_tick": 90000},
                {"op": "append_clip", "sequence_id": "seq_speed_child", "track_id": "seq_speed_child_video_1", "id": "child_a", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 45000, "duration_tick": 45000},
                {"op": "append_clip", "sequence_id": "seq_speed_child", "track_id": "seq_speed_child_video_1", "id": "child_b", "asset_id": asset_id, "source_in_tick": 45000, "source_out_tick": 90000, "timeline_start_tick": 45000, "duration_tick": 45000},
                {"op": "append_sequence_clip", "sequence_id": "seq_main", "track_id": "track_video_1", "nested_sequence_id": "seq_speed_child", "id": "nested_speed", "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 62383, "speed_curve": {"keyframes": [{"at_tick": 0, "speed": 1.0}, {"at_tick": 45000, "speed": 2.0, "interpolation": "linear"}, {"at_tick": 90000, "speed": 1.0}]}}
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "nested-speed-curve.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("feature") == "nested_sequence_speed_curve_piecewise" for item in rendered["data"]["warnings"]))
            self.assertFalse(any(item.get('code') == 'NESTED_SOURCE_CFR_NORMALIZED' for item in rendered['data']['warnings']))
            manifest = json.loads(Path(rendered['data']['manifest']).read_text(encoding='utf-8'))

            def native_clocks(value):
                if isinstance(value, dict):
                    if 'video_frame_clock' in value:
                        yield value['video_frame_clock']
                    for child in value.values():
                        yield from native_clocks(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from native_clocks(child)

            clocks = [clock for clock in native_clocks(manifest)
                      if clock.get('source_clock_anchor') == 'original-native-intervals-before-nested-author-map']
            self.assertEqual(len(clocks), 2)
            self.assertTrue(all(clock['native_source_intervals']['protocol'] == 'covering-native-source-half-open-v1'
                                for clock in clocks))

    def test_nested_sequence_reverse_preserves_temporal_order(self) -> None:
        project = {
            "sequences": [
                {
                    "id": "seq_main", "duration_tick": 90000,
                    "tracks": [{"id": "main_video", "kind": "video", "order": 0, "clips": [{
                        "id": "nested", "sequence_id": "seq_child", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 180000,
                        "speed": 2.0, "reverse": True,
                    }]}],
                },
                {
                    "id": "seq_child", "duration_tick": 180000,
                    "tracks": [{"id": "child_video", "kind": "video", "order": 0, "clips": [
                        {"id": "child_a", "asset_id": "asset", "timeline_start_tick": 0, "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000},
                        {"id": "child_b", "asset_id": "asset", "timeline_start_tick": 90000, "duration_tick": 90000, "source_in_tick": 90000, "source_out_tick": 180000},
                    ]}],
                },
            ],
        }
        warnings: list[dict] = []
        flattened = _flatten_sequence_tracks(project, project["sequences"][0], warnings)
        clips = sorted(next(track["clips"] for track in flattened if track["clips"]), key=lambda item: item["timeline_start_tick"])
        self.assertEqual([clip["id"] for clip in clips], ["nested.child_b", "nested.child_a"])
        self.assertEqual([(clip["timeline_start_tick"], clip["source_in_tick"], clip["source_out_tick"]) for clip in clips], [(0, 90000, 180000), (45000, 0, 90000)])
        self.assertTrue(all(clip.get("reverse") for clip in clips))
        self.assertFalse(any(item.get("feature") == "nested_sequence_reverse" for item in warnings))

        partial_project = json.loads(json.dumps(project))
        partial_parent = partial_project["sequences"][0]["tracks"][0]["clips"][0]
        partial_parent["source_in_tick"] = 45000
        partial_parent["source_out_tick"] = 135000
        partial_parent["speed"] = 1.0
        partial_warnings: list[dict] = []
        partial_flattened = _flatten_sequence_tracks(partial_project, partial_project["sequences"][0], partial_warnings)
        partial_clips = sorted(next(track["clips"] for track in partial_flattened if track["clips"]), key=lambda item: item["timeline_start_tick"])
        self.assertEqual([(clip["timeline_start_tick"], clip["source_in_tick"], clip["source_out_tick"]) for clip in partial_clips], [(0, 90000, 135000), (45000, 45000, 90000)])
        self.assertTrue(all(clip.get("reverse") for clip in partial_clips))

    def test_nested_sequence_multiple_keyframed_parents_keep_global_clock(self) -> None:
        project = {
            "sequences": [
                {
                    "id": "seq_main", "duration_tick": 90000,
                    "tracks": [{"id": "main_video", "kind": "video", "order": 0, "clips": [{
                        "id": "outer", "sequence_id": "seq_child", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                        "transform": {"position": {"x": 0.65, "y": 0.5}, "scale": 1.0},
                        "keyframes": [{"property": "transform.scale", "keyframes": [
                            {"at_tick": 0, "value": 1.0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": 0.8, "interpolation": "linear"},
                        ]}],
                    }]}],
                },
                {
                    "id": "seq_child", "duration_tick": 90000,
                    "tracks": [{"id": "child_video", "kind": "video", "order": 0, "clips": [{
                        "id": "inner", "sequence_id": "seq_grandchild", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                        "transform": {"position": {"x": 0.5, "y": 0.5}, "rotation": 10.0},
                        "keyframes": [{"property": "transform.rotation", "keyframes": [
                            {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": 45.0, "interpolation": "linear"},
                        ]}],
                    }]}],
                },
                {
                    "id": "seq_grandchild", "duration_tick": 90000,
                    "tracks": [{"id": "grandchild_video", "kind": "video", "order": 0, "clips": [{
                        "id": "leaf", "asset_id": "asset", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                    }]}],
                },
            ],
        }
        warnings: list[dict] = []
        flattened = _flatten_sequence_tracks(project, project["sequences"][0], warnings)
        leaf = next(clip for track in flattened for clip in track["clips"] if clip["id"].endswith("leaf"))
        layers = leaf["_nested_parent_transforms"]
        self.assertEqual(len(layers), 2)
        self.assertFalse(any(item.get("feature") == "nested_sequence_multiple_parent_keyframes" for item in warnings))
        scale_track = next(item for item in leaf["keyframes"] if item.get("property") == "nested.parent.0.transform.scale")
        rotation_track = next(item for item in leaf["keyframes"] if item.get("property") == "nested.parent.1.transform.rotation")
        self.assertEqual([item["at_tick"] for item in scale_track["keyframes"]], [0, 90000])
        self.assertEqual([item["at_tick"] for item in rotation_track["keyframes"]], [0, 90000])
        expressions = _transform_exprs(leaf, 0.5, 90000)
        self.assertIn("-0.20000000", expressions["scale"])
        self.assertIn("45.00000000", expressions["rotation"])

    def test_mask_and_blend_compositing_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-composite-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://composite", "--license-spdx", "CC0-1.0", "--evidence", "local://composite")
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_track", "id": "track_video_2", "kind": "video", "order": 1},
                {"op": "add_track", "id": "track_video_3", "kind": "video", "order": 2},
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "mask": {"type": "ellipse", "cx": 0.5, "cy": 0.5, "rx": 0.45, "ry": 0.35, "feather": 0.02}, "keyframes": [{"property": "mask.cx", "keyframes": [{"at_tick": 0, "value": 0.5, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.55, "interpolation": "linear"}]}]},
                {"op": "append_clip", "track_id": "track_video_2", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "blend": {"mode": "multiply", "opacity": 0.65}},
                {"op": "append_clip", "track_id": "track_video_3", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "mask": {"type": "path", "points": [[0.15, 0.2], [0.85, 0.2], [0.5, 0.85]]}},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            progress_stderr = io.StringIO()
            with contextlib.redirect_stderr(progress_stderr):
                code, result = invoke("render", "--project", str(project), "--output", str(project / "renders" / "composite.mp4"), "--progress", "jsonl")
            self.assertEqual(code, 0, result)
            self.assertTrue((project / "renders" / "composite.mp4").exists())
            self.assertFalse(any(item.get("feature", "").startswith("mask:") for item in result["data"]["warnings"]))
            events = [json.loads(line) for line in progress_stderr.getvalue().splitlines() if line.strip()]
            self.assertTrue({"render_started", "artifact_written", "completed"}.issubset({event["type"] for event in events}), events)

    def test_mask_keyframes_and_feather_change_pixels(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-mask-pixels-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "timeline_start_tick": 45000, "source_in_tick": 0, "source_out_tick": 90000,
                "transform": {"opacity": 0.5},
                "mask": {"type": "circle", "cx": 0.2, "cy": 0.5, "radius": 0.18, "feather": 0.04,
                         "keyframes": [{"property": "cy", "keyframes": [{"at_tick": 0, "value": 0.5, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.6, "interpolation": "linear"}]}]},
                "keyframes": [{"property": "mask.cx", "keyframes": [{"at_tick": 0, "value": 0.2, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.8, "interpolation": "linear"}]}],
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "animated-mask.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertFalse(any(item.get("feature") == "mask_feather" for item in rendered["warnings"]))

            def frame(at: float) -> bytes:
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                self.assertEqual(len(result.stdout), 320 * 180 * 3)
                return result.stdout

            early, late = frame(0.5), frame(1.3)
            red_early = early[0::3]
            red_late = late[0::3]
            center_early = sum((i % 320) * value for i, value in enumerate(red_early)) / sum(red_early)
            center_late = sum((i % 320) * value for i, value in enumerate(red_late)) / sum(red_late)
            self.assertGreater(center_late - center_early, 130)
            # Alpha survives masking, the edge is feathered and pixels outside
            # the mask stay black. These assertions inspect the decoded output.
            self.assertTrue(100 <= red_early[90 * 320 + 64] <= 155)
            self.assertTrue(20 <= red_early[90 * 320 + 96] <= 100)
            self.assertLess(red_early[90 * 320 + 130], 15)

    def test_dynamic_polygon_mask_keyframes_change_pixels(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-polygon-mask-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            points = [[0.08, 0.18], [0.42, 0.18], [0.25, 0.82]]
            tracks = []
            for index, (x, _y) in enumerate(points):
                tracks.append({
                    "property": f"points.{index}.x",
                    "keyframes": [
                        {"at_tick": 0, "value": x, "interpolation": "linear"},
                        {"at_tick": 90000, "value": x + 0.5, "interpolation": "linear"},
                    ],
                })
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "mask": {"type": "polygon", "points": points, "keyframes": tracks},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "animated-polygon.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertFalse(any(item.get("feature") == "mask_path_animation" for item in rendered["data"]["warnings"]), rendered)

            def red_centroid(at: float) -> float:
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                red = result.stdout[0::3]
                total = sum(red)
                self.assertGreater(total, 0)
                return sum((index % 320) * value for index, value in enumerate(red)) / total

            self.assertGreater(red_centroid(0.15), 45)
            self.assertGreater(red_centroid(0.85) - red_centroid(0.15), 90)

    def test_dynamic_polygon_mask_feather_renders_inner_soft_edge(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-polygon-feather-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "mask": {
                    "type": "polygon",
                    "points": [[0.2, 0.2], [0.8, 0.2], [0.5, 0.8]],
                    "keyframes": [{"property": "feather", "keyframes": [
                        {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 0.12, "interpolation": "linear"},
                    ]}],
                },
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "dynamic-polygon-feather.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertFalse(any(item.get("feature") == "mask_dynamic_feather" for item in rendered["data"]["warnings"]), rendered)

            def frame_rgb(at: float) -> bytes:
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                self.assertEqual(len(result.stdout), 320 * 180 * 3)
                return result.stdout

            early, late = frame_rgb(0.1), frame_rgb(0.9)
            edge_index = (42 * 320 + 160) * 3
            outside_index = (25 * 320 + 160) * 3
            center_index = (90 * 320 + 160) * 3
            self.assertGreater(early[edge_index], late[edge_index] + 60, (early[edge_index], late[edge_index]))
            self.assertGreater(early[edge_index], 180, (early[edge_index], late[edge_index]))
            self.assertLess(late[edge_index], 190, (early[edge_index], late[edge_index]))
            self.assertGreater(late[center_index], 210)
            self.assertLess(late[outside_index], 15)

    def test_cubic_path_mask_segments_are_validated_and_rendered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-cubic-mask-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "mask": {"type": "path", "segments": [
                    {"type": "line", "from": [0.2, 0.2], "to": [0.8, 0.2]},
                    {"type": "cubic", "from": [0.8, 0.2], "control1": [0.95, 0.55], "control2": [0.05, 0.55], "to": [0.2, 0.2], "samples": 8},
                ]},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)
            output = project / "renders" / "cubic-mask.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("feature") == "mask:path" for item in rendered["data"]["warnings"]), rendered)

    def test_cubic_path_control_point_keyframes_change_pixels(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-animated-cubic-mask-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "mask": {"type": "path", "segments": [
                    {"type": "line", "from": [0.1, 0.2], "to": [0.5, 0.2]},
                    {"type": "cubic", "from": [0.5, 0.2], "control1": [0.7, 0.2], "control2": [0.7, 0.8], "to": [0.1, 0.8], "samples": 10},
                    {"type": "line", "from": [0.1, 0.8], "to": [0.1, 0.2]},
                ], "keyframes": [
                    {"property": "segments.1.control1.x", "keyframes": [{"at_tick": 0, "value": 0.7, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.98, "interpolation": "linear"}]},
                    {"property": "mask.segments.1.control2.x", "keyframes": [{"at_tick": 0, "value": 0.7, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.98, "interpolation": "linear"}]},
                ]},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            code, validated = invoke("validate", "--project", str(project))
            self.assertEqual(code, 0, validated)
            output = project / "renders" / "animated-cubic-mask.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)

            def centroid(at: float) -> float:
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                red = result.stdout[0::3]
                total = sum(red)
                self.assertGreater(total, 0)
                return sum((index % 320) * value for index, value in enumerate(red)) / total

            self.assertGreater(centroid(0.85) - centroid(0.15), 8.0)

    def test_line_path_endpoint_keyframe_changes_pixels(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-animated-line-mask-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "mask": {"type": "path", "segments": [
                    {"type": "line", "from": [0.1, 0.2], "to": [0.5, 0.2]},
                    {"type": "line", "from": [0.5, 0.2], "to": [0.5, 0.8]},
                    {"type": "line", "from": [0.5, 0.8], "to": [0.1, 0.8]},
                    {"type": "line", "from": [0.1, 0.8], "to": [0.1, 0.2]},
                ], "keyframes": [{
                    "property": "segments.0.to.x",
                    "keyframes": [
                        {"at_tick": 0, "value": 0.5, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 0.95, "interpolation": "linear"},
                    ],
                }]},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            code, validated = invoke("validate", "--project", str(project))
            self.assertEqual(code, 0, validated)
            output = project / "renders" / "animated-line-mask.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)

            def centroid(at: float) -> float:
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                red = result.stdout[0::3]
                total = sum(red)
                self.assertGreater(total, 0)
                return sum((index % 320) * value for index, value in enumerate(red)) / total

            self.assertGreater(centroid(0.85) - centroid(0.15), 25.0)

    def test_dynamic_simple_mask_feather_renders_soft_edge(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-dynamic-feather-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            masks = [
                {"type": "circle", "cx": 0.5, "cy": 0.5, "radius": 0.25},
                {"type": "ellipse", "cx": 0.5, "cy": 0.5, "rx": 45 / 320, "ry": 45 / 180},
                {"type": "rectangle", "x": 115 / 320, "y": 45 / 180, "width": 90 / 320, "height": 90 / 180},
            ]
            for mask in masks:
                with self.subTest(mask=mask["type"]):
                    project = workspace / mask["type"]
                    self.assertEqual(invoke("project", "init", str(project))[0], 0)
                    _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
                    changes = workspace / "changes.json"
                    changes.write_text(json.dumps({"operations": [{
                        "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                        "source_in_tick": 0, "source_out_tick": 90000,
                        "mask": {**mask, "keyframes": [{"property": "feather", "keyframes": [
                            {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": 0.12, "interpolation": "linear"},
                        ]}]},
                    }]}), encoding="utf-8")
                    code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
                    self.assertEqual(code, 0, composed)
                    output = project / "renders" / "dynamic-feather.mp4"
                    code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
                    self.assertEqual(code, 0, rendered)
                    self.assertFalse(any(item.get("feature") == "mask_dynamic_feather" for item in rendered["data"]["warnings"]), rendered)

                    def red_at(at: float, x: int, y: int = 90) -> int:
                        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                        return result.stdout[(y * 320 + x) * 3]

                    early, late = red_at(0.1, 120), red_at(0.9, 120)
                    self.assertGreater(early, late + 35, (early, late))
                    self.assertGreater(red_at(0.9, 160), 210)
                    self.assertLess(red_at(0.9, 90), 15)

    def test_dynamic_blend_opacity_changes_composite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-blend-opacity-") as raw:
            workspace = Path(raw)
            red_source = self.make_image(workspace, "red.png")
            blue_source = workspace / "blue.png"
            completed = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x180", "-frames:v", "1", str(blue_source)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, red_ingest = invoke("media", "ingest", "--project", str(project), "--input", str(red_source))
            _, blue_ingest = invoke("media", "ingest", "--project", str(project), "--input", str(blue_source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_track", "id": "track_overlay", "kind": "video", "order": 1},
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": red_ingest["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_overlay", "asset_id": blue_ingest["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000, "blend": {"mode": "multiply", "opacity": 0.0}, "keyframes": [{"property": "blend.opacity", "keyframes": [{"at_tick": 0, "value": 0.0, "interpolation": "linear"}, {"at_tick": 90000, "value": 1.0, "interpolation": "linear"}]}]},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "dynamic-blend.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)

            def center_red(at: float) -> int:
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                return result.stdout[(90 * 320 + 160) * 3]

            early, late = center_red(0.1), center_red(0.9)
            self.assertGreater(early, late + 80, (early, late))
            self.assertGreater(early, 190, (early, late))
            self.assertLess(late, 55, (early, late))

    def test_opacity_keyframes_on_normal_layers_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-normal-opacity-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            for property_name in ("transform.opacity", "blend.opacity"):
                with self.subTest(property=property_name):
                    project = workspace / property_name.replace(".", "_")
                    self.assertEqual(invoke("project", "init", str(project))[0], 0)
                    _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
                    changes = workspace / "changes.json"
                    changes.write_text(json.dumps({"operations": [{
                        "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                        "timeline_start_tick": 45000, "source_in_tick": 0, "source_out_tick": 90000,
                        "blend": {"mode": "normal", "opacity": 0.5 if property_name == "transform.opacity" else 1.0},
                        "keyframes": [{"property": property_name, "keyframes": [
                            {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                        ]}],
                    }]}), encoding="utf-8")
                    code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
                    self.assertEqual(code, 0, composed)
                    output = project / "renders" / "normal-opacity.mp4"
                    code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
                    self.assertEqual(code, 0, rendered)
                    colors = []
                    for at in (0.6, 1.3):
                        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                        colors.append(result.stdout[(90 * 320 + 160) * 3])
                    self.assertGreater(colors[1], colors[0] + 60, colors)

    def test_inverted_mask_changes_coverage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-inverted-mask-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "mask": {"type": "circle", "cx": 0.2, "cy": 0.5, "radius": 0.18, "invert": True},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "inverted-mask.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            frame = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
            self.assertEqual(frame.returncode, 0, frame.stderr.decode("utf-8", "replace"))
            red = frame.stdout[0::3]
            self.assertLess(red[90 * 320 + 64], 20)
            self.assertGreater(red[90 * 320 + 160], 180)

    def test_audio_ducking_and_volume_keyframes_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-audio-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "update_track", "track_id": "track_audio_1", "patch": {"overlap_policy": "allow", "audio": {"volume": 0.8, "pan": -0.1}}},
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_audio_1", "id": "voice", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "audio": {"role": "voice", "volume": 1.0}},
                {"op": "append_clip", "track_id": "track_audio_1", "id": "music", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "audio": {"role": "music", "duck_under_voice": True, "volume": 0.4}, "timeline_start_tick": 0},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "ducking.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertIn("volume=volume=0.800000", planned["data"]["plan"]["filter_complex"])
            self.assertIn("aeval=exprs=", planned["data"]["plan"]["filter_complex"])
            code, result = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            self.assertTrue(any(item.get("code") == "AUDIO_DUCKING_APPLIED" for item in result["warnings"]))

            mute_changes = workspace / "mute-track.json"
            mute_changes.write_text(json.dumps({"operations": [
                {"op": "update_track", "track_id": "track_audio_1", "patch": {"audio": {"muted": True}}},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(mute_changes))[0], 0)
            code, muted_plan = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, muted_plan)
            self.assertNotIn("[1:a]", muted_plan["data"]["plan"]["filter_complex"])
            self.assertNotIn("[2:a]", muted_plan["data"]["plan"]["filter_complex"])

            restore_changes = workspace / "restore-track.json"
            restore_changes.write_text(json.dumps({"operations": [
                {"op": "update_track", "track_id": "track_audio_1", "patch": {"audio": {"volume": 0.8, "pan": -0.1}}},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(restore_changes))[0], 0)
            solo_changes = workspace / "solo-track.json"
            solo_changes.write_text(json.dumps({"operations": [
                {"op": "add_track", "id": "track_audio_solo", "kind": "audio", "order": 2, "audio": {"solo": True}},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(solo_changes))[0], 0)
            code, solo_plan = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, solo_plan)
            self.assertNotIn("[1:a]", solo_plan["data"]["plan"]["filter_complex"])
            self.assertNotIn("[2:a]", solo_plan["data"]["plan"]["filter_complex"])

    def test_audio_pan_keyframes_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-pan-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_audio_1", "id": "pan_automation", "asset_id": ingest_result["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000, "audio": {"pan": 0.0}, "keyframes": [{
                    "property": "audio.pan", "keyframes": [
                        {"at_tick": 0, "value": -1.0, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                    ],
                }]},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "pan-automation.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

            def channel_levels(at: float) -> tuple[float, float]:
                decoded = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-t", "0.1", "-vn", "-ac", "2", "-ar", "48000", "-f", "s16le", "pipe:1"],
                    capture_output=True,
                )
                self.assertEqual(decoded.returncode, 0, decoded.stderr.decode("utf-8", "replace"))
                samples = memoryview(decoded.stdout).cast("h")
                left = [abs(value) for value in samples[0::2]]
                right = [abs(value) for value in samples[1::2]]
                self.assertTrue(left and right)
                return sum(left) / len(left), sum(right) / len(right)

            early_left, early_right = channel_levels(0.15)
            late_left, late_right = channel_levels(0.85)
            self.assertGreater(early_left, early_right * 2.0)
            self.assertGreater(late_right, late_left * 2.0)

    def test_audio_pan_keyframes_reject_out_of_range(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-pan-invalid-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            before = (project / "project.json").read_bytes()
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_audio_1", "asset_id": ingest_result["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000,
                "keyframes": [{"property": "audio.pan", "keyframes": [{"at_tick": 0, "value": 1.1, "interpolation": "linear"}]}],
            }]}), encoding="utf-8")
            code, rejected = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertNotEqual(code, 0, rejected)
            self.assertIn("PAN_KEYFRAME_RANGE", json.dumps(rejected))
            self.assertEqual((project / "project.json").read_bytes(), before)

    def test_numeric_pan_preserves_stereo_channels(self) -> None:
        """A centered numeric pan must not collapse an already-stereo asset."""
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-stereo-pan-") as raw:
            workspace = Path(raw)
            source = workspace / "stereo.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=green:s=320x180:r=24:d=1",
                    "-f", "lavfi", "-i", "aevalsrc=0.8*sin(2*PI*440*t)|0:s=48000:d=1",
                    "-shortest", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
                ],
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_audio_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "audio": {"pan": 0.0}, "keyframes": [{"property": "audio.pan", "keyframes": [{"at_tick": 0, "value": 0.0, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.0, "interpolation": "linear"}]}]},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "stereo-pan.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)

            decoded = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", "0.5", "-i", str(output), "-t", "0.1", "-vn", "-ac", "2", "-ar", "48000", "-f", "s16le", "pipe:1"],
                capture_output=True,
            )
            self.assertEqual(decoded.returncode, 0, decoded.stderr.decode("utf-8", "replace"))
            samples = memoryview(decoded.stdout).cast("h")
            left = sum(abs(value) for value in samples[0::2]) / max(1, len(samples[0::2]))
            right = sum(abs(value) for value in samples[1::2]) / max(1, len(samples[1::2]))
            self.assertGreater(left, 1000)
            self.assertLess(right, left * 0.08, (left, right))

    def test_crossfade_transition_renders_with_overlapping_handles(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-transition-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "update_track", "track_id": "track_video_1", "overlap_policy": "allow"},
                {"op": "append_clip", "track_id": "track_video_1", "id": "transition_a", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 45000, "timeline_start_tick": 0, "duration_tick": 45000},
                {"op": "append_clip", "track_id": "track_video_1", "id": "transition_b", "asset_id": asset_id, "source_in_tick": 45000, "source_out_tick": 90000, "timeline_start_tick": 36000, "duration_tick": 45000, "transition_in": {"type": "crossfade", "duration": 0.1}},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            output = project / "renders" / "crossfade.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("code") == "RENDER_FEATURE_UNSUPPORTED" for item in rendered["warnings"]))

    def test_crossfade_transition_auto_handles_contiguous_clips(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-transition-auto-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "id": "auto_a", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "timeline_start_tick": 0, "duration_tick": 90000},
                {"op": "append_clip", "track_id": "track_video_1", "id": "auto_b", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "timeline_start_tick": 90000, "duration_tick": 90000, "transition_in": {"type": "crossfade", "duration": 0.1, "auto_handle": True}},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            output = project / "renders" / "crossfade-auto.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("code") == "RENDER_FEATURE_UNSUPPORTED" for item in rendered["warnings"]), rendered)
            self.assertTrue(any(item.get("feature") == "complex_transition_auto_handle" for item in rendered["warnings"]), rendered)
            self.assertGreater(probe_media(output)["duration_seconds"], 1.8)

    def test_extended_xfade_catalog_transition_renders(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-xfade-catalog-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "update_track", "track_id": "track_video_1", "overlap_policy": "allow"},
                {"op": "append_clip", "track_id": "track_video_1", "id": "catalog_a", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 45000, "timeline_start_tick": 0, "duration_tick": 45000},
                {"op": "append_clip", "track_id": "track_video_1", "id": "catalog_b", "asset_id": asset_id, "source_in_tick": 45000, "source_out_tick": 90000, "timeline_start_tick": 36000, "duration_tick": 45000, "transition_in": {"type": "circleopen", "duration": 0.1}},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            output = project / "renders" / "circleopen.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("feature") == "complex_transition" for item in rendered["data"]["warnings"]), rendered)

    def test_normalized_crop_and_fill_mode_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-crop-fit-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "crop": {"unit": "normalized", "x": 0.25, "y": 0, "width": 0.5, "height": 1, "fit": "fill"},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "normalized-crop.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

    def test_dynamic_crop_position_keyframes_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-crop-keyframes-") as raw:
            workspace = Path(raw)
            source = workspace / "fixed-quadrants.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:r=24:d=1,drawbox=x=0:y=0:w=160:h=90:color=red:t=fill,drawbox=x=160:y=90:w=160:h=90:color=blue:t=fill",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for unit in ("pixels", "normalized"):
                with self.subTest(unit=unit):
                    project = workspace / unit
                    self.assertEqual(invoke("project", "init", str(project))[0], 0)
                    _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
                    x_end, y_end = (160, 90) if unit == "pixels" else (0.5, 0.5)
                    def animated(property_name: str, end: float) -> dict:
                        return {"property": property_name, "keyframes": [
                            {"at_tick": 0, "value": 0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": end, "interpolation": "linear"},
                        ]}
                    changes = workspace / "changes.json"
                    changes.write_text(json.dumps({"operations": [{
                        "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"],
                        "source_in_tick": 0, "source_out_tick": 90000, "timeline_start_tick": 45000,
                        "crop": {"unit": unit, "x": 0, "y": 0, "width": x_end, "height": y_end, "fit": "stretch", "keyframes": [animated("x", x_end)]},
                        "keyframes": [animated("crop.y", y_end)],
                    }]}), encoding="utf-8")
                    code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
                    self.assertEqual(code, 0, composed)
                    output = project / "renders" / "dynamic-crop.mp4"
                    code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "160", "--height", "90")
                    self.assertEqual(code, 0, rendered)

                    def center_rgb(at: float) -> bytes:
                        frame = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                        self.assertEqual(frame.returncode, 0, frame.stderr.decode("utf-8", "replace"))
                        self.assertEqual(len(frame.stdout), 160 * 90 * 3)
                        offset = (45 * 160 + 80) * 3
                        return frame.stdout[offset:offset + 3]

                    early = center_rgb(0.625)
                    late = center_rgb(1.375)
                    self.assertGreater(early[0], 220, early)
                    self.assertLess(early[2], 30, early)
                    self.assertLess(late[0], 30, late)
                    self.assertGreater(late[2], 220, late)

    def test_crop_keyframes_reject_invalid_or_unsupported_values_before_save(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-crop-invalid-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            before = (project / "project.json").read_bytes()
            cases = [
                ("x", 1.5, "CROP_KEYFRAME_RANGE"),
                ("width", 0.0, "CROP_KEYFRAME_RANGE"),
                ("fit", 0.5, "CROP_KEYFRAME_PROPERTY_UNSUPPORTED"),
                ("x", True, "CROP_KEYFRAME_VALUE_INVALID"),
            ]
            for property_name, value, expected in cases:
                with self.subTest(property=property_name, value=value):
                    changes = workspace / "invalid.json"
                    changes.write_text(json.dumps({"operations": [{
                        "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                        "source_in_tick": 0, "source_out_tick": 90000,
                        "crop": {"unit": "normalized", "width": 0.5, "height": 0.5, "keyframes": [{
                            "property": property_name, "keyframes": [{"at_tick": 0, "value": value, "interpolation": "linear"}],
                        }]},
                    }]}), encoding="utf-8")
                    code, rejected = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
                    self.assertNotEqual(code, 0, rejected)
                    self.assertIn(expected, json.dumps(rejected))
                    self.assertEqual((project / "project.json").read_bytes(), before)

    def test_dynamic_crop_size_keyframes_render_on_fixed_canvas(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-crop-size-keyframes-") as raw:
            workspace = Path(raw)
            source = workspace / "fixed-quadrants.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:r=24:d=1,drawbox=x=0:y=0:w=160:h=90:color=red:t=fill,drawbox=x=160:y=90:w=160:h=90:color=blue:t=fill",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "crop": {"unit": "normalized", "x": 0, "y": 0, "width": 0.5, "height": 0.5, "fit": "stretch", "keyframes": [
                    {"property": "width", "keyframes": [
                        {"at_tick": 0, "value": 0.5, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                    ]},
                    {"property": "height", "keyframes": [
                        {"at_tick": 0, "value": 0.5, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                    ]},
                ]},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "dynamic-crop-size.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "160", "--height", "90")
            self.assertEqual(code, 0, rendered)
            self.assertFalse(any(item.get("feature") == "crop_dynamic_size" for item in rendered["data"]["warnings"]), rendered)

            def sample(at: float) -> bytes:
                frame = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(frame.returncode, 0, frame.stderr.decode("utf-8", "replace"))
                self.assertEqual(len(frame.stdout), 160 * 90 * 3)
                offset = (60 * 160 + 120) * 3
                return frame.stdout[offset:offset + 3]

            early, late = sample(0.1), sample(0.9)
            self.assertGreater(early[0], 220, early)
            self.assertLess(early[2], 35, early)
            self.assertLess(late[0], 35, late)
            self.assertGreater(late[2], 180, late)

    def test_dynamic_crop_size_keyframes_support_fit_and_fill(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-crop-size-modes-") as raw:
            workspace = Path(raw)
            source = workspace / "source.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=red:s=320x180:r=24:d=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for fit in ("fit", "fill"):
                with self.subTest(fit=fit):
                    project = workspace / fit
                    self.assertEqual(invoke("project", "init", str(project))[0], 0)
                    _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
                    changes = workspace / f"{fit}.json"
                    size_tracks = [
                        {"property": "width", "keyframes": [{"at_tick": 0, "value": 0.8, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.2, "interpolation": "linear"}]},
                        {"property": "height", "keyframes": [{"at_tick": 0, "value": 0.2, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.8, "interpolation": "linear"}]},
                    ]
                    changes.write_text(json.dumps({"operations": [{
                        "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"],
                        "source_in_tick": 0, "source_out_tick": 90000,
                        "crop": {"unit": "normalized", "x": 0.1, "y": 0.1, "width": 0.8, "height": 0.2, "fit": fit, "keyframes": size_tracks},
                    }]}), encoding="utf-8")
                    code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
                    self.assertEqual(code, 0, composed)
                    output = project / "renders" / f"dynamic-crop-{fit}.mp4"
                    code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "160", "--height", "90")
                    self.assertEqual(code, 0, rendered)
                    self.assertEqual(rendered["data"]["probe"]["video"]["width"], 160)
                    self.assertEqual(rendered["data"]["probe"]["video"]["height"], 90)

                    def pixel(at: float, x: int, y: int) -> tuple[int, int, int]:
                        frame = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                        self.assertEqual(frame.returncode, 0, frame.stderr.decode("utf-8", "replace"))
                        offset = (y * 160 + x) * 3
                        return tuple(frame.stdout[offset:offset + 3])

                    early_top = pixel(0.1, 80, 2)
                    early_center = pixel(0.1, 80, 45)
                    late_left = pixel(0.9, 2, 45)
                    late_center = pixel(0.9, 80, 45)
                    if fit == "fit":
                        self.assertLess(max(early_top), 20, early_top)
                        self.assertLess(max(late_left), 20, late_left)
                    else:
                        self.assertGreater(early_top[0], 180, early_top)
                        self.assertGreater(late_left[0], 180, late_left)
                    self.assertGreater(early_center[0], 180, early_center)
                    self.assertGreater(late_center[0], 180, late_center)

    def test_timeline_edit_operations_update_and_remove(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-timeline-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            first = workspace / "first.json"
            first.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "id": "clip_edit", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "motion_preset": "zoom_in", "amount": 0.1},
                {"op": "add_track", "track_id": "track_video_2", "kind": "video", "order": 1},
                {"op": "add_marker", "id": "marker_hook", "at_tick": 12000, "label": "hook"},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(first))
            self.assertEqual(code, 0, result)
            first_project = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(first_project["sequences"][0]["tracks"][0]["clips"][0]["keyframes"][0]["property"], "transform.scale")
            second = workspace / "second.json"
            second.write_text(json.dumps({"operations": [
                {"op": "update_clip", "clip_id": "clip_edit", "patch": {"duration_tick": 45000, "source_out_tick": 45000, "speed": 1.25, "reverse": True, "crop": {"x": 0, "y": 0, "width": 160, "height": 90}, "mask": {"type": "circle", "cx": 0.5, "cy": 0.5, "radius": 0.4}}},
                {"op": "set_sequence_duration", "duration_tick": 45000},
                {"op": "remove_marker", "marker_id": "marker_hook"},
                {"op": "remove_track", "track_id": "track_video_2"},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(second))
            self.assertEqual(code, 0, result)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            sequence = project_json["sequences"][0]
            self.assertEqual(sequence["duration_tick"], 45000)
            self.assertEqual(len(sequence["tracks"]), 2)
            self.assertEqual(sequence["tracks"][0]["clips"][0]["speed"], 1.25)
            self.assertTrue(sequence["tracks"][0]["clips"][0]["reverse"])
            self.assertEqual(sequence["tracks"][0]["clips"][0]["crop"]["width"], 160)
            self.assertEqual(sequence["tracks"][0]["clips"][0]["mask"]["type"], "circle")
            self.assertEqual(sequence["markers"], [])
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)
            third = workspace / "third.json"
            third.write_text(json.dumps({"operations": [{"op": "remove_clip", "clip_id": "clip_edit"}]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(third))
            self.assertEqual(code, 0, result)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project_json["sequences"][0]["duration_tick"], 1)

    def test_timeline_ripple_split_slip_speed_reverse_and_freeze(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-advanced-timeline-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "id": "clip_a", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 45000, "duration_tick": 45000},
                {"op": "append_clip", "id": "clip_b", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 45000, "source_out_tick": 90000, "timeline_start_tick": 45000, "duration_tick": 45000},
                {"op": "split_clip", "clip_id": "clip_a", "at_tick": 20000, "left_id": "clip_a_left", "right_id": "clip_a_right"},
                {"op": "slip_clip", "clip_id": "clip_b", "delta_source_tick": -5000},
                {"op": "slide_clip", "clip_id": "clip_b", "delta_tick": 5000},
                {"op": "ripple_insert", "at_tick": 100000, "duration_tick": 9000},
                {"op": "ripple_delete", "at_tick": 0, "duration_tick": 9000},
                {"op": "set_clip_speed", "clip_id": "clip_b", "speed": 1.25},
                {"op": "reverse_clip", "clip_id": "clip_b", "enabled": True},
                {"op": "freeze_frame", "clip_id": "clip_b", "duration_tick": 9000},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            code, validation = invoke("validate", "--project", str(project))
            self.assertEqual(code, 0, validation)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            clips = project_json["sequences"][0]["tracks"][0]["clips"]
            ids = {clip["id"] for clip in clips}
            self.assertTrue({"clip_a_left", "clip_a_right", "clip_b"}.issubset(ids))
            clip_b = next(clip for clip in clips if clip["id"] == "clip_b")
            self.assertTrue(clip_b["reverse"])
            self.assertEqual(clip_b["freeze"]["duration_tick"], 9000)
            output = project / "renders" / "advanced.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertIn("/1.25000000", planned["data"]["plan"]["filter_complex"])

            def frame_clocks(value):
                if isinstance(value, dict):
                    if "video_frame_clock" in value:
                        yield value["video_frame_clock"]
                    for child in value.values():
                        yield from frame_clocks(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from frame_clocks(child)

            self.assertTrue(any(
                clock.get("source_clock_anchor") == "reversed-native-source-intervals"
                for clock in frame_clocks(planned["data"]["plan"])
            ))
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

    def test_midpoint_freeze_is_inserted_into_video_timeline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-midpoint-freeze-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "freeze.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "id": "freeze_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "freeze_frame", "clip_id": "freeze_clip", "at_tick": 45000, "duration_tick": 18000},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            freeze_clip = project_json["sequences"][0]["tracks"][0]["clips"][0]
            freeze_clip["freeze"]["at_tick"] = freeze_clip["duration_tick"] + 1
            (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
            code, invalid = invoke("validate", "--project", str(project))
            self.assertEqual(code, 2, invalid)
            freeze_clip["freeze"]["at_tick"] = 45000
            (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
            output = project / "renders" / "midpoint-freeze.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            filter_graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("loop=loop=6:size=1:start=15", filter_graph)
            self.assertFalse(any(item.get("feature") == "freeze_frame" for item in planned["data"]["plan"]["warnings"]))
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            probe = probe_media(output)
            self.assertAlmostEqual(probe["duration_seconds"], 1.2, delta=0.15)

    def test_midpoint_freeze_audio_pause_is_inserted_at_same_timeline_position(self) -> None:
        """The default freeze policy inserts silence where video is held."""
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-freeze-audio-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "freeze-audio.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "id": "freeze_video", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "id": "freeze_audio", "track_id": "track_audio_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000,
                 "keyframes": [{"property": "audio.volume", "keyframes": [
                     {"at_tick": 0, "value": 1.0, "interpolation": "linear"},
                     {"at_tick": 45000, "value": 0.2, "interpolation": "linear"},
                     {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                 ]}]},
                {"op": "freeze_frame", "clip_id": "freeze_video", "at_tick": 45000, "duration_tick": 18000},
                {"op": "freeze_frame", "clip_id": "freeze_audio", "at_tick": 45000, "duration_tick": 18000},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "freeze-audio.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("anullsrc=r=48000:cl=stereo,atrim=end_sample=9600", graph)
            self.assertIn("concat=n=3:v=0:a=1", graph)
            self.assertIn("t-0.20000000", graph)
            self.assertNotIn("apad=pad_dur=0.200000", graph)
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

            def mean_audio_abs(at: float) -> float:
                decoded = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{at:.3f}", "-t", "0.08", "-i", str(output), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1"],
                    capture_output=True,
                )
                self.assertEqual(decoded.returncode, 0, decoded.stderr.decode("utf-8", errors="replace"))
                samples = memoryview(decoded.stdout).cast("h")
                return sum(abs(value) for value in samples) / max(1, len(samples))

            before = mean_audio_abs(0.35)
            during = mean_audio_abs(0.56)
            after = mean_audio_abs(0.85)
            self.assertGreater(before, 300, (before, during, after))
            self.assertLess(during, before * 0.2, (before, during, after))
            self.assertGreater(after, 300, (before, during, after))

    def test_render_profiles_and_custom_canvas_quality(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-profiles-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://profiles", "--license-spdx", "CC0-1.0", "--evidence", "local://profiles",
            )
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            square = project / "renders" / "square.mp4"
            code, rendered = invoke("render", "--project", str(project), "--profile", "square", "--publish", "--output", str(square))
            self.assertEqual(code, 0, rendered)
            self.assertEqual(rendered["data"]["profile"], "square")
            self.assertEqual((rendered["data"]["probe"]["video"]["width"], rendered["data"]["probe"]["video"]["height"]), (1080, 1080))
            code, checked = invoke("quality", "check", "--project", str(project), "--input", str(square), "--profile", "square", "--require-audio")
            self.assertEqual(code, 0, checked)
            custom = project / "renders" / "custom.mp4"
            code, rendered = invoke("render", "--project", str(project), "--profile", "custom", "--width", "640", "--height", "360", "--output", str(custom))
            self.assertEqual(code, 0, rendered)
            self.assertEqual((rendered["data"]["probe"]["video"]["width"], rendered["data"]["probe"]["video"]["height"]), (640, 360))
            cancel_file = workspace / "cancel.flag"
            cancel_file.write_text("cancel", encoding="utf-8")
            cancelled_output = project / "renders" / "cancelled.mp4"
            code, cancelled = invoke("render", "--project", str(project), "--profile", "square", "--cancel-file", str(cancel_file), "--output", str(cancelled_output))
            self.assertEqual(code, 8, cancelled)
            self.assertEqual(cancelled["errors"][0]["code"], "CANCELLED")
            self.assertFalse(cancelled_output.exists())

    def test_render_local_webm_encoder_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-codec-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "codec.webm"
            code, result = invoke(
                "render", "--project", str(project), "--container", "webm", "--video-codec", "libvpx-vp9",
                "--audio-codec", "libopus", "--crf", "32", "--output", str(output),
            )
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            self.assertIn("webm", result["data"]["probe"]["format"])
            manifest = json.loads((output.with_suffix(output.suffix + ".manifest.json")).read_text(encoding="utf-8"))
            self.assertEqual(manifest["settings"]["output"]["container"], "webm")
            self.assertEqual(manifest["settings"]["output"]["video"]["codec"], "libvpx-vp9")

    def test_cancelled_render_can_resume_with_unchanged_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-resume-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://resume", "--license-spdx", "CC0-1.0", "--evidence", "local://resume",
            )
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)

            cancel_file = workspace / "cancel.flag"
            cancel_file.write_text("cancel", encoding="utf-8")
            output = project / "renders" / "resume.mp4"
            code, cancelled = invoke("render", "--project", str(project), "--output", str(output), "--cancel-file", str(cancel_file))
            self.assertEqual(code, 8, cancelled)
            self.assertEqual(cancelled["errors"][0]["code"], "CANCELLED")
            operation_id = cancelled["operation_id"]
            self.assertEqual(operation_id, cancelled["errors"][0]["operation_id"])
            record_path = project / "operations" / f"{operation_id}.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "cancelled")
            self.assertTrue(record["plan"]["filter_complex"])
            self.assertTrue(record["project_fingerprint"])
            self.assertIn(asset_id, record["input_hashes"])

            asset_path = project / json.loads((project / "project.json").read_text(encoding="utf-8"))["assets"][0]["uri"]
            original_bytes = asset_path.read_bytes()
            asset_path.write_bytes(original_bytes + b"changed-after-cancel")
            cancel_file.unlink()
            code, changed = invoke("render", "--project", str(project), "--resume", operation_id)
            self.assertEqual(code, 2, changed)
            self.assertEqual(changed["errors"][0]["code"], "RESUME_INPUT_CHANGED")
            asset_path.write_bytes(original_bytes)

            code, resumed = invoke("render", "--project", str(project), "--resume", operation_id)
            self.assertEqual(code, 0, resumed)
            self.assertTrue(output.exists())
            self.assertEqual(resumed["data"]["resume_of"], operation_id)
            self.assertNotEqual(resumed["operation_id"], operation_id)

            code, rejected = invoke("render", "--project", str(project), "--resume", operation_id)
            self.assertEqual(code, 2, rejected)
            self.assertEqual(rejected["errors"][0]["code"], "RESUME_INPUT_CHANGED")

    def test_running_local_process_can_be_cancelled(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-cancel-process-") as raw:
            cancel_file = Path(raw) / "cancel.flag"
            timer = threading.Timer(0.25, lambda: cancel_file.write_text("cancel", encoding="utf-8"))
            timer.start()
            try:
                with self.assertRaises(AppError) as raised:
                    run_process([sys.executable, "-c", "import time; time.sleep(2)"], timeout=10, cancel_file=cancel_file)
            finally:
                timer.cancel()
            self.assertEqual(raised.exception.code, "CANCELLED")
            self.assertEqual(raised.exception.exit_code, 8)


if __name__ == "__main__":
    unittest.main()

