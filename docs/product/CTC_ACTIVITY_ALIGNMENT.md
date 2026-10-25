# CTC 词边界与音频活动估计

[简体 README](../../README.md) · [繁體 README](../../README.zh-TW.md) · [English](../../README.en.md) · [完整目标差距](GOAL_GAPS_20261025.md)

CLI 0.1.8 增加显式 `--boundary-mode activity`。它使用同一解码 PCM 的活动区间改善**有静音分隔的词**边界，同时保留原 CTC 字符和词时间。默认 `ctc` 模式继续保留字符峰的原始语义；两种模式都需要已有本地模型、校正文以及人工复核。

这项功能尚不证明连续语音内部词界、中文逐字、歌词、说话人或重叠语音的精确对齐。G15 的完整关闭条件仍然有效。

## 依赖、登记与调用

基础包包含算法和 NumPy，不包含 Torch/Transformers 或模型权重。需要显式提供已有的原生 Windows Python、标准 Wav2Vec2ForCTC safetensors 目录及模型来源证据。登记时锁定模型、执行器与产品实现摘要；从开发版切换至安装版、移动实现或修改文件后，须重新登记。

```powershell
# $avk 是统一 Skill 的 scripts/run.ps1；所有路径都指向已存在的本地文件。
& $avk asr adapter register --project $project --adapter-id words `
  --engine transformers-wav2vec2-ctc-local-v1 `
  --python-executable $ctcPython --model-path $ctcModel `
  --device cuda --threads 4 --evidence $ctcEvidence

& $avk subtitle align --project $project --asset-id speech --adapter-id words `
  --transcript $correctedText --output assets/alignment/words.json `
  --granularity whitespace --boundary-mode activity --timeout 600 --dry-run

& $avk subtitle align --project $project --asset-id speech --adapter-id words `
  --transcript $correctedText --output assets/alignment/words.json `
  --granularity whitespace --boundary-mode activity --timeout 600
```

源音频先通过 `media ingest` 登记，并使用实际返回的 asset ID。CUDA 需要兼容的原生 Torch/驱动；`--device cpu` 可显式登记 CPU。CTC 不隐式下载，不自动切换设备；配音/翻译的 `auto` 配置不代替本对齐适配器登记。

TXT 视为一个源窗口。严格 SRT 可明确分段窗口与原稿范围。运行上限仍为 1800 秒、16384 码点、8192 声学 token；每次前向不超过 30 秒，较长输入使用上下文窗口，完整模型/进程内存另计。未知字符、大小写扩展或繁简缺字会拒绝，需要显式校正文。

需要可编辑高亮字幕时，先创建未锁定的 subtitle 轨道，登记所需字体，再在实际运行命令追加：

```powershell
--apply --track-id captions --font-asset-id font
```

`--apply` 每段最多 128 个显示范围。已有输出禁止覆盖；已有字幕重叠须明确处理或使用 `--replace-track`。音频仍须显式加入音轨，字幕入轨不会自动创建声音。

## 结果如何解释

| 字段 | 含义与使用方式 |
|---|---|
| `boundary_mode` | 实际请求/输出模式，`ctc` 或 `activity` |
| `characters` | 原 CTC token、帧、样本时间、原文码点与字符后验，活动估计不改写 |
| `raw_units` | activity 模式中的原始词范围，供回溯和独立比较 |
| `units` | 最终使用范围；可接受活动区间时估计，否则保留原 CTC |
| `activity.algorithm` | `ctc-guided-activity-v3`；v1/v2 失败结果另存，不覆盖 |
| `activity.regions` | 从实际 PCM 检出的区间及其 CTC 中点归属 |
| `activity.decisions` | 每词是否估计及原因；共享活动、低信噪比、跨区间、超预算或邻词冲突会保留原值 |
| `review_required` | 始终要求复核；活动区间可能来自噪声、音乐，后验也不是校准准确率 |
| `worker` | 实际前向数、设备、峰值显存、版本、网络拦截与输入绑定 |
| `display_cues` | 写入可编辑字幕的实际时间；显示按时点亮不证明时间本身准确 |

另生成 SRT、原稿副本与资产/权利依赖。控制器先验证字符网格与原词，再对同一哈希绑定 PCM 独立重算活动区间、决定与时间；篡改会拒绝。回滚与取消保留诊断，不提升素材或模型权利状态。

## 算法与实测边界

5ms 整数 RMS 帧、显式 DC/噪声底估计、强信号接受与弱信号延展，最多连接 40ms 内部空洞。邻接弱信号区间仅在距离不超过 120ms、无词锚点且唯一邻接已锚定强区间时补入；两个已有词锚点不因此合并，两侧均符合时保留歧义。每次最多移动 750ms，且必须单一词锚定、与邻词不冲突。移动上限是拒绝条件，不是统一加减时间。完整冻结规则与三版修订见[契约](../specs/CTC声学活动边界契约_20261025.md)。

v1 的四组 GPU 实测中，原六词/七词最大误差为 210.0/140.375ms，未过原 66.6667ms 门槛；新 AWB 干净/背景版本为 13.25/8.25ms。v2 降低弱音阈值后，原六词通过，但七词仍为 105.375ms。三版源码、原始输出、评分和失败均保留在[实测目录](../validation/evidence/ctc-activity-20261025-r1/)。没有移动原参考、删词、改变评分或放宽门槛。

v3 开发源实际 36 次 CLI / 6 次 CUDA 前向；冻结源码、规则和输入在执行前后相同：

| 素材 | 原 CTC 最大误差 | v3 活动估计最大误差 | 参考与门槛 |
|---|---:|---:|---|
| 原六词 SLT | 258.1875ms | 4.7500ms | 全词起止各不超过 66.6667ms |
| 原七词 RMS | 286.5000ms | 4.6250ms | 原输入、文本和参考保持 |
| 新八词 AWB | 353.1875ms | 4.9375ms | 作者合成词块 |
| AWB + DC/背景 | 353.1875ms | 4.3125ms | 同词块，明确微小背景 |
| 独立八词 KAL | 363.4375ms | 4.3750ms | 新词、不同声线和间隔 |
| 独立八词 KAL16 | 193.6875ms | 4.5625ms | 新词、不同声线和间隔 |

[开发原始结果](../validation/evidence/ctc-activity-20261025-r1/development-v3-r1/state.json)与安装版、CPU、真实 Skill、成片/工程包结果分别记录；不相加成一个测试通过数。实际安装版本与摘要以[本地交付](COMMUNITY_LOCAL_DELIVERY.md)为准。

自然语音独立精标、连续播放/听审与完整 G15 验收继续开放。作者合成词块摆放是受控参考，不冒充自然音素真值。

English: explicit activity mode estimates isolated-word regions from the same PCM while retaining raw CTC
character/word clocks. The controller recomputes every decision. Shared continuous activity and ambiguous
regions preserve raw timings. Existing local weights and a separately registered native runtime are required;
CPU/CUDA are explicit, with no implicit download or fallback. Neither controlled authored blocks nor subtitle
highlight rendering establish natural phonetic, Chinese-character, singing or overlap precision.
