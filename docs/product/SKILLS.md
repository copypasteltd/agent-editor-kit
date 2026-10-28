# 一个本地 Skill、17 项内部模块详情

<!-- community-current -->

**CLI0.1.43 / alpha.4-local.41 / r44 kit · 1 Skill / 17 modules / 82 files.**

新增**真实本地 CUDA DeepFilterNet3 对白降噪**：原生采样时钟、单/双声道、独立增强资产与可编辑音轨、强度/衰减上限、分段重叠、配方重跑、工程包和取消回滚。

[Speech enhancement workflow](SPEECH_ENHANCEMENT.md)

<!-- /community-current -->

<!-- unified-skill-registration -->

只注册 `$agent-ffmpeg-local-editor`。K01–K17 是按需读取的内部模块，原独立名称只用于追溯，调用时无需再指定。 [Guide](../skills/UNIFIED_SKILL.md)

<!-- /unified-skill-registration -->

[README](../../README.md) · [Registration](../local/INSTALLATION.md)

| 编号 | 内部模块 | 职责 | 输入 → 输出 | 相关命令 | 依赖/边界 |
|---|---|---|---|---|---|
| K01 | [`$agent-ffmpeg-local-editor`](../../skills/agent-ffmpeg-local-editor/SKILL.md) | 项目总入口与交付 | brief + 本地素材 → 计划、可编辑工程、成片、manifest | `project init; timeline compose; look; render` | 按能力路由，包含滤镜客户选型；需要基础 CLI。 |
| K02 | [`timeline`](../../skills/agent-ffmpeg-local-editor/references/modules/timeline/module.md) | 时间线、关键帧与运镜 | 编辑 JSON → 多轨/运镜/转场/嵌套 | `timeline compose/edit; motion apply; motion pack list/inspect/create/capture/apply` | 明确目标轨道/片段与作者时钟。 |
| K03 | [`quality`](../../skills/agent-ffmpeg-local-editor/references/modules/quality/module.md) | 成片与像素核验 | 成片 + manifest + 参考 → 报告/Scope/差异 | `quality check/scopes/mask/golden` | 区分目检/播放/听审；支持滤镜样例选型复核。 |
| K04 | [`project-ops`](../../skills/agent-ffmpeg-local-editor/references/modules/project-ops/module.md) | 工程运维、恢复与队列 | 工程 + 作业 → 快照/恢复/重链/运行结果 | `project snapshot/recover; media relink; queue` | 保留旧源与失败；不是云任务调度器。 |
| K05 | [`local-policy`](../../skills/agent-ffmpeg-local-editor/references/modules/local-policy/module.md) | 本地执行约束 | 工程引用 → 审计/结构化拒绝 | `policy audit` | 运行时禁止远程引用；不推断为 OS 沙箱。 |
| K06 | [`rights-ledger`](../../skills/agent-ffmpeg-local-editor/references/modules/rights-ledger/module.md) | 素材与模型权利证据 | 来源/许可/本地证据 → 台账/影响/门禁 | `rights list/check/update/impact` | 分别处理母图与 LUT 许可；不自动认定版权。 |
| K07 | [`local-models`](../../skills/agent-ffmpeg-local-editor/references/modules/local-models/module.md) | 已有离线模型登记 | 原生环境 + 权重/哈希/许可 → 适配器与推理产物 | `audio adapter; audio separate-stems; media adapter; asr adapter; ocr; face; tts` | 无权重下载；先核对能力/环境，再调用。 |
| K08 | [`video-understand`](../../skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md) | 镜头/静音、图文语义检索与视频证据 | 本地视频/图片/描述/参考图 → 分析、预览、源时间与候选 | `media understand/contact-sheet; subtitle transcribe; semantic index/calibrate/calibration-list/search; project upgrade-semantic` | [检索说明](../../skills/agent-ffmpeg-local-editor/references/semantic-retrieval.md)；采样点不定义片段时长，候选需复核。 |
| K09 | [`template-library`](../../skills/agent-ffmpeg-local-editor/references/modules/template-library/module.md) | 模板与片段组复用 | 模板/变量/素材库 → 可编辑变体与索引 | `template apply/batch; library; fragment` | 用户自有素材，按资源许可复用。 |
| K10 | [`long-to-short`](../../skills/agent-ffmpeg-local-editor/references/modules/long-to-short/module.md) | 长视频转短片 | 本地课程/口播 + 核对文本 → 粗剪与短片工程 | `media highlights/smart-cut; timeline compose` | 候选段需复核，不声称全自动语义导演。 |
| K11 | [`screen-demo`](../../skills/agent-ffmpeg-local-editor/references/modules/screen-demo/module.md) | 录屏与锚点运镜 | 录屏 + 操作锚点 → 放大/回全景/字幕演示 | `timeline compose; ocr anchors; preview range` | OCR 需要已有模型，文本框不等于可点击控件。 |
| K12 | [`reference-remake`](../../skills/agent-ffmpeg-local-editor/references/modules/reference-remake/module.md) | 参考片节奏与布局重建 | 本地参考 + 原创替换素材 → 可编辑重制 | `media understand; timeline compose` | 重建结构，不自动获取或授权参考素材。 |
| K13 | [`ffmpeg`](../../skills/agent-ffmpeg-local-editor/references/modules/ffmpeg/module.md) | 原生音视频工具 | 本地文件 + 参数 → 转码/缩放/提取/压缩 | `native ffmpeg / ffprobe` | 直接原生工具；先检查编解码器。 |
| K14 | [`video-edit`](../../skills/agent-ffmpeg-local-editor/references/modules/video-edit/module.md) | 通用视频剪切流程 | 本地文件 + 剪辑要求 → 修剪/拼接/叠加结果 | `native ffmpeg; installed CLI` | 复杂可编辑项目交给 timeline/editor。 |
| K15 | [`ad-creative`](../../skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md) | 广告创意、可编辑分镜与变体 | 产品/受众/审核文案/实际资产 → 计划、独立序列与局部返工 | `advisory; ad plan; ad storyboard/build/revise` | 创意选择与卖点证据明确提供；不自带生成视频模型。 |
| K16 | [`video-content-strategist`](../../skills/agent-ffmpeg-local-editor/references/modules/video-content-strategist/module.md) | 视频内容策略 | 目标/受众/提供的参考 → 内容定位/系列/脚本 | `advisory Skill` | 不自带实时趋势、平台账号或抓取器。 |
| K17 | [`campaign-analytics`](../../skills/agent-ffmpeg-local-editor/references/modules/campaign-analytics/module.md) | 提供数据的投放分析 | 本地投放表 → ROAS/CPA/漏斗/建议 | `advisory Skill` | 无广告平台连接；指标依赖原始数据与归因假设。 |

