"""Update full trilingual docs only after installed tests and actual C47 proof."""
from pathlib import Path
import hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/emitter-animation-20261027-r1'
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
    test=load(BASE/'installed-regression-r1/verification.json');case=load(BASE/'case-r1/verification.json')
    assert install['status']=='installed-and-byte-verified' and install['source_file_count']==235
    assert test['status']=='passed' and test['tests']==679 and test['failures']==test['errors']==test['skipped']==0
    assert case['status']=='passed' and case['all_48_decoded_10bit_frames_equal'] and case['all_384000_PCM_equal']
    assert case['animation_tracks']==14 and case['GIF_duration_ms']==4000
    cap_path='docs/product/emitter-animation-capabilities-cli-0.1.37.json'
    (ROOT/cap_path).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/cap_path)['data']['capabilities'];assert len(caps)==76
    descriptions={
        '':'新增 **21 项发射器属性关键帧**：积分发射率、出生时的运动/寿命、源时间上的颜色/大小/形状等外观，支持六种插值和可暂停发射。`vfx animation-properties` 查询约束，`vfx animate` 添加、显式替换或移除单条属性；原始源时钟贯穿裁切、倒放、嵌套、预览、队列和工程包。四格案例由已注册安装版 Skill 实际 GPU 渲染。',
        '.zh-TW':'新增 **21 項發射器屬性關鍵影格**：積分發射率、出生時的運動/壽命、源時間上的顏色/大小/形狀等外觀，支援六種插值與暫停發射。`vfx animation-properties` 查詢約束，`vfx animate` 新增、明確替換或移除單條屬性；原始源時鐘貫穿裁切、倒放、巢狀、預覽、佇列及工程包。四格案例由已註冊安裝版 Skill 實際 GPU 渲染。',
        '.en':'New **keyframes for all 21 emitter properties**: integrated birth rate, motion/lifetime sampled at birth and live color/size/shape, with six easing modes and emission pauses. Discover constraints through `vfx animation-properties`; add, explicitly replace or remove a property with `vfx animate`. The original source clock survives trim, reverse, nesting, preview, queues and packages. The four-cell case is actual registered installed Skill GPU output.'}
    limits={
        '':'安装版 679 项回归通过、零跳过；C47 的 14 条属性轨道和全部 48 个 10bit 解码帧、384000 个 Float32 PCM 采样在工程包回读后相同。GIF 为实际渲染帧，4 秒。二维发射器动画已接通；3D、碰撞、深度、流体及完整剪映特效库仍待补齐。保留全部 253 项历史核验与 38 项原关闭条件。',
        '.zh-TW':'安裝版 679 項回歸通過、零跳過；C47 的 14 條屬性軌道和全部 48 個 10bit 解碼影格、384000 個 Float32 PCM 取樣在工程包回讀後相同。GIF 為實際渲染影格，4 秒。二維發射器動畫已接通；3D、碰撞、深度、流體及完整剪映特效庫仍待補齊。保留全部 253 項歷史核驗與 38 項原關閉條件。',
        '.en':'All 679 installed regressions pass with zero skips. C47 retains 14 tracks, all 48 decoded 10-bit frames and all 384000 Float32 PCM scalars after package reimport. The GIF contains actual rendered frames over four seconds. 3-D, collisions, depth, fluids and the complete CapCut-scale effect library remain open; all 253 earlier R rows and 38 original closure conditions remain.'}
    features={
        '':'| F63 | 可编辑程序化粒子与发射器动画 | 六种原创建效配方、五形状、seed/独立CFR；21属性源时钟关键帧、六种缓动、发射暂停；真实GPU栅格化。剪辑/预览/队列/包/本地OTIO贯通。 | `vfx list/inspect/apply/update/show/animation-properties/animate` | CPU积分与出生采样，GPU绘制；64点/属性、16发射器、4096预留活粒子；无3D/碰撞/深度。 |',
        '.zh-TW':'| F63 | 可編輯程序化粒子與發射器動畫 | 六種原創配方、五形狀、seed/獨立CFR；21屬性源時鐘關鍵影格、六種緩動、暫停發射；實際GPU光柵化。剪輯/預覽/佇列/包/本地OTIO貫通。 | `vfx list/inspect/apply/update/show/animation-properties/animate` | CPU積分與出生取樣，GPU繪製；64點/屬性、16發射器、4096預留活粒子；無3D/碰撞/深度。 |',
        '.en':'| F63 | Editable particles and emitter animation | Six original recipes/five shapes/seed/native CFR;21 source-clock animated properties,six easings,emission pauses and actual GPU rasterization. Editing/preview/queue/package/local OTIO. | `vfx list/inspect/apply/update/show/animation-properties/animate` | CPU rate integration/birth evaluation,GPU painting;64 points/property,16 emitters,4096 reserved live particles;no3-D/collision/depth. |'}
    checks={
        '':[
            'CLI0.1.37/local.35离线安装包：235产品文件与源码一致；679项安装版回归通过、零失败/错误/跳过，包含18项新数值/CLI、1项新实际GPU及4项新工程集成，不重复加总。',
            '21属性与原始源时钟：独立积分公式、六缓动、暂停/预热、精确同时出生与hold边界、跳帧/缓存一致、保守资源预算及取消已测；旧静态源恒值关键帧逐像素相同。',
            '实际注册Skill C47：14轨、4格、48帧/12FPS/640×360/4秒；导出回读所有轨道、48帧10bit与完整384000 Float32 PCM相同，实际GPU进程/线程/流/共享段关闭。',
            '单属性增改删、显式replace、轨道锁、快照、dry-run、文件内容幂等与失败原子性；真实编码CPU/GPU、工程包/本地OTIO、拆分/嵌套倒放、预览失效及持久队列已验。',
            'r38独立工具包：1入口/17模块/76 Skill文件/120包文件；新目录完整校验、隔离注册及25次调用，原Codex发现联接保持；无新推理或渲染。',
            '三语README完整63功能/21服务、76能力快照、Skill、安装与C47案例/GIF/可编辑包已更新；253历史核验及38原关闭条件保持，总目标仍未完成。'],
        '.zh-TW':[
            'CLI0.1.37/local.35離線安裝包：235產品檔案與原始碼一致；679項安裝版回歸通過、零失敗/錯誤/跳過，包含18項新數值/CLI、1項新實際GPU及4項新工程整合，不重複加總。',
            '21屬性與原始源時鐘：獨立積分公式、六緩動、暫停/預熱、精確同時出生與hold邊界、跳幀/快取一致、保守資源預算及取消已測；舊靜態源恆值關鍵影格逐像素相同。',
            '實際註冊Skill C47：14軌、4格、48幀/12FPS/640×360/4秒；匯出回讀所有軌道、48幀10bit與完整384000 Float32 PCM相同，實際GPU程序/執行緒/串流/共享段關閉。',
            '單屬性增改刪、明確replace、軌道鎖、快照、dry-run、檔案內容冪等與失敗原子性；實際編碼CPU/GPU、工程包/本地OTIO、拆分/巢狀倒放、預覽失效及持久佇列已驗。',
            'r38獨立工具包：1入口/17模組/76 Skill檔案/120包檔案；新目錄完整校驗、隔離註冊及25次呼叫，原Codex發現聯接保持；無新推論或渲染。',
            '三語README完整63功能/21服務、76能力快照、Skill、安裝及C47案例/GIF/可編輯包已更新；253歷史核驗與38原關閉條件保留，總目標仍未完成。'],
        '.en':[
            'CLI0.1.37/local.35 offline bundle:235 product files match source;679 installed regressions pass with zero failures/errors/skips,including18 new numeric/CLI,one new actual GPU andfour new integration tests,counted once.',
            '21 original-source-clock properties tested with independent integrals,six easings,pauses/prewarm,exact birth/hold coincidences,seek/cache invariance,conservative admission and cancellation;constant keys reproduce old static pixels exactly.',
            'Actual registered Skill C47:14 tracks,four panels,48frames/12FPS/640×360/four seconds;package reimport retains all tracks,48 decoded10bit frames andall384000 Float32 PCM scalars. Owned GPU process/thread/stream/shared handles closed.',
            'Single-property add/replace/remove,locks,snapshots,dry-run,file-content idempotency andatomic errors;actual CPU/GPU encoding,package/local OTIO,split/nested reverse,preview invalidation andpersistent queue verified.',
            'Fresh r38 kit:one entry/17 modules/76 Skill files/120 package files,complete pack checks,isolated registration and25 calls retain actual Codex discovery;no new inference or render.',
            'Complete trilingual63-function/21-service manuals,76 capability snapshots,Skill/install workflows andC47 actual GIF/editable package synchronized;all253 prior R rows/38 closure cells retained andoverall goal remains open.']}
    targets=['installed-regression-r1/verification.json','source-emitters-r2/verification.json','case-r1/verification.json',
             'installed-regression-r1/receipts.json','kit-r1/verification.json','final-delivery-r1/verification.json']
    for suffix in ('','.zh-TW','.en'):
        name='README'+suffix+'.md';s=read(name);old=rows(s,'R');assert len(old)==253
        block='<!-- emitter-animation-current -->\n\n**CLI0.1.37 / alpha.4-local.35 / r38 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n'
        block+='[Workflow / usage](docs/product/EMITTER_ANIMATION.md) · [C47](docs/product/CASES.md#c47-emitter-animation) · [Install](docs/releases/CLI_0.1.37_LOCAL.md) · [Evidence](docs/validation/发射器关键帧实测_2026-10-27.md)\n\n'
        block+='![Actual registered Skill GPU output, decoded and labeled](docs/assets/emitter-animation-20261027-r1/emitter-animation.gif)\n\n'+limits[suffix]+'\n\n<!-- /emitter-animation-current -->\n\n'
        marker='<!-- gpu-dispatch-current -->';assert marker in s
        s=s.replace(marker,block+'<!-- gpu-dispatch-history -->',1).replace('<!-- /gpu-dispatch-current -->','<!-- /gpu-dispatch-history -->',1)
        # Identify old limitations by their historical release instead of implying
        # they still constrain the new installed version; original R rows stay exact.
        s=s.replace('当前为二维诊断效果；没有三维碰撞、深度遮挡、流体或发射器参数关键帧。',
            'CLI0.1.35当时为二维诊断效果，未包含发射器参数关键帧；CLI0.1.37已补齐。三维碰撞、深度遮挡和流体仍未实现。')
        s=s.replace('目前為二維診斷效果；沒有三維碰撞、深度遮擋、流體或發射器參數關鍵幀。',
            'CLI0.1.35當時為二維診斷效果，未含發射器參數關鍵影格；CLI0.1.37已補齊。三維碰撞、深度遮擋及流體仍未實作。')
        s=s.replace('This is a 2-D diagnostic effect core. 3-D/collisions, depth occlusion, fluids and emitter-parameter keyframes remain open.',
            'CLI0.1.35 was a 2-D diagnostic core without emitter keyframes; CLI0.1.37 adds them. 3-D/collisions, depth occlusion and fluids remain open.')
        s=re.sub(r'^\| F63 \|.*$',lambda _:features[suffix],s,count=1,flags=re.M)
        s=after(s,'R','\n'.join('| R'+str(254+i)+' | 2026-10-27 emitter animation | '+d+' | [Evidence](docs/validation/evidence/emitter-animation-20261027-r1/'+p+') |' for i,(d,p) in enumerate(zip(checks[suffix],targets))))
        s='\n'.join(l.replace('local.34/final-r1/installed','local.35/final-r1/installed').replace('CLI 0.1.36','CLI 0.1.37')
                    if 'local.34/final-r1/installed' in l and not l.startswith('| R') else l for l in s.splitlines())+'\n'
        s=s.replace('[r28 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r28.zip)',
                    '[r38 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r38.zip)')
        assert len(rows(s,'F'))==63 and len(rows(s,'S'))==21 and len(rows(s,'K'))==17 and len(rows(s,'R'))==259
        assert all(rows(s,'R')[k]==v for k,v in old.items());write(name,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            path=base+suffix+'.md';s=read(path);relative='EMITTER_ANIMATION.md' if '/product/' in path else '../product/EMITTER_ANIMATION.md'
            block='<!-- community-current -->\n\n**CLI0.1.37 / alpha.4-local.35 / r38 kit · 1 Skill / 17 modules / 76 files.**\n\n'+descriptions[suffix]+'\n\n[Emitter workflow and limits]('+relative+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            if base.endswith('CAPABILITIES'):
                s=re.sub(r'^\| F63 \|.*$',lambda _:features[suffix],s,count=1,flags=re.M)
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S);assert n==1,key
                s+='\n[CLI0.1.37 exact installed capability snapshot](emitter-animation-capabilities-cli-0.1.37.json).\n'
            write(path,s)
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
    prior=load(ROOT/'docs/validation/evidence/gpu-dispatch-20261027-r1/installation-final-r1/verification.json')
    for old,new in [('alpha.4-local.34','alpha.4-local.35'),('CLI 0.1.36','CLI 0.1.37'),('r37.zip','r38.zip'),
        ('0.1.36-r37.json','0.1.37-r38.json'),(prior['archive_sha256'],install['archive_sha256']),
        (prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(old,new)
    s+='\nCLI0.1.37/local.35/r38: [emitter keyframes](EMITTER_ANIMATION.md), [C47 actual editable output](CASES.md#c47-emitter-animation), [local installation](../releases/CLI_0.1.37_LOCAL.md).\n';write(p,s)
    release='# CLI0.1.37 · emitter keyframes · alpha.4-local.35\n\nLocal tested build; public alpha.3 / CLI0.1.2 remains unchanged.\n\n'
    release+='Application ZIP: `'+Path(install['archive']).relative_to(ROOT).as_posix()+'`\n\nBytes: `'+str(install['archive_bytes'])+'` · SHA256: `'+install['archive_sha256']+'`\n\nManifest: `'+install['manifest_sha256']+'`\n\n'
    release+='Installed: `'+Path(install['installed']).relative_to(ROOT).as_posix()+'`\n\n235 source/installed Python files match;76 capability declarations;one public Skill/17 modules/76 Skill files. r38 kit contains120 files and keeps application/model archives separate.\n\n'
    release+='21 emitter properties,six easing modes,integrated zero-capable rate,birth-time motion/lifetime andlive linear-light appearance;add/replace/remove CLI with normal atomic project semantics.679 installed tests pass without skips. C47 authors14 tracks;all48 decoded10bit frames andall384000 PCM scalars equal after package import.\n\n'
    release+='[Verified installation](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Usage and constraints](../product/EMITTER_ANIMATION.md) · [C47 actual output](../product/CASES.md#c47-emitter-animation) · [r38 kit](../skills/agent-editor-kit-community-unified-skill-r38.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.37-r38.json) · [Verification](../validation/发射器关键帧实测_2026-10-27.md).\n\n'
    release+='2-D analytic emitters;no3-D/collision/depth/fluids/full effect-library acceptance. All38 original closure conditions remain.\n';write('docs/releases/CLI_0.1.37_LOCAL.md',release)
    p='docs/product/CASES.md';s=read(p);assert 'id="c47-emitter-animation"' not in s
    s+='\n<a id="c47-emitter-animation"></a>\n\n## C47 · 发射器关键帧 / Emitter animation\n\n'
    s+='Registered installed CLI0.1.37 authors14 source-clock tracks across four320×180 panels in a640×360 project: moving trail,paused confetti,live color/size/shape andstar easing.48frames/12FPS/four seconds. Package reimport retains alltracks,all48 decoded10bit frames andcomplete384000 Float32 PCM scalars.\n\n'
    s+='![Actual GPU output, decoded and labeled](../assets/emitter-animation-20261027-r1/emitter-animation.gif)\n\n'
    s+='[Actual MP4](../assets/emitter-animation-20261027-r1/emitter-animation.mp4) · [Lossless master](../assets/emitter-animation-20261027-r1/emitter-animation.mkv) · [Editable project](../assets/emitter-animation-20261027-r1/editable-emitter-animation.aevpkg.zip) · [Without tracks](../assets/emitter-animation-20261027-r1/before.png) · [At2s](../assets/emitter-animation-20261027-r1/contact.png) · [Recipes](../assets/emitter-animation-20261027-r1/recipes.json) · [Source/license](../assets/emitter-animation-20261027-r1/SOURCE.txt) · [Media manifest](../assets/emitter-animation-20261027-r1/media-manifest.json) · [Workflow](EMITTER_ANIMATION.md) · [Evidence](../validation/发射器关键帧实测_2026-10-27.md).\n\n'
    s+='Original synthetic scene;no external media/models. MKV is actual GPU render,MP4 is a playable encode,GIF/contact add labels to decoded master frames. before.png comes from a separate GPU render with only emitter tracks removed. GIF duration is exactly4000ms. Silent diagnostic audio;continuous human playback/listening andnatural-footage/full-product acceptance remain open.\n';write(p,s)
    for p in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        s=read(p);first=s.index('\n')
        s=s[:first]+'\n\n当前本地 **CLI0.1.37 / alpha.4-local.35 / r38 kit**：[G06发射器21属性源时钟动画](EMITTER_ANIMATION.md)已接通，679项安装版回归、C47完整48帧及PCM工程包往返通过。3D/碰撞/深度/流体与完整特效库继续开发，38原关闭条件保持。\n'+s[first:];write(p,s)
    p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：',1);first=s.index('\n')
    s=s[:first]+'\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.37 / local.35 / r38 kit** · [Emitter animation](product/EMITTER_ANIMATION.md) · [Install](releases/CLI_0.1.37_LOCAL.md) · [C47](product/CASES.md#c47-emitter-animation).\n'+s[first:];write(p,s)
    text='# 发射器关键帧实测 · 2026-10-27\n\nCLI0.1.37 / local.35 / r38。原生Windows，无虚拟化、依赖下载、全局安装或源码回落。\n\n'
    text+='235产品文件与最终安装一致。679项安装版回归通过，零失败/错误/跳过；其中18新数值/CLI、1新实际GPU、4新工程集成与656旧回归各计一次。C47实际注册Skill创建14条动画轨，工程包往返所有48个10bit解码帧及完整384000 Float32 PCM相同。\n\n'
    text+='## 可复核证据\n\n'
    for title,path in [('Offline build/install/source identity','installation-final-r1/verification.json'),('Installed679 regression','installed-regression-r1/verification.json'),
        ('Independent numeric/CLI18','source-emitters-r2/verification.json'),('Actual source GPU','source-emitter-gpu-r1/verification.json'),
        ('Source engineering integration4','source-emitter-integration-r1/verification.json'),('Registered C47 full render/package equality','case-r1/verification.json'),
        ('Actual runtime activation/registration','activation-final-r1/activation-and-registration.json'),('Fresh isolated r38 kit','kit-r1/verification.json'),
        ('Final delivery audit','final-delivery-r1/verification.json')]:text+='- ['+title+'](evidence/emitter-animation-20261027-r1/'+path+')\n'
    text+='\n## 数值和时钟\n\n独立公式校验线性rate积分2t+t²及逆根；三种多项式缓动积分使用闭式期望，Bezier按公共32段查表独立梯形积分比对。精确同时出生/hold边界、恒值曲线旧静态逐像素一致、负ID预热、rate零/暂停、出生寿命/运动不回写及外观线性光采样均测。非线性根为64次有理二分下界，精度不是无限；出生样本有本地有界缓存并轮询取消。\n\n'
    text+='## 实际媒体与工程\n\n源GPU测试逐24帧对比预乘光及alpha，阈值3e-6；整片CPU/GPU真实编码与全部PCM、工程包/本地OTIO、拆分/嵌套反向24帧、预览命中/曲线变更失效、持久队列/直接编码一致分别核验。C47有14动画轨/48帧/12FPS/640×360/4秒；全部10bit画面和双声道192000采样对（384000个交错Float32数）往返相同。实际GPU调用次数及程序/线程/流/共享段关闭记于原始manifest。空发射器帧直接返回透明帧，不伪记GPU派发。\n\n'
    text+='[C47完整媒体与案例](../product/CASES.md#c47-emitter-animation)包含原生MKV、可播放MP4、4000ms GIF、真实去除关键帧的对照、参数和可编辑包。图像标签在解码后添加；静态检查与连续人类播放/听音及自然画质验收分别记录。3D、碰撞、深度、流体和完整效果库仍未完成，全部38原关闭条件保留。\n';write('docs/validation/发射器关键帧实测_2026-10-27.md',text)
    record=dict(status='documented',cli_version='0.1.37',readme_R_rows=259,prior_R_rows_preserved=253,
        functions=63,services=21,capabilities=76,goal_complete=False)
    write((out/'verification.json').relative_to(ROOT).as_posix(),json.dumps(record,indent=2)+'\n');print(json.dumps(record))
if __name__=='__main__':main()
