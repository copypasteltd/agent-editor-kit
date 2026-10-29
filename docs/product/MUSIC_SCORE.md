# Agent可编辑谱面、原创程序配乐与音效

**当前已正式安装并注册CLI59/local57。** 真实C盘Skill入口已完成谱面／音效生成与完整PCM核验；安装400项亦通过。[当前使用流程](../validation/CLI59统一Skill切换_2026-10-29.md)。下方候选等待描述保留为阶段历史。


当前版本为**已正式安装及注册CLI0.1.59/local57/r57**。原生安装、配乐专项、400安装回归、完整音画重放及实际C盘入口均已通过；统一Skill不回落源码。这里实现的是谱面驱动的解析合成器，不是神经文本生曲，也不将其视作完整AI配乐目标已完成。[直接使用已安装候选59](../validation/CLI59独立安装交付_2026-10-29.md)。

## 已实现的接口与使用顺序

| 编号 | 接口 | 输入与输出 |
| --- | --- | --- |
| M01 | `music inspect-score --input score.json` | 严格校验并规范化谱面，返回帧数、音符数和CPU执行信息，不生成文件 |
| M02 | `music compose --project PROJECT --input score.json` | 流式生成48kHz双声道16bit WAV，导入音频资产并保存可编辑谱面与来源 |
| M03 | `--stems` | 另存每轨前置主总线处理的完整长度分轨；谱面保留主增益／限幅设置 |
| M04 | `--apply --track-id AUDIO_TRACK --timeline-start-seconds 0` | 预先检查目标轨道后挂接时间线；不改变既有音轨或覆盖原文件 |
| M05 | `music effect --preset whoosh/riser/impact/chime --duration-seconds 2` | 使用解析噪声、振荡器与包络生成4类可编辑电子音效，非环境录音拟真模型 |
| M06 | `convert export/import --target-format package` | 工程包保留谱面、音频、分轨、来源与权利；可在导入后重新合成 |

以下明确调用开发源码，需现有原生Python、NumPy、Pillow、jsonschema、FFmpeg/ffprobe。正式Skill59也支持同一命令，生产使用顶部统一Skill入口；不需要新虚拟环境、模型下载或音乐服务。

```powershell
$python = 'C:/Python313/python.exe'
$entry = 'E:/dev/sandbox/AI广告剪辑/scripts/run_source_editor.py'
$score = 'E:/dev/sandbox/AI广告剪辑/docs/assets/music-score59-20261029-r1/score.json'
$project = 'E:/video-work/original-score59' # 新的空目录
& $python -E -B $entry version
& $python -E -B $entry music inspect-score --input $score
& $python -E -B $entry project init $project
& $python -E -B $entry music compose --project $project --input $score --new-asset-id song --stems --apply --track-id track_audio_1 --dry-run
& $python -E -B $entry music compose --project $project --input $score --new-asset-id song --stems --apply --track-id track_audio_1
& $python -E -B $entry music effect --project $project --preset whoosh --duration-seconds 2 --new-asset-id whoosh
```

输出存入 `assets/music-scores/ASSET_ID/`：`master.wav`、`score.json`、`SOURCE.json`，选用分轨时还有 `stem-NN.wav`。再次编排时修改谱面并使用新的资产ID重新合成，保留原版本。Agent负责把创意和结构落实成音符、配器和节奏；本接口不将自然语言自动转成谱面。

## 谱面格式与实际合成内容

```json
{
  "format": "agent-music-score-v1",
  "tempo_bpm": 120,
  "duration_beats": 8,
  "seed": 42,
  "master_gain_db": -6,
  "limiter": "none",
  "tracks": [{
    "id": "lead", "instrument": "pluck", "gain_db": -12, "pan": -0.2,
    "notes": [
      {"id":"n1","start_beat":0,"duration_beats":2,"pitch":62,"velocity":0.7},
      {"id":"n2","start_beat":2,"duration_beats":2,"pitch":69,"velocity":0.6},
      {"id":"n3","start_beat":4,"duration_beats":4,"pitch":65,"velocity":0.7}
    ]
  }]
}
```

