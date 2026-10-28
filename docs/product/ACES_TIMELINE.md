# ACES 时间线、预览与工程重放（源码 CLI 0.1.53）

本页描述源码阶段的新路径。正式交付、逐帧测量和预览已接到原生 OpenColorIO 2.6.0 显示/视图变换；当前安装包和本地 `$agent-ffmpeg-local-editor` 仍是 CLI52，不能直接以已安装入口调用本页的新功能。离线打包、安装验收和 Skill 激活另行完成。

## 输入语义与显示选择

ACES 使用场景线性 ACEScg（AP1、D60）作为工作输入。`input_interpretation` 是作者对数值语义的明确声明，不会自动对相机 Log、普通 sRGB、PQ 或 HLG 素材施加相机 IDT。已有显式素材信号转换仍负责将素材变到工作 RGB；它不因此成为相机标定。带 nit 的工作信号也不会在 ACES 调用前再按输出亮度缩放一次：传给 Output Transform 的是已声明的场景相对值。

必须先通过 `surface ocio-configs` 查询固定配置，再选择真实 display/view。ACES 2.1 配置的 SDR 视图仍名为 `ACES 2.0 - SDR 100 nits (Rec.709)`。交付路径不接受 Raw/Un-tone-mapped 冒充 ACES Output Transform。

| 编号 | 显示 | OCIO 实际输出 | 后续交付 |
| --- | --- | --- | --- |
| A01 | sRGB - Display | BT.709 / sRGB | 明确作者 SDR 传递函数 |
| A02 | Rec.1886 Rec.709 - Display | BT.709 / gamma 2.4 | 先解码实际 gamma，再转作者 SDR 信号 |
| A03 | Gamma 2.2 Rec.709 - Display | BT.709 / gamma 2.2 | 同上；该显示是否可用由固定配置决定 |
| A04 | Rec.2100-PQ - Display | BT.2020 / ST 2084 | 必须匹配作者 PQ 输出及 10-bit 编码 |
| A05 | Rec.2100-HLG - Display | BT.2020 / HLG 1000 nit | 必须匹配 1000 nit、gamma 1.2、零显示黑位及 10-bit 编码 |

显示空间与视图的组合由官方配置校验。PQ 视图的内容峰值不是自动测得的内容峰值，不会自动填入 HDR10 MaxCLL/MaxFALL。其他显示、相机 IDT、AMF/LMT、动态 HDR 与物理监看仍未验收。

## Agent 使用步骤

1. 确认运行的是源码 CLI53：`version` 和 `capabilities` 中应出现 `native_aces_display`。已安装 CLI52 暂不包含它。
2. 查询 `surface ocio-configs --config aces-2.1`，记录固定 URI、配置摘要和准确的 display/view 名称。
3. 把下列字段合并到已有 `settings.pixel_pipeline`；保留 `engine`、素材 `sources`、预算等其他必要字段。这不是独立完整工程。

```json
{
  "working_signal": {"primaries": "aces-ap1", "transfer": "linear"},
  "output_signal": {"primaries": "bt709", "transfer": "srgb", "reference_white_nits": 100},
  "range_policy": "clip",
  "aces_display": {
    "config": "aces-2.1",
    "display": "sRGB - Display",
    "view": "ACES 2.0 - SDR 100 nits (Rec.709)",
    "exposure_stops": 0,
    "input_interpretation": "scene-linear-ACEScg"
  }
}
```

4. 同时令作者 `settings.color` 匹配输出：上例使用 BT.709 基色、`iec61966-2-1` 传递函数与 BT.709 矩阵。SDR 输出若声明亮度单位，须为该 SDR 视图的 100 nit。选择 `reject` 时，实际超范围值会失败；`clip` 才允许最终边界裁切并计数。
5. 执行 `validate`，再执行常规 `render`。收据应记录 `aces_display`、`last_aces_display` 的处理器与配置摘要、实际帧/像素数量，以及 `ACES_processors_closed`。
6. 执行 `surface measure`，核对其 `encoder_RGB16_input_sha256` 与成片收据 `transport.video_input_sha256`。这测量编码前交付 RGB16，不是编码后像素或物理显示峰值。
7. 用 `preview frame/range` 提供观看样例，导出可编辑工程包，在新目录导入并重放完整像素与 PCM。记录具体执行入口，不能把源码输出标为已安装 Skill 输出。

工程内的 ACES 声明随可编辑工程包迁移；运行库固定在产品中，不将宿主系统 DLL 路径写成可移植素材引用。渲染、预览缓存和队列复用会核对固定原生文件及数值实现依赖，损坏文件应拒绝执行。

## 预览优先级与单次变换

