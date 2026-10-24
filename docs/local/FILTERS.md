# 滤镜功能 README：500 套内置风格

[简体中文](FILTERS.md) · [繁體中文](FILTERS.zh-TW.md) · [English](FILTERS.en.md)

当前安装版为 **v0.1.0-alpha.3 / CLI 0.1.2 / 目录 2.0.0**。500 套均随包离线安装，Agent 可以检索、读取实际效果、预览并应用到片段或全局。原 100 套的 ID 和 LUT 字节保持兼容。


<!-- N002-GALLERY-START -->

## N002 母图：全部 500 套实际样例与客户选型

![Original and actual styles](../assets/looks-n002-20261024-r1/selection-board.jpg)

[All 500 supplied-image samples](FILTER_GALLERY.md) · [Interactive gallery](../assets/looks-n002-20261024-r1/index.html) · [Client Skill workflow](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md)

每套统一以用户提供的 1672×940 母图、强度 1.0 实际运行，提供原图、全尺寸无损图、小图与稳定 ID。Agent 可导出客户候选板和 JSON，再对目标素材重新预览选定强度，最后应用到明确片段或全局。原图与 LUT 各自权利分开记录。

<!-- N002-GALLERY-END -->

## 功能与使用逻辑

| # | 功能 | 实际行为 |
|---|---|---|
| P01 | 命名与编号 | 001–100 保留 sp-/t3-；101–500 使用 nt-/fl-；命令使用稳定 ID |
| P02 | 搜索 | 简体/繁体名称、英文、ID、简体/英文描述、许可及分类 |
| P03 | inspect | 每套的实际灰阶/肤色/RGB 作用、场景建议、试用强度、网格、作者、许可、锁定来源与哈希 |
| P04 | preview | 使用内置合成卡或本地 SDR 图片输出新 PNG；支持静态 0–1 强度，保护已有文件 |
| P05 | apply | 显式 --clip-id 或 --global；默认替换同作用域的内置预设，保留手工效果；--append 才叠加 |
| P06 | 事务与证据 | dry-run 不写文件；实际应用复制 LUT/许可/来源，登记台账、快照、幂等重试；修改过的项目资源拒绝覆盖 |
| P07 | 旧版兼容 | 识别 alpha.2 预设标记；精确匹配旧证据时保留原字节；项目包往返保留稳定 LUT ID 和资源许可 |
| P08 | 许可区分 | MIT 100、CC BY-SA 267、CC0 133；按每套许可复制署名、变更与再分发义务 |

