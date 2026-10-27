# 當前功能模塊與服務清單

<!-- community-current -->

**CLI0.1.41 / alpha.4-local.39 / r42 kit · 1 Skill / 17 modules / 80 files.**

新增**真正本機 CUDA 神經口型同步**：使用 MuseTalk 1.5、Whisper-tiny、VAE 及 BiSeNet，讓指定圖片／影片隨獨立語音生成口型。支援25FPS人臉框關鍵影格、完整PCM保留、可重跑配方，以及分別可編輯的影片／音訊關聯片段。

[Neural lip-sync workflow and limits](LIP_SYNC.md)

<!-- /community-current -->

[README](../../README.zh-TW.md) · [Machine response](model-session-capabilities-cli-0.1.34.json) · [Module data](module-catalog.json)

| 編號 | 功能模塊 | 具體行為與輸入 → 輸出 | 入口 | 依賴/邊界 |
|---|---|---|---|---|
| F01 | Agent 調用協議 | 任務參數 → JSON 響應、退出碼、錯誤、warning、產物與 provenance；能力與 schema 可查詢。 | `version; doctor; capabilities; schema show` | Skill 組織任務，CLI 執行；沒有後臺云端 Agent 服務。 |
| F02 | 可編輯專案 | 創建/檢查 Agent Project，保存資產、序列、軌道、ticks 時鐘、輸出配置和權利引用。 | `project init/inspect` | 源媒體與專案元資料分離，移動工程後需重鏈並復核證據路徑。 |
| F03 | 事務、恢復與快照 | 中繼資料事務/快照；原生子程序樹歸屬；明確復原四軌及字幕配音持久化暫存與未提交輸出。  新增語義登記/索引/校準/檢索的受管任務。| `project snapshot/restore/migrate/recover; operation inspect` | 整棵已引用語義目錄保護；活躍/變化/未知/舊快取保留。僅已接入任務，不是模型續算；目前完整性讀取已回應逾時/取消；其他 worker/OS 阻塞 I/O 仍有邊界。 |
| F04 | 素材導入與重鏈 | 本地圖片/影片/音頻/字體 → 探測結果、穩定資產 ID、雜湊和來源記錄。 | `media ingest/relink` | 不抓取在線素材；導入不自動證明商業授權。 |
| F05 | 代理、縮略圖與波形 | 素材 → 輕量代理、圖片縮略圖、音頻波形、可核查聯系表。 | `media prepare/contact-sheet` | 聯系表是抽樣證據；不代表逐影格視覺理解。 |
| F06 | 鏡頭、靜音與高光分析 | 本地影片/音頻 → 切鏡、靜音、節拍或啟發式高光候選與時間證據。 | `media understand/highlights` | 高光是啟發式候選，語義判斷需要 Agent/已註冊適配器復核。 |
| F07 | 智能粗剪與廣告計劃 | 經檢查的靜音/文本片段或廣告 brief → 編輯計劃 → 可編輯粗剪。 | `media smart-cut; ad plan/apply` | 計劃與實際 apply 分開；不承諾自動導演效果或投放表現。 |
| F08 | 節拍剪輯與多機同步 | 節拍錨點/本地多機音軌 → 剪切或 offset/顯式 affine 時鐘及切機計劃。 | `media beat-cut/multicam` | 低置信度、覆蓋不足、非線性漂移需拒絕/顯式處理；不自動添加音軌。 |
| F09 | 多軌基礎剪輯 | 編輯 JSON → 加軌、插入、更新、拆分、刪除、時長/位置修改與畫幅設置。 | `timeline compose/edit` | 遵守軌道鎖、整數 ticks、資產時長與實際能力契約。 |
| F10 | 範圍與輸出窗口編輯 | 明確區間 → 裁切/刪除/波紋等範圍編輯，保留作者時間與源映射。 | `timeline edit` | 復雜變速與嵌套的組合需按具體契約檢查，不推斷所有組合均可用。 |
| F11 | 源句柄、滑移與滑動 | 源入出點與鄰接片段 → 可逆源編輯、源句柄轉場和剪口調整。 | `timeline edit/transition` | 源句柄不足會報錯；不以靜默復制影格替代。 |
| F12 | 磁吸、主軌與關聯音畫 | 主軌重排、原生追蹤跨剪口同步拆分、區域關聯ID及音畫附著。 | `timeline edit` | 明確同步及拆分策略；鎖、轉場端點及資源門禁；非原生追蹤跨剪口仍受限。 |
| F13 | 復合與嵌套序列 | 子序列 → 獨立畫布合成、父變換/透明度、嵌套時鐘與定格。 | `timeline compose/edit` | 獨立空間不代表獨立色彩/影格率；部分組級空間轉場未接受。 |
| F14 | 變速、倒放與定格 | 共享完整作者時鐘、逐層輸出和單次聲音；原生獨立空間進出場可保留。 | `timeline edit; render` | 跨片段轉場仍需完整上級；ripple/retime、鎖、預算和音訊後端邊界保留。 |
| F15 | 關鍵影格與緩動 | 位置、錨點、縮放、旋轉、透明度、裁切、蒙版、音量/聲像 → 逐影格動畫。 | `timeline compose; schema show` | hold/linear/ease_in/ease_out/ease_in_out/bezier；枚舉/布爾值不推斷為連續動畫。 |
| F16 | 12 套運鏡預設 | 推拉、上下左右平移、Ken Burns、旋入/旋出、淡入/淡出、shake → 可編輯關鍵影格。 | `motion list/inspect/apply` | 參數有界；是明確關鍵影格預設，不是 AI 三維相機或全部商業運鏡庫。 |
| F17 | 轉場與剪口效果 | 相鄰片段與源句柄 → 淡化、擦除、滑動、黑/白場、圓形等已聲明轉場。 | `timeline transition; capabilities` | 依算繪路徑和層級選擇；明確 Float32 已提供 F55 的轉場子集，CPU 執行，支援範圍見獨立契約。 |
| F18 | 幾何蒙版與逐影格修正 | 矩形/圓/橢圓/路徑/多邊形 → 反選、羽化、動畫、編碼蒙版與修正。 | `timeline compose; media mask-edit; quality mask` | 路徑點數和取樣受限；幾何通過不等於語義分割/身份正確。 |
| F19 | 圖層合成與混合 | 多軌視覺層 → normal/multiply/screen/overlay/difference/addition/softlight/hardlight。 | `timeline compose; capabilities` | 預設路徑主要為編碼 8-bit RGB；不宣稱線性光/HDR 合成等價。 |
| F20 | 46 個效果處理算子 | 模糊/銳化、降噪、色調、曲線、HSL、色鍵、暗角、顆粒等 → 可配置效果鏈。 | `effects list/inspect` | 可動畫參數與實際後端逐項查詢；46 算子與 500 成品 LUT 是不同統計。 |
| F21 | 500 套離線風格 | 名稱/ID/類別/許可檢索 → 詳情、圖片預覽、片段或全局應用與來源副本。 | `look list/inspect/preview/apply` | 500 個不同數值變換含同系列曲線；SDR 創意映射，不是 500 個獨立家族。 |
| F22 | 自定義 LUT 與色彩自動化 | 本地 .cube/.3dl/.csp/.dat → 登記、檢查；支持的 3D LUT 強度與色彩參數按契約動畫。 | `lut register/list/inspect; effects inspect` | 格式登記不等於所有路徑都完整解析；完整 CUBE 才有對應強度/浮點支持。 |
| F23 | 顯式 Float32 像素路徑 | 聲明輸入/工作/輸出信號、順序與預算 → 原生浮點色彩、LUT/shaper、選定空間處理和 surface。 | `render; preview; surface export/inspect` | 必須顯式選擇 float32-native-v1；能力子集，拒絕不支持項，非完整 HDR/ICC 管線。 |
| F24 | 字幕、文字與分段 | SRT/VTT/ASS/SSA/TTML 或文字 → 規范化、分段、雙語、文字層、逐字高亮和文字動畫。 | `subtitle validate/normalize/segment; timeline compose` | 字體需本地可用；復雜排版、雙向 shaping 與部分動畫/時鐘有明確近似或拒絕。 |
| F25 | 離線轉寫與字詞對齊 | 音頻 + 已有 Whisper/CTC 模型/校正文 → 轉寫、字幕、字詞時碼與 CER 評估。 | `asr adapter; subtitle transcribe/align/evaluate` | 基礎包不帶權重；activity 保留原 CTC 並通過 6 組受控詞塊門檻；自然連續語音、中文和歌詞精度仍未驗收。[流程](CTC_ACTIVITY_ALIGNMENT.md) |
| F26 | 多軌音頻與總線 | 顯式音軌 → 混音、總線、音量/聲像、靜音/solo、淡化、EQ、壓縮、降噪、響度與閃避。 | `audio extract; timeline compose; quality check` | 影片資產有聲音不代表時間線自動出聲；自動 PCM/LUFS 檢查不代替聽審。 |
| F27 | 本地語音合成 | 已有本地 flite 或登記 SoulX 權重/授權參考聲 → WAV 資產與可選音軌。 | `tts adapter/voice; tts synthesize` | flite 取決於 FFmpeg 構建且限 ASCII 英文；SoulX 需 CUDA/原生依賴，非基礎包自帶配音庫。 |
| F28 | 獨立四軌與雙軌分離 | 音訊 → drums/bass/other/vocals 四個模型預測、float WAV 與可編輯音軌；保留原雙軌和 mid/side。 | `audio separate-stems; audio separate; audio adapter` | 另供原生環境/權重；受控 CPU/GPU 實測，自然品質/聽審/模型權利仍待驗。 |
| F29 | 跟蹤、綁定與重構圖 | 模板/模型/已編碼蒙版軌跡 → 文字/貼紙錨定、裁切與主體重構圖關鍵影格。 | `media track/track-bind/reframe` | 多目標須明確對象；置信度/蒙版不等於身份保證，支持的變換與時鐘需檢查。 |
| F30 | OCR 錨點與人臉修飾 | 已有 PP-OCR/OpenSeeFace 模型 → OCR 框/文字、錨點運鏡、人臉點位與受限修飾。 | `ocr adapter/scan/anchors; face adapter/scan/retouch` | 已有 ONNX CPU 環境與權重；不是完整 UI 行為識別、美妝、瘦身或臉部生成。 |
| F31 | 人像摳像與對象分割 | 已有 RVM/SAM2 + 提示點/框 → 透明影片、對象 mask 和可編輯派生資產。 | `media adapter; media matting` | RVM 人像與 SAM2 對象分割不同；概率 mask 不是物理發絲 matte，需檢查運動/遮擋。 |
| F32 | 修復、生成編輯與擴畫 | 已有 LaMa/VACE + 蒙版/提示 → 修復或擴大畫布，保留來源與可重放 recipe。 | `media inpaint/outpaint; media adapter` | LaMa 逐影格不保證時序；VACE 需 CUDA 且僅窗口聯合；自然紋理/時序品質未普遍驗收。 |
| F33 | HTML/CSS/SVG/Canvas 動效 | 受信任本地源碼/素材/字體 → 可編輯模板控件、透明標題、逐筆描線、布局診斷與時間線合成。 | `motion html-*; motion stroke-source` | 另需已有 Node/Playwright/Chromium；非任意網頁沙箱，不自動下載瀏覽器。 |
| F34 | 參數模板與批量變體 | 本地 JSON 模板 + 類型變量 → 可編輯專案變體、批量輸入與模板快照。 | `template apply/batch` | 支持 asset/color/enum 等類型；復雜條件圖和表達式執行未實現。 |
| F35 | 素材索引與片段組復用 | 素材目錄/已編輯片段 → 檢索、重復/相似檢查、跨專案片段組與依賴閉包。 | `library index/search/duplicates/similar; fragment` | 用戶自建資源庫，未內置商業素材訂閱/正版音樂庫存。 |
| F36 | 影格、區間與緩存預覽 | 工程 + 明確影格/區間 → PNG/短影片/緩存與可驗證取樣證據。 | `preview frame/range; cache; preview cache-*` | 預覽不是完整成片核驗；色彩路徑與緩存簽名需一致。 |
| F37 | 輸出、編碼與GPU投影 | 專案 → MP4/WebM/MKV、明確OpenCL裁切/仿射/子畫布投影、編解碼探測及manifest。 | `render --projection-acceleration; render` | 原生GPU需雙精度/紋理預檢；CPU預設，其餘特效仍CPU，無即時/通用4K保證。 |
| F38 | 持久佇列、重試與取消 | 凍結專案快照 → 本地排隊、有限worker、明確重試/取消及序列化提交。 | `queue enqueue/list/inspect/run/cancel` | GPU投影策略逐作業傳遞，拒絕其 --reuse-identical 繞過探測；不是雲渲染。 |
| F39 | 成片、Scope 與 golden 核驗 | 實際編碼文件 → 音畫/影格率/畫幅/時長、響度/黑場、色彩 Scope、蒙版和 golden 差異報告。 | `quality check/scopes/mask/golden` | 自動檢查、靜態目檢、連續播放、人工聽審分別記錄；不等於商業成片品質認證。 |
| F40 | 權利臺賬與本地策略 | 素材/字體/LUT/模型/模板證據 → 依賴臺賬、變更歷史、影響/撤回與發布門禁。 | `rights; policy audit; render --publish` | --publish 只檢查本地權利，不上傳；臺賬不自動裁定版權。 |
| F41 | 專案與時間線交換 | Agent JSON/package、OTIO、Kdenlive MLT、已有合法明文草稿 → 導入/導出與損失報告。 | `convert import/export` | Exact/Approximate/Unsupported/Failed 逐項報告；明文草稿不調用剪映，不解密或下載專有資源。 |
| F42 | 管道診斷與錯誤交付 | 失敗操作 → 有界日志、diagnostic manifest、顯式導出和可復查錯誤資訊。 | `diagnostics list/show/export; operation inspect` | 失敗/拒絕不是成功渲染；包含本地路徑的診斷需按交付範圍處理。 |
| F43 | 創意、內容與投放分析 | 用戶提供的產品、受眾、參考片或投放表 → 腳本、結構、變體建議與分析。 | `ad plan/apply; advisory Skills` | 策略 Skill 不提供廣告平臺連接、自動投放、實時資料或效果保證。 |
| F44 | 內建開源素材庫 | 359 項逐項具名 BGM/短樂/音效/簡繁字型 → 查詢、檢查、權利登記與專案資產。 | `materials list/inspect/verify/ingest` | 44 BGM、85 短樂、228 音效、2 字型；逐項保留來源/許可，影片/貼紙和產業覆蓋不足。 |
| F45 | Kokoro 中英配音庫 | 文字、103 具名音色和語速 → 完整 WAV、實際時長與可編輯聲音資產。 | `voice list/synthesize; model-pack` | 可選 CPU/CUDA 包；累計至少 7 個音色實際生成，完整試聽、情緒/方言與人類聽審未驗收。 |
| F46 | 中英翻譯與雙語字幕 | 文字或普通 SRT → 中英雙向譯文、簡繁轉換、雙語 SRT 與明確術語譯後替換。 | `translate text/subtitles` | OPUS 需本地模型；保留 cue 順序/毫秒，錯譯仍保留，不能代替人工語義接受。 |
| F47 | GPU 配音與翻譯選擇 | 明確 CPU/CUDA/auto 和視訊記憶體預檢 → 實際 provider、裝置與明確回退/失敗。 | `gpu inspect; voice; translate; --device` | RTX 3060 實測；配音 CUDA 13 / 翻譯 CUDA 12、配音目前僅裝置 0，其餘濾鏡不因此 GPU 化。 |
| F48 | 配樂準備與聲音混合 | 實際音樂/人聲資產 → 擷取、迴圈、淡入淡出、明確增益與人聲閃避混音。 | `music prepare/mix` | 保留原分軌，不靜默裁人聲；不作曲、不自動修復迴圈接縫或保證畫面語義匹配。 |
| F49 | 原生擷取 | 明確視窗/螢幕/區域/攝影機/麥克風 → 有限錄製、CPU/NVENC、取消與專案資產登記。 | `capture devices/record` | 真實視窗 CPU/GPU 已驗；攝影機/麥克風、聯合音畫同步、裝置故障與長錄製未驗。 |
| F50 | 離線圖文語義檢索與條件選擇 | 本地索引、中英/參考圖、同影格正負條件、經驗校準檔案、實際預覽/來源時間及可編輯引用。 | `semantic adapter-register/index/calibrate/calibration-list/search/verify` | 專案包按需衍生路徑繫結；同機 80 條遷移決策保留，仍有 3 條已知錯誤；執行環境另備，G26/G31 開放 |
| F51 | 字幕翻譯配音聯合流程 | 普通中英 SRT、明確音色/軌道 → 譯文或保留同語種原文、完整批次 WAV、實際時窗、可編輯聲音/字幕及原子提交。 | `dub subtitles` | 同語種只初始化配音模型；保留原聲/重試/錯譯；cue 時窗不證明字詞精度、自然韻律或口型同步。 |
| F52 | 可編輯廣告分鏡與返工 | 已確認 brief/實際素材 → 多畫幅與時長的畫面/字幕/配音/源音/配樂獨立軌道；按鏡頭及變體局部改稿。 | `ad storyboard/build/revise` | 整影格分配、原素材位元組鎖、實際字型排版和完整配音時窗；不自動創造賣點或決定素材語義。 |
| F53 | 語義執行時升級 | 舊適配器/索引/校準 → 新安裝路徑的新 ID，複製向量/預覽/資料集並保留擬合及原觀察。 | `project upgrade-semantic` | 全部 19 個實作與外部依賴須位元組相同；零新模型前向，原記錄不改；內容變更拒絕並要求重建。 |
| F54 | 可復用參數運鏡 | 本地版本化 JSON / 既有作者曲線 → 一般關鍵影格、參數/摘要/快照、跨專案復用。六套實際預覽供選型。 | `motion pack list/inspect/create/capture/apply` | 65 點採樣、transform 屬性；預設拒絕衝突，明確取代整條屬性軌；跟蹤綁定拒絕，CPU 合成/自然品質未結案。 |
| F55 | 線性浮點轉場與群組進出場 | 明確 Float32 專案 → 57 xfade圖案+2 dip、預乘alpha混合、真實句柄/原作者時鐘、關聯音軌、群組擦除/推移及實際預覽成片。 | `timeline transition; preview; render; queue` | CPU；12種真實句柄宣告，其他圖案用明確重疊/邊緣；normal雙源混合；風噪有平台差異，HDR/自然品質未閉。 |
| F56 | 線性浮點文字與字幕 | 獨立／內嵌／SRT、聯合逐詞／打字機 → 原生位元組覆蓋率、可重用字形、分塊線性合成、原作者時鐘、4K標題及實際交付。 | `timeline compose; preview; render; queue` | 明確本機字型；CPU／明確GPU；覆蓋率8bit／顏色Float32；工作區准入非峰值RSS；富ASS／Bidi／自然品質未閉。 |
| F57 | 原生Float32 GPU執行 | 仿射、一般合成、文字組件/逐詞、粒子光柵及光學/高光擴散效果；任務自有管道/共享像素，貫通渲染/預覽/佇列/恢復。 | `projection_acceleration; render; preview; queue` | off/prefer/require；binary64精度/次正規探測，粒子保留Float32；有界控制及所屬程序/執行緒/串流清理，其他算子CPU。 |
| F58 | Float32全域/區間調整層 | 全軌含字幕合成後依序調色/光效；既有浮點效果及光學/高光擴散效果、六種插值，選定根僅套用一次。 | `settings.adjustments; preview; render; queue` | 明確線性工作域/效果訊號；光學/高光擴散可GPU，其餘CPU；LUT持鎖/包遷移，原作者區間時鐘，非完整HDR。 |
| F59 | 原生PTS跟蹤及疊加軌 | 保存來源觀測→依實際原生影格求跟隨位置；共用crop/TRS、ROI縮放／相對旋轉、透明度、視窗及巢狀聲音。 | `media track-bind; preview; render; queue; package` | 明確Float32，原生PTS不烘焙顯示鍵；預算／循環門禁；模板漂移及遮擋另審，中間格式烘焙未接通。 |
| F60 | 原生跟蹤與烘焙交付 | 實際alpha/5類遮罩/59轉場足跡；剪輯與共享變速保留觀察；原生烘焙逐幀核驗並保留來源旁車。 | `media track-bind; timeline compose/edit; convert export --bake-tracking` | 目前凍結圖/FPS；20,000幀/256,000求值；無法表達的整數步進拒絕；外部播放器與自然身分/遮擋待驗收。 |
| F61 | 本地GPU影片生成 | 文生、圖生、尾幀/首尾幀；原文提示/取樣、真實模型視窗、可編輯入軌、端點核驗、可移植配方與受管恢復。 | `media adapter; media generate` | 既有原生VACE/CUDA依賴；無聲8bit SDR；條件端點合成保留；自然品質/生成權利/完整剪映AI待驗收。 |
| F62 | 原生GPU模型會話 | 同工程/適配器/提示詞重用權重與嵌入；每任務重設，活連線傳遞持鎖雜湊；取消、期限、閒置及任務數退出。 | `media model-session; media generate --model-session` | 原生Windows VACE；首條仍載入；新提示詞須新會話，串行執行；非全域顯存預留/多GPU。 |
| F63 | 可編輯程序化粒子與發射器動畫 | 六種原創配方、五形狀、seed/獨立CFR；21屬性源時鐘關鍵影格、六種緩動、暫停發射；實際GPU光柵化。剪輯/預覽/佇列/包/本地OTIO貫通。 | `vfx list/inspect/apply/update/show/animation-properties/animate` | CPU積分與出生取樣，GPU繪製；64點/屬性、16發射器、4096預留活粒子；無3D/碰撞/深度。 |
| F64 | 可編輯光學效果與GPU運算 | 眩光核心/條紋/光暈/鬼影、旋轉橢圓漏光、徑向紅藍色差；全部數值通道關鍵影格、原作者時鐘、片段/區間調整層，CPU/OpenCL。 | `effects list/inspect` → `timeline compose` → preview/render | 明確線性RGB；原alpha位元保留，透明隱藏色不滲出；ghosts/edge靜態，非實體鏡頭/自動亮源/bloom。 |
| F65 | 實際高光 Bloom / 膠片 Halation | 軟膝閾值提取實際高光→分離高斯擴散→核心抑制/線性著色；可編輯數值軌道及原作者時鐘，片段或根區間調整層。 | `effects list/inspect; timeline compose; preview; render; queue` | sigma0…32輸入像素；透明/複製邊界、原alpha位元保持；實際四kernel GPU/CPU參考，有界空間/訪問預算；非物理膠片/HDR驗收。 |
| F66 | 原生 PQ／HLG HDR 與 SDR 顯示 | 明確參考白及HLG峰值/gamma，解碼至顯示線性光；不同nit素材、一般效果/合成、10-bit BT.2020 NCL交付，獨立選擇SDR trim及PNG/MP4預覽。 | `timeline compose; validate; preview; render; convert` | 傳遞CPU，既有合成/光效可GPU；拒絕8-bit/標籤不符/缺單位；alpha位元保留。非ICC/動態中繼資料或HDR監看驗收。 |
| F67 | 本機神經口型同步 | 圖片／影片＋獨立聲音→真正CUDA MuseTalk口型；25FPS人臉框關鍵影格、語義下半臉混合、完整PCM及alpha保留，可復用配方並影片/音訊關聯入軌。 | `lipsync adapter register/list/inspect; lipsync generate` | 本機safetensors及既有原生Torch依賴；臉部256×256、明確8bit SDR與來源運鏡、無CPU回退；自然口型、完整數位人仍未驗收。 |

