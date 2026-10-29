# HDR10 static declarations and actual encoded SEI

Read the packaged `docs/product/HDR_METADATA.md` for the complete JSON and workflow.
Use the installed launcher; inspect `capabilities.native_hdr10_static_metadata`.

- Author `settings.output.hdr10.mastering_display` with RGB/white xy and min/max
  nits, plus `content_light.max_cll_nits/max_fall_nits`. Zero light levels mean
  unknown. Values are declarations; do not fabricate measured peaks.
- Exact xy steps are 1/50000; luminance steps are 1/10000 nit. Invalid precision,
  triangle/white geometry and light relationships fail without silent rounding.
- Select explicit native PQ/BT.2020 NCL limited range, `libx265`, `yuv420p10le`
  and MKV or MP4. x265 encoding is CPU; configured OpenCL composition can use GPU.
- Validate and inspect render dry-run, render, then read
  `delivery.hdr10_static_metadata`. Verification decodes the first32 video packets
  and checks every observed frame's actual SEI plus stream tags before publish.
  It is prefix verification, not a claim about every frame in a long file.
- Present the original HDR master, declared values and separate actual SDR
  PNG/GIF/MP4. SDR viewing copies do not carry HDR declarations and cannot prove
  HDR-monitor appearance. Export an editable package for retained declarations.
- C54 uses actual registered Skill output and GPU composition; full-frame and
  PCM package replay are checked. Inspect failure receipts if SEI is missing.
- Dynamic HDR10+, Dolby Vision, content-peak analysis, ICC adaptation and monitor
  calibration remain outside this feature. Never describe static tags as those.
