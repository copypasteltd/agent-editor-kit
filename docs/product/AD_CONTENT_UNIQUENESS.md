# 按素材内容去重选材（源码 CLI0.1.58）

## 行为与配置

同一文件以不同资产ID导入时，旧版只按ID去重，可能让多个镜头重复使用同一来源。源码58新增 `unique_content`：使用已登记的规范SHA256作为同源内容标识，并在全部镜头之间进行联合最大分配。

| 编号 | 请求 | 结果 |
| --- | --- | --- |
| U01 | 省略两个选项 | 默认按资产ID和精确内容去重 |
| U02 | `unique_assets: true, unique_content: false` | 显式保留旧版仅ID去重行为 |
| U03 | `unique_assets: false`，省略 `unique_content` | 允许复用，与显式关闭ID去重的意图一致 |
| U04 | `unique_assets: false, unique_content: true` | 仍禁止精确同源内容重复 |
| U05 | 非布尔值或内容摘要缺失／格式错误 | 拒绝，不退回ID冒充内容身份 |
| U06 | 已明确绑定的镜头 | 预留其内容摘要，其他镜头不能选其别名 |

```json
{"unique_assets": true, "unique_content": true}
```

将以上字段放在现有 `ad select` 请求顶层；原查询、brief、变体、版权及校准字段仍必需。来源窗口先检查全部变体长度和音频条件；只有满足条件的别名参与内容组，每个查询按分数、资产ID、来源时间确定最优别名，再对内容组做联合分配。输出记录 `uniqueness_group`、`unique_content` 和 `content_identity`，便于agent解释选择依据。

## 实际验证与边界

旧57实现已用同SHA不同ID回归重现重复选择，失败证据保留。源码58的57项选材／分镜回归通过，其中12项新增内容去重测试，包含100组随机别名图与独立穷举最优解比较、已绑定镜头、权利过滤和显式复用行为。

[源码57项收据](../validation/evidence/ad-content-uniqueness-20261029-r1/source58-selection-r1/verification.json) · [旧版问题重现](../validation/evidence/ad-content-uniqueness-20261029-r1/baseline-r1/verification.json)

这是精确文件字节身份，不是感知相似度、镜头语义去重、跨转码重复识别或完整广告质量验收。联合最优仅相对于服务实际返回并通过约束的有限候选集合。正式注册Skill仍CLI56；源码58尚未完成独立安装交付，勿向旧入口假定新默认行为。
