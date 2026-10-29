# 校准语义选材 → 可编辑广告分镜

完整CLI54候选已独立离线安装，281模块／8原生资源字节一致，45项安装专项通过；[安装恢复](../validation/CLI54安装恢复_2026-10-29.md)。唯一已注册Skill仍为CLI53／r54，实际CUDA闭环另验。

源码 CLI **0.1.54** 新增 `ad select`。当前已安装的 CLI53／r54 Skill 保持原版本；新版离线安装、统一 Skill 同步及广泛回归另行验收，不能向 CLI53 入口发送此命令。该功能推进 G26／G27／G35，原38项关闭条件继续保留。

## 工作流程

1. 导入本地图片／视频、字体、配乐，逐项登记来源与权利。
2. 明确登记已有的原生图文模型，以实际 CUDA 或 CPU 建立索引；为实际设备、索引及素材类型建立独立校准档案。
3. 提供产品、受众、已确认文案、镜头查询和各画幅／时长。查询镜头不再要求调用者预先知道素材 ID。
4. `ad select --dry-run` 核验输入和索引／档案绑定，不执行模型、不生成选中计划。
5. 实际 `ad select` 将整批镜头查询送入已有本地语义服务，按候选范围、源音和权利条件过滤，再联合分配素材，输出普通 `ad build` 可读计划。
6. `ad build` 验证计划、实际文件摘要、字体排版和当前工程后原子提交。继续预览、渲染、局部返工及工程包导出／导入重放。

```powershell
# 以下命令要求源码 CLI54／后续匹配安装，不适用于现有 CLI53 Skill。
function Invoke-AekSource {
  & 'C:/Python313/python.exe' -E -B -u -X utf8 -c "import sys;sys.path.insert(0,r'E:/dev/sandbox/AI广告剪辑/product/src');from ai_ad_editor.cli import main;raise SystemExit(main())" @args
}
Invoke-AekSource version
Invoke-AekSource ad select --project E:/video-work/demo `
  --input E:/video-work/demo/selection.json `
  --output E:/video-work/demo/validation/selected.json `
  --index-id visual-v1 --calibration-id accepted-cuda `
  --kind image --device cuda --dry-run

# 检查 dry-run 后，去掉 --dry-run 实际选材。
Invoke-AekSource ad build --project E:/video-work/demo `
  --input E:/video-work/demo/validation/selected.json
