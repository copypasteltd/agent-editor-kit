# CLI66交付后半程与原生完整回归

**后续实际终态已取得：** [三个真实故障](DELIVERY66_ACTUAL_FAULTS.md)及[本机正式66升级／回滚／实际C盘入口](DELIVERY66_FORMAL_ACCEPTANCE.md)均通过。下文保留各阶段原时点的边界；当前正式为CLI66／local64／r59，公开发行仍待。

2026-11-06，Asia/Taipei。正式入口仍CLI0.1.63／local61／r58。原r6源码与安装分别完整4,124项通过、0失败／错误／跳过、退出码0；候选CLI66真实CUDA配乐、r2完整音画工程、r59便携安装和第二台CPU63→66→63→66均已通过。真实故障、正式发现入口与发行仍按各自实际终态验收。[安装终态](DELIVERY66_R6_INSTALLED_ACCEPTANCE.md) · [音乐／音画／便携终态](DELIVERY66_R6_MUSIC_AV_PORTABLE_ACCEPTANCE.md) · [第二台结果](CROSS_MACHINE66_RESULTS.md)。原546产品／用例／依赖、8工具、69构建来源及95正式文件继续保持r6字节。

原r4已完整执行4,114项，10失败／15错误／0跳过，原冻结一致；原r2的4,110项中断及初轮8处跳过仍保留。r4中的12项会话用例均ok，属于原整套子集。新代码、43项工具检查及依赖预检均不等于新版安装、实际模型／媒体、正式切换或发行已通过。

| 编号 | 本批完整代码 | 核验边界 |
| --- | --- | --- |
| H01 | 原生后台监督：启动／状态查询、进程创建时间及映像身份、子命令日志、实际退出码与结果摘要 | 明确脱离终端作业；主机拒绝时记录失败，不静默退回原会话；存活判断查询实际进程，不能只看文件或PID |
| H02 | 配乐输出冲突和其他文件错误转为结构化CLI错误；次级报告删除错误不掩盖原错误 | 新增4项真实CLI／事务边界用例，工作进程明确模拟，不冒充神经推理 |
| H03 | 复用现有单Skill打包器，增加三语快速开始与交付说明；完整ZIP路径／类型／预算／CRC／摘要预检 | 保持一个公开Skill与17内部模块；独立安装与注册另验，构建不等于验收 |
| H04 | 新路径独立解包、应用自带安装器、隔离注册、实际PowerShell入口、整段RGBA／PCM及母音频／配方重放 | 使用同一主机既有依赖；不算第二台或干净主机 |
| H05 | 真实配乐取消、超时、提交冲突三类故障工具 | 使用实际安装版与原生模型，不修改产品函数；取消等到真实扩散回调，冲突需完整四组件CUDA与独立PCM；尚待实际运行 |
| H06 | 五类原门禁＋便携包＋实际故障后，正式升级→显式回滚→再次升级→实际发现入口重放 | 失败尝试回滚，保留备份；不能以版本查询代替实际媒体验收 |
| H07 | 生成应用ZIP、唯一Skill ZIP、三语快速开始、发布说明与SHA256清单；匹配源提交后新建alpha.4 | 公开下载不含未审核模型音频；不覆盖既有标签或附件，缺发布凭据时保留本地可审阅成果 |
| H08 | 下一批9文件候选增加产品、8交付工具、69构建来源、实际Skill／注册及三语README的提交绑定，保留原始摘要与Git换行规范化 | 保留原31方法／断言，完整43项已通过；9文件已应用，产品整套及实际交付仍待验证。[范围](DELIVERY66_RELEASE_BINDING.md) |
| H09 | 构建来源贯穿基础／最终ZIP、便携实装、正式入口及发布锁；新增文档外链固定发行标签；TTS断网用例显式绑定被测包 | 69来源、62原手册及19处子进程AST复核；实际新包与断网断言另验。[实现及边界](DELIVERY66_PACKAGING_PROVENANCE.md) |
| H10 | 新Skill说明直接来自冻结工具常量；官方校验器在输出前及执行后核对摘要；4份安装／素材手册恢复当前63版本层 | 9文件已应用、43工具契约通过；历史手册完整保留，不切换正式入口。[生成输入](DELIVERY66_STAGE_INPUTS.md) |

