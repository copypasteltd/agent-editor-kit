# 本机 GPU 扩展离线包与安装 / Native GPU extension delivery

[使用手册](COMMUNITY_MATERIALS.md) · [繁體中文](COMMUNITY_MATERIALS.zh-TW.md) · [English](COMMUNITY_MATERIALS.en.md)

当前本机版本是 **`v0.1.0-alpha.4-local.11` / CLI 0.1.13**，正式安装在 `E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.11/final-r1/installed/`。这是本地构建和验收记录；公开 GitHub Release 仍是 alpha.3 / CLI 0.1.2，原附件、标签和摘要不覆盖。

The current build is installed locally. Public alpha.3 downloads remain unchanged and do not contain the new voice, translation, material or GPU commands. The updated Skill kit must be paired with this matching local runtime bundle.

本轮增加完整性读取的超时/取消与部分摘要丢弃，保留[语义任务恢复](SEMANTIC_JOB_RECOVERY.md)，保留[语义工程包迁移](SEMANTIC_PROJECT_PACKAGE.md)，保留[显式条件与设备绑定的经验校准拒识](SEMANTIC_RETRIEVAL.md)，保留[字幕翻译配音联合流程](SUBTITLE_DUBBING.md)，保留[CTC 词活动边界](CTC_ACTIVITY_ALIGNMENT.md)，保留[原生任务恢复](JOB_RECOVERY.md)，保留[独立四轨分离](FOUR_STEM_SEPARATION.md)、[原生采集](NATIVE_CAPTURE.md)及精确声道关系修复。前一版本 `v0.1.0-alpha.4-local.1` 的 ZIP 与 SHA-256 `cf4e55f410582547d7fe56549d4594b4d8f0ee6aff8be24f77408c035fd74ead` 保留，旧 r2 kit 继续匹配旧包。

## 本机文件 / Local files

所有路径均位于 `E:/dev/sandbox/AI广告剪辑/` 下。

