"""Maintain additive three-language material/GPU manuals and README entries.

Requires real installed CPU/GPU verification evidence. Historical release
manuals and published ZIPs remain unchanged.
"""
from pathlib import Path
import argparse
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
PAGE='COMMUNITY_MATERIALS'


def traditional(text, site):
    sys.path.insert(0,str(site))
    from opencc import OpenCC
    preserved=[]
    def keep(match):
        preserved.append(match.group());return 'AEKKEEP%06dEND'%(len(preserved)-1)
    protected=re.sub(r'```[\s\S]*?```|`[^`\n]+`|\]\([^\n)]*\)',keep,text)
    protected=OpenCC('s2twp').convert(protected)
    return re.sub(r'AEKKEEP(\d{6})END',lambda m:preserved[int(m[1])],protected)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    a=parser.parse_args();evidence=a.evidence.resolve()
    cpu=json.loads((evidence/'cpu/verification.json').read_bytes())
    gpu=json.loads((evidence/'gpu/verification.json').read_bytes())
    if not cpu['video_full_decode'] or not gpu['cuda_voice'] or not gpu['cuda_translation']:
        raise ValueError('Real installed verification is required')
    catalog=json.loads((ROOT/'product/src/ai_ad_editor/material_data/catalog.json').read_bytes())
    packs=json.loads((ROOT/'product/src/ai_ad_editor/material_data/model-packs.json').read_bytes())
    voices=json.loads((ROOT/'product/src/ai_ad_editor/material_data/voices.json').read_bytes())
    site=ROOT/'local/agent-ffmpeg/community-packs-r2/opus-zh-en-cpu-int8/site'
    rel=evidence.relative_to(ROOT).as_posix()
    zh=f'''# 开源素材、配音、翻译、配乐与 GPU 使用手册

本轮交付是本机已安装验证的 **CLI 0.1.3 / `v0.1.0-alpha.4-local.1`**。公开 GitHub Release 仍为 alpha.3 / CLI 0.1.2；不要把这些新命令用于旧附件。注册入口仍只有 `$agent-ffmpeg-local-editor`，17 项内部模块继续保留。

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
$aekSkills = if ($env:CODEX_HOME) {{ Join-Path $env:CODEX_HOME 'skills' }} else {{ Join-Path $env:USERPROFILE '.codex/skills' }}
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
{{"entries":[{{"source":"background music","target":"BGM","variants":["背景音乐"]}}]}}
```

术语是明确的译后替换：源词出现且译文有已知 variant 才替换；找不到会拒绝，不声称受约束解码。真实失败示例：`speech` 被通用模型译成“演讲”，应按视频语境改成“原声/语音”。字幕翻译保留时间不代表文本与发音重新对齐。

OPUS 原始归档许可为 CC-BY-4.0；与部分 Hugging Face card 的 Apache 标签冲突时，包保留原始实际许可证和模型署名。Kokoro 权重 Apache-2.0；音色不是用户上传真人克隆。生成配音和派生混音在项目台账仍默认 `unverified/internal`，模型许可不自动变成客户广告的发布权利。

## 真实案例与验收

[逐项素材](COMMUNITY_MATERIAL_CATALOG.md) · [103 音色与实际试听范围](COMMUNITY_VOICES.md) · [本地包与安装](COMMUNITY_LOCAL_DELIVERY.md) · [原始核验](../../{rel}/cpu/verification.json) · [GPU 核验](../../{rel}/gpu/verification.json)。

实际案例保留 12 秒、360×640、30fps、360 帧、独立音轨、SC 字幕与 TC 标题、滤镜、音效和 `.aevpkg.zip` 往返工程。原始配音/混音文件在本地交付目录；未确认发布权利的声音不随公共 README 再分发。公共页面展示由已验证开源资源制作的无配音演示和 GIF，完整本地成片及机器响应另见实测路径。

CPU 专项 {cpu['commands']} 条实际命令、GPU 专项 {gpu['commands']} 条实际命令；不与历史回归合并计数。字幕逆序和重叠、毫秒时间、三音色、UTF-8 文本/语速、缺失/篡改/额外模型文件与严格 CUDA/CPU 回退分别检查。人类听审和语义接受尚未完成，亦未实现完整剪映等价。
'''
    workflow = re.search(r'```powershell\n([\s\S]*?)\n```', zh)[1]
    workflow = workflow.replace('# --apply 需要明确指定未锁定/未静音的 audio 轨道。', '# --apply requires an unlocked, unmuted audio track.').replace('# 素材导入后，用实际返回 ID 编写 timeline compose JSON；视频/字幕/音轨分别编辑。', '# Author timeline compose JSON with returned IDs; video, captions and audio are explicit tracks.')
    en=f'''# Community materials, voice, translation, music and GPU workflow

The verified local build is **CLI 0.1.3 / `v0.1.0-alpha.4-local.1`**. The public GitHub Release remains alpha.3 / CLI 0.1.2; its old archive does not contain these commands. Invoke only `$agent-ffmpeg-local-editor`; its 17 internal modules remain available.

| ID | Module | Implemented | Limits |
|---|---|---|---|
| M01 | Real resources | 44 BGM tracks, 85 jingles, 228 unique SFX and 2 Noto SC/TC fonts: 359 actual files | Five tracks have documented lossy conversion; duplicate SFX have aliases and count once; no commercial stock subscription |
| M02 | Local speech | 103 upstream named Kokoro voices, Chinese/English text or UTF-8 files, speed 0.5–2.0, 24 kHz mono PCM WAV, explicit timeline apply | Three voices actually audition-generated; not 103 human-reviewed voices; no cloning or guaranteed emotion |
| M03 | Translation | OPUS Chinese↔English, simplified/traditional processing, paragraphs, bilingual subtitles and explicit glossary post-edits | SRT cue order/overlap/milliseconds preserved; ASS/VTT styling flattened; no semantic approval |
| M04 | Music preparation | Offset, trim, explicit looping, gain and fades, with original credits | No seam repair or music generation |
| M05 | Mix/ducking | Voice+BGM, sidechain compression, limiter, exact 48 kHz stereo sample count | Original stems retained; no silent voice truncation; PCM metrics are not listening or true-peak acceptance |
| M06 | SFX/fonts | Real CC0 interface/impact/footstep sounds and OFL Noto SC/TC rendering | Retain font licenses/RFN; no redistributed proprietary system fonts |
| G01 | GPU | Voice: CUDA 13/ORT; translation: CUDA 12/CT2 `int8_float16`; `auto/cpu/cuda` | RTX 3060 tested; cold startup may be slower; other devices remain unverified |
| G02 | Device policy | Free VRAM preflight: 3072 MiB voice, 1536 MiB translation; explicit fallback reasons | Thresholds cannot prevent every OOM; strict CUDA fails clearly; other GPU processes stay running |
| M07 | Offline packs | Bundled base assets plus four optional hash-pinned model packs, isolated workers/native installer | No environment creation or implicit network; changed/missing packs are rejected |

## Complete workflow

Set `$avk` to the unified Skill launcher. The local registration supplies existing CPU/GPU pack paths and NVIDIA library directories. `--device auto` prefers the available GPU; standalone installs may pass `--pack`, `--gpu-pack` and `--cuda-library-directory` explicitly. Nothing is downloaded during editing or inference.

```powershell
{workflow}
```

1. Run `version`, `gpu inspect`, `model-pack list` and create the project.
2. Search/inspect resources, ingest music/SFX/fonts, and select a named voice.
3. Generate speech from the actual local text file. Translate the supplied subtitle file, retaining cue timings.
4. Prepare BGM to cover the natural speech duration; mix/duck without overwriting stems.
5. Author explicit video, subtitle and audio tracks with returned asset IDs. `--apply` requires an unlocked, unmuted audio track.
6. Validate, preview, render, check the encoded file, and export the editable package.

The sample text/subtitle files must exist. If speech exceeds the requested 12-second edit, extend the bed/edit instead of cutting the line. Inspect `ok`, `status`, `errors`, `warnings`, `data.device`, inference provider and actual files.

Text size/width uses author-canvas pixels. `preview --height` scales a preview; `render --width/--height` changes the composition raster rather than simply resizing a completed frame. Set `update_sequence.patch.canvas` to the intended final dimensions, author matching text styles and render at that size. The original cropped-text attempt is retained; eight separate follow-up commands verify corrected preview/render/package output.

## GPU compatibility and performance

| Path | Model/computation | Dependencies | Verified scope |
|---|---|---|---|
| CPU voice | Kokoro int8 ONNX | sherpa-onnx 2.0.0 / ORT 1.28.2 | Native Windows CPython 3.13 x64 |
| CUDA voice | Upstream unquantized ONNX / Float32 | NVIDIA driver, CUDA 13, cuDNN 9 and optional GPU pack | RTX 3060; voice adapter currently device 0 only |
| CPU translation | OPUS int8 | Source-built CT2 4.8.3 + Ruy, no MKL/cuDNN/Intel OpenMP | Both directions, text and subtitles |
| CUDA translation | Same OPUS int8 weights / `int8_float16` computation | CUDA 12 cuBLAS and optional GPU pack | RTX 3060; explicit device index |
| AMD/Intel/Apple GPU | Not integrated | `auto` may use verified CPU path | No claimed GPU support |

With the same Float32 voice model and ~6.85 seconds of text, second generation took ~4.93 s CPU versus ~0.62 s CUDA; loading took ~4.08 s CPU versus ~7.54 s CUDA. Other device workloads were running. The ~8× generation improvement is not an end-to-end single-CLI guarantee. A CUDA translation example took ~0.38 s on first generation and ~0.037 s on repeat, excluding full CLI startup/hash checks. Cold/warm times remain separate.

Open-source engine/model licenses are separate from optional GPU dependencies. NVIDIA driver/CUDA/cuDNN have their own proprietary terms; upstream Windows GPU binaries also preserve supplied third-party terms, including Intel runtime where present. They are not described as open-source media assets. Use the separate Ruy CPU path to avoid proprietary numerical backends. This change does not move all FFmpeg filters onto the GPU.

`auto` checks free memory and records CPU fallback. A real CUDA worker failure may retry CPU only before any output exists; its failed-worker log remains in the response. Missing/changed pack contents never bypass integrity checks. `cuda` is strict and returns failure. No other GPU tasks are stopped.

## Portable model packs

Use `scripts/install_community_pack.py --archive <local.zip> --sha256 <archive-hash> --catalog <installed/site/ai_ad_editor/material_data/model-packs.json> --id <pack-id> --target <new-local-path>`. The local parent must exist; target must not. The installer verifies the installed CLI's manifest pin and every file before moving its staging directory. It refuses overwritten targets, wrong digests, missing/extra/duplicate files, unsafe paths and modified model data. It uses neither network nor global pip.

## Translation, glossary and rights

Supported directions are `en ↔ zh-Hans/zh-Hant`. Simplified/traditional conversion happens on the Chinese side. Text: one paragraph per line, up to 1000; subtitles: up to 1000 cues; each unit up to 512 model tokens. Reaching the decoder limit is an error. Source text, translation, scores, model digest and cue timing are retained.

```json
{{"entries":[{{"source":"background music","target":"BGM","variants":["背景音乐"]}}]}}
```

This is explicit post-editing, not constrained decoding. If a source term occurs but the expected translated variant cannot be found, the command refuses output. The actual generic-model error `speech`→“演讲” remains documented; video context needs review. Retained cue times do not mean new forced alignment.

Original OPUS archives carry CC-BY-4.0. Where a model card has a conflicting Apache label, the actual archived license/attribution is retained. Kokoro weights are Apache-2.0; this workflow does not clone an uploaded person. Generated speech/derived mixes remain `unverified/internal` in the project ledger until project-context/output rights are reviewed.

## Actual evidence and cases

[359-file catalog](COMMUNITY_MATERIAL_CATALOG.md) · [103 voices and generated audition scope](COMMUNITY_VOICES.md) · [Local package and installation](COMMUNITY_LOCAL_DELIVERY.md) · [CPU evidence](../../{rel}/cpu/verification.json) · [GPU evidence](../../{rel}/gpu/verification.json).

The actual edit is 12 s, 360×640, 30 fps, 360 decoded frames, with separate audio, SC captions, TC title, look/SFX and editable-package round trip. Speech/mixes remain in the local delivery folder while publication rights are unresolved. Public examples use verified open resources without redistributing those generated voices. The full local output and JSON response paths remain in the evidence.

CPU: {cpu['commands']} actual commands; GPU: {gpu['commands']} actual commands, separate from historical regression totals. Tests include three voices, UTF-8 input/speed, unordered/overlapping millisecond cues, corrupt/missing/extra pack files, strict CUDA and explicit CPU fallback. Human listening, semantic approval and complete CapCut parity remain open.
'''
    for suffix,text in [('',zh),('.en',en),('.zh-TW',traditional(zh,site))]:
        (ROOT/('docs/product/'+PAGE+suffix+'.md')).write_text(text,encoding='utf8',newline='\n')
    # Actual per-file metadata: no invented mood, age or effectiveness labels.
    collections={r['id']:r for r in catalog['collections']}
    lines=['# 社区素材逐项目录 / Community material inventory','',
           '359 个实际文件；音轨时长/编码来自 ffprobe。名称保留上游事实，不推断未试听的情绪或客户适配度。',
           '','[使用手册](COMMUNITY_MATERIALS.md) · [English](COMMUNITY_MATERIALS.en.md) · [繁體中文](COMMUNITY_MATERIALS.zh-TW.md)','',
           '| # | 稳定 ID / Stable ID | 名称 / Name | 类别 | 时长/格式 | 来源/许可 | SHA-256 |','|---|---|---|---|---|---|---|']
    for i,row in enumerate(catalog['records'],1):
        col=collections[row['collection_id']];m=row['media']
        media=(f"{m.get('duration_seconds',0):.3f}s; {m.get('codec','')} / {m.get('sample_rate','')}Hz / {m.get('channels','')}ch" if row['kind']!='font' else 'Variable TTF; '+str(row['bytes'])+' bytes')
        lines.append(f"| A{i:03d} | `{row['id']}` | {row['name']} | {row['kind']} / {row['category']} | {media} | [{col['creator']}]({col['source_url']}); {col['license']['spdx']} | `{row['sha256']}` |")
    lines+=['','完整来源、转码、别名与单文件媒体信息见应用内 `materials inspect --id <id>`；许可随 `materials ingest` 复制进工程。',
            '模型包与每种原始权利分开列明；基础文件不包含任何模型权重。']
    (ROOT/'docs/product/COMMUNITY_MATERIAL_CATALOG.md').write_text('\n'.join(lines)+'\n',encoding='utf8',newline='\n')
    lines=['# 103 个具名音色 / Named voices','',
           '来自 Kokoro v1.1 中文/英文上游映射，3 英文女声、55 中文女声、45 中文男声。性别/语言标签来自上游，不代表真人身份或授权克隆。',
           '实际常规试听产物：`zf_001`、`zm_009`、`af_maple`。另有同模型 CPU/CUDA 比较；人工听审尚未完成，未为其余 100 个音色编造试听评价。',
           '','| # | ID | speaker_id | 语言 / Language | 上游标签 | 实测范围 |','|---|---|---|---|---|---|']
    for i,row in enumerate(voices['voices'],1):
        scope='实际生成 WAV / WAV generated' if row['id'] in {'zf_001','zm_009','af_maple'} else '映射已核验，未逐音色推理/听审'
        lines.append(f"| V{i:03d} | `{row['id']}` | {row['speaker_id']} | {row['language']} | {row['gender']} | {scope} |")
    lines+=['','生成试听用 `voice synthesize --voice <id>`，检查实际设备、时长、输出与输入文案，再向客户选型；切勿仅按编号推断年龄、声线或商业适用性。']
    (ROOT/'docs/product/COMMUNITY_VOICES.md').write_text('\n'.join(lines)+'\n',encoding='utf8',newline='\n')
    # Add documentation without truncating the restored feature/Skill/case tables.
    for suffix,language in [('', 'zh'),('.zh-TW','tw'),('.en','en')]:
        path=ROOT/('README'+suffix+'.md');s=path.read_text('utf8')
        start='<!-- community-materials-gpu -->';end='<!-- /community-materials-gpu -->'
        if start in s:s=re.sub(re.escape(start)+r'[\s\S]*?'+re.escape(end)+'\n*','',s)
        if language=='en':
            block=f'''{start}

**Local installed extension: CLI 0.1.3, GPU voice/translation and 359 bundled open resources.** The public alpha.3 attachments remain unchanged. Invoke the single `$agent-ffmpeg-local-editor` entry; its updated local registration prefers configured GPU packs, records the actual device/fallback, and retains CPU compatibility.

[Complete workflow and limits](docs/product/COMMUNITY_MATERIALS.en.md) · [Resource catalog](docs/product/COMMUNITY_MATERIAL_CATALOG.md) · [103 named voices and actual audition scope](docs/product/COMMUNITY_VOICES.md) · [CPU evidence]({rel}/cpu/verification.json) · [GPU evidence]({rel}/gpu/verification.json).

| Extension | Actual implementation | Limits |
|---|---|---|
| F44 / M01 | 44 BGM, 85 jingles, 228 unique SFX, 2 OFL Noto fonts | Source licenses/attribution remain separate; no stock subscription |
| F45 / M02 | Chinese/English speech, 103 named voices, text files/speed/WAV | Three voices generated for audition; no cloning or universal voice-quality approval |
| F46 / M03 | Offline bidirectional translation, bilingual SRT, glossary | Cue order/milliseconds retained; translation and pronunciation need review |
| F47 / G01 | CUDA voice/translation, auto/cpu/cuda, free-VRAM preflight | RTX 3060 tested; strict CUDA and explicit CPU fallback; optional NVIDIA runtime terms |
| F48 / M04–M05 | Real BGM trim/loop/fades, speech/music mix and ducking | Preserved stems; no composition or automatic seam repair |

CPU {cpu['commands']} commands and GPU {gpu['commands']} commands are separate current tests. The real 12-second edit was fully decoded and package-round-tripped. Public examples omit speech whose publication rights remain unverified; local original stems and complete outputs remain available in delivery records. Human listening and full CapCut equivalence remain open.

{end}

'''
        else:
            block=f'''{start}

**本机新增已安装扩展：CLI 0.1.3，GPU 配音/翻译与 359 项内置开源资源。** 公开 alpha.3 附件保持原版。外层只指定 `$agent-ffmpeg-local-editor`；本机登记 GPU 包后默认优先 GPU，明确返回实际设备/回退原因，保留 CPU 兼容。

[完整流程与边界](docs/product/COMMUNITY_MATERIALS{suffix}.md) · [逐项素材目录](docs/product/COMMUNITY_MATERIAL_CATALOG.md) · [103 音色与实际试听范围](docs/product/COMMUNITY_VOICES.md) · [CPU 实测]({rel}/cpu/verification.json) · [GPU 实测]({rel}/gpu/verification.json)。

| 扩展编号 | 已实现 | 边界 |
|---|---|---|
| F44 / M01 | 44 首 BGM、85 个短乐、228 个独立音效、2 个 OFL Noto 字体 | 分别保留来源/许可，不是商业素材订阅库 |
| F45 / M02 | 中英配音、103 具名音色、文本文件/语速/WAV | 实际常规生成试听 3 音色，不克隆、不宣称全音色听审 |
| F46 / M03 | 本地双向翻译、双语 SRT、显式术语表 | cue 顺序/毫秒保留，语义/发音仍需校对 |
| F47 / G01 | CUDA 配音/翻译、auto/cpu/cuda、显存预检 | RTX 3060 实测，严格 CUDA/CPU 回退分明，NVIDIA 依赖许可另列 |
| F48 / M04–M05 | 真实 BGM 截取/循环/淡入淡出、配音混合和闪避 | 保留原分轨，不代表作曲或自动接缝修复 |

CPU {cpu['commands']} 条、GPU {gpu['commands']} 条为本轮独立实测。12 秒真实成片已完整解码、工程往返。未确认发布权利的生成配音不随公共页面再分发，本地原始分轨/完整成片见交付记录。人工听审与完整剪映等价仍未完成。

{end}

'''
            if language=='tw':block=traditional(block,site)
        s=s.replace('## ',block+'## ',1)
        if '| R33 |' not in s:
            index=s.find('| R32 |');line_end=s.find('\n',index)
            if index<0:raise ValueError('R32 historical row missing')
            if language=='en':
                rows=f"\n| R33 | Installed community/CPU extension | {cpu['commands']} actual commands; 359 assets, three generated voices, 12 s / 360 decoded frames, subtitle timing and package round trip | [Evidence]({rel}/cpu/verification.json); human listening/semantic acceptance open |\n| R34 | Installed CUDA extension | {gpu['commands']} actual commands; GPU voice and translation, strict failure, CPU/worker fallback | [Evidence]({rel}/gpu/verification.json); RTX 3060 only, cold/warm times separate |"
            else:
                rows=f"\n| R33 | 新安装社区素材/CPU 扩展 | {cpu['commands']} 条实际命令；359 素材、3 音色、12 秒 / 360 帧完整解码、字幕时间及工程往返 | [证据]({rel}/cpu/verification.json)；人工听审/语义接受未完成 |\n| R34 | 新安装 CUDA 扩展 | {gpu['commands']} 条实际命令；GPU 配音与翻译、严格失败、CPU/worker 回退 | [证据]({rel}/gpu/verification.json)；仅 RTX 3060，冷启动/持续推理分列 |"
                if language=='tw':rows=traditional(rows,site)
            s=s[:line_end]+rows+s[line_end:]
        path.write_text(s,encoding='utf8',newline='\n')
    maintain_existing_docs(site, rel, cpu, gpu)
    print(json.dumps(dict(status='written',materials=359,voices=103,readmes=3,cpu_commands=cpu['commands'],gpu_commands=gpu['commands'])))


