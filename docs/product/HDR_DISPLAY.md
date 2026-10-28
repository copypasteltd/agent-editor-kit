# 原生 HDR 信号与 SDR 预览 / Native HDR signals and SDR viewing

CLI 0.1.40 在 `float32-native-v1` 中接入显示光 PQ、HLG、明确亮度单位、
BT.2020 NCL 10-bit 编码及可选 SDR 显示映射。源素材、合成工作域和交付边界均由作者
明确声明；不会仅凭文件的 HDR 标签决定相机曝光、纸白或显示器参数。

[README](../../README.md) · [English](../../README.en.md) · [繁體中文](../../README.zh-TW.md)

## 信号与亮度单位

原有 `{ "primaries": "bt709", "transfer": "srgb" }` 等二字段信号保持原来的相对数值解释。
新信号增加 `reference_white_nits`，表示该信号解码后线性 RGB 数值 `1` 对应的 cd/m²。
这使 SDR 图形、较亮的高光与不同纸白素材能够在共同的显示线性光域合成。

| 字段 | 解释与约束 |
|---|---|
| `primaries` | `bt709`、`display-p3`、`bt2020` 默认D65；CLI0.1.45另支持ProPhoto D50/AP1 D60和明确white_xy，见[白点适应](CHROMATIC_ADAPTATION.md)；PQ/HLG编码端要求BT.2020/D65 |
| `transfer` | 原有 `linear`、`srgb`、`bt709-oetf`、`gamma22`、`gamma24`，另有 `pq-st2084`、`hlg-bt2100` |
| `reference_white_nits` | 明确有限数值 0.01–10000；HDR 工程的所有视觉源、工作信号与输出均须声明 |
| `display_peak_nits` | HLG 必须声明，100–10000 cd/m²；其他传递函数不用此项 |
| `system_gamma` | HLG 必须声明，0.5–3；不由标签或显示器状态推测 |
| `hdr_input_range_policy` | 每个 `sources.<asset_id>` 的可选 `reject` / `clip`，默认 `reject`；明确处理解码后超出 0–1 的 PQ/HLG 编码分量 |
| `range_policy` | 最终交付 `reject` / `clip`；HDR 输出在标准定义域之外时，必须拒绝或明确计数截断 |

例如，工作域 `bt2020/linear/reference_white_nits=203` 中，1000 cd/m² 的中性高光
约为 RGB `4.9261`，不会在合成前降成 8-bit 或截到 `1`。图形、文字、粒子等现有相对
作者颜色沿用工作域的参考白单位；外部视觉资产必须单独明确亮度。alpha 始终是覆盖率，
不参与传递函数或亮度缩放；颜色转换保留其 Float32 位模式。

PQ 用 [ITU-R BT.2100-3 表 4](https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.2100-3-202502-I!!PDF-E.pdf)
的显示 EOTF 与逆 EOTF，将编码信号与 0–10000 cd/m² 联系起来。它不是相机 OETF。
HLG 用同一标准表 5 的逆 OETF 和 RGB 联动 OOTF，明确峰值与 system gamma；当前采用
理想零黑位。彩色像素的亮度耦合不能替换成三个独立通道的 gamma。

## 实际处理顺序

原生帧与 PTS → 明确 YCbCr 矩阵/量程/采样位置（若需要）→ PQ/HLG 解码 →
参考白亮度单位换算、RGB基色矩阵与明确白点Bradford适应 → Float32 显示线性光剪辑、效果与合成 →
可选 SDR 显示映射 → 输出传递函数 → 明确的整数边界 → 10-bit 编码。

数值转换按块使用 Float64 计算，并写回 Float32 工作表面；其算子预算与取消检查沿用
现有原生色彩管线。颜色传递转换当前由 CPU 执行；几何、正常叠加、文字、粒子和已接通
的光效可继续选择实际 OpenCL GPU。硬件编码配置沿用现有支持边界，不能把 GPU 合成
与 GPU 编码混为一项。

PQ/HLG 源编码 RGB 默认须在 0–1。YCbCr 重建和有损编码可能产生轻微超界；如决定
截断，给该资产明确 `hdr_input_range_policy: "clip"`，并检查
`HDR_input_components_clipped_across_decoded_windows`。这是解码窗口内实际工作量的
累计计数，重复解码同一帧也会计入，不是唯一源像素总数。

## HDR 输出配置

以下为 `settings` 内的配置片段；`picture` 必须是实际登记的资产 ID。

```json
{
  "color": {"primaries":"bt2020","transfer":"smpte2084","matrix":"bt2020nc","range":"limited"},
  "output": {
    "container":"mkv",
    "video":{"codec":"libx264","crf":0,"preset":"ultrafast","pixel_format":"yuv444p10le"},
    "audio":{"codec":"pcm_f32le"}
  },
  "pixel_pipeline": {
    "engine":"float32-native-v1",
    "working_signal":{"primaries":"bt2020","transfer":"linear","reference_white_nits":203},
    "output_signal":{"primaries":"bt2020","transfer":"pq-st2084","reference_white_nits":203},
    "range_policy":"reject",
    "sources": {
      "picture": {
        "source_signal":{"primaries":"bt2020","transfer":"pq-st2084","reference_white_nits":203},
        "display_geometry":"square-unrotated",
        "demux_origin":0
      }
    },
    "preview_mapping": {
      "operator":"reinhard-luminance",
      "source_peak_nits":1000,"target_peak_nits":100,"exposure_stops":0,"gamut_policy":"clip"
    }
  }
}
```

HLG 的 `output_signal` 改为 `hlg-bt2100`，并声明 `display_peak_nits`、`system_gamma`，
同时将 `color.transfer` 改成 `arib-std-b67`。HDR 输出只接受明确的
`yuv420p10le`、`yuv422p10le` 或 `yuv444p10le`；色彩标签须匹配实际转换，
8-bit、透明输出、错误矩阵或缺少亮度单位均会拒绝。

