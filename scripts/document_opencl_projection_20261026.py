"""Publish actual GPU composition evidence without removing historical scope."""
from pathlib import Path
import argparse
import json
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/opencl-projection-20261026-r1'
REPORT='docs/validation/OpenCL原生投影实测_2026-10-26.md'
GUIDE='docs/product/OPENCL_PROJECTION.md'

def load(path):return json.loads(path.read_bytes())
def write(path,text):path.write_text(text,encoding='utf8',newline='\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--final-kit',action='store_true')
    args=parser.parse_args()
    installation=load(BASE/'installation-final-r2/verification.json')
    assert installation['status']=='installed-and-byte-verified' and installation['source_file_count']==209
    bench=load(BASE/'benchmark-r2/verification.json');assert bench['status']=='passed'
    assert bench['frames_and_clock_equal_all_six'] and bench['audio_pcm_equal_all_six']
    for name in ('controls-r1','skill-r2','preview-r2'):
        assert load(BASE/name/'verification.json')['status']=='passed',name
    medians=bench['medians_seconds'];cpu,gpu=medians['cpu'],medians['opencl'];ratio=bench['median_ratio']
    tests=[]
    for name,expected in [('native-final-r1',18),('sequence-final-r1',63),('queue-schema-final-r1',47),
                          ('regression-final-r1',119),('cli-development-r1',122)]:
        proof=load(BASE/'tests'/name/'verification.json')
        assert proof['status']=='passed' and proof['result']['methods']==expected and proof['result']['skipped']==0
        assert proof['frozen_equal'] and proof['installed_frozen_equal']
        tests.append((name,expected))
    kit=None
    if args.final_kit:
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.20-r21.json')
        assert load(BASE/'kit-r2/verification.json')['status']=='passed' and kit['files']==96
    summaries=[
        f'原生 GPU 动态裁切、仿射运镜及子画布双线性/面积投影已交付。相同编码与工程三轮中位数 {cpu:.2f}→{gpu:.2f}秒（{ratio:.2f}×），六次全部120帧、时钟和PCM相同；默认CPU，显式策略决定使用/回退。',
        f'原生 GPU 動態裁切、仿射運鏡及子畫布雙線性/面積投影已交付。相同編碼及專案三輪中位數 {cpu:.2f}→{gpu:.2f}秒（{ratio:.2f}×），六次全部120影格、時鐘及PCM相同；預設CPU，以明確策略選擇使用/回退。',
        f'Native GPU crop, affine camera motion and child-canvas bilinear/area projection are installed. Same-project/codec three-run medians {cpu:.2f}→{gpu:.2f}s ({ratio:.2f}×); all120 frames, clocks and PCM match across six renders. CPU remains the default; explicit policy records GPU use/fallback.'
    ]
    checks=[
        [('固定离线安装','CLI0.1.20/local.18-final-r2；209产品文件与ZIP安装版逐字节一致，旧包保留'),
         ('原生GPU与4K像素','18项真实GPU专项0skip；1080p/4K仿射整帧、4K源面积缩小、透明/时钟/全部通道/独立几何与积分通过'),
         ('渲染/队列/Schema回归','119项渲染策略/采样/透明/时钟/硬件、63项序列、47项队列/Schema、122项CLI分别通过，0skip'),
         ('相同编码交错计时',f'CPU/GPU各3次；中位数{cpu:.3f}→{gpu:.3f}秒，{ratio:.3f}×；六次120帧/时钟/完整PCM相同，非4K实时保证'),
         ('失败、取消、恢复与队列','错误设备require明确失败；启动前取消后原设置恢复、真实GPU队列及quality通过；两次120帧/PCM相同'),
         ('真实统一Skill','唯一注册入口调用最终安装版GPU投影；120帧/PCM相同，69文件/17内部模块，无源码回落'),
         ('案例媒体与使用流程','自制原图、实际GPU MP4/GIF、可编辑包、SHA和完整解码；未做连续播放/听审，自然质量仍开放'),
         ('三语文档与独立kit','三语README、完整功能/服务、Skill说明、C28与r21独立kit同步；保留138历史核验行和38原关闭条件')],
        [('固定離線安裝','CLI0.1.20/local.18-final-r2；209產品檔案與ZIP安裝版逐位元組一致，舊包保留'),
         ('原生GPU與4K像素','18項實際GPU專項0skip；1080p/4K仿射整幀、4K源面積縮小、透明/時鐘/全部通道/獨立幾何與積分通過'),
         ('渲染/佇列/Schema迴歸','119項渲染策略/採樣/透明/時鐘/硬體、63項序列、47項佇列/Schema、122項CLI分別通過，0skip'),
         ('相同編碼交錯計時',f'CPU/GPU各3次；中位數{cpu:.3f}→{gpu:.3f}秒，{ratio:.3f}×；六次120影格/時鐘/完整PCM相同，非4K即時保證'),
         ('失敗、取消、恢復與佇列','錯誤裝置require明確失敗；啟動前取消後原設定恢復、實際GPU佇列及quality通過；兩次120影格/PCM相同'),
         ('實際統一Skill','唯一註冊入口調用最終安裝版GPU投影；120影格/PCM相同，69檔案/17內部模組，無原始碼回落'),
         ('案例媒體與使用流程','自製原圖、實際GPU MP4/GIF、可編輯包、SHA及完整解碼；未做連續播放/聽審，自然品質仍開放'),
         ('三語文件與獨立kit','三語README、完整功能/服務、Skill說明、C28及r21獨立kit同步；保留138歷史核驗列及38原結案條件')],
        [('Pinned offline install','CLI0.1.20/local.18-final-r2;209 product files byte-match the installed ZIP; previous bundles retained'),
         ('Native GPU/4K pixels','18 actual-GPU tests,zero skips;1080p/4K affine whole frames,4K area-source reduction,alpha/clocks/all channels and independent geometry/integration'),
         ('Render/queue/schema regression','119 render-policy/sampling/alpha/clock/hardware,63 sequence,47 queue/schema and122 CLI methods pass separately,zero skips'),
         ('Paired identical-codec timing',f'Three CPU/GPU runs each: medians{cpu:.3f}→{gpu:.3f}s,{ratio:.3f}×;all120 frames/clocks/full PCM match across six;not realtime4K acceptance'),
         ('Failure/cancel/resume/queue','Unavailable required device fails;cancelled operation resumes saved settings;actual GPU queue and quality pass;both120-frame/PCM outputs match'),
         ('Actual unified Skill','The single registered launcher uses final installed GPU projection;120 frames/PCM match;69 files/17 internal modules,no source fallback'),
         ('Case/media/workflow','Self-authored original,actual GPU MP4/GIF,editable package,SHA/full decode;no continuous-playback/listening or natural-quality acceptance'),
         ('Trilingual docs/isolated kit','README,function/service detail,Skill,C28 and isolated r21 kit synchronized;138 historical evidence rows/38 original closures retained')]
    ]
    targets=['installation-final-r2/verification.json','tests/native-final-r1/verification.json',
             'tests/regression-final-r1/verification.json','benchmark-r2/verification.json','controls-r1/verification.json',
             'skill-r2/verification.json','preview-r2/verification.json','final-delivery-r1/verification.json']
    for language,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        path=ROOT/name;text=path.read_text('utf-8-sig')
        text=text.replace('projection-scanline-current','projection-scanline-history')
        text=re.sub(r'(<!-- projection-scanline-history -->\n\n)(\*\*CLI)',r'\1**Historical / 历史 / 歷史：CLI',text,count=1)
        block='<!-- opencl-projection-current -->\n\n**CLI0.1.20 / alpha.4-local.18 / r21 kit** · 1 Skill / 17 modules. '+summaries[language]+'\n\n'
        block+='[Install / 固定安装](docs/releases/CLI_0.1.20_LOCAL.md) · [GPU workflow / 使用流程]('+GUIDE+') · [C28](docs/product/CASES.md#c28-opencl-projection) · [Evidence]('+REPORT+')\n\n'
        block+='```powershell\n& $avk validate --project $project\n& $avk render --project $project --output $output --projection-acceleration prefer --projection-device 0.0 --projection-memory-mib 1024 --sequence-sampling area --sequence-memory-mib 1024 --hardware-encode off\n```\n\n'
        block+='![Actual installed GPU composition / silent](docs/assets/opencl-projection-20261026-r1/projection.gif)\n\n'
        block+=['仅本机RTX3060设备实测；其余特效/字幕仍CPU。1080p/4K单帧像素对照已过，通用4K实时、长片与自然视听继续验收。',
                '僅本機RTX3060裝置實測；其餘特效/字幕仍CPU。1080p/4K單幀像素對照已過，通用4K即時、長片及自然視聽繼續驗收。',
                'RTX3060 device-tested only;other effects/subtitles remain CPU.1080p/4K single-frame pixel equality passes;general realtime4K,long-form and natural audiovisual acceptance remain open.'][language]
        block+='\n\n<!-- /opencl-projection-current -->\n\n'
        if '<!-- opencl-projection-current -->' in text:
            text=re.sub(r'<!-- opencl-projection-current -->.*?<!-- /opencl-projection-current -->\n\n',lambda _:block,text,count=1,flags=re.S)
        else:text=text.replace('<!-- projection-scanline-history -->',block+'<!-- projection-scanline-history -->',1)
        lines=[]
        for line in text.splitlines():
            if not re.match(r'^\| R\d+\s*\|',line):
                line=line.replace('--hardware-encode auto','--hardware-encode off')
                if line.startswith('**') and ('359' in line or 'unified-skill-r20.zip' in line):
                    line=line.replace('CLI 0.1.19','CLI 0.1.20').replace('unified-skill-r20.zip','unified-skill-r21.zip').replace('[r20 Skill kit]','[r21 Skill kit]')
                if 'local.17/final-r1/installed' in line:
                    line=line.replace('local.17/final-r1/installed','local.18/final-r2/installed').replace('CLI 0.1.19','CLI 0.1.20')
                if 'GOAL_GAPS_20261025.md)' in line:line=line.replace('CLI 0.1.19','CLI 0.1.20')
            lines.append(line)
        text='\n'.join(lines)+'\n'
        replacements=[
            {'F37':'| F37 | 输出、编码与GPU投影 | 工程 → MP4/WebM/MKV、显式OpenCL裁切/仿射/子画布投影、编解码探测与manifest。 | `render --projection-acceleration; render` | 原生GPU需双精度/纹理预检；CPU默认，其他特效仍CPU，无实时/通用4K保证。 |',
             'F38':'| F38 | 持久队列、重试与取消 | 冻结项目快照 → 本地排队、有限worker、显式重试/取消与串行元数据提交。 | `queue enqueue/list/inspect/run/cancel` | GPU投影策略逐作业传递，拒绝其 --reuse-identical 绕过探测；不是云渲染。 |',
             'S16':'| S16 | GPU兼容服务 | 已有原生OpenCL ICD / NVIDIA模型运行库 | 投影off/prefer/require，模型auto/cpu/cuda；实际设备、探测、预算与回退 | `render --projection-acceleration; gpu inspect; --device` | RTX3060实测；仅投影算子GPU化，外部驱动/库许可另列 |'},
            {'F37':'| F37 | 輸出、編碼與GPU投影 | 專案 → MP4/WebM/MKV、明確OpenCL裁切/仿射/子畫布投影、編解碼探測及manifest。 | `render --projection-acceleration; render` | 原生GPU需雙精度/紋理預檢；CPU預設，其餘特效仍CPU，無即時/通用4K保證。 |',
             'F38':'| F38 | 持久佇列、重試與取消 | 凍結專案快照 → 本地排隊、有限worker、明確重試/取消及序列化提交。 | `queue enqueue/list/inspect/run/cancel` | GPU投影策略逐作業傳遞，拒絕其 --reuse-identical 繞過探測；不是雲渲染。 |',
             'S16':'| S16 | GPU相容服務 | 已有原生OpenCL ICD / NVIDIA模型執行庫 | 投影off/prefer/require，模型auto/cpu/cuda；實際裝置、探測、預算及回退 | `render --projection-acceleration; gpu inspect; --device` | RTX3060實測；僅投影算子GPU化，外部驅動/庫授權另列 |'},
            {'F37':'| F37 | Delivery,encoding and GPU projection | Projects → MP4/WebM/MKV,explicit OpenCL crop/affine/child-canvas samplers,codec probes and manifests. | `render --projection-acceleration; render` | Requires native GPU binary64/image probes;CPU default,other effects remain CPU,no realtime/general4K guarantee. |',
             'F38':'| F38 | Persistent queues,retry and cancel | Frozen snapshots → local jobs,bounded workers,explicit retry/cancel and serialized commits. | `queue enqueue/list/inspect/run/cancel` | Per-job GPU projection policy rejects --reuse-identical bypass;not cloud rendering. |',
             'S16':'| S16 | GPU compatibility | Existing native OpenCL ICD / NVIDIA model runtimes | Projection off/prefer/require,models auto/cpu/cuda;actual device,probes,budget and fallback | `render --projection-acceleration; gpu inspect; --device` | RTX3060 tested;projection operators only,external driver/library terms separate |'}
        ][language]
        for key,row in replacements.items():
            text,n=re.subn(r'^\| '+key+r'\s*\|.*$',lambda _:row,text,count=1,flags=re.M);assert n==1
        for number,((title,detail),target) in enumerate(zip(checks[language],targets),139):
            row=f'| R{number} | 2026-10-26 {title} | {detail} | [Evidence](docs/validation/evidence/opencl-projection-20261026-r1/{target}) |'
            if re.search(r'^\| R'+str(number)+r'\s*\|',text,re.M):
                text=re.sub(r'^\| R'+str(number)+r'\s*\|.*$',lambda _:row,text,count=1,flags=re.M)
            else:
                previous=re.search(r'^\| R'+str(number-1)+r'\s*\|.*$',text,re.M);assert previous
                text=text[:previous.end()]+'\n'+row+text[previous.end():]
        write(path,text)
    for name in ('GOAL_GAPS_20261025.md','IMPLEMENTATION_PLAN_20261025.md'):
        path=ROOT/'docs/product'/name;text=path.read_text('utf8')
        text=text.replace('当前本地 **CLI0.1.19','此前本地 **CLI0.1.19',1)
        current='当前本地 **CLI0.1.20 / alpha.4-local.18 / r21 kit**，原生OpenCL裁切/仿射/子画布双线性及面积投影已交付；[使用与实际核验](OPENCL_PROJECTION.md)。其余特效/字幕仍CPU，全部38原关闭条件保持。'
        if current not in text:
            at=text.index('\n\n')+2;text=text[:at]+current+'\n\n'+text[at:]
        if name.startswith('GOAL'):
            row=re.search(r'^\| G32\s*\|.*$',text,re.M);assert row;parts=row[0].split('|')
            addition='；CLI0.1.20接入原生GPU裁切/仿射/序列双线性/面积投影，RTX3060三轮同编码及1080p/4K单帧像素对照通过'
            if addition not in parts[3]:parts[3]+=addition
            parts[4]=' 其他特效/字幕仍CPU；仅本机RTX3060，4K验证为单帧像素/小目标缩小，非实时或长片吞吐。模型常驻、多厂商/设备、全进程RAM/VRAM/磁盘预算及复杂组合验收仍开放 '
            text=text[:row.start()]+'|'.join(parts)+text[row.end():]
            text=re.sub(r'^\| V01\s*\|.*$', '| V01 | 当前已安装与注册 | local.18-final-r2 / CLI0.1.20，1Skill/17模块、69文件、r21 kit；[209文件固定安装](../validation/evidence/opencl-projection-20261026-r1/installation-final-r2/verification.json)，旧包保留 |',text,flags=re.M)
            text=text.replace('[当前全部字段](projection-scanline-capabilities-cli-0.1.19.json)','[当前全部字段](opencl-projection-capabilities-cli-0.1.20.json)')
            row=re.search(r'^\| G38\s*\|.*$',text,re.M);parts=row[0].split('|')
            parts[3]=' 公开alpha.3/CLI0.1.2保持；本地local.18-final-r2/CLI0.1.20/r21安装注册核验；新范围见原生GPU投影实测 '
            text=text[:row.start()]+'|'.join(parts)+text[row.end():]
        else:
            text=re.sub(r'^\| W07[^\n]+$', '| W07 色彩与GPU性能 | G08、G32 | 完整颜色管理、目标算子、GPU/CPU选择、资源预算、模型复用与4K/长片 | 原生OpenCL裁切/仿射/序列双线性及面积投影、同编码三轮与1080p/4K单帧对照交付；其他特效/字幕、常驻、全进程预算与长片仍开放 |',text,flags=re.M)
            text=re.sub(r'^\| W09[^\n]+$', '| W09 许可与公开交付 | G37–G38 | 固定依赖/模型/素材许可、离线包、单一Skill、三语README与公开预发行 | 当前CLI0.1.20/local.18-final-r2/r21本地安装并加载；三语功能/服务/Skill、实际预览与使用流程同步，公开旧版本保持 |',text,flags=re.M)
        addition='\n2026-10-26 G32实现：'+summaries[0]+'[完整证据](../validation/OpenCL原生投影实测_2026-10-26.md)。\n'
        if addition not in text:text+=addition
        write(path,text)
    for prefix in ('docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
        for language,suffix in enumerate(('','.zh-TW','.en')):
            path=ROOT/(prefix+suffix+'.md');text=path.read_text('utf8')
            route='../product/' if prefix.startswith('docs/skills') else ''
            block='<!-- community-current -->\n\n**CLI0.1.20 / alpha.4-local.18 / r21 kit · 1 Skill / 17 modules / 69 files.**\n\n'+summaries[language]+'\n\n'
            block+='[GPU workflow]('+route+'OPENCL_PROJECTION.md) · [Motion]('+route+'MOTION_PACKS.md) · [Install]('+route+'COMMUNITY_LOCAL_DELIVERY.md) · [75 declarations]('+route+'opencl-projection-capabilities-cli-0.1.20.json).\n\n<!-- /community-current -->'
            text,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,text,count=1,flags=re.S);assert n==1
            write(path,text)
    path=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=path.read_text('utf8')
    at=text.index('## CLI 0.1.5');head,tail=text[:at],text[at:]
    head=head.replace('alpha.4-local.17','alpha.4-local.18').replace('CLI 0.1.19','CLI 0.1.20').replace('final-r1/installed','final-r2/installed').replace('candidate-r1/bundle.zip','candidate-r2/bundle.zip')
    head=head.replace('6e779a6d241db07863773954d106a0a1a3bbd06b775c002c32e5430c192b77de',installation['archive_sha256'])
    head=head.replace('ad703ee0efe2e688b94de61a20eec6d22615e1b879651c8acea6c7011acdd456',installation['manifest_sha256'].removeprefix('sha256:'))
    head=head.replace('unified-skill-r20.zip','unified-skill-r21.zip').replace('community-unified-skill-package-0.1.19-r20.json','community-unified-skill-package-0.1.20-r21.json')
    tail=tail.replace('## CLI 0.1.19 当前交付 / Current delivery','## CLI 0.1.19 历史交付 / Historical delivery')
    addition='\n## CLI0.1.20 当前交付 / Current delivery\n\n209产品Python文件，69个Skill文件、17模块、r21独立kit。原生OpenCL crop/affine/sequence双线性/面积投影；CPU默认，GPU策略/配额/实际探测独立于编码。完整使用及队列/失败/恢复边界见 [GPU workflow](OPENCL_PROJECTION.md)，实际包摘要见 [固定交付](../releases/CLI_0.1.20_LOCAL.md)。\n'
    text=head+tail
    if addition not in text:text+=addition
    write(path,text)
    path=ROOT/'docs/product/CASES.md';text=path.read_text('utf8')
    if 'id="c28-opencl-projection"' not in text:
        text+='\n<a id="c28-opencl-projection"></a>\n\n## C28 原生GPU裁切、运镜与面积投影 / Native GPU projection\n\n'+summaries[0]+'\n\n[使用流程](OPENCL_PROJECTION.md) · [完整实测](../validation/OpenCL原生投影实测_2026-10-26.md) · [原图](../assets/opencl-projection-20261026-r1/original.png) · [MP4](../assets/opencl-projection-20261026-r1/projection.mp4) · [可编辑工程包](../assets/opencl-projection-20261026-r1/editable-projection.aevpkg.zip)\n\n![Actual installed OpenCL render / silent](../assets/opencl-projection-20261026-r1/projection.gif)\n\n自制FIELD NOTES图卡；480×270原生子画布，384×216/30fps/4秒输出，动态裁切、仿射、反向与arc_push。相同libx264编码；预览另用NVENC压缩，不混作投影性能。自然视听、连续播放/听审及完整目标保持开放。\n'
    write(path,text)
    for relative in ('docs/README.md','docs/product/PROJECTION_RENDERING.md','docs/product/AFFINE_RENDERING.md','docs/product/MOTION_PACKS.md'):
        path=ROOT/relative;text=path.read_text('utf8').replace('--hardware-encode auto','--hardware-encode off')
        link=('product/' if relative=='docs/README.md' else '')+'OPENCL_PROJECTION.md'
        addition='\n2026-10-26: [CLI0.1.20 native GPU projection / 原生GPU投影]('+link+') adds explicit OpenCL crop/affine/child-canvas samplers,actual-device/precision probes and failure/queue handling. Earlier CPU timing and scope remain historical; other effects stay CPU.\n'
        if addition not in text:text+=addition
        write(path,text)
    path=ROOT/'scripts/sync_capability_manuals.py';text=path.read_text('utf8').replace('0.1.19','0.1.20').replace('local.17','local.18').replace('r20 kit','r21 kit')
    text=text.replace('Animated crop and nested bilinear/area projection parameter reuse,','Native OpenCL crop/affine/child-canvas bilinear/area projection,')
    text=text.replace('[Projection workflow/preview](PROJECTION_RENDERING.md)','[GPU projection workflow/preview](OPENCL_PROJECTION.md)');write(path,text)
    table='\n'.join('| '+run+' | '+str(count)+' / '+str(count)+'，0 skip | [证据](evidence/opencl-projection-20261026-r1/tests/'+run+'/verification.json) |' for run,count in tests)
    evidence=f'''# OpenCL 原生投影实际交付（2026-10-26）

本地 CLI0.1.20 / alpha.4-local.18-final-r2 / r21 kit。209产品Python文件与ZIP安装版一致，唯一注册Skill为69文件/17模块。[使用与可编辑案例](../product/OPENCL_PROJECTION.md) · [实现契约](../specs/OpenCL原生投影实现契约_20261026.md)。所有G01–G38原关闭条件保持，未宣称完整剪映等价。

## 实际内核与设备

RTX3060，驱动595.95，Windows原生OpenCL3.0 CUDA，现有FFmpeg8.1，未调度虚拟化/模型服务或修改其他GPU任务。动态crop、固定画布仿射和原生子序列双线性/面积投影使用GPU；其余特效/字幕/混合保留CPU。NVENC为独立编码器，不混作GPU投影。本轮未新增模型推理。

每次GPU实际渲染读取设备/纹理限制，回读包括负零、DBL_MAX和最小次正规数的全部binary64系数位，以及gbrap8/Float32纹理样本位；已完成探测和渲染的完整日志保留。面积前缀按CPU逐行再逐列顺序，三Float32纹理分量运输binary64和，禁止fast-math/FMA。18项原生GPU测试覆盖1080p/4K仿射整帧、4K源缩至960×540的面积采样、奇数跨画幅、隐藏色、所有通道、重复/倒退PTS、嵌套反向、独立前向标记与单元交叠；大画幅是单帧像素验收，不是4K实时/长片验收。

## 最终安装包的六次交错测量

同一CLI0.1.20-final-r2、工程、输入与编码：640×360自制图卡，480×270原生子画布，384×216/30fps/4秒输出，动态crop/仿射/反向/arc_push/area。libx264 CRF0/yuv444p/PCM Float32，硬件编码关闭。只约束本测量进程及继承子进程为4逻辑CPU，未约束其他应用；非独占主机基准。完整CLI/预检/质量/编码计时，解码另计。

CPU三次：`{bench['timings_seconds']['cpu']}`秒；OpenCL三次：`{bench['timings_seconds']['opencl']}`秒。中位数 **{cpu:.6f}→{gpu:.6f}秒，{ratio:.3f}×**。六次全部120帧RGBA、帧时钟和完整4秒48kHz双声道Float32 PCM相同。图卡音轨静音，无人声/音乐听感结论。作者数据、素材、设置与Rights Ledger保持，正常追加六条render输出与日志。[原始命令、逐帧摘要、PCM及计时](evidence/opencl-projection-20261026-r1/benchmark-r2/verification.json)。

## 冻结源码与测试

| Scope | 实际方法 | 证据 |
|---|---|---|
{table}

各范围单独计数，不与历史总数、模型推理或独立Agent成功率混合。源码/安装同209文件；122项CLI使用源码执行，其冻结字节与最终安装版相同，其他范围明确调用最终安装包。18项GPU专项不静默跳过无设备情况。

## 失败、恢复、安装与Skill

[错误设备require失败、启动前取消、原设置恢复、实际队列与quality](evidence/opencl-projection-20261026-r1/controls-r1/verification.json)。恢复与队列输出各120帧/完整PCM与基线相同。恢复需原输入/输出设置指纹保持；换设备需新render。GPU投影拒绝显式结果复用，避免绕过逐作业设备核验。prefer仅执行前回退；运行中错误/超时/取消失败且不发布。

另将同一工程用OpenCL投影与NVENC联合实际输出，两个诊断状态均verified；完整解码120帧、完整PCM与基线相同。NVENC为有损yuv420p/2M编码，不与libx264无损像素或六次投影计时混合。

[最终ZIP安装](evidence/opencl-projection-20261026-r1/installation-final-r2/verification.json) · [实际注册](evidence/opencl-projection-20261026-r1/activation-final-r2/activation-and-registration.json) · [实际Skill GPU渲染](evidence/opencl-projection-20261026-r1/skill-r2/verification.json) · [独立r21 kit](evidence/opencl-projection-20261026-r1/kit-r2/verification.json)。Skill实际120帧/PCM相同，启动器仅调用固定安装版，无源码回落；17模块保持单入口。

## 案例媒体与保留的错误

[MP4/GIF完整解码与工程包导出](evidence/opencl-projection-20261026-r1/preview-r2/verification.json) · [媒体摘要](../assets/opencl-projection-20261026-r1/media-manifest.json) · [原图](../assets/opencl-projection-20261026-r1/original.png)。自制FIELD NOTES/MIT及Noto/OFL；台账未据此自动变成商业广告已批准。只做自动完整解码与记录的抽帧目检，没有连续播放/人类听审或自然质量验收。

[两张静帧观察](evidence/opencl-projection-20261026-r1/preview-r2/visual-observation.json)：原图图卡与中点实际GPU输出分别查看，标题及橙色环可见，中点画幅按设计裁切放大的图卡；这是助手静帧检查，不能替代人类审美验收。

初次系数探测发现负零丢失；[原失败](evidence/opencl-projection-20261026-r1/coefficient-failure-r1/failure.json)及原生输出保留。AVExpr除零不能识别负零符号，改用atan2象限检测，后续全部64位探测通过。首轮策略测试的测试夹具漏序列而失败，[原日志](evidence/opencl-projection-20261026-r1/tests/policy-development-r1/tests.log)保留；补齐夹具后通过，未改验收。第一次安装/六次测量作为中间构建[保留](evidence/opencl-projection-20261026-r1/benchmark-r1/verification.json)；补齐GPU作业结果复用门禁后另建final-r2，并重新执行六次，不混合计时。

首轮独立kit验证中，GPU dry-run已成功，但验收脚本错从data直接读取投影报告；实际结构为data.plan，导致脚本KeyError。[原失败](evidence/opencl-projection-20261026-r1/kit-r1/failure.json)保留。仅纠正验收脚本读取层级，在新的独立中文空格目录重做全部命令；未改产品或放宽检查。

其余特效/字幕、独立线性光Float32管线、多厂商/多设备、自然视听、完整4K/长片、全进程资源预算与公开新版发行继续开放。公开alpha.3标签/附件保持，未覆盖或强推。完整目标保持active。
'''
    write(ROOT/REPORT,evidence)
    kit_line=('r21独立kit / '+str(kit['bytes'])+' bytes / 96 files；SHA-256 `'+kit['sha256']+'`') if kit else 'r21独立kit / 96 files；摘要见匹配的版本化JSON'
    release=f'''# CLI0.1.20 本地交付 / Local delivery

2026-10-26，agent editor kit，`v0.1.0-alpha.4-local.18`最终构建`final-r2`。Native Windows x64/CPython3.13，209产品Python文件、69 Skill文件、1入口/17模块。公开alpha.3/CLI0.1.2与旧包保持；此为已安装本地交付，不覆盖公开发行附件。

新增原生OpenCL动态裁切、仿射与子画布双线性/面积投影，以及显式off/prefer/require策略、逐设备精度/纹理探测、工作栅格预算、kernel摘要、完整日志和队列/恢复集成。CPU默认；其他效果仍CPU，独立线性光浮点管线尚未GPU接入。现有500风格、359资源、字幕配音、GPU配音/翻译与17模块保持。

| Item | Under `E:/dev/sandbox/AI广告剪辑/` | SHA-256 |
|---|---|---|
| Native application ZIP,{installation['archive_bytes']} bytes | `local/agent-ffmpeg/v0.1.0-alpha.4-local.18/candidate-r2/bundle.zip` | `{installation['archive_sha256']}` |
| Bundle manifest | ZIP `manifest.json` | `{installation['manifest_sha256'].removeprefix('sha256:')}` |
| Installed runtime | `local/agent-ffmpeg/v0.1.0-alpha.4-local.18/final-r2/installed/` | [209-file proof](../validation/evidence/opencl-projection-20261026-r1/installation-final-r2/verification.json) |
| {kit_line} | [r21 ZIP](../skills/agent-editor-kit-community-unified-skill-r21.zip) | [metadata](../skills/community-unified-skill-package-0.1.20-r21.json) |

[Offline install/register](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Complete workflow/queue/editable case](../product/OPENCL_PROJECTION.md) · [17 Skill modules](../product/SKILLS.md) · [75 actual declarations](../product/opencl-projection-capabilities-cli-0.1.20.json) · [Native evidence]({REPORT.removeprefix('docs/') .replace('validation/','../validation/',1)})

```powershell
$aekSkills = if ($env:CODEX_HOME) {{ Join-Path $env:CODEX_HOME 'skills' }} else {{ Join-Path $env:USERPROFILE '.codex/skills' }}
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk validate --project $project
& $avk render --project $project --output $output --projection-acceleration prefer --projection-device 0.0 --projection-memory-mib 1024 --sequence-sampling area --sequence-memory-mib 1024 --hardware-encode off
```

先将project/output指向真实本地路径，或按完整使用页导入案例到新目录。使用匹配r21/运行ZIP；启动器验证摘要，不回落源码。现有驱动/FFmpeg、Python和可选模型另供；无Docker/WSL/虚拟环境、隐式下载或后台模型服务。仅RTX3060设备实测。4K是单帧像素对照，通用实时/长片、自然质量与全剪映等价仍开放。所有38原关闭条件保持。
'''
    write(ROOT/'docs/releases/CLI_0.1.20_LOCAL.md',release)
    print(json.dumps(dict(status='documented',readme_rows=146,prior_rows_preserved=138,goal_closures_preserved=38,ratio=ratio,final_kit=bool(kit)),ensure_ascii=False))

if __name__=='__main__':main()
