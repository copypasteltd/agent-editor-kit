# One local Skill: 17 internal task modules

<!-- community-current -->

**CLI0.1.48 / alpha.4-local.46 / r49 kit · 1 Skill / 17 modules / 87 files.**

Added **native RGB ICC output, profile-embedded16-bit PNG sequence delivery and soft proof**: actual B2A tables,intents/BPC,explicit nits scaling,authored frames and synchronized PCM;native simulation in normal render/previews and portable profile dependencies.

[ICC output / soft proof workflow](ICC_OUTPUT.md)

<!-- /community-current -->

<!-- unified-skill-registration -->

Register only `$agent-ffmpeg-local-editor`. K01–K17 load as internal references; previous specialist names are provenance, not additional invocation names. [Guide](../skills/UNIFIED_SKILL.en.md)

<!-- /unified-skill-registration -->

[README](../../README.en.md) · [Registration](../local/INSTALLATION.md)

| ID | Internal module | Responsibility | Input → output | Commands | Dependency/limit |
|---|---|---|---|---|---|
| K01 | [`$agent-ffmpeg-local-editor`](../../skills/agent-ffmpeg-local-editor/SKILL.md) | Editing and delivery entrypoint | brief + local media → plan, project, video, manifest | `project init; timeline compose; look; render` | Routes by capability, including client look selection; needs the base CLI. |
| K02 | [`timeline`](../../skills/agent-ffmpeg-local-editor/references/modules/timeline/module.md) | Timeline, keys and motion | Edit JSON → tracks/motion/transitions/nesting | `timeline compose/edit; motion apply; motion pack list/inspect/create/capture/apply` | Explicit track/clip targets and author clocks. |
| K03 | [`quality`](../../skills/agent-ffmpeg-local-editor/references/modules/quality/module.md) | Output and pixel review | Video + manifest + reference → reports/scopes/differences | `quality check/scopes/mask/golden` | Separate static review/playback/listening; review look selections. |
| K04 | [`project-ops`](../../skills/agent-ffmpeg-local-editor/references/modules/project-ops/module.md) | Project operations, recovery and queues | Projects + jobs → snapshots/recovery/relink/results | `project snapshot/recover; media relink; queue` | Preserve sources/failures; not a cloud scheduler. |
| K05 | [`local-policy`](../../skills/agent-ffmpeg-local-editor/references/modules/local-policy/module.md) | Local execution policy | Project references → audit/structured refusal | `policy audit` | Remote references refused; not an OS sandbox. |
| K06 | [`rights-ledger`](../../skills/agent-ffmpeg-local-editor/references/modules/rights-ledger/module.md) | Media and model rights evidence | Source/license/local evidence → ledger/impact/gates | `rights list/check/update/impact` | Treat image and LUT rights separately; no automatic legal determination. |
| K07 | [`local-models`](../../skills/agent-ffmpeg-local-editor/references/modules/local-models/module.md) | Existing offline model registration | Native runtime + weights/hashes/licenses → adapters/artifacts | `audio adapter; audio separate-stems; media adapter; asr adapter; ocr; face; tts` | No weight downloads; check capability/runtime before execution. |
| K08 | [`video-understand`](../../skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md) | Scene/silence, semantic retrieval and video evidence | Local video/images/text/reference → analysis, previews, source times and candidates | `media understand/contact-sheet; subtitle transcribe; semantic index/calibrate/calibration-list/search; project upgrade-semantic` | [Retrieval reference](../../skills/agent-ffmpeg-local-editor/references/semantic-retrieval.md); sample points provide no event duration; review candidates. |
| K09 | [`template-library`](../../skills/agent-ffmpeg-local-editor/references/modules/template-library/module.md) | Templates and reusable fragments | Templates/variables/library → editable variants/index | `template apply/batch; library; fragment` | User-provided assets and per-resource licenses. |
| K10 | [`long-to-short`](../../skills/agent-ffmpeg-local-editor/references/modules/long-to-short/module.md) | Long video to short clips | Local lesson/talk + reviewed text → rough cuts/short projects | `media highlights/smart-cut; timeline compose` | Review candidate segments; no autonomous semantic-director claim. |
| K11 | [`screen-demo`](../../skills/agent-ffmpeg-local-editor/references/modules/screen-demo/module.md) | Screen demos and camera anchors | Recording + action anchors → zoom/return/caption demo | `timeline compose; ocr anchors; preview range` | OCR needs existing models; text boxes are not clickable-control bounds. |
| K12 | [`reference-remake`](../../skills/agent-ffmpeg-local-editor/references/modules/reference-remake/module.md) | Reference pacing/layout remake | Local reference + replacement assets → editable remake | `media understand; timeline compose` | Rebuild structure; no automatic acquisition or rights grant. |
| K13 | [`ffmpeg`](../../skills/agent-ffmpeg-local-editor/references/modules/ffmpeg/module.md) | Native media tools | Local files + settings → conversion/resize/extraction/compression | `native ffmpeg / ffprobe` | Native tools; inspect codec availability. |
| K14 | [`video-edit`](../../skills/agent-ffmpeg-local-editor/references/modules/video-edit/module.md) | General video-edit workflows | Local files + edit instructions → trims/concat/overlays | `native ffmpeg; installed CLI` | Use timeline/editor for complex editable projects. |
| K15 | [`ad-creative`](../../skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md) | Creative planning, editable storyboards and variants | Product/audience/reviewed copy/actual assets → plans, independent sequences and scoped revisions | `advisory; ad plan; ad storyboard/build/revise` | Explicit creative decisions and claim evidence; no bundled video-generation model. |
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

