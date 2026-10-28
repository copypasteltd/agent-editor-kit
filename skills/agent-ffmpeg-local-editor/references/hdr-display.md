# Explicit HDR and SDR viewing

CLI0.1.40 supports `pq-st2084` and `hlg-bt2100` in the native Float32 pipeline.
Read the packaged `docs/product/HDR_DISPLAY.md` for complete field constraints
and the actual versioned case before authoring a new HDR project.

- Every HDR project's source/working/output signal declares `reference_white_nits`.
  Working transfer is `linear`. PQ/HLG primaries are `bt2020`.
- HLG additionally declares `display_peak_nits` and `system_gamma`; zero black is
  the explicit implementation assumption. PQ uses display EOTF/inverse, not
  a camera OETF. Never infer these quantities from a file's color tags.
- HDR output uses explicit `yuv420p10le`, `yuv422p10le` or `yuv444p10le`,
  `bt2020` primaries, `bt2020nc` matrix and `smpte2084` / `arib-std-b67` transfer
  matching the selected PQ / HLG conversion. Validate before rendering.
- Source `hdr_input_range_policy=clip` is opt-in and reports YCbCr reconstruction
  excursions. Output `range_policy=clip` is a separate explicit decision.
  Show clamping counts to the reviewer; never silently change either policy.
- For `preview frame/range`, explicitly set `preview_mapping` with all five
  fields: `operator=reinhard-luminance`, `source_peak_nits`, `target_peak_nits`,
  `exposure_stops`, `gamut_policy=reject|clip`. PNG and MP4 are SDR viewing trims,
  distinct from the original HDR master. Show the mapping along with the image.
- Optional `display_mapping` makes a separate SDR delivery. Its target peak
  must equal the SDR output signal's `reference_white_nits`.
- Native transfer conversion is tiled CPU math; supported composition/effects
  can retain actual GPU execution. Preserve the input files, author graph,
  original-clock edits and explicit signals through editable package delivery.

Run the pinned installed launcher, validate, inspect a real SDR preview, render
the HDR master and inspect actual decoded pixels/VUI and complete audio. Export
an editable package and test it after importing into a new local directory.
Keep the original HDR master available for a proper HDR display review.

This does not implement ICC, nonzero-black HLG display calibration, perceptual
gamut mapping, mastering-display/CLL/dynamic metadata or Dolby Vision. Synthetic
numeric/encoded checks do not establish natural-footage or HDR monitor quality.

CLI0.1.44 adds optional actual HDR10 static SEI. Read [HDR10 metadata](hdr-metadata.md).

CLI0.1.45 adds explicit Bradford reference-white conversion,ProPhoto D50 and
linear AP1 D60. Read [chromatic adaptation](chromatic-adaptation.md). HDR encoded
BT.2100/output white remains D65; chromaticity is separate from reference nits.

CLI0.1.46 adds [explicit native RGB ICC source profiles](icc-profiles.md). HDR projects require authored reference-white nits on every source, including ICC inputs; ICC tags do not measure luminance.
