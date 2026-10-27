# 本地神经口型同步 / 本機神經口型同步 / Local neural lip sync

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

CLI **0.1.41 / alpha.4-local.39** adds an actual offline MuseTalk 1.5 CUDA
pipeline. A registered image or video supplies appearance and existing motion;
a separately registered audio asset drives the mouth. The result is a new,
ordinary editable video asset containing lossless RGBA and original decoded
Float32 PCM. `--apply` creates linked video/audio clips on explicit tracks.

实际执行 UNet、Whisper-tiny、SD VAE 和 BiSeNet；不是用字幕、音量驱动几何嘴形或循环图片模拟神经推理。
實際執行 UNet、Whisper-tiny、SD VAE 及 BiSeNet；來源運鏡保留，身體動作及完整表演仍須另外提供。
The trained face raster is 256×256. Identity, natural mouth motion, teeth,
occlusion, profiles and perceptual synchronization require review on each shot.
This implementation does not establish complete digital-human or CapCut parity.

## 工作流程 / Workflow

Use the single registered `$agent-ffmpeg-local-editor`. Model dependencies stay
separate from the application ZIP. `$project`, `$portrait`, `$speech`,
`$modelDirectory`, `$nativeModelPython` and `$modelEvidence` below are explicit
existing local paths. Use the asset IDs returned by ingestion.

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk lipsync generate --help
& $avk project init $project

& $avk lipsync adapter register --project $project --adapter-id mouth-local `
  --model-path $modelDirectory --executable $nativeModelPython `
  --evidence $modelEvidence --device cuda --batch-size 2 --threads 4 `
  --license-spdx 'MIT AND Apache-2.0' --verification-status unverified
& $avk media ingest --project $project --input $portrait
& $avk media ingest --project $project --input $speech

# Explicit x0 y0 x1 y1 pixel box, including the entire face and chin.
# Replace these coordinates after inspecting the actual source image.
$mouthArgs = @('lipsync', 'generate', '--project', $project,
  '--adapter-id', 'mouth-local', '--source-asset-id', $portraitAssetId,
  '--audio-asset-id', $speechAssetId, '--asset-id', 'speaking-01',
  '--face-box', '160', '80', '352', '304', '--seed', '17',
  '--mask-top', '0.45', '--feather-pixels', '3',
  '--apply', '--video-track-id', 'track_video_1', '--audio-track-id', 'track_audio_1')
& $avk @mouthArgs --dry-run
& $avk @mouthArgs
& $avk validate --project $project
& $avk render --project $project --output $previewMovie
& $avk convert export --project $project --target-format package --output $editablePackage

# Keep the original result; make a new asset from its editable recipe.
& $avk lipsync generate --project $project --adapter-id mouth-local `
  --recipe-asset-id speaking-01 --asset-id speaking-02 --seed 19 --dry-run