## K01 · `$agent-ffmpeg-local-editor`

项目总入口与交付

brief + 本地素材 → 计划、可编辑工程、成片、manifest

`project init; timeline compose; look; render`

按能力路由，包含滤镜客户选型；需要基础 CLI。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/SKILL.md)

## K02 · `timeline`

时间线、关键帧与运镜

编辑 JSON → 多轨/运镜/转场/嵌套

`timeline compose/edit; motion apply`

明确目标轨道/片段与作者时钟。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/timeline/module.md)

## K03 · `quality`

成片与像素核验

成片 + manifest + 参考 → 报告/Scope/差异

`quality check/scopes/mask/golden`

区分目检/播放/听审；支持滤镜样例选型复核。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/quality/module.md)

## K04 · `project-ops`

工程运维、恢复与队列

工程 + 作业 → 快照/恢复/重链/运行结果

`project snapshot/recover; media relink; queue`

保留旧源与失败；不是云任务调度器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/project-ops/module.md)

## K05 · `local-policy`

本地执行约束

工程引用 → 审计/结构化拒绝

`policy audit`

运行时禁止远程引用；不推断为 OS 沙箱。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/local-policy/module.md)

## K06 · `rights-ledger`

素材与模型权利证据

来源/许可/本地证据 → 台账/影响/门禁

`rights list/check/update/impact`

分别处理母图与 LUT 许可；不自动认定版权。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/rights-ledger/module.md)

## K07 · `local-models`

已有离线模型登记

原生环境 + 权重/哈希/许可 → 适配器与推理产物

`media adapter; asr adapter; ocr; face; tts; voice; translate; dub subtitles; gpu`

无权重下载；先核对能力/环境，再调用。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/local-models/module.md)

## K08 · `video-understand`

镜头/静音与视频证据

本地视频/音频 → 分析 JSON、帧、字幕候选

`media understand/contact-sheet; subtitle transcribe; semantic index/calibrate/calibration-list/search`

启发式与模型语义能力分开说明。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md)

## K09 · `template-library`

模板与片段组复用

模板/变量/素材库 → 可编辑变体与索引

`template apply/batch; library; fragment`

用户自有素材，按资源许可复用。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/template-library/module.md)

## K10 · `long-to-short`

长视频转短片

本地课程/口播 + 核对文本 → 粗剪与短片工程

`media highlights/smart-cut; timeline compose`

候选段需复核，不声称全自动语义导演。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/long-to-short/module.md)

## K11 · `screen-demo`

录屏与锚点运镜

录屏 + 操作锚点 → 放大/回全景/字幕演示

`timeline compose; ocr anchors; preview range`

OCR 需要已有模型，文本框不等于可点击控件。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/screen-demo/module.md)

## K12 · `reference-remake`

参考片节奏与布局重建

本地参考 + 原创替换素材 → 可编辑重制

`media understand; timeline compose`

重建结构，不自动获取或授权参考素材。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/reference-remake/module.md)

## K13 · `ffmpeg`

原生音视频工具

本地文件 + 参数 → 转码/缩放/提取/压缩

`native ffmpeg / ffprobe`

直接原生工具；先检查编解码器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/ffmpeg/module.md)

## K14 · `video-edit`

通用视频剪切流程

本地文件 + 剪辑要求 → 修剪/拼接/叠加结果

`native ffmpeg; installed CLI`

复杂可编辑项目交给 timeline/editor。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/video-edit/module.md)

## K15 · `ad-creative`

广告创意与变体

产品/受众/证据 → hook/文案/脚本/变体

`advisory; ad plan`

策略任务说明，不自带媒体生成模型。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md)

## K16 · `video-content-strategist`

视频内容策略

目标/受众/提供的参考 → 内容定位/系列/脚本

`advisory Skill`

不自带实时趋势、平台账号或抓取器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/video-content-strategist/module.md)

## K17 · `campaign-analytics`

提供数据的投放分析

本地投放表 → ROAS/CPA/漏斗/建议

`advisory Skill`

无广告平台连接；指标依赖原始数据与归因假设。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/campaign-analytics/module.md)

## 滤镜客户选型

[Workflow](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [Gallery guide](../local/FILTER_GALLERY.md)

本机只注册一个指向统一 Skill 的目录联接；17 项模块在目录内按需读取。运行包与图册是分离交付：仅安装 wheel 并不自动包含图册。helper 只读已经渲染的样例，导出新对照板；最终编辑调用固定 CLI 并保存工程快照。


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
