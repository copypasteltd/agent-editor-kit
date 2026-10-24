# Offline visual semantic retrieval / 离线图文语义检索

This guide describes local CLI 0.1.5 / `v0.1.0-alpha.4-local.3`, installed on the
native Windows host. The single `$agent-ffmpeg-local-editor` entry shares this
runtime; the public alpha.3 / CLI 0.1.2 package retains its original scope.

关联：[完整目标 G26/G27/G32](GOAL_GAPS_20261025.md) ·
[检索契约](../specs/离线语义素材检索契约_v0.1_2026-10-25.md) ·
[统一 Skill](SKILLS.md)。全部 G01–G38 继续保留。

## 能做什么

Agent 可以对明确选中的本地图片和视频采样帧建立真正的图文模型向量索引，
使用中文、英文或本地参考图找候选。结果包含原始查询、cosine 分数、源资产 ID、
源摘要、实际采样时间、预览资产、权利状态和可编辑时间线引用。

当前实现使用已有的 `google/siglip2-base-patch16-224` 本地 safetensors，768 维。
索引使用图片内容，不把文件名、标签或人工答案送进模型。相同预览字节只编码一次，
再映射回各源记录。每次 worker 内复用同一个模型完成整批输入。

这是采样画面相似检索。分数不是概率；一个采样点不能证明整段动作、人物身份、
完整事件边界或素材使用权。Agent 应展示候选预览，再确定素材和剪辑范围。

## 已有原生依赖与模型登记

基础应用包不包含 Torch、Transformers 或 1.5GB 模型权重。需明确提供已存在的
原生 Windows Python、兼容的 Torch/Transformers/NumPy/Pillow/tokenizers/safetensors，
以及完整本地模型目录。产品命令不下载依赖、模型或远程代码。

本轮使用原生 CPython 3.13.14、Torch 2.13.0+cu130、Transformers 5.14.1，
RTX 3060 12GB。该 Python 来自本机已有的嵌入式分发；推理是独立进程，未启动
ComfyUI 服务或虚拟化环境。CPU 使用 float32；支持 BF16 的 CUDA 使用 BF16。
其他依赖组合和设备需要单独验证。

当前工作区 `local/agent-ffmpeg/runtime.json` 的 `semantic_config` 指向
`local/agent-ffmpeg/semantic-runtime.json`：记录已有 Python、模型、来源/许可证据
及已验登记响应摘要。Agent 读取它，再对每个工程明确登记；此配置不会自动下载或
调用模型。开发验证的 NumPy/Pillow 为 2.4.6/12.3.0；安装版独立路径固定为
2.4.2/12.1.0，两套实际路径与版本分别保留在原始响应中。

下面 `$avk` 应指向包含本功能且经过验收的安装版 Skill 启动器；`$project`、
`$nativePython`、`$model`、`$licenseEvidence` 均是调用方明确提供的本地路径。

```powershell
& $avk semantic adapter-register --project $project --adapter-id siglip2 `
  --python-executable $nativePython --model-path $model `
  --creator Google --license-spdx Apache-2.0 --evidence $licenseEvidence `
  --verification-status verified
& $avk semantic adapter-inspect --project $project --adapter-id siglip2
```

`verified` 是调用方对现有证据的声明，应有真实来源支持。登记会检查本地格式、
配置、实现和选定原生运行库，并固定字节/摘要、模块位置和版本；登记不进行模型
前向。后续字节或位置改变会拒绝旧登记。更换模型、环境或软件实现时需重新登记
并重建索引；当前不支持直接搬移这些绝对运行时路径。

完整性核验会读取大型模型和原生库，已知存在明显启动成本。固定的是选定组件，
不声称包含所有 OS DLL 或所有 Python 间接依赖。

## 建立索引

先正常 `media ingest`，再使用实际返回的资产 ID：

```powershell
& $avk semantic index --project $project --index-id campaign-v1 --adapter-id siglip2 `
  --asset-id asset_product --asset-id asset_lifestyle `
  --sample-interval-seconds 2 --max-samples-per-asset 128 --device auto
& $avk semantic verify --project $project --index-id campaign-v1
& $avk semantic index-list --project $project
```

明确选择整个项目时可使用 `--all-visual-assets`，与 `--asset-id` 二选一。
工具自动排除自身登记的预览图片。图片只采样一次；视频使用实际 native PTS、
流时间基与容器起点选择画面，并通过解码 `showinfo` 验证抽取帧。VFR 的长持帧
可能对应多个请求时间，同一实际帧只保留一条记录并保留全部请求时间。

当前上限：每次 512 个源资产、4,096 条索引记录、每视频 128 个请求采样点；
超出预算会拒绝。需由调用方显式调整采样间隔或分库。抽帧不是自动镜头/动作检测。

索引清单、float32 小端向量及 RGB PNG 预览保存在项目 `assets/semantic/`，
均登记来源与派生关系。已有 index ID 不覆盖；失败会清理本操作的新输出，
保留任务诊断。源、预览、向量、清单、登记或模型/实现发生变化时，校验拒绝。

## 文本、批量和参考图查询

```powershell
& $avk semantic search --project $project --index-id campaign-v1 `
  --query '木桌上的一杯咖啡' --limit 5 --device auto
& $avk semantic search --project $project --index-id campaign-v1 `
  --queries-file $queries --limit 3 --kind video --all-samples --device cuda
