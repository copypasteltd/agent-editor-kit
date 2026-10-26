# CLI0.1.26 本地交付 / Local delivery

agent editor kit / `v0.1.0-alpha.4-local.24` / final-r2。
219产品Python文件，单一 `$agent-ffmpeg-local-editor`、17内部模块、73 Skill文件。

原生 PTS 动态跟踪绑定接通实际视频时钟与 crop/fit/TRS 几何，支持作者窗口、
倒放/变速/定格/嵌套、源透明度、ROI缩放和相对旋转。`overlay` 轨道进入随包
schema/校验器和显式浮点渲染，嵌套叠加序列保留完整音轨。默认管线会明确拒绝
`overlay`，避免漏层。保存观测不在渲染时重新运行模型或烘焙显示关键帧。

| Artifact | E:/dev/sandbox/AI广告剪辑/下路径 | SHA-256 |
|---|---|---|
| Application ZIP / 302778138 bytes | `local/agent-ffmpeg/v0.1.0-alpha.4-local.24/candidate-r2/bundle.zip` | `92ddba2b7c3fbd6c0df210f86b4a6f4702c4a16ca80c3ced45ab0452fbb9df4b` |
| Manifest | ZIP内 `manifest.json` | `sha256:9fc746f1af66d40f96446ff327147995300f6996ce708db695361e26bfc0c239` |
| Installed | `local/agent-ffmpeg/v0.1.0-alpha.4-local.24/final-r2/installed/` | [安装与219文件证据](../validation/evidence/float-tracking-20261026-r1/installation-final-r2/verification.json) |
| r27 unified Skill | [ZIP](../skills/agent-editor-kit-community-unified-skill-r27.zip) | [metadata](../skills/community-unified-skill-package-0.1.26-r27.json) |

[离线安装/登记流程](../product/COMMUNITY_LOCAL_DELIVERY.md) ·
[跟踪使用与参数](../product/FLOAT_TRACKING.md) ·
[C36源/结果/GIF/工程包](../product/CASES.md#c36-float-tracking) ·
[实测及失败记录](../validation/原生PTS跟踪实测_2026-10-26.md) ·
[实际75项能力响应](../product/float-tracking-capabilities-cli-0.1.26.json)。

统一 Skill 固定调用已校验安装包，不回落源码。原有四个 CPU/CUDA 配音/翻译
包和语义配置保留。本轮跟踪分析为实际本地模板匹配；没有新增神经模型推理。
坐标CPU，符合条件的浮点投影/叠加/文字GPU，裁切和其他CPU效果保留各自实现。

Native Windows only. The installed bundle is pinned and used by one registered
Skill with17 internal modules. No source fallback, virtualization, global install
or resident model service. Native PTS and actual crop/TRS determine saved binding
playback; overlay child sound remains intact. Analysis sampling/confidence is
separate from the Float32 picture pipeline. See the linked C36 reproduction and
individual frozen test groups; no full-product equivalence is inferred.

这是本地交付；公开 alpha.3/CLI0.1.2 的原标签、附件和摘要保持。自然身份与
遮挡质量、源mask/转场可见性、原生绑定的MLT/OTIO烘焙、完整HDR/ICC和全部
目标仍按原关闭条件继续开发、验收。
