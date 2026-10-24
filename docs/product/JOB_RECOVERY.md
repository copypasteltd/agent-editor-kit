# CLI 0.1.7：任务中断恢复 / Interrupted-job recovery / 工作中斷復原

[简体 README](../../README.md) · [繁體 README](../../README.zh-TW.md) · [English README](../../README.en.md) · [四轨分离](FOUR_STEM_SEPARATION.md) · [完整目标差距](GOAL_GAPS_20261025.md)

本版增加原生 Windows 子进程生命周期管理，以及独立四轨任务的持久化临时目录和输出登记。正常返回、取消或异常会在项目元数据提交或回滚后清理本任务文件；主 CLI 被强制结束后，可显式检查并恢复。

This version adds native Windows process lifetime management and durable workspaces for four-source separation. Explicit recovery restores pending project metadata first, then checks ownership before removing abandoned scratch files or unreferenced outputs. This is a bounded recovery feature; full G33 acceptance remains open.

本版新增原生 Windows 子程序生命週期管理與四軌工作暫存紀錄。強制結束後，請先預覽，再執行明確復原；原始素材、已提交的資產、仍在執行或無法確認歸屬的檔案均有保留規則。

## 使用流程 / Workflow

通过已安装版统一 Skill 执行，先读取 `project recover --help`：

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk project recover --help
& $avk project recover --project 'E:/your-project' --cleanup-jobs --dry-run
& $avk project recover --project 'E:/your-project' --cleanup-jobs
& $avk validate --project 'E:/your-project'
```

1. 保存失败响应和项目路径。中断不会自动恢复推理进度；准备重新执行时使用新的输出前缀。
2. `--dry-run` 检查待恢复元数据和任务计划，不写元数据、不删除文件。查看 `data.job_recovery.jobs` 的状态和输出列表。
3. 明确执行 `--cleanup-jobs` 时先恢复元数据事务，再检查工作目录和资产引用。原始文件被移除或 JSON 损坏时，存在有效事务日志才能恢复；不能凭空重建缺失备份。
4. 核对响应中的 `ok`、`status`、`errors`、`warnings`、`data.job_recovery`，再 `validate`。保留项应人工核对原因，不能以强制删除代替恢复。

Without `--cleanup-jobs`, `project recover` retains its metadata-only behavior. Dry-run is a plan, not a cleanup or successful resume. Normal separation responses expose `data.job_cleanup`; recovery responses expose `data.job_recovery`. Repeating recovery after successful cleanup should report zero newly cleaned jobs.

未加 `--cleanup-jobs` 時仍只復原中繼資料。`--dry-run` 是檢查計畫，不能當成已清理或已續算。

## 归属与保留 / Ownership and preservation

| 内容 / Item | 行为 / Behavior |
|---|---|
| 工作目录 | `cache/managed-jobs/job-<32位十六进制UUID>/`；当前仅 `four-stem-separation` |
| 运行中工作 | `owner.lock` 的原生文件锁作为租约；拿不到租约时 `active_or_locked_preserved`，不按 PID 或年龄猜测 |
| 未提交派生输出 | 发布前持久化目标路径、文件系统身份、字节数及 SHA-256；只有仍匹配且未被工程资产引用的输出才可移除 |
| 已提交资产 | 工程引用的输出返回 `referenced_preserved`，保留四条可编辑音轨及对应文件 |
| 修改或替换的输出 | `changed_output_preserved`；包括字节相同但文件身份不同的替换，保留任务及证据 |
| 未知/受阻目录 | `unverified_or_blocked_preserved`；未知格式、连接/符号链接、损坏登记、无法访问时保留 |
| 原素材与旧缓存 | 原素材、用户文件以及历史 `cache/four-stem-separation/` 等非管理目录保留，不猜测归属 |
| 扫描预算 | 每次最多 256 个任务，每任务 10,000 个目录项、64KiB 登记、128 个输出；超限保留并提示再次检查 |

原生进程管理仅覆盖经共享 `run_process` helper 启动的子进程树。子进程先暂停创建，加入本次调用独占的 Windows Job Object 后才运行；主进程退出/取消/超时时结束该树。创建或加入失败会拒绝执行新子进程，不静默降级。它不结束其他任务，也不是虚拟机、容器或安全沙箱。

The native guard applies to subprocesses started through the shared `run_process` helper, not every custom process path or third-party service. A suspended child joins a private Windows Job Object before application code runs; closing its last handle ends the owned descendants. See Microsoft's [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) and [nested-job semantics](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs).

## 验收边界 / Limits

新机制不迁移或删除旧失败证据；不保存模型的中间张量，不提供原位置断点续算。恢复依赖仍可读取的本地工程、事务备份、有效文件身份和合作式写入。它没有宣称抵御恶意并发改写、任意断电/文件系统损坏，或解决磁盘耗尽、设备丢失、长时并发与公平调度。

Four-source adapters pin implementation files as integrity artifacts. Moving from 0.1.6 to 0.1.7 requires explicit re-registration of the existing environment/model; it must not silently update an old adapter's hashes. The model and native Python remain separately supplied, and unverified model/media rights remain unverified.

本地验收与真实强制中断记录见[任务中断恢复实测](../validation/任务中断恢复实测_2026-10-25.md)。该记录区分原生生命周期测试、真实模型推理和仅用于观察边界的暂停注入；未完成的人类听审与完整 G33 门槛继续保留。
