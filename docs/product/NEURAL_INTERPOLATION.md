# 本地 CUDA 神经补帧与可编辑慢动作 / Neural interpolation

CLI **0.1.42** / **alpha.4-local.40** / **r43 kit**。仍为唯一入口
`$agent-ffmpeg-local-editor`，17内部模块。新增真正 RIFE4.25 CUDA 推理，补帧资产可独立入库、
慢放入轨及按配方重跑。完整G10关闭条件和完整剪映功能目标继续保留。

## 使用流程

先按[本地使用流程](COMMUNITY_LOCAL_DELIVERY.md)定位已安装的 `$avk`，运行 `version`、
`doctor`、`capabilities`。本轮安装包不包含神经权重和CUDA模型解释器，不会自动下载安装它们。

```powershell
& $avk media ingest --project E:/work/edit --input E:/media/source.mov `
  --license-spdx CC0-1.0 --evidence E:/media/SOURCE.txt
& $avk interpolate adapter register --project E:/work/edit --adapter-id rife425 `
  --model-path E:/models/rife425 --executable E:/native/python.exe `
  --evidence E:/models/rife425/SOURCE.json --license-spdx MIT
& $avk interpolate adapter inspect --project E:/work/edit --adapter-id rife425
& $avk interpolate generate --project E:/work/edit --adapter-id rife425 `
  --source-asset-id RETURNED_ASSET_ID --asset-id preview_4x --factor 4 `
  --start-frame 0 --end-frame 48 --cut-after-frame 23 --dry-run
& $avk interpolate generate --project E:/work/edit --adapter-id rife425 `
  --source-asset-id RETURNED_ASSET_ID --asset-id slow_4x --factor 4 `
  --start-frame 0 --end-frame 48 --cut-after-frame 23 `
  --apply --video-track-id track_video_1 --audio-track-id track_audio_1 `
  --playback-speed 0.25 --timeout-seconds 3600 --storage-budget-mib 2048
& $avk validate --project E:/work/edit
& $avk preview frame --help
& $avk render --project E:/work/edit --output E:/work/edit/renders/slow.mp4
& $avk convert export --project E:/work/edit --target-format package `
  --output E:/work/edit/exports/edit.aevpkg.zip
```

`RETURNED_ASSET_ID`必须使用实际入库返回值。源没有音轨时不指定`--audio-track-id`；
有音轨时必须指定，画面和声音是两个关联但可独立编辑的片段。默认生成资产保持原时长，
`--playback-speed`只改变入轨速度：4倍帧数加0.25倍播放速度得到4倍时长慢动作。
普通渲染按时间线速度伸缩音频；生成资产内PCM仍保持原样。

重跑使用新资产ID：

```powershell
& $avk interpolate generate --project E:/work/edit --adapter-id rife425 `
  --recipe-asset-id slow_4x --asset-id alternate_3x --factor 3 --dry-run
