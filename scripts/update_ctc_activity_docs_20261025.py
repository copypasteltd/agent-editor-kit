"""Maintain current delivery documentation while retaining historical evidence rows."""
from pathlib import Path
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/ctc-activity-20261025-r1'
REPORT = 'CTC声学边界实测_2026-10-25.md'
ARCHIVE = 'a5c6f773e32122347b36ba471b5f8c28fe0fe422cd20d69d4c8a6ad96202182e'
MANIFEST = 'sha256:8aae41452002706b2c74398c1e58fc7c16db458932e62f3e3614b57248d7994a'


def read(name):
    return (ROOT / name).read_text('utf-8-sig')


def write(name, text):
    (ROOT / name).write_text(text, encoding='utf-8', newline='\n')


def load(name):
    return json.loads((BASE / name).read_bytes())


def row_cells(line):
    return [cell.strip() for cell in line.strip('|').split('|')]


def current_pages(demo, kit):
    banner = '''<!-- community-current -->

**Current local / 当前本机 / 目前本機：CLI 0.1.8 / alpha.4-local.6。** One registered Skill / 17 modules;
CTC activity boundaries, native job recovery, independent four-source separation, offline image/text retrieval,
GPU voice/translation and 359 resources. Public alpha.3 remains CLI 0.1.2.
[Current delivery](COMMUNITY_LOCAL_DELIVERY.md) · [74 declarations](ctc-activity-capabilities-cli-0.1.8.json) ·
[CTC workflow and limits](CTC_ACTIVITY_ALIGNMENT.md) · [All 38 remaining gap groups](GOAL_GAPS_20261025.md).
Controlled word-block precision does not establish natural speech/Chinese/lyrics acceptance.

<!-- /community-current -->'''
    limits = {
        'zh': '基础包不带权重；activity 保留原 CTC 并通过 6 组受控词块门槛；自然连续语音、中文和歌词精度仍未验收。[流程](docs/product/CTC_ACTIVITY_ALIGNMENT.md)',
        'tw': '基礎包不帶權重；activity 保留原 CTC 並通過 6 組受控詞塊門檻；自然連續語音、中文和歌詞精度仍未驗收。[流程](docs/product/CTC_ACTIVITY_ALIGNMENT.md)',
        'en': 'Weights remain separate; activity preserves raw CTC and passes six controlled word-block cases. Natural continuous speech, Chinese and lyrics remain unaccepted. [Workflow](docs/product/CTC_ACTIVITY_ALIGNMENT.md)',
    }
    sections = {
        'zh': '''## 本机 CLI 0.1.8：保留原时码的词活动边界

显式 `--boundary-mode activity --granularity whitespace` 使用实际 PCM 改善有静音分隔的词起止，并保留原 CTC 字符/词时间。须先明确登记已有原生 CTC Python/权重；Kokoro/OPUS 包不提供此模型。默认 `ctc` 不变，CPU/CUDA 分别选择。

开发和固定安装版分别执行 6 组实际 GPU 推理：最大误差 4.3125–4.9375ms，原 66.6667ms 门槛不变；v1/v2 失败保留。受控合成词块不证明自然连续语音、中文、歌词或重叠声音精度，G15 仍开放。
''',
        'tw': '''## 本機 CLI 0.1.8：保留原時碼的詞活動邊界

顯式 `--boundary-mode activity --granularity whitespace` 使用實際 PCM 改善有靜音分隔的詞起止，並保留原 CTC 字元/詞時間。須先明確登記已有原生 CTC Python/權重；Kokoro/OPUS 包不提供此模型。預設 `ctc` 不變，CPU/CUDA 分別選擇。

開發與固定安裝版分別執行 6 組實際 GPU 推理：最大誤差 4.3125–4.9375ms，原 66.6667ms 門檻不變；v1/v2 失敗保留。受控合成詞塊不證明自然連續語音、中文、歌詞或重疊聲音精度，G15 仍開放。
''',
        'en': '''## Local CLI 0.1.8: word activity boundaries with raw timing retained

Explicit `--boundary-mode activity --granularity whitespace` uses actual PCM to estimate isolated-word regions while retaining original CTC characters/word times. Register an existing native CTC Python/weights first; Kokoro/OPUS packs do not supply this model. Default `ctc` is unchanged; CPU/CUDA are explicit choices.

Development and installed builds each run six actual GPU cases: maximum errors 4.3125–4.9375ms under the unchanged 66.6667ms gate. v1/v2 failures are retained. Controlled authored word blocks do not establish natural continuous-speech, Chinese, singing or overlap precision; G15 remains open.
'''
    }
    commands = '''
```powershell
# Existing project/source and explicitly registered native CTC adapter required.
& $avk subtitle align --project $project --asset-id speech --adapter-id ctc --transcript $text --output assets/alignment/words.json --granularity whitespace --boundary-mode activity --dry-run
& $avk subtitle align --project $project --asset-id speech --adapter-id ctc --transcript $text --output assets/alignment/words.json --granularity whitespace --boundary-mode activity
```

[Workflow / 使用流程](docs/product/CTC_ACTIVITY_ALIGNMENT.md) · [Actual checks / 实测](docs/validation/CTC声学边界实测_2026-10-25.md) · [C17 / source, output and package](docs/product/CASES.md#c17-ctc-activity).

![Actual installed applied captions — silent diagnostic](docs/assets/ctc-activity-20261025-r1/demo-r1/actual-output-silent.gif)

'''
    labels = {
        'zh': ['受控字词对齐修复', '安装版专项与回归', 'CPU、分窗与取消', '实际字幕成片和工程包', '统一 Skill r7', '最新完整目标评估'],
        'tw': ['受控字詞對齊修復', '安裝版專項與回歸', 'CPU、分窗與取消', '實際字幕成片與工程包', '統一 Skill r7', '最新完整目標評估'],
        'en': ['Controlled word-boundary repair', 'Installed contracts/regressions', 'CPU, windows and cancellation', 'Actual caption edit/package', 'Unified Skill r7', 'Current complete-goal review'],
    }
    outcomes = {
        'zh': [
            '开发/安装版分别 36 次 CLI、6 次真实 GPU 前向；6 组全词起止均过原门槛',
            '活动边界 17、CTC 25、ASR 22 分别通过；CLI 首轮 121/122，1 项开发路径假设失败，修正测试后源码/安装各 1 项定向通过',
            'CPU 另 12 次 CLI/2 前向；兼容异常另 7/5，默认原值、47 秒分窗、SRT 绝对时钟及取消/超时保留元数据',
            f'{demo["cli_calls"]} 次 CLI/1 前向，{demo["video_frames"]} 帧；工程往返 PCM/逐帧 RGB 相同',
            f'81 文件/63 Skill 文件，1 注册入口/17 内部模块；隔离核验 {kit["process_calls"]} 次进程调用',
            '真实注册入口另 6 次只读；74 项声明/38 组差距保留，全部原关闭条件不变',
        ],
        'tw': [
            '開發/安裝版分別 36 次 CLI、6 次真實 GPU 前向；6 組全詞起止均過原門檻',
            '活動邊界 17、CTC 25、ASR 22 分別通過；CLI 首輪 121/122，1 項開發路徑假設失敗，修正測試後原始碼/安裝各 1 項定向通過',
            'CPU 另 12 次 CLI/2 前向；相容異常另 7/5，預設原值、47 秒分窗、SRT 絕對時鐘及取消/逾時保留中繼資料',
            f'{demo["cli_calls"]} 次 CLI/1 前向，{demo["video_frames"]} 影格；工程往返 PCM/逐格 RGB 相同',
            f'81 檔案/63 Skill 檔案，1 註冊入口/17 內部模組；隔離核驗 {kit["process_calls"]} 次行程呼叫',
            '真實註冊入口另 6 次唯讀；74 項宣告/38 組差距保留，全部原關閉條件不變',
        ],
        'en': [
            'Development/installed: 36 CLI calls and 6 real GPU forwards each; all boundaries pass in six cases',
            '17 activity, 25 CTC and 22 ASR pass; CLI initially 121/122 with one development-path assumption failure; corrected test passes one targeted source/installed recheck each',
            'CPU: another 12 calls/2 forwards; compatibility: 7/5, raw default, 47-second windows, SRT clocks and cancellation/timeout metadata preservation',
            f'{demo["cli_calls"]} CLI calls/1 forward, {demo["video_frames"]} frames; package PCM and every decoded RGB frame match',
            f'81 files/63 Skill files, one registration/17 modules; {kit["process_calls"]} isolated process calls',
            'Six additional read-only registered calls; 74 declarations and 38 remaining groups; all original closure conditions retained',
        ],
    }
    evidence = [
        '[Development](docs/validation/evidence/ctc-activity-20261025-r1/development-v3-r1/state.json) · [Installed](docs/validation/evidence/ctc-activity-20261025-r1/installed-r1/state.json); 2026-10-25; authored blocks, not phonetic truth; v1/v2 failures retained',
        '[Tests / retained failure](docs/validation/CTC声学边界实测_2026-10-25.md) · [Targeted installed recheck](docs/validation/evidence/ctc-activity-20261025-r1/installed-runtime-recheck-r1/verification.json); 2026-10-25; neither the full 122 nor historical 2,930 rerun after test correction',
        '[CPU](docs/validation/evidence/ctc-activity-20261025-r1/cpu-v3-r1/state.json) · [Compatibility](docs/validation/evidence/ctc-activity-20261025-r1/extended-r1/verification.json); 2026-10-25; long-window structure is not precision acceptance',
        '[C17 / GIF](docs/product/CASES.md#c17-ctc-activity) · [Actual render](docs/validation/evidence/ctc-activity-20261025-r1/demo-r1/verification.json); 2026-10-25; silent diagnostic, no human listening/continuous playback',
        '[Actual Skill](docs/validation/evidence/ctc-activity-20261025-r1/skill-r1/state.json) · [r7 kit](docs/validation/evidence/ctc-activity-20261025-r1/kit-r1/verification.json); 2026-10-25; same physical host, weights separate',
        '[38 numbered gaps](docs/product/GOAL_GAPS_20261025.md) · [Read-only inventory/API](docs/validation/evidence/goal-gaps-20261025-r8/inventory.json); 2026-10-25; public alpha.3 / CLI 0.1.2; no full CapCut acceptance',
    ]
    for name, locale in [('README.md', 'zh'), ('README.zh-TW.md', 'tw'), ('README.en.md', 'en')]:
        text = read(name)
        old_rows = [line for line in text.splitlines() if re.match(r'^\| R\d{2} \|', line)]
        assert len(old_rows) == 59 and '<!-- ctc-activity-r1 -->' not in text
        text = text.replace('r6 Skill kit', 'r7 Skill kit', 1).replace('agent-editor-kit-community-unified-skill-r6.zip', 'agent-editor-kit-community-unified-skill-r7.zip', 1)
        text = text.replace('CLI 0.1.7', 'CLI 0.1.8', 1)
        block = '<!-- ctc-activity-r1 -->\n\n' + sections[locale] + commands + '<!-- /ctc-activity-r1 -->\n\n'
        text = text.replace('<!-- job-recovery-r1 -->', block + '<!-- job-recovery-r1 -->', 1)
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith('| F25 |'):
                cells = row_cells(line);cells[-1] = limits[locale];lines[index] = '| ' + ' | '.join(cells) + ' |'
            elif not line.startswith('|') and 'GOAL_GAPS_20261025.md' in line and 'CLI 0.1.7' in line:
                summaries = {
                    'zh': '[当前完整目标差距表](docs/product/GOAL_GAPS_20261025.md)按 CLI 0.1.8 更新全部 G01–G38。单一 Skill、500 风格/预览、359 资源、GPU 配音/翻译、四轨/恢复及受控词活动边界已交付；自然视听、复杂组合、高级 AI、内容模板、Agent 自主任务、长片可靠性和新版公开包仍开放。R60–R65 分别记录真实执行及限制，不给出总体完成率。[2026-10-24 评估](docs/product/GOAL_GAPS_20261024.md)是历史快照。',
                    'tw': '[目前完整目標差距表](docs/product/GOAL_GAPS_20261025.md)按 CLI 0.1.8 更新全部 G01–G38。單一 Skill、500 風格/預覽、359 資源、GPU 配音/翻譯、四軌/恢復及受控詞活動邊界已交付；自然視聽、複雜組合、進階 AI、內容範本、Agent 自主任務、長片可靠性和新版公開包仍開放。R60–R65 分別記錄真實執行及限制，不給出總體完成率。[2026-10-24 評估](docs/product/GOAL_GAPS_20261024.md)是歷史快照。',
                    'en': '[The complete-goal assessment](docs/product/GOAL_GAPS_20261025.md) updates every G01–G38 against CLI 0.1.8. A single Skill, 500 looks/previews, 359 resources, GPU voice/translation, stems/recovery and controlled word activity timing are delivered. Natural audiovisual quality, complex combinations, advanced AI, content/templates, autonomous Agent tasks, long-job reliability and a newer public release remain open. R60–R65 retain separate real scopes and limits; no overall completion percentage is established. The [2026-10-24 assessment](docs/product/GOAL_GAPS_20261024.md) is historical.',
                }
                lines[index] = summaries[locale]
        text = '\n'.join(lines) + '\n'
        added = '\n'.join(f'| R{60+i} | {labels[locale][i]} | {outcomes[locale][i]} | {evidence[i]} |' for i in range(6))
        text = text.replace(old_rows[-1], old_rows[-1] + '\n' + added, 1)
        assert all(row in text.splitlines() for row in old_rows)
        write(name, text)
    for suffix, locale in [('', 'zh'), ('.zh-TW', 'tw'), ('.en', 'en')]:
        for family in ('CAPABILITIES', 'SKILLS'):
            name = f'docs/product/{family}{suffix}.md'
            text = re.sub(r'<!-- community-current -->.*?<!-- /community-current -->', banner, read(name), count=1, flags=re.S)
            if family == 'CAPABILITIES':
                lines = text.splitlines()
                for i, line in enumerate(lines):
                    if line.startswith('| F25 |'):
                        cells = row_cells(line);cells[-1] = limits[locale].replace('docs/product/CTC_ACTIVITY_ALIGNMENT.md', 'CTC_ACTIVITY_ALIGNMENT.md');lines[i] = '| ' + ' | '.join(cells) + ' |'
                text = '\n'.join(lines) + '\n'
            write(name, text)
        name = f'docs/skills/UNIFIED_SKILL{suffix}.md'
        skill_banner = banner.replace('(COMMUNITY_', '(../product/COMMUNITY_').replace('(ctc-activity-capabilities', '(../product/ctc-activity-capabilities').replace('(CTC_ACTIVITY_', '(../product/CTC_ACTIVITY_').replace('(GOAL_GAPS_', '(../product/GOAL_GAPS_')
        skill_banner = skill_banner.replace('One registered Skill / 17 modules;', 'One registered Skill / 17 modules; [r7 kit](agent-editor-kit-community-unified-skill-r7.zip);')
        write(name, re.sub(r'<!-- community-current -->.*?<!-- /community-current -->', skill_banner, read(name), count=1, flags=re.S))
    name = 'docs/README.md'
    text = read(name).replace('v0.1.0-alpha.4-local.5', 'v0.1.0-alpha.4-local.6')
    text = text.replace('CLI 0.1.7', 'CLI 0.1.8')
    text = text.replace('goal-gaps-20261025-r7/', 'goal-gaps-20261025-r8/')
    text = text.replace('[194 文件一致性与待验草稿](validation/evidence/goal-gaps-20261025-r8/review.json)', '[195 文件与真实对齐结果](validation/CTC声学边界实测_2026-10-25.md)')
    # Keep the explicitly historical C16 feature/version label.
    text = text.replace('- [CLI 0.1.8 原生任务中断恢复', '- [CLI 0.1.7 原生任务中断恢复')
    text += '\n- [CLI 0.1.8 词活动边界：依赖、CPU/GPU、原时间保留、字幕与质量边界](product/CTC_ACTIVITY_ALIGNMENT.md) · [全部实测与失败](validation/CTC声学边界实测_2026-10-25.md) · [C17](product/CASES.md#c17-ctc-activity)。\n'
    write(name, text)