`media adapter; asr adapter; ocr; face; tts; voice; translate; dub subtitles; gpu`

No weight downloads; check capability/runtime before execution.

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/local-models/module.md)

## K08 · `video-understand`

Scene/silence and video evidence

Local video/audio → analysis JSON, frames, caption candidates

`media understand/contact-sheet; subtitle transcribe; semantic index/calibrate/calibration-list/search`

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

CLI 0.1.7: K04 uses [owned job recovery](JOB_RECOVERY.md); preview `--cleanup-jobs --dry-run` and preserve active/changed/unknown/legacy files. K07 retains explicit adapter re-registration and separate model/runtime rights.


## CLI 0.1.9 / F51 / S20 / K07: joint subtitle translation and dubbing

[Workflow / 使用流程](SUBTITLE_DUBBING.md) · [Internal Skill reference](../../skills/agent-ffmpeg-local-editor/references/subtitle-dubbing.md) · [Actual C18 output](CASES.md#c18-subtitle-dubbing) · [Checks and failures](../validation/字幕翻译配音联合流程实测_2026-10-25.md).

Plain local SRT → OPUS Chinese/English translation → one Kokoro initialization per voice batch → actual complete WAV sample checks → atomic editable audio/bilingual captions. Original text/times and every speed attempt are retained. Explicit tracks/casting/mixing and bounded whole-utterance regeneration; managed cancellation/timeout/recovery protects committed media and model licenses.

字幕翻译、完整分段配音、实际时窗和可编辑入轨已实现；字幕翻譯、完整分段配音、實際時窗與可編輯入軌已實作。仅中英/普通 SRT；仅 cue 级安排。Actual awkward translations remain recorded. Naturalness, semantic acceptance, word alignment, lip sync, broad reliability and full CapCut parity remain open. The existing 103-name voice catalog now has at least seven distinct voices actually generated; no human listening acceptance.


<!-- semantic-decisions-current -->

## CLI 0.1.10 / F50 / S18 / K08: explicit clauses and empirical acceptance

[完整流程 / Workflow](SEMANTIC_RETRIEVAL.md) · [实际质量/错误 / Actual results](../validation/语义条件与校准拒识实测_2026-10-25.md) · [C19](CASES.md#c19-semantic-decisions).

中英条件检索与同帧正负比较、索引/类型/实现/实际设备绑定经验校准已交付。
中英條件檢索、同影格正負比較與裝置綁定經驗校準已實作。
`semantic calibrate/calibration-list/search` uses 32–128 reviewed examples (at least 16 positive and 16 absent),
a correct-positive gate and empirical strict cutoff. Labels stay in the controller. All results still require review.
Installed CPU/CUDA and the actual Skill retain two false accepts and one original false rejection.
The new retrieval package fails search after import even though general validate succeeds; portable profiles are not established.
Complex negation, natural actions/identity/audio/recommendation, large-library performance and managed semantic crash recovery remain open.
Original CLI 0.1.5 query failures and raw mode remain historical evidence; they are not erased by this extension.

<!-- /semantic-decisions-current -->

[Fixed-canvas affine reuse / 扫描行复用](AFFINE_RENDERING.md) uses the existing render workflow, keeps CPU composition explicit, and provides paired timing and actual previews.

[Animated crop and native-canvas projection / 动态裁切与嵌套投影](PROJECTION_RENDERING.md) retains the existing bilinear/area kernels, explicit raster quota and editable keys; CPU composition and GPU encoding remain separate.

CLI0.1.22: independent/inline Float32 text, joint typewriter/highlight and plain SRT. Read [workflow](FLOAT_TEXT.md); CPU,8bit coverage/Float32 colors,explicit fonts and original clocks. 4K text/GPU text/rich ASS and full target acceptance remain open.

Historical CLI0.1.23:[4K text and reusable native byte coverage](FLOAT_TEXT_COVERAGE.md). CPU tiled linear component composition,exact original clocks,bounded adaptive caches. GPU text,natural quality,HDR,realtime and full original conditions remain open.

CLI0.1.24:[native Float32 GPU workflow](FLOAT_GPU.md). Explicit geometry/normal composition/text colors/word selection;owned worker cleanup;CPU glyph rasterization and remaining operators retained. Full original target conditions remain open.

CLI0.1.25: [global/interval Float32 grading](FLOAT_ADJUSTMENTS.md); one selected root, authored clocks, explicit local LUT dependencies; CPU effects with compatible GPU composition. One Skill /17 modules /72 files.
