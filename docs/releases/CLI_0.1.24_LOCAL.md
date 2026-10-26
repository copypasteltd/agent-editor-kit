# CLI0.1.24 本地交付 / Local delivery

agent editor kit / `v0.1.0-alpha.4-local.22` / final-r4；217产品Python文件、71 Skill文件、单入口17模块。[原生浮点GPU使用](../product/FLOAT_GPU.md)。

| 内容 | E:/dev/sandbox/AI广告剪辑/下路径 | SHA-256 |
|---|---|---|
| Application ZIP / 302768670bytes | `local/agent-ffmpeg/v0.1.0-alpha.4-local.22/candidate-r4/bundle.zip` | `2e129e94a6aa8cc05f021a15ed0399c8500f676a6d47fe6c17884c847bcf8a2c` |
| Manifest | ZIP内`manifest.json` | `783ba350c6fbf2f7d2a4dc2cefe69457d99988fb494c5091af0cc1f36857ad69` |
| Installed | `local/agent-ffmpeg/v0.1.0-alpha.4-local.22/final-r4/installed/` | [217-file proof](../validation/evidence/float-gpu-20261026-r1/installation-final-r4/verification.json) |
| r25 unified Skill / 102files/541715bytes/SHA-256 `59a44d9523e4bc3f673f7a7505ef4575840550ef02bcb53cd7302e837929f5e6` | [r25 ZIP](../skills/agent-editor-kit-community-unified-skill-r25.zip) | [metadata](../skills/community-unified-skill-package-0.1.24-r25.json) |

[离线安装/注册](../product/COMMUNITY_LOCAL_DELIVERY.md) · [75实际能力](../product/float-gpu-capabilities-cli-0.1.24.json) · [核验与性能](../validation/浮点GPU执行层实测_2026-10-26.md) · [17模块](../product/SKILLS.md)。四个原CPU/GPU模型包和配置保留，没有新模型推理。原生Windows，无Docker/WSL/虚拟环境或全局安装。

GPU明确选择off/prefer/require；语音/翻译独立auto/cpu/cuda。实际GPU支持范围为仿射、普通合成、字色和逐词选择，字形栅格/转场/其他算子CPU。单对4K实测CPU 296.712→GPU 139.938秒，不作实时或通用速度保证。当前包为本地交付；公开alpha.3/CLI0.1.2标签、附件及摘要保持。完整目标继续开放。
