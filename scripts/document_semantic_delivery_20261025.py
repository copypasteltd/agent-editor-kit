"""Update current manuals without deleting historical numbered README evidence."""
from pathlib import Path
import collections,hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/semantic-20261025-r1'
REPORT='docs/validation/离线语义检索实测_2026-10-25.md'


def load(relative):return json.loads((BASE/relative).read_bytes())
def write(path,text):path.write_text(text,encoding='utf8',newline='\n')
def replace_row(text,ident,line):
    pattern=r'^\| '+re.escape(ident)+r' \|.*$'
    text,count=re.subn(pattern,lambda _:line,text,flags=re.M)
    assert count==1,(ident,count)
    return text


CONFIG={
'README.md':dict(
    section='本地 CLI 0.1.5：按描述或参考图检索素材',
    intro='使用已有离线 SigLIP2 模型，对选定图片和视频采样帧建立向量索引；按中文、英文或本地参考图返回候选预览、源时间和可编辑引用。仍使用一个 `$agent-ffmpeg-local-editor`。',
    limitation='在预先冻结的小样本中，开发版 CPU/GPU 的 16 条常规查询首选及 mean asset recall@3 均为 1.0；安装版真实 Skill 另验相同 20 条文本与 CPU 参考图。中文否定误选咖啡，两条库外鲨鱼查询仍返回草地；不是可靠拒识、动作理解或自动导演。',
    dependencies='基础 ZIP 不含 Torch 或约 1.5GB 权重。先按本地交付配置已有原生环境，读取 runtime.json 的 semantic_config，明确登记到工程，再建立索引；不隐式下载。',
    feature='| F50 / V01 | 离线图文语义索引、中文/英文/参考图查询、预览与可编辑时间点，auto/cpu/cuda | 小型静态图集实测；否定/库外拒识/自然动作/音频推荐仍未完成 |',
    service='| S18 | 图文语义检索 | 显式登记的原生 SigLIP2 worker | 已有 Torch/Transformers/模型；实际 GPU/CPU、源/预览/向量完整性 | `semantic adapter-register/index/search/verify` | 冷启动和大库性能未收口；分数不是概率 |',
    skill='| K08 | [`video-understand`](skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md) | 镜头/静音、图文语义检索与视频证据 | 本地视频/图片/描述/参考图 → 分析、预览、源时间与候选 | `media understand/contact-sheet; subtitle transcribe; semantic index/search` | [检索说明](skills/agent-ffmpeg-local-editor/references/semantic-retrieval.md)；采样点不定义片段时长，候选需复核。 |',
    case_title='C14：实际检索候选 → 可编辑片段 → 安装版成片',
    case='冻结查询的真实返回中，明确选择猫、咖啡、宇航员三个视频候选，保留其原排名和源时间；每段人工规则指定 1 秒。安装版 11 次 CLI 完成工程、字幕、渲染、质检、工程包导出/导入和重渲染：3 秒、640×360、30fps/90 帧，往返解码画面相同。输入为自然静态图组成的序列，不能推断自然运动或广告质量；音轨与人工视听范围单列。',
    latest='**最新交付（R45–R48，2026-10-25）：** 本机升级 CLI 0.1.5 / alpha.4-local.3；73 项能力声明为 20 已实现、45 有限制、7 本地适配器、1 降级，不是完成率。G26 图文检索已完成实际 CPU/GPU 对照、固定安装包与统一 Skill 调用、可编辑成片往返；否定/库外拒识、自然动作/身份/音频推荐、大库与模型常驻仍缺。完整 38 组差距均保留未关闭条件；公开发行仍为 alpha.3 / CLI 0.1.2。',
    rows=[
        '| R45 | 真实图文语义相关性 | 开发索引 2 次 CUDA 图像前向；5 次查询 CLI 共 11 次前向；CPU/GPU 常规 16 条 top-1/mean recall@3 均 1.0，6 时间点、参考图、同图改名与只读门禁通过 | [全部 20 条评分](docs/validation/evidence/semantic-20261025-r1/development-r1/queries/quality.json) · [失败也展示](docs/assets/semantic-20261025-r1/all-query-results.png)；2026-10-25，中文否定错选、2 条库外未拒识；非自然动作/未见训练集验收 |',
        '| R46 | 检索契约、异常与回归 | 开发 25 项和安装版另 25 项契约测试；CLI 122 项、离线策略 34 项分别通过；8 次实际异常 CLI、存活 worker 取消约 0.21 秒并退出 | [本轮实测](docs/validation/离线语义检索实测_2026-10-25.md)；2026-10-25，测试范围有重叠，不相加；取消仅验启动/完整性阶段 |',
        '| R47 | CLI 0.1.5 固定安装与单一 Skill | 新 8-wheel 包及全部产品 Python 源字节核对；4 既有模型包重验；真实注册入口 9 次 CLI，包含实际 GPU 批量文本和 CPU 参考图；r4 kit 独立入口另验 | [安装摘要](docs/product/COMMUNITY_LOCAL_DELIVERY.md) · [入口实测](docs/validation/evidence/semantic-20261025-r1/skill-r1/verification.json)；2026-10-25，单台物理主机，不冒充公开新 Release |',
        '| R48 | 检索候选的可编辑案例 | 开发版 11 次 CLI、安装版另 11 次 CLI；3 秒/90 帧实际渲染、完整解码、工程往返像素相同 | [实际 MP4/GIF/工程包](docs/product/CASES.md#c14-semantic-retrieval) · [安装证据](docs/validation/evidence/semantic-20261025-r1/installed-r1/demo/verification.json)；2026-10-25，静态图序列、明确选 1 秒，非自动事件边界/自然动作或人工听审 |'
    ]),
'README.zh-TW.md':dict(
    section='本機 CLI 0.1.5：按描述或參考圖檢索素材',
    intro='使用既有離線 SigLIP2 模型，對選定圖片與影片採樣畫面建立向量索引；按中文、英文或本機參考圖返回候選預覽、來源時間與可編輯引用。仍使用一個 `$agent-ffmpeg-local-editor`。',
    limitation='在預先凍結的小樣本中，開發版 CPU/GPU 的 16 條常規查詢首選及 mean asset recall@3 均為 1.0；安裝版真實 Skill 另驗相同 20 條文字與 CPU 參考圖。中文否定誤選咖啡，兩條庫外鯊魚查詢仍返回草地；尚無可靠拒識、動作理解或自動導演。',
    dependencies='基礎 ZIP 不含 Torch 或約 1.5GB 權重。先按本機交付設定既有原生環境，讀取 runtime.json 的 semantic_config，明確登記至工程後再建立索引；不隱式下載。',
    feature='| F50 / V01 | 離線圖文語義索引、中文/英文/參考圖查詢、預覽與可編輯時間點，auto/cpu/cuda | 小型靜態圖集實測；否定/庫外拒識/自然動作/音訊推薦仍未完成 |',
    service='| S18 | 圖文語義檢索 | 明確登記的原生 SigLIP2 worker | 既有 Torch/Transformers/模型；實際 GPU/CPU、來源/預覽/向量完整性 | `semantic adapter-register/index/search/verify` | 冷啟動與大庫效能未收口；分數不是機率 |',
    skill='| K08 | [`video-understand`](skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md) | 鏡頭/靜音、圖文語義檢索與影片證據 | 本機影片/圖片/描述/參考圖 → 分析、預覽、來源時間與候選 | `media understand/contact-sheet; subtitle transcribe; semantic index/search` | [檢索說明](skills/agent-ffmpeg-local-editor/references/semantic-retrieval.md)；採樣點不定義片段長度，候選需複核。 |',
    case_title='C14：實際檢索候選 → 可編輯片段 → 安裝版成片',
    case='從凍結查詢的真實返回中，明確選擇貓、咖啡、太空人三個影片候選，保留原排名及來源時間；每段以明確規則指定 1 秒。安裝版 11 次 CLI 完成工程、字幕、渲染、質檢、工程包匯出/匯入及重渲染：3 秒、640×360、30fps/90 幀，往返解碼畫面相同。輸入為自然靜態圖片組成的序列，不能推論自然運動或廣告品質；音軌與人工視聽範圍另列。',
    latest='**最新交付（R45–R48，2026-10-25）：** 本機升級 CLI 0.1.5 / alpha.4-local.3；73 項能力聲明為 20 已實作、45 有限制、7 本機適配器、1 降級，不是完成率。G26 圖文檢索已完成實際 CPU/GPU 對照、固定安裝包與統一 Skill 調用、可編輯成片往返；否定/庫外拒識、自然動作/身份/音訊推薦、大庫與模型常駐仍缺。完整 38 組差距均保留未關閉條件；公開發行仍為 alpha.3 / CLI 0.1.2。',
    rows=[
        '| R45 | 真實圖文語義相關性 | 開發索引 2 次 CUDA 圖像前向；5 次查詢 CLI 共 11 次前向；CPU/GPU 常規 16 條 top-1/mean recall@3 均 1.0，6 時間點、參考圖、同圖改名與唯讀門禁通過 | [全部 20 條評分](docs/validation/evidence/semantic-20261025-r1/development-r1/queries/quality.json) · [失敗亦展示](docs/assets/semantic-20261025-r1/all-query-results.png)；2026-10-25，中文否定錯選、2 條庫外未拒識；非自然動作/未見訓練集驗收 |',
        '| R46 | 檢索契約、異常與回歸 | 開發 25 項與安裝版另 25 項契約測試；CLI 122 項、離線策略 34 項分別通過；8 次實際異常 CLI、存活 worker 取消約 0.21 秒並退出 | [本輪實測](docs/validation/离线语义检索实测_2026-10-25.md)；2026-10-25，範圍重疊不相加；取消僅驗啟動/完整性階段 |',
        '| R47 | CLI 0.1.5 固定安裝與單一 Skill | 新 8-wheel 包及全部產品 Python 原始碼位元核對；4 既有模型包重驗；真實註冊入口 9 次 CLI，包含實際 GPU 批量文字與 CPU 參考圖；r4 kit 獨立入口另驗 | [安裝摘要](docs/product/COMMUNITY_LOCAL_DELIVERY.md) · [入口實測](docs/validation/evidence/semantic-20261025-r1/skill-r1/verification.json)；2026-10-25，單台實體主機，不冒充公開新 Release |',
        '| R48 | 檢索候選的可編輯案例 | 開發版 11 次 CLI、安裝版另 11 次 CLI；3 秒/90 幀實際渲染、完整解碼、工程往返像素相同 | [實際 MP4/GIF/工程包](docs/product/CASES.md#c14-semantic-retrieval) · [安裝證據](docs/validation/evidence/semantic-20261025-r1/installed-r1/demo/verification.json)；2026-10-25，靜態圖片序列、明確選 1 秒，非自動事件邊界/自然動作或人工聽審 |'
    ]),
'README.en.md':dict(
    section='Local CLI 0.1.5: find footage by description or reference image',
    intro='Build real SigLIP2 embeddings for explicitly selected local images and video samples. Chinese, English and reference-image queries return previews, source times and editable references through the same `$agent-ffmpeg-local-editor` entry.',
    limitation='On the pre-frozen small set, development CPU/GPU positive top-1 and mean asset recall@3 are 1.0 for 16 ordinary queries; the installed Skill separately exercises all 20 text queries and a CPU reference image. Chinese negation chooses coffee incorrectly and both out-of-library shark queries return grass. Reliable rejection, natural-action understanding and automatic direction remain open.',
    dependencies='The base ZIP excludes Torch and the approximately 1.5GB weights. Configure an existing native environment, read semantic_config from runtime.json, explicitly register it per project, then index. No implicit downloads.',
    feature='| F50 / V01 | Offline image/text embeddings, Chinese/English/reference-image queries, previews and editable source points; auto/cpu/cuda | Small static-image acceptance; negation, open-set rejection, natural actions and audio recommendation remain open |',
    service='| S18 | Visual semantic retrieval | Explicit native SigLIP2 worker | Existing Torch/Transformers/model; actual GPU/CPU and source/preview/vector integrity | `semantic adapter-register/index/search/verify` | Cold-start and large-library performance open; cosine is not probability |',
    skill='| K08 | [`video-understand`](skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md) | Scene/silence, semantic retrieval and video evidence | Local video/images/text/reference → analysis, previews, source times and candidates | `media understand/contact-sheet; subtitle transcribe; semantic index/search` | [Retrieval reference](skills/agent-ffmpeg-local-editor/references/semantic-retrieval.md); sample points provide no event duration; review candidates. |',
    case_title='C14: actual retrieval candidates → editable clips → installed output',
    case='Explicitly select cat, coffee and astronaut video candidates from actual frozen-query responses, preserving overall returned ranks and source times. Author one second per clip. Eleven installed CLI calls build the project/captions, render, check, export/import and rerender: 3s, 640×360, 30fps/90 frames, with identical decoded roundtrip pixels. The input is a sequence of natural stills, not an acceptance test for natural motion or ad quality; audio and human review are recorded separately.',
    latest='**Latest delivery (R45–R48, 2026-10-25):** local CLI 0.1.5 / alpha.4-local.3 has 73 declarations: 20 implemented, 45 limited, seven adapter-only and one degraded; these are not a completion percentage. G26 now has actual CPU/GPU comparisons, a pinned installed runtime/one Skill and editable roundtrip output. Negation, open-set rejection, natural actions/identity/audio recommendation, large libraries and persistent model reuse remain open. All 38 gap groups retain unmet conditions. Public release remains alpha.3 / CLI 0.1.2.',
    rows=[
        '| R45 | Actual semantic relevance | Development index: two CUDA image forwards; five search CLI calls: eleven forwards; CPU/GPU 16-positive top-1/mean recall@3 both 1.0, with six timestamps, reference image, renamed duplicate and read-only gates passing | [All 20 scored queries](docs/validation/evidence/semantic-20261025-r1/development-r1/queries/quality.json) · [Failures included](docs/assets/semantic-20261025-r1/all-query-results.png); 2026-10-25, Chinese negation fails and both OOD queries lack rejection; no natural-action/unseen-training acceptance |',
        '| R46 | Retrieval contracts, adverse paths and regression | 25 development and separately 25 installed contract tests; 122 CLI and 34 offline-policy tests pass separately; eight actual adverse CLI calls and a live worker canceled/exited in about 0.21s | [Validation](docs/validation/离线语义检索实测_2026-10-25.md); 2026-10-25, overlapping scopes are not added; cancellation covers startup/integrity only |',
        '| R47 | Pinned CLI 0.1.5 and one Skill | New eight-wheel bundle, every product Python source byte compared, four existing packs reverified; nine actual registered-entry calls including GPU text batch and CPU reference; r4 kit separately checked | [Delivery hashes](docs/product/COMMUNITY_LOCAL_DELIVERY.md) · [Actual Skill evidence](docs/validation/evidence/semantic-20261025-r1/skill-r1/verification.json); 2026-10-25, same physical host, no new public Release claim |',
        '| R48 | Editable retrieval demonstration | Eleven development CLI calls and separately eleven installed calls; actual 3s/90-frame renders, full decode and identical package-roundtrip pixels | [MP4/GIF/editable package](docs/product/CASES.md#c14-semantic-retrieval) · [Installed evidence](docs/validation/evidence/semantic-20261025-r1/installed-r1/demo/verification.json); 2026-10-25, still sequence and explicitly authored 1s ranges; no inferred event extent/natural-action or human-listening acceptance |'
    ])}


