# Float32 转场、真实句柄与可编辑组

agent editor kit CLI 0.1.21 / `v0.1.0-alpha.4-local.19`，单一 `$agent-ffmpeg-local-editor` 入口，17 个内部模块。显式选择 `settings.pixel_pipeline.engine="float32-native-v1"` 才启用本页的线性光路径；原有默认 FFmpeg 管线、OpenCL 投影、GPU 配音/翻译继续按各自契约使用。

## 输入、计算与输出

已经声明色彩信号的本地视频/图片、可编辑序列和转场声明，进入原生 PTS 帧宿主。片段效果、裁切、变换、蒙版与透明度先各自执行，两源转场在预乘 alpha 的线性 RGB 中混合，再合成到下层。不会把两张半透明图先后叠加冒充交叉淡化。Float64 分块计算，公开表面保持 Float32，最终交付边界按项目的输出信号与编码器转换。

原项目不改写：真实句柄扩展只存在于私有编译 IR。关键帧继续使用原作者时钟；VFR 采用原生 PTS；父级裁切、倒放、定格、曲线变速仍映射到子序列原转场时刻。音频来自显式音轨，复用原样本和源包络。倒放时，原 PCM 区间反转而包络按连续子序列展示边界计算，这与直接倒放已经混合的 PCM 有一个采样边界语义差异。

## 三种用法

1. **已有剪口、保留总时长**：用 `timeline transition` 添加/调长/移除 `source_transitions`。规划器核对两端实际源头尾句柄、显示帧网格、源整数 tick 和关联音轨；不足则失败，不克隆尾帧或补静音。
2. **已有重叠片段**：在 `transition_out` / `transition_in` 声明相同类型和秒数，交集必须精确等于时长。`dissolve`、`crossfade` 和空间图案配成一次双源混合；单独的 `fade` 保持边缘透明度包络语义。
3. **图层或可编辑组进出场**：单独 `transition_in/out` 对透明画布执行。`wipe`、`slide` 加 `direction` 可给整个子序列进出场；子序列内容及关联声音仍可编辑。

下面请求适用于 90000 ticks/s、12fps 的项目，五帧转场跨原剪口分配为前二帧、后三帧。使用自己的资产、片段和序列 ID，不照抄示例 ID。

