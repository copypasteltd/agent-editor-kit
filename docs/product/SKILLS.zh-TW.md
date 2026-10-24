# 17 個本地 Skill 詳情

[README](../../README.zh-TW.md) · [Registration](../local/INSTALLATION.md)

| 編號 | Skill | 職責 | 輸入 → 輸出 | 相關命令 | 依賴/邊界 |
|---|---|---|---|---|---|
| K01 | [`$agent-ffmpeg-local-editor`](../../skills/agent-ffmpeg-local-editor/SKILL.md) | 專案總入口與交付 | brief + 本地素材 → 計劃、可編輯工程、成片、manifest | `project init; timeline compose; look; render` | 按能力路由，包含濾鏡客戶選型；需要基礎 CLI。 |
| K02 | [`$agent-ffmpeg-local-timeline`](../../skills/agent-ffmpeg-local-timeline/SKILL.md) | 時間線、關鍵影格與運鏡 | 編輯 JSON → 多軌/運鏡/轉場/嵌套 | `timeline compose/edit; motion apply` | 明確目標軌道/片段與作者時鐘。 |
| K03 | [`$agent-ffmpeg-local-quality`](../../skills/agent-ffmpeg-local-quality/SKILL.md) | 成片與像素核驗 | 成片 + manifest + 參考 → 報告/Scope/差異 | `quality check/scopes/mask/golden` | 區分目檢/播放/聽審；支持濾鏡樣例選型復核。 |
| K04 | [`$agent-ffmpeg-local-project-ops`](../../skills/agent-ffmpeg-local-project-ops/SKILL.md) | 工程運維、恢復與隊列 | 工程 + 作業 → 快照/恢復/重鏈/運行結果 | `project snapshot/recover; media relink; queue` | 保留舊源與失敗；不是云任務調度器。 |
| K05 | [`$agent-ffmpeg-local-local-policy`](../../skills/agent-ffmpeg-local-local-policy/SKILL.md) | 本地執行約束 | 工程引用 → 審計/結構化拒絕 | `policy audit` | 運行時禁止遠程引用；不推斷為 OS 沙箱。 |
| K06 | [`$agent-ffmpeg-local-rights-ledger`](../../skills/agent-ffmpeg-local-rights-ledger/SKILL.md) | 素材與模型權利證據 | 來源/許可/本地證據 → 臺賬/影響/門禁 | `rights list/check/update/impact` | 分別處理母圖與 LUT 許可；不自動認定版權。 |
| K07 | [`$agent-ffmpeg-local-local-models`](../../skills/agent-ffmpeg-local-local-models/SKILL.md) | 已有離線模型登記 | 原生環境 + 權重/雜湊/許可 → 適配器與推理產物 | `media adapter; asr adapter; ocr; face; tts` | 無權重下載；先核對能力/環境，再調用。 |
| K08 | [`$agent-ffmpeg-local-video-understand`](../../skills/agent-ffmpeg-local-video-understand/SKILL.md) | 鏡頭/靜音與影片證據 | 本地影片/音頻 → 分析 JSON、影格、字幕候選 | `media understand/contact-sheet; subtitle transcribe` | 啟發式與模型語義能力分開說明。 |
| K09 | [`$agent-ffmpeg-local-template-library`](../../skills/agent-ffmpeg-local-template-library/SKILL.md) | 模板與片段組復用 | 模板/變量/素材庫 → 可編輯變體與索引 | `template apply/batch; library; fragment` | 用戶自有素材，按資源許可復用。 |
| K10 | [`$agent-ffmpeg-local-long-to-short`](../../skills/agent-ffmpeg-local-long-to-short/SKILL.md) | 長影片轉短片 | 本地課程/口播 + 核對文本 → 粗剪與短片工程 | `media highlights/smart-cut; timeline compose` | 候選段需復核，不聲稱全自動語義導演。 |
| K11 | [`$agent-ffmpeg-local-screen-demo`](../../skills/agent-ffmpeg-local-screen-demo/SKILL.md) | 錄屏與錨點運鏡 | 錄屏 + 操作錨點 → 放大/回全景/字幕演示 | `timeline compose; ocr anchors; preview range` | OCR 需要已有模型，文本框不等於可點擊控件。 |
| K12 | [`$agent-ffmpeg-local-reference-remake`](../../skills/agent-ffmpeg-local-reference-remake/SKILL.md) | 參考片節奏與布局重建 | 本地參考 + 原創替換素材 → 可編輯重制 | `media understand; timeline compose` | 重建結構，不自動獲取或授權參考素材。 |
| K13 | [`$agent-ffmpeg-local-ffmpeg`](../../skills/agent-ffmpeg-local-ffmpeg/SKILL.md) | 原生音影片工具 | 本地文件 + 參數 → 轉碼/縮放/提取/壓縮 | `native ffmpeg / ffprobe` | 直接原生工具；先檢查編解碼器。 |
| K14 | [`$agent-ffmpeg-local-video-edit`](../../skills/agent-ffmpeg-local-video-edit/SKILL.md) | 通用影片剪切流程 | 本地文件 + 剪輯要求 → 修剪/拼接/疊加結果 | `native ffmpeg; installed CLI` | 復雜可編輯專案交給 timeline/editor。 |
| K15 | [`$agent-ffmpeg-local-ad-creative`](../../skills/agent-ffmpeg-local-ad-creative/SKILL.md) | 廣告創意與變體 | 產品/受眾/證據 → hook/文案/腳本/變體 | `advisory; ad plan` | 策略任務說明，不自帶媒體生成模型。 |
| K16 | [`$agent-ffmpeg-local-video-content-strategist`](../../skills/agent-ffmpeg-local-video-content-strategist/SKILL.md) | 影片內容策略 | 目標/受眾/提供的參考 → 內容定位/系列/腳本 | `advisory Skill` | 不自帶實時趨勢、平臺賬號或抓取器。 |
| K17 | [`$agent-ffmpeg-local-campaign-analytics`](../../skills/agent-ffmpeg-local-campaign-analytics/SKILL.md) | 提供資料的投放分析 | 本地投放表 → ROAS/CPA/漏斗/建議 | `advisory Skill` | 無廣告平臺連接；指標依賴原始資料與歸因假設。 |

