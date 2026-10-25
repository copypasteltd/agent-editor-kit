"""Update actual runtime-upgrade delivery; preserve historical rows and goal gates."""
import argparse
from pathlib import Path
import json
import re
from sync_capability_manuals import links

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/semantic-upgrade-20261025-r1'
REPORT = 'docs/validation/语义运行时升级实测_2026-10-25.md'
GUIDE = 'docs/product/SEMANTIC_RUNTIME_UPGRADE.md'


def load(name):
    return json.loads((BASE/name).read_bytes())


def read(name):
    return (ROOT/name).read_text('utf-8-sig')


def write(name, text):
    (ROOT/name).write_text(text, encoding='utf8', newline='\n')


def rows(text, prefix):
    return {m[1]: m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$', text, re.M)}


def replace_row(text, key, value):
    text, count = re.subn(r'^\| '+key+r'\s*\|.*$', lambda _: value, text, flags=re.M)
    assert count == 1, key
    return text


def guides():
    installation = load('installation-r3/verification.json')
    assert installation['status'] == 'installed-and-byte-verified'
    name = 'docs/product/COMMUNITY_LOCAL_DELIVERY.md'
    text = read(name).replace('CLI 0.1.14 当前交付 / Current delivery', 'CLI 0.1.14 历史交付 / Historical delivery')
    text = text.replace('v0.1.0-alpha.4-local.12', 'v0.1.0-alpha.4-local.13').replace('/final-r2/installed', '/final-r3/installed')
    text = text.replace('candidate-r2/bundle.zip', 'candidate-r3/bundle.zip')
    text = text.replace('504531688a3e0f34e7f5775cc2af9c255fd532bb6422629eca60a53e137d2fcc', installation['archive_sha256'])
    text = text.replace('sha256:6e6192aefd59edb8e52472016103c4c27031fdb10b84446fc8de770131d63072', installation['manifest_sha256'])
    text = text.replace('unified-skill-r13.zip', 'unified-skill-r14.zip').replace('package-0.1.14.json', 'package-0.1.15.json')
    text = text.replace(' / CLI 0.1.14**', ' / CLI 0.1.15**')
    text = text.replace('本轮新增[可编辑广告', '此前新增[可编辑广告')
    text = text.replace('更换语义实现或其绝对位置后须明确重新登记并重建索引/档案，不能\n手改原 pin。',
        '语义实现内容改变须重新登记并重建。仅安装位置改变且 19 个实现与外部依赖字节相同时，可用\n`project upgrade-semantic` 显式派生新绑定，不重新推理；不能手改原 pin。')
    text += ('\n## CLI 0.1.15 当前交付 / Current delivery\n\n'
        f"{installation['archive_bytes']} bytes、206 个产品 Python 文件。[显式语义运行时升级](SEMANTIC_RUNTIME_UPGRADE.md)"
        '允许相同实现/依赖在安装路径变化后复用向量、预览和设备校准；旧记录/资产/权利保留，零新模型前向。'
        '原 0.1.14/local.12/r13 包和原始失败保留，模型路径或字节不兼容时仍拒绝。[真实实测](../validation/语义运行时升级实测_2026-10-25.md)。\n')
    write(name, text)
    name = 'docs/product/SEMANTIC_PROJECT_PACKAGE.md'; text = read(name)
    text = replace_row(text, 'M07', '| M07 | 跨机器或安装升级 | 项目包与模型依赖分别准备；仅安装位置改变且全部实现/依赖字节相同时可显式 `project upgrade-semantic`；内容改变则重新登记和重建，不改旧 pin |')
    start = text.index('同一安装版内移动工程，与从旧安装升级是两件事。')
    end = text.index('\n[迁移契约]', start)
    text = text[:start]+('同一安装版内移动工程，与从旧安装升级是两件事。CLI 0.1.15 新增'
        '[显式运行时升级](SEMANTIC_RUNTIME_UPGRADE.md)：仅全部 19 个语义实现模块及外部依赖字节相同'
        '时派生新适配器/索引/校准 ID，保留原向量、阈值、观察和旧记录，不重新推理；旧安装可以不可访问。'
        '改变实现或依赖内容仍须重新登记并重建，不能手改原 pin。使用返回的新 ID 真实查询。\n')+text[end:]
    write(name, text)


HEADLINES = (
    '新增 `project upgrade-semantic`：安装路径改变时，逐文件校验相同实现/依赖，派生新适配器、索引和校准，无需重复模型推理。旧记录、素材、阈值和原错误保留。',
    '新增 `project upgrade-semantic`：安裝路徑改變時，逐檔案校驗相同實作/依賴，衍生新適配器、索引及校準，無須重複模型推論。舊記錄、素材、閾值及原錯誤保留。',
    'New `project upgrade-semantic` derives new adapter/index/profile identities after an installation-path change, verifying byte-identical code/dependencies and reusing vectors without inference. Original data, fitted thresholds and known errors remain.',
)
UPGRADE_NOTES = (
    '旧安装路径直接复用的拒绝保留；CLI 0.1.15 现在提供[显式升级](docs/product/SEMANTIC_RUNTIME_UPGRADE.md)。全部实现/依赖字节相同时可复用向量，改变内容仍须重新建立索引和校准，不改旧 pin。',
    '舊安裝路徑直接復用的拒絕保留；CLI 0.1.15 現在提供[明確升級](docs/product/SEMANTIC_RUNTIME_UPGRADE.md)。全部實作/依賴位元組相同時可復用向量，改變內容仍須重新建立索引和校準，不改舊 pin。',
    'Direct use of an unavailable old installation still fails integrity checks. CLI 0.1.15 adds an [explicit upgrade](docs/product/SEMANTIC_RUNTIME_UPGRADE.md) for byte-identical implementations/dependencies; changed content requires rebuilding. Old pins stay intact.',
)
F53 = (
    '| F53 | 语义运行时升级 | 旧适配器/索引/校准 → 新安装路径下的新 ID，复制向量/预览/数据集且保留拟合和原观察。 | `project upgrade-semantic` | 全部 19 个实现与外部依赖须字节相同；零新模型前向，原记录不改；内容变化拒绝并要求重建。 |',
    '| F53 | 語義執行時升級 | 舊適配器/索引/校準 → 新安裝路徑的新 ID，複製向量/預覽/資料集並保留擬合及原觀察。 | `project upgrade-semantic` | 全部 19 個實作與外部依賴須位元組相同；零新模型前向，原記錄不改；內容變更拒絕並要求重建。 |',
    '| F53 | Semantic runtime relocation | Old adapter/index/profiles → new installation-bound identities, copying vectors/previews/datasets and retaining fitted observations. | `project upgrade-semantic` | All 19 implementation files and external dependencies must be byte-identical; zero new model forwards; original records retained; changed bytes require rebuilding. |',
)
CHECKS = (
    [('固定安装', 'CLI 0.1.15 / local.13；206 产品文件与发行 ZIP 安装版一致'),
     ('代码与安装回归', '源码契约 122/122、安装契约 122/122、安装 CLI 122/122，0 skip；分范围记录，不相加'),
     ('显式零推理升级', '案例独有旧安装移走后直接查询拒绝；显式迁移 1 索引/2 设备校准，19 实现 SHA 相同、0 新模型前向；原数据保留'),
     ('真实 CPU 与 CUDA 对照', '升级前后各 80 查询的决定/排序相同，分数误差 ≤1e-6；三条原语义错误保留，不计质量改进'),
     ('升级后工程包', '导出/导入保留全部资产字节/语义元数据；移走原工程后验证与真实注册 Skill 查询通过'),
     ('真实超时与取消', '原生 1 秒/5 秒预算、64MiB 早期/512MiB 读取中取消；读取中断丢弃部分摘要，元数据/资产保持'),
     ('单一 Skill 与独立工具包', '1 Skill/17 模块、66 Skill 文件、r14 kit；独立中文/空格目录配置/注册/升级 dry-run 等 8 调用'),
     ('交付与历史保持', 'R01–R109 原文及全部 38 原关闭条件保持；本地加载/三语文档更新，公开旧版不覆盖')],
    [('固定安裝', 'CLI 0.1.15 / local.13；206 產品檔案與發行 ZIP 安裝版一致'),
     ('程式與安裝迴歸', '原始碼契約 122/122、安裝契約 122/122、安裝 CLI 122/122，0 skip；分範圍記錄，不相加'),
     ('明確零推論升級', '案例獨有舊安裝移走後直接查詢拒絕；明確遷移 1 索引/2 裝置校準，19 實作 SHA 相同、0 新模型前向；原資料保留'),
     ('實際 CPU 與 CUDA 對照', '升級前後各 80 查詢的決策/排序相同，分數誤差 ≤1e-6；三條原語義錯誤保留，不計品質改善'),
     ('升級後專案包', '匯出/匯入保留全部資產位元組/語義中繼資料；移走原專案後驗證及實際註冊 Skill 查詢通過'),
     ('實際逾時與取消', '原生 1 秒/5 秒預算、64MiB 早期/512MiB 讀取中取消；讀取中斷丟棄部分摘要，中繼資料/資產保持'),
     ('單一 Skill 與獨立工具包', '1 Skill/17 模組、66 Skill 檔案、r14 kit；獨立中文/空格目錄設定/註冊/升級 dry-run 等 8 呼叫'),
     ('交付與歷史保持', 'R01–R109 原文及全部 38 原結案條件保持；本機載入/三語文件更新，公開舊版不覆寫')],
    [('Pinned installation', 'CLI 0.1.15 / local.13; 206 product files match the release ZIP installation'),
     ('Source/installed regression', 'Source contracts 122/122, installed contracts 122/122, installed CLI 122/122, zero skips; separate non-additive scopes'),
     ('Explicit zero-forward upgrade', 'With the owned old installation moved away, direct search rejects; explicit migration derives 1 index/2 device profiles, 19 identical implementation SHAs, zero new model forwards; originals retained'),
     ('Actual CPU/CUDA comparisons', 'Each device preserves all 80 pre/post decisions and ranking, score error ≤1e-6; three known semantic mistakes retained, no quality-improvement claim'),
     ('Upgraded project package', 'Export/import retains all asset bytes and semantic metadata; validation and registered-Skill search execute after moving the source project away'),
     ('Native timeout/cancellation', 'One/five-second budgets plus early/read cancellation at 64/512MiB; partial reads discard digests; metadata/assets unchanged'),
     ('Unified Skill and separate kit', '1 Skill/17 modules, 66 Skill files, r14 kit; eight configure/register/upgrade-dry-run and diagnostic calls from a separate Chinese/space path'),
     ('Delivery/history retention', 'R01–R109 verbatim and all 38 original goal gates retained; local Skill and three-language docs updated; public old assets not overwritten')],
)


def final():
    for phase in ('setup-r2', 'upgrade-r2', 'roundtrip-r2', 'faults-r3', 'kit-r1'):
        assert load(phase+'/verification.json')['status'] == 'passed', phase
    for phase in ('before-cpu', 'before-cuda', 'after-cpu', 'after-cuda', 'skill-cuda'):
        proof = load(phase+'-r2/verification.json')
        assert proof['status'] == 'passed-with-known-quality-errors' and proof['query_count'] == 80
    for run, count in (('development-r6',122), ('installed-contracts-r3',122), ('installed-cli-r3',122)):
        proof = load('tests/'+run+'/verification.json')
        assert proof['status'] == 'passed' and proof['result']['methods'] == count
    evidence = ['installation-r3/verification.json', 'tests/installed-contracts-r3/verification.json',
        'upgrade-r2/verification.json', 'after-cuda-r2/verification.json', 'roundtrip-r2/verification.json',
        'faults-r3/verification.json', 'kit-r1/verification.json', 'final-delivery-r1/verification.json']
    for i, name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        text = read(name); old = rows(text, 'R'); assert len(old) == 109
        text = text.replace('<!-- ad-storyboard-current -->','<!-- ad-storyboard-history -->').replace('<!-- /ad-storyboard-current -->','<!-- /ad-storyboard-history -->')
        text = text.replace('**CLI 0.1.14 / alpha.4-local.12 / r13 kit**',
            '**Historical / 历史 / 歷史：CLI 0.1.14 / alpha.4-local.12 / r13 kit**',1)
        block = ('<!-- semantic-upgrade-current -->\n\n**CLI 0.1.15 / alpha.4-local.13 / r14 kit** · 206 product Python files · 1 Skill / 17 modules. '+HEADLINES[i]+'\n\n'
            '[Workflow / 使用流程]('+GUIDE+') · [C24](docs/product/CASES.md#c24-semantic-upgrade) · [Evidence / 实测]('+REPORT+')\n\n'
            '```powershell\n# Use actual source IDs and unused destination IDs; inspect returned mappings.\n'
            '& $avk project upgrade-semantic --project $project --adapter-id siglip2 --new-adapter-id siglip2_current --id-prefix current --dry-run\n'
            '& $avk project upgrade-semantic --project $project --adapter-id siglip2 --new-adapter-id siglip2_current --id-prefix current --idempotency-key runtime-upgrade-1\n'
            '```\n\nCPU/CUDA: 80 decisions each preserved before/after; three known errors retained. Zero new model forwards in the upgrade itself.\n\n<!-- /semantic-upgrade-current -->\n\n')
        text = text.replace('<!-- ad-storyboard-history -->', block+'<!-- ad-storyboard-history -->',1)
        text = re.sub(r'^(?:升级注意：|升級注意：|Upgrade: ).*$', lambda _: UPGRADE_NOTES[i], text, flags=re.M)
        history = False; updated = []
        for line in text.splitlines():
            if line == '<!-- ad-storyboard-history -->': history = True
            if not history and not re.match(r'^\| R\d+\s*\|',line):
                line = line.replace('CLI 0.1.14', 'CLI 0.1.15').replace('v0.1.0-alpha.4-local.12/final-r2','v0.1.0-alpha.4-local.13/final-r3')
                line = line.replace('[r13 Skill kit]', '[r14 Skill kit]').replace('unified-skill-r13.zip','unified-skill-r14.zip')
            updated.append(line)
            if line == '<!-- /ad-storyboard-history -->': history = False
        text = '\n'.join(updated)+'\n'
        old_f52 = rows(text,'F')['F52']; text = text.replace(old_f52, old_f52+'\n'+F53[i],1)
        old_k08 = rows(text,'K')['K08']
        text = text.replace(old_k08,old_k08.replace('semantic index/calibrate/calibration-list/search`',
            'semantic index/calibrate/calibration-list/search; project upgrade-semantic`'),1)
        additions = '\n'.join('| R'+str(110+n)+' | '+title+' | '+detail+' | [2026-10-25 evidence](docs/validation/evidence/semantic-upgrade-20261025-r1/'+evidence[n]+') · [Scope]('+REPORT+') |'
            for n,(title,detail) in enumerate(CHECKS[i]))
        text = text.replace(old['R109'], old['R109']+'\n'+additions,1)
        text = re.sub(r'^\*\*Current delivery /.*$', '**Current delivery / 当前交付 / 目前交付（R110–R117，2026-10-25）：** CLI 0.1.15 / local.13 / r14; explicit byte-identical semantic runtime relocation, zero upgrade inference and preserved CPU/GPU/Skill results. Full goal remains active.', text, flags=re.M)
        assert all(rows(text,'R')[key] == value for key,value in old.items())
        assert len(rows(text,'R')) == 117 and len(rows(text,'F')) == 53
        write(name,text)
        suffix=('', '.zh-TW', '.en')[i]
        for manual in ('CAPABILITIES','SKILLS'):
            manual_name='docs/product/'+manual+suffix+'.md';manual_text=read(manual_name)
            manual_text=manual_text.replace('CLI 0.1.14 / alpha.4-local.12 / r13 kit', 'CLI 0.1.15 / alpha.4-local.13 / r14 kit')
            manual_text=manual_text.replace('ad-storyboard-capabilities-cli-0.1.14.json', 'semantic-upgrade-capabilities-cli-0.1.15.json')
            if manual=='SKILLS':
                matches=list(re.finditer(r'^\| K\d{2}\s*\|.*$',manual_text,re.M))
                assert len(matches)==17
                replacements='\n'.join(links(line,(ROOT/manual_name).parent) for line in rows(text,'K').values())
                manual_text=manual_text[:matches[0].start()]+replacements+manual_text[matches[-1].end():]
            write(manual_name,manual_text)
    name='docs/product/GOAL_GAPS_20261025.md'; text=read(name); old=rows(text,'G')
    prior = text.index('2026-10-25 当前本地交付为'); end=text.index('\n\n',prior)
    text = text[:prior]+('2026-10-25 当前本地交付为 **CLI 0.1.15 / alpha.4-local.13 / r14 kit**，206 个产品 Python 文件与安装版一致。'
        '[显式语义运行时升级](SEMANTIC_RUNTIME_UPGRADE.md)已解决相同实现迁移时的旧安装路径绑定障碍；零新模型前向，'
        '[CPU/CUDA/注册 Skill 实测](../validation/语义运行时升级实测_2026-10-25.md)保留原 80 条决定和三条错误。'
        '内容变化仍需重建，所有 38 原关闭条件保持。\n\n'+text[prior:end].replace('当前本地交付为','此前本地交付为')+text[end:])
    text=replace_row(text,'V01','| V01 | 当前已安装与注册 | local.13 / CLI 0.1.15，1 Skill/17 模块、r14 kit；[206 文件固定安装](../validation/evidence/semantic-upgrade-20261025-r1/installation-r3/verification.json)，旧包保留 |')
    text=replace_row(text,'V03','| V03 | 能力声明 | 75 项：20 implemented、47 implemented_with_limits、7 local_adapter_only、1 degraded；[当前全部字段](semantic-upgrade-capabilities-cli-0.1.15.json)，不换算完成率 |')
    text=replace_row(text,'D01','| D01 | 当前可直接使用 | CLI 0.1.15 / local.13 / r14，固定安装 206 文件，1 Skill/17 模块；旧版本保留 |')
    text=replace_row(text,'D02','| D02 | 本批契约与回归 | 源码契约 122/122、安装契约 122/122、安装 CLI 122/122，0 skip；分范围记录，不相加，历史全量未重跑 |')
    for key in ('G31','G34'):
        parts=rows(text,'G')[key].split('|')
        parts[3]+=' CLI 0.1.15 支持相同字节实现的显式运行时迁移，保留原数据/设备校准；'
        if key=='G34':
            parts[4]=' 旧安装路径的字节相同升级缺口已修复并实测；新目录不是新主机。Python/FFmpeg、驱动/CUDA、模型搬迁、干净主机升级和回滚仍须验证 '
        text=replace_row(text,key,'|'.join(parts))
    parts=rows(text,'G')['G38'].split('|'); parts[3]=' 公开 alpha.3 / CLI 0.1.2 保留；本地 local.13 / CLI 0.1.15 / r14 已安装注册核验 ';text=replace_row(text,'G38','|'.join(parts))
    assert len(rows(text,'G')) == 38 and all(rows(text,'G')[key].split('|')[5] == value.split('|')[5] for key,value in old.items())
    write(name,text)
    name='docs/product/IMPLEMENTATION_PLAN_20261025.md';text=read(name)
    start=text.index('当前交付为');end=text.index('\n\n',start)
    text=text[:start]+('当前交付为 **CLI 0.1.15 / alpha.4-local.13 / r14 kit**；[真实运行时迁移](../validation/语义运行时升级实测_2026-10-25.md)。'
        '实现/依赖字节相同的旧索引现在可显式迁移、零新推理；原元数据、CPU/CUDA 校准和错误保持。'
        '原广告编辑/配音链路继续提供，全部原关闭条件保持。下文旧版本为历史。')+text[end:]
    text+='\n2026-10-25 G31/G34 [CLI 0.1.15 实际交付](../validation/语义运行时升级实测_2026-10-25.md)：显式派生新适配器/索引/校准、原安装不可用后零推理迁移，CPU/CUDA/注册 Skill 的冻结 80 查询保持决定/排序/分数，保留三条错误；超时/取消/回滚/多索引契约与包往返分别留证。当前 local.13/r14/206 文件，1 Skill/17 模块。全部 G01–G38 原关闭条件保持，总目标继续进行。\n'
    write(name,text)
    name='docs/README.md';text=read(name).replace('CLI 0.1.14 / alpha.4-local.12 / r13 kit','CLI 0.1.15 / alpha.4-local.13 / r14 kit').replace('当前 CLI 0.1.14','当前 CLI 0.1.15')
    text+='\n- [CLI 0.1.15 显式语义运行时升级、保留向量与校准](product/SEMANTIC_RUNTIME_UPGRADE.md) · [真实 CPU/CUDA/Skill 与零前向迁移实测](validation/语义运行时升级实测_2026-10-25.md) · [C24](product/CASES.md#c24-semantic-upgrade)。\n';write(name,text)
    name='docs/product/CASES.md';text=read(name)
    text+='\n<a id="c24-semantic-upgrade"></a>\n\n## C24：旧安装不可用后的显式零推理迁移\n\n'
    text+='同一组冻结的 80 查询，在案例独有的旧安装移走前后分别由 CPU/CUDA 运行。新命令派生 1 索引/2 设备校准，零新模型前向，向量/预览/数据集和原资产/记录保留。升级后工程包导入、原工程移走，再由真实注册 Skill 查询。决定/排序保持，分数误差不超过 1e-6；三条旧错误保留。\n\n[使用流程](SEMANTIC_RUNTIME_UPGRADE.md) · [原命令/响应/耗时/失败与范围](../validation/语义运行时升级实测_2026-10-25.md)。该批修复数据与运行时绑定，没有新视觉效果，不制作替代性 GIF；既有查询真实预览见 C20，广告/滤镜演示保留。\n';write(name,text)
    print(json.dumps(dict(status='updated',readme_rows=117,functional_rows=53,original_goal_gates_preserved=38)))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('guides','final'),required=True)
    args=parser.parse_args();guides() if args.phase=='guides' else final()
