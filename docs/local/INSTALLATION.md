# 本地发行包与 17 个 Agent Skills / Local installation

当前安装：**v0.1.0-alpha.3 / CLI 0.1.2 / catalog 2.0.0 / 500 looks**。日期：2026-10-24。

已从校验后的分卷合成 ZIP，在 E 盘离线安装并激活，17 个 `$agent-ffmpeg-local-` Skill 已绑定新 manifest；保留旧 alpha.1 / alpha.2 安装和不可变包。
Native Windows installation, no container/WSL/virtual environment or global site-packages modification. Existing CPython 3.13 and FFmpeg/ffprobe required.

| Item | Path/value |
|---|---|
| Installed app | `E:\dev\sandbox\AI广告剪辑\local\agent-ffmpeg\v0.1.0-alpha.3\installed` |
| Installed size, including current runtime files | 438,441,943 bytes |
| Runtime config | `local/agent-ffmpeg/runtime.json` |
| Main Skill | `$agent-ffmpeg-local-editor` |
| Editable Skills | `skills/agent-ffmpeg-local-*/` on E: |
| Discovery | `C:/Users/carzy/.codex/skills/` directory junctions to E: |
| Registration manifest | [agent-ffmpeg-local-install-manifest.json](../../agent-ffmpeg-local-install-manifest.json) |
| Full local ZIP | `E:\dev\sandbox\AI广告剪辑\product\.runtime\look500-release-20261024\reassembled\agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip` |
| Download parts | [alpha.3 artifacts](../releases/v0.1.0-alpha.3/artifacts) |
| ZIP SHA-256 | `1a967e4def2afc14e9f110c6cad90e172ff457a77ef405cb83932f1f1187b968` |
| Bundle manifest | `sha256:3bc0a74144953b97a769db01f3d2d863889da80f010d78ab7e4a2b4eedf1ceea` |

[500 names and actual effects](LOOK_PRESETS.md) · [Filter workflow](FILTERS.md) · [Assembly/installation](../releases/v0.1.0-alpha.3/USAGE.md) · [Installation receipt](../validation/evidence/look500-20261024-r1/install/installation.json) · [17 formats and actual launcher calls](../validation/evidence/look500-20261024-r1/skills/verification.json).

Per-resource licenses: 100 MIT, 267 CC-BY-SA-4.0, 133 CC0-1.0. See the individual inspect response and project-local evidence. Suggested scenes/intensity are not natural-footage acceptance.

## 直接使用 / Use now

在 Codex 下一条消息中调用 / Invoke on the next Codex turn:

```text
$agent-ffmpeg-local-editor 使用我提供的本地素材制作一条 15 秒竖屏广告，
先给出可编辑时间线和预览帧，再渲染并检查成片。
```

原生 PowerShell 入口 / Native PowerShell entry:

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk capabilities
& $avk schema show
& $avk render --help
```

若当前 PowerShell 执行策略阻止 `.ps1`，可仅为该次子进程指定 / If script execution is blocked, use a process-scoped option:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $avk doctor
```

启动器从实际 Skill 联接定位 E 盘项目，读取运行绑定，核对版本、安装回执及 `run.py` 哈希，以 `-I -S -B -X utf8` 调用安装版。源码入口 `ai-ad-editor.ps1` 仅用于开发。缺失安装、版本不匹配或启动文件变化均返回失败，不静默切换源码。
The launcher resolves the junction, checks the runtime pin/receipt and launcher digest, then executes the installed app with isolated Python flags. Missing or mismatched installations fail explicitly. This startup check does not rehash every installed dependency on every call; the offline installer checks the wheel inventory.

### 新工程闭环 / New project workflow

以下素材与编辑 JSON 须事先存在；从导入响应取得真实 `asset_id`，不要照抄案例里的随机 ID。
Supply actual media and edit JSON; use the real asset ID returned by ingest.

```powershell
$avkProject = 'E:/dev/sandbox/AI广告剪辑/workspace/my-ad'
& $avk project init $avkProject --name 'My ad'
& $avk media ingest --project $avkProject --input 'E:/media/product.mp4'
& $avk timeline compose --project $avkProject --input 'E:/media/changes.json'
& $avk validate --project $avkProject
& $avk preview frame --project $avkProject --frame 0
& $avk render --project $avkProject --output "$avkProject/renders/ad.mp4"
& $avk quality check --project $avkProject --input "$avkProject/renders/ad.mp4"
```

Agent 同时检查退出码、`ok`、`status`、`errors`、`warnings` 与 `artifacts`。音轨须显式编排。`render --publish` 只做本地权利门禁，不上传平台。完整参数和两条渲染路径的边界见[发行版使用手册](../releases/v0.1.0-alpha.3/USAGE.md)；新命名空间以本页及当前 Skill 正文为准。
Check exit codes and all structured result fields. Author audio explicitly. `--publish` gates local rights without uploading. Consult the release manual for command/renderer contracts, applying the new Skill names below.

## 17 个入口 / Skill catalog

