"""Synchronize current functional/readme entries with completed 500-look evidence."""
from pathlib import Path
from collections import Counter
import json
import re

from build_look_profile_docs import traditional

ROOT=Path(__file__).resolve().parents[1]
TAG='v0.1.0-alpha.3'
E='docs/validation/evidence/look500-20261024-r1'


def main():
    catalog=json.loads((ROOT/'product/src/ai_ad_editor/look_data/catalog.json').read_bytes())
    reg=json.loads((ROOT/E/'regression-policy.json').read_bytes())
    installed=json.loads((ROOT/E/'installed/verification.json').read_bytes())
    skills=json.loads((ROOT/E/'skills/verification.json').read_bytes())
    installation=json.loads((ROOT/E/'install/installation.json').read_bytes())
    assert all(r.get('status')=='passed' for r in (reg,installed,skills))
    categories=Counter(r['category'] for r in catalog['records'])
    shared_commands="""```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk look list --query '黑白'
& $avk look list --query 'CC0-1.0'
& $avk look inspect --id fl-0000001-action-magenta-01
& $avk look preview --id fl-0000001-action-magenta-01 --output 'E:/video-work/magenta-preview.png' --strength 0.65
& $avk look apply --project 'E:/video-work/my-ad' --id fl-0000001-action-magenta-01 --global --strength 0.65 --dry-run
& $avk look apply --project 'E:/video-work/my-ad' --id fl-0000001-action-magenta-01 --global --strength 0.65
```
"""
    functional="""# 滤镜功能 README：500 套内置风格

[简体中文](FILTERS.md) · [繁體中文](FILTERS.zh-TW.md) · [English](FILTERS.en.md)

当前安装版为 **v0.1.0-alpha.3 / CLI 0.1.2 / 目录 2.0.0**。500 套均随包离线安装，Agent 可以检索、读取实际效果、预览并应用到片段或全局。原 100 套的 ID 和 LUT 字节保持兼容。

## 功能与使用逻辑

| # | 功能 | 实际行为 |
|---|---|---|
| P01 | 命名与编号 | 001–100 保留 sp-/t3-；101–500 使用 nt-/fl-；命令使用稳定 ID |
| P02 | 搜索 | 简体/繁体名称、英文、ID、简体/英文描述、许可及分类 |
| P03 | inspect | 每套的实际灰阶/肤色/RGB 作用、场景建议、试用强度、网格、作者、许可、锁定来源与哈希 |
| P04 | preview | 使用内置合成卡或本地 SDR 图片输出新 PNG；支持静态 0–1 强度，保护已有文件 |
| P05 | apply | 显式 --clip-id 或 --global；默认替换同作用域的内置预设，保留手工效果；--append 才叠加 |
| P06 | 事务与证据 | dry-run 不写文件；实际应用复制 LUT/许可/来源，登记台账、快照、幂等重试；修改过的项目资源拒绝覆盖 |
| P07 | 旧版兼容 | 识别 alpha.2 预设标记；精确匹配旧证据时保留原字节；项目包往返保留稳定 LUT ID 和资源许可 |
| P08 | 许可区分 | MIT 100、CC BY-SA 267、CC0 133；按每套许可复制署名、变更与再分发义务 |

使用顺序：**list 选候选 → inspect 读详情和许可 → preview 比较适合素材的强度 → dry-run 确认作用域 → apply → render → 解码核验**。

"""+shared_commands+"""
## 全部命名与详细说明

[500 套编号及实际作用总表](LOOK_PRESETS.md)。每套有原名、来源前缀、唯一 ID 和逐项说明；新名称带实测中灰偏向/明暗/跨度提示。

| 编号 | 逐项详情 |
|---|---|
| 001–100 | [保留的原始风格](look-profiles/001-100.md) |
| 101–200 | [新增风格与原始曲线变体](look-profiles/101-200.md) |
| 201–300 | [新增风格与原始曲线变体](look-profiles/201-300.md) |
| 301–400 | [新增胶片与社区创意](look-profiles/301-400.md) |
| 401–500 | [新增社区创意色彩](look-profiles/401-500.md) |

每份详情包含 7 个灰阶、3 个肤色和红绿蓝 3 个色块的输入/输出，Y′ 码值、中段跨度、使用建议、试用强度、注意点、作者/来源/许可、转换误差、LUT 摘要和真实 PNG/MP4。

**500 指不同的实际数值变换，含同系列上游曲线变体，不代表 500 个独立风格家族。** 上游的 +/− 后缀写进 ID；不将同一 LUT 的强度或格式副本计为新预设。全部通过共同 17³ 色网格签名与参考预览去重。

## 类别与来源

| 类别 | 数量 |
|---|---:|
"""+'\n'.join(f'| `{k}` | {n} |' for k,n in categories.items())+"""

类别沿用来源分组，拍立得与负片组也含黑白变体，以每套实测说明为准。来源：Striped Purple 49、t3mujinpack 51、Natron 267、FreshLUTs 133。Natron 原始 Hald 转换为 33³；原有 CUBE 与新增 FreshLUTs CUBE 保留原网格。目录记录逐项采样误差和输入假设。FreshLUTs 按明确的上传者 Rec.709 标签选择，未将未知、Log 或 HLG 标签改判为 SDR；这不是独立相机校准。`fl-0000228-science-fiction-for-flog` 的标签为 Rec.709，但标题提到 FLog，输入域存在歧义，仅作为已准备 SDR 的实验创意比较，不作为已验证的 FLog 转换。

CC BY-SA LUT 及改编预览需要保留作者/来源、标明转换并按相同或兼容许可再分发。软件本体 MIT 不能代替资源许可。[完整通知与锁定来源](../releases/v0.1.0-alpha.3/THIRD_PARTY.md)。

## 实际输出与核验

![原视频与新增风格实际成片](../assets/look500-20261024-r1/motion-comparison.gif)

[原视频](../assets/look500-20261024-r1/original.mp4) · [500 套实际预览总览](../assets/look500-20261024-r1/contact-sheet.jpg) · [逐项 PNG/MP4](LOOK_PRESETS.md) · [当轮核验及失败修复](../validation/LOOK500_20261024.md)。

## 色彩与效果范围

LUT 只执行逐像素色彩映射；不产生颗粒、光晕、暗角、空间雾、美颜或 AI 特效。场景/强度是试片建议；合成色块不代表肤色保护或自然素材验收。Y′ 和跨度是编码 RGB 的对照量，不是曝光、线性亮度或主观评分。

`look apply` 用于默认 FFmpeg 的 SDR 管线；Float32/Log/HDR 显式拒绝。先按独立色彩契约转换素材再选风格。静态强度混合的是编码 RGB，不是线性光。

原有 46 个效果处理算子与 500 套风格是两种计数。用户仍可用 `lut register` 登记本地 `.cube/.3dl/.csp/.dat`；默认路径的部分强度以完整 3D CUBE 为准，非 CUBE 只记录有限元数据。显式 Float32 路径另支持完整 CUBE 的 1D/3D/1D shaper，必须声明信号、域与预算；两条路径能力不同。

## 自定义 LUT 与底层效果

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk effects list
& $avk effects inspect --name lut3d
& $avk lut register --help
& $avk lut register --project 'E:/video-work/my-project' --input 'E:/looks/cinematic.cube' --name 'My look'
```

登记后，把返回的 `lut_id` 加入时间线的 LUT 效果，再预览、渲染；单纯登记文件不会改变画面。自带素材需要补全实际许可和来源。底层动态强度使用编码 8-bit RGB 混合；核对 `effects inspect --name lut3d`、`effects.numeric_effect_automation` 和所选渲染路径。登记器部分历史限制字段只描述静态处理，不能据此推断所有路径的能力。

显式 `float32-native-v1` 读取完整 CUBE 的 1D、3D 或 shaper+3D，不读取 `.3dl/.csp/.dat`；默认 FFmpeg 路径不会自动获得 1D 支持。剪映专有滤镜包与任意第三方插件不属于标准 LUT 的兼容范围。

[历史 Float32/shaper 安装版实测](../validation/evidence/float-shaper-20261023-lab/installed-r1/verification.json) · [历史真实对照 GIF](../assets/float-shaper-20261023-installed-r1/formal-comparison.gif)。这些结果不计入本轮 500 套核验。

[安装与 Skill](INSTALLATION.md) · [新版使用手册](../releases/v0.1.0-alpha.3/USAGE.md) · [历史 100 套测量](LOOK_PRESET_DETAILS.md)。
"""
    (ROOT/'docs/local/FILTERS.md').write_text(functional,encoding='utf-8',newline='\n')
    (ROOT/'docs/local/FILTERS.zh-TW.md').write_text(traditional(functional).replace('LOOK_PRESETS.md','LOOK_PRESETS.zh-TW.md').replace('look-profiles/001-100.md','look-profiles/001-100.zh-TW.md').replace('look-profiles/101-200.md','look-profiles/101-200.zh-TW.md').replace('look-profiles/201-300.md','look-profiles/201-300.zh-TW.md').replace('look-profiles/301-400.md','look-profiles/301-400.zh-TW.md').replace('look-profiles/401-500.md','look-profiles/401-500.zh-TW.md'),encoding='utf-8',newline='\n')
    english="""# Functional filter README: 500 built-in looks

[简体中文](FILTERS.md) · [繁體中文](FILTERS.zh-TW.md) · [English](FILTERS.en.md)

Installed release **v0.1.0-alpha.3 / CLI 0.1.2 / catalog 2.0.0** ships 500 offline color transforms, previews and per-resource evidence. Existing 100 LUT bytes/IDs are preserved.

| # | Capability | Behavior |
|---|---|---|
| P01 | Stable naming | 001–100 retain sp-/t3-; new nt-/fl- IDs identify sources and original variants |
| P02 | Search | Simplified/Traditional Chinese names, English, IDs, Simplified Chinese/English descriptions, licenses and category |
| P03 | Inspect | Actual gray/skin/RGB measurements, use suggestions, trial strength, grid, author, license, pinned source and hashes |
| P04 | Preview | New PNG from a bundled synthetic card or local SDR still; static intensity 0–1; existing output preserved |
| P05 | Apply | Explicit clip or global scope; replace bundled looks and preserve manual effects; append only when requested |
| P06 | Transaction | Dry run writes nothing; actual edits copy LUT/license/provenance, add rights/snapshot/idempotency; refuse modified project resources |
| P07 | Compatibility | Preserve exact alpha.2 provenance, replace old preset markers and retain LUT IDs/licenses through package round trips |
| P08 | Licensing | 100 MIT, 267 CC-BY-SA-4.0, 133 CC0; apply each resource's actual obligations |

Workflow: **list → inspect description/license → preview several strengths → dry-run explicit scope → apply → render → inspect decoded output**.

"""+shared_commands+"""
## Complete names and detailed profiles

[500 numbered looks with actual effects](LOOK_PRESETS.en.md). Each has a source-qualified ID and original title. New localized titles include measured tone hints. All 500 include seven gray, three skin and three RGB swatches, gray Y′ code values, middle-span ratio, suggested use/intensity, cautions, author/source/license, conversion error, digest, PNG and video.

| Numbers | Profiles |
|---|---|
| 001–100 | [Existing looks](look-profiles/001-100.en.md) |
| 101–200 | [New looks and original curve variants](look-profiles/101-200.en.md) |
| 201–300 | [New looks and original curve variants](look-profiles/201-300.en.md) |
| 301–400 | [Film and community looks](look-profiles/301-400.en.md) |
| 401–500 | [Community creative looks](look-profiles/401-500.en.md) |

500 means distinct numeric transforms, including related upstream curve variants, not 500 unrelated style families. Runtime intensity settings and alternate file formats are not additional looks. Common 17³ sampled signatures and reference previews are unique.

Sources: 49 Striped Purple, 51 t3mujinpack, 267 Natron and 133 FreshLUTs. Categories follow source collections; instant and negative groups also contain monochrome variants. Inspect measured profiles for actual behavior. Hald inputs become 33³ CUBEs with disclosed numerical approximation; original CUBE grids remain intact. FreshLUTs selections use explicit uploader Rec.709 labels, without reclassifying unknown/Log/HLG labels as SDR. Labels are not independent camera calibration: `fl-0000228-science-fiction-for-flog` is labeled Rec.709 but mentions FLog in its title. Its input is ambiguous; use only for experimental creative comparisons on prepared SDR, not verified FLog conversion.

CC-BY-SA resources require author/source credit, retained license, stated conversions and share-alike redistribution of adapted data/previews. Application MIT does not replace these terms. [Notices and pinned sources](../releases/v0.1.0-alpha.3/THIRD_PARTY.md).

## Actual output and boundaries

![Actual original/new-look video comparison](../assets/look500-20261024-r1/motion-comparison.gif)

[Original video](../assets/look500-20261024-r1/original.mp4) · [500 native previews](../assets/look500-20261024-r1/contact-sheet.jpg) · [Individual PNG/video](LOOK_PRESETS.en.md) · [Exact checks and corrected failures](../validation/LOOK500_20261024.md).

These are per-pixel SDR color transforms, not grain, glow, vignette, spatial haze, beauty or AI effects. Suggested scenes/intensity are starting points, not natural-footage acceptance. Y′ and span use encoded RGB, not exposure or linear luminance.

`look apply` uses the default SDR FFmpeg path and refuses Float32/Log/HDR. Static partial strength mixes encoded RGB. Explicit source conversion must precede look selection when appropriate.

The existing 46 processing operators and 500 looks are different counts. `lut register` accepts local .cube/.3dl/.csp/.dat; default-renderer static partial strength requires a full 3D CUBE and other formats have limited metadata. The explicit Float32 path separately supports complete CUBE 1D/3D/shapers with declared signals/domain/budget; renderer coverage differs.

## Custom LUTs and processing operators

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk effects list
& $avk effects inspect --name lut3d
& $avk lut register --help
& $avk lut register --project 'E:/video-work/my-project' --input 'E:/looks/cinematic.cube' --name 'My look'
```

Add the returned `lut_id` to a supported timeline LUT effect before preview/render. Registration alone does not change pixels. Supply actual rights and provenance for your own assets. Dynamic strength uses encoded 8-bit RGB mixing; inspect `lut3d`, `effects.numeric_effect_automation` and the selected renderer. Some historical registry limit fields describe static handling only.

Explicit `float32-native-v1` reads complete 1D/3D/shaper+3D CUBEs, not .3dl/.csp/.dat, and does not add 1D support to the default FFmpeg renderer. Proprietary CapCut packs and arbitrary third-party plugins are separate formats.

[Historical installed Float32/shaper evidence](../validation/evidence/float-shaper-20261023-lab/installed-r1/verification.json) · [Historical actual comparison GIF](../assets/float-shaper-20261023-installed-r1/formal-comparison.gif). These checks are not included in this round's 500-look counts.

[Local Skills/install](INSTALLATION.md) · [New release usage](../releases/v0.1.0-alpha.3/USAGE.md) · [Historical 100-look measurements](LOOK_PRESET_DETAILS.md).
"""
    (ROOT/'docs/local/FILTERS.en.md').write_text(english,encoding='utf-8',newline='\n')
    for locale,name,arch,workflow,limit in (
        ('zh','README.md','## 方案与运行逻辑','## 最短使用闭环','## 已知限制与后续开发'),
        ('tw','README.zh-TW.md','## 方案與執行邏輯','## 最短使用閉環','## 已知限制與後續開發'),
        ('en','README.en.md','## Architecture and operation','## Minimal workflow','## Limitations and next milestones')):
        path=ROOT/name;old=path.read_text('utf-8');en=locale=='en';suffix='.en' if en else '.zh-TW' if locale=='tw' else ''
        architecture=old.split(arch,1)[1].split('\n## ',2)
        # Keep the two existing architecture/capability sections intact.
        block=arch+architecture[0]+'\n## '+architecture[1]
        block=re.sub(r'^\| F13 .*$',('| F13 | 500 named offline looks (alpha.3) | `look list/inspect/preview/apply` | Per-look measurements, preview, source and MIT/CC0/CC-BY-SA license; creative SDR RGB |' if en else '| F13 | 500 套具名离线风格（alpha.3） | `look list/inspect/preview/apply` | 逐项实际效果、预览、来源与 MIT/CC0/CC BY-SA 许可；创意 SDR RGB |'),block,flags=re.M)
        if locale=='tw':block=traditional(block)
        intro=('# agent editor kit\n\n'+('**Local video editing CLI for Agents.** Editable JSON timelines, explicit contracts and actual render evidence.' if en else '**面向 Agent 的本地视频编辑 CLI。** 使用可编辑 JSON 时间线、明确的能力契约和实际渲染证据完成广告剪辑与自动化。')+'\n\n'
            '[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md) · [Repository](https://github.com/copypasteltd/agent-editor-kit) · [Download parts](docs/releases/v0.1.0-alpha.3/artifacts) · [Install](docs/releases/v0.1.0-alpha.3/USAGE.md) · [Documentation](docs/README.md)\n\n'
            +('**Current local release: v0.1.0-alpha.3, CLI 0.1.2, 500 built-in looks.** Installed on E:, with all 17 local Skills updated. Download every binary part and reassemble the ordinary ZIP. No new GitHub Release was created; the tested package is committed with this repository.' if en else '**当前本地版本：v0.1.0-alpha.3，CLI 0.1.2，500 套内置风格。** 已安装到 E 盘并同步 17 个本地 Skill。下载全部分卷后合成普通 ZIP 安装；本轮未创建新的 GitHub Release，可用包随仓库提供。')+'\n\n'
            f'![Actual new-look video comparison](docs/assets/look500-20261024-r1/motion-comparison.gif)\n\n'
            f'[500 numbered names and detailed effects](docs/local/LOOK_PRESETS{suffix}.md) · [Functional filter README](docs/local/FILTERS{suffix}.md) · [Original video](docs/assets/look500-20261024-r1/original.mp4) · [Verification](docs/validation/LOOK500_20261024.md).\n\n')
        install_section=('## Installed looks and local Skills\n\n' if en else '## 500 套风格与本地 Skill\n\n')
        install_section+=('500 distinct numeric looks: 100 existing MIT, 267 Natron CC-BY-SA and 133 FreshLUTs CC0. The count includes related original curve variants, not 500 unrelated families; runtime strengths and format copies are excluded. All names/IDs, actual gray/skin/RGB effects, scenes, trial strength, source/license and PNG/video are listed in the complete manual.' if en else
            '500 个不同的数值风格：保留原 100 套 MIT，新增 Natron 267 套 CC BY-SA 与 FreshLUTs 133 套 CC0。计数含同系列上游曲线变体，不代表 500 个独立风格家族；运行强度和格式副本不重复计数。完整手册写明每套的名称/ID、真实灰阶/肤色/RGB 作用、场景、试用强度、来源许可和 PNG/MP4。')+'\n\n'
        install_section+=('| Category | Count |\n|---|---:|\n'+'\n'.join(f'| `{k}` | {n} |' for k,n in categories.items())+'\n\n')
        install_section+=('Select with `look list`, read measured descriptions and license with `inspect`, compare previews, then apply to an explicit clip or global scope. Replace is default; append is explicit. Creative encoded SDR RGB only; LUTs do not generate grain, glow or beauty effects. Per-resource terms and project evidence are preserved.' if en else
            '先 `look list` 选候选，用 `inspect` 读实际作用和许可，比较预览后应用到明确片段或全局。默认替换内置预设，`--append` 才叠加。仅创意 SDR 编码 RGB；颗粒、光晕和美颜属于其他效果。应用时复制每套许可和来源，项目包往返保留预设 ID。')+'\n\n'
        install_section+=shared_commands+'\n'
        install_section+=f"**`$agent-ffmpeg-local-editor`** · 17 Skills · `E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/{TAG}/installed/`. [Install and Skill details](docs/local/INSTALLATION.md).\n\n"
        install_section+=('## Installation\n\n' if en else '## 安装\n\n')
        install_section+=('Native Windows x64 + existing CPython 3.13 and FFmpeg/ffprobe. Eight pinned wheels include the app, NumPy and Pillow. Installation is offline, creates no virtual environment and leaves global site-packages unchanged. Python, FFmpeg and model runtimes are separate prerequisites.' if en else
            '原生 Windows x64，已有 CPython 3.13 和 FFmpeg/ffprobe。8 个固定 wheel 包含应用、NumPy、Pillow；离线安装，不创建虚拟环境，不修改全局 site-packages。Python、FFmpeg 和模型环境不随包分发。')+'\n\n'
        install_section+='[Download all parts and read assembly/install commands](docs/releases/v0.1.0-alpha.3/USAGE.md). [SHA256SUMS](docs/releases/v0.1.0-alpha.3/artifacts/SHA256SUMS.txt). Hashes verify content, not publisher identity.\n\n'
        remainder=workflow+old.split(workflow,1)[1]
        remainder=remainder.replace("$avkRun = 'E:\\tools\\avk-alpha2\\run.py'",
            "$avkPython = 'C:/Python313/python.exe'\n$avkRun = 'E:/tools/aek-alpha3-installed/run.py'")
        # Idempotent regeneration keeps R01–R21 as historical evidence.
        remainder=re.sub(r'^\| R2[234] .*\n','',remainder,flags=re.M)
        checks=(f'| R22 | 500-look catalog and focused regression | **500 unique signatures/previews; {reg["tests_run"]} tests passed** | [Regression]({E}/regression-policy.json) · [Sources](docs/validation/evidence/look500-sources-20261024-r1/compilation.json); initial package-marker failure corrected; full historical suite not rerun |\n'
                f'| R23 | Installed 500-look real execution | **1,000 installed in-process CLI calls; 500 PNGs + 500 native filter videos; {installed["project_rendered_look_cases"]} selected project renders** | [Exact scope]({E}/installed/verification.json) · [GIF](docs/assets/look500-20261024-r1/motion-comparison.gif); each native video decodes 12 frames; 500 upstream comparisons; synthetic input, no natural-footage/listening acceptance |\n'
                f'| R24 | New package, Skills and three-language manual | **17 Skill formats; {skills["skill_launcher_commands"]} launcher calls; 500 detailed profiles per language** | [Installation]({E}/install/installation.json) · [Skills]({E}/skills/verification.json) · [Docs]({E}/docs-verification.json); native E: install, real new-license previews/renders, one expected refusal; old packages retained |\n') if en else (
                f'| R22 | 500 风格目录与定向回归 | **500 个独立签名/预览；{reg["tests_run"]} 项通过** | [回归]({E}/regression-policy.json) · [构建](docs/validation/evidence/look500-sources-20261024-r1/compilation.json)；修复首轮项目包标记错误，保留失败记录；未重跑历史全量 |\n'
                f'| R23 | 安装版 500 项实际输出 | **1,000 次安装版进程内 CLI 调用；500 PNG + 500 原生滤镜成片；{installed["project_rendered_look_cases"]} 项完整项目渲染** | [明确范围]({E}/installed/verification.json) · [GIF](docs/assets/look500-20261024-r1/motion-comparison.gif)；每片解码 12 帧，500 项上游对照；合成输入，未做自然素材/听审验收 |\n'
                f'| R24 | 新包、Skill 与三语完整手册 | **17 个 Skill 格式通过；{skills["skill_launcher_commands"]} 次入口调用；每种语言 500 份详情** | [安装]({E}/install/installation.json) · [Skill]({E}/skills/verification.json) · [文档]({E}/docs-verification.json)；E 盘原生安装，新增许可预设真实应用/渲染，1 次预期拒绝；保留旧包 |\n')
        if locale=='tw':checks=traditional(checks)
        preceding,following=remainder.split(limit,1)
        remainder=preceding.rstrip()+'\n'+checks+'\n'+limit+following
        result=intro+block+'\n\n'+install_section+remainder
        if locale=='tw':result=traditional(result)
        path.write_text(result,encoding='utf-8',newline='\n')
    # Keep the existing 17-entry installation table and historical cases.
    installation_path=ROOT/'docs/local/INSTALLATION.md';old=installation_path.read_text('utf-8')
    tail='## 直接使用 / Use now'+old.split('## 直接使用 / Use now',1)[1]
    current,historical=tail.split('## 首版历史实测 / Historical alpha.1 verification',1)
    current=current.replace('scripts/install_look_release.py','scripts/install_look500_release.py')
    current=current.replace('releases/v0.1.0-alpha.2/','releases/v0.1.0-alpha.3/')
    tail=current+'## 首版历史实测 / Historical alpha.1 verification'+historical
    runtime=json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
    installed_dir=Path(runtime['installed_directory'])
    byte_count=sum(p.stat().st_size for p in installed_dir.rglob('*') if p.is_file())
    header=f'''# 本地发行包与 17 个 Agent Skills / Local installation

当前安装：**{TAG} / CLI 0.1.2 / catalog 2.0.0 / 500 looks**。日期：2026-10-24。

已从校验后的分卷合成 ZIP，在 E 盘离线安装并激活，17 个 `$agent-ffmpeg-local-` Skill 已绑定新 manifest；保留旧 alpha.1 / alpha.2 安装和不可变包。
Native Windows installation, no container/WSL/virtual environment or global site-packages modification. Existing CPython 3.13 and FFmpeg/ffprobe required.

| Item | Path/value |
|---|---|
| Installed app | `{runtime['installed_directory']}` |
| Installed size, including current runtime files | {byte_count:,} bytes |
| Runtime config | `local/agent-ffmpeg/runtime.json` |
| Main Skill | `$agent-ffmpeg-local-editor` |
| Editable Skills | `skills/agent-ffmpeg-local-*/` on E: |
| Discovery | `C:/Users/carzy/.codex/skills/` directory junctions to E: |
| Registration manifest | [agent-ffmpeg-local-install-manifest.json](../../agent-ffmpeg-local-install-manifest.json) |
| Full local ZIP | `{installation['archive']}` |
| Download parts | [alpha.3 artifacts](../releases/v0.1.0-alpha.3/artifacts) |
| ZIP SHA-256 | `{runtime['zip_sha256']}` |
| Bundle manifest | `{runtime['manifest_sha256']}` |

[500 names and actual effects](LOOK_PRESETS.md) · [Filter workflow](FILTERS.md) · [Assembly/installation](../releases/v0.1.0-alpha.3/USAGE.md) · [Installation receipt](../validation/evidence/look500-20261024-r1/install/installation.json) · [17 formats and actual launcher calls](../validation/evidence/look500-20261024-r1/skills/verification.json).

Per-resource licenses: 100 MIT, 267 CC-BY-SA-4.0, 133 CC0-1.0. See the individual inspect response and project-local evidence. Suggested scenes/intensity are not natural-footage acceptance.

'''
    installation_path.write_text(header+tail,encoding='utf-8',newline='\n')
    index=ROOT/'docs/README.md';old=index.read_text('utf-8')
    old=old.replace('[Local package](releases/v0.1.0-alpha.2/artifacts/agent-video-kit-v0.1.0-alpha.2-cp313-win_amd64.zip)','[Local package parts](releases/v0.1.0-alpha.3/artifacts)')
    marker='| 阅读目标 / Goal | Document |'
    before=old.split(marker,1)[0].split('\n\n')[:2]
    intro='\n\n'.join(before)+'\n\n当前为 **v0.1.0-alpha.3 / CLI 0.1.2 / 500 离线风格**，已安装并同步 17 个本地 Skill；完整剪映等价仍未验收。Current local build has 500 named looks, measured per-look profiles, individual licenses and installed native verification.\n\n'
    table=marker+old.split(marker,1)[1]
    table=table.replace('100 预设完整编号','500 预设完整编号').replace('[100 looks]','[500 looks]')
    table=table.replace('| 新包安装、检索、预览与应用 / Alpha.2 usage | [Alpha.2 manual](releases/v0.1.0-alpha.2/USAGE.md) |','| 新包分卷安装、检索、预览与应用 / Alpha.3 usage | [Alpha.3 manual](releases/v0.1.0-alpha.3/USAGE.md) |')
    table=table.replace('| 100 预设实测、单元回归、Skill 与项目包 / Current verification | [Look verification](validation/LOOK_PRESETS_20261024.md) |','| 500 预设实测、定向回归、Skill 与项目包 / Current verification | [500-look verification](validation/LOOK500_20261024.md) |')
    table=table.replace('| 100 项实际色彩作用','| 历史 100 项实际色彩作用')
    table=table.replace('| 滤镜、LUT 格式、调色与关键帧 / Filters, LUTs and grading | [Filters](local/FILTERS.md) |','| 500 套实际详情与功能性 README / Full profiles and filter workflow | [简体](local/FILTERS.md) · [繁體](local/FILTERS.zh-TW.md) · [English](local/FILTERS.en.md) |')
    index.write_text(intro+table,encoding='utf-8',newline='\n')
    print(json.dumps({'status':'updated','root_readmes':3,'functional_readmes':3,'looks':500,'skill_entries':17}))


if __name__=='__main__':main()