| 編號 | 服務模塊 | 運行形式 | 需要什么/提供什么 | 入口 | 範圍 |
|---|---|---|---|---|---|
| S01 | 本地 Agent 工具服務 | 原生進程/JSON | Python 3.13 + 已安裝包；Agent 可通過命令行或 Skill 調用。 | `version / capabilities / schema show` | 不內置 SaaS、HTTP API 或 MCP server；可由調用方自行封裝。 |
| S02 | 專案與操作存儲 | 本地文件/事務 | Agent Project、快照、鎖、操作與恢復記錄。 | `project / operation` | 不是多人云協作資料庫。 |
| S03 | 媒體處理與預設渲染 | 隨功能調用 | 已有 FFmpeg/ffprobe，素材均來自本地。 | `media / timeline / render` | 實際編碼器/濾鏡可用性取決於當前 FFmpeg。 |
| S04 | 顯式浮點像素內核 | 選擇性啟用 | NumPy 與聲明的 signal/預算；與預設管線分開檢查。 | `surface / render / preview` | 子集實現，非通用 FFmpeg 或剪映內核的完整替代。 |
| S05 | 字幕與語音 | 基礎解析 + 可選模型 | 字幕文件解析可直接用；Whisper/CTC/SoulX 需已有註冊環境。 | `subtitle / asr / tts` | 無預設云轉寫/配音供應商。 |
| S06 | 視覺 AI 與修復 | 可選本地適配器 | RVM/SAM2/LaMa/VACE/跟蹤/OCR/人臉的各自原生依賴與權重。 | `media adapter / ocr / face` | 基礎包無模型權重，未配置不能聲明已執行。 |
| S07 | HTML 動效生成 | 可選本地運行時 | 明確登記已有 Node、Playwright、Chromium、模板、圖片和字體。 | `motion html-*` | 不依賴 OpenFilm 在線服務；不自動安裝瀏覽器。 |
| S08 | 資源、模板與風格目錄 | 隨包目錄 + 用戶庫 | 500 LUT 隨包；素材、字體、音樂、模板由用戶登記或自建。 | `look / lut / template / library / fragment` | 不存在完整商業素材/模板訂閱庫。 |
| S09 | 本地渲染隊列與緩存 | 持久作業文件 | 單進程預設串行，明確條件下有限本地 worker 與緩存。 | `queue / preview / cache` | 無跨機器調度、云渲染或遠端計費服務。 |
| S10 | 品質檢查與診斷 | 本地產物服務 | FFmpeg 解碼/Scope、PNG/JSON 報告、golden、失敗診斷。 | `quality / diagnostics` | 客觀檢查與主觀品質驗收分開。 |
| S11 | 權利與交換服務 | 本地證據與文件交換 | 臺賬/策略/包雜湊/損失報告，不調用專有編輯器。 | `rights / policy / convert` | 不自動授予第三方素材/模型商業權利。 |
| S12 | 創意與運營支持 | Agent 任務指導 | 依賴調用方提供業務資訊與資料，產出腳本/建議/分析。 | `$agent-ffmpeg-local-editor` / K01–K17 | 不包含廣告平臺賬號接入、投放或自動采集資料。 |
| S13 | 內建社群素材服務 | 離線目錄 | 359 項有來源/許可的 BGM、短樂、音效、字型 | `materials list/inspect/verify/ingest` | 逐項權利，不是商業素材訂閱庫 |
| S14 | 本地配音/翻譯 | 原生模型 worker | 4 個可選 CPU/CUDA 包，103 音色對映和 OPUS 文字/字幕 | `voice / translate / model-pack` | 累計至少 7 個不同音色有真實輸出；103 音色完整試聽及人工驗收未完成 |
| S15 | 配樂準備與混音 | 原生 FFmpeg 音訊 | 顯式擷取/迴圈/淡化、獨立人聲/配樂、閃避 | `music prepare/mix` | 不作曲、不靜默裁人聲、不承諾接縫修復 |
| S16 | GPU相容服務 | 既有原生OpenCL ICD / NVIDIA模型庫 | 圖投影及獨立Float32仿射/一般疊加/字色/逐詞/粒子/光學/高光擴散；off/prefer/require，模型auto/cpu/cuda；實際探測/預算/清理 | `render --projection-acceleration; gpu inspect; --device` | RTX3060實測；字形/其他效果/轉場等CPU，系統庫授權另列。 |
| S17 | 原生 Windows 擷取 | FFmpeg gdigrab / DirectShow | 明確來源、裝置 ID、有限時長、完整解碼與素材登記 | `capture devices/record` | 真實視窗 CPU/GPU 已驗；攝影機/麥克風/同步未驗 |
| S18 | 圖文語義與經驗校準 | 明確登記的原生 SigLIP2 worker | 既有 Torch/Transformers/權重；檔案綁定索引/實作/類型/實際裝置 | `semantic adapter-register/index/calibrate/calibration-list/search/verify` | 分數非機率；冷啟動/大庫與校準工程遷移仍有限制 |
| S19 | 獨立四軌分離 | 原生 Torch/TorchAudio HDemucs worker | 明確登記原生 Python、權重/證據/實作雜湊；auto/cpu/cuda，4 float WAV/軌道 | `audio adapter; audio separate-stems` | 基礎 ZIP 不含 Torch/權重；自然聽感與權重許可未閉 |
| S20 | 字幕翻譯配音聯合服務 | 既有 OPUS / Kokoro 原生 worker + 受管工程事務 | 普通 SRT、明確語言/音色/軌道，CPU/CUDA/auto，批內復用 | `dub subtitles` | [完整流程](SUBTITLE_DUBBING.md)；保留全句與重試，字詞/口型/自然品質未閉 |
| S21 | 本地GPU常駐推理會話 | 原生行程、認證Windows命名管道、JSON/原始幀、重疊拒寫鎖與生命週期監控。 | 既有本地VACE適配器；同一提示詞多方案。 | `media model-session start/status/stop` | 不開放網路埠；同工程串行，首條載入與其他模型重用仍有限。 |
| S22 | MuseTalk CUDA 神經口型服務 | 本機Whisper-tiny音訊特徵、MuseTalk1.5 UNet、SD VAE及BiSeNet；固定safetensors與拒寫鎖、原生工作回收。 | 明確既有Torch/Diffusers/Transformers/OpenCV原生依賴及模型證據；無自動安裝。 | `lipsync adapter; lipsync generate` | 模型256×256，25FPS；授權、自然度、完整數位人及HDR另行驗收。 |

## 完整安裝版能力字段

以下逐項保留本輪從安裝版讀取的能力字段、狀態、命令、限制與配額。它們是契約，不是本輪對每一項重新執行的驗收。狀態 local_adapter_only 需要已有模型，implemented_with_limits 需閱讀限制。

### `visual_semantic_retrieval`

```json
{
  "status": "implemented_with_limits",
  "engine": "transformers-siglip-local-v1",
  "protocol": "agent-semantic-embedding-v1",
  "index_format": "agent-visual-semantic-index-v1",
  "commands": [
    "semantic adapter-register/adapter-list/adapter-inspect",
    "semantic index/index-list/verify/search",
    "semantic calibrate/calibration-list",
    "project upgrade-semantic"
  ],
  "input_kinds": [
    "project_image",
    "project_video",
    "text_query",
    "local_reference_image"
  ],
  "devices": [
    "auto",
    "cpu",
    "cuda"
  ],
  "dimension": 768,
  "text_token_limit": 64,
  "silent_truncation": false,
  "maximum_assets": 512,
  "maximum_rows": 4096,
  "maximum_queries": 128,
  "maximum_batch_size": 32,
  "score": "cosine_similarity_not_probability",
  "source_clock": "original_native_PTS_relative_to_container_origin",
  "query_protocol": "agent-semantic-clauses-v1",
  "query_modes": [
    "clauses",
    "raw"
  ],
  "maximum_include_clauses": 8,
  "maximum_exclude_clauses": 8,
  "decisions": [
    "candidates_require_review",
    "calibrated_match",
    "no_calibrated_match"
  ],
  "calibration": {
    "format": "agent-semantic-acceptance-profile-v1",
    "dataset_format": "agent-semantic-calibration-set-v1",
    "minimum_queries": 32,
    "maximum_queries": 128,
    "minimum_positive_queries": 16,
    "minimum_absent_queries": 16,
    "binding": [
      "index",
      "model",
      "implementation",
      "query_protocol",
      "kind",
      "actual_device",
      "device_index"
    ],
    "acceptance": "minimum_positive_clause_cosine_strictly_greater_than_empirical_cutoff",
    "all_results_require_review": true
  },
  "integrity": [
    "model",
    "selected_native_runtime_components",
    "product_implementation",
    "source_media",
    "preview",
    "vectors",
    "manifest"
  ],
  "execution_control": {
    "integrity_reads_observe_deadline_and_cancel": true,
    "partial_digest_discarded": true,
    "native_read_locks_preserved": true,
    "cancel_marker_probe_interval_seconds": 0.025,
    "inspection_commands_support_timeout_and_cancel": true,
    "recovery_verifies_outputs_after_operation_budget_reset": true,
    "blocked_OS_file_read_preemption": false
  },
  "project_package": {
    "owned_directories_preserved": true,
    "external_source_uri_rebinding": "verified_derived_metadata_only",
    "vectors_samples_calibration_fit_dataset_device_and_adapter_pins": "unchanged",
    "import_validation": "semantic_inner_bindings_before_staged_publication",
    "native_runtime_bundled": false,
    "inference_during_conversion": false
  },
  "runtime_upgrade": {
    "command": "project upgrade-semantic",
    "format": "agent-semantic-runtime-upgrade-v1",
    "explicit_new_ids": true,
    "requires_all_pinned_implementation_bytes_identical": true,
    "requires_external_model_runtime_and_evidence_bytes_identical": true,
    "old_installation_directory_required": false,
    "old_records_retained": true,
    "vectors_previews_dataset_fit_observations_device_preserved": true,
    "new_model_forwards": 0,
    "maximum_indexes": 32,
    "maximum_profiles": 64,
    "maximum_total_preview_rows": 4096,
    "maximum_copied_payload_bytes": 536870912,
    "changed_implementation_requires_new_index_and_calibration": true
  },
  "managed_jobs": {
    "actions": [
      "adapter-register",
      "index",
      "calibrate",
      "search"
    ],
    "native_owner_lease": true,
    "semantic_tree_write_ahead_publication": true,
    "explicit_cleanup": "project recover --cleanup-jobs",
    "diagnostics_retained_until_explicit_cleanup": true,
    "legacy_semantic_cache": "preserved_unmanaged",
    "inference_checkpoint_resume": false
  },
  "limits": [
    "requires_existing_registered_native_Python_Torch_Transformers_Pillow_and_local_SigLIP_safetensors",
    "fixed_768_dimension_224px_64token_base_profile_only",
    "sampled_frames_do_not_prove_actions_or_identity",
    "model_reuse_within_current_batch_only",
    "empirical_profile_not_universal_rejection_or_probability",
    "bounded_negation_grammar_unparsed_scope_requires_review",
    "exclusions_are_relative_frame_evidence_not_object_absence_detection",
    "calibration_does_not_establish_natural_scene_rejection_or_recall",
    "no_audio_embeddings_or_music_recommendation",
    "no_implicit_download_or_remote_code",
    "byte_identical_implementation_relocation_requires_explicit_upgrade_with_new_ids",
    "changed_model_runtime_or_implementation_requires_explicit_registration_and_index_rebuild",
    "legacy_flattened_semantic_packages_require_reexport_from_intact_source_project",
    "OS_DLL_closure_long_library_performance_and_broad_advertising_quality_unaccepted"
  ]
}
```

### `native_capture`

```json
{
  "status": "implemented_with_limits",
  "engine": "ffmpeg-windows-capture-v1",
  "commands": [
    "capture.devices",
    "capture.record"
  ],
  "sources": [
    "explicit_window_title",
    "desktop_or_region",
    "explicit_dshow_camera",
    "explicit_dshow_microphone"
  ],
  "features": [
    "bounded_native_windows_recording",
    "stable_current_device_ids",
    "optional_explicit_audio_input",
    "cpu_or_nvenc_video_encoding",
    "auto_records_cpu_fallback",
    "cancellation_and_preserved_diagnostics",
    "complete_output_decode_before_asset_registration",
    "local_source_evidence"
  ],
  "limits": [
    "windows_gdigrab_and_dshow_build_required",
    "no_implicit_microphone_or_camera",
    "device_modes_and_permissions_must_be_available",
    "av_sync_and_natural_recording_need_review",
    "not_a_capture_of_all_windows_or_a_background_monitor",
    "capture_does_not_grant_content_rights"
  ]
}
```

### `community_materials`

```json
{
  "status": "implemented_with_limits",
  "catalog_version": "1.0.0",
  "commands": [
    "materials.list",
    "materials.inspect",
    "materials.verify",
    "materials.ingest"
  ],
  "counts": {
    "music": 44,
    "jingle": 85,
    "sfx": 228,
    "font": 2
  },
  "features": [
    "bundled_real_audio_and_fonts",
    "stable_ids_and_three_language_search",
    "source_archive_and_individual_file_hashes",
    "copied_local_rights_and_attribution_evidence",
    "explicit_optional_audio_track_apply"
  ],
  "limits": [
    "source_licenses_remain_separate_from_product_code",
    "attribution_and_font_redistribution_conditions_survive_import",
    "not_a_commercial_stock_subscription_or_unlimited_music_catalog"
  ]
}
```

### `community_voice_translation`

```json
{
  "status": "implemented_with_limits",
  "provider": "native_windows_cpu_or_explicit_cuda",
  "commands": [
    "model-pack.list",
    "model-pack.verify",
    "voice.list",
    "voice.synthesize",
    "translate.text",
    "translate.subtitles",
    "gpu.inspect"
  ],
  "voices": 103,
  "voice_engine": "kokoro-sherpa-cpu-v1",
  "translation_engine": "opus-ctranslate2-ruy-cpu-v1",
  "device_selection": [
    "auto",
    "cpu",
    "cuda"
  ],
  "gpu_packs": [
    "kokoro-zh-en-cuda13",
    "opus-zh-en-cuda12-int8"
  ],
  "features": [
    "hash_pinned_optional_local_model_packs",
    "isolated_cpython313_without_site_startup",
    "chinese_english_named_voice_and_speed",
    "natural_duration_24k_mono_wav",
    "chinese_english_bidirectional_translation",
    "explicit_simplified_traditional_conversion",
    "srt_cue_order_and_millisecond_timing_preservation",
    "bilingual_subtitles",
    "explicit_glossary_post_edits_or_refusal"
  ],
  "limits": [
    "weights_not_in_base_package",
    "no_runtime_downloads",
    "cpython313_windows_x64_packs",
    "no_voice_cloning",
    "no_asr_or_precise_word_alignment_added",
    "translation_not_a_semantic_accuracy_guarantee",
    "subtitle_style_flattened_to_srt",
    "glossary_is_not_constrained_decoding",
    "output_and_text_rights_need_review"
  ]
}
```

### `community_music`

```json
{
  "status": "implemented_with_limits",
  "engine": "community-audio-ffmpeg-v1",
  "commands": [
    "music.prepare",
    "music.mix"
  ],
  "features": [
    "explicit_source_asset_and_rights_parents",
    "trim_and_opt_in_loop",
    "gain_and_fade_in_out",
    "speech_music_sidechain_ducking",
    "preserved_original_stems",
    "exact_requested_48k_stereo_pcm_sample_count",
    "sample_peak_and_rms_metrics"
  ],
  "limits": [
    "looping_does_not_repair_seams",
    "not_music_generation_or_composition",
    "not_human_listening_or_true_peak_loudness_acceptance",
    "no_silent_voice_truncation_or_source_overwrite"
  ]
}
```

### `timeline_native_float_keyer`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-signal-author-clock-continuous-float32-color-key-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "continuous_RGB_or_explicit_matrix_chroma_distance",
    "input_alpha_multiplied_by_key_coverage_never_replaced",
    "animated_key_RGB_similarity_blend_fractional_feather_despill_intensity",
    "explicit_RGB_signal_and_preserve_or_clip_distance_gamut",
    "deterministic_chroma_mean_of_distances_and_fractional_box_feather",
    "static_matte_inversion_and_red_green_blue_or_auto_despill_axis",
    "linear_working_RGB_mix_and_independent_coverage_mix",
    "same_ordered_kernel_for_formal_render_and_preview",
    "adaptive_default_768MiB_operator_workspace_and_cancellation"
  ],
  "limits": [
    "not_semantic_person_hair_or_AI_matting",
    "native_scanline_boundary_history_not_reproduced",
    "native_scalar_float_option_not_integer_pixel_bit_equivalence",
    "static_metric_matrix_range_neighbourhood_inversion_and_spill_axis",
    "color_tokens_are_RGB_only_no_alpha_or_remote_resource",
    "natural_material_quality_HDR_long_form_and_peak_RSS_not_accepted"
  ]
}
```

### `timeline_native_float_sharpen`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-YCbCr-author-clock-continuous-float32-unsharp-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "sharpen_unsharp_luma_chroma_and_independent_alpha",
    "explicit_matrix_range_reference_bits_and_RGB_signals",
    "normalized_binomial_kernels_with_replicated_edges",
    "fractional_and_independent_animated_radii_zero_to_eleven",
    "positive_sharpen_and_negative_blur_amounts",
    "six_author_easings_and_rational_ticks",
    "continuous_or_native_scalar_coefficients",
    "explicit_code_and_output_gamut_policies",
    "default_alpha_bits_preserved",
    "linear_working_intensity_and_coverage_mix",
    "shared_formal_and_preview_chain",
    "full_spatial_scratch_with_adaptive_conversion_tiles"
  ],
  "limits": [
    "native_scalar_mode_preserves_uint16_extra_eight_bit_strength_shift",
    "no_integer_raster_or_native_pixel_rounding",
    "native_integer_accumulator_or_signed_multiply_overflow_not_reproduced",
    "fourteen_bit_code_axis_is_a_continuous_extension",
    "fractional_zero_radius_large_kernel_sum_and_amount_above_five_are_extensions",
    "alpha_always_clips_to_zero_one",
    "code_clip_uses_reference_bits_not_native_uint16_storage_ceiling",
    "kernel_size_aliases_are_static_odd_three_to_twenty_three",
    "workspace_estimate_is_not_peak_RSS",
    "no_natural_quality_HDR_or_realtime_acceptance"
  ]
}
```

### `timeline_native_float_spatial_means`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-signal-author-clock-continuous-float32-spatial-means-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "average_and_box_blur",
    "linked_or_independent_animated_radii",
    "replicated_average_edges_and_half_sample_symmetric_box_edges",
    "fractional_outer_taps_no_integer_raster",
    "subtraction_free_positive_coverage_sums",
    "one_to_four_box_passes_or_zero_power_identity",
    "GBRA_plane_selection",
    "straight_or_premultiplied_RGBA",
    "explicit_input_output_RGB_signals",
    "linear_working_intensity_and_coverage_mix",
    "shared_formal_and_preview_chain",
    "full_spatial_scratch_with_adaptive_conversion_tiles"
  ],
  "limits": [
    "native_integer_quantization_and_fixed_reciprocals_not_reproduced",
    "average_radii_clamp_to_half_axis_size",
    "box_large_or_fractional_radii_are_explicit_extensions",
    "legacy_average_sizeY_zero_inherits_X_canonical_radius_y_zero_disables_axis",
    "power_planes_and_alpha_mode_are_static",
    "premultiplied_requires_all_four_planes",
    "workspace_estimate_is_not_peak_RSS",
    "no_natural_quality_HDR_or_realtime_acceptance"
  ]
}
```

### `timeline_native_float_gaussian`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-signal-author-clock-normalized-float32-Gaussian-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "linked_or_independent_horizontal_vertical_radii",
    "six_author_easings_rational_ticks",
    "normalized_recursive_Gaussian_no_integer_raster",
    "one_to_six_steps",
    "GBRA_plane_selection",
    "straight_or_premultiplied_RGBA_blur",
    "explicit_input_output_RGB_signals",
    "linear_working_intensity_and_coverage_mix",
    "shared_formal_and_preview_chain",
    "full_spatial_scratch_with_adaptive_conversion_tiles"
  ],
  "limits": [
    "default_blur_changes_RGB_and_alpha",
    "premultiplied_requires_all_four_planes",
    "normalized_binary64_recursion_is_not_bit_exact_native_float32",
    "full_spatial_scratch_admitted_before_output",
    "workspace_estimate_is_not_peak_RSS",
    "temporal_denoise_not_added_here",
    "no_natural_quality_HDR_or_realtime_acceptance"
  ]
}
```

### `timeline_native_float_basic_tone`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-YCbCr-author-clock-continuous-float32-basic-tone-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "brightness_contrast_saturation_color_gamma_hue_global_HSL_grayscale",
    "explicit_matrix_range_and_RGB_signals",
    "continuous_or_native_scalar_coefficients",
    "8_or_10_bit_fractional_code_axes",
    "six_author_easings_rational_ticks",
    "linear_working_intensity_mix",
    "bit_preserved_alpha",
    "shared_formal_and_preview_chain"
  ],
  "limits": [
    "global_HSL_is_YCbCr_rotation_not_RGB_HSL",
    "eq_saturation_clamps_at_3_like_native",
    "native_coefficients_does_not_quantize_pixels_or_promise_bit_equivalence",
    "eq10_is_explicit_continuous_extension",
    "changed_planes_clip_to_reference_code_range",
    "no_natural_quality_or_HDR_acceptance",
    "workspace_estimate_is_not_peak_RSS"
  ]
}
```

### `timeline_native_float_selective_hsl`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-signal-author-clock-continuous-float32-eight-band-hsl-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "24_independent_eight_band_HSL_channels",
    "original_hue_simultaneous_triangular_weights",
    "unequal_orange_and_purple_sectors",
    "six_author_easings_and_rational_ticks",
    "explicit_input_output_RGB_signals",
    "linear_working_intensity_mix",
    "explicit_reject_clip_or_residual_input_gamut",
    "continuous_values_without_integer_raster_or_LUT",
    "ordered_existing_effect_chain",
    "alpha_bits_preserved",
    "bounded_tiles_and_cancellation"
  ],
  "limits": [
    "HSL_operator_uses_bounded_input_signal_RGB",
    "preserve_residual_is_a_declared_creative_extension_not_HDR_appearance",
    "zero_intensity_bypasses_gamut_policy_after_surface_validation",
    "legacy_eight_bit_native_and_geq_backends_unchanged",
    "workspace_estimate_not_total_RSS",
    "no_HDR_natural_quality_or_full_CapCut_acceptance"
  ]
}
```

### `timeline_native_float_balance`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-signal-author-clock-float32-three-way-balance-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "nine_independent_three_way_wheel_channels",
    "shadow_only_RGB_balance",
    "legacy_Kelvin_shadow_mapping",
    "six_author_easings_and_rational_ticks",
    "explicit_input_output_RGB_signals",
    "linear_working_intensity_mix",
    "negative_and_superwhite_RGB_with_preserve_gamut",
    "explicit_operator_domain_clip",
    "bounded_native_HSL_or_unbounded_midrange_lightness",
    "ordered_existing_effect_chain",
    "alpha_bits_preserved",
    "bounded_tiles_and_cancellation"
  ],
  "limits": [
    "weights_use_input_max_plus_min_not_Rec709_luma",
    "native_HSL_requires_operator_input_RGB_zero_one",
    "native_HSL_black_white_defined_without_native_nonfinite_arithmetic",
    "midrange_is_a_distinct_explicit_lightness_method",
    "Kelvin_is_creative_mapping_not_physical_white_balance",
    "native_FFmpeg_colorbalance_accepts_integer_formats_only",
    "workspace_estimate_not_total_RSS",
    "no_HDR_natural_quality_or_full_CapCut_acceptance"
  ]
}
```

### `timeline_native_float_levels`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-signal-author-clock-float32-rgba-levels-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "shared_RGB_and_independent_RGBA_endpoints",
    "seven_native_preserve_metrics",
    "whole_surface_automatic_input_endpoints",
    "explicit_input_output_RGB_signals",
    "six_author_endpoint_and_intensity_easings",
    "linear_working_intensity_mix",
    "ordered_exposure_LUT_curves_levels_chain",
    "finite_negative_and_over_one_RGB",
    "alpha_bits_preserved_unless_explicitly_mapped",
    "bounded_tiles_and_cancellation"
  ],
  "limits": [
    "rimin_rimax_romin_romax_retain_legacy_shared_RGB_alias_semantics",
    "independent_red_endpoints_use_red_input_black_and_related_canonical_names",
    "negative_input_endpoints_are_auto_detection_sentinels_not_literal_negative_cutoffs",
    "auto_minimum_seed_one_maximum_seed_zero_matches_native_normalized_policy",
    "zero_span_defaults_reject_or_explicit_output_black",
    "alpha_output_must_remain_zero_one",
    "workspace_estimate_not_total_RSS",
    "no_HDR_ICC_nits_natural_quality_or_full_CapCut_acceptance"
  ]
}
```

