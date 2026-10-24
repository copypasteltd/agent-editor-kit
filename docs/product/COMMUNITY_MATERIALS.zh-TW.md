# 開源素材、配音、翻譯、配樂與 GPU 使用手冊

本輪交付是本機已安裝驗證的 **CLI 0.1.3 / `v0.1.0-alpha.4-local.1`**。公開 GitHub Release 仍為 alpha.3 / CLI 0.1.2；不要把這些新命令用於舊附件。註冊入口仍只有 `$agent-ffmpeg-local-editor`，17 項內部模組繼續保留。

## 能力與交付層級

| 編號 | 模組 | 已實現 | 實際邊界 |
|---|---|---|---|
| M01 | 社群資源 | 44 首 BGM、85 個短樂、228 個獨立音效、Noto 簡/繁 2 個字型；共 359 項實際檔案 | 不是商業素材訂閱庫；5 首音軌經明確有損轉碼，2 對重複音效只計獨立檔案，保留別名 |
| M02 | 本地配音 | Kokoro 103 個上游具名音色，中英文字/UTF-8 檔案、0.5–2.0 語速、24kHz 單聲道 PCM WAV、匯入/顯式應用音軌 | 實際生成 3 個音色試聽檔案；人工聽審未完成，不做克隆或自動情緒保證 |
| M03 | 中英翻譯 | OPUS 中英雙向、簡/繁輸入輸出、逐段文字、雙語字幕、顯式術語譯後替換 | 非通用多語翻譯；SRT 保留 cue 順序/毫秒/重疊，ASS/VTT 轉 SRT 後丟樣式；無自動語義驗收 |
| M04 | BGM 準備 | 按素材 ID 匯入；偏移、擷取、明確迴圈、增益、淡入淡出 | 迴圈不等於接縫修復；不生成原創音樂 |
| M05 | 混音/閃避 | 獨立人聲+BGM，側鏈壓低配樂、限幅、48kHz 雙聲道、準確樣本數 | 保留原分軌；不靜默截斷人聲；PCM 峰值/RMS 不等於聽感或真峰值認證 |
| M06 | 音效/字型 | CC0 介面/撞擊/腳步音效，OFL Noto SC/TC 字幕與標題實際渲染 | 音效時長/用途逐項檢查；字型保留 OFL/RFN，不再分發商業系統字型 |
| G01 | GPU 處理 | 配音 CUDA 13 / ONNX Runtime；翻譯 CUDA 12 / CTranslate2 `int8_float16`；`auto / cpu / cuda` | 本機 RTX 3060 已實測；GPU 初始化可能慢於 CPU；不代表所有平臺/型號已驗收 |
| G02 | 視訊記憶體/回退 | 查詢空閒視訊記憶體；配音至少 3072MiB、翻譯至少 1536MiB；自動模式顯式記錄回退 | 閾值是保守預檢，不能保證絕不 OOM；嚴格 CUDA 失敗不偽報成功；不停止其他 GPU 任務 |
| M07 | 離線交付 | 基礎素材隨應用；4 個可選模型包，清單/逐檔案雜湊、獨立程序和原生安裝 | 不建立虛擬環境，不隱式聯網；缺失或篡改的包拒絕，不借 CPU 回退繞過校驗 |

## 從零到交付

先在本地完成應用和模型包安裝。新包位置及雜湊見本輪交付記錄；公共舊 alpha.3 可繼續使用其原手冊。外層只指定一個 Skill：

```text
$agent-ffmpeg-local-editor
使用本地 GPU 配音，把提供的中文文案制作成双语字幕短片。
先展示音色和滤镜候选，确认选型后组合独立人声、背景音乐与音效。
交付可编辑工程、预览、成片和质量报告，并说明实际设备和回退情况。
```

