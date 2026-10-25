# 統一 Skill：一個入口、17 項能力

<!-- community-current -->

**Current local / 当前本机 / 目前本機：CLI 0.1.16 / alpha.4-local.14 / r16 kit.** One registered Skill / 17 modules; [r16 kit](agent-editor-kit-community-unified-skill-r16.zip). Six reusable motion paths and native animation capture are now installed, alongside editable ad variants, semantic runtime migration, GPU voice/translation, subtitle dubbing and 359 resources.

[Motion workflow + previews](../product/MOTION_PACKS.md) · [Current installation](../product/COMMUNITY_LOCAL_DELIVERY.md) · [All 38 original goals](../product/GOAL_GAPS_20261025.md). Public alpha.3 assets retain their original version.

<!-- /community-current -->

## alpha.3 / r1 歷史流程（以下原文保留）

[简体中文](UNIFIED_SKILL.md) · [English](UNIFIED_SKILL.en.md) · [完整模塊](../product/SKILLS.zh-TW.md)

外層只需指定 **`$agent-ffmpeg-local-editor`**。它根據實際任務讀取內部模塊，不再要求分別調用 timeline、quality、local-models 等 16 個專用 Skill。全部模塊與上游輔助腳本、模板、來源和許可都包含在該 Skill 目錄內。

本次改變 Skill 的組織和註冊方式。運行內核仍固定為已公開的 **v0.1.0-alpha.3 / CLI 0.1.2 / 500 套濾鏡**；未發布的素材、翻譯和配音候選功能不計入該安裝版。原 alpha.3 Release 的 17 Skill 下載包、標籤和摘要保留不變。

## 當前這臺電腦

本倉庫已安裝運行包。更新倉庫後執行以下命令即可遷移註冊，無需再次安裝內核：

```powershell
Set-Location 'E:/dev/sandbox/AI广告剪辑'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
```

註冊器先檢查內核回執、啟動器摘要和統一 Skill 的完整文件清單，再保留總入口、移除本專案原 16 個專用入口的目錄聯接。原始專用 Skill 文件仍保留在倉庫用於歷史復現；不刪除源文件、不清理其他專案或 `video-cut-*` 註冊。遇到同名無關目錄、不同目標的聯接或已編輯的舊 Skill 時，在變更註冊前退出並保留現狀。註冊回執另存於 `local/agent-ffmpeg/registrations/`，不把機器路徑寫回可移植清單。

遷移後重新打開會話，讓客戶端刷新發現列表。當前已打開會話可能仍顯示緩存中的舊入口。

## 另一臺電腦 / 新目錄安裝

需要原生 Windows x64、已有 CPython 3.13 x64、PATH 中的 FFmpeg/ffprobe。下載：

1. [新的統一 Skill kit](https://github.com/copypasteltd/agent-editor-kit/raw/refs/heads/main/docs/skills/agent-editor-kit-unified-skill-r1.zip)。
2. [alpha.3 運行 ZIP](https://github.com/copypasteltd/agent-editor-kit/releases/download/v0.1.0-alpha.3/agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip)。
3. 如需客戶濾鏡選型，再下載 [gallery ZIP](https://github.com/copypasteltd/agent-editor-kit/releases/download/v0.1.0-alpha.3/agent-editor-kit-v0.1.0-alpha.3-gallery.zip)。

```powershell
$aekPython = 'C:/Python313/python.exe'
$aekHome = 'E:/tools/agent-editor-kit-unified'
Expand-Archive -LiteralPath 'E:/Downloads/agent-editor-kit-unified-skill-r1.zip' -DestinationPath $aekHome
Set-Location $aekHome
& $aekPython -I -B -X utf8 ./install.py --archive 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
$avk = Join-Path $aekHome 'skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $aekPython -I -B -X utf8 ./run-example.py --output 'E:/video-work/unified-first-demo'
```

安裝保留已有目標目錄；請選一個新的工具目錄。若當前 Codex 已有指向另一工具目錄的同名 Skill，註冊器會保護它並報錯。可以繼續使用已有倉庫的註冊入口，或先用 `-SkillsDirectory 'E:/video-work/aek-discovery'` 檢查獨立發現目錄；不要直接覆蓋無關目錄。

運行包與 Skill kit 的 SHA-256 分別見原 Release 的 SHA256SUMS.txt 與本目錄 [包摘要](unified-skill-package.json)。安裝器會實際校驗內核運行包和 kit 內的逐文件摘要。雜湊校驗並不等於發布者簽名。

## 調用示例

```text
$agent-ffmpeg-local-editor 用 E:/media/product.mp4 制作 15 秒竖屏广告。
先检查能力、素材和音轨，展示暖色与黑白滤镜候选；客户选定后生成预览、成片、质检和可编辑工程包。

$agent-ffmpeg-local-editor 给 clip_1 加可编辑推近与关键帧，预览首中末帧。

$agent-ffmpeg-local-editor 把 E:/media/interview.mp4 按提供的字幕拆成三条短片，保留原声音轨。

$agent-ffmpeg-local-editor 分析本地投放数据，计算 ROAS、CPA 并提出下一轮创意脚本。
```

你可以直接點名“時間線”“配音適配器”“濾鏡選型”“質檢”等任務，無需指定模塊文件名或另一個 Skill。入口按需讀取對應參考；合並不意味著每次加載全部說明，也不會啟動子 Agent。模塊表、來源和依賴見 [Skill 正文](../../skills/agent-ffmpeg-local-editor/SKILL.md) 和 [17 項詳細模塊](../product/SKILLS.zh-TW.md)。

隨包示例產出 6 秒、360×640、30 fps、180 影格的影片及音軌、可編輯工程和工程包。功能鏈路演示、自動解碼檢查、自然畫質和人工聽審分別記錄；Skill 合並不會補齊未驗收的剪映對標功能。

## 結構與維護

```text
skills/agent-ffmpeg-local-editor/
  SKILL.md                       # 唯一被注册的入口，共同流程和路由
  agents/openai.yaml             # 客户端显示信息
  scripts/run.ps1, run.py        # 已安装内核的固定入口
  scripts/look_gallery.py        # 真实滤镜候选板
  references/runtime.md         # 共享运行约定
  references/looks.md            # 滤镜应用语义
  references/client-look-selection.md
  references/modules/*/module.md # 17 项模块，按需读取
  references/modules/*/references/upstream/ # 对应来源、许可与辅助资源
```

註冊清單格式為 `agent-ffmpeg-local-skills-v2`：`skill_count=1`，`module_count=17`。每個模塊有穩定 K01–K17 編號和對應舊名稱映射。後續擴展優先增加內部參考，不再註冊新的 `$agent-ffmpeg-local-*` 專用入口。原始拆分源的歸檔和重建腳本供維護者使用，正式打包只取清單中的一個入口。

[本輪實際核驗與遷移回執](../validation/evidence/unified-skill-20261024-r1/) · [原 alpha.3 Release](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v0.1.0-alpha.3)
