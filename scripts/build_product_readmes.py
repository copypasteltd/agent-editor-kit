"""Maintain substantial three-language product READMEs and complete current capability manuals.

Historical verification rows are preserved verbatim in a separate data file. The
current README is deliberately a usable manual, not merely a document-link index.
"""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import shutil
from urllib.parse import unquote

from build_look_profile_docs import traditional
from readme_product_content import MODULES, SERVICES, SKILLS

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/product'
EVIDENCE = ROOT / 'docs/validation/evidence/looks-n002-20261024-r1'
G = 'docs/assets/looks-n002-20261024-r1'
LANGUAGES = [('zh', 'README.md', ''), ('tw', 'README.zh-TW.md', '.zh-TW'), ('en', 'README.en.md', '.en')]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '|' + '|'.join('---' for _ in headers) + '|',
                      *['| ' + ' | '.join(str(cell).replace('|', ' / ').replace('\n', '<br>') for cell in row) + ' |' for row in rows]]) + '\n'


def repair_links(text, source, target):
    import os
    def replace(match):
        destination = match.group(2)
        if re.match(r'^[a-z]+:', destination) or destination.startswith('#'):
            return match.group()
        path, marker, fragment = destination.partition('#')
        resolved = (source.parent / unquote(path)).resolve()
        relative = Path(os.path.relpath(resolved, target.parent)).as_posix()
        return match.group(1) + relative + (marker + fragment if marker else '') + ')'
    return re.sub(r'(!?\[[^\]]*\]\()([^\n)]+)\)', replace, text)


