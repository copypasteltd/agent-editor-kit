---
name: agent-ffmpeg-local-editor
description: "Edit local advertising videos with the installed agent editor kit CLI, including 500 named offline style/filter presets with measured descriptions. Use for look search, previews, editing, rendering and delivery."
---

# Agent FFmpeg Local / editor

总入口：计划、项目创建与交付. Local release: `v0.1.0-alpha.3`.

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

Read `version`, `doctor`, `capabilities` and `schema show` first. Turn the brief into an explicit edit plan.
Create an owned project, ingest existing local media with rights evidence, compose, validate, preview, render,
check the encoded output and export a project package. Route detailed timeline, template, model and quality work
to the corresponding `agent-ffmpeg-local-` Skills.

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
