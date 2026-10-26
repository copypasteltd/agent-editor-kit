# GPU 操作调度 / GPU operation dispatch

CLI **0.1.36** 将原生 Float32 GPU 执行层的高频控制消息改为任务自有的本机二进制管道。
粒子、投影、透明合成和文字算子的像素继续通过原有三个共享内存段传输。
它修复每个小算子都写盘、fsync、轮询控制文件产生的等待；GPU 像素内核保持原字节。

这是 G32 性能工作的一个已实现部分。完整剪映等价、实时预览、4K 长片性能和其他设备
仍按原始验收条件推进；本次对照工程为自行构建的 960×360 六格粒子诊断场景。

## Agent 使用流程

继续使用唯一入口 `$agent-ffmpeg-local-editor`。无新增服务或命令，离线安装版自行选择新通道。
在已有显式 `float32-native-v1` 工程中保留原始工作/输出信号；预览、队列使用工程中同一设置。

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk validate --project $project
& $avk render --project $project --output $output `
  --projection-acceleration require --projection-device 0.0 `
  --hardware-encode off --hardware-decode off
& $avk quality check --project $project --input $output
```

`$project` 和 `$output` 为已确认的实际工程及输出路径。`0.0` 是 OpenCL 平台/设备索引。
普通工程不因升级而自动切换到 GPU。`off|prefer|require` 的行为与
[Float32 GPU 合约](FLOAT_GPU.md)一致：`prefer` 仅允许探测前失败回退，实际执行失败必须报错。
具体源参数、seed、裁切/倒放及包导出见[可编辑粒子](PROCEDURAL_PARTICLES.md)。

## 协议、持久化与清理

`owned-inherited-binary-pipes-v1` 使用当前进程创建的子进程 stdin/stdout 原生管道。
帧头为四字节大端正文长度，正文为有限 UTF-8 JSON 对象，最多 **128KiB**。
拒绝截断、非对象、重复键、非有限数值和超长消息。每条消息继续核对任务 nonce 与连续序号。
没有 TCP/HTTP、监听端口、pickle、独立消息服务或虚拟化环境。

父进程各有一个读/写辅助线程、各一个容量为一的队列。主调度线程等待可立即唤醒的结果，
每次最多等待20ms以检查取消；满管道写入不会阻塞主线程。渲染完成或失败时先等待/停止
所属子进程，再回收辅助线程、管道流和共享内存句柄。父进程关闭管道后，空闲 worker 收到 EOF 即退出。
控制消息不写 `request.json` / `response.json`；一次启动的 `init.json`、实际回执以及
工程快照、manifest、队列状态仍按原有原子替换和 fsync 规则持久化。

查看 `data.projection_acceleration.control` 及对应 `cache/float-gpu/*/receipt.json`：

| 字段 | 含义 |
|---|---|
| `protocol` | 实际启用的控制协议 |
| `sent_packets` / `received_packets` | 已完成写入/读取的包数；接收数包含探测回执 |
| `sent_bytes` / `received_bytes` | 包含四字节头的实际控制字节数 |
| `queue_capacity_each` / `max_packet_bytes` | 队列与每包正文的边界 |
| `threads_closed` / `streams_closed` | 清理后的实际状态 |
| `transient_control_persisted` | false；只指瞬时操作包，工程/验收记录继续持久化 |

`worker_closed`、`shared_handles_closed`、实际设备、数值探测和每类 GPU 算子数继续保留。
新控制模块加入执行摘要、渲染运行时依赖和粒子输入指纹；不借优化跳过任何实现校验。
控制边界不代表总进程 RSS 或全设备 VRAM 已受限。

## 可复现对照

基准通过实际注册的 Skill 调用离线安装版，原版 CLI0.1.35 与新版使用同一个
[C45可编辑包](../assets/procedural-particles-20261027-r3/editable-particle-grid.aevpkg.zip)。
验证素材包、作者图和 FFmpeg/ffprobe SHA 相同，再实际渲染全部48帧、解码每帧10bit画面及完整
双声道 Float32 PCM。对应脚本为 `scripts/benchmark_float_gpu_dispatch_20261027.py`；
`--baseline baseline-r1` 对照逐帧哈希与全部音频字节。

高频调用另由 `scripts/profile_float_gpu_dispatch_20261027.py` 记录32次8×8算子、三帧作者图、
CPU/GPU独立数值对照和函数耗时。每次使用新目录保留原始命令、输出和失败；源代码探测与最终
安装版测量分别标明，具体结果见[本轮验收](../validation/GPU管道调度实测_2026-10-27.md)。

原有[C45媒体与GIF](CASES.md#c45-procedural-particles)继续展示同一画面；新增对照应证明输出相等，
不把相同画面的重复GIF当成新增功能。声音为该合成诊断场景的静音轨，未作自然听感验收。

## English contract

CLI0.1.36 uses inherited native stdin/stdout pipes for per-operation control, while pixels retain the
same three shared-memory segments and unchanged OpenCL kernels. Four-byte length-prefixed UTF-8 JSON
objects are bounded to128KiB; nonce/sequence validation, cancellation, timeouts and owned-worker cleanup
remain active. Dedicated bounded reader/writer queues keep OS backpressure off the cancellation thread.
Project snapshots, manifests, queues and durable receipts keep their existing atomic fsync behavior.
Use the same explicit native Float32 project and GPU policy, then inspect actual operator and cleanup
receipts. The matched installed benchmark checks all48 decoded10bit frames and complete stereo PCM;
one diagnostic scene does not establish realtime,4K,long-form,multivendor or full CapCut acceptance.
