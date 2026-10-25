"""Document actual editable-ad delivery, preserving all historical evidence and goals."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/ad-storyboard-20261025-r1'
REPORT = 'docs/validation/可编辑广告分镜与返工实测_2026-10-25.md'
PENDING = {}


def read(name):
    return PENDING[name] if name in PENDING else (ROOT/name).read_text('utf-8-sig')


def write(name, value):
    PENDING[name] = value


def rows(text, prefix):
    return {m[1]: m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$', text, re.M)}


def replace_row(text, key, value):
    text, count = re.subn(r'^\| '+key+r'\s*\|.*$', lambda _: value, text, flags=re.M)
    assert count == 1, (key, count)
    return text


def load(name):
    return json.loads((BASE/name).read_bytes())


HEADLINES = (
    '已实现广告 brief→多画幅/时长→独立可编辑轨道→指定镜头返工→工程包迁移。新增 `ad storyboard/build/revise`；同语种 GPU 批量配音保留原文，3 句只初始化一次模型。实际生成竖屏 12 秒、横屏/方形各 9 秒。横屏只改最后 3 秒，前 180 帧与声音 PCM 不变；真实注册 Skill 再次返工通过。',
    '已實作廣告 brief→多畫幅/時長→獨立可編輯軌道→指定鏡頭返工→專案包遷移。新增 `ad storyboard/build/revise`；同語種 GPU 批次配音保留原文，3 句只初始化一次模型。實際生成直式 12 秒、橫式/方形各 9 秒。橫式僅改最後 3 秒，前 180 影格與聲音 PCM 不變；實際註冊 Skill 再次返工通過。',
    'Reviewed ad brief→multiple canvases/durations→separate editable tracks→selected-shot revision→portable project package now runs end to end. New `ad storyboard/build/revise`; same-language GPU voice batches preserve copy and initialize once for three lines. Actual vertical 12s, wide/square 9s variants. Revising only the last 3s preserves the first 180 frames and decoded PCM; the registered Skill repeats a scoped revision.',
)
LIMITS = (
    '调用者明确提供文案与素材选择；本例是自制产品图卡广告，不是自然素材广告质量或 Agent 自主成功率验收。完整目标继续进行。',
    '呼叫者明確提供文案與素材選擇；本例是自製產品圖卡廣告，不是自然素材廣告品質或 Agent 自主成功率驗收。完整目標繼續進行。',
    'Copy and asset choices are explicit caller inputs. This is an authored product-card ad, without natural-ad quality or independent Agent-success acceptance. The full goal remains active.',
)
F52 = (
    '| F52 | 可编辑广告分镜与返工 | 已确认 brief/实际素材 → 多画幅与时长的画面/字幕/配音/源音/配乐独立轨道；按镜头与变体局部改稿。 | `ad storyboard/build/revise` | 整帧分配、原素材字节锁、实际字体排版和完整配音时窗；不自动创造卖点或决定素材语义。 |',
    '| F52 | 可編輯廣告分鏡與返工 | 已確認 brief/實際素材 → 多畫幅與時長的畫面/字幕/配音/源音/配樂獨立軌道；按鏡頭及變體局部改稿。 | `ad storyboard/build/revise` | 整影格分配、原素材位元組鎖、實際字型排版和完整配音時窗；不自動創造賣點或決定素材語義。 |',
    '| F52 | Editable ad storyboards and revision | Reviewed brief/actual assets → separate picture/caption/voice/source/music tracks for multiple canvases/durations; selected-shot/variant revisions. | `ad storyboard/build/revise` | Whole-frame allocation, actual asset locks, real font layout and complete voice-window checks; caller supplies claims and semantic choices. |',
)
F51 = (
    '| F51 | 字幕翻译配音联合流程 | 普通中英 SRT、显式音色/轨道 → 译文或保留同语种原文、完整批量 WAV、实际时窗、可编辑声音/字幕和原子提交。 | `dub subtitles` | 同语种只初始化配音模型；保留原声/重试/错译；cue 时窗不证明字词精度、自然韵律或口型同步。 |',
    '| F51 | 字幕翻譯配音聯合流程 | 普通中英 SRT、明確音色/軌道 → 譯文或保留同語種原文、完整批次 WAV、實際時窗、可編輯聲音/字幕及原子提交。 | `dub subtitles` | 同語種只初始化配音模型；保留原聲/重試/錯譯；cue 時窗不證明字詞精度、自然韻律或口型同步。 |',
    '| F51 | Joint subtitle translation/dubbing | Plain Chinese/English SRT and explicit voices/tracks → translation or preserved same-language copy, complete batched WAV, actual fit, editable audio/captions and atomic application. | `dub subtitles` | Same-language mode initializes only voice; preserves originals/retries/awkward translations; cue fit does not establish word precision, naturalness or lip sync. |',
)
K15 = (
    '| K15 | [`ad-creative`](skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md) | 广告创意、可编辑分镜与变体 | 产品/受众/审核文案/实际资产 → 计划、独立序列与局部返工 | `advisory; ad plan; ad storyboard/build/revise` | 创意选择与卖点证据明确提供；不自带生成视频模型。 |',
    '| K15 | [`ad-creative`](skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md) | 廣告創意、可編輯分鏡與變體 | 產品/受眾/審核文案/實際資產 → 計劃、獨立序列與局部返工 | `advisory; ad plan; ad storyboard/build/revise` | 明確提供創意選擇與賣點證據；不自帶生成影片模型。 |',
    '| K15 | [`ad-creative`](skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md) | Creative planning, editable storyboards and variants | Product/audience/reviewed copy/actual assets → plans, independent sequences and scoped revisions | `advisory; ad plan; ad storyboard/build/revise` | Explicit creative decisions and claim evidence; no bundled video-generation model. |',
)
CHECKS = (
    [('安装包一致性', 'CLI 0.1.14 / local.12；205 产品 Python 文件与固定安装包一致，旧包保留'),
     ('代码与安装回归', '最终源码相关契约 226/226；最终安装专项 55/55；安装 CLI 122/122；分别记录，不相加'),
     ('真实同语种 GPU 配音', '3 句原文保持，CUDA 配音一次初始化/3 次生成，无翻译 worker；完整声音保留本地'),
     ('实际多画幅编码', '竖 12 秒/360 帧、横/方各 9 秒/270 帧；另验 NVENC 270 帧；不宣称全部效果 GPU 化'),
     ('指定镜头返工', '安装版与真实注册 Skill 分别改横屏末镜；前 180 帧/解码 PCM/未选序列/原素材保持'),
     ('可编辑包迁移', '原工程路径不可用后导入，3 序列可编辑，重渲染 RGB/PCM 与修改后原片一致'),
     ('单一 Skill 与工具包', '1 Skill/17 模块、66 Skill 文件；r13 独立中文/空格目录验证，同物理主机'),
     ('交付与失败保留', 'R01–R101 和全部 38 原关闭条件保留；同语种旧拒绝/记录器错误/NVENC 缺码率失败均留档，无自然质量/听审结论')],
    [('安裝包一致性', 'CLI 0.1.14 / local.12；205 產品 Python 檔案與固定安裝包一致，舊包保留'),
     ('程式與安裝回歸', '最終原始碼相關契約 226/226；最終安裝專項 55/55；安裝 CLI 122/122；分別記錄，不相加'),
     ('實際同語種 GPU 配音', '3 句原文保留，CUDA 配音一次初始化/3 次生成，無翻譯 worker；完整聲音保留本機'),
     ('實際多畫幅編碼', '直式 12 秒/360 影格、橫式/方形各 9 秒/270 影格；另驗 NVENC 270 影格；不宣稱全部效果 GPU 化'),
     ('指定鏡頭返工', '安裝版及實際註冊 Skill 分別改橫式末鏡；前 180 影格/解碼 PCM/未選序列/原素材保留'),
     ('可編輯包遷移', '原專案路徑不可用後匯入，3 序列可編輯，重渲染 RGB/PCM 與修改後原片一致'),
     ('單一 Skill 與工具包', '1 Skill/17 模組、66 Skill 檔案；r13 獨立中文/空格目錄驗證，同物理主機'),
     ('交付及失敗保留', 'R01–R101 及全部 38 原結案條件保留；同語種舊拒絕/記錄器錯誤/NVENC 缺碼率失敗均留檔，無自然品質/聽審結論')],
    [('Installed byte identity', 'CLI 0.1.14 / local.12; 205 product Python files match the pinned installation; older bundles retained'),
     ('Code and installed regression', 'Final source contracts 226/226; final installed focused suite 55/55; installed CLI 122/122; separate scopes, not additive'),
     ('Real same-language GPU voice', 'Three original lines retained; one CUDA voice initialization/three generations; no translation worker; complete speech stays local'),
     ('Actual canvas variants', 'Vertical 12s/360 frames, wide/square each 9s/270; separate 270-frame NVENC check; does not imply GPU effects throughout'),
     ('Selected-shot revisions', 'Installed runtime and registered Skill independently revise the last wide shot; first 180 frames/decoded PCM/unselected sequences/original assets retained'),
     ('Editable package migration', 'With the original project unavailable, import retains three editable sequences and reproduces revised RGB/PCM exactly'),
     ('Unified Skill and kit', '1 Skill/17 modules, 66 Skill files; r13 tested in a separate Chinese/space directory on the same physical host'),
     ('Delivery and preserved failures', 'R01–R101 and all 38 original closure conditions retained; old same-language rejection/recorder error/missing NVENC bitrate preserved; no natural-quality/listening acceptance')],
)


def main():
    for phase in ('setup-finalize-r1', 'render-continue-r1', 'revision-r1', 'roundtrip-r1', 'skill-r1', 'media-r1'):
        assert load(phase+'/verification.json')['status'] == 'passed', phase
    assert load('activation-r1/activation-and-registration.json')['status'] == 'passed'
    evidence = ['installation-r2/verification.json', 'tests/installed-r2/verification.json',
        'setup-finalize-r1/verification.json', 'render-continue-r1/verification.json',
        'skill-r1/verification.json', 'roundtrip-r1/verification.json', 'kit-r1/verification.json',
        'final-delivery-r1/verification.json']
    for i, name in enumerate(('README.md', 'README.zh-TW.md', 'README.en.md')):
        text = read(name); old = rows(text, 'R'); assert len(old) == 101
        marker = '<!-- semantic-control-current -->'
        assert marker in text
        block = ('<!-- ad-storyboard-current -->\n\n**CLI 0.1.14 / alpha.4-local.12 / r13 kit** · 205 product Python files · 1 Skill / 17 modules. '+HEADLINES[i]+'\n\n'
            '[Workflow / 使用流程](docs/product/AD_STORYBOARD.md) · [C23 / 原输入与实际输出](docs/product/CASES.md#c23-ad-storyboard) · '
            '[Evidence / 实测与边界]('+REPORT+')\n\n'
            '```powershell\n# Ingest actual assets and prepare the reviewed brief first; use the pinned Skill launcher below.\n'
            '& $avk ad storyboard --project $project --input "$project/brief.json" --output "$project/validation/ad-plan.json" --dry-run\n'
            '& $avk ad storyboard --project $project --input "$project/brief.json" --output "$project/validation/ad-plan.json"\n'
            '& $avk ad build --project $project --input "$project/validation/ad-plan.json"\n'
            '& $avk render --project $project --sequence-id ad_product_wide_sequence --output "$project/renders/wide.mp4"\n'
            '& $avk ad revise --project $project --input "$project/revision.json" --output "$project/validation/revision-1.json"\n'
            '& $avk ad build --project $project --input "$project/validation/revision-1.json"\n```\n\n'
            '![Actual wide ad / silent](docs/assets/ad-storyboard-20261025-r1/wide9.gif)\n\n'+LIMITS[i]+'\n\n<!-- /ad-storyboard-current -->\n\n')
        text = text.replace(marker, block+'<!-- semantic-control-history -->', 1).replace('<!-- /semantic-control-current -->', '<!-- /semantic-control-history -->', 1)
        text = text.replace('**CLI 0.1.13 / alpha.4-local.11 / r12 kit**', '**Historical / 历史 / 歷史：CLI 0.1.13 / alpha.4-local.11 / r12 kit**', 1)
        text = text.replace('[r12 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r12.zip)', '[r13 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r13.zip)', 1)
        lines = []
        for line in text.splitlines():
            if line.startswith(('**本机新增', '**本機新增', '**Local installed extension:')):
                line = line.replace('CLI 0.1.13', 'CLI 0.1.14')
            if line.startswith('**Current delivery /'):
                line = '**Current delivery / 当前交付 / 目前交付（R102–R109，2026-10-25）：** CLI 0.1.14 / local.12 / r13; editable ad variants, scoped revisions, same-language GPU voice and actual package rerender. All original goal conditions remain open.'
            if not re.match(r'^\| R\d{2,3} ', line):
                line = line.replace('v0.1.0-alpha.4-local.11/final-r1/installed', 'v0.1.0-alpha.4-local.12/final-r2/installed')
                if 'final-r2/installed' in line or '当前完整目标差距表' in line or '目前完整目標差距表' in line or 'current full-goal gap' in line.lower():
                    line = line.replace('CLI 0.1.13', 'CLI 0.1.14')
            line = line.replace('F44–F51', 'F44–F52')
            lines.append(line)
        text = '\n'.join(lines)+'\n'
        text = text.replace('同步校验可能延迟超时。', '当前完整性读取已响应超时/取消；其他 worker/OS 阻塞 I/O 仍有边界。')
        text = text.replace('同步校驗可能延遲逾時。', '目前完整性讀取已回應逾時/取消；其他 worker/OS 阻塞 I/O 仍有邊界。')
        text = text.replace('synchronous checks may delay deadlines.', 'current integrity reads observe deadlines/cancellation; other workers/OS blocking I/O retain limits.')
        text = replace_row(text, 'F51', F51[i])
        text = text.replace(F51[i], F51[i]+'\n'+F52[i], 1)
        text = replace_row(text, 'K15', K15[i])
        addition = '\n'.join(f'| R{102+n} | {title} | {detail} | [2026-10-25 evidence](docs/validation/evidence/ad-storyboard-20261025-r1/{ev}) · [Scope]({REPORT}) |'
            for n, ((title, detail), ev) in enumerate(zip(CHECKS[i], evidence, strict=True)))
        text = text.replace(rows(text, 'R')['R101'], rows(text, 'R')['R101']+'\n'+addition, 1)
        assert all(rows(text, 'R')[key] == value for key, value in old.items())
        assert len(rows(text, 'R')) == 109 and len(rows(text, 'F')) == 52
        write(name, text)
        # Current Skill manual summaries follow the same K15 contract.
        skill_name = 'docs/product/SKILLS'+('', '.zh-TW', '.en')[i]+'.md'
        st = read(skill_name)
        start, end = st.index('<!-- community-current -->'), st.index('<!-- /community-current -->')
        current = ('<!-- community-current -->\n\n**CLI 0.1.14 / alpha.4-local.12 / r13 kit · 1 Skill / 17 modules.**\n\n'+HEADLINES[i]+'\n\n'
            '[Editable ad workflow](AD_STORYBOARD.md) · [Same-language/translated dubbing](SUBTITLE_DUBBING.md) · '
            '[75 declarations](ad-storyboard-capabilities-cli-0.1.14.json) · [Current delivery](COMMUNITY_LOCAL_DELIVERY.md) · '
            '[All original goal conditions](GOAL_GAPS_20261025.md).\n\n'+LIMITS[i]+'\n\n')
        st = st[:start]+current+st[end:]
        st = replace_row(st, 'K15', K15[i].replace('(skills/', '(../../skills/'))
        write(skill_name, st)
        cap_name = 'docs/product/CAPABILITIES'+('', '.zh-TW', '.en')[i]+'.md'
        ct = read(cap_name)
        first_end = ct.index('<!-- /community-current -->')
        head = ct[:first_end].replace('CLI 0.1.13 / alpha.4-local.11', 'CLI 0.1.14 / alpha.4-local.12 / r13 kit')
        head = head.replace('semantic-control-capabilities-cli-0.1.13.json', 'ad-storyboard-capabilities-cli-0.1.14.json')
        ct = head+ct[first_end:]
        ct = ct.replace('[Machine response](semantic-control-capabilities-cli-0.1.13.json)', '[Machine response](ad-storyboard-capabilities-cli-0.1.14.json)', 1)
        write(cap_name, ct)
    finish_goals()
    finish_case_report()
    for name, value in PENDING.items():
        (ROOT/name).write_text(value, encoding='utf8', newline='\n')
    print(json.dumps(dict(status='documented', files=len(PENDING), preserved_goal_conditions=38, historical_readme_rows=101, current_readme_rows=109)))


def finish_goals():
    name = 'docs/product/GOAL_GAPS_20261025.md'; text = read(name); old = rows(text, 'G')
    start = text.index('2026-10-25 当前本地交付为 **CLI'); end = text.index('\n\n', start)
    historical = text[start:end].replace('当前本地交付', '历史 local.11 交付', 1).replace('本批真实实测', '上一批真实实测', 1)
    current = ('2026-10-25 当前本地交付为 **CLI 0.1.14 / alpha.4-local.12 / r13 kit**，205 个产品 Python 文件与安装版一致。'
        '新增可编辑广告分镜、多画幅/时长、指定镜头返工和保留原文的 GPU 批量配音；'
        '[实际 3 变体、局部返工、工程往返和注册 Skill](../validation/可编辑广告分镜与返工实测_2026-10-25.md)。'
        '调用者明确选择素材/文案，未宣称自然广告质量或自主成功率；全部 38 原关闭条件保持。')
    text = text[:start]+current+'\n\n'+historical+text[end:]
    text = replace_row(text, 'V01', '| V01 | 当前已安装与注册 | local.12 / CLI 0.1.14，1 Skill/17 模块、r13 kit；[205 文件固定安装](../validation/evidence/ad-storyboard-20261025-r1/installation-r2/verification.json)，旧包保留 |')
    text = replace_row(text, 'V03', '| V03 | 能力声明 | 75 项：20 implemented、47 implemented_with_limits、7 local_adapter_only、1 degraded；[当前全部字段](ad-storyboard-capabilities-cli-0.1.14.json)，广告契约扩入 ai 字段；不换算完成率 |')
    text = text.replace(rows(text, 'V')['V19'], rows(text, 'V')['V19']+'\n| V20 | CLI 0.1.14 广告生产 | [真实分镜/同语种 GPU 配音/三画幅/局部返工/包迁移/Skill](../validation/可编辑广告分镜与返工实测_2026-10-25.md)；自制产品图卡单例，真实失败保留，自然质量/独立 Agent 任务集未验收 |', 1)
    text = text.replace(rows(text, 'A')['A15'], rows(text, 'A')['A15']+'\n| A16 | CLI 0.1.14 审核 brief→实际素材→独立可编辑轨道→三画幅/时长→指定镜头返工→可编辑包与真实 Skill | 整帧/字体/完整声音/实际素材锁和原子提交；创意选择由调用者提供，G27 原自然任务集/质量与自主条件继续开放 |', 1)
    changes = {
        'G02': (' 多轨/序列/嵌套与可编辑广告变体；每变体独立画面/字幕/配音/源音/配乐轨 ', ' 本批 3 画幅/时长及局部返工通过；复杂嵌套/时钟/效果组合的完整工程集继续开放 '),
        'G19': (' 中英翻译/完整配音与可编辑入轨；新增同语种保持原文、仅一次 GPU voice 初始化/三句实际生成 ', ' 错译历史保留；多语、自然韵律/发音/情绪、字词精度、声音权利和口型仍未完整验收 '),
        'G27': (' 新增 ad storyboard/build/revise；3 可编辑画幅/时长、GPU 完整配音、指定末镜返工和包迁移已实际执行 ', ' 调用者给出素材/审核文案；仅自制产品图卡案例，固定自然 brief 集、语义选材/叙事/美感/权利与自主返工稳定性仍开放 '),
        'G29': (' 现有变量模板/片段组；新增多画幅时长的广告分镜和逐镜头覆盖、返工 ', ' 行业/玩法/复杂动态的可用授权模板库、变体质量及稳定复用任务集仍缺 '),
        'G32': (' GPU 配音/翻译、批内复用、可中断校验；本批 CUDA 配音一次初始化/3 句，另验 270 帧 NVENC ', ' 编码不代表滤镜/字幕 GPU；本批不同 CPU/GPU 编码参数不比较加速比。模型仍逐命令加载，4K/长片/多设备/全进程资源预算与常驻仍缺 '),
        'G35': (' 单一 Skill 路由/固定包；本批真实已注册入口导入、指定镜头返工、渲染验证 ', ' 脚本执行 Skill 不等于独立 Agent 从自然任务自行决策成功；独立任务集、错误恢复和人类选型完整验收仍缺 '),
        'G38': (' 公开 alpha.3 / CLI 0.1.2 保留；本地 local.12 / CLI 0.1.14 / r13 已安装注册核验 ', ' 本地扩展尚无匹配公开新版 Release；旧标签/附件不覆盖，完整正式门禁未过 '),
    }
    for key, (have, gap) in changes.items():
        cells = rows(text, 'G')[key].split('|'); cells[3:5] = [have, gap]
        text = replace_row(text, key, '|'.join(cells))
    assert len(rows(text, 'G')) == 38
    assert all(rows(text, 'G')[key].split('|')[5].strip() == value.split('|')[5].strip() for key, value in old.items())
    text = replace_row(text, 'D01', '| D01 | 当前可直接使用 | CLI 0.1.14 / local.12 / r13，固定安装 205 文件，1 Skill/17 模块；旧版本保留 |')
    text = replace_row(text, 'D02', '| D02 | 本批契约与回归 | 最终源码相关契约 226/226、安装专项 55/55、安装 CLI 122/122，0 skip；范围分别记录，不相加，历史全量未重跑 |')
    text += '\nCLI 0.1.14 [可编辑广告主链路实测](../validation/可编辑广告分镜与返工实测_2026-10-25.md)推进 G02/G19/G27/G29/G32/G35。完整性超时修复属于上一批真实记录，未重算；38 个原关闭条件逐字保留，完整目标继续进行。\n'
    write(name, text)
    name = 'docs/product/IMPLEMENTATION_PLAN_20261025.md'; text = read(name)
    start = text.index('当前交付为 **CLI'); end = text.index('\n\n', start)
    text = text[:start]+'当前交付为 **CLI 0.1.14 / alpha.4-local.12 / r13 kit**；[可编辑广告实际交付](../validation/可编辑广告分镜与返工实测_2026-10-25.md)。审核 brief、明确素材、三画幅/时长、完整 GPU 配音、指定镜头返工及工程包闭环已实现；全部原关闭条件保持。下文旧版本为历史。'+text[end:]
    w = {
        'W03': ' 已实现普通独立序列/五轨广告变体与局部改稿；实际 3 画幅、整帧时长、前 180 帧/PCM 保留。复杂编辑组合仍推进 ',
        'W04': ' 新增同语种原文 GPU 批量配音，一次初始化/三次实际生成，不经翻译；原错译和自然质量/高级 AI 条件保留 ',
        'W05': ' 新广告分镜/变体/返工/实际渲染/工程包链路交付；调用者确定文案/素材。自然广告任务集、语义选材与内容生态继续推进 ',
        'W07': ' 本批真实 CUDA voice batch 和 270 帧 NVENC 通过；参数不同不报加速比，滤镜/字幕仍 CPU；常驻、4K/长片与资源预算开放 ',
        'W08': ' 新广告计划拒绝陈旧/篡改/改动素材，原子提交与取消/模拟写后回滚有契约；实际注册 Skill 返工通过，独立 Agent 任务集/自然质量及其他恢复边界开放 ',
        'W09': ' 当前 CLI 0.1.14 / local.12 / r13 kit 已本地加载；三语 README 同步，公开仍 alpha.3，旧标签/附件保留 ',
    }
    for key, value in w.items():
        match = re.search(r'^\| '+key+r' [^\n]+', text, re.M); assert match
        cells = match[0].split('|'); cells[-2] = value
        text = text[:match.start()]+'|'.join(cells)+text[match.end():]
    text += '\n2026-10-25 CLI 0.1.14：新增两份产品模块和三条广告命令，完整同语种 GPU 批量配音、多画幅独立五轨与按镜头返工。固定包及真实注册 Skill 通过渲染/PCM/工程往返；[本批实测及保留失败](../validation/可编辑广告分镜与返工实测_2026-10-25.md)。独立 Agent 自主生产、自然视听、内容生态与全部原目标继续进行。\n'
    write(name, text)
    name = 'docs/README.md'; text = read(name)
    text = text.replace('CLI 0.1.13 / alpha.4-local.11 / r12 kit', 'CLI 0.1.14 / alpha.4-local.12 / r13 kit', 1).replace('当前 CLI 0.1.13 的全部', '当前 CLI 0.1.14 的全部', 1)
    text += '\n- [CLI 0.1.14 可编辑广告分镜/多画幅/时长/局部返工](product/AD_STORYBOARD.md) · [实际 GPU/三变体/包迁移/注册 Skill/失败](validation/可编辑广告分镜与返工实测_2026-10-25.md) · [C23 MP4/GIF/原素材](product/CASES.md#c23-ad-storyboard)。\n'
    write(name, text)


def finish_case_report():
    installation = load('installation-r2/verification.json')
    write(REPORT, f'''# 可编辑广告分镜、多画幅与局部返工实测（CLI 0.1.14）

CLI 0.1.14 / alpha.4-local.12 / r13 kit，唯一 `$agent-ffmpeg-local-editor`，17 内部模块。
新增 `ad storyboard`、`ad build`、`ad revise`，以及同语种保持原文的完整 GPU 批量配音。
输入为审核后的 brief、明确的资产 ID 与文案；创意、语义选材和产品主张不是此编译器自动决定。
[完整使用流程/JSON](../product/AD_STORYBOARD.md)、[预先约定的实现/验收契约](../specs/可编辑广告分镜与返工契约_20261025.md)。

产品新增 `ad_storyboard.py` 和 `ad_storyboard_cli.py`；以有理帧率按整帧分配时间，独立生成画面/字幕/配音/源音/配乐轨，实际字体换行/超画布拒绝，完整声音超时窗拒绝。实际素材读锁及 SHA、原工程指纹、计划摘要和重建计划比较共同防止陈旧/任意篡改计划。提交使用现有事务/快照/幂等键；返工只改选择的变体/镜头字段，保留其他序列与手工样式/效果/关键帧。

本例是明确产品 brief：推广 agent editor kit 的原素材保留、逐镜头编辑和多画幅交付。4 套程序自制图卡/运动 MP4 为原始输入，CC0，Noto 字体 OFL，实际资源库音乐保留来源许可；不是 GUI 截图，也不是自然拍摄广告质量基准。[审核 brief](../assets/ad-storyboard-20261025-r1/reviewed-brief.json)、[原始输入与来源](../assets/ad-storyboard-20261025-r1/source/SOURCE.txt)、[实际输出](../product/CASES.md#c23-ad-storyboard)。

同语种 zh-Hans/zh-Hans 保留三句原文，“保留原始素材。”“自由修改每个镜头。”“现在开始本地剪辑。”。实际 RTX 3060 CUDA，Kokoro zf_001，**一次初始化、3 次生成、无翻译 worker**；完整命令约 57.869 秒，包括校验/初始化等，非纯推理耗时。[GPU 原始响应](evidence/ad-storyboard-20261025-r1/setup-continue-r1/gpu-voice-batch.stdout)、[记录器失败后独立复核](evidence/ad-storyboard-20261025-r1/setup-finalize-r1/verification.json)。未确认发布权利的生成声音留在本地，公开只放无声衍生物；未进行人工听审。

实际 CPU 成片：竖屏 360×640 / 12 秒 / 360 帧、横屏 640×360 / 9 秒 / 270 帧、方形 360×360 / 9 秒 / 270 帧，30fps。CPU 三次约 28.894 / 23.599 / 15.152 秒；另行明确码率的 NVENC 横屏 270 帧约 28.445 秒。CPU CRF0 与 GPU 4M 设置不同，且回归并行，**不比较 GPU 加速比**；编码 GPU 不代表字幕/滤镜 GPU。[原 CPU 编码记录](evidence/ad-storyboard-20261025-r1/render-r1/calls.json)、[补充 NVENC 与完整帧复核](evidence/ad-storyboard-20261025-r1/render-continue-r1/verification.json)。

实际安装版只换横屏最后 cta 镜头素材和文字，前 **180 个解码 RGB 帧相同**、末 90 帧改变，完整解码 PCM 字节和 SHA 相同，未选序列 JSON 与全部原资产 SHA 不变。[局部返工](evidence/ad-storyboard-20261025-r1/revision-r1/verification.json)。之后经真实 C 盘发现联接/统一 Skill 再导入、返工和重渲染，8 次实际命令/原生工具调用，同样通过这些条件。[实际 Skill](evidence/ad-storyboard-20261025-r1/skill-r1/verification.json)。这证明实际入口流程，不等于独立 Agent 自主决策成功率。

可编辑包 12,824,413 bytes，SHA `bbeddea9c74adef532f3ef175c1b709dbc41cd139f90e2cd1c6aa6b83253b79b`。
移走原工程后，导入保留 3 序列；横屏重渲染 RGB/PCM 与修改后原片相同。[实际往返](evidence/ad-storyboard-20261025-r1/roundtrip-r1/verification.json)。模型/运行时 pin 仍外部依赖，这是同一物理主机，未宣称干净机器或跨机器验收。

最终源码相关契约 **226/226**、最终安装专项 **55/55**（广告 26、配音 29）、最终安装完整 CLI **122/122**，均 0 skip。三个范围有重叠，不相加，也未重跑历史 2930 项。覆盖帧分配、计划/素材篡改、实际字体边界、手工编辑保留、完整声音、dry-run/幂等、取消、陈旧计划及模拟保存后异常的事务回滚。后者是故障注入契约，不是真实进程崩溃恢复。
[源码 226](evidence/ad-storyboard-20261025-r1/tests/development-r4/verification.json)、[安装 55](evidence/ad-storyboard-20261025-r1/tests/installed-r2/verification.json)、[安装 CLI 122](evidence/ad-storyboard-20261025-r1/tests/installed-cli-r2/verification.json)。

固定本地应用包 **{installation['archive_bytes']} bytes**，SHA `{installation['archive_sha256']}`，manifest `{installation['manifest_sha256']}`；205 产品 Python 文件源码/安装版逐字节一致。[安装证据](evidence/ad-storyboard-20261025-r1/installation-r2/verification.json)。[4 原模型包重新核验/实际注册](evidence/ad-storyboard-20261025-r1/activation-r1/activation-and-registration.json)、[r13 独立中文/空格目录工具包](evidence/ad-storyboard-20261025-r1/kit-r1/verification.json)。旧安装/模型 pin/公开 alpha.3 附件保留。

原失败不改写：初始同语种配音被旧契约拒绝；续跑记录器在生成/分镜/提交实际完成后因未定义 `music` 变量失败，后续独立读取原流并校验完成物；首个 NVENC 请求缺显式码率被正确拒绝，补参数后成功。[setup 原失败](evidence/ad-storyboard-20261025-r1/setup-r1/verification.json)、[记录器失败](evidence/ad-storyboard-20261025-r1/setup-continue-r1/verification.json)、[NVENC 拒绝](evidence/ad-storyboard-20261025-r1/render-r1/verification.json)。早期候选/测试收据仍为当时版本，不计作最终安装测试。

MP4/GIF 均从实际编码视频产生，逐帧解码；3 个 GIF 为 5fps 的 60/45/45 帧，时长 12/9/9 秒。[SHA/尺寸/帧数](../assets/ad-storyboard-20261025-r1/media-manifest.json)。另有不重叠的图册布局，原第一版图册及收据保留。[新图册记录](evidence/ad-storyboard-20261025-r1/media-board-r1/verification.json)。实际静帧检查记录见 [still inspection](evidence/ad-storyboard-20261025-r1/still-inspection-r1/verification.json)；它不代表连续播放或声音听审。

自然素材广告 brief 集、独立 Agent、复杂镜头语义/节奏/叙事、复杂组合/排版、高级 AI、常驻 GPU/资源预算、长片/4K、干净主机和匹配的公开新版 Release 继续开放。单例技术闭环不关闭完整 G27 或任何原目标组。[全部原 38 条件](../product/GOAL_GAPS_20261025.md)、[最终交付核对](evidence/ad-storyboard-20261025-r1/final-delivery-r1/verification.json)。
''')
    name = 'docs/product/CASES.md'; text = read(name)
    text += '''
<a id="c23-ad-storyboard"></a>

## C23：真实广告分镜、三种画幅与只改末镜

推广 agent editor kit 的审核 brief 与 4 套自制动态产品图卡，导入真实字幕字体/资源库音乐，用同语种 CUDA 完整批量配音，编译为三套普通可编辑五轨序列。
[完整 JSON 与使用流程](AD_STORYBOARD.md) · [审核 brief](../assets/ad-storyboard-20261025-r1/reviewed-brief.json) · [原始输入/CC0 与字体来源](../assets/ad-storyboard-20261025-r1/source/SOURCE.txt) · [完整实测及原失败](../validation/可编辑广告分镜与返工实测_2026-10-25.md)。

| 变体 | 实际输出 | GIF | 原输入/静帧 |
|---|---|---|---|
| 9:16 / 12 秒 / 360 帧 / 30fps | [无声 MP4](../assets/ad-storyboard-20261025-r1/vertical12-silent.mp4) | [60 帧 GIF](../assets/ad-storyboard-20261025-r1/vertical12.gif) | [实际静帧](../assets/ad-storyboard-20261025-r1/vertical12.png) |
| 16:9 / 9 秒 / 270 帧 / 30fps | [无声 MP4](../assets/ad-storyboard-20261025-r1/wide9-silent.mp4) | [45 帧 GIF](../assets/ad-storyboard-20261025-r1/wide9.gif) | [实际静帧](../assets/ad-storyboard-20261025-r1/wide9.png) |
| 1:1 / 9 秒 / 270 帧 / 30fps | [无声 MP4](../assets/ad-storyboard-20261025-r1/square9-silent.mp4) | [45 帧 GIF](../assets/ad-storyboard-20261025-r1/square9.gif) | [实际静帧](../assets/ad-storyboard-20261025-r1/square9.png) |

![实际三种画幅静帧，非 GUI 截图](../assets/ad-storyboard-20261025-r1/variants-clear.png)

只替换横屏 cta 镜头和文字：前 180 帧完全一致，末 90 帧改变，解码 PCM/其他两套序列/原资产不变。实际注册 Skill 独立重复返工通过。
[修改前 7.5 秒帧](../assets/ad-storyboard-20261025-r1/revision-before.png) · [修改后同一帧](../assets/ad-storyboard-20261025-r1/revision-after.png) · [安装版证明](../validation/evidence/ad-storyboard-20261025-r1/revision-r1/verification.json) · [真实 Skill](../validation/evidence/ad-storyboard-20261025-r1/skill-r1/verification.json)。

完整声音/分轨/修改后视频在本地 `workspace/ad-storyboard-20261025-installed-r1/original-project-offline/`；可编辑包为该工作目录的 `campaign.aevpkg.zip`，另有 `restored/` 与 `skill-restored/`。原工程不可用时已导入并重渲染，RGB/PCM 相同。公开媒体不含未核验发布权利的生成配音。
这是自制图卡产品广告，非自然广告或独立 Agent 质量基准；程序完整解码、静帧检查、连续播放、人类听审分别记录。当前只有前两者，不宣称后两者。[媒体 SHA/帧数](../assets/ad-storyboard-20261025-r1/media-manifest.json)。
'''
    write(name, text)
    name = 'docs/product/AD_STORYBOARD.md'; text = read(name)
    text += '\n## 实际可复查案例 / Actual case\n\n[C23 的原输入、3 个实际 MP4/GIF、修改前后帧](CASES.md#c23-ad-storyboard) · [完整测试/安装/真实 GPU/Skill/往返与失败](../validation/可编辑广告分镜与返工实测_2026-10-25.md)。图卡为程序自制，非 GUI 截图；声音保留本地，公开为无声衍生物。单例闭环不等于自然广告质量或独立 Agent 自主验收。\n'
    write(name, text)


if __name__ == '__main__':
    main()
