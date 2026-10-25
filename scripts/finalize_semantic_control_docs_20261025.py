"""Publish actual execution-control results without trimming history or goal scope."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-control-20261025-r1'
REPORT = 'docs/validation/完整性校验超时取消实测_2026-10-25.md'
PENDING = {}


def read(path):
    return PENDING[path] if path in PENDING else (ROOT/path).read_text('utf-8-sig')


def write(path, text):
    PENDING[path] = text


def load(path):
    return json.loads((BASE/path).read_bytes())


def numbered(text, prefix):
    return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}


def replace_row(text, key, value):
    result, count = re.subn(r'^\| '+key+r'\s*\|.*$',lambda _:value,text,flags=re.M)
    assert count == 1,(key,count)
    return result


def main():
    installation = load('installation-r1/verification.json')
    faults = load('faults-r1/verification.json')
    assert faults['status'] == 'passed' and len(faults['cases']) == 5
    assert load('activation-r1/activation-and-registration.json')['status'] == 'passed'
    assert load('kit-r1/verification.json')['status'] == 'passed'
    for name,count in (('development-r1',168),('installed-r1',168),('development-cli-r1',122),
                        ('bounded-development-r1',5),('bounded-installed-r1',5)):
        value = load('tests/'+name+'/verification.json')
        assert value['status'] == 'passed' and value['result']['methods'] == count and value['result']['skipped'] == 0
    for name in ('after-cuda','after-cpu','skill-cuda'):
        value = load('installed-r1/'+name+'/verification.json')
        assert value['all_80_decisions_and_ordered_hits_identical'] and value['maximum_score_error'] == 0
        errors = {r['id'] for r in value['quality']['queries'] if not (r['top1_correct'] if r['expected_asset_ids'] else r['rejected'])}
        assert errors == {'q14','hout00zh','hout08zh'}
    cases = {r['case']:r for r in faults['cases']}
    timeout_text = ' / '.join(f'{cases[n]["elapsed_seconds"]:.3f}' for n in ('search-timeout','adapter-inspect-timeout','verify-timeout'))
    cancel_text = ' / '.join(f'{cases[n]["cancel_to_exit_seconds"]:.3f}' for n in ('search-cancel','adapter-inspect-cancel'))
    links = '[实际耗时/原始诊断](docs/validation/完整性校验超时取消实测_2026-10-25.md)'
    headlines = (
        f'**CLI 0.1.13 / alpha.4-local.11 / r12 kit** · 203 product Python files · 1 Skill / 17 modules. 完整性读取现在响应超时/取消，部分摘要丢弃，原生读锁和恢复保护保留。1 秒超时三例完整 CLI 实测 {timeout_text} 秒；取消后退出 {cancel_text} 秒。模型仍逐命令加载，三条原查询错误及完整目标保持开放。',
        f'**CLI 0.1.13 / alpha.4-local.11 / r12 kit** · 203 product Python files · 1 Skill / 17 modules. 完整性讀取現在回應逾時/取消，部分摘要丟棄，原生讀鎖與恢復保護保留。1 秒逾時三例完整 CLI 實測 {timeout_text} 秒；取消後退出 {cancel_text} 秒。模型仍逐命令載入，三條原查詢錯誤與完整目標保持開放。',
        f'**CLI 0.1.13 / alpha.4-local.11 / r12 kit** · 203 product Python files · 1 Skill / 17 modules. Integrity reads now observe timeout/cancellation, discard partial digests and preserve native locks/recovery. Three 1-second requests took {timeout_text}s end to end; cancellation to exit took {cancel_text}s. Per-command loading, three known query errors and the full goal remain open.')
    additions = (
        [('R96','完整性读取控制','源码/安装版相关契约各 168/168；有界内存摘要各 5/5，源码 CLI 122/122；范围分别记录，不相加'),
         ('R97','真实超时修复',f'搜索/适配器检查/索引核验各请求 1 秒；完整 CLI 实测 {timeout_text} 秒，均返回 PROCESS_TIMEOUT'),
         ('R98','真实读取中取消',f'观察实际读取超过 64MiB 后发取消；搜索/检查在 {cancel_text} 秒内退出，保留 CANCELLED 和部分摘要诊断'),
         ('R99','CPU/GPU 与统一 Skill 回归','CPU/CUDA/真实 Skill 各 80 决策在迁移后与原工程一致、分数差 0；原三条检索错误保留'),
         ('R100','新版安装与本地加载','CLI 0.1.13 / local.11 / r12；203 产品文件一致，1 Skill/17 模块，4 原模型包重验；同机独立工具包验证'),
         ('R101','当前交付核对','保留全部原 38 组关闭条件及 R01–R95；本批无新自然质量/人工听审结论，公开仍 alpha.3')],
        [('R96','完整性讀取控制','原始碼/安裝版相關契約各 168/168；有界記憶體摘要各 5/5，原始碼 CLI 122/122；範圍分別記錄，不相加'),
         ('R97','實際逾時修復',f'搜尋/適配器檢查/索引核驗各請求 1 秒；完整 CLI 實測 {timeout_text} 秒，均返回 PROCESS_TIMEOUT'),
         ('R98','實際讀取中取消',f'觀察實際讀取超過 64MiB 後取消；搜尋/檢查在 {cancel_text} 秒內退出，保留 CANCELLED 與部分摘要診斷'),
         ('R99','CPU/GPU 與統一 Skill 回歸','CPU/CUDA/實際 Skill 各 80 決策在遷移後與原工程一致、分數差 0；原三條檢索錯誤保留'),
         ('R100','新版安裝與本地載入','CLI 0.1.13 / local.11 / r12；203 產品檔案一致，1 Skill/17 模組，4 原模型包重驗；同機獨立工具包驗證'),
         ('R101','目前交付核對','保留全部原 38 組結案條件與 R01–R95；本批無新自然品質/人工聽審結論，公開仍 alpha.3')],
        [('R96','Interruptible integrity reads','Source/installed contracts each 168/168; bounded-memory hashing each 5/5; source CLI 122/122; scopes separate, not additive'),
         ('R97','Real timeout correction',f'Three 1-second search/adapter-inspect/verify requests took {timeout_text}s end to end, all PROCESS_TIMEOUT'),
         ('R98','Cancellation during real reads',f'Cancel after observing over 64MiB read; search/inspection exited in {cancel_text}s after the marker, retaining CANCELLED and partial-digest diagnostics'),
         ('R99','CPU/GPU and unified Skill regression','CPU/CUDA/actual Skill each preserve all 80 migrated decisions and scores exactly; three known query errors retained'),
         ('R100','Installed and locally loaded delivery','CLI 0.1.13 / local.11 / r12; 203 equal product files, 1 Skill/17 modules, four unchanged model packs verified; separate kit on the same host'),
         ('R101','Delivery audit','All 38 original closure conditions and R01–R95 retained; no new natural-quality or human-listening acceptance; public release still alpha.3')])
    evidence = ['tests/installed-r1/verification.json','faults-r1/verification.json','faults-r1/verification.json',
        'installed-r1/skill-cuda/verification.json','kit-r1/verification.json','final-delivery-r1/verification.json']
    for i,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        text = read(name); historical = numbered(text,'R'); assert len(historical) == 95
        pattern = r'<!-- current-goal-review-r15 -->.*?<!-- /current-goal-review-r15 -->'
        text,count = re.subn(pattern,lambda _:'<!-- semantic-control-current -->\n\n'+headlines[i]+'\n\n'+links+'\n\n<!-- /semantic-control-current -->',text,flags=re.S)
        assert count == 1
        text = text.replace('[r11 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r11.zip)',
            '[r12 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r12.zip)',1)
        lines=[]
        for line in text.splitlines():
            if line.startswith(('**本机新增','**本機新增','**Local installed extension:')):
                line=line.replace('CLI 0.1.12','CLI 0.1.13')
            if line.startswith(('**公开发行版本：','**公開發行版本：','**Public release:')):
                line=line.replace('1 个统一 Skill / 17 项内部模块','17 个历史拆分 Skill').replace('1 個統一 Skill / 17 項內部模組','17 個歷史拆分 Skill').replace('1 unified Skill / 17 internal modules','17 historical separate Skills')
            if line.startswith('**Current delivery /'):
                line='**Current delivery / 当前交付 / 目前交付（R96–R101，2026-10-25）：** CLI 0.1.13 / local.11 / r12; interruptible integrity reads, full hashes/native locks preserved. Per-command model loading and all original goal conditions remain open.'
            if not re.match(r'^\| R\d{2} ',line):
                line=line.replace('v0.1.0-alpha.4-local.10/final-r1/installed','v0.1.0-alpha.4-local.11/final-r1/installed')
                if '当前完整目标差距表' in line or '目前完整目標差距表' in line or 'current full-goal gap' in line.lower():
                    line=line.replace('CLI 0.1.12','CLI 0.1.13')
            lines.append(line)
        text='\n'.join(lines)+'\n'
        tail='\n'.join(f'| {ident} | {title} | {detail} | [2026-10-25 evidence](docs/validation/evidence/semantic-control-20261025-r1/{ev}) · [Scope]({REPORT}) |'
            for (ident,title,detail),ev in zip(additions[i],evidence,strict=True))
        last=numbered(text,'R')['R95']; text=text.replace(last,last+'\n'+tail,1)
        assert all(numbered(text,'R')[key] == line for key,line in historical.items())
        write(name,text)
    finish_report(installation,faults,timeout_text,cancel_text)
    finish_goals(timeout_text,cancel_text)
    for name,text in PENDING.items():
        (ROOT/name).write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='updated',files=list(PENDING),readme_rows=101,original_goal_groups=38)))


def finish_report(installation,faults,timeout_text,cancel_text):
    rows='\n'.join(f'| {r["case"]} | {r["elapsed_seconds"]:.6f} | '+(f'{r["cancel_to_exit_seconds"]:.6f}' if r['cancel_to_exit_seconds'] is not None else '—')+
        f' | {r["error"]["code"]} | [原始响应](evidence/semantic-control-20261025-r1/faults-r1/{r["case"]}/verification.json) |' for r in faults['cases'])
    write(REPORT,f'''# 完整性校验超时与取消实测（CLI 0.1.13）

CLI 0.1.13 / alpha.4-local.11 / r12 kit，唯一 `$agent-ffmpeg-local-editor`、17 内部模块。修复发生在实际完整性读取过程；每份成功摘要仍覆盖全部字节，保留命令级原生读锁。中断时丢弃部分摘要、关闭当前句柄、保留原错误码。操作预算退出后才执行恢复，恢复仍完整核验输出身份/SHA。

原 CLI 0.1.12 的 1 秒超时约 81.739 秒，原[失败记录](evidence/semantic-recovery-20261025-r1/faults-r1/search-timeout/verification.json)保留。本批三个 1 秒请求完整 CLI 耗时为 {timeout_text} 秒，取消到退出为 {cancel_text} 秒。这是本机实测，预定门槛是超时完整过程≤8 秒、取消到退出≤3 秒；非独占性能 benchmark。

| 实际场景 | 完整 CLI 秒 | 取消至退出秒 | 错误码 | 证据 |
|---|---:|---:|---|---|
{rows}

取消基于本任务原生进程实际读取超过 64MiB 后创建标记，没有暂停/替换模型或计时钩子。错误诊断证明发生在 `integrity-read`，保留路径、已读字节和部分摘要未缓存状态。五例原素材、工程/权利元数据和安装代码均不变。[执行协议](../specs/可中断完整性校验契约_20261025.md)、[全部原始流](evidence/semantic-control-20261025-r1/faults-r1/verification.json)。

源码/安装版相关契约各 [168](evidence/semantic-control-20261025-r1/tests/development-r1/verification.json)/[168](evidence/semantic-control-20261025-r1/tests/installed-r1/verification.json)，源码 CLI [122](evidence/semantic-control-20261025-r1/tests/development-cli-r1/verification.json)，有界摘要各 [5](evidence/semantic-control-20261025-r1/tests/bounded-development-r1/verification.json)/[5](evidence/semantic-control-20261025-r1/tests/bounded-installed-r1/verification.json)，均 0 skip。18 项控制/读锁测试包含在 168 项内；不相加，也未重跑历史 2930 项。三项既有子进程测试仍使用同字节源码路径，安装版范围如实保留。

真实 CPU/CUDA 各 40 条校准，并使用原冻结的 80 条查询完成前后与两次包往返。CPU/CUDA/注册 Skill 各 80 决策、排序和分数完全保留，原源路径已移走；[完整执行](evidence/semantic-control-20261025-r1/campaign-r1/verification.json)、[CPU](evidence/semantic-control-20261025-r1/installed-r1/after-cpu/verification.json)、[CUDA](evidence/semantic-control-20261025-r1/installed-r1/after-cuda/verification.json)、[实际 Skill](evidence/semantic-control-20261025-r1/installed-r1/skill-cuda/verification.json)。三条错误 q14/hout00zh/hout08zh 保留，熟悉静态素材与措辞独立不证明自然语义质量；没有调整阈值迁就这些错误。

原生包 {installation['archive_bytes']} bytes，SHA `{installation['archive_sha256']}`，manifest `{installation['manifest_sha256']}`；[203 文件安装核对](evidence/semantic-control-20261025-r1/installation-r1/verification.json)。[4 既有模型包激活与注册](evidence/semantic-control-20261025-r1/activation-r1/activation-and-registration.json)、[r12 工具包独立目录](evidence/semantic-control-20261025-r1/kit-r1/verification.json)，均为同一物理主机。旧安装、原模型 pin 与旧公开 alpha.3 附件保留；适配器升级使用显式新登记，未改写旧 SHA。

`adapter-list`、`adapter-inspect`、`verify` 新增超时/取消参数；正常语义动作沿用原参数。先查看安装版命令帮助，再提供本地取消标记路径。检查退出码、`errors[].code/diagnostics` 和真实墙钟；不要把错误码正确当作及时性通过。

本批没有新视频渲染、录像、连续播放、人工听审或自然语义接受。模型仍逐命令加载；OS 阻塞文件读取不保证抢占，其他 worker/断电/磁盘/长并发、干净主机、完整 G32/G33 与[全部原目标](../product/GOAL_GAPS_20261025.md)继续开放。[最终交付审计](evidence/semantic-control-20261025-r1/final-delivery-r1/verification.json)。
''')


def finish_goals(timeout_text,cancel_text):
    name='docs/product/GOAL_GAPS_20261025.md'; text=read(name); old=numbered(text,'G')
    start=text.index('2026-10-25 当前本地交付为 **CLI')
    end=text.index('\n\n',start)
    text=text[:start]+f'2026-10-25 当前本地交付为 **CLI 0.1.13 / alpha.4-local.11 / r12 kit**，203 个产品 Python 文件与安装版相同。完整性校验现在响应超时/取消、丢弃部分摘要并保留原生读锁；三个 1 秒请求实测 {timeout_text} 秒，取消后退出 {cancel_text} 秒。[本批真实实测](../validation/完整性校验超时取消实测_2026-10-25.md)。全部 38 原关闭条件保持，完整目标继续进行。'+text[end:]
    text=text.replace('**本次用户请求复核 r13：**','**历史只读复核 r13（CLI 0.1.12）：**',1)
    for key in ('G32','G33','G38'):
        cells=old[key].split('|')
        if key=='G32':
            cells[3]=' GPU 配音/翻译、批内复用与阶段计时；CLI 0.1.13 校验读取响应超时/取消，部分摘要不缓存 '
            cells[4]=f' 1 秒请求本批完整 CLI 为 {timeout_text} 秒；该子项已修复，模型仍逐命令加载，大量效果 CPU，长片/4K/多设备/资源预算与常驻仍缺 '
        elif key=='G33':
            cells[3]=' 受管语义/四轨/配音恢复；新增读取预算、原错误码与中断诊断，预算退出后完整恢复校验 '
            cells[4]=f' 本批取消到退出 {cancel_text} 秒且原资产/元数据不变；其他 worker、断电/磁盘耗尽/设备丢失/长并发仍开放，旧缓存不接管，不支持推理续算 '
        else:
            cells[3]=' 公开 alpha.3 / CLI 0.1.2 保留；本地 local.11 / CLI 0.1.13 / r12 已安装、注册和核验 '
            cells[4]=' 本地扩展尚无匹配公开新版 Release；旧标签/附件不覆盖，完整正式门禁未过 '
        text=replace_row(text,key,'|'.join(cells))
    for key,line in numbered(text,'G').items():
        assert line.split('|')[5].strip()==old[key].split('|')[5].strip()
    text=replace_row(text,'V01','| V01 | 当前已安装与注册 | local.11 / CLI 0.1.13，1 Skill/17 模块、r12 kit；[203 文件固定安装](../validation/evidence/semantic-control-20261025-r1/installation-r1/verification.json)，旧安装/工具包保留 |')
    text=replace_row(text,'V03','| V03 | 能力声明 | 75 项：20 implemented、47 implemented_with_limits、7 local_adapter_only、1 degraded；[当前响应](semantic-control-capabilities-cli-0.1.13.json)，不换算总体完成率 |')
    text=text.replace('| V17 | 当前任务恢复/交付审计 |','| V17 | CLI 0.1.12 历史任务恢复/交付审计 |',1)
    text=text.replace('| V18 | 本次 r13 实际安装状态评估 |','| V18 | 历史 r13 / CLI 0.1.12 安装状态评估 |',1)
    v18=numbered(text,'V')['V18']
    text=text.replace(v18,v18+'\n| V19 | CLI 0.1.13 实际补齐 | [校验读取的超时/取消及 CPU/CUDA/Skill 回归](../validation/完整性校验超时取消实测_2026-10-25.md)；及时性子项已修复，完整 G32/G33 与全部原关闭条件保持 |',1)
    text=replace_row(text,'D01','| D01 | 当前可直接使用 | CLI 0.1.13 / local.11 / r12，固定安装 203 文件，1 Skill/17 模块；旧版本保留 |')
    text=replace_row(text,'D02','| D02 | 本批契约与回归 | 源码/安装相关契约各 168/168、有界摘要各 5/5，源码 CLI 122/122，均 0 skip；范围分别记录，不相加，历史全量未重跑 |')
    text=replace_row(text,'D07','| D07 | 仍需工作 | 自然语义/视听、OS 阻塞 I/O、其他 worker、常驻与大库、干净主机和公开交付；全部 38 原条件不变 |')
    text=text.replace('当前 0.1.12 / local.10 / r11 新增语义任务恢复','历史 0.1.12 / local.10 / r11 新增语义任务恢复；当前 0.1.13 / local.11 / r12 再补读取中的超时/取消',1)
    write(name,text)
    name='docs/product/IMPLEMENTATION_PLAN_20261025.md'; text=read(name)
    start=text.index('当前交付为 **CLI'); end=text.index('\n\n',start)
    text=text[:start]+'当前交付为 **CLI 0.1.13 / alpha.4-local.11 / r12 kit**；[真实读取超时/取消实测](../validation/完整性校验超时取消实测_2026-10-25.md)。校验中的及时性子项已修复；全部原关闭条件保持，完整目标继续进行。下文旧版本记录均为当时历史状态。'+text[end:]
    text='\n'.join(line.replace('CLI 0.1.12 / local.10 / r11 kit','CLI 0.1.13 / local.11 / r12 kit').replace('及时超时、其他 worker','其他 worker')
        if line.startswith('| W') else line for line in text.splitlines())+'\n'
    text+='\n2026-10-25 CLI 0.1.13：共享摘要/原生读锁加入操作预算，语义检查命令补超时/取消，保留原错误码与部分摘要诊断。实际五例及时性门槛通过，CPU/CUDA/统一 Skill 原 80 决策不变；固定包与 r12 kit 已本地加载。此批推进 W07/W08，逐命令加载、其他可靠性与全部 G01–G38 原条件继续开放。\n'
    write(name,text)
    name='docs/README.md';text=read(name).replace('CLI 0.1.12 / alpha.4-local.10 / r11 kit','CLI 0.1.13 / alpha.4-local.11 / r12 kit',1)
    text=text.replace('当前 CLI 0.1.12 的全部 38 组差距','当前 CLI 0.1.13 的全部 38 组差距',1)
    text+='\n[CLI 0.1.13 完整性读取超时/取消实测](validation/完整性校验超时取消实测_2026-10-25.md) · [实现契约](specs/可中断完整性校验契约_20261025.md)。\n'
    write(name,text)
    name='docs/product/CASES.md';text=read(name)
    text+='\n<a id="c22-semantic-control"></a>\n\n## C22：真实完整性读取中的超时与取消\n\nCLI 0.1.13 在实际模型/运行库字节读取中响应超时和取消，部分摘要丢弃，原素材与元数据保留。\n[五例原始命令/响应/耗时](../validation/完整性校验超时取消实测_2026-10-25.md)；CPU/CUDA/实际统一入口各 80 决策往返一致，原错误保留。\n本案例是原生进程与文件行为，无新视觉效果/屏幕录制，不使用历史 GIF 冒充当轮输出。\n'
    write(name,text)


if __name__ == '__main__':
    main()
