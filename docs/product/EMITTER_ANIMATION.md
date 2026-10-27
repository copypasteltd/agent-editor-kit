# 发射器关键帧 / 發射器關鍵影格 / Emitter keyframes

CLI0.1.37 / alpha.4-local.35 / r38. The installed CLI and unified
`$agent-ffmpeg-local-editor` author editable particle parameter animation, with
native Float32 CPU composition or probed OpenCL particle rasterization. Recipes
and implementation are original MIT code; no model, footage or network needed.

## Usage / 使用流程

Use the [verified local installation](COMMUNITY_LOCAL_DELIVERY.md) and its
registered Skill launcher. The example uses 90,000 ticks/second and a four-second
snow source. For existing projects inspect their actual generator clock first.

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
$project = 'E:/dev/sandbox/emitter-animation-demo'
& $avk version
& $avk project init $project
& $avk vfx animation-properties
& $avk vfx apply --project $project --preset snow --seed 73 --clip-id snow --duration-tick 360000 --enable-native
$keys = Join-Path $project 'position-keys.json'
'[{"at_tick":0,"value":[0.15,0.1],"interpolation":"ease_in_out"},{"at_tick":360000,"value":[0.85,0.1]}]' | Set-Content -LiteralPath $keys -Encoding UTF8
& $avk vfx animate --project $project --clip-id snow --emitter-index 0 --property position --keyframes $keys --dry-run
& $avk vfx animate --project $project --clip-id snow --emitter-index 0 --property position --keyframes $keys
& $avk vfx show --project $project --clip-id snow
& $avk validate --project $project
& $avk preview frame --project $project --frame 30 --height 360
& $avk render --project $project --output (Join-Path $project 'renders/snow.mp4') --projection-acceleration require --projection-device 0.0
& $avk convert export --project $project --target-format package --output (Join-Path $project 'exports/editable-snow.aevpkg.zip')
```

Default project FPS is independent of source ticks; inspect `vfx show` and the
project settings to choose a preview frame. Set the actual GPU device reported by
`doctor`; `require` refuses unavailable GPU, `prefer` records preflight CPU
fallback and `off` selects CPU. Rasterization is GPU work; birth scheduling,
hashing, parameter evaluation and tile binning remain CPU. GPU encoding is an
independent option. Existing media require explicit source signals when enabling
the native linear pipeline; see [particle workflow](PROCEDURAL_PARTICLES.md).

Adding an existing property fails until `--replace` is explicit. To clear only
that track and recover its static base value:

```powershell
& $avk vfx animate --project $project --clip-id snow --emitter-index 0 --property position --remove --dry-run
& $avk vfx animate --project $project --clip-id snow --emitter-index 0 --property position --remove
```

`--sequence-id`/`--track-id` target another sequence or track. Locked tracks fail
atomically. Updates retain clip timing, transforms, masks and other tracks, with
normal project snapshots, dry-run and idempotency. UTF-8 point files are capped
at 1MiB; their content participates in request identity. Change an idempotency key
when changing the file. Complete `--config` recipes may also contain tracks.

## All 21 properties / 完整属性

Values animate whole pairs/matrices/palettes, rather than component paths.
Ranges below apply to every key and the static recipe. A pair described as a
range must stay ordered. Positions and velocities use source canvas dimensions.

| Property | Clock | Value, units and behavior |
|---|---|---|
| rate | integrated source time | 0…1024 particles/s; zero pauses births, retaining older live particles. |
| lifetime | at birth | [min,max], 0.01…120 seconds. |
| position | at birth | [x,y], each −4…4 in source canvas widths/heights. |
| spread | at birth | [width,height], each 0…8; symmetric random box around position. |
| velocity | at birth | [[xmin,xmax],[ymin,ymax]], −8…8 dimensions/s. |
| acceleration | at birth | [x,y], −8…8 dimensions/s²; retained for that particle. |
| rotation | at birth | [min,max], −36000…36000 degrees. |
| spin | at birth | [min,max], −36000…36000 degrees/s. |
| sway | at birth | [amplitude,frequency], 0…2 source widths and 0…16 Hz. |
| twinkle | at birth | [depth,frequency], 0…1 opacity depth and 0…16 Hz. |
| size | live source time | [min,max], 0.0001…0.5 of source height; stable per-birth random selector. |
| size_end | live source time | 0…4 final/initial radius ratio, evaluated at each particle's normalized age. |
| aspect | live source time | 0.05…20, x radius / y radius. |
| shape | live source time | disc, rectangle, diamond, star or ring; hold transitions only. |
| softness | live source time | 0…1 edge softness; antialiasing still applied. |
| glow | live source time | 0…1 analytic halo amount. |
| colors | live source time | 1…32 `#RRGGBB` sRGB colors; converted/interpolated in linear BT.709. |
| color_end | live source time | `#RRGGBB` or null; life-age color endpoint, null switches require hold. |
| opacity | live source time | 0…1 base coverage. |
| fade_in | live source time | 0…1 fraction of each particle's lifetime. |
| fade_out | live source time | 0…1 lifetime fraction; overlapping fades multiply. |

