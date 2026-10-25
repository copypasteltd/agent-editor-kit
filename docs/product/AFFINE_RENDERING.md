# 仿射渲染复用 / Affine rendering reuse

CLI **0.1.17 / alpha.4-local.15** 自动复用固定画布仿射合成中的扫描行参数。无需新命令或修改工程；普通 `render`、嵌套同画幅变换及已有运镜包继续输出可编辑工程。

**English:** Fixed-canvas affine composition automatically reuses pure transform parameters within each scanline. Existing projects, motion packs, render commands and editable keyframes keep their contracts. This is a CPU optimization; selected hardware encoders remain separate.

[实测与交错计时 / Paired measurements](../validation/仿射扫描行复用实测_2026-10-25.md) · [六套运镜参数 / Motion workflow](MOTION_PACKS.md) · [本地安装 / Installation](COMMUNITY_LOCAL_DELIVERY.md)

## 使用 / Usage

```powershell
# Use actual project/sequence IDs and the registered Skill launcher.
& $avk capabilities
& $avk motion pack apply --project $project --sequence-id $sequence --clip-id $clip --name detail_scan --dry-run
# Inspect conflicts. Apply without --dry-run when the target is correct.
& $avk render --project $project --sequence-id $sequence --output "$project/renders/review.mp4"
& $avk quality check --project $project --input "$project/renders/review.mp4"
```

没有“快但画质低”的开关：同一浮点预乘、双线性逆采样、半像素坐标和反预乘顺序继续执行。每个颜色平面、每个线程切片、每条扫描行在 X=0 刷新，不以时间戳缓存整帧，因此重复/倒退时间戳也重新计算。带像素坐标或有状态函数的内部表达式沿用逐像素求值。

**English:** The existing premultiplied float bilinear sampler and arithmetic order remain. Each plane/slice refreshes at the first pixel of every row. There is no cross-frame cache or dependence on monotonically increasing timestamps. Pixel-dependent or stateful expressions retain legacy evaluation.

## 实际预览 / Actual preview

![实际安装版旋转扫视 / Actual installed rotating scan](../assets/affine-scanline-20261025-r1/detail-scan.gif)

[原图 / Original](../assets/affine-scanline-20261025-r1/original.png) · [MP4](../assets/affine-scanline-20261025-r1/detail-scan.mp4) · [中点静帧 / Midpoint](../assets/affine-scanline-20261025-r1/midpoint.png) · [来源和摘要 / Provenance](../assets/affine-scanline-20261025-r1/media-manifest.json)

实际输出来自同一自制 FIELD NOTES 图卡和已发布 detail_scan 默认配方；MP4 640×360/30fps/4秒/120帧，无声；GIF 480×270/10fps/40帧。预览编码为 NVENC，变换合成为 CPU。旧版和新版在相同工程、源图、编码参数、子进程CPU亲和性下交错三轮；所有120帧及完整音频PCM相同。各次时间、中位数和测量边界保留在实测记录，不使用此前并发65秒作为新加速比基线。

**English:** The silent preview uses the existing self-authored card and default detail_scan recipe. Three paired, interleaved old/new CPU renders use the same project, source, codec settings and child-process CPU affinity. Full decoded frames and PCM are compared. See the evidence for individual timings and medians; the earlier concurrent 65-second observation is historical rather than the denominator for a new speed ratio.

此优化只覆盖固定画布仿射 helper；动态 crop/fit 的序列投影、其他 geq 滤镜、4K/长片/并发RSS和自然素材美学并未因此验收。已有空间路径仍为65点折线；不改变其他原目标门槛。

**English:** This does not optimize every geq filter or the separate crop/fit sequence projector. General 4K, long-form, concurrency/RSS and natural-footage acceptance remain open. Motion paths still use 65 linear samples.

2026-10-26: CLI0.1.19 extends pure scanline reuse to animated crop and child crop/fit/TRS, for bilinear and area. [Current workflow / 当前使用](PROJECTION_RENDERING.md) includes the editable combination case and actual previews; historical timing remains scoped to its original fixture.

2026-10-26: [CLI0.1.20 native GPU projection / 原生GPU投影](OPENCL_PROJECTION.md) adds explicit OpenCL crop/affine/child-canvas samplers,actual-device/precision probes and failure/queue handling. Earlier CPU timing and scope remain historical; other effects stay CPU.
