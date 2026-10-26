"""Document C40 without dropping historical README rows or goal conditions."""
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/tracking-retime-20261026-r1'

def load(p): return json.loads(Path(p).read_bytes())
def write(p, text): (ROOT/p).write_text(text, encoding='utf8', newline='\n')
def rows(text): return {m[1]: m[0] for m in re.finditer(r'^\| (R\d{2,3})\s*\|.*$', text, re.M)}


def main():
    install = load(BASE/'installation-final-r1/verification.json')
    case = load(BASE/'case-r1/verification.json')
    assert install['status']=='installed-and-byte-verified' and case['status']=='passed'
    languages = [
        ('', 'README.md', '原生跟踪共享变速',
         '跟踪源、标签与关联音轨支持完整输出变速。依赖闭包保存在共享作者子序列，各父层只选择自己的输出；保留原始观察、原生PTS、ROI基准、裁切/运镜、透明度和外部叠放顺序。',
         '实际2倍速案例：全部18帧Float32与解码画面对应原片偶数帧；完整72000双声道采样与独立FFmpeg tempo输出逐样本相等。工程包重导入与队列另行核验。合成诊断素材，未作自然质量、连续播放或人工听审验收。',
         '| F14 | 变速、倒放与定格 | 显式速度/曲线/Bezier/定格点；原生跟踪依赖闭包共享完整作者时钟，各层输出选择保留叠放位置及关联声音。 | `timeline edit; render` | 默认ripple与显式sync_content:retime不同；锁/端点/预算门禁，音频后端与非恒速曲线保留原精度边界。 |',
         '| F60 | 原生跟踪后续编辑 | 共享作者变速、逐层输出、完整音轨单次选择；磁性分片重排、分割/裁切/波纹/范围、物理滑移与外扩；保留原始观察/基准。 | `timeline compose/edit; preview; render; package` | 显式Float32；父层关联组保留共享输出时钟；显式解除关联会分离完整输出；中间格式烘焙及自然遮挡质量继续推进。 |'),
        ('.zh-TW', 'README.zh-TW.md', '原生追蹤共享變速',
         '追蹤來源、標籤與關聯音軌支援完整輸出變速。依賴閉包保存在共享作者子序列，各父層只選擇自己的輸出；保留原始觀察、原生PTS、ROI基準、裁切/運鏡、透明度及外部疊放順序。',
         '實際2倍速案例：全部18影格Float32及解碼畫面對應原片偶數影格；完整72000雙聲道取樣與獨立FFmpeg tempo輸出逐樣本相等。工程包重匯入及佇列另外核驗。合成診斷素材，未作自然品質、連續播放或人工聽審驗收。',
         '| F14 | 變速、倒放與定格 | 明確速度/曲線/Bezier/定格點；原生追蹤依賴閉包共享完整作者時鐘，各層輸出選擇保留疊放位置及關聯聲音。 | `timeline edit; render` | 預設ripple與明確sync_content:retime不同；鎖/端點/預算門禁，音訊後端及非恆速曲線保留原精度邊界。 |',
         '| F60 | 原生追蹤後續編輯 | 共享作者變速、逐層輸出、完整音軌單次選擇；磁性分片重排、分割/裁切/波紋/範圍、物理滑移及外擴；保留原始觀察/基準。 | `timeline compose/edit; preview; render; package` | 明確Float32；父層關聯組保留共享輸出時鐘；明確解除關聯會分離完整輸出；中間格式烘焙及自然遮擋品質持續推進。 |'),
        ('.en', 'README.en.md', 'Native shared-author tracking retime',
         'Tracked sources, followers and linked sound now share a complete author graph during relative output retiming. Each parent layer selects its own output, preserving saved observations, native PTS, ROI references, crop/motion, scalar alpha and external blend order.',
         'Actual 2x case: all 18 Float32 and decoded frames match the original even frames; all 72000 stereo samples equal an independent FFmpeg tempo oracle. Package reimport and queue checked separately. Synthetic diagnostics; no natural-quality, continuous-playback or human-listening acceptance.',
         '| F14 | Speed, reverse and freeze | Explicit scalar/curve/Bezier/freeze maps; native tracking dependency closure shares complete author time, with per-layer outputs and linked sound. | `timeline edit; render` | Default ripple differs from explicit sync_content:retime; locks/endpoints/budgets apply. Audio backends and nonconstant curves retain their precision limits. |',
         '| F60 | Editing native tracking | Shared-author retime, selected layer outputs and single sound selection; magnetic partition/reorder, split/trim/ripple/range and physical slip/extension with retained observations/references. | `timeline compose/edit; preview; render; package` | Explicit Float32. Keep the parent link cohort for a shared output clock; explicit unlink separates complete outputs. Interchange baking and natural occlusion quality remain open. |')]
    descriptions = {
        '': ['离线安装CLI0.1.30/local.28-final-r1，222个产品Python文件/schema与源码一致；唯一Skill、17模块、73文件。',
             '安装版分组核验：跟踪79、磁性66、编辑195、绑定71、Float32合成98、渲染46、音频65、旧CLI192；各组独立，无跳过。',
             'C40统一Skill实际2倍速：共享作者依赖图、逐层输出；全部18帧Float32/PTS/几何与原偶数帧一致；完整72000双声道采样与独立tempo误差0；包及队列复现。',
             'r31独立工具包：唯一注册、17模块、73个Skill文件；真实共享变速dry-run、原观察保持和工程验证，作者工程及素材不变。',
             '安装版/Skill/媒体/三语完整文档及暂存字节核验；保留211条历史R记录及38项原关闭条件；60功能、20服务、75组实际能力声明。',
             '保留开发失败：重复嵌套变速的额外alpha取整和缺少显式sync_content:retime的测试场景；修复共享输出路径/明确请求后通过，未放宽逐像素门槛。'],
        '.zh-TW': ['離線安裝CLI0.1.30/local.28-final-r1，222個產品Python檔案/schema與原始碼一致；唯一Skill、17模組、73檔案。',
             '安裝版分組核驗：追蹤79、磁性66、編輯195、綁定71、Float32合成98、渲染46、音訊65、舊CLI192；各組獨立，無跳過。',
             'C40統一Skill實際2倍速：共享作者依賴圖、逐層輸出；全部18影格Float32/PTS/幾何與原偶數影格一致；完整72000雙聲道取樣與獨立tempo誤差0；包及佇列重現。',
             'r31獨立工具包：唯一註冊、17模組、73個Skill檔案；真實共享變速dry-run、原觀察保留及工程驗證，作者工程及素材不變。',
             '安裝版/Skill/媒體/三語完整文件及暫存位元組核驗；保留211條歷史R記錄及38項原關閉條件；60功能、20服務、75組實際能力聲明。',
             '保留開發失敗：重複巢狀變速的額外alpha取整及缺少明確sync_content:retime的測試情境；修復共享輸出/明確請求後通過，未放寬逐像素門檻。'],
        '.en': ['Installed CLI 0.1.30/local.28-final-r1: 222 product Python files/schema equal source; one Skill, 17 modules, 73 files.',
             'Separate installed groups, with no skips: tracking 79, magnetic 66, editing 195, bindings 71, Float32 98, render 46, audio 65, legacy 192.',
             'C40 actual registered Skill 2x edit: shared author dependency graph and per-layer outputs; all 18 Float32/PTS/geometry frames equal original even frames; all 72000 stereo samples equal the independent tempo oracle; package and queue reproduced.',
             'r31 fresh isolated kit: one registration, 17 modules, 73 Skill files; real shared-retime dry-run/observations/validation with unchanged authored project and assets.',
             'Installed/Skill/media/full trilingual documentation and staged-byte audit; retain 211 historical R rows and 38 original goal closures; 60 functions, 20 services, 75 actual declarations.',
             'Preserved failed development attempt: extra alpha rounding on repeated nesting and missing explicit sync_content:retime in fixtures. Fixed shared outputs/requests; no pixel threshold relaxation.']}
    targets = ['installation-final-r1/verification.json', 'tracking-installed-r1/verification.json',
        'case-r1/verification.json', 'kit-r1/verification.json', 'final-delivery-r1/verification.json',
        'development-attempts-r1/verification.json']
    for suffix, name, title, description, verification, f14, f60 in languages:
        text = (ROOT/name).read_text('utf-8-sig'); old = rows(text); assert len(old)==211
        text = text.replace('**CLI0.1.29 / alpha.4-local.27 / r30 kit',
            '**Historical / 历史 / 歷史：CLI0.1.29 / alpha.4-local.27 / r30 kit', 1)
        block = ('<!-- tracking-retime-current -->\n\n**CLI0.1.30 / alpha.4-local.28 / r31 kit · 1 Skill / 17 modules.**\n\n'
            + description + '\n\n[Workflow](docs/product/TRACKING_RETIME.md) · [C40](docs/product/CASES.md#c40-tracking-retime) · '
            '[Install](docs/releases/CLI_0.1.30_LOCAL.md) · [Evidence](docs/validation/跟踪共享变速实测_2026-10-26.md)\n\n'
            '![Actual registered Skill / silent GIF](docs/assets/tracking-retime-20261026-r1/edited.gif)\n\n'
            + verification + '\n\n<!-- /tracking-retime-current -->\n\n')
        text = text.replace('<!-- tracking-magnetic-current -->', block+'<!-- tracking-magnetic-current -->', 1)
        for number, line in [(14, f14), (60, f60)]:
            text = re.sub(r'^\| F'+str(number)+r'\s*\|.*$', lambda _: line, text, count=1, flags=re.M)
        text = '\n'.join(line.replace('local.27/final-r1/installed','local.28/final-r1/installed').replace('0.1.29','0.1.30')
            if not line.startswith('| R') and 'local.27/final-r1/installed' in line else line for line in text.splitlines())+'\n'
        additions = ['| R'+str(212+i)+' | 2026-10-26 '+title+' | '+d+' | [Evidence](docs/validation/evidence/tracking-retime-20261026-r1/'+target+') |'
            for i, (d, target) in enumerate(zip(descriptions[suffix], targets))]
        last = re.search(r'^\| R211\s*\|.*$', text, re.M); assert last
        text = text[:last.end()]+'\n'+'\n'.join(additions)+text[last.end():]
        assert len(rows(text))==217 and all(rows(text)[k]==v for k,v in old.items())
        write(name,text)
        for path in ('docs/product/SKILLS'+suffix+'.md','docs/skills/UNIFIED_SKILL'+suffix+'.md'):
            link = 'TRACKING_RETIME.md' if '/product/' in path else '../product/TRACKING_RETIME.md'
            current = '<!-- community-current -->\n\n**CLI0.1.30 / alpha.4-local.28 / r31 kit · 1 Skill / 17 modules / 73 files.**\n\n'+description+'\n\n[Shared-author retime workflow]('+link+')\n\n<!-- /community-current -->'
            write(path,re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:current,(ROOT/path).read_text('utf8'),count=1,flags=re.S))
    validation = '# 跟踪共享作者变速实测 · 2026-10-26\n\nCLI0.1.30/local.28-final-r1/r31；原生Windows、唯一统一Skill、17模块。\n\n| Scope | Actual evidence |\n|---|---|\n'
    scopes = [('Offline install222 source files','installation-final-r1/verification.json'),
        ('One Skill/4 existing CPU-CUDA packs','activation-final-r1/activation-and-registration.json')]
    scopes += [(name+' '+str(count),name+'-installed-r1/verification.json') for name,count in [('tracking',79),('magnetic',66),('editing',195),('bindings',71),('float',98),('render',46),('audio',65),('legacy',192)]]
    scopes += [('Actual C40','case-r1/verification.json'),('All18 Float32/PTS/geometry','case-r1/native-float-frame-oracles.json'),
        ('Shared context','case-r1/shared-author-context.json'),('GPU cleanup','case-r1/gpu-receipt.json'),('Queue complete frames/PCM','queue-r1/verification.json'),
        ('Static media inspection','media-inspection-r1/verification.json'),('Fresh kit','kit-r1/verification.json'),('Final audit','final-delivery-r1/verification.json'),
        ('Staged-byte evidence directory',''),('Preserved failed development attempt','development-attempts-r1/verification.json')]
    validation += ''.join('| '+label+' | [Evidence](evidence/tracking-retime-20261026-r1/'+target+') |\n' for label,target in scopes)
    validation += ('\nC40以CC0 C36动态裁切/运镜/ROI标签和合成双声道音轨为输入，统一Skill实际执行2倍速。原片3秒36帧成为1.5秒18帧；'
        '全部Float32像素、原生PTS、作者时钟和动态几何匹配原片偶数帧0,2,…,34，全部解码帧也相同。完整72000双声道样本与独立原生FFmpeg '
        '`atempo=2.0`、显式补齐/裁至72000采样的原声音轨逐样本相等，最大误差0。验证关联声音未重复及时间映射，不代表自然听感。\n\n'
        '子序列保留完整作者图；父层通过sequence_clip_id选择独立输出。保留原始观察、外部层序和浮点scalar alpha；部分变速保留区间外源路由；'
        '重复关联变速保持共享时钟。父层解除关联会分离完整输出，继续修改跟踪需编辑共享作者图；不承诺独立父包装间的新活动绑定。\n\n'
        '源码source-r1保留8个像素失败及1个错误：重复包装额外透明度取整，以及两个测试未明确sync_content:retime。修复共享输出路径和明确测试请求后source-r3/安装版79项通过；'
        '像素门槛保持完全相等。source-r2是77项中间结果，未计入最终安装版。\n\n'
        '实际GPU投影及worker/shared handle清理留证。原生包重导入与独立队列另行逐帧/完整PCM核验。只做静态抽帧检查；未作连续播放、人工听审、自然跟踪/遮挡质量验收；无新模型推理、源码回退或虚拟化。'
        'OTIO/MLT/草稿原生时钟烘焙、复杂场景质量与全部38原关闭条件保持开放。\n\n'
        '[Workflow](../product/TRACKING_RETIME.md) · [C40 media](../product/CASES.md#c40-tracking-retime) · [Install](../releases/CLI_0.1.30_LOCAL.md).\n')
    write('docs/validation/跟踪共享变速实测_2026-10-26.md',validation)
    release = '# CLI0.1.30 · shared-author tracking retime · local.28\n\n本地离线构建并加载唯一 `$agent-ffmpeg-local-editor`；公开alpha.3/CLI0.1.2原标签与附件保持。\n\n| Item | Verified value |\n|---|---|\n'
    for key,value in [('Runtime','v0.1.0-alpha.4-local.28/final-r1/installed'),('Local ZIP',install['archive']),('ZIP bytes',str(install['archive_bytes'])),('ZIP SHA256',install['archive_sha256']),('Manifest SHA256',install['manifest_sha256']),('CLI and wheel','0.1.30'),('Product','222 Python files/schema equal source'),('Skill','1 entry/17 modules/73 files;r31 kit')]:
        release += '| '+key+' | `'+value+'` |\n'
    release += ('\n[Offline setup](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Commands](../product/TRACKING_RETIME.md) · [Evidence](../validation/跟踪共享变速实测_2026-10-26.md) · '
        '[C40](../product/CASES.md#c40-tracking-retime) · [r31 kit](../skills/agent-editor-kit-community-unified-skill-r31.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.30-r31.json).\n\n'
        'Separate installed zero-skip groups79/66/195/71/98/46/65/192; actual2x C40 all18 Float32/decoded frames and complete72000 stereo PCM samples match independent oracles. '
        'Native package and queue checked separately. Synthetic diagnostic media/static review; no full-goal or natural/listening acceptance.\n')
    write('docs/releases/CLI_0.1.30_LOCAL.md',release)
    media = '../assets/'+Path(case['public']).name
    case_text = ('\n<a id="c40-tracking-retime"></a>\n\n## C40 · 跟踪共享作者变速 · CLI0.1.30\n\n'
        'CC0动态裁切/运镜/ROI标签与合成双声道音轨；实际统一Skill执行2倍速，36帧3秒成为18帧1.5秒。全部Float32/解码画面、原生PTS和动态几何对应原偶数帧；'
        '完整72000双声道采样与独立tempo输出误差0。工程包及队列分别核验；实际GPU投影和清理留证。静态检查；无自然质量/连续播放/人工听审验收。\n\n'
        '![Actual silent GIF]('+media+'/edited.gif)\n\n[Before MP4]('+media+'/before.mp4) · [Edited MP4]('+media+'/edited.mp4) · '
        '[Editable package]('+media+'/editable-tracking-retime.aevpkg.zip) · [Source/rights]('+media+'/SOURCE.txt) · [Hashes]('+media+'/media-manifest.json) · '
        '[Workflow](TRACKING_RETIME.md) · [Evidence](../validation/跟踪共享变速实测_2026-10-26.md).\n')
    write('docs/product/CASES.md',(ROOT/'docs/product/CASES.md').read_text('utf8')+case_text)
    write('docs/product/TRACKING_RETIME.md',(ROOT/'docs/product/TRACKING_RETIME.md').read_text('utf8')+case_text)
    for path in ('docs/product/FLOAT_TRACKING.md','docs/product/TRACKING_EDITS.md','docs/product/TRACKING_SOURCE_EDITS.md','docs/product/TRACKING_MAGNETIC.md'):
        text=(ROOT/path).read_text('utf8'); first=text.index('\n')+1
        write(path,text[:first]+'\nCLI0.1.30 adds [shared-author tracking retime and C40](TRACKING_RETIME.md); prior versioned records retain their historical scope.\n'+text[first:])
    path='docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=(ROOT/path).read_text('utf8')
    for old,new in [('local.27/final-r1/installed','local.28/final-r1/installed'),('local.27/candidate-r1/bundle.zip','local.28/candidate-r1/bundle.zip'),
        ('v0.1.0-alpha.4-local.27` / CLI 0.1.29','v0.1.0-alpha.4-local.28` / CLI 0.1.30'),
        ('055017499795ca1df41d541736952346095f6c3761cfed73b12a4bcee1b6c9ea',install['archive_sha256']),
        ('9f48fd2750870f8ec1c313a1b2254b0e06d80af269e0cec34cdbada02b5e9e76',install['manifest_sha256'].split(':')[1]),
        ('agent-editor-kit-community-unified-skill-r30.zip','agent-editor-kit-community-unified-skill-r31.zip'),
        ('community-unified-skill-package-0.1.29-r30.json','community-unified-skill-package-0.1.30-r31.json')]:text=text.replace(old,new)
    write(path,text+'\nCLI0.1.30/local.28/r31：[shared-author tracking retime](TRACKING_RETIME.md), [verified local delivery](../releases/CLI_0.1.30_LOCAL.md).\n')
    path='docs/README.md';text=(ROOT/path).read_text('utf8').replace('Current local / 当前本地 / 目前本地：**CLI0.1.29 / local.27 / r30 kit**','Historical / 历史 / 歷史：**CLI0.1.29 / local.27 / r30 kit**',1)
    write(path,text.replace('\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.30 / local.28 / r31 kit** · [Shared-author retime](product/TRACKING_RETIME.md) · [Install](releases/CLI_0.1.30_LOCAL.md) · [C40](product/CASES.md#c40-tracking-retime).\n',1))
    for path in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        text=(ROOT/path).read_text('utf8').replace('当前本地 **CLI0.1.29 / alpha.4-local.27 / r30 kit**','此前本地 **CLI0.1.29 / alpha.4-local.27 / r30 kit**',1);first=text.index('\n')+1
        text=text[:first]+'\n当前本地 **CLI0.1.30 / alpha.4-local.28 / r31 kit**：[跟踪共享作者变速](TRACKING_RETIME.md)已实装，逐层输出保留原始观察/外部层序/alpha并避免重复音轨；[实际全帧/完整PCM](../validation/跟踪共享变速实测_2026-10-26.md)。全部38原关闭条件保持。\n'+text[first:]
        text=text.replace('local.27-final-r1/CLI0.1.29/r30','local.28-final-r1/CLI0.1.30/r31')
        write(path,text)
    print('C40 documented; all211 historical R rows retained; original goal conditions unchanged.')


if __name__=='__main__':main()
