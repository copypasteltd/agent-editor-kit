# 跟踪后的可编辑剪辑 / Editable native tracking

CLI **0.1.27 / alpha.4-local.25 / r28 kit**, one registered
`$agent-ffmpeg-local-editor`, 17 internal modules. This extends the installed
[native PTS binding](FLOAT_TRACKING.md) with detached edit-lineage planning.
It reuses saved observations; editing never starts a tracker/model.

## 使用流程 / Workflow

先导入本地素材、编排源视频与标签、以 `media track-bind --apply` 保存实际轨迹。
显式选择 `settings.pixel_pipeline.engine=float32-native-v1`，保留已登记资产、
来源摘要、信号声明和权利记录。通过统一 Skill 调用匹配的安装版。

```powershell
$aekEntry = Join-Path $env:USERPROFILE '.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aekEntry version
& $aekEntry timeline compose --project $projectPath --input $editJson --dry-run
& $aekEntry timeline compose --project $projectPath --input $editJson
& $aekEntry validate --project $projectPath
& $aekEntry preview frame --project $projectPath --sequence-id $sequenceId --frame 12
& $aekEntry render --project $projectPath --sequence-id $sequenceId --output $moviePath
& $aekEntry quality check --project $projectPath --input $moviePath
& $aekEntry convert export --project $projectPath --target-format package --output $packagePath
```

`$projectPath` 等变量须取实际工程/返回值。示例编辑 JSON 如下，tick 来自工程
timebase；片段 ID 必须替换为当前工程的实际 ID。

```json
{
  "sequence_id": "child",
  "operations": [
    {"op":"split_clip","clip_id":"moving_source","at_tick":67500,
     "left_id":"source_left","right_id":"source_right"},
    {"op":"split_clip","clip_id":"follow_marker","at_tick":135000,
     "left_id":"follower_left","right_id":"follower_right"},
    {"op":"ripple_delete","at_tick":90000,"duration_tick":45000}
  ]
}
```

分割会替换原片段 ID，后续操作使用返回的新 ID。整体操作先在独立候选工程中规划；
CLI 验证通过后保存，并保留变更记录及快照。`--dry-run` 保持作者工程原字节。
需要定点插入、覆盖、留空删除、抽出删除、滚动或滑动剪口时，改用
`timeline edit --input ...` 的 `insert/overwrite/lift/extract/roll/slide`。
保留源句柄内的 roll/slide 不重新生成观察；不够的真实源外扩仍明确拒绝。

Ingest and bind first, inspect the dry-run plan, apply the same request, validate,
preview the affected boundary, render, check the encoded output and export the
editable package. Use IDs returned by the last edit. Output windows retain the
complete authored source/animation graph; they do not rescale or rewrite keys.

## 数据与行为 / Data contract

| Field / behavior | Meaning |
|---|---|
| `tracking_binding.source_fragments` | Native-only list of `{track_id,clip_id}` references to retained direct source pieces, up to 128 per binding. Primary `source_track_id/source_clip_id` matches the first live entry. |
| Missing `source_fragments` | Original single-source binding; backward-compatible within its selected renderer. |
| Explicit `source_fragments: []` | Source was removed. Preserve the binding/observations as hidden; do not silently restore an unbound marker. Rebind explicitly to replacement media. |
| `reference_output_tick` | Pins the complete original source-output clock for ROI scaling and relative rotation. Split/move/delete retain the baseline instead of recomputing it from a new cut endpoint. |
| Source gaps / boundaries | No source coverage hides the follower. Exact half-open interval selection follows native forward/reverse semantics. |
| Geometry / alpha | Original PTS selection, actual crop/fit/TRS and base opacity automation remain shared with the picture. |
| Locks / failure | A required rewrite on a locked follower rejects the whole candidate. Invalid IDs, ambiguous overlapping fragments, source-identity changes and cycles reject. |
| Budgets | 128 bindings, 64,000 observations, 4,000 observations/binding, 128 fragments/binding, 4,096 total render references, 16 dependency levels; existing frame/workspace quotas remain. |
| Package | Stores original observations, asset identity, reference clock and live/empty routes. Import requires matching CLI/schema support. |

