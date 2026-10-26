# 原生 GPU 模型会话 / Native GPU model sessions

CLI **0.1.34 / alpha.4-local.32** 在已有 `media generate` 上增加显式模型会话。适用于同一工程、同一 VACE 适配器、同一正负提示词下连续生成多个镜头或多个 seed 方案。它复用 CUDA 视频权重与提示词嵌入，省去每条命令反复读取大模型和重新加载文字编码器的成本。

新增原生 GPU 模型会话：显式启动、查询、停止，连续生成复用权重和同一提示词嵌入；每个任务重置调度器、前窗上下文与统计。实际同机首条生成 654.27 秒，后两条 35.46/28.48 秒；会话全模型校验另计 480.42 秒。相同 seed 的 17 帧逐像素相同，实际去噪取消可回滚并退出所属进程。

[完整实测、失败与资源证据](../validation/原生GPU模型常驻实测_2026-10-27.md)。

## 使用流程

使用已注册的唯一 `$agent-ffmpeg-local-editor` 入口。先准备工程、已登记适配器和原文提示词；需要图生模式时先导入图片，使用 CLI 返回的 asset ID。基础包不包含 VACE 权重或原生 Torch/Diffusers 环境，继续使用已有本地登记。

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk media model-session start --help

$sessionStart = & $avk media model-session start --project $avkProject `
  --adapter-id $vaceAdapterId --idle-seconds 300 --lifetime-seconds 14400 --max-jobs 32 |
  ConvertFrom-Json
if (-not $sessionStart.ok) { throw 'Model session failed to start' }
$modelSessionId = $sessionStart.data.session_id
try {
  & $avk media generate --project $avkProject --adapter-id $vaceAdapterId `
    --model-session $modelSessionId --asset-id generated-01 --mode text-to-video `
    --prompt $reviewedPrompt --seed 240 --width 256 --height 144 --frames 17 --fps 12
  if ($LASTEXITCODE -ne 0) { throw 'Generation failed' }
  & $avk media generate --project $avkProject --adapter-id $vaceAdapterId `
    --model-session $modelSessionId --asset-id generated-02 --mode text-to-video `
    --prompt $reviewedPrompt --seed 241 --width 256 --height 144 --frames 17 --fps 12
  if ($LASTEXITCODE -ne 0) { throw 'Generation failed' }
  & $avk validate --project $avkProject
} finally {
  $modelState = & $avk media model-session status --project $avkProject --session-id $modelSessionId |
    ConvertFrom-Json
  if ($modelState.data.live) {
    & $avk media model-session stop --project $avkProject --session-id $modelSessionId
  }
}
```

`$avkProject`、`$vaceAdapterId` 和 `$reviewedPrompt` 须填实际工程路径、登记 ID 和确认后的提示词。需要可编辑入轨时，另加 `--apply --track-id track_video_1 --timeline-start-seconds ...`，按实际有理帧时钟安排起点，避免覆盖。首图、尾图、双端图仍使用原有 `--mode`、asset ID 和 `--image-fit`；会话不改变端点合成与独立核验方式。

开始会话不等于模型已经装入 GPU。`start` 完成全模型摘要、代码/可执行文件核验并持有文件锁，`model_loaded` 为 false；第一条真正生成才加载文字编码器、计算嵌入、释放文字编码器并加载视频权重。后续生成保留视频权重和一组嵌入。启动、首条加载、推理、编码与整条 CLI 的耗时分别记录，不能把热复用耗时当作首次使用耗时。

## 支持范围

| 项目 | 当前行为 |
|---|---|
| 工程与适配器 | 会话仅接受创建它的工程和完整适配器摘要；模型/运行代码改变须重新登记和新建会话。 |
| 提示词 | 固定正提示、负提示和 `prompt-max-tokens`；任一变化返回 `MODEL_SESSION_PROMPT_MISMATCH`，不会发布新资产。 |
| 可变参数 | seed、采样步数、guidance、conditioning、flow shift、输出尺寸、帧数、图生条件和模式可变，仍受原有数组与视频预算约束。 |
| 每任务重置 | 新建 scheduler，清空前窗生成上下文、输入 trace 和窗口统计；只有权重与提示嵌入持续存在。 |
| 并发 | 同一会话只接受一个租约；其他请求返回 `MODEL_SESSION_BUSY`，不会中断原任务。 |
| 保留与失败 | 成功视频和编辑工程保留；取消、所有者断连、任务超时或推理失败会退出该会话，后续需新建。 |
| 停止 | `media model-session stop` 等待所属进程退出；操作系统释放该进程的 CUDA 上下文和文件句柄，不处理其他 GPU 进程。 |
| 平台 | 原生 Windows 命名管道与 CUDA/BF16；本轮不使用 Docker、WSL、虚拟环境或新模型下载。 |

