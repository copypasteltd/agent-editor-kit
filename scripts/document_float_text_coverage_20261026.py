"""Document actual installed coverage/4K/performance results without shrinking goals."""
import argparse, json, re, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-text-coverage-20261026-r1'
BASELINE='c896f5271d6e129e418b08c7c245fc0ce2ece435'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def load(p):return json.loads(Path(p).read_bytes())
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d{2,3})\s*\|.*$',s,re.M)}
def before(name):return subprocess.check_output([GIT,'show',BASELINE+':'+name],cwd=ROOT).decode('utf-8-sig')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--audit-run',default='r1');ap.add_argument('--final-kit',action='store_true');a=ap.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*',a.audit_run)
    install=load(BASE/'installation-final-r2/verification.json');case=load(BASE/'case-r1/verification.json')
    four=load(BASE/'4k-r2/verification.json');bench=load(BASE/'benchmark-r1/verification.json')
    tests={g:load(BASE/(g+'-installed-final-r1/verification.json')) for g in ('text','float','audio','render','legacy','text-legacy')}
    assert all(r['status']=='passed' and r['skipped']==0 for r in tests.values())
    assert case['status']==four['status']==bench['status']=='passed' and install['source_and_installed_equal']
    median=bench['median_seconds'];speed=bench['median_speedup'];kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.23-r24.json') if a.final_kit else None
    four_seconds=next(c['seconds'] for c in four['calls'] if c['name']=='render')
    summaries=[
        '字形栅格已改为原生字节覆盖率，颜色按块浮点合成；相同前缀与段落几何复用缓存，保留原作者时钟。实际统一Skill完成4K/8帧标题动画和含转场/关联音轨的6秒/72帧案例。CPU文字，覆盖率8bit、颜色Float32。',
        '字形栅格已改為原生位元組覆蓋率，顏色採分塊浮點合成；相同前綴與段落幾何重用快取，保留原作者時鐘。實際統一Skill完成4K／8影格標題動畫及含轉場／關聯音軌的6秒／72影格案例。CPU文字，覆蓋率8bit、顏色Float32。',
        'Native byte glyph coverage now feeds tiled linear component composition. Equal prefixes and paragraph geometry reuse masks without quantizing author time. The registered Skill renders a 4K/8-frame title animation and a 6s/72-frame transition/linked-audio case. CPU text,8bit coverage,Float32 colors.'
    ]
    summaries[0]+=f' 该4K案例的CPU渲染调用耗时{four_seconds:.3f}秒，速度仍需改善。'
    summaries[1]+=f' 該4K案例的CPU算繪呼叫耗時{four_seconds:.3f}秒，速度仍須改善。'
    summaries[2]+=f' The actual 4K CPU render call took {four_seconds:.3f}s; throughput still needs improvement.'
    limits=[
        '文字由CPU合成，字形覆盖率为8bit；工作区准入估算、实时速度、长片和完整目标分别验收。',
        '文字使用CPU合成，字形覆蓋率為8bit；工作區准入估算、即時速度、長片及完整目標分別驗收。',
        'CPU text;8bit glyph coverage;admission estimate is not peak RSS or realtime/long-form acceptance. Full target conditions remain open.'
    ]
    feature=[
        '| F56 | 线性浮点文字与字幕 | 独立/内嵌/SRT、联合逐词/打字机 → 原生字节覆盖率、可复用字形、分块线性合成、原作者时钟、4K标题和实际交付。 | `timeline compose; preview; render; queue` | 明确本地字体；CPU；覆盖率8bit/颜色Float32；工作区准入非峰值RSS；富ASS/Bidi/GPU文字/自然质量未闭。 |',
        '| F56 | 線性浮點文字與字幕 | 獨立／內嵌／SRT、聯合逐詞／打字機 → 原生位元組覆蓋率、可重用字形、分塊線性合成、原作者時鐘、4K標題及實際交付。 | `timeline compose; preview; render; queue` | 明確本機字型；CPU；覆蓋率8bit／顏色Float32；工作區准入非峰值RSS；富ASS／Bidi／GPU文字／自然品質未閉。 |',
        '| F56 | Linear Float32 text and captions | Independent/inline/SRT,joint word/typewriter → native byte coverage,reusable glyphs,tiled linear composition,original clocks,4K titles and actual delivery. | `timeline compose; preview; render; queue` | Explicit local font;CPU;8bit coverage/Float32 colors;admission is not peak RSS;rich ASS/Bidi/GPU text/natural quality open. |'
    ]
    targets=['installation-final-r2/verification.json','text-installed-final-r1/verification.json',
        'text-installed-final-r1/text_receipts.json','render-installed-final-r1/verification.json',
        'case-r1/verification.json','4k-r2/verification.json','benchmark-r1/verification.json',
        'final-delivery-'+a.audit_run+'/verification.json']
    details=[
        ['CLI0.1.23/local.21-final-r2，214产品文件与离线安装一致；71 Skill文件、1入口/17模块',
         '26文字专项0skip：4K四组件独立覆盖率/Float64公式误差≤3e-7，256原生码值准确，小预算前置拒绝',
         '相同字素前缀/普通活动段落共享不可写字形；原时钟不取整；32MiB工作区缩小缓存后小画幅可用；数值AST/取消验证',
         f"分别98浮点/64音频源句柄嵌套/44预览渲染/191CLI队列Schema/72默认文字，全部0skip，不合并计数",
         f"真实注册Skill6秒/72帧：字幕/逐词/打字机/旋转/父倒放/真实句柄，288000双声道采样误差{case['max_pcm_error']:.12g}；恢复/队列逐帧与PCM相同",
         f'真实注册Skill3840×2160/4fps/2秒/8帧、三字层、四组件、淡入和逐词打字机；完整解码/质检/可编辑包/MP4/GIF；CPU渲染调用耗时{four_seconds:.3f}秒，非实时',
         f"同工程320×180、6次交错成片，4逻辑CPU亲和，中位数{median['old']:.3f}→{median['new']:.3f}秒（{speed:.3f}×）；全部72帧时钟/PCM相同，解码10bit码差≤1；非独占主机",
         '三语56功能/20服务/17模块/75能力，C31/C32、r24独立kit；保留162历史行与38原关闭条件'],
        ['CLI0.1.23/local.21-final-r2，214產品檔案與離線安裝相同；71 Skill檔案、1入口／17模組',
         '26項文字專項零略過：4K四元件獨立覆蓋率／Float64公式誤差≤3e-7，256原生碼值正確，小預算前置拒絕',
         '相同字素前綴／一般活動段落共用不可寫字形；原時鐘不取整；32MiB工作區縮小快取後小畫幅可用；數值AST／取消核驗',
         '分別98浮點／64音訊句柄巢狀／44預覽算繪／191CLI佇列Schema／72預設文字，全部零略過，未合併計數',
         f"實際註冊Skill6秒／72影格：字幕／逐詞／打字機／旋轉／父倒放／真實句柄，288000雙聲道取樣誤差{case['max_pcm_error']:.12g}；恢復／佇列全影格與PCM相同",
         f'實際註冊Skill3840×2160／4fps／2秒／8影格、三字層、四元件、淡入和逐詞打字機；完整解碼／質檢／可編輯包／MP4／GIF；CPU算繪呼叫耗時{four_seconds:.3f}秒，非即時',
         f"同專案320×180、6次交錯成片，4邏輯CPU親和，中位數{median['old']:.3f}→{median['new']:.3f}秒（{speed:.3f}×）；全部72影格時鐘／PCM相同，解碼10bit碼差≤1；非獨占主機",
         '三語56功能／20服務／17模組／75能力，C31／C32、r24獨立kit；保留162歷史列及38原關閉條件'],
        ['CLI0.1.23/local.21-final-r2;214 source files byte-match offline installation;71 Skill files,one entry/17 modules',
         '26 text tests,zero skips:4K four-component independent coverage/Float64 oracle error<=3e-7,all256 native codes exact,small-budget preflight rejection',
         'Equal prefixes and normal/active paragraphs share immutable glyph masks;exact author clocks;32MiB workspace adapts cache ceilings for small canvases;numeric AST/cancel verified',
         'Separate98 float/64 audio-handles-nesting/44 preview-render/191 CLI-queue-schema/72 default-text;zero skips,no combined count',
         f"Actual registered Skill6s/72frames:captions/word/typewriter/rotation/reversed parent/real handles,288000stereo samples error={case['max_pcm_error']:.12g};resume/queue frames and PCM equal",
         f'Actual registered Skill3840x2160/4fps/2s/8frames,three text layers,four components,fade and joint word/typewriter;full decode/quality/editable package/MP4/GIF;CPU render call {four_seconds:.3f}s,not realtime',
         f"Six interleaved 320x180 full renders,4logical-CPU affinity:median{median['old']:.3f}->{median['new']:.3f}s ({speed:.3f}x);all72 frame clocks/PCM equal,decoded10bit code error<=1;nonexclusive host",
         'Three languages:56functions/20services/17modules/75declarations,C31/C32,r24 isolated kit;162historical rows and38original closure conditions retained']]
    for i,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        path=ROOT/name;text=path.read_text('utf-8-sig')
        text=text.replace('<!-- float-text-current -->','<!-- float-text-history -->').replace('<!-- /float-text-current -->','<!-- /float-text-history -->')
        text=text.replace('**CLI0.1.22 / alpha.4-local.20 / r23 kit','**Historical / 历史 / 歷史：CLI0.1.22 / alpha.4-local.20 / r23 kit')
        text=text.replace('Plain SRT/explicit font;CPU text;4K native text currently rejected by workspace admission.',
                          'Historical CLI0.1.22:plain SRT/explicit font;CPU text;4K text was rejected by its workspace admission.')
        block='<!-- float-text-coverage-current -->\n\n**CLI0.1.23 / alpha.4-local.21 / r24 kit · 1 Skill / 17 modules.**\n\n'+summaries[i]+'\n\n'
        block+='[Workflow](docs/product/FLOAT_TEXT_COVERAGE.md) · [C31/C32](docs/product/CASES.md#c31-float-text-coverage) · [Local install](docs/releases/CLI_0.1.23_LOCAL.md) · [Evidence](docs/validation/文字覆盖率分块与复用实测_2026-10-26.md)\n\n'
        block+='![Actual registered Skill 4K title animation / silent GIF](docs/assets/float-text-coverage-20261026-4k-r2/4k-native-text.gif)\n\n'
        block+=limits[i]+'\n\n<!-- /float-text-coverage-current -->\n\n'
        if '<!-- float-text-coverage-current -->' in text:
            text=re.sub(r'<!-- float-text-coverage-current -->.*?<!-- /float-text-coverage-current -->\n\n',lambda _:block,text,count=1,flags=re.S)
        else:text=text.replace('<!-- float-text-history -->',block+'<!-- float-text-history -->',1)
        lines=[]
        for line in text.splitlines():
            if not re.match(r'^\| R\d+\s*\|',line):
                line=line.replace('local.20/final-r2/installed','local.21/final-r2/installed')
                if 'local.21/final-r2/installed' in line or 'GOAL_GAPS_20261025.md)' in line:line=line.replace('CLI 0.1.22','CLI 0.1.23')
                if line.startswith('**') and 'unified-skill-r23.zip' in line:line=line.replace('unified-skill-r23.zip','unified-skill-r24.zip').replace('r23 Skill kit','r24 Skill kit')
            lines.append(line)
        text='\n'.join(lines)+'\n'
        text=re.sub(r'^\| F56\s*\|.*$',lambda _:feature[i],text,flags=re.M)
        for n,(detail,target) in enumerate(zip(details[i],targets),163):
            row=f'| R{n} | 2026-10-26 Native coverage/4K | {detail} | [Evidence](docs/validation/evidence/float-text-coverage-20261026-r1/{target}) |'
            if f'R{n}' in rows(text,'R'):text=re.sub(r'^\| R'+str(n)+r'\s*\|.*$',lambda _:row,text,flags=re.M)
            else:
                last=re.search(r'^\| R'+str(n-1)+r'\s*\|.*$',text,re.M);assert last
                text=text[:last.end()]+'\n'+row+text[last.end():]
        old=rows(before(name),'R');assert len(old)==162 and all(rows(text,'R')[k]==v for k,v in old.items())
        write(path,text)
    for prefix in ('docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
        for suffix in ('','.zh-TW','.en'):
            path=ROOT/(prefix+suffix+'.md');text=path.read_text('utf-8-sig')
            text=text.replace('0.1.22 / alpha.4-local.20 / r23 kit','0.1.23 / alpha.4-local.21 / r24 kit').replace('float-text-capabilities-cli-0.1.22.json','float-text-coverage-capabilities-cli-0.1.23.json')
            link='../product/FLOAT_TEXT_COVERAGE.md' if prefix.startswith('docs/skills') else 'FLOAT_TEXT_COVERAGE.md'
            note='\nCLI0.1.23:[4K text and reusable native byte coverage]('+link+'). CPU tiled linear component composition,exact original clocks,bounded adaptive caches. GPU text,natural quality,HDR,realtime and full original conditions remain open.\n'
            if note not in text:text+=note
            write(path,text)
    for name in ('GOAL_GAPS_20261025.md','IMPLEMENTATION_PLAN_20261025.md'):
        path=ROOT/'docs/product'/name;text=path.read_text('utf-8-sig').replace('当前本地 **CLI0.1.22','此前本地 **CLI0.1.22',1)
        note='\n当前本地 **CLI0.1.23 / alpha.4-local.21 / r24 kit**：[4K文字/原生覆盖率复用/分块合成](FLOAT_TEXT_COVERAGE.md)已交付，CPU；实际4K成片与同源交错性能证据留存。全部38原关闭条件保持。\n'
        if note not in text:
            at=text.index('\n\n')+2;text=text[:at]+note+'\n'+text[at:]
        if name.startswith('GOAL'):
            text=text.replace('local.20-final-r2 / CLI0.1.22，1Skill/17模块、71文件、r23 kit；[213文件固定安装](../validation/evidence/float-text-20261026-r1/installation-final-r2/verification.json)',
                'local.21-final-r2 / CLI0.1.23，1Skill/17模块、71文件、r24 kit；[214文件固定安装](../validation/evidence/float-text-coverage-20261026-r1/installation-final-r2/verification.json)')
            text=text.replace('[当前全部字段](float-text-capabilities-cli-0.1.22.json)','[当前全部字段](float-text-coverage-capabilities-cli-0.1.23.json)')
            text=text.replace('CLI0.1.22新增显式Float32独立/内嵌文字、原时钟、联合高亮与纯文本SRT','CLI0.1.23增加4K字层、原生覆盖率复用及分块合成；显式Float32独立/内嵌文字、原时钟、联合高亮与纯文本SRT')
            def current_release(match):
                cells=match[0].split('|')
                cells[3]=' 公开alpha.3/CLI0.1.2保持；本地local.21-final-r2/CLI0.1.23/r24已安装注册核验；覆盖率复用、4K字层与交错性能实测留证 '
                return '|'.join(cells)
            text=re.sub(r'^\| G38\s*\|.*$',current_release,text,flags=re.M)
            def current_performance(match):
                cells=match[0].split('|')
                marker='；CLI0.1.23另有CPU文字4K/8帧实际离线交付'
                if marker not in cells[3]:cells[3]=cells[3].rstrip()+marker+' '
                cells[4]=cells[4].replace('，4K验证为单帧像素/小目标缩小','，GPU4K验证为单帧像素/小目标缩小')
                return '|'.join(cells)
            text=re.sub(r'^\| G32\s*\|.*$',current_performance,text,flags=re.M)
            old=rows(before('docs/product/'+name),'G');new=rows(text,'G')
            assert len(new)==38 and all(new[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        write(path,text)
    path=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=path.read_text('utf-8-sig')
    old_install=load(ROOT/'docs/validation/evidence/float-text-20261026-r1/installation-final-r2/verification.json')
    for x,y in [('local.20','local.21'),('0.1.22','0.1.23'),('r23','r24'),(old_install['archive_sha256'],install['archive_sha256']),
                (old_install['manifest_sha256'].removeprefix('sha256:'),install['manifest_sha256'].removeprefix('sha256:')),
                ('213产品Python文件','214产品Python文件')]:text=text.replace(x,y)
    text=text.replace('float-text-capabilities-cli-0.1.23.json','float-text-coverage-capabilities-cli-0.1.23.json')
    note='\n当前[4K文字、原生字节覆盖率复用与分块合成](FLOAT_TEXT_COVERAGE.md)保留作者时钟及精度。GPU文字仍开放；准入估算非峰值RSS或实时承诺。\n'
    if note not in text:text+=note
    write(path,text)
    path=ROOT/'docs/product/CASES.md';text=path.read_text('utf-8-sig')
    for case_id,title,folder,description in [('c31-float-text-coverage','C31 Native coverage / 原生字形覆盖率复用','float-text-coverage-20261026-r1',
        '6秒/72帧/12fps；原生字节覆盖率、联合打字机/逐词、中文SRT、旋转/倒放及五组真实句柄/关联音轨。取消恢复和队列的全部帧/时钟/PCM相同，字体许可随可编辑包保留。'),
        ('c32-4k-text','C32 4K titles / 实际4K字层','float-text-coverage-20261026-4k-r2',
        f'3840×2160/4fps/2秒/8帧；三个可编辑文字层，四组件颜色、淡入、逐词与完整前缀打字机。实际安装版通过统一Skill执行预览/编码/完整解码/质检/工程包；CPU渲染调用耗时{four_seconds:.3f}秒，非实时。自制文字与背景，Noto字型按OFL保留。')]:
        if f'id="{case_id}"' not in text:
            fourk=case_id.startswith('c32');movie='4k-native-text' if fourk else 'native-text';package='editable-4k-text' if fourk else 'editable-native-text'
            text+=f'\n<a id="{case_id}"></a>\n\n## {title}\n\n{description}\n\n[Workflow](FLOAT_TEXT_COVERAGE.md) · [Original](../assets/{folder}/original.png) · [MP4](../assets/{folder}/{movie}.mp4) · [Editable package](../assets/{folder}/{package}.aevpkg.zip)\n\n![Actual registered Skill / silent GIF](../assets/{folder}/{movie}.gif)\n\nCPU文字；8bit覆盖率/Float32颜色，分块Float64算术。不代表自然视听、GPU文字、HDR、长片、实时或完整目标验收；无连续播放或人工听审。\n'
    write(path,text)
    counts='\n'.join(f"| {g} | {r['tests']} passed / 0 skip | [receipt](evidence/float-text-coverage-20261026-r1/{g}-installed-final-r1/verification.json) |" for g,r in tests.items())
    write(ROOT/'docs/validation/文字覆盖率分块与复用实测_2026-10-26.md',f'''# 原生字形覆盖率、4K与复用实测（2026-10-26）

CLI0.1.23/local.21-final-r2，214产品Python文件与ZIP安装版逐字节一致。ZIP {install['archive_bytes']}bytes，SHA-256 `{install['archive_sha256']}`。[安装原记录](evidence/float-text-coverage-20261026-r1/installation-final-r2/verification.json)。单一Skill/17模块/71文件；没有模型推理或虚拟化。

| 独立组 | 结果 | 证据 |
|---|---|---|
{counts}

分组和历史测试不合并计数。26项文字核验包含真实4K四组件、独立RGBA8覆盖率/Float64公式、256码值准确、颜色/alpha误差≤3e-7，原媒体位值保留、SRT/原作者/倒放/定格/窗口、普通活动二值选择、整前缀打字机、缓存不变/不可写、预编译预算、数值AST与原生取消。小32MiB工作区按8MiB缓存上限继续支持小画幅，4K在不足预算前置拒绝。

[C31实际统一Skill](evidence/float-text-coverage-20261026-r1/case-r1/verification.json)完成6秒/72帧工程及预览、编码器启动后取消/恢复、显式MKV队列、质检和可编辑包。全部帧/时钟/PCM一致，288000双声道采样独立公式误差 `{case['max_pcm_error']:.12g}`；作者数据与权利保持。[工程包实际导入](evidence/float-text-coverage-20261026-r1/package-r1/verification.json)单列。

[C32实际4K统一Skill](evidence/float-text-coverage-20261026-r1/4k-r2/verification.json)：3840×2160、2秒、4fps、8帧，三字层、淡入和联合逐词打字机。完整解码/质检/包导出；实际原生覆盖率{four['native_coverage_rasters']}张、复用命中{four['coverage_cache_hits']}次。CPU渲染调用实际耗时{four_seconds:.3f}秒；这是完成4K功能交付的记录，尚未达到实时速度。主机非独占，不能直接把它与后述4逻辑CPU亲和的320×180交错性能实验混比。原素材、MP4、GIF、预览和工程包见[完整案例](../product/CASES.md#c32-4k-text)。默认工作区准入约705.5MiB，是分配估算，不是峰值RSS硬上限。

[同源交错性能实测](evidence/float-text-coverage-20261026-r1/benchmark-r1/verification.json)使用旧CLI0.1.22与新0.1.23安装版、同一作者数据/素材/编码配置，每次全新工程及空工程缓存，4逻辑CPU亲和，按old/new/new/old/old/new交错各3轮。全部6次为320×180、6秒/72帧成片；中位数 {median['old']:.3f}→{median['new']:.3f} 秒，{speed:.3f}倍。全部帧时钟及完整PCM相同，解码YUV444 10bit最大差≤1码；不声称逐位像素相同。主机非独占、OS页缓存不受控，未测峰值RSS，没有把GPU、缩小输入或单帧缓存当成完整成片加速。

首轮24项和次轮25项源码测试及r1安装包分别保留；之后补齐小工作区缓存自适应，再构建final-r2，26项与全部最终安装组针对同一214文件核验。[4K首轮案例](evidence/float-text-coverage-20261026-r1/4k-r1/verification.json)因案例脚本向工程目录外输出而被正确拒绝；仅修正案例到工程内编码，再复制成功成片，r2完成真实交付。未放宽产品输出边界。旧版4K拒绝记录和原误差/失败均保留，不追改历史关闭条件。

CPU文字；原生覆盖率8bit，颜色/元件边界Float32、分块算术Float64。富ASS、复杂Bidi、GPU文字、自然视听、HDR、长片和完整剪映等价仍开放。静帧观察、连续播放与人工听审分开记录。全部38原关闭条件保持。
''')
    kitdesc=f"{kit['files']}files/{kit['bytes']}bytes/SHA-256 `{kit['sha256']}`" if kit else 'r24版本化摘要待封装后填入'
    write(ROOT/'docs/releases/CLI_0.1.23_LOCAL.md',f'''# CLI0.1.23 本地交付 / Local delivery

agent editor kit / `v0.1.0-alpha.4-local.21` / final-r2；214产品Python文件、71 Skill文件、1入口17模块。[4K文字/覆盖率复用/分块合成使用](../product/FLOAT_TEXT_COVERAGE.md)。

| 内容 | E:/dev/sandbox/AI广告剪辑/下路径 | SHA-256 |
|---|---|---|
| Application ZIP / {install['archive_bytes']}bytes | `local/agent-ffmpeg/v0.1.0-alpha.4-local.21/candidate-r2/bundle.zip` | `{install['archive_sha256']}` |
| Manifest | ZIP内`manifest.json` | `{install['manifest_sha256'].removeprefix('sha256:')}` |
| Installed | `local/agent-ffmpeg/v0.1.0-alpha.4-local.21/final-r2/installed/` | [214-file proof](../validation/evidence/float-text-coverage-20261026-r1/installation-final-r2/verification.json) |
| r24 unified Skill / {kitdesc} | [r24 ZIP](../skills/agent-editor-kit-community-unified-skill-r24.zip) | [metadata](../skills/community-unified-skill-package-0.1.23-r24.json) |

[离线安装/注册](../product/COMMUNITY_LOCAL_DELIVERY.md) · [实际75能力](../product/float-text-coverage-capabilities-cli-0.1.23.json) · [核验](../validation/文字覆盖率分块与复用实测_2026-10-26.md) · [17模块](../product/SKILLS.md)。四个原CPU/GPU模型包和配置保留；没有新模型推理。文字CPU，GPU投影/配音/翻译分别选择。

新包和旧包分别保留；公开alpha.3/CLI0.1.2标签/附件未覆盖。原生Windows，不使用Docker/WSL/虚拟环境。GPU字层、自然视听、HDR、实时/长片及完整目标继续进行。
''')
    path=ROOT/'docs/README.md';text=path.read_text('utf-8-sig')
    text=text.replace('Current local / 当前本地 / 目前本地：**CLI0.1.22',
                      'Historical / 历史 / 歷史：**CLI0.1.22')
    note='\nCurrent local / 当前本地 / 目前本地：**CLI0.1.23 / local.21 / r24 kit** · [4K text/coverage](product/FLOAT_TEXT_COVERAGE.md) · [Local bundle](releases/CLI_0.1.23_LOCAL.md) · [C31/C32](product/CASES.md#c31-float-text-coverage).\n'
    if note not in text:
        at=text.index('\n\n')+2;text=text[:at]+note+'\n'+text[at:]
    write(path,text)
    print(json.dumps({'status':'documented','functions':56,'services':20,'readme_rows':170,'history_preserved':162,'closures_preserved':38}))


if __name__=='__main__':main()
