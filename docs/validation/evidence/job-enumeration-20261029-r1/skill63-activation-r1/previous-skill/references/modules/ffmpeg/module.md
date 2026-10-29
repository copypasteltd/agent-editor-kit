# 本地 FFmpeg 格式和媒体处理 / ffmpeg

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Local files + settings → conversion/resize/extraction/compression

Commands: `native ffmpeg / ffprobe`. Native tools; inspect codec availability.

## Workflow

Locate existing native `ffmpeg` and `ffprobe`, inspect the input and choose explicit codecs, streams and
output settings. Use argument arrays and a new local output; never concatenate untrusted shell text. Validate
actual streams, duration and decode. For editable projects use the installed Agent CLI instead of flattening
all edits. Read upstream examples only after checking current tool help and local policy.

## Attributed resources

[Upstream workflow](references/upstream/workflow.md) retains author, source commit and license. Use specific frameworks/helpers only when relevant; inspect their inputs and dependencies first. The shared runtime contract governs execution.
