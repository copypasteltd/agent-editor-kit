# 4K 文字、覆盖率复用与分块浮点合成

CLI **0.1.23 / alpha.4-local.21** 将字形栅格与颜色计算分开。现有独立标题、内嵌字幕、纯文本 SRT、逐词高亮、打字机、原作者时钟和倒放边界继续使用同一工程格式。明确选择 `float32-native-v1` 并登记本地字体；不需要新增文字开关。

English: native FFmpeg now emits byte coverage only. Ordered component colors use tiled Float64 source-over with Float32 component boundaries. The default workspace admits 3840×2160 text. Equal shaped prefixes and paragraph geometry reuse masks without quantizing author time. Text remains on CPU; glyph coverage remains eight bits. Read actual installed capabilities and preview cue/word boundaries before rendering.

繁體：原生 FFmpeg 只輸出字形覆蓋率；底框、陰影、描邊、填色採分塊浮點合成。預設工作區可接受 3840×2160 字層，相同前綴及段落幾何可重用快取，作者時鐘不取整。字形覆蓋率仍為 8 位元，文字仍使用 CPU。先檢查實際能力並預覽字幕／逐詞邊界，再輸出影片。

## 實際案例與選用邊界

[C31 可編輯剪輯](CASES.md#c31-float-text-coverage)包含 6 秒／72 影格、中文 SRT、逐詞／打字機、旋轉、父倒放及真實來源句柄與關聯音軌。已透過註冊 Skill 完成預覽、編碼、取消／恢復、佇列及工程包匯入；匯入後三處預覽的解碼像素與原工程相同。[完整執行記錄](../validation/evidence/float-text-coverage-20261026-r1/case-r1/verification.json)。

[C32 實際 4K 標題](CASES.md#c32-4k-text)使用自製文字與純色背景，三字層、淡入及逐詞打字機，輸出 3840×2160／4fps／2秒／8影格。CPU 算繪呼叫實際耗時 **692.895 秒**；可用於離線輸出，仍需改善速度。該次產生 80 張原生覆蓋率、32 次快取命中，全部 8 影格完成解碼、質檢與可編輯包匯出。[原始證據](../validation/evidence/float-text-coverage-20261026-r1/4k-r2/verification.json) · [MP4](../assets/float-text-coverage-20261026-4k-r2/4k-native-text.mp4) · [工程包](../assets/float-text-coverage-20261026-4k-r2/editable-4k-text.aevpkg.zip)。

![Actual 4K title delivery, reduced preview](../assets/float-text-coverage-20261026-4k-r2/4k-native-text.gif)

English: the actual CPU render call took 692.895 seconds for eight 4K frames. This is an offline text delivery with authored solid backgrounds. Review the separate clock/PCM checks and static observations; natural footage, realtime speed and GPU text have their own open acceptance conditions.

## 使用流程

1. 使用唯一入口 `$agent-ffmpeg-local-editor`，查詢 `version`、`capabilities`、`schema show`。`subtitles.float32_native` 必須包含 `native_byte_component_coverage_and_tiled_Float64_source_over` 及 `4K_text_with_explicit_workspace_admission`。
2. 依 [文字作者格式](FLOAT_TEXT.md) 登記本地字型並編輯文字／字幕軌。來源媒體、工作域、輸出域必須明確；字幕與字型不當作像素來源。保留合法來源和字型授權。
3. 設定畫布 `settings.canvas.width=3840`、`height=2160`，按實際畫布選擇字級、位置與安全區。`settings.sequence_sampling.max_working_bytes` 控制共享工作區准入；上限 768MiB，預設快取上限會隨小工作區調整。該欄位不是整個程序 RAM/VRAM 硬上限。
4. `timeline compose` 後執行 `validate`、`preview frame`，檢查作者時鐘、字素前綴、活動詞、父倒放與字幕半開邊界。用實際客戶素材確認排版、明暗與可讀性。
5. `render`、`quality check` 並匯出可編輯工程包。需要取消／恢復或佇列時沿用原命令；快取不是完整電影預渲染，也不取代編碼器或權利檢查。

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk capabilities
& $avk timeline compose --project 'E:/video-work/my-ad' --input 'E:/video-work/changes.json'
& $avk validate --project 'E:/video-work/my-ad'
& $avk preview frame --project 'E:/video-work/my-ad' --frame 24
& $avk render --project 'E:/video-work/my-ad' --output 'E:/video-work/my-ad/renders/ad.mp4'
& $avk quality check --project 'E:/video-work/my-ad' --input 'E:/video-work/my-ad/renders/ad.mp4'
```

上述工程、素材和 changes.json 必須先存在；完整字層 JSON、SRT 時鐘欄位與動畫參數見 [FLOAT_TEXT](FLOAT_TEXT.md)。原作者格式及明確拒絕項不變。

## 精度和快取

原生覆蓋率直接使用 `gray` 位元組平面，256 個碼值全部檢查。作者顏色由本機原生解析器讀取，再從 sRGB 轉入明確線性工作域；每個底框、陰影、描邊、填色的 alpha 只與覆蓋率相乘一次。CPU 以最多 16384 像素的分塊執行 Float64 source-over，各元件邊界存為 Float32。媒體原像素不進入字形程序。

一般與活動文字保留兩份完整段落，以原生度量建立二值選區，避免同一個詞重畫。字形快取按實際文字位元組、字型路徑及原生幾何圖內容尋址。不同作者時間若得到相同前綴或靜態形狀，可共用覆蓋率；動態位置、不同文字或幾何不會混用。淡入／淡出透明度在完整段落上套用一次，不必重做字形。

既有完整 Float32 表面 LRU 和新的字節覆蓋率 LRU 各有獨立上限；預設各 64MiB，實際上限取請求值與工作區四分之一的較小值。命中覆蓋率不可寫，對外表面為獨立副本。字素和時間決策仍使用原作者時鐘，沒有 CFR 文字電影或納秒取整。

## 資源和診斷

單次准入估算為四張 Float32 RGBA 表面、每像素 8 位元組的原生／暫存空間、兩個快取上限、分塊暫存及固定開銷。3840×2160、預設快取時約 705.5MiB，可在 768MiB 上限內執行。這是分配估算，不能當作作業系統峰值 RSS 保證；長片、複合工程和並行程序仍須實測。

渲染證據分別記錄 `native_snapshots`（邏輯文字快照）、`native_coverage_rasters`（實際原生字節栅格）、`coverage_cache_hits`、`coverage_cached_bytes`、每張圖的 SHA、`estimated_working_bytes` 和顏色／時間契約。邏輯快照數不等於原生啟動數。小預算會縮小快取，仍不足時在原生程序啟動前拒絕。

僅支援純文字 SRT、明確本地字型及既有動畫。富 ASS/SSA/VTT、複雜 Bidi／內部塑形簇、GPU 字形合成、自然視聽、HDR/ICC、即時及完整剪映等價仍開放。較大畫布、模型和外部工作不因這次文字改進而自動通過資源驗收。
