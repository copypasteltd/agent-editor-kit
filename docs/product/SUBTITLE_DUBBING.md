# 字幕翻译、分段配音与可编辑交付

**CLI 0.1.14 新增：** 同语种 en/en、zh-Hans/zh-Hans 或 zh-Hant/zh-Hant 批量配音保持原文，只初始化配音模型，不加载翻译包、重复字幕或应用译后术语表。语音保持完整，仍检查实际时窗。用于[广告分镜流程](AD_STORYBOARD.md)。下文早期翻译/配音记录继续保留。


[简体首页](../../README.md) · [繁體](../../README.zh-TW.md) · [English](../../README.en.md)

CLI 0.1.9 的 `dub subtitles` 将本地 SRT 翻译、Kokoro 批量配音、实际时窗检查、
声音资产和字幕入轨放进一个工程事务。它推进 G19，完整多语、语义接受、字词精标和口型仍开放。
只用与本地 local.7 运行包匹配的统一 Skill；公开 alpha.3 / CLI 0.1.2 没有此命令。

## 一次调用的输入与输出

| 项目 | 行为 |
|---|---|
| 输入 | 本地普通 UTF-8 SRT、中英源/目标语言；可选术语表、逐 cue 音色、GPU/CPU 与时窗策略 |
| 翻译 | OPUS 中英双向，中文显式简/繁；不截断超过模型 token 上限的文字 |
| 配音 | 同一次 Kokoro 加载复用整批 cue；手动音色表可给不同原字幕编号选择不同音色 |
| 时窗 | 控制器读取实际 24kHz PCM16 WAV 样本数，逐段确认完整声音可放入源字幕窗口 |
| 可编辑内容 | 每次生成的完整声音分别登记；最终声音逐 cue 入 audio 轨，译文/双语逐 cue 入 subtitle 轨 |
| 证据 | 原始 SRT、译文 SRT、双语 SRT、所有语速尝试、实际样本/哈希、设备、模型来源和许可证据、报告 |
| 工程提交 | 全批通过后一次提交；源视频、已有音轨和已有片段保留，字幕窗口不自动移动 |

源 SRT 按原文件顺序处理，原编号和毫秒时码写入报告；重复编号、损坏块、格式指令不静默略过。
当前输入上限 1 MiB、1000 cue、每段 3000 字符、每次声音 300 秒；项目 timebase 须能整除 1000。

## 准备工程并运行

沿用[本地包与模型安装流程](COMMUNITY_LOCAL_DELIVERY.md)，登记两组 CPU/GPU 包及各自 CUDA 库。
统一入口启动器会传入本地设备配置。以下 `source.srt` 必须是真实存在、已校对的字幕。

```powershell
$avk = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
$project = 'E:/video-work/product-ad'
& $avk project init $project --name 'Product ad'
& $avk materials list --kind font
# 内置目录中的稳定 ID；繁体字幕可改用 noto-sans-tc-variable。
& $avk materials ingest --project $project --id noto-sans-sc-variable --asset-id caption_font
```

默认工程已有 `track_audio_1`。创建字幕轨的 `tracks.json`：

```json
{"sequence_id":"seq_main","operations":[{"op":"add_track","track_id":"captions","kind":"subtitle","order":0}]}
```

```powershell
& $avk timeline compose --project $project --input 'E:/video-work/tracks.json'
& $avk dub subtitles --project $project --input 'E:/media/source.srt' --from en --to zh-Hans --device auto --fit reject --apply --audio-track-id track_audio_1 --subtitle-track-id captions --font-asset-id caption_font --dry-run
& $avk dub subtitles --project $project --input 'E:/media/source.srt' --from en --to zh-Hans --device auto --fit reject --apply --audio-track-id track_audio_1 --subtitle-track-id captions --font-asset-id caption_font
& $avk validate --project $project
& $avk render --project $project --output 'E:/video-work/product-ad/renders/ad.mp4'
& $avk quality check --project $project --input 'E:/video-work/product-ad/renders/ad.mp4'
```

