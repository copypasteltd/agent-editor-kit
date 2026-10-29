"""Publish actual installed59 evidence without changing the registered Skill."""
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-score-20261029-r1'

def load(p): return json.loads(p.read_bytes())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    case=load(BASE/'installed59-score-case-r2/verification.json')
    gpu=load(BASE/'installed59-gpu-r1/verification.json')
    draft=load(BASE/'skill59-draft-entry-r1/verification.json')
    assert case['status']==gpu['status']==draft['status']=='passed'
    assert case['complete_source_installed_PCM_equal'] and case['complete_source_installed_AV_equal']
    assert gpu['complete_source_installed_PCM_equal'] and gpu['actual_CUDA_model']
    assert draft['live_registered_cli']=='0.1.58' and not draft['activated']
    assets=ROOT/'docs/assets/music-score59-installed-20261029-r1';assets.mkdir(exist_ok=False)
    for key,name in [('wav','actual.wav'),('movie','actual.mp4'),('png','actual.png'),('gif','actual.gif'),('source','SOURCE.txt')]:
        shutil.copyfile(case['artifacts'][key],assets/name)
    source=dict(scope='actual-independent-installed59-replay',fixture_license='CC0-1.0',
        synthesizer_source_license='MIT',human_listening=False,neural_music=False,
        receipt='docs/validation/evidence/music-score-20261029-r1/installed59-score-case-r2/verification.json',
        receipt_sha256=sha(BASE/'installed59-score-case-r2/verification.json'),
        files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in assets.iterdir()})
    (assets/'SOURCE.json').write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    p=ROOT/'docs/product/CASES.md';text=p.read_text(encoding='utf-8')
    assert '### C75安装候选复核' not in text
    text+='''

### C75安装候选复核（CLI59/local57）

独立离线安装入口重新生成16秒／5分轨和4类音效，完整3072000字节原PCM与源码相同；导入后重新合成相同。全部480帧／110592000字节RGBA和6144000字节解码Float32 PCM与源码及包重放相同，无源码回落。r1因验收脚本变量名冲突在最终目录检查失败，保留记录；修复脚本后r2重新完整执行通过，应用源码未改。

[安装版真实WAV](../assets/music-score59-installed-20261029-r1/actual.wav) · [安装版真实MP4](../assets/music-score59-installed-20261029-r1/actual.mp4) · [来源与文件摘要](../assets/music-score59-installed-20261029-r1/SOURCE.json) · [完整安装版收据](../validation/evidence/music-score-20261029-r1/installed59-score-case-r2/verification.json)

![Actual installed59 measured waveform and authored score](../assets/music-score59-installed-20261029-r1/actual.gif)

这是实测波形／谱面诊断图和真实音频，不是GUI录制。另行完成实际PowerShell单入口Skill候选生成，完整PCM也与源码相同。正式注册仍58，安装400及正式切换继续开放；不计人类听审或神经音乐验收。
'''
    p.write_text(text,encoding='utf-8',newline='\n')
    headers={
    'README.md':'**CLI59安装候选完整音画复核通过**：16秒／5分轨的全部PCM、480帧画面及成片音频与源码和工程包重放一致；实际CUDA降噪4次前向的完整PCM也一致。单入口Skill候选已通过真实PowerShell生成配乐。安装400继续，正式注册仍CLI58。[安装版流程及边界](docs/validation/CLI59独立安装交付_2026-10-29.md)。',
    'README.en.md':'**CLI59 installed candidate passed complete music/AV replay**:all16s/5-track PCM,480 frames and decoded soundtrack match source and portable replay. Actual CUDA denoising also matches complete source PCM across4 forwards. The unregistered single-entry Skill generated music through its real PowerShell entry. Installed400 continues;registered Skill remains CLI58. [Usage and limits](docs/validation/CLI59独立安装交付_2026-10-29.md).',
    'README.zh-TW.md':'**CLI59安裝候選完整音畫複核通過**：16秒／5分軌的全部PCM、480幀畫面及成片音訊與原始碼和專案包重放一致；實際CUDA降噪4次前向的完整PCM也一致。單入口Skill候選已透過真實PowerShell生成配樂。安裝400繼續，正式註冊仍CLI58。[安裝流程及邊界](docs/validation/CLI59独立安装交付_2026-10-29.md)。'}
    rows={
    'README.md':[
    '| R462 | CLI59/local57独立安装候选 | 原生离线安装1706载荷／282模块／8原生资源逐字节一致；31入口／19配乐／19控制／57选材／104语义分别通过；正式Skill仍58 |',
    '| R463 | C75安装版完整配乐重放 | r1验收脚本变量冲突失败保留，修复后r2完整重做；3072000字节原PCM、110592000字节RGBA、6144000字节成片PCM与源码和工程重放相同；不计听审 |',
    '| R464 | CLI59源码及安装实际CUDA | 各4次DF3前向、完整1124160字节PCM相同并完成包重放；12.25dB受控噪声MSE改善，不计自然质量；源收据旧模块计数字段另有更正审计 |',
    '| R465 | 单入口Skill59候选 | 1入口／17模块／93文件，静态验证及真实PowerShell配乐、5分轨、音效和只读预检通过；完整PCM与源码相同；尚未正式注册，安装400继续 |'],
    'README.en.md':[
    '| R462 | CLI59/local57 native candidate |1706 exact payload files/282 modules/8 native resources;separate31 bootstrap/19 score/19 control/57 selection/104 semantic passes;registered Skill stays58 |',
    '| R463 | C75 installed full music replay | Retained r1 harness-variable failure;r2 fully rerun passed;all3072000 original PCM/110592000 RGBA/6144000 decoded PCM bytes match source and portable replay;no listening acceptance |',
    '| R464 | Actual source/installed CLI59 CUDA |4 DF3 forwards each,complete1124160-byte PCM matches source and replay;12.25dB controlled-noise MSE improvement,not natural quality;source report count corrected by separate audit |',
    '| R465 | Single-entry Skill59 candidate |1 entry/17 modules/93 files;static validation and actual PowerShell score,5 stems,effect,readonly preflight passed;complete PCM matches source;unregistered,installed400 pending |'],
    'README.zh-TW.md':[
    '| R462 | CLI59/local57獨立安裝候選 | 原生離線安裝1706載荷／282模組／8原生資源逐位元組一致；31入口／19配樂／19控制／57選材／104語義分別通過；正式Skill仍58 |',
    '| R463 | C75安裝版完整配樂重放 | 保留r1驗收腳本變數衝突失敗，修復後r2完整重做；3072000位元組原PCM、110592000位元組RGBA、6144000位元組成片PCM與原始碼和專案重放相同；不計聽審 |',
    '| R464 | CLI59原始碼與安裝實際CUDA | 各4次DF3前向、完整1124160位元組PCM相同並完成包重放；12.25dB受控噪聲MSE改善，不計自然品質；原收據模組計數另有更正稽核 |',
    '| R465 | 單入口Skill59候選 | 1入口／17模組／93檔案，靜態驗證及真實PowerShell配樂、5分軌、音效與唯讀預檢通過；完整PCM與原始碼相同；尚未正式註冊，安裝400繼續 |']}
    report={}
    for name,header in headers.items():
        p=ROOT/name;t=p.read_text(encoding='utf-8');old=[line for line in t.splitlines() if re.match(r'^\| R\d+ \|',line)]
        assert len(old)==461
        first,rest=t.split('\n',1);t=first+'\n\n'+header+'\n\n'+rest
        anchor=next(line for line in old if line.startswith('| R461 |'))
        t=t.replace(anchor,anchor+'\n'+'\n'.join(rows[name]),1)
        assert all(line in t.splitlines() for line in old)
        p.write_text(t,encoding='utf-8',newline='\n');report[name]=dict(previous_rows_preserved=461,current_rows=465,sha256=sha(p))
    out=BASE/'candidate-docs-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    (out/'verification.json').write_text(json.dumps(dict(status='passed',readmes=report,registered_cli='0.1.58',installed_candidate='0.1.59',installed400_accepted=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='passed',readmes=3,previous_rows_preserved=461,current_rows=465)))

if __name__=='__main__':main()
