# 明确参考白点与色适应 / Explicit reference whites and chromatic adaptation

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

CLI0.1.45 extends the native Float32 editor with **Bradford adaptation in linear
XYZ**, **ProPhoto RGB D50** and **linear ACES AP1 D60**. Sources, working RGB,
effect signal boundaries, previews and editable packages share the conversion.
The existing two-field D65 signals retain their previous interpretation.

繁體：來源、線性工作域、效果、預覽與可編輯專案共用明確白點轉換；ProPhoto RGB
預設 D50，AP1 預設 D60，最終 BT.709／BT.2100 視訊交付仍使用 D65。

## Declare the actual source interpretation

`white_xy` means CIE1931 **reference-white chromaticity**, separate from
`reference_white_nits`, which describes luminance units. A reference white is
part of an RGB colorimetric definition. It does not identify the photographed
light source, correct camera white balance or infer an embedded ICC profile.
Declare the real source; changing an sRGB label to ProPhoto is not a filter.

| Signal field / 字段 | Meaning / 约束 |
|---|---|
| `primaries: "bt709"`, `"display-p3"`, `"bt2020"` | Their existing default reference white is D65,xy `[0.3127,0.329]`. |
| `primaries: "prophoto-rgb"` | ProPhoto RGB chromaticities; default D50,xy `[0.3457,0.3585]`,using the W3C four-decimal white,not automatically an ICC PCS white. |
| `primaries: "aces-ap1"` | Academy AP1 primaries,including green xy `[0.165,0.830]`; default D60,xy `[0.32168,0.33767]`. Select `linear` for the working signal. |
| `transfer: "prophoto-rgb"` | Decode signed encoded values: `v/16` for `abs(v)<=1/32`; otherwise `sign(v)*abs(v)^1.8`. Encode: `16*v` for `abs(v)<1/512`; otherwise the signed inverse1.8 power. Negative values use an explicit mathematical extension. |
| `white_xy: [x,y]` | Optional explicit override. Two finite numbers in `[0.0001,0.9998]`,positive XYZ components,white inside the RGB primary triangle and positive Bradford cone responses. Booleans,NaN,degenerate/outside white points fail. |
| `reference_white_nits` | Existing optional explicit0.01–10000 cd/m². Declare both endpoints to rescale absolute linear units; HDR editing requires the existing full luminance declarations. |
| Encoded/output restrictions | PQ/HLG encoded signals require BT.2020/D65. Current BT.709 and BT.2100 video delivery remains D65. Other source/working whites are adapted before encoding. Raw intermediate surfaces may retain D50/D60. |

For each tile: inverse source transfer → source RGB-to-XYZ at its reference
white → Bradford source-to-target white adaptation → target XYZ-to-RGB →
explicit nit-unit scaling → target transfer → owned Float32 output. Math uses
Float64 within bounded tiles. Alpha bits are preserved. Negative/above-one RGB
is retained until an independently declared output/range boundary; there is no
implicit perceptual gamut mapping. Identical/equivalent D65 signals keep their
byte-exact copy path.

## Editable video workflow

Use the installed `$agent-ffmpeg-local-editor` launcher from the main README.
Initialize a project,ingest licensed local assets,compose an ordinary timeline,
then declare the interpretation of every visual source. This is a **settings
fragment**; replace `chart` with an actual registered asset ID:

```json
{
  "color": {"primaries":"bt709","transfer":"iec61966-2-1","matrix":"bt709","range":"limited"},
  "output": {
    "container":"mkv",
    "video":{"codec":"libx264","preset":"ultrafast","crf":0,"pixel_format":"yuv444p10le"},
    "audio":{"codec":"pcm_f32le"}
  },
  "pixel_pipeline": {
    "engine":"float32-native-v1",
    "working_signal":{"primaries":"aces-ap1","transfer":"linear","white_xy":[0.32168,0.33767]},
    "output_signal":{"primaries":"bt709","transfer":"srgb"},
    "range_policy":"clip",
    "sources": {
      "chart": {
        "source_signal":{"primaries":"prophoto-rgb","transfer":"prophoto-rgb"},
        "display_geometry":"square-unrotated",
        "demux_origin":0
      }
    }
  }
}
```

```powershell
& $avk capabilities
& $avk validate --project $aekProject
& $avk render --project $aekProject --output "$aekProject/renders/check.mkv" --dry-run --hardware-encode off --projection-acceleration require --projection-device 0.0
& $avk render --project $aekProject --output "$aekProject/renders/final.mkv" --hardware-encode off --projection-acceleration require --projection-device 0.0
& $avk preview frame --project $aekProject --frame 24 --height 360
& $avk preview range --project $aekProject --start-frame 0 --end-frame 48 --height 360
& $avk convert export --project $aekProject --output "$aekProject/exports/editable.aevpkg.zip" --target-format package
```

