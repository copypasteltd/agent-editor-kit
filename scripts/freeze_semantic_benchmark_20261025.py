"""Freeze local, attributed visual retrieval fixtures before any model query.

Copies existing scikit-image data directly; never calls its download helpers.
Only native FFmpeg and Pillow are used. Labels are never supplied to inference.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/Lib/site-packages/skimage/data")
OUT = ROOT / "docs/assets/semantic-20261025-r1"
EVIDENCE = ROOT / "docs/validation/evidence/semantic-20261025-r1/benchmark-frozen"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8", newline="\n")


def run(arguments):
    result = subprocess.run(arguments, capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[-4000:])
    return arguments


def main():
    assert not OUT.exists() and not EVIDENCE.exists()
    OUT.mkdir(parents=True); EVIDENCE.mkdir(parents=True)
    docs = {node.name: ast.get_docstring(node) for node in ast.parse((DATA/"_fetchers.py").read_text("utf-8")).body
            if isinstance(node, ast.FunctionDef)}
    entries = []
    selections = [
        ("asset_a7", "camera.png", "camera", "Lav Varshney", "CC0-1.0"),
        ("asset_b4", "coffee.png", "coffee", "Rachel Michetti; courtesy Pikolo Espresso Bar", "CC0-1.0"),
        ("asset_c2", "chelsea.png", "chelsea", "Stefan van der Walt", "CC0-1.0"),
        ("asset_d9", "astronaut.png", "astronaut", "NASA; Eileen Collins photograph", "LicenseRef-NASA-Public-Domain"),
        ("asset_e3", "grass.png", "grass", "CC0 Textures", "CC0-1.0"),
        ("asset_f8", "gravel.png", "gravel", "CC0 Textures", "CC0-1.0"),
        ("asset_g5", "clock_motion.png", "clock", "Stefan van der Walt", "CC0-1.0"),
        ("asset_h6", "hubble_deep_field.jpg", "hubble_deep_field", "NASA / Hubble", "LicenseRef-NASA-Public-Domain"),
    ]
    for ident, source, function, creator, license_id in selections:
        destination = OUT / (ident + Path(source).suffix)
        shutil.copyfile(DATA/source, destination)
        entries.append(dict(asset_id=ident, path=destination.relative_to(ROOT).as_posix(), kind="image",
                            sha256=sha(destination), original_name=source, creator=creator, license_spdx=license_id,
                            source_url="https://scikit-image.org/docs/stable/api/skimage.data.html#skimage.data."+function,
                            local_upstream_docstring=docs[function]))
    # An intentionally misleading filename cannot alter the image embedding.
    duplicate = OUT / "coffee_intro.png"
    shutil.copyfile(DATA/"chelsea.png", duplicate)
    entries.append({**entries[2], "asset_id":"asset_i1", "path":duplicate.relative_to(ROOT).as_posix(),
                    "same_pixels_as":"asset_c2", "original_name":"chelsea.png"})
    reference = OUT/"reference-crop.png"
    commands = [run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(DATA/"chelsea.png"),
                     "-vf", "crop=iw*0.8:ih*0.8:iw*0.1:ih*0.1", "-frames:v", "1", "-n", str(reference)])]
    video = OUT/"asset_v1.mp4"
    command = ["ffmpeg", "-nostdin", "-v", "error"]
    for name in ("coffee.png", "chelsea.png", "astronaut.png"):
        command += ["-loop", "1", "-framerate", "12", "-t", "2", "-i", str(DATA/name)]
    graph = ";".join(f"[{i}:v]scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS[v{i}]" for i in range(3))
    graph += ";[v0][v1][v2]concat=n=3:v=1:a=0[v]"
    commands.append(run(command+["-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-crf", "18",
                                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-n", str(video)]))
    entries.append(dict(asset_id="asset_v1", path=video.relative_to(ROOT).as_posix(), kind="video", sha256=sha(video),
                        derived_from=["asset_b4","asset_c2","asset_d9"], duration_seconds=6, fps=12, frames=72,
                        license_spdx="LicenseRef-Mixed-CC0-NASA", creator="Original sequence; source credits in SOURCE.json"))
    # All queries, relevance labels and gates are set here, before any forward.
    definitions = [
        ("q01", "a cup of coffee on a wooden table", ["asset_b4"], [[0,2]]),
        ("q02", "木桌上的一杯咖啡", ["asset_b4"], [[0,2]]),
        ("q03", "a close-up photograph of a cat", ["asset_c2","asset_i1"], [[2,4]]),
        ("q04", "一只猫的近距离照片", ["asset_c2","asset_i1"], [[2,4]]),
        ("q05", "a woman wearing an astronaut spacesuit", ["asset_d9"], [[4,6]]),
        ("q06", "穿宇航服的女性宇航员", ["asset_d9"], [[4,6]]),
        ("q07", "a photographer standing behind a camera", ["asset_a7"], []),
        ("q08", "站在相机后面的摄影师", ["asset_a7"], []),
        ("q09", "a close-up texture of grass", ["asset_e3"], []),
        ("q10", "草地的纹理", ["asset_e3"], []),
        ("q11", "small gray stones and gravel", ["asset_f8"], []),
        ("q12", "灰色碎石和小石子", ["asset_f8"], []),
        ("q13", "a clock face with numbers and hands", ["asset_g5"], []),
        ("q14", "带数字和指针的钟表", ["asset_g5"], []),
        ("q15", "distant galaxies and stars in deep space", ["asset_h6"], []),
        ("q16", "深空中的星系和星星", ["asset_h6"], []),
        ("q17", "a cat, not a cup of coffee", ["asset_c2","asset_i1"], [[2,4]]),
        ("q18", "一只猫，不是一杯咖啡", ["asset_c2","asset_i1"], [[2,4]]),
        ("q19", "an underwater shark swimming beside coral", [], []),
        ("q20", "水下珊瑚旁边游动的鲨鱼", [], []),
    ]
    queries = [dict(id=ident, text=text, relevant_image_ids=ids, relevant_video_intervals=intervals,
                    group="positive" if int(ident[1:])<=16 else "negation" if int(ident[1:])<=18 else "out_of_domain")
               for ident,text,ids,intervals in definitions]
    truth = dict(protocol="semantic-natural-benchmark-v1", frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                 assets=entries, queries=queries,
                 reference_image=dict(path=reference.relative_to(ROOT).as_posix(),sha256=sha(reference),
                                      relevant_image_ids=["asset_c2","asset_i1"], relevant_video_intervals=[[2,4]]),
                 video_sampling_interval_seconds=1.,
                 gates=dict(positive_top1_minimum=0.75, positive_recall_at_3_minimum=0.90,
                            video_queries_first_6_timestamp_top1_minimum=0.80,
                            image_query_top1_required=True, renamed_duplicate_vectors_equal=True),
                 caveats=["All 20 queries must be reported; negation and out-of-domain failures remain visible.",
                          "Cosine is not calibrated probability; open-set abstention is unimplemented and ungated.",
                          "Labels never enter model requests; familiar public images are not an unseen training-distribution benchmark.",
                          "Eight scenes and a still-image sequence do not prove action understanding or broad advertising quality.",
                          "NASA imagery is used for a technical demonstration without endorsement; personality and trademark rights are separate."],
                 generator_sha256=sha(Path(__file__)))
    save(EVIDENCE/"truth.json",truth)
    save(OUT/"SOURCE.json",dict(assets=entries, reference_image=truth["reference_image"], commands=commands,
                               upstream_docstrings_sha256=sha(DATA/"_fetchers.py")))
    (OUT/"NOTICE.txt").write_text("Local visual-retrieval demonstration. Image-specific credits and upstream license statements are in SOURCE.json.\n"
                                "CC0 images remain CC0. NASA images are public-domain US Government imagery as documented by scikit-image; no endorsement or personality-rights clearance is implied.\n"
                                "The sequence and reference crop retain their source credits. These are existing static photographs, not a benchmark of natural moving actions.\n",
                                encoding="utf-8",newline="\n")
    print(json.dumps(dict(status="frozen_before_any_semantic_forward",truth_sha256=sha(EVIDENCE/"truth.json"),
                          assets=len(entries),queries=len(queries),new_model_forwards=0),ensure_ascii=False),flush=True)


if __name__=="__main__":main()
