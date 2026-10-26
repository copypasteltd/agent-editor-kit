# 原生 PTS 跟踪绑定 / Native PTS tracking bindings

CLI0.1.29 now supports synchronized magnetic tracking cuts/reorder; [current workflow and C39](TRACKING_MAGNETIC.md). Earlier versioned records below retain their original scope.

CLI0.1.28 extends tracked physical slip/real source handles; see [current source-edit workflow](TRACKING_SOURCE_EDITS.md). Earlier versioned checks below retain their original scope.

agent editor kit CLI 0.1.26 / `v0.1.0-alpha.4-local.24`，单入口
`$agent-ffmpeg-local-editor`。保存的跟踪观测已接入显式 Float32 渲染、帧与范围
预览、队列及恢复。源轨道与标记轨道保持可编辑，渲染不重复运行分析模型。

## Agent 使用流程

先用已安装 Skill 查询 `capabilities`、`schema show` 和
`media track-bind --help`。摄取本地视频及透明贴图，分别放到直接视觉片段；
保留实际返回的资产、序列、轨道和片段 ID。设置
`settings.pixel_pipeline.engine = "float32-native-v1"`，按
[浮点文字流程](FLOAT_TEXT.md)完整声明源、线性工作域与交付信号。所有视频和
图片都需来源信号；无容器起点的静态PNG须显式设置该源 `demux_origin: "0"`。视频声音须放到明确音轨。

```powershell
$avk = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk media track-bind --project $project --asset-id $videoId `
  --sequence-id $sequenceId --source-track-id $videoTrackId --source-clip-id $videoClipId `
  --target-track-id $labelTrackId --target-clip-id $labelClipId `
  --roi '0.125,0.35,0.063,0.11' --step-frames 1 --max-samples 600 `
  --scale-mode roi --rotation-mode source --apply
& $avk validate --project $project
& $avk preview frame --project $project --frame 0
& $avk preview range --project $project --start-frame 0 --end-frame 36
& $avk render --project $project --output $movie
& $avk quality check --project $project --input $movie
& $avk convert export --project $project --target-format package --output $package
```

变量须使用实际工程路径和 ID，帧范围须在工程内。ROI 是原视频上的归一化
`left,top,width,height`。省略 `--apply` 可先检查真实分析和置信度。显式提供源
片段引用，才能跟随该片段的时钟和画面变换。

原生计划中的 `keyframes: []`、`sampled_frames: 0` 表示保存动态绑定，保留作者
关键帧；它不把轨迹烘焙成工程显示帧率。目标原始 scale/rotation/opacity 与
透明度关键帧保存在 binding.base，重复绑定沿用该基准。

## 实际时钟与坐标

跟踪绑定对同一实际选中视频帧求值：原始 int64 PTS × 有理数 time base −
记录的 demux origin。正放、倒放、标量/曲线变速、定格、裁切窗口和嵌套父级
都复用视频渲染的时钟；不会先换成名义 FPS 再吸附。VFR、非零 demux 起点及
部分原生索引的播放有独立时钟检查。

锚点使用实际源帧尺寸以及渲染器同一个 crop/fit/TRS 逆矩阵。观测是归一化
像素边缘坐标，采样器使用整数像素中心，两者显式换算。动态裁切的取整、
fit/fill/stretch、anchor、位置、缩放及旋转与画面一致。源 transform/blend
透明度乘以目标基准透明度。ROI 缩放和相对旋转以目标原作者起点的源几何为
基准；随机顺序预览不改变基准。绑定链按依赖求值并拒绝循环。

`overlay` 轨道作为显式原生管线中的视觉轨道，保留顺序、静音、嵌套时钟和
子序列明确音轨。随包 schema 和语义校验都要求 `float32-native-v1`，防止默认
渲染遗漏叠加轨。默认管线的多轨画面继续使用 `video`。

## 精度、资源与边界

坐标求值为 CPU；符合条件的仿射、普通合成和文字颜色可使用已探测的原生
GPU。动态裁切及现有 CPU 效果按其原合同执行。视频合成保持 Float32；跟踪
分析的缩放 RGB 图和置信度单独记录。

内置模板匹配按分析采样时钟产生观测，并不等于逐原生帧检测。观测之间插值，
端部可保持；遮挡、尺度改变和切镜可能漂移。源范围、裁切及静音可控制可见性；
源 mask、转场和目标遮挡仍需单独复核。这里未宣称自然身份跟踪、遮挡恢复或
所有运动质量已经验收。

单绑定 1–4000 条观测，总计最多 128 个绑定/64000 条观测，依赖深度最多16。
源仍要求方形像素且无显示旋转，ROI 结果使用已有0.01–20缩放限制。源 SHA
改变或循环拒绝。原生绑定导出到 MLT/OTIO/draft 时明确拒绝，待按原生时钟
烘焙接通；可编辑 package 保存原始观测及引用。移除原生 binding 恢复作者变换，
不自动冻结当前姿态。

## C36 实际联测及客户预览

实际安装版的统一 Skill 分析原始移动纹理目标，产生36条观测；动画 crop、
scale 和 rotation 改变源画面，红色标记按保存观测跟随，父级叠加序列倒放，
声音跟随完整源音轨。标题使用 Noto Sans SC/OFL，图形/标记/验证声音为原创
CC0。GIF 无声；MP4 含合成验证音，不是自然配音或音乐质量证明。

![实际输出 / Silent actual output](../assets/float-tracking-20261026-r5/native-tracking.gif)

[原始视频](../assets/float-tracking-20261026-r5/original.native.mkv) ·
[原始声音](../assets/float-tracking-20261026-r5/original.audio.wav) ·
[实际 MP4](../assets/float-tracking-20261026-r5/native-tracking.mp4) ·
[可编辑包](../assets/float-tracking-20261026-r5/editable-native-tracking.aevpkg.zip) ·
[媒体摘要](../assets/float-tracking-20261026-r5/media-manifest.json) ·
[执行证据](../validation/evidence/float-tracking-20261026-r1/case-r5/verification.json)。

复现脚本：[真实 Skill 案例](../../scripts/run_float_tracking_case_20261026.py)、
[安装与字节核验](../../scripts/build_float_tracking_20261026.py)、
[专项和回归](../../scripts/test_float_tracking_20261026.py)。每次使用新 `--run`
目录，保留失败。实际输入输出、完整像素/PCM比较、工程包重导入及已观察边界
以证据文件为准；不以命令退出成功替代质量验收。

## English workflow

Select the installed native Float32 pipeline with complete source/working/output
signals. Ingest the source video and transparent marker, place direct visual
clips in the same sequence, and supply explicit source/target track and clip
IDs to `media track-bind`. Inspect ROI confidence, then apply, validate, preview,
render, check and export an editable package. Dynamic plans have no baked
display keys. Source clocks use the same selected original PTS as the picture;
crop/fit/TRS share the actual renderer geometry. Overlay tracks require explicit
native selection and preserve child audio. Coordinate evaluation is CPU, with
eligible GPU projection/composition/text retained. Template analysis sampling,
natural identity/occlusion quality and external interchange baking have the
separate limits stated above. The controlled C36 input/output and evidence are
linked alongside its silent GIF.
