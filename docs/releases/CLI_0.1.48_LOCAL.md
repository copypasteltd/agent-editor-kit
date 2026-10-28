# CLI0.1.48 / alpha.4-local.46 — ICC output and native soft proof

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

新增**原生 RGB ICC 输出、16位内嵌配置 PNG 序列与软打样**：实际B2A查找表、四意图/BPC、明确亮度缩放、作者时间线逐帧交付和同步PCM；普通渲染/预览原生模拟，配置依赖可移植。

新增**原生 RGB ICC 輸出、16位內嵌設定 PNG 序列與軟打樣**：實際B2A查找表、四意圖／BPC、明確亮度縮放、作者時間線逐影格交付及同步PCM；一般算繪／預覽原生模擬，設定依賴可移植。

Added **native RGB ICC output, profile-embedded16-bit PNG sequence delivery and soft proof**: actual B2A tables,intents/BPC,explicit nits scaling,authored frames and synchronized PCM;native simulation in normal render/previews and portable profile dependencies.

```text
installed: local/agent-ffmpeg/v0.1.0-alpha.4-local.46/final-r1/installed
application ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.46/candidate-r1/bundle.zip
archive bytes: 303207227
archive SHA256: 7518e73d158e75c5db2e6183fa2b252cab4bfe90f4acd1215994b3882279f27f
manifest: sha256:3ec1c2ecb9538c9eeaf4572aa934a803cae2bbb9a392709d7798e36fdf479024
```

273 Python files and native ICC artifacts match tested source bytes;87 capabilities. One public `$agent-ffmpeg-local-editor`,17 internal modules,87 Skill files,r49 kit142 entries. Public alpha.3/CLI0.1.2 artifacts unchanged. Native Windows,no virtualization/global installation/source fallback.

Follow [offline activation](../product/COMMUNITY_LOCAL_DELIVERY.md),then [complete ICC output workflow](../product/ICC_OUTPUT.md):init/ingest/compose → explicit source/working signals → authorized output ICC/hash/intent → validate/dry-run → surface render → inspect-output → native soft-proof movie/preview → package/import/replay. Color CMM uses CPU;selected supported editing uses OpenCL GPU.

17 source checks,17 installed checks and335 installed compatibility checks pass separately. C58 embeds ICC per frame,independently checks384 B2A patches and384 soft-proof Y/Cb/Cr triplets,and replays all48 PNG frames/files,66355200 decoded soft-proof movie bytes and384000 nonzero PCM scalars identically,with48 actual GPU Bloom calls/sequence. ICC uses CPU;supported editing uses GPU. The synthetic diagnostic profile is not printer/display calibration or artistic acceptance.

[C58 actual media](../product/CASES.md#c58-native-icc-output) · [Verification](../validation/原生ICC输出与软打样实测_2026-10-29.md).
