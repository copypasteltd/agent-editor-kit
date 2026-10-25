# Native GPU projection (CLI 0.1.20)

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
Other effects, subtitles and blending still run on CPU; the independent
linear-light `pixel_pipeline` is not supported by this OpenCL backend.

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
