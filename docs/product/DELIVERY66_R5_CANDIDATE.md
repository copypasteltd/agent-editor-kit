# CLI66完整修正批次与集中核验

2026-11-06，Asia/Taipei。原r4已完成4,114项：10失败、15错误、0跳过，完整结果及25条堆栈均保留。全部修正代码一次写齐后，20个目标文件已备份、预检并写入；r5冻结546个产品／用例／依赖文件、7个工具和95个正式文件。正式入口仍CLI0.1.63／local61／r58。

当前仓库检查点提供files/下完整候选副本和证据，本地20个目标文件已应用；应用源码提交待完整产品回归通过。

当前31项完整交付工具契约已实际通过，零失败／错误／跳过。两组真实隔离导入均通过；未过滤产品全套r5实际发现4,124项，仍在运行，没有通过终态。下表“代码已完成”不等于新版安装、模型推理或正式交付已经通过。

| 编号 | 已完成代码 | 当前验证及保留边界 |
| --- | --- | --- |
| U01 | 两个诊断夹具改用真实Session.prepare建立受控Directory | 原r4堆栈已证实Path.read错误；保留原用例及拒绝断言，产品r5待终态 |
| U02 | 三个目录精确预期更新为既有0.11.0／51 | 原r4三项失败均已确认；数值通道、布尔限制、像素参考和误差阈值不变 |
| U03 | 音乐phase先验字符串再查白名单，非对象JSON明确无效 | 新产品方法5项进入完整r5，不冒充模型推理 |
| U04 | 音乐仅转发phase／done／total／worker_pid四个核准字段 | 不接受伪造state、私有路径和未知字段 |
| U05 | 未准备、非普通文件、有界读取失败保留明确诊断状态 | 原受控Directory读取及重解析保护不放宽，不替代原业务错误 |
| U06 | 5项真实文件音乐进度方法覆盖注入、畸形、非对象、损坏和不可用 | 计入4,124产品发现数；未拿静态编译当作功能通过 |
| U07 | 显式令牌→已有原生gh默认凭据→Git助手的发布身份顺序 | 已有真实只读仓库权限证据；31项契约验证选择，不等于公开附件上传 |
| U08 | 6项发布契约覆盖优先级、回落、UTF8／UTF16、超限秘密及只校验模式 | 已在完整31项交付组通过；不读取或输出真实秘密，不创建发行 |
| U09 | 三语快速开始覆盖摘要、离线安装、基础配置、可选模型／CUDA、单Skill、选型、音轨、渲染和工程包 | 当前30段PowerShell原生语法0错误；摘要仍占位，命令流程尚待新包独立验收 |
| U10 | 整轮前实际导入NumPy／Pillow／OpenCV／jsonschema，锁定应用、解释器、版本及原生字节 | 应用profile已实际通过；依赖版本与安装包内固定版本分别记录 |
| U11 | 错误／失败／子测试即时完整堆栈刷盘，后续用例继续执行 | 真实文件契约通过；保留原unittest全部断言、最终统计及退出码 |
| U12 | 3项依赖／日志契约覆盖缺库、错版本、错应用／解释器／隔离及即时子测试 | 已在31项交付组通过；内层故意失败的5个用例不算产品通过数 |
| U13 | 转场／社区音频／视频生成／粒子4模块在计算位置加载NumPy／Pillow | 剔除导入后的数值／校验AST一致；实际算法和CLI由整套回归验证 |
| U14 | 新增2项实际原生CLI方法，显式禁NumPy／Pillow／Torch时执行版本、能力及3类帮助 | 原蒙版／修复3项失败用例保留；新增2项计入产品全套，尚无整轮终态 |
| U15 | 音频增强进度同类有界处理，保留segment时钟及字段白名单；新增3项真实文件方法 | 为静态同类修正，不声称原r4已有对应进度缺陷 |
| U16 | 递归锁定模块PYD／DLL及NumPy／Pillow随附库 | 实际依赖profile各36文件，合并外部工具后43文件；测试结束须仍一致 |
| U17 | 应用与不注入应用目录的bare-worker分别实际隔离导入并拒绝公共文件变更 | 两profile已通过，防止控制器可导入而隔离worker缺库 |
| U18 | 最终r4动态堆栈发现的光学／辉光／颜色信号／曲线4模块延后加载 | 保留数值AST和float_curves.np检查接口；扩展静态图145模块／49函数作用域，0提前重依赖路径；实际仍待全套 |
| U19 | --base-only基础配置不需模型包；备份旧配置、清除外机模型路径、拒绝矛盾参数 | 4项新增真实文件／CLI交付契约全部通过；既有--packs仍强制安装版验包 |
| U20 | 便携验收调用真实基础配置器后再注册／音画重放；错误日志附有界AppError代码／cause／hint | 日志契约通过；新包尚未构建，独立便携验收、真实模型及正式注册仍待执行 |

20个文件为10个产品模块、5个原产品测试文件、5个交付／配置工具。新增产品方法10项，新增交付方法13项，交付完整组31项；两组不合并为通过数。完整逐文件原／候选摘要见[实现清单](../validation/candidates/delivery66-r5/implementation.json)，完整备份保存在E盘local/agent-ffmpeg/delivery66-correction-apply-r1/backups。

第一次交付组启动未发现任何用例：既有嵌入式原生Python不自动把脚本目录加入sys.path，导致找不到同目录交付工具。未修改解释器、._pth或产品代码；显式加入交付工具目录后重跑完整31项通过。该启动失败保留为contracts-r3，不计产品回归失败或通过。

[20文件实际写入](../validation/evidence/delivery66-handoff-20261106-r1/correction-application-r1/verification.json) · [r5完整冻结](../validation/evidence/delivery66-20261106-r1/freeze-r5/verification.json) · [31项完整交付结果](../validation/evidence/delivery66-handoff-20261106-r1/contracts-r4/verification.json) · [31项原日志](../validation/evidence/delivery66-handoff-20261106-r1/contracts-r4/tests.stderr) · [实际依赖和运行观察](../validation/evidence/delivery66-handoff-20261106-r1/correction-batch-review-r1/verification.json) · [30段原生语法检查](../validation/evidence/delivery66-handoff-20261106-r1/quickstart-syntax-r2/verification.json)。

[简体流程草稿](../validation/candidates/delivery66-r5/quickstart-drafts/QUICKSTART.md) · [繁體流程草稿](../validation/candidates/delivery66-r5/quickstart-drafts/QUICKSTART.zh-TW.md) · [English workflow draft](../validation/candidates/delivery66-r5/quickstart-drafts/QUICKSTART.en.md)。草稿明确保留BUILD_MANIFEST_REQUIRED，不可当作已发行包摘要。

下一步须等完整产品终态，再构建离线候选、安装版完整回归、新版CUDA配乐、配方／整段RGBA与PCM重放、真实取消／超时／提交冲突、唯一Skill正式升级／显式回滚／重激活，以及匹配源提交的新发行。G01—G38关闭条件继续保留。

此前7／8／9／15文件是历史静态快照，分别保留在correction-draft-r2、correction-draft-r3、dependency-preflight-draft-r1及lazy-startup-draft-r1；其中130模块图遗漏模块初始化函数，不能替代本轮最终堆栈或实际测试。[原r4完整结果](DELIVERY66_R4_RESULTS.md) · [完整未完成内容](UNFINISHED_20261106.md) · [集中执行顺序](DELIVERY66_HANDOFF.md)。
