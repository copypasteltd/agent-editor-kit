# 线性 Float32 GPU 执行层

CLI0.1.38 当前新增[眩光、漏光和色差](OPTICAL_EFFECTS.md)实际GPU运算，沿用原有粒子与
投影/合成路径。命名主探测为9次，其中3次为真实光学算子；此前65536级和次正规alpha
校验继续保留。编辑帧的 `operations.optics` 与探测数分开记录。光学算子用binary64，
粒子保持原Float32栅格化；下文历史范围中“效果由CPU处理”排除这些后续原生增量。

CLI0.1.36 保留本页算子、精度与选择方式，将高频控制文件改为任务自有的本机管道。
像素内核和共享内存布局保持原字节；详见[GPU调度、清理与实测](GPU_DISPATCH.md)。
下文CLI0.1.24为首次接入的历史范围，当前安装与摘要见[本地交付](COMMUNITY_LOCAL_DELIVERY.md)。

`agent editor kit` CLI0.1.24 为显式 `float32-native-v1` 工程连接原生 Windows
OpenCL 执行层。它面向渲染与预览任务，不启动常驻模型服务，不下载依赖。
默认仍为 CPU；指定的 GPU 必须支持 IEEE binary64。完整剪映等价目标保持开放。

## 配置与使用

在既有工程 `settings` 中设置以下对象；源素材、线性工作信号、输出信号和字体
仍需按[浮点文字说明](FLOAT_TEXT.md)明确登记。预览读取工程中的同一设置。

```json
"projection_acceleration": {
  "mode": "require",
  "device": "0.0",
  "max_working_bytes": 1073741824,
  "probe_timeout_seconds": 30
}
```

通过统一 `$agent-ffmpeg-local-editor` 调用已安装 CLI；也可为单次渲染覆盖设置：

```powershell
& $avk validate --project $project
& $avk preview frame --project $project --frame 4 --height 540
& $avk render --project $project --output $output --projection-acceleration require --projection-device 0.0 --projection-memory-mib 1024 --hardware-encode off --hardware-decode off
& $avk quality check --project $project --input $output
```

`$avk` 是[本地安装流程](COMMUNITY_LOCAL_DELIVERY.md)中的已安装启动脚本。
`0.0` 表示 OpenCL 平台/设备索引；不能据此推断 CUDA 或 NVIDIA 的编号。
`sequence_sampling.method` 必须为 `bilinear`，硬件编码/解码保持 `off`。
默认 FFmpeg 图投影和此独立浮点执行层是两个后端，各自保留实际设备与精度证据。

## 算子与精度

GPU 执行预乘 alpha 的双线性仿射采样、普通 source-over、文字框/阴影/描边/填充的
有序颜色组件、完整段落叠加和逐词二值选择。字形栅格、crop/mask、效果、转场、
其他混合模式、信号转换、音频和编码继续由 CPU 执行；回执明确列出 `GPU_scope`
与 `CPU_scope`。此浮点后端的 `require` 要求所声明的 GPU 算子实际执行，
不表示所有编辑算子都迁往 GPU。

内核使用 binary64 中间运算与明确的 Float32 舍入边界，禁用 fast math 和浮点
乘加收缩。媒体表面始终是直通 Float32 RGBA；字形覆盖率仍为原生 8bit。
颜色未经过 GPU 8bit 媒体转换。保留透明外缘、负值/超一 RGB、完整段落选择、
原作者时钟、组件顺序和动画 alpha 的应用位置；不改变字幕为输出帧网格时间。

每次执行先在任务独占的 GPU 子进程中比较 CPU 独立公式：65,536 个原生灰阶值、
透明/扩展 RGB、亚像素仿射、文字组件与二值选择，绝对误差上限 `3e-7`。
探测次数与编辑帧的实际算子次数分别记录，不能用探测成功代替实际成片。

## 生命周期、预算与错误

一个渲染/预览任务拥有一个有限生命周期的进程、三个可复用设备缓冲区及三个命名
共享主机段。JSON 控制消息最多128KiB，仅同任务 nonce 和连续序号可使用。
GPU 不读取任意媒体路径；像素通过共享段传输，子进程只加载明确的现有产品和 NumPy。
执行实现、数值运行时、Python 与 OpenCL loader 纳入本次渲染的依赖摘要/持锁记录。

配额分别限制设备缓冲池和共享主机缓冲池。4K 三个完整 Float32 设备缓冲区
共398,131,200字节，两个主机表面与逐词掩码约273,715,200字节，另加小控制开销。
源缓存、文字 LRU 和 CPU 工作区另有上限；这些估算不等于合并峰值 RSS，
也没有预留其他任务正在使用的显存。设备分配失败如实报错，不停止其他 GPU 任务。

`off` 不创建 GPU 进程。`prefer` 仅允许启动前设备、精度或预算准入失败时记录
`cpu_fallback`。执行中失败、超时、取消均失败并清理本任务的进程和共享句柄，
不会悄悄改为 CPU 成功。`require` 在探测失败或没有实际适用算子时失败。
`render --dry-run` 只生成计划，不创建 GPU context、worker 或共享段。

渲染结果的 `data.projection_acceleration` 及 `cache/float-gpu/*/receipt.json`
保留实际设备/驱动、内核 SHA、执行文件 SHA、精度误差、算子数、PID、退出码和
句柄关闭状态。队列和恢复沿用原始设置/指纹；不同设备或策略须创建新任务。
GPU 任务继续拒绝 `queue run --reuse-identical`，保证各任务具备自己的实测证据。

## 验证记录

本轮安装、完整成片、故障修复、性能比较及验收边界统一保存在
[本轮证据目录](../validation/evidence/float-gpu-20261026-r1/)。
每次运行使用独立目录，失败记录同样保留。真实安装与案例完成后由对应验证摘要
给出结论；连续播放、人工听音、自然内容质量、实时4K和长片另行验收。

OpenCL API 依据 [Khronos 官方规范](https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_API.html)，
本实现仅使用原生 context、queue、program、buffer 和 kernel 的 OpenCL1.2 API。
