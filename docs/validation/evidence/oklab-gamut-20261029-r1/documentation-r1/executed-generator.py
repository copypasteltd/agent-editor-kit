"""Document actual source-phase OKLab implementation, never installed parity."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
BASELINE='faf0cab06a8336b157965f583ce16afe08781566'


def load(p):return json.loads(p.read_bytes())
def write(p,s):p.write_text(s,encoding='utf8',newline='\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--case',required=True);a=ap.parse_args()
 out=BASE/('documentation-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
 for folder,n in [('source-r3',62),('schema-r1',17)]:
  r=load(BASE/folder/'verification.json');assert r['status']=='passed' and r['tests']==n and r['frozen_equal']
 compat=load(BASE/'compat-r1/verification.json');assert compat['status']=='failed' and compat['tests']==352 and compat['failures']==1 and compat['errors']==compat['skipped']==0
 case=load(BASE/('case-'+a.case)/'verification.json');assert case['status']=='passed' and not case['installed_Skill_used']
 k4=load(BASE/'4k-r1/verification.json');assert k4['status']=='passed' and k4['all_pixels_compared']
 sys.path.insert(0,str(ROOT/'product/src'))
 # Capture authoritative CLI rather than construct a capability response.
 command=[sys.executable,'-E','-B','-X','utf8','-c',"import sys;sys.path.insert(0,'product/src');from ai_ad_editor.cli import main;raise SystemExit(main())",'capabilities']
 r=subprocess.run(command,cwd=ROOT,capture_output=True,check=True);(out/'capabilities.stdout.json').write_bytes(r.stdout);(out/'capabilities.stderr.txt').write_bytes(r.stderr)
 caps=json.loads(r.stdout);assert caps['ok'];(ROOT/'docs/product/oklab-gamut-capabilities-cli-0.1.51.json').write_bytes(r.stdout)
 guide='''# OKLab 色度边界映射 / OKLab 色度邊界映射 / OKLab chroma boundary reduction

**源码 CLI0.1.51；当前安装与统一Skill仍CLI0.1.50/local.48/r51。** 本功能尚未安装打包，不要给旧Skill传入新枚举或回退到源码。[本轮源码证据](../validation/OKLab色域映射源码实测_2026-10-29.md)。

在 `settings.pixel_pipeline.display_mapping` 或 `preview_mapping` 中明确设置：

```json
{"operator":"reinhard-luminance","source_peak_nits":1000,"target_peak_nits":100,"exposure_stops":0,"gamut_policy":"oklab-chroma"}
```

1. 使用原生 `float32-native-v1`，为素材、线性工作域和输出声明基色、传递函数与 `reference_white_nits`。
2. 正式SDR交付目标须是D65 BT.709，并将输出 `reference_white_nits` 设为 `target_peak_nits`；HDR作者工程使用 `preview_mapping` 生成单独SDR查看副本。
3. 验证工程，再执行既有 `preview frame/range`、`render`、`surface measure` 和工程包导出。源码开发入口与安装Skill分开；本页不是已安装操作承诺。
4. 将实际成片、完整映射配置、`perceptual_gamut` 与全帧 `colour_boundary_all_frames`/transport计数一起交付，比较原图与裁切方案后选型。

转换先将工作线性RGB变换到BT.709/D65，保留负分量，再按非负CIE Y执行明确的modified-Reinhard亮度肩部。之后在OKLab中固定感知明度L和色相方向，将a/b统一乘以0..1的比例，24次二分选择RGB单位立方体内的候选。不是逐通道RGB裁切；不是保持CIE Y。已经位于目标域内的肩部结果保持原字节，alpha位保持。

`gamut_pixels_mapped`、`gamut_chroma_reduced_pixels`、`gamut_lightness_to_black_pixels`、`gamut_lightness_to_white_pixels`按帧统计并在正式交付中汇总。L<=0映为黑；越界像素L>=1-1e-7映为白，后者是公开矩阵有限精度保护，明确计数，不宣称端点色相/明度保留。负CIE Y、非有限输入、错误目标、超预算和取消直接失败，不静默修正。旧reject/clip路径保持其原语义与默认值。

每块最多65536像素，Float64计算后写回Float32，CPU执行并在二分循环内响应取消；工作区估算不是全进程RSS/VRAM。正式渲染及中间包依赖摘要包含新实现。当前不是GPU色彩内核、软拐点压缩、CSS local-MINDE、ACES、BT.2390、动态HDR或显示器校准，也不等于完整剪映效果验收。

矩阵来源：[Björn Ottosson OKLab 原文](https://bottosson.github.io/posts/oklab/)，使用2021-01-25线性sRGB系数（原作者提供public-domain/MIT许可）；二分边界搜索为本项目实现。这里只借鉴坐标变换，不把本项目搜索称为原作者的完整色域映射算法。

繁體：新增明確選用的OKLab固定明度/色相縮色度；僅D65 BT.709目標，CPU分塊，端點與全幀計數可查。已安裝Skill尚未升級，完整自然HDR/藝術品質仍待驗收。

English: Source CLI0.1.51 adds explicit `oklab-chroma` for BT.709/D65 SDR trims and previews. It reduces chroma along a fixed OKLab lightness/hue ray, with counted black/near-white endpoints. This preserves perceptual L, not CIE Y. CPU tiled execution; no soft knee, ACES or monitor-certification claim. Installed Skill remains CLI0.1.50 pending matching delivery.
'''
 write(ROOT/'docs/product/OKLAB_GAMUT.md',guide)
 public='docs/assets/oklab-gamut-20261029-'+a.case
 snippets=[
 ('README.md','源码 CLI0.1.51 新增明确可选的 OKLab 保感知明度/色相缩色度，用于 HDR→BT.709 SDR 交付及预览。当前安装 Skill 仍 CLI0.1.50/local.48/r51，新安装包与独立安装验收待完成。','专项62/62；兼容初跑351/352，文档Schema副本同步后专项17/17通过；C61两种真实成片、全帧独立参考和工程包完整音画重放留证。数值图卡不代替自然画面与物理HDR监看验收。'),
 ('README.zh-TW.md','原始碼 CLI0.1.51 新增明確選用的 OKLab 保感知明度/色相縮色度，用於 HDR→BT.709 SDR交付及預覽。目前安裝Skill仍CLI0.1.50/local.48/r51，新安裝套件與獨立驗收待完成。','專項62/62；相容初跑351/352，文件Schema副本同步後專項17/17通過；C61真實成片、全幀獨立參考與工程包完整音畫重放留證。數值圖卡不代替自然畫面及物理HDR監看驗收。'),
 ('README.en.md','Source CLI0.1.51 adds opt-in OKLab lightness/hue-preserving chroma reduction for HDR-to-BT.709 SDR delivery and previews. Installed Skill remains CLI0.1.50/local.48/r51; matching installation and independent kit acceptance are pending.','Source-specific62/62 passes; compatibility initially passes351/352, then the documented Schema copy is synchronized and Schema17/17 passes. C61 contains real encoded comparisons, an independent full-frame oracle and complete editable-package pixel/PCM replay. Diagnostic charts do not certify natural-image aesthetics or physical HDR monitoring.')]
 for name,summary,validation in snippets:
  p=ROOT/name;s=p.read_text('utf8');oldrows=[l for l in s.splitlines() if re.match(r'^\| R\d+ \|',l)];assert len(oldrows)==340
  banner='\n<!-- oklab-gamut-source -->\n\n**'+summary+'**\n\n[Workflow](docs/product/OKLAB_GAMUT.md) · [Source release](docs/releases/CLI_0.1.51_SOURCE.md) · [C61](docs/product/CASES.md#c61-oklab-gamut) · [Evidence](docs/validation/OKLab色域映射源码实测_2026-10-29.md)\n\n![Left clip / right OKLab — actual SDR outputs]('+public+'/comparison.gif)\n\n'+validation+'\n\n<!-- /oklab-gamut-source -->\n'
  mark='<!-- native-hdr-media-current -->';assert mark in s;s=s.replace(mark,banner+'\n'+mark,1)
  rows=[f'| R341 | Source CLI0.1.51 OKLab/native HDR measurement | 62/62; 0fail/error/skip; source only | 2026-10-29 | [raw](docs/validation/evidence/oklab-gamut-20261029-r1/source-r3/verification.json) | CPU BT709/D65; not installed |',
        f'| R342 | Source CLI0.1.51 compatibility | 351/352 initially; documented-Schema mismatch fixed; Schema17/17 rerun passes | 2026-10-29 | [raw](docs/validation/evidence/oklab-gamut-20261029-r1/compat-r1/verification.json) | natural quality/long-form pending |',
        f'| R343 | C61 actual clip/OKLab encoded comparison + package replay | 10frames/384x216; full YUV/native reference; complete PCM | 2026-10-29 | [raw](docs/validation/evidence/oklab-gamut-20261029-r1/case-{a.case}/verification.json) | source execution; SDR diagnostic; failed r1/r2 preserved |',
        f'| R344 | Source OKLab 4K operator | 8294400 pixels vs independent oracle; max linear RGB error {k4["maximum_linear_RGB_error"]:.9g}; {k4["operator_elapsed_seconds"]:.3f}s | 2026-10-29 | [raw](docs/validation/evidence/oklab-gamut-20261029-r1/4k-r1/verification.json) | one CPU surface; nonexclusive timing; not encoded/real-time/long-form |']
  last=oldrows[-1];assert s.count(last)==1;s=s.replace(last,last+'\n'+'\n'.join(rows),1)
  additions={'README.md':' 源码51另增OKLab保感知明度/色相缩色度；安装50尚未包含。',
             'README.zh-TW.md':' 原始碼51另增OKLab保感知明度/色相縮色度；安裝50尚未包含。',
             'README.en.md':' Source51 adds OKLab lightness/hue chroma reduction; installed50 does not include it yet.'}
  lines=s.splitlines()
  for i,line in enumerate(lines):
   if line.startswith('| F66 |'):
    cells=line.split('|');cells[3]+=additions[name];lines[i]='|'.join(cells)
  s='\n'.join(lines)+'\n'
  assert [l for l in s.splitlines() if re.match(r'^\| R\d+ \|',l)][:340]==oldrows;write(p,s)
 write(ROOT/'docs/releases/CLI_0.1.51_SOURCE.md','''# CLI0.1.51 源码阶段 / 原始碼階段 / source phase

新增显式 `gamut_policy=oklab-chroma`，贯通正式SDR渲染、HDR的SDR预览、光量测量、可编辑工程包和全帧色域计数。算法、完整配置及边界见[功能使用说明](../product/OKLAB_GAMUT.md)，实际输出见[C61](../product/CASES.md#c61-oklab-gamut)。

**已安装版本仍CLI0.1.50/local.48/r51。** 本源码版本没有可宣称已验收的离线安装包；不要修改旧Skill的版本针或让其回退源码。下一轮需重新构建ZIP、冻结277份产品文件、安装核验、注册统一Skill并独立解压测试匹配kit。

最终源码专项62/62；兼容初跑351/352，文档Schema副本同步后Schema17/17通过，分别留证，三次作者渲染（clip、OKLab、包重放），独立RGB16输入与编码后YUV完全一致，源/成片/重放PCM一致。未新增神经模型或GPU色彩内核。旧reject/clip语义保留。[完整实测及失败记录](../validation/OKLab色域映射源码实测_2026-10-29.md)。

繁體：目前僅原始碼功能驗收；CPU分塊、D65 BT.709、非軟拐點/ACES/物理監看，安裝版和自然畫面驗收待完成。

English: Source-only addition; the installed unified Skill remains CLI0.1.50. Explicit CPU-tiled BT.709/D65 OKLab chroma boundary reduction, with counted endpoints and full-frame receipts. Matching offline delivery, natural-image quality, ACES/dynamic HDR and physical-monitor validation remain open.
''')
 report=f'''# OKLab 色域映射源码实测（2026-10-29）

本轮是**源码 CLI0.1.51**，277个产品Python文件。安装仍CLI0.1.50/local.48/r51，统一Skill未回退源码；不新发公开Release。G08完整关闭条件保留。

| 编号 | 实际核验 | 证据及边界 |
| --- | --- | --- |
| T01 | 最终源码专项62/62，0失败/错误/跳过 | [原始记录](evidence/oklab-gamut-20261029-r1/source-r3/verification.json)；含13项新专项、既有HDR/光量测试，不能与兼容组重复累计 |
| T02 | 源码兼容初跑351/352，1失败/0错误/0跳过；同步文档Schema后17/17专项通过 | [记录](evidence/oklab-gamut-20261029-r1/compat-r1/verification.json)；ICC/HLG/色适应/色彩/渲染/预览/工程包/LUT/曲线/队列；失败仅为文档Schema副本；[修复后17项](evidence/oklab-gamut-20261029-r1/schema-r1/verification.json)，未重跑全352项 |
| T03 | 196个独立标量颜色，31个色相保留点 | [receipts](evidence/oklab-gamut-20261029-r1/source-r3/receipts.json)；独立公开逆变换系数与48次标量搜索，不调用产品映射 |
| T04 | C61真实裁切/OKLab成片与工程包重放 | [实际记录](evidence/oklab-gamut-20261029-r1/case-{a.case}/verification.json)；10帧、384×216，全部YUV平面检查，独立原生参考差{case['native_reference_maximum_code_difference']}code；解析YCbCr最大误差{case['maximum_10bit_code_error']:.9f}code |
| T05 | 完整音轨 | 源PCM、原成片、重放成片共{case['PCM_bytes']}bytes逐字节一致；不等于人类听审 |
| T06 | 4K算子全部像素独立核对 | [记录](evidence/oklab-gamut-20261029-r1/4k-r1/verification.json)；8294400像素，最大误差{k4['maximum_linear_RGB_error']:.9g}，CPU单表面{k4['operator_elapsed_seconds']:.3f}s（非独占）；非4K成片/实时/长片验收 |

兼容组唯一失败是公开文档Schema副本未同步；产品实现字节未改，补副本后Schema17/17通过。首轮source-r1保留Schema摘要未同步的10处拒绝；source-r2修正后61/61。随后补近白精度保护与测试，最终source-r3为62/62。case-r1原解析门槛2code失败，实际误差2.279996982code；case-r2原生参考只做zscale、未经过成片编码器，仍差2code。最终明确测量边界：先核对独立RGB16全部输入字节，再让独立输入经过相同zscale和编码器核对全部YUV码值（实际差0）。解析3code与原生1code门禁同时保留，未只放宽解析门槛。

实际输出为原创CC0合成图卡；并排GIF左为逐通道clip，右为OKLab方案。[GIF](../assets/oklab-gamut-20261029-{a.case}/comparison.gif)与[MP4](../assets/oklab-gamut-20261029-{a.case}/comparison.mp4)均由实际成片生成。[静态目检与帧数记录](evidence/oklab-gamut-20261029-r1/case-{a.case}/preview-review/verification.json)确认GIF10帧/1000ms、MP4 10帧/10FPS；未执行人类连续播放、听审或物理HDR验收。无新模型推理、无Docker/WSL、无浏览器窗口。

仍待：安装包/Skill同步、自然肤色与多光源/连续镜头、长片/4K性能、感知软拐点/ACES/动态HDR和物理监看。详细算法、参数与限制见[功能说明](../product/OKLAB_GAMUT.md)。
'''
 write(ROOT/'docs/validation/OKLab色域映射源码实测_2026-10-29.md',report)
 p=ROOT/'docs/product/CASES.md';s=p.read_text('utf8');assert 'id="c61-oklab-gamut"' not in s
 s+=f'''\n<a id="c61-oklab-gamut"></a>

## C61 · Source CLI0.1.51 OKLab色域映射真实对照 / 實際對照 / actual comparison

**源码执行，非已安装Skill。** 原创CC0 BT.2020线性图卡，10帧/10FPS/1秒/384×216，具有变化亮度、原色/间色/灰阶和随机色块。明确203nit工作单位、100nit BT.709/sRGB输出，两次同源真实渲染仅改变gamut_policy：左clip，右oklab-chroma。

![Actual encoded comparison](../assets/oklab-gamut-20261029-{a.case}/comparison.gif)

全部829440像素/三YUV平面与独立xy矩阵/标量OKLab/48次搜索参考核对；解析YCbCr最大差{case['maximum_10bit_code_error']:.9f}code，独立RGB16经原生zscale参考最大差{case['native_reference_maximum_code_difference']}code。工程包保留配置，重放全部像素及源/原片/重放完整PCM一致（{case['PCM_bytes']}bytes）。全帧事件记录：[raw](../validation/evidence/oklab-gamut-20261029-r1/case-{a.case}/verification.json)。

[clip MKV](../assets/oklab-gamut-20261029-{a.case}/clip.mkv) · [OKLab MKV](../assets/oklab-gamut-20261029-{a.case}/oklab.mkv) · [MP4](../assets/oklab-gamut-20261029-{a.case}/comparison.mp4) · [PNG](../assets/oklab-gamut-20261029-{a.case}/comparison.png) · [editable package](../assets/oklab-gamut-20261029-{a.case}/editable-oklab.aevpkg.zip) · [sources](../assets/oklab-gamut-20261029-{a.case}/SOURCE.json)

繁體：固定感知明度/色相縮色度，黑白端點另計，CPU/D65 BT.709；仍待自然畫面、安裝版及物理監看。

English: Real source-phase encoded comparisons and full editable-package replay; CPU-only BT.709/D65 chroma boundary reduction. Preserve OKLab L/hue except counted endpoints, not CIE Y. Diagnostic chart, not natural quality, installed delivery or physical monitor acceptance.
''';write(p,s)
 p=ROOT/'docs/product/GOAL_GAPS_20261025.md';s=p.read_text('utf8');lines=s.splitlines()
 for i,line in enumerate(lines):
  if line.startswith('| G08 |'):
   parts=line.split('|');parts[3]+=' CLI0.1.51源码新增OKLab固定感知明度/色相色度边界映射，真实SDR成片/完整包重放留证；安装Skill仍50。';lines[i]='|'.join(parts)
 write(p,'\n'.join(lines)+'\n')
 p=ROOT/'docs/README.md';s=p.read_text('utf8');s=s.replace('\n','\n\n源码CLI0.1.51：[OKLab色域映射](product/OKLAB_GAMUT.md) / [实测](validation/OKLab色域映射源码实测_2026-10-29.md)。安装仍CLI0.1.50，匹配新包待交付。\n',1);write(p,s)
 for suffix,summary,_ in snippets:
  lang=suffix[len('README'):-len('.md')]
  p=ROOT/('docs/product/CAPABILITIES'+lang+'.md');s=p.read_text('utf8');s+='\n\n源码CLI0.1.51 / Source only: [OKLab gamut](OKLAB_GAMUT.md)。安装声明仍以CLI0.1.50为准；新源码能力见[实际capabilities](oklab-gamut-capabilities-cli-0.1.51.json)。\n';write(p,s)
 result=dict(status='documented',source_version='0.1.51',installed_version='0.1.50',R=344,original_rows_retained=340,whole_goal_complete=False)
 write(out/'verification.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
