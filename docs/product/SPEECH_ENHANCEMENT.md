# Native CUDA speech enhancement / 本地对白增强 / 本機對白增強

CLI 0.1.43 adds actual **DeepFilterNet3** full-band speech denoising. The fixed
133-tensor FP32/I64 safetensors graph runs on the existing native CUDA Python.
The NumPy analysis/features/synthesis frontend runs on CPU; FFmpeg performs
explicit sample-rate conversion. This command installs no dependencies and
downloads no model. The one public Skill remains `$agent-ffmpeg-local-editor`.

## Use the installed release

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk audio enhancement-adapter register --help
& $avk audio enhance --help
$project = 'E:/video-work/dialogue'
& $avk project init $project
& $avk media ingest --project $project --input 'E:/media/interview.wav'
# Read data.asset.id and supply the actual source/model license evidence.
& $avk audio enhancement-adapter register --project $project `
  --adapter-id df3_local --model-path 'E:/models/deepfilternet3' `
  --executable 'D:/native-python/python.exe' --evidence 'E:/models/df3-rights.json' `
  --license-spdx 'MIT OR Apache-2.0' --creator 'DeepFilterNet contributors' `
  --threads 4 --segment-seconds 10 --overlap 0.25
& $avk audio enhancement-adapter inspect --project $project --adapter-id df3_local
& $avk audio enhance --project $project --adapter-id df3_local `
  --source-asset-id SOURCE_ID --asset-id dialogue_enhanced `
  --strength 0.85 --attenuation-limit-db 24 --dry-run
& $avk audio enhance --project $project --adapter-id df3_local `
  --source-asset-id SOURCE_ID --asset-id dialogue_enhanced `
  --strength 0.85 --attenuation-limit-db 24 --apply --track-id track_audio_1
& $avk validate --project $project
# Audition the enhanced WAV at data.asset.uri relative to the project root.
# Render MP4 only after adding an explicit video, still-image or text clip.
```

The example paths are placeholders for **existing native installations**, not
download locations or an instruction to create a virtual environment. The
verified local package and installed path are in [CLI 0.1.43 delivery](../releases/CLI_0.1.43_LOCAL.md).

An audio-only workflow delivers the enhanced WAV directly. Video rendering
requires a picture layer; the CLI correctly rejects an empty visual timeline.
[C53](CASES.md#c53-native-speech-enhancement) adds an actual waveform image as an
editable still clip before rendering and comparing the complete package roundtrip.
Project import preserves historical adapter records; it does not install their
external models or make an older implementation binding valid automatically.

## What gets preserved

- The first decoded audio stream is indexed using its real PTS and sample
  counts. Hard gaps are explicitly zero-filled; later decoded samples overwrite
  overlap intervals. This is the existing native audio interval clock, with no
  soft asynchronous time stretching.
- Selection uses nearest native samples. `--start-seconds` defaults to zero;
  an omitted end means the actual indexed end. Output has exactly the selected
  sample count at the original sample rate, with one or two original channels.
- Stereo channels are separate model batch rows. The command never collapses
  them to mono. Independent nonlinear estimates can change stereo phase/width.
- The 48 kHz model estimates speech; other sample rates explicitly resample to
  48 kHz and back. This does not reconstruct missing high-frequency information.
  Wet output for a 96 kHz source has the model's 24 kHz Nyquist limit.
- `strength` is a native-rate dry/wet mix. With attenuation limit `L`, effective
  wet is `strength * (1 - 10**(-L/20))`; omitted `L` means complete model output.
  `L=0` or `strength=0` bypasses inference/resampling and preserves every decoded
  selected Float32 bit. These controls do not guarantee a uniform spectral dB
  reduction. No automatic clipping or loudness normalization is performed.
- Complete encoded Float32 WAV samples are decoded and hashed before publication.
  The source file and any original timeline clips remain available for comparison.

## Rerun and edit

```powershell
& $avk audio enhance --project $project --adapter-id df3_local `
  --recipe-asset-id dialogue_enhanced --asset-id dialogue_gentler --strength 0.5
& $avk convert export --project $project --target-format package `
  --output 'E:/video-work/dialogue/exports/dialogue.aevpkg.zip'
