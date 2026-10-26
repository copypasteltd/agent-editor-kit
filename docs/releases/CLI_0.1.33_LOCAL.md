# CLI0.1.33 · local GPU generation · local.31

唯一 `$agent-ffmpeg-local-editor` / one Skill with17 internal modules. Public alpha.3 downloads remain unchanged.

| Item | Verified value |
|---|---|
| Runtime | `v0.1.0-alpha.4-local.31/final-r1/installed` |
| ZIP | `E:\dev\sandbox\AI广告剪辑\local\agent-ffmpeg\v0.1.0-alpha.4-local.31\candidate-r1\bundle.zip` |
| Bytes | `302811930` |
| SHA256 | `2133ea5756c43858832bb24049028e0e21b3ad27acdcbe249698e293ac202d83` |
| Manifest SHA256 | `sha256:855426d7aa2f4ed1d09ffd8163f4a994a27780c65f29d79e09a799f2663f663a` |
| CLI/wheel | `0.1.33` |
| Product | `227 Python files/schema equal source` |
| Skill | `1 entry/17 modules/74 files;r34 kit114 files` |

新增本地 GPU 文生、图生、尾帧与首尾帧视频生成：显式条件、原文提示词、seed/采样和窗口参数，产出无声视频资产，并可直接作为普通可编辑片段入轨。复用现有 VACE 原生内核、GPU 内存准入、权利依赖与事务恢复。

四种模式均有真实 CUDA 输出、全部17帧解码与工程包往返记录；每个端点另做解码哈希核验。保留端点不证明模型运动/身份质量；模型与生成内容权利、自然质量、完整播放及完整剪映等价仍未验收。模型成片/GIF/工程包保留本机；下图仅是自行绘制的 CC0 条件图，不是生成输出。

[Workflow](../product/VIDEO_GENERATION.md) · [Installation](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Actual evidence](../validation/本地GPU视频生成实测_2026-10-26.md) · [r34 kit](../skills/agent-editor-kit-community-unified-skill-r34.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.33-r34.json).

Model-pack activation now uses a configurable per-pack deadline: default600 seconds, range1–3600 via `--verify-timeout-seconds`. Full verification remains mandatory. The independent kit check forces a one-second timeout and confirms that both prior runtime configuration files remain byte-identical. Initial180-second failure and the unaccepted candidate archive are retained in development evidence.
