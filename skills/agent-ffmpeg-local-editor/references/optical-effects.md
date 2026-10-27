# Editable native optical effects

Use the pinned installed launcher from `runtime.md`; read installed capabilities
and `effects inspect` before authoring. Available original MIT operators:
`lens_flare` / `lensflare`, `light_leak` / `lightleak`,
`chromatic_aberration` / `rgb_split`. No external footage/model is required.

```powershell
& $avk effects list --query optical --keyframable-only
& $avk effects inspect --name lens_flare
& $avk effects inspect --name light_leak
& $avk effects inspect --name rgb_split
& $avk timeline compose --project $project --input $composition --dry-run
& $avk timeline compose --project $project --input $composition
& $avk validate --project $project
& $avk preview frame --project $project --frame $chosenFrame --height 540
& $avk render --project $project --output $output --projection-acceleration prefer --projection-device 0.0 --hardware-encode off
```

Author effects in a clip's ordered `effects` array or a selected-sequence
`settings.adjustments` interval. `timeline compose` / `update_clip` replaces
the array: retain all existing wanted effects explicitly. Use native
`float32-native-v1`, declared linear working RGB, explicit source/output signals,
source geometry/origin and delivery range policy. Legacy FFmpeg graphs refuse
these operators. A dry run is not an executed effect or GPU proof.

Each effect has `type`, `parameters` and optional `keyframes`:

```json
{"type":"lens_flare","parameters":{"brightness":0.35,"radius":0.08,"ghosts":6},
 "keyframes":[{"property":"x","keyframes":[
   {"at_tick":0,"value":0.12,"interpolation":"ease_in_out"},
   {"at_tick":360000,"value":0.86,"interpolation":"linear"}]}]}
```

The sample uses four seconds at 90,000 ticks/s. Inspect the actual clip's original
author clock/duration. Six easing modes use common numeric automation. Splits and
windows retain author time. Reverse selects the previous half-open source frame
while continuous effects sample the original author's left limit, not the prior
forward display-frame parameters. Root adjustment clocks are interval-local.

Key parameters and units:

- All: `intensity` 0…1, center `x/y` −1…2 normalized to input dimensions.
- Flare/leak: radius .005…2 shorter dimensions, angle −360…360 degrees;
  red/green/blue 0…4 **linear working RGB**; brightness 0…8 additive light.
- Flare: streak 0…8, streak_width .001….25 shorter dimensions, halo 0…4,
  ghost_spacing .1…2; **static** ghosts integer 0…12, default6.
- Leak: aspect .05…20, rotated y radius / x radius.
- Split: red_shift/blue_shift −64…64 input pixels, falloff 0…4;
  **static** edge clamp|transparent. Green and original alpha stay fixed.

All numeric channels support keys; max1024/channel,16384/effect,4MiB automation.
Original alpha bits survive, including subnormals/signed zero. Active zero-alpha
RGB is cleaned. Chromatic bilinear sampling ignores hidden transparent RGB by
premultiplying and coverage normalization. Zero intensity/brightness or zero
split work is a bit-exact no-op. Additive light can exceed1; retain explicit
range policy and preview highlight clipping. Tint values are not sRGB hex colors.

`off|prefer|require` retains the existing render-owned GPU policy. Actual OpenCL
optics use binary64 math with Float32 boundaries. Read the actual
`operations.optics`, probe/device/kernel hashes and worker/shared/thread/stream
cleanup. Nine named main probe dispatches include three optical cases; probe
success is separate from edited-frame operations. Other effects remain CPU.
Do not conflate GPU optical work with hardware encoding or model inference.

For client selection, show the **actual** original, contact and GIF/MP4 from
[C48](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/CASES.md#c48-optical-effects),
describe the chosen operator/center/color/strength, and test on the client's
footage. The case's four panels compare original, flare, warm leak and color split;
its nine channels remain editable in a project package. The GIF labels are added
to decoded GPU frames. Preserve client decisions and exact output evidence.

Full parameters, runnable import/edit/render workflow, original PNG, recipes,
license and editable package:
[optical workflow](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/OPTICAL_EFFECTS.md).
These are artistic analytic effects. No automatic bright-source detection,
physical lens calibration, bloom/halation/depth or complete CapCut library claim.
Package/local OTIO retain data; external renderers may not execute the operators.
Keep still inspection, continuous playback and human quality/listening distinct.
