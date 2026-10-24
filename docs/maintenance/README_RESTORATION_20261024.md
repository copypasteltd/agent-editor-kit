# README 内容缩减原因与系统恢复 / README reduction and restoration

日期：2026-10-24。基准 `main`：`1aa13905739bbb45e2d8708af7773e707098ef49`。本次是文档、样例与 Skill 选型工具更新，不改写 alpha.3 运行包，不覆盖既有公开标签或附件。
Date: 2026-10-24. This update restores documentation, adds real sample outputs and a Skill selection helper, without replacing the alpha.3 runtime bundle or prior published tags/assets.

## 为什么以前的 README 内容少了

发布整理时，把累积的 V 系列功能核验、原视频/GIF、完整命令/响应与长篇说明移动到了 `docs/releases/v0.1.0-alpha.1/history/` 和各版本手册。随后 100/500 套风格与三语维护继续使用精简的首页生成器，新增内容也被压成摘要和链接。

这导致首页虽有索引，却缺少可直接阅读的功能细节、服务依赖、Skill 输入输出与演示信息。**归档保留了历史，但用摘要取代用户要求的完整产品说明，是这次文档处理的问题。** 不能以“长日志不适合首页”为由省略功能说明和案例。

The release documentation moved accumulated V-series checks, original videos/GIFs, commands/responses and long notes into archived/versioned manuals. Later look-library and multilingual updates reused a condensed homepage generator. The history survived, but the homepage lost directly useful functionality, dependencies, Skill I/O and demonstrations. Replacing the requested complete product explanation with summaries was a documentation mistake.

| 对照 | 字节 | 行数 | 说明 |
|---|---:|---:|---|
| 发布前完整中文 README | 368,103 | 1,906 | [不可改写的历史说明](../releases/v0.1.0-alpha.1/history/README.zh.pre-release.md) |
| 本次更新前的中文 README | 22,758 | 189 | 对应上述基准提交；正文约缩减 94% |
| 本次恢复版本 | 见核验回执 | 见核验回执 | [三语文档核验](../validation/evidence/looks-n002-20261024-r1/docs-verification.json) 保存实际大小与本地链接检查 |

字节/行数不是功能完成度。此次从正式安装版读取了 68 个能力分组、46 个效果算子、12 个运镜预设，文档按 43 个功能说明模块、12 个服务模块整理；模块有依赖和交叉，不是 43 个独立算法。能力字段是当前发行契约，不代表本轮对每个能力重新执行完整验收。
Bytes and line counts are not completion scores. The installed runtime supplies 68 capability groups, 46 operators and 12 motion presets, documented in 43 functional groups and 12 service groups with overlap/dependencies. These contracts are not newly rerun acceptance for every capability.

## 本次恢复和新增内容

| 编号 | 内容 | 交付位置 |
|---|---|---|
| D01 | 简体/繁体/英文首页，功能、服务、依赖、安装、完整闭环、错误恢复、案例和编号核验 | [简体](../../README.md)、[繁體](../../README.zh-TW.md)、[English](../../README.en.md) |
| D02 | 完整安装版能力契约与所有字段，46 算子参数、12 运镜参数 | [能力手册](../product/CAPABILITIES.md)、[效果手册](../product/EFFECTS.md)、对应机器 JSON |
| D03 | 17 个 Skill 的作用、输入输出、入口、依赖、边界和本地加载 | [Skill 手册](../product/SKILLS.md)、各 Skill 正文 |
| D04 | 42 个既有演示图恢复至完整案例册，保留原输入/输出/指标/失败，研究与产品区分 | [案例册](../product/CASES.md) |
| D05 | 用户 N002 母图的 500 次真实 CLI 预览；全尺寸无损图和浏览小图各 500 张 | [样例清单](../assets/looks-n002-20261024-r1/manifest.json)、[真实执行](../validation/evidence/looks-n002-20261024-r1/render-verification.json) |
| D06 | 搜索/分类/许可/原图对照/勾选/候选 JSON 导出；本地 HTML、桌面和手机截图、实际操作录屏 | [交互页](../assets/looks-n002-20261024-r1/index.html)、[浏览器记录](../validation/evidence/looks-n002-20261024-r1/browser-verification.json) |
| D07 | 500 套逐项图册（三语），每个详细风格 profile 同步显示 N002 结果 | [图册](../local/FILTER_GALLERY.md)、[详情](../local/LOOK_PRESETS.md) |
| D08 | Agent 给客户展示候选、生成对照板、记录最终 ID/强度/作用域的可执行流程 | [Skill 说明](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md)、[对照板工具](../../skills/agent-ffmpeg-local-editor/scripts/look_gallery.py) |

## 图像与核验口径

母图 `N002.png` 1672×940 RGB，SHA-256 `babaa64ce3434a23133c41a1d2b4fad384a5e6707546b527508d4731ba83ab4b`，原始字节不变。安装版每套实际运行 `look preview`，强度统一 1.0、四面体插值。全尺寸无损 WebP 与 CLI PNG 的 RGB 全像素一致，小图是 512×288 的缩放/有损编码。只有这一张用户提供的图被用于本次滤镜比较，不泛化为全部自然视频画质、肤色保护或 HDR 验收。

母图没有嵌入色彩配置，本次按编码 SDR RGB 试片，不推断相机色彩。用户明确提供并要求用于 README/Skill 展示，未将母图或全部衍生图声明为软件 MIT 或 CC0。LUT 的作者/来源/独立许可与母图分别记录在 [资源说明](../assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md)。

新核验 R25–R28 单列：真实渲染、选型页、Skill/helper、文档/链接。历史 2,930 项内核全量、旧模型与旧视频不重跑、不相加。选型 GIF 是实际静态样例切换；WebM 是真实文档页操作录像，不是剪辑器 GUI。浏览器验证后所有本任务页面均关闭；未调度 Docker、WSL 或虚拟环境。

## 后续维护

`scripts/build_product_readmes.py` 维护完整三语文档；`scripts/readme_product_content.py` 保存经核对的功能/服务/Skill 双语内容。原来的 `build_look500_readmes.py` 已改成完整生成器的兼容入口，防止后续更新再次把 README 变成精简摘要。`build_look500_docs.py` 生成详情时会保留 N002 样例；`build_n002_gallery_docs.py` 同步图册、功能滤镜 README 与版权说明。

每次能力变更同步首页、机器契约、具体手册和相关 Skill；保留日期与执行证据。长篇旧日志继续归档，但首页需要保留行为、输入输出、依赖、使用步骤和可访问的真实案例。维护 `main`，检查后普通推送到 `copypasteltd/agent-editor-kit`，不覆盖已发布历史附件。
