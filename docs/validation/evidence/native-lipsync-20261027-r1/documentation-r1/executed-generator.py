"""Maintain complete trilingual product/Skill docs and preserve every historical row."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def after(s,p,entry):
    m=list(re.finditer(r'^\| '+p+r'\d+\s*\|.*$',s,re.M))[-1];return s[:m.end()]+'\n'+entry+s[m.end():]

def main():
    out=BASE/'documentation-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r1/verification.json');test=load(BASE/'installed-lipsync-r1/verification.json');compat=load(BASE/'source-service-compat-r1/verification.json');case=load(BASE/'case-r1/verification.json')
    assert install['source_file_count']==248 and install['cli_version']=='0.1.41' and test['tests']==28
    for t in (test,compat):assert t['status']=='passed' and t['failures']==t['errors']==t['skipped']==0 and t['frozen_equal'] and t['test_frozen_equal']
    assert case['status']=='passed' and all(c['ok'] for c in case['checks'])
    moving=load(BASE/'video-and-cancel-r1/verification.json')
    assert moving['status']=='passed' and moving['moving_frames']==30 and moving['real_cancel_after_neural_frames'] and all(c['ok'] for c in moving['checks'])
    n=case['frames'];pcm=case['selected_PCM_scalars'];nt=compat['tests']
    capture='docs/product/lip-sync-capabilities-cli-0.1.41.json';(ROOT/capture).write_bytes((BASE/'installation-final-r1/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==80
    desc={
        '':'新增**真实本地 CUDA 神经口型同步**：使用 MuseTalk 1.5、Whisper-tiny、VAE 和 BiSeNet，让指定图片／视频随独立语音生成口型。支持25FPS人脸框关键帧、完整PCM保留、可重跑配方，以及分别可编辑的视频／音频关联片段。',
        '.zh-TW':'新增**真正本機 CUDA 神經口型同步**：使用 MuseTalk 1.5、Whisper-tiny、VAE 及 BiSeNet，讓指定圖片／影片隨獨立語音生成口型。支援25FPS人臉框關鍵影格、完整PCM保留、可重跑配方，以及分別可編輯的影片／音訊關聯片段。',
        '.en':'Adds **actual local CUDA neural lip sync**: MuseTalk1.5, Whisper-tiny, VAE and BiSeNet drive a supplied portrait/video from separate speech. Explicit25FPS face-box keys, complete selected PCM, rerunnable recipes and independent linked video/audio clips remain editable.'}
    limits={
        '':f'本批 **28项安装版检查通过，零失败／错误／跳过**；另{nt}项既有服务源码兼容回归通过，源码与安装版248文件一致。C51实际生成{n}帧，原始{pcm}个PCM标量、全部alpha及区域外RGB保留，完整音画在工程包迁移后相同。既有993项HDR整轮记录保留为历史结果。脸部模型256×256；完整身体／表演、自动跟踪、自然口型／听审、HDR推理及完整目标仍需建设。',
        '.zh-TW':f'本批 **28項安裝版檢查通過，零失敗／錯誤／跳過**；另{nt}項既有服務原始碼相容回歸通過，原始碼與安裝版248檔案一致。C51實際生成{n}影格，原始{pcm}個PCM標量、全部alpha及區域外RGB保留，完整音畫在工程包遷移後相同。既有993項HDR整輪紀錄保留為歷史結果。臉部模型256×256；完整身體／表演、自動跟蹤、自然口型／聽審、HDR推理及完整目標仍須建設。',
        '.en':f'This batch passes **28 installed checks with zero failures/errors/skips**, plus{nt} source regressions for existing services; all248 source/installed files match. Actual C51 retains{n} frames, all{pcm} original PCM scalars, all alpha and outside-region RGB; full rendered audio/video match after package import. Earlier993-test HDR results remain historical. The256×256 face model does not close full-body performance, automatic tracking, natural lip/listening quality, HDR inference or the complete goal.'}
    feature={
        '':'| F67 | 本地神经口型同步 | 图片／视频＋独立声音→真实CUDA MuseTalk口型；25FPS人脸框关键帧、语义下半脸混合、完整PCM及alpha保留，可复用配方并视频/音频关联入轨。 | `lipsync adapter register/list/inspect; lipsync generate` | 本地safetensors及已有原生Torch依赖；脸部256×256、明确8bit SDR与源运镜、无CPU回退；自然口型、完整数字人仍未验收。 |',
        '.zh-TW':'| F67 | 本機神經口型同步 | 圖片／影片＋獨立聲音→真正CUDA MuseTalk口型；25FPS人臉框關鍵影格、語義下半臉混合、完整PCM及alpha保留，可復用配方並影片/音訊關聯入軌。 | `lipsync adapter register/list/inspect; lipsync generate` | 本機safetensors及既有原生Torch依賴；臉部256×256、明確8bit SDR與來源運鏡、無CPU回退；自然口型、完整數位人仍未驗收。 |',
        '.en':'| F67 | Local neural lip sync | Image/video + separate speech → actual CUDA MuseTalk mouth;25FPS box keys, semantic lower-face blend, complete PCM/alpha, rerunnable recipe and linked editable video/audio clips. | `lipsync adapter register/list/inspect; lipsync generate` | Explicit local safetensors/native Torch runtime;256×256 face,8bit SDR/source motion,no CPU fallback; natural quality/full digital human remain open. |'}
    service={
        '':'| S22 | MuseTalk CUDA 神经口型服务 | 本地Whisper-tiny音频特征、MuseTalk1.5 UNet、SD VAE与BiSeNet；固定safetensors与拒写锁、原生任务回收。 | 显式已有Torch/Diffusers/Transformers/OpenCV原生依赖及模型证据；无自动安装。 | `lipsync adapter; lipsync generate` | 模型256×256，25FPS；授权、自然度、完整数字人及HDR另行验收。 |',
        '.zh-TW':'| S22 | MuseTalk CUDA 神經口型服務 | 本機Whisper-tiny音訊特徵、MuseTalk1.5 UNet、SD VAE及BiSeNet；固定safetensors與拒寫鎖、原生工作回收。 | 明確既有Torch/Diffusers/Transformers/OpenCV原生依賴及模型證據；無自動安裝。 | `lipsync adapter; lipsync generate` | 模型256×256，25FPS；授權、自然度、完整數位人及HDR另行驗收。 |',
        '.en':'| S22 | MuseTalk CUDA neural mouth service | Local Whisper-tiny, MuseTalk1.5 UNet, SD VAE and BiSeNet; fixed safetensors, deny-write locks and owned native cleanup. | Explicit existing native Torch/Diffusers/Transformers/OpenCV and model evidence; no automatic install. | `lipsync adapter; lipsync generate` | 256×256 face/25FPS; rights,naturalness,full digital human and HDR acceptance remain separate. |'}
    tests={
        '':['CLI0.1.41/local.39离线构建与安装：248文件逐字节相同，80项能力；28项安装版检查全过，零失败/错误/跳过。',
            '28项源码检查：部分管道读取、蒙版/区域外/alpha0隐藏RGB、44.1k精确样本、配方摘要/迁移、真实FFmpeg、取消/超时、错误诊断和事务回滚。',
            f'{nt}项既有抠像/分割/修复/生成/片段库/schema源码兼容检查全过；不与此前993项历史安装回归合并为本轮总数。',
            '实际CUDA模型探针通过；首轮旧VAE参数名失败保留，修复使用严格显式映射。权重固定来源/哈希，weights_only转safetensors并逐张量回读。',
            f'C51真实注册安装版Skill：{n}帧、全部{pcm}个原始PCM标量/alpha/区域外RGB保留；关联可编辑入轨，工程包完整画面/声音重放相同，带合成人物/声音的MP4/GIF与来源。',
            'r42单入口工具包：1 Skill/17模块/80 Skill文件/128ZIP项；完整哈希、独立注册及安装入口核验；三语F67/S22及全部277既有R记录和38原关闭条件保留。'],
        '.zh-TW':['CLI0.1.41/local.39離線建置及安裝：248檔案逐位元組相同，80項能力；28項安裝版檢查全過，零失敗/錯誤/跳過。',
            '28項原始碼檢查：部分管道讀取、蒙版/區域外/alpha0隱藏RGB、44.1k精確樣本、配方摘要/遷移、真正FFmpeg、取消/逾時、錯誤診斷及交易回滾。',
            f'{nt}項既有去背/分割/修復/生成/片段庫/schema原始碼相容檢查全過；不與此前993項歷史安裝回歸合併為本輪總數。',
            '實際CUDA模型探針通過；首輪舊VAE參數名稱失敗保留，修正使用嚴格明確映射。權重固定來源/雜湊，weights_only轉safetensors並逐張量回讀。',
            f'C51真正註冊安裝版Skill：{n}影格、全部{pcm}個原始PCM標量/alpha/區域外RGB保留；關聯可編輯入軌，工程包完整畫面/聲音重播相同，附合成人物/聲音的MP4/GIF及來源。',
            'r42單入口工具包：1 Skill/17模組/80 Skill檔案/128ZIP項；完整雜湊、獨立註冊及安裝入口核驗；三語F67/S22及全部277既有R紀錄和38原關閉條件保留。'],
        '.en':['CLI0.1.41/local.39 offline build/install:248 byte-identical source/installed files,80 capabilities;28 installed checks pass with zero failures/errors/skips.',
            '28 source tests cover partial pipes,semantic/box/alpha0 protection,44.1k sample clocks,recipe digests/rebinding,real FFmpeg,cancel/deadline,diagnostics and transaction rollback.',
            f'{nt} existing matting/segmentation/inpainting/generation/fragments/schema source compatibility tests pass. Earlier993 installed HDR tests remain a separate historical run.',
            'Actual CUDA model probe passes; first legacy-VAE key failure retained and corrected with strict explicit mapping. Pinned weights use weights_only conversion to safetensors and exact tensor reload.',
            f'Registered installed Skill C51:actual{n} frames,all{pcm} original PCM scalars,alpha and outside-region RGB preserved;linked editable tracks and complete package-render audio/video equality;synthetic portrait/speech MP4/GIF and provenance.',
            'r42:one Skill/17 modules/80 Skill files/128 ZIP entries;full hashes,isolated registration and installed entry checks. Trilingual F67/S22 retain all277 earlier R rows and38 original closure cells.']}
    targets=['installed-lipsync-r1/verification.json','source-lipsync-r3/verification.json','source-service-compat-r1/verification.json','model-probe-r2/verification.json','case-r1/verification.json','kit-r1/verification.json']
    for suffix in ('','.zh-TW','.en'):
        name='README'+suffix+'.md';s=read(name);old=rows(s,'R');assert len(old)==277
        block='<!-- native-lip-sync-current -->\n\n**CLI0.1.41 / alpha.4-local.39 / r42 kit · 1 Skill / 17 modules.**\n\n'+desc[suffix]+'\n\n'
        block+='[Workflow / usage](docs/product/LIP_SYNC.md) · [C51](docs/product/CASES.md#c51-native-lip-sync) · [Install](docs/releases/CLI_0.1.41_LOCAL.md) · [Evidence](docs/validation/本地神经口型实测_2026-10-27.md)\n\n'
        extra={'':'另有30帧移动视频/人脸框实测；实际模型输出后取消任务，三个子进程回收、工程回滚和诊断均通过。',
               '.zh-TW':'另有30影格移動影片/人臉框實測；真正模型輸出後取消工作，三個子程序回收、工程回滾及診斷均通過。',
               '.en':'A separate30-frame moving-video/box case passes; cancellation after actual neural frames reclaims all three children, rolls back metadata and retains diagnostics.'}
        block+='![Actual local neural lip sync / synthetic portrait and voice](docs/assets/native-lipsync-20261027-r1/comparison.gif)\n\n'+limits[suffix]+'\n\n'+extra[suffix]+' [Evidence](docs/validation/evidence/native-lipsync-20261027-r1/video-and-cancel-r1/verification.json).\n\n<!-- /native-lip-sync-current -->\n\n'
        assert '<!-- hdr-display-current -->' in s;s=s.replace('<!-- hdr-display-current -->',block+'<!-- hdr-display-history -->',1).replace('<!-- /hdr-display-current -->','<!-- /hdr-display-history -->',1)
        s=after(after(s,'F',feature[suffix]),'S',service[suffix]);s=after(s,'R','\n'.join('| R'+str(278+i)+' | 2026-10-27 native lip sync | '+d+' | [Evidence](docs/validation/evidence/native-lipsync-20261027-r1/'+p+') |' for i,(d,p) in enumerate(zip(tests[suffix],targets))))
        s='\n'.join(l.replace('local.38/final-r1/installed','local.39/final-r1/installed').replace('CLI 0.1.40','CLI 0.1.41') if 'local.38/final-r1/installed' in l and not l.startswith('| R') else l for l in s.splitlines())+'\n'
        s=s.replace('[r41 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r41.zip)','[r42 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r42.zip)')
        for old_heading,new_heading in [('完整的 63 个功能模块','完整的 67 个功能模块'),('完整的 63 個功能模組','完整的 67 個功能模組'),('All 63 functional modules','All 67 functional modules'),('46 个效果算子','51 个效果算子'),('46 個效果算子','51 個效果算子'),('46 effect operators','51 effect operators')]:s=s.replace('## '+old_heading,'## '+new_heading)
        assert len(rows(s,'F'))==67 and len(rows(s,'S'))==22 and len(rows(s,'K'))==17 and len(rows(s,'R'))==283
        assert all(rows(s,'R')[k]==v for k,v in old.items());write(name,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            path=base+suffix+'.md';s=read(path);relative='LIP_SYNC.md' if '/product/' in path else '../product/LIP_SYNC.md'
            block='<!-- community-current -->\n\n**CLI0.1.41 / alpha.4-local.39 / r42 kit · 1 Skill / 17 modules / 80 files.**\n\n'+desc[suffix]+'\n\n[Neural lip-sync workflow and limits]('+relative+')\n\n<!-- /community-current -->'
            s,nsub=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert nsub==1
            if base.endswith('CAPABILITIES'):
                s=after(after(s,'F',feature[suffix]),'S',service[suffix])
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,nsub=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if nsub==0:assert key=='native_lip_sync';s+='\n'+section+'\n'
                s+='\n[CLI0.1.41 exact installed capability snapshot](lip-sync-capabilities-cli-0.1.41.json).\n'
            write(path,s)
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p);prior=load(ROOT/'docs/validation/evidence/native-hdr-20261027-r1/installation-final-r1/verification.json')
    for old,new in [('alpha.4-local.38','alpha.4-local.39'),('CLI 0.1.40','CLI 0.1.41'),('r41.zip','r42.zip'),('0.1.40-r41.json','0.1.41-r42.json'),(prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(old,new)
    s+='\nCLI0.1.41/local.39/r42: [local neural lip sync](LIP_SYNC.md), [C51](CASES.md#c51-native-lip-sync), [local installation](../releases/CLI_0.1.41_LOCAL.md). MuseTalk safetensors and the native CUDA model interpreter are separate explicit dependencies from the four existing community packs; registration does not install them.\n';write(p,s)
    p='docs/product/GOAL_GAPS_20261025.md';s=read(p);closure={m[1]:m[0].split('|')[5] for m in re.finditer(r'^\| (G\d+)\s*\|.*$',s,re.M)};assert len(closure)==38
    s=s.replace('\n\n','\n\n当前本地 **CLI0.1.41 / alpha.4-local.39 / r42 kit**：[G24真实CUDA口型](LIP_SYNC.md)已接通显式人脸框、独立语音、25FPS时钟、完整PCM/alpha、可重跑配方及关联可编辑双轨。实际模型、工程包与失败证据见[C51](CASES.md#c51-native-lip-sync)。完整身体/表演、自然口型/听审与所有38原关闭条件保持。\n\n',1)
    line=next(l for l in s.splitlines() if l.startswith('| G24 '));parts=line.split('|');parts[3]=' CLI0.1.41已实装MuseTalk1.5/Whisper/VAE/BiSeNet CUDA口型；图片/视频＋独立语音、人脸框关键帧、完整PCM/alpha和可编辑配方/双轨；[实际C51](CASES.md#c51-native-lip-sync)。 '
    parts[4]=' 完整数字人、身体/表情/人物驱动、多人物/遮挡/自然嘴形与感知同步、连续播放/听审、自动跟踪、HDR/多设备/广泛验收仍缺。 '
    s=s.replace(line,'|'.join(parts),1);assert closure=={m[1]:m[0].split('|')[5] for m in re.finditer(r'^\| (G\d+)\s*\|.*$',s,re.M)};write(p,s)
    report=dict(status='documentation-written-with-real-evidence',functional_modules=67,services=22,internal_modules=17,previous_R_rows_retained=277,new_R_rows=6,all_38_original_closure_cells_preserved=True)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
if __name__=='__main__':main()
