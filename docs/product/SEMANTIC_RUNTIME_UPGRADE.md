# 语义索引的安装路径升级 / Semantic runtime relocation

CLI **0.1.15** 新增 `project upgrade-semantic`。旧安装路径失效时，在实现和原生依赖字节完全一致的前提下，派生新的适配器、索引和校准记录，复用已有向量，不运行模型。原记录、素材、编辑序列与权利限制保留。

This command explicitly derives new adapter/index/calibration identities for the current installation when every pinned semantic implementation and external dependency remains byte-identical. It copies vectors/previews/datasets, retains fitted thresholds and observations, and performs **zero new model forwards**. It does not repair incompatible model data or improve search quality.

[检索与校准](SEMANTIC_RETRIEVAL.md) · [工程包](SEMANTIC_PROJECT_PACKAGE.md) · [统一入口](SKILLS.md) · [本机安装](COMMUNITY_LOCAL_DELIVERY.md) · [真实实测](../validation/语义运行时升级实测_2026-10-25.md)

## 使用流程

从唯一注册的 `$agent-ffmpeg-local-editor` 调用；`$project` 指向已存在且完整的本地工程。先查看旧适配器 ID、索引 ID 和新命令帮助。

```powershell
$avk = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
$project = 'E:/video-work/my-ad'
& $avk version
& $avk project upgrade-semantic --help
& $avk semantic adapter-list --project $project
& $avk semantic index-list --project $project

# Use actual IDs. The new adapter and derived IDs must be unused.
& $avk project upgrade-semantic --project $project --adapter-id siglip2 --new-adapter-id siglip2_current --id-prefix current --dry-run
& $avk project upgrade-semantic --project $project --adapter-id siglip2 --new-adapter-id siglip2_current --id-prefix current --idempotency-key semantic-runtime-upgrade-1
```

检查退出码、`ok/status/errors/warnings` 和响应中的 `index_mappings`、`calibration_mappings`，使用返回的新 ID。默认升级该适配器的全部索引及其校准；只迁移部分时重复指定 `--index-id`。

```powershell
& $avk project upgrade-semantic --project $project --adapter-id siglip2 --new-adapter-id siglip2_subset --id-prefix selected --index-id images-v1 --timeout-seconds 600
# Replace NEW_INDEX_ID and NEW_CUDA_PROFILE_ID with returned IDs.
& $avk semantic search --project $project --index-id NEW_INDEX_ID --calibration-id NEW_CUDA_PROFILE_ID --kind image --query '一只猫，不是一杯咖啡' --device cuda
& $avk validate --project $project
```

升级本身不会查询；最后一条真实检索需已有外部模型和原生运行库。`auto/cpu/cuda`、GPU 优先和严格 CUDA 的行为由检索命令负责。CPU 与 CUDA 使用各自原校准；本命令不替换设备、不重调阈值。

Use the returned IDs rather than guessing deterministic hashes. A successful dry run establishes eligibility, not a completed migration or a model inference. Run an actual search and inspect returned previews, sampled times, rejected candidates and known errors.

## 精确保留与拒绝条件

当前契约对 19 个语义实现模块逐个比对原记录中的 SHA-256 和长度，包含推理、图像处理、校准和任务管理实现。旧安装无需仍可读取，但原登记摘要须绑定有效 Rights Ledger。外部模型、Python、原生库和许可证据仍须在原登记路径存在并通过校验；不会隐式下载、修改旧 pin 或放宽校验。

随应用安装的 NumPy/Pillow 原生文件按旧 `site/` 内相对位置映射到当前安装，逐个校验 SHA/长度完全一致才派生新运行文件和模块路径。worker 的实际版本与模块路径校验保留；缺失或内容改变仍拒绝。首次真实 GPU 查询暴露的模块路径错误及修复前响应一并留档。

派生索引改变身份、适配器绑定、目标路径和相应指纹；向量、预览、源素材顺序/采样时间及原推理观察保留。派生校准只改变身份与索引绑定，保留数据集字节、cutoff、fit、observations、实际设备和查询协议。继承旧记录的许可证据和权限限制，不提升授权。

`SEMANTIC_UPGRADE_REBUILD_REQUIRED` 表示实现内容或模块集合不同，需要明确登记新适配器并重新建立索引/校准。`SEMANTIC_UPGRADE_DEPENDENCY_CHANGED` 表示外部闭包变化。损坏的源素材、索引、向量、预览、校准或数据集均拒绝升级。损坏的旧 CLI 0.1.10 ZIP 仍须从完好源工程重新导出。

Changed implementation/model/runtime bytes require explicit rebuilding. This is a strict relocation facility, not a numerical compatibility promise between different implementations. Existing integrity errors remain errors until an eligible explicit upgrade succeeds.

## 预算、原子提交和恢复

最多 32 个索引、64 个校准、4096 个预览行、512 MiB 派生负载；既有与新增受管任务合计不超过 256。复制前核对磁盘空间，保留 256 MiB 加两倍负载。原生只读文件锁保护校验和复制，`--timeout-seconds` 与 `--cancel-file` 贯穿读取、复制与提交。

每个索引/校准分别有受管目录；快照、工程事务和幂等记录共同保护提交。普通错误与取消回滚未提交的工程记录；如进程异常退出，先预览并执行现有工程恢复：

```powershell
& $avk project recover --project $project --cleanup-jobs --dry-run
& $avk project recover --project $project --cleanup-jobs
```

重复执行使用相同幂等键；想派生另一套记录须明确更换新 ID 和键。原文件不会就地重写。真实断电、任意磁盘故障和全平台恢复仍按 G33 原条件验收。

## 证据与范围

契约测试与真实 CPU/CUDA/Skill 查询分开留档。真实案例使用冻结的 80 条查询，比较安装路径升级前后的决定、素材排序和分数，并保留 `q14`、`hout00zh`、`hout08zh` 三条已知错误。移走的是案例独有的旧安装及源工程，不移动用户共享安装、不终止其他 GPU 工作。

本功能没有新增视频效果，因此不生成替代性的 GIF；原预览、查询响应、SHA 和迁移记录是核验产物。已有广告、滤镜和视频演示继续可用。跨机器原生依赖安装、大图库、常驻模型与自然语义质量保持原目标范围。
