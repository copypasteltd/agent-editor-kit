# Linear Float32 titles and captions

For a `settings.pixel_pipeline.engine="float32-native-v1"` project, CLI0.1.22
supports independent text generators, inline captions and plain SRT. Read
installed `capabilities` → `subtitles.float32_native` before composing.
Use the installed launcher; this feature runs on CPU.

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

Default cache64MiB; native text admission estimates20 Float32 RGBA rasters
against the explicit maximum768MiB workspace. This is not a process RSS cap.
4K text is rejected before native execution. Unknown styles, stateful x/y,
wall-clock expansion, missing font metrics and malformed word times fail.
Bidi/internal shaping clusters, GPU text, HDR, natural quality, realtime and
full CapCut parity remain open. Preserve the original target conditions.
