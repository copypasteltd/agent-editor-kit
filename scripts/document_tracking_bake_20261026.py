"""Preserve all 223 historical README evidence rows while documenting CLI0.1.32."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-bake-20261026-r1'

def load(path): return json.loads(path.read_bytes())
def write(path,text): (ROOT/path).write_text(text,encoding='utf8',newline='\n')
def rows(text): return {m[1]:m[0] for m in re.finditer(r'^\| (R\d{2,3})\s*\|.*$',text,re.M)}

def main():
    install=load(BASE/'installation-final-r3/verification.json'); case=load(BASE/'case-r5/verification.json')
    assert install['status']=='installed-and-byte-verified' and case['status']=='passed'
    counts={name:load(BASE/(name+'-installed-r3/verification.json'))['tests'] for name in ('tracking','conversion','legacy')}
    assert counts=={'tracking':149,'conversion':83,'legacy':192}
    desc={
        '':'原生 PTS 跟踪现可烘焙为普通 hold 关键帧：保留真实帧时钟、遮罩和转场可见度，对烘焙前后全部 Float32 显示帧逐帧比较，再导出工程。原始绑定另存旁车；普通工程包继续保留动态绑定。',
        '.zh-TW':'原生 PTS 跟蹤現可烘焙為普通 hold 關鍵幀：保留真實幀時鐘、遮罩與轉場可見度，逐幀比較烘焙前後全部 Float32 顯示幀，再匯出工程。原始綁定另存旁車；普通工程包繼續保留動態綁定。',
        '.en':'Native PTS tracking now exports as ordinary hold keys. It samples actual clocks, masks and transition visibility, then compares every Float32 display frame before exporting. Original bindings remain in a separate source sidecar; ordinary packages still retain dynamic bindings.'}
    boundary={
        '':'C42 实际注册 Skill：36 帧 Float32 核验、工程包重导入后的36个解码帧与完整144000双声道采样一致；5种格式导出/回读，严格草稿和源文件覆盖拒绝通过。GPU 两轮帧运算及资源关闭有记录。外部播放器、自然质量、连续播放和人工听审未验收；38项原关闭条件继续保留。',
        '.zh-TW':'C42 實際註冊 Skill：36幀 Float32 核驗，工程包重匯入後36個解碼幀與完整144000雙聲道採樣一致；5種格式匯出/回讀，嚴格草稿與來源覆寫拒絕通過。GPU 兩輪幀運算與資源關閉留證。外部播放器、自然品質、連續播放與人工聽審未驗收；保留38項原關閉條件。',
        '.en':'Actual registered C42 verifies 36 Float32 frames, all 36 decoded package-roundtrip frames and all 144,000 stereo samples, five format export/import paths, strict-draft rejection and source-overwrite protection. Both frame-only GPU passes record operations and cleanup. External players, natural quality, continuous playback and human listening remain unaccepted; all 38 original closure conditions remain.'}
    timing={'':'GIF 为 24 帧、实际 3.01 秒（10ms 延时单位）；MP4 保留原始 3 秒时钟。',
        '.zh-TW':'GIF 為 24 幀、實際 3.01 秒（10ms 延遲單位）；MP4 保留原始 3 秒時鐘。',
        '.en':'The 24-frame GIF is 3.01 seconds because delays use 10 ms units; MP4 retains the original 3-second timing.'}
    entry={
        '':['CLI0.1.32/local.30：225个产品文件及schema与源码一致；唯一Skill/17模块/73文件/4个已有模型包。安装版分组：跟踪149、转换83、旧流程192；失败、错误、跳过均为0。',
            'C42实际安装Skill：45次原生绑定求值、36个Float32帧精确一致；烘焙包导入后全部36个解码帧及完整144000双声道采样保留。',
            '5条导出/回读路径：package、agent-json、OTIO、MLT、draft。旁车保留原始观察，严格草稿与源文件覆盖拒绝；逐次转换核验源文件字节不变，外部渲染器等价未验收。',
            '每轮纯帧操作实际GPU affine90/over81；来源、worker及共享资源均关闭。prepared传输状态与编码成片质量分开留证。',
            '新r33 kit共112文件，唯一Skill/17模块/73 Skill文件；独立注册及实际CLI/help/烘焙dry-run已验证，无渲染或源码回退。',
            '完整三语README、60功能/20服务/75声明、使用流程、案例/GIF、Skill及字节核验同步；223条历史R记录及38项原关闭条件保留，开发失败独立留证。'],
        '.zh-TW':['CLI0.1.32/local.30：225產品檔案/schema與原始碼一致；唯一Skill/17模組/73檔案/4既有模型包。獨立安裝組：跟蹤149、轉換83、舊流程192，失敗/錯誤/跳過皆0。',
            'C42實際安裝Skill：45次原生綁定取樣、36幀Float32精確一致；烘焙工程包重匯入後全部36解碼幀及144000完整雙聲道採樣保留。',
            '5條格式匯出/回讀：package、agent-json、OTIO、MLT、draft；旁車保留原始觀察；嚴格草稿與來源覆寫拒絕；未宣稱外部渲染器等價。',
            '每輪純幀運算實際GPU affine90/over81；來源、worker與共享資源已關閉。prepared傳輸狀態與編碼成片品質分開記錄。',
            '新r33 kit112檔案、唯一Skill/17模組/73 Skill檔案；獨立註冊及CLI/help/烘焙dry-run核驗，無渲染或原始碼回退。',
            '完整三語README、60功能/20服務/75宣告、流程、案例/GIF、Skill與位元組審核同步；223歷史R列及38原關閉條件保留，開發失敗獨立留證。'],
        '.en':['CLI0.1.32/local.30:225 product files/schema equal source; one Skill/17 modules/73 files/four existing model packs. Separate installed groups:149 tracking,83 conversion,192 legacy, with zero failures/errors/skips.',
            'Actual installed C42:45 native binding samples and36 exact Float32 frames; imported baked package retains every decoded frame and144000 complete stereo samples.',
            'Five export/import paths:package,agent-json,OTIO,MLT,draft. Sidecars preserve original observations; strict draft and source overwrite reject. External renderer equivalence is not certified.',
            'Each frame-only GPU pass executes90 affine/81 over operations; providers,worker and shared handles close. Prepared transport is distinct from encoded-movie quality acceptance.',
            'Fresh r33 kit112 files:one Skill/17 modules/73 Skill files; isolated registration,actual CLI/help/bake dry-run verified,without rendering or source fallback.',
            'Full trilingual READMEs,60 functions/20 services/75 declarations,workflow,case/GIF,Skill and byte audits updated;223 historical R rows and38 original closure cells preserved. Failed development attempts retained separately.']}
    targets=['installation-final-r3/verification.json','case-r5/verification.json','case-r5/format-exports.json','case-r5/native-bake-proof.json','kit-r1/verification.json','development-attempts-r4/verification.json']
    for suffix,name in [('','README.md'),('.zh-TW','README.zh-TW.md'),('.en','README.en.md')]:
        text=(ROOT/name).read_text('utf8'); previous=rows(text); assert len(previous)==223
        text=text.replace('**CLI0.1.31 / alpha.4-local.29 / r32 kit','**Historical / 历史 / 歷史：CLI0.1.31 / alpha.4-local.29 / r32 kit',1)
        block='<!-- tracking-bake-current -->\n\n**CLI0.1.32 / alpha.4-local.30 / r33 kit · 1 Skill / 17 modules.**\n\n'+desc[suffix]+'\n\n'
        block+='```powershell\n& $avk convert export --project $avkProject --target-format package `\n  --bake-tracking --output $bakedPackagePath\n& $avk convert import --input $bakedPackagePath --output $newProjectDirectory\n```\n\n'
        block+='[Workflow](docs/product/TRACKING_BAKE.md) · [C42](docs/product/CASES.md#c42-tracking-bake) · [Install](docs/releases/CLI_0.1.32_LOCAL.md) · [Evidence](docs/validation/跟踪原生烘焙导出实测_2026-10-26.md)\n\n'
        block+='![Native tracking left / baked keys right / actual silent GIF](docs/assets/tracking-bake-20261026-r5/comparison.gif)\n\n'+boundary[suffix]+'\n\n'+timing[suffix]+'\n\n<!-- /tracking-bake-current -->\n\n'
        text=text.replace('<!-- tracking-visibility-current -->',block+'<!-- tracking-visibility-current -->',1)
        f60={
            '':'| F60 | 原生跟踪与烘焙交付 | 实际alpha/5类遮罩/59转场足迹；剪辑与共享变速保留观察；原生烘焙逐帧核验并保留源旁车。 | `media track-bind; timeline compose/edit; convert export --bake-tracking` | 当前冻结图/FPS；20,000帧/256,000求值；无法表达的整数步进拒绝；外部播放器及自然身份/遮挡待验收。 |',
            '.zh-TW':'| F60 | 原生跟蹤與烘焙交付 | 實際alpha/5類遮罩/59轉場足跡；剪輯與共享變速保留觀察；原生烘焙逐幀核驗並保留來源旁車。 | `media track-bind; timeline compose/edit; convert export --bake-tracking` | 目前凍結圖/FPS；20,000幀/256,000求值；無法表達的整數步進拒絕；外部播放器與自然身分/遮擋待驗收。 |',
            '.en':'| F60 | Native tracking and baked delivery | Actual alpha/five masks/59 transition footprints; edits and shared retime retain observations; native bake verifies all frames and retains source sidecars. | `media track-bind; timeline compose/edit; convert export --bake-tracking` | Frozen graph/FPS;20,000 frames/256,000 samples;unrepresentable integer steps reject;external players and natural identity/occlusion remain unaccepted. |'}
        text=re.sub(r'^\| F60\s*\|.*$',lambda _:f60[suffix],text,count=1,flags=re.M)
        text='\n'.join(line.replace('local.29/final-r1/installed','local.30/final-r3/installed').replace('0.1.31','0.1.32')
            if not line.startswith('| R') and 'local.29/final-r1/installed' in line else line for line in text.splitlines())+'\n'
        last=re.search(r'^\| R223\s*\|.*$',text,re.M); assert last
        additions=['| R'+str(224+i)+' | 2026-10-26 native tracking bake | '+value+' | [Evidence](docs/validation/evidence/tracking-bake-20261026-r1/'+target+') |' for i,(value,target) in enumerate(zip(entry[suffix],targets))]
        text=text[:last.end()]+'\n'+'\n'.join(additions)+text[last.end():]
        assert len(rows(text))==229 and all(rows(text)[k]==v for k,v in previous.items()); write(name,text)
        for path in ('docs/product/SKILLS'+suffix+'.md','docs/skills/UNIFIED_SKILL'+suffix+'.md'):
            link='TRACKING_BAKE.md' if '/product/' in path else '../product/TRACKING_BAKE.md'
            current='<!-- community-current -->\n\n**CLI0.1.32 / alpha.4-local.30 / r33 kit · 1 Skill / 17 modules / 73 files.**\n\n'+desc[suffix]+'\n\n[Tracking bake workflow]('+link+')\n\n<!-- /community-current -->'
            write(path,re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:current,(ROOT/path).read_text('utf8'),count=1,flags=re.S))
    report='# 原生跟踪烘焙导出实测 · 2026-10-26\n\nCLI0.1.32/local.30/r33；唯一统一Skill、17模块、原生Windows。\n\n'+boundary['']+'\n\n| Scope | Evidence |\n|---|---|\n'
    for label,target in [('Installation','installation-final-r3/verification.json'),('Four existing packs','activation-final-r4/activation-and-registration.json'),('Current Skill registration','registration-final-r2.json'),('Tracking149','tracking-installed-r3/verification.json'),('Conversion83','conversion-installed-r3/verification.json'),('Legacy192','legacy-installed-r3/verification.json'),('C42','case-r5/verification.json'),('All36 Float32 frames','case-r5/native-bake-proof.json'),('Complete decoded frames/PCM','case-r5/decoded-full-media.json'),('Formats','case-r5/format-exports.json'),('Fresh kit','kit-r1/verification.json'),('Failed attempts','development-attempts-r4/verification.json')]: report+='| '+label+' | [Evidence](evidence/tracking-bake-20261026-r1/'+target+') |\n'
    report+='\n独立分组存在交集，不汇总成剪映等价率。复用已具独立滑动/无绑定参考的C41自制CC0素材，本轮实际跑原生烘焙、包往返与完整音画；未重新运行模型。初始无效测试夹具、MLT扩展名及profile帧率缺陷、草稿重叠映射、Skill pin先后顺序和GPU纯帧状态断言失败单独保留并修复。case-r4把正常render追加的输出/日志误判为转换修改，最终案例逐次转换核验工程和权利台账哈希，并单独核验render只追加输出/日志及更新时间；原始失败记录保留。最终门槛未放宽：全部Float32帧/解码帧/完整PCM保持精确一致。GPU纯帧证明记录prepared/实际算子/清理；成片另经公共render质量核验。\n\n[Workflow](../product/TRACKING_BAKE.md) · [C42](../product/CASES.md#c42-tracking-bake) · [Install](../releases/CLI_0.1.32_LOCAL.md).\n'
    report+='\nGIF检查：24帧共3010ms，保留每帧120/130ms实际延时；原MP4为3秒。初始3000ms断言的失败已留证。六张静态抽帧已目检，全部24帧左右RGB相等；不作为连续播放或听审。 [实际检查记录](evidence/tracking-bake-20261026-r1/media-inspection-r2/verification.json)。\n'
    write('docs/validation/跟踪原生烘焙导出实测_2026-10-26.md',report)
    release='# CLI0.1.32 · native tracking bake · local.30\n\n本地安装并注册唯一 `$agent-ffmpeg-local-editor`。公开alpha.3历史附件保持。\n\n| Item | Verified value |\n|---|---|\n'
    for key,value in [('Runtime','v0.1.0-alpha.4-local.30/final-r3/installed'),('ZIP',install['archive']),('Bytes',str(install['archive_bytes'])),('SHA256',install['archive_sha256']),('Manifest SHA256',install['manifest_sha256']),('CLI/wheel','0.1.32'),('Product','225 Python files/schema equal source'),('Skill','1 entry/17 modules/73 files;r33 kit112 files')]: release+='| '+key+' | `'+value+'` |\n'
    release+='\n'+desc['']+'\n\n'+boundary['']+'\n\n[Installation](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Workflow](../product/TRACKING_BAKE.md) · [Evidence](../validation/跟踪原生烘焙导出实测_2026-10-26.md) · [r33 kit](../skills/agent-editor-kit-community-unified-skill-r33.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.32-r33.json).\n'
    write('docs/releases/CLI_0.1.32_LOCAL.md',release)
    example='\n<a id="c42-tracking-bake"></a>\n\n## C42 · 原生跟踪烘焙交付 · CLI0.1.32\n\n'+boundary['']+'\n\n左：动态原生绑定；右：普通hold关键帧；实际导出的两份画面，GIF无声。24帧GIF实际3010ms，逐帧延时写入manifest；MP4仍为原始3秒。\n\n![Actual comparison](../assets/tracking-bake-20261026-r5/comparison.gif)\n\n[Native MP4](../assets/tracking-bake-20261026-r5/original.mp4) · [Baked MP4](../assets/tracking-bake-20261026-r5/baked.mp4) · [Baked editable package](../assets/tracking-bake-20261026-r5/editable-baked-tracking.aevpkg.zip) · [Original dynamic package](../assets/tracking-visibility-20261026-r2/editable-tracking-visibility.aevpkg.zip) · [Source/rights](../assets/tracking-bake-20261026-r5/SOURCE.txt) · [Hashes](../assets/tracking-bake-20261026-r5/media-manifest.json) · [Workflow](TRACKING_BAKE.md).\n'
    write('docs/product/CASES.md',(ROOT/'docs/product/CASES.md').read_text('utf8')+example)
    write('docs/product/TRACKING_BAKE.md',(ROOT/'docs/product/TRACKING_BAKE.md').read_text('utf8')+example)
    path='docs/product/COMMUNITY_LOCAL_DELIVERY.md'; text=(ROOT/path).read_text('utf8')
    old=load(ROOT/'docs/validation/evidence/tracking-visibility-20261026-r1/installation-final-r1/verification.json')
    footer=re.search(r'^CLI0\.1\.31/local\.29/r32：.*$',text,re.M)
    if footer: text=text[:footer.start()]+'TRACKING_BAKE_OLD_DELIVERY_FOOTER'+text[footer.end():]
    previous_footer=re.search(r'^CLI0\.1\.30/local\.29/r31：.*$',text,re.M)
    if previous_footer: text=text[:previous_footer.start()]+'TRACKING_BAKE_OLDER_DELIVERY_FOOTER'+text[previous_footer.end():]
    for before,after in [('local.29/final-r1/installed','local.30/final-r3/installed'),('local.29/candidate-r1/bundle.zip','local.30/candidate-r3/bundle.zip'),('local.29','local.30'),('CLI 0.1.31','CLI 0.1.32'),('r32.zip','r33.zip'),('0.1.31-r32.json','0.1.32-r33.json'),(old['archive_sha256'],install['archive_sha256']),(old['manifest_sha256'],install['manifest_sha256'])]: text=text.replace(before,after)
    if footer: text=text.replace('TRACKING_BAKE_OLD_DELIVERY_FOOTER','历史 / Historical：'+footer[0])
    if previous_footer: text=text.replace('TRACKING_BAKE_OLDER_DELIVERY_FOOTER','历史 / Historical：'+previous_footer[0].replace('local.29','local.28'))
    write(path,text+'\nCLI0.1.32/local.30/r33：[原生跟踪烘焙](TRACKING_BAKE.md) · [verified local delivery](../releases/CLI_0.1.32_LOCAL.md)。历史[CLI0.1.31](../releases/CLI_0.1.31_LOCAL.md)保留。\n')
    path='docs/README.md';text=(ROOT/path).read_text('utf8').replace('Current local / 当前本地 / 目前本地：**CLI0.1.31 / local.29 / r32 kit**','Historical / 历史 / 歷史：**CLI0.1.31 / local.29 / r32 kit**',1)
    write(path,text.replace('\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.32 / local.30 / r33 kit** · [Bake](product/TRACKING_BAKE.md) · [Install](releases/CLI_0.1.32_LOCAL.md) · [C42](product/CASES.md#c42-tracking-bake).\n',1))
    for path in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        text=(ROOT/path).read_text('utf8').replace('当前本地 **CLI0.1.31 / alpha.4-local.29 / r32 kit**','此前本地 **CLI0.1.31 / alpha.4-local.29 / r32 kit**',1); first=text.index('\n')+1
        text=text[:first]+'\n当前本地 **CLI0.1.32 / alpha.4-local.30 / r33 kit**：[原生跟踪烘焙导出](TRACKING_BAKE.md)已接通，冻结图逐帧Float32相等、完整音画包往返与5格式回读留证；外部运行器仍需验收，全部38原关闭条件保持。\n'+text[first:]
        text=text.replace('local.29-final-r1/CLI0.1.31/r32','local.30-final-r3/CLI0.1.32/r33');write(path,text)
    path='docs/product/GOAL_GAPS_20261025.md';text=(ROOT/path).read_text('utf8')
    match=re.search(r'^\| G31\s*\|.*$',text,re.M);assert match
    cells=match[0].split('|');cells[3]+=' CLI0.1.32原生跟踪烘焙为普通hold关键帧，逐帧Float32核验；五格式回读、MLT扩展名/分数FPS及OTIO原时基保存、草稿重叠近似映射已补；[C42](CASES.md#c42-tracking-bake)留证。'
    write(path,text[:match.start()]+'|'.join(cells)+text[match.end():])
    path='docs/product/IMPLEMENTATION_PLAN_20261025.md';text=(ROOT/path).read_text('utf8').replace('相机/麦克风/音画同步及互操作继续推进','CLI0.1.32跟踪烘焙和5格式回读已接通；相机/麦克风/音画同步及外部运行器互操作继续推进',1);write(path,text)
    path='docs/product/TRACKING_VISIBILITY.md';text=(ROOT/path).read_text('utf8').replace('MLT/OTIO/草稿的原生时钟烘焙仍未实现；原生工程包保留全部绑定。','后续CLI0.1.32已接通[原生时钟烘焙](TRACKING_BAKE.md)；本页CLI0.1.31为历史实测，普通原生工程包继续保留全部绑定。');write(path,text)
    path='docs/product/FLOAT_TRACKING.md';text=(ROOT/path).read_text('utf8');first=text.index('\n')+1
    text=text[:first]+'\n本页保留CLI0.1.26初始契约；当前CLI0.1.32已支持[原生逐帧核验烘焙](TRACKING_BAKE.md)，旧导出门禁为历史状态。\n'+text[first:]
    text+='\nCLI0.1.32现支持[原生逐帧核验烘焙](TRACKING_BAKE.md)：外部格式自动烘焙，Agent JSON/package显式`--bake-tracking`，保留源绑定旁车。上述CLI0.1.26的导出限制为历史状态。\n';write(path,text)
    print(json.dumps(dict(status='documented',historical_rows_preserved=223,current_rows=229,counts=counts),ensure_ascii=False))

if __name__=='__main__': main()
