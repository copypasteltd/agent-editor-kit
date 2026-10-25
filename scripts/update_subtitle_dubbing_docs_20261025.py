"""Add the verified joint-dubbing delivery without rewriting historical README rows."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = 'docs/validation/evidence/subtitle-dubbing-20261025-r1/'


def main():
    sections = {
        'README.md': '''## 本机 CLI 0.1.9：字幕翻译、完整配音与可编辑交付

`dub subtitles` 联合 OPUS 中英翻译、Kokoro 批量配音、实际 WAV 时窗检查和原子工程提交。一次 voice batch 只初始化一次模型；逐段保留原文、译文、完整声音、所有语速尝试及原 cue 时间。默认超窗拒绝；显式加速会完整重生成，最多三次，不截台词。

先按[完整流程](docs/product/SUBTITLE_DUBBING.md)准备源 SRT、字体及明确的 audio/subtitle 目标轨道，再运行：

```powershell
& $avk dub subtitles --project $project --input $sourceSrt --from en --to zh-Hans --device auto --fit reject --apply --audio-track-id track_audio_1 --subtitle-track-id captions --font-asset-id caption_font --dry-run
& $avk dub subtitles --project $project --input $sourceSrt --from en --to zh-Hans --device auto --fit reject --apply --audio-track-id track_audio_1 --subtitle-track-id captions --font-asset-id caption_font
& $avk validate --project $project
```

安装版 GPU 22 次 CLI、CPU 另 9 次、真实统一 Skill 另 9 次，分别留档；27 项安装专项、122 项 CLI 回归通过，另验运行中取消/超时及三个强制中断边界。19 秒/570 帧成片的工程往返 PCM/解码 RGB 相同。第三段实际译文“以秒数创建另一个版本 。”仍不自然，原结果保留；没有据技术通过宣布语义、听感、逐字或口型达标。

[实际结果与失败](docs/validation/字幕翻译配音联合流程实测_2026-10-25.md) · [C18 / 原输入、实际输出、工程与 GIF](docs/product/CASES.md#c18-subtitle-dubbing)。下图是实际成片的无声诊断；配音权利未核验，完整音画和可编辑包保留本地。''',
        'README.zh-TW.md': '''## 本機 CLI 0.1.9：字幕翻譯、完整配音與可編輯交付

`dub subtitles` 串接 OPUS 中英翻譯、Kokoro 批次配音、實際 WAV 時窗檢查及原子工程提交。一次 voice batch 只初始化一次模型；逐段保留原文、譯文、完整聲音、所有語速嘗試及原 cue 時間。預設超窗拒絕；明確加速會完整重新生成，最多三次，不截台詞。

先按[完整流程](docs/product/SUBTITLE_DUBBING.md)準備來源 SRT、字體及明確的 audio/subtitle 目標軌道，再執行：

```powershell
& $avk dub subtitles --project $project --input $sourceSrt --from en --to zh-Hans --device auto --fit reject --apply --audio-track-id track_audio_1 --subtitle-track-id captions --font-asset-id caption_font --dry-run
& $avk dub subtitles --project $project --input $sourceSrt --from en --to zh-Hans --device auto --fit reject --apply --audio-track-id track_audio_1 --subtitle-track-id captions --font-asset-id caption_font
& $avk validate --project $project
```

安裝版 GPU 22 次 CLI、CPU 另 9 次、真實統一 Skill 另 9 次，分別留存；27 項安裝專項、122 項 CLI 回歸通過，另驗執行中取消/逾時及三個強制中斷邊界。19 秒/570 影格成片的工程往返 PCM/解碼 RGB 相同。第三段原始譯文「以秒数创建另一个版本 。」仍不自然，原結果保留；沒有據技術通過宣告語義、聽感、逐字或口型達標。

[實際結果與失敗](docs/validation/字幕翻译配音联合流程实测_2026-10-25.md) · [C18 / 原始輸入、實際輸出、工程與 GIF](docs/product/CASES.md#c18-subtitle-dubbing)。下圖是實際成片的無聲診斷；配音權利未核驗，完整音畫與可編輯包保留本機。''',
        'README.en.md': '''## Local CLI 0.1.9: subtitle translation and complete editable dubbing

`dub subtitles` combines OPUS Chinese/English translation, batched Kokoro speech, actual WAV window checks and an atomic project commit. One voice batch initializes Kokoro once; source/translated text, complete speech, all speed attempts and original cue times are retained. Overflow refuses the commit by default. Explicit speed fitting regenerates whole utterances up to three times without cutting dialogue.

Prepare the source SRT, ingested font and explicit audio/subtitle destination tracks using the [complete workflow](docs/product/SUBTITLE_DUBBING.md), then run:

```powershell
& $avk dub subtitles --project $project --input $sourceSrt --from en --to zh-Hans --device auto --fit reject --apply --audio-track-id track_audio_1 --subtitle-track-id captions --font-asset-id caption_font --dry-run
& $avk dub subtitles --project $project --input $sourceSrt --from en --to zh-Hans --device auto --fit reject --apply --audio-track-id track_audio_1 --subtitle-track-id captions --font-asset-id caption_font
& $avk validate --project $project
```

Installed GPU: 22 CLI calls; CPU: another 9; actual registered Skill: another 9, recorded separately. The installed 27-method suite and 122-method CLI regression pass, alongside active cancellation/timeout and three hard-stop boundaries. The 19-second/570-frame package roundtrip preserves PCM and decoded RGB exactly. The actual third translation, “以秒数创建另一个版本 。”, remains awkward and is retained. Engineering checks do not establish semantic acceptance, natural listening, word precision or lip sync.

[Actual results and retained failures](docs/validation/字幕翻译配音联合流程实测_2026-10-25.md) · [C18 / inputs, actual output, project and GIF](docs/product/CASES.md#c18-subtitle-dubbing). The preview is a silent diagnostic extracted from the real output. Full audio/project media stays local while content rights remain unverified.'''
    }
    features = {
        'README.md': '| F51 / D01 | 中英字幕翻译、批量完整配音、实际 WAV 时窗、显式音色/混音和原子入轨 | 仅普通 SRT / 中英；cue 级时间，语义/听感/口型未验收 |',
        'README.zh-TW.md': '| F51 / D01 | 中英字幕翻譯、批次完整配音、實際 WAV 時窗、明確音色/混音及原子入軌 | 僅普通 SRT / 中英；cue 級時間，語義/聽感/口型未驗收 |',
        'README.en.md': '| F51 / D01 | Chinese/English SRT translation, complete batched speech, actual WAV fitting, explicit casting/mixing and atomic clips | Plain SRT / Chinese-English only; cue timing, semantics/naturalness/lip sync unaccepted |'
    }
    services = {
        'README.md': '| S20 | 字幕翻译配音联合服务 | 既有 OPUS / Kokoro 原生 worker + 受管工程事务 | 普通 SRT、明确语言/音色/轨道，CPU/CUDA/auto，批内复用 | `dub subtitles` | [完整流程](docs/product/SUBTITLE_DUBBING.md)；保留全句和重试，字词/口型/自然质量未闭 |',
        'README.zh-TW.md': '| S20 | 字幕翻譯配音聯合服務 | 既有 OPUS / Kokoro 原生 worker + 受管工程事務 | 普通 SRT、明確語言/音色/軌道，CPU/CUDA/auto，批內復用 | `dub subtitles` | [完整流程](docs/product/SUBTITLE_DUBBING.md)；保留全句與重試，字詞/口型/自然品質未閉 |',
        'README.en.md': '| S20 | Joint subtitle dubbing | Existing native OPUS/Kokoro workers + managed project transaction | Plain SRT, explicit languages/voices/tracks, CPU/CUDA/auto, batch reuse | `dub subtitles` | [Workflow](docs/product/SUBTITLE_DUBBING.md); complete utterances/retries retained; words/lip sync/natural quality open |'
    }
    checks = {
        'README.md': [
            ('最终安装版专项与回归', '新配音专项 27/27、CLI 122/122，无 skip；197 个产品 Python 文件等于源码', 'tests/installed-r2/verification.json', 'tests/installed-cli-r2/verification.json', '契约测试与真实模型分开；未重跑历史 2930'),
            ('真实字幕翻译配音', 'GPU 22 次 CLI / 6 流水线 / 11 次完整声音生成；CPU 另 9 / 2 / 4，含原始译文与超窗拒绝', 'installed-gpu-r2/verification.json', 'installed-cpu-r2/verification.json', '保留错译，无人工听审/语义接受/口型结论'),
            ('配音运行控制与崩溃恢复', '实际 worker 取消/总超时、三个 owner 强制结束；提交前回滚，提交后声音/字幕/模型许可保留', 'control-r1/verification.json', 'crashes-r1/verification.json', '只有受管路径；其他缓存、断电/磁盘/长并发仍开放'),
            ('实际双语成片与工程包', '8 次 CLI，19 秒/570 帧；原声音摆放 PCM 最大差 0，工程往返 PCM/RGB 相同', 'demo-r1/verification.json', 'demo-r1/executed-generator.py', 'C18 无声诊断，原错译保留；不是自然视听验收'),
            ('统一 Skill r8 与本地加载', '一个注册入口/17 内部模块；真实 Skill 另 9 次 CLI、两个 CUDA 任务；小型 kit 独立清单/注册核验', 'skill-r1/verification.json', 'kit-r1/verification.json', '同一物理主机；旧 kit/公开 alpha.3 未覆盖')
        ],
        'README.zh-TW.md': [
            ('最終安裝版專項與回歸', '新配音專項 27/27、CLI 122/122，無 skip；197 個產品 Python 檔案等於原始碼', 'tests/installed-r2/verification.json', 'tests/installed-cli-r2/verification.json', '契約測試與真實模型分開；未重跑歷史 2930'),
            ('真實字幕翻譯配音', 'GPU 22 次 CLI / 6 流程 / 11 次完整聲音生成；CPU 另 9 / 2 / 4，含原始譯文與超窗拒絕', 'installed-gpu-r2/verification.json', 'installed-cpu-r2/verification.json', '保留錯譯，無人工聽審/語義接受/口型結論'),
            ('配音執行控制與崩潰復原', '實際 worker 取消/總逾時、三個 owner 強制結束；提交前回滾，提交後聲音/字幕/模型許可保留', 'control-r1/verification.json', 'crashes-r1/verification.json', '僅受管路徑；其他快取、斷電/磁碟/長並行仍開放'),
            ('實際雙語成片與工程包', '8 次 CLI，19 秒/570 影格；原聲音擺放 PCM 最大差 0，工程往返 PCM/RGB 相同', 'demo-r1/verification.json', 'demo-r1/executed-generator.py', 'C18 無聲診斷，原錯譯保留；不是自然視聽驗收'),
            ('統一 Skill r8 與本機載入', '一個註冊入口/17 內部模組；真實 Skill 另 9 次 CLI、兩個 CUDA 任務；小型 kit 獨立清單/註冊核驗', 'skill-r1/verification.json', 'kit-r1/verification.json', '同一實體主機；舊 kit/公開 alpha.3 未覆蓋')
        ],
        'README.en.md': [
            ('Final installed contracts/regression', '27/27 dubbing and 122/122 CLI methods, no skip; 197 product Python files equal source', 'tests/installed-r2/verification.json', 'tests/installed-cli-r2/verification.json', 'Contract tests separate from real models; historical 2930 not rerun'),
            ('Real subtitle translation and speech', 'GPU: 22 CLI / 6 pipelines / 11 complete generations; CPU: another 9 / 2 / 4, including original translations and overflow refusal', 'installed-gpu-r2/verification.json', 'installed-cpu-r2/verification.json', 'Awkward translations retained; no human listening/semantic acceptance/lip sync'),
            ('Dubbing control and crash recovery', 'Actual worker cancellation/deadline and three hard-stopped owners; precommit rollback, postcommit speech/captions/model licenses preserved', 'control-r1/verification.json', 'crashes-r1/verification.json', 'Managed paths only; other caches/power/disk/long concurrency remain open'),
            ('Actual bilingual edit/package', '8 CLI calls, 19 seconds/570 frames; source-placement PCM max difference 0; package PCM/RGB exact', 'demo-r1/verification.json', 'demo-r1/executed-generator.py', 'C18 silent diagnostic retains awkward translation; not natural audiovisual acceptance'),
            ('Unified Skill r8/local loading', 'One entry/17 modules; actual Skill: another 9 CLI calls, both CUDA tasks; separate kit inventory/registration check', 'skill-r1/verification.json', 'kit-r1/verification.json', 'Same physical host; old kits/public alpha.3 retained')
        ]
    }
    pending = {}
    for name in sections:
        source = (ROOT/name).read_text('utf-8')
        old_rows = re.findall(r'^\| R\d{2} \|.*$',source,re.M)
        assert len(old_rows)==66 and '<!-- subtitle-dubbing-r1 -->' not in source
        text = source.replace('r7 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r7.zip)', 'r8 Skill kit](docs/skills/agent-editor-kit-community-unified-skill-r8.zip)',1)
        # This replaces only the current top statement, preserving old feature/history versions.
        text=text.replace('CLI 0.1.8，GPU','CLI 0.1.9，GPU',1).replace('CLI 0.1.8, GPU','CLI 0.1.9, GPU',1)
        text=text.replace('实际常规生成试听 3 音色','至少 7 个音色有真实生成，未完成人类听审',1)
        text=text.replace('實際常規生成試聽 3 音色','至少 7 個音色有真實生成，未完成人類聽審',1)
        text=text.replace('Only three different voices generated/listened; no cloning or full-voice acceptance','At least seven voices actually generated; no human listening acceptance, cloning or full-voice review',1)
        line=next(line for line in text.splitlines() if line.startswith('| F50 /'))
        text=text.replace(line,line+'\n'+features[name],1)
        line=next(line for line in text.splitlines() if line.startswith('| S19 |'))
        text=text.replace(line,line+'\n'+services[name],1)
        text=text.replace('F44–F50','F44–F51',1)
        block='<!-- subtitle-dubbing-r1 -->\n\n'+sections[name]+'\n\n![Actual installed subtitle dubbing — silent](docs/assets/subtitle-dubbing-20261025-r1/demo-r1/preview.gif)\n\n<!-- /subtitle-dubbing-r1 -->\n\n'
        text=text.replace('<!-- ctc-activity-r1 -->',block+'<!-- ctc-activity-r1 -->',1)
        extra=[]
        for number,(title,result,a,b,limits) in enumerate(checks[name],67):
            extra.append(f'| R{number} | {title} | {result} | [Evidence]({BASE+a}) · [Separate scope]({BASE+b}); 2026-10-25; {limits} |')
        extra.append('| R72 | G01–G38 / current goal review | CLI 0.1.9, 75 declarations; all 38 original closure conditions retained | [Numbered gap assessment](docs/product/GOAL_GAPS_20261025.md) · [Actual entry/API](docs/validation/evidence/goal-gaps-20261025-r10/inventory.json) · [History/link audit](docs/validation/evidence/goal-gaps-20261025-r10/documentation-audit.json); 2026-10-25; review calls counted separately from inference/render; no overall completion percentage |')
        text=text.replace(old_rows[-1],old_rows[-1]+'\n'+'\n'.join(extra),1)
        footer={'README.md':'[当前完整目标差距表]','README.zh-TW.md':'[目前完整目標差距表]','README.en.md':'[The complete-goal assessment]'}[name]
        pos=text.index(footer)
        text=text[:pos]+text[pos:].replace('CLI 0.1.8','CLI 0.1.9',1).replace('R60–R66','R67–R72',1)
        assert re.findall(r'^\| R\d{2} \|.*$',text,re.M)[:66]==old_rows
        assert len(re.findall(r'^\| R\d{2} \|.*$',text,re.M))==72
        assert len(text)>len(source)
        pending[name]=text
    for name,text in pending.items():
        (ROOT/name).write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps(dict(updated=list(pending),historical_rows_per_readme_preserved=66,new_checks='R67-R72'),ensure_ascii=False))


if __name__=='__main__':main()
