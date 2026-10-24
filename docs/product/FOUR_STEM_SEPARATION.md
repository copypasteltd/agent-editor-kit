# 独立四轨音源分离 / Independent four-source separation

[简体 README](../../README.md) · [繁體 README](../../README.zh-TW.md) · [English README](../../README.en.md) · [实测与失败](../validation/独立四轨音源分离实测_2026-10-25.md)

`audio separate-stems` 输出鼓 `drums`、贝斯 `bass`、其他乐器 `other`、人声 `vocals` 四条独立 HDemucs 估计。
`--apply` 将它们登记为四个音频资产，并新建四条可编辑音轨。原素材和原轨道保留。
现有 `audio separate` 仍提供双轨人声/残差伴奏；未配置模型时的 mid/side 仅是声道近似。

四軌命令會保留鼓、貝斯、其他樂器與人聲四個模型輸出，並可建立四條可編輯音軌。
既有雙軌人聲／殘差伴奏與 mid/side 命令繼續使用各自契約。

The four-source command retains all four neural estimates and can create four editable audio tracks.
The existing two-source vocal/residual-accompaniment and approximate mid/side command keeps its contract.

## 模型与服务依赖 / Dependencies

| 项目 / Item | 实际要求 / Requirement |
|---|---|
| 本地运行 / Application | CLI 0.1.6；一个统一 Skill 的固定安装包 |
| 四轨引擎 / Engine | `torchaudio-hdemucs-four-stem-local-v1`，显式项目登记 |
| 模型 / Checkpoint | 已有兼容 `torchaudio.models.hdemucs_high` 的 `.pt/.pth` tensor state dict；严格载入，不执行自定义模型代码 |
| 原生依赖 / Native runtime | 已有 Python `.exe`、NumPy、Torch、TorchAudio、FFmpeg/ffprobe；不创建虚拟环境，不启动 ComfyUI 服务 |
| CPU/GPU | `auto/cpu/cuda`，GPU index 0–31；`auto` 优先有至少 2048MiB 空闲显存的 NVIDIA GPU，仅预检不足时显式回退；推理错误/OOM 不回退 |
| 完整性 / Integrity | 模型、Python、证据与 8 个实现文件固定哈希；命令范围持读锁；原生 Python 模块版本/路径在 worker 响应中记录，完整操作系统与 Python 依赖闭包仍未打包 |
| 权利 / Rights | 四条派生轨均依赖源素材与模型台账；登记成功不授予模型/声音/音乐商业许可 |

