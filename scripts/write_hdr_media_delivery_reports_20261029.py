"""Write factual local-release, C60 and acceptance reports from successful installed receipts."""
from pathlib import Path
import argparse,json
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-media-measure-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);a=ap.parse_args();assert a.case.replace('-','').isalnum()
install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/('installed-case-'+a.case)/'verification.json')
assert case['status']=='passed' and case['installed_skill_used'] and install['cli_version']=='0.1.50'
for name,n in [('installed-r1',29),('installed-boundary-r1',42),('installed-compat-r1',352)]:
 v=load(BASE/name/'verification.json');assert v['status']=='passed' and v['tests']==n
media='../assets/native-hdr-media-installed-20261029-'+a.case+'/'
release="""# CLI 0.1.50 本地发行 / Local release

本地版本 **v0.1.0-alpha.4-local.48**，统一入口 **`$agent-ffmpeg-local-editor`**，17个内部模块、89个Skill文件。公开GitHub alpha.3/CLI0.1.2的标签和附件保持原字节；本记录为新本地构建，不是新的公开Release。

新增 `surface measure-media` 编码后成片光量核验，保留既有编码前 `surface measure`。实际作者渲染与解码后数字光量的边界必须分开；两者都不是物理显示器实测。[完整使用说明](../product/HDR_MEDIA_MEASUREMENT.md)。

## 本地包与调用

| 编号 | 文件或状态 | 实际值 |
| --- | --- | --- |
| L01 | 基础运行ZIP | `local/agent-ffmpeg/v0.1.0-alpha.4-local.48/candidate-r1/bundle.zip` |
| L02 | ZIP bytes | ARCHIVE_BYTES |
| L03 | ZIP SHA-256 | `ARCHIVE_SHA` |
| L04 | 清单摘要 | `MANIFEST_SHA` |
| L05 | 已安装目录 | `local/agent-ffmpeg/v0.1.0-alpha.4-local.48/final-r1/installed` |
| L06 | 统一Skill kit | [r51 ZIP](../skills/agent-editor-kit-community-unified-skill-r51.zip) / [摘要](../skills/community-unified-skill-package-0.1.50-r51.json) |

以上相对路径以 `E:/dev/sandbox/AI广告剪辑/` 为根。已有原生Windows x64、CPython3.13、FFmpeg/ffprobe及GPU任务对应的本地依赖；不调用Docker、WSL、虚拟环境、全局pip或隐式模型下载。新功能本身不需要新神经模型。

```powershell
$aekSkill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aekSkill version
& $aekSkill surface measure-media --help
& $aekSkill surface measure-media --project PROJECT --input renders/master.mkv --signal-json SIGNAL.json --pixel-family yuv --yuv-matrix bt2020nc --yuv-range limited --chroma-location left --scan progressive --dry-run
```

将 `PROJECT` 和 `SIGNAL.json` 替换为实际绝对路径，输入成片需位于工程内。PQ信号JSON例：`{"primaries":"bt2020","transfer":"pq-st2084","reference_white_nits":203}`。核对计划后去掉 `--dry-run` 进行原生逐帧读取。默认越界失败；明确接受截断时才加 `--range-policy clip`，并将裁切计数随报告交付。HLG须明确显示峰值、gamma及需要时的黑位；RGB成片不带YCbCr参数。

源文件或信号发生变化后重新计划，取消使用工程内 `--cancel-file`。未知帧时长不按FPS猜测，曝光缺口/重叠直接报告。保留完整JSON中的源SHA、解码RGBA/时钟摘要、MaxRGB/CIE Y、原生解码进程退出与线程回收结果。

迁移至新目录时，按[完整离线安装流程](../product/COMMUNITY_LOCAL_DELIVERY.md)校验ZIP和清单、原生安装、加载可选模型包、激活同版本runtime、注册单入口。r51必须匹配本地.48应用，不能套用alpha.3或旧r50运行包。

## 本轮核验和限制

安装专项29/29、边界42/42、兼容352/352分别通过，276份Python源码/安装相同。C60由实际C盘发现联接的Skill完成PQ/HLG H.265 Main10 4:2:0渲染、完整独立像素/光量核对及HLG工程包重放；完整PCM也相同。四个既有语音/翻译模型包已核验并保留配置，本轮没有新增模型推理或下载。

C60图表为CC0合成数值诊断，不代替自然画面艺术验收。实际4:2:0重建存在越界；失败的reject记录保留，后续clip结果明确带计数。GIF/MP4仅为作者时间线的显式SDR查看副本。4K/长片/更多编解码、动态HDR、完整ACES/感知色域/自然HDR监看及完整剪映等价仍未完成。

繁體：本地CLI0.1.50已安裝並註冊為單一Skill；新增解碼後成片光量複核，須明確色彩與原生時鐘，不自動寫入SEI。請配對r51及本地.48套件；公開alpha.3仍為舊版。[實測](../validation/编码后成片安装与跨编码实测_2026-10-29.md)。

English: CLI0.1.50 is installed as local.48 and exposed through one unified Skill with17modules/89files.Match the r51kit to this bundle;public alpha.3 remains unchanged.Use explicit signal/native-clock semantics and retain range counts.Post-codec digital metering does not certify a physical HDR display or complete CapCut parity.[Evidence](../validation/编码后成片安装与跨编码实测_2026-10-29.md).
"""
for old,new in [('ARCHIVE_BYTES',str(install['archive_bytes'])),('ARCHIVE_SHA',install['archive_sha256']),('MANIFEST_SHA',install['manifest_sha256'])]:release=release.replace(old,new)
write('docs/releases/CLI_0.1.50_LOCAL.md',release)
text='\n\n<a id="c60-post-codec-hdr420"></a>\n\n## C60 · 编码后HDR420 / 解碼後HDR420 / Post-codec HDR420\n\n'
text+='Actual registered CLI0.1.50/local.48 unified Skill,one entry/17modules/89files.Native Windows;no source fallback or new neural-model forward.CC0 C59 synthetic chart and stereo tones are imported as an editable project;the actual native renderer produces separate PQ and HLG (1000nit peak,gamma1.2,explicit1nit black) H.265 Main10 limited BT2020,left-sited progressive4:2:0 movies at640×360,48frames,12fps.\n\n'
text+='The independent oracle imports no product colour/meter modules.It decodes complete native10bit planes,reconstructs left-sited chroma using two-pass NumPy interpolation,and independently applies PQ/HLG/BT2020 Y equations.The complete Float32 RGBA and native PTS/duration digests match for both11059200-pixel movies.Maximum peak/average/minimum nit error is below1e-7.HLG package import/rerender preserves all decoded RGB/clock bytes and complete1536000-byte stereoFloat32PCM.\n\n'
text+='| Movie | MaxRGB peak nit | CIE Y peak nit | Negative RGB components | Over-one components | Oracle max error nit |\n| --- | --- | --- | --- | --- | --- |\n'
for label,r in case['cases'].items():text+='| '+label+' | '+str(r['peak_pixel']['maxrgb']['nits'])+' | '+str(r['peak_pixel']['cie_y']['nits'])+' | '+str(r['range_counts']['negative_components'])+' | '+str(r['range_counts']['over_one_components'])+' | '+str(r['maximum_metric_error_nits'])+' |\n'
text+='\nBoth reject-mode calls fail specifically at the out-of-range RGB boundary;the successful explicit clip runs retain all component counts.No automatic metadata rewrite or gamut repair is inferred.Native millisecond exposure totals3.984s while the source span is4s;the16 one-millisecond gaps are reported rather than filled.\n\n'
text+='![Actual authored-timeline SDR preview]('+media+'author-SDR-preview.gif)\n\n'
text+=' · '.join('['+label+']('+media+name+')' for label,name in [('PQ420 master','pq420.mkv'),('HLG420 master','hlg420.mkv'),('PQ measurement','pq420-measurement.json'),('HLG measurement','hlg420-measurement.json'),('Actual SDR MP4','author-SDR-preview.mp4'),('Actual SDR PNG','author-SDR-frame.png'),('Editable HLG package','editable-hlg420.aevpkg.zip'),('Provenance','SOURCE.json'),('Media hashes','media-manifest.json')])+'\n\n'
text+='The preview is an explicit Reinhard SDR view of the authored working timeline,not a decoded-output420 comparison or physical HDR monitor.GIF24frames/4000ms;MP448frames/4s;PNG reviewed statically by the agent.No continuous-playback,human-listening,natural-image or full-HDR-quality acceptance.See [actual checks](../validation/evidence/native-hdr-media-measure-20261029-r1/installed-case-'+a.case+'/checks.json).\n'
assert 'c60-post-codec-hdr420' not in (ROOT/'docs/product/CASES.md').read_text('utf8')
old=(ROOT/'docs/product/CASES.md').read_text('utf8');before,c59=old.split('<a id="c59-native-hdr-measurement"></a>',1)
c59=c59.replace('384000 nonzero PCM scalars','384000 total PCM scalars')
c59+='\nC59 count correction (C60 follow-up):the same registered source tones decode to384000 total Float32 scalars,383999 nonzero.The earlier nonzero count overstated by one;original historical R331/receipts remain archived.See [source/original/replay PCM recount](../validation/evidence/native-hdr-media-measure-20261029-r1/installed-case-'+a.case+'/replay-review-r1/verification.json).\n'
write('docs/product/CASES.md',before+'<a id="c59-native-hdr-measurement"></a>'+c59+text)
report='# 编码后成片本地安装与跨编码实测（2026-10-29）\n\n'
report+='CLI0.1.50/local.48由完整离线ZIP原生安装并注册到单一Skill；r51独立kit与同一运行包配对。源码阶段记录继续保留：[上一轮](编码后成片光量核验_2026-10-29.md)。本轮没有改动276份已冻结产品源码，也没有重用上轮通过数冒充安装核验。\n\n'
report+='| 编号 | 实际执行 | 结果与证据 | 边界 |\n| --- | --- | --- | --- |\n'
for i,(name,n,description) in enumerate([('installed-r1',29,'测量专项'),('installed-boundary-r1',42,'原生像素/视频/schema边界'),('installed-compat-r1',352,'HDR/ICC/预览/中间包/常规渲染/队列兼容')],1):
 report+='| T0'+str(i)+' | '+description+' | '+str(n)+'/'+str(n)+'，0 failures/errors/skips；[原记录](evidence/native-hdr-media-measure-20261029-r1/'+name+'/verification.json) | 与源码和历史轮次分列，不重复累计。 |\n'
