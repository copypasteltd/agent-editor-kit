"""Publish only actual CLI60 loop evidence; preserve historical README rows."""
import hashlib
import json
import re
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'

def main():
    report=json.loads((BASE/'actual-case-r1/verification.json').read_bytes())
    assert report['status']=='passed' and report['source_only']
    assert report['complete_package_recipe_repair_PCM_equal']
    assert json.loads((BASE/'targeted-r1/verification.json').read_bytes())['status']=='passed'
    out=ROOT/'docs/assets/music-loop60-20261029-r1';out.mkdir(exist_ok=True)
    names=dict(source='source.wav',unit='unit.wav',before='before.wav',after='after.wav',
        png='actual.png',gif='actual.gif',package='package.zip',recipe='recipe.json',notice='SOURCE.txt')
    inventory={}
    for key,name in names.items():
        src=Path(report['artifacts'][key]);dest=out/name
        if dest.exists():assert dest.read_bytes()==src.read_bytes()
        else:shutil.copyfile(src,dest)
        inventory[name]=dict(bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
    (out/'SOURCE_AND_LICENSES.json').write_text(json.dumps(dict(
        source='Original C75 analytical score fragment; actual CLI60 overlap repair and repetitions',
        media_license='CC0-1.0',code_license='MIT',neural_forwards=0,
        human_listening=False,natural_music_seamlessness_accepted=False,
        gif='Single-frame actual waveform diagnostic, not screen recording',files=inventory),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rows={
      'README.md':('| F84 | 循环接缝交叠修复（开发CLI60） | 样本时钟、双曲线、可编辑配方、权利继承、取消与事务回滚；周期明确缩短。 | `music repair-loop` | [流程与C76试听](docs/product/MUSIC_LOOP.md)；正式Skill仍59，未计自然听感验收。 |',
        '| R469 | CLI60循环修复专项 | 18项新修复＋19项谱面回归全部通过；独立混合公式、完整中段、取消回滚、权利与工程包重做；[收据](docs/validation/evidence/music-loop-20261029-r1/targeted-r1/verification.json) |',
        '| R470 | C76实际音乐接缝 | 13.37→13.32秒，50ms交叠；完整2557440字节PCM在导入后配方重做一致，前三／后三循环可试听；[案例](docs/product/MUSIC_LOOP.md)。CPU，无神经推理或听审 |'),
      'README.en.md':('| F84 | Loop overlap repair(source CLI60) | Sample-clock crossfade,two curves,editable recipe,inherited rights,cancel and transactional rollback;explicit shorter cycle. | `music repair-loop` | [Workflow and C76 audio](docs/product/MUSIC_LOOP.md);registered Skill remains59,no listening acceptance. |',
        '| R469 | CLI60 loop regression | 18 new loop and19 score tests passed;independent mix oracle,body identity,cancel/rollback,rights and package re-repair;[receipt](docs/validation/evidence/music-loop-20261029-r1/targeted-r1/verification.json) |',
        '| R470 | C76 actual loop repair | 13.37→13.32s,50ms overlap;complete2557440-byte PCM identical after package recipe replay;three-cycle before/after audio;[case](docs/product/MUSIC_LOOP.md).CPU,no neural forwards or listening acceptance |'),
      'README.zh-TW.md':('| F84 | 循環接縫交疊修復（開發CLI60） | 樣本時鐘、雙曲線、可編輯配方、權利繼承、取消與交易回復；週期明確縮短。 | `music repair-loop` | [流程與C76試聽](docs/product/MUSIC_LOOP.md)；正式Skill仍59，未計自然聽感驗收。 |',
        '| R469 | CLI60循環修復專項 | 18項新修復＋19項譜面回歸全部通過；獨立混合公式、完整中段、取消回復、權利與專案包重做；[收據](docs/validation/evidence/music-loop-20261029-r1/targeted-r1/verification.json) |',
        '| R470 | C76實際音樂接縫 | 13.37→13.32秒，50ms交疊；完整2557440位元組PCM匯入後配方重做一致，前／後三循環可試聽；[案例](docs/product/MUSIC_LOOP.md)。CPU，無神經推論或聽審 |')}
    preserved={}
    for name,(feature,*checks) in rows.items():
        p=ROOT/name;text=p.read_text(encoding='utf-8');lines=text.splitlines()
        old=[line for line in lines if re.match(r'^\| R\d+ \|',line)]
        assert len(old)==468 and not any(line.startswith('| F84 |') for line in lines)
        index=next(i for i,line in enumerate(lines) if line.startswith('| F83 |'))
        lines.insert(index+1,feature)
        index=next(i for i,line in enumerate(lines) if line.startswith('| R468 |'))
        lines[index+1:index+1]=checks
        updated='\n'.join(lines)+'\n';assert all(line in updated for line in old)
        p.write_text(updated,encoding='utf-8');preserved[name]=len(old)
    cases=ROOT/'docs/product/CASES.md'
    with cases.open('a',encoding='utf-8') as f:
        f.write('\n\n## C76 — source60 sample-clock loop repair\n\n[实际前后音频、波形、配方、工程包与明确边界](MUSIC_LOOP.md)。13.37秒原创解析配乐片段交叠50ms，周期13.32秒；完整PCM包重做一致。开发源码60限定；正式Skill59未包含。不是自然音乐或人工听审验收。\n')
    gap=ROOT/'docs/product/GOAL_GAPS_20261025.md';text=gap.read_text(encoding='utf-8')
    old=next(line for line in text.splitlines() if line.startswith('| G25 |'));parts=old.split('|')
    closure=parts[5]
    parts[3]+='；开发CLI60另有CPU循环交叠修复、严格配方、实际PCM包重放，正式Skill仍59'
    parts[4]=parts[4].replace('无缝循环修复','自然听感无缝循环验收')
    new='|'.join(parts);assert new.split('|')[5]==closure
    gap.write_text(text.replace(old,new),encoding='utf-8')
    attr=ROOT/'.gitattributes'
    with attr.open('a',encoding='utf-8') as f:f.write('\ndocs/validation/evidence/music-loop-20261029-r1/** -text -whitespace\ndocs/assets/music-loop60-20261029-r1/** -text -whitespace\n')
    proof=BASE/'publication-r1';proof.mkdir(exist_ok=False)
    (proof/'verification.json').write_text(json.dumps(dict(status='passed',preserved_R_rows=preserved,
        new_R_rows=470,G25_closure_unchanged=True,source_only=True,registered_cli='0.1.59',files=inventory),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='passed',published_files=len(inventory),preserved_R_rows=preserved)),flush=True)

if __name__=='__main__':main()