[原r4完整结果与25条异常归因](DELIVERY66_R4_RESULTS.md) · [20文件完整修正](DELIVERY66_R5_CANDIDATE.md) · [31项真实工具结果](../validation/evidence/delivery66-handoff-20261106-r1/contracts-r4/verification.json) · [当前运行观察](../validation/evidence/delivery66-handoff-20261106-r1/correction-batch-review-r1/verification.json)。历史17／18项工具组与各个草稿静态快照保留，不与当前43项相加。

本批后续证据在docs/validation/evidence/delivery66-handoff-20261106-r1/；原／新源码及安装整套在docs/validation/evidence/delivery66-20261106-r1/。全部新临时、安装和模型任务输出保存在E盘local/agent-ffmpeg/下。全程原生Windows，无Docker、WSL、虚拟环境或浏览器交互。

## 集中执行顺序

先完成全部本批代码再集中测试；以下是当前r6批次的复现顺序，已经存在的收据不可覆盖，不要再次启动同编号。发现问题后等整套结果汇总，再一次补完所有修正，另用新freeze／run编号。

既有E盘原生嵌入式Python不会自动把交付脚本目录加入sys.path。显式只加入该工具目录可运行工具间导入，不改解释器／._pth，不将产品源码注入正式Skill。首次未设置该目录的contracts-r3在发现测试前失败；同批无代码修改，完整contracts-r4通过31项。

```powershell
$python = 'E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe'
$toolBootstrap = 'import sys,runpy;from pathlib import Path;p=Path(sys.argv[1]).resolve();sys.path.insert(0,str(p.parent));sys.argv=sys.argv[1:];runpy.run_path(str(p),run_name="__main__")'
function Invoke-AekDeliveryTool {
    param([string]$Script, [string[]]$ToolArguments)
    & $python -E -B -u -X utf8 -c $toolBootstrap $Script @ToolArguments
    if ($LASTEXITCODE -ne 0) { throw "Delivery tool failed: $Script" }
}
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments @('freeze', '--run', 'r6')
Invoke-AekDeliveryTool -Script 'docs/validation/test_delivery66_handoff.py'
Invoke-AekDeliveryTool -Script 'docs/validation/run_delivery66_native.py' -ToolArguments @('start', '--run', 'r6', '--freeze-run', 'r6')
Invoke-AekDeliveryTool -Script 'docs/validation/run_delivery66_native.py' -ToolArguments @('status', '--run', 'r6', '--freeze-run', 'r6')
```

完整源码终态真正通过后，才按相同冻结构建离线候选。每条命令显式传入`--freeze-run r6 --tests-run r6`，不要沿用工具的历史默认r4。下方r1为后半程计划编号；若已有目录，选择新编号并在所有后续引用中统一。

```powershell
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments @('build', '--run', 'r1', '--freeze-run', 'r6', '--tests-run', 'r6')
$installed = Join-Path (Get-Location) 'local/agent-ffmpeg/delivery66/candidate-r1/installed'
Invoke-AekDeliveryTool -Script 'docs/validation/run_delivery66_native.py' -ToolArguments @('start', '--installed', $installed, '--run', 'r6', '--freeze-run', 'r6')
Invoke-AekDeliveryTool -Script 'docs/validation/run_delivery66_native.py' -ToolArguments @('status', '--installed', $installed, '--run', 'r6', '--freeze-run', 'r6')
```

