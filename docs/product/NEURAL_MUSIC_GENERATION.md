# 原生 GPU 神经配乐（CLI64）

开发中的 ACE-Step 1.5 Turbo 接入通过现有原生 ComfyUI 核心直接执行，不启动 GUI、HTTP 服务或共享队列。正式注册入口目前仍为 CLI0.1.63；本页的新增命令须由 CLI0.1.64 执行。真实推理、安装与正式 Skill 的验收状态分别记录，不能从接口或单元测试通过推断后续步骤已经完成。

目前 local62 已独立离线构建并安装，[288应用模块与源码精确一致](../validation/evidence/music-generation-20261030-r1/candidate-r1/verification.json)；[94文件统一Skill候选](../validation/evidence/music-generation-20261030-r1/skill-stage-r1/verification.json)的正文与实际PowerShell version／help通过，但尚未正式注册。[源码首个真实GPU生成](../validation/evidence/music-generation-20261030-r1/actual-piano4/verification.json)和[候选PowerShell入口的安装版工程包回放](../validation/evidence/music-generation-20261030-r1/installed-package-stage1/verification.json)已通过。此前1800秒预算超时的[失败记录](../validation/evidence/music-generation-20261030-r1/actual-piano3/verification.json)保留。独立安装版的新生成和完整回归尚待验收。完整开发与验收状态见[本轮记录](../validation/CLI64原生神经配乐_2026-10-30.md)。

它与已有 `music compose` 不同：`compose` 从可编辑音符谱面做 CPU 解析合成；`generate` 从风格提示或歌词运行神经模型，输出完整的 48kHz、双声道 Float32 WAV。神经配乐保存可编辑的生成请求与来源配方，不将音频声称为可编辑 MIDI、乐器分轨或逐音符谱面。

## 模型、运行库与许可

引擎为 `acestep15-native-cuda-v1`，协议为 `agent-native-music-generation-v1`。本机使用已有原生 Python3.13.14 / Torch2.14.0+cu130 / ComfyUI0.41.0；新模型、任务、缓存与证据均在 E 盘。不安装全局依赖，不调用 Docker／WSL，不操作其他项目服务。

