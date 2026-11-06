# CLI66交付后半程与原生完整回归

2026-11-06，Asia/Taipei。正式入口仍CLI0.1.63／local61／r58。完整修正20文件已一次写齐、备份、应用并冻结r5；产品及依赖546文件、交付工具7文件、原正式文件95项。31项完整交付契约通过，零失败／错误／跳过；应用和bare-worker实际隔离预检通过。产品全套实际发现4,124项，仍运行、无终态。

原r4已完整执行4,114项，10失败／15错误／0跳过，原冻结一致；原r2的4,110项中断及初轮8处跳过仍保留。r4中的12项会话用例均ok，属于原整套子集。新代码、31项工具检查及依赖预检均不等于新版安装、实际模型／媒体、正式切换或发行已通过。

| 编号 | 本批完整代码 | 核验边界 |
| --- | --- | --- |
| H01 | 原生后台监督：启动／状态查询、进程创建时间及映像身份、子命令日志、实际退出码与结果摘要 | 明确脱离终端作业；主机拒绝时记录失败，不静默退回原会话；存活判断查询实际进程，不能只看文件或PID |
| H02 | 配乐输出冲突和其他文件错误转为结构化CLI错误；次级报告删除错误不掩盖原错误 | 新增4项真实CLI／事务边界用例，工作进程明确模拟，不冒充神经推理 |
| H03 | 复用现有单Skill打包器，增加三语快速开始与交付说明；完整ZIP路径／类型／预算／CRC／摘要预检 | 保持一个公开Skill与17内部模块；独立安装与注册另验，构建不等于验收 |
| H04 | 新路径独立解包、应用自带安装器、隔离注册、实际PowerShell入口、整段RGBA／PCM及母音频／配方重放 | 使用同一主机既有依赖；不算第二台或干净主机 |
| H05 | 真实配乐取消、超时、提交冲突三类故障工具 | 使用实际安装版与原生模型，不修改产品函数；取消等到真实扩散回调，冲突需完整四组件CUDA与独立PCM；尚待实际运行 |
| H06 | 五类原门禁＋便携包＋实际故障后，正式升级→显式回滚→再次升级→实际发现入口重放 | 失败尝试回滚，保留备份；不能以版本查询代替实际媒体验收 |
| H07 | 生成应用ZIP、唯一Skill ZIP、三语快速开始、发布说明与SHA256清单；匹配源提交后新建alpha.4 | 公开下载不含未审核模型音频；不覆盖既有标签或附件，缺发布凭据时保留本地可审阅成果 |
| H08 | 下一批9文件候选增加产品、8交付工具、69构建来源、实际Skill／注册及三语README的提交绑定，保留原始摘要与Git换行规范化 | 新增11契约、下一轮计划42项，未执行／应用；r5原31项通过不能替代新批验证。[范围](DELIVERY66_RELEASE_BINDING.md) |
| H09 | 构建来源贯穿基础／最终ZIP、便携实装、正式入口及发布锁；新增文档外链固定发行标签；TTS断网用例显式绑定被测包 | 69来源、62原手册及19处子进程AST复核；实际新包与断网断言另验。[实现及边界](DELIVERY66_PACKAGING_PROVENANCE.md) |

[原r4完整结果与25条异常归因](DELIVERY66_R4_RESULTS.md) · [20文件完整修正](DELIVERY66_R5_CANDIDATE.md) · [31项真实工具结果](../validation/evidence/delivery66-handoff-20261106-r1/contracts-r4/verification.json) · [当前运行观察](../validation/evidence/delivery66-handoff-20261106-r1/correction-batch-review-r1/verification.json)。历史17／18项工具组与各个草稿静态快照保留，不和当前31项相加。

本批后续证据在docs/validation/evidence/delivery66-handoff-20261106-r1/；原／新源码及安装整套在docs/validation/evidence/delivery66-20261106-r1/。全部新临时、安装和模型任务输出保存在E盘local/agent-ffmpeg/下。全程原生Windows，无Docker、WSL、虚拟环境或浏览器交互。

## 集中执行顺序

先完成全部本批代码再集中测试；以下是当前r5批次的复现顺序，已经存在的收据不可覆盖，不要再次启动同编号。发现问题后等整套结果汇总，再一次补完所有修正，另用新freeze／run编号。

既有E盘原生嵌入式Python不会自动把交付脚本目录加入sys.path。显式只加入该工具目录可运行工具间导入，不改解释器／._pth，不将产品源码注入正式Skill。首次未设置该目录的contracts-r3在发现测试前失败；同批无代码修改，完整contracts-r4通过31项。

