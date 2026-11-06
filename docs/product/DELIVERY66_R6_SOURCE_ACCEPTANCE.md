# CLI66：r6源码整套通过及独立安装检查点

2026-11-06，Asia/Taipei。本批所有代码修正先完成并冻结，然后集中运行。原r6源码整套已完整结束：**4,124项、0失败、0错误、0跳过、退出码0**。真实监督／子进程均已退出；源码、测试、交付工具、构建来源及正式安装的冻结字节一致。

## 当前已完成与未完成

| 编号 | 实际结果 | 边界 |
| --- | --- | --- |
| S01 | 原r6源码整套4,124项全部通过，未过滤发现、未放宽断言或时限 | 不是安装版整套结果，也不代表全部自然素材质量 |
| S02 | 原r5的Unicode入口、两个工程锁、音频诊断、TTS断网5例在同一整套通过；恢复预检17例亦在其中通过 | 子集不另行累加；旧失败／错误及r2中断继续保留 |
| S03 | 实际原生离线构建并安装CLI0.1.66；289应用模块与冻结源码逐字节一致 | 不是正式Skill升级；无源码回退 |
| S04 | 上述安装版同一r6完整4,124项通过，0失败／错误／跳过、退出码0；实际监督／子进程均已退出 | [完整安装终态与候选入口](DELIVERY66_R6_INSTALLED_ACCEPTANCE.md)；正式仍63，未再启动源码回归 |
| S05 | 43项交付工具契约已通过，0失败／错误／跳过 | 独立fixture工具组，不与产品整套相加，不替代真实模型故障 |

源码运行器报告7408.883秒，unittest原日志7401.930秒；原生监督总耗时7421.183秒。各层时间相互包含，不相加，也不作为性能对照。

## 实际候选与来源

- 版本：v0.1.0-alpha.4-local.64／CLI0.1.66。
- 安装目录：`local/agent-ffmpeg/delivery66/candidate-r1/installed`。
- 本地应用ZIP：`local/agent-ffmpeg/delivery66/candidate-r1/bundle.zip`。
- 应用ZIP SHA-256：`36b2970f92d24393e6ae6b77636f43b89bea6c3a201aaa164889148feb2d0786`。
- 清单摘要：`sha256:1da7f0a678ea678f49af6d9b847dfd8912b11ede04aad22f8d87ee247ee1117a`。
- 应用来源：289个模块精确一致；冻结范围546产品／测试／依赖、8交付工具、69构建来源、95正式文件。

正式发现入口仍CLI0.1.63／local61／r58，唯一`$agent-ffmpeg-local-editor`、17内部模块。CLI66候选安装与正式注册是不同状态。

## 还要完成的交付链

源码／安装整套及候选单Skill入口已通过 → 真实66 CUDA配乐 → 完整母音频／配方／RGBA／PCM工程包重放 → 新工具包真实基础配置及隔离注册 → 实际模型取消／超时／输出冲突 → 正式升级／显式回滚／再次升级及发现入口重放 → 同版三语流程、源码绑定、普通推送及新alpha.4发行。

第二台CLI63 CPU基线已经通过；66跨机升级／回滚、GPU任务、干净主机、自然听审和原G01—G38完整目标仍开放。应用ZIP不包括Python、FFmpeg、驱动、所有模型和整个外部音乐运行库。全部过程使用原生Windows，未使用Docker、WSL、虚拟环境或新浏览器标签。

## 原始证据

- [源码完整终态](../validation/evidence/delivery66-20261106-r1/source-all-r6/verification.json) · [完整测试日志](../validation/evidence/delivery66-20261106-r1/source-all-r6/tests.stderr)。
- [原生监督终态](../validation/evidence/delivery66-20261106-r1/native-source-all-r6/state.json) · [离线构建／安装](../validation/evidence/delivery66-20261106-r1/candidate-r1/verification.json)。
- [本次检查点](../validation/evidence/delivery66-handoff-20261106-r1/r6-source-install-checkpoint-r1/verification.json) · [实际安装进程观察](../validation/evidence/delivery66-handoff-20261106-r1/r6-source-install-checkpoint-r1/installed-live-observation.json)。
- [原r5全部失败及r6完整修正](DELIVERY66_R6_EXECUTION.md) · [完整未完成清单](UNFINISHED_20261106.md) · [原始38组目标](GOAL_GAPS_20261025.md)。
