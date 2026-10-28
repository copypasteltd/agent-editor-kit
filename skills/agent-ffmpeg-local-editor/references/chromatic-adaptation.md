# Explicit reference whites / ProPhoto D50 / AP1 D60

Use the pinned installed launcher and inspect `native_chromatic_adaptation`.
The packaged `docs/product/CHROMATIC_ADAPTATION.md` contains full JSON, commands
and the actual C55 diagnostic media/package workflow.

- Declare the source interpretation; never label ordinary sRGB imagery as
  ProPhoto just to obtain a look. `prophoto-rgb` primaries default to D50 and
  `prophoto-rgb` transfer uses a linear toe plus signed1.8 extension.
- `aces-ap1` defaults to D60. Choose `linear` for the edit working signal;
  camera IDT, scene/display rendering and ACES RRT/ODT/DRT require separate work.
- Optional `white_xy:[x,y]` belongs inside source/working/effect RGB signal
  declarations. It is CIE1931 reference-white chromaticity, not Kelvin, exposure
  or automatic white balance. Conversion uses Bradford in linear XYZ.
- Preserve explicit `reference_white_nits` on both ends when absolute units
  matter. Reference-white chromaticity and white luminance are separate fields.
- Final BT.709/PQ/HLG video delivery remains D65; use the selected output
  transfer and matching tags. PQ/HLG encoded signals also require BT.2020.
- Use `surface export --source-primaries prophoto-rgb --source-transfer
  prophoto-rgb --working-primaries aces-ap1 --working-transfer linear
  --working-white-xy 0.32168 0.33767` for a native-clock Float32 intermediate.
  Source overrides use `--source-white-xy X Y`; inspect the returned manifest.
- Validate, inspect dry-run, render, preview actual D65 PNG/MP4/GIF and export
  an editable package. CPU performs color conversion; supported geometry and
  Bloom/Halation can use the configured native OpenCL GPU. The glow threshold
  uses luminance coefficients for the declared working reference white.
- Show C55's actual preview together with `signals.json`, original source and
  the clearly labelled independent no-adaptation control. That control omits
  Bloom and is a mathematical diagnostic, not another engine output or a
  natural image quality/HDR-monitor assessment. Preserve this distinction.
- Explicit D65 equivalents keep alpha and identical-signal RGB bits. Other
  conversions preserve alpha, signed/above-one RGB until a separately declared
  output boundary. There is no implicit perceptual gamut mapping or ICC parsing.
