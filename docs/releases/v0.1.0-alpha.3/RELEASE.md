# agent editor kit v0.1.0-alpha.3 发行范围

[下载](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v0.1.0-alpha.3) · [简体上手](QUICKSTART.md) · [繁體上手](QUICKSTART.zh-TW.md) · [English](QUICKSTART.en.md) · [发行说明](RELEASE-NOTES.md)

本次发布已有本地验证的 alpha.3 为 GitHub **预发布版**。应用 CLI 为 0.1.2，风格目录为 2.0.0。沿用原运行包及其 SHA-256，不重新打包应用、不更改既有分卷、旧标签或历史附件。

运行包 SHA-256：`1a967e4def2afc14e9f110c6cad90e172ff457a77ef405cb83932f1f1187b968`。

本次新增的是发行交付层：可直接下载的运行 ZIP、带离线安装入口的 17-Skill Agent kit、可执行示例、独立可选的 500 样例图册、三语上手指南，以及相应的安装/示例/发布下载核对记录。

| 范围 | 当前交付 |
|---|---|
| 平台 | 原生 Windows x64 / 已有 CPython 3.13 x64 / FFmpeg 与 ffprobe |
| 核心 | 结构化 CLI、可编辑项目、多轨剪辑、关键帧、字幕、音频、蒙版、效果、渲染、质检、工程包与本地权利门禁，具体依赖与限制以 capabilities 为准 |
| 风格 | 500 套具名 SDR 风格、46 效果算子、12 运镜；500 样例为独立图册交付 |
| Skills | 17 个 `$agent-ffmpeg-local-*`；离线安装后注册，调用固定安装版 |
| 首次示例 | CC0 虚构广告素材 → 6 秒竖屏视频、运镜、0.65 风格、显式音轨、实际质检与工程包往返 |
| 模型/浏览器 | 不随基础包分发，不能把适配器声明当作权重已经安装 |
| 网络 | 开发和 GitHub 发布核对使用网络；产品示例和离线安装不下载模型或媒体 |

此前差距评估 G38 的“alpha.3 尚无独立 GitHub Release”在此次公开发布成功后关闭；完整正式版门禁、自然素材视听质量、已知字幕/音频/抠像问题与其他功能差距继续保留。[原始差距快照](../../product/GOAL_GAPS_20261024.md)不重写为历史上已完成。

本次公开预发布不等于完整剪映功能/效果验收，不将历史回归和当轮验证累计成完成率。基础内核的历史 2,930 项回归保留原证据；本次执行安装和发行示例验证，不宣称重跑该完整套件。详情及当前结果见 README 的新增编号核验与本次机器证据。

English: this publishes the already tested alpha.3 native runtime, retaining its immutable bytes and limitations. New delivery assets add a portable Agent kit, offline bootstrap, executable CC0 example, optional full look gallery and three-language instructions. It remains a prerelease with explicit capability limits, optional external model dependencies and open natural-media quality gates.

## 本次发行实测

[机器核验记录](../../validation/evidence/release-v0.1.0-alpha.3-r1/verification.json)保留新目录安装回执、17 个 Skill 联接、4 次注册入口查询、20 次示例 CLI、2 次预期拒绝、实际编码信息与解码日志。[示例 MP4](../../assets/release-v0.1.0-alpha.3-r1/demo.mp4)与 [GIF](../../assets/release-v0.1.0-alpha.3-r1/demo.gif)由本次实际输出生成；输入为 CC0 虚构图片和合成音频。安装目录含中文与空格，但仍是现有主机的新目录，不能替代第二台干净主机验证。没有浏览器调用或新模型推理，未做连续播放和听审。

公开附件按 `public/assets.lock.json` 锁定名称、字节与 SHA-256。标签推送后由原生 Windows GitHub Actions 重建附件、比对锁文件，上传齐全后公开预发布；公开后的实际下载核对另存 publication 回执，不改写运行包中的历史构建信息。

文档链接核验覆盖三语 README、三语上手指南及当前 Skill 入口和共享契约。`references/upstream/` 是原样保留的历史来源快照，其中旧相对路径仍带原仓库语境，不能作为本版安装入口；首次扩大检查已发现一处遗留策略链接不适用于搬迁后的快照。当前执行以 QUICKSTART、Skill 正文与共享 runtime 契约为准，这一历史引用边界写入本次文档核验回执。
