# 线性 Float32 文字与字幕 / Linear Float32 text

CLI0.1.23 的当前资源与4K实现见 [覆盖率复用和分块合成](FLOAT_TEXT_COVERAGE.md)。下文作者格式继续适用，0.1.22 的20张Float32栅格和4K拒绝规则是旧版实现记录。

CLI **0.1.22 / alpha.4-local.20** 为显式 `float32-native-v1` 工程接入独立文字轨道、片段内字幕和纯文本 SRT。原生 FFmpeg 负责塑形及覆盖率，填充、描边、阴影、底框的颜色转换与叠加在明确的线性 Float32 域完成。媒体原像素不进入文字栅格进程。

English: explicitly select the Float32 pipeline, register a local font, author a subtitle-track text generator or inline `subtitle`, preview the actual author frames, render and export the editable package. Native glyph coverage has eight bits; authored colors and compositing use Float32. Plain SRT only; rich ASS/SSA/VTT remain on the default path. This implementation runs on CPU.

繁體：先明確選擇 Float32 管線及登記本機字型，再建立字幕軌文字產生器或片段內字幕。預覽作者影格、輸出並交付可編輯套件。字形覆蓋率為 8 位元，顏色與合成使用 Float32；目前只接受純文字 SRT，CPU 執行。

## 使用流程

