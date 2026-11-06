# agent editor kit / CLI0.1.66

**未發行手冊草稿。** CLI66應用尚未建置，安裝摘要暫用明確佔位符；以下命令尚未作為新版完整流程驗收。發行時由實際候選清單填入摘要。

原生Windows CPython3.13 x64應用；唯一公開入口為 `$agent-ffmpeg-local-editor`，包含17個內部模組。應用ZIP不包含Python、FFmpeg／ffprobe、驅動、模型權重或完整音樂執行庫。先準備本機依賴；不使用Docker、WSL或虛擬環境。

1. 下載本次Release的兩個ZIP、SHA256SUMS.txt及本語言快速開始至同一目錄。將以下路徑改為實際路徑。逐項比較計算摘要與清單，全部相符後解壓縮至新目錄；後續安裝器還會核對應用內部清單。

```powershell
$downloads = "E:/video-tools/downloads"
$bundle = "E:/video-tools/application-bundle"
$kit = "E:/video-tools/skill-kit"
Get-Content -LiteralPath "$downloads/SHA256SUMS.txt"
Get-FileHash -LiteralPath "$downloads/agent-editor-kit-v0.1.0-alpha.4-cp313-win_amd64.zip" -Algorithm SHA256
Get-FileHash -LiteralPath "$downloads/agent-editor-kit-community-unified-skill-r59.zip" -Algorithm SHA256
Expand-Archive -LiteralPath "$downloads/agent-editor-kit-v0.1.0-alpha.4-cp313-win_amd64.zip" -DestinationPath $bundle
Expand-Archive -LiteralPath "$downloads/agent-editor-kit-community-unified-skill-r59.zip" -DestinationPath $kit
```

2. 離線安裝應用。目標目錄必須是新路徑。此步驟不下載模型；模型尚未準備時，可先透過安裝版入口執行version／doctor及基礎剪輯命令。

```powershell
$python = "C:/Python313/python.exe"
$installed = "E:/video-tools/application-installed"
& $python -E -B -X utf8 "$bundle/install.py" --bundle $bundle --target $installed --manifest-sha256 "sha256:BUILD_MANIFEST_REQUIRED"
& $python -I -S -B -X utf8 "$installed/run.py" version
& $python -I -S -B -X utf8 "$installed/run.py" doctor
```

3. 設定基礎剪輯模式，將統一Skill綁定到上述安裝目錄。時間線、濾鏡、字幕、預覽與算圖可直接使用；配音、翻譯與語意模型按下一段另行設定。設定器先備份舊設定，再建立基礎綁定並清除舊機器模型路徑。

```powershell
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --base-only
```

選用模型：需要配音／翻譯時，先準備已核對的 `kokoro-zh-en-int8` 與 `opus-zh-en-cpu-int8` 兩個CPU套件；`kokoro-zh-en-cuda13` 與 `opus-zh-en-cuda12-int8` 為選用GPU套件。PACKS指向包含這四種解壓目錄的父目錄；設定器要求兩個CPU套件，逐一驗證後才寫入模型綁定。本次兩個ZIP未包含這些模型套件；來源、授權、預期摘要與重現工具見下方連結。

