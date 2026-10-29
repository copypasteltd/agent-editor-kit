"""Publish actual installed60 results only after short gates, CUDA and case pass."""
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'

def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    for group,count in [('bootstrap',31),('loop',37),('control',19),('selection',57),('semantic',104)]:
        r=load(BASE/('installed60-'+group+'-r1/verification.json'))
        assert r['status']=='passed' and r['tests']==count and r['source_and_installed_equal'] and r['frozen_equal']
        assert r['failures']==r['errors']==r['skipped']==0
        assert all(sha(ROOT/name)==pin for name,pin in r['file_hashes'].items())
    case=load(BASE/'installed-actual-case-r1/verification.json');gpu=load(BASE/'installed60-gpu-r1/verification.json')
    assert case['status']=='passed' and case['complete_source_installed_PCM_equal']
    assert case['complete_package_recipe_repair_PCM_equal'] and case['registered_skill_unchanged']
    assert gpu['status']=='passed' and gpu['complete_source_installed_PCM_equal']
    assert gpu['actual_CUDA_model'] and gpu['complete_PCM_replay_equal'] and gpu['code_files']==283
    out=ROOT/'docs/assets/music-loop60-installed-20261029-r1';out.mkdir(exist_ok=False)
    inventory={}
    for key,name in [('unit','actual.wav'),('png','actual.png'),('gif','actual.gif')]:
        target=out/name;shutil.copyfile(Path(case['artifacts'][key]),target)
        inventory[name]=dict(bytes=target.stat().st_size,sha256=sha(target))
    (out/'SOURCE_AND_LICENSES.json').write_text(json.dumps(dict(media_license='CC0-1.0',code_license='MIT',
        source='Actual CLI0.1.60 independently installed C76 original analytical score loop repair',
        model_forwards=0,human_listening=False,natural_music_seamlessness_accepted=False,
        GIF='Single-frame diagnostic waveform,not screen recording',
        complete_PCM_sha256=case['complete_repaired_PCM_sha256'],files=inventory),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rows={
      'README.md':[
        '| R474 | CLI60独立安装功能回归 | 安装目录实际31入口／37配乐／19控制／57选材／104语义分别通过，零失败／错误／跳过，283模块与源码相同；正式Skill仍59，安装400另验 |',
        '| R475 | C76安装版与实际CUDA | 循环完整2557440字节PCM与源码及包重做相同；DF3实际4次CUDA前向，完整1124160字节PCM与源码／重放相同；[安装实测与音频](docs/validation/CLI60独立安装交付_2026-10-29.md)。不计自然质量或听审 |'],
      'README.en.md':[
        '| R474 | CLI60 installed functional groups | Actual installed31 bootstrap/37 music/19 control/57 selection/104 semantic tests passed separately,zero failures/errors/skips,283 modules match source;registered Skill remains59,installed400 separate |',
        '| R475 | C76 installed and actual CUDA | Complete2557440-byte loop PCM matches source and package re-repair;DF3 actual4 CUDA forwards,complete1124160-byte PCM matches source/replay;[installed evidence and audio](docs/validation/CLI60独立安装交付_2026-10-29.md).No natural-quality or listening acceptance |'],
      'README.zh-TW.md':[
        '| R474 | CLI60獨立安裝功能回歸 | 安裝目錄實際31入口／37配樂／19控制／57選材／104語義分別通過，零失敗／錯誤／跳過，283模組與原始碼相同；正式Skill仍59，安裝400另驗 |',
        '| R475 | C76安裝版與實際CUDA | 循環完整2557440位元組PCM與原始碼及專案包重做相同；DF3實際4次CUDA前向，完整1124160位元組PCM與原始碼／重放相同；[安裝實測及音訊](docs/validation/CLI60独立安装交付_2026-10-29.md)。不計自然品質或聽審 |']}
    for name,added in rows.items():
        p=ROOT/name;lines=p.read_text(encoding='utf-8').splitlines()
        old=[x for x in lines if re.match(r'^\| R\d+ \|',x)];assert len(old)==473
        i=next(i for i,x in enumerate(lines) if x.startswith('| R473 |'));lines[i+1:i+1]=added
        text='\n'.join(lines)+'\n';assert all(x in text for x in old);p.write_text(text,encoding='utf-8')
    p=ROOT/'docs/validation/CLI60独立安装交付_2026-10-29.md';text=p.read_text(encoding='utf-8')
    text=text.replace('安装候选的31入口已通过。安装37专项、19控制、57选材、104语义、实际GPU及C76重做正在串行验收，安装400完整契约单独运行，未出终态收据不计通过。',
        '安装候选的31入口／37配乐专项／19控制／57选材／104语义分别通过，零失败／错误／跳过。实际DF3 CUDA及C76完整PCM重做也已通过。安装400完整契约单独运行，未出终态收据不计通过。')
    text+='''

## 实际独立安装案例

![实际安装版接缝测量](../assets/music-loop60-installed-20261029-r1/actual.png)

[实际安装版修复音频](../assets/music-loop60-installed-20261029-r1/actual.wav) · [来源与摘要](../assets/music-loop60-installed-20261029-r1/SOURCE_AND_LICENSES.json) · [完整案例收据](evidence/music-loop-20261029-r1/installed-actual-case-r1/verification.json)。13.37秒源片段经50ms交叠成为13.32秒，完整2557440字节PCM与开发源码和工程包导入后配方重做相同。前后各三周期的完整PCM与单元直接重复相同，中段不改。未人工听审，不计自然音乐无缝验收。

[实际安装CUDA收据](evidence/music-loop-20261029-r1/installed60-gpu-r1/verification.json)：RTX3060／4次DF3模型前向／无CPU回落，完整1124160字节PCM与源码及工程包重放相同，受控噪声MSE改善12.25446dB。这是已有降噪路径的回归，不增加其它模型或自然质量验收。
'''
    p.write_text(text,encoding='utf-8')
    p=ROOT/'docs/product/CASES.md'
    with p.open('a',encoding='utf-8') as f:f.write('\n\n### C76 — independent installed60 replay\n\n[安装版实际音频、波形与完整PCM证据](../validation/CLI60独立安装交付_2026-10-29.md)。283安装模块与源码相同，循环完整PCM与源码及可编辑工程重做相同；独立实际DF3 CUDA回归亦通过。正式Skill仍59，未计自然听审或完整目标闭合。\n')
    with (ROOT/'.gitattributes').open('a',encoding='utf-8') as f:f.write('\ndocs/assets/music-loop60-installed-20261029-r1/** -text -whitespace\n')
    evidence=BASE/'installed-publication-r1';evidence.mkdir(exist_ok=False)
    (evidence/'verification.json').write_text(json.dumps(dict(status='passed',current_R_rows=475,
        previous_R_rows_preserved=473,files=inventory,formal_cli='0.1.59',candidate_cli='0.1.60',
        actual_loop_PCM_bytes=2557440,actual_CUDA_PCM_bytes=1124160,
        natural_quality_accepted=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='passed',current_R_rows=475,published_files=3)),flush=True)

if __name__=='__main__':main()
