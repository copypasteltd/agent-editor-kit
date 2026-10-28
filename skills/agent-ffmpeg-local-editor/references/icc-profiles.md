# Explicit native ICC source color management

Use the pinned installed launcher and inspect `native_icc_source_profiles`.
The packaged `docs/product/ICC_PROFILES.md` provides full JSON/commands and C56.
The native Windows x64 LittleCMS 2.19.1 DLL, source revision, SHA and MIT license
are included and verified. Color management runs on CPU; supported editing
operators use the separately selected native OpenCL GPU.

1. Confirm what the local source code values actually represent. Obtain its
   RGB ICC v2/v4 file and rights evidence; place it inside the project. Do not
   invent a camera profile or treat a profile as a creative LUT.
2. Run `surface inspect-profile --project PROJECT --input assets/source.icc`.
   This checks header/tag budgets, real native parsing and actual SHA without
   editing author data. Choose a supported rendering intent explicitly.
3. Set `settings.pixel_pipeline.engine:"float32-native-v1"` and source signal:

```json
{
  "icc_profile":"assets/source.icc",
  "sha256":"sha256:<actual 64 lowercase hex>",
  "intent":"relative-colorimetric",
  "black_point_compensation":false
}
```

4. Declare a linear RGB `working_signal` and explicit output signal. Native CMM
   converts directly to that working profile, including declared D50/D60 whites.
   The four intents are `perceptual`, `relative-colorimetric`, `saturation` and
   `absolute-colorimetric`; an intent missing from a table profile is rejected.
   Results can differ according to profile tables; matrix profiles need not
   produce different results for each intent. BPC is an explicit boolean.
5. For absolute light units/HDR, declare `reference_white_nits` on the ICC source
   and working/output signals. ICC white-point tags are chromaticity/media-white
   data, not a measurement of scene illumination or display peak luminance.
6. Validate, inspect dry-run, render and preview actual output. Read
   `delivery.pixel_pipeline.source_receipts.<asset_id>.ICC_transform`, including
   CMM version, profile bytes, intent, unit scaling and handle cleanup. Source
   RGB must be finite 0..1; working negative/superwhite RGB and alpha bits are
   preserved until a separately declared output boundary.
7. `surface export` accepts `--source-icc-profile assets/source.icc
   --source-icc-sha256 sha256:... --source-icc-intent relative-colorimetric`
   with `--working-primaries`, optional `--working-white-xy` and linear transfer.
   Optional BPC uses `--source-icc-black-point-compensation`. Explicit nit units
   use `--source-reference-white-nits` and `--working-reference-white-nits`.
   Do not mix ICC flags with `--source-primaries/transfer/white-xy` declarations.
8. Export a `package` and test its import/replay. The exact profile bytes are
   included; profiles outside `assets/` become content-addressed package paths.
   Author data is unchanged. Register rights separately; packaging grants none.

Show C56's actual PNG/MP4/GIF and its profile/settings before client selection.
Its left comparison is an independent no-adaptation/no-Bloom mathematical
control; right is the actual ICC/OpenCL engine output. It is a numeric diagnostic,
not a natural-image artistic assessment. No continuous human playback/listening
or HDR-monitor acceptance is claimed. Scope: RGB matrix/shaper and table source
profiles, not CMYK/device links, arbitrary output ICC, softproofing, embedded
profile auto-detection, ICC v5 or complete ACES rendering. The profile is limited
to 16MiB/4096 tags; surface budgets are estimates, not total process peak RSS.

CLI0.1.47 adds [complete HDR/HLG black signal JSON for surface export](hlg-black-level.md), with explicit nits and reject/clip policies. Existing individual RGB/ICC flags remain supported.
