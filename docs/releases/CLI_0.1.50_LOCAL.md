# CLI 0.1.50 本地发行 / Local release

本地版本 **v0.1.0-alpha.4-local.48**，统一入口 **`$agent-ffmpeg-local-editor`**，17个内部模块、89个Skill文件。公开GitHub alpha.3/CLI0.1.2的标签和附件保持原字节；本记录为新本地构建，不是新的公开Release。

新增 `surface measure-media` 编码后成片光量核验，保留既有编码前 `surface measure`。实际作者渲染与解码后数字光量的边界必须分开；两者都不是物理显示器实测。[完整使用说明](../product/HDR_MEDIA_MEASUREMENT.md)。

## 本地包与调用

| 编号 | 文件或状态 | 实际值 |
| --- | --- | --- |
| L01 | 基础运行ZIP | `local/agent-ffmpeg/v0.1.0-alpha.4-local.48/candidate-r1/bundle.zip` |
| L02 | ZIP bytes | 303217936 |
| L03 | ZIP SHA-256 | `d1907d2c1037b72833d0950866364fa1136d3880eb36a1435dbe0a6242a2611b` |
| L04 | 清单摘要 | `sha256:964eae07d10658ccf0b5e9f3b3941d58c1480603366a61613560654a9e3b0cff` |
| L05 | 已安装目录 | `local/agent-ffmpeg/v0.1.0-alpha.4-local.48/final-r1/installed` |
| L06 | 统一Skill kit | [r51 ZIP](../skills/agent-editor-kit-community-unified-skill-r51.zip) / [摘要](../skills/community-unified-skill-package-0.1.50-r51.json) |

以上相对路径以 `E:/dev/sandbox/AI广告剪辑/` 为根。已有原生Windows x64、CPython3.13、FFmpeg/ffprobe及GPU任务对应的本地依赖；不调用Docker、WSL、虚拟环境、全局pip或隐式模型下载。新功能本身不需要新神经模型。

```powershell
$aekSkill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aekSkill version
& $aekSkill surface measure-media --help
& $aekSkill surface measure-media --project PROJECT --input renders/master.mkv --signal-json SIGNAL.json --pixel-family yuv --yuv-matrix bt2020nc --yuv-range limited --chroma-location left --scan progressive --dry-run
```

将 `PROJECT` 和 `SIGNAL.json` 替换为实际绝对路径，输入成片需位于工程内。PQ信号JSON例：`{"primaries":"bt2020","transfer":"pq-st2084","reference_white_nits":203}`。核对计划后去掉 `--dry-run` 进行原生逐帧读取。默认越界失败；明确接受截断时才加 `--range-policy clip`，并将裁切计数随报告交付。HLG须明确显示峰值、gamma及需要时的黑位；RGB成片不带YCbCr参数。

源文件或信号发生变化后重新计划，取消使用工程内 `--cancel-file`。未知帧时长不按FPS猜测，曝光缺口/重叠直接报告。保留完整JSON中的源SHA、解码RGBA/时钟摘要、MaxRGB/CIE Y、原生解码进程退出与线程回收结果。

迁移至新目录时，按[完整离线安装流程](../product/COMMUNITY_LOCAL_DELIVERY.md)校验ZIP和清单、原生安装、加载可选模型包、激活同版本runtime、注册单入口。r51必须匹配本地.48应用，不能套用alpha.3或旧r50运行包。

## 本轮核验和限制

安装专项29/29、边界42/42、兼容352/352分别通过，276份Python源码/安装相同。C60由实际C盘发现联接的Skill完成PQ/HLG H.265 Main10 4:2:0渲染、完整独立像素/光量核对及HLG工程包重放；完整PCM也相同。四个既有语音/翻译模型包已核验并保留配置，本轮没有新增模型推理或下载。

C60图表为CC0合成数值诊断，不代替自然画面艺术验收。实际4:2:0重建存在越界；失败的reject记录保留，后续clip结果明确带计数。GIF/MP4仅为作者时间线的显式SDR查看副本。4K/长片/更多编解码、动态HDR、完整ACES/感知色域/自然HDR监看及完整剪映等价仍未完成。

繁體：本地CLI0.1.50已安裝並註冊為單一Skill；新增解碼後成片光量複核，須明確色彩與原生時鐘，不自動寫入SEI。請配對r51及本地.48套件；公開alpha.3仍為舊版。[實測](../validation/编码后成片安装与跨编码实测_2026-10-29.md)。

English: CLI0.1.50 is installed as local.48 and exposed through one unified Skill with17modules/89files.Match the r51kit to this bundle;public alpha.3 remains unchanged.Use explicit signal/native-clock semantics and retain range counts.Post-codec digital metering does not certify a physical HDR display or complete CapCut parity.[Evidence](../validation/编码后成片安装与跨编码实测_2026-10-29.md).
