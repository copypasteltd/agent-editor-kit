# 原生 GPU 裁切与投影 / Native GPU projection

CLI **0.1.20 / alpha.4-local.18**，唯一入口 **`$agent-ffmpeg-local-editor`**，17 个内部模块。动态裁切、固定画布仿射运镜、子序列原生画布的双线性/面积投影可显式使用现有 GPU；默认仍为 CPU。字幕、混合及其他特效按原 CPU 流程运行，配音/翻译和硬件编解码分别选择设备。

Native OpenCL inverse samplers are available for animated crop, affine camera keys and native child-canvas projection. The default is CPU. Other effects/compositing, GPU speech/translation and hardware encoding have separate execution paths and policies.

原生 GPU 裁切、仿射運鏡及子畫布投影均須明確選擇策略；預設 CPU。請讀取實際裝置、節點、探測與失敗紀錄，不能把計畫或 NVENC 編碼當成 GPU 合成已執行。

[固定安装与摘要 / Install](../releases/CLI_0.1.20_LOCAL.md) · [Skill详情](SKILLS.md) · [全部功能](CAPABILITIES.md) · [实现契约](../specs/OpenCL原生投影实现契约_20261026.md) · [实际核验](../validation/OpenCL原生投影实测_2026-10-26.md)

## 使用流程 / Workflow

先在已安装的唯一 Skill 中检查版本和能力；使用已存在的本地素材创作普通可编辑工程。以下完整案例导入到新目录，包含自制图卡、动态 crop、480×270 原生子画布、反向时钟与 `arc_push` 关键帧，输出384×216/30fps/4秒。

Use the existing local installation, verify capabilities, import the editable case into a new directory, validate and render. Review actual output and retained diagnostics before delivery.

```powershell
$aekSource = 'E:/dev/sandbox/AI广告剪辑'
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk capabilities
$aekProject = Join-Path $aekSource 'workspace/opencl-client'
$aekCase = Join-Path $aekSource 'docs/assets/opencl-projection-20261026-r1/editable-projection.aevpkg.zip'
& $avk convert import --input $aekCase --output $aekProject
& $avk validate --project $aekProject
& $avk render --project $aekProject --sequence-id projection_demo --output (Join-Path $aekProject 'renders/client.mp4') --projection-acceleration prefer --projection-device 0.0 --projection-memory-mib 1024 --sequence-sampling area --sequence-memory-mib 1024 --hardware-encode off
& $avk quality check --project $aekProject --input (Join-Path $aekProject 'renders/client.mp4') --sequence-id projection_demo --projection-acceleration prefer --sequence-sampling area
```

`0.0` 是 OpenCL 平台0/设备0，不保证所有机器都是同一显卡。render 前会查询现有本地 ICD，检查 GPU、双精度、纹理上限、系数64位传输和实际 gbrap8/Float32 上传采样回读。缺依赖时明确回退或报错，不安装驱动、下载组件或启动服务。

Platform/device indexes are machine specific. Each actual GPU render probes the selected existing ICD and checks binary64 coefficients and real texture round trips. There are no implicit driver/model downloads or background services.

## 策略、工程与队列 / Policy and jobs

| Policy | 实际处理 / Behavior |
|---|---|
| `off` | 默认 CPU 投影；existing CPU pixels/precision |
| `prefer` | 支持且在配额内的节点使用 GPU；执行前设备/格式不支持或节点语义不适用时保留 CPU 并记录原因 |
| `require` | 所有请求的投影必须适用；无适用算子、设备/精度不可用、节点不支持或配额不足时失败 |

运行中 GPU 错误、超时或取消均为失败，不自动改成 CPU 成片，也不作为 NVENC 错误重试。`prefer` 成功时仍须检查实际节点和 `cpu_fallback`，不能仅凭退出码声称 GPU 已工作。`--dry-run` 只生成计划，不创建 GPU 上下文或 shader 文件。

Runtime GPU failure, timeout and cancellation fail the render. Prefer-mode preflight fallback is explicit. A plan is not evidence of GPU execution.

项目可持久化以下配置；命令行仅覆盖当前输出。此配置和 `acceleration` 编解码、`sequence_sampling` 准入分别独立：

