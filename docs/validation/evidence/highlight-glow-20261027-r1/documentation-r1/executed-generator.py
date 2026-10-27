"""Synchronize complete trilingual manuals without deleting acceptance history."""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/highlight-glow-20261027-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d+)\s*\|.*$',s,re.M)}
def after(s,prefix,entry):
    m=list(re.finditer(r'^\| '+prefix+r'\d+\s*\|.*$',s,re.M))[-1]
    return s[:m.end()]+'\n'+entry+s[m.end():]

def gpu_rows(s,suffix):
    replacements={
        '': [('及三类光学效果','及光学/高光扩散效果'),('与三光学效果','与光学/高光扩散效果'),
             ('光学可GPU，其余CPU','光学/高光扩散可GPU，其余CPU'),('逐词/粒子/光学；','逐词/粒子/光学/高光扩散；')],
        '.zh-TW': [('及三類光學效果','及光學/高光擴散效果'),('及三光學效果','及光學/高光擴散效果'),
                   ('光學可GPU，其餘CPU','光學/高光擴散可GPU，其餘CPU'),('逐詞/粒子/光學；','逐詞/粒子/光學/高光擴散；')],
        '.en': [('three optical effects','optical/highlight-glow effects'),('three optical operators','optical/highlight-glow operators'),
                ('optics can use GPU','optics/highlight glow can use GPU'),('particles/optics;','particles/optics/highlight-glow;')]}
    lines=s.splitlines()
    for i,line in enumerate(lines):
        if re.match(r'^\| (F57|F58|S16) \|',line):
            for old,new in replacements[suffix]:line=line.replace(old,new)
            lines[i]=line
    return '\n'.join(lines)+'\n'

