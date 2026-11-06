# CLI66：r6安装整套通过与候选Skill入口验收

2026-11-06，Asia/Taipei。本批代码已全部写齐、应用并冻结后集中测试。原生安装版r6于2026-11-06 17:24:51结束：**发现并执行4,124项，0失败、0错误、0跳过，退出码0**。原监督与测试子进程均已实际退出，运行包位于独立安装目录，没有源码回退。

| 编号 | 已有实际证据 | 验收边界 |
| --- | --- | --- |
| I01 | 源码r6完整4,124项通过；安装版r6完整4,124项分别通过 | 同一产品套件的两种运行位置，不相加为独立功能覆盖 |
| I02 | 同一546项产品／测试／依赖冻结；原断言与时限保留；289个安装应用模块与源码逐字节一致 | 不等于全部自然视听质量、性能或完整剪映等价 |
| I03 | 安装运行报告实际包路径，按已加载包绑定测试子进程；独立依赖profile及完整日志保留 | 静态子进程复核只覆盖其明确选中范围，不据此承诺所有外部调用路径 |
| I04 | 候选单Skill前置校验、真实PowerShell版本／交付帮助／能力查询通过；95个Skill文件、17内部模块 | 未执行正式切换；正式仍63／local61／r58，原95项正式保护文件未改 |
| I05 | 原衔接进程在核对两套完整终态和726项输入后进入实际66配乐任务 | 任务启动不算CUDA推理成功；完整生成、音频／工程重放、故障与工具包各待独立终态 |

安装unittest原日志7848.433秒；产品运行器7863.206秒；原生监督7882.043秒。各层计时互相包含，不相加，也不据此作源码／安装性能结论。

## 当前本地包与实际入口

- CLI版本：0.1.66；候选应用包版本：v0.1.0-alpha.4-local.64。
- 独立安装：`local/agent-ffmpeg/delivery66/candidate-r1/installed`。
- 应用ZIP：`local/agent-ffmpeg/delivery66/candidate-r1/bundle.zip`。
- ZIP SHA-256：`36b2970f92d24393e6ae6b77636f43b89bea6c3a201aaa164889148feb2d0786`。
- 清单：`sha256:1da7f0a678ea678f49af6d9b847dfd8912b11ede04aad22f8d87ee247ee1117a`。
- 本次候选Skill目录：`local/agent-ffmpeg/delivery66/stage-r1/skills/agent-ffmpeg-local-editor`。

```powershell
$candidateEntry = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/delivery66/stage-r1/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $candidateEntry version # 已实际核验0.1.66
& $candidateEntry delivery --help
& $candidateEntry capabilities
```

以上三个候选命令已实际执行。当前正式入口仍为`C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1`，实际指向正式CLI0.1.63。基础剪辑、500滤镜及既有模块继续按正式63手册使用；候选目录尚未替换正式发现入口。

## 尚需实际完成

66真实CUDA音乐、完整母音频／配方／全帧RGBA与PCM工程包重放、新便携包基础配置与独立注册、第二台63→66→63→66、真实模型取消／超时／发布冲突、正式升级／显式回滚／重激活与实际发现入口、同版三语资料及新alpha.4公开发行继续推进。自然质量、完整听审、干净主机、跨机GPU及全部G01—G38关闭条件保持开放。

原r5五项失败、原r4与更早中断均保留。没有重启已完成的r6、过滤测试、降低断言或修改原生环境。全部执行为原生Windows，无Docker、WSL、虚拟环境或新浏览器标签。

## 原始证据

- [安装版完整终态](../validation/evidence/delivery66-20261106-r1/installed-all-r6/verification.json) · [完整测试日志](../validation/evidence/delivery66-20261106-r1/installed-all-r6/tests.stderr)。
- [原生监督终态](../validation/evidence/delivery66-20261106-r1/native-installed-all-r6/state.json) · [源码完整终态](../validation/evidence/delivery66-20261106-r1/source-all-r6/verification.json)。
- [候选Skill入口](../validation/evidence/delivery66-20261106-r1/skill-entry-r1/verification.json) · [离线应用安装](../validation/evidence/delivery66-20261106-r1/candidate-r1/verification.json)。
- [本轮终态／来源／保护核对](../validation/evidence/delivery66-handoff-20261106-r1/r6-installed-acceptance-r1/verification.json)。
- [完整未完成内容](UNFINISHED_DETAIL_20261106.md) · [后续交付顺序](DELIVERY66_HANDOFF.md) · [原始38组目标](GOAL_GAPS_20261025.md)。
