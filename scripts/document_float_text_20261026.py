"""Maintain three-language feature/workflow/history using actual installed evidence."""
import argparse,json,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-text-20261026-r1'
BASELINE='15c8561d9bd2a1536f34ee79d6cd035db8351335'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
GUIDE='docs/product/FLOAT_TEXT.md'
REPORT='docs/validation/Float32文字字幕实测_2026-10-26.md'

def load(p):return json.loads(Path(p).read_bytes())
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d{2,3})\s*\|.*$',s,re.M)}
def before(name):return subprocess.check_output([GIT,'show',BASELINE+':'+name],cwd=ROOT).decode('utf-8-sig')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--final-kit',action='store_true');args=ap.parse_args()
    install=load(BASE/'installation-final-r2/verification.json');case=load(BASE/'case-r3/verification.json')
    assert install['source_and_installed_equal'] and case['status']=='passed' and case['registered_skill']
    tests={g:load(BASE/(g+'-installed-final-r1')/'verification.json') for g in ('text','float','audio','render','legacy','text-legacy')}
    assert all(r['status']=='passed' and r['skipped']==0 for r in tests.values())
    kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.22-r23.json') if args.final_kit else None
    summaries=[
        '线性浮点管线已接入独立文字、片段内字幕、打字机/逐词高亮联动及纯文本SRT；保留原作者时钟、裁切偏移和父级倒放边界。四组件颜色与alpha独立核对，实际统一Skill完成含转场与关联音轨的6秒/72帧案例。文字合成为CPU，字形覆盖率8位、颜色与合成Float32。',
        '線性浮點管線已接入獨立文字、片段內字幕、打字機／逐詞高亮聯動及純文字SRT；保留原作者時鐘、裁切偏移與父級倒放邊界。四元件顏色與alpha獨立核對，實際統一Skill完成含轉場與關聯音軌的6秒／72影格案例。文字合成為CPU，字形覆蓋率8位元、顏色與合成Float32。',
        'The linear Float32 pipeline now renders independent titles, inline captions, joint typewriter/word highlights and plain SRT, preserving original clocks, trim offsets and reversed parent boundaries. Independent component color/alpha checks and an actual registered-Skill 6s/72-frame case cover transitions and linked audio. Text runs on CPU:8-bit glyph coverage,Float32 colors/composition.'
    ]
    features=[
        '| F56 | 线性浮点文字与字幕 | 独立字层/片段内字幕/SRT → 原生塑形、线性底框/阴影/描边/填充、逐词与打字机联动、原时钟/倒放、真实预览与成片。 | `timeline compose; preview; render; queue` | 明确本地字体；CPU；覆盖率8bit/颜色Float32；纯文本SRT，复杂Bidi/4K文字/GPU文字未闭。 |',
        '| F56 | 線性浮點文字與字幕 | 獨立字層／片段內字幕／SRT → 原生塑形、線性底框／陰影／描邊／填充、逐詞與打字機聯動、原時鐘／倒放、實際預覽與成片。 | `timeline compose; preview; render; queue` | 明確本機字型；CPU；覆蓋率8bit／顏色Float32；純文字SRT，複雜Bidi／4K文字／GPU文字未閉。 |',
        '| F56 | Linear Float32 text and captions | Independent/inline/SRT → native shaping,linear box/shadow/border/fill,joint word/typewriter,original/reverse clocks,actual preview and rendering. | `timeline compose; preview; render; queue` | Explicit local font;CPU;8bit coverage/Float32 color;plain SRT;complex Bidi/4K/GPU text open. |'
    ]
    targets=['installation-final-r2/verification.json','text-installed-final-r1/verification.json','text-installed-final-r1/text_receipts.json',
             'float-installed-final-r1/verification.json','text-legacy-installed-final-r1/verification.json','case-r3/verification.json',
             'case-r3/verification.json','final-delivery-r4/verification.json']
    details=[
        [f'CLI0.1.22/local.20-final-r2；213产品文件与新离线安装一致；单一Skill/17模块/71文件',
         f'19项文字专项、0skip：独立颜色/alpha、四组件、逐词/打字机、SRT、倒放、窗口/定格、缓存、变更和原生取消清理',
         '全部256覆盖率码值重建误差0；sRGB EOTF/alpha误差≤3e-7；未覆盖原媒体逐位保持且保留>256级灰阶',
         f"分别{tests['float']['tests']}浮点/{tests['audio']['tests']}音频源句柄嵌套/{tests['render']['tests']}标准预览渲染，全部0skip，不合并计数",
         f"分别{tests['text-legacy']['tests']}默认文字/{tests['legacy']['tests']}CLI预览队列Schema，全部0skip；旧未知生成器拒绝错误码保留",
         f"真实注册Skill6秒/72帧：中文SRT、打字机+逐词、旋转/内嵌字、父倒放/真实句柄；288000双声道采样误差{case['max_pcm_error']:.12g}",
         '编码器启动后取消/同操作恢复/显式MKV队列，全部帧/时钟/PCM相同；quality和原作者/权利不变；可编辑包保留字体许可',
         '三语56功能/20服务/17模块/75能力、C30原素材/MP4/GIF/工程包、r23独立kit；保留154历史行及38原关闭条件'],
        [f'CLI0.1.22/local.20-final-r2；213個產品檔案與新離線安裝相同；單一Skill／17模組／71檔案',
         '19項文字專項、零略過：獨立顏色／alpha、四元件、逐詞／打字機、SRT、倒放、視窗／定格、快取、變更與原生取消清理',
         '全部256個覆蓋率碼值重建誤差0；sRGB EOTF／alpha誤差≤3e-7；未覆蓋原媒體逐位元保持且保留>256級灰階',
         f"分別{tests['float']['tests']}項浮點／{tests['audio']['tests']}項音訊句柄巢狀／{tests['render']['tests']}項標準預覽算繪，全部零略過，未合併計數",
         f"分別{tests['text-legacy']['tests']}項預設文字／{tests['legacy']['tests']}項CLI預覽佇列Schema，全部零略過；保留未知產生器拒絕錯誤碼",
         f"實際註冊Skill6秒／72影格：中文SRT、打字機+逐詞、旋轉／內嵌字、父倒放／真實句柄；288000雙聲道取樣誤差{case['max_pcm_error']:.12g}",
         '編碼器啟動後取消／同操作恢復／明確MKV佇列，全部影格／時鐘／PCM相同；quality及作者／權利保持；可編輯包保留字型授權',
         '三語56功能／20服務／17模組／75能力、C30原素材／MP4／GIF／工程包、r23獨立kit；保留154歷史列及38原關閉條件'],
        ['CLI0.1.22/local.20-final-r2;213 source files byte-match the offline installation;one Skill/17 modules/71 files',
         '19 text tests,zero skips:independent color/alpha,four components,word/typewriter,SRT,reverse,trim/freeze,cache,mutation and native cancel cleanup',
         'All256 coverage codes reconstruct exactly;sRGB EOTF/alpha error<=3e-7;uncovered original media bits retained with>256 gray values',
         f"Separate groups:{tests['float']['tests']}float/{tests['audio']['tests']}audio-handles-nesting/{tests['render']['tests']}standard-preview-render;zero skips,no combined count",
         f"Separate groups:{tests['text-legacy']['tests']}default-text/{tests['legacy']['tests']}CLI-preview-queue-schema;zero skips;unknown-generator rejection code retained",
         f"Actual registered Skill:6s/72frames,Chinese SRT,joint typewriter/highlight,rotation/inline text,reversed parent/real handles;288000stereo samples,error={case['max_pcm_error']:.12g}",
         'Cancel after encoder startup,resume same operation,explicit MKV queue:all frames/clocks/PCM match;quality passes,authoring/rights retained;editable package includes font license',
         'Three languages:56 functions/20 services/17 modules/75 declarations;C30 original/MP4/GIF/editable package,r23 isolated kit;154 historical rows and38 closures retained']]
    for i,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        path=ROOT/name;text=path.read_text('utf-8-sig')
        transition_limits = [
            ('以默认渲染路径和具体层级为准；Float32 后续转场候选未随本版提供。', '按渲染路径和层级选择；显式 Float32 已提供 F55 的转场子集，CPU 执行，支持范围见其独立契约。'),
            ('以預設渲染路徑和具體層級為準；Float32 後續轉場候選未隨本版提供。', '依算繪路徑和層級選擇；明確 Float32 已提供 F55 的轉場子集，CPU 執行，支援範圍見獨立契約。'),
            ('Support depends on renderer and layer context; later Float32 transition candidates are not bundled.', 'Select by renderer and layer context; the explicit CPU Float32 subset is delivered under the separate F55 contract.')]
        obsolete_notes = [
            '后续 Float32 转场/运行时闭包候选 R113/R114 未随本版提供。',
            '後續 Float32 轉場/運行時閉包候選 R113/R114 未隨本版提供。',
            'Later R113/R114 Float32 transition/runtime-closure candidates are not included in this release.']
        text=text.replace(*transition_limits[i]).replace(' '+obsolete_notes[i], '').replace(obsolete_notes[i], '')
        text=text.replace('outside current core acceptance. \n', 'outside current core acceptance.\n')
        text=text.replace('<!-- float-transition-current -->','<!-- float-transition-history -->').replace('<!-- /float-transition-current -->','<!-- /float-transition-history -->')
        text=text.replace('**CLI0.1.21 / alpha.4-local.19 / r22 kit','**Historical / 历史 / 歷史：CLI0.1.21 / alpha.4-local.19 / r22 kit')
        block='<!-- float-text-current -->\n\n**CLI0.1.22 / alpha.4-local.20 / r23 kit · 1 Skill / 17 modules.**\n\n'+summaries[i]+'\n\n'
        block+='[Workflow / 使用流程]('+GUIDE+') · [C30](docs/product/CASES.md#c30-float-text) · [Local install](docs/releases/CLI_0.1.22_LOCAL.md) · [Evidence]('+REPORT+')\n\n'
        block+='![Actual registered Skill native text / silent GIF](docs/assets/float-text-20261026-r3/native-text.gif)\n\n'
        block+='Plain SRT/explicit font;CPU text;4K native text currently rejected by workspace admission. Full original target conditions remain open.\n\n<!-- /float-text-current -->\n\n'
        if '<!-- float-text-current -->' in text:text=re.sub(r'<!-- float-text-current -->.*?<!-- /float-text-current -->\n\n',lambda _:block,text,count=1,flags=re.S)
        else:text=text.replace('<!-- float-transition-history -->',block+'<!-- float-transition-history -->',1)
        lines=[]
        for line in text.splitlines():
            if not re.match(r'^\| R\d+\s*\|',line):
                line=line.replace('local.19/final-r1/installed','local.20/final-r2/installed')
                if 'local.20/final-r2/installed' in line or 'GOAL_GAPS_20261025.md)' in line:line=line.replace('CLI 0.1.21','CLI 0.1.22')
                if line.startswith('**') and 'unified-skill-r22.zip' in line:line=line.replace('unified-skill-r22.zip','unified-skill-r23.zip').replace('r22 Skill kit','r23 Skill kit')
            lines.append(line)
        text='\n'.join(lines)+'\n'
        if 'F56' in rows(text,'F'):text=re.sub(r'^\| F56\s*\|.*$',lambda _:features[i],text,flags=re.M)
        else:
            last=re.search(r'^\| F55\s*\|.*$',text,re.M);assert last
            text=text[:last.end()]+'\n'+features[i]+text[last.end():]
        for n,(detail,target) in enumerate(zip(details[i],targets),155):
            row=f'| R{n} | 2026-10-26 Float32 text | {detail} | [Evidence](docs/validation/evidence/float-text-20261026-r1/{target}) |'
            if f'R{n}' in rows(text,'R'):text=re.sub(r'^\| R'+str(n)+r'\s*\|.*$',lambda _:row,text,flags=re.M)
            else:
                last=re.search(r'^\| R'+str(n-1)+r'\s*\|.*$',text,re.M);assert last
                text=text[:last.end()]+'\n'+row+text[last.end():]
        old=rows(before(name),'R');assert len(old)==154 and all(rows(text,'R')[k]==v for k,v in old.items())
        write(path,text)
    write(ROOT/'docs/product/float-text-capabilities-cli-0.1.22.json',json.dumps(load(BASE/'case-r3/capabilities.json'),ensure_ascii=False,indent=2)+'\n')
    for prefix in ('docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
        for suffix in ('','.zh-TW','.en'):
            path=ROOT/(prefix+suffix+'.md');text=path.read_text('utf-8-sig')
            text=text.replace('0.1.21 / alpha.4-local.19 / r22 kit','0.1.22 / alpha.4-local.20 / r23 kit').replace('70 files.','71 files.')
            text=text.replace('float-transition-capabilities-cli-0.1.21.json','float-text-capabilities-cli-0.1.22.json')
            link='../product/FLOAT_TEXT.md' if prefix.startswith('docs/skills') else 'FLOAT_TEXT.md'
            note='\nCLI0.1.22: independent/inline Float32 text, joint typewriter/highlight and plain SRT. Read [workflow]('+link+'); CPU,8bit coverage/Float32 colors,explicit fonts and original clocks. 4K text/GPU text/rich ASS and full target acceptance remain open.\n'
            if note not in text:text+=note
            write(path,text)
    for name in ('GOAL_GAPS_20261025.md','IMPLEMENTATION_PLAN_20261025.md'):
        path=ROOT/'docs/product'/name;text=path.read_text('utf-8-sig')
        text=text.replace('当前本地 **CLI0.1.21','此前本地 **CLI0.1.21',1)
        note='\n当前本地 **CLI0.1.22 / alpha.4-local.20 / r23 kit**：独立/内嵌浮点文字、逐词/打字机与纯文本SRT已安装；[使用与实际案例](FLOAT_TEXT.md)。CPU文字，复杂Bidi/4K文字/GPU文字及全部38原关闭条件保持开放。\n'
        if note not in text:
            at=text.index('\n\n')+2;text=text[:at]+note+'\n'+text[at:]
        if name.startswith('GOAL'):
            text=text.replace(
                'local.19-final-r1 / CLI0.1.21，1Skill/17模块、70文件、r22 kit；[211文件固定安装](../validation/evidence/float-transition-20261026-r1/installation-final-r1/verification.json)',
                'local.20-final-r2 / CLI0.1.22，1Skill/17模块、71文件、r23 kit；[213文件固定安装](../validation/evidence/float-text-20261026-r1/installation-final-r2/verification.json)')
            text=text.replace('[当前全部字段](float-transition-capabilities-cli-0.1.21.json)', '[当前全部字段](float-text-capabilities-cli-0.1.22.json)')
            text=text.replace('Float32尚有字幕/生成器等未移植操作', 'Float32已补独立/内嵌文字及纯文本SRT；富ASS和非文字生成器等仍未移植')
            text=text.replace('文本、样式、简繁 Noto、双语/逐字高亮/打字机/HTML 动效 |', '文本、样式、简繁 Noto、双语/逐字高亮/打字机/HTML 动效；CLI0.1.22新增显式Float32独立/内嵌文字、原时钟、联合高亮与纯文本SRT |')
            old=rows(before('docs/product/'+name),'G');new=rows(text,'G')
            assert len(new)==38 and all(new[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        write(path,text)
    path=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=path.read_text('utf-8-sig')
    for a,b in [('local.19','local.20'),('0.1.21','0.1.22'),('final-r1/installed','final-r2/installed'),('candidate-r1/bundle','candidate-r2/bundle'),('r22','r23'),
                ('baf48f03b2434f5e50930d2ae08a123309c9ea8bf0e94a30bb9280c65f533239',install['archive_sha256']),
                ('8454b2c879c2bad8c944eb6e8dd2ffb2083beb93bc72f8e6f91f1a9076ec0c60',install['manifest_sha256'].removeprefix('sha256:'))]:text=text.replace(a,b)
    text=text.replace('209产品Python文件，69个Skill文件、17模块、r21独立kit。原生OpenCL','213产品Python文件，71个Skill文件、17模块、r23独立kit。原生OpenCL')
    note='\n当前新增[线性浮点文字、打字机/逐词高亮、SRT及原作者时钟](FLOAT_TEXT.md)。CPU字形合成与现有GPU投影、语音/翻译分别选择；字形覆盖率8位、颜色Float32。\n'
    if note not in text:text+=note
    write(path,text)
    path=ROOT/'docs/product/CASES.md';text=path.read_text('utf-8-sig')
    if 'id="c30-float-text"' not in text:text+='''
<a id="c30-float-text"></a>

## C30 浮点文字、打字机、逐词高亮与中文SRT / Native Float32 text

真实注册Skill调用CLI0.1.22，6秒/72帧/12fps。中文Noto字体、整段前缀打字机与逐词选色、字层旋转、内嵌标题、根SRT、父级倒放及五组真实源句柄/关联音轨同时编辑。原生覆盖率256码值重建准确；颜色与合成为线性Float32。

[使用流程](FLOAT_TEXT.md) · [完整实测](../validation/Float32文字字幕实测_2026-10-26.md) · [原视频](../assets/float-text-20261026-r3/original.native.mkv) · [原音轨](../assets/float-text-20261026-r3/original.audio.wav) · [MP4](../assets/float-text-20261026-r3/native-text.mp4) · [可编辑包](../assets/float-text-20261026-r3/editable-native-text.aevpkg.zip)

![Actual registered Skill output / silent GIF](../assets/float-text-20261026-r3/native-text.gif)

自制几何视频、字幕与合成验证音调为CC0；Noto Sans SC为OFL-1.1，原字体与许可保留。GIF无声，MP4的验证音调不代表配音/音乐质量。取消恢复及队列完整帧/时钟/PCM相同，逐采样对照原源。CPU文字，未做连续播放或人工听审；自然视听、4K字层、GPU文字、HDR及完整目标保持开放。
'''
    write(path,text)
    counts='\n'.join(f"| {g} | {r['tests']} passed / 0 skip | [receipt](evidence/float-text-20261026-r1/{g}-installed-final-r1/verification.json) |" for g,r in tests.items())
    timings={r['name']:round(r['seconds'],3) for r in case['calls'] if r['name'] in ('render','resume','queue-run')}
    write(ROOT/REPORT,f'''# Float32文字字幕实际核验（2026-10-26）

CLI0.1.22 / local.20-final-r2；213产品Python文件与ZIP安装版逐字节一致；71个Skill文件、一个入口/17模块。ZIP {install['archive_bytes']} bytes，SHA-256 `{install['archive_sha256']}`。[安装原记录](evidence/float-text-20261026-r1/installation-final-r2/verification.json)。

| 独立组 | 结果 | 原始证据 |
|---|---|---|
{counts}

分组、历史测试和真实案例不合并计数。文字19项覆盖四组件独立原生8bit覆盖率+Python Float64 source-over oracle、sRGB EOTF、alpha只施加一次、未覆盖媒体逐位保留、原生取消清理、缓存边界、字体变化、SRT半开范围、原展示时钟/父倒放、逐词和打字机。全部256字形码值重建误差0；颜色/alpha绝对误差≤3e-7；未覆盖媒体保留超过256灰阶。

[实际注册Skill](evidence/float-text-20261026-r1/case-r3/verification.json)：6秒/72帧/12fps，四个文字计划，中文SRT、联合打字机/逐词、旋转/内嵌字、五组真实句柄/关联音轨、子画布及父倒放。288000双声道采样与原源/作者时钟独立公式误差 `{case['max_pcm_error']:.12g}`。编码器启动后取消、原操作恢复及显式MKV/PCM队列的全部帧/时钟/PCM一致；quality通过，作者数据和权利不变。[C30原输入、实际MP4/GIF和可编辑包](../product/CASES.md#c30-float-text)。

开发阶段保留并修正：opaque黑底不能依赖color滤镜协商alpha，现显式Float32零alpha；原生RGB8→Float32白值偏低，不能假设code/255，现用256码值离散重建并验证，不归一化媒体色彩；逐词选区曾在浮点格式上使用8位阈值，现锁定选区的8位计算边界。早期个人探针在被忽略的workspace中保留，不当作安装版通过证据。

首轮[float-final-r1](evidence/float-text-20261026-r1/float-final-r1/verification.json)暴露未知生成器进入文字宿主的错误码变化；恢复原拒绝行为后重建final-r2。r1构建、原失败及源码测试均保留；最终组对同一冻结的213文件重做，不放宽像素或拒绝标准。[case-r1](evidence/float-text-20261026-r1/case-r1/verification.json)的外部URL权利引用被本地策略拒绝；[case-r2](evidence/float-text-20261026-r1/case-r2/verification.json)缺少字体/SRT的资产probe。修正案例登记及附带本地字体许可后，在全新r3工程完成；没有改产品策略或放宽验证。

[工程包实际导入](evidence/float-text-20261026-r1/package-r1/verification.json)另外通过真实统一Skill执行导入/validate/三帧预览，与原工程对应帧解码RGBA64完全相同，字体OFL许可保留。该验证仍是同一主机，未声称干净机器或跨平台通过。

真实案例非独占耗时（秒）：`{json.dumps(timings)}`；当时还有并行回归，单帧预览约49–68秒，不能作独占benchmark或实时能力证明。当前每个动画快照启动原生栅格进程，是继续优化的性能边界。

CPU文字；字形覆盖率8bit、颜色/合成Float32。64MiB表面LRU与20张栅格工作区准入为分配估算，不是峰值RSS。默认768MiB预算在4K原生文字启动前拒绝；没有1080p性能、GPU字层、富ASS、复杂Bidi、HDR、自然视听或完整剪映等价验收。静帧观察另记；无人类听审或连续播放。全部38原关闭条件保持。
''')
    kitdesc=f"{kit['files']}files/{kit['bytes']}bytes/SHA-256 `{kit['sha256']}`" if kit else '摘要见r23版本化元数据'
    write(ROOT/'docs/releases/CLI_0.1.22_LOCAL.md',f'''# CLI0.1.22 本地交付 / Local delivery

2026-10-26，agent editor kit / `v0.1.0-alpha.4-local.20` / final-r2。原生Windows x64/CPython3.13，213产品Python文件、71 Skill文件、单入口17模块。新增独立/内嵌Float32文字、逐词/打字机联动及纯文本SRT。[完整使用流程与组合限制](../product/FLOAT_TEXT.md)。

| 内容 | E:/dev/sandbox/AI广告剪辑/下的路径 | SHA-256 |
|---|---|---|
| Application ZIP / {install['archive_bytes']}bytes | `local/agent-ffmpeg/v0.1.0-alpha.4-local.20/candidate-r2/bundle.zip` | `{install['archive_sha256']}` |
| Manifest | ZIP内`manifest.json` | `{install['manifest_sha256'].removeprefix('sha256:')}` |
| Installed | `local/agent-ffmpeg/v0.1.0-alpha.4-local.20/final-r2/installed/` | [213-file proof](../validation/evidence/float-text-20261026-r1/installation-final-r2/verification.json) |
| r23 unified Skill / {kitdesc} | [r23 ZIP](../skills/agent-editor-kit-community-unified-skill-r23.zip) | [metadata](../skills/community-unified-skill-package-0.1.22-r23.json) |

[离线安装/注册](../product/COMMUNITY_LOCAL_DELIVERY.md) · [实际75项能力](../product/float-text-capabilities-cli-0.1.22.json) · [证据](../validation/Float32文字字幕实测_2026-10-26.md) · [17模块](../product/SKILLS.md)。保持四个已有GPU/CPU模型包及其固定摘要，不下载模型、不创建Docker/WSL/虚拟环境、不调用模型服务器。文字在CPU执行，GPU投影/配音/翻译分别选择。

本地ZIP及安装保留旧版本；公开alpha.3/CLI0.1.2的标签/资产未覆盖。复杂Bidi、富ASS、4K/GPU文字、自然视听/HDR/长片和完整剪映目标继续进行。
''')
    path=ROOT/'docs/README.md';text=path.read_text('utf-8-sig')
    text=text.replace('Current local / 当前本地 / 目前本地：**CLI0.1.21','Historical local / 此前本地 / 先前本機：**CLI0.1.21')
    note='\nCurrent local / 当前本地 / 目前本地：**CLI0.1.22 / local.20 / r23 kit** · [Float32 text](product/FLOAT_TEXT.md) · [Local bundle](releases/CLI_0.1.22_LOCAL.md) · [C30](product/CASES.md#c30-float-text).\n'
    if note not in text:
        at=text.index('\n\n')+2;text=text[:at]+note+'\n'+text[at:]
    write(path,text)
    print(json.dumps(dict(status='documented',functions=56,services=20,readme_rows=162,historical_rows_preserved=154,closure_conditions_preserved=38)))

if __name__=='__main__':main()
