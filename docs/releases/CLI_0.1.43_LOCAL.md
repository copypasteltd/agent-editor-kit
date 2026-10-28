# CLI0.1.43 / alpha.4-local.41 — native CUDA speech enhancement

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

真实DeepFilterNet3 CUDA对白降噪、原生单/双声道与精确采样时钟、干湿控制、可编辑音轨、配方重跑、工程包、取消回滚。繁體：真正本機CUDA對白降噪及完整原生取樣。 English: native CUDA speech denoising with exact native samples and editable audio. Full dereverberation/music fidelity and full product parity remain ongoing.

This is a **local compiled installation**, separate from immutable public alpha.3/CLI0.1.2.

```text
E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.41/candidate-r3/bundle.zip
bytes: 302976814
SHA-256: 577880a69c056928983cf2f7ed394cd3134c7c767c3ed582a5ee002f974f8d25
manifest SHA-256: f1c17764755bacd2131f6c9ede680b7b33ef793a4b3439ca1833f51316e3a5d5
installed: E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/v0.1.0-alpha.4-local.41/final-r3/installed
```

266 Python product files match frozen tested source;82 capabilities. r44kit has1public Skill/17internal modules/82Skill files/132ZIP entries. The installed Skill remains `$agent-ffmpeg-local-editor`, with no source fallback. Existing native Python/CUDA/Torch/safetensors and the fixed local model are explicitly registered; no virtualization or dependency installation.

Use [offline installation/activation](../product/COMMUNITY_LOCAL_DELIVERY.md), then [the complete speech workflow](../product/SPEECH_ENHANCEMENT.md): init, ingest real local media, register model/native Python/license, dry-run, generate a new enhanced asset, audition original/output, validate, render and export an editable package. `--apply --track-id` adds a separate audio clip; avoid playing original and enhanced tracks together unintentionally. `--recipe-asset-id` plus a new ID reuses immutable source/model/settings; strength can be changed.

33 source checks,33 installed checks and156 installed compatibility checks are separate. C53 real English input SNR0→12.25dB; synthetic Mandarin0→9.69dB. Complete native samples,bit-exact bypass,package-render PCM,fragment rebinding and cancellation after actual neural output pass. Retained initial real-case failure exposed an atomic temporary-file race,now covered by regression. Clean-speech distortion,reverb controls,independent official CPU-reference differences and all earlier failures are disclosed. No human listening or broad natural/music quality acceptance is claimed.

[C53/audio/GIF/spectra](../product/CASES.md#c53-native-speech-enhancement) · [Actual evidence](../validation/本地对白增强实测_2026-10-27.md) · [Build/install](../validation/evidence/native-speech-enhancement-20261027-r1/installation-final-r3/verification.json)
