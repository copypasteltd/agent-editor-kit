"""Publish only the independently accepted CLI59 kit and synchronize current documentation."""
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/music-score-20261029-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, text):
    path.write_text(text, encoding='utf-8', newline='\n')


def main():
    build = load(BASE/'formal-kit-build-r1/verification.json')
    accepted = load(BASE/'formal-kit-r1/verification.json')
    package = build['package']
    assert accepted['status'] == 'passed' and accepted['kit_cli'] == '0.1.59'
    assert accepted['kit_sha256'] == package['sha256'] == sha(Path(package['archive']))
    assert accepted['complete_YUV_equal'] and accepted['complete_PCM_equal']
    assert accepted['independently_extracted'] and not accepted['actual_live_discovery_changed']
    registered = load(BASE/'registered59-gpu-r1/verification.json')
    assert registered['status'] == 'passed' and registered['actual_C_drive_entry']
    destination = ROOT/'docs/skills'/Path(package['archive']).name
    assert not destination.exists()
    shutil.copyfile(package['archive'], destination)
    assert sha(destination) == package['sha256']
    write(ROOT/'docs/skills/community-unified-skill-package-0.1.59-r57.json',
          json.dumps(dict(package, archive=destination.relative_to(ROOT).as_posix(),
                          independently_accepted=True, proof='docs/validation/evidence/music-score-20261029-r1/formal-kit-r1/verification.json'), ensure_ascii=False, indent=2)+'\n')
    proof = 'docs/validation/CLI59统一Skill切换_2026-10-29.md'
    preview = '![Actual installed59 score and measured waveform](docs/assets/music-score59-installed-20261029-r1/actual.gif)'
    command = "```powershell\n$skill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor'\n& \"$skill/scripts/run.ps1\" version\n& \"$skill/scripts/run.ps1\" capabilities\n```"
    prefixes = {
        'README.md': f'''**当前本地版本：CLI0.1.59 / local57 / r57统一Skill工具包。** 唯一入口 `$agent-ffmpeg-local-editor`，17内部模块、93文件。源码与安装版各31／19／57／104／400五组分别通过；候选及真实C盘入口的实际CUDA降噪、完整1124160字节PCM工程重放分别通过。完整剪映等价仍未完成。

[繁體中文](README.zh-TW.md) · [English](README.en.md) · [r57 Skill ZIP](docs/skills/agent-editor-kit-community-unified-skill-r57.zip) · [完整交付与流程]({proof}) · [500滤镜母图预览](docs/assets/looks-n002-20261024-r1/index.html)

{command}

确认版本为 `0.1.59`；按[安装使用流程](docs/validation/CLI59独立安装交付_2026-10-29.md)准备匹配应用包及原生依赖，再登记素材与权利、建立工程、执行选材与预览、渲染并导出可编辑工程包。`unique_content`默认按精确SHA256去重；[选材规则与实际案例](docs/product/AD_CONTENT_UNIQUENESS.md)说明继承、复用、查询分配及感知重复边界。

r57已在独立中文／空格目录解包、配置四个模型包、独立注册并实际重渲染；完整589824字节YUV、307200字节PCM与参考及工程包重放相同，PNG也逐字节相同。此工具包验收没有新增模型推理，不代替自然视听质量或干净机器验收。

{preview}

母图滤镜、功能／服务模块、Skill内部模块和完整案例说明均保留在下方；完整开发历史可展开查看。

''',
        'README.en.md': f'''**Current local version: CLI0.1.59 / local57 / r57 unified Skill kit.** One `$agent-ffmpeg-local-editor` entry,17 internal modules,93 files. Source and installed 31/19/57/104/400 groups passed separately. Staged and actual C-discovered CUDA denoising passed complete1124160-byte PCM package replay. Full CapCut parity remains incomplete.

[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [r57 Skill ZIP](docs/skills/agent-editor-kit-community-unified-skill-r57.zip) · [Delivery and workflow]({proof})

{command}

Confirm version `0.1.59`;follow the [matching application installation](docs/validation/CLI59独立安装交付_2026-10-29.md),register media and rights,create a project,select and preview,render,and export an editable package. [Exact-content selection](docs/product/AD_CONTENT_UNIQUENESS.md) explains SHA256 deduplication,default inheritance,reuse and perceptual-duplicate limits.

The r57 kit independently passed extraction into a Chinese/space path,four-model-pack configuration,isolated registration,and actual re-rendering. Complete589824-byte YUV and307200-byte PCM match the reference and project replay;PNG bytes also match. This kit check adds no model inference and is not natural-quality or clean-host acceptance.

{preview}

The detailed feature/service modules,500-filter previews,Skill modules and cases remain below;expand the preserved development history for earlier stages.

''',
        'README.zh-TW.md': f'''**目前本地版本：CLI0.1.59 / local57 / r57統一Skill工具包。** 唯一入口 `$agent-ffmpeg-local-editor`，17內部模組、93檔案。原始碼與安裝版各31／19／57／104／400五組分別通過；候選與真實C盤入口實際CUDA降噪及完整1124160位元組PCM專案重播分別通過。完整剪映等價仍未完成。

[简体中文](README.md) · [English](README.en.md) · [r57 Skill ZIP](docs/skills/agent-editor-kit-community-unified-skill-r57.zip) · [交付與流程]({proof})

{command}

確認版本為 `0.1.59`；依[安裝使用流程](docs/validation/CLI59独立安装交付_2026-10-29.md)準備配套應用與原生依賴，再登記素材及權利、建立專案、選材與預覽、渲染並匯出可編輯專案包。[選材規則與實際案例](docs/product/AD_CONTENT_UNIQUENESS.md)說明精確SHA256去重、預設繼承、重用及感知重複邊界。

r57已在獨立中文／空格目錄解包、配置四個模型套件、獨立註冊並實際重渲染；完整589824位元組YUV、307200位元組PCM與參考及專案重播相同，PNG亦逐位元組相同。此工具包驗收未新增模型推理，不代替自然視聽品質或乾淨機器驗收。

{preview}

功能／服務模組、500濾鏡預覽、Skill內部模組與案例均保留於下方；完整開發歷史可展開查看。

'''}
    audit = {}
    for name, prefix in prefixes.items():
        path = ROOT/name
        old = path.read_text('utf-8')
        rows = re.findall(r'^\| R\d+ .*$', old, re.M)
        assert len(rows) == 465 and len(set(rows)) == 465
        marker = '<!-- aek-history-summary -->'
        before, after = old.split(marker, 1)
        title, old_intro = before.split('\n', 1)
        split = after.index('</summary>')+len('</summary>')
        after = after[:split]+'\n\n'+old_intro.strip()+'\n'+after[split:]
        music = {
            'README.md':'新增可编辑谱面解析合成：8类音色、4类电子音效、5分轨实际案例与完整PCM重合成。正式Skill59已真实生成；不是神经文本生曲。先检查谱面／dry-run，再生成、试听、挂接、渲染及导出工程包。[完整JSON与命令](docs/product/MUSIC_SCORE.md) · [C75真实WAV／MP4／GIF及可编辑工程](docs/product/CASES.md#c75-source59-editable-score)。独立r57工具包也通过实际配乐生成，3072000字节PCM与源码相同。',
            'README.en.md':'New editable analytical score synthesis:8 instruments,4 electronic effects,actual5-stem case and full PCM recomposition. Registered Skill59 generated it;this is not neural text-to-music. Inspect/dry-run,compose,audition,place,render and export an editable package. [JSON and commands](docs/product/MUSIC_SCORE.md) · [C75 actual WAV/MP4/GIF and project](docs/product/CASES.md#c75-source59-editable-score). The independently registered r57 kit also generated all3072000 PCM bytes matching source.',
            'README.zh-TW.md':'新增可編輯譜面解析合成：8類音色、4類電子音效、5分軌實際案例及完整PCM重合成。正式Skill59已實際生成；不是神經文本生曲。先檢查譜面／dry-run，再生成、試聽、掛接、渲染與匯出專案包。[完整JSON及命令](docs/product/MUSIC_SCORE.md) · [C75真實WAV／MP4／GIF與可編輯專案](docs/product/CASES.md#c75-source59-editable-score)。獨立r57工具包亦通過實際配樂生成，3072000位元組PCM與原始碼相同。'}
        new = title+'\n\n'+prefix+music[name]+'\n\n'+marker+after
        extra = {
            'README.md': [
                '| R466 | CLI59安装400项终态 | 400通过，零失败／错误／跳过，281源码与安装模块及测试冻结一致；[证据](docs/validation/evidence/music-score-20261029-r1/installed58-contracts-r1/verification.json) |',
                '| R467 | CLI59统一Skill实际切换 | 候选及真实C盘入口CUDA分别4次前向；完整PCM与源码及工程重放相同，1入口／17模块／93文件，旧版备份保留；[流程](docs/validation/CLI59统一Skill切换_2026-10-29.md) |',
                '| R468 | r57独立工具包 | 160条目／159清单文件，四包配置、独立注册、两次渲染及完整YUV／PCM／PNG重放通过；首轮换行校验失败保留，无新增模型推理；[证据](docs/validation/evidence/music-score-20261029-r1/formal-kit-r1/verification.json) |'],
            'README.en.md': [
                '| R466 | CLI59 installed400 terminal | All400 passed with zero failures/errors/skips;282 source/installed modules and tests frozen;[proof](docs/validation/evidence/music-score-20261029-r1/installed58-contracts-r1/verification.json) |',
                '| R467 | Actual unified CLI59 activation | Staged and actual C-discovered CUDA each ran4 forwards;full PCM matches source and project replay;one entry/17 modules/93 files,old backups retained;[workflow](docs/validation/CLI59统一Skill切换_2026-10-29.md) |',
                '| R468 | Independent r57 kit | 160 entries/159 inventory files;four-pack configuration,isolated registration,two renders and full YUV/PCM/PNG replay passed;initial newline-check failure retained,no new model inference;[proof](docs/validation/evidence/music-score-20261029-r1/formal-kit-r1/verification.json) |'],
            'README.zh-TW.md': [
                '| R466 | CLI59安裝400項終態 | 400通過，零失敗／錯誤／跳過，281原始碼與安裝模組及測試凍結一致；[證據](docs/validation/evidence/music-score-20261029-r1/installed58-contracts-r1/verification.json) |',
                '| R467 | CLI59統一Skill實際切換 | 候選及真實C盤入口CUDA各4次前向；完整PCM與原始碼及專案重播相同，1入口／17模組／93檔案，舊版備份保留；[流程](docs/validation/CLI59统一Skill切换_2026-10-29.md) |',
                '| R468 | r57獨立工具包 | 160條目／159清單檔案，四包配置、獨立註冊、兩次渲染及完整YUV／PCM／PNG重播通過；首輪換行校驗失敗保留，未新增模型推理；[證據](docs/validation/evidence/music-score-20261029-r1/formal-kit-r1/verification.json) |']}
        previous = next(row for row in rows if row.startswith('| R465 |'))
        new = new.replace(previous, previous+'\n'+'\n'.join(extra[name]), 1)
        assert all(row in new for row in rows)
        assert len(re.findall(r'^\| R\d+ .*$', new, re.M)) == 468
        write(path, new)
        audit[name] = dict(previous_rows_preserved=465, current_rows=468, sha256=sha(path))
    current = '''**CLI0.1.59 / local57 / r57: one `$agent-ffmpeg-local-editor` entry,17 modules,93 files.** Source and independently installed31/19/57/104/400 groups passed separately. Staged and actual C-discovered CUDA denoising passed full PCM replay. The r57 kit independently passed extraction,four-pack configuration,isolated registration and complete ACES YUV/PCM/PNG replay without changing live discovery. The kit also generated the actual score with complete3072000-byte PCM matching source;no new neural inference is claimed for that kit check.

[Download r57 kit](agent-editor-kit-community-unified-skill-r57.zip) · [SHA-256](community-unified-skill-package-0.1.59-r57.json) · [Installation and use](../validation/CLI59独立安装交付_2026-10-29.md) · [Rollout proof](../validation/CLI59统一Skill切换_2026-10-29.md) · [Exact-content selection and C74 preview](../product/AD_CONTENT_UNIQUENESS.md)

Pair this kit with the separate CLI59/local57 application bundle and existing model packs. It adds editable analytical score synthesis and4 procedural effects;exact-SHA256 content deduplication remains,not perceptual duplicate detection. Same-host native Windows acceptance does not establish clean-host,natural-quality or full CapCut parity. Previous r55/runtime56 downloads remain immutable.
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
    write(out/'verification.json', json.dumps(dict(status='passed', cli_version='0.1.59', kit_sha256=sha(destination), readmes=audit, previous_releases_unchanged=True, full_product_goal_closed=False),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='published-and-documented', kit_sha256=sha(destination), readmes=audit),ensure_ascii=False))


if __name__ == '__main__':
    main()
