# 原生 ICC 输出与软打样 / 原生 ICC 輸出與軟打樣 / Native ICC output and soft proof

CLI **0.1.48** adds actual LittleCMS RGB output transforms, individually
profile-embedded straight RGBA16 PNG sequences, authored 48kHz stereo Float32LE
PCM, and native soft proof in the common movie/preview pipeline. Existing
[ICC source conversion](ICC_PROFILES.md) remains available. This is a local
build, not a replacement of the immutable public alpha.3 downloads.

## 使用流程 / 使用流程 / Workflow

Use the installed unified `$agent-ffmpeg-local-editor` launcher. Build an
editable project with `project init`, `media ingest`, and `timeline compose`.
Choose `settings.pixel_pipeline.engine:"float32-native-v1"` and explicitly
declare source RGB/HDR/ICC signals and linear working RGB. See
[HDR mapping](HDR_DISPLAY.md) for a deliberate HDR-to-SDR trim; no monitor
brightness or source transfer is guessed.

Put an authorized RGB ICC v2/v4 file inside the project. Hash its actual bytes
and save a local JSON descriptor such as:

```json
{
  "icc_profile": "profiles/client-output.icc",
  "sha256": "sha256:REPLACE_WITH_ACTUAL_64_HEX_DIGEST",
  "intent": "relative-colorimetric",
  "black_point_compensation": false
}
```

The placeholder is intentionally invalid until replaced. `intent` accepts
`perceptual`, `relative-colorimetric`, `saturation`, or `absolute-colorimetric`.
Profile paths must stay inside the project without symlinks/junctions.
Native output-direction intent support is checked; an input-only A2B profile
is not accepted as an output profile. Actual B2A CLUTs are evaluated by the
pinned MIT LittleCMS 2.19.1 Windows x64 DLL, not replaced by a gamma/matrix look.

```text
validate --project PROJECT
surface render --project PROJECT --sequence-id SEQUENCE --output renders/icc
  --output-profile-json target.json --range-policy reject --dry-run
surface render --project PROJECT --sequence-id SEQUENCE --output renders/icc
  --output-profile-json target.json --range-policy reject
surface inspect-output --project PROJECT --input renders/icc
```

Commands use one line in the actual terminal; line wrapping above is for
reading. Outputs require a new project-local directory and never overwrite
existing deliveries. Optional `--start-frame` / `--stop-frame` select a
zero-based, half-open **CFR timeline** interval, unlike native-source indices
in `surface export`. `--max-output-mib` bounds delivery bytes up to 8192 MiB;
`--cancel-file` cooperatively cancels decoding, GPU work, conversion and audio.
Dry-run validates the profile and conservative budget without media decoding,
rendering, model inference, output directory creation or operation history.

The resulting directory contains:

- `frame-NNNNNNNNN.png`: actual timeline frame, straight RGBA16, exact target
  profile embedded in an `iCCP` chunk in **every** frame.
- `output.icc`: the exact profile bytes, also recorded by SHA-256.
- `audio.f32le`: interleaved stereo Float32 little-endian PCM at 48000Hz.
- `sequence.json`: project/recipe hashes, exact frame indices/times, every
  delivered file hash, audio sample boundaries, native CMM and GPU receipts,
  runtime artifacts, cleanup and all-frame application clipping totals.

Audio is compiled from the same authored audio graph, retaining nested audio,
clip windows, envelopes and routing. The selected interval begins at
`ceil(start_frame / fps * 48000)` and ends at
`ceil(min(stop_frame / fps, authored_duration) * 48000)`. The last rounded-up
video frame never silently extends the authored sound. To audition or mux the
PCM with another authorized delivery, pass FFmpeg `-f f32le -ar 48000 -ac 2`
**before** its `-i audio.f32le`. Raw PCM itself has no self-describing header.

## 软打样 / 軟打樣 / Soft proof

Add this optional object to `settings.pixel_pipeline`:

```json
{
  "proofing": {
    "profile": {
      "icc_profile": "profiles/client-proof.icc",
      "sha256": "sha256:REPLACE_WITH_ACTUAL_64_HEX_DIGEST",
      "intent": "relative-colorimetric",
      "black_point_compensation": false
    },
    "simulation_intent": "absolute-colorimetric"
  }
}
```