同一绑定的源分片窗口不能重叠，即使某轨静音也不猜测哪个源有效。跟随层裁切不改变源轨迹；
只移动源轨时，跟随层依据新覆盖范围显示、隐藏或跟随。删除源不自动删除跟随层。
原生规划器修复同序列引用，不改写无关序列。旧默认渲染路径继续保留旧绑定裁切门禁。

## 实测 C37 / Actual case

[原输入源和音频](../assets/float-tracking-20261026-r5/SOURCE.txt)来自 C36 的自制 CC0
几何、透明标记与双声道合成音；字体许可随工程保留。以可编辑子序列作为根，实际统一 Skill
先渲染 3 秒/36 帧，再分别分割源、标签与音轨，删除 `[1.0,1.5)` 秒，得到 2.5 秒/30 帧、
320×180/12 fps。保留原帧 `0..11,18..35`。

![Actual silent GIF](../assets/tracking-edits-20261026-r3/edited.gif)

[Before MP4](../assets/tracking-edits-20261026-r3/before.mp4) ·
[Edited MP4](../assets/tracking-edits-20261026-r3/edited.mp4) ·
[Editable package](../assets/tracking-edits-20261026-r3/editable-tracking-edits.aevpkg.zip) ·
[Media hashes](../assets/tracking-edits-20261026-r3/media-manifest.json) ·
[Actual calls and results](../validation/evidence/tracking-edits-20261026-r1/case-r3/verification.json) ·
[Float32/PTS oracle](../validation/evidence/tracking-edits-20261026-r1/case-r3/native-float-frame-oracles.json) ·
[Queue](../validation/evidence/tracking-edits-20261026-r1/queue-r3/verification.json).

全部 30 个保留帧的 Float32 像素、原生 PTS、源帧索引、作者 tick 和绑定几何与未剪辑原片
逐项相同。明确使用 **H.264 CRF0 / yuv444p 8bit** 核验编码边界；实际解码 RGBA64 像素
逐帧相同。完整 120,000 双声道 PCM 采样与独立拼接参照一致，最大误差 0。
工程包重新导入后，所有解码画面/时钟及完整 PCM 相同。
实际 GPU affine/over 操作和工作进程/共享句柄清理均有回执。

The verifier compares every retained Float32 pixel before delivery, native clocks,
geometry and all 120,000 stereo samples. It separately checks the decoded 8-bit
diagnostic encoding and the imported editable package. The GIF is silent (20
frames); MP4 audio contains synthetic tones. These are controlled editing
checks, with no natural footage/identity, continuous playback or human listening
acceptance. No new model inference or speed claim.

## 已保留边界与失败 / Preserved limits and failures

源 slip、真实源外扩、带绑定片段的容器变速及磁性裁切传播仍有明确门禁。
源蒙版/转场/遮挡可见性、跨镜头身份和自然多目标质量继续按原目标验收。
MLT/OTIO/draft 尚未实现原生 PTS 烘焙，请交付可编辑工程包。

首轮安装回归的两个旧最小绑定用例触发缺少轨道字段异常，兼容读取已修复并重建。
首轮视频用例误把本机 `CRF0/yuv444p10le` 当作逐像素无损：H.264 SPS 的
`qpprime_y_zero_transform_bypass_flag=0`，剪口改变预测历史后解码像素不同。
首个不一致帧的实际源帧/几何/Float32像素和完整PCM一致。该编码反例保留；最终改用显式 8bit 无损核验
并增加全部 Float32 像素对照，没有降低像素相等门槛，也不宣称 10bit 普遍无损。

[Failure record](../validation/evidence/tracking-edits-20261026-r1/development-attempts-r1/verification.json) ·
[Installed release](../releases/CLI_0.1.27_LOCAL.md) ·
[Full original target](GOAL_GAPS_20261025.md).

链式绑定补查：中间跟随层的当前姿态与其固定ROI基准分开求值；一个延后开始的下级标签在源分割后原先有8帧像素差异，最终候选修复并通过逐帧相等检查。

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