- 明确 `aces_preview` 时，用该 SDR 观看变换替代正式交付视图，仅影响预览。
- 没有单独观看变换时，SDR 正式 `aces_display` 经过同一个正式交付边界，然后解码到显示线性域再缩小；不会再次执行 ACES。
- 既有 `preview_mapping` 仍可作为明确的替代观看配置，优先于继承正式 ACES。`aces_preview` 与 `preview_mapping` 不能同时声明。
- PQ／HLG 母版不能自动套 SDR 截断。必须单独声明 SDR `aces_preview` 或已有显式观看映射。作者 HDR 输出不因此改变。
- 正式 `aces_display` 不能同时叠加 `display_mapping`。ACES 与 ICC 软打样的复合路径尚未验收，当前明确拒绝该组合。

HDR 母版的 `aces_preview` 可使用上例整个 SDR 选择对象。正式 `aces_display` 改为准确的 PQ/HLG 显示与 HDR 视图，作者输出、编码与亮度单位也必须一起匹配。不能仅修改显示字符串。

## 源码入口与复跑

原生 Windows CPython 3.13 x64，在项目根目录定义开发入口，不调用全局安装或虚拟化环境：

```powershell
function aekdev {
  & C:/Python313/python.exe -E -B -X utf8 -c "import sys;sys.path.insert(0,r'E:/dev/sandbox/AI广告剪辑/product/src');from ai_ad_editor.cli import main;raise SystemExit(main())" @args
}
aekdev version
aekdev surface ocio-configs --config aces-2.1
aekdev validate --project <project-directory>
aekdev render --project <project-directory> --sequence-id <sequence-id> --output renders/aces.mkv
aekdev surface measure --project <project-directory> --sequence-id <sequence-id>
aekdev preview range --project <project-directory> --start-frame 0 --end-frame 8 --height 64
```

以下分别是专项、兼容和保留媒体的独立验收任务。只有对应终态收据为 passed 才算通过。

```powershell
C:/Python313/python.exe -E -B -u -X utf8 docs/validation/verify_aces_pipeline.py --group special --run-id r4
C:/Python313/python.exe -E -B -u -X utf8 docs/validation/verify_aces_pipeline.py --group meter --run-id r4
C:/Python313/python.exe -E -B -u -X utf8 docs/validation/verify_aces_pipeline.py --group compat --run-id r5
C:/Python313/python.exe -E -B -u -X utf8 docs/validation/verify_aces_pipeline.py --group case
```

[专项收据](../validation/evidence/aces-pipeline-20261029-r1/special-r4.json) · [测量/Schema回归](../validation/evidence/aces-pipeline-20261029-r1/meter-r4.json) · [案例收据](../validation/evidence/aces-pipeline-20261029-r1/case-r1.json)。开发观察与重跑历史单独保留，不累加成新功能。兼容r3是测量修复前启动的长任务，不作为最终源码冻结验收；后续r5门槛另验。

## 案例与未完成边界

案例是原创数值色条与立体声音调，96×128、10 FPS、8 帧、0.8 秒。它用于验证真实链路，不能证明自然画面的审美质量、长片吞吐或 HDR 监看。GIF 是从编码后的观看 MP4 制作的放大副本，不能拿它做浮点精度参考。

![Source ACES numeric case](../assets/aces-timeline-20261029-r1/preview.gif)

[观看 MP4](../assets/aces-timeline-20261029-r1/preview.mp4) · [作者成片](../assets/aces-timeline-20261029-r1/author-aces.mkv) · [第 7 帧 PNG16](../assets/aces-timeline-20261029-r1/frame7.png) · [可编辑工程包](../assets/aces-timeline-20261029-r1/editable-project.zip)。

ACES Output Transform 当前在 CPU 执行，投影／合成的既有 GPU 配置不改变这一点。原生模块驻留进程，处理器关闭收据不代表 DLL 卸载或全进程 RSS 测量。离线新包、实际安装 Skill、自然素材、更多显示制式、相机 IDT／AMF／LMT、GPU ACES 与完整监看仍待完成；原 38 项产品关闭条件不变。

繁體：原始碼 CLI53 接通原生 ACES 正式交付、逐幀測量、單次顯示轉換後的線性縮圖，以及 HDR 母版的獨立 SDR 預覽。已安裝 Skill 仍為 CLI52；CPU ACES 不代表 GPU 或完整色彩驗收。

English: Source CLI53 connects pinned native ACES display/view transforms to formal rendering and metering, inherits the SDR delivery edge once before display-linear resizing, and supports an explicit separate SDR view for HDR masters. Installed Skill delivery is still CLI52. The numeric example is an integration proof, not natural-footage, monitor, real-time or full-product acceptance.
