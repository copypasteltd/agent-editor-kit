# Community materials, voice, translation, music and GPU workflow

The current runtime is **CLI 0.1.8 / `v0.1.0-alpha.4-local.6`**, paired with the [matching local bundle and r7 kit](COMMUNITY_LOCAL_DELIVERY.md). This page preserves the materials/voice/translation/GPU evidence from **CLI 0.1.3 / local.1**; those tasks were not all rerun in this increment. The public GitHub Release remains alpha.3 / CLI 0.1.2; its old archive does not contain these commands. Invoke only `$agent-ffmpeg-local-editor`; its 17 internal modules remain available.

| ID | Module | Implemented | Limits |
|---|---|---|---|
| M01 | Real resources | 44 BGM tracks, 85 jingles, 228 unique SFX and 2 Noto SC/TC fonts: 359 actual files | Five tracks have documented lossy conversion; duplicate SFX have aliases and count once; no commercial stock subscription |
| M02 | Local speech | 103 upstream named Kokoro voices, Chinese/English text or UTF-8 files, speed 0.5–2.0, 24 kHz mono PCM WAV, explicit timeline apply | Three voices actually audition-generated; not 103 human-reviewed voices; no cloning or guaranteed emotion |
| M03 | Translation | OPUS Chinese↔English, simplified/traditional processing, paragraphs, bilingual subtitles and explicit glossary post-edits | SRT cue order/overlap/milliseconds preserved; ASS/VTT styling flattened; no semantic approval |
| M04 | Music preparation | Offset, trim, explicit looping, gain and fades, with original credits | No seam repair or music generation |
| M05 | Mix/ducking | Voice+BGM, sidechain compression, limiter, exact 48 kHz stereo sample count | Original stems retained; no silent voice truncation; PCM metrics are not listening or true-peak acceptance |
| M06 | SFX/fonts | Real CC0 interface/impact/footstep sounds and OFL Noto SC/TC rendering | Retain font licenses/RFN; no redistributed proprietary system fonts |
| G01 | GPU | Voice: CUDA 13/ORT; translation: CUDA 12/CT2 `int8_float16`; `auto/cpu/cuda` | RTX 3060 tested; cold startup may be slower; other devices remain unverified |
| G02 | Device policy | Free VRAM preflight: 3072 MiB voice, 1536 MiB translation; explicit fallback reasons | Thresholds cannot prevent every OOM; strict CUDA fails clearly; other GPU processes stay running |
| M07 | Offline packs | Bundled base assets plus four optional hash-pinned model packs, isolated workers/native installer | No environment creation or implicit network; changed/missing packs are rejected |

## Complete workflow