## K01 · `$agent-ffmpeg-local-editor`

專案總入口與交付

brief + 本地素材 → 計劃、可編輯工程、成片、manifest

`project init; timeline compose; look; render`

按能力路由，包含濾鏡客戶選型；需要基礎 CLI。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-editor/SKILL.md)

## K02 · `$agent-ffmpeg-local-timeline`

時間線、關鍵影格與運鏡

編輯 JSON → 多軌/運鏡/轉場/嵌套

`timeline compose/edit; motion apply`

明確目標軌道/片段與作者時鐘。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-timeline/SKILL.md)

## K03 · `$agent-ffmpeg-local-quality`

成片與像素核驗

成片 + manifest + 參考 → 報告/Scope/差異

`quality check/scopes/mask/golden`

區分目檢/播放/聽審；支持濾鏡樣例選型復核。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-quality/SKILL.md)

## K04 · `$agent-ffmpeg-local-project-ops`

工程運維、恢復與隊列

工程 + 作業 → 快照/恢復/重鏈/運行結果

`project snapshot/recover; media relink; queue`

保留舊源與失敗；不是云任務調度器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-project-ops/SKILL.md)

## K05 · `$agent-ffmpeg-local-local-policy`

本地執行約束

工程引用 → 審計/結構化拒絕

`policy audit`

運行時禁止遠程引用；不推斷為 OS 沙箱。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-local-policy/SKILL.md)

## K06 · `$agent-ffmpeg-local-rights-ledger`

