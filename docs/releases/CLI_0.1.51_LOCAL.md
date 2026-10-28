# CLI0.1.51 / local.49：本地安装与使用 / Local delivery

一个公共 `$agent-ffmpeg-local-editor`、17内部模块、90个Skill文件，匹配r52小kit。公开alpha.3/CLI0.1.2附件保持历史字节；本版本为原生Windows本地安装与验收，不是新的公开release。

应用ZIP：`local/agent-ffmpeg/v0.1.0-alpha.4-local.49/candidate-r2/bundle.zip`，303220972 bytes，SHA256 `b9e61e026690dd25dcd6b9635f529a2a775f15a2f83bc91938ceeacf30cf5529`。清单 `sha256:9f8fd3c0d03cca6c8d44a3e6ab86ffb2cab8e36b0d7f3ee57e19c2afbe7e2316`。已安装目录 `local/agent-ffmpeg/v0.1.0-alpha.4-local.49/final-r2/installed`。

## 使用流程 / Workflow

1. 按[完整离线安装流程](../product/COMMUNITY_LOCAL_DELIVERY.md)安装匹配应用ZIP和按任务选择的模型包；不要将旧alpha.3运行包与新Skill混用。
2. 调用唯一已注册入口，先核对版本，再导入[正确工程包](../assets/oklab-registered-20261029-r2/editable-oklab.aevpkg.zip)到新的本地目录。
3. validate后，按[完整OKLab配置](../product/OKLAB_GAMUT.md)明确输入、线性工作与输出信号、nit、映射策略。正式SDR用display_mapping；HDR母版查看用preview_mapping，后者优先。
4. 输出实际PNG/MP4供客户选型，保留配置与裁切/端点计数。正式成片另做实际媒体测量、工程包往返与声音核对。

```powershell
$aekSkill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aekSkill version
& $aekSkill convert import --input 'EDITABLE_PACKAGE' --output 'NEW_PROJECT'
& $aekSkill validate --project 'NEW_PROJECT'
& $aekSkill preview frame --project 'NEW_PROJECT' --frame 9 --height 216
& $aekSkill preview range --project 'NEW_PROJECT' --start-frame 0 --end-frame 10 --height 216
& $aekSkill render --project 'NEW_PROJECT' --sequence-id 'seq_main' --output 'NEW_PROJECT/renders/master.mkv'
& $aekSkill convert export --project 'NEW_PROJECT' --target-format package --output 'NEW_PROJECT/exports/editable.aevpkg.zip'
```

以上帧范围和seq_main对应C62示例；其他工程先读取实际序列ID、帧率与总帧数，输出路径使用工程内的新文件。

本轮安装专项64/64、预览18/18、完整兼容352/352分别通过；15项色域专项是64子集，不累加。277份产品Python文件与离线安装逐字节一致。C62真实Skill的两次渲染、全部YUV与完整PCM包重放通过。四个已有模型包重新核验，没有新增模型推理。

C62首轮r1的整份project.json不变断言错误包含了正常render输出/操作日志，保留[失败分析](../validation/evidence/oklab-gamut-20261029-r1/registered-case-r1/failure-analysis.json)。最终r2分别验证作者图不变、渲染只追加允许的输出日志、预览/导出不改工程字节；未修改产品实现或重跑已冻结的352门禁。两轮各执行2次真实渲染，最终验收统计指r2。

本轮保留首候选预览失败与C61重复ID勘误；[修复与失败历史](../validation/SDR预览映射修复_2026-10-29.md)。CPU OKLab不是GPU算子、软拐点或ACES；自然肤色/连续镜头/4K长片/动态HDR/物理监看及[38组原目标](../product/GOAL_GAPS_20261025.md)继续建设。

繁體：已安裝單入口Skill，明確參數後先validate再預覽與算繪，保留工程包與全音畫證據。English: Use the matching local runtime and single registered Skill. Validate explicit colour/nit/mapping configuration, show actual previews, and verify full media/package replay. Public alpha.3 remains historical; full CapCut parity is not claimed.
