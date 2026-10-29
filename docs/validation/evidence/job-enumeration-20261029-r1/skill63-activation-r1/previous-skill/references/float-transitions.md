# Float32 transitions and editable groups

CLI 0.1.21 provides real transitions in the explicitly selected
`settings.pixel_pipeline.engine="float32-native-v1"` path. Read installed
`capabilities` → `transitions.float32_native` and the source/working/output
signal requirements before authoring a new project. The default 8-bit renderer
and OpenCL projection have separate contracts; this Float32 path runs on CPU.

For the tested full workflow, source inputs, actual MP4/GIF and editable case,
use [Float32 transition guide](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/FLOAT_TRANSITIONS.md).

## Choose the authoring model

- **Real source handles at an existing cut:** use `timeline transition` with
  the declaration below. The 12 source-handle IDs are `dissolve`, `crossfade`,
  `dip_black`, `dip_white`, `wipe_left/right/up/down`, `slide_left/right/up/down`.
  Asset clips and optional linked explicit audio clips must have enough actual
  source media. The authored cut and sequence duration stay fixed.
- **Already overlapping clips:** author `transition_out` / `transition_in` with
  the same type and `duration` in seconds. The overlap must equal that duration.
  `dissolve`/`crossfade` and spatial patterns pair the two layers and composite
  once. A plain `fade` remains a single-edge opacity envelope.
- **A clip or editable nested group entering/leaving:** a standalone edge
  transitions against transparent RGBA. For example `{"type":"wipe",
  "direction":"right","duration":0.25}` on `transition_in`, or `slide` on
  `transition_out`. This is a layer effect; it does not create source handles.

```json
{
  "action": "add",
  "id": "cut_ab",
  "from_clip_id": "shot_a",
  "to_clip_id": "shot_b",
  "type": "dip_white",
  "duration_tick": 37500,
  "audio": "linked"
}
```

At 90000 ticks/s and 12fps, this is five display frames. The extra odd frame
belongs after the cut; dip reaches its matte at the original cut, using the
actual pre/duration ratio. Set the ticks from the project's real frame grid.

```powershell
& $avk timeline transition --project $project --sequence-id $sequence --input $request --dry-run
& $avk timeline transition --project $project --sequence-id $sequence --input $request
& $avk validate --project $project
& $avk preview frame --project $project --sequence-id $sequence --frame $frame
& $avk render --project $project --sequence-id $sequence --output $output --hardware-encode off
& $avk quality check --project $project --sequence-id $sequence --input $output
```

Use returned IDs, preserve the preview and actual render diagnostics, and
export the editable project when delivering. A dry run is a plan only.

## Patterns, alpha and boundaries

The backend catalogue has 57 xfade patterns plus the two authored-cut dips.
For legacy edge JSON, spell directional wipe/slide as `wipe`/`slide` with an
explicit direction. Other xfade IDs such as `circleopen`, `radial`, `pixelize`,
`zoomin`, `hblur` and `squeezeh` are accepted directly. Catalogue backend IDs
`wipeleft` and `slideup` describe those same directional operations; do not
copy them into fields that use the public `wipe`/`slide` spelling.

Mixing is linear-light premultiplied RGBA, with a public Float32 straight-alpha
boundary. Transparent hidden RGB cannot bleed. Visible extended RGB is retained
except `fadefast`/`fadeslow`, which require 0..1. No automatic clipping or HDR
delivery acceptance is implied. FFmpeg's integer colour arithmetic differs;
wind hashes also depend on the platform's sine implementation.

Keep actual source coverage, native VFR PTS, author keyframes and source-handle
clocks. Parent trim/reverse/freeze/curve clocks remain effective. Paired audio
uses the existing continuous child presentation envelope, including at reverse
boundaries; it is not defined as reversing a previously mixed PCM buffer.

Conflicting endpoints, overlapping pair windows, unavailable real handles,
automatic tail cloning, and non-normal pair blend modes fail explicitly.
Resource quotas are allocation estimates, not total RAM/VRAM limits. Review
client footage, continuous motion and audio independently; the synthetic case
does not establish natural quality or complete CapCut equivalence.
