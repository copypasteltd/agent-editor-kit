# HDR10 static metadata / 母版显示与内容亮度

CLI 0.1.44 adds explicit HDR10 static declarations to the existing native
Float32/PQ rendering pipeline. The renderer writes actual HEVC SEI and checks
decoded frames before atomically publishing the movie and manifest.

[HDR signals and SDR viewing](HDR_DISPLAY.md) · [README](../../README.md) ·
[繁體中文](../../README.zh-TW.md) · [English](../../README.en.md)

## Authoring and use

Use the installed `$agent-ffmpeg-local-editor` launcher. Initialize a project,
ingest licensed local media and compose the timeline as in the main README.
Declare source, working and output luminance in `settings.pixel_pipeline`.
The following is an **output configuration fragment**, not a complete project:

```json
{
  "container": "mkv",
  "video": {"codec":"libx265","preset":"medium","crf":18,"pixel_format":"yuv420p10le"},
  "audio": {"codec":"pcm_f32le"},
  "hdr10": {
    "mastering_display": {
      "red_xy":[0.68,0.32], "green_xy":[0.265,0.69],
      "blue_xy":[0.15,0.06], "white_xy":[0.3127,0.329],
      "min_luminance_nits":0.0001, "max_luminance_nits":1000
    },
    "content_light": {"max_cll_nits":1000,"max_fall_nits":400}
  }
}
```

Save this fragment under `settings.output` in the editable `project.json`.
Use `color` = BT.2020 primaries, `smpte2084`, `bt2020nc`, `limited` and an
explicit native `pq-st2084` output signal with `reference_white_nits`.
The example's mastering primaries describe a P3-D65 mastering display;
the encoded signal still uses BT.2020 primaries. No mastering device is inferred.

```powershell
& $avk capabilities
& $avk schema show
& $avk validate --project E:/work/my-edit
& $avk render --project E:/work/my-edit --output E:/work/my-edit/renders/hdr.mkv --dry-run
& $avk render --project E:/work/my-edit --output E:/work/my-edit/renders/hdr.mkv
& $avk preview range --project E:/work/my-edit --start-frame 0 --end-frame 24 --height 360
& $avk convert export --project E:/work/my-edit --target-format package --output E:/work/my-edit/exports/edit.zip
```

`$avk` is the unified Skill's `scripts/run.ps1` path. The portable C54 example
includes complete source declarations, actual inputs, an editable package and
the render/preview receipts. CLI encoder overrides must remain compatible:
`libx265`, `yuv420p10le`, limited-range PQ/BT.2020 NCL and MP4/MKV.
MP4 requires AAC audio; MKV also accepts the existing PCM choices.
HLG, SDR, 8-bit, 4:2:2/4:4:4 and hardware-encoder metadata are rejected in this
version. Actual OpenCL composition remains available; x265 encoding uses CPU.

## Values and validation

| Field | Unit and policy |
|---|---|
| `red_xy`, `green_xy`, `blue_xy`, `white_xy` | CIE 1931 xy, two JSON numbers. Exact multiples of 1/50000; x≥0, y>0, x+y≤1. No silent rounding. |
| Mastering primaries / white | Nondegenerate triangle; white strictly inside it. This is validation, not calibration. |
| `min_luminance_nits` | 0–10000 cd/m², exact multiples of 1/10000; strictly below maximum. |
| `max_luminance_nits` | 0.0001–10000 cd/m², exact multiples of 1/10000. |
| `max_cll_nits`, `max_fall_nits` | Integer 0–10000 cd/m². Zero explicitly means unknown; when both are known MaxFALL≤MaxCLL. |

Missing/unknown fields, booleans, nonfinite values, invalid units, invalid
display geometry and incompatible signal/encoder configurations fail clearly.
All values are **author declarations**. The application does not measure
content peaks, infer these values from the SDR preview or manufacture a
physical mastering-display calibration. Set unknown content levels to zero.

The fixed encoder grammar follows the [x265 4.1 metadata
documentation](https://x265.readthedocs.io/en/4.1/cli.html#cmdoption-master-display).
Coordinates become 1/50000 integers; luminance becomes 1/10000-nit integers.
The internal parameter string is built from validated numbers only. Caller
supplied encoder flags or executable code are not accepted in this object.
See also [FFmpeg libx265 options](https://www.ffmpeg.org/ffmpeg-codecs.html#libx265).

## What the output receipt proves

Before publication a native owned/cancellable ffprobe process reads the first
32 video packets, decodes that prefix and returns actual frame side data.
Every observed frame must carry exactly one matching mastering-display and
content-light record. Rational values are compared exactly, including white
point, min/max luminance, MaxCLL and MaxFALL. The actual stream must be HEVC,
10-bit 4:2:0, limited-range BT.2020/PQ/NCL. Missing, duplicate or conflicting
records fail the render before replacement of an existing delivery.

The returned `delivery.hdr10_static_metadata` and movie manifest retain the
declaration, verified decoded-frame count, packet bound and explicit scope.
This proves the **observed prefix**, not every SEI in a long movie. It does not
prove measured content brightness, HDR monitor appearance, ICC/chromatic
adaptation, dynamic HDR10+, Dolby Vision or full CapCut equivalence.

The ordinary preview remains a separately mapped SDR viewing copy. No HDR
static declarations are written into that preview. Its PNG/GIF/MP4 cannot
validate HDR monitoring. Export/import retains the editable declarations;
the C54 case compares all decoded video frames and all PCM samples after
package replay. Complete-project checks and historical closure conditions
remain in the product roadmap.

CLI0.1.49 adds [actual all-frame light metering and colour receipt totals](HDR_MEASUREMENT.md). MaxRGB/CIE Y and declared SEI remain separate;the measurement is before YUV/codec,not physical monitor acceptance.
