# CLI0.1.49 / alpha.4-local.47 — All-frame HDR light measurement

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

新增**全帧 HDR 光量测量与色彩裁切汇总**：实际作者时间线、明确nit、MaxRGB与CIE Y分别报告、峰值位置/最大帧平均/精确时长加权、可选有效画面范围。测量与正式渲染共用实际RGB16输入路径；中间包补齐所有帧的转换收据。

新增**全影格 HDR 光量測量與色彩裁切彙總**：實際作者時間線、明確nit、MaxRGB與CIE Y分別報告、峰值位置／最大影格平均／精確時長加權、可選有效畫面範圍。測量與正式算繪共用實際RGB16輸入路徑；中間包補齊所有影格轉換收據。

Added **all-frame HDR light metering and colour-clipping ledgers**: actual authored timeline,explicit nits,separate MaxRGB/CIE Y,peak locations/maximum frame averages/exact exposure weighting,and explicit active regions. Metering shares the real RGB16 encoder-input path;intermediate bundles now retain all-frame conversion receipts.

```text
installed: local/agent-ffmpeg/v0.1.0-alpha.4-local.47/final-r1/installed
application ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.47/candidate-r1/bundle.zip
archive bytes: 303213870
archive SHA256: fc42ba3e5057573048e0aab4aa5b02e94b1ceae2fc07b7e05cb8461ff0cabf04
manifest: sha256:e612767df92bda5212592285403e5a0dd4ce9b9d41a40680de328a705420214a
```

275 Python files match tested source bytes;88 capabilities. One public `$agent-ffmpeg-local-editor`,17 internal modules,88 Skill files,r50 kit144 entries. Public alpha.3/CLI0.1.2 downloads unchanged. Native Windows,no virtualization/global installation/source fallback.

Follow [offline activation](../product/COMMUNITY_LOCAL_DELIVERY.md) and [measurement workflow](../product/HDR_MEASUREMENT.md):init/ingest/compose → declare working/output nits → validate/dry-run → measure full timeline → inspect metric/scope/range counts → make explicit mastering decisions → render/inspect manifest → package/import/replay. CPU colour/meter,selected native GPU editing.

19 source checks,19 installed checks and352 installed compatibility checks pass separately. C59 independently checks all48 frames/11059200 pixels and the RGB16 input digest,then replays the complete PQ master/audio/measurements after package import. Another48-frame actual GPU Bloom/native ICC proof run has identical meter/render input. No post-codec peak,physical display or artistic-quality acceptance is claimed.

[C59](../product/CASES.md#c59-native-hdr-measurement) · [Evidence](../validation/全帧HDR光量与裁切汇总实测_2026-10-29.md).
