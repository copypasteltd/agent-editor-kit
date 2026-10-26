"""Append current delivery without removing any historical README evidence rows."""
from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-visibility-20261026-r1'
LANG=[('','README.md'),('.zh-TW','README.zh-TW.md'),('.en','README.en.md')]

def write(name,text):(ROOT/name).write_text(text,encoding='utf8',newline='\n')
def load(p):return json.loads(p.read_bytes())
def rows(s):return {m[1]:m[0] for m in re.finditer(r'^\| (R\d{2,3})\s*\|.*$',s,re.M)}

def main():
    install=load(BASE/'installation-final-r1/verification.json');case=load(BASE/'case-r2/verification.json')
    assert install['status']=='installed-and-byte-verified' and case['status']=='passed'
    names=('tracking','magnetic','editing','bindings','float','render','audio','legacy','effects','text')
    counts={name:load(BASE/(name+'-installed-r1/verification.json'))['tests'] for name in names
        if (BASE/(name+'-installed-r1/verification.json')).is_file()}
    assert set(names)-set(counts)<= {'text'}
    desc={
      '':'实际源像素/效果alpha和5类遮罩已接入跟踪；59种入出场/双源转场传递锚点及ROI足迹，连续转场保留完整密度，生成黑白幕不伪造来源；独立空间入出场可共享变速。',
      '.zh-TW':'實際來源像素/效果alpha和5類遮罩已接入跟蹤；59種進出場/雙來源轉場傳遞錨點及ROI足跡，連續轉場保留完整密度，生成黑白幕不偽造來源；獨立空間進出場可共享變速。',
      '.en':'Tracking reads actual source pixel/effect alpha and five mask shapes. All 59 edge/paired transitions transport point and ROI footprints, retaining full density between operations; generated mattes carry no source contribution. Independent spatial edges survive shared-output retime.'}
    validation={
      '':'C41：45次跟踪求值对照独立整数滑动参考，全部36帧Float32及解码画面对照无绑定参考工程，完整144000双声道采样、包往返、队列分别核验。实际GPU投影/合成及清理留证。仅受控素材/静态抽帧，未验收自然遮挡、身份、连续播放或人工听感；38项原关闭条件保留。',
      '.zh-TW':'C41：45次跟蹤求值對照獨立整數滑動參考，全部36幀Float32及解碼畫面對照無綁定參考工程，完整144000雙聲道採樣、包往返、佇列分別核驗。實際GPU投影/合成及清理留證。僅受控素材/靜態抽幀，未驗收自然遮擋、身分、連續播放或人工聽感；38項原關閉條件保留。',
      '.en':'C41 checks 45 binding evaluations against an independent integer-slide oracle, all 36 Float32 and decoded frames against an unbound reference project, complete 144,000 stereo samples, package roundtrip and queue separately. Actual GPU projection/composition and cleanup are recorded. Controlled media and static inspection do not accept natural occlusion/identity, continuous playback or human listening. All 38 original goal closure conditions remain.'}
    entries={
      '':['Installed native CLI0.1.31/local.29:224 product files/schema match source; one Skill,17 modules,73 files,4 existing model packs. Separate frozen installed groups: '+', '.join(k+'='+str(v) for k,v in counts.items())+'.',
          'C41 actual registered Skill:45 binding rows/36 Float32+decoded frames against independent slide and unbound-transform oracle;144000 complete stereo samples unchanged; package roundtrip passed.',
          'Independent queue reproduces36 complete decoded frames and144000 stereo samples; author graph/assets/settings/rights retained; actual GPU worker/shared handles closed.',
          'Fresh r32 kit:111 files, one registration/17 modules/73 Skill files; actual isolated CLI and inverse C40 retime dry-run, current visibility protocol checked; no source fallback/inference.',
          'Current complete trilingual READMEs/manuals/capability JSON/Skill/media and staged-byte audit;217 historical R rows and38 original closure cells retained;60 functions/20 services/75 actual declarations.',
          'Development failures retained separately:old scalar-only alpha assertion,Fraction progress validation,slide direction/oracle precision,missing probe/edge guard and invalid first C41 request. Final thresholds and goal boundaries remain explicit.'],
      '.zh-TW':['已安裝原生CLI0.1.31/local.29，224個產品檔案/schema與原始碼一致；唯一Skill/17模組/73檔案/4個既有模型包。分組實測：'+', '.join(k+'='+str(v) for k,v in counts.items())+'。',
          'C41實際註冊Skill：45次綁定求值/36幀Float32及解碼畫面對照獨立滑動和無綁定參考；完整144000雙聲道採樣不變；工程包往返通過。',
          '獨立佇列重現36完整解碼幀和144000雙聲道採樣；作者圖/資產/設定/權利保留；實際GPU worker/shared handles已關閉。',
          '新r32獨立kit111檔案，唯一註冊/17模組/73 Skill檔案；獨立CLI、C40反向變速dry-run和新可見度協定已核驗，無原始碼回退/推理。',
          '完整三語README/手冊/能力JSON/Skill/媒體及暫存位元組審核；保留217歷史R列與38原關閉條件；60功能/20服務/75實際宣告。',
          '開發失敗獨立保留：舊標量alpha斷言、Fraction進度、滑動方向/參考精度、缺少probe/獨立邊緣門禁及第一份無效C41請求。最終門檻與目標邊界明確保留。'],
      '.en':['Native CLI0.1.31/local.29 installed:224 product files/schema equal source; one Skill/17 modules/73 files/four existing model packs. Separate frozen installed groups: '+', '.join(k+'='+str(v) for k,v in counts.items())+'.',
          'Actual registered C41:45 binding evaluations and36 Float32/decoded frames match independent slide and unbound-transform oracles; full144000 stereo samples unchanged; native package roundtrip passed.',
          'Independent queue reproduces all36 decoded frames and144000 stereo samples; authored graph/assets/settings/rights retained; actual GPU worker/shared handles closed.',
          'Fresh isolated r32 kit111 files:one registration/17 modules/73 Skill files; real isolated CLI,current visibility protocol and inverse C40 retime dry-run checked; no source fallback/inference.',
          'Complete trilingual READMEs/manuals/capability JSON/Skill/media and staged-byte audit; all217 historical R rows and38 original closure cells retained;60 functions/20 services/75 actual declarations.',
          'Failed development runs retained separately:old scalar-only alpha assertion,Fraction progress admission,slide direction/finite-difference precision,missing probe/edge guard and invalid first C41 authoring request. Final gates and goal scope remain explicit.']}
    targets=['tracking-installed-r1/verification.json','case-r2/verification.json','queue-r1/verification.json',
        'kit-r1/verification.json','final-delivery-r1/verification.json','development-attempts-r1/verification.json']
    for suffix,name in LANG:
        text=(ROOT/name).read_text('utf-8-sig');old=rows(text);assert len(old)==217
        text=text.replace('**CLI0.1.30 / alpha.4-local.28 / r31 kit','**Historical / 历史 / 歷史：CLI0.1.30 / alpha.4-local.28 / r31 kit',1)
        block=('<!-- tracking-visibility-current -->\n\n**CLI0.1.31 / alpha.4-local.29 / r32 kit · 1 Skill / 17 modules.**\n\n'+desc[suffix]+'\n\n'
            '[Workflow](docs/product/TRACKING_VISIBILITY.md) · [C41](docs/product/CASES.md#c41-tracking-visibility) · [Install](docs/releases/CLI_0.1.31_LOCAL.md) · [Evidence](docs/validation/跟踪实际可见度实测_2026-10-26.md)\n\n'
            '![Actual registered Skill / silent GIF](docs/assets/tracking-visibility-20261026-r2/edited.gif)\n\n'+validation[suffix]+'\n\n<!-- /tracking-visibility-current -->\n\n')
        text=text.replace('<!-- tracking-retime-current -->',block+'<!-- tracking-retime-current -->',1)
        f14={'':'| F14 | 变速、倒放与定格 | 共享完整作者时钟、逐层输出和单次声音；原生独立空间入出场可保留。 | `timeline edit; render` | 跨片段转场仍需完整上级；ripple/retime、锁、预算和音频后端边界保留。 |',
             '.zh-TW':'| F14 | 變速、倒放與定格 | 共享完整作者時鐘、逐層輸出和單次聲音；原生獨立空間進出場可保留。 | `timeline edit; render` | 跨片段轉場仍需完整上級；ripple/retime、鎖、預算和音訊後端邊界保留。 |',
             '.en':'| F14 | Speed, reverse and freeze | Shared complete author clock, selected layers and single sound instance; independent native spatial edges retained. | `timeline edit; render` | Paired endpoints require the complete parent; ripple/retime, lock, budget and audio-backend limits remain. |'}
        f60={'':'| F60 | 原生跟踪与后续编辑 | 实际alpha/5类遮罩、59转场锚点与ROI足迹；共享变速、磁性分片、物理源编辑保留观察。 | `media track-bind; timeline compose/edit; preview; render; package` | 来源贡献在更高轨道遮挡前；丢失足迹隐藏；自然身份/遮挡质量与中间格式烘焙待补。 |',
             '.zh-TW':'| F60 | 原生跟蹤與後續編輯 | 實際alpha/5類遮罩、59轉場錨點與ROI足跡；共享變速、磁性分片、實體來源編輯保留觀察。 | `media track-bind; timeline compose/edit; preview; render; package` | 來源貢獻在更高軌道遮擋前；丟失足跡隱藏；自然身分/遮擋品質與中間格式烘焙待補。 |',
             '.en':'| F60 | Native tracking and continued editing | Actual alpha/five masks,59 transition point/ROI footprints; shared retime, magnetic partitions and physical source edits retain observations. | `media track-bind; timeline compose/edit; preview; render; package` | Source contribution precedes higher-track occlusion; lost footprints hide; natural identity/occlusion quality and interchange baking remain open. |'}
        for number,line in [(14,f14[suffix]),(60,f60[suffix])]:text=re.sub(r'^\| F'+str(number)+r'\s*\|.*$',lambda _:line,text,count=1,flags=re.M)
        text='\n'.join(line.replace('local.28/final-r1/installed','local.29/final-r1/installed').replace('0.1.30','0.1.31')
            if not line.startswith('| R') and 'local.28/final-r1/installed' in line else line for line in text.splitlines())+'\n'
        last=re.search(r'^\| R217\s*\|.*$',text,re.M);assert last
        additions=['| R'+str(218+i)+' | 2026-10-26 native tracking visibility | '+description+' | [Evidence](docs/validation/evidence/tracking-visibility-20261026-r1/'+target+') |' for i,(description,target) in enumerate(zip(entries[suffix],targets))]
        text=text[:last.end()]+'\n'+'\n'.join(additions)+text[last.end():]
        assert len(rows(text))==223 and all(rows(text)[k]==v for k,v in old.items());write(name,text)
        for path in ('docs/product/SKILLS'+suffix+'.md','docs/skills/UNIFIED_SKILL'+suffix+'.md'):
            link='TRACKING_VISIBILITY.md' if '/product/' in path else '../product/TRACKING_VISIBILITY.md'
            current='<!-- community-current -->\n\n**CLI0.1.31 / alpha.4-local.29 / r32 kit · 1 Skill / 17 modules / 73 files.**\n\n'+desc[suffix]+'\n\n[Tracking visibility workflow]('+link+')\n\n<!-- /community-current -->'
            write(path,re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:current,(ROOT/path).read_text('utf8'),count=1,flags=re.S))
    text='# 跟踪实际可见度实测 · 2026-10-26\n\nCLI0.1.31/local.29/r32；原生Windows、唯一统一Skill、17模块。\n\n| Scope | Actual evidence |\n|---|---|\n'
    scopes=[('Offline224 product files','installation-final-r1/verification.json'),('One Skill/four existing packs','activation-final-r1/activation-and-registration.json')]
    scopes += [(name+' '+str(count),name+'-installed-r1/verification.json') for name,count in counts.items()]
    scopes += [('Actual C41','case-r2/verification.json'),('45 independent point/PTS rows','case-r2/independent-footprint-oracles.json'),('All36 independent Float32 frames','case-r2/native-float-frame-oracles.json'),('Actual GPU cleanup','case-r2/gpu-receipt.json'),('Queue complete frames/PCM','queue-r1/verification.json'),('Static inspection','media-inspection-r1/verification.json'),('Fresh kit','kit-r1/verification.json'),('Final audit','final-delivery-r1/verification.json'),('Staged-byte directory',''),('Failed development attempts','development-attempts-r1/verification.json')]
    text+=''.join('| '+label+' | [Evidence](evidence/tracking-visibility-20261026-r1/'+target+') |\n' for label,target in scopes)
    text+='\n'+validation['']+'\n\n原始自制CC0 C36几何视频/标记与合成声音。独立参考从原生PTS观察插值、真实无绑定源alpha、显式整数滑动采样得到普通transform关键帧，未调用来源足迹计算器。全部45行最大误差'+str(case['max_binding_error'])+'；全部36帧Float32完全相等，全部解码帧完全相等；完整144000双声道PCM未变。包往返和独立队列另测。\n\n'
    text+='来源追溯覆盖5类遮罩、羽化/反转、真实像素alpha、59模式两分支、生成幕、连续采样、真实句柄/左极限、ROI丢失、循环、取消/预算、入出场变速。旧链式alpha断言已改为独立双线性边缘计算；finite-difference参考使用更大二进制精确扰动以降低Float32相减误差，逐帧完全相等门槛未放宽。失败source-r1/r2/r4及case-r1保留，未计入最终安装版125项。\n\n'
    text+='无新增模型推理/虚拟化/源码回退；静态抽帧，不代表连续播放/人工听审/自然遮挡或身份质量。足迹CPU，实际投影与合成GPU。全部38原关闭条件继续开放。\n\n[Workflow](../product/TRACKING_VISIBILITY.md) · [C41](../product/CASES.md#c41-tracking-visibility) · [Install](../releases/CLI_0.1.31_LOCAL.md).\n'
    write('docs/validation/跟踪实际可见度实测_2026-10-26.md',text)
    release='# CLI0.1.31 · actual tracking visibility · local.29\n\n本地离线构建并加载唯一 `$agent-ffmpeg-local-editor`。公开alpha.3/CLI0.1.2原标签与附件保持。\n\n| Item | Verified value |\n|---|---|\n'
    for key,value in [('Runtime','v0.1.0-alpha.4-local.29/final-r1/installed'),('Local ZIP',install['archive']),('ZIP bytes',str(install['archive_bytes'])),('ZIP SHA256',install['archive_sha256']),('Manifest SHA256',install['manifest_sha256']),('CLI/wheel','0.1.31'),('Product','224 Python files/schema equal source'),('Skill','1 entry/17 modules/73 files;r32 kit111 files')]:release+='| '+key+' | `'+value+'` |\n'
    release+='\n'+desc['']+'\n\n'+validation['']+'\n\n[Setup](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Commands](../product/TRACKING_VISIBILITY.md) · [Evidence](../validation/跟踪实际可见度实测_2026-10-26.md) · [C41](../product/CASES.md#c41-tracking-visibility) · [r32 kit](../skills/agent-editor-kit-community-unified-skill-r32.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.31-r32.json).\n'
    write('docs/releases/CLI_0.1.31_LOCAL.md',release)
    case_text=('\n<a id="c41-tracking-visibility"></a>\n\n## C41 · 跟踪遮罩与空间转场 · CLI0.1.31\n\n'+validation['']+'\n\n'
        '![Actual silent GIF](../assets/tracking-visibility-20261026-r2/edited.gif)\n\n[Before MP4](../assets/tracking-visibility-20261026-r2/before.mp4) · [Edited MP4](../assets/tracking-visibility-20261026-r2/edited.mp4) · [Editable package](../assets/tracking-visibility-20261026-r2/editable-tracking-visibility.aevpkg.zip) · [Source/rights](../assets/tracking-visibility-20261026-r2/SOURCE.txt) · [Hashes](../assets/tracking-visibility-20261026-r2/media-manifest.json) · [Workflow](TRACKING_VISIBILITY.md).\n')
    write('docs/product/CASES.md',(ROOT/'docs/product/CASES.md').read_text('utf8')+case_text)
    write('docs/product/TRACKING_VISIBILITY.md',(ROOT/'docs/product/TRACKING_VISIBILITY.md').read_text('utf8')+case_text)
    path='docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=(ROOT/path).read_text('utf8')
    old=load(ROOT/'docs/validation/evidence/tracking-retime-20261026-r1/installation-final-r1/verification.json')
    for before,after in [('local.28','local.29'),('CLI 0.1.30','CLI 0.1.31'),('r31.zip','r32.zip'),('0.1.30-r31.json','0.1.31-r32.json'),(old['archive_sha256'],install['archive_sha256']),(old['manifest_sha256'],install['manifest_sha256'])]:text=text.replace(before,after)
    write(path,text+'\nCLI0.1.31/local.29/r32：[实际跟踪可见度](TRACKING_VISIBILITY.md) · [verified local delivery](../releases/CLI_0.1.31_LOCAL.md). 前版本[CLI0.1.30](../releases/CLI_0.1.30_LOCAL.md)保留。\n')
    path='docs/README.md';text=(ROOT/path).read_text('utf8').replace('Current local / 当前本地 / 目前本地：**CLI0.1.30 / local.28 / r31 kit**','Historical / 历史 / 歷史：**CLI0.1.30 / local.28 / r31 kit**',1)
    write(path,text.replace('\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.31 / local.29 / r32 kit** · [Visibility](product/TRACKING_VISIBILITY.md) · [Install](releases/CLI_0.1.31_LOCAL.md) · [C41](product/CASES.md#c41-tracking-visibility).\n',1))
    for path in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        text=(ROOT/path).read_text('utf8').replace('当前本地 **CLI0.1.30 / alpha.4-local.28 / r31 kit**','此前本地 **CLI0.1.30 / alpha.4-local.28 / r31 kit**',1);first=text.index('\n')+1
        text=text[:first]+'\n当前本地 **CLI0.1.31 / alpha.4-local.29 / r32 kit**：[跟踪实际遮罩/alpha及59转场足迹](TRACKING_VISIBILITY.md)已实装，独立空间入出场可共享变速；[全帧/完整PCM实测](../validation/跟踪实际可见度实测_2026-10-26.md)。来源贡献不等于自然遮挡/身份；全部38原关闭条件保持。\n'+text[first:]
        text=text.replace('local.28-final-r1/CLI0.1.30/r31','local.29-final-r1/CLI0.1.31/r32');write(path,text)
    print(json.dumps(dict(status='documented',historical_rows_preserved=217,current_rows=223,counts=counts),ensure_ascii=False))

if __name__=='__main__':main()