def gap_pages():
    name = 'docs/product/GOAL_GAPS_20261025.md'
    old = read(name)
    rows = [line for line in old.splitlines() if re.match(r'^\| G\d{2} \|', line)]
    assert len(rows) == 38
    revised = []
    for row in rows:
        cells = row_cells(row)
        if cells[0] == 'G15':
            cells[2] = 'CLI 0.1.8 已交付显式 CTC activity 模式、原字符/词时间保留、控制器重算、CPU/GPU、固定安装版与统一 Skill；6 组受控词块通过原门槛'
            cells[3] = '原六词 258.1875ms 历史失败在新模式下为 4.75ms，原七词为 4.625ms；v1/v2 与 Qwen 220/161ms 失败均保留。受控作者词块不证明自然连续语音内部词界、中文逐字、歌词或重叠；仍缺独立人工精标与自然质量验收'
        elif cells[0] == 'G32':
            cells[2] += '；CTC CPU/CUDA 实测与实际前向/显存记录'
        elif cells[0] == 'G38':
            cells[2] = 'alpha.3 / CLI 0.1.2 已公开预发布；本地 alpha.4-local.6 / CLI 0.1.8 与 r7 kit 已交付'
            cells[3] = '最新官方 API 仍只有 alpha.3；当前 GPU/素材、采集、检索、四轨、任务恢复与词活动边界属于 main/本地增量；新版公开包和完整正式版门禁未过'
        revised.append('| ' + ' | '.join(cells) + ' |')
    stages = old[old.index('## 已达到的阶段性目标'):old.index('## 38 组剩余差距')]
    stages = stages.rstrip() + '\n| A14 | CLI 0.1.8 显式词活动估计、同 PCM 控制器重算、原时码保留、CPU/GPU、单一 Skill 和实际字幕工程往返 | 6 组受控词块通过；自然连续语音、中文、歌词、重叠和人工精标仍开放，不关闭 G15 |\n\n'
    quality = old[old.index('## 优先关闭的质量问题'):old.index('## 建议执行顺序')]
    qrows = quality.splitlines()
    for i, line in enumerate(qrows):
        if line.startswith('| Q01 |'):
            qrows[i] = '| Q01 | [原 CTC](../validation/离线CTC字词强制对齐实测_2026-10-18.md)与 Qwen 失败保持；新 activity 模式[受控实测](../validation/CTC声学边界实测_2026-10-25.md) | 安装版 6 组最大误差 4.3125–4.9375ms，原门槛不变；v1/v2 失败保留。独立自然精标、连续语音、中文和歌词仍不关闭 G15 |'
    order = old[old.index('## 建议执行顺序'):old.index('## 实测来源与本轮边界')]
    header = '''# 完整产品目标差距评估（2026-10-25）

[简体 README](../../README.md) · [繁體](../../README.zh-TW.md) · [English](../../README.en.md) · [完整实施台账](IMPLEMENTATION_PLAN_20261025.md)

**当前有可工作的开源 Agent 视频编辑 CLI，但尚未达到完整剪映功能与效果水准。38 组差距均仍有未满足的关闭条件；这不表示 38 组都没有实现。** 主要缺口是自然视听质量、复杂编辑组合、Agent 自主广告任务、内容/模板生态、高级 AI、资源可靠性及公开交付。

本次以已确认的[需求基线](../产品需求与开发路线基线_2026-10-12.md)、[130 项历史对照](../Concat与剪映功能差异矩阵_2026-10-12.md)、当前安装包与真实证据为准。
没有对当前剪映所有地区、平台和订阅版本作新普查，具体竞品版本与逐项质量门槛仍须冻结。
消费级 GUI、移动端交互、账号、云协作不纳入当前 CLI 收口范围；任意私有草稿无损转换没有承诺。

## 当前版本与实证

| 编号 | 核对项 | 结果和边界 |
|---|---|---|
| V01 | 已安装与注册 | alpha.4-local.6 / CLI 0.1.8，单一 `$agent-ffmpeg-local-editor`、17 内部模块、r7 kit；[安装审计](../validation/evidence/ctc-activity-20261025-r1/installation/verification.json)确认 195 个产品 Python 文件逐字节一致 |
| V02 | 实际入口盘点 | 真实注册 Skill 新增 6 次只读命令；[响应/API](../validation/evidence/goal-gaps-20261025-r8/inventory.json)；与模型/渲染分开计数 |
| V03 | 能力声明 | 74 项：20 implemented、46 implemented_with_limits、7 local_adapter_only、1 degraded；[实际响应](ctc-activity-capabilities-cli-0.1.8.json)。这是声明分布，不是总体完成率 |
| V04 | 本轮新增实际功能 | 词活动边界，原时码保留；开发/安装版分别 36 次 CLI/6 次 CUDA 前向，CPU 另 12/2，真实 Skill 另 12/2；[完整实测](../validation/CTC声学边界实测_2026-10-25.md) |
| V05 | 对齐效果 | 安装版 6 组最大误差 4.3125–4.9375ms，通过原 66.6667ms 门槛；只针对作者合成词块。自然连续语音、中文、歌词、重叠和独立人工精标未验收 |
| V06 | 回归与案例 | 安装版 17 活动/25 CTC/22 ASR 分别通过；CLI 首轮 121/122，1 项开发路径假设失败，修正测试后源码/安装各 1 项定向通过，未重跑整组。47 秒分窗/SRT/取消/超时及 C17 可编辑字幕成片另验 |
| V07 | 既有扩展 | 500 LUT、N002 500 张预览、359 资源、中英 GPU 配音/翻译、原生采集、图文检索、四轨与有界恢复继续保留；原限制和失败不因新功能而撤销 |
| V08 | 公开下载 | 最新 GitHub API 仍为 alpha.3 预发布 / CLI 0.1.2；本机与公开版本存在差距。旧 Release、附件、摘要均不覆盖 |

本轮没有重跑历史 2,930 项，没有新的自然听感/语义接受或独立 Agent 成功率结论，未建立整体完成百分比。
[上轮 r7 只读评估](../validation/evidence/goal-gaps-20261025-r7/review.json)保留当时“未集成草稿”的历史状态；它不是当前实现状态。

'''
    table = '''## 38 组剩余差距

“先收口 / 随后建设 / 完整范围扩展”表示执行顺序，沿用原 G01–G38 编号与全部关闭条件。
支持子集、已知失败、尚未实现和未完成质量验收分别写清；组大小不同，不能相加计算完成率。

| 编号 | 目标模块 | 当前已有 | 具体剩余差距 | 关闭条件 | 顺序 |
|---|---|---|---|---|---|
'''
    footer = '''## 本轮变化与继续开放项

G15 从未集成草稿进展为可安装、可由统一 Skill 调用的有限功能；原六词/七词和四组扩展词块通过。
算法、输入和原参考执行前后冻结，v1/v2/Qwen 失败保留；没有据此关闭完整 G15。
G17 自然音乐与去混响、G26 否定与库外拒识、G33 其他 worker/旧缓存及故障，仍按原条件继续。

优先验证完整真实广告主链路：明确 brief → 选材 → 多轨/字幕/配音/翻译 → 成片 → 局部返工 → 可编辑交付。
随后以长片/4K/并发、设备/磁盘故障、另一台干净原生物理主机和公开新版本收口。
高级 AI 与内容生态沿完整范围建设，不因发布预发行版而删项。

来源：[本次入口/API](../validation/evidence/goal-gaps-20261025-r8/inventory.json)、
[本轮模型/安装/Skill/成片](../validation/CTC声学边界实测_2026-10-25.md)、
[语义检索与失败](../validation/离线语义检索实测_2026-10-25.md)、
[四轨质量](../validation/独立四轨音源分离实测_2026-10-25.md)、
[任务恢复](../validation/任务中断恢复实测_2026-10-25.md)、[C17](CASES.md#c17-ctc-activity)。
所有实测在原生 Windows，未使用 Docker/WSL/虚拟环境；没有浏览器 UI 标签页遗留。

English: CLI 0.1.8 is a usable Agent editing subset, not complete CapCut parity.
All 38 original gap groups retain unmet closure conditions. New PCM activity timing passes six
controlled authored-word cases, with raw CTC preserved and failures retained; natural speech,
Chinese, singing, overlap and independent human precision remain open. Public downloads are still
alpha.3 / CLI 0.1.2. No overall completion percentage or human audiovisual acceptance is established.
'''
    write(name, header + stages + table + '\n'.join(revised) + '\n\n' + '\n'.join(qrows) + '\n\n' + order + footer)
    plan = read('docs/product/IMPLEMENTATION_PLAN_20261025.md')
    plan = plan.replace('当前 CLI 0.1.7 / local.5 与 r6 kit 已构建/本地安装', '当前 CLI 0.1.8 / local.6 与 r7 kit 已构建/本地安装')
    plan += '\n2026-10-25 G15 [显式词活动边界交付](../validation/CTC声学边界实测_2026-10-25.md)：CLI 0.1.8 / local.6，原 CTC 保留、控制器同 PCM 重算、开发/安装版/CPU/真实 Skill 分开实测，原六词/七词及四组扩展通过原门槛；v1/v2/Qwen 失败保留。自然连续语音、中文、歌词、重叠与独立人工精标仍开放，W02/W08 与完整 G15 未关闭。新 r7 kit 保留一个入口/17 模块，公开仍 alpha.3。全部 G01–G38 原关闭条件继续有效。\n'
    write('docs/product/IMPLEMENTATION_PLAN_20261025.md', plan)


