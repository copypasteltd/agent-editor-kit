# agent editor kit v0.1.0-alpha.3 — Agent CLI preview / Agent 剪辑预发布

Native Windows x64 · CPython 3.13 · CLI 0.1.2 · 500 looks · 17 local Skills.

Download the **runtime ZIP** and **Agent kit ZIP**. Extract the Agent kit, run its offline installer against the runtime ZIP, register the Skills, then run the included six-second example. The **gallery ZIP** is optional for browsing all 500 actual supplied-image look previews and exporting client shortlists.

下载 **运行 ZIP** 与 **Agent kit ZIP**；解压 Agent kit，使用其中的离线安装入口安装运行 ZIP，注册 Skill 后即可执行随包示例。选型需要时再下载 **gallery ZIP**，其中包含母图的全部 500 套真实滤镜样例与离线页面。

- [简体中文安装与使用](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/releases/v0.1.0-alpha.3/QUICKSTART.md)
- [繁體中文安裝與使用](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/releases/v0.1.0-alpha.3/QUICKSTART.zh-TW.md)
- [English installation and workflow](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/releases/v0.1.0-alpha.3/QUICKSTART.en.md)
- [完整功能 / Complete functionality](https://github.com/copypasteltd/agent-editor-kit/tree/v0.1.0-alpha.3)

The editing core provides structured projects, multitrack editing, keyframes, captions, audio, masks, effects, rendering, quality checks and project packages under explicit capability contracts. The look catalog retains the original 100 IDs and adds 400 transforms, with per-resource MIT, CC BY-SA 4.0 or CC0 provenance. Community look names do not imply official camera/manufacturer filters.

核心以结构化 CLI 组织项目、多轨剪辑、关键帧、字幕、音频、蒙版、效果、渲染、质检和工程包。500 预设保留原 100 项 ID，并提供逐项许可与来源。随包示例使用 CC0 虚构产品图片和合成声音，输出可编辑工程、实际视频和验证记录。

Python, FFmpeg/ffprobe, models, GPU drivers and Node/Chromium are not bundled. Basic editing and the example require no model or browser. AI adapters need their declared existing local dependencies. This prerelease does not establish complete CapCut parity, general HDR/ICC, broad natural-video quality, listening acceptance or long-form/4K performance.

这是预发布版，完整剪映对标及自然视听、长片/4K 等门禁仍未完成；已知对齐、音频和模型画质缺口继续公开保留。安装和示例不使用 Docker、WSL、容器、虚拟环境或运行时下载。

The runtime archive is unchanged: SHA-256 `1a967e4def2afc14e9f110c6cad90e172ff457a77ef405cb83932f1f1187b968`. Compare every attachment with `SHA256SUMS.txt`. The original multipart files remain available as a fallback; individual parts are not ZIP archives.

Fresh-directory native validation: offline install in an E-drive path containing spaces and Chinese characters, 17 Skill junctions, four queries through the registered PowerShell launcher, 20 successful demo CLI calls, two expected refusals preserving existing output, 180 encoded frames, full A/V decode, quality checks and project-package recovery. This was a fresh directory on the existing Windows host, not a second clean machine. No model inference, browser, Docker, WSL or virtual environment was used.

本次新增实测：E 盘中文/空格路径离线安装、17 个 Skill 注册、注册入口的 4 次查询、示例的 20 次成功 CLI、2 次保留既有产物的预期拒绝，以及成片 180 帧、完整音画解码、质检和工程包恢复。实测发生在现有 Windows 主机的新目录；未将其写成全新主机验收。

[Actual demo MP4](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/assets/release-v0.1.0-alpha.3-r1/demo.mp4) · [Demo GIF](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/assets/release-v0.1.0-alpha.3-r1/demo.gif) · [Native verification](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/validation/evidence/release-v0.1.0-alpha.3-r1/verification.json)
