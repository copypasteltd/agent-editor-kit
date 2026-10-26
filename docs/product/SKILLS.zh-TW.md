# 一個本地 Skill、17 項內部模塊詳情

<!-- community-current -->

**CLI0.1.34 / alpha.4-local.32 / r35 kit · 1 Skill / 17 modules / 75 files.**

新增原生 GPU 模型會話：明確啟動、查詢、停止，連續生成重用權重與同一提示詞嵌入；每個任務重設 scheduler、前窗上下文及統計。實際同機首條生成 654.27 秒，後兩條 35.46/28.48 秒；會話全模型校驗另計 480.42 秒。相同 seed 的 17 幀逐像素一致，實際去噪取消可回滾並退出所屬行程。

[Model session workflow](MODEL_SESSIONS.md)

<!-- /community-current -->

<!-- unified-skill-registration -->

只註冊 `$agent-ffmpeg-local-editor`。K01–K17 是按需讀取的內部模塊，原獨立名稱只用於追溯，調用時無需再指定。 [Guide](../skills/UNIFIED_SKILL.zh-TW.md)

<!-- /unified-skill-registration -->

[README](../../README.zh-TW.md) · [Registration](../local/INSTALLATION.md)

| 編號 | 內部模組 | 職責 | 輸入 → 輸出 | 相關命令 | 依賴/邊界 |
|---|---|---|---|---|---|
| K01 | [`$agent-ffmpeg-local-editor`](../../skills/agent-ffmpeg-local-editor/SKILL.md) | 專案總入口與交付 | brief + 本地素材 → 計劃、可編輯工程、成片、manifest | `project init; timeline compose; look; render` | 按能力路由，包含濾鏡客戶選型；需要基礎 CLI。 |
| K02 | [`timeline`](../../skills/agent-ffmpeg-local-editor/references/modules/timeline/module.md) | 時間線、關鍵影格與運鏡 | 編輯 JSON → 多軌/運鏡/轉場/嵌套 | `timeline compose/edit; motion apply; motion pack list/inspect/create/capture/apply` | 明確目標軌道/片段與作者時鐘。 |
| K03 | [`quality`](../../skills/agent-ffmpeg-local-editor/references/modules/quality/module.md) | 成片與像素核驗 | 成片 + manifest + 參考 → 報告/Scope/差異 | `quality check/scopes/mask/golden` | 區分目檢/播放/聽審；支持濾鏡樣例選型復核。 |
| K04 | [`project-ops`](../../skills/agent-ffmpeg-local-editor/references/modules/project-ops/module.md) | 工程運維、恢復與隊列 | 工程 + 作業 → 快照/恢復/重鏈/運行結果 | `project snapshot/recover; media relink; queue` | 保留舊源與失敗；不是云任務調度器。 |
| K05 | [`local-policy`](../../skills/agent-ffmpeg-local-editor/references/modules/local-policy/module.md) | 本地執行約束 | 工程引用 → 審計/結構化拒絕 | `policy audit` | 運行時禁止遠程引用；不推斷為 OS 沙箱。 |
| K06 | [`rights-ledger`](../../skills/agent-ffmpeg-local-editor/references/modules/rights-ledger/module.md) | 素材與模型權利證據 | 來源/許可/本地證據 → 臺賬/影響/門禁 | `rights list/check/update/impact` | 分別處理母圖與 LUT 許可；不自動認定版權。 |
| K07 | [`local-models`](../../skills/agent-ffmpeg-local-editor/references/modules/local-models/module.md) | 已有離線模型登記 | 原生環境 + 權重/雜湊/許可 → 適配器與推理產物 | `audio adapter; audio separate-stems; media adapter; asr adapter; ocr; face; tts` | 無權重下載；先核對能力/環境，再調用。 |
| K08 | [`video-understand`](../../skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md) | 鏡頭/靜音、圖文語義檢索與影片證據 | 本機影片/圖片/描述/參考圖 → 分析、預覽、來源時間與候選 | `media understand/contact-sheet; subtitle transcribe; semantic index/calibrate/calibration-list/search; project upgrade-semantic` | [檢索說明](../../skills/agent-ffmpeg-local-editor/references/semantic-retrieval.md)；採樣點不定義片段長度，候選需複核。 |
| K09 | [`template-library`](../../skills/agent-ffmpeg-local-editor/references/modules/template-library/module.md) | 模板與片段組復用 | 模板/變量/素材庫 → 可編輯變體與索引 | `template apply/batch; library; fragment` | 用戶自有素材，按資源許可復用。 |
| K10 | [`long-to-short`](../../skills/agent-ffmpeg-local-editor/references/modules/long-to-short/module.md) | 長影片轉短片 | 本地課程/口播 + 核對文本 → 粗剪與短片工程 | `media highlights/smart-cut; timeline compose` | 候選段需復核，不聲稱全自動語義導演。 |
| K11 | [`screen-demo`](../../skills/agent-ffmpeg-local-editor/references/modules/screen-demo/module.md) | 錄屏與錨點運鏡 | 錄屏 + 操作錨點 → 放大/回全景/字幕演示 | `timeline compose; ocr anchors; preview range` | OCR 需要已有模型，文本框不等於可點擊控件。 |
| K12 | [`reference-remake`](../../skills/agent-ffmpeg-local-editor/references/modules/reference-remake/module.md) | 參考片節奏與布局重建 | 本地參考 + 原創替換素材 → 可編輯重制 | `media understand; timeline compose` | 重建結構，不自動獲取或授權參考素材。 |
| K13 | [`ffmpeg`](../../skills/agent-ffmpeg-local-editor/references/modules/ffmpeg/module.md) | 原生音影片工具 | 本地文件 + 參數 → 轉碼/縮放/提取/壓縮 | `native ffmpeg / ffprobe` | 直接原生工具；先檢查編解碼器。 |
| K14 | [`video-edit`](../../skills/agent-ffmpeg-local-editor/references/modules/video-edit/module.md) | 通用影片剪切流程 | 本地文件 + 剪輯要求 → 修剪/拼接/疊加結果 | `native ffmpeg; installed CLI` | 復雜可編輯專案交給 timeline/editor。 |
| K15 | [`ad-creative`](../../skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md) | 廣告創意、可編輯分鏡與變體 | 產品/受眾/審核文案/實際資產 → 計劃、獨立序列與局部返工 | `advisory; ad plan; ad storyboard/build/revise` | 明確提供創意選擇與賣點證據；不自帶生成影片模型。 |
| K16 | [`video-content-strategist`](../../skills/agent-ffmpeg-local-editor/references/modules/video-content-strategist/module.md) | 影片內容策略 | 目標/受眾/提供的參考 → 內容定位/系列/腳本 | `advisory Skill` | 不自帶實時趨勢、平臺賬號或抓取器。 |
| K17 | [`campaign-analytics`](../../skills/agent-ffmpeg-local-editor/references/modules/campaign-analytics/module.md) | 提供資料的投放分析 | 本地投放表 → ROAS/CPA/漏斗/建議 | `advisory Skill` | 無廣告平臺連接；指標依賴原始資料與歸因假設。 |

