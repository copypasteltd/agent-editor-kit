# CLI0.1.45 / alpha.4-local.43 — explicit reference-white adaptation

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

Bradford白点适应、ProPhoto D50、线性AP1 D60、浮点中间包/预览/可编辑工程及白点感知GPU光晕。繁體：明確白點與實際預覽，保留既有D65。 English: explicit reference whites across native editing and delivery. Immutable public alpha.3/CLI0.1.2 remains unchanged.

```text
installed: local/agent-ffmpeg/v0.1.0-alpha.4-local.43/final-r1/installed
application ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.43/candidate-r1/bundle.zip
archive bytes: 302985103
archive SHA256: 35a2e99f5fcb7ff97ccb8ebda7aa2dc4b511e28e02a0680a5992af5ea3dbf3a4
manifest: sha256:89b5e3d6c266420d6efc06702642b8e6d481e1a9bf5ec112cea8326eeacea3f6
```

268 product Python files match tested source;84 capabilities. One public `$agent-ffmpeg-local-editor`,17 internal modules,84 Skill files. r46 kit contains136 ZIP entries; no source fallback or virtualization.

Use the [offline install/activation workflow](../product/COMMUNITY_LOCAL_DELIVERY.md),then [full configuration/commands](../product/CHROMATIC_ADAPTATION.md). Init/ingest/compose,declare actual source/working/output signals,validate,dry-run,render,inspect the chromatic-transform manifest,preview actual D65 output and export an editable package. `surface export` exposes source/working xy overrides and all new relative RGB choices. Existing NumPy/FFmpeg suffice; no new model/library install. Color math uses CPU; configured composition and white-aware Bloom/Halation use OpenCL.

20 source checks,20 installed checks and267 installed compatibility checks pass separately. C55 independently checks230400 first-frame pixels,eight patches over all48 frames,and complete48-frame/384000-PCM-scalar package replay. Initial independent-oracle assertions and expected SDR-range refusal are retained;final delivery declares clip. Raw source values do not imply ICC parsing or automatic white balance. AP1 linear configuration is not a full ACES IDT/RRT/ODT/DRT. D65 encoded output,perceptual gamut and natural HDR-monitor limitations are explicit;the whole goal remains ongoing.

[C55 media/GIF/package](../product/CASES.md#c55-native-chromatic-adaptation) · [Evidence](../validation/明确白点色适应实测_2026-10-28.md)
