# agent editor kit：下载、安装与首次成片

[繁體中文](QUICKSTART.zh-TW.md) · [English](QUICKSTART.en.md) · [发行下载](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v0.1.0-alpha.3) · [完整功能](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/README.md)

本版是 **v0.1.0-alpha.3 预发布版 / CLI 0.1.2 / 500 风格 / 17 个 Skill**，面向 Agent 的原生 Windows 本地剪辑。完整剪映功能及自然视听质量仍是开发目标；当前支持范围见功能手册。

## 1. 准备环境与下载

需要已有 **Windows x64、CPython 3.13 x64、FFmpeg 和 ffprobe**。将 FFmpeg/ffprobe 放入 PATH；以下 Python 路径按本机实际位置修改。安装离线执行，不使用 Docker、WSL、容器、虚拟环境或全局 pip 安装。

从上方 Release 的 Assets 下载到例如 `E:/Downloads/`：

| 文件 | 是否需要 | 用途 |
|---|---|---|
| `agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip` | 必需 | 可安装应用和 8 个固定 wheel；无需再下载分卷 |
| `agent-editor-kit-v0.1.0-alpha.3-agent-kit.zip` | 必需 | 安装入口、17 个 Skill、注册脚本、三语指南、可执行示例与 CC0 输入素材 |
| `SHA256SUMS.txt` | 建议核对 | 对照下载文件的 SHA-256；安装入口另行强制核对运行包 |
| `agent-editor-kit-v0.1.0-alpha.3-gallery.zip` | 选型时需要 | N002 原图、500 套真实滤镜样例、离线选型页、许可与候选对照板资源 |

基础包不包含 Python、FFmpeg、Node/Chromium、模型权重或 GPU 驱动。基础剪辑和下面示例不需要模型或 Node；转写、配音、抠像、修复等按对应适配器另行准备已有本地依赖。

## 2. 解压 Agent kit 并安装运行包

选择新的工具目录。保留运行 ZIP 原样，由安装脚本校验和解包：

```powershell
$avkPython = 'C:/Python313/python.exe'
$avkHome = 'E:/tools/agent-editor-kit-alpha3'
$avkArchive = 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip'
Expand-Archive -LiteralPath 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-agent-kit.zip' -DestinationPath $avkHome
Set-Location $avkHome
& $avkPython -I -B -X utf8 ./install.py --archive $avkArchive
```

成功输出 JSON 的 `ok` 为 `true`。应用位于 `$avkHome/local/agent-ffmpeg/v0.1.0-alpha.3/installed/`，绑定文件位于 `$avkHome/local/agent-ffmpeg/runtime.json`。已有目录不会被覆盖；重复安装请沿用原入口或选择新的工具目录。

## 3. 注册 Skill 并检查真实能力

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
$avk = Join-Path $avkHome 'skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk capabilities
& $avk schema show
```

注册脚本把 17 个 `$agent-ffmpeg-local-*` 目录联接到 Codex 的 Skills 发现目录；正文仍在工具目录。若存在指向其他目录的同名 Skill，会保留并报错，不强行覆盖。已使用仓库本地版的本机用户可以继续沿用原入口，无需重复注册。

注册后，若当前客户端尚未列出新 Skill，可重新打开会话使其重新发现。在 Agent 中调用：

```text
$agent-ffmpeg-local-editor 用 E:/media/product.mp4 制作一条 15 秒竖屏广告。
先读取素材和实际能力，生成可编辑时间线与预览，再渲染、质检和导出工程包。
需要保留原声时显式添加音轨；为滤镜提供实际候选图并记录最终 ID、强度和作用范围。
```

## 4. 一条命令跑通首次成片

不准备额外素材也可以运行。示例使用随包 CC0 虚构产品图片与合成脉冲音，完成导入、时间线、运镜、0.65 强度滤镜、显式音轨、预览、发布权利检查、实际渲染、质检和工程包往返：

```powershell
& $avkPython -I -B -X utf8 ./run-example.py --output 'E:/video-work/aek-first-demo'
```

输出目录必须尚不存在。主要产物：

| 路径（相对示例输出目录） | 内容 |
|---|---|
| `project/project.json` | 可继续编辑的工程 |
| `project/renders/demo.mp4` | 360×640、30 fps、6 秒、180 帧的实际成片及音轨 |
| `demo.aevpkg.zip` | 可导入的工程与引用素材包 |
| `restored/` | 从工程包恢复并验证的工程 |
| `commands.json`、`logs/` | 每次真实 CLI 调用、响应、错误和耗时 |
| `verification.json`、`probe.json` | 实际编码与完整解码核对结果 |

示例是安装与功能链路演示，不是自然广告画质、音乐听感或完整剪映等价验收。

## 5. 为客户展示 500 套滤镜

将可选图册 ZIP 解压到同一个 `$avkHome`：

```powershell
Expand-Archive -LiteralPath 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-gallery.zip' -DestinationPath $avkHome
Start-Process (Join-Path $avkHome 'docs/assets/looks-n002-20261024-r1/index.html')
```

在离线页面搜索、筛选、比较原图和效果，导出候选 JSON。Agent 也可生成一张小型对照板：

```powershell
$aekGallery = Join-Path $avkHome 'skills/agent-ffmpeg-local-editor/scripts/look_gallery.py'
& $avkPython -I -S -B -X utf8 $aekGallery --ids t3-fuji-superia-800 nt-bw-agfa-apx-100 fl-0000634-darkblue --output 'E:/video-work/client-look-options'
```

客户确认后，在真实目标素材上再试选定强度，记录稳定 ID、强度与片段/全局范围后应用。图册样例强度均为 1.0；LUT 的许可与母图的使用权分别记录。浏览完成后关闭不用的页面标签。

## 6. 使用自己的素材与手动 CLI

读取每个命令的 `--help`；从导入响应获取真实资产 ID，不能直接照抄其他工程的片段 ID。视频素材有声音不代表时间线自动包含音轨。用户素材默认需要补充真实来源和许可，才能通过本地 `render --publish` 门禁；该参数不会上传视频。

```powershell
& $avk project init 'E:/video-work/my-ad' --name 'My ad'
& $avk media ingest --project 'E:/video-work/my-ad' --input 'E:/media/product.mp4'
& $avk timeline compose --help
& $avk look list --query '黑白'
& $avk look inspect --id t3-kodak-gold-200
& $avk render --help
& $avk quality check --help
```

后续顺序为：素材导入 → 按真实 ID 编写/应用编辑计划 → 校验工程 → 预览 → 渲染 → 检查实际编码、音画与权利 → 导出工程包。示例脚本包含一份可执行的编辑 JSON 生成逻辑。

[功能、服务与 Skill 全说明](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/README.md) · [已知差距](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/product/GOAL_GAPS_20261024.md) · [分卷备用安装](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/releases/v0.1.0-alpha.3/USAGE.md)