```

`--source-asset-id`, `--audio-asset-id`, region, ranges and blend parameters can
override a reused recipe. An explicitly different audio asset uses its complete
range by default. Rerun does not overwrite the old asset or existing timeline
clips. A package carries source image/video, audio, generated output and recipe;
models remain explicitly registered dependencies when rerunning on a new machine.
Clip trim, move, linked edits, effects, captions and rendering use the ordinary
editor. Unlink the pair through existing timeline editing when independent
timing is intentional. No additional public Skill is registered.

## 时钟与区域 / 時鐘與區域 / Clocks and region

The learned model clock is fixed at **25 fps**. Audio selection uses original
decoded sample indices at 8–96 kHz and 1–8 channels. The complete selected PCM
is preserved. Output duration rounds up to the next 25 fps frame; only the tail
is padded, by less than 40 ms. Whisper receives a separate 16 kHz mono copy.
No time stretching, voice replacement or dropped selected audio is implicit.
The ordinary project renderer uses the project's display frame rate. C51 retains
the 133-frame/25 fps neural master; its default 30 fps MP4 has 160 frames. The GIF
shows all 133 master frames over exactly 5320 ms. These clocks are recorded
separately, and complete package-render equivalence is checked at the export clock.

For moving faces, use `--boxes-file` instead of `--face-box`:

```json
{
  "clock": "output-frame-25fps",
  "keys": [
    {"frame": 0, "box": [160, 80, 352, 304]},
    {"frame": 24, "box": [168, 80, 360, 304]}
  ]
}
```

Box keys begin at output frame 0, are strictly ordered, and remain within the
requested frame count. Coordinates interpolate linearly and round to pixels;
the last key holds. Each side must be at least 32 pixels and stay inside the
source canvas. Automatic face detection/tracking is not part of this command.
Boxes refer to the normalized output frame clock, after source range/FPS choices.

`--mask-top` suppresses the upper fraction of the selected face box (0–0.8);
`--feather-pixels` controls spatial feathering (0–32 pixels). BiSeNet selects
face skin/lips/mouth, then the explicit box bounds the applied patch. RGB outside
the box, invisible RGB under source alpha 0, and all alpha bytes are preserved.
Blending uses encoded 8-bit SDR RGB. HDR, high-bit-depth, ICC images, rotated,
anamorphic or interlaced material must be explicitly preprocessed first.

| Source | Behavior |
|---|---|
| Single image | Repeated explicitly for the chosen audio duration. Animated images are rejected. |
| Video `--source-mode once` | Default; selected source interval must cover the complete output duration. |
| Video `hold` | Use the chosen interval, then explicitly hold its final frame. |
| Video `loop` | Explicitly repeat the complete source video. Subrange loops require a separately prepared asset. |

Use `--source-start-seconds` / `--source-end-seconds` for once/hold video ranges;
use `--audio-start-seconds` / `--audio-end-seconds` for audio. Existing source
audio is not mixed into the result: the explicitly selected speech asset is used.

## 本地依赖与来源 / 本機依賴與來源 / Dependencies

The application never downloads models, runs remote Python or loads pickle.
The fixed graph loads explicit local **safetensors** with strict state dictionaries.
The pinned old SD VAE attention names are mapped to current Diffusers names;
missing, duplicate or incompatible keys still fail. CUDA absence/admission
failure stops the job; there is no automatic CPU inference fallback.

The existing native Windows model interpreter used by this implementation has
Torch 2.13.0+cu130, Diffusers 0.39.0, Transformers 5.14.1, Safetensors 0.8.0,
OpenCV 5.0.0.93, NumPy 2.4.6 and Pillow 12.3.0 in its native package inventory.
The installed worker puts the application's pinned site directory first:
the actual C51 model receipt records **NumPy 2.4.2**, alongside the Torch,
Diffusers, Transformers and Safetensors versions above. Native package inventory
and effective worker imports are distinct. No virtual environment or package installation
is performed by registration or generation. Actual versions are recorded in
each model response; other dependency combinations require their own acceptance.

Expected model directory:

```text
unet/config.json
unet/diffusion_pytorch_model.safetensors
vae/config.json
vae/diffusion_pytorch_model.safetensors
whisper/config.json
whisper/preprocessor_config.json
whisper/model.safetensors
parser/model.safetensors
conversion.json
licenses/MuseTalk-LICENSE.txt
```

Original MuseTalk/BiSeNet `.pth` files were acquired separately and converted
once in development with `torch.load(weights_only=True)`, then reloaded and
compared tensor by tensor. They are not loaded during product inference.
The maintained acquisition/conversion scripts and their receipts are under
`scripts/*lipsync*20261027.py` and the evidence linked below. Registration binds
the model files, fixed configs, evidence, native Python and implementation files
to hashes. Windows read locks freeze inputs while they are in use. The worker
blocks network calls before importing model packages.

| Component | Exact upstream revision | License/source |
|---|---|---|
| MuseTalk code | `0a89dec45a0192b824e3cf4daf96c239440c5ed8` | [MIT](https://github.com/TMElyralab/MuseTalk/blob/0a89dec45a0192b824e3cf4daf96c239440c5ed8/LICENSE) |
| MuseTalk 1.5 checkpoint | `2bcb936e2fddb4d86db4c62fd45b387d0c061571` | [Pinned official model/license](https://huggingface.co/TMElyralab/MuseTalk/tree/2bcb936e2fddb4d86db4c62fd45b387d0c061571) |
| SD VAE ft-MSE | `31f26fdeee1355a5c34592e401dd41e45d25a493` | [MIT model card](https://huggingface.co/stabilityai/sd-vae-ft-mse/tree/31f26fdeee1355a5c34592e401dd41e45d25a493) |
| Whisper tiny | `169d4a4341b33bc18d8881c4b69c2e104e1cc0af` | [Apache-2.0 model card](https://huggingface.co/openai/whisper-tiny/tree/169d4a4341b33bc18d8881c4b69c2e104e1cc0af) |
| BiSeNet graph/checkpoint | MuseTalk pinned graph; separate acquisition receipt | MIT; complete checkpoint includes the backbone. |

See [acquisition receipts](../validation/evidence/native-lipsync-20261027-r1/acquisition-files.json),
[conversion receipts](../validation/evidence/native-lipsync-20261027-r1/weight-conversion.json)
and the bundled `LIPSYNC_LICENSES.txt`. Model licensing does not grant rights to
a source person's likeness, supplied speech or every possible generated result.
The editor retains separate source/audio/model dependencies in the Rights Ledger;
generated assets start as `unverified` / `internal` pending the relevant review.

## 资源、失败与证据 / Resources and evidence

Limits: at most 600 seconds / 15,000 frames, source edges 32–4096 pixels,
1–8 frames per model batch, 512 MiB owned frame-array budget and a maximum
2 GiB output asset. A conservative workspace bound must fit the explicit
`--storage-budget-mib` (16–2048) and free disk. This is not a peak RSS or CUDA
memory guarantee: Torch weights, activations and native libraries are separate.
The GPU admission report and actual peak allocation are recorded.

`--timeout-seconds` bounds pipeline processing and verification after CLI preflight.
Initial registry/source hashing is a separate admission step. `--cancel-file` supports
an explicit local cancellation marker. Owned Windows jobs reclaim decoder,
worker and encoder processes; managed workspaces support interrupted publication
recovery through `project recover --cleanup-jobs`. Metadata transactions roll
back failed publication. Failure diagnostics retain bounded logs and receipts.
The full encoded qtrle/argb output is decoded and SHA-checked against every RGBA
frame; all original-rate/channel Float32 PCM is decoded and compared separately.
These proofs establish transport/clock preservation, not natural lip quality.

Current actual case, tests, source/output/GIF and known limits are linked from
[C51](CASES.md#c51-native-lip-sync). Earlier failed acquisition/model/protocol
attempts remain in [the evidence directory](../validation/evidence/native-lipsync-20261027-r1).