## 资源预算与状态

| 参数 | 默认 | 接受范围 / 作用 |
|---|---:|---|
| `--startup-timeout-seconds` | 1800 | 1–3600 秒；包含会话完整性核验。失败会停止本次自己创建的进程并保存启动失败记录。 |
| `--idle-seconds` | 300 | 10–3600 秒；无租约空闲达到预算后退出。 |
| `--lifetime-seconds` | 14400 | 60–86400 秒；ready 后整体生命周期上限，达到后退出，可能中断在执行任务。 |
| `--max-jobs` | 32 | 1–1024；最后一条成功任务完成事务后退出。 |
| 生成 `--timeout-seconds` | 3600 | 会话租约从 acquire 起计时；与生成管道内部剩余时间预算共同生效，不能延长外层期限。 |

`status` 返回 PID、live/status、adapter pin、model_loaded、完成和失败推理数、租约/执行状态及预算。已退出的会话返回 `live: false` 和留存的停止原因；磁盘历史状态不会伪装成活进程。历史私有文件位于工程 `cache/model-sessions/<UUID>/`，不进入可编辑工程包。`private.json` 包含本地认证密钥，不应复制到公开证据或客户交付。

现有 CUDA 准入仍按实际设备 UUID、Torch/整卡空闲量和每窗口预留空间检查，不提供显存预留或 OOM 保证。空闲缓存释放仅作用于当前进程，常驻参数仍保留。跨厂商、多 GPU、总进程树 RAM/VRAM/磁盘硬配额和全局调度继续开放。

## 完整性与传输

驻留进程在 ready 前完整哈希全部模型、解释器、证据和实现文件，并用 Windows 只共享读取的句柄持续拒绝写入和删除。控制器通过经过认证的本地命名管道领取租约和文件身份/摘要证明，在驻留锁仍生效时接续自己的拒写锁；身份、尺寸、摘要或适配器清单不一致立即拒绝。只有此次活连接的证明可用，旧磁盘回执不能跳过校验。

控制消息使用有界 JSON，帧使用有界原始字节块；不反序列化 pickle、不开放 TCP、不执行远程代码。每条任务仍验证源/掩码、采样、模型执行统计、无网络行为、完整 RGBA 编码往返和明确条件端点；保持既有权利依赖、快照、受管工作区和事务发布。网络限制为现有 Python 审计保护，不能作为操作系统沙箱承诺。

## 质量与交付

这是生成速度和资源生命周期的实现。自然提示遵循、身份、镜头运动、窗口接缝及模型/输出版权仍需独立审查；条件端点精确保留不能证明中间生成质量。输出仍为无声、不透明 8-bit SDR。模型和生成资产默认 `unverified/internal`，完整剪映等价目标继续进行。

繁體中文：同一工程、適配器及提示詞可重用常駐權重與嵌入；每個任務重設 scheduler 和前窗狀態。`start` 先完成全部摘要核驗，首次生成仍需載入模型；使用完畢必須 `stop`。取消、逾時、斷連與失敗會退出該會話；更換提示詞請新建。自然品質、輸出權利、完整資源配額與剪映等價未驗收。

English: Use one explicit native Windows session per project, registered VACE adapter and prompt pair/token budget. Reuse CUDA weights and prompt embeddings; reset scheduler, previous-frame state and metrics per job. Startup verifies all model bytes; first generation still loads weights. Stop after the batch. Cancellation, deadline, owner disconnect and failure retire only the owned process. New prompts need a new session. Natural quality, output rights, complete resource quotas and CapCut equivalence remain open.

![Measured timing data only](../assets/model-session-20261027-r1/timing.png)
