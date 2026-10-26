# 统一 Skill：一个入口、17 项能力

<!-- community-current -->

**CLI0.1.31 / alpha.4-local.29 / r32 kit · 1 Skill / 17 modules / 73 files.**

实际源像素/效果alpha和5类遮罩已接入跟踪；59种入出场/双源转场传递锚点及ROI足迹，连续转场保留完整密度，生成黑白幕不伪造来源；独立空间入出场可共享变速。

[Tracking visibility workflow](../product/TRACKING_VISIBILITY.md)

<!-- /community-current -->

## alpha.3 / r1 历史流程（以下原文保留）

[繁體中文](UNIFIED_SKILL.zh-TW.md) · [English](UNIFIED_SKILL.en.md) · [完整模块](../product/SKILLS.md)

外层只需指定 **`$agent-ffmpeg-local-editor`**。它根据实际任务读取内部模块，不再要求分别调用 timeline、quality、local-models 等 16 个专用 Skill。全部模块与上游辅助脚本、模板、来源和许可都包含在该 Skill 目录内。

本次改变 Skill 的组织和注册方式。运行内核仍固定为已公开的 **v0.1.0-alpha.3 / CLI 0.1.2 / 500 套滤镜**；未发布的素材、翻译和配音候选功能不计入该安装版。原 alpha.3 Release 的 17 Skill 下载包、标签和摘要保留不变。

## 当前这台电脑

本仓库已安装运行包。更新仓库后执行以下命令即可迁移注册，无需再次安装内核：

```powershell
Set-Location 'E:/dev/sandbox/AI广告剪辑'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
```

注册器先检查内核回执、启动器摘要和统一 Skill 的完整文件清单，再保留总入口、移除本项目原 16 个专用入口的目录联接。原始专用 Skill 文件仍保留在仓库用于历史复现；不删除源文件、不清理其他项目或 `video-cut-*` 注册。遇到同名无关目录、不同目标的联接或已编辑的旧 Skill 时，在变更注册前退出并保留现状。注册回执另存于 `local/agent-ffmpeg/registrations/`，不把机器路径写回可移植清单。

迁移后重新打开会话，让客户端刷新发现列表。当前已打开会话可能仍显示缓存中的旧入口。

## 另一台电脑 / 新目录安装

需要原生 Windows x64、已有 CPython 3.13 x64、PATH 中的 FFmpeg/ffprobe。下载：

