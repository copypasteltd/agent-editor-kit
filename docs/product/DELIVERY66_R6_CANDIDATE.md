# CLI66原生子进程与音频诊断修正候选

2026-11-06，Asia/Taipei。r5完整产品回归由原生监督继续执行，实际发现4,124项、尚无终态。03:26 UTC的不可变检查点记录4个问题事件：Unicode模块启动1项FAIL、两个工程锁子进程就绪FAIL、音频诊断异常分支1项ERROR。这是运行中事件快照，不能作为最终失败统计。

本页3文件候选尚未应用、导入或执行；r5的546个产品／用例／依赖文件、7工具及95个正式文件保持原字节。待整轮全部结果汇总，一次补齐所有发现后再应用完整批次、冻结新编号并集中回归；不提前运行单项测试。正式入口仍CLI0.1.63／local61／r58。

| 编号 | 已写完整候选代码 | 已有证据与未验收边界 |
| --- | --- | --- |
| J01 | 音频诊断模块显式导入实际捕获的AppError | 当前r5完整堆栈直接记录NameError；保留非普通文件拒绝、unavailable状态和错误码断言，候选未执行 |
| J02 | 既有测试辅助模块提供显式被测应用绑定；Unicode入口实际执行包__main__，两个锁子进程执行原真实脚本 | 子进程先核对实际__init__.py来源与父测试选择的source／installed根目录一致；不依赖PYTHONPATH，不替换产品函数，不回落源码 |
| J03 | Unicode用例在真实CLI启动前明确建立ASCII／strict stdout及stderr，再交给产品自行修复UTF-8 | 保留中文／emoji路径、request-id、真实FFmpeg导入、JSON／JSONL及中文事件断言；不通过预先设置UTF-8绕开原问题 |
| J04 | 两个工程锁子进程保留有界stderr，失败时附最多8,192字节实际输出 | 保持3秒就绪、5秒归属子进程清理、真实锁竞争及取消断言；原r5锁错误未记录子进程stderr，环境根因仍是同类静态推断 |
| J05 | 3文件语法及生成的3种子程序静态编译；10个r5改动应用模块做名称绑定复核 | 覆盖后无未绑定名称；保留124个原测试方法和1,371处断言条件。静态检查不等于功能回归通过，新增测试方法0项 |

解释器只读检查确认：既有E盘嵌入式原生Python普通启动也为isolated=1／ignore_environment=1，PYTHONPATH指定的产品目录不在sys.path。该检查的实际stdout是ASCII／strict，stderr为ASCII／backslashreplace；所以不能笼统声称所有编码环境设置都被忽略。候选显式建立ASCII／strict是为了保证原对抗条件，而不是把未执行的编码流程算作通过。

真实Unicode失败直接显示No module named ai_ad_editor。两项锁失败只有“未就绪”断言：代码同样只靠PYTHONPATH传包目录，属于已定位机制、待下一轮实际stderr确认的关联原因。音频错误则直接显示except中的AppError未定义。区分直接堆栈与静态推断，不将四个事件宣称为四个独立产品内核缺陷。

候选只有3个代码文件：product/tests/package_under_test.py、product/tests/test_cli.py、product/src/ai_ad_editor/enhancement_pipeline.py。原产品算法、模型、GUI、正式注册和既有解释器均未改写。新临时和候选仍在E盘，无Docker、WSL、容器或虚拟环境。

[逐文件原／候选摘要](../validation/candidates/delivery66-r6/implementation.json) · [完整实时异常快照](../validation/evidence/delivery66-handoff-20261106-r1/r5-live-correction-draft-r1/observed-issues.json) · [解释器实际环境检查](../validation/evidence/delivery66-handoff-20261106-r1/r5-live-correction-draft-r1/interpreter-environment.json) · [原生进程身份观察](../validation/evidence/delivery66-handoff-20261106-r1/r5-live-correction-draft-r1/observation.json) · [静态及冻结收据](../validation/evidence/delivery66-handoff-20261106-r1/r5-live-correction-draft-r1/verification.json)。

31项交付契约的既有通过仍只覆盖其r5冻结版本；本候选没有追加通过数，没有重新启动、过滤或中断当前产品整套。完整目标仍按G01—G38保留。[当前未完成内容](UNFINISHED_20261106.md) · [前20文件修正](DELIVERY66_R5_CANDIDATE.md) · [交付顺序](DELIVERY66_HANDOFF.md)。
