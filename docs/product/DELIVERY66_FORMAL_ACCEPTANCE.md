# CLI66正式单Skill：升级、显式回滚与真实发现入口

2026-11-06，Asia/Taipei。原五类交付门禁、r59便携安装和三个实际模型故障通过后，使用冻结的原通用交付控制器完成正式升级。[完整收据](../validation/evidence/delivery66-handoff-20261106-r1/formal-entry-r1/verification.json)为`passed`。

| 编号 | 实际执行 | 结果 |
| --- | --- | --- |
| D01 | 检查descriptor并预览升级 | 同版CLI66应用、原源码／安装整套、完整工程、候选Skill、实际CUDA配乐等证据通过原门禁；没有放宽原断言 |
| D02 | 第一次正式升级 | 由原控制器切换唯一Skill至CLI66，实际PowerShell版本入口通过 |
| D03 | 显式回滚 | 恢复CLI63，原95项正式保护文件逐字节相同，旧版实际入口返回0.1.63；保留备份 |
| D04 | 再次正式升级 | 原控制器再次激活CLI66，最终交付ID `e0935d406569489baedec3f6d4b72ed9` |
| D05 | 实际C盘发现入口 | `C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor`解析到项目Skill；实际PowerShell调用独立安装版66，无源码回落 |
| D06 | 完整媒体及文件一致性 | 真实发现入口导入／渲染，完整RGBA／PCM、母WAV和生成配方与已通过的r2工程一致；全部已交付Skill文件与冻结候选相符 |

当前正式安装为**CLI0.1.66／v0.1.0-alpha.4-local.64／r59**，唯一`$agent-ffmpeg-local-editor`，17内部模块、95 Skill文件。原63／local61／r58保留为可回滚历史；第二台显式隔离循环与本机通用控制器正式验收是两组独立结果。

```powershell
$entry = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $entry version # 0.1.66
& $entry doctor
& $entry media --help
& $entry delivery --help
```

使用逻辑：先核对版本和依赖，建立工程并登记有用途记录的素材；展示现有滤镜／音色候选并记录选择；按能力模块检查参数和预算，再执行、预览、完整质检及工程导出／重放。神经音乐仍需要显式已有原生运行库及四个权重，基础剪辑的`--base-only`配置不要求这些模型依赖。

正式升级和文件／音画一致性通过，不代表已完成自然听审、完整高级功能、干净主机迁移、跨设备GPU或所有故障。匹配alpha.4的最终应用ZIP、r59 Skill ZIP、三语快速开始、发布说明、SHA256清单和来源锁现已生成于`local/agent-ffmpeg/delivery66-handoff/release-assets-r1/`，状态为[ready-not-published](../validation/evidence/delivery66-handoff-20261106-r1/release-assets-r1/verification.json)。匹配源提交推送及公开发行／远端附件核对仍待完成。[实际配乐／工程／便携](DELIVERY66_R6_MUSIC_AV_PORTABLE_ACCEPTANCE.md) · [三个真实故障](DELIVERY66_ACTUAL_FAULTS.md) · [详细未完成清单](UNFINISHED_DETAIL_20261106.md)。
