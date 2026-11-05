# CLI66交付后半程与原生完整回归

2026-11-06，Asia/Taipei。正式入口仍CLI0.1.63／local61／r58。本批完成代码后再集中核验；代码存在不代表新安装、真实配乐故障、正式切换或公开发行已经通过。

原配置完整的4,110项源码r2回归已中断：工具会话75402不可用，原主进程22948及对应运行命令已确认不存在，原日志没有终态总结。中断原因和退出码未知，不按通过或完整失败计数，没有根据历史父子PID清理其他程序。[原始中断收据](../validation/evidence/delivery66-20261106-r1/source-all-r2/verification.json)保留日志摘要、原冻结及观察状态。

| 编号 | 本批完整代码 | 核验边界 |
| --- | --- | --- |
| H01 | 原生后台监督：启动／状态查询、进程创建时间及映像身份、子命令日志、实际退出码与结果摘要 | 明确脱离终端作业；主机拒绝时记录失败，不静默退回原会话；存活判断查询实际进程，不能只看文件或PID |
| H02 | 配乐输出冲突和其他文件错误转为结构化CLI错误；次级报告删除错误不掩盖原错误 | 新增4项真实CLI／事务边界用例，工作进程明确模拟，不冒充神经推理 |
| H03 | 复用现有单Skill打包器，增加三语快速开始与交付说明；完整ZIP路径／类型／预算／CRC／摘要预检 | 保持一个公开Skill与17内部模块；独立安装与注册另验，构建不等于验收 |
| H04 | 新路径独立解包、应用自带安装器、隔离注册、实际PowerShell入口、整段RGBA／PCM及母音频／配方重放 | 使用同一主机既有依赖；不算第二台或干净主机 |
| H05 | 真实配乐取消、超时、提交冲突三类故障工具 | 使用实际安装版与原生模型，不修改产品函数；取消等到真实扩散回调，冲突需完整四组件CUDA与独立PCM；尚待实际运行 |
| H06 | 五类原门禁＋便携包＋实际故障后，正式升级→显式回滚→再次升级→实际发现入口重放 | 失败尝试回滚，保留备份；不能以版本查询代替实际媒体验收 |
| H07 | 生成应用ZIP、唯一Skill ZIP、三语快速开始、发布说明与SHA256清单；匹配源提交后新建alpha.4 | 公开下载不含未审核模型音频；不覆盖既有标签或附件，缺发布凭据时保留本地可审阅成果 |

本批后续证据放在`docs/validation/evidence/delivery66-handoff-20261106-r1/`；新临时、安装和模型任务输出放在E盘`local/agent-ffmpeg/delivery66-handoff/`。全程原生Windows，不运行Docker、WSL、虚拟环境或浏览器。

首组17项契约为历史结果。修复失效Git路径并补入第18项用例后，r4冻结版本的完整18项契约实际通过，零失败／错误／跳过；产品与正式文件不变。这是模拟／文件安全／原生Git检查，不包含模型推理、注册或正式激活。原生监督随后启动未过滤源码全套，实际发现4,114项，独立工具调用确认监督与子进程身份存活；目前没有终态，不能计为通过。[18项结果](../validation/evidence/delivery66-handoff-20261106-r1/contracts-r2/verification.json) · [不可变观察记录](../validation/evidence/status-review-20261106-r1/review-r2/verification.json)。r3仅为此前快照，没有启动产品全套。

最新只读检查点：r4原生监督与子进程仍实际存活，日志已有配乐进度大小／异常字段两项用例ERROR，尚无最终统计或异常根因。保持冻结字节，待整轮汇总后一次修正全部问题再集中核验；不把运行中当通过。[观察记录](../validation/evidence/delivery66-handoff-20261106-r1/remaining-r3/observation.json)。

## 集中执行顺序

先完成并冻结全部本批实现及必要用例，再执行整轮回归。每次使用新的run编号，不覆盖旧证据。下面列出计划编号；对应前置收据不存在或不通过时，后续命令拒绝执行。

```powershell
$python = 'C:/Python313/python.exe'
& $python -E -B -u -X utf8 docs/validation/delivery66.py freeze --run r4
& $python -E -B -u -X utf8 docs/validation/test_delivery66_handoff.py
& $python -E -B -u -X utf8 docs/validation/run_delivery66_native.py start --run r4 --freeze-run r4
& $python -E -B -u -X utf8 docs/validation/run_delivery66_native.py status --run r4 --freeze-run r4
```

源码全套真正通过后，使用原工具`delivery66.py build`离线构建安装；再以同一监督工具的`--installed`执行安装版全套。传入明确的`--freeze-run r4 --tests-run r4`，应用字节必须与冻结相符。随后依次执行原工具的`stage`、`music`、`package`、`descriptor`；实际音乐使用新的66输出，不复用65成功来代替。

```powershell
& $python -E -B -u -X utf8 docs/validation/delivery66_handoff.py kit --run r1
& $python -E -B -u -X utf8 docs/validation/delivery66_handoff.py verify-kit --run r1
& $python -E -B -u -X utf8 docs/validation/delivery66_music_faults.py --run r1
& $python -E -B -u -X utf8 docs/validation/delivery66_handoff.py activate --run r1
& $python -E -B -u -X utf8 docs/validation/delivery66_handoff.py assets --run r1
```

后半程默认引用r4冻结／r4源码和安装回归，其他候选、Skill、音乐、工程包及描述默认为r1；若实际执行采用别的编号，须通过对应`--*-run`显式选择。`kit`仅构建；`verify-kit`才实际独立安装和播放数据重放。`activate`要求便携包和三类真实故障全部通过，且不会省略原源码／安装／工程／Skill／真实CUDA音乐五类门禁。

`assets`只准备可审阅本地发布附件。发布前先提交并普通推送对应源码与三语README，用完整提交ID调用`publish_delivery66.py --assets PATH --source-commit COMMIT --run r1`做校验；另加`--publish`才创建新标签／草稿、上传匹配附件并发布。授权凭据仅留在内存，拒绝认证重定向，不写入日志；任何既有不同标签、附件或发行记录均保留。

## 能力与原范围

神经配乐命令`music generate`仍须登记显式本地适配器，输出仍为内部未核验，完整听审、自然质量、权利、性能、长曲及更多曲风分别验收。应用ZIP不包含Python、FFmpeg、驱动、全部模型或完整音乐运行库。当前工具不使原G01—G38自动关闭，也不把同机隔离路径等同跨机器。

本批状态见README顶部与新增编号记录；早期r2“运行中”为历史阶段，以上中断记录替代其当前状态。[完整未完成清单](UNFINISHED_20261106.md) · [原目标](GOAL_GAPS_20261025.md)。
