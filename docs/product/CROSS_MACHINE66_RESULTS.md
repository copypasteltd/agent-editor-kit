# 第二台原生Windows：CLI66安装、升级与回滚结果

2026-11-06，Asia/Taipei。实际第二台主机`DESKTOP-TE44HE1`，原生Python3.13.14，使用既有原生依赖，无Docker／WSL／虚拟环境。控制器一次启动，18:20完成；[远程完整收据](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1/verification.json)状态为`cross-machine-cli66-cpu-upgrade-rollback-passed`。

## 实际执行及结果

| 编号 | 阶段 | 真实结果 |
| --- | --- | --- |
| M01 | 传输与离线安装 | 六个锁定附件，合计306900954字节；应用ZIP、Skill ZIP、基线工程、预期参考和两个执行脚本的摘要逐项相符；实际CLI66离线安装及`--base-only`配置通过 |
| M02 | 旧版基线 | 63版隔离单Skill入口实际导入、渲染和完整解码通过 |
| M03 | 原注册器冲突拒绝 | 66注册器遇到旧版联接时实际拒绝，旧注册／文件保持；随后显式仅移除本次受管的隔离联接 |
| M04 | 63→66 | 原注册器注册CLI66；实际Skill导入／渲染，全部60帧RGBA、非静音PCM、视频时钟与母素材均符合本机66参考 |
| M05 | 66→63 | 显式回滚隔离联接并用原注册器注册63；重复完整媒体检查，符合63参考 |
| M06 | 63→66 | 再次显式升级；完整媒体检查再次通过，最终保持隔离66入口 |
| M07 | 原文件保护 | 原63的283应用模块、原r58档案及私有配置未变；新66的289应用模块与新档案未变；全局Skill注册及PATH未改 |
| M08 | 受管资源退出 | 本地控制器和本次附件传输进程均已退出；仅白名单主机／随机令牌的临时端口8672在下载后关闭，已核对本机端口不可连接。没有打开新的浏览器标签 |

每次媒体任务是程序图案、440Hz参考音、`t3-kodak-gold-200`强度0.65，320×180／30fps／2秒。每版本均对照它自己的本机完整RGBA／PCM、时钟和母素材参考。没有要求63与66跨版本像素相同；同一版本升级前后／回滚前后结果一致。

| 运行 | 版本 | 直接证据 |
| --- | --- | --- |
| before63 | 0.1.63 | [完整收据](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1/case-before63/verification.json) · [实际成片](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1/case-before63/imported/renders/cross-host.mp4) |
| upgrade66 | 0.1.66 | [完整收据](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1/case-upgrade66/verification.json) · [实际成片](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1/case-upgrade66/imported/renders/cross-host.mp4) |
| rollback63 | 0.1.63 | [完整收据](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1/case-rollback63/verification.json) · [实际成片](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1/case-rollback63/imported/renders/cross-host.mp4) |
| final66 | 0.1.66 | [完整收据](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1/case-final66/verification.json) · [实际成片](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1/case-final66/imported/renders/cross-host.mp4) |

## 没有由本次关闭的范围

本次为**真实跨机器CPU安装与显式隔离升级／回滚验收**；`cross_machine=true`，`cli66_cpu_upgrade_accepted=true`。每份子任务收据沿用基线格式，其`cli66_accepted=false`表示该子任务不单独接受整个CLI66，不与总收据中的CPU升级通过矛盾。

这条路径使用原注册器与显式受管联接迁移，`generic_delivery_controller_tested=false`；不是通用交付控制器正式升级验收。主机已有依赖，`clean_host=false`；本次`gpu_render=false`、`model_inference=false`，没有验证RTX4090模型或GPU渲染，没有人工听审或自然剪辑质量接受。G34和完整目标继续开放；本机正式C盘Skill仍为CLI63，未由该隔离测试切换。

后续仍需干净原生Windows首次安装、Python／FFmpeg／驱动／可选模型完整依赖迁移、CPU／GPU典型任务、通用控制器实际正式切换和故障恢复。[原代码与17项独立协议契约](CROSS_MACHINE66_UPGRADE.md) · [当前全部差距](UNFINISHED_DETAIL_20261106.md)。17项为夹具契约，与4,124产品项及8项AV契约分别记录。