& $avk semantic search --project $project --index-id campaign-v1 `
  --image $referenceImage --kind image --device cpu
```

查询文件只接收 ID 和文本，不接收人工答案或相关性标签：

```json
{"queries":[{"id":"coffee-zh","text":"木桌上的一杯咖啡"},{"id":"cat-en","text":"a close-up photograph of a cat"}]}
```

一批 1–128 个查询；每条最多 1,024 字符，tokenizer 后最多 64 token。
模型按既定规则转小写，原始查询仍保留；过长输入明确拒绝，不截断。
默认每资产只返回最高分的一个采样点；`--all-samples` 保留各采样点候选。
`--kind` 可限制 image/video；`--min-score` 是调用方显式筛选值，不是概率或
自动校准的“可信命中”。当前默认始终返回排名候选，包括没有正确素材的查询。

检索不改 `project.json` 或权利台账；模型任务与诊断缓存会写入项目 cache。

## 把候选用于可编辑时间线

每项 hit 的 `editable_reference` 返回 `asset_id`、`source_seek_seconds` 和
按当前工程时间基换算的 `source_in_tick`。先展示实际 `preview_uri` 及源时间，
确认候选，再按用户任务明确选择时长并创建已有 `append_clip` 操作。
`point_sample_only=true` 和 `duration_requires_review=true` 表示结果没有给出事件长度。
不能把固定采样间隔当成应剪片段的完整时长。

原素材已是项目资产，可直接编辑；外部参考图不因查询而成为工程素材。
索引/预览的派生登记不授予源内容新的商业权利。发布继续经过原有 rights gate。

## GPU、超时和取消

`auto` 优先使用具有足够空闲显存的已存在 NVIDIA 设备；预检预算为 3,072MiB。
`cuda` 为严格选择，设备不存在或不够资源时失败。`cpu` 明确使用 CPU。
`--device-index` 选择设备，未停止或抢占其他 GPU 任务。

worker 报告实际设备、模型 dtype、模型加载/推理时间、CUDA 已分配/预留峰值、
前向次数及批次内模型加载次数。auto 遇到可识别的 CUDA 执行错误可明确重试 CPU，
并保留原始 GPU 失败。完整性或协议错误不能通过 CPU 回退绕过。

```powershell
& $avk semantic search --project $project --index-id campaign-v1 --query 'a cat' `
  --device auto --batch-size 8 --timeout-seconds 600 --cancel-file $cancelMarker
```

取消通过创建调用方指定的 marker 文件完成。任务在独立进程执行，有界等待并终止
本操作的子进程；大型完整性核验阶段的取消响应和总体性能仍需持续改进。
当前无跨命令模型常驻服务。应把多条查询合为一批以摊薄启动成本。

## 实测与未完成范围

预先冻结的样例包含 8 类现成自然静态图片、误导文件名的重复图片、一个三镜头
静态图序列视频，以及 20 条中英/否定/库外查询。标签与门槛在第一次检索前固定。
这些常见公开图片可能曾出现在模型训练中，不能作为未见分布或自然动作理解证据。

开发版 25 项契约测试通过（部分用模拟向量检查完整性）；安装版另 25 项通过。
122 项 CLI 回归和 34 项离线策略回归分别通过，不与历史或相互覆盖的测试相加。
实际开发模型执行包括 2 次 CUDA 图像前向，以及文本/视频候选/参考图/CPU 对照
检索中的 11 次前向。GPU 与 CPU 对 16 条常规查询的首选和 mean asset recall@3
均为 1.0，六个静态序列视频时间点全部符合冻结标注，裁剪猫参考图首选正确。
同图误导文件名的两份向量逐位相同；查询未改工程和权利台账。

中文否定查询误选咖啡，英文否定通过；两个库外鲨鱼查询均返回草地候选，未实现
可靠拒识。全部 20 条保留于[完整结果板](../assets/semantic-20261025-r1/all-query-results.png)，
原始响应和评分见[开发相关性](../validation/evidence/semantic-20261025-r1/development-r1/queries/quality.json)。

真实异常 CLI 覆盖重复索引、预取消、过长文本、不可用 GPU、向量/源/清单改动；
均按预期拒绝，恢复后完整性验证通过。另一次在 worker 实际存活后取消，约
0.21 秒返回且子进程退出；此结果只证明启动/完整性阶段取消，不代表 CUDA 内核
执行期间或宿主大文件哈希阶段响应已验收。

开发版真实候选已用于三段可编辑时间线、渲染、质检、工程包往返与重渲染：
3 秒、640×360、30fps/90 帧，往返解码画面相同。每段明确创作 1 秒长度，
未从采样点推断事件边界；案例不代表自然动作或自动广告导演。
安装包、真实统一入口及最终安装版案例分别见
[本地交付](COMMUNITY_LOCAL_DELIVERY.md)、
[统一入口证据](../validation/evidence/semantic-20261025-r1/skill-r1/verification.json)、
[安装版成片证据](../validation/evidence/semantic-20261025-r1/installed-r1/demo/verification.json)。

开放项包括：可靠否定/关系理解、自动拒绝无匹配、自然运动/动作、跨镜头人物身份、
音频 embedding、配乐/音效推荐、长期大库性能、常驻模型复用和独立 Agent 成功率。
本功能的阶段交付不关闭完整 G26，也不缩小其他 37 组目标。
