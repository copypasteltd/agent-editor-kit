"""Synchronize trilingual installed-delivery docs without deleting historical evidence."""
from pathlib import Path
import argparse,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-media-measure-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def append_row(s,row):
 m=list(re.finditer(r'^\| R\d+ \|.*$',s,re.M))[-1];return s[:m.end()]+'\n'+row+s[m.end():]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--case',required=True);a=ap.parse_args();assert all(x.replace('-','').isalnum() for x in (a.run,a.case))
 out=BASE/('documentation-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
 install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/('installed-case-'+a.case)/'verification.json')
 assert install['status']=='installed-and-byte-verified' and install['source_file_count']==276 and case['status']=='passed' and case['installed_skill_used']
 counts={}
 for name,n in [('installed-r1',29),('installed-boundary-r1',42),('installed-compat-r1',352)]:
  v=load(BASE/name/'verification.json');assert v['status']=='passed' and v['tests']==n and v['failures']==v['errors']==v['skipped']==0;counts[name]=n
 media='docs/assets/native-hdr-media-installed-20261029-'+a.case+'/'
 capture='docs/product/hdr-media-measure-capabilities-cli-0.1.50.json';(ROOT/capture).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
 caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==88
 descriptions={
 '':'新增**编码后原生成片光量复核**：实际原生PTS/曝光、明确RGB与YCbCr解释、MaxRGB/CIE Y、越界与裁切计数、完整解码像素/时钟摘要。保留编码前 `surface measure`，新增 `surface measure-media`，两种测量边界分别报告。',
 '.zh-TW':'新增**解碼後原生成片光量複核**：實際原生PTS／曝光、明確RGB與YCbCr解釋、MaxRGB／CIE Y、越界與裁切計數、完整解碼像素／時鐘摘要。保留編碼前 `surface measure`，新增 `surface measure-media`，兩種測量邊界分別報告。',
 '.en':'Added **native post-codec media light metering**:original PTS/exposures,explicit RGB/YCbCr interpretation,separate MaxRGB/CIE Y,range/clipping counts,and full decoded-pixel/clock digests.`surface measure` remains the pre-codec boundary;`surface measure-media` checks the encoded file.'}
 detail={
 '':'安装版29项专项、42项边界回归与352项兼容回归分别通过。C60由真实本地统一Skill执行PQ/HLG H.265 Main10 4:2:0渲染；两条48帧成片逐像素独立核验，HLG可编辑工程包重放像素与完整PCM一致。GIF为作者时间线的明确SDR查看副本，非编码后或物理HDR监看验收。',
 '.zh-TW':'安裝版29項專項、42項邊界回歸與352項相容回歸分別通過。C60由真實本地統一Skill執行PQ／HLG H.265 Main10 4:2:0算繪；兩條48影格成片逐像素獨立核驗，HLG可編輯專案重播像素與完整PCM一致。GIF為作者時間線的明確SDR檢視副本，非解碼後或實體HDR監看驗收。',
 '.en':'Installed focused29,boundary42 and compatibility352 tests pass separately.C60 uses the actual registered unified Skill to render PQ/HLG H.265 Main10 4:2:0;both48-frame movies match independent pixel/light oracles.HLG package replay preserves decoded pixels and complete PCM.The GIF is an explicit authored-timeline SDR view,not encoded-output or physical HDR acceptance.'}
 frows={
 '':'| F75 | 编码前后HDR光量与转换收据 | 明确nit；实际作者RGB16输入与编码后原生RGB/YCbCr分别测量，MaxRGB/CIE Y、位置/时长、完整像素与时钟摘要、全帧裁切账本。 | `native_hdr_light_measurement; surface measure; surface measure-media; surface export; render` | CPU测量；不推断显示器、不自动写SEI；原生曝光缺口/重叠不填补。 |',
 '.zh-TW':'| F75 | 編碼前後HDR光量與轉換收據 | 明確nit；實際作者RGB16輸入與解碼後原生RGB／YCbCr分別測量，MaxRGB／CIE Y、位置／時長、完整像素與時鐘摘要、全影格裁切帳本。 | `native_hdr_light_measurement; surface measure; surface measure-media; surface export; render` | CPU測量；不推斷顯示器、不自動寫SEI；原生曝光缺口／重疊不填補。 |',
 '.en':'| F75 | Pre/post-codec HDR light and colour receipts | Explicit nits;separate authored RGB16 input/native decoded RGB/YCbCr measurements;MaxRGB/CIE Y,locations/durations,pixel/clock digests and all-frame clipping ledgers. | `native_hdr_light_measurement; surface measure; surface measure-media; surface export; render` | CPU meter;no inferred monitor or automatic SEI;native exposure gaps/overlaps not filled. |'}
 srows={
 '':'| S30 | 编码前后光量诊断与全帧色彩审计 | 只读原生时间线与成片、可取消分块测量、RGB16/解码RGBA与原生时钟摘要、所有帧转换收据及进程线程回收。 | 既有FFmpeg/NumPy与可选OpenCL；不下载模型。 | `surface measure; surface measure-media; surface export; render` | 明确色彩/逐行YCbCr与正原生时长；部分有效区域不代表整片全画布；768MiB算子估算非总RSS。 |',
 '.zh-TW':'| S30 | 編碼前後光量診斷與全影格色彩審計 | 唯讀原生時間線與成片、可取消分塊測量、RGB16／解碼RGBA及原生時鐘摘要、全部轉換收據與程序執行緒回收。 | 既有FFmpeg／NumPy與選用OpenCL；不下載模型。 | `surface measure; surface measure-media; surface export; render` | 明確色彩／逐行YCbCr及正原生時長；部分有效區域不代表完整畫布；768MiB算子估算非總RSS。 |',
 '.en':'| S30 | Pre/post-codec light diagnostics and colour audit | Readonly native timeline/media,cancellable tiled metering,RGB16/decoded RGBA/native-clock digests,all-frame receipts and owned-process/thread cleanup. | Existing FFmpeg/NumPy,optional OpenCL;no model downloads. | `surface measure; surface measure-media; surface export; render` | Explicit colour/progressive YCbCr and positive native durations;partial regions not full-canvas certification;768MiB operator estimate not total RSS. |'}
 evidence='docs/validation/evidence/native-hdr-media-measure-20261029-r1/'
 for suffix in ('','.zh-TW','.en'):
  p='README'+suffix+'.md';s=read(p);oldrows=[l for l in s.splitlines() if re.match(r'^\| R\d+ \|',l)];assert len(oldrows)==335
  s='\n'.join(l for l in s.splitlines() if not l.startswith(('**源码开发进展：CLI 0.1.50','**原始碼開發進展：CLI 0.1.50','**Source development: CLI 0.1.50')))+'\n'
  s=s.replace('native-hdr-measure-current','native-hdr-measure-history')
  block='<!-- native-hdr-media-current -->\n\n**CLI0.1.50 / alpha.4-local.48 / r51 kit · 1 Skill / 17 modules / 89 files.**\n\n'+descriptions[suffix]+'\n\n'
  block+='[Workflow](docs/product/HDR_MEDIA_MEASUREMENT.md) · [C60](docs/product/CASES.md#c60-post-codec-hdr420) · [Install](docs/releases/CLI_0.1.50_LOCAL.md) · [Evidence](docs/validation/编码后成片安装与跨编码实测_2026-10-29.md)\n\n'
  block+='![Actual authored timeline SDR view]('+media+'author-SDR-preview.gif)\n\n'+detail[suffix]+'\n\n<!-- /native-hdr-media-current -->\n\n'
  errata={'':'C59/R331计数更正：384000个PCM总标量中383999非零；旧历史行保留，[当前纠正与证据](docs/validation/编码后成片安装与跨编码实测_2026-10-29.md)。','.zh-TW':'C59／R331計數更正：384000個PCM總標量中383999非零；原歷史行保留，[目前更正與證據](docs/validation/编码后成片安装与跨编码实测_2026-10-29.md)。','.en':'C59/R331 correction:384000 total PCM scalars,383999 nonzero.Historical rows remain archived;see the [current correction and evidence](docs/validation/编码后成片安装与跨编码实测_2026-10-29.md).'}[suffix]
  block=block.replace('<!-- /native-hdr-media-current -->',errata+'\n\n<!-- /native-hdr-media-current -->')
  s=s.replace('<!-- native-hdr-measure-history -->',block+'<!-- native-hdr-measure-history -->',1)
  for prefix,row in [('F75',frows[suffix]),('S30',srows[suffix])]:s,n=re.subn(r'^\| '+prefix+r' \|.*$',lambda _:row,s,count=1,flags=re.M);assert n==1
  texts={
   '':['安装专项29/29，源码/安装276份Python文件相同。','安装边界回归42/42，原生YCbCr/视频读取/schema。','安装兼容回归352/352；与29/42专项分列，不累加历史次数。','C60真实注册Skill：PQ/HLG H.265 4:2:0两条48帧独立像素/光量核验，HLG工程包重放全像素与PCM一致。','r51独立工具包核验，1入口/17模块/89 Skill文件；无源码回落。'],
   '.zh-TW':['安裝專項29/29，原始碼／安裝276份Python檔案相同。','安裝邊界回歸42/42，原生YCbCr／影片讀取／schema。','安裝相容回歸352/352；與29／42專項分列，不累加歷史次數。','C60真實註冊Skill：PQ／HLG H.265 4:2:0兩條48影格獨立像素／光量核驗，HLG專案重播全像素與PCM一致。','r51獨立工具包核驗，1入口／17模組／89 Skill檔案；無原始碼回落。'],
   '.en':['Installed focused tests29/29;276Python source/installed files identical.','Installed boundary regressions42/42:native YCbCr/video/schema.','Installed compatibility352/352;separate from29/42 and historical runs.','C60 actual registered Skill:PQ/HLG H.265 4:2:0,two48-frame independent pixel/light oracles;HLG package replay preserves all pixels/PCM.','r51 independent kit acceptance:1entry/17modules/89Skill files;no source fallback.']}[suffix]
  runs=['installed-r1','installed-boundary-r1','installed-compat-r1','installed-case-'+a.case,'kit-r1']
  for i,(text,run) in enumerate(zip(texts,runs),336):s=append_row(s,'| R'+str(i)+' | 2026-10-29 CLI0.1.50 installed | '+text+' | [Evidence]('+evidence+run+'/verification.json) |')
  assert [l for l in s.splitlines() if re.match(r'^\| R\d+ \|',l)][:335]==oldrows
  write(p,s)
  for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
   p=base+suffix+'.md';s=read(p);rel='HDR_MEDIA_MEASUREMENT.md' if '/product/' in p else '../product/HDR_MEDIA_MEASUREMENT.md'
   block='<!-- community-current -->\n\n**CLI0.1.50 / alpha.4-local.48 / r51 kit · 1 Skill / 17 modules / 89 files.**\n\n'+descriptions[suffix]+'\n\n[Post-codec workflow]('+rel+')\n\n<!-- /community-current -->'
   s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
   if base.endswith('CAPABILITIES'):
    for prefix,row in [('F75',frows[suffix]),('S30',srows[suffix])]:s,n=re.subn(r'^\| '+prefix+r' \|.*$',lambda _:row,s,count=1,flags=re.M);assert n==1
    for key,value in caps.items():
     section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
     s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S);assert n==1,key
    s+='\n[CLI0.1.50 exact installed capabilities](hdr-media-measure-capabilities-cli-0.1.50.json).\n'
   write(p,s)
 prior=load(ROOT/'docs/validation/evidence/native-hdr-measure-20261028-r1/installation-final-r1/verification.json')
 p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
 for old,new in [('local.47','local.48'),('CLI 0.1.49','CLI 0.1.50'),('CLI0.1.49','CLI0.1.50'),('r50.zip','r51.zip'),('package-0.1.49-r50.json','package-0.1.50-r51.json'),(prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256']),('CLI_0.1.49_LOCAL.md','CLI_0.1.50_LOCAL.md')]:s=s.replace(old,new)
 s+='\nCurrent post-codec workflow:[HDR_MEDIA_MEASUREMENT](HDR_MEDIA_MEASUREMENT.md) · [C60](CASES.md#c60-post-codec-hdr420).\n';write(p,s)
 p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：').replace('Source development / 源码开发 / 原始碼開發：','Historical source stage / 历史源码阶段 / 歷史原始碼階段：')
 s=s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.50 / local.48 / r51 kit** · [Workflow](product/HDR_MEDIA_MEASUREMENT.md) · [Install](releases/CLI_0.1.50_LOCAL.md) · [C60](product/CASES.md#c60-post-codec-hdr420).\n\n',1);write(p,s)
 p='docs/product/GOAL_GAPS_20261025.md';s=read(p)
 old=next(l for l in s.splitlines() if l.startswith('| G08 |'));cells=old.split('|');closure=cells[-3]
 cells[3]+=' CLI0.1.50本地安装版新增编码后原生PTS/YCbCr光量复核，C60实际PQ/HLG H.265 4:2:0独立像素/光量与HLG包重放通过。 '
 cells[4]=cells[4].replace('编码后/物理峰值测量','物理峰值测量与更广编码后覆盖');assert cells[-3]==closure
 s=s.replace(old,'|'.join(cells));s=s.replace('\n\n','\n\n2026-10-29 G08本地交付：**CLI0.1.50 / local.48 / r51 kit**贯通编码后成片光量复核、真实PQ/HLG H.265 4:2:0及包重放，[C60](CASES.md#c60-post-codec-hdr420)。安装29/42/352分别核验；仍保留38项原关闭条件，完整色彩/HDR/监看继续开发。\n\n',1);write(p,s)
 p='docs/product/HDR_MEDIA_MEASUREMENT.md';s=read(p);start=s.index('本轮新增源码命令');end=s.index('\n\n## 输入',start)
 s=s[:start]+'本地 CLI 0.1.50 / alpha.4-local.48 已安装并加载统一 `$agent-ffmpeg-local-editor`。`surface measure-media` 复核编码后文件，`surface measure` 测量编码器RGB16输入；两者不可混称。[安装流程](../releases/CLI_0.1.50_LOCAL.md)。'+s[end:]
 start=s.index('源码入口示例');end=s.index('\n\n去掉',start)
 s=s[:start]+"""通过已注册本地统一Skill调用（原生PowerShell）：

```powershell
$aekSkill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aekSkill surface measure-media --project PROJECT --input renders/master.mkv --signal-json SIGNAL.json --pixel-family yuv --yuv-matrix bt2020nc --yuv-range limited --chroma-location left --scan progressive --dry-run
```

`--signal-json` 使用实际本地JSON的绝对路径；不要调用旧版安装，也不要静默回落到源码。"""+s[end:]
 s=s.replace('- 这一轮尚未完成新增命令的发行包构建、安装版回归与公开客户端案例；正式可用版本仍以当前安装版为准。','- 当前已完成本地包、安装专项/边界/兼容与C60 PQ/HLG 4:2:0实测；公开alpha.3附件仍为旧版，不能当作CLI0.1.50下载。4K/长片/更广编解码与物理监看验收继续开发。')
 s+='\n\n[本地安装版跨编码实测](../validation/编码后成片安装与跨编码实测_2026-10-29.md) · [C60](CASES.md#c60-post-codec-hdr420)。\n';write(p,s)
 p='docs/product/HDR_MEASUREMENT.md';s=read(p).replace('后续源码开发：编码后文件复核','编码后文件复核').replace('新增命令尚未进入当前CLI0.1.49安装版','CLI0.1.50本地安装已支持该命令');write(p,s)
 p='docs/releases/CLI_0.1.50_SOURCE.md';s=read(p);s=s.replace('\n\n','\n\n历史源码阶段记录。后续本地交付已完成，见[CLI0.1.50本地安装](CLI_0.1.50_LOCAL.md)；以下保留当时状态，不作为当前安装说明。\n\n',1);write(p,s)
 report=dict(status='documented',F=75,S=30,K=17,R=340,prior_R_retained=335,original_G_closures_retained=38,tests=counts,whole_goal_complete=False)
 (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))
if __name__=='__main__':main()
