# 17 个本地 Skill 详情

[README](../../README.md) · [Registration](../local/INSTALLATION.md)

| 编号 | Skill | 职责 | 输入 → 输出 | 相关命令 | 依赖/边界 |
|---|---|---|---|---|---|
| K01 | [`$agent-ffmpeg-local-editor`](../../skills/agent-ffmpeg-local-editor/SKILL.md) | 项目总入口与交付 | brief + 本地素材 → 计划、可编辑工程、成片、manifest | `project init; timeline compose; look; render` | 按能力路由，包含滤镜客户选型；需要基础 CLI。 |
| K02 | [`$agent-ffmpeg-local-timeline`](../../skills/agent-ffmpeg-local-timeline/SKILL.md) | 时间线、关键帧与运镜 | 编辑 JSON → 多轨/运镜/转场/嵌套 | `timeline compose/edit; motion apply` | 明确目标轨道/片段与作者时钟。 |
| K03 | [`$agent-ffmpeg-local-quality`](../../skills/agent-ffmpeg-local-quality/SKILL.md) | 成片与像素核验 | 成片 + manifest + 参考 → 报告/Scope/差异 | `quality check/scopes/mask/golden` | 区分目检/播放/听审；支持滤镜样例选型复核。 |
| K04 | [`$agent-ffmpeg-local-project-ops`](../../skills/agent-ffmpeg-local-project-ops/SKILL.md) | 工程运维、恢复与队列 | 工程 + 作业 → 快照/恢复/重链/运行结果 | `project snapshot/recover; media relink; queue` | 保留旧源与失败；不是云任务调度器。 |
| K05 | [`$agent-ffmpeg-local-local-policy`](../../skills/agent-ffmpeg-local-local-policy/SKILL.md) | 本地执行约束 | 工程引用 → 审计/结构化拒绝 | `policy audit` | 运行时禁止远程引用；不推断为 OS 沙箱。 |
| K06 | [`$agent-ffmpeg-local-rights-ledger`](../../skills/agent-ffmpeg-local-rights-ledger/SKILL.md) | 素材与模型权利证据 | 来源/许可/本地证据 → 台账/影响/门禁 | `rights list/check/update/impact` | 分别处理母图与 LUT 许可；不自动认定版权。 |
| K07 | [`$agent-ffmpeg-local-local-models`](../../skills/agent-ffmpeg-local-local-models/SKILL.md) | 已有离线模型登记 | 原生环境 + 权重/哈希/许可 → 适配器与推理产物 | `media adapter; asr adapter; ocr; face; tts` | 无权重下载；先核对能力/环境，再调用。 |
| K08 | [`$agent-ffmpeg-local-video-understand`](../../skills/agent-ffmpeg-local-video-understand/SKILL.md) | 镜头/静音与视频证据 | 本地视频/音频 → 分析 JSON、帧、字幕候选 | `media understand/contact-sheet; subtitle transcribe` | 启发式与模型语义能力分开说明。 |
| K09 | [`$agent-ffmpeg-local-template-library`](../../skills/agent-ffmpeg-local-template-library/SKILL.md) | 模板与片段组复用 | 模板/变量/素材库 → 可编辑变体与索引 | `template apply/batch; library; fragment` | 用户自有素材，按资源许可复用。 |
| K10 | [`$agent-ffmpeg-local-long-to-short`](../../skills/agent-ffmpeg-local-long-to-short/SKILL.md) | 长视频转短片 | 本地课程/口播 + 核对文本 → 粗剪与短片工程 | `media highlights/smart-cut; timeline compose` | 候选段需复核，不声称全自动语义导演。 |
| K11 | [`$agent-ffmpeg-local-screen-demo`](../../skills/agent-ffmpeg-local-screen-demo/SKILL.md) | 录屏与锚点运镜 | 录屏 + 操作锚点 → 放大/回全景/字幕演示 | `timeline compose; ocr anchors; preview range` | OCR 需要已有模型，文本框不等于可点击控件。 |
| K12 | [`$agent-ffmpeg-local-reference-remake`](../../skills/agent-ffmpeg-local-reference-remake/SKILL.md) | 参考片节奏与布局重建 | 本地参考 + 原创替换素材 → 可编辑重制 | `media understand; timeline compose` | 重建结构，不自动获取或授权参考素材。 |
| K13 | [`$agent-ffmpeg-local-ffmpeg`](../../skills/agent-ffmpeg-local-ffmpeg/SKILL.md) | 原生音视频工具 | 本地文件 + 参数 → 转码/缩放/提取/压缩 | `native ffmpeg / ffprobe` | 直接原生工具；先检查编解码器。 |
| K14 | [`$agent-ffmpeg-local-video-edit`](../../skills/agent-ffmpeg-local-video-edit/SKILL.md) | 通用视频剪切流程 | 本地文件 + 剪辑要求 → 修剪/拼接/叠加结果 | `native ffmpeg; installed CLI` | 复杂可编辑项目交给 timeline/editor。 |
| K15 | [`$agent-ffmpeg-local-ad-creative`](../../skills/agent-ffmpeg-local-ad-creative/SKILL.md) | 广告创意与变体 | 产品/受众/证据 → hook/文案/脚本/变体 | `advisory; ad plan` | 策略任务说明，不自带媒体生成模型。 |
| K16 | [`$agent-ffmpeg-local-video-content-strategist`](../../skills/agent-ffmpeg-local-video-content-strategist/SKILL.md) | 视频内容策略 | 目标/受众/提供的参考 → 内容定位/系列/脚本 | `advisory Skill` | 不自带实时趋势、平台账号或抓取器。 |
| K17 | [`$agent-ffmpeg-local-campaign-analytics`](../../skills/agent-ffmpeg-local-campaign-analytics/SKILL.md) | 提供数据的投放分析 | 本地投放表 → ROAS/CPA/漏斗/建议 | `advisory Skill` | 无广告平台连接；指标依赖原始数据与归因假设。 |

