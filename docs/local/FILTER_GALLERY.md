# N002 母图 × 500 套滤镜：实际样例与客户选型

[简体中文](FILTER_GALLERY.md) · [繁體中文](FILTER_GALLERY.zh-TW.md) · [English](FILTER_GALLERY.en.md)

[Interactive gallery](../assets/looks-n002-20261024-r1/index.html) · [Filter workflow](FILTERS.md) · [Measured profiles](LOOK_PRESETS.md) · [Actual executions](../validation/evidence/looks-n002-20261024-r1/render-verification.json)

500 套均实际运行安装版 CLI，统一使用本次用户提供的母图，强度 1.0、四面体插值。原图 1672×940；原尺寸无损 WebP 的 RGB 与 CLI PNG 逐像素一致，缩略图仅用于选择。原图无嵌入色彩配置，按编码 SDR RGB 试片。

![Original and eleven actual looks](../assets/looks-n002-20261024-r1/selection-board.jpg)

## 每一套实际样例

| # | 逐项样例、原尺寸图与 ID |
|---|---|
| 001–100 | [100 actual previews](filter-gallery/001-100.md) |
| 101–200 | [100 actual previews](filter-gallery/101-200.md) |
| 201–300 | [100 actual previews](filter-gallery/201-300.md) |
| 301–400 | [100 actual previews](filter-gallery/301-400.md) |
| 401–500 | [100 actual previews](filter-gallery/401-500.md) |

## 50 套一张的速查总览

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

## Agent 向客户展示与记录选择

1. 先根据需求选 3–6 套，展示原图与实际样例；附编号、名称、稳定 ID、当前强度和许可。
2. 客户可报编号/ID，或本地打开交互页筛选、勾选并导出候选 JSON。GitHub 不执行仓库 HTML，下载后直接打开。
3. 使用 Skill helper 导出客户专属对照板；100% 样例不能冒充 0.65 强度效果。
4. 在客户实际目标帧上以候选 ID 和真实强度运行 look preview。确认最终 ID、强度、片段/全局作用域后再 apply，保留快照。
5. 编码成片后检查实际输出与 warning；本图没有证明所有肤色、场景、HDR 或视频时序质量。

```powershell
$aekGallery = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/look_gallery.py'
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --query '黑白' --limit 6
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --ids t3-fuji-superia-800 nt-bw-agfa-apx-100 fl-0000634-darkblue --output 'E:/video-work/client-look-options'
```

[Example board](../assets/looks-n002-20261024-r1/client-shortlist-example/board.jpg) · [Returned selection](../assets/looks-n002-20261024-r1/client-shortlist-example/selection.json) · [Skill procedure](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md)

## 来源、强度与展示边界

母图使用依据是本次用户提供及明确要求展示，未标记为 MIT/CC0。滤镜保留每项 MIT/CC0/CC BY-SA 许可、作者和变更来源。原图权利与 LUT 权利分别记录；[完整说明及逐项署名](../assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md)。500 是不同数值变换，包含同系列曲线变体，不等于 500 个独立风格家族。

[Desktop screenshot](../assets/looks-n002-20261024-r1/gallery-desktop.png) · [Mobile screenshot](../assets/looks-n002-20261024-r1/gallery-mobile.png) · [Actual UI recording](../assets/looks-n002-20261024-r1/gallery-walkthrough.webm)
