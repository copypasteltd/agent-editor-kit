# 可编辑粒子 / Editable procedural particles

CLI 0.1.35 adds a versioned, random-access particle source to the native Float32
timeline. It runs on native Windows with the offline NumPy installation, existing FFmpeg tools and an
optional render-owned OpenCL GPU worker. No models, external assets, services or
downloads are needed. This is one component of G06; full CapCut parity remains open.

## 使用流程 / Workflow

Use the single installed Skill `$agent-ffmpeg-local-editor` and its launcher:

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk vfx list
& $avk vfx inspect --name snow
& $avk project init 'E:/dev/sandbox/particle-demo'
& $avk vfx apply --project 'E:/dev/sandbox/particle-demo' --preset snow --seed 73 --clip-id snow --duration-tick 360000 --enable-native --dry-run
& $avk vfx apply --project 'E:/dev/sandbox/particle-demo' --preset snow --seed 73 --clip-id snow --duration-tick 360000 --enable-native
& $avk vfx show --project 'E:/dev/sandbox/particle-demo' --clip-id snow
& $avk preview frame --project 'E:/dev/sandbox/particle-demo' --frame 30
& $avk render --project 'E:/dev/sandbox/particle-demo' --output 'E:/dev/sandbox/particle-demo/renders/snow.mp4' --projection-acceleration require --projection-device 0.0
& $avk vfx update --project 'E:/dev/sandbox/particle-demo' --clip-id snow --preset embers --seed 73 --dry-run
```

The default project clock is 90,000 ticks/s; 360,000 ticks means four seconds.
Use an absolute output path within the selected project; relative output paths
resolve against the calling working directory.
Read the actual project clock for existing projects. `--enable-native` explicitly
selects linear BT.709 compositing and sRGB output transfer, with matching color tags.
Existing video/image assets require `--source-signals` with their explicit
`pixel_pipeline.sources` declarations; the command does not guess source signals.
Existing native pipeline settings are preserved. `require` fails on unavailable
GPU; `prefer` permits a recorded preflight CPU fallback; `off` uses CPU.
The particle GPU handles coverage, glow and ordered compositing; hash sampling,
birth/motion evaluation, binning, color conversion and encoding retain their
documented CPU/native encoder paths. GPU selection does not imply GPU encoding.

`vfx apply` adds an independent video/overlay clip, making an overlay track when
none is specified. `--track-id` targets an existing visual track.
`--start-tick`, `--duration-tick`, and optional `--source-duration-tick` control
placement, visible duration and finite source extent. A longer source gives
real handles for later slip/extension. `--sequence-id` selects a sequence.
`--config` accepts a complete generator JSON instead of a preset. `vfx update`
replaces the source recipe while keeping IDs, visible/source ranges, transforms,
automation and masks. A shorter replacement source is rejected if the current
clip needs frames beyond it. Every mutation supports a read-only dry-run and the
ordinary project snapshot/transaction machinery.

Configuration and source-signal files must be readable UTF-8 JSON, at most 1MiB.
Malformed, missing or oversized files return a structured `PARTICLE_JSON` error
without changing the project. Both file contents participate in the ordinary
idempotency fingerprint: changing content at the same path rejects an old key
with `IDEMPOTENCY_CONFLICT` instead of replaying a stale edit.

## 六个原创建效配方 / Six original recipes

All recipes are version 1.0.0, MIT, authored within agent editor kit, with zero
external resource dependencies. `vfx inspect` returns every authored override;
`vfx show` returns the complete normalized recipe used by the renderer.

| ID | 实际画面与运动 / Appearance and motion | 发射率、寿命与尺寸 / Rate, life, radius | 使用边界 / Limits |
|---|---|---|---|
| snow | 白色柔边圆片下落；横摆幅度 .018、频率 .32Hz，终尺寸 .7，透明度 .75。 | 38/s；3–6s；画布高的 .0025–.009。 | 冬季氛围；无人物深度遮挡。 |
| confetti | 五色矩形，宽高比 .5；自转 −200–200°/s，垂直加速度 .06，透明度 .95。 | 38/s；2.5–4.5s；.004–.011H。 | 二维彩纸；无三维翻面或碰撞。 |
| embers | 底部黄橙颗粒上升变暗红；光晕 .75，闪烁深度 .35、2.1Hz；终尺寸 .15。 | 26/s；2–5s；.0015–.006H。 | 气氛余烬；无火焰生成、真实物体照明。 |
| bokeh | 金/玫瑰/蓝大圆光斑缓慢上升；柔边 .85、光晕 .3、透明度 .28、终尺寸 1.2。 | 5/s；4–8s；.025–.08H。 | 装饰光斑；非真实景深或镜头失焦恢复。 |
| rain | 蓝灰细长矩形，宽高比 .06，旋转 −10°；垂直速度 1.1–1.5H/s，透明度 .38。 | 105/s；.7–1.1s；.00065–.0012H。 | 二维斜雨；无水花、折射、湿润材质。 |
| sparkles | 金白五角星，自转 −30–30°/s；光晕 .4、闪烁深度 .8/1.8Hz、终尺寸 .3。 | 12/s；1.2–3s；.003–.016H。 | 点缀星芒；不会自动识别或跟踪高光。 |

## 可编辑参数 / Parameter contract

The generator is stored directly on the clip. No baked video replaces its source:

```json
{
  "type": "particles",
  "protocol": "analytic-seeded-particle-source-v1",
  "seed": 73,
  "canvas": {"width": 640, "height": 360},
  "fps": {"num": 30000, "den": 1001},
  "duration_tick": 360000,
  "ticks_per_second": 90000,
  "emitters": [{"rate": 38, "colors": ["#ffffff"], "shape": "disc"}]
}
```

Unspecified emitter fields use versioned defaults; unknown fields fail. Defaults
are expanded by `vfx show`. The shipped offline schema validates types/shape and
the runtime additionally enforces ordered ranges, rational FPS, duration, total
active particles and raster budgets.

| 字段 / Field | 单位、语义与边界 / Units and meaning |
|---|---|
| seed | Integer 0…2^63−1. SHA-512 sampling per emitter/birth; frame order and NumPy RNG state have no effect. |
| canvas, fps, duration_tick, ticks_per_second | Independent source raster, rational 1…120 FPS and finite source extent ≤600s. Source samples hold on half-open CFR intervals; reverse uses exact left limits. Partial final frames do not extend the declared source extent. |
| emitters | 1…16; ordered layers, then ascending birth ID. Same-frame translucent overlap preserves that order. |
| rate, lifetime | Births/s (.01…1024); random ordered life range in seconds (.01…120). `prewarm=true` includes negative birth IDs alive at source time zero. |
| position, spread | Center in normalized canvas X/Y (−4…4); full initial random spread width/height (0…8). |
| velocity, acceleration | Two ordered initial X/Y velocity ranges in widths/heights per second (−8…8), plus X/Y acceleration per second² (−8…8). Trajectory is analytical. |
| size, size_end, aspect | Ordered initial X-radius range in canvas heights (.0001….5); terminal size multiplier (0…4); X/Y radius ratio (.05…20). |
| rotation, spin | Ordered initial degrees and degrees/s (±36000). Rotated rectangle bounds include the corners. |
| shape, softness, glow | disc / rectangle / diamond / star / ring; coverage softness and Gaussian halo strength 0…1. Glow is truncated at four radii with finite raster support. |
| colors, color_end | 1…32 sRGB #RRGGBB colors; optional terminal color. Palette and end colors convert to linear BT.709 before interpolation/over; conversion into another explicitly selected linear working gamut is recorded. |
| opacity, fade_in, fade_out | Overall coverage 0…1; fade fractions of each particle's life 0…1. Overlapping fade regions multiply. |
| sway | Horizontal sinusoidal amplitude in canvas widths (0…2) and frequency Hz (0…16); anchored to each particle's birth position. |
| twinkle | Opacity modulation depth 0…1 and frequency Hz 0…16, with per-particle phase. |

Source motion parameters are static within a source recipe. Use ordinary clip
TRS/opacity keyframes, masks, blend modes, transitions, reverse, speed curves,
freeze, presentation-window cuts and nesting to animate and edit the result.
Emitter-parameter keyframe tracks, collisions, 3-D emitters, depth/occlusion,
fluid simulation and AI-generated effects are not implemented by this source.

## 有界执行、迁移与验收 / Execution and delivery

The source allows at most 4,096 conservatively reserved live particles, a
4096×2160 pixel budget and 128Mi candidate pixel visits per frame. The CPU uses
bounded row strips; GPU uses 32×32 CSR tile lists in stable order, validates all
device indices before dispatch and retains the existing render worker lifecycle
and memory quotas. Limits are work-buffer/admission bounds, not a process RSS or
global free-VRAM reservation. Cancellation is polled during scene generation,
binning, CPU strips and GPU wait. A single bounded kernel dispatch is reclaimed
by terminating its owned worker when cancelled; no unrelated process is killed.

The native standard render, preview/cache and persistent queue consume the same
editable IR. The legacy FFmpeg filter graph reports
`PARTICLE_NATIVE_PIPELINE_REQUIRED`; it never silently omits a particle clip.
Seed/recipe changes invalidate the author fingerprint; implementation hashes are
included in render dependencies and the common preview/queue runtime inventory.

Agent JSON and project packages preserve complete source parameters. OTIO uses
`GeneratorReference.1` + Agent metadata and preserves native settings/background
and source signal ID mappings for local reimport. Other OTIO players do not
necessarily render AgentParticles. Additional/nested sequences retain the
existing OTIO export limits; use project packages for a full multi-sequence graph.
MLT and draft formats cannot execute this generator; their conversion reports
must be checked before delivery. No CapCut runtime is required.

[Actual C45 media and editable package](CASES.md#c45-procedural-particles) ·
[Installed build](../releases/CLI_0.1.35_LOCAL.md) ·
[Verification and failed attempts](../validation/可编辑粒子实测_2026-10-27.md).
