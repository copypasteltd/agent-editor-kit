# CLI 0.1.27 · native tracking edits · local.25

本地已编译、离线安装并加载唯一 `$agent-ffmpeg-local-editor`。新增保留源分片的
跟踪编辑：分割、裁切、波纹及范围操作保留原生 PTS、完整作者曲线和 ROI/旋转基准。
删除源后标签隐藏；锁定引用和歧义源覆盖整体拒绝。

This is a local build and verification record. Public alpha.3 / CLI 0.1.2 tags,
archives and hashes remain unchanged. This document does not publish a new
GitHub Release or establish full CapCut/Jianying equivalence.

| Item | Verified path or value |
|---|---|
| Runtime | `v0.1.0-alpha.4-local.25/final-r4/installed` / CLI `0.1.27` |
| Local bundle | `E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.25/candidate-r4/bundle.zip` |
| ZIP bytes | 302781524 |
| ZIP SHA-256 | `5b211392c31a5eaa8c99102e1f2f2c1d819bdda1808d68cbcabad7393e75bc32` |
| Manifest SHA-256 | `ab670088d524ff5ee501d5a9f2cb9e9486cd5d35a16b6c2bde9f41ffdacd442d` |
| Product / schema | 220 `.py` files match source; packaged schema matches documented bytes |
| Skill | One entry / 17 internal modules / 73 Skill files |
| Kit | [r28 ZIP](../skills/agent-editor-kit-community-unified-skill-r28.zip) / [digest](../skills/community-unified-skill-package-0.1.27-r28.json) |
| Existing model packs | Four explicitly configured CPU/CUDA voice/translation packs and semantic runtime retained |

## 使用 / Use

按照[离线交付指南](../product/COMMUNITY_LOCAL_DELIVERY.md)校验 ZIP/manifest，解包到
新目录，运行随包安装器；保持原生 Windows/CPython 3.13 和明确登记的已有依赖。
不创建虚拟环境、不自动下载模型。用匹配 r28 kit 配置运行目录并登记。

```powershell
$aek = Join-Path $env:USERPROFILE '.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aek version
& $aek capabilities
& $aek schema show
& $aek timeline compose --project $projectPath --input $editJson --dry-run
& $aek timeline compose --project $projectPath --input $editJson
& $aek validate --project $projectPath
& $aek render --project $projectPath --output $moviePath
& $aek convert export --project $projectPath --target-format package --output $packagePath
```

[完整编辑流程和 JSON](../product/TRACKING_EDITS.md)说明原生 Float32 选择、实际 ID、
源分片、隐藏状态、基准时钟、范围操作和边界。读取实际计划，检查受影响帧和完整音轨后交付。

## 验证 / Validation

安装版按组分别通过：33 跟踪、195 编辑、71 绑定/画布/复用片段、192 默认 CLI/预览/
队列/Schema、46 原生渲染、65 音频/转场、98 Float32，全部零跳过。
这是各组运行结果，不合并历史通过次数，也不代表竞品等价。

统一 Skill 实跑 C37：36 帧→删除中间 6 帧→30 帧，2.5 秒/12 fps/320×180。
全部保留 Float32 像素/原生时钟/跟随几何一致；显式 8bit 无损核验编码的解码像素相同。
完整 120,000 双声道 PCM 采样拼接误差 0。工程包重新导入后全部画面/时钟和完整声音相同；
队列另有实际执行回执。GPU affine/over 与 owned worker/shared-handle 清理留证。

[Evidence and failures](../validation/跟踪剪辑实测_2026-10-26.md) ·
[C37 and media](../product/CASES.md#c37-tracking-edits) ·
[Installed bytes](../validation/evidence/tracking-edits-20261026-r1/installation-final-r4/verification.json).

源 slip/真实外扩、绑定容器变速、磁性传播、原生中间格式烘焙、遮挡/跨镜头身份和自然质量
继续有明确边界。本机 10bit CRF0 编码反例及最初安装兼容读取失败保留。
没有新模型推理、连续播放、人工听审或性能承诺；全部 38 组原始关闭条件保持。

## 最终发行元数据 / Final distribution metadata

功能回归、C37 和独立队列的实际执行目录是 **final-r3**。后续打包检查发现其 CLI 为
0.1.27，wheel 的发行元数据仍为 0.1.26，r28 发布门禁拒绝了这个候选；未发布该错误包。
最终 **final-r4** 修正 wheel 元数据为 0.1.27，并为构建和 Skill 固定步骤增加版本一致性检查。
220 个可执行 Python 文件、全部产品资源字节及七个依赖 wheel 与 final-r3 相同。
最终已注册入口另外执行版本/能力/Schema/校验及实际预览，RGBA64 解码与原预览相同。

Functional tests, C37 and the independent queue actually ran on **final-r3**.
Final **final-r4** corrects distribution metadata, with identical executable and
resource payloads and seven identical dependency wheels. The final registered
entry separately checks version/capabilities/schema/validation and decodes a new
preview. Earlier failed kit metadata and the incomplete kit-r1 attempt remain
excluded; final r28 acceptance is **kit-r2**. This is a metadata repack, not another
full regression or model inference claim.

[Distribution and actual final-entry proof](../validation/evidence/tracking-edits-20261026-r1/distribution-r1/verification.json).