使用顺序：**list 选候选 → inspect 读详情和许可 → preview 比较适合素材的强度 → dry-run 确认作用域 → apply → render → 解码核验**。

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk look list --query '黑白'
& $avk look list --query 'CC0-1.0'
& $avk look inspect --id fl-0000001-action-magenta-01
& $avk look preview --id fl-0000001-action-magenta-01 --output 'E:/video-work/magenta-preview.png' --strength 0.65
& $avk look apply --project 'E:/video-work/my-ad' --id fl-0000001-action-magenta-01 --global --strength 0.65 --dry-run
& $avk look apply --project 'E:/video-work/my-ad' --id fl-0000001-action-magenta-01 --global --strength 0.65
```

## 全部命名与详细说明

[500 套编号及实际作用总表](LOOK_PRESETS.md)。每套有原名、来源前缀、唯一 ID 和逐项说明；新名称带实测中灰偏向/明暗/跨度提示。

| 编号 | 逐项详情 |
|---|---|
| 001–100 | [保留的原始风格](look-profiles/001-100.md) |
| 101–200 | [新增风格与原始曲线变体](look-profiles/101-200.md) |
| 201–300 | [新增风格与原始曲线变体](look-profiles/201-300.md) |
| 301–400 | [新增胶片与社区创意](look-profiles/301-400.md) |
| 401–500 | [新增社区创意色彩](look-profiles/401-500.md) |

每份详情包含 7 个灰阶、3 个肤色和红绿蓝 3 个色块的输入/输出，Y′ 码值、中段跨度、使用建议、试用强度、注意点、作者/来源/许可、转换误差、LUT 摘要和真实 PNG/MP4。

**500 指不同的实际数值变换，含同系列上游曲线变体，不代表 500 个独立风格家族。** 上游的 +/− 后缀写进 ID；不将同一 LUT 的强度或格式副本计为新预设。全部通过共同 17³ 色网格签名与参考预览去重。

## 类别与来源

| 类别 | 数量 |
|---|---:|
| `cinema` | 39 |
| `creative` | 135 |
| `landscape` | 10 |
| `infrared` | 2 |
| `lomography` | 5 |
| `film-bw` | 37 |
| `film-negative` | 112 |
| `film-slide` | 41 |
| `instant-consumer` | 54 |
| `instant-pro` | 65 |

类别沿用来源分组，拍立得与负片组也含黑白变体，以每套实测说明为准。来源：Striped Purple 49、t3mujinpack 51、Natron 267、FreshLUTs 133。Natron 原始 Hald 转换为 33³；原有 CUBE 与新增 FreshLUTs CUBE 保留原网格。目录记录逐项采样误差和输入假设。FreshLUTs 按明确的上传者 Rec.709 标签选择，未将未知、Log 或 HLG 标签改判为 SDR；这不是独立相机校准。`fl-0000228-science-fiction-for-flog` 的标签为 Rec.709，但标题提到 FLog，输入域存在歧义，仅作为已准备 SDR 的实验创意比较，不作为已验证的 FLog 转换。

CC BY-SA LUT 及改编预览需要保留作者/来源、标明转换并按相同或兼容许可再分发。软件本体 MIT 不能代替资源许可。[完整通知与锁定来源](../releases/v0.1.0-alpha.3/THIRD_PARTY.md)。

## 实际输出与核验

![原视频与新增风格实际成片](../assets/look500-20261024-r1/motion-comparison.gif)

[原视频](../assets/look500-20261024-r1/original.mp4) · [500 套实际预览总览](../assets/look500-20261024-r1/contact-sheet.jpg) · [逐项 PNG/MP4](LOOK_PRESETS.md) · [当轮核验及失败修复](../validation/LOOK500_20261024.md)。

## 色彩与效果范围

LUT 只执行逐像素色彩映射；不产生颗粒、光晕、暗角、空间雾、美颜或 AI 特效。场景/强度是试片建议；合成色块不代表肤色保护或自然素材验收。Y′ 和跨度是编码 RGB 的对照量，不是曝光、线性亮度或主观评分。

`look apply` 用于默认 FFmpeg 的 SDR 管线；Float32/Log/HDR 显式拒绝。先按独立色彩契约转换素材再选风格。静态强度混合的是编码 RGB，不是线性光。

原有 46 个效果处理算子与 500 套风格是两种计数。用户仍可用 `lut register` 登记本地 `.cube/.3dl/.csp/.dat`；默认路径的部分强度以完整 3D CUBE 为准，非 CUBE 只记录有限元数据。显式 Float32 路径另支持完整 CUBE 的 1D/3D/1D shaper，必须声明信号、域与预算；两条路径能力不同。

## 自定义 LUT 与底层效果

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk effects list
& $avk effects inspect --name lut3d
& $avk lut register --help
& $avk lut register --project 'E:/video-work/my-project' --input 'E:/looks/cinematic.cube' --name 'My look'
```

登记后，把返回的 `lut_id` 加入时间线的 LUT 效果，再预览、渲染；单纯登记文件不会改变画面。自带素材需要补全实际许可和来源。底层动态强度使用编码 8-bit RGB 混合；核对 `effects inspect --name lut3d`、`effects.numeric_effect_automation` 和所选渲染路径。登记器部分历史限制字段只描述静态处理，不能据此推断所有路径的能力。

显式 `float32-native-v1` 读取完整 CUBE 的 1D、3D 或 shaper+3D，不读取 `.3dl/.csp/.dat`；默认 FFmpeg 路径不会自动获得 1D 支持。剪映专有滤镜包与任意第三方插件不属于标准 LUT 的兼容范围。

[历史 Float32/shaper 安装版实测](../validation/evidence/float-shaper-20261023-lab/installed-r1/verification.json) · [历史真实对照 GIF](../assets/float-shaper-20261023-installed-r1/formal-comparison.gif)。这些结果不计入本轮 500 套核验。

[安装与 Skill](INSTALLATION.md) · [新版使用手册](../releases/v0.1.0-alpha.3/USAGE.md) · [历史 100 套测量](LOOK_PRESET_DETAILS.md)。
