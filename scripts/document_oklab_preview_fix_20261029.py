"""Publish preview-fix evidence without rewriting historical acceptance rows."""
from pathlib import Path
import hashlib,json,re,shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'

def main():
    results={}
    for name,count in [('preview-fix-r3',15),('source-r5',64),('preview-regression-r1',18),
                       ('installed-measure-r1',64),('installed-preview-r1',18)]:
        value=json.loads((BASE/name/'verification.json').read_bytes())
        assert value['status']=='passed' and value['tests']==count and value['frozen_equal'],name
        results[name]=value
    build=json.loads((BASE/'installation-final-r2/verification.json').read_bytes())
    probe=json.loads((BASE/'preview-probe-r3/verification.json').read_bytes())
    assert build['status']=='installed-and-byte-verified' and probe['status']=='passed'
    assets=ROOT/'docs/assets/oklab-preview-candidate-20261029-r1'
    assets.mkdir(exist_ok=False)
    archive=Path(probe['corrected_package'])
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==probe['corrected_package_sha256']
    shutil.copyfile(archive,assets/'corrected-oklab.aevpkg.zip')
    frame=json.loads((BASE/'preview-probe-r3/frame.stdout.json').read_bytes())['data']
    window=json.loads((BASE/'preview-probe-r3/range.stdout.json').read_bytes())['data']
    shutil.copyfile(frame['path'],assets/'frame.png')
    assert window['verified_clock']['decoded_video_frames']==10
    assert (window['request']['width'],window['request']['height'])==(384,216)
    shutil.copyfile(window['path'],assets/'preview.mp4')
    manifest={'scope':'Actual candidate installed CLI; not the registered Skill or a release.',
              'source':'Original CC0 synthetic C61 chart; imported audio clip ID corrected and validated.',
              'frames':10,'fps':10,'duration_seconds':1,'width':384,'height':216,
              'human_listening':False,'continuous_playback_review':False,'files':[]}
    for p in sorted(assets.iterdir()):
        manifest['files'].append(dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    (assets/'SOURCE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    report=ROOT/'docs/validation/SDR预览映射修复_2026-10-29.md'
    report.write_text(f'''# SDR 预览正式映射继承：实现、候选安装与勘误

本轮修复 G08 的实际预览遗漏。作者工程只配置 `display_mapping` 而无 `preview_mapping` 时，旧预览忽略正式 SDR 映射，宽色域输入在 frame/range 输出处越界。现在显式预览映射仍优先；否则复用正式 `delivery_surface`，仅应用一次映射、打样与输出转换，回到 BT.709 显示线性域后缩小，再转换到 PNG/Float32 参考信号。保留作者 JSON，不自动修改作者配置。

## 本轮实现事项

| 编号 | 内容 | 实际证据与边界 |
| --- | --- | --- |
| D01 | 明确复现候选 r1 的有效工程预览失败 | [有效工程探测](evidence/oklab-gamut-20261029-r1/preview-probe-r2/verification.json)；frame/range 均失败；非 PROJECT_INVALID |
| D02 | 正式 SDR 映射继承、显式预览优先、映射后线性缩小 | [专项15/15](evidence/oklab-gamut-20261029-r1/preview-fix-r3/verification.json)；包含独立 Decimal PQ/亮度肩部/sRGB、完整 RGB16 PNG 与 Float32 双像素平均；15 是下面64的子集 |
| D03 | 源码 HDR/光量与预览回归 | [64/64](evidence/oklab-gamut-20261029-r1/source-r5/verification.json)、[18/18](evidence/oklab-gamut-20261029-r1/preview-regression-r1/verification.json)；分别计数，不冒充完整兼容352项 |
| D04 | 原生 Windows 离线候选包 r2 重建与安装 | [安装](evidence/oklab-gamut-20261029-r1/installation-final-r2/verification.json)；277 Python 文件逐字节相同；88能力；ZIP {build['archive_bytes']} bytes；SHA256 `{build['archive_sha256']}` |
| D05 | 候选安装版真实核验 | [64/64](evidence/oklab-gamut-20261029-r1/installed-measure-r1/verification.json)、[18/18](evidence/oklab-gamut-20261029-r1/installed-preview-r1/verification.json)；[实际CLI](evidence/oklab-gamut-20261029-r1/preview-probe-r3/verification.json)以 `-I -S` 调用安装入口，真实frame/10帧range、正确工程包导出/导入/validate/再次预览；无源码回退 |

候选安装路径：`local/agent-ffmpeg/v0.1.0-alpha.4-local.49/final-r2/installed`。本地可用ZIP：`local/agent-ffmpeg/v0.1.0-alpha.4-local.49/candidate-r2/bundle.zip`。统一注册 Skill **仍 CLI0.1.50/local.48/r51**；不能把候选检查写为Skill升级、公开release或完整剪映验收。

实际候选输出：[PNG](../assets/oklab-preview-candidate-20261029-r1/frame.png)、[MP4](../assets/oklab-preview-candidate-20261029-r1/preview.mp4)、[已修正ID的可编辑工程包](../assets/oklab-preview-candidate-20261029-r1/corrected-oklab.aevpkg.zip)、[来源与文件摘要](../assets/oklab-preview-candidate-20261029-r1/SOURCE.json)。图卡为原创CC0；MP4为查看副本，不替代浮点参考、人工听审或物理HDR监看。

## 失败记录与历史 C61 勘误

1. C61 历史包的素材与音频片段同时使用 `sound`，正常 CLI 验证报 ID_DUPLICATE。历史低层渲染的独立像素与完整PCM证据仍成立，但不证明该包可直接经正常CLI编辑。旧附件与 R343 保留；上述新包仅将导入副本的片段ID改为 `audio_clip`，先 validate 再预览和往返。
2. 初次探测 r1 的初步结论误把无效工程拒绝当作预览缺陷；[更正结果](evidence/oklab-gamut-20261029-r1/preview-probe-r1/verification.json)及 initial-inference.json 均保留。真正复现来自有效工程 r2。
3. source-r4 最初新增测试请求低于CLI允许的64px；preview-fix-r1/r2 随后用FFmpeg scale放大灰阶，RGB通道出现最多3个16位码值差异，中性灰独立公式不再适用，误差达15/13code。修正为直接逐平面重复原始RGB16字节，保持中性灰；原2code/浮点门槛未放宽。r3专项和source-r5及安装组使用修正后的原始输入。所有失败日志与执行快照保留，不改写通过。

## 待处理、待完成事项

| 编号 | 下一步 | 原目标 |
| --- | --- | --- |
| P01 | 对最终候选运行完整兼容门禁，再更新唯一Skill版本针、引用与注册清单，独立解包验证新kit | G08 / 交付 |
| P02 | 自然肤色、多光源、连续镜头与4K长片性能；CPU OKLab GPU化需独立数值与取消/清理验收 | G08 |
| P03 | 完整ACES/感知软拐点/动态HDR与物理监看，以及其余原始差距项 | [全部38项原关闭条件](../product/GOAL_GAPS_20261025.md) |

繁體：修復正式SDR映射繼承與線性縮小，候選安裝核驗通過；統一Skill仍50，新kit尚未交付。舊C61包ID衝突與首輪錯誤判讀已勘誤。

English: Frame/range previews now inherit the formal SDR delivery mapping unless an explicit preview mapping overrides it. Mapping/proof runs once before display-linear resizing. Source and candidate-installed gates are reported separately. The registered Skill remains CLI50; final compatibility and matching kit delivery are pending. Historical C61 duplicate IDs and the initial invalid-fixture inference are corrected transparently.
''',encoding='utf8',newline='\n')
    rows='''| R345 | Valid-fixture SDR preview defect + historical C61 correction | Installed r1 fails frame/range after validate; C61 duplicate audio clip ID documented | 2026-10-29 | [errata](docs/validation/SDR预览映射修复_2026-10-29.md) | original raw evidence retained; invalid-fixture r1 is not defect proof |
| R346 | SDR delivery inheritance before display-linear preview resize | Source gamut15/15, HDR/measure64/64, preview18/18; independent PQ/PNG/Float32 oracle | 2026-10-29 | [source](docs/validation/evidence/oklab-gamut-20261029-r1/source-r5/verification.json) | 15 is a subset of64; not full compatibility352 |
| R347 | Native CLI51 candidate r2 offline build/install | 277 Python files byte-exact;88 capabilities; native ICC unchanged | 2026-10-29 | [build](docs/validation/evidence/oklab-gamut-20261029-r1/installation-final-r2/verification.json) | candidate only; registered Skill remains50 |
| R348 | Actual candidate-installed HDR/measure and preview regression | 64/64 and18/18, separate groups, zero skips | 2026-10-29 | [measure](docs/validation/evidence/oklab-gamut-20261029-r1/installed-measure-r1/verification.json), [preview](docs/validation/evidence/oklab-gamut-20261029-r1/installed-preview-r1/verification.json) | final full compatibility and unified kit pending |
| R349 | Actual installed valid C61 frame/range and corrected editable package | frame9 +10frame range; export/import/validate/preview; author JSON unchanged | 2026-10-29 | [CLI](docs/validation/evidence/oklab-gamut-20261029-r1/preview-probe-r3/verification.json), [outputs](docs/validation/SDR预览映射修复_2026-10-29.md) | isolated candidate -I -S; no registered-Skill or human-monitor claim |'''
    intros={
      'README.md':'本轮已修复正式SDR映射的预览继承，CLI51候选r2完成源码/安装版专项及实际工程包往返；统一Skill仍50，完整兼容与新kit待完成。',
      'README.zh-TW.md':'本輪已修復正式SDR映射的預覽繼承，CLI51候選r2完成原始碼/安裝版專項與實際工程包往返；統一Skill仍50，完整相容與新kit待完成。',
      'README.en.md':'Formal SDR preview inheritance is fixed and CLI51 candidate r2 passes source/installed targeted gates plus actual package replay. Registered Skill remains50; full compatibility and matching kit delivery are pending.'}
    for name,intro in intros.items():
        p=ROOT/name;s=p.read_text('utf8');old=re.findall(r'^\| R\d+ .*$',s,re.M)
        assert len(old)==344 and not any('| R345 ' in r for r in old)
        s=s.replace(old[-1],old[-1]+'\n'+rows,1)
        marker='<!-- oklab-gamut-source -->'
        s=s.replace(marker,marker+'\n\n'+intro+' [Fix / evidence / C61 errata](docs/validation/SDR预览映射修复_2026-10-29.md).',1)
        assert re.findall(r'^\| R\d+ .*$',s,re.M)[:344]==old
        p.write_text(s,encoding='utf8',newline='\n')
    note='\n\n**2026-10-29 follow-up / 后续勘误 / 後續勘誤：** [SDR预览映射修复与C61包ID勘误](../validation/SDR预览映射修复_2026-10-29.md)。CLI51候选r2已构建与安装专项核验；统一Skill仍50；完整兼容、新kit、自然画面及物理监看待完成。\n'
    for name in ['docs/product/OKLAB_GAMUT.md','docs/product/CASES.md','docs/releases/CLI_0.1.51_SOURCE.md']:
        p=ROOT/name;p.write_text(p.read_text('utf8')+note,encoding='utf8',newline='\n')
    for name,target in [('docs/validation/OKLab色域映射源码实测_2026-10-29.md','SDR预览映射修复_2026-10-29.md'),('docs/README.md','validation/SDR预览映射修复_2026-10-29.md')]:
        p=ROOT/name;p.write_text(p.read_text('utf8')+f'\n\n2026-10-29 follow-up: [SDR预览映射修复、候选安装核验与历史C61勘误]({target})；统一注册Skill仍CLI50。\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='documented',readme_rows=349,registered_skill_version='0.1.50',candidate_version='0.1.51')))

if __name__=='__main__':main()
