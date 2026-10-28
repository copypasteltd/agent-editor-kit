"""Document the real CLI52 registered-Skill delivery before r53 kit packaging."""
from pathlib import Path
import argparse,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/gpu-gamut-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/'registered-case-r1/verification.json')
    assert case['status']=='passed' and case['registered_skill_used'] and not case['source_execution']
    for name,n in [('source-r2',70),('compat-r1',352),('installed-measure-r1',70),('installed-compat-r1',352)]:
        v=load(BASE/name/'verification.json');assert v['status']=='passed' and v['tests']==n and v['skipped']==0
    assert load(BASE/'activation-final-r1/activation-and-registration.json')['status']=='passed'
    ns=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert ns['cli_version']=='0.1.52' and len(ns['files'])==91
    out=BASE/('delivery-docs-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    capture=ROOT/'docs/product/gpu-gamut-installed-capabilities-cli-0.1.52.json';capture.write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
    caps=load(capture)['data']['capabilities'];assert len(caps)==89
    descriptions={'':'本地统一Skill已升级CLI52：GPU执行亮度肩部与OKLab缩色度，信号转换与ICC仍由CPU处理。源码与安装版各70项专项、各352项兼容分别通过；C64由实际注册入口完成GPU成片/预览及完整音画工程包重放。',
      '.zh-TW':'本地統一Skill已升級CLI52：GPU執行亮度肩部與OKLab縮色度，訊號轉換與ICC仍由CPU處理。源碼與安裝版各70項專項、各352項相容分別通過；C64由實際註冊入口完成GPU成片／預覽與完整音畫專案重播。',
      '.en':'The registered unified Skill now uses CLI52: GPU luminance shoulder and OKLab chroma search, with signal conversion and ICC on CPU. Separate source and installed 70-test and 352-test groups passed. C64 exercised real registered-Skill GPU rendering, previews and complete video/audio editable-package replay.'}
    rows='''| R359 | CLI52 frozen source compatibility | 352/352; no failures/errors/skips | [raw](docs/validation/evidence/gpu-gamut-20261029-r1/compat-r1/verification.json) | separate source gate; contains 18 preview tests |
| R360 | CLI52 byte-matched installed compatibility | 352/352; 278 source modules equal | [raw](docs/validation/evidence/gpu-gamut-20261029-r1/installed-compat-r1/verification.json) | source and installed groups reported separately |
| R361 | C64 actual registered CLI52 GPU Skill | 2 renders; 10-frame YUV and complete PCM replay equal; frame9 PNG16 error 0 | [raw](docs/validation/evidence/gpu-gamut-20261029-r1/registered-case-r1/verification.json) | 1 Skill / 17 modules / 91 files; synthetic SDR; no full parity claim |'''
    for suffix in ('','.zh-TW','.en'):
        path=ROOT/('README'+suffix+'.md');s=path.read_text('utf8');old=re.findall(r'^\| R\d+ .*$',s,re.M);assert len(old)==358
        s=s.replace(old[-1],old[-1]+'\n'+rows,1)
        block='<!-- gpu-gamut-installed-current -->\n\n**CLI0.1.52 / local.50 · 1 Skill / 17 modules / 91 files.**\n\n'+descriptions[suffix]+'\n\n[Workflow](docs/product/GPU_GAMUT.md) · [Install / usage](docs/releases/CLI_0.1.52_LOCAL.md) · [C64](docs/product/CASES.md#c64-installed-gpu-gamut)\n\n![Actual registered Skill GPU SDR view](docs/assets/gpu-gamut-registered-20261029-r1/preview.gif)\n\n<!-- /gpu-gamut-installed-current -->\n\n'
        s=s.replace('<!-- gpu-gamut-source-current -->',block+'<!-- gpu-gamut-source-history -->\n\nHistorical source/candidate stage; superseded by installed CLI52 above.',1).replace('<!-- /gpu-gamut-source-current -->','<!-- /gpu-gamut-source-history -->',1)
        s=s.replace('<!-- oklab-installed-current -->','<!-- oklab-installed-history -->\n\nHistorical installed CLI51; superseded by CLI52 above.',1).replace('<!-- /oklab-installed-current -->','<!-- /oklab-installed-history -->',1)
        assert re.findall(r'^\| R\d+ .*$',s,re.M)[:358]==old;write(path,s)
        for stem in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            path=ROOT/(stem+suffix+'.md');s=path.read_text('utf8');link='GPU_GAMUT.md' if '/product/' in stem else '../product/GPU_GAMUT.md'
            block='<!-- community-current -->\n\n**CLI0.1.52 / local.50 · 1 Skill / 17 modules / 91 files.**\n\n'+descriptions[suffix]+'\n\n[GPU colour workflow]('+link+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            s=s.replace('Source CLI52 GPU update (installed Skill remains CLI51):','Historical source CLI52 stage, superseded by installed delivery:')
            if stem.endswith('CAPABILITIES'):
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if n==0:assert key=='native_sdr_gamut_mapping';s+='\n'+section+'\n'
                s+='\n[CLI52 exact installed capabilities](gpu-gamut-installed-capabilities-cli-0.1.52.json).\n'
            write(path,s)
    path=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=path.read_text('utf8');previous=load(ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1/installation-final-r2/verification.json')
    for old,new in [('local.49/final-r2','local.50/final-r1'),('local.49/candidate-r2','local.50/candidate-r1'),('local.49','local.50'),('CLI 0.1.51','CLI 0.1.52'),('CLI0.1.51','CLI0.1.52'),('r52.zip','r53.zip'),('package-0.1.51-r52.json','package-0.1.52-r53.json'),(previous['archive_sha256'],install['archive_sha256']),(previous['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(old,new)
    s+='\nCurrent GPU colour workflow: [parameters](GPU_GAMUT.md) · [C64](CASES.md#c64-installed-gpu-gamut) · [CLI52 installation](../releases/CLI_0.1.52_LOCAL.md).\n';write(path,s)
    path=ROOT/'docs/product/GPU_GAMUT.md';s=path.read_text('utf8')
    s=s.replace('开发源码 CLI **0.1.52** 新增原生 OpenCL 色彩算子。本地已注册统一 Skill 仍为 **CLI0.1.51 / local.49 / r52**；新源码、新候选包与已激活安装版分别核验，不能混用版本。公开 alpha.3 附件保持原字节。','本地已注册统一 Skill 为 **CLI0.1.52 / local.50**，实际安装与源码各自的70项专项、352项兼容分别通过；[C64](CASES.md#c64-installed-gpu-gamut)通过实际注册入口执行。[安装与使用](../releases/CLI_0.1.52_LOCAL.md)。公开 alpha.3 附件保持原字节。')
    s=s.replace('开发源码','源码与安装版').replace('本轮核验报告](../validation/GPU色域映射源码实测_2026-10-29.md)','本轮安装交付报告](../validation/GPU色域映射安装与统一Skill交付_2026-10-29.md)')
    s=s.replace('必須區分源碼 CLI52、候選安裝與目前已註冊 CLI51','已註冊 CLI52 與源碼各自核驗').replace('Source CLI52 adds','Installed CLI52 adds').replace('The installed unified Skill remains CLI51 until matching installation gates pass.','The actual registered CLI52 Skill and native installation passed separate matching gates.')
    write(path,s)
    path=ROOT/'docs/product/OKLAB_GAMUT.md';s=path.read_text('utf8');s=s.replace('\n\n','\n\n**当前已安装CLI0.1.52/local50，可选实际GPU肩部/缩色度；下方旧源码与CLI51状态为历史。** [当前CPU/GPU参数与使用](GPU_GAMUT.md) · [实际安装](../releases/CLI_0.1.52_LOCAL.md)。\n\n',1);write(path,s)
    path=ROOT/'docs/releases/CLI_0.1.52_SOURCE.md';s=path.read_text('utf8');s=s.replace('\n\n','\n\nHistorical source stage; superseded by [actual installed CLI52 delivery](CLI_0.1.52_LOCAL.md).\n\n',1);write(path,s)
    path=ROOT/'docs/README.md';s=path.read_text('utf8').replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：').replace('Source CLI52 GPU update (installed Skill remains CLI51):','Historical source CLI52 stage, superseded by installed delivery:')
    s=s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.52 / local.50** · [GPU colour](product/GPU_GAMUT.md) · [Install](releases/CLI_0.1.52_LOCAL.md) · [C64](product/CASES.md#c64-installed-gpu-gamut).\n\n',1);write(path,s)
    path=ROOT/'docs/product/GOAL_GAPS_20261025.md';s=path.read_text('utf8')
    before={l.split('|')[1].strip():l.split('|')[-3] for l in s.splitlines() if re.match(r'^\| G\d\d \|',l)};assert len(before)==38
    for key in ('G08','G32'):
        row=next(l for l in s.splitlines() if l.startswith('| '+key+' |'));cells=row.split('|');cells[3]+=' CLI52/local50已实装GPU亮度肩部/OKLab缩色度；源码与安装各70/352分列，C64实际统一Skill全像素/PCM重放通过。非实时/完整ACES或物理监看验收。 ';s=s.replace(row,'|'.join(cells),1)
    after={l.split('|')[1].strip():l.split('|')[-3] for l in s.splitlines() if re.match(r'^\| G\d\d \|',l)};assert before==after;write(path,s)
    path=ROOT/'docs/product/CASES.md';s=path.read_text('utf8');assert 'id="c64-installed-gpu-gamut"' not in s
    s+='''
<a id="c64-installed-gpu-gamut"></a>

## C64 · Actual registered Skill GPU colour delivery / 實際已註冊GPU色彩

CLI0.1.52/local50，91个Skill文件、1外层入口/17内部模块。通过真实C盘发现联接、固定离线安装启动器执行验证、两次正式GPU渲染、frame9与全10帧range预览及工程包往返；无源码回退。素材为既有CC0原创图卡与音调，10帧/10FPS/1秒/384×216。

![Actual registered Skill SDR view](../assets/gpu-gamut-registered-20261029-r1/preview.gif)

[Movie](../assets/gpu-gamut-registered-20261029-r1/oklab.mkv) · [MP4](../assets/gpu-gamut-registered-20261029-r1/preview.mp4) · [PNG](../assets/gpu-gamut-registered-20261029-r1/frame.png) · [Editable package](../assets/gpu-gamut-registered-20261029-r1/editable-oklab.aevpkg.zip) · [Provenance](../assets/gpu-gamut-registered-20261029-r1/SOURCE.json) · [Actual CLI receipts](../validation/evidence/gpu-gamut-20261029-r1/registered-case-r1/verification.json)

正式渲染10次gamut_map、frame预览1次、range预览10次。全部4,976,640 byte YUV、384,000 byte PCM与历史CPU独立参考已验成片及再次GPU工程包重放一致。全部RGB16编码器输入摘要等于独立参考，frame9 PNG16最大误差0code。预览/导出不改作者字节；render仅追加输出、操作日志和更新时间，作者图其余字段保持。

GPU执行曝光/亮度肩部/24步缩色度，CPU执行信号转换/ICC。GIF与MP4均为真实SDR查看副本，10帧/1000ms；不是物理HDR或自然素材艺术质量验收。四个既有模型包重新核验，没有新增模型推理。繁體：實際註冊入口與完整音畫/專案重播留證。English: Actual registered-Skill execution and complete encoded media replay; no full CapCut, natural-quality, ACES or monitor-certification claim.
''';write(path,s)
    sequence=load(BASE/'registered-case-r1/author-before.json')['sequences'][0]['id']
    write(ROOT/'docs/releases/CLI_0.1.52_LOCAL.md',f'''# CLI0.1.52 / local.50：本地安装与使用 / Local delivery

一个公共 `$agent-ffmpeg-local-editor`、17内部模块、91个Skill文件。对应独立原生Windows运行包；公开alpha.3/CLI0.1.2附件保持原字节。本轮不是新的公开release，也不宣称完整剪映等价。

本地应用ZIP：`local/agent-ffmpeg/v0.1.0-alpha.4-local.50/candidate-r1/bundle.zip`，{install['archive_bytes']} bytes，SHA256 `{install['archive_sha256']}`；清单 `{install['manifest_sha256']}`。已安装目录 `local/agent-ffmpeg/v0.1.0-alpha.4-local.50/final-r1/installed`，278个源码模块逐字节一致。

## 使用流程 / Workflow

1. 使用[匹配应用包与统一Skill安装流程](../product/COMMUNITY_LOCAL_DELIVERY.md)，按任务选择已有模型包。先核对真实version/capabilities；不要混用旧alpha.3运行包或回退源码。
2. 导入[C64完整可编辑工程包](../assets/gpu-gamut-registered-20261029-r1/editable-oklab.aevpkg.zip)到新目录，运行validate。该包含明确GPU require、设备0.0及正式BT.709 SDR映射；部署机器须验证自己的OpenCL FP64设备，不照搬本机编号。
3. 按[GPU色彩完整参数](../product/GPU_GAMUT.md)声明输入/工作/输出信号与nit。正式SDR用display_mapping，HDR母版查看用preview_mapping；显式预览映射优先，否则继承正式映射一次。
4. 实际预览后向客户展示PNG/MP4和配置，检查真实gamut_map计数及端点/裁切统计。随后正式渲染、核对完整音画并导出工程包。

```powershell
$aekSkill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aekSkill version
& $aekSkill capabilities
& $aekSkill convert import --input 'EDITABLE_PACKAGE' --output 'NEW_PROJECT'
& $aekSkill validate --project 'NEW_PROJECT'
& $aekSkill preview frame --project 'NEW_PROJECT' --frame 9 --height 216
& $aekSkill preview range --project 'NEW_PROJECT' --start-frame 0 --end-frame 10 --height 216
& $aekSkill render --project 'NEW_PROJECT' --sequence-id '{sequence}' --output 'NEW_PROJECT/renders/master.mkv'
& $aekSkill convert export --project 'NEW_PROJECT' --target-format package --output 'NEW_PROJECT/exports/editable.aevpkg.zip'
```

帧范围与序列ID取自C64；其他工程读取实际序列/时长。`projection_acceleration.operations.gamut_map`证明实际GPU派发，准备成功或dry-run不证明执行。CPU信号转换、ICC、输出编码与GPU肩部/缩色度分开描述。

源码专项70/70、源码兼容352/352；安装专项70/70、安装兼容352/352分别留证，18项预览测试已包含在各352组中，不另行叠加。C64真实注册入口两次渲染、所有YUV/完整PCM/独立RGB16与工程包重放通过。四个已有模型包完整复核，未新增推理。见[交付报告](../validation/GPU色域映射安装与统一Skill交付_2026-10-29.md)。

仍待跨厂商GPU、自然质量、编码4K/长片/实时、完整ACES/动态HDR/物理监看及[其余原目标](../product/GOAL_GAPS_20261025.md)。繁體：使用匹配套件、實際預覽、檢查GPU派發與完整音畫，再交付可編輯專案。English: Use the matching native runtime and one Skill; validate explicit settings, show actual previews, inspect real GPU receipts and verify complete media/package replay.
''')
    write(ROOT/'docs/validation/GPU色域映射安装与统一Skill交付_2026-10-29.md','''# GPU色域映射安装与统一Skill交付 · 2026-10-29

实际激活CLI0.1.52/local50，统一公共Skill一个、17模块、91文件；原生Windows，没有Docker/WSL/虚拟环境、浏览器或新增模型推理。

| 编号 | 本轮交付/核验 | 证据 |
| --- | --- | --- |
| D01 | 源码352项兼容终态全部通过 | [source](evidence/gpu-gamut-20261029-r1/compat-r1/verification.json) |
| D02 | 独立安装版352项兼容全部通过 | [installed](evidence/gpu-gamut-20261029-r1/installed-compat-r1/verification.json) |
| D03 | 278个源码模块与安装完全一致 | [构建安装](evidence/gpu-gamut-20261029-r1/installation-final-r1/verification.json)；源码/安装70专项为上一轮已完成证据 |
| D04 | 匹配单入口Skill、实际激活与C盘发现联接 | [pin](evidence/gpu-gamut-20261029-r1/skill-pin-r1/verification.json) · [activation](evidence/gpu-gamut-20261029-r1/activation-final-r1/activation-and-registration.json) |
| D05 | C64真实注册Skill执行两次GPU渲染及完整包重放 | [case](evidence/gpu-gamut-20261029-r1/registered-case-r1/verification.json) |
| D06 | 中/繁/英README、参数、安装、服务/能力及Skill说明同步 | [工作流](../product/GPU_GAMUT.md) · [使用逻辑](../releases/CLI_0.1.52_LOCAL.md) |

全4,976,640 byte YUV及384,000 byte PCM相同，RGB16编码器输入摘要与独立参考一致，PNG16误差0code。正式10次、单帧1次、区间10次真实gamut_map派发；GPU肩部/缩色度不等于GPU信号转换/ICC。GIF/MP4帧数/时长核对；静态PNG视觉查看另记录，不冒充连续观片/听审/物理HDR监看。

上一轮4K仅单表面8,294,400像素，不是本轮新4K成片、实时或长片验收。C63两次源码案例的终态均通过，只计同一案例能力；此前观察暂缺终态的误记已更正，执行快照历史保留。

| 编号 | 待完成 | 原目标 |
| --- | --- | --- |
| P01 | r53小kit打包、独立解压/配置/注册与实际GPU预览验收 | 交付/G08/G32 |
| P02 | 多厂商GPU、自然素材质量、4K成片/长片/实时资源测量 | G32 |
| P03 | 完整ACES、色彩/HDR/物理监看及其余全部关闭条件 | [38项原目标](../product/GOAL_GAPS_20261025.md) |

源码70、源码352、安装70、安装352分别报告，18项预览已在352组内。完整产品目标未完成，既有全部358条README核验行与38项关闭条件保留。
''')
    result=dict(status='documented-installed-delivery',cli='0.1.52',skill_files=91,original_R_rows_preserved=358,current_R_rows=361,original_38_closure_cells_preserved=before==after,kit_acceptance='pending-separate-gate',goal_complete=False)
    write(out/'verification.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
