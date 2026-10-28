# CLI 0.1.50 源码开发状态 / Source development status

历史源码阶段记录。后续本地交付已完成，见[CLI0.1.50本地安装](CLI_0.1.50_LOCAL.md)；以下保留当时状态，不作为当前安装说明。

2026-10-29：新增 `surface measure-media` 编码后成片光量复核，源码专项通过；完整工作流与命令见[使用说明](../product/HDR_MEDIA_MEASUREMENT.md)，失败记录及实际48帧成片复核见[核验记录](../validation/编码后成片光量核验_2026-10-29.md)。

这是源码开发变更，不是新 GitHub Release 或已安装的新发行包。现有本地发行、统一 Skill 与 r50 kit 仍为 CLI 0.1.49 / local.47；公开 alpha.3 下载保持 CLI 0.1.2 原字节。新入口的离线打包、安装版验收与统一 Skill 更新仍待完成，不允许 Skill 静默退回源码。

繁體：這是 CLI 0.1.50 原始碼開發狀態，新增原生成片解碼後光量複核。既有本地發行與統一 Skill 仍為 CLI 0.1.49；新命令尚未進入已安裝套件。請勿將原始碼測試寫成安裝版或完整剪映等價驗收。

English: CLI 0.1.50 source development adds native post-codec media light metering. The installed runtime and unified Skill remain CLI 0.1.49. Offline packaging, installed acceptance and Skill synchronization are pending. Source tests and the actual 48-frame encoded-master oracle are evidence for this source change, not installed-release or full CapCut acceptance.
