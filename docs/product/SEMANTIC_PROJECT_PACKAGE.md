# 语义检索与校准工程的离线迁移

CLI 0.1.11 为 `convert export/import --target-format package` 增加语义数据闭环：保留受管目录，按需改写外部源路径，在导入发布前检查内部绑定。
这是 [G31](GOAL_GAPS_20261025.md) 的一个子项；OTIO、MLT 和受限明文草稿仍按各自损失报告处理。

| 编号 | 使用逻辑 | 行为与范围 |
|---|---|---|
| M01 | 在原工程检索、核对候选 | 先完成显式本地模型登记、索引和分别适用的 CPU/CUDA 校准；[检索流程](SEMANTIC_RETRIEVAL.md) |
| M02 | 导出 `package` | 所有引用素材须已在本地；`assets/semantic/` 与 `assets/semantic-calibration/` 保留树结构 |
| M03 | 外部源迁移 | 素材复制到 ZIP，必要的索引 URI、指纹与档案索引引用重新派生；向量、数据集、原观察、阈值、设备和适配器 pin 不变 |
| M04 | 导入新目录 | 检查外层 ZIP 与内部语义绑定后发布；损坏包不会留下可用目标工程 |
| M05 | 在目标工程执行真实检索 | 原模型/运行时/实现 pin 仍须可用。转换不打包权重、不重新信任运行时，也不自动改设备档案 |
| M06 | 客户选材与剪辑 | 展示返回的实际预览、资产 ID、采样点和分数，保留无匹配与错误；再明确片段时长、编排、渲染、核验与交付 |
| M07 | 跨机器或安装升级 | 项目包与模型依赖分别准备；仅安装位置改变且全部实现/依赖字节相同时可显式 `project upgrade-semantic`；内容改变则重新登记和重建，不改旧 pin |

通过 `$agent-ffmpeg-local-editor` 的固定安装入口执行，先读取命令帮助。下例中原工程已经有 `images-v1` 索引和 `accept-cuda` 校准，目标目录须不存在或为空：

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
$sourceProject = 'E:/video-work/my-ad'
$portableProject = 'E:/video-work/my-ad-restored'
$projectZip = 'E:/video-work/my-ad.aevpkg.zip'
& $avk version
& $avk semantic search --project $sourceProject --index-id images-v1 --query '一只猫，不是一杯咖啡' --kind image --calibration-id accept-cuda --device cuda
& $avk convert export --project $sourceProject --target-format package --output $projectZip
& $avk convert import --input $projectZip --output $portableProject
& $avk validate --project $portableProject
& $avk semantic search --project $portableProject --index-id images-v1 --query '一只猫，不是一杯咖啡' --kind image --calibration-id accept-cuda --device cuda
```

检查每条响应的退出码、`ok/status/errors/warnings`，保存两侧真实查询结果和转换报告。
`validate`、转换成功或 `--dry-run` 都不能替代最后一条真实检索。该步骤正是旧 C19 曾暴露迁移失败的地方。

导出不修改原 `project.json`、Rights Ledger、素材、模型或校准数据。需要派生绑定时只在包内生成新版本，原权利限制继续保留。
许可证证据里已有的绝对路径和未随包提供的原生依赖仍须按交付说明逐项复核。

旧 CLI 0.1.10 生成的摊平检索包会在新版导入检查时拒绝。保留旧失败证据，从完好原工程重新导出；本版没有从损坏 ZIP 自动恢复完整索引的工具。

同一安装版内移动工程，与从旧安装升级是两件事。CLI 0.1.15 新增[显式运行时升级](SEMANTIC_RUNTIME_UPGRADE.md)：仅全部 19 个语义实现模块及外部依赖字节相同时派生新适配器/索引/校准 ID，保留原向量、阈值、观察和旧记录，不重新推理；旧安装可以不可访问。改变实现或依赖内容仍须重新登记并重建，不能手改原 pin。使用返回的新 ID 真实查询。

[迁移契约](../specs/语义工程包迁移契约_20261025.md) · [当前完整差距](GOAL_GAPS_20261025.md) · [安装与依赖](COMMUNITY_LOCAL_DELIVERY.md)
