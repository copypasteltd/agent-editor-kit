# 原生采集 CLI / Native capture

面向 Agent 的窗口、屏幕/区域、DirectShow 摄像头与麦克风采集。它生成可导入和继续编辑的本地素材，使用原生 FFmpeg，不需要 Docker、WSL、虚拟环境、浏览器或常驻 GUI 服务。新增于 CLI 0.1.4；安装与证据见[本轮交付](../validation/补齐实施首批实测_2026-10-25.md)。

Native Windows CLI capture produces local editable assets through FFmpeg. CLI 0.1.4 adds finite window/desktop/region, explicit camera and explicit microphone recording. No browser, virtualized environment or permanent GUI service is required. See the [delivery and evidence](../validation/补齐实施首批实测_2026-10-25.md).

## 使用流程 / Workflow

先按[统一 Skill 安装流程](COMMUNITY_LOCAL_DELIVERY.md)配置当前本地版本。`$avk` 为唯一 Skill 的 `scripts/run.ps1`。先读取帮助和设备清单，再选择来源与有限时长。

Use the pinned unified Skill launcher. Read help and list available devices before choosing the source and finite duration.

```powershell
& $avk capture devices
& $avk capture record --help
& $avk capture record --project './workspace/demo' --kind window --window-title 'Your application title' --duration-seconds 5 --encoder auto --asset-id window-take-01 --dry-run
& $avk capture record --project './workspace/demo' --kind window --window-title 'Your application title' --duration-seconds 5 --encoder auto --asset-id window-take-01
& $avk capture record --project './workspace/demo' --kind screen --width 1280 --height 720 --offset-x 0 --offset-y 0 --fps 30 --duration-seconds 5 --asset-id screen-take-01
```

纯录音使用 `--kind microphone --microphone-id <capture devices 返回的 audio ID>`；相机使用 `--kind camera --camera-id <video ID>`。视频录制如需声音，另外显式提供 `--microphone-id`。设备 ID 绑定类型和当前硬件路径，不从同名设备中静默挑选。相机可请求 `--width / --height / --fps`，实际模式取决于设备。未请求麦克风时，视频输出没有音频轨。

For audio-only recording use `--kind microphone --microphone-id <audio ID from capture devices>`; for a camera use `--kind camera --camera-id <video ID>`. Video audio requires an explicit microphone ID. IDs bind device type and hardware path; ambiguous or unavailable IDs fail. Camera dimensions and FPS depend on supported device modes. A video request without a microphone produces no audio stream.

## 参数与输出 / Parameters and output

| 参数 / Parameter | 行为 / Behavior |
|---|---|
| `--duration-seconds` | 必填，0.25–3600 秒；采集结束并完成封装后才登记 / Required, finite 0.25–3600 seconds |
| `--kind window` | 必须指定精确窗口标题；目标不存在则失败 / Explicit exact window title; unavailable windows fail |
| `--kind screen` | 桌面或指定区域；偏移允许负值以选择其他显示器 / Desktop or region; signed monitor coordinates |
| `--encoder auto` | 有 NVIDIA GPU 时先尝试 NVENC，失败显式记录并用新临时文件重试 CPU / Try NVENC on NVIDIA, record failure and CPU fallback |
| `--encoder h264_nvenc` | 严格 GPU 编码；失败不回落 / Strict GPU encoding |
| `--encoder libx264` | 明确 CPU 编码 / Explicit CPU encoding |
| `--cancel-file` | 本地取消标记；支持启动前和录制中取消 / Local pre-start or in-flight cancellation |
| `--dry-run` | 返回计划与命令，不启动录制、不创建媒体 / Plan only; no recording or media creation |
| 输出 / Output | `assets/captures/<asset-id>/capture.mp4` 或 `capture.wav`、`SOURCE.json`、Rights Ledger 与操作记录 |

输出先在项目 `cache/capture/` 内生成；检查时长、请求的流和完整解码后再登记。现有 ID/目录不会覆盖。失败和取消保留本次缓存诊断，工程不登记半成品。采集证明只说明来源和执行过程，内容权利默认仍为未核验。

Capture writes a new cache file, checks duration/streams and decodes the entire output before registering it. Existing assets are preserved. Failed or cancelled runs retain diagnostics without registering incomplete media. Capture provenance does not grant rights to the recorded content.

## 实际案例与边界 / Actual example and limits

![GPU 录制样例 / Actual GPU capture](../assets/native-capture-20261025-r1/preview.gif)

[原始 CPU MP4](../assets/native-capture-20261025-r1/cpu-window.mp4) · [原始 GPU MP4](../assets/native-capture-20261025-r1/gpu-window.mp4) · [生成与来源](../assets/native-capture-20261025-r1/SOURCE.md) · [媒体摘要](../assets/native-capture-20261025-r1/verification.json)

这是测试程序自身显示的 FFmpeg 动态测试图，CPU 与 GPU 各 2 秒 / 30 帧；没有录制其他应用、麦克风或摄像头。它验证真实采集及编码，不是新产品 GUI。静态查看与自动解码不代表连续人工观看或音画同步通过。当前主机枚举到音频设备，没有视频设备；摄像头、麦克风实际录制、联合音画同步、设备拔出/权限变化和长时间录制仍待验收，G30 继续开放。

The test records this script's own animated FFmpeg test pattern, two seconds/30 frames per CPU and GPU output. No unrelated application, microphone or camera was captured. This proves native capture/encoding, not a product GUI or human playback acceptance. The host enumerated audio devices and no camera. Actual microphone/camera recording, combined AV sync, device loss/permissions and long recordings remain unaccepted; G30 stays open.
