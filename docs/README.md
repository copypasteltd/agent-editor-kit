# agent editor kit 文档 / Documentation

[简体中文](../README.md) · [繁體中文](../README.zh-TW.md) · [English](../README.en.md) · [Repository](https://github.com/copypasteltd/agent-editor-kit) · [Local package parts](releases/v0.1.0-alpha.3/artifacts)

当前为 **v0.1.0-alpha.3 / CLI 0.1.2 / 500 离线风格**，已安装并同步 17 个本地 Skill；完整剪映等价仍未验收。Current local build has 500 named looks, measured per-look profiles, individual licenses and installed native verification.

| 阅读目标 / Goal | Document |
|---|---|
| 当前完整功能与本地服务模块、安装版全部能力字段 / Complete functional and service modules | [简体](product/CAPABILITIES.md) · [繁體](product/CAPABILITIES.zh-TW.md) · [English](product/CAPABILITIES.en.md) |
| 46 效果算子与 12 运镜的具体参数、范围、后端 / Full effect and motion parameters | [简体](product/EFFECTS.md) · [繁體](product/EFFECTS.zh-TW.md) · [English](product/EFFECTS.en.md) |
| 当前 17 个新命名 Skill 的输入输出、依赖与职责 / Current Skill details | [简体](product/SKILLS.md) · [繁體](product/SKILLS.zh-TW.md) · [English](product/SKILLS.en.md) |
| N002 母图的全部 500 套实际滤镜样例、原图与客户选型 / All supplied-image previews | [交互图册](assets/looks-n002-20261024-r1/index.html) · [简体说明](local/FILTER_GALLERY.md) · [繁體說明](local/FILTER_GALLERY.zh-TW.md) · [English](local/FILTER_GALLERY.en.md) |
| 恢复的全部演示与原输入/输出/失败记录 / Restored full demonstration casebook | [Complete cases](product/CASES.md) |
| README 缩减原因、恢复范围与维护方式 / README reduction and restoration | [Restoration record](maintenance/README_RESTORATION_20261024.md) |
| 新仓库、产品名称与三语维护规则 / Repository, name and README languages | [Maintenance record](maintenance/REPOSITORY_AND_READMES.md) |
| 500 预设完整编号、分类与实际预览 / Numbered look catalog | [500 looks](local/LOOK_PRESETS.md) |
| 历史 100 项实际色彩作用、灰阶/肤色/三色数值与场景建议 / Detailed measured profiles | [简体详情](local/LOOK_PRESET_DETAILS.md) · [繁體詳情](local/LOOK_PRESET_DETAILS.zh-TW.md) · [数据与核验](validation/evidence/look-profiles-20261024-r1/verification.json) |
| 新包分卷安装、检索、预览与应用 / Alpha.3 usage | [Alpha.3 manual](releases/v0.1.0-alpha.3/USAGE.md) |
| 500 预设实测、定向回归、Skill 与项目包 / Current verification | [500-look verification](validation/LOOK500_20261024.md) |
| 本机正式安装、17 个新名称与实际 Skill 调用 / Installed app and new Skill namespace | [Local installation](local/INSTALLATION.md) |
| 500 套实际详情与功能性 README / Full profiles and filter workflow | [简体](local/FILTERS.md) · [繁體](local/FILTERS.zh-TW.md) · [English](local/FILTERS.en.md) |
| 开源风格库来源、Star、许可、工程量与社区 LUT 实测 / Open looks: sources, licenses, effort and real probe | [Open look-library assessment](research/OPEN_LOOK_LIBRARY_20261024.md) |
| 安装、结构、命令、渲染路径、故障与恢复 / Install and operate | [USAGE](releases/v0.1.0-alpha.1/USAGE.md) |
| 发行时的 17 个旧名 Skill / Original release Skill names | [SKILLS](releases/v0.1.0-alpha.1/SKILLS.md) |
| 原视频、输出、GIF、响应与复现 / Complete examples | [CASES](releases/v0.1.0-alpha.1/CASES.md) |
| 范围、验收、风险与下一阶段 / Release scope and gates | [RELEASE](releases/v0.1.0-alpha.1/RELEASE.md) |
| 许可与依赖 / Notices | [THIRD_PARTY](releases/v0.1.0-alpha.1/THIRD_PARTY.md) |
| 本地案例阅读页 / Local documentation gallery | [Demo page](demo/index.html), serve locally as described in CASES |
| 需求与路径基线 / Product baseline | [产品需求与开发路线基线](产品需求与开发路线基线_2026-10-12.md) |
| 模块边界 / Architecture | [系统边界与模块契约](architecture/系统边界与模块契约_v0.1_2026-10-13.md) |
| Agent Project 合同 / Schema | [JSON schema](specs/agent-project.schema.json) |
| 当前基线完整回归 / Frozen baseline | [2930-method receipt](validation/evidence/float-shaper-20261023-lab/full-r1.json) |
| 本轮发布验证 / New release checks | [Release gate](validation/evidence/release-v0.1.0-alpha.1-r2/release-verification.json) |
| 远端发布与 6 个附件下载核验 / Published assets verified | [Publication receipt](validation/evidence/release-v0.1.0-alpha.1-r2/publication.json) |
| 历史编号功能与核验 / Complete historical numbered checks | [Archived README](releases/v0.1.0-alpha.1/history/README.zh.pre-release.md) |
| 历史全部文档入口 / Historical document catalog | [Archived index](releases/v0.1.0-alpha.1/history/docs-index.pre-release.md) |

专项合同保留在 `specs/`，真实实测和失败记录在 `validation/`，媒体在 `assets/`，第三方来源在 `third-party/`，版本发布文档在 `releases/`。不将历史测试、当轮案例和研究检查累计为一个“完成度”。
Contracts remain in specs; raw successes/failures in validation; media in assets; upstream evidence in third-party; milestone guides in releases. Historical tests, new cases and research checks retain separate scopes.
