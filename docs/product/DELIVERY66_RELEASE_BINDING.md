# CLI66发布提交绑定候选

2026-11-06，Asia/Taipei。此页记录尚未应用、导入或执行的r6候选。正式Skill仍为CLI0.1.63／local61／r58，当前r5完整产品回归继续运行。本候选不是已发布功能。

## 具体问题

现有发布器把release-lock中的frozen_source与Git提交核对，546项包含产品、测试、工程schema及离线安装代码。7个交付控制工具单独冻结，正式Skill／注册清单及三语README也不在该546项中。因此，即使这些公开入口文件尚未提交，原提交门禁仍可能只根据产品文件通过。此为实际代码路径和冻结清单的静态检查结论，尚未执行失败复现。

原实现已经分别检查原始字节摘要及Git clean后的对象ID；无需删除换行规范化。新候选保留该机制，扩展提交覆盖范围。

## 下一批实现

| 编号 | 发布内容角色 | 绑定来源与规则 |
| --- | --- | --- |
| S01 | product | 原冻结产品／测试／依赖／schema清单，逐项保持原始SHA-256 |
| S02 | delivery_tools | 全部7个冻结交付控制工具；同时补入后半程source_unchanged检查 |
| S03 | skill | 实际交付描述中的唯一Skill全部公开文件，逐项与已验收候选一致 |
| S04 | registration | 实际交付描述中的agent-ffmpeg-local-install-manifest.json |
| S05 | documentation | README.md、README.zh-TW.md、README.en.md，发布资产生成时捕获实际字节 |

新release-lock格式为agent-editor-reviewed-release-v2，source_binding格式为agent-editor-release-source-v1。五类角色必须齐全、路径规范且不能大小写重叠；缺失文件、错误摘要及local/机器配置进入公开提交范围均拒绝。实际机器runtime.json仍由交付描述和正式文件保护记录核验，不进入公开源码角色。

发布前再次核对全部原始字节，再比较当前main提交中的Git clean对象。完整文件未提交、内容不匹配、旧锁格式或描述文件变化均拒绝。发布说明同步改为三语基础安装先行：--base-only无需模型，可选AI模型另配。

## 已写完整但未执行的检查

| 编号 | 新契约代码 | 目标失败情形 |
| --- | --- | --- |
| T01 | 角色完整性与机器配置排除 | 删除任意角色文件、旧绑定格式、私有配置、跨角色重复 |
| T02 | 冻结及正式字节漂移 | 产品、交付工具、Skill或注册清单在验收后改变；交付工具冻结缺失 |
| T03 | 原生Git换行规范化 | 真实本地提交把CRLF规范化为LF，原始字节仍匹配锁时应通过 |
| T04 | 未提交的公开入口修改 | 真实Git提交缺少新工具／Skill／注册及任一语言README内容，应拒绝 |
| T05 | 提交遗漏文件 | 真实提交遗漏已绑定Skill文件，即使本机文件仍在也应拒绝 |
| T06 | clean对象相同但原始字节改变 | CRLF改成LF后Git对象相同，但原始摘要变化，仍应拒绝 |

原31项交付契约的方法名和断言保持，唯一原方法的夹具格式更新为v2；新增6方法，下一轮工具整套计划37项，尚无这37项的执行结果。原31项通过只属于r5，不能外推到本候选。四项新Git契约只计划操作E盘自有临时仓库、commit-tree和本地比较，清除继承的GIT_*环境，不运行提交钩子或网络发布。

## 实际静态证据与后续顺序

6个候选代码文件已静态编译。全部289个应用模块名称绑定检查在当前源码发现已知AppError漏导入；覆盖候选后无未绑定名称，三个新增工具候选也未发现该类遗漏。静态检查不证明运行时分支、模型或真实发布通过。

保持r5的546产品／用例／依赖、7工具和95正式文件不变。等待原整轮终态，补齐所有新发现后统一应用、冻结新批，再集中执行完整37项工具契约及未筛选产品回归。之后完成独立安装、媒体／配方重放、真实模型故障、正式升级回滚和发布，不跳过原门禁；G01—G38继续开放。

[6文件原／候选摘要](../validation/candidates/delivery66-r6/implementation.json) · [原范围缺口](../validation/evidence/delivery66-handoff-20261106-r1/r6-source-binding-draft-r1/before.json) · [静态及冻结检查](../validation/evidence/delivery66-handoff-20261106-r1/r6-source-binding-draft-r1/verification.json) · [原3文件修正及实时问题](DELIVERY66_R6_CANDIDATE.md) · [当前未完成内容](UNFINISHED_20261106.md)。
