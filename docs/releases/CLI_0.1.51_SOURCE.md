# CLI0.1.51 源码阶段 / 原始碼階段 / source phase

Historical source stage; superseded by [actual CLI51 local delivery](CLI_0.1.51_LOCAL.md).

新增显式 `gamut_policy=oklab-chroma`，贯通正式SDR渲染、HDR的SDR预览、光量测量、可编辑工程包和全帧色域计数。算法、完整配置及边界见[功能使用说明](../product/OKLAB_GAMUT.md)，实际输出见[C61](../product/CASES.md#c61-oklab-gamut)。

**已安装版本仍CLI0.1.50/local.48/r51。** 本源码版本没有可宣称已验收的离线安装包；不要修改旧Skill的版本针或让其回退源码。下一轮需重新构建ZIP、冻结277份产品文件、安装核验、注册统一Skill并独立解压测试匹配kit。

最终源码专项62/62；兼容初跑351/352，文档Schema副本同步后Schema17/17通过，分别留证，三次作者渲染（clip、OKLab、包重放），独立RGB16输入与编码后YUV完全一致，源/成片/重放PCM一致。未新增神经模型或GPU色彩内核。旧reject/clip语义保留。[完整实测及失败记录](../validation/OKLab色域映射源码实测_2026-10-29.md)。

繁體：目前僅原始碼功能驗收；CPU分塊、D65 BT.709、非軟拐點/ACES/物理監看，安裝版和自然畫面驗收待完成。

English: Source-only addition; the installed unified Skill remains CLI0.1.50. Explicit CPU-tiled BT.709/D65 OKLab chroma boundary reduction, with counted endpoints and full-frame receipts. Matching offline delivery, natural-image quality, ACES/dynamic HDR and physical-monitor validation remain open.


**2026-10-29 follow-up / 后续勘误 / 後續勘誤：** [SDR预览映射修复与C61包ID勘误](../validation/SDR预览映射修复_2026-10-29.md)。CLI51候选r2已构建与安装专项核验；统一Skill仍50；完整兼容、新kit、自然画面及物理监看待完成。
