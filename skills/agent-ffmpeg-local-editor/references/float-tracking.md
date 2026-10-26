# Native PTS tracking bindings / 原生帧跟随

CLI 0.1.26 adds dynamic `tracking_binding` playback to the explicitly selected
`float32-native-v1` renderer. Read the installed schema/capabilities and
`media track-bind --help` before authoring. Existing legacy CFR bindings remain
on their own renderer. No model is executed when a saved binding is rendered.

## Bind an actual source clip

Ingest a local video and a transparent marker image, then place each on its own
video/overlay track. Retain the returned asset, sequence, track and clip IDs.
Use explicit source/working/output signal declarations from
[Float32 text](float-text.md); declare both video and image sources. The source
and target must be direct visual clips in the same sequence. Nested parents may
retime or reverse that sequence, and overlay containers retain explicit child
audio tracks.

```powershell
& $avk media track-bind --project $avkProject --asset-id $videoId `
  --sequence-id $sequenceId --source-track-id $sourceTrackId --source-clip-id $sourceClipId `
  --target-track-id $labelTrackId --target-clip-id $labelClipId `
  --roi '0.125,0.35,0.063,0.11' --step-frames 1 --max-samples 600 `
  --scale-mode roi --rotation-mode source --apply
& $avk validate --project $avkProject
& $avk preview frame --project $avkProject --frame 0
& $avk preview range --project $avkProject --start-frame 0 --end-frame 36
& $avk render --project $avkProject --output $outputPath
& $avk quality check --project $avkProject --input $outputPath
& $avk convert export --project $avkProject --target-format package --output $packagePath
```

ROI is normalized `left,top,width,height` in the original source raster. Start
with a clear textured object. Without `--apply`, inspect the actual plan and
confidence first. Native plans intentionally return `keyframes: []` and
`sampled_frames: 0`: saved source observations drive the renderer dynamically;
they are not missing display keys. Preserve the target's authored keys and the
binding's original base values. Rebinding retains that original base.

## Clock, geometry and output

The anchor uses the exact original video frame selected by native PTS, rational
time base and demux origin. Its source time follows the same trim, scalar/curve
speed, freeze, reverse, presentation window and nested clock as the picture.
Coordinates use the same actual crop/fit/TRS inverse and pixel-centre convention
as rendering. Source transform/blend alpha multiplies the target's saved base
alpha. Optional ROI scaling/relative rotation uses geometry at the original
target author start; random-access previews do not change that reference.

The renderer accepts saved observations for CFR/VFR and nonzero demux origins.
Analysis cadence and accuracy are separate: the built-in template tracker
samples rescaled RGB frames and can drift on occlusion, scale changes or cuts.
Do not claim native-frame detections or natural identity quality from an
interpolated observation. Masks, transitions and occlusion visibility require
separate review. Source crop/range/mute visibility is evaluated explicitly.

Coordinate math is CPU. Eligible affine/normal composition/text can use the
explicitly probed native GPU path; CPU crop and effects remain CPU. Do not
claim a GPU model tracker or an entirely GPU-resident pipeline.

Budgets: 128 bindings, 64,000 total observations, 4,000 observations per binding,
16 dependency levels. Cycles and changed source hashes reject. Sources remain
square-pixel/unrotated; ROI scale uses the existing 0.01..20 clamp. Use editable
project packages to preserve observations: MLT/OTIO/draft export currently
rejects native bindings until native-clock baking is implemented. Clearing a
native binding restores authored transforms; it does not bake the current pose.

## Client preview

Actual controlled C36 case: local template analysis, animated crop/TRS, following
red marker, reversed overlay child, GPU text and preserved stereo source audio.
Show the input and actual output together; label the GIF as silent and the MP4
as synthetic verification audio. The case checks every native source index,
independent projected position, actual marker centroid and full stereo PCM;
resume/queue and package reimport are checked separately.

[Case and reproduction](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/FLOAT_TRACKING.md)
· [Input](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/float-tracking-20261026-r5/original.native.mkv)
· [Silent GIF](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/float-tracking-20261026-r5/native-tracking.gif)
· [MP4](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/float-tracking-20261026-r5/native-tracking.mp4)
