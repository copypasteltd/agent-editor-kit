---
name: agent-ffmpeg-local-video-content-strategist
description: "Plan video content direction, scripts, short-form series or long-to-short reuse from supplied goals, audience and references. Use for 视频内容策略 or short-form planning."
---

# Agent FFmpeg Local / video-content-strategist

内容定位、脚本与渠道策略. Local release: `v0.1.0-alpha.3`.

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

Define the audience, objective and format using supplied context. Produce a content plan and script with
clear visual beats and evidence-backed claims. Hand an accepted brief to the installed editor workflow.
Use local/supplied references; this Skill provides no platform scraping, online publishing or rendering kernel.

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
