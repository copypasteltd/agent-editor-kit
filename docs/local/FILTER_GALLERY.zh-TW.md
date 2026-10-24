# N002 母圖 × 500 套濾鏡：實際樣例與客戶選型

[簡體中文](FILTER_GALLERY.md) · [繁體中文](FILTER_GALLERY.zh-TW.md) · [English](FILTER_GALLERY.en.md)

[Interactive gallery](../assets/looks-n002-20261024-r1/index.html) · [Filter workflow](FILTERS.zh-TW.md) · [Measured profiles](LOOK_PRESETS.zh-TW.md) · [Actual executions](../validation/evidence/looks-n002-20261024-r1/render-verification.json)

500 套均實際運行安裝版 CLI，統一使用本次用戶提供的母圖，強度 1.0、四面體插值。原圖 1672×940；原尺寸無損 WebP 的 RGB 與 CLI PNG 逐像素一致，縮略圖僅用於選擇。原圖無嵌入色彩配置，按編碼 SDR RGB 試片。

![Original and eleven actual looks](../assets/looks-n002-20261024-r1/selection-board.jpg)

## 每一套實際樣例

| # | 逐項樣例、原尺寸圖與 ID |
|---|---|
| 001–100 | [100 actual previews](filter-gallery/001-100.zh-TW.md) |
| 101–200 | [100 actual previews](filter-gallery/101-200.zh-TW.md) |
| 201–300 | [100 actual previews](filter-gallery/201-300.zh-TW.md) |
| 301–400 | [100 actual previews](filter-gallery/301-400.zh-TW.md) |
| 401–500 | [100 actual previews](filter-gallery/401-500.zh-TW.md) |

## 50 套一張的速查總覽

- [001–050](../assets/looks-n002-20261024-r1/sheets/001-050.jpg)
- [051–100](../assets/looks-n002-20261024-r1/sheets/051-100.jpg)
- [101–150](../assets/looks-n002-20261024-r1/sheets/101-150.jpg)
- [151–200](../assets/looks-n002-20261024-r1/sheets/151-200.jpg)
- [201–250](../assets/looks-n002-20261024-r1/sheets/201-250.jpg)
- [251–300](../assets/looks-n002-20261024-r1/sheets/251-300.jpg)
- [301–350](../assets/looks-n002-20261024-r1/sheets/301-350.jpg)
- [351–400](../assets/looks-n002-20261024-r1/sheets/351-400.jpg)
- [401–450](../assets/looks-n002-20261024-r1/sheets/401-450.jpg)
- [451–500](../assets/looks-n002-20261024-r1/sheets/451-500.jpg)

## Agent 向客戶展示與記錄選擇

1. 先根據需求選 3–6 套，展示原圖與實際樣例；附編號、名稱、穩定 ID、當前強度和許可。
2. 客戶可報編號/ID，或本地打開交互頁篩選、勾選並導出候選 JSON。GitHub 不執行倉庫 HTML，下載後直接打開。
3. 使用 Skill helper 導出客戶專屬對照板；100% 樣例不能冒充 0.65 強度效果。
4. 在客戶實際目標影格上以候選 ID 和真實強度運行 look preview。確認最終 ID、強度、片段/全局作用域後再 apply，保留快照。
5. 編碼成片後檢查實際輸出與 warning；本圖沒有證明所有膚色、場景、HDR 或影片時序品質。

```powershell
$aekGallery = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/look_gallery.py'
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --query '黑白' --limit 6
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --ids t3-fuji-superia-800 nt-bw-agfa-apx-100 fl-0000634-darkblue --output 'E:/video-work/client-look-options'
```

[Example board](../assets/looks-n002-20261024-r1/client-shortlist-example/board.jpg) · [Returned selection](../assets/looks-n002-20261024-r1/client-shortlist-example/selection.json) · [Skill procedure](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md)

## 來源、強度與展示邊界

母圖使用依據是本次用戶提供及明確要求展示，未標記為 MIT/CC0。濾鏡保留每項 MIT/CC0/CC BY-SA 許可、作者和變更來源。原圖權利與 LUT 權利分別記錄；[完整說明及逐項署名](../assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md)。500 是不同數值變換，包含同系列曲線變體，不等於 500 個獨立風格家族。

[Desktop screenshot](../assets/looks-n002-20261024-r1/gallery-desktop.png) · [Mobile screenshot](../assets/looks-n002-20261024-r1/gallery-mobile.png) · [Actual UI recording](../assets/looks-n002-20261024-r1/gallery-walkthrough.webm)