Then use normal `render`, `preview frame` and `preview range`. Native
`cmsCreateProofingTransformTHR` runs with `cmsFLAGS_SOFTPROOFING`, returning
linear working RGB before the declared standard video encoding. The CMM API
uses the output profile in both directions; the selected output intent and
relative-colorimetric input support are validated. `simulation_intent` is
the API's final proofing-intent parameter; it is not a second printer output
intent. Gamut alarm colors are not enabled. A matrix-only proof profile can
produce an almost identical result; that is not evidence of a broken transform.
The original bidirectional CLUT diagnostic visibly changes the simulated view.

`reference_white_nits` is **not** accepted inside the proof profile. Proof is
a relative PCS simulation; it does not infer physical paper luminance. HDR
viewing still requires an explicitly authored display mapping. Where a display
mapping is selected, proof is applied after that mapping, before the output
transfer. Without a mapping it acts on the explicitly declared linear working
values. It is a simulation, not a measured HDR display or printer acceptance.

`surface render` performs the requested final device-profile conversion and
**does not apply the view-only proof transform a second time**. Its manifest
states `softproof_applied_to_device_output:false`. Normal movie output retains
its real standard VUI; arbitrary device RGB is never merely relabelled BT.709
or BT.2020 YUV. To review the device PNGs, use a viewer that honors embedded ICC.

Proof profiles participate in actual-byte preview/resume fingerprints and
editable package dependencies. `convert export --target-format package`
snapshots the profile, relocating non-asset profiles into a content-addressed
`assets/color-profiles/` path in the packaged copy. The original author file
is not rewritten. After import, validate, preview and render again. Packaging
profile bytes does not create a license or grant redistribution rights.

## 数值与核验边界 / 數值與核驗邊界 / Numerical and verification boundaries

Working RGB remains Float32 and can contain finite negative/superwhite values.
Alpha is independent straight coverage and remains bit-exact through the CMM;
the PNG boundary explicitly rounds all channels to unsigned16 using nearest-
even rounding after Float64 scaling. If working/reference-white nits are used,
both working and target ICC declarations must provide them; linear values are
scaled by working_nits / output_nits **before** ICC encoding.

`range-policy reject` checks the **CMM's returned device RGB**. `clip` explicitly
clips that returned RGB to 0..1 and counts affected components across all frames.
An ICC curve/table can already map negative values to zero or compress gamut
inside the native transform. That profile-defined behavior is separately
acknowledged; application clipping counts are not a measure of all native CMM
gamut mapping. Original negative/superwhite working component counts are available
at the transform boundary. No generic artist-approved gamut compression is claimed.

The PNG writer emits IHDR / iCCP / bounded IDAT / IEND only, avoiding conflicting
sRGB, cICP, gamma or chromaticity declarations. `surface inspect-output` checks
every file hash, every PNG CRC, every decompressed RGBA16 pixel byte, embedded
profile identity, and PCM finite values/sample counts. It deliberately accepts
this product's noninterlaced filter-0 transport, not every possible external PNG.
Derived-byte verification is not original-media provenance, rights, perceptual
quality, continuous listening or physical-device matching acceptance.

Profiles are limited to 16MiB / 4096 tags, surfaces to 16384 pixels per side /
16777216 pixels, conversion tiles to 262144 pixels, and the declared conversion
workspace to 768MiB. File/runtime read locks, cancellation and native handle
cleanup are verified. Conservative delivery/working estimates are not peak RSS
guarantees. ICC is CPU CMM work; supported timeline operators still use explicitly
selected native OpenCL GPU execution. No global package install or virtualization.

RGB ICC v2/v4 are supported. CMYK, ICC v5, device-link/named-color/abstract
profiles, complete ACES/OCIO, dynamic HDR, measured monitor/printer calibration
and natural-image artistic matching remain open goal conditions.

Primary facts: [W3C PNG Third Edition](https://www.w3.org/TR/2025/REC-png-3-20250624/)
and the pinned [LittleCMS source](https://github.com/mm2/Little-CMS/tree/lcms2.19.1).
No vendor ICC collection, standard PDF pages or proprietary presets are bundled.
