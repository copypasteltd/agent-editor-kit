# Native CUDA interpolation and editable slow motion

Use `interpolate` with the pinned installed launcher. One public Skill and the
existing timeline/local-models/quality modules cover this workflow.

1. Ingest the actual local **video**, inspect its returned asset ID and rights.
2. Register an explicitly supplied RIFE4.25 inference safetensors directory and
   existing native CUDA Python. Registration records hashes; it installs or
   downloads nothing. Model-directory Python/Pickle is never executed.
3. Plan with `--dry-run`, specifying half-open native frame indices, factor2..8,
   cuts and storage budget. Dry-run probes native frames; it performs no neural
   forward and makes no project metadata changes.
4. Generate a new asset, preview actual output, check original anchors, alpha,
   occlusion, thin lines and cuts, then apply or rerun with a new asset ID.
5. Export an editable package. Preserve sources and recipe. Explicitly register
   the external model again after migration before a neural rerun.

```powershell
& $avk interpolate adapter register --project E:/work/edit --adapter-id rife425 `
  --model-path E:/models/rife425 --executable E:/native/python.exe `
  --evidence E:/models/rife425/SOURCE.json --license-spdx MIT
& $avk interpolate generate --project E:/work/edit --adapter-id rife425 `
  --source-asset-id SOURCE_ID --asset-id smooth_preview --factor 4 `
  --start-frame 0 --end-frame 48 --cut-after-frame 23 --dry-run
& $avk interpolate generate --project E:/work/edit --adapter-id rife425 `
  --source-asset-id SOURCE_ID --asset-id slow_motion --factor 4 `
  --start-frame 0 --end-frame 48 --cut-after-frame 23 `
  --apply --video-track-id track_video_1 --audio-track-id track_audio_1 `
  --playback-speed 0.25
& $avk interpolate generate --project E:/work/edit --adapter-id rife425 `
  --recipe-asset-id slow_motion --asset-id revised_motion --factor 3 --dry-run
```

Omit `--audio-track-id` when the source has no audio. An explicit audio track
is required when audio exists. The generated lossless MOV keeps source duration
and decoded original PCM. `--playback-speed` changes linked editable clips;
ordinary rendering stretches the audio at that speed. Changing the asset FPS
alone does not create slow motion.

Native CFR/VFR PTS and every interval are subdivided equally. All N original
decoded RGBA frames remain byte-exact anchors among N×factor output frames.
The final interval holds the final frame; there is no motion extrapolation.
Synthesized alpha uses actual trained flow/mask on premultiplied RGBA; alpha0
RGB is zero on generated frames. Original anchor hidden RGB remains unchanged.

`--cut-after-frame` is relative to the selected frame range. The default `.35`
threshold measures mean absolute RGB difference; it is not a semantic cut
detector. Use `--scene-cut-threshold 0` to disable it or supply explicit cuts.
Cut/static pairs hold their preceding anchor and do not count as model forwards.
Review flashes, fades, occlusions and transparent hidden colors yourself.

The first audio stream retains rate/channels and selected decoded Float32 PCM,
aligned by actual native video/audio start timestamps. Boundaries round to the
nearest original audio sample. Leading/trailing gaps are explicit zero samples;
unknown source duration is rejected. The generated asset never silently drops
selected original samples. Check the report's rounding error separately.

Limits: NVIDIA CUDA only, no CPU fallback; scale .25/.5/1/2; square unrotated
progressive8bitSDR; up to600 selected seconds,15,000 source/120,000 output frames,
32..4096 pixel edges,512MiB owned CPU arrays and2GiB asset. Conservative storage
admission can reject large cases earlier. These bounds do not describe total
process RSS or guarantee GPU OOM prevention. The pipeline timeout starts after
preflight hashes/native frame probing; use a cancel marker throughout.

Human-facing selection must use actual encoded samples, identify the selected
factor/scale/cut rules, and retain the original next to the preview. RIFE quality
on difficult motion, naturalness, native HDR, semantic cuts, cross-GPU exactness
and the complete CapCut feature goal remain separate acceptance work.

See repository `docs/product/NEURAL_INTERPOLATION.md`, caseC52 and its original,
neural result, held-out reference, GIF, real cancellation and package receipts.
