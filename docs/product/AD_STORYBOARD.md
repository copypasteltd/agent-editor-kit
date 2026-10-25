# 可编辑广告分镜、多画幅变体与局部返工

适用于 CLI 0.1.14 本地扩展。实际安装与核验状态见[本地交付](COMMUNITY_LOCAL_DELIVERY.md)。
这套流程把已确认的广告 brief、文案和本地素材选择落实为普通可编辑序列。
产品/卖点、镜头语义、素材来源与人类客户的创意选择由调用者提供。

## 使用流程

1. 用 `media ingest` 或 `materials ingest` 导入原片、字体与配乐，保留实际返回的资产 ID。
2. 需要配音时，先生成完整声音并检查实际时长。GPU 配置后优先用 `auto` 或严格 `cuda`。
3. 写 brief，用 `ad storyboard` 检查各画幅的时长、素材边界和字幕，取得计划。
4. 用 `ad build` 提交。计划绑定原工程和实际素材摘要，修改过的工程需要重新规划。
5. 用已有 `preview frame`、`render` 和 `quality check` 预览、编码及核验每个变体。
6. 客户改稿时，用稳定的镜头/变体 ID 编写返工请求，`ad revise` 规划，再 `ad build` 提交。
7. 用 `convert export --target-format package` 交付可编辑工程；导入后实际重渲染。

```powershell
$project = 'E:/video-work/product-ad'
$avk = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk ad storyboard --project $project --input "$project/brief.json" --output "$project/validation/ad-plan.json" --dry-run
& $avk ad storyboard --project $project --input "$project/brief.json" --output "$project/validation/ad-plan.json"
& $avk ad build --project $project --input "$project/validation/ad-plan.json" --idempotency-key product-ad-build-1
& $avk render --project $project --sequence-id ad_product_wide_sequence --output "$project/renders/wide.mp4"
& $avk quality check --project $project --input "$project/renders/wide.mp4"
```

输出计划必须为项目 `validation/` 下的新文件。`--dry-run` 不写计划或工程。
普通规划只写计划，不改变 `project.json`；提交保存之前的快照并使用既有原子事务。
`--timeout-seconds` 和 `--cancel-file` 覆盖规划、实际输入校验和提交前检查。

已校对的同语种 SRT 可以直接批量配音，例如 `dub subtitles --from zh-Hans --to zh-Hans`。
英文用 en/en、繁體中文用 zh-Hant/zh-Hant。该模式保持每条原文，只初始化配音模型，
不加载翻译包、不应用译后术语替换、不重复显示两行相同“译文”。

## Brief 格式

以下 ID 需要替换成实际导入的资产 ID。画面允许 image/video，配音/配乐必须为 audio，字体必须为 font。

```json
{
  "id": "product",
  "product": "实际产品名称",
  "audience": "已确认的目标客户",
  "cta": "已确认的行动文案",
  "caption_style": {"font_asset_id": "font", "font_ratio": 0.045, "safe_margin_ratio": 0.08},
  "shots": [
    {"id": "hook", "asset_id": "video_a", "source_in_tick": 0, "weight": 1, "text": "已确认的开场文案", "fit": "fit"},
    {"id": "proof", "asset_id": "video_b", "weight": 1, "text": "可核验的展示", "voice": {"asset_id": "voice_b"}},
    {"id": "cta", "asset_id": "image_c", "weight": 1, "text": "已确认的行动文案"}
  ],
  "music": {"asset_id": "music", "source_in_tick": 0, "gain_db": -24},
  "variants": [
    {"id": "wide", "canvas": {"width": 1280, "height": 720}, "duration_seconds": 9},
    {"id": "vertical", "canvas": {"width": 720, "height": 1280}, "duration_seconds": 12},
    {"id": "square", "canvas": {"width": 720, "height": 720}, "duration_seconds": 9,
     "shot_ids": ["proof", "hook", "cta"], "overrides": {"hook": {"text": "另一条已确认的开场文案"}}}
  ]
}
```

`id`、变体 ID 和镜头 ID 为 1–32 个合法字符。最多 50 镜头、30 变体，每变体 3–180 秒。
所有数值必须有限。画布明确指定，尺寸需兼容当前 4:2:0 输出。
按项目有理帧率分配整帧；`weight` 是镜头时长权重，每镜头至少一帧。
计划返回实际帧数、tick 和非整帧时长的舍入提示。不会静默伸长原片或循环配乐。

每个变体有视频、字幕、配音、源音和配乐轨。源音默认不加入；
镜头中明确设置 `include_source_audio: true` 后才建立对应声音片段，`source_gain_db` 控制其增益。
`voice` 可指定 `source_in_tick` / `source_out_tick` 和 `gain_db`；默认使用完整声音。
音频超出镜头窗口会明确失败，调用者应调整时长或先通过已有配音流程重新生成完整句子。

字幕字体按画幅高度计算，使用实际字体度量换行并拒绝超画布文案。
复杂手工位置、动画、RTL/全 Unicode 排版和整段视听质量继续需要相应预览验收。

硬件编码可显式使用 `render --hardware-encode require --hardware-encoder nvenc --video-bitrate 4M`。
实际可用性按本机 FFmpeg/驱动探测；GPU 编码不表示字幕合成或所有滤镜都在 GPU 上运行。

## 精确局部返工

```json
{
  "campaign_id": "product",
  "variant_ids": ["wide"],
  "shots": [
    {"id": "cta", "asset_id": "replacement_video", "source_in_tick": 90000,
     "text": "客户确认后的行动文案", "fit": "fill"}
  ]
}
```

```powershell
& $avk ad revise --project $project --input "$project/revision.json" --output "$project/validation/revision-1.json"
& $avk ad build --project $project --input "$project/validation/revision-1.json"
```

仅修改选中的变体和镜头字段，保留其他序列/镜头以及未涉及的效果、关键帧、字体样式等人工编辑。
配音不会因字幕改字自动重生成；需要换声音时明确提供新的 `voice`，删除声音用 `voice: null`。
字幕设为空字符串删除该镜头的字幕。初次没有字幕的镜头也可补字幕。
镜头分割导致身份不再唯一、目标轨道丢失/锁定或工程偏离计划时会拒绝覆盖。
复杂时间结构修改可继续用普通时间线编辑工具，之后重新规划需要的广告改动。

## English workflow

Ingest actual local media and a font, prepare reviewed copy and complete voice assets, then run
`ad storyboard` → `ad build` → preview/render/quality. Each variant has an independent canvas,
duration and editable picture/caption/voice/source/music tracks. Source audio is explicit.
Use `ad revise` with campaign, variant and shot IDs, inspect its plan, then `ad build` again.
Plans reject stale projects, changed media, truncated speech and caption overflow; unrelated edits
are preserved. Creative decisions are supplied by the caller. Decoding and package equality do not
establish natural ad quality, human listening or independent Agent autonomy.

## 实际可复查案例 / Actual case

[C23 的原输入、3 个实际 MP4/GIF、修改前后帧](CASES.md#c23-ad-storyboard) · [完整测试/安装/真实 GPU/Skill/往返与失败](../validation/可编辑广告分镜与返工实测_2026-10-25.md)。图卡为程序自制，非 GUI 截图；声音保留本地，公开为无声衍生物。单例闭环不等于自然广告质量或独立 Agent 自主验收。
