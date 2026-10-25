"""Publish only completed semantic-package evidence into current multilingual docs."""
from __future__ import annotations
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/semantic-package-20261025-r1'
REPORT='docs/validation/语义工程包迁移实测_2026-10-25.md'
GALLERY='docs/assets/semantic-package-20261025-r1/installed-r1'
DEMO='docs/assets/semantic-package-20261025-r1/demo-installed-r1'


def read(path): return (ROOT/path).read_text('utf-8-sig')
def write(path,text): (ROOT/path).write_text(text,encoding='utf8',newline='\n')
def load(path): return json.loads((BASE/path).read_bytes())
def numbered(text,prefix):
    return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2})\s*\|.*$',text,re.M)}
def row(text,key,line):
    result,n=re.subn(r'^\| '+key+r'\s*\|.*$',lambda _:line,text,flags=re.M)
    assert n==1,(key,n)
    return result


def main():
    installed=load('installation-r1/verification.json')
    assert installed['source_file_count']==200 and installed['source_and_installed_equal']
    for name in ('development-r3','development-cli-r2','installed-r1','installed-cli-r1'):
        value=load('tests/'+name+'/verification.json')
        assert value['exit_code']==0 and value['terminal_ok'] and value['frozen_equal'] and value['skipped']==0
        assert value['methods']==(122 if 'cli' in name else 65)
    phases=['setup-cuda','index-cuda','calibrate-cuda','calibrate-cpu','before-cuda','before-cpu',
        'roundtrip-cuda','after-cuda','after-cpu','skill-cuda','legacy-cuda']
    results={name:load('installed-r1/'+name+'/verification.json') for name in phases}
    assert all(v['status']=='completed-with-explicit-quality-limits' for v in results.values())
    for name in ('after-cuda','after-cpu','skill-cuda'):
        assert results[name]['all_80_decisions_and_ordered_hits_identical']
        assert results[name]['original_source_and_external_paths_unavailable']
    assert results['legacy-cuda']['legacy_0_1_10_package_rejected_before_publication']
    demo=load('demo-installed-r1/verification.json'); assert demo['status']=='passed-with-review-limits'
    phase_rows=[]
    for name,value in results.items():
        phase_rows.append(f'| {name} | {value["calls"]} | [{value["started_at_utc"]} — {value["finished_at_utc"]}](evidence/semantic-package-20261025-r1/installed-r1/{name}/verification.json) |')
    quality_rows=[]
    for name in ('before-cuda','after-cuda','before-cpu','after-cpu','skill-cuda'):
        value=results[name]; q=value['quality']
        errors=[r['id'] for r in q['queries'] if (not r['top1_correct'] if r['expected_asset_ids'] else not r['rejected'])]
        assert set(errors)=={'q14','hout00zh','hout08zh'},(name,errors)
        quality_rows.append(f'| {name} | {q["positive"]["correct"]}/36 | {q["negation"]["correct"]}/22 | {q["out_of_library"]["correct"]}/20 | {q["out_of_domain"]["correct"]}/2 | '+', '.join(errors)+' |')
    write(REPORT,'''# 语义工程包迁移实测（CLI 0.1.11，2026-10-25）

当前交付 `alpha.4-local.9 / CLI 0.1.11`，统一 `$agent-ffmpeg-local-editor` / 17 模块。
修复旧 C19 中索引树被摊平导致检索失败的子项。新导出/导入在同一主机完成真实 CPU/CUDA/Skill 往返，
原工程与外部源先移到不同路径，目标检索仍正常；模型/原生依赖继续使用外部原 pin。
完整 G26/G31/G32/G33/G34/G36/G38 未关闭，[全部 38 条原条件](../product/GOAL_GAPS_20261025.md)保持。

## 测试与固定安装

| 编号 | 范围 | 实际结果与证据 |
|---|---|---|
| T01 | 最终源码语义专项 | [65/65，0 skip](evidence/semantic-package-20261025-r1/tests/development-r3/verification.json)：48 既有 + 17 迁移契约，替身不作模型质量 |
| T02 | 最终源码 CLI | [122/122，0 skip](evidence/semantic-package-20261025-r1/tests/development-cli-r2/verification.json)，标准原生 Python |
| T03 | 固定安装版语义专项 | [另 65/65，0 skip](evidence/semantic-package-20261025-r1/tests/installed-r1/verification.json)，源码/安装文件不变 |
| T04 | 固定安装版 CLI | [另 122/122，0 skip](evidence/semantic-package-20261025-r1/tests/installed-cli-r1/verification.json)；3 个既有 CLI 子进程用字节相同源码路径，未算额外测试 |
| T05 | 新 ZIP/离线安装 | [302659130 bytes，200 产品文件与源码相同](evidence/semantic-package-20261025-r1/installation-r1/verification.json)，旧包和旧安装保留 |
| T06 | 单一注册与原有模型包 | [1 Skill/17 模块、4 包校验与运行配置](evidence/semantic-package-20261025-r1/activation-r1/verification.json)，仍是已有原生主机 |
| T07 | 独立工具包 | [r10 新目录安装/注册/入口核验](evidence/semantic-package-20261025-r1/kit-r1/verification.json)，不冒充干净主机或新的模型质量 |

源码专项最初两次失败保留在 development-r1/r2：测试夹具外部素材未标 `external_authorized`，及断言误用 `feature` 键。
源码 CLI 首轮 development-cli-r1 的 3 项失败也保留：嵌入式 Python 的 `._pth` 忽略子进程 `PYTHONPATH`，
出现 `No module named ai_ad_editor`/子进程未取得锁。改用标准原生 Python 后完整 122 项重跑通过；没有修改产品来绕开这些失败。
这些记录与最终通过范围分开，不叠加为功能通过数；未重跑历史 2930 项。

应用 ZIP SHA-256 `'''+installed['archive_sha256']+'''`；manifest `'''+installed['manifest_sha256']+'''`。
[安装流程](../product/COMMUNITY_LOCAL_DELIVERY.md) · [迁移操作](../product/SEMANTIC_PROJECT_PACKAGE.md) · [固定契约](../specs/语义工程包迁移契约_20261025.md)。

## 冻结输入与真实迁移

沿用先前冻结的 [协议](evidence/semantic-decision-20261025-r1/frozen/protocol.json)，SHA-256
`74b6c3c38d15284fd9a7814083378f82170cf516161898907bbf901fe997026b`。
11 资产/10 类熟悉静态图，40 条校准（20 正向/20 库外），60 另组措辞 + 20 原查询，共 80 条迁移回归。
标签不传 embedding worker；本批不在已知失败上重新调阈值，不增加独立自然质量结论。

1. 使用固定安装版创建新工程；一个素材在建索引前明确改为本批外部路径并标明外部授权，其余使用工程内副本。
2. 明确登记新实现的原生适配器、CUDA 建索引，分别运行 CPU/CUDA 校准和 80 条真实原工程查询。
3. 导出/导入，核对模型 pin、向量、采样、数据集、fit、观察和设备不变；必要的 URI 派生绑定与权利版本单独记录。
4. 再次导出/导入；第二轮语义资产字节相同。将本批原工程/外部源移到不同路径，使原引用位置不可用。
5. 在第一次导入工程分别真实跑 CPU/CUDA 80 条；通过注册 Skill 在第二次工程跑 CUDA 80 条。
6. 用新版实际导入旧 0.1.10 损坏包，确认拒绝且不发布目标目录；旧 ZIP 原字节保留。

两侧全部 80 条决策与命中排序一致，分数绝对误差不超过预定 `1e-6`。这是迁移完整性，错误决策也一致。

| 实际范围 | 正向 top-1 | 否定 top-1 | 另组库外拒绝 | 原库外拒绝 | 保留的错误 ID |
|---|---:|---:|---:|---:|---|
'''+ '\n'.join(quality_rows)+'''

`hout00zh` 大象、`hout08zh` 吉他仍被错误接受；`q14` 原中文钟表仍被误拒。不是新增召回或自然质量改进。
全部返回预览与三条错误见 [迁移后 80 条图库](../assets/semantic-package-20261025-r1/installed-r1/index.html)。

## 实际执行时间与响应

| 范围 | CLI 调用 | UTC 开始—结束及完整收据 |
|---|---:|---|
'''+ '\n'.join(phase_rows)+'''

冷启动包含全依赖哈希、Python 进程和模型加载。运行时复用仍限当前 batch；部分回归与其他任务同时进行，
这些墙钟不是独占 CPU/GPU 性能基准，也没有长片/4K/大库 P50/P95 或常驻服务结论。

## 可视案例与边界

[C20](../product/CASES.md#c20-semantic-package) 提供同一批迁移后的实际结果、6 张卡、12 秒/360 帧 MP4、5fps/60 帧 GIF，
卡片包的全部解码帧往返相同；另有可查询的真实索引/校准工程包。卡内文字为栅格，片段可编辑。
静态抽帧检查、全视频解码和工程帧摘要分别留档；没有人类连续播放、听审或语义接受。

旧 [C19 失败包与错误](../assets/semantic-decision-20261025-r1/demo-installed-r1/KNOWN_ISSUE.md)不改写。
旧损坏包没有自动修复工具；从完好原工程用新版重新导出。模型/运行时不在工程包内，
更换安装位置/字节仍需明确重新登记及重建。正常导入失败清理不代表强制结束/断电恢复已完成。
完整 G31 的私有草稿、复杂效果、排版、Bezier、跨机器证据/依赖，以及其余全部原产品目标继续执行。
''')
    for suffix in ('','.zh-TW','.en'):
        path='README'+suffix+'.md'; text=read(path); old=numbered(text,'R'); assert len(old)==81
        language='en' if suffix=='.en' else 'tw' if suffix else 'zh'
        title={'zh':'本机 CLI 0.1.11：可迁移的检索与校准工程','tw':'本機 CLI 0.1.11：可遷移的檢索與校準工程','en':'Local CLI 0.1.11: portable indexed and calibrated projects'}[language]
        intro={'zh':'新导出保留语义目录，必要时只改写路径派生绑定；导入先核验内部索引、素材、向量、预览、校准与权利，再发布目标工程。向量、原观察、阈值、设备和模型 pin 保留。',
            'tw':'新匯出保留語義目錄，必要時只改寫路徑衍生繫結；匯入先核驗內部索引、素材、向量、預覽、校準與權利，再發布目標專案。向量、原觀察、門檻、裝置與模型 pin 保留。',
            'en':'Packages preserve semantic directories and derive only required URI bindings. Import verifies source/index/vector/preview/profile/dataset and rights hashes before publishing. Vectors, observations, cutoffs, devices and model pins are retained.'}[language]
        limits={'zh':'同一主机的真实 CPU/GPU/Skill 各 80 条迁移后结果与原工程一致；保留两条误接受和一条钟表误拒。旧 0.1.10 损坏包拒绝导入，从完好原工程重新导出。完整 G01–G38 仍有未闭条件。',
            'tw':'同一主機的真實 CPU/GPU/Skill 各 80 條遷移後結果與原專案一致；保留兩條誤接受與一條時鐘誤拒。舊 0.1.10 損壞包拒絕匯入，從完好原專案重新匯出。完整 G01–G38 仍有未閉條件。',
            'en':'Same-host CPU, CUDA and registered-Skill runs each preserve all 80 original decisions after migration, including two false accepts and a clock false rejection. Re-export intact sources to replace damaged 0.1.10 packages. All G01–G38 original closure conditions remain.'}[language]
        review='**CLI 0.1.11 / alpha.4-local.9 / r10 kit**：200 product Python files; one Skill / 17 modules. '+limits
        text=re.sub(r'<!-- current-goal-review-r13 -->.*?<!-- /current-goal-review-r13 -->',
            '<!-- current-goal-review-r14 -->\n\n'+review+'\n\n[All 38 numbered gaps](docs/product/GOAL_GAPS_20261025.md) · [Actual migration evidence]('+REPORT+')\n\n<!-- /current-goal-review-r14 -->',text,flags=re.S)
        text=text.replace('agent-editor-kit-community-unified-skill-r9.zip','agent-editor-kit-community-unified-skill-r10.zip')
        text=text.replace('[r9 Skill kit]','[r10 Skill kit]').replace('CLI 0.1.10，GPU','CLI 0.1.11，GPU').replace('CLI 0.1.10, GPU','CLI 0.1.11, GPU')
        block=re.search(r'<!-- community-materials-gpu -->.*?<!-- /community-materials-gpu -->',text,re.S); assert block
        text=text[:block.start()]+block[0].replace('CLI 0.1.10','CLI 0.1.11')+text[block.end():]
        text=text.replace('local/agent-ffmpeg/v0.1.0-alpha.4-local.8/final-r1/installed/',
                          'local/agent-ffmpeg/v0.1.0-alpha.4-local.9/final-r1/installed/')
        text='\n'.join(line.replace('CLI 0.1.10','CLI 0.1.11') if ('alpha.4-local.9/final-r1/installed/' in line
            or ('GOAL_GAPS_20261025.md' in line and not line.startswith('|'))) else line for line in text.split('\n'))
        section='<!-- semantic-package-r1 -->\n\n## '+title+'\n\n'+intro+'\n\n'+limits+'\n\n'+\
            '[Workflow](docs/product/SEMANTIC_PROJECT_PACKAGE.md) · [Actual checks and limits]('+REPORT+') · [All 80 results]('+GALLERY+'/index.html) · [C20](docs/product/CASES.md#c20-semantic-package) · [r10 kit](docs/skills/agent-editor-kit-community-unified-skill-r10.zip)\n\n'+\
            '```powershell\n& $avk convert export --project $sourceProject --target-format package --output $projectZip\n& $avk convert import --input $projectZip --output $restoredProject\n& $avk semantic search --project $restoredProject --index-id images-v1 --query "a cat" --kind image --calibration-id accept-cuda --device cuda\n```\n\n'+\
            'Use actual paths/index/profile IDs and the pinned Skill launcher shown below. Native model/runtime dependencies remain separate; inspect conversion warnings and run the real query.\n\n'+\
            '![Actual post-migration decisions, including errors]('+DEMO+'/decisions.gif)\n\n<!-- /semantic-package-r1 -->\n\n'
        assert '<!-- semantic-decision-r1 -->' in text
        text=text.replace('<!-- semantic-decision-r1 -->',section+'<!-- semantic-decision-r1 -->',1)
        f=numbered(text,'F')['F50']; cells=f.split('|'); cells[-2]=' '+{
            'zh':'工程包按需派生路径绑定；同机 80 条迁移决策保留，仍有 3 条已知错误；运行时另备，G26/G31 开放',
            'tw':'專案包按需衍生路徑繫結；同機 80 條遷移決策保留，仍有 3 條已知錯誤；執行環境另備，G26/G31 開放',
            'en':'URI-only portable semantic package; all 80 decisions retained with 3 known errors; same-host runtime pins remain external; G26/G31 open'}[language]+' '
        text=row(text,'F50','|'.join(cells))
        additions=[
            ('R82','源码契约与 CLI / Source checks','65/65 semantic + 122/122 CLI, zero skips; initial fixture and embedded-runtime failures retained','tests/development-r3/verification.json'),
            ('R83','固定安装版 / Installed checks','200 source-identical product files; separate 65/65 semantic + 122/122 CLI; same native host','tests/installed-r1/verification.json'),
            ('R84','真实迁移 / Actual model roundtrip','CPU/CUDA/Skill each 80 decisions and ordered hits identical after source paths unavailable; 3 known errors retained','installed-r1/after-cuda/verification.json'),
            ('R85','旧损坏包 / Legacy invalid package','Actual 0.1.10 flattened package rejected before destination publication; old bytes retained; no automatic repair','installed-r1/legacy-cuda/verification.json'),
            ('R86','C20 可视案例 / Visual example','12s/360 frames MP4; 60-frame GIF; editable card package decoded frames identical; no human continuous review','demo-installed-r1/verification.json'),
            ('R87','单入口交付 / Single-entry delivery','CLI 0.1.11 / local.9 / r10; one Skill, 17 modules, 65 pinned files; all 38 original gap conditions remain','kit-r1/verification.json')]
        lines='\n'.join('| '+key+' | '+label+' | '+detail+' | [2026-10-25 evidence](docs/validation/evidence/semantic-package-20261025-r1/'+target+') · [Full scope]('+REPORT+') |' for key,label,detail,target in additions)
        last=old['R81']; text=text.replace(last,last+'\n'+lines,1)
        for key,value in old.items(): assert numbered(text,'R')[key]==value
        text=re.sub(r'\*\*[^\n]*R76–R81[^\n]*\*\*[^\n]*',
            '**Current delivery / 当前交付 / 目前交付（R82–R87，2026-10-25）：** CLI 0.1.11 / alpha.4-local.9 / r10; 200 product files, 1 Skill / 17 modules. Source and installed 65 semantic / 122 CLI scopes pass separately. Actual migration preserves 80 decisions including 3 mistakes. Public alpha.3 / CLI 0.1.2 assets and all 38 original conditions remain.',text)
        write(path,text)
    # Update current manual banners only; versioned evidence below stays historical.
    for stem in ('CAPABILITIES','SKILLS'):
        for suffix in ('','.zh-TW','.en'):
            path='docs/product/'+stem+suffix+'.md'; text=read(path)
            match=re.search(r'<!-- community-current -->.*?<!-- /community-current -->',text,re.S); assert match
            block=match[0].replace('0.1.10','0.1.11').replace('alpha.4-local.8','alpha.4-local.9').replace('semantic-decision-capabilities','semantic-package-capabilities')
            block=block.replace('[Current delivery]', '[Semantic package workflow](SEMANTIC_PROJECT_PACKAGE.md) · [Current delivery]')
            text=text[:match.start()]+block+text[match.end():]
            text=text.replace('[Machine response](semantic-decision-capabilities-cli-0.1.10.json)',
                              '[Machine response](semantic-package-capabilities-cli-0.1.11.json)')
            write(path,text)
    path='docs/product/COMMUNITY_LOCAL_DELIVERY.md'; text=read(path); split=text.index('## CLI 0.1.10')
    current=text[:split].replace('alpha.4-local.8','alpha.4-local.9').replace('0.1.10','0.1.11').replace('unified-skill-r9.zip','unified-skill-r10.zip')
    current=current.replace('da3ada9242ad7c5385eb91d542a7fa78ab335997df6c39c6aadf5dbdd6a4d243',installed['archive_sha256'])
    current=current.replace('sha256:fa6ddf51337a6b7b4f9b9a00adc76a387c291c89931e9973b3e2f1a2877361a1',installed['manifest_sha256'])
    current=current.replace('本轮增加[显式条件','本轮增加[语义工程包迁移](SEMANTIC_PROJECT_PACKAGE.md)，保留[显式条件')
    history=text[split:].replace('当前已实测的迁移缺口','CLI 0.1.10 当时已实测的迁移缺口')
    write(path,current+'## CLI 0.1.11 语义工程包迁移 / Semantic project-package migration\n\n'+
        '应用 ZIP 302,659,130 bytes，200 产品 Python 文件；[安装收据](../validation/evidence/semantic-package-20261025-r1/installation-r1/verification.json)。\n'+
        '[使用流程](SEMANTIC_PROJECT_PACKAGE.md) · [完整实际核验](../validation/语义工程包迁移实测_2026-10-25.md)。\n'+
        'CPU/CUDA/统一 Skill 各 80 条迁移后查询保持原决策；两条误接受和一条钟表误拒仍在。\n'+
        '外部模型、原生运行时和安装实现 pin 保留；不是干净主机交付或全部 G31 关闭。\n'+
        '旧 local.8 / CLI 0.1.10、r9 kit 与 C19 原错误保留；下节是当时历史实测。\n\n'+history)
    path='docs/product/GOAL_GAPS_20261025.md'; text=read(path); original=numbered(text,'G')
    start=text.index('2026-10-25 当前本地交付为'); end=text.index('\n\n| 编号',start)
    text=text[:start]+'2026-10-25 当前本地交付为 **CLI 0.1.11 / alpha.4-local.9 / r10 kit**，200 个产品 Python 文件与固定安装版相同。语义工程包目录与必要的 URI 派生绑定已修复，真实同机 CPU/CUDA/Skill 各 80 条迁移后决策与原工程一致，原源路径不可用。保留两条误接受、一条钟表误拒及旧 C19 失败；旧损坏包需从完好源重新导出。源码/安装专项和 CLI 分别通过，仍不关闭完整 G26/G31 或任何其他组。[本批实测](../validation/语义工程包迁移实测_2026-10-25.md)。以下 38 原关闭条件不变。'+text[end:]
    text=row(text,'V01','| V01 | 当前已安装与注册 | alpha.4-local.9 / CLI 0.1.11，1 Skill/17 模块、r10 kit；[200 文件固定安装](../validation/evidence/semantic-package-20261025-r1/installation-r1/verification.json)，旧 local.8/r9 保留 |')
    text=text.replace('semantic-decision-capabilities-cli-0.1.10.json','semantic-package-capabilities-cli-0.1.11.json')
    for key,label in {'V12':'CLI 0.1.10 历史 CPU/GPU 与 Skill','V13':'CLI 0.1.10 控制、诊断与迁移旧错误','V14':'历史 r9 独立工具包验证'}.items():
        cells=numbered(text,'V')[key].split('|');cells[2]=' '+label+' ';text=row(text,key,'|'.join(cells))
    last=numbered(text,'V')['V14']; text=text.replace(last,last+'\n| V15 | 当前语义工程包闭环 | [CPU/CUDA/Skill 真实 80 条往返](../validation/语义工程包迁移实测_2026-10-25.md)，源路径移走、第二次包字节保留；旧错误包导入拒绝。不是自然质量、自动修复旧 ZIP 或跨机器依赖验收 |',1)
    updates={
        'G26':('CLI 0.1.11 保留明确正/负条件、设备绑定经验校准及匹配/无匹配；新增同机可查询工程包', '两条大象/吉他误接受、一条钟表误拒仍在；本批只验证熟悉图像的迁移一致性，自然动作/身份/音频/推荐、大库与常驻仍未闭'),
        'G31':('CLI 0.1.11 工程包保留语义树，必要时仅派生 URI 绑定；CPU/CUDA/Skill 各 80 条真实迁移后决策一致，另二次往返与旧损坏包拒绝通过', '仍 degraded；私有草稿复杂效果/排版/Bezier/依赖不能完整映射；旧损坏 ZIP 无自动修复，跨机器证据/运行时仍缺。旧 C19 失败保留'),
        'G33':('保留既有受管任务/恢复；新增语义工程包在 staging 校验内部绑定后发布，正常导入失败清理', 'staging 的正常失败不是崩溃任务恢复；语义校准/检索仍非受管崩溃任务，断电/磁盘耗尽/设备丢失/长并发继续开放'),
        'G38':('公开 alpha.3 / CLI 0.1.2 保留；当前本地 alpha.4-local.9 / CLI 0.1.11 / r10 kit 已安装核验', '本地语义包修复、GPU/素材、采集/检索、四轨/恢复、词活动和字幕配音尚无匹配公开新版 Release；完整正式门禁未过')}
    for key,(supported,gap) in updates.items():
        cells=numbered(text,'G')[key].split('|'); cells[3]=' '+supported+' '; cells[4]=' '+gap+' '; text=row(text,key,'|'.join(cells))
    for key,value in original.items(): assert numbered(text,'G')[key].split('|')[5]==value.split('|')[5]
    text=text.replace('现 CLI 0.1.10 已完成新 ZIP 离线安装、CPU/GPU 校准/查询、真实 Skill 和独立 r9 工具包入口核验；并未重新解释历史记录。',
        '历史 CLI 0.1.10 / local.8 / r9 已完成当时的安装与模型核验；其错误原样保留。当前 CLI 0.1.11 / local.9 / r10 另完成语义工程包修复与真实往返，下表区分当前交付和保留的质量边界。')
    for key,detail in {'D01':'CLI 0.1.11 / local.9 / r10，固定安装 200 文件，1 Skill/17 模块；旧版本保留',
        'D02':'源码/安装专项各 65/65，源码/安装 CLI 各 122/122，0 skip；源码首轮嵌入式子进程失败保留',
        'D06':'C20 12 秒/360 帧与卡片包像素往返通过；语义项目 CPU/CUDA/Skill 各 80 条真实往返同原决策；旧 C19 失败保留'}.items():
        cells=numbered(text,'D')[key].split('|');cells[-2]=' '+detail+' ';text=row(text,key,'|'.join(cells))
    text+='\n\nCLI 0.1.11 [语义工程包迁移实测](../validation/语义工程包迁移实测_2026-10-25.md)补上同机新包闭环；全部 38 原关闭条件保留。旧损坏 ZIP、跨机器运行时、自然检索质量和全部格式等价仍未完成。\n'
    write(path,text)
    for path in ('docs/product/IMPLEMENTATION_PLAN_20261025.md','docs/product/SEMANTIC_RETRIEVAL.md','docs/product/COMMUNITY_ACCEPTANCE.md'):
        write(path,read(path)+'\n\n2026-10-25 CLI 0.1.11 / local.9：新增[语义工程包迁移](SEMANTIC_PROJECT_PACKAGE.md)与[真实核验](../validation/语义工程包迁移实测_2026-10-25.md)。同机 CPU/CUDA/Skill 各 80 决策在原路径不可用后保留；原三条错误及旧 C19 失败不改写。原生依赖继续外部固定，全部 G01–G38 原条件保持，完整目标继续进行。\n')
    path='docs/README.md';text=read(path);where=text.index('\n\n',text.index('\n')+1)
    text=text[:where]+'\n\n当前 CLI 0.1.11： [语义工程包操作](product/SEMANTIC_PROJECT_PACKAGE.md) · [本批实测与失败](validation/语义工程包迁移实测_2026-10-25.md) · [全部 G01–G38](product/GOAL_GAPS_20261025.md)。'+text[where:];write(path,text)
    path='docs/product/CASES.md';text=read(path)
    text=text.replace('## C19：条件/拒识完整预览与真实工程迁移失败 / Decisions and migration failure',
        '## C19：条件/拒识完整预览与真实工程迁移失败 / Decisions and migration failure\n\n历史 CLI 0.1.10 实测保留。CLI 0.1.11 的新包修复与真实往返见 [C20](#c20-semantic-package)；旧损坏包本身未被修改或自动修复。')
    text+='\n\n<a id="c20-semantic-package"></a>\n\n## C20：真实语义工程包迁移 / Portable semantic project\n\n'+\
        '[完整流程](SEMANTIC_PROJECT_PACKAGE.md) · [完整实际核验](../validation/语义工程包迁移实测_2026-10-25.md) · [迁移后 80 决策](../assets/semantic-package-20261025-r1/installed-r1/index.html)。\n\n'+\
        '![Post-migration actual decisions](../assets/semantic-package-20261025-r1/demo-installed-r1/decisions.gif)\n\n'+\
        '| 编号 | 内容 | 实际核验与限制 |\n|---|---|---|\n'+\
        '| C20-01 | 11 资产、40 校准、80 查询，含一个明确外部源 | CPU/CUDA/Skill 各 80 条迁移后决策与原工程一致；向量、阈值、数据、设备和模型 pin 保留，原源路径已移走 |\n'+\
        '| C20-02 | [完整 HTML/PNG/JSON](../assets/semantic-package-20261025-r1/installed-r1/index.html) | 实际返回预览，保留大象/吉他误接受和钟表误拒；熟悉静态图，非新自然质量 |\n'+\
        '| C20-03 | [12 秒 MP4](../assets/semantic-package-20261025-r1/demo-installed-r1/decisions.mp4) / GIF | 960×540 / 30fps / 360 帧；GIF 5fps / 60 帧 / 12000ms，诊断卡片，非执行录像 |\n'+\
        '| C20-04 | [可编辑卡片包](../assets/semantic-package-20261025-r1/demo-installed-r1/editable-cards.aevpkg.zip) | 导入重渲染全部帧摘要相同；6 段 image clips 可编辑，卡内排版为栅格 |\n'+\
        '| C20-05 | [索引/校准工程包](../assets/semantic-package-20261025-r1/demo-installed-r1/retrieval-project.aevpkg.zip) | 包含本批已迁移工程素材与数据；原生模型/运行时不在包中，使用时原 pin 必须仍匹配 |\n'+\
        '| C20-06 | [实际编码帧](../assets/semantic-package-20261025-r1/demo-installed-r1/actual-encoded-frames.png) | Agent 静态目检另行记录，无人类连续观看、听审或语义接受；[媒体收据](../validation/evidence/semantic-package-20261025-r1/demo-installed-r1/verification.json) |\n\n'+\
        '旧 C19 失败原样保留，新版拒绝该损坏 ZIP；从完好源重新导出。Same-host package integrity preserves mistakes too; full G26/G31 and all original goal conditions remain open.\n'
    write(path,text)
    print(json.dumps(dict(status='docs-synchronized',readme_rows=87,product_python_files=200,goal_conditions_preserved=38),ensure_ascii=False))


if __name__=='__main__': main()
