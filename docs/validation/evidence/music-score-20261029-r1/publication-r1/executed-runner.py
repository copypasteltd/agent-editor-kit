"""Publish original source59 fixture media; preserve prior releases and README rows."""
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/music-score-20261029-r1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    case_path = BASE/'actual-case-r1/verification.json'
    case = json.loads(case_path.read_bytes())
    assert case['status'] == 'passed' and case['source_only'] and case['cli_version'] == '0.1.59'
    assert case['complete_recomposition_PCM_equal'] and case['complete_rendered_AV_replay_equal']
    assert case['actual_model_forwards'] == 0 and case['registered_skill_unchanged']
    target = ROOT/'docs/assets/music-score59-20261029-r1'
    target.mkdir(exist_ok=False)
    names = {'wav':'actual.wav', 'movie':'actual.mp4', 'png':'actual.png', 'gif':'actual.gif',
             'editable_package':'editable-score.zip', 'score':'score.json', 'source':'SOURCE.txt'}
    for key, name in names.items():
        shutil.copyfile(case['artifacts'][key], target/name)
    for name, effect in case['effects'].items():
        source = Path(effect['path'])
        assert 'sha256:'+sha(source) == effect['sha256']
        shutil.copyfile(source, target/(name+'.wav'))
    save(target/'SOURCE.json', dict(format='agent-original-fixture-v1', cli_version='0.1.59',
        license='CC0-1.0', source_code_license='MIT', copied_recordings=False, model_weights=False,
        neural_generation=False, human_listening=False, case_receipt_sha256=sha(case_path),
        files={p.name:dict(bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(target.iterdir()) if p.is_file()}))
    case_doc = ROOT/'docs/product/CASES.md'
    text = case_doc.read_text('utf-8')
    assert 'id="c75-source59-editable-score"' not in text
    text += '''

<a id="c75-source59-editable-score"></a>
## C75：源码CLI59可编辑谱面与原创程序音频

原生CPU解析合成，16秒／48kHz双声道16bit，5条实际分轨，8种可用乐器和4种不同电子音效；没有模型前向、采样音色库或复制录音。谱面与程序生成的诊断图／音频属于本例原创CC0素材，源代码MIT。它不是神经生曲、人类演奏或自然质量验收。

[原始完整WAV](../assets/music-score59-20261029-r1/actual.wav) · [实际成片MP4](../assets/music-score59-20261029-r1/actual.mp4) · [可编辑谱面](../assets/music-score59-20261029-r1/score.json) · [完整工程包](../assets/music-score59-20261029-r1/editable-score.zip) · [来源与摘要](../assets/music-score59-20261029-r1/SOURCE.json)

![Measured source59 waveform and authored score](../assets/music-score59-20261029-r1/actual.png)

![Actual source59 diagnostic movie](../assets/music-score59-20261029-r1/actual.gif)

音效试听：[whoosh](../assets/music-score59-20261029-r1/whoosh.wav) · [riser](../assets/music-score59-20261029-r1/riser.wav) · [impact](../assets/music-score59-20261029-r1/impact.wav) · [chime](../assets/music-score59-20261029-r1/chime.wav)。四项实际生成，完整文件摘要各不相同；不是重命名同一音频。

完整3072000字节原始PCM在导出／导入后重新合成逐字节相同。实际成片为320×180／30fps／480帧，完整110592000字节RGBA和6144000字节解码Float32 PCM与工程包重放相同。成片画面是实际测得波形及谱面诊断图，不是GUI截图或神经视频。PNG已目检，无连续视听／听审结论；AAC成片不声称与原16bit母带无损相同。

引擎对用户输入默认保持unverified／internal，不自动确认商用权利；本例明确的CC0来源说明不泛化到其他输入。正式注册仍CLI58，源码59的新安装／Skill交付、自然质量及G25完整范围继续开放。[接口与限制](MUSIC_SCORE.md) · [核验记录](../validation/CLI59谱面合成_2026-10-29.md) · [原始实测收据](../validation/evidence/music-score-20261029-r1/actual-case-r1/verification.json)
'''
    case_doc.write_text(text, encoding='utf-8', newline='\n')
    prefixes = {
        'README.md': '**开发源码CLI0.1.59新增可编辑谱面合成与4类程序音效**：8种解析乐器、分轨、时间线挂接及谱面工程包重合成；19项专项、31入口／57选材／104语义分组分别通过。C75实际16秒／5轨、完整PCM重合成及成片音画重放通过。控制回归有1个PID测试标记空读错误，400项仍运行；正式Skill保持CLI58，不自动调用源码。',
        'README.en.md': '**Development CLI0.1.59 adds editable-score synthesis and4 procedural effects**:8 analytical instruments,stems,timeline placement and portable score recomposition. The19 targeted and31 bootstrap/57 selection/104 semantic groups passed separately. C75 passed actual16s/5-track synthesis,full PCM recomposition and full rendered AV replay. One control test hit an empty PID fixture marker;400 contracts continue. The registered Skill remains CLI58 and never falls back to source.',
        'README.zh-TW.md': '**開發原始碼CLI0.1.59新增可編輯譜面合成及4類程序音效**：8種解析樂器、分軌、時間線掛接與譜面專案重合成；19項專項、31入口／57選材／104語義分組分別通過。C75實際16秒／5軌、完整PCM重合成及成片音畫重播通過。控制回歸有1個PID測試標記空讀錯誤，400項仍執行；正式Skill維持CLI58，不自動呼叫原始碼。'}
    frows = {
        'README.md':'| F83 | 可编辑谱面与程序音效（源码59） | 谱面拍点／MIDI音高／8解析乐器 → 48kHz双声道WAV、分轨和可编辑工程；4种电子音效。 | `music inspect-score/compose/effect` | [实际内容、命令、配器与限制](docs/product/MUSIC_SCORE.md)；不是神经生曲，正式Skill58暂不支持。 |',
        'README.en.md':'| F83 | Editable score and procedural effects(source59) | Beat/MIDI score and8 analytical instruments →48kHz stereo WAV,stems and editable package;4 electronic effects. | `music inspect-score/compose/effect` | [Implementation,workflow and limits](docs/product/MUSIC_SCORE.md);not neural text-to-music,not yet in registered CLI58. |',
        'README.zh-TW.md':'| F83 | 可編輯譜面與程序音效（原始碼59） | 譜面拍點／MIDI音高／8解析樂器 → 48kHz雙聲道WAV、分軌與可編輯專案；4種電子音效。 | `music inspect-score/compose/effect` | [實際內容、命令、配器及限制](docs/product/MUSIC_SCORE.md)；不是神經生曲，正式Skill58暫不支援。 |'}
    rows = {
        'README.md':[
            '| R459 | CLI59谱面核心与事务 | 19专项、31入口、57选材、104语义分组分别通过；首轮设备字段错误保留，修正后复验；[证据与范围](docs/validation/CLI59谱面合成_2026-10-29.md) |',
            '| R460 | C75实际源码音频与成片 | 16秒5分轨、4种不同音效、完整3072000字节PCM重合成和110592000字节RGBA／6144000字节Float32 PCM重放一致；无神经推理或听审；[案例](docs/product/CASES.md#c75-source59-editable-score) |',
            '| R461 | CLI59交付前检查边界 | 控制19项1个PID标记空读错误；原子发布夹具原型4项通过，未替换正式测试；400项运行中，正式安装／Skill仍58；旧手册版本已同步 |'],
        'README.en.md':[
            '| R459 | CLI59 score core and transactions | Targeted19/bootstrap31/selection57/semantic104 passed separately;initial device-field error retained and fixed;[evidence and scope](docs/validation/CLI59谱面合成_2026-10-29.md) |',
            '| R460 | C75 actual source audio and movie |16s/5 stems/4 distinct effects;complete3072000-byte PCM recomposition and110592000-byte RGBA/6144000-byte Float32 PCM replay match;no neural inference or listening acceptance;[case](docs/product/CASES.md#c75-source59-editable-score) |',
            '| R461 | CLI59 delivery boundaries | One empty-PID-marker error in19 control tests;atomic-publication fixture prototype passed4 tests without changing formal tests;400 contracts running,installed Skill remains58;older manual version banners synchronized |'],
        'README.zh-TW.md':[
            '| R459 | CLI59譜面核心與事務 | 19專項、31入口、57選材、104語義分組分別通過；首輪設備欄位錯誤保留，修正後複驗；[證據與範圍](docs/validation/CLI59谱面合成_2026-10-29.md) |',
            '| R460 | C75實際原始碼音訊與成片 | 16秒5分軌、4種不同音效、完整3072000位元組PCM重合成與110592000位元組RGBA／6144000位元組Float32 PCM重播相同；無神經推理或聽審；[案例](docs/product/CASES.md#c75-source59-editable-score) |',
            '| R461 | CLI59交付前檢查邊界 | 控制19項1個PID標記空讀錯誤；原子發佈夾具原型4項通過，未替換正式測試；400項執行中，正式安裝／Skill仍58；舊手冊版本已同步 |']}
    audit = {}
    for name, prefix in prefixes.items():
        path = ROOT/name; old = path.read_text('utf-8')
        original_rows = re.findall(r'^\| R\d+ .*$', old, re.M)
        assert len(original_rows) == 458
        title, body = old.split('\n', 1)
        links = '[Score workflow / 谱面流程](docs/product/MUSIC_SCORE.md) · [C75 WAV / MP4 / editable package](docs/product/CASES.md#c75-source59-editable-score)'
        text = title+'\n\n'+prefix+'\n\n'+links+'\n\n![Actual source59 score audition](docs/assets/music-score59-20261029-r1/actual.gif)\n'+body
        last_f = next(line for line in text.splitlines() if line.startswith('| F82 |'))
        last_r = next(line for line in text.splitlines() if line.startswith('| R458 |'))
        text = text.replace(last_f, last_f+'\n'+frows[name], 1)
        text = text.replace(last_r, last_r+'\n'+'\n'.join(rows[name]), 1)
        assert all(row in text for row in original_rows)
        assert len(re.findall(r'^\| R\d+ .*$', text, re.M)) == 461
        path.write_text(text, encoding='utf-8', newline='\n')
        audit[name] = dict(previous_rows_preserved=458, current_rows=461, sha256=sha(path))
    out = BASE/'publication-r1'; out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    save(out/'verification.json', dict(status='passed', source_only=True, cli_version='0.1.59',
        readmes=audit, files={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(target.iterdir()) if p.is_file()},
        registered_skill_cli='0.1.58', full_product_goal_closed=False))
    print(json.dumps(dict(status='published', readmes=audit), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
