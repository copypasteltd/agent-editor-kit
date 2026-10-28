"""Maintain trilingual entrypoints, exact capabilities and all historic R/G cells."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-metadata-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def after(s,p,text):
    m=list(re.finditer(r'^\| '+p+r'\d+\s*\|.*$',s,re.M))[-1];return s[:m.end()]+'\n'+text+s[m.end():]
def main():
    out=BASE/'documentation-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/'case-r2/verification.json')
    assert case['status']=='passed' and all(c['ok'] for c in case['checks'])
    for name,n in [('source-r3',21),('installed-r1',21),('installed-compat-r1',105)]:
        r=load(BASE/name/'verification.json');assert r['status']=='passed' and r['tests']==n and r['failures']==r['errors']==r['skipped']==0
    capture='docs/product/hdr-metadata-capabilities-cli-0.1.44.json'
    (ROOT/capture).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==83
    descriptions={
      '':'新增**HDR10母版显示与MaxCLL/MaxFALL静态元数据**：明确xy/nit单位，实际写入HEVC SEI，发布前核验解码帧；支持可编辑工程包，继续使用GPU合成和独立SDR预览。',
      '.zh-TW':'新增**HDR10母版顯示與MaxCLL/MaxFALL靜態中繼資料**：明確xy/nit單位，實際寫入HEVC SEI，發布前核驗解碼影格；支援可編輯專案封裝，沿用GPU合成和獨立SDR預覽。',
      '.en':'Added **HDR10 mastering-display and MaxCLL/MaxFALL static metadata**: exact xy/nit units, actual HEVC SEI writing and decoded-frame verification before publication; editable packages, GPU composition and separate SDR viewing copies.'}
    limits={
      '':'21项源码、21项安装版专项与105项安装版兼容检查分别通过。C54独立核对全部48帧SEI；工程包重放全部视频帧和384000个PCM标量相同。产品默认核验前32个视频包解出的帧；数值为作者声明，不是自动峰值测量。x265编码CPU、合成GPU。动态HDR、ICC/监看、自然质量及原38项完整目标继续建设。',
      '.zh-TW':'21項原始碼、21項安裝版專項與105項安裝版相容檢查分別通過。C54獨立核對全部48影格SEI；專案封裝重播全部視訊影格和384000個PCM純量相同。產品預設核驗前32個視訊封包解出的影格；數值為作者聲明，並非自動峰值量測。x265編碼CPU、合成GPU。動態HDR、ICC/監看、自然品質及原38項完整目標持續建置。',
      '.en':'21 source checks,21 installed checks and105 installed compatibility checks pass separately. C54 independently checks all48 frames of SEI; package replay preserves every decoded video frame and384000 PCM scalars. Production verifies frames decoded from the first32 video packets. Values are author declarations, not measured peaks. x265 encoding uses CPU; composition uses GPU. Dynamic HDR,ICC/monitoring,natural quality and all38 original goal closure conditions remain ongoing.'}
    features={
      '':'| F70 | HDR10静态元数据交付 | 母版RGB/白点xy、最小/最大nit、MaxCLL/MaxFALL → 实际HEVC SEI与解码核验清单。 | `settings.output.hdr10; validate; render; convert` | 明确原生PQ/BT2020 NCL有限量程、libx265/10bit420/MP4或MKV；作者声明、前32包核验。 |',
      '.zh-TW':'| F70 | HDR10靜態中繼資料交付 | 母版RGB/白點xy、最小/最大nit、MaxCLL/MaxFALL → 實際HEVC SEI與解碼核驗清單。 | `settings.output.hdr10; validate; render; convert` | 明確原生PQ/BT2020 NCL有限範圍、libx265/10bit420/MP4或MKV；作者聲明、前32封包核驗。 |',
      '.en':'| F70 | HDR10 static metadata delivery | Mastering RGB/white xy,min/max nits,MaxCLL/MaxFALL → actual HEVC SEI and decoded verification receipt. | `settings.output.hdr10; validate; render; convert` | Explicit native PQ/BT2020 NCL limited range,libx265/10bit420/MP4 or MKV; author declarations,prefix32-packet verification. |'}
    services={
      '':'| S25 | x265 HDR10静态SEI服务 | 固定语法参数写入＋原生ffprobe解码逐有理数核对，发布前失败关闭。 | 已有原生FFmpeg/libx265/ffprobe；无新模型。 | `render` | 编码CPU；观察解码前缀，非全片认证/峰值测量。 |',
      '.zh-TW':'| S25 | x265 HDR10靜態SEI服務 | 固定語法參數寫入＋原生ffprobe解碼逐有理數核對，發布前失敗關閉。 | 既有原生FFmpeg/libx265/ffprobe；無新模型。 | `render` | 編碼CPU；觀察解碼前綴，非全片認證/峰值量測。 |',
      '.en':'| S25 | x265 static HDR10 SEI service | Fixed encoder grammar plus exact rational checks of actual native ffprobe decoded side data before publication. | Existing native FFmpeg/libx265/ffprobe; no new model. | `render` | CPU encoding; observed prefix,not whole-movie certification or peak measurement. |'}
    records={
      '':['CLI0.1.44/local.42原生构建安装：267程序文件一致、83能力，旧公开版本保留。',
          '21源码专项：单位/几何/未知亮度、实际MP4/MKV SEI、无SEI拒绝覆盖、预览与包迁移；初轮白点映射/测试时间戳错误修正并保留失败。',
          '最终安装版21专项通过，105既有HDR/渲染/预览/schema/队列兼容回归另列，零失败/错误/跳过。',
          'C54真实Skill/GPU合成/CPU HEVC，默认前32包核验通过；独立检查全部48帧SEI与VUI。',
          'C54工程包重放全部48帧与384000 PCM标量相同；独立SDR预览无HDR SEI，GIF24帧/4秒。',
          'r45独立解包/配置/注册：1入口/17内部模块/83Skill文件/134ZIP项，现有297条R和38原关闭条件全部保留。'],
      '.zh-TW':['CLI0.1.44/local.42原生建置安裝：267程式檔一致、83能力，舊公開版本保留。',
          '21原始碼專項：單位/幾何/未知亮度、實際MP4/MKV SEI、無SEI拒絕覆蓋、預覽與封裝遷移；首輪白點映射/測試時間戳錯誤修正並保留失敗。',
          '最終安裝版21專項通過，105既有HDR/渲染/預覽/schema/佇列相容回歸另列，零失敗/錯誤/略過。',
          'C54真實Skill/GPU合成/CPU HEVC，預設前32封包核驗通過；獨立檢查全部48影格SEI與VUI。',
          'C54專案封裝重播全部48影格與384000 PCM純量相同；獨立SDR預覽無HDR SEI，GIF24影格/4秒。',
          'r45獨立解壓縮/設定/註冊：1入口/17內部模組/83Skill檔/134ZIP項，既有297條R和38原關閉條件全部保留。'],
      '.en':['CLI0.1.44/local.42 native build/install:267 matching product files,83 capabilities;published releases retained.',
          '21 source checks cover exact units/geometry/unknown light,real MP4/MKV SEI,missing-SEI publication refusal,preview/package. Initial white-point mapping and test timestamp errors retained and corrected.',
          'Final installed21 checks and105 existing HDR/render/preview/schema/queue regressions pass separately,zero failures/errors/skips.',
          'C54 registered Skill,actual GPU composition/CPU HEVC;production32-packet prefix and independent all48-frame SEI/VUI verification.',
          'C54 package replay preserves all48 decoded frames and384000 PCM scalars;separate SDR preview has no HDR SEI,GIF24frames/4seconds.',
          'r45 independent extraction/configuration/registration:1entry/17modules/83Skill files/134ZIP entries;all297 prior R rows and38 original closure conditions retained.']}
    targets=['installation-final-r1','source-r3','installed-compat-r1','case-r2','case-r2','kit-r1']
    for suffix in ('','.zh-TW','.en'):
        p='README'+suffix+'.md';s=read(p);old=rows(s,'R');assert len(old)==297
        block='<!-- native-hdr-metadata-current -->\n\n**CLI0.1.44 / alpha.4-local.42 / r45 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n[Workflow / usage](docs/product/HDR_METADATA.md) · [C54](docs/product/CASES.md#c54-native-hdr10-metadata) · [Install](docs/releases/CLI_0.1.44_LOCAL.md) · [Evidence](docs/validation/HDR10静态元数据实测_2026-10-28.md)\n\n![Actual mapped SDR preview; separate HDR10 master](docs/assets/native-hdr-metadata-20261028-r2/sdr-view.gif)\n\n[HDR10 master](docs/assets/native-hdr-metadata-20261028-r2/hdr10-master.mkv) · [SDR preview](docs/assets/native-hdr-metadata-20261028-r2/sdr-preview.mp4) · [Declared values](docs/assets/native-hdr-metadata-20261028-r2/declaration.json) · [Editable package](docs/assets/native-hdr-metadata-20261028-r2/editable-hdr10.aevpkg.zip)\n\n'+limits[suffix]+'\n\n<!-- /native-hdr-metadata-current -->\n\n'
        s=s.replace('<!-- native-speech-enhancement-current -->',block+'<!-- native-speech-enhancement-history -->',1).replace('<!-- /native-speech-enhancement-current -->','<!-- /native-speech-enhancement-history -->',1)
        s=after(after(s,'F',features[suffix]),'S',services[suffix])
        s=after(s,'R','\n'.join('| R'+str(298+i)+' | 2026-10-28 HDR10 SEI | '+d+' | [Evidence](docs/validation/evidence/native-hdr-metadata-20261028-r1/'+t+'/verification.json) |' for i,(d,t) in enumerate(zip(records[suffix],targets))))
        s=s.replace('[r44 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r44.zip)','[r45 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r45.zip)')
        s='\n'.join(line.replace('local.41/final-r3/installed','local.42/final-r1/installed').replace('CLI 0.1.41','CLI 0.1.44') if 'local.41/final-r3/installed' in line else line for line in s.splitlines())+'\n'
        s=s.replace('完整的 69 个功能模块','完整的 70 个功能模块').replace('完整的 69 個功能模組','完整的 70 個功能模組').replace('All 69 functional modules','All 70 functional modules')
        assert len(rows(s,'R'))==303 and all(rows(s,'R')[k]==v for k,v in old.items());write(p,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            p=base+suffix+'.md';s=read(p);relative='HDR_METADATA.md' if '/product/' in p else '../product/HDR_METADATA.md'
            block='<!-- community-current -->\n\n**CLI0.1.44 / alpha.4-local.42 / r45 kit · 1 Skill / 17 modules / 83 files.**\n\n'+descriptions[suffix]+'\n\n[HDR10 static metadata workflow]('+relative+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            if base.endswith('CAPABILITIES'):
                s=after(after(s,'F',features[suffix]),'S',services[suffix])
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if n==0:assert key=='native_hdr10_static_metadata';s+='\n'+section+'\n'
                s+='\n[CLI0.1.44 exact installed capabilities](hdr-metadata-capabilities-cli-0.1.44.json).\n'
            write(p,s)
    prior=load(ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1/installation-final-r3/verification.json')
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
    for a,b in [('alpha.4-local.41','alpha.4-local.42'),('0.1.43','0.1.44'),('r44','r45'),
                (prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256']),
                ('local.42/final-r3/','local.42/final-r1/'),('local.42/candidate-r3/','local.42/candidate-r1/')]:s=s.replace(a,b)
    write(p,s)
    p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：')
    write(p,s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.44 / local.42 / r45 kit** · [HDR10 static SEI](product/HDR_METADATA.md) · [Install](releases/CLI_0.1.44_LOCAL.md) · [C54](product/CASES.md#c54-native-hdr10-metadata).\n\n',1))
    p='docs/product/GOAL_GAPS_20261025.md';s=read(p);old=rows(s,'G');line=old['G08'];cells=line.split('|')
    cells[3]=' 明确nit/PQ/HLG、线性光合成、10bitBT2020及SDR预览保留；CLI0.1.44新增HDR10静态母版/CLL实际SEI与解码前缀核验，[C54](CASES.md#c54-native-hdr10-metadata)全48帧独立核对、工程包完整音画重放。 '
    cells[4]=' 作者声明不是内容峰值测量；默认核验前32视频包解码帧。ICC/色适应/非零黑位HLG/动态元数据、感知色域映射、自然HDR监看和完整后端效果质量仍未闭。 '
    s=s.replace(line,'|'.join(cells),1);assert all(rows(s,'G')[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
    write(p,s)
    release=f'''# CLI0.1.44 / alpha.4-local.42 — actual HDR10 static SEI

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

HDR10母版显示/MaxCLL/MaxFALL明确声明、实际HEVC SEI写入、发布前解码核验、工程包与GPU合成。繁體：明確母版聲明與實際SEI核驗。 English: declared HDR10 static metadata with actual HEVC and decoded verification. This local compiled build preserves immutable public alpha.3/CLI0.1.2.

```text
installed: local/agent-ffmpeg/v0.1.0-alpha.4-local.42/final-r1/installed
application ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.42/candidate-r1/bundle.zip
archive bytes: {install['archive_bytes']}
archive SHA256: {install['archive_sha256']}
manifest: {install['manifest_sha256']}
```

267 product Python files match tested source;83 capabilities. One public `$agent-ffmpeg-local-editor`,17 internal modules,83 Skill files. r45 kit has134 ZIP entries; no source fallback or virtualization.

Use the [offline install/activation workflow](../product/COMMUNITY_LOCAL_DELIVERY.md), then [HDR10 configuration and commands](../product/HDR_METADATA.md). Init/ingest/compose,declare all source/working/output signals and `settings.output.hdr10`,validate,dry-run,render,inspect `delivery.hdr10_static_metadata`,generate a separate SDR viewing copy and export an editable package. Existing native FFmpeg/libx265/ffprobe handle encoding/probing; no model download. Actual composition can use OpenCL; x265 uses CPU.

21 source checks,21 installed checks and105 installed compatibility checks pass separately. C54 checks all48 frames independently and full package video/384000 PCM replay. Production verification reads32 video packets,not a whole-movie certificate. Declarations are not peak measurements or calibration. Dynamic HDR,ICC/monitoring and full product goal remain ongoing.

[C54 master/SDR/GIF/package](../product/CASES.md#c54-native-hdr10-metadata) · [Evidence](../validation/HDR10静态元数据实测_2026-10-28.md)
''';write('docs/releases/CLI_0.1.44_LOCAL.md',release)
    p='docs/product/CASES.md';s=read(p)+'\n<a id="c54-native-hdr10-metadata"></a>\n\n## C54 · 实际HDR10 SEI / 實際HDR10 SEI / Actual HDR10 static metadata\n\n'
    s+='Actual installed CLI0.1.44 and registered unified Skill. C50 original contributor-generated CC0 chart,SDR badge and stereo tones are imported as an editable project. Native PQ display-linear edit,48 actual GPU glow calls per render and CPU x265 ten-bit420 output. Declared P3-D65 mastering display0.0001–1000nits,MaxCLL1000/MaxFALL400 are not measured peaks.\n\n'
    s+='Production verifies frames decoded from the first32 packets; C54 separately checks all48 frames with an independent rational oracle. All48 decoded frames and384000 nonzero PCM scalars match after package import/render. The separate SDR preview has BT.709 tags and no HDR static SEI. GIF24frames/4seconds; static figure reviewed,no human continuous playback/listening or HDR monitor acceptance.\n\n'
    media='../assets/native-hdr-metadata-20261028-r2/'
    s+='![Actual SDR view; separate HDR master]('+media+'sdr-view.gif)\n\n'
    s+=' · '.join('['+label+']('+media+name+')' for label,name in [('HDR10 master','hdr10-master.mkv'),('Actual SDR MP4','sdr-preview.mp4'),('SDR frame','sdr-frame.png'),('Declared values','declaration.json'),('Master manifest','hdr10-master.mkv.manifest.json'),('Editable package','editable-hdr10.aevpkg.zip'),('Selection sheet','comparison.png'),('Provenance','SOURCE.txt'),('Media hashes','media-manifest.json')])+'\n\n'
    s+='[Workflow](HDR_METADATA.md) · [Evidence](../validation/HDR10静态元数据实测_2026-10-28.md). Initial case r1 retained: its author-byte check spanned the normal render operation timestamp. The corrected r2 snapshots bytes immediately before previews. Initial source round also retained the fixed ffprobe white-point mapping failure; no failed round is counted as final success.\n';write(p,s)
    evidence='''# HDR10静态元数据真实交付核验 · 2026-10-28

CLI0.1.44/local.42，267源码/安装文件一致，83能力；统一Skill1入口/17模块/83文件。所有新记录在[evidence目录](evidence/native-hdr-metadata-20261028-r1/)。

| 验证 | 实际结果 | 证据 |
|---|---|---|
| 最终源码 | 21专项，0失败/错误/跳过；冻结字节一致 | [source-r3](evidence/native-hdr-metadata-20261028-r1/source-r3/verification.json) |
| 安装版专项 | 21专项，0失败/错误/跳过；实际MP4/MKV HEVC、未知CLL零值、无SEI拒绝替换旧成片、完整包迁移 | [installed-r1](evidence/native-hdr-metadata-20261028-r1/installed-r1/verification.json) |
| 安装版兼容 | 105既有HDR/渲染/预览/schema/队列检查，另列 | [compat](evidence/native-hdr-metadata-20261028-r1/installed-compat-r1/verification.json) |
| 真实Skill C54 | 48帧/12FPS/4秒，两次48次GPU光效；产品前32包核验与独立48帧SEI数值检查均通过 | [case-r2](evidence/native-hdr-metadata-20261028-r1/case-r2/verification.json) |
| 工程包音画 | 48帧33177600字节及384000个PCM标量全部相同 | [checks](evidence/native-hdr-metadata-20261028-r1/case-r2/checks.json) |
| 客户SDR预览 | 无HDR SEI；PNG/GIF/MP4明确映射，GIF24帧/4000ms | [public manifest](../assets/native-hdr-metadata-20261028-r2/media-manifest.json) |
| 本地安装 | 原生离线构建/安装，源码文件一致 | [installation](evidence/native-hdr-metadata-20261028-r1/installation-final-r1/verification.json) |
| r45独立注册 | 独立解压、配置与临时联接，1入口/17模块；不改真实发现路径 | [kit](evidence/native-hdr-metadata-20261028-r1/kit-r1/verification.json) |

失败记录完整保留：[source-r1](evidence/native-hdr-metadata-20261028-r1/source-r1/verification.json)白点字段映射错误，已修正为实际ffprobe `white_point_x/y`；该轮还把测试保存工程引起的updated_at变化误算为产品改写。[case-r1](evidence/native-hdr-metadata-20261028-r1/case-r1/verification.json)检查跨越正常渲染事务时间戳，r2改为预览前冻结；产品无需为该测试假设改变写入逻辑。source-r2是中间冻结字节，不当作最终安装版通过数。

核验依据：[x265官方静态元数据参数](https://x265.readthedocs.io/en/4.1/cli.html#cmdoption-master-display)、[FFmpeg libx265](https://www.ffmpeg.org/ffmpeg-codecs.html#libx265)，以及实际本机编码/解码。明确定义xy=1/50000、nit=1/10000，无静默取整；MaxCLL/MaxFALL整数0表示未知。固定参数语法拒绝任意编码器开关。

声明值不等于峰值测量/母版监视器校准；产品前缀核验不等于全片SEI认证。此例是原创诊断图和音调，不是自然HDR作品或听审。静态图已查看，未做人工连续播放/听审。GPU用于合成，x265编码及颜色数学CPU。ICC、色适应、动态HDR10+、Dolby Vision、非零黑位HLG、感知色域映射、自然HDR监看与完整剪映等价仍未完成。38原关闭条件未改。

[完整使用流程](../product/HDR_METADATA.md) · [C54](../product/CASES.md#c54-native-hdr10-metadata) · [本地版本](../releases/CLI_0.1.44_LOCAL.md)
''';write('docs/validation/HDR10静态元数据实测_2026-10-28.md',evidence)
    write('docs/validation/evidence/native-hdr-metadata-20261028-r1/documentation-r1/verification.json',json.dumps(dict(status='updated',languages=3,F=70,S=25,K=17,R=303,prior_R_retained=297,G_closure_cells_retained=38),indent=2)+'\n')
    print(json.dumps(dict(status='documented',F=70,S=25,R=303,languages=3)))
if __name__=='__main__':main()
