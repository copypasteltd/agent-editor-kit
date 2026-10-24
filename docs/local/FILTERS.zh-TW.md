# 濾鏡功能 README：500 套內置風格

[簡體中文](FILTERS.md) · [繁體中文](FILTERS.zh-TW.md) · [English](FILTERS.en.md)

當前安裝版為 **v0.1.0-alpha.3 / CLI 0.1.2 / 目錄 2.0.0**。500 套均隨包離線安裝，Agent 可以檢索、讀取實際效果、預覽並應用到片段或全局。原 100 套的 ID 和 LUT 位元組保持兼容。

## 功能與使用邏輯

| # | 功能 | 實際行為 |
|---|---|---|
| P01 | 命名與編號 | 001–100 保留 sp-/t3-；101–500 使用 nt-/fl-；命令使用穩定 ID |
| P02 | 搜索 | 簡體/繁體名稱、英文、ID、簡體/英文描述、許可及分類 |
| P03 | inspect | 每套的實際灰階/膚色/RGB 作用、場景建議、試用強度、網格、作者、許可、鎖定來源與雜湊 |
| P04 | preview | 使用內置合成卡或本地 SDR 圖片輸出新 PNG；支持靜態 0–1 強度，保護已有文件 |
| P05 | apply | 顯式 --clip-id 或 --global；預設替換同作用域的內置預設，保留手工效果；--append 才疊加 |
| P06 | 事務與證據 | dry-run 不寫文件；實際應用復制 LUT/許可/來源，登記臺賬、快照、冪等重試；修改過的專案資源拒絕覆蓋 |
| P07 | 舊版兼容 | 識別 alpha.2 預設標記；精確匹配舊證據時保留原位元組；專案包往返保留穩定 LUT ID 和資源許可 |
| P08 | 許可區分 | MIT 100、CC BY-SA 267、CC0 133；按每套許可復制署名、變更與再分發義務 |

