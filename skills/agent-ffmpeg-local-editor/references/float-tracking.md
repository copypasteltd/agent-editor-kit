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
as rendering. CLI 0.1.31 samples actual projected source pixel/mask/effect alpha
and transports point footprints through its own edge and paired transitions.
Source contribution multiplies the target's saved base alpha once. Optional ROI scaling/relative rotation uses geometry at the original
target author start; random-access previews do not change that reference.

The renderer accepts saved observations for CFR/VFR and nonzero demux origins.
Analysis cadence and accuracy are separate: the built-in template tracker
samples rescaled RGB frames and can drift on occlusion, scale changes or cuts.
Do not claim native-frame detections or natural identity quality from an
interpolated observation. Higher track occlusion and natural identity require
separate review. Source crop/range/mute, actual alpha, five mask shapes and
59 transition source contributions are evaluated explicitly.

Coordinate math is CPU. Eligible affine/normal composition/text can use the
explicitly probed native GPU path; CPU crop and effects remain CPU. Do not
claim a GPU model tracker or an entirely GPU-resident pipeline.

Budgets: 128 bindings, 64,000 total observations, 4,000 observations per binding,
16 dependency levels. Cycles and changed source hashes reject. Sources remain
square-pixel/unrotated; ROI scale uses the existing 0.01..20 clamp. Use editable
project packages to preserve observations. CLI 0.1.32 adds verified native
baking for MLT/OTIO/draft and explicit baked native exports below. Clearing a
native binding restores authored transforms; it does not bake the current pose.

## Continue editing a bound clip (CLI 0.1.27)

Use `timeline compose` for split/trim/ripple insert/delete, or `timeline edit`
for insert/overwrite/lift/extract and retained-handle roll/slide. Preview the
JSON plan with `--dry-run` before applying the same input. Use the actual IDs
returned by the previous edit: splitting replaces the source ID with its two
piece IDs. The native planner updates each surviving follower's
`tracking_binding.source_fragments` with explicit track/clip references. It
keeps the observations, source hash, keys and complete author clock intact.

`reference_output_tick` pins the original complete-source output clock used
for ROI scale/relative rotation. Keep this value on later edits. A gap in the
route hides the follower; an explicit empty route after source removal is a
retained hidden binding, not an instruction to restore unbound transforms.
Inspect that state in the plan and rebind explicitly when replacing footage.

Locked follower references reject atomically. Overlapping source fragments are
ambiguous and reject; routes admit up to 128 fragments per binding and 4,096
total references. Shared-author retime is supported as described below. Export
baking freezes the graph after editing; it does not bypass editing guards.
Deliver the editable package after verification.

## Actual visibility and spatial transitions (CLI 0.1.31)

Native bindings automatically use `native-transition-point-footprint-v1`.
Preview every transition boundary and any masked/partially transparent source.
Inspect each tracking row's `visibility`, `active`, `reason` and `values`.
No transition: sample the actual projected alpha bilinearly and multiply the
separate scalar opacity. During an edge/pair, an alpha-weighted bilinear point
footprint travels through the actual transition sampling kernel; its mass
(clamped 0..1) controls visibility and its centroid controls position. Original
PTS and saved observations stay unchanged. Generated black/white mattes have
no source contribution. A lost anchor hides the label; a missing or degenerate
required ROI endpoint hides it with `source-ROI-footprint-unobservable`.

Own edge followed by a paired transition retains the full Float64 density
between operations. Colour-dependent patterns read the real RGBA, not a probe
colour. Masks use exactly the rendered crop-before-mask/source-before-project
ordering. This measures source contribution before higher track occlusion;
pixelize/blur/warps may duplicate or lose footprints and do not establish a
natural object's identity. Review natural scenes separately.

Independent spatial edges now survive native complete-output retime. A paired
endpoint still requires selecting its complete parent group. Cyclic dependencies
through a transition peer reject before pixel I/O, including conservative cases
whose windows might not intersect. Additional visibility dependency depth is
limited to 64; the direct leaf cache is per frame and at most min(workspace/4,
64MiB). Footprint calculation is CPU with bounded tiles and cancellation;
eligible projection/composition retains the probed GPU path.

[Workflow and C41](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/TRACKING_VISIBILITY.md)
· [Silent preview](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/tracking-visibility-20261026-r2/edited.gif)
· [Editable case](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/tracking-visibility-20261026-r2/editable-tracking-visibility.aevpkg.zip)

[Editing workflow, real case and silent preview](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/TRACKING_EDITS.md)

## Original C36 preview

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

## Physical source edits (CLI 0.1.28)

Use `timeline edit --input request.json --sequence-id ID --dry-run` for
`{"action":"slip","clip_id":"ID","delta_source_tick":N}` or
`{"action":"extend_source","clip_id":"ID","head_tick":N,"tail_tick":N}`.
These edit the finite registered source and preserve timeline link groups.
Apply the planned project hash with `--expected-project-sha256 HASH`.

