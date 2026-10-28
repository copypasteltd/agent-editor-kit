"""Document actual native ICC delivery; preserve every previous R/G closure cell."""
from pathlib import Path
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-icc-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def after(s,p,text):
    m=list(re.finditer(r'^\| '+p+r'\d+\s*\|.*$',s,re.M))[-1];return s[:m.end()]+'\n'+text+s[m.end():]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('documentation-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/'case-r1/verification.json');oracle=load(BASE/'case-r1/independent-every-frame-patches.json')
    assert case['status']=='passed' and all(c['ok'] for c in case['checks']) and oracle['status']=='passed' and oracle['comparisons']==384
    tests={}
    for run in ('source-r3','installed-r1','installed-compat-r1'):
        r=load(BASE/run/'verification.json');assert r['status']=='passed' and r['failures']==r['errors']==r['skipped']==0;tests[run]=r['tests']
    assert tests['source-r3']==tests['installed-r1']==26
    n=tests['installed-compat-r1'];media='docs/assets/native-icc-20261028-r1/'
    capture='docs/product/icc-capabilities-cli-0.1.46.json';(ROOT/capture).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==85
    description={
      '':'新增**原生 ICC 色彩管理**：明确本地 RGB ICC v2/v4、SHA、四种渲染意图与黑点补偿，由 LittleCMS 2.19.1 直接转换到线性工作 RGB；贯通素材、浮点导出、预览缓存和可编辑工程包。',
      '.zh-TW':'新增**原生 ICC 色彩管理**：明確本機 RGB ICC v2/v4、SHA、四種算圖意圖與黑點補償，由 LittleCMS 2.19.1 直接轉換至線性工作 RGB；貫通素材、浮點匯出、預覽快取及可編輯專案封裝。',
      '.en':'Added **native ICC source color management**: explicit local RGB ICC v2/v4 files, SHA pins, four rendering intents and black-point compensation. LittleCMS 2.19.1 converts directly to linear working RGB across source decoding, raw surfaces, preview caches and editable packages.'}
    limits={
      '':f'26项源码专项、26项安装专项和{n}项安装兼容检查分别通过。C56独立核对首帧230400像素、全48帧色块与完整非静音音画工程包重放；每次48次实际GPU Bloom。ICC CMM使用CPU，支持的合成/光晕使用原生GPU。范围是RGB源配置：任意ICC输出、软打样、CMYK、内嵌配置自动识别、完整ACES和自然HDR监看仍待补齐，38项原目标关闭条件保留。',
      '.zh-TW':f'26項原始碼專項、26項安裝專項與{n}項安裝相容檢查分別通過。C56獨立核對首影格230400像素、全48影格色塊及完整非靜音音畫專案封裝重播；每次48次實際GPU Bloom。ICC CMM使用CPU，支援的合成／光暈使用原生GPU。範圍為RGB來源設定：任意ICC輸出、軟打樣、CMYK、內嵌設定自動識別、完整ACES與自然HDR監看仍待補齊，保留38項原目標關閉條件。',
      '.en':f'26 source checks, 26 installed checks and {n} installed compatibility checks pass separately. C56 independently checks 230400 first-frame pixels, patches across all 48 encoded frames and full non-silent video/PCM package replay, with 48 actual GPU Bloom calls per render. ICC uses CPU; supported composition/glow uses native GPU. Arbitrary output ICC, softproofing, CMYK, embedded-profile inference, full ACES and natural HDR monitoring remain open. All 38 original goal closure conditions are retained.'}
    feature={
      '':'| F72 | 原生ICC来源色彩管理 | RGB ICC v2/v4矩阵/CLUT、明确SHA/意图/BPC → 线性RGB工作域，Float32/alpha、实际预览与工程包依赖闭合。 | `native_icc_source_profiles; surface inspect-profile; surface export; render; preview; convert` | 固定MIT LittleCMS原生CPU；不含任意输出ICC/软打样/CMYK/自动内嵌推断。 |',
      '.zh-TW':'| F72 | 原生ICC來源色彩管理 | RGB ICC v2/v4矩陣/CLUT、明確SHA/意圖/BPC → 線性RGB工作域，Float32/alpha、實際預覽與專案依賴閉合。 | `native_icc_source_profiles; surface inspect-profile; surface export; render; preview; convert` | 固定MIT LittleCMS原生CPU；不含任意輸出ICC/軟打樣/CMYK/自動內嵌推斷。 |',
      '.en':'| F72 | Native ICC source color management | RGB ICC v2/v4 matrix/CLUT, explicit SHA/intent/BPC → linear working RGB, Float32/alpha, actual previews and portable profile dependencies. | `native_icc_source_profiles; surface inspect-profile; surface export; render; preview; convert` | Pinned MIT LittleCMS/native CPU; no arbitrary output ICC, softproofing, CMYK or embedded-profile inference. |'}
    service={
      '':'| S27 | 原生ICC CMM服务 | 固定LittleCMS2.19.1 Windows x64 DLL、私有上下文、分块Float32、持锁/取消/关闭、实际配置字节核验。 | 包内原生DLL与MIT许可；无需新模型/全局安装。 | `surface; render; preview; convert` | 16MiB/4096标签及表面预算；CPU转换，GPU合成独立选择。 |',
      '.zh-TW':'| S27 | 原生ICC CMM服務 | 固定LittleCMS2.19.1 Windows x64 DLL、私有上下文、分塊Float32、持鎖/取消/關閉、實際設定檔位元組核驗。 | 包內原生DLL與MIT授權；無需新模型/全域安裝。 | `surface; render; preview; convert` | 16MiB/4096標籤與表面預算；CPU轉換，GPU合成獨立選擇。 |',
      '.en':'| S27 | Native ICC CMM service | Pinned LittleCMS2.19.1 Windows x64 DLL, private contexts, tiled Float32, read locks/cancellation/cleanup and actual profile-byte verification. | Bundled DLL/MIT license; no new model/global installation. | `surface; render; preview; convert` | 16MiB/4096 tags and surface budgets; CPU conversion, independently selected GPU composition. |'}
    records={
      '':['CLI0.1.46/local.44离线包：269个Python文件与ICC DLL/许可逐字节一致，85能力；保留旧公开包。',
          '26源码专项通过：真实v2/v4矩阵/非线性CLUT、四意图/BPC、独立矩阵和Pillow2.17 CMM对照、nits/alpha/负值、取消/持锁、surface CLI/缓存/工程包。初轮Gamma量化/版本查询和缺意图表失败保留。',
          f'安装版26专项通过；另列{n}项既有白点/HDR10/光晕/色彩/曲线/LUT/浮点渲染/预览/工程包/schema/队列兼容，零失败/错误/跳过。',
          'C56真实注册Skill：原创CC0 RGB ICC v4配置、230400像素独立工作域对照、48帧×8色块编码核对；每次48次实际GPU Bloom及CMM关闭收据。',
          'C56工程包保留ICC原字节/信号；完整48帧66355200解码字节和384000个非零PCM标量重放一致，实际PNG/MP4/GIF和作者只读预览。',
          'r47统一Skill：1入口/17内部模块/85文件、安装版固定摘要及独立解包注册/ICC工程计划；首次激活因清单更新先后被拦截，完成清单后重新成功。'],
      '.zh-TW':['CLI0.1.46/local.44離線包：269個Python檔案及ICC DLL/授權逐位元組一致，85能力；保留舊公開包。',
          '26原始碼專項通過：真實v2/v4矩陣/非線性CLUT、四意圖/BPC、獨立矩陣與Pillow2.17 CMM對照、nits/alpha/負值、取消/持鎖、surface CLI/快取/專案包。保留初輪Gamma量化/版本查詢與缺意圖表失敗。',
          f'安裝版26專項通過；另列{n}項既有白點/HDR10/光暈/色彩/曲線/LUT/浮點算圖/預覽/專案包/schema/佇列相容，零失敗/錯誤/略過。',
          'C56真實註冊Skill：原創CC0 RGB ICC v4設定、230400像素獨立工作域對照、48影格×8色塊編碼核對；每次48次實際GPU Bloom及CMM關閉收據。',
          'C56專案包保留ICC原位元組/訊號；完整48影格66355200解碼位元組與384000個非零PCM標量重播一致，實際PNG/MP4/GIF及作者唯讀預覽。',
          'r47統一Skill：1入口/17內部模組/85檔案、安裝版固定摘要與獨立解包註冊/ICC專案計畫；首次啟用因清單更新先後被攔截，完成清單後重新成功。'],
      '.en':['CLI0.1.46/local.44 offline build: 269 Python files plus native ICC DLL/license match source byte-for-byte; 85 capabilities. Public older artifacts retained.',
          '26 source checks: actual v2/v4 matrix/nonlinear CLUT profiles, four intents/BPC, independent matrix/Pillow2.17 CMM reference, nits/alpha/negative RGB, cancellation/locks, raw-surface CLI/cache/package closure. Initial gamma-quantization/version-query and missing-intent-table failures retained.',
          f'26 installed checks plus a separate {n}-check installed compatibility run covering white points/HDR10/glow/color/curves/LUT/render/preview/packages/schema/queues; zero failures/errors/skips.',
          'C56 registered Skill: original CC0 RGB ICC v4 profile, independent 230400-pixel working-space reference and 48×8 encoded patches, with 48 actual GPU Bloom calls/render and CMM cleanup receipts.',
          'C56 editable package retains exact ICC bytes/signals; all 48 decoded frames/66355200 bytes and 384000 nonzero PCM scalars replay identically; actual PNG/MP4/GIF and author-preserving previews.',
          'r47 unified Skill: one entry/17 modules/85 files, pinned installed runtime and independent extraction/registration/ICC project plan. First activation correctly refused an incomplete pin update; activation succeeded after the pin finished.']}
    targets=['installation-final-r1','source-r3','installed-compat-r1','case-r1','case-r1','kit-r1']
    for suffix in ('','.zh-TW','.en'):
        p='README'+suffix+'.md';s=read(p);old=rows(s,'R');assert len(old)==309
        s=s.replace('<!-- native-chromatic-current -->','<!-- native-chromatic-history -->',1).replace('<!-- /native-chromatic-current -->','<!-- /native-chromatic-history -->',1)
        block='<!-- native-icc-current -->\n\n**CLI0.1.46 / alpha.4-local.44 / r47 kit · 1 Skill / 17 modules.**\n\n'+description[suffix]+'\n\n'
        block+='[Workflow / usage](docs/product/ICC_PROFILES.md) · [C56](docs/product/CASES.md#c56-native-icc-profiles) · [Install](docs/releases/CLI_0.1.46_LOCAL.md) · [Evidence](docs/validation/原生ICC色彩管理实测_2026-10-28.md)\n\n'
        block+='![Actual ICC client preview]('+media+'actual-preview.gif)\n\n'+limits[suffix]+'\n\n<!-- /native-icc-current -->\n\n'
        s=s.replace('<!-- native-chromatic-history -->',block+'<!-- native-chromatic-history -->',1)
        s=after(after(s,'F',feature[suffix]),'S',service[suffix])
        s=after(s,'R','\n'.join('| R'+str(310+i)+' | 2026-10-28 ICC | '+d+' | [Evidence](docs/validation/evidence/native-icc-20261028-r1/'+t+'/verification.json) |' for i,(d,t) in enumerate(zip(records[suffix],targets))))
        s=s.replace('[r46 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r46.zip)','[r47 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r47.zip)')
        s='\n'.join(line.replace('local.43/final-r1/installed','local.44/final-r1/installed').replace('CLI 0.1.45','CLI 0.1.46') if 'local.43/final-r1/installed' in line else line for line in s.splitlines())+'\n'
        s=s.replace('完整的 71 个功能模块','完整的 72 个功能模块').replace('完整的 71 個功能模組','完整的 72 個功能模組').replace('All 71 functional modules','All 72 functional modules')
        assert len(rows(s,'R'))==315 and all(rows(s,'R')[k]==v for k,v in old.items());write(p,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            p=base+suffix+'.md';s=read(p);relative='ICC_PROFILES.md' if '/product/' in p else '../product/ICC_PROFILES.md'
            block='<!-- community-current -->\n\n**CLI0.1.46 / alpha.4-local.44 / r47 kit · 1 Skill / 17 modules / 85 files.**\n\n'+description[suffix]+'\n\n[Native ICC workflow]('+relative+')\n\n<!-- /community-current -->'
            s,count=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert count==1
            if base.endswith('CAPABILITIES'):
                s=after(after(s,'F',feature[suffix]),'S',service[suffix])
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,count=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if count==0:assert key=='native_icc_source_profiles';s+='\n'+section+'\n'
                s+='\n[CLI0.1.46 exact installed capabilities](icc-capabilities-cli-0.1.46.json).\n'
            write(p,s)
    prior=load(ROOT/'docs/validation/evidence/native-chromatic-20261028-r1/installation-final-r1/verification.json')
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
    # Current installation fields only; retain older feature/version histories.
    s=s.replace('**`v0.1.0-alpha.4-local.43` / CLI 0.1.45**','**`v0.1.0-alpha.4-local.44` / CLI 0.1.46**').replace('local.43/final-r1/installed','local.44/final-r1/installed').replace('local.43/candidate-r1/bundle.zip','local.44/candidate-r1/bundle.zip')
    for x,y in [('r46.zip','r47.zip'),('package-0.1.45-r46.json','package-0.1.46-r47.json'),(prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(x,y)
    s+='\nCurrent CLI0.1.46: [native ICC source profiles](ICC_PROFILES.md), [C56](CASES.md#c56-native-icc-profiles), [installation](../releases/CLI_0.1.46_LOCAL.md). The native CMM/DLL/MIT license are bundled; no new model or global install is required.\n';write(p,s)
    p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：')
    write(p,s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.46 / local.44 / r47 kit** · [Native ICC](product/ICC_PROFILES.md) · [Install](releases/CLI_0.1.46_LOCAL.md) · [C56](product/CASES.md#c56-native-icc-profiles).\n\n',1))
    p='docs/product/GOAL_GAPS_20261025.md';s=read(p);old=rows(s,'G');line=old['G08'];cells=line.split('|')
    cells[3]=' 明确nit/PQ/HLG、HDR10静态SEI、Bradford D50/D60保留；CLI0.1.46新增原生RGB ICC v2/v4矩阵/CLUT、四意图/BPC、Float32素材/中间包/预览与配置依赖工程迁移，[C56](CASES.md#c56-native-icc-profiles)完整音画包重放。 '
    cells[4]=' ICC源转换已实现；任意输出ICC/软打样/CMYK/内嵌推断、完整ACES、峰值测量/非零黑位HLG/动态元数据/感知色域、自然HDR监看及完整后端质量仍未闭。 '
    s=s.replace(line,'|'.join(cells),1);assert all(rows(s,'G')[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
    s=s.replace('当前本地 **CLI','此前本地 **CLI');s=s.replace('\n\n','\n\n当前本地 **CLI0.1.46 / alpha.4-local.44 / r47 kit**：[原生ICC来源色彩管理](ICC_PROFILES.md)贯通明确RGB配置/意图/BPC、线性工作域、实际预览、Float32中间包与可移植配置依赖。[C56](CASES.md#c56-native-icc-profiles)与源码/安装/兼容核验分别留证；完整ICC输出/ACES/感知色域与监看、38项原关闭条件继续建设。\n\n',1);write(p,s)
    for p in ('docs/product/HDR_DISPLAY.md','docs/product/CHROMATIC_ADAPTATION.md'):
        write(p,read(p)+'\nCLI0.1.46 adds a separate [native ICC source-profile path](ICC_PROFILES.md): explicit RGB v2/v4 matrix/table files, rendering intent/BPC and direct linear working RGB conversion. Existing mathematical reference-white conversion still infers no profile or physical illuminant. ICC white tags do not supply HDR luminance; declare source/working/output nits separately.\n')
    release=f'''# CLI0.1.46 / alpha.4-local.44 — native ICC source color management

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

原生RGB ICC v2/v4来源、矩阵与CLUT、四意图/BPC、Float32/alpha、nits、实际预览和依赖完整工程包。繁體：原生來源設定、浮點匯出與可編輯專案。 English: explicit native ICC sources across editing and portable delivery. Public alpha.3/CLI0.1.2 artifacts remain immutable.

```text
installed: local/agent-ffmpeg/v0.1.0-alpha.4-local.44/final-r1/installed
application ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.44/candidate-r1/bundle.zip
archive bytes: {install['archive_bytes']}
archive SHA256: {install['archive_sha256']}
manifest: {install['manifest_sha256']}
```

269 Python files and native ICC manifest/DLL/license match tested source bytes. 85 capabilities; one public `$agent-ffmpeg-local-editor`,17 internal modules,85 Skill files. r47 small kit contains138 ZIP entries. No source fallback, virtualization, global dependency installation or implicit download.

Follow [offline installation/activation](../product/COMMUNITY_LOCAL_DELIVERY.md), then [ICC configuration and complete usage](../product/ICC_PROFILES.md). Init/ingest/compose → inspect actual local profile → pin SHA/intent/BPC → declare linear working/output signals → validate/dry-run → render → inspect CMM/GPU receipts → preview actual output → export/import/replay an editable package. `surface export` also accepts explicit ICC flags and source/working nits. Native CMM runs on CPU; configured supported composition and Bloom/Halation use OpenCL.

26 source,26 installed and {n} installed compatibility checks pass separately. C56 uses an original CC0 gamma1.8 ProPhoto D50 ICC profile,independently checks230400 working pixels and384 frame/patch pairs,and replays all48 frames/384000 nonzero PCM scalars identically. Failed initial oracle/table fixtures and the first activation-order refusal are retained. Native RGB source ICC is implemented; arbitrary output ICC,softproofing,CMYK,embedded-profile inference,complete ACES,natural-image/HDR-monitor acceptance remain open.

[C56 actual media/GIF/editable package](../product/CASES.md#c56-native-icc-profiles) · [Evidence](../validation/原生ICC色彩管理实测_2026-10-28.md)
''';write('docs/releases/CLI_0.1.46_LOCAL.md',release)
    cm='../assets/native-icc-20261028-r1/';p='docs/product/CASES.md';s=read(p)+'\n<a id="c56-native-icc-profiles"></a>\n\n## C56 · 原生ICC色彩管理 / 原生ICC色彩管理 / Native ICC source profiles\n\n'
    s+='Actual installed CLI0.1.46 and registered unified Skill. Original CC0 RGB16 chart/stereo tones and an original RGB ICC v4.3 gamma1.8 ProPhoto D50 profile are edited in explicit linear AP1 D60, with48 actual GPU Bloom calls per render,then encoded as D65/sRGB ten-bit video. The CMM inspects and converts the actual profile,with private handles and read locks.\n\n'
    s+=f"Independent published-matrix/gamma reference:230400 first-surface pixels,maximum absolute error {case['maximum_surface_error']:.12g};384 encoded frame/patch pairs,maximum luma-code error {oracle['maximum_luma_code_error']:.12g}. ICC serialization quantizes tags; these approximate numeric comparisons are distinct from exact alpha and package replay. All48 decoded video frames ({case['decoded_video_bytes']}bytes) and384000 nonzero PCM scalars are byte-identical after package import. The exact ICC file and source declarations survive migration. Actual previews preserve author data;GIF24frames/4seconds.\n\n"
    s+='![Actual native ICC preview]('+cm+'actual-preview.gif)\n\n'
    s+=' · '.join('['+label+']('+cm+name+')' for label,name in [('Original source','source-prophoto-d50.mkv'),('Original ICC','source.icc'),('Actual master','edited-master.mkv'),('Actual MP4','actual-preview.mp4'),('Actual frame','actual-frame.png'),('Signals','signals.json'),('Comparison','comparison.png'),('Editable package','editable-icc.aevpkg.zip'),('Manifest','edited-master.mkv.manifest.json'),('Provenance','SOURCE.txt'),('Media hashes','media-manifest.json')])+'\n\n'
    s+='Left comparison: independent mathematical no-adaptation/no-Bloom control; right: actual native ICC/GPU Bloom engine frame at the same frame index. This is a numeric diagnostic,not a matched artistic A/B. The generated gamma1.8 source values stay above the ProPhoto toe. No vendor profile is copied or presumed licensed. No human continuous playback/listening,natural-image artistic or HDR-monitor acceptance. RGB source profiles do not provide arbitrary output ICC,softproofing,CMYK,embedded-profile inference or full ACES rendering.\n';write(p,s)
    report='# 原生ICC色彩管理实测 / Native ICC verification — 2026-10-28\n\n'+description['']+'\n\n'+limits['']+'\n\n'
    report+='LittleCMS2.19.1 MIT source pinned at commit `21c582a594fe5279f90c0b93437c398f93bf62b0`; native LLVM/MinGW Windows build, no virtualization. DLL SHA `'+install['native_ICC_artifacts']['avk_lcms_b0149bbc4fa977a2.dll']+'`. [Upstream release](https://github.com/mm2/Little-CMS/releases/tag/lcms2.19.1). CMM encoded version2190 is the upstream header value for this hotfix tag. Pillow reference uses a separate shipped CMM2.17; the product does not use its eight-bit conversion.\n\n'
    report+='Source-r1 retained two oracle issues: serialized v2 u8Fixed8 gamma differs from the authoring request, and the installed Pillow version exposes its CMM version differently. Source-r2 retained a CLUT fixture containing only A2B0 while requesting A2B1 relative colorimetric intent; actual CMM correctly rejected it. The final original fixture includes the requested table. Tolerances were not relaxed to mask these failures. Source-r3 and installed-r1 both pass26 checks.\n\n'
    report+='Activation-r1 was refused because activation started before the new Skill pin finished. Pin completion was confirmed,then activation-r2 verified four existing packs and registered the single junction successfully. No source fallback was enabled.\n\n'
    for run in ('native-build-r1','source-r1','source-r2','source-r3','installation-final-r1','installed-r1','installed-compat-r1','case-r1','kit-r1'):
        report+='- ['+run+'](evidence/native-icc-20261028-r1/'+run+'/verification.json)\n'
    report+='\n[Activation receipt](evidence/native-icc-20261028-r1/activation-final-r2/activation-and-registration.json) · [Actual C56 media](../product/CASES.md#c56-native-icc-profiles)\n'
    write('docs/validation/原生ICC色彩管理实测_2026-10-28.md',report)
    result=dict(status='passed',F=72,S=27,K=17,R=315,prior_R_retained=309,G_closure_cells_retained=38,tests=tests,whole_goal_complete=False)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(result))
if __name__=='__main__':main()
