"""Maintain real motion delivery documentation without removing past evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/motion-pack-20261025-r1'
REPORT='docs/validation/可复用运镜包实测_2026-10-25.md'
GUIDE='docs/product/MOTION_PACKS.md'


def read(name):return (ROOT/name).read_text('utf-8-sig')
def write(name,text):(ROOT/name).write_text(text,encoding='utf8',newline='\n')
def load(name):return json.loads((BASE/name).read_bytes())
def rows(text,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}
def replace_row(text,key,value):
    text,count=re.subn(r'^\| '+key+r'\s*\|.*$',lambda _:value,text,flags=re.M)
    assert count==1,key
    return text


def prepare():
    installation=load('installation-r1/verification.json');assert installation['status']=='installed-and-byte-verified'
    text=read('docs/product/COMMUNITY_LOCAL_DELIVERY.md')
    before,after=text.split('## CLI 0.1.15 当前交付 / Current delivery',1)
    before=before.replace('CLI 0.1.15','CLI 0.1.16').replace('v0.1.0-alpha.4-local.13','v0.1.0-alpha.4-local.14')
    before=before.replace('final-r3/installed','final-r1/installed').replace('candidate-r3/bundle.zip','candidate-r1/bundle.zip')
    before=before.replace('ef6f81fa0bfe9bcf6f453ddbe363c08138771e1ac42f3b63341fe467e296630f',installation['archive_sha256'])
    before=before.replace('sha256:7e159296635268ce15433f90461e934d41eb698d015dccadc73e3278b378db87',installation['manifest_sha256'])
    before=before.replace('unified-skill-r14.zip','unified-skill-r15.zip').replace('package-0.1.15.json','package-0.1.16.json')
    text=before+'## CLI 0.1.15 历史交付 / Historical delivery'+after
    text+='\n## CLI 0.1.16 当前交付 / Current delivery\n\n'+str(installation['archive_bytes'])+' bytes、208 个产品 Python 文件。'
    text+='新增[可复用运镜包](MOTION_PACKS.md)：六套参数化路径、已有关键帧捕获、明确属性冲突和作者时钟、工程包复用。'
    text+='[六套真实 MP4/GIF 与安装/Skill 实测](../validation/可复用运镜包实测_2026-10-25.md)。'
    text+='无模型推理或新依赖；变换仍为 CPU，NVENC 只加速编码。原 local.13/r14 与历史结果保留，全部完整目标继续进行。\n'
    write('docs/product/COMMUNITY_LOCAL_DELIVERY.md',text)
    source=ROOT/'docs/assets/motion-pack-20261025-r1/contact-sheet.png'
    assert source.exists()
    destination=ROOT/'skills/agent-ffmpeg-local-editor/assets/motion-packs/contact-sheet.png'
    assert not destination.exists();destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(source.read_bytes())
    (ROOT/'docs/product/motion-pack-capabilities-cli-0.1.16.json').write_bytes((BASE/'installation-r1/capabilities.stdout.json').read_bytes())


HEADLINES=(
    '新增可复用运镜包：六套参数路径、已有动画捕获、跨时长/画幅复用、明确冲突和作者时钟；结果保留为可编辑关键帧。',
    '新增可復用運鏡包：六套參數路徑、既有動畫擷取、跨時長/畫幅復用、明確衝突及作者時鐘；結果保留為可編輯關鍵影格。',
    'New portable motion packs: six parameterized paths, existing-animation capture, reuse across durations/canvases, explicit conflict handling and authored clocks; results remain editable keyframes.',
)
BOUNDARIES=(
    '每条 4 秒/120 帧；六套 MP4/GIF 均完整解码。原生裁切/嵌套倒放、捕获复用、工程包和真实 Skill 的逐帧对照通过。空间路径为 65 点折线；带旋转样例耗时约 65 秒，CPU 合成性能/自然素材与主体跟随仍待补齐。',
    '每條 4 秒/120 影格；六套 MP4/GIF 均完整解碼。原生裁切/巢狀倒放、擷取復用、專案包及實際 Skill 的逐影格對照通過。空間路徑為 65 點折線；含旋轉樣例耗時約 65 秒，CPU 合成效能/自然素材及主體跟隨仍待補齊。',
    'Each preview is four seconds/120 frames; all six MP4/GIF files decode. Native trim/nested-reverse, captured reuse, project-package and registered-Skill pixel checks pass. Paths use 65-point polylines; the rotating example took about 65 seconds. CPU composition performance, natural footage and subject-follow combinations remain open.',
)
F54=(
    '| F54 | 可复用参数运镜 | 本地版本化 JSON / 已有作者曲线 → 普通关键帧、参数/摘要/快照、跨工程复用。六套真实预览供选型。 | `motion pack list/inspect/create/capture/apply` | 65 点采样、transform 属性；默认拒绝冲突，显式替换整条属性轨；跟踪绑定拒绝，CPU 合成/自然质量未闭。 |',
    '| F54 | 可復用參數運鏡 | 本地版本化 JSON / 既有作者曲線 → 一般關鍵影格、參數/摘要/快照、跨專案復用。六套實際預覽供選型。 | `motion pack list/inspect/create/capture/apply` | 65 點採樣、transform 屬性；預設拒絕衝突，明確取代整條屬性軌；跟蹤綁定拒絕，CPU 合成/自然品質未結案。 |',
    '| F54 | Portable parameterized motion | Versioned local JSON / captured authored curves → editable keys, resolved parameters/digests/snapshot and cross-project reuse, with six actual previews. | `motion pack list/inspect/create/capture/apply` | 65-point paths, transform properties; conflicts reject unless whole-property replacement is explicit; tracking bindings reject; CPU performance/natural quality remain open. |',
)
CHECKS=(
    [('固定安装','CLI 0.1.16 / local.14，208 产品文件与固定 ZIP 安装版逐字节一致'),
     ('新增契约与原生像素','源码/安装契约各 20/20、原生像素各 5/5，0 skip；范围分开，非完成率'),
     ('真实运镜预览','7 条原生渲染含原图对照，另产品 NVENC 120 帧；六套 4 秒 MP4/GIF、实际源/参数/哈希；带旋转样例约 65 秒'),
     ('捕获复用与工程包','外部包及原工程不可用后，捕获复用/导入工程各 120 帧与原结果相同，JSON/资产保持'),
     ('真实注册 Skill','唯一入口 dry-run、正式 apply、render、validate 通过；120 帧与基准相同，17 模块保持'),
     ('保留失败与回归','122/122 安装 CLI 回归；首轮夹具漏源时码、演示脚本传入不支持的 canvas.background 两条失败保留'),
     ('本地加载与三语文档','r15 kit/参数/预览/功能手册同步；R01–R117 与 38 原关闭条件保留，公开旧附件不覆盖')],
    [('固定安裝','CLI 0.1.16 / local.14，208 產品檔案與固定 ZIP 安裝版逐位元組一致'),
     ('新增契約及原生像素','原始碼/安裝契約各 20/20、原生像素各 5/5，0 skip；範圍分開，非完成率'),
     ('實際運鏡預覽','7 條原生渲染含原圖對照，另產品 NVENC 120 影格；六套 4 秒 MP4/GIF、實際來源/參數/雜湊；旋轉樣例約 65 秒'),
     ('擷取復用及專案包','外部包及原專案不可用後，擷取復用/匯入專案各 120 影格與原結果相同，JSON/素材保持'),
     ('實際註冊 Skill','唯一入口 dry-run、正式 apply、render、validate 通過；120 影格與基準相同，17 模組保持'),
     ('保留失敗及迴歸','122/122 安裝 CLI 迴歸；首輪夾具漏來源時間碼、示範腳本傳入不支援的 canvas.background 兩條失敗保留'),
     ('本機載入及三語文件','r15 kit/參數/預覽/功能手冊同步；R01–R117 與 38 原結案條件保留，公開舊附件不覆寫')],
    [('Pinned installation','CLI 0.1.16 / local.14; 208 product files match the pinned ZIP installation byte for byte'),
     ('New contracts/native pixels','Source/installed contracts each 20/20, native pixels each 5/5, zero skips; separate scopes, not a completion rate'),
     ('Actual motion previews','Seven native renders include the original control; another product NVENC output has 120 frames; six four-second MP4/GIF previews, source/parameters/hashes; rotation example took about 65 seconds'),
     ('Capture reuse/project package','With external recipes and the source project unavailable, capture reuse/imported output each match all 120 baseline frames; project JSON/asset bytes retained'),
     ('Registered Skill','Single-entry dry-run/apply/render/validate execute; all 120 frames match baseline; seventeen modules retained'),
     ('Failures/regression retained','122/122 installed CLI regression; initial fixture missing source ticks and demo script using unsupported canvas.background remain in the evidence'),
     ('Local load/three-language docs','r15 kit, parameter/previews and functional manuals updated; R01–R117 and all 38 original goal gates retained; public old assets unchanged')],
)


def final():
    for name in ('setup-continue-r1','render-r1','reuse-r1','skill-r1','kit-r1'):
        assert load(name+'/verification.json')['status']=='passed',name
    for run,count in (('development-r2',20),('native-development-r2',5),('installed-contracts-r1',20),('installed-native-r1',5),('installed-cli-r1',122)):
        proof=load('tests/'+run+'/verification.json');assert proof['status']=='passed' and proof['result']['methods']==count
    evidence=('installation-r1/verification.json','tests/installed-native-r1/verification.json','render-r1/verification.json',
        'reuse-r1/verification.json','skill-r1/verification.json','tests/installed-cli-r1/verification.json','final-delivery-r1/verification.json')
    for i,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        text=read(name);old=rows(text,'R');assert len(old)==117
        text=text.replace('<!-- semantic-upgrade-current -->','<!-- semantic-upgrade-history -->').replace('<!-- /semantic-upgrade-current -->','<!-- /semantic-upgrade-history -->')
        text=text.replace('**CLI 0.1.15 / alpha.4-local.13 / r14 kit**','**Historical / 历史 / 歷史：CLI 0.1.15 / alpha.4-local.13 / r14 kit**',1)
        block=('<!-- motion-pack-current -->\n\n**CLI 0.1.16 / alpha.4-local.14 / r15 kit** · 208 product Python files · 1 Skill / 17 modules. '+HEADLINES[i]+'\n\n'
            '[Workflow / 使用流程]('+GUIDE+') · [C25 / Original + six previews](docs/product/CASES.md#c25-motion-packs) · [Evidence]('+REPORT+')\n\n'
            '```powershell\n& $avk motion pack list\n& $avk motion pack inspect --name arc_push\n'
            '& $avk motion pack apply --project $project --sequence-id $sequence --clip-id $clip --name arc_push --param travel=0.18 --param zoom=0.12 --dry-run\n'
            '# Review the returned property conflicts, then apply without --dry-run.\n```\n\n'
            '![Actual parameterized arc / silent](docs/assets/motion-pack-20261025-r1/arc_push.gif)\n\n'+BOUNDARIES[i]+'\n\n<!-- /motion-pack-current -->\n\n')
        text=text.replace('<!-- semantic-upgrade-history -->',block+'<!-- semantic-upgrade-history -->',1)
        history=False;updated=[]
        for line in text.splitlines():
            if re.match(r'<!-- [^/].*-history -->',line):history=True
            if not history and not re.match(r'^\| R\d+\s*\|',line):
                line=line.replace('CLI 0.1.15','CLI 0.1.16').replace('v0.1.0-alpha.4-local.13/final-r3','v0.1.0-alpha.4-local.14/final-r1')
                line=line.replace('[r14 Skill kit]','[r15 Skill kit]').replace('unified-skill-r14.zip','unified-skill-r15.zip')
            updated.append(line)
            if re.match(r'<!-- /.*-history -->',line):history=False
        text='\n'.join(updated)+'\n'
        last=rows(text,'F')['F53'];text=text.replace(last,last+'\n'+F54[i],1)
        k=rows(text,'K')['K02'];text=text.replace(k,k.replace('motion apply','motion apply; motion pack list/inspect/create/capture/apply'),1)
        last=rows(text,'R')['R117']
        new=['| R'+str(n)+' | 2026-10-25 '+title+' | '+description+' | [Evidence](docs/validation/evidence/motion-pack-20261025-r1/'+evidence[n-118]+') |'
             for n,(title,description) in enumerate(CHECKS[i],118)]
        text=text.replace(last,last+'\n'+'\n'.join(new),1)
        assert all(rows(text,'R')[key]==value for key,value in old.items())
        assert len(rows(text,'R'))==124 and len(rows(text,'F'))==54
        write(name,text)
    name='docs/product/GOAL_GAPS_20261025.md';text=read(name);old=rows(text,'G')
    paragraph=('2026-10-25 当前本地交付为 **CLI 0.1.16 / alpha.4-local.14 / r15 kit**，208 个产品 Python 文件与安装版一致。'
        '[可复用运镜包](MOTION_PACKS.md)新增六套参数路径、已有曲线捕获和工程复用，'
        '[原生像素/安装/真实 Skill](../validation/可复用运镜包实测_2026-10-25.md)分别留证；'
        'CPU 合成、自然素材/主体跟随与全部原目标继续推进。旧 0.1.15 的语义升级和原错误保留，全部 38 原关闭条件保持。')
    text=re.sub(r'^2026-10-25 当前本地交付为 .*$',lambda _:paragraph,text,count=1,flags=re.M)
    text=replace_row(text,'V01','| V01 | 当前已安装与注册 | local.14 / CLI 0.1.16，1 Skill/17 模块、r15 kit；[208 文件固定安装](../validation/evidence/motion-pack-20261025-r1/installation-r1/verification.json)，旧包保留 |')
    text=text.replace('semantic-upgrade-capabilities-cli-0.1.15.json','motion-pack-capabilities-cli-0.1.16.json')
    cells=rows(text,'G')['G04'].split('|')
    cells[3]=' 多属性/6 插值/12 基础运镜；六套参数路径包、已有作者曲线捕获、跨时长/画幅与工程包复用 '
    cells[4]=' 固定图卡/原生时钟/跨工程像素通过；自然素材美学、主体跟随组合和 CPU 旋转性能仍不足 '
    cells[6]=' 进行中；新包已实装 '
    text=replace_row(text,'G04','|'.join(cells))
    assert all(rows(text,'G')[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
    text+='\n2026-10-25 G04 子项交付：[CLI 0.1.16 可复用运镜包](MOTION_PACKS.md)；新包/捕获/关键帧/作者时钟/实际预览与复用均有代码和固定安装。旋转 4 秒样例实测约 65 秒，性能与自然素材/跟随组合未闭；所有原关闭条件保持。\n'
    write(name,text)
    name='docs/product/IMPLEMENTATION_PLAN_20261025.md';text=read(name)
    text=re.sub(r'^当前交付为 .*$',lambda _:'当前交付为 **CLI 0.1.16 / alpha.4-local.14 / r15 kit**；[可复用运镜包实测](../validation/可复用运镜包实测_2026-10-25.md)。六套路径、已有动画捕获、关键帧编译、真实预览和复用已实装；原 0.1.15 运行时迁移与既有广告主链路保持。全部原关闭条件保持。',text,count=1,flags=re.M)
    line=next(x for x in text.splitlines() if x.startswith('| W03 '));text=text.replace(line,line.rsplit('|',2)[0]+'| 新增参数路径/已有曲线捕获与稳定工程复用，安装/真实 Skill 像素通过；主体跟随、自然质量与复杂组合继续推进 |',1)
    line=next(x for x in text.splitlines() if x.startswith('| W09 '));text=text.replace(line,line.rsplit('|',2)[0]+'| 当前 CLI 0.1.16 / local.14 / r15 kit 已本地加载；三语 README 和预览/使用流程同步，公开旧版本保持 |',1)
    text+='\n2026-10-25 [可复用运镜包实际交付](../validation/可复用运镜包实测_2026-10-25.md)：208 文件固定安装、六套实际原图/MP4/GIF、跨工程/时长/画幅、裁切/非线性嵌套倒放和注册 Skill 像素证据。仍为 CPU 变换，NVENC 为编码；原目标继续推进。\n'
    write(name,text)
    name='docs/README.md';text=read(name).replace('当前 CLI 0.1.15','当前 CLI 0.1.16')
    anchor=next(line for line in text.splitlines() if line.startswith('| 46 效果算子'))
    text=text.replace(anchor,anchor+'\n| 新增可复用参数运镜、已有曲线捕获、真实预览 / Portable motion and previews | [完整流程](product/MOTION_PACKS.md) · [C25](product/CASES.md#c25-motion-packs) · [安装/像素/Skill 实测](validation/可复用运镜包实测_2026-10-25.md) |',1)
    write(name,text)
    for suffix in ('','.zh-TW','.en'):
        name='docs/product/SKILLS'+suffix+'.md';text=read(name)
        block='<!-- community-current -->\n\n**CLI 0.1.16 / alpha.4-local.14 / r15 kit · 1 Skill / 17 modules.**\n\n'+HEADLINES[('','.zh-TW','.en').index(suffix)]+'\n\n[Motion workflow/previews](MOTION_PACKS.md) · [Ad workflow](AD_STORYBOARD.md) · [Runtime upgrade](SEMANTIC_RUNTIME_UPGRADE.md) · [75 declarations](motion-pack-capabilities-cli-0.1.16.json) · [Current delivery](COMMUNITY_LOCAL_DELIVERY.md).\n\n<!-- /community-current -->'
        text=re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,text,count=1,flags=re.S)
        oldk=rows(text,'K')['K02'];text=text.replace(oldk,oldk.replace('motion apply','motion apply; motion pack list/inspect/create/capture/apply'),1)
        write(name,text)
        name='docs/product/EFFECTS'+suffix+'.md';text=read(name)
        text+='\n## Portable motion packs / 可复用运镜包\n\nCLI 0.1.16 adds six parameterized paths and capture/reuse of existing curves, compiled into ordinary editable transform keys. The twelve base motion presets above remain unchanged. [Full parameter ranges, commands and actual six MP4/GIF previews](MOTION_PACKS.md) · [Installed/Skill evidence](../validation/可复用运镜包实测_2026-10-25.md). Generated paths are 65-point polylines; CPU composition and natural/subject-follow quality remain limited.\n'
        write(name,text)
        name='docs/skills/UNIFIED_SKILL'+suffix+'.md';text=read(name)
        block=('<!-- community-current -->\n\n**Current local / 当前本机 / 目前本機：CLI 0.1.16 / alpha.4-local.14 / r15 kit.** One registered Skill / 17 modules; '
            '[r15 kit](agent-editor-kit-community-unified-skill-r15.zip). Six reusable motion paths and native animation capture are now installed, alongside editable ad variants, semantic runtime migration, GPU voice/translation, subtitle dubbing and 359 resources.\n\n'
            '[Motion workflow + previews](../product/MOTION_PACKS.md) · [Current installation](../product/COMMUNITY_LOCAL_DELIVERY.md) · [All 38 original goals](../product/GOAL_GAPS_20261025.md). Public alpha.3 assets retain their original version.\n\n<!-- /community-current -->')
        text=re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,text,count=1,flags=re.S)
        write(name,text)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('prepare','final'),required=True)
    {'prepare':prepare,'final':final}[parser.parse_args().phase]()
