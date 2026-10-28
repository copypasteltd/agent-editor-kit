# CLI0.1.47 / alpha.4-local.45 — HLG display black

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

新增**HLG 非零显示黑位和完整信号 JSON CLI**：明确黑位、峰值、伽马和参考白亮度，贯通源/输出、浮点中间包、预览与工程包；低于目标黑位严格拒绝或显式裁切计数。

新增**HLG 非零顯示黑位與完整訊號 JSON CLI**：明確黑位、峰值、伽馬及參考白亮度，貫通來源／輸出、浮點中間包、預覽與專案包；低於目標黑位嚴格拒絕或明確裁切計數。

Added **nonzero HLG display black and complete signal JSON CLI**: explicit black/peak/gamma/reference-white nits across sources, outputs, raw surfaces, previews and packages; below-black outputs reject or explicitly clip with counts.

```text
installed: local/agent-ffmpeg/v0.1.0-alpha.4-local.45/final-r1/installed
application ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.45/candidate-r1/bundle.zip
archive bytes: 303193916
archive SHA256: ff4d6487ac1338a431e507b3eced2496011458088171ce0cb35367c681d81730
manifest: sha256:0805b4798a4b11168a4753112afafaad9f26ab8463fc1ec06d0e30b04ddeacdf
```

270 Python files and native ICC artifacts match tested source bytes;86 capabilities.
One public `$agent-ffmpeg-local-editor`,17 internal modules,86 Skill files,r48 kit140 entries.
Public alpha.3/CLI0.1.2 artifacts remain unchanged. No source fallback,virtualization,
global installation or implicit model download.

Follow [offline activation](../product/COMMUNITY_LOCAL_DELIVERY.md),then
[complete HLG/CLI workflow](../product/HLG_BLACK_LEVEL.md):init/ingest/compose →
declare signals and domain policies → validate/dry-run → render → inspect actual
pixels/VUI/receipts → preview with explicit SDR mapping → package/import/replay.
Color math uses CPU;supported Bloom/composition uses selected native OpenCL GPU.

21 source checks,21 installed checks and314 installed compatibility checks pass separately. C57 checks230400 working pixels,384 encoded frame/patch pairs and all48 frames/384000 nonzero PCM scalars after package replay,with48 actual GPU Bloom calls/render. Color math uses CPU; supported composition uses GPU. The0.5-nit black is a diagnostic declaration,not monitor calibration; dynamic HDR,full ACES and natural-image monitoring remain open.

[C57 actual media/GIF/package](../product/CASES.md#c57-hlg-display-black) ·
[Verification](../validation/HLG显示黑位实测_2026-10-28.md)
