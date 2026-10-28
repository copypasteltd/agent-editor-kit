"""Document the actual registered CLI51 delivery before immutable kit packaging."""
from pathlib import Path
import argparse,json,re
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args()
    assert a.run.replace('-','').isalnum()
    out=BASE/('delivery-docs-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r2/verification.json')
    case=load(BASE/'registered-case-r2/verification.json')
    assert case['status']=='passed' and case['registered_skill_used']
    assert load(BASE/'activation-final-r1/activation-and-registration.json')['status']=='passed'
    for name,n in [('installed-measure-r1',64),('installed-preview-r1',18),('installed-compat-r2',352)]:
        t=load(BASE/name/'verification.json');assert t['status']=='passed' and t['tests']==n and t['skipped']==0
    assert load(ROOT/'agent-ffmpeg-local-install-manifest.json')['cli_version']=='0.1.51'
    capture=ROOT/'docs/product/oklab-gamut-installed-capabilities-cli-0.1.51.json'
    capture.write_bytes((BASE/'installation-final-r2/capabilities.stdout.json').read_bytes())
    caps=load(capture)['data']['capabilities'];assert len(caps)==88
    descriptions={
      '':'本地安装CLI51已接通明确OKLab缩色度、正式SDR交付映射继承及映射后线性预览缩小。显式preview_mapping仍优先。实际统一Skill执行C62，完整像素/PCM工程包重放通过；CPU色彩内核，不等于完整剪映/ACES/物理监看。',
      '.zh-TW':'本地安裝CLI51已接通明確OKLab縮色度、正式SDR交付映射繼承與映射後線性預覽縮小。顯式preview_mapping仍優先。實際統一Skill執行C62，完整像素／PCM專案重播通過；CPU色彩核心，不等於完整剪映／ACES／實體監看。',
      '.en':'Installed CLI51 provides explicit OKLab chroma reduction, inherited formal SDR mapping and display-linear preview resizing after mapping. Explicit preview_mapping takes priority. C62 runs through the actual unified Skill with full pixel/PCM package replay. CPU colour math; no complete CapCut/ACES/physical-monitor claim.'}
    media='docs/assets/oklab-registered-20261029-r2/'
    rows='''| R350 | Final CLI51 installed compatibility | 352/352 with zero failures/errors/skips; frozen277 files | 2026-10-29 | [compat](docs/validation/evidence/oklab-gamut-20261029-r1/installed-compat-r2/verification.json) | separate from64/18 focused gates; not full product parity |
| R351 | Unified Skill51 pin, native activation and registration | 1 public Skill/17 modules/90 files; actual junction and4 existing packs verified | 2026-10-29 | [activation](docs/validation/evidence/oklab-gamut-20261029-r1/activation-final-r1/activation-and-registration.json) | no new model forwards; public alpha.3 unchanged |
| R352 | C62 actual registered-Skill OKLab render/preview/package | Full10frame YUV replay,384000byte complete PCM,frame9 independent RGB16 oracle | 2026-10-29 | [case](docs/validation/evidence/oklab-gamut-20261029-r1/registered-case-r2/verification.json) | diagnostic synthetic SDR; CPU; no natural/physical acceptance |'''
    for suffix in ('','.zh-TW','.en'):
        p=ROOT/('README'+suffix+'.md');s=p.read_text('utf8')
        old=re.findall(r'^\| R\d+ .*$',s,re.M);assert len(old)==349
        s=s.replace(old[-1],old[-1]+'\n'+rows,1)
        block='<!-- oklab-installed-current -->\n\n**CLI0.1.51 / local.49 / r52 kit · 1 Skill / 17 modules / 90 files.**\n\n'+descriptions[suffix]+'\n\n'
        block+='[Workflow](docs/product/OKLAB_GAMUT.md) · [Install](docs/releases/CLI_0.1.51_LOCAL.md) · [C62](docs/product/CASES.md#c62-installed-oklab)\n\n'
        block+='![Actual registered Skill SDR view]('+media+'preview.gif)\n\n<!-- /oklab-installed-current -->\n\n'
        s=s.replace('<!-- oklab-gamut-source -->',block+'<!-- oklab-gamut-source-history -->',1)
        s=s.replace('<!-- /oklab-gamut-source -->','<!-- /oklab-gamut-source-history -->',1)
        # The source-stage block remains a dated history, not current guidance.
        s=s.replace('<!-- oklab-gamut-source-history -->','<!-- oklab-gamut-source-history -->\n\nHistorical source/candidate stage; superseded by the installed workflow above.\n',1)
        s=s.replace('<!-- native-hdr-media-current -->','<!-- native-hdr-media-history -->\n\nHistorical CLI50 delivery; current CLI51 is described above.',1).replace('<!-- /native-hdr-media-current -->','<!-- /native-hdr-media-history -->',1)
        assert re.findall(r'^\| R\d+ .*$',s,re.M)[:349]==old;write(p,s)
        for stem in ['docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL']:
            p=ROOT/(stem+suffix+'.md');s=p.read_text('utf8')
            link='OKLAB_GAMUT.md' if '/product/' in stem else '../product/OKLAB_GAMUT.md'
            block='<!-- community-current -->\n\n**CLI0.1.51 / local.49 / r52 kit · 1 Skill / 17 modules / 90 files.**\n\n'+descriptions[suffix]+'\n\n[OKLab / SDR workflow]('+link+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            if stem.endswith('CAPABILITIES'):
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S);assert n==1,key
                s+='\n[CLI51 exact installed capabilities](oklab-gamut-installed-capabilities-cli-0.1.51.json).\n'
            write(p,s)
    old=load(ROOT/'docs/validation/evidence/native-hdr-media-measure-20261029-r1/installation-final-r1/verification.json')
    p=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=p.read_text('utf8')
    for left,right in [('local.48/final-r1','local.49/final-r2'),('local.48/candidate-r1','local.49/candidate-r2'),('local.48','local.49'),('CLI 0.1.50','CLI 0.1.51'),('CLI0.1.50','CLI0.1.51'),('r51.zip','r52.zip'),('package-0.1.50-r51.json','package-0.1.51-r52.json'),(old['archive_sha256'],install['archive_sha256']),(old['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(left,right)
    s+='\nCurrent OKLab workflow: [configuration](OKLAB_GAMUT.md) · [C62](CASES.md#c62-installed-oklab) · [CLI51 installation](../releases/CLI_0.1.51_LOCAL.md).\n';write(p,s)
    p=ROOT/'docs/product/OKLAB_GAMUT.md';s=p.read_text('utf8')
    s=s.replace('\n\n','\n\n**当前已安装CLI0.1.51/local.49，统一Skill已加载；以下初始源码阶段状态保留为历史。** [实际安装与使用](../releases/CLI_0.1.51_LOCAL.md) · [C62](CASES.md#c62-installed-oklab)。\n\n',1);write(p,s)
    p=ROOT/'docs/releases/CLI_0.1.51_SOURCE.md';s=p.read_text('utf8');s=s.replace('\n\n','\n\nHistorical source stage; superseded by [actual CLI51 local delivery](CLI_0.1.51_LOCAL.md).\n\n',1);write(p,s)
    p=ROOT/'docs/README.md';s=p.read_text('utf8').replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：')
    s=s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.51 / local.49 / r52 kit** · [Workflow](product/OKLAB_GAMUT.md) · [Install](releases/CLI_0.1.51_LOCAL.md) · [C62](product/CASES.md#c62-installed-oklab).\n\n',1);write(p,s)
    p=ROOT/'docs/product/GOAL_GAPS_20261025.md';s=p.read_text('utf8');row=next(l for l in s.splitlines() if l.startswith('| G08 |'));cells=row.split('|');closure=cells[-3]
    cells[3]+=' CLI51/local49已实装OKLab缩色度与正式SDR预览继承，C62由真实统一Skill核验完整像素/PCM往返。 '
    assert cells[-3]==closure;s=s.replace(row,'|'.join(cells));write(p,s)
    p=ROOT/'docs/product/CASES.md';s=p.read_text('utf8')
    s+='''
<a id="c62-installed-oklab"></a>

## C62 · Actual registered unified Skill OKLab delivery / 實際統一Skill

CLI0.1.51/local.49，原创CC0图卡10帧/10FPS/1秒/384×216。使用真正C盘发现联接的统一Skill，经固定安装入口执行validate、正式渲染、frame9及全10帧range预览、工程包导出/导入/再次validate与渲染。旧C61重复ID已在新包修正，无绕过验证。

![Actual SDR viewing copy](../assets/oklab-registered-20261029-r2/preview.gif)

[Movie](../assets/oklab-registered-20261029-r2/oklab.mkv) · [Preview MP4](../assets/oklab-registered-20261029-r2/preview.mp4) · [PNG](../assets/oklab-registered-20261029-r2/frame.png) · [Editable package](../assets/oklab-registered-20261029-r2/editable-oklab.aevpkg.zip) · [Provenance](../assets/oklab-registered-20261029-r2/SOURCE.json) · [Raw verification](../validation/evidence/oklab-gamut-20261029-r1/registered-case-r2/verification.json)

全部10帧三YUV平面与独立标量参考已核验的历史成片及本轮包重放一致；完整384000byte PCM一致。frame9 PNG16对独立RGB16参考≤2code。正式SDR映射仅应用一次，之后显示线性缩小；显式preview_mapping优先。GIF是实际压缩SDR查看副本，不是浮点母版或物理HDR监看。

繁體：真實已註冊Skill執行、完整音畫重播及獨立像素參考；自然素材、完整ACES與實體監看仍待驗收。

English: Real registered-Skill execution, full-frame YUV and complete PCM replay, plus independent RGB16 frame preview checks. CPU-tiled colour math; no natural-footage, full ACES or physical-monitor acceptance.
''';write(p,s)
    release=ROOT/'docs/releases/CLI_0.1.51_LOCAL.md'
    write(release,f'''# CLI0.1.51 / local.49：本地安装与使用 / Local delivery

一个公共 `$agent-ffmpeg-local-editor`、17内部模块、90个Skill文件，匹配r52小kit。公开alpha.3/CLI0.1.2附件保持历史字节；本版本为原生Windows本地安装与验收，不是新的公开release。

应用ZIP：`local/agent-ffmpeg/v0.1.0-alpha.4-local.49/candidate-r2/bundle.zip`，{install['archive_bytes']} bytes，SHA256 `{install['archive_sha256']}`。清单 `{install['manifest_sha256']}`。已安装目录 `local/agent-ffmpeg/v0.1.0-alpha.4-local.49/final-r2/installed`。

## 使用流程 / Workflow

1. 按[完整离线安装流程](../product/COMMUNITY_LOCAL_DELIVERY.md)安装匹配应用ZIP和按任务选择的模型包；不要将旧alpha.3运行包与新Skill混用。
2. 调用唯一已注册入口，先核对版本，再导入[正确工程包](../assets/oklab-registered-20261029-r2/editable-oklab.aevpkg.zip)到新的本地目录。
3. validate后，按[完整OKLab配置](../product/OKLAB_GAMUT.md)明确输入、线性工作与输出信号、nit、映射策略。正式SDR用display_mapping；HDR母版查看用preview_mapping，后者优先。
4. 输出实际PNG/MP4供客户选型，保留配置与裁切/端点计数。正式成片另做实际媒体测量、工程包往返与声音核对。

```powershell
$aekSkill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aekSkill version
& $aekSkill convert import --input 'EDITABLE_PACKAGE' --output 'NEW_PROJECT'
& $aekSkill validate --project 'NEW_PROJECT'
& $aekSkill preview frame --project 'NEW_PROJECT' --frame 9 --height 216
& $aekSkill preview range --project 'NEW_PROJECT' --start-frame 0 --end-frame 10 --height 216
& $aekSkill render --project 'NEW_PROJECT' --sequence-id 'seq_main' --output 'NEW_PROJECT/renders/master.mkv'
& $aekSkill convert export --project 'NEW_PROJECT' --target-format package --output 'NEW_PROJECT/exports/editable.aevpkg.zip'
```

以上帧范围和seq_main对应C62示例；其他工程先读取实际序列ID、帧率与总帧数，输出路径使用工程内的新文件。

本轮安装专项64/64、预览18/18、完整兼容352/352分别通过；15项色域专项是64子集，不累加。277份产品Python文件与离线安装逐字节一致。C62真实Skill的两次渲染、全部YUV与完整PCM包重放通过。四个已有模型包重新核验，没有新增模型推理。

C62首轮r1的整份project.json不变断言错误包含了正常render输出/操作日志，保留[失败分析](../validation/evidence/oklab-gamut-20261029-r1/registered-case-r1/failure-analysis.json)。最终r2分别验证作者图不变、渲染只追加允许的输出日志、预览/导出不改工程字节；未修改产品实现或重跑已冻结的352门禁。两轮各执行2次真实渲染，最终验收统计指r2。

本轮保留首候选预览失败与C61重复ID勘误；[修复与失败历史](../validation/SDR预览映射修复_2026-10-29.md)。CPU OKLab不是GPU算子、软拐点或ACES；自然肤色/连续镜头/4K长片/动态HDR/物理监看及[38组原目标](../product/GOAL_GAPS_20261025.md)继续建设。

繁體：已安裝單入口Skill，明確參數後先validate再預覽與算繪，保留工程包與全音畫證據。English: Use the matching local runtime and single registered Skill. Validate explicit colour/nit/mapping configuration, show actual previews, and verify full media/package replay. Public alpha.3 remains historical; full CapCut parity is not claimed.
''')
    write(out/'verification.json',json.dumps(dict(status='documented',R=352,prior_R_preserved=349,skill_files=90,whole_goal_complete=False),indent=2)+'\n')
    print('Documented actual registered CLI51 delivery; kit packaging/independent extraction next.')
if __name__=='__main__':main()
