# CLI0.1.44 / alpha.4-local.42 — actual HDR10 static SEI

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

HDR10母版显示/MaxCLL/MaxFALL明确声明、实际HEVC SEI写入、发布前解码核验、工程包与GPU合成。繁體：明確母版聲明與實際SEI核驗。 English: declared HDR10 static metadata with actual HEVC and decoded verification. This local compiled build preserves immutable public alpha.3/CLI0.1.2.

```text
installed: local/agent-ffmpeg/v0.1.0-alpha.4-local.42/final-r1/installed
application ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.42/candidate-r1/bundle.zip
archive bytes: 302981613
archive SHA256: 2556eb80788d610710cc97aee8c79648a9bfec3fb92e42d3e8dc5a4a777a0e97
manifest: sha256:2abbddda9d784eef3dccb433b516009354f2bb0b9ae4957231633f5050d2abb4
```

267 product Python files match tested source;83 capabilities. One public `$agent-ffmpeg-local-editor`,17 internal modules,83 Skill files. r45 kit has134 ZIP entries; no source fallback or virtualization.

Use the [offline install/activation workflow](../product/COMMUNITY_LOCAL_DELIVERY.md), then [HDR10 configuration and commands](../product/HDR_METADATA.md). Init/ingest/compose,declare all source/working/output signals and `settings.output.hdr10`,validate,dry-run,render,inspect `delivery.hdr10_static_metadata`,generate a separate SDR viewing copy and export an editable package. Existing native FFmpeg/libx265/ffprobe handle encoding/probing; no model download. Actual composition can use OpenCL; x265 uses CPU.

21 source checks,21 installed checks and105 installed compatibility checks pass separately. C54 checks all48 frames independently and full package video/384000 PCM replay. Production verification reads32 video packets,not a whole-movie certificate. Declarations are not peak measurements or calibration. Dynamic HDR,ICC/monitoring and full product goal remain ongoing.

[C54 master/SDR/GIF/package](../product/CASES.md#c54-native-hdr10-metadata) · [Evidence](../validation/HDR10静态元数据实测_2026-10-28.md)