def main():
    DOC.mkdir(parents=True, exist_ok=True)
    history = DOC / 'readme-verification-history.json'
    if not history.exists():
        rows = {}
        for locale, filename, suffix in LANGUAGES:
            current = (ROOT / filename).read_text('utf-8')
            rows[locale] = [line for line in current.splitlines() if re.match(r'^\| R\d\d \|', line)]
            assert len(rows[locale]) == 24
        save(history, {'source_commit': '1aa13905739bbb45e2d8708af7773e707098ef49', 'rows': rows})
    history_rows = json.loads(history.read_bytes())['rows']
    cap_response = json.loads((ROOT / 'product/.runtime/readme-capabilities-20261024.json').read_text('utf-8-sig'))
    doctor = json.loads((ROOT / 'product/.runtime/readme-doctor-20261024.json').read_text('utf-8-sig'))
    effect_response = json.loads((ROOT / 'product/.runtime/readme-effects-20261024.json').read_text('utf-8-sig'))
    motion_response = json.loads((ROOT / 'product/.runtime/readme-motion-20261024.json').read_text('utf-8-sig'))
    assert all(r['ok'] for r in (cap_response, doctor, effect_response, motion_response))
    for name, value in [('capabilities', cap_response), ('doctor', doctor), ('effects', effect_response), ('motion', motion_response)]:
        save(DOC / (name + '.json'), value)
        save(EVIDENCE / ('installed-' + name + '.json'), value)
    capabilities = cap_response['data']['capabilities']
    effects = effect_response['data']['effects']
    motions = capabilities['motion']['presets']
    assert len(effects) == 46 and len(motions) == 12
    save(DOC / 'module-catalog.json', {'release': 'v0.1.0-alpha.3', 'modules': MODULES, 'services': SERVICES, 'skills': SKILLS,
                                     'numbering': 'Documentation groups, not independent algorithm counts or completion scores.'})

    archived = ROOT / 'docs/releases/v0.1.0-alpha.1/history/README.zh.pre-release.md'
    old = archived.read_text('utf-8-sig')
    demonstration = old[old.index('## 实测演示素材'):old.index('## 当前状态')]
    cases_path = DOC / 'CASES.md'
    cases = '''# 完整演示案例与原始证据 / Complete demonstrations and source evidence

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

## C01–C04：广告、模板、浮点色彩与可恢复交付 / Ads, templates, float color and delivery

[完整步骤、输入、编辑 JSON、实际响应、输出、GIF、音频和复现脚本](../releases/v0.1.0-alpha.1/CASES.md)。这些为已保留的发行案例，不计作本轮新执行。
The release casebook retains inputs, edit JSON, actual responses, output, GIF/audio and reproduction scripts. These are dated executions, not new runs in this documentation update.

## C05：N002 母图 × 500 套滤镜 / Supplied still × all 500 looks

本轮使用正式安装版 CLI 逐项执行 500 次预览。母图为用户提供的 1672×940 RGB PNG，原始字节不变；每套均使用四面体插值、强度 1.0。500 张无损 WebP 与 CLI PNG 解码 RGB 逐像素相同。小图和对照板仅用于浏览。
This update actually executes all 500 previews on the supplied still in the installed CLI, with tetrahedral interpolation and strength 1.0. Every full-size lossless WebP matches the decoded CLI PNG exactly. Thumbnails and boards are browsing aids.

[原始 PNG](../assets/looks-n002-20261024-r1/source.png) · [交互选型页](../assets/looks-n002-20261024-r1/index.html) · [全部编号图册](../local/FILTER_GALLERY.md) · [500 次 CLI 记录](../validation/evidence/looks-n002-20261024-r1/render-verification.json) · [样例/许可清单](../assets/looks-n002-20261024-r1/manifest.json)

![Original and eleven actual looks](../assets/looks-n002-20261024-r1/selection-board.jpg)

下面 GIF 是实际静态滤镜样例的切换，不是新视频渲染或模型推理。Below is an animation of actual still previews, not a new video render or model inference.

![Actual still-preview sequence](../assets/looks-n002-20261024-r1/look-selection.gif)

## C06：客户候选对照板 / Client shortlist board

Skill 的 `look_gallery.py` 可按稳定 ID 导出原图 + 1–12 套样例、完整 ID、许可和 `selection.json`；不修改时间线。客户选型后再按目标素材重新试片和应用。
The Skill helper exports the original plus 1–12 selected looks with stable IDs, licenses and selection.json, without editing a project. Render reviewed candidates on the target media before application.

[实际对照板](../assets/looks-n002-20261024-r1/client-shortlist-example/board.jpg) · [实际候选 JSON](../assets/looks-n002-20261024-r1/client-shortlist-example/selection.json) · [Skill](../../skills/agent-ffmpeg-local-editor/SKILL.md)

## C07：真实选型页、截图与操作录像 / Real selection page, screenshots and recording

原生 Microsoft Edge 实际打开本地 HTML，检查分页、搜索、分类/许可、原图滑杆、勾选、JSON 下载、中英繁切换、空结果和手机布局；全部测试页面已关闭，无外部请求。
Native Edge opens the actual offline HTML to check pagination, search, category/license filters, comparison split, selection, JSON download, three languages, empty results and mobile layout. All owned test pages are closed; no remote requests.

[桌面截图](../assets/looks-n002-20261024-r1/gallery-desktop.png) · [手机截图](../assets/looks-n002-20261024-r1/gallery-mobile.png) · [实际操作录屏 WebM](../assets/looks-n002-20261024-r1/gallery-walkthrough.webm) · [浏览器检查](../validation/evidence/looks-n002-20261024-r1/browser-verification.json)

这是选型文档页，不是视频剪辑 GUI。This is a documentation/selection page, not an editing GUI.

## H 系列：全部既有功能演示 / Complete dated functional demonstrations

以下恢复原演示说明及输入/输出链接，保留原日期、V 编号、指标和失败边界。它们不是本轮重跑结果。研究段落仍明确标注未集成或未达到质量门槛。GIF 不包含声音；听审与自动采样是不同记录。
The following restored demonstrations retain their original dates, V IDs, metrics, input/output links and failure limits. They were not rerun in this update. Research remains labeled as unintegrated or below quality gates; GIFs are silent and listening differs from automatic sample checks.

'''
    cases += repair_links(demonstration, archived, cases_path)
    cases_path.write_text(cases.rstrip()+'\n', encoding='utf-8', newline='\n')

    for locale, filename, suffix in LANGUAGES:
        en = locale == 'en'
        pick = lambda zh, english: english if en else zh
        translate = traditional if locale == 'tw' else lambda value: value
        module_rows = [[f'F{i:02}', r[1 if en else 0], r[3 if en else 2], '`'+r[4]+'`', r[6 if en else 5]] for i, r in enumerate(MODULES, 1)]
        service_rows = [[f'S{i:02}', r[1 if en else 0], r[3 if en else 2], r[5 if en else 4], '`'+r[6]+'`', r[8 if en else 7]] for i, r in enumerate(SERVICES, 1)]
        skill_rows = [[f'K{i:02}', f'[`$agent-ffmpeg-local-{r[0]}`](skills/agent-ffmpeg-local-{r[0]}/SKILL.md)', r[2 if en else 1], r[4 if en else 3], '`'+r[5]+'`', r[7 if en else 6]] for i, r in enumerate(SKILLS, 1)]
        module_table = table(pick(['编号','功能模块','具体行为与输入 → 输出','入口','依赖/边界'],['ID','Module','Behavior and input → output','Entry','Dependency/limit']), module_rows)
        service_table = table(pick(['编号','服务模块','运行形式','需要什么/提供什么','入口','范围'],['ID','Service module','Execution','Needs/provides','Entry','Scope']), service_rows)
        skill_table = table(pick(['编号','Skill','职责','输入 → 输出','相关命令','依赖/边界'],['ID','Skill','Responsibility','Input → output','Commands','Dependency/limit']), skill_rows)

        text = '# agent editor kit\n\n'
        text += pick('**面向 Agent 的开源、本地视频编辑 CLI。** 从结构化编辑计划到可编辑工程、预览、成片、质量报告和可恢复交付；保留每一步的真实输出与来源。',
                     '**An open-source local video-editing CLI for Agents.** Turn structured plans into editable projects, previews, video, quality reports and recoverable deliveries, retaining real artifacts and provenance.')+'\n\n'
        text += '[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md) · [Repository](https://github.com/copypasteltd/agent-editor-kit) · [Docs](docs/README.md)\n\n'
        text += pick('**可用本地版：v0.1.0-alpha.3 · CLI 0.1.2 · 500 套风格 · 17 个本地 Skill。** 基础包已在原生 Windows/CPython 3.13 x64 安装实测。本轮更新完整文档与样例，不修改发行包；alpha.3 提供仓库分卷包，尚未另建 GitHub Release。完整剪映等价仍是开发目标，尚未验收。',
                     '**Usable local build: v0.1.0-alpha.3 · CLI 0.1.2 · 500 looks · 17 local Skills.** Installation has been exercised on native Windows/CPython 3.13 x64. This update expands documentation/examples without changing the release bundle. Alpha.3 is supplied as repository archive parts, without a separate new GitHub Release. Complete Jianying/CapCut parity remains an unaccepted development target.')+'\n\n'
        text += pick('本页包含完整功能模块、服务与依赖、安装与使用逻辑、Skill 输入输出、真实案例和核验表。长篇原始验收日志继续留档，功能说明与案例入口恢复到首页。',
                     'This page includes functional modules, services/dependencies, installation/usage, Skill inputs/outputs, real cases and verification. Long raw acceptance logs remain archived; practical feature descriptions and case access are restored here.')+'\n\n'
        text += pick('## 先看实际效果：同一母图的 500 套滤镜','## See real output: 500 looks on one supplied still')+'\n\n'
        text += pick('以下每一格都来自用户提供的 N002 母图，经已安装 CLI 实际处理。原图 + 11 套示例只是入口；全部 500 套均有独立样例和详情。',
                     'Every tile below comes from the supplied N002 still processed by the installed CLI. The original plus eleven looks are an entry point; all 500 have individual samples and profiles.')+'\n\n'
        text += f'![Original N002 and actual filter outputs]({G}/selection-board.jpg)\n\n'
        text += pick(f'[**打开全部 500 套交互选型页**]({G}/index.html) · [全部编号样例](docs/local/FILTER_GALLERY{suffix}.md) · [逐项实际效果](docs/local/LOOK_PRESETS{suffix}.md) · [原始 PNG]({G}/source.png) · [来源与许可]({G}/SOURCE_AND_LICENSES.md)\n\n',
                     f'[**Open the interactive 500-look gallery**]({G}/index.html) · [Numbered samples](docs/local/FILTER_GALLERY{suffix}.md) · [Measured profiles](docs/local/LOOK_PRESETS{suffix}.md) · [Original PNG]({G}/source.png) · [Sources/licenses]({G}/SOURCE_AND_LICENSES.md)\n\n')
        text += pick('选型页支持简体/繁体/英文、编号/名称/ID/描述搜索、类别与许可筛选、原图滑杆、候选勾选和 JSON 导出。每页仅加载 40 张小图，选中时再加载原尺寸大图。GitHub 文件页不执行 HTML，请下载仓库后直接双击该 HTML；无需服务或联网。',
                     'The gallery supports three languages, number/name/ID/description search, category/license filters, an original-image split, shortlisting and JSON export. It loads 40 thumbnails per page and a full-size image for the active look. GitHub does not execute repository HTML; download the checkout and open the HTML locally, without a server or network.')+'\n\n'
        text += pick('**样例口径：** 原图 1672×940，统一强度 1.0、四面体插值；500 张原尺寸无损 WebP 与实际 CLI PNG 的解码 RGB 逐像素一致，500 张小图为缩放的 WebP。母图没有嵌入色彩配置，按编码 SDR RGB 试片，不推断为相机/HDR 校准。母图使用依据为用户本次提供与展示指令，未将其标为 MIT/CC0。',
                     '**Sample contract:** 1672×940 source, strength 1.0 and tetrahedral interpolation throughout. All 500 full-size lossless WebPs exactly match decoded CLI PNG RGB; the 500 thumbnails are resized WebP. No color profile is embedded in the source, so this is an encoded-SDR-RGB trial rather than camera/HDR calibration. The user supplied the image and requested these examples; it is not declared MIT/CC0.')+'\n\n'
        text += pick('## 产品方案与完整执行逻辑','## Architecture and complete execution logic')+'\n\n'
        text += '''```mermaid
flowchart LR
  A[Human brief / media / selected look IDs] --> B[Agent + local Skills]
  B --> C[CLI JSON + capabilities + schema]
  C --> D[Editable project / transactions / rights]
  D --> E[Validate + preview + reviewed plan]
  E --> F[Default FFmpeg graph]
  E --> G[Explicit supported Float32 path]
  H[Existing local AI / HTML adapters] --> D
  F --> I[Video + manifest + quality + package]
  G --> I
```

'''
        text += pick('当前实现是 **Python CLI + Agent Project schema + FFmpeg**，并有显式的 Float32 处理子集。Concat 是早期路线研究对象，发行包不是“删除 Concat GUI 的二进制”。已采用的 OpenFilm 字幕分段、帧时钟、HTML 动效/模板等复用保留来源与许可；当前运行不依赖 OpenFilm 在线服务。',
                     'The implementation is **Python CLI + Agent Project schema + FFmpeg**, with an explicitly selected Float32 subset. Concat was an early architecture research candidate; the release is not a Concat binary with its GUI deleted. Adopted OpenFilm caption segmentation, frame-clock and HTML/template work retains provenance/licenses and needs no OpenFilm online service.')+'\n\n'
        workflow = [pick('读取 version/doctor/capabilities/schema，确定本机真实可用的能力与依赖。','Read version/doctor/capabilities/schema to determine actual local support and dependencies.'),
                    pick('把 brief 写成计划：素材、画幅、时长、镜头、音轨、字幕、运镜、风格、交付与证据。','Turn the brief into a plan covering assets, canvas, duration, cuts, audio, captions, motion, looks and delivery evidence.'),
                    pick('创建独立工程，导入本地素材，用真实 asset ID 与整数 ticks 编写编辑 JSON；音轨明确添加。','Create an owned project, ingest local media, and author edit JSON using actual asset IDs and integer ticks; add audio explicitly.'),
                    pick('通过事务 compose/edit/apply 写入时间线，保留快照；先校验，再预览关键帧和区间。','Apply transactional compose/edit/apply operations with snapshots, validate, then preview important frames/ranges.'),
                    pick('若需要选型，展示原图与少量候选，记录最终 ID/强度/作用域；在目标素材上复试。','For selection, show the original and a small candidate set, record final IDs/strength/scope and trial them on target media.'),
                    pick('渲染至工程内新路径，检查实际编码文件、manifest、warning、音画与权利，再导出项目包。','Render to a new project-owned path, inspect the encoded output, manifest, warnings, A/V and rights, then export the project package.')]
        text += '\n'.join(f'{i}. {line}' for i, line in enumerate(workflow, 1))+'\n\n'
        text += pick('## 43 个功能说明模块','## 43 functional documentation modules')+'\n\n'
        text += pick('编号用于定位文档；各模块有依赖与交叉，不是“43 个独立内核”或完成率。下表直接写明行为、入口与限制；[完整机器能力清单及每项契约](docs/product/CAPABILITIES'+suffix+'.md)保留全部字段。',
                     'IDs locate documentation groups with dependencies/overlap; they are not 43 independent kernels or a completion score. The table describes behavior, commands and limits. The [complete machine capability manual](docs/product/CAPABILITIES'+suffix+'.md) retains every field.')+'\n\n'+module_table+'\n'
        text += pick('## 支持的服务模块与依赖','## Supported service modules and dependencies')+'\n\n'
        text += pick('这里的“服务”指本地处理模块与适配器。基础包提供 CLI/项目/渲染能力；模型、浏览器、字体与用户素材按下面条件提供。',
                     '“Service” here means a local processing module or adapter. The base package supplies the CLI, projects and rendering; models, browser runtimes, fonts and user assets follow the conditions below.')+'\n\n'+service_table+'\n'
        text += pick('**本机查询与交付状态：** 本轮 doctor 检测到原生 Python 3.13.1、FFmpeg/ffprobe 8.1 和 Node；这不证明每个模型或浏览器适配器均已注册。doctor 只查到系统存在 Docker/WSL 可执行路径，没有运行它们。本项目始终使用原生工具，不调度 Docker/WSL/虚拟环境。',
                     '**Observed local environment:** this update’s doctor sees native Python 3.13.1, FFmpeg/ffprobe 8.1 and Node; this does not establish registration of every model/browser adapter. doctor merely discovers Docker/WSL executable paths and does not run them. This project uses native tools without invoking Docker/WSL/virtual environments.')+'\n\n'
        text += pick('### 可选 AI 模块具体支持什么','### What the optional AI modules actually provide')+'\n\n'
        ai_rows = [
            ['Whisper / CTC',pick('转写、字幕、校正文强制对齐、CER；需已有 safetensors/原生环境。','Transcription/captions/corrected-text alignment/CER; existing weights/native runtime required.'),'asr adapter; subtitle transcribe/align/evaluate'],
            ['flite / SoulX',pick('英文基础语音或授权参考音色合成；SoulX 需已有 CUDA BF16 环境。','Basic English speech or authorized-reference voice synthesis; SoulX requires existing CUDA BF16 runtime.'),'tts adapter/voice/synthesize'],
            ['HDemucs',pick('人声/伴奏分离，区别于无需模型的 mid/side 声道近似。','Vocal/accompaniment separation, distinct from model-free mid/side approximation.'),'audio adapter; audio separate'],
            ['Tracking / YOLOv10 ONNX',pick('模板/原生 ONNX/命令 JSON 轨迹，驱动绑定与重构图，须选明确对象。','Template/native ONNX/command-JSON tracking for binding/reframing; explicitly choose objects.'),'media adapter/track/track-bind/reframe'],
            ['PP-OCRv4 / OpenSeeFace',pick('OCR 文字框与相机锚点、66 点人脸与受限修饰；需现有 ONNX CPU 依赖。','OCR polygons/camera anchors, 66-point faces and bounded retouch; existing ONNX CPU dependencies.'),'ocr; face'],
            ['RVM / SAM2',pick('人像软透明抠像 / 提示式对象分割；模型、提示、场景切换与 mask 都需检查。','Human soft-alpha matting / prompted object segmentation; review models, prompts, cuts and masks.'),'media adapter; media matting'],
            ['LaMa / VACE',pick('逐帧修复 / CUDA 窗口联合生成编辑与扩画；保留时序/纹理未验收边界。','Framewise repair / CUDA joint-window generative edits and outpainting, retaining temporal/texture acceptance limits.'),'media inpaint/outpaint']]
        text += table(pick(['体系','功能与前提','命令'],['Stack','Capability and prerequisite','Commands']),ai_rows)+'\n'
        text += pick('以上接口不代表这些权重随基础包分发。历史某模型实测也不等于当前工程已配置；应读取实际 registry 和命令结果。外部模型、音色和素材的许可分别核验，软件 MIT 不覆盖它们。',
                     'These interfaces do not mean the base bundle contains the weights. A historical model execution does not establish configuration of the current project; inspect its registry and results. Model, voice and media licenses are separate from software MIT.')+'\n\n'
        text += pick('## 46 个效果算子与 12 个运镜预设','## 46 effect operators and 12 motion presets')+'\n\n'
        by_category = {}
        for effect in effects:
            by_category.setdefault(effect['category'], []).append('`'+effect['id']+'`')
        text += table(pick(['效果类别','可查询的实际算子'],['Effect category','Actual discoverable operators']),[[k,', '.join(v)] for k,v in by_category.items()])+'\n'
        text += pick('12 套运镜：','12 motion presets: ')+', '.join('`'+r['id']+'`' for r in motions)+'.\n\n'
        text += pick('数值参数、默认值、范围、是否可关键帧和后端逐项见 [全部效果参数](docs/product/EFFECTS'+suffix+'.md)。LUT 负责颜色映射；颗粒、暗角、模糊、几何、蒙版和 AI 修复是各自独立处理，不因选择风格而自动加入。',
                     'See [every effect’s parameters](docs/product/EFFECTS'+suffix+'.md) for defaults, bounds, keyframe support and backend. LUTs map color; grain, vignette, blur, geometry, masks and AI repair are separate operations and are not automatically added by selecting a look.')+'\n\n'
        text += pick('## 500 套滤镜：命名、详情与客户选型','## 500 looks: names, detail and client selection')+'\n\n'
        text += pick('001–100 保留 `sp-`/`t3-`，101–500 使用 `nt-`/`fl-` 来源前缀。名称保留上游胶片/风格与曲线变体；稳定 ID 才是调用标识。目录含 500 个不同数值变换，包含相关上游曲线，不按运行强度或文件格式重复计数，也不代表 500 个互不相关的风格家族。',
                     '001–100 retain `sp-`/`t3-`; 101–500 use source prefixes `nt-`/`fl-`. Names retain upstream film/style/curve variants; stable IDs are the command identifiers. The 500 distinct transforms include related upstream curves and do not count strength/format copies or imply 500 unrelated families.')+'\n\n'
        catalog = json.loads((ROOT/'product/src/ai_ad_editor/look_data/catalog.json').read_bytes())['records']
        categories = Counter(r['category'] for r in catalog)
        text += table(['Category','Count'],sorted(categories.items()))+'\n'
        text += pick('每套详情包含：原名/简繁名称/ID/类别、实际灰阶与肤色/RGB 数值、建议场景、试用强度、注意事项、作者、来源 commit、转换误差、LUT 哈希、独立许可、本次 N002 样例以及历史合成卡 PNG/视频。',
                     'Each profile includes original/localized names, ID/category, measured gray/skin/RGB values, trial use/strength, cautions, creator, source commit, conversion error, LUT hash/license, this N002 sample and dated synthetic-card PNG/video.')+'\n\n'
        text += table(pick(['编号','详情与母图样例'],['Numbers','Profiles and supplied-image samples']), [[f'{n+1:03}–{n+100:03}', f'[Profiles](docs/local/look-profiles/{n+1:03}-{n+100:03}{suffix}.md) · [N002 samples](docs/local/filter-gallery/{n+1:03}-{n+100:03}{suffix}.md)'] for n in range(0,500,100)])+'\n'
        text += pick('来源与许可：Striped Purple 49 + t3mujinpack 51（MIT），Natron 267（CC BY-SA 4.0），FreshLUTs 133（CC0）。Natron Hald 转 CUBE 的数值近似逐项披露；社区胶片/产品名不代表官方徕卡、剪映或厂商算法。`fl-0000228-science-fiction-for-flog` 的 Rec.709 标签与 FLog 标题存在歧义，仅做实验创意比较，不能作为已验证的相机 Log 转换。',
                     'Sources/licenses: Striped Purple 49 + t3mujinpack 51 (MIT), Natron 267 (CC BY-SA 4.0), FreshLUTs 133 (CC0). Natron Hald-to-CUBE approximation is disclosed per entry. Community film/product names are not official Leica/CapCut/manufacturer algorithms. `fl-0000228-science-fiction-for-flog` has an ambiguous Rec.709 label versus FLog title; use only for experimental creative comparison, not verified camera-log conversion.')+'\n\n'
        text += pick('**面向客户的流程：** Agent 先展示原图 + 3–6 套符合需求的实际样例，并写清编号、名称、稳定 ID、强度、色彩变化与许可；客户可在选型页筛选并导出候选，或直接报编号。Agent 再对真实目标素材生成选定强度预览，记录最终 ID、强度与片段/全局作用域，再 dry-run/apply。对照滑杆只改变原图显示区域，不模拟滤镜强度。',
                     '**Client workflow:** show the original plus 3–6 relevant actual samples, identifying number, name, stable ID, strength, color change and license. Clients can filter/export candidates or give numbers. Render selected strengths on the actual target media, record final ID/strength/clip-or-global scope, then dry-run/apply. The split slider changes the original comparison region and does not simulate strength.')+'\n\n'
        text += '''```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
$aekGallery = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/look_gallery.py'
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --query '黑白' --limit 6
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --ids t3-fuji-superia-800 nt-bw-agfa-apx-100 fl-0000634-darkblue --output 'E:/video-work/client-look-options'
& $avk look inspect --id t3-fuji-superia-800
& $avk look preview --id t3-fuji-superia-800 --input 'E:/media/client-frame.png' --output 'E:/video-work/client-strength-065.png' --strength 0.65
& $avk look apply --project 'E:/video-work/my-ad' --id t3-fuji-superia-800 --clip-id clip_1 --strength 0.65 --dry-run
& $avk look apply --project 'E:/video-work/my-ad' --id t3-fuji-superia-800 --clip-id clip_1 --strength 0.65
```

'''
        text += pick('上例输出目录必须是新目录；`clip_1` 应替换为真实片段 ID。helper 只输出 `board.jpg` 与 `selection.json`，不改工程；样例均为 100% 强度。`look apply` 默认替换该作用域的内置风格并保留手工效果，`--append` 才叠加；`--global` 作用于全部序列。静态强度混合的是编码 RGB。仅创意 SDR，Float32/Log/HDR 应先按独立色彩契约准备。',
                     'Use a new output directory and replace `clip_1` with an actual clip ID. The helper writes only `board.jpg` and `selection.json`, without project edits; samples are at 100%. `look apply` replaces built-in looks in scope while preserving manual effects; stacking requires `--append`, and `--global` affects every sequence. Static strength mixes encoded RGB. Prepare Float32/Log/HDR through a separate color contract before creative SDR looks.')+'\n\n'
        text += pick('## 安装、包内容与本机加载','## Installation, bundle contents and local loading')+'\n\n'
        text += pick('基础环境：原生 Windows x64、已有 CPython 3.13、FFmpeg/ffprobe。发行包含 8 个固定 wheel（应用、NumPy、Pillow 及 schema 依赖），采用目标目录离线安装，不创建虚拟环境、不改全局 site-packages。Python、FFmpeg、Node/Chromium、模型权重、商业字体/音乐不包含在基础包。',
                     'Prerequisites: native Windows x64, existing CPython 3.13 and FFmpeg/ffprobe. Eight pinned wheels contain the app, NumPy, Pillow and schema dependencies, installed offline to a target folder without a virtual environment or global site-packages changes. Python, FFmpeg, Node/Chromium, model weights and commercial fonts/music are not bundled.')+'\n\n'
        text += pick('[下载所有分卷与元数据](docs/releases/v0.1.0-alpha.3/artifacts/) · [安装手册](docs/releases/v0.1.0-alpha.3/USAGE.md) · [摘要](docs/releases/v0.1.0-alpha.3/artifacts/SHA256SUMS.txt)。分卷不是独立 ZIP；先合成后解压。哈希验证内容一致性，不是发布者签名。',
                     '[Download all parts/metadata](docs/releases/v0.1.0-alpha.3/artifacts/) · [Installation manual](docs/releases/v0.1.0-alpha.3/USAGE.md) · [Checksums](docs/releases/v0.1.0-alpha.3/artifacts/SHA256SUMS.txt). Parts are not standalone ZIPs: assemble before extracting. Hashes verify content, not publisher signatures.')+'\n\n'
        text += '''```powershell
$avkPython = 'C:/Python313/python.exe'
# Run from the directory containing every .partNN and the supplied metadata.
& $avkPython -I -B -X utf8 ./assemble.py --output E:/tools/agent-editor-kit-alpha3.zip
Expand-Archive E:/tools/agent-editor-kit-alpha3.zip E:/tools/agent-editor-kit-alpha3
Set-Location E:/tools/agent-editor-kit-alpha3
$avkManifest = (Get-Content ./version.json -Raw | ConvertFrom-Json).manifest_sha256
& $avkPython -I -B -X utf8 ./bundle/install.py --target E:/tools/aek-alpha3-installed --manifest-sha256 $avkManifest
& $avkPython -I -S -B -X utf8 E:/tools/aek-alpha3-installed/run.py doctor
```

'''
        text += pick('本机已经安装到 `E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.3/installed/`。17 个 Skill 的正文/脚本在仓库 `skills/`，Codex 的 `C:/Users/carzy/.codex/skills/` 对应项为联接。移动仓库后重新登记；注册脚本保护同名无关目录。',
                     'This host already has `E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.3/installed/`. The 17 Skills’ bodies/scripts live in `skills/`, with Codex discovery junctions under `C:/Users/carzy/.codex/skills/`. Re-register after relocation; unrelated conflicting directories are preserved.')+'\n\n'
        text += '''```powershell
Set-Location 'E:/dev/sandbox/AI广告剪辑'
./register-agent-ffmpeg-local-skills.ps1
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk capabilities
& $avk schema show
& $avk COMMAND --help
```

'''
        text += pick('Skill 启动器验证本地安装回执与 launcher 哈希，再以 `-I -S` 调用固定发行版；安装缺失时明确报错，不静默回退源码。500 套 N002 展示图片和选型页属于仓库文档资源，未改写已发布的运行包；仅下载运行 ZIP 不会自动获得本次完整图册。',
                     'The Skill launcher checks the installation receipt and launcher hash, then invokes the pinned release with `-I -S`; missing installation fails without silent source fallback. N002 images and the gallery are checkout documentation assets, not a changed release bundle; downloading only the runtime ZIP does not include this complete gallery.')+'\n\n'
        text += pick('## 从零到交付的命令与工程结构','## Commands and project structure: start to delivery')+'\n\n'
        text += '''```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
$aekProject = 'E:/video-work/first-ad'
& $avk project init $aekProject --name 'First ad'
& $avk media ingest --project $aekProject --input 'E:/media/product.mp4'
# Read returned data.asset.id; author changes.json using actual IDs and source ranges.
& $avk timeline compose --project $aekProject --input 'E:/video-work/changes.json'
& $avk validate --project $aekProject
& $avk rights check --project $aekProject
& $avk policy audit --project $aekProject
& $avk preview frame --project $aekProject --frame 0
& $avk render --project $aekProject --output 'E:/video-work/first-ad/renders/ad.mp4'
& $avk quality check --project $aekProject --input 'E:/video-work/first-ad/renders/ad.mp4'
& $avk convert export --help
```

'''
        text += pick('素材与 changes.json 是示例路径，需要用真实文件与 ID。默认时基 90,000 ticks/秒、显示帧率 30/1；源时间、作者时间、帧号与原生 PTS 不可混用。视频轨不会自动导入音轨，需明确写入 audio track。[可复现广告的真实编辑 JSON](docs/validation/evidence/release-v0.1.0-alpha.1-r2/changes.json)。',
                     'Media/changes.json paths are placeholders requiring real files and IDs. Default author timebase is 90,000 ticks/second and display rate 30/1; source time, author time, frame number and native PTS differ. Video tracks do not automatically add audio; author audio tracks explicitly. See the [executed ad edit JSON](docs/validation/evidence/release-v0.1.0-alpha.1-r2/changes.json).')+'\n\n'
        text += '''```text
project/
  project.json         # editable settings, assets, sequences and tracks
  rights-ledger.json   # source, license and dependency evidence
  assets/              # imported/derived assets, LUTs and notices
  history/             # snapshots
  operations/          # operations, diagnostics and render queue
  renders/             # delivered files and manifests
  cache/               # disposable derived previews/analysis
```

'''
        text += pick('响应包含 `ok/command/request_id/operation_id/status/data/artifacts/warnings/errors/provenance`。同时检查进程退出码与响应，不能只看文件存在；`--dry-run` 是计划，不能当作实际渲染，幂等语义只用于声明支持的写操作。',
                     'Responses contain `ok/command/request_id/operation_id/status/data/artifacts/warnings/errors/provenance`. Check exit status and response, not merely file existence. A dry run is a plan rather than a render; idempotency applies only to advertised writes.')+'\n\n'
        text += pick('默认导入权利为未核验；商业交付前补全真实来源、许可和证据，再使用 `rights check`/`render --publish`。`--publish` 是本地门禁，不上传到任何平台。转换输出携带 Exact/Approximate/Unsupported/Failed 损失报告，明文草稿交换不保证全部效果无损。',
                     'Imported rights default to unverified; supply actual source/license/evidence before commercial delivery and `rights check`/`render --publish`. `--publish` is a local gate, not a platform upload. Interchange reports Exact/Approximate/Unsupported/Failed losses and cannot promise lossless plaintext-draft effects.')+'\n\n'
        text += pick('## 17 个本地 Skill：职责、输入输出与使用边界','## 17 local Skills: responsibility, inputs/outputs and limits')+'\n\n'+skill_table+'\n'
        text += pick('常用组合：创意/内容策略 → editor → video-understand → timeline/template → quality → project-ops。rights-ledger/local-policy 检查相关依赖；local-models 只在任务需要真实模型时启用。滤镜客户选型由 editor 展示与记录，quality 复核实际目标素材。',
                     'Typical routing: creative/content strategy → editor → understanding → timeline/template → quality → project operations. Rights/policy check relevant dependencies; local-models is used when actual inference is needed. The editor presents/records look choices and quality reviews the target-media result.')+'\n\n'
        text += '''```text
$agent-ffmpeg-local-editor 用本地素材做 6 秒竖屏广告，保留工程、音轨、权利证据和成片核验。
$agent-ffmpeg-local-editor 用 N002 图册向客户展示暖色胶片、黑白、冷色电影各两套；给编号/ID/强度/许可和对照板，等客户选型后再试目标素材。
$agent-ffmpeg-local-timeline 给 clip_1 添加可编辑推近和关键帧，预览首中末帧。
$agent-ffmpeg-local-template-library 用提供的本地产品图和变量生成一个可编辑模板变体。
$agent-ffmpeg-local-quality 对实际输出、manifest 和 Scope 复核，分别说明自动检查、目检、播放和听审。
```

'''
        text += pick('[当前完整 Skill 手册](docs/product/SKILLS'+suffix+'.md) · [客户选型工作流](skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [注册与本地安装](docs/local/INSTALLATION.md)。Skill 是任务指导，不自带额外模型/素材订阅，也不自动连接广告平台。',
                     '[Current full Skill manual](docs/product/SKILLS'+suffix+'.md) · [Client selection workflow](skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [Registration/install](docs/local/INSTALLATION.md). Skills are task instructions, without additional model/stock subscriptions or automatic ad-platform access.')+'\n\n'
        text += pick('## 完整案例、原输入、实际输出与 GIF','## Complete cases, original inputs, actual output and GIFs')+'\n\n'
        case_rows = [
            ['C01',pick('6 秒 FIELD 竖屏广告：原创产品卡 + 合成音 → 360×640/30 fps/180 帧。','Six-second FIELD ad: original cards + synthetic audio → 360×640/30 fps/180 frames.'),'[Input](docs/assets/release-v0.1.0-alpha.1-r2/input.mp4) · [MP4](docs/assets/release-v0.1.0-alpha.1-r2/field.mp4) · [GIF](docs/assets/release-v0.1.0-alpha.1-r2/field.gif) · [JSON](docs/validation/evidence/release-v0.1.0-alpha.1-r2/changes.json)'],
            ['C02',pick('3 秒模板换款：真实 asset ID/时长变量 → 可编辑静音变体。','Three-second template variant: real asset/duration variables → editable silent output.'),'[Template](docs/validation/evidence/release-v0.1.0-alpha.1-r2/template.json) · [Variables](docs/validation/evidence/release-v0.1.0-alpha.1-r2/variables.json) · [MP4](docs/assets/release-v0.1.0-alpha.1-r2/variant.mp4) · [GIF](docs/assets/release-v0.1.0-alpha.1-r2/variant.gif)'],
            ['C03',pick('Float32 1D/shaper + 3D LUT：有序色彩链、源时钟和独立预览的历史实测。','Dated Float32 1D/shaper + 3D LUT color-chain, source-clock and independent-preview execution.'),'[Input](docs/assets/float-shaper-20261023-installed-r1/original.mp4) · [Output](docs/assets/float-shaper-20261023-installed-r1/edited.mp4) · [GIF](docs/assets/float-shaper-20261023-installed-r1/formal-comparison.gif)'],
            ['C04',pick('项目包导出/恢复 + 真实远程引用拒绝；保留完整 CLI 响应。','Package export/restore and actual remote-reference refusal, with complete CLI responses.'),'[Export](docs/validation/evidence/release-v0.1.0-alpha.1-r2/export-package.stdout.json) · [Restored validation](docs/validation/evidence/release-v0.1.0-alpha.1-r2/restored-validate.stdout.json) · [Refusal](docs/validation/evidence/release-v0.1.0-alpha.1-r2/remote-refused.stdout.json)'],
            ['C05',pick('本轮 N002 × 500：500 次安装版预览，500 张全尺寸无损图逐像素一致。','New N002 × 500: 500 installed previews with 500 full-size lossless pixel matches.'),f'[Source]({G}/source.png) · [Gallery]({G}/index.html) · [All samples](docs/local/FILTER_GALLERY{suffix}.md) · [GIF]({G}/look-selection.gif)'],
            ['C06',pick('客户候选板：原图 + 指定稳定 ID、名称、许可与可回传 selection.json。','Client board: original plus selected stable IDs, names, licenses and returnable selection.json.'),f'[Board]({G}/client-shortlist-example/board.jpg) · [JSON]({G}/client-shortlist-example/selection.json)'],
            ['C07',pick('真实选型页：桌面/手机截图、实际操作录屏和交互断言。','Real gallery: desktop/mobile screenshots, actual interaction recording and assertions.'),f'[Desktop]({G}/gallery-desktop.png) · [Mobile]({G}/gallery-mobile.png) · [WebM]({G}/gallery-walkthrough.webm)'],
            ['H01 / V35',pick('源句柄转场：作者输入、双剪口实际输出、独立像素参考。','Source-handle transitions: authored input, actual two-cut result and independent pixel reference.'),'[Input](docs/assets/source-transitions-20261017/authored-input.mp4) · [Output](docs/assets/source-transitions-20261017/C01-actual.mp4) · [GIF](docs/assets/source-transitions-20261017/comparison.gif)'],
            ['H02 / V41',pick('HTML 原生动效：保留源码、透明标题与时间线合成；已有浏览器环境。','Native HTML motion: editable source, alpha titles and timeline composition with an existing browser runtime.'),'[Source](docs/assets/html-motion-20261018/source.mp4) · [HTML](docs/assets/html-motion-20261018/template/index.html) · [Output](docs/assets/html-motion-20261018/S03-timeline.mp4) · [GIF](docs/assets/html-motion-20261018/native-comparison.gif)'],
            ['H03 / V43',pick('逐帧蒙版修正：缺选/误选修正，几何通过但自然 LaMa 修复仍有涂抹。','Frame mask corrections: selected/clear errors corrected; geometry passes while natural LaMa repair still smears.'),'[Source](docs/assets/mask-edits-20261018/source.mp4) · [Before](docs/assets/mask-edits-20261018/mask-input.mov) · [After](docs/assets/mask-edits-20261018/mask-edited.mov) · [GIF](docs/assets/mask-edits-20261018/comparison.gif)'],
            ['H04 / V37',pick('片段组跨项目复用：转场、字幕、LUT、子序列与关联依赖。','Cross-project fragments: transitions, captions, LUTs, child sequences and linked dependencies.'),'[Input](docs/assets/fragments-20261018/source-a.mp4) · [Output](docs/assets/fragments-20261018/C01-actual.mp4) · [GIF](docs/assets/fragments-20261018/comparison.gif)'],
            ['H05 / V34',pick('字幕分段与双语：人工标记源文本、实际输出和参考；不是模型转写演示。','Caption segmentation/bilingual text: authored timings, actual output and reference; not an ASR demonstration.'),'[Input](docs/assets/subtitle-segments-20261017/source.mp4) · [Output](docs/assets/subtitle-segments-20261017/S01-segmented.mp4) · [GIF](docs/assets/subtitle-segments-20261017/comparison.gif)'],
            ['H06 / V49',pick('真实离线 CTC：模型时间驱动字幕，边界偏差 258.1875 ms，未通过 66.6667 ms 门槛。','Actual offline CTC: model-timed captions; 258.1875 ms boundary error fails the 66.6667 ms gate.'),'[Input audio](docs/assets/ctc-alignment-20261018/input.wav) · [Output](docs/assets/ctc-alignment-20261018/result.mp4) · [GIF](docs/assets/ctc-alignment-20261018/comparison.gif)'],
            ['H07 / V53',pick('磁吸主轨重排：A/B/C/D → C/A/B/D，保持关联音画与作者约束。','Magnetic primary-track reorder: A/B/C/D → C/A/B/D with linked audio and author constraints.'),'[Input](docs/assets/magnetic-reorder-v53-r5-20261018/source-preview.mp4) · [Output](docs/assets/magnetic-reorder-v53-r5-20261018/MR01.mp4) · [GIF](docs/assets/magnetic-reorder-v53-r5-20261018/reorder-before-after.gif)']]
        text += table(pick(['编号','场景与实测范围','原始文件、输出与证据'],['ID','Scenario and actual scope','Original/output/evidence']),case_rows)+'\n'
        text += pick('本轮实际选型页桌面截图，支持原图对照与候选导出：','Actual desktop screenshot of the selection page, with original comparison and shortlist export:')+'\n\n'+f'![Actual offline look selection page]({G}/gallery-desktop.png)\n\n'
        text += pick('下面是实际 CLI 渲染的 FIELD 广告；所有源卡片、音频、编辑 JSON、响应与流信息见案例手册。GIF 无声，原 MP4 可检查音轨。',
                     'Below is the actual CLI-rendered FIELD ad. The casebook retains source cards/audio, edit JSON, responses and stream data. GIF is silent; inspect the MP4 for audio.')+'\n\n'
        text += '![Actual rendered FIELD ad](docs/assets/release-v0.1.0-alpha.1-r2/field.gif)\n\n'
        text += pick('已保留的 HTML 动效源码与时间线合成实测：','Dated execution of editable HTML motion and timeline compositing:')+'\n\n![Actual HTML motion and composition](docs/assets/html-motion-20261018/native-comparison.gif)\n\n'
        text += pick('关键帧、运镜、动态蒙版、标题、转场和音频组合的既有实际演示：','Dated actual keyframe/camera/mask/title/transition/audio composition:')+'\n\n![Actual CLI feature demonstration](docs/assets/readme-20261016/cli-showcase.gif)\n\n'
        text += pick('[**完整案例册：恢复全部既有功能演示、输入/输出、指标与失败**](docs/product/CASES.md) · [首版完整复现步骤](docs/releases/v0.1.0-alpha.1/CASES.md)。本轮只新增 N002 静态滤镜和选型文档工具实测，其他案例保留日期，不累计为新模型或新回归。研究性的时序修复仍单列为未集成/未验收。',
                     '[**Complete casebook: all restored functional demos, inputs/outputs, metrics and failures**](docs/product/CASES.md) · [Release reproduction steps](docs/releases/v0.1.0-alpha.1/CASES.md). New executions here are N002 still looks and selection-document tools; other cases retain their dates and are not counted as new inference/regression. Experimental temporal repair remains separately labeled unintegrated/unaccepted.')+'\n\n'
        text += pick('## 故障、恢复与交付注意点','## Troubleshooting, recovery and delivery')+'\n\n'
        text += table(pick(['现象','处理方式'],['Symptom','Action']),[
            [pick('缺少 FFmpeg / 模型 / 浏览器','Missing FFmpeg/model/browser'),pick('先 doctor/inspect，提供已有原生依赖；不自动联网下载或改用不声明的后端。','Run doctor/inspect and supply existing native dependencies; no automatic download or undeclared fallback.')],
            [pick('输出已存在 / 路径在工程外','Output exists / outside project'),pick('选择新的工程内绝对路径；保留原结果与失败证据。','Choose a new absolute project-owned path; preserve earlier results/failures.')],
            [pick('项目锁或中断','Project locked/interrupted'),pick('查看 operation/queue，按支持入口取消或恢复；不盲删锁。','Inspect operations/queue, cancel or recover through supported commands; do not blindly remove locks.')],
            [pick('发布门禁阻止','Publish gate blocks'),pick('补全每个素材、字体、LUT、模型的真实许可和本地证据，重新 rights check。','Supply actual per-media/font/LUT/model license and local evidence, then recheck rights.')],
            [pick('效果/浮点组合不支持','Unsupported effect/float combination'),pick('读取能力契约，调整明确计划与所选渲染路径；不悄悄降级。','Read the capability contract and revise the reviewed plan/renderer, without silent degradation.')],
            [pick('只有图册，没有运行能力','Gallery without runtime'),pick('图册可以纯本地浏览；生成新强度和编辑工程需要另行安装并加载固定 CLI。','The gallery can be browsed offline; new strengths and project edits require the pinned CLI installation.')]
        ])+'\n'
        text += pick('## 功能核验与发布证据','## Functional verification and release evidence')+'\n\n'
        text += pick('R01–R24 保留对应版本/日期核验；R25–R28 记录 N002 图册与完整文档恢复；R29 记录本次目标差距及安装版只读核对。各行按原证据日期理解，历史核验未因文档更新重跑；计数不相加，也不据此宣称完整剪映等价。',
                     'R01–R24 retain their original versions/dates; R25–R28 record the N002 gallery and full-manual restoration; R29 records this goal-gap assessment and read-only installed inventory. Each row keeps its evidence date. Historical checks were not rerun for documentation updates; counts are not added or used to claim complete CapCut parity.')+'\n\n'
        text += '| # | '+pick('核验 | 实际结果 | 证据与边界','Verification | Actual result | Evidence and scope')+' |\n|---|---|---|---|\n'+'\n'.join(history_rows[locale])+'\n'
        new_rows = [
            ['R25',pick('N002 全部滤镜的真实产出','Actual N002 outputs for every look'),pick('500 次安装版 CLI；500 全尺寸无损图 + 500 小图，500 个独立像素哈希。','500 installed CLI executions; 500 full-size lossless images + 500 thumbnails, with 500 unique pixel hashes.'), '[Render receipt](docs/validation/evidence/looks-n002-20261024-r1/render-verification.json) · '+pick('原图哈希不变；无新视频/模型推理，不是全自然视频质量验收。','Source hash unchanged; no new video/inference or general natural-video quality acceptance.')],
            ['R26',pick('选型页、截图与实际录像','Gallery, screenshots and actual recording'),pick('原生浏览器交互、三语、搜索/筛选/候选下载/手机布局检查通过。','Native-browser interaction, three languages, search/filter/export/mobile checks pass.'),'[Browser receipt](docs/validation/evidence/looks-n002-20261024-r1/browser-verification.json) · '+pick('0 远程请求；测试标签全部关闭。','Zero remote requests; all owned test tabs closed.')],
            ['R27',pick('Skill 客户选型与本地加载','Skill client selection and local registration'),pick('17 个 Skill 格式/联接核验；真实候选对照板、搜索与失败保护。','17 Skill format/junction checks; actual shortlist board, search and refusal protection.'),'[Skill workflow receipt](docs/validation/evidence/looks-n002-20261024-r1/skill-verification.json) · '+pick('不修改时间线；示例强度 1.0。','No timeline edits; sample strength 1.0.')],
            ['R28',pick('三语完整文档与样例链接','Complete three-language docs and sample links'),pick('功能/服务/Skill/案例/500 项图册、能力字段与本地链接核对。','Modules/services/Skills/cases/500 samples, capability fields and local-link checks.'),'[Documentation receipt](docs/validation/evidence/looks-n002-20261024-r1/docs-verification.json) · '+pick('未重跑历史 2,930 项内核全量。','Historical 2,930-test full kernel suite not rerun.')],
            ['R29',pick('完整目标差距与安装版核对','Goal gaps and installed inventory'),pick('4 次安装版只读 CLI 成功；68 项能力声明与手册一致；38 组差距分别列出收口条件。','4 successful installed read-only CLI calls; 68 capability contracts match the manual; 38 gap groups have explicit acceptance conditions.'),'[Assessment](docs/product/GOAL_GAPS_20261024.md) · [Inventory](docs/validation/evidence/goal-gaps-20261024-r1/inventory.json) · '+pick('本轮 0 渲染/0 推理；既有精度失败与未验收项保留。','Zero renders/inference in this assessment; prior accuracy failures and open acceptance remain.')]
        ]
        text += '\n'.join('| '+' | '.join(row)+' |' for row in new_rows)+'\n\n'
        text += pick('## 当前边界与开发方向','## Current limits and development direction')+'\n\n'
        text += pick('当前可交付的是有明确契约、离线可运行、可编辑、可复查的 Agent CLI 闭环。完整开源素材/模板生态、约定的 AI 特效/美颜/排版、完整色彩管线、指定草稿版本的真实转换质量、广泛自然视听和长片资源性能仍需开发与验收。消费级 GUI、账号、云协作及任意私有版本无损转换不属于当前内核收口门槛。后续 Float32 转场/运行时闭包候选 R113/R114 未随本版提供。',
                     'The deliverable is an offline, editable and auditable Agent CLI workflow with explicit contracts. Openly licensed asset/template ecosystems, agreed AI/beauty/layout features, complete color processing, actual quality for supported draft profiles, broad natural-media acceptance and long-form resource performance remain open. Consumer GUI, accounts, cloud collaboration and arbitrary lossless private-draft interchange are outside current core acceptance. Later R113/R114 Float32 transition/runtime-closure candidates are not included in this release.')+'\n\n'
        text += pick('[2026-10-24 完整目标差距表](docs/product/GOAL_GAPS_20261024.md)列出 38 组差距、当前实现与收口条件。优先关闭真实素材质量、字词对齐和音频已知失败、复杂编辑组合、长片资源与干净主机安装；随后建设素材/模板库，再扩展完整 AI 范围。当前没有足够依据给出整体完成百分比。',
                     'The [2026-10-24 goal-gap assessment](docs/product/GOAL_GAPS_20261024.md) lists 38 gap groups, current support and acceptance conditions. First close natural-media quality, known alignment/audio failures, complex edit combinations, long-form resources and clean-host installation; then build the asset/template ecosystem and remaining AI scope. The evidence does not establish an overall completion percentage.')+'\n\n'
        text += pick('下一步以真实客户素材与最小可复现工程收集缺口，逐项补齐、实测、发布新版本；不覆盖既有发布包/摘要/标签。只按实际成功产物更新核验。',
                     'Use real client media and minimal reproducible projects to identify gaps, implement/check them individually and publish new versions without replacing prior bundles/digests/tags. Record actual successful artifacts rather than inferred completion.')+'\n\n'
        text += pick('## 文档体系、来源与维护','## Documentation, provenance and maintenance')+'\n\n'
        text += '\n'.join([
            f'- [Current capability manual](docs/product/CAPABILITIES{suffix}.md) · [Effect parameters](docs/product/EFFECTS{suffix}.md) · [Skills](docs/product/SKILLS{suffix}.md) · [Complete demonstrations](docs/product/CASES.md).',
            f'- [Filter workflow](docs/local/FILTERS{suffix}.md) · [500 profiles](docs/local/LOOK_PRESETS{suffix}.md) · [N002 gallery guide](docs/local/FILTER_GALLERY{suffix}.md) · [Installed setup](docs/local/INSTALLATION.md).',
            '- [Alpha.3 usage](docs/releases/v0.1.0-alpha.3/USAGE.md) · [Base workflow](docs/releases/v0.1.0-alpha.1/USAGE.md) · [Release scope](docs/releases/v0.1.0-alpha.1/RELEASE.md).',
            '- [Requirements/roadmap](docs/产品需求与开发路线基线_2026-10-12.md) · [Architecture](docs/architecture/系统边界与模块契约_v0.1_2026-10-13.md) · [JSON schema](docs/specs/agent-project.schema.json).',
            '- [Historical numbered acceptance](docs/releases/v0.1.0-alpha.1/history/README.zh.pre-release.md) · [Historical document catalog](docs/releases/v0.1.0-alpha.1/history/docs-index.pre-release.md) · [README restoration record](docs/maintenance/README_RESTORATION_20261024.md).',
            '- [Software MIT](LICENSE) · [Base third-party notices](docs/releases/v0.1.0-alpha.1/THIRD_PARTY.md) · [500 LUT notices](docs/releases/v0.1.0-alpha.3/THIRD_PARTY.md) · [Supplied-image rights](docs/assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md).'])+'\n\n'
        text += pick('自有代码按 MIT 分发；第三方 Skill、模型、字体、LUT 与媒体分别保留各自许可，用户母图不因进入仓库而获得 MIT/CC0 授权。提交问题时提供版本、最小工程、实际命令、错误与 manifest。后续功能更新同步简体/繁体/英文 README，维护 `main`，通过检查后普通推送到本仓库。',
                     'Own code is MIT; third-party Skills, models, fonts, LUTs and media retain their own terms. Inclusion does not make the supplied image MIT/CC0. Report issues with version, minimal project, actual commands/errors and manifest. Functional updates maintain all three READMEs on main and use normal pushes after verification.')+'\n'
        (ROOT / filename).write_text(translate(text), encoding='utf-8', newline='\n')

        # Detailed manuals retain the same reviewed rows and all installed fields.
        module_manual = f'# '+pick('当前功能模块与服务清单','Current modules and services')+'\n\n[README](../../'+filename+') · [Machine response](capabilities.json) · [Module data](module-catalog.json)\n\n'+module_table+'\n'+service_table+'\n'
        module_manual += pick('## 完整安装版能力字段','## Complete installed capability fields')+'\n\n'
        module_manual += pick('以下逐项保留本轮从安装版读取的能力字段、状态、命令、限制与配额。它们是契约，不是本轮对每一项重新执行的验收。状态 local_adapter_only 需要已有模型，implemented_with_limits 需阅读限制。',
                              'Below are every capability’s fields/status/commands/limits/budgets read from the installed release. They are contracts rather than newly rerun acceptance for every feature. local_adapter_only needs existing models; implemented_with_limits requires its limits to be read.')+'\n\n'
        for key, value in capabilities.items():
            module_manual += f'### `{key}`\n\n```json\n'+json.dumps(value, ensure_ascii=False, indent=2)+'\n```\n\n'
        (DOC / ('CAPABILITIES'+suffix+'.md')).write_text(translate(module_manual).rstrip()+'\n', encoding='utf-8', newline='\n')
        effect_manual = '# '+pick('效果算子完整参数','Complete effect parameters')+'\n\n[README](../../'+filename+') · [Installed response](effects.json)\n\n'
        effect_manual += pick('46 项，来自当前安装版 effects list；参数是否支持动画以每项声明为准。','46 entries from the installed effects list; animation support follows each entry’s declaration.')+'\n\n'
        for effect in effects:
            effect_manual += f'## `{effect["id"]}`\n\n```json\n'+json.dumps(effect, ensure_ascii=False, indent=2)+'\n```\n\n'
        effect_manual += pick('## 12 套运镜的完整参数','## Complete parameters for 12 motion presets')+'\n\n```json\n'+json.dumps(motions, ensure_ascii=False, indent=2)+'\n```\n'
        (DOC/('EFFECTS'+suffix+'.md')).write_text(translate(effect_manual),encoding='utf-8',newline='\n')
        skill_manual = '# '+pick('17 个本地 Skill 详情','17 local Skill details')+'\n\n[README](../../'+filename+') · [Registration](../local/INSTALLATION.md)\n\n'+skill_table.replace('(skills/','(../../skills/')+'\n'
        for i,row in enumerate(SKILLS,1):
            skill_manual += f'## K{i:02} · `$agent-ffmpeg-local-{row[0]}`\n\n'+row[2 if en else 1]+'\n\n'+row[4 if en else 3]+'\n\n`'+row[5]+'`\n\n'+row[7 if en else 6]+'\n\n'
            skill_manual += f'[Actual Skill instructions](../../skills/agent-ffmpeg-local-{row[0]}/SKILL.md)\n\n'
        skill_manual += pick('## 滤镜客户选型','## Client look selection')+'\n\n[Workflow](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [Gallery guide](../local/FILTER_GALLERY'+suffix+'.md)\n\n'
        skill_manual += pick('本机 17 个目录均为 E 盘源文件到 Codex 发现路径的联接。运行包与图册是分离交付：仅安装 wheel 并不自动包含图册。helper 只读已经渲染的样例，导出新对照板；最终编辑调用固定 CLI 并保存工程快照。',
                             'All 17 local registrations are junctions to E-drive canonical files. Runtime and gallery are separate: wheels alone do not include the gallery. The helper reads rendered samples and exports a new comparison board; final edits use the pinned CLI with snapshots.')+'\n'
        (DOC/('SKILLS'+suffix+'.md')).write_text(translate(skill_manual),encoding='utf-8',newline='\n')
    print(json.dumps({'status':'generated','readmes':3,'functional_groups':len(MODULES),'service_groups':len(SERVICES),'skills':len(SKILLS),'machine_capabilities':len(capabilities),'effects':len(effects),'motions':len(motions),'restored_demo_images':len(re.findall(r'!\[', demonstration))},ensure_ascii=False))


if __name__ == '__main__':
    main()
