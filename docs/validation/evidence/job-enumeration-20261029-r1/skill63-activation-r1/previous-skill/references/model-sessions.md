# Explicit native GPU model sessions

Use for multiple video generations with one already registered local VACE
adapter and the same positive/negative prompt plus `prompt-max-tokens`.
This extends the existing video-generation workflow; it is not another Skill.

Call the pinned installed launcher from [runtime](runtime.md). No new model
download or environment installation is needed. Native Windows only.

```powershell
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
} finally {
  $modelState = & $avk media model-session status --project $avkProject --session-id $modelSessionId |
    ConvertFrom-Json
  if ($modelState.data.live) {
    & $avk media model-session stop --project $avkProject --session-id $modelSessionId
  }
}
```

For image/last/first-last modes, pass the same explicit image IDs, fit and
timeline options documented in [video generation](video-generation.md).
Seeds, steps, guidance, flow shift, raster, frame count and endpoint conditions
may change; scheduler, overlap context and job metrics reset every time.
Changing either prompt or token budget is rejected before asset publication;
stop/start a new session for a new prompt. Sessions execute one leased job at
a time and reject concurrent or foreign adapter/project requests.

`start` hashes all weights and runtime implementation files under native
Windows locks. A ready session has verified bytes but has not loaded the GPU
model yet. First generation loads it; later generations reuse CUDA weights
and CPU prompt embeddings. Authenticated local named pipes transfer JSON and
raw frames, never pickle or TCP. The client acquires overlapping deny-write
locks before adopting the session's verified digests. An old receipt on disk
cannot substitute for a live authenticated session.

`status` reports live process state, loaded flag, successful inference count,
adapter pin and budgets. `stop` waits for the owned process to exit. Idle,
lifetime, job count and active deadline limits release the process; cancel,
owner disconnect or inference failure retire it. Do not reuse that UUID after
retirement. Keep completed assets; retry unfinished work with a new asset ID
and a new session. Do not kill other users' GPU processes to admit this model.

Do not interpret resident speed as first-use latency or a guarantee of natural
motion, prompt fidelity, output rights, total RAM/VRAM reservation, multi-GPU
scheduling or CapCut equivalence. Generated assets remain silent 8-bit SDR with
unverified/internal rights until reviewed. Preserve all generation/progress,
RGBA roundtrip, endpoint, timing and failure receipts.

Current implementation and measured case:
[MODEL_SESSIONS.md](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/MODEL_SESSIONS.md).
