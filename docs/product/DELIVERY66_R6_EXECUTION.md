# CLI66整批r6应用与集中验证

**后续完整终态：原r6源码4,124项全部通过，0失败／错误／跳过、退出码0；同冻结66已实际离线安装，安装版整套已启动、尚无终态。正式入口仍63。** [终态与候选证据](DELIVERY66_R6_SOURCE_ACCEPTANCE.md)。以下保留当时整批应用、集中启动及旧失败的历史现场。

2026-11-06，Asia/Taipei。开发源码CLI0.1.66；正式唯一Skill仍为CLI0.1.63／local61／r58。本页记录先完成全部本批代码、再集中验证的实际执行，不代表新版安装、模型或公开发行已通过。

## 本次实际结果

| 编号 | 已执行内容 | 结果及证据 | 边界 |
| --- | --- | --- | --- |
| E01 | 收齐原r5未过滤整套，核实原监督／测试进程均退出 | 4,124项，4失败、1错误、0跳过，退出码1；[终态](../validation/evidence/delivery66-20261106-r1/source-all-r5/verification.json)、[五条完整堆栈](../validation/evidence/delivery66-handoff-20261106-r1/r5-terminal-review-r1/failure-catalog.json)、[进程终态复核](../validation/evidence/delivery66-handoff-20261106-r1/r5-terminal-review-r1/verification.json) | 原r4、r2及r5全部失败／中断均保留，不把用例发现数当通过数 |
| E02 | 全部9文件统一预检、保存备份，整批应用 | [实际应用收据](../validation/evidence/delivery66-handoff-20261106-r1/r6-complete-application-r1/verification.json)记录原始／新摘要和备份；95正式文件保持不变 | 每文件替换不宣称多文件全局原子事务；没有切换正式Skill |
| E03 | 在任何新功能检查前冻结r6 | [冻结清单](../validation/evidence/delivery66-20261106-r1/freeze-r6/verification.json)：546产品／用例／依赖、8交付工具、69构建来源、95正式文件及官方校验器摘要，实施单元至H10 | 当前冻结覆盖全部本批实现；运行中不修改这些文件 |
| E04 | 原生执行完整43项交付工具检查 | [实际终态](../validation/evidence/delivery66-handoff-20261106-r1/contracts-r5/verification.json)：43项通过，0失败／错误／跳过，退出码0；[完整输出](../validation/evidence/delivery66-handoff-20261106-r1/contracts-r5/tests.stderr) | fixture-only；含真实本地Git与打包，但无模型推理、正式注册或公开发布；不与原31项相加 |
| E05 | 启动新的未过滤产品整套r6 | [启动复核](../validation/evidence/delivery66-handoff-20261106-r1/r6-centralized-start-r1/verification.json)、[实际发现4,124项](../validation/evidence/delivery66-handoff-20261106-r1/r6-centralized-start-r1/discovery.json)；已核实真实监督及子进程存活 | 仍运行、没有终态；启动检查点没有问题事件不等于全部通过 |
| E06 | 完成应用与bare-worker两组实际原生隔离依赖预检 | 两组各36个文件，总依赖43个去重文件；[应用profile](../validation/evidence/delivery66-handoff-20261106-r1/r6-centralized-start-r1/native-isolated-dependencies.json)、[bare-worker](../validation/evidence/delivery66-handoff-20261106-r1/r6-centralized-start-r1/native-bare-worker-dependencies.json)、[总依赖](../validation/evidence/delivery66-handoff-20261106-r1/r6-centralized-start-r1/native-dependencies.json) | 文件集合重叠，不累加为独立覆盖；未改解释器、._pth、site-packages或创建虚拟环境 |

## 原r5问题与本批处理

| 编号 | 原失败事实 | 已应用处理 | 尚需证明 |
| --- | --- | --- | --- |
| F01 | Unicode CLI子进程找不到ai_ad_editor | 显式绑定实际被测源码／安装包，仍调用真正__main__并建立ASCII／strict前置条件 | r6整套及安装版执行原Unicode／进度／真实FFmpeg断言 |
| F02 | 两个真实锁用例未在原3秒内取得ready文件 | 既有脚本显式绑定同一包，失败时保留有界stderr；原3秒／5秒清理门槛不放宽 | 原r5未捕获到实际子进程原因，不能仅凭静态推断宣称锁实现已验收 |
| F03 | 音频异常诊断捕获AppError时出现NameError | 导入真正AppError，保留原unavailable状态和错误码检查 | 新源码与安装版完整回归通过，原错误现场继续保留 |
| F04 | TTS断网用例在导入时失败，尚未进入socket拦截 | 原socket脚本与15方法／全部断言保留，只修正被测包绑定 | 必须实际执行到原网络拦截断言，不能把原导入失败算作断网通过 |

发布提交绑定、69来源冻结、固定版本文档、Skill说明／官方校验器和包内目标版本说明已在同一批写齐。43项工具终态只证明其明确覆盖的契约，产品整套、真实模型、媒体重放及正式入口各自保留门禁。[完整实现范围](DELIVERY66_R6_CANDIDATE.md)、[Skill生成输入](DELIVERY66_STAGE_INPUTS.md)。

## 后续顺序与使用边界

等待本次完整终态，若仍有问题，收齐全量后再统一完成下一批代码，不挑选单项反复调测。本次完整通过后，再依次进行离线包、安装版完整回归、候选Skill、CLI66真实CUDA音乐及故障、完整RGBA／PCM／母音频／配方重放、独立工具包安装注册、正式升级／回滚／真实发现入口和新Release。

目前日常仍使用正式CLI63入口；神经音乐真实历史成功属于65候选。4份安装／素材手册已区分正式、候选、开发及历史版本。没有新66可用包、正式Skill升级或新公开发行结果，不以43项通过关闭原G01—G38。

[完整交付流程](DELIVERY66_HANDOFF.md) · [未完成条件](UNFINISHED_20261106.md) · [原38组目标](GOAL_GAPS_20261025.md)。