def main():
    skill=load('skill-r1/verification.json');demo=load('installed-r1/demo/verification.json')
    install=load('installation/verification.json');source=load('development-r1/queries/verification.json')
    assert skill['status']=='passed-with-quality-limits' and all(skill['gates'].values())
    assert demo['status']=='passed' and demo['demonstration']['package_roundtrip_decoded_pixels_equal']
    assert source['quality_all_gates_passed'] and install['status']=='installed_source_bytes_match'
    caps=load('skill-r1/03.stdout.json');counts=collections.Counter(r['status'] for r in caps['data']['capabilities'].values())
    assert counts==dict(implemented=20,implemented_with_limits=45,local_adapter_only=7,degraded=1),counts
    catalog=ROOT/'docs/product/semantic-capabilities-cli-0.1.5.json'
    write(catalog,json.dumps(caps,ensure_ascii=False,indent=2)+'\n')
    evidence_rows=[]
    for name,c in CONFIG.items():
        path=ROOT/name;old=path.read_text('utf8');text=old
        assert '<!-- semantic-retrieval-r1 -->' not in text
        historical=re.findall(r'^\| R(?:0[1-9]|[1-3][0-9]|4[0-4]) \|.*$',old,re.M)
        assert len(historical)==44
        text=text.replace('[r3 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r3.zip)',
                          '[r4 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r4.zip)',1)
        # Only the current extension banner changes; dated capture/R01-R44 stay intact.
        text=text.replace('CLI 0.1.4, GPU voice','CLI 0.1.5, GPU voice',1)
        text=text.replace('CLI 0.1.4，GPU','CLI 0.1.5，GPU',1)
        text=re.sub(r'(?m)^(## 43[^\n]*)(?:F44[–-]F48)([^\n]*)$',r'\1F44–F50\2',text)
        line=next(l for l in text.splitlines() if l.startswith('| F49 /'))
        text=text.replace(line,line+'\n'+c['feature'],1)
        line=next(l for l in text.splitlines() if l.startswith('| S17 |'))
        text=text.replace(line,line+'\n'+c['service'],1)
        text=replace_row(text,'K08',c['skill'])
        commands="""```powershell
# Existing project, registered local adapter and ingested source IDs required.
& $avk semantic index --project $project --index-id campaign-v1 --adapter-id siglip2 --all-visual-assets --sample-interval-seconds 2 --device auto
& $avk semantic search --project $project --index-id campaign-v1 --query '木桌上的一杯咖啡' --limit 5 --device auto
& $avk semantic search --project $project --index-id campaign-v1 --image $referenceImage --kind image --device cpu
```"""
        section=('<!-- semantic-retrieval-r1 -->\n\n## '+c['section']+'\n\n'+c['intro']+'\n\n'+c['dependencies']+
            '\n\n[Workflow / 登记与命令](docs/product/SEMANTIC_RETRIEVAL.md) · [Validation / 实测]('+REPORT+') · [All 20 queries / 全部结果](docs/assets/semantic-20261025-r1/all-query-results.png)\n\n'+
            commands+'\n\n'+c['limitation']+'\n\n![All frozen queries, including failures](docs/assets/semantic-20261025-r1/all-query-results.png)\n\n<!-- /semantic-retrieval-r1 -->\n\n')
        text=text.replace('<!-- native-capture-r1 -->',section+'<!-- native-capture-r1 -->',1)
        case=('### '+c['case_title']+'\n\n'+c['case']+
            '\n\n![Actual installed candidate-to-edit output](docs/assets/semantic-20261025-r1/demo-installed-r1-workflow/semantic-cut.gif)\n\n'+
            '[Input MP4](docs/assets/semantic-20261025-r1/asset_v1.mp4) · [Output MP4](docs/assets/semantic-20261025-r1/demo-installed-r1-workflow/semantic-cut.mp4) · '+
            '[Candidate/output board](docs/assets/semantic-20261025-r1/demo-installed-r1-workflow/candidate-to-output.png) · '+
            '[Editable package](docs/assets/semantic-20261025-r1/demo-installed-r1-workflow/editable-project.aevpkg.zip) · [Full case](docs/product/CASES.md#c14-semantic-retrieval)\n\n')
        case_index=text.index('<!-- community-cases -->')
        text=text[:case_index]+case+text[case_index:]
        row=next(l for l in text.splitlines() if l.startswith('| R44 |'))
        text=text.replace(row,row+'\n'+'\n'.join(c['rows']),1)
        # Replace stale present-tense summaries only; historical evidence is unchanged.
        start=text.index('\n## ',text.index('| R48 |'))
        end=text.index('\n## ',start+4)
        tail=text[start:end]
        tail=re.sub(r'\*\*[^\n]*R44[^\n]*\*\*[^\n]*',lambda _:c['latest'],tail,count=1)
        tail=tail.replace('CLI 0.1.4','CLI 0.1.5').replace('72 ','73 ')
        stale=[l for l in tail.splitlines() if ('R43' in l and ('本次' in l or '本輪' in l or '本次' in l or 'This R43' in l))]
        for line in stale:
            tail=tail.replace(line,'')
        text=text[:start]+tail+text[end:]
        assert all(row in text for row in historical),'Historical README rows changed'
        assert len(re.findall(r'^\| R\d\d \|',text,re.M))==48
        write(path,text)
        evidence_rows.append(dict(path=name,old_bytes=len(old.encode()),new_bytes=len(text.encode()),historical_R01_R44_unchanged=True))
    delivery=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=delivery.read_text('utf8')
    text=text.replace('v0.1.0-alpha.4-local.2','v0.1.0-alpha.4-local.3').replace('CLI 0.1.4','CLI 0.1.5')
    text=text.replace('local/agent-ffmpeg/v0.1.0-alpha.4-local.3/agent-editor-kit-v0.1.0-alpha.4-local.3-cp313-win_amd64.zip',
                      'local/agent-ffmpeg/v0.1.0-alpha.4-local.3/candidate-r1/bundle.zip')
    text=text.replace('4e406058e082d1c9d778e9c4665f307d5027f17542c6fabfbc9d8d72ac0a2333',install['archive_sha256'])
    text=text.replace('fd418d94461b57423072fb730959e36cb39264fd48a96be26dc297fe52b59897',install['manifest_sha256'])
    text=text.replace('agent-editor-kit-community-unified-skill-r3.zip','agent-editor-kit-community-unified-skill-r4.zip')
    text=text.replace('community-unified-skill-package-0.1.4.json','community-unified-skill-package-0.1.5.json')
    text+='''

## CLI 0.1.5 离线图文语义检索 / Offline visual semantic retrieval

[完整使用流程](SEMANTIC_RETRIEVAL.md) · [本轮完整实测](../validation/离线语义检索实测_2026-10-25.md)。
新基础 ZIP 为 302,607,251 字节；8 wheel / 47 文件，产品 wheel 版本 0.1.5。
全部产品 Python 文件与安装版逐字节摘要相同；[原生安装记录](../validation/evidence/semantic-20261025-r1/installation/verification.json)。
同一 RTX 3060 主机验证 CUDA BF16 和 CPU float32。Torch/Transformers 及约 1.5GB SigLIP2 权重
单独来自既有原生环境，不在基础 ZIP 或四个配音/翻译 ZIP 内；产品不隐式安装或下载。

现有工作区的 `local/agent-ffmpeg/semantic-runtime.json` 记录本机绝对路径、模型摘要和许可依据，
`runtime.json` 的 `semantic_config` 指向该文件。Agent 对新工程仍须明确 `semantic adapter-register`。
换主机应创建包含实际 `python_executable`、`model_path`、`evidence`、`creator`、`license_spdx`、
`verification_status` 与 `format: agent-local-semantic-runtime-v1` 的本地 JSON，再传给激活脚本；
不得复制不可用的绝对路径，登记时由产品重新检查依赖和字节。

```powershell
# The JSON and all referenced native paths must already exist.
& $aekPython -I -B -X utf8 ./scripts/activate_community_runtime.py --installed ./local/agent-ffmpeg/installed --packs $aekPacks --voice-cuda-lib $aekVoiceCuda --translation-cuda-lib $aekTranslationCuda --semantic-config $aekSemanticProfile
```

This optional profile supports explicit registration; it does not activate model inference or download files.
The base archive and four speech/translation packs remain separate. Clean-host acceptance is still open.

历史 CLI 0.1.4 / local.2：
`local/agent-ffmpeg/v0.1.0-alpha.4-local.2/agent-editor-kit-v0.1.0-alpha.4-local.2-cp313-win_amd64.zip`，
SHA-256 `4e406058e082d1c9d778e9c4665f307d5027f17542c6fabfbc9d8d72ac0a2333`，
manifest `sha256:fd418d94461b57423072fb730959e36cb39264fd48a96be26dc297fe52b59897`；
[r3 kit](../skills/agent-editor-kit-community-unified-skill-r3.zip) 继续对应旧包，旧标签/附件未改。
'''
    write(delivery,text)
    # Current manual banners are distinct from their preserved alpha.3 chapters.
    for stem in ('CAPABILITIES','SKILLS'):
        for suffix in ('','.en','.zh-TW'):
            path=ROOT/('docs/product/'+stem+suffix+'.md');text=path.read_text('utf8')
            text=re.sub(r'(<!-- community-current -->).*?(<!-- /community-current -->)',
                lambda m:m[1]+'\n\n**Current local / 当前本机 / 目前本機：CLI 0.1.5 / alpha.4-local.3。** '+
                'Offline visual semantic retrieval, GPU voice/translation, 359 resources, native capture and one Skill / 17 modules. '+
                'Public alpha.3 stays CLI 0.1.2. [Installation](COMMUNITY_LOCAL_DELIVERY.md) · [Semantic workflow](SEMANTIC_RETRIEVAL.md) · '+
                '[Current declarations](semantic-capabilities-cli-0.1.5.json) · [All 38 gaps](GOAL_GAPS_20261025.md).\n\n'+m[2],text,flags=re.S)
            if stem=='SKILLS':
                text=text.replace('`media understand/contact-sheet; subtitle transcribe`','`media understand/contact-sheet; subtitle transcribe; semantic index/search`')
            text+=('\n\n## CLI 0.1.5 / F50 / S18 / K08: visual semantic retrieval\n\n'+
                '[Complete workflow / 完整流程](SEMANTIC_RETRIEVAL.md) · '+
                '[Skill reference](../../skills/agent-ffmpeg-local-editor/references/semantic-retrieval.md) · '+
                '[Actual output](CASES.md#c14-semantic-retrieval).\n\n'+
                'Explicit local SigLIP2 image/video-sample embeddings; Chinese/English/reference-image search; native PTS, previews, editable source points, integrity and auto/cpu/cuda. '+
                '16 positive queries pass on this small familiar set; Chinese negation and both open-set queries fail expected selection/rejection. '+
                'No natural-action, cross-shot identity, audio matching or large-library acceptance. One sampled point does not define clip duration.\n')
            write(path,text)
    cases=ROOT/'docs/product/CASES.md'
    text=cases.read_text('utf8')+'\n\n<a id="c14-semantic-retrieval"></a>\n\n## C14：检索候选 → 可编辑成片 / Retrieval to editable output\n\n'+CONFIG['README.md']['case']+'\n\n'+CONFIG['README.en.md']['case']+'''\n\n
![Actual installed output](../assets/semantic-20261025-r1/demo-installed-r1-workflow/semantic-cut.gif)

| 输入/输出 / Artifact | 路径 / Evidence |
|---|---|
| 原序列 / Original sequence | [6s/72-frame input MP4](../assets/semantic-20261025-r1/asset_v1.mp4) · [image sources/licenses](../assets/semantic-20261025-r1/SOURCE.json) · [notices](../assets/semantic-20261025-r1/NOTICE.txt) |
| 实际安装版输出 / Installed output | [MP4](../assets/semantic-20261025-r1/demo-installed-r1-workflow/semantic-cut.mp4) · [candidate/output board](../assets/semantic-20261025-r1/demo-installed-r1-workflow/candidate-to-output.png) |
| 可编辑内容 / Editable delivery | [project package](../assets/semantic-20261025-r1/demo-installed-r1-workflow/editable-project.aevpkg.zip) · [actual selected hits/ranks](../assets/semantic-20261025-r1/demo-installed-r1-workflow/selected-hits.json) |
| 原始响应与逐帧校验 / CLI and decode | [11 calls](../validation/evidence/semantic-20261025-r1/demo-installed-r1-workflow/calls.json) · [verification](../validation/evidence/semantic-20261025-r1/installed-r1/demo/verification.json) |
| 不筛掉的失败 / All query failures retained | [all 20 results](../assets/semantic-20261025-r1/all-query-results.png) · [full scoring](../validation/evidence/semantic-20261025-r1/skill-r1/quality.json) |

复现 / Reproduce: `scripts/verify_semantic_20261025.py --run <new-run> --phase setup --installed <installed>`，
同一新 run 运行 index，再以实际查询响应执行 `--phase demo --demo-response <actual-response.json>`。
不要重用已有输出目录。完整生成器与原始命令以对应 evidence 下的 executed-generator.py/calls.json 为准。
发布门禁未执行；NASA 形象不作产品背书。静态查看、自动解码、连续人工播放和听审分别记录。
'''
    write(cases,text)
    plan=ROOT/'docs/product/IMPLEMENTATION_PLAN_20261025.md';text=plan.read_text('utf8')
    text=replace_row(text,'W05 内容与广告生产','| W05 内容与广告生产 | G06–G07、G25–G29 | 效果/模板/运镜/开源媒体库，语义检索，音乐/音效生成和匹配，真实 brief 的混剪与返工 | G26 有限检索已随 CLI 0.1.5 安装及单一 Skill 交付：实际 CPU/GPU、20 条冻结查询、预览/源时间、可编辑成片往返。中文否定与库外拒识仍失败；自然动作/身份/音频/推荐、大库与模型复用继续开放。其余 W05 待执行，500 LUT 与 359 资源不作为质量完成率 |')
    text+='\n\n2026-10-25 本轮 G26 [实际交付](../validation/离线语义检索实测_2026-10-25.md)：CLI 0.1.5 / local.3，单一 Skill 17 模块；开发版和安装版证据分开。新增能力是有限的采样画面检索，不关闭完整 G26、G27、G32 或其他差距组。上面的 03:55/04:38 记录是当时历史状态，原始响应未修改。\n'
    write(plan,text)
    # Preserve all G01-G38 rows, changing G26 only with the actual new evidence.
    gap=ROOT/'docs/product/GOAL_GAPS_20261025.md';text=gap.read_text('utf8')
    old_gap_rows=re.findall(r'^\| G\d\d \|.*$',text,re.M)
    text=text.replace('本次于 2026-10-25 04:38（台北）重新通过真实注册入口核对安装版，38 组均仍有未关闭条件；','本轮又交付有限图文语义检索，并通过真实注册入口核对 CLI 0.1.5；38 组均仍有未关闭条件；',1)
    a=text.index('## 版本与核对范围');b=text.index('## 如何判断距离目标还有多远')
    text=text[:a]+'''## 版本与核对范围

| 项目 | 本次确认的状态 | 证据与边界 |
|---|---|---|
| 本地已安装包 | `v0.1.0-alpha.4-local.3` / CLI `0.1.5` | 固定 8-wheel 原生包，全部产品 Python 源字节对照；[安装与摘要](COMMUNITY_LOCAL_DELIVERY.md) |
| 公开发行 | `v0.1.0-alpha.3` 预发布 / CLI `0.1.2` | 本轮未发布新标签、未覆盖旧附件；[公开发行页](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v0.1.0-alpha.3) |
| 当前入口 | 1 个 `$agent-ffmpeg-local-editor`，17 内部模块 | K08 增加检索说明；固定调用安装版，不静默回退源码 |
| 实际入口核对 | 9 次 CLI：version、doctor、capabilities、schema、gpu、model-pack、index-list、GPU 批量文本、CPU 参考图 | [真实统一入口](../validation/evidence/semantic-20261025-r1/skill-r1/verification.json)；与开发源测试分开 |
| 当前能力声明 | 73 项：20 implemented、45 implemented_with_limits、7 local_adapter_only、1 degraded | [实际安装版响应](semantic-capabilities-cli-0.1.5.json)，新增 visual_semantic_retrieval；不是整体完成率 |
| 真实语义执行 | 开发 GPU 索引＋5 次搜索共 13 次模型前向；安装版另 GPU 索引/文本与 CPU 图像 | 16 正向查询 CPU/GPU top-1、mean recall@3 均 1.0，6 个合成静态序列时间点通过；中文否定与库外拒识失败保留；[完整实测](../validation/离线语义检索实测_2026-10-25.md) |
| 实际可编辑案例 | 开发与安装版各 11 次 CLI，3 秒/90 帧，包往返解码画面一致 | [实际 MP4/GIF/工程](CASES.md#c14-semantic-retrieval)；静态图序列，不代表自然动作、完整广告质量或人工听审 |
| 回归与异常 | 开发 25 项契约、安装版另 25；122 CLI、34 离线策略分别通过；实际异常/取消通过 | 测试有重叠，不累加；取消仅在 worker 启动/完整性阶段实测，历史 2,930 项未重跑 |
| 上轮历史 | CLI 0.1.4 / 72 项声明，另列开发候选 | [04:38 只读复核](../validation/evidence/goal-gaps-20261025-r3/inventory.json)和[候选边界](../validation/evidence/goal-gaps-20261025-r3/review.json)原样保留；当时未交付检索的结论不作为当前状态 |

'''+text[b:]
    text=text.replace('本地 CLI 0.1.4 可用；公开 alpha.3 仍为 CLI 0.1.2，开发候选另列','本地 CLI 0.1.5 可用；公开 alpha.3 仍为 CLI 0.1.2，SigLIP2 原生环境/权重需另供')
    text=replace_row(text,'G26','| G26 | 素材语义搜索与推荐 | CLI 0.1.5 已安装离线图文向量索引/中文英文参考图检索、预览/源时间/可编辑引用；实际 CPU/GPU、统一 Skill 和工程往返通过 | 小型常见静态图集不证明自然动作/跨镜头身份；中文否定错选咖啡、2 条库外仍返回草地；缺可靠拒识、音频 embedding/配乐推荐、长库性能与常驻复用 | 冻结扩展授权语料及独立相关性/动作/身份/音频标注；修复原失败与库外校准，安装/Skill/手册一致，原定完整推荐范围逐项通过 | 随后建设 |')
    assert len(re.findall(r'^\| G\d\d \|',text,re.M))==38
    assert all(r in text for r in old_gap_rows if not r.startswith('| G26 |'))
    a=text.index('## 实测来源与本轮边界')
    text=text[:a]+'''## 实测来源与本轮边界

当前状态依据[CLI 0.1.5 真实统一入口](../validation/evidence/semantic-20261025-r1/skill-r1/verification.json)、
[安装字节核对](../validation/evidence/semantic-20261025-r1/installation/verification.json)、
[完整新执行](../validation/离线语义检索实测_2026-10-25.md)和[可编辑案例](CASES.md#c14-semantic-retrieval)。
新功能与模型执行不与上轮只读调用、历史 2,930 项回归或社区配音/翻译测试相加。
所有查询保留，包括中文否定和库外失败；常见静态图片可能曾用于训练。没有自然动作、
独立 Agent benchmark、干净第二物理主机、连续人工视听或完整剪映等价的新验收结论。

历史只读复核和当时开发候选的原始响应保留在
[首轮](../validation/evidence/goal-gaps-20261025-r1/inventory.json)、
[第二轮](../validation/evidence/goal-gaps-20261025-r2/inventory.json)、
[第三轮](../validation/evidence/goal-gaps-20261025-r3/inventory.json)。
既有配音/翻译、声道、采集、Qwen 对齐失败分别见[扩展验收](COMMUNITY_ACCEPTANCE.md)与
[首批补齐实测](../validation/补齐实施首批实测_2026-10-25.md)，原门槛和失败未撤销。
本轮原生 Windows 执行，没有 Docker/WSL/虚拟环境，也未打开浏览器 UI。

English: local CLI 0.1.5 / alpha.4-local.3 now delivers limited visual semantic retrieval
through one registered Skill (17 modules), with 73 declarations (20 implemented,
45 limited, seven adapter-only, one degraded). Public alpha.3 remains CLI 0.1.2.
Actual CPU/GPU retrieval and editable package roundtrips pass their bounded tests;
Chinese negation and both out-of-domain queries retain failures. All 38 gap groups
remain open. No total completion percentage or full CapCut parity is established.

后续全部工作继续见[完整实施台账](IMPLEMENTATION_PLAN_20261025.md)。
'''
    write(gap,text)
    center=ROOT/'docs/README.md';text=center.read_text('utf8')
    text=text.replace('CLI 0.1.4','CLI 0.1.5').replace('v0.1.0-alpha.4-local.2','v0.1.0-alpha.4-local.3')
    text+=('\n- [CLI 0.1.5 离线图文检索：登记、索引、中文/英文/参考图、GPU 与可编辑复用](product/SEMANTIC_RETRIEVAL.md)\n'+
        '- [实际 20 条查询、保留失败、原生安装与单一 Skill/成片核验](validation/离线语义检索实测_2026-10-25.md)\n')
    text=text.replace(' · [另行开发的 GPU 索引](validation/evidence/goal-gaps-20261025-r3/candidate-progress.json)',
        ' · [当前实际 Skill 检索](validation/evidence/semantic-20261025-r1/skill-r1/verification.json)')
    write(center,text)
    receipt=BASE/'documentation-update.json'
    assert not receipt.exists()
    write(receipt,json.dumps(dict(status='updated',readmes=evidence_rows,all_G01_G38_preserved=True,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='documentation_updated',readmes=3,historical_rows_preserved=44,gap_groups=38)),flush=True)


if __name__=='__main__':main()
