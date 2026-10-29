# Editable highlight Bloom and film Halation

Use the pinned installed launcher from `runtime.md`. Discover actual constraints:

```powershell
& $avk effects list --query native:float32-glow --keyframable-only
& $avk effects inspect --name bloom
& $avk effects inspect --name film_halation
```

Original MIT operators: `bloom`/`highlight_bloom`, `halation`/`film_halation`.
These extract actual image highlights, spread their light through normalized
three-sigma separable Gaussian FIR, and add light in explicit linear working RGB.
Halation subtracts a controllable bright core and defaults to a red/orange tint.
No asset download, model, remote service or GUI is required.

Author an ordinary clip's ordered `effects` or selected-root `settings.adjustments`.
Use native `float32-native-v1`, explicit D65 working/source/output signals, asset
geometry/demux origin and range policy. `timeline compose`/`update_clip` replaces the
effects array: retain existing wanted effects. Legacy FFmpeg graphs reject these operators.

```json
{"type":"bloom","parameters":{"radius":10,"threshold":0.4,"knee":0.15,"gain":1.5},
 "keyframes":[{"property":"intensity","keyframes":[
  {"at_tick":0,"value":0.2,"interpolation":"ease_in_out"},
  {"at_tick":360000,"value":0.9,"interpolation":"linear"}]}]}
```

The sample spans four seconds at 90000 ticks/s. Inspect the actual original author
duration. Every key, including the last, declares interpolation. Six numeric easings
retain author time through windows/splits and continuous reverse left limits; root
adjustment intervals apply once after video/subtitles and use interval-local time.

Numeric parameters:

- `intensity` 0…1; `gain` 0…8; multiplied for final added light.
- `threshold` 0…16, relative linear luminance in the declared working primaries.
- `knee` 0…4, soft-knee width; zero selects a hard threshold.
- `radius` 0…32, Gaussian sigma in the input effect surface's pixels. Bloom default12,
  Halation default6. The finite support is `ceil(3*radius)` each side.
- `red/green/blue` 0…4, linear working RGB multipliers. Bloom defaults1/1/1;
  Halation defaults1/.2/.05. They are not encoded sRGB hex colors.
- Halation-only `core_suppression` 0…1, default1; removes the original bright core.
- **Static** `edge`: transparent (default) or clamp. Do not keyframe it.

All numeric fields use max1024 keys/channel,16384/effect,4MiB. Source alpha weights
emitted light; hidden transparent RGB never lights neighbors. Original alpha bits
are preserved, including subnormals/signed zero; active fully transparent RGB is
zero. Intensity/gain zero or black tint is a byte-exact no-op, with no GPU dispatch.
Halation radius0/core_suppression1 is also a no-op. Light can exceed1: preview
clipping and choose explicit delivery range behavior.

Dry-run/apply composition → validate → preview → render → inspect encoded result →
export editable package. Use `--projection-acceleration off|prefer|require` under the
existing policy. Actual OpenCL uses four kernels, three owned device buffers,
Float32 intermediate surfaces, binary64 accumulation and one final download.
`operations.glow` counts edited-frame operations; `native.operations` also includes
startup probes. Main probe kernels total17 with this version; auxiliary subnormal
probes are separate. Read device/kernel hashes and worker/shared/thread/stream
cleanup. GPU encoding and model inference are separate capabilities.

Workspace admission includes full spatial scratch plus bounded tiles/LUTs, up to
768MiB; per-frame neighbor visits are capped at2^32. These are operator budgets,
not total RSS or global GPU reservations. Large frames/sigmas can be rejected.

For customer selection, show the actual original, before/contact PNG and GIF/MP4
from [C49](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/CASES.md#c49-highlight-glow).
Its original/Bloom/Halation/combined panels retain six numeric tracks in an editable
package. Explain brightness threshold, spread radius, tint and strength, then test
on the customer's footage and record the choice. Do not substitute a mock preview.

[Full runnable workflow and parameter details](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/HIGHLIGHT_GLOW.md).
Package/local OTIO preserve parameters; external renderers may not execute them.
Natural footage, physical film accuracy, HDR, real-time/4K performance and the complete
CapCut library remain unaccepted. Keep still inspection, playback and listening distinct.
