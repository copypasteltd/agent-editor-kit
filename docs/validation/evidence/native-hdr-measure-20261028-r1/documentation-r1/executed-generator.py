"""Document actual all-frame metering; retain historical R rows and G closure cells."""
from pathlib import Path
import argparse, hashlib, json, re

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-measure-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d+)\s*\|.*$',s,re.M)}
def append_row(s,prefix,text):
    match=list(re.finditer(r'^\| '+prefix+r'\d+\s*\|.*$',s,re.M))[-1]
    return s[:match.end()]+'\n'+text+s[match.end():]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);a=ap.parse_args();assert a.case.replace('-','').isalnum()
    out=BASE/'documentation-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    installed=load(BASE/'installation-final-r1/verification.json');case=load(BASE/('case-'+a.case)/'verification.json')
    assert installed['source_file_count']==275 and installed['capability_count']==88 and case['status']=='passed'
    counts={}
    for run in ('source-r4','installed-r1','installed-compat-r1'):
        result=load(BASE/run/'verification.json');assert result['status']=='passed' and result['failures']==result['errors']==result['skipped']==0
        counts[run]=result['tests']
    assert counts=={'source-r4':19,'installed-r1':19,'installed-compat-r1':352}
    capture='docs/product/hdr-measure-capabilities-cli-0.1.49.json';(ROOT/capture).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==88
    descriptions={
        '':'新增**全帧 HDR 光量测量与色彩裁切汇总**：实际作者时间线、明确nit、MaxRGB与CIE Y分别报告、峰值位置/最大帧平均/精确时长加权、可选有效画面范围。测量与正式渲染共用实际RGB16输入路径；中间包补齐所有帧的转换收据。',
        '.zh-TW':'新增**全影格 HDR 光量測量與色彩裁切彙總**：實際作者時間線、明確nit、MaxRGB與CIE Y分別報告、峰值位置／最大影格平均／精確時長加權、可選有效畫面範圍。測量與正式算繪共用實際RGB16輸入路徑；中間包補齊所有影格轉換收據。',
        '.en':'Added **all-frame HDR light metering and colour-clipping ledgers**: actual authored timeline,explicit nits,separate MaxRGB/CIE Y,peak locations/maximum frame averages/exact exposure weighting,and explicit active regions. Metering shares the real RGB16 encoder-input path;intermediate bundles now retain all-frame conversion receipts.'}
    detail={
        '':'19项源码专项、19项安装专项和352项安装兼容分别通过。C59以独立公式核对全部48帧/11059200像素与RGB16输入摘要，真实PQ成片完整音画及测量工程包重放一致；另验48次实际GPU Bloom与原生ICC软打样的测量/渲染输入相同。不是编码后峰值、物理显示器或艺术质量验收。',
        '.zh-TW':'19項原始碼專項、19項安裝專項與352項安裝相容分別通過。C59以獨立公式核對全部48影格／11059200像素及RGB16輸入摘要，真實PQ成片完整音畫與測量專案重播一致；另驗48次實際GPU Bloom及原生ICC軟打樣的測量／算繪輸入相同。非編碼後峰值、實體顯示器或藝術品質驗收。',
        '.en':'19 source checks,19 installed checks and352 installed compatibility checks pass separately. C59 independently checks all48 frames/11059200 pixels and the RGB16 input digest,then replays the complete PQ master/audio/measurements after package import. Another48-frame actual GPU Bloom/native ICC proof run has identical meter/render input. No post-codec peak,physical display or artistic-quality acceptance is claimed.'}
    features={
        '':'| F75 | 全帧HDR光量与转换收据 | 明确nit、实际时间线与RGB16边界；MaxRGB/CIE Y峰值、帧平均、位置/范围/时长；原生中间包所有帧裁切汇总。 | `native_hdr_light_measurement; surface measure; surface export; render` | CPU测量、独立GPU剪辑；不推断监看亮度、不自动写SEI、不冒充编码后测量。 |',
        '.zh-TW':'| F75 | 全影格HDR光量與轉換收據 | 明確nit、實際時間線與RGB16邊界；MaxRGB/CIE Y峰值、影格平均、位置／範圍／時長；原生中間包全影格裁切彙總。 | `native_hdr_light_measurement; surface measure; surface export; render` | CPU測量、獨立GPU剪輯；不推斷監看亮度、不自動寫SEI、不冒充編碼後測量。 |',
        '.en':'| F75 | All-frame HDR light and conversion receipts | Explicit nits,actual timeline/RGB16 edge;MaxRGB/CIE Y peaks,frame averages,locations/regions/exposure;all-frame native-bundle clipping totals. | `native_hdr_light_measurement; surface measure; surface export; render` | CPU meter,separate GPU editing;no inferred monitor brightness,implicit SEI or post-codec measurement claim. |'}
    services={
        '':'| S30 | 光量诊断与全帧色彩审计 | 只读原生时间线、可取消分块测量、完整RGB16摘要、所有帧转换收据；实际源/GPU资源回收。 | 既有FFmpeg/NumPy与可选OpenCL；不下载模型。 | `surface measure; surface export; render` | 部分帧或有效区域不代表整片全画布；768MiB自有算子估算非总RSS/VRAM。 |',
        '.zh-TW':'| S30 | 光量診斷與全影格色彩稽核 | 唯讀原生時間線、可取消分塊測量、完整RGB16摘要、全影格轉換收據；實際來源／GPU資源回收。 | 既有FFmpeg／NumPy與可選OpenCL；不下載模型。 | `surface measure; surface export; render` | 部分影格或有效區域不代表整片全畫布；768MiB自有算子估算非總RSS／VRAM。 |',
        '.en':'| S30 | Light diagnostics and all-frame colour audit | Readonly native timeline,cancellable tiled meter,complete RGB16 digest,all-frame conversion receipts and actual source/GPU cleanup. | Existing FFmpeg/NumPy,optional OpenCL;no new model download. | `surface measure; surface export; render` | Partial frames/active area do not certify the full canvas;768MiB owned-operator estimate is not total RSS/VRAM. |'}
    records={
        '':['CLI0.1.49/local.47：275个产品Python文件与受测安装版相同；88能力、1公开Skill/17模块/88文件。','19项源码专项：独立PQ/HLG/MaxRGB/CIE Y、时长/范围/alpha、真实CLI只读/取消、首帧裁切末帧正常。','19项安装专项及352项安装兼容分别通过；显示映射/原生软打样测量与正式渲染RGB16摘要相同。','C59：独立全部48帧/11059200像素公式与RGB16输入摘要；真实PQ成片66355200视频字节和384000非零PCM标量。','C59：工程包全音画/所有测量重放相同；另有48帧真实GPU Bloom/原生软打样输入同正式渲染；实际MP4/GIF。'],
        '.zh-TW':['CLI0.1.49/local.47：275個產品Python檔案與受測安裝版相同；88能力、1公開Skill／17模組／88檔案。','19項原始碼專項：獨立PQ／HLG／MaxRGB／CIE Y、時長／範圍／alpha、真實CLI唯讀／取消、首影格裁切末影格正常。','19項安裝專項與352項安裝相容分別通過；顯示映射／原生軟打樣測量及正式算繪RGB16摘要相同。','C59：獨立全部48影格／11059200像素公式與RGB16輸入摘要；真實PQ成片66355200影片位元組及384000非零PCM標量。','C59：專案全音畫／全部測量重播一致；另有48影格真實GPU Bloom／原生軟打樣輸入同正式算繪；實際MP4／GIF。'],
        '.en':['CLI0.1.49/local.47:275 product Python files match tested installation;88 capabilities,one public Skill/17 modules/88 files.','19 source checks:independent PQ/HLG/MaxRGB/CIE Y,exposure/regions/alpha,real readonly CLI/cancellation,and early clipping with a clear last frame.','19 installed checks and352 separate installed compatibility checks;display-map/native-proof meter and actual render RGB16 digests agree.','C59:independent equations for all48 frames/11059200 pixels and RGB16 input digest;actual PQ master66355200 video bytes and384000 nonzero PCM scalars.','C59:complete media/all measurements replay after package import;another48-frame actual GPU Bloom/native-proof run matches render input;actual MP4/GIF.']}
    targets=['installation-final-r1','source-r4','installed-compat-r1','case-'+a.case,'case-'+a.case]
    public='docs/assets/native-hdr-measure-20261029-'+a.case+'/'
    for suffix in descriptions:
        p='README'+suffix+'.md';s=read(p);old=rows(s,'R');assert len(old)==327
        block='<!-- native-hdr-measure-current -->\n\n**CLI0.1.49 / alpha.4-local.47 / r50 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n'
        block+='[Workflow](docs/product/HDR_MEASUREMENT.md) · [C59](docs/product/CASES.md#c59-native-hdr-measurement) · [Install](docs/releases/CLI_0.1.49_LOCAL.md) · [Evidence](docs/validation/全帧HDR光量与裁切汇总实测_2026-10-29.md)\n\n'
        block+='![Actual SDR view of HDR metering case]('+public+'actual-preview.gif)\n\n'+detail[suffix]+'\n\n<!-- /native-hdr-measure-current -->\n\n'
        s=s.replace('native-icc-output-current','native-icc-output-history');s=s.replace('<!-- native-icc-output-history -->',block+'<!-- native-icc-output-history -->',1)
        s=append_row(append_row(s,'F',features[suffix]),'S',services[suffix])
        s=append_row(s,'R','\n'.join('| R'+str(328+i)+' | 2026-10-29 HDR meter | '+text+' | [Evidence](docs/validation/evidence/native-hdr-measure-20261028-r1/'+target+'/verification.json) |' for i,(text,target) in enumerate(zip(records[suffix],targets))))
        s=s.replace('[r49 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r49.zip)','[r50 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r50.zip)')
        s=s.replace('完整的 74 个功能模块','完整的 75 个功能模块').replace('完整的 74 個功能模組','完整的 75 個功能模組').replace('All 74 functional modules','All 75 functional modules')
        s='\n'.join(line.replace('local.46/final-r1/installed','local.47/final-r1/installed').replace('CLI 0.1.48','CLI 0.1.49') if 'local.46/final-r1/installed' in line and not line.startswith('| R') else line for line in s.splitlines())+'\n'
        assert len(rows(s,'R'))==332 and all(rows(s,'R')[key]==value for key,value in old.items());write(p,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            p=base+suffix+'.md';s=read(p);rel='HDR_MEASUREMENT.md' if '/product/' in p else '../product/HDR_MEASUREMENT.md'
            block='<!-- community-current -->\n\n**CLI0.1.49 / alpha.4-local.47 / r50 kit · 1 Skill / 17 modules / 88 files.**\n\n'+descriptions[suffix]+'\n\n[Light metering workflow]('+rel+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            if base.endswith('CAPABILITIES'):
                s=append_row(append_row(s,'F',features[suffix]),'S',services[suffix])
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if not n:assert key=='native_hdr_light_measurement';s+='\n'+section+'\n'
                s+='\n[CLI0.1.49 exact installed capabilities](hdr-measure-capabilities-cli-0.1.49.json).\n'
            write(p,s)
    prior=load(ROOT/'docs/validation/evidence/native-icc-output-20261028-r1/installation-final-r1/verification.json')
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p)
    for old,new in [('**`v0.1.0-alpha.4-local.46` / CLI 0.1.48**','**`v0.1.0-alpha.4-local.47` / CLI 0.1.49**'),('local.46/final-r1/installed','local.47/final-r1/installed'),('local.46/candidate-r1/bundle.zip','local.47/candidate-r1/bundle.zip'),('r49.zip','r50.zip'),('package-0.1.48-r49.json','package-0.1.49-r50.json'),(prior['archive_sha256'],installed['archive_sha256']),(prior['manifest_sha256'],installed['manifest_sha256'])]:s=s.replace(old,new)
    write(p,s+'\nCurrent CLI0.1.49: [all-frame light metering](HDR_MEASUREMENT.md) · [C59](CASES.md#c59-native-hdr-measurement) · [Install](../releases/CLI_0.1.49_LOCAL.md).\n')
    p='docs/README.md';s=read(p).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：');write(p,s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.49 / local.47 / r50 kit** · [Light measurement](product/HDR_MEASUREMENT.md) · [Install](releases/CLI_0.1.49_LOCAL.md) · [C59](product/CASES.md#c59-native-hdr-measurement).\n\n',1))
    p='docs/product/GOAL_GAPS_20261025.md';s=read(p);old=rows(s,'G');cells=old['G08'].split('|')
    cells[3]+=' CLI0.1.49新增真实全帧RGB16交付前光量测量、MaxRGB/CIE Y/范围/时长、首末事件与所有帧裁切账本及实际工程包重放。 '
    cells[4]=cells[4].replace('峰值测量/动态元数据','编码后/物理峰值测量/动态元数据').replace('浮点中间包目前为末帧边界收据，逐帧裁切汇总待补。','浮点中间包现有逐帧裁切汇总，旧末帧收据保留且明确范围；不推断旧包缺失历史。')
    s=s.replace(old['G08'],'|'.join(cells));new=rows(s,'G');assert len(new)==38 and all(new[k].split('|')[-3]==v.split('|')[-3] for k,v in old.items())
    write(p,s.replace('\n\n','\n\n当前本地 **CLI0.1.49 / local.47 / r50 kit**：[全帧HDR光量与裁切汇总](HDR_MEASUREMENT.md)、[C59](CASES.md#c59-native-hdr-measurement)。保留全部38项原关闭条件，完整目标继续建设。\n\n',1))
    for p in ('docs/product/HDR_DISPLAY.md','docs/product/HDR_METADATA.md','docs/product/ICC_OUTPUT.md'):
        write(p,read(p)+'\nCLI0.1.49 adds [actual all-frame light metering and colour receipt totals](HDR_MEASUREMENT.md). MaxRGB/CIE Y and declared SEI remain separate;the measurement is before YUV/codec,not physical monitor acceptance.\n')
    release='# CLI0.1.49 / alpha.4-local.47 — All-frame HDR light measurement\n\n[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)\n\n'+'\n\n'.join(descriptions.values())+'\n\n'
    release+=f"```text\ninstalled: local/agent-ffmpeg/v0.1.0-alpha.4-local.47/final-r1/installed\napplication ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.47/candidate-r1/bundle.zip\narchive bytes: {installed['archive_bytes']}\narchive SHA256: {installed['archive_sha256']}\nmanifest: {installed['manifest_sha256']}\n```\n\n"
    release+='275 Python files match tested source bytes;88 capabilities. One public `$agent-ffmpeg-local-editor`,17 internal modules,88 Skill files,r50 kit144 entries. Public alpha.3/CLI0.1.2 downloads unchanged. Native Windows,no virtualization/global installation/source fallback.\n\n'
    release+='Follow [offline activation](../product/COMMUNITY_LOCAL_DELIVERY.md) and [measurement workflow](../product/HDR_MEASUREMENT.md):init/ingest/compose → declare working/output nits → validate/dry-run → measure full timeline → inspect metric/scope/range counts → make explicit mastering decisions → render/inspect manifest → package/import/replay. CPU colour/meter,selected native GPU editing.\n\n'+detail['.en']+'\n\n[C59](../product/CASES.md#c59-native-hdr-measurement) · [Evidence](../validation/全帧HDR光量与裁切汇总实测_2026-10-29.md).\n';write('docs/releases/CLI_0.1.49_LOCAL.md',release)
    media='../assets/native-hdr-measure-20261029-'+a.case+'/'
    s=read('docs/product/CASES.md')+'\n<a id="c59-native-hdr-measurement"></a>\n\n## C59 · 全帧HDR光量 / 全影格HDR光量 / All-frame HDR light metering\n\n'
    s+='Actual registered CLI0.1.49/one unified Skill. Original CC0 RGB16 BT2020 linear chart (unit white1000nit),203nit linear working/PQ output,and stereo347/523Hz tones;640×360,48frames,12fps,4seconds. Early bright patch and later bright frame average deliberately differ. Full,active-area and partial reports preserve author bytes.\n\n'
    s+=f"Independent equations cover all{case['independent_pixels']} pixels and the complete RGB16 input digest;maximum nit error {case['independent_maximum_error_nits']:.12g}. Real PQ master/all66355200 decoded video bytes and384000 nonzero PCM scalars replay exactly after editable-package import;all reported measurements also replay exactly. A separate actual48-frame GPU Bloom/native ICC proof run has identical meter/render input and closed native handles/GPU worker. No speed benchmark is inferred.\n\n"
    oracle=load(BASE/('case-'+a.case)/'independent-oracle.json')
    s+='| Metric / 指标 / 指標 | Peak nit / 峰值 | Peak frame / 峰值影格 | Maximum frame average nit | Average peak frame |\n|---|---|---|---|---|\n'
    for key in ('maxrgb','cie_y'):
        s+='| `'+key+'` | '+str(oracle['peak_nits'][key])+' | '+str(oracle['peak_frames'][key])+' | '+str(oracle['frame_average_maximum_nits'][key])+' | '+str(oracle['average_peak_frames'][key])+' |\n'
    s+='\nCIE Y peaks in frame0;MaxRGB peaks in frame18. The late warm highlight and broad bright area distinguish the metrics. PQ/RGB16 quantization can move decoded maxima slightly above the original1000nit source component;the meter does not silently cap them.\n\n'
    s+='![Actual explicit SDR view of HDR chart]('+media+'actual-preview.gif)\n\n'+' · '.join('['+label+']('+media+name+')' for label,name in [('Original source','source-linear.mkv'),('Original tones','source-stereo.wav'),('PQ master','hdr-master.mkv'),('Master manifest','hdr-master.manifest.json'),('Actual MP4 SDR view','actual-preview.mp4'),('Actual frame','actual-frame.png'),('Full measurement','measurement.json'),('Active-area measurement','active-area-measurement.json'),('Partial measurement','partial-measurement.json'),('GPU/proof measurement','GPU-proof-measurement.json'),('Editable package','editable-hdr-measure.aevpkg.zip'),('Provenance','SOURCE.txt'),('Hashes','media-manifest.json')])+'\n\n'
    s+='Preview is an explicit Reinhard SDR viewing copy,not physical HDR monitoring. Measurements are before YUV/codec,not post-codec/filtered MaxCLL certification. No automatic SEI/mastering rewrite,human listening,continuous playback or artistic-quality acceptance.\n';write('docs/product/CASES.md',s)
    report='# 全帧HDR光量与裁切汇总实测 / All-frame HDR light verification — 2026-10-29\n\n'+detail['']+'\n\n'
    report+='Source-r1 retained3 failures/3 errors:the integration fixture incorrectly selected unsupported BT2020 linear SDR delivery;it now declares actual PQ output. One hand-transcribed CIE Y reference average was corrected from16.1001645 to16.1000964 using the independently solved BT2020/D65 primary matrix. Source-r2 passed17 tests;source-r3/r4 add actual native-proof/display-map equality and invalid-context coverage. Source-r4 also captures the original ICC helper fixture. Product numeric tolerances were not loosened.\n\n'
    for run in ('source-r1','source-r2','source-r3','source-r4','installation-final-r1','installed-r1','installed-compat-r1','case-'+a.case,'kit-r1'):
        report+='- ['+run+'](evidence/native-hdr-measure-20261028-r1/'+run+'/verification.json)\n'
    report+='\nC59 case-r1 failed because its independent oracle assumed native12fps source frames map one-to-one to author12fps;Matroska stores millisecond PTS. Case-r2 independently probes actual native timestamps and uses rational hold selection. The complete reference/real RGB16 hash then agrees without changing the product or its tolerance. [Preserved case-r1](evidence/native-hdr-measure-20261028-r1/case-r1/verification.json).\n'
    report+='\n[Independent all-frame oracle](evidence/native-hdr-measure-20261028-r1/case-'+a.case+'/independent-oracle.json) · [Actual checks](evidence/native-hdr-measure-20261028-r1/case-'+a.case+'/checks.json) · [Activation](evidence/native-hdr-measure-20261028-r1/activation-final-r1/activation-and-registration.json) · [C59](../product/CASES.md#c59-native-hdr-measurement).\n\nNo Docker/WSL/virtualization,global package installation,model download or GUI browser tab was used. Complete original R327 history and38 original G closure cells retained.\n'
    write('docs/validation/全帧HDR光量与裁切汇总实测_2026-10-29.md',report)
    (out/'verification.json').write_text(json.dumps(dict(status='passed',F=75,S=30,K=17,R=332,prior_R_retained=327,G_closure_cells_retained=38,tests=counts,whole_goal_complete=False),indent=2)+'\n',encoding='utf8',newline='\n')
    print('Three-language docs updated;R327 and38 G closures preserved.')


if __name__=='__main__':main()
