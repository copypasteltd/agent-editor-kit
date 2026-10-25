# 语义任务的中断恢复与诊断

CLI 0.1.12 本机安装版把 `semantic adapter-register/index/calibrate/search` 纳入受管任务。
安装版、统一 Skill 和真实故障范围以本轮实测收据为准；执行前先检查 `version`、`capabilities` 和命令帮助。

| 编号 | 使用场景 | 操作及保留内容 |
|---|---|---|
| S01 | 正常登记、建索引、校准或检索 | 返回 `managed_workspace`；请求、进程、响应及阶段文件保留在该目录，正常完成不自动删证据 |
| S02 | 取消或超时 | 使用任务的 `--cancel-file` / `--timeout-seconds`；只终止本次受管进程，保留失败与实际设备信息 |
| S03 | CLI 被强制结束 | 先执行恢复 dry-run；检查待恢复事务、任务归属、未引用产物与保留原因 |
| S04 | 确认回收 | `project recover --cleanup-jobs` 先恢复事务元数据，再检查文件/目录身份与 SHA；已提交引用保护整棵索引或校准目录 |
| S05 | 检查重用 | `validate` 之后运行真实 `semantic search`；有索引/校准记录或 dry-run 成功均不能代替真实查询 |
| S06 | 原始执行证据需交付 | 显式清理前复制需要的请求、响应、失败和样例；恢复清理会移除未引用的受管缓存 |
| S07 | 用户改过文件或目录 | 报告保留原因，不强制删除；包括同字节文件替换、目录替换、额外文件和新空目录 |
| S08 | 升级后的旧适配器 | 仍须明确重新登记新 adapter/index/calibration ID，保留旧证据；不手工改 SHA |

通过唯一 `$agent-ffmpeg-local-editor` 的固定安装入口执行，`$project` 使用实际工程路径：

```powershell
& $avk version
& $avk project recover --project $project --cleanup-jobs --dry-run
# 先检查返回的 pending、metadata_rollback_pending、jobs 和各项保留理由。
& $avk project recover --project $project --cleanup-jobs
& $avk validate --project $project
& $avk semantic search --project $project --index-id images-v1 --query '一只猫，不是一杯咖啡' --kind image --calibration-id accept-cuda --device cuda
```

读取响应的退出码、`ok/status/errors/warnings`；恢复报告位于 `data.job_recovery`。
默认 `project recover` 仅处理元数据。恢复不是重新运行模型，也不是推理断点续跑。
活跃任务的原生租约会阻止清理；真实清理依然要求工程写锁。不要用递归删除整个 cache 代替恢复命令。

新任务使用 `cache/managed-jobs/`，旧 `cache/semantic-jobs/` 留作历史，不自动接管。
发布前写入文件与目录身份、SHA 和唯一目的地；只接受本任务的语义命名空间。
目录中任一资产或活动权利证据仍被工程引用时，保留该目录全部文件。

`worker-phase.json` 记录当前阶段；最终响应的 `phase_seconds` 分开记录环境准备、原生依赖导入、
适配器校验、模型加载和推理。阶段文件用于诊断，不是操作系统隔离、进度百分比或剩余时间估计。
模型仍在每个命令内加载，尚无常驻服务；已有同步完整性检查可能使总超时响应延后，须报告实际墙钟。

本契约没有关闭自然检索质量、断电、磁盘耗尽、设备丢失、恶意主机隔离、长并发或完整 G32/G33。
完整原条件见 [G01–G38](GOAL_GAPS_20261025.md)，工程迁移另见[语义工程包](SEMANTIC_PROJECT_PACKAGE.md)。


[本批实际核验与失败](../validation/语义任务中断恢复实测_2026-10-25.md) · [C21](CASES.md#c21-semantic-recovery)。
