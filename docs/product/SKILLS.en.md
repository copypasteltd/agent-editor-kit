# 17 local Skill details

[README](../../README.en.md) · [Registration](../local/INSTALLATION.md)

| ID | Skill | Responsibility | Input → output | Commands | Dependency/limit |
|---|---|---|---|---|---|
| K01 | [`$agent-ffmpeg-local-editor`](../../skills/agent-ffmpeg-local-editor/SKILL.md) | Editing and delivery entrypoint | brief + local media → plan, project, video, manifest | `project init; timeline compose; look; render` | Routes by capability, including client look selection; needs the base CLI. |
| K02 | [`$agent-ffmpeg-local-timeline`](../../skills/agent-ffmpeg-local-timeline/SKILL.md) | Timeline, keys and motion | Edit JSON → tracks/motion/transitions/nesting | `timeline compose/edit; motion apply` | Explicit track/clip targets and author clocks. |
| K03 | [`$agent-ffmpeg-local-quality`](../../skills/agent-ffmpeg-local-quality/SKILL.md) | Output and pixel review | Video + manifest + reference → reports/scopes/differences | `quality check/scopes/mask/golden` | Separate static review/playback/listening; review look selections. |
| K04 | [`$agent-ffmpeg-local-project-ops`](../../skills/agent-ffmpeg-local-project-ops/SKILL.md) | Project operations, recovery and queues | Projects + jobs → snapshots/recovery/relink/results | `project snapshot/recover; media relink; queue` | Preserve sources/failures; not a cloud scheduler. |
| K05 | [`$agent-ffmpeg-local-local-policy`](../../skills/agent-ffmpeg-local-local-policy/SKILL.md) | Local execution policy | Project references → audit/structured refusal | `policy audit` | Remote references refused; not an OS sandbox. |
| K06 | [`$agent-ffmpeg-local-rights-ledger`](../../skills/agent-ffmpeg-local-rights-ledger/SKILL.md) | Media and model rights evidence | Source/license/local evidence → ledger/impact/gates | `rights list/check/update/impact` | Treat image and LUT rights separately; no automatic legal determination. |
| K07 | [`$agent-ffmpeg-local-local-models`](../../skills/agent-ffmpeg-local-local-models/SKILL.md) | Existing offline model registration | Native runtime + weights/hashes/licenses → adapters/artifacts | `media adapter; asr adapter; ocr; face; tts` | No weight downloads; check capability/runtime before execution. |
| K08 | [`$agent-ffmpeg-local-video-understand`](../../skills/agent-ffmpeg-local-video-understand/SKILL.md) | Scene/silence and video evidence | Local video/audio → analysis JSON, frames, caption candidates | `media understand/contact-sheet; subtitle transcribe` | Distinguish heuristics from model semantics. |
| K09 | [`$agent-ffmpeg-local-template-library`](../../skills/agent-ffmpeg-local-template-library/SKILL.md) | Templates and reusable fragments | Templates/variables/library → editable variants/index | `template apply/batch; library; fragment` | User-provided assets and per-resource licenses. |
| K10 | [`$agent-ffmpeg-local-long-to-short`](../../skills/agent-ffmpeg-local-long-to-short/SKILL.md) | Long video to short clips | Local lesson/talk + reviewed text → rough cuts/short projects | `media highlights/smart-cut; timeline compose` | Review candidate segments; no autonomous semantic-director claim. |
| K11 | [`$agent-ffmpeg-local-screen-demo`](../../skills/agent-ffmpeg-local-screen-demo/SKILL.md) | Screen demos and camera anchors | Recording + action anchors → zoom/return/caption demo | `timeline compose; ocr anchors; preview range` | OCR needs existing models; text boxes are not clickable-control bounds. |
| K12 | [`$agent-ffmpeg-local-reference-remake`](../../skills/agent-ffmpeg-local-reference-remake/SKILL.md) | Reference pacing/layout remake | Local reference + replacement assets → editable remake | `media understand; timeline compose` | Rebuild structure; no automatic acquisition or rights grant. |
| K13 | [`$agent-ffmpeg-local-ffmpeg`](../../skills/agent-ffmpeg-local-ffmpeg/SKILL.md) | Native media tools | Local files + settings → conversion/resize/extraction/compression | `native ffmpeg / ffprobe` | Native tools; inspect codec availability. |
| K14 | [`$agent-ffmpeg-local-video-edit`](../../skills/agent-ffmpeg-local-video-edit/SKILL.md) | General video-edit workflows | Local files + edit instructions → trims/concat/overlays | `native ffmpeg; installed CLI` | Use timeline/editor for complex editable projects. |
| K15 | [`$agent-ffmpeg-local-ad-creative`](../../skills/agent-ffmpeg-local-ad-creative/SKILL.md) | Ad creative and variants | Product/audience/evidence → hooks/copy/scripts/variants | `advisory; ad plan` | Advisory instructions without bundled media-generation models. |
| K16 | [`$agent-ffmpeg-local-video-content-strategist`](../../skills/agent-ffmpeg-local-video-content-strategist/SKILL.md) | Video content strategy | Goals/audience/supplied references → direction/series/scripts | `advisory Skill` | No live trends, platform accounts or crawler. |
| K17 | [`$agent-ffmpeg-local-campaign-analytics`](../../skills/agent-ffmpeg-local-campaign-analytics/SKILL.md) | Supplied campaign-data analysis | Local campaign tables → ROAS/CPA/funnel/suggestions | `advisory Skill` | No ad-platform connector; metrics depend on data/attribution assumptions. |

