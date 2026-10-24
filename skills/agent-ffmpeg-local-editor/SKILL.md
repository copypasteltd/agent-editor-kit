---
name: agent-ffmpeg-local-editor
description: "Edit and deliver local videos with agent editor kit: multitrack editing, keyframes, 500 filter previews, offline visual semantic search, GPU voice/translation, licensed music/SFX, captions and quality checks. Also use for ad planning, reference remakes, long-to-short clips, screen demos or supplied campaign data that feeds an edit."
---

# agent editor kit / unified local Skill

One public entry, 17 internal task modules. Select the relevant references below;
do not load every module or invoke separately registered specialist Skills.
The current local runtime is `v0.1.0-alpha.4-local.4` / CLI `0.1.6`.
The published alpha.3 downloads retain CLI 0.1.2 and their original scope.

## Runtime and common workflow

Read [runtime.md](references/runtime.md) for the installed-release contract and
response format. Use the pinned installation through this Skill's launcher:

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk capabilities
& $avk schema show
& $avk COMMAND --help
```

For an edit, turn the brief and actual local media into an explicit plan, ingest
assets, author a timeline, validate, preview, render, check the encoded output
and export an editable project package. Use returned asset/clip IDs. Audio needs
an explicit audio track. Planning-only requests do not require rendering.

## Choose the task references

| ID | Task / when to read | Internal reference |
|---|---|---|
| K01 | Editing and delivery entrypoint / 项目总入口与交付 | [editor](references/modules/editor/module.md) |
| K02 | Timeline, keys and motion / 时间线、关键帧与运镜 | [timeline](references/modules/timeline/module.md) |
| K03 | Output and pixel review / 成片与像素核验 | [quality](references/modules/quality/module.md) |
| K04 | Project operations, recovery and queues / 工程运维、恢复与队列 | [project-ops](references/modules/project-ops/module.md) |
| K05 | Local execution policy / 本地执行约束 | [local-policy](references/modules/local-policy/module.md) |
| K06 | Media and model rights evidence / 素材与模型权利证据 | [rights-ledger](references/modules/rights-ledger/module.md) |
| K07 | Existing offline model registration / 已有离线模型登记 | [local-models](references/modules/local-models/module.md) |
| K08 | Scene/silence, visual semantic search and video evidence / 镜头、静音、图文语义检索与视频证据 | [video-understand](references/modules/video-understand/module.md) |
| K09 | Templates and reusable fragments / 模板与片段组复用 | [template-library](references/modules/template-library/module.md) |
| K10 | Long video to short clips / 长视频转短片 | [long-to-short](references/modules/long-to-short/module.md) |
| K11 | Screen demos and camera anchors / 录屏与锚点运镜 | [screen-demo](references/modules/screen-demo/module.md) |
| K12 | Reference pacing/layout remake / 参考片节奏与布局重建 | [reference-remake](references/modules/reference-remake/module.md) |
| K13 | Native media tools / 原生音视频工具 | [ffmpeg](references/modules/ffmpeg/module.md) |
| K14 | General video-edit workflows / 通用视频剪切流程 | [video-edit](references/modules/video-edit/module.md) |
| K15 | Ad creative and variants / 广告创意与变体 | [ad-creative](references/modules/ad-creative/module.md) |
| K16 | Video content strategy / 视频内容策略 | [video-content-strategist](references/modules/video-content-strategist/module.md) |
| K17 | Supplied campaign-data analysis / 提供数据的投放分析 | [campaign-analytics](references/modules/campaign-analytics/module.md) |

For ordinary edits, start with editor/timeline and use quality for delivered
media. Add other modules when the request needs them. For example:

- Long interview to shorts: video-understand → long-to-short → timeline → quality.
- Product ad: ad-creative or content strategy → editor → timeline/template → quality.
- Client filter choice: [client-look-selection.md](references/client-look-selection.md)
  and [looks.md](references/looks.md); show actual candidate images, IDs, strength
  and license, record the chosen target, then test it on the client's footage.
- Local AI task: local-models plus the relevant media module; require existing
  registered dependencies and check actual inference artifacts.
- Separate drums, bass, other instruments and vocals: read
  [audio-stems.md](references/audio-stems.md). Register the existing four-source
  runtime explicitly, prefer GPU with `auto`, retain the four editable tracks,
  and review leakage, artifacts, float peaks and source/model rights.
- Find footage from a description or reference image: read
  [semantic-retrieval.md](references/semantic-retrieval.md). Use an explicit local
  adapter/index and show returned previews, source times and scores. Review the
  clip duration separately; negation and queries with no matching asset remain
  unreliable. Read the full 20-query failure gallery before promising selection quality.
- Native window/screen/camera/microphone capture: read
  [native-capture.md](references/native-capture.md), select an explicit source,
  record for a finite duration, then edit the returned asset ID normally.
- Voice, translation or music: read [community-materials.md](references/community-materials.md).
  The configured `auto` device prefers GPU for speech/translation, reports the
  actual provider and explicitly records CPU fallback. Preserve source stems.
- Campaign report: campaign-analytics; use its findings to propose an edit brief.

These are internal references, not separate registrations or autonomous agents.
Detailed source credits and licenses remain beside the relevant module resources.

## Execution invariants

- Use the installed release, never silently fall back to `product/src` or the
  source launcher. Missing dependencies are a reported capability gap.
- Native Windows tools only; no Docker, WSL, containers or virtual environments.
  Media and inference dependencies must already be local. No implicit downloads.
- Use argument arrays for paths, keep new artifacts in the owned project and
  preserve input files and existing output. Check exit code plus `ok`, `status`,
  `errors`, `warnings` and `artifacts`; a dry run is not a render.
- Consult installed capabilities and command help before using an effect or model.
  Candidate development commands are not installed release capabilities.
- Record actual source/license evidence. Unknown rights stay unverified;
  `render --publish` is a local rights gate, not an upload.
- Distinguish automatic decode/PCM checks, still inspection, continuous playback
  and human listening. This release has not achieved full CapCut parity.
- Close unused browser tabs after any separately used browser operation.
