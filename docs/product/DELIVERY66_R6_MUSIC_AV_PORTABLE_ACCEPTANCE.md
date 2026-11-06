# CLI66：真实GPU配乐、完整音画工程与便携包验收

2026-11-06，Asia/Taipei。本页记录r6安装版完整回归之后的实际结果，不改写原失败，不关闭G01—G38。源码和安装版各自4,124项完整通过的证据见[安装验收](DELIVERY66_R6_INSTALLED_ACCEPTANCE.md)，不能与下述8项工具契约或其他测试组累加。

## 已实际通过

| 编号 | 实际执行 | 结果与证据 | 尚未证明的范围 |
| --- | --- | --- | --- |
| A01 | 候选单Skill的真实PowerShell入口调用独立安装版CLI0.1.66，执行神经配乐 | RTX3060、Torch2.13.0+cu130／CUDA13.0；文本2、语言模型50、扩散8、VAE1次前向均在CUDA0。四个权重实际pread打开，dynamic_vram=false；允许权重CPU卸载，无CPU神经前向回落。[原始收据](../validation/evidence/delivery66-20261106-r1/native-music-r1/verification.json) | 一次10秒任务，不证明长曲、演唱、更多曲风、跨设备质量或吞吐 |
| A02 | 完整母音频、入轨及归属清理 | 10秒、48kHz、双声道Float32 WAV，每声道480000样本；完整PCM独立回读、900000tick音轨、原工作进程退出及受管工作目录清理通过 | 没有人工完整听审，natural_quality_accepted=false；输出仍internal/unverified，不作为已获准公开的声音样例 |
| A03 | 给派生工程合法添加画面，再导出、导入、双端渲染与完整解码对照 | FFmpeg程序图案320×568／30fps／300帧／10秒；原始生曲工程不变。母WAV、完整生成配方、所有RGBA及PCM一致。[实际重放](../validation/evidence/delivery66-20261106-r1/package-replay-r2/verification.json) | 程序图案不是自然剪辑质量验收；没有再次进行模型前向 |
| A04 | 独立便携包基础配置、单Skill注册和实际入口媒体重放 | r59 ZIP，168条目，SHA256 `02528ab7cc05d9195e7107fc51e2fe845a0935649dc0b7568b36b805950bda96`；真实离线安装、`--base-only`、PowerShell及完整RGBA／PCM通过。[便携验收](../validation/evidence/delivery66-handoff-20261106-r1/portable-kit-r1/verification.json) | 同机新目录与既有原生依赖，clean_host=false、cross_machine=false；基础配置无需可选模型包 |

候选应用为local64／CLI0.1.66、289应用模块；候选Skill为95文件／17内部模块。正式唯一Skill在本页记录时仍为CLI0.1.63／local61／r58。候选和便携安装通过不等于正式发现入口已切换。

## 媒体数值与实际成本

| 项目 | 实际值 |
| --- | --- |
| 母WAV SHA256 | `dbe4b13c061a7ca0533a63b3f3cae37d99e9cd1c622c4bd2e575ab22062f9a77`，3840092字节 |
| 母WAV完整PCM SHA256 | `90b6eddc68799d3ed6882358b6ea9685c100cbaee6664db3eda33b7ccf7eaa62` |
| 重放完整RGBA SHA256 | `7edb455305942832f7f3f18a7adf8a27840cf2ed3d8e700157d6c029852cceb1` |
| 重放编码后完整PCM SHA256 | `e0a697aae8b8d1b266e3fa88c23bc6775dcbcf06f8daa3d555ff68fdea5e19b4` |
| 编码后音频 | 48kHz／双声道，AAC完整解码每声道480256样本；有限非静音，RMS0.017295569831956913、峰值0.2689383029937744。与母WAV的480000样本分别记录 |
| 登记／预检／生成调用 | 分别270.089秒／145.562秒／848.931秒；生成约14.15分钟 |
| 工作进程生成／模型函数 | 分别696.468秒／395.299秒；模型函数包含运行时导入204.652秒，各层互相包含，不能相加 |

这些是一例实测的成本；与历史CLI65的39.25分钟生成调用不构成相同条件性能对照，不能据此宣称加速倍数。模型导入、权重读盘／校验、载入、推理、编码和跨任务常驻仍要独立建立性能矩阵。

本地母音频：`local/agent-ffmpeg/delivery66/music-r1/project/assets/derived/piano66.wav`。本地工程包：`local/agent-ffmpeg/delivery66/package-r2/music.aevpkg.zip`。本地成片：`local/agent-ffmpeg/delivery66/package-r2/original/renders/music.mp4`。上述媒体仅供本地复查，不在本次公开提交中附带未经听审及用途确认的音乐输出。

## 保留的失败与完整修正批次

原`package-replay-r1`尝试把只有音乐的工程渲染成视频；CLI实际以`VIDEO_TRACK_EMPTY`拒绝，退出码2。该拒绝是正确的产品行为，原[调用记录](../validation/evidence/delivery66-20261106-r1/package-replay-r1/calls.json)和[结构化错误](../validation/evidence/delivery66-20261106-r1/package-replay-r1/original-render.stdout)保留，旧监督进程失败终态也保留。

随后先写齐三个独立验收／衔接文件，再冻结、集中验证：`delivery66_av_replay.py`、`test_delivery66_av_replay.py`、`continue_delivery66_handoff.py`。原546产品／用例／依赖、8交付工具、69构建来源及95正式文件均未改动，既有产品断言和视频空轨拒绝规则保留。

| 编号 | 新批次 | 结果 |
| --- | --- | --- |
| Q01 | 三文件写齐并冻结 | [代码阶段收据](../validation/evidence/delivery66-handoff-20261106-r1/av-replay-code-phase-r1/verification.json)，先于功能验证 |
| Q02 | 独立媒体契约 | [8项完整通过](../validation/evidence/delivery66-handoff-20261106-r1/av-replay-contracts-r1/verification.json)，0失败／错误／跳过；覆盖空画面、额外音轨、缺末帧、错误音画时钟、NaN／Inf、静音、截短及过多填充。夹具测试不冒充神经推理 |
| Q03 | 实际r2工程 | 在复制工程中通过真实CLI摄入合法画面；原生渲染、迁移和完整RGBA／PCM均通过，原始生曲工程逐文件未变 |

复现时使用[更新后的衔接说明](DELIVERY66_HANDOFF.md)：工程重放用`--run r2`，后续descriptor／kit／verify-kit／faults／activate／assets统一传`--package-run r2`；原freeze／tests仍为r6。已经存在的运行编号不可覆盖，旧失败观察器不可再次启动。

## 继续开放

真实取消、超时、发布目标冲突以各自实际模型收据为准；正式切换／回滚、实际C盘发现入口、发布源绑定和alpha.4公开附件仍须取得各自终态。[详细未完成清单](UNFINISHED_DETAIL_20261106.md)。第二台CPU升级循环的独立证据见[跨机器结果](CROSS_MACHINE66_RESULTS.md)。这些通过项都不替代人工视听、自然素材质量、干净主机和全部GPU迁移验收。
