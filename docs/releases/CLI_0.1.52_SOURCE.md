# CLI0.1.52 源码开发版 / Source development

Historical source stage; superseded by [actual installed CLI52 delivery](CLI_0.1.52_LOCAL.md).

新增原生GPU亮度肩部/OKLab缩色度，复用受管OpenCL工作进程与共享缓冲；正式SDR交付、明确HDR预览和正式映射继承使用同一路径。已有CPU reject/clip/oklab语义保持。

[完整使用流程与执行边界](../product/GPU_GAMUT.md) · [C63实际案例](../product/CASES.md#c63-source-gpu-gamut) · [专项/独立参考/待办](../validation/GPU色域映射源码实测_2026-10-29.md) · [源码89项能力原始收据](../product/gpu-gamut-source-capabilities-cli-0.1.52.json)

当前注册入口仍CLI0.1.51/local49/r52。源码测试和单独候选构建不等于安装激活；新版离线包、安装回归、实际Skill案例及统一kit待完整核验。不要用旧Skill调用本版GPU新增能力，不回退源码冒充安装版。公开alpha.3/CLI0.1.2资产保持原字节。

## 已构建的本地候选包

候选 ZIP 位于 `local/agent-ffmpeg/v0.1.0-alpha.4-local.50/candidate-r1/bundle.zip`，303223087 bytes，SHA256 `979b54babd7db6d89b0da1e8ee3343657a8f2cb8a95dcfc5d24da6d66f1ad564`。清单 SHA256 为 `a2e511c5ca126dd94bbf1efd3f7ee38eef1d60f0453cfdeed47eda7ebd9b3f39`。

已解压、校验并独立安装在 `local/agent-ffmpeg/v0.1.0-alpha.4-local.50/final-r1/installed`；通过 `-I -S` 安装入口核对实际版本52、89项能力与全部278个源码文件一致。见[实际构建/安装收据](../validation/evidence/gpu-gamut-20261029-r1/installation-final-r1/verification.json)。这只是候选安装，**尚未替换已注册CLI51 Skill**；完整安装专项与兼容回归仍须读取终态。

繁體：源碼GPU路徑已實作並留存真實音畫核驗，安裝版與新版Skill交付另行驗收。English: Source GPU mapping is implemented and checked against real media and independent references; installed runtime and Skill delivery remain a separate gate.

候选安装版专项已完成：[70/70通过、无失败/跳过](../validation/evidence/gpu-gamut-20261029-r1/installed-measure-r1/verification.json)。安装版352项兼容组仍在运行，统一Skill保持51。
