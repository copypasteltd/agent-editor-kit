"""Synchronize completed native recovery evidence and all original goal conditions."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-recovery-20261025-r1'
REPORT = 'docs/validation/语义任务中断恢复实测_2026-10-25.md'
GUIDE = 'docs/product/SEMANTIC_JOB_RECOVERY.md'
CASES = ('index-publication', 'calibration-publication', 'calibration-commit',
         'search-hard-stop', 'search-cancel', 'search-timeout', 'cleanup')
PENDING = {}


def read(path): return PENDING[path] if path in PENDING else (ROOT / path).read_text('utf-8-sig')
def write(path, value): PENDING[path] = value
def load(path): return json.loads((BASE / path).read_bytes())
def numbered(text, prefix):
    return {m[1]: m[0] for m in re.finditer(r'^\| (' + prefix + r'\d{2})\s*\|.*$', text, re.M)}
def row(text, key, value):
    text, count = re.subn(r'^\| ' + key + r'\s*\|.*$', lambda _: value, text, flags=re.M)
    assert count == 1, (key, count)
    return text


def main():
    installation = load('installation-r1/verification.json')
    assert installation['source_file_count'] == 202 and installation['source_and_installed_equal']
    for name in ('development-r1', 'development-cli-r1', 'installed-r1', 'installed-cli-r1'):
        v = load('tests/' + name + '/verification.json')
        assert v['status'] == 'passed' and v['frozen_equal'] and v['installed_frozen_equal']
        assert v['result'] == dict(methods=122 if 'cli' in name else 150,
                                  skipped=0, failures=0, errors=0, success=True)
    faults = {name: load('faults-r1/' + name + '/verification.json') for name in CASES}
    assert all(v['status'] == 'passed' for v in faults.values())
    phases = ('setup-cuda', 'index-cuda', 'calibrate-cuda', 'calibrate-cpu', 'before-cuda',
              'before-cpu', 'roundtrip-cuda', 'after-cuda', 'after-cpu', 'skill-cuda')
    actual = {name: load('installed-r1/' + name + '/verification.json') for name in phases}
    assert all(v['status'] == 'completed-with-explicit-quality-limits' for v in actual.values())
    for name in ('after-cuda', 'after-cpu', 'skill-cuda'):
        assert actual[name]['all_80_decisions_and_ordered_hits_identical']
        assert actual[name]['original_source_and_external_paths_unavailable']
    quality = []
    for name in ('before-cuda', 'before-cpu', 'after-cuda', 'after-cpu', 'skill-cuda'):
        q = actual[name]['quality']
        errors = [r['id'] for r in q['queries'] if not (r['top1_correct'] if r['expected_asset_ids'] else r['rejected'])]
        assert set(errors) == {'q14', 'hout00zh', 'hout08zh'}
        quality.append(f'| {name} | {q["positive"]["correct"]}/36 | {q["negation"]["correct"]}/22 | {q["out_of_library"]["correct"]}/20 | {q["out_of_domain"]["correct"]}/2 | ' + ', '.join(errors) + ' |')
    seconds = faults['search-timeout']['fault_process']['elapsed_seconds']
    fault_rows = '\n'.join('| J%02d | %s | 通过；%s 次命令 | [原始证据](evidence/semantic-recovery-20261025-r1/faults-r1/%s/verification.json) |' %
        (i, name, faults[name]['calls'], name) for i, name in enumerate(CASES, 1))
    phase_rows = '\n'.join(f'| {name} | {v["calls"]} | [{v["started_at_utc"]} — {v["finished_at_utc"]}](evidence/semantic-recovery-20261025-r1/installed-r1/{name}/verification.json) |' for name, v in actual.items())
    write(REPORT, '''# 语义任务中断恢复实测（CLI 0.1.12，2026-10-25）

本机 `alpha.4-local.10 / CLI 0.1.12`，唯一 `$agent-ffmpeg-local-editor`、17 内部模块。
本轮将登记、索引、校准、检索接入持久任务/原生租约；索引与校准目录采用发布意图、文件/目录身份和 SHA 保护。
这推进 G33 的明确子项，并让 G32 的冷启动成本可观察；[全部 38 组原关闭条件](../product/GOAL_GAPS_20261025.md)保留。

## 分范围核验

| 编号 | 范围 | 实际结果及边界 |
|---|---|---|
| T01 | 树恢复专项 | [22/22](evidence/semantic-recovery-20261025-r1/tests/trees-r1/verification.json)；包含引用、同字节替换、额外文件/空目录、发布前后和部分清理；已包含在 150 项中，不另加总 |
| T02 | 源码相关契约 | [150/150](evidence/semantic-recovery-20261025-r1/tests/development-r1/verification.json)，0 skip；合成夹具不计模型质量 |
| T03 | 源码 CLI | [122/122](evidence/semantic-recovery-20261025-r1/tests/development-cli-r1/verification.json)，0 skip |
| T04 | 固定安装版相关契约 | [另 150/150](evidence/semantic-recovery-20261025-r1/tests/installed-r1/verification.json)，0 skip |
| T05 | 固定安装版 CLI | [另 122/122](evidence/semantic-recovery-20261025-r1/tests/installed-cli-r1/verification.json)，0 skip；3 项既有子进程使用字节相同源码路径，未冒充额外安装测试 |
| T06 | 离线应用 | [302663151 bytes / 202 个产品 Python 文件](evidence/semantic-recovery-20261025-r1/installation-r1/verification.json)与源码逐字节相同；旧 ZIP/安装保留 |
| T07 | 配置与统一入口 | [实际激活/4 包校验](evidence/semantic-recovery-20261025-r1/activation-r1/verification.json)，仍为同一主机，未新增权重下载 |
| T08 | 独立工具包 | [r11 同机新目录/注册/8 次调用](evidence/semantic-recovery-20261025-r1/kit-r2/verification.json)；不是另一台干净主机验收 |

应用 ZIP SHA-256 `''' + installation['archive_sha256'] + '''`；manifest `''' + installation['manifest_sha256'] + '''`。
没有以本轮替代历史 2930 项回归，没有人类听审、自然语义接受或新的视觉效果录像。
激活和登记实际退出码均为 0；收集 helper 随后误把本机编码的人类可读登记 stdout 当作 UTF-8 JSON，
触发解析错误。改读登记器已写出的结构化 registration.json 后继续实际能力调用，未重复激活/登记；
[控制器失败保留](evidence/semantic-recovery-20261025-r1/activation-r1/controller-failure-r1.json)与原始流原样留档。
工具包首次验证 helper 误指向旧 CLI 0.1.11 工程，触发 SEMANTIC_ADAPTER_INTEGRITY_FAILED；
[原失败](evidence/semantic-recovery-20261025-r1/kit-r1/failure.json)保留。修正到本批已登记/迁移的工程，
在新 r2 目录重做完整 8 次调用；没有修改旧工程或适配器 SHA 来绕过保护。

## 真实模型故障与恢复

既有 SigLIP2、Torch 原生进程实际执行。发布/提交边界的暂停只存在验证 helper 的内存包装，
未替换模型预测、生产发布或恢复代码；只结束本次创建并持有句柄的进程，不终止其他 GPU 程序。

| 编号 | 实际阶段 | 结果 | 证据 |
|---|---|---|---|
''' + fault_rows + '''

发布后未提交：恢复事务后回收本任务未引用树，原元数据/输入保持。
提交后：任一资产/活动权利引用保护整个目录，清理诊断后真实查询新校准 ID 仍可用。
运行中强停/取消：在 worker 报告 model-loading 时操作，原生句柄验证 worker 已退出；不声称已验证 CUDA kernel 内取消。
正常清理：先 dry-run，再显式回收受管诊断，已提交索引/校准/权利/素材字节不变，随后实际查询成功。
旧 cache/semantic-jobs、变化目录和未知记录保留，不采用 blanket cache 删除。

**实际超时限制**：请求 1 秒超时的故障进程约 ''' + f'{seconds:.3f}' + ''' 秒才终止并返回 PROCESS_TIMEOUT。
其中包含同步完整性检查；错误类型符合预期，但响应时限没有通过。取消也可能被该同步区段延后。
该失败边界继续列在 G32/G33；不将该用例描述为“1 秒准时终止”。

## 冻结语义回归与工程迁移

[本批故障协议](evidence/semantic-recovery-20261025-r1/frozen/protocol.json)，SHA-256
`23d312f14e82bb69d80dda73e3143eb1dc4e67ddc2b82b65db401d777ac09199`。
沿用 [原协议](evidence/semantic-decision-20261025-r1/frozen/protocol.json)：11 资产、10 类熟悉静态图；
40 校准、60 另组措辞与 20 原查询。没有调阈值、添加自然素材或改变原三条错误。
CPU/CUDA 各 80 条在工程两次往返且原路径不可用后保持全部决策/排序，真实 Skill 另执行 80 条。

| 入口/阶段 | 正向 top-1 | 否定 top-1 | 另组库外拒绝 | 原库外拒绝 | 已知错误 |
|---|---:|---:|---:|---:|---|
''' + '\n'.join(quality) + '''

大象/吉他误接受、中文钟表误拒仍保留。这是恢复/迁移完整性回归，不增加独立自然检索质量结论。
[C20 既有真实预览与 GIF](../product/CASES.md#c20-semantic-package)是前一版演示，不标作本批执行录像。
[C21](../product/CASES.md#c21-semantic-recovery)提供本批输入、命令、原始响应、恢复和预期失败边界。

## 耗时与完整响应

worker-phase.json 与 phase_seconds 分开记录环境、导入、完整性校验、加载、推理。
首次 inspect 的实际导入约 72.56 秒、校验约 20.90 秒；不同任务阶段耗时不同，不能加总为统一模型速度。
仍逐命令加载，尚无常驻模型；其他原生任务同时存在，墙钟不是独占 benchmark。

| 阶段 | 命令数 | UTC 开始—结束 / 原始收据 |
|---|---:|---|
''' + phase_rows + '''

仍缺：其他 worker 的系统接入、断电/磁盘耗尽/设备丢失/长并发、及时的全流程取消/超时、
常驻复用、大库/4K/长片、独立自然视听、干净主机与新版公开发行。
[使用流程](../product/SEMANTIC_JOB_RECOVERY.md) · [固定契约](../specs/语义任务发布与中断恢复契约_20261025.md) ·
[安装方式](../product/COMMUNITY_LOCAL_DELIVERY.md)。全程原生 Windows，无 Docker/WSL/虚拟环境/浏览器 UI。
''')
    labels = {
        '': ('本机 CLI 0.1.12：语义任务恢复与诊断', '登记、索引、校准和检索纳入受管任务；发布前写入身份/SHA，提交引用保护整棵目录。7 类真实故障/清理用例通过结构恢复检查，但 1 秒超时响应延后至约 %.3f 秒；完整性能与恢复目标未完成。' % seconds),
        '.zh-TW': ('本機 CLI 0.1.12：語義任務恢復與診斷', '登記、索引、校準與檢索納入受管任務；發布前寫入身分/SHA，已提交引用保護整棵目錄。7 類真實故障/清理案例通過結構恢復檢查，但 1 秒逾時回應延後至約 %.3f 秒；完整效能與恢復目標未完成。' % seconds),
        '.en': ('Local CLI 0.1.12: managed semantic recovery', 'Registration, indexing, calibration and search now use owned durable jobs. Identity/SHA publication records protect whole referenced directories. Seven real fault/cleanup cases pass recovery checks; the 1-second timeout still takes about %.3f seconds. Full performance and recovery acceptance remains open.' % seconds)}
    for suffix, (title, intro) in labels.items():
        path = 'README' + suffix + '.md'; text = read(path); old = numbered(text, 'R'); assert len(old) == 87
        review = '**CLI 0.1.12 / alpha.4-local.10 / r11 kit** · 202 product Python files · 1 Skill / 17 modules. ' + intro
        text, n = re.subn(r'<!-- current-goal-review-r14 -->.*?<!-- /current-goal-review-r14 -->',
            '<!-- current-goal-review-r15 -->\n\n' + review + '\n\n[All 38 numbered gaps](docs/product/GOAL_GAPS_20261025.md) · [Actual checks](' + REPORT + ')\n\n<!-- /current-goal-review-r15 -->', text, flags=re.S); assert n == 1
        block = re.search(r'<!-- community-materials-gpu -->.*?<!-- /community-materials-gpu -->', text, re.S); assert block
        text = text[:block.start()] + block[0].replace('CLI 0.1.11', 'CLI 0.1.12') + text[block.end():]
        text = text.replace('CPU 46 条、GPU 15 条为本轮独立实测。12 秒真实成片', 'CPU 46 条、GPU 15 条属于素材/GPU 扩展历史批次的独立实测，本次语义恢复未重跑它们。该批 12 秒真实成片')
        text = text.replace('CPU 46 條、GPU 15 條為本輪獨立實測。12 秒真實成片', 'CPU 46 條、GPU 15 條屬於素材/GPU 擴充歷史批次的獨立實測，本次語義恢復未重跑它們。該批 12 秒真實成片')
        text = text.replace('CPU 46 commands and GPU 15 commands are separate current tests. The real 12-second edit', 'The 46 CPU and 15 GPU commands are separate tests from the earlier materials/GPU batch; this semantic-recovery batch did not rerun them. That batch\'s real 12-second edit')
        text = text.replace('[r10 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r10.zip)', '[r11 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r11.zip)')
        text = text.replace('v0.1.0-alpha.4-local.9/final-r1/installed/', 'v0.1.0-alpha.4-local.10/final-r1/installed/')
        text = '\n'.join(line.replace('CLI 0.1.11', 'CLI 0.1.12') if ('alpha.4-local.10/final-r1/installed/' in line or
            ('GOAL_GAPS_20261025.md' in line and not line.startswith('|'))) else line for line in text.split('\n'))
        section = '<!-- semantic-recovery-r1 -->\n\n## ' + title + '\n\n' + intro + '\n\n[Workflow](' + GUIDE + ') · [Real evidence and limitations](' + REPORT + ') · [C21](docs/product/CASES.md#c21-semantic-recovery) · [r11 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r11.zip)\n\n```powershell\n& $avk project recover --project $project --cleanup-jobs --dry-run\n& $avk project recover --project $project --cleanup-jobs\n& $avk validate --project $project\n```\n\nInspect the dry-run and retain required diagnostics first. Cleanup preserves committed references, active jobs, changed/unknown files and legacy caches. It does not resume inference.\n\n<!-- /semantic-recovery-r1 -->\n\n'
        text = text.replace('<!-- semantic-package-r1 -->', section + '<!-- semantic-package-r1 -->', 1)
        text = text.replace('## ' + {'': '本机', '.zh-TW': '本機', '.en': 'Local'}[suffix] + ' CLI 0.1.11', '## ' + {'': '历史', '.zh-TW': '歷史', '.en': 'Historical'}[suffix] + ' CLI 0.1.11')
        f = numbered(text, 'F')['F03'].split('|')
        f[3] += {'': ' 新增语义登记/索引/校准/检索的受管任务。', '.zh-TW': ' 新增語義登記/索引/校準/檢索的受管任務。', '.en': ' Adds managed semantic registration/index/calibration/search jobs.'}[suffix]
        f[-2] = {'': ' 整棵已引用语义目录保护；活跃/变化/未知/旧缓存保留。仅已接入任务，不是模型续算；同步校验可能延迟超时。 ', '.zh-TW': ' 整棵已引用語義目錄保護；活躍/變化/未知/舊快取保留。僅已接入任務，不是模型續算；同步校驗可能延遲逾時。 ', '.en': ' Whole referenced semantic directories protected; active/changed/unknown/legacy paths retained. Only integrated jobs; no inference resume; synchronous checks may delay deadlines. '}[suffix]
        text = row(text, 'F03', '|'.join(f))
        additions = [
            ('R88', '源码范围 / Source checks', '150 related contracts; separate 122 CLI; zero skips; 22 tree cases included, not added', 'tests/development-r1/verification.json'),
            ('R89', '固定安装 / Installed checks', '202 source-identical Python files; separate 150 related contracts / 122 CLI; zero skips', 'tests/installed-r1/verification.json'),
            ('R90', '实际恢复 / Real recovery', '7 actual native model fault/cleanup cases; owned worker exit and pre/post-commit invariants; no power-loss claim', 'faults-r1/calibration-commit/verification.json'),
            ('R91', '语义回归 / Query regression', 'CPU/CUDA/registered Skill each preserve all 80 decisions after migration; known 3 errors retained', 'installed-r1/skill-cuda/verification.json'),
            ('R92', '性能失败保留 / Timing limitation', '1-second timeout actually %.3fs; imports/hash/load/inference observable; no persistent service or deadline pass' % seconds, 'faults-r1/search-timeout/verification.json'),
            ('R93', '单入口交付 / Single-entry delivery', 'CLI 0.1.12 / local.10 / r11; 1 Skill / 17 modules; same-host isolated kit, no clean-machine claim', 'kit-r2/verification.json'),
            ('R94', '完整目标复核 / Full goal review', 'All G01–G38 original closure conditions and R01–R87 retained; public release/API checked separately; no overall percentage', 'final-delivery-r2/verification.json')]
        lines = '\n'.join('| ' + key + ' | ' + label + ' | ' + detail + ' | [2026-10-25 evidence](docs/validation/evidence/semantic-recovery-20261025-r1/' + target + ') · [Scope](' + REPORT + ') |' for key, label, detail, target in additions)
        text = text.replace(old['R87'], old['R87'] + '\n' + lines, 1)
        text = re.sub(r'\*\*Current delivery /[^\n]+', '**Current delivery / 当前交付 / 目前交付（R88–R94，2026-10-25）：** CLI 0.1.12 / local.10 / r11; 202 product files, 1 Skill / 17 modules. Native semantic recovery added; observed timeout overrun and three known query errors remain. Public alpha.3 assets and all 38 original conditions preserved.', text)
        assert all(numbered(text, 'R')[key] == value for key, value in old.items())
        write(path, text)
    for stem in ('CAPABILITIES', 'SKILLS'):
        for suffix in ('', '.zh-TW', '.en'):
            path = 'docs/product/' + stem + suffix + '.md'; text = read(path)
            match = re.search(r'<!-- community-current -->.*?<!-- /community-current -->', text, re.S); assert match
            block = match[0].replace('0.1.11', '0.1.12').replace('alpha.4-local.9', 'alpha.4-local.10').replace('semantic-package-capabilities', 'semantic-recovery-capabilities')
            block = block.replace('[Current delivery]', '[Semantic recovery](SEMANTIC_JOB_RECOVERY.md) · [Current delivery]')
            text = text[:match.start()] + block + text[match.end():]
            write(path, text.replace('[Machine response](semantic-package-capabilities-cli-0.1.11.json)', '[Machine response](semantic-recovery-capabilities-cli-0.1.12.json)'))
    path = 'docs/product/COMMUNITY_LOCAL_DELIVERY.md'; text = read(path); start = text.index('## CLI 0.1.11')
    current = text[:start].replace('alpha.4-local.9', 'alpha.4-local.10').replace('0.1.11', '0.1.12').replace('unified-skill-r10.zip', 'unified-skill-r11.zip')
    current = current.replace('5f8526444d468c62563cdaf805597bd288cb59624956518e5f3dd185b492e90d', installation['archive_sha256']).replace('sha256:bc29ef0d61e71e04fe498c416a287cdd9a15fe729e3e4d26a5f9216d4a48eaa9', installation['manifest_sha256'])
    current = current.replace('本轮增加[语义工程包迁移]', '本轮增加[语义任务恢复](SEMANTIC_JOB_RECOVERY.md)，保留[语义工程包迁移]')
    write(path, current + '## CLI 0.1.12 语义任务恢复 / Managed semantic recovery\n\n302663151 bytes、202 个产品 Python 文件；[完整实测](../validation/语义任务中断恢复实测_2026-10-25.md)。\n7 类真实故障/清理核验；1 秒超时存在同步校验延后，未关闭完整 G32/G33。旧 local.9/r10 和全部历史证据保留。\n\n' + text[start:])
    path = 'docs/product/GOAL_GAPS_20261025.md'; text = read(path); original = numbered(text, 'G')
    start = text.index('2026-10-25 当前本地交付为'); end = text.index('\n\n| 编号', start)
    text = text[:start] + '2026-10-25 当前本地交付为 **CLI 0.1.12 / alpha.4-local.10 / r11 kit**，202 个产品 Python 文件与固定安装版相同。新增语义登记/索引/校准/检索受管恢复，7 类实际故障/清理通过结构核验；1 秒超时实际约 %.3f 秒，响应及时性未过。CPU/CUDA/Skill 各 80 条往返决策一致，三条已知错误仍保留。全部 38 原关闭条件保持；[本批实测](../validation/语义任务中断恢复实测_2026-10-25.md)。' % seconds + text[end:]
    text = row(text, 'V01', '| V01 | 当前已安装与注册 | local.10 / CLI 0.1.12，1 Skill/17 模块、r11 kit；[202 文件固定安装](../validation/evidence/semantic-recovery-20261025-r1/installation-r1/verification.json)，旧 local.9/r10 保留 |')
    text = text.replace('semantic-package-capabilities-cli-0.1.11.json', 'semantic-recovery-capabilities-cli-0.1.12.json')
    text = text.replace('V16 | CLI 0.1.11 当前交付审计', 'V16 | CLI 0.1.11 历史交付审计')
    text = text.replace('当前 CLI 0.1.11 / local.9 / r10 另完成语义工程包修复与真实往返，下表区分当前交付和保留的质量边界。',
        'CLI 0.1.11 / local.9 / r10 此前完成语义工程包修复与真实往返；当前 0.1.12 / local.10 / r11 新增语义任务恢复，下表区分当前交付和保留的质量边界。')
    text = text.replace('Current CLI 0.1.11 / local.9 / r10 preserves', 'Historical CLI 0.1.11 / local.9 / r10 preserves')
    last = numbered(text, 'V')['V16']; text = text.replace(last, last + '\n| V17 | 当前任务恢复/交付审计 | [7 类实际故障与完整分范围实测](../validation/语义任务中断恢复实测_2026-10-25.md)；[6 次实际只读入口/完整交付审计](../validation/evidence/semantic-recovery-20261025-r1/final-delivery-r2/verification.json)，不增加自然质量或总体完成率 |', 1)
    updates = {
        'G26': ('保留条件/校准检索和同机可迁移工程，CLI 0.1.12 接入受管语义任务；真实 CPU/CUDA/Skill 各 80 条迁移一致', '两条大象/吉他误接受、一条钟表误拒保留；熟悉静态图恢复回归不证明自然动作/身份/音频/推荐，大库与常驻未闭'),
        'G32': ('保留 GPU 配音/翻译和批内复用；新增 worker 阶段/耗时，区分导入、完整性校验、加载和推理', '仍仅 RTX 3060，逐命令加载；首次 inspect 导入约 72.56 秒、校验约 20.90 秒；1 秒超时实际约 %.3f 秒。大量效果 CPU，长片/4K/多设备/并发与常驻未闭' % seconds),
        'G33': ('CLI 0.1.12 四种语义操作加入租约/持久任务；索引和校准树身份/SHA 发布、引用全树保护、提交前回收/提交后保留；7 类真实故障/清理核验', '结构恢复子项已补；同步完整性校验延迟超时/取消，其他 worker、断电/磁盘耗尽/设备丢失/长并发仍开放；旧缓存不自动接管，不支持推理续算'),
        'G38': ('公开 alpha.3 / CLI 0.1.2 保留；当前本地 local.10 / CLI 0.1.12 / r11 kit 已核验安装与注册', '本地扩展尚无匹配公开新版 Release，旧标签/附件不覆盖；完整正式门禁未过')}
    for key, (have, gap) in updates.items():
        cells = numbered(text, 'G')[key].split('|'); cells[3], cells[4] = ' ' + have + ' ', ' ' + gap + ' '; text = row(text, key, '|'.join(cells))
    assert all(numbered(text, 'G')[key].split('|')[5] == value.split('|')[5] for key, value in original.items())
    text = row(text, 'D01', '| D01 | 当前可直接使用 | CLI 0.1.12 / local.10 / r11，固定安装 202 文件，1 Skill/17 模块；旧版本保留 |')
    text = row(text, 'D02', '| D02 | 本批契约与回归 | 源码/安装相关专项各 150/150、CLI 各 122/122，0 skip；22 树专项已包含，不相加；完整历史套件未重跑 |')
    text = row(text, 'D07', '| D07 | 仍需工作 | 自然语义/视听、及时超时/取消、其他 worker、常驻与大库、干净主机和公开交付；全部 38 原条件不变 |')
    text += '\n\nCLI 0.1.12 [语义任务恢复](SEMANTIC_JOB_RECOVERY.md)与[真实实测](../validation/语义任务中断恢复实测_2026-10-25.md)推进 G33 子项；1 秒超时延后及三条检索错误保留。所有 38 组仍有未关闭条件，不计算总体完成率。\n'
    write(path, text)
    path = 'docs/product/IMPLEMENTATION_PLAN_20261025.md'; text = read(path)
    text = re.sub(r'当前交付为 \*\*.*?以下带 r11/r12', '当前交付为 **CLI 0.1.12 / alpha.4-local.10 / r11 kit**；[语义任务恢复实测](../validation/语义任务中断恢复实测_2026-10-25.md)含 7 类实际故障/清理，响应超时仍延后；全部原关闭条件保持。以下带 r11/r12', text, count=1)
    states = {'W05': 'CLI 0.1.12 保留条件/经验校准及同机迁移，三条错误仍在；自然动作/身份/音频/推荐和内容生态开放', 'W08': '新增四种语义任务受管恢复/整树保护，7 类实际用例通过结构核验；及时超时、其他 worker、断电/磁盘/并发与自然自主任务仍开放', 'W09': '当前 CLI 0.1.12 / local.10 / r11 kit 已安装加载；三语 README 同步，公开仍 alpha.3，原标签/附件保留'}
    for key, state in states.items():
        text = re.sub(r'^(\| ' + key + r'[^\n]*\|)[^|\n]*\|$', lambda m: m[1] + ' ' + state + ' |', text, count=1, flags=re.M)
    write(path, text + '\n\n2026-10-25 CLI 0.1.12：语义登记/索引/校准/检索纳入受管恢复，[本批实测](../validation/语义任务中断恢复实测_2026-10-25.md)。超时同步检查延后为已知失败边界；完整 G32/G33 和全部原目标保持进行中。\n')
    path = 'docs/README.md'; text = read(path)
    start = text.index('当前 CLI 0.1.11：'); end = text.index('| 阅读目标 / Goal', start)
    text = text[:start] + '当前本机交付 **CLI 0.1.12 / alpha.4-local.10 / r11 kit**，固定安装包、1 Skill/17 模块。\n\n[语义任务恢复操作](product/SEMANTIC_JOB_RECOVERY.md) · [本批真实故障/已知超时限制](validation/语义任务中断恢复实测_2026-10-25.md) · [全部 G01–G38](product/GOAL_GAPS_20261025.md)。公开仍 alpha.3 / CLI 0.1.2，旧附件/历史收据/原关闭条件保留。\n\n' + text[end:]
    text = text.replace('当前 CLI 0.1.10 的全部 38 组差距', '当前 CLI 0.1.12 的全部 38 组差距')
    write(path, text)
    for path in ('docs/product/SEMANTIC_RETRIEVAL.md', 'docs/product/COMMUNITY_ACCEPTANCE.md'):
        text = read(path)
        if path.endswith('SEMANTIC_RETRIEVAL.md'):
            text = text.replace('This guide describes CLI 0.1.10 / `v0.1.0-alpha.4-local.8`.',
                'This guide describes CLI 0.1.12 / `v0.1.0-alpha.4-local.10`.')
            text = text.replace('**当前迁移限制：**', '**历史 CLI 0.1.10 迁移限制（旧失败保留）：**')
            marker = '## CLI 0.1.10 条件与校准流程'
            text = text.replace(marker, '## 当前工作流与历史迁移问题\n\nCLI 0.1.11 已修复新导出的语义工程包并真实验证同机迁移；旧损坏 ZIP 需从完好源重新导出。当前 CLI 0.1.12 新增受管任务恢复，[操作说明](SEMANTIC_JOB_RECOVERY.md)。模型/原生运行时仍外部固定，三条已知语义错误保留。\n\n' + marker, 1)
        else:
            text = text.replace('当前安装版已为 **CLI 0.1.10 / local.8**', '当前安装版已为 **CLI 0.1.12 / local.10**')
        write(path, text + '\n\n2026-10-25 当前 CLI 0.1.12：[语义任务恢复](SEMANTIC_JOB_RECOVERY.md)与[真实实测](../validation/语义任务中断恢复实测_2026-10-25.md)。7 类故障/清理结构核验通过，但同步完整性检查延迟超时/取消；仍逐命令加载，三条查询错误与全部原目标保留。\n')
    path = GUIDE; write(path, read(path).replace('CLI 0.1.12 开发候选把', 'CLI 0.1.12 本机安装版把') + '\n\n[本批实际核验与失败](../validation/语义任务中断恢复实测_2026-10-25.md) · [C21](CASES.md#c21-semantic-recovery)。\n')
    path = 'docs/specs/语义任务发布与中断恢复契约_20261025.md'
    write(path, read(path).replace('（开发候选 CLI 0.1.12）', '（CLI 0.1.12）') + '\n\n[本轮实际结果](../validation/语义任务中断恢复实测_2026-10-25.md)。及时超时未通过，完整条件不因结构恢复通过而关闭。\n')
    path = 'docs/product/CASES.md'
    write(path, read(path) + '''

<a id="c21-semantic-recovery"></a>

## C21：语义任务真实中断、恢复与失败边界 / Native semantic recovery

[使用流程](SEMANTIC_JOB_RECOVERY.md) · [输入/全部命令/结果](../validation/语义任务中断恢复实测_2026-10-25.md)。

| 编号 | 案例 | 实际结果与限制 |
|---|---|---|
| C21-01 | 11 本地资产、明确外部授权源、40 校准、80 查询 | 采用既有熟悉静态图协议，实际 CPU/CUDA/Skill，三条原查询错误保留 |
| C21-02 | 真实索引/校准发布后、提交前结束 CLI | 显式恢复后回收未引用目录，元数据与原输入不变 |
| C21-03 | 校准提交后结束 CLI | 已提交整树保留，清理缓存后使用原新 ID 真实查询通过 |
| C21-04 | model-loading 阶段强停和取消 | 原生句柄验证仅本任务 worker 退出；不推断 kernel 中取消 |
| C21-05 | 1 秒超时 | 返回 PROCESS_TIMEOUT，但同步完整性检查导致墙钟显著超限；作为明确未通过的及时性边界保留 |
| C21-06 | 显式诊断清理与工程两次往返 | 索引/校准/权利/素材保留，原路径移走后 CPU/CUDA/Skill 各 80 决策一致 |

本批是文件/进程/模型任务行为，未制作新的视觉效果或冒充屏幕录制。[C20](#c20-semantic-package)提供前一版同组查询的实际图片、MP4/GIF与可编辑卡片包，日期和版本分别保留。
''')
    # Complete assertions before changing any current document.
    for path, value in PENDING.items():
        (ROOT / path).write_text(value, encoding='utf8', newline='\n')
    print(json.dumps(dict(status='docs-synchronized',readme_rows=94,product_files=202,original_goal_conditions_preserved=38), ensure_ascii=False))


if __name__ == '__main__': main()