### `timeline_native_float_curves`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-signal-continuous-float32-rgb-curves-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "continuous_natural_cubic_and_monotone_pchip",
    "all_inheritance_and_independent_RGB",
    "explicit_post_master_after_channels",
    "explicit_input_output_RGB_signals",
    "linear_working_intensity_mix",
    "six_author_control_point_and_intensity_easings",
    "original_author_windows_nested_reverse_clocks",
    "ordered_exposure_LUT_curves_chain",
    "alpha_bits_preserved",
    "bounded_tiles_and_cancellation"
  ],
  "limits": [
    "fixed_topology_1_to_256_points_per_curve",
    "strict_increasing_binary64_x_at_each_author_sample",
    "curve_output_clamps_zero_one_and_constant_endpoints",
    "no_integer_curve_grid_or_fallback",
    "no_dynamic_point_insert_delete",
    "workspace_estimate_not_total_RSS",
    "no_HDR_ICC_nits_gamut_mapping_or_natural_quality_acceptance",
    "full_CapCut_parity_unaccepted"
  ]
}
```

### `timeline_native_float_lut`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-signal-float32-cube-lut-v2",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "project_local_path_or_registered_sha256",
    "immutable_red_fastest_cube",
    "nearest_trilinear_tetrahedral_pyramid_prism",
    "explicit_input_output_RGB_signals",
    "linear_working_domain_intensity_mix",
    "six_author_intensity_interpolations",
    "original_author_windows_and_nested_clock",
    "ordered_exposure_lut_chain",
    "source_alpha_bits_preserved",
    "bounded_tiles_and_cancellation",
    "standalone_1D_CUBE_or_Resolve_1D_then_3D_shaper",
    "independent_nearest_linear_cosine_cubic_spline_1D_interpolation",
    "explicit_Iridas_RGB_domain_or_Resolve_per_stage_input_ranges",
    "combined_table_registry_metadata_and_immutable_SHA256"
  ],
  "limits": [
    "complete_3D_CUBE_2_to_256_or_1D_2_to_65536",
    "explicit_table_and_workspace_admission",
    "domain_normalization_then_boundary_clamp",
    "native_strict_pyramid_axis_ties",
    "no_3dl_csp_dat_or_runtime_format_guessing",
    "combined_shaper_rejects_ambiguous_DOMAIN_headers",
    "1D_cubic_spline_may_overshoot_without_output_clip",
    "legacy_encoded_lut3d_does_not_gain_1D_support",
    "no_HDR_ICC_nits_gamut_mapping_or_natural_quality_acceptance",
    "workspace_estimate_not_total_RSS",
    "full_CapCut_parity_unaccepted"
  ]
}
```

### `timeline_native_float_crop`

```json
{
  "status": "implemented_with_limits",
  "protocol": "author-clock-float32-crop-projection-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "pixel_and_normalized_units",
    "fit_fill_stretch",
    "static_and_animated_xy_width_height",
    "clip_and_crop_local_keyframes",
    "six_author_interpolations",
    "original_author_clock",
    "leaf_static_and_position_only_ties_even_rounding",
    "continuous_compound_crop",
    "single_pass_crop_fit_TRS",
    "fill_overscan_retained_until_final_canvas",
    "premultiplied_alpha_sampling",
    "parent_canvas_mask_after_crop_projection",
    "bounded_tiles_and_cancellation"
  ],
  "limits": [
    "nearest_or_bilinear_not_area_or_lanczos",
    "transparent_fit_bars",
    "not_legacy_integer_filter_byte_equivalence",
    "workspace_estimate_not_total_RSS",
    "no_natural_HDR_or_full_CapCut_parity_acceptance"
  ]
}
```

### `timeline_native_float_mask`

```json
{
  "status": "implemented_with_limits",
  "protocol": "author-clock-float32-alpha-mask-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame"
  ],
  "features": [
    "rectangle_circle_ellipse",
    "even_odd_polygon",
    "sampled_line_and_cubic_path",
    "clip_and_mask_local_keyframes",
    "original_author_clock",
    "invert",
    "source_alpha_preserved",
    "static_alpha_only_symmetric_box2",
    "animated_inner_distance_feather",
    "straight_RGB_bits_preserved_before_affine",
    "bounded_tiles_and_cancellation"
  ],
  "limits": [
    "32_path_candidate_points_8_segments",
    "cubic_is_sampled_polyline_not_analytic",
    "ellipse_distance_is_normalized_radial_approximation",
    "static_and_animated_feather_have_distinct_authored_semantics",
    "workspace_estimate_not_total_RSS",
    "no_natural_HDR_or_full_CapCut_parity_acceptance"
  ]
}
```

### `standard_native_float_render`

```json
{
  "status": "implemented_with_limits",
  "protocol": "standard-render-native-float32-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "render",
    "render.resume",
    "queue.run"
  ],
  "features": [
    "original_native_PTS_windows",
    "explicit_linear_D65_RGBA_Float32_composition",
    "existing_author_IR_and_audio_graph",
    "bounded_encoder_stdin",
    "final_RGB16_delivery_edge",
    "explicit_zscale_output_matrix_range",
    "independent_alpha8_delivery",
    "common_encoders_quality_fingerprints_operations",
    "caught_publish_IO_pair_rollback",
    "linear_premultiplied_transitions",
    "real_source_handles_and_linked_audio",
    "authored_group_spatial_edges",
    "linear_float32_titles_inline_text_and_plain_SRT",
    "explicit_probed_native_opencl_float_geometry_normal_over_and_text_colors",
    "ordered_sequence_adjustments_after_complete_composite",
    "native_PTS_dynamic_tracking_bindings",
    "overlay_tracks_and_nested_overlay_audio"
  ],
  "tracking": {
    "protocol": "native-PTS-float32-tracking-bindings-v1",
    "selection": "saved tracking_binding on an explicit native Float32 visual clip",
    "commands": [
      "media.track-bind",
      "render",
      "preview.frame",
      "preview.range",
      "render.resume",
      "queue.run"
    ],
    "clock": "selected original int64 PTS times rational time_base minus demux origin; no CFR keyframe bake",
    "geometry": "same crop/fit/TRS inverse and actual source dimensions as rendered source",
    "features": [
      "CFR_and_VFR_observation_playback",
      "nonzero_demux_origin",
      "partial_native_index",
      "scalar_and_curve_retime",
      "reverse_freeze_and_nested_clocks",
      "dynamic_crop",
      "source_and_target_presentation_windows",
      "source_opacity_and_blend",
      "ROI_scale_and_relative_rotation",
      "chained_bindings",
      "cycle_and_aggregate_budget_gates",
      "editable_package_preserves_source_observations",
      "split_trim_ripple_insert_delete_source_and_target",
      "range_insert_overwrite_lift_extract_retained_roll_slide",
      "retained_source_fragments_and_hidden_deleted_sources",
      "pinned_ROI_rotation_reference_after_surgery",
      "locked_reference_atomic_rejection",
      "physical_source_slip_and_real_head_tail_extension",
      "fragment_specific_author_reference_offsets_and_target_opacity_reanchor",
      "source_handle_roll_slide_with_retained_observations",
      "rational_integer_grid_piecewise_constant_curve_clock",
      "magnetic_reorder_synchronized_source_target_cuts_and_lineage_repair",
      "shared_author_dependency_closure_complete_output_retime",
      "per_layer_selected_output_preserves_external_blend_and_scalar_alpha",
      "selected_audio_instances_avoid_duplicate_sound",
      "partial_retime_retained_parent_routes_and_repeated_linked_retime",
      "actual_projected_pixel_alpha_effects_and_all_five_mask_shapes",
      "all_59_edge_and_paired_transition_source_point_footprints",
      "full_density_transport_across_edge_then_paired_transition",
      "spatial_point_and_ROI_transport_generated_matte_has_no_source",
      "actual_transition_peer_binding_cycle_preflight_and_bounded_leaf_cache"
    ],
    "visibility_protocol": "native-transition-point-footprint-v1",
    "visibility_alpha": "no transition: bilinear projected alpha times scalar opacity; transitions: alpha-weighted point footprint mass clamped to 0..1",
    "visibility_geometry": "bilinear tent/Float64 density transported through the actual sampling kernels; mass centroid; required missing or degenerate ROI hides target",
    "max_visibility_dependency_depth": 64,
    "max_leaf_cache_bytes": 67108864,
    "edit_protocol": "native-tracking-edit-lineage-v1",
    "max_source_fragments_per_binding": 128,
    "max_total_source_references": 4096,
    "edit_limits": [
      "selected_outputs_keep_inner_binding_graph;explicit_unlink_separates_authored_outputs",
      "retime_sync_content_ripple_does_not_retime_unselected_intersections",
      "legacy_tracking_magnetic_cuts_keep_existing_binding_guard",
      "overlapping_source_fragments_reject_ambiguous_coverage",
      "physical_source_limits_and_unobserved_range_hiding_remain",
      "nonconstant_curve_mapping_keeps_existing_bounded_float_clock"
    ],
    "source_edit_reference_policy": "head extensions accumulate author_offset_tick per source fragment; slip recalibrates ROI/rotation at the pinned output clock",
    "max_bindings": 128,
    "max_total_observations": 64000,
    "max_observations_per_binding": 4000,
    "max_depth": 16,
    "display_keyframes_baked": false,
    "render_time_model_inference": false,
    "GPU": "coordinate and transition footprint evaluation CPU; explicit probed Float32 GPU projection/compositing when eligible",
    "limits": [
      "direct_square_unrotated_video_sources",
      "observation_analysis_quality_and_sampling_are_separate",
      "source_contribution_precedes_higher_track_occlusion",
      "ROI_scale_clamp_0_01_to_20",
      "nonlocal_warps_may_duplicate_or_lose_a_pixel_footprint_no_natural_identity_claim",
      "conservative_transition_peer_visibility_cycles_rejected_before_pixel_fetch",
      "external_OTIO_MLT_draft_playback_requires_independent_renderer_acceptance",
      "not_natural_identity_tracking_or_full_motion_quality_acceptance"
    ],
    "interchange_bake": {
      "protocol": "native-PTS-tracking-frame-verified-bake-v1",
      "entry": "convert export --bake-tracking --target-format agent-json|package; automatic for otio/kdenlive-xml/jianying-draft-json",
      "sampling": "actual native Float32 frame/visibility evaluation, including nested clocks and transition peers",
      "verification": "all selected and standalone sequence display frames compared by exact Float32 RGBA hash before export",
      "max_frames": 20000,
      "max_samples": 256000,
      "preserves": [
        "author_project",
        "original_media",
        "retime_clocks",
        "audio",
        "masks",
        "transitions",
        "source_binding_sidecar"
      ],
      "rejects": [
        "conflicting_author_clock_demands",
        "unrepresentable_integer_tick_steps",
        "pixel_mismatch",
        "budget",
        "input_change"
      ],
      "limits": [
        "frozen_graph_and_display_FPS_only;re_bake_after_edits",
        "external_renderer_not_certified",
        "unsupported_external_effects_still_reported",
        "muted_unreachable_targets_listed_without_playback_keys"
      ]
    }
  },
  "adjustments": {
    "protocol": "selected-sequence-author-clock-float32-adjustments-v1",
    "selection": "settings.adjustments; explicit native Float32 pipeline",
    "forms": [
      "effect_object",
      "effect_array_container",
      "supported_signal_free_string_shorthand"
    ],
    "stage": "after_all_selected_sequence_video_and_subtitle_tracks_before_delivery",
    "clock": "selected_sequence_tick_minus_declared_start_tick; original interval duration retained",
    "nested": "once_at_selected_root_not_each_child_canvas",
    "resource_policy": "existing_effect_compiler_signals_alpha_range_automation_and_LUT_dependencies",
    "interval": "start_inclusive_end_exclusive; shorter_target_clips_coverage_without_time_rescaling",
    "max_layers": 128,
    "max_effects": 4096,
    "max_declaration_bytes": 8388608,
    "GPU": "analytic_optical_and_highlight_glow_effects_only;other_adjustment_operators_CPU",
    "audio_changed": false
  },
  "limits": [
    "explicit_opt_in_not_default_migration",
    "unported_operators_reject_without_legacy_fallback",
    "square_unrotated_native_sources_only",
    "BT709_relative_delivery_not_HDR_or_ICC",
    "source_cache_and_projection_quotas_are_not_total_RSS",
    "publication_pair_not_crash_atomic",
    "no_natural_longform_or_full_CapCut_parity_acceptance"
  ]
}
```

### `native_float_surface_bundle`

```json
{
  "status": "implemented_with_limits",
  "protocol": "agent-native-clock-float32-bundle-v1",
  "commands": [
    "surface.export",
    "surface.inspect"
  ],
  "features": [
    "registered_local_RGB_gray_YCbCr_sources",
    "owned_straight_RGBA_Float32",
    "original_int64_frame_index_PTS_duration",
    "explicit_D65_relative_colour_signals",
    "BT709_DisplayP3_BT2020_linear_gamut_matrix",
    "explicit_source_transfer_interpretation",
    "bounded_static_affine_sampling",
    "independent_alpha",
    "selected_native_frame_window",
    "source_tool_implementation_SHA256",
    "atomic_bounded_bundle",
    "readonly_pixel_clock_hash_verification"
  ],
  "limits": [
    "intermediate_bundle_is_not_an_encoded_movie",
    "not_yet_timeline_render_preview_or_cache_backend",
    "YCbCr_requires_matrix_range_siting_and_caller_progressive_declaration",
    "BT709_camera_inverse_OETF_differs_from_display_gamma",
    "relative_D65_only_no_absolute_nits_ICC_or_HDR",
    "native_prefix_decode_before_selected_window",
    "maximum_2GiB_bundle_not_peak_RSS_acceptance",
    "point_bilinear_affine_without_severe_minification_antialiasing_acceptance",
    "inspect_verifies_derived_bytes_without_revalidating_original_inputs",
    "no_audio_export_natural_HDR_long_file_or_full_CapCut_parity_acceptance"
  ]
}
```

### `nested_native_video_clock`

```json
{
  "status": "implemented_with_limits",
  "protocol": "covering-native-source-half-open-v1",
  "scope": "registered_native_video_leaves_with_composed_author_time_maps",
  "features": [
    "original_VFR_display_intervals",
    "fractional_covering_source_frames",
    "composed_nonlinear_author_clocks",
    "native_reverse_interval_duration_order",
    "real_native_EOF_and_demux_origin",
    "shared_verified_native_frame_index",
    "existing_bounded_reverse_chunk_fallback"
  ],
  "limits": [
    "virtual_inline_surfaces_keep_child_CFR_contract",
    "general_nested_VFR_effect_combinations_require_separate_acceptance",
    "native_frame_index_reverse_expression_memory_and_disk_budgets_apply",
    "no_long_duration_peak_RSS_natural_HDR_audio_or_full_capcut_parity_acceptance"
  ]
}
```

### `native_video_frame_index`

```json
{
  "status": "implemented_with_limits",
  "protocol": "native-video-frame-index-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame",
    "cache.list",
    "cache.prune"
  ],
  "cache_kind": "native-video-index",
  "features": [
    "native_int64_pts_and_durations",
    "source_runtime_decoder_pinned",
    "readonly_miss_planning",
    "source_frame_probe_skipped_on_verified_hits",
    "single_graph_index_reuse",
    "post_render_file_revalidation",
    "explicit_safe_pruning"
  ],
  "limits": [
    "ordinary_reverse_and_flattened_native_nested_video_only",
    "maximum_1000000_frames_per_source",
    "maximum_256_entries_per_project",
    "full_source_and_runtime_hash_io_on_hits",
    "source_index_decode_counter_excludes_audio_pixel_decode_and_output_encoding",
    "no_long_duration_latency_peak_RSS_HDR_or_full_capcut_parity_acceptance"
  ]
}
```

### `native_audio_source_clock`

```json
{
  "status": "implemented_with_limits",
  "protocol": "native-decoded-audio-interval-clock-v1",
  "commands": [
    "render",
    "preview.range",
    "preview.frame",
    "media.multicam",
    "cache.list",
    "cache.prune"
  ],
  "cache_kind": "native-audio-clock",
  "features": [
    "decoded_frame_PTS_and_native_sample_counts",
    "hard_gaps_as_zero_samples",
    "later_decoded_overlap_samples_win",
    "half_tick_per_PTS_and_coarse_relative_anchor_uncertainty",
    "native_float_PCM_only_when_discontinuous",
    "original_asset_references_retained",
    "source_runtime_and_derived_SHA256",
    "shared_graph_context",
    "atomic_bounded_cache",
    "explicit_prune_protects_registered_source_assets"
  ],
  "bounds": {
    "frames": 2000000,
    "index_bytes": 67108864,
    "PCM_bytes": 8589934592,
    "entries": 256
  },
  "async_clock_drift_correction": false,
  "limits": [
    "full_native_audio_index_decode_on_cache_miss",
    "source_and_runtime_hash_IO_on_hits",
    "subtick_discontinuities_in_coarse_containers_are_not_recoverable",
    "limits_are_not_peak_RSS_or_long_file_latency_acceptance",
    "arbitrary_codec_priming_and_midstream_format_changes_require_explicit_acceptance",
    "natural_HDR_listening_and_full_CapCut_parity_unaccepted"
  ]
}
```

### `reverse_video_cache`

```json
{
  "status": "implemented_with_limits",
  "protocol": "native-lossless-reverse-chunks-v1",
  "commands": [
    "cache.list",
    "cache.prune"
  ],
  "activation": "native_video_leaf_reverse_over_shared_selected_frame_budget",
  "features": [
    "sequential_bounded_native_frame_chunks",
    "FFV1_native_pixel_format",
    "original_reverse_interval_clock_reapplied",
    "keyframe_preroll_and_absolute_PTS_trim",
    "orthogonal_source_rotation_and_flip",
    "source_runtime_and_cache_byte_pinning",
    "cancel_and_atomic_cache_publication",
    "post_render_cache_reverification",
    "explicit_prune_with_current_project_reference_protection"
  ],
  "frame_raster_estimate_budget_bytes": 268435456,
  "disk_reservation_limit_bytes": 137438953472,
  "limits": [
    "budget_is_not_process_RSS",
    "long_duration_latency_not_accepted",
    "general_nested_VFR_surface_resampling_not_accepted",
    "reverse_audio_not_included",
    "natural_and_HDR_quality_not_accepted",
    "cache_inventory_is_not_content_validation"
  ]
}
```

### `timeline_preview`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-timeline-preview-v1",
  "commands": [
    "preview.frame",
    "preview.range",
    "preview.cache-list",
    "preview.cache-prune"
  ],
  "features": [
    "full_author_graph_before_output_frame_trim",
    "rational_display_frame_and_pcm_sample_ranges",
    "rgba_png_frame",
    "lossless_bgra_ffv1_float_pcm_reference",
    "mp4_review_delivery",
    "actual_content_and_runtime_hashes",
    "verified_persistent_cache",
    "new_directory_export",
    "project_lock_cancel_atomic_publication",
    "bounded_space_admission_and_cache_pruning"
  ],
  "limits": [
    "software_offline_preview_no_playback_gui",
    "cumulative_decode_from_author_start",
    "maximum_3600_frames_and_conservative_working_space_budget",
    "maximum_256_cache_entries",
    "external_subtitle_font_fallback_stochastic_and_open_container_dependencies_bypass_reuse",
    "mp4_is_lossy_and_opaque_lossless_reference_retains_alpha_and_pcm",
    "sha_verification_cost_applies_on_cache_hits",
    "no_automatic_natural_quality_or_realtime_acceptance"
  ]
}
```

### `timeline_native_float_exposure`

```json
{
  "status": "implemented_with_limits",
  "protocol": "linear-float32-native-coefficient-exposure-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "author_effect": "exposure",
  "parameters": {
    "amount": [
      -3,
      3
    ],
    "black": [
      -1,
      1
    ]
  },
  "features": [
    "linear_RGB_before_mask_and_affine",
    "nested_group_after_child_composition",
    "standard_render_and_preview_shared_host",
    "straight_alpha_bits_preserved",
    "finite_negative_over_one_RGB_no_integer_edge",
    "ordered_static_chains_and_disabled_effects",
    "six_direct_author_easings_for_amount_and_black",
    "rational_original_author_window_and_nested_clock"
  ],
  "animation_protocol": "author-clock-native-coefficient-float32-exposure-v1",
  "limits": [
    "native_binary32_coefficients",
    "singular_white_equals_black_gain_1024",
    "absolute_white_black_difference_for_positive_gain",
    "final_delivery_range_policy_still_applies",
    "no_automatic_HDR_natural_quality_or_CapCut_parity"
  ]
}
```

### `timeline_native_float_preview`

```json
{
  "status": "implemented_with_limits",
  "protocol": "agent-native-float32-timeline-preview-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1",
  "commands": [
    "preview.frame",
    "preview.range",
    "preview.cache-list",
    "preview.cache-prune"
  ],
  "features": [
    "same_standard_render_native_sources_and_author_IR",
    "selected_complete_author_frame_indices",
    "straight_BT709_linear_Float32_NUT_reference",
    "RGBA16_PNG_frame",
    "sample_exact_authored_Float32_PCM_ranges",
    "linear_premultiplied_bilinear_resize_after_composite",
    "BT709_MP4_view_over_linear_black",
    "content_and_NumPy_runtime_bound_cache",
    "owned_process_provider_cleanup_before_publication"
  ],
  "limits": [
    "explicit_opt_in_not_default_migration",
    "same_unported_operator_rejections_as_float_render",
    "relative_D65_not_HDR_or_ICC",
    "bilinear_minification_not_area_antialiasing",
    "cache_budget_is_disk_admission_not_total_RSS",
    "source_seek_preroll_may_decode_earlier_frames",
    "MP4_is_lossy_opaque_review_copy",
    "no_realtime_natural_quality_or_full_CapCut_acceptance"
  ]
}
```

### `contact_sheet`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-native-contact-sheet-v1",
  "commands": [
    "media.contact-sheet"
  ],
  "features": [
    "explicit_or_packet_timestamp_source_anchors",
    "actual_decoded_presentation_timestamps",
    "alpha_aware_vp8_vp9_decoder",
    "bounded_scaled_rgba_frames",
    "checker_light_dark_alpha_views",
    "source_tools_frame_and_panel_sha256",
    "owned_native_process_timeout_cancel_cleanup",
    "new_directory_publication"
  ],
  "limits": [
    "32_frames_640x640_cells_8192_canvas_side_16million_canvas_pixels",
    "8bit_preview_not_source_precision_or_hdr_quality_measurement",
    "selected_frames_not_continuous_playback_or_audio_review",
    "automatic_count_is_upper_bound_on_unique_packet_candidates_verified_on_decode",
    "packet_demux_index_deadline_60seconds_not_a_decoded_quality_acceptance",
    "actual_frame_at_or_after_anchor_may_be_later_on_vfr_or_sparse_video",
    "no_browser_no_model_no_network",
    "no_automatic_quality_acceptance"
  ]
}
```

### `face_retouch`

```json
{
  "status": "implemented_with_limits",
  "engine": "openseeface-66-onnx-cpu-local-v1",
  "commands": [
    "face.adapter.register",
    "face.adapter.list",
    "face.adapter.inspect",
    "face.scan",
    "face.retouch"
  ],
  "features": [
    "explicit_local_cpu_onnx_and_native_python_artifacts",
    "66_raw_heatmap_landmarks_every_source_frame",
    "adjacent_geometry_association_cut_and_absence_reset",
    "explicit_neutral_default_smoothing_exposure_cheek_and_eye_controls",
    "lossless_encoded_rgba_original_alpha_and_outside_support_checks",
    "all_original_audio_streams_pcm_verified",
    "complete_landmark_recipe_replay_without_model_forwards",
    "owned_native_process_timeout_cancel_and_project_transactions"
  ],
  "limits": [
    "existing_numpy_opencv_onnx_onnxruntime_native_python_and_two_models_required",
    "1800_frames_4_faces_2073600_pixels_32mib_report_admission",
    "cfr_60fps_600seconds_zero_rotation_zero_start_square_pixels",
    "8bit_sdr_only_hdr_and_high_bit_depth_rejected",
    "srgb_bt709_gamma22_gamma28_explicit_unspecified_transfer_assumed_srgb",
    "raw_heatmap_scores_are_not_calibrated_probabilities",
    "geometry_association_is_not_identity",
    "landmarks_are_not_precise_skin_or_occlusion_segmentation",
    "not_makeup_body_sculpting_hair_relighting_or_face_generation",
    "mediapipe_sdk_not_used",
    "natural_quality_and_full_capcut_parity_unaccepted"
  ]
}
```

