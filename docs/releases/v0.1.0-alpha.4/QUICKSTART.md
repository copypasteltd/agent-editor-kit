# agent editor kit / CLI0.1.66

原生Windows CPython3.13 x64应用；唯一公开入口为 `$agent-ffmpeg-local-editor`，包含17个内部模块。应用ZIP不包含Python、FFmpeg／ffprobe、驱动、模型权重或完整音乐运行库。先准备本机依赖；不使用Docker、WSL或虚拟环境。

1. 下载本次Release的两个ZIP、SHA256SUMS.txt及本语言快速开始到同一目录。把下面的路径改为实际路径。逐项比较计算摘要与清单，全部匹配后解包到新目录；后续安装器还会校验应用内部清单。

```powershell
$downloads = "E:/video-tools/downloads"
$bundle = "E:/video-tools/application-bundle"
$kit = "E:/video-tools/skill-kit"
Get-Content -LiteralPath "$downloads/SHA256SUMS.txt"
Get-FileHash -LiteralPath "$downloads/agent-editor-kit-v0.1.0-alpha.4-cp313-win_amd64.zip" -Algorithm SHA256
Get-FileHash -LiteralPath "$downloads/agent-editor-kit-community-unified-skill-r59.zip" -Algorithm SHA256
Expand-Archive -LiteralPath "$downloads/agent-editor-kit-v0.1.0-alpha.4-cp313-win_amd64.zip" -DestinationPath $bundle
Expand-Archive -LiteralPath "$downloads/agent-editor-kit-community-unified-skill-r59.zip" -DestinationPath $kit
```

2. 离线安装应用。目标目录必须是新路径。此步骤不下载模型；模型尚未准备时，可先通过安装版入口执行version／doctor及基础剪辑命令。

```powershell
$python = "C:/Python313/python.exe"
$installed = "E:/video-tools/application-installed"
& $python -E -B -X utf8 "$bundle/install.py" --bundle $bundle --target $installed --manifest-sha256 "sha256:1da7f0a678ea678f49af6d9b847dfd8912b11ede04aad22f8d87ee247ee1117a"
& $python -I -S -B -X utf8 "$installed/run.py" version
& $python -I -S -B -X utf8 "$installed/run.py" doctor
```

3. 配置基础剪辑模式，将统一Skill绑定到上述安装目录。时间线、滤镜、字幕、预览和渲染可直接使用；配音、翻译和语义模型按下一段另行配置。配置器先备份旧配置，再建立基础绑定并清除旧机器模型路径。

```powershell
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --base-only
```

可选模型：需要配音／翻译时，先准备已校验的 `kokoro-zh-en-int8` 与 `opus-zh-en-cpu-int8` 两个CPU包；`kokoro-zh-en-cuda13` 与 `opus-zh-en-cuda12-int8` 为可选GPU包。PACKS指向包含这四种解包目录的父目录；配置器要求两个CPU包，并逐包验证后写入模型绑定。本次两个ZIP未包含这些模型包；来源、许可、预期摘要与复现工具见下方链接。

