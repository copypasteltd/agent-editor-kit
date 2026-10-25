# CLI0.1.20 本地交付 / Local delivery

2026-10-26，agent editor kit，`v0.1.0-alpha.4-local.18`最终构建`final-r2`。Native Windows x64/CPython3.13，209产品Python文件、69 Skill文件、1入口/17模块。公开alpha.3/CLI0.1.2与旧包保持；此为已安装本地交付，不覆盖公开发行附件。

新增原生OpenCL动态裁切、仿射与子画布双线性/面积投影，以及显式off/prefer/require策略、逐设备精度/纹理探测、工作栅格预算、kernel摘要、完整日志和队列/恢复集成。CPU默认；其他效果仍CPU，独立线性光浮点管线尚未GPU接入。现有500风格、359资源、字幕配音、GPU配音/翻译与17模块保持。

| Item | Under `E:/dev/sandbox/AI广告剪辑/` | SHA-256 |
|---|---|---|
| Native application ZIP,302706914 bytes | `local/agent-ffmpeg/v0.1.0-alpha.4-local.18/candidate-r2/bundle.zip` | `088b588151d425324ee98019b38772e5a464a00a509d1d15f8eba01e7cd41841` |
| Bundle manifest | ZIP `manifest.json` | `8aeb0ab5cd67b54e1d28367bd41672902df8d897595e4a7d64070277afea68a4` |
| Installed runtime | `local/agent-ffmpeg/v0.1.0-alpha.4-local.18/final-r2/installed/` | [209-file proof](../validation/evidence/opencl-projection-20261026-r1/installation-final-r2/verification.json) |
| r21独立kit / 517779 bytes / 96 files；SHA-256 `e06f0b06d85b6f5d40318eb5276723f4510cfd507524d947dcb027d2f26f7a1f` | [r21 ZIP](../skills/agent-editor-kit-community-unified-skill-r21.zip) | [metadata](../skills/community-unified-skill-package-0.1.20-r21.json) |

[Offline install/register](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Complete workflow/queue/editable case](../product/OPENCL_PROJECTION.md) · [17 Skill modules](../product/SKILLS.md) · [75 actual declarations](../product/opencl-projection-capabilities-cli-0.1.20.json) · [Native evidence](../validation/OpenCL原生投影实测_2026-10-26.md)

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk validate --project $project
& $avk render --project $project --output $output --projection-acceleration prefer --projection-device 0.0 --projection-memory-mib 1024 --sequence-sampling area --sequence-memory-mib 1024 --hardware-encode off
```

先将project/output指向真实本地路径，或按完整使用页导入案例到新目录。使用匹配r21/运行ZIP；启动器验证摘要，不回落源码。现有驱动/FFmpeg、Python和可选模型另供；无Docker/WSL/虚拟环境、隐式下载或后台模型服务。仅RTX3060设备实测。4K是单帧像素对照，通用实时/长片、自然质量与全剪映等价仍开放。所有38原关闭条件保持。