音高为整数MIDI21–108；`69`为440Hz。时间使用拍而非音频文件循环；先按十进制数的有理值换算48kHz采样位置，取最近整数（恰好半数时取偶数）。`duration_beats × 60 / tempo_bpm` 是输出时长；音符须完整落在谱面内，不自动截断或延长。稳定轨道／音符ID绑定噪声种子，重排同一内容或改变流式分块不改变同机PCM。

| 编号 | 乐器 | 实际内容 |
| --- | --- | --- |
| I01 | `sine` | MIDI音高的正弦波，短起止包络 |
| I02 | `pluck` | 基频与2、3次谐波按1／0.3／0.1混合，指数衰减与去点击包络；非钢琴采样 |
| I03 | `bell` | 基频、2.01倍及3.9倍非整数泛音，各自不同衰减；电子钟声 |
| I04 | `pad` | 基频与2、3次谐波，加整段正弦平方渐入渐出包络；非真实弦乐模型 |
| I05 | `kick` | 下降瞬态频率的正弦低鼓与指数衰减 |
| I06 | `snare` | 固定种子的解析噪声与185Hz鼓体，指数衰减 |
| I07 | `hihat` | 相邻噪声采样差分与短衰减，高频打击感 |
| I08 | `sweep` | 固定种子噪声乘上升相位振荡和整段包络，供whoosh／riser |

立体声为等功率声像，`pan=-1`全左，`1`全右。主总线默认不自动归一化；溢出会失败并清理此次输出，可降低增益或明确使用 `limiter:"tanh"`。分轨在主增益和主限幅之前导出，不能在有非线性主限幅时直接相加冒充最终母带。实际CPU合成成本、前置峰值、输出采样峰值、RMS、帧数与摘要写入来源记录；RMS／采样峰值不是LUFS或真峰值验收。

## 资源、事务与权利边界

| 编号 | 约束 | 行为 |
| --- | --- | --- |
| B01 | 20–300 BPM、至多600秒、16轨、每轨512音符、总2048音符 | 拒绝非法值、布尔伪数字、NaN、重复ID和未知字段 |
| B02 | 至多1800累计音符秒；主音轨加分轨PCM最多512MiB | 流式处理，不把完整长曲展开到RAM；不代表整个Python进程内存上限 |
| B03 | 每个音符至少占1采样且不超界 | 不隐式补成完整乐曲；全静音结果拒绝 |
| B04 | 标准CLI工程写锁、可恢复元数据事务、分块取消检查 | 无效目标在合成前拒绝；取消、削波或晚期提交错误清理本次目录并恢复工程元数据 |
| B05 | 不使用权重、录音素材或共享音乐服务 | CPU解析合成；未声称GPU神经音乐或真实乐器拟真 |
| B06 | 输出默认`unverified`、仅`internal` | 引擎不自动确认用户谱面／输出的商用权利；使用既有rights接口登记真实来源与许可 |

同机跨分块和顺序稳定已测试；不同NumPy／CPU平台的逐字节一致未验收。结构重写、自动和声／旋律规划、画面语义匹配、无缝循环修复、神经音乐及自然听审仍是G25待实现或待验收内容。YuE2权重许可问题另见[后端接入边界](MUSIC_BACKEND_ADMISSION.md)。

## 实际案例与验收

[C75原始WAV、成片、GIF、谱面与工程包](CASES.md#c75-source59-editable-score)。这是一首16秒、5轨原创程序合成诊断配乐，不冒充人类演奏、神经生成、自然质量或完整剪映等价。

源码19专项及31入口／57选材／104语义分组分别通过；控制19项r1出现1个PID标记空读错误，原子发布标记原型4项通过后修复正式测试，控制19项r2全部通过；400项服务契约全部通过且运行期冻结一致。400项在PID测试夹具修复前完成，修复不涉及应用源码或其400项测试模块。[本轮实现与证据](../validation/CLI59谱面合成_2026-10-29.md)。
