# 原生完整回归的依赖与即时错误记录

2026-11-06，Asia/Taipei。20文件修正已一次写齐、备份并应用，r5冻结后集中检查。31项交付契约全通过；两组实际隔离依赖预检通过，产品整套实际发现4,124项，仍运行、无终态。正式Skill仍CLI0.1.63／local61／r58。没有修改共享解释器、._pth或安装包，没有创建虚拟环境，也没有Docker／WSL。

| 编号 | 原问题／已完成代码 | 实际结果与限制 |
| --- | --- | --- |
| N01 | 原C测试Python缺OpenCV；其隔离模式看不到用户目录NumPy／Pillow | 原r4最终10条cv2异常、2条CLI明确缺NumPy；另外5个关联传输结果没有直接cause，不能扩大归因 |
| N02 | 使用既有E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe | 原生解释器，无新安装、共享依赖改写或虚拟化；实际导入通过，不再只是发现元数据 |
| N03 | 应用profile实际-I导入并核对CLI0.1.66及准确应用路径 | NumPy2.5.3、Pillow12.3.0、OpenCV模块5.0.0、jsonschema4.26.0，实际来源均独立记录 |
| N04 | bare-worker不注入应用目录，独立-I导入相同4依赖 | 实际通过，application_file/version均无值；防止控制器可用但隔离worker不可用 |
| N05 | 锁定解释器、模块入口、嵌套PYD／DLL和随附库 | 每profile36文件；加Rubber Band／Node／Chromium等实际工具后43文件。结束时再次逐字节核对 |
| N06 | 即时刷盘完整堆栈、失败子测试及有界AppError.code/cause/hint，继续全部用例 | 日志契约通过；不改变结果／门槛、不fail-fast、不跳过。故意失败的内层5项不算产品通过 |
| N07 | 8模块按计算需要加载NumPy／Pillow | 原3项轻量CLI失败来自effects初始化目录；扩大静态图145模块／49函数作用域，0提前重依赖路径。静态图不替代实际CLI |
| N08 | 音乐与音频增强畸形进度有界诊断；原测试夹具和3个目录预期修正 | 新增10项产品方法进入完整4,124项；没有逐模块提前测试或放宽原数值／像素断言 |
| N09 | 完整交付契约31项，新增13项 | 实际全部通过，零失败／错误／跳过；仅工具／文件／CLI夹具，不算真实模型推理或正式注册 |
| N10 | 嵌入式Python不自动加入交付脚本目录 | contracts-r3启动前失败，无发现数；仅显式加入交付工具目录后完整31项通过，不注入产品路径、不改共享Python |

应用离线包固定NumPy2.4.2／Pillow12.1.0，源码本轮所用既有环境版本不同。后续安装全套仍须分别记录实际应用来源与依赖字节，不能宣称源码与安装环境完全相同，也不能用源测试替代安装验收。

[当前集中核验](../validation/evidence/delivery66-handoff-20261106-r1/correction-batch-review-r1/verification.json) · [应用隔离profile](../validation/evidence/delivery66-20261106-r1/source-all-r5/native-isolated-dependencies.json) · [bare-worker profile](../validation/evidence/delivery66-20261106-r1/source-all-r5/native-bare-worker-dependencies.json) · [实际依赖总清单](../validation/evidence/delivery66-20261106-r1/source-all-r5/native-dependencies.json) · [31项终态](../validation/evidence/delivery66-handoff-20261106-r1/contracts-r4/verification.json)。

原r4已完成4,114项，10失败／15错误／0跳过，记录永久保留。[原结果及归因置信边界](DELIVERY66_R4_RESULTS.md) · [20文件范围](DELIVERY66_R5_CANDIDATE.md) · [完整未完成内容](UNFINISHED_20261106.md) · [后续执行顺序](DELIVERY66_HANDOFF.md)。G01—G38仍保留原关闭条件。

当前r5即时日志已记录4个新问题事件；下一批3文件修正显式绑定实际source／installed包，保留ASCII对抗管道、原锁等待／清理门槛和全部断言，并补音频AppError导入。当前冻结仍完整保留，候选未应用／执行，待r5终态后一次补齐所有发现。[新批完整说明及证据](DELIVERY66_R6_CANDIDATE.md)。