| # | 新调用名 / New invocation | 用途 / Purpose | 旧名后缀 / Legacy suffix |
|---|---|---|---|
| 1 | [`$agent-ffmpeg-local-editor`](../../skills/agent-ffmpeg-local-editor/SKILL.md) | 项目与交付 / Editing and delivery | `agent-editor` |
| 2 | [`$agent-ffmpeg-local-timeline`](../../skills/agent-ffmpeg-local-timeline/SKILL.md) | 时间线、关键帧与运镜 / Timeline and keyframes | `timeline` |
| 3 | [`$agent-ffmpeg-local-quality`](../../skills/agent-ffmpeg-local-quality/SKILL.md) | 成片与证据 / Quality and evidence | `quality` |
| 4 | [`$agent-ffmpeg-local-project-ops`](../../skills/agent-ffmpeg-local-project-ops/SKILL.md) | 快照、恢复与队列 / Snapshots and queues | `project-ops` |
| 5 | [`$agent-ffmpeg-local-local-policy`](../../skills/agent-ffmpeg-local-local-policy/SKILL.md) | 本地运行规则 / Local policy | `local-policy` |
| 6 | [`$agent-ffmpeg-local-rights-ledger`](../../skills/agent-ffmpeg-local-rights-ledger/SKILL.md) | 权利台账 / Rights Ledger | `rights-ledger` |
| 7 | [`$agent-ffmpeg-local-local-models`](../../skills/agent-ffmpeg-local-local-models/SKILL.md) | 已有离线模型 / Existing offline models | `local-models` |
| 8 | [`$agent-ffmpeg-local-video-understand`](../../skills/agent-ffmpeg-local-video-understand/SKILL.md) | 镜头、静音与帧证据 / Media analysis | `video-understand` |
| 9 | [`$agent-ffmpeg-local-template-library`](../../skills/agent-ffmpeg-local-template-library/SKILL.md) | 模板与片段组 / Templates and clip groups | `template-library` |
| 10 | [`$agent-ffmpeg-local-long-to-short`](../../skills/agent-ffmpeg-local-long-to-short/SKILL.md) | 长转短 / Long-to-short | `long-to-short` |
| 11 | [`$agent-ffmpeg-local-screen-demo`](../../skills/agent-ffmpeg-local-screen-demo/SKILL.md) | 录屏锚点与缩放 / Screen demos | `screen-demo` |
| 12 | [`$agent-ffmpeg-local-reference-remake`](../../skills/agent-ffmpeg-local-reference-remake/SKILL.md) | 结构复刻 / Reference remakes | `reference-remake` |
| 13 | [`$agent-ffmpeg-local-ffmpeg`](../../skills/agent-ffmpeg-local-ffmpeg/SKILL.md) | 原生 FFmpeg 工具 / Native FFmpeg | `ffmpeg` |
| 14 | [`$agent-ffmpeg-local-video-edit`](../../skills/agent-ffmpeg-local-video-edit/SKILL.md) | 修剪与拼接 / Trim and concatenate | `video-edit` |
| 15 | [`$agent-ffmpeg-local-ad-creative`](../../skills/agent-ffmpeg-local-ad-creative/SKILL.md) | 广告创意 / Ad creative | `ad-creative` |
| 16 | [`$agent-ffmpeg-local-video-content-strategist`](../../skills/agent-ffmpeg-local-video-content-strategist/SKILL.md) | 内容策略 / Content strategy | `video-content-strategist` |
| 17 | [`$agent-ffmpeg-local-campaign-analytics`](../../skills/agent-ffmpeg-local-campaign-analytics/SKILL.md) | 本地数据分析 / Supplied campaign data | `campaign-analytics` |

旧调用为 `$video-cut-旧名后缀`，仍保留以复现已有任务。新前缀的 `local-policy`、`local-models` 保留其领域后缀，因此名称含两次 `local`。三个营销 Skill 提供方案指导，两个通用媒体 Skill 也可直接使用已有 FFmpeg；项目命令统一用安装版。
Legacy calls remain available separately for reproducibility. Marketing Skills are advisory, and the generic media Skills can use native FFmpeg. The 17 new registrations are not 17 newly implemented rendering engines or additional bundled AI models.

新命名空间在本次 `main` 更新中提供；已公开的 `v0.1.0-alpha.1-skills.zip` 仍是当时的 17 个 `video-cut-` 入口，未覆盖发布附件。上游工作流和许可随相应新 Skill 的 `references/upstream/` 保留；[第三方通知](../releases/v0.1.0-alpha.3/THIRD_PARTY.md)继续适用。
The new namespace is supplied by this main-branch update. Published release assets retain their original legacy names and hashes. Credited upstream references and their licenses are retained.

## 重新安装与注册 / Install on another checkout

在项目根目录执行，目标和证据目录须是新路径 / Run at the repository root using fresh destinations:

```powershell
& C:/Python313/python.exe -E -B -X utf8 scripts/install_look500_release.py --activate `
  --evidence 'E:/dev/sandbox/AI广告剪辑/docs/validation/evidence/my-local-install'
