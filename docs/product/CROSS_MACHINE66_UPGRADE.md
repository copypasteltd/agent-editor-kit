# CLI66第二台原生Windows升级与回滚验证

**最新实际终态：2026-11-06 18:20，Asia/Taipei，第二台原生Windows的CPU63→66→63→66已通过。** 离线安装、`--base-only`、四次完整RGBA／PCM／时钟／母素材检查及原文件保护通过；传输进程退出且端口关闭。[完整结果及实际MP4](CROSS_MACHINE66_RESULTS.md)。这是显式受管隔离联接迁移，非通用正式控制器、GPU或干净主机验收。本机正式入口仍CLI63。

以下保留**本批代码冻结时的历史快照与执行约束**。当时五个操作脚本全部写齐、静态检查后冻结，尚未联系第二台；原r6源码完整4,124项通过，本机安装版尚在运行。该快照的“未执行”不能代替上方已经取得的实际终态。

后续衔接执行器及其契约用例整批完成并另行冻结；17项原生解释器契约检查全部通过，0失败／错误／跳过。它串起已有五脚本的门槛、一次启动、实际进程观察、传输关闭和四次媒体证据回收；该代码检查时尚未执行远程任务，随后才取得上方真实CPU终态。[代码冻结](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-controller-code-phase-r1/verification.json) · [17项实际契约结果](../validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-controller-contracts-r1/verification.json)。

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

## 衔接执行器与集中契约检查

[continue_controller.py](../validation/cross_machine66_20261106_r1/continue_controller.py)是一次性、有时限的执行工具。它不接管原安装整套、不重复准备已存在的primary／parcels，也不安装新MCP服务。执行前仍须原源码和安装版各4,124项完整通过、实际66便携包通过，并已有六份摘要锁定的parcels。

本次17项检查使用明确标注的协议夹具与E盘临时目录，覆盖实际存活优先于表面终态、错误所有权／解释器／进程身份、观察超时后原句柄、无终态退出、缺下载证明、锁屏／过期预检、路径逃逸、私密内容拦截、完整四次回放与母机参考绑定、返回MP4摘要及既有证据保护。它们不启动远端、不生成模型结果，不与产品4,124项或原43项工具契约相加。

| 编号 | 执行器行为 | 可证明的边界 |
| --- | --- | --- |
| C01 | 读取正式remote-4090客户端生成的900秒内状态记录，核对主机、输入桌面和Agent实际查看的截图摘要 | `ready`本身不足以证明已解锁；截图仅保留在本地私有运行记录，不公开桌面 |
| C02 | 重验原源码／安装／便携门槛、六个传输角色及本批冻结代码／契约摘要 | 不以文件存在或17项夹具代替真实主流程通过 |
| C03 | 临时服务仅服务已锁定文件和指定设备；只调用一次远端start | start观察失败后只查询原所有权，不换编号重启；本地客户端仍存活时不并发新RPC |
| C04 | 按创建时间、映像和所有权观察同一个实际远端进程 | 实际存活时，即使出现表面passed收据，也继续观察；缺终态不算通过 |
| C05 | 输入下载并校验后关闭本次服务并确认其实际进程退出 | 不终止远端已有GPU任务，不更改全局注册或系统配置 |
| C06 | 收齐63→66→63→66四次真实回放，逐次对照各版本母机参考、60帧／完整PCM、时钟和返回MP4摘要 | 不要求63与66的图像跨版本相等；本批只验CPU及显式隔离注册迁移 |
| C07 | 有界返回、拒绝目录重解析／路径逃逸／私密材料，完整写入暂存目录后一次改名发布 | 已存在的公开证据拒绝覆盖；失败日志保留在私有目录供复核 |

门槛真正通过后，先通过Skill客户端取得当前设备状态：

```powershell
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$python = 'E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe'
$remoteClient = 'C:/Users/carzy/.codex/skills/remote-4090/scripts/windows_mcp.py'
$statusLines = & $python -E -B -u -X utf8 $remoteClient --timeout 55 --network-mode direct status
if ($LASTEXITCODE -ne 0) { throw 'Inspect the retained device status before proceeding.' }
$deviceStatus = $statusLines[-1] | ConvertFrom-Json
$deviceSummary = Join-Path $deviceStatus.output 'summary.json'
$screenPath = @($deviceStatus.calls | Where-Object { $_.name -eq 'Screenshot' })[0].images[0]
```

Agent随后须用图像查看工具实际检查`$screenPath`，并核对本次设备探针；这是[remote-4090 Skill](C:/Users/carzy/.codex/skills/remote-4090/SKILL.md)已有的状态／截图步骤。确认后按实际截图计算摘要，在预检仍有效时执行：

```powershell
$screenSha256 = (Get-FileHash -LiteralPath $screenPath -Algorithm SHA256).Hash.ToLowerInvariant()
& $python -E -B -u -X utf8 'docs/validation/cross_machine66_20261106_r1/continue_controller.py' --preflight $deviceSummary --reviewed-screenshot-sha256 $screenSha256
if ($LASTEXITCODE -ne 0) { throw 'Inspect the original owned run and retained logs; do not repeat start.' }
```

执行器状态在`local/agent-ffmpeg/cross-machine66-controller-20261106-r1/state.json`；只有全部实际条件满足，才将远端原始收据、四段MP4和允许的日志写入`docs/validation/evidence/delivery66-cross-machine-20261106-r1/upgrade66-remote-r1/`。该目录目前尚未生成；脚本、契约通过或命令示例均不表示远端实测完成。

## 保留的完整目标边界

即使以上CPU迁移通过，GPU模型迁移、干净主机、不同驱动／设备、完整依赖打包、长片资源和自然视听质量仍需单独验收。当前第二台环境已经具备Python和FFmpeg，不能当作首次安装的干净系统。全部G01—G38继续开放，不把本批操作代码、静态检查或四段短视频扩大为剪映等价结论。

[当前源码及候选终态](DELIVERY66_R6_SOURCE_ACCEPTANCE.md) · [旧63真实跨机基线](CROSS_MACHINE63_BASELINE.md) · [完整未完成清单](UNFINISHED_20261106.md)。