[Model catalog and pinned manifests](https://github.com/copypasteltd/agent-editor-kit/blob/main/product/src/ai_ad_editor/material_data/model-packs.json) · [CPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_model_pack.py) · [GPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_gpu_packs.py) · [Offline pack installer](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/install_community_pack.py)

```powershell
$packs = "E:/video-tools/model-packs"
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --packs $packs
```

若使用GPU包，將設定命令替換為以下形式，並填入對應的實際DLL目錄。配音與翻譯的CUDA版本要求不同；不要混用兩個目錄。後續使用 `--device auto` 優先選擇設定的GPU，並檢查回傳的實際裝置／provider及CPU回落說明。

```powershell
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --packs $packs --voice-cuda-lib "E:/video-tools/cuda13/bin" --translation-cuda-lib "E:/video-tools/cuda12/bin"
```

4. 註冊唯一Skill並檢查實際安裝版本。已有同名入口且指向其他位置時，註冊器會保留並拒絕替換；升級請先閱讀隨包交付說明，不手動刪除不明目錄。Agent外層只需指定 `$agent-ffmpeg-local-editor`。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$kit/register-agent-ffmpeg-local-skills.ps1"
$entry = "$kit/skills/agent-ffmpeg-local-editor/scripts/run.ps1"
& $entry version
& $entry doctor
& $entry capabilities
& $entry model-pack list
& $entry gpu inspect
```

5. 建立專案並匯入自己的授權素材。以下影片、圖片、字幕、配音文字和changes.json必須實際存在。讀取匯入回傳的 `data.asset.id`，再依schema及說明編寫changes.json；不能照抄舊案例的隨機ID。影片與音訊軌須分別編排，先預覽實際濾鏡候選並記錄客戶選擇，再合成時間線。

```powershell
$aekProject = "E:/video-work/my-ad"
& $entry project init $aekProject --name "My ad"
& $entry media ingest --project $aekProject --input "E:/media/product.mp4"
& $entry schema show
& $entry timeline compose --help
& $entry look list --query "Kodak"
& $entry look inspect --id t3-kodak-gold-200
& $entry look preview --id t3-kodak-gold-200 --input "E:/media/still.png" --output "$aekProject/exports/film-preview.png" --strength 0.65
& $entry timeline compose --project $aekProject --input "E:/video-work/changes.json"
& $entry look apply --project $aekProject --id t3-kodak-gold-200 --global --strength 0.65 --dry-run
& $entry look apply --project $aekProject --id t3-kodak-gold-200 --global --strength 0.65
```

可選配音／翻譯範例會實際執行模型，須先準備輸入檔案、模型包與設定，並使用新的asset ID。完整音訊、發音、翻譯語意與時長仍須複核。生成後用實際音訊資產ID編寫voice-changes.json，將聲音明確編入音軌，再執行以下最後一條compose；翻譯字幕也須依目標軌道編排。

```powershell
& $entry voice list
& $entry voice synthesize --project $aekProject --voice zf_001 --input "E:/media/narration.txt" --device auto --asset-id asset_voice
& $entry translate subtitles --project $aekProject --from zh-Hans --to en --input "E:/media/captions.srt" --output exports/bilingual.srt --mode bilingual --device auto
& $entry timeline compose --project $aekProject --input "E:/video-work/voice-changes.json"
```

6. 驗證、預覽、算圖並檢查實際成片，再匯出可編輯專案包。匯入使用新的目標目錄；重新算圖後分別檢查畫面、完整音軌、時鐘與配方。JSON的ok／status／errors／warnings／artifacts與程序結束碼需要同時檢查，品質檢查不能代替完整播放及聽審。

```powershell
& $entry validate --project $aekProject
& $entry preview frame --project $aekProject --frame 0
& $entry render --project $aekProject --output "$aekProject/renders/ad.mp4"
& $entry quality check --project $aekProject --input "$aekProject/renders/ad.mp4"
& $entry convert export --project $aekProject --target-format package --output "$aekProject/exports/ad.aevpkg.zip"
& $entry convert import --input "$aekProject/exports/ad.aevpkg.zip" --output "E:/video-work/restored-ad"
& $entry render --project "E:/video-work/restored-ad" --output "E:/video-work/restored-ad/renders/replay.mp4"
& $entry rights check --project $aekProject
```

神經音樂是額外能力，需要明確登記既有本機適配器、原生執行庫與權重；上述四包不能替代音樂模型。先閱讀[神經音樂說明](../../../../product/NEURAL_MUSIC_GENERATION.md)。一般譜面合成、循環修復與神經生曲的含義不同。

```powershell
& $entry music generate --help
& $entry delivery --help
```

[Skill詳情與17模組](../../../../../skills/agent-ffmpeg-local-editor/SKILL.md) · [濾鏡客戶選型](../../../../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [配音／翻譯／音訊](../../../../../skills/agent-ffmpeg-local-editor/references/community-materials.md) · [升級、恢復及回滾](../../../../product/DELIVERY_CONTROLLER.md)

發佈成片前補充素材／模型／聲音用途的權利證據，並執行rights check。render的--publish僅執行本機權利門檻，不上傳平台。模型生成內容仍須逐項審查；本包不附未審核模型音訊。同機新目錄驗收不等於乾淨主機或跨機器通過，完整剪映等價及原G01—G38條件繼續開放。

`v0.1.0-alpha.4-local.64` / CLI`0.1.66`
