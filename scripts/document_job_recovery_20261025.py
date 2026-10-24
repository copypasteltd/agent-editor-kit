"""Synchronize the verified CLI 0.1.7 delivery without removing historical README evidence."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/job-recovery-20261025-r1'
REPORT = 'docs/validation/任务中断恢复实测_2026-10-25.md'


def read(name):
    return (ROOT / name).read_text('utf8')


def save(name, text):
    (ROOT / name).write_text(text, encoding='utf8', newline='\n')


def history(text):
    return [line for line in text.splitlines() if re.match(r'^\| R(?:0[1-9]|[1-4][0-9]|5[0-3]) \|', line)]


def main():
    for folder in ('installation', 'faults-r1', 'demo-r1', 'kit-r1'):
        assert json.loads((BASE / folder / 'verification.json').read_bytes())['status'] == 'passed', folder
    inventory = json.loads((ROOT / 'docs/validation/evidence/goal-gaps-20261025-r6/inventory.json').read_bytes())
    assert inventory['capability_count'] == 74 and inventory['version']['cli_version'] == '0.1.7'
    report = read(REPORT)
    if '## 单一 Skill 与 r6 kit' not in report:
        report += '''
## 单一 Skill 与 r6 kit

真实 C 盘目录联接入口另执行 **11 次 CLI/2 次实际模型前向**，auto 选择 RTX 3060，正常工作目录清理并保留四条可编辑轨；[真实入口](evidence/job-recovery-20261025-r1/skill-r1/verification.json)。
r6 kit 为 **79 文件/228,867 字节**，其中 62 个 Skill 文件，仍只注册 1 Skill/17 内部模块；
[ZIP 摘要](../skills/community-unified-skill-package-0.1.7.json)。另解包到中文/空格新目录，在隔离 discovery 中登记，
执行 8 个原生进程调用（其中 4 个 JSON CLI），确认版本、能力、四轨 dry-run 和恢复 dry-run；不改真实注册、不推理、不渲染。
[kit 独立验证](evidence/job-recovery-20261025-r1/kit-r1/verification.json) · [真实注册回执](evidence/job-recovery-20261025-r1/skill-registration.json)。

另外通过真实统一入口做 [6 次只读盘点](evidence/goal-gaps-20261025-r6/inventory.json)：74 项声明为 20 implemented、46 implemented_with_limits、7 local_adapter_only、1 degraded。
这不是完成率，不与推理或回归合并计数；官方 Release API HTTP 200 仅返回 alpha.3。所有 G01–G38 继续保留原关闭条件。
'''
    save(REPORT, report)
    entries = {
        'md': dict(title='本地 CLI 0.1.7：原生中断恢复与保留规则',
            intro='新四轨任务记录持久化工作目录与输出意图；共享 helper 管理原生子进程树。恢复先回滚待提交元数据，再检查归属：仅回收匹配身份/摘要且未引用的输出，保留提交后的四轨资产、活跃/变化/未知项和旧非管理缓存。',
            limit='已在真实安装版的 worker 启动、首个输出发布、元数据待提交与已提交四个位置强制结束 owner 并恢复；其中三个位置仅注入观察暂停，真实模型与恢复代码未替换。旧缓存、其他模型路径、断电/磁盘不足/长并发仍未全面验收，G33 不关闭。',
            latest='**最新交付（R54–R58，2026-10-25）：** 本地 CLI 0.1.7 / alpha.4-local.5、r6 kit，仍为 1 Skill/17 内部模块。部分 G33 原生进程/四轨工作目录/强制中断恢复已实现并实际验证；旧非管理缓存与完整故障矩阵仍开放。74 项声明为 20 已实现、46 有限制、7 适配器、1 降级，不是完成率。G15/G16/G20/G22/G26 原失败和全部 38 组关闭条件保留；公开仍 alpha.3 / CLI 0.1.2。',
            f03=('元数据事务/快照；原生子进程树归属；显式恢复四轨持久化工作目录和未提交输出。', '已提交资产保留；变化/活跃/未知/旧缓存保留。仅受管四轨工作目录，不是完整媒体备份或模型续算。'),
            rows=[
                'R54 | 原生生命周期与恢复回归 | 开发/安装版各 17 项专项通过；四轨各 15、旧双轨 22、CLI 122、离线 34 分别通过 | [全部范围与失败保留]('+REPORT+')；2026-10-25，0 skip、执行前后冻结摘要一致，各套件不相加',
                'R55 | 真实安装版强制中断 | 4 个模型任务仅强制结束 owner；另 17 次正常 CLI/6 次 GPU 前向；未提交输出回收，已提交四轨保留 | [4 阶段实际记录](docs/validation/evidence/job-recovery-20261025-r1/faults-r1/verification.json)；2026-10-25，三阶段有观察暂停；旧缓存/断电/磁盘/长并发未闭',
                'R56 | CLI 0.1.7 真实推理与成片 | 开发 11 次 CLI/2 前向、安装版 16/4、统一入口另 11/2；成片另 9 次 CLI，6 秒/180 帧，混音最大差 0，工程包往返 PCM/画面相同 | [C16/GIF](docs/product/CASES.md#c16-job-recovery) · [实际成片](docs/validation/evidence/job-recovery-20261025-r1/demo-r1/verification.json)；2026-10-25，受控音频留本地，无自然质量或听审验收',
                'R57 | 固定安装与单一 Skill r6 | 新 8-wheel 离线包、194 个产品 Python 文件逐字节相同；r6 79 文件，隔离注册/只读/恢复 dry-run 8 次进程调用 | [安装](docs/validation/evidence/job-recovery-20261025-r1/installation/verification.json) · [r6 kit](docs/validation/evidence/job-recovery-20261025-r1/kit-r1/verification.json)；2026-10-25，仍同一物理主机，未新建公开 Release',
                'R58 | 当前完整目标复核 | 实际统一入口另 6 次只读盘点；74 项声明与全部 38 组剩余条件保留 | [完整编号差距](docs/product/GOAL_GAPS_20261025.md) · [原始响应/API](docs/validation/evidence/goal-gaps-20261025-r6/inventory.json)；2026-10-25，0 新推理/渲染，公开 alpha.3 / CLI 0.1.2'
            ]),
        'zh-TW.md': dict(title='本機 CLI 0.1.7：原生中斷復原與保留規則',
            intro='新四軌工作記錄持久化暫存目錄與輸出意圖；共享 helper 管理原生子程序樹。復原先還原待提交中繼資料，再確認歸屬：僅清除身分/摘要相符且未引用的輸出，保留已提交四軌、執行中/變更/未知項與舊非管理快取。',
            limit='真實安裝版已在 worker 啟動、首個輸出、提交前與提交後四個位置強制結束 owner 並復原；三個位置僅注入觀察暫停，未替換模型或復原實作。舊快取、其他模型、斷電/磁碟不足/長時間並行仍未完整驗收，G33 保持開放。',
            latest='**最新交付（R54–R58，2026-10-25）：** 本機 CLI 0.1.7 / alpha.4-local.5、r6 kit，仍為 1 Skill/17 內部模組。部分 G33 原生程序/四軌暫存/強制中斷復原已實作並實測；舊非管理快取與完整故障矩陣仍開放。74 項聲明為 20 已實作、46 有限制、7 適配器、1 降級，不是完成率。G15/G16/G20/G22/G26 原失敗及全部 38 組關閉條件保留；公開仍 alpha.3 / CLI 0.1.2。',
            f03=('中繼資料事務/快照；原生子程序樹歸屬；明確復原四軌持久化暫存與未提交輸出。', '保留已提交資產、變更/執行中/未知/舊快取。僅受管四軌暫存，並非完整媒體備份或模型續算。'),
            rows=[
                'R54 | 原生生命週期與復原回歸 | 開發/安裝版各 17 項通過；四軌各 15、舊雙軌 22、CLI 122、離線 34 分別通過 | [範圍與失敗保留]('+REPORT+')；2026-10-25，0 skip、凍結摘要一致，各套件不相加',
                'R55 | 真實安裝版強制中斷 | 4 個模型工作僅結束 owner；另 17 次正常 CLI/6 次 GPU 前向；回收未提交輸出，保留已提交四軌 | [四階段紀錄](docs/validation/evidence/job-recovery-20261025-r1/faults-r1/verification.json)；2026-10-25，三階段有觀察暫停；舊快取/斷電/磁碟/長並行未閉',
                'R56 | CLI 0.1.7 真實推理與成片 | 開發 11 次 CLI/2 前向、安裝另 16/4、真實入口另 11/2；成片另 9 次 CLI，6 秒/180 幀，混音最大差 0，工程往返 PCM/畫面相同 | [C16/GIF](docs/product/CASES.md#c16-job-recovery) · [成片紀錄](docs/validation/evidence/job-recovery-20261025-r1/demo-r1/verification.json)；2026-10-25，受控音訊留本機，無自然品質或人工聽審驗收',
                'R57 | 固定安裝與單一 Skill r6 | 新 8-wheel 包、194 個產品 Python 檔案位元組相同；r6 79 檔案，隔離登記/只讀/復原 dry-run 8 次程序呼叫 | [安裝](docs/validation/evidence/job-recovery-20261025-r1/installation/verification.json) · [r6 kit](docs/validation/evidence/job-recovery-20261025-r1/kit-r1/verification.json)；2026-10-25，同一實體主機，無新公開 Release',
                'R58 | 目前完整目標複核 | 真實統一入口另 6 次只讀；74 項聲明、38 組未滿足條件保留 | [完整差距](docs/product/GOAL_GAPS_20261025.md) · [原始回應/API](docs/validation/evidence/goal-gaps-20261025-r6/inventory.json)；2026-10-25，0 新推理/渲染，公開仍 alpha.3 / CLI 0.1.2'
            ]),
        'en.md': dict(title='Local CLI 0.1.7: native interruption recovery',
            intro='Four-source jobs now retain durable workspace/publication records, while the shared helper owns native process trees. Explicit recovery restores pending metadata first, then removes only matching, unreferenced outputs. Committed stems, active/changed/unknown entries and legacy unmanaged caches are preserved.',
            limit='Four real installed model jobs were hard-stopped at worker startup, first publication, prepared metadata and committed metadata. Three boundaries use observation-only pauses; the model and recovery implementation are unchanged. Legacy caches, other workers, power loss, disk exhaustion and long concurrency remain unaccepted; G33 stays open.',
            latest='**Latest delivery (R54–R58, 2026-10-25):** local CLI 0.1.7 / alpha.4-local.5 and r6 kit; one Skill / 17 internal modules. Bounded native process and four-source workspace recovery is implemented and tested. Legacy caches and the complete fault matrix remain open. The 74 declarations are 20 implemented, 46 limited, seven adapter-only and one degraded, not a completion percentage. Original G15/G16/G20/G22/G26 failures and all 38 closure conditions remain. Public alpha.3 retains CLI 0.1.2.',
            f03=('Metadata transactions/snapshots, native child-tree ownership and explicit recovery of durable four-source workspaces/uncommitted outputs.', 'Preserves committed assets and active/changed/unknown/legacy files. Owned four-source workspaces only; not a full media backup or inference resume.'),
            rows=[
                'R54 | Native lifetime and recovery regressions | Development/installed 17 checks each; separate four-source 15 each, legacy two-source 22, CLI 122 and offline 34 pass | [Scope and retained failures]('+REPORT+'); 2026-10-25, zero skips, before/after hashes equal; overlapping suites are not summed',
                'R55 | Actual installed hard-stop recovery | Four model jobs stopped by terminating only the owner; 17 other CLI calls/six actual GPU forwards; abandoned outputs removed, committed tracks retained | [Four boundaries](docs/validation/evidence/job-recovery-20261025-r1/faults-r1/verification.json); 2026-10-25, three observation pauses; legacy caches/power loss/disk/concurrency remain open',
                'R56 | CLI 0.1.7 inference and editable delivery | Development 11 CLI/two forwards, installed 16/four, real Skill 11/two; separate nine-call render case, 6s/180 frames, mix error zero and exact PCM/pixel roundtrip | [C16/GIF](docs/product/CASES.md#c16-job-recovery) · [Actual render](docs/validation/evidence/job-recovery-20261025-r1/demo-r1/verification.json); 2026-10-25, controlled audio local only; no natural-quality/listening acceptance',
                'R57 | Pinned installation and single r6 Skill | New eight-wheel bundle; 194 product Python files byte-identical; 79-file r6 kit, eight isolated configure/register/read-only/dry-run process calls | [Installation](docs/validation/evidence/job-recovery-20261025-r1/installation/verification.json) · [Kit](docs/validation/evidence/job-recovery-20261025-r1/kit-r1/verification.json); 2026-10-25, same physical host, no new public Release',
                'R58 | Current full-goal review | Six additional real read-only Skill calls; 74 declarations and all 38 unmet group conditions retained | [Numbered gaps](docs/product/GOAL_GAPS_20261025.md) · [Raw responses/API](docs/validation/evidence/goal-gaps-20261025-r6/inventory.json); 2026-10-25, zero new inference/rendering, public alpha.3 / CLI 0.1.2'
            ])}
    for suffix, data in entries.items():
        name = 'README.' + suffix
        text = read(name)
        old = history(text)
        assert len(old) == 53 and 'job-recovery-r1' not in text
        text = text.replace('r5 Skill kit', 'r6 Skill kit').replace('agent-editor-kit-community-unified-skill-r5.zip', 'agent-editor-kit-community-unified-skill-r6.zip')
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith('**本机新增') or line.startswith('**本機新增') or line.startswith('**Local installed extension:'):
                lines[index] = line.replace('CLI 0.1.6', 'CLI 0.1.7')
            elif line.startswith('| F03 |'):
                cells = line.split('|')
                cells[3], cells[5] = ' ' + data['f03'][0] + ' ', ' ' + data['f03'][1] + ' '
                lines[index] = '|'.join(cells)
            elif line.startswith('**最新交付') or line.startswith('**Latest delivery'):
                lines[index] = data['latest']
            elif 'GOAL_GAPS_20261025.md)' in line and ('38 ' in line or '38组' in line):
                lines[index] = line.replace('CLI 0.1.6', 'CLI 0.1.7')
        text = '\n'.join(lines) + '\n'
        section = '\n<!-- job-recovery-r1 -->\n\n## ' + data['title'] + '\n\n' + data['intro'] + '''

```powershell
& $avk project recover --project $project --cleanup-jobs --dry-run
& $avk project recover --project $project --cleanup-jobs
& $avk validate --project $project
```

''' + data['limit'] + '\n\n[Workflow / 完整使用流程](docs/product/JOB_RECOVERY.md) · [Actual validation / 实测]('+REPORT+') · [C16 / actual output](docs/product/CASES.md#c16-job-recovery)\n\n<!-- /job-recovery-r1 -->\n\n'
        text = text.replace('<!-- independent-four-stems-r1 -->', section + '<!-- independent-four-stems-r1 -->', 1)
        line = next(line for line in text.splitlines() if line.startswith('| R53 |'))
        text = text.replace(line, line + '\n' + '\n'.join('| ' + row + ' |' for row in data['rows']), 1)
        assert old == history(text), name
        save(name, text)

    for suffix in ('md', 'en.md', 'zh-TW.md'):
        for prefix in ('CAPABILITIES', 'SKILLS'):
            name = 'docs/product/' + prefix + '.' + suffix
            text = read(name)
            header = ('**Current local / 当前本机 / 目前本機：CLI 0.1.7 / alpha.4-local.5。** '
                'Native process ownership and four-source job recovery; independent stems, offline retrieval, GPU voice/translation, 359 resources and capture; one Skill / 17 modules. '
                'Public alpha.3 remains CLI 0.1.2. [Installation](COMMUNITY_LOCAL_DELIVERY.md) · [Recovery / 恢复 / 復原](JOB_RECOVERY.md) · '
                '[Actual evidence](../validation/任务中断恢复实测_2026-10-25.md) · [74 current declarations](job-recovery-capabilities-cli-0.1.7.json) · [38 remaining groups](GOAL_GAPS_20261025.md).')
            text, count = re.subn(r'\*\*Current local[^\n]+', lambda _: header, text)
            assert count == 1
            if prefix == 'CAPABILITIES':
                source = read('README.' + suffix)
                row = next(line for line in source.splitlines() if line.startswith('| F03 |'))
                text = re.sub(r'^\| F03 \|[^\n]+', lambda _: row, text, flags=re.M)
            else:
                text += '\nCLI 0.1.7: K04 uses [owned job recovery](JOB_RECOVERY.md); preview `--cleanup-jobs --dry-run` and preserve active/changed/unknown/legacy files. K07 retains explicit adapter re-registration and separate model/runtime rights.\n'
            save(name, text)

    name = 'docs/product/GOAL_GAPS_20261025.md'
    text = read(name).replace('goal-gaps-20261025-r5/', 'goal-gaps-20261025-r6/').replace('four-stem-capabilities-cli-0.1.6.json', 'job-recovery-capabilities-cli-0.1.7.json')
    text = text.replace('alpha.4-local.4', 'alpha.4-local.5').replace('CLI `0.1.6`', 'CLI `0.1.7`').replace('CLI 0.1.6', 'CLI 0.1.7').replace('r5 kit', 'r6 kit')
    text = text.replace('four-stems-20261025-r1/skill-r1/', 'job-recovery-20261025-r1/skill-r1/')
    text = text.replace('；强制终止缓存回收未闭', '；新受管工作目录恢复已实测，旧缓存与完整 G33 未闭')
    text = text.replace('强制结束遗留缓存明确保留', '历史强制结束遗留缓存保留；当前新受管任务恢复另经四阶段实测')
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith('| G33 |'):
            cells = line.split('|')
            cells[3] = ' CLI 0.1.7 原生子进程树、四轨持久化工作目录/发布意图、事务后清理与显式 recover；开发/安装专项各 17 项及真实四阶段 owner 强制结束恢复通过；已提交四轨保留 '
            cells[4] = ' 仅经共享 helper 的进程树与新四轨受管目录；历史非管理缓存、其他模型路径与模型断点续算未覆盖；断电、磁盘不足、设备丢失、长并发/公平性仍未完整验收 '
            lines[index] = '|'.join(cells)
        elif line.startswith('| 回归与异常 |'):
            lines[index] = '| 回归与异常 | 恢复专项开发/安装各 17；四轨各 15、双轨 22、CLI 122、离线 34 分别通过；4 次实际强制结束＋17 次正常 CLI/6 次 GPU 前向 | [当前恢复实测](../validation/任务中断恢复实测_2026-10-25.md)；三阶段观察暂停，旧非管理缓存与完整 G33 未闭，不合并计数 |'
        elif line.startswith('| 实际可编辑案例 |'):
            lines[index] = '| 实际可编辑案例 | CLI 0.1.7：6 秒/180 帧、48kHz PCM 288,000 帧，混音差 0，包往返音画相同；提交后中断恢复保留四轨 | [C16](CASES.md#c16-job-recovery)；公开仅原创数值图与无声诊断，原音/模型权利未核验，无人工听审 |'
    text = '\n'.join(lines) + '\n'
    insertion = '\n| A13 | 原生进程归属与新四轨强制中断恢复，dry-run、提交前回收/提交后保留、统一入口及 r6 kit | 仅新受管工作目录，旧缓存保留；其他 worker、断电/磁盘不足/长并发及完整 G33 不关闭 |\n'
    text = text.replace('\n## 38 组剩余差距', insertion + '\n## 38 组剩余差距', 1)
    text += '\n本轮新增 G33 [有界恢复实测](../validation/任务中断恢复实测_2026-10-25.md)，没有撤销旧缓存失败或关闭任何完整差距组。全部 38 项关闭条件沿用原文，完整产品目标仍在进行中。\n'
    save(name, text)

    name = 'docs/product/IMPLEMENTATION_PLAN_20261025.md'
    text = read(name)
    text = text.replace('| 待执行；新目录安装不冒充新主机，机器检查与人工接受分别记录 |', '| 进行中：CLI 0.1.7 已交付原生进程树/新四轨任务四阶段强制中断恢复；旧缓存、其他 worker、断电/磁盘/长并发与干净主机/人工质量继续开放 |')
    text = text.replace('当前 CLI 0.1.6 / local.4 与 r5 kit', '当前 CLI 0.1.7 / local.5 与 r6 kit')
    text += '\n2026-10-25 G33 [有界中断恢复](../validation/任务中断恢复实测_2026-10-25.md)：共享 helper 的原生子进程树、新四轨持久化工作目录/发布意图及显式恢复已交付。实际四个强制结束阶段、正常 CPU/GPU/Skill 与工程往返均验证；旧非管理缓存作为历史失败保留。未覆盖的 worker、断电/磁盘/长并发等继续按原 G33 门槛推进，完整目标未完成。\n'
    save(name, text)

    name = 'docs/README.md'
    text = read(name).replace('v0.1.0-alpha.4-local.3 / CLI 0.1.6', 'v0.1.0-alpha.4-local.5 / CLI 0.1.7').replace('CLI 0.1.6 /', 'CLI 0.1.7 /')
    text = text.replace('Local CLI 0.1.6 includes', 'Local CLI 0.1.7 includes').replace('当前 CLI 0.1.6 的 38', '当前 CLI 0.1.7 的 38')
    text = text.replace('goal-gaps-20261025-r5/', 'goal-gaps-20261025-r6/').replace('four-stems-20261025-r1/skill-r1/', 'job-recovery-20261025-r1/skill-r1/')
    text += '\n- [CLI 0.1.7 原生任务中断恢复：流程、保留规则和范围](product/JOB_RECOVERY.md) · [真实四阶段/回归/成片](validation/任务中断恢复实测_2026-10-25.md) · [C16](product/CASES.md#c16-job-recovery)。\n'
    save(name, text)

    name = 'docs/product/CASES.md'
    text = read(name)
    assert 'id="c16-job-recovery"' not in text
    text += '''
<a id="c16-job-recovery"></a>

## C16：CLI 0.1.7 成片与强制中断恢复 / Installed output and interruption recovery

当前固定安装版保留 CPU/GPU 四源预测；选择 CUDA 四轨，受控原音仅留本机。9 次实际 CLI 完成原创数值图、6 秒/180 帧成片、检查、工程往返和发布拒绝：混音最大差 0，往返 PCM/解码 RGB 相同。

The current installed build renders a six-second numeric diagnostic with four editable CUDA tracks. Nine CLI calls verify rendering, package roundtrip and the expected rights-gate refusal. Audio stays local; this is not a natural listening-quality demonstration.

![Actual CLI 0.1.7 silent diagnostic](../assets/job-recovery-20261025-r1/installed-diagnostic-silent.gif)

[Original numeric PNG](../assets/job-recovery-20261025-r1/installed-metrics.png) · [Silent MP4](../assets/job-recovery-20261025-r1/installed-diagnostic-silent.mp4) · [Source/hash](../assets/job-recovery-20261025-r1/SOURCE.json) · [Actual render/roundtrip](../validation/evidence/job-recovery-20261025-r1/demo-r1/verification.json)。GIF 10fps/60 帧/6000ms，无声；不是中断过程录像。

同一安装工程另在实际 worker 启动、第一输出、元数据待提交和已提交后四个位置强制结束 CLI：前三者恢复原元数据并回收未提交输出；最后保留提交后的 4 WAV/四轨，只清理工作目录。三个边界仅加入观察暂停，模型/DSP/恢复实现未替换；正常渲染流程未注入。

[Four real hard-stop cases](../validation/evidence/job-recovery-20261025-r1/faults-r1/verification.json) · [Full report/retained failures](../validation/任务中断恢复实测_2026-10-25.md) · [Recovery workflow](JOB_RECOVERY.md)。旧非管理缓存保留；断电、磁盘不足、其他模型缓存、长并发、自然音频质量和人工听审仍开放，未关闭完整 G33/G36。
'''
    save(name, text)
    print(json.dumps(dict(updated_readmes=3, historical_rows_per_readme=53, new_rows='R54-R58', goal_groups=38), ensure_ascii=False))


if __name__ == '__main__':
    main()
