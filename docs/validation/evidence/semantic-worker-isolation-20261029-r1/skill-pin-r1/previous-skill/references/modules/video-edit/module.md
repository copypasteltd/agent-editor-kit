# 修剪、拼接、变速与压缩 / video-edit

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Local files + edit instructions → trims/concat/overlays

Commands: `native ffmpeg; installed CLI`. Use timeline/editor for complex editable projects.

## Workflow

Probe inputs first. Use the installed CLI for edits that must remain editable; use native FFmpeg for
explicit one-off transformations. Select streams and audio policy deliberately. Preserve source files, reject
accidental overwrite, and check the actual encoded output. Review any bundled helper before executing it.

## Attributed resources

[Upstream workflow](references/upstream/workflow.md) retains author, source commit and license. Use specific frameworks/helpers only when relevant; inspect their inputs and dependencies first. The shared runtime contract governs execution.
