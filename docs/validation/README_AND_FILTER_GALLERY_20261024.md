# 完整 README 与母图滤镜图册实测 / Complete README and supplied-image gallery verification

日期 2026-10-24；安装版 `v0.1.0-alpha.3` / CLI `0.1.2` / 风格目录 `2.0.0`。本轮不修改产品内核或运行包，保留旧版案例/回归原日期。

| 编号 | 实际执行 | 结果 | 原始证据与边界 |
|---|---|---|---|
| R25 | 原生 `-I -S` 进程仅导入固定安装目录，使用正式 CLI parser 对 N002 执行 500 次 `look preview` | 500 原尺寸无损 WebP + 500 小图；500 个独立像素哈希；每张 WebP 与 CLI PNG RGB 全像素一致 | [渲染回执](evidence/looks-n002-20261024-r1/render-verification.json)、每套 stdout JSON、[所有参数/哈希/路径](../assets/looks-n002-20261024-r1/manifest.json)；没有新视频渲染或模型推理，不是全自然视频质量验收 |
| R26 | 既有原生 Edge/Playwright 打开本地 HTML：40 张分页、稳定 ID 搜索、类别 37 项/CC0 133 项、滑杆、勾选、下载 JSON、简繁英、空结果、手机宽度/键盘 | 19 项浏览器断言通过，无页面脚本错误，无远程请求；所有本任务标签关闭 | [浏览器回执](evidence/looks-n002-20261024-r1/browser-verification.json)、[桌面](../assets/looks-n002-20261024-r1/gallery-desktop.png)、[手机](../assets/looks-n002-20261024-r1/gallery-mobile.png)、[真实录屏](../assets/looks-n002-20261024-r1/gallery-walkthrough.webm)；这是选型文档页 |
| R27 | 17 个 Skill 格式/联接/哈希；helper 实际搜索/导出板/拒绝覆盖/拒绝未知 ID；注册的 Skill 启动器实际 version/inspect/preview | 4 次 helper（含 2 预期拒绝），3 次已注册启动器成功；实际预览与图册像素相同，工程不变 | [Skill 回执](evidence/looks-n002-20261024-r1/skill-verification.json)、[命令日志](evidence/looks-n002-20261024-r1/skill-commands.json)、[对照板](../assets/looks-n002-20261024-r1/client-shortlist-example/board.jpg)、[候选 JSON](../assets/looks-n002-20261024-r1/client-shortlist-example/selection.json)；格式/调用不等于全体 Agent 决策质量 |
| R28 | 三语 README、43 功能说明/12 服务/17 Skill/28 核验行、全部能力字段、500 详情与样例、原本地链接/锚点、1000 图像哈希 | 具体文件数/链接数/大小见机器回执；三语命令完全一致，42 个历史演示恢复并保留边界 | [文档回执](evidence/looks-n002-20261024-r1/docs-verification.json)；没有重跑 2,930 项历史全量内核回归 |

## 输入与实际处理

母图由用户提供，1672×940 RGB PNG，2,087,113 字节，SHA-256 `babaa64ce3434a23133c41a1d2b4fad384a5e6707546b527508d4731ba83ab4b`。原始文件与仓库 `source.png` 摘要一致，文件未改写。无嵌入 ICC/profile，按编码 SDR RGB 处理；不推断 Log/HDR 或相机信号。

全部样例使用强度 1.0、四面体插值。PNG 原始中间输出和临时 CUBE 在 `product/.runtime/looks-n002-20261024-r1/` 的 E 盘工作区；发布的无损 WebP 总计 589,811,430 字节，RGB 全像素相同。小图 512×288、WebP quality 90，接触表/JPEG/GIF 有缩放或有损编码，不能替代无损大图的像素证据。

图册的来源与权限不是由软件 MIT 继承：[母图/每套 LUT 的独立说明](../assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md)。用户提供母图并明确要求生成并同步到 README/Skill；未将其标为 CC0 或宣称拥有额外第三方权利。

## 复现

```powershell
# Render into NEW E-drive directories; keep failed runs and existing outputs.
C:/Python313/python.exe -I -S -B -u -X utf8 scripts/render_n002_look_gallery.py --installed 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.3/installed' --source 'E:/dev/sandbox/视频拆解/新片俄式艺术重制_v4_2026-10-23/output/imagegen/raw/N002.png' --assets E:/video-work/n002-assets-new --evidence E:/video-work/n002-evidence-new --work E:/video-work/n002-work-new
# Rebuild the checked-out documentation from retained actual receipts:
C:/Python313/python.exe -E -B -X utf8 scripts/build_product_readmes.py
C:/Python313/python.exe -E -B -X utf8 scripts/build_n002_gallery_docs.py
C:/Python313/python.exe -E -B -X utf8 scripts/build_look500_docs.py
C:/Python313/python.exe -E -B -X utf8 scripts/verify_n002_gallery_docs.py
```

渲染脚本验证输入摘要与当前固定安装回执。网页/Skill 核验脚本在当前固定 evidence 目录保存结果；生成新一轮证据前应使用新的目录/编号，避免覆盖旧失败或已公开记录。没有启动 Docker、WSL 或虚拟环境，临时 LUT/PNG 位于 E 盘。浏览器仅使用既有原生运行时，结束后关闭本任务页面。

## 静态查看与未验收范围

已查看桌面预览和原图 + 11 套风格的对照板；暖色/去色/霓虹/冷色差异可见。500 套完整图像经过哈希和实际输出像素检查，不等于逐套人工审美验收。此次单张静态图没有时间变化或音频，不能据此宣称自然视频时序、播放、听感、肤色保护、HDR/ICC 或完整剪映功能达标。

文档检查首轮将 inline code 内的图片语法示例当作真实链接而误报；[原失败](evidence/looks-n002-20261024-r1/docs-check-initial-failure.json)保留。检查器改用已有 Markdown 解析器的实际 link/image token，仍检查全部真实目标和预设锚点；该问题不是滤镜执行失败。
