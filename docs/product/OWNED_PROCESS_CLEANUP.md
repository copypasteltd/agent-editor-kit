# 原生自有进程同步回收（源码 CLI0.1.58）

## 问题与修复

安装57服务契约回归实际出现超时类型不一致和临时WAV被占用，398项产生1个失败、1个错误，未获安装验收。另用实际Windows文件写入进程独立复核：旧Job关闭返回时，20次中20次子进程尚未退出、文件仍无法删除。所有试验自有子进程随后明确等待退出，没有杀除其他任务。

Windows外部终止是异步操作；发送终止信号或活动进程计数为零，不能替代等待进程句柄退出。参考微软[TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess)、[TerminateJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject)及[IsProcessInJob](https://learn.microsoft.com/en-us/windows/win32/api/jobapi/nf-jobapi-isprocessinjob)。

源码58在终止前获取自有作业中的进程句柄，复查成员关系以防PID复用，显式终止该Job并等待已持有根／后代句柄退出，再检查作业活动数。保留10秒清理预算、4096进程枚举界限及幂等关闭。只处理自身拥有的作业，不构成全系统沙箱或对任意恶意逃逸进程的保证。

补帧预处理工具自身超时现在映射为流水线 `TIMEOUT`；外层 `ExecutionInterrupted` 预算异常保留原对象，取消及其他错误不误改。

## 实际验证

| 编号 | 核验 | 结果 |
| --- | --- | --- |
| J01 | 旧实现真实文件写入进程20轮 | 全部重现异步返回／文件占用；历史证据保留 |
| J02 | 首次修复控制19项 | 后代进程等待仍失败；不作为通过证据 |
| J03 | 句柄等待修正后控制19项 | 全部通过；含20轮根进程、父已退后代、独立Job互不干扰、幂等关闭 |
| J04 | 补帧超时3项专项 | 全部通过，含实际原生文件写入子进程和外层预算对象保持 |
| J05 | 完整400项服务契约 | 400项实际执行全部通过，零失败／错误／跳过；不是由专项推导通过 |

[旧实现20轮证据](../validation/evidence/native-worker-bootstrap-20261029-r1/job-close-baseline-r1/verification.json) · [首次修复失败](../validation/evidence/ad-content-uniqueness-20261029-r1/source58-control-r1/verification.json) · [修正后19项](../validation/evidence/ad-content-uniqueness-20261029-r1/source58-control-r2/verification.json) · [超时3项](../validation/evidence/ad-content-uniqueness-20261029-r1/source58-timeout-r1/verification.json)

以上为源码58控制行为；没有把合成传输测试计为神经质量验收。正式Skill仍56，57候选失败记录完整保留；58新包、独立安装和实际模型流程仍须验收。


[源码58完整400项最终收据](../validation/evidence/ad-content-uniqueness-20261029-r1/source58-contracts-r1/verification.json)：原失败超时用例及两项新增预处理用例也在完整组中通过；58独立安装仍另验。
