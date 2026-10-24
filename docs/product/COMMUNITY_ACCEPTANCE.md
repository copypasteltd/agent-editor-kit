# 素材与 GPU 扩展验收 / Community and GPU acceptance

2026-10-25；当前本机 **CLI 0.1.3 / `v0.1.0-alpha.4-local.1`**。本页验收本轮素材/配音/翻译/配乐/GPU 扩展，不把它当作完整剪映功能或成片质量的验收。

This page records the scoped local extension. It does not certify full CapCut equivalence, natural-media quality, human listening or semantic translation acceptance. Public alpha.3 remains unchanged.

[需求基线](MATERIALS_EXPANSION_20261024.md) · [完整使用流程](COMMUNITY_MATERIALS.md) · [English](COMMUNITY_MATERIALS.en.md) · [繁體中文](COMMUNITY_MATERIALS.zh-TW.md) · [离线包与安装](COMMUNITY_LOCAL_DELIVERY.md)

| 编号 | 本轮交付 / Delivered | 实际证据 / Evidence | 仍保留的边界 / Limits |
|---|---|---|---|
| M01 | 359 个真实资源：44 BGM、85 短乐、228 独立音效、2 字体；稳定 ID 与逐项查询 | [全部素材](COMMUNITY_MATERIAL_CATALOG.md)；CPU `verify-all-materials` 实际校验 359 文件 | 不是商业素材订阅库；两对重复音效保留别名但不重复计数 |
| M02 | 中英本地配音、103 上游具名音色、UTF-8 文件、语速、WAV 和项目导入 | CPU 三音色真实生成，GPU/default-Skill 真实生成；[音色范围](COMMUNITY_VOICES.md) | 只生成 3 个不同音色的常规试听文件，不是 103 个音色逐个推理/听审；无真人克隆 |
| M03 | OPUS 中英双向文本/字幕、简繁、双语与术语译后替换 | CPU/GPU 真实推理；乱序/重叠 cue、毫秒和输出顺序保留；术语替换实际执行 | 仍有 `speech`→“演讲”的语境错误；无自动语义接受、口型或强制对齐 |
| M04 | 真正 BGM 截取、偏移、循环、增益、淡化 | 12 秒 576000 样本及 4 秒 192000 样本实际输出 | 循环不等于接缝修复，不生成原创配乐 |
| M05 | 独立人声/BGM 混音、限幅和侧链闪避 | [PCM 测量](../validation/evidence/community-materials-20261025-r1/cpu/ducking-measurement.json)：27 个人声窗口，背景音乐中位压低约 8.59 dB | 测量通过不等于听感或真峰值接受；保留原分轨，不静默截断台词 |
| M06 | 开源音效、Noto 简繁字体和实际字幕/标题成片 | 可公开 r2 示例、内部语音案例；PNG 与编码帧分别检查 | OFL/RFN 和字体版权保留；不再分发商业系统字体 |
| M07 | 应用与 4 个可选模型包分层、原生离线安装、全文件哈希 | [8 条可移动安装/拒绝检查](../validation/evidence/community-materials-20261025-r1/portable/verification.json)，实际中文/空格路径 | 目前只验收 Windows CPython 3.13 x64；未测试其他 OS/ABI |
| M08 | 一个统一 Skill、17 内部模块，默认走已配置 GPU | [11 条实际发现入口调用](../validation/evidence/community-materials-20261025-r1/skill/verification.json)，不传模型路径也实际 CUDA 推理 | 不代表单独 Agent 行为评测；旧 16 个源模块/历史包保留 |
| M09 | 三语 README 与手册、359 素材和 103 音色表、案例/GIF/响应及新本地包 | [当前手册](COMMUNITY_MATERIALS.md)、[离线交付](COMMUNITY_LOCAL_DELIVERY.md)、实际证据和可复现脚本 | 生成配音权利尚未按客户场景确认，因此完整 WAV/配音成片留在本机 |
| M10 | 保留缺失/篡改、GPU 失败、错译、文字溢出与原始失败路径 | [历史失败](../validation/evidence/community-materials-20261025-r1/history/)、[首版排版问题](../assets/community-materials-20261025-r1/KNOWN_ISSUE.md) | 不把解码或命令通过数当作剪映等价/商业画质评分 |
| G01 | auto/cpu/cuda，GPU 配音和中英字幕/文本翻译 | [15 条 CUDA 检查](../validation/evidence/community-materials-20261025-r1/gpu/verification.json)：RTX 3060；真实 CUDA provider、`int8_float16` | 仅本机显卡实测；GPU 冷加载可能慢于 CPU；配音目前仅设备 0 |
| G02 | 空闲显存预检、明确回退、严格 CUDA 失败 | GPU 无效设备、真实运行库缺失时 auto 回退/严格拒绝；日志保留 | 未人为耗尽整块显存制造 OOM；3072/1536 MiB 预检不是绝不 OOM 保证；不停止其他任务 |
| G03 | CPU 开源数值方案与可选 GPU 依赖分层 | 自编 CT2 Ruy；Intel 原始许可/原 DLL 哈希比对；NVIDIA 库保持外部依赖 | GPU 驱动、CUDA/cuDNN 与部分上游二进制依赖包含各自专有条款，不标成开源素材 |

## 分开计数的真实执行 / Separate executions

