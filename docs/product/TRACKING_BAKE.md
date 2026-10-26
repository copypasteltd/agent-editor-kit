# Native tracking bake · CLI 0.1.32

动态绑定保存原始观测，适合继续剪辑。新导出路径把当前工程的跟随结果变成普通 hold 关键帧，便于交付已冻结的工程；源工程继续保存动态绑定。

## 使用流程 / 使用流程 / Workflow

使用已注册的唯一 `$agent-ffmpeg-local-editor`。先读取当前安装的 `capabilities`、`schema show` 与命令帮助，再使用工程实际返回的 ID。下面 `$avk` 是本地已注册 Skill 中的 `scripts/run.ps1` 绝对路径。

```powershell
& $avk convert export --help
& $avk validate --project $avkProject
& $avk convert export --project $avkProject --target-format package `
  --bake-tracking --output $bakedPackagePath
& $avk convert import --input $bakedPackagePath --output $newProjectDirectory
& $avk validate --project $newProjectDirectory
& $avk render --project $newProjectDirectory --output $bakedMoviePath
& $avk quality check --project $newProjectDirectory --input $bakedMoviePath
```

`agent-json` 也支持 `--bake-tracking`，但 JSON 引用本地素材。跨目录或跨机器交付优先使用完整 `package`，保留字体、LUT、权利账本与媒体。普通 `package` 导出仍保存活动绑定；只有显式加入此参数才转成普通关键帧。返回的 `source_sidecar` 保存完整原始绑定 JSON，`source_root` 说明原工程位置；该旁车依赖原始字体和其他工程资源，完整源工程包也应保留。

OTIO、MLT 和明文草稿导出自动执行跟踪烘焙，不需要加入该参数。`--strict` 草稿仍拒绝 Baked、Approximate、Unsupported 或 Failed，不会因为烘焙成功而把外部损失当作已解决。

## 实际执行逻辑 / 實際執行邏輯 / Execution

1. 在读取像素前计算全部序列的显示帧数，检查总帧预算和原生时钟。
2. 打开真实原始媒体，使用同一个 Float32 原生渲染器读取 PTS、VFR、裁切、TRS、变速、冻结、反向、窗口、遮罩和转场来源足迹。记录嵌套实例和转场对端实际触发的绑定求值。
3. 将结果放到目标片段的作者动画时钟上，用普通整数 tick 的 hold 关键帧准确回读每次需求；不四舍五入位置、缩放、旋转或透明度。
4. 用去掉活动绑定后的完整工程重新渲染每条序列全部显示帧，对比 Float32 RGBA 字节摘要。任何一帧不同都拒绝导出。
5. 导出原媒体引用和可编辑工程，写出转换报告、烘焙证明及原绑定旁车。音频、遮罩、转场和速度规格继续保留原字段。

证据中的 `source_project_sha256` / `baked_project_sha256` 是导出器改写媒体路径和追加导出 provenance 之前的内存工程摘要。`tracking_bake` 位于输出文件旁的 `.conversion-report.json`；可移植包内部的 `conversion-report.json` 也保留相同的烘焙证明和 Baked 损失声明。

本轮同时修复 `.mlt` 扩展名识别和 MLT profile 显示帧率保存，支持 `30000/1001` 等整数比。OTIO 本地 metadata 现在保存/恢复整数 tick 时基、显示帧率和序列时长；第三方 OTIO 不含这些本地字段时使用原适配器的标准字段与缺省行为。

草稿的重叠片段保留原目标区间，映射为显式允许的叠放/混音轨，并记录 `timeline-overlap: Approximate`。这不会重建私有转场或推断剪口；严格模式拒绝这项近似。

## 预算与边界 / 預算與邊界 / Limits

| Constraint | Behavior |
|---|---|
| 总显示帧 | 全部序列合计最多 20,000；超限在打开媒体前拒绝 |
| 目标求值 | 最多 256,000 次，包含嵌套与转场依赖读取 |
| 像素缓存 | 每帧处理后只保存摘要；不缓存整段电影像素 |
| 整数时钟 | 同作者时刻要求冲突值、或小于一个 tick 的变化无法精确放置时明确失败 |
| 未取样目标 | 静音/不可达目标列入 `unsampled_paths`，不伪造播放关键帧 |
| GPU | 按工程已明确选择的原生 GPU 投影/合成路径执行；来源足迹与坐标计算仍为 CPU |
| 模型 | 不运行跟踪、生成、配音或翻译模型 |
| 认证范围 | 当前冻结图和显示帧率；更改时钟、FPS、几何或可见度后，从动态原工程重新烘焙 |
| 外部编辑器 | OTIO/MLT/草稿运行器未验收；原生逐帧相等不代表第三方颜色、效果或嵌套图等价 |

外部格式已有的效果、嵌套、轨道、字幕和源句柄损失继续写入原转换报告。本功能补上原生跟踪烘焙，不消除这些格式边界。手工连续播放、听审、自然身份跟踪与遮挡质量另行验收。

The CLI freezes native tracking into ordinary hold keys and verifies every Float32 display frame before export. Keep the dynamic source and its editable package. The certificate applies to the frozen graph and display FPS; re-bake after edits. Native pixel equality does not certify OTIO, MLT or draft players. Total limits are 20,000 sequence frames and 256,000 target evaluations. No model inference or virtualization is used.

主要错误码：`TRACK_BIND_BAKE_BUDGET` 表示配额不足；`TRACK_BIND_BAKE_CLOCK_CONFLICT` / `TRACK_BIND_BAKE_SUBTICK` 表示普通整数关键帧不能准确表达当前时钟；`TRACK_BIND_BAKE_VERIFY` 表示重新渲染不一致；`TRACK_BIND_BAKE_INPUT_CHANGED` 表示作者工程变化。SDK 不提供根目录时仍返回 `TRACK_BIND_NATIVE_BAKE_REQUIRED`。发生这些错误时保留动态源工程，修正输入或时基后重新导出。

CLI 會將原生跟蹤凍結為普通 hold 關鍵幀，並在匯出前核對全部 Float32 顯示幀。請保留動態來源與完整工程包；變更時鐘、FPS、幾何或可見度後重新烘焙。原生像素一致不代表外部編輯器等價。總配額為 20,000 個序列幀和 256,000 次目標求值，不會執行模型推理或虛擬化。

[Dynamic tracking](FLOAT_TRACKING.md) · [Visibility](TRACKING_VISIBILITY.md) · [Shared retime](TRACKING_RETIME.md) · [Installation](COMMUNITY_LOCAL_DELIVERY.md)

<a id="c42-tracking-bake"></a>

## C42 · 原生跟踪烘焙交付 · CLI0.1.32

C42 实际注册 Skill：36 帧 Float32 核验、工程包重导入后的36个解码帧与完整144000双声道采样一致；5种格式导出/回读，严格草稿和源文件覆盖拒绝通过。GPU 两轮帧运算及资源关闭有记录。外部播放器、自然质量、连续播放和人工听审未验收；38项原关闭条件继续保留。

左：动态原生绑定；右：普通hold关键帧；实际导出的两份画面，GIF无声。24帧GIF实际3010ms，逐帧延时写入manifest；MP4仍为原始3秒。

![Actual comparison](../assets/tracking-bake-20261026-r5/comparison.gif)

[Native MP4](../assets/tracking-bake-20261026-r5/original.mp4) · [Baked MP4](../assets/tracking-bake-20261026-r5/baked.mp4) · [Baked editable package](../assets/tracking-bake-20261026-r5/editable-baked-tracking.aevpkg.zip) · [Original dynamic package](../assets/tracking-visibility-20261026-r2/editable-tracking-visibility.aevpkg.zip) · [Source/rights](../assets/tracking-bake-20261026-r5/SOURCE.txt) · [Hashes](../assets/tracking-bake-20261026-r5/media-manifest.json) · [Workflow](TRACKING_BAKE.md).
