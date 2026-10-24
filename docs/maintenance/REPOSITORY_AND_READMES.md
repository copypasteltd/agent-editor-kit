# agent editor kit：仓库、产品名与 README 维护

2026-10-24 起，产品名称为 **agent editor kit**，代码和后续自动推送的唯一目标为 [copypasteltd/agent-editor-kit](https://github.com/copypasteltd/agent-editor-kit)。本地继续在 `E:/dev/sandbox/AI广告剪辑/` 开发，主分支为 `main`。

## 推送配置

`origin` 的拉取和推送 URL 均为：

```text
git@github.com:copypasteltd/agent-editor-kit.git
```

现有 post-commit hook 调用 `git-auto-push.ps1`。脚本核对 `main`、origin 地址及唯一的有效推送地址，再执行普通 `git push origin main`。后续更新无需再次变更目标。迁移前已检查新仓库 main 为 `f76995ce0791cc093baff047167b5774005593ea`，它是本地 main 的祖先，本次使用普通快进推送。

## 三种语言

| 语言 | 完整产品 README |
|---|---|
| 简体中文 | [README.md](../../README.md) |
| 繁體中文（臺灣用語） | [README.zh-TW.md](../../README.zh-TW.md) |
| English | [README.en.md](../../README.en.md) |

三份文档提供相互切换入口，覆盖相同的安装、使用、13 项能力、4 个案例、17 个 Skill、编号核验记录和功能边界。后续变更须同步更新三份 README 与 [文档索引](../README.md)。翻译正文和链接标签时，命令、参数、稳定 ID、文件名、中文路径、链接目标和代码块保持可执行的原文。

繁体版以简体正文为基础，使用 Windows 原生字符转换并人工校对影片、音讯、时间轴、关键影格和专案等用语；不需要安装额外转换依赖。

## 版本与历史材料

本次为仓库配置与文档更新。当前本地安装版本仍为 `v0.1.0-alpha.2`（CLI `0.1.1`），现有安装包文件名采用历史 `agent-video-kit-*` 前缀，命令与 `$agent-ffmpeg-local-*` 调用入口见 README。当前产品标题统一采用 **agent editor kit**。

原仓库为 `Tonscriptions/agent-video-kit`。已公开的 alpha.1 标签、发布附件、历史报告和带哈希的核验记录保存当时名称与来源；它们提供历史证据。新仓库的当前安装入口指向随 Git 保存的 alpha.2 ZIP。本次不新建 GitHub Release，也不改写已验证的安装包字节。

## 本轮核验

检查三份 README 的完整性、语言切换、相同代码块与链接目标、全部本地文件链接，以及自动推送脚本语法和新目标的 dry-run。[机器可读回执](../validation/evidence/readme-rebrand-20261024-r1/verification.json)记录检查结果；README 的 R20 单列本轮文档核验，历史测试和渲染数量沿用原日期。

本次未修改视频处理代码、未新增渲染或模型推理，未重新执行历史产品回归测试。
