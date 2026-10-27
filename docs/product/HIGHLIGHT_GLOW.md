# 高光扩散 / Highlight-derived Bloom and Halation

CLI0.1.39 在普通片段 `effects` 和选定序列的 `settings.adjustments` 中支持
`bloom`（别名 `highlight_bloom`）与 `halation`（别名 `film_halation`）。
两项均为原创 MIT 算子，无模型、外部特效包或网络依赖。与固定位置的眩光不同，
它们从输入画面的实际高光产生扩散光。Halation 提供暖色边缘光晕；这是艺术化
胶片效果，尚未标定真实胶片乳剂、镜头、曝光或色彩科学。

[README](../../README.md) · [English](../../README.en.md) ·
[繁體中文](../../README.zh-TW.md) · [C49 真实案例](CASES.md#c49-highlight-glow) ·
[安装及使用](../releases/CLI_0.1.39_LOCAL.md) ·
[核验](../validation/高光扩散实测_2026-10-27.md)

## 输入、输出和算法

使用 `float32-native-v1`，明确线性 RGB 工作域、每个资产的来源信号、几何及解复用原点、
输出信号和范围策略。支持 D65 bt709、display-p3、bt2020 基色；阈值使用相应 RGB→XYZ
矩阵的 Y 行计算相对亮度，不把视频标签猜作 HDR 或绝对尼特。

处理顺序为：提取高光 → 横向 Gaussian FIR → 纵向 Gaussian FIR → 与原图合成。
每一步输出 Float32；阈值、卷积累加和合成使用 binary64。高斯截断在 `ceil(3*radius)`，
按完整有限核归一化，半径为零时核为单点。边界是显式透明黑扩展或端点复制。

亮源取 `max(RGB,0)`，相对亮度为 L。硬阈值贡献为 `max(L-threshold,0)`；
软膝贡献为 `clamp(L-threshold+knee,0,2*knee)^2/(4*knee)`（knee=0 时关闭）。
取两者最大值后限于 L，再以 `contribution/L` 缩放亮源颜色，并乘**源 alpha**。
黑色不会凭空发光，隐藏在全透明像素中的 RGB 不会照亮邻居。

Bloom 将扩散结果乘 RGB 色调及 `intensity*gain` 加入原 RGB。
Halation 先逐通道取 `max(扩散光-core_suppression*原高光,0)`，再着色、叠加，
用于保留亮部主体而在其邻域产生暖色光晕。两者保持原 alpha **位模式**，包含次正规数和
负零；激活时全透明位置 RGB 清零，不扩大覆盖率。部分透明源只贡献与其覆盖率相应的光能。
输出 RGB 可超过 1，必须明确采用保留范围或交付裁切策略。

## 参数和关键帧

| 参数 | Bloom 默认 | Halation 默认 | 范围与实际含义 |
|---|---:|---:|---|
| `intensity` | 1 | 1 | 0…1，最终加光强度 |
| `threshold` | .7 | .7 | 0…16，线性工作域相对亮度阈值 |
| `knee` | .2 | .2 | 0…4，阈值两侧的软膝宽度；0 为硬阈值 |
| `radius` | 12 | 6 | 0…32，输入效果表面上的高斯 sigma，单位像素；支持浮点与动画 |
| `gain` | 1 | 1 | 0…8，扩散光增益；与 intensity 相乘 |
| `red` | 1 | 1 | 0…4，线性工作 RGB 中的红光倍率 |
| `green` | 1 | .2 | 0…4，绿光倍率 |
| `blue` | 1 | .05 | 0…4，蓝光倍率 |
| `core_suppression` | 不接受 | 1 | 0…1，仅 Halation；扣除原高光以抑制核心 |
| `edge` | transparent | transparent | `transparent` 或 `clamp`，静态枚举，不支持关键帧 |

所有数值参数支持 hold、linear、ease_in、ease_out、ease_in_out、bezier 六种插值；
每通道最多 1024 个键、每效果最多 16384 个键、序列化上限 4MiB。
每个项目关键帧均需显式填写 `interpolation`，包含最后一个键。
片段使用原作者呈现时钟，裁切和拆分不重新起算；倒放使用半开源帧及连续作者时钟左极限。
调整层使用选中根的区间局部时钟，在全部视频及字幕合成后按顺序应用一次。

强度或增益为 0、全部色调为 0 时逐字节返回输入且不派发 GPU；
Halation 的 radius=0 且 core_suppression=1 同样为无操作。

## Agent 的使用流程

使用统一 Skill 的已校验安装版入口。首次查看能力与参数，随后导入案例或建立自己的显式信号工程：
以下本机复现命令从当前仓库根目录执行；移动仓库后请改为实际克隆目录。

```powershell
Set-Location 'E:/dev/sandbox/AI广告剪辑'
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk effects list --query native:float32-glow --keyframable-only
& $avk effects inspect --name bloom
& $avk effects inspect --name film_halation
& $avk convert import --input docs/assets/highlight-glow-20261027-r1/editable-highlight-glow.aevpkg.zip --output local/agent-ffmpeg/my-glow-project
```

如需修改，读取工程中实际 clip ID，保留所有所需效果后用 `update_clip` 替换整条 effects 数组。
以下 composition.json 适用于已包含 `bloom` 片段的 C49 工程；90000 ticks/s，共四秒：

```json
{"operations":[{"op":"update_clip","clip_id":"bloom","patch":{"effects":[
 {"type":"bloom","parameters":{"radius":10,"threshold":0.4,"knee":0.15,"gain":1.5},
  "keyframes":[{"property":"intensity","keyframes":[
   {"at_tick":0,"value":0.2,"interpolation":"ease_in_out"},
   {"at_tick":360000,"value":0.9,"interpolation":"linear"}]}]}
]}}]}
```

```powershell
& $avk timeline compose --project local/agent-ffmpeg/my-glow-project --input composition.json --dry-run
& $avk timeline compose --project local/agent-ffmpeg/my-glow-project --input composition.json
& $avk validate --project local/agent-ffmpeg/my-glow-project
& $avk preview frame --project local/agent-ffmpeg/my-glow-project --frame 24 --height 540
& $avk render --project local/agent-ffmpeg/my-glow-project --output local/agent-ffmpeg/my-glow-project/renders/glow.mp4 --projection-acceleration require --projection-device 0.0 --hardware-encode off
```

`require` 要求实际可用的原生 OpenCL GPU；`prefer` 只在预检无法使用时按既有策略选择 CPU，
运行中故障不静默降级；`off` 使用 CPU 参考。硬件编码与这些效果的 GPU 运算是独立选项。
旧 FFmpeg graph 会明确拒绝这两个原生算子。

## GPU、预算和交付证据

每个激活的效果执行 **4 次 GPU kernel dispatch**：bright、horizontal blur、vertical blur、merge。
原图与两个临时表面复用已有三个所属 GPU buffer，三个中间图均留在显存，仅最后下载一次。
控制仍走渲染所属的本机管道和共享内存；没有外部服务或全局 GPU 工作进程。

读 manifest 中的 `operations.glow`（编辑帧操作数），以及 `native.operations.glow_bright`、
`glow_blur`、`glow_merge`（设备 kernel 总数）。设备总数含独立启动探测，不能直接当成内容帧计数。
本版主探测增加两种效果各四个 kernel，共 17 个命名主派发；原次正规辅助探测另列。
同时检查 worker、共享句柄、控制线程和流已关闭及未发生运行时 CPU 回退。

CPU/GPU 均在分配前检查尺寸、已有完整空间工作区和邻域访问预算。算子工作区上限 768MiB，
保守估算包含完整空间暂存、LUT 保留及分块；这是算子配额，**不是整个程序 RSS/显存保证**。
每帧访问上限为 2^32，计划值为 `像素数 * (2*ceil(3*radius)+1) * 2`。
大分辨率、大半径可能触及配额；本版没有提供实时、4K 长片或多 GPU 性能保证。

工程包和本地 OTIO 保留效果及所有数值轨道，导入后可继续改参数；其他外部编辑器未必能够执行
这些原创算子。自然素材、肤色、镜头间一致性、曝光习惯、HDR、物理胶片及完整剪映效果库仍须继续验收。

![C49 actual GPU output](../assets/highlight-glow-20261027-r1/highlight-glow.gif)

[原图](../assets/highlight-glow-20261027-r1/original-source.png) ·
[移除效果对照](../assets/highlight-glow-20261027-r1/before.png) ·
[实际输出静帧](../assets/highlight-glow-20261027-r1/contact.png) ·
[MP4](../assets/highlight-glow-20261027-r1/highlight-glow.mp4) ·
[可编辑包](../assets/highlight-glow-20261027-r1/editable-highlight-glow.aevpkg.zip) ·
[已实际执行的修改 JSON](../assets/highlight-glow-20261027-r1/usage-composition.json)

## English usage contract

Bloom and Halation derive light from actual coverage-weighted positive linear RGB
highlights. D65 working primaries determine luminance. A soft-knee bright pass feeds
normalized three-sigma separable Gaussian FIR stages; Halation subtracts an editable
bright core before applying a warm tint. Sigma is 0…32 input-surface pixels. All numeric
fields animate on the original author clock; `edge` remains static. Original alpha bits
survive, hidden transparent RGB emits no light, and extended RGB requires an explicit
delivery range policy.

Inspect `effects list --query native:float32-glow` and `effects inspect` through the
pinned installed Skill, import the editable C49 package, then dry-run/apply a composition,
validate, preview and render. Both operators support selected-root adjustment intervals.
Actual OpenCL execution uses four kernels and a single final readback per active operation;
the CPU reference uses the same Float32 stage boundaries. Read edited-frame operation
counts separately from startup probe kernels and verify owned-resource cleanup.

The chart demonstrates deterministic editing, GPU execution and project interchange.
It does not establish natural-footage quality, physical film accuracy, HDR, real-time
performance or complete CapCut parity. Keep still review, continuous playback and human
listening acceptance separate.
