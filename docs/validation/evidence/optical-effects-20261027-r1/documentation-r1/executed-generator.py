"""Synchronize complete trilingual manuals after actual installed/C48 proof."""
from pathlib import Path
import hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/optical-effects-20261027-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d+)\s*\|.*$',s,re.M)}
def after(s,prefix,entry):
    m=list(re.finditer(r'^\| '+prefix+r'\d+\s*\|.*$',s,re.M))[-1]
    return s[:m.end()]+'\n'+entry+s[m.end():]

def main():
    out=BASE/'documentation-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r1/verification.json')
    test=load(BASE/'installed-regression-final-r2/verification.json');case=load(BASE/'case-r3/verification.json')
    assert install['status']=='installed-and-byte-verified' and install['source_file_count']==237
    assert test['status']=='passed' and test['tests']==704 and test['failures']==test['errors']==test['skipped']==0
    assert case['status']=='passed' and case['all_48_decoded_10bit_frames_equal'] and case['all_384000_PCM_equal']
    assert case['animation_tracks']==9 and case['GIF_duration_ms']==4000
    cap_path='docs/product/optical-effects-capabilities-cli-0.1.38.json'
    (ROOT/cap_path).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/cap_path)['data']['capabilities'];assert len(caps)==77
    descriptions={
        '':'新增可编辑 **镜头眩光、漏光和色差**：线性光浮点运算、参数关键帧、原作者时钟、片段及选定序列调整层；CPU参考与实际OpenCL GPU路径已接通。通过 `effects list --query optical` / `effects inspect` 查询约束，用 `timeline compose` 保留参数与动画。四格案例含原图、去除效果的对照和真实GPU输出。',
        '.zh-TW':'新增可編輯 **鏡頭眩光、漏光及色差**：線性光浮點運算、參數關鍵影格、原作者時鐘、片段及選定序列調整層；CPU參考與實際OpenCL GPU路徑已接通。透過 `effects list --query optical` / `effects inspect` 查詢約束，用 `timeline compose` 保留參數及動畫。四格案例包含原圖、移除效果的對照及實際GPU輸出。',
        '.en':'New editable **lens flare, light leaks and chromatic aberration**: linear-light Float32 math, numeric keys, original author clocks, clip effects and selected-sequence adjustments, with CPU references and actual OpenCL GPU execution. Discover constraints with `effects list --query optical` / `effects inspect`; author with `timeline compose`. The four-panel case retains the original image, effects-removed control and actual GPU output.'}
    limits={
        '':'安装版最终704项不同用例通过：全量702项通过，另2项旧目录断言更新后定向重测通过，产品文件未变、无跳过。C48保留9条动画轨，全部48个10bit解码帧及384000个Float32 PCM采样在工程包往返后相同，GIF为实际解码帧、4000ms。艺术化光效已接通；真实镜头求解、自动亮源检测、bloom/halation/深度和完整剪映效果库继续开发。全部259项既有核验及38项原关闭条件保留。',
        '.zh-TW':'安裝版最終704項不同用例通過：全量702項通過，另2項舊目錄斷言更新後定向重測通過，產品檔案未變、無跳過。C48保留9條動畫軌，全部48個10bit解碼影格及384000個Float32 PCM取樣在工程包往返後相同，GIF為實際解碼影格、4000ms。藝術光效已接通；實體鏡頭求解、自動亮源偵測、bloom/halation/深度及完整剪映效果庫持續開發。全部259項既有核驗與38項原關閉條件保留。',
        '.en':'All 704 distinct installed tests pass: 702 full-run successes plus two corrected catalog retests, with unchanged product files and no skips. C48 preserves nine animation tracks, all 48 decoded 10-bit frames and 384000 Float32 PCM scalars after package reimport; the GIF contains actual decoded frames and lasts 4000ms. Physical lens solving, automatic light detection, bloom/halation/depth and the full CapCut effect library remain open. All 259 prior R rows and 38 original closure conditions remain.'}
    features={
        '':'| F64 | 可编辑光学效果与GPU运算 | 眩光核心/条纹/光晕/鬼影、旋转椭圆漏光、径向红蓝色差；全部数值通道关键帧、原作者时钟、片段/区间调整层，CPU/OpenCL。 | `effects list/inspect` → `timeline compose` → preview/render | 明确线性RGB；原alpha位保留，透明隐藏色不渗出；ghosts/edge静态，非物理镜头/自动亮源/bloom。 |',
        '.zh-TW':'| F64 | 可編輯光學效果與GPU運算 | 眩光核心/條紋/光暈/鬼影、旋轉橢圓漏光、徑向紅藍色差；全部數值通道關鍵影格、原作者時鐘、片段/區間調整層，CPU/OpenCL。 | `effects list/inspect` → `timeline compose` → preview/render | 明確線性RGB；原alpha位元保留，透明隱藏色不滲出；ghosts/edge靜態，非實體鏡頭/自動亮源/bloom。 |',
        '.en':'| F64 | Editable GPU optical effects | Flare core/streak/halo/ghosts, rotated elliptical leak and radial red/blue split; all numeric channels animate on original author clocks. Clip/interval adjustments, CPU/OpenCL. | `effects list/inspect` → `timeline compose` → preview/render | Explicit linear RGB; original alpha bits retained; transparent hidden RGB does not bleed. Static ghosts/edge; no physical lens, automatic light detection or bloom. |'}
    gpu_rows={
        '':[
            '| F57 | 原生Float32 GPU执行 | 仿射、普通合成、文字组件/逐词、粒子栅格及三类光学效果；任务自有管道/共享像素，贯通渲染/预览/队列/恢复。 | `projection_acceleration; render; preview; queue` | off/prefer/require；binary64精度/次正规探测，粒子保持Float32；有界控制及所属进程/线程/流清理，其他算子CPU。 |',
            '| F58 | Float32全局/区间调整层 | 全轨含字幕合成后按顺序调色/光效；既有浮点效果与三光学效果、六种插值，选中根只应用一次。 | `settings.adjustments; preview; render; queue` | 明确线性工作域/效果信号；光学可GPU，其余CPU；LUT持锁/包迁移，原作者区间时钟，非完整HDR。 |',
            '| S16 | GPU兼容服务 | 已有原生OpenCL ICD / NVIDIA模型库 | 图投影及独立Float32仿射/普通叠加/字色/逐词/粒子/光学；off/prefer/require，模型auto/cpu/cuda；实际探测/预算/清理 | `render --projection-acceleration; gpu inspect; --device` | RTX3060实测；字形/其他效果/转场等CPU，系统库许可另列。 |'],
        '.zh-TW':[
            '| F57 | 原生Float32 GPU執行 | 仿射、一般合成、文字組件/逐詞、粒子光柵及三類光學效果；任務自有管道/共享像素，貫通渲染/預覽/佇列/恢復。 | `projection_acceleration; render; preview; queue` | off/prefer/require；binary64精度/次正規探測，粒子保留Float32；有界控制及所屬程序/執行緒/串流清理，其他算子CPU。 |',
            '| F58 | Float32全域/區間調整層 | 全軌含字幕合成後依序調色/光效；既有浮點效果及三光學效果、六種插值，選定根僅套用一次。 | `settings.adjustments; preview; render; queue` | 明確線性工作域/效果訊號；光學可GPU，其餘CPU；LUT持鎖/包遷移，原作者區間時鐘，非完整HDR。 |',
            '| S16 | GPU相容服務 | 既有原生OpenCL ICD / NVIDIA模型庫 | 圖投影及獨立Float32仿射/一般疊加/字色/逐詞/粒子/光學；off/prefer/require，模型auto/cpu/cuda；實際探測/預算/清理 | `render --projection-acceleration; gpu inspect; --device` | RTX3060實測；字形/其他效果/轉場等CPU，系統庫授權另列。 |'],
        '.en':[
            '| F57 | Native Float32 GPU execution | Affine/normal composition, text components/word selection, particle rasterization and three optical effects; owned pipes/shared pixels across render/preview/queue/recovery. | `projection_acceleration; render; preview; queue` | off/prefer/require; binary64/subnormal probes, Float32 particle math; bounded control and owned process/thread/stream cleanup. Other operators remain CPU. |',
            '| F58 | Float32 global/interval adjustments | Ordered grading/light effects after all tracks/subtitles; existing float effects plus three optical operators, six easings and one application to the selected root. | `settings.adjustments; preview; render; queue` | Explicit linear signals; optics can use GPU, other effects use CPU. LUT locks/package migration retain interval author time; full HDR remains open. |',
            '| S16 | GPU compatibility | Existing native OpenCL ICD / NVIDIA model libraries | Graph projection; independent Float32 affine/normal over/text/words/particles/optics; off/prefer/require and model auto/cpu/cuda; actual probes/budgets/cleanup | `render --projection-acceleration; gpu inspect; --device` | RTX3060 tested; glyphs, other effects and transitions remain CPU. System-library licenses are separate. |']}
    def synchronize_gpu_rows(s,suffix):
        for entry in gpu_rows[suffix]:
            row_id=entry.split('|')[1].strip()
            s,n=re.subn(r'^\| '+row_id+r' \|.*$',lambda _:entry,s,count=1,flags=re.M);assert n==1,row_id
        return s
    checks={
        '':[
            'CLI0.1.38/local.36离线包：237产品文件与源码一致；最终704不同用例通过（全量702+目录契约定向重测2），无未解决失败/错误/跳过；新增16数值、3实际GPU、6工程集成共25项各计一次。',
            '三类光学效果独立高斯闭式、径向整数采样、预乘透明边缘、65536级alpha/次正规/符号零、六缓动、预算/取消/原子失败已验；同输入CPU/GPU光学实测完全相同。',
            '注册安装版Skill C48：4格、9轨、48帧/12FPS/960×540/4秒；可编辑效果及全48帧10bit、384000 Float32 PCM往返相同；143次真实光学GPU派发及所属资源关闭。',
            '相同解码输入CPU/GPU编码误差≤1个10bit码值；粒子叠加独立保持≤3e-6浮点预算；拆分/倒放左极限、根调整区间、包/本地OTIO、预览失效与队列分别核验。',
            'r39独立工具包：1入口/17模块/77 Skill文件/122包文件；完整校验、隔离注册和29次调用；实际Codex发现联接保持，无新推理或渲染。',
            '三语README完整64功能/21服务、77能力快照、Skill、安装和C48实际GIF/原图/对照/可编辑包同步；259既有核验和38原关闭条件保留，总目标继续开发。'],
        '.zh-TW':[
            'CLI0.1.38/local.36離線包：237產品檔案與原始碼一致；最終704不同用例通過（全量702+目錄契約定向重測2），無未解決失敗/錯誤/跳過；新增16數值、3實際GPU、6工程整合共25項各計一次。',
            '三類光學效果獨立高斯閉式、徑向整數取樣、預乘透明邊緣、65536級alpha/次正規/符號零、六緩動、預算/取消/原子失敗已驗；同輸入CPU/GPU光學實測完全相同。',
            '註冊安裝版Skill C48：4格、9軌、48幀/12FPS/960×540/4秒；可編輯效果與全48幀10bit、384000 Float32 PCM往返相同；143次實際光學GPU派發及所屬資源關閉。',
            '相同解碼輸入CPU/GPU編碼誤差≤1個10bit碼值；粒子疊加獨立維持≤3e-6浮點預算；拆分/倒放左極限、根調整區間、包/本地OTIO、預覽失效與佇列分別核驗。',
            'r39獨立工具包：1入口/17模組/77 Skill檔案/122包檔案；完整校驗、隔離註冊及29次呼叫；實際Codex發現聯接保持，無新推論或渲染。',
            '三語README完整64功能/21服務、77能力快照、Skill、安裝及C48實際GIF/原圖/對照/可編輯包同步；259既有核驗及38原關閉條件保留，總目標持續開發。'],
        '.en':[
            'CLI0.1.38/local.36 offline bundle: 237 product files match source; 704 distinct installed tests pass (702 full-run successes plus two catalog retests), with no unresolved failures/errors/skips. The 25 additions include 16 numeric, three actual GPU and six engineering tests, counted once.',
            'Independent Gaussian closed forms, integer radial maps, premultiplied transparent edges, 65536 alpha levels/subnormals/signed zero, six easings, budgets, cancellation and atomic errors verified; measured optical CPU/GPU output on the same input matches exactly.',
            'Registered installed Skill C48: four panels, nine tracks, 48 frames/12FPS/960×540/four seconds. All editable effects, 48 decoded 10-bit frames and 384000 Float32 PCM scalars match after package import; 143 real optical dispatches with owned resources closed.',
            'CPU/GPU encoding from the same decoded source differs by at most one 10-bit code; particle composition independently stays within its 3e-6 float budget. Split/reverse left limits, root adjustment intervals, package/local OTIO, cache invalidation and persistent queue verified.',
            'Fresh r39 kit: one entry/17 modules/77 Skill files/122 package files. Complete validation, isolated registration and 29 calls retain actual Codex discovery; no new inference or render.',
            'Complete trilingual manuals with 64 functions/21 services, 77 capability snapshots, Skill/install workflows and C48 actual GIF/original/control/editable package synchronized. All 259 prior R rows and 38 closure cells retained; the overall goal remains open.']}
    targets=['installed-regression-final-r2/verification.json','source-optics-r2/verification.json','case-r3/verification.json',
        'installed-regression-final-r2/receipts.json','kit-r1/verification.json','final-delivery-r1/verification.json']
    for suffix in ('','.zh-TW','.en'):
        name='README'+suffix+'.md';s=read(name);old=rows(s,'R');assert len(old)==259
        block='<!-- optical-effects-current -->\n\n**CLI0.1.38 / alpha.4-local.36 / r39 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n'
        block+='[Workflow / usage](docs/product/OPTICAL_EFFECTS.md) · [C48](docs/product/CASES.md#c48-optical-effects) · [Install](docs/releases/CLI_0.1.38_LOCAL.md) · [Evidence](docs/validation/光学效果实测_2026-10-27.md)\n\n'
        block+='![Actual registered Skill GPU optical output](docs/assets/optical-effects-20261027-r3/optical-effects.gif)\n\n'+limits[suffix]+'\n\n<!-- /optical-effects-current -->\n\n'
        marker='<!-- emitter-animation-current -->';assert marker in s
        s=s.replace(marker,block+'<!-- emitter-animation-history -->',1).replace('<!-- /emitter-animation-current -->','<!-- /emitter-animation-history -->',1)
        s=after(s,'F',features[suffix])
        s=synchronize_gpu_rows(s,suffix)
        s=after(s,'R','\n'.join('| R'+str(260+i)+' | 2026-10-27 optical effects | '+d+' | [Evidence](docs/validation/evidence/optical-effects-20261027-r1/'+p+') |' for i,(d,p) in enumerate(zip(checks[suffix],targets))))
        s='\n'.join(l.replace('local.35/final-r1/installed','local.36/final-r1/installed').replace('CLI 0.1.37','CLI 0.1.38')
            if 'local.35/final-r1/installed' in l and not l.startswith('| R') else l for l in s.splitlines())+'\n'
        s=s.replace('[r38 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r38.zip)',
            '[r39 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r39.zip)')
        assert len(rows(s,'F'))==64 and len(rows(s,'S'))==21 and len(rows(s,'K'))==17 and len(rows(s,'R'))==265
        assert all(rows(s,'R')[k]==v for k,v in old.items());write(name,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            path=base+suffix+'.md';s=read(path);relative='OPTICAL_EFFECTS.md' if '/product/' in path else '../product/OPTICAL_EFFECTS.md'
            block='<!-- community-current -->\n\n**CLI0.1.38 / alpha.4-local.36 / r39 kit · 1 Skill / 17 modules / 77 files.**\n\n'+descriptions[suffix]+'\n\n[Optical workflow and constraints]('+relative+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            if base.endswith('CAPABILITIES'):
                s=after(s,'F',features[suffix])
                s=synchronize_gpu_rows(s,suffix)
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if n==0:
                        assert key=='optical_effects';s+='\n'+section+'\n'
                s+='\n[CLI0.1.38 exact installed capability snapshot](optical-effects-capabilities-cli-0.1.38.json).\n'
            write(path,s)
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
    prior=load(ROOT/'docs/validation/evidence/emitter-animation-20261027-r1/installation-final-r1/verification.json')
    for old,new in [('alpha.4-local.35','alpha.4-local.36'),('CLI 0.1.37','CLI 0.1.38'),('r38.zip','r39.zip'),
        ('0.1.37-r38.json','0.1.38-r39.json'),(prior['archive_sha256'],install['archive_sha256']),
        (prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(old,new)
    s+='\nCLI0.1.38/local.36/r39: [optical effects](OPTICAL_EFFECTS.md), [C48 actual editable output](CASES.md#c48-optical-effects), [local installation](../releases/CLI_0.1.38_LOCAL.md).\n';write(p,s)
    release='# CLI0.1.38 · editable optical effects · alpha.4-local.36\n\nLocal tested build; public alpha.3 / CLI0.1.2 remains unchanged.\n\n'
    release+='Application ZIP: `'+Path(install['archive']).relative_to(ROOT).as_posix()+'`\n\nBytes: `'+str(install['archive_bytes'])+'` · SHA256: `'+install['archive_sha256']+'`\n\nManifest: `'+install['manifest_sha256']+'`\n\n'
    release+='Installed: `'+Path(install['installed']).relative_to(ROOT).as_posix()+'`\n\n237 source/installed Python files match; 77 capabilities; 49 effects in catalog 0.10.0; one public Skill/17 modules/77 Skill files. The r39 kit has 122 entries; application/model archives remain separate.\n\n'
    release+='Lens flare, light leak and chromatic aberration use explicit linear working RGB, preserve alpha bits and retain numeric author-clock keys. CPU references and owned OpenCL binary64 kernels are integrated with clips and selected-root intervals. All 704 distinct installed tests pass without skips: 702 full-run successes plus two corrected catalog retests on unchanged product files. C48 retains nine tracks, all 48 decoded 10-bit frames and 384000 PCM scalars after package reimport.\n\n'
    release+='[Install](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Usage/parameters](../product/OPTICAL_EFFECTS.md) · [C48](../product/CASES.md#c48-optical-effects) · [r39 kit](../skills/agent-editor-kit-community-unified-skill-r39.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.38-r39.json) · [Verification](../validation/光学效果实测_2026-10-27.md).\n\n'
    release+='Physical lens solving, automatic light detection, bloom/halation/depth, natural quality and full CapCut equivalence remain open. All 38 original closure conditions remain.\n';write('docs/releases/CLI_0.1.38_LOCAL.md',release)
    p='docs/product/CASES.md';s=read(p);assert 'id="c48-optical-effects"' not in s
    s+='\n<a id="c48-optical-effects"></a>\n\n## C48 · 可编辑光学效果 / Editable optical effects\n\n'
    s+='Registered installed CLI0.1.38 imports an original CC0 product chart and composes four 480×270 panels in 960×540: original, moving lens flare, warm light leak and radial color split. Nine numeric channels remain editable. 48 frames/12FPS/four seconds. Package reimport retains effects/curves, all 48 decoded 10-bit frames and all 384000 Float32 PCM scalars. Each render executes 143 actual optical GPU dispatches; the first frame has zero shifts and skips chromatic work.\n\n'
    s+='![Actual GPU optical output, decoded and labeled](../assets/optical-effects-20261027-r3/optical-effects.gif)\n\n'
    s+='[MP4](../assets/optical-effects-20261027-r3/optical-effects.mp4) · [Lossless master](../assets/optical-effects-20261027-r3/optical-effects.mkv) · [Editable project](../assets/optical-effects-20261027-r3/editable-optical-effects.aevpkg.zip) · [Original PNG](../assets/optical-effects-20261027-r3/original-source.png) · [Without effects](../assets/optical-effects-20261027-r3/before.png) · [At2s](../assets/optical-effects-20261027-r3/contact.png) · [Recipes](../assets/optical-effects-20261027-r3/recipes.json) · [Source/license](../assets/optical-effects-20261027-r3/SOURCE.txt) · [Media manifest](../assets/optical-effects-20261027-r3/media-manifest.json) · [Workflow](OPTICAL_EFFECTS.md) · [Evidence](../validation/光学效果实测_2026-10-27.md).\n\n'
    s+='The MKV is actual installed GPU output, the MP4 is a playable encode, and GIF/contact images use decoded output with labels. Before is a separate GPU render with only optical effects removed. The GIF contains 48 actual frames over 4000ms. This is a silent synthetic diagnostic without external imagery/models. Continuous human playback/listening, natural footage quality and physical lens/full product acceptance remain open.\n';write(p,s)
    for p in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        s=read(p);first=s.index('\n')
        s=s[:first]+'\n\n当前本地 **CLI0.1.38 / alpha.4-local.36 / r39 kit**：[G06原生CPU/GPU光学效果](OPTICAL_EFFECTS.md)已接通眩光/漏光/色差及作者时钟动画，704安装版回归、C48全48帧与完整PCM往返通过。物理镜头、自动亮源、bloom/halation/深度和完整效果库继续开发；38原关闭条件保持。\n'+s[first:];write(p,s)
    p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：',1);first=s.index('\n')
    s=s[:first]+'\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.38 / local.36 / r39 kit** · [Optical effects](product/OPTICAL_EFFECTS.md) · [Install](releases/CLI_0.1.38_LOCAL.md) · [C48](product/CASES.md#c48-optical-effects).\n'+s[first:];write(p,s)
    text='# 光学效果实测 · 2026-10-27\n\nCLI0.1.38 / local.36 / r39。原生Windows，无虚拟化、依赖下载、全局安装或源码回落。\n\n'
    text+='237产品文件与最终安装一致；704安装版测试通过，零失败/错误/跳过。25项新增=16数值+3实际GPU+6工程集成，679既有回归保留，各计一次。C48通过实际注册Skill创建九条光学关键帧轨，全48个10bit帧与384000 Float32 PCM在工程包往返后相同。\n\n## 可复核证据\n\n'
    for title,path in [('Offline build/install','installation-final-r1/verification.json'),('Installed704 regressions','installed-regression-final-r2/verification.json'),
        ('Independent numeric16','source-optics-r2/verification.json'),('Actual source GPU3','source-optics-gpu-r2/verification.json'),
        ('Source integration6','source-optics-integration-r3/verification.json'),('Particle/optical precision diagnostic','composition-diagnostic-r1/verification.json'),
        ('Registered C48 full render/package equality','case-r3/verification.json'),('Activation/registration','activation-final-r1/activation-and-registration.json'),
        ('Fresh isolated r39 kit','kit-r1/verification.json'),('Final delivery audit','final-delivery-r1/verification.json')]:
        text+='- ['+title+'](evidence/optical-effects-20261027-r1/'+path+')\n'
    text+='\n## 独立数值、透明边缘和GPU\n\n高斯中心/轴向/旋转闭式、核心眩光与圆形漏光一致、独立整数径向映射、透明隐藏RGB不渗出、65536级alpha和次正规/符号零逐位保留、零效果位相同、六缓动/跳帧/切片不变、预算/取消和非法输入原子性均已测。GPU使用现有OpenCL ICD；九次命名主探测含三光学执行，旧灰阶/次正规探测保留。实际光学最大误差阈值3e-6，独立随机扩展色/分数采样/透明边界另测。\n\n'
    text+='## 集成与误差归因\n\n相同解码PNG输入的CPU/GPU完整编码≤1个10bit码值，全部PCM相同；带粒子的完整24帧浮点叠加独立要求≤3e-6。诊断实测：同一输入的三光学效果CPU/GPU误差0，已有粒子源直通RGB差1.758337e-6、alpha差1.341105e-7，叠加后完整浮点最大1.639128e-6。此前将不同粒子栅格输入的完整编码直接套≤1码门槛出现3码差，失败原记录保留；未以放宽编码阈值替代同输入算子验证。\n\n'
    text+='连续光学关键帧按原作者时间求值；嵌套倒放在原时钟左极限求值，原生源帧按半开区间取前帧。修正测试中把连续参数误当上一显示帧的错误期望后，24拆分帧和24倒放独立参考帧逐位相同。包/本地OTIO效果及全片保持，预览命中/键变更失效、队列/直接编码、选定根区间只应用一次分别测试。PNG无容器起点时显式声明demux_origin=0；未加入隐式推断。\n\n'
    text+='早期失败留档：数值r1把Float32的0.3与Python双精度字面量逐位比较，已改为原输入对应位；GPU r1暴露控制调用的values命名冲突，改用parameters消息字段后真实派发通过。集成r1另误选OTIO首个空轨，已按clip ID定位；集成r2遗漏静态PNG的显式容器起点，补充测试输入声明后r3通过。失败尝试不计为通过。\n\n'
    text+='最终回归口径：安装版全量实际执行704项，702通过、2处旧目录版本/来源/数量断言失败；仅更新这两个方法的目录契约后，定向重测2项通过。产品237文件自全量运行起未变；AST比较证明其他702用例未改。最终704个不同用例通过，累计706次执行，不是重新单跑704项零失败。原全量失败日志、最终逐用例清单和两项重测均保留；首次清单解析遗漏3条多行用例描述的失败记录也保留。\n\n'
    text+='案例联调r1的模糊optical查询还包含optical_flow别名，后改用精确后端查询；r2示例未显式写末键插值并把四格置于一个禁止重叠的轨道，CLI原子拒绝。r3补足末键linear并创建四个视频轨后完整通过，程序文件没有因此变更。\n\n'
    text+='## 案例和边界\n\nC48原图自行绘制CC0，四格960×540、48帧/12FPS/4秒、九条关键帧；143次光学编辑帧GPU派发/每轮，所有worker/shared/control线程与流关闭。工程包保留完整效果与键，往返全48个10bit帧及384000交错PCM标量相同。GIF来自解码主片而非图像库模拟，恰为4000ms；去除效果的before单独真实GPU渲染。\n\n'
    text+='[案例和全部媒体](../product/CASES.md#c48-optical-effects)包含MP4/MKV/GIF、原图、对照、配方和包。静态检查另记；连续人类播放/听音、自然素材、物理镜头、自动亮源、bloom/halation/深度、完整效果库及全部38原关闭条件保持开放。失败测试原记录保留，不改写为成功。\n'
    write('docs/validation/光学效果实测_2026-10-27.md',text)
    record=dict(status='documented',cli_version='0.1.38',readme_R_rows=265,prior_R_rows_preserved=259,
        functions=64,services=21,capabilities=77,goal_complete=False)
    write((out/'verification.json').relative_to(ROOT).as_posix(),json.dumps(record,indent=2)+'\n');print(json.dumps(record))

if __name__=='__main__':main()
