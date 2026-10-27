# CLI 0.1.41 / alpha.4-local.39 — local neural lip sync

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

This is a versioned **local installation**, separate from the immutable public
`v0.1.0-alpha.3` / CLI 0.1.2 assets. It adds actual MuseTalk 1.5 audio-driven face
lip sync to the existing native FFmpeg editor. It does not close the full
CapCut-equivalent goal or replace the existing 500 looks, editing/HDR/effect,
voice, translation, search and project workflows.

The offline application archive is already built at:

```text
E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.39/candidate-r1/bundle.zip
bytes: 302911550
SHA-256: 088f532524f56b700e8b40780c809a1e90525a842c2402c355bf9825f7a0292f
manifest SHA-256: d9eadc513068d476aa563221b6f0b245ae113321ea32ca73d83c90021ff67bef
```

Installed at `local/agent-ffmpeg/v0.1.0-alpha.4-local.39/final-r1/installed/`.
All **248 product Python files** match the current source byte for byte.
The matching Skill kit is `agent-editor-kit-community-unified-skill-r42.zip`:
**one public Skill / 17 internal modules**. The native model runtime, model
weights, driver/CUDA, Python and FFmpeg remain separate explicit dependencies;
this application archive does not silently download or install any of them.

Use [the installation and activation flow](../product/COMMUNITY_LOCAL_DELIVERY.md)
and [the exact lip-sync workflow](../product/LIP_SYNC.md). The already registered
entry remains `$agent-ffmpeg-local-editor`; no separate lip-sync Skill is needed.

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk lipsync adapter --help
& $avk lipsync generate --help
```

Register local MuseTalk safetensors and native CUDA Python, ingest a portrait or
video and speech separately, author a face/chin box, inspect a dry-run, generate,
review visual output and complete audio, then validate/render/export normally.
Use new asset IDs for recipe reruns. The output retains all decoded selected
PCM samples and all source alpha; the selected face region receives semantic
neural mouth patches. Both video/audio clips remain ordinary linked edits.

The model operates at 25 fps with a trained 256×256 face raster. Tail silence is
under 40 ms; existing source motion is retained. CPU IO/blending and actual CUDA
Whisper/UNet/VAE/BiSeNet execution are distinguished in receipts. Input must be
8-bit SDR with explicit unrotated square geometry; HDR/ICC need preprocessing.
Full-body generation, automatic face tracking, naturalness/identity/perceptual
sync acceptance, clean-host installation and complete product parity remain open.

See [C51 and actual media](../product/CASES.md#c51-native-lip-sync),
[current evidence](../validation/evidence/native-lipsync-20261027-r1),
[28 source tests](../validation/evidence/native-lipsync-20261027-r1/source-lipsync-r3/verification.json)
and [byte-verified offline build/install](../validation/evidence/native-lipsync-20261027-r1/installation-final-r1/verification.json).
Failed earlier development/acquisition attempts are retained separately.
