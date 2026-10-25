# 动态裁切与嵌套投影 / Animated crop and nested projection

CLI **0.1.19 / alpha.4-local.17 / r20 kit**。动态 crop 的 fit/fill/stretch，以及原生子序列画布的 crop/fit/旋转/缩放/位置/锚点组合，自动复用每行的纯数值参数。现有命令和工程仍可使用；保持半像素位置、浮点预乘透明采样、作者时钟和采样精度。

Animated crop and child-canvas crop/fit/TRS automatically reuse pure parameters per scanline. Existing projects and commands work unchanged. Bilinear and source-axis fractional box area sampling preserve their precision, alpha behavior and authored clocks. This is CPU composition; GPU encoding remains a separate explicit choice.

[安装与包摘要 / Installation](COMMUNITY_LOCAL_DELIVERY.md) · [真实实测 / Evidence](../validation/裁切与序列投影实测_2026-10-26.md) · [完整功能 / Capabilities](CAPABILITIES.md) · [Skill](SKILLS.md)

## 使用 / Workflow

唯一入口是 `$agent-ffmpeg-local-editor`；Agent 先明确画布、片段、裁切关键帧、子序列关系及运镜，再验证和渲染。默认双线性；缩小细密纹理时可显式选择面积采样。配额不足会拒绝，不降低画质。已有工程的 sampler 优先由作者设置决定；以下参数是一次渲染的显式覆盖。

Use the single Skill. Author canvas/crop keys/child sequences/motion, validate, render and review the actual output. Bilinear is the default; select area explicitly when reducing fine detail. The raster admission quota rejects oversized combinations without lowering quality. Overrides apply to the requested render.

```powershell
$aekSource = 'E:/dev/sandbox/AI广告剪辑'
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk capabilities
# Choose a new destination / 目标目录需尚不存在
$aekProject = Join-Path $aekSource 'workspace/projection-client'
$aekCase = Join-Path $aekSource 'docs/assets/projection-scanline-20261026-r2/editable-projection.aevpkg.zip'
& $avk convert import --input $aekCase --output $aekProject
& $avk validate --project $aekProject
& $avk render --project $aekProject --sequence-id projection_demo --output (Join-Path $aekProject 'renders/client.mp4') --sequence-sampling area --sequence-memory-mib 1024 --hardware-encode off
```

该工程包含 640×360 自制图卡、480×270 子序列、384×216/30fps/4秒成片、动态裁切、子序列反向播放和 `arc_push` 普通可编辑关键帧。可以用 `motion pack apply` 调整运镜；先查看属性冲突，明确同意替换后使用 `--replace`。画面选型向客户展示真实 GIF/MP4，不以低清预览推断 4K 性能。

The editable case combines a self-authored 640×360 graphic, a 480×270 child and a 384×216/30fps/four-second output, animated crop, reverse child playback and editable `arc_push` keys. Inspect property conflicts before replacing motion. Show clients the actual preview; measure the real target duration and canvas for delivery.

## 实际预览 / Actual preview

[原图 / Original](../assets/projection-scanline-20261026-r2/original.png) · [实际 MP4](../assets/projection-scanline-20261026-r2/projection.mp4) · [可编辑案例 / Editable case](../assets/projection-scanline-20261026-r2/editable-projection.aevpkg.zip) · [文件摘要 / Media manifest](../assets/projection-scanline-20261026-r2/media-manifest.json)

![Actual installed output / silent](../assets/projection-scanline-20261026-r2/projection.gif)

## 实现与边界 / Implementation and limits

动态裁切在每个平面/切片的 X=0 初始化窗口与 fit 参数。序列投影在十个 AVExpr 寄存器内按重复表达式长度估计选择复用项，行常量和像素临时值分离；面积采样在求出左右边界后复用坐标寄存器保存上下边界，再以四个只读寄存器积分。该启发式只决定存储，不近似数值；不跨行/帧缓存，不依赖时间戳单调。像素依赖、有状态或未知函数保留旧逐像素路径。

Each plane/slice refreshes constants at X=0 on every row. A bounded dependency graph chooses repeated expressions to store, using disjoint pixel scratch registers. Area integration reuses the consumed coordinate registers for top/bottom, then reads four stored bounds without overwriting row constants. The heuristic changes storage only. Pixel/stateful/unknown expressions retain the original path; repeated or backward timestamps do not reuse another frame's constants.

面积核仍是源轴对齐矩形，不是旋转多边形积分。`sequence-memory-mib` 约束可达序列投影工作缓冲，不包含解码、编码、并行任务或整个进程 RSS。尚未验收全部 4K/长片、自然素材运镜美学或 GPU 合成。旧版本实测、失败和全部 G01–G38 原关闭条件保留。

Area remains a source-axis rectangle, not rotated-polygon integration. The quota covers reachable projection buffers, not total process RSS. General 4K/long-form performance, natural-motion aesthetics and GPU composition remain unaccepted. Historical evidence and all original goal closure conditions remain intact.

2026-10-26: [CLI0.1.20 native GPU projection / 原生GPU投影](OPENCL_PROJECTION.md) adds explicit OpenCL crop/affine/child-canvas samplers,actual-device/precision probes and failure/queue handling. Earlier CPU timing and scope remain historical; other effects stay CPU.
