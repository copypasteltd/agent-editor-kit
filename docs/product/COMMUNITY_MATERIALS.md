# 开源素材、配音、翻译、配乐与 GPU 使用手册

当前运行版本为 **CLI0.1.58 / `v0.1.0-alpha.4-local.56` / r56 kit**，使用[匹配的本地应用包及统一Skill流程](COMMUNITY_LOCAL_DELIVERY.md)。本页素材／配音／翻译／GPU专项实测基线仍为 **CLI0.1.3 / local.1**，本轮四个模型包仅重新配置校验，没有重新推理全部这些任务；CLI58实际DF3 CUDA、精确去重、ACES及安装回归分别见[交付证据](../validation/CLI58统一Skill切换_2026-10-29.md)。公开alpha.3 / CLI0.1.2旧附件保持，不含本地全部新命令。仍只注册 `$agent-ffmpeg-local-editor`，17内部模块。r56压缩包内本手册是打包时的历史快照，当前版本及配套以包内COMMUNITY_LOCAL_DELIVERY和本仓库最新入口为准。

## 能力与交付层级

| 编号 | 模块 | 已实现 | 实际边界 |
|---|---|---|---|
| M01 | 社区资源 | 44 首 BGM、85 个短乐、228 个独立音效、Noto 简/繁 2 个字体；共 359 项实际文件 | 不是商业素材订阅库；5 首音轨经明确有损转码，2 对重复音效只计独立文件，保留别名 |
| M02 | 本地配音 | Kokoro 103 个上游具名音色，中英文本/UTF-8 文件、0.5–2.0 语速、24kHz 单声道 PCM WAV、导入/显式应用音轨 | 实际生成 3 个音色试听文件；人工听审未完成，不做克隆或自动情绪保证 |
| M03 | 中英翻译 | OPUS 中英双向、简/繁输入输出、逐段文本、双语字幕、显式术语译后替换 | 非通用多语翻译；SRT 保留 cue 顺序/毫秒/重叠，ASS/VTT 转 SRT 后丢样式；无自动语义验收 |
| M04 | BGM 准备 | 按素材 ID 导入；偏移、截取、明确循环、增益、淡入淡出 | 循环不等于接缝修复；不生成原创音乐 |
| M05 | 混音/闪避 | 独立人声+BGM，侧链压低配乐、限幅、48kHz 双声道、准确样本数 | 保留原分轨；不静默截断人声；PCM 峰值/RMS 不等于听感或真峰值认证 |
| M06 | 音效/字体 | CC0 界面/撞击/脚步音效，OFL Noto SC/TC 字幕与标题实际渲染 | 音效时长/用途逐项检查；字体保留 OFL/RFN，不再分发商业系统字体 |
| G01 | GPU 处理 | 配音 CUDA 13 / ONNX Runtime；翻译 CUDA 12 / CTranslate2 `int8_float16`；`auto / cpu / cuda` | 本机 RTX 3060 已实测；GPU 初始化可能慢于 CPU；不代表所有平台/型号已验收 |
| G02 | 显存/回退 | 查询空闲显存；配音至少 3072MiB、翻译至少 1536MiB；自动模式显式记录回退 | 阈值是保守预检，不能保证绝不 OOM；严格 CUDA 失败不伪报成功；不停止其他 GPU 任务 |
| M07 | 离线交付 | 基础素材随应用；4 个可选模型包，清单/逐文件哈希、独立进程和原生安装 | 不创建虚拟环境，不隐式联网；缺失或篡改的包拒绝，不借 CPU 回退绕过校验 |

## 从零到交付

先在本地完成应用和模型包安装。新包位置及哈希见本轮交付记录；公共旧 alpha.3 可继续使用其原手册。外层只指定一个 Skill：

```text
$agent-ffmpeg-local-editor
使用本地 GPU 配音，把提供的中文文案制作成双语字幕短片。
先展示音色和滤镜候选，确认选型后组合独立人声、背景音乐与音效。
交付可编辑工程、预览、成片和质量报告，并说明实际设备和回退情况。
```