## K01 · `$agent-ffmpeg-local-editor`

Editing and delivery entrypoint

brief + local media → plan, project, video, manifest

`project init; timeline compose; look; render`

Routes by capability, including client look selection; needs the base CLI.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/SKILL.md)

## K02 · `$agent-ffmpeg-local-timeline`

Timeline, keys and motion

Edit JSON → tracks/motion/transitions/nesting

`timeline compose/edit; motion apply`

Explicit track/clip targets and author clocks.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-timeline/SKILL.md)

## K03 · `$agent-ffmpeg-local-quality`

Output and pixel review

Video + manifest + reference → reports/scopes/differences

`quality check/scopes/mask/golden`

Separate static review/playback/listening; review look selections.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-quality/SKILL.md)

## K04 · `$agent-ffmpeg-local-project-ops`

Project operations, recovery and queues

Projects + jobs → snapshots/recovery/relink/results

`project snapshot/recover; media relink; queue`

Preserve sources/failures; not a cloud scheduler.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-project-ops/SKILL.md)

## K05 · `$agent-ffmpeg-local-local-policy`

Local execution policy

Project references → audit/structured refusal

`policy audit`

Remote references refused; not an OS sandbox.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-local-policy/SKILL.md)

## K06 · `$agent-ffmpeg-local-rights-ledger`

Media and model rights evidence

Source/license/local evidence → ledger/impact/gates

`rights list/check/update/impact`

Treat image and LUT rights separately; no automatic legal determination.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-rights-ledger/SKILL.md)

## K07 · `$agent-ffmpeg-local-local-models`

Existing offline model registration

Native runtime + weights/hashes/licenses → adapters/artifacts

`media adapter; asr adapter; ocr; face; tts`

No weight downloads; check capability/runtime before execution.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-local-models/SKILL.md)

## K08 · `$agent-ffmpeg-local-video-understand`

Scene/silence and video evidence

Local video/audio → analysis JSON, frames, caption candidates

`media understand/contact-sheet; subtitle transcribe`

Distinguish heuristics from model semantics.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-video-understand/SKILL.md)

## K09 · `$agent-ffmpeg-local-template-library`

Templates and reusable fragments

Templates/variables/library → editable variants/index

`template apply/batch; library; fragment`

User-provided assets and per-resource licenses.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-template-library/SKILL.md)

## K10 · `$agent-ffmpeg-local-long-to-short`

Long video to short clips

Local lesson/talk + reviewed text → rough cuts/short projects

`media highlights/smart-cut; timeline compose`

Review candidate segments; no autonomous semantic-director claim.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-long-to-short/SKILL.md)

## K11 · `$agent-ffmpeg-local-screen-demo`

Screen demos and camera anchors

Recording + action anchors → zoom/return/caption demo

`timeline compose; ocr anchors; preview range`

OCR needs existing models; text boxes are not clickable-control bounds.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-screen-demo/SKILL.md)

## K12 · `$agent-ffmpeg-local-reference-remake`

Reference pacing/layout remake

Local reference + replacement assets → editable remake

`media understand; timeline compose`

Rebuild structure; no automatic acquisition or rights grant.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-reference-remake/SKILL.md)

## K13 · `$agent-ffmpeg-local-ffmpeg`

Native media tools

Local files + settings → conversion/resize/extraction/compression

`native ffmpeg / ffprobe`

Native tools; inspect codec availability.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-ffmpeg/SKILL.md)

## K14 · `$agent-ffmpeg-local-video-edit`

General video-edit workflows

Local files + edit instructions → trims/concat/overlays

`native ffmpeg; installed CLI`

Use timeline/editor for complex editable projects.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-video-edit/SKILL.md)

## K15 · `$agent-ffmpeg-local-ad-creative`

Ad creative and variants

Product/audience/evidence → hooks/copy/scripts/variants

`advisory; ad plan`

Advisory instructions without bundled media-generation models.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-ad-creative/SKILL.md)

## K16 · `$agent-ffmpeg-local-video-content-strategist`

Video content strategy

Goals/audience/supplied references → direction/series/scripts

`advisory Skill`

No live trends, platform accounts or crawler.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-video-content-strategist/SKILL.md)

## K17 · `$agent-ffmpeg-local-campaign-analytics`

Supplied campaign-data analysis

Local campaign tables → ROAS/CPA/funnel/suggestions

`advisory Skill`

No ad-platform connector; metrics depend on data/attribution assumptions.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-campaign-analytics/SKILL.md)

## Client look selection

[Workflow](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [Gallery guide](../local/FILTER_GALLERY.en.md)

All 17 local registrations are junctions to E-drive canonical files. Runtime and gallery are separate: wheels alone do not include the gallery. The helper reads rendered samples and exports a new comparison board; final edits use the pinned CLI with snapshots.
