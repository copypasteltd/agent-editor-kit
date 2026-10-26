# 跟踪的实际可见度与空间转场 · CLI0.1.31

`float32-native-v1` 下的原生 `tracking_binding` 自动读取实际源图层 alpha，并跟随空间转场移动。使用现有 `media track-bind` 建立观察，不需要增加新开关。它保留原始 PTS、观察、裁切和作者时钟，服务于 Agent 的标签、标注和局部跟随。

当前交付为 `alpha.4-local.29` / CLI0.1.31 / r32 kit；本地只注册 `$agent-ffmpeg-local-editor`，17 个内部模块。公开 alpha.3 的历史附件保持。

## Agent 操作流程

先通过统一 Skill 的已安装入口读取 `version`、`capabilities`、`media track-bind --help`。导入视频与透明标签图片，明确原生 Float32 信号、画布、序列和实际片段 ID。下列变量使用实际返回值。

```powershell
& $avk media track-bind --project $avkProject --asset-id $videoId `
  --sequence-id $sequenceId --source-track-id $sourceTrackId --source-clip-id $sourceClipId `
  --target-track-id $labelTrackId --target-clip-id $labelClipId `
  --roi '0.125,0.35,0.063,0.11' --step-frames 1 --max-samples 600 `
  --scale-mode roi --rotation-mode source --apply
& $avk validate --project $avkProject
& $avk render --project $avkProject --sequence-id $sequenceId --output $outputPath --dry-run
& $avk preview frame --project $avkProject --sequence-id $sequenceId --frame 0
& $avk render --project $avkProject --sequence-id $sequenceId --output $outputPath
& $avk quality check --project $avkProject --input $outputPath
& $avk convert export --project $avkProject --target-format package --output $packagePath
```

检查遮罩边缘、入出场起止点、两源转场前中后以及随机访问预览。报告中的跟踪行包含 `active`、`reason`、`values` 与 `visibility`。`visibility.steps` 记录模式、方向、作者进度、真实源句柄、预算和来源足迹；`point_footprints` 记录质量、覆盖率及质心。给客户展示实际 MP4/GIF、输入和可编辑工程包，并说明静态检查与连续播放、听审的差别。

## 实际语义

无转场时，在实际投影后的图层上双线性采样 alpha，再乘单独保留的变换/混合标量透明度。原始像素透明度、效果链、矩形/圆形/椭圆/多边形/路径遮罩及羽化都在这张真实图层中。裁切时先投影再执行画布遮罩；无裁切时先执行源遮罩再投影，与渲染器一致。

转场期间，把锚点初始化为 alpha 加权的双线性像素足迹。附加 Float64 密度通道与真实预乘 RGBA 一起通过现有 59 种转场内核。颜色相关判断仍读取真实 RGBA，黑白幕等生成像素的来源密度为零。足迹质量限制到 0..1 后决定标签透明度，质心决定位置。自己的边缘转场后若还有两源转场，保留完整密度场继续传递，不在质心上重新撒点。

ROI 缩放和来源旋转模式额外传递宽度端点，按可见端点重算宽度与方向。锚点丢失返回 `source-anchor-footprint-invisible`；请求的 ROI 端点丢失或退化返回 `source-ROI-footprint-unobservable` 并隐藏标签。基准保留原作者源几何，不把转场动画烘焙进观察或显示帧率关键帧。

这里的可见度是源自身对转场输出的贡献，发生在更高轨道遮挡之前。模糊、像素化、压缩、缩放等采样可能复制或丢失足迹；质心不是自然物体身份判定。自然遮挡、跨镜身份、表情和运动质量仍需独立模型与人工验收。

## 剪辑、资源和 GPU

原生完整输出变速允许保留独立空间入出场；两源转场端点仍需选择完整上级组。分片、VFR、非零起点、倒放、定格、共享变速保留原有时钟。后续CLI0.1.32已接通[原生时钟烘焙](TRACKING_BAKE.md)；本页CLI0.1.31为历史实测，普通原生工程包继续保留全部绑定。

真实转场会读取对端实际图层；新增依赖检查在像素 I/O 之前拒绝循环及超过 64 层的可见度依赖。该检查保守处理完整声明图，可能拒绝时间窗不相交的循环声明。原有 128 绑定、64000 总观察、4000 单绑定观察、4096 总源引用和 16 层绑定限制保留。

直接叶片图层按帧缓存，最多 `min(max_working_bytes/4, 64MiB)`；嵌套输出仍遍历并保留元数据。转场足迹分块在 CPU 计算，具有取消轮询和工作区配额；配额是分配估算，不是进程总 RSS。已有探测通过的 GPU 投影与 normal 合成继续使用 GPU，不声称全流程 GPU 常驻。

## C41 复现与验收

[案例及可编辑包](CASES.md#c41-tracking-visibility) · [本地安装](COMMUNITY_LOCAL_DELIVERY.md) · [版本](../releases/CLI_0.1.31_LOCAL.md) · [实测证据](../validation/跟踪实际可见度实测_2026-10-26.md)。

```powershell
C:/Python313/python.exe -E -B -u -X utf8 scripts/run_tracking_visibility_case_20261026.py --run r2
```

选择未使用的 run ID，保留失败记录。C41 使用自制 CC0 C36 几何视频、透明标记与合成双声道声音；导入后创建双源滑动转场、动态羽化遮罩与两个标签。完整画面/原始时钟/来源足迹、独立无绑定参考输出、音轨、包往返和队列分别留证。受控样例不等于自然质量或全部产品目标验收。

<a id="c41-tracking-visibility"></a>

## C41 · 跟踪遮罩与空间转场 · CLI0.1.31

C41：45次跟踪求值对照独立整数滑动参考，全部36帧Float32及解码画面对照无绑定参考工程，完整144000双声道采样、包往返、队列分别核验。实际GPU投影/合成及清理留证。仅受控素材/静态抽帧，未验收自然遮挡、身份、连续播放或人工听感；38项原关闭条件保留。

![Actual silent GIF](../assets/tracking-visibility-20261026-r2/edited.gif)

[Before MP4](../assets/tracking-visibility-20261026-r2/before.mp4) · [Edited MP4](../assets/tracking-visibility-20261026-r2/edited.mp4) · [Editable package](../assets/tracking-visibility-20261026-r2/editable-tracking-visibility.aevpkg.zip) · [Source/rights](../assets/tracking-visibility-20261026-r2/SOURCE.txt) · [Hashes](../assets/tracking-visibility-20261026-r2/media-manifest.json) · [Workflow](TRACKING_VISIBILITY.md).