```

可覆盖源资产、倍率、原生选区和切镜规则。换源时默认使用新源完整区间，不借用旧选区；
旧参数若超出新源会被拒绝，须明确修订。配方包含源摘要、原生时钟、输出PTS/持续时间、
选区、音频样本范围和切镜参数，资产验证及片段库导入会核验并重绑定父资产ID和摘要。
工程包携带素材与配方，模型是外部显式依赖，迁移后重跑须再次登记。

## 实际处理与边界

| 项目 | 行为及限制 |
|---|---|
| 模型 | 固定RIFE4.25五阶段IFNet；158个FP32推理张量；实际Torch CUDA，GPU不足失败，没有CPU回退。scale=.25/.5/1/2，输入按scale所需倍数replicate填边。 |
| 原生时钟 | ffprobe实际逐帧PTS和最后帧持续时间；CFR/VFR均支持；半开原生帧选区；N帧得到N×factor帧，factor为2..8整数，含1/3等任意查询时间。没有先套固定FPS。 |
| 最后区间 | 最后原帧持续区间明确重复该帧，不做没有参考图的运动外推。 |
| 原帧 | 每个解码后原始RGBA作为输出anchor逐字节复制，含alpha0隐藏RGB；编码后再次抽出全部anchor计算摘要。 |
| 透明度 | 合成帧用实际训练flow和mask运送预乘RGBA，再反预乘；合成alpha量化到0时清零RGB。原帧不改。不是透明视频专训模型，边缘仍需复核。 |
| 切镜/静态 | 默认mean absolute RGB difference≥.35保持上一帧；`--scene-cut-threshold 0`禁用；`--cut-after-frame`是选区相对索引，可多次指定；RGBA完全相同时跳过模型。切镜/静态保持不冒充模型forward。 |
| 音频 | 保留第一音轨的原采样率、声道及选择的全部解码Float32 PCM；从实际音画start_pts与time_base对齐；边界四舍五入到最近原始样本，报告有理数误差；首尾空档明确补零；未知原时长拒绝。 |
| 编码核验 | qtrle/argb MOV，无损RGBA；owned option file中的setts设定每个包PTS/DTS/持续时间，绕开Windows命令行长度；全流RGBA、全原帧、全PCM、每个PTS与持续时间必须往返一致才发布。 |
| 可编辑性 | 新素材、独立画面/音轨、关联link_id、播放速度、可重跑配方、快照、权利依赖与工程包；支持原有时间线关键帧、滤镜和后续调整。 |
| 权利 | 官方说明代码及其列出的模型按MIT；原始素材/模型/生成内容分别登记，不把MIT自动当作人物或素材授权。模型目录Python/Pickle不执行，运行时固定源码和safetensors。 |
| 资源 | ≤600选区秒，≤15,000源帧/120,000输出帧，32..4096像素边，≤512MiB受管CPU数组及≤2GiB素材；16..2048MiB显式磁盘预算，保守估算可更早拒绝。不是全进程RSS或显存预留。 |
| 生命周期 | 原生Windows Job拥有decoder/worker/encoder，取消/超时后杀停并等待、关闭管道、清理owned workspace；发布失败事务回滚，保留限额诊断。超时计时不含前置完整摘要/原生帧探测，探测单独≤300秒且可取消。 |
| 输入 | 当前要求无ICC、无旋转、方形像素、逐行8bitSDR视频；HDR/高位深须用户明确预处理，不静默丢失。 |

## 模型来源和复现

[Practical-RIFE官方](https://github.com/hzwer/Practical-RIFE)推荐4.25并在README声明列出的模型与项目均按MIT。
固定官方commit`bbfd2ea90910789a860ea3e2b32a240cd577b75e`；官方Drive连接实际超时，记录保留。
本轮从固定Hugging Face revision的公共镜像取得原始归档，校验上游LFS SHA256/大小；
原始归档不是对官方Drive逐字节比对。`weights_only=True`仅在开发转换中读取原始权重；
严格核验已知teacher/caltime训练分支后移除，158推理张量与独立saferife镜像全部逐张量相同，
转成safetensors后严格回读。运行时不允许pickle、模型目录动态代码、联网或自动下载。

完整固定来源、失败尝试、张量转换和CUDA探针见
[证据目录](../validation/evidence/native-interpolation-20261027-r1/)。源代码版权声明见产品`RIFE_LICENSE.txt`。
上游README推荐Python≤3.11；本项目的固定图实际原生Python3.13/CUDA组合由本轮实测证明，
不冒称上游对该组合提供支持。

## 验收与预览

[C52完整案例](CASES.md#c52-native-neural-interpolation)使用CC0确定运动/透明度诊断源和
Blender Foundation CC-BY-3.0《Sintel》动画预告片。后者有真实保留的中间帧作参考；
它是动画素材，不是真人实拍。原始片段、4倍慢动作、逐帧误差和失败样例分开记录。
GIF只展示实际编码结果，不能代替全帧数据核验或人工连续播放/听审。

遮挡、闪光、细线、快速运动、切镜阈值误判、跨设备确定性、自然质量、HDR、
实时4K和完整剪映等价继续验收，不因一个案例通过而关闭G10或38项产品目标。

繁體摘要：真正CUDA神經補幀保留原生CFR/VFR時間、全部原始RGBA影格與原始PCM；
以新素材及關聯可編輯雙軌交付。切鏡使用明確索引或RGB差分，最後區間保持末幀。
請審核遮擋/細線/快速運動，原生HDR與自然品質尚未完成廣泛驗收。

English: Actual native CUDA RIFE4.25 creates editable interpolation assets while
preserving native CFR/VFR timestamps, all original decoded RGBA anchors and
selected original PCM. Use explicit cuts and review actual encoded results.
The final interval holds; alpha transport uses premultiplied flow. GPU/model
dependencies remain explicit. Natural motion/HDR/occlusion acceptance and full
CapCut parity are ongoing; no quality claim follows from the protocol tests.
