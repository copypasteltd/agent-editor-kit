---
name: agent-ffmpeg-local-rights-ledger
description: "Record source, license, creator and local evidence for media, fonts, templates, LUTs and models. Inspect per-resource MIT, CC0 or CC-BY-SA obligations for the 500 bundled looks and project-local evidence."
---

# Agent FFmpeg Local / rights-ledger

素材、字体、模型与模板权利台账. Local release: `v0.1.0-alpha.3`.

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

Inspect `rights --help` and `media ingest --help`. Record the actual source and license evidence per asset;
unknown rights remain unverified. Use `rights check` before `render --publish`. The publish flag is a local gate,
not a platform upload. When moving a project, rebind local license-evidence paths and recheck the ledger.

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

For human-facing filter selection, read [client-look-selection.md](../agent-ffmpeg-local-editor/references/client-look-selection.md). It maps all 500 real N002 samples to stable IDs and exports a small labeled original/candidate board with `scripts/look_gallery.py`. Show actual images, number/name/ID, strength and license; record the chosen ID/strength/scope, then trial the target media before applying. The samples are strength 1.0; image rights are separate from LUT rights. The runtime ZIP alone does not include the checkout gallery.
