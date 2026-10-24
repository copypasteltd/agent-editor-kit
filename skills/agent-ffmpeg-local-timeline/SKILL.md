---
name: agent-ffmpeg-local-timeline
description: "Compose local video timelines, keyframes, camera presets, transitions, masks and speed curves. Apply 500 named built-in color looks to explicit clips or global adjustments using the installed CLI."
---

# Agent FFmpeg Local / timeline

时间线、关键帧、运镜、转场、嵌套. Local release: `v0.1.0-alpha.3`.

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

Inspect `schema show`, `effects list` and `timeline compose --help`. Author an edit JSON with integer ticks,
source ranges, explicit tracks and audio. Use `timeline compose` or `timeline edit` only with supported operations.
Use `preview frame` or `preview range` to inspect actual results before rendering. Keep native PTS and nested clocks.

## Execution contract

- Native local Windows tools only; no Docker, WSL, containers or virtual environments.
- Media must be local; model inference requires existing explicitly registered weights and dependencies.
- Keep edits and output artifacts in the owned project; preserve source media and existing output files.
- Check exit code, `ok`, `status`, `errors`, `warnings` and `artifacts`; a dry plan is not an actual render.
- Author audio explicitly. `render --publish` checks local rights; it does not upload media.
- Inspect capabilities before effects or Float32 work; do not substitute unsupported features silently.
- Close unused browser tabs after any separately authorized browser operation.

## Offline look presets

Use `look list`, `look inspect`, `look preview` and `look apply` for 500 named offline color looks. Inspect measured descriptions, original variants and the per-resource MIT, CC0 or CC-BY-SA license. Read [the look workflow](../agent-ffmpeg-local-editor/references/looks.md) before choosing target, strength or delivery. These are creative SDR looks; preview suggestions are not natural-footage acceptance.
