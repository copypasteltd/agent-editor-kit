# 本机 GPU 扩展离线包与安装 / Native GPU extension delivery

[使用手册](COMMUNITY_MATERIALS.md) · [繁體中文](COMMUNITY_MATERIALS.zh-TW.md) · [English](COMMUNITY_MATERIALS.en.md)

当前本机版本是 **`v0.1.0-alpha.4-local.3` / CLI 0.1.5**，正式安装在 `E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.3/final/installed/`。这是本地构建和验收记录；公开 GitHub Release 仍是 alpha.3 / CLI 0.1.2，原附件、标签和摘要不覆盖。

The current build is installed locally. Public alpha.3 downloads remain unchanged and do not contain the new voice, translation, material or GPU commands. The updated Skill kit must be paired with this matching local runtime bundle.

本轮增加[原生采集](NATIVE_CAPTURE.md)及精确声道关系修复；[新安装与专项](../validation/补齐实施首批实测_2026-10-25.md)分别记录。前一版本 `v0.1.0-alpha.4-local.1` 的 ZIP 与 SHA-256 `cf4e55f410582547d7fe56549d4594b4d8f0ee6aff8be24f77408c035fd74ead` 保留，旧 r2 kit 继续匹配旧包。

## 本机文件 / Local files

所有路径均位于 `E:/dev/sandbox/AI广告剪辑/` 下。

| 内容 / Item | 路径 / Path | 校验 / Verification |
|---|---|---|
| 编译好的基础运行 ZIP / Application bundle | `local/agent-ffmpeg/v0.1.0-alpha.4-local.3/candidate-r1/bundle.zip` | SHA-256 `804cac8e45d62b4440fb39423126a86d650e415e37ed3f9b7db724b65a2a62cd` |
| 运行包清单 / Bundle manifest | ZIP 内 / inside ZIP: `manifest.json` | `sha256:29583211d5cf376f51c295b419ba7bdaaf9f46fa5314820fcc6e180f47a4f95f` |
| 单入口 Skill kit / Single-entry kit | `docs/skills/agent-editor-kit-community-unified-skill-r4.zip` | [独立包摘要 / Package digest](../skills/community-unified-skill-package-0.1.5.json) |
| 四个模型 ZIP / Four model ZIPs | `local/agent-ffmpeg/community-model-archives-r2/` | 见下表及 / see table and `archives.json` |
| 可移动模型安装 / Relocated model installation | `local/agent-ffmpeg/community-portable-r1/模型 包/` | 实际从四个 ZIP 安装；路径含中文与空格 / actually installed from all four ZIPs |
| 当前调用配置 / Runtime configuration | `local/agent-ffmpeg/runtime.json` | 固定应用摘要、原生 Python、启动器摘要 / pinned app, native Python and launcher |
| CPU/GPU 路径配置 / Device configuration | `local/agent-ffmpeg/community-runtime.json` | 按任务指定 CPU/GPU 包及已有 NVIDIA DLL 目录 / explicit per-task pack/library paths |

基础运行包含 8 个固定 wheel、500 LUT 和 359 项真实音频/字体资源；模型权重分层存放，基础运行 ZIP 不含下面四个模型包。模型 ZIP 总计约 1.05 GB，展开约 1.34 GB。GPU 外部运行库另计；安装中不在 C 盘下载模型，不创建虚拟环境。

The application contains eight pinned wheels, 500 looks and 359 actual music/jingle/SFX/font files. Model weights remain optional and separate. The four model archives total about 1.05 GB, expanding to about 1.34 GB; existing external NVIDIA runtimes are separate.

| 包 ID / Pack ID | ZIP bytes | ZIP SHA-256 | Manifest SHA-256 |
|---|---:|---|---|
| `kokoro-zh-en-int8` | 151369628 | `1b970731deea9df5194c9ea6d9c072ee074c753ba5d0ee42f266c069ad1de553` | `5df1e69b62cb023489b131b238a765fec9581afc37fb21840fd3c3f77faaa29e` |
| `opus-zh-en-cpu-int8` | 150960451 | `65d045735deccb170f12d4db0df8fa0ad79b2c88d326fc00b004393958953e58` | `95d8b0953de8fb65cc93815d646a034c9a794226aff28f76b8693bf41d04c2be` |
| `kokoro-zh-en-cuda13` | 583062292 | `87bc0691310db90a9d1cda9992d869089dfe73ea2331d988683e7457e02dfa08` | `fb46a9cfc9823f4cb18d1c669a145e2fec772e39e0e32f1a7a68eae18cc4d987` |
| `opus-zh-en-cuda12-int8` | 168635396 | `35084c7c17093f62bf0aff6479d1c67d4c11860bdae88238e89f584441c82d0f` | `eda65efa7fa83be5f1bd01dab3c5b6278aaa897cd747d82549b135f74a0838d4` |

