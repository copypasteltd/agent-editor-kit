# CLI0.1.32 · native tracking bake · local.30

本地安装并注册唯一 `$agent-ffmpeg-local-editor`。公开alpha.3历史附件保持。

| Item | Verified value |
|---|---|
| Runtime | `v0.1.0-alpha.4-local.30/final-r3/installed` |
| ZIP | `E:\dev\sandbox\AI广告剪辑\local\agent-ffmpeg\v0.1.0-alpha.4-local.30\candidate-r3\bundle.zip` |
| Bytes | `302800994` |
| SHA256 | `68afad180fb09a5d87fcf0dd5c029e9e60c787949382662972796b74c6a798bb` |
| Manifest SHA256 | `sha256:fce0dfe256f83dfb0e36c31cb4ba9b8d08136574bab6fa5100594a625b896f11` |
| CLI/wheel | `0.1.32` |
| Product | `225 Python files/schema equal source` |
| Skill | `1 entry/17 modules/73 files;r33 kit112 files` |

原生 PTS 跟踪现可烘焙为普通 hold 关键帧：保留真实帧时钟、遮罩和转场可见度，对烘焙前后全部 Float32 显示帧逐帧比较，再导出工程。原始绑定另存旁车；普通工程包继续保留动态绑定。

C42 实际注册 Skill：36 帧 Float32 核验、工程包重导入后的36个解码帧与完整144000双声道采样一致；5种格式导出/回读，严格草稿和源文件覆盖拒绝通过。GPU 两轮帧运算及资源关闭有记录。外部播放器、自然质量、连续播放和人工听审未验收；38项原关闭条件继续保留。

[Installation](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Workflow](../product/TRACKING_BAKE.md) · [Evidence](../validation/跟踪原生烘焙导出实测_2026-10-26.md) · [r33 kit](../skills/agent-editor-kit-community-unified-skill-r33.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.32-r33.json).
