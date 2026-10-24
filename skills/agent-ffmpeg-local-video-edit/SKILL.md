---
name: agent-ffmpeg-local-video-edit
description: "Trim, concatenate, resize, speed up, overlay, extract or replace audio, compress and convert local videos using native FFmpeg or the installed editable-project CLI."
---

# Agent FFmpeg Local / video-edit

修剪、拼接、变速与压缩. Local release: `v0.1.0-alpha.3`.

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

Probe inputs first. Use the installed CLI for edits that must remain editable; use native FFmpeg for
explicit one-off transformations. Select streams and audio policy deliberately. Preserve source files, reject
accidental overwrite, and check the actual encoded output. Review any bundled helper before executing it.

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
