---
name: agent-ffmpeg-local-ffmpeg
description: "Use native local FFmpeg and ffprobe for conversion, resizing, compression, audio extraction, GIF/MP4 conversion and preparation of local editing assets."
---

# Agent FFmpeg Local / ffmpeg

本地 FFmpeg 格式和媒体处理. Local release: `v0.1.0-alpha.3`.

## Installed runtime

Use the installed release, not `ai-ad-editor.ps1` or `product/src`. The shared launcher pins
`v0.1.0-alpha.3`, checks the installation receipt and launcher hash, and starts native Python with `-I -S`.

```powershell
$avkSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $avkSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk doctor
& $avk capabilities
& $avk COMMAND --help
```

Use argument arrays for paths with spaces/Chinese characters. A missing installation is an error; never
silently fall back to source. Read [the shared runtime contract](../agent-ffmpeg-local-editor/references/runtime.md)
for installation, CLI response checks and a complete project workflow.

## Workflow

Locate existing native `ffmpeg` and `ffprobe`, inspect the input and choose explicit codecs, streams and
output settings. Use argument arrays and a new local output; never concatenate untrusted shell text. Validate
actual streams, duration and decode. For editable projects use the installed Agent CLI instead of flattening
all edits. Read upstream examples only after checking current tool help and local policy.

## Execution contract

- Native local Windows tools only; no Docker, WSL, containers or virtual environments.
- Media must be local; model inference requires existing explicitly registered weights and dependencies.
- Keep edits and output artifacts in the owned project; preserve source media and existing output files.
- Check exit code, `ok`, `status`, `errors`, `warnings` and `artifacts`; a dry plan is not an actual render.
- Author audio explicitly. `render --publish` checks local rights; it does not upload media.
- Inspect capabilities before effects or Float32 work; do not substitute unsupported features silently.
- Close unused browser tabs after any separately authorized browser operation.

## Credited reference

[Upstream workflow and resources](references/upstream/workflow.md) retain their original provenance and licenses.
The installed-release contract above takes precedence over older source-launch examples.
