"""Update complete trilingual manuals after installed all-frame/PCM verification."""
from pathlib import Path
import hashlib,json,re,shutil
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/gpu-dispatch-20261027-r1'

def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(s,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d+) \|.*$',s,re.M)}
def after(s,prefix,entry):
    m=list(re.finditer(r'^\| '+prefix+r'\d+ \|.*$',s,re.M))[-1]
    return s[:m.end()]+'\n'+entry+s[m.end():]

def main():
    out=BASE/'documentation-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r1/verification.json')
    test=load(BASE/'installed-regression-r1/verification.json');assert test['status']=='passed' and test['tests']==656
    baseline=load(BASE/'render-baseline-r1/verification.json')
    current=load(BASE/'render-installed-r1/verification.json')
    profile=load(BASE/'profile-installed-r2/verification.json')
    assert current['status']=='passed' and current['all_frames_equal'] and current['all_PCM_equal']
    assert profile['status']=='passed' and profile['cli_version']=='0.1.36'
    assert all(current['GPU']['control'][k] for k in ('threads_closed','streams_closed'))
    speed=current['speedup_one_pair'];before=baseline['render_seconds'];now=current['render_seconds']
    timing=f'{before:.2f}s → {now:.2f}s ({speed:.2f}×)'
    media=ROOT/'docs/assets/gpu-dispatch-20261027-r1';media.mkdir(exist_ok=False)
    # Original chart of measured data, rather than an illustrative video frame.
    image=Image.new('RGB',(1120,510),'#121b29');draw=ImageDraw.Draw(image)
    font=lambda size:ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',size)
    draw.text((44,28),'Measured native GPU dispatch',font=font(34),fill='#eaf3ff')
    draw.text((44,82),'Same 48 frames / 12 FPS / 960 x 360 / 288 particle dispatches',font=font(23),fill='#afc1d6')
    scale=760/max(before,now)
    for y,label,seconds,color in [(165,'CLI 0.1.35',before,'#f2ad79'),(275,'CLI 0.1.36',now,'#5ad5b0')]:
        draw.text((44,y),label,font=font(24),fill='#eaf3ff')
        draw.rectangle((255,y,255+seconds*scale,y+45),fill=color)
        draw.text((255,y+49),f'{seconds:.3f} seconds',font=font(21),fill='#eaf3ff')
    draw.text((44,392),f'{speed:.2f}x in this matched pair; every decoded 10-bit frame and all PCM equal.',font=font(23),fill='#eaf3ff')
    draw.text((44,440),'Diagnostic / one pair / includes startup & encoding / no realtime or 4K acceptance',font=font(20),fill='#afc1d6')
    image.save(media/'timing.png')
    movie=Path(current['movie']);assert movie.stat().st_size<90*1024**2
    shutil.copyfile(movie,media/'optimized.mkv')
    write('docs/assets/gpu-dispatch-20261027-r1/timings.json',json.dumps(dict(
        baseline_cli='0.1.35',current_cli='0.1.36',baseline_seconds=before,current_seconds=now,
        speedup_one_pair=speed,decoded_frames=48,all_frames_equal=True,all_PCM_equal=True,
        stereo_frame_pairs=192000,float32_samples=384000,fixture_sha256=current['fixture_sha256'],
        author_graph_sha256=current['author_graph_sha256'],scope=current['performance_scope']),indent=2)+'\n')
    write('docs/assets/gpu-dispatch-20261027-r1/SOURCE.txt',
        'Original measured timing chart: CC0-1.0. No model-generated image.\n'
        'optimized.mkv: actual registered installed CLI0.1.36 output from the original C45 diagnostic author graph.\n'
        'Procedural recipes/code: project MIT; source package and recipe details remain in C45.\n'
        'No third-party footage, models, people, logos, fonts in the rendered diagnostic video.\n'
        'Chart uses locally available Segoe UI for rendering; the font file is not distributed.\n'
        'See docs/product/CASES.md#c45-procedural-particles and docs/validation/GPU管道调度实测_2026-10-27.md.\n')
    files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in media.iterdir() if p.is_file()}
    write('docs/assets/gpu-dispatch-20261027-r1/media-manifest.json',json.dumps(dict(
        files=files,frame_count=48,fps='12/1',duration_seconds=4,synthetic_diagnostic=True,
        all_frames_decoded=True,all_PCM_decoded=True,continuous_human_playback=False,
        human_listening=False,natural_quality_accepted=False),ensure_ascii=False,indent=2)+'\n')
    cap_path='docs/product/gpu-dispatch-capabilities-cli-0.1.36.json'
    (ROOT/cap_path).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/cap_path)['data']['capabilities'];assert len(caps)==76
    descriptions={
        '':f'原生Float32 GPU控制改为任务自有本机管道，消除每个算子的控制文件写盘与轮询。相同48帧工程通过实际注册安装版对照：**{timing}**；全部10bit解码帧和384000个Float32音频采样相同，数值内核字节保持。',
        '.zh-TW':f'原生Float32 GPU控制改為任務自有本機管道，消除每個算子的控制檔案寫入與輪詢。相同48幀工程透過實際註冊安裝版對照：**{timing}**；全部10bit解碼幀和384000個Float32音訊取樣相同，數值核心位元組保持。',
        '.en':f'Native Float32 GPU control now uses owned native pipes, removing per-operator control-file writes and polling. The same48-frame project through the registered installed Skill measures **{timing}**; all decoded10bit frames and384000 Float32 audio samples match, with byte-identical numeric kernels.'}
    limits={
        '':'单个960×360诊断工程的同机一次配对，包含启动、编码及核验；不是实时、4K长片或跨设备保证。完整剪映等价仍未完成；所有38项原关闭条件与247项历史核验保留。',
        '.zh-TW':'單一960×360診斷工程、同機一次配對，包含啟動、編碼及核驗；不是即時、4K長片或跨裝置保證。完整剪映等價仍未完成；38項原關閉條件與247項歷史核驗保留。',
        '.en':'One matched960×360 diagnostic pair on this machine, including startup,encoding and checks; not realtime,4K,long-form or multivendor acceptance. Full CapCut parity remains open; all38 original closure cells and247 historical verification rows remain.'}
    features={
        '':'| F57 | 原生Float32 GPU执行 | 显式策略驱动仿射、普通合成、文字组件/逐词选择；任务自有管道调度、共享像素、渲染/预览/队列/恢复。 | `projection_acceleration; render; preview; queue` | off/prefer/require；真实binary64/次正规数探测；有界控制包/队列及进程/线程/流清理；其他算子CPU。 |',
        '.zh-TW':'| F57 | 原生Float32 GPU執行 | 顯式策略驅動仿射、一般合成、文字元件/逐詞選擇；任務自有管道調度、共享像素、渲染/預覽/佇列/恢復。 | `projection_acceleration; render; preview; queue` | off/prefer/require；實際binary64/次正規數探測；有界控制包/佇列及程序/執行緒/串流清理；其他算子CPU。 |',
        '.en':'| F57 | Native Float32 GPU execution | Explicit policy for affine,normal over,text components/word selection; owned pipe dispatch/shared pixels;render,preview,queue,resume. | `projection_acceleration; render; preview; queue` | off/prefer/require;actual binary64/subnormal probes;bounded packets/queues and owned process/thread/stream cleanup;other operators CPU. |'}
    checks={
        '':[
            'CLI0.1.36/local.34离线包：234产品文件与源码一致；最终安装版656项回归通过、零跳过，包含12协议、23原生GPU及粒子/真实编码/PCM/预览/队列/编辑/旧流程。',
            f'真实注册Skill、相同素材包/作者图/FFmpeg、48帧12FPS：{timing}。48个10bit解码帧哈希及全部384000 PCM浮点采样相同；单次受控配对，不推断4K/实时。',
            '独立记录32次小算子、3帧作者图及CPU/GPU误差；原GPU数值模块和worker execute/probe保持，227个旧产品文件字节相同。高频调用、整片与历史C45分别计时。',
            '128KiB包/单槽读写队列、截断/非有限/重复键拒绝；实际满管道、破管道、120消息、取消/超时/恢复均测试。工程原子写盘不变；实际进程/线程/流/共享段回收留证。',
            'r37独立工具包：一个入口/17模块/76 Skill文件、119包文件；独立目录解包、完整模型校验、注册及23次调用，实际发现联接保持。',
            '三语63功能/21服务及76能力快照、C46真实输出/耗时图、完整使用/安装/Skill手册更新；247历史核验和38原关闭条件保持。开发期两个测试辅助进程失败原样留证。'],
        '.zh-TW':[
            'CLI0.1.36/local.34離線包：234產品檔案與原始碼一致；最終安裝版656項回歸通過、零跳過，含12協議、23原生GPU及粒子/實際編碼/PCM/預覽/佇列/編輯/舊流程。',
            f'實際註冊Skill、相同素材包/作者圖/FFmpeg、48幀12FPS：{timing}。48個10bit解碼幀雜湊及全部384000 PCM浮點取樣相同；單次受控配對，不推論4K/即時。',
            '分開記錄32次小算子、3幀作者圖及CPU/GPU誤差；原GPU數值模組和worker execute/probe保持，227個舊產品檔案位元組相同。高頻呼叫、整片與歷史C45分開計時。',
            '128KiB包/單槽讀寫佇列，拒絕截斷/非有限/重複鍵；實際滿管道、斷管道、120訊息、取消/逾時/恢復均測試。工程原子寫入不變；實際程序/執行緒/串流/共享段回收留證。',
            'r37獨立工具包：一入口/17模組/76 Skill檔案、119包檔案；獨立目錄解包、完整模型校驗、註冊及23次呼叫，實際發現聯接保持。',
            '三語63功能/21服務及76能力快照、C46實際輸出/耗時圖、完整使用/安裝/Skill手冊更新；247歷史核驗和38原關閉條件保持。開發期兩次測試輔助程序失敗原樣留證。'],
        '.en':[
            'CLI0.1.36/local.34 offline bundle:234 product files equal source;656 final installed regressions pass,zero skips,including12 protocol/23 native GPU and particles,encoding,PCM,preview,queue,editing and legacy paths.',
            f'Registered Skill,same fixture/author graph/FFmpeg,48frames at12FPS:{timing}. All48 decoded10bit frame hashes and384000 PCM scalars equal;one diagnostic pair,no4K/realtime extrapolation.',
            'Separate32-tiny-operation and3-author-frame profiles/CPU-GPU errors. Numeric GPU modules and worker execute/probe remain unchanged;227 existing product files are byte-identical. Microcalls,full movie and historical C45 are timed separately.',
            '128KiB packets/single-slot queues reject truncation,nonfinite JSON and duplicate members;actual pipe backpressure/breakage,120 messages,cancel/timeout/resume tested. Atomic project persistence retained;process/thread/stream/shared-memory closure recorded.',
            'Fresh r37 kit:one entry,17 modules,76 Skill files/119 package files;independent extraction,complete pack verification,registration and23 calls retain actual discovery.',
            'Three languages,63 functions/21 services/76 capability snapshots,C46 actual output/timing chart,complete workflow/install/Skill docs synchronized. All247 earlier R rows/38 closure cells preserved;two failed development test-helper attempts retained.']}
    targets=['installed-regression-r1/verification.json','render-installed-r1/verification.json','kernel-identity-r1/verification.json',
             'installed-regression-r1/receipts.json','kit-r1/verification.json','final-delivery-r1/verification.json']
    for suffix in ('','.zh-TW','.en'):
        name='README'+suffix+'.md';s=read(name);old=rows(s,'R');assert len(old)==247
        block='<!-- gpu-dispatch-current -->\n\n**CLI0.1.36 / alpha.4-local.34 / r37 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n'
        block+='[Workflow / usage](docs/product/GPU_DISPATCH.md) · [C46](docs/product/CASES.md#c46-gpu-dispatch) · [Install](docs/releases/CLI_0.1.36_LOCAL.md) · [Evidence](docs/validation/GPU管道调度实测_2026-10-27.md)\n\n'
        block+='![Measured timing; identical decoded output](docs/assets/gpu-dispatch-20261027-r1/timing.png)\n\n'+limits[suffix]+'\n\n<!-- /gpu-dispatch-current -->\n\n'
        marker='<!-- procedural-particles-current -->';assert marker in s
        s=s.replace(marker,block+'<!-- procedural-particles-history -->',1).replace('<!-- /procedural-particles-current -->','<!-- /procedural-particles-history -->',1)
        s=re.sub(r'^\| F57 \|.*$',lambda _:features[suffix],s,count=1,flags=re.M)
        s=after(s,'R','\n'.join('| R'+str(248+i)+' | 2026-10-27 GPU dispatch | '+d+' | [Evidence](docs/validation/evidence/gpu-dispatch-20261027-r1/'+p+') |' for i,(d,p) in enumerate(zip(checks[suffix],targets))))
        s='\n'.join(l.replace('local.33/final-r2/installed','local.34/final-r1/installed').replace('CLI 0.1.35','CLI 0.1.36')
                    if 'local.33/final-r2/installed' in l and not l.startswith('| R') else l for l in s.splitlines())+'\n'
        assert len(rows(s,'F'))==63 and len(rows(s,'S'))==21 and len(rows(s,'R'))==253
        assert all(rows(s,'R')[k]==v for k,v in old.items());write(name,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            path=base+suffix+'.md';s=read(path)
            relative='GPU_DISPATCH.md' if '/product/' in path else '../product/GPU_DISPATCH.md'
            block='<!-- community-current -->\n\n**CLI0.1.36 / alpha.4-local.34 / r37 kit · 1 Skill / 17 modules / 76 files.**\n\n'+descriptions[suffix]+'\n\n[GPU workflow and limits]('+relative+')\n\n<!-- /community-current -->'
            s,count=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert count==1
            if base.endswith('CAPABILITIES'):
                s=re.sub(r'^\| F57 \|.*$',lambda _:features[suffix],s,count=1,flags=re.M)
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    pattern=r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```'
                    s,count=re.subn(pattern,lambda _:section,s,count=1,flags=re.M|re.S);assert count==1,key
                s+='\n[CLI0.1.36 exact installed capability snapshot](gpu-dispatch-capabilities-cli-0.1.36.json).\n'
            write(path,s)
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
    prior=load(ROOT/'docs/validation/evidence/procedural-particles-20261027-r1/installation-final-r2/verification.json')
    for a,b in [('local.33/final-r2/installed','local.34/final-r1/installed'),('local.33/candidate-r2/bundle.zip','local.34/candidate-r1/bundle.zip'),
        ('alpha.4-local.33','alpha.4-local.34'),('CLI 0.1.35','CLI 0.1.36'),('r36.zip','r37.zip'),('0.1.35-r36.json','0.1.36-r37.json'),
        (prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(a,b)
    s+='\nCLI0.1.36/local.34/r37: [owned GPU control pipes](GPU_DISPATCH.md), [C46 timing and identical output](CASES.md#c46-gpu-dispatch), [local installation](../releases/CLI_0.1.36_LOCAL.md).\n';write(p,s)
    release='# CLI0.1.36 · owned GPU control pipes · alpha.4-local.34\n\nLocal tested build; public alpha.3 / CLI0.1.2 remains unchanged.\n\n'
    release+='Application ZIP: `'+Path(install['archive']).relative_to(ROOT).as_posix()+'`\n\nBytes: `'+str(install['archive_bytes'])+'` · SHA256: `'+install['archive_sha256']+'`\n\nManifest: `'+install['manifest_sha256']+'`\n\n'
    release+='Installed: `'+Path(install['installed']).relative_to(ROOT).as_posix()+'`\n\n234 source/installed Python files match;76 capability declarations,one public Skill/17 modules/76 Skill files. r37 kit contains119 files and keeps application/model archives separate.\n\n'
    release+=f'Matched registered Skill render: **{timing}**. All48 decoded10bit frames and384000 PCM float samples equal.656 installed tests pass without skips;23 native GPU and12 protocol tests are included,not added again. Numeric kernels and worker execution/probe remain unchanged.\n\n'
    release+='[Installation with local ZIP verification](../product/COMMUNITY_LOCAL_DELIVERY.md) · [GPU usage and cleanup](../product/GPU_DISPATCH.md) · [C46 actual output](../product/CASES.md#c46-gpu-dispatch) · [r37 kit](../skills/agent-editor-kit-community-unified-skill-r37.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.36-r37.json) · [Verification](../validation/GPU管道调度实测_2026-10-27.md).\n\n'
    release+='One matched960×360/4s diagnostic pair;no realtime/4K/long-form/multivendor or complete CapCut acceptance. All38 original goal closure cells remain.\n';write('docs/releases/CLI_0.1.36_LOCAL.md',release)
    p='docs/product/CASES.md';s=read(p);assert 'id="c46-gpu-dispatch"' not in s
    s+='\n<a id="c46-gpu-dispatch"></a>\n\n## C46 · 原生GPU调度 / Owned GPU dispatch\n\n'
    s+=f'Actual registered installed CLI0.1.35→0.1.36,unchanged C45 author graph/tools/fixture,48frames at12FPS/4s/960×360,288 particle dispatches. **{timing}**. All48 decoded10bit frames and complete384000 Float32 PCM samples equal.\n\n'
    s+='![Actual paired wall time](../assets/gpu-dispatch-20261027-r1/timing.png)\n\n[Actual optimized MKV](../assets/gpu-dispatch-20261027-r1/optimized.mkv) · [Timing data](../assets/gpu-dispatch-20261027-r1/timings.json) · [Source/license](../assets/gpu-dispatch-20261027-r1/SOURCE.txt) · [Media manifest](../assets/gpu-dispatch-20261027-r1/media-manifest.json) · [C45 original source/GIF](#c45-procedural-particles) · [Workflow](GPU_DISPATCH.md) · [Evidence](../validation/GPU管道调度实测_2026-10-27.md).\n\n'
    s+='Original synthetic diagnostic scene,silent track;no model inference. Timing includes launcher,startup,encoding and checks. One measured pair,not realtime/4K/long-form/multivendor performance. Full decode equality is separate from natural quality,continuous human playback and listening;those remain unaccepted.\n';write(p,s)
    for p in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        s=read(p).replace('当前本地 **CLI0.1.35','此前本地 **CLI0.1.35',1);first=s.index('\n')
        s=s[:first]+f'\n\n当前本地 **CLI0.1.36 / alpha.4-local.34 / r37 kit**：[G32原生GPU管道调度](GPU_DISPATCH.md)已实现，实际注册Skill同工程{timing}，48帧及完整PCM相同，656项安装版回归通过。实时/4K/长片/多设备及38项原关闭条件继续保留。\n'+s[first:];write(p,s)
    p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：',1);first=s.index('\n')
    s=s[:first]+'\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.36 / local.34 / r37 kit** · [GPU dispatch](product/GPU_DISPATCH.md) · [Install](releases/CLI_0.1.36_LOCAL.md) · [C46](product/CASES.md#c46-gpu-dispatch).\n'+s[first:];write(p,s)
    text='# GPU管道调度实测 · 2026-10-27\n\nCLI0.1.36 / local.34 / r37。原生Windows，无虚拟化、依赖下载、全局安装或源码回落。\n\n'
    text+=f'最终安装包234文件与源码一致；656项安装版回归通过、零跳过。实际注册Skill完整渲染对照：**{timing}**，全部48帧10bit画面及384000 Float32 PCM采样相同。\n\n'
    text+='## 实际工程和验收范围\n\nC45原创建效包SHA为`'+current['fixture_sha256']+'`，作者图SHA为`'+current['author_graph_sha256']+'`。48帧/12FPS/4秒/960×360，每次288粒子、288仿射、288合成。原版与新版同设备/工具及编码参数，单次配对包含启动/编码/核验。实际输出与耗时图见[C46](../product/CASES.md#c46-gpu-dispatch)。\n\n'
    text+='## 可复核证据\n\n'
    for title,path in [('Offline build/install/source identity','installation-final-r1/verification.json'),('Final installed656 regression','installed-regression-r1/verification.json'),
        ('Baseline registered CLI35 render','render-baseline-r1/verification.json'),('Matched registered CLI36 render','render-installed-r1/verification.json'),
        ('Baseline installed microprofile','profile-installed-r1/verification.json'),('Final installed microprofile','profile-installed-r2/verification.json'),
        ('Unchanged numeric kernels','kernel-identity-r1/verification.json'),('Actual activation/registration','activation-final-r1/activation-and-registration.json'),
        ('Fresh independent r37 kit','kit-r1/verification.json'),('Final delivery audit','final-delivery-r1/verification.json')]:
        text+='- ['+title+'](evidence/gpu-dispatch-20261027-r1/'+path+')\n'
    oldprof=load(BASE/'profile-installed-r1/verification.json')
    text+=f'\n32次8×8算子：旧worker {oldprof["tiny_worker_total_seconds"]:.6f}s，新安装版 {profile["tiny_worker_total_seconds"]:.6f}s；三帧作者图旧{oldprof["GPU_author_frames_seconds"]:.6f}s/新{profile["GPU_author_frames_seconds"]:.6f}s；新CPU/GPU误差{profile["CPU_GPU_max_error"]:.9g}。这些独立计时不与整片相加，微型调用也不代表客户端素材性能。\n\n'
    text+='## 生命周期与失败保留\n\n12项协议测试覆盖碎片读写/UTF8/确切长度上限/截断/重复键/非有限数值/真实满管道/破管道/120次消息和流回收；23项真实GPU测试包含原精度、取消/超时、故障及实际编码恢复。它们均包含于656，未重复加总。工程原子替换/fsync继续生效，高频操作包单独走管道。\n\n'
    text+='[source-control-r1](evidence/gpu-dispatch-20261027-r1/source-control-r1/verification.json)和[source-control-r2](evidence/gpu-dispatch-20261027-r1/source-control-r2/verification.json)为开发期未接纳的测试辅助进程失败：命令行exec字符串换行转义错误，以及Windows测试子进程在导入数值库前直接关闭CRT stdin造成提前退出。辅助代码修复后[source-control-r3](evidence/gpu-dispatch-20261027-r1/source-control-r3/verification.json)12项通过，最终安装版再次通过。原始日志与执行脚本保留，未重写旧结果。\n\n'
    text+='自然画质、完整人类连续播放/听音、实时4K/长片/多设备和总峰值RAM/VRAM仍未验收。该诊断音轨为静音；384000为交错双声道浮点数，等于192000个每声道采样。38原关闭条件和历史记录保持。\n';write('docs/validation/GPU管道调度实测_2026-10-27.md',text)
    record={'status':'documented','cli_version':'0.1.36','readme_R_rows':253,'prior_R_rows_preserved':247,
        'functions':63,'services':21,'capabilities':76,'goal_complete':False,'timing':timing,
        'scope':'Documentation generated only after installed regression,profile and matched frame/PCM checks.'}
    write((out/'verification.json').relative_to(ROOT).as_posix(),json.dumps(record,indent=2)+'\n');print(json.dumps(record))

if __name__=='__main__':main()