## K01 · `$agent-ffmpeg-local-editor`

项目总入口与交付

brief + 本地素材 → 计划、可编辑工程、成片、manifest

`project init; timeline compose; look; render`

按能力路由，包含滤镜客户选型；需要基础 CLI。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/SKILL.md)

## K02 · `$agent-ffmpeg-local-timeline`

时间线、关键帧与运镜

编辑 JSON → 多轨/运镜/转场/嵌套

`timeline compose/edit; motion apply`

明确目标轨道/片段与作者时钟。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-timeline/SKILL.md)

## K03 · `$agent-ffmpeg-local-quality`

成片与像素核验

成片 + manifest + 参考 → 报告/Scope/差异

`quality check/scopes/mask/golden`

区分目检/播放/听审；支持滤镜样例选型复核。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-quality/SKILL.md)

## K04 · `$agent-ffmpeg-local-project-ops`

工程运维、恢复与队列

工程 + 作业 → 快照/恢复/重链/运行结果

`project snapshot/recover; media relink; queue`

保留旧源与失败；不是云任务调度器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-project-ops/SKILL.md)

## K05 · `$agent-ffmpeg-local-local-policy`

本地执行约束

工程引用 → 审计/结构化拒绝

`policy audit`

运行时禁止远程引用；不推断为 OS 沙箱。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-local-policy/SKILL.md)

## K06 · `$agent-ffmpeg-local-rights-ledger`

素材与模型权利证据

来源/许可/本地证据 → 台账/影响/门禁

`rights list/check/update/impact`

分别处理母图与 LUT 许可；不自动认定版权。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-rights-ledger/SKILL.md)

## K07 · `$agent-ffmpeg-local-local-models`

已有离线模型登记

原生环境 + 权重/哈希/许可 → 适配器与推理产物

`media adapter; asr adapter; ocr; face; tts`

无权重下载；先核对能力/环境，再调用。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-local-models/SKILL.md)

## K08 · `$agent-ffmpeg-local-video-understand`

镜头/静音与视频证据

本地视频/音频 → 分析 JSON、帧、字幕候选

`media understand/contact-sheet; subtitle transcribe`

启发式与模型语义能力分开说明。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-video-understand/SKILL.md)

## K09 · `$agent-ffmpeg-local-template-library`

模板与片段组复用

模板/变量/素材库 → 可编辑变体与索引

`template apply/batch; library; fragment`

用户自有素材，按资源许可复用。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-template-library/SKILL.md)

## K10 · `$agent-ffmpeg-local-long-to-short`

长视频转短片

本地课程/口播 + 核对文本 → 粗剪与短片工程

`media highlights/smart-cut; timeline compose`

候选段需复核，不声称全自动语义导演。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-long-to-short/SKILL.md)

## K11 · `$agent-ffmpeg-local-screen-demo`

录屏与锚点运镜

录屏 + 操作锚点 → 放大/回全景/字幕演示

`timeline compose; ocr anchors; preview range`

OCR 需要已有模型，文本框不等于可点击控件。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-screen-demo/SKILL.md)

## K12 · `$agent-ffmpeg-local-reference-remake`

参考片节奏与布局重建

本地参考 + 原创替换素材 → 可编辑重制

`media understand; timeline compose`

重建结构，不自动获取或授权参考素材。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-reference-remake/SKILL.md)

## K13 · `$agent-ffmpeg-local-ffmpeg`

原生音视频工具

本地文件 + 参数 → 转码/缩放/提取/压缩

`native ffmpeg / ffprobe`

直接原生工具；先检查编解码器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-ffmpeg/SKILL.md)

## K14 · `$agent-ffmpeg-local-video-edit`

通用视频剪切流程

本地文件 + 剪辑要求 → 修剪/拼接/叠加结果

`native ffmpeg; installed CLI`

复杂可编辑项目交给 timeline/editor。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-video-edit/SKILL.md)

## K15 · `$agent-ffmpeg-local-ad-creative`

广告创意与变体

产品/受众/证据 → hook/文案/脚本/变体

`advisory; ad plan`

策略任务说明，不自带媒体生成模型。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-ad-creative/SKILL.md)

## K16 · `$agent-ffmpeg-local-video-content-strategist`

视频内容策略

目标/受众/提供的参考 → 内容定位/系列/脚本

`advisory Skill`

不自带实时趋势、平台账号或抓取器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-video-content-strategist/SKILL.md)

## K17 · `$agent-ffmpeg-local-campaign-analytics`

提供数据的投放分析

本地投放表 → ROAS/CPA/漏斗/建议

`advisory Skill`

无广告平台连接；指标依赖原始数据与归因假设。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-campaign-analytics/SKILL.md)

## 滤镜客户选型

[Workflow](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [Gallery guide](../local/FILTER_GALLERY.md)

本机 17 个目录均为 E 盘源文件到 Codex 发现路径的联接。运行包与图册是分离交付：仅安装 wheel 并不自动包含图册。helper 只读已经渲染的样例，导出新对照板；最终编辑调用固定 CLI 并保存工程快照。
