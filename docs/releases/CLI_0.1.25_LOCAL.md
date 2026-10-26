# CLI0.1.25 本地交付 / Local delivery

agent editor kit / `v0.1.0-alpha.4-local.23` / final-r1。218产品Python文件，单一 `$agent-ffmpeg-local-editor`、17内部模块、72 Skill文件。

本次补上显式Float32渲染的全局与区间调整层：完整含字幕合成后依序执行，保留原始区间/关键帧时钟，选中根只应用一次；本地LUT依赖持锁并随可编辑包迁移。调整层仍为CPU计算，可与已有GPU投影和字色合成共同执行。

| Artifact | E:/dev/sandbox/AI广告剪辑/下路径 | SHA-256 |
|---|---|---|
| Application ZIP / 302772595 bytes | `local/agent-ffmpeg/v0.1.0-alpha.4-local.23/candidate-r1/bundle.zip` | `cc2ee3ff79eeeec17563c75ac99544bea0f04f78e81b5f7fcd0c367c3a9a66ac` |
| Manifest | ZIP内 `manifest.json` | `sha256:4cea4b5f4e9424237474dbc3b2a96748ae5d12925d21b5a3a377b7ce0e4694ae` |
| Installed | `local/agent-ffmpeg/v0.1.0-alpha.4-local.23/final-r1/installed/` | [218-file proof](../validation/evidence/float-adjustments-20261026-r1/installation-final-r1/verification.json) |
| r26 unified Skill | [ZIP](../skills/agent-editor-kit-community-unified-skill-r26.zip) | [metadata](../skills/community-unified-skill-package-0.1.25-r26.json) |

[完整离线安装/登记步骤](../product/COMMUNITY_LOCAL_DELIVERY.md) · [调整层使用与参数](../product/FLOAT_ADJUSTMENTS.md) · [C35完整源/结果/GIF/工程包](../product/CASES.md#c35-float-adjustments) · [实测与失败记录](../validation/Float32调整层实测_2026-10-26.md) · [实际75能力响应](../product/float-adjustments-capabilities-cli-0.1.25.json)。

统一Skill调用本次已校验的安装包，不回落源码。四个既有CPU/CUDA配音/翻译包与语义配置保留；本轮未新增模型推理。原生Windows，不运行Docker、WSL、虚拟环境、全局安装或常驻服务。

输入/工作/输出信号必须明确；预览、渲染、队列、恢复共用宿主，音轨独立并保留原采样。项目包重导入应再校验、预览和检查LUT/许可。

仅本地交付，公开alpha.3/CLI0.1.2及其原标签/附件/摘要保持。GPU调整层、完整HDR/ICC、实时性能、自然素材质量、人工听审和完整剪映等价未据此宣称完成。