## 从本地包安装到新目录 / Install supplied local archives

要求原生 Windows x64、已有 CPython 3.13 x64、FFmpeg/ffprobe 在 PATH。包和输出目录必须是本地路径；不使用 Docker、WSL、容器、虚拟环境、全局 pip 或隐式下载。准备好上述 ZIP 后执行；示例目录需尚不存在。`$aekSource` 按收到的本地交付位置调整。

Requires native Windows x64, existing CPython 3.13 x64 and FFmpeg/ffprobe on PATH. Supply the local archives first. Choose a new destination; no global installation or network access is used.

```powershell
$aekPython = 'C:/Python313/python.exe'
$aekSource = 'E:/dev/sandbox/AI广告剪辑'
$aekHome = 'E:/tools/agent-editor-kit-gpu'
$aekArchive = Join-Path $aekSource 'local/agent-ffmpeg/v0.1.0-alpha.4-local.3/candidate-r1/bundle.zip'
$aekExpectedZip = '804cac8e45d62b4440fb39423126a86d650e415e37ed3f9b7db724b65a2a62cd'
if ((Get-FileHash -LiteralPath $aekArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $aekExpectedZip) { throw 'Application archive hash mismatch' }
Expand-Archive -LiteralPath (Join-Path $aekSource 'docs/skills/agent-editor-kit-community-unified-skill-r4.zip') -DestinationPath $aekHome
Expand-Archive -LiteralPath $aekArchive -DestinationPath (Join-Path $aekHome 'bundle')
Set-Location $aekHome
& $aekPython -I -B -X utf8 ./bundle/install.py --bundle ./bundle --target ./local/agent-ffmpeg/installed --manifest-sha256 'sha256:29583211d5cf376f51c295b419ba7bdaaf9f46fa5314820fcc6e180f47a4f95f' --timeout-seconds 600
if ($LASTEXITCODE) { throw 'Native application installation failed' }
```

逐个安装需要的模型包；配音和翻译分别需要自己的 CPU 包，GPU 包为可选加速。下例安装全部四包，输入清单来自实际 ZIP 摘要；安装器另检查安装版 CLI 内置的模型清单 pin、ZIP 文件集和每个解压文件。它拒绝已有目标、错误摘要、额外/缺失文件和内容改动，并清理本次失败的 staging。

Install the needed CPU packs and optional CUDA packs. The following installs all four from the supplied archives, verifying both archive digests and the installed application's manifest pins.

```powershell
$aekModelArchives = Join-Path $aekSource 'local/agent-ffmpeg/community-model-archives-r2'
$aekPacks = Join-Path $aekHome 'local/agent-ffmpeg/models'
New-Item -ItemType Directory -Path $aekPacks -Force | Out-Null
$aekCatalog = Join-Path $aekHome 'local/agent-ffmpeg/installed/site/ai_ad_editor/material_data/model-packs.json'
$aekPackRows = (Get-Content -LiteralPath (Join-Path $aekModelArchives 'archives.json') -Raw -Encoding utf8 | ConvertFrom-Json).packs
foreach ($aekPack in $aekPackRows) {
    & $aekPython -I -B -X utf8 ./scripts/install_community_pack.py --archive (Join-Path $aekModelArchives ($aekPack.id + '.zip')) --sha256 $aekPack.sha256 --catalog $aekCatalog --id $aekPack.id --target (Join-Path $aekPacks $aekPack.id)
    if ($LASTEXITCODE) { throw ('Model installation failed: ' + $aekPack.id) }
}
```

将已有 NVIDIA 库路径改为本机实际位置。配音需要 CUDA 13/cuDNN 9；翻译需要 CUDA 12 cuBLAS，两者可来自不同的已安装目录。不会启动这些库所属的其他软件。无 GPU 时省略下面两个 library 参数即可保留 CPU 方案。

Use actual existing NVIDIA library directories. Voice needs CUDA 13/cuDNN 9; translation uses CUDA 12 cuBLAS. Their directories may differ. No associated server/application is started. For CPU-only operation omit the two library arguments.

```powershell
$aekVoiceCuda = 'E:/libraries/cuda13-cudnn9/bin'
$aekTranslationCuda = 'C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.4/bin'
& $aekPython -I -B -X utf8 ./scripts/activate_community_runtime.py --installed ./local/agent-ffmpeg/installed --packs $aekPacks --voice-cuda-lib $aekVoiceCuda --translation-cuda-lib $aekTranslationCuda
if ($LASTEXITCODE) { throw 'Runtime configuration failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
if ($LASTEXITCODE) { throw 'Skill registration failed; preserve an unrelated existing registration' }
$avk = Join-Path $aekHome 'skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk gpu inspect
& $avk capabilities
& $avk voice list
```