| 内容 / Item | 路径 / Path | 校验 / Verification |
|---|---|---|
| 编译好的基础运行 ZIP / Application bundle | `local/agent-ffmpeg/v0.1.0-alpha.4-local.11/candidate-r1/bundle.zip` | SHA-256 `ec2edda498a297eb04cc205f929abedfa395ad96eb83710ca5f53cd211cfecd1` |
| 运行包清单 / Bundle manifest | ZIP 内 / inside ZIP: `manifest.json` | `sha256:37b8cd1ab04ff5d00d0c68d74cdbf98bacaa9e2d042da8e2d61ea6d657391488` |
| 单入口 Skill kit / Single-entry kit | `docs/skills/agent-editor-kit-community-unified-skill-r12.zip` | [独立包摘要 / Package digest](../skills/community-unified-skill-package-0.1.13.json) |
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
$aekArchive = Join-Path $aekSource 'local/agent-ffmpeg/v0.1.0-alpha.4-local.11/candidate-r1/bundle.zip'
$aekExpectedZip = 'ec2edda498a297eb04cc205f929abedfa395ad96eb83710ca5f53cd211cfecd1'
if ((Get-FileHash -LiteralPath $aekArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $aekExpectedZip) { throw 'Application archive hash mismatch' }
Expand-Archive -LiteralPath (Join-Path $aekSource 'docs/skills/agent-editor-kit-community-unified-skill-r12.zip') -DestinationPath $aekHome
Expand-Archive -LiteralPath $aekArchive -DestinationPath (Join-Path $aekHome 'bundle')
Set-Location $aekHome
& $aekPython -I -B -X utf8 ./bundle/install.py --bundle ./bundle --target ./local/agent-ffmpeg/installed --manifest-sha256 'sha256:37b8cd1ab04ff5d00d0c68d74cdbf98bacaa9e2d042da8e2d61ea6d657391488' --timeout-seconds 600
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
CLI 0.1.5 开始交付该检索功能；对应旧包与[当时安装记录](../validation/evidence/semantic-20261025-r1/installation/verification.json)保留。
CLI 0.1.7 当时的基础 ZIP 为 302,628,548 字节；8 wheel、清单登记 47 文件，连同 manifest.json 共 48 个 ZIP 文件；产品 wheel 为 0.1.7。
194 个产品 Python 文件与安装版逐字节相同；[本次安装审计](../validation/evidence/job-recovery-20261025-r1/installation/verification.json)。
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


## CLI 0.1.6 独立四轨 / Independent four-source separation

[登记、设备选择、信号契约与完整命令](FOUR_STEM_SEPARATION.md) · [真实 CPU/GPU、安装版与 Skill 实测](../validation/独立四轨音源分离实测_2026-10-25.md)。
`audio separate-stems` 保存 drums/bass/other/vocals 四个独立模型预测，`--apply` 新建四条可编辑音轨；
auto 优先 NVIDIA，严格 CUDA 和 CPU 路径分别返回实际设备。新的音频 adapter 明确使用
`torchaudio-hdemucs-four-stem-local-v1`；不能将既有双轨 adapter 当成四轨 adapter。

该功能需另供原生 Python/Torch/TorchAudio/NumPy 与兼容 checkpoint，**不在上述四个 Kokoro/OPUS 模型包内**。
本机实验权重权利仍为 unverified，不随包再分发；基本 ZIP 与小型 Skill kit 均不含 Torch 或四轨权重。
受控样例通过不等于自然音乐/去混响/人工听感已经验收。

### 升级时重新固定路径 / Explicit upgrade pins

旧 local.3 / CLI 0.1.5 的 ZIP SHA-256 为 `804cac8e45d62b4440fb39423126a86d650e415e37ed3f9b7db724b65a2a62cd`，
manifest `sha256:29583211d5cf376f51c295b419ba7bdaaf9f46fa5314820fcc6e180f47a4f95f`；
[r4 kit](../skills/agent-editor-kit-community-unified-skill-r4.zip) 与旧包继续保留。
升级请选择新目录，核对实际 version/manifest 后显式激活。模型 adapter 和检索索引固定实现的绝对路径及摘要；
换安装路径后需要明确重登记相应 adapter，语义索引按其绑定实现重新建立/验证，不能默认复用旧 pin 或修改旧证据。
原始素材、旧安装和工程快照保留；尚未完成另一台干净物理主机的升级/回滚验收。

The new runtime preserves historical bundles. Register model adapters explicitly against the actual installed implementation;
rebuild/verify path-pinned semantic indexes when the implementation installation changes. No silent source fallback,
model download or adapter migration is performed. Independent four-source weights/native dependencies remain separate,
and clean-host upgrade/rollback acceptance is open.

## CLI 0.1.7 原生中断恢复 / Native interruption recovery

[完整使用与保留规则](JOB_RECOVERY.md) · [真实故障注入、回归与成片](../validation/任务中断恢复实测_2026-10-25.md)。
新四轨任务持久化工作目录和输出意图，正常提交/回滚后清理；强制结束后先预览再执行
`project recover --cleanup-jobs`。默认 `project recover` 仍只恢复元数据。此功能不删除旧非管理缓存，
不提供模型断点续算，也不代表完整 G33 已关闭。

旧 local.4 / CLI 0.1.6：`local/agent-ffmpeg/v0.1.0-alpha.4-local.4/candidate-r1/bundle.zip`，
SHA-256 `10ec4f490186f3f0c34ae52921aec0e8fd76e302d89252449b4e1651b68ecc71`，
manifest `sha256:8206db8867a0d0908153cfa00f425c469909fb07545102ec59dcdc8e007b5ba9`，
[r5 kit](../skills/agent-editor-kit-community-unified-skill-r5.zip) 仍匹配旧包；历史核验原样保留。
四轨完整性固定项由 8 个实现文件增为 12 个（加模型/Python/证据共 15 项），请明确重新登记 adapter。

The historical r6 kit contains one Skill and 17 internal modules, with a recovery reference and this matching
runtime pin. Native lifetime tests, real installed hard-stop boundaries, normal CPU/GPU inference and
editable delivery are recorded separately. Older unmanaged caches and historical evidence remain intact.


## CLI 0.1.8 词活动边界 / CTC word-boundary extension

[完整使用流程与限制](CTC_ACTIVITY_ALIGNMENT.md)。显式 `--boundary-mode activity` 使用同一 PCM，
保留原 CTC 字符/词时间，控制器独立重算区间与决定。默认 `ctc` 语义保持。
这是另行登记的已有原生 Torch/Transformers 与 Wav2Vec2ForCTC safetensors，
**不在基础 ZIP 或四个 Kokoro/OPUS 包内**。CPU/CUDA 显式选择，不隐式下载或回退。
受控词块精度改善不代表自然连续语音、中文、歌词或重叠声音验收完成。

CLI 0.1.8 历史包实际 8 wheel / 195 个产品 Python 文件，全部与源码逐字节一致：
[固定安装审计](../validation/evidence/ctc-activity-20261025-r1/installation/verification.json)。
未完成另一台干净原生主机安装；未新建公开 Release。
开发 candidate-r1 属于 v2 失败候选，保留且未激活；该历史交付匹配 local.6/candidate-r2 的 v3 摘要；本页上表现已指向条件检索 local.8 的新摘要。

历史 local.5 / CLI 0.1.7 与 r6 kit 保留：
ZIP SHA-256 `12f0d076f1b0dd18f7438adf678a99354a0ce6fa1b10843f326ebc2a8d8251da`，
manifest `sha256:ae4daffd658d326df75d1b8c0540a3f193800f03528d0d38883a0767f73fa5a0`；
[r6 kit](../skills/agent-editor-kit-community-unified-skill-r6.zip) 与其固定的旧安装仍可复现，未被覆盖。


## CLI 0.1.9 历史字幕翻译配音联合流程 / Joint subtitle dubbing

[完整使用流程](SUBTITLE_DUBBING.md) · [实际 CPU/GPU/Skill、故障与成片](../validation/字幕翻译配音联合流程实测_2026-10-25.md)。
复用上表四个既有模型包，不新增下载；一次 voice batch 初始化一次 Kokoro。
按实际完整 WAV 检查原 cue 时窗，明确目标 audio/subtitle 轨道后原子应用；超窗拒绝或显式完整再生成。
普通 SRT / 中英；语义、自然听感、精确字词和口型仍未验收，实际不自然译文保留。

该历史版本 ZIP 302,645,253 bytes，8 wheel；manifest 登记 47 文件，含自身共 48 ZIP 文件。
该版本当时 197 个产品 Python 文件等于最终源码：[新安装审计](../validation/evidence/subtitle-dubbing-20261025-r1/installation-r2/verification.json)。
最终安装版 27 项新专项和 122 项 CLI 回归通过；新 r8 kit 仍是一个入口/17 内部模块。
不代表干净主机验收，不覆盖旧公开 Release。

旧 local.6 / CLI 0.1.8 和 r7 kit 保留：
ZIP SHA-256 `a5c6f773e32122347b36ba471b5f8c28fe0fe422cd20d69d4c8a6ad96202182e`，
manifest `sha256:8aae41452002706b2c74398c1e58fc7c16db458932e62f3e3614b57248d7994a`；
[r7 kit](../skills/agent-editor-kit-community-unified-skill-r7.zip) 与旧运行 pin 不改。
本批 local.7/candidate-r1 的模型字典处理错误已留档，未激活；该历史安装只使用 local.7/candidate-r2 摘要；上表现已指向 local.8/candidate-r1。


## CLI 0.1.12 历史语义任务恢复 / Managed semantic recovery

302663151 bytes、202 个产品 Python 文件；[完整实测](../validation/语义任务中断恢复实测_2026-10-25.md)。
7 类真实故障/清理核验；1 秒超时存在同步校验延后，未关闭完整 G32/G33。旧 local.9/r10 和全部历史证据保留。

## CLI 0.1.11 语义工程包迁移 / Semantic project-package migration

应用 ZIP 302,659,130 bytes，200 产品 Python 文件；[安装收据](../validation/evidence/semantic-package-20261025-r1/installation-r1/verification.json)。
[使用流程](SEMANTIC_PROJECT_PACKAGE.md) · [完整实际核验](../validation/语义工程包迁移实测_2026-10-25.md)。
CPU/CUDA/统一 Skill 各 80 条迁移后查询保持原决策；两条误接受和一条钟表误拒仍在。
外部模型、原生运行时和安装实现 pin 保留；不是干净主机交付或全部 G31 关闭。
旧 local.8 / CLI 0.1.10、r9 kit 与 C19 原错误保留；下节是当时历史实测。

## CLI 0.1.10 条件检索与经验拒识 / Explicit clauses and calibrated decisions

[完整操作流程](SEMANTIC_RETRIEVAL.md) · [实际模型/失败/安装/Skill/案例](../validation/语义条件与校准拒识实测_2026-10-25.md)。

新运行 ZIP 302,655,012 bytes；199 个产品 Python 文件与源码逐字节一致，
[独立安装收据](../validation/evidence/semantic-decision-20261025-r1/installation-r1/verification.json)。
最终源码和安装版检索专项分别 48/48；安装版完整 CLI 122/122、0 skip。
原始整句排名继续用 `--query-mode raw` 复现，默认条件查询配合索引/类型/实际设备绑定的
经验校准档案。该档案不证明通用拒识、自然动作/身份/音频推荐或完整 G26 关闭。

CLI 0.1.10 当时已实测的迁移缺口：新检索/校准工程 export/import/通用 validate 成功后，search dry-run
报 `SEMANTIC_INDEX_INVALID` / `Manifest outside project semantic asset tree`。
[C19 原错误与复现包](../assets/semantic-decision-20261025-r1/demo-installed-r1/KNOWN_ISSUE.md)保留；
普通卡片工程的 360 帧往返通过不代替索引/档案可搬迁或干净主机验收。

Torch/Transformers 与 SigLIP2 权重仍为另行登记的既有本地依赖，不在本应用 ZIP 或四个
Kokoro/OPUS 包内。更换语义实现或其绝对位置后须明确重新登记并重建索引/档案，不能
手改原 pin。单一注册 Skill 和内部模块数保持 1/17；公开旧 Release 不覆盖。

历史 local.7 / CLI 0.1.9 与 r8 kit 保留：ZIP SHA-256
`d085f6109a73d0e92ce9f160c1dab68925c21a5775a9d8ec7d8a710e14cc456d`，
manifest `sha256:0a79580cc12c1ec813404f3838fa2f17dc0c8d4a67678e4b25fba88d870facfe`；
[r8 kit](../skills/agent-editor-kit-community-unified-skill-r8.zip) 与其旧 pin 不改。

## CLI 0.1.13 当前交付 / Current delivery

302664913 bytes、203 个产品 Python 文件；[读取超时/取消实际核验](../validation/完整性校验超时取消实测_2026-10-25.md)。旧 local.10/r11 与原收据保留。CPU/CUDA 和统一入口验证按本批收据记录；模型仍逐命令加载，完整 G32/G33 未关闭。