The frame/range values above match C55; choose valid display-frame indexes for
the actual project. `projection-device 0.0` selects the device tested here;
discover and choose the intended installed adapter. Color conversion uses CPU;
supported geometry/composition and Bloom/Halation use native OpenCL when
requested. Their thresholds now use luminance coefficients for the working
reference white,including explicit custom whites. GPU encoding is separate.

Inspect `delivery.pixel_pipeline.source_receipts.<asset_id>.color_boundary`
for the actual source-to-working transform. The final declared output signal is
in `delivery.pixel_pipeline.output_signal`; integer-boundary clipping is counted
in `delivery.pixel_pipeline.transport.clipped_RGB_components`. Extended
conversions include `chromatic_transform`: source/target xy,Bradford or identity,
the XYZ adaptation matrix,and explicit `ICC_profile_parsed:false` /
`ACES_output_transform:false`. Source receipt working signals retain the
authored white. Ordinary LUT/curve input/output signal declarations use the
same parser and adaptation; their separate domains and limits still apply.

For nit-aware HDR work,read [HDR display](HDR_DISPLAY.md) and
[HDR10 static metadata](HDR_METADATA.md). AP1/D60 can be the linear working
configuration while PQ/HLG delivery remains BT.2020/D65. AP1 selection alone
does not perform a camera IDT or scene-to-display rendering.

## Native-clock Float32 intermediate

```powershell
& $avk surface export --project $aekProject --asset-id chart --output "$aekProject/renders/ap1-surface" --source-primaries prophoto-rgb --source-transfer prophoto-rgb --working-primaries aces-ap1 --working-transfer linear --working-white-xy 0.32168 0.33767 --stop-frame 1
& $avk surface inspect --project $aekProject --input "$aekProject/renders/ap1-surface"
```

`--source-white-xy X Y` overrides the source reference white. Omitting either
white override selects that primary set's default. Source/working primaries
and transfer choices expose the same five primary sets and six relative
transfers as the core. The half-open frame range uses original native frames,
not output CFR frames. Choose a new output directory. This raw export retains
the selected original clock and Float32 values,not audio or an encoded movie;
existing progressive YCbCr requirements and2GiB budget remain in force.

## Actual case and selection previews

[C55](CASES.md#c55-native-chromatic-adaptation) uses original CC0 ProPhoto D50
diagnostic RGB16 media and stereo tones,an explicit AP1/D60 working signal,
actual editable GPU Bloom and D65/sRGB ten-bit delivery. Independent published
matrix/transfer checks cover every pixel of the first raw surface and neutral
and color patches across the encoded sequence. Package replay compares every
decoded frame and PCM scalar; the actual PNG/MP4/GIF support client review.

![Actual encoded D65 client preview](../assets/native-chromatic-20261028-r3/actual-preview.gif)

[Actual frame](../assets/native-chromatic-20261028-r3/actual-frame.png) ·
[Actual MP4](../assets/native-chromatic-20261028-r3/actual-preview.mp4) ·
[Original declared ProPhoto source](../assets/native-chromatic-20261028-r3/source-prophoto-d50.mkv) ·
[Signal declarations](../assets/native-chromatic-20261028-r3/signals.json) ·
[Comparison sheet](../assets/native-chromatic-20261028-r3/comparison.png) ·
[Editable package](../assets/native-chromatic-20261028-r3/editable-chromatic.aevpkg.zip) ·
[Provenance](../assets/native-chromatic-20261028-r3/SOURCE.txt)

Present the actual D65 preview alongside the signal declarations. The sheet's
left image is an **independent mathematical no-adaptation control without
Bloom**; the right image is the actual engine output with Bloom. It explains
the missing reference-white operation; it is not a matched artistic A/B or a
second engine render. Do not present unconverted ProPhoto code values as an
sRGB client preview or call this diagnostic a natural-footage acceptance test.

The implementation does not parse ICC profiles,infer camera/log color,
perform automatic physical white balance,implement full ACES IDT/RRT/ODT/DRT,
or certify HDR monitor appearance. G08's broader color/HDR closure remains open.
No new model/library installation,network service or virtualized runtime is
required.

Primary specifications: [W3C CSS Color4 color spaces and conversion](https://www.w3.org/TR/css-color-4/)
and [Academy ACEScg encoding/AP1](https://docs.acescentral.com/encodings/acescg/).
Implementation is original; the numerical constants describe those encodings.

CLI0.1.46 adds a separate [native ICC source-profile path](ICC_PROFILES.md): explicit RGB v2/v4 matrix/table files, rendering intent/BPC and direct linear working RGB conversion. Existing mathematical reference-white conversion still infers no profile or physical illuminant. ICC white tags do not supply HDR luminance; declare source/working/output nits separately.