以下 `$avk` 指向統一 Skill 的 `scripts/run.ps1`。本機登記了 CPU/GPU 模型路徑與已有 NVIDIA 庫，因此 `--device auto` 優先選 GPU；獨立安裝可顯式傳 `--pack`、`--gpu-pack`、`--cuda-library-directory`。CLI 不會替你下載依賴。

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
$aekProject = 'E:/video-work/community-ad'
& $avk version
& $avk gpu inspect
& $avk model-pack list
& $avk project init $aekProject --name 'Community ad'
& $avk materials list --kind music --query 'rpg'
& $avk materials inspect --id kenney-music-jingles-jingles-hit00
& $avk materials ingest --project $aekProject --id kenney-music-jingles-jingles-hit00 --asset-id asset_jingle
& $avk voice list --language zh
& $avk voice synthesize --project $aekProject --voice zf_001 --input 'E:/video-work/narration.txt' --device auto --asset-id asset_voice
& $avk translate subtitles --project $aekProject --from zh-Hans --to en --input 'E:/video-work/source.srt' --output exports/bilingual.srt --mode bilingual --device auto
& $avk music prepare --project $aekProject --asset-id asset_jingle --duration-seconds 12 --loop --fade-in-seconds 0.3 --fade-out-seconds 0.8 --new-asset-id asset_bed
& $avk music mix --project $aekProject --voice-asset-id asset_voice --music-asset-id asset_bed --duration-seconds 12 --music-gain-db -18 --duck --new-asset-id asset_mix
# --apply 需要明确指定未锁定/未静音的 audio 轨道。
# 素材导入后，用实际返回 ID 编写 timeline compose JSON；视频/字幕/音轨分别编辑。
& $avk validate --project $aekProject
& $avk preview frame --project $aekProject --frame 0 --height 640
& $avk render --project $aekProject --output 'E:/video-work/community-ad/renders/ad.mp4'
& $avk quality check --project $aekProject --input 'E:/video-work/community-ad/renders/ad.mp4' --require-audio
& $avk convert export --project $aekProject --target-format package --output 'E:/video-work/community-ad.aevpkg.zip'
```

示例中的文字/字幕檔案須已存在。混音時長必須覆蓋自然配音時長；若配音超過 12 秒，請延長 BGM 和成片，不截斷臺詞。檢查響應中的 `ok / status / errors / warnings / data.device / inference.provider` 和實際輸出檔案。

字幕字號/寬度按作者畫布畫素設定。`preview --height` 縮放預覽；`render --width/--height` 改變合成畫布，不是單純縮放最終畫面。建議在 `update_sequence.patch.canvas` 固定最終畫布，再按該尺寸設定文字並用預設尺寸渲染。本輪保留首次文字溢位失敗記錄，另有 8 條命令複核修正後的預覽、成片及工程往返。

## GPU 相容與取捨

| 路徑 | 模型/精度 | 執行庫 | 當前狀態 |
|---|---|---|---|
| CPU 配音 | Kokoro int8 ONNX | sherpa-onnx 2.0.0 / ORT 1.28.2 | Windows CPython 3.13 x64 實測 |
| GPU 配音 | 同源非量化 ONNX / Float32 | NVIDIA 驅動、CUDA 13、cuDNN 9；獨立 GPU 包 | RTX 3060 實測，當前僅裝置 0 |
| CPU 翻譯 | OPUS int8 | 自編譯 CTranslate2 4.8.3 + Ruy，無 MKL/cuDNN/Intel OpenMP | 雙向文字/字幕實測 |
| GPU 翻譯 | 同一 OPUS int8 權重、`int8_float16` 計算 | CUDA 12 cuBLAS；GPU 包 | RTX 3060 實測，顯式 device-index |
| AMD/Intel GPU、Apple GPU | 未整合 | 不偽用 CUDA | 透過 `auto` 選擇已驗證 CPU 路徑 |

同一非量化配音模型、同一約 6.85 秒文字：CPU 第二次生成約 4.93 秒，GPU 第二次約 0.62 秒；GPU 載入約 7.54 秒、CPU 約 4.08 秒。裝置上另有任務，結果不是基準承諾。一次 CLI 啟動包含包校驗/模型載入，不能套用約 8 倍的持續生成加速比。翻譯示例 CUDA 首次推理約 0.38 秒、再次約 0.037 秒，亦不含完整 CLI 啟動。詳見實際證據。

核心與模型許可分別列明。NVIDIA 驅動/CUDA/cuDNN 是 GPU 相容依賴，含其自身非開源許可；上游 GPU Windows 二進位制附帶的 Intel 執行庫同樣保留原許可，不包裝為“開源素材”。需要避開專有數值核心時選擇獨立 CPU Ruy 方案。普通素材處理/FFmpeg 濾鏡沒有因此自動全部 GPU 化。

## 模型包與可移動安裝

包必須與當前 CLI 內建 `model-packs.json` 的鎖定摘要相符。使用 `scripts/install_community_pack.py --archive <local.zip> --sha256 <archive-hash> --catalog <installed/site/ai_ad_editor/material_data/model-packs.json> --id <pack-id> --target <new-local-path>`。目標需不存在，父目錄需已存在；安裝在本地 staging 校驗完後原子遷移，不全域性 pip、不訪問網路。

現有目的地、ZIP 摘要不符、缺失/額外/重複檔案、路徑穿越、模型檔案改動會拒絕。`--device auto` 的 GPU 執行失敗可在尚未產出檔案時重試 CPU，響應保留失敗日誌和原因；包篡改不觸發此回退。`--device cuda` 嚴格返回失敗。缺失的依賴不會自動下載。

## 翻譯、術語與權利

支援 `en ↔ zh-Hans/zh-Hant`；簡繁在中文輸入/輸出側處理，不是獨立中英模型以外的多語服務。文字每行一段、最多 1000 段；字幕最多 1000 cue；每段最多 512 模型 token，觸及解碼上限會拒絕，避免靜默截斷。返回源文、譯文、模型摘要、分數和時碼，人工校對另行記錄。

```json
{"entries":[{"source":"background music","target":"BGM","variants":["背景音乐"]}]}
```

術語是明確的譯後替換：源詞出現且譯文有已知 variant 才替換；找不到會拒絕，不聲稱受約束解碼。真實失敗示例：`speech` 被通用模型譯成“演講”，應按影片語境改成“原聲/語音”。字幕翻譯保留時間不代表文字與發音重新對齊。

OPUS 原始歸檔許可為 CC-BY-4.0；與部分 Hugging Face card 的 Apache 標籤衝突時，包保留原始實際許可證和模型署名。Kokoro 權重 Apache-2.0；音色不是使用者上傳真人克隆。生成配音和派生混音在專案臺賬仍預設 `unverified/internal`，模型許可不自動變成客戶廣告的釋出權利。

## 真實案例與驗收

[逐項素材](COMMUNITY_MATERIAL_CATALOG.md) · [103 音色與實際試聽範圍](COMMUNITY_VOICES.md) · [本地包與安裝](COMMUNITY_LOCAL_DELIVERY.md) · [原始核驗](../../docs/validation/evidence/community-materials-20261025-r1/cpu/verification.json) · [GPU 核驗](../../docs/validation/evidence/community-materials-20261025-r1/gpu/verification.json)。

實際案例保留 12 秒、360×640、30fps、360 幀、獨立音軌、SC 字幕與 TC 標題、濾鏡、音效和 `.aevpkg.zip` 往返工程。原始配音/混音檔案在本地交付目錄；未確認釋出權利的聲音不隨公共 README 再分發。公共頁面展示由已驗證開源資源製作的無配音演示和 GIF，完整本地成片及機器響應另見實測路徑。

CPU 專項 46 條實際命令、GPU 專項 15 條實際命令；不與歷史迴歸合併計數。字幕逆序和重疊、毫秒時間、三音色、UTF-8 文字/語速、缺失/篡改/額外模型檔案與嚴格 CUDA/CPU 回退分別檢查。人類聽審和語義接受尚未完成，亦未實現完整剪映等價。