1. [新的统一 Skill kit](https://github.com/copypasteltd/agent-editor-kit/raw/refs/heads/main/docs/skills/agent-editor-kit-unified-skill-r1.zip)。
2. [alpha.3 运行 ZIP](https://github.com/copypasteltd/agent-editor-kit/releases/download/v0.1.0-alpha.3/agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip)。
3. 如需客户滤镜选型，再下载 [gallery ZIP](https://github.com/copypasteltd/agent-editor-kit/releases/download/v0.1.0-alpha.3/agent-editor-kit-v0.1.0-alpha.3-gallery.zip)。

```powershell
$aekPython = 'C:/Python313/python.exe'
$aekHome = 'E:/tools/agent-editor-kit-unified'
Expand-Archive -LiteralPath 'E:/Downloads/agent-editor-kit-unified-skill-r1.zip' -DestinationPath $aekHome
Set-Location $aekHome
& $aekPython -I -B -X utf8 ./install.py --archive 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
$avk = Join-Path $aekHome 'skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $aekPython -I -B -X utf8 ./run-example.py --output 'E:/video-work/unified-first-demo'
```

安装保留已有目标目录；请选一个新的工具目录。若当前 Codex 已有指向另一工具目录的同名 Skill，注册器会保护它并报错。可以继续使用已有仓库的注册入口，或先用 `-SkillsDirectory 'E:/video-work/aek-discovery'` 检查独立发现目录；不要直接覆盖无关目录。

运行包与 Skill kit 的 SHA-256 分别见原 Release 的 SHA256SUMS.txt 与本目录 [包摘要](unified-skill-package.json)。安装器会实际校验内核运行包和 kit 内的逐文件摘要。哈希校验并不等于发布者签名。

## 调用示例

```text
$agent-ffmpeg-local-editor 用 E:/media/product.mp4 制作 15 秒竖屏广告。
先检查能力、素材和音轨，展示暖色与黑白滤镜候选；客户选定后生成预览、成片、质检和可编辑工程包。

$agent-ffmpeg-local-editor 给 clip_1 加可编辑推近与关键帧，预览首中末帧。

$agent-ffmpeg-local-editor 把 E:/media/interview.mp4 按提供的字幕拆成三条短片，保留原声音轨。

$agent-ffmpeg-local-editor 分析本地投放数据，计算 ROAS、CPA 并提出下一轮创意脚本。
```

你可以直接点名“时间线”“配音适配器”“滤镜选型”“质检”等任务，无需指定模块文件名或另一个 Skill。入口按需读取对应参考；合并不意味着每次加载全部说明，也不会启动子 Agent。模块表、来源和依赖见 [Skill 正文](../../skills/agent-ffmpeg-local-editor/SKILL.md) 和 [17 项详细模块](../product/SKILLS.md)。

随包示例产出 6 秒、360×640、30 fps、180 帧的视频及音轨、可编辑工程和工程包。功能链路演示、自动解码检查、自然画质和人工听审分别记录；Skill 合并不会补齐未验收的剪映对标功能。

## 结构与维护

```text
skills/agent-ffmpeg-local-editor/
  SKILL.md                       # 唯一被注册的入口，共同流程和路由
  agents/openai.yaml             # 客户端显示信息
  scripts/run.ps1, run.py        # 已安装内核的固定入口
  scripts/look_gallery.py        # 真实滤镜候选板
  references/runtime.md         # 共享运行约定
  references/looks.md            # 滤镜应用语义
  references/client-look-selection.md
  references/modules/*/module.md # 17 项模块，按需读取
  references/modules/*/references/upstream/ # 对应来源、许可与辅助资源
```

注册清单格式为 `agent-ffmpeg-local-skills-v2`：`skill_count=1`，`module_count=17`。每个模块有稳定 K01–K17 编号和对应旧名称映射。后续扩展优先增加内部参考，不再注册新的 `$agent-ffmpeg-local-*` 专用入口。原始拆分源的归档和重建脚本供维护者使用，正式打包只取清单中的一个入口。

[本轮实际核验与迁移回执](../validation/evidence/unified-skill-20261024-r1/) · [原 alpha.3 Release](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v0.1.0-alpha.3)

[Fixed-canvas affine reuse / 扫描行复用](../product/AFFINE_RENDERING.md) uses the existing render workflow, keeps CPU composition explicit, and provides paired timing and actual previews.

[Animated crop and native-canvas projection / 动态裁切与嵌套投影](../product/PROJECTION_RENDERING.md) retains the existing bilinear/area kernels, explicit raster quota and editable keys; CPU composition and GPU encoding remain separate.

CLI0.1.22: independent/inline Float32 text, joint typewriter/highlight and plain SRT. Read [workflow](../product/FLOAT_TEXT.md); CPU,8bit coverage/Float32 colors,explicit fonts and original clocks. 4K text/GPU text/rich ASS and full target acceptance remain open.

Historical CLI0.1.23:[4K text and reusable native byte coverage](../product/FLOAT_TEXT_COVERAGE.md). CPU tiled linear component composition,exact original clocks,bounded adaptive caches. GPU text,natural quality,HDR,realtime and full original conditions remain open.

CLI0.1.24:[native Float32 GPU workflow](../product/FLOAT_GPU.md). Explicit geometry/normal composition/text colors/word selection;owned worker cleanup;CPU glyph rasterization and remaining operators retained. Full original target conditions remain open.

CLI0.1.25: [global/interval Float32 grading](../product/FLOAT_ADJUSTMENTS.md); one selected root, authored clocks, explicit local LUT dependencies; CPU effects with compatible GPU composition. One Skill /17 modules /72 files.
