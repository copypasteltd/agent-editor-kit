"""Maintain full three-language manuals and append immutable numbered evidence."""
from pathlib import Path
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/procedural-particles-20261027-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d+) \|.*$',s,re.M)}
def after(s,prefix,entry):
    matches=list(re.finditer(r'^\| '+prefix+r'\d+ \|.*$',s,re.M));assert matches
    m=matches[-1];return s[:m.end()]+'\n'+entry+s[m.end():]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--install-run',default='r2');ap.add_argument('--case-run',default='r3');a=ap.parse_args()
    install=load(BASE/('installation-final-'+a.install_run)/'verification.json')
    case=load(BASE/('case-'+a.case_run)/'verification.json');assert case['status']=='passed'
    assert install['source_file_count']==233 and install['capability_count']==76
    current_caps=load(BASE/('installation-final-'+a.install_run)/'capabilities.stdout.json')
    assert len(current_caps['data']['capabilities'])==76
    write('docs/product/procedural-particles-capabilities-cli-0.1.35.json',json.dumps(current_caps,ensure_ascii=False,indent=2)+'\n')
    gallery=case['public'];manifest=load(ROOT/gallery/'media-manifest.json')
    descriptions={
        '':'新增可编辑程序化粒子：雪、彩纸、余烬、光斑、斜雨、星芒。源参数、seed和独立帧率直接保存在工程；原生Float32合成、真实OpenCL栅格化、普通关键帧/裁切/倒放、预览、队列及工程包/OTIO回读已接通。六宫格为已注册安装版Skill实际渲染，未使用模型或第三方影像。',
        '.zh-TW':'新增可編輯程序化粒子：雪、彩紙、餘燼、光斑、斜雨、星芒。來源參數、seed和獨立幀率直接儲存在工程；原生Float32合成、實際OpenCL光柵化、一般關鍵幀/裁切/倒放、預覽、佇列及工程包/OTIO回讀已接通。六宮格由已註冊安裝版Skill實際渲染，未使用模型或第三方影像。',
        '.en':'Editable procedural snow, confetti, embers, bokeh, rain and sparkles now retain their parameters, seed and independent FPS in the project. Native Float32 composition, actual OpenCL rasterization, normal clip keys/cuts/reverse, preview, queues and package/OTIO reimport share the editable source. The six-cell scene is rendered through the registered installed Skill with no models or third-party footage.'}
    limits={
        '':'当前为二维诊断效果；没有三维碰撞、深度遮挡、流体或发射器参数关键帧。旧FFmpeg图会明确拒绝此源；完整剪映等价与全部38项原关闭条件继续保留。',
        '.zh-TW':'目前為二維診斷效果；沒有三維碰撞、深度遮擋、流體或發射器參數關鍵幀。舊FFmpeg圖明確拒絕此來源；完整剪映等價與全部38項原關閉條件持續保留。',
        '.en':'This is a 2-D diagnostic effect core. 3-D/collisions, depth occlusion, fluids and emitter-parameter keyframes remain open. The legacy FFmpeg graph explicitly rejects this source. Full CapCut parity and all 38 original closure conditions remain open.'}
    features={
        '':'| F63 | 可编辑程序化粒子 | 六种原创建效配方、五形状、seed/独立CFR/发射器；真实GPU分块栅格化与线性透明合成。支持普通剪辑、预览、队列、包及本地OTIO往返。 | `vfx list/inspect/apply/update/show` | 原生浮点管线；CPU负责hash/运动/分块；16发射器、4096活粒子、128Mi候选像素/帧；无3D/碰撞/深度。 |',
        '.zh-TW':'| F63 | 可編輯程序化粒子 | 六種原創配方、五形狀、seed/獨立CFR/發射器；實際GPU分塊光柵化與線性透明合成。支援一般剪輯、預覽、佇列、工程包及本地OTIO往返。 | `vfx list/inspect/apply/update/show` | 原生浮點管線；CPU負責hash/運動/分塊；16發射器、4096活粒子、128Mi候選像素/幀；無3D/碰撞/深度。 |',
        '.en':'| F63 | Editable procedural particles | Six original recipes, five shapes, seed, native CFR and emitters; actual GPU tile rasterization and linear transparency. Ordinary edits, preview, queues, packages and local OTIO roundtrips. | `vfx list/inspect/apply/update/show` | Native Float32 pipeline; CPU hash/motion/binning; 16 emitters, 4096 reserved live particles, 128Mi candidate visits/frame; no 3-D/collision/depth. |'}
    titles={'':'完整的 63 个功能模块','.zh-TW':'完整的 63 個功能模組','.en':'All 63 functional modules'}
    targets=['installation-final-'+a.install_run+'/verification.json','installed-particle-gpu-r3/verification.json',
        'case-'+a.case_run+'/verification.json','installed-integration-r2/verification.json','kit-r1/verification.json','development-attempts-r1/verification.json']
    checks={
        '':[
            'CLI0.1.35/local.33：233产品文件/Schema与新离线包一致；最终安装版粒子19、GPU1、集成5及旧流程192分别通过。原生回归427在首候选通过；最终文件读取/幂等修复及231文件字节对应另行核验。',
            '真实RTX/OpenCL：六配方18帧加五形状5帧共23次栅格化，预乘颜色/alpha与CPU独立后端对照；种子、随机访问、边角、透明度与资源准入均有独立数值测试。',
            'C45由实际注册Skill生成48帧/12FPS六宫格，288次粒子GPU调度；可编辑包迁移后所有解码帧一致。GIF额外加了编号/英文标签；原片、原始纯色背景和配方均保留。',
            '安装版真实编码/完整PCM、预览命中与seed失效、队列、分割及嵌套倒放、工程包/OTIO往返通过；OTIO背景色遗漏已修复。原生时钟与核验范围分开记。',
            '一个入口/17内部模块/76 Skill文件；r36 kit独立目录解包/登记、vfx查询/帮助和既有原生渲染计划实测；未切换真实发现目录，不含应用和模型大包。',
            '三语63功能/21服务/76能力、完整流程、C45媒体、安装摘要与Skill同步；241历史R列和38原关闭条件保留。参数文件读取失败及未接纳候选原样留证。'],
        '.zh-TW':[
            'CLI0.1.35/local.33：233產品檔案/Schema與新離線包一致；最終安裝版粒子19、GPU1、集成5及舊流程192分開通過。原生回歸427於首候選通過；最終檔案讀取/冪等修復及231檔案位元組對應另驗。',
            '實際RTX/OpenCL：六配方18幀加五形狀5幀共23次光柵化，預乘顏色/alpha與CPU獨立後端對照；seed、隨機存取、邊角、透明度與資源准入有獨立數值測試。',
            'C45由實際註冊Skill生成48幀/12FPS六宮格，288次粒子GPU調度；可編輯工程包遷移後所有解碼幀相同。GIF額外加了編號/英文標籤；原片、純色背景和配方保留。',
            '安裝版實際編碼/完整PCM、預覽命中與seed失效、佇列、分割及巢狀倒放、工程包/OTIO往返通過；OTIO背景色遺漏已修復。原生時鐘與核驗範圍分開記。',
            '一個入口/17內部模組/76 Skill檔案；r36 kit於獨立目錄解包/註冊，vfx查詢/說明與既有原生渲染計畫實測；未切換實際發現目錄，不含應用和模型大包。',
            '三語63功能/21服務/76能力、完整流程、C45媒體、安裝雜湊與Skill同步；241歷史R列和38原關閉條件保留。參數檔案讀取失敗和未接納候選原樣留證。'],
        '.en':[
            'CLI0.1.35/local.33: 233 product files and schema match the new offline bundle; final installed particle/GPU/integration/legacy groups pass 19/1/5/192 separately. Native427 passed on candidate1; the final JSON-reader/idempotency repair and231 unchanged files are checked explicitly.',
            'Actual RTX/OpenCL: 18 frames across six recipes plus five shapes, 23 raster dispatches compared in premultiplied light/alpha against the separate CPU backend. Independent numeric tests cover seed/seeking, corners, transparency and admission budgets.',
            'C45 registered Skill renders 48 frames at12FPS with288 GPU particle dispatches; all decoded frames equal after editable-package migration. GIF adds numbered English labels; actual MP4, solid input and recipes retained.',
            'Installed encoding/full PCM, preview hits/seed invalidation, queue, split/nested reverse and package/OTIO roundtrips pass. Missing OTIO background was repaired; clocks and verification scopes remain explicit.',
            'One entry,17 modules,76 Skill files; fresh-directory r36 kit extraction/registration, vfx discovery/help and existing native plans tested. Actual discovery retained; large application/model archives separate.',
            'Three languages,63 functions/21 services/76 capabilities, full workflow,C45 media/install hashes/Skill synchronized. All241 historical R rows and38 original closure cells retained; rejected JSON-reader candidates/failures preserved.']}
    code='''```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
$avkProject = 'E:/dev/sandbox/particle-demo'
& $avk project init $avkProject
& $avk vfx list
& $avk vfx inspect --name snow
& $avk vfx apply --project $avkProject --preset snow --seed 73 --clip-id snow --duration-tick 360000 --enable-native --dry-run
& $avk vfx apply --project $avkProject --preset snow --seed 73 --clip-id snow --duration-tick 360000 --enable-native
& $avk vfx show --project $avkProject --clip-id snow
```
'''
    for suffix in ('','.zh-TW','.en'):
        name='README'+suffix+'.md';s=read(name);old=rows(s,'R');assert len(old)==241
        block='<!-- procedural-particles-current -->\n\n**CLI0.1.35 / alpha.4-local.33 / r36 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n'+code+'\n'
        block+='[Workflow / parameters](docs/product/PROCEDURAL_PARTICLES.md) · [C45](docs/product/CASES.md#c45-procedural-particles) · [Install](docs/releases/CLI_0.1.35_LOCAL.md) · [Evidence](docs/validation/可编辑粒子实测_2026-10-27.md)\n\n'
        block+='![Actual registered Skill GPU output, annotated GIF]('+gallery+'/particle-grid.gif)\n\n'+limits[suffix]+'\n\n<!-- /procedural-particles-current -->\n\n'
        marker='<!-- model-session-current -->';assert marker in s
        s=s.replace(marker,block+'<!-- model-session-history -->',1).replace('<!-- /model-session-current -->','<!-- /model-session-history -->',1)
        s=after(s,'F',features[suffix]);s=after(s,'R','\n'.join('| R'+str(242+i)+' | 2026-10-27 editable particles | '+d+' | [Evidence](docs/validation/evidence/procedural-particles-20261027-r1/'+p+') |' for i,(d,p) in enumerate(zip(checks[suffix],targets))))
        s=re.sub(r'^## .*?62 (?:个功能模块|個功能模組|functional modules)$','## '+titles[suffix],s,count=1,flags=re.M)
        s='\n'.join(l.replace('local.32/final-r3/installed','local.33/final-'+a.install_run+'/installed').replace('CLI 0.1.34','CLI 0.1.35') if 'local.32/final-r3/installed' in l and not l.startswith('| R') else l for l in s.splitlines())+'\n'
        assert len(rows(s,'F'))==63 and len(rows(s,'S'))==21 and len(rows(s,'R'))==247
        assert all(rows(s,'R')[k]==v for k,v in old.items());write(name,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            path=base+suffix+'.md';s=read(path)
            relative='PROCEDURAL_PARTICLES.md' if '/product/' in path else '../product/PROCEDURAL_PARTICLES.md'
            block='<!-- community-current -->\n\n**CLI0.1.35 / alpha.4-local.33 / r36 kit · 1 Skill / 17 modules / 76 files.**\n\n'+descriptions[suffix]+'\n\n[Particle workflow and limits]('+relative+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            if base.endswith('CAPABILITIES'):
                assert len(rows(s,'F'))==62;s=after(s,'F',features[suffix]);assert len(rows(s,'F'))==63
                for key,value in current_caps['data']['capabilities'].items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    pattern=r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```'
                    s,count=re.subn(pattern,lambda _:section,s,count=1,flags=re.M|re.S)
                    if not count:s+='\n\n'+section+'\n'
                s+='\n[CLI0.1.35 exact installed capability snapshot](procedural-particles-capabilities-cli-0.1.35.json).\n'
            write(path,s)
    path='docs/product/CASES.md';s=read(path);assert 'id="c45-procedural-particles"' not in s
    case_calls=load(BASE/('case-'+a.case_run)/'calls.json')
    render_seconds={name:next(c['seconds'] for c in case_calls if c['id']==name) for name in ('render','render-restored')}
    prefix='../assets/'+Path(gallery).name+'/'
    s+='\n<a id="c45-procedural-particles"></a>\n\n## C45 · 可编辑GPU粒子 / Editable GPU particles\n\n'
    s+='Actual registered Skill, CLI0.1.35/local.33. Six-cell original diagnostic scene,48 frames/12FPS/4s;288 particle GPU dispatches. Seed/emitters/source FPS remain editable; all48 decoded RGB frames equal after project-package migration. No third-party media or model inference.\n\n'
    s+='![Before / original solid background]('+prefix+'before.png)\n\n![Actual output with labels]('+prefix+'contact.png)\n\n![Actual rendered output, annotated silent GIF]('+prefix+'particle-grid.gif)\n\n'
    s+='[Actual MP4]('+prefix+'particle-grid.mp4) · [Editable package]('+prefix+'editable-particle-grid.aevpkg.zip) · [Recipes]('+prefix+'recipes.json) · [Source/license]('+prefix+'SOURCE.txt) · [Media hashes]('+prefix+'media-manifest.json) · [Workflow](PROCEDURAL_PARTICLES.md) · [Evidence](../validation/可编辑粒子实测_2026-10-27.md).\n\n'
    s+='GIF/contact images decode the actual MP4 and add recipe numbers/English labels. GIF '+str(manifest['GIF_frames'])+' frames/'+str(manifest['GIF_duration_ms'])+'ms; authored MP4 is4s. Diagnostic static frame inspection, full-frame package comparison and silent audio decode are separate; no natural-footage/continuous-playback/human-listening acceptance.\n';write(path,s)
    s+='\nActual registered-launcher wall time: original GPU render '+str(round(render_seconds['render'],3))+'s; migrated render '+str(round(render_seconds['render-restored'],3))+'s. These include startup, IPC and encoding; no matched CPU timing was performed for C45, so no GPU speedup claim is made.\n';write(path,s)
    path='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(path)
    old=load(ROOT/'docs/validation/evidence/model-session-20261027-r1/installation-final-r3/verification.json')
    for left,right in [('local.32/final-r3/installed','local.33/final-'+a.install_run+'/installed'),('local.32/candidate-r3/bundle.zip','local.33/candidate-'+a.install_run+'/bundle.zip'),
        ('alpha.4-local.32','alpha.4-local.33'),('CLI 0.1.34','CLI 0.1.35'),('r35.zip','r36.zip'),('0.1.34-r35.json','0.1.35-r36.json'),
        (old['archive_sha256'],install['archive_sha256']),(old['manifest_sha256'],install['manifest_sha256']),
        (str(old['archive_bytes']),str(install['archive_bytes']))]:s=s.replace(left,right)
    s+='\nCLI0.1.35/local.33/r36 adds [editable procedural particles](PROCEDURAL_PARTICLES.md); see [C45](CASES.md#c45-procedural-particles) and [current installation hashes](../releases/CLI_0.1.35_LOCAL.md).\n';write(path,s)
    release='# CLI0.1.35 · editable GPU particles · alpha.4-local.33\n\nInstalled local development build; public alpha.3 / CLI0.1.2 is unchanged.\n\n'
    release+='Application ZIP: `'+Path(install['archive']).relative_to(ROOT).as_posix()+'`\n\nBytes: `'+str(install['archive_bytes'])+'` · SHA256: `'+install['archive_sha256']+'`\n\nManifest: `'+install['manifest_sha256']+'`\n\n'
    release+='Installed: `'+Path(install['installed']).relative_to(ROOT).as_posix()+'`\n\n233 Python product files match source, offline schema pinned,76 capability declarations. Single public Skill /17 internal modules /76 Skill files. r36 kit keeps application/model archives separate.\n\n'
    release+='[Full workflow and parameters](../product/PROCEDURAL_PARTICLES.md) · [Native installation](../product/COMMUNITY_LOCAL_DELIVERY.md) · [C45 actual media](../product/CASES.md#c45-procedural-particles) · [Verification](../validation/可编辑粒子实测_2026-10-27.md) · [r36 kit](../skills/agent-editor-kit-community-unified-skill-r36.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.35-r36.json).\n\n'
    release+='Final installed particle/GPU/integration/legacy groups are19/1/5/192, zero skips;23 particle CPU/GPU comparisons and actual48-frame/288-dispatch C45 package roundtrip. Native427 passed on candidate1;231 product files, including every pixel/GPU kernel, are byte-identical after the final JSON-reader/idempotency fix. These counts do not establish full CapCut parity. Legacy particle rendering, emitter keys,3-D/collisions/depth/fluids and natural-video quality remain open.\n';write('docs/releases/CLI_0.1.35_LOCAL.md',release)
    for path in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        s=read(path);first=s.index('\n')
        s=s[:first]+'\n\n当前本地 **CLI0.1.35 / alpha.4-local.33 / r36 kit**：[G06可编辑粒子](PROCEDURAL_PARTICLES.md)已接通原生CPU/GPU、普通编辑、预览/队列与包/本地OTIO；[真实安装版案例与边界](../validation/可编辑粒子实测_2026-10-27.md)。三维/碰撞/深度、复合效果包及全部38原关闭条件继续保留。\n'+s[first:]
        s=s.replace('当前本地 **CLI0.1.34','此前本地 **CLI0.1.34',1);write(path,s)
    path='docs/README.md';s=read(path).replace('Current local / 当前本地 / 目前本地：','Historical / 历史 / 歷史：',1);first=s.index('\n')
    s=s[:first]+'\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.35 / local.33 / r36 kit** · [Editable particles](product/PROCEDURAL_PARTICLES.md) · [Install](releases/CLI_0.1.35_LOCAL.md) · [C45](product/CASES.md#c45-procedural-particles).\n'+s[first:];write(path,s)
    # Correct the provisional gallery location after a retained failed candidate.
    for path in ('docs/product/PROCEDURAL_PARTICLES.md','skills/agent-ffmpeg-local-editor/references/procedural-particles.md'):
        s=read(path).replace('procedural-particles-20261027-r1/',Path(gallery).name+'/')
        if '/references/' in path:
            root='https://github.com/copypasteltd/agent-editor-kit/blob/main/'
            s+='\n[Actual contact sheet]('+root+gallery+'/contact.png) · [Actual annotated GIF]('+root+gallery+'/particle-grid.gif) · [Editable C45 workflow]('+root+'docs/product/PROCEDURAL_PARTICLES.md).\n'
        write(path,s)
    # Skill content changed only through reviewed references; refresh the exact inventory.
    path=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(path)
    m['files']=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted((ROOT/'skills/agent-ffmpeg-local-editor').rglob('*')) if p.is_file()]
    assert len(m['files'])==76;path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print('Updated full three-language READMEs/manuals, F63, R242–R247, C45 and exact Skill inventory; retained241 prior rows.')
if __name__=='__main__':main()
