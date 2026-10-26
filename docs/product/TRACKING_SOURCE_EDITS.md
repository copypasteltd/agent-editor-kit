# 跟踪源滑移与真实外扩 / Physical tracked-source editing

CLI0.1.29 now supports synchronized magnetic tracking cuts/reorder; [current workflow and C39](TRACKING_MAGNETIC.md). Earlier versioned records below retain their original scope.

CLI 0.1.28 支持带原生跟踪绑定的 `slip`、`extend_source`，以及需要真实源句柄的
`roll/slide`。它们编辑已登记素材的真实范围，保留原始观测和关联音轨，使用有限源边界检查。
本流程用于显式 `float32-native-v1`；其他渲染路径沿用各自的绑定门禁。

## 使用 / Use

先确认素材的 `probe.duration_seconds`、源入出点、轨道锁与 `link_id`。单位均为工程
ticks；例如 90,000 ticks/second 时，22,500 是 0.25 秒。JSON 使用实际返回的片段 ID。

```json
{"action":"slip","clip_id":"moving_source","delta_source_tick":22500}
```

```json
{"action":"extend_source","clip_id":"moving_source","head_tick":22500,"tail_tick":22500}
```

```powershell
$aek = Join-Path $env:USERPROFILE '.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aek version
$aekPlan = (& $aek timeline edit --project $projectPath --sequence-id $sequenceId --input $requestJson --dry-run) | ConvertFrom-Json
$aekPlan.data.plan
& $aek timeline edit --project $projectPath --sequence-id $sequenceId --input $requestJson --expected-project-sha256 $aekPlan.data.plan.base_project_sha256
& $aek validate --project $projectPath
& $aek preview frame --project $projectPath --sequence-id $sequenceId --frame $changedFrame --height 360
& $aek render --project $projectPath --sequence-id $sequenceId --output $moviePath
& $aek convert export --project $projectPath --target-format package --output $packagePath
```

`linked` 默认依照工程设置扩展关联选择，可明确 `"options":{"linked":false}`。源编辑
不隐式执行其他同步轨的波纹/宿主联动。计划包含真实源范围、选择成员、绑定前后值与
`source_edits`；应用时校验计划的工程摘要，避免对陈旧工程执行。

## 时钟和画面 / Clock and picture

滑移改变物理 `source_in_tick/source_out_tick`，保持片段落点和作者处理时长。跟随位置
根据新取到的真实原生 PTS 及已有观测重新求值。ROI 缩放/相对旋转在固定输出参考点上
重新采样新媒体；这次媒体替换会改变基准，没有伪装成保留旧画面的操作。未覆盖的观测
时间范围隐藏标签，真实源不足或无有限探测时长则拒绝。

头部真实外扩为每个被改动的 `tracking_binding.source_fragments` 条目累计
`author_offset_tick`。绑定公共 `reference_output_tick` 保留，实际参考钟为二者之和。
因此只外扩某个源分片、继续分割或重复外扩时，其他分片不被错误地一起偏移。
跟随视频自身外扩时，`base.opacity_keyframes` 跟随作者起点重锚；观测坐标与时间保持。

Source slip changes the selected original PTS and recalibrates ROI/rotation at
the pinned output reference. Head extension instead retains the old reference
by adding a per-fragment author offset. Extending a bound video target shifts
its base opacity keys. Original observations remain asset-clock data.

整数网格上的分段恒速曲线采用有理数反求，避免 `0.3` 的二进制近似误选前一帧。
非恒速曲线继续采用既有有界浮点映射；没有全局 epsilon、显示帧率重对齐或源帧伪造。
源曲线、淡入淡出和真实外扩仍服从原生源编辑的作者处理语义。

## 约束 / Limits

锁定依赖更新、真实源越界、非整数头部源网格、歧义源重叠和循环/预算超限会整体拒绝。
静态图片没有有限的视频源句柄；用普通时长编辑处理静态内容。
带绑定容器变速、磁性裁切传播、MLT/OTIO/draft 原生绑定烘焙、源蒙版/转场可见性、遮挡
和跨镜头身份依然按各自的开放条件推进。可编辑工程包保留分片偏移及全部原始观测。

[此前分片剪辑流程](TRACKING_EDITS.md) · [原生跟踪](FLOAT_TRACKING.md) ·
[本地安装与固定摘要](../releases/CLI_0.1.28_LOCAL.md)。

## C38 实际案例 / Actual case


已登记CC0移动几何、透明标记与双声道合成音，有限内段先滑移0.25秒，再关联头尾各外扩0.25秒。
36帧/3秒，其中30帧有真实源覆盖；全部Float32像素与独立无绑定作者工程相同，完整144000双声道采样误差0。
工程包重导入与队列分别核验。实际GPU投影及清理留证；GIF静音，无自然身份/连续播放/人工听审验收。

![Actual silent GIF](../assets/tracking-source-edits-20261026-r3/edited.gif)

[Before MP4](../assets/tracking-source-edits-20261026-r3/before.mp4) · [Edited MP4](../assets/tracking-source-edits-20261026-r3/edited.mp4) · [Editable package](../assets/tracking-source-edits-20261026-r3/editable-tracking-source-edits.aevpkg.zip) · [Source/rights](../assets/tracking-source-edits-20261026-r3/SOURCE.txt) · [Hashes](../assets/tracking-source-edits-20261026-r3/media-manifest.json) · [Workflow](TRACKING_SOURCE_EDITS.md) · [Evidence](../validation/跟踪源编辑实测_2026-10-26.md).