### `pipeline_diagnostics`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-native-pipeline-diagnostic-v1",
  "commands": [
    "diagnostics.list",
    "diagnostics.show",
    "diagnostics.export"
  ],
  "features": [
    "decoder_worker_encoder_observed_and_cleanup_exit_separation",
    "windows_raw_unsigned_and_hex_exit_values",
    "bounded_redacted_stderr_before_workspace_cleanup",
    "failure_operation_id_and_optional_integrity_bound_reference",
    "plain_single_link_file_handle_checks",
    "limited_local_history_and_explicit_new_zip_export"
  ],
  "limits": [
    "shared_rvm_sam2_lama_vace_native_controller_only",
    "not_all_preflight_or_post_publication_failures_have_attachments",
    "stderr_64kib_each_response_read_128kib_summaries_32kib_manifest_64kib",
    "record_512kib_zip_768kib_history_32_records_64mib_14days_on_write",
    "root_cause_unknown_observation_order_is_not_causality",
    "redaction_not_complete_secret_recognition_or_crash_stability_acceptance"
  ]
}
```

### `hardware_acceleration`

```json
{
  "status": "implemented_with_limits",
  "engine": "ffmpeg-native-probed-v1",
  "commands": [
    "render",
    "queue.enqueue",
    "queue.run"
  ],
  "features": [
    "independent_off_prefer_require_encode_decode_policy",
    "actual_raster_pixel_format_color_bitrate_four_frame_encoder_probe",
    "forced_d3d11va_cuda_frames_download_compared_to_cpu_framemd5",
    "bounded_recorded_runtime_fallback_and_final_format_gate",
    "persistent_probe_attempt_logs_manifest_queue_resume",
    "independent_off_prefer_require_opencl_projection_policy",
    "same_pts_avexpr_binary64_coefficient_textures",
    "opencl_dynamic_crop_affine_native_sequence_bilinear_and_area",
    "ordered_binary64_prefix_transported_in_three_float32_texels",
    "actual_gpu_identity_fp64_image_extents_and_bitwise_texture_probes",
    "projection_raster_admission_kernel_hashes_logs_queue_resume",
    "render_owned_float32_opencl_worker_shared_buffers",
    "binary64_linear_float_affine_normal_over_text_components_binary_word_selection"
  ],
  "projection": {
    "engine": "opencl-binary64-projection-v1",
    "default": "off",
    "device": "explicit_platform.device_index",
    "native_runtime": "existing_windows_OpenCL_ICD_and_FFmpeg_program_opencl",
    "formats": [
      "gbrap",
      "gbrapf32le"
    ],
    "fallback": "prefer_before_execution_only",
    "runtime_failure": "fails_without_cpu_or_encoder_retry",
    "quota_scope": "projection_raster_admission_not_total_ram_or_vram"
  },
  "float32_projection": {
    "engine": "render-owned-float32-opencl-v1",
    "default": "off",
    "selection": "pixel_pipeline=float32-native-v1;projection_acceleration=off|prefer|require",
    "device": "explicit_platform.device_index",
    "native_runtime": "existing_windows_OpenCL_ICD",
    "control": {
      "protocol": "owned-inherited-binary-pipes-v1",
      "max_packet_bytes": 131072,
      "queue_capacity_each": 1,
      "pixel_transport": "three_owned_shared_memory_segments",
      "network": false,
      "per_operation_control_files": false,
      "cleanup": "owned_child_wait_then_join_IO_threads_and_close_streams",
      "durability": "project_snapshots_manifests_and_receipts_remain_atomic_fsync"
    },
    "surface": "straight_RGBA_Float32;binary64_kernel_math;no_fast_math",
    "operators": [
      "premultiplied_bilinear_affine",
      "normal_source_over",
      "ordered_text_color_components",
      "binary_word_selection",
      "seeded_particle_rasterization",
      "analytic_optical_effects",
      "highlight_separable_glow"
    ],
    "probe": "65536_native_levels_and_independent_CPU_oracles_before_execution",
    "lifetime": "one_owned_finite_worker_per_render_or_preview;cancel_timeout_cleanup",
    "budgets": "separate_device_and_host_shared_buffer_limits;not_peak_RSS_or_reserved_free_VRAM",
    "CPU_scope": [
      "glyph_rasterization",
      "effects_except_native_optics",
      "masks",
      "crop",
      "transitions",
      "non_normal_blends",
      "color_conversion",
      "audio",
      "encoding"
    ]
  },
  "limits": [
    "windows_backend_catalog_only_no_downloads",
    "explicit_video_bitrate_required_not_crf_quality_equivalence",
    "decode_yuv420_8_10bit_h264_hevc_vp9_av1_mpeg2_only",
    "four_frame_equality_does_not_prove_whole_source_quality",
    "pixel_probe_budget_not_total_driver_vram_limit",
    "encode_decode_driver_default_device_identity_not_certified",
    "projection_requires_gpu_images_and_ieee_binary64_actual_preflight",
    "projection_pixel_stateful_expressions_not_ported",
    "float_opencl_scope_explicit_other_operators_CPU_no_realtime_4k_or_capcut_parity_claim"
  ]
}
```

### `ocr`

```json
{
  "status": "implemented_with_limits",
  "engine": "ppocr-v4-onnx-cpu-local-v1",
  "commands": [
    "ocr.adapter.register",
    "ocr.adapter.list",
    "ocr.adapter.inspect",
    "ocr.scan",
    "ocr.anchors"
  ],
  "features": [
    "explicit_local_det_rec_and_native_python_sha256",
    "cpu_onnx_db_detection_and_ctc_recognition",
    "original_frame_indices_verified_cfr_pts_and_text_polygons",
    "source_model_bound_immutable_reports",
    "unique_exact_text_query_to_editable_camera_keyframes",
    "focus_then_return_to_full_frame",
    "native_process_tree_cancel_timeout_cleanup",
    "model_rights_dependencies_snapshots_and_packages"
  ],
  "limits": [
    "existing_numpy_opencv_onnx_onnxruntime_native_python_and_models_required",
    "120_sample_frames_16m_pixels_128_boxes_rec_width_2048",
    "video_cfr_60fps_600seconds_no_rotation_or_sar",
    "no_orientation_classifier_curved_or_vertical_text_acceptance",
    "anchor_requires_same_canvas_plain_forward_unretimed_clip",
    "text_bounds_are_not_clickable_control_bounds_or_action_detection",
    "sampled_ocr_does_not_prove_complete_privacy_redaction",
    "natural_ocr_quality_and_capcut_parity_unaccepted"
  ]
}
```

### `audio_routing`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-audio-routing-v1",
  "commands": [
    "timeline.compose:add_sequence",
    "timeline.compose:update_sequence",
    "render"
  ],
  "features": [
    "sequence_local_named_dag_buses",
    "shared_effect_returns_and_multilevel_outputs",
    "pre_post_fader_sends",
    "sample_clock_track_bus_master_and_send_automation",
    "named_track_or_bus_sidechain",
    "bus_mute_and_graph_solo",
    "unpruned_solo_detector_context",
    "explicit_fanout_and_float_sum",
    "complete_authored_child_audio_before_ancestor_time_maps",
    "full_scope_fragment_expansion_and_track_reference_remapping",
    "cycle_missing_reference_and_budget_rejection"
  ],
  "limits": [
    "stereo_48khz_not_spatial_surround",
    "fixed_tone_processor_order_not_plugin_host",
    "128_authored_nodes_512_edges_1024_points_4mib_routing_graph",
    "bus_solo_with_sidechain_uses_two_signal_graphs",
    "no_feedback_or_arbitrary_effect_parameter_automation",
    "inline_atempo_quality_and_file_only_r3_limits_apply",
    "not_natural_audio_or_capcut_parity_acceptance"
  ]
}
```

### `stroke_motion`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-stroke-motion-v1",
  "commands": [
    "motion.stroke-source",
    "motion.html-render"
  ],
  "features": [
    "explicit_authored_unicode_polylines_and_character_times",
    "original_openfilm_canvas2d_progressive_ink_functions",
    "integer_project_clock_and_arbitrary_frame_order",
    "editable_deterministic_source_bundle_and_color_parameter",
    "existing_offline_transparent_render_package_and_rights_pipeline"
  ],
  "limits": [
    "no_automatic_glyph_generation_chinese_stroke_order_or_audio_alignment",
    "no_svg_font_parser_kerning_or_complex_text_shaping",
    "256_characters_2048_strokes_32768_points_8_million_point_frames",
    "explicit_geometry_bounds_not_canvas_text_semantics_or_capcut_parity"
  ]
}
```

### `schema`

```json
{
  "status": "implemented",
  "commands": [
    "schema.show",
    "schema.export"
  ],
  "features": [
    "byte_pinned_packaged_draft202012_schema",
    "explicit_local_date_time_checker",
    "no_external_reference_retrieval",
    "missing_executor_or_resource_is_an_error",
    "exclusive_original_byte_export"
  ],
  "limits": [
    "date_time_leap_seconds_not_supported",
    "native_python_and_ffmpeg_provided_separately"
  ]
}
```

### `mask_edit`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-local-mask-edit-v1",
  "commands": [
    "media.mask-edit"
  ],
  "features": [
    "bound_encoded_mask_grid_and_source_sha256",
    "add_subtract_intersect_replace_in_order",
    "rectangle_ellipse_polygon_capsule_brush",
    "hold_linear_geometry_and_explicit_scene_resets",
    "bounded_supersampling_opacity_and_inward_feather",
    "editable_plan_in_assets_and_packages",
    "rebuild_from_registered_authored_plan",
    "lossless_alpha_and_exact_cfr_pts",
    "dry_run_cancel_timeout_transactions_and_idempotency"
  ],
  "limits": [
    "explicit_geometry_not_automatic_object_or_occlusion_reconstruction",
    "constant_white_rgb_alpha_coverage_no_audio",
    "ellipse_feather_uses_radial_distance_approximation",
    "explicit_pixel_buffer_raw_storage_and_work_estimates_not_total_ram",
    "not_natural_segmentation_repair_or_capcut_quality_acceptance"
  ]
}
```

### `html_motion`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-local-html-motion-v1",
  "commands": [
    "motion.html-register",
    "motion.html-source",
    "motion.html-inspect",
    "motion.html-fields",
    "motion.html-controls",
    "motion.html-quality",
    "motion.html-render"
  ],
  "features": [
    "explicit_byte_pinned_local_node_playwright_chromium",
    "editable_source_bundle_and_registered_image_font_closure",
    "typed_template_parameters_and_rebuild_to_new_asset_version",
    "sampled_root_css_text_image_controls_in_two_fresh_contexts",
    "local_asset_image_overrides_with_rights_dependencies",
    "per_frame_restore_and_partial_null_reset_saved_template_changes",
    "stable_component_ids_separate_definition_and_per_asset_value_snapshots",
    "agent_discoverable_typed_field_schema_ranges_units_defaults_and_choices",
    "registered_source_closure_component_images_with_strict_rights_gate",
    "per_frame_visible_hidden_and_original_page_reset_without_gui",
    "single_clip_asset_replacement_preserves_author_time_and_processing",
    "all_frame_dom_text_bounds_and_axis_specific_container_clipping",
    "actual_chromium_platform_fonts_and_local_sfnt_woff1_unicode_mapping",
    "explicit_strict_layout_gate_inherited_and_reexecuted_on_rebuild",
    "straight_alpha_ffv1_bgra_nut_exact_rational_frame_clock",
    "explicit_centered_midpoint_html_subframe_shutter_1_to_16_samples",
    "premultiplied_encoded_srgb_integer_half_up_alpha_accumulation",
    "source_cut_anchors_replay_and_per_subframe_time_hash_evidence",
    "strict_layout_checks_every_actual_shutter_subframe",
    "all_frames_rechecked_in_two_fresh_context_orders",
    "native_windows_job_timeout_cancel_and_descendant_cleanup",
    "dry_run_hash_binding_idempotency_and_project_transactions"
  ],
  "limits": [
    "native_windows_existing_toolchain_required_no_downloads",
    "trusted_local_templates_not_general_hostile_javascript_sandbox",
    "no_full_openfilm_timeline_iframe_embedded_media_or_webgl",
    "1800_frames_2_billion_pixel_work_64_mib_bundle_512_mib_output",
    "shutter_work_includes_three_redraw_and_two_optional_layout_passes",
    "8bit_encoded_srgb_preview_no_linear_light_hdr_or_automatic_internal_cuts",
    "not_cross_browser_font_or_hdr_capcut_quality_acceptance"
  ]
}
```

### `range_edits`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-range-edit-v1",
  "commands": [
    "timeline.edit:insert",
    "timeline.edit:overwrite",
    "timeline.edit:lift",
    "timeline.edit:extract",
    "timeline.edit:roll",
    "timeline.edit:slide",
    "timeline.compose:linked_edit"
  ],
  "features": [
    "integer_three_point_insert_and_overwrite",
    "linked_and_sync_lock_scope",
    "main_track_riders",
    "non_destructive_complete_author_clock_pieces",
    "roll_and_slide_with_retained_author_handles",
    "linked_audio_cut_pairs",
    "whole_file_subtitle_offset_preservation",
    "reviewable_created_and_removed_ids",
    "dry_run_fingerprint_idempotency_and_atomic_batches",
    "collision_lanes_preserve_track_processing"
  ],
  "limits": [
    "source_handle_policy_is_explicit_and_reauthors_native_processing",
    "partial_tracking_and_real_transition_endpoint_cuts_rejected",
    "roll_requires_unique_continuous_linked_pairs",
    "slide_requires_disjoint_continuous_linked_triples",
    "track_and_root_processing_follow_new_timeline",
    "markers_remain_absolute",
    "existing_window_render_budgets_apply",
    "not_full_magnetic_rearrangement_or_capcut_parity_acceptance"
  ]
}
```

### `source_edits`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-source-edit-v1",
  "commands": [
    "timeline.edit:slip",
    "timeline.edit:extend_source",
    "timeline.edit:roll:handle_policy=source",
    "timeline.edit:slide:handle_policy=source",
    "timeline.compose:linked_edit",
    "timeline.compose:slip_clip"
  ],
  "features": [
    "linked_source_range_slip_without_timeline_movement",
    "retained_handles_before_genuine_local_source_extension",
    "reverse_constant_and_source_relative_curved_speed",
    "output_keyframes_effect_keys_and_freeze_prefix_reanchoring",
    "finite_asset_or_nested_sequence_bounds",
    "real_transition_handle_revalidation",
    "dry_run_fingerprint_idempotency_and_atomic_batches"
  ],
  "limits": [
    "finite_recorded_video_audio_or_sequence_inputs",
    "integer_source_tick_head_grid",
    "tail_includes_minimal_whole_source_tick",
    "extension_reauthors_edge_processing_and_native_retiming",
    "nested_curves_recompute_duration_normalization_with_explicit_warning",
    "tracking_source_or_target_source_changes_rejected",
    "partial_real_transition_endpoint_resize_rejected",
    "not_full_magnetic_editing_or_capcut_quality_acceptance"
  ]
}
```

### `presentation_cuts`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-presentation-window-v1",
  "commands": [
    "timeline.compose:split_clip",
    "timeline.compose:trim_clip",
    "timeline.compose:ripple_insert",
    "timeline.compose:ripple_delete"
  ],
  "features": [
    "non_destructive_author_clock",
    "middle_delete_keeps_both_sides",
    "split_inside_clips",
    "original_reverse_curves_freeze_animation_and_audio_processing",
    "recursive_native_av_graph",
    "global_id_and_lock_guards",
    "atomic_compose_batch",
    "cross_track_link_gate_for_scoped_ripple",
    "explicit_frame_and_sample_selection"
  ],
  "limits": [
    "window_inside_authored_duration_only",
    "markers_keep_absolute_ticks",
    "not_roll_slide_overwrite_or_full_magnetic_editing",
    "tracking_bindings_rejected",
    "affected_source_transitions_and_legacy_cross_clip_track_transitions_must_be_removed",
    "inline_processed_child_r3_retime_rejected",
    "speed_curve_reverse_and_freeze_edits_require_full_author_take",
    "smart_cut_reframe_and_tracking_on_output_windows_rejected",
    "64_direct_windows_16_recursion_levels_plus_existing_raster_budget",
    "external_formats_report_unsupported",
    "full_author_processing_can_repeat_work",
    "subframe_cuts_sample_on_display_grid_not_continuous_video"
  ]
}
```

### `fragment_library`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-local-fragment-library-v1",
  "commands": [
    "fragment.save",
    "fragment.list",
    "fragment.inspect",
    "fragment.apply"
  ],
  "features": [
    "immutable_versions",
    "local_search",
    "streamed_hashed_resources",
    "linked_transition_and_binding_selection_closure",
    "recursive_editable_sequences",
    "original_author_ticks_and_native_canvas",
    "isolated_instance_ids",
    "rights_revision_and_disposition_history",
    "fixed_file_luts_fonts_and_captions",
    "hash_bound_plans",
    "dry_run_snapshot_transaction_idempotency"
  ],
  "limits": [
    "same_timebase_fps_color_and_audio_context_required",
    "global_adjustments_and_external_audio_executables_rejected",
    "partial_ducking_bus_selection_rejected",
    "compound_video_track_insertion_only",
    "model_weights_and_executable_adapters_not_bundled",
    "source_rights_changes_do_not_automatically_propagate",
    "crash_may_leave_unreferenced_resources",
    "default_4gib_4096files_32mib_manifest"
  ],
  "runtime": "native-python-no-node-browser-network-or-virtualization",
  "workflow_reference_revision": "eefd6a8d379289102141359a4718dbab12170526"
}
```

### `subtitle_segmentation`

```json
{
  "status": "implemented_with_limits",
  "engine": "openfilm-local-subtitle-segment-v1",
  "commands": [
    "subtitle.segment"
  ],
  "features": [
    "source_line_preservation",
    "cjk_latin_mixed_segmentation",
    "numbers_units_abbreviations",
    "provided_onsets_and_estimated_interiors",
    "weighted_untimed_lines",
    "supplied_translation_alignment",
    "shared_translation_groups",
    "original_translation_bilingual_display",
    "hash_bound_piece_corrections",
    "unicode_codepoint_indexes",
    "relative_node_clock_absolute_integer_ticks",
    "bounded_rules",
    "new_json_and_srt_assets",
    "inline_timeline_application",
    "clip_rights_dependencies",
    "dry_run_snapshot_transaction_idempotency"
  ],
  "runtime": "native-local-node-22.2-or-newer-no-npm-browser-or-service",
  "source_revision": "b138595d4c2d1fa5262b4a8a8c7cd98187c4b077",
  "source_license": "MIT",
  "limits": [
    "not_asr_forced_alignment_or_machine_translation",
    "word_interiors_use_speaking_weights",
    "icu_version_affects_cjk_word_boundaries",
    "unbreakable_words_can_exceed_width",
    "short_source_lines_remain_short",
    "source_line_clock_overlap_rejected",
    "new_text_rights_start_unverified",
    "srt_is_millisecond_quantized",
    "node_worker_has_30_second_128mib_js_heap_budget_not_total_rss",
    "max_2000_codepoints_per_line_100000_total_25million_estimated_work_units"
  ]
}
```

### `magnetic_reorder`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-main-track-reorder-v1",
  "commands": [
    "timeline.edit:reorder",
    "timeline.compose:linked_edit"
  ],
  "features": [
    "stable_multiselection_before_anchor_or_end",
    "gapless_integer_tick_main_track",
    "displaced_shot_linked_audio",
    "original_host_rider_offsets",
    "sync_lock_opt_out",
    "explicit_link_priority",
    "locked_group_and_negative_time_rejection",
    "author_window_curve_reverse_freeze_and_nested_content_preservation",
    "sequence_subtitle_clock_compensation",
    "compatible_collision_lanes",
    "explicit_preserve_or_drop_broken_transition_policy",
    "full_before_after_plan",
    "existing_snapshot_transaction_idempotency_and_package_roundtrip",
    "opt_in_cross_cut_sync_author_window_partition_and_link_regions"
  ],
  "limits": [
    "logical_tick_boundaries_not_screen_distance_snapping",
    "initial_main_overlap_rejected",
    "conflicting_linked_main_deltas_rejected",
    "sync_span_policy_reject_is_legacy_default_split_is_magnetic_default",
    "effect_or_ducking_bus_lane_relocation_rejected",
    "markers_remain_absolute",
    "track_and_sequence_processing_evaluates_at_new_timeline_positions",
    "20000_clip_admission_not_total_process_RSS_or_long_film_acceptance",
    "no_claim_of_all_capcut_gestures_or_full_function_and_quality_parity"
  ],
  "runtime": "python-standard-library-no-media-process-model-browser-or-network"
}
```

### `magnetic_mode`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-magnetic-mode-v1",
  "commands": [
    "timeline.edit:magnet",
    "timeline.edit:shift",
    "timeline.edit:remove",
    "timeline.compose:append_clip",
    "timeline.compose:append_sequence_clip",
    "timeline.compose:remove_clip",
    "timeline.compose:slide_clip",
    "timeline.compose:trim_clip"
  ],
  "features": [
    "persistent_sequence_editing_magnetic",
    "gapless_main_invariant",
    "nearest_integer_tick_cut_earlier_tie",
    "sync_default_on_with_explicit_opt_out",
    "full_author_sync_partition",
    "native_package_and_fragment_preservation"
  ],
  "limits": [
    "not_all_capcut_gestures",
    "absolute_author_setters_keep_semantics_use_relative_retime_for_following",
    "no_screen_pixel_snap",
    "markers_and_bus_automation_remain_absolute",
    "partial_tracking_and_real_transition_endpoint_cuts_reject",
    "natural_audio_quality_and_long_film_resources_unaccepted"
  ]
}
```

### `complete_output_retime`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-complete-output-retime-v1",
  "commands": [
    "timeline.edit:retime",
    "timeline.compose:retime_clip"
  ],
  "features": [
    "relative_complete_visible_author_output",
    "editable_author_sequences",
    "constant_and_bounded_curved_speed",
    "reverse_and_compound_freeze",
    "partial_linked_host_clock",
    "multi_main_right_to_left_ripple",
    "background_sync_ripple_or_explicit_retime",
    "original_rights_and_package_closure",
    "complete_audio_bus_context",
    "exact_hold_knots_and_merged_equal_native_tempos",
    "editable_external_blend_opacity_clock_maps",
    "native_alpha_only_blend_commands",
    "blend_clock_package_and_fragment_closure"
  ],
  "limits": [
    "absolute_author_setters_keep_their_existing_semantics",
    "direct_transition_tracking_endpoints_reject",
    "blend_clock_4096_points_16_maps_1MiB_and_shared_root_command_budget",
    "continuous_blend_parameters_are_not_arbitrary_old_raster_mask_identity",
    "isolated_ancestors_transform_already_rasterized_child_frames",
    "markers_and_root_bus_automation_remain_absolute",
    "existing_native_graph_quotas",
    "natural_audio_and_full_capcut_parity_not_accepted"
  ]
}
```

### `linked_editing`

```json
{
  "status": "implemented_with_limits",
  "engine": "agent-tick-linked-edit-v1",
  "commands": [
    "timeline.edit",
    "timeline.compose:linked_edit"
  ],
  "features": [
    "native_integer_tick_plans",
    "explicit_or_lowest_video_main_track",
    "persistent_clip_links",
    "merge_link_groups",
    "unlink_orphans",
    "linked_whole_clip_remove",
    "linked_whole_clip_shift",
    "single_gap_and_batch_gap_closing",
    "sync_common_room_and_shortfall",
    "track_sync_opt_out",
    "main_track_riders_and_anchored_music_beds",
    "collision_lane_processing_gate",
    "atomic_locked_link_rejection",
    "subtitle_sequence_clock_offset",
    "tracking_reference_rebinding",
    "read_only_dry_run",
    "optional_stale_project_hash_gate",
    "snapshot_transaction_and_idempotency"
  ],
  "limits": [
    "whole_clip_planning_not_insert_overwrite_roll_or_source_trim",
    "sync_shortfall_keeps_all_reached_tracks_together_no_single_track_fallback",
    "markers_keep_absolute_sequence_ticks",
    "new_lanes_use_next_order_and_copy_processing",
    "audio_effect_bus_relocation_rejected",
    "external_authoring_semantics_and_subtitle_offsets_report_unsupported",
    "no_claim_of_all_capcut_magnet_gestures_or_full_parity"
  ],
  "source_revision": "b138595d4c2d1fa5262b4a8a8c7cd98187c4b077",
  "source_license": "MIT",
  "runtime": "python-standard-library-no-node-browser-or-network"
}
```

### `media`