report+='| T04 | C60真实注册Skill的PQ/HLG H.265420、独立oracle及可编辑包重放 | '+str(case['checks'])+'个实际检查通过；[原记录](evidence/native-hdr-media-measure-20261029-r1/installed-case-'+a.case+'/verification.json) | 每条48帧/11059200像素；明确裁切、完整PCM；非物理监看。 |\n'
report+='| T05 | 实际PNG静态检查、MP4/GIF元数据检查 | [原记录](evidence/native-hdr-media-measure-20261029-r1/installed-case-'+a.case+'/preview-review/verification.json) | 无人类连续播放或听审。 |\n'
report+='| T06 | 独立r51解包/清单/配置/联接注册/新命令实际调用 | [原记录](evidence/native-hdr-media-measure-20261029-r1/kit-r1/verification.json) | 1入口/17模块/89Skill文件，无源码回落，不改变真实C盘发现联接。 |\n'
report+='\n[实际C60全部数字、媒体与限制](../product/CASES.md#c60-post-codec-hdr420) · [安装流程](../releases/CLI_0.1.50_LOCAL.md)。\n\n'
report+='PQ和HLG默认reject均因真实RGB越界失败；保留原始JSON和stderr，只有确认错误为HDR_MEASURE_RANGE才显式clip重跑。完整解码像素摘要在裁切前计算，计数覆盖整帧；独立参考使用相同声明的明确clip解释。PQ出现674289个负分量；HLG出现732015个负分量及39个超一分量。不能隐藏这些数量后把结果描述成无裁切的色彩保真验收。\n\n'
report+='独立解码和公式不是物理亮度测量。当前原生时间基1/1000，跨度4秒，曝光总和3.984秒与16处1ms缺口原样报告；不按12fps猜测或修改源时钟。\n\n'
report+='补充复核：实际HLG测量重放的完整RGBA、时钟、逐帧度量摘要及全部峰值/均值/范围字段均相同；源WAV、原成片与重放的1536000字节PCM逐字节一致，384000个标量中383999非零。[补充原记录](evidence/native-hdr-media-measure-20261029-r1/installed-case-'+a.case+'/replay-review-r1/verification.json)。历史C59/R331将384000个总标量误写为全部非零，差一；原历史行保留，当前说明在此纠正，不据此推断其他历史案例。\n\n'
report+='原始CC0来源及所有媒体字节摘要公开；新增GIF24帧/4000ms、MP448帧/4s、PNG640×360。该预览显示作者工作时间线的Reinhard SDR查看副本，不代表解码后HDR420比较。HLG工程包完整PCM1536000字节重放一致，本轮不做听审。\n\n'
report+='既有四个语音/翻译包激活时按摘要核验，无新模型下载、全局安装或模型forward。全程原生Windows，没有Docker/WSL/容器/虚拟环境，没有打开GUI浏览器tab。38项原目标关闭条件保持，[完整差距](../product/GOAL_GAPS_20261025.md)。\n'
write('docs/validation/编码后成片安装与跨编码实测_2026-10-29.md',report)
print('Local release, C60 and factual installed acceptance reports written.')
