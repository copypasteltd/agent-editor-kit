"""Maintain current delivery and trilingual evidence without rewriting history."""
import argparse
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/affine-scanline-20261025-r1'
GUIDE='docs/product/AFFINE_RENDERING.md'
REPORT='docs/validation/仿射扫描行复用实测_2026-10-25.md'


def load(path):return json.loads(path.read_bytes())
def write(path,text):path.write_text(text,encoding='utf8',newline='\n')
def read(path):return path.read_text('utf-8-sig')


def prepare():
    installation=load(BASE/'installation-r1/verification.json')
    assert installation['status']=='installed-and-byte-verified'
    previous=load(ROOT/'docs/validation/evidence/motion-pack-20261025-r1/installation-r2/verification.json')
    path=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md'
    before,after=read(path).split('## CLI 0.1.16 当前交付 / Current delivery',1)
    before=before.replace('CLI 0.1.16','CLI 0.1.17').replace('v0.1.0-alpha.4-local.14','v0.1.0-alpha.4-local.15')
    before=before.replace('local.15/final-r2','local.15/final-r1').replace('local.15/candidate-r2','local.15/candidate-r1')
    before=before.replace('unified-skill-r16.zip','unified-skill-r17.zip').replace('package-0.1.16-r2.json','package-0.1.17.json')
    for field in ('archive_sha256','manifest_sha256','archive_bytes'):
        before=before.replace(str(previous[field]),str(installation[field]))
    text=before+'## CLI 0.1.16 历史交付 / Historical delivery'+after
    text+='\n## CLI 0.1.17 当前交付 / Current delivery\n\n'
    text+=str(installation['archive_bytes'])+' bytes，208 个产品 Python 文件。固定画布仿射合成自动按扫描行复用纯数值变换，浮点预乘双线性采样保持。'
    text+='[使用与实测预览](AFFINE_RENDERING.md) · [交错计时、逐帧与安装核验](../validation/仿射扫描行复用实测_2026-10-25.md)。'
    text+='CPU 计算优化，GPU 编码依旧显式选择；原 local.14/r16 和历史失败保留，全部完整目标继续推进。\n'
    write(path,text)
    (ROOT/'docs/product/affine-scanline-capabilities-cli-0.1.17.json').write_bytes((BASE/'installation-r1/capabilities.stdout.json').read_bytes())
    path=ROOT/'docs/product/MOTION_PACKS.md';text=read(path)
    text=text.replace('CLI **0.1.16 / alpha.4-local.14**：','CLI **0.1.16 / alpha.4-local.14** 引入；当前 0.1.17：',1)
    marker='[完整实测 / Evidence]'
    at=text.index(marker)
    text=text[:at]+'CLI 0.1.17 自动复用固定画布仿射参数；[使用与同源交错计时](AFFINE_RENDERING.md)。原六包、参数和作者时钟保持，历史65秒记录保留。\n\n'+text[at:]
    write(path,text)