def case_page(demo):
    name = 'docs/product/CASES.md'
    text = read(name)
    assert 'id="c17-ctc-activity"' not in text
    text += f'''

<a id="c17-ctc-activity"></a>

## C17：原 CTC、活动估计与实际高亮字幕 / Raw CTC, activity timing and applied captions

CLI 0.1.8 固定安装版，通过实际注册的统一 Skill 执行。原 CTC 字符/词时间保留，
activity 用同一 PCM 估计有静音分隔的词区间，控制器独立重算；原音仍是独立可编辑音轨。
下图是实际成片的无声诊断，不是自然语音精度或听感验收。

![Actual installed applied-caption output, silent](../assets/ctc-activity-20261025-r1/demo-r1/actual-output-silent.gif)

| 项目 / Item | 实际结果与边界 / Actual result and limit |
|---|---|
| 输入 / Input | [原六词 WAV](../assets/ctc-alignment-20261018/input.wav) + [校正文](../assets/ctc-alignment-20261018/transcript.txt) + [不变的作者词块参考](../assets/ctc-alignment-20261018/input-provenance.json)，125850 样本/16kHz/7.865625 秒；不是自然音素精标 |
| 原图与无字幕视频 / Original board | [PNG](../assets/ctc-activity-20261025-r1/demo-r1/comparison-board.png) · [原图无声 MP4](../assets/ctc-activity-20261025-r1/demo-r1/original-board-silent.mp4)；灰=作者摆放、橙=原 CTC 峰、绿=实际 activity |
| 实际输出 / Actual output | [无声 MP4](../assets/ctc-activity-20261025-r1/demo-r1/actual-output-silent.mp4) · [实际第 30 帧](../assets/ctc-activity-20261025-r1/demo-r1/actual-frame-30.png) · [应用的时码](../assets/ctc-activity-20261025-r1/demo-r1/applied-alignment.json)；1280×720 / 30fps / {demo['video_frames']} 帧 |
| GIF | {demo['gif_frames']} 帧 / {demo['gif_duration_ms']}ms，实际抽取的无声预览，合并相同帧后的帧数按实际文件记录 |
| 模型与成片 / Execution | {demo['cli_calls']} 次真实 Skill CLI / 1 次 CUDA 前向；`--apply` 写入可编辑字幕，独立音轨与画面经实际 render/quality/package 执行 |
| PCM 与往返 / Preservation | 与原音重采样最大差 {demo['source_pcm_max_abs_difference']}；工程包导入并重渲染，PCM 和全部解码 RGB 逐帧摘要完全相同 |
| 本机完整音画和工程 / Local AV and project | `local/agent-ffmpeg/ctc-activity-20261025-r1/installed-r1/original/renders/activity.mkv`；同 run 下 `activity.aevpkg.zip`；公共预览为无声诊断 |
| 来源与复现 / Provenance | [图形来源](../assets/ctc-activity-20261025-r1/demo-r1/SOURCE.json) · [实际执行/摘要](../validation/evidence/ctc-activity-20261025-r1/demo-r1/verification.json) · [执行器副本](../validation/evidence/ctc-activity-20261025-r1/demo-r1/executed-generator.py) |

本原输入在新模式下最大边界误差为 4.75ms，原始 CTC 为 258.1875ms；门槛仍是全词起止 66.6667ms。
另五组受控输入、CPU、安装版与真实 Skill 分别见[完整实测和保留失败](../validation/CTC声学边界实测_2026-10-25.md)。
静态 PNG 已目检；自动解码、连续人工播放、听审和自然精标分别记录，后面三项本轮没有完成。
G15/G33/G36 和完整剪映等价仍开放。

English: the installed unified Skill produces actual editable highlighted captions and an independent audio track.
The source/roundtrip PCM and every decoded RGB frame match. Public previews are silent diagnostics;
controlled authored blocks are not natural phonetic truth. Human listening, continuous playback,
natural speech, Chinese, singing and overlapping voices remain unaccepted.
'''
    write(name, text)