```

这是本机已有Python及其依赖的显式源码入口，不创建虚拟环境或安装全局命令。新机器仍须按交付契约准备依赖；已有本地 Skill 继续固定到已验收安装包。实际选材后再执行 build，dry-run 本身不产生计划。

## 输入示例

```json
{
  "unique_assets": true,
  "queries": [
    {"id": "hook", "text": "俯拍咖啡杯与杯碟"},
    {"id": "detail", "text": "一只猫", "include": ["一只猫"], "exclude": ["一杯咖啡"]}
  ],
  "brief": {
    "id": "demo",
    "product": "已确认的产品",
    "audience": "已确认的目标受众",
    "cta": "查看完整内容",
    "caption_style": {"font_asset_id": "font"},
    "shots": [
      {"id": "hook", "text": "已审核的开场文案", "weight": 1},
      {"id": "detail", "text": "已审核的后续文案", "weight": 1}
    ],
    "variants": [
      {"id": "wide", "canvas": {"width": 1280, "height": 720}, "duration_seconds": 6},
      {"id": "vertical", "canvas": {"width": 720, "height": 1280}, "duration_seconds": 9}
    ]
  }
}
```

`font`、固定镜头及可选配音／配乐的 ID 必须已经导入。完整文案、轨道及局部返工格式沿用[广告分镜契约](AD_STORYBOARD.md)。查询仅接受已有 `id/text/include/exclude` 条件语法，不把人工标签或预期素材 ID 发给模型。

## 选择规则与失败行为

| 编号 | 规则 | 具体行为 |
|---|---|---|
| S01 | 1–50个查询镜头 | 查询 ID 唯一且对应真实镜头；每项至少用于一个变体 |
| S02 | 单批实际检索 | 复用已有语义服务批量推理；`--device cuda` 要求实际设备与校准绑定一致 |
| S03 | 校准接受 | 需要 `calibrated_match`；无档案、无合格候选、设备不匹配不能静默提升为匹配 |
| S04 | 摘要及来源 | 候选资产存在且种类为图片／视频，来源 SHA 与当前登记一致；保留实际点采样起点 |
| S05 | 完整来源窗口 | 按所有变体的实际有理帧率计算最大镜头长度，拒绝从采样起点起长度不足的视频；不静默回移、循环或变速 |
| S06 | 明确源音 | 任一变体需要原音时，候选必须具有已探测音轨 |
| S07 | 权利状态 | 自动选择仅接受当前检索返回的 `verified` 状态；不等于已验证所有商业用途／肖像／商标／发布限制 |
| S08 | 联合分配 | 默认资产ID不重复（不保证不同ID的内容不重复），固定镜头占用的资产ID也保留；采用整数代价的矩形 Hungarian 分配，最大化1e-8量化的相似度总和 |
| S09 | 明确允许复用 | `unique_assets=false` 才允许查询镜头重复使用素材；同分按资产 ID 稳定选择 |
| S10 | 多采样候选 | 同资产有多个合格采样点时，选最高分且长度足够的采样点；同分选择更早起点 |
| S11 | 请求不冲突 | 查询镜头不能同时提供 `asset_id/source_in_tick`，相应变体也不能覆盖这两个字段 |
| S12 | 可迁移依据 | 原查询、档案／索引、素材 SHA、起点、分数、最大镜头时长与原调用者依据保留在镜头 rationale；计划摘要覆盖这些信息 |
| S13 | 工程保持 | 选材只写新计划和受管推理证据，不修改 `project.json`；提交沿用原子事务、快照、实际素材和字体检查 |
| S14 | 超时与取消 | 沿用实际受管语义进程、操作预算及分配循环检查；保留失败证据，不发布部分分镜 |

`--limit` 为每查询1–20个候选；全局最优只针对这批**返回且通过过滤的候选**，不是对完整视频或未返回素材的最优保证。增加候选范围需要再次显式运行，不会自动降低校准阈值。

## 输出与展示

保存的 JSON 是原广告计划，可直接交给 `ad build`。CLI 响应额外包含逐镜头选择、被过滤候选及原因、原始检索预览／分数／推理设备和受管工作目录。Agent 应展示原查询、实际预览和最终成片，供客户检查整段动作、人物、叙事和文案关联。

图片相似度和经验校准不能证明完整镜头语义、动作、身份、商品效果或自然广告质量。此功能没有自动生成商品承诺，也没有证明独立 Agent 从自由 brief 自主完成广告的成功率。自然动作／长片、人物与品牌约束、听审及完整 G27／G35 验收继续开放。

## 验证状态

最终冻结源码已分别通过45项选材／分镜测试和104项语义检索／决策／任务／工程包／升级兼容测试。新控制器包含独立穷举参考的100组候选图、冲突重分配、无解拒绝、完整来源窗口、源音、摘要、权利、原查询绑定及 CLI 计划→实际提交检查。最终源码分组、实际CUDA索引／校准／选材／渲染和包重放的终态以 [原始证据](../validation/evidence/ad-selection-20261029-r1) 为准；正在运行的任务不视为已通过。

繁體：本功能以實際校準語義檢索聯合選材，產生可編輯分鏡；目前為CLI54原始碼擴展，既有CLI53 Skill維持原版。English: Source CLI54 joins calibrated visual retrieval to editable storyboards with global candidate assignment and portable selection receipts. It does not establish whole-shot semantics or autonomous advertising quality.

## 2026-10-29 原生校准与候选 Skill

完整11来源／10内容去重图像的CUDA索引与校准已成功。校准20条正例全部正确接受，20条负例仍有1条误接受；5%为本次经验拟合，不是无误选保证，真实选材与成片闭环另验。原先缺brick／horse的失败设置未删除。

[统一Skill候选](../validation/evidence/ad-selection-20261029-r1/skill-candidate-r1/verification.json)在E盘保持1入口／17模块／93文件，增加内部选材说明；格式检查、实际安装版version／capabilities通过，没有在这些检查中执行新GPU推理。正式注册仍为CLI53／r54。安装版真实选材／成片验收通过后再激活。
