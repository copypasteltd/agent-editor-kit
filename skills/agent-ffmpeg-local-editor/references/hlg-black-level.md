# Explicit HLG display black / CLI0.1.47

Use the pinned launcher; inspect `native_hlg_black_level`. Complete workflow:
`docs/product/HLG_BLACK_LEVEL.md` in the small kit. The ITU-R BT.2100-3 Table5
black-lift extension is CPU Float32 color math; supported editing operators
still use the separately selected native OpenCL GPU. No monitor is probed.

1. Confirm the actual code-value meaning with the client. Explicit source:

```json
{"primaries":"bt2020","transfer":"hlg-bt2100","reference_white_nits":203,
 "display_peak_nits":1000,"system_gamma":1.2,"display_black_nits":0.005}
```

2. Declare linear working RGB with `reference_white_nits:203`, and an explicit
   output signal (PQ, HLG or supported relative output with declared nits).
   Use `settings.pixel_pipeline.engine:"float32-native-v1"`; source declarations
   are under `sources.<asset_id>.source_signal`. Do not invent physical values.
3. `display_black_nits` accepts finite numbers0..10 only on HLG, with beta<1.
   Omission retains the original ideal-zero path. Explicit zero preserves its
   numeric bytes, while recording that the user actually declared zero.
4. For raw native-clock frames, save complete source and working JSON objects:

```text
surface export --project PROJECT --asset-id ASSET --output renders/surface
  --source-signal-json source.json --working-signal-json working.json
  --stop-frame 1
```

   Do not mix complete JSON with individual source/working flags. HDR requires
   explicit reference-white nits on both sides. Input and output domains default
   to reject. To authorize output clipping use `--hdr-range-policy clip`;
   input clipping uses `--hdr-input-range-policy clip`. Recipes embed the parsed
   descriptors and policies; external descriptor files are not live dependencies.
5. In timeline rendering choose `pixel_pipeline.range_policy:"reject"` or
   explicit `"clip"`. Below-black output and rounded white-endpoint overflow
   follow this policy and are counted. No hidden epsilon snapping is performed.
6. Validate, dry-run, render, inspect actual VUI and the HLG black-level receipt,
   preview with an explicit SDR mapping, then package/import/replay. Raw bundles
   preserve alpha bits and original PTS/durations; they contain no encoded audio.
7. Show C57 actual PNG/MP4/GIF and signals to clients. Its intentionally raised
   0.5-nit black is a numeric diagnostic, not calibrated monitor acceptance.
   Left is an independent ideal-zero/no-glow control; right is actual HLG black
   conversion plus GPU Bloom. Full ACES, dynamic HDR, measured display matching,
   subblack PLUGE signals and natural-image artistic validation remain open.