```json
{"action":"add","id":"cut_ab","type":"dip_white","duration_tick":37500,"from_clip_id":"shot_a","to_clip_id":"shot_b","audio":"linked"}
```

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk capabilities
& $avk timeline transition --project $project --sequence-id $sequence --input $request --dry-run
& $avk timeline transition --project $project --sequence-id $sequence --input $request
& $avk validate --project $project
& $avk preview frame --project $project --sequence-id $sequence --frame $frame
& $avk render --project $project --sequence-id $sequence --output $output --hardware-encode off
& $avk quality check --project $project --sequence-id $sequence --input $output
```

`$project/$sequence/$request/$frame/$output` 需指向已准备好的本地工程、JSON、帧号和新输出。JSON 响应需检查退出码、`ok/errors/warnings/artifacts`。预检不等于渲染；交付时保留实际 manifest 和可编辑工程包。

## 图案与命名

后端 57 种 xfade 图案，加两种按原剪口比例计算的 dip，共 59 个图案 ID。`capabilities` 的 `transitions.float32_native.patterns` 返回完整稳定目录。

| 家族 | 后端图案 ID / 公共作者写法 |
|---|---|
| 线性混合与闪白/闪黑 | `fade`，连续别名 `dissolve/crossfade`；`fadeblack/fadewhite/fadegrays/fadefast/fadeslow`；真实句柄 `dip_black/dip_white` |
| 方向擦除与角落擦除 | 后端 `wipeleft/wiperight/wipeup/wipedown`；边缘 JSON 写 `wipe` + `direction=left/right/up/down`；`wipetl/wipetr/wipebl/wipebr` |
| 推移、覆盖、揭示 | 后端 `slideleft/slideright/slideup/slidedown`；边缘 JSON 写 `slide` +方向；`coverleft/coverright/coverup/coverdown`；`revealleft/revealright/revealup/revealdown` |
| 圆形与矩形 | `circlecrop/rectcrop/circleopen/circleclose/horzopen/horzclose/vertopen/vertclose` |
| 平滑、对角与旋转 | `smoothleft/smoothright/smoothup/smoothdown`；`diagtl/diagtr/diagbl/diagbr`；`radial` |
| 切片与风噪 | `hlslice/hrslice/vuslice/vdslice`；`hlwind/hrwind/vuwind/vdwind` |
| 像素、模糊、缩放与压缩 | `pixelize/hblur/zoomin/squeezeh/squeezev`；颜色距离 `distance` |

真实源句柄编辑器的类型是 `dissolve/crossfade/dip_black/dip_white/wipe_left/wipe_right/wipe_up/wipe_down/slide_left/slide_right/slide_up/slide_down` 十二种。其余形态用显式重叠或图层边缘声明。后端图案 ID 与公共作者字段写法有区别，上表给出了方向别名。

## 验证与边界

透明 RGB 清零，可见有限负值和超白保留；`fadefast/fadeslow` 的可见 RGB 要求 0..1，不会偷偷截断。空间公式改编自 [FFmpeg n8.0 vf_xfade.c](https://github.com/FFmpeg/FFmpeg/blob/n8.0/libavfilter/vf_xfade.c)，该派生模块为 LGPL-2.1-or-later，离线安装包含可修改源码、完整许可及 NOTICE。线性光/alpha 算术有别于整数 xfade；风噪的正弦哈希有平台差异。

独立原生 FFmpeg 中点对照覆盖全部 57 图案，其中 53 个非风噪图案最大误差 1 个 16 位码值；风噪仅报告差异，不声称逐位一致。[原始比较](../validation/evidence/float-transition-20261026-r1/xfade-r1/verification.json)。[安装版完整 4K 图像核对](../validation/evidence/float-transition-20261026-r1/4k-r1/verification.json)覆盖淡化、逐行模糊和擦除，分配估算限制 512MiB，误差最多 5.96e-8；这是单帧核对，不是 4K 实时承诺或峰值 RSS 测量。

同轨双源窗口不得相交，两端冲突或时长不符拒绝；双源图层暂只接受 normal 混合。真实句柄端点沿用直接本地视频/显式音轨、恒速/倒放等既有范围，不能借此承诺曲线/定格片段的句柄扩展。已完成子序列可以再被父级变速/定格/倒放。CPU 分块执行，未接入 GPU；预算不是全进程 RAM/VRAM 上限。字幕/生成器等尚未移植的浮点操作仍明确拒绝。

自然素材、连续运动、声音听审、HDR、长片、通用性能与完整剪映等价继续验收，全部 G01–G38 原关闭条件保持。[实现契约](../specs/Float32转场实现契约_20261026.md)。

## English / 繁體快速说明

The explicit Float32 path now evaluates actual premultiplied linear-light transitions,
real source handles, linked audio and nested group edges. Use an exact overlap or
the declarative source-handle editor, retain the author's clock, preview the cut,
render and inspect the encoded result. CPU only; wind hashes differ by platform.
The FFmpeg-derived module is LGPL-2.1-or-later, with source and notices included.
Natural/HDR/long-form/full CapCut equivalence remains open.

明確選擇 Float32 管線後，可執行線性光預乘轉場、真實來源句柄、關聯音軌與巢狀群組進出場。先以精確重疊或轉場編輯器建立宣告，再預覽、渲染並檢查實際編碼。CPU 執行，風噪雜湊有平台差異；原工程與作者時鐘保留。自然視聽、HDR、長片與完整剪映等價仍未結案。


## 已安装案例与复现

[原输入](../assets/float-transition-20261026-r3/original.native.mkv) · [原音轨](../assets/float-transition-20261026-r3/original.audio.wav) · [MP4](../assets/float-transition-20261026-r3/transitions.mp4) · [可编辑包](../assets/float-transition-20261026-r3/editable-transitions.aevpkg.zip) · [完整命令/核验](../validation/evidence/float-transition-20261026-r1/case-r3/verification.json)。

```powershell
$caseZip = 'E:/dev/sandbox/AI广告剪辑/docs/assets/float-transition-20261026-r3/editable-transitions.aevpkg.zip'
$project = 'E:/video-work/float-transitions-review'
& $avk convert import --input $caseZip --output $project
& $avk validate --project $project
& $avk preview frame --project $project --frame 36
& $avk render --project $project --output (Join-Path $project 'renders/review.mkv') --container mkv --hardware-encode off
```

选择新的工程目录和输出。队列作业还须显式写 `container:"mkv"` 与匹配的 PCM 音频设置；队列默认 MP4，不根据输出扩展名改容器。案例原格式 MKV 保留完整 Float32 PCM；展示 MP4 另作明确输出传递转换和 AAC 压缩，不作为无损音频证据。

![Actual registered Skill output / silent](../assets/float-transition-20261026-r3/transitions.gif)
