# CLI65：神经配乐读取策略与完整计时

CLI0.1.65 的开发候选将四组件权重读取固定为原生 safetensors `pread`，并将运行库导入计入模型函数总时间。正式注册入口仍为 CLI0.1.63／local61／r58；候选构建、真实生成、独立安装和正式切换分别验收。

本页补充[神经配乐使用手册](NEURAL_MUSIC_GENERATION.md)，不改变[原38项目标](GOAL_GAPS_20261025.md)的范围。

## 实际改变

1. 保留 Comfy 原生 checkpoint 加载器、张量类型、metadata 及后续采样逻辑。在当前隔离工作进程内，临时将 `safetensors.safe_open` 路由到 `backend='pread'`，仅允许当前组件所需的确切本地文件。
2. 文本阶段必须实际打开两个编码器；扩散和VAE阶段分别打开对应组件。任一阶段绕过读取、使用其他文件、加载器异常或原生库不支持 `pread` 时失败；不会尝试 mmap、pickle 或 CPU 神经推理。
3. 成功或异常退出加载区间时恢复原读取器。成功结果要求四个不同组件的实际读取记录；控制端拒绝缺项、重复项、其他后端或无效打开次数。
4. 核心参数必须由该核心的 `add_argument` 实际声明，包含 `--disable-dynamic-vram`。仅当核心声明 `--offline` 时才传入该前端参数。工作进程网络阻断、离线环境、完整权重及代码锁定始终有效，不以可选前端参数代替。

该策略允许权重在CPU内存中加载或卸载，实际神经前向仍必须发生在CUDA0。`pread` 是文件读取策略，不是新的GPU计算算法，也不能单凭小型读取测试推断真实生成已提速。

## 计时字段

`generation.worker.model.elapsed_seconds` 从模型函数入口开始，包含运行库导入。CLI64旧案例的同名字段排除了此前导入，比较时必须区分；完整命令耗时仍由外层调用单独记录。

| 字段 | 实际计时范围 |
| --- | --- |
| `runtime_import_seconds` | 模型函数入口、参数准备、运行库导入和设备准备至首次权重阶段之前 |
| `text_checkpoint_load_seconds` | 两个文本组件的checkpoint读取及加载器初始化 |
| `text_encode_seconds_including_device_load` | 文本／可选语言模型执行；可能包含设备载入 |
| `text_load_and_encode_seconds` | 文本阶段合计，包含加载、准备与编码 |
| `diffusion_checkpoint_load_seconds` | 扩散checkpoint读取及模型创建 |
| `diffusion_sample_seconds_including_device_load` | latent准备、采样与设备载入等实际调用 |
| `diffusion_load_and_generate_seconds` | 扩散阶段合计 |
| `vae_checkpoint_load_seconds` | VAE checkpoint读取及解码器创建 |
| `vae_decode_seconds_including_device_load` | VAE解码、输出时钟／有限值检查、转换为原生Float32样本；可能包含设备载入 |
| `vae_load_and_decode_seconds` | VAE阶段合计 |

这些是墙钟时间，均不称为纯GPU kernel时间。阶段合计不得重复相加为推理耗时；控制端核对导入与三个大阶段之和未超出完整模型函数时间。

## 新登记与使用顺序

升级实现或读取策略后，原适配器的实现字节／设置摘要将不再匹配。保留旧工程与旧音频，使用新ID显式登记；不静默修改旧记录。

本机候选PowerShell入口准备后，使用：

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/music65-skill-stage-r1/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version # 须为0.1.65
& $avk music generator-adapter register --project $project --adapter-id ace15_v65 `
  --model-path $models --runtime-root $core --executable $nativePython --evidence $evidence
& $avk music generator-adapter inspect --project $project --adapter-id ace15_v65
& $avk music inspect-generation --input $request
& $avk music generate --project $project --adapter-id ace15_v65 --input $request `
  --new-asset-id music65 --dry-run
& $avk music generate --project $project --adapter-id ace15_v65 --input $request `
  --new-asset-id music65 --timeout-seconds 3600
```

`$models`、`$core`、`$nativePython` 和本地 `$evidence` 须显式提供。完整命令包含登记或预检时的大文件校验；3600秒仅为该次工作进程及输出检查的预算，不是速度承诺。模型和运行库均不随应用ZIP自动下载或打包。

成功后核对四组件 `local_weight_reads`、四阶段实际神经前向及设备、原生样本数、完整PCM回读、输出摘要和权利记录，再试听并选择。需要入轨时显式使用 `--apply --track-id`，先检查轨道锁定和重叠；完整参数见主手册。

## 已有证据及仍缺内容

[37项请求／读取／响应检查](../validation/evidence/music-loading-20261030-r1/source65-unit-r1/verification.json)通过，包含新12项读取策略与计时边界；37项也包含在[74项配乐回归](../validation/evidence/music-loading-20261030-r1/source65-music-r1/verification.json)中，不重复累计。

[E盘已有环境](../validation/evidence/music-loading-20261030-r1/native-reader-r1/verification.json)和[D盘已有环境](../validation/evidence/music-loading-20261030-r1/native-reader-d1/verification.json)均实际用 safetensors0.8.0 的 `pread` 读取四份微型BF16张量，张量数值与metadata一致、读取器恢复。分别使用Torch2.14.0+cu130和2.13.0+cu130；没有载入音乐权重或执行神经前向，不能当作两套核心的音乐生成兼容或速度验收。

[导入栈采样](../validation/evidence/music-loading-20261030-r1/native-stack-reader1/verification.json)显示采样时位于Torch模块文件读取。只读采样不确定全部等待原因；不据此承诺 `pread` 能消除导入成本。

CLI64的真实10秒首例、66分钟完整命令和完整431组的一项失败继续保留。CLI65的新生成、完整安装回归、正式Skill切换、自然听感、长曲、歌词、乐器分轨、跨显卡及干净主机按各自实际证据验收。

## 独立安装回归与恢复限制

local63候选的独立安装版分别通过74项配乐、33项原生隔离和26项执行控制回归，实际模块路径来自安装目录，无源码回落。这三组不代替新音乐模型前向、完整443兼容、自然听审或正式注册。

原12项会话组保留一项20秒启动失败。保留原门槛的内存观测单项后来通过，只说明该次未复现；不能据此确认写盘是唯一原因或宣布原失败已修复。另以两个一次性工程复现恢复备份未核验SHA和后续缺失导致部分写回的问题，尚未修复。完整证据和下一步见[本轮记录](../validation/CLI65配乐读取与计时_2026-10-30.md)。
