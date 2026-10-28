# 全帧光量测量 / 全影格光量測量 / All-frame light measurement

CLI **0.1.49** measures the actual authored timeline through the same native
Float32 delivery conversion as normal rendering. It also fixes the native
Float32 intermediate bundle's missing all-frame colour receipts. This is a local
build; immutable public alpha.3 downloads retain their original CLI0.1.2 scope.

## 使用流程 / 使用流程 / Workflow

Use the installed unified `$agent-ffmpeg-local-editor` launcher. Ingest authorized
media and compose the editable project. Set `pixel_pipeline.engine` to
`float32-native-v1`; declare actual sources, linear working RGB and output RGB.
Both working and output signals must explicitly supply `reference_white_nits`.
PQ/HLG retain their full declared signal contracts, including HLG display peak,
system gamma and any nonzero display black. Relative tags alone cannot tell the
meter how bright an image is.

Run each command on one line through the launcher:

```text
validate --project PROJECT
surface measure --project PROJECT --sequence-id SEQUENCE --dry-run
surface measure --project PROJECT --sequence-id SEQUENCE
surface measure --project PROJECT --sequence-id SEQUENCE --start-frame 12 --stop-frame 48
surface measure --project PROJECT --sequence-id SEQUENCE --active-region 0 36 640 288
```

`--start-frame` is inclusive and `--stop-frame` is exclusive, on the timeline's
display CFR clock. These are not native source frame numbers. The default covers
every timeline frame and the full canvas. Explicit `--active-region X Y WIDTH
HEIGHT` selects a fully contained rectangle, for example after a human decides
whether authored letterbox bars belong in the statistic. There is no automatic
black-bar detection or exclusion. Full-frame and active-area averages differ.

The JSON envelope contains the report in `data`. Save it at the caller's chosen
evidence path if needed. The command itself creates no movie/report directory,
rewrites no author project/history and inserts no SEI. Dry-run validates signal,
range, geometry, budgets and selection without opening a native frame provider.
`--cancel-file PATH` cancels source decoding, native GPU work and tiled metering;
cancelled/failed runs return no successful partial peak summary.

## What is measured

The measurement edge is **after authored editing, optional display mapping,
native ICC soft proof, output-signal conversion, explicit reject/clip policy,
and nearest-even RGB16 quantization**. It is before encoder YUV conversion,
chroma subsampling and codec quantization. This is the real common encoder's
RGB16 input; the report includes its complete planar GBR+A transport SHA256 and
byte count for independent comparison with a render manifest. Audio is not
decoded or measured. Supported authored effects still use the selected native
OpenCL backend; the light meter and colour transfer arithmetic use CPU.

Every selected frame is decoded from the native author graph. PQ and HLG are
decoded to display-linear RGB in explicit nits. Two metrics remain separate:

| Field | Exact meaning |
|---|---|
| `peak_pixel.maxrgb` | Largest decoded linear R/G/B nit component across the selected pixels and frames; includes frame/x/y location. |
| `peak_pixel.cie_y` | Largest decoded RGB dot the declared RGB-primary/whitepoint XYZ Y row; includes frame/x/y location. |
| `maximum_frame_average.maxrgb` | Largest spatial frame average of per-pixel max(R,G,B), with the winning frame. |
| `maximum_frame_average.cie_y` | Largest spatial frame average of CIE Y, with the winning frame. |
| `duration_weighted_frame_average_nits` | Average of the frame averages weighted by exact authored frame exposure durations. |
| `minimum_RGB_component_nits` | Smallest decoded RGB component in the selected region. |
| `framed_metrics_sha256` | Ordered, length-prefixed canonical receipt digest covering every selected frame, without retaining an unbounded receipt list. |
| `all_timeline_frames_measured` | True only when the selection covers every authored display frame. |
| `full_canvas_measured` | True only when the selected rectangle is the entire canvas. |

A saturated blue pixel can have a high MaxRGB and low CIE Y. Neither field is
silently renamed to the other. All pixel maxima are retained; noise/ringing and
outlier filtering are not silently removed. Ties choose the first frame and
first raster pixel. A final CFR frame extending beyond authored duration gets
only its actual remaining duration in the weighted average; it remains a full
frame in spatial peak/maximum-frame-average statistics.

The W3C PNG third edition explains why content-light analysis examines every
frame and distinguishes a maximum pixel from the maximum frame average. It also
notes practical outlier filtering considerations. Our report explicitly names
its two algorithms and does not claim filtered mastering certification.
[W3C cLLI, 2025-06-24](https://www.w3.org/TR/2025/REC-png-3-20250624/#cLLI-chunk)

## HDR10 delivery decisions

Inspect both metrics, the complete/partial scope flags and range counts. A
partial range or active-area report cannot certify an entire full-canvas master.
Choose the intended mastering convention deliberately, with its own outlier and
rounding policy. The command does not invent a mastering display, clip measured
values to an invented display peak or modify `settings.output.hdr10`.

For actual HEVC HDR10 SEI, author the explicit integer content-light and mastering
display declaration documented in [HDR10 metadata](HDR_METADATA.md), validate,
render, and inspect the encoded-prefix SEI receipt. The meter's pre-codec pixels
are not the decoded encoded movie. YUV rounding, subsampling and lossy encoding
can change decoded extrema; physical monitor acceptance still requires a display
workflow. MaxCLL/MaxFALL declarations and actual measurement receipts are separate
evidence, not interchangeable claims.

## All-frame colour conversion receipts

`surface export` Float32 bundles retain `colour_boundary` as the historical
**last selected frame** receipt and explicitly mark
`colour_boundary_scope:"last-selected-frame"`. New
`colour_boundary_all_frames` covers every selected native source frame:

* counts summed over all frames and maximum count per frame;
* frames with counted events, first/last affected frame and selected range;
* a length-prefixed SHA256 over each complete ordered conversion receipt;
* no per-movie receipt/pixel cache.

Ordinary native timeline render manifests and `surface measure` use the same
bounded ledger. It counts declared HDR input/output clamps and known application
mapping counters present at that edge. Native CMM-internal gamut compression is
not an application clip count. Standard render's display-map and final integer
clipping counts are additionally available in its existing transport counters;
metering reports those same counters separately. Do not add counters from
different stages and call the sum a count of unique affected pixels.

A real regression fixture puts a below-black HLG clip in frame0 and an in-range
frame last. The last receipt correctly says zero clips; the all-frame ledger
retains the earlier 1,536 clipped RGB components. Old bundles without this new
ledger remain readable; missing history is not inferred from their last frame.
Hash/clock verification of a derived bundle does not recompute the historical
source conversion, prove rights or establish perceptual quality.

## Limits and verification

The meter accepts at most1,000,000 selected frames and16,777,216 pixels per
surface, with side lengths up to16,384. The conservative owned surface/tile
estimate is limited to768MiB; it is not total process RSS, source-cache, GPU/VRAM
or whole-machine memory acceptance. No entire movie pixel or frame-receipt list
is retained. The report includes native provider cleanup, selected GPU receipts,
locked implementation/source dependencies and the frozen project digest.

Only explicitly opaque final delivery is accepted. Transparent data needs a
deliberate background composition first, including outside a selected active
region. No hidden alpha weighting, black background or physical display
brightness is guessed. This does not implement dynamic HDR10+, Dolby Vision,
full ACES, perceptual gamut mapping or natural HDR monitor calibration.


编码后文件复核见[HDR_MEDIA_MEASUREMENT.md](HDR_MEDIA_MEASUREMENT.md)，CLI0.1.50本地安装已支持该命令。
