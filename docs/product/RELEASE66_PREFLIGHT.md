# CLI66公开发行预检（2026-11-06）

本次只读取GitHub官方API、远端标签及仓库已有流程状态。没有创建标签、分支或Release，没有上传附件，也没有触发远端工作流。本地程序仍CLI66开发版／正式CLI63，r4完整回归仍无终态；本次不新增功能测试或模型验收。

**后续身份复核已找到可用路径。** 本机原有GitHub CLI的两条原生凭据分别读取本仓库均返回HTTP200，官方仓库元数据返回admin／maintain／push权限及repo范围。此前403仅属于默认Git凭据助手选择的另一身份，不能再写成“没有可用发布身份”。本次仍只读；Release创建／上传尚未执行，不能把仓库权限读取当成发布成功。

| 编号 | 实际检查 | 结果及含义 |
| --- | --- | --- |
| P01 | 当前HTTPS凭据读取官方发行列表 | HTTP403，官方响应为“Sorry. Your account was suspended”。凭据来自本机Git凭据助手，值未写入文件或输出；结果只描述该凭据对应身份，不能推断SSH身份或整个组织状态 |
| P02 | 不带凭据读取同一仓库发行列表 | HTTP200，完整一页只有v0.1.0-alpha.3，发布于2026-10-24T12:52:48Z；没有重新下载或重验其二进制包 |
| P03 | SSH查询alpha.4远端标签 | 查询成功、没有匹配引用；不创建或覆盖标签 |
| P04 | 官方API读取仓库工作流 | first-release.yml及release-alpha3.yml均为active；已有流程固定旧标签和旧附件，不能直接当作CLI66流程使用 |
| P05 | 发布依赖复核 | 先完成源码／安装全套、实际CUDA、工程包、故障、唯一Skill切换／回滚及本地附件；之后再处理新版公开发布身份和匹配流程 |
| P06 | 两条已有原生GitHub CLI凭据读取本仓库 | 均HTTP200，返回仓库admin／maintain／push权限；只读取既有明确GitHub条目，凭据值仅在内存中使用，不输出、不保存、不修改凭据库 |
| P07 | 浏览器备选入口 | computer-use两次均报告原生连接不可用；没有读取网页、登录或打开新标签，不绕过到未授权的浏览器控制方式 |
| P08 | 隔离发布器修正草稿 | 显式环境令牌优先，其次已有原生gh默认凭据，最后Git凭据助手；增加六项契约方法，尚未应用或执行，待整批冻结后集中验证 |

当前冻结的CLI66直接API发布器仍优先使用此前被拒绝的默认Git凭据；新的原生gh读取路径只写入隔离候选，尚未切换运行中的冻结工具。仓库权限已确认，下一步是整批合入和验证该路径，再使用通过全部门禁的同源附件进行真实发行。旧工作流不需要为此触发，也不覆盖既有标签／附件。

后续可继续进行本地开发、集中回归、独立安装和附件准备；当前外部问题不构成整个产品任务停滞。新发行仍须保持旧标签／附件不变，且不得包含未经确认的模型生成音频。

[第一次实际403及SSH查询](../validation/evidence/delivery66-handoff-20261106-r1/release-preflight-r1/verification.json) · [认证／匿名对照](../validation/evidence/delivery66-handoff-20261106-r1/release-preflight-r2/verification.json) · [现有工作流状态](../validation/evidence/delivery66-handoff-20261106-r1/actions-preflight-r1/verification.json) · [全部剩余内容](UNFINISHED_20261106.md)。

[原生gh身份实际200记录](../validation/evidence/delivery66-handoff-20261106-r1/release-identity-r1/verification.json) · [隔离候选范围](DELIVERY66_R5_CANDIDATE.md)。
