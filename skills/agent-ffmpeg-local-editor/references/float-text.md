# Linear Float32 titles and captions

For a `settings.pixel_pipeline.engine="float32-native-v1"` project, CLI0.1.24
supports independent text generators, inline captions and plain SRT. Read
installed `capabilities` → `subtitles.float32_native` before composing.
Use the installed launcher. CPU is the default; read
[projection-gpu.md](projection-gpu.md) for the explicit Float32 OpenCL backend
and its separate device/host quotas. Glyph rasterization stays on CPU.

Register an actual local font and pass `font_asset_id` or `fontfile`. Keep
explicit source/working/output signals; fonts and SRT are not pixel sources.
Put `generator={"type":"text"}` plus `subtitle.text/style` on a subtitle
track. For existing video or child-sequence clips, attach `subtitle` directly.
Audio remains on explicit audio tracks.

Native glyph coverage has eight bits. Authored sRGB colors are converted into
the declared linear working space and each box/shadow/border/fill is composed
in Float32. A 256-code native probe must reconstruct coverage exactly. Media
pixels never enter the native text process. Animation alpha is applied once.

Typewriter snapshots shape whole grapheme prefixes on the complete paragraph's
fixed anchor/baselines. Word highlights select between two complete paragraphs;
they do not repaint the active word twice. Original presentation clocks,
trim offsets and parent reverse left limits are preserved. Freeze on the
media clip keeps the title presentation clock running.

Preview actual author frames around word/cue boundaries and edited cuts,
then render, inspect the encoded result and export an editable package.
Retain font/caption rights and actual render diagnostics. See the full
[workflow, JSON and limits](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/FLOAT_TEXT.md)
and [actual C30 media](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/CASES.md#c30-float-text).

Plain SRT accepts `asset_time_base=sequence|clip` and integer
`asset_time_offset_tick`. Rich ASS/SSA/VTT and file-level word animations must
first be explicitly converted to editable text. No legacy pixel fallback.

CLI0.1.23 uses native byte coverage and tiled Float64 source-over with Float32
component boundaries. Equal shaped prefixes and geometry reuse immutable
masks without quantizing author time. Normal/active paragraphs share glyph
coverage while retaining their distinct linear colors. Animation alpha is
applied once after painting the complete paragraph.

Surface and byte-mask LRUs each default to64MiB; each ceiling adapts to at
most one quarter of an explicit smaller workspace. Admission reserves four
Float32 surfaces, byte rasters/scratch, both cache ceilings and tile scratch
against the maximum768MiB. Default 3840x2160 text fits this estimate; it is
not a peak RSS cap, realtime promise or long-form acceptance. Inspect actual
native_coverage_rasters, coverage_cache_hits and estimated_working_bytes.
Read the [4K/cache workflow](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/FLOAT_TEXT_COVERAGE.md).
Unknown styles, stateful x/y,
wall-clock expansion, missing font metrics and malformed word times fail.
Bidi/internal shaping clusters, GPU text, HDR, natural quality, realtime and
full CapCut parity remain open. Preserve the original target conditions.
