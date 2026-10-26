# 时间线、关键帧、运镜、转场、嵌套 / timeline

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Edit JSON → tracks/motion/transitions/nesting

Commands: `timeline compose/edit; motion apply; motion pack list/inspect/create/capture/apply`. Explicit track/clip targets and author clocks.

## Workflow

Inspect `schema show`, `effects list` and `timeline compose --help`. Author an edit JSON with integer ticks,
source ranges, explicit tracks and audio. Use `timeline compose` or `timeline edit` only with supported operations.
Use `preview frame` or `preview range` to inspect actual results before rendering. Keep native PTS and nested clocks.

For looks and client choices, read [looks](../../looks.md) and [actual visual selection](../../client-look-selection.md).

For reusable paths and saved keyframe animation, read [motion packs](../../motion-packs.md).
For a marker or label following actual source frames in the native Float32
renderer, read [native PTS tracking](../../float-tracking.md). Keep source
observations editable; do not replace them with guessed display keys.
For explicit linear Float32 text, typewriter, word highlights and plain SRT,
read [float text](../../float-text.md). Retain explicit fonts and original clocks.
Inspect actual previews and parameters; apply on the visible output clock, preserve
source retiming, and replace conflicting whole property tracks only explicitly.

## Dynamic crop and nested projection (CLI 0.1.19)

Read [motion-packs](../../motion-packs.md) for the editable combination workflow. Dynamic crop and child crop/fit/TRS automatically reuse pure scanline parameters. Bilinear and source-axis box area sampling retain their existing precision and alpha contract; area is explicit via `--sequence-sampling area`. Keep `--sequence-memory-mib` explicit for overrides; no silent quality reduction or quota expansion. CPU is the default. For CLI 0.1.20 native GPU samplers, read [projection-gpu](../../projection-gpu.md); hardware encoding is separate.