## K01 · `$agent-ffmpeg-local-editor`

專案總入口與交付

brief + 本地素材 → 計劃、可編輯工程、成片、manifest

`project init; timeline compose; look; render`

按能力路由，包含濾鏡客戶選型；需要基礎 CLI。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/SKILL.md)

## K02 · `timeline`

時間線、關鍵影格與運鏡

編輯 JSON → 多軌/運鏡/轉場/嵌套

`timeline compose/edit; motion apply`

明確目標軌道/片段與作者時鐘。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/timeline/module.md)

## K03 · `quality`

成片與像素核驗

成片 + manifest + 參考 → 報告/Scope/差異

`quality check/scopes/mask/golden`

區分目檢/播放/聽審；支持濾鏡樣例選型復核。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/quality/module.md)

## K04 · `project-ops`

工程運維、恢復與隊列

工程 + 作業 → 快照/恢復/重鏈/運行結果

`project snapshot/recover; media relink; queue`

保留舊源與失敗；不是云任務調度器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/project-ops/module.md)

## K05 · `local-policy`

本地執行約束

工程引用 → 審計/結構化拒絕

`policy audit`

運行時禁止遠程引用；不推斷為 OS 沙箱。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/local-policy/module.md)

## K06 · `rights-ledger`

素材與模型權利證據

