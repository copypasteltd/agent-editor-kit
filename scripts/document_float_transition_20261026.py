"""Maintain complete trilingual documentation from actual installed receipts."""
import argparse,json,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-transition-20261026-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
GUIDE='docs/product/FLOAT_TRANSITIONS.md'
REPORT='docs/validation/Float32转场实测_2026-10-26.md'
BASELINE='b7b33c9b8319c5dfac814e6aba1076dd18ce5ccd'

def load(path):return json.loads(Path(path).read_bytes())
def write(path,text):Path(path).write_text(text,encoding='utf8',newline='\n')
def historical(name):return subprocess.check_output([GIT,'show',BASELINE+':'+name],cwd=ROOT).decode('utf-8-sig')
def rows(text,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--final-kit',action='store_true');args=ap.parse_args()
    install=load(BASE/'installation-final-r1/verification.json');assert install['source_and_installed_equal']
    case=load(BASE/'case-r3/verification.json');assert case['status']=='passed' and case['registered_skill']
    tests={name:load(BASE/name/'verification.json') for name in ('kernel-installed-final-r1','float-installed-r1','audio-final-r1','render-installed-r1','legacy-installed-r1')}
    assert all(t['status']=='passed' and t['skipped']==0 for t in tests.values())
    kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.21-r22.json') if args.final_kit else None
    summaries=[
        '显式线性 Float32 管线新增 57 种 xfade 图案与黑/白 dip，真实源句柄、关联音轨及组级空间进出场已接入。实际统一 Skill 完成 6秒/72帧案例，倒放、预览、取消恢复、队列与逐样本音频核对通过。CPU 执行；默认路径与 GPU 投影沿用各自契约。',
        '明確線性 Float32 管線新增 57 種 xfade 圖案及黑/白 dip，真實來源句柄、關聯音軌與群組空間進出場已接入。實際統一 Skill 完成 6秒/72影格案例，倒放、預覽、取消恢復、佇列與逐樣本音訊核對通過。CPU 執行；預設管線與 GPU 投影沿用各自契約。',
        'The explicit linear Float32 path adds 57 xfade patterns plus black/white dips, real source handles, linked audio and spatial group edges. The registered Skill completes a 6s/72-frame case with reverse, preview, cancel/resume, queues and independent PCM checks. CPU execution; default rendering and GPU projection keep their own contracts.'
    ]
    feature_rows=[
        '| F55 | 线性浮点转场与组级进出场 | 显式 Float32 工程 → 57 xfade图案+2 dip、预乘alpha混合、真实句柄/原作者时钟、关联音轨、组级擦除/推移与实际预览成片。 | `timeline transition; preview; render; queue` | CPU；12种真实句柄声明，其他图案用显式重叠/边缘；normal双源混合；风噪有平台差异，HDR/自然质量未闭。 |',
        '| F55 | 線性浮點轉場與群組進出場 | 明確 Float32 專案 → 57 xfade圖案+2 dip、預乘alpha混合、真實句柄/原作者時鐘、關聯音軌、群組擦除/推移及實際預覽成片。 | `timeline transition; preview; render; queue` | CPU；12種真實句柄宣告，其他圖案用明確重疊/邊緣；normal雙源混合；風噪有平台差異，HDR/自然品質未閉。 |',
        '| F55 | Linear Float32 transitions and group edges | Explicit Float32 projects → 57 xfade patterns+2 dips,premultiplied alpha,real handles/original clocks,linked audio,group wipe/slide,actual preview and encoding. | `timeline transition; preview; render; queue` | CPU;12 real-handle declaration types,other patterns use overlap/edges;normal paired blending;platform-dependent wind,HDR/natural quality open. |'
    ]
    targets=['installation-final-r1/verification.json','kernel-installed-final-r1/verification.json','xfade-r1/verification.json',
        '4k-r1/verification.json','render-installed-r1/verification.json','case-r3/verification.json','case-r3/verification.json','final-delivery-r2/verification.json']
    details=[
        f'CLI0.1.21/local.19-final-r1，211产品文件与新ZIP安装版逐字节一致；70 Skill文件，1入口/17模块',
        '25项专项0skip；预乘alpha、全部59图案/不同分块、真实句柄、奇数剪口、VFR、倒放/裁切/定格/非线性父时钟、取消通过',
        '57图案实际独立FFmpeg对照；53个非风噪图案误差最多1个16位码值；4风噪记录平台哈希差异，不声称逐位相同',
        '安装版3840×2160淡化/逐行模糊/擦除完整帧核对；512MiB分配估算，最大误差5.96e-8；非实时/峰值RSS验收',
        f"分别通过98浮点、64音频/源句柄/嵌套、44安装版预览/渲染及{tests['legacy-installed-r1']['tests']}CLI/默认预览/队列/Schema，全部0skip，不合并计数",
        f"实际注册Skill完成6秒/72帧、5组真实句柄及配对音轨、子序列倒放、组级空间边缘；288000双声道采样误差{case['max_pcm_error']:.12g}",
        '编码器启动后取消，再按原操作恢复；队列显式MKV/PCM，同一成片全部帧/时钟/PCM一致；quality通过，作者数据/权利台账不改',
        '三语55功能/20服务/17模块与75能力字段同步；C29 MP4/GIF/可编辑包、r22独立kit；保留146历史行和38原关闭条件'
    ]
    for language,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        path=ROOT/name;text=path.read_text('utf-8-sig')
        text=text.replace('<!-- opencl-projection-current -->','<!-- opencl-projection-history -->').replace('<!-- /opencl-projection-current -->','<!-- /opencl-projection-history -->')
        text=text.replace('**CLI0.1.20 / alpha.4-local.18 / r21 kit**','**Historical / 历史 / 歷史：CLI0.1.20 / alpha.4-local.18 / r21 kit**')
        block='<!-- float-transition-current -->\n\n**CLI0.1.21 / alpha.4-local.19 / r22 kit · 1 Skill / 17 modules.**\n\n'+summaries[language]+'\n\n'
        block+='[Workflow / 使用流程]('+GUIDE+') · [C29](docs/product/CASES.md#c29-float-transitions) · [Local install](docs/releases/CLI_0.1.21_LOCAL.md) · [Evidence]('+REPORT+')\n\n'
        block+='![Actual registered Skill output / silent GIF](docs/assets/float-transition-20261026-r3/transitions.gif)\n\n'
        block+='CPU Float32; source-handle types and overlap/edge patterns are distinct. Natural audiovisual, HDR, long-form and all original target conditions remain open.\n\n<!-- /float-transition-current -->\n\n'
        if '<!-- float-transition-current -->' in text:
            text=re.sub(r'<!-- float-transition-current -->.*?<!-- /float-transition-current -->\n\n',lambda _:block,text,count=1,flags=re.S)
        else:text=text.replace('<!-- opencl-projection-history -->',block+'<!-- opencl-projection-history -->',1)
        text=text.replace('local.18/final-r2/installed','local.19/final-r1/installed')
        lines=[]
        for line in text.splitlines():
            if not re.match(r'^\| R\d+\s*\|',line):
                if 'local.19/final-r1/installed' in line or ('GOAL_GAPS_20261025.md)' in line):line=line.replace('CLI 0.1.20','CLI 0.1.21')
                if line.startswith('**') and '359' in line:line=line.replace('CLI 0.1.20','CLI 0.1.21')
                if line.startswith('**') and 'unified-skill-r21.zip' in line:line=line.replace('unified-skill-r21.zip','unified-skill-r22.zip').replace('r21 Skill kit','r22 Skill kit')
            lines.append(line)
        text='\n'.join(lines)+'\n'
        if re.search(r'^\| F55\s*\|',text,re.M):text=re.sub(r'^\| F55\s*\|.*$',lambda _:feature_rows[language],text,flags=re.M)
        else:
            last=re.search(r'^\| F54\s*\|.*$',text,re.M);assert last
            text=text[:last.end()]+'\n'+feature_rows[language]+text[last.end():]
        for number,(detail,target) in enumerate(zip(details,targets),147):
            # Evidence IDs and measurements are kept identical across languages.
            row=f'| R{number} | 2026-10-26 Float32 transitions | {detail} | [Evidence](docs/validation/evidence/float-transition-20261026-r1/{target}) |'
            if language==1:
                traditional=[
                    'CLI0.1.21/local.19-final-r1，211個產品檔案與ZIP安裝版逐位元組相同；70個Skill檔案，1入口／17模組',
                    '25項專項測試、零略過；預乘alpha、全部59種圖案／不同分塊、真實來源句柄、奇數剪口、VFR、倒放／裁切／定格／非線性父時鐘及取消均通過',
                    '全部57種圖案與獨立原生FFmpeg實際對照；53種非風噪圖案最多相差1個16位元碼值；4種風噪記錄平台雜湊差異，未聲稱逐位元相同',
                    '安裝版3840×2160淡化／逐行模糊／擦除完整影格核對；512MiB分配估算，最大誤差5.96e-8；未作即時／峰值RSS驗收',
                    f"分別通過98項浮點、64項音訊／來源句柄／巢狀、44項安裝版預覽／算繪及{tests['legacy-installed-r1']['tests']}項CLI／預設預覽／佇列／Schema測試；全部零略過，未合併計數",
                    f"實際註冊Skill完成6秒／72影格、5組真實來源句柄及配對音軌、子序列倒放、群組空間邊緣；288000個雙聲道取樣誤差{case['max_pcm_error']:.12g}",
                    '編碼器啟動後取消，再依原操作恢復；佇列明確指定MKV／PCM，全部影格／時鐘／PCM相同；quality通過，作者資料與權利臺帳未改',
                    '三語55功能／20服務／17模組與75能力欄位同步；C29 MP4／GIF／可編輯套件、r22獨立工具包；保留146列歷史紀錄及38項原關閉條件'][number-147]
                row=f'| R{number} | 2026-10-26 Float32 transitions | {traditional} | [Evidence](docs/validation/evidence/float-transition-20261026-r1/{target}) |'
            if language==2:
                english=[
                    'CLI0.1.21/local.19-final-r1;211 product files byte-match the installed ZIP;70 Skill files,one entry/17 modules',
                    '25 tests,zero skips:alpha,all59 patterns/tiles,real handles,odd cuts,VFR,reverse/trim/freeze/nonlinear parents and cancellation',
                    'All57 native FFmpeg midpoint comparisons;53 non-wind patterns differ by at most one16-bit code;four wind hashes reported without bit-parity claim',
                    'Installed3840x2160 full-frame fade/row-blur/wipe checks;512MiB allocation estimate,error<=5.96e-8;not realtime/peak-RSS acceptance',
                    f"Separate passing groups:98 float,64 audio/handles/nesting,44 installed preview/render,and{tests['legacy-installed-r1']['tests']}CLI/default-preview/queue/schema;zero skips,no combined count",
                    f"Actual registered Skill:6s/72frames,five real-handle/audio pairs,reversed child and spatial group edges;288000 stereo samples,error={case['max_pcm_error']:.12g}",
                    'Cancel after encoder startup,resume same operation,explicit MKV/PCM queue:all frames/clocks/PCM match;quality passes,authoring/rights unchanged',
                    'Three languages:55 functions/20 services/17 modules/75 declarations;C29 MP4/GIF/editable package,r22 isolated kit;146 history rows and38 closures retained'][number-147]
                row=f'| R{number} | 2026-10-26 Float32 transitions | {english} | [Evidence](docs/validation/evidence/float-transition-20261026-r1/{target}) |'
            if re.search(r'^\| R'+str(number)+r'\s*\|',text,re.M):text=re.sub(r'^\| R'+str(number)+r'\s*\|.*$',lambda _:row,text,flags=re.M)
            else:
                last=re.search(r'^\| R'+str(number-1)+r'\s*\|.*$',text,re.M);assert last
                text=text[:last.end()]+'\n'+row+text[last.end():]
        license_note='\nFloat32 transition derivative: [LGPL-2.1-or-later notice](product/src/ai_ad_editor/float_transitions_NOTICE.txt) · [complete license](product/src/ai_ad_editor/COPYING.LGPLv2.1.txt). Other files retain their stated licenses.\n'
        if license_note not in text:text+=license_note
        before=rows(historical(name),'R');after=rows(text,'R');assert len(before)==146 and all(after[k]==v for k,v in before.items())
        write(path,text)
    machine=load(BASE/'case-r3/capabilities.json');write(ROOT/'docs/product/float-transition-capabilities-cli-0.1.21.json',json.dumps(machine,ensure_ascii=False,indent=2)+'\n')
    for prefix in ('docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
        for i,suffix in enumerate(('','.zh-TW','.en')):
            path=ROOT/(prefix+suffix+'.md');text=path.read_text('utf8');route='../product/' if prefix.startswith('docs/skills') else ''
            block='<!-- community-current -->\n\n**CLI0.1.21 / alpha.4-local.19 / r22 kit · 1 Skill / 17 modules / 70 files.**\n\n'+summaries[i]+'\n\n'
            block+='[Float32 workflow]('+route+'FLOAT_TRANSITIONS.md) · [GPU projection]('+route+'OPENCL_PROJECTION.md) · [Install]('+route+'COMMUNITY_LOCAL_DELIVERY.md) · [75 declarations]('+route+'float-transition-capabilities-cli-0.1.21.json).\n\n<!-- /community-current -->'
            text,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,text,count=1,flags=re.S);assert n==1;write(path,text)
    path=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=path.read_text('utf8')
    for a,b in [('0.1.20','0.1.21'),('local.18','local.19'),('candidate-r2','candidate-r1'),('final-r2','final-r1'),('unified-skill-r21','unified-skill-r22'),('0.1.21-r21','0.1.21-r22'),('r21 kit','r22 kit'),
        ('088b588151d425324ee98019b38772e5a464a00a509d1d15f8eba01e7cd41841',install['archive_sha256']),
        ('8aeb0ab5cd67b54e1d28367bd41672902df8d897595e4a7d64070277afea68a4',install['manifest_sha256'].removeprefix('sha256:'))]:text=text.replace(a,b)
    note='\n2026-10-26：CLI0.1.21 已安装线性浮点转场/真实句柄/关联音轨/组级空间进出场；[完整使用与实际案例](FLOAT_TRANSITIONS.md)，[211文件固定离线交付](../releases/CLI_0.1.21_LOCAL.md)。CPU浮点路径与既有GPU投影、GPU语音/翻译分别选择。旧包和全部原关闭条件保留。\n'
    if note not in text:text+=note
    write(path,text)
    for name in ('GOAL_GAPS_20261025.md','IMPLEMENTATION_PLAN_20261025.md'):
        path=ROOT/'docs/product'/name;text=path.read_text('utf8')
        text=text.replace('当前本地 **CLI0.1.20','此前本地 **CLI0.1.20',1)
        current='当前本地 **CLI0.1.21 / alpha.4-local.19 / r22 kit**：线性浮点转场、真实源句柄/关联音轨和组级空间进出场已安装；[使用与实际案例](FLOAT_TRANSITIONS.md)。全部38原关闭条件保持。'
        if current not in text:
            at=text.index('\n\n')+2;text=text[:at]+current+'\n\n'+text[at:]
        if name.startswith('GOAL'):
            match=re.search(r'^\| G05\s*\|.*$',text,re.M);parts=match[0].split('|')
            parts[3]=' 默认24类家族及源句柄；CLI0.1.21新增显式Float32的57图案+2 dip、预乘alpha/原时钟、组级空间边缘、真实源句柄/关联音轨，6秒安装版成片/预览/恢复/队列留证 '
            parts[4]=' 默认8bit组级空间路径仍有限；Float32尚有字幕/生成器等未移植操作，非normal双源/自动克隆不支持；自然运动/HDR/长片及跨平台质量继续验收 '
            text=text[:match.start()]+'|'.join(parts)+text[match.end():]
            text=re.sub(r'^\| V01\s*\|.*$','| V01 | 当前已安装与注册 | local.19-final-r1 / CLI0.1.21，1Skill/17模块、70文件、r22 kit；[211文件固定安装](../validation/evidence/float-transition-20261026-r1/installation-final-r1/verification.json)，旧包保留 |',text,flags=re.M)
            text=text.replace('[当前全部字段](opencl-projection-capabilities-cli-0.1.20.json)','[当前全部字段](float-transition-capabilities-cli-0.1.21.json)')
            before=rows(historical('docs/product/'+name),'G');after=rows(text,'G');assert len(before)==38 and all(after[k].split('|')[5]==v.split('|')[5] for k,v in before.items())
        else:
            text+='\n2026-10-26 W03/G05：'+summaries[0]+'[实际证据](../validation/Float32转场实测_2026-10-26.md)。\n' if '2026-10-26 W03/G05' not in text else ''
        write(path,text)
    path=ROOT/'docs/product/CASES.md';text=path.read_text('utf8')
    case_block='''
<a id="c29-float-transitions"></a>

## C29 线性浮点转场、原素材音轨与子序列倒放 / Float32 transitions

实际单一注册 Skill 调用 CLI0.1.21，6秒/72帧/12fps；五个真实源剪口、独立关联声音、子序列倒放、组级擦除/推移。自制几何图像与合成双声道音调，CC0。预览、编码、编码器启动后取消/原设置恢复、显式MKV/PCM队列、完整帧/时钟/PCM一致，quality通过。音频为验证信号，不是配音/音乐自然质量证明。

[完整流程](FLOAT_TRANSITIONS.md) · [实测](../validation/Float32转场实测_2026-10-26.md) · [原视频](../assets/float-transition-20261026-r3/original.native.mkv) · [原音轨](../assets/float-transition-20261026-r3/original.audio.wav) · [实际MP4](../assets/float-transition-20261026-r3/transitions.mp4) · [可编辑包](../assets/float-transition-20261026-r3/editable-transitions.aevpkg.zip)

![Actual registered Skill composition / silent GIF](../assets/float-transition-20261026-r3/transitions.gif)

CPU Float32；512MiB工作区单帧4K核对不等于实时或全进程资源验收。未做连续播放/人工听审，自然视听/HDR/长片/全剪映等价仍开放。
'''
    if 'id="c29-float-transitions"' not in text:text+='\n'+case_block
    write(path,text)
    path=ROOT/GUIDE;text=path.read_text('utf8')
    example='''
## 已安装案例与复现

[原输入](../assets/float-transition-20261026-r3/original.native.mkv) · [原音轨](../assets/float-transition-20261026-r3/original.audio.wav) · [MP4](../assets/float-transition-20261026-r3/transitions.mp4) · [可编辑包](../assets/float-transition-20261026-r3/editable-transitions.aevpkg.zip) · [完整命令/核验](../validation/evidence/float-transition-20261026-r1/case-r3/verification.json)。

```powershell
$caseZip = 'E:/dev/sandbox/AI广告剪辑/docs/assets/float-transition-20261026-r3/editable-transitions.aevpkg.zip'
$project = 'E:/video-work/float-transitions-review'
& $avk convert import --input $caseZip --output $project
& $avk validate --project $project
& $avk preview frame --project $project --frame 36
& $avk render --project $project --output (Join-Path $project 'renders/review.mkv') --container mkv --hardware-encode off
```

选择新的工程目录和输出。队列作业还须显式写 `container:"mkv"` 与匹配的 PCM 音频设置；队列默认 MP4，不根据输出扩展名改容器。案例原格式 MKV 保留完整 Float32 PCM；展示 MP4 另作明确输出传递转换和 AAC 压缩，不作为无损音频证据。

![Actual registered Skill output / silent](../assets/float-transition-20261026-r3/transitions.gif)
'''
    if '## 已安装案例与复现' not in text:text+='\n'+example
    write(path,text)
    counts='\n'.join(f"| {name} | {r['tests']} passed / 0 skip | [receipt](evidence/float-transition-20261026-r1/{name}/verification.json) |" for name,r in tests.items())
    evidence=f'''# Float32 转场实际核验（2026-10-26）

CLI0.1.21 / local.19-final-r1。211产品Python文件与ZIP安装版逐字节一致，单一Skill/17模块/70文件。新包 `{install['archive_bytes']}` bytes，SHA-256 `{install['archive_sha256']}`。[固定安装](evidence/float-transition-20261026-r1/installation-final-r1/verification.json)。

| 独立执行组 | 结果 | 证据 |
|---|---|---|
{counts}

不把这些组、历史测试与当轮渲染混为总体通过率。原始失败记录保留。

[原生FFmpeg全部57图案中点对照](evidence/float-transition-20261026-r1/xfade-r1/verification.json)：53个非风噪图案最多1个16位码值误差；四风噪的正弦哈希平台差异逐项报告，未放宽为逐位一致。[4K完整图像](evidence/float-transition-20261026-r1/4k-r1/verification.json)：3840×2160，淡化1.762秒、逐行模糊3.434秒、擦除1.537秒，各自全像素独立核对，最大误差5.96e-8；512MiB为分配估算，未测进程峰值RSS，不是实时保证。

[实际注册Skill案例](evidence/float-transition-20261026-r1/case-r3/verification.json)：6秒、72帧、12fps，5个真实剪口及关联音轨、256×144子画布→320×180输出、父级倒放与组级擦除/推移。全部288000双声道采样与独立原源/作者时钟公式误差 `{case['max_pcm_error']:.12g}`。编码器输出出现后实际请求取消；恢复与明确MKV/PCM队列的全部帧/时钟/PCM一致，quality通过。原作者设置/资产/序列及Rights Ledger保持；实际MP4/GIF/原始输入及可编辑包见[C29](../product/CASES.md#c29-float-transitions)。

失败与修正：[首轮kernel](evidence/float-transition-20261026-r1/kernel-r1/verification.json)发现dip用1-p反算导致剪口极小残值，改为使用原进度后精确抵达matte；[首轮audio](evidence/float-transition-20261026-r1/audio-r1/verification.json)把倒放成品PCM错作原作者连续时钟包络参考，改为独立原源公式，并显式配置已有Rubber Band以消除一次skip；[case-r1](evidence/float-transition-20261026-r1/case-r1/verification.json)在任务创建前取消，无可续跑operation；[case-r2](evidence/float-transition-20261026-r1/case-r2/verification.json)恢复通过，但队列夹具漏写container而默认MP4/PCM冲突。后两者修正执行时机与显式请求，在全新r3工程重做完整流程，产品未改、标准未放宽。

最终审计r1因误用GitHub仅返回稳定版的`/releases/latest`而404；r2改为读取真实预发布列表，原失败留档，产品与关闭条件未改。

FFmpeg派生模块保留 LGPL-2.1-or-later 源码、完整许可和NOTICE；不是把所有依赖改标MIT。CPU浮点与现有OpenCL投影/GPU模型独立，未移植算子明确拒绝。静帧观察另记；未做连续播放、人工听审、自然素材/HDR/长片/通用4K验收。全部G01–G38原关闭条件与完整目标继续有效。
'''
    write(ROOT/REPORT,evidence)
    kit_desc=f"{kit['files']} files / {kit['bytes']} bytes / SHA-256 `{kit['sha256']}`" if kit else '摘要与文件数以匹配的r22版本化JSON为准'
    release=f'''# CLI0.1.21 本地交付 / Local delivery

2026-10-26，agent editor kit，`v0.1.0-alpha.4-local.19` / final-r1，原生Windows x64/CPython3.13。211产品Python文件、70 Skill文件、单一入口/17模块。新增线性浮点转场、真实句柄/关联声音及组级空间进出场。[完整使用流程、信号、类型、预览与可编辑案例](../product/FLOAT_TRANSITIONS.md)。

| Item | Path under E:/dev/sandbox/AI广告剪辑/ | SHA-256 |
|---|---|---|
| Application ZIP / {install['archive_bytes']} bytes | `local/agent-ffmpeg/v0.1.0-alpha.4-local.19/candidate-r1/bundle.zip` | `{install['archive_sha256']}` |
| Bundle manifest | ZIP `manifest.json` | `{install['manifest_sha256'].removeprefix('sha256:')}` |
| Installed runtime | `local/agent-ffmpeg/v0.1.0-alpha.4-local.19/final-r1/installed/` | [211-file proof](../validation/evidence/float-transition-20261026-r1/installation-final-r1/verification.json) |
| r22 single Skill kit / {kit_desc} | [r22 ZIP](../skills/agent-editor-kit-community-unified-skill-r22.zip) | [metadata](../skills/community-unified-skill-package-0.1.21-r22.json) |

[Offline install/register](../product/COMMUNITY_LOCAL_DELIVERY.md) · [75 installed declarations](../product/float-transition-capabilities-cli-0.1.21.json) · [Actual evidence](../validation/Float32转场实测_2026-10-26.md) · [17 modules](../product/SKILLS.md)。公开alpha.3/CLI0.1.2及其附件保留，未覆盖标签或公开资产；此页是新本地交付。

原生Python、FFmpeg/驱动和可选模型另备，无Docker/WSL/虚拟环境、隐式下载或后台模型服务器。现有500风格、359资源、GPU配音/翻译、OpenCL投影与其证据保持；此次Float32转场执行在CPU。自然视听、HDR、长片和完整剪映等价继续验收，全部原关闭条件保留。
'''
    write(ROOT/'docs/releases/CLI_0.1.21_LOCAL.md',release)
    path=ROOT/'scripts/sync_capability_manuals.py';text=path.read_text('utf8').replace('0.1.20','0.1.21').replace('local.18','local.19').replace('r21 kit','r22 kit')
    text=text.replace("('F', 54)","('F', 55)").replace("('F',54)","('F',55)").replace('functional_rows=54','functional_rows=55')
    text=text.replace('Native OpenCL crop/affine/child-canvas bilinear/area projection,','Linear Float32 transitions/source handles/group edges, native OpenCL crop/affine/child-canvas projection,')
    text=text.replace("'[GPU projection workflow/preview](OPENCL_PROJECTION.md)","'[Float32 transition workflow](FLOAT_TRANSITIONS.md) · [GPU projection workflow/preview](OPENCL_PROJECTION.md)")
    write(path,text)
    path=ROOT/'docs/README.md';text=path.read_text('utf8')
    index='\nCurrent local / 当前本地 / 目前本地：**CLI0.1.21 / local.19 / r22 kit** · [Float32 transitions](product/FLOAT_TRANSITIONS.md) · [Local bundle](releases/CLI_0.1.21_LOCAL.md) · [Actual case](product/CASES.md#c29-float-transitions).\n'
    if index not in text:
        at=text.index('\n\n')+2;text=text[:at]+index+'\n'+text[at:]
    write(path,text)
    print(json.dumps(dict(status='documented',functions=55,services=20,readme_evidence_rows=154,historical_rows_preserved=146,goal_closures_preserved=38,final_kit=bool(kit))))

if __name__=='__main__':main()
