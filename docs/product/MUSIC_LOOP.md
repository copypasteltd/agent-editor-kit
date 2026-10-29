# 循环音乐接缝修复

开发源码 CLI 0.1.60 新增 `music repair-loop`。当前正式本地安装与统一 Skill 仍为 CLI 0.1.59 / local57 / r57，不能通过该旧入口使用此新命令。CLI60/local58独立候选包已构建并安装，功能回归与Skill切换另行执行；[候选包位置、摘要和使用流程](../validation/CLI60独立安装交付_2026-10-29.md)。旧发布包不覆盖。

## 使用流程

使用已经导入、具有有效权利记录的音频／视频资产。以下调用明确运行开发源码；不要将其当作已安装包验证。

```powershell
$python = 'C:/Python313/python.exe'
$entry = 'E:/dev/sandbox/AI广告剪辑/scripts/run_source_editor.py'
$project = 'E:/video-work/my-project'
& $python -E -B $entry music repair-loop --project $project --asset-id music --crossfade-ms 50 --curve raised-cosine --new-asset-id loop1 --dry-run
& $python -E -B $entry music repair-loop --project $project --asset-id music --crossfade-ms 50 --curve raised-cosine --new-asset-id loop1 --apply --track-id track_audio_1
# 使用产出的 recipe.json 重新生成新的资产；源资产和其完整 SHA256 必须匹配。
& $python -E -B $entry music repair-loop --project $project --input 'E:/video-work/recipe.json' --new-asset-id loop2
```

`--input` 与源资产／交叠／曲线显式参数互斥。默认交叠100毫秒，支持 `linear` 与 `raised-cosine`。交叠须为有限正数、最多5000毫秒，且换算后至少2个样本。毫秒使用有理数换算48kHz样本位置，最近整数、半数取偶。

## 精确语义与限制

源首条音频流经 FFmpeg 解码成48kHz双声道16bit工作 PCM。源最多600秒，实际解码同样有长度限制。格式转换并非原始压缩音频或24bit素材的无损保留。设解码样本数为 N、交叠为 M，要求 N>2M：输出为 `x[M:N-M] + blend(x[N-M:N], x[0:M])`，因此周期变为 **N−M**，每次循环缩短 M 个样本；不会偷偷补齐原时长。

交叠权重为线性 t 或 `0.5−0.5cos(πt)`，首尾含端点，互补增益混合后量化。中段相对于解码工作 PCM 逐字节不变；无隐藏归一化或限幅。CPU 流式实现，块大小4096帧；这是 DSP，不是神经配乐，不以 GPU 推理计数。

输出位于 `assets/music-loops/loop_<资产ID哈希>/`，包含 `master.wav`、严格可编辑的 `recipe.json`、`SOURCE.json`。返回完整PCM摘要、源／输出样本数、缩短量、RMS、峰值、首尾最大采样跳变量。临时解码文件成功后清除。工程包保留该目录及源素材，可导入后按相同配方重做。

`--dry-run` 不生成文件、不修改工程，返回 `exact_sample_count_requires_decode: true`：预检不承诺素材实际长度足够，真实解码才检查 N>2M。轨道类型／锁定／静音预检在解码前执行。取消或失败清理本次新目录，提交后失败由工程事务恢复工程与权利记录。

派生资产继承源许可、限制、渠道、署名和验证状态，校验源文件摘要与禁用状态；不会把未验证来源提升为已验证或自动授权商业用途。

**接缝采样跳变下降不等于听感无缝。** 相位抵消、节拍／和声匹配、乐句自然衔接、响度及真峰值、自然录音和客户听审尚未验收；该接口不做节拍结构重写。处理静音／过短／损坏源会拒绝，不用循环填充掩盖问题。

## C76 实际案例与回归

使用 C75 原创 CC0 解析配乐的13.37秒片段，50毫秒交叠后13.32秒，641760→639360帧，中段636960帧完全保留。双声道最大首尾跳变量0.03521728515625→0.0009765625。分别重复3周期，完整PCM与单元直接重复一致；工程包导入后按配方修复，完整2557440字节PCM相同。没有人工听审、自然音乐无缝验收或神经前向。

![实际接缝波形](../assets/music-loop60-20261029-r1/actual.png)

[原始单元](../assets/music-loop60-20261029-r1/source.wav) · [修复单元](../assets/music-loop60-20261029-r1/unit.wav) · [修复前三循环](../assets/music-loop60-20261029-r1/before.wav) · [修复后三循环](../assets/music-loop60-20261029-r1/after.wav) · [配方](../assets/music-loop60-20261029-r1/recipe.json) · [可编辑工程包](../assets/music-loop60-20261029-r1/package.zip) · [来源与摘要](../assets/music-loop60-20261029-r1/SOURCE_AND_LICENSES.json)。GIF为单帧诊断图，非录屏。

[37项专项回归](../validation/evidence/music-loop-20261029-r1/targeted-r1/verification.json)：18项新修复测试及19项既有谱面测试；包括独立混合公式、中段与分块一致性、错误参数、损坏数据、只读预检、取消清理、提交后回滚、权利继承及工程包重做。[真实案例收据](../validation/evidence/music-loop-20261029-r1/actual-case-r1/verification.json)。G25完整配乐目标继续开放。