[Model catalog and pinned manifests](https://github.com/copypasteltd/agent-editor-kit/blob/main/product/src/ai_ad_editor/material_data/model-packs.json) · [CPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_model_pack.py) · [GPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_gpu_packs.py) · [Offline pack installer](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/install_community_pack.py)

```powershell
$packs = "E:/video-tools/model-packs"
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --packs $packs
```

若使用GPU包，将配置命令替换为下面的形式，并填写对应的实际DLL目录。配音与翻译的CUDA版本要求不同；不要把两个目录混写。后续使用 `--device auto` 优先选择配置的GPU，并检查返回的实际设备／provider及CPU回落说明。

```powershell
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --packs $packs --voice-cuda-lib "E:/video-tools/cuda13/bin" --translation-cuda-lib "E:/video-tools/cuda12/bin"
```

4. 注册唯一Skill并检查实际安装版本。已有同名入口且指向其他位置时，注册器会保留并拒绝替换；升级请先阅读随包交付说明，不手工删除不明目录。Agent外层只需指定 `$agent-ffmpeg-local-editor`。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$kit/register-agent-ffmpeg-local-skills.ps1"
$entry = "$kit/skills/agent-ffmpeg-local-editor/scripts/run.ps1"
& $entry version
& $entry doctor
& $entry capabilities
& $entry model-pack list
& $entry gpu inspect
```

5. 创建工程并导入自己的授权素材。下例中的视频、图片、字幕、配音文本和changes.json必须实际存在。读取导入返回的 `data.asset.id`，再依据schema及帮助编写changes.json；不能照抄旧案例的随机ID。视频和音频轨须分别编排，先预览实际滤镜候选并记录客户选择，再合成时间线。

```powershell
$aekProject = "E:/video-work/my-ad"
& $entry project init $aekProject --name "My ad"
& $entry media ingest --project $aekProject --input "E:/media/product.mp4"
& $entry schema show
& $entry timeline compose --help
& $entry look list --query "Kodak"
& $entry look inspect --id t3-kodak-gold-200
& $entry look preview --id t3-kodak-gold-200 --input "E:/media/still.png" --output "$aekProject/exports/film-preview.png" --strength 0.65
& $entry timeline compose --project $aekProject --input "E:/video-work/changes.json"
& $entry look apply --project $aekProject --id t3-kodak-gold-200 --global --strength 0.65 --dry-run
& $entry look apply --project $aekProject --id t3-kodak-gold-200 --global --strength 0.65
```

可选配音／翻译示例会真实运行模型，需先准备输入文件、模型包与配置，并使用新的asset ID。完整音频、发音、翻译语义和时长仍需复核。生成后用真实音频资产ID编写voice-changes.json，将声音显式编入音轨，再执行下面最后一条compose；翻译字幕也须按目标轨道编排。

```powershell
& $entry voice list
& $entry voice synthesize --project $aekProject --voice zf_001 --input "E:/media/narration.txt" --device auto --asset-id asset_voice
& $entry translate subtitles --project $aekProject --from zh-Hans --to en --input "E:/media/captions.srt" --output exports/bilingual.srt --mode bilingual --device auto
& $entry timeline compose --project $aekProject --input "E:/video-work/voice-changes.json"
```

6. 验证、预览、渲染并检查实际成片，再导出可编辑工程包。导入使用新的目标目录；重新渲染后分别检查画面、完整音轨、时钟及配方。JSON的ok／status／errors／warnings／artifacts与进程退出码需要同时检查，质量检查不能代替完整播放及听审。

```powershell
& $entry validate --project $aekProject
& $entry preview frame --project $aekProject --frame 0
& $entry render --project $aekProject --output "$aekProject/renders/ad.mp4"
& $entry quality check --project $aekProject --input "$aekProject/renders/ad.mp4"
& $entry convert export --project $aekProject --target-format package --output "$aekProject/exports/ad.aevpkg.zip"
& $entry convert import --input "$aekProject/exports/ad.aevpkg.zip" --output "E:/video-work/restored-ad"
& $entry render --project "E:/video-work/restored-ad" --output "E:/video-work/restored-ad/renders/replay.mp4"
& $entry rights check --project $aekProject
```

神经音乐是额外能力，需要显式登记已有本地适配器、原生运行库和权重；上述四包不能替代音乐模型。先阅读[神经音乐说明](../../../skills/agent-ffmpeg-local-editor/references/neural-music.md)。普通谱面合成、循环修复和神经生曲的含义不同。

```powershell
& $entry music generate --help
& $entry delivery --help
```

[Skill详情与17模块](../../../skills/agent-ffmpeg-local-editor/SKILL.md) · [滤镜客户选型](../../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [配音／翻译／音频](../../../skills/agent-ffmpeg-local-editor/references/community-materials.md) · [升级、恢复及回滚](../../product/DELIVERY_CONTROLLER.md)

发布成片前补充素材／模型／声音用途的权利证据，并执行rights check。render的--publish仅执行本地权利门禁，不上传平台。模型生成内容仍须逐项审查；本包不附未审核模型音频。同机新目录验收不等于干净主机或跨机器通过，完整剪映等价及原G01—G38条件继续开放。

`v0.1.0-alpha.4-local.64` / CLI`0.1.66`
