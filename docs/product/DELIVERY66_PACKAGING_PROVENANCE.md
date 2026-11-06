# CLI66工具包构建输入与原生子进程候选

**执行更新：9文件整批已应用并冻结r6，43项工具整套实际通过；新的4,124项未过滤产品整套运行中。正式Skill仍CLI0.1.63。** [实际终态、来源冻结及后续顺序](DELIVERY66_R6_EXECUTION.md)。下文完整保留执行前的准备／静态快照，其中“未执行／候选”按当时阶段理解，不覆盖本次真实结果。

2026-11-06，Asia/Taipei。当前r5完整回归继续，下一批r6候选共9个代码文件，尚未应用、导入或执行。正式唯一Skill仍CLI0.1.63／local61／r58。本文的代码完成和静态检查不表示新工具包、模型或发行通过。

## 构建输入缺口与完整修正

原单Skill打包器从仓库读取注册脚本、安装助手、LICENSE及62份产品手册；后半程另加入DELIVERY_CONTROLLER.md。共69项构建来源中，原r5仅activate_community_runtime.py已在7工具冻结内，其余68项未纳入构建输入冻结。此为代码和清单的静态发现。

| 编号 | 已写完整代码 | 待执行的证明 |
| --- | --- | --- |
| P01 | 打包器集中声明原有助手／手册路径，提供source_names／source_inventory；保留原62份手册和输入路径 | 实际原生打包，清单来源与每项真实字节一致 |
| P02 | 下一批freeze另记录全部69项packaging_source_files；交付工具扩为8项，包含打包器 | 新冻结、工具整套和产品源码／安装整套；当前r5仍为546／7／95原字节 |
| P03 | 打包前、写出前及写出后复核来源；基础ZIP、最终ZIP、便携安装验收、正式切换、发行锁传递同一来源记录 | 缺失、变化和版本不一致时拒绝；失败现场保留 |
| P04 | 发布源码绑定扩为六角色：product、delivery_tools、packaging、skill、registration、documentation | 69来源中的2项已归8工具，其余67项进入packaging角色，拒绝遗漏或冲突；机器配置仍排除 |
| P05 | --source-ref接受main、完整40位提交或发行标签；本次交付显式使用v0.1.0-alpha.4 | 新转换的外部文档链接指向固定标签，随公开发行的同一提交生效；旧标签及附件不修改 |

release-lock仍为agent-editor-reviewed-release-v2，source_binding升级为agent-editor-release-source-v2。源码提交比较保留原始SHA-256与Git clean对象双重检查。69来源记录不会把同一工具重复计算为两个独立发布文件。

本批再增加5项工具契约：原生打包来源及标签、非法引用在输出前拒绝、缺失／读取中变化来源在写出前拒绝、构建门禁在创建目录前拒绝、未提交的注册助手／LICENSE／手册拒绝。原31方法与断言保留；加前批6项及后续校验器1项后下一轮计划43项，全部候选新增检查尚未执行。

## r5新增断网用例失败

r5在tests_started=2362时记录test_python_network_guard_blocks_connection_before_network_io失败，堆栈直接显示子进程No module named ai_ad_editor。它没有执行到真实网络拦截断言，不能作为网络保护本身失效的证明。

新增第9个候选文件product/tests/test_local_tts.py复用显式被测包子进程辅助器。原socket.create_connection脚本和全部断言保留，仍须实际得到TTS_NETWORK_DISABLED及socket.getaddrinfo记录；不替换网络保护实现，不执行模型，也不回落源码。15个原TTS方法和断言均静态保留，新增产品用例0项。

已按AST检查产品用例中19处直接sys.executable子进程调用；需要修正的4处是原3处CLI入口／锁调用及此次TTS调用。其他调用使用显式包路径、独立worker／runpy路径，或仅运行标准库进程夹具；故意加载foreign包的导入隔离测试保持原对抗行为。此为静态范围检查，不是19项额外通过。

## 当前证据与后续

9候选文件语法通过；覆盖候选的289应用模块及候选工具／用例无静态未绑定名称。原r5的546产品／用例／依赖、7工具、95正式文件仍一致。实时问题检查点为4失败事件／1错误事件，原整套尚无终态；它不是最终失败统计。

继续原整轮，收齐全部问题后一次补全、应用并冻结新批，集中执行43项工具整套及未过滤源码／安装整套，再推进真实CUDA音乐、故障、媒体包、正式切换／回滚及新发行。完整G01—G38不变。

[9文件摘要](../validation/candidates/delivery66-r6/implementation.json) · [原69来源及68未冻结项](../validation/evidence/delivery66-handoff-20261106-r1/r6-packaging-inputs-draft-r1/before.json) · [19处子进程AST记录](../validation/evidence/delivery66-handoff-20261106-r1/r6-packaging-inputs-draft-r1/child-launch-audit.json) · [5问题事件快照](../validation/evidence/delivery66-handoff-20261106-r1/r6-packaging-inputs-draft-r1/observed-issues.json) · [静态及原冻结收据](../validation/evidence/delivery66-handoff-20261106-r1/r6-packaging-inputs-draft-r1/verification.json) · [提交绑定说明](DELIVERY66_RELEASE_BINDING.md)。

后续[Skill生成输入修正](DELIVERY66_STAGE_INPUTS.md)保持69项构建来源和62份手册清单，更新其中4份手册当前段并完整保留历史。