```powershell
$python = 'E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe'
$toolBootstrap = 'import sys,runpy;from pathlib import Path;p=Path(sys.argv[1]).resolve();sys.path.insert(0,str(p.parent));sys.argv=sys.argv[1:];runpy.run_path(str(p),run_name="__main__")'
function Invoke-AekDeliveryTool {
    param([string]$Script, [string[]]$ToolArguments)
    & $python -E -B -u -X utf8 -c $toolBootstrap $Script @ToolArguments
    if ($LASTEXITCODE -ne 0) { throw "Delivery tool failed: $Script" }
}
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments @('freeze', '--run', 'r5')
Invoke-AekDeliveryTool -Script 'docs/validation/test_delivery66_handoff.py'
Invoke-AekDeliveryTool -Script 'docs/validation/run_delivery66_native.py' -ToolArguments @('start', '--run', 'r5', '--freeze-run', 'r5')
Invoke-AekDeliveryTool -Script 'docs/validation/run_delivery66_native.py' -ToolArguments @('status', '--run', 'r5', '--freeze-run', 'r5')
```

完整源码终态真正通过后，才按相同冻结构建离线候选。每条命令显式传入`--freeze-run r5 --tests-run r5`，不要沿用工具的历史默认r4。下方r1为后半程计划编号；若已有目录，选择新编号并在所有后续引用中统一。

```powershell
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments @('build', '--run', 'r1', '--freeze-run', 'r5', '--tests-run', 'r5')
$installed = Join-Path (Get-Location) 'local/agent-ffmpeg/delivery66/candidate-r1/installed'
Invoke-AekDeliveryTool -Script 'docs/validation/run_delivery66_native.py' -ToolArguments @('start', '--installed', $installed, '--run', 'r5', '--freeze-run', 'r5')
Invoke-AekDeliveryTool -Script 'docs/validation/run_delivery66_native.py' -ToolArguments @('status', '--installed', $installed, '--run', 'r5', '--freeze-run', 'r5')
```

安装版完整回归通过后依次stage、music、package、descriptor。实际music必须来自66新安装和新输出，不使用65旧成功代替；应用和bare-worker依赖分别按实际来源报告。

```powershell
$roundPins = @('--run', 'r1', '--freeze-run', 'r5', '--tests-run', 'r5')
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments (@('stage') + $roundPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments (@('music') + $roundPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments (@('package') + $roundPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments (@('descriptor') + $roundPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_handoff.py' -ToolArguments (@('kit') + $roundPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_handoff.py' -ToolArguments (@('verify-kit') + $roundPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_music_faults.py' -ToolArguments $roundPins
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_handoff.py' -ToolArguments (@('activate') + $roundPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_handoff.py' -ToolArguments (@('assets') + $roundPins)
```

kit只是构建。verify-kit才在独立中文／空格路径用真实安装器安装，调用真实`--base-only`配置器后注册一个Skill，再通过PowerShell入口重放全部RGBA／PCM／母音频和配方。基础剪辑不需要预先安装四个模型包；可选--packs路径仍验证完整包，模型／CUDA配置另外执行。这是同机独立路径验收，不是第二台／干净主机。

activate仍须源码／安装／工程／Skill／真实CUDA音乐五类原门禁、独立便携验收和取消／超时／提交冲突三个真实模型故障全部通过，再进行正式升级、显式回滚、重激活和实际发现入口媒体验收。正式文件变更失败时保留可恢复现场，不靠version查询代替媒体验收。

assets只准备可审阅本地附件。随后提交并普通推送完全匹配的源码与三语README，再将真实完整源提交ID及附件目录传给publish_delivery66.py先校验；加--publish才新建alpha.4。发布器使用显式环境身份→既有原生gh→旧Git助手；秘密仅在内存，禁止认证重定向。既有标签、附件和发行记录不可覆盖。

## 使用流程及未关闭范围

三份快速开始含实际安装、基础配置、可选模型来源／构建／离线安装、分别CUDA目录、唯一Skill、真实asset/clip ID、客户滤镜预览、音轨、预览／渲染／质检及工程包重放。目前仍是占位摘要草稿；独立安装通过后才填入真实摘要和附件。30段原生PowerShell语法0错误只证明可解析，不证明各流程执行通过。

应用ZIP不包含原生Python、FFmpeg、驱动、全部模型和整个外部音乐运行库。实际配乐仍是internal/unverified；完整听审、自然质量、长曲／演唱／更多曲风、资源性能及发布权利分别验收。没有用本轮31项工具测试关闭G01—G38，也没有把同机隔离路径等同跨机器。

[完整未完成清单](UNFINISHED_20261106.md) · [原38组目标](GOAL_GAPS_20261025.md) · [原生依赖与日志](NATIVE_TEST_DEPENDENCIES_20261106.md)。

当前r5即时日志最新检查点记录5个问题事件，新增TTS断网用例子进程找不到应用包；下一批现为9文件候选，包含子进程／音频、发布绑定及69构建来源冻结。原断言、ASCII对抗管道与锁门槛保留；全部289应用模块候选静态无未绑定名称。原546／7／95冻结完整保留，42项工具整套仅为计划，待r5终态后一次补齐所有发现。[新批完整说明及证据](DELIVERY66_R6_CANDIDATE.md)。