`--dry-run` 验证输入、模型包、设备和目标轨道，不加载模型；实际配音时长仍为未知。
不加 `--apply` 时登记资产和证据，保留后续手动编排；不依赖自动生成或覆盖目标轨道。
目标轨道须未锁定、未静音、目标时窗无既有片段，字体须已导入。

## 时长策略与试听选择

默认 `--fit reject`：任何完整配音超窗即拒绝整批，不截台词、不改写译文、不拉伸视频。
查看 `DUBBING_CUE_OVERFLOW` 返回的本地 `failure.json`，试听保留的原始声音后，
可以显式调整字幕窗口/文字或选择下述再生成策略。

```powershell
& $avk dub subtitles --project $project --input 'E:/media/source.srt' --from en --to zh-Hans --fit speed --speed 1 --max-speed 1.6 --device auto
```

最多 3 次完整生成，后续语速由实际超长比例计算且不超过上限；最大允许语速为 2。
原始及每次加速 WAV 都保留为独立资产。更快不代表自然韵律已接受，需比较试听。
仍超长时工程不提交，失败目录保留；同一输出 ID 不覆盖已有输出。

默认中文 `zf_001`、英文 `af_maple`。先用 `voice list` 查目录；逐 cue 表示例：

```json
{"cues":{"2":"zf_002","3":"zf_003"}}
```

通过 `--voice-map E:/media/voices.json` 传入，键为原 SRT 编号；音色须符合目标语言。
它是手动选角，不进行说话人分离，也不克隆参考声音。

## GPU、重叠与恢复

`--device auto/cpu/cuda` 应用于两任务，可用 `--translation-device`、`--voice-device` 分别覆盖。
各自包路径为 `--translation-pack/--translation-gpu-pack`、`--voice-pack/--voice-gpu-pack`，
CUDA 库目录也分别指定；通常使用已登记配置即可。当前 Kokoro CUDA 只支持设备 0。
两个模型顺序执行，不同时驻留；批内复用不等于跨命令常驻缓存。

auto 的真实 CUDA worker 失败可在新目录中重试已验证 CPU 包；取消、超时、坏包、超窗和协议失败不转成 GPU 回退。
`--timeout-seconds` 是全流程预算，`--cancel-file` 可中止运行中的原生 worker。

重叠 SRT 默认拒绝。需要并行声音时，显式 `--overlap-policy mix`，应用的两个轨道也须显式允许重叠。
这不会自动移动字幕或做说话人语义判断。`--timeline-start-tick` 可将整批放到明确偏移。

```powershell
& $avk project recover --project $project --cleanup-jobs --dry-run
& $avk project recover --project $project --cleanup-jobs
```

恢复先处理元数据事务，再按文件身份清理未提交派生输出；已提交资产及许可证据保留。
超窗保留目录在显式清理时会删除，试听/保存需要的失败样例应在清理前完成。
其他任务和旧缓存的完整恢复范围仍见[任务恢复](JOB_RECOVERY.md)。

## 结果与开放条件

成功响应包含 `report`、`assets`、`clips`、`devices`、`total_generations` 和验证结果。
报告逐 cue 给出源文、译文、原时码、音色、各次语速/样本数/哈希及最终资产 ID。
字幕保持原 cue 窗口，声音采用实际时长；没有音素、字词或口型精度承诺。
源字幕、译文和声音默认 unverified/internal；模型许可不能代替内容与目标用途确认。

实际结果、失败、安装版和案例将分别记录在[本批证据目录](../validation/evidence/subtitle-dubbing-20261025-r1/)。
本文没有据此关闭自然听感、语义接受、多语、说话人分离或完整 G19。

English: translate local plain SRT, synthesize complete cue speech with one Kokoro initialization,
check actual WAV samples and commit editable audio/bilingual captions in one transaction.
Explicit speed fitting regenerates whole utterances and retains originals. This is cue-level timing;
naturalness, translation semantics, word alignment, lip sync and content rights remain review items.
