"""Publish verified C38 usage and append six acceptance rows without history loss."""
from pathlib import Path
import hashlib,json,re,subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-source-edits-20261026-r1'
BASELINE='30815df0090652c17a896afae5845f3eeef76b29'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def load(p):return json.loads(Path(p).read_bytes())
def write(name,s):(ROOT/name).write_text(s,encoding='utf8',newline='\n')
def rowmap(s):return {m[1]:m[0] for m in re.finditer(r'^\| (R\d{2,3})\s*\|.*$',s,re.M)}

def main():
    install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/'case-r3/verification.json')
    assert install['status']=='installed-and-byte-verified' and case['status']=='passed'
    languages=[('README.md','',
        '跟踪源可滑移、真实头尾外扩及使用真实句柄roll/slide；原始观察保留，每个分片独立保留作者偏移，关联音轨同步源编辑，锁定引用冲突整体拒绝。修复分段恒速曲线在帧边界的浮点误选。',
        '| F60 | 原生跟踪后续编辑 | 分割/裁切/波纹/范围、物理源滑移与真实外扩；分片作者偏移、ROI基准、目标透明度及关联音轨保持。 | `timeline compose/edit; preview; render; package` | 显式Float32；有限源/锁/重叠/循环预算门禁；容器变速、磁性传播和中间格式烘焙继续推进。 |'),
        ('README.zh-TW.md','.zh-TW',
        '追蹤來源可滑移、真實頭尾外擴及使用真實句柄roll/slide；保留原始觀察，各分片獨立保留作者偏移，關聯音軌同步來源編輯，鎖定引用衝突整體拒絕。修正分段恆速曲線在影格邊界的浮點誤選。',
        '| F60 | 原生追蹤後續編輯 | 分割/裁切/波紋/範圍、物理來源滑移與真實外擴；分片作者偏移、ROI基準、目標透明度及關聯音軌保留。 | `timeline compose/edit; preview; render; package` | 明確Float32；有限來源/鎖/重疊/循環預算門禁；容器變速、磁性傳播及中間格式烘焙持續推進。 |'),
        ('README.en.md','.en',
        'Tracked physical sources now support slip, real head/tail extension and source-handle roll/slide. Original observations, per-fragment author offsets, target opacity keys and linked audio remain editable; locked dependencies reject atomically. Integer-grid piecewise constant curves use rational inversion at native frame boundaries.',
        '| F60 | Editing native tracking | Split/trim/ripple/range edits plus physical slip/extension; preserve fragment author offsets, ROI reference, target opacity and linked audio. | `timeline compose/edit; preview; render; package` | Explicit Float32; finite source/lock/overlap/cycle budgets. Bound-container retime, magnetic cut propagation and interchange baking remain open. |')]
    for name,suffix,description,function in languages:
        path=ROOT/name;text=path.read_text('utf-8-sig');old=rowmap(text);assert len(old)==199
        text=text.replace('**CLI0.1.27 / alpha.4-local.25 / r28 kit','**Historical / 历史 / 歷史：CLI0.1.27 / alpha.4-local.25 / r28 kit',1)
        block='<!-- tracking-source-edits-current -->\n\n**CLI0.1.28 / alpha.4-local.26 / r29 kit · 1 Skill / 17 modules.**\n\n'+description+'\n\n[Workflow](docs/product/TRACKING_SOURCE_EDITS.md) · [C38](docs/product/CASES.md#c38-tracking-source-edits) · [Local install](docs/releases/CLI_0.1.28_LOCAL.md) · [Evidence](docs/validation/跟踪源编辑实测_2026-10-26.md)\n\n![Actual registered Skill / silent GIF](docs/assets/tracking-source-edits-20261026-r3/edited.gif)\n\n36 Float32 frames equal an independent unbound project; original native indices and 144000 stereo PCM samples verified. Synthetic diagnostic content; no natural-quality or human listening acceptance.\n\n<!-- /tracking-source-edits-current -->\n\n'
        text=text.replace('<!-- tracking-edits-current -->',block+'<!-- tracking-edits-current -->',1)
        text=re.sub(r'^\| F60\s*\|.*$',lambda _:function,text,count=1,flags=re.M)
        lines=[]
        for line in text.splitlines():
            if 'local.25/final-r4/installed' in line and not line.startswith('| R'):
                line=line.replace('local.25/final-r4/installed','local.26/final-r1/installed').replace('0.1.27','0.1.28')
            lines.append(line)
        text='\n'.join(lines)+'\n'
        descriptions=[
            'Offline ZIP installed; 220 product Python files/schema equal source; CLI0.1.28/local.26-final-r1; one Skill/17 modules/73 files.',
            'Installed groups: 46 tracking/source,195 editing,71 bindings,98 Float32,46 render,65 audio,192 legacy; zero skips, kept as separate groups.',
            'C38 actual registered source/audio slip and real head-tail extension: 36 Float32 frames equal independent unbound authoring; all native indices;144000 complete stereo samples error0; editable package roundtrip.',
            'r29 fresh isolated kit: one registration/17 modules/73 Skill files; actual source-edit dry-run, finite physical ranges and validation; real discovery retained.',
            'Final installed/Skill/media/document/staged-byte checks; 199 historical R rows and38 original closure cells preserved;60 functions/20 services/75 declarations.',
            'Development failures retained: initial insufficient physical handle fixture; actual two-frame flat-curve rounding counterexample fixed with rational inversion; no epsilon or tolerance relaxation; initial case harness context lookup and an incorrect nominal-FPS oracle were corrected before final acceptance; both failed runs retained.'
        ]
        if suffix!='.en':
            descriptions=[
                '离线 ZIP 已安装；220 个产品 Python 文件及 schema 与源码逐字节一致；CLI0.1.28/local.26-final-r1；1 个 Skill、17 个模块、73 个文件。',
                '安装版分组验证：跟踪/源编辑46项、编辑195项、绑定71项、Float32合成98项、渲染46项、音频65项、旧CLI192项；均无跳过，各组独立计数。',
                'C38真实统一Skill执行视频与关联音轨滑移及头尾外扩：36帧Float32像素与独立无绑定工程一致；逐项核对原PTS索引；完整144000双声道采样误差0；可编辑工程包往返。',
                'r29工具包独立注册：唯一入口、17模块、73个Skill文件；实际源滑移dry-run与验证，原作者工程及素材不变，实际Codex发现入口不变。',
                '安装版、Skill、媒体、文档及暂存字节核验；保留199条历史R记录和38项原关闭条件；60项功能、20类服务、75组实际能力声明。',
                '保留失败反例：不足真实源句柄的测试输入、恒速曲线两帧误选、案例脚本错误入口及误用标称fps的独立参照；分别修复，未增加epsilon或降低像素精度。'
            ]
            if suffix=='.zh-TW':
                descriptions=[
                    '離線 ZIP 已安裝；220個產品Python檔案及schema與原始碼逐位元組一致；CLI0.1.28/local.26-final-r1；1個Skill、17個模組、73個檔案。',
                    '安裝版分組驗證：追蹤/來源編輯46項、編輯195項、綁定71項、Float32合成98項、算繪46項、音訊65項、舊CLI192項；均無略過，各組獨立計數。',
                    'C38真實統一Skill執行視訊與關聯音軌滑移及頭尾外擴：36影格Float32像素與獨立無綁定工程一致；逐項核對原PTS索引；完整144000雙聲道取樣誤差0；可編輯工程包往返。',
                    'r29工具包獨立註冊：唯一入口、17模組、73個Skill檔案；實際來源滑移dry-run與驗證，原作者工程及素材不變，實際Codex探索入口不變。',
                    '安裝版、Skill、媒體、文件及暫存位元組核驗；保留199條歷史R紀錄和38項原關閉條件；60項功能、20類服務、75組實際能力宣告。',
                    '保留失敗反例：不足真實來源句柄的測試輸入、恆速曲線兩影格誤選、案例腳本錯誤入口及誤用標稱fps的獨立參照；分別修正，未增加epsilon或降低像素精度。'
                ]
        targets=['installation-final-r1/verification.json','tracking-installed-r1/verification.json','case-r3/verification.json',
            'kit-r1/verification.json','final-delivery-r1/verification.json','development-attempts-r1/verification.json']
        label={'':'原生跟踪源编辑','.zh-TW':'原生追蹤來源編輯','.en':'Native tracking source edits'}[suffix]
        added=['| R'+str(200+i)+' | 2026-10-26 '+label+' | '+d+' | [Evidence](docs/validation/evidence/tracking-source-edits-20261026-r1/'+t+') |' for i,(d,t) in enumerate(zip(descriptions,targets))]
        match=re.search(r'^\| R199\s*\|.*$',text,re.M);assert match
        text=text[:match.end()]+'\n'+'\n'.join(added)+text[match.end():]
        assert all(rowmap(text)[k]==v for k,v in old.items()) and len(rowmap(text))==205
        write(name,text)
        for item in ['docs/product/SKILLS'+suffix+'.md','docs/skills/UNIFIED_SKILL'+suffix+'.md']:
            path=ROOT/item;s=path.read_text('utf8');link='TRACKING_SOURCE_EDITS.md' if '/product/' in item else '../product/TRACKING_SOURCE_EDITS.md'
            current='<!-- community-current -->\n\n**CLI0.1.28 / alpha.4-local.26 / r29 kit · 1 Skill / 17 modules / 73 files.**\n\n'+description+'\n\n[Physical tracked-source editing]('+link+')\n\n<!-- /community-current -->'
            write(item,re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:current,s,count=1,flags=re.S))
    evidence='''# 跟踪源滑移与外扩实测 · 2026-10-26

CLI0.1.28/local.26-final-r1/r29。保存原始观测，跟踪源实际滑移、头尾外扩和真实句柄roll/slide；
每个源分片单独保留作者偏移，视频目标基准透明度重锚。恒速曲线采用有理数反求。

| Scope | Result / evidence |
|---|---|
'''
    for title,target in [('Offline installed220 files','installation-final-r1/verification.json'),
        ('One Skill17 modules/4 existing CPU-CUDA packs','activation-final-r1/activation-and-registration.json'),
        ('46 tracking-source checks','tracking-installed-r1/verification.json'),('195 editing','editing-installed-r1/verification.json'),
        ('71 binding/canvas/fragments','bindings-installed-r1/verification.json'),('98 float composition','float-installed-r1/verification.json'),
        ('46 render','render-installed-r1/verification.json'),('65 audio','audio-installed-r1/verification.json'),('192 legacyCLI/preview/queue/schema','legacy-installed-r1/verification.json'),
        ('C38 actual registered Skill','case-r3/verification.json'),('36 independent Float32 oracles','case-r3/native-float-oracles.json'),
        ('GPU actual operation and cleanup','case-r3/gpu-receipt.json'),('Independent queue all frames/PCM','queue-r1/verification.json'),
        ('Fresh r29 registration and source-edit dry-run','kit-r1/verification.json'),('Final byte/document audit','final-delivery-r1/verification.json'),
        ('Development failures preserved','development-attempts-r1/verification.json')]:
        evidence+='| '+title+' | [Evidence](evidence/tracking-source-edits-20261026-r1/'+target+') |\n'
    evidence+='''
实际C38通过统一入口把有限内段视频/音频先滑移0.25秒，再头尾各外扩0.25秒。输出仍3秒/36帧，
其中30帧有真实源覆盖；独立无绑定工程明确编写源范围及逐帧hold位置，不调用编辑或绑定算法。
全部Float32像素相同、原生索引逐项匹配ffprobe读取的实际PTS，覆盖输出帧3..32；未以标称12fps伪造均匀时钟，完整144000双声道采样独立源拼接误差0。
工程包重导入后的36解码帧/时钟与完整PCM一致。8bit H.264 CRF0仅作受控核验边界。

源码首次43项有1个测试样例缺少2倍速所需的真实源句柄；修正输入后，45项发现恒速曲线外扩
时两个原生帧误选。反例原日志保留；最终46项采用有理数恒速反求通过，没有加epsilon或降低像素门槛。
首次案例校验脚本读取了不存在的context.host属性；第二次独立参照误以标称12fps推算原PTS。分别修正实际timeline入口与ffprobe原生时间戳参照，两个失败记录均保留。
非恒速仍有既有浮点编译边界；自然身份/遮挡、连续播放、人工听审、全竞品等价均未验收。
各组独立统计，不合并历史通过次数。原生Windows；无虚拟环境、源码回退、新模型推理或外部消息。

[Workflow](../product/TRACKING_SOURCE_EDITS.md) · [C38 media](../product/CASES.md#c38-tracking-source-edits) ·
[Install](../releases/CLI_0.1.28_LOCAL.md)。全部38原关闭条件保持。
'''
    write('docs/validation/跟踪源编辑实测_2026-10-26.md',evidence)
    release='# CLI0.1.28 · physical tracked-source editing · local.26\n\n本地编译、离线安装并加载唯一 `$agent-ffmpeg-local-editor`；公开 alpha.3/CLI0.1.2 标签、附件和摘要保持。\n\n'
    values=[('Runtime','v0.1.0-alpha.4-local.26/final-r1/installed'),('Local ZIP',install['archive']),('ZIP bytes',str(install['archive_bytes'])),
        ('ZIP SHA256',install['archive_sha256']),('Manifest SHA256',install['manifest_sha256']),('Version','CLI and wheel0.1.28'),
        ('Product','220 executable files and bundled schema equal source'),('Skill','1 entry/17 modules/73 files; r29 kit')]
    release+='| Item | Verified value |\n|---|---|\n'+''.join('| '+k+' | `'+v+'` |\n' for k,v in values)
    release+='\n[Offline setup](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Full workflow/commands](../product/TRACKING_SOURCE_EDITS.md) · [Actual evidence and limits](../validation/跟踪源编辑实测_2026-10-26.md) · [C38](../product/CASES.md#c38-tracking-source-edits) · [r29 kit](../skills/agent-editor-kit-community-unified-skill-r29.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.28-r29.json).\n\nSeparate installed regression groups:46/195/71/98/46/65/192, zero skips. C38 checks all36 Float32 frames, original PTS,144000 complete stereo PCM samples, editable package and queue. Static frames checked; no natural-quality, continuous playback or human listening acceptance. The complete goal and38 original closure conditions remain open.\n'
    write('docs/releases/CLI_0.1.28_LOCAL.md',release)
    public=Path(case['public']).relative_to(ROOT).as_posix()
    case_text='''\n<a id="c38-tracking-source-edits"></a>

## C38 · 跟踪源滑移/真实外扩 · CLI0.1.28

已登记CC0移动几何、透明标记与双声道合成音，有限内段先滑移0.25秒，再关联头尾各外扩0.25秒。
36帧/3秒，其中30帧有真实源覆盖；全部Float32像素与独立无绑定作者工程相同，完整144000双声道采样误差0。
工程包重导入与队列分别核验。实际GPU投影及清理留证；GIF静音，无自然身份/连续播放/人工听审验收。

'''
    relative='../assets/'+Path(public).name
    case_text+='![Actual silent GIF]('+relative+'/edited.gif)\n\n[Before MP4]('+relative+'/before.mp4) · [Edited MP4]('+relative+'/edited.mp4) · [Editable package]('+relative+'/editable-tracking-source-edits.aevpkg.zip) · [Source/rights]('+relative+'/SOURCE.txt) · [Hashes]('+relative+'/media-manifest.json) · [Workflow](TRACKING_SOURCE_EDITS.md) · [Evidence](../validation/跟踪源编辑实测_2026-10-26.md).\n'
    path=ROOT/'docs/product/CASES.md';write('docs/product/CASES.md',path.read_text('utf8')+case_text)
    path=ROOT/'docs/product/TRACKING_SOURCE_EDITS.md';s=path.read_text('utf8')
    s+='\n## C38 实际案例 / Actual case\n\n'+case_text.split('## C38',1)[1].split('\n',1)[1]
    # The source guide and case catalog share docs/product as their parent.
    write('docs/product/TRACKING_SOURCE_EDITS.md',s)
    for name in ['docs/product/TRACKING_EDITS.md','docs/product/FLOAT_TRACKING.md']:
        path=ROOT/name;s=path.read_text('utf8');head=s.index('\n')+1
        s=s[:head]+'\nCLI0.1.28 extends tracked physical slip/real source handles; see [current source-edit workflow](TRACKING_SOURCE_EDITS.md). Earlier versioned checks below retain their original scope.\n'+s[head:];write(name,s)
    path=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=path.read_text('utf8')
    s=s.replace('local.25/final-r4/installed','local.26/final-r1/installed').replace('local.25/candidate-r4/bundle.zip','local.26/candidate-r1/bundle.zip')
    s=s.replace('v0.1.0-alpha.4-local.25` / CLI 0.1.27','v0.1.0-alpha.4-local.26` / CLI 0.1.28')
    s=s.replace('5b211392c31a5eaa8c99102e1f2f2c1d819bdda1808d68cbcabad7393e75bc32',install['archive_sha256'])
    s=s.replace('ab670088d524ff5ee501d5a9f2cb9e9486cd5d35a16b6c2bde9f41ffdacd442d',install['manifest_sha256'].split(':')[1])
    s=s.replace('agent-editor-kit-community-unified-skill-r28.zip','agent-editor-kit-community-unified-skill-r29.zip').replace('community-unified-skill-package-0.1.27-r28.json','community-unified-skill-package-0.1.28-r29.json')
    s=s.replace('## CLI0.1.27 当前交付 / Current delivery','## CLI0.1.27 历史交付 / Historical delivery')
    s+='\nCLI0.1.28/local.26/r29：tracked physical slip/extension and rational constant clocks; [full workflow](TRACKING_SOURCE_EDITS.md), [verified release](../releases/CLI_0.1.28_LOCAL.md). Earlier local versions remain historical.\n';write('docs/product/COMMUNITY_LOCAL_DELIVERY.md',s)
    path=ROOT/'docs/README.md';s=path.read_text('utf8').replace('Current local / 当前本地 / 目前本地：**CLI0.1.27 / local.25 / r28 kit**','Historical / 历史 / 歷史：**CLI0.1.27 / local.25 / r28 kit**',1)
    s=s.replace('\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.28 / local.26 / r29 kit** · [Source editing](product/TRACKING_SOURCE_EDITS.md) · [Install](releases/CLI_0.1.28_LOCAL.md) · [C38](product/CASES.md#c38-tracking-source-edits).\n',1);write('docs/README.md',s)
    for name in ['docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md']:
        path=ROOT/name;s=path.read_text('utf8');s=s.replace('当前本地 **CLI0.1.27 / alpha.4-local.25 / r28 kit**','此前本地 **CLI0.1.27 / alpha.4-local.25 / r28 kit**',1)
        first=s.index('\n')+1;s=s[:first]+'\n当前本地 **CLI0.1.28 / alpha.4-local.26 / r29 kit**：[跟踪源编辑](TRACKING_SOURCE_EDITS.md)已接入物理滑移/外扩、分片基准和有理数恒速时钟；[实际完整像素/PCM](../validation/跟踪源编辑实测_2026-10-26.md)。全部38原关闭条件保持。\n'+s[first:]
        if 'GOAL_GAPS' in name:s=s.replace('local.25-final-r4/CLI0.1.27/r28','local.26-final-r1/CLI0.1.28/r29')
        else:s=s.replace('当前CLI0.1.26/local.24-final-r2/r27本地安装并加载','当前CLI0.1.28/local.26-final-r1/r29本地安装并加载')
        write(name,s)
    print('Three full READMEs, original199 rows retained, C38 and native source-edit workflow updated.')

if __name__=='__main__':main()