安装版完整回归通过后，stage-r1与music-r1已经完成。原package-replay-r1将纯音乐工程当作视频渲染，实际以VIDEO_TRACK_EMPTY拒绝；失败日志完整保留，不重跑、不修改产品空画面保护。三个替代验收／衔接文件先写齐冻结，8项独立AV契约通过后，用r2在派生工程添加合法画面并完成全部媒体重放；原生曲工程未变。

以下明确展示实际采用的编号关系；已存在的目录只读取收据，不重复执行。原r6的8个工具保持冻结，AV helper独立固定摘要。后续所有门槛统一指定`--package-run r2`，避免误读保留的失败r1。

```powershell
$roundPins = @('--run', 'r1', '--freeze-run', 'r6', '--tests-run', 'r6')
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments (@('stage') + $roundPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments (@('music') + $roundPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_av_replay.py' -ToolArguments @('--run', 'r2', '--freeze-run', 'r6', '--tests-run', 'r6')
$handoffPins = $roundPins + @('--package-run', 'r2')
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66.py' -ToolArguments (@('descriptor') + $handoffPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_handoff.py' -ToolArguments (@('kit') + $handoffPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_handoff.py' -ToolArguments (@('verify-kit') + $handoffPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_music_faults.py' -ToolArguments $handoffPins
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_handoff.py' -ToolArguments (@('activate') + $handoffPins)
Invoke-AekDeliveryTool -Script 'docs/validation/delivery66_handoff.py' -ToolArguments (@('assets') + $handoffPins)
```

kit只是构建；r59的verify-kit已实际在独立中文／空格路径用真实安装器安装，调用真实`--base-only`配置器后注册一个Skill，再通过PowerShell入口重放全部RGBA／PCM／母音频和配方。基础剪辑不需要预先安装四个模型包；可选--packs路径仍验证完整包，模型／CUDA配置另外执行。这是同机独立路径验收；另有第二台CPU升级结果，二者均不冒充干净主机。

activate仍须源码／安装／工程／Skill／真实CUDA音乐五类原门禁、独立便携验收和取消／超时／提交冲突三个真实模型故障全部通过，再进行正式升级、显式回滚、重激活和实际发现入口媒体验收。正式文件变更失败时保留可恢复现场，不靠version查询代替媒体验收。

assets只准备可审阅本地附件。随后提交并普通推送完全匹配的源码与三语README，再将真实完整源提交ID及附件目录传给publish_delivery66.py先校验；加--publish才新建alpha.4。发布器使用显式环境身份→既有原生gh→旧Git助手；秘密仅在内存，禁止认证重定向。既有标签、附件和发行记录不可覆盖。

## 使用流程及未关闭范围

三份快速开始含实际安装、基础配置、可选模型来源／构建／离线安装、分别CUDA目录、唯一Skill、真实asset/clip ID、客户滤镜预览、音轨、预览／渲染／质检及工程包重放。目前仍是占位摘要草稿；独立安装通过后才填入真实摘要和附件。30段原生PowerShell语法0错误只证明可解析，不证明各流程执行通过。

应用ZIP不包含原生Python、FFmpeg、驱动、全部模型和整个外部音乐运行库。实际配乐仍是internal/unverified；完整听审、自然质量、长曲／演唱／更多曲风、资源性能及发布权利分别验收。没有用本轮31项工具测试关闭G01—G38，也没有把同机隔离路径等同跨机器。

[完整未完成清单](UNFINISHED_20261106.md) · [原38组目标](GOAL_GAPS_20261025.md) · [原生依赖与日志](NATIVE_TEST_DEPENDENCIES_20261106.md)。

原r5完整终态保留5条问题堆栈；9文件已应用并冻结r6，43项工具整套及源码／安装各自4,124项完整通过。CLI／音频／TTS原断言和门槛未放宽。三个AV修正文件另行先写齐冻结再验证8项契约，未改原产品和8工具。已通过的真实模型／音画／便携／跨机CPU结果与仍待的故障／正式入口／发行分别记录。[当前完整差距](UNFINISHED_DETAIL_20261106.md)。
