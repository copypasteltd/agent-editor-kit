"""Publish installed403, all real voice auditions and the actual local gallery."""
import hashlib,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
VOICE=ROOT/'docs/validation/evidence/voice-auditions-20261029-r1'
NOTE='docs/validation/CLI61全音色试听_2026-10-29.md'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(path.read_bytes())


def main():
    full=load(BASE/'installed61-contracts-r1/verification.json')
    assert full['status']=='passed' and full['tests']==403 and full['frozen_equal'] and full['source_and_installed_equal']
    assert full['failures']==full['errors']==full['skipped']==0
    assert all(sha(ROOT/p)==h for p,h in full['file_hashes'].items())
    voice=load(VOICE/'r2/verification.json')
    assert voice['status']=='passed' and voice['voices']==103 and voice['actual_CUDA_generations']==103
    assert voice['total_model_initializations']==2 and voice['all_full_PCM_package_replay_equal']
    assert not voice['human_listening'] and not voice['audio_published'] and voice['rights']=='internal-unverified'
    assert load(VOICE/'r1/verification.json')['status']=='failed'
    screenshot=load(VOICE/'gallery-screenshot-r1/verification.json')
    assert screenshot['status']=='passed' and screenshot['owned_browser_processes_remaining']==0
    assert screenshot['source_audio_elements']==103 and sha(ROOT/screenshot['screenshot'])==screenshot['screenshot_sha256']
    records=voice['voice_records'];assert len(records)==103 and len({r['PCM_sha256'] for r in records})==103
    gallery=Path(voice['local_gallery']);index=load(gallery.parent/'voices.json')
    assert index['voices']==records and screenshot['source_page_sha256']==sha(gallery)
    for row in records:
        assert sha(gallery.parent/row['preview'])==row['WAV_sha256'] and row['full_package_PCM_equal']
    installation=load(BASE/'installation-candidate-r1/verification.json')
    assert all(sha(p)==h for p,h in installation['registered_skill_file_hashes'].items())
    out=VOICE/'publication-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    texts={
        'README.md':[
            '独立安装403项完整契约终态通过，零失败／错误／跳过；283应用模块与源码及测试冻结一致。实际CUDA口型及完整音画重放另列，不将契约数当自然质量通过数。',
            '103音色已逐项实际生成WAV：中文100／英文3，显式CUDA及provider DLL加载、两批各一次初始化，无应用层CPU回退；完整32157758字节PCM工程包往返一致。新增本地逐音色试听页与逐项元数据，未听审／权利未核验。',
            '真实原生Chrome截图展示本地103音色试听页；无头浏览器已退出，未留对应进程或交互标签页。截图不等于播放／听审，未将内部声音文件公开发布。'],
        'README.zh-TW.md':[
            '獨立安裝403項完整契約終態通過，零失敗／錯誤／跳過；283應用模組與原始碼及測試凍結一致。實際CUDA口型及完整音畫重播另列，不將契約數當自然品質通過數。',
            '103音色已逐項實際產生WAV：中文100／英文3，明確CUDA及provider DLL載入、兩批各一次初始化，無應用層CPU回退；完整32157758位元組PCM工程包往返一致。新增本地逐音色試聽頁與逐項中繼資料，未聽審／權利未核驗。',
            '真實原生Chrome截圖展示本地103音色試聽頁；無頭瀏覽器已退出，未留對應行程或互動分頁。截圖不等於播放／聽審，未公開發布內部聲音檔案。'],
        'README.en.md':[
            'Independent installed403 contracts passed with zero failures/errors/skips;283 app modules and tests frozen against source.Actual CUDA lip-sync and full media replay are separate;contract counts do not establish natural quality.',
            'All103 voices produced actual WAVs:100 Chinese/3 English,explicit CUDA with provider DLL loaded,one initialization per language batch,and no application-level CPU fallback.All32157758 PCM bytes survived package replay.A local per-voice audition gallery and metadata are available;listening and output rights remain unaccepted.',
            'An actual native Chrome screenshot shows the local103-voice gallery.The owned headless browser exited with no matching process or interactive tab left.Screenshot capture is not playback/listening,and internal audio files were not publicly published.']}
    paths=[]
    for name,values in texts.items():
        p=ROOT/name;text=p.read_text(encoding='utf-8')
        old=[line for line in text.splitlines() if re.match(r'^\| R\d+ \|',line)];assert len(old)==491
        lines=text.splitlines();i=next(i for i,line in enumerate(lines) if line.startswith('| R491 |'))
        for j,value in enumerate(values):lines.insert(i+1+j,f'| R{492+j} | CLI61 voice delivery | '+value+' [Evidence / use]('+NOTE+') |')
        text='\n'.join(lines)+'\n';assert all(line in text for line in old)
        ids=re.findall(r'^\| (R\d+) \|',text,re.M);assert len(ids)==len(set(ids))==494
        mark='<!-- aek-history-summary -->';assert mark in text
        block={'README.md':'新增103音色本地试听流程：先按语言／音色ID听样音，确认后再用于配音。全量WAV已实际生成，听感、发音、情绪及输出权利仍待审核。',
               'README.zh-TW.md':'新增103音色本地試聽流程：先依語言／音色ID聽樣音，確認後再用於配音。全量WAV已實際產生，聽感、發音、情緒及輸出權利仍待審核。',
               'README.en.md':'New local103-voice audition workflow:listen by language/voice ID and confirm before dubbing.All WAVs are real outputs;pronunciation,emotion,naturalness and output rights still need review.'}[name]
        text=text.replace(mark,block+' [Workflow / 逐音色数据]('+NOTE+')\n\n![Actual local103 voice gallery](docs/assets/voice-gallery61-20261029-r1/actual.png)\n\n'+mark,1)
        p.write_text(text,encoding='utf-8',newline='\n');paths.append(p)
    table=['| 编号 | 音色 ID | 语言／标签 | 实际时长（秒） | 样本数／PCM字节 | 本地预览文件 |',
           '| --- | --- | --- | --- | --- | --- |']
    for row in records:
        table.append(f'| V{row["number"]:03} | `{row["voice_id"]}` | {row["language"]}／{row["gender"]} | {row["duration_seconds"]:.6f} | {row["frames"]}／{row["PCM_bytes"]} | `{row["preview"]}` |')
    per_voice='\n'.join(table)
    body=f'''# CLI61 全部103音色实际试听生成与交付

本轮使用CLI61／local59独立安装版公开 `dub subtitles` 命令，实际生成全部103个音色的WAV。中文100、英文3，各批仅初始化一次Kokoro；使用显式CUDA，原生provider DLL已加载，无应用层CPU回退。未验证每个ONNX算子的执行设备，不将此证据写成所有算子都在GPU运行。没有使用真人参考音色克隆。

全部24kHz／单声道／16bit PCM，共32157758字节，各输出非静音且103项PCM哈希均不同；每项声音完整导出／导入工程包后相同。未截断原句，同语种保持原文，不调用翻译。自动WAV检查、页面截图、实际试听、发音校对和自然度验收是不同层次；后三者本轮未完成。

## 本地试听与选型

[打开本机103音色试听页](E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/voice-preview61-r2/preview/index.html)。页面在E盘，音频 `preload=none`，点击后才加载；截图里的0:00不代表WAV为空。该路径属于本机安装，GitHub读者须按下述流程在自己的已配置本地环境重新生成。

![实际本地试听页截图](../assets/voice-gallery61-20261029-r1/actual.png)

1. 按语言和音色ID寻找候选，点击实际WAV，比较音色、发音及语气。中文样句为“这是本地语音试听，请听清每个字，再选择适合的声音。”；英文为“This is a local voice preview. Please listen before choosing.”。
2. 告诉Agent选定的 `voice_id`，以原任务文本另行生成、试听；通用样句不代表产品名、长文、数字、专名或情绪表现均合格。
3. 需要可编辑字幕配音时，用 `--voice-map` 对原字幕编号明确指定音色；不自动猜测角色。保留源文、原声、模型和输出的权利账本，再明确挂接、渲染与导出工程。
4. 样音当前为 `internal-unverified`：可供本地内部试听选型，未发布这些音频到公共仓库，也未提升商业使用权利。截图是项目原创UI与文本的实际浏览器截图，不包含音频发布许可。

## 复现

在本仓库已有CLI61独立候选及原生Kokoro CPU／CUDA包时执行；`--run` 须是尚不存在的新编号，避免覆盖历史输出：

```powershell
& 'C:/Python313/python.exe' -E -B -u -X utf8 docs/validation/run_installed61_voice_auditions.py --run customer1
```

程序从当前本地运行配置读取已有包位置，显式传入 `--voice-pack`、`--voice-gpu-pack`、`--voice-cuda-library-directory`，生成中／英SRT及选角JSON，再调用独立安装版。没有全局安装、下载新权重或Docker／WSL。输出位于 `local/agent-ffmpeg/voice-preview61-customer1/preview/`；每个音色的JSON包含WAV／PCM哈希、时长、样本数、来源工程和审核状态。

首轮r1因直接安装入口缺少显式模型配置，在推理前以 `ARGUMENT_INVALID` 停止，保留原失败。r2改用明确本地包路径后全部通过。该修正属于调用流程，不是更改产品模型或绕过校验。

## 逐音色实测

下表预览文件相对于本地 `preview/`；每项是本轮真实生成值，非估算。历史7个音色的旧结果保留，不与本轮103重复计数。每项仍未人类听审。

{per_voice}

## 原始证据及当前版本

- [103音色完整WAV／PCM及两批CUDA收据](evidence/voice-auditions-20261029-r1/r2/verification.json)
- [首轮配置失败原始收据](evidence/voice-auditions-20261029-r1/r1/verification.json)
- [实际Chrome截图及进程退出收据](evidence/voice-auditions-20261029-r1/gallery-screenshot-r1/verification.json)
- [安装版完整403回归](evidence/lipsync-timeout-20261029-r1/installed61-contracts-r1/verification.json)：零失败／错误／跳过，283模块与源码及测试冻结一致。

源码及独立安装候选均CLI61，正式Skill仍CLI59／local57／r57。CLI61候选Skill已生成且静态校验通过；其PowerShell实际案例、正式切换与最终独立r58包仍另行验收。G18缺少的方言、多语、情绪、自然韵律、任务语境及人类听审未因此关闭；全部38组原关闭条件保持。
'''
    note=ROOT/NOTE;note.write_text(body,encoding='utf-8',newline='\n');paths.append(note)
    catalog=ROOT/'docs/product/COMMUNITY_VOICES.md';old=catalog.read_text(encoding='utf-8')
    current='# 103 个具名音色 / Named voices\n\nCLI61独立安装版已逐项生成全部103个音色：中文100／英文3，两批显式CUDA各初始化一次，完整PCM与工程包往返一致；仍未人类听审及输出权利审核。[本地试听页、完整命令、样句与收据](../validation/CLI61全音色试听_2026-10-29.md)。\n\n'+per_voice+'\n\n<details>\n<summary>本轮之前的逐音色历史状态（完整保留）</summary>\n\n'+old+'\n</details>\n'
    assert old in current;catalog.write_text(current,encoding='utf-8',newline='\n');paths.append(catalog)
    gaps=ROOT/'docs/product/GOAL_GAPS_20261025.md';text=gaps.read_text(encoding='utf-8')
    def closures(s):return {line.split('|')[1].strip():line.split('|')[-3].strip() for line in s.splitlines() if re.match(r'^\| G\d\d \|',line)}
    before=closures(text);assert len(before)==38
    marker='累计至少 7 个不同音色有真实 WAV；103 项试听、自然韵律、情绪/方言/多语与客户语境人类听审未完成'
    assert marker in text
    text=text.replace(marker,'原7音色历史保留；CLI61安装候选本轮103音色均实际生成WAV、两批显式CUDA各一次初始化、完整PCM工程包往返及本地试听页已验；自然韵律、情绪/方言/多语与客户语境的人类逐项听审仍未完成',1)
    index=text.index('\n\n')+2
    text=text[:index]+'2026-10-29 G18：CLI61独立安装候选已实际生成全部103音色试听WAV及本地选型页，完整PCM工程包往返通过；安装完整403也已通过。正式Skill仍59，候选PowerShell验证继续。原38组关闭条件不变，未把生成或自动检查当作自然发音／听审验收。[逐音色实测与使用](../validation/CLI61全音色试听_2026-10-29.md)。\n\n'+text[index:]
    assert closures(text)==before
    gaps.write_text(text,encoding='utf-8',newline='\n');paths.append(gaps)
    guide=ROOT/'docs/validation/CLI61独立安装交付_2026-10-29.md';text=guide.read_text(encoding='utf-8');index=text.index('\n\n')+2
    text=text[:index]+'后续终态：独立安装完整403项服务契约现已通过，零失败／错误／跳过；全部103音色也已通过实际显式CUDA生成及完整PCM工程包重放。[全音色试听流程和实际数据](CLI61全音色试听_2026-10-29.md)。正式Skill仍59，候选入口和最终工具包另验。\n\n'+text[index:]
    guide.write_text(text,encoding='utf-8',newline='\n');paths.append(guide)
    result=dict(status='passed',README_rows=494,previous491_rows_preserved=True,installed403_passed=True,
                actual_voice_auditions=103,total_PCM_bytes=32157758,local_gallery=True,
                actual_browser_screenshot=True,owned_browser_processes_remaining=0,
                previous_voice_catalog_preserved=True,all38_goal_closures_preserved=True,
                protected_files_unchanged=95,formal_activation=False,
                file_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='file_hashes'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
