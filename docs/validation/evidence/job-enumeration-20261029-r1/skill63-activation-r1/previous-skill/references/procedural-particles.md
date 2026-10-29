# Editable particles / 可编辑粒子

Use the installed launcher for `vfx list`, `vfx inspect --name ID`,
`vfx apply`, `vfx update` and `vfx show`. The six original MIT recipes are
snow, confetti, embers, bokeh, rain and sparkles; all numeric parameters remain
in `clip.generator` under `analytic-seeded-particle-source-v1`. No external
asset/model downloads or services are needed.

For a new project at the default 90,000 ticks/s:

```powershell
& $avk vfx apply --project $project --preset snow --seed 73 --clip-id snow --duration-tick 360000 --enable-native --dry-run
& $avk vfx apply --project $project --preset snow --seed 73 --clip-id snow --duration-tick 360000 --enable-native
& $avk vfx show --project $project --clip-id snow
& $avk render --project $project --output (Join-Path $project 'renders/snow.mp4') --projection-acceleration require --projection-device 0.0
```

`--enable-native` explicitly selects linear BT.709 compositing/sRGB output.
Existing video/image media require explicit `--source-signals` declarations;
do not guess their transfer, alpha or YUV interpretation. Already configured
native settings are retained. `require` fails if the GPU is unavailable;
`prefer` records preflight CPU fallback; `off` is CPU. Hash/motion/binning and
color conversion stay on CPU; particle rasterization/compositing uses the
actual OpenCL worker. This does not enable GPU encoding.

For client selection, show the actual C45 contact sheet/GIF and identify the
selected recipe, seed and preview time. Inspect the current `vfx inspect`
recipe; show normalized current values using `vfx show`. Snow is drifting white
discs; confetti is rotating five-color rectangles; embers rise and fade red;
bokeh is soft large pastel circles; rain is narrow blue-gray falling rectangles;
sparkles are rotating gold/white stars. Previews are procedural 2-D overlays,
not a claim of AI effects, collisions, depth or material lighting.

`--config` accepts a complete generator JSON; unknown parameters fail.
Config/signal files are UTF-8 JSON capped at 1MiB; bad files fail without mutation.
File contents are included in idempotency checks; use a new key after changing them.
`vfx update` preserves the target's time ranges, transforms, keys and masks.
`--source-duration-tick` on apply reserves a longer finite source for later
slip/extension. Use the actual project clock, sequence/track IDs and normal
timeline editing APIs. Half-open source FPS samples, reverse, speed curves,
freeze, windows and nesting preserve particle identity. CLI0.1.37 adds source-
clock emitter tracks for all 21 scalar/vector/palette properties. Ordinary clip
TRS/opacity/mask keys still act on the composed result.

## Animate the editable emitter

```powershell
& $avk vfx animation-properties
# UTF-8 JSON array; original generator ticks, not output frame numbers.
$emitterKeys = Join-Path $project 'position-keys.json'
'[{"at_tick":0,"value":[0.2,0.7],"interpolation":"ease_in_out"},{"at_tick":360000,"value":[0.8,0.3]}]' | Set-Content -LiteralPath $emitterKeys -Encoding UTF8
& $avk vfx animate --project $project --clip-id snow --emitter-index 0 --property position --keyframes $emitterKeys --dry-run
& $avk vfx animate --project $project --clip-id snow --emitter-index 0 --property position --keyframes $emitterKeys
& $avk vfx show --project $project --clip-id snow
```

Use `--replace` only to replace an existing property; `--remove` removes one
track and restores its static recipe value. Track locks, snapshots, validation,
dry-run and content-aware idempotency remain active. Change the idempotency key
when changing a keyframe file. The source must reserve every authored key tick.

- `rate`: integrate particles/second over source time; zero pauses new births.
  Existing live particles continue. Birth IDs and samples stay stable during seek.
- Birth-sampled: `lifetime`, `position`, `spread`, `velocity`, `acceleration`,
  `rotation`, `spin`, `sway`, `twinkle`. A later key affects subsequent births;
  it does not teleport earlier particles or rewrite their lifetime/motion.
- Live appearance: `size`, `size_end`, `aspect`, `shape`, `softness`, `glow`,
  `colors`, `color_end`, `opacity`, `fade_in`, `fade_out`. These affect all live
  particles at the sampled source time. Colors interpolate in linear BT.709.

Each property accepts up to 64 unique integer ticks in 0…source duration,
with hold/linear/ease_in/ease_out/ease_in_out/bezier. Whole pairs, velocity
matrices and palettes are key values, not component paths. Bezier controls are
two or four numbers in 0…1; overshoot is rejected. Shape and nullable end-color
switches require hold. Continuous palettes require equal color counts; use hold
to change that count. Before/after authored keys the first/last value is held.
Prewarm uses the initial rate and first property values, with negative birth IDs.
Seed, prewarm, source canvas/FPS and duration are static identity fields.

For clients, show actual C47 GIF/contact, identify the cell, property, clock,
seed and time. Save accepted key tracks in the project package; do not present
a recipe label as evidence of rendered appearance. C47 has 14 authored tracks,
48 decoded frames and full PCM equality after package reimport.

Limits: 16 emitters, 4,096 reserved live particles, 4096×2160 pixel budget,
1…120 source FPS, 600 seconds and 128Mi candidate pixel visits per frame;
configured CPU/GPU work-buffer limits remain enforced. GPU/CPU precision is
checked in premultiplied light and alpha; straight RGB near zero alpha can
amplify small numerical differences. No global VRAM reservation is implied.

Use project packages to preserve editable recipes. Local OTIO reimport restores
the generator and native settings; external OTIO viewers do not necessarily
support AgentParticles. Legacy FFmpeg graphs explicitly reject these sources;
do not remove a generator merely to make a render pass. Review foreign-format
conversion reports. The C45 evidence is a diagnostic scene; it does not accept
natural footage, all CapCut effects or full product parity.

Full parameters, recipe descriptions and actual media:
`docs/product/PROCEDURAL_PARTICLES.md`, `docs/product/CASES.md#c45-procedural-particles`,
`docs/assets/procedural-particles-20261027-r3/`, and
`docs/validation/可编辑粒子实测_2026-10-27.md` in the project checkout.

[Actual contact sheet](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/procedural-particles-20261027-r3/contact.png) · [Actual annotated GIF](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/procedural-particles-20261027-r3/particle-grid.gif) · [Editable C45 workflow](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/PROCEDURAL_PARTICLES.md).

[Emitter animation workflow and all constraints](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/EMITTER_ANIMATION.md) · [Actual C47 animation GIF](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/emitter-animation-20261027-r1/emitter-animation.gif) · [Editable C47 case](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/CASES.md#c47-emitter-animation).
