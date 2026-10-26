# 本地 GPU 视频生成 / Local GPU video generation

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

CLI **0.1.33 / alpha.4-local.31** adds `media generate` to the existing native
Wan2.1 VACE 1.3B implementation. It uses the registered local CUDA model,
creates a new video asset and optionally places an ordinary editable clip on
an explicit track. All generation runs through native Windows processes.
The application archive contains the controller and renderer; existing model
weights, native Torch/Diffusers runtime and license evidence remain separate.

## 生成模式 / Modes

| `--mode` | 条件参数 / Conditions | 实际行为 / Behavior |
|---|---|---|
| `text-to-video` | Prompt | Generate every frame from grey RGB/white mask conditions. |
| `image-to-video` | `--first-asset-id` | Condition on the preprocessed first image, retain that first frame and generate subsequent frames. |
| `last-frame-to-video` | `--last-asset-id` | Condition on the last image, generate preceding frames and retain the last frame. |
| `first-last-to-video` | Both image IDs | Condition on and retain both endpoints; generate the interior. |

端点保留是明确的合成约束，不能作为模型身份、运动或提示词遵循已通过的证据。
Endpoint retention is a composition contract. Generated motion, identity,
prompt adherence and transition into the known endpoint require separate review.
Long clips use bounded joint windows; `previous` conditions later windows on
already emitted overlap. This is not full-video attention or checkpoint resume.

## 使用流程 / Workflow

Use the registered `$agent-ffmpeg-local-editor` launcher. The variables below
refer to actual existing local files and the IDs returned by ingestion.

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk media generate --help
& $avk project init $project

# Explicit existing model/native Python/evidence; no dependency download.
& $avk media adapter register --project $project --adapter-id vace-local `
  --engine diffusers-wan-vace-local-v1 --model-path $modelDirectory `
  --executable $nativeModelPython --evidence $modelEvidence `
  --device cuda --license-spdx Apache-2.0 --verification-status unverified `
  --permitted-use internal

# Ingest supplied SDR images and use their returned asset IDs.
& $avk media ingest --project $project --input $firstImage
& $avk media ingest --project $project --input $lastImage

$generationArgs = @('media', 'generate', '--project', $project,
  '--adapter-id', 'vace-local', '--asset-id', 'generated-shot-01',
  '--mode', 'first-last-to-video', '--first-asset-id', $firstAssetId,
  '--last-asset-id', $lastAssetId, '--width', '256', '--height', '144',
  '--frames', '17', '--fps', '12', '--image-fit', 'contain',
  '--prompt', 'An amber bottle on a blue tabletop. Soft light and a slow camera move.',
  '--seed', '230', '--inference-steps', '18', '--window-frames', '17',
  '--window-overlap', '4', '--apply', '--track-id', 'track_video_1')
& $avk @generationArgs --dry-run
& $avk @generationArgs
& $avk validate --project $project
& $avk preview frame --project $project --frame 0
& $avk render --project $project --output $previewMovie
& $avk convert export --project $project --target-format package --output $editablePackage
```

For text-only generation omit the image flags and use `text-to-video`. Without
`--apply` and `--track-id`, the result is registered as an asset only. With apply,
choose a video/overlay track and a nonoverlapping timeline start, or an explicitly
overlap-enabled track. Audio and captions can be authored through the existing
independent commands. Generation creates no audio.

## 参数与资源 / Parameters and resources

The requested raster is the model raster: edges must be multiples of 16 within
64–2048, frames 5–4097, rational FPS 1–60 and duration at most 600 seconds.
These are admission bounds, not a guarantee that a GPU can run every combination.
The default is 512×288, 81 frames at 16 FPS, 17-frame windows/4 overlap and 30
steps. Window arrays are limited to 512 MiB, including the selected overlap
configuration; Torch, model weights and GPU workspaces have separate costs.
Actual CUDA admission checks physical/free memory before text weights, video
weights and each nonempty window. No CPU model fallback or process eviction occurs.
Large checkpoint integrity reads and cold model loading can dominate command
latency. Compare complete CLI time with the recorded generation/model-window
timings; this implementation has no persistent GPU model host.

Images must be registered, hash-matching single 8-bit SDR images, at most 16M
pixels. HDR/ICC/high-precision images require an explicit prior conversion.
`contain` pads with black, `cover` crops, `stretch` resizes and `reject` requires
the exact output size. EXIF orientation is applied. Transparency is flattened
on black. The output is opaque 8-bit RGB stored as lossless QTRLE/ARGB MOV.
This feature does not generate a physical matte or HDR video.

`--storage-budget-mib` bounds a conservative condition/output storage estimate;
ordinary per-file project limits also apply. It is not a disk-space reservation.
`--timeout-seconds` covers condition construction, the native model pipeline
and its final checks; adapter/image integrity preflight and metadata commit
remain outside that timer. Integrity reads use the existing command read locks.
Cancel markers are checked during generation and before publication. OS-blocked
I/O is not forcibly preempted.

## 返回、迁移与恢复 / Results, portability and recovery

Inspect `data.generation`: the full condition/mask RGBA hashes, actual worker
provider, model calls/input shapes, GPU memory admission, inference timing and
encoded RGBA roundtrip are retained. Each supplied endpoint also has an
independent decoded-output hash check. `data.generated_clip` identifies the
editable clip, and `data.asset.uri` points to `assets/derived/<asset-id>.mov`.

The asset stores a digest-bound `source.video_generation` recipe with mode,
prompt/sampling, raster/clock, fit policy and image IDs/hashes. It survives
ordinary project packaging; fragment reuse rebinds image IDs and recomputes the
recipe digest. Package conversion does not include model weights or turn a
historical adapter path into a new runnable installation.

After upgrading/moving the application, register the current native model
implementation under a fresh adapter ID before new inference. Existing visual
adapters pin their implementation paths/bytes; keep the old records for
reproduction. Previously generated assets remain ordinary media in the project.

Conditions, masks and private pipeline files live in an owned
`video-generation` job. Publication writes ownership/hash intent before moving
the movie into derived assets. Project/rights/operation writes participate in
the existing transaction. Cancel, timeout and write failures roll back
uncommitted output. After a hard interruption, use
`project recover --project $project --cleanup-jobs --dry-run`, inspect the
result, then run it without dry-run. Committed assets, changed files and live
leases remain protected. See [job recovery](JOB_RECOVERY.md).

Generated rights default to unverified/internal, retaining model and condition
image dependencies. Check Rights Ledger before any customer/public use. Technical
success does not establish natural generation quality, commercial rights or
full CapCut equivalence. [Official Wan pipeline documentation](https://huggingface.co/docs/diffusers/v0.38.0/en/api/pipelines/wan)
describes the underlying black-known/white-generate conditioning model.
