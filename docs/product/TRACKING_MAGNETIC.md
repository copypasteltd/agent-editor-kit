# 跟踪素材的磁性重排 / Magnetic native tracking

CLI0.1.29 在显式 `float32-native-v1` 工程中支持跟踪源和跟随标签跨主轨剪口同步拆分、重排。
它保留原始观察和完整作者窗口，在移动后重建分片引用；不重新跟踪、不烘焙显示帧率关键帧。

## 使用 / Use

先设置正确的 `sequence.editing.main_track_id`（video主轨），确认同步轨、轨道锁、关联组和真实转场端点。
`options.sync` 控制同步跟随，`sync_span_policy: split` 明确允许跨剪口拆分。
启用 `sequence.editing.magnetic` 时默认启用同步及拆分；命令可明确提供选项。

```json
{"action":"reorder","clip_ids":["shot_c"],"before_clip_id":"shot_a","options":{"sync":true},"sync_span_policy":"split"}
```

`before_clip_id: null` 表示移到末尾。使用实际工程返回的片段ID，先查看计划再应用固定工程摘要：

```powershell
$aek = Join-Path $env:USERPROFILE '.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aek version
$aekPlan = (& $aek timeline edit --project $projectPath --sequence-id $sequenceId --input $requestJson --dry-run) | ConvertFrom-Json
$aekPlan.data.plan.sync_splits
$aekPlan.data.plan.moves
$aekPlan.data.plan.tracking_binding_changes
& $aek timeline edit --project $projectPath --sequence-id $sequenceId --input $requestJson --expected-project-sha256 $aekPlan.data.plan.base_project_sha256
& $aek validate --project $projectPath
& $aek preview frame --project $projectPath --sequence-id $sequenceId --frame $cutFrame --height 360
& $aek render --project $projectPath --sequence-id $sequenceId --output $moviePath
& $aek convert export --project $projectPath --target-format package --output $packagePath
```

## 保留的语义 / Retained semantics

分片保留 `source_in_tick/source_out_tick`、作者处理、关键帧和 `presentation_window`。
同步移动改变可见片段的落点；窗口偏移继续指向完整原作者输出。关联视频、音频与标签按主轨区域
得到对应的 `link_id`，便于继续编辑。原始 `tracking_binding.observations` 始终使用资产时钟。

绑定重建使用拆分前的完整工程和每个新片段的原始身份。计划会列出引用的前后值、保留源分片和
`reference_output_tick`；已有每分片 `author_offset_tick` 一并保留。ROI缩放、相对旋转、动态裁切、
定格、倒放、曲线速度和链式跟随在各自的完整作者时钟上求值。输出从实际原生PTS选帧，未按标称fps重排源时间戳。

The planner resolves every split descendant against the pre-cut graph, including
already split sources and chains. Source observation times and per-fragment
reference offsets remain intact. Whole-clip reorders and synchronized cut
propagation share this repair; the plan exposes every required binding change.

## 约束 / Limits

锁定依赖所需的引用改写整体拒绝；锁定关联成员、歧义源重叠、循环、128个源分片或总片段预算超限
继续拒绝。`sync_lock:false` 的轨道保留原作者落点，但解锁依赖的源路由可按实际编辑更新；检查计划中的绑定变化。
原本位于主轨间隙的内容、绝对标记和根级处理继续使用既有语义，不承诺任意重排都保持最终画面完全相同。

非原生渲染路径的跟踪跨剪口仍保留门禁；真实源转场端点和旧式跨片段转场沿用明确保护规则。
带绑定的完整输出容器变速需要共享依赖时钟，仍单独推进。MLT/OTIO/draft绑定烘焙、遮挡、跨镜头身份和自然跟踪质量
不由本次重排实现证明。先核验预览、完整音轨和工程包，再交付实际成片。

[源滑移与外扩](TRACKING_SOURCE_EDITS.md) · [此前分片编辑](TRACKING_EDITS.md) ·
[原生跟踪](FLOAT_TRACKING.md) · [本地安装](../releases/CLI_0.1.29_LOCAL.md)

<a id="c39-tracking-magnetic"></a>

## C39 · 跟踪磁性重排 · CLI0.1.29

CC0移动几何、动态裁切/运镜、跟随标记和双声道合成音；实际统一Skill把第3秒移到第1秒前，跨剪口拆分视频、标签和关联音轨。全部36帧Float32像素/原生PTS/动态几何按原帧顺序保持；完整144000双声道采样误差0。工程包和队列分别核验，实际GPU投影与清理留证。GIF静音，无自然质量/连续播放/人工听审验收。

![Actual silent GIF](../assets/tracking-magnetic-20261026-r1/edited.gif)

[Before MP4](../assets/tracking-magnetic-20261026-r1/before.mp4) · [Edited MP4](../assets/tracking-magnetic-20261026-r1/edited.mp4) · [Editable package](../assets/tracking-magnetic-20261026-r1/editable-tracking-magnetic.aevpkg.zip) · [Source/rights](../assets/tracking-magnetic-20261026-r1/SOURCE.txt) · [Hashes](../assets/tracking-magnetic-20261026-r1/media-manifest.json) · [Workflow](TRACKING_MAGNETIC.md) · [Evidence](../validation/跟踪磁性重排实测_2026-10-26.md).
