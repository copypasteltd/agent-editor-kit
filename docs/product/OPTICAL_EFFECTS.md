# 光学效果 / 光學效果 / Optical effects

CLI0.1.38 / alpha.4-local.36 adds original MIT **lens flare, light leaks and
chromatic aberration** to the editable native Float32 effect chain. They work
on clips and selected-sequence adjustment intervals, with numeric keyframes,
CPU reference math and actual render-owned OpenCL GPU kernels. No model or
network is required. See [C48](CASES.md#c48-optical-effects) for the actual output.

## 使用 / Usage

Use the [verified local installation](COMMUNITY_LOCAL_DELIVERY.md) and the
single registered `$agent-ffmpeg-local-editor` entry. Starting from the complete
editable case is the shortest reproducible workflow:

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
$project = 'E:/dev/sandbox/optical-study'
$package = 'E:/dev/sandbox/AI广告剪辑/docs/assets/optical-effects-20261027-r3/editable-optical-effects.aevpkg.zip'
& $avk version
& $avk effects list --query optical --keyframable-only
& $avk effects inspect --name lens_flare
& $avk effects inspect --name light_leak
& $avk effects inspect --name rgb_split
& $avk convert import --input $package --output $project
& $avk validate --project $project
& $avk preview frame --project $project --frame 24 --height 540
& $avk render --project $project --output (Join-Path $project 'renders/optical.mkv') --container mkv --video-codec libx264 --crf 0 --pixel-format yuv444p10le --audio-codec pcm_f32le --projection-acceleration require --projection-device 0.0 --hardware-encode off
& $avk convert export --project $project --target-format package --output (Join-Path $project 'exports/edited-optical.aevpkg.zip')
```

Set the device index from the actual machine. `off` selects CPU, `prefer`
allows a recorded preflight CPU fallback, `require` rejects failed GPU admission.
Runtime GPU failures, cancellation and timeout fail and close only the owned
worker. Hardware encoding is independent. Previews use project GPU settings;
render flags override only that render.

To revise a clip, use `timeline compose` with `update_clip`. The following
replaces **the entire effects array** for the C48 `lens-flare` clip; retain other
effects in this array if they are wanted. First preview the dry run:

```powershell
$patch = Join-Path $project 'optical-patch.json'
@'
{"operations":[{"op":"update_clip","clip_id":"lens-flare","patch":{"effects":[
  {"id":"moving-light","type":"lens_flare","parameters":{"brightness":0.35,"radius":0.08,"ghosts":6},
   "keyframes":[{"property":"x","keyframes":[
     {"at_tick":0,"value":0.12,"interpolation":"ease_in_out"},
     {"at_tick":360000,"value":0.86,"interpolation":"linear"}]}]}
]}}]}
'@ | Set-Content -LiteralPath $patch -Encoding UTF8
& $avk timeline compose --project $project --input $patch --dry-run
& $avk timeline compose --project $project --input $patch
& $avk validate --project $project
& $avk preview frame --project $project --frame 24 --height 540
```

The sample clock is 90,000 ticks/second, four seconds. Inspect the target clip's
original author duration before copying keys. Removing a channel restores its
static parameter value. `enabled:false` disables that effect. Unknown fields,
nonfinite numbers, invalid bounds and keys beyond author duration fail validation.
Normal project locks, snapshots, dry runs and idempotency still apply.

## 参数 / Parameters

All numeric parameters below accept original-author-clock keyframes. Defaults
and ranges are also returned by `effects inspect`; aliases are `lensflare`,
`lightleak` and `rgb_split`. Colors are **linear RGB components in the explicitly
declared working primaries**, not hex/sRGB values. Coordinates are normalized to
the effect's input image. Radius/width use its shorter dimension; displacement
uses source pixels before clip projection.

| Parameter | Effects | Default | Bounds / behavior |
|---|---|---:|---|
| intensity | all | 1 | 0…1; additive-light gain or split interpolation. Zero is a bit-exact no-op. |
| x / y | flare, leak | .2 / .3 | −1…2; center in input widths/heights; offscreen centers are allowed. |
| x / y | chromatic | .5 / .5 | −1…2; radial split origin. |
| radius | flare, leak | .12 | .005…2 shorter dimensions; Gaussian core/ellipse scale. |
| angle | flare, leak | 0 | −360…360 degrees; rotates streak/ellipse. |
| red / green / blue | flare, leak | 1 / .55 / .25 | 0…4 per linear working component; no implicit display-gamma conversion. |
| brightness | flare, leak | 1 | 0…8 additive light. Zero or all-zero tint is an exact no-op. |
| streak | flare | .5 | 0…8 anisotropic exponential streak weight. |
| streak_width | flare | .008 | .001….25 shorter dimensions. |
| halo | flare | .3 | 0…4 Gaussian ring weight; ring radius 2.7×core, radial sigma .22×core. |
| ghost_spacing | flare | .55 | .1…2; position increments along source-to-image-center vector. |
| ghosts | flare | 6 | **Static integer** 0…12; attenuated analytic colored rings. |
| aspect | leak | 2 | .05…20; ellipse's rotated y radius / x radius. |
| red_shift / blue_shift | chromatic | 3 / −3 | −64…64 source pixels; green stays at its original sample. |
| falloff | chromatic | 1 | 0…4 radial exponent; multiplier = min(2×normalized radial distance,4)^falloff. |
| edge | chromatic | clamp | **Static enum** clamp or transparent; transparent samples contribute no coverage. |

Flare adds a radial Gaussian core, exponential horizontal streak, halo and up
to 12 ghosts. Leak adds a rotated elliptical Gaussian. These are analytic
artistic effects, without lens calibration, scene brightness detection or a
physical ray-traced lens claim. Chromatic splitting bilinearly samples
premultiplied color/coverage, normalizes the sampled channel by coverage and
interpolates red/blue with the original value. It changes color channels while
preserving the input coverage, including transparent sampling at the image edge.

All three preserve original Float32 alpha **bits**, including subnormals and
signed zero. Active zero-alpha pixels have zero RGB. Inactive effects preserve
all input bytes, including hidden RGB. Extended negative/above-one RGB is
retained; the C48 delivery deliberately chooses `range_policy:"clip"`. Review
clipped highlights and colored edges on the client's footage.

## 时钟、执行与互通 / Execution contract

Native working signal must be explicitly linear. Source/output signals,
demux origin and display geometry must follow the existing native input
contract; see [Float32 rendering](FLOAT_TEXT.md) and the editable C48 project.
These effects are refused by the legacy FFmpeg graph with
`FLOAT_OPTICS_NATIVE_PIPELINE_REQUIRED`, rather than silently omitted.

Channels accept hold, linear, ease_in, ease_out, ease_in_out and bezier. A left
key controls its following interval; endpoints hold outside the authored key
range. Up to 1024 keys/channel, 16,384 keys/effect, 4MiB serialized automation.
Bezier uses the common bounded author interpolation implementation. Overshoot
is clamped to parameter bounds. `ghosts` and `edge` cannot be animated.

Clip effects retain original presentation author clocks through splits/windows
and nesting. Reverse native frames sample the previous half-open frame, while
continuous effect keys use the original author's **left-limit clock**; this is
not the previous forward display frame's parameter value. Selected-sequence
adjustments run once after compositing, on their own interval-local author clock.

CPU math uses bounded row tiles. OpenCL uses binary64 math, no fast math and
Float32 output boundaries. Three additional actual optical probe dispatches
bring the named main probe count to nine; earlier 65,536-level/subnormal checks
remain. Probe counts and edited-frame operation counts are separate. Inspect
`projection_acceleration.operations.optics`, device/hash/precision metadata and
worker/shared/control cleanup, not merely an available encoder name.

The existing conservative workspace admission covers six Float32 surfaces,
retained LUT/automation and tile scratch. Surface ceilings: 16,384 per dimension,
16,777,216 pixels, default operator budget at most 768MiB. GPU device/shared pools
retain their separate explicit bounds. These limits are not a combined process
RSS/free-VRAM guarantee or 4K realtime acceptance.

Project packages and local OTIO preserve the editable effects and curves.
Foreign OTIO/MLT/draft renderers may not execute native optical operators; retain
conversion reports and use a rendered movie when the destination cannot render
the effect. Cache keys, queue manifests and runtime identity include the new
CPU/OpenCL implementations. Changes invalidate previous previews/renders.

## 预览与验收 / Preview and acceptance

![Actual registered Skill GPU output](../assets/optical-effects-20261027-r3/optical-effects.gif)

[Original PNG](../assets/optical-effects-20261027-r3/original-source.png) ·
[Before effects](../assets/optical-effects-20261027-r3/before.png) ·
[At 2s](../assets/optical-effects-20261027-r3/contact.png) ·
[MP4](../assets/optical-effects-20261027-r3/optical-effects.mp4) ·
[Editable package](../assets/optical-effects-20261027-r3/editable-optical-effects.aevpkg.zip) ·
[Recipes](../assets/optical-effects-20261027-r3/recipes.json) ·
[Evidence](../validation/光学效果实测_2026-10-27.md).

C48 has original/flare/leak/split panels and nine editable channels. The GIF is
made from actual decoded GPU output with labels; it does not simulate the effects
in an image library. Human continuous playback/listening, natural footage,
physical-lens quality, bloom/halation/depth and the complete CapCut effect library
remain separate, open acceptance work. All original product closure conditions
remain unchanged.
