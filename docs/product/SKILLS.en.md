# One local Skill: 17 internal task modules

<!-- community-current -->

**Current local / 当前本机 / 目前本機：CLI 0.1.5 / alpha.4-local.3。** Offline visual semantic retrieval, GPU voice/translation, 359 resources, native capture and one Skill / 17 modules. Public alpha.3 stays CLI 0.1.2. [Installation](COMMUNITY_LOCAL_DELIVERY.md) · [Semantic workflow](SEMANTIC_RETRIEVAL.md) · [Current declarations](semantic-capabilities-cli-0.1.5.json) · [All 38 gaps](GOAL_GAPS_20261025.md).

<!-- /community-current -->

<!-- unified-skill-registration -->

Register only `$agent-ffmpeg-local-editor`. K01–K17 load as internal references; previous specialist names are provenance, not additional invocation names. [Guide](../skills/UNIFIED_SKILL.en.md)

<!-- /unified-skill-registration -->

[README](../../README.en.md) · [Registration](../local/INSTALLATION.md)

| ID | Internal module | Responsibility | Input → output | Commands | Dependency/limit |
|---|---|---|---|---|---|
| K01 | [`$agent-ffmpeg-local-editor`](../../skills/agent-ffmpeg-local-editor/SKILL.md) | Editing and delivery entrypoint | brief + local media → plan, project, video, manifest | `project init; timeline compose; look; render` | Routes by capability, including client look selection; needs the base CLI. |
| K02 | [`timeline`](../../skills/agent-ffmpeg-local-editor/references/modules/timeline/module.md) | Timeline, keys and motion | Edit JSON → tracks/motion/transitions/nesting | `timeline compose/edit; motion apply` | Explicit track/clip targets and author clocks. |
| K03 | [`quality`](../../skills/agent-ffmpeg-local-editor/references/modules/quality/module.md) | Output and pixel review | Video + manifest + reference → reports/scopes/differences | `quality check/scopes/mask/golden` | Separate static review/playback/listening; review look selections. |
| K04 | [`project-ops`](../../skills/agent-ffmpeg-local-editor/references/modules/project-ops/module.md) | Project operations, recovery and queues | Projects + jobs → snapshots/recovery/relink/results | `project snapshot/recover; media relink; queue` | Preserve sources/failures; not a cloud scheduler. |
| K05 | [`local-policy`](../../skills/agent-ffmpeg-local-editor/references/modules/local-policy/module.md) | Local execution policy | Project references → audit/structured refusal | `policy audit` | Remote references refused; not an OS sandbox. |
| K06 | [`rights-ledger`](../../skills/agent-ffmpeg-local-editor/references/modules/rights-ledger/module.md) | Media and model rights evidence | Source/license/local evidence → ledger/impact/gates | `rights list/check/update/impact` | Treat image and LUT rights separately; no automatic legal determination. |
| K07 | [`local-models`](../../skills/agent-ffmpeg-local-editor/references/modules/local-models/module.md) | Existing offline model registration | Native runtime + weights/hashes/licenses → adapters/artifacts | `media adapter; asr adapter; ocr; face; tts; voice; translate; gpu` | No weight downloads; check capability/runtime before execution. |
| K08 | [`video-understand`](../../skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md) | Scene/silence and video evidence | Local video/audio → analysis JSON, frames, caption candidates | `media understand/contact-sheet; subtitle transcribe; semantic index/search` | Distinguish heuristics from model semantics. |
| K09 | [`template-library`](../../skills/agent-ffmpeg-local-editor/references/modules/template-library/module.md) | Templates and reusable fragments | Templates/variables/library → editable variants/index | `template apply/batch; library; fragment` | User-provided assets and per-resource licenses. |
| K10 | [`long-to-short`](../../skills/agent-ffmpeg-local-editor/references/modules/long-to-short/module.md) | Long video to short clips | Local lesson/talk + reviewed text → rough cuts/short projects | `media highlights/smart-cut; timeline compose` | Review candidate segments; no autonomous semantic-director claim. |
| K11 | [`screen-demo`](../../skills/agent-ffmpeg-local-editor/references/modules/screen-demo/module.md) | Screen demos and camera anchors | Recording + action anchors → zoom/return/caption demo | `timeline compose; ocr anchors; preview range` | OCR needs existing models; text boxes are not clickable-control bounds. |
| K12 | [`reference-remake`](../../skills/agent-ffmpeg-local-editor/references/modules/reference-remake/module.md) | Reference pacing/layout remake | Local reference + replacement assets → editable remake | `media understand; timeline compose` | Rebuild structure; no automatic acquisition or rights grant. |
| K13 | [`ffmpeg`](../../skills/agent-ffmpeg-local-editor/references/modules/ffmpeg/module.md) | Native media tools | Local files + settings → conversion/resize/extraction/compression | `native ffmpeg / ffprobe` | Native tools; inspect codec availability. |
| K14 | [`video-edit`](../../skills/agent-ffmpeg-local-editor/references/modules/video-edit/module.md) | General video-edit workflows | Local files + edit instructions → trims/concat/overlays | `native ffmpeg; installed CLI` | Use timeline/editor for complex editable projects. |
| K15 | [`ad-creative`](../../skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md) | Ad creative and variants | Product/audience/evidence → hooks/copy/scripts/variants | `advisory; ad plan` | Advisory instructions without bundled media-generation models. |
| K16 | [`video-content-strategist`](../../skills/agent-ffmpeg-local-editor/references/modules/video-content-strategist/module.md) | Video content strategy | Goals/audience/supplied references → direction/series/scripts | `advisory Skill` | No live trends, platform accounts or crawler. |
| K17 | [`campaign-analytics`](../../skills/agent-ffmpeg-local-editor/references/modules/campaign-analytics/module.md) | Supplied campaign-data analysis | Local campaign tables → ROAS/CPA/funnel/suggestions | `advisory Skill` | No ad-platform connector; metrics depend on data/attribution assumptions. |

