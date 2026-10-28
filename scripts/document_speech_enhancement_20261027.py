"""Document the real installed CUDA enhancement batch without deleting history."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
def load(p):return json.loads(Path(p).read_bytes())
def read(p):return (ROOT/p).read_text('utf8')
def write(p,s):(ROOT/p).write_text(s,encoding='utf8',newline='\n')
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def after(s,p,block):
    matches=list(re.finditer(r'^\| '+p+r'\d+\s*\|.*$',s,re.M));assert matches;m=matches[-1];return s[:m.end()]+'\n'+block+s[m.end():]
def main():
    out=BASE/'documentation-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r3/verification.json');case=load(BASE/'case-complete-r1/verification.json');extra=load(BASE/'quality-and-cancel-r4/verification.json')
    for v in (case,extra):assert v['status']=='passed' and all(c['ok'] for c in v['checks'])
    for p,n in [('source-enhancement-r6',33),('installed-enhancement-r3',33),('installed-compat-r3',156)]:
        v=load(BASE/p/'verification.json');assert v['status']=='passed' and v['tests']==n and v['failures']==v['errors']==v['skipped']==0
    assert install['source_file_count']==266 and install['capability_count']==82
    capture='docs/product/speech-enhancement-capabilities-cli-0.1.43.json';(ROOT/capture).write_bytes((BASE/'installation-final-r3/capabilities.stdout.json').read_bytes())
    caps=load(ROOT/capture)['data']['capabilities'];assert len(caps)==82
    q=case['quality'];en=q['english_seeded_noise']['enhanced'];zh=q['chinese_synthetic_seeded_noise']['enhanced']
    desc={'':'新增**真实本地 CUDA DeepFilterNet3 对白降噪**：原生采样时钟、单/双声道、独立增强资产与可编辑音轨、强度/衰减上限、分段重叠、配方重跑、工程包和取消回滚。',
          '.zh-TW':'新增**真正本機 CUDA DeepFilterNet3 對白降噪**：原生取樣時鐘、單/雙聲道、獨立增強資產與可編輯音軌、強度/衰減上限、分段重疊、配方重跑、工程包及取消回滾。',
          '.en':'Adds **actual native CUDA DeepFilterNet3 speech denoising** with native sample clocks, mono/stereo, separate enhanced assets and editable audio tracks, strength/attenuation controls, overlapping segments, portable rerun recipes, packages and owned cancellation.'}
    limits={'':f'33项源码、33项安装版专项和156项安装版兼容回归分别通过。C53英语真人录音从0 dB输入提升至SNR {en["SNR_dB"]:.2f} dB，中文合成人声提升至{zh["SNR_dB"]:.2f} dB；完整原生样本数与工程包PCM相同。保留干净对白损伤、混响控制和首轮临时文件竞态失败。未做人类听审；分段状态重置、前端CPU/神经图CUDA；完整去混响/音乐保真和38原目标关闭条件继续开发。',
        '.zh-TW':f'33項原始碼、33項安裝版專項及156項安裝版相容回歸分別通過。C53英語真人錄音由0 dB輸入提升至SNR {en["SNR_dB"]:.2f} dB，中文合成人聲提升至{zh["SNR_dB"]:.2f} dB；完整原生樣本數與工程包PCM相同。保留乾淨對白損傷、混響控制及首輪暫存檔競態失敗。未做人類聽審；分段狀態重置、前端CPU/神經圖CUDA；完整去混響/音樂保真及38原目標關閉條件持續開發。',
        '.en':f'33 source checks,33 installed checks and156 installed compatibility regressions pass separately. C53 real English human speech improves from0 dB input to SNR {en["SNR_dB"]:.2f} dB; synthetic Mandarin reaches{zh["SNR_dB"]:.2f} dB. Native samples and complete package-render PCM are preserved. Clean-speech damage,reverb controls and the initial atomic-temp-file race remain recorded. No human listening acceptance; per-segment state resets,CPU frontend/CUDA neural graph. Full dereverberation,music fidelity and all38 original closure conditions remain ongoing.'}
    features={'':'| F69 | CUDA对白降噪与增强 | 原生采样时钟/单双声道、真实模型、干湿强度/衰减、可编辑独立音轨、配方重跑/工程包、取消回滚。 | `audio enhancement-adapter; audio enhance` | DeepFilterNet3固定safetensors＋已有原生CUDA依赖；分段状态重置、CPU前端；不是完整去混响/音乐保真。 |',
        '.zh-TW':'| F69 | CUDA對白降噪與增強 | 原生取樣時鐘/單雙聲道、真正模型、乾濕強度/衰減、可編輯獨立音軌、配方重跑/工程包、取消回滾。 | `audio enhancement-adapter; audio enhance` | DeepFilterNet3固定safetensors＋既有原生CUDA依賴；分段狀態重置、CPU前端；完整去混響/音樂保真待完成。 |',
        '.en':'| F69 | CUDA speech denoising | Native sample clock/mono-stereo,actual model,dry/wet attenuation,editable audio,portable recipes/packages,owned cancel/rollback. | `audio enhancement-adapter; audio enhance` | Fixed DF3 safetensors/existing native CUDA;segment state resets,CPU frontend;full dereverb/music fidelity open. |'}
    services={'':'| S24 | DeepFilterNet3对白服务 | 固定133张量/48kHz全带宽模型；神经推理CUDA、NumPy前端CPU、FFmpeg重采样。 | 显式本地权重/原生Torch/safetensors及MIT OR Apache-2.0证据。 | `audio enhancement-adapter; audio enhance` | 8..96kHz、1/2声道、完整源≤1800秒/选区≤600秒；无自动下载/依赖安装/CPU回退。 |',
        '.zh-TW':'| S24 | DeepFilterNet3對白服務 | 固定133張量/48kHz全頻模型；神經推論CUDA、NumPy前端CPU、FFmpeg重取樣。 | 明確本機權重/原生Torch/safetensors及MIT OR Apache-2.0證據。 | `audio enhancement-adapter; audio enhance` | 8..96kHz、1/2聲道、完整來源≤1800秒/選區≤600秒；無自動下載/依賴安裝/CPU回退。 |',
        '.en':'| S24 | DeepFilterNet3 speech service | Fixed133-tensor48kHz full-band model;CUDA neural graph,NumPy CPU frontend,FFmpeg resampling. | Explicit local weights/native Torch/safetensors and MIT OR Apache-2.0 evidence. | `audio enhancement-adapter; audio enhance` | 8..96kHz,mono/stereo,source≤1800s/selection≤600s;no downloads,installs or CPU fallback. |'}
    descriptions={
      '':['CLI0.1.43/local.41修复版离线构建安装，266程序文件逐字节一致、82能力；原公开alpha.3保留。','33项源码专项：FFT原生尾部/独立声道/OLA/配方/Float32精确旁路/真实worker/取消超时、持久诊断及临时响应文件原子替换竞态。','33项安装版专项和156项安装版四轨/时钟/片段/schema/补帧回归分开记录，均零失败/错误/跳过；首轮安装和失败案例保留。','固定官方DeepFilterNet3 commit/双许可证/133张量；weights_only开发转换、safetensors逐张量相同；真实CUDA和独立官方Windows CPU参考差异保留。','C53真实英语/中文合成人声加噪输入、实际增强、干净/混响控制、全原生样本、配方重跑和完整工程包PCM相同；含声音对照/频谱/GIF。','首轮真实双声道触发临时文件竞态已修复；实际神经段完成后取消，owned进程回收、原元数据回滚、无半成品；真实片段导入重绑通过。','r44统一入口工具包：1 Skill/17模块/82 Skill文件/132 ZIP项；三语F69/S24，全部290既有R行和38原关闭条件保留。'],
      '.zh-TW':['CLI0.1.43/local.41修正版離線建置安裝，266程式檔逐位元組相同、82能力；原公開alpha.3保留。','33項原始碼專項：FFT原生尾部/獨立聲道/OLA/配方/Float32精確旁路/真正worker/取消逾時、持久診斷及暫存回應檔原子替換競態。','33項安裝版專項及156項安裝版四軌/時鐘/片段/schema/補幀回歸分開記錄，均零失敗/錯誤/跳過；首輪安裝及失敗案例保留。','固定官方DeepFilterNet3 commit/雙授權/133張量；weights_only開發轉換、safetensors逐張量相同；真正CUDA及獨立官方Windows CPU參考差異保留。','C53真人英語/中文合成人聲加噪輸入、真正增強、乾淨/混響控制、全部原生樣本、配方重跑及完整工程包PCM相同；附聲音對照/頻譜/GIF。','首輪真正雙聲道觸發暫存檔競態已修復；真正神經段完成後取消，owned程序回收、原中繼資料回滾、無半成品；真正片段匯入重綁通過。','r44統一入口工具包：1 Skill/17模組/82 Skill檔案/132 ZIP項；三語F69/S24，全部290既有R列及38原關閉條件保留。'],
      '.en':['CLI0.1.43/local.41 corrected native offline build/install:266 byte-identical product files,82 capabilities;published alpha.3 preserved.','33 source checks:FFT native tails,independent channels,OLA,recipes,bit-exact Float32 bypass,real worker,cancel/deadline,persistent rollback diagnostics and atomic receipt removal race.','33 installed checks and156 installed stem/clock/fragment/schema/interpolation regressions pass separately with no failures/errors/skips;initial builds and failed case retained.','Pinned official DF3 commit/dual licenses/133 tensors;weights_only development conversion and complete safetensors equality;actual CUDA and independent official native CPU differences retained.','C53 real English/synthetic Mandarin noisy inputs,actual outputs,clean/reverb controls,native samples,recipe rerun and complete package-render PCM equality;audible video/spectra/GIF.','The real stereo case exposed a fixed atomic-temp-file race. Cancel after actual neural output reclaims owned worker,rolls back metadata,leaves no partial asset;real fragment rebinding passes.','r44:one Skill/17 modules/82 Skill files/132 ZIP entries;trilingual F69/S24 retain all290 prior R rows and38 original closure cells.']}
    targets=['installation-final-r3/verification.json','source-enhancement-r6/verification.json','installed-compat-r3/verification.json','conversion.json','case-complete-r1/verification.json','quality-and-cancel-r4/verification.json','kit-r1/verification.json']
    for suffix in ('','.zh-TW','.en'):
        p='README'+suffix+'.md';s=read(p);old=rows(s,'R');assert len(old)==290
        block='<!-- native-speech-enhancement-current -->\n\n**CLI0.1.43 / alpha.4-local.41 / r44 kit · 1 Skill / 17 modules.**\n\n'+desc[suffix]+'\n\n[Workflow / usage](docs/product/SPEECH_ENHANCEMENT.md) · [C53](docs/product/CASES.md#c53-native-speech-enhancement) · [Install](docs/releases/CLI_0.1.43_LOCAL.md) · [Evidence](docs/validation/本地对白增强实测_2026-10-27.md)\n\n![Actual speech waveforms; silent GIF](docs/assets/native-speech-enhancement-20261027-r2/comparison.gif)\n\n[Listen: clean → noisy → actual enhanced](docs/assets/native-speech-enhancement-20261027-r2/audible-comparison.mp4) · [Original16k human source](docs/assets/native-speech-enhancement-20261027-r2/original-human-16k.flac) · [Enhanced WAV](docs/assets/native-speech-enhancement-20261027-r2/english-enhanced.wav) · [Scientific spectra](docs/assets/native-speech-enhancement-20261027-r2/spectra-and-waveforms.png)\n\n'+limits[suffix]+'\n\n<!-- /native-speech-enhancement-current -->\n\n'
        s=s.replace('<!-- native-interpolation-current -->',block+'<!-- native-interpolation-history -->',1).replace('<!-- /native-interpolation-current -->','<!-- /native-interpolation-history -->',1)
        s=after(after(s,'F',features[suffix]),'S',services[suffix]);s=after(s,'R','\n'.join('| R'+str(291+i)+' | 2026-10-27 speech enhancement | '+d+' | [Evidence](docs/validation/evidence/native-speech-enhancement-20261027-r1/'+target+') |' for i,(d,target) in enumerate(zip(descriptions[suffix],targets))))
        s='\n'.join(line.replace('local.40/final-r1/installed','local.41/final-r3/installed') if not line.startswith('| R') else line for line in s.splitlines())+'\n'
        s=s.replace('[r43 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r43.zip)','[r44 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r44.zip)')
        s=s.replace('完整的 68 个功能模块','完整的 69 个功能模块').replace('完整的 68 個功能模組','完整的 69 個功能模組').replace('All 68 functional modules','All 69 functional modules')
        s='\n'.join(line.replace('46','51') if line.startswith('| F20 ') else line for line in s.splitlines())+'\n'
        assert len(rows(s,'F'))==69 and len(rows(s,'S'))==24 and len(rows(s,'R'))==297 and all(rows(s,'R')[k]==v for k,v in old.items());write(p,s)
        for base in ('docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            p=base+suffix+'.md';s=read(p);relative='SPEECH_ENHANCEMENT.md' if '/product/' in p else '../product/SPEECH_ENHANCEMENT.md'
            block='<!-- community-current -->\n\n**CLI0.1.43 / alpha.4-local.41 / r44 kit · 1 Skill / 17 modules / 82 files.**\n\n'+desc[suffix]+'\n\n[Speech enhancement workflow]('+relative+')\n\n<!-- /community-current -->'
            s,n=re.subn(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:block,s,count=1,flags=re.S);assert n==1
            if base.endswith('CAPABILITIES'):
                s=after(after(s,'F',features[suffix]),'S',services[suffix]);s='\n'.join(line.replace('46','51') if line.startswith('| F20 ') else line for line in s.splitlines())+'\n'
                for key,value in caps.items():
                    section='### `'+key+'`\n\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```'
                    s,n=re.subn(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n.*?\n```',lambda _:section,s,count=1,flags=re.M|re.S)
                    if n==0:assert key=='native_speech_enhancement';s+='\n'+section+'\n'
                s+='\n[CLI0.1.43 exact installed capabilities](speech-enhancement-capabilities-cli-0.1.43.json).\n'
            write(p,s)
    p='docs/product/COMMUNITY_LOCAL_DELIVERY.md';s=read(p);prior=load(ROOT/'docs/validation/evidence/native-interpolation-20261027-r1/installation-final-r1/verification.json')
    for old,new in [('alpha.4-local.40','alpha.4-local.41'),('0.1.42','0.1.43'),('r43','r44'),(prior['archive_sha256'],install['archive_sha256']),(prior['manifest_sha256'],install['manifest_sha256'])]:s=s.replace(old,new)
    s=s.replace('local.41/final-r1/','local.41/final-r3/').replace('local.41/candidate-r1/','local.41/candidate-r3/')
    s+='\nCurrent CLI0.1.43 adds [actual native CUDA speech enhancement](SPEECH_ENHANCEMENT.md) and [C53](CASES.md#c53-native-speech-enhancement). The fixed DeepFilterNet3 weights, existing native CUDA interpreter and dual-license evidence are separate explicit resources; runtime installs/downloads nothing.\n';write(p,s)
    for p in ['docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md']:
        s=read(p);old=rows(s,'G');s=s.replace('\n\n','\n\n当前本地 **CLI0.1.43 / alpha.4-local.41 / r44 kit**：[G17真实CUDA对白降噪](SPEECH_ENHANCEMENT.md)已接通单/双声道原生样本时钟、完整PCM、分段OLA、可编辑独立音轨、配方/工程包、实际神经段后取消。[C53](CASES.md#c53-native-speech-enhancement)保留真人英语与中文合成人声、噪声/干净/混响控制及原子临时文件竞态修复。33源码/33安装专项及156安装兼容分列；完整去混响/音乐保真/听审和38原关闭条件继续建设。\n\n',1)
        if old:
            line=next(line for line in s.splitlines() if line.startswith('| G17 '));parts=line.split('|')
            parts[3]=' HDemucs四轨保留；CLI0.1.43真实DeepFilterNet3 CUDA对白降噪，原生采样/单双声道、可编辑音轨、配方/工程包、真实取消及[C53](CASES.md#c53-native-speech-enhancement)。 '
            parts[4]=' 受控噪声改善已测，干净对白有误差；混响控制不等于完整去混响。真实多噪声/音乐泄漏、自然可懂度、听审和各素材/模型权利完整验收仍缺。 '
            s=s.replace(line,'|'.join(parts),1);assert len(old)==38 and all(rows(s,'G')[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        write(p,s)
    p='docs/README.md';s=read(p);write(p,s.replace('\n\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.43 / local.41 / r44 kit** · [CUDA speech enhancement / 对白增强 / 對白增強](product/SPEECH_ENHANCEMENT.md) · [Install](releases/CLI_0.1.43_LOCAL.md) · [C53](product/CASES.md#c53-native-speech-enhancement).\n\n',1))
    release=f'''# CLI0.1.43 / alpha.4-local.41 — native CUDA speech enhancement

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

真实DeepFilterNet3 CUDA对白降噪、原生单/双声道与精确采样时钟、干湿控制、可编辑音轨、配方重跑、工程包、取消回滚。繁體：真正本機CUDA對白降噪及完整原生取樣。 English: native CUDA speech denoising with exact native samples and editable audio. Full dereverberation/music fidelity and full product parity remain ongoing.

This is a **local compiled installation**, separate from immutable public alpha.3/CLI0.1.2.

```text
E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.41/candidate-r3/bundle.zip
bytes: {install['archive_bytes']}
SHA-256: {install['archive_sha256']}
manifest SHA-256: {install['manifest_sha256'].removeprefix('sha256:')}
installed: E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.41/final-r3/installed
```

266 Python product files match frozen tested source;82 capabilities. r44kit has1public Skill/17internal modules/82Skill files/132ZIP entries. The installed Skill remains `$agent-ffmpeg-local-editor`, with no source fallback. Existing native Python/CUDA/Torch/safetensors and the fixed local model are explicitly registered; no virtualization or dependency installation.

Use [offline installation/activation](../product/COMMUNITY_LOCAL_DELIVERY.md), then [the complete speech workflow](../product/SPEECH_ENHANCEMENT.md): init, ingest real local media, register model/native Python/license, dry-run, generate a new enhanced asset, audition original/output, validate, render and export an editable package. `--apply --track-id` adds a separate audio clip; avoid playing original and enhanced tracks together unintentionally. `--recipe-asset-id` plus a new ID reuses immutable source/model/settings; strength can be changed.

33 source checks,33 installed checks and156 installed compatibility checks are separate. C53 real English input SNR0→{en['SNR_dB']:.2f}dB; synthetic Mandarin0→{zh['SNR_dB']:.2f}dB. Complete native samples,bit-exact bypass,package-render PCM,fragment rebinding and cancellation after actual neural output pass. Retained initial real-case failure exposed an atomic temporary-file race,now covered by regression. Clean-speech distortion,reverb controls,independent official CPU-reference differences and all earlier failures are disclosed. No human listening or broad natural/music quality acceptance is claimed.

[C53/audio/GIF/spectra](../product/CASES.md#c53-native-speech-enhancement) · [Actual evidence](../validation/本地对白增强实测_2026-10-27.md) · [Build/install](../validation/evidence/native-speech-enhancement-20261027-r1/installation-final-r3/verification.json)
''';write('docs/releases/CLI_0.1.43_LOCAL.md',release)
    media='../assets/native-speech-enhancement-20261027-r2/'
    p='docs/product/CASES.md';s=read(p);s+='\n<a id="c53-native-speech-enhancement"></a>\n\n## C53 · CUDA对白增强 / 對白增強 / Speech enhancement\n\n'
    s+=f'实际注册CLI0.1.43/统一Skill，RTX3060真实DeepFilterNet3/133张量。LibriSpeech CC-BY-4.0英语真人原始16kHz录音明确升采样48kHz；{case["english_result"]["generation"]["worker"]["range"]["samples"]}个原生样本，{case["English_model_calls"]}次模型forward。另有原始24kHz Kokoro中文合成人声转44.1kHz双声道，显式范围137..{case["chinese_result"]["generation"]["worker"]["range"]["end_sample"]}、{case["Chinese_model_calls"]}次batch forward，两个声道独立处理。这不是原生全频真人/真实双声道录制。\n\n'
    s+='| Controlled case | Input SNR dB | Enhanced SNR dB | Enhanced SI-SDR dB |\n|---|---:|---:|---:|\n'
    for name,v in q.items():s+=f'| {name} | {v["input"]["SNR_dB"]:.4f} | {v["enhanced"]["SNR_dB"]:.4f} | {v["enhanced"]["SI_SDR_dB"]:.4f} |\n'
    s+='\n干净对白的输入误差为0；该行极大的输入SNR仅为公式分母1e-30保护值，不是实测动态范围。已知干净源/固定噪声指标不替代听感；混响仅三个离散延时的控制，不证明完整去混响。Segment2s/overlap0.25，每段特征/GRU重置，神经CUDA/前端CPU。\n\n'
    s+='![Actual waveform preview; silent GIF]('+media+'comparison.gif)\n\n'
    links=[('Audible clean/noisy/enhanced','audible-comparison.mp4'),('Original human16k FLAC','original-human-16k.flac'),('Clean48k WAV','english-clean.wav'),('Noisy English input','english-noisy.wav'),('Actual English enhanced','english-enhanced.wav'),('Synthetic Mandarin clean','chinese-clean.wav'),('Mandarin noisy input','chinese-noisy.wav'),('Actual Mandarin enhanced selected range','chinese-enhanced.wav'),('Clean-speech control output','clean_control.wav'),('Reverb/noise input','english-reverb-noisy.wav'),('Reverb control output','reverb_control.wav'),('Scientific spectra/waveforms','spectra-and-waveforms.png'),('Editable package','editable-enhancement.aevpkg.zip'),('Rerun recipes','recipes.json'),('License/provenance','SOURCE.txt'),('Exact media hashes/probes','media-manifest.json')]
    s+=' · '.join('['+label+']('+media+name+')' for label,name in links)+'\n\nAll selected Float32 samples bypass bit-exactly at strength0. Complete source/output assets and immutable recipes survive package import; full rendered decoded PCM matches. Actual fragment import rebinds source/output IDs. Real cancellation after a completed neural segment terminates the owned worker,rolls back metadata,retains bounded diagnostics and leaves no half asset. No human listening/continuous playback or complete G17/product acceptance.\n\n[Workflow](SPEECH_ENHANCEMENT.md) · [Evidence](../validation/本地对白增强实测_2026-10-27.md)\n';write(p,s)
    report='''# 本地对白增强实测 / Native speech enhancement · 2026-10-27

CLI0.1.43/local.41/r44，原生Windows，无Docker/WSL/虚拟环境/依赖安装；一个公开Skill/17内部模块，源码回退禁用。

| 范围 | 实际结果及证据 |
|---|---|
| 编译安装 | 修复版266程序文件与源码逐字节一致、82能力。[安装](evidence/native-speech-enhancement-20261027-r1/installation-final-r3/verification.json) |
| 源码专项 | 33项，零失败/错误/跳过；包含FFT/OLA/原生时钟/声道/旁路/配方/实际worker/超时取消及原子临时文件竞态。[源码](evidence/native-speech-enhancement-20261027-r1/source-enhancement-r6/verification.json) |
| 安装专项 | 同33项在最终安装版独立执行。[安装](evidence/native-speech-enhancement-20261027-r1/installed-enhancement-r3/verification.json) |
| 安装兼容 | 156项四轨/原生音频时钟/片段/schema/补帧检查，不与历史次数合计。[兼容](evidence/native-speech-enhancement-20261027-r1/installed-compat-r3/verification.json) |
| 上游及权重 | 官方固定commit d375b2d8309e0935d165700c91da9de862a99c31、MIT OR Apache-2.0、133张量；weights_only开发转换、完整safetensors回读相同。[来源](evidence/native-speech-enhancement-20261027-r1/acquisition.json) · [转换](evidence/native-speech-enhancement-20261027-r1/conversion.json) |
| 独立参考 | 官方Windows Rust/Tract/ONNX CPU发布版：输出16bit且补偿后少1440尾样本；CUDA长度/精度/分段策略不同，探针不bit-exact，不冒称完全等价。[参考](evidence/native-speech-enhancement-20261027-r1/probe-r1/independent-reference.json) |
| C53真实模型 | 真人英语、中文合成人声，固定噪声与干净/混响控制；完整样本、CUDA计数、无CPU回退/网络、强度旁路和配方重跑，完整工程包渲染PCM相同。[案例](evidence/native-speech-enhancement-20261027-r1/case-complete-r1/verification.json) |
| 真实取消与片段 | 神经段完成后取消，owned worker退出、元数据回滚、无半成品；真实片段迁移ID重绑及校验。[取消](evidence/native-speech-enhancement-20261027-r1/quality-and-cancel-r4/verification.json) |
| 对照媒体 | 原始FLAC/原声/加噪/增强、带声音MP4/无声GIF/真实频谱及哈希。[媒体](evidence/native-speech-enhancement-20261027-r1/media-r1/verification.json) |
| 工具包 | r44，1Skill/17模块/82Skill文件/132ZIP项，独立安装入口检查。[kit](evidence/native-speech-enhancement-20261027-r1/kit-r1/verification.json) |

失败均保留：官方下载TLS重置后用官方GitHub API；首个参考CLI负参数传递错误；FFT测试误差容限/取消测试触发时间夹具修正；真实双声道首轮FileNotFoundError由原子响应临时文件消失引发，产品已修复并新增竞态回归。修复后案例的音频生成完成，只有视频渲染因缺少画面层被明确拒绝；独立续跑添加实际波形卡片并完成工程包/渲染核验，未重算或替换既有音频。片段首次选择音轨目标被既有视频容器API拒绝，改用正确目标后重绑通过。真实取消发现原validation诊断被事务删除，已接入持久诊断库并增补事务回滚回归；最终安装版重跑英语/中文与公开WAV逐字节相同，再实测取消及诊断读取。首轮成功测试针对旧冻结字节，不算修复版通过数。

源音频权利与模型/生成资产分开登记；真人样本来自OpenSLR LibriSpeech CC-BY-4.0、下载链接为官方Qwen2-Audio样例，明确原始16kHz。中文为既有Kokoro合成人声、24kHz升采样44.1kHz，非真人或真实立体声。噪声/离散混响为受控诊断，不是自然声学基准。干净对白有损伤；无人工听审/连续播放，完整去混响、自然音乐质量/可懂度及38原目标关闭条件继续开发。

[案例及逐项指标](../product/CASES.md#c53-native-speech-enhancement) · [完整使用流程和参数边界](../product/SPEECH_ENHANCEMENT.md)
''';write('docs/validation/本地对白增强实测_2026-10-27.md',report)
    result=dict(status='documentation-written-with-actual-evidence',functional_modules=69,services=24,internal_modules=17,prior_R_rows_retained=290,new_R_rows=7,all_38_goal_closure_cells_preserved=True)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
if __name__=='__main__':main()
