"""Document verified C39 while retaining every historical README row and goal gate."""
from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-magnetic-20261026-r1'

def load(p):return json.loads(Path(p).read_bytes())
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s):return {m[1]:m[0] for m in re.finditer(r'^\| (R\d{2,3})\s*\|.*$',s,re.M)}

def main():
    install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/'case-r1/verification.json')
    assert install['status']=='installed-and-byte-verified' and case['status']=='passed'
    language=[('', 'README.md','原生跟踪磁性重排',
        '磁性重排支持跟踪源、标签与关联音轨跨主轨剪口同步拆分；从剪切前的完整作者工程重建源引用，保留原始观察、ROI基准、每分片偏移及完整处理时钟。',
        '36帧Float32像素、原生PTS和动态跟踪几何均按独立指定的原帧顺序保持；完整144000双声道采样误差0。合成诊断素材，无自然质量、连续播放或人工听审验收。',
        '| F12 | 磁吸、主轨与关联音画 | 主轨重排、原生跟踪跨剪口同步拆分、区域关联ID和音画附着。 | `timeline edit` | 显式同步及拆分策略；锁、转场端点和资源门禁；非原生跟踪跨剪口继续受限。 |',
        '| F60 | 原生跟踪后续编辑 | 磁性重排分片路由、分割/裁切/波纹/范围、物理滑移与外扩；保留原始观察、分片偏移、ROI基准、目标透明度及关联音轨。 | `timeline compose/edit; preview; render; package` | 显式Float32；有限源/锁/重叠/循环预算门禁；带绑定容器变速及中间格式烘焙继续推进。 |'),
        ('.zh-TW','README.zh-TW.md','原生追蹤磁性重排',
        '磁性重排支援追蹤來源、標籤與關聯音軌跨主軌剪口同步拆分；從剪切前的完整作者工程重建來源引用，保留原始觀察、ROI基準、各分片偏移及完整處理時鐘。',
        '36影格Float32像素、原生PTS及動態追蹤幾何均按獨立指定的原影格順序保留；完整144000雙聲道取樣誤差0。合成診斷素材，未作自然品質、連續播放或人工聽審驗收。',
        '| F12 | 磁吸、主軌與關聯音畫 | 主軌重排、原生追蹤跨剪口同步拆分、區域關聯ID及音畫附著。 | `timeline edit` | 明確同步及拆分策略；鎖、轉場端點及資源門禁；非原生追蹤跨剪口仍受限。 |',
        '| F60 | 原生追蹤後續編輯 | 磁性重排分片路由、分割/裁切/波紋/範圍、物理滑移與外擴；保留原始觀察、分片偏移、ROI基準、目標透明度及關聯音軌。 | `timeline compose/edit; preview; render; package` | 明確Float32；有限來源/鎖/重疊/循環預算門禁；帶綁定容器變速及中間格式烘焙持續推進。 |'),
        ('.en','README.en.md','Native magnetic tracking',
        'Magnetic reorder now partitions tracked sources, followers and linked audio across main-track cuts. It rebuilds source routes from the complete pre-cut graph, retaining observations, pinned ROI references, fragment offsets and complete authored clocks.',
        'All36 Float32 frames, native PTS and dynamic tracking geometry retain the independently specified original-frame permutation; complete144000 stereo samples have zero error. Synthetic diagnostics; no natural-quality, continuous-playback or human-listening acceptance.',
        '| F12 | Magnetic tracks and linked edits | Main-track reorder, synchronized native tracking cuts, region-specific links and attached audio. | `timeline edit` | Explicit sync/split policies; locks, transition endpoints and resource gates. Non-native tracking cuts remain guarded. |',
        '| F60 | Editing native tracking | Magnetic source routes, split/trim/ripple/range and physical slip/extension; retain observations, fragment offsets, ROI references, target opacity and linked audio. | `timeline compose/edit; preview; render; package` | Explicit Float32 with finite-source/lock/overlap/cycle budgets; bound-container retime and interchange baking remain open. |')]
    descriptions={
        '': ['离线安装CLI0.1.29/local.27-final-r1，220个产品Python文件和schema与源码一致；唯一Skill、17模块、73文件。',
             '安装版分组核验：跟踪61、磁性编辑66、编辑195、绑定71、Float32合成98、渲染46、音频65、旧CLI192；各组独立，无跳过。',
             'C39统一Skill实际跨剪口重排视频/标签/音轨：36帧Float32像素、原生PTS和动态几何按原帧重排；完整144000双声道采样误差0；工程包及队列复现。',
             'r30独立工具包：唯一注册、17模块、73个Skill文件；真实磁性重排dry-run、绑定改写和工程验证；作者工程及素材不变，实际发现入口不变。',
             '安装版/Skill/媒体/三语文档/暂存字节核验；保留205条历史R记录及38项原关闭条件；60功能、20服务、75组实际能力声明。',
             '保留开发失败：新测试请求的片段ID a与资产ID a冲突，正确拒绝；改用shot_a/shot_b/shot_c，未降低像素门槛或移除产品门禁。'],
        '.zh-TW':['離線安裝CLI0.1.29/local.27-final-r1，220個產品Python檔案及schema與原始碼一致；唯一Skill、17模組、73檔案。',
             '安裝版分組核驗：追蹤61、磁性編輯66、編輯195、綁定71、Float32合成98、算繪46、音訊65、舊CLI192；各組獨立，無略過。',
             'C39統一Skill實際跨剪口重排視訊/標籤/音軌：36影格Float32像素、原生PTS及動態幾何按原影格重排；完整144000雙聲道取樣誤差0；工程包及佇列重現。',
             'r30獨立工具包：唯一註冊、17模組、73個Skill檔案；真實磁性重排dry-run、綁定改寫及工程驗證；作者工程及素材不變，實際探索入口不變。',
             '安裝版/Skill/媒體/三語文件/暫存位元組核驗；保留205條歷史R紀錄及38項原關閉條件；60功能、20服務、75組實際能力宣告。',
             '保留開發失敗：新測試要求的片段ID a與資產ID a衝突，正確拒絕；改用shot_a/shot_b/shot_c，未降低像素門檻或移除產品門禁。'],
        '.en':['Offline CLI0.1.29/local.27-final-r1 installed;220 product Python files/schema equal source;one Skill,17 modules,73 files.',
             'Installed groups:61 tracking,66 magnetic,195 editing,71 bindings,98 Float32,46 render,65 audio,192 legacy;separate groups,zero skips.',
             'C39 actual registered source/follower/audio partition and reorder:all36 Float32 frames,native PTS and dynamic geometry retain original frame permutation;complete144000 stereo samples error0;package and queue reproduced.',
             'r30 fresh isolated kit:one registration,17 modules,73 Skill files;actual magnetic dry-run,binding rewrites and validation;author/assets and real discovery unchanged.',
             'Installed/Skill/media/three-language docs/staged-byte verification;205 historical rows and38 original closure conditions preserved;60 functions,20 services,75 declarations.',
             'Rejected development fixture retained:clip ID a conflicted with asset a;correctly rejected,then renamed shot_a/shot_b/shot_c without weakening pixels or product guards.']}
    targets=['installation-final-r1/verification.json','tracking-installed-r1/verification.json','case-r1/verification.json',
             'kit-r1/verification.json','final-delivery-r2/verification.json','development-attempts-r1/verification.json']
    for suffix,name,title,description,verified,f12,f60 in language:
        text=(ROOT/name).read_text('utf-8-sig');old=rows(text);assert len(old)==205
        text=text.replace('**CLI0.1.28 / alpha.4-local.26 / r29 kit','**Historical / 历史 / 歷史：CLI0.1.28 / alpha.4-local.26 / r29 kit',1)
        block='<!-- tracking-magnetic-current -->\n\n**CLI0.1.29 / alpha.4-local.27 / r30 kit · 1 Skill / 17 modules.**\n\n'+description+'\n\n[Workflow](docs/product/TRACKING_MAGNETIC.md) · [C39](docs/product/CASES.md#c39-tracking-magnetic) · [Install](docs/releases/CLI_0.1.29_LOCAL.md) · [Evidence](docs/validation/跟踪磁性重排实测_2026-10-26.md)\n\n![Actual registered Skill / silent GIF](docs/assets/tracking-magnetic-20261026-r1/edited.gif)\n\n'+verified+'\n\n<!-- /tracking-magnetic-current -->\n\n'
        text=text.replace('<!-- tracking-source-edits-current -->',block+'<!-- tracking-source-edits-current -->',1)
        for number,line in [(12,f12),(60,f60)]:text=re.sub(r'^\| F'+str(number)+r'\s*\|.*$',lambda _:line,text,count=1,flags=re.M)
        lines=[]
        for line in text.splitlines():
            if not line.startswith('| R') and 'local.26/final-r1/installed' in line:
                line=line.replace('local.26/final-r1/installed','local.27/final-r1/installed').replace('0.1.28','0.1.29')
            lines.append(line)
        text='\n'.join(lines)+'\n'
        additions=['| R'+str(206+i)+' | 2026-10-26 '+title+' | '+d+' | [Evidence](docs/validation/evidence/tracking-magnetic-20261026-r1/'+target+') |' for i,(d,target) in enumerate(zip(descriptions[suffix],targets))]
        match=re.search(r'^\| R205\s*\|.*$',text,re.M);assert match
        text=text[:match.end()]+'\n'+'\n'.join(additions)+text[match.end():]
        assert len(rows(text))==211 and all(rows(text)[k]==v for k,v in old.items());write(name,text)
        for path in ('docs/product/SKILLS'+suffix+'.md','docs/skills/UNIFIED_SKILL'+suffix+'.md'):
            link='TRACKING_MAGNETIC.md' if '/product/' in path else '../product/TRACKING_MAGNETIC.md'
            current='<!-- community-current -->\n\n**CLI0.1.29 / alpha.4-local.27 / r30 kit · 1 Skill / 17 modules / 73 files.**\n\n'+description+'\n\n[Magnetic tracking workflow]('+link+')\n\n<!-- /community-current -->'
            write(path,re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:current,(ROOT/path).read_text('utf8'),count=1,flags=re.S))
    validation='# 跟踪磁性重排实测 · 2026-10-26\n\nCLI0.1.29/local.27-final-r1/r30；原生Windows、唯一统一Skill、17模块。\n\n| Scope | Actual evidence |\n|---|---|\n'
    scopes=[('Offline install220 source files','installation-final-r1/verification.json'),('One Skill/4 existing CPU-CUDA packs','activation-final-r1/activation-and-registration.json')]
    scopes += [(name+' '+str(count),name+'-installed-r1/verification.json') for name,count in [('tracking',61),('magnetic',66),('editing',195),('bindings',71),('float',98),('render',46),('audio',65),('legacy',192)]]
    scopes += [('Actual C39','case-r1/verification.json'),('All36 Float32/PTS/geometry','case-r1/native-float-frame-oracles.json'),('GPU cleanup','case-r1/gpu-receipt.json'),('Queue complete frames/PCM','queue-r1/verification.json'),('Static media inspection','media-inspection-r1/verification.json'),('Fresh kit','kit-r1/verification.json'),('Final audit','final-delivery-r2/verification.json'),('Staged-byte evidence directory',''),('Rejected fixture','development-attempts-r1/verification.json')]
    validation+=''.join('| '+label+' | [Evidence](evidence/tracking-magnetic-20261026-r1/'+target+') |\n' for label,target in scopes)
    validation+='\nC39在原C36动态裁切/运镜/ROI跟随素材上增加三段透明主轨，实际统一Skill把第3秒移到第1秒前。跟踪视频、跟随标签和关联音轨均跨剪口拆分；保留原始观察和完整作者处理。\n\n独立指定帧序24..35、0..23；全部36帧Float32像素、原生PTS、作者时钟和动态几何与原帧一致。8bit yuv444p H.264 CRF0用于受控核验；全部解码帧按相同顺序保持。完整144000双声道采样按原PCM区间2..3s、0..2s拼接，误差0。工程包重导入和独立队列另行核验。\n\n保留开发失败：测试请求clip ID a与资产a冲突，产品正确拒绝；修正测试ID后61项通过。原58项早期通过和66项源码磁性回归分别保留，不计入最终安装版计数。\n\n合成CC0诊断素材和合成音；只做静态抽帧检查，无连续播放、人工听审、自然身份或遮挡质量验收；未执行新模型推理、源码回退或虚拟化。带绑定容器变速、外部格式烘焙及全部38原关闭条件继续按原目标推进。\n\n[Workflow](../product/TRACKING_MAGNETIC.md) · [C39 media](../product/CASES.md#c39-tracking-magnetic) · [Install](../releases/CLI_0.1.29_LOCAL.md).\n'
    write('docs/validation/跟踪磁性重排实测_2026-10-26.md',validation)
    release='# CLI0.1.29 · native magnetic tracking · local.27\n\n本地编译、离线安装并加载唯一 `$agent-ffmpeg-local-editor`。公开alpha.3/CLI0.1.2原标签与附件保持。\n\n| Item | Verified value |\n|---|---|\n'
    for key,value in [('Runtime','v0.1.0-alpha.4-local.27/final-r1/installed'),('Local ZIP',install['archive']),('ZIP bytes',str(install['archive_bytes'])),('ZIP SHA256',install['archive_sha256']),('Manifest SHA256',install['manifest_sha256']),('CLI and wheel','0.1.29'),('Product','220 Python files/schema equal source'),('Skill','1 entry/17 modules/73 files;r30 kit')]:release+='| '+key+' | `'+value+'` |\n'
    release+='\n[Offline setup](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Workflow/commands](../product/TRACKING_MAGNETIC.md) · [Actual evidence and limits](../validation/跟踪磁性重排实测_2026-10-26.md) · [C39](../product/CASES.md#c39-tracking-magnetic) · [r30 kit](../skills/agent-editor-kit-community-unified-skill-r30.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.29-r30.json).\n\nInstalled groups61/66/195/71/98/46/65/192 are separate and zero-skip. Actual C39 retains all36 Float32/decoded frames and full144000 stereo PCM samples through the specified permutation; package/queue checked separately. Synthetic diagnostic content, static review only. Complete parity and38 original closure conditions remain open.\n'
    write('docs/releases/CLI_0.1.29_LOCAL.md',release)
    media='../assets/'+Path(case['public']).name
    case_text='\n<a id="c39-tracking-magnetic"></a>\n\n## C39 · 跟踪磁性重排 · CLI0.1.29\n\nCC0移动几何、动态裁切/运镜、跟随标记和双声道合成音；实际统一Skill把第3秒移到第1秒前，跨剪口拆分视频、标签和关联音轨。全部36帧Float32像素/原生PTS/动态几何按原帧顺序保持；完整144000双声道采样误差0。工程包和队列分别核验，实际GPU投影与清理留证。GIF静音，无自然质量/连续播放/人工听审验收。\n\n![Actual silent GIF]('+media+'/edited.gif)\n\n[Before MP4]('+media+'/before.mp4) · [Edited MP4]('+media+'/edited.mp4) · [Editable package]('+media+'/editable-tracking-magnetic.aevpkg.zip) · [Source/rights]('+media+'/SOURCE.txt) · [Hashes]('+media+'/media-manifest.json) · [Workflow](TRACKING_MAGNETIC.md) · [Evidence](../validation/跟踪磁性重排实测_2026-10-26.md).\n'
    write('docs/product/CASES.md',(ROOT/'docs/product/CASES.md').read_text('utf8')+case_text)
    write('docs/product/TRACKING_MAGNETIC.md',(ROOT/'docs/product/TRACKING_MAGNETIC.md').read_text('utf8')+case_text)
    for path in ('docs/product/FLOAT_TRACKING.md','docs/product/TRACKING_EDITS.md','docs/product/TRACKING_SOURCE_EDITS.md'):
        text=(ROOT/path).read_text('utf8');first=text.index('\n')+1
        text=text[:first]+'\nCLI0.1.29 now supports synchronized magnetic tracking cuts/reorder; [current workflow and C39](TRACKING_MAGNETIC.md). Earlier versioned records below retain their original scope.\n'+text[first:];write(path,text)
    path='docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=(ROOT/path).read_text('utf8')
    for old,new in [('local.26/final-r1/installed','local.27/final-r1/installed'),('local.26/candidate-r1/bundle.zip','local.27/candidate-r1/bundle.zip'),('v0.1.0-alpha.4-local.26` / CLI 0.1.28','v0.1.0-alpha.4-local.27` / CLI 0.1.29'),('2b8620c8476878180863b05b57c40b848c3033153cfa5f8b6d3827f41ff78ed7',install['archive_sha256']),('6d6d3b1759ccf16f823660f39134bd4602f0434b9d9f67607699ff69b5cba0bf',install['manifest_sha256'].split(':')[1]),('agent-editor-kit-community-unified-skill-r29.zip','agent-editor-kit-community-unified-skill-r30.zip'),('community-unified-skill-package-0.1.28-r29.json','community-unified-skill-package-0.1.29-r30.json')]:text=text.replace(old,new)
    text=text.replace('当前新增 [原生PTS跟踪绑定与叠加轨]','CLI0.1.26 历史新增 [原生PTS跟踪绑定与叠加轨]')
    text+='\nCLI0.1.29/local.27/r30：native magnetic synchronized tracking cuts/reorder; [workflow](TRACKING_MAGNETIC.md), [verified local release](../releases/CLI_0.1.29_LOCAL.md). Previous versioned records remain historical.\n';write(path,text)
    path='docs/README.md';text=(ROOT/path).read_text('utf8').replace('Current local / 当前本地 / 目前本地：**CLI0.1.28 / local.26 / r29 kit**','Historical / 历史 / 歷史：**CLI0.1.28 / local.26 / r29 kit**',1)
    text=text.replace('\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.29 / local.27 / r30 kit** · [Magnetic tracking](product/TRACKING_MAGNETIC.md) · [Install](releases/CLI_0.1.29_LOCAL.md) · [C39](product/CASES.md#c39-tracking-magnetic).\n',1);write(path,text)
    for path in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        text=(ROOT/path).read_text('utf8').replace('当前本地 **CLI0.1.28 / alpha.4-local.26 / r29 kit**','此前本地 **CLI0.1.28 / alpha.4-local.26 / r29 kit**',1);first=text.index('\n')+1
        text=text[:first]+'\n当前本地 **CLI0.1.29 / alpha.4-local.27 / r30 kit**：[跟踪磁性重排](TRACKING_MAGNETIC.md)已实装，源/目标/音频跨剪口同步拆分并从完整原作者图重建引用；[全部画面/完整音轨实测](../validation/跟踪磁性重排实测_2026-10-26.md)。38项原关闭条件保持。\n'+text[first:]
        text=text.replace('local.26-final-r1/CLI0.1.28/r29','local.27-final-r1/CLI0.1.29/r30').replace('当前CLI0.1.28/local.26-final-r1/r29本地安装并加载','当前CLI0.1.29/local.27-final-r1/r30本地安装并加载');write(path,text)
    print('C39 documented;all205 historical rows retained in three full READMEs;38 original closure conditions unchanged.')

if __name__=='__main__':main()