注册器只处理本项目拥有的目录联接；同名但无关的注册会保留并报错。已使用当前仓库入口时无需另注册到另一个安装目录。客户端缓存未刷新时重新打开会话，外层继续只指定 **`$agent-ffmpeg-local-editor`**。

The registrar preserves unrelated same-name registrations. Existing users may keep this repository's registration. Refresh the client/session discovery cache when necessary; use one Skill entry.

## 设备选择与许可 / Device selection and terms

- `--device auto` 默认优先可用 GPU，配音预检 3072 MiB、翻译 1536 MiB 空闲显存；返回实际设备和回退原因。
- `--device cuda` 严格使用 GPU，依赖、显存或推理失败时返回失败；`--device cpu` 强制 CPU。
- RTX 3060 已实际测试；不承诺 AMD/Intel/Apple GPU，亦不承诺单次冷启动更快。不会停止其他 GPU 任务。
- 核心、模型、素材和可选数值库分别保留许可。GPU 翻译包保留 `GPU-DEPENDENCIES.txt`、Intel OpenMP/MKL 和 oneDNN 原始许可；NVIDIA 系统库不随包再分发。独立 CPU Ruy 翻译包不含 MKL/Intel OpenMP/CUDA 后端。
- `auto` prefers an available GPU and reports fallback; `cuda` is strict; `cpu` is explicit. Optional NVIDIA/Intel terms do not replace open-source engine/model/media licenses.

## 原始核验 / Evidence

[本轮 CPU](../validation/evidence/community-materials-20261025-r1/cpu/verification.json) · [GPU](../validation/evidence/community-materials-20261025-r1/gpu/verification.json) · [可移动安装与拒绝](../validation/evidence/community-materials-20261025-r1/portable/verification.json) · [单入口实际调用](../validation/evidence/community-materials-20261025-r1/skill/verification.json) · [验收与未完成项](COMMUNITY_ACCEPTANCE.md)。

这些记录区分真实生成、解码、静态目检、连续播放和人类听审。不把三音色生成或 103 条映射当成全部音色的质量验收。


## CLI 0.1.5 离线图文语义检索 / Offline visual semantic retrieval

[完整使用流程](SEMANTIC_RETRIEVAL.md) · [本轮完整实测](../validation/离线语义检索实测_2026-10-25.md)。
新基础 ZIP 为 302,607,251 字节；8 wheel / 47 文件，产品 wheel 版本 0.1.5。
全部产品 Python 文件与安装版逐字节摘要相同；[原生安装记录](../validation/evidence/semantic-20261025-r1/installation/verification.json)。
同一 RTX 3060 主机验证 CUDA BF16 和 CPU float32。Torch/Transformers 及约 1.5GB SigLIP2 权重
单独来自既有原生环境，不在基础 ZIP 或四个配音/翻译 ZIP 内；产品不隐式安装或下载。

现有工作区的 `local/agent-ffmpeg/semantic-runtime.json` 记录本机绝对路径、模型摘要和许可依据，
`runtime.json` 的 `semantic_config` 指向该文件。Agent 对新工程仍须明确 `semantic adapter-register`。
换主机应创建包含实际 `python_executable`、`model_path`、`evidence`、`creator`、`license_spdx`、
`verification_status` 与 `format: agent-local-semantic-runtime-v1` 的本地 JSON，再传给激活脚本；
不得复制不可用的绝对路径，登记时由产品重新检查依赖和字节。

```powershell
# The JSON and all referenced native paths must already exist.
& $aekPython -I -B -X utf8 ./scripts/activate_community_runtime.py --installed ./local/agent-ffmpeg/installed --packs $aekPacks --voice-cuda-lib $aekVoiceCuda --translation-cuda-lib $aekTranslationCuda --semantic-config $aekSemanticProfile
```

This optional profile supports explicit registration; it does not activate model inference or download files.
The base archive and four speech/translation packs remain separate. Clean-host acceptance is still open.

历史 CLI 0.1.4 / local.2：
`local/agent-ffmpeg/v0.1.0-alpha.4-local.2/agent-editor-kit-v0.1.0-alpha.4-local.2-cp313-win_amd64.zip`，
SHA-256 `4e406058e082d1c9d778e9c4665f307d5027f17542c6fabfbc9d8d72ac0a2333`，
manifest `sha256:fd418d94461b57423072fb730959e36cb39264fd48a96be26dc297fe52b59897`；
[r3 kit](../skills/agent-editor-kit-community-unified-skill-r3.zip) 继续对应旧包，旧标签/附件未改。
