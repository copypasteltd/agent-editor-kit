# CLI0.1.46 / alpha.4-local.44 — native ICC source color management

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

原生RGB ICC v2/v4来源、矩阵与CLUT、四意图/BPC、Float32/alpha、nits、实际预览和依赖完整工程包。繁體：原生來源設定、浮點匯出與可編輯專案。 English: explicit native ICC sources across editing and portable delivery. Public alpha.3/CLI0.1.2 artifacts remain immutable.

```text
installed: local/agent-ffmpeg/v0.1.0-alpha.4-local.44/final-r1/installed
application ZIP: local/agent-ffmpeg/v0.1.0-alpha.4-local.44/candidate-r1/bundle.zip
archive bytes: 303191555
archive SHA256: e8b86856185ac3166108330947aec85c8906acbc7092d0266b7c25464c415d23
manifest: sha256:bbc6db3f335dcf38716f2aae154cb64266ce56e032357d731413721ee358d356
```

269 Python files and native ICC manifest/DLL/license match tested source bytes. 85 capabilities; one public `$agent-ffmpeg-local-editor`,17 internal modules,85 Skill files. r47 small kit contains138 ZIP entries. No source fallback, virtualization, global dependency installation or implicit download.

Follow [offline installation/activation](../product/COMMUNITY_LOCAL_DELIVERY.md), then [ICC configuration and complete usage](../product/ICC_PROFILES.md). Init/ingest/compose → inspect actual local profile → pin SHA/intent/BPC → declare linear working/output signals → validate/dry-run → render → inspect CMM/GPU receipts → preview actual output → export/import/replay an editable package. `surface export` also accepts explicit ICC flags and source/working nits. Native CMM runs on CPU; configured supported composition and Bloom/Halation use OpenCL.

26 source,26 installed and 287 installed compatibility checks pass separately. C56 uses an original CC0 gamma1.8 ProPhoto D50 ICC profile,independently checks230400 working pixels and384 frame/patch pairs,and replays all48 frames/384000 nonzero PCM scalars identically. Failed initial oracle/table fixtures and the first activation-order refusal are retained. Native RGB source ICC is implemented; arbitrary output ICC,softproofing,CMYK,embedded-profile inference,complete ACES,natural-image/HDR-monitor acceptance remain open.

[C56 actual media/GIF/editable package](../product/CASES.md#c56-native-icc-profiles) · [Evidence](../validation/原生ICC色彩管理实测_2026-10-28.md)