def prepare():
    name = 'docs/product/COMMUNITY_LOCAL_DELIVERY.md'
    text = read(name)
    assert 'CTC word-boundary extension' not in text
    text = text.replace('v0.1.0-alpha.4-local.5', 'v0.1.0-alpha.4-local.6')
    text = text.replace('/ CLI 0.1.7**', '/ CLI 0.1.8**')
    text = text.replace('local.6/candidate-r1/', 'local.6/candidate-r2/')
    text = text.replace('12f0d076f1b0dd18f7438adf678a99354a0ce6fa1b10843f326ebc2a8d8251da', ARCHIVE)
    text = text.replace('sha256:ae4daffd658d326df75d1b8c0540a3f193800f03528d0d38883a0767f73fa5a0', MANIFEST)
    text = text.replace('agent-editor-kit-community-unified-skill-r6.zip', 'agent-editor-kit-community-unified-skill-r7.zip')
    text = text.replace('community-unified-skill-package-0.1.7.json', 'community-unified-skill-package-0.1.8.json')
    text = text.replace('本轮增加[原生任务恢复]', '本轮增加[CTC 词活动边界](CTC_ACTIVITY_ALIGNMENT.md)，保留[原生任务恢复]')
    text += '''

## CLI 0.1.8 词活动边界 / CTC word-boundary extension

[完整使用流程与限制](CTC_ACTIVITY_ALIGNMENT.md)。显式 `--boundary-mode activity` 使用同一 PCM，
保留原 CTC 字符/词时间，控制器独立重算区间与决定。默认 `ctc` 语义保持。
这是另行登记的已有原生 Torch/Transformers 与 Wav2Vec2ForCTC safetensors，
**不在基础 ZIP 或四个 Kokoro/OPUS 包内**。CPU/CUDA 显式选择，不隐式下载或回退。
受控词块精度改善不代表自然连续语音、中文、歌词或重叠声音验收完成。

本轮包实际 8 wheel / 195 个产品 Python 文件，全部与源码逐字节一致：
[固定安装审计](../validation/evidence/ctc-activity-20261025-r1/installation/verification.json)。
未完成另一台干净原生主机安装；未新建公开 Release。
开发 candidate-r1 属于 v2 失败候选，保留且未激活；当前交付只匹配上表 candidate-r2/v3 摘要。

历史 local.5 / CLI 0.1.7 与 r6 kit 保留：
ZIP SHA-256 `12f0d076f1b0dd18f7438adf678a99354a0ce6fa1b10843f326ebc2a8d8251da`，
manifest `sha256:ae4daffd658d326df75d1b8c0540a3f193800f03528d0d38883a0767f73fa5a0`；
[r6 kit](../skills/agent-editor-kit-community-unified-skill-r6.zip) 与其固定的旧安装仍可复现，未被覆盖。
'''
    write(name, text)


