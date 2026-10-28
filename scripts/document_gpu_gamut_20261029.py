"""Document source CLI52 GPU evidence without upgrading the installed CLI51 Skill."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/gpu-gamut-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args()
    assert a.run.replace('-','').isalnum()
    out=BASE/('source-docs-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')};assert len(pins)==278
    for folder,n in [('source-r2',70),('gpu-control-r1',12)]:
        v=load(BASE/folder/'verification.json');assert v['status']=='passed' and v['tests']==n and v['skipped']==0 and v['frozen_equal']
        assert v['product_files']==pins
    case=load(BASE/'case-r2/verification.json');probe=load(BASE/'4k-r1/verification.json')
    assert case['status']=='passed' and case['source_files']==pins and not case['registered_skill_used']
    assert probe['status']=='passed' and probe['all_pixels_compared']
    ns=ROOT/'agent-ffmpeg-local-install-manifest.json'
    assert load(ns)['cli_version']=='0.1.51' and sha(ns)==case['namespace_manifest_sha256']
    code="import sys;sys.path.insert(0,"+repr(str(ROOT/'product/src'))+");from ai_ad_editor.cli import main;main()"
    p=subprocess.run([sys.executable,'-E','-B','-X','utf8','-c',code,'capabilities'],cwd=ROOT,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    assert p.returncode==0,p.stderr
    cap=json.loads(p.stdout);assert cap['ok'] and cap['provenance']['cli_version']=='0.1.52' and len(cap['data']['capabilities'])==89
    capture=ROOT/'docs/product/gpu-gamut-source-capabilities-cli-0.1.52.json';capture.write_bytes(p.stdout)
    descriptions={
      '':'源码CLI52新增实际GPU亮度肩部及OKLab缩色度，信号转换与ICC仍由CPU处理。70项专项、12项控制管道测试、4K单表面独立参考及C63完整音画/工程包重放通过；本地注册Skill仍CLI51/local49/r52。352项兼容回归及新版安装交付另行验收。',
      '.zh-TW':'源碼CLI52新增實際GPU亮度肩部與OKLab縮色度，訊號轉換與ICC仍由CPU處理。70項專項、12項控制管道測試、4K單表面獨立參考及C63完整音畫／專案重播通過；本地註冊Skill仍CLI51/local49/r52。352項相容回歸與新版安裝交付另行驗收。',
      '.en':'Source CLI52 adds a real GPU luminance shoulder and OKLab chroma reduction; signal conversion and ICC remain on CPU. Separate 70-test and 12-test groups, an independent 4K single-surface check and full C63 video/audio/package replay passed. Registered Skill remains CLI51/local49/r52. The 352-test compatibility run and new installed delivery require separate acceptance.'}
    evidence='docs/validation/evidence/gpu-gamut-20261029-r1/'
    rows=f'''| R354 | CLI52 source GPU + HDR/measurement | 70/70; frozen 278 source files | [raw]({evidence}source-r2/verification.json) | source, not installed-Skill acceptance |
| R355 | CLI52 native GPU control lifecycle | 12/12; no skipped tests | [raw]({evidence}gpu-control-r1/verification.json) | owned worker/pipes/shared handles; not GPU instruction preemption |
| R356 | Actual 3840×2160 GPU colour operator | all 8,294,400 pixels vs independent reference | [raw]({evidence}4k-r1/verification.json) | one surface; not encoded 4K, real-time or long-form |
| R357 | C63 source GPU full encoded media/package replay | 10 frames; 4,976,640 YUV bytes; 384,000 PCM bytes equal; PNG16 error 0 | [raw]({evidence}case-r2/verification.json) | source CLI52, synthetic SDR chart; installed Skill remains CLI51 |'''
    history={}
    for suffix in ('','.zh-TW','.en'):
        path=ROOT/('README'+suffix+'.md');s=path.read_text('utf8')
        old=re.findall(r'^\| R\d+ .*$',s,re.M);assert len(old)==353
        s=s.replace(old[-1],old[-1]+'\n'+rows,1)
        block='<!-- gpu-gamut-source-current -->\n\n**Development source CLI0.1.52 · installed Skill CLI0.1.51 / local.49 / r52 unchanged.**\n\n'+descriptions[suffix]+'\n\n[Workflow](docs/product/GPU_GAMUT.md) · [Source release](docs/releases/CLI_0.1.52_SOURCE.md) · [C63](docs/product/CASES.md#c63-source-gpu-gamut) · [Evidence](docs/validation/GPU色域映射源码实测_2026-10-29.md)\n\n![Actual GPU SDR preview](docs/assets/gpu-gamut-20261029-r2/preview.gif)\n\n<!-- /gpu-gamut-source-current -->\n\n'
        assert '<!-- gpu-gamut-source-current -->' not in s
        s=s.replace('<!-- oklab-installed-current -->',block+'<!-- oklab-installed-current -->',1)
        assert re.findall(r'^\| R\d+ .*$',s,re.M)[:353]==old;write(path,s)
        history[path.name]=dict(preserved_R_rows=len(old),new_R_rows=4,old_rows_sha256=hashlib.sha256('\n'.join(old).encode()).hexdigest())
    gap=ROOT/'docs/product/GOAL_GAPS_20261025.md';s=gap.read_text('utf8')
    before={line.split('|')[1].strip():line.split('|')[-3] for line in s.splitlines() if re.match(r'^\| G\d\d \|',line)};assert len(before)==38
    for key in ('G08','G32'):
        row=next(l for l in s.splitlines() if l.startswith('| '+key+' |'));cells=row.split('|')
        cells[3]+=' 源码CLI52接通GPU亮度肩部/OKLab缩色度；70专项、12控制管道、4K单表面与C63完整音画/包重放已验。本地Skill仍51，源码兼容与安装交付另验；非实时/完整色彩验收。 '
        s=s.replace(row,'|'.join(cells),1)
    after={line.split('|')[1].strip():line.split('|')[-3] for line in s.splitlines() if re.match(r'^\| G\d\d \|',line)};assert before==after;write(gap,s)
    path=ROOT/'docs/product/CASES.md';s=path.read_text('utf8');assert 'id="c63-source-gpu-gamut"' not in s
    s+='''
<a id="c63-source-gpu-gamut"></a>

## C63 · Source CLI52 GPU SDR mapping / 源碼 GPU 映射

源码CLI0.1.52，CC0合成图卡与原创音调10帧/10FPS/1秒/384×216。独立源码入口执行验证、GPU正式渲染、frame9与全10帧range预览、工程包导入/导出及再次GPU渲染。**未调用已注册Skill；后者仍CLI51。**

![Actual GPU SDR viewing copy](../assets/gpu-gamut-20261029-r2/preview.gif)

[Movie](../assets/gpu-gamut-20261029-r2/oklab.mkv) · [MP4](../assets/gpu-gamut-20261029-r2/preview.mp4) · [PNG](../assets/gpu-gamut-20261029-r2/frame.png) · [Editable package](../assets/gpu-gamut-20261029-r2/editable-oklab.aevpkg.zip) · [Media provenance](../assets/gpu-gamut-20261029-r2/SOURCE.json) · [Verification](../validation/evidence/gpu-gamut-20261029-r1/case-r2/verification.json)

实际正式渲染派发10次GPU gamut_map，完整4,976,640 byte YUV及384,000 byte PCM与旧独立标量参考已验的CPU成片、再次GPU工程包重放一致；RGB16编码器输入摘要等于独立参考，frame9 PNG16最大误差0code。预览/导出不改作者工程；正常render仅追加输出与变更日志、更新时间，作者图其余字段保持。

r1、r2最终均通过，选用r2演示且只计一个案例能力；观察暂缺终态不代表中断。静态PNG已查看，GIF/MP4帧数与时长程序化核验；没有连续人工观片、听审、自然HDR或物理监看验收。

繁體：完整CPU/GPU音畫與專案重播核對；源碼、已安裝Skill與公開發行分開。English: Full decoded CPU/GPU video/audio and editable-package replay were checked; this source execution is not registered-Skill or physical-HDR acceptance.
''';write(path,s)
    report='''# GPU色域映射源码实测 · 2026-10-29

源码CLI0.1.52，278个Python模块、89项能力。本地注册仍CLI0.1.51/local49/r52，未改命名空间或Skill固定入口。原生Windows，没有Docker/WSL、浏览器或新增模型推理。

| 编号 | 实现/核验 | 证据与范围 |
| --- | --- | --- |
| D01 | GPU曝光、亮度肩部、OKLab 24次二分缩色度 | [实现与使用](../product/GPU_GAMUT.md)；信号转换/ICC仍CPU |
| D02 | 70项源码色彩/光量专项通过，0失败/跳过 | [最终冻结源码](evidence/gpu-gamut-20261029-r1/source-r2/verification.json) |
| D03 | 12项GPU控制管道回归通过 | [独立测试组](evidence/gpu-gamut-20261029-r1/gpu-control-r1/verification.json) |
| D04 | 4K单表面8,294,400像素全部对独立参考 | [逐像素证据](evidence/gpu-gamut-20261029-r1/4k-r1/verification.json)，非成片/实时性能 |
| D05 | C63真实10帧GPU成片、预览与工程包重放 | [完整核验](evidence/gpu-gamut-20261029-r1/case-r2/verification.json)，不是注册Skill执行 |

随机测试四种曝光、66049像素、负RGB分量及alpha特殊位；计数/输出对CPU核对。负CIE Y工作进程拒绝、不回退；错误策略派发前拒绝；取消关闭工作进程/管道/共享句柄。4K独立参考采用独立xy矩阵与48步标量搜索，产品采用24步；最大线性RGB误差1.54e-7，CPU/GPU最大差1.78e-15。18.10s CPU / 1.74s GPU另加0.94s启动只是一轮非独占算子测量。

源码source-r1初次6项专项属于早期能力元数据；最终source-r2的70项与当前278模块摘要逐个核对。C63 r1与r2最终均通过，只计一个案例能力；以实际终态收据为准。

| 编号 | 待完成 | 原目标 |
| --- | --- | --- |
| P01 | 352项源码兼容回归，读取终态后再记录通过/失败 | G08/G32 |
| P02 | 新候选离线安装、安装专项/兼容与实际注册Skill案例、统一Skill及kit同步 | G08/G32/交付 |
| P03 | 跨厂商设备、实时/4K成片/长片性能与自然素材质量 | G32 |
| P04 | 完整ACES/色彩/HDR/物理监看及其余原始产品关闭条件 | [全部38项](../product/GOAL_GAPS_20261025.md) |

源码与安装版不同，旧公开alpha.3附件保持字节。全部353条历史README核验行及38项原关闭条件保持，不宣称完整剪映等价。
''';write(ROOT/'docs/validation/GPU色域映射源码实测_2026-10-29.md',report)
    write(ROOT/'docs/releases/CLI_0.1.52_SOURCE.md','''# CLI0.1.52 源码开发版 / Source development

新增原生GPU亮度肩部/OKLab缩色度，复用受管OpenCL工作进程与共享缓冲；正式SDR交付、明确HDR预览和正式映射继承使用同一路径。已有CPU reject/clip/oklab语义保持。

[完整使用流程与执行边界](../product/GPU_GAMUT.md) · [C63实际案例](../product/CASES.md#c63-source-gpu-gamut) · [专项/独立参考/待办](../validation/GPU色域映射源码实测_2026-10-29.md) · [源码89项能力原始收据](../product/gpu-gamut-source-capabilities-cli-0.1.52.json)

当前注册入口仍CLI0.1.51/local49/r52。源码测试和单独候选构建不等于安装激活；新版离线包、安装回归、实际Skill案例及统一kit待完整核验。不要用旧Skill调用本版GPU新增能力，不回退源码冒充安装版。公开alpha.3/CLI0.1.2资产保持原字节。

繁體：源碼GPU路徑已實作並留存真實音畫核驗，安裝版與新版Skill交付另行驗收。English: Source GPU mapping is implemented and checked against real media and independent references; installed runtime and Skill delivery remain a separate gate.
''')
    for relative,link in [('docs/README.md','product/GPU_GAMUT.md'),('docs/product/CAPABILITIES.md','GPU_GAMUT.md'),('docs/product/CAPABILITIES.zh-TW.md','GPU_GAMUT.md'),('docs/product/CAPABILITIES.en.md','GPU_GAMUT.md')]:
        path=ROOT/relative;s=path.read_text('utf8');suffix='.en' if '.en.' in relative else '.zh-TW' if '.zh-TW.' in relative else ''
        s=s.replace('\n\n','\n\nSource CLI52 GPU update (installed Skill remains CLI51): '+descriptions[suffix]+' [Workflow]('+link+').\n\n',1);write(path,s)
    path=ROOT/'.gitattributes';s=path.read_text('utf8')+'\n# Native GPU SDR source evidence and media remain byte-exact.\ndocs/validation/evidence/gpu-gamut-20261029-r1/** -text -whitespace\ndocs/assets/gpu-gamut-20261029-*/** -text -whitespace\ndocs/product/gpu-gamut-source-capabilities-cli-0.1.52.json -text -whitespace\nscripts/*gpu_gamut*20261029.py text eol=lf\nproduct/src/ai_ad_editor/float_gamut_kernel.py text eol=lf\nproduct/tests/test_gpu_gamut.py text eol=lf\n';write(path,s)
    assert pins=={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    result=dict(status='passed',source_version='0.1.52',registered_version='0.1.51',source_files=278,capabilities=89,history=history,original_38_closure_cells_preserved=before==after,namespace_unchanged=sha(ns)==case['namespace_manifest_sha256'],new_model_forwards=0)
    write(out/'verification.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
