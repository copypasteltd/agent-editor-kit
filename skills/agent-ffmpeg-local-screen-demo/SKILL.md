---
name: agent-ffmpeg-local-screen-demo
description: "Edit local screen recordings into product demos with explicit action anchors, keyframed zooms, captions and visible outcomes. Use for 录屏演示, 产品教程 or 操作视频."
---

# Agent FFmpeg Local / screen-demo

录屏锚点、缩放与产品演示. Local release: `v0.1.0-alpha.3`.

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

Map actual actions, pauses and visible results to source times. Use supported timeline keyframes or camera
presets, keeping cursor actions and result text legible. Retain honest waits or disclose sped-up sections.
Preview key anchors at output resolution, render and verify the result. This Skill edits recordings; it is not
a browser-control integration. Close unused tabs if a separate browser tool is used.

## Execution contract

- Native local Windows tools only; no Docker, WSL, containers or virtual environments.
- Media must be local; model inference requires existing explicitly registered weights and dependencies.
- Keep edits and output artifacts in the owned project; preserve source media and existing output files.
- Check exit code, `ok`, `status`, `errors`, `warnings` and `artifacts`; a dry plan is not an actual render.
- Author audio explicitly. `render --publish` checks local rights; it does not upload media.
- Inspect capabilities before effects or Float32 work; do not substitute unsupported features silently.
- Close unused browser tabs after any separately authorized browser operation.