通过唯一的 `$agent-ffmpeg-local-editor` 入口运行，遵守返回的工程、资产、轨道和片段 ID。安装与公开旧发行的区别见 [本机交付](COMMUNITY_LOCAL_DELIVERY.md)。

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk capabilities
& $avk schema show
& $avk media ingest --help
& $avk timeline compose --help
```

1. 创建或打开本地工程，登记实际媒体与字体。字体使用 `font_asset_id` 或明确的本地 `fontfile`。字体必须可读且具有真实布局度量；不采用系统字体或平均字宽回退。
2. 设置 `settings.pixel_pipeline.engine="float32-native-v1"`、线性 `working_signal`、输出信号和实际视频/图片的源信号。保持 `settings.color`、输出编码配置及源矩阵/量程声明一致。[转场流程](FLOAT_TRANSITIONS.md)与现有浮点工程使用同一配置。字体、SRT 不加入像素源表。
3. 独立文字使用 `kind="subtitle"` 轨道及 `generator={"type":"text"}`；视频或子序列片段直接附带 `subtitle`。显式音轨继续负责声音。
4. `validate` 后预览关键时点，检查实际文字、字形、位置、颜色和时间。再执行标准 `render` 或队列；取消后沿原操作 `--resume`。文字跟随原作者展示时钟，父级变速/倒放会传递到文字求值。
5. 对编码结果执行 `quality check`，保留预览、操作记录和权利台账，最后 `convert export --target-format package`。包内保留可编辑文字及原字体/SRT 依赖。

以下是 90000 ticks/s 工程中的独立文字片段。将它作为 `timeline compose` 的 `add_clip` 操作中 `clip`，并填入实际字幕轨道 ID；`font_local` 替换为字体登记返回的 ID。

```json
{
  "id": "title_demo",
  "generator": {"type": "text"},
  "timeline_start_tick": 0,
  "duration_tick": 270000,
  "source_in_tick": 0,
  "source_out_tick": 270000,
  "subtitle": {
    "text": "AGENT EDITOR KIT",
    "style": {
      "font_asset_id": "font_local", "fontsize": 32,
      "fontcolor": "#e8f3ffdd", "active_color": "#ffd080dd",
      "box": true, "boxcolor": "#122438a0", "boxborderw": 6,
      "borderw": 1, "bordercolor": "#08182899",
      "shadowx": 2, "shadowy": 2, "shadowcolor": "#04081080",
      "x": "20", "y": "40", "expansion": "none"
    },
    "animation": {"type": "typewriter", "duration": 2.4},
    "word_timing": [
      {"text": "AGENT", "start": 0, "end": 1},
      {"text": "EDITOR", "start": 1, "end": 2},
      {"text": "KIT", "start": 2, "end": 3}
    ]
  }
}
```

```powershell
& $avk validate --project $project
& $avk preview frame --project $project --frame 12 --height 360
& $avk preview range --project $project --start-frame 0 --end-frame 36 --height 360
& $avk render --project $project --output $output --hardware-encode off
& $avk quality check --project $project --input $output
& $avk convert export --project $project --target-format package --output $package
```

帧索引及预览范围须符合实际工程时长。示例关闭硬件编码是为了复现实测，不影响既有其他路径的 GPU 选择。

## 文字、时钟及组合规则

| 项目 | 实际行为 |
|---|---|
| 填充、底框、阴影、描边 | 原生字形覆盖率分别取样；颜色从作者 sRGB 转到指定线性工作信号，按底框→阴影→描边→填充 source-over；最后只施加一次文字动画透明度。 |
| 原生覆盖率 | 当前 FFmpeg 的 RGB8→浮点转换不会严格给出 `code/255`。启动时用全部 256 个码值校验离散重建，再用于字形覆盖率；不对媒体色彩作这种归一化。 |
| 打字机 | 每个实际作者时间生成完整前缀，复用整段锚点与逐行基线；字素组合不按代码点拆开，不先生成低帧率文字影片缓存。 |
| 逐词高亮 | 同一完整段落绘制正常色与活动色，二值区域选择一次；不把活动词重复叠加。可与打字机共用一个时间。 |
| 自有倒放/定格 | 文字使用片段展示时钟，定格媒体时文字继续推进；父级倒放则使用子序列左极限，保持半开边界。 |
| 裁切展示窗口 | 仍用完整作者起点、时长与窗口偏移，文字动画不会从零重新开始。 |
| 原生 SRT | `asset_time_base` 可选 `sequence`（默认）或 `clip`，`asset_time_offset_tick` 为整数 tick；逐条半开范围求值，允许最多16条同时活动。 |
| 片段内字幕 | 媒体效果后绘制，随后执行片段投影；字幕自身旋转只转文字，不旋转媒体。 |
| 独立文字 | 先按所在序列画布绘制，再执行本片段效果、裁切、变换、蒙版、混合及转场。 |
| 动画 | fade/fade_in/fade_out、四向 slide、typewriter/typing、pop、bounce、rotate；rotate 为真实浮点仿射及渐显。 |
| 字体/实现依赖 | 字体、SRT、FFmpeg、文字实现与 Pillow 布局实现绑定 SHA；标准命令在依赖读锁范围内完成，不静默替换字体或重用已变化内容。 |

## 资源与未完成边界

宿主共享 LRU 默认64MiB，返回独立表面，避免调用者修改缓存。原生文字图按20张 Float32 RGBA 全画幅估算做单次准入，最大工作区768MiB；这是准入估算，**不是进程峰值 RSS 限制**。默认预算下1080p在准入范围内，4K文字会在启动原生进程前拒绝；本轮不作1080p性能或实时承诺。

单段文字64KiB、SRT4MiB/8192条、原生图4MiB；既有打字机最多512字素/128行，逐词最多128范围。无状态 x/y、真实本地字体及 `expansion=none` 是确定性回放要求。未知字段/样式、无效逐词时间、富文本标签、ASS/SSA/VTT文件动画、随机/外部元数据表达式均明确拒绝。

复杂双向文字的逐词/打字机布局、词内部塑形簇、高级排版、4K原生文字、GPU文字合成、自然视听质量、HDR/ICC及完整剪映等价仍须继续实现或验收。已有默认渲染器的富字幕功能不因选择浮点路径而自动获得浮点实现。

## 实测与交付

[当轮安装与核验报告](../validation/Float32文字字幕实测_2026-10-26.md)记录独立像素 oracle、实际统一 Skill 案例、安装包、队列和取消恢复。具体可视案例与原素材见 [C30](CASES.md#c30-float-text)。所有历史 G01–G38 关闭条件保持不变。