```json
{
  "status": "implemented",
  "features": [
    "probe",
    "local_ingest",
    "image_loop",
    "proxy",
    "thumbnail",
    "waveform",
    "scene_change",
    "silence",
    "beat_anchors",
    "heuristic_highlights",
    "highlight_rough_cut_apply",
    "beat_cut_timeline",
    "multicam_audio_sync",
    "multicam_switch_plan",
    "relink_by_hash",
    "relink_by_unique_name",
    "local_template_tracking",
    "local_visual_model_tracking_adapter",
    "local_multi_object_tracking",
    "native_yolov10_onnx_cpu",
    "native_motion_association",
    "tracking_clip_model_rights_dependencies",
    "visual_adapter_registry",
    "local_tracking_bind_to_visual_clip",
    "local_auto_reframe",
    "smart_cut_silence",
    "smart_cut_transcript_phrases",
    "smart_cut_linked_audio",
    "stabilize_vidstab_two_pass"
  ],
  "tracking_contract": "local_template_matching_emits_confidence_and_transform_keyframes",
  "multicam_source_coverage": {
    "status": "implemented_with_limits",
    "version": "0.6.0",
    "coverage_clock": "native-video-first-last-intervals-v1",
    "coverage_evidence": "source_sha256_native_pts_duration_time_base_and_demux_origin",
    "dry_run_cache_contract": "read_verified_indexes_or_probe_without_cache_writes",
    "unknown_video_coverage_contract": "return_audio_only_sync_with_diagnostics_but_refuse_camera_switch_authoring",
    "source_shortfall_default": "reject",
    "source_shortfall_choices": [
      "reject",
      "trim",
      "stretch"
    ],
    "trim_contract": "intersect_camera_coverage_in_reference_clock_preserve_calibrated_rate_and_timeline_gaps",
    "stretch_contract": "explicit_clamp_or_slow_changes_event_sync_and_emits_warning",
    "apply_contract": "reject_locked_tracks_and_sub_tick_segments_preserve_authored_duration_and_requested_output_window",
    "audio_source_clock": "native-decoded-audio-interval-clock-v1",
    "limits": [
      "fixed_offset_default_or_explicit_affine_clock",
      "unknown_final_native_frame_duration_rejects",
      "full_source_index_probe_on_cache_miss",
      "offset_estimate_uses_bounded_50hz_audio_envelope",
      "native_audio_start_uses_first_pts_zero_without_async",
      "discontinuous_audio_timestamp_quality_unaccepted",
      "legacy_function_input_without_native_coverage_warns_container_only",
      "timeline_placement_is_quantized_to_project_ticks",
      "no_automatic_audio_track_or_semantic_camera_director",
      "natural_multicam_quality_unaccepted"
    ]
  },
  "multicam_clock": {
    "status": "implemented_with_limits",
    "protocol": "multicam-affine-clock-v1",
    "command": "media.multicam",
    "default_model": "offset",
    "explicit_model": "affine",
    "forward_mapping": "source_seconds=offset_seconds+source_per_reference*reference_seconds",
    "features": [
      "distributed_prefix_windows",
      "complete_window_pearson",
      "parabolic_subsample_peak",
      "robust_slope_fit",
      "three_alignment_passes",
      "anchor_residual_and_ambiguity_evidence",
      "source_ID_and_SHA_binding",
      "sealed_model_content",
      "native_coverage_inverse_mapping",
      "explicit_extrapolation_gate"
    ],
    "bounds": {
      "prefix_seconds": 600,
      "max_drift_ppm": 20000,
      "default_max_drift_ppm": 5000,
      "anchors": [
        3,
        31
      ],
      "window_seconds": [
        4,
        60
      ]
    },
    "limits": [
      "single_affine_clock_only",
      "low_confidence_or_nonlinear_clock_rejects_without_offset_fallback",
      "no_discontinuous_clock_or_distributed_full_long_file_sampling",
      "model_digest_detects_content_changes_but_is_not_a_trusted_signature",
      "reference_audio_track_remains_explicit",
      "natural_multicam_HDR_long_RSS_playback_listening_and_full_CapCut_parity_unaccepted"
    ]
  },
  "source_audio_clock": {
    "status": "implemented_with_limits",
    "protocol": "native-decoded-audio-interval-clock-v1",
    "normalization": "native_decoded_intervals_before_float_resampling_and_source_selection",
    "leading_source_gap": "silence_samples",
    "internal_source_gap": "zero_samples_at_native_rate",
    "internal_source_overlap": "later_decoded_frame_overwrites_earlier_samples",
    "paths": [
      "scalar_reverse",
      "speed_curve",
      "nested_audio",
      "offline_R3_source_decode",
      "multicam_audio_envelope"
    ],
    "async_clock_drift_correction": false,
    "limits": [
      "native_PCM_interval_controls",
      "arbitrary_compressed_codec_priming_requires_separate_acceptance",
      "audio_normalization_itself_does_not_estimate_clock_drift",
      "natural_HDR_long_RSS_listening_and_full_CapCut_parity_unaccepted"
    ]
  },
  "mask_tracking": {
    "status": "implemented_with_limits",
    "engine": "local-mask-bbox-tracking-v1",
    "commands": [
      "media.track",
      "media.track-bind",
      "media.reframe"
    ],
    "features": [
      "registered_encoded_alpha_or_explicit_luma_mask",
      "source_clock_offset",
      "bounded_mask_review",
      "explicit_checkpoint_gate",
      "nonempty_dense_range_gate",
      "scene_cut_gate",
      "boundary_interpolation",
      "terminal_hold",
      "source_clip_canvas_binding",
      "mask_and_source_rights_closure",
      "failed_report_survives_metadata_rollback"
    ],
    "limits": [
      "caller_selects_mask_identity_and_extent",
      "bbox_is_not_pose_or_reidentification",
      "confidence_means_nonempty_not_model_score",
      "geometry_follows_supplied_mask_errors",
      "display_aspect_must_match",
      "persistent_canvas_binding_requires_existing_square_pixel_zero_rotation_CFR_source_contract",
      "reframe_apply_rejects_intrinsic_geometry_that_changes_display_dimensions",
      "interpolation_and_sampling_are_explicit_approximations",
      "decode_storage_budget_excludes_total_ram_and_ffmpeg",
      "semantic_segmentation_and_broad_natural_video_quality_unaccepted"
    ]
  },
  "alpha_fit_padding_contract": "declared_alpha_rasters_and_transparent_output_use_RGBA_transparent_letterbox_padding_before_layer_transform_and_compositing;_ordinary_opaque_fit_keeps_black_letterbox",
  "visual_adapter_contract": "media_adapter_registers_hash_verified_local_command_json_tracking_runner;v1_validates_single_object_frames_and_v2_validates_unique_object_trajectories_before_keyframes",
  "tracking_bind_contract": "legacy_source_normalized_bake_or_explicit_source_clip_timeline_canvas_binding_with_source_hash_observations_and_render_time_recompilation",
  "canvas_tracking_binding": {
    "status": "implemented_with_limits",
    "version": "timeline-canvas-v1",
    "limits_scope": "features_and_limits_below_describe_legacy_bake; explicit_native_Float32_uses_standard_native_float_render.tracking",
    "features": [
      "source_clip_reference",
      "source_sha256_gate",
      "source_clock_observations",
      "crop_fit_fill_stretch",
      "animated_crop",
      "position_scale_anchor_rotation",
      "hflip_vflip",
      "trim_speed_reverse_speed_curve",
      "display_frame_freeze",
      "source_opacity",
      "output_canvas_recompile",
      "crop_visibility",
      "optional_roi_scale",
      "optional_source_rotation",
      "cycle_rejection",
      "detach_preserves_preview_keys",
      "external_export_baking"
    ],
    "max_display_frames": 20000,
    "limits": [
      "direct_cfr_square_pixel_zero_rotation_zero_start_pts_sources",
      "positive_uniform_scale",
      "nested_parent_coordinates_require_review",
      "source_masks_and_occlusion_visibility_require_review",
      "nonlinear_geometry_effects_rejected",
      "observations_are_interpolated_not_new_detections",
      "pixel_and_performance_acceptance_is_fixture_specific"
    ]
  },
  "reframe_contract": "local_template_or_hash_verified_command_json_track_to_normalized_target_aspect_crop_keyframes_with_confidence_and_clipping_warnings",
  "smart_cut_contract": "ffmpeg_local_silencedetect_plus_explicit_local_caption_phrase_ranges_generates_source_clock_ranges_and_can_apply_to_direct_video_and_linked_audio_clips",
  "stabilize_contract": "media_stabilize_runs_local_vidstabdetect_then_vidstabtransform_and_registers_a_project_derived_asset_with_parent_rights",
  "beat_cut_contract": "media_beat_cut_uses_local_ffmpeg_energy_anchors_to_generate_auditable_source_bounded_video_clips_and_can_apply_them_with_snapshot_validation_and_operation_record",
  "highlights_contract": "media_highlights_uses_local_scene_silence_and_optional_beat_evidence_to_write_hash_linked_candidates_and_can_apply_them_to_a_registered_video_track_with_before_snapshot_overlap_gate_validation_and_review_warning",
  "limits": [
    "multicam_requires_two_or_more_local_video_assets_with_audio",
    "multicam_uses_bounded_audio_envelope_cross_correlation_and_does_not_claim_visual_or_speaker_understanding",
    "multicam_low_confidence_offsets_require_waveform_review",
    "multicam_switch_plan_is_fixed_or_explicit_and_does_not_auto_direct_shots",
    "highlights_use_scene_silence_and_optional_beat_heuristics_not_semantic_or_visual_director_understanding",
    "highlights_apply_requires_a_registered_local_video_asset_and_explicit_target_track",
    "highlights_apply_rejects_existing_track_overlap_unless_replace_track_is_explicit",
    "highlights_apply_requires_review_for_semantics_continuity_audio_sync_and_transitions",
    "native_yolo_requires_explicit_python_onnx_coco80_and_local_evidence",
    "native_yolo_is_cpu_only_and_has_no_appearance_reid",
    "native_yolo_rejects_external_onnx_data_and_nonstandard_operator_domains",
    "native_yolo_sampling_is_ffmpeg_fps_resampled_and_budgeted_without_silent_truncation",
    "tracking_can_drift_on_occlusion_scale_change_or_scene_cut",
    "tracking_requires_local_pillow_and_numpy_when_template_engine_is_used",
    "visual_command_json_v1_accepts_only_normalized_single_object_bbox_frames",
    "visual_command_json_v2_validates_unique_object_id_trajectories",
    "multi_object_tracking_apply_requires_explicit_object_selection",
    "multi_object_tracking_all_objects_is_report_only",
    "multi_object_identity_requires_quality_golden_review",
    "visual_command_json_requires_hash_verified_local_model_and_argv_only_runner",
    "visual_command_json_rejects_shell_wrappers_and_network_is_disabled",
    "visual_runner_results_require_quality_golden_review_and_do_not_claim_model_quality",
    "legacy_bind_without_source_clip_references_uses_source_normalized_duration_mapping",
    "tracking_bind_rejects_audio_and_nested_sequence_targets",
    "auto_reframe_requires_direct_constant_speed_forward_clip",
    "auto_reframe_reports_subject_clipping_when_target_aspect_cannot_fit_bbox",
    "smart_cut_rejects_nested_speed_curve_and_freeze_clips",
    "smart_cut_transcript_matching_is_explicit_lexical_cue_granularity_and_does_not_claim_semantic_or_word_level_understanding",
    "smart_cut_removes_silence_only_without_transcript_phrases",
    "beat_cut_uses_energy_peaks_not_musical_semantic_understanding",
    "beat_cut_reuses_or_slows_source_clips_when_interval_exceeds_source_duration",
    "beat_cut_requires_registered_local_video_assets_for_timeline_apply",
    "stabilize_requires_ffmpeg_libvidstab",
    "stabilize_creates_derived_asset_and_does_not_rewrite_timeline",
    "stabilize_quality_depends_on_motion_and_crop_policy"
  ]
}
```

### `library`

```json
{
  "status": "implemented",
  "features": [
    "local_index",
    "deterministic_token_search",
    "subtitle_sidecar_search",
    "media_facets",
    "duration_filter",
    "dimension_filter",
    "audio_presence_filter",
    "sha256_duplicate_groups",
    "incremental_stat_refresh",
    "ffmpeg_average_hash_candidates"
  ],
  "catalog_version": "0.3.0",
  "semantic_index_version": "0.2.0",
  "search_source": "deterministic-local",
  "vector_index": false,
  "visual_similarity_contract": "optional_ffmpeg_ahash_v1_samples_with_hamming_distance_candidate_groups",
  "limits": [
    "no_vlm_embeddings",
    "no_content_understanding_without_local_model",
    "duplicate_detection_is_exact_hash_only",
    "visual_similarity_is_a_review_candidate_not_content_understanding",
    "incremental_refresh_trusts_file_stat_and_sidecar_signatures",
    "subtitle_sidecar_requires_matching_relative_stem"
  ]
}
```

### `look_presets`

```json
{
  "status": "implemented_with_limits",
  "catalog_version": "2.0.0",
  "count": 500,
  "commands": [
    "look.list",
    "look.inspect",
    "look.preview",
    "look.apply"
  ],
  "features": [
    "Chinese_Traditional_Chinese_English_search",
    "hash_verified_per_resource_licenses",
    "offline_previews",
    "500_named_measured_descriptions",
    "MIT_CC0_CC_BY_SA_provenance",
    "alpha2_project_compatibility",
    "clip_or_global_application",
    "replace_or_append",
    "static_strength_0_to_1",
    "project_portable_LUT_license_provenance_and_rights",
    "dry_run",
    "idempotency"
  ],
  "limits": [
    "creative_SDR_encoded_RGB_only",
    "upstream_camera_transfer_not_calibrated",
    "Float32_Log_HDR_apply_rejected",
    "not_official_proprietary_or_Leica_filters",
    "normalized_grid_approximation_measured_per_preset",
    "no_spatial_film_grain_or_AI_beauty"
  ]
}
```

### `lut_library`

```json
{
  "status": "implemented",
  "features": [
    "project_local_registration",
    "sha256_identity",
    "cube_metadata",
    "list",
    "inspect",
    "rights_ledger_registration",
    "lut_id_effect_reference",
    "hash_mismatch_gate",
    "cube_static_intensity_blend",
    "deterministic_intensity_cache"
  ],
  "library_version": "0.1.0",
  "path": "assets/lut-library.json",
  "extensions": [
    ".cube",
    ".3dl",
    ".csp",
    ".dat"
  ],
  "limits": [
    "non_cube_metadata_is_extension_only",
    "non_cube_intensity_unsupported",
    "dynamic_intensity_uses_static_value",
    "snapshot_restore_does_not_delete_newly_copied_asset_files"
  ]
}
```

### `project`

```json
{
  "status": "implemented",
  "features": [
    "init",
    "inspect",
    "migrate",
    "recover",
    "atomic_save",
    "native_process_write_lock",
    "snapshot",
    "restore",
    "before_mutation_snapshot",
    "metadata_transaction_journal",
    "automatic_preflight_recovery"
  ],
  "snapshot_contract": "self_contained_project_rights_lock_json",
  "migration_contract": "project_migrate_creates_before_migrate_snapshot_and_validates_candidate",
  "write_lock_contract": "operations/project-write.lock_serializes_cooperating_cli_read_modify_write_operations_and_returns_retryable_PROJECT_WRITE_LOCKED",
  "transaction_contract": "operations/project-transaction.json_journals_project_rights_lock_and_metadata_records_before_cooperating_cli_mutations;_prepared_journal_is_rolled_back_on_next_start_or_project_recover",
  "failure_diagnostic_contract": "normal_exception_rollback_preserves_explicitly_referenced_versioned_failed_validation_JSON_and_failed_cancelled_partial_operation_records;_crash_recovery_does_not_infer_exception_diagnostics",
  "transaction_scope": [
    "project.json",
    "rights-ledger.json",
    "project.lock.json",
    "assets/lut-library.json",
    "operations_metadata",
    "history_metadata",
    "validation_metadata",
    "exports_metadata"
  ],
  "owned_job_recovery": {
    "command": "project recover --cleanup-jobs",
    "format": "agent-owned-job-workspace-v1",
    "features": [
      "dry_run",
      "native_owner_lease",
      "four_stem_transaction_scoped_workspaces",
      "subtitle_dubbing_and_semantic_workspaces",
      "semantic_tree_identity_and_hash_intents",
      "whole_semantic_tree_preserved_if_any_asset_or_rights_reference_exists",
      "durable_publication_intent",
      "exclusive_same_volume_publish",
      "filesystem_identity_and_hash_check",
      "rollback_before_unreferenced_output_cleanup",
      "referenced_and_modified_outputs_preserved",
      "native_windows_suspended_child_job_assignment_before_application_code",
      "owned_descendants_end_on_owner_exit"
    ],
    "limits": [
      "four_stem_subtitle_dubbing_and_semantic_only",
      "historical_unmanaged_cache_preserved",
      "semantic_diagnostics_retained_until_explicit_cleanup_no_checkpoint_resume",
      "up_to_256_jobs_and_10000_entries_per_workspace",
      "cooperating_local_filesystem_not_hostile_OS_sandbox",
      "job_object_assignment_failure_is_strict_no_unsupervised_fallback",
      "power_loss_and_disk_exhaustion_not_full_acceptance"
    ]
  },
  "limits": [
    "default_recovery_is_metadata_only;_unmanaged_media_render_and_cache_side_effects_remain_preserved",
    "direct_external_json_editors_do_not_join_cli_lock_or_transaction",
    "cross_version_snapshot_migration_is_limited_to_known_legacy_shapes"
  ]
}
```

### `timeline`

```json
{
  "nested_freeze": {
    "version": "1",
    "operation_order": [
      "complete_authored_child_rgba_and_audio_bus",
      "source_trim_speed_reverse",
      "freeze",
      "container_space_effects_and_audio_bus",
      "outer_time_map"
    ],
    "audio_modes": [
      "silence",
      "continue_then_silent_tail"
    ],
    "parent_animation_clock": "containing_sequence_authored_output",
    "internal_graph_data_only": true,
    "intermediate_media_files": 0,
    "limits": [
      "display_frame_hold_duration_quantization_is_reported",
      "composed_audio_retime_does_not_accept_file_only_r3",
      "loop_reverse_buffers_and_total_process_rss_are_not_surface_quota",
      "natural_audio_hdr_vfr_and_full_capcut_equivalence_not_accepted"
    ]
  },
  "status": "implemented",
  "features": [
    "multi_track",
    "append",
    "update",
    "remove",
    "split",
    "ripple_insert",
    "ripple_delete",
    "slip",
    "slide",
    "speed",
    "speed_curve",
    "speed_curve_reverse_reflection",
    "speed_curve_easing",
    "speed_curve_bezier_handles",
    "bounded_speed_clock_compilation",
    "reverse",
    "freeze_frame",
    "crop",
    "crop_position_keyframes",
    "crop_size_keyframes",
    "transform_anchor",
    "motion_preset_keyframes",
    "motion_preset_apply",
    "nested_sequences",
    "independent_sequence_pixel_canvas",
    "sequence_canvas_update",
    "selected_sequence_native_output",
    "single_pass_native_sequence_projection",
    "explicit_sequence_area_sampling",
    "fractional_crop_cell_area",
    "premultiplied_sequence_area_alpha",
    "sequence_projection_working_quota",
    "sequence_sampling_output_override",
    "isolated_sequence_compositing",
    "sequence_parent_canvas_transform",
    "sequence_parent_canvas_crop_mask",
    "sequence_parent_opacity_after_overlap",
    "sequence_group_track_z_order",
    "alpha_preserving_isolated_blend",
    "sequence_group_fade",
    "nested_reverse",
    "nested_reverse_parent_bezier_keyframes",
    "nested_parent_keyframe_layers",
    "nested_analytic_video_clock",
    "nested_covering_source_frame_intervals",
    "nested_subframe_source_trim",
    "nested_mapped_video_eof",
    "nested_global_half_open_output_frames",
    "nested_authored_keyframe_clock",
    "nested_integrated_audio_windows",
    "markers"
  ],
  "limits": [
    "dynamic_crop_uses_fixed_canvas_inverse_sampling",
    "dynamic_crop_cpu_default_explicit_probed_opencl_available",
    "nested_reverse_static_clips_preserve_temporal_order",
    "native_nested_leaf_intervals_preserved_virtual_surfaces_keep_child_cfr",
    "speed_easing_compilation_has_250_microsecond_source_clock_bound_and_1024_segment_limit",
    "speed_bezier_requires_finite_handles_normalized_x_and_positive_interior_speed",
    "source_speed_endpoint_floor_remains_0_01",
    "deep_animated_clock_expressions_have_explicit_4mib_limit",
    "nested_freeze_hold_quantization_is_explicit",
    "sequence_canvas_fps_color_and_sar_are_project_shared",
    "cpu_sequence_working_raster_is_componentwise_max_source_parent_opencl_uses_native_source_target",
    "bilinear_default_retained_explicit_area_has_source_axis_box_kernel",
    "area_general_rotation_is_not_exact_rotated_pixel_polygon_ewa_or_lanczos",
    "projection_quota_excludes_leaf_decoder_encoder_threads_and_concurrent_jobs_rss",
    "leaf_minification_linear_light_hdr_and_natural_quality_unaccepted",
    "sequence_spatial_order_is_child_composite_crop_transform_opacity_effects_mask_fade",
    "group_crop_and_affine_cpu_default_explicit_probed_opencl_available",
    "isolated_compositing_is_8bit_encoded_rgb_not_linear_light_or_hdr_acceptance",
    "default_8bit_group_slide_wipe_unaccepted_explicit_float32_group_spatial_edges_available",
    "nested_audio_tempo_windows_are_limited_to_16384_and_at_least_one_48khz_sample",
    "audio_speed_curve_uses_piecewise_atempo_and_can_have_segment_boundaries"
  ]
}
```

### `motion`

```json
{
  "status": "implemented",
  "catalog_version": "0.1.0",
  "source": "local-catalog",
  "engine": "timeline-keyframes",
  "features": [
    "list",
    "inspect",
    "apply",
    "aliases",
    "bounded_parameters",
    "partial_clip_range",
    "snapshot_before_apply",
    "operation_record"
  ],
  "presets": [
    {
      "id": "zoom_in",
      "aliases": [
        "push_in"
      ],
      "category": "scale",
      "description": "在片段区间内平滑放大画面。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.scale"
      ],
      "parameters": {
        "amount": {
          "type": "number",
          "default": 0.15,
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "相对缩放增量"
        }
      },
      "limits": []
    },
    {
      "id": "zoom_out",
      "aliases": [
        "pull_out"
      ],
      "category": "scale",
      "description": "从放大状态平滑回到原始缩放。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.scale"
      ],
      "parameters": {
        "amount": {
          "type": "number",
          "default": 0.15,
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "相对缩放增量"
        }
      },
      "limits": []
    },
    {
      "id": "pan_left",
      "aliases": [
        "slide_left"
      ],
      "category": "position",
      "description": "沿 X 轴从右向左平移。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.position.x"
      ],
      "parameters": {
        "amount": {
          "type": "number",
          "default": 0.15,
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "归一化位移范围"
        }
      },
      "limits": []
    },
    {
      "id": "pan_right",
      "aliases": [
        "slide_right"
      ],
      "category": "position",
      "description": "沿 X 轴从左向右平移。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.position.x"
      ],
      "parameters": {
        "amount": {
          "type": "number",
          "default": 0.15,
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "归一化位移范围"
        }
      },
      "limits": []
    },
    {
      "id": "pan_up",
      "aliases": [
        "slide_up"
      ],
      "category": "position",
      "description": "沿 Y 轴从下向上平移。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.position.y"
      ],
      "parameters": {
        "amount": {
          "type": "number",
          "default": 0.15,
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "归一化位移范围"
        }
      },
      "limits": []
    },
    {
      "id": "pan_down",
      "aliases": [
        "slide_down"
      ],
      "category": "position",
      "description": "沿 Y 轴从上向下平移。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.position.y"
      ],
      "parameters": {
        "amount": {
          "type": "number",
          "default": 0.15,
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "归一化位移范围"
        }
      },
      "limits": []
    },
    {
      "id": "ken_burns",
      "aliases": [
        "kenburns"
      ],
      "category": "compound",
      "description": "同时平移和缩放的照片式镜头运动。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.scale",
        "transform.position.x",
        "transform.position.y"
      ],
      "parameters": {
        "amount": {
          "type": "number",
          "default": 0.15,
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "缩放及位移强度"
        }
      },
      "limits": []
    },
    {
      "id": "rotate_in",
      "aliases": [
        "rotate_left"
      ],
      "category": "rotation",
      "description": "从指定角度平滑旋转回零度。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.rotation"
      ],
      "parameters": {
        "degrees": {
          "type": "number",
          "default": 8.0,
          "minimum": -360.0,
          "maximum": 360.0,
          "description": "起始旋转角度"
        }
      },
      "limits": []
    },
    {
      "id": "rotate_out",
      "aliases": [
        "rotate_right"
      ],
      "category": "rotation",
      "description": "从零度平滑旋转到指定角度。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.rotation"
      ],
      "parameters": {
        "degrees": {
          "type": "number",
          "default": 8.0,
          "minimum": -360.0,
          "maximum": 360.0,
          "description": "结束旋转角度"
        }
      },
      "limits": []
    },
    {
      "id": "fade_in",
      "aliases": [
        "opacity_in"
      ],
      "category": "opacity",
      "description": "在片段区间内从透明渐入。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.opacity"
      ],
      "parameters": {},
      "limits": [
        "opacity_is_composited_as_a_transform_keyframe"
      ]
    },
    {
      "id": "fade_out",
      "aliases": [
        "opacity_out"
      ],
      "category": "opacity",
      "description": "在片段区间内渐出到透明。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.opacity"
      ],
      "parameters": {},
      "limits": [
        "opacity_is_composited_as_a_transform_keyframe"
      ]
    },
    {
      "id": "shake",
      "aliases": [],
      "category": "position",
      "description": "生成交替位置点的轻微抖动。",
      "engine": "timeline-keyframes",
      "source": "local-catalog",
      "license": "project-code",
      "properties": [
        "transform.position.x"
      ],
      "parameters": {
        "amount": {
          "type": "number",
          "default": 0.15,
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "抖动范围"
        },
        "points": {
          "type": "integer",
          "default": 8,
          "minimum": 2,
          "maximum": 64,
          "description": "关键帧点数"
        }
      },
      "limits": [
        "uses_deterministic_linear_keyframes"
      ]
    }
  ],
  "limits": [
    "presets_write_transform_keyframes_and_do_not_generate_new_media",
    "fixed_catalog_does_not_claim_gui_motion_template_equivalence",
    "keyframe_motion_is_rendered_by_local_ffmpeg_backend"
  ]
}
```