來源/許可/本地證據 → 臺賬/影響/門禁

`rights list/check/update/impact`

分別處理母圖與 LUT 許可；不自動認定版權。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/rights-ledger/module.md)

## K07 · `local-models`

已有離線模型登記

原生環境 + 權重/雜湊/許可 → 適配器與推理產物

`media adapter; asr adapter; ocr; face; tts; voice; translate; dub subtitles; gpu`

無權重下載；先核對能力/環境，再調用。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/local-models/module.md)

## K08 · `video-understand`

鏡頭/靜音與影片證據

本地影片/音頻 → 分析 JSON、影格、字幕候選

`media understand/contact-sheet; subtitle transcribe; semantic index/calibrate/calibration-list/search`

啟發式與模型語義能力分開說明。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/video-understand/module.md)

## K09 · `template-library`

模板與片段組復用

模板/變量/素材庫 → 可編輯變體與索引

`template apply/batch; library; fragment`

用戶自有素材，按資源許可復用。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/template-library/module.md)

## K10 · `long-to-short`

長影片轉短片

本地課程/口播 + 核對文本 → 粗剪與短片工程

`media highlights/smart-cut; timeline compose`

候選段需復核，不聲稱全自動語義導演。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/long-to-short/module.md)

## K11 · `screen-demo`

錄屏與錨點運鏡

錄屏 + 操作錨點 → 放大/回全景/字幕演示

`timeline compose; ocr anchors; preview range`

OCR 需要已有模型，文本框不等於可點擊控件。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/screen-demo/module.md)

## K12 · `reference-remake`

參考片節奏與布局重建

本地參考 + 原創替換素材 → 可編輯重制

`media understand; timeline compose`

重建結構，不自動獲取或授權參考素材。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/reference-remake/module.md)

## K13 · `ffmpeg`

原生音影片工具

本地文件 + 參數 → 轉碼/縮放/提取/壓縮

`native ffmpeg / ffprobe`

直接原生工具；先檢查編解碼器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/ffmpeg/module.md)

## K14 · `video-edit`

通用影片剪切流程

本地文件 + 剪輯要求 → 修剪/拼接/疊加結果

`native ffmpeg; installed CLI`

復雜可編輯專案交給 timeline/editor。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/video-edit/module.md)

## K15 · `ad-creative`

廣告創意與變體

產品/受眾/證據 → hook/文案/腳本/變體

`advisory; ad plan`

策略任務說明，不自帶媒體生成模型。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/ad-creative/module.md)

## K16 · `video-content-strategist`

影片內容策略

目標/受眾/提供的參考 → 內容定位/系列/腳本

`advisory Skill`

不自帶實時趨勢、平臺賬號或抓取器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/video-content-strategist/module.md)

## K17 · `campaign-analytics`

提供資料的投放分析

本地投放表 → ROAS/CPA/漏斗/建議

`advisory Skill`

無廣告平臺連接；指標依賴原始資料與歸因假設。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/references/modules/campaign-analytics/module.md)

## 濾鏡客戶選型