& C:/Python313/python.exe -E -B -X utf8 scripts/update_agent_ffmpeg_local_skills.py
.\register-agent-ffmpeg-local-skills.ps1
```

安装脚本校验固定发行 ZIP 和 manifest，展开并调用随包原生离线安装器；不访问网络、不创建虚拟环境、不写全局依赖。注册脚本可重复运行：只复用指向同一 Skill 的联接，先检查所有冲突和正文摘要，同名无关目录保留。默认发现目录遵循 `$CODEX_HOME/skills`，未设置则为当前用户 `.codex/skills`。
Installation verifies the pinned ZIP/manifest and runs its wheel-only installer. Registration is repeatable and preserves unrelated conflicting entries. Discovery follows `CODEX_HOME`, otherwise the current user's `.codex/skills`.

移动整个项目后需重新安装运行绑定，并重新注册到当前检出。已有安装和配置不会自动覆盖；先保留工程和回执，选择新的安装目录或手工归档旧安装、`runtime.json`。不要删除源码或用户工程来修复环境；不要重新下载缺失模型作为隐式修复。
After relocation, recreate the machine-specific installation binding and registration. Existing installations/configs are preserved. Archive or select fresh destinations deliberately while keeping projects and receipts. No automatic uninstall or background downloader is provided.

## 首版历史实测 / Historical alpha.1 verification

| # | 执行内容 / Executed | 结果 / Result | 证据 / Evidence |
|---|---|---|---|
| L01 | 发行 ZIP、8 wheels、原生依赖审计 / Offline installation | 安装成功，NumPy `.pyd` 运算及 schema 审计通过 / Installed and native audit passed | [Installation](../validation/evidence/local-install-20261024-r1/installation/installation.json), [dependency audit](../validation/evidence/local-install-20261024-r1/installation/dependency-audit.json) |
| L02 | 17 Skill 格式、UI 名称、相对引用、Codex 联接 / Skill discovery | 17 项通过，旧 Skill 正文未变 / 17 validated, legacy unchanged | [Skills](../validation/evidence/local-install-20261024-r1/skills/skills.json) |
| L03 | 从 Codex 路径运行启动器 / Registered launcher | 8 次调用：7 成功、1 预期拒绝；中文空格路径成片成功 / 7 successes, 1 expected refusal | [Commands](../validation/evidence/local-install-20261024-r1/skills/commands.json), [receipt](../validation/evidence/local-install-20261024-r1/skills/verification.json) |
| L04 | 安装版案例复跑 / Fresh installed cases | 28 次调用：27 成功、1 预期拒绝，2 个成片及项目包往返 / Two renders and package round trip | [Commands](../validation/evidence/local-install-20261024-r1/cases/commands.json), [receipt](../validation/evidence/local-install-20261024-r1/cases/verification.json) |
| L05 | 原视频、输出、GIF 与静态抽帧 / Media evidence | 广告 6 秒 360×640/30fps/180 帧；变体 3 秒/90 帧 / 6 s ad and 3 s variant | [Input](../assets/local-install-20261024-r1/input.mp4), [ad](../assets/local-install-20261024-r1/field.mp4), [variant](../assets/local-install-20261024-r1/variant.mp4), [review](../validation/evidence/local-install-20261024-r1/review.json) |

![安装版真实成片 / Actual installed render](../assets/local-install-20261024-r1/field.gif)

[模板变体 GIF / Variant GIF](../assets/local-install-20261024-r1/variant.gif) · [真实 Skill 渲染响应 / Skill response](../validation/evidence/local-install-20261024-r1/skills/render.stdout.json) · [错误返回 / Refusal](../validation/evidence/local-install-20261024-r1/skills/remote-refused.stdout.json)。

从 Skill 渲染的成片与直接调用安装版的成片 SHA-256 相同：`777726f76a162af53030271d56ff1c9b8618582d79278bf67a103ee0f1f63c57`。已目检 1 秒与 4 秒的实际输出帧；解码/音轨存在性由工具检查。本轮没有连续播放或人工听审，没有新模型推理，也没有新浏览器截图或录屏。36 次命令调用和 17 项格式检查不计为新增完整回归，也不证明全套 Skill 的 Agent 决策质量或剪映等价。
The registered launcher produces byte-identical media to the direct installed run. Frames at 1 s and 4 s were reviewed; decode/audio-presence checks were automatic. No continuous playback, human listening, new model inference or new browser recording was performed. These checks are separate from the historical full suite and do not establish full CapCut parity or every Skill's reasoning quality.

初轮启动器冒烟发现 Windows 隐藏子进程没有转发 JSON；已显式继承 stdout/stderr，随后 8 次正式调用均返回实际 JSON。
An initial smoke check caught missing JSON forwarding from a hidden Windows child process; explicit stdout/stderr handles fixed it before the eight recorded launcher checks.

复现命令见 [安装脚本](../../scripts/install_look_release.py)、[案例脚本](../../scripts/first_release_cases.py)与 [Skill 核验脚本](../../scripts/verify_agent_ffmpeg_local.py)。案例脚本的三个输出目录必须全新，核验脚本的 `--cases` 指向成功案例目录；原始失败、回执和媒体均保留。
Use fresh output/evidence/asset directories when reproducing cases; pass the successful case directory as `--cases` to the Skill verifier. Preserve previous runs and artifacts.