### `templates`

```json
{
  "status": "implemented",
  "features": [
    "local_json_template",
    "typed_variables",
    "enum_variables",
    "numeric_and_string_constraints",
    "default_values",
    "exact_placeholder_type_preservation",
    "inline_string_placeholders",
    "template_snapshot",
    "batch_variant_input",
    "append_clip",
    "update_clip",
    "replace_clip",
    "remove_clip",
    "add_track",
    "update_track",
    "remove_track",
    "add_marker",
    "remove_marker"
  ],
  "variable_types": [
    "any",
    "string",
    "number",
    "integer",
    "boolean",
    "asset",
    "color",
    "enum"
  ],
  "limits": [
    "asset_type_only_validates_string_shape_before_project_asset_and_rights_checks",
    "complex_slot_graphs_and_conditional_operations_pending",
    "expression_evaluation_disabled"
  ]
}
```

### `keyframes`

```json
{
  "status": "implemented",
  "properties": [
    "transform.position.x",
    "transform.position.y",
    "transform.anchor.x",
    "transform.anchor.y",
    "transform.scale",
    "transform.rotation",
    "transform.opacity",
    "blend.opacity",
    "audio.volume",
    "audio.pan",
    "crop.x",
    "crop.y",
    "crop.width",
    "crop.height",
    "mask.x",
    "mask.y",
    "mask.width",
    "mask.height",
    "mask.cx",
    "mask.cy",
    "mask.radius",
    "mask.rx",
    "mask.ry",
    "mask.feather",
    "mask.points.<index>.x",
    "mask.points.<index>.y",
    "mask.segments.<index>.<from|control1|control2|to>.x",
    "mask.segments.<index>.<from|control1|control2|to>.y"
  ],
  "interpolation": [
    "hold",
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "bezier"
  ],
  "bezier_control_points": {
    "forms": [
      [
        "y1",
        "y2"
      ],
      [
        "x1",
        "y1",
        "x2",
        "y2"
      ]
    ],
    "x_range": [
      0,
      1
    ],
    "execution": "normalized cubic easing sampled into a frame-evaluable FFmpeg expression"
  },
  "motion_packs": {
    "status": "implemented_with_limits",
    "engine": "agent-motion-pack-v1",
    "format": "agent-editor-motion-pack",
    "format_version": 1,
    "commands": [
      "motion.pack.list",
      "motion.pack.inspect",
      "motion.pack.create",
      "motion.pack.capture",
      "motion.pack.apply"
    ],
    "builtins": [
      "orbit_focus",
      "arc_push",
      "bezier_sweep",
      "whip_settle",
      "breathe_float",
      "detail_scan"
    ],
    "features": [
      "versioned_portable_json",
      "bounded_affine_parameters",
      "rational_normalized_times",
      "editable_native_transform_keys",
      "complete_authored_easing_capture",
      "presentation_window_offsets",
      "explicit_conflict_replacement",
      "embedded_recipe_and_digests",
      "snapshot_atomic_commit_and_idempotency"
    ],
    "limits": [
      "six_builtins_use_65_linear_samples",
      "transform_properties_only",
      "replaces_whole_selected_property_tracks",
      "sub_tick_point_collisions_rejected",
      "tracking_bindings_rejected",
      "not_3d_camera_solve_or_full_motion_quality_acceptance"
    ]
  }
}
```

### `effects`

```json
{
  "status": "implemented",
  "features": [
    "grayscale",
    "sepia",
    "blur",
    "boxblur",
    "sharpen",
    "brightness",
    "contrast",
    "saturation",
    "hue",
    "hsl",
    "gamma",
    "color_temperature",
    "color_balance",
    "color_wheel",
    "rgb_curves",
    "vignette",
    "noise",
    "invert",
    "posterize",
    "edgedetect",
    "deband",
    "deshake",
    "histeq",
    "gradfun",
    "chroma_key",
    "hflip",
    "vflip",
    "exposure",
    "color_levels",
    "curves",
    "hqdn3d",
    "smartblur",
    "avgblur",
    "tmix",
    "tblend",
    "lens_correction",
    "draw_box",
    "color_contrast",
    "solarize",
    "threshold",
    "deflicker",
    "dctdnoiz",
    "frame_interpolation",
    "effect_catalog_cli",
    "effect_parameter_keyframes",
    "sequence_adjustments",
    "interval_adjustments",
    "lut3d_project_local",
    "lut3d_static_intensity"
  ],
  "catalog_version": "0.11.0",
  "catalog_features": [
    "avgblur",
    "blur",
    "box_blur",
    "brightness",
    "chroma_key",
    "color_balance",
    "color",
    "color_contrast",
    "color_levels",
    "color_temperature",
    "color_wheel",
    "contrast",
    "curves",
    "deband",
    "deflicker",
    "deshake",
    "dctdnoiz",
    "draw_box",
    "edgedetect",
    "exposure",
    "frame_interpolation",
    "gamma",
    "gradfun",
    "grayscale",
    "hsl",
    "hqdn3d",
    "histeq",
    "hflip",
    "hue",
    "invert",
    "lens_correction",
    "lut3d",
    "noise",
    "posterize",
    "rgb_curves",
    "selective_hsl",
    "sepia",
    "sharpen",
    "smartblur",
    "solarize",
    "saturation",
    "tblend",
    "threshold",
    "tmix",
    "vflip",
    "vignette",
    "lens_flare",
    "light_leak",
    "chromatic_aberration",
    "bloom",
    "halation"
  ],
  "catalog_source": "native-and-ffmpeg-local",
  "catalog_contract": "effects.list_and_effects.inspect_return_local_ffmpeg_backend_parameter_limits_and_keyframe_contract",
  "unknown_effect_policy": "RENDER_FEATURE_UNSUPPORTED",
  "effect_keyframe_contract": "brightness_contrast_saturation_hue_hsl_gamma_vignette_use_local_eq_eval_frame_and_hue_frame_expressions",
  "selective_hsl": {
    "status": "implemented_with_limits",
    "engine": "encoded-rgb-eight-band-hsl-v1",
    "backend": "ffmpeg:frei0r",
    "fallback_backends": [
      "ffmpeg:geq"
    ],
    "numeric_channels": 25,
    "native_pixel_kernel": {
      "program_format": "AVKHSL01",
      "policy": "verified-native-auto",
      "distribution": "bundled_Windows_amd64_hash_named_DLL_with_C_source_and_MIT_notice",
      "runtime_compilation": false,
      "program_depth_limit": 128,
      "program_bytes_limit": 32256,
      "parallel_policy": "up_to_three_shared_Windows_background_workers_plus_the_calling_thread",
      "selection_env": "AI_AD_EDITOR_HSL_BACKEND=auto|native|expression"
    },
    "bands_degrees": {
      "red": 0,
      "orange": 30,
      "yellow": 60,
      "green": 120,
      "cyan": 180,
      "blue": 240,
      "purple": 270,
      "magenta": 300
    },
    "features": [
      "independent_hue_saturation_lightness_per_band",
      "animated_final_RGB_intensity",
      "original_hue_circular_triangular_weights",
      "author_clock_expressions_at_actual_frame_PTS",
      "preserve_achromatic_pixels_and_exact_input_alpha",
      "editable_package_and_fragment_transfer"
    ],
    "limits": [
      "encoded_RGB_8bit",
      "64KiB_single_kernel_16MiB_root_expression_bytes",
      "shared_1024_effect_instances_and_2000000_state_samples",
      "no_vendor_algorithm_or_full_CapCut_parity_acceptance"
    ]
  },
  "curve_point_automation": {
    "status": "implemented_with_limits",
    "engine": "native-curve-points-cfr-v1",
    "effects": [
      "curves",
      "rgb_curves"
    ],
    "channels": [
      "all",
      "red",
      "green",
      "blue"
    ],
    "property_pattern": "<channel>.<zero_based_point_index>.<x|y>",
    "point_count_per_channel": [
      1,
      256
    ],
    "coordinate_range": [
      0,
      1
    ],
    "features": [
      "whole_channel_atomic_commands",
      "explicit_RGB_preserved_when_all_animates",
      "complete_author_clock_at_actual_CFR",
      "recursive_shared_effect_budgets",
      "editable_project_package_fragment_rebuild",
      "input_alpha_preserved"
    ],
    "limits": [
      "fixed_topology",
      "six_decimal_8bit_x_bins_must_strictly_increase",
      "natural_cubic_spatial_curve",
      "master_is_all_alias_only_for_curves",
      "animated_channel_forks_static_all_if_no_own_points",
      "not_HDR_or_vendor_color_equivalence"
    ]
  },
  "numeric_effect_automation": {
    "status": "implemented_with_limits",
    "engine": "native-color-command-cfr-v1",
    "effects": [
      "blur",
      "chroma_key",
      "color_balance",
      "color_contrast",
      "color_levels",
      "color_temperature",
      "color_wheel",
      "exposure",
      "lens_correction",
      "lut3d"
    ],
    "numeric_channels": 34,
    "clock": "complete_author_output_sampled_on_actual_CFR_grid",
    "features": [
      "blur_both_axes",
      "lens_k1_k2_center",
      "colorkey_similarity_blend",
      "input_alpha_times_RGB_key_coverage",
      "root_unique_static_and_dynamic_key_alpha_compositors",
      "colorcontrast_seven_numeric_channels",
      "recursive_unique_targets",
      "native_runtime_option_gate",
      "content_addressed_command_files",
      "editable_project_package_fragment_rebuild",
      "shared_recursive_budgets"
    ],
    "limits": [
      "color_tokens_enums_and_plane_selection_remain_static",
      "1024_additional_key_alpha_compositors_per_recursive_root",
      "blur_filters_RGB_and_alpha_planes",
      "colorkey_uses_RGB_distance_not_semantic_matting_or_despill",
      "lens_correction_uses_native_sampling_and_fill",
      "six_decimal_native_values",
      "Bezier_overshoot_clamped",
      "2000000_state_samples_200000_commands_16MiB_1024_targets_per_recursive_root",
      "not_HDR_or_full_CapCut_effect_equivalence"
    ]
  },
  "numeric_color_automation": {
    "status": "implemented_with_limits",
    "engine": "native-color-command-cfr-v1",
    "effects": [
      "color_balance",
      "color_contrast",
      "color_levels",
      "color_temperature",
      "color_wheel",
      "exposure",
      "lut3d"
    ],
    "numeric_channels": 27,
    "clock": "complete_author_output_sampled_on_actual_CFR_grid",
    "features": [
      "recursive_unique_targets",
      "native_runtime_option_gate",
      "content_addressed_command_files",
      "editable_project_and_package_rebuild",
      "independent_text_group_and_interval_adjustments"
    ],
    "limits": [
      "numeric_channels_only",
      "six_decimal_native_values",
      "Bezier_overshoot_clamped",
      "2000000_state_samples_200000_commands_16MiB_1024_targets_per_recursive_root",
      "existing_Kelvin_shadow_RGB_mapping_not_physical_white_balance",
      "not_HDR_color_management_or_CapCut_color_algorithm_equivalence"
    ]
  },
  "adjustment_contract": "settings.adjustments_are_applied_after_track_compositing_in_declared_order; start_tick_and_duration_tick_define_optional_sequence_clock_intervals",
  "limits": [
    "other_unsupported_effect_parameters_use_static_value_with_warning",
    "unlisted_native_filter_automation_remains_static_with_warning",
    "hsl_lightness_maps_to_ffmpeg_hue_brightness",
    "rgb_curves_use_fixed_topology_coordinate_animation",
    "color_wheel_maps_to_ffmpeg_colorbalance_three_way_wheel",
    "curves_accept_one_whitelist_validated_all_master_curve",
    "interval_adjustments_are_video_only_and_reassembled_with_trim_concat",
    "lut_intensity_requires_project_local_cube_for_partial_strength",
    "frame_interpolation_uses_local_minterpolate_and_can_be_cpu_expensive",
    "frame_interpolation_scene_change_detection_is_heuristic"
  ]
}
```

### `compositing`

```json
{
  "status": "implemented",
  "masks": [
    "rectangle",
    "circle",
    "ellipse",
    "path",
    "polygon"
  ],
  "blend_modes": [
    "normal",
    "multiply",
    "screen",
    "overlay",
    "difference",
    "addition",
    "softlight",
    "hardlight"
  ],
  "features": [
    "mask_invert",
    "dynamic_feather_simple_shapes",
    "dynamic_feather_path_polygon",
    "path_cubic_segments",
    "path_curve_control_point_keyframes",
    "blend_opacity_keyframes",
    "rgb_blend_math"
  ],
  "limits": [
    "dynamic_path_uses_fixed_sample_count",
    "path_point_count_is_fixed_per_clip",
    "path_cubic_segments_are_sampled_polygons",
    "path_polygon_feather_uses_inner_edge_distance_approximation",
    "ffmpeg_expression_register_limit_falls_back_to_expanded_expression_with_warning",
    "blend_requires_same_canvas_inputs"
  ]
}
```

### `transitions`

```json
{
  "status": "implemented",
  "features": [
    "fade",
    "crossfade",
    "dissolve",
    "wipe",
    "slide",
    "circlecrop",
    "rectcrop",
    "distance",
    "fadeblack",
    "fadewhite",
    "radial",
    "smooth",
    "circleopen",
    "circleclose",
    "pixelize",
    "zoomin",
    "cover",
    "reveal",
    "diagonal",
    "slice",
    "wind",
    "blur",
    "fadegrays",
    "squeeze",
    "auto_handle_contiguous_clips"
  ],
  "xfade_catalog": "local_ffmpeg_xfade",
  "float32_native": {
    "status": "implemented_with_limits",
    "protocol": "linear-premultiplied-float32-transitions-v1",
    "selection": "settings.pixel_pipeline.engine=float32-native-v1",
    "patterns": [
      "circleclose",
      "circlecrop",
      "circleopen",
      "coverdown",
      "coverleft",
      "coverright",
      "coverup",
      "diagbl",
      "diagbr",
      "diagtl",
      "diagtr",
      "dip_black",
      "dip_white",
      "distance",
      "fade",
      "fadeblack",
      "fadefast",
      "fadegrays",
      "fadeslow",
      "fadewhite",
      "hblur",
      "hlslice",
      "hlwind",
      "horzclose",
      "horzopen",
      "hrslice",
      "hrwind",
      "pixelize",
      "radial",
      "rectcrop",
      "revealdown",
      "revealleft",
      "revealright",
      "revealup",
      "slidedown",
      "slideleft",
      "slideright",
      "slideup",
      "smoothdown",
      "smoothleft",
      "smoothright",
      "smoothup",
      "squeezeh",
      "squeezev",
      "vdslice",
      "vdwind",
      "vertclose",
      "vertopen",
      "vuslice",
      "vuwind",
      "wipebl",
      "wipebr",
      "wipedown",
      "wipeleft",
      "wiperight",
      "wipetl",
      "wipetr",
      "wipeup",
      "zoomin"
    ],
    "features": [
      "linear_light_premultiplied_RGBA",
      "xfade_spatial_catalog",
      "original_author_clocks",
      "group_wipe_slide_and_other_spatial_edges",
      "exact_overlap_pairs",
      "real_source_handles",
      "linked_audio_envelopes",
      "odd_frame_cut_fraction",
      "nested_reverse_left_limits",
      "bounded_tiles_and_row_blur",
      "cancellation",
      "no_authored_project_rewrite"
    ],
    "limits": [
      "CPU_only",
      "explicit_float_pipeline_not_default_migration",
      "no_automatic_tail_clone",
      "pair_modes_require_normal",
      "nonintersecting_pair_windows",
      "fadefast_fadeslow_require_visible_RGB_0_to_1",
      "unmatched_edges_target_transparent",
      "linear_alpha_math_not_integer_xfade_bit_parity",
      "quota_not_total_RSS",
      "natural_longform_HDR_and_full_CapCut_parity_unaccepted"
    ],
    "license": "LGPL-2.1-or-later;see float_transitions_NOTICE.txt"
  },
  "source_handle_editor": {
    "engine": "agent-source-transition-v1",
    "command": "timeline transition",
    "actions": [
      "add",
      "resize",
      "remove"
    ],
    "field": "sequence.source_transitions",
    "features": [
      "real_source_windows",
      "unchanged_authored_clips_and_duration",
      "linked_audio_pairs",
      "independent_linear_audio_envelopes",
      "multi_cut_chain",
      "constant_speed_and_reverse",
      "native_black_white_dip",
      "transitioned_child_inline_video_surface",
      "ancestor_trim_reverse_constant_and_curve_retime",
      "authored_child_audio_envelope_clock",
      "original_audio_sources_and_buses",
      "inline_surface_working_quota",
      "scoped_child_render_warnings"
    ],
    "limits": [
      "cut_endpoints_are_direct_video_and_explicit_audio_tracks",
      "exact_display_frame_and_integer_source_tick_grid",
      "source_span_must_match_constant_speed",
      "cut_endpoints_do_not_accept_sequence_curve_freeze_tracking_or_per_clip_blend",
      "transitioned_child_can_be_frozen_after_complete_child_composition",
      "legacy_transition_fields_conflict",
      "nonintersecting_windows",
      "inline_surfaces_are_encoded_rgb_not_linear_light_hdr",
      "inline_quota_is_not_process_rss",
      "all_natural_quality_hdr_vfr_and_performance_not_accepted"
    ]
  },
  "condition": "manual transitions require adjacent clips with matching overlap handles; auto_handle=true or handle_policy=auto enables contiguous clips and preserves their authored timeline length with an explicit tail-padding approximation warning"
}
```

### `subtitles`

```json
{
  "status": "implemented",
  "float32_native": {
    "status": "implemented_with_limits",
    "protocol": "native-glyph-linear-float32-paint-v1",
    "selection": "settings.pixel_pipeline.engine=float32-native-v1",
    "commands": [
      "preview.frame",
      "preview.range",
      "render",
      "render.resume",
      "queue.run"
    ],
    "features": [
      "independent_text_track_and_inline_captions",
      "explicit_registered_font_SHA",
      "linear_Float32_box_shadow_border_fill_source_over",
      "256_code_native_coverage_calibration",
      "whole_paragraph_binary_word_highlights",
      "whole_prefix_grapheme_typewriter_snapshots",
      "original_presentation_clock_and_parent_reverse_left_limits",
      "plain_SRT_half_open_cues",
      "fade_slide_pop_bounce_rotate",
      "clip_effects_transforms_masks_crop_blend_and_transitions",
      "bounded_LRU_surface_cache",
      "owned_native_process_cancellation_cleanup",
      "native_byte_component_coverage_and_tiled_Float64_source_over",
      "content_addressed_prefix_and_geometry_mask_LRU",
      "4K_text_with_explicit_workspace_admission"
    ],
    "GPU": {
      "selection": "explicit_projection_acceleration_off_prefer_require",
      "engine": "render-owned-float32-opencl-v1",
      "scope": [
        "ordered_color_components",
        "paragraph_source_over",
        "binary_word_selection"
      ],
      "glyph_rasterization": "CPU"
    },
    "limits": [
      "glyph_coverage_8bit_authored_colors_and_composition_Float32",
      "SRT_plain_text_only_rich_ASS_SSA_VTT_not_ported",
      "explicit_font_and_native_metrics_required",
      "stateful_positions_and_wall_clock_expansion_rejected",
      "bidi_and_internal_word_clusters_pending",
      "typewriter_512_graphemes_highlight_128_ranges",
      "four_Float32_surfaces_plus_native_masks_tiles_two_cache_limits_admission_not_peak_RSS",
      "sequential_native_CPU_coverage_rasters_explicit_GPU_color_composition",
      "not_realtime_HDR_or_full_CapCut_acceptance"
    ]
  },
  "limits_scope": "remaining subtitle limits describe the default encoded-RGB path; float32_native has its own explicit contract",
  "formats": [
    "srt",
    "vtt",
    "ass",
    "ssa",
    "ttml"
  ],
  "features": [
    "validate",
    "normalize_srt",
    "ttml_clock_parser",
    "inline_drawtext",
    "independent_text_track",
    "nested_authored_subtitle_clock",
    "nested_reverse_caption_boundaries",
    "external_caption_time_base",
    "external_caption_local_font",
    "nested_text_animation_and_transition_clock",
    "drawtext_line_spacing",
    "drawtext_border_and_shadow",
    "drawtext_alignment",
    "drawtext_text_shaping",
    "subtitle_width_wrap_font_metrics",
    "local_font_advance_metrics",
    "fade_text_animation",
    "slide_text_animation",
    "typewriter_text_animation",
    "native_whole_prefix_typewriter",
    "fixed_paragraph_typewriter_anchor",
    "native_typewriter_multiline_baselines",
    "cfr_authored_clock_typewriter_commands",
    "word_highlight_native_animation_composition",
    "pop_text_animation",
    "bounce_text_animation",
    "independent_rotate_text_layer",
    "independent_text_transform_keyframes",
    "independent_text_masks",
    "independent_text_blend",
    "mixed_video_text_track_order",
    "independent_text_fade_transitions",
    "independent_text_spatial_transitions",
    "word_timing_highlight",
    "word_timing_source_matching",
    "whole_paragraph_word_color_selection",
    "native_ffmpeg_text_metrics",
    "word_timing_multiline_source_mapping",
    "word_timing_no_double_paint",
    "native_multiline_paragraph_baselines",
    "literal_newline_without_extra_glyph",
    "straight_text_color_alpha",
    "ordered_box_shadow_border_fill_coverage",
    "local_ffmpeg_color_parser",
    "color_alpha_times_animation_and_layer_opacity",
    "local_asr_to_srt",
    "registered_native_whisper_asr",
    "local_font_ingest",
    "subtitle_cer_evaluation",
    "ffmpeg_whisper_cpp_asr",
    "subtitle_asset_registration",
    "subtitle_track_apply_with_snapshot"
  ],
  "limits": [
    "embedded_rotate_text_is_approximated",
    "dynamic_raster_inline_animation_alpha_keeps_explicit_approximation",
    "word_highlight_native_engine_metrics_required",
    "word_highlight_dynamic_inline_raster_suppressed_with_warning",
    "word_highlight_bidi_and_internal_shaping_clusters_rejected",
    "word_highlight_position_stateful_expressions_rejected",
    "word_highlight_negative_line_spacing_requires_review",
    "dynamic_raster_inline_color_keeps_explicit_approximation",
    "text_color_8bit_encoded_rgb_not_linear_light",
    "random_text_colors_rejected",
    "external_ass_color_semantics_require_separate_acceptance",
    "word_highlight_measurement_budget_128_ranges_512_queries",
    "caption_freeze_clock_keeps_explicit_approximation",
    "subtitle_asset_animation_keeps_explicit_approximation",
    "external_caption_sequence_clock_is_default",
    "drawtext_frame_counter_remains_final_frame_counter",
    "independent_text_complex_transition_handles_pending",
    "advanced_text_layout_exact_metrics_pending",
    "subtitle_width_wrap_falls_back_to_average_glyph_width_without_local_font",
    "word_timing_general_overlapping_lines_pending",
    "multiline_box_smaller_than_paragraph_rejected",
    "dynamic_inline_typewriter_layout_keeps_explicit_approximation",
    "native_typewriter_requires_runtime_text_commands",
    "native_typewriter_512_graphemes_128_lines_16384_commands_4MiB",
    "native_typewriter_bidi_and_stateful_position_rejected",
    "typewriter_general_VFR_and_freeze_pending",
    "complex_bidi_layout_pending",
    "ffmpeg_whisper_requires_an_explicit_local_model_file_and_whisper_enabled_ffmpeg_build",
    "automatic_subtitle_apply_requires_a_registered_source_asset_for_rights_inheritance"
  ]
}
```

