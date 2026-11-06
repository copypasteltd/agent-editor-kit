# CLI66候选Skill生成输入与手册版本修正

2026-11-06，Asia/Taipei。以下是尚未应用／执行的r6候选代码及已更新手册，不是正式Skill升级。正式入口仍为CLI0.1.63／local61／r58；CLI65有独立候选真实CUDA音乐证据，CLI66尚待完整交付。

## 本批修正

| 编号 | 原问题 | 已写入的候选实现 | 验收边界 |
| --- | --- | --- | --- |
| S01 | stage从未纳入冻结的prepare_music65_skill.py提取REFERENCE，旧脚本变化可能改变待交付Skill正文 | 完整说明转入被冻结的delivery66.py常量；stage仅替换明确版本占位符，去掉旧脚本读取及ast依赖 | 尚未真实生成或校验新Skill；原脚本及历史证据保留 |
| S02 | 神经配乐说明链接指向可变main | 新候选正文链接固定v0.1.0-alpha.4，仍保留模型、原生运行库、真实音频及权利边界 | 标签与公开附件尚未创建，不把未来链接作为现有发行证明 |
| S03 | 原生Skill校验器是仓库外部输入，其字节未与交付代码绑定 | 固定当前官方quick_validate.py的SHA-256；冻结前、生成输出前、校验后检查，同一来源写入freeze及stage收据；后续交付同样核对 | 不改C盘校验器、解释器或策略；仅使用已有本地工具。来源变化时先拒绝 |
| S04 | 四份工具包手册首页仍把CLI59写成当前，早期三音色／无循环修复结论容易盖过后续实测 | 更新正式63／候选65／开发66，补齐103音色、解析配乐、循环修复、GPU及选型使用逻辑；原文完整折叠为历史 | 103音色WAV仍明确来自CLI61候选，不声称本轮重生成或全部人工听审 |
| S05 | 正式升级前冻结的手册保存原本机63状态，未来放入66包时可能与包内QUICKSTART混淆 | 打包时在四份入口手册最前加入实际清单CLI／release目标，说明下方本机记录属于其原日期；不把旧实测改标为66 | 现有原生打包契约新增四手册目标版本断言，方法总数仍43；尚未执行 |

当前官方校验器SHA-256：`6068513d924ed3559e186dfcdead7439129828dcf402167fd925c06dffbf2806`。这是本轮构建／校验工具依赖，不是用户运行应用时需要另装的模型。统一Skill继续维持一个公开入口、17内部模块；生成后的真实安装、命令和媒体门禁不因元信息校验通过而省略。

## 集中验证安排

原31项工具方法及断言调用均保留。前批11项新增契约之外，本批新增校验器改变时在stage创建任何输出前拒绝的契约，下一轮完整工具组现为43项，全部新增契约尚未执行。没有新增产品测试方法，没有筛选当前产品整套或修改原锁／Unicode／断网断言。

当前9文件候选语法及摘要一致；289应用模块叠加候选的297个文件无静态未绑定全局名称。4份手册当前段的51个本地链接可解析；4段PowerShell经原生语法解析0错误，命令没有执行。本批静态结果不增加功能通过数，不代替真实Skill、模型或安装验收。

原r5整套仍保持546产品／用例／依赖、7工具及95正式文件的冻结字节。收齐其完整终态与所有新发现后，再一次补齐、应用、冻结新批，并集中执行43项工具整套及未过滤产品整套。完整G01—G38继续开放。

证据：[修改前输入](../validation/evidence/delivery66-handoff-20261106-r1/r6-stage-inputs-draft-r1/before.json)、[首次静态复核](../validation/evidence/delivery66-handoff-20261106-r1/r6-stage-inputs-draft-r1/verification.json)、[最终代码静态复核](../validation/evidence/delivery66-handoff-20261106-r1/r6-stage-inputs-draft-r1/final-code-review/verification.json)、[手册历史保留](../validation/evidence/delivery66-handoff-20261106-r1/r6-stage-inputs-draft-r1/guide-updates.json)、[原生PowerShell语法](../validation/evidence/delivery66-handoff-20261106-r1/r6-stage-inputs-draft-r1/powershell-syntax.json)。

使用入口：[本机安装](COMMUNITY_LOCAL_DELIVERY.md)、[简体手册](COMMUNITY_MATERIALS.md)、[繁體手冊](COMMUNITY_MATERIALS.zh-TW.md)、[English manual](COMMUNITY_MATERIALS.en.md)。后续仍按[完整交付顺序](DELIVERY66_HANDOFF.md)执行。
