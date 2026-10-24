# agent editor kit：下載、安裝與首次成片

[繁體中文](QUICKSTART.zh-TW.md) · [English](QUICKSTART.en.md) · [發行下載](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v0.1.0-alpha.3) · [完整功能](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/README.md)

本版是 **v0.1.0-alpha.3 預發布版 / CLI 0.1.2 / 500 風格 / 17 個 Skill**，面向 Agent 的原生 Windows 本地剪輯。完整剪映功能及自然視聽品質仍是開發目標；當前支持範圍見功能手冊。

## 1. 準備環境與下載

需要已有 **Windows x64、CPython 3.13 x64、FFmpeg 和 ffprobe**。將 FFmpeg/ffprobe 放入 PATH；以下 Python 路徑按本機實際位置修改。安裝離線執行，不使用 Docker、WSL、容器、虛擬環境或全局 pip 安裝。

從上方 Release 的 Assets 下載到例如 `E:/Downloads/`：

| 文件 | 是否需要 | 用途 |
|---|---|---|
| `agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip` | 必需 | 可安裝應用和 8 個固定 wheel；無需再下載分卷 |
| `agent-editor-kit-v0.1.0-alpha.3-agent-kit.zip` | 必需 | 安裝入口、17 個 Skill、註冊腳本、三語指南、可執行示例與 CC0 輸入素材 |
| `SHA256SUMS.txt` | 建議核對 | 對照下載文件的 SHA-256；安裝入口另行強制核對運行包 |
| `agent-editor-kit-v0.1.0-alpha.3-gallery.zip` | 選型時需要 | N002 原圖、500 套真實濾鏡樣例、離線選型頁、許可與候選對照板資源 |

基礎包不包含 Python、FFmpeg、Node/Chromium、模型權重或 GPU 驅動。基礎剪輯和下面示例不需要模型或 Node；轉寫、配音、摳像、修復等按對應適配器另行準備已有本地依賴。

## 2. 解壓 Agent kit 並安裝運行包

選擇新的工具目錄。保留運行 ZIP 原樣，由安裝腳本校驗和解包：

```powershell
$avkPython = 'C:/Python313/python.exe'
$avkHome = 'E:/tools/agent-editor-kit-alpha3'
$avkArchive = 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip'
Expand-Archive -LiteralPath 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-agent-kit.zip' -DestinationPath $avkHome
Set-Location $avkHome
& $avkPython -I -B -X utf8 ./install.py --archive $avkArchive
```

成功輸出 JSON 的 `ok` 為 `true`。應用位於 `$avkHome/local/agent-ffmpeg/v0.1.0-alpha.3/installed/`，綁定文件位於 `$avkHome/local/agent-ffmpeg/runtime.json`。已有目錄不會被覆蓋；重復安裝請沿用原入口或選擇新的工具目錄。

## 3. 註冊 Skill 並檢查真實能力

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
$avk = Join-Path $avkHome 'skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk capabilities
& $avk schema show
```

註冊腳本把 17 個 `$agent-ffmpeg-local-*` 目錄聯接到 Codex 的 Skills 發現目錄；正文仍在工具目錄。若存在指向其他目錄的同名 Skill，會保留並報錯，不強行覆蓋。已使用倉庫本地版的本機用戶可以繼續沿用原入口，無需重復註冊。

註冊後，若當前客戶端尚未列出新 Skill，可重新打開會話使其重新發現。在 Agent 中調用：

```text
$agent-ffmpeg-local-editor 用 E:/media/product.mp4 制作一条 15 秒竖屏广告。
先读取素材和实际能力，生成可编辑时间线与预览，再渲染、质检和导出工程包。
需要保留原声时显式添加音轨；为滤镜提供实际候选图并记录最终 ID、强度和作用范围。
```

## 4. 一條命令跑通首次成片

不準備額外素材也可以運行。示例使用隨包 CC0 虛構產品圖片與合成脈沖音，完成導入、時間線、運鏡、0.65 強度濾鏡、顯式音軌、預覽、發布權利檢查、實際渲染、質檢和工程包往返：

```powershell
& $avkPython -I -B -X utf8 ./run-example.py --output 'E:/video-work/aek-first-demo'
```

輸出目錄必須尚不存在。主要產物：

| 路徑（相對示例輸出目錄） | 內容 |
|---|---|
| `project/project.json` | 可繼續編輯的工程 |
| `project/renders/demo.mp4` | 360×640、30 fps、6 秒、180 影格的實際成片及音軌 |
| `demo.aevpkg.zip` | 可導入的工程與引用素材包 |
| `restored/` | 從工程包恢復並驗證的工程 |
| `commands.json`、`logs/` | 每次真實 CLI 調用、響應、錯誤和耗時 |
| `verification.json`、`probe.json` | 實際編碼與完整解碼核對結果 |

示例是安裝與功能鏈路演示，不是自然廣告畫質、音樂聽感或完整剪映等價驗收。

## 5. 為客戶展示 500 套濾鏡

將可選圖冊 ZIP 解壓到同一個 `$avkHome`：

```powershell
Expand-Archive -LiteralPath 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-gallery.zip' -DestinationPath $avkHome
Start-Process (Join-Path $avkHome 'docs/assets/looks-n002-20261024-r1/index.html')
```

在離線頁面搜索、篩選、比較原圖和效果，導出候選 JSON。Agent 也可生成一張小型對照板：

```powershell
$aekGallery = Join-Path $avkHome 'skills/agent-ffmpeg-local-editor/scripts/look_gallery.py'
& $avkPython -I -S -B -X utf8 $aekGallery --ids t3-fuji-superia-800 nt-bw-agfa-apx-100 fl-0000634-darkblue --output 'E:/video-work/client-look-options'
```

客戶確認後，在真實目標素材上再試選定強度，記錄穩定 ID、強度與片段/全局範圍後應用。圖冊樣例強度均為 1.0；LUT 的許可與母圖的使用權分別記錄。瀏覽完成後關閉不用的頁面標籤。

## 6. 使用自己的素材與手動 CLI

讀取每個命令的 `--help`；從導入響應獲取真實資產 ID，不能直接照抄其他工程的片段 ID。影片素材有聲音不代表時間線自動包含音軌。用戶素材預設需要補充真實來源和許可，才能通過本地 `render --publish` 門禁；該參數不會上傳影片。

```powershell
& $avk project init 'E:/video-work/my-ad' --name 'My ad'
& $avk media ingest --project 'E:/video-work/my-ad' --input 'E:/media/product.mp4'
& $avk timeline compose --help
& $avk look list --query '黑白'
& $avk look inspect --id t3-kodak-gold-200
& $avk render --help
& $avk quality check --help
```

後續順序為：素材導入 → 按真實 ID 編寫/應用編輯計劃 → 校驗工程 → 預覽 → 渲染 → 檢查實際編碼、音畫與權利 → 導出工程包。示例腳本包含一份可執行的編輯 JSON 生成邏輯。

[功能、服務與 Skill 全說明](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/README.md) · [已知差距](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/product/GOAL_GAPS_20261024.md) · [分卷備用安裝](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/releases/v0.1.0-alpha.3/USAGE.md)
