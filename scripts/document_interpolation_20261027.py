"""Complete trilingual current delivery docs without deleting history or goals."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-interpolation-20261027-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def after(s,p,entry):
    m=list(re.finditer(r'^\| '+p+r'\d+\s*\|.*$',s,re.M))[-1];return s[:m.end()]+'\n'+entry+s[m.end():]
def main():
    out=BASE/'documentation-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r1/verification.json');source=load(BASE/'source-interpolation-r3/verification.json');tests=load(BASE/'installed-interpolation-r1/verification.json');compat=load(BASE/'installed-compat-r2/verification.json');case=load(BASE/'case-r1/verification.json');quality=load(BASE/'quality-and-cancel-r1/verification.json')
    assert install['source_file_count']==257 and install['cli_version']=='0.1.42'
    for test,count in ((source,37),(tests,37),(compat,143)):assert test['status']=='passed' and test['tests']==count and test['failures']==test['errors']==test['skipped']==0 and test['frozen_equal'] and test['test_frozen_equal']
    for item in (case,quality):assert item['status']=='passed' and all(c['ok'] for c in item['checks'])
    capture='docs/product/neural-interpolation-capabilities-cli-0.1.42.json';(ROOT/capture).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes());caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==81
    desc={'':'新增**真实本地 CUDA RIFE4.25 神经补帧与可编辑慢动作**：保留CFR/VFR原生PTS、每帧持续时间、全部源RGBA帧及原音轨；2..8倍补帧、显式切镜保持、预乘alpha、可重跑配方和关联双轨。',
        '.zh-TW':'新增**真正本機 CUDA RIFE4.25 神經補幀與可編輯慢動作**：保留CFR/VFR原生PTS、每影格持續時間、全部來源RGBA影格及原音軌；2..8倍補幀、明確切鏡保持、預乘alpha、可重跑配方及關聯雙軌。',
        '.en':'Adds **actual native CUDA RIFE4.25 interpolation and editable slow motion**: native CFR/VFR PTS, every frame duration, all original RGBA anchors and selected original PCM remain intact. Integer2..8 factors,explicit cut holds,premultiplied alpha,rerunnable recipes and linked tracks.'}
    limits={'':'37项安装版补帧检查和143项安装版兼容回归通过；37项源码检查单列。C52动画24→96帧，另12→36帧透明VFR与105840个原始PCM标量完整保留，工程包完整音画重放相同。23张独立保留参考帧平均MSE：模型12.28／重复24.36／线性混合14.87；**末段模型重影失败保留**，显式保持以停顿换取去重影。未做人工连续播放／听审；自然质量、HDR模型与完整目标继续建设。',
        '.zh-TW':'37項安裝版補幀檢查及143項安裝版相容回歸通過；37項原始碼檢查分列。C52動畫24→96影格，另12→36影格透明VFR與105840個原始PCM標量完整保留，工程包完整音畫重播相同。23張獨立保留參考影格平均MSE：模型12.28／重複24.36／線性混合14.87；**末段模型重影失敗保留**，明確保持以停頓換取去重影。未做人工連續播放／聽審；自然品質、HDR模型及完整目標繼續建置。',
        '.en':'37 installed interpolation checks and143 installed compatibility regressions pass;37 source checks are separate. C52 animation24→96frames; another transparent VFR12→36 case preserves all105840 original PCM scalars. Complete package-render audio/video match. Across23 held-out originals,mean MSE is12.28 neural/24.36 hold/14.87 blend. **The final-pair ghosting failure is retained**; an explicit hold trades motion for removing it. No continuous human playback/listening,natural-quality/HDR-model or full-product acceptance is claimed.'}
    feature={'':'| F68 | CUDA神经补帧与慢动作 | 原生CFR/VFR、每源帧RGBA、预乘alpha、完整PCM；2..8倍、切镜保持、关联慢放双轨、配方重跑及工程包。 | `interpolate adapter; interpolate generate` | 显式RIFE4.25 safetensors＋原生CUDA Python；无CPU回退；困难运动/遮挡/自然质量/HDR未广泛验收。 |',
        '.zh-TW':'| F68 | CUDA神經補幀與慢動作 | 原生CFR/VFR、每來源影格RGBA、預乘alpha、完整PCM；2..8倍、切鏡保持、關聯慢放雙軌、配方重跑及工程包。 | `interpolate adapter; interpolate generate` | 明確RIFE4.25 safetensors＋原生CUDA Python；無CPU回退；困難運動/遮擋/自然品質/HDR未廣泛驗收。 |',
        '.en':'| F68 | CUDA neural interpolation / slow motion | Native CFR/VFR,all original RGBA anchors,premultiplied alpha,complete PCM;factor2..8,cut holds,linked slow-motion tracks,recipes/packages. | `interpolate adapter; interpolate generate` | Explicit RIFE4.25 safetensors/native CUDA Python;no CPU fallback;difficult motion/occlusion/natural-quality/HDR acceptance open. |'}
    service={'':'| S23 | RIFE CUDA补帧服务 | 固定五阶段IFNet/158个FP32推理张量、严格本地摘要、实际CUDA；不执行模型目录代码/Pickle。 | 已有原生Torch＋safetensors依赖和MIT模型证据；无自动安装。 | `interpolate adapter; interpolate generate` | 原生时间细分、全帧/PCM往返；阈值不是语义切镜；自然质量仍须复核。 |',
        '.zh-TW':'| S23 | RIFE CUDA補幀服務 | 固定五階段IFNet/158個FP32推理張量、嚴格本機雜湊、真正CUDA；不執行模型目錄程式/Pickle。 | 已有原生Torch＋safetensors依賴及MIT模型證據；無自動安裝。 | `interpolate adapter; interpolate generate` | 原生時間細分、全影格/PCM往返；閾值不是語意切鏡；自然品質仍須複核。 |',
        '.en':'| S23 | RIFE CUDA interpolation | Fixed five-stage IFNet/158 FP32 inference tensors,local artifact hashes,actual CUDA;no model-directory code/Pickle. | Existing native Torch/safetensors and MIT model evidence;no installation. | `interpolate adapter; interpolate generate` | Native interval subdivision,complete frame/PCM proofs;RGB threshold is not semantic cuts;quality review required. |'}
    descriptions={
        '':['CLI0.1.42/local.40离线构建、安装和257程序文件逐字节一致，81能力；不修改公开alpha.3。',
            '37项源码补帧检查：任意整数倍率/有理数VFR、部分管道、原帧/隐藏RGB、切镜/静态/末帧保持、PCM、配方迁移、真实FFmpeg、取消/超时及事务回滚。',
            '37项安装版补帧检查通过；另143项安装版口型/原生时钟/抠像/片段库/schema兼容回归通过，独立记录，不与旧993/177合并。基础解释器缺依赖的失败轮保留。',
            '固定MIT上游代码、归档LFS摘要；官方Drive超时保留；158推理张量与独立镜像逐张量相同，再转safetensors回读，实际CUDA探针通过。',
            'C52安装版真实RIFE动画24→96帧、透明VFR12→36帧、全105840个PCM标量/原帧/nativePTS保留；完整工程包音画一致，带原片/结果/GIF/配方。',
            '保留实际末段重影失败，23张参考帧误差逐帧披露；显式保持减少该处重影但有停顿。真实CUDA输出后取消，三个子进程回收、无半成品、工程回滚和诊断通过。',
            'r43统一入口工具包，1 Skill/17模块/81 Skill文件/130 ZIP项；三语F68/S23及全部283既有R行和38原关闭条件保留。'],
        '.zh-TW':['CLI0.1.42/local.40離線建置、安裝及257程式檔逐位元組相同，81能力；不修改公開alpha.3。',
            '37項原始碼補幀檢查：任意整數倍率/有理數VFR、部分管道、原始影格/隱藏RGB、切鏡/靜態/末幀保持、PCM、配方遷移、真正FFmpeg、取消/逾時及交易回滾。',
            '37項安裝版補幀檢查通過；另143項安裝版口型/原生時鐘/去背/片段庫/schema相容回歸通過，分別記錄，不與舊993/177合併。基礎解譯器缺依賴的失敗輪保留。',
            '固定MIT上游程式、歸檔LFS雜湊；官方Drive逾時保留；158推理張量與獨立鏡像逐張量相同，再轉safetensors回讀，真正CUDA探針通過。',
            'C52安裝版真正RIFE動畫24→96影格、透明VFR12→36影格、全105840個PCM標量/原始影格/nativePTS保留；完整工程包音畫一致，附原片/結果/GIF/配方。',
            '保留真正末段重影失敗，23張參考影格誤差逐幀披露；明確保持減少該處重影但有停頓。真正CUDA輸出後取消，三個子程序回收、無半成品、工程回滾及診斷通過。',
            'r43統一入口工具包，1 Skill/17模組/81 Skill檔案/130 ZIP項；三語F68/S23及全部283既有R列和38原關閉條件保留。'],
        '.en':['CLI0.1.42/local.40 offline build/install:257 byte-identical product files,81 capabilities;public alpha.3 untouched.',
            '37 source interpolation checks:integer factors/rational VFR,partial pipes,original anchors/hidden RGB,cuts/static/final holds,PCM,portable recipes,real FFmpeg,cancel/deadline and rollback.',
            '37 installed interpolation checks plus143 separately recorded installed lip-sync/native-clock/matting/fragments/schema regressions pass. Prior993/177 counts are not aggregated. Missing-dependency base-interpreter failures remain recorded.',
            'Pinned MIT source/archive LFS hashes;official Drive timeout retained. All158 inference tensors equal an independent mirror,with strict safetensors reload and actual CUDA graph probe.',
            'Installed RIFE C52:animation24→96 frames;transparent VFR12→36;all105840 original PCM scalars,anchors/native PTS retained;complete package-render audio/video equality,originals/results/GIF/recipes.',
            'Actual final-pair ghosting is retained with23 per-frame held-out comparisons. Explicit hold reduces this error by sacrificing motion. Cancellation after neural output reclaims three children,rolls back metadata and retains diagnostics.',
            'r43:one Skill/17 modules/81 Skill files/130 ZIP entries;trilingual F68/S23 retain all283 prior R rows and38 original goal closure cells.']}
    targets=['installation-final-r1/verification.json','source-interpolation-r3/verification.json','installed-compat-r2/verification.json','weight-conversion.json','case-r1/verification.json','quality-and-cancel-r1/verification.json','kit-r1/verification.json']
    for suffix in ('','.zh-TW','.en'):
        name='README'+suffix+'.md';s=read(name);old=rows(s,'R');assert len(old)==283
        block='<!-- native-interpolation-current -->\n\n**CLI0.1.42 / alpha.4-local.40 / r43 kit · 1 Skill / 17 modules.**\n\n'+desc[suffix]+'\n\n[Workflow / usage](docs/product/NEURAL_INTERPOLATION.md) · [C52](docs/product/CASES.md#c52-native-neural-interpolation) · [Install](docs/releases/CLI_0.1.42_LOCAL.md) · [Evidence](docs/validation/本地神经补帧实测_2026-10-27.md)\n\n![Actual native CUDA interpolation;original versus neural slowed4x](docs/assets/native-interpolation-20261027-r1/comparison.gif)\n\n'+limits[suffix]+'\n\n[Actual retained failure and explicit hold](docs/assets/native-interpolation-20261027-r1/failure-and-hold.png) · [Held-out per-frame measurements](docs/validation/evidence/native-interpolation-20261027-r1/case-r1/verification.json)\n\n<!-- /native-interpolation-current -->\n\n'
        s=s.replace('<!-- native-lip-sync-current -->',block+'<!-- native-lip-sync-history -->',1).replace('<!-- /native-lip-sync-current -->','<!-- /native-lip-sync-history -->',1)
        s=after(after(s,'F',feature[suffix]),'S',service[suffix]);s=after(s,'R','\n'.join('| R'+str(284+i)+' | 2026-10-27 native interpolation | '+d+' | [Evidence](docs/validation/evidence/native-interpolation-20261027-r1/'+p+') |' for i,(d,p) in enumerate(zip(descriptions[suffix],targets))))
        s='\n'.join(l.replace('local.39/final-r1/installed','local.40/final-r1/installed') if 'local.39/final-r1/installed' in l and not l.startswith('| R') else l for l in s.splitlines())+'\n'
        s=s.replace('[r42 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r42.zip)','[r43 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r43.zip)')
        for a,b in [('完整的 67 个功能模块','完整的 68 个功能模块'),('完整的 67 個功能模組','完整的 68 個功能模組'),('All 67 functional modules','All 68 functional modules')]:s=s.replace('## '+a,'## '+b)
        assert len(rows(s,'F'))==68 and len(rows(s,'S'))==23 and len(rows(s,'K'))==17 and len(rows(s,'R'))==290 and all(rows(s,'R')[k]==v for k,v in old.items());write(name,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            path=base+suffix+'.md';s=read(path);relative='NEURAL_INTERPOLATION.md' if '/product/' in path else '../product/NEURAL_INTERPOLATION.md'
            block='<!-- community-current -->\n\n**CLI0.1.42 / alpha.4-local.40 / r43 kit · 1 Skill / 17 modules / 81 files.**\n\n'+desc[suffix]+'\n\n[Native interpolation workflow and limits]('+relative+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            if base.endswith('CAPABILITIES'):
                s=after(after(s,'F',feature[suffix]),'S',service[suffix])
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if n==0:assert key=='native_neural_interpolation';s+='\n'+section+'\n'
                s+='\n[CLI0.1.42 exact installed capability snapshot](neural-interpolation-capabilities-cli-0.1.42.json).\n'
            write(path,s)
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p);prior=load(ROOT/'docs/validation/evidence/native-lipsync-20261027-r1/installation-final-r1/verification.json')
    for old,new in [('alpha.4-local.39','alpha.4-local.40'),('CLI 0.1.41','CLI 0.1.42'),('r42.zip','r43.zip'),('0.1.41-r42.json','0.1.42-r43.json'),(prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(old,new)
    s+='\nCLI0.1.42/local.40/r43: [CUDA neural interpolation and editable slow motion](NEURAL_INTERPOLATION.md), [C52](CASES.md#c52-native-neural-interpolation), [current local installation](../releases/CLI_0.1.42_LOCAL.md). RIFE safetensors and the existing native CUDA Python are separate explicit dependencies; registration installs nothing.\n';write(p,s)
    for p in ['docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md']:
        s=read(p);old=rows(s,'G');prefix='当前本地 **CLI0.1.42 / alpha.4-local.40 / r43 kit**：[G10真实CUDA RIFE补帧](NEURAL_INTERPOLATION.md)已接通原生CFR/VFR、原始RGBA帧/PCM、切镜保持、配方/慢动作双轨及工程包。[C52](CASES.md#c52-native-neural-interpolation)包含独立参考、透明VFR、实际重影失败/显式保持及输出后取消。37项安装版专项和143项安装版兼容回归通过；完整自然质量/HDR/广泛验收及38原关闭条件继续建设。\n\n';s=s.replace('\n\n','\n\n'+prefix,1)
        if old:
            line=next(l for l in s.splitlines() if l.startswith('| G10 '));parts=line.split('|');parts[3]=' 常速/曲线/Bezier/倒放/定格/FFmpeg光流及CLI0.1.42真实RIFE4.25 CUDA；原生CFR/VFR、全源RGBA/PCM、2..8倍、切镜保持、慢放双轨/配方/工程包；[C52](CASES.md#c52-native-neural-interpolation)。 ';parts[4]=' 神经补帧已内置但动画末段仍有实际重影失败；显式保持仅以停顿回避。自然实拍/遮挡/快速运动/细线/语义切镜、HDR、4K性能与广泛质量/成本验收仍缺。 ';s=s.replace(line,'|'.join(parts),1);assert len(old)==38 and all(rows(s,'G')[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        write(p,s)
    p='docs/README.md';s=read(p);s=s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.42 / local.40 / r43 kit** · [CUDA interpolation / 神经补帧 / 神經補幀](product/NEURAL_INTERPOLATION.md) · [Install](releases/CLI_0.1.42_LOCAL.md) · [C52](product/CASES.md#c52-native-neural-interpolation).\n\n',1);write(p,s)
    # Versioned release text uses the actual locally compiled archive identity.
    release=f'''# CLI0.1.42 / alpha.4-local.40 — native CUDA interpolation

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

新增真正RIFE4.25 CUDA神经补帧/慢动作，保留原生CFR/VFR时钟、全部RGBA源帧与原PCM，2..8倍、切镜保持、透明度、可重跑配方和可编辑关联双轨。繁體：真正CUDA補幀保留原生時間、來源影格與PCM；所有品質邊界及38原關閉條件持續保留。 English: actual CUDA interpolation, original native clocks/anchors/PCM, portable recipes and editable slow-motion tracks; full product parity remains ongoing.

This is a **local compiled installation**, separate from immutable public alpha.3/CLI0.1.2.

```text
E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.40/candidate-r1/bundle.zip
bytes: {install['archive_bytes']}
SHA-256: {install['archive_sha256']}
manifest SHA-256: {install['manifest_sha256'].removeprefix('sha256:')}
installed: E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.40/final-r1/installed
```

All257 product Python files match tested source. r43kit has one public Skill/17modules/81Skill files/130ZIP entries. No source fallback. Models, native CUDA interpreter, Python and FFmpeg remain explicit existing dependencies; no package installation/download occurs at runtime.

Use [installation/activation](../product/COMMUNITY_LOCAL_DELIVERY.md), then [full workflow](../product/NEURAL_INTERPOLATION.md): ingest video, register local safetensors/native Python/evidence, inspect native-frame dry-run, generate new asset, inspect original/actual previews, validate/render/export. Use new IDs for reruns. Add --apply and --playback-speed0.25 for editable4x slow motion; source audio requires its own linked audio track. Generated master keeps original selected duration and PCM.

37 source checks,37 installed checks and143 installed compatibility tests are recorded separately. Actual C52 creates96animation frames plus36transparentVFR frames, preserves105840originalPCM scalars and complete package-render equality. Earlier missing-dependency/acquisition/development failures are retained. C52 also retains a genuine ghosting failure and a freezing hold alternative; no continuous human playback/listening or broad natural-quality acceptance is claimed.

[Actual case/media/GIF/failure](../product/CASES.md#c52-native-neural-interpolation) · [Evidence](../validation/本地神经补帧实测_2026-10-27.md) · [Installed checks](../validation/evidence/native-interpolation-20261027-r1/installed-interpolation-r1/verification.json) · [Build/install](../validation/evidence/native-interpolation-20261027-r1/installation-final-r1/verification.json)
''';write('docs/releases/CLI_0.1.42_LOCAL.md',release)
    # Public media inventory and exact probe clocks, excluding self-reference.
    public=ROOT/'docs/assets/native-interpolation-20261027-r1';files=[]
    for p in sorted(public.iterdir()):
        if not p.is_file() or p.name=='media-manifest.json':continue
        item=dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p))
        if p.suffix in ('.mov','.mp4'):
            result=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)],capture_output=True,check=True,timeout=60);item['probe']=json.loads(result.stdout)
        if p.suffix=='.gif':
            from PIL import Image
            with Image.open(p) as gif:item.update(frames=gif.n_frames,duration_ms=sum((gif.seek(i),gif.info.get('duration',0))[1] for i in range(gif.n_frames)))
        files.append(item)
    (public/'media-manifest.json').write_text(json.dumps(dict(case='C52',source='CC-BY-3.0 Blender Foundation animation;CC0 original diagnostic',files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    review=dict(status='static-frames-inspected',reviewer='agent-visual-review',continuous_human_playback=False,human_listening=False,
        finding='Natural comparison is actual Sintel animation. Retained worst pair shows visible duplicated/ghosted face;explicit hold alternative sacrifices motion. No naturalness pass.',
        files={name:sha(public/name) for name in ('comparison.png','held-out-worst.png')})
    (BASE/'static-review.json').write_text(json.dumps(review,indent=2)+'\n',encoding='utf8')
    p='docs/product/CASES.md';s=read(p);s+='''
<a id="c52-native-neural-interpolation"></a>

## C52 · CUDA神经补帧 / 神經補幀 / Native neural interpolation

实际注册CLI0.1.42/单入口Skill，RTX3060真正RIFE4.25 CUDA。CC-BY-3.0《Sintel》12..14秒动画片段缩至320×180：24FPS原参考的偶数帧组成12FPS/24帧输入，奇数帧不提供给模型。4倍补帧得到96帧/48FPS/2秒，69次实际forward；可编辑0.25倍慢放为8秒，原始源帧RGBA全部相同。

獨立23張原始中間影格平均MSE：模型12.2806、重複24.3586、線性混合14.8733。模型22/23優於重複、13/23優於混合，末段pair22有明顯人臉重影，保留失敗；該處明確保持使MSE169.2437降至5.6454，代價是停頓，不視為自然補幀品質通過。另有原創CC0透明VFR診斷12→36影格，明確切鏡、全部原RGBA/PTS/持續時間及105840原始Float32 PCM標量保留，模型forward20次。

Actual installed output and original/held-out sources are distinct. The editable package preserves both initial masters/recipes; complete ordinary rendered RGBA and decoded PCM match after import. Alternate explicit-hold output is a separate companion. Real CUDA cancellation after emitted neural frames reclaims all three children, rolls back metadata and leaves no partial asset. No continuous human playback/listening or live-action/natural-quality acceptance is claimed.

![Actual slowed source versus neural output](../assets/native-interpolation-20261027-r1/comparison.gif)

[Playable slow-motion edit](../assets/native-interpolation-20261027-r1/slow-motion.mp4) · [Original24FPS reference](../assets/native-interpolation-20261027-r1/original-reference.mp4) · [Lossless full reference](../assets/native-interpolation-20261027-r1/original-reference.mov) · [Actual12FPS model input](../assets/native-interpolation-20261027-r1/sparse-source.mov) · [Original transparentVFR + stereoPCM](../assets/native-interpolation-20261027-r1/alpha-vfr-source.mov) · [Editable package + masters/recipes](../assets/native-interpolation-20261027-r1/editable-interpolation.aevpkg.zip) · [Retained failure/hold comparison](../assets/native-interpolation-20261027-r1/failure-and-hold.png) · [Worst original/model/error4x](../assets/native-interpolation-20261027-r1/held-out-worst.png) · [Separate hold alternative](../assets/native-interpolation-20261027-r1/explicit-hold-slow.mp4) · [Source/license](../assets/native-interpolation-20261027-r1/SOURCE.txt) · [Exact media hashes/clocks](../assets/native-interpolation-20261027-r1/media-manifest.json) · [Workflow](NEURAL_INTERPOLATION.md) · [Evidence](../validation/本地神经补帧实测_2026-10-27.md)
''';write(p,s)
    report='''# 本地神经补帧实测 / Native interpolation · 2026-10-27

CLI0.1.42/local.40/r43，原生Windows，无Docker/WSL/虚拟环境/安装包变更；一个公开Skill、17内部模块，源码回退禁用。

| 范围 | 实际结果及证据 |
|---|---|
| 编译安装 | 257程序文件与源码逐字节一致，81能力。[安装](evidence/native-interpolation-20261027-r1/installation-final-r1/verification.json) |
| 源码专项 | 37项，零失败/错误/跳过；原生VFR/有理数倍率、原帧/alpha、PCM、真实媒体、取消/超时、发布后回滚、配方迁移。[源码](evidence/native-interpolation-20261027-r1/source-interpolation-r3/verification.json) |
| 安装专项 | 同37项独立安装版执行，零失败/错误/跳过。[安装专项](evidence/native-interpolation-20261027-r1/installed-interpolation-r1/verification.json) |
| 安装兼容 | 143项既有口型/原生音画时钟/抠像/片段库/schema，零失败/错误/跳过。[兼容](evidence/native-interpolation-20261027-r1/installed-compat-r2/verification.json) |
| 权重来源 | 固定官方MIT源码及镜像revision/LFS大小/哈希；官方Drive超时，归档非官方逐字节认证。158推理张量与独立镜像相同、strict转safetensors回读。[镜像](evidence/native-interpolation-20261027-r1/mirror-acquisition.json) · [转换](evidence/native-interpolation-20261027-r1/weight-conversion.json) |
| 模型探针 | 实际Torch2.13+cu130/RTX3060，1/3、2/3、1/2时间，网络守卫、FP32、透明alpha0RGB清零。[CUDA](evidence/native-interpolation-20261027-r1/private-cuda-probe.json) |
| 实际案例 | 24→96动画帧/69forward；透明VFR12→36/20forward，105840原PCM标量、原帧和逐帧PTS/持续时间；工程包全画面/全PCM相同。[C52](evidence/native-interpolation-20261027-r1/case-r1/verification.json) |
| 真实失败 | 动画pair22神经重影，原图/输出/误差及23帧指标全保留。显式保持降低该帧误差但有停顿，不冒称解决自然补帧。[失败及真实取消](evidence/native-interpolation-20261027-r1/quality-and-cancel-r1/verification.json) |
| 真实取消 | 输出神经帧后触发取消，三个owned子进程退出，项目与权利元数据回滚，无半成品/owned目录，限额诊断保留。 |
| 工具包 | r43，1Skill/17模块/81Skill文件/130ZIP项；独立注册与实装入口检查。[kit](evidence/native-interpolation-20261027-r1/kit-r1/verification.json) |

失败尝试保留：Drive超时；转换首次training分支拒绝、旧caltime形状拒绝；探针alpha0量化残RGB；首轮合成测试worker解释器路径/音频fixture生成问题；基础Python没有既有cv2依赖的兼容轮失败，改用已有原生模型解释器重跑，无依赖安装。失败轮不计入通过数；历史993/177也不合并为本轮总数。

两张静态样图已经agent目检，最差帧存在明显重影。未进行人类连续播放、听审、自然实拍语料验收、4K/实时/跨设备验收。ICC/HDR模型、语义切镜、遮挡/细线/快速运动仍需开发/验收；38原goal关闭条件完整保留。

[完整案例](../product/CASES.md#c52-native-neural-interpolation) · [使用逻辑](../product/NEURAL_INTERPOLATION.md) · [原素材与实际结果清单](../assets/native-interpolation-20261027-r1/media-manifest.json)
''';write('docs/validation/本地神经补帧实测_2026-10-27.md',report)
    result=dict(status='documentation-written-with-actual-evidence',functional_modules=68,services=23,internal_modules=17,prior_R_rows_retained=283,new_R_rows=7,all_38_goal_closure_cells_preserved=True)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
if __name__=='__main__':main()