固定重打包仓库：[Comfy-Org/ACE-Step-1.5](https://huggingface.co/Comfy-Org/ACE-Step-1.5)，revision `371bb1680f8c88d8c1083f6ffb6330d3d55bff76`。下载镜像只承担传输，完整 SHA256 与原始仓库声明逐文件核对；产品命令不会自动下载模型。

| 本地文件名 | 原始 split_files 路径 | 字节 | 完整 SHA256 |
| --- | --- | ---: | --- |
| diffusion_model.safetensors | diffusion_models/acestep_v1.5_turbo.safetensors | 4787825604 | 3f6e0797fad420a39bd33979eb6e840e30989e34a3794e843d23b60ec6e422d7 |
| text_encoder.safetensors | text_encoders/qwen_0.6b_ace15.safetensors | 1191588248 | fd4590c82153b8ddb67e15a2e7aaa8afa8b83a858c8a9b82a4831063156aa7a7 |
| language_model.safetensors | text_encoders/qwen_1.7b_ace15.safetensors | 3708523360 | ed63e9247d1f55f3ace04fa11e95b085fc82d459c82c5626f0b2e37b91ebd710 |
| vae.safetensors | vae/ace_1.5_vae.safetensors | 337431732 | 6de92e3a862acd287e08b024ac90f0783a8635451b728721a33ff03565bcb2bb |

上游 [ACE-Step 代码许可](https://github.com/ace-step/ACE-Step-1.5/blob/main/LICENSE)声明 MIT；本次重打包模型卡声明 Apache-2.0；所用外部 ComfyUI 核心保留 GPLv3 许可，未混称为本产品 MIT 源码。记录见[本地许可声明与文本](../validation/evidence/acestep15-admission-20261029-r1/notices-r2/verification.json)。模型许可、运行库许可及具体产出权利分别记录；生成结果默认 `unverified / internal`，不会自动成为可发布广告素材。YuE2 的非商用权重不作为本功能的默认后端，见[准入说明](MUSIC_BACKEND_ADMISSION.md)。

登记会校验四个模型的完整哈希、张量载荷、原生 Python.exe、来源证据及有界 ComfyUI 源码／资源清单。模型目录与运行代码拒绝符号链接／目录联接；共享模型、custom_nodes 和网页目录不作递归扫描。登记与每次调用需读取大体积权重，冷盘校验时间应与模型推理时间分别计算。外部 Python 环境中的依赖包版本记录在真实执行结果中；本版本未将整个外部环境打包或逐文件冻结为干净主机交付。

## 请求与参数

UTF-8 JSON 示例：

```json
{
  "format": "agent-neural-music-v1",
  "prompt": "Warm acoustic piano instrumental, soft brushed drums and upright bass, intimate chamber jazz, clean studio recording.",
  "lyrics": "",
  "instrumental": true,
  "duration_seconds": 10,
  "bpm": 90,
  "language": "unknown",
  "keyscale": "D minor",
  "timesignature": 4,
  "seed": 20261030,
  "steps": 8,
  "generate_audio_codes": true
}
```

| 字段 | 范围和实际含义 |
| --- | --- |
| prompt | 1—4000 字符，原文保留。描述曲风、乐器、情绪与录音特征；提示遵循须试听。 |
| instrumental / lyrics | 明确布尔值。纯音乐的歌词为空；演唱必须提供非空歌词与语言，不静默丢弃歌词。歌词最多12000字符。 |
| duration_seconds | 接口接受10—600秒，须为0.04秒整数倍，对应原生25 latent frames/s。不是已验收全部时长／显卡的承诺；长曲仍需资源及质量验证。 |
| bpm | 10—300整数，默认120；音乐语义控制，不是已测得速度或节拍准确率。 |
| language | 明确语言代码；纯音乐默认unknown。接口可选51代码，不等于51种语言歌唱质量均通过。 |
| keyscale | 如C major、D minor；支持标准升降音名。模型条件不等于逐音符调性保证。 |
| timesignature | 2、3、4、6，默认4；表示拍号条件。 |
| seed | 0至2^63−1整数，默认0；不承诺跨设备／库版本逐字节复现。 |
| steps | 1—32整数，默认8。Turbo原生示例配置为8步、Euler、simple、CFG1、flow shift3和multiplier1。 |
| generate_audio_codes | 布尔值，默认true。明确是否执行语言模型音频码生成；关闭时不会伪造语言模型前向次数。 |

不会用补零、循环、重采样、归一化或裁短来冒充请求的生成时长。实际输出须为精确 `round(duration_seconds × 48000)` 个立体声样本，有限且非静音，否则任务失败。

## 使用顺序

先用匹配版本的入口检查 `version` 和 `music generate --help`。以下 `$avk` 是该入口脚本；`$project`、模型、核心、原生 Python 和证据路径均由调用方显式提供。

本机开发候选可以显式调用下列安装入口检查版本，避免误用仍为63的正式Skill：

```powershell
$musicPython = 'C:/Python313/python.exe'
$musicLauncher = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.62/final-r1/installed/run.py'
& $musicPython -I -S -B -X utf8 $musicLauncher version
& $musicPython -I -S -B -X utf8 $musicLauncher music generate --help
```

后面的 `$avk` 可指向已匹配该候选的未注册PowerShell入口：`E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/music64-skill-stage-r1/skills/agent-ffmpeg-local-editor/scripts/run.ps1`。这只用于开发验证，不改变Codex发现的正式注册入口。完整64安装回归、实际模型、工程包和正式切换全部通过后才更新正式Skill。

```powershell
& $avk music generator-adapter register --project $project --adapter-id ace15 `
  --model-path $models --runtime-root $core --executable $python --evidence $evidence
& $avk music generator-adapter inspect --project $project --adapter-id ace15
& $avk music inspect-generation --input $request
& $avk music generate --project $project --adapter-id ace15 --input $request `
  --new-asset-id music01 --apply --track-id track_audio_1 --dry-run
& $avk music generate --project $project --adapter-id ace15 --input $request `
  --new-asset-id music01 --apply --track-id track_audio_1
```

请求可在生成前编辑，也可从旧资产保存的配方重跑：

```powershell
& $avk music generate --project $project --adapter-id ace15 `
  --recipe-asset-id music01 --new-asset-id music02
```

配方重跑保留原请求，要求模型和运行代码摘要相同；新提示或新歌词请保存为新 JSON 并用 `--input`。使用新资产ID，保留旧版本。`--apply` 必须同时显式选择未锁定的音频轨，预先检查与既有片段重叠；不加 `--apply` 时只入库供试听。生成后先听完整 WAV，核对歌词、结构、节奏、音量和使用权，再决定混音与挂接。长曲结构、编曲重写、音色分轨、自动视听语义匹配仍属后续范围。

## 执行、回收和工程证据

文本编码器、可选语言模型、扩散模型和VAE分别记录实际神经前向次数与输出设备；只发现CUDA设备或将CPU结果复制到显卡，不构成执行通过。文本与扩散模型显式使用CUDA0/BF16，VAE遵循原生解码器精度，最终输出Float32。允许权重卸载到CPU，拒绝CPU神经推理回退；文本和扩散阶段分别做显存准入，真实峰值与阶段耗时写入报告。显存准入是运行前快照，不能保证任意长曲不发生OOM。

任务采用原生 Windows 受控子进程，执行前挂接 KILL_ON_JOB_CLOSE。参数包含 `--timeout-seconds`（默认1800，最多7200，覆盖工作进程和输出核验，不含登记及命令预检）、`--storage-budget-mib`（默认2048，64—8192）与 `--cancel-file`。失败或取消应回滚工程修改并保留有界脱敏诊断；进程回收、超时和取消须用实际收据验收，不能只从实现推断已通过。

输出先作为完整Float32 PCM写入，再编码为无音频处理的Float32 WAV；控制端独立检查FFprobe时钟、WAV摘要与完整解码PCM摘要。请求、模型／代码摘要、原生采样时钟和音频摘要作为 `source.music_generation` 保存在资产中；工程校验拒绝摘要被改动或与资产不符的配方。工程包保存音频及请求配方，外部大模型仍按原始路径／摘要登记，不从工程包静默下载或重新信任。

当前测试与失败历史：

- [25项请求／BF16载荷／配方／执行证据检查](../validation/evidence/music-generation-20261030-r5/unit/verification.json)，不含模型推理。
- [33项原生工作进程隔离检查](../validation/evidence/music-generation-20261030-r1/source64-bootstrap-r1/verification.json)，不含模型推理。
- [原生接口探测](../validation/evidence/acestep15-admission-20261029-r1/native-interface-r3/verification.json)，673运行文件、393实际导入文件均被登记清单覆盖；不加载权重。
- [首次实际调用被BF16校验拒绝](../validation/evidence/music-generation-20261030-r1/actual-piano1/verification.json)，修复前记录保留，不能计作生成通过。
- [第二次登记被本地许可路径策略拒绝](../validation/evidence/music-generation-20261030-r1/actual-piano2/verification.json)，只修正验证脚本，不放宽本地策略。
- [首次完整生成调用超时](../validation/evidence/music-generation-20261030-r1/actual-piano3/verification.json)，没有音乐输出或自然质量结论；失败诊断记录原生工作进程被回收。最后报告的阶段较粗，不能由这一阶段文本确认具体导入栈或推理耗时。

完整G25、跨显卡矩阵、干净主机、自然音乐听审、输出权利和完整剪映等价验收仍未关闭。

## 首个实测结果

[源码64首个真实案例](../validation/evidence/music-generation-20261030-r1/actual-piano4/verification.json)已产生10秒、48kHz双声道Float32 WAV，480000样本；文本2、语言模型50、扩散8和VAE1次实际前向均在CUDA0，完整PCM回读和入轨通过。首次完整生成命令 3979.74 秒，工作进程 3397.72 秒；模型函数 1192.00 秒不包含此前导入，也包含各阶段权重载入，不能当作纯计算时间。这仍是开发候选，正式入口63不含新命令；完整兼容组431中有1项启动等待失败。新音乐的安装版、Skill、人类听审和更广案例仍按各自收据验收。[源码工程包回放](../validation/evidence/music-generation-20261030-r1/package-r1/verification.json)已确认母带WAV与配方完整相同，成片全部RGBA与解码PCM重放相同；AAC成片不是无损母带。

## 使用已生成的本地工程包

本机已实际执行下面的候选入口流程，完整命令及退出码见[回放记录](../validation/evidence/music-generation-20261030-r1/installed-package-stage1/calls.json)。将`$musicReplayProject`设为E盘尚不存在的目录，将`$musicProjectZip`设为调用方拥有的工程包。本轮内部音频未提交到公开仓库；公开克隆本身不包含这个ZIP。

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/music64-skill-stage-r1/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
$musicProjectZip = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/music-generation64-package-r1/editable-neural-music.zip'
$musicReplayProject = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/my-music-replay'
& $avk version
& $avk convert import --input $musicProjectZip --output $musicReplayProject
& $avk render --project $musicReplayProject --output "$musicReplayProject/renders/replay.mp4"
```

这条流程只使用工程包内既有音频和配方，模型前向为0。重新生成须重新登记外部模型／核心／Python并调用`music generate`。本轮安装回放通过不能代替独立安装版新生成、正式Skill切换、人类完整听审或具体输出权利结论。

## CLI65读取与计时更新

开发候选65固定四组件pread与静态加载策略，并将运行库导入纳入模型函数总时钟；实际命令、字段范围、新适配器登记、两套原生小型BF16核验及验收限制见[CLI65读取与完整计时手册](NEURAL_MUSIC_LOADING.md)。旧CLI64实测和失败收据原样保留；正式入口仍63。
