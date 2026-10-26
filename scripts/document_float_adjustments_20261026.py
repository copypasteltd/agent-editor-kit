"""Document verified installed grading without rewriting historical evidence."""
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-adjustments-20261026-r1'
BASELINE='e155947b0cbdb00ebbcbd0f198a22bfcdfda03f0'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def load(path):return json.loads(Path(path).read_bytes())
def write(path,text):Path(path).write_text(text,encoding='utf8',newline='\n')
def rows(text,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}
def before(path):return subprocess.check_output([GIT,'show',BASELINE+':'+path],cwd=ROOT).decode('utf-8-sig')

def main():
    install=load(BASE/'installation-final-r1/verification.json')
    case=load(BASE/'case-r1/verification.json');package=load(BASE/'package-r1/verification.json')
    groups={g:load(BASE/(g+'-installed-r1/verification.json')) for g in ('adjustments','effects','float','audio','render','legacy','text','gpu')}
    assert install['source_and_installed_equal'] and install['source_file_count']==218
    assert case['status']==package['status']=='passed' and case['registered_skill']
    assert all(v['status']=='passed' and v['skipped']==0 and v['frozen_equal'] for v in groups.values())
    features=[
      '全局和区间 Float32 调整层已进入安装版：LUT 与曝光、效果链顺序、六类关键帧插值、选中序列只应用一次。统一 Skill 实跑6秒/72帧工程，组合GPU字幕/投影、倒放子序列、转场及关联声音；取消恢复与队列全部帧时钟/完整PCM一致。项目包带LUT原字节，重导入的帧与范围预览一致。',
      '全域及區間 Float32 調整層已進入安裝版：LUT 與曝光、效果鏈順序、六類關鍵影格插值、選中序列僅套用一次。統一 Skill 實跑6秒／72影格專案，組合GPU字幕／投影、倒放子序列、轉場與關聯聲音；取消恢復及佇列全部影格時鐘／完整PCM相同。專案包含LUT原位元組，重新匯入的影格及範圍預覽相同。',
      'Installed global/interval Float32 adjustments now support ordered effect chains, LUT/exposure, six keyframe interpolations and one application at the selected sequence root. The registered Skill delivers a 6s/72-frame edit with GPU text/affine, reversed nested clips, transitions and linked audio. Resume/queue preserve every frame clock and complete PCM; package reimport preserves LUT bytes and frame/range previews.'
    ]
    limits=[
      '调整层为CPU Float32计算，可与已支持的GPU合成组合；本轮未新增模型推理或性能承诺。自然素材视听、HDR/ICC及完整目标继续验收。',
      '調整層為CPU Float32計算，可與已支援的GPU合成組合；本輪未新增模型推理或效能承諾。自然素材視聽、HDR／ICC及完整目標持續驗收。',
      'Adjustments use CPU Float32 and combine with supported GPU composition. No new model inference or performance claim. Natural-content quality, HDR/ICC and the full goal remain open.'
    ]
    f58=[
      '| F58 | Float32全局/区间调整层 | 全轨含字幕合成后按顺序调色；LUT/曝光及既有浮点效果、六类关键帧、选中根只应用一次。 | `settings.adjustments; preview; render; queue` | 显式线性工作域/效果信号；CPU执行；LUT持锁/包迁移；保留作者区间时钟，非完整HDR。 |',
      '| F58 | Float32全域／區間調整層 | 全軌含字幕合成後依序調色；LUT／曝光及既有浮點效果、六類關鍵影格、選中根僅套用一次。 | `settings.adjustments; preview; render; queue` | 明確線性工作域／效果訊號；CPU執行；LUT持鎖／封裝遷移；保留作者區間時鐘，非完整HDR。 |',
      '| F58 | Float32 global/interval adjustments | Ordered grading after all tracks including subtitles;existing float effects,LUT/exposure,six keyframe modes,selected root once. | `settings.adjustments; preview; render; queue` | Explicit linear working/effect signals;CPU execution;locked/portable LUTs;original interval clocks,not complete HDR. |'
    ]
    group_line=', '.join(g+'='+str(v['tests']) for g,v in groups.items())
    details=[
      ['离线ZIP安装、218产品文件逐字节一致；CLI0.1.25/local.23-final-r1；统一Skill/17模块/72文件',
       '14项调整层检查，含独立像素/时钟公式、实际10bit编码、完整原PCM、RGBA16帧预览、Windows LUT读锁与释放',
       '安装版各组分别通过且0skip：'+group_line+'；不合并历史计数',
       f"统一Skill6秒/72帧；全局LUT+曝光与区间动画共108次层应用；完整288000双声道采样误差{case['max_pcm_error']:.12g}；恢复/队列全帧和PCM相同",
       '可编辑包实际导入，LUT原字节/字体许可保留，3帧RGBA64与12帧Float32范围/48000双声道PCM完全相同',
       'r26独立kit解包/登记/计划/校验，真实发现目录保持；唯一Skill17模块72文件',
       '三语58功能/20服务/17模块/75声明；178历史核验行、38原关闭条件保持；最终交付字节与链接核验'],
      ['離線ZIP安裝、218產品檔案逐位元組相同；CLI0.1.25/local.23-final-r1；統一Skill／17模組／72檔案',
       '14項調整層檢查，含獨立像素／時鐘公式、實際10bit編碼、完整原PCM、RGBA16影格預覽、Windows LUT讀鎖及釋放',
       '安裝版各組分別通過且零略過：'+group_line+'；未合併歷史計數',
       f"統一Skill6秒／72影格；全域LUT+曝光及區間動畫共108次層套用；完整288000雙聲道取樣誤差{case['max_pcm_error']:.12g}；恢復／佇列全影格及PCM相同",
       '可編輯包實際匯入，LUT原位元組／字型授權保留，3影格RGBA64與12影格Float32範圍／48000雙聲道PCM完全相同',
       'r26獨立kit解包／登記／計畫／校驗，真實發現目錄保持；唯一Skill17模組72檔案',
       '三語58功能／20服務／17模組／75宣告；178歷史核驗列、38原關閉條件保持；最終交付位元組及連結核驗'],
      ['Offline ZIP installed,218 source files byte-match;CLI0.1.25/local.23-final-r1;one Skill/17 modules/72 files',
       '14 adjustment tests:independent pixel/clock oracles,actual 10bit encode,complete original PCM,RGBA16 frame preview,Windows LUT read-lock/release',
       'Separate installed groups,zero skips:'+group_line+';not combined with history',
       f"Registered Skill6s/72frames;global LUT/exposure plus animated interval,108 layer applications;288000 stereo sample oracle error={case['max_pcm_error']:.12g};resume/queue frames and full PCM equal",
       'Actual editable package import,LUT bytes/font license retained;3 RGBA64 frames and12 Float32 range frames/48000 stereo PCM samples exactly match',
       'r26 isolated kit extraction/registration/planning/validation;real discovery retained;one Skill/17 modules/72 files',
       'Three languages58functions/20services/17modules/75declarations;178 historical rows/38original closure conditions retained;final delivery bytes/links checked']
    ]
    targets=['installation-final-r1','adjustments-installed-r1','effects-installed-r1','case-r1','package-r1','kit-r2','final-delivery-r1']
    for i,name in enumerate(('README.md','README.zh-TW.md','README.en.md')):
        text=(ROOT/name).read_text('utf-8-sig')
        text=text.replace('<!-- float-gpu-current -->','<!-- float-gpu-history -->').replace('<!-- /float-gpu-current -->','<!-- /float-gpu-history -->')
        text=text.replace('**CLI0.1.24 / alpha.4-local.22 / r25 kit','**Historical / 历史 / 歷史：CLI0.1.24 / alpha.4-local.22 / r25 kit')
        block='<!-- float-adjustments-current -->\n\n**CLI0.1.25 / alpha.4-local.23 / r26 kit · 1 Skill / 17 modules.**\n\n'+features[i]+'\n\n'
        block+='[Workflow](docs/product/FLOAT_ADJUSTMENTS.md) · [C35](docs/product/CASES.md#c35-float-adjustments) · [Local install](docs/releases/CLI_0.1.25_LOCAL.md) · [Evidence](docs/validation/Float32调整层实测_2026-10-26.md)\n\n'
        block+='![Actual registered Skill edit / silent GIF](docs/assets/float-adjustments-20261026-r1/native-text.gif)\n\n'+limits[i]+'\n\n<!-- /float-adjustments-current -->\n\n'
        if '<!-- float-adjustments-current -->' in text:
            text=re.sub(r'<!-- float-adjustments-current -->.*?<!-- /float-adjustments-current -->\n\n',lambda _:block,text,count=1,flags=re.S)
        else:text=text.replace('<!-- float-gpu-history -->',block+'<!-- float-gpu-history -->',1)
        if 'F58' not in rows(text,'F'):
            m=re.search(r'^\| F57\s*\|.*$',text,re.M);assert m
            text=text[:m.end()]+'\n'+f58[i]+text[m.end():]
        for n,(detail,target) in enumerate(zip(details[i],targets),179):
            line=f'| R{n} | 2026-10-26 Float32 adjustments | {detail} | [Evidence](docs/validation/evidence/float-adjustments-20261026-r1/{target}/verification.json) |'
            if f'R{n}' in rows(text,'R'):text=re.sub(r'^\| R'+str(n)+r'\s*\|.*$',lambda _:line,text,flags=re.M)
            else:
                m=re.search(r'^\| R'+str(n-1)+r'\s*\|.*$',text,re.M);assert m
                text=text[:m.end()]+'\n'+line+text[m.end():]
        lines=[]
        for line in text.splitlines():
            if not line.startswith('| R'):
                if 'local.22/final-r4/installed' in line:line=line.replace('local.22/final-r4/installed','local.23/final-r1/installed').replace('0.1.24','0.1.25')
                if line.startswith('**') and 'unified-skill-r25.zip' in line:line=line.replace('r25','r26')
            lines.append(line)
        text='\n'.join(lines)+'\n';historical=rows(before(name),'R');assert len(historical)==178
        assert all(rows(text,'R')[k]==v for k,v in historical.items())
        assert len(rows(text,'F'))==58 and len(rows(text,'R'))==185
        write(ROOT/name,text)
    for prefix in ('docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
        for suffix in ('','.zh-TW','.en'):
            p=ROOT/(prefix+suffix+'.md');s=p.read_text('utf-8-sig')
            s=s.replace('0.1.24 / alpha.4-local.22 / r25 kit','0.1.25 / alpha.4-local.23 / r26 kit').replace('1 Skill / 17 modules / 71 files','1 Skill / 17 modules / 72 files').replace('float-gpu-capabilities-cli-0.1.24.json','float-adjustments-capabilities-cli-0.1.25.json')
            link='../product/FLOAT_ADJUSTMENTS.md' if prefix.startswith('docs/skills') else 'FLOAT_ADJUSTMENTS.md'
            note='\nCLI0.1.25: [global/interval Float32 grading]('+link+'); one selected root, authored clocks, explicit local LUT dependencies; CPU effects with compatible GPU composition. One Skill /17 modules /72 files.\n'
            if note not in s:s+=note
            write(p,s)
    guide=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=guide.read_text('utf-8-sig')
    old=load(ROOT/'docs/validation/evidence/float-gpu-20261026-r1/installation-final-r4/verification.json')
    for a,b in [('local.22','local.23'),('0.1.24','0.1.25'),('r25','r26'),('final-r4','final-r1'),('candidate-r4','candidate-r1'),
                ('217产品Python文件','218产品Python文件'),('71 Skill','72 Skill'),('71个Skill文件','72个Skill文件'),
                (old['archive_sha256'],install['archive_sha256']),
                (old['manifest_sha256'].removeprefix('sha256:'),install['manifest_sha256'].removeprefix('sha256:'))]:s=s.replace(a,b)
    s=s.replace('float-gpu-capabilities-cli-0.1.25.json','float-adjustments-capabilities-cli-0.1.25.json')
    note='\n当前新增 [Float32全局/区间调整层](FLOAT_ADJUSTMENTS.md)：按完整合成结果调色，选中根只应用一次，LUT依赖持锁并可移植；与已有GPU合成共存。\n'
    if note not in s:s+=note
    write(guide,s)
    cases=ROOT/'docs/product/CASES.md';s=cases.read_text('utf-8-sig')
    if 'id="c35-float-adjustments"' not in s:
        s+='\n<a id="c35-float-adjustments"></a>\n\n## C35 · Global/interval Float32 grading with the registered Skill\n\n'
        s+='CLI0.1.25/local.23-final-r1. Self-authored CC0 geometric footage, stereo tones, captions and linear LUT; Noto Sans SC/OFL font. Two adjustment layers run after GPU composition;108 layer applications over72frames/6s/12fps/320×180. Five source-handle transitions, reversed child and CJK/SRT/typewriter/word selection remain editable.\n\n'
        s+='![Actual silent GIF](../assets/float-adjustments-20261026-r1/native-text.gif)\n\n'
        s+='[Source video](../assets/float-adjustments-20261026-r1/original.native.mkv) · [Source audio](../assets/float-adjustments-20261026-r1/original.audio.wav) · [Actual MP4](../assets/float-adjustments-20261026-r1/native-text.mp4) · [Editable package](../assets/float-adjustments-20261026-r1/editable-native-text.aevpkg.zip) · [Media hashes](../assets/float-adjustments-20261026-r1/media-manifest.json) · [Workflow](FLOAT_ADJUSTMENTS.md) · [Execution](../validation/evidence/float-adjustments-20261026-r1/case-r1/verification.json) · [Reimport/range](../validation/evidence/float-adjustments-20261026-r1/package-r1/verification.json).\n\n'
        s+='All resumed/queued frames, clocks and complete PCM match. Reimport retains LUT bytes/font license;three RGBA64 frames and12 Float32 range frames/full48000stereo samples match exactly. Synthetic tones are numerical evidence;no human listening,continuous playback,natural-content quality or new GPU speed claim.\n'
    write(cases,s)
    p=ROOT/'docs/product/GOAL_GAPS_20261025.md';s=p.read_text('utf-8-sig');old=rows(before(p.relative_to(ROOT).as_posix()),'G')
    changed=[]
    for line in s.splitlines():
        if line.startswith('| G08 '):
            parts=line.split('|');parts[3]+='；CLI0.1.25现有全局/区间Float32调整、LUT持锁/迁移与真实编码/完整PCM核验';line='|'.join(parts)
        if line.startswith('| G38 '):line=line.replace('local.22-final-r4/CLI0.1.24/r25','local.23-final-r1/CLI0.1.25/r26')
        changed.append(line)
    s='\n'.join(changed)+'\n';new=rows(s,'G');assert len(new)==38
    assert all(new[k].split('|')[5]==v.split('|')[5] for k,v in old.items());write(p,s)
    p=ROOT/'docs/product/IMPLEMENTATION_PLAN_20261025.md';s=p.read_text('utf-8-sig')
    s=s.replace('当前CLI0.1.20/local.18-final-r2/r21本地安装并加载','当前CLI0.1.25/local.23-final-r1/r26本地安装并加载')
    write(p,s)
    raw=load(BASE/'installation-final-r1/capabilities.stdout.json')
    write(ROOT/'docs/product/float-adjustments-capabilities-cli-0.1.25.json',json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='documented',functions=58,readme_rows=185,historical_rows_preserved=178,goal_closures_preserved=38),ensure_ascii=False))

if __name__=='__main__':main()
