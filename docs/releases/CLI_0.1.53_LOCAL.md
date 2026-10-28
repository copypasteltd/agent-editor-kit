# agent editor kit CLI0.1.53 本地交付

当前本机基础运行与唯一注册 Skill 已升级到 `v0.1.0-alpha.4-local.51` / CLI0.1.53。源码与安装版分别完成18项原生ACES／时间线、46项测量／Schema、373项广泛兼容性回归，均无失败／错误／跳过且冻结一致。完整剪映对标目标仍未完成，保留全部38项闭合条件。

## 交付文件与对应关系

| 编号 | 文件／配置 | 版本或摘要 |
|---|---|---|
| 1 | `local/agent-ffmpeg/v0.1.0-alpha.4-local.51/candidate-r2/bundle.zip` | 305,677,502字节；SHA256 `98e76427a875f8355abe0d75244d437af0dc196986ad36691e1595b426d41ee1` |
| 2 | ZIP内 `manifest.json` | `sha256:9fcf7db46f825b14469293591f35b8f65c1089f7f6fb38a50712db4da54acf30` |
| 3 | 独立安装目录 | `local/agent-ffmpeg/v0.1.0-alpha.4-local.51/final-r2/installed` |
| 4 | 本机唯一注册入口 | `$agent-ffmpeg-local-editor`；1入口／17模块／92文件，CLI53 |
| 5 | 正式小型Skill包 | `docs/skills/agent-editor-kit-community-unified-skill-r54.zip`；727,275字节；SHA256 `bb368702ae26f1b97749501099ac1adc003574716c634cbb99989894ad006e86`；153条目，独立解包／配置／注册／完整YUV与PCM重放通过 |
| 6 | 配置 | `local/agent-ffmpeg/runtime.json`、`community-runtime.json`；保留四个已有CPU／GPU配音和翻译包 |

基础包要求原生Windows CPython3.13 x64和已有FFmpeg；不附带Python、FFmpeg或大型模型权重，不创建venv，不使用Docker／WSL，不下载模型。280个安装代码模块与原生资源字节匹配，能力目录90项。旧local50/r53及公开alpha.3/CLI0.1.2的文件、标签与摘要保持不变。

## 本机最小使用流程

在仓库根目录的原生PowerShell执行；下面使用真实注册入口及已有C66工程包，选择新的输出目录以保留旧工程。

```powershell
$aekSkill = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $aekSkill version
& $aekSkill capabilities
& $aekSkill surface ocio-configs --config aces-2.1

$aekProject = 'E:/dev/sandbox/AI广告剪辑/local/我的ACES工程'
& $aekSkill convert import --input './docs/assets/aces-installed-20261029-r1/editable-aces.zip' --output $aekProject
& $aekSkill validate --project $aekProject
$aekSequence = (Get-Content -LiteralPath (Join-Path $aekProject 'project.json') -Raw -Encoding utf8 | ConvertFrom-Json).sequences[0].id
& $aekSkill render --project $aekProject --sequence-id $aekSequence --output (Join-Path $aekProject 'renders/aces.mkv')
& $aekSkill preview frame --project $aekProject --frame 7 --height 128
& $aekSkill preview range --project $aekProject --start-frame 0 --end-frame 8 --height 64
& $aekSkill surface measure --project $aekProject --sequence-id $aekSequence
& $aekSkill convert export --project $aekProject --output (Join-Path $aekProject 'exports/editable.zip') --target-format package
```

新机器的解包、固定摘要安装、模型包配置及唯一入口注册，按[完整原生安装流程](../product/COMMUNITY_LOCAL_DELIVERY.md)执行；不能把旧alpha.3基础包与新r54 Skill混用。

## 本版新增能力与边界

固定官方OCIO2.6.0及ACES1.3／2.0／2.1 Studio配置，支持场景线性ACEScg输入、显式display/view、正式SDR／PQ／HLG输出、单次显示变换后的显示线性预览缩图、独立HDR母版SDR观看视图、全帧测量与原生依赖核验。配置版本与视图名称不同：ACES2.1配置中的SDR视图实际仍名为ACES2.0 SDR100nit。

原生ACES运行在CPU；既有GPU色域映射、投影、光效以及配音／翻译配置保留。本轮未新增模型推理。未实现或未验收的相机自动IDT、AMF／LMT、GPU ACES、物理HDR监看、自然连续观片／听审和完整产品对标继续列入原目标，不能用数值图卡或通过的测试数量替代。

[ACES操作参数](../product/ACES_TIMELINE.md) · [原生内核与许可](../product/ACES_NATIVE.md) · [C66影片／GIF／工程包](../product/CASES.md#c66-installed-aces-timeline) · [本轮原始收据](../validation/ACES离线交付进度_2026-10-29.md) · [原38项闭合条件](../product/GOAL_GAPS_20261025.md)

繁體：本機CLI53與唯一Skill已註冊，原始碼及安裝分組驗收通過；完整產品目標仍開放。English: CLI53 is locally installed and registered; source and installed acceptance groups passed independently. Full product parity remains unachieved.
