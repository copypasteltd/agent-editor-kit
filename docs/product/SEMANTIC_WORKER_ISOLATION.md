# 原生语义工作进程依赖隔离

## 已复现的 CLI55 安装问题

CLI55 源码的实际 CUDA 选材及两画幅完整工程重放已经通过。但源码工程显式迁移到字节相同的安装版后，实际选材返回 `SEMANTIC_RUNTIME_CHANGED`，没有产生成片。该失败保留在[安装版原始记录](../validation/evidence/process-budget-20261029-r1/installed-case-r1/verification.json)，不会改写为通过。

| 编号 | 依赖 | 注册／源码实际推理 | 安装版实际加载 |
| --- | --- | --- | --- |
| I01 | NumPy | 模型Python目录，2.4.6 | 应用安装site目录，2.4.2 |
| I02 | Pillow | 模型Python目录，12.3.0 | 应用安装site目录，12.1.0 |
| I03 | Torch／Transformers | 显式D盘模型环境 | 同一模型环境；未发生该项迁移 |

根因是 `semantic_worker.py` 启动时把应用的site目录放到整个模块搜索路径最前面。在源码目录运行时该目录没有NumPy／Pillow；安装包中则有控制器依赖，于是同一模型Python开始加载另一套依赖。运行时指纹检查正确拒绝了变化；显式迁移当前仅核对实现及已有运行时记录，不能预先消除此加载优先级差异。

[独立原生进程回归](../validation/evidence/process-budget-20261029-r1/installed-import-shadow-r1/verification.json)已重现同一机制：模型目录和应用目录各放置不同的NumPy标记，模型目录同时放置一个不得加载的同名应用包。真实worker必须加载自己的应用包，同时保留模型依赖的原生搜索顺序。CLI55在前者正确、后者失败；不是神经模型质量测试。

## 修复及验收路径

下一版将仅在引入自身应用包时临时置顶应用路径，随后恢复原生依赖搜索顺序；后续应用子模块通过已经固定的包路径加载。不能删除运行时指纹检查、手工改旧校准摘要或放宽依赖一致性要求。

待CLI55第二套原生环境实际案例终态后，才修改冻结的运行时代码并提升版本。随后执行原生引导回归、15项进程控制、45项选材／分镜和104项语义兼容；重新登记新版本的实现、索引和校准；生成新离线包，执行独立安装及完整GPU选材／音画重放。模型权重及固定查询／标签不因失败调参。

正式Skill仍CLI53／local51／r54。新版固定脚本已实测：即使给出 `--apply`，遇到失败的安装版实际案例也返回 `rejected`，命名空间、运行配置和92个注册文件均未改变：[拒绝切换收据](../validation/evidence/process-budget-20261029-r1/skill-pin-preflight-r2/verification.json)。成功固定、运行配置激活、C盘注册入口及正式工具包仍须独立验收。

此处是G26／G34的实际安装兼容缺口，不减少其原关闭条件，也不关闭自然语义质量或完整Agent任务成功率要求。

## CLI56 源码修复进展

CLI55第二套E盘原生环境实际案例已终态通过，完整音画与D盘案例一致；随后才修改运行时代码并提升到CLI56。工作进程先引入自己固定目录的应用包，恢复原始sys.path，再引入契约及模型依赖；还核对应用包实际文件路径，拒绝同名外部应用包。版本／模块路径／模型摘要核验全部保留。

| 编号 | 实际检查 | 结果与证据 |
| --- | --- | --- |
| F01 | 原生隔离子进程，应用与依赖同名碰撞 | [1项通过](../validation/evidence/semantic-worker-isolation-20261029-r1/bootstrap-r1/verification.json) |
| F02 | 命令预算／取消／自有子进程回收 | [15项通过](../validation/evidence/semantic-worker-isolation-20261029-r1/deadline-r1/verification.json) |
| F03 | 选材与可编辑广告分镜 | [45项通过](../validation/evidence/semantic-worker-isolation-20261029-r1/selection-r1/verification.json) |
| F04 | 检索／决策／任务／包／显式升级 | [104项通过](../validation/evidence/semantic-worker-isolation-20261029-r1/semantic-r1/verification.json) |

四组分别零失败／错误／跳过，281模块和各自测试文件前后冻结一致。新CLI56/local54完整离线包与新完整11素材注册／索引／校准任务正在运行。源码测试通过不代表安装版实际模型或最终注册Skill已验收；CLI55安装失败仍保持失败，不重写其包或校准摘要。
