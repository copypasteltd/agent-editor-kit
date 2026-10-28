# Native GPU SDR gamut mapping

Available in pinned installed CLI0.1.52. Read `oklab-gamut.md` for the shared
mapping contract. In native Float32 rendering, set the existing project settings:

```json
{"projection_acceleration":{"mode":"require","device":"0.0"}}
```

Merge this settings fragment without replacing the existing pixel pipeline.
Enumerate and verify the actual local device; `0.0` is the tested RTX3060,
not a portable device guarantee. OpenCL FP64 is required. Use an explicit
`display_mapping` for BT.709/D65 SDR delivery, or `preview_mapping` for viewing
an HDR master. Select `gamut_policy: oklab-chroma`, declare source/target peak
nits, exposure and all source/working/output signals. Output reference white
must match the mapping target. Explicit preview mapping wins; otherwise the
formal mapping is inherited once, then resized in display-linear light.

Use the pinned launcher from `runtime.md` to validate, render and preview.
Check `pixel_pipeline.projection_acceleration.operations.gamut_map` and
`last_display_mapping.perceptual_gamut.GPU` (or `last_preview_mapping` for an
explicit viewing trim). Planned GPU work does not prove actual dispatch.
Show real PNG/MP4 previews and preserve the chosen mapping configuration.
Export/import the editable package and verify complete decoded video and PCM.
Client choices refer to actual viewing media, not the unrelated 500-look gallery.

GPU scope is exposure, modified-Reinhard luminance shoulder and 24-step OKLab
chroma search. Arithmetic is binary64, output Float32; alpha bits are retained.
Signal conversion, ICC and output encoding remain CPU. Fixed OKLab L/hue is
not fixed CIE Y. Black/near-white endpoint mappings have separate counters.
`clip` and `reject` keep their CPU paths. `off` uses CPU; `prefer` may record an
initial preflight fallback. Running GPU failure, timeout or cancellation never
silently becomes a successful CPU render. Keep owned process/pipe/shared-handle
cleanup receipts; do not terminate other GPU jobs.

Three reused device buffers plan 48 bytes/pixel, with 4 bytes/pixel host flags.
This is not full RSS or measured post-exit VRAM. One 4K surface comparison is
not encoded 4K, realtime, natural quality or long-form acceptance. Complete
ACES, soft-knee, dynamic HDR, monitor calibration and cross-vendor acceptance
remain outside this implementation.

Workflow and actual source/installed receipts:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/GPU_GAMUT.md
