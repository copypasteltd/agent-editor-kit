"""Synchronize the actual 0.1.10 delivery, all gap conditions and three languages."""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-decision-20261025-r1'
REPORT = 'docs/validation/语义条件与校准拒识实测_2026-10-25.md'
GALLERY = 'docs/assets/semantic-decision-20261025-r1/installed-r1'
DEMO = 'docs/assets/semantic-decision-20261025-r1/demo-installed-r1'
INSTALL = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.8/final-r1/installed/'


def read(path):
    return (ROOT/path).read_text(encoding='utf-8-sig')


def write(path, text):
    (ROOT/path).write_text(text, encoding='utf-8', newline='\n')


def load(relative):
    return json.loads((BASE/relative).read_bytes())


def rows(text, prefix):
    return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2})\s*\|.*$', text, re.M)}


def replace_row(text, key, line):
    text, count = re.subn(r'^\| '+key+r'\s*\|.*$', lambda _: line, text, flags=re.M)
    assert count == 1, (key,count)
    return text


def main():
    installation = load('installation-r1/verification.json')
    assert installation['source_and_installed_equal'] and installation['source_file_count'] == 199
    assert load('controls-r1/verification.json')['status'] == 'passed'
    assert load('demo-finalization-r1/verification.json')['retrieval_profile_package_verified_same_host'] is False
    phase_rows = []
    phases = ['installed-r1/setup-cuda','installed-r1/index-cuda','installed-r1/calibrate-cuda',
              'installed-r1/calibrate-cpu','installed-r1/heldout-cuda','installed-r1/heldout-cpu',
              'installed-r1/regression-cuda','installed-r1/regression-cpu','skill-r1/heldout-cuda']
    for phase in phases:
        value = load(phase+'/verification.json')
        assert value['status'] == 'completed-with-quality-evidence' and value['source_bytes_unchanged']
        calls = json.loads((BASE/phase/'calls.json').read_bytes())
        forwards = 0
        for i in range(len(calls)):
            response = load(phase+f'/{i+1:02}.stdout.json')
            inference = response.get('data',{}).get('inference') or response.get('data',{}).get('profile',{}).get('inference',{})
            forwards += inference.get('response',{}).get('model_forward_calls',0)
        phase_rows.append(f'| {phase} | {len(calls)} | {forwards} | [{value["started_at_utc"]} — {value["finished_at_utc"]}](evidence/semantic-decision-20261025-r1/{phase}/verification.json) |')
    report = '''# 语义条件与经验校准拒识实测（CLI 0.1.10，2026-10-25）

当前交付 `v0.1.0-alpha.4-local.8` / CLI 0.1.10，单一 `$agent-ffmpeg-local-editor` / 17 内部模块。
增加明确正/负条件、同采样帧比较、设备绑定的经验校准和明确无匹配结果。
这批已进入固定安装包与真实注册入口；仍有两条库外误接受、一条原正向误拒和新发现的工程迁移错误。
完整 G26/G31/G32/G33/G36 未关闭，[全部 38 组条件](../product/GOAL_GAPS_20261025.md)保持。

## 安装与测试范围

| 编号 | 实际执行 | 结果与边界 |
|---|---|---|
| T01 | 最终源码检索契约 | [48/48、0 skip](evidence/semantic-decision-20261025-r1/tests/development-r3/verification.json)；25 既有 + 23 新契约，替身只验证错误/事务/数学，不作模型质量 |
| T02 | 最终固定安装版检索契约 | [另 48/48、0 skip](evidence/semantic-decision-20261025-r1/tests/installed-r1/verification.json)，199 产品文件前后不变 |
| T03 | 最终固定安装版 CLI 回归 | [122/122、0 skip](evidence/semantic-decision-20261025-r1/tests/installed-cli-r1/verification.json)；不是重跑全部历史 2930 项 |
| T04 | ZIP 解包离线安装 | [302655012 bytes / 199 文件与源码相同](evidence/semantic-decision-20261025-r1/installation-r1/verification.json)；新目录在同一原生主机，非干净主机证明 |
| T05 | 真实统一 Skill | [CPU/GPU 安装配置与单一入口登记](evidence/semantic-decision-20261025-r1/activation-r1/verification.json)；另实际跑 60 条 CUDA 查询，保留失败 |
| T06 | 实际控制/拒绝路径 | [9 次安装版 CLI](evidence/semantic-decision-20261025-r1/controls-r1/verification.json)，含 auto CUDA、实际 CPU 与 CUDA 档案不匹配、质量失败；原工程/许可/档案不变 |
| T07 | r9 工具包 | [独立目录安装/注册/入口/dry-run 验证](evidence/semantic-decision-20261025-r1/kit-r1/verification.json)，不冒充另一台机器或新模型质量 |

应用 ZIP SHA-256 `da3ada9242ad7c5385eb91d542a7fa78ab335997df6c39c6aadf5dbdd6a4d243`；
manifest `sha256:fa6ddf51337a6b7b4f9b9a00adc76a387c291c89931e9973b3e2f1a2877361a1`。
[完整安装与依赖](../product/COMMUNITY_LOCAL_DELIVERY.md) · [新契约](../specs/语义条件与校准拒识契约_20261025.md)。

## 冻结协议与实际质量

模型推理前冻结 [protocol.json](evidence/semantic-decision-20261025-r1/frozen/protocol.json)，
SHA-256 `74b6c3c38d15284fd9a7814083378f82170cf516161898907bbf901fe997026b`。
40 条校准（20 正向/20 库外），60 条另组措辞（20 正向/20 否定/20 库外），原 20 条回归另有 raw 对照。
只有 11 资产/10 类熟悉静态图；另组独立性只指查询措辞，非独立新素材、自然动作、音频或人工盲评。
标签仅由控制器评分，未给 embedding worker。未依据另组失败再调阈值。

| 编号 | 设备/入口与集合 | 正向正确接受/首位 | 否定正确首位 | 库外正确拒绝 | 仍有错误 |
|---|---|---|---|---|---|
| Q01 | 安装版 CUDA / 校准 40 | 20/20 | — | 19/20 | 1 条误接受；经验 FAR 5% |
| Q02 | 安装版 CPU / 校准 40 | 20/20 | — | 19/20 | 1 条误接受；经验 FAR 5% |
| Q03 | 安装版 CUDA / 另组 60 | 20/20 | 20/20 | 18/20 | 中文大象/木吉他误接受 |
| Q04 | 安装版 CPU / 另组 60 | 20/20 | 20/20 | 18/20 | 同两条错误 |
| Q05 | 真实注册 Skill CUDA / 另组 60 | 20/20 | 20/20 | 18/20 | 同两条错误；非独立新语料 |
| Q06 | 安装版 CUDA / 原 20 新模式 | 15/16 | 2/2 | 2/2 | 中文钟表被误拒 |
| Q07 | 安装版 CPU / 原 20 新模式 | 15/16 | 2/2 | 2/2 | 同一条误拒 |
| Q08 | 安装版 CUDA / 原 20 raw | 16/16 | 1/2 | 0/2 | 原中文否定/无素材失败继续可复现 |
| Q09 | 安装版 CPU / 原 20 raw | 16/16 | 1/2 | 0/2 | 同类原失败 |

CUDA 阈值 `0.0561935684022833`，CPU 阈值 `0.05586498798289672`，严格大于才接受。
默认校准要求正确正向覆盖至少 75%，避免“全部拒绝”通过；误接受比例仅该校准集经验值，非概率或普遍保证。
档案绑定索引、模型、实现、query protocol、素材类型、实际设备和设备号；auto 回退不能套用另一设备阈值。
同一采样帧的正/负相对分数不证明整段对象不存在，全部结果仍标注需复核。

| 错误 ID | 原文 | 实际结果 |
|---|---|---|
| hout00zh | 草原上站立的大象 | 库中没有大象，却接受摄影师等候选 |
| hout08zh | 靠在墙边的木吉他 | 库中没有吉他，却接受砖墙 |
| q14 | 带数字和指针的钟表 | 库中有钟表，但被阈值拒绝 |

[全部 80 条实际结果与失败](../assets/semantic-decision-20261025-r1/installed-r1/index.html) ·
[机器可读完整决策](../assets/semantic-decision-20261025-r1/installed-r1/decisions.json)。
正向/否定成功率按首位计；返回的其余候选仍可能错误，未把前 3 项当全部相关。

## 实际调用与成本

| 范围 | CLI 调用 | 本批响应报告的模型前向 | UTC 开始—结束及原收据 |
|---|---|---|---|
''' + '\n'.join(phase_rows) + '''

上表 index/校准/查询相互独立计数，不与源码开发记录或历史重复相加。
运行时为已有原生 Torch/Transformers/SigLIP2，RTX 3060 CUDA BF16 或 CPU float32；控制器使用安装版 NumPy/Pillow。
响应分别保留进程/完整性核验、模型加载和推理耗时。部分任务并发执行，不能当独占性能比较；
GPU 前向较快不消除冷启动、约 2.78GB 依赖完整性读取和跨命令重复加载成本。没有常驻模型服务或大库性能验收。

9 次控制调用中，dry-run/歧义语法/类型/raw 与档案冲突/预取消没有模型前向；
auto、实际 CPU 设备不匹配和故意错误标签校准另有真实前向，见原 calls.json/worker 收据。
故意错误标签仅是质量门禁故障注入，不修改冻结质量标注或计作语义测试集。
首次源码契约失败及第一次来源 URL 拒绝分别保留在 tests/development-r1、development-r1/setup-cuda。
先前 r12 只读盘点中的“未安装候选”是历史状态，现已由本批独立安装/模型/Skill 收据补齐。

## C19：真实结果、可编辑卡片与迁移失败

[12 秒无声 MP4](../assets/semantic-decision-20261025-r1/demo-installed-r1/decisions.mp4) ·
[GIF](../assets/semantic-decision-20261025-r1/demo-installed-r1/decisions.gif) ·
[六张实际编码帧](../assets/semantic-decision-20261025-r1/demo-installed-r1/actual-encoded-frames.png) ·
[六段可编辑卡片工程](../assets/semantic-decision-20261025-r1/demo-installed-r1/editable-cards.aevpkg.zip)。

960×540 / 30fps / 360 帧，六张卡各 2 秒；GIF 5fps / 60 帧 / 12000ms。
六段可编辑 image clip，卡内排版是栅格图；不冒充可编辑文字图层、自然广告或实时执行录像。
原工程与卡片包导入重渲染全部 360 帧 decoded framemd5 相同，两次真实 render。
19 次 CLI 前 18 次成功；第 19 次对另外导入的检索工程执行 dry-run **实际失败**：
`SEMANTIC_INDEX_INVALID` / `Manifest outside project semantic asset tree`。
该检索包虽 export/import/validate 成功，不能据此宣称索引/档案可搬迁；
[原错误](evidence/semantic-decision-20261025-r1/demo-installed-r1/19.stdout.json)、
[原执行失败](evidence/semantic-decision-20261025-r1/demo-installed-r1/failure.json)、
[保留已完成媒体的核验](evidence/semantic-decision-20261025-r1/demo-finalization-r1/verification.json)、
[失败复现包与说明](../assets/semantic-decision-20261025-r1/demo-installed-r1/KNOWN_ISSUE.md)均保留。
未手改 pin 或把这次失败改成预期通过，也未执行新的重建替代流程。

四张全量诊断页和六张编码画面/合成页只做 Agent 静态检查：文字在画布内，红色错误卡与无候选卡保留。
没有人类连续播放、听审、语义接受；没有配音音轨。素材为既有 CC0/NASA，字体 OFL，来源逐项保留。
所有执行原生 Windows，无 Docker/WSL/虚拟环境，无浏览器 UI 标签。

## 未关闭条件

有界否定语法仍会保守拒绝含“不”的部分肯定词；复杂语法不能靠静默改写通过。
自然动作、跨镜头身份、音频/推荐、大库与常驻复用、跨机器依赖、完整崩溃恢复和语义工程迁移继续开放。
本批改善原否定/拒识行为，未达到可靠通用检索或完整剪映功能效果水准。

English: CLI 0.1.10 ships explicit clauses and index/device-bound empirical acceptance profiles.
Real installed CPU/CUDA and the registered Skill retain two held-out false accepts and one original false rejection.
The ordinary card package preserves decoded frames, but the new retrieval package fails search after import.
All original 38 gap-group closure conditions remain. No universal rejection, human acceptance or full CapCut parity claim.
'''
    write(REPORT, report)
    texts = {
      '': dict(
        status='**目标状态（2026-10-25）：开源 Agent CLI 已可用，完整剪映功能与质量尚未达成。** 当前固定安装 CLI 0.1.10 / local.8 / r9 kit，1 Skill/17 内部模块。新增条件检索和设备绑定经验校准，实际 CPU/GPU/Skill 验证后仍有两条库外误选、一条钟表误拒；新检索工程导入后检索失败。38 组原关闭条件全部保留。',
        title='本机 CLI 0.1.10：明确条件、校准选择与完整失败预览',
        intro='中文“一只猫，不是一杯咖啡”和显式 `include`/`exclude` 在同一采样帧比较；可用索引/设备绑定的经验校准返回匹配或无匹配。先明确重新登记模型、重建索引，再准备 32–128 条（至少 16 正向、16 库外）人工核对的校准 JSON。查询标签不传模型。',
        quality='安装版 CPU/GPU 与真实 Skill 的另组 60 条均为正向 20/20、否定 20/20、库外拒绝 18/20；原 20 条新模式正向 15/16、否定 2/2、库外拒绝 2/2。原 raw 否定 1/2、库外拒绝 0/2 仍可复现。阈值是本索引经验值；全部结果需复核，复杂否定/自然动作/身份/音频/大库仍未完成。',
        migration='C19 六张卡片各 2 秒，真实 12 秒/360 帧 MP4 和 60 帧 GIF，包含全部三条查询错误；卡片工程往返像素相同。另一个新索引/校准工程在导入后检索报 `SEMANTIC_INDEX_INVALID`，该迁移失败保留，不宣称可搬迁或已关闭 G31。',
        f='| F50 | 离线图文语义检索与条件选择 | 本地索引、中英/参考图、同帧正负条件、经验校准档案、实际预览/源时间及可编辑引用。 | `semantic adapter-register/index/calibrate/calibration-list/search/verify` | CPU/GPU/Skill 已验，仍有两条误选、一条误拒及新工程迁移错误；非通用拒识/动作/身份/音频推荐。 |',
        s='| S18 | 图文语义与经验校准 | 明确登记的原生 SigLIP2 worker | 已有 Torch/Transformers/权重；档案绑定索引/实现/类型/实际设备 | `semantic adapter-register/index/calibrate/calibration-list/search/verify` | 分数非概率；冷启动/大库与校准工程迁移仍有限制 |',
        footer='**当前交付与复核（R76–R81，2026-10-25）：** CLI 0.1.10 / alpha.4-local.8 / r9，1 Skill/17 模块；199 个产品文件与安装版一致。48 项源码专项、另 48 项安装专项与 122 项安装 CLI 回归分别通过；真实模型、错误控制、案例和迁移失败分开记录。全部 G01–G38 条件保留；公开 alpha.3 / CLI 0.1.2 原包不改。'),
      '.zh-TW': dict(
        status='**目標狀態（2026-10-25）：開源 Agent CLI 已可用，完整剪映功能與品質尚未達成。** 目前固定安裝 CLI 0.1.10 / local.8 / r9 kit，1 Skill/17 內部模組。新增條件檢索及裝置綁定經驗校準；實際 CPU/GPU/Skill 驗證後仍有兩條庫外誤選、一條時鐘誤拒，以及新檢索工程匯入後檢索失敗。38 組原關閉條件全部保留。',
        title='本機 CLI 0.1.10：明確條件、校準選擇與完整失敗預覽',
        intro='中文「一只猫，不是一杯咖啡」和明確 `include`/`exclude` 在同一取樣影格比較；可用索引/裝置綁定的經驗校準回傳匹配或無匹配。先明確重新登記模型、重建索引，再準備 32–128 條（至少 16 正向、16 庫外）人工核對的校準 JSON。查詢標註不傳模型。',
        quality='安裝版 CPU/GPU 與實際 Skill 的另組 60 條均為正向 20/20、否定 20/20、庫外拒絕 18/20；原 20 條新模式正向 15/16、否定 2/2、庫外拒絕 2/2。原 raw 否定 1/2、庫外拒絕 0/2 仍可重現。閾值僅為本索引經驗值；全部結果需複核，複雜否定/自然動作/身分/音訊/大庫仍未完成。',
        migration='C19 六張卡片各 2 秒，實際 12 秒/360 影格 MP4 和 60 影格 GIF，保留全部三條查詢錯誤；卡片工程往返像素相同。另一個新索引/校準工程在匯入後檢索報 `SEMANTIC_INDEX_INVALID`，該遷移失敗保留，不宣稱可搬遷或已關閉 G31。',
        f='| F50 | 離線圖文語義檢索與條件選擇 | 本地索引、中英/參考圖、同影格正負條件、經驗校準檔案、實際預覽/來源時間及可編輯引用。 | `semantic adapter-register/index/calibrate/calibration-list/search/verify` | CPU/GPU/Skill 已驗，仍有兩條誤選、一條誤拒及新工程遷移錯誤；非通用拒識/動作/身分/音訊推薦。 |',
        s='| S18 | 圖文語義與經驗校準 | 明確登記的原生 SigLIP2 worker | 既有 Torch/Transformers/權重；檔案綁定索引/實作/類型/實際裝置 | `semantic adapter-register/index/calibrate/calibration-list/search/verify` | 分數非機率；冷啟動/大庫與校準工程遷移仍有限制 |',
        footer='**目前交付與複核（R76–R81，2026-10-25）：** CLI 0.1.10 / alpha.4-local.8 / r9，1 Skill/17 模組；199 個產品檔案與安裝版一致。48 項原始碼專項、另 48 項安裝專項與 122 項安裝 CLI 回歸分別通過；實際模型、錯誤控制、案例和遷移失敗分開記錄。全部 G01–G38 條件保留；公開 alpha.3 / CLI 0.1.2 原包不改。'),
      '.en': dict(
        status='**Goal status (2026-10-25): a usable open-source Agent CLI; full CapCut functionality and quality remain unaccepted.** The pinned local delivery is CLI 0.1.10 / local.8 / r9 kit, one Skill / 17 modules. Explicit clauses and device-bound empirical calibration now have installed CPU/CUDA and registered-Skill evidence, retaining two false accepts, one false rejection and a new retrieval-package migration failure. All 38 original closure conditions remain.',
        title='Local CLI 0.1.10: explicit clauses, calibrated selection and all observed failures',
        intro='Compare explicit `include`/`exclude` clauses on the same sampled frame, preserving the original query. An index/device-bound empirical profile can return a match or no match. Explicitly re-register the model and rebuild the index, then supply 32–128 reviewed calibration queries with at least 16 positives and 16 absent examples. Labels stay in the controller.',
        quality='Installed CPU/CUDA and the registered Skill each return 20/20 positive, 20/20 negation and 18/20 absent-query rejection on the same 60-query wording set. The original 20-query regression yields 15/16 positive, 2/2 negation and 2/2 rejection; raw still yields 1/2 negation and 0/2 rejection. Thresholds are empirical for this index, not probabilities or universal guarantees. All results require review; complex negation, natural actions, identity, audio and large libraries remain open.',
        migration='C19 shows six actual two-second cards, including all three query errors: a 12-second/360-frame MP4 and 60-frame GIF. Card-package rerendered pixels match. A separate new indexed/calibrated project fails search after import with `SEMANTIC_INDEX_INVALID`; that actual migration failure is preserved and G31 remains open.',
        f='| F50 | Offline visual semantic retrieval and conditions | Local index, Chinese/English/reference images, same-frame positive/negative clauses, empirical profiles, actual previews/source times and editable references. | `semantic adapter-register/index/calibrate/calibration-list/search/verify` | Installed CPU/CUDA/Skill checked; two false accepts, one false rejection and a new migration error remain; no universal rejection/action/identity/audio recommendation claim. |',
        s='| S18 | Visual semantics and empirical calibration | Explicit native SigLIP2 worker | Existing Torch/Transformers/weights; profile binds index/implementation/kind/actual device | `semantic adapter-register/index/calibrate/calibration-list/search/verify` | Scores are not probabilities; cold start, scale and calibrated-project migration remain limited |',
        footer='**Current delivery and review (R76–R81, 2026-10-25):** CLI 0.1.10 / alpha.4-local.8 / r9; one Skill / 17 modules, 199 product files equal the installation. Source 48, separate installed 48 and installed CLI 122 checks pass in their own scopes. Actual models, controls, media and the migration failure are recorded separately. All G01–G38 conditions remain. Public alpha.3 retains CLI 0.1.2.'),
    }
    checks = [
      ('R76','条件与校准契约 / Clause and calibration contracts','Source 48/48, zero skips; bounded grammar, empirical cutoff, rollback/device/hash guards; model substitutes are contracts only','tests/development-r3/verification.json'),
      ('R77','固定安装回归 / Installed regressions','Separate installed 48/48 + CLI 122/122, zero skips; not all historical tests','tests/installed-r1/verification.json'),
      ('R78','实际 CPU/CUDA 模型 / Actual CPU/CUDA','Separate device profiles, 40 calibration each; held-out 20/20 positive, 20/20 negation, 18/20 rejection; original positive 15/16; errors retained','installed-r1/heldout-cuda/verification.json'),
      ('R79','实际统一入口与拒绝 / Registered Skill and refusals','Actual Skill 60-query batch retains errors; 9 installed controls preserve metadata/rights/profiles; no universal semantics acceptance','controls-r1/verification.json'),
      ('R80','C19 实际视频与迁移失败 / Media and migration failure','80 result cards; six editable clips, two renders, 360 decoded frames equal; retrieval package search fails after import; failure retained','demo-finalization-r1/verification.json'),
      ('R81','当前离线安装与 r9 / Current installation and r9','199 product files equal installed CLI 0.1.10; one Skill / 17 modules / 64 Skill files; isolated r9 activation, not clean-host acceptance','kit-r1/verification.json'),
    ]
    for suffix, words in texts.items():
        name = 'README'+suffix+'.md'
        text = read(name)
        old_rows = rows(text,'R')
        assert all(f'R{i:02}' in old_rows for i in range(1,76))
        current = '<!-- current-goal-review-r13 -->\n\n'+words['status']+'\n\n[完整编号评估 / All gaps](docs/product/GOAL_GAPS_20261025.md) · [真实结果与限制 / Actual results]('+REPORT+') · [80-query gallery]('+GALLERY+'/index.html)\n\n<!-- /current-goal-review-r13 -->'
        text, n = re.subn(r'<!-- current-goal-review-r(?:12|13) -->.*?<!-- /current-goal-review-r(?:12|13) -->', lambda _:current,text,flags=re.S)
        assert n == 1
        protected = rows(text,'R')
        lines = []
        for line in text.splitlines():
            if re.match(r'^\| R\d{2}\s*\|',line):
                lines.append(line); continue
            line=line.replace('r8 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r8.zip)', 'r9 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r9.zip)')
            line=line.replace('v0.1.0-alpha.4-local.7/final-r2/installed/', 'v0.1.0-alpha.4-local.8/final-r1/installed/')
            if 'final-r1/installed/' in line:
                line=line.replace('CLI 0.1.9','CLI 0.1.10')
            if line.startswith(('**本机新增已安装扩展','**本機新增已安裝擴充','**New locally installed extension','**Local installed extension')):
                line=line.replace('CLI 0.1.9','CLI 0.1.10')
            if 'GOAL_GAPS_20261025.md)' in line and ('CLI 0.1.9' in line) and not line.startswith('|'):
                line=line.replace('CLI 0.1.9','CLI 0.1.10')
            if line.startswith('**当前交付与复核（R67') or line.startswith('**目前交付與複核（R67') or line.startswith('**Current delivery and review (R67'):
                line=words['footer']
            lines.append(line)
        text='\n'.join(lines)+'\n'
        text=replace_row(text,'F50',words['f'])
        text=replace_row(text,'S18',words['s'])
        for line in text.splitlines():
            if line.startswith('| V01 / F50 |'):
                text=text.replace(line,'| V01 / F50 | '+('Explicit clauses, empirical profiles and actual previews / 条件检索与经验校准' if suffix=='.en' else '条件检索、设备绑定经验校准、实际预览与可编辑时间点')+' | Two false accepts, one false rejection; imported retrieval package fails; G26/G31 remain open |')
        text=text.replace('semantic index/search`','semantic index/calibrate/calibration-list/search`')
        section='\n\n<!-- semantic-decision-r1 -->\n\n## '+words['title']+'\n\n'+words['intro']+'''\n\n```powershell
# Existing project/index, explicit native adapter and reviewed calibration JSON required.
& $avk semantic calibrate --project $project --index-id images-v1 --calibration-id accept-cuda --kind image --input $calibrationJson --device cuda
& $avk semantic search --project $project --index-id images-v1 --query '一只猫，不是一杯咖啡' --kind image --calibration-id accept-cuda --device cuda --limit 3
& $avk semantic calibration-list --project $project
```
\n'''+words['quality']+'\n\n'+words['migration']+'\n\n[Workflow](docs/product/SEMANTIC_RETRIEVAL.md) · [Actual checks and failures]('+REPORT+') · [All 80 results]('+GALLERY+'/index.html) · [C19](docs/product/CASES.md#c19-semantic-decisions)\n\n![Actual decisions, including errors]('+DEMO+'/decisions.gif)\n\n<!-- /semantic-decision-r1 -->\n\n'
        if '<!-- semantic-decision-r1 -->' in text:
            text=re.sub(r'\n*<!-- semantic-decision-r1 -->.*?<!-- /semantic-decision-r1 -->\n*',lambda _:section,text,flags=re.S)
        else:
            marker='<!-- subtitle-dubbing-r1 -->'
            assert marker in text
            text=text.replace(marker,section+marker,1)
        new_rows=[]
        for key,title,result,path in checks:
            new_rows.append(f'| {key} | {title} | {result} | [2026-10-25 evidence](docs/validation/evidence/semantic-decision-20261025-r1/{path}) · [Full scope]({REPORT}) |')
        if 'R76' not in rows(text,'R'):
            last=rows(text,'R')['R75']
            text=text.replace(last,last+'\n'+'\n'.join(new_rows),1)
        assert all(rows(text,'R')[k]==v for k,v in old_rows.items() if int(k[1:])<=75)
        assert all(rows(text,'R')[k]==v for k,v in protected.items() if int(k[1:])<=75)
        write(name,text)
    # Keep every original closure condition byte-for-byte while updating real state.
    path='docs/product/GOAL_GAPS_20261025.md'
    text=read(path); original_rows=rows(text,'G')
    original_closure={key:line.split('|')[5].strip() for key,line in original_rows.items()}
    text=re.sub(r'2026-10-25 当前本地交付仍为.*?以下 G01–G38 原关闭条件全部保持。',
        '2026-10-25 当前本地交付为 **CLI 0.1.10 / alpha.4-local.8 / r9 kit**，199 个产品 Python 文件与固定安装版逐字节相同。显式条件与经验拒识已进入发行 ZIP 和真实统一 Skill；CPU/GPU/Skill 仍有两条库外误接受和一条原钟表误拒。另发现检索/校准工程导入后索引路径错误；原失败留档。源码/安装契约、实际模型、控制路径、C19 与迁移失败分范围记录，不能当通用检索或自然广告质量完成。[本批完整实测](../validation/语义条件与校准拒识实测_2026-10-25.md)。r10/r11/r12 是此前只读历史盘点；以下 G01–G38 原关闭条件全部保持。', text, count=1, flags=re.S)
    text=replace_row(text,'V01','| V01 | 当前已安装与注册 | alpha.4-local.8 / CLI 0.1.10，单一 Skill、17 模块、r9 kit；[199 文件安装](../validation/evidence/semantic-decision-20261025-r1/installation-r1/verification.json)，原 local.7/r8 保留 |')
    text=text.replace('[实际响应](subtitle-dubbing-capabilities-cli-0.1.9.json)','[当前实际响应](semantic-decision-capabilities-cli-0.1.10.json)')
    text=text.replace('| V10 | 本次 r12 当前状态 |','| V10 | 此前 r12 历史状态 |').replace('| V11 | 检索开发候选，不是安装版 |','| V11 | r12 当时的开发候选快照 |')
    extra='''| V12 | 新安装版 CPU/GPU 与 Skill | 校准各 40 条，另组各 60 条，原 20 条及 raw 各自实测；正确与失败分开保留，[完整结果](../validation/语义条件与校准拒识实测_2026-10-25.md) |
| V13 | 新控制、诊断与迁移错误 | 安装版 9 次控制、全部 80 条预览、C19 12 秒/360 帧和卡片往返通过；检索工程导入后 `SEMANTIC_INDEX_INVALID`，不能宣称附属能力可搬迁 |
| V14 | 新独立工具包验证 | r9 在独立中文/空格目录配置/注册/调用，仍为同一主机与既有模型；[实测](../validation/evidence/semantic-decision-20261025-r1/kit-r1/verification.json)，不是干净主机/跨机器验收 |
'''
    if 'V12' not in rows(text,'V'):
        text=text.replace(rows(text,'V')['V11'],rows(text,'V')['V11']+'\n'+extra.rstrip())
    changes={
      'G26':('CLI 0.1.10 已交付明确正/负条件、同采样帧评分、索引/实现/类型/实际设备绑定经验校准、匹配/无匹配；安装版 CPU/CUDA 和真实 Skill 已验', '原否定 2/2、原库外 2/2 改善，但原正向钟表误拒 1 条；另组 CPU/GPU/Skill 库外仅拒绝 18/20，大象/吉他误选。仅熟悉静态图和有界语法；新档案工程迁移报错，自然动作/身份/音频/推荐、大库与常驻复用未闭'),
      'G31':(None,'当前声明 degraded；复杂效果、排版、Bezier/私有依赖不能完整映射。新语义索引/校准工程虽 export/import/validate 成功，检索实际报 Manifest outside project semantic asset tree；普通卡片像素往返另通过。真实授权草稿与跨机器附属能力往返不足'),
      'G32':(None,'仅 RTX 3060、配音仅设备 0；19 秒字幕 CPU render 约 210/198 秒（非独占）。新语义批内复用有实测，但每命令完整性读取/模型加载成本仍大；大量效果未 GPU 化，常驻、多依赖、并发显存和长片/4K P50/P95 未闭'),
      'G33':(None,'只覆盖共享 helper 和两类受管路径；新语义校准正常失败/取消/元数据回滚已验，尚非受管崩溃恢复任务。旧缓存、其他模型、断点续算、断电/磁盘耗尽/设备丢失、长并发与公平性仍未完整验收'),
      'G38':('公开 alpha.3 / CLI 0.1.2 保留；本地 alpha.4-local.8 / CLI 0.1.10、r9 kit 已安装和真实入口核验', '截至最近成功官方 API 核对仍为 alpha.3；本地新 GPU/素材、采集、检索/经验校准、四轨/恢复、词活动边界和字幕配音尚未形成对应公开 Release，完整正式版门禁未过'),
    }
    for key,(implemented,gap) in changes.items():
        cells=rows(text,'G')[key].split('|')
        if implemented:cells[3]=' '+implemented+' '
        cells[4]=' '+gap+' '
        text=replace_row(text,key,'|'.join(cells))
    q08='| Q08 | [原检索失败](../validation/离线语义检索实测_2026-10-25.md)与[新实际 CPU/GPU/Skill/迁移失败](../validation/语义条件与校准拒识实测_2026-10-25.md) | 条件与经验阈值已交付；修复原否定/库外选择，但保留原钟表误拒、另组大象/吉他误接受和新检索工程迁移失败。未据门槛通过关闭 G26/G31 |'
    text=replace_row(text,'Q08',q08)
    start=text.index('## 本次开发候选与交付版本的差别')
    end=text.index('## 建议执行顺序',start)
    text=text[:start]+'''## 新交付与仍未关闭的边界

此前 r12 的未安装候选与失败快照原样保留。现 CLI 0.1.10 已完成新 ZIP 离线安装、CPU/GPU 校准/查询、真实 Skill 和独立 r9 工具包入口核验；并未重新解释历史记录。

| 编号 | 范围 | 实际结果与仍缺条件 |
|---|---|---|
| D01 | 当前可直接使用 | CLI 0.1.10 / local.8 / r9；固定安装，单一入口/17 模块；旧 local.7/r8 留存 |
| D02 | 契约与回归 | 最终源码 48/48、另安装专项 48/48、安装 CLI 122/122，均 0 skip；替身契约不作模型质量 |
| D03 | CPU/GPU 经验校准 | 各 20/20 正向、1/20 库外误接受；CPU 与 CUDA 阈值不同，不能解释为概率或通用保证 |
| D04 | 另组 60 条与真实 Skill | 三个入口均 20/20 正向、20/20 否定、18/20 库外拒绝；大象/吉他误选保留，只有查询措辞独立 |
| D05 | 原 20 条与 raw | 新模式正向 15/16，否定/库外各 2/2，钟表误拒；实际 raw 仍 16/16、1/2、0/2，保留召回/拒识权衡 |
| D06 | 实际媒体与迁移 | 80 结果全预览，C19 12 秒/360 帧卡片包往返通过；新检索工程导入后检索失败，不能宣称档案可搬迁 |
| D07 | 仍需工作 | 独立新素材与人工标注、自然动作/身份/音频/推荐、通用语法、大库/常驻、语义崩溃任务与跨机器交付；全部 38 原条件不变 |

''' +text[end:]
    text=text.replace('安装版和一个 Skill 可执行的联合流程','安装版和一个 Skill 可执行的联合流程')
    text=text[:text.index('\nEnglish:')] + '''

新增 G26 条件/经验校准和固定交付不改变其他工作范围；新迁移错误增加 G31 的具体可复现问题。
[本批实测、错误与 C19](../validation/语义条件与校准拒识实测_2026-10-25.md)与此前 r12 只读盘点分别保留。
English: current local CLI 0.1.10 ships explicit clauses and empirical profiles, with real installed CPU/CUDA and unified-Skill evidence.
Two held-out false accepts, one original false rejection and a new retrieval-package migration failure remain.
All 38 original closure conditions still apply; no overall completion percentage or full CapCut parity is established.
'''
    assert original_closure=={key:line.split('|')[5].strip() for key,line in rows(text,'G').items()}
    write(path,text)
    for suffix in ('','.zh-TW','.en'):
        for kind in ('CAPABILITIES','SKILLS'):
            path='docs/product/'+kind+suffix+'.md'
            text=read(path)
            text=text.replace('[Machine response](subtitle-dubbing-capabilities-cli-0.1.9.json)', '[Machine response](semantic-decision-capabilities-cli-0.1.10.json)')
            marker='<!-- semantic-decisions-current -->'
            section='''\n\n<!-- semantic-decisions-current -->

## CLI 0.1.10 / F50 / S18 / K08: explicit clauses and empirical acceptance

[完整流程 / Workflow](SEMANTIC_RETRIEVAL.md) · [实际质量/错误 / Actual results](../validation/语义条件与校准拒识实测_2026-10-25.md) · [C19](CASES.md#c19-semantic-decisions).

中英条件检索与同帧正负比较、索引/类型/实现/实际设备绑定经验校准已交付。
中英條件檢索、同影格正負比較與裝置綁定經驗校準已實作。
`semantic calibrate/calibration-list/search` uses 32–128 reviewed examples (at least 16 positive and 16 absent),
a correct-positive gate and empirical strict cutoff. Labels stay in the controller. All results still require review.
Installed CPU/CUDA and the actual Skill retain two false accepts and one original false rejection.
The new retrieval package fails search after import even though general validate succeeds; portable profiles are not established.
Complex negation, natural actions/identity/audio/recommendation, large-library performance and managed semantic crash recovery remain open.
Original CLI 0.1.5 query failures and raw mode remain historical evidence; they are not erased by this extension.

<!-- /semantic-decisions-current -->
'''
            if marker in text:text=re.sub(r'\n*<!-- semantic-decisions-current -->.*?<!-- /semantic-decisions-current -->\n*',lambda _:section,text,flags=re.S)
            else:text+=section
            if kind=='SKILLS':text=text.replace('semantic index/search`','semantic index/calibrate/calibration-list/search`')
            write(path,text)
    path='docs/product/CASES.md'; text=read(path)
    if 'id="c19-semantic-decisions"' not in text:
        text+='''\n\n<a id="c19-semantic-decisions"></a>

## C19：条件/拒识完整预览与真实工程迁移失败 / Decisions and migration failure

[完整实测](../validation/语义条件与校准拒识实测_2026-10-25.md) · [全部 80 条决策](../assets/semantic-decision-20261025-r1/installed-r1/index.html) · [实际源与许可](../assets/semantic-decision-20261025-r1/SOURCE.json)。

![Actual decisions including all three query failures](../assets/semantic-decision-20261025-r1/demo-installed-r1/decisions.gif)

| 编号 | 输入/输出 | 实际核验与边界 |
|---|---|---|
| C19-01 | 已冻结 40 校准/60 另组/20 原查询，11 资产/10 类熟悉静态图 | 真实安装 CPU/CUDA 与统一 Skill；另组库外 18/20，保留大象/吉他误选与原钟表误拒 |
| C19-02 | 全部 80 条实际决策 → HTML/4 张 PNG/JSON | 包含全部失败；其余候选不保证全部相关；无新的模型推理 |
| C19-03 | 六张实际结果卡 → [12 秒 MP4](../assets/semantic-decision-20261025-r1/demo-installed-r1/decisions.mp4) / GIF | 960×540 / 30fps / 360 帧；GIF 5fps / 60 帧 / 12000ms，非执行录像或自然广告 |
| C19-04 | [六段可编辑卡片包](../assets/semantic-decision-20261025-r1/demo-installed-r1/editable-cards.aevpkg.zip) → 导入/重渲染 | 全部解码帧摘要相同；六段 image clips 可编辑，卡内文字是栅格图 |
| C19-05 | 新检索/校准工程 → 导出/导入/通用 validate → search dry-run | 前三步成功、search 实际失败 `SEMANTIC_INDEX_INVALID`；[错误与复现包说明](../assets/semantic-decision-20261025-r1/demo-installed-r1/KNOWN_ISSUE.md)，不计可搬迁通过 |
| C19-06 | [六张实际编码帧](../assets/semantic-decision-20261025-r1/demo-installed-r1/actual-encoded-frames.png) | Agent 静态检查；不是人类连续播放/听审/语义接受，无声音音轨 |

[19 次 CLI 原始失败](../validation/evidence/semantic-decision-20261025-r1/demo-installed-r1/failure.json)与
[已完成媒体核验](../validation/evidence/semantic-decision-20261025-r1/demo-finalization-r1/verification.json)分别保存。
English: real output retains all mistakes. Card-package frames match; the separate indexed/calibrated project fails search after import.
All original G26/G31/G32/G33/G36 conditions remain; no natural-action, human acceptance or clean-host migration claim.
'''
    write(path,text)
    path='docs/product/IMPLEMENTATION_PLAN_20261025.md';text=read(path)
    text=re.sub(r'^\| W05 [^\n]+', '| W05 内容与广告生产 | G06–G07、G25–G29 | 效果/模板/运镜/开源媒体库、检索与真实广告返工 | CLI 0.1.10 条件/经验校准已安装；真实 CPU/GPU/Skill 保留两条误选、一条误拒和新迁移错误；自然动作/身份/音频/推荐、大库/常驻与内容生态仍开放 |',text,flags=re.M)
    text+='''\n2026-10-25 新交付 [CLI 0.1.10 / 条件与经验校准](../validation/语义条件与校准拒识实测_2026-10-25.md)：local.8/r9，199 文件固定安装；实际 CPU/CUDA/统一 Skill 与源码/安装契约分范围通过。两条库外误接受、一条原钟表误拒保留。C19 卡片工程像素往返通过，但新检索/校准工程导入后检索失败，G31 追加具体复现；不改写此前 r12 历史候选结论。全部 38 原条件保持，总目标进行中。
'''
    write(path,text)
    path='docs/README.md';text=read(path)
    # Consolidate only the stale current-status preamble; all historic catalog entries remain.
    first_table=text.index('|')
    heading=text[:text.index('\n')]
    text=heading+'''\n\n[简体中文](../README.md) · [繁體中文](../README.zh-TW.md) · [English](../README.en.md) · [Repository](https://github.com/copypasteltd/agent-editor-kit)

当前本机交付 **CLI 0.1.10 / alpha.4-local.8 / r9 kit**，固定安装包、1 Skill/17 模块。
新增条件检索和设备绑定经验校准，CPU/GPU/真实 Skill 均有收据；两条库外误选、一条钟表误拒和检索工程迁移失败保留。
[完整 G01–G38 差距表](product/GOAL_GAPS_20261025.md) · [本批实际实现/失败/C19](validation/语义条件与校准拒识实测_2026-10-25.md) ·
[当前安装流程](product/COMMUNITY_LOCAL_DELIVERY.md) · [全部 80 条预览](assets/semantic-decision-20261025-r1/installed-r1/index.html)。
三语功能手册保留 F01–F51 / S01–S20 与 75 项真实能力字段；完整剪映目标未完成，无总体完成率。
公开 alpha.3 / CLI 0.1.2 旧包与所有历史收据/原关闭条件保留。
Current local delivery and actual query/migration failures are explicit; all 38 original closure conditions apply.

'''+text[first_table:]
    # The first catalog row is current, other explicitly versioned records stay historic.
    lines=text.splitlines()
    for i,line in enumerate(lines):
        if line.startswith('| 当前 CLI 0.1.9'):
            lines[i]='| 当前 CLI 0.1.10 的全部 38 组差距 / Current full-goal assessment | [最新编号表](product/GOAL_GAPS_20261025.md) · [CPU/GPU/Skill 与错误](validation/语义条件与校准拒识实测_2026-10-25.md) · [C19](product/CASES.md#c19-semantic-decisions) |'
    write(path,'\n'.join(lines)+'\n')
    print(json.dumps(dict(status='synchronized',cli_version='0.1.10',readme_rows_preserved=75,
        appended_rows='R76–R81',gap_closure_conditions_preserved=len(original_closure)),ensure_ascii=False))


if __name__ == '__main__':main()
