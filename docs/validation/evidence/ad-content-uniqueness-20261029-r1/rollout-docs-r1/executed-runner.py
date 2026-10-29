"""Publish only the independently accepted CLI58 kit and synchronize current documentation."""
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/ad-content-uniqueness-20261029-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, text):
    path.write_text(text, encoding='utf-8', newline='\n')


def main():
    build = load(BASE/'formal-kit-build-r2/verification.json')
    accepted = load(BASE/'formal-kit-r3/verification.json')
    package = build['package']
    assert accepted['status'] == 'passed' and accepted['kit_cli'] == '0.1.58'
    assert accepted['kit_sha256'] == package['sha256'] == sha(Path(package['archive']))
    assert accepted['complete_YUV_equal'] and accepted['complete_PCM_equal']
    assert accepted['independently_extracted'] and not accepted['actual_live_discovery_changed']
    registered = load(BASE/'registered58-gpu-r1/verification.json')
    assert registered['status'] == 'passed' and registered['actual_C_drive_entry']
    destination = ROOT/'docs/skills'/Path(package['archive']).name
    assert not destination.exists()
    shutil.copyfile(package['archive'], destination)
    assert sha(destination) == package['sha256']
    write(ROOT/'docs/skills/community-unified-skill-package-0.1.58-r56.json',
          json.dumps(dict(package, archive=destination.relative_to(ROOT).as_posix(),
                          independently_accepted=True, proof='docs/validation/evidence/ad-content-uniqueness-20261029-r1/formal-kit-r3/verification.json'), ensure_ascii=False, indent=2)+'\n')
    proof = 'docs/validation/CLI58统一Skill切换_2026-10-29.md'
    preview = '![Actual exact-content deduplication](docs/assets/ad-content58-20261029-r1/actual.gif)'
    command = "```powershell\n$skill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor'\n& \"$skill/scripts/run.ps1\" version\n& \"$skill/scripts/run.ps1\" capabilities\n```"
    prefixes = {
        'README.md': f'''**当前本地版本：CLI0.1.58 / local56 / r56统一Skill工具包。** 唯一入口 `$agent-ffmpeg-local-editor`，17内部模块、93文件。源码与安装版各31／19／57／104／400五组分别通过；候选及真实C盘入口的实际CUDA降噪、完整1124160字节PCM工程重放分别通过。完整剪映等价仍未完成。

[繁體中文](README.zh-TW.md) · [English](README.en.md) · [r56 Skill ZIP](docs/skills/agent-editor-kit-community-unified-skill-r56.zip) · [完整交付与流程]({proof}) · [500滤镜母图预览](docs/assets/looks-n002-20261024-r1/index.html)

{command}

确认版本为 `0.1.58`；按[安装使用流程](docs/validation/CLI58独立安装交付_2026-10-29.md)准备匹配应用包及原生依赖，再登记素材与权利、建立工程、执行选材与预览、渲染并导出可编辑工程包。`unique_content`默认按精确SHA256去重；[选材规则与实际案例](docs/product/AD_CONTENT_UNIQUENESS.md)说明继承、复用、查询分配及感知重复边界。

r56已在独立中文／空格目录解包、配置四个模型包、独立注册并实际重渲染；完整589824字节YUV、307200字节PCM与参考及工程包重放相同，PNG也逐字节相同。此工具包验收没有新增模型推理，不代替自然视听质量或干净机器验收。

{preview}

母图滤镜、功能／服务模块、Skill内部模块和完整案例说明均保留在下方；完整开发历史可展开查看。

''',
        'README.en.md': f'''**Current local version: CLI0.1.58 / local56 / r56 unified Skill kit.** One `$agent-ffmpeg-local-editor` entry,17 internal modules,93 files. Source and installed 31/19/57/104/400 groups passed separately. Staged and actual C-discovered CUDA denoising passed complete1124160-byte PCM package replay. Full CapCut parity remains incomplete.

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [r56 Skill ZIP](docs/skills/agent-editor-kit-community-unified-skill-r56.zip) · [Delivery and workflow]({proof})

{command}

Confirm version `0.1.58`;follow the [matching application installation](docs/validation/CLI58独立安装交付_2026-10-29.md),register media and rights,create a project,select and preview,render,and export an editable package. [Exact-content selection](docs/product/AD_CONTENT_UNIQUENESS.md) explains SHA256 deduplication,default inheritance,reuse and perceptual-duplicate limits.

The r56 kit independently passed extraction into a Chinese/space path,four-model-pack configuration,isolated registration,and actual re-rendering. Complete589824-byte YUV and307200-byte PCM match the reference and project replay;PNG bytes also match. This kit check adds no model inference and is not natural-quality or clean-host acceptance.

{preview}

The detailed feature/service modules,500-filter previews,Skill modules and cases remain below;expand the preserved development history for earlier stages.

''',
        'README.zh-TW.md': f'''**目前本地版本：CLI0.1.58 / local56 / r56統一Skill工具包。** 唯一入口 `$agent-ffmpeg-local-editor`，17內部模組、93檔案。原始碼與安裝版各31／19／57／104／400五組分別通過；候選與真實C盤入口實際CUDA降噪及完整1124160位元組PCM專案重播分別通過。完整剪映等價仍未完成。

[简体中文](README.md) · [English](README.en.md) · [r56 Skill ZIP](docs/skills/agent-editor-kit-community-unified-skill-r56.zip) · [交付與流程]({proof})

{command}

確認版本為 `0.1.58`；依[安裝使用流程](docs/validation/CLI58独立安装交付_2026-10-29.md)準備配套應用與原生依賴，再登記素材及權利、建立專案、選材與預覽、渲染並匯出可編輯專案包。[選材規則與實際案例](docs/product/AD_CONTENT_UNIQUENESS.md)說明精確SHA256去重、預設繼承、重用及感知重複邊界。

r56已在獨立中文／空格目錄解包、配置四個模型套件、獨立註冊並實際重渲染；完整589824位元組YUV、307200位元組PCM與參考及專案重播相同，PNG亦逐位元組相同。此工具包驗收未新增模型推理，不代替自然視聽品質或乾淨機器驗收。

{preview}

功能／服務模組、500濾鏡預覽、Skill內部模組與案例均保留於下方；完整開發歷史可展開查看。

'''}
    audit = {}
    for name, prefix in prefixes.items():
        path = ROOT/name
        old = path.read_text('utf-8')
        rows = re.findall(r'^\| R\d+ .*$', old, re.M)
        assert len(rows) == 455 and len(set(rows)) == 455
        marker = '<!-- aek-history-summary -->'
        before, after = old.split(marker, 1)
        title, old_intro = before.split('\n', 1)
        split = after.index('</summary>')+len('</summary>')
        after = after[:split]+'\n\n'+old_intro.strip()+'\n'+after[split:]
        new = title+'\n\n'+prefix+marker+after
        extra = {
            'README.md': [
                '| R456 | CLI58安装400项终态 | 400通过，零失败／错误／跳过，281源码与安装模块及测试冻结一致；[证据](docs/validation/evidence/ad-content-uniqueness-20261029-r1/installed58-contracts-r1/verification.json) |',
                '| R457 | CLI58统一Skill实际切换 | 候选及真实C盘入口CUDA分别4次前向；完整PCM与源码及工程重放相同，1入口／17模块／93文件，旧版备份保留；[流程](docs/validation/CLI58统一Skill切换_2026-10-29.md) |',
                '| R458 | r56独立工具包 | 159条目／158清单文件，四包配置、独立注册、两次渲染及完整YUV／PCM／PNG重放通过；首轮换行校验失败保留，无新增模型推理；[证据](docs/validation/evidence/ad-content-uniqueness-20261029-r1/formal-kit-r3/verification.json) |'],
            'README.en.md': [
                '| R456 | CLI58 installed400 terminal | All400 passed with zero failures/errors/skips;281 source/installed modules and tests frozen;[proof](docs/validation/evidence/ad-content-uniqueness-20261029-r1/installed58-contracts-r1/verification.json) |',
                '| R457 | Actual unified CLI58 activation | Staged and actual C-discovered CUDA each ran4 forwards;full PCM matches source and project replay;one entry/17 modules/93 files,old backups retained;[workflow](docs/validation/CLI58统一Skill切换_2026-10-29.md) |',
                '| R458 | Independent r56 kit | 159 entries/158 inventory files;four-pack configuration,isolated registration,two renders and full YUV/PCM/PNG replay passed;initial newline-check failure retained,no new model inference;[proof](docs/validation/evidence/ad-content-uniqueness-20261029-r1/formal-kit-r3/verification.json) |'],
            'README.zh-TW.md': [
                '| R456 | CLI58安裝400項終態 | 400通過，零失敗／錯誤／跳過，281原始碼與安裝模組及測試凍結一致；[證據](docs/validation/evidence/ad-content-uniqueness-20261029-r1/installed58-contracts-r1/verification.json) |',
                '| R457 | CLI58統一Skill實際切換 | 候選及真實C盤入口CUDA各4次前向；完整PCM與原始碼及專案重播相同，1入口／17模組／93檔案，舊版備份保留；[流程](docs/validation/CLI58统一Skill切换_2026-10-29.md) |',
                '| R458 | r56獨立工具包 | 159條目／158清單檔案，四包配置、獨立註冊、兩次渲染及完整YUV／PCM／PNG重播通過；首輪換行校驗失敗保留，未新增模型推理；[證據](docs/validation/evidence/ad-content-uniqueness-20261029-r1/formal-kit-r3/verification.json) |']}
        previous = next(row for row in rows if row.startswith('| R455 |'))
        new = new.replace(previous, previous+'\n'+'\n'.join(extra[name]), 1)
        assert all(row in new for row in rows)
        assert len(re.findall(r'^\| R\d+ .*$', new, re.M)) == 458
        write(path, new)
        audit[name] = dict(previous_rows_preserved=455, current_rows=458, sha256=sha(path))
    current = '''**CLI0.1.58 / local56 / r56: one `$agent-ffmpeg-local-editor` entry,17 modules,93 files.** Source and independently installed31/19/57/104/400 groups passed separately. Staged and actual C-discovered CUDA denoising passed full PCM replay. The r56 kit independently passed extraction,four-pack configuration,isolated registration and complete ACES YUV/PCM/PNG replay without changing live discovery. No new model inference is claimed for that kit check.

[Download r56 kit](agent-editor-kit-community-unified-skill-r56.zip) · [SHA-256](community-unified-skill-package-0.1.58-r56.json) · [Installation and use](../validation/CLI58独立安装交付_2026-10-29.md) · [Rollout proof](../validation/CLI58统一Skill切换_2026-10-29.md) · [Exact-content selection and C74 preview](../product/AD_CONTENT_UNIQUENESS.md)

Pair this kit with the separate CLI58/local56 application bundle and existing model packs. It adds exact-SHA256 content deduplication,not perceptual duplicate detection. Same-host native Windows acceptance does not establish clean-host,natural-quality or full CapCut parity. Previous r55/runtime56 downloads remain immutable.
'''
    for suffix in ['', '.en', '.zh-TW']:
        path = ROOT/('docs/skills/UNIFIED_SKILL'+suffix+'.md')
        text = path.read_text('utf-8')
        text, count = re.subn(r'(?s)(<!-- community-current -->).*?(<!-- /community-current -->)',lambda m:m[1]+'\n\n'+current+'\n'+m[2],text,count=1)
        assert count == 1
        write(path, text)
    out = BASE/'rollout-docs-r1'
    out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    write(out/'verification.json', json.dumps(dict(status='passed', cli_version='0.1.58', kit_sha256=sha(destination), readmes=audit, previous_releases_unchanged=True, full_product_goal_closed=False),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='published-and-documented', kit_sha256=sha(destination), readmes=audit),ensure_ascii=False))


if __name__ == '__main__':
    main()
