# Native GPU projection (initial CLI 0.1.24; current additions below)

CLI0.1.39 also runs [highlight Bloom and Halation](highlight-glow.md).
Each active glow operation uses four device kernels with one final
readback; intermediate images stay on device. Seventeen named main
probe kernels include eight glow kernels; auxiliary subnormal probes
are separate. `operations.glow` counts edited-frame work.


CLI0.1.38 additionally runs [analytic optical effects](optical-effects.md) on
the native linear Float32 GPU backend, alongside the existing seeded particle
rasterization. Nine named main probe dispatches include three actual optical
cases; all prior precision/subnormal checks remain. Optics use binary64 math,
particles retain their existing Float32 raster math. `operations.optics` and
`operations.particles` report edited-frame work separately from probes.
The historical CPU-effects statements below exclude these native additions.

Read this for an edit with animated crop, affine camera keys or native child
canvases when GPU composition is requested. Use the installed launcher from
`runtime.md`. This backend needs the existing Windows OpenCL ICD, a GPU with
images and IEEE binary64, and FFmpeg with `program_opencl`. It downloads nothing.

```powershell
& $avk validate --project $project
& $avk render --project $project --sequence-id $sequence --output $output --projection-acceleration prefer --projection-device 0.0 --projection-memory-mib 1024 --sequence-sampling area --sequence-memory-mib 1024 --hardware-encode off
```

Choose the policy explicitly:

- `off`: CPU projection, the default.
- `prefer`: GPU for admitted pure projection nodes. Unsupported device/format,
  stateful or pixel expressions, and over-quota nodes use CPU with reasons.
- `require`: every requested projection must be supported; missing device,
  unsupported nodes or no applicable projection fail. Running GPU errors,
  cancellation and timeout fail; they never become successful CPU renders.

`0.0` is platform 0/device 0, not a promise about the machine's device order.
Read `data.projection_acceleration` and its retained `report.json`: actual device,
driver, chosen nodes, kernel hashes, admission bytes, coefficient/texture probes,
logs and final status. A `planned` response proves no GPU execution. A successful
`prefer` render can report `cpu_fallback` or mixed CPU/GPU nodes.

GPU composition and hardware encoding are independent. `--hardware-encode`
accepts `off|prefer|require`, not `auto`. If choosing hardware encoding, also
provide the explicit supported video bitrate. Voice/translation retain their
separate configured `auto` device policy.

Per-frame AVExpr coefficients retain authored PTS, Bezier and hold clocks.
Binary64 coefficient transport and actual gbrap8/Float32 texture round trips
are checked before rendering. Bilinear/area sampling keeps premultiplied alpha.
Area uses the existing source-axis rectangle footprint, not a rotated polygon.
This FFmpeg graph backend keeps effects, subtitles and blending on CPU.
The independent linear-light `pixel_pipeline` uses the separate backend below.

`projection-memory-mib` conservatively admits cumulative raster slots, including
area prefix textures. It is separate from `sequence-memory-mib` and is not a
total RAM/VRAM limit. Keep explicit quotas; do not lower quality or enlarge
budgets silently. Do not stop other GPU tasks. Review full-resolution delivery
and actual output rather than extrapolating a short graphic benchmark.

Queue JSON supports `projection_acceleration`, `projection_device` and
`projection_memory_mib` at job level. GPU projection jobs reject
`queue run --reuse-identical` so each job retains its own device probe.
Resume retains saved render settings and requires identical fingerprints;
changing device/policy requires a new render, not a modified resume.
Use `render --dry-run` to inspect planned nodes without creating a GPU context.

The [workflow and editable case](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/OPENCL_PROJECTION.md)
provides actual media, benchmark evidence and the current tested device scope.
Machine equality, still inspection, continuous playback and human listening
remain separate checks. Full CapCut parity has not been accepted.

## Independent linear Float32 pipeline

With `settings.pixel_pipeline.engine = "float32-native-v1"`, the same
`projection_acceleration` setting selects `render-owned-float32-opencl-v1`.
It uses the existing Windows OpenCL ICD directly, without FFmpeg
`program_opencl`, a model server, download or virtual environment.

```json
"projection_acceleration": {
  "mode": "require",
  "device": "0.0",
  "max_working_bytes": 1073741824,
  "probe_timeout_seconds": 30
}
```

Set this in the editable project for previews and queue jobs. A render can
also supply `--projection-acceleration require --projection-device 0.0
--projection-memory-mib 1024`. Retain explicit linear working/output signals,
local font registration and `sequence_sampling.method = "bilinear"`.
Hardware encode/decode stay `off` in this pipeline.

GPU work covers premultiplied bilinear affine sampling, normal source-over,
ordered text box/shadow/border/fill colors, whole-paragraph source-over and
binary word selection. Native glyph rasterization, crop/masks, effects,
transitions, other blends, signal conversion, audio and encoding remain CPU
operations and appear in `CPU_scope`. Here `require` requires the declared
GPU primitives and a nonempty actual operation receipt, not every editor
operator to run on GPU. `prefer` permits a recorded preflight CPU fallback;
execution failure, cancellation or timeout never silently retry on CPU.

Before execution, the render-owned process compares GPU operations against
independent CPU oracles, including all 65,536 native gray levels. Arithmetic
is binary64 without fast math, with explicit Float32 component boundaries;
media pixels do not pass through an 8bit GPU conversion. Glyph coverage is
still 8bit. Original author clocks, paragraph selection and animation alpha
semantics are retained.

Inspect `data.projection_acceleration` and the matching `cache/float-gpu/*/
receipt.json`: actual device/driver, kernel and execution hashes, probe errors,
actual per-operator counts, worker PID/exit, shared-handle cleanup and final
status. `probe` operations are separate from the edited-frame `operations`.
A dry run creates no GPU context, worker or shared buffers.

There are at most three retained device buffers and three shared host
segments per render. The requested quota independently bounds each pool;
the combined process memory and free VRAM are not reserved or measured by
these limits. At 4K, three full Float32 device buffers use 398,131,200 bytes.
Existing source/text caches and CPU workspaces have separate ceilings. Keep
other GPU jobs running and retain explicit budgets. Cancellation and timeout
terminate only this task's owned process, then close its shared handles.

The [Float32 GPU contract and cases](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/FLOAT_GPU.md)
contains installed-package evidence and measured performance. Inspect actual
full-resolution output; this scope does not establish realtime or complete
CapCut quality parity.

## Owned control pipes, CLI0.1.36

The installed native Float32 backend uses `owned-inherited-binary-pipes-v1`.
No per-operation JSON files or network service are needed; media pixels still
use the same three owned shared buffers. Project/snapshot/manifest/queue and
receipt durability remain active. There is one bounded send/receive queue,
each with capacity1; each UTF-8 JSON packet body is bounded to128KiB.
Inspect `projection_acceleration.control.protocol`, `sent_packets`,
`received_packets`, `threads_closed` and `streams_closed`, together with
`worker_closed`/`shared_handles_closed`. Runtime errors must fail and close
the owned process rather than silently retry on CPU. Existing GPU policy,
commands, author clocks and kernel precision remain the same.

For measured all-frame/PCM before-after checks and their scope, read
[GPU dispatch](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/GPU_DISPATCH.md).
Do not promise realtime or extrapolate one diagnostic timing to client footage.

## CLI52 GPU colour addition

Read [gpu-gamut.md](gpu-gamut.md) for actual luminance shoulder/OKLab chroma
search. Native GPU scope now includes this operator; signal conversion and ICC
remain CPU. Inspect `operations.gamut_map`, not merely GPU preparation status.