素材與模型權利證據

來源/許可/本地證據 → 臺賬/影響/門禁

`rights list/check/update/impact`

分別處理母圖與 LUT 許可；不自動認定版權。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-rights-ledger/SKILL.md)

## K07 · `$agent-ffmpeg-local-local-models`

已有離線模型登記

原生環境 + 權重/雜湊/許可 → 適配器與推理產物

`media adapter; asr adapter; ocr; face; tts`

無權重下載；先核對能力/環境，再調用。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-local-models/SKILL.md)

## K08 · `$agent-ffmpeg-local-video-understand`

鏡頭/靜音與影片證據

本地影片/音頻 → 分析 JSON、影格、字幕候選

`media understand/contact-sheet; subtitle transcribe`

啟發式與模型語義能力分開說明。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-video-understand/SKILL.md)

## K09 · `$agent-ffmpeg-local-template-library`

模板與片段組復用

模板/變量/素材庫 → 可編輯變體與索引

`template apply/batch; library; fragment`

用戶自有素材，按資源許可復用。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-template-library/SKILL.md)

## K10 · `$agent-ffmpeg-local-long-to-short`

長影片轉短片

本地課程/口播 + 核對文本 → 粗剪與短片工程

`media highlights/smart-cut; timeline compose`

候選段需復核，不聲稱全自動語義導演。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-long-to-short/SKILL.md)

## K11 · `$agent-ffmpeg-local-screen-demo`

錄屏與錨點運鏡

錄屏 + 操作錨點 → 放大/回全景/字幕演示

`timeline compose; ocr anchors; preview range`

OCR 需要已有模型，文本框不等於可點擊控件。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-screen-demo/SKILL.md)

## K12 · `$agent-ffmpeg-local-reference-remake`

參考片節奏與布局重建

本地參考 + 原創替換素材 → 可編輯重制

`media understand; timeline compose`

重建結構，不自動獲取或授權參考素材。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-reference-remake/SKILL.md)

## K13 · `$agent-ffmpeg-local-ffmpeg`

原生音影片工具

本地文件 + 參數 → 轉碼/縮放/提取/壓縮

`native ffmpeg / ffprobe`

直接原生工具；先檢查編解碼器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-ffmpeg/SKILL.md)

## K14 · `$agent-ffmpeg-local-video-edit`

通用影片剪切流程

本地文件 + 剪輯要求 → 修剪/拼接/疊加結果

`native ffmpeg; installed CLI`

復雜可編輯專案交給 timeline/editor。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-video-edit/SKILL.md)

## K15 · `$agent-ffmpeg-local-ad-creative`

廣告創意與變體

產品/受眾/證據 → hook/文案/腳本/變體

`advisory; ad plan`

策略任務說明，不自帶媒體生成模型。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-ad-creative/SKILL.md)

## K16 · `$agent-ffmpeg-local-video-content-strategist`

影片內容策略

目標/受眾/提供的參考 → 內容定位/系列/腳本

`advisory Skill`

不自帶實時趨勢、平臺賬號或抓取器。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-video-content-strategist/SKILL.md)

## K17 · `$agent-ffmpeg-local-campaign-analytics`

提供資料的投放分析

本地投放表 → ROAS/CPA/漏斗/建議

`advisory Skill`

無廣告平臺連接；指標依賴原始資料與歸因假設。

[Actual Skill instructions](../../skills/agent-ffmpeg-local-campaign-analytics/SKILL.md)

## 濾鏡客戶選型

[Workflow](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [Gallery guide](../local/FILTER_GALLERY.zh-TW.md)

本機 17 個目錄均為 E 盤源文件到 Codex 發現路徑的聯接。運行包與圖冊是分離交付：僅安裝 wheel 並不自動包含圖冊。helper 只讀已經渲染的樣例，導出新對照板；最終編輯調用固定 CLI 並保存工程快照。
