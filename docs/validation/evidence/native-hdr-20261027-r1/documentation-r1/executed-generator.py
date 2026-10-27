"""Publish complete trilingual HDR usage and real evidence without deleting history."""
from pathlib import Path
import hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-hdr-20261027-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def after(s,p,entry):
    m=list(re.finditer(r'^\| '+p+r'\d+\s*\|.*$',s,re.M))[-1]
    return s[:m.end()]+'\n'+entry+s[m.end():]

def main():
    out=BASE/'documentation-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r1/verification.json');tests=load(BASE/'installed-regression-r2/verification.json')
    case=load(BASE/'case-r3/verification.json')
    assert install['source_file_count']==240 and tests['status']=='passed' and tests['tests']==993
    assert tests['failures']==tests['errors']==tests['skipped']==0 and tests['frozen_equal'] and tests['test_frozen_equal']
    assert case['status']=='passed' and case['all_48_decoded_10bit_frames_equal'] and case['all_384000_PCM_equal'] and case['PCM_nonzero']
    assert case['GPU']['operations']['glow']==48 and case['GIF_duration_ms']==4000
    capture='docs/product/native-hdr-capabilities-cli-0.1.40.json'
    (ROOT/capture).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==79
    desc={
        '':'新增**原生 PQ／HLG HDR 信号、明确 nit 单位、10-bit BT.2020 交付和独立 SDR 预览**。HLG 包含 RGB 联动 OOTF；不同参考白的 SDR 图形与 HDR 高光可在线性光域合成。明确选择输入／输出截断、SDR 映射及其色域策略，保留作者时钟、效果和可编辑工程。',
        '.zh-TW':'新增**原生 PQ／HLG HDR 訊號、明確 nit 單位、10-bit BT.2020 交付及獨立 SDR 預覽**。HLG 包含 RGB 聯動 OOTF；不同參考白的 SDR 圖形與 HDR 高光可在線性光域合成。明確選擇輸入／輸出截斷、SDR 映射及其色域策略，保留作者時鐘、效果及可編輯工程。',
        '.en':'Adds **native display-light PQ/HLG, explicit nit units, 10-bit BT.2020 delivery and separate SDR previews**. HLG includes the RGB-coupled OOTF; SDR graphics and HDR highlights with different reference whites compose in linear light. Author clocks, effects and editable projects retain explicit input/output clipping and SDR mapping decisions.'}
    limit={
        '':'安装版单轮 **993 项回归通过，零失败／错误／跳过**：保留上轮734项，加入20项HDR数值／实际工程核验及239项相关色彩兼容检查。C50 为实际注册 Skill 输出，48帧／12FPS／4秒，非静音双声道384000个Float32 PCM标量及全部10bit帧在包迁移后相同。色彩传递数学当前CPU，已接通合成／光效继续实际GPU；HDR监看、自然质量、ICC、非零黑位HLG、母版／动态元数据及完整目标继续建设。',
        '.zh-TW':'安裝版單輪 **993 項回歸通過，零失敗／錯誤／跳過**：保留上輪734項，加入20項HDR數值／實際工程核驗及239項相關色彩相容檢查。C50 為實際註冊 Skill 輸出，48影格／12FPS／4秒，非靜音雙聲道384000個Float32 PCM標量及全部10bit影格在工程包遷移後相同。色彩傳遞數學目前CPU，已接通合成／光效持續實際GPU；HDR監看、自然品質、ICC、非零黑位HLG、母版／動態中繼資料及完整目標持續建設。',
        '.en':'One installed run passes **993 regressions with zero failures/errors/skips**: all prior734, 20 HDR numeric/actual-engineering checks and239 related color compatibility tests. Registered Skill C50 retains all48 decoded10-bit frames and384000 nonzero stereo Float32 PCM scalars after package import (12FPS/four seconds). Transfer math is tiled CPU; supported composition/effects retain actual GPU use. HDR monitor/natural quality, ICC, nonzero-black HLG, mastering/dynamic metadata and the complete goal remain open.'}
    feature={
        '':'| F66 | 原生 PQ／HLG HDR 与 SDR 显示 | 明确参考白及HLG峰值/gamma，解码至显示线性光；不同nit素材、普通效果/合成、10-bit BT.2020 NCL交付，单独选择SDR trim及PNG/MP4预览。 | `timeline compose; validate; preview; render; convert` | 传递CPU，已有合成/光效可GPU；拒绝8-bit/标签不符/缺单位；alpha位保留。非ICC/动态元数据或HDR监看验收。 |',
        '.zh-TW':'| F66 | 原生 PQ／HLG HDR 與 SDR 顯示 | 明確參考白及HLG峰值/gamma，解碼至顯示線性光；不同nit素材、一般效果/合成、10-bit BT.2020 NCL交付，獨立選擇SDR trim及PNG/MP4預覽。 | `timeline compose; validate; preview; render; convert` | 傳遞CPU，既有合成/光效可GPU；拒絕8-bit/標籤不符/缺單位；alpha位元保留。非ICC/動態中繼資料或HDR監看驗收。 |',
        '.en':'| F66 | Native PQ/HLG HDR and SDR viewing | Explicit reference white/HLG peak/gamma → display-linear edits; mixed-nit assets, ordinary effects/composition and10-bit BT.2020 NCL delivery; separate SDR trim and PNG/MP4 previews. | `timeline compose; validate; preview; render; convert` | CPU transfer math; existing GPU composition/effects; rejects8-bit/mismatched tags/missing units; alpha bits retained. ICC/dynamic metadata/HDR monitoring unaccepted. |'}
    checks={
        '':['CLI0.1.40/local.38，240产品文件源码/安装一致；993安装版用例单轮全过，零失败/错误/跳过，保留原734项并加入20项HDR与239项色彩兼容核验。',
            '12数值项：独立50位Decimal PQ oracle、HLG彩色联动OOTF/逆变换、多峰值gamma、绝对nit换算、显式域/色域截断计数、alpha位、分块一致、取消及预算。',
            '8实际集成项：PQ/HLG原生10bit与VUI、PQ→HLG、独立标量SDR trim、真正10bit YCbCr输入、PNG/MP4预览、缺失映射/8bit/缺单位拒绝、schema及完整音画工程包。',
            '239既有色彩/曲线/LUT/浮点包/色阶/三路平衡/色调专项回归通过，原有二字段相对信号、精度、资源及迁移约束保留。',
            '注册安装版Skill C50实际混合100nit SDR图形与203nit参考白HDR；48帧、非静音双声道384000 PCM及10bit画面包往返相同，输出PQ/HLG母版、独立SDR trim和4000ms GIF。',
            'r41工具包1入口/17模块/79 Skill文件/126包文件，完整校验与独立注册32次调用；三语F66/S21，271既有R记录及38原关闭条件保留。'],
        '.zh-TW':['CLI0.1.40/local.38，240產品檔案原始碼/安裝一致；993安裝版用例單輪全過，零失敗/錯誤/跳過，保留原734項並加入20項HDR及239項色彩相容核驗。',
            '12數值項：獨立50位Decimal PQ oracle、HLG彩色聯動OOTF/逆變換、多峰值gamma、絕對nit換算、明確域/色域截斷計數、alpha位元、分塊一致、取消及預算。',
            '8實際整合項：PQ/HLG原生10bit與VUI、PQ→HLG、獨立標量SDR trim、真正10bit YCbCr輸入、PNG/MP4預覽、缺映射/8bit/缺單位拒絕、schema及完整音畫工程包。',
            '239既有色彩/曲線/LUT/浮點包/色階/三路平衡/色調專項回歸通過，原二欄位相對訊號、精度、資源及遷移約束保留。',
            '註冊安裝版Skill C50實際混合100nit SDR圖形及203nit參考白HDR；48影格、非靜音雙聲道384000 PCM及10bit畫面工程包往返相同，輸出PQ/HLG母版、獨立SDR trim及4000ms GIF。',
            'r41工具包1入口/17模組/79 Skill檔案/126包檔案，完整校驗與獨立註冊32次呼叫；三語F66/S21，271既有R記錄及38原關閉條件保留。'],
        '.en':['CLI0.1.40/local.38:240 source/installed product files match; one installed run passes993 tests, zero failures/errors/skips, retaining all734 prior checks plus20 HDR and239 related color tests.',
            '12 numeric tests use independent50-digit Decimal PQ and scalar coupled-HLG oracles; explicit nits/peak/gamma, domain/gamut counters, alpha bits, tiles, cancellation and budgets.',
            '8 actual integration tests: native PQ/HLG10-bit pixels/VUI, PQ→HLG, scalar SDR trim, real10-bit YCbCr input, PNG/MP4 previews, invalid configuration rejection, schema and complete package audio/video.',
            '239 existing color/curves/LUT/float-bundle/levels/balance/tone tests preserve two-field relative signal semantics, precision, resource and migration contracts.',
            'Registered installed Skill C50 mixes100-nit SDR graphics with203-nit reference-white HDR. All48 frames/nonzero384000 stereo PCM scalars match after package import; actual PQ/HLG masters, SDR trim and4000ms GIF.',
            'r41:one Skill/17 modules/79 Skill files/126 kit entries; full verification and32 isolated registration calls. Trilingual F66/S21 retain all271 prior R rows and38 original closure cells.']}
    targets=['installed-regression-r2/verification.json','source-numeric-r4/verification.json',
             'installed-regression-r2/receipts.json','source-compat-r1/verification.json','case-r3/verification.json','kit-r1/verification.json']
    for suffix in ('','.zh-TW','.en'):
        name='README'+suffix+'.md';s=read(name);old=rows(s,'R');assert len(old)==271
        block='<!-- hdr-display-current -->\n\n**CLI0.1.40 / alpha.4-local.38 / r41 kit · 1 Skill / 17 modules.**\n\n'+desc[suffix]+'\n\n'
        block+='[Workflow / usage](docs/product/HDR_DISPLAY.md) · [C50](docs/product/CASES.md#c50-native-hdr) · [Install](docs/releases/CLI_0.1.40_LOCAL.md) · [Evidence](docs/validation/HDR显示光实测_2026-10-27.md)\n\n'
        block+='![Actual SDR viewing trim of HDR edit](docs/assets/native-hdr-20261027-r3/hdr-sdr-view.gif)\n\n'+limit[suffix]+'\n\n<!-- /hdr-display-current -->\n\n'
        assert '<!-- highlight-glow-current -->' in s
        s=s.replace('<!-- highlight-glow-current -->',block+'<!-- highlight-glow-history -->',1).replace('<!-- /highlight-glow-current -->','<!-- /highlight-glow-history -->',1)
        s=after(s,'F',feature[suffix])
        s=after(s,'R','\n'.join('| R'+str(272+i)+' | 2026-10-27 native HDR | '+d+' | [Evidence](docs/validation/evidence/native-hdr-20261027-r1/'+p+') |' for i,(d,p) in enumerate(zip(checks[suffix],targets))))
        s='\n'.join(l.replace('local.37/final-r2/installed','local.38/final-r1/installed').replace('CLI 0.1.39','CLI 0.1.40')
            if 'local.37/final-r2/installed' in l and not l.startswith('| R') else l for l in s.splitlines())+'\n'
        s=s.replace('[r40 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r40.zip)','[r41 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r41.zip)')
        assert len(rows(s,'F'))==66 and len(rows(s,'S'))==21 and len(rows(s,'K'))==17 and len(rows(s,'R'))==277
        assert all(rows(s,'R')[k]==v for k,v in old.items());write(name,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            path=base+suffix+'.md';s=read(path);relative='HDR_DISPLAY.md' if '/product/' in path else '../product/HDR_DISPLAY.md'
            block='<!-- community-current -->\n\n**CLI0.1.40 / alpha.4-local.38 / r41 kit · 1 Skill / 17 modules / 79 files.**\n\n'+desc[suffix]+'\n\n[HDR workflow and constraints]('+relative+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            if base.endswith('CAPABILITIES'):
                s=after(s,'F',feature[suffix])
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if n==0:assert key=='native_hdr_display_pipeline';s+='\n'+section+'\n'
                s+='\n[CLI0.1.40 exact installed capability snapshot](native-hdr-capabilities-cli-0.1.40.json).\n'
            write(path,s)
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
    prior=load(ROOT/'docs/validation/evidence/highlight-glow-20261027-r1/installation-final-r2/verification.json')
    for old,new in [('alpha.4-local.37','alpha.4-local.38'),('CLI 0.1.39','CLI 0.1.40'),('r40.zip','r41.zip'),
        ('0.1.39-r40.json','0.1.40-r41.json'),(prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(old,new)
    s=s.replace('alpha.4-local.38/candidate-r2','alpha.4-local.38/candidate-r1').replace('alpha.4-local.38/final-r2','alpha.4-local.38/final-r1')
    s+='\nCLI0.1.40/local.38/r41: [native PQ/HLG and SDR viewing](HDR_DISPLAY.md), [C50](CASES.md#c50-native-hdr), [installation](../releases/CLI_0.1.40_LOCAL.md).\n';write(p,s)
    release='# CLI0.1.40 · native PQ/HLG HDR · alpha.4-local.38\n\nLocal tested build; public alpha.3/CLI0.1.2 and its original assets/tags remain unchanged.\n\n'
    release+='Application ZIP: `'+Path(install['archive']).relative_to(ROOT).as_posix()+'`\n\nBytes: `'+str(install['archive_bytes'])+'` · SHA256: `'+install['archive_sha256']+'`\n\nManifest: `'+install['manifest_sha256']+'`\n\nInstalled: `'+Path(install['installed']).relative_to(ROOT).as_posix()+'`\n\n'
    release+='240 source/installed Python files match;79 capabilities;51 effects;one public Skill/17 modules/79 Skill files. r41 contains126 entries; app/model archives remain separate. All993 installed tests pass in one complete run, zero failures/errors/skips. New20 HDR checks and239 related color checks retain all734 prior tests.\n\n'
    release+='[Install/launch](../product/COMMUNITY_LOCAL_DELIVERY.md) → [HDR/SDR workflow](../product/HDR_DISPLAY.md) → [C50 editable example](../product/CASES.md#c50-native-hdr). [r41 kit](../skills/agent-editor-kit-community-unified-skill-r41.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.40-r41.json) · [Verification](../validation/HDR显示光实测_2026-10-27.md).\n\n'
    release+='PQ display EOTF/inverse and coupled HLG OOTF/inverse use explicit nit/reference-white/peak/gamma declarations. Native10-bit BT2020 NCL output carries matching VUI; source/output clipping and SDR viewing require explicit choices. Actual C50 mixes different-nit HDR/SDR assets with GPU Bloom, nonzero stereo PCM and complete package reimport equality.\n\nNo ICC, nonzero-black HLG calibration, mastering/CLL/dynamic metadata, Dolby Vision, natural/HDR monitor or full product acceptance. All38 original goal closure conditions remain.\n';write('docs/releases/CLI_0.1.40_LOCAL.md',release)
    p='docs/product/CASES.md';s=read(p);assert 'id="c50-native-hdr"' not in s
    s+='\n<a id="c50-native-hdr"></a>\n\n## C50 · 原生 HDR 与 SDR 显示 / Native HDR and SDR viewing\n\n'
    s+='Actual registered installed CLI0.1.40 creates a48-frame/12FPS/four-second640×360 HDR chart with0.1–700 cd/m² patches and a moving warm highlight. A declared100-nit SDR badge composites into203-nit reference-white BT2020 linear working light, with editable Bloom intensity and real GPU dispatch. All48 decoded10-bit frames and all384000 nonzero stereo Float32 PCM scalars remain byte-identical after package import. Each content render executes48 glow operations/192 kernels, with probe work separate and owned resources closed.\n\n'
    media='../assets/native-hdr-20261027-r3/'
    s+='![Actual SDR viewing trim; original HDR master is separate]('+media+'hdr-sdr-view.gif)\n\n'
    s+=' · '.join('['+label+']('+media+name+')' for label,name in [('SDR viewing MP4','sdr-preview.mp4'),('PQ10-bit master','pq-master.mkv'),('HLG10-bit master','hlg-master.mkv'),('Separate SDR trim','sdr-master.mkv'),('Editable project','editable-native-hdr.aevpkg.zip'),('Actual SDR PNG','preview-frame.png'),('Original PQ input','source-pq.mkv'),('Original SDR badge','source-sdr-badge.png'),('Original stereo tones','source-stereo.wav'),('Recipes','recipes.json'),('Source/license','SOURCE.txt'),('Media manifest','media-manifest.json')])+'\n\n'
    s+='[Usage](HDR_DISPLAY.md) · [Evidence](../validation/HDR显示光实测_2026-10-27.md). MP4/GIF/PNG are explicit SDR previews using the declared modified-Reinhard mapping, not evidence of HDR monitor quality. Original PQ/HLG masters retain their matching actual10-bit pixel/VUI boundaries. Synthetic charts/tones are CC0; source scripts and algorithms are MIT. No continuous human playback/listening, natural-footage acceptance, display calibration or full product parity is claimed.\n';write(p,s)
    note='当前本地 **CLI0.1.40 / alpha.4-local.38 / r41 kit**：[G08原生PQ/HLG显示光及SDR预览](HDR_DISPLAY.md)已接通明确nit单位、HLG联动OOTF、10bit BT.2020输出；993安装版回归单轮通过，C50真实GPU混合HDR/SDR素材、全48帧及非静音完整PCM工程包往返相同。ICC、母版/动态元数据、自然HDR监看及38原关闭条件继续开发。'
    for p in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        s=read(p);first=s.index('\n');write(p,s[:first]+'\n\n'+note+'\n'+s[first:])
    p='docs/product/GOAL_GAPS_20261025.md';s=read(p)
    lines=s.splitlines()
    for i,l in enumerate(lines):
        if l.startswith('| G08 |'):
            fields=l.split('|');fields[3]=' 原有调色/LUT/曲线/HSL/调整层；CLI0.1.40新增明确nit/PQ/HLG联动OOTF、线性光合成、10bit BT2020 NCL输出和独立SDR预览，真实Skill C50与993安装版回归留证 '
            fields[4]=' ICC/色适应/非零黑位HLG/母版与动态元数据、感知色域映射、自然HDR监看和完整后端效果质量仍未闭；10bit编码本身不证明这些验收 '
            lines[i]='|'.join(fields)
    write(p,'\n'.join(lines)+'\n')
    p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：',1);first=s.index('\n')
    write(p,s[:first]+'\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.40 / local.38 / r41 kit** · [HDR/SDR](product/HDR_DISPLAY.md) · [Install](releases/CLI_0.1.40_LOCAL.md) · [C50](product/CASES.md#c50-native-hdr).\n'+s[first:])
    validation='# HDR 显示光实测 · 2026-10-27\n\nCLI0.1.40/local.38/r41，原生Windows，无虚拟化、依赖下载、全局安装或源码回落。\n\n'
    for label,target in [('最终单轮993安装版回归','installed-regression-r2/verification.json'),('独立12数值项','source-numeric-r4/verification.json'),('239相关兼容项','source-compat-r1/verification.json'),('离线安装/240文件同字节','installation-final-r1/verification.json'),('实际注册Skill C50','case-r3/verification.json'),('隔离r41完整校验与32调用','kit-r1/verification.json'),('最终交付审核','final-delivery-r1/verification.json')]:
        validation+='['+label+'](evidence/native-hdr-20261027-r1/'+target+')\n\n'
    validation+='最终安装版单轮993项全部通过、零失败/错误/跳过：734原有项＋20新增HDR项＋239相关色彩兼容项，互不重复。标准数值使用独立50位Decimal PQ oracle及标量HLG RGB联动参考；实际核验包含10bit PQ/HLG像素与VUI、跨格式绝对光度、YCbCr读入、SDR映射、预览、完整非静音双声道PCM及工程包音画往返。CPU分块传递转换与实际GPU合成/光效分别留证。\n\n'
    validation+='早期数值r1/r2错误保留：HLG参考函数错误地保留NumPy Float32中间乘法，已转为独立Python double；PQ10000/203在公共Float32端点略超标准范围，测试现明确选择并检查计数clip，产品不隐式放宽域；联动差异的独立绝对阈值由误写30更正20，完整数值oracle不变。\n\n'
    validation+='早期工程r1/r2/r3保留：夹具音频权利/唯一ID/时长、Path参数、CLI预览最小高度和区间参数、回执字段读取错误已在最终完整套件中修正；没有删掉失败项。安装回归r1因旧scratch名称冲突在任何测试前退出，原文件保留；改为native-hdr前缀，最终r2独立运行全部993项。C50 r1误用add_track不支持的overlay值，r2缺项目默认10bit输出被正确拒绝，均保留；最终r3使用普通视频图层并明确输出。\n\n'
    validation+='C50为自行生成的CC0 chart/图形/非静音双声道，640×360、48帧/12FPS/4秒，HDR700nit高光及100nit SDR图形在203nit参考白线性域合成；实际GPU Bloom48操作/192内容kernel，另有启动探测。原PQ工程包重导入后全部48帧10bit像素及384000个Float32 PCM标量相同；HLG母版和SDR trim另行实际编码并核查VUI。GIF48帧4000ms来自实际SDR观看MP4解码。\n\n'
    validation+='静帧抽查、连续人类播放、听审及HDR显示器监看分别记录。自然素材质量、ICC/色适应、HLG非零黑位、母版/动态元数据、感知色域映射、实时/长片及完整剪映等价未验收，38原关闭条件保持。\n\n[算法/约束/使用](../product/HDR_DISPLAY.md) · [全部案例媒体](../product/CASES.md#c50-native-hdr).\n'
    write('docs/validation/HDR显示光实测_2026-10-27.md',validation)
    record=dict(status='documented',cli_version='0.1.40',readme_R_rows=277,prior_R_rows_preserved=271,functions=66,services=21,capabilities=79,goal_complete=False)
    write((out/'verification.json').relative_to(ROOT).as_posix(),json.dumps(record,indent=2)+'\n');print(json.dumps(record))
if __name__=='__main__':main()