def finish():
    installed, cpu, skill = [load(p + '/state.json') for p in ('installed-r1', 'cpu-v3-r1', 'skill-r1')]
    for value in (installed, cpu, skill):
        assert value['status'] == 'executed' and value['all_activity_gates_passed'] and value['frozen_equal']
    extended, demo, kit = [load(p + '/verification.json') for p in ('extended-r1', 'demo-r1', 'kit-r1')]
    for value in (extended, demo, kit):
        assert value['status'] == 'passed'
    checks = {}
    for folder in ('installed-contracts-r1', 'installed-ctc-regression-r1', 'installed-asr-regression-r1', 'installed-cli-regression-r1'):
        value = load(folder + '/verification.json')
        assert value['frozen_equal'] and value['skipped'] == 0
        if folder == 'installed-cli-regression-r1':
            assert value['exit_code'] == 1 and not value['terminal_ok']
        else:
            assert value['exit_code'] == 0 and value['terminal_ok']
        checks[folder] = value['methods']
    assert list(checks.values()) == [17, 25, 22, 122]
    for folder in ('installed-runtime-recheck-r1', 'source-runtime-recheck-r1'):
        value = load(folder + '/verification.json')
        assert value['methods'] == 1 and value['exit_code'] == 0 and value['terminal_ok'] and value['frozen_equal']
    rows = '\n'.join('| ' + row['fixture'] + ' | ' + str(row['quality']['raw_ctc']['max_error_ms']) + ' | '
        + str(row['quality']['activity']['max_error_ms']) + ' | 通过 |' for row in installed['cases'])
    text = f'''# CTC 词活动边界实测（2026-10-25）

[README](../../README.md) · [使用流程](../product/CTC_ACTIVITY_ALIGNMENT.md) · [完整差距](../product/GOAL_GAPS_20261025.md)

**CLI 0.1.8 / alpha.4-local.6 交付显式 activity 模式，改善有静音分隔的词边界；完整 G15 未关闭。**
原 CTC 字符及词时间保留，控制器从同一哈希绑定 PCM 独立重算决定，默认 ctc 模式未改变。
算法不读取参考词块。门槛仍为所有词起止误差各 ≤ 2/30 秒（66.6667ms）。
参考是作者摆放、按明确阈值裁切的合成词块，**不是自然音素人工精标**。

## 固定安装版结果

| 素材 | 原 CTC 最大误差 ms | activity v3 最大误差 ms | 原门槛 |
|---|---:|---:|---|
{rows}

开发源另 36 次 CLI / 6 次 CUDA 前向；固定安装版另 {installed['cli_calls']} 次 / {installed['model_forward_calls']} 次。
CPU 另 {cpu['cli_calls']} 次 / {cpu['model_forward_calls']} 次，原六词与七词相同分数；
真实注册 Skill 另 {skill['cli_calls']} 次 / {skill['model_forward_calls']} 次。每组源码、规则、输入执行前后冻结一致。
[开发](evidence/ctc-activity-20261025-r1/development-v3-r1/state.json) ·
[安装版](evidence/ctc-activity-20261025-r1/installed-r1/state.json) ·
[CPU](evidence/ctc-activity-20261025-r1/cpu-v3-r1/state.json) ·
[真实 Skill](evidence/ctc-activity-20261025-r1/skill-r1/state.json)。这些计数互相独立，不合并为完成率。

## 功能、兼容与异常

安装版活动边界专项 17 项、原 CTC 25 项、ASR 22 项分别通过，无跳过，源码执行前后相同。
专项包括弱音、DC/低信噪比、共享活动保留、邻词冲突、有限移动、显式绝对时钟、取消及控制器拒绝篡改。
协议测试不是模型推理；前面的 CUDA/CPU 才是真实神经执行。

CLI 整组首轮 121/122 通过，1 项 `test_runtime_storage_is_local_to_product` 将缓存目录写死为开发路径，
在安装版实际使用自己的运行目录时失败。原日志、执行前后冻结摘要和失败测试源码保留：
[整组原记录](evidence/ctc-activity-20261025-r1/installed-cli-regression-r1/verification.json)。
修正测试区分默认产品归属目录与显式配置，并检查实际临时/模型目录和离线标志；产品代码没有为它修改。
源码/安装版各另 1 项定向复核通过：
[源码](evidence/ctc-activity-20261025-r1/source-runtime-recheck-r1/verification.json) ·
[安装](evidence/ctc-activity-20261025-r1/installed-runtime-recheck-r1/verification.json)。
**没有在修正后重跑整组 122 项，也不将首轮写成全绿。**

另 {extended['cli_calls']} 次实际命令 / {extended['model_forward_calls']} 次 GPU 前向验证默认词范围与原始 CTC 完全相同、
47 秒长输入分窗、两个显式 SRT 段落的绝对样本时钟、预取消和超时保持三份工程元数据且不发布结果。
长窗/SRT 这一轮仅验结构与时钟，未据此宣称词界精度。
[兼容与异常记录](evidence/ctc-activity-20261025-r1/extended-r1/verification.json)。

## 真实可编辑成片

{demo['cli_calls']} 次 CLI / {demo['model_forward_calls']} 次 CUDA 前向，实际 `--apply` 后渲染字幕与独立音轨。
{demo['video_frames']} 帧 / 30fps / 1280×720；原始 PCM 差 {demo['source_pcm_max_abs_difference']}，
工程包导入重渲染的 PCM 和逐帧解码 RGB 完全相同。
GIF {demo['gif_frames']} 帧 / {demo['gif_duration_ms']}ms，仅为无声诊断；未完成人工连续播放和听审。
[C17](../product/CASES.md#c17-ctc-activity) · [原始响应](evidence/ctc-activity-20261025-r1/demo-r1/verification.json)。

## 安装与 Skill

8 个固定 wheel，195 个产品 Python 文件与源码逐字节相同；原生新目录安装，仍为同一物理主机。
r7 kit 实际 {kit['files']} 文件 / {kit['skill_files']} Skill 文件，只注册 1 个入口 / 17 内部模块；
隔离注册另 {kit['process_calls']} 次进程调用，未改变实际 Codex 发现目录，dry-run 未修改工程。
[安装审计](evidence/ctc-activity-20261025-r1/installation/verification.json) ·
[kit 核验](evidence/ctc-activity-20261025-r1/kit-r1/verification.json) ·
[当前安装流程与摘要](../product/COMMUNITY_LOCAL_DELIVERY.md)。旧包、kit、公开标签和附件均保留。

## 保留失败与剩余差距

v1 原六词/七词 210 / 140.375ms 均失败；v2 七词仍为 105.375ms。
v3 在保留原参考和全部词的前提下，处理邻接且唯一归属的弱音；不使用固定时间补偿。
两份失败源码 ZIP、原始输出和诊断保留在
[v1](evidence/ctc-activity-20261025-r1/development-r1/state.json)、
[v2](evidence/ctc-activity-20261025-r1/development-v2-r1/state.json) 与对应 failed-source ZIP。
既有 Qwen 220/161ms 失败也未被删除或改为通过。

共享连续语音、低信噪比、跨区间或邻词冲突会保留原词时间；音乐也可能被当成活动。
自然语音内部词界、中文逐字、歌词、说话人/重叠、独立精标与人工视听均开放。
已有 worker 诊断缓存不因此取得四轨受管恢复能力；G15/G33/G36 不关闭。
不新增第 75 个能力声明，不重跑历史 2,930 项，不宣称完整剪映等价。

语音来源保留 Flite 的 SLT/RMS 旧归属，以及本轮
[AWB/KAL/KAL16 原始许可与固定修订](../third-party/ctc-activity-source-20261025/)。
模型仍使用既有 Apache-2.0 记录，重型运行时与权重未装入基础 ZIP。
本轮无 Docker/WSL/容器/虚拟环境，也未打开浏览器 UI。
'''
    # A directory is not a browsable Markdown target; link a real source receipt.
    text = text.replace('../third-party/ctc-activity-source-20261025/)', '../third-party/ctc-activity-source-20261025/source.json)')
    write('docs/validation/' + REPORT, text)
    response = ROOT / 'docs/validation/evidence/goal-gaps-20261025-r8/logs/capabilities.stdout.json'
    (ROOT / 'docs/product/ctc-activity-capabilities-cli-0.1.8.json').write_bytes(response.read_bytes())
    case_page(demo)
    current_pages(demo, kit)
    gap_pages()
    print(json.dumps(dict(report=REPORT, checks=checks, installed_cli_calls=installed['cli_calls'], kit_files=kit['files']), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'finish'))
    args = parser.parse_args()
    (prepare if args.phase == 'prepare' else finish)()