def main():
    out=BASE/'documentation-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r2/verification.json')
    tests=load(BASE/'installed-regression-r2/verification.json');case=load(BASE/'case-r1/verification.json')
    assert install['source_file_count']==239 and tests['status']=='passed' and tests['tests']==734
    assert tests['failures']==tests['errors']==tests['skipped']==0 and tests['frozen_equal'] and tests['test_frozen_equal']
    assert case['status']=='passed' and case['all_48_decoded_10bit_frames_equal'] and case['all_384000_PCM_equal']
    assert case['animation_tracks']==6 and case['GPU']['operations']['glow']==192
    assert case['GIF_duration_ms']==4000
    cap_path='docs/product/highlight-glow-capabilities-cli-0.1.39.json'
    (ROOT/cap_path).write_bytes((BASE/'installation-final-r2/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/cap_path)['data']['capabilities'];assert len(caps)==78
    descriptions={
        '':'新增 **Bloom 高光扩散与 Halation 胶片光晕**：从画面真实高光提取亮源，在明确线性 RGB 域执行软膝阈值、分离高斯邻域扩散、核心抑制与着色叠加。支持作者时钟关键帧、片段及根调整层，CPU 参考和真实 GPU 四阶段实现同步交付。',
        '.zh-TW':'新增 **Bloom 高光擴散與 Halation 膠片光暈**：從畫面實際高光提取亮源，在明確線性 RGB 域執行軟膝閾值、分離高斯鄰域擴散、核心抑制及著色疊加。支援作者時鐘關鍵影格、片段及根調整層，CPU 參考與實際 GPU 四階段實作同步交付。',
        '.en':'New **highlight Bloom and film Halation** extract actual image highlights in explicit linear RGB, with soft-knee thresholds, separable Gaussian neighborhood spread, core suppression and tinted addition. Numeric author-clock keys, clip effects and selected-root adjustments use CPU references or actual four-stage GPU execution.'}
    limits={
        '':'安装版单轮 734 项回归通过、零失败/错误/跳过；新增 21 数值、3 真实 GPU、6 工程集成，共30项。C49四格保留六条数值轨道，工程包往返全48个10bit帧与384000个Float32 PCM相同；每次内容渲染192个glow操作、768个设备kernel（另计启动探测）。真实素材质量、物理胶片、HDR、实时/4K长片、完整效果库及原38项关闭条件继续开发。既有265条核验逐行保留。',
        '.zh-TW':'安裝版單輪 734 項回歸通過、零失敗/錯誤/跳過；新增21數值、3實際GPU、6工程整合，共30項。C49四格保留六條數值軌道，工程包往返全48個10bit影格及384000個Float32 PCM相同；每次內容渲染192個glow操作、768個裝置kernel（啟動探測另計）。自然素材品質、物理膠片、HDR、即時/4K長片、完整效果庫與原38項關閉條件持續開發。既有265條核驗逐行保留。',
        '.en':'A single installed run passes all 734 regressions with zero failures/errors/skips, adding 21 numeric, 3 real GPU and 6 engineering tests. C49 retains six numeric tracks, all 48 decoded 10-bit frames and 384000 Float32 PCM scalars after package import. Each content render uses 192 glow operations/768 device kernels, excluding startup probes. Natural-footage quality, physical film accuracy, HDR, real-time/4K long-form performance, the full effect library and all 38 original closure conditions remain open. All 265 prior R rows are preserved.'}
    features={
        '':'| F65 | 真实高光 Bloom / 胶片 Halation | 软膝阈值提取实际高光→分离高斯扩散→核心抑制/线性着色；可编辑数值轨道和原作者时钟，片段或根区间调整层。 | `effects list/inspect; timeline compose; preview; render; queue` | sigma0…32输入像素；透明/复制边界、原alpha位保持；实际四kernel GPU/CPU参考，有界空间/访问预算；非物理胶片/HDR验收。 |',
        '.zh-TW':'| F65 | 實際高光 Bloom / 膠片 Halation | 軟膝閾值提取實際高光→分離高斯擴散→核心抑制/線性著色；可編輯數值軌道及原作者時鐘，片段或根區間調整層。 | `effects list/inspect; timeline compose; preview; render; queue` | sigma0…32輸入像素；透明/複製邊界、原alpha位元保持；實際四kernel GPU/CPU參考，有界空間/訪問預算；非物理膠片/HDR驗收。 |',
        '.en':'| F65 | Highlight Bloom / film Halation | Actual soft-knee highlight extraction→separable Gaussian spread→core suppression/linear tint; editable numeric author-clock tracks in clips or selected-root adjustment intervals. | `effects list/inspect; timeline compose; preview; render; queue` | sigma0…32 input pixels; transparent/clamp edges; alpha bits preserved; actual four-kernel GPU or CPU reference; bounded workspace/visits; physical film/HDR unaccepted. |'}
    checks={
        '':['CLI0.1.39/local.37离线包239产品文件与源码逐字节相同；734安装版用例单轮全过，零失败/错误/跳过，含30新增项，旧704项保留。',
            '独立二维高斯冲激/软膝能量/基色亮度/阈值单调/胶片去核心、透明亮源与65536级alpha位、六缓动/分块/取消/配额/溢出21项通过。',
            '3项实际GPU核验包含72组效果×边界×半径×基色；每个操作4kernel、原alpha位一致，CPU参考误差≤3e-6，无操作/非法请求原子拒绝和取消资源关闭通过。',
            '6项集成验证同源编码≤1个10bit码、全部PCM、粒子组合≤3e-6、拆分/倒放左极限、包/本地OTIO、预览键失效/队列、根区间仅应用一次。',
            '注册安装版Skill C49：原图/Bloom/Halation/组合四格，6数值轨、48帧/12FPS/4秒；全帧10bit和384000 PCM工程包往返相同，192glow内容操作及所属资源关闭。',
            'r40独立工具包1入口/17模块/78 Skill文件/124包文件，完整校验/隔离注册32次调用；三语README65功能/21服务及全部265既有核验和38原关闭条件保留。'],
        '.zh-TW':['CLI0.1.39/local.37離線包239產品檔案與原始碼逐位元組相同；734安裝版用例單輪全過，零失敗/錯誤/跳過，包含30新增項，舊704項保留。',
            '獨立二維高斯衝激/軟膝能量/基色亮度/閾值單調/膠片去核心、透明亮源及65536級alpha位元、六緩動/分塊/取消/配額/溢出21項通過。',
            '3項實際GPU核驗包含72組效果×邊界×半徑×基色；每操作4kernel、原alpha位元一致，CPU參考誤差≤3e-6，無操作/非法請求原子拒絕及取消資源關閉通過。',
            '6項整合驗證同源編碼≤1個10bit碼、完整PCM、粒子組合≤3e-6、拆分/倒放左極限、包/本地OTIO、預覽鍵失效/佇列、根區間僅套用一次。',
            '註冊安裝版Skill C49：原圖/Bloom/Halation/組合四格，6數值軌、48影格/12FPS/4秒；全影格10bit及384000 PCM工程包往返相同，192glow內容操作及所屬資源關閉。',
            'r40獨立工具包1入口/17模組/78 Skill檔案/124包檔案，完整校驗/隔離註冊32次呼叫；三語README65功能/21服務及所有265既有核驗和38原關閉條件保留。'],
        '.en':['CLI0.1.39/local.37 offline bundle: 239 product files byte-match source; a single 734-test installed run passes with zero failures/errors/skips, preserving 704 prior cases and adding 30.',
            '21 numeric checks cover an independent 2D Gaussian impulse, soft-knee energy, primary-dependent luminance, monotonic thresholds, core suppression, hidden RGB/65536 alpha bits, easings, tiles, cancellation, quotas and overflow.',
            'Three real-GPU tests include 72 effect/edge/radius/primaries combinations; four kernels per operation, exact alpha bits and CPU error≤3e-6; noop/invalid atomic rejection and owned cancellation cleanup pass.',
            'Six integration tests cover same-source encoding within one 10-bit code/full PCM, particle composition≤3e-6, split/reverse left limits, package/local OTIO, preview invalidation/queue and one selected-root interval application.',
            'Registered installed Skill C49: original/Bloom/Halation/combined, six numeric tracks, 48 frames/12FPS/four seconds. All 10-bit frames and 384000 PCM scalars match after package import; 192 content glow operations and owned cleanup verified.',
            'Fresh r40 kit: one entry/17 modules/78 Skill files/124 entries, complete verification/isolated registration and 32 calls. Trilingual 65-function/21-service manuals retain all 265 prior R rows and 38 original closure cells.']}
    targets=['installed-regression-r2/verification.json','source-glow-r2/verification.json','source-glow-gpu-r2/verification.json',
             'installed-regression-r2/receipts.json','case-r1/verification.json','kit-r1/verification.json']
    for suffix in ('','.zh-TW','.en'):
        name='README'+suffix+'.md';s=read(name);old=rows(s,'R');assert len(old)==265
        block='<!-- highlight-glow-current -->\n\n**CLI0.1.39 / alpha.4-local.37 / r40 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n'
        block+='[Workflow / usage](docs/product/HIGHLIGHT_GLOW.md) · [C49](docs/product/CASES.md#c49-highlight-glow) · [Install](docs/releases/CLI_0.1.39_LOCAL.md) · [Evidence](docs/validation/高光扩散实测_2026-10-27.md)\n\n'
        block+='![Actual registered Skill GPU highlight output](docs/assets/highlight-glow-20261027-r1/highlight-glow.gif)\n\n'+limits[suffix]+'\n\n<!-- /highlight-glow-current -->\n\n'
        assert '<!-- optical-effects-current -->' in s
        s=s.replace('<!-- optical-effects-current -->',block+'<!-- optical-effects-history -->',1).replace('<!-- /optical-effects-current -->','<!-- /optical-effects-history -->',1)
        s=gpu_rows(after(s,'F',features[suffix]),suffix)
        s=after(s,'R','\n'.join('| R'+str(266+i)+' | 2026-10-27 highlight glow | '+d+' | [Evidence](docs/validation/evidence/highlight-glow-20261027-r1/'+p+') |' for i,(d,p) in enumerate(zip(checks[suffix],targets))))
        s='\n'.join(l.replace('local.36/final-r1/installed','local.37/final-r2/installed').replace('CLI 0.1.38','CLI 0.1.39')
            if 'local.36/final-r1/installed' in l and not l.startswith('| R') else l for l in s.splitlines())+'\n'
        s=s.replace('[r39 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r39.zip)','[r40 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r40.zip)')
        assert len(rows(s,'F'))==65 and len(rows(s,'S'))==21 and len(rows(s,'K'))==17 and len(rows(s,'R'))==271
        assert all(rows(s,'R')[k]==v for k,v in old.items());write(name,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            path=base+suffix+'.md';s=read(path);relative='HIGHLIGHT_GLOW.md' if '/product/' in path else '../product/HIGHLIGHT_GLOW.md'
            block='<!-- community-current -->\n\n**CLI0.1.39 / alpha.4-local.37 / r40 kit · 1 Skill / 17 modules / 78 files.**\n\n'+descriptions[suffix]+'\n\n[Highlight workflow and constraints]('+relative+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            if base.endswith('CAPABILITIES'):
                s=gpu_rows(after(s,'F',features[suffix]),suffix)
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if n==0:assert key=='highlight_glow';s+='\n'+section+'\n'
                s+='\n[CLI0.1.39 exact installed capability snapshot](highlight-glow-capabilities-cli-0.1.39.json).\n'
            write(path,s)
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
    prior=load(ROOT/'docs/validation/evidence/optical-effects-20261027-r1/installation-final-r1/verification.json')
    for old,new in [('alpha.4-local.36','alpha.4-local.37'),('CLI 0.1.38','CLI 0.1.39'),('r39.zip','r40.zip'),
        ('0.1.38-r39.json','0.1.39-r40.json'),(prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(old,new)
    s=s.replace('alpha.4-local.37/candidate-r1','alpha.4-local.37/candidate-r2').replace('alpha.4-local.37/final-r1','alpha.4-local.37/final-r2')
    s+='\nCLI0.1.39/local.37/r40: [highlight Bloom and Halation](HIGHLIGHT_GLOW.md), [C49 actual editable output](CASES.md#c49-highlight-glow), [local installation](../releases/CLI_0.1.39_LOCAL.md).\n';write(p,s)
    release='# CLI0.1.39 · highlight Bloom / film Halation · alpha.4-local.37\n\nLocal tested build; public alpha.3 / CLI0.1.2 remains unchanged.\n\n'
    release+='Application ZIP: `'+Path(install['archive']).relative_to(ROOT).as_posix()+'`\n\nBytes: `'+str(install['archive_bytes'])+'` · SHA256: `'+install['archive_sha256']+'`\n\nManifest: `'+install['manifest_sha256']+'`\n\nInstalled: `'+Path(install['installed']).relative_to(ROOT).as_posix()+'`\n\n'
    release+='239 source/installed Python files match; 78 capabilities; 51 effects in catalog 0.11.0; one public Skill/17 modules/78 Skill files. The r40 kit has 124 entries; application/model archives remain separate. A single installed run passes all 734 tests with zero failures/errors/skips. C49 preserves six tracks, all 48 decoded 10-bit frames and 384000 PCM scalars after package import.\n\n'
    release+='[Installation and launch](../product/COMMUNITY_LOCAL_DELIVERY.md) → [Inspect/edit/preview/render workflow](../product/HIGHLIGHT_GLOW.md) → [C49 editable example](../product/CASES.md#c49-highlight-glow). [r40 kit](../skills/agent-editor-kit-community-unified-skill-r40.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.39-r40.json) · [Verification](../validation/高光扩散实测_2026-10-27.md).\n\n'
    release+='Highlights use explicit linear luminance, soft-knee extraction and normalized FIR spread. Four actual GPU kernels retain intermediates on device; CPU uses matching Float32 boundaries. Numeric keys, selected-root intervals, transparent edges and alpha bits are retained. Physical film/lens accuracy, natural footage, HDR, real-time/4K performance and full CapCut parity remain open. All38 original closure conditions remain.\n';write('docs/releases/CLI_0.1.39_LOCAL.md',release)
    p='docs/product/CASES.md';s=read(p);assert 'id="c49-highlight-glow"' not in s
    s+='\n<a id="c49-highlight-glow"></a>\n\n## C49 · 高光扩散与胶片光晕 / Bloom and Halation\n\n'
    s+='Registered installed CLI0.1.39 imports an original CC0 product/highlight chart into four 480×270 panels in 960×540: original, Bloom, warm core-suppressed Halation and both combined. Six numeric tracks remain editable. 48 frames/12FPS/four seconds. Package reimport retains all effects/keys, all 48 decoded 10-bit frames and 384000 Float32 PCM scalars. Each content render executes192 glow operations/768 actual kernels, excluding startup probes; all owned resources close.\n\n'
    s+='![Actual GPU highlight output, decoded and labeled](../assets/highlight-glow-20261027-r1/highlight-glow.gif)\n\n'
    media='../assets/highlight-glow-20261027-r1/'
    s+=' · '.join('['+label+']('+media+name+')' for label,name in [('MP4','highlight-glow.mp4'),('Lossless master','highlight-glow.mkv'),('Editable project','editable-highlight-glow.aevpkg.zip'),('Original PNG','original-source.png'),('Without effects','before.png'),('At2s','contact.png'),('Recipes','recipes.json'),('Source/license','SOURCE.txt'),('Media manifest','media-manifest.json')])+'\n\n'
    s+='[Workflow](HIGHLIGHT_GLOW.md) · [Evidence](../validation/高光扩散实测_2026-10-27.md). The MKV is actual installed GPU output; the MP4 is a playable encode and GIF/contact images add labels to decoded master frames. Before is a separate effects-removed GPU render. GIF 48 frames/4000ms. This silent synthetic diagnostic has no external footage/model; still review, continuous human playback/listening, natural quality and physical film/full product acceptance are separate.\n';write(p,s)
    note='当前本地 **CLI0.1.39 / alpha.4-local.37 / r40 kit**：[G06真实高光Bloom/Halation](HIGHLIGHT_GLOW.md)已接通CPU/实际四阶段GPU、数值关键帧及根区间调整层；734安装版回归单轮通过，C49六轨全48帧及完整PCM工程包往返相同。物理胶片/镜头、深度/完整效果库、自然质量/HDR及38原关闭条件继续开发。'
    for p in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        s=read(p);first=s.index('\n');s=s[:first]+'\n\n'+note+'\n'+s[first:];write(p,s)
    p='docs/product/GOAL_GAPS_20261025.md';s=read(p)
    s=s.replace('| G06 | 特效与复合效果库 | 46 个可查询效果算子 |',
        '| G06 | 特效与复合效果库 | 51个可查询算子、6种可编辑粒子、解析光效及Bloom/Halation CPU/GPU |')
    write(p,s)
    p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：',1);first=s.index('\n')
    s=s[:first]+'\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.39 / local.37 / r40 kit** · [Highlight glow](product/HIGHLIGHT_GLOW.md) · [Install](releases/CLI_0.1.39_LOCAL.md) · [C49](product/CASES.md#c49-highlight-glow).\n'+s[first:];write(p,s)
    text='# 高光扩散实测 · 2026-10-27\n\nCLI0.1.39 / local.37 / r40。原生Windows，无虚拟化、依赖下载、全局安装或源码回落。\n\n'
    text+='239产品文件与安装逐字节相同；734安装版用例单轮通过，零失败/错误/跳过。30新增=21数值+3实际GPU+6工程集成，原704项保留，逐项只计一次。\n\n'
    for title,path in [('Offline build/install','installation-final-r2/verification.json'),('Installed734 regressions','installed-regression-r2/verification.json'),('Numeric21','source-glow-r2/verification.json'),('Actual GPU3','source-glow-gpu-r2/verification.json'),('Integration6','source-glow-integration-r1/verification.json'),('Registered C49','case-r1/verification.json'),('Activation/registration','activation-final-r1/activation-and-registration.json'),('Fresh isolated r40 kit','kit-r1/verification.json'),('Delivery audit','final-delivery-r1/verification.json')]:
        text+='- ['+title+'](evidence/highlight-glow-20261027-r1/'+path+')\n'
    text+='\n独立二维冲激高斯参考、软膝能量、D65基色亮度/阈值单调、核心抑制/色调比例、隐藏透明RGB、覆盖率能量、边界、零sigma、65536级alpha与次正规/负零、六插值/分块/跳帧、参数/曲线/配额/取消/溢出均已验。GPU在72组效果/边界/半径/基色组合上与CPU参考误差≤3e-6，alpha位相同，每组四kernel；无操作不派发，错误请求原子拒绝，取消关闭所属worker/shared/control线程及流。\n\n'
    text+='首个候选的733项完整回归保留：其中一项旧目录断言把整个optical类别误限于原来的三个解析算子，现改为按两个明确后端分别验证3+2个算子；没有删减功能断言。额外边界检查复现合法radius=1e-160的Python幂平方溢出，改为IEEE乘法使极小半径稳定收敛至单点核，新增独立回归，并在实际GPU矩阵中加入1e-160和最小正次正规sigma。最终r2离线候选重新完整执行734项，结果与早期候选分别留档，不把旧失败改写成通过。\n\n[原完整候选记录](evidence/highlight-glow-20261027-r1/installed-regression-r1/verification.json) · [极小半径复现及修正](evidence/highlight-glow-20261027-r1/tiny-radius-correction-r1/verification.json).\n\n'
    text+='同解码源CPU/GPU编码≤1个10bit码、全部PCM相同；粒子组合保持≤3e-6浮点预算，拆分及嵌套倒放原作者连续左极限、包/本地OTIO、预览缓存键与队列、根区间仅应用一次均经过实际集成。C49经实际注册Skill创建，六条数值轨、四格960×540、48帧/12FPS/4秒；往返全48个10bit帧和384000交错Float32 PCM标量相同，静音。每轮192glow操作/768编辑帧kernel；启动主探测17和次正规辅助探测另计。三个中间表面留在显存，只下载最终图。\n\n'
    text+='GIF来自真实解码输出，48帧/4000ms，标签后加；before为移除效果后单独GPU渲染。原图自行绘制CC0，配方与实现MIT，无外部素材和模型。静帧检查另记；连续人类播放、听音、自然素材质量、物理胶片/镜头、HDR、实时/4K长片及完整效果库未验收，全部38原关闭条件保留。\n\n[全部媒体、来源与可编辑包](../product/CASES.md#c49-highlight-glow) · [参数/算法/使用](../product/HIGHLIGHT_GLOW.md).\n'
    write('docs/validation/高光扩散实测_2026-10-27.md',text)
    record=dict(status='documented',cli_version='0.1.39',readme_R_rows=271,prior_R_rows_preserved=265,
                functions=65,services=21,capabilities=78,goal_complete=False)
    write((out/'verification.json').relative_to(ROOT).as_posix(),json.dumps(record,indent=2)+'\n');print(json.dumps(record))

if __name__=='__main__':main()
