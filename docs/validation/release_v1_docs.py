"""Reorganize all three public manuals without discarding dated verification."""
from pathlib import Path
import hashlib
import json
import posixpath
import re
import sys
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'local/agent-ffmpeg/release-v1-20261107'
RELEASE = ROOT / 'docs/releases/v1.0.0'
HISTORY = ROOT / 'docs/history/readme-before-v1.0.0'
BASE = 'https://github.com/copypasteltd/agent-editor-kit'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def relocate(text, prefix):
    def link(match):
        target = match[2]
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith(('#', '/')):
            return match.group()
        return match[1] + prefix + target + match[3]
    return re.sub(r'(!?\[[^\]\n]*\]\()([^\s)]+)(\))', link, text)


def section(text, start, end):
    return text[text.index(start):text.index(end)]


def main():
    RELEASE.mkdir(parents=True, exist_ok=True)
    HISTORY.mkdir(parents=True, exist_ok=True)
    write(HISTORY / '.gitattributes', '*.original.txt -text -diff\n')
    before = json.loads((WORK / 'before.json').read_bytes())
    build_path = ROOT / 'docs/validation/evidence/release-v1-20261107/build-r1/verification.json'
    pin = json.loads(build_path.read_bytes())['manifest_sha256'] if build_path.exists() else 'STABLE_MANIFEST_SHA256'
    names = ('README.md', 'README.zh-TW.md', 'README.en.md')
    history = {}
    intro = [
        '''# agent editor kit

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md)

面向Agent的开源视频剪辑与生成内核：通过一个Skill或原生CLI管理素材、可编辑时间线、500套风格滤镜、关键帧、字幕、声音、AI模型任务与交付。以FFmpeg和明确登记的本地运行库为基础，直接处理自己的工程文件。

**正式发行：v1.0.0；内核标识：CLI0.1.66；统一Skill：r60。** 发行版本与内核构建编号分别记录。本版重新构建已验收的66内核、离线依赖包、单Skill工具包和三语手册，整合此前已实现能力。它不是所有剪映功能或自然视听质量已经达标的声明。CLI67人像分区和独立文字塑形/排版候选继续保留在开发区，未收入正式包。

[正式Release与全部附件](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v1.0.0) · [发行说明](docs/releases/v1.0.0/RELEASE-NOTES.md) · [完整版本手册](docs/releases/v1.0.0/README.md) · [原G01–G38与剩余工作](docs/product/UNFINISHED_20261107.md)

## 安装包与运行条件

| 编号 | 交付物 | 用途 |
|---|---|---|
| D01 | [Windows x64离线应用包](https://github.com/copypasteltd/agent-editor-kit/releases/download/v1.0.0/agent-editor-kit-v1.0.0-cp313-win_amd64.zip) | 原生应用wheel、固定离线依赖、安装器、第三方许可与分发清单；内核CLI0.1.66 |
| D02 | [统一Skill工具包r60](https://github.com/copypasteltd/agent-editor-kit/releases/download/v1.0.0/agent-editor-kit-v1.0.0-unified-skill-r60.zip) | 一个外层Skill、17内部模块、注册/配置脚本、完整使用说明；与D01摘要绑定 |
| D03 | [SHA256SUMS.txt](https://github.com/copypasteltd/agent-editor-kit/releases/download/v1.0.0/SHA256SUMS.txt) | 核对附件字节；另有简体、繁体、英文快速开始及发布说明，共7附件 |

原生Windows x64、已有CPython3.13 x64和FFmpeg/ffprobe；基础剪辑可用CPU。包内不含Python、FFmpeg、驱动、模型权重或完整Torch/CUDA运行库。可选AI功能需按下文服务表登记已有本地模型与依赖；本项目不用Docker、WSL或虚拟环境。当前正式二进制交付与实测平台为Windows，不能把Python跨平台代码当成已验证的Linux/macOS安装包。

## 从下载到交付的完整流程

''',
        '''# agent editor kit

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md)

面向Agent的開源影片剪輯與生成核心：透過一個Skill或原生CLI管理素材、可編輯時間軸、500套風格濾鏡、關鍵影格、字幕、聲音、AI模型任務與交付。以FFmpeg及明確登記的本機執行環境為基礎，直接處理自己的專案檔案。

**正式發行：v1.0.0；核心標識：CLI0.1.66；統一Skill：r60。** 發行版本與核心建置編號分別記錄。本版重新建置已驗收的66核心、離線相依套件、單Skill工具包與三語手冊，整合此前已實現的能力。這不代表所有剪映功能或自然影音品質已經達標。CLI67人像分區及獨立文字塑形/排版候選保留在開發區，未收入正式包。

[正式Release及所有附件](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v1.0.0) · [發行說明](docs/releases/v1.0.0/RELEASE-NOTES.md) · [完整版本手冊](docs/releases/v1.0.0/README.zh-TW.md) · [原G01–G38與剩餘工作](docs/product/UNFINISHED_20261107.md)

## 安裝包與執行條件

| 編號 | 交付物 | 用途 |
|---|---|---|
| D01 | [Windows x64離線應用包](https://github.com/copypasteltd/agent-editor-kit/releases/download/v1.0.0/agent-editor-kit-v1.0.0-cp313-win_amd64.zip) | 原生應用wheel、固定離線相依套件、安裝器、第三方授權與分發清單；核心CLI0.1.66 |
| D02 | [統一Skill工具包r60](https://github.com/copypasteltd/agent-editor-kit/releases/download/v1.0.0/agent-editor-kit-v1.0.0-unified-skill-r60.zip) | 一個外層Skill、17內部模組、註冊/設定腳本及完整說明；與D01摘要綁定 |
| D03 | [SHA256SUMS.txt](https://github.com/copypasteltd/agent-editor-kit/releases/download/v1.0.0/SHA256SUMS.txt) | 核對附件位元組；另有簡體、繁體、英文快速開始與發行說明，共7附件 |

原生Windows x64、已有CPython3.13 x64及FFmpeg/ffprobe；基礎剪輯可使用CPU。包內不含Python、FFmpeg、驅動程式、模型權重或完整Torch/CUDA執行環境。可選AI功能需依下方服務表登記既有本機模型與相依套件；本專案不用Docker、WSL或虛擬環境。目前正式二進位交付與實測平台為Windows，不能把Python跨平台程式碼當成已驗證的Linux/macOS安裝包。

## 從下載到交付的完整流程

''',
        '''# agent editor kit

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md)

An open-source video editing and generation engine for agents. One Skill or a native CLI manages media, editable timelines, 500 looks, keyframes, captions, audio, local AI jobs and portable delivery. FFmpeg and explicitly registered native runtimes operate on your own project files.

**Stable distribution: v1.0.0. Engine identifier: CLI0.1.66. Unified Skill: r60.** The distribution version and existing engine build identifier are recorded separately. This release rebuilds the accepted engine, pinned offline dependencies, single-Skill toolkit and complete trilingual manuals, consolidating implemented capabilities. It does not certify complete CapCut feature parity or natural audiovisual quality. Unaccepted CLI67 portrait regions and experimental shaping/typography remain development candidates, outside the stable packages.

[Stable Release and all assets](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v1.0.0) · [Release notes](docs/releases/v1.0.0/RELEASE-NOTES.md) · [Versioned manual](docs/releases/v1.0.0/README.en.md) · [Original G01–G38 and remaining work](docs/product/UNFINISHED_20261107.md)

## Packages and prerequisites

| ID | Distribution | Purpose |
|---|---|---|
| D01 | [Windows x64 offline application](https://github.com/copypasteltd/agent-editor-kit/releases/download/v1.0.0/agent-editor-kit-v1.0.0-cp313-win_amd64.zip) | Native application wheel, pinned offline dependencies, installer, third-party notices and distribution manifest; CLI0.1.66 engine |
| D02 | [Unified Skill toolkit r60](https://github.com/copypasteltd/agent-editor-kit/releases/download/v1.0.0/agent-editor-kit-v1.0.0-unified-skill-r60.zip) | One public Skill, 17 internal modules, registration/configuration helpers and complete manuals; hash-paired with D01 |
| D03 | [SHA256SUMS.txt](https://github.com/copypasteltd/agent-editor-kit/releases/download/v1.0.0/SHA256SUMS.txt) | Asset checksums; the release also supplies three QUICKSTART languages and release notes, seven assets total |

Use native Windows x64 with an existing CPython3.13 x64 and FFmpeg/ffprobe. Basic editing works on CPU. Python, FFmpeg, drivers, model weights and the complete Torch/CUDA runtime are separate prerequisites. Register existing local models and dependencies for optional AI services in the table below. This project uses no Docker, WSL or virtual environment. Windows is the verified binary distribution target; portable Python source does not establish a tested Linux/macOS installer.

## Complete download-to-delivery workflow

''']
    anchors = [
        ('## 产品方案与完整执行逻辑', '## 分卷备用安装、包内容与仓库本机入口', '## 一个 Skill、17 项内部模块', '## 功能核验与发布证据'),
        ('## 產品方案與完整執行邏輯', '## 分卷備用安裝、包內容與倉庫本機入口', '## 一個 Skill、17 項內部模組', '## 功能核驗與發布證據'),
        ('## Architecture and complete execution logic', '## Multipart fallback, bundle contents and repository installation', '## One Skill, 17 internal modules', '## Functional verification and release evidence')]
    new_checks = [
        '''## 正式版核验、历史记录与剩余工作

| 编号 | 内容 | 结果与证据 |
|---|---|---|
| R618 | v1.0.0正式分发构建与三语文档整理 | [构建](docs/validation/evidence/release-v1-20261107/build-r1/verification.json) · [本轮原生安装、真实Skill、完整音画重放](docs/validation/evidence/release-v1-20261107/local-r1/verification.json)。内核源码/安装版各4,124项为历史验收，经本版完整应用字节绑定复用；不记为本轮新跑8,248项 |
| R619 | 正式公开发行 | [发布收据](docs/validation/evidence/release-v1-20261107/publication-r1/verification.json)；新标签、新附件、non-prerelease；既有alpha不覆盖 |
| R620 | 正式下载独立复核 | [匿名下载、7附件摘要、新目录原生安装与真实单Skill完整重放](docs/validation/evidence/release-v1-20261107/public-download-r1/verification.json)。同机新目录不等于干净主机或新GPU/模型质量验收 |

原先707条F/R记录保留在[可浏览历史README](docs/history/readme-before-v1.0.0/README.md)，并保留[原始逐字节快照](docs/history/readme-before-v1.0.0/README.md.original.txt)与[三语原始编号行](docs/history/readme-before-v1.0.0/numbered-rows.json)。本页的功能表、案例和服务说明继续完整保留，历史状态不再置于当前安装流程之前。每轮新增实测继续追加编号，旧失败不删除、不转记。

| 编号 | 尚未关闭 | 具体边界/下一步 |
|---|---|---|
| P01 | CLI67人像分区候选 | 原4,154项整套和后续真实GPU/安装/升级链未完成；暂停记录保留，正式1.0.0不带入 |
| P02 | 完整文字排版集成 | 独立Unicode/Bidi/塑形结果已有证据；工程、字幕、Float32、字体许可依赖打包和真实成片整体验收仍待 |
| P03 | 真实内容质量 | 自然口型、困难补帧、对白降噪、翻译与配音语义、音乐质量、HDR监看、长片性能需要按对应模型与设备分别验收 |
| P04 | 完整产品目标 | 原G01–G38继续开放，包括全部高级效果/模板/AI功能及跨设备交付；详见[逐项未完成条件](docs/product/UNFINISHED_20261107.md) |

## 文档与许可

[本版Skill详解](docs/releases/v1.0.0/SKILL.md) · [本版案例索引](docs/releases/v1.0.0/CASES.md) · [详细能力表](docs/product/CAPABILITIES.md) · [项目架构与需求](docs/README.md) · [MIT代码许可](LICENSE) · [500 LUT来源许可](docs/releases/v0.1.0-alpha.3/THIRD_PARTY.md) · [母图来源边界](docs/assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md)

软件许可不自动覆盖素材、字体、模型、声音或客户成片。`rights check`检查项目权利账本；`render --publish`是本地门禁，不负责上传社交平台。滤镜命名中的相机/胶片名称用于风格描述，不表示原厂授权或官方色彩匹配。实际输出GIF无声，音频必须查看MP4/WAV并单独听审。
''',
        '''## 正式版核驗、歷史記錄與剩餘工作

| 編號 | 內容 | 結果與證據 |
|---|---|---|
| R618 | v1.0.0正式分發建置及三語文件整理 | [建置](docs/validation/evidence/release-v1-20261107/build-r1/verification.json) · [本輪原生安裝、實際Skill與完整影音重放](docs/validation/evidence/release-v1-20261107/local-r1/verification.json)。核心原始碼/安裝版各4,124項屬歷史驗收，以本版完整應用位元組綁定沿用；不計為本輪新跑8,248項 |
| R619 | 正式公開發行 | [發行收據](docs/validation/evidence/release-v1-20261107/publication-r1/verification.json)；新標籤、新附件、non-prerelease；既有alpha不覆寫 |
| R620 | 正式下載獨立複核 | [匿名下載、7附件摘要、新目錄原生安裝及實際單Skill完整重放](docs/validation/evidence/release-v1-20261107/public-download-r1/verification.json)。同機新目錄不等於乾淨主機或新GPU/模型品質驗收 |

原先707條F/R記錄保存在[可瀏覽歷史README](docs/history/readme-before-v1.0.0/README.zh-TW.md)，另有[原始位元組快照](docs/history/readme-before-v1.0.0/README.zh-TW.md.original.txt)及[三語原始編號行](docs/history/readme-before-v1.0.0/numbered-rows.json)。本頁完整保留功能表、案例與服務說明；歷史狀態不再排列於目前安裝流程之前。新實測繼續追加編號，歷史失敗不刪除、不轉記。

| 編號 | 尚未關閉 | 具體邊界/下一步 |
|---|---|---|
| P01 | CLI67人像分區候選 | 原4,154項整套與後續真實GPU/安裝/升級鏈尚未完成；暫停記錄保留，正式1.0.0不帶入 |
| P02 | 完整文字排版整合 | 獨立Unicode/Bidi/塑形已有證據；專案、字幕、Float32、字型授權相依套件打包及真實成片整批驗收仍待 |
| P03 | 真實內容品質 | 自然口型、困難補幀、對白降噪、翻譯配音語義、音樂品質、HDR監看及長片效能，需依模型與裝置分別驗收 |
| P04 | 完整產品目標 | 原G01–G38繼續開放，包含全部進階效果/範本/AI及跨裝置交付；見[逐項剩餘條件](docs/product/UNFINISHED_20261107.md) |

## 文件與授權

[本版Skill詳解](docs/releases/v1.0.0/SKILL.md) · [本版案例索引](docs/releases/v1.0.0/CASES.md) · [詳細能力表](docs/product/CAPABILITIES.zh-TW.md) · [專案架構及需求](docs/README.md) · [MIT程式碼授權](LICENSE) · [500 LUT來源授權](docs/releases/v0.1.0-alpha.3/THIRD_PARTY.md) · [母圖來源邊界](docs/assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md)

軟體授權不自動涵蓋素材、字型、模型、聲音或客戶成片。`rights check`檢查專案權利帳本；`render --publish`是本機門禁，不負責上傳社群平台。濾鏡中的相機/底片名稱描述風格，不代表原廠授權或官方色彩匹配。GIF無聲，聲音需查看MP4/WAV並另行聽審。
''',
        '''## Stable acceptance, dated history and remaining work

| ID | Work | Results and evidence |
|---|---|---|
| R618 | v1.0.0 distribution rebuild and complete trilingual documentation | [Build](docs/validation/evidence/release-v1-20261107/build-r1/verification.json) · [This release's native install, real Skill and whole-media replay](docs/validation/evidence/release-v1-20261107/local-r1/verification.json). The 4,124 source and 4,124 installed engine tests are historical acceptance, reused through exact application byte binding; they are not 8,248 newly executed tests |
| R619 | Public stable publication | [Publication receipt](docs/validation/evidence/release-v1-20261107/publication-r1/verification.json); new tag/assets, non-prerelease; existing alphas preserved |
| R620 | Independent public download verification | [Anonymous download, all seven hashes, new native install and actual single-Skill whole-media replay](docs/validation/evidence/release-v1-20261107/public-download-r1/verification.json). A fresh directory on this host is not a clean-host, new-GPU or model-quality acceptance |

All 707 prior F/R records remain in the [browsable historical README](docs/history/readme-before-v1.0.0/README.en.md), with an [exact original byte snapshot](docs/history/readme-before-v1.0.0/README.en.md.original.txt) and [original trilingual numbered rows](docs/history/readme-before-v1.0.0/numbered-rows.json). Functional tables, services and cases remain in this manual. Dated development status no longer precedes current installation instructions. New observations append IDs without deleting old failures or reassigning test results.

| ID | Still open | Boundary and next work |
|---|---|---|
| P01 | CLI67 portrait-region candidate | The original 4,154-test regression and subsequent actual GPU/install/upgrade chain are incomplete. Paused records remain preserved; the stable distribution excludes it |
| P02 | Complete typography integration | Independent Unicode/Bidi/shaping evidence exists; project/subtitle/Float32 integration, portable font notices and complete actual-media acceptance remain |
| P03 | Natural content quality | Lip sync, difficult interpolation, denoising, translation/speech semantics, music quality, HDR monitoring and long-form performance require separate model/device acceptance |
| P04 | Full product goal | Original G01–G38 remains open, including advanced effects/templates/AI and cross-device delivery. See [itemized unfinished conditions](docs/product/UNFINISHED_20261107.md) |

## Documentation and licensing

[Stable Skill guide](docs/releases/v1.0.0/SKILL.md) · [Stable casebook](docs/releases/v1.0.0/CASES.md) · [Detailed capability matrix](docs/product/CAPABILITIES.en.md) · [Architecture and requirements](docs/README.md) · [MIT source license](LICENSE) · [500 LUT notices](docs/releases/v0.1.0-alpha.3/THIRD_PARTY.md) · [Supplied image rights](docs/assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md)

The software license does not automatically license media, fonts, models, voices or client outputs. `rights check` checks the project ledger; `render --publish` is a local gate and does not upload to a social platform. Camera/film look names describe creative styles, without manufacturer endorsement or official color matching. GIFs are silent; use MP4/WAV and a separate listening review for audio.
''']
    for i, name in enumerate(names):
        original = (WORK / 'readmes-before' / name).read_bytes()
        text = original.decode('utf-8-sig').replace('\r\n', '\n')
        rows = re.findall(r'^\|\s*[FR]\d+\s*\|.*$', text, flags=re.M)
        assert len(rows) == 707
        history[name] = dict(sha256=hashlib.sha256(original).hexdigest(), count=len(rows), rows=rows)
        (HISTORY / (name + '.original.txt')).write_bytes(original)
        header = '> Historical snapshot before v1.0.0, 2026-11-07. Statements below retain their original evidence dates and versions. [Current manual](../../../' + name + ').\n\n'
        readable = header + relocate(text, '../../../')
        write(HISTORY / name, '\n'.join(line.rstrip() for line in readable.splitlines()) + '\n')
        suffix = ('', '.zh-TW', '.en')[i]
        quick = (ROOT / 'docs/releases/v0.1.0-alpha.4' / ('QUICKSTART' + suffix + '.md')).read_text(encoding='utf-8')
        quick = quick.replace('v0.1.0-alpha.4-local.64', 'v1.0.0').replace('v0.1.0-alpha.4', 'v1.0.0')
        quick = quick.replace('agent-editor-kit-community-unified-skill-r59.zip', 'agent-editor-kit-v1.0.0-unified-skill-r60.zip')
        quick = quick.replace('sha256:1da7f0a678ea678f49af6d9b847dfd8912b11ede04aad22f8d87ee247ee1117a', pin)
        quick = quick.replace('# agent editor kit / CLI0.1.66', '# agent editor kit v1.0.0 / CLI0.1.66')
        def quick_root_link(match):
            target = match[2]
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                return match.group()
            resolved = posixpath.normpath(posixpath.join('docs/releases/v1.0.0', target))
            return match[1] + BASE + '/blob/v1.0.0/' + quote(resolved, safe='/#') + match[3]
        quick_root = re.sub(r'(!?\[[^\]\n]*\]\()([^\s)]+)(\))', quick_root_link, quick)
        write(RELEASE / ('QUICKSTART' + suffix + '.md'), quick_root)
        # Preserve complete existing function/service/look/Skill/case prose;
        # replace obsolete installation and unbounded chronological status with current flow.
        a, b, c, d = anchors[i]
        functions = section(text, a, b)
        skill_cases = section(text, c, d)
        scope_note = [
            '\n下面的功能与案例按各自证据日期保留；旧案例的CLI编号是实际执行版本，不代表本轮重新执行。正式1.0.0的安装和调用以本页前述流程及R618–R620为准。\n\n',
            '\n以下功能及案例保留各自證據日期；舊案例的CLI編號是實際執行版本，不表示本輪重新執行。正式1.0.0的安裝及呼叫以前述流程和R618–R620為準。\n\n',
            '\nCapabilities and cases below retain their evidence dates. Older CLI identifiers describe actual historical runs, not tests repeated for this release. Use the installation workflow above and R618–R620 for v1.0.0.\n\n'][i]
        checks = new_checks[i]
        # The tag predates its own public-download receipt. Link these two
        # post-publication records to main; never retag published source.
        for receipt in ('publication-r1/verification.json', 'public-download-r1/verification.json'):
            path = 'docs/validation/evidence/release-v1-20261107/' + receipt
            checks = checks.replace('(' + path + ')', '(' + BASE + '/blob/main/' + path + ')')
        demo = [
            '## 本版新安装与工程重放的实际输出\n\n程序图案与独立测试音经真实安装版剪辑、LUT及工程包重放；2秒、60帧、完整立体声对照。该例用于核验分发/渲染链路，真实素材及AI案例见后面的完整案例表。\n\n',
            '## 本版新安裝與專案重放的實際輸出\n\n程式圖案及獨立測試音經真實安裝版剪輯、LUT與專案包重放；2秒、60幀、完整立體聲對照。此例核驗分發/渲染鏈路，真實素材及AI案例見後方完整案例表。\n\n',
            '## Actual output from this release’s fresh installation and replay\n\nA generated test pattern and independent diagnostic tone pass through the installed editor, LUT and editable package replay: two seconds, 60 frames and full stereo comparison. This checks distribution/rendering; real-resource and AI cases are documented in the complete case tables below.\n\n'][i]
        demo += '![v1.0.0 actual installed output, silent diagnostic GIF](docs/assets/release-v1-20261107/actual.gif)\n\n[MP4](docs/assets/release-v1-20261107/actual.mp4) · [PNG](docs/assets/release-v1-20261107/preview.png) · [Input video](docs/assets/release-v1-20261107/input-pattern.mp4) · [Input WAV](docs/assets/release-v1-20261107/input-tone.wav) · [Editable project](docs/assets/release-v1-20261107/editable.aevpkg.zip) · [Source and notices](docs/assets/release-v1-20261107/SOURCE_AND_LICENSES.md)\n\n'
        rendered = intro[i] + quick_root.split('\n', 2)[2] + '\n' + scope_note + demo + functions + skill_cases + checks
        write(ROOT / name, rendered)
        write(RELEASE / name, relocate(rendered, '../../../'))
    write(HISTORY / 'numbered-rows.json', json.dumps(history, ensure_ascii=False, indent=2) + '\n')
    modules = before['formal_skill_inventory']['modules']
    skill = '''# Unified Skill / 統一Skill / 统一Skill

Stable distribution **v1.0.0**, engine **CLI0.1.66**, toolkit **r60**. Invoke
`$agent-ffmpeg-local-editor` as the single outer entry. It routes to 17 internal
references; do not register 17 additional Skills or silently call source code.

This Skill forwards arguments to the hash-pinned native offline installation.
The application ZIP and Skill ZIP are a pair. Run the included QUICKSTART first,
then version, doctor and capabilities through the actual installed launcher.
Basic `--base-only` setup does not install or execute optional AI models.

| ID | Internal module | Purpose | Reference |
|---|---|---|---|
'''
    for row in modules:
        skill += '| ' + row['id'] + ' | ' + row['key'] + ' | ' + row['purpose_zh'] + ' / ' + row['purpose_en'] + ' | [module](' + BASE + '/blob/v1.0.0/skills/agent-ffmpeg-local-editor/' + row['reference'] + ') |\n'
    skill += '''
## Agent workflow and client selection

1. Confirm output dimensions, frame rate, language, deliverables, available media,
   models and client-approved rights. Inspect capabilities and the actual schema.
2. Create an Agent Project. Ingest actual files and keep returned asset IDs. Edit
   JSON using those IDs; video, music and voice require explicit separate tracks.
3. For style selection, use real previews from the 500-look gallery below. Show
   the original and chosen candidates, stable IDs, intensity and source/license.
   Read `references/client-look-selection.md`; do not present generated mockups
   as application output. Save the client's selected ID before applying it.
4. Add trim, keyframes, motion, captions and transitions. For AI operations, read
   only the relevant module/model reference, explicitly register the available
   local adapter, prefer the configured GPU, and inspect the actual provider.
   Some CUDA neural adapters require GPU and reject CPU fallback. CPU font layout
   and CPU signal conversion do not become GPU operations through documentation.
5. Validate, preview, render, quality-check and inspect actual outputs. Review
   complete audio separately. An `ok` JSON response is not natural-quality approval.
6. Export the editable package, import into a new path and rerender. Keep complete
   frame/audio/time/source hashes and record any external model/runtime dependency.

## Real filter previews

All 500 styles use the same supplied N002 still. The gallery supports names,
search, categories and a client shortlist. Images preview intensity 1.0 unless
otherwise specified. For a different source or intensity, use `look preview`.
The LUTs describe creative looks, not certified manufacturer color science.

[500-preview gallery](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/docs/assets/looks-n002-20261024-r1/index.html)
· [client selection instructions](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/skills/agent-ffmpeg-local-editor/references/client-look-selection.md)
· [complete manual](https://github.com/copypasteltd/agent-editor-kit/blob/v1.0.0/README.en.md)

CLI67 portrait regions and experimental rich typography are not installed by
this toolkit. Original G01–G38 remains open. Older evidence retains its original
version/date. Do not add full-GUI, cloud-service, model-quality or CapCut-parity
claims to a client proposal based only on this stable distribution label.
'''
    write(RELEASE / 'SKILL.md', skill)
    cases = '''# v1.0.0 casebook / 案例集 / 案例集

| ID | Input and actual output | Evidence / status |
|---|---|---|
| V1-C01 | This release's native offline package → Chinese/space path install → one registered PowerShell Skill → 2s / 60 frames test pattern + independent 48kHz stereo test tone → actual LUT edit and editable package replay | [Local acceptance](../../validation/evidence/release-v1-20261107/local-r1/verification.json); full decoded RGBA/PCM, timing and source hashes; diagnostic media, not natural content quality |
| V1-C02 | Anonymous official public downloads → all seven hashes → another new native directory → same complete Skill/package/media workflow | [Public acceptance](../../validation/evidence/release-v1-20261107/public-download-r1/verification.json); same host, not a clean machine |
| C05–C07 | User supplied N002 → 500 actual full-resolution images + 500 thumbnails → real gallery, shortlist and recorded interaction | [Full style gallery](../../assets/looks-n002-20261024-r1/index.html); historical actual installed-CLI execution, not 500 new executions this round |
| C01–C15 and later | Ads, templates, captions, voice/translation/GPU, real resource edits, semantic search, stems and independent modules | [Complete dated casebook](../../product/CASES.md); retain each actual input/output/version and rights boundary |
| CLI66 delivery | Actual CUDA music and complete media/package replay, cancellation/timeout/output conflict, two native Windows CPU upgrade/rollback | [Full formal acceptance](../../product/DELIVERY66_FORMAL_ACCEPTANCE.md), [actual model faults](../../product/DELIVERY66_ACTUAL_FAULTS.md), [second-host evidence](../../product/CROSS_MACHINE66_RESULTS.md); historical acceptance, not new model inference |

![Historical actual resource edit](../../assets/community-materials-20261025-r2/community-resources.gif)

[Actual resource MP4](../../assets/community-materials-20261025-r2/community-resources.mp4)
· [original inputs and editable case files](../../releases/v0.1.0-alpha.1/CASES.md)
· [historical full RGBA/PCM public replay](../../product/PUBLIC_RELEASE66_ACCEPTANCE.md)

The stable README preserves the complete case tables, real screenshots, MP4/GIF
links, original inputs, command/JSON details and per-case limitations. Model clips
without confirmed public redistribution rights remain local and link only to
their evidence. Silent GIFs do not establish audio quality or human listening.
'''
    write(RELEASE / 'CASES.md', cases)
    notes = '''# agent editor kit v1.0.0

首个正式发行 / 首個正式發行 / First stable distribution.

**Distribution v1.0.0 · engine CLI0.1.66 · unified Skill r60 · Windows CPython3.13 x64.**
The engine's existing version identifier is retained. This is a stable
consolidation and packaging release of the accepted engine, not a declaration
that every CapCut feature or natural-quality target is complete.

## Included

- Editable multitrack projects, keyframes/motion/transitions, templates, subtitles,
  audio workflows, rights and quality ledgers, portable project packages and recovery.
- 500 named looks with the supplied-image gallery, descriptions, attribution and
  client shortlist; actual case MP4s/GIFs, source inputs and dated evidence.
- Optional local model workflows: configured GPU voice/translation, semantic
  retrieval, stems, neural music, video generation, sessions, CUDA lip sync,
  interpolation and speech enhancement; explicit model/runtime prerequisites apply.
- Explicit Float32 composition, selected OpenCL operations, particles, optical
  effects, HDR/ICC/ACES paths with documented scope and device requirements.
- Rebuilt offline application and dependencies, 1 public Skill / 17 internal
  modules, full Simplified Chinese, Traditional Chinese and English manuals.

## Validation and scope

The accepted engine has historical source and installed regressions of **4,124
tests each, zero failures/errors/skips**. This release binds the exact application
payload to that acceptance; it does not report those as newly executed tests.
Fresh native install, actual PowerShell Skill, complete 60-frame RGBA/full stereo
PCM/package replay, Chinese/space paths and wrong-manifest/runtime rejection are
verified by this release's new acceptance receipts. Public assets are independently
redownloaded and installed after publication; see the final repository receipt.

Unaccepted CLI67 portrait regions and experimental typography remain outside the
stable packages. Original G01–G38, clean-host/GPU portability, natural model quality,
long-form performance and complete CapCut equivalence remain open.

## Install

Download **both ZIPs** plus SHA256SUMS.txt and your QUICKSTART language. Existing
native Python3.13 x64 and FFmpeg/ffprobe are required. Verify hashes, extract into
new directories, run the offline installer with the pinned manifest, configure
`--base-only`, register `$agent-ffmpeg-local-editor`, then inspect version/doctor.
Model weights, Python, FFmpeg, drivers and the complete Torch/CUDA environment
are **not included**. There is no Docker, WSL or virtual environment.

Existing installations: use a new side-by-side directory, keep old projects and
runtime/Skill pins as a pair, and follow the complete manual before registration.
No old public alpha tag or asset is overwritten. Code is MIT; model/media/font
licenses and final output rights are separate.

[完整简体手册 / 完整繁體手冊 / Complete English manual](https://github.com/copypasteltd/agent-editor-kit/tree/v1.0.0/docs/releases/v1.0.0)
'''
    write(RELEASE / 'RELEASE-NOTES.md', notes)
    print(json.dumps(dict(status='documentation-batch-written', languages=3,
        historical_rows_each=707, current_release='v1.0.0', manifest_pin_resolved=build_path.exists())))


if __name__ == '__main__':
    main()
