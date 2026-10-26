"""Document measured resident-model behavior while preserving all prior R/G rows."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/model-session-20261027-r1'
BASELINE='18b93ceae20e78ed44fb9d6e6e58ee874cec3c5a'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def load(path):return json.loads(Path(path).read_bytes())
def write(path,text):(ROOT/path).write_text(text,encoding='utf8',newline='\n')
def rows(text,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}
def previous(path):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','show',BASELINE+':'+path],cwd=ROOT).decode('utf-8-sig')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    assert args.run.replace('-','').isalnum();out=BASE/('documentation-'+args.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r3/verification.json');case=load(BASE/'case-r1/verification.json')
    rendered=load(BASE/'render-roundtrip-r2/verification.json');resource=load(BASE/'resources-r1/verification.json')
    assert install['status']=='installed-and-byte-verified' and install['source_file_count']==230
    assert case['status']=='passed_actual_cuda_resident_reuse_and_cancel' and len(case['jobs'])==3 and all(c['ok'] for c in case['checks'])
    assert rendered['status']=='passed' and rendered['registered_skill'] and rendered['decoded_equal_frames']==128
    assert resource['status']=='completed'
    tests={}
    for group,path,count in [('session','session-installed-r2',19),('generation','generation-installed-r2',14),('vace','vace-installed-r3',161),('legacy','legacy-installed-r2',192)]:
        value=load(BASE/path/'verification.json');assert value['status']=='passed' and value['tests']==count and value['frozen_equal']
        tests[group]=count
    startup=case['session_start']['startup_seconds'];cold=case['cold_cli_seconds'];warm=case['warm_cli_seconds'];ratio=case['cold_to_warm_replay_ratio']
    descriptions={
        '':f'新增原生 GPU 模型会话：显式启动、查询、停止，连续生成复用权重和同一提示词嵌入；每个任务重置调度器、前窗上下文与统计。实际同机首条生成 {cold:.2f} 秒，后两条 {warm[0]:.2f}/{warm[1]:.2f} 秒；会话全模型校验另计 {startup:.2f} 秒。相同 seed 的 17 帧逐像素相同，实际去噪取消可回滚并退出所属进程。',
        '.zh-TW':f'新增原生 GPU 模型會話：明確啟動、查詢、停止，連續生成重用權重與同一提示詞嵌入；每個任務重設 scheduler、前窗上下文及統計。實際同機首條生成 {cold:.2f} 秒，後兩條 {warm[0]:.2f}/{warm[1]:.2f} 秒；會話全模型校驗另計 {startup:.2f} 秒。相同 seed 的 17 幀逐像素一致，實際去噪取消可回滾並退出所屬行程。',
        '.en':f'Explicit native GPU sessions add start/status/stop and reuse weights plus the same prompt embeddings. Scheduler, prior-frame context and metrics reset per job. This host measured {cold:.2f}s for the first generation and {warm[0]:.2f}/{warm[1]:.2f}s for the next two; session-wide model verification adds {startup:.2f}s separately. Same-seed replay matches all 17 decoded frames. Cancellation during real denoising rolls back and exits only the owned process.'}
    limits={
        '':'这是单机单次冷热观测，首次登记/完整校验/加载成本全部保留；更换正负提示词或 token 预算须新建会话，只允许串行任务。自然质量、模型与输出权利、总进程 RAM/VRAM 配额、多 GPU 和完整剪映等价仍未验收；静态检查已发现生成中间帧彩边、背景块状伪影和异常碎片；实际模型视频/GIF与工程包保留本机。下图仅展示实际耗时数据。',
        '.zh-TW':'這是單機單次冷熱觀測，首次登記/完整校驗/載入成本全部保留；更換正負提示詞或 token 預算須新建會話，僅允許串行任務。自然品質、模型與輸出權利、總行程 RAM/VRAM 配額、多 GPU 及完整剪映等價仍未驗收；靜態檢查已發現生成中間幀彩邊、背景塊狀偽影與異常碎片；實際模型影片/GIF與工程包保留本機。下圖僅展示實際耗時資料。',
        '.en':'These are single observations on one host, with registration, full verification and first-load costs retained. A new prompt pair/token budget requires a new session; jobs are serial. Natural quality, model/output rights, total process RAM/VRAM quotas, multi-GPU support and full CapCut equivalence remain unaccepted. Static review found colored edges, block-like backgrounds and a stray fragment in generated interiors. Actual videos/GIFs/packages stay local. The chart shows measured timing data only.'}
    f62={
        '':'| F62 | 原生GPU模型会话 | 同工程/适配器/提示词复用权重与嵌入；每任务重置，活连接传递持锁摘要；取消、期限、空闲及任务数退出。 | `media model-session; media generate --model-session` | 原生Windows VACE；首条仍载入；新提示词须新会话，串行执行；非全局显存预留/多GPU。 |',
        '.zh-TW':'| F62 | 原生GPU模型會話 | 同工程/適配器/提示詞重用權重與嵌入；每任務重設，活連線傳遞持鎖雜湊；取消、期限、閒置及任務數退出。 | `media model-session; media generate --model-session` | 原生Windows VACE；首條仍載入；新提示詞須新會話，串行執行；非全域顯存預留/多GPU。 |',
        '.en':'| F62 | Native GPU model sessions | Reuse weights/embeddings per project/adapter/prompt; reset jobs, transfer live locked digests, retire on cancel/deadline/idle/job budget. | `media model-session; media generate --model-session` | Native Windows VACE; first job still loads; new prompt needs a new serial session; no global VRAM reservation/multi-GPU. |'}
    s21={
        '':'| S21 | 本地GPU常驻推理会话 | 原生进程、认证Windows命名管道、JSON/原始帧、重叠拒写锁和生命周期看门狗。 | 已有本地VACE适配器；同一提示词多方案。 | `media model-session start/status/stop` | 不开放网络端口；同工程串行，首条加载及其他模型复用仍有限。 |',
        '.zh-TW':'| S21 | 本地GPU常駐推理會話 | 原生行程、認證Windows命名管道、JSON/原始幀、重疊拒寫鎖與生命週期監控。 | 既有本地VACE適配器；同一提示詞多方案。 | `media model-session start/status/stop` | 不開放網路埠；同工程串行，首條載入與其他模型重用仍有限。 |',
        '.en':'| S21 | Local resident GPU inference session | Native process, authenticated Windows named pipe, JSON/raw frames, overlapping deny-write locks and lifecycle watchdog. | Existing local VACE adapter, repeated variants of one prompt. | `media model-session start/status/stop` | No network port; serial per project; initial loading and reuse of other models remain limited. |'}
    entries={
        '':[
            'CLI0.1.34/local.32：230产品文件/schema与固定安装包一致；安装版会话/读锁19、生成14、VACE/修复/恢复161、旧流程192通过，分组保留，不合并宣传等价。',
            f'C44实际CUDA连续3任务，51个RGBA帧独立解码；同seed重放17帧像素相同，权重/文字编码器各加载一次。首次生成{cold:.2f}s、复用{warm[0]:.2f}/{warm[1]:.2f}s，全量校验{startup:.2f}s另计，非多轮基准。',
            '真实去噪启动后取消，项目/权利文件逐字节回滚、无未完成资产、所属会话退出；原生worker RAM与整卡显存抽样分开记，非全进程硬配额。',
            '已注册统一Skill渲染原/迁移工程，全部128个30FPS帧解码一致；51个12FPS源帧、作者4.25秒与编码128/30秒分开记录；实际GIF/包保留本机。',
            '一个入口/17内部模块/75 Skill文件；r35 kit116文件，独立目录解包/登记/当前声明/帮助/旧图渲染计划与包校验超时保护，未改变真实发现目录。',
            '三语62功能/21服务/75声明、完整流程、C44/实测/版本摘要与Skill同步；235历史R列及38原关闭条件保留；开发失败及未接纳候选单独留证。'],
        '.zh-TW':[
            'CLI0.1.34/local.32：230產品檔案/schema與固定安裝包一致；安裝版會話/讀鎖19、生成14、VACE/修復/恢復161、舊流程192通過，各組分開保留。',
            f'C44實際CUDA連續3任務，51個RGBA幀獨立解碼；同seed重放17幀像素一致，權重/文字編碼器各載入一次。首次生成{cold:.2f}s、重用{warm[0]:.2f}/{warm[1]:.2f}s，全量校驗{startup:.2f}s另計，非多輪基準。',
            '真實去噪啟動後取消，工程/權利檔案逐位元組回滾、無未完成資產、所屬會話退出；原生worker RAM與整卡顯存取樣分開記，非全行程硬配額。',
            '已註冊統一Skill渲染原/遷移工程，全部128個30FPS幀解碼一致；51個12FPS來源幀、作者4.25秒與編碼128/30秒分開記錄；實際GIF/包保留本機。',
            '一個入口/17內部模組/75 Skill檔案；r35 kit116檔案，獨立目錄解包/登記/目前宣告/說明/舊圖渲染計畫與包校驗逾時保護，未改變實際發現目錄。',
            '三語62功能/21服務/75宣告、完整流程、C44/實測/版本雜湊與Skill同步；235歷史R列及38原關閉條件保留；開發失敗與未接納候選分開留證。'],
        '.en':[
            'CLI0.1.34/local.32:230 product files/schema equal the installed bundle. Installed groups pass19 session/locks,14 generation,161 VACE/repair/recovery and192 legacy tests; counts remain separate.',
            f'C44:three real CUDA jobs,51 independently decoded RGBA frames,same-seed17-frame pixel-identical replay and one load each of video/text weights. First CLI{cold:.2f}s,warm{warm[0]:.2f}/{warm[1]:.2f}s,full verification{startup:.2f}s separately; single observations.',
            'Cancellation after actual denoising restores project/rights bytes,publishes no unfinished asset and exits the owned session. Native worker RAM and whole-device VRAM samples are separate; no total-process hard quota claim.',
            'Registered unified Skill renders original/imported projects with128 matching decoded30FPS frames. Source51 frames at12FPS,author4.25s and encoded128/30s are separate. Actual GIFs/packages remain local.',
            'One entry,17 modules,75 Skill files;r35 kit116 files. Isolated unpack/registration/current declarations/help/legacy graph planning and pack-timeout protection pass without changing real discovery.',
            'Full trilingual62 functions/21 services/75 declarations,workflow,C44/evidence/release pins and Skill synchronized.235 historical R rows and38 original closure cells retained; failed development and rejected candidates recorded.']}
    targets=['installation-final-r3/verification.json','case-r1/verification.json','resources-r1/verification.json','render-roundtrip-r2/verification.json','kit-r1/verification.json','development-attempts-r1/verification.json']
    for suffix,name in [('','README.md'),('.zh-TW','README.zh-TW.md'),('.en','README.en.md')]:
        text=(ROOT/name).read_text('utf-8-sig');old=rows(previous(name),'R');assert len(old)==235 and len(rows(text,'R'))==235
        assert 'model-session-current' not in text
        block='<!-- model-session-current -->\n\n**CLI0.1.34 / alpha.4-local.32 / r35 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n'
        block+='```powershell\n$sessionStart = & $avk media model-session start --project $avkProject --adapter-id $vaceAdapterId | ConvertFrom-Json\nif (-not $sessionStart.ok) { throw \'Model session failed to start\' }\ntry {\n  & $avk media generate --project $avkProject --adapter-id $vaceAdapterId `\n    --model-session $sessionStart.data.session_id --asset-id variant-01 `\n    --prompt $reviewedPrompt --width 256 --height 144 --frames 17 --fps 12\n  if ($LASTEXITCODE -ne 0) { throw \'Generation failed\' }\n} finally {\n  & $avk media model-session stop --project $avkProject --session-id $sessionStart.data.session_id\n}\n```\n\n'
        block+='[Workflow / try-finally](docs/product/MODEL_SESSIONS.md) · [C44](docs/product/CASES.md#c44-model-sessions) · [Install](docs/releases/CLI_0.1.34_LOCAL.md) · [Evidence](docs/validation/原生GPU模型常驻实测_2026-10-27.md)\n\n'+limits[suffix]+'\n\n'
        block+='![Measured session timing; not generated model imagery](docs/assets/model-session-20261027-r1/timing.png)\n\n<!-- /model-session-current -->\n\n'
        text=text.replace('<!-- video-generation-current -->',block+'<!-- video-generation-current -->',1)
        text=text.replace('**CLI0.1.33 / alpha.4-local.31 / r34 kit','**Historical / 历史 / 歷史：CLI0.1.33 / alpha.4-local.31 / r34 kit',1)
        for key,value in [('F61',f62[suffix]),('S20',s21[suffix])]:
            match=re.search(r'^\| '+key+r'\s*\|.*$',text,re.M);assert match;text=text[:match.end()]+'\n'+value+text[match.end():]
        match=re.search(r'^\| R235\s*\|.*$',text,re.M);assert match
        additions=['| R'+str(236+i)+' | 2026-10-27 native GPU sessions | '+value+' | [Evidence](docs/validation/evidence/model-session-20261027-r1/'+target+') |' for i,(value,target) in enumerate(zip(entries[suffix],targets))]
        text=text[:match.end()]+'\n'+'\n'.join(additions)+text[match.end():]
        text='\n'.join(line.replace('local.31/final-r1/installed','local.32/final-r3/installed').replace('CLI 0.1.33','CLI 0.1.34')
            if not line.startswith('| R') and 'local.31/final-r1/installed' in line else line for line in text.splitlines())+'\n'
        title={'':'## 完整的 62 个功能模块','.zh-TW':'## 完整的 62 個功能模組','.en':'## All 62 functional modules'}[suffix]
        text=re.sub(r'^## 43 [^\n]+$',lambda _:title,text,count=1,flags=re.M)
        assert len(rows(text,'R'))==241 and all(rows(text,'R')[k]==v for k,v in old.items());write(name,text)
        for folder in ('docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            path=folder+suffix+'.md';link='MODEL_SESSIONS.md' if '/product/' in path else '../product/MODEL_SESSIONS.md'
            block='<!-- community-current -->\n\n**CLI0.1.34 / alpha.4-local.32 / r35 kit · 1 Skill / 17 modules / 75 files.**\n\n'+descriptions[suffix]+'\n\n[Model session workflow]('+link+')\n\n<!-- /community-current -->'
            write(path,re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,(ROOT/path).read_text('utf8'),count=1,flags=re.S))
        path='docs/product/CAPABILITIES'+suffix+'.md';text=(ROOT/path).read_text('utf8')
        text=text.replace('CLI0.1.33 / alpha.4-local.31 / r34 kit','CLI0.1.34 / alpha.4-local.32 / r35 kit').replace('video-generation-capabilities-cli-0.1.33.json','model-session-capabilities-cli-0.1.34.json')
        for key,value in [('F61',f62[suffix]),('S20',s21[suffix])]:
            match=re.search(r'^\| '+key+r'\s*\|.*$',text,re.M);assert match;text=text[:match.end()]+'\n'+value+text[match.end():]
        text=text.replace('<!-- /community-current -->',descriptions[suffix]+'\n\n[Model sessions](MODEL_SESSIONS.md)\n\n<!-- /community-current -->',1)
        caps=load(ROOT/'docs/product/model-session-capabilities-cli-0.1.34.json')['data']['capabilities']
        for key,value in caps.items():
            pattern=r'(### `'+re.escape(key)+r'`\s*\n\n```json\n)(.*?)(\n```)'
            text,n=re.subn(pattern,lambda m:m[1]+json.dumps(value,ensure_ascii=False,indent=2)+m[3],text,count=1,flags=re.S);assert n==1,key
        write(path,text)
    path='docs/product/MODEL_SESSIONS.md';text=(ROOT/path).read_text('utf8')
    text=re.sub(r'当前状态：.*?\n\n',descriptions['']+'\n\n[完整实测、失败与资源证据](../validation/原生GPU模型常驻实测_2026-10-27.md)。\n\n',text,count=1,flags=re.S)
    text+='\n![Measured timing data only](../assets/model-session-20261027-r1/timing.png)\n';write(path,text)
    record='# 原生GPU模型常驻实测 · 2026-10-27\n\n'+descriptions['']+'\n\n'+limits['']+'\n\n'
    record+='[真实命令与完整响应](evidence/model-session-20261027-r1/case-r1/verification.json) · [复现脚本](../../scripts/run_model_session_case_20261027.py) · [原生资源抽样](evidence/model-session-20261027-r1/resources-r1/verification.json) · [实际Skill与工程往返](evidence/model-session-20261027-r1/render-roundtrip-r2/verification.json)\n\n'
    record+='| 阶段 | 实际秒数 | 说明 |\n|---|---:|---|\n'
    registration=next(c['seconds'] for c in case['calls'] if c['name']=='register-vace')
    for name,seconds,note in [('登记',registration,'重建当前代码完整摘要，非生成耗时'),('会话启动',startup,'整模型哈希/锁定，不含首次GPU模型加载'),('首次生成',cold,'包含文字编码器/视频权重加载、推理、编码及命令开销'),('同seed热重放',warm[0],'17帧逐像素一致，单次观测'),('新条件热生成',warm[1],'同提示词，不同seed/条件；自然质量仍未验收')]:record+=f'| {name} | {seconds:.3f} | {note} |\n'
    record+='\n相同宿主的首次/热重放比值为 '+f'{ratio:.3f}×'+'；启动及登记成本另计，不等于多机、多轮、长片或任意提示词的速度保证。\n\n'
    record+='实测安装为 `local.32/final-r2`。长任务中实际发现状态命令被工程写锁阻塞，已在最终安装 `final-r3` 修复：会话控制绕过编辑事务，生成命令继续持有工程写锁。全部229个其他产品文件及完整推理内核逐字节不变，CLI语法树仅新增一项控制命令豁免；真实GPU耗时不冒充修复后的重测。修复后跨进程状态/停止和全部回归在final-r3重跑。[完整差异与前后证据](evidence/model-session-20261027-r1/control-fix-r1/verification.json)。\n\n'
    record+='| 模型任务 | 模式 | CUDA窗口秒数 | Torch峰值bytes | 本机输出 |\n|---|---|---:|---:|---|\n'
    for row in case['jobs']:
        record+=f"| {row['asset_id']} | {row['mode']} | {row['model_execution']['window_seconds'][0]:.3f} | {row['cuda_peak_allocated_bytes']} | `{row['preview']}` |\n"
    record+='\n完整工作集峰值：`'+str(resource['peak_working_set_bytes'])+'` bytes；最大抽样private bytes：`'+str(resource['maximum_sampled_private_bytes'])+'`。仅驻留worker、ready后抽样，不含父进程/FFmpeg总量；整卡显存包括其他应用，不冒充本进程显存。\n\n'
    record+='实际去噪开始后写入取消标记，命令退出8，工程/权利账本逐字节保留、无未完成资产，所属模型会话退出；不停止其他用户GPU进程。修改提示词返回10而保留原会话。完整17帧的同seed重放一致不能证明跨GPU确定性、自然运镜或所有任务都正确。\n\n'
    record+='已静态检查每条第0/4/8/12/16帧：中间帧存在彩色边缘、背景块状伪影，warm-new第4帧瓶口上方出现异常碎片，末帧有彩边失真。这些是真实质量反例，不能按“端点一致/文件可解码”验收自然广告质量。[静态观察原记录](evidence/model-session-20261027-r1/static-review-r1.json)。未进行完整连续播放或人类听审。\n\n'
    record+='已注册Skill在原/迁移工程实际渲染：128帧、30FPS，全部解码RGBA摘要相同；作者时长4.25s，编码时长128/30s，最后不足一显示帧按CFR输出。GIF '+str(rendered['gif_frames'])+' 帧、'+str(rendered['gif_duration_ms'])+'ms，10ms延迟量化。本机GIF：`'+rendered['gif']+'`。模型源视频无声，普通渲染器可生成AAC静音轨；无声音质量/完整播放验收。\n\n'
    record+='安装版分组：会话/文件锁19、生成14、VACE/修复/恢复161、旧流程192；不相加冒充功能等价。原协议测试使用明确标注的合成模型，本C44为真实现有VACE CUDA。\n\n[开发失败与未接受候选](evidence/model-session-20261027-r1/development-attempts-r1/verification.json)保留。模型视频/GIF和可编辑包留在本机，公开内容仅数字证据和自绘CC0条件图。\n'
    record+='\n实际Skill初次调用因旧启动器版本/摘要被拒绝，已更新并重新登记。注册脚本新增实际启动器预检：隔离副本故意使用旧pin时，在创建发现目录或成功回执前拒绝；正确pin和真实登记均通过。[前置核验与最终登记](evidence/model-session-20261027-r1/registration-preflight-r1/verification.json)。\n'
    write('docs/validation/原生GPU模型常驻实测_2026-10-27.md',record)
    path='docs/product/CASES.md';text=(ROOT/path).read_text('utf8');assert 'c44-model-sessions' not in text
    text+='\n<a id="c44-model-sessions"></a>\n\n## C44：原生GPU常驻与冷热重放 / Resident GPU reuse\n\n'+descriptions['']+'\n\n'+limits['']+'\n\n[完整实测/本机视频与GIF](../validation/原生GPU模型常驻实测_2026-10-27.md) · [使用流程](MODEL_SESSIONS.md) · [复现代码](../../scripts/run_model_session_case_20261027.py)\n\n![Actual timing data](../assets/model-session-20261027-r1/timing.png)\n';write(path,text)
    path='docs/releases/CLI_0.1.34_LOCAL.md';text=(ROOT/path).read_text('utf8')
    text=text.replace('已安装本地开发版，230产品文件与源码一致；真实GPU冷热复用/取消实测进行中。Installed local build; real CUDA cold/warm and cancellation acceptance is still running.',descriptions['']+'\n\n'+descriptions['.en'])
    text+='\n安装版19/14/161/192各组通过，230产品文件、75 Skill文件、17模块、r35 kit116文件；[实际完整证据](../validation/原生GPU模型常驻实测_2026-10-27.md)。同提示词串行复用；首条成本及全部38原关闭条件保留。\n';write(path,text)
    for path in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        text=(ROOT/path).read_text('utf8').replace('当前本地 **CLI0.1.33','此前本地 **CLI0.1.33',1);first=text.index('\n')+1
        text=text[:first]+'\n当前本地 **CLI0.1.34 / alpha.4-local.32 / r35 kit**：[原生GPU模型会话](MODEL_SESSIONS.md)实际连续生成/同seed逐帧重放/去噪取消与安装版Skill交付；[冷热成本和资源证据](../validation/原生GPU模型常驻实测_2026-10-27.md)。全部38原关闭条件保留。\n'+text[first:];write(path,text)
    path='docs/product/GOAL_GAPS_20261025.md';text=(ROOT/path).read_text('utf8')
    for key in ('G23','G32','G33','G38'):
        match=re.search(r'^\| '+key+r'\s*\|.*$',text,re.M);cells=match[0].split('|')
        cells[3]+=' CLI0.1.34显式GPU会话/同提示词复用、实际冷热/逐帧重放/取消退出已留证；'
        if key=='G32':cells[4]=cells[4].replace('模型常驻、多厂商/设备','其他模型/多提示词常驻、多厂商/设备')
        if key=='G23':cells[4]=cells[4].replace('冷读取成本','首次冷读取/加载成本')
        if key=='G38':cells[3]=cells[3].replace('local.31-final-r1/CLI0.1.33/r34','local.32-final-r3/CLI0.1.34/r35')
        text=text[:match.start()]+'|'.join(cells)+text[match.end():]
    old=rows(previous(path),'G');current=rows(text,'G');assert len(old)==len(current)==38
    assert all(current[k].split('|')[5]==v.split('|')[5] for k,v in old.items());write(path,text)
    path='docs/product/IMPLEMENTATION_PLAN_20261025.md';text=(ROOT/path).read_text('utf8')
    for key in ('W07','W08','W09'):
        match=re.search(r'^\| '+key+r'[^\n]+$',text,re.M);assert match;cells=match[0].split('|')
        cells[-2]+=' CLI0.1.34原生VACE会话、同提示词复用/独立首次成本/逐帧重放/真实取消和本地r35交付已完成；完整原目标保持。 '
        text=text[:match.start()]+'|'.join(cells)+text[match.end():]
    write(path,text)
    path='docs/README.md';text=(ROOT/path).read_text('utf8').replace('Current local / 当前本地 / 目前本地：**CLI0.1.33','Historical / 历史 / 歷史：**CLI0.1.33',1)
    write(path,text.replace('\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.34 / local.32 / r35 kit** · [Native model sessions](product/MODEL_SESSIONS.md) · [Install](releases/CLI_0.1.34_LOCAL.md) · [C44](product/CASES.md#c44-model-sessions).\n',1))
    (out/'verification.json').write_text(json.dumps(dict(status='documented',historical_R_rows_preserved=235,current_R_rows=241,
        function_rows=62,service_rows=21,skill_modules=17,capability_count=75,original_G_closure_cells_preserved=38,tests=tests),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Documented CLI0.1.34 in three languages, history preserved',flush=True)


if __name__=='__main__':main()
