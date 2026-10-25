# CLI 0.1.18 本地交付 / Local delivery

历史中间构建；最终本地版本与完整复核见 [CLI0.1.19](CLI_0.1.19_LOCAL.md)。本页保留实际中间包摘要，未冒充最终计时验收。

2026-10-26，`v0.1.0-alpha.4-local.16`，agent editor kit。原生 Windows x64 / CPython 3.13，FFmpeg/ffprobe 使用已有本地安装。1 个 `$agent-ffmpeg-local-editor` 入口、17 个内部模块、68 个 Skill 文件、208 个产品 Python 文件。

Native Windows delivery, with one registered Skill and 17 internal modules. This local build extends scanline reuse to animated crop and native child-canvas crop/fit/TRS for both bilinear and area sampling. Existing editing, motion packs, 500 looks, 359 resources, subtitle dubbing, GPU voice/translation, semantic search and recovery remain available within their documented limits.

| Item | Location under `E:/dev/sandbox/AI广告剪辑/` | SHA-256 |
|---|---|---|
| Application ZIP, 302695912 bytes | `local/agent-ffmpeg/v0.1.0-alpha.4-local.16/candidate-r1/bundle.zip` | `bad78990d43645b1ee30e2f09096f717f0c164fe677a331e354dc497773c687b` |
| Application manifest | ZIP 内 / inside ZIP: `manifest.json` | `8cb582154a3e104e3df83dd45c8aad6aee28b2b1c6313838942c3be54e4952d9` |
| Installed runtime | `local/agent-ffmpeg/v0.1.0-alpha.4-local.16/final-r1/installed/` | [208 file verification](../validation/evidence/projection-scanline-20261026-r1/installation-r1/verification.json) |
| r18 Skill kit, 509563 bytes / 94 files | [ZIP](../skills/agent-editor-kit-community-unified-skill-r18.zip) | `e037dde8fd4d502679e485e4ee3323e1a62cf53b8b49709c4a8ff4e5fa0e2934` |

模型权重与 NVIDIA 库仍分层；模型已有本机登记，`auto` 为配音/翻译优先使用 GPU，返回实际设备及显式回退原因。渲染中的 crop/投影合成为 CPU，硬件编码另外选择。基础包不捆绑 Python、FFmpeg、GPU 外部运行库或全部可选模型，不使用 Docker/WSL/虚拟环境或隐式下载。

Model weights and NVIDIA libraries remain separate. Configured voice/translation prefer GPU with actual-device/fallback reporting. Crop/projection composition is CPU; hardware encoding is separate. Python, FFmpeg and all optional models are not bundled. No virtualization or implicit model download is used.

[离线安装、四个模型包及注册 / Install and register](../product/COMMUNITY_LOCAL_DELIVERY.md) · [完整使用与可编辑案例 / Workflow and editable case](../product/PROJECTION_RENDERING.md) · [Skill详情](../product/SKILLS.md) · [75项实际能力字段](../product/projection-scanline-capabilities-cli-0.1.18.json) · [本轮原生测试和实测](../validation/裁切与序列投影实测_2026-10-26.md)

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk capabilities
& $avk validate --project $project
& $avk render --project $project --output $output --sequence-sampling area --sequence-memory-mib 1024 --hardware-encode auto
```

先将 `$project` 和 `$output` 指向实际本地工程/输出；完整示例含可编辑案例的导入命令，见使用页。不要将 r18 kit 与旧运行包混用；启动器验证固定摘要，拒绝静默回落源码。

Set the real local project/output paths first. The workflow page includes an importable case. Pair r18 with its matching runtime: the launcher verifies pinned digests and has no source fallback.

这是已安装本地版本的交付快照，不覆盖既有公开标签/附件。完整剪映等价、全场景自然质量、4K/长片及 GPU 合成尚未验收；所有 G01–G38 原关闭条件保留。

This is a local delivery snapshot. Existing public tags/assets remain immutable. Full goal equivalence, natural-quality acceptance, general 4K/long-form and GPU composition remain open.