Source slip uses the new original PTS with the existing observations; ROI and
rotation recalibrate at the pinned output reference. Unobserved source regions
hide the follower. Real head extension accumulates `author_offset_tick` on each
retained source fragment, preserving the prior ROI/rotation reference even when
only one fragment expands. Extending a bound video target shifts its base
opacity keys along with its author clock. Source-handle roll/slide use the same
logic. Locked dependent rewrites and insufficient physical handles reject
atomically. Preview changed intervals and check linked audio before delivery.

Integer-grid piecewise constant curves now use rational source-clock inversion;
nonconstant curves keep the existing bounded float mapping. This does not
establish natural tracking/occlusion or arbitrary nonlinear timing precision.

[Full workflow and C38 preview](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/TRACKING_SOURCE_EDITS.md)

## Magnetic synchronized reorder (CLI 0.1.29)

With an explicit video main track, use:

```json
{"action":"reorder","clip_ids":["shot_c"],"before_clip_id":"shot_a","options":{"sync":true},"sync_span_policy":"split"}
```

Plan with `timeline edit --dry-run`, inspect `sync_splits`, `moves` and
`tracking_binding_changes`, then apply with its `--expected-project-sha256`.
Native Float32 sources and followers can cross main-track cuts. Retained pieces
keep original author windows and observations; source routes are repaired from
the complete pre-cut graph, including chains, pinned ROI/rotation references
and per-fragment author offsets. Linked video/audio keep region-specific links.
Review sync opt-outs, locked dependants, changed source coverage and the encoded
output. Legacy non-native tracking cuts and true transition endpoints retain
explicit guards. CLI 0.1.30 adds shared-author retime below. Natural identity/
occlusion quality remains a separate acceptance condition.

[Full workflow and actual C39 preview](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/TRACKING_MAGNETIC.md)

## Shared author output retime (CLI 0.1.30)

```json
{"action":"retime","clip_ids":["source_clip"],"transform":{"speed":2}}
```

For intersections following a separate main shot, explicitly request
`"sync_content":"retime"` and enable sync. The default `ripple` policy keeps
its existing meaning. Plan with `timeline edit --dry-run`; inspect
`steps[].shared_author_context`, every retimed member, readonly reference
context, parent link group, retained outside routes and the clock/duration.
Apply its project fingerprint with `--expected-project-sha256`.

The native planner closes required tracking dependencies in both directions,
copies complete author clips into one shared child and makes each parent slot
select its own output through `sequence_clip_id`. Saved observations, crop/TRS,
ROI reference, alpha and effects keep their original clock. Layer order and
noncommutative external blending stay in the parent. Audio selects private
instances so sibling video/label outputs do not duplicate the sound.

Keep the generated parent link group when moving or retiming these outputs
together. Edit the shared child's source/binding for subsequent tracking
changes. Explicit unlink or `linked:false` separates complete authored outputs;
it does not create live bindings between the independent parent wrappers.
Locks, disabled dependency sync locks, real-transition endpoints and resource
limits reject before commit. Default-renderer fallback and intermediate-format
equivalence are unavailable; retain the native package or agent JSON graph.

Show the actual C40 GIF/MP4 to explain the selected speed and preserve the
editable package. Its synthetic 2x case verifies all 18 Float32/decoded frames,
original native PTS/geometry and the complete 72000-sample stereo output
against an independent FFmpeg tempo oracle, including package/queue checks.
Review real client footage and sound separately before delivery.

[Commands, scope and actual C40 preview](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/TRACKING_RETIME.md)

## Verified native tracking bake

CLI 0.1.32 exports a frozen native binding graph as ordinary hold keys. Preserve
the dynamic project when more retime, geometry or visibility edits are planned.

```powershell
& $avk convert export --project $avkProject --target-format package `
  --bake-tracking --output $bakedPackagePath
& $avk convert export --project $avkProject --target-format agent-json `
  --bake-tracking --output $bakedJsonPath
& $avk convert import --input $bakedPackagePath --output $newProjectDirectory
```

Native exports evaluate actual source PTS, masks and transition visibility,
including nested instances and transition peers. They rerender the baked graph
and compare every Float32 RGBA display frame. Limits: 20,000 total sequence
frames and 256,000 target samples. Conflicting author-clock demands, steps that
integer ticks cannot represent, changed inputs, or pixel mismatches fail. No
model is run and no frame values are rounded to hide errors. The original
bindings are retained in `.source-agent.json`; preserve the source project and
ordinary editable package too, including fonts, rights and assets. An unsampled
muted/unreachable target is listed in the receipt and has no playback keys.

OTIO, MLT and plaintext draft exports bake automatically and retain format loss
reports. Their players still need independent acceptance for unsupported
effects, graph structure and colour; an internal exact bake is not external
renderer parity. Draft strict mode continues to reject Baked/Approximate/losses.
After editing clocks, display FPS, geometry or visibility, bake the original
dynamic project again. [Workflow](../../../docs/product/TRACKING_BAKE.md).

CLI 0.1.32 also accepts `.mlt` imports, retains rational MLT profile FPS, and
preserves tick rate/display FPS/duration in local OTIO metadata. Overlapping
draft segments retain their target ranges with an explicit Approximate stack
or mix report; strict mode rejects this approximation. Private transition
semantics still require independent acceptance.
