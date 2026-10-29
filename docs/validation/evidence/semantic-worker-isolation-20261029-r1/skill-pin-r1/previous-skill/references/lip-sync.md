# Local neural lip sync

Use this reference when a supplied portrait/video should speak a supplied audio
track, or when rerunning an existing lip-sync recipe. Use the pinned installed
CLI through `scripts/run.ps1`; do not call source code or download dependencies.
Full workflow, model pins, limits and case: `docs/product/LIP_SYNC.md` in the
repository, or [the maintained guide](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/LIP_SYNC.md).

1. Inspect `lipsync generate --help`, actual source geometry, audio duration,
   source/voice rights and `lipsync adapter inspect`. This command requires a
   separately registered local MuseTalk 1.5 native CUDA adapter and existing
   safetensors. Registration never installs Torch/models or falls back to CPU.
2. Ingest source image/video and speech as separate assets. Author an explicit
   face/chin pixel box or output-frame-25fps box keys. Use actual returned IDs.
3. Run `lipsync generate --project ... --adapter-id ... --source-asset-id ...
   --audio-asset-id ... --asset-id NEW_ID --face-box X0 Y0 X1 Y1 --dry-run`.
   Inspect the complete sample selection, frame count, tail padding and quotas.
4. Execute with the same parameters. For editable delivery add `--apply
   --video-track-id VIDEO_TRACK --audio-track-id AUDIO_TRACK`. The two ordinary
   clips share a link ID; use existing linked edits or deliberately unlink.
5. Review original versus generated mouth and chin across actual interior
   frames, then listen to the complete output with speech. A GIF has no audio.
   Confirm returned real CUDA model-forward counts, no network events,
   complete RGBA/PCM roundtrip and process/stream cleanup. Transport proofs do
   not certify natural motion, identity, teeth, occlusion or perceptual sync.
6. Validate/render/export an editable package normally. To revise, use
   `--recipe-asset-id EXISTING --asset-id NEW_ID`, optionally override audio,
   source, boxes, ranges, mask/feather or seed. Retain old output for comparison.

The learned face raster is 256×256 and output clock is fixed at 25 fps. Original
decoded PCM keeps its sample rate and channels; all selected samples remain,
with under 40 ms tail padding. Whisper uses a separate mono16k copy. Source
video must cover the output unless `hold` or complete-video `loop` is explicit.
A single image repeats explicitly; looping a video subrange requires preparing
that independent asset first. Boxes interpolate in output-frame coordinates,
begin at 0 and must stay in range. No implicit face detection or tracking.

`--mask-top` (0–0.8) protects upper face; `--feather-pixels` (0–32) blends the
semantic skin/lips/mouth mask inside the authored box. All alpha bytes, hidden
RGB at alpha0 and RGB outside that box are retained. The blend is encoded8bit
SDR: preprocess HDR, ICC, rotation, non-square pixels/interlacing explicitly.
This feature retains existing source motion; it does not create full body
animation or an accepted digital-human performance. Generated rights begin
unverified/internal and retain separate source/audio/model dependencies.

For failures inspect returned diagnostic IDs and bounded pipeline logs. Use a
finite timeout/cancel marker and `project recover --cleanup-jobs` for interrupted
owned workspaces. Keep user files and other GPU jobs intact. The 512MiB owned
array budget is not peak RSS or total CUDA usage. Show actual previews for
client selection; record which visual and listening checks were performed.