使用順序：**list 選候選 → inspect 讀詳情和許可 → preview 比較適合素材的強度 → dry-run 確認作用域 → apply → render → 解碼核驗**。

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk look list --query '黑白'
& $avk look list --query 'CC0-1.0'
& $avk look inspect --id fl-0000001-action-magenta-01
& $avk look preview --id fl-0000001-action-magenta-01 --output 'E:/video-work/magenta-preview.png' --strength 0.65
& $avk look apply --project 'E:/video-work/my-ad' --id fl-0000001-action-magenta-01 --global --strength 0.65 --dry-run
& $avk look apply --project 'E:/video-work/my-ad' --id fl-0000001-action-magenta-01 --global --strength 0.65
```

## 全部命名與詳細說明

[500 套編號及實際作用總表](LOOK_PRESETS.zh-TW.md)。每套有原名、來源前綴、唯一 ID 和逐項說明；新名稱帶實測中灰偏向/明暗/跨度提示。

| 編號 | 逐項詳情 |
|---|---|
| 001–100 | [保留的原始風格](look-profiles/001-100.zh-TW.md) |
| 101–200 | [新增風格與原始曲線變體](look-profiles/101-200.zh-TW.md) |
| 201–300 | [新增風格與原始曲線變體](look-profiles/201-300.zh-TW.md) |
| 301–400 | [新增膠片與社區創意](look-profiles/301-400.zh-TW.md) |
| 401–500 | [新增社區創意色彩](look-profiles/401-500.zh-TW.md) |

每份詳情包含 7 個灰階、3 個膚色和紅綠藍 3 個色塊的輸入/輸出，Y′ 碼值、中段跨度、使用建議、試用強度、注意點、作者/來源/許可、轉換誤差、LUT 摘要和真實 PNG/MP4。

**500 指不同的實際數值變換，含同系列上游曲線變體，不代表 500 個獨立風格家族。** 上游的 +/− 後綴寫進 ID；不將同一 LUT 的強度或格式副本計為新預設。全部通過共同 17³ 色網格簽名與參考預覽去重。

## 類別與來源

| 類別 | 數量 |
|---|---:|
| `cinema` | 39 |
| `creative` | 135 |
| `landscape` | 10 |
| `infrared` | 2 |
| `lomography` | 5 |
| `film-bw` | 37 |
| `film-negative` | 112 |
| `film-slide` | 41 |
| `instant-consumer` | 54 |
| `instant-pro` | 65 |

類別沿用來源分組，拍立得與負片組也含黑白變體，以每套實測說明為準。來源：Striped Purple 49、t3mujinpack 51、Natron 267、FreshLUTs 133。Natron 原始 Hald 轉換為 33³；原有 CUBE 與新增 FreshLUTs CUBE 保留原網格。目錄記錄逐項取樣誤差和輸入假設。FreshLUTs 按明確的上傳者 Rec.709 標籤選擇，未將未知、Log 或 HLG 標籤改判為 SDR；這不是獨立相機校準。`fl-0000228-science-fiction-for-flog` 的標籤為 Rec.709，但標題提到 FLog，輸入域存在歧義，僅作為已準備 SDR 的實驗創意比較，不作為已驗證的 FLog 轉換。

CC BY-SA LUT 及改編預覽需要保留作者/來源、標明轉換並按相同或兼容許可再分發。軟體本體 MIT 不能代替資源許可。[完整通知與鎖定來源](../releases/v0.1.0-alpha.3/THIRD_PARTY.md)。

## 實際輸出與核驗

![原影片與新增風格實際成片](../assets/look500-20261024-r1/motion-comparison.gif)

[原影片](../assets/look500-20261024-r1/original.mp4) · [500 套實際預覽總覽](../assets/look500-20261024-r1/contact-sheet.jpg) · [逐項 PNG/MP4](LOOK_PRESETS.zh-TW.md) · [當輪核驗及失敗修復](../validation/LOOK500_20261024.md)。

## 色彩與效果範圍

LUT 只執行逐像素色彩映射；不產生顆粒、光暈、暗角、空間霧、美顏或 AI 特效。場景/強度是試片建議；合成色塊不代表膚色保護或自然素材驗收。Y′ 和跨度是編碼 RGB 的對照量，不是曝光、線性亮度或主觀評分。

`look apply` 用於預設 FFmpeg 的 SDR 管線；Float32/Log/HDR 顯式拒絕。先按獨立色彩契約轉換素材再選風格。靜態強度混合的是編碼 RGB，不是線性光。

原有 46 個效果處理算子與 500 套風格是兩種計數。用戶仍可用 `lut register` 登記本地 `.cube/.3dl/.csp/.dat`；預設路徑的部分強度以完整 3D CUBE 為準，非 CUBE 只記錄有限元資料。顯式 Float32 路徑另支持完整 CUBE 的 1D/3D/1D shaper，必須聲明信號、域與預算；兩條路徑能力不同。

## 自定義 LUT 與底層效果

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk effects list
& $avk effects inspect --name lut3d
& $avk lut register --help
& $avk lut register --project 'E:/video-work/my-project' --input 'E:/looks/cinematic.cube' --name 'My look'
```

登記後，把返回的 `lut_id` 加入時間線的 LUT 效果，再預覽、渲染；單純登記文件不會改變畫面。自帶素材需要補全實際許可和來源。底層動態強度使用編碼 8-bit RGB 混合；核對 `effects inspect --name lut3d`、`effects.numeric_effect_automation` 和所選渲染路徑。登記器部分歷史限制字段只描述靜態處理，不能據此推斷所有路徑的能力。

顯式 `float32-native-v1` 讀取完整 CUBE 的 1D、3D 或 shaper+3D，不讀取 `.3dl/.csp/.dat`；預設 FFmpeg 路徑不會自動獲得 1D 支持。剪映專有濾鏡包與任意第三方插件不屬於標準 LUT 的兼容範圍。

[歷史 Float32/shaper 安裝版實測](../validation/evidence/float-shaper-20261023-lab/installed-r1/verification.json) · [歷史真實對照 GIF](../assets/float-shaper-20261023-installed-r1/formal-comparison.gif)。這些結果不計入本輪 500 套核驗。

[安裝與 Skill](INSTALLATION.md) · [新版使用手冊](../releases/v0.1.0-alpha.3/USAGE.md) · [歷史 100 套測量](LOOK_PRESET_DETAILS.md)。