[Workflow](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [Gallery guide](../local/FILTER_GALLERY.zh-TW.md)

本機只註冊一個指向統一 Skill 的目錄聯接；17 項模組在目錄內按需讀取。運行包與圖冊是分離交付：僅安裝 wheel 並不自動包含圖冊。helper 只讀已經渲染的樣例，導出新對照板；最終編輯調用固定 CLI 並保存工程快照。


## CLI 0.1.5 / F50 / S18 / K08: visual semantic retrieval

[Complete workflow / 完整流程](SEMANTIC_RETRIEVAL.md) · [Skill reference](../../skills/agent-ffmpeg-local-editor/references/semantic-retrieval.md) · [Actual output](CASES.md#c14-semantic-retrieval).

Explicit local SigLIP2 image/video-sample embeddings; Chinese/English/reference-image search; native PTS, previews, editable source points, integrity and auto/cpu/cuda. 16 positive queries pass on this small familiar set; Chinese negation and both open-set queries fail expected selection/rejection. No natural-action, cross-shot identity, audio matching or large-library acceptance. One sampled point does not define clip duration.

CLI 0.1.7: K04 uses [owned job recovery](JOB_RECOVERY.md); preview `--cleanup-jobs --dry-run` and preserve active/changed/unknown/legacy files. K07 retains explicit adapter re-registration and separate model/runtime rights.


## CLI 0.1.9 / F51 / S20 / K07: joint subtitle translation and dubbing

[Workflow / 使用流程](SUBTITLE_DUBBING.md) · [Internal Skill reference](../../skills/agent-ffmpeg-local-editor/references/subtitle-dubbing.md) · [Actual C18 output](CASES.md#c18-subtitle-dubbing) · [Checks and failures](../validation/字幕翻译配音联合流程实测_2026-10-25.md).

Plain local SRT → OPUS Chinese/English translation → one Kokoro initialization per voice batch → actual complete WAV sample checks → atomic editable audio/bilingual captions. Original text/times and every speed attempt are retained. Explicit tracks/casting/mixing and bounded whole-utterance regeneration; managed cancellation/timeout/recovery protects committed media and model licenses.

字幕翻译、完整分段配音、实际时窗和可编辑入轨已实现；字幕翻譯、完整分段配音、實際時窗與可編輯入軌已實作。仅中英/普通 SRT；仅 cue 级安排。Actual awkward translations remain recorded. Naturalness, semantic acceptance, word alignment, lip sync, broad reliability and full CapCut parity remain open. The existing 103-name voice catalog now has at least seven distinct voices actually generated; no human listening acceptance.


<!-- semantic-decisions-current -->

## CLI 0.1.10 / F50 / S18 / K08: explicit clauses and empirical acceptance

[完整流程 / Workflow](SEMANTIC_RETRIEVAL.md) · [实际质量/错误 / Actual results](../validation/语义条件与校准拒识实测_2026-10-25.md) · [C19](CASES.md#c19-semantic-decisions).

中英条件检索与同帧正负比较、索引/类型/实现/实际设备绑定经验校准已交付。
中英條件檢索、同影格正負比較與裝置綁定經驗校準已實作。
`semantic calibrate/calibration-list/search` uses 32–128 reviewed examples (at least 16 positive and 16 absent),
a correct-positive gate and empirical strict cutoff. Labels stay in the controller. All results still require review.
Installed CPU/CUDA and the actual Skill retain two false accepts and one original false rejection.
The new retrieval package fails search after import even though general validate succeeds; portable profiles are not established.
Complex negation, natural actions/identity/audio/recommendation, large-library performance and managed semantic crash recovery remain open.
Original CLI 0.1.5 query failures and raw mode remain historical evidence; they are not erased by this extension.

<!-- /semantic-decisions-current -->

[Fixed-canvas affine reuse / 扫描行复用](AFFINE_RENDERING.md) uses the existing render workflow, keeps CPU composition explicit, and provides paired timing and actual previews.

[Animated crop and native-canvas projection / 动态裁切与嵌套投影](PROJECTION_RENDERING.md) retains the existing bilinear/area kernels, explicit raster quota and editable keys; CPU composition and GPU encoding remain separate.

CLI0.1.22: independent/inline Float32 text, joint typewriter/highlight and plain SRT. Read [workflow](FLOAT_TEXT.md); CPU,8bit coverage/Float32 colors,explicit fonts and original clocks. 4K text/GPU text/rich ASS and full target acceptance remain open.

Historical CLI0.1.23:[4K text and reusable native byte coverage](FLOAT_TEXT_COVERAGE.md). CPU tiled linear component composition,exact original clocks,bounded adaptive caches. GPU text,natural quality,HDR,realtime and full original conditions remain open.

CLI0.1.24:[native Float32 GPU workflow](FLOAT_GPU.md). Explicit geometry/normal composition/text colors/word selection;owned worker cleanup;CPU glyph rasterization and remaining operators retained. Full original target conditions remain open.

CLI0.1.25: [global/interval Float32 grading](FLOAT_ADJUSTMENTS.md); one selected root, authored clocks, explicit local LUT dependencies; CPU effects with compatible GPU composition. One Skill /17 modules /72 files.