Set `$avk` to the unified Skill launcher. The local registration supplies existing CPU/GPU pack paths and NVIDIA library directories. `--device auto` prefers the available GPU; standalone installs may pass `--pack`, `--gpu-pack` and `--cuda-library-directory` explicitly. Nothing is downloaded during editing or inference.

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
$aekProject = 'E:/video-work/community-ad'
& $avk version
& $avk gpu inspect
& $avk model-pack list
& $avk project init $aekProject --name 'Community ad'
& $avk materials list --kind music --query 'rpg'
& $avk materials inspect --id kenney-music-jingles-jingles-hit00
& $avk materials ingest --project $aekProject --id kenney-music-jingles-jingles-hit00 --asset-id asset_jingle
& $avk voice list --language zh
& $avk voice synthesize --project $aekProject --voice zf_001 --input 'E:/video-work/narration.txt' --device auto --asset-id asset_voice
& $avk translate subtitles --project $aekProject --from zh-Hans --to en --input 'E:/video-work/source.srt' --output exports/bilingual.srt --mode bilingual --device auto
& $avk music prepare --project $aekProject --asset-id asset_jingle --duration-seconds 12 --loop --fade-in-seconds 0.3 --fade-out-seconds 0.8 --new-asset-id asset_bed
& $avk music mix --project $aekProject --voice-asset-id asset_voice --music-asset-id asset_bed --duration-seconds 12 --music-gain-db -18 --duck --new-asset-id asset_mix
# --apply requires an unlocked, unmuted audio track.
# Author timeline compose JSON with returned IDs; video, captions and audio are explicit tracks.
& $avk validate --project $aekProject
& $avk preview frame --project $aekProject --frame 0 --height 640
& $avk render --project $aekProject --output 'E:/video-work/community-ad/renders/ad.mp4'
& $avk quality check --project $aekProject --input 'E:/video-work/community-ad/renders/ad.mp4' --require-audio
& $avk convert export --project $aekProject --target-format package --output 'E:/video-work/community-ad.aevpkg.zip'
```

1. Run `version`, `gpu inspect`, `model-pack list` and create the project.
2. Search/inspect resources, ingest music/SFX/fonts, and select a named voice.
3. Generate speech from the actual local text file. Translate the supplied subtitle file, retaining cue timings.
4. Prepare BGM to cover the natural speech duration; mix/duck without overwriting stems.
5. Author explicit video, subtitle and audio tracks with returned asset IDs. `--apply` requires an unlocked, unmuted audio track.
6. Validate, preview, render, check the encoded file, and export the editable package.

The sample text/subtitle files must exist. If speech exceeds the requested 12-second edit, extend the bed/edit instead of cutting the line. Inspect `ok`, `status`, `errors`, `warnings`, `data.device`, inference provider and actual files.

Text size/width uses author-canvas pixels. `preview --height` scales a preview; `render --width/--height` changes the composition raster rather than simply resizing a completed frame. Set `update_sequence.patch.canvas` to the intended final dimensions, author matching text styles and render at that size. The original cropped-text attempt is retained; eight separate follow-up commands verify corrected preview/render/package output.

## GPU compatibility and performance

| Path | Model/computation | Dependencies | Verified scope |
|---|---|---|---|
| CPU voice | Kokoro int8 ONNX | sherpa-onnx 2.0.0 / ORT 1.28.2 | Native Windows CPython 3.13 x64 |
| CUDA voice | Upstream unquantized ONNX / Float32 | NVIDIA driver, CUDA 13, cuDNN 9 and optional GPU pack | RTX 3060; voice adapter currently device 0 only |
| CPU translation | OPUS int8 | Source-built CT2 4.8.3 + Ruy, no MKL/cuDNN/Intel OpenMP | Both directions, text and subtitles |
| CUDA translation | Same OPUS int8 weights / `int8_float16` computation | CUDA 12 cuBLAS and optional GPU pack | RTX 3060; explicit device index |
| AMD/Intel/Apple GPU | Not integrated | `auto` may use verified CPU path | No claimed GPU support |

With the same Float32 voice model and ~6.85 seconds of text, second generation took ~4.93 s CPU versus ~0.62 s CUDA; loading took ~4.08 s CPU versus ~7.54 s CUDA. Other device workloads were running. The ~8× generation improvement is not an end-to-end single-CLI guarantee. A CUDA translation example took ~0.38 s on first generation and ~0.037 s on repeat, excluding full CLI startup/hash checks. Cold/warm times remain separate.

Open-source engine/model licenses are separate from optional GPU dependencies. NVIDIA driver/CUDA/cuDNN have their own proprietary terms; upstream Windows GPU binaries also preserve supplied third-party terms, including Intel runtime where present. They are not described as open-source media assets. Use the separate Ruy CPU path to avoid proprietary numerical backends. This change does not move all FFmpeg filters onto the GPU.

`auto` checks free memory and records CPU fallback. A real CUDA worker failure may retry CPU only before any output exists; its failed-worker log remains in the response. Missing/changed pack contents never bypass integrity checks. `cuda` is strict and returns failure. No other GPU tasks are stopped.

## Portable model packs

Use `scripts/install_community_pack.py --archive <local.zip> --sha256 <archive-hash> --catalog <installed/site/ai_ad_editor/material_data/model-packs.json> --id <pack-id> --target <new-local-path>`. The local parent must exist; target must not. The installer verifies the installed CLI's manifest pin and every file before moving its staging directory. It refuses overwritten targets, wrong digests, missing/extra/duplicate files, unsafe paths and modified model data. It uses neither network nor global pip.

## Translation, glossary and rights

Supported directions are `en ↔ zh-Hans/zh-Hant`. Simplified/traditional conversion happens on the Chinese side. Text: one paragraph per line, up to 1000; subtitles: up to 1000 cues; each unit up to 512 model tokens. Reaching the decoder limit is an error. Source text, translation, scores, model digest and cue timing are retained.

```json
{"entries":[{"source":"background music","target":"BGM","variants":["背景音乐"]}]}
```

This is explicit post-editing, not constrained decoding. If a source term occurs but the expected translated variant cannot be found, the command refuses output. The actual generic-model error `speech`→“演讲” remains documented; video context needs review. Retained cue times do not mean new forced alignment.

Original OPUS archives carry CC-BY-4.0. Where a model card has a conflicting Apache label, the actual archived license/attribution is retained. Kokoro weights are Apache-2.0; this workflow does not clone an uploaded person. Generated speech/derived mixes remain `unverified/internal` in the project ledger until project-context/output rights are reviewed.

## Actual evidence and cases

[359-file catalog](COMMUNITY_MATERIAL_CATALOG.md) · [103 voices and generated audition scope](COMMUNITY_VOICES.md) · [Local package and installation](COMMUNITY_LOCAL_DELIVERY.md) · [CPU evidence](../../docs/validation/evidence/community-materials-20261025-r1/cpu/verification.json) · [GPU evidence](../../docs/validation/evidence/community-materials-20261025-r1/gpu/verification.json).

The actual edit is 12 s, 360×640, 30 fps, 360 decoded frames, with separate audio, SC captions, TC title, look/SFX and editable-package round trip. Speech/mixes remain in the local delivery folder while publication rights are unresolved. Public examples use verified open resources without redistributing those generated voices. The full local output and JSON response paths remain in the evidence.

CPU: 46 actual commands; GPU: 15 actual commands, separate from historical regression totals. Tests include three voices, UTF-8 input/speed, unordered/overlapping millisecond cues, corrupt/missing/extra pack files, strict CUDA and explicit CPU fallback. Human listening, semantic approval and complete CapCut parity remain open.
