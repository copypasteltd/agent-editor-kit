# agent editor kit 文档 / Documentation

[简体中文](../README.md) · [繁體中文](../README.zh-TW.md) · [English](../README.en.md) · [Repository](https://github.com/copypasteltd/agent-editor-kit) · [Local package](releases/v0.1.0-alpha.2/artifacts/agent-video-kit-v0.1.0-alpha.2-cp313-win_amd64.zip)

产品名称为 `agent editor kit`，后续代码维护于 `copypasteltd/agent-editor-kit`。原仓库公开首版是 `v0.1.0-alpha.1`；本机后续构建已升级到 `v0.1.0-alpha.2`（CLI `0.1.1`），新增 100 个离线风格预设和本地 Skill 更新。新仓库尚未发布对应 GitHub Release，可从上方本地包链接获取。完整剪映等价仍未验收。The product is now agent editor kit; all future updates go to the new repository. Complete READMEs are available in Simplified Chinese, Traditional Chinese and English; versioned manuals remain bilingual.

| 阅读目标 / Goal | Document |
|---|---|
| 新仓库、产品名称与三语维护规则 / Repository, name and README languages | [Maintenance record](maintenance/REPOSITORY_AND_READMES.md) |
| 100 预设完整编号、分类与实际预览 / Numbered look catalog | [100 looks](local/LOOK_PRESETS.md) |
| 新包安装、检索、预览与应用 / Alpha.2 usage | [Alpha.2 manual](releases/v0.1.0-alpha.2/USAGE.md) |
| 100 预设实测、单元回归、Skill 与项目包 / Current verification | [Look verification](validation/LOOK_PRESETS_20261024.md) |
| 本机正式安装、17 个新名称与实际 Skill 调用 / Installed app and new Skill namespace | [Local installation](local/INSTALLATION.md) |
| 滤镜、LUT 格式、调色与关键帧 / Filters, LUTs and grading | [Filters](local/FILTERS.md) |
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