模型架构、固定四源及 MUSDB-HQ 训练来源可核对 [TorchAudio 官方模型说明](https://docs.pytorch.org/audio/stable/generated/torchaudio.pipelines.HDEMUCS_HIGH_MUSDB.html)。
当前本机实验权重来自官方已有文件，334,697,255 bytes，SHA-256
`85ce4420e0852344b816487b4c4bb821bd406376b93bf684b2b76aa56404c46a`。
其模型权利仍为 **unverified**；权重、原生 Torch 环境和实验音频不随小型 Skill kit 再分发。
代码许可、训练数据许可、模型许可和用户输入许可分别记录。

## 使用流程 / Workflow

以下变量指向已存在的本地文件。模型路径、Python 环境和许可证据由实际安装提供；缺少时报告依赖缺口，不下载或回退开发源码。

The variables below must name existing local files. Supply the native runtime, compatible weights and actual license evidence explicitly.

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
$aekProject = 'E:/video-work/four-stems'
$aekModel = 'E:/models/hdemucs_high_musdbhq_only.pt'
$aekNativePython = 'E:/native-torch/python.exe'
$aekEvidence = 'E:/models/hdemucs-evidence.json'
& $avk version
& $avk capabilities
& $avk project init $aekProject
& $avk media ingest --project $aekProject --input 'E:/media/music.wav' --asset-id music
& $avk audio adapter register --project $aekProject --adapter-id music_four --engine torchaudio-hdemucs-four-stem-local-v1 --model-path $aekModel --executable $aekNativePython --evidence $aekEvidence --device auto --segment-seconds 4 --overlap 0.25
& $avk audio adapter inspect --project $aekProject --adapter-id music_four
& $avk audio separate-stems --project $aekProject --asset-id music --adapter-id music_four --prefix edit --apply --dry-run
& $avk audio separate-stems --project $aekProject --asset-id music --adapter-id music_four --prefix edit --apply --device auto --timeout-seconds 600
& $avk validate --project $aekProject
& $avk rights check --project $aekProject
```

结果中的 `data.assets`、`data.generated_tracks`、`data.separation.stems` 给出实际 ID、WAV 路径和样本数。
`data.separation.worker` 给出实际设备、模型前向次数、版本、GPU 峰值和逐轨峰值；
`device_selection` 保留预检/回退原因。重复执行请换 `--prefix`；相同幂等键可重放已完成响应。
使用 `--cancel-file <local-marker>` 时，创建该标记文件取消任务；取消/超时终止本任务 worker，清理本次临时音频及未完成派生文件。
检查完整性和磁盘 I/O 的耗时也计入总任务预算，取消响应延迟仍受阶段边界影响。

Inspect the returned IDs and artifacts. The response records actual inference/device/memory and the preflight selection.
Use a new prefix for another separation, or replay a completed request with its idempotency key.
Create the explicit cancellation marker to cancel a running task. Cancellation does not stop unrelated GPU work.

## 信号与编辑契约 / Signal and editing contract

| 编号 | 契约 / Contract | 使用影响 / Implication |
|---|---|---|
| A01 | 模型工作格式固定 44,100Hz、双声道 float32 | 输入可来自视频或音频；最终 WAV 可显式重采样到命令支持的采样率，按确定样本数输出 |
| A02 | 分段 1–20 秒、重叠 0–0.75、共享三角 overlap/add | 工作内存按分段与模型增长；源、四轨和权重使用磁盘映射；不等于已完成全部长任务资源验收 |
| A03 | 每轨保存模型自己的预测，共享归一化与 DC/4 恢复 | 不用残差伪造鼓或贝斯；不独立归一化、不自动限幅；峰值可超过 1，混音前复核 |
| A04 | 原始四轨和不做混合一致性投影 | `raw_sum_max_abs_error` / `raw_sum_rms_error` 如实记录；和原音不完全相同不被静默修成其他轨 |
| A05 | 单次最长 1800 秒、总超时 0–7200 秒的有限正数 | 磁盘预检估算十份 PCM 加 256MiB 余量；估算不是并发磁盘预约；长片/并发仍是 G32/G33 开放项 |
| A06 | 四条新音轨均可独立静音、音量自动化、裁切和包迁移 | `--apply` 后检查原音轨是否同时发声，明确静音/选择需要的轨；不静默替换原工程内容 |
| A07 | 独占创建新输出、事务/快照、派生权利 | 不覆盖已有 ID/文件；编码或元数据提交失败清理本次四轨；模型适配器需在新的安装位置显式重登记 |

## 实测边界 / Acceptance limits

详见[完整实测](../validation/独立四轨音源分离实测_2026-10-25.md)：契约测试与实际模型推理分开；
固定受控混音与另一段 CC0 音乐分开；CPU/GPU、开发源、安装版和真实统一 Skill 调用分开。
模型输出不自动证明自然乐器/歌声分离质量，SI-SDR 改善与泄漏、伪影、瞬态和主观听感分别记录。
本轮不关闭 G17，也不关闭历史 G15 对齐、G16 极短音频窗口及 G37 模型权利差距。

Contract tests, real model execution and human acceptance are separate. Controlled fixtures and a CC0 music excerpt do not establish general natural-music quality, dereverberation or listening acceptance. All existing goal gaps retain their acceptance conditions.