| 编号 | 执行 | 结果 |
|---|---|---|
| R33 | 最终安装版 CPU 专项，46 条命令，8 次模型推理、3 个不同音色 | [记录](../validation/evidence/community-materials-20261025-r1/cpu/verification.json)；12 秒、360 帧完整解码、7 项预期拒绝、工程包往返 |
| R34 | 最终安装版 GPU 专项，15 条命令 | [记录](../validation/evidence/community-materials-20261025-r1/gpu/verification.json)；CUDA 配音、双向文本/字幕、CPU 指定、回退和严格失败 |
| R35 | 4 模型包的 8 条安装/拒绝命令 | [记录](../validation/evidence/community-materials-20261025-r1/portable/verification.json)；原 ZIP/已有安装不变，错误文件拒绝后 staging 清理 |
| R36 | C 盘 Codex 发现目录实际入口，11 条 CLI 命令及真实注册回执 | [记录](../validation/evidence/community-materials-20261025-r1/skill/verification.json)；仅一个 `$agent-ffmpeg-local-editor`，默认配音/翻译实际 CUDA |
| R37a | 排版修正后的 8 条命令，无新模型推理 | [记录](../validation/evidence/community-materials-20261025-r1/cpu/presentation-correction/verification.json)；新成片与工程往返，预览/编码帧 RGB 平均绝对差约 1.34/255 |
| R37b | 可公开素材示例，14 条 CLI 命令，无生成配音 | [记录](../assets/community-materials-20261025-r2/verification.json)；12 秒 360 帧，权利门禁与完整解码通过，实际 MP4/GIF |

这些数字不与历史 2930 项回归或旧 alpha 证据相加。首次错误排版的解码曾通过，视觉展示仍不合格：`render --width/height` 改变合成画布，文字样式的像素值不随它自动等比例缩放。已通过固定目标 sequence canvas 修正案例，保留旧成片。自动解码检查无法替代排版目检。

Command totals remain separate from historical regression totals. The first layout was decodable but visibly cropped; the corrected sequence canvas/styles retain its original failed evidence. Automatic decode checks cannot establish text layout quality.

## 性能证据 / Performance scope

同一非量化 Kokoro 模型、同一文本，模型内第二次生成：CPU 约 4.93 秒、CUDA 约 0.62 秒；模型加载：CPU 约 4.08 秒、CUDA 约 7.54 秒。原始测试保留在 [benchmark](../validation/evidence/community-materials-20261025-r1/voice-benchmark/benchmark.json)。GPU 上仍有其他任务；约 8 倍仅指该次热生成，不能套用为单次 CLI 总加速或其他文本/显卡保证。

The measured warm-generation improvement excludes hashing, process startup and model load. These operations remain visible in actual CLI timings; no guarantee is made that every short request is faster on GPU.

## 开源来源与许可 / Sources and licenses

- [Kokoro 中文版](https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh)、[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)：权重/推理封装及其各自 Apache/第三方通知。
- [OPUS-MT](https://github.com/Helsinki-NLP/Opus-MT)、[CTranslate2](https://github.com/OpenNMT/CTranslate2)：本轮原始两个模型归档均为 CC-BY-4.0；CT2 MIT。原始许可优先于冲突的 model card 标签。
- [Kenney](https://kenney.nl/assets)：本轮具体三包为 CC0；[GT RPG soundtrack](https://opengameart.org/content/gt-rpg-soundtrack) 为 Juhani Junkala / CC-BY-4.0；其他曲目逐包列在目录。
- [Noto SC](https://github.com/google/fonts/tree/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/notosanssc)、[Noto TC](https://github.com/google/fonts/tree/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/notosanstc)：OFL-1.1，保留原 copyright/RFN。
- GPU 翻译包的 [原始 Intel/oneDNN 通知与来源比对](../../sources/materials-20261024/vendor-notices/ctranslate2-4.8.3-win/provenance.json)；Intel OpenMP DLL 与官方 2025.3 wheel 字节相同。NVIDIA 系统库只按本机已有路径加载。

## 还没有完成的总产品目标 / Remaining product work

| # | 差距 / Remaining gap | 本轮关系 |
|---|---|---|
| P01 | 全量剪映风格特效、模板、贴纸、正版订阅素材及自然素材逐项验收 | 359 开源资源与既有 500 LUT 扩充了目录，尚不等价 |
| P02 | 所有 103 音色、多语种、情绪/唱歌/克隆、客户试听和广告发布上下文 | 本轮支持中英常规合成；其余未承诺 |
| P03 | 通用多语种及人类接受的语境翻译、口型和强制对齐 | 本轮是中英双向文本/保时序字幕，仍需语义复核 |
| P04 | 原创音乐生成、节奏结构重写、无缝循环修复 | 本轮是已有开源音乐的可控准备/混音 |
| P05 | AMD/Intel/Apple GPU、跨平台、长任务/并发显存预算和性能保证 | 目前 Windows RTX 3060 实测；CPU 保留；未杀占用进程或建立虚拟化环境 |
| P06 | 完整 HDR/ICC/浮点算子覆盖、专业音频/自然抠像/修复/转写精度 | 仍沿用既有明确子集和失败边界；本轮未以素材扩展宣称解决 |
| P07 | 将本地扩展另行发布为新的公开 Release | 本轮仅安装本地包并更新 main；alpha.3 标签/附件/摘要保留原版 |

本轮范围内的实现与离线交付已完成；人工听审、翻译语义接受和上述总产品差距作为后续验收项单独保留。

完整产品的现状与 G01–G38 收口条件见 [2026-10-25 目标差距评估](GOAL_GAPS_20261025.md)。本页仍仅记录素材与 GPU 扩展的阶段性验收。