## K01 · `$agent-ffmpeg-local-editor`

Editing and delivery entrypoint

brief + local media → plan, project, video, manifest

`project init; timeline compose; look; render`

Routes by capability, including client look selection; needs the base CLI.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/SKILL.md)

## K02 · `timeline`

Timeline, keys and motion

Edit JSON → tracks/motion/transitions/nesting

`timeline compose/edit; motion apply`

Explicit track/clip targets and author clocks.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/timeline/module.md)

## K03 · `quality`

Output and pixel review

Video + manifest + reference → reports/scopes/differences

`quality check/scopes/mask/golden`

Separate static review/playback/listening; review look selections.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/quality/module.md)

## K04 · `project-ops`

Project operations, recovery and queues

Projects + jobs → snapshots/recovery/relink/results

`project snapshot/recover; media relink; queue`

Preserve sources/failures; not a cloud scheduler.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/project-ops/module.md)

## K05 · `local-policy`

Local execution policy

Project references → audit/structured refusal

`policy audit`

Remote references refused; not an OS sandbox.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/local-policy/module.md)

## K06 · `rights-ledger`

Media and model rights evidence

Source/license/local evidence → ledger/impact/gates

`rights list/check/update/impact`

Treat image and LUT rights separately; no automatic legal determination.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/rights-ledger/module.md)

## K07 · `local-models`

Existing offline model registration

Native runtime + weights/hashes/licenses → adapters/artifacts

`media adapter; asr adapter; ocr; face; tts; voice; translate; gpu`

No weight downloads; check capability/runtime before execution.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/local-models/module.md)

## K08 · `video-understand`

Scene/silence and video evidence

Local video/audio → analysis JSON, frames, caption candidates

`media understand/contact-sheet; subtitle transcribe; semantic index/search`

Distinguish heuristics from model semantics.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md)

## K09 · `template-library`

Templates and reusable fragments

Templates/variables/library → editable variants/index

`template apply/batch; library; fragment`

User-provided assets and per-resource licenses.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/template-library/module.md)

## K10 · `long-to-short`

Long video to short clips

Local lesson/talk + reviewed text → rough cuts/short projects

`media highlights/smart-cut; timeline compose`

Review candidate segments; no autonomous semantic-director claim.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/long-to-short/module.md)

## K11 · `screen-demo`

Screen demos and camera anchors

Recording + action anchors → zoom/return/caption demo

`timeline compose; ocr anchors; preview range`

OCR needs existing models; text boxes are not clickable-control bounds.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/screen-demo/module.md)

## K12 · `reference-remake`

Reference pacing/layout remake

Local reference + replacement assets → editable remake

`media understand; timeline compose`

Rebuild structure; no automatic acquisition or rights grant.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/reference-remake/module.md)

## K13 · `ffmpeg`

Native media tools

Local files + settings → conversion/resize/extraction/compression

`native ffmpeg / ffprobe`

Native tools; inspect codec availability.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/ffmpeg/module.md)

## K14 · `video-edit`

General video-edit workflows

Local files + edit instructions → trims/concat/overlays

`native ffmpeg; installed CLI`

Use timeline/editor for complex editable projects.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/video-edit/module.md)

## K15 · `ad-creative`

Ad creative and variants

Product/audience/evidence → hooks/copy/scripts/variants

`advisory; ad plan`

Advisory instructions without bundled media-generation models.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md)

## K16 · `video-content-strategist`

Video content strategy

Goals/audience/supplied references → direction/series/scripts

`advisory Skill`

No live trends, platform accounts or crawler.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/video-content-strategist/module.md)

## K17 · `campaign-analytics`

Supplied campaign-data analysis

Local campaign tables → ROAS/CPA/funnel/suggestions

`advisory Skill`

No ad-platform connector; metrics depend on data/attribution assumptions.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/campaign-analytics/module.md)

## Client look selection

[Workflow](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [Gallery guide](../local/FILTER_GALLERY.en.md)

A single discovery junction points to the unified E-drive Skill; its 17 modules are internal references. Runtime and gallery are separate: wheels alone do not include the gallery. The helper reads rendered samples and exports a new comparison board; final edits use the pinned CLI with snapshots.


## CLI 0.1.5 / F50 / S18 / K08: visual semantic retrieval

[Complete workflow / 完整流程](SEMANTIC_RETRIEVAL.md) · [Skill reference](../../skills/agent-ffmpeg-local-editor/references/semantic-retrieval.md) · [Actual output](CASES.md#c14-semantic-retrieval).

Explicit local SigLIP2 image/video-sample embeddings; Chinese/English/reference-image search; native PTS, previews, editable source points, integrity and auto/cpu/cuda. 16 positive queries pass on this small familiar set; Chinese negation and both open-set queries fail expected selection/rejection. No natural-action, cross-shot identity, audio matching or large-library acceptance. One sampled point does not define clip duration.