YCbCr 源还须声明 `yuv_spec`（例如 `bt2020nc`、`limited`、`left`）与
`scan: "progressive"`。既有几何、时间基、范围窗口、源持锁与依赖校验约束继续适用。
选择 HLG 峰值不同的接收设备时，应据目标条件明确给出新的 system gamma。

输出携带匹配的 BT.2020、传递函数、NCL 矩阵和量程 VUI 标签。
CLI0.1.44另支持可选的[HDR10母版显示与MaxCLL/MaxFALL声明](HDR_METADATA.md)：
明确PQ/10-bit4:2:0/libx265时写入实际SEI并核验解码前缀；这些数值是作者声明，
不自动测量内容峰值。动态元数据或Dolby Vision仍未接通。

## SDR 映射与预览

HDR 工程调用 `preview frame/range` 时必须设置 `preview_mapping`。帧 PNG 为明确
sRGB SDR 图；区间参考是 BT.709 线性 Float32 的 SDR trim，MP4 是其观看副本。
预览不会改变 HDR 作者工程或原始 HDR 成片；此 SDR 参考不用于证明 HDR 监看质量。

把同一配置放到 `pixel_pipeline.display_mapping` 可输出独立 SDR 成片；此时
`output_signal` 须为 BT.709 的支持传递函数，其 `reference_white_nits` 必须等于
映射的 `target_peak_nits`。HDR 输出不能同时添加此 SDR 映射。

映射采用目标线性光亮度的 modified Reinhard：令 `x = Y_nits / target_peak_nits ×
2^exposure_stops`，`w = source_peak_nits / target_peak_nits`，映射亮度为
`x(1+x/w²)/(1+x)`，再按亮度比例缩放 RGB。源峰值是作者给定的肩部参数，不是自动
分析结果。`exposure_stops` 范围 −16–16；`gamut_policy` 明确拒绝或计数截断目标
RGB 的负分量及超过 1 的分量。映射前后 alpha 位模式保持。

这是可编辑的创作性 SDR trim，不宣称 BT.2390、感知色域压缩或自动母版质量。
自然画面、色彩关系、暗部、高光与显示设备仍需要分别检查。

## 本机可复现流程 / Reproduce the installed case

以下命令使用实际注册的统一 Skill、C50 的可编辑包和新的本机目录。案例包含
GPU Bloom、HDR 图表、另一参考白的 SDR 图形和非静音双声道。设备 `0.0` 是本机
已核验的 OpenCL 设备；其他机器应先检查其设备信息。

```powershell
Set-Location 'E:/dev/sandbox/AI广告剪辑'
$hdrLauncher = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
$hdrExample = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/hdr-usage-r1'
& $hdrLauncher convert import --input 'E:/dev/sandbox/AI广告剪辑/docs/assets/native-hdr-20261027-r3/editable-native-hdr.aevpkg.zip' --output $hdrExample
& $hdrLauncher validate --project $hdrExample
& $hdrLauncher preview frame --project $hdrExample --frame 24 --height 360
& $hdrLauncher preview range --project $hdrExample --start-frame 0 --end-frame 48 --height 360
& $hdrLauncher render --project $hdrExample --output "$hdrExample/renders/usage-pq.mkv" --container mkv --video-codec libx264 --crf 0 --pixel-format yuv444p10le --audio-codec pcm_f32le --hardware-encode off --projection-acceleration require --projection-device 0.0
```

查看返回的 PNG／SDR MP4，再检查 HDR 母版的实际像素、VUI 和完整音轨。
切换 HLG 或创建 SDR 成片前，按上面的约束更改输出信号、标签及可选映射，并重新验证。
源文件和原 PQ 工程包可保留，以便重新选择显示参数。

## English operating contract

Use explicit display-light PQ or HLG and declare `reference_white_nits` on every
visual source, linear working signal and output. HLG additionally requires an
explicit display peak and system gamma; this implementation assumes ideal zero
black. The legacy two-field relative signals retain their existing semantics.

HDR is decoded to display-linear Float32, edited using the original author
clocks, then encoded through a declared 10-bit BT.2020 NCL boundary with matching
VUI. PQ/HLG domain violations default to rejection. Source and output clipping
require separate explicit policies and report the actual clamped components.
Transfer math runs on the CPU; supported composition/effects can use OpenCL.

For client previews, supply `preview_mapping`. Show the generated SDR PNG/MP4
alongside the declared mapping and keep the original HDR master available.
`display_mapping` produces a separate SDR trim; its target peak must match the
SDR output reference white. Neither operation establishes HDR monitor acceptance,
ICC support, dynamic metadata or full product parity. Optional declared HDR10
static metadata is documented in [HDR10 metadata](HDR_METADATA.md).

CLI0.1.45: [explicit reference-white conversion](CHROMATIC_ADAPTATION.md) extends source/linear working/effect signals to ProPhoto D50,AP1 D60 and explicit xy. BT.2100 encoded signals/output remain D65; this does not parse ICC or provide full ACES rendering.

CLI0.1.46 adds a separate [native ICC source-profile path](ICC_PROFILES.md): explicit RGB v2/v4 matrix/table files, rendering intent/BPC and direct linear working RGB conversion. Existing mathematical reference-white conversion still infers no profile or physical illuminant. ICC white tags do not supply HDR luminance; declare source/working/output nits separately.

CLI0.1.47 adds [HLG display black and complete source/working signal JSON for raw surface CLI](HLG_BLACK_LEVEL.md). Explicit nits,black/peak/gamma and reject/clip policies are required; no monitor inference. Existing RGB/ICC individual flags remain supported.
