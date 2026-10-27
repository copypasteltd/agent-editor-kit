# Float32 全局与区间调整层

CLI0.1.39 的根区间支持[真实高光Bloom/Halation](HIGHLIGHT_GLOW.md)，保持区间局部原作者时钟和全轨合成后只应用一次。解析光学及高光扩散可使用实际GPU；其他调整算子保留既有CPU实现。


agent editor kit CLI 0.1.25 / `v0.1.0-alpha.4-local.23`，统一入口
`$agent-ffmpeg-local-editor`。本次补上显式浮点渲染原先拒绝
`settings.adjustments` 的缺口，复用已有浮点效果、关键帧和 LUT 实现。

## 处理位置与时间

所有视频、文字及字幕轨先完成合成，再依声明顺序执行调整层，最后转换到交付
信号。全局设置只在本次选中的根序列执行一次；递归的子画布不重复调色。
直接选择子序列预览或输出时，该子序列成为选中的根。

`start_tick` 包含起点，`start_tick + duration_tick` 不包含终点。
效果取样时间为选中序列的精确 tick 减去层起点，不重吸附到帧网格；较短序列
只截取覆盖范围，不压缩作者声明的关键帧时长。未声明时长的层覆盖至所选序列
末尾。项目校验仍要求作者区间位于工程最长序列内；有明确时长时关键帧不能越界。
现有 hold、linear、ease_in、ease_out、ease_in_out、bezier 规则保持。

## Agent 使用流程

先建立显式 `float32-native-v1` 工程，完整声明输入、线性工作域、输出信号和
本地资产。将下例数组写入 `project.json` 的 `settings.adjustments`；这是可编辑
工程字段，不新增一个独立 CLI 命令。90000 ticks/s 下，第二层覆盖第1至第4秒。

```json
[
  {"id":"base-grade","effects":[{"type":"exposure","parameters":{"amount":-0.1}}]},
  {"id":"darken-window","start_tick":90000,"duration_tick":270000,"effects":[
    {"type":"exposure","parameters":{"amount":0},"keyframes":[
      {"property":"amount","keyframes":[
        {"at_tick":0,"value":0,"interpolation":"ease_in_out"},
        {"at_tick":270000,"value":-0.6,"interpolation":"linear"}
      ]}
    ]}
  ]}
]
```

使用[统一 Skill 启动脚本](SKILLS.md)对应的 `$avk`：

```powershell
& $avk capabilities
& $avk validate --project $project
& $avk preview frame --project $project --frame 24 --height 540
& $avk preview range --project $project --start-frame 0 --end-frame 48 --height 540
& $avk render --project $project --output $output --hardware-encode off --hardware-decode off
& $avk quality check --project $project --input $output
& $avk convert export --project $project --target-format package --output $package
```

曝光、LUT、曲线、色阶、平衡、选区 HSL、tone、Gaussian、spatial、sharpen、
keyer 复用既有编译器支持集与参数契约。不同效果仍需其要求的显式信号、范围与
alpha 语义；不能把默认 FFmpeg 支持的所有效果直接视为浮点实现。未知的启用
效果报错，禁用层/效果不执行。上限128层、每链128效果、总4096效果、JSON 8MiB。

## 本地 LUT、GPU 与交付

LUT 采用工程内路径或已登记的本地 ID。明确填写 `input_signal` 与
`output_signal`，与 LUT 实际设计域一致。渲染将 CUBE 与库清单的 SHA/大小纳入
依赖，并在生成至发布期间持有原生只读锁；变更报错。项目包导出会保留原字节并
改写可移植路径。复制文件后重新登记权利证据。

调整层运行在 CPU 的 Float32 表面上，可与[实际 GPU 投影/字色合成](FLOAT_GPU.md)
组合。此处没有新的 GPU 调色或音频处理。单个效果的工作区配额不等于进程峰值
RSS，也不代表 HDR/ICC 或实时渲染验收。负值及超一 RGB 需要有效交付策略；
不能通过偷偷截断宣称结果正确。

结果的 `delivery.pixel_pipeline.timeline.adjustments` 保存所选序列、层参数、
覆盖区间、执行帧数和层应用次数；依赖位于 `pixel_pipeline.artifacts`。
帧/范围预览、正式渲染、队列和恢复使用同一宿主。原始项目、音轨与权利记录保持。

## 实测与样例

源测试、已安装测试、真实统一 Skill 交付与故障记录保存在
[本轮证据目录](../validation/evidence/float-adjustments-20261026-r1/)。
最终结果以其中已完成的 `verification.json` 为准。失败尝试保留。
自然素材观感、连续播放、人工听审、完整 HDR 及完整剪映等价继续独立验收。

[实际成片与可编辑包](CASES.md#c35-float-adjustments) · [本轮安装/测试/迁移结果](../validation/Float32调整层实测_2026-10-26.md)

![统一Skill实际调整层成片 / 静音GIF](../assets/float-adjustments-20261026-r1/native-text.gif)