Birth-sampled motion parameters affect newly born particles, preserving older
cohorts' lifetime, position and motion equations. Live appearance affects all
living particles. Seed, prewarm, source FPS/canvas/clock and duration retain
static source identity and are not animatable fields. Individual birth IDs derive
the same random values regardless of preview order, cache state or render chunks.

Each emitter stores `keyframes: [{property, keyframes: [{at_tick,value,
interpolation,control_points?}]}]`. Ticks are unique integers in the original
generator's 0…duration range. Up to 64 points/property, 21 distinct properties.
Before the first key its first value is held; after the last its last value is
held. Absent tracks use static recipe values. Hold/linear/ease_in/ease_out/
ease_in_out/bezier are supported. Bezier requires two or four controls in 0…1,
with no overshoot. A left key controls the following segment. Shape/null switches
and changing palette cardinality require hold; continuous palettes retain their
length. First/last-key conventions also apply to negative-time prewarm births.

## Time, resources and interoperability

`source-anchored-emitter-keyframes-v1` integrates rate with rational polynomial
pieces. Integer integrated phases yield stable births. Nonlinear inverse uses
64 rational bisections, a deterministic lower bound within segment seconds/2^64;
exact constant intervals, integral endpoints and coincident authored key ticks
retain exact rational times. Bezier follows the common serialized 32-piece
easing lookup; its integral is exact for that lookup, not an analytic cubic
Bezier integral. Cancellation is polled during inverse evaluation.

Pause intervals never reseed the emitter. Birth 0 starts the first interval with
positive integral; prewarm uses the initial rate and first property values with
negative IDs. Source-frame sampling remains half-open. Trim, slip, reverse,
freeze, speed curves, nested sequences and output FPS map to this same original
source clock. Seeking never steps a simulation from the beginning.

Conservative admission sums `ceil(max_rate × max_lifetime) + 1` per nonzero
emitter, capped at 4096. All authored key maxima participate even if peaks occur
at different times. Zero-rate emitters reserve zero births. Per-emitter inverse
and birth-parameter caches are bounded to twice their reservation (2…8192
entries); these are work bounds rather than process RSS/global VRAM guarantees.
Other particle pixel, duration, emitter, visit and GPU work-buffer quotas remain.

Native preview/cache, direct render and persistent queue include curve content
and implementation hashes in their dependencies. Project packages preserve every
track; local OTIO reimport retains them. Foreign OTIO renderers may not implement
AgentParticles; MLT/draft/legacy FFmpeg filters cannot execute this source. Full
multi-sequence editing graphs should use project packages.

## Actual demo / 實際案例

[C47 four-cell case](CASES.md#c47-emitter-animation) uses 14 tracks in moving
trail, timed confetti, live color/shape and star-easing panels. The registered
installed Skill creates and GPU-renders 48 frames at 12 FPS/640×360/4 seconds.
Its package reimport preserves all tracks, all 48 decoded 10-bit frames and the
complete 384000 interleaved Float32 PCM scalars. The silent diagnostic audio does
not establish speech quality or human listening acceptance. GIF timing uses
10ms cumulative rounding for exactly four authored seconds.

![Actual GPU-rendered emitter animation, decoded and labeled](../assets/emitter-animation-20261027-r1/emitter-animation.gif)

[Actual MP4](../assets/emitter-animation-20261027-r1/emitter-animation.mp4) ·
[Lossless master](../assets/emitter-animation-20261027-r1/emitter-animation.mkv) ·
[Editable package](../assets/emitter-animation-20261027-r1/editable-emitter-animation.aevpkg.zip) ·
[Recipes](../assets/emitter-animation-20261027-r1/recipes.json) ·
[Before: same source without tracks](../assets/emitter-animation-20261027-r1/before.png) ·
[At 2s](../assets/emitter-animation-20261027-r1/contact.png) ·
[Sources/license](../assets/emitter-animation-20261027-r1/SOURCE.txt) ·
[Installed verification](../validation/发射器关键帧实测_2026-10-27.md).

This closes emitter parameter animation within the analytic 2-D particle source.
3-D emitters, collisions, depth occlusion, fluid simulation and the full editable
CapCut-scale effect library remain separate development requirements. The original
38 product closure conditions are retained; this batch does not close the goal.
