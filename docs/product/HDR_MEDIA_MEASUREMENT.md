# 编码后原生成片光量复核

本地 CLI 0.1.50 / alpha.4-local.48 已安装并加载统一 `$agent-ffmpeg-local-editor`。`surface measure-media` 复核编码后文件，`surface measure` 测量编码器RGB16输入；两者不可混称。[安装流程](../releases/CLI_0.1.50_LOCAL.md)。

## 输入与调用

在工程内准备现有本地成片，以及明确的 RGB 信号 JSON。例如 PQ：

```json
{"primaries":"bt2020","transfer":"pq-st2084","reference_white_nits":203}
```

通过已注册本地统一Skill调用（原生PowerShell）：

```powershell
$aekSkill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aekSkill surface measure-media --project PROJECT --input renders/master.mkv --signal-json SIGNAL.json --pixel-family yuv --yuv-matrix bt2020nc --yuv-range limited --chroma-location left --scan progressive --dry-run
```

`--signal-json` 使用实际本地JSON的绝对路径；不要调用旧版安装，也不要静默回落到源码。

去掉 `--dry-run` 执行实际测量。参数不从成片标签或工程输出配置自动推断；标签不能替代明确的 HLG 显示峰值、gamma、黑位或 SDR 参考白。只接受工程内本地文件。RGB 成片用 `--pixel-family rgb`，不附 YCbCr 参数。默认量程策略 `reject`，检测越界即失败；只有显式 `--range-policy clip` 才截断到 [0,1] 并报告负值、超一及裁切分量数量。

可用 `--active-region X Y WIDTH HEIGHT` 限定画面区域；范围外仍验证整帧透明度与有限值，并统计整帧越界分量。只有全画布结果可标记 `full_canvas_measured=true`。目前每次测量完整视频流，不做帧率变换或源帧抽样。

## 测量边界

读取第一个视频流的原生像素格式、PTS 和时长；YCbCr 采用明确的矩阵/量程/逐行色度位置重建 RGB。保留该原生适配器的 Float32 代码值，再提升至 Float64 做传递函数及光量计算，不再量化为 RGB16。解码后 RGBA Float32 摘要与原生时钟摘要单独报告；原始文件 SHA 与实现文件在生命周期边界校验。

分别输出 MaxRGB 与 CIE Y 的最高像素、最高帧平均值、按原生帧时长加权平均值和最低 RGB 分量，禁止混称同一 MaxCLL 定义。所有帧时长必须明确为正；未知或零末帧时长拒绝，不根据平均 FPS 猜测。原生曝光之间的缺口和重叠分别计数；加权平均基于各帧声明曝光总和，不填补缺口或规范化重叠。`native_span_seconds` 与曝光总时长可能不同。

不写入 SEI，不修改成片、工程或素材；取消/异常不返回成功的部分峰值，解码进程与管道线程须关闭。无整片像素缓存，有界帧索引最多一百万帧；工作区估算上限 768 MiB，不代表进程 RSS 或设备显存峰值。

## 保留限制

- 此功能是依赖明确声明的数字成片光量检查，不是物理显示器实测、色彩校准或艺术验收。
- 不自动选择 MaxCLL/MaxFALL 母版约定，不实现动态 HDR、Dolby Vision、完整 ACES 或自然 HDR 监看。
- 只支持已有原生 RGB/YCbCr 像素适配；隔行图像、隐式旋转、自动背景、隐式色度语义不被当作已支持。
- YCbCr 重建可产生负值或超一；显式 clip 会改变测量结果，必须与计数一同展示。
- 当前已完成本地包、安装专项/边界/兼容与C60 PQ/HLG 4:2:0实测；公开alpha.3附件仍为旧版，不能当作CLI0.1.50下载。4K/长片/更广编解码与物理监看验收继续开发。

核验记录见 [本轮实测](../validation/编码后成片光量核验_2026-10-29.md)。原目标 G08 的其他要求继续保留。


[本地安装版跨编码实测](../validation/编码后成片安装与跨编码实测_2026-10-29.md) · [C60](CASES.md#c60-post-codec-hdr420)。
