---
name: agent-ffmpeg-local-ad-creative
description: "Plan or iterate ad copy, hooks, scripts, product claims and creative variants from a supplied offer and audience. Use for 广告创意, 广告建议 or ad creative testing."
---

# Agent FFmpeg Local / ad-creative

广告文案、Hook 和创意变体. Local release: `v0.1.0-alpha.3`.

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

Collect the actual offer, audience, proof and call to action. Propose distinct hooks and a shot/copy plan,
then map the accepted variant to local assets, captions and timing for the editor Skill. Do not invent product
claims or performance metrics. This is creative guidance, not a rendering engine or ad-platform connector.
Use the credited upstream reference for detailed copy frameworks.

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