def final():
    bench=load(BASE/'verify-r2/verification.json')
    assert bench['status']=='passed' and bench['frames_equal_all_six'] and bench['audio_pcm_equal_all_six']
    for phase in ('skill-r2','preview-r2','kit-r2'):assert load(BASE/phase/'verification.json')['status']=='passed'
    scopes=[('development-r1',8),('native-motion-development-r1',5),('alpha-development-r1',17),
            ('affine-installed-r1',8),('motion-installed-r1',5),('alpha-installed-r1',17),
            ('clock-installed-r1',None),('cli-installed-r1',122)]
    for run,count in scopes:
        proof=load(BASE/'tests'/run/'verification.json')
        assert proof['status']=='passed' and proof['result']['skipped']==0
        assert count is None or proof['result']['methods']==count
    old,new=bench['medians_seconds']['old'],bench['medians_seconds']['new'];ratio=bench['median_ratio']
    table='\n'.join('| '+run+' | '+str(load(BASE/'tests'/run/'verification.json')['result']['methods'])+' / '+str(load(BASE/'tests'/run/'verification.json')['result']['methods'])+'，0 skip | [日志](evidence/affine-scanline-20261025-r1/tests/'+run+'/verification.json) |' for run,_ in scopes)
    timings='\n'.join('| '+str(n+1)+' | '+f"{bench['timings_seconds']['old'][n]:.6f}"+' | '+f"{bench['timings_seconds']['new'][n]:.6f}"+' |' for n in range(3))
    report=f'''# 仿射扫描行参数复用实测（2026-10-25）

CLI **0.1.17 / alpha.4-local.15 / r17 kit** 已安装并由真实统一 Skill 调用。208 个产品文件与固定包一致，1入口/17模块/68 Skill 文件。优化只改变固定画布仿射 helper 的纯表达式计算复用；半像素坐标、浮点预乘和双线性采样未更换。[使用流程](../product/AFFINE_RENDERING.md) · [实现前契约](../specs/仿射扫描行复用契约_20261025.md)。

## 真实交错计时

原安装0.1.16与新安装0.1.17：相同可编辑包导入工程、相同自制图卡和 detail_scan 默认配方，640×360/30fps/4秒，libx264 CRF0/yuv444p、PCM float32，硬件编码关闭。仅本计时进程及子进程的CPU亲和性限为 {len(bench['affinity']['logical_processors'])} 个逻辑处理器；FFmpeg线程选项保持双方相同的默认值。其他应用没有改变，非独占主机基准。顺序为old1/new1/new2/old2/old3/new3。

| 轮 | 旧安装秒 | 新安装秒 |
|---|---:|---:|
{timings}

旧中位数 **{old:.6f}秒**，新中位数 **{new:.6f}秒**，比值 **{ratio:.3f}×**。计时包含CLI启动、依赖检查、渲染和编码，不包括后续解码核验；不是GPU加速比或一般性能保证。此前并发负载下65秒记录继续保留，不用作此比值分母。

六次实际成片的全部120帧RGBA摘要相同，完整4秒/48kHz/双声道/float32 PCM摘要相同；时间线、设置、资产、Rights Ledger与原工程包一致。render正常追加六条outputs、六条change_log并更新updated_at，其余工程字段相同。原始计时、命令、输出和摘要：[复核证据](evidence/affine-scanline-20261025-r1/verify-r2/verification.json)。音频在此图卡工程为静音，不据此推断自然声音质量。

## 分范围测试

| 范围 | 通过/方法 | 证据 |
|---|---:|---|
{table}

各范围分别执行，不相加为功能完成率。新增8项实际RGBA测试包括静态极值、六包强制仿射、多切片线程、重复/倒退时间戳、Bezier/hold/非零开始/嵌套反向、透明隐藏RGB、像素依赖/有状态回退和独立前向旋转几何。旧实现快照只作为差分回归基准；独立红点质心另有解析门槛。17项原透明采样、5项原生运镜、嵌套时钟和122项CLI回归独立留档。没有重复模型推理或新增模型质量结论。

## 实际安装、Skill与媒体

真实 C 盘发现联接仍指向 E 盘单入口 Skill；实际 version/capabilities/render/validate、全120帧和PCM对照通过：[真实 Skill](evidence/affine-scanline-20261025-r1/skill-r2/verification.json)。r17 kit在独立中文/空格目录登记并执行9次进程调用，使用独有导入工程，真实发现目录未改变：[kit核验](evidence/affine-scanline-20261025-r1/kit-r2/verification.json)。

[固定离线包与208文件](evidence/affine-scanline-20261025-r1/installation-r1/verification.json) · [实际MP4/GIF完整解码](evidence/affine-scanline-20261025-r1/preview-r2/verification.json)。公开原图/中点/MP4/GIF来自自制FIELD NOTES，未发布新用户私有素材；NVENC只编码预览，合成是CPU。未做连续播放或人类美学/听觉验收。

![实际安装版输出](../assets/affine-scanline-20261025-r1/detail-scan.gif)

## 保留的失败和范围

首轮测量脚本写错Python解码名称utf8-sig，旧版version已成功，但解析阶段失败，没有形成有效测量；[原失败](evidence/affine-scanline-20261025-r1/benchmark-r1/verification.json)和脚本快照保留。脚本改为utf-8-sig，在新的独有工作目录执行完整三轮。r2六次渲染/解码都成功，但辅助脚本错误要求整个project.json字节不变，忽略render正常登记输出，因此[最终辅助断言失败](evidence/affine-scanline-20261025-r1/benchmark-r2/verification.json)。后续verify-r2独立重读保存的命令结果、校验原输出哈希，再次完整解码六个实际文件；与原工程包逐字段比对，确认只有正常的六条输出/日志及updated_at改变。它使用保存的原计时，没有重计时、重渲染或覆盖失败记录，未改产品/像素/性能门槛。

kit-r1所有命令成功，但辅助验证和真实Skill渲染共用了工程；render正常更新元数据，导致dry-run前后字节断言失败。[原失败](evidence/affine-scanline-20261025-r1/kit-r1/failure.json)保留；kit-r2改为其独有目录导入工程，再执行同一dry-run/验证，不降低字节一致门槛。运行包及r17 kit字节未因此更改。

本优化不覆盖动态crop/fit的独立序列投影、其他geq滤镜、全部4K/长片/RSS或GPU合成。自然素材、运镜美学和主体跟随组合仍开放；所有38组原关闭条件及R01–R124历史记录保持。公开alpha.3标签/附件不覆盖，本轮是本地安装与main更新。
'''
    write(ROOT/REPORT,report)
    summaries=(
        f'固定画布旋转/缩放自动复用扫描行参数；同工程三轮中位数 {old:.2f} → {new:.2f} 秒（{ratio:.2f}×），六次全部120帧及PCM相同。CPU合成，GPU编码仍显式选择。',
        f'固定畫幅旋轉/縮放自動復用掃描行參數；同專案三輪中位數 {old:.2f} → {new:.2f} 秒（{ratio:.2f}×），六次全部120影格及PCM相同。CPU合成，GPU編碼仍明確選擇。',
        f'Fixed-canvas affine parameters are reused per scanline. Paired medians: {old:.2f} → {new:.2f} seconds ({ratio:.2f}×); all 120 frames and PCM match across six renders. CPU composition; hardware encoding remains explicit.',
    )
    checks=(
        [('固定安装','CLI0.1.17/local.15，208产品文件与发行ZIP安装版一致'),('像素与透明采样','源码/安装各8项新像素、5项运镜和17项透明采样通过；各范围独立'),('交错性能实测',f'同工程三轮中位数{old:.3f}→{new:.3f}秒（{ratio:.3f}×），六次120帧与完整PCM相同；4逻辑CPU亲和性，非GPU比值'),('真实注册Skill','实际渲染/validate；120帧和PCM与旧安装相同，单入口17模块'),('时钟与CLI回归','安装版嵌套时钟及122项CLI通过，0skip；未重跑全部历史套件'),('保留失败与范围','测量脚本编码名称失败保留；CPU优化，仅固定画布仿射，完整4K/长片/自然质量未验收'),('kit与完整文档','r17 kit独立登记/调用通过；三语README、C26和实测同步，124历史行及38原关闭条件保持')],
        [('固定安裝','CLI0.1.17/local.15，208產品檔案與發行ZIP安裝版一致'),('像素與透明採樣','原始碼/安裝各8項新像素、5項運鏡及17項透明採樣通過；各範圍獨立'),('交錯效能實測',f'同專案三輪中位數{old:.3f}→{new:.3f}秒（{ratio:.3f}×），六次120影格與完整PCM相同；4邏輯CPU親和性，非GPU比值'),('實際註冊Skill','實際渲染/validate；120影格及PCM與舊安裝相同，單入口17模組'),('時鐘與CLI迴歸','安裝版巢狀時鐘及122項CLI通過，0skip；未重跑全部歷史套件'),('保留失敗及範圍','測量腳本編碼名稱失敗保留；CPU最佳化，僅固定畫幅仿射，完整4K/長片/自然品質未驗收'),('kit及完整文件','r17 kit獨立登記/調用通過；三語README、C26及實測同步，124歷史列及38原結案條件保持')],
        [('Pinned installation','CLI0.1.17/local.15; 208 product files match the installed release ZIP'),('Pixels/alpha sampling','Source/installed: 8 new pixel, 5 motion and 17 alpha tests each pass; scopes remain separate'),('Paired timing',f'Three-run medians {old:.3f}→{new:.3f}s ({ratio:.3f}×), all120 frames and complete PCM match across six renders; four logical CPU affinity, not a GPU ratio'),('Registered Skill','Actual render/validate; 120 frames and PCM match old installation; one entry/17 modules'),('Clocks/CLI regression','Installed nested clocks and122 CLI tests pass, zero skips; not the entire historical suite'),('Failure/limits retained','Measurement-helper encoding-name failure retained; CPU optimization for fixed-canvas affine only; general4K/long-form/natural quality unaccepted'),('Kit/full documentation','Independent r17 kit registration/calls pass; trilingual README/C26/evidence updated;124 historical rows and38 original closure conditions retained')],
    )
    targets=['installation-r1/verification.json','tests/affine-installed-r1/verification.json','verify-r2/verification.json',
             'skill-r2/verification.json','tests/cli-installed-r1/verification.json','benchmark-r1/verification.json','final-delivery-r2/verification.json']
    for language,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        path=ROOT/name;text=read(path)
        text=text.replace('<!-- motion-pack-current -->','<!-- motion-pack-history -->',1).replace('<!-- /motion-pack-current -->','<!-- /motion-pack-history -->',1)
        text=text.replace('**CLI 0.1.16 / alpha.4-local.14 / r16 kit**','**Historical / 历史 / 歷史：CLI 0.1.16 / alpha.4-local.14 / r16 kit**',1)
        block='<!-- affine-scanline-current -->\n\n**CLI 0.1.17 / alpha.4-local.15 / r17 kit** · 208 product Python files · 1 Skill / 17 modules. '+summaries[language]+'\n\n'
        block+='[Workflow / 使用流程]('+GUIDE+') · [C26](docs/product/CASES.md#c26-affine-scanline) · [Evidence]('+REPORT+')\n\n'
        block+='![Actual installed render / silent](docs/assets/affine-scanline-20261025-r1/detail-scan.gif)\n\n'
        block+='Same 640×360/30fps/4s fixture and codec; bounded child-process CPU affinity. Separate crop/fit projectors, general4K/long-form and natural-footage acceptance remain open.\n\n<!-- /affine-scanline-current -->\n\n'
        text=text.replace('<!-- motion-pack-history -->',block+'<!-- motion-pack-history -->',1)
        lines=[]
        for line in text.splitlines():
            if not re.match(r'^\| R\d+\s*\|',line) and 'Historical /' not in line:
                line=line.replace('[r16 Skill kit]','[r17 Skill kit]').replace('unified-skill-r16.zip','unified-skill-r17.zip')
                if 'final-r2/installed' in line:line=line.replace('v0.1.0-alpha.4-local.14/final-r2','v0.1.0-alpha.4-local.15/final-r1').replace('CLI 0.1.16','CLI 0.1.17')
            lines.append(line)
        text='\n'.join(lines)+'\n'
        for index,((title,detail),target) in enumerate(zip(checks[language],targets),125):
            row=f'| R{index} | 2026-10-25 {title} | {detail} | [Evidence](docs/validation/evidence/affine-scanline-20261025-r1/{target}) |'
            prior=re.search(r'^\| R'+str(index-1)+r'\s*\|.*$',text,re.M);assert prior
            text=text[:prior.end()]+'\n'+row+text[prior.end():]
        write(path,text)
    for name in ('GOAL_GAPS_20261025.md','IMPLEMENTATION_PLAN_20261025.md'):
        path=ROOT/'docs/product'/name;text=read(path)
        at=text.index('\n\n')+2
        current='当前本地 **CLI0.1.17 / alpha.4-local.15 / r17 kit**，固定画布仿射扫描行复用已交付；[同源三轮计时与逐帧核验](../validation/仿射扫描行复用实测_2026-10-25.md)。CPU合成，全部38原关闭条件保持。\n\n'
        text=text[:at]+current+text[at:]
        text=text.replace('当前交付为 **CLI 0.1.16','此前交付为 **CLI 0.1.16').replace('当前本地交付为 **CLI 0.1.16','此前本地交付为 **CLI 0.1.16')
        if name.startswith('GOAL'):
            row=re.search(r'^\| G32\s*\|.*$',text,re.M);assert row
            parts=row[0].split('|');parts[3]+='；固定画布仿射纯参数按扫描行复用，同工程旧/新三轮与像素一致实测'
            text=text[:row.start()]+'|'.join(parts)+text[row.end():]
            text=re.sub(r'^\| V01\s*\|.*$', '| V01 | 当前已安装与注册 | local.15 / CLI0.1.17，1Skill/17模块、r17 kit；[208文件固定安装](../validation/evidence/affine-scanline-20261025-r1/installation-r1/verification.json)，旧包保留 |',text,flags=re.M)
        else:
            text=text.replace('当前 CLI 0.1.16 / local.14 / r16 kit','当前 CLI0.1.17 / local.15 / r17 kit')
        text+='\n2026-10-25 G32子项：[扫描行仿射复用](AFFINE_RENDERING.md)实际安装与Skill交付；'+summaries[0]+'全部原关闭条件保持。\n'
        write(path,text)
    for prefix in ('docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
        for suffix in ('','.zh-TW','.en'):
            path=ROOT/(prefix+suffix+'.md');text=read(path)
            text=text.replace('0.1.16','0.1.17').replace('local.14','local.15').replace('r16 kit','r17 kit').replace('[r16','[r17').replace('unified-skill-r16.zip','unified-skill-r17.zip')
            text=text.replace('package-0.1.17-r2.json','package-0.1.17.json').replace('local.15/final-r2','local.15/final-r1').replace('motion-pack-capabilities-cli-0.1.17.json','affine-scanline-capabilities-cli-0.1.17.json')
            text+='\n[Fixed-canvas affine reuse / 扫描行复用]('+('../product/AFFINE_RENDERING.md' if prefix.startswith('docs/skills') else 'AFFINE_RENDERING.md')+') uses the existing render workflow, keeps CPU composition explicit, and provides paired timing and actual previews.\n'
            write(path,text)
    path=ROOT/'docs/product/CASES.md';text=read(path)
    text+='\n<a id="c26-affine-scanline"></a>\n\n## C26 仿射扫描行复用 / Affine scanline reuse\n\n'+summaries[0]+'\n\n[使用 / Workflow](AFFINE_RENDERING.md) · [原始命令、完整逐帧与计时 / Evidence](../validation/仿射扫描行复用实测_2026-10-25.md) · [原图](../assets/affine-scanline-20261025-r1/original.png) · [MP4](../assets/affine-scanline-20261025-r1/detail-scan.mp4)\n\n![Actual installed output](../assets/affine-scanline-20261025-r1/detail-scan.gif)\n\nFour-second self-authored graphic, silent; no natural-footage or continuous-playback acceptance. Full goal remains active.\n'
    write(path,text)
    path=ROOT/'docs/README.md';text=read(path)
    text+='\n- [仿射扫描行复用：使用、预览与计时](product/AFFINE_RENDERING.md)\n- [仿射扫描行复用实测与边界](validation/仿射扫描行复用实测_2026-10-25.md)\n'
    write(path,text)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('prepare','final'),required=True)
    {'prepare':prepare,'final':final}[parser.parse_args().phase]()
