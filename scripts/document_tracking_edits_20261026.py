"""Refresh the full three-language README without changing historical R/G rows."""
from pathlib import Path
import hashlib,json,re,subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-edits-20261026-r1'
BASELINE='a0254306b22f41f3e45a469f05c294b03b4e106b'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def load(p):return json.loads(Path(p).read_bytes())
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def rows(s,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',s,re.M)}
def old(p):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','show',BASELINE+':'+str(p)],cwd=ROOT).decode('utf8')

def main():
    install=load(BASE/'installation-final-r3/verification.json');case=load(BASE/'case-r3/verification.json')
    assert install['source_file_count']==220 and case['status']=='passed'
    features=[
        '带跟踪绑定的原生剪辑已接通：源与标签可分割、裁切、波纹插入/删除及范围编辑；自动重规划保留源分片，固定ROI缩放/旋转基准，源删除后跟随层隐藏，锁定引用冲突整体拒绝。统一Skill实跑C37：36帧剪为30帧，全部保留Float32像素/PTS/绑定坐标一致，完整120000双声道采样误差0，可编辑包重导入相同。',
        '帶跟蹤綁定的原生剪輯已接通：來源與標籤可分割、裁切、波紋插入／刪除及範圍編輯；自動重規劃保留來源分片，固定ROI縮放／旋轉基準，來源刪除後跟隨層隱藏，鎖定引用衝突整體拒絕。統一Skill實跑C37：36影格剪為30影格，全部保留Float32像素／PTS／綁定座標相同，完整120000雙聲道取樣誤差0，可編輯套件重新匯入相同。',
        'Native bound clips now support split/trim/ripple and range edits. The planner repairs retained source fragments, pins ROI/rotation references, hides followers after source removal and rejects locked-reference changes atomically. Registered-Skill C37 cuts 36 frames to 30: every retained Float32 pixel/native PTS/binding coordinate matches, all 120,000 stereo samples splice exactly, and editable-package reimport matches.'
    ]
    limits=[
        '核验编码明确采用8bit H.264 CRF0；本机10bit同参数并非逐像素无损，反例保留。源slip/真实外扩、容器变速、磁性裁切及中间格式原生烘焙继续有边界；完整目标仍在开发。',
        '核驗編碼明確採用8bit H.264 CRF0；本機10bit同參數並非逐像素無損，反例保留。來源slip／實際外擴、容器變速、磁性裁切及中介格式原生烘焙繼續有邊界；完整目標持續開發。',
        'The diagnostic uses explicit 8-bit H.264 CRF0; this machine’s 10-bit setting is not pixel-lossless and its counterexample is retained. Source slip/extension, container retiming, magnetic cut propagation and native interchange baking retain explicit limits. The full goal remains active.'
    ]
    f60=[
        '| F60 | 跟踪后的可编辑剪辑 | 分割/裁切/波纹与范围编辑→保留源分片引用、原始轨迹和ROI/旋转基准；删除源后隐藏标签。 | `timeline compose/edit; preview; render; package` | 显式原生Float32；128分片/绑定，锁定/循环/歧义门禁；源slip/真实外扩/磁性传播仍受限。[流程](docs/product/TRACKING_EDITS.md) |',
        '| F60 | 跟蹤後的可編輯剪輯 | 分割／裁切／波紋及範圍編輯→保留來源分片引用、原始軌跡及ROI／旋轉基準；刪除來源後隱藏標籤。 | `timeline compose/edit; preview; render; package` | 明確原生Float32；128分片／綁定，鎖定／循環／歧義門禁；來源slip／實際外擴／磁性傳播仍受限。[流程](docs/product/TRACKING_EDITS.md) |',
        '| F60 | Editable native tracking | Split/trim/ripple/range edits → retained source fragments, original observations and pinned ROI/rotation references; removed sources hide followers. | `timeline compose/edit; preview; render; package` | Explicit native Float32;128 fragments/binding,lock/cycle/ambiguity gates;source slip/extension/magnetic propagation retain limits.[Workflow](docs/product/TRACKING_EDITS.md) |'
    ]
    detail=[
        ['离线ZIP安装220产品文件/随包Schema一致；CLI0.1.27/local.25-final-r3，唯一Skill17模块73文件',
         '安装版分别33跟踪/195编辑/71绑定/192默认CLI预览队列Schema/46原生渲染/65音频/98浮点检查通过，全部0skip；不合并历史计数',
         'C37实际统一Skill：30保留帧的全部Float32像素/PTS/绑定坐标相同；8bit核验编码解码相同，完整120000双声道PCM误差0；包重导入/队列相同',
         'r28独立kit解包、单入口登记、实际CLI计划/校验；73Skill文件/17模块，包内文档与源一致',
         '三语60功能/20服务/17模块/75实际声明；193历史核验行与全部38关闭条件保持；源码/安装/kit/链接交付核验',
         '失败保留：首安装2个旧最小绑定读取异常已修复重建；首视频误把本机10bit CRF0当作无损，保留SPS/实际像素反例，最终8bit及全部Float32核验通过'],
        ['離線ZIP安裝220產品檔案／隨包Schema相同；CLI0.1.27/local.25-final-r3，唯一Skill17模組73檔案',
         '安裝版分別33跟蹤／195編輯／71綁定／192預設CLI預覽佇列Schema／46原生渲染／65音訊／98浮點檢查通過，全部零略過；未合併歷史計數',
         'C37實際統一Skill：30保留影格全部Float32像素／PTS／綁定座標相同；8bit核驗編碼解碼相同，完整120000雙聲道PCM誤差0；套件重新匯入／佇列相同',
         'r28獨立kit解包、單入口登記、實際CLI規劃／校驗；73Skill檔案／17模組，包內文件與來源相同',
         '三語60功能／20服務／17模組／75實際宣告；193歷史核驗列及全部38關閉條件保留；原始碼／安裝／kit／連結交付核驗',
         '失敗保留：首安裝2個舊最小綁定讀取異常已修復重建；首影片誤把本機10bit CRF0當作無損，保留SPS／實際像素反例，最終8bit及全部Float32核驗通過'],
        ['220 product files match the installed ZIP/schema;CLI0.1.27/local.25-final-r3;one Skill,17 modules,73 Skill files',
         'Installed groups pass separately with zero skips:33 tracking,195 editing,71 bindings,192 legacy CLI/preview/queue/schema,46 native render,65 audio,98 Float32;no historical-count sum',
         'Registered-Skill C37:all 30 retained Float32 pixel frames/native PTS/binding coordinates match;8-bit diagnostic decoded pixels and full120000 stereo PCM match;package/queue match',
         'Fresh r28 kit unpack/single-entry registration/actual CLI planning and validation;73 Skill files/17 modules;packaged docs match source',
         'Three languages preserve60 functions/20 services/17 modules/75 actual declarations;all193 historical R rows and38 original closure cells remain;source/install/kit/link delivery audit',
         'Failures retained:first install hit2 legacy minimal-binding read errors,now fixed/rebuilt;first case incorrectly assumed this machine’s10-bit CRF0 was lossless;SPS/pixel counterexample retained;explicit8-bit and complete Float32 checks pass']
    ]
    targets=['installation-final-r3','tracking-installed-r3','case-r3','kit-r1','final-delivery-r1','development-attempts-r1']
    for i,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        p=ROOT/name;text=p.read_text('utf-8-sig');assert '<!-- tracking-edits-current -->' not in text
        text=text.replace('float-tracking-current','float-tracking-history').replace('**CLI0.1.26 / alpha.4-local.24 / r27 kit','**Historical / 历史 / 歷史：CLI0.1.26 / alpha.4-local.24 / r27 kit')
        block='<!-- tracking-edits-current -->\n\n**CLI0.1.27 / alpha.4-local.25 / r28 kit · 1 Skill / 17 modules.**\n\n'+features[i]+'\n\n'
        block+='[Workflow](docs/product/TRACKING_EDITS.md) · [C37](docs/product/CASES.md#c37-tracking-edits) · [Local install](docs/releases/CLI_0.1.27_LOCAL.md) · [Evidence](docs/validation/跟踪剪辑实测_2026-10-26.md)\n\n'
        block+='![Actual registered Skill / silent GIF](docs/assets/tracking-edits-20261026-r3/edited.gif)\n\n'+limits[i]+'\n\n<!-- /tracking-edits-current -->\n\n'
        text=text.replace('<!-- float-tracking-history -->',block+'<!-- float-tracking-history -->',1)
        m=re.search(r'^\| F59\s*\|.*$',text,re.M);assert m;text=text[:m.end()]+'\n'+f60[i]+text[m.end():]
        for number,(message,target) in enumerate(zip(detail[i],targets),194):
            row=f'| R{number} | 2026-10-26 Native tracking edits | {message} | [Evidence](docs/validation/evidence/tracking-edits-20261026-r1/{target}/verification.json) |'
            m=re.search(r'^\| R'+str(number-1)+r'\s*\|.*$',text,re.M);assert m;text=text[:m.end()]+'\n'+row+text[m.end():]
        lines=[]
        for line in text.splitlines():
            if not line.startswith('| R') and 'local.24/final-r2/installed' in line:
                line=line.replace('local.24/final-r2/installed','local.25/final-r3/installed').replace('0.1.26','0.1.27')
            if line.startswith('**') and 'unified-skill-r27.zip' in line:line=line.replace('r27','r28')
            if line.startswith('[当前完整目标差距表]'):line=line.replace('CLI 0.1.23','CLI 0.1.27')
            lines.append(line)
        text='\n'.join(lines)+'\n';history=rows(old(name),'R');assert len(history)==193 and all(rows(text,'R')[k]==v for k,v in history.items())
        assert len(rows(text,'F'))==60 and len(rows(text,'R'))==199;write(p,text)
    for prefix in ('docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
        for i,suffix in enumerate(('','.zh-TW','.en')):
            p=ROOT/(prefix+suffix+'.md');text=p.read_text('utf-8-sig');link='../product/TRACKING_EDITS.md' if prefix.startswith('docs/skills') else 'TRACKING_EDITS.md'
            block='<!-- community-current -->\n\n**CLI0.1.27 / alpha.4-local.25 / r28 kit · 1 Skill / 17 modules / 73 files.**\n\n'+features[i]+'\n\n[Native tracking editing workflow]('+link+')\n\n<!-- /community-current -->'
            write(p,re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,text,count=1,flags=re.S))
    p=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=p.read_text('utf-8-sig')
    # Replace only current installation material; historical sections retain their claims.
    split=text.index('## CLI 0.1.5')
    current,history=text[:split],text[split:]
    previous=load(ROOT/'docs/validation/evidence/float-tracking-20261026-r1/installation-final-r2/verification.json')
    for a,b in [('local.24','local.25'),('0.1.26','0.1.27'),('r27','r28'),
        (previous['archive_sha256'],install['archive_sha256']),(previous['manifest_sha256'],install['manifest_sha256'])]:current=current.replace(a,b)
    current=current.replace('float-tracking-capabilities-cli-0.1.27.json','tracking-edits-capabilities-cli-0.1.27.json')
    history=history.replace('## CLI0.1.26 当前交付 / Current delivery','## CLI0.1.26 历史交付 / Historical delivery')
    text=current+history+'\n## CLI0.1.27 当前交付 / Current delivery\n\n220产品Python文件，73 Skill文件、17模块、r28 kit。[跟踪后的可编辑剪辑](TRACKING_EDITS.md)补齐保留源分片、基准时钟和删除隐藏；[完整安装与实测](../releases/CLI_0.1.27_LOCAL.md)。旧包、反例和38原关闭条件保留。\n'
    write(p,text)
    p=ROOT/'docs/product/CASES.md';text=p.read_text('utf-8-sig');assert 'id="c37-tracking-edits"' not in text
    text+='\n<a id="c37-tracking-edits"></a>\n\n## C37 · Split and ripple-edit native following markers and stereo audio\n\n'+features[2]+'\n\n'
    text+='![Actual silent GIF](../assets/tracking-edits-20261026-r3/edited.gif)\n\n[Workflow, input/output, commands and limits](TRACKING_EDITS.md) · [Before MP4](../assets/tracking-edits-20261026-r3/before.mp4) · [Edited MP4](../assets/tracking-edits-20261026-r3/edited.mp4) · [Editable package](../assets/tracking-edits-20261026-r3/editable-tracking-edits.aevpkg.zip).\n\n2.5s/30frames/12fps/320×180; explicit8bit diagnostic delivery, complete Float32 composition checked separately. Self-authored CC0 source/marker/tones, font license retained. No new model inference, natural quality, continuous playback or human listening acceptance.\n';write(p,text)
    for filename in ('GOAL_GAPS_20261025.md','IMPLEMENTATION_PLAN_20261025.md'):
        p=ROOT/'docs/product'/filename;text=p.read_text('utf-8-sig')
        text=text.replace('当前本地 **CLI0.1.24','此前本地 **CLI0.1.24').replace('当前本地 **CLI0.1.26','此前本地 **CLI0.1.26')
        first=text.index('\n');text=text[:first]+'\n\n当前本地 **CLI0.1.27 / alpha.4-local.25 / r28 kit**：[跟踪后的可编辑剪辑](TRACKING_EDITS.md)已实装并以真实统一Skill逐帧/完整PCM及工程包往返核验。全部38原关闭条件保持。\n'+text[first:]
        if filename.startswith('GOAL'):
            lines=[]
            for line in text.splitlines():
                if line.startswith('| G12 '):
                    fields=line.split('|');fields[3]+='；CLI0.1.27补源/目标分割裁切与波纹/范围编辑、基准持久化和源删除隐藏';line='|'.join(fields)
                if line.startswith('| G38 '):line=line.replace('local.24-final-r2/CLI0.1.26/r27','local.25-final-r3/CLI0.1.27/r28')
                lines.append(line)
            text='\n'.join(lines)+'\n';historical=rows(old('docs/product/'+filename),'G')
            assert len(historical)==38 and all(rows(text,'G')[k].split('|')[5]==v.split('|')[5] for k,v in historical.items())
        write(p,text)
    p=ROOT/'docs/README.md';text=p.read_text('utf-8-sig').replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：',1)
    first=text.index('\n');text=text[:first]+'\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.27 / local.25 / r28 kit** · [Tracking edits](product/TRACKING_EDITS.md) · [Installation](releases/CLI_0.1.27_LOCAL.md) · [C37](product/CASES.md#c37-tracking-edits).\n'+text[first:];write(p,text)
    write(ROOT/'docs/product/tracking-edits-capabilities-cli-0.1.27.json',json.dumps(load(BASE/'installation-final-r2/capabilities.stdout.json'),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='documented',functions=60,services=20,readme_rows=199,historical_rows_preserved=193,goal_closures_preserved=38)))

if __name__=='__main__':main()
