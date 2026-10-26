"""Document the actual installed native tracking release without rewriting history."""
from pathlib import Path
import hashlib,json,re,subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-tracking-20261026-r1'
BASELINE='8de33691417328a1d801312028697096e971d404'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def load(p):return json.loads(Path(p).read_bytes())
def write(p,text):Path(p).write_text(text,encoding='utf8',newline='\n')
def rows(text,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d{2,3})\s*\|.*$',text,re.M)}
def old(p):return subprocess.check_output([GIT,'show',BASELINE+':'+p],cwd=ROOT).decode('utf-8-sig')

def main():
    install=load(BASE/'installation-final-r2/verification.json');case=load(BASE/'case-r5/verification.json')
    package=load(BASE/'package-r1/verification.json')
    groups={g:load(BASE/(g+'-installed-r2/verification.json')) for g in ('tracking','bindings','float','effects','adjustments','audio','render','legacy','text','gpu')}
    assert install['source_file_count']==219 and case['status']==package['status']=='passed'
    assert all(p['status']=='passed' and not p['skipped'] and p['frozen_equal'] for p in groups.values())
    group_line=', '.join(g+'='+str(v['tests']) for g,v in groups.items())
    feature=[
      '原生 PTS 跟踪绑定已接入安装版：贴图/标签复用实际视频帧时钟及 crop/fit/TRS 坐标，支持倒放、变速、定格、嵌套和作者窗口；叠加序列保留声音。统一 Skill 实跑36帧/3秒案例，动画裁切与旋转下逐帧核对锚点和标记像素，取消恢复/队列完整画面时钟与PCM一致，可编辑包保留原始观测。',
      '原生 PTS 跟蹤綁定已接入安裝版：貼圖／標籤共用實際影片影格時鐘及 crop/fit/TRS 座標，支援倒放、變速、定格、巢狀及作者視窗；疊加序列保留聲音。統一 Skill 實跑36影格／3秒案例，動畫裁切及旋轉下逐影格核對錨點和標記像素，取消恢復／佇列完整畫面時鐘與PCM相同，可編輯套件保留原始觀測。',
      'Installed native-PTS tracking bindings now share the picture clock and actual crop/fit/TRS geometry across reversal, retiming, freeze, nesting and author windows. Overlay sequences retain audio. The registered Skill delivers a 3s/36-frame moving-marker case with independent anchor/pixel checks; resume/queue retain complete frame clocks and PCM, and editable packages preserve original observations.'
    ]
    limits=[
      '模板匹配的采样/置信度单独记录；坐标CPU，符合条件的投影/合成/文字用GPU。遮挡、mask/转场可见性、自然身份质量与原生绑定的MLT/OTIO烘焙仍有边界，完整目标继续开发。',
      '模板匹配的取樣／置信度分別記錄；座標CPU，符合條件的投影／合成／文字用GPU。遮擋、mask／轉場可見性、自然身份品質及原生綁定的MLT/OTIO烘焙仍有邊界，完整目標持續開發。',
      'Template sampling/confidence is reported separately. Coordinates use CPU; eligible projection/composition/text use GPU. Occlusion, mask/transition visibility, natural identity quality and native-binding MLT/OTIO baking retain explicit limits. The full goal remains active.'
    ]
    f59=[
      '| F59 | 原生PTS跟踪与叠加轨 | 保存源观测→按实际原生帧求跟随位置；共享crop/TRS、ROI缩放/相对旋转、透明度、窗口与嵌套声音。 | `media track-bind; preview; render; queue; package` | 显式Float32，原生PTS不烘焙显示键；预算/循环门禁；模板漂移与遮挡另审，中间格式烘焙未接通。 |',
      '| F59 | 原生PTS跟蹤及疊加軌 | 保存來源觀測→依實際原生影格求跟隨位置；共用crop/TRS、ROI縮放／相對旋轉、透明度、視窗及巢狀聲音。 | `media track-bind; preview; render; queue; package` | 明確Float32，原生PTS不烘焙顯示鍵；預算／循環門禁；模板漂移及遮擋另審，中間格式烘焙未接通。 |',
      '| F59 | Native PTS tracking and overlay tracks | Saved source observations → actual selected-frame anchors;shared crop/TRS,ROI scale/relative rotation,alpha,windows and nested audio. | `media track-bind; preview; render; queue; package` | Explicit Float32,no display-key bake,budget/cycle gates;template drift/occlusion require review;native interchange baking pending. |'
    ]
    details=[
      ['离线ZIP安装219产品文件/随包schema一致；CLI0.1.26/local.24-final-r2；统一Skill17模块73文件',
       '18项原生跟踪检查：真实像素、VFR/非零起点/大PTS、裁切TRS、变速/倒放/定格/窗口/嵌套、alpha、绑定链/循环',
       '安装版各组分别通过且0skip：'+group_line+'；不合并历史次数',
       f"统一Skill36帧/3秒：真实模板分析36观测、父级倒放叠加轨；独立锚点误差≤{case['max_anchor_error_pixels']:.8g}px，标记质心≤{case['max_red_marker_centroid_error_pixels']:.8g}px；完整144000双声道PCM误差{case['max_pcm_error']:.8g}，恢复/队列相同",
       '实际项目包重导入，观测/引用摘要与字体许可保留；3帧RGBA64及12帧Float32范围/48000完整双声道采样相同',
       'r27独立kit实际解包/登记/计划/校验；唯一Skill17模块73文件，真实发现目录保持',
       '三语59功能/20服务/17模块/75实际声明；185历史核验行和38原关闭条件保留；最终交付字节/链接核验',
       '开发失败保留：首轮overlay schema漏接已修复；另两轮案例插值/图片起点声明错误及原生PTS参照公式已修正；早期71项测试0断言失败但代码变更破坏冻结，不计最终验收'],
      ['離線ZIP安裝219產品檔案／隨包schema相同；CLI0.1.26/local.24-final-r2；統一Skill17模組73檔案',
       '18項原生跟蹤檢查：實際像素、VFR／非零起點／大PTS、裁切TRS、變速／倒放／定格／視窗／巢狀、alpha、綁定鏈／循環',
       '安裝版各組分別通過且零略過：'+group_line+'；未合併歷史次數',
       f"統一Skill36影格／3秒：實際模板分析36觀測、父級倒放疊加軌；獨立錨點誤差≤{case['max_anchor_error_pixels']:.8g}px，標記質心≤{case['max_red_marker_centroid_error_pixels']:.8g}px；完整144000雙聲道PCM誤差{case['max_pcm_error']:.8g}，恢復／佇列相同",
       '實際專案包重新匯入，觀測／引用摘要與字型授權保留；3影格RGBA64及12影格Float32範圍／48000完整雙聲道取樣相同',
       'r27獨立kit實際解包／登記／計畫／校驗；唯一Skill17模組73檔案，實際發現目錄保持',
       '三語59功能／20服務／17模組／75實際宣告；185歷史核驗列及38原關閉條件保留；最終交付位元組／連結核驗',
       '開發失敗保留：首輪overlay schema漏接已修復；另兩輪案例插值／圖片起點宣告錯誤及原生PTS參照公式已修正；早期71項零斷言失敗但程式變動破壞凍結，不計最終驗收'],
      ['Offline ZIP installed,219 product files/packaged schema match;CLI0.1.26/local.24-final-r2;one Skill/17 modules/73 files',
       '18 native tracking checks:actual pixels,VFR/nonzero origin/large PTS,crop/TRS,retime/reverse/freeze/windows/nesting,alpha,chains/cycles',
       'Separate final installed groups,zero skips:'+group_line+';not combined with history',
       f"Registered Skill36frames/3s,actual template analysis36observations,reversed overlay;independent anchor error≤{case['max_anchor_error_pixels']:.8g}px,marker centroid≤{case['max_red_marker_centroid_error_pixels']:.8g}px;144000 complete stereo PCM samples error={case['max_pcm_error']:.8g};resume/queue equal",
       'Actual package reimport preserves observation/reference hash and font license;3 RGBA64 frames plus12 Float32 range frames/48000 full stereo samples equal',
       'r27 isolated kit unpack/register/plan/validate;one Skill/17 modules/73 files;actual discovery preserved',
       'Three languages59functions/20services/17modules/75actual declarations;185historical rows/38original closure conditions retained;final delivery byte/link checks',
       'Failed attempts retained:overlay schema gap fixed;fixture interpolation/image-origin declarations and native-PTS oracle corrected;early71tests had no assertion failure but lost source freeze during edits,excluded from final acceptance']
    ]
    targets=['installation-final-r2','tracking-installed-r2','effects-installed-r2','case-r5','package-r1','kit-r2','final-delivery-r2','development-attempts-r1']
    for i,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        text=(ROOT/name).read_text('utf-8-sig')
        text=text.replace('<!-- float-adjustments-current -->','<!-- float-adjustments-history -->').replace('<!-- /float-adjustments-current -->','<!-- /float-adjustments-history -->')
        text=text.replace('**CLI0.1.25 / alpha.4-local.23 / r26 kit','**Historical / 历史 / 歷史：CLI0.1.25 / alpha.4-local.23 / r26 kit')
        block='<!-- float-tracking-current -->\n\n**CLI0.1.26 / alpha.4-local.24 / r27 kit · 1 Skill / 17 modules.**\n\n'+feature[i]+'\n\n'
        block+='[Workflow](docs/product/FLOAT_TRACKING.md) · [C36](docs/product/CASES.md#c36-float-tracking) · [Local install](docs/releases/CLI_0.1.26_LOCAL.md) · [Evidence](docs/validation/原生PTS跟踪实测_2026-10-26.md)\n\n'
        block+='![Actual registered Skill / silent GIF](docs/assets/float-tracking-20261026-r5/native-tracking.gif)\n\n'+limits[i]+'\n\n<!-- /float-tracking-current -->\n\n'
        if '<!-- float-tracking-current -->' in text:text=re.sub(r'<!-- float-tracking-current -->.*?<!-- /float-tracking-current -->\n\n',lambda _:block,text,count=1,flags=re.S)
        else:text=text.replace('<!-- float-adjustments-history -->',block+'<!-- float-adjustments-history -->',1)
        if 'F59' not in rows(text,'F'):
            m=re.search(r'^\| F58\s*\|.*$',text,re.M);assert m;text=text[:m.end()]+'\n'+f59[i]+text[m.end():]
        for n,(detail,target) in enumerate(zip(details[i],targets),186):
            line=f'| R{n} | 2026-10-26 Native PTS tracking | {detail} | [Evidence](docs/validation/evidence/float-tracking-20261026-r1/{target}/verification.json) |'
            if 'R'+str(n) in rows(text,'R'):text=re.sub(r'^\| R'+str(n)+r'\s*\|.*$',lambda _:line,text,flags=re.M)
            else:
                m=re.search(r'^\| R'+str(n-1)+r'\s*\|.*$',text,re.M);assert m;text=text[:m.end()]+'\n'+line+text[m.end():]
        lines=[]
        for line in text.splitlines():
            if not line.startswith('| R'):
                if 'local.23/final-r1/installed' in line:line=line.replace('local.23/final-r1/installed','local.24/final-r2/installed').replace('0.1.25','0.1.26')
                if line.startswith('**') and 'unified-skill-r26.zip' in line:line=line.replace('r26','r27')
            lines.append(line)
        text='\n'.join(lines)+'\n';history=rows(old(name),'R');assert len(history)==185 and all(rows(text,'R')[k]==v for k,v in history.items())
        assert len(rows(text,'F'))==59 and len(rows(text,'R'))==193;write(ROOT/name,text)
    for prefix in ('docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
        for suffix in ('','.zh-TW','.en'):
            p=ROOT/(prefix+suffix+'.md');text=p.read_text('utf-8-sig')
            link='../product/FLOAT_TRACKING.md' if prefix.startswith('docs/skills') else 'FLOAT_TRACKING.md'
            current='<!-- community-current -->\n\n**CLI0.1.26 / alpha.4-local.24 / r27 kit · 1 Skill / 17 modules / 73 files.**\n\n'+feature[('','.zh-TW','.en').index(suffix)]+'\n\n[Native tracking workflow]('+link+')\n\n<!-- /community-current -->'
            text=re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:current,text,count=1,flags=re.S)
            write(p,text)
    guide=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=guide.read_text('utf-8-sig')
    previous=load(ROOT/'docs/validation/evidence/float-adjustments-20261026-r1/installation-final-r1/verification.json')
    for a,b in [('local.23','local.24'),('0.1.25','0.1.26'),('r26','r27'),('local.24/final-r1','local.24/final-r2'),('local.24/candidate-r1','local.24/candidate-r2'),
                ('218产品Python文件','219产品Python文件'),('72个Skill文件','73个Skill文件'),('72 Skill','73 Skill'),
                (previous['archive_sha256'],install['archive_sha256']),
                (previous['manifest_sha256'].removeprefix('sha256:'),install['manifest_sha256'].removeprefix('sha256:'))]:text=text.replace(a,b)
    text=text.replace('float-adjustments-capabilities-cli-0.1.26.json','float-tracking-capabilities-cli-0.1.26.json')
    text+='\n当前新增 [原生PTS跟踪绑定与叠加轨](FLOAT_TRACKING.md)：动态观测、实际视频时钟/几何、嵌套声音；219产品文件、73 Skill文件、1入口/17模块。\n'
    write(guide,text)
    cases=ROOT/'docs/product/CASES.md';text=cases.read_text('utf-8-sig')
    if 'id="c36-float-tracking"' not in text:
        text+='\n<a id="c36-float-tracking"></a>\n\n## C36 · Native PTS following marker through crop/TRS and reversed overlay audio\n\n'
        text+='CLI0.1.26/local.24-final-r2, registered unified Skill. Actual local template analysis produces36observations; animated crop/scale/rotation, following transparent marker, reversed nested overlay, GPU text and full stereo audio.36frames/3s/12fps/320×180. Original CC0 geometry/marker/tones; Noto Sans SC/OFL.\n\n'
        text+='![Actual silent GIF](../assets/float-tracking-20261026-r5/native-tracking.gif)\n\n'
        text+='[Source video](../assets/float-tracking-20261026-r5/original.native.mkv) · [Source audio](../assets/float-tracking-20261026-r5/original.audio.wav) · [Actual MP4](../assets/float-tracking-20261026-r5/native-tracking.mp4) · [Editable package](../assets/float-tracking-20261026-r5/editable-native-tracking.aevpkg.zip) · [Media hashes](../assets/float-tracking-20261026-r5/media-manifest.json) · [Workflow](FLOAT_TRACKING.md) · [Execution](../validation/evidence/float-tracking-20261026-r1/case-r5/verification.json) · [Reimport](../validation/evidence/float-tracking-20261026-r1/package-r1/verification.json).\n\n'
        text+=f"Every selected original source index matches. Independent anchor error≤{case['max_anchor_error_pixels']:.8g}px,actual red marker centroid error≤{case['max_red_marker_centroid_error_pixels']:.8g}px. Full144000 stereo PCM samples match the independent reversal oracle;resume/queue match all decoded frames/clocks/PCM. Package retains observations/license;3RGBA64frames and12Float32rangeframes/full48000stereoPCM match. No natural identity,occlusion,continuous playback,human listening or speed acceptance.\n"
    write(cases,text)
    path=ROOT/'docs/product/GOAL_GAPS_20261025.md';text=path.read_text('utf-8-sig');historical=rows(old(path.relative_to(ROOT).as_posix()),'G')
    lines=[]
    for line in text.splitlines():
        if line.startswith('| G12 '):
            fields=line.split('|');fields[3]+='；CLI0.1.26原生PTS绑定/动态crop-TRS/嵌套声音、真实统一Skill逐帧/PCM核验';line='|'.join(fields)
        if line.startswith('| G38 '):line=line.replace('local.23-final-r1/CLI0.1.25/r26','local.24-final-r2/CLI0.1.26/r27')
        lines.append(line)
    text='\n'.join(lines)+'\n';assert all(rows(text,'G')[k].split('|')[5]==v.split('|')[5] for k,v in historical.items());write(path,text)
    path=ROOT/'docs/product/IMPLEMENTATION_PLAN_20261025.md';text=path.read_text('utf-8-sig')
    text=text.replace('当前本地 **CLI0.1.24','此前本地 **CLI0.1.24').replace('当前CLI0.1.25/local.23-final-r1/r26本地安装并加载','当前CLI0.1.26/local.24-final-r2/r27本地安装并加载')
    line='当前本地 **CLI0.1.26 / alpha.4-local.24 / r27 kit**：[原生PTS跟踪绑定](FLOAT_TRACKING.md)、动态crop/TRS共享几何与叠加轨嵌套声音已接入；真实模板分析/逐帧锚点像素/完整PCM/恢复队列/包重导入留证。全部38原关闭条件保持。\n\n'
    text=text.replace('# 完整目标实施台账（2026-10-25 起）\n','# 完整目标实施台账（2026-10-25 起）\n\n'+line,1);write(path,text)
    write(ROOT/'docs/product/float-tracking-capabilities-cli-0.1.26.json',json.dumps(load(BASE/'installation-final-r2/capabilities.stdout.json'),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='documented',functions=59,services=20,readme_rows=193,historical_rows_preserved=185,goal_closures_preserved=38)))

if __name__=='__main__':main()
