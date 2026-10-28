# HLG 显示黑位 / HLG 顯示黑位 / HLG display black

CLI0.1.47 adds explicit nonzero HLG display black and complete RGB/HDR/ICC signal
JSON for `surface export`. This is a CPU color-boundary operation; configured
composition, Bloom/Halation and other supported operators retain native OpenCL
GPU execution. No new model, virtualization or global installation is needed.

简体：黑位是作者明确声明的显示解释，不是程序测出的屏幕黑位。繁體：黑位為使用者明確宣告，並非程式測得的螢幕數值。English: display black is an authored interpretation, never inferred from monitor or video metadata.

## Complete usage

Use the [pinned installed Skill/runtime](COMMUNITY_LOCAL_DELIVERY.md). Init a
project, ingest original local media with rights evidence, compose editable
tracks, then declare `settings.pixel_pipeline`:

```json
{
  "engine":"float32-native-v1",
  "working_signal":{"primaries":"bt2020","transfer":"linear","reference_white_nits":203},
  "output_signal":{"primaries":"bt2020","transfer":"pq-st2084","reference_white_nits":203},
  "range_policy":"reject",
  "sources":{
    "ASSET_ID":{
      "source_signal":{
        "primaries":"bt2020","transfer":"hlg-bt2100",
        "reference_white_nits":203,"display_peak_nits":1000,
        "system_gamma":1.2,"display_black_nits":0.005
      },
      "display_geometry":"square-unrotated"
    }
  }
}
```

These are example declarations, not universal camera/display settings. Replace
them with the actual agreed source/output meaning. For PQ delivery set root
`settings.color` to BT.2020 / `smpte2084` / `bt2020nc`, and select an actual
supported ten-bit video encoder/pixel format. HLG output uses `arib-std-b67`.
For a client SDR preview separately declare `preview_mapping`, for example:

```json
{"operator":"reinhard-luminance","source_peak_nits":1000,"target_peak_nits":100,
 "exposure_stops":0,"gamut_policy":"clip"}
```

Validate and inspect render dry-run before execution. Render with explicit GPU
policy/device for supported operators; CPU color conversion and CPU/GPU video
encoding are separate decisions. Inspect encoded VUI, source color-boundary
`HLG_black_level`, alpha and range counts; preview actual output; export a
`package`, import into a new location, validate and replay its full audio/video.
Do not claim a passing SDR preview validates an HDR monitor.

## Raw native-clock CLI

Save the complete HLG source object as `source.json`, and the working object
as `working.json`. Paths may point to local JSON; parsed values are embedded in
the recipe, so these descriptor files do not become live render dependencies.
Use the registered unified launcher with these CLI arguments:

```text
surface export --project PROJECT --asset-id ASSET_ID --output renders/linear-surface
  --source-signal-json source.json --working-signal-json working.json
  --stop-frame 1
```

The displayed command is wrapped for readability; pass it as a single argument
sequence. The output is a new project-owned directory containing
`frames.rgba-f32le`, `clock.i64le` and `bundle.json`. It retains original source
frame indexes, PTS and durations; it is an intermediate, with no encoded movie
or audio. `surface inspect --project PROJECT --input renders/linear-surface`
checks the actual bundle. Defaults reject invalid input/output domains.

- Complete source JSON and individual source flags are mutually exclusive.
  Complete working JSON also rejects mixed individual working parameters.
- All HDR paths require explicit reference-white nits on both ends. HLG also
  requires display peak and system gamma; nonzero black cannot supply them.
- For authorized output-domain clipping pass `--hdr-range-policy clip`;
  input clipping is separately `--hdr-input-range-policy clip`. The recipe
  embeds these choices and receipts count clipped components.
- Existing ordinary RGB and ICC source flags remain supported. Complete JSON
  also accepts the [explicit ICC source descriptor](ICC_PROFILES.md), while its
  target must remain a supported linear working profile.

In the current raw bundle, `colour_boundary` is the conversion receipt for the
last selected frame, not a sum of clipping counts over the whole bundle. Use
the declared selected-frame range when reading that receipt; do not present
its component count as a full-clip total. Full encoded-video/PCM replay checks
are separate from these per-surface numeric diagnostics.

## Numeric contract

[ITU-R BT.2100-3 Table5](https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.2100-3-202502-I!!PDF-E.pdf)
defines HLG display black lift. Original implementation follows these facts:

```text
beta = sqrt(3 * (display_black_nits/display_peak_nits)^(1/system_gamma))
lifted_RGB = beta + (1-beta) * encoded_RGB
```

Then apply inverse HLG OETF and coupled-RGB OOTF using declared peak/gamma.
Neutral encoded zero maps to the declared physical black luminance. The inverse
applies the coupled inverse OOTF, OETF and `(lifted_RGB-beta)/(1-beta)`.
`display_black_nits` is finite numeric0..10, HLG-only, and beta must be below1.
Bool/string/NaN/Inf/missing contexts and degenerate ranges are rejected.

Omitted black retains the previous ideal-zero implementation and metadata.
Explicit zero follows identical numeric operations/bytes but records the author
declaration. Positive black is part of signal equality, preview fingerprints,
surface recipes and portable project settings. Alpha bits, including signed
zero/subnormal values, remain separate from transfer and adaptation math.

Inputs retain the existing nominal encoded0..1 domain. Outputs below the target
black, or above representable range, reject unless clipping was explicitly
selected. Rounded published HLG coefficients make the white endpoint slightly
above the nominal peak; strict inverse conversion may therefore reject that
endpoint. The product does not add an invisible epsilon clamp or alter the
existing zero-black curve to conceal this behavior.

## Evidence and boundaries

[C57 actual media and package](CASES.md#c57-hlg-display-black) use an original
CC0 RGB16 diagnostic, stereo tones, declared0.5-nit black/1000-nit peak and GPU
Bloom, with independent working-surface and encoded-patch checks. The intentionally
raised black makes this a numeric diagnostic. Its independent ideal-zero/no-glow
control is labeled separately from the actual engine output.

This extension does not implement subblack PLUGE codes, display measurement,
automatic peak/black/gamma inference, dynamic HDR metadata, complete ACES,
perceptual gamut rendering or natural-image/HDR-monitor acceptance. Standard
math facts are referenced; no copyrighted standard pages are redistributed.
See [HDR workflow](HDR_DISPLAY.md), [HDR10 static metadata](HDR_METADATA.md) and
[remaining original product acceptance conditions](GOAL_GAPS_20261025.md).
