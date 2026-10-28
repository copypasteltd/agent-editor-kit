"""Document delivered ICC output; preserve every historical R and G closure cell."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-icc-output-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def after(s,p,text):
 m=list(re.finditer(r'^\| '+p+r'\d+\s*\|.*$',s,re.M))[-1];return s[:m.end()]+'\n'+text+s[m.end():]
def main():
 out=BASE/'documentation-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
 install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/'case-r3/verification.json');assert case['status']=='passed'
 proof=load(BASE/'case-r3/independent-softproof.json');assert proof['status']=='passed' and max(proof['maximum_YCbCr_errors_codes'])<1
 counts={}
 for run in ('source-r2','installed-r1','installed-compat-r1'):
  r=load(BASE/run/'verification.json');assert r['status']=='passed' and r['failures']==r['errors']==r['skipped']==0;counts[run]=r['tests']
 assert counts=={'source-r2':17,'installed-r1':17,'installed-compat-r1':335}
 capture='docs/product/icc-output-capabilities-cli-0.1.48.json';(ROOT/capture).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
 caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==87
 descriptions={
 '':'新增**原生 RGB ICC 输出、16位内嵌配置 PNG 序列与软打样**：实际B2A查找表、四意图/BPC、明确亮度缩放、作者时间线逐帧交付和同步PCM；普通渲染/预览原生模拟，配置依赖可移植。',
 '.zh-TW':'新增**原生 RGB ICC 輸出、16位內嵌設定 PNG 序列與軟打樣**：實際B2A查找表、四意圖／BPC、明確亮度縮放、作者時間線逐影格交付及同步PCM；一般算繪／預覽原生模擬，設定依賴可移植。',
 '.en':'Added **native RGB ICC output, profile-embedded16-bit PNG sequence delivery and soft proof**: actual B2A tables,intents/BPC,explicit nits scaling,authored frames and synchronized PCM;native simulation in normal render/previews and portable profile dependencies.'}
 details={
 '':'17项源码专项、17项安装专项与335项安装兼容分别通过。C58逐帧内嵌ICC，独立核对384组B2A色块及384组软打样Y/Cb/Cr；全48帧PNG像素/文件、66355200字节软打样成片及384000非零PCM标量工程包重放相同，每次序列48次实际GPU Bloom。ICC用CPU，支持的剪辑算子用GPU；合成诊断配置不等于打印机/显示器校准或艺术质量验收。',
 '.zh-TW':'17項原始碼專項、17項安裝專項及335項安裝相容分別通過。C58逐影格內嵌ICC，獨立核對384組B2A色塊及384組軟打樣Y/Cb/Cr；全48影格PNG像素／檔案、66355200位元組軟打樣成片及384000非零PCM標量專案重播一致，每次序列48次實際GPU Bloom。ICC用CPU，支援的剪輯算子用GPU；合成診斷設定非印表機／顯示器校準或藝術品質驗收。',
 '.en':'17 source checks,17 installed checks and335 installed compatibility checks pass separately. C58 embeds ICC per frame,independently checks384 B2A patches and384 soft-proof Y/Cb/Cr triplets,and replays all48 PNG frames/files,66355200 decoded soft-proof movie bytes and384000 nonzero PCM scalars identically,with48 actual GPU Bloom calls/sequence. ICC uses CPU;supported editing uses GPU. The synthetic diagnostic profile is not printer/display calibration or artistic acceptance.'}
 features={
 '':'| F74 | 原生ICC输出与软打样 | RGB v2/v4矩阵/B2A CLUT、四意图/BPC、明确nits、逐帧内嵌ICC的RGBA16 PNG及作者PCM、真实SOFTPROOFING和完整交付检查。 | `native_icc_output_profiles; surface render; surface inspect-output; render; preview; convert` | CPU CMM；GPU剪辑独立；8GiB产物预算；无CMYK/ICC5/物理设备校准。 |',
 '.zh-TW':'| F74 | 原生ICC輸出與軟打樣 | RGB v2/v4矩陣／B2A CLUT、四意圖／BPC、明確nits、逐影格內嵌ICC的RGBA16 PNG與作者PCM、真實SOFTPROOFING及完整交付檢查。 | `native_icc_output_profiles; surface render; surface inspect-output; render; preview; convert` | CPU CMM；GPU剪輯獨立；8GiB產物預算；無CMYK／ICC5／物理設備校準。 |',
 '.en':'| F74 | Native ICC output and soft proof | RGB v2/v4 matrix/B2A CLUT,intents/BPC,explicit nits,individually ICC-embedded RGBA16 PNGs and authored PCM,real SOFTPROOFING and complete delivery verification. | `native_icc_output_profiles; surface render; surface inspect-output; render; preview; convert` | CPU CMM;separate GPU editing;8GiB file budget;no CMYK/ICC5/physical-device calibration. |'}
 services={
 '':'| S29 | ICC交付与模拟服务 | 逐帧ICC设备输出、标准电影软打样、原生CMM句柄/字节持锁、PNG CRC与完整像素/PCM核验。 | 固定MIT LittleCMS原生Windows；无需新模型。 | `surface render; surface inspect-output; render; preview; convert` | 配置自身映射和程序裁切分开；PNG序列与PCM，不把任意ICC RGB冒充标准YUV。 |',
 '.zh-TW':'| S29 | ICC交付與模擬服務 | 逐影格ICC設備輸出、標準影片軟打樣、原生CMM控制代碼／位元組持鎖、PNG CRC及完整像素／PCM核驗。 | 固定MIT LittleCMS原生Windows；無需新模型。 | `surface render; surface inspect-output; render; preview; convert` | 設定本身映射與程式裁切分開；PNG序列與PCM，不將任意ICC RGB冒充標準YUV。 |',
 '.en':'| S29 | ICC delivery and simulation service | Per-frame device-profile output,standard-movie soft proof,owned CMM handles/read locks,PNG CRC/all-pixel/PCM verification. | Pinned MIT LittleCMS on native Windows;no new model. | `surface render; surface inspect-output; render; preview; convert` | Separate native profile mapping from application clipping;PNG sequence/PCM,never relabel arbitrary device RGB as standard YUV. |'}
 records={
 '':['CLI0.1.48/local.46：273个Python文件和原生CMM与受测源码逐字节一致；87能力。','17项源码专项通过：独立矩阵/曲线/B2A、意图/BPC、alpha全部65536码、PNG完整性、时间线/CLI/PCM。','17安装专项及335兼容分别通过；原HLG/ICC/HDR/色适应/光晕/渲染/预览/Schema/队列继续验收。','C58：384组独立B2A色块、全48帧内嵌ICC输出/逐帧像素/CRC检查、每序列48次GPU Bloom。','C58：可移植软打样配置，工程包重放全部PNG文件/像素、66355200字节成片和384000非零PCM标量相同；实际PNG/MP4/GIF。','r49单Skill：1入口/17模组/87文件；固定本地安装，独立解包校验与安装版交付计划。'],
 '.zh-TW':['CLI0.1.48/local.46：273個Python檔案及原生CMM與受測原始碼逐位元組一致；87能力。','17項原始碼專項通過：獨立矩陣／曲線／B2A、意圖／BPC、alpha全部65536碼、PNG完整性、時間線／CLI／PCM。','17安裝專項與335相容分別通過；原HLG／ICC／HDR／色適應／光暈／算繪／預覽／Schema／佇列持續驗收。','C58：384組獨立B2A色塊、全48影格內嵌ICC輸出／逐影格像素／CRC檢查、每序列48次GPU Bloom。','C58：可移植軟打樣設定，專案重播全部PNG檔案／像素、66355200影片位元組及384000非零PCM標量一致；實際PNG／MP4／GIF。','r49單Skill：1入口／17模組／87檔案；固定本機安裝，獨立解包核驗及安裝版交付計畫。'],
 '.en':['CLI0.1.48/local.46:273 Python files/native CMM match tested source bytes;87 capabilities.','17 source checks:independent matrix/gamma/B2A,intents/BPC,all65536 alpha codes,PNG integrity,timeline/CLI/PCM.','17 installed checks and335 separate compatibility checks retain HLG/ICC/HDR/white/glow/render/preview/schema/queue coverage.','C58:384 independent B2A patches,all48 ICC-embedded frames/full pixels/CRCs,and48 GPU Bloom calls per sequence.','C58:portable proof profile;all PNG files/pixels,66355200 movie bytes and384000 nonzero PCM scalars replay exactly;actual PNG/MP4/GIF.','r49 single Skill:one entry/17 modules/87 files,pinned local installation,independent extraction/verification and installed delivery plan.']}
 targets=['installation-final-r1','source-r2','installed-compat-r1','case-r3','case-r3','kit-r1']
 for suffix in descriptions:
  p='README'+suffix+'.md';s=read(p);old=rows(s,'R');assert len(old)==321
  s=s.replace('native-hlg-black-current','native-hlg-black-history')
  block='<!-- native-icc-output-current -->\n\n**CLI0.1.48 / alpha.4-local.46 / r49 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n'
  block+='[Workflow / usage](docs/product/ICC_OUTPUT.md) · [C58](docs/product/CASES.md#c58-native-icc-output) · [Install](docs/releases/CLI_0.1.48_LOCAL.md) · [Evidence](docs/validation/原生ICC输出与软打样实测_2026-10-29.md)\n\n![Actual ICC soft proof](docs/assets/native-icc-output-20261028-r3/actual-preview.gif)\n\n'+details[suffix]+'\n\n<!-- /native-icc-output-current -->\n\n'
  s=s.replace('<!-- native-hlg-black-history -->',block+'<!-- native-hlg-black-history -->',1)
  s=after(after(s,'F',features[suffix]),'S',services[suffix])
  s=after(s,'R','\n'.join('| R'+str(322+i)+' | 2026-10-29 ICC | '+d+' | [Evidence](docs/validation/evidence/native-icc-output-20261028-r1/'+t+'/verification.json) |' for i,(d,t) in enumerate(zip(records[suffix],targets))))
  s=s.replace('[r48 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r48.zip)','[r49 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r49.zip)')
  s='\n'.join(line.replace('local.45/final-r1/installed','local.46/final-r1/installed').replace('CLI 0.1.47','CLI 0.1.48') if 'local.45/final-r1/installed' in line and not line.startswith('| R') else line for line in s.splitlines())+'\n'
  s=s.replace('完整的 73 个功能模块','完整的 74 个功能模块').replace('完整的 73 個功能模組','完整的 74 個功能模組').replace('All 73 functional modules','All 74 functional modules')
  assert len(rows(s,'R'))==327 and all(rows(s,'R')[k]==v for k,v in old.items());write(p,s)
  for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
   p=base+suffix+'.md';s=read(p);rel='ICC_OUTPUT.md' if '/product/' in p else '../product/ICC_OUTPUT.md'
   block='<!-- community-current -->\n\n**CLI0.1.48 / alpha.4-local.46 / r49 kit · 1 Skill / 17 modules / 87 files.**\n\n'+descriptions[suffix]+'\n\n[ICC output / soft proof workflow]('+rel+')\n\n<!-- /community-current -->'
   s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
   if base.endswith('CAPABILITIES'):
    s=after(after(s,'F',features[suffix]),'S',services[suffix])
    for key,value in caps.items():
     section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
     s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
     if not n:assert key=='native_icc_output_profiles';s+='\n'+section+'\n'
    s+='\n[CLI0.1.48 exact installed capabilities](icc-output-capabilities-cli-0.1.48.json).\n'
   write(p,s)
 prior=load(ROOT/'docs/validation/evidence/native-hlg-black-20261028-r1/installation-final-r1/verification.json')
 p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
 for a,b in [('**`v0.1.0-alpha.4-local.45` / CLI 0.1.47**','**`v0.1.0-alpha.4-local.46` / CLI 0.1.48**'),('local.45/final-r1/installed','local.46/final-r1/installed'),('local.45/candidate-r1/bundle.zip','local.46/candidate-r1/bundle.zip'),('r48.zip','r49.zip'),('package-0.1.47-r48.json','package-0.1.48-r49.json'),(prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(a,b)
 write(p,s+'\nCurrent CLI0.1.48: [ICC output and native soft proof](ICC_OUTPUT.md) · [C58](CASES.md#c58-native-icc-output) · [Install](../releases/CLI_0.1.48_LOCAL.md).\n')
 p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：');write(p,s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.48 / local.46 / r49 kit** · [ICC output](product/ICC_OUTPUT.md) · [Install](releases/CLI_0.1.48_LOCAL.md) · [C58](product/CASES.md#c58-native-icc-output).\n\n',1))
 p='docs/product/GOAL_GAPS_20261025.md';s=read(p);old=rows(s,'G');line=old['G08'];cells=line.split('|')
 cells[3]+=' CLI0.1.48已补原生RGB ICC输出/B2A、真实软打样、逐帧内嵌ICC的PNG16及作者PCM、完整像素/CRC检查与可移植proof配置。 '
 cells[4]=cells[4].replace('任意输出ICC/软打样/CMYK/内嵌推断','CMYK/ICC5/内嵌推断')+' 任意设备RGB电影封装仍不冒充标准YUV；RGB ICC交付为PNG序列与PCM。 ';s=s.replace(line,'|'.join(cells),1)
 assert all(rows(s,'G')[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
 s=s.replace('当前本地 **CLI','此前本地 **CLI');write(p,s.replace('\n\n','\n\n当前本地 **CLI0.1.48 / alpha.4-local.46 / r49 kit**：[原生ICC输出与软打样](ICC_OUTPUT.md)、[C58](CASES.md#c58-native-icc-output)及专项/兼容分别留证；所有38项原关闭条件保留，完整剪映等价仍未完成。\n\n',1))
 for p in ('docs/product/HDR_DISPLAY.md','docs/product/ICC_PROFILES.md'):
  write(p,read(p)+'\nCLI0.1.48 adds [native RGB ICC output,profile-embedded PNG16 timeline delivery/authored PCM and real native soft proof](ICC_OUTPUT.md). Arbitrary device RGB is never relabelled as standard YUV;physical-device matching remains open.\n')
 release='# CLI0.1.48 / alpha.4-local.46 — ICC output and native soft proof\n\n'
 release+='[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)\n\n'+'\n\n'.join(descriptions.values())+'\n\n'
 release+=f"```text\ninstalled: local/agent-ffmpeg/v0.1.0-alpha.4-local.46/final-r1/installed\napplication ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.46/candidate-r1/bundle.zip\narchive bytes: {install['archive_bytes']}\narchive SHA256: {install['archive_sha256']}\nmanifest: {install['manifest_sha256']}\n```\n\n"
 release+='273 Python files and native ICC artifacts match tested source bytes;87 capabilities. One public `$agent-ffmpeg-local-editor`,17 internal modules,87 Skill files,r49 kit142 entries. Public alpha.3/CLI0.1.2 artifacts unchanged. Native Windows,no virtualization/global installation/source fallback.\n\n'
 release+='Follow [offline activation](../product/COMMUNITY_LOCAL_DELIVERY.md),then [complete ICC output workflow](../product/ICC_OUTPUT.md):init/ingest/compose → explicit source/working signals → authorized output ICC/hash/intent → validate/dry-run → surface render → inspect-output → native soft-proof movie/preview → package/import/replay. Color CMM uses CPU;selected supported editing uses OpenCL GPU.\n\n'+details['.en']+'\n\n[C58 actual media](../product/CASES.md#c58-native-icc-output) · [Verification](../validation/原生ICC输出与软打样实测_2026-10-29.md).\n';write('docs/releases/CLI_0.1.48_LOCAL.md',release)
 cm='../assets/native-icc-output-20261028-r3/';p='docs/product/CASES.md';s=read(p)+'\n<a id="c58-native-icc-output"></a>\n\n## C58 · 原生ICC输出与软打样 / 原生ICC輸出與軟打樣 / Native ICC output and proof\n\n'
 s+='Actual installed CLI0.1.48 through registered unified Skill. Original CC0 linear RGB16 chart/stereo tones and original synthetic bidirectional RGB/XYZ ICC CLUT. Editable native GPU Bloom → actual profile-embedded PNG16/PCM device delivery;separate native SOFTPROOFING → actual standard ten-bit sRGB master and previews. The synthetic profile is a numerical diagnostic,not a printer or monitor characterization.\n\n'
 s+=f"All384 frame/patch B2A comparisons:max error {case['maximum_patch_error_codes']:.12g} of65535. All48 PNG frames/files ({case['PNG_pixel_bytes']} decoded pixel bytes),all66355200 decoded proof-movie bytes and384000 nonzero PCM scalars replay exactly after editable-package import;48 actual GPU Bloom calls per sequence. Every PNG embeds the exact ICC and passes full CRC/decompression checking.\n\n"
 s+='Independent soft-proof oracle separately checks384 Y/Cb/Cr triplets (1152 encoded components),with maximum errors '+str(proof['maximum_YCbCr_errors_codes'])+' codes,using original table interpolation,independent XYZ matrices,sRGB and limited-range BT709 math;no product/CMM functions.\n\n'
 s+='![Actual native ICC soft proof]('+cm+'actual-preview.gif)\n\n'+' · '.join('['+label+']('+cm+name+')' for label,name in [('Original source','source-linear.mkv'),('Original tones','source-stereo.wav'),('Original ICC','original-proof.icc'),('Profile descriptor','profile.json'),('Device PNG16','actual-device-frame.png'),('Actual proof master','proof-master.mkv'),('Actual MP4','actual-preview.mp4'),('Actual frame','actual-frame.png'),('Comparison','comparison.png'),('Editable package','editable-icc-output.aevpkg.zip'),('Sequence receipt','sequence.json'),('Master manifest','proof-master.mkv.manifest.json'),('Provenance','SOURCE.txt'),('Media hashes','media-manifest.json')])+'\n\n'
 s+='Left:independent source-to-sRGB/no-glow mathematical control;right:actual native proof preview plus GPU Bloom at the same frame. Not a matched device/artistic A/B. Actual GIF24 frames/4 seconds. No human continuous playback/listening or physical display/printer matching acceptance. CMYK,ICC5,full ACES,dynamic HDR and natural-image artistic acceptance remain open.\n';write(p,s)
 report='# 原生ICC输出与软打样实测 / Native ICC output verification — 2026-10-29\n\n'+details['']+'\n\n'
 report+='Initial uncaptured development tests exposed a fixture duration mismatch (one visual frame followed by authored black),a strict nits-array shape expectation and native gamma mapping of negative RGB to zero. Fixtures now span the full declared duration;negative-working and explicit application-clipping counts are distinguished. Persisted ICC XYZ/adaptation s15Fixed16 quantization is bounded separately from the ideal double-precision matrix oracle. Source-r1 runner had an invalid group-name mapping before tests;source-r2 freezes the complete passing17-test source set. C58 case-r1 retained an invalid null nits field in a relative proof descriptor and was correctly rejected by Schema;case-r3 omits the optional physical field. Case-r2 incorrectly compared the author snapshot from before the normal render against the later previews;normal render legitimately records author history. Case-r3 snapshots after normal rendering and checks preview-only preservation. No product numerical path or acceptance threshold was changed to make the case pass.\n\n'
 for run in ('source-r2','installation-final-r1','installed-r1','installed-compat-r1','case-r1','case-r2','case-r3','kit-r1'):report+='- ['+run+'](evidence/native-icc-output-20261028-r1/'+run+'/verification.json)\n'
 report+='\n[Independent soft-proof oracle](evidence/native-icc-output-20261028-r1/case-r3/independent-softproof.json):384 Y/Cb/Cr triplets (1152 encoded components),all errors below1 code;no product/CMM functions.\n'
 report+='\n[Activation](evidence/native-icc-output-20261028-r1/activation-final-r1/activation-and-registration.json) · [Primary research](evidence/native-icc-output-20261028-r1/primary-research.json) · [C58](../product/CASES.md#c58-native-icc-output). No standard pages/vendor profile collection redistributed;no GUI browser tabs opened.\n';write('docs/validation/原生ICC输出与软打样实测_2026-10-29.md',report)
 result=dict(status='passed',F=74,S=29,K=17,R=327,prior_R_retained=321,G_closure_cells_retained=38,tests=counts,whole_goal_complete=False)
 (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(result))
if __name__=='__main__':main()
