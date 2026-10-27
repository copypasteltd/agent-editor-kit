# Global and interval Float32 grading

CLI0.1.39 adds [highlight Bloom/Halation](highlight-glow.md) to selected-root
intervals, using the same local author clock and one post-composition
application. Native optics/glow can use the actual owned GPU; other
adjustment operators retain their existing CPU implementation.


Use the installed CLI 0.1.25 for `settings.adjustments` in an explicit
`float32-native-v1` project. Read the actual capability field
`standard_native_float_render.adjustments`. This uses the same supported
Float32 effect compiler as clip effects, with its explicit signal, alpha,
animation, range and workspace requirements.

Place the ordered declarations in project `settings.adjustments`, then use
the ordinary validate → frame/range preview → render → quality → package
workflow. Register sources, font and LUT rights normally. This field is part
of the editable project; there is no new command or separate Skill.

```json
[
  {"id":"base-grade","effects":[{"type":"exposure","parameters":{"amount":-0.1}}]},
  {"id":"darken-window","start_tick":90000,"duration_tick":270000,"effects":[
    {"type":"exposure","parameters":{"amount":0},"keyframes":[
      {"property":"amount","keyframes":[
        {"at_tick":0,"value":0,"interpolation":"ease_in_out"},
        {"at_tick":270000,"value":-0.6,"interpolation":"linear"}
      ]}
    ]}
  ]}
]
```

The example assumes 90000 ticks/s. Effects execute in array order, after all
video and subtitle tracks and before delivery conversion. Apply them once to
the selected root sequence, including when a child is selected as the output.
Nested children do not receive the global grade again. A clip effect executes
earlier and therefore can produce a different result.

Intervals are `[start_tick, start_tick + duration_tick)`. Keyframes use exact
selected-sequence tick minus layer start, retaining original duration when
the selected sequence is shorter. The project validator still checks authored
intervals against the longest project sequence. Explicit duration bounds the
keys. Six existing interpolation modes retain their own contracts. Disabled
layers/effects do nothing; unsupported enabled effects fail.

For a local CUBE LUT use `type: lut3d`, a project-relative `parameters.path`,
and explicit `input_signal`/`output_signal`, e.g. both
`{"primaries":"bt709","transfer":"linear"}` for a LUT designed for that
domain. Do not label an arbitrary display LUT as linear. Its bytes and any
library manifest become render dependencies and are read-locked through
publication. Editable package export includes the referenced LUT bytes.

Inspect `delivery.pixel_pipeline.timeline.adjustments` for the protocol,
compiled layers, applied-frame and layer-application counts. Inspect actual
preview, encoded pixels and complete audio; exposure can exceed delivery
range. Select a valid range policy explicitly. Adjustments use CPU Float32
surfaces; compatible GPU projection/text composition can run in the same
task. They do not alter audio or establish HDR, ICC, realtime performance or
natural-content quality. The declared limits are 128 layers, 128 effects per
chain, 4096 total effects and 8 MiB JSON; per-effect quotas are not process RSS.

The actual installed/registered-Skill case, source and silent GIF are linked
from [the workflow](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/FLOAT_ADJUSTMENTS.md).
