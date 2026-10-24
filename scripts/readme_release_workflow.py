"""Practical public-release workflow shared by all three complete READMEs."""


def quickstart(pick, suffix):
    release = 'https://github.com/copypasteltd/agent-editor-kit/releases'
    download = release + '/download/v0.1.0-alpha.3/'
    prefix = 'agent-editor-kit-v0.1.0-alpha.3-'
    text = pick('## 下载并跑通第一条视频', '## Download and render your first video') + '\n\n'
    text += pick(
        '**环境：Windows x64、已有 CPython 3.13 x64、FFmpeg/ffprobe 在 PATH。** 基础流程不需要模型、Node 或浏览器；安装不使用 Docker、WSL、虚拟环境或全局 pip。Python 路径按实际安装位置修改。',
        '**Requirements: Windows x64, existing CPython 3.13 x64 and FFmpeg/ffprobe on PATH.** The basic workflow needs no model, Node or browser. Installation uses no Docker, WSL, virtual environment or global pip. Adjust the Python path for your installation.') + '\n\n'
    text += '| ' + pick('下载附件 | 用途', 'Download | Purpose') + ' |\n|---|---|\n'
    rows = [
        (prefix + 'cp313-win_amd64.zip', pick('必需：应用和 8 个固定 wheel，约 196 MB。', 'Required: app and eight pinned wheels, about 196 MB.')),
        (prefix + 'agent-kit.zip', pick('必需：离线安装入口、17 个 Skill、注册脚本、指南和可运行示例。', 'Required: offline installer, 17 Skills, registration, guides and runnable example.')),
        (prefix + 'gallery.zip', pick('可选：原图、500 套真实样例、离线选型页和客户对照板资源。', 'Optional: original, 500 real look samples, offline selection page and client-board assets.')),
        ('SHA256SUMS.txt', pick('核对下载文件；安装入口还会强制验证运行 ZIP 哈希。', 'Verify downloads; the installer also enforces the runtime ZIP hash.')),
    ]
    text += '\n'.join('| [' + name + '](' + download + name + ') | ' + purpose + ' |' for name, purpose in rows) + '\n\n'
    text += pick('**1. 安装。** 将两个必需 ZIP 下载到 `E:/Downloads/`，选择新的工具目录；保留运行 ZIP 原样，由安装入口校验并解包。',
                 '**1. Install.** Download both required ZIPs to `E:/Downloads/` and choose a new tool directory. Leave the runtime ZIP intact for the installer to validate and extract.') + '\n\n'
    text += '''```powershell
$avkPython = 'C:/Python313/python.exe'
$avkHome = 'E:/tools/agent-editor-kit-alpha3'
$avkArchive = 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip'
Expand-Archive -LiteralPath 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-agent-kit.zip' -DestinationPath $avkHome
Set-Location $avkHome
& $avkPython -I -B -X utf8 ./install.py --archive $avkArchive
```

'''
    text += pick('**2. 加载 Skill 并检查环境。** 安装响应 `ok: true` 后注册；脚本保留同名冲突目录。已有本仓库本机安装的用户可继续使用原入口。客户端尚未发现 Skill 时，重新打开会话。',
                 '**2. Register Skills and inspect support.** After installation returns `ok: true`, register the Skills. Conflicting directories are preserved. Existing repository installations can keep their current launcher. Open a new conversation if the client has not discovered the Skills yet.') + '\n\n'
    text += '''```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
$avk = Join-Path $avkHome 'skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk capabilities
& $avk schema show
```

'''
    text += pick('**3. 跑通示例。** 无需额外素材；随包 CC0 图片与合成音频经过实际剪辑、运镜、滤镜、预览、渲染、质检及工程包导入导出。输出目录必须尚不存在。',
                 '**3. Run the example.** No extra media is needed. Included CC0 artwork and synthetic audio pass through actual editing, motion, a look, preview, render, quality checks and project-package export/import. The output directory must not already exist.') + '\n\n'
    text += '''```powershell
& $avkPython -I -B -X utf8 ./run-example.py --output 'E:/video-work/aek-first-demo'
```

'''
    text += pick('主要产物：`project/project.json` 可编辑工程、`project/renders/demo.mp4`（6 秒、360×640、30 fps、180 帧及音轨）、`demo.aevpkg.zip`、`restored/`、逐次响应和 `verification.json`。此示例核验安装与功能链路；自然画质和听审仍需独立验收。',
                 'Outputs include editable `project/project.json`, `project/renders/demo.mp4` (6 seconds, 360×640, 30 fps, 180 frames and audio), `demo.aevpkg.zip`, `restored/`, per-command responses and `verification.json`. This demonstrates installation and the editing chain; natural-media quality and listening remain separate acceptance work.') + '\n\n'
    text += pick('**4. 用 Agent 编辑自己的素材。** 明确素材路径、目标、时长、画幅及音轨；Agent 先检查真实能力和来源，再形成时间线、预览和交付。',
                 '**4. Edit your own media with an Agent.** Supply media paths, goals, duration, canvas and audio intent. The Agent checks actual support and provenance before creating a timeline, previews and delivery.') + '\n\n'
    text += '```text\n' + pick(
        '$agent-ffmpeg-local-editor 用 E:/media/product.mp4 制作 15 秒竖屏广告。\n先检查能力和素材，明确保留原声音轨，展示滤镜候选；生成预览、成片、质检报告和可编辑工程包。',
        '$agent-ffmpeg-local-editor Make a 15-second vertical ad from E:/media/product.mp4.\nInspect support and media first, explicitly retain source audio, show look candidates, then deliver previews, video, quality reports and an editable project package.') + '\n```\n\n'
    text += pick('**5. 按需安装图册。** 将可选 `gallery.zip` 解压到同一个 `$avkHome`，打开 `docs/assets/looks-n002-20261024-r1/index.html`；也可用下方 Skill helper 输出候选对照板。使用完关闭不用的浏览器标签。',
                 '**5. Add the optional gallery.** Extract `gallery.zip` into the same `$avkHome` and open `docs/assets/looks-n002-20261024-r1/index.html`, or use the Skill helper below to export a candidate board. Close unused browser tabs afterwards.') + '\n\n'
    text += '[Release](' + release + '/tag/v0.1.0-alpha.3) · [' + pick('完整安装与使用流程', 'Full installation and workflow') + '](docs/releases/v0.1.0-alpha.3/QUICKSTART' + suffix + '.md) · [' + pick('范围与限制', 'Scope and limits') + '](docs/releases/v0.1.0-alpha.3/RELEASE.md)\n\n'
    return text
