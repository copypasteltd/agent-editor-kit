"""Publish actual HLG black evidence, preserving all previous R/G closure cells."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hlg-black-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def after(s,p,text):
 m=list(re.finditer(r'^\| '+p+r'\d+\s*\|.*$',s,re.M))[-1];return s[:m.end()]+'\n'+text+s[m.end():]
def main():
 out=BASE/'documentation-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
 install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/'case-r1/verification.json');oracle=load(BASE/'case-r1/independent-every-frame-patches.json')
 assert case['status']=='passed' and oracle['status']=='passed' and oracle['comparisons']==384
 tests={}
 for run in ('source-r3','installed-r1','installed-compat-r1'):
  r=load(BASE/run/'verification.json');assert r['status']=='passed' and r['failures']==r['errors']==r['skipped']==0;tests[run]=r['tests']
 assert tests=={'source-r3':21,'installed-r1':21,'installed-compat-r1':314}
 capture='docs/product/hlg-black-capabilities-cli-0.1.47.json';(ROOT/capture).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
 caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==86
 descriptions={
 '':'新增**HLG 非零显示黑位和完整信号 JSON CLI**：明确黑位、峰值、伽马和参考白亮度，贯通源/输出、浮点中间包、预览与工程包；低于目标黑位严格拒绝或显式裁切计数。',
 '.zh-TW':'新增**HLG 非零顯示黑位與完整訊號 JSON CLI**：明確黑位、峰值、伽馬及參考白亮度，貫通來源／輸出、浮點中間包、預覽與專案包；低於目標黑位嚴格拒絕或明確裁切計數。',
 '.en':'Added **nonzero HLG display black and complete signal JSON CLI**: explicit black/peak/gamma/reference-white nits across sources, outputs, raw surfaces, previews and packages; below-black outputs reject or explicitly clip with counts.'}
 details={
 '':'21项源码专项、21项安装专项与314项安装兼容分别通过。C57核对230400个工作域像素、384组编码色块及完整48帧/384000个非零PCM标量工程包重放；每次48次实际GPU Bloom。色彩数学使用CPU，支持的合成使用GPU。0.5nit黑位是诊断声明，不是屏幕校准；动态HDR、完整ACES与自然监看仍未验收。',
 '.zh-TW':'21項原始碼專項、21項安裝專項及314項安裝相容分別通過。C57核對230400個工作域像素、384組編碼色塊及完整48影格／384000個非零PCM標量專案重播；每次48次實際GPU Bloom。色彩數學使用CPU，支援的合成使用GPU。0.5nit黑位為診斷宣告，非螢幕校準；動態HDR、完整ACES與自然監看尚未驗收。',
 '.en':'21 source checks,21 installed checks and314 installed compatibility checks pass separately. C57 checks230400 working pixels,384 encoded frame/patch pairs and all48 frames/384000 nonzero PCM scalars after package replay,with48 actual GPU Bloom calls/render. Color math uses CPU; supported composition uses GPU. The0.5-nit black is a diagnostic declaration,not monitor calibration; dynamic HDR,full ACES and natural-image monitoring remain open.'}
 features={
 '':'| F73 | HLG显示黑位与完整信号CLI | BT.2100黑位提升/逆变换、明确nit与黑位、零黑位原数值路径、完整RGB/HDR/ICC JSON与显式域策略。 | `native_hlg_black_level; surface export; render; preview; convert` | 不推测屏幕；nominal0..1；超限拒绝或明确裁切；不含动态HDR/完整ACES。 |',
 '.zh-TW':'| F73 | HLG顯示黑位與完整訊號CLI | BT.2100黑位提升／逆變換、明確nit與黑位、零黑位原數值路徑、完整RGB/HDR/ICC JSON與明確域策略。 | `native_hlg_black_level; surface export; render; preview; convert` | 不推測螢幕；nominal0..1；超限拒絕或明確裁切；無動態HDR／完整ACES。 |',
 '.en':'| F73 | HLG display black and complete signal CLI | BT.2100 black lift/inverse,explicit nits,unchanged zero-black numeric path,complete RGB/HDR/ICC JSON and explicit domain policies. | `native_hlg_black_level; surface export; render; preview; convert` | No monitor inference; nominal0..1; reject or explicit counted clipping; no dynamic HDR/full ACES. |'}
 services={
 '':'| S28 | 明确HLG黑位服务 | 分块Float32/alpha、beta校验、源/目标黑位、输出域计数与原生时钟中间包。 | 包内原生Windows CPU数学；既有GPU合成独立配置。 | `surface; render; preview; convert` | 无新增模型/全局安装；不替代屏幕测量或HDR监看验收。 |',
 '.zh-TW':'| S28 | 明確HLG黑位服務 | 分塊Float32/alpha、beta校驗、來源／目標黑位、輸出域計數及原生時鐘中間包。 | 包內原生Windows CPU數學；既有GPU合成獨立設定。 | `surface; render; preview; convert` | 無新增模型／全域安裝；不替代螢幕測量或HDR監看驗收。 |',
 '.en':'| S28 | Explicit HLG black service | Tiled Float32/alpha,beta validation,source/target black,domain counts and native-clock raw bundles. | Native Windows CPU math; separately configured GPU composition. | `surface; render; preview; convert` | No new model/global install; no replacement for display measurement/HDR monitor acceptance. |'}
 records={
 '':['CLI0.1.47/local.45：270个Python文件与原生ICC依赖字节一致，86能力；旧包保留。','21源码专项通过；保留初轮共享测试夹具污染与严格白点端点拒绝记录，未加入隐藏epsilon裁切。','21安装专项和另列314安装兼容通过，含27项ICC及旧有HDR/白点/渲染/预览/schema/队列；零失败/错误/跳过。','C57：230400工作域像素独立对照、384编码色块，每次48次GPU Bloom；明确HLG黑位，不推测屏幕。','C57：工程包48帧66355200视频字节与384000非零PCM标量逐字节重放，真实PNG/MP4/GIF、只读预览。','r48统一Skill：1入口/17模块/86文件，固定安装包；独立解包配置/注册/HLG计划与作者只读核验。'],
 '.zh-TW':['CLI0.1.47/local.45：270個Python檔案與原生ICC依賴位元組一致，86能力；保留舊包。','21原始碼專項通過；保留首輪共用測試資料污染與嚴格白點端點拒絕，未加入隱藏epsilon裁切。','21安裝專項及另列314安裝相容通過，含27項ICC與既有HDR／白點／算圖／預覽／schema／佇列；零失敗／錯誤／略過。','C57：230400工作域像素獨立對照、384編碼色塊，每次48次GPU Bloom；明確HLG黑位，不推測螢幕。','C57：專案包48影格66355200影片位元組及384000非零PCM標量逐位元組重播，真實PNG／MP4／GIF、唯讀預覽。','r48統一Skill：1入口／17模組／86檔案，固定安裝包；獨立解包設定／註冊／HLG計畫與作者唯讀核驗。'],
 '.en':['CLI0.1.47/local.45:270 Python files/native ICC artifacts match tested source bytes;86 capabilities;older releases retained.','21 source checks pass;initial shared-fixture mutation and strict rounded-white rejection retained;no hidden epsilon clamp.','21 installed checks plus314 separate compatibility checks,including27 ICC checks and existing HDR/white/render/preview/schema/queue coverage;zero failures/errors/skips.','C57:230400 independent working pixels,384 encoded patch comparisons,48 actual GPU Bloom calls/render;authored HLG black,no monitor inference.','C57:all48 frames/66355200 decoded video bytes and384000 nonzero PCM scalars replay byte-identically;actual PNG/MP4/GIF and read-only previews.','r48 unified Skill:one entry/17 modules/86 files,pinned installed release;independent extraction/configuration/registration/HLG plan and read-only author validation.']}
 targets=['installation-final-r1','source-r3','installed-compat-r1','case-r1','case-r1','kit-r1']
 for suffix in descriptions:
  p='README'+suffix+'.md';s=read(p);old=rows(s,'R');assert len(old)==315
  s=s.replace('native-icc-current','native-icc-history')
  block='<!-- native-hlg-black-current -->\n\n**CLI0.1.47 / alpha.4-local.45 / r48 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n'
  block+='[Workflow / usage](docs/product/HLG_BLACK_LEVEL.md) · [C57](docs/product/CASES.md#c57-hlg-display-black) · [Install](docs/releases/CLI_0.1.47_LOCAL.md) · [Evidence](docs/validation/HLG显示黑位实测_2026-10-28.md)\n\n![Actual HLG black preview](docs/assets/native-hlg-black-20261028-r1/actual-preview.gif)\n\n'+details[suffix]+'\n\n<!-- /native-hlg-black-current -->\n\n'
  s=s.replace('<!-- native-icc-history -->',block+'<!-- native-icc-history -->',1)
  s=after(after(s,'F',features[suffix]),'S',services[suffix])
  s=after(s,'R','\n'.join('| R'+str(316+i)+' | 2026-10-28 HLG | '+d+' | [Evidence](docs/validation/evidence/native-hlg-black-20261028-r1/'+t+'/verification.json) |' for i,(d,t) in enumerate(zip(records[suffix],targets))))
  s=s.replace('[r47 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r47.zip)','[r48 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r48.zip)')
  s='\n'.join(line.replace('local.44/final-r1/installed','local.45/final-r1/installed').replace('CLI 0.1.46','CLI 0.1.47') if 'local.44/final-r1/installed' in line else line for line in s.splitlines())+'\n'
  s=s.replace('完整的 72 个功能模块','完整的 73 个功能模块').replace('完整的 72 個功能模組','完整的 73 個功能模組').replace('All 72 functional modules','All 73 functional modules')
  assert len(rows(s,'R'))==321 and all(rows(s,'R')[k]==v for k,v in old.items());write(p,s)
  for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
   p=base+suffix+'.md';s=read(p);rel='HLG_BLACK_LEVEL.md' if '/product/' in p else '../product/HLG_BLACK_LEVEL.md'
   block='<!-- community-current -->\n\n**CLI0.1.47 / alpha.4-local.45 / r48 kit · 1 Skill / 17 modules / 86 files.**\n\n'+descriptions[suffix]+'\n\n[HLG black workflow]('+rel+')\n\n<!-- /community-current -->'
   s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
   if base.endswith('CAPABILITIES'):
    s=after(after(s,'F',features[suffix]),'S',services[suffix])
    for key,value in caps.items():
     section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
     s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
     if not n:assert key=='native_hlg_black_level';s+='\n'+section+'\n'
    s+='\n[CLI0.1.47 exact installed capabilities](hlg-black-capabilities-cli-0.1.47.json).\n'
   write(p,s)
 prior=load(ROOT/'docs/validation/evidence/native-icc-20261028-r1/installation-final-r1/verification.json')
 p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
 for a,b in [('**`v0.1.0-alpha.4-local.44` / CLI 0.1.46**','**`v0.1.0-alpha.4-local.45` / CLI 0.1.47**'),('local.44/final-r1/installed','local.45/final-r1/installed'),('local.44/candidate-r1/bundle.zip','local.45/candidate-r1/bundle.zip'),('r47.zip','r48.zip'),('package-0.1.46-r47.json','package-0.1.47-r48.json'),(prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(a,b)
 write(p,s+'\nCurrent CLI0.1.47: [HLG black and complete signal CLI](HLG_BLACK_LEVEL.md) · [C57](CASES.md#c57-hlg-display-black) · [Install](../releases/CLI_0.1.47_LOCAL.md).\n')
 p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：');write(p,s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.47 / local.45 / r48 kit** · [HLG black](product/HLG_BLACK_LEVEL.md) · [Install](releases/CLI_0.1.47_LOCAL.md) · [C57](product/CASES.md#c57-hlg-display-black).\n\n',1))
 p='docs/product/GOAL_GAPS_20261025.md';s=read(p);old=rows(s,'G');line=old['G08'];cells=line.split('|')
 cells[3]+=' CLI0.1.47已补非零HLG显示黑位、明确完整信号JSON CLI、零黑位数值兼容、实际预览与包重放。 '
 cells[4]=cells[4].replace('/非零黑位HLG','')+' 浮点中间包目前为末帧边界收据，逐帧裁切汇总待补。 ';s=s.replace(line,'|'.join(cells),1)
 assert all(rows(s,'G')[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
 s=s.replace('当前本地 **CLI','此前本地 **CLI');write(p,s.replace('\n\n','\n\n当前本地 **CLI0.1.47 / alpha.4-local.45 / r48 kit**：[HLG显示黑位](HLG_BLACK_LEVEL.md)和完整信号CLI已贯通；[C57](CASES.md#c57-hlg-display-black)与专项/兼容分列留证。38项原目标关闭条件保留，完整剪映等价未完成。\n\n',1))
 for p in ('docs/product/HDR_DISPLAY.md','docs/product/ICC_PROFILES.md'):
  write(p,read(p)+'\nCLI0.1.47 adds [HLG display black and complete source/working signal JSON for raw surface CLI](HLG_BLACK_LEVEL.md). Explicit nits,black/peak/gamma and reject/clip policies are required; no monitor inference. Existing RGB/ICC individual flags remain supported.\n')
 release=f'''# CLI0.1.47 / alpha.4-local.45 — HLG display black

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

{descriptions['']}

{descriptions['.zh-TW']}

{descriptions['.en']}

```text
installed: local/agent-ffmpeg/v0.1.0-alpha.4-local.45/final-r1/installed
application ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.45/candidate-r1/bundle.zip
archive bytes: {install['archive_bytes']}
archive SHA256: {install['archive_sha256']}
manifest: {install['manifest_sha256']}
```

270 Python files and native ICC artifacts match tested source bytes;86 capabilities.
One public `$agent-ffmpeg-local-editor`,17 internal modules,86 Skill files,r48 kit140 entries.
Public alpha.3/CLI0.1.2 artifacts remain unchanged. No source fallback,virtualization,
global installation or implicit model download.

Follow [offline activation](../product/COMMUNITY_LOCAL_DELIVERY.md),then
[complete HLG/CLI workflow](../product/HLG_BLACK_LEVEL.md):init/ingest/compose →
declare signals and domain policies → validate/dry-run → render → inspect actual
pixels/VUI/receipts → preview with explicit SDR mapping → package/import/replay.
Color math uses CPU;supported Bloom/composition uses selected native OpenCL GPU.

{details['.en']}

[C57 actual media/GIF/package](../product/CASES.md#c57-hlg-display-black) ·
[Verification](../validation/HLG显示黑位实测_2026-10-28.md)
''';write('docs/releases/CLI_0.1.47_LOCAL.md',release)
 cm='../assets/native-hlg-black-20261028-r1/';p='docs/product/CASES.md';s=read(p)+'\n<a id="c57-hlg-display-black"></a>\n\n## C57 · HLG显示黑位 / HLG顯示黑位 / HLG display black\n\n'
 s+='Actual installed CLI0.1.47 and registered unified Skill. Original CC0 RGB16 diagnostic/stereo tones;BT.2020 HLG,203-nit reference,1000-nit peak,gamma1.2,explicit0.5-nit black → linear working RGB → actual GPU Bloom → ten-bit PQ master. Separate explicit Reinhard SDR previews.\n\n'
 s+=f"Independent first-surface reference:230400 pixels,max error {case['maximum_surface_error']:.12g}. All384 frame/patch comparisons:max luma code error {oracle['maximum_luma_code_error']:.12g}. Two renders each execute48 actual GPU Bloom calls. All48 decoded frames ({case['decoded_video_bytes']}bytes) and384000 nonzero PCM scalars replay identically after editable package import. Actual previews preserve author data;GIF24frames/4seconds.\n\n"
 s+='![Actual HLG black preview]('+cm+'actual-preview.gif)\n\n'+' · '.join('['+label+']('+cm+name+')' for label,name in [('Original source','source-hlg-black.mkv'),('Actual master','edited-master.mkv'),('Actual MP4','actual-preview.mp4'),('Actual frame','actual-frame.png'),('Signals','signals.json'),('Comparison','comparison.png'),('Editable package','editable-hlg-black.aevpkg.zip'),('Manifest','edited-master.mkv.manifest.json'),('Provenance','SOURCE.txt'),('Media hashes','media-manifest.json')])+'\n\n'
 s+='Left:independent ideal-zero-black/no-glow control;right:actual declared0.5-nit black/GPU Bloom at the same frame index. Diagnostic declaration,not measured display calibration or matched natural-image artistic A/B. No human continuous playback/listening or HDR-monitor acceptance. Full ACES,dynamic HDR,subblack PLUGE and natural-image acceptance remain open.\n';write(p,s)
 report='# HLG显示黑位实测 / HLG black verification — 2026-10-28\n\n'+details['']+'\n\n'
 report+='Source-r1 retained shared frozen-dataclass `vars()` fixture mutation and a correctly rejected rounded-white endpoint. Invalid fixture data now uses a copied dictionary;inverse interior tests and a separate strict-reject/explicit-clip endpoint test verify the intended domain policy. No hidden epsilon clamp or tolerance relaxation. Source-r2 passed21 tests;after correcting stale raw HDR acceptance receipts,source-r3 passed21 tests on the final bytes. ICC runtime manifest/DLL/license are also rechecked under acquired read locks;27 ICC compatibility tests include a simulated pre-lock change.\n\n'
 for run in ('source-r1','source-r2','source-r3','installation-final-r1','installed-r1','installed-compat-r1','case-r1','kit-r1'):report+='- ['+run+'](evidence/native-hlg-black-20261028-r1/'+run+'/verification.json)\n'
 report+='\n[Activation](evidence/native-hlg-black-20261028-r1/activation-final-r1/activation-and-registration.json) · [Primary research](evidence/native-hlg-black-20261028-r1/primary-research.json) · [Actual C57](../product/CASES.md#c57-hlg-display-black). No standard PDF pages redistributed;no GUI browser tabs opened.\n'
 write('docs/validation/HLG显示黑位实测_2026-10-28.md',report)
 result=dict(status='passed',F=73,S=28,K=17,R=321,prior_R_retained=315,G_closure_cells_retained=38,tests=tests,whole_goal_complete=False)
 (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(result))
if __name__=='__main__':main()
