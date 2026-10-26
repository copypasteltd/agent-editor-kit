from __future__ import annotations

import array
import contextlib
import copy
import io
import json
import math
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_ad_editor.cli import main
from ai_ad_editor.media import probe_media
from ai_ad_editor.runtime import configure_local_runtime


def invoke(*args: str) -> tuple[int, dict]:
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        code = main(list(args))
    return code, json.loads(captured.getvalue())


class DraftAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_local_runtime()

    def media(self, root: Path) -> Path:
        path = root/"本地 镜头.mp4"
        result = subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","lavfi","-i","color=red:s=320x180:r=24:d=1.2","-f","lavfi","-i","sine=frequency=440:sample_rate=48000:d=1.2","-shortest","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(path)],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return path

    def draft(self, source: Path) -> dict:
        return {
            "id":"draft_fixture", "version":360000, "name":"离线广告", "fps":24, "duration":1_200_000,
            "canvas_config":{"width":320,"height":180},
            "materials":{
                "videos":[{"id":"media_1","type":"video","path":source.name}],
                "texts":[], "audio_fades":[{"id":"fade_1","fade_in_duration":50_000,"fade_out_duration":50_000}],
            },
            "tracks":[{"id":"video_1","type":"video","attribute":0,"segments":[{
                "id":"clip_1", "material_id":"media_1", "target_timerange":{"start":200_000,"duration":800_000},
                "source_timerange":{"start":0,"duration":800_000},"speed":1,"volume":0.4,
                "render_index":4,"extra_material_refs":["fade_1"],"reverse":False,
                "clip":{"alpha":1,"scale":{"x":0.5,"y":0.5},"rotation":0,"transform":{"x":0.2,"y":0.4}},
                "common_keyframes":[{"property_type":"KFTypePositionX","keyframe_list":[
                    {"time_offset":0,"values":[0.2],"curveType":"Line"},
                    {"time_offset":800_000,"values":[-0.2],"curveType":"Line"},
                ]}],
            }]}], "keyframes":{},
        }

    def save(self, root: Path, payload: dict) -> Path:
        source = root/"draft_info.json"
        source.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8-sig")
        return source

    def render(self, root: Path) -> Path:
        code, result = invoke("render","--project",str(root),"--output",str(root/"renders"/"fixture.mp4"),"--profile","custom","--width","320","--height","180")
        self.assertEqual(code,0,result)
        return root/"renders"/"fixture.mp4"

    def pcm_rms(self, source: Path, start: float, duration: float) -> float:
        result = subprocess.run(["ffmpeg","-v","error","-ss",str(start),"-i",str(source),"-t",str(duration),"-vn","-ac","1","-ar","48000","-f","f32le","pipe:1"],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        values = array.array("f",result.stdout)
        self.assertTrue(values)
        return math.sqrt(sum(value*value for value in values)/len(values))

    def test_draft_import_maps_source_clock_text_position_and_embedded_sound(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-import-") as raw:
            root = Path(raw)
            media = self.media(root)
            payload = self.draft(media)
            payload["tracks"][0]["segments"][0]["source_timerange"] = {"start":100_000,"duration":800_000}
            payload["tracks"][0]["segments"][0]["target_timerange"]["duration"] = 400_000
            payload["tracks"][0]["segments"][0]["speed"] = 2
            payload["tracks"][0]["segments"][0]["common_keyframes"][0]["keyframe_list"][1]["time_offset"] = 400_000
            payload["materials"]["texts"].append({"id":"text_1","type":"text","alignment":1,"content":json.dumps({"text":"本地广告","styles":[{"size":12,"fill":{"content":{"solid":{"color":[1,1,1]}}}}]},ensure_ascii=False)})
            payload["tracks"].append({"id":"titles","type":"text","segments":[{"id":"caption_1","material_id":"text_1","target_timerange":{"start":100_000,"duration":800_000},"clip":{"transform":{"x":0,"y":-0.3}}}]})
            source = self.save(root,payload)
            project = root/"project"
            code, result = invoke("convert","import","--input",str(source),"--output",str(project))
            self.assertEqual(code,0,result)
            self.assertEqual(result["data"]["report_data"]["source_format"],"jianying-draft-json")
            self.assertTrue(result["warnings"])
            loaded = json.loads((project/"project.json").read_text(encoding="utf-8"))
            video = next(track for track in loaded["sequences"][0]["tracks"] if track["kind"]=="video")["clips"][0]
            self.assertEqual((video["timeline_start_tick"],video["duration_tick"],video["source_in_tick"],video["source_out_tick"]),(18000,36000,9000,81000))
            self.assertEqual(video["speed"],2)
            self.assertEqual(video["transform"]["position"],{"x":0.6,"y":0.3})
            self.assertEqual(video["keyframes"][0]["keyframes"][-1]["value"],0.4)
            self.assertEqual(video["audio"]["fade_in"],0.05)
            text = next(track for track in loaded["sequences"][0]["tracks"] if track["kind"]=="subtitle")["clips"][0]
            self.assertEqual(text["subtitle"]["text"],"本地广告")
            self.assertEqual(text["transform"]["position"]["y"],0.65)
            self.assertEqual(invoke("validate","--project",str(project))[0],0)
            self.assertEqual(invoke("policy","audit","--project",str(project))[0],0)
            rendered = self.render(project)
            self.assertEqual(probe_media(rendered)["video"]["width"],320)
            self.assertGreater(self.pcm_rms(rendered,0.3,0.1),0.01)
            self.assertLess(self.pcm_rms(rendered,0.02,0.08),0.001)
            self.assertLess(self.pcm_rms(rendered,1.05,0.1),0.001)
            self.assertNotEqual(invoke("rights","check","--project",str(project))[0],0)

    def test_overlapping_segments_preserve_target_ranges_and_report_approximate_stack_and_mix(self):
        with tempfile.TemporaryDirectory(prefix='draft-overlap-') as raw:
            root=Path(raw);payload=self.draft(self.media(root))
            peer=copy.deepcopy(payload['tracks'][0]['segments'][0]);peer['id']='clip_2'
            peer['target_timerange']={'start':600_000,'duration':600_000}
            peer['source_timerange']={'start':0,'duration':600_000};peer['common_keyframes']=[]
            payload['tracks'][0]['segments'].append(peer);source=self.save(root,payload)
            code,result=invoke('convert','import','--input',str(source),'--output',str(root/'project'))
            self.assertEqual(code,0,result)
            project=json.loads((root/'project/project.json').read_bytes())
            tracks=[t for t in project['sequences'][0]['tracks'] if t['clips']]
            self.assertEqual({t['kind'] for t in tracks},{'video','audio'})
            self.assertTrue(all(t['overlap_policy']=='allow' for t in tracks))
            visual=next(t for t in tracks if t['kind']=='video')['clips']
            self.assertEqual([(c['timeline_start_tick'],c['duration_tick']) for c in visual],[(18000,72000),(54000,54000)])
            self.assertEqual(invoke('validate','--project',str(root/'project'))[0],0)
            losses=[r for r in result['data']['report_data']['items'] if r['capability']=='timeline-overlap']
            self.assertEqual(len(losses),2);self.assertTrue(all(r['status']=='Approximate' for r in losses))
            code,result=invoke('convert','import','--input',str(source),'--output',str(root/'strict'),'--strict')
            self.assertEqual(code,2,result);self.assertFalse((root/'strict/project.json').exists())

    def test_draft_roundtrip_preserves_sound_without_double_mixing_and_frames(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-roundtrip-") as raw:
            root = Path(raw)
            source = self.save(root,self.draft(self.media(root)))
            original = root/"original"
            code, result = invoke("convert","import","--input",str(source),"--output",str(original),"--strict")
            self.assertEqual(code,0,result)
            baseline = self.render(original)
            exported = root/"exported.json"
            code, result = invoke("convert","export","--project",str(original),"--output",str(exported),"--target-format","jianying-draft-json","--strict")
            self.assertEqual(code,0,result)
            draft = json.loads(exported.read_text(encoding="utf-8"))
            self.assertEqual(len(draft["tracks"]),1)
            self.assertAlmostEqual(draft["tracks"][0]["segments"][0]["volume"],0.4)
            self.assertTrue(Path(result["data"]["source_sidecar"]).is_file())
            imported = root/"roundtrip"
            code, result = invoke("convert","import","--input",str(exported),"--output",str(imported),"--strict")
            self.assertEqual(code,0,result)
            rendered = self.render(imported)
            self.assertAlmostEqual(self.pcm_rms(rendered,0.35,0.3),self.pcm_rms(baseline,0.35,0.3),delta=0.001)
            frames = []
            for path in (baseline,rendered):
                frame = subprocess.run(["ffmpeg","-v","error","-ss","0.5","-i",str(path),"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","pipe:1"],capture_output=True)
                self.assertEqual(frame.returncode,0,frame.stderr)
                frames.append(frame.stdout)
            self.assertEqual(frames[0],frames[1])

    def test_draft_private_resources_are_reported_redacted_and_strictly_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-loss-") as raw:
            root = Path(raw)
            payload = self.draft(self.media(root))
            payload["materials"]["video_effects"] = [{"id":"effect_1","resource_id":"private-only","download_url":"https://example.invalid/closed-effect"}]
            payload["tracks"][0]["segments"][0]["extra_material_refs"].append("effect_1")
            source = self.save(root,payload)
            rejected = root/"rejected"
            code, result = invoke("convert","import","--input",str(source),"--output",str(rejected),"--strict")
            self.assertEqual(code,2,result)
            self.assertEqual(result["errors"][0]["code"],"CONVERSION_STRICT_REJECTED")
            self.assertFalse(rejected.exists())
            project = root/"best-effort"
            code, result = invoke("convert","import","--input",str(source),"--output",str(project))
            self.assertEqual(code,0,result)
            self.assertEqual(result["data"]["report_data"]["summary"]["status"],"success_with_warnings")
            self.assertTrue(any(item["status"]=="Unsupported" for item in result["warnings"]))
            preserved = (project/"validation"/"source-draft.json").read_text(encoding="utf-8")
            self.assertNotIn("https://",preserved)
            self.assertIn("redacted_reference_sha256",preserved)
            self.assertEqual(invoke("policy","audit","--project",str(project))[0],0)
            alternate = copy.deepcopy(payload)
            alternate["materials"].pop("video_effects")
            alternate["tracks"][0]["segments"][0]["extra_material_refs"] = ["fade_1"]
            alternate["new_version"] = "999.0.0"
            code, result = invoke("convert","import","--input",str(self.save(root,alternate)),"--output",str(root/"unknown-version"),"--strict")
            self.assertEqual(code,2,result)
            self.assertEqual(result["errors"][0]["code"],"CONVERSION_STRICT_REJECTED")
            self.assertIn("draft-version",result["errors"][0]["cause"])
            self.assertFalse((root/"unknown-version").exists())

    def test_draft_network_media_is_rejected_before_copy_or_project_creation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-network-") as raw:
            root = Path(raw)
            payload = self.draft(root/"local.mp4")
            for index, path in enumerate(("https://example.invalid/clip.mp4","s3://bucket/clip.mp4",r"\\server\share\clip.mp4","file://remote-host/share/clip.mp4")):
                with self.subTest(path=path):
                    altered = copy.deepcopy(payload)
                    altered["materials"]["videos"][0]["path"] = path
                    source = self.save(root,altered)
                    destination = root/f"bad-{index}"
                    with patch("ai_ad_editor.convert._asset_from_local") as loader:
                        code, result = invoke("convert","import","--input",str(source),"--output",str(destination))
                    self.assertEqual(code,2,result)
                    loader.assert_not_called()
                    self.assertFalse(destination.exists())

    def test_draft_invalid_structure_and_ranges_leave_no_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-invalid-") as raw:
            root = Path(raw)
            base = self.draft(self.media(root))
            cases = []
            duplicate = copy.deepcopy(base)
            duplicate["materials"]["videos"].append(copy.deepcopy(duplicate["materials"]["videos"][0]))
            cases.append(duplicate)
            negative = copy.deepcopy(base)
            negative["tracks"][0]["segments"][0]["target_timerange"]["start"] = -1
            cases.append(negative)
            invalid = copy.deepcopy(base)
            invalid["tracks"][0]["segments"][0]["clip"]["transform"] = [1,2]
            cases.append(invalid)
            invalid_range = copy.deepcopy(base)
            invalid_range["tracks"][0]["segments"][0]["source_timerange"]["duration"] = 50_000_000
            cases.append(invalid_range)
            nonfinite = copy.deepcopy(base)
            nonfinite["fps"] = float("nan")
            cases.append(nonfinite)
            for index, payload in enumerate(cases):
                with self.subTest(index=index):
                    source = self.save(root,payload)
                    output = root/f"invalid-{index}"
                    code, result = invoke("convert","import","--input",str(source),"--output",str(output))
                    self.assertEqual(code,2,result)
                    self.assertFalse(output.exists())

    def test_draft_missing_local_media_is_partial_and_not_a_success(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-missing-") as raw:
            root = Path(raw)
            source = self.save(root,self.draft(root/"missing.mp4"))
            project = root/"partial"
            code, result = invoke("convert","import","--input",str(source),"--output",str(project))
            self.assertEqual(code,2,result)
            self.assertFalse(result["ok"])
            self.assertTrue((project/"project.json").is_file())
            self.assertEqual(result["data"]["report_data"]["summary"]["status"],"partial")
            self.assertTrue(result["errors"])

    def test_draft_export_changed_asset_hash_leaves_no_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-hash-") as raw:
            root = Path(raw)
            source = self.save(root,self.draft(self.media(root)))
            project = root/"project"
            self.assertEqual(invoke("convert","import","--input",str(source),"--output",str(project))[0],0)
            loaded = json.loads((project/"project.json").read_text(encoding="utf-8"))
            path = project/loaded["assets"][0]["uri"]
            with path.open("ab") as handle:
                handle.write(b"modified")
            output = root/"out.json"
            code, result = invoke("convert","export","--project",str(project),"--output",str(output),"--target-format","jianying-draft-json")
            self.assertEqual(code,2,result)
            self.assertIn(result["errors"][0]["code"],{"CONVERSION_PROJECT_INVALID","CONVERSION_ASSET_HASH_MISMATCH"})
            self.assertFalse(output.exists())

    def test_draft_export_strict_loss_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-export-loss-") as raw:
            root = Path(raw)
            source = self.save(root,self.draft(self.media(root)))
            project = root/"project"
            self.assertEqual(invoke("convert","import","--input",str(source),"--output",str(project))[0],0)
            path = project/"project.json"
            loaded = json.loads(path.read_text(encoding="utf-8"))
            video = next(track for track in loaded["sequences"][0]["tracks"] if track["kind"]=="video")["clips"][0]
            video["mask"] = {"type":"circle","cx":0.5,"cy":0.5,"radius":0.4}
            path.write_text(json.dumps(loaded,ensure_ascii=False),encoding="utf-8")
            output = root/"out.json"
            output.write_text("existing-user-file",encoding="utf-8")
            code, result = invoke("convert","export","--project",str(project),"--output",str(output),"--target-format","jianying-draft-json","--strict")
            self.assertEqual(code,2,result)
            self.assertEqual(result["errors"][0]["code"],"CONVERSION_STRICT_REJECTED")
            self.assertEqual(output.read_text(encoding="utf-8"),"existing-user-file")
            self.assertFalse(output.with_suffix(".json.source-agent.json").exists())
            captions = root/"captions.srt"
            captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nLocal captions\n",encoding="utf-8")
            code, ingested = invoke("media","ingest","--project",str(project),"--input",str(captions))
            self.assertEqual(code,0,ingested)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            video = next(track for track in loaded["sequences"][0]["tracks"] if track["kind"]=="video")["clips"][0]
            video.pop("mask")
            video["subtitle"] = {"text":"Embedded captions"}
            loaded["settings"]["canvas"]["background"] = "transparent"
            loaded["sequences"][0]["tracks"].append({"id":"caption-asset-track","kind":"subtitle","order":10,"clips":[{"id":"caption-asset","asset_id":ingested["data"]["asset"]["id"],"timeline_start_tick":0,"duration_tick":90000,"source_in_tick":0,"source_out_tick":90000}]})
            path.write_text(json.dumps(loaded),encoding="utf-8")
            code, result = invoke("convert","export","--project",str(project),"--output",str(output),"--target-format","jianying-draft-json")
            self.assertEqual(code,0,result)
            capabilities = {item["capability"] for item in result["warnings"]}
            self.assertTrue({"subtitle-asset","embedded-subtitle","canvas-background"}.issubset(capabilities),result)

    def test_draft_crop_text_color_and_local_font_survive_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-text-crop-") as raw:
            root = Path(raw)
            payload = self.draft(self.media(root))
            payload["materials"]["videos"][0]["crop"] = {"upper_left_x":0.1,"upper_left_y":0.2,"upper_right_x":0.9,"upper_right_y":0.2,"lower_left_x":0.1,"lower_left_y":0.8,"lower_right_x":0.9,"lower_right_y":0.8}
            style = {"size":15,"fill":{"content":{"solid":{"color":[0.2,2/3,0.8]}}}}
            font = next((path for path in (Path("C:/Windows/Fonts/arial.ttf"),Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")) if path.is_file()),None)
            if font:
                style["font"] = {"id":"local-font","path":str(font)}
            payload["materials"]["texts"].append({"id":"title","type":"text","global_alpha":0.75,"alignment":2,"content":json.dumps({"text":"Local Ad","styles":[style]})})
            payload["tracks"].append({"id":"titles","type":"text","segments":[{"id":"title-clip","material_id":"title","target_timerange":{"start":0,"duration":1_200_000}}]})
            source = self.save(root,payload)
            original, imported = root/"original", root/"roundtrip"
            code, result = invoke("convert","import","--input",str(source),"--output",str(original))
            self.assertEqual(code,0,result)
            output = root/"export.json"
            code, result = invoke("convert","export","--project",str(original),"--output",str(output),"--target-format","jianying-draft-json")
            self.assertEqual(code,0,result)
            exported = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(exported["materials"]["videos"][0]["crop"],payload["materials"]["videos"][0]["crop"])
            self.assertEqual(exported["materials"]["texts"][0]["global_alpha"],0.75)
            code, result = invoke("convert","import","--input",str(output),"--output",str(imported))
            self.assertEqual(code,0,result)
            loaded = json.loads((imported/"project.json").read_text(encoding="utf-8"))
            title = next(track for track in loaded["sequences"][0]["tracks"] if track["kind"]=="subtitle")["clips"][0]
            self.assertEqual(title["subtitle"]["style"]["fontcolor"],"#33aacc@0.750000")
            self.assertEqual(title["subtitle"]["style"]["fontsize"],27)
            self.assertEqual(title["subtitle"]["style"]["text_align"],"right")
            if font:
                self.assertTrue(any(asset["kind"]=="font" for asset in loaded["assets"]))
                self.assertIn("font_asset_id",title["subtitle"]["style"])
            self.render(imported)

    def test_draft_altered_or_globally_muted_original_does_not_gain_sound(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-audio-edits-") as raw:
            root = Path(raw)
            media = self.media(root)
            for mode in ("volume", "track-muted", "global-muted"):
                with self.subTest(mode=mode):
                    payload = self.draft(media)
                    if mode == "global-muted":
                        payload["config"] = {"video_mute":True}
                    source = self.save(root,payload)
                    original = root/mode
                    self.assertEqual(invoke("convert","import","--input",str(source),"--output",str(original))[0],0)
                    path = original/"project.json"
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    audio = next(track for track in loaded["sequences"][0]["tracks"] if track["kind"]=="audio")
                    if mode == "volume":
                        audio["clips"][0]["audio"]["volume"] = 0.2
                    elif mode == "track-muted":
                        audio["muted"] = True
                    path.write_text(json.dumps(loaded),encoding="utf-8")
                    baseline = self.render(original)
                    output = root/f"{mode}.json"
                    code, result = invoke("convert","export","--project",str(original),"--output",str(output),"--target-format","jianying-draft-json")
                    self.assertEqual(code,0,result)
                    exported = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual(next(track for track in exported["tracks"] if track["type"]=="video")["segments"][0]["volume"],0)
                    imported = root/f"{mode}-roundtrip"
                    code, result = invoke("convert","import","--input",str(output),"--output",str(imported))
                    self.assertEqual(code,0,result)
                    rendered = self.render(imported)
                    self.assertAlmostEqual(self.pcm_rms(rendered,0.35,0.3),self.pcm_rms(baseline,0.35,0.3),delta=0.001)

    def test_draft_nonplaintext_and_source_overwrite_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="draft-protected-") as raw:
            root = Path(raw)
            source = root/"encrypted.json"
            source.write_bytes(b"\xff\x00\x80encrypted")
            output = root/"invalid"
            code, result = invoke("convert","import","--input",str(source),"--output",str(output))
            self.assertEqual(code,2,result)
            self.assertFalse(output.exists())
            source = self.save(root,self.draft(self.media(root)))
            project = root/"project"
            self.assertEqual(invoke("convert","import","--input",str(source),"--output",str(project))[0],0)
            original = (project/"project.json").read_bytes()
            code, result = invoke("convert","export","--project",str(project),"--output",str(project/"project.json"),"--target-format","jianying-draft-json")
            self.assertEqual(code,2,result)
            self.assertEqual((project/"project.json").read_bytes(),original)


if __name__ == "__main__":
    unittest.main()
