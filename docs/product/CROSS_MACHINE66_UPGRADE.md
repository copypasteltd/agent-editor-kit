# CLI66第二台原生Windows升级与回滚验证

2026-11-06，Asia/Taipei。本批五个操作脚本已经全部写齐，集中完成静态检查后冻结；没有联系第二台机器，也没有执行新版跨机器功能验证。原r6源码完整4,124项通过；本机66安装版整套仍在原进程中运行。正式入口仍CLI0.1.63／local61／r58。

## 本批完成的代码及其状态

| 编号 | 脚本 | 完整实现内容 | 当前结果 |
| --- | --- | --- | --- |
| U01 | `case.py` | 显式绑定63或66安装入口；原始程序图案、440Hz音频、滤镜、可编辑工程包；完整60帧RGBA、非静音PCM、视频时钟和母素材比较 | 已写齐；本批未实际执行 |
| U02 | `remote_baseline.py` | 原63基线保护、新66离线安装、真实`--base-only`配置、注册冲突拒绝、63→66→63→66四次隔离发现入口及完整重放 | 已写齐；本批未实际执行 |
| U03 | `remote_control.py` | 原生Windows-MCP单设备锁、短启动命令、所有权和进程创建时间／映像检查、取回原日志与MP4 | 三个生成命令仅做语法及传输长度检查，未向设备发送 |
| U04 | `transfer_server.py` | 只向指定第二台机器传送已固定摘要的六种输入；临时随机令牌及端口，日志不打印令牌 | 已写齐；没有启动服务 |
| U05 | `prepare_transfer.py` | 完整批次冻结；强制检查本机源码／安装版整套、新版便携工具包及真实媒体基线后才准备传输 | 已写齐；只运行freeze，没有运行primary／parcels |

五个脚本均通过Python编译检查，零SyntaxWarning。启动、状态、取回三条命令的UTF-16 Base64长度分别为7,860／6,040／7,204，均低于既有10,000预算；实际Windows PowerShell解析均为零错误。检查使用不可用的文档示例地址和虚构所有者，仅生成、解析命令，没有执行这些命令，不算远端或产品功能验收。

[完整代码冻结](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-code-phase-r1/verification.json) · [静态结果](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-static-review-r1/verification.json) · [完整五脚本](../validation/cross_machine66_20261106_r1/)。

## 执行前必须具备的真实结果

1. 相同r6冻结实现的源码、安装版完整4,124项均通过，零失败／错误／跳过；安装版不得回退源码。
2. 本地66离线包及289应用模块仍与候选收据一致。
3. 66真实CUDA配乐、完整工程／配方重放等原交付门槛通过，生成r59单Skill工具包。
4. 该工具包实际完成本机独立安装、真实基础配置及隔离注册，取得`portable-kit-r1`通过收据。
5. 第二台旧63基线的目录、所有权、原终态、母素材、应用、工具及配置摘要与原记录一致。

`prepare_transfer.py primary`在源码和安装版整套通过前拒绝执行；`parcels`还要求66工具包实际实装通过。代码静态通过不能替代这些条件。

## 计划中的实际验证

| 编号 | 操作 | 必须取得的证据 |
| --- | --- | --- |
| V01 | 在第二台新目录解包、离线安装66 | 新包／清单摘要及全部289应用模块一致，中文和空格路径实际可用 |
| V02 | 调用归档内真实基础配置器 | `configuration_mode=base-only`，没有模型包验证及旧机器模型路径 |
| V03 | 用原r58注册器将63绑定到新建隔离发现目录 | 一个Skill、17内部模块；实际PowerShell入口重放旧63参考 |
| V04 | 直接用新注册器注册到仍指向63的同一位置 | 原注册器必须拒绝，旧联接及入口保持原样，不生成假成功收据 |
| V05 | 核对既有联接所有权后，显式移除该联接并调用新原注册器 | 实际入口升级为66，并完整重放本机66参考工程 |
| V06 | 同法显式回滚为63，再次升级为66 | 两次均通过实际发现入口完整重放；同版前后全部解码结果相同 |
| V07 | 检查边界及取回原始材料 | 旧归档／应用／私有配置未变，全局Skill发现和PATH未变；保留所有日志和四段真实MP4 |

这里验证的是**原安装器＋基础配置器＋原注册器＋显式受管隔离联接迁移**。迁移仅对本批新建隔离发现目录中的已核实联接操作；使用Windows非递归联接删除，不删除任何规范Skill目录。注册失败时尝试用原注册器恢复旧指向，并保留失败现场。

它不等于通用`delivery activate/recover/rollback`控制器的跨机器验收。该控制器的本机五类门槛、实际故障及正式升级回滚继续按[原交付顺序](DELIVERY66_HANDOFF.md)执行。

## 路径和依赖

- 主项目、临时传输和脚本执行目录均在E盘：`local/agent-ffmpeg/cross-machine66-20261106-r1/`。
- 第二台受管新目录：`C:/dev/agent-editor-kit-upgrade-20261106-r1`；其原生Python位于`C:/dev/comfyUI/python_embeded/python.exe`。
- 第二台旧63基线目录只读复用：`C:/dev/agent-editor-kit-validation-20261106-r2`，原工具和安装不覆盖。
- 第二台使用C盘是该设备既有磁盘布局；不会把主项目迁回本机C盘。
- 不下载模型、不进行GPU推理、不更改全局Python包、驱动、PATH或执行策略，不控制其他GPU任务。
- 不使用Docker、WSL、虚拟机或虚拟环境，不打开浏览器标签。

## 后续集中执行入口

本批r1代码已经冻结，不要覆盖原目录、重跑freeze或修改冻结脚本。当前还不满足执行门槛。门槛通过后使用已冻结的私有执行副本依次执行：

```powershell
$python = 'E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe'
$qa = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/cross-machine66-20261106-r1'
& $python -E -B -u -X utf8 "$qa/prepare_transfer.py" primary
& $python -E -B -u -X utf8 "$qa/prepare_transfer.py" parcels
```

随后启动同目录的临时传输服务，通过`remote_control.py start`只启动一次原生任务，继续查询同一个所有权及实际进程身份，最后取回证据。启动观察超时不代表任务失败，不能因此重复start或改用新目录掩盖原结果。确认输入已下载并校验后关闭临时服务；本批实际输出通过前不制作新演示或宣称迁移成功。

`remote_control.py`内部复用[remote-4090 Skill](C:/Users/carzy/.codex/skills/remote-4090/SKILL.md)的既有原生设备锁及Windows-MCP客户端；设备凭据、临时传输地址和原始桌面观察只保存在被忽略的本地执行目录，不加入公开文档或Git提交。

## 保留的完整目标边界

即使以上CPU迁移通过，GPU模型迁移、干净主机、不同驱动／设备、完整依赖打包、长片资源和自然视听质量仍需单独验收。当前第二台环境已经具备Python和FFmpeg，不能当作首次安装的干净系统。全部G01—G38继续开放，不把本批操作代码、静态检查或四段短视频扩大为剪映等价结论。

[当前源码及候选终态](DELIVERY66_R6_SOURCE_ACCEPTANCE.md) · [旧63真实跨机基线](CROSS_MACHINE63_BASELINE.md) · [完整未完成清单](UNFINISHED_20261106.md)。
