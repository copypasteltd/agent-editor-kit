"""Document the actual projection delivery, retaining all historical evidence."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/projection-scanline-20261026-r1'
GUIDE='docs/product/PROJECTION_RENDERING.md'
REPORT='docs/validation/裁切与序列投影实测_2026-10-26.md'


def load(path):return json.loads(path.read_bytes())
def read(path):return path.read_text('utf-8-sig')
def write(path,text):path.write_text(text,encoding='utf8',newline='\n')


def main():
    bench=load(BASE/'benchmark-r3/verification.json')
    assert bench['status']=='passed' and bench['frames_equal_all_six'] and bench['audio_pcm_equal_all_six']
    for phase in ('skill-r3','preview-r4','kit-r2','example-import-r1'):assert load(BASE/phase/'verification.json')['status']=='passed'
    scopes=[('final-development-r1',13),('projection-final-r1',13),
            ('sequence-final-r1',63),('clock-final-r1',45),('alpha-final-r1',17),
            ('affine-final-r1',8),('cli-final-r1',122)]
    for run,count in scopes:
        proof=load(BASE/'tests'/run/'verification.json')
        assert proof['status']=='passed' and proof['result']==dict(methods=count,skipped=0,failures=0,errors=0,success=True)
    old,new=bench['medians_seconds']['old'],bench['medians_seconds']['new'];ratio=bench['median_ratio']
    timings='\n'.join(f'| {n+1} | {bench["timings_seconds"]["old"][n]:.6f} | {bench["timings_seconds"]["new"][n]:.6f} |' for n in range(3))
    table='\n'.join('| '+run+' | '+str(count)+' / '+str(count)+'，0 skip | [证据](evidence/projection-scanline-20261026-r1/tests/'+run+'/verification.json) |' for run,count in scopes)
    report=f'''# 动态裁切与序列投影实测（2026-10-26）

本地 **CLI0.1.19 / alpha.4-local.17 / r20 kit**。208产品文件与发行ZIP安装版一致；唯一注册Skill含17模块、68文件，r20 kit94文件。[使用流程](../product/PROJECTION_RENDERING.md) · [实现前契约](../specs/裁切与序列投影参数复用契约_20261026.md)。

## 实际交错测量

旧安装0.1.17对新安装0.1.19，同一工程/素材/关键帧/采样器/编码设置。640×360自制图卡，480×270原生子序列，384×216/30fps/4秒成片；动态裁切、子序列反向时钟、arc_push关键帧与面积采样组合。libx264 CRF0/yuv444p、PCM float32、硬件编码关闭。仅测量进程及继承子进程限制4个逻辑CPU，未改变其他应用/模型任务；非独占主机基准。old1/new1/new2/old2/old3/new3交错执行，计时包含CLI/检查/渲染/编码，解码另计。

| 轮 | 旧安装秒 | 新安装秒 |
|---|---:|---:|
{timings}

中位数 **{old:.6f} → {new:.6f}秒，{ratio:.3f}×**。这是此组合工程的CPU结果，不是GPU加速比、单独采样器测速或一般4K吞吐保证。旧/新各三次，全部120帧RGBA摘要和完整4秒48kHz双声道float32 PCM相同。图卡音频为静音，不据此推断真实声音质量。作者工程除render正常追加的六条输出/日志及updated_at外全部相同，资产与Rights Ledger字节保持。[原始命令、计时、逐帧和哈希](evidence/projection-scanline-20261026-r1/benchmark-r3/verification.json)。

## 分范围测试

| 范围 | 方法通过数 | 证据 |
|---|---:|---|
{table}

各范围分别执行，不相加成完成率。首轮12项之后，增加同时动画全部裁切和变换通道的寄存器压力测试，再执行13项安装版专项；两份原记录保留。专项包括三种fit、两种采样、透明/不透明裁切、奇数/不同画幅、Bezier/hold、嵌套反向时钟、多切片、重复/倒退PTS、隐藏RGB、内部像素/有状态表达式旧路径、独立前向几何，以及非法依赖/寄存器拒绝。63项既有序列套件另含独立像素单元交叠积分、配额预拒、队列/恢复/导入导出；45项时钟、17项透明、8项仿射及122项CLI独立留证，没有重跑全部历史模型质量套件。

早期开发/安装12项及寄存器压力13项、0.1.18包与r18 kit保留为中间构建记录；最终0.1.19在面积积分中另复用6/7保存上下边界。最终13项及各范围重新运行，固定同208文件，包/源码/安装逐字节一致。冻结旧函数独立与Git基线2a78657b核对，没有用新实现当差分预期。

## 安装、Skill和实际媒体

[离线包与208文件](evidence/projection-scanline-20261026-r1/installation-final-r1/verification.json) · [真实注册Skill渲染](evidence/projection-scanline-20261026-r1/skill-r3/verification.json) · [独立kit](evidence/projection-scanline-20261026-r1/kit-r2/verification.json) · [MP4/GIF完整解码](evidence/projection-scanline-20261026-r1/preview-r4/verification.json)。实际Skill渲染同组合工程，120帧及PCM与旧安装相同。kit使用独有中文/空格目录及工程执行9次进程/6次JSON调用，不改真实发现目录。

另通过真实注册Skill把公开案例ZIP导入新的中文/空格目录，按使用页显式选择area和1024MiB栅格配额，再执行无损编码对照；[新导入工程全部120帧及PCM仍与旧安装相同](evidence/projection-scanline-20261026-r1/example-import-r1/verification.json)，输入ZIP摘要保持。此独立5进程实测不混入六次性能计时，未新增模型推理。

原图、可编辑案例、MP4/GIF和摘要见[使用页](../product/PROJECTION_RENDERING.md)。案例沿用原包ledger，记录仍为unverified；自制图卡MIT及字体OFL来源见SOURCE.txt，render/validate成功不表示commercial_ad权利门禁已通过。来源为自制FIELD NOTES，预览NVENC仅做编码、合成仍为CPU。完整解码通过，已抽帧目检；未做人类听审、连续播放或自然素材美学验收。

## 边界和完整目标

本轮补齐动态裁切和序列crop/fit/TRS参数复用，保留双线性和源轴矩形面积积分。不是旋转多边形积分或GPU合成；工作栅格配额不代表进程RSS。全部4K/长片、自然质量、其他geq模块及其余完整功能仍须实现和验收，G01–G38原关闭条件不变。

此前仿射测量辅助脚本和kit的真实失败继续保留在[历史实测](仿射扫描行复用实测_2026-10-25.md)，没有把历史未通过改成通过。本轮[benchmark-r1](evidence/projection-scanline-20261026-r1/benchmark-r1/verification.json)因编排脚本漏填末端关键帧interpolation而在compose时被拒绝，尚无性能测量；补齐linear字段后使用新的r2工程执行；r2保留[中间计时与主动中断](evidence/projection-scanline-20261026-r1/benchmark-r2/verification.json)，最终0.1.19使用全新r3工程重新执行六次，不混合中间构建数据。未改产品/验收门槛或覆盖失败。另一次[preview-r3](evidence/projection-scanline-20261026-r1/preview-r3/verification.json)用错CLI导出参数，被参数解析拒绝；保留原目录与失败响应，修正为 `--target-format package` 后另用preview-r4与assets-r2重新导出，r20 kit改用成功目录。r19原包和独立验证留作中间记录。公开既有标签/附件没有覆盖。
'''
    write(ROOT/REPORT,report)
    summaries=[f'动态裁切及嵌套crop/fit/TRS支持扫描行复用，双线性/面积采样保持精度；同组合工程三轮中位数{old:.2f}→{new:.2f}秒（{ratio:.2f}×），六次120帧及PCM相同。',
        f'動態裁切及巢狀crop/fit/TRS支援掃描行復用，雙線性/面積採樣保持精度；同組合專案三輪中位數{old:.2f}→{new:.2f}秒（{ratio:.2f}×），六次120影格及PCM相同。',
        f'Animated crop and nested crop/fit/TRS reuse scanline parameters with unchanged bilinear/area precision. Paired three-run medians {old:.2f}→{new:.2f}s ({ratio:.2f}×); all120 frames and PCM match across six renders.']
    checks=[
        [('固定安装','CLI0.1.19/local.17，208产品文件与固定ZIP安装版相同'),('裁切与寄存器压力','13项安装版专项通过；新增全部裁切/变换通道同时动画，旧12项记录保留'),('序列/透明/时钟回归','63项序列、45项时钟、17项透明、8项仿射及122项CLI分别通过，0skip'),('组合工程交错计时',f'动态crop/反向子序列/arc_push/area，旧新各3次中位数{old:.3f}→{new:.3f}秒；六次全120帧与PCM相同'),('实际注册Skill','真实入口渲染与validate通过；120帧/PCM与旧安装相同，68文件/17模块'),('实际案例与媒体','自制原图、可编辑工程包、MP4/GIF完整解码及抽帧目检；首轮编排字段拒绝保留；未做连续播放/听审'),('kit与完整文档','r20 kit独立登记/调用；三语README、C27、使用流程及证据同步，保留131历史行/38原关闭条件')],
        [('固定安裝','CLI0.1.19/local.17，208產品檔案與固定ZIP安裝版相同'),('裁切及暫存器壓力','13項安裝版專項通過；新增全部裁切/變換通道同時動畫，舊12項紀錄保留'),('序列/透明/時鐘迴歸','63項序列、45項時鐘、17項透明、8項仿射及122項CLI分別通過，0skip'),('組合專案交錯計時',f'動態crop/反向子序列/arc_push/area，舊新各3次中位數{old:.3f}→{new:.3f}秒；六次全120影格與PCM相同'),('實際註冊Skill','實際入口渲染及validate通過；120影格/PCM與舊安裝相同，68檔案/17模組'),('實際案例及媒體','自製原圖、可編輯專案包、MP4/GIF完整解碼及抽幀目檢；首輪編排欄位拒絕保留；未做連續播放/聽審'),('kit及完整文件','r20 kit獨立登記/調用；三語README、C27、使用流程及證據同步，保留131歷史列/38原結案條件')],
        [('Pinned installation','CLI0.1.19/local.17; 208 product files match the installed pinned ZIP'),('Crop/register pressure','13 installed tests pass, including all animated crop/transform channels; original12-test evidence retained'),('Sequence/alpha/clocks','63 sequence,45 clock,17 alpha,8 affine and122 CLI methods pass separately, zero skips'),('Paired combination timing',f'Animated crop/reverse child/arc_push/area, three runs each: medians{old:.3f}→{new:.3f}s; all120 frames and PCM match across six renders'),('Registered Skill','Actual render/validate;120 frames/PCM match old installation;68 files/17 modules'),('Actual case/media','Self-authored original/editable package, complete MP4/GIF decode and extracted-frame inspection; first authoring-field rejection retained; no playback/listening acceptance'),('Kit/full documentation','Independent r20 kit registration/calls; trilingual README/C27/workflow/evidence updated;131 historical rows/38 original closures preserved')]]
    targets=['installation-final-r1/verification.json','tests/projection-final-r1/verification.json','tests/sequence-final-r1/verification.json',
             'benchmark-r3/verification.json','skill-r3/verification.json','preview-r4/verification.json','final-delivery-r1/verification.json']
    for language,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        path=ROOT/name;text=read(path)
        text=text.replace('<!-- affine-scanline-current -->','<!-- affine-scanline-history -->',1).replace('<!-- /affine-scanline-current -->','<!-- /affine-scanline-history -->',1)
        text=text.replace('**CLI 0.1.17 / alpha.4-local.15 / r17 kit**','**Historical / 历史 / 歷史：CLI 0.1.17 / alpha.4-local.15 / r17 kit**',1)
        block='<!-- projection-scanline-current -->\n\n**CLI 0.1.19 / alpha.4-local.17 / r20 kit** · 1 Skill / 17 modules. '+summaries[language]+'\n\n'
        block+='[Install / 固定0.1.19](docs/releases/CLI_0.1.19_LOCAL.md) · [Workflow / 使用流程]('+GUIDE+') · [C27](docs/product/CASES.md#c27-projection-scanline) · [Evidence]('+REPORT+')\n\n'
        block+='```powershell\n& $avk validate --project $project\n& $avk render --project $project --sequence-sampling area --sequence-memory-mib 1024 --output $output --hardware-encode auto\n```\n\n'
        block+='![Actual installed output / silent](docs/assets/projection-scanline-20261026-r2/projection.gif)\n\n'
        block+=['CPU合成；GPU编码单独选择。本次为384×216/4秒组合实测，完整4K/长片和自然质量继续验收。','CPU合成；GPU編碼另外選擇。本次為384×216/4秒組合實測，完整4K/長片及自然品質繼續驗收。','CPU composition; GPU encoding is separate. This is a384×216/four-second combination measurement, with general4K/long-form and natural-quality acceptance still open.'][language]
        block+='\n\n<!-- /projection-scanline-current -->\n\n'
        if '<!-- projection-scanline-current -->' in text:
            text=re.sub(r'<!-- projection-scanline-current -->.*?<!-- /projection-scanline-current -->\n\n',lambda _:block,text,count=1,flags=re.S)
        else:text=text.replace('<!-- affine-scanline-history -->',block+'<!-- affine-scanline-history -->',1)
        lines=[]
        for line in text.splitlines():
            if not re.match(r'^\| R\d+\s*\|',line):
                if '359' in line and 'CLI 0.1.16' in line and line.startswith('**'):
                    line=line.replace('CLI 0.1.16','CLI 0.1.19')
                if 'GOAL_GAPS_20261025.md)' in line:
                    line=re.sub(r'CLI 0\.1\.1[67]', 'CLI 0.1.19',line)
                if line.startswith('**Current delivery / 当前交付 / 目前交付（R110'):
                    line=line.replace('Current delivery / 当前交付 / 目前交付','Historical delivery / 历史交付 / 歷史交付').replace('CLI 0.1.16','CLI 0.1.15')
                line=line.replace('unified-skill-r17.zip','unified-skill-r20.zip').replace('[r17 Skill kit]','[r20 Skill kit]')
                if 'local.15/final-r1/installed' in line:
                    line=line.replace('local.15/final-r1/installed','local.17/final-r1/installed').replace('CLI 0.1.17','CLI 0.1.19')
            lines.append(line)
        text='\n'.join(lines)+'\n'
        for number,((title,detail),target) in enumerate(zip(checks[language],targets),132):
            row=f'| R{number} | 2026-10-26 {title} | {detail} | [Evidence](docs/validation/evidence/projection-scanline-20261026-r1/{target}) |'
            if re.search(r'^\| R'+str(number)+r'\s*\|.*$',text,re.M):
                text=re.sub(r'^\| R'+str(number)+r'\s*\|.*$',lambda _:row,text,count=1,flags=re.M)
            else:
                prior=re.search(r'^\| R'+str(number-1)+r'\s*\|.*$',text,re.M);assert prior
                text=text[:prior.end()]+'\n'+row+text[prior.end():]
        write(path,text)
    for name in ('GOAL_GAPS_20261025.md','IMPLEMENTATION_PLAN_20261025.md'):
        path=ROOT/'docs/product'/name;text=read(path)
        current='当前本地 **CLI0.1.19 / alpha.4-local.17 / r20 kit**，动态裁切及序列crop/fit/TRS复用已交付；[使用与同源交错计时](PROJECTION_RENDERING.md)。CPU合成，38原关闭条件保持。'
        text=text.replace('当前本地 **CLI0.1.17','此前本地 **CLI0.1.17',1)
        if current not in text:
            at=text.index('\n\n')+2;text=text[:at]+current+'\n\n'+text[at:]
        if name.startswith('GOAL'):
            row=re.search(r'^\| G32\s*\|.*$',text,re.M);assert row
            parts=row[0].split('|')
            addition='；动态裁切和原生序列crop/fit/TRS双线性/面积参数复用、同组合三轮及逐帧对照已交付'
            if addition not in parts[3]:parts[3]+=addition
            text=text[:row.start()]+'|'.join(parts)+text[row.end():]
            text=re.sub(r'^\| V01\s*\|.*$', '| V01 | 当前已安装与注册 | local.17 / CLI0.1.19，1Skill/17模块、r20 kit；[208文件固定安装](../validation/evidence/projection-scanline-20261026-r1/installation-final-r1/verification.json)，旧包保留 |',text,flags=re.M)
            text=text.replace('[当前全部字段](motion-pack-capabilities-cli-0.1.16.json)','[当前全部字段](projection-scanline-capabilities-cli-0.1.19.json)')
        addition='\n2026-10-26 G32子项：'+summaries[0]+'[完整实测](../validation/裁切与序列投影实测_2026-10-26.md)。\n'
        if addition not in text:text+=addition
        write(path,text)
    for prefix in ('docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
        for suffix in ('','.zh-TW','.en'):
            path=ROOT/(prefix+suffix+'.md');text=read(path)
            text=text.replace('0.1.17','0.1.19').replace('local.15','local.17').replace('r17 kit','r20 kit').replace('[r17','[r20').replace('unified-skill-r17.zip','unified-skill-r20.zip')
            text=text.replace('affine-scanline-capabilities-cli-0.1.19.json','projection-scanline-capabilities-cli-0.1.19.json')
            addition='\n[Animated crop and native-canvas projection / 动态裁切与嵌套投影]('+('../product/PROJECTION_RENDERING.md' if prefix.startswith('docs/skills') else 'PROJECTION_RENDERING.md')+') retains the existing bilinear/area kernels, explicit raster quota and editable keys; CPU composition and GPU encoding remain separate.\n'
            if addition not in text:text+=addition
            write(path,text)
    path=ROOT/'docs/product/CASES.md';text=read(path)
    if 'id="c27-projection-scanline"' not in text:
        text+='\n<a id="c27-projection-scanline"></a>\n\n## C27 动态裁切与嵌套投影 / Crop and nested projection\n\n'+summaries[0]+'\n\n[完整使用流程](PROJECTION_RENDERING.md) · [原始实测](../validation/裁切与序列投影实测_2026-10-26.md) · [可编辑案例](../assets/projection-scanline-20261026-r2/editable-projection.aevpkg.zip) · [原图](../assets/projection-scanline-20261026-r2/original.png) · [实际MP4](../assets/projection-scanline-20261026-r2/projection.mp4)\n\n![Actual installed output / silent](../assets/projection-scanline-20261026-r2/projection.gif)\n\nNative child480×270/output384×216,30fps/4s, reverse clock, animated crop, arc_push and area sampling. Self-authored graphic; natural-motion, continuous-playback and listening acceptance remain open.\n'
    write(path,text)
    for relative in ('docs/product/MOTION_PACKS.md','docs/product/AFFINE_RENDERING.md','docs/README.md'):
        path=ROOT/relative;text=read(path)
        link=('product/' if relative=='docs/README.md' else '')+'PROJECTION_RENDERING.md'
        addition='\n2026-10-26: CLI0.1.19 extends pure scanline reuse to animated crop and child crop/fit/TRS, for bilinear and area. [Current workflow / 当前使用]('+link+') includes the editable combination case and actual previews; historical timing remains scoped to its original fixture.\n'
        if addition not in text:text+=addition
        write(path,text)
    path=ROOT/'scripts/sync_capability_manuals.py';text=read(path)
    text=text.replace('0.1.17','0.1.19').replace('local.15','local.17').replace('r17 kit','r20 kit')
    text=text.replace('Scanline affine parameter reuse, portable motion/capture,','Animated crop and nested bilinear/area projection parameter reuse, portable motion/capture,')
    text=text.replace('[Affine timing/preview](AFFINE_RENDERING.md)','[Projection workflow/preview](PROJECTION_RENDERING.md)')
    write(path,text)


if __name__=='__main__':main()