以下 `$avk` 指向统一 Skill 的 `scripts/run.ps1`。本机登记了 CPU/GPU 模型路径与已有 NVIDIA 库，因此 `--device auto` 优先选 GPU；独立安装可显式传 `--pack`、`--gpu-pack`、`--cuda-library-directory`。CLI 不会替你下载依赖。

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
$aekProject = 'E:/video-work/community-ad'
& $avk version
& $avk gpu inspect
& $avk model-pack list
& $avk project init $aekProject --name 'Community ad'
& $avk materials list --kind music --query 'rpg'
& $avk materials inspect --id kenney-music-jingles-jingles-hit00
& $avk materials ingest --project $aekProject --id kenney-music-jingles-jingles-hit00 --asset-id asset_jingle
& $avk voice list --language zh
& $avk voice synthesize --project $aekProject --voice zf_001 --input 'E:/video-work/narration.txt' --device auto --asset-id asset_voice
& $avk translate subtitles --project $aekProject --from zh-Hans --to en --input 'E:/video-work/source.srt' --output exports/bilingual.srt --mode bilingual --device auto
& $avk music prepare --project $aekProject --asset-id asset_jingle --duration-seconds 12 --loop --fade-in-seconds 0.3 --fade-out-seconds 0.8 --new-asset-id asset_bed
& $avk music mix --project $aekProject --voice-asset-id asset_voice --music-asset-id asset_bed --duration-seconds 12 --music-gain-db -18 --duck --new-asset-id asset_mix
# --apply 需要明确指定未锁定/未静音的 audio 轨道。
# 素材导入后，用实际返回 ID 编写 timeline compose JSON；视频/字幕/音轨分别编辑。
& $avk validate --project $aekProject
& $avk preview frame --project $aekProject --frame 0 --height 640
& $avk render --project $aekProject --output 'E:/video-work/community-ad/renders/ad.mp4'
& $avk quality check --project $aekProject --input 'E:/video-work/community-ad/renders/ad.mp4' --require-audio
& $avk convert export --project $aekProject --target-format package --output 'E:/video-work/community-ad.aevpkg.zip'
```

示例中的文本/字幕文件须已存在。混音时长必须覆盖自然配音时长；若配音超过 12 秒，请延长 BGM 和成片，不截断台词。检查响应中的 `ok / status / errors / warnings / data.device / inference.provider` 和实际输出文件。

字幕字号/宽度按作者画布像素设置。`preview --height` 缩放预览；`render --width/--height` 改变合成画布，不是单纯缩放最终画面。建议在 `update_sequence.patch.canvas` 固定最终画布，再按该尺寸设置文字并用默认尺寸渲染。本轮保留首次文字溢出失败记录，另有 8 条命令复核修正后的预览、成片及工程往返。

## GPU 兼容与取舍

| 路径 | 模型/精度 | 运行库 | 当前状态 |
|---|---|---|---|
| CPU 配音 | Kokoro int8 ONNX | sherpa-onnx 2.0.0 / ORT 1.28.2 | Windows CPython 3.13 x64 实测 |
| GPU 配音 | 同源非量化 ONNX / Float32 | NVIDIA 驱动、CUDA 13、cuDNN 9；独立 GPU 包 | RTX 3060 实测，当前仅设备 0 |
| CPU 翻译 | OPUS int8 | 自编译 CTranslate2 4.8.3 + Ruy，无 MKL/cuDNN/Intel OpenMP | 双向文本/字幕实测 |
| GPU 翻译 | 同一 OPUS int8 权重、`int8_float16` 计算 | CUDA 12 cuBLAS；GPU 包 | RTX 3060 实测，显式 device-index |
| AMD/Intel GPU、Apple GPU | 未集成 | 不伪用 CUDA | 通过 `auto` 选择已验证 CPU 路径 |

同一非量化配音模型、同一约 6.85 秒文本：CPU 第二次生成约 4.93 秒，GPU 第二次约 0.62 秒；GPU 加载约 7.54 秒、CPU 约 4.08 秒。设备上另有任务，结果不是基准承诺。一次 CLI 启动包含包校验/模型加载，不能套用约 8 倍的持续生成加速比。翻译示例 CUDA 首次推理约 0.38 秒、再次约 0.037 秒，亦不含完整 CLI 启动。详见实际证据。

核心与模型许可分别列明。NVIDIA 驱动/CUDA/cuDNN 是 GPU 兼容依赖，含其自身非开源许可；上游 GPU Windows 二进制附带的 Intel 运行库同样保留原许可，不包装为“开源素材”。需要避开专有数值内核时选择独立 CPU Ruy 方案。普通素材处理/FFmpeg 滤镜没有因此自动全部 GPU 化。

## 模型包与可移动安装

包必须与当前 CLI 内置 `model-packs.json` 的锁定摘要相符。使用 `scripts/install_community_pack.py --archive <local.zip> --sha256 <archive-hash> --catalog <installed/site/ai_ad_editor/material_data/model-packs.json> --id <pack-id> --target <new-local-path>`。目标需不存在，父目录需已存在；安装在本地 staging 校验完后原子迁移，不全局 pip、不访问网络。

现有目的地、ZIP 摘要不符、缺失/额外/重复文件、路径穿越、模型文件改动会拒绝。`--device auto` 的 GPU 运行失败可在尚未产出文件时重试 CPU，响应保留失败日志和原因；包篡改不触发此回退。`--device cuda` 严格返回失败。缺失的依赖不会自动下载。

## 翻译、术语与权利

支持 `en ↔ zh-Hans/zh-Hant`；简繁在中文输入/输出侧处理，不是独立中英模型以外的多语服务。文本每行一段、最多 1000 段；字幕最多 1000 cue；每段最多 512 模型 token，触及解码上限会拒绝，避免静默截断。返回源文、译文、模型摘要、分数和时码，人工校对另行记录。

```json
{"entries":[{"source":"background music","target":"BGM","variants":["背景音乐"]}]}
```

术语是明确的译后替换：源词出现且译文有已知 variant 才替换；找不到会拒绝，不声称受约束解码。真实失败示例：`speech` 被通用模型译成“演讲”，应按视频语境改成“原声/语音”。字幕翻译保留时间不代表文本与发音重新对齐。

OPUS 原始归档许可为 CC-BY-4.0；与部分 Hugging Face card 的 Apache 标签冲突时，包保留原始实际许可证和模型署名。Kokoro 权重 Apache-2.0；音色不是用户上传真人克隆。生成配音和派生混音在项目台账仍默认 `unverified/internal`，模型许可不自动变成客户广告的发布权利。

## 真实案例与验收

[逐项素材](COMMUNITY_MATERIAL_CATALOG.md) · [103 音色与实际试听范围](COMMUNITY_VOICES.md) · [本地包与安装](COMMUNITY_LOCAL_DELIVERY.md) · [原始核验](../../docs/validation/evidence/community-materials-20261025-r1/cpu/verification.json) · [GPU 核验](../../docs/validation/evidence/community-materials-20261025-r1/gpu/verification.json)。

实际案例保留 12 秒、360×640、30fps、360 帧、独立音轨、SC 字幕与 TC 标题、滤镜、音效和 `.aevpkg.zip` 往返工程。原始配音/混音文件在本地交付目录；未确认发布权利的声音不随公共 README 再分发。公共页面展示由已验证开源资源制作的无配音演示和 GIF，完整本地成片及机器响应另见实测路径。

CPU 专项 46 条实际命令、GPU 专项 15 条实际命令；不与历史回归合并计数。字幕逆序和重叠、毫秒时间、三音色、UTF-8 文本/语速、缺失/篡改/额外模型文件与严格 CUDA/CPU 回退分别检查。人类听审和语义接受尚未完成，亦未实现完整剪映等价。