```json
{
  "projection_acceleration": {
    "mode": "prefer",
    "device": "0.0",
    "max_working_bytes": 1073741824,
    "probe_timeout_seconds": 30
  }
}
```

放在 `project.json` 的 `settings` 中。单个队列作业 JSON 使用下列平面字段，经 `queue enqueue --input` 加入；`queue run` 沿用其策略：

```json
{
  "job_id": "gpu-delivery",
  "sequence_id": "projection_demo",
  "output": "renders/queued.mkv",
  "container": "mkv",
  "video_codec": "libx264",
  "pixel_format": "yuv444p",
  "audio_codec": "pcm_f32le",
  "crf": 0,
  "hardware_encode": "off",
  "projection_acceleration": "require",
  "projection_device": "0.0",
  "projection_memory_mib": 1024,
  "sequence_sampling": "area",
  "sequence_memory_mib": 1024
}
```

从失败操作恢复时，以 `render --resume OPERATION_ID` 使用原保存设置；恢复要求输入及输出设置指纹保持，包括设备策略。改设备或输出设置需新建 render，不能改写旧操作。恢复是重新渲染，并非从 GPU 中间帧续算。显式 GPU 投影作业拒绝 `queue run --reuse-identical`，保证逐作业设备探测不被成片复用绕过。

For hardware encoding, `--hardware-encode` accepts `off|prefer|require`, while `--hardware-encoder` selects `auto|nvenc|qsv|amf|mf`. Encoding also needs an explicit supported video bitrate. Earlier `--hardware-encode auto` documentation examples were invalid; use the valid policy above. Voice/translation have their separate `auto` model-device setting.

## 核验与边界 / Evidence and limits

render 响应和 manifest 中的 `projection_acceleration` 包含实际 GPU、驱动、逐节点使用/拒绝原因、工作栅格估算、shader SHA-256、探测和完整已完成日志。报告保存到工程 `renders/diagnostics/projection_OPERATION_ID/report.json`；原生执行器的中断错误另保留诊断尾部。发布前重新核验输入及 shader 字节，失败不发布临时输出。

源帧分流的小系数图使用相同 PTS，原 AVExpr 计算作者时钟/Bezier/hold；GPU 不重写关键帧数学。binary64 系数拆为三段可精确存入 Float32 的整数及指数。面积前缀保留逐行、再逐列的双精度求和顺序。禁用 fast-math/FMA 收缩，保留半像素、原预乘采样和反预乘。

`projection-memory-mib` 为累计投影工作栅格准入，包括源/目标帧槽、系数和面积前缀临时纹理；不是整个进程 RAM 或总 VRAM 保证。`sequence-memory-mib` 是另一个序列栅格限制。默认各1024MiB；大画幅可能需显式更大预算，不能静默扩额或降低精度。

当前仅有本机 RTX3060 的原生设备实测，不能外推 AMD/Intel、其他驱动或其他系统。独立线性光 `settings.pixel_pipeline`、像素/有状态表达式不接入该 GPU 路径。面积 footprint 仍为源轴矩形，未实现旋转多边形积分。默认8位编码RGB合成不等于全浮点/HDR流水线。

Only the recorded RTX3060/native Windows configuration is device-tested here. Independent linear-light float rendering and pixel/stateful expressions are unsupported by this backend. The area footprint remains a source-axis rectangle. This does not establish all-vendor compatibility, all-effect GPU rendering, real-time 4K, long-form reliability or full CapCut parity.

[原图](../assets/opencl-projection-20261026-r1/original.png) · [实际MP4](../assets/opencl-projection-20261026-r1/projection.mp4) · [可编辑工程包](../assets/opencl-projection-20261026-r1/editable-projection.aevpkg.zip) · [媒体摘要](../assets/opencl-projection-20261026-r1/media-manifest.json)

![Actual installed OpenCL composition / silent](../assets/opencl-projection-20261026-r1/projection.gif)

实际预览静音。自动完整解码、像素/PCM对照、抽帧目检、连续播放与人类听审分别记录；保留失败和原 G01–G38 关闭条件。

当前CLI0.1.24另有[独立原生Float32 GPU执行层](FLOAT_GPU.md)：明确GPU策略、字色/普通叠加/仿射/逐词选择，保留CPU字形和其他算子；上文历史版本边界不追改。
