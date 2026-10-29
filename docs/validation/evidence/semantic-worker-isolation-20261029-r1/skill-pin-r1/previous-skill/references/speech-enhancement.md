# Local neural speech enhancement

Use `audio enhance` for a noisy local dialogue asset. Read installed help first.
The fixed DeepFilterNet3 graph runs on CUDA; NumPy frontend and FFmpeg resampling
run on CPU. Require an explicitly registered existing local safetensors model and
native Python with Torch/NumPy/safetensors. No runtime model download or install.

```powershell
& $avk audio enhancement-adapter register --project $project --adapter-id df3 `
  --model-path 'E:/models/deepfilternet3' --executable 'D:/native-python/python.exe' `
  --evidence 'E:/models/df3-rights.json' --license-spdx 'MIT OR Apache-2.0' `
  --creator 'DeepFilterNet contributors' --segment-seconds 10 --overlap 0.25
& $avk audio enhance --project $project --adapter-id df3 `
  --source-asset-id SOURCE_ID --asset-id dialogue_enhanced `
  --strength 0.85 --attenuation-limit-db 24 --apply --track-id track_audio_1
& $avk audio enhance --project $project --adapter-id df3 `
  --recipe-asset-id dialogue_enhanced --asset-id dialogue_gentler --strength 0.5
```

Use actual source IDs and rights evidence. Model, source and derived audio have
separate rights. Match recipe model bytes and segment/overlap/thread settings on
rerun. Keep original audio; choose which track to audition before rendering.
The generated audio clip is ordinary editable audio, with its own gain/fades.

The first audio stream uses its native sample interval clock, including explicit
hard-gap zero fill and later-frame overwrite at overlaps. Select nearest native
samples; output preserves native rate, sample count and mono/stereo channels.
The 48 kHz model independently estimates each channel; other rates resample
explicitly. Stereo width and high-frequency content can change.

Effective wet is `strength * (1 - 10**(-attenuation_limit_db/20))`; omit the limit
for complete model output. This is mixing, not guaranteed spectral attenuation.
`strength=0` or limit `0` bypasses inference/resampling and retains all selected
Float32 PCM bits. No automatic clipping or normalization. Every encoded output
sample is decoded and hashed before asset publication.

Source ≤1800 s, selected range ≤600 s, 8–96 kHz, one/two channels; segments 1–30 s
with explicit recurrent/normalization reset and positive triangle overlap/add.
Long recordings can show segment artifacts. Native CUDA has no CPU fallback.
Timeout/cancel owns the Windows worker/descendants and rolls metadata back;
diagnostics survive. Use `project recover --cleanup-jobs` after interruption.

Show actual clean/noisy/enhanced WAV or MP4 previews for client choice; the GIF
has no sound. Listen for lost consonants, breaths, metallic tails, reverb and
stereo movement. Metrics and static waveforms do not establish naturalness.

[Full workflow and exact constraints](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/SPEECH_ENHANCEMENT.md)
· [Actual C53 previews and limits](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/CASES.md#c53-native-speech-enhancement).
