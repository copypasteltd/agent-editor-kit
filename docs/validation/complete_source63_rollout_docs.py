"""Synchronize CLI63 documentation only after the corresponding real delivery gates."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/job-enumeration-20261029-r1'
NOTE = 'docs/validation/CLI63统一Skill切换_2026-10-29.md'
KIT = 'docs/skills/agent-editor-kit-community-unified-skill-r58.zip'
LANGS = ('README.md', 'README.zh-TW.md', 'README.en.md')


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(text, prefix):
    return re.findall(r'^\| ' + prefix + r'\d+ \|.*$', text, re.M)


def write(path, text):
    path.write_text(text, encoding='utf-8', newline='\n')


def gate(paths):
    missing = [str(p.relative_to(ROOT)) for p in paths if not p.is_file()]
    if missing:
        print(json.dumps(dict(status='pending', missing=missing, mutated=False)))
        return False
    return True


def registered_gates():
    paths = [BASE / 'skill63-activation-r1/verification.json',
             BASE / 'registered-controller-r1/verification.json',
             BASE / 'installed63-contracts-r2/verification.json']
    if not gate(paths):
        return None
    activation, registered, contracts = map(load, paths)
    assert activation['status'] == 'activated-and-entry-verified'
    assert activation['cli_version'] == registered['cli_version'] == '0.1.63'
    assert not activation['post_test_document_changes']
    assert registered['status'] == 'passed' and registered['actual_C_drive_entry']
    assert registered['actual_loop_DF3_MuseTalk_passed']
    assert registered['registered_skill_files_frozen'] == 93
    assert contracts['status'] == 'passed' and contracts['tests'] == 406
    assert contracts['failures'] == contracts['errors'] == contracts['skipped'] == 0
    assert contracts['frozen_equal'] and contracts['source_and_installed_equal']
    for p, digest in contracts['file_hashes'].items():
        assert sha(ROOT / p) == digest
    for pin in activation['gates'].values():
        assert sha(ROOT / pin['path']) == pin['sha256']
    assert sha(ROOT / 'agent-ffmpeg-local-install-manifest.json') == activation['namespace_sha256']
    assert sha(ROOT / 'local/agent-ffmpeg/runtime.json') == activation['runtime_sha256']
    manifest = load(ROOT / 'agent-ffmpeg-local-install-manifest.json')
    assert manifest['cli_version'] == '0.1.63' and len(manifest['files']) == 93
    assert all(sha(ROOT / r['path']) == r['sha256'] for r in manifest['files'])
    return activation, registered, contracts


def registered_note():
    install = load(BASE / 'installation-candidate-r1/verification.json')
    return f'''# CLI63统一Skill切换与使用

正式本地版本为 **CLI0.1.63 / local61**，唯一入口 `$agent-ffmpeg-local-editor`，17内部模块、93文件。原C盘发现目录继续联接E盘Skill；应用、模型配置与回滚备份保留在E盘。不使用Docker、WSL或虚拟环境。

## 实际交付

| 编号 | 内容 | 证据与边界 |
| --- | --- | --- |
| 1 | 原生离线安装，1707载荷／283应用模块／8原生资源相同 | [安装收据](evidence/job-enumeration-20261029-r1/installation-candidate-r1/verification.json)；不是干净主机验收 |
| 2 | 源码和安装版分别31入口／37配乐循环／26进程控制／57选材／104语义／406合同通过 | [安装406-r2](evidence/job-enumeration-20261029-r1/installed63-contracts-r2/verification.json)；分组有重叠，不相加宣称独立功能数；r1中断日志保留 |
| 3 | 源码、安装、候选Skill及真实C盘入口分别实际执行DF3 CUDA、MuseTalk CUDA和CPU循环修复 | [正式入口控制器](evidence/job-enumeration-20261029-r1/registered-controller-r1/verification.json)；实际完整PCM／RGBA及工程包重放，不等于自然质量听审 |
| 4 | 切换93个已实测Skill文件及运行配置，保留备份 | [激活收据](evidence/job-enumeration-20261029-r1/skill63-activation-r1/verification.json)；注册字节与候选实测相同，没有测试后再改Skill说明 |
| 5 | 纳入103音色本地选型说明 | [103音色原始实测](CLI61全音色试听_2026-10-29.md)来自CLI61候选，不冒充CLI63重新生成；WAV仅内部未审核 |

应用位置：`{install['installed']}`。完整离线ZIP为305698303字节，SHA256为`c9151896fe28de8446adfe35633b18956e3e390bac0ccaa038f713be233e9727`；这是本地交付，不是新的公开GitHub Release。小Skill包、应用ZIP、Python／FFmpeg与模型包分别准备，不把小Skill包描述成完整运行环境。

## 本机操作顺序

```powershell
$entry = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
$project = 'E:/video-work/customer-edit' # 新工程路径
& $entry version
& $entry doctor
& $entry capabilities
& $entry project init $project
& $entry media ingest --help
& $entry music repair-loop --help
```

1. `version`应返回`0.1.63`。通过统一Skill的启动器运行安装版，不静默退回源码。先用`doctor`检查实际依赖，模型功能按其内部说明登记已有本地权重和显式设备配置。
2. 导入授权素材，登记来源／许可／证据，保留原文件。用稳定资产ID建立时间线；声音需要明确音轨。按命令`--help`查看所选模型与效果的具体输入，不能根据模型目录存在推断已经推理成功。
3. 选滤镜时先向客户展示[500项母图实测](../assets/looks-n002-20261024-r1/index.html)的真实候选图，保留ID／强度，再在客户实际素材上预览。母图效果不代表所有光源、肤色和动态镜头都适用。
4. 配音前打开本地`local/agent-ffmpeg/voice-preview61-r2/preview/index.html`，按语言、音色ID提供真实WAV供内部试听。103项音频来自CLI61实际CUDA生成，尚无人类听审，也未公开发布音频；不能直接承诺客户文本的发音、情绪或商业授权。
5. 配乐可用[可编辑谱面](../product/MUSIC_SCORE.md)或既有授权音乐。循环接缝用下面的预检／生成命令；核对缩短后的长度，提供原始与修复后的WAV，客户听审后再挂接。配乐合成与交叠修复是CPU DSP，DF3／MuseTalk实际CUDA不算GPU音乐生成。
6. 先预览、再渲染并检查实际编码音画，导出可编辑工程包；来源、配方、权重依赖和权利状态须保留。更换新资产ID修订，不覆盖已接受版本。

```powershell
# SOURCE须是已导入且可使用的音频资产；AUDIO_TRACK须是可写的音轨ID。
& $entry music repair-loop --project $project --asset-id SOURCE --crossfade-ms 50 --curve raised-cosine --new-asset-id loop1 --dry-run
& $entry music repair-loop --project $project --asset-id SOURCE --crossfade-ms 50 --curve raised-cosine --new-asset-id loop1 --apply --track-id AUDIO_TRACK
# 按实际返回的recipe_uri指定配方；重做使用新ID。
& $entry music repair-loop --project $project --input 'E:/video-work/recipe.json' --new-asset-id loop2
```

输出采用48kHz双声道16bit工作PCM，交叠M样本后周期从N缩短为N−M；不自动补回原时长。`--dry-run`不解码，无法保证实际样本数或音频足够长。完整语义、权限继承、源SHA256、配额与失败行为见[循环修复](../product/MUSIC_LOOP.md)。

![C76实际边界波形；这是诊断图，不是听审](../assets/music-loop60-20261029-r1/actual.png)

[原始三循环WAV](../assets/music-loop60-20261029-r1/before.wav) · [修复三循环WAV](../assets/music-loop60-20261029-r1/after.wav) · [实际可编辑配方](../assets/music-loop60-20261029-r1/recipe.json)。这些公开原始样例来自C76历史执行；新CLI63各层完整PCM与其直接比较，不能将历史样例改标为本轮新录制。

## 剩余边界

CLI60安装400的超时错误码失败、CLI61候选口型存储扫描失败及CLI62清理枚举失败均保留原始证据。CLI63修复自有进程枚举与退出同步；不因此声称已唯一复现CLI62自然故障的底层原因。

第二台Windows目前仅只读环境预检通过；不是干净机器、安装或GPU推理验收。连续播放、人类听审、自然画面质量、商业素材适用性、完整开源依赖和全部38项原关闭条件仍开放。现有公开alpha.3标签及附件保持不变。

## r58工具包

正式入口已通过实际任务；r58独立解包、重新配置和重放仍须其单独终态收据。通过前不提供下载，也不将构建成功写成安装验收成功。
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=('registered', 'kit'), required=True)
    a = p.parse_args()
    ready = registered_gates()
    if ready is None:
        return 2
    if a.phase == 'kit' and not gate([BASE / 'rollout-registered-docs-r1/verification.json',
                                    BASE / 'formal-kit-build-r1/verification.json',
                                    BASE / 'formal-kit-r1/verification.json']):
        return 2
    out = BASE / ('rollout-' + a.phase + '-docs-r1')
    assert not out.exists()
    manifest = ROOT / 'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT / 'local/agent-ffmpeg/runtime.json'
    protected = {manifest: sha(manifest), runtime: sha(runtime)}
    protected.update({ROOT / r['path']: r['sha256'] for r in load(manifest)['files']})
    originals = {ROOT / n: (ROOT / n).read_text(encoding='utf-8') for n in LANGS}
    counts = {len(rows(t, 'R')) for t in originals.values()}
    assert len(counts) == 1
    expected_rows = counts.pop()
    assert expected_rows >= 523
    for t in originals.values():
        assert [int(re.match(r'^\| R(\d+) \|', r)[1]) for r in rows(t, 'R')] == list(range(1, expected_rows + 1))
    if a.phase == 'kit':
        assert expected_rows == load(BASE / 'rollout-registered-docs-r1/verification.json')['README_rows']
    goal = ROOT / 'docs/product/GOAL_GAPS_20261025.md'
    old_goal = goal.read_text(encoding='utf-8')
    assert len(rows(old_goal, 'G')) == 38
    planned = {}
    if a.phase == 'registered':
        planned[ROOT / NOTE] = registered_note()
        lead = [
            '**当前正式本地版本：CLI0.1.63 / local61。** 唯一入口 `$agent-ffmpeg-local-editor`，17内部模块、93文件。源码与安装分别31／37／26／57／104／406组通过；候选与真实C盘入口CPU循环修复、DF3及MuseTalk CUDA和完整音画工程包重放分别通过。r58独立工具包仍待验收，公开Release保持alpha.3／CLI0.1.2；完整剪映等价未完成。',
            '**目前正式本地版本：CLI0.1.63 / local61。** 唯一入口 `$agent-ffmpeg-local-editor`，17內部模組、93檔案。原始碼與安裝版分別31／37／26／57／104／406組通過；候選與真實C盤入口CPU循環修復、DF3及MuseTalk CUDA與完整音畫專案重播分別通過。r58獨立工具包仍待驗收，公開Release維持alpha.3／CLI0.1.2；完整剪映等價未完成。',
            '**Current registered local version: CLI0.1.63 / local61.** One `$agent-ffmpeg-local-editor` entry, 17 modules, 93 files. Source and installed 31/37/26/57/104/406 groups passed separately; staged and C-discovered loop repair, DF3/MuseTalk CUDA and full AV project replay passed. Independent r58 kit acceptance is pending; public alpha.3 still contains CLI0.1.2. Full CapCut parity remains open.']
        workflow = [
            '先确认版本，再检查依赖、建立工程并登记授权素材。展示500滤镜实际候选图及103音色本地WAV，记录选择；先预检，再生成、试听、挂接时间线、预览、渲染和导出工程包。循环修复会缩短周期，不能承诺原时长或未经听审的无缝效果。',
            '先確認版本，再檢查依賴、建立專案並登記授權素材。展示500濾鏡實際候選圖與103音色本地WAV，記錄選擇；先預檢，再生成、試聽、掛接時間線、預覽、渲染與匯出專案。循環修復會縮短週期，不能承諾原時長或未經聽審的無縫效果。',
            'Confirm the version, check dependencies, create a project and register authorized media. Present real 500-look previews and local 103-voice WAVs, record selections, then dry-run, generate, audition, place, preview, render and export. Loop overlap shortens the cycle; it does not establish listening approval or the original duration.']
        links = f'[简体中文](README.md) · [繁體中文](README.zh-TW.md) · [English](README.en.md) · [CLI63 workflow]({NOTE}) · [500 look previews](docs/assets/looks-n002-20261024-r1/index.html) · [103 voice auditions](docs/validation/CLI61全音色试听_2026-10-29.md)'
        command = '''```powershell
$entry = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $entry version # 0.1.63
& $entry doctor
& $entry music repair-loop --help
```'''
        labels = [('CLI63安装完整回归', 'CLI63统一Skill正式切换'),
                  ('CLI63安裝完整回歸', 'CLI63統一Skill正式切換'),
                  ('CLI63 installed full regression', 'CLI63 registered unified Skill')]
        for i, (path, text) in enumerate(originals.items()):
            title, _, rest = text.partition('\n\n')
            old_top, marker, history = rest.partition('<!-- aek-history-summary -->')
            assert marker and '<summary>' in history
            end = history.index('</summary>') + len('</summary>')
            kept = history[:end] + '\n\n' + old_top + history[end:]
            prefix = lead[i] + '\n\n' + links + '\n\n' + command + '\n\n' + workflow[i]
            prefix += '\n\n[Loop commands and before/after WAVs](docs/product/MUSIC_LOOP.md) · [Editable score](docs/product/MUSIC_SCORE.md)\n\n'
            prefix += '![Actual C76 boundary diagnostic](docs/assets/music-loop60-20261029-r1/actual.png)\n\n'
            prefix += '![Actual CLI61 local103 voice gallery](docs/assets/voice-gallery61-20261029-r1/actual.png)\n\n'
            new = title + '\n\n' + prefix + marker + kept
            old_rows = rows(text, 'R')
            extra = [f'| R{expected_rows + 1} | {labels[i][0]} | 31/37/26/57/104/406, zero failures/errors/skips; exact installed/source bytes. [406-r2 proof](docs/validation/evidence/job-enumeration-20261029-r1/installed63-contracts-r2/verification.json) |',
                     f'| R{expected_rows + 2} | {labels[i][1]} | 1 entry/17 modules/93 tested files; actual loop/DF3 CUDA/MuseTalk CUDA, full PCM/RGBA and package replay. Historical CLI61 103-voice guidance included before testing. Natural quality/clean host open. [Workflow]({NOTE}) |']
            new = new.replace(old_rows[-1], old_rows[-1] + '\n' + '\n'.join(extra), 1)
            assert rows(new, 'R')[:expected_rows] == old_rows
            assert old_top.strip() in new and len(rows(new, 'R')) == expected_rows + 2
            planned[path] = new
        for name in ('MUSIC_LOOP.md', 'MUSIC_SCORE.md'):
            path = ROOT / 'docs/product' / name
            text = path.read_text(encoding='utf-8')
            title = text.splitlines()[0]
            current = '\n\n2026-10-29 正式交付更新：CLI0.1.63/local61已安装并注册，真实C盘入口循环修复、DF3及MuseTalk CUDA和完整音画工程包重放已通过。下方旧候选／59版本文字保留为阶段历史；当前统一Skill可执行本页已实现命令。[实际使用流程](../validation/CLI63统一Skill切换_2026-10-29.md)。'
            planned[path] = text.replace(title, title + current, 1)
        title = old_goal.splitlines()[0]
        updated = old_goal.replace(title, title + '\n\n2026-10-29 G25/G33/G34：CLI63/local61正式统一Skill已通过候选与真实C盘入口CPU循环修复、DF3/MuseTalk CUDA和完整音画包重放；[交付使用](../validation/CLI63统一Skill切换_2026-10-29.md)。原38项关闭条件不变，自然听审、干净主机与完整产品继续开放。', 1)
        assert rows(updated, 'G') == rows(old_goal, 'G')
        planned[goal] = updated
    else:
        build = load(BASE / 'formal-kit-build-r1/verification.json')
        accepted = load(BASE / 'formal-kit-r1/verification.json')
        package = build['package']
        assert accepted['status'] == 'passed' and accepted['kit_cli'] == '0.1.63'
        assert accepted['kit_sha256'] == package['sha256'] == sha(Path(package['archive']))
        assert accepted['kit_entries'] == 161 and accepted['inventory_files'] == 160 and accepted['skill_files'] == 93
        assert accepted['complete_YUV_equal'] and accepted['complete_PCM_equal'] and accepted['PNG_file_byte_equal']
        assert accepted['complete_loop_package_repair_PCM_equal'] and accepted['complete_source_score_PCM_equal']
        assert accepted['independently_extracted'] and accepted['independent_E_drive_registration']
        assert not accepted['actual_live_discovery_changed'] and accepted['new_model_forwards'] == 0
        destination = ROOT / KIT
        summary = ROOT / 'docs/skills/community-unified-skill-package-0.1.63-r58.json'
        assert not destination.exists() and not summary.exists()
        receipt = dict(package, archive=KIT, independently_accepted=True,
                       proof='docs/validation/evidence/job-enumeration-20261029-r1/formal-kit-r1/verification.json')
        planned[summary] = json.dumps(receipt, ensure_ascii=False, indent=2) + '\n'
        kit_texts = [
            '**r58统一Skill工具包已独立验收。** 161条目／160清单文件／93 Skill文件；中文和空格目录解包、四包配置、独立注册、实际谱面与循环修复、完整ACES YUV／PCM／PNG及工程包重放通过。未新增模型推理，不等于干净主机或自然质量验收。',
            '**r58統一Skill工具包已獨立驗收。** 161條目／160清單檔案／93 Skill檔案；中文與空格目錄解包、四包配置、獨立註冊、實際譜面與循環修復、完整ACES YUV／PCM／PNG及專案重播通過。未新增模型推理，不等於乾淨主機或自然品質驗收。',
            '**The r58 unified Skill kit passed independent acceptance.** 161 entries/160 inventory files/93 Skill files; Chinese/space extraction, four-pack setup, isolated registration, actual score and loop generation, full ACES YUV/PCM/PNG and project replay passed. No new neural inference; clean-host and natural-quality acceptance remain open.']
        for i, (path, text) in enumerate(originals.items()):
            title, _, rest = text.partition('\n\n')
            link = f'[r58 Skill ZIP]({KIT}) · [SHA256](docs/skills/community-unified-skill-package-0.1.63-r58.json) · [使用流程 / Workflow]({NOTE})'
            new = title + '\n\n' + kit_texts[i] + '\n\n' + link + '\n\n' + rest
            new = new.replace('r58独立工具包仍待验收，', 'r58工具包已独立验收，', 1)
            new = new.replace('r58獨立工具包仍待驗收，', 'r58工具包已獨立驗收，', 1)
            new = new.replace('Independent r58 kit acceptance is pending;', 'The r58 kit passed independent acceptance;', 1)
            old_rows = rows(text, 'R')
            extra = f'| R{expected_rows + 1} | CLI63/r58 independent kit | 161/160/93 entries/inventory/Skill files; isolated setup/registration, full score/loop PCM and ACES YUV/PCM/PNG package replay. No new neural forwards or clean-host acceptance. [Proof](docs/validation/evidence/job-enumeration-20261029-r1/formal-kit-r1/verification.json) |'
            new = new.replace(old_rows[-1], old_rows[-1] + '\n' + extra, 1)
            assert rows(new, 'R')[:expected_rows] == old_rows and len(rows(new, 'R')) == expected_rows + 1
            planned[path] = new
        path = ROOT / NOTE
        planned[path] = path.read_text(encoding='utf-8') + f'''\n\n### 最终r58独立验收

[r58下载](../skills/agent-editor-kit-community-unified-skill-r58.zip)及[摘要](../skills/community-unified-skill-package-0.1.63-r58.json)：{package['bytes']}字节，SHA256 `{package['sha256']}`。161条目／160清单文件／93 Skill文件；独立中文／空格路径解包、既有四包配置与独立注册通过。完整谱面3072000字节PCM、循环修复2557440字节PCM及工程包按配方重做通过；ACES全部589824字节YUV、307200字节PCM及PNG与参考／包重放相同。

[实际终态证据](evidence/job-enumeration-20261029-r1/formal-kit-r1/verification.json)。该工具包验证未新增神经前向，未改变正式发现入口；同机新路径不等于干净新主机。包内文档是构建时快照，本节及README顶部反映后续终态。旧r57包保持原摘要不变。
'''
    current_text = ('**CLI0.1.63 / local61: one `$agent-ffmpeg-local-editor` entry, 17 modules, 93 files.** '
                    'Source and installed 31/37/26/57/104/406 groups passed separately. '
                    'Actual staged and C-discovered loop repair, DF3 CUDA, MuseTalk CUDA and complete AV package replay passed. '
                    'Loop overlap shortens the sample period; natural quality, listening approval, clean hosts and all38 original closure conditions remain open.\n\n'
                    '[使用流程 / Workflow](../validation/CLI63统一Skill切换_2026-10-29.md) · '
                    '[Loop repair and WAVs](../product/MUSIC_LOOP.md) · '
                    '[103 local voice auditions](../validation/CLI61全音色试听_2026-10-29.md)\n\n')
    if a.phase == 'kit':
        current_text += ('The independently accepted r58 kit has161 entries/160 inventory files/93 Skill files. '
                         'Four-pack setup, independent registration, score/loop PCM and ACES YUV/PCM/PNG package replay passed; '
                         'no new neural inference in this kit check. Application ZIP, Python/FFmpeg and models remain separate.\n\n'
                         '[r58 Skill ZIP](agent-editor-kit-community-unified-skill-r58.zip) · '
                         '[SHA256](community-unified-skill-package-0.1.63-r58.json)\n')
    else:
        current_text += 'Independent r58 kit acceptance is pending; no new kit download is claimed. Public alpha.3/CLI0.1.2 is unchanged.\n'
    for suffix in ('', '.en', '.zh-TW'):
        path = ROOT / ('docs/skills/UNIFIED_SKILL' + suffix + '.md')
        text = path.read_text(encoding='utf-8')
        pattern = r'(?s)(<!-- community-current -->)(.*?)(<!-- /community-current -->)'
        found = re.search(pattern, text)
        assert found
        old_current = found[2]
        new = re.sub(pattern, lambda m: m[1] + '\n\n' + current_text + '\n' + m[3], text, count=1)
        new += '\n\n<details>\n<summary>CLI63 delivery history / 保留先前交付状态</summary>\n' + old_current + '\n</details>\n'
        planned[path] = new
    # Validate the full plan before changing any document. Skill bytes stay frozen.
    for path, text in planned.items():
        assert path.is_relative_to(ROOT) and text.endswith('\n')
    out.mkdir(exist_ok=False)
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    if a.phase == 'kit':
        shutil.copyfile(package['archive'], destination)
        assert sha(destination) == package['sha256']
    before = {p.relative_to(ROOT).as_posix(): sha(p) if p.exists() else None for p in planned}
    for path, text in planned.items():
        write(path, text)
    assert all(sha(p) == digest for p, digest in protected.items())
    assert rows(goal.read_text(encoding='utf-8'), 'G') == rows(old_goal, 'G')
    result = dict(status='passed', phase=a.phase, cli_version='0.1.63',
                  README_rows=expected_rows + (2 if a.phase == 'registered' else 1),
                  previous_README_rows_preserved=expected_rows, original_goal_rows_preserved=38,
                  frozen_formal_files=95, public_release_changed=False, full_goal_closed=False,
                  before=before, after={p.relative_to(ROOT).as_posix(): sha(p) for p in planned})
    write(out / 'verification.json', json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
