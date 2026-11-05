# CLI66整批交付修正与集中回归

2026-11-06，Asia/Taipei。前一检查点为`256f54f`。本轮先完成所有已识别的交付修正代码、必要用例和执行工具，再一次合入，冻结r2后集中执行全套。原G01—G38范围保持，不据此宣布完整剪映等价。

| 编号 | 本轮代码 | 当前验收状态 |
| --- | --- | --- |
| C01 | 工程包工具改用实际支持的`package`；重放输入改为新版真实生成结果 | 代码已合入，待实际安装版导出／导入及完整RGBA／PCM重放 |
| C02 | `delivery`进入Agent能力清单，列出参数、限制、五类门禁和不支持范围 | 已合入；实际安装版／Skill查询待验收 |
| C03 | v2交付描述要求源码、安装、工程包、Skill和实际CUDA配乐五类独立证据；绑定应用／Skill／WAV／请求／工程摘要及四组件前向设备 | 真实66神经生成尚未执行；历史65成功不能替代 |
| C04 | 有界读取、字段类型、重复键、非有限数、Windows别名、完整备份预检、恢复dry-run及中断后用户修改保护；原生锁和耐久备份保留 | 整批回归中；未在正式入口切换 |
| C05 | 显式原生Rubber Band／Node／HTML依赖预检；15个测试文件的子进程与资源绑定所选应用包，保留原测试名称、断言和20秒门槛 | 原生版本预检已实际完成；4,110项完整源码回归运行中，无终态 |

## 使用及后续顺序

正式用户仍调用`$agent-ffmpeg-local-editor`，当前为CLI63／local61／r58。`delivery`为66开发能力，不能把下面候选命令套在正式63入口。

整轮工具顺序为：冻结→源码全套→离线构建安装→安装版全套→候选Skill→实际CUDA配乐→新音频工程包重放→生成并检查交付描述→正式切换／恢复／回滚验证。模型、运行库、输出权利、自然听审和干净主机另按原条件验收。

```powershell
C:/Python313/python.exe -E -B -u -X utf8 docs/validation/delivery66.py tests --run r2 --freeze-run r2
```

后续动作使用新的独立run编号，并指向同一冻结实现；不得覆盖旧收据，不得跳过尚未通过的前置门禁。运行中的`tests.stderr`不是完整通过证明。

## 初轮中断与原始记录

初轮4,101项发现八处明确的Rubber Band配置跳过。因为零跳过验收已无法满足，在完整修正候选写完后主动中断，保留原日志；不是观察超时，也不是完整失败／通过总数。新全套增加九个交付测试方法，发现4,110项。

首次终止命令的进程树枚举包含复用编号，返回128；原始输出保留。工具会话已返回终态，测试主进程确认退出。未把数字父子关系当作当前所有权，未声称所有历史子进程清理已获证明；后续终止脚本改为仅操作已验证的主进程句柄。

- [完整修正候选](../validation/candidates/delivery66-r3/implementation.json)
- [一次合入记录](../validation/evidence/delivery66-20261106-r1/correction-apply-r2/verification.json)
- [新冻结清单](../validation/evidence/delivery66-20261106-r1/freeze-r2/verification.json)
- [初轮中断及八处跳过](../validation/evidence/delivery66-20261106-r1/source-all-r1/verification.json)
- [实际原生依赖预检](../validation/evidence/delivery66-20261106-r1/source-all-r2/native-dependencies.json)
- [交付控制器候选使用](DELIVERY_CONTROLLER.md)
- [全部剩余范围](UNFINISHED_20261106.md)

源码仍CLI0.1.66／289应用模块。local64仅是待构建的新候选版本号；现有CLI65候选与正式CLI63均不因此升级。当前没有新的模型推理、自然听审或公开Release验收。
