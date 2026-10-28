"""Update trilingual product manuals without removing any prior R/G closure cell."""
from pathlib import Path
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-chromatic-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def after(s,p,text):
    m=list(re.finditer(r'^\| '+p+r'\d+\s*\|.*$',s,re.M))[-1];return s[:m.end()]+'\n'+text+s[m.end():]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--case',default='r3');a=ap.parse_args()
    assert a.run.replace('-','').isalnum() and a.case.replace('-','').isalnum()
    out=BASE/('documentation-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/('case-'+a.case)/'verification.json')
    assert case['status']=='passed' and all(c['ok'] for c in case['checks'])
    oracle=load(BASE/('case-'+a.case)/'independent-every-frame-patches.json')
    assert oracle['status']=='passed' and oracle['comparisons']==384
    counts={}
    for name in ('source-r3','installed-r1','installed-compat-r1'):
        r=load(BASE/name/'verification.json');assert r['status']=='passed' and r['failures']==r['errors']==r['skipped']==0;counts[name]=r['tests']
    assert counts['source-r3']==counts['installed-r1']==20
    n=counts['installed-compat-r1'];media='docs/assets/native-chromatic-20261028-'+a.case+'/'
    capture='docs/product/chromatic-capabilities-cli-0.1.45.json';(ROOT/capture).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==84
    descriptions={
      '':'新增**Bradford 白点适应、ProPhoto RGB D50 和线性 ACES AP1 D60**：贯通来源、工作域、效果信号、浮点中间包、实际预览和可编辑工程包；光晕按声明白点计算亮度，现有 D65 行为保留。',
      '.zh-TW':'新增**Bradford 白點適應、ProPhoto RGB D50 和線性 ACES AP1 D60**：貫通來源、工作域、效果訊號、浮點中間封裝、實際預覽與可編輯專案；光暈依聲明白點計算亮度，保留既有 D65 行為。',
      '.en':'Added **Bradford reference-white adaptation, ProPhoto RGB D50 and linear ACES AP1 D60** across sources, working RGB, effect signals, raw surfaces, actual previews and editable packages. Glow luminance follows the declared white; existing D65 behavior is retained.'}
    limits={
      '':f'20项源码专项、20项安装专项和{n}项安装兼容检查分别通过。C55独立对照首帧230400像素及全48帧色块，实际GPU Bloom与完整音画包重放通过。颜色数学CPU，合成/光晕可用GPU；最终BT.709/BT.2100交付D65。参考白点转换不是ICC解析、自动物理白平衡或完整ACES输出变换；感知色域映射、自然HDR监看及38项完整目标继续开发。',
      '.zh-TW':f'20項原始碼專項、20項安裝專項和{n}項安裝相容檢查分別通過。C55獨立對照首影格230400像素及全48影格色塊，實際GPU Bloom與完整音畫封裝重播通過。顏色數學CPU，合成／光暈可用GPU；最終BT.709／BT.2100交付D65。參考白點轉換並非ICC解析、自動物理白平衡或完整ACES輸出變換；感知色域映射、自然HDR監看及38項完整目標持續開發。',
      '.en':f'20 source checks,20 installed checks and{n} installed compatibility checks pass separately. C55 independently checks230400 first-frame pixels and patches across all48 encoded frames,actual GPU Bloom and full video/PCM package replay. Color math uses CPU; composition/glow can use GPU. BT.709/BT.2100 delivery remains D65. Reference-white conversion does not parse ICC, infer physical white balance or provide full ACES output rendering. Perceptual gamut mapping,natural HDR monitoring and all38 original goal closure conditions remain ongoing.'}
    features={
      '':'| F71 | 白点适应与宽色域工作配置 | ProPhoto D50／AP1 D60／明确xy → 线性XYZ Bradford、nit缩放、实际D65预览与工程包。 | `native_chromatic_adaptation; render; preview; surface export; convert` | CPU色彩数学，GPU光晕按声明白点；不含ICC解析／完整ACES／自动白平衡。 |',
      '.zh-TW':'| F71 | 白點適應與寬色域工作設定 | ProPhoto D50／AP1 D60／明確xy → 線性XYZ Bradford、nit縮放、實際D65預覽與專案封裝。 | `native_chromatic_adaptation; render; preview; surface export; convert` | CPU色彩數學，GPU光暈依聲明白點；不含ICC解析／完整ACES／自動白平衡。 |',
      '.en':'| F71 | Explicit-white and wide-gamut working configurations | ProPhoto D50/AP1 D60/explicit xy → linear XYZ Bradford,nit scaling,actual D65 previews and editable packages. | `native_chromatic_adaptation; render; preview; surface export; convert` | CPU color math,working-white-aware GPU glow; no ICC parsing/full ACES/automatic white balance. |'}
    services={
      '':'| S26 | 明确白点RGB转换服务 | 原生分块Float64计算／Float32表面、ProPhoto分段传递、Bradford矩阵及白点几何校验。 | 已有NumPy；无新增模型／服务。 | `render; preview; surface` | 编码交付D65，alpha保位；不推断素材ICC或场景光源。 |',
      '.zh-TW':'| S26 | 明確白點RGB轉換服務 | 原生分塊Float64計算／Float32表面、ProPhoto分段傳遞、Bradford矩陣與白點幾何核驗。 | 既有NumPy；無新增模型／服務。 | `render; preview; surface` | 編碼交付D65，alpha保位；不推斷素材ICC或場景光源。 |',
      '.en':'| S26 | Explicit-white RGB conversion service | Native tiled Float64 math/Float32 surfaces,ProPhoto piecewise transfer,Bradford matrices and white geometry checks. | Existing NumPy; no new model/service. | `render; preview; surface` | D65 encoded delivery,alpha bits retained; no ICC or scene-illuminant inference. |'}
    records={
      '':['CLI0.1.45/local.43原生离线构建安装：268程序文件一致、84能力；旧公开包保留。',
          '20源码专项：独立公开矩阵／标量传递、D50/D60/自定白、nit与alpha、实际GPU、surface CLI、成片／预览／工程包；初轮两项断言错误保留并修正。',
          f'安装版20专项通过，{n}项既有色彩／HDR10／光晕／LUT／曲线／渲染／预览／包／schema／队列兼容另列，零失败／错误／跳过。',
          'C55真实注册Skill：230400像素独立AP1对照、48帧8色块实际编码核对；每次48次GPU Bloom。首轮超出SDR整数范围正确拒绝，明确clip后交付。',
          'C55完整48帧与384000个非零PCM标量工程包重放相同；预览不改作者内容，实际GIF24帧／4秒；数学控制图明确标识。',
          'r46独立解包／配置／注册：1入口／17模块／84Skill文件／136ZIP项；全部303条旧R与38原关闭条件保留。'],
      '.zh-TW':['CLI0.1.45/local.43原生離線建置安裝：268程式檔一致、84能力；既有公開包保留。',
          '20原始碼專項：獨立公開矩陣／純量傳遞、D50/D60/自定白、nit與alpha、實際GPU、surface CLI、成片／預覽／專案；首輪兩項斷言錯誤保留並修正。',
          f'安裝版20專項通過，{n}項既有色彩／HDR10／光暈／LUT／曲線／渲染／預覽／封裝／schema／佇列相容另列，零失敗／錯誤／略過。',
          'C55真實註冊Skill：230400像素獨立AP1對照、48影格8色塊實際編碼核對；每次48次GPU Bloom。首輪超出SDR整數範圍正確拒絕，明確clip後交付。',
          'C55完整48影格與384000個非零PCM純量專案封裝重播相同；預覽不改作者內容，實際GIF24影格／4秒；數學控制圖明確標示。',
          'r46獨立解壓縮／設定／註冊：1入口／17模組／84Skill檔／136ZIP項；全部303條舊R與38原關閉條件保留。'],
      '.en':['CLI0.1.45/local.43 native offline build/install:268 matching product files,84 capabilities;immutable public downloads retained.',
          '20 source checks:independent published matrices/scalar transfers,D50/D60/custom whites,nits/alpha,actual GPU,surface CLI,encoded output/previews/packages. Initial two oracle/assertion errors retained and corrected.',
          f'20 installed checks and{n} existing color/HDR10/glow/LUT/curves/render/preview/package/schema/queue compatibility checks pass separately,zero failures/errors/skips.',
          'C55 registered Skill:230400-pixel independent AP1 oracle,eight patches over all48 encoded frames;48 actual GPU Bloom calls/render. Initial SDR-range refusal retained;delivery explicitly selects clip.',
          'C55 package replay preserves all48 decoded frames and384000 nonzero PCM scalars;previews preserve author data,GIF24frames/4seconds,mathematical control explicitly labelled.',
          'r46 independent extraction/configuration/registration:1entry/17modules/84Skill files/136ZIP entries;all303 prior R rows and38 original closure conditions retained.']}
    targets=['installation-final-r1','source-r3','installed-compat-r1','case-'+a.case,'case-'+a.case,'kit-r1']
    for suffix in ('','.zh-TW','.en'):
        p='README'+suffix+'.md';s=read(p);old=rows(s,'R');assert len(old)==303
        block='<!-- native-chromatic-current -->\n\n**CLI0.1.45 / alpha.4-local.43 / r46 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n[Workflow / usage](docs/product/CHROMATIC_ADAPTATION.md) · [C55](docs/product/CASES.md#c55-native-chromatic-adaptation) · [Install](docs/releases/CLI_0.1.45_LOCAL.md) · [Evidence](docs/validation/明确白点色适应实测_2026-10-28.md)\n\n'
        block+='![Actual D65 encoded preview]('+media+'actual-preview.gif)\n\n[Actual MP4]('+media+'actual-preview.mp4) · [Signals]('+media+'signals.json) · [Comparison]('+media+'comparison.png) · [Editable package]('+media+'editable-chromatic.aevpkg.zip)\n\n'+limits[suffix]+'\n\n<!-- /native-chromatic-current -->\n\n'
        assert '<!-- native-hdr-metadata-current -->' in s
        s=s.replace('<!-- native-hdr-metadata-current -->',block+'<!-- native-hdr-metadata-history -->',1).replace('<!-- /native-hdr-metadata-current -->','<!-- /native-hdr-metadata-history -->',1)
        s=after(after(s,'F',features[suffix]),'S',services[suffix])
        s=after(s,'R','\n'.join('| R'+str(304+i)+' | 2026-10-28 chromatic | '+d+' | [Evidence](docs/validation/evidence/native-chromatic-20261028-r1/'+t+'/verification.json) |' for i,(d,t) in enumerate(zip(records[suffix],targets))))
        s=s.replace('[r45 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r45.zip)','[r46 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r46.zip)')
        s='\n'.join(line.replace('local.42/final-r1/installed','local.43/final-r1/installed').replace('CLI 0.1.44','CLI 0.1.45') if 'local.42/final-r1/installed' in line else line for line in s.splitlines())+'\n'
        s=s.replace('完整的 70 个功能模块','完整的 71 个功能模块').replace('完整的 70 個功能模組','完整的 71 個功能模組').replace('All 70 functional modules','All 71 functional modules')
        assert len(rows(s,'R'))==309 and all(rows(s,'R')[k]==v for k,v in old.items());write(p,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            p=base+suffix+'.md';s=read(p);relative='CHROMATIC_ADAPTATION.md' if '/product/' in p else '../product/CHROMATIC_ADAPTATION.md'
            block='<!-- community-current -->\n\n**CLI0.1.45 / alpha.4-local.43 / r46 kit · 1 Skill / 17 modules / 84 files.**\n\n'+descriptions[suffix]+'\n\n[Explicit-white workflow]('+relative+')\n\n<!-- /community-current -->'
            s,nsub=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert nsub==1
            if base.endswith('CAPABILITIES'):
                s=after(after(s,'F',features[suffix]),'S',services[suffix])
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,nsub=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if nsub==0:assert key=='native_chromatic_adaptation';s+='\n'+section+'\n'
                s+='\n[CLI0.1.45 exact installed capabilities](chromatic-capabilities-cli-0.1.45.json).\n'
            write(p,s)
    prior=load(ROOT/'docs/validation/evidence/native-hdr-metadata-20261028-r1/installation-final-r1/verification.json')
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
    # Correct two already historical headings instead of silently relabelling them again.
    s=s.replace('CLI0.1.44/local.41/r45:','Historical CLI0.1.42/local.40/r43:').replace('Current CLI0.1.44 adds','Historical CLI0.1.43 adds')
    s=s.replace('[current local installation](../releases/CLI_0.1.44_LOCAL.md)','[that local installation](../releases/CLI_0.1.42_LOCAL.md)')
    for x,y in [('alpha.4-local.42','alpha.4-local.43'),(' / CLI 0.1.44',' / CLI 0.1.45'),('r45.zip','r46.zip'),
                ('package-0.1.44-r45.json','package-0.1.45-r46.json'),(prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(x,y)
    s+='\nCurrent CLI0.1.45: [explicit reference whites / ProPhoto D50 / AP1 D60](CHROMATIC_ADAPTATION.md),[C55](CASES.md#c55-native-chromatic-adaptation),[installation](../releases/CLI_0.1.45_LOCAL.md). Color conversion uses CPU; supported glow/composition can use native OpenCL.\n';write(p,s)
    p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：')
    write(p,s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.45 / local.43 / r46 kit** · [White adaptation](product/CHROMATIC_ADAPTATION.md) · [Install](releases/CLI_0.1.45_LOCAL.md) · [C55](product/CASES.md#c55-native-chromatic-adaptation).\n\n',1))
    p='docs/product/GOAL_GAPS_20261025.md';s=read(p);old=rows(s,'G');line=old['G08'];cells=line.split('|')
    cells[3]=' 明确nit/PQ/HLG、10bitBT2020、SDR预览与HDR10静态SEI核验保留；CLI0.1.45新增Bradford、ProPhoto D50、AP1 D60、自定白点及白点感知GPU光晕，[C55](CASES.md#c55-native-chromatic-adaptation)独立数值、完整音画包重放。 '
    cells[4]=' 参考白点转换不是ICC解析、完整ACES或自动物理白平衡；交付仍D65。峰值测量/非零黑位HLG/动态元数据/感知色域映射、自然HDR监看和完整后端质量仍未闭。 '
    s=s.replace(line,'|'.join(cells),1);assert all(rows(s,'G')[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
    s=s.replace('当前本地 **CLI','此前本地 **CLI')
    s=s.replace('\n\n','\n\n当前本地 **CLI0.1.45 / alpha.4-local.43 / r46 kit**：[G08明确白点与色适应](CHROMATIC_ADAPTATION.md)已贯通ProPhoto D50、AP1 D60、自定xy、nit、效果/中间包/实际预览/工程包及GPU光晕亮度。[C55](CASES.md#c55-native-chromatic-adaptation)与专项/兼容实测保留；完整ICC/ACES/感知色域和监看、38原关闭条件继续建设。\n\n',1);write(p,s)
    p='docs/product/HDR_DISPLAY.md';s=read(p)
    s=s.replace('| `primaries` | D65 `bt709`、`display-p3`、`bt2020`；PQ/HLG 当前要求 `bt2020` |','| `primaries` | `bt709`、`display-p3`、`bt2020` 默认D65；CLI0.1.45另支持ProPhoto D50/AP1 D60和明确white_xy，见[白点适应](CHROMATIC_ADAPTATION.md)；PQ/HLG编码端要求BT.2020/D65 |')
    s=s.replace('参考白单位换算与 D65 基色矩阵','参考白亮度单位换算、RGB基色矩阵与明确白点Bradford适应')
    s+='\nCLI0.1.45: [explicit reference-white conversion](CHROMATIC_ADAPTATION.md) extends source/linear working/effect signals to ProPhoto D50,AP1 D60 and explicit xy. BT.2100 encoded signals/output remain D65; this does not parse ICC or provide full ACES rendering.\n';write(p,s)
    release=f'''# CLI0.1.45 / alpha.4-local.43 — explicit reference-white adaptation

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

Bradford白点适应、ProPhoto D50、线性AP1 D60、浮点中间包/预览/可编辑工程及白点感知GPU光晕。繁體：明確白點與實際預覽，保留既有D65。 English: explicit reference whites across native editing and delivery. Immutable public alpha.3/CLI0.1.2 remains unchanged.

```text
installed: local/agent-ffmpeg/v0.1.0-alpha.4-local.43/final-r1/installed
application ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.43/candidate-r1/bundle.zip
archive bytes: {install['archive_bytes']}
archive SHA256: {install['archive_sha256']}
manifest: {install['manifest_sha256']}
```

268 product Python files match tested source;84 capabilities. One public `$agent-ffmpeg-local-editor`,17 internal modules,84 Skill files. r46 kit contains136 ZIP entries; no source fallback or virtualization.

Use the [offline install/activation workflow](../product/COMMUNITY_LOCAL_DELIVERY.md),then [full configuration/commands](../product/CHROMATIC_ADAPTATION.md). Init/ingest/compose,declare actual source/working/output signals,validate,dry-run,render,inspect the chromatic-transform manifest,preview actual D65 output and export an editable package. `surface export` exposes source/working xy overrides and all new relative RGB choices. Existing NumPy/FFmpeg suffice; no new model/library install. Color math uses CPU; configured composition and white-aware Bloom/Halation use OpenCL.

20 source checks,20 installed checks and{n} installed compatibility checks pass separately. C55 independently checks230400 first-frame pixels,eight patches over all48 frames,and complete48-frame/384000-PCM-scalar package replay. Initial independent-oracle assertions and expected SDR-range refusal are retained;final delivery declares clip. Raw source values do not imply ICC parsing or automatic white balance. AP1 linear configuration is not a full ACES IDT/RRT/ODT/DRT. D65 encoded output,perceptual gamut and natural HDR-monitor limitations are explicit;the whole goal remains ongoing.

[C55 media/GIF/package](../product/CASES.md#c55-native-chromatic-adaptation) · [Evidence](../validation/明确白点色适应实测_2026-10-28.md)
''';write('docs/releases/CLI_0.1.45_LOCAL.md',release)
    p='docs/product/CASES.md';s=read(p)+'\n<a id="c55-native-chromatic-adaptation"></a>\n\n## C55 · 明确参考白点 / 明確參考白點 / Explicit reference-white adaptation\n\n'
    s+='Actual installed CLI0.1.45 and registered unified Skill. Original CC0 RGB16 ProPhoto D50 diagnostic chart and stereo tones are edited in explicit linear AP1 D60,with48 actual GPU Bloom calls/render,and delivered as D65/sRGB ten-bit video. An independent published-matrix/transfer oracle checks all230400 first-surface pixels;neutral/color patches are checked across every encoded frame.\n\n'
    s+=f"Maximum first-surface absolute error: {case['maximum_surface_error']:.12g}; maximum encoded patch luma-code error: {case['maximum_patch_luma_code_error']:.12g}. All48 decoded video frames ({case['decoded_video_bytes']}bytes) and384000 nonzero PCM scalars are identical after editable-package replay. Actual previews preserve author data;GIF24frames/4seconds.\n\n"
    cm='../assets/native-chromatic-20261028-'+a.case+'/'
    s+='![Actual D65 client preview]('+cm+'actual-preview.gif)\n\n'
    s+=' · '.join('['+label+']('+cm+name+')' for label,name in [('Original ProPhoto source','source-prophoto-d50.mkv'),('Actual master','edited-master.mkv'),('Actual MP4','actual-preview.mp4'),('Actual frame','actual-frame.png'),('Signals','signals.json'),('Comparison','comparison.png'),('Editable package','editable-chromatic.aevpkg.zip'),('Manifest','edited-master.mkv.manifest.json'),('Provenance','SOURCE.txt'),('Media hashes','media-manifest.json')])+'\n\n'
    s+='The comparison left panel is an independent mathematical no-adaptation control without Bloom;the right is an actual engine frame with Bloom. This is an explicitly labelled numerical diagnostic,not a matched artistic A/B. No human continuous playback/listening,natural-footage or HDR-monitor acceptance. Reference-white adaptation does not infer physical white balance,parse ICC or implement full ACES rendering.\n\nInitial case-r1 correctly refused out-of-range SDR integers. Case-'+a.case+' explicitly selects final clip;negative/superwhite linear intermediates remain available. Case-r2 retained an independent oracle that omitted final clip;the corrected oracle checks the declared integer boundary. A separate check compares all48x8 frame/patch pairs individually,not only the sequence mean. Initial source-r1 retained two test-only issues:NumPy weak scalar promotion rounded the independent scalar copysign oracle early,and tuple/list metadata was compared without JSON normalization. Source-r3/installed-r1 are the final frozen20-check rounds.\n\n[Workflow](CHROMATIC_ADAPTATION.md) · [Evidence](../validation/明确白点色适应实测_2026-10-28.md).\n';write(p,s)
    e='docs/validation/evidence/native-chromatic-20261028-r1/'
    evidence=f'''# 明确参考白点与色适应实测 · 2026-10-28

CLI0.1.45/local.43：268程序文件与安装版逐字节相同，84能力；统一Skill1入口／17内部模块／84文件。全部38原关闭条件和303条既有README核验记录保留。

| 实际检查 | 结果 | 证据 |
|---|---|---|
| 源码专项 | 20项，0失败／错误／跳过；独立矩阵、标量传递、原有D65、白点／nit／alpha／取消及实际文件 | [source-r3](evidence/native-chromatic-20261028-r1/source-r3/verification.json) |
| 安装版专项 | 20项，另列；真实GPU6次Bloom/Halation、surface CLI、成片／预览／工程包 | [installed-r1](evidence/native-chromatic-20261028-r1/installed-r1/verification.json) |
| 安装版兼容 | {n}项既有色彩／HDR10／光晕／LUT／曲线／渲染／预览／包／schema／队列检查，0失败／错误／跳过 | [compat](evidence/native-chromatic-20261028-r1/installed-compat-r1/verification.json) |
| C55独立数值 | 首帧230400像素，最大误差{case['maximum_surface_error']:.12g}；8色块全48帧，最大亮度码误差{case['maximum_patch_luma_code_error']:.12g} | [case](evidence/native-chromatic-20261028-r1/case-{a.case}/verification.json) |
| C55包往返 | 全48帧{case['decoded_video_bytes']}字节及384000个非零PCM标量相同；两次各48次实际GPU光晕 | [checks](evidence/native-chromatic-20261028-r1/case-{a.case}/checks.json) |
| 逐帧独立色块核对 | 48×8共384次，最大亮度码误差{oracle['maximum_luma_code_error']:.12g}，包含明确SDR截断；不只比较全序列均值 | [independent oracle](evidence/native-chromatic-20261028-r1/case-{a.case}/independent-every-frame-patches.json) |
| 实际预览 | PNG／MP4／GIF，24帧4000ms，不改作者工程 | [media hashes](../assets/native-chromatic-20261028-{a.case}/media-manifest.json) |
| 原生离线安装 | 完整ZIP校验、离线安装、全部源码一致；四个既有语音／翻译包重新激活 | [install](evidence/native-chromatic-20261028-r1/installation-final-r1/verification.json) |
| r46独立工具包 | 136ZIP项、84Skill文件、独立解压／配置／注册／可移植包验证，不改真实发现路径 | [kit](evidence/native-chromatic-20261028-r1/kit-r1/verification.json) |

保留失败：[source-r1](evidence/native-chromatic-20261028-r1/source-r1/verification.json)含两项测试断言问题：NumPy弱标量规则让独立copysign参考提前变成Float32；内存tuple被错误地与JSON list直接比较。修正为Python binary64标量计算及规范化元组比较，未放宽数值断言。source-r2的19项是中间冻结，新增surface CLI后最终source-r3为20项。C55 [case-r1](evidence/native-chromatic-20261028-r1/case-r1/verification.json)正确拒绝超出SDR整数域的RGB；最终工程显式选择clip，不修改产品默认拒绝行为。

独立依据：[W3C CSS Color4](https://www.w3.org/TR/css-color-4/)的ProPhoto D50／Bradford D50→D65／有理数BT.709矩阵，以及[Academy ACEScg/AP1](https://docs.acescentral.com/encodings/acescg/)基色与D60。测试使用公开参考常数，与产品从xy推导矩阵的实现分开；标量参考避免调用产品传递函数。GPU专项使用当前原生OpenCL0.0，不能推论跨设备逐位一致。

Case-r2还保留了独立参考漏算最终clip引起的色块断言失败。逐值分析见[oracle-analysis](evidence/native-chromatic-20261028-r1/case-r2/oracle-analysis.json)；修正参考边界后原1.6亮度码阈值不变，没有调整产品转换行为。

图册左侧为无白点适应、无Bloom的独立数学控制，右侧为实际引擎输出；不是艺术质量同条件A/B。参考白点不是场景光源探测或自动白平衡。颜色计算CPU，光晕／合成可GPU，编码另计。未做人工连续播放／听审／自然素材或HDR监看验收。ICC解析、完整ACES IDT/RRT/ODT/DRT、感知色域映射和原38项完整目标继续建设。

[完整命令与配置](../product/CHROMATIC_ADAPTATION.md) · [C55](../product/CASES.md#c55-native-chromatic-adaptation) · [安装](../releases/CLI_0.1.45_LOCAL.md)
''';write('docs/validation/明确白点色适应实测_2026-10-28.md',evidence)
    report=dict(status='updated',languages=3,F=71,S=26,K=17,R=309,prior_R_retained=303,G_closure_cells_retained=38,tests=counts,case=a.case)
    write(str(out.relative_to(ROOT)/'verification.json'),json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