### `audio`

```json
{
  "status": "implemented",
  "features": [
    "multi_track_mix",
    "track_mute",
    "track_solo",
    "track_volume",
    "track_pan",
    "track_role",
    "volume_automation",
    "pan_automation",
    "stereo_preserving_numeric_pan",
    "fade",
    "denoise",
    "compressor",
    "equalizer",
    "highpass",
    "lowpass",
    "dialogue_enhance",
    "pitch_shift",
    "reverb",
    "loudnorm",
    "ducking",
    "pan",
    "beat_anchors",
    "freeze_audio_silence_at_timeline_position",
    "sequence_duration_audio_padding",
    "extract_audio_asset",
    "derived_audio_rights_inheritance",
    "audio_track_apply",
    "mid_side_separation_approximation",
    "separation_asset_pair",
    "selected_stem_audio_track_apply",
    "offline_adapter_registry",
    "adapter_hash_verification",
    "adapter_rights_registration",
    "command_json_audio_runner",
    "native_offline_hdemucs_vocals_accompaniment",
    "explicit_separation_cpu_cuda",
    "disk_backed_overlap_add",
    "float_pcm_mixture_consistency",
    "derived_stem_model_rights_dependency",
    "separation_failure_output_cleanup",
    "explicit_local_rubberband_r3_offline",
    "whole_clip_audio_time_map",
    "pinned_audio_stretcher_artifacts",
    "float32_audio_stretch_intermediate",
    "pcm_24_32_float_mkv_output",
    "unity_tempo_bypasses_buffered_stretch",
    "explicit_r3_together_apart_channel_mode",
    "channel_mode_in_immutable_audio_cache_key",
    "explicit_r3_real_source_context",
    "r3_context_rational_edge_map",
    "r3_context_exact_authored_sample_crop",
    "hierarchical_sequence_audio_buses",
    "track_effects_after_clip_sum",
    "container_effects_after_sequence_sum",
    "float_sum_without_input_normalization",
    "sample_grid_audio_placement",
    "sample_evaluated_gain_envelopes",
    "container_authored_audio_clock",
    "sequence_local_audio_solo",
    "audio_mute_preserves_video",
    "scope_local_multi_input_ducking",
    "audio_bus_manifest_nodes",
    "source_contained_atempo_context",
    "tempo_core_integrated_sample_anchors",
    "audio_tempo_context_manifest",
    "actual_retimed_source_end_selection",
    "terminal_context_pcm_preflight_limit"
  ],
  "native_separation_engine": "torchaudio-hdemucs-local-v1",
  "limits": [
    "extract_audio_uses_first_local_audio_stream",
    "extract_audio_outputs_lossless_pcm_wav",
    "mid_side_separation_is_phase_based_and_approximate",
    "true_vocal_background_separation_requires_a_registered_offline_model_adapter",
    "native_hdemucs_requires_existing_compatible_pt_pth_weights_native_python_torch_torchaudio_numpy_and_evidence",
    "native_hdemucs_is_stereo_44100_model_with_explicit_device_no_download_or_fallback",
    "native_hdemucs_max_7200_seconds_and_segment_1_to_20_seconds",
    "native_hdemucs_accompaniment_is_original_minus_model_vocals_not_independent_four_stem_export",
    "native_hdemucs_float_wav_can_exceed_unit_peak_and_requires_listening_license_and_broad_music_review",
    "legacy_demucs_uvr_openunmix_onnx_engines_without_dedicated_runner_remain_metadata_only",
    "unknown_audio_adapter_never_falls_back_to_mid_side",
    "command_json_runner_accepts_one_local_json_request_and_requires_exact_center_side_wav_outputs",
    "command_json_runner_rejects_cmd_and_bat_shell_wrappers",
    "command_json_runner_quality_and_model_license_require_project_golden_and_rights_review",
    "freeze_audio_continue_uses_tail_padding",
    "unconfigured_audio_speed_curve_uses_piecewise_atempo",
    "offline_r3_requires_explicit_local_executable_dependency_and_license_hashes",
    "offline_r3_time_map_is_not_sample_exact_local_content_alignment",
    "offline_r3_ultra_short_pitch_and_listening_unaccepted",
    "offline_r3_together_default_preserves_v26_centre_focus",
    "offline_r3_apart_can_degrade_mono_compatibility",
    "offline_r3_channel_mode_does_not_solve_ultra_short_pitch",
    "r3_source_context_0_to_1000_ms_default_zero",
    "r3_context_requires_finite_source_bound_and_real_audio_handles",
    "r3_expanded_pcm_stays_bounded_512mib_per_file",
    "r3_context_may_include_nearby_transients_and_does_not_accept_phase_or_natural_quality",
    "offline_r3_pcm_buffers_are_bounded_to_512mib_each_and_8_channels",
    "float_sum_can_exceed_unit_peak_without_automatic_limiter",
    "legacy_multitrack_mix_level_changes_when_input_normalization_is_removed",
    "bus_effects_except_volume_and_pan_are_static",
    "track_fades_require_clip_authored_envelopes_and_emit_unsupported_warning",
    "duck_detector_is_sequence_local_and_pre_current_track_processing",
    "named_send_return_feedback_and_spatial_buses_are_not_implemented",
    "context_atempo_controlled_dc_interior_and_end_checks_do_not_accept_arbitrary_material",
    "terminal_atempo_context_has_64mib_estimated_float_pcm_limit_not_total_ram_acceptance",
    "context_atempo_is_not_continuous_phase_pitch_transient_or_listening_acceptance"
  ]
}
```

### `four_stem_separation`

```json
{
  "status": "implemented_with_limits",
  "engine": "torchaudio-hdemucs-four-stem-local-v1",
  "commands": [
    "audio adapter register/list/inspect",
    "audio separate-stems"
  ],
  "features": [
    "four_independent_neural_estimates",
    "drums_bass_other_vocals",
    "shared_source_normalization_and_overlap_add",
    "raw_sum_error_diagnostics",
    "stereo_float_wav",
    "four_editable_audio_tracks",
    "source_and_model_rights_dependencies",
    "auto_cpu_cuda",
    "explicit_gpu_index",
    "finite_total_timeout",
    "cancel_and_failure_cleanup",
    "command_scoped_artifact_locks",
    "no_implicit_downloads"
  ],
  "limits": [
    "explicit_existing_compatible_checkpoint_and_native_torch_torchaudio_required",
    "model_is_stereo_44100_hdemucs_high_with_four_fixed_sources",
    "single_job_max_1800_seconds",
    "segment_1_to_20_seconds_overlap_0_to_0_75",
    "auto_falls_back_only_at_gpu_preflight",
    "no_runtime_oom_or_model_failure_fallback",
    "raw_estimate_sum_is_not_projected_to_mixture",
    "no_independent_normalization_or_limiter_float_peaks_may_exceed_one",
    "editing_preserves_original_tracks_review_duplicate_mix_before_render",
    "natural_leakage_artifacts_listening_and_checkpoint_license_acceptance_remain_open",
    "runtime_versions_recorded_but_complete_os_and_python_dependency_closure_not_bundled"
  ]
}
```

### `render`

```json
{
  "affine_expression_reuse": {
    "engine": "native-geq-scanline-v2",
    "status": "implemented_with_limits",
    "scope": [
      "fixed_canvas_affine_video_filters",
      "dynamic_crop_fit_fill_stretch",
      "sequence_crop_fit_TRS_bilinear_and_area"
    ],
    "invariants": [
      "refresh_at_each_plane_slice_scanline_X_zero",
      "pure_expressions_only",
      "preserve_half_pixel_coordinates_and_arithmetic_order",
      "premultiplied_float_bilinear_sampler_unchanged",
      "pixel_dependent_or_stateful_expressions_keep_legacy_evaluation"
    ],
    "sequence_cache": {
      "selection": "greedy_expanded_expression_length_without_numeric_approximation",
      "bilinear_persistent_registers": [
        0,
        1,
        2,
        3,
        4,
        5,
        8,
        9
      ],
      "area_persistent_registers": [
        0,
        1,
        2,
        3,
        4,
        5
      ],
      "pixel_scratch_registers_disjoint": true,
      "area_kernel": "unchanged_source_axis_fractional_box_integral"
    },
    "limits": [
      "CPU_composition",
      "not_all_geq_filters",
      "no_global_frame_cache",
      "not_full_4K_long_form_or_GPU_composition_acceptance"
    ]
  },
  "status": "implemented",
  "video_frame_clock": {
    "protocol": "rational-local-video-clock-v1",
    "input": "registered_native_stream_time_base_or_read_only_local_probe",
    "working_grid": "exact_common_multiple_of_input_denominator_author_TPS_and_output_FPS_numerator",
    "output_interval": "global_CFR_half_open_ceil_start_to_ceil_end",
    "forward_source_anchor": "requested_author_source_in_tick_with_covering_frame_prefix",
    "complete_window_eof": "bounded_known_frame_count_guard",
    "short_ordinary_sources_padded": false,
    "ordinary_input_VFR_normalized": false,
    "native_denominator_limit": 2147483647,
    "limits": [
      "finite_nonlinear_retime_resolution",
      "unrepresentable_grid_rejected",
      "cumulative_decode_before_source_in",
      "virtual_inline_surfaces_keep_child_CFR",
      "general_nested_VFR_effect_combinations_require_separate_acceptance",
      "source_index_and_balanced_expression_budgets"
    ],
    "ordinary_reverse": "original_native_frame_intervals_mirrored_with_fractional_source_bounds"
  },
  "features": [
    "ffmpeg_local",
    "output_profiles",
    "jsonl_progress",
    "cancel_file",
    "safe_resume",
    "float_premultiplied_alpha_media_resize",
    "float_premultiplied_alpha_text_resize",
    "float_premultiplied_alpha_affine_sampling",
    "float_premultiplied_alpha_dynamic_crop",
    "straight_alpha_independent_text_raster"
  ],
  "resume_contract": "rebuild_from_validated_plan_when_project_and_input_hashes_match",
  "limits": [
    "resume_is_not_partial_frame_checkpoint",
    "changed_inputs_are_rejected",
    "other_long_tasks_progress_pending",
    "other_effect_warps_require_separate_alpha_sampling_review",
    "float_alpha_resize_uses_existing_encoded_RGB_transfer_not_linear_light",
    "float_affine_and_dynamic_crop_sampling_have_no_4k_throughput_or_total_memory_acceptance"
  ]
}
```

### `queue`

```json
{
  "status": "implemented",
  "features": [
    "enqueue",
    "list",
    "inspect",
    "sequential_run",
    "bounded_local_workers",
    "continue_on_error_worker_guard",
    "serial_metadata_commit",
    "explicit_retry",
    "cancel_pending",
    "cancel_running",
    "cancel_ack_while_project_lock_held",
    "opt_in_same_invocation_result_reuse"
  ],
  "state_file": "operations/render-queue.json",
  "execution": "single_process_default_sequential_or_explicit_bounded_local_ffmpeg_workers",
  "worker_contract": "workers_only_render_frozen_project_snapshots_and_quality; project_outputs_operations_and_queue_metadata_commit_serially",
  "cancel_contract": "pending_cancel_confirms_when_queue_lock_is_free; running_or_lock_contended_cancel_acknowledges_marker_then_queue_run_confirms_terminal_state",
  "limits": [
    "workers_greater_than_one_requires_continue_on_error",
    "reuse_requires_serial_workers_new_targets_and_explicit_local_dependencies",
    "reuse_has_no_cross_invocation_cache",
    "reuse_rejects_hardware_probes_external_stretch_tracking_bindings_and_font_fallback",
    "distributed_workers_pending",
    "priority_and_fairness_pending",
    "cross_machine_artifacts_pending",
    "running_cancel_confirmation_is_eventual"
  ]
}
```

### `quality`

```json
{
  "status": "implemented",
  "features": [
    "stream_presence",
    "canvas",
    "duration",
    "av_duration_delta",
    "authored_cfr_sample_endpoints",
    "av_start_and_end_residuals",
    "matroska_stream_duration_tags",
    "blackdetect_optional",
    "ebur128_optional",
    "target_lufs_gate",
    "true_peak_gate",
    "fail_on_black",
    "waveform_scope",
    "vectorscope",
    "histogram_scope",
    "golden_manifest_capture",
    "golden_manifest_verify",
    "golden_hash_and_metric_drift_report",
    "mask_per_frame_extent",
    "mask_explicit_positive_negative_checks",
    "mask_scene_boundary_review"
  ],
  "scope_engine": "ffmpeg-local",
  "scope_artifacts": [
    "png",
    "json_report"
  ],
  "defaults": {
    "max_av_sync_ms": 80.0,
    "lufs_tolerance": 2.0
  },
  "av_clock_contract": "known_author_duration_predicts_video_ceil_CFR_and_audio_ceil_sample_endpoints; raw_delta_is_preserved; unchanged_limit_applies_to_start_end_and_quantization_residuals; quality_CLI_requires_explicit_sequence_binding; missing_stream_duration_is_unverified",
  "limits": [
    "true_peak_gate_requires_expensive_scan_and_ffmpeg_ebur128",
    "scope_images_are_review_artifacts_not_automatic_color_judgement",
    "mask_extent_and_assertions_do_not_establish_object_identity_or_full_segmentation_quality",
    "mask_temporal_iou_is_not_motion_compensated",
    "mask_decoded_storage_budget_excludes_ffmpeg_and_total_process_ram",
    "golden_is_exact_for_the_captured_local_artifact_and_requires_the_same_local_media_and_settings",
    "cross_device_visual_thresholds_pending"
  ]
}
```

### `output`

```json
{
  "status": "implemented",
  "profiles": [
    "vertical",
    "square",
    "landscape",
    "vertical_720",
    "landscape_720",
    "custom"
  ],
  "containers": [
    "mp4",
    "webm",
    "mkv"
  ],
  "video_codecs": [
    "libx264",
    "libx265",
    "libvpx-vp9",
    "libvpx",
    "libaom-av1"
  ],
  "pixel_formats": [
    "yuv420p",
    "yuv422p",
    "yuv444p",
    "yuv420p10le",
    "yuv422p10le",
    "yuv444p10le",
    "yuva420p"
  ],
  "audio_codecs": [
    "aac",
    "libopus",
    "opus",
    "pcm_s16le",
    "pcm_s24le",
    "pcm_s32le",
    "pcm_f32le"
  ],
  "defaults": {
    "container": "mp4",
    "video_codec": "libx264",
    "audio_codec": "aac"
  },
  "color_metadata_contract": "settings.color_is_forwarded_as_ffmpeg_primaries_transfer_matrix_range; optional_hdr_tone_map_uses_local_zscale_float_tonemap_to_bt709",
  "tone_mapping": [
    "linear",
    "gamma",
    "clip",
    "reinhard",
    "hable",
    "mobius"
  ],
  "alpha_contract": "separate_original_8_bit_alpha_from_RGB_to_YUV_conversion; VP9_CRF0_without_bitrate_uses_lossless_YUV_alpha; tagged_VPX_input_uses_explicit_libvpx_decoder_and_straight_RGBA_before_blending; VP8_transparency_disables_auto_alt_ref",
  "limits": [
    "codec availability still depends on the local FFmpeg build",
    "10_bit_requires_encoder_and_container_support",
    "transparent_output_requires_webm_vpx_and_yuva420p",
    "webm requires VPX/AV1 video plus Opus audio",
    "lossless_VP9_YUV_alpha_is_not_lossless_RGBA_RGB_420_color",
    "VP8_and_nonzero_CRF_or_bitrate_alpha_are_lossy",
    "resampling_rotation_HDR_and_other_decoders_need_separate_precision_acceptance"
  ]
}
```

### `interoperability`

```json
{
  "status": "degraded",
  "formats": [
    "agent-json",
    "package",
    "otio",
    "kdenlive-xml",
    "jianying-draft-json"
  ],
  "package_semantic_data": {
    "owned_namespace_preserved": true,
    "external_uri_only_derived_rebinding": true,
    "import_staged_before_publication": true,
    "inner_index_profile_dataset_vector_source_preview_and_rights_hash_checks": true,
    "external_native_runtime_bundled_or_retrusted": false,
    "legacy_flattened_semantic_package_repair": false
  },
  "features": [
    "agent_json_exact_roundtrip",
    "portable_agent_project_package",
    "package_asset_uri_rewrite",
    "package_sha256_manifest",
    "package_path_traversal_and_symlink_gate",
    "otio_stack_track_gap_clip",
    "otio_tick_rational_time",
    "otio_metadata_clip_recovery",
    "kdenlive_profile_frame_rate",
    "kdenlive_blank_gap_mapping",
    "kdenlive_entry_frame_mapping",
    "jianying_plaintext_import_export",
    "draft_microsecond_tick_mapping",
    "draft_transform_crop_linear_keyframe_mapping",
    "draft_text_local_font_mapping",
    "draft_explicit_embedded_audio",
    "draft_strict_loss_gate",
    "draft_redacted_source_sidecar",
    "local_reference_only"
  ],
  "report_states": [
    "Exact",
    "Mapped",
    "Approximate",
    "Baked",
    "Unsupported",
    "Failed"
  ],
  "limits": [
    "package_excludes_renders_cache_operations_and_history",
    "package_requires_all_referenced_assets_to_exist_locally",
    "complex_effects_and_advanced_animation_require_explicit_mapping_report",
    "otio_sequential_track_cannot_represent_overlapping_clips_without_metadata",
    "kdenlive_effect_filters_and_text_generators_require_explicit_mapping_or_bake",
    "foreign_relative_references_are_resolved_against_interchange_file",
    "draft_profile_jianying_plaintext_v1_uses_version_360000_and_new_version_110_0_0_without_runtime_compatibility_claim",
    "draft_encrypted_files_are_rejected_without_decryption",
    "draft_private_resources_are_preserved_redacted_and_never_downloaded",
    "draft_text_layout_and_bezier_are_approximate",
    "draft_imported_media_and_fonts_have_unverified_rights",
    "draft_strict_mode_rejects_approximate_baked_unsupported_or_failed_before_target_write",
    "draft_export_uses_first_sequence_and_preserves_unmapped_parameters_in_sidecar"
  ]
}
```

### `segmentation`

```json
{
  "status": "local_adapter_only",
  "engine": "transformers-sam2-video-local-v1",
  "protocol": "agent-video-sam2-segmentation-v1",
  "commands": [
    "media.adapter.register",
    "media.adapter.inspect",
    "media.matting"
  ],
  "features": [
    "native_torch_cpu_or_cuda",
    "explicit_safetensors_only",
    "positive_negative_points_and_boxes",
    "multi_object_union_or_selection",
    "future_frame_corrections",
    "explicit_scene_reset",
    "streamed_frames_and_pruned_memory",
    "binary_or_probability_alpha",
    "lossless_rgba_audio_and_rights_pipeline"
  ],
  "limits": [
    "local_prompt_json_required",
    "normalized_output_coordinates_and_cfr_frame_indices",
    "max_8_objects_256_events_32_points_per_object_event",
    "512_mib_session_tensor_budget_excludes_model_and_process_memory",
    "no_device_fallback_or_runtime_downloads",
    "forward_corrections_do_not_rewrite_prior_frames",
    "explicit_reset_requires_new_prompts",
    "segmentation_probability_is_not_physical_matte",
    "broad_advertising_quality_and_commercial_rights_acceptance_pending"
  ]
}
```

### `video_outpainting`

```json
{
  "status": "local_adapter_only",
  "engine": "agent-local-outpaint-v1",
  "engines": [
    "torchscript-lama-local-v1",
    "diffusers-wan-vace-local-v1"
  ],
  "protocol": "agent-video-outpaint-mask-v1",
  "commands": [
    "media.outpaint"
  ],
  "features": [
    "explicit_larger_canvas_and_integer_original_placement",
    "single_source_decode_and_same_pts_generated_outer_mask",
    "all_normalized_original_rgba_samples_protected",
    "opaque_generated_region_and_lossless_qtrle_roundtrip",
    "framewise_lama_or_joint_vace_windows_with_explicit_prompt",
    "editable_hash_bound_recipe_in_assets_and_packages",
    "original_audio_rights_cancel_timeout_idempotency_and_transactions"
  ],
  "limits": [
    "existing_local_models_and_native_python_required_no_downloads",
    "sdr_8bit_display_cfr_after_explicit_source_normalization",
    "no_source_crop_no_mask_grow_or_feather_no_guaranteed_hidden_scene_recovery",
    "8192_per_edge_16777216_pixels_and_existing_model_buffer_cuda_budgets",
    "harmonic_correction_is_spatial_not_structural_or_temporal_reconstruction",
    "generated_structure_seams_texture_temporal_quality_and_model_rights_require_review",
    "natural_quality_and_full_capcut_parity_unaccepted"
  ]
}
```

### `inpainting`

```json
{
  "status": "local_adapter_only",
  "engine": "torchscript-lama-local-v1",
  "engines": [
    "torchscript-lama-local-v1",
    "diffusers-wan-vace-local-v1"
  ],
  "protocol": "agent-video-lama-inpainting-v1",
  "commands": [
    "media.adapter.register",
    "media.adapter.inspect",
    "media.inpaint"
  ],
  "features": [
    "native_torch_cpu_or_cuda",
    "explicit_local_torchscript",
    "alpha_or_luma_asset_mask",
    "mask_clock_and_geometry_validation",
    "bounded_roi_inference",
    "explicit_direct_or_harmonic_region_color_correction",
    "selected_pixel_solver_budget_and_convergence_reports",
    "lazy_model_load_after_mask_admission",
    "outside_rgb_and_source_alpha_preserved",
    "qtrle_rgba_decode_hash",
    "audio_timeline_and_rights_dependencies",
    "cancel_timeout_and_rollback"
  ],
  "limitations": [
    "framewise_image_inpainting_not_joint_temporal_video_model",
    "texture_flicker_and_occlusion_require_review",
    "harmonic_color_correction_is_spatial_not_structural_or_temporal_repair",
    "no_text_prompt_generative_fill",
    "external_model_license_and_broad_quality_not_accepted"
  ]
}
```

### `generative_video_editing`

