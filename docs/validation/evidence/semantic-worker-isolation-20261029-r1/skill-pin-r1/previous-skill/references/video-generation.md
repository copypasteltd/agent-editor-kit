# Generate editable local video

Use `media generate` for text, a first image, a last image or an explicit
first/last pair. Inspect installed help and
`capabilities.generative_video_editing.complete_video_generation` first.
Use an explicitly registered native CUDA VACE adapter and existing local
weights/runtime/evidence. The base archive contains no model weights.

```powershell
$generationArgs = @('media', 'generate', '--project', $project,
  '--adapter-id', $adapterId, '--asset-id', 'generated-shot-01',
  '--mode', 'first-last-to-video', '--first-asset-id', $firstAssetId,
  '--last-asset-id', $lastAssetId, '--width', '256', '--height', '144',
  '--frames', '17', '--fps', '12', '--image-fit', 'contain',
  '--prompt', $reviewedPrompt, '--inference-steps', '18', '--seed', '230',
  '--window-frames', '17', '--window-overlap', '4',
  '--apply', '--track-id', 'track_video_1')
& $avk @generationArgs --dry-run
& $avk @generationArgs
& $avk validate --project $project
```

Modes: `text-to-video` uses no images; `image-to-video` uses first only;
`last-frame-to-video` uses last only; `first-last-to-video` uses both.
Use returned registered image IDs. Choose `reject|contain|cover|stretch`
explicitly; images are 8-bit SDR, oriented and flattened on black.
Known endpoints are retained by composition and independently hash checked.
They do not demonstrate generated identity/motion quality. Inspect interior
frames and the approach to each retained endpoint before client delivery.

Inspect `data.generation.result.worker` for real CUDA provider/model calls,
input shapes, admission and timing. Compare requested frame count/FPS with the
decoded result, endpoint checks and RGBA roundtrip. Generation creates silent,
opaque lossless MOV assets; author audio/captions separately. Default rights
are unverified/internal with model/image dependencies. Show actual local
previews with mode, prompt, seed, fit and review status; do not present a
procedural condition image as generated output.

Use a fresh asset ID for a new attempt. Apply only to an explicit unlocked
video/overlay track. Portable recipes survive project packaging and fragment
reuse. For interrupted jobs, read [job-recovery.md](job-recovery.md); cleanup
does not resume diffusion from a checkpoint. The generation timeout excludes
adapter/image integrity preflight and metadata commit.

An application/runtime upgrade requires explicit visual-adapter registration
with the current implementation and a fresh adapter ID. Preserve prior records
and generated assets for reproduction.

[Full workflow and evidence](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/VIDEO_GENERATION.md)
