# agent editor kit v0.1.0-alpha.4

公开时间：2026-11-06 19:22:05，Asia/Taipei（11:22:05Z）。[GitHub Release](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v0.1.0-alpha.4)；源提交`2eb9130c45fa446b1f328df777a0a3624d681990`，CLI0.1.66／local64／统一Skill r59。原标签与附件保留，未覆盖旧发行。

## 使用流程 / 使用流程 / Workflow

[简体中文快速开始](QUICKSTART.md) · [繁體中文快速開始](QUICKSTART.zh-TW.md) · [English quickstart](QUICKSTART.en.md) · [Release notes](RELEASE-NOTES.md) · [SHA256SUMS](SHA256SUMS.txt)。三份快速开始保留发行版命令与正文，仅修正仓库阅读所需的相对链接；RELEASE-NOTES及SHA256清单与发行附件逐字节相同。

1. 从本版Release下载应用ZIP、r59 Skill ZIP、SHA256清单和对应语言说明；先逐项校验摘要。
2. 原生Windows准备CPython3.13 x64及FFmpeg／ffprobe；解包并离线安装到新目录。两个ZIP不包含Python、FFmpeg、GPU驱动或完整模型／音乐权重。
3. 用工具包配置器的`--base-only`绑定安装版，再注册唯一`$agent-ffmpeg-local-editor`；17项能力由内部模块按需加载。配音／翻译及其他GPU模型按各自说明另配，不能把基础安装当作模型已安装。
4. 执行`version`、`doctor`和`capabilities`，确认实际安装路径与CLI0.1.66。然后建工程、导入授权素材、展示滤镜／音色候选、记录选择并编辑时间线。
5. 先预检，再预览／渲染／质检；完整播放、听审及语义接受分别进行。导出可编辑工程包，在新目录导入重放后交付。

具体命令与实际ID以上述三语快速开始为准。公开下载附件内的相对链接面向解包后的完整Skill工具包；仓库中的三份网页说明仅调整了这些相对链接，发行ZIP与附件本身保持原字节。

## 本版已验证范围与边界

源码与独立安装各自完整4,124项通过，原断言保留、安装无源码回退。已验证实际CUDA短配乐、母音频／配方与完整音画工程重放、r59同机便携基础安装、第二台CPU63→66→63→66、本机通用正式升级／逐字节回滚／再次升级，以及真实模型取消／超时／输出冲突。这些测试组分别记录，不合并计数，不代表完整剪映功能或自然视听质量。

本版原始发布程序已完成7附件上传及远端摘要核对；19:27匿名官方API和远端tag复核通过。尚未从公开下载地址重新下载这两个ZIP后执行全新安装／注册／成片重放；不是干净主机、跨机GPU、全依赖迁移或完整Agent自主任务验收。完整G01—G38继续开放。

[功能模块与服务说明](../../product/CAPABILITIES.md) · [繁體功能說明](../../product/CAPABILITIES.zh-TW.md) · [English capabilities](../../product/CAPABILITIES.en.md) · [单Skill与17内部模块](../../skills/UNIFIED_SKILL.md) · [完整案例与媒体](../../product/CASES.md) · [详细待办与完成条件](../../product/UNFINISHED_DETAIL_20261106.md)。

## 公开附件

| 文件 | 字节数 | SHA256 |
| --- | --- | --- |
| agent-editor-kit-community-unified-skill-r59.zip | 798393 | `02528ab7cc05d9195e7107fc51e2fe845a0935649dc0b7568b36b805950bda96` |
| agent-editor-kit-v0.1.0-alpha.4-cp313-win_amd64.zip | 305730971 | `36b2970f92d24393e6ae6b77636f43b89bea6c3a201aaa164889148feb2d0786` |
| QUICKSTART.en.md | 8678 | `a24bb94d68079a37efd5c2cb4ee84246e44d297caa41908eaceca5a90ac8b0ca` |
| QUICKSTART.md | 8272 | `cf9bd5c907aabd02c7f999d291acd2eec584a1a89688e73a7d93b1b9888d88ac` |
| QUICKSTART.zh-TW.md | 8269 | `614e8ec9f31f73c331b35724d47abcb5b4a6bbe55c97cf0dbbea2a2f5c5a454b` |
| RELEASE-NOTES.md | 1336 | `741c6668e3d02f323c7d539b80027eca9e0a48ac902327a8da06ba83e293bdc5` |
| SHA256SUMS.txt | 565 | `acde009dc5a0642946f8918688e8dc87bd1186863e6bbc9271a9972a7e1063f7` |

[实际发布终态](../../validation/evidence/delivery66-handoff-20261106-r1/publication-r2/verification.json) · [独立匿名API／摘要及保护复核](../../validation/evidence/status-review-20261106-r7/review-r1/verification.json) · [正式Skill验收](../../product/DELIVERY66_FORMAL_ACCEPTANCE.md) · [三类实际模型故障](../../product/DELIVERY66_ACTUAL_FAULTS.md)。
