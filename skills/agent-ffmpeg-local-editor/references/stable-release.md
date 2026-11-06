# Unified Skill / 統一Skill / 统一Skill

Stable distribution **v1.0.0**, engine **CLI0.1.66**, toolkit **r60**. Invoke
`$agent-ffmpeg-local-editor` as the single outer entry. It routes to 17 internal
references; do not register 17 additional Skills or silently call source code.

This Skill forwards arguments to the hash-pinned native offline installation.
The application ZIP and Skill ZIP are a pair. Run the included QUICKSTART first,
then version, doctor and capabilities through the actual installed launcher.
Basic `--base-only` setup does not install or execute optional AI models.

| ID | Internal module | Purpose | Reference |
|---|---|---|---|
| K01 | editor | 总入口：计划、项目创建与交付 / Editing and delivery entrypoint | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/editor/module.md) |
| K02 | timeline | 时间线、关键帧、运镜、转场、嵌套 / Timeline, keys and motion | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/timeline/module.md) |
| K03 | quality | 成片、像素、蒙版、Scope 与证据核验 / Output and pixel review | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/quality/module.md) |
| K04 | project-ops | 快照、恢复、重链和队列 / Project operations, recovery and queues | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/project-ops/module.md) |
| K05 | local-policy | 离线运行与远程引用审计 / Local execution policy | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/local-policy/module.md) |
| K06 | rights-ledger | 素材、字体、模型与模板权利台账 / Media and model rights evidence | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/rights-ledger/module.md) |
| K07 | local-models | 显式登记并运行已有离线模型 / Existing offline model registration | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/local-models/module.md) |
| K08 | video-understand | 镜头、静音、帧证据与转写 / Scene/silence and video evidence | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md) |
| K09 | template-library | 模板变量、素材索引和片段组复用 / Templates and reusable fragments | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/template-library/module.md) |
| K10 | long-to-short | 长视频、课程和口播转短片 / Long video to short clips | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/long-to-short/module.md) |
| K11 | screen-demo | 录屏锚点、缩放与产品演示 / Screen demos and camera anchors | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/screen-demo/module.md) |
| K12 | reference-remake | 参考片结构复刻与原创素材替换 / Reference pacing/layout remake | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/reference-remake/module.md) |
| K13 | ffmpeg | 本地 FFmpeg 格式和媒体处理 / Native media tools | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/ffmpeg/module.md) |
| K14 | video-edit | 修剪、拼接、变速与压缩 / General video-edit workflows | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/video-edit/module.md) |
| K15 | ad-creative | 广告文案、Hook 和创意变体 / Ad creative and variants | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md) |
| K16 | video-content-strategist | 内容定位、脚本与渠道策略 / Video content strategy | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/video-content-strategist/module.md) |
| K17 | campaign-analytics | 依据本地数据分析投放与变体 / Supplied campaign-data analysis | [module](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/modules/campaign-analytics/module.md) |

## Agent workflow and client selection

1. Confirm output dimensions, frame rate, language, deliverables, available media,
   models and client-approved rights. Inspect capabilities and the actual schema.
2. Create an Agent Project. Ingest actual files and keep returned asset IDs. Edit
   JSON using those IDs; video, music and voice require explicit separate tracks.
3. For style selection, use real previews from the 500-look gallery below. Show
   the original and chosen candidates, stable IDs, intensity and source/license.
   Read `references/client-look-selection.md`; do not present generated mockups
   as application output. Save the client's selected ID before applying it.
4. Add trim, keyframes, motion, captions and transitions. For AI operations, read
   only the relevant module/model reference, explicitly register the available
   local adapter, prefer the configured GPU, and inspect the actual provider.
   Some CUDA neural adapters require GPU and reject CPU fallback. CPU font layout
   and CPU signal conversion do not become GPU operations through documentation.
5. Validate, preview, render, quality-check and inspect actual outputs. Review
   complete audio separately. An `ok` JSON response is not natural-quality approval.
6. Export the editable package, import into a new path and rerender. Keep complete
   frame/audio/time/source hashes and record any external model/runtime dependency.

## Real filter previews

All 500 styles use the same supplied N002 still. The gallery supports names,
search, categories and a client shortlist. Images preview intensity 1.0 unless
otherwise specified. For a different source or intensity, use `look preview`.
The LUTs describe creative looks, not certified manufacturer color science.

[500-preview gallery](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/docs/assets/looks-n002-20261024-r1/index.html)
· [client selection instructions](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/client-look-selection.md)
· [complete manual](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/README.en.md)

CLI67 portrait regions and experimental rich typography are not installed by
this toolkit. Original G01–G38 remains open. Older evidence retains its original
version/date. Do not add full-GUI, cloud-service, model-quality or CapCut-parity
claims to a client proposal based only on this stable distribution label.
