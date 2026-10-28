# CLI0.1.52 / local.50：本地安装与使用 / Local delivery

一个公共 `$agent-ffmpeg-local-editor`、17内部模块、91个Skill文件。对应独立原生Windows运行包；公开alpha.3/CLI0.1.2附件保持原字节。本轮不是新的公开release，也不宣称完整剪映等价。

本地应用ZIP：`local/agent-ffmpeg/v0.1.0-alpha.4-local.50/candidate-r1/bundle.zip`，303223087 bytes，SHA256 `979b54babd7db6d89b0da1e8ee3343657a8f2cb8a95dcfc5d24da6d66f1ad564`；清单 `sha256:a2e511c5ca126dd94bbf1efd3f7ee38eef1d60f0453cfdeed47eda7ebd9b3f39`。已安装目录 `local/agent-ffmpeg/v0.1.0-alpha.4-local.50/final-r1/installed`，278个源码模块逐字节一致。

## 使用流程 / Workflow

1. 使用[匹配应用包与统一Skill安装流程](../product/COMMUNITY_LOCAL_DELIVERY.md)，按任务选择已有模型包。先核对真实version/capabilities；不要混用旧alpha.3运行包或回退源码。
2. 导入[C64完整可编辑工程包](../assets/gpu-gamut-registered-20261029-r1/editable-oklab.aevpkg.zip)到新目录，运行validate。该包含明确GPU require、设备0.0及正式BT.709 SDR映射；部署机器须验证自己的OpenCL FP64设备，不照搬本机编号。
3. 按[GPU色彩完整参数](../product/GPU_GAMUT.md)声明输入/工作/输出信号与nit。正式SDR用display_mapping，HDR母版查看用preview_mapping；显式预览映射优先，否则继承正式映射一次。
4. 实际预览后向客户展示PNG/MP4和配置，检查真实gamut_map计数及端点/裁切统计。随后正式渲染、核对完整音画并导出工程包。

```powershell
$aekSkill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aekSkill version
& $aekSkill capabilities
& $aekSkill convert import --input 'EDITABLE_PACKAGE' --output 'NEW_PROJECT'
& $aekSkill validate --project 'NEW_PROJECT'
& $aekSkill preview frame --project 'NEW_PROJECT' --frame 9 --height 216
& $aekSkill preview range --project 'NEW_PROJECT' --start-frame 0 --end-frame 10 --height 216
& $aekSkill render --project 'NEW_PROJECT' --sequence-id 'seq_main' --output 'NEW_PROJECT/renders/master.mkv'
& $aekSkill convert export --project 'NEW_PROJECT' --target-format package --output 'NEW_PROJECT/exports/editable.aevpkg.zip'
```

帧范围与序列ID取自C64；其他工程读取实际序列/时长。`projection_acceleration.operations.gamut_map`证明实际GPU派发，准备成功或dry-run不证明执行。CPU信号转换、ICC、输出编码与GPU肩部/缩色度分开描述。

源码专项70/70、源码兼容352/352；安装专项70/70、安装兼容352/352分别留证，18项预览测试已包含在各352组中，不另行叠加。C64真实注册入口两次渲染、所有YUV/完整PCM/独立RGB16与工程包重放通过。四个已有模型包完整复核，未新增推理。见[交付报告](../validation/GPU色域映射安装与统一Skill交付_2026-10-29.md)。

仍待跨厂商GPU、自然质量、编码4K/长片/实时、完整ACES/动态HDR/物理监看及[其余原目标](../product/GOAL_GAPS_20261025.md)。繁體：使用匹配套件、實際預覽、檢查GPU派發與完整音畫，再交付可編輯專案。English: Use the matching native runtime and one Skill; validate explicit settings, show actual previews, inspect real GPU receipts and verify complete media/package replay.

## 匹配统一 Skill kit / Matched unified kit

[r53 ZIP](../skills/agent-editor-kit-community-unified-skill-r53.zip)，716918 bytes，SHA256 `e43354629090d0c339ec3e752bc54670455cabc5ac1a15cc3f72911aae2a126f`。[独立包摘要](../skills/community-unified-skill-package-0.1.52-r53.json)。该小包包含Skill与原生安装/注册辅助文件，应用ZIP和可选模型包分别提供，不能独立充当应用运行包。

[独立解压/配置/注册实测](../validation/evidence/gpu-gamut-20261029-r1/kit-r1/verification.json)：150归档条目、149清单条目、91 Skill文件，实际GPU frame/range与48帧编码后光量复核通过。真实C盘发现联接保持不变；同机隔离注册不等于陌生主机/跨GPU厂商验收。