def maintain_existing_docs(site, rel, cpu, gpu):
    """Preserve historical manuals while marking the current local extension."""
    for suffix, language in [('', 'zh'), ('.en', 'en'), ('.zh-TW', 'tw')]:
        en = language == 'en'
        details = 'COMMUNITY_MATERIALS' + suffix + '.md'
        current = ('**Current local extension: CLI 0.1.3.** GPU speech/translation, 359 bundled resources and offline model packs are installed and verified. '
                   'The alpha.3 sections below remain the historical CLI 0.1.2 baseline. '
                   if en else '**当前本机扩展：CLI 0.1.3。** GPU 配音/翻译、359 项内置资源与离线模型包已安装实测；以下 alpha.3 内容保留为历史 CLI 0.1.2 基线。')
        if language == 'tw': current = traditional(current, site)
        services = ('''| S13 | Bundled community resources | Offline catalog | 359 source/license-pinned music/jingle/SFX/font files | `materials list/inspect/verify/ingest` | Per-resource rights; no commercial stock subscription |
| S14 | Local speech/translation | Native model workers | Four optional pinned CPU/CUDA packs; 103 voice mappings and OPUS text/subtitles | `voice / translate / model-pack` | Three audition voices generated; human review remains separate |
| S15 | BGM preparation and mixing | Native FFmpeg audio | Explicit trim/loop/fades, independent voice/music stems and ducking | `music prepare/mix` | No composition, voice truncation or seam-repair promise |
| S16 | GPU compatibility | Native NVIDIA libraries | `auto/cpu/cuda`, free-VRAM check, explicit provider/fallback | `gpu inspect; --device` | RTX 3060 tested; optional NVIDIA/Intel terms preserved |'''
                    if en else '''| S13 | 内置社区素材服务 | 离线目录 | 359 项有来源/许可的 BGM、短乐、音效、字体 | `materials list/inspect/verify/ingest` | 逐项权利，不是商业素材订阅库 |
| S14 | 本地配音/翻译 | 原生模型 worker | 4 个可选 CPU/CUDA 包，103 音色映射和 OPUS 文本/字幕 | `voice / translate / model-pack` | 实际生成 3 音色试听文件，人工验收另列 |
| S15 | 配乐准备与混音 | 原生 FFmpeg 音频 | 显式截取/循环/淡化、独立人声/配乐、闪避 | `music prepare/mix` | 不作曲、不静默裁人声、不承诺接缝修复 |
| S16 | GPU 兼容服务 | 原生 NVIDIA 运行库 | auto/cpu/cuda、显存预检、实际 provider/回退 | `gpu inspect; --device` | RTX 3060 实测，NVIDIA/Intel 依赖许可另列 |''')
        if language == 'tw': services = traditional(services, site)
        for filename in ('README' + suffix + '.md', 'docs/product/CAPABILITIES' + suffix + '.md'):
            path = ROOT / filename
            s = path.read_text('utf8').replace('`17 agent-ffmpeg-local-* Skills`', '`$agent-ffmpeg-local-editor` / K01–K17')
            s = re.sub(r'^\| S1[3-6] \|.*\n?', '', s, flags=re.M)
            index = s.find('| S12 |')
            if index < 0: raise ValueError('Service table missing: ' + filename)
            end = s.find('\n', index)
            s = s[:end] + '\n' + services + s[end:]
            if filename.startswith('docs/'):
                marker = '<!-- community-current -->'
                s = re.sub(re.escape(marker) + r'[\s\S]*?<!-- /community-current -->\n*', '', s)
                block = marker + '\n\n' + current + f' [Details]({details}) · [Local delivery](COMMUNITY_LOCAL_DELIVERY.md) · [Current installed capabilities](community-capabilities.json)\n\n<!-- /community-current -->\n\n'
                s = s.replace('\n\n', '\n\n' + block, 1)
            else:
                if en:
                    s = s.replace('**Release: v0.1.0-alpha.3', '**Public release: v0.1.0-alpha.3')
                    s = s.replace('## 43 functional documentation modules', '## 43 base functional modules, plus F44–F48 above')
                    s = s.replace('## Download and render your first video', '## Public alpha.3: download and render your first video')
                    unified = '**One registered entry: `$agent-ffmpeg-local-editor`.** The current local GPU extension uses the [r2 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r2.zip) and matching [local bundle/model installation](docs/product/COMMUNITY_LOCAL_DELIVERY.md). Its 17 internal modules are loaded as needed. The historical r1 kit remains paired with the unchanged public alpha.3 runtime below.'
                else:
                    s = s.replace('**发行版本：', '**公开发行版本：').replace('**發行版本：', '**公開發行版本：')
                    s = s.replace('## 43 个功能说明模块', '## 43 个基础功能模块，以及上方 F44–F48 扩展').replace('## 43 個功能說明模塊', '## 43 個基礎功能模塊，以及上方 F44–F48 擴充')
                    s = s.replace('## 下载并跑通第一条视频', '## 公开 alpha.3：下载并跑通第一条视频').replace('## 下載並跑通第一條影片', '## 公開 alpha.3：下載並跑通第一條影片')
                    unified = '**只注册一个入口：`$agent-ffmpeg-local-editor`。** 当前本机 GPU 扩展使用 [r2 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r2.zip) 与匹配的[本地运行包/模型安装流程](docs/product/COMMUNITY_LOCAL_DELIVERY.md)，17 项内部模块按需加载。历史 r1 kit 继续匹配下方保持原版的公开 alpha.3 运行包。'
                    if language == 'tw': unified = traditional(unified, site)
                s = re.sub(r'<!-- unified-skill-registration -->[\s\S]*?<!-- /unified-skill-registration -->', '<!-- unified-skill-registration -->\n\n' + unified + '\n\n<!-- /unified-skill-registration -->', s)
                s = re.sub(r'^\| R3[5-7] \|.*\n?', '', s, flags=re.M)
                row_end = s.find('\n', s.find('| R34 |'))
                if en:
                    newrows = f'\n| R35 | Portable model installation | Four actual model ZIPs; eight install/refusal calls in a Chinese/spaced path | [Evidence]({rel}/portable/verification.json); original files preserved, failed staging cleaned |\n| R36 | Real registered Skill with GPU defaults | 11 actual CLI calls; one discovery entry, default CUDA speech/translation and explicit CPU | [Evidence]({rel}/skill/verification.json); installed runtime only |\n| R37 | Corrected presentation and public example | Eight follow-up layout calls, no new inference; 14 separate public-example calls; both decode 360 frames | [Layout]({rel}/cpu/presentation-correction/verification.json) · [MP4/GIF](docs/assets/community-materials-20261025-r2/verification.json); first cropped-text case retained, no human listening |'
                else:
                    newrows = f'\n| R35 | 可移动模型安装 | 4 个模型 ZIP；中文/空格路径下 8 条安装/拒绝命令 | [证据]({rel}/portable/verification.json)；原文件不变、失败 staging 清理 |\n| R36 | 真正注册入口与 GPU 默认值 | 11 条实际 CLI；1 个发现入口，默认配音/翻译 CUDA，显式 CPU | [证据]({rel}/skill/verification.json)；只调用已安装版 |\n| R37 | 排版修正与公开样例 | 8 条修正命令、0 新推理；另 14 条公开案例命令；均完整解码 360 帧 | [排版]({rel}/cpu/presentation-correction/verification.json) · [MP4/GIF](docs/assets/community-materials-20261025-r2/verification.json)；保留首次文字溢出，未做人工听审 |'
                    if language == 'tw': newrows = traditional(newrows, site)
                if row_end < 0: raise ValueError('Current R34 table row missing')
                s = s[:row_end] + newrows + s[row_end:]
                marker = '<!-- community-cases -->'
                s = re.sub(re.escape(marker) + r'[\s\S]*?<!-- /community-cases -->\n*', '', s)
                cases = (f'''{marker}

**C10–C12: actual local extension cases.** C10 retains three speech WAVs, bilingual captions, BGM/ducked stems, an editable project and a corrected 12-second video locally. C11 actually invokes the registered Skill with default GPU speech/translation, while retaining explicit CPU. C12 is the publishable music/SFX/font example below; the GIF is silent and the MP4 includes licensed music/SFX. Generated speech is kept in local review records.

![Actual community resource edit](docs/assets/community-materials-20261025-r2/community-resources.gif)

[MP4](docs/assets/community-materials-20261025-r2/community-resources.mp4) · [Original art](docs/assets/release-v0.1.0-alpha.3-r1/input/card-1.png) · [Sources/licenses](docs/assets/community-materials-20261025-r2/SOURCE_AND_LICENSES.md) · [Steps and limits](docs/product/COMMUNITY_MATERIALS.en.md) · [Acceptance and remaining product gaps](docs/product/COMMUNITY_ACCEPTANCE.md).

<!-- /community-cases -->

''' if en else f'''{marker}

**C10–C12：本轮真实案例。** C10 在本机保留 3 个音色 WAV、双语字幕、BGM/闪避分轨、可编辑工程和修正后的 12 秒成片；C11 从真正注册入口执行默认 GPU 配音/翻译并验证显式 CPU；C12 为下方可公开音乐/音效/字体演示。GIF 无声，MP4 含有明确来源的音乐/音效；生成配音保留在本地审阅记录中。

![实际社区素材编辑](docs/assets/community-materials-20261025-r2/community-resources.gif)

[MP4](docs/assets/community-materials-20261025-r2/community-resources.mp4) · [原始图片](docs/assets/release-v0.1.0-alpha.3-r1/input/card-1.png) · [来源/许可](docs/assets/community-materials-20261025-r2/SOURCE_AND_LICENSES.md) · [完整步骤与边界](docs/product/COMMUNITY_MATERIALS{suffix}.md) · [验收与总产品剩余差距](docs/product/COMMUNITY_ACCEPTANCE.md)。

<!-- /community-cases -->

''')
                if language == 'tw': cases = traditional(cases, site)
                headings = ['## 完整案例、原输入、实际输出与 GIF', '## 完整案例、原輸入、實際輸出與 GIF', '## Complete cases, original inputs, actual output and GIFs']
                target_heading = next((h for h in headings if h in s), None)
                if not target_heading: raise ValueError('Case section missing: ' + filename)
                s = s.replace(target_heading + '\n\n', target_heading + '\n\n' + cases, 1)
                note_start, note_end = '<!-- community-supplementary-checks -->', '<!-- /community-supplementary-checks -->'
                s = re.sub(re.escape(note_start) + r'[\s\S]*?' + re.escape(note_end) + '\n*', '', s)
                note = (f'{note_start}\n\nAdditional checks stay separate: [22 existing subtitle regression tests]({rel}/subtitle-regression.json) pass against the installed package; [five actual calls from the extracted small kit]({rel}/kit/verification.json) verify its own configuration, isolated registration and default CUDA translation. These are not additional voices or a full historical regression rerun.\n\n{note_end}\n\n' if en else f'{note_start}\n\n附加检查单独记录：[22 项既有字幕回归]({rel}/subtitle-regression.json)在安装版通过；[小型 Skill kit 解包后的 5 次实际调用]({rel}/kit/verification.json)验证了独立配置、隔离发现目录注册与默认 CUDA 翻译。不计作新增音色或历史全量重跑。\n\n{note_end}\n\n')
                if language == 'tw': note = traditional(note, site)
                section = next(h for h in ('## 功能核验与发布证据', '## 功能核驗與發布證據', '## Functional verification and release evidence') if h in s)
                s = s.replace(section + '\n\n', section + '\n\n' + note, 1)
            path.write_text(s, encoding='utf8', newline='\n')
        for filename in ('docs/product/SKILLS' + suffix + '.md', 'docs/skills/UNIFIED_SKILL' + suffix + '.md'):
            path = ROOT / filename
            s = path.read_text('utf8')
            marker = '<!-- community-current -->'
            s = re.sub(re.escape(marker) + r'[\s\S]*?<!-- /community-current -->\n*', '', s)
            prefix = '../product/' if '/skills/' in filename else ''
            block = marker + '\n\n' + current + f' [Workflow]({prefix}{details}) · [Local installation]({prefix}COMMUNITY_LOCAL_DELIVERY.md)\n\n<!-- /community-current -->\n\n'
            s = s.replace('\n\n', '\n\n' + block, 1)
            if '/skills/' in filename:
                archived = ('## Archived alpha.3 / r1 instructions\n\n' if en else '## alpha.3 / r1 历史流程（以下原文保留）\n\n')
                if language == 'tw': archived = traditional(archived, site)
                if '## Archived alpha.3 / r1' not in s and '## alpha.3 / r1 ' not in s:
                    mark = '<!-- /community-current -->\n\n'
                    s = s.replace(mark, mark + archived, 1)
            if '/product/SKILLS' in filename:
                s = s.replace('`media adapter; asr adapter; ocr; face; tts`', '`media adapter; asr adapter; ocr; face; tts; voice; translate; gpu`')
            path.write_text(s, encoding='utf8', newline='\n')
    for filename in ('docs/README.md', 'docs/local/INSTALLATION.md', 'docs/product/GOAL_GAPS_20261024.md'):
        path = ROOT / filename
        s = path.read_text('utf8')
        marker = '<!-- community-current -->'
        s = re.sub(re.escape(marker) + r'[\s\S]*?<!-- /community-current -->\n*', '', s)
        prefix = 'product/' if filename == 'docs/README.md' else '../product/' if '/local/' in filename else ''
        block = marker + '\n\n当前本机已更新到 **CLI 0.1.3 / GPU 配音与翻译 / 359 项内置资源 / 单一 Skill**。以下原安装/差距记录按其原版本保留。' + f' [新增完整流程]({prefix}COMMUNITY_MATERIALS.md) · [本地离线交付]({prefix}COMMUNITY_LOCAL_DELIVERY.md) · [本轮验收与剩余差距]({prefix}COMMUNITY_ACCEPTANCE.md)\n\n<!-- /community-current -->\n\n'
        s = s.replace('\n\n', '\n\n' + block, 1)
        path.write_text(s, encoding='utf8', newline='\n')


if __name__=='__main__':main()