```json
{
  "status": "local_adapter_only",
  "engine": "diffusers-wan-vace-local-v1",
  "protocol": "agent-video-wan-vace-inpainting-v1",
  "commands": [
    "media.adapter.register",
    "media.adapter.inspect",
    "media.inpaint",
    "media.generate"
  ],
  "features": [
    "fixed_local_wan_vace_1_3b_safetensors",
    "cuda_bfloat16_and_float32_vae",
    "staged_local_text_encoder_offload_and_release",
    "verbatim_prompt_and_negative_prompt_no_truncation",
    "seed_steps_guidance_and_conditioning",
    "explicit_flow_shift",
    "bounded_model_input_scale_1_2_4",
    "actual_window_input_shapes",
    "joint_4k_plus_1_frame_windows",
    "explicit_scene_boundaries_and_overlap_blending",
    "source_alpha_and_outside_rgb_preserved",
    "shared_audio_rights_cancel_and_recovery",
    "harmonic_region_color_correction_after_float_window_mix",
    "selected_pixel_solver_budget_and_convergence_reports"
  ],
  "cuda_admission": {
    "policy": "cuda-uuid-physical-and-torch-free-v1",
    "headroom_mib": 768,
    "physical_query": "local_nvidia_smi_uuid",
    "stages": [
      "text_weights",
      "video_weights",
      "each_nonempty_window"
    ],
    "idle_cache_release": "current_worker_before_each_admission",
    "text_offload_hooks_removed_before_video": true,
    "reservation": false,
    "oom_guarantee": false
  },
  "complete_video_generation": {
    "protocol": "local-vace-conditioned-video-generation-v1",
    "command": "media.generate",
    "modes": [
      "text-to-video",
      "image-to-video",
      "last-frame-to-video",
      "first-last-to-video"
    ],
    "conditioning": "grey_rgb127_white_mask_generate_black_mask_known_first_last_images",
    "known_endpoints": "explicit_fit_black_flatten_sdr_rgb_retained_and_independently_decode_hash_checked",
    "image_fit": [
      "reject",
      "contain",
      "cover",
      "stretch"
    ],
    "bounds": {
      "raster_multiple": 16,
      "minimum_edge": 64,
      "maximum_edge": 2048,
      "frames": [
        5,
        4097
      ],
      "fps": [
        1,
        60
      ],
      "duration_seconds": 600,
      "window_array_bytes": 536870912,
      "image_pixels": 16777216
    },
    "features": [
      "real_cuda_inference_shared_native_pipeline",
      "condition_rgba_roundtrip",
      "exact_requested_frame_count_rational_fps",
      "digest_bound_portable_recipe",
      "registered_generated_asset_and_editable_track_apply",
      "model_image_rights_dependencies",
      "owned_job_crash_recovery_and_transaction_rollback",
      "cancel_timeout_before_publication"
    ],
    "audio_generated": false,
    "quality_accepted": false,
    "model_session": {
      "status": "implemented_with_limits",
      "commands": [
        "media.model-session.start",
        "media.model-session.status",
        "media.model-session.stop"
      ],
      "option": "--model-session",
      "transport": "authenticated_native_windows_named_pipe_json_and_raw_bytes",
      "integrity": "full_hashes_once_under_resident_deny_write_locks_then_overlapping_consumer_locks",
      "reuse": [
        "cuda_video_weights",
        "same_prompt_embeddings"
      ],
      "per_job_reset": [
        "scheduler",
        "previous_generated_context",
        "window_metrics"
      ],
      "budgets": {
        "idle_seconds": [
          10,
          3600
        ],
        "lifetime_seconds": [
          60,
          86400
        ],
        "max_jobs": [
          1,
          1024
        ]
      },
      "limits": [
        "one_project_one_adapter_one_prompt_pair",
        "new_prompt_requires_new_session",
        "serial_jobs_only",
        "first_job_loads_weights",
        "cancel_disconnect_deadline_failure_retires_owned_process",
        "not_a_global_memory_reservation_or_multi_gpu_scheduler"
      ]
    },
    "limits": [
      "opaque_8bit_sdr_output_not_hdr_or_matte_generation",
      "no_implicit_model_install_or_cpu_fallback",
      "retained_endpoints_are_not_proof_of_generated_identity_or_motion",
      "prompt_motion_identity_seams_and_natural_quality_require_review",
      "unverified_generated_rights_default_to_internal"
    ]
  },
  "generation_parameters": {
    "flow_shift": {
      "default": 3.0,
      "minimum": 0.1,
      "maximum": 32.0
    },
    "model_input_scale": {
      "default": 1,
      "choices": [
        1,
        2,
        4
      ]
    },
    "temporal_context": {
      "default": "none",
      "choices": [
        "none",
        "previous"
      ],
      "previous_requires_positive_overlap": true,
      "source": "same_scene_previous_emitted_generated_rgba",
      "output": "retain_emitted_prefix",
      "extra_owned_array_bound": "width*height*4*window_overlap",
      "controller_and_model_input_traces": true,
      "generated_context_is_ground_truth": false,
      "natural_quality_accepted": false
    }
  },
  "limitations": [
    "joint_windows_not_global_full_video_attention",
    "harmonic_color_correction_is_spatial_not_structural_or_temporal_repair",
    "temporal_seams_identity_texture_and_occlusion_need_review",
    "base_model_max_edge_precedes_explicit_input_scale",
    "scaled_array_budget_excludes_model_and_torch_memory_and_is_not_a_cuda_oom_guarantee",
    "no_cross_device_byte_determinism",
    "commercial_rights_broad_quality_and_full_jianying_parity_unaccepted"
  ]
}
```

### `matting`

```json
{
  "status": "local_adapter_only",
  "engine": "rvm-onnx-cpu-matting-v1",
  "protocol": "agent-video-rvm-matting-v1",
  "commands": [
    "media.adapter.register",
    "media.adapter.inspect",
    "media.matting"
  ],
  "features": [
    "native_onnx_cpu",
    "recurrent_human_video_alpha",
    "soft_straight_alpha",
    "input_alpha_multiply",
    "bounded_rgba_pipeline",
    "qtrle_argb_mov",
    "rgba_decode_hash_verification",
    "audio_offset_and_range_preservation",
    "source_rotation_and_sar_normalization",
    "source_model_rights_dependencies",
    "timeline_apply",
    "cancel_timeout_process_cleanup"
  ],
  "limits": [
    "explicit_existing_fp32_onnx_native_python_and_evidence_required",
    "no_download_install_or_provider_fallback",
    "self_contained_onnx_without_custom_domains",
    "sdr_rgb_8bit_only_hdr_requires_explicit_tone_map",
    "cfr_resampling_and_partial_tail_frame_extension_are_reported",
    "max_16777216_pixels_per_frame",
    "default_18000_frames_budget_is_explicitly_adjustable",
    "project_media_file_size_limit_applies_to_lossless_output",
    "human_only_quality_hair_motion_occlusion_scene_cuts_require_review",
    "python_network_guard_is_not_an_os_sandbox",
    "broad_advertising_quality_and_model_commercial_license_acceptance_pending"
  ]
}
```

### `forced_alignment`

```json
{
  "status": "local_adapter_only",
  "engine": "transformers-wav2vec2-ctc-local-v1",
  "protocol": "agent-video-ctc-align-v1",
  "commands": [
    "asr.adapter.register",
    "asr.adapter.inspect",
    "subtitle.align"
  ],
  "boundary_modes": [
    "ctc",
    "activity"
  ],
  "activity_algorithm": "ctc-guided-activity-v3",
  "features": [
    "native_offline_wav2vec2_ctc_safetensors",
    "explicit_corrected_text_or_srt_windows",
    "full_repeated_token_viterbi",
    "original_codepoint_mapping",
    "explicit_case_and_granularity",
    "receptive_field_sample_grid",
    "overlapped_30_second_inference_windows",
    "character_and_word_highlight_track_apply",
    "source_transcript_model_rights_closure",
    "command_scoped_native_read_locks",
    "idempotency_cancel_timeout_and_transaction_rollback",
    "explicit_pcm_conditioned_isolated_word_activity",
    "raw_character_and_word_timing_preserved",
    "controller_recomputes_activity_from_hash_bound_pcm",
    "ambiguous_continuous_activity_preserves_ctc"
  ],
  "limits": [
    "1800_seconds_16384_codepoints_8192_tokens",
    "512_mib_emissions_64_million_traceback_cells_excludes_total_process_and_model_memory",
    "activity_requires_explicit_whitespace_granularity",
    "activity_is_not_phonetic_truth_or_continuous_internal_word_alignment",
    "noise_music_and_wrong_transcripts_require_review",
    "oov_or_script_conversion_requires_explicit_user_corrected_text",
    "posterior_is_not_calibrated_accuracy",
    "wrong_transcripts_can_be_forced_into_audio",
    "python_network_guard_is_not_an_os_sandbox",
    "singing_diarization_broad_natural_quality_and_full_capcut_equivalence_unaccepted"
  ]
}
```

### `ai`

```json
{
  "status": "local_adapter_only",
  "features": [
    "offline_transformers_asr_gate",
    "registered_native_whisper_asr",
    "asr_model_integrity_registry",
    "asr_long_form_attention_mask",
    "subtitle_cer_evaluation",
    "ffmpeg_whisper_cpp_asr",
    "local_asr_subtitle_generation",
    "local_flite_tts",
    "registered_soulx_chinese_tts",
    "tts_voice_transcript_registry",
    "tts_generated_audio_asset_and_track_apply",
    "tts_model_voice_rights_dependencies",
    "heuristic_highlights",
    "highlight_rough_cut_apply",
    "local_ad_plan",
    "local_ad_plan_apply",
    "editable_ad_storyboard",
    "multiformat_ad_variants",
    "scoped_ad_shot_revision",
    "local_template_tracking",
    "offline_model_registry"
  ],
  "ad_storyboard": {
    "engine": "agent-ad-storyboard-v1",
    "commands": [
      "ad.storyboard",
      "ad.build",
      "ad.revise"
    ],
    "features": [
      "explicit_brief_and_local_assets",
      "rational_fps_frame_apportionment",
      "independent_variant_canvases_and_durations",
      "editable_picture_caption_voice_source_music_tracks",
      "same_language_reviewed_subtitle_voice_batch",
      "native_input_read_locks",
      "plan_and_project_digest_gates",
      "complete_voice_window_gate",
      "font_metric_overflow_gate",
      "scoped_revision_preserves_unselected_edits",
      "snapshot_and_atomic_project_commit"
    ],
    "limits": [
      "creative_decisions_supplied_by_caller",
      "no_implicit_semantic_selection_or_claim_generation",
      "no_implicit_voice_truncation_or_music_loop",
      "complex_manual_clip_splits_require_explicit_replanning",
      "natural_ad_quality_and_independent_agent_benchmark_pending"
    ]
  },
  "network": "disabled",
  "asr_contract": "asr.adapter_registers_explicit_native_python_safetensors_and_evidence_for_hash_verified_isolated_whisper_inference_and_subtitle_model_rights_dependencies_with_legacy_local_model_path_gates_preserved",
  "tts_contract": "tts.adapter_and_voice_register_explicit_local_soulx_artifacts_and_exact_transcript_then_tts.synthesize_hash_verifies_and_runs_isolated_native_python_without_network_or_downloads_and_registers_generated_wav_with_optional_audio_track_apply",
  "limits": [
    "model_weights_must_be_provided_locally",
    "registered_whisper_requires_native_python_with_local_torch_and_transformers",
    "whisper_segment_timing_is_not_word_alignment_or_diarization",
    "whisper_cer_does_not_convert_chinese_scripts",
    "whisper_broad_ad_corpus_acceptance_pending",
    "python_network_audit_is_not_an_os_sandbox",
    "ffmpeg_whisper_requires_whisper_enabled_local_ffmpeg",
    "flite_voice_inventory_depends_on_local_ffmpeg_build",
    "flite_adapter_is_ascii_english_only",
    "soulx_hf_full_bf16_weights_and_cuda_required",
    "soulx_single_voice_per_synthesis_and_max_2000_text_characters",
    "soulx_model_reference_text_and_output_rights_need_explicit_review",
    "soulx_emotion_dialect_multispeaker_and_broad_quality_acceptance_pending",
    "heuristic_highlights_do_not_claim_semantic_or_visual_director_understanding"
  ]
}
```

### `rights`

```json
{
  "status": "implemented",
  "schema_version": "0.2.0",
  "features": [
    "local_ledger",
    "immutable_revisions",
    "status_transitions",
    "takedown_and_dispute_gate",
    "channel_gate",
    "expiry_gate",
    "audit_history",
    "template_dependency_closure",
    "derived_asset_closure",
    "hash_snapshot_gate",
    "atomic_batch_update",
    "release_manifest",
    "historical_impact_report",
    "historical_disposition_decisions",
    "disposition_approval_and_cancellation_chain",
    "replacement_dependency_gate",
    "approved_replace_delete_release_block",
    "local_disposition_apply_with_snapshot"
  ],
  "commands": [
    "rights.check",
    "rights.list",
    "rights.history",
    "rights.update",
    "rights.batch-update",
    "rights.impact",
    "rights.retract",
    "rights.decide",
    "rights.apply",
    "rights.export"
  ],
  "limits": [
    "disposition_apply_updates_current_project_references_and_preserves_historical_media_files",
    "license_policy_is_field_and_status_based_without_external_network_verification"
  ]
}
```

### `subtitle_dubbing`

```json
{
  "status": "implemented_with_limits",
  "protocol": "agent-subtitle-dubbing-v1",
  "commands": [
    "dub.subtitles"
  ],
  "features": [
    "strict_srt_source_order_and_millisecond_clocks",
    "english_chinese_translation",
    "one_kokoro_initialization_per_batch",
    "explicit_per_cue_voice_map",
    "cpu_cuda_auto_per_task",
    "whole_utterance_bounded_speed_regeneration",
    "independent_actual_wav_sample_fit_checks",
    "original_and_retry_audio_retained",
    "editable_audio_and_bilingual_subtitle_clips",
    "single_project_transaction",
    "owned_crash_recovery",
    "overflow_evidence_and_explicit_cleanup",
    "source_translation_model_and_voice_rights_dependencies",
    "total_timeout_cancel_and_dry_run"
  ],
  "limits": [
    "existing_native_pinned_model_packs_required_no_downloads",
    "plain_utf8_srt_1mib_1000_cues",
    "english_chinese_only_3000_characters_and_300_seconds_per_cue",
    "kokoro_cuda_device_zero_only",
    "max_three_complete_generations_and_speed_two",
    "explicit_overlap_mix_and_track_admission",
    "millisecond_divisible_project_timebase_required",
    "cue_timing_not_phonetic_alignment_or_lip_sync",
    "source_translation_voice_rights_and_natural_quality_require_review",
    "full_g19_and_capcut_parity_unaccepted"
  ]
}
```

### `policy`

```json
{
  "status": "implemented",
  "network": "disabled",
  "features": [
    "local_reference_validation",
    "project_json_remote_reference_audit",
    "provider_marker_detection",
    "remote_media_rejection"
  ],
  "limits": [
    "research_and_documentation_urls_are_not_runtime_inputs",
    "local_models_must_be_registered_by_path_and_hash"
  ]
}
```

## CLI 0.1.5 / F50 / S18 / K08: visual semantic retrieval

[Complete workflow / 完整流程](SEMANTIC_RETRIEVAL.md) · [Skill reference](../../skills/agent-ffmpeg-local-editor/references/semantic-retrieval.md) · [Actual output](CASES.md#c14-semantic-retrieval).

Explicit local SigLIP2 image/video-sample embeddings; Chinese/English/reference-image search; native PTS, previews, editable source points, integrity and auto/cpu/cuda. 16 positive queries pass on this small familiar set; Chinese negation and both open-set queries fail expected selection/rejection. No natural-action, cross-shot identity, audio matching or large-library acceptance. One sampled point does not define clip duration.


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


### `procedural_particles`

```json
{
  "status": "implemented_with_limits",
  "protocol": "analytic-seeded-particle-source-v1",
  "catalog_version": "1.0.0",
  "recipes": [
    "snow",
    "confetti",
    "embers",
    "bokeh",
    "rain",
    "sparkles"
  ],
  "commands": [
    "vfx.list",
    "vfx.inspect",
    "vfx.apply",
    "vfx.update",
    "vfx.show",
    "vfx.animate",
    "vfx.animation-properties"
  ],
  "source": "editable_clip_generator_not_baked_media",
  "network": false,
  "external_assets": [],
  "license": "MIT",
  "backend": "explicit_native_linear_Float32_timeline",
  "GPU": "render_owned_OpenCL_particle_coverage_glow_ordered_over_with_32x32_CSR_bins",
  "CPU": [
    "seed_hash",
    "analytic_birth_trajectory",
    "tile_index",
    "color_conversion",
    "ordinary_encoder"
  ],
  "source_clock": "declared_rational_CFR_half_open_intervals_exact_reverse_left_limits",
  "emitter_animation": {
    "protocol": "source-anchored-emitter-keyframes-v1",
    "clock": "original_generator_ticks",
    "properties": 21,
    "max_points_per_property": 64,
    "interpolations": [
      "hold",
      "linear",
      "ease_in",
      "ease_out",
      "ease_in_out",
      "bezier"
    ],
    "rate": "nonnegative_exact_rational_integral_with_64_step_rational_inverse_and_stable_birth_ID",
    "birth_sampled": [
      "lifetime",
      "position",
      "spread",
      "velocity",
      "acceleration",
      "rotation",
      "spin",
      "sway",
      "twinkle"
    ],
    "live_source_sampled": [
      "size",
      "size_end",
      "aspect",
      "shape",
      "softness",
      "glow",
      "colors",
      "color_end",
      "opacity",
      "fade_in",
      "fade_out"
    ],
    "palette_interpolation": "linear_BT709_not_hex_or_sRGB_code_interpolation",
    "discrete": "shape_and_nullable_end_color_changes_hold_only",
    "budget": "max_animated_rate_times_max_animated_lifetime_across_emitters",
    "edit": "one_property_per_explicit_emitter;replacement_opt_in;snapshot_and_idempotency"
  },
  "integration": [
    "native_render",
    "native_preview",
    "cache",
    "persistent_queue",
    "clip_windows",
    "speed_curves",
    "reverse",
    "freeze",
    "TRS_keys",
    "masks",
    "blend",
    "nested_sequences",
    "source_slip_and_handles",
    "agent_json",
    "project_package",
    "local_OTIO_metadata_roundtrip"
  ],
  "limits": {
    "emitters": 16,
    "live_particle_reservation": 4096,
    "pixels": 8847360,
    "fps": [
      1,
      120
    ],
    "source_seconds": 600,
    "candidate_pixel_visits_per_frame": 134217728
  },
  "unsupported": [
    "legacy_FFmpeg_graph",
    "3D",
    "collisions",
    "depth_occlusion",
    "fluid_simulation",
    "AI_effect_generation",
    "foreign_OTIO_particle_execution"
  ],
  "runtime_failure_CPU_fallback": false,
  "natural_footage_quality_accepted": false,
  "goal_G06_complete": false
}
```

[CLI0.1.35 exact installed capability snapshot](procedural-particles-capabilities-cli-0.1.35.json).

[CLI0.1.36 exact installed capability snapshot](gpu-dispatch-capabilities-cli-0.1.36.json).

[CLI0.1.37 exact installed capability snapshot](emitter-animation-capabilities-cli-0.1.37.json).

### `optical_effects`

```json
{
  "status": "implemented_with_limits",
  "protocol": "author-clock-linear-float32-optical-effects-v1",
  "effects": [
    "lens_flare",
    "light_leak",
    "chromatic_aberration"
  ],
  "selection": "ordinary_clip_effects_or_selected_sequence_adjustments",
  "commands": [
    "effects.list",
    "effects.inspect",
    "timeline.compose",
    "preview.frame",
    "preview.range",
    "render",
    "queue"
  ],
  "backend": "CPU_or_actual_render_owned_OpenCL_binary64_math_Float32_surfaces",
  "signal": "explicit_linear_working_RGB;numeric_tint_in_working_primaries",
  "alpha": "original_coverage_bits_preserved;hidden_RGB_ignored_in_active_sampling",
  "sampling": "premultiplied_bilinear_channel_displacement;clamp_or_transparent_edges",
  "clock": "original_author_tick;shared_hold_linear_ease_in_ease_out_ease_in_out_bezier",
  "static_fields": [
    "ghosts_0_to_12",
    "chromatic_edge_mode"
  ],
  "resource_policy": "existing_full_spatial_scratch_admission_and_bounded_CPU_tiles;owned_GPU_quotas",
  "license": "MIT_original_formulas_and_kernels",
  "network": false,
  "external_assets": [],
  "unsupported": [
    "legacy_FFmpeg_graph",
    "automatic_bright_source_detection",
    "physical_lens_calibration",
    "depth_occlusion",
    "HDR_acceptance",
    "natural_footage_quality_acceptance"
  ],
  "goal_G06_complete": false
}
```

[CLI0.1.38 exact installed capability snapshot](optical-effects-capabilities-cli-0.1.38.json).

### `highlight_glow`

```json
{
  "status": "implemented_with_limits",
  "protocol": "highlight-derived-separable-float32-glow-v1",
  "effects": [
    "bloom",
    "halation"
  ],
  "aliases": [
    "highlight_bloom",
    "film_halation"
  ],
  "commands": [
    "effects.list",
    "effects.inspect",
    "timeline.compose",
    "preview.frame",
    "preview.range",
    "render",
    "queue"
  ],
  "selection": "ordinary_clip_effects_or_selected_sequence_adjustments",
  "signal": "explicit_linear_working_RGB;D65_bt709_display_p3_or_bt2020_luminance",
  "highlight_extraction": "positive_RGB_coverage_weighted_soft_knee_no_hidden_RGB_light",
  "spread": "normalized_three_sigma_separable_Gaussian_FIR;Float32_per_stage;binary64_accumulation",
  "halation": "nonnegative_blurred_light_minus_editable_bright_core;linear_RGB_tint",
  "backend": "CPU_or_actual_render_owned_OpenCL;four_kernels_and_one_final_download",
  "clock": "original_author_tick;six_shared_numeric_easings;edge_enum_static",
  "alpha": "input_bits_preserved;active_fully_transparent_RGB_zero",
  "limits": {
    "sigma_source_pixels": [
      0,
      32
    ],
    "neighbor_samples_per_frame": 4294967296,
    "workspace_bytes": 805306368,
    "workspace_is_peak_RSS": false
  },
  "network": false,
  "external_assets": [],
  "license": "MIT_original_implementation",
  "unsupported": [
    "physical_lens_or_emulsion_calibration",
    "automatic_artistic_selection",
    "HDR_acceptance",
    "natural_footage_quality_acceptance",
    "full_G06_effect_library"
  ],
  "goal_G06_complete": false
}
```

[CLI0.1.39 exact installed capability snapshot](highlight-glow-capabilities-cli-0.1.39.json).

### `native_hdr_display_pipeline`

```json
{
  "status": "implemented_with_limits",
  "protocol": "explicit-display-nits-PQ-HLG-float32-v1",
  "selection": "settings.pixel_pipeline.engine=float32-native-v1; explicit reference_white_nits on every HDR project source/working/output signal",
  "transfers": [
    "pq-st2084",
    "hlg-bt2100"
  ],
  "working": "display-linear Float32 D65 RGB; declared reference_white_nits per signal",
  "features": [
    "PQ_display_EOTF_and_inverse_10000_nits",
    "HLG_RGB_coupled_OOTF_and_inverse",
    "explicit_HLG_display_peak_and_system_gamma_ideal_zero_black",
    "absolute_nit_unit_scaling_and_D65_primary_conversion",
    "native_RGB_and_explicit_progressive_YCbCr_inputs",
    "explicit_input_domain_reject_or_counted_clip",
    "original_author_clock_effects_linear_composition_and_editable_packages",
    "BT2020_NCL_PQ_HLG_ten_bit_delivery_with_matching_VUI",
    "explicit_modified_Reinhard_luminance_SDR_trim_and_SDR_preview",
    "preserved_alpha_bits_tiled_budgets_and_cancellation"
  ],
  "limits": [
    "CPU_tiled_color_conversion_not_GPU_transfer_kernels",
    "only_BT2020_PQ_HLG_native_ten_bit_nonalpha_delivery",
    "no_inferred_luminance_or_metadata_or_automatic_tone_map",
    "no_ICC_chromatic_adaptation_mastering_CLL_dynamic_metadata_or_DolbyVision",
    "HLG_ideal_zero_black_only_explicit_peak_and_gamma",
    "SDR_trim_is_explicit_creative_Reinhard_not_BT2390_or_perceptual_gamut_mapping",
    "natural_HDR_monitor_long_form_and_full_CapCut_acceptance_pending"
  ]
}
```

[CLI0.1.40 exact installed capability snapshot](native-hdr-capabilities-cli-0.1.40.json).

### `native_lip_sync`

```json
{
  "status": "implemented_with_limits",
  "protocol": "agent-native-lipsync-v1",
  "engine": "musetalk-v15-native-cuda-v1",
  "commands": [
    "lipsync.adapter.register",
    "lipsync.adapter.list",
    "lipsync.adapter.inspect",
    "lipsync.generate"
  ],
  "features": [
    "actual_MuseTalk_1_5_UNet_Whisper_tiny_VAE_BiSeNet_CUDA",
    "explicit_image_or_video_and_audio_assets",
    "output_25fps_face_box_linear_keys",
    "explicit_once_hold_or_full_video_loop",
    "semantic_lower_face_blend",
    "straight_alpha_and_outside_region_RGB_preserved",
    "complete_lossless_RGBA_and_PCM_roundtrip",
    "portable_rerunnable_recipe",
    "independent_video_and_audio_clips",
    "owned_cancel_timeout_recovery"
  ],
  "clock": {
    "video_fps": 25,
    "model_audio_sample_rate": 16000,
    "audio_preservation": "original_decoded_float_PCM_sample_rate_and_channels",
    "tail_padding": "less_than_one_video_frame_no_selected_samples_dropped"
  },
  "limits": {
    "trained_face_pixels": [
      256,
      256
    ],
    "duration_seconds": 600,
    "raster_edge_pixels": 4096,
    "batch_frames": [
      1,
      8
    ],
    "owned_array_bytes": 536870912,
    "maximum_asset_bytes": 2147483648
  },
  "network": false,
  "model_downloads": false,
  "CPU_fallback": false,
  "unsupported": [
    "full_body_pose_or_expression_generation",
    "automatic_face_detection_or_tracking",
    "automatic_identity_or_naturalness_acceptance",
    "native_HDR_or_ICC_face_inference",
    "cross_device_bit_determinism",
    "full_digital_human_or_CapCut_parity"
  ]
}
```

[CLI0.1.41 exact installed capability snapshot](lip-sync-capabilities-cli-0.1.41.json).