```

Adapters also bind the installed implementation bytes. After a runtime upgrade,
register a new adapter ID; an old adapter can correctly fail inspection because
its bound worker changed. Matching model bytes and segment settings still permit
a portable recipe rerun with the newly registered implementation. Compare the
result with the previous master before replacing an editorial choice.

The asset's `source.speech_enhancement` recipe contains source/model hashes,
native selection clock, strength/attenuation and segmentation settings. It has
no runtime/model absolute paths. Reruns require matching model bytes and
registered segment/overlap/thread settings. Fragment imports rebind source IDs
and recompute the recipe hash. Fragment application uses its existing video-track
container API even for a selected audio-only group; the child audio remains
editable. Project packages include source and enhanced
audio assets/recipes; model weights and native dependencies remain separately
registered local resources. Use a new asset ID; existing files are never replaced.

`--apply` requires an unlocked audio `--track-id`; it adds an independent clip,
with its own gain, fades, routing and timeline position. Select which source or
enhanced track to audition so both are not unintentionally mixed together.

## Model, resources and cancellation

The adapter requires ordinary local `config.json`, `model.safetensors`,
`conversion.json`, `LICENSE-MIT.txt` and `LICENSE-APACHE.txt`. Configuration is
fixed to the reviewed DeepFilterNet3 checkpoint/graph. The product loads no
Pickle or model-directory Python and executes no arbitrary provider. Development
conversion used `torch.load(weights_only=True)` once, then strict state matching
and complete safetensors tensor equality. Model, source and output rights remain
separate. [Pinned upstream and conversion evidence](../validation/evidence/native-speech-enhancement-20261027-r1/acquisition.json).

Neural inference requires CUDA; there is no silent CPU fallback. CUDA free-memory
admission is a current observation, not a reservation or an OOM guarantee.
`--timeout-seconds` is a pipeline deadline; metadata/source preflight occurs before
that clock. `--cancel-file` is checked before and during execution. A suspended
worker is attached to an owned Windows job before code executes; decoder and
resampler children inherit that ownership. Cancellation/deadline/failure removes
owned work and rolls back project metadata; bounded diagnostic files survive
under `renders/diagnostics/pipelines/`; the CLI error includes its diagnostic ID.
Use `diagnostics list/show/export` to inspect bounded, redacted receipts after
metadata rollback. Only the worker is individually observed; its FFmpeg children
inherit the owned Windows job. Recovery uses `project recover --cleanup-jobs`.

| Parameter | Supported range / behavior |
|---|---|
| Source | Audio/video, first audio stream, 8–96 kHz, mono/stereo, indexed length ≤1800 s |
| Selected range | Positive native sample interval, ≤600 s |
| Segment | 1–30 s, default 10 s; network and feature normalization reset per segment |
| Overlap | 0–0.75, default 0.25; positive triangle overlap/add |
| Strength | 0–1, default 1 |
| Attenuation limit | Omitted or 0–100 dB; explicit native-rate dry/wet formula above |
| Storage | Explicit 64–8192 MiB, default 2048; estimated and monitored owned work |
| CPU arrays | Fixed segment dimensions admit ≤512 MiB owned array work; excludes total process RSS, Torch/FFmpeg and OS mapping cache |
| Deadline | Positive ≤7200 s, default 900 s; preflight excluded |

## Review actual audio

Use [C53](CASES.md#c53-native-speech-enhancement) and its original/mixture/enhanced
WAVs, playable comparison, editable package, measured errors and retained
failures. Noise suppression metrics are not a listening acceptance test. Review
consonants, breaths, music, reverberation, segment boundaries and stereo position.
This adds an actual denoising core; broad de-reverberation, music fidelity and
complete G17/CapCut parity remain unproven.
